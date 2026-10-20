"""Uji pembacaan halaman tanpa jaringan: judul, teks, tabel, menu navigasi, dan pemotongan."""

from __future__ import annotations

import pytest

from lppm_mcp.halaman import (
    CATATAN_TABEL_KOSONG,
    Halaman,
    isi_halaman,
    menu_navigasi,
    tabel_halaman,
    tautan_berikutnya,
    tautan_isi,
    teks_halaman,
)
from conftest import (
    HALAMAN_BERANDA,
    HALAMAN_DETAIL,
    PORTAL,
    TOKEN_UJI,
    halaman_login,
    halaman_penelitian,
)


# --- teks ------------------------------------------------------------------


def test_teks_hanya_bagian_isi_tanpa_menu_dan_skrip():
    teks = teks_halaman(HALAMAN_BERANDA)

    assert "Selamat datang, King Kong." in teks
    assert "Penelitian aktif" in teks
    assert "Usulan Baru" not in teks  # menu samping
    assert "Hak cipta" not in teks  # footer
    assert "jangan-tampil" not in teks  # skrip


def test_teks_membaca_nilai_isian_tapi_tidak_token():
    """Halaman detail Laravel sering menaruh datanya di <input disabled>."""
    teks = teks_halaman(HALAMAN_DETAIL)

    assert "Rancang Bangun Aplikasi Contoh" in teks
    assert "Hibah Karangan" in teks
    assert "Internal" not in teks  # pilihan yang tidak terpilih
    assert "Penelitian karangan untuk pengujian." in teks
    assert TOKEN_UJI not in teks
    assert "jangan-tampil" not in teks


def test_teks_tabel_satu_baris_per_rekam():
    teks = teks_halaman(halaman_penelitian(1))

    assert "No | Judul | Ketua | Tahun | Status | Aksi" in teks
    assert "1 | Rancang Bangun Aplikasi Contoh | King Kong | 2025 | Disetujui | Hapus" in teks


def test_teks_halaman_tanpa_penanda_isi_membuang_kerangka():
    html = "<html><body><nav><a href='/a'>Menu</a></nav><p>Isi saja</p><footer>Kaki</footer></body></html>"

    assert teks_halaman(html) == "Isi saja"


# --- judul -----------------------------------------------------------------


def test_judul_dari_heading_di_bagian_isi():
    assert Halaman(url=f"{PORTAL}/penelitian", html=halaman_penelitian(1)).judul() == "Daftar Penelitian"


def test_judul_jatuh_ke_title_kalau_isi_tanpa_heading():
    assert Halaman(url=f"{PORTAL}/login", html=halaman_login(TOKEN_UJI)).judul() == "LPPM Contoh"


# --- tabel -----------------------------------------------------------------


def test_tabel_berkunci_nama_kolom_dan_membawa_tautan_baris():
    tabel = tabel_halaman(halaman_penelitian(1), f"{PORTAL}/penelitian")

    assert len(tabel) == 1
    assert tabel[0]["judul"] == "Penelitian Saya"
    assert tabel[0]["kolom"] == ["No", "Judul", "Ketua", "Tahun", "Status", "Aksi"]
    assert tabel[0]["jumlah_baris"] == 2
    pertama = tabel[0]["baris"][0]
    assert pertama["Judul"] == "Rancang Bangun Aplikasi Contoh"
    assert pertama["Ketua"] == "King Kong"
    assert pertama["_tautan"] == [
        {"teks": "Detail", "url": f"{PORTAL}/penelitian/101"},
        {"teks": "Hapus", "url": f"{PORTAL}/penelitian/101/hapus"},
    ]


def test_tabel_tanpa_thead_memakai_baris_th_pertama():
    html = "<table><tr><th>Skema</th><th>Dana</th></tr><tr><td>Internal</td><td>5.000.000</td></tr></table>"

    assert tabel_halaman(html)[0]["baris"] == [{"Skema": "Internal", "Dana": "5.000.000"}]


def test_baris_yang_tidak_cocok_dengan_kolom_dikunci_nomor_urut():
    html = (
        "<table><thead><tr><th>No</th><th>Judul</th></tr></thead>"
        "<tbody><tr><td colspan='2'>No data available in table</td></tr></tbody></table>"
    )

    assert tabel_halaman(html)[0]["baris"] == [{"1": "No data available in table"}]


def test_nama_kolom_kosong_dan_kembar_dibuat_unik():
    html = "<table><thead><tr><th>Nama</th><th></th><th>Nama</th></tr></thead><tr><td>a</td><td>b</td><td>c</td></tr></table>"

    assert tabel_halaman(html)[0]["kolom"] == ["Nama", "kolom_2", "Nama_2"]


def test_tabel_kunci_nilai_tanpa_kepala():
    tabel = tabel_halaman(HALAMAN_DETAIL)

    assert tabel[0]["kolom"] == []
    assert tabel[0]["baris"] == [{"1": "Anggota", "2": "Spider Man"}]


# --- menu navigasi ---------------------------------------------------------


def test_menu_beranda_lengkap_dengan_grup():
    menu = menu_navigasi(HALAMAN_BERANDA, f"{PORTAL}/home", PORTAL)

    assert [(satu["grup"], satu["nama"], satu["path"]) for satu in menu] == [
        ("King Kong", "Profil Saya", "/profil"),
        ("", "Dashboard", "/home"),
        ("Penelitian", "Daftar Penelitian", "/penelitian"),
        ("Penelitian", "Usulan Baru", "/penelitian/create"),
        ("", "Pengabdian (PkM)", "/pengabdian"),
        ("", "Surat Tugas", "/surat-tugas"),
    ]
    assert menu[2]["url"] == f"{PORTAL}/penelitian"


def test_menu_tanpa_logout_logo_dan_host_lain():
    alamat = [satu["url"] for satu in menu_navigasi(HALAMAN_BERANDA, f"{PORTAL}/home", PORTAL)]

    assert not any("logout" in satu for satu in alamat)
    assert not any("siakad" in satu for satu in alamat)
    assert alamat.count(f"{PORTAL}/home") == 1


def test_menu_dropdown_bertingkat_templat_publik():
    menu = menu_navigasi(halaman_login(TOKEN_UJI), f"{PORTAL}/login", PORTAL)

    assert {"nama": "Jurnal Karangan", "grup": "Publikasi > Jurnal", "path": "/jurnal/karangan",
            "url": f"{PORTAL}/jurnal/karangan"} in menu
    assert all(satu["path"] != "/login" for satu in menu)  # tombol login ada di luar <nav>


# --- tautan ----------------------------------------------------------------


def test_tautan_berikutnya_dari_paginasi_laravel():
    assert tautan_berikutnya(halaman_penelitian(1), f"{PORTAL}/penelitian") == f"{PORTAL}/penelitian?page=2"
    assert tautan_berikutnya(halaman_penelitian(2), f"{PORTAL}/penelitian?page=2") == ""


def test_tautan_isi_tanpa_menu_dan_tanpa_duplikat():
    tautan = tautan_isi(halaman_penelitian(1), f"{PORTAL}/penelitian")

    alamat = [satu["url"] for satu in tautan]
    assert f"{PORTAL}/penelitian/102" in alamat
    assert f"{PORTAL}/home" not in alamat  # menu samping
    assert len(alamat) == len(set(alamat))


# --- isi_halaman -----------------------------------------------------------


def test_isi_teks_dipotong_dan_ditandai():
    isi = isi_halaman(Halaman(url=f"{PORTAL}/home", html=HALAMAN_BERANDA), "teks", maks_karakter=10)

    assert len(isi["teks"]) == 10
    assert isi["terpotong"] is True
    assert isi["panjang"] > 10


def test_isi_tabel_dipotong_per_baris():
    isi = isi_halaman(Halaman(url=f"{PORTAL}/penelitian", html=halaman_penelitian(1)), "tabel", maks_karakter=200)

    assert isi["terpotong"] is True
    assert isi["tabel"][0]["jumlah_baris"] == 2
    assert len(isi["tabel"][0]["baris"]) < 2


def test_isi_tabel_kosong_memberi_catatan_ajax():
    html = "<table><thead><tr><th>Judul</th></tr></thead><tbody></tbody></table>"
    isi = isi_halaman(Halaman(url=f"{PORTAL}/penelitian", html=html), "tabel")

    assert isi["catatan"] == CATATAN_TABEL_KOSONG


def test_bentuk_asing_ditolak():
    with pytest.raises(ValueError, match="bentuk"):
        isi_halaman(Halaman(url=PORTAL, html="<p>a</p>"), "pdf")
