"""Uji pembacaan halaman lewat klien: urutan permintaan, batas portal, dan larangan aksi."""

from __future__ import annotations

import pytest

from lppm_mcp.lppm_client import AlamatDitolak, KlienLppm, LppmError, kata_aksi
from lppm_mcp.menu import MenuLppm
from conftest import PASSWORD_UJI, PORTAL, USERNAME_UJI


@pytest.fixture
def klien(situs) -> KlienLppm:
    """Klien berkredensial karangan yang bicara dengan portal tiruan."""
    return KlienLppm(USERNAME_UJI, PASSWORD_UJI)


class DaftarPenelitianKarangan(MenuLppm):
    """Contoh menu turunan, seperti yang kelak ditulis untuk menu penelitian sungguhan."""

    path_bawaan = "/penelitian"
    kunci_path = "LPPM_PATH_PENELITIAN"


def test_halaman_pertama_login_dulu_lalu_membaca(klien, situs):
    halaman = klien.ambil_halaman("/penelitian")

    assert [(satu["metode"], satu["path"]) for satu in situs.permintaan] == [
        ("GET", "/login"),
        ("POST", "/login"),
        ("GET", "/home"),
        ("GET", "/penelitian"),
    ]
    assert halaman.url == f"{PORTAL}/penelitian"
    assert halaman.judul() == "Daftar Penelitian"


def test_sesi_dipakai_ulang_antar_halaman(klien, situs):
    klien.ambil_halaman("/penelitian")
    klien.ambil_halaman("/penelitian/101")

    assert situs.jumlah("POST", "/login") == 1


def test_url_penuh_di_portal_diterima(klien):
    assert klien.ambil_halaman(f"{PORTAL}/penelitian/101").judul() == "Detail Penelitian"


def test_pengalihan_di_dalam_portal_diikuti(klien):
    halaman = klien.ambil_halaman("/pindah")

    assert halaman.url == f"{PORTAL}/penelitian/101"


@pytest.mark.parametrize(
    "alamat",
    [
        "https://siakad.pradita.ac.id/dashboard",  # host lain, walau satu domain kampus
        "//contoh-lain.id/curi",  # tanpa skema
        "http://lppm.pradita.ac.id/penelitian",  # tanpa TLS
        "https://lppm.pradita.ac.id@contoh-lain.id/",  # menyaru lewat userinfo
    ],
)
def test_alamat_di_luar_portal_ditolak_sebelum_login(klien, situs, alamat):
    with pytest.raises(AlamatDitolak, match="di luar portal"):
        klien.ambil_halaman(alamat)
    assert situs.permintaan == []


@pytest.mark.parametrize(
    "alamat",
    ["/logout", "/penelitian/101/hapus", "/pkm/7/delete", "/proposal?aksi=setujui", "/surat-tugas/3/batalkan"],
)
def test_alamat_aksi_ditolak_karena_hanya_membaca(klien, situs, alamat):
    with pytest.raises(AlamatDitolak, match="hanya membaca"):
        klien.ambil_halaman(alamat)
    assert situs.permintaan == []


def test_kata_aksi_dicocokkan_utuh_per_kata():
    """'pengajuan' bukan 'ajukan', dan 'hapusan' bukan 'hapus'."""
    assert kata_aksi(f"{PORTAL}/penelitian/pengajuan") == ""
    assert kata_aksi(f"{PORTAL}/dokumen/hapusan-lama") == ""
    assert kata_aksi(f"{PORTAL}/penelitian/5/hapus") == "hapus"


def test_pengalihan_ke_host_lain_tidak_diikuti(klien, situs):
    """Cookie sesi berlaku untuk seluruh .pradita.ac.id, jadi tidak boleh ikut ke host lain."""
    with pytest.raises(AlamatDitolak, match="dialihkan ke luar portal"):
        klien.ambil_halaman("/tautan-siakad")
    assert all(satu["url"].startswith(PORTAL) for satu in situs.permintaan)


def test_berkas_biner_ditolak(klien):
    with pytest.raises(LppmError, match="application/pdf"):
        klien.ambil_halaman("/dokumen/surat-tugas.pdf")


def test_halaman_tidak_ada_dilaporkan(klien):
    with pytest.raises(LppmError, match="HTTP 404"):
        klien.ambil_halaman("/tidak-ada")


def test_daftar_navigasi_dibaca_dari_beranda(klien):
    menu = klien.daftar_navigasi()

    assert klien.url_beranda == f"{PORTAL}/home"
    assert {"nama": "Surat Tugas", "grup": "", "path": "/surat-tugas", "url": f"{PORTAL}/surat-tugas"} in menu


def test_menu_turunan_menelusuri_paginasi(klien):
    baris = DaftarPenelitianKarangan(klien).baris()

    assert [satu["Judul"] for satu in baris] == [
        "Rancang Bangun Aplikasi Contoh",
        "Analisis Data Karangan",
        "Studi Kasus Fiktif",
    ]


def test_path_menu_bisa_dipindah_lewat_setelan(klien, monkeypatch):
    monkeypatch.setenv("LPPM_PATH_PENELITIAN", "/riset")

    assert DaftarPenelitianKarangan(klien).path() == "/riset"


def test_menu_tanpa_path_ditolak(klien):
    with pytest.raises(LppmError, match="path_bawaan"):
        MenuLppm(klien).halaman()
