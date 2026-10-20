"""Uji login gaya Laravel: token dan nama isian dari form, deteksi gagal, dan login ulang."""

from __future__ import annotations

import pytest

from lppm_mcp.konfigurasi import KonfigurasiError
from lppm_mcp.lppm_client import (
    AlamatDitolak,
    KlienLppm,
    LoginDitolak,
    LppmError,
    baca_form_login,
    samarkan,
)
from conftest import PASSWORD_UJI, PORTAL, TOKEN_UJI, USERNAME_UJI, halaman_login


def test_form_login_dibaca_dari_halamannya():
    """Bentuk yang sama dengan halaman login portal asli per Oktober 2026."""
    form = baca_form_login(halaman_login(TOKEN_UJI), f"{PORTAL}/login")

    assert form.action == f"{PORTAL}/login"
    assert form.method == "POST"
    assert form.field_username == "login"
    assert form.field_password == "password"
    assert form.isian_bawaan == {"_token": TOKEN_UJI}


def test_token_dari_meta_kalau_form_tidak_membawanya():
    html = (
        '<html><head><meta name="csrf-token" content="token-meta"></head><body>'
        '<form method="post" action="/masuk"><input name="email" type="email">'
        '<input name="password" type="password"></form></body></html>'
    )
    form = baca_form_login(html, f"{PORTAL}/masuk")

    assert form.isian_bawaan["_token"] == "token-meta"
    assert form.field_username == "email"
    assert form.action == f"{PORTAL}/masuk"


def test_halaman_tanpa_form_login_ditolak():
    with pytest.raises(LppmError, match="Form login tidak ditemukan"):
        baca_form_login("<html><body><p>Pemeliharaan</p></body></html>", f"{PORTAL}/login")


def test_membuat_klien_belum_menghubungi_portal(situs):
    """Login hanya berjalan saat pemakai memanggil sesuatu yang butuh halaman."""
    klien = KlienLppm(USERNAME_UJI, PASSWORD_UJI)

    assert situs.permintaan == []
    assert klien.sudah_login is False


def test_login_mengirim_token_dan_isian_dari_form(situs):
    klien = KlienLppm(USERNAME_UJI, PASSWORD_UJI).login()

    kiriman = [satu for satu in situs.permintaan if satu["metode"] == "POST"]
    assert len(kiriman) == 1
    assert kiriman[0]["url"] == f"{PORTAL}/login"
    assert kiriman[0]["data"] == {"_token": TOKEN_UJI, "login": USERNAME_UJI, "password": PASSWORD_UJI}
    assert klien.url_beranda == f"{PORTAL}/home"
    assert klien.sudah_login is True


def test_kredensial_diambil_dari_setelan_saat_login(situs, kredensial_di_setelan):
    klien = KlienLppm().login()

    assert klien.sudah_login is True


def test_kredensial_kosong_dilaporkan_sebelum_menghubungi_portal(situs):
    with pytest.raises(KonfigurasiError, match="LPPM_USERNAME, LPPM_PASSWORD"):
        KlienLppm().login()
    assert situs.permintaan == []


def test_login_ditolak_membawa_pesan_portal(situs):
    with pytest.raises(LoginDitolak) as galat:
        KlienLppm(USERNAME_UJI, "sandi-yang-salah").login()

    assert "These credentials do not match our records." in str(galat.value)
    assert "sandi-yang-salah" not in str(galat.value)


def test_pesan_portal_disamarkan_dari_kredensial(situs):
    """Portal yang menggemakan username atau sandi tidak boleh membocorkannya lewat pesan galat."""
    situs.pesan_gagal = f"Akun {USERNAME_UJI} dengan sandi sandi-yang-salah tidak cocok"

    with pytest.raises(LoginDitolak) as galat:
        KlienLppm(USERNAME_UJI, "sandi-yang-salah").login()

    assert USERNAME_UJI not in str(galat.value)
    assert "sandi-yang-salah" not in str(galat.value)
    assert "***" in str(galat.value)


def test_samarkan_mengabaikan_nilai_kosong():
    assert samarkan("tidak ada rahasia", "", "") == "tidak ada rahasia"


def test_kredensial_tidak_muncul_di_repr(situs):
    klien = KlienLppm(USERNAME_UJI, PASSWORD_UJI).login()

    assert PASSWORD_UJI not in repr(klien)
    assert USERNAME_UJI not in repr(klien)


def test_token_csrf_ditolak_dilaporkan_jelas(situs):
    situs.token_di_form = "token-basi"

    with pytest.raises(LppmError, match="419"):
        KlienLppm(USERNAME_UJI, PASSWORD_UJI).login()


def test_form_login_ke_host_lain_tidak_dikirimi_kredensial(situs):
    situs.action_login = "https://pencuri.contoh-lain.id/login"

    with pytest.raises(AlamatDitolak):
        KlienLppm(USERNAME_UJI, PASSWORD_UJI).login()
    assert situs.jumlah("POST", "/login") == 0


def test_sesi_yang_masih_hidup_tidak_login_ulang(situs):
    """Laravel mengalihkan GET /login ke beranda kalau sesinya masih berlaku."""
    situs.masuk = True

    klien = KlienLppm(USERNAME_UJI, PASSWORD_UJI).login()

    assert klien.url_beranda == f"{PORTAL}/home"
    assert situs.jumlah("POST", "/login") == 0


def test_login_ulang_otomatis_saat_sesi_habis(situs):
    klien = KlienLppm(USERNAME_UJI, PASSWORD_UJI)
    assert "Rancang Bangun" in klien.ambil_halaman("/penelitian").teks()

    situs.masuk = False  # sesi Laravel kedaluwarsa setelah dua jam
    halaman = klien.ambil_halaman("/penelitian")

    assert "Rancang Bangun" in halaman.teks()
    assert klien.jumlah_login == 2
    assert situs.jumlah("POST", "/login") == 2


def test_login_ulang_yang_gagal_dilaporkan(situs):
    klien = KlienLppm(USERNAME_UJI, PASSWORD_UJI)
    klien.ambil_halaman("/penelitian")

    situs.masuk = False
    situs.password_benar = "sandi-baru-karangan"  # sandi diganti di tengah jalan

    with pytest.raises(LoginDitolak):
        klien.ambil_halaman("/penelitian")
