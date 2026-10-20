"""REST API portal LPPM Pradita.

Membuka kemampuan yang sama dengan CLI dan MCP lewat HTTP: cek login, menu
navigasi, isi satu halaman, serta jatah, riwayat, dan pengajuan cek Turnitin.
Semua endpoint hanya membaca portal, kecuali POST /turnitin dengan
uji_coba=false.

Kredensial boleh dikirim per permintaan (username dan password di badan JSON,
atau header X-LPPM-Username dan X-LPPM-Password pada GET), jadi satu server
bisa melayani beberapa dosen. Kalau keduanya dikosongkan, dipakai
LPPM_USERNAME dan LPPM_PASSWORD dari setelan server.

Jalankan:
    ./lppm api              # http://localhost:8000

Contoh:
    curl -X POST localhost:8000/halaman -H "Content-Type: application/json" \
         -d '{"path": "/infolppm/profil"}'
"""

from __future__ import annotations

import hashlib
import time
from typing import Literal

from fastapi import APIRouter, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from lppm_mcp import __version__, turnitin
from lppm_mcp.halaman import isi_halaman
from lppm_mcp.konfigurasi import KonfigurasiError, baca_angka, baca_pengaturan
from lppm_mcp.lppm_client import AlamatDitolak, KlienLppm, LoginDitolak, LppmError

# nama perguruan tinggi hanya untuk label; tidak memengaruhi perilaku apa pun
NAMA_INSTANSI = baca_pengaturan("LPPM_NAMA_INSTANSI", "Pradita")

# Rute dikumpulkan di router supaya proyek lain bisa menempelkannya ke aplikasi
# FastAPI miliknya sendiri:
#     from lppm_mcp.api import router
#     app_saya.include_router(router, prefix="/lppm")
router = APIRouter()

# satu klien dipakai ulang selama masih segar; klien itu sendiri yang login
# ulang kalau sesi portalnya habis di tengah jalan
UMUR_SESI_DETIK = baca_angka("LPPM_UMUR_SESI_DETIK", 900)
sesi_tersimpan: dict[str, tuple[float, KlienLppm]] = {}


def buat_app() -> FastAPI:
    """Aplikasi FastAPI berdiri sendiri yang hanya berisi rute paket ini."""
    app = FastAPI(
        title=f"LPPM {NAMA_INSTANSI} API",
        version=__version__,
        description=(
            "Baca portal LPPM: cek login, menu navigasi, isi satu halaman, serta jatah dan riwayat "
            "cek Turnitin. Satu-satunya endpoint yang bisa menulis adalah POST /turnitin dengan "
            "uji_coba=false."
        ),
    )
    app.include_router(router)
    return app


class Kredensial(BaseModel):
    """Kredensial portal. Kosongkan keduanya untuk memakai setelan server."""

    username: str = Field(default="", description="NIDN atau email; kosong berarti setelan server")
    password: str = Field(default="", description="Password portal; kosong berarti setelan server")


class PermintaanHalaman(Kredensial):
    """Satu halaman yang dibaca beserta bentuk keluarannya."""

    path: str = Field(description="Path atau URL penuh di bawah portal LPPM, mis. /infolppm/profil")
    bentuk: Literal["teks", "tabel"] = Field(default="teks", description="teks atau tabel")
    maks_karakter: int = Field(default=0, ge=0, description="Potong keluaran sepanjang ini; 0 berarti utuh")


class PermintaanTurnitin(Kredensial):
    """Satu pengajuan cek Turnitin. Bawaannya uji coba: tidak ada yang dikirim."""

    judul: str = Field(description="Judul naskah")
    tautan: str = Field(
        description="Tautan Google Drive naskah: https://drive.google.com/... atau https://docs.google.com/..."
    )
    uji_coba: bool = Field(
        default=True,
        description="true (bawaan): kembalikan rencana kiriman tanpa mengirim; false: kirim dan pakai satu jatah",
    )
    paksa: bool = Field(default=False, description="true: tetap ajukan walau judul yang sama sudah ada di riwayat")


def kunci_sesi(kredensial: Kredensial) -> str:
    """Kunci penyimpanan sesi. Password hanya disimpan sebagai sidik SHA-256."""
    if not kredensial.username and not kredensial.password:
        return "setelan"
    sidik = hashlib.sha256(kredensial.password.encode("utf-8")).hexdigest()
    return f"{kredensial.username}:{sidik}"


def galat_http(galat: Exception) -> HTTPException:
    """Terjemahkan kesalahan pustaka ke status HTTP yang sesuai."""
    if isinstance(galat, KonfigurasiError):
        return HTTPException(status_code=400, detail=str(galat))
    if isinstance(galat, (AlamatDitolak, turnitin.PengajuanDitolak)):
        return HTTPException(status_code=422, detail=str(galat))
    if isinstance(galat, LoginDitolak):
        return HTTPException(status_code=401, detail=str(galat))
    return HTTPException(status_code=502, detail=str(galat))


def ambil_klien(kredensial: Kredensial) -> KlienLppm:
    """Klien untuk kredensial ini, dipakai ulang selama masih segar. Login berjalan saat dibutuhkan."""
    if bool(kredensial.username) != bool(kredensial.password):
        raise HTTPException(status_code=422, detail="Isi username dan password sekaligus, atau kosongkan keduanya")
    kunci = kunci_sesi(kredensial)
    tersimpan = sesi_tersimpan.get(kunci)
    if tersimpan and time.monotonic() - tersimpan[0] < UMUR_SESI_DETIK:
        return tersimpan[1]
    try:
        klien = KlienLppm(kredensial.username or None, kredensial.password or None)
    except KonfigurasiError as galat:
        raise galat_http(galat) from galat
    sesi_tersimpan[kunci] = (time.monotonic(), klien)
    return klien


@router.post("/sesi", summary="Cek kredensial LPPM")
def cek_sesi(kredensial: Kredensial) -> dict:
    """Login (atau pakai sesi yang masih hidup), lalu kembalikan alamat berandanya."""
    klien = ambil_klien(kredensial)
    try:
        klien.login()
    except (LppmError, KonfigurasiError) as galat:
        raise galat_http(galat) from galat
    return {"ok": True, "beranda": klien.url_beranda}


@router.post("/menu", summary="Menu navigasi portal setelah login")
def daftar_menu(kredensial: Kredensial) -> dict:
    """Tautan menu yang terlihat di beranda, lengkap dengan grup induknya."""
    klien = ambil_klien(kredensial)
    try:
        menu = klien.daftar_navigasi()
    except (LppmError, KonfigurasiError) as galat:
        raise galat_http(galat) from galat
    return {"beranda": klien.url_beranda, "data": menu}


@router.post("/halaman", summary="Isi satu halaman portal sebagai teks atau tabel")
def ambil_halaman(permintaan: PermintaanHalaman) -> dict:
    """Hanya GET. Alamat di luar portal atau yang tampak seperti aksi dibalas 422."""
    klien = ambil_klien(permintaan)
    try:
        halaman = klien.ambil_halaman(permintaan.path)
    except (LppmError, KonfigurasiError) as galat:
        raise galat_http(galat) from galat
    return isi_halaman(halaman, permintaan.bentuk, permintaan.maks_karakter)


@router.get("/turnitin", summary="Jatah dan riwayat pengajuan cek Turnitin")
def status_turnitin(
    x_lppm_username: str = Header(default="", description="NIDN atau email; kosong berarti setelan server"),
    x_lppm_password: str = Header(default="", description="Password portal; kosong berarti setelan server"),
) -> dict:
    """Hanya membaca. Kredensial per permintaan dikirim lewat header karena GET tidak berbadan."""
    klien = ambil_klien(Kredensial(username=x_lppm_username, password=x_lppm_password))
    try:
        status = turnitin.daftar_turnitin(klien)
    except (LppmError, KonfigurasiError) as galat:
        raise galat_http(galat) from galat
    return status.sebagai_dict()


@router.post("/turnitin", summary="Ajukan cek Turnitin (bawaannya uji coba)")
def ajukan_turnitin(permintaan: PermintaanTurnitin) -> dict:
    """Dengan uji_coba=true (bawaan) hanya rencana kiriman dan jatahnya yang dikembalikan.

    Dengan uji_coba=false form dikirim sekali dan memakai satu jatah. Isian
    yang tidak sah, jatah habis, dan judul kembar dibalas 422 tanpa mengirim
    apa pun. Hasil yang tidak pasti sesudah kiriman dibalas 502; periksa
    GET /turnitin sebelum mencoba lagi.
    """
    klien = ambil_klien(permintaan)
    try:
        hasil = turnitin.ajukan_turnitin(
            klien, permintaan.judul, permintaan.tautan, uji_coba=permintaan.uji_coba, paksa=permintaan.paksa
        )
    except (LppmError, KonfigurasiError) as galat:
        raise galat_http(galat) from galat
    return hasil.sebagai_dict()


app = buat_app()
