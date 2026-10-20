"""Uji akar proyek (berdiri sendiri vs dipakai proyek lain), urutan setelan, dan alamat portal."""

from __future__ import annotations

from pathlib import Path

import pytest

from lppm_mcp import konfigurasi
from lppm_mcp.lppm_client import KlienLppm, tentukan_alamat


@pytest.fixture
def akar_tiruan(tmp_path):
    """Akar proyek tiruan, dipasang lewat API yang dipakai proyek pemanggil."""
    konfigurasi.atur_akar_proyek(tmp_path)
    return tmp_path


# --- akar proyek -----------------------------------------------------------


def test_berdiri_sendiri_berakar_di_repositori_ini():
    """Mode pertama: repositori di-clone lalu dijalankan apa adanya."""
    konfigurasi.atur_akar_proyek(None)
    akar = konfigurasi.akar_bawaan()

    assert (akar / "pyproject.toml").is_file()
    assert konfigurasi.akar_proyek() == akar


def test_env_proyek_induk_tidak_ikut_terpungut(tmp_path):
    """Direktori di atas akar tidak pernah ditelusuri.

    Penelusuran ke atas membuat kredensial yang terpakai bergantung pada letak
    folder, dan bisa jadi milik proyek lain.
    """
    induk = tmp_path / "induk"
    aplikasi = induk / "app"
    aplikasi.mkdir(parents=True)
    (induk / ".env").write_text("LPPM_USERNAME=induk\nLPPM_PASSWORD=induk\n")
    konfigurasi.atur_akar_proyek(aplikasi)

    assert konfigurasi.berkas_env() == aplikasi / ".env"
    with pytest.raises(konfigurasi.KonfigurasiError):
        konfigurasi.baca_kredensial("LPPM_USERNAME", "LPPM_PASSWORD")


def test_proyek_pemanggil_menentukan_akarnya_sendiri(akar_tiruan):
    """Mode kedua: proyek lain memasang paket ini dan menunjuk akarnya."""
    assert konfigurasi.akar_proyek() == akar_tiruan
    assert konfigurasi.dir_data() == akar_tiruan / "data"


def test_akar_lewat_environment(tmp_path, monkeypatch):
    konfigurasi.atur_akar_proyek(None)
    monkeypatch.setenv("LPPM_AKAR_PROYEK", str(tmp_path))

    assert konfigurasi.akar_proyek() == tmp_path


# --- urutan setelan --------------------------------------------------------


def test_setelan_yaml_dibaca(akar_tiruan):
    (akar_tiruan / "lppm.yaml").write_text("nama_instansi: Kampus Karangan\nbatas_halaman_detik: 30\n")

    assert konfigurasi.baca_pengaturan("LPPM_NAMA_INSTANSI", "Pradita") == "Kampus Karangan"
    assert konfigurasi.baca_angka("LPPM_BATAS_HALAMAN_DETIK", 120) == 30


def test_berkas_env_menang_atas_yaml(akar_tiruan):
    (akar_tiruan / "lppm.yaml").write_text("nama_instansi: Dari YAML\n")
    (akar_tiruan / ".env").write_text("LPPM_NAMA_INSTANSI=Dari ENV\n")

    assert konfigurasi.baca_pengaturan("LPPM_NAMA_INSTANSI") == "Dari ENV"


def test_environment_menang_atas_berkas_env(akar_tiruan, monkeypatch):
    (akar_tiruan / ".env").write_text("LPPM_NAMA_INSTANSI=Dari ENV\n")
    monkeypatch.setenv("LPPM_NAMA_INSTANSI", "Dari environment")

    assert konfigurasi.baca_pengaturan("LPPM_NAMA_INSTANSI") == "Dari environment"


def test_setelan_dari_kode_menang_atas_environment(akar_tiruan, monkeypatch):
    """Proyek yang menyetel dari kode tidak boleh berubah karena environment mesin."""
    monkeypatch.setenv("LPPM_NAMA_INSTANSI", "Dari environment")
    konfigurasi.atur_setelan(nama_instansi="Dari kode")

    assert konfigurasi.baca_pengaturan("LPPM_NAMA_INSTANSI") == "Dari kode"


def test_setelan_dari_kode_menerima_kedua_gaya_nama(akar_tiruan):
    konfigurasi.atur_setelan(LPPM_BASE_URL="https://a.ac.id")
    assert konfigurasi.baca_pengaturan("LPPM_BASE_URL") == "https://a.ac.id"

    konfigurasi.atur_setelan(base_url="https://b.ac.id")
    assert konfigurasi.baca_pengaturan("LPPM_BASE_URL") == "https://b.ac.id"


def test_setelan_tanpa_yaml_memakai_nilai_bawaan(akar_tiruan):
    assert konfigurasi.berkas_konfigurasi() is None
    assert konfigurasi.baca_pengaturan("LPPM_NAMA_INSTANSI", "Pradita") == "Pradita"


def test_angka_tidak_masuk_akal_ditolak_jelas(akar_tiruan, monkeypatch):
    monkeypatch.setenv("LPPM_BATAS_HALAMAN_DETIK", "selama mungkin")

    with pytest.raises(konfigurasi.KonfigurasiError, match="harus berupa angka"):
        konfigurasi.baca_angka("LPPM_BATAS_HALAMAN_DETIK", 120)


# --- kredensial ------------------------------------------------------------


def test_kredensial_tidak_pernah_dibaca_dari_yaml(akar_tiruan):
    """lppm.yaml dimaksudkan untuk dibagikan, jadi kata sandi di sana diabaikan."""
    (akar_tiruan / "lppm.yaml").write_text("username: dosen\npassword: bocor\n")

    with pytest.raises(konfigurasi.KonfigurasiError, match="LPPM_PASSWORD"):
        konfigurasi.baca_kredensial("LPPM_USERNAME", "LPPM_PASSWORD")


def test_kredensial_dari_berkas_env(akar_tiruan):
    (akar_tiruan / ".env").write_text("LPPM_USERNAME=0000000001\nLPPM_PASSWORD=sandi-karangan\n")

    assert konfigurasi.baca_kredensial("LPPM_USERNAME", "LPPM_PASSWORD") == {
        "LPPM_USERNAME": "0000000001",
        "LPPM_PASSWORD": "sandi-karangan",
    }


def test_kredensial_boleh_datang_dari_kode_tanpa_berkas_env(akar_tiruan):
    """Proyek pemakai tidak wajib menyediakan .env sama sekali."""
    konfigurasi.atur_setelan(LPPM_USERNAME="a@contoh.ac.id", LPPM_PASSWORD="rahasia-karangan")

    assert konfigurasi.baca_kredensial("LPPM_USERNAME", "LPPM_PASSWORD")["LPPM_PASSWORD"] == "rahasia-karangan"


def test_pesan_kredensial_kurang_hanya_menyebut_nama_kunci(akar_tiruan):
    konfigurasi.atur_setelan(LPPM_USERNAME="0000000001")

    with pytest.raises(konfigurasi.KonfigurasiError) as galat:
        konfigurasi.baca_kredensial("LPPM_USERNAME", "LPPM_PASSWORD")
    assert "LPPM_PASSWORD" in str(galat.value)
    assert "0000000001" not in str(galat.value)


def test_kesalahan_setelan_bukan_systemexit(akar_tiruan):
    """Pustaka tidak boleh menghentikan program yang memakainya."""
    with pytest.raises(Exception) as galat:
        konfigurasi.baca_kredensial("LPPM_USERNAME", "LPPM_PASSWORD")
    assert not isinstance(galat.value, SystemExit)


# --- sesi HTTP dan alamat portal --------------------------------------------


def test_sesi_http_selalu_memverifikasi_tls():
    assert konfigurasi.buat_sesi_http().verify is True


def test_uji_tidak_bisa_menyentuh_jaringan():
    """Pagar di conftest: sesi HTTP sungguhan diblokir selama uji (.invalid tidak pernah ada)."""
    with pytest.raises(AssertionError, match="jaringan sungguhan"):
        konfigurasi.buat_sesi_http().get("https://contoh.invalid/")


def test_tidak_ada_kode_yang_mematikan_verifikasi_tls():
    """Verifikasi TLS tidak boleh dimatikan di mana pun dalam paket."""
    sumber = "".join(
        berkas.read_text(encoding="utf-8") for berkas in Path(konfigurasi.__file__).parent.glob("*.py")
    )
    assert "verify=False" not in sumber.replace(" ", "")


def test_alamat_bawaan_portal_pradita():
    assert tentukan_alamat() == ("https://lppm.pradita.ac.id", "https://lppm.pradita.ac.id/login")


def test_alamat_cukup_dari_lppm_website(monkeypatch):
    """Isi .env.contoh hanya menyebut LPPM_WEBSITE; alamat portal diturunkan darinya."""
    monkeypatch.setenv("LPPM_WEBSITE", "https://lppm.kampus-karangan.ac.id/login")

    assert tentukan_alamat() == ("https://lppm.kampus-karangan.ac.id", "https://lppm.kampus-karangan.ac.id/login")


def test_argumen_pemanggil_menang_atas_setelan(monkeypatch):
    monkeypatch.setenv("LPPM_WEBSITE", "https://lppm.pradita.ac.id/login")

    klien = KlienLppm(base_url="https://lppm.kampus-karangan.ac.id/")
    assert klien.base_url == "https://lppm.kampus-karangan.ac.id"
    assert klien.url_login == "https://lppm.kampus-karangan.ac.id/login"


def test_alamat_portal_harus_https():
    with pytest.raises(konfigurasi.KonfigurasiError, match="https"):
        KlienLppm(base_url="http://lppm.pradita.ac.id")


def test_halaman_login_di_host_lain_ditolak(monkeypatch):
    """Kata sandi hanya boleh dikirim ke host portal itu sendiri."""
    monkeypatch.setenv("LPPM_BASE_URL", "https://lppm.pradita.ac.id")
    monkeypatch.setenv("LPPM_WEBSITE", "https://masuk.contoh-lain.id/login")

    with pytest.raises(konfigurasi.KonfigurasiError, match="harus https dan berada di"):
        KlienLppm()
