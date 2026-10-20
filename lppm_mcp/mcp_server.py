"""MCP server portal LPPM Pradita.

Membuka kemampuan yang sama dengan CLI dan REST API lewat protokol MCP, sehingga
asisten AI bisa memakai sendiri portal LPPM: cek login, menu navigasi, isi satu
halaman, serta jatah, riwayat, dan pengajuan cek Turnitin. Semua tool hanya
membaca, kecuali ajukan_turnitin dengan uji_coba=False.

Kredensial tidak diterima lewat parameter tool. Semuanya dibaca dari setelan
(LPPM_USERNAME dan LPPM_PASSWORD di .env atau environment), jadi asisten tidak
pernah memegang kata sandi. Login baru berjalan saat tool pertama dipanggil,
dan sesinya dipakai ulang antar-pemanggilan sampai habis.

Daftarkan ke Claude Code (perintah `lppm-mcp` ikut terpasang bersama paketnya):
    claude mcp add lppm-mcp -- lppm-mcp
"""

from __future__ import annotations

from typing import Literal

from mcp.server.mcpserver import MCPServer

from lppm_mcp import __version__, turnitin
from lppm_mcp.halaman import isi_halaman
from lppm_mcp.konfigurasi import KonfigurasiError, baca_pengaturan
from lppm_mcp.lppm_client import LPPM_BASE_URL_BAWAAN, KlienLppm, LppmError, tentukan_alamat

MAKS_KARAKTER_BAWAAN = 20000


def alamat_portal() -> str:
    """Alamat portal untuk teks instruksi; setelan yang belum benar jatuh ke alamat bawaan."""
    try:
        return tentukan_alamat()[0]
    except KonfigurasiError:
        return LPPM_BASE_URL_BAWAAN


# instruksi menyebut instansi dan alamatnya supaya asisten tahu sistem mana yang
# sedang dipakai; keduanya ikut setelan, tidak ditanam di teks
NAMA_INSTANSI = baca_pengaturan("LPPM_NAMA_INSTANSI", "Pradita")

server = MCPServer(
    name="lppm-mcp",
    version=__version__,
    instructions=(
        f"Membaca portal LPPM {NAMA_INSTANSI} ({alamat_portal()}): penelitian, "
        "pengabdian kepada masyarakat (PkM), surat tugas, dan dokumen dosen, "
        "serta memantau dan mengajukan cek Turnitin. Urutan yang disarankan: cek_login, lalu "
        "daftar_menu untuk melihat menu yang tersedia bagi akun ini, lalu "
        "ambil_halaman dengan path dari menu itu (bentuk='tabel' untuk halaman "
        "daftar). daftar_turnitin menampilkan jatah dan riwayat cek Turnitin. "
        "Semua tool hanya membaca, kecuali ajukan_turnitin. Jatah cek Turnitin "
        "terbatas (2 per pemakai) dan setiap kiriman memakai satu jatah, jadi "
        "jalankan ajukan_turnitin dengan uji_coba=True lebih dulu, tunjukkan "
        "rencananya dan sisa jatahnya ke pemakai, lalu kirim dengan "
        "uji_coba=False hanya setelah pemakai menyetujuinya. Kalau hasilnya "
        "tidak pasti, periksa daftar_turnitin dan jangan mengirim ulang. "
        "Kredensial diambil dari setelan server (.env); jangan meminta kata sandi "
        "ke pemakai. Tautan aksi seperti hapus, setujui, atau logout ditolak."
    ),
)

# Satu klien untuk seluruh pemanggilan tool, supaya tidak login ulang setiap
# kali. cek_login menggantinya dengan klien baru yang baru saja login.
klien_tersimpan: KlienLppm | None = None


def klien_bersama() -> KlienLppm:
    """Klien yang dipakai bersama tool; dibuat saat pertama dibutuhkan, belum login."""
    global klien_tersimpan
    if klien_tersimpan is None:
        klien_tersimpan = KlienLppm()
    return klien_tersimpan


@server.tool()
def cek_login() -> dict:
    """Cek apakah kredensial LPPM di setelan (.env) bisa dipakai login.

    Selalu login ulang dari awal, jadi berguna juga setelah .env diubah.
    """
    global klien_tersimpan
    try:
        klien = KlienLppm().login()
    except (LppmError, KonfigurasiError) as galat:
        return {"ok": False, "pesan": str(galat)}
    klien_tersimpan = klien
    return {"ok": True, "beranda": klien.url_beranda}


@server.tool()
def daftar_menu() -> dict:
    """Menu navigasi portal LPPM yang tersedia bagi akun ini, dibaca dari beranda setelah login.

    Tiap entri berisi nama, grup induknya (mis. "Penelitian"), path, dan URL.
    Path-nya bisa langsung dipakai di ambil_halaman.
    """
    try:
        klien = klien_bersama()
        menu = klien.daftar_navigasi()
    except (LppmError, KonfigurasiError) as galat:
        return {"ok": False, "pesan": str(galat)}
    return {"ok": True, "beranda": klien.url_beranda, "jumlah": len(menu), "menu": menu}


@server.tool()
def ambil_halaman(
    path: str,
    bentuk: Literal["teks", "tabel"] = "teks",
    maks_karakter: int = MAKS_KARAKTER_BAWAAN,
) -> dict:
    """Baca satu halaman portal LPPM (hanya GET) sebagai teks atau tabel.

    `path` boleh path relatif (mis. /infolppm/profil) atau URL penuh, asalkan
    berada di portal LPPM. bentuk="teks" mengembalikan isi halaman tanpa menu
    dan skrip; bentuk="tabel" mengembalikan tiap tabel sebagai baris berkunci
    nama kolom, dengan tautan tiap baris di `_tautan`. `maks_karakter` membatasi
    panjang keluaran (0 berarti utuh); `terpotong` menandai kalau batas itu
    tercapai. Alamat di luar portal dan tautan aksi (hapus, setujui, logout,
    dan sejenisnya) ditolak.
    """
    try:
        halaman = klien_bersama().ambil_halaman(path)
        return {"ok": True, **isi_halaman(halaman, bentuk, maks_karakter)}
    except (LppmError, KonfigurasiError, ValueError) as galat:
        return {"ok": False, "pesan": str(galat)}


@server.tool()
def daftar_turnitin() -> dict:
    """Jatah dan riwayat pengajuan cek Turnitin di portal LPPM (hanya membaca).

    `jatah` berisi dipakai, total, dan sisa. Tiap baris `riwayat` berisi no,
    judul, tanggal_submit (ISO 8601), no_surat (null selama portal menulis "-"),
    dan status. Kolom Aksi dicatat apa adanya: aksi_teks, aksi_tautan (setiap
    href), aksi_pemicu (atribut data-* seperti data-toggle dan data-target,
    beserta teks modal yang dituju), dan ada_modal_perbaikan. Jangan menebak arti
    kolom Aksi selain dari isinya.
    """
    try:
        status = turnitin.daftar_turnitin(klien_bersama())
    except (LppmError, KonfigurasiError) as galat:
        return {"ok": False, "pesan": str(galat)}
    return {"ok": True, **status.sebagai_dict()}


@server.tool()
def ajukan_turnitin(judul: str, tautan: str, uji_coba: bool = True, paksa: bool = False) -> dict:
    """Ajukan satu naskah untuk dicek Turnitin oleh LPPM.

    Dengan uji_coba=False tool ini menulis ke portal dan memakai satu jatah,
    padahal jatahnya terbatas (2 per pemakai). Bawaannya uji coba: judul,
    tautan, jatah, dan riwayat diperiksa, lalu rencana kirimannya dikembalikan
    tanpa mengirim apa pun. Tunjukkan rencana itu ke pemakai dan kirim hanya
    setelah pemakai menyetujuinya.

    `tautan` harus https ke drive.google.com atau docs.google.com. Judul yang
    sudah ada di riwayat ditolak, kecuali paksa=True. Sesudah kiriman, `diterima`
    bernilai true kalau baris barunya muncul di riwayat. Kalau `terkirim` true
    tapi hasilnya tidak pasti, periksa daftar_turnitin dan jangan mengirim ulang.
    """
    try:
        hasil = turnitin.ajukan_turnitin(klien_bersama(), judul, tautan, uji_coba=uji_coba, paksa=paksa)
    except turnitin.HasilTidakPasti as galat:
        return {"ok": False, "terkirim": True, "pesan": str(galat)}
    except (LppmError, KonfigurasiError) as galat:
        return {"ok": False, "terkirim": False, "pesan": str(galat)}
    return {"ok": hasil.uji_coba or hasil.diterima, **hasil.sebagai_dict()}


def jalankan() -> None:
    """Titik masuk perintah `lppm-mcp` (stdio)."""
    server.run()


if __name__ == "__main__":
    jalankan()
