"""Uji ketiga antarmuka (CLI, MCP, REST API) di atas portal tiruan.

Yang diperiksa terutama hal yang tidak boleh bocor: kredensial tidak tercetak,
tool MCP tidak menerima kata sandi lewat parameter, dan galat dilaporkan rapi.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from lppm_mcp import cli
from conftest import (
    JUDUL_TURNITIN_UJI,
    PASSWORD_UJI,
    PORTAL,
    TAUTAN_NASKAH_UJI,
    TOKEN_UJI,
    USERNAME_UJI,
    JawabanTiruan,
)

JUDUL_BARU = "Rancangan Sistem Karangan untuk Kota Metropolis"


# --- CLI -------------------------------------------------------------------


def test_cli_cek_login_berhasil_tanpa_mencetak_kredensial(situs, kredensial_di_setelan, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["lppm-cek-login"])

    assert cli.jalankan_cek_login() == 0
    keluaran = capsys.readouterr()
    assert "Login LPPM OK" in keluaran.out
    assert PASSWORD_UJI not in keluaran.out + keluaran.err
    assert USERNAME_UJI not in keluaran.out + keluaran.err


def test_cli_cek_login_gagal_keluar_dengan_kode_1(situs, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["lppm-cek-login"])

    assert cli.jalankan_cek_login() == 1
    assert "Gagal: Kredensial belum ada" in capsys.readouterr().err


def test_cli_halaman_teks(situs, kredensial_di_setelan, capsys):
    assert cli.main_halaman(["/penelitian/101"]) == 0

    keluaran = capsys.readouterr().out
    assert keluaran.startswith("Detail Penelitian\n")
    assert "Hibah Karangan" in keluaran


def test_cli_halaman_tabel_json(situs, kredensial_di_setelan, capsys):
    assert cli.main_halaman(["/penelitian", "--tabel", "--json"]) == 0

    isi = json.loads(capsys.readouterr().out)
    assert isi["tabel"][0]["baris"][1]["Ketua"] == "Spider Man"


def test_cli_menu(situs, kredensial_di_setelan, capsys):
    assert cli.main_menu([]) == 0

    keluaran = capsys.readouterr().out
    assert "Penelitian > Usulan Baru" in keluaran
    assert "/surat-tugas" in keluaran


def test_cli_turnitin_mencetak_jatah_dan_riwayat(situs, kredensial_di_setelan, capsys):
    assert cli.main_turnitin([]) == 0

    keluaran = capsys.readouterr().out
    assert "Jatah cek Turnitin: 1 dari 2 terpakai, sisa 1" in keluaran
    assert f"1 | {JUDUL_TURNITIN_UJI} | 20/10/2026 15:15 | - | Submit | Proses LPPM" in keluaran


def test_cli_turnitin_json(situs, kredensial_di_setelan, capsys):
    assert cli.main_turnitin(["--json"]) == 0

    isi = json.loads(capsys.readouterr().out)
    assert isi["jatah"]["sisa"] == 1
    assert isi["riwayat"][0]["no_surat"] is None
    assert isi["riwayat"][0]["tanggal_submit"] == "2026-10-20T15:15"


def test_cli_turnitin_ajukan_tanpa_kirim_hanya_uji_coba(situs, kredensial_di_setelan, capsys):
    assert cli.main_turnitin(["ajukan", "--judul", JUDUL_BARU, "--tautan", TAUTAN_NASKAH_UJI]) == 0

    keluaran = capsys.readouterr().out
    assert keluaran.startswith("Uji coba: belum ada yang dikirim.")
    assert f"POST {PORTAL}/turnitin" in keluaran
    assert f"judul_naskah  {JUDUL_BARU}" in keluaran
    assert "Tambahkan --kirim" in keluaran
    assert TOKEN_UJI not in keluaran
    assert situs.jumlah("POST", "/turnitin") == 0


def test_cli_turnitin_ajukan_kirim(situs, kredensial_di_setelan, capsys):
    argumen = ["ajukan", "--judul", JUDUL_BARU, "--tautan", TAUTAN_NASKAH_UJI, "--kirim"]

    assert cli.main_turnitin(argumen) == 0
    keluaran = capsys.readouterr().out
    assert keluaran.startswith("Pengajuan terkirim dan tercatat di riwayat.")
    assert "[success] Pengajuan Cek Turnitin berhasil dikirim." in keluaran
    assert "Jatah: 2 dari 2 terpakai, sisa 0" in keluaran
    assert situs.jumlah("POST", "/turnitin") == 1


def test_cli_turnitin_kiriman_yang_tidak_tercatat_keluar_dengan_kode_1(situs, kredensial_di_setelan, capsys):
    situs.turnitin_galat_validasi = "Link naskah harus dapat dibuka LPPM."

    assert cli.main_turnitin(["ajukan", "--judul", JUDUL_BARU, "--tautan", TAUTAN_NASKAH_UJI, "--kirim"]) == 1
    assert "[danger] Link naskah harus dapat dibuka LPPM." in capsys.readouterr().out


def test_cli_turnitin_json_boleh_sebelum_sub_perintah(situs, kredensial_di_setelan, capsys):
    assert cli.main_turnitin(["--json", "ajukan", "--judul", JUDUL_BARU, "--tautan", TAUTAN_NASKAH_UJI]) == 0

    isi = json.loads(capsys.readouterr().out)
    assert isi["uji_coba"] is True
    assert isi["isian"] == {"judul_naskah": JUDUL_BARU, "file_artikel": TAUTAN_NASKAH_UJI}


def test_cli_turnitin_tautan_tidak_sah_keluar_dengan_kode_1(situs, kredensial_di_setelan, capsys, monkeypatch):
    argumen = ["lppm-turnitin", "ajukan", "--judul", JUDUL_BARU, "--tautan", "http://contoh.id/a"]
    monkeypatch.setattr("sys.argv", argumen)

    assert cli.jalankan_turnitin() == 1
    assert "Gagal: Tautan naskah harus https" in capsys.readouterr().err
    assert situs.permintaan == []


# --- MCP -------------------------------------------------------------------


@pytest.fixture
def server_mcp(monkeypatch):
    """Modul server MCP dengan klien bersama yang dikosongkan sebelum dan sesudah uji."""
    pytest.importorskip("mcp")
    from lppm_mcp import mcp_server

    monkeypatch.setattr(mcp_server, "klien_tersimpan", None)
    return mcp_server


def test_mcp_tool_tanpa_parameter_kredensial(server_mcp):
    alat = {satu.name: satu for satu in asyncio.run(server_mcp.server.list_tools())}

    assert set(alat) == {"cek_login", "daftar_menu", "ambil_halaman", "daftar_turnitin", "ajukan_turnitin"}
    for satu in alat.values():
        parameter = set(satu.input_schema.get("properties", {}))
        assert not parameter & {"username", "password"}
    assert alat["ambil_halaman"].input_schema["properties"]["bentuk"]["enum"] == ["teks", "tabel"]


def test_mcp_ajukan_turnitin_bawaannya_uji_coba(server_mcp):
    alat = {satu.name: satu for satu in asyncio.run(server_mcp.server.list_tools())}["ajukan_turnitin"]
    skema = alat.input_schema

    assert set(skema["required"]) == {"judul", "tautan"}
    assert skema["properties"]["uji_coba"]["default"] is True
    assert skema["properties"]["paksa"]["default"] is False


def test_mcp_instruksi_meminta_uji_coba_dan_persetujuan(server_mcp):
    instruksi = server_mcp.server.instructions

    assert "uji_coba=True lebih dulu" in instruksi
    assert "setelah pemakai menyetujuinya" in instruksi
    assert "2 per pemakai" in instruksi


def test_mcp_cek_login(server_mcp, situs, kredensial_di_setelan):
    assert server_mcp.cek_login() == {"ok": True, "beranda": f"{PORTAL}/home"}


def test_mcp_tanpa_kredensial_memberi_pesan_bukan_galat(server_mcp, situs):
    hasil = server_mcp.daftar_menu()

    assert hasil["ok"] is False
    assert "LPPM_USERNAME" in hasil["pesan"]


def test_mcp_daftar_menu_lalu_ambil_halaman_memakai_satu_sesi(server_mcp, situs, kredensial_di_setelan):
    menu = server_mcp.daftar_menu()
    path = next(satu["path"] for satu in menu["menu"] if satu["nama"] == "Daftar Penelitian")
    isi = server_mcp.ambil_halaman(path, bentuk="tabel")

    assert isi["ok"] is True
    assert isi["tabel"][0]["jumlah_baris"] == 2
    assert situs.jumlah("POST", "/login") == 1


def test_mcp_ambil_halaman_di_luar_portal_ditolak(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.ambil_halaman("https://siakad.pradita.ac.id/dashboard")

    assert hasil["ok"] is False
    assert "di luar portal" in hasil["pesan"]


def test_mcp_daftar_turnitin(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.daftar_turnitin()

    assert hasil["ok"] is True
    assert hasil["jatah"] == {
        "dipakai": 1,
        "total": 2,
        "sisa": 1,
        "teks": "Status Pengajuan Anda: 1 dari 2 jatah digunakan (Sisa 1x pengajuan)",
    }
    assert hasil["riwayat"][0]["judul"] == JUDUL_TURNITIN_UJI


def test_mcp_ajukan_turnitin_uji_coba_tidak_mengirim(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.ajukan_turnitin(JUDUL_BARU, TAUTAN_NASKAH_UJI)

    assert hasil["ok"] is True
    assert hasil["uji_coba"] is True and hasil["terkirim"] is False
    assert hasil["isian"] == {"judul_naskah": JUDUL_BARU, "file_artikel": TAUTAN_NASKAH_UJI}
    assert hasil["jatah"]["sisa"] == 1
    assert situs.jumlah("POST", "/turnitin") == 0


def test_mcp_ajukan_turnitin_kirim_sesudah_disetujui(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.ajukan_turnitin(JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)

    assert hasil["ok"] is True
    assert hasil["diterima"] is True
    assert hasil["baris_baru"]["judul"] == JUDUL_BARU
    assert situs.jumlah("POST", "/turnitin") == 1


def test_mcp_ajukan_turnitin_judul_kembar_memberi_pesan(server_mcp, situs, kredensial_di_setelan):
    hasil = server_mcp.ajukan_turnitin(JUDUL_TURNITIN_UJI, TAUTAN_NASKAH_UJI, uji_coba=False)

    assert hasil == {"ok": False, "terkirim": False, "pesan": hasil["pesan"]}
    assert "sudah ada di riwayat" in hasil["pesan"]
    assert situs.jumlah("POST", "/turnitin") == 0


def test_mcp_ajukan_turnitin_hasil_tidak_pasti_ditandai_terkirim(server_mcp, situs, kredensial_di_setelan):
    situs.turnitin_balasan = JawabanTiruan(f"{PORTAL}/turnitin", 419, teks="Page Expired")

    hasil = server_mcp.ajukan_turnitin(JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)

    assert hasil["ok"] is False and hasil["terkirim"] is True
    assert "daftar_turnitin" in hasil["pesan"]


# --- REST API --------------------------------------------------------------


@pytest.fixture
def api(monkeypatch):
    """TestClient REST API dengan simpanan sesi yang kosong."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx2")
    from fastapi.testclient import TestClient

    from lppm_mcp import api as modul_api

    monkeypatch.setattr(modul_api, "sesi_tersimpan", {})
    return TestClient(modul_api.app)


def test_api_sesi_dengan_kredensial_per_permintaan(api, situs):
    jawaban = api.post("/sesi", json={"username": USERNAME_UJI, "password": PASSWORD_UJI})

    assert jawaban.status_code == 200
    assert jawaban.json() == {"ok": True, "beranda": f"{PORTAL}/home"}


def test_api_kredensial_salah_dibalas_401(api, situs):
    jawaban = api.post("/sesi", json={"username": USERNAME_UJI, "password": "sandi-yang-salah"})

    assert jawaban.status_code == 401
    assert "sandi-yang-salah" not in jawaban.text


def test_api_kredensial_setengah_dibalas_422(api, situs):
    assert api.post("/sesi", json={"username": USERNAME_UJI}).status_code == 422


def test_api_halaman_memakai_kredensial_setelan(api, situs, kredensial_di_setelan):
    jawaban = api.post("/halaman", json={"path": "/penelitian", "bentuk": "tabel"})

    assert jawaban.status_code == 200
    assert jawaban.json()["tabel"][0]["kolom"][1] == "Judul"


def test_api_menu(api, situs, kredensial_di_setelan):
    jawaban = api.post("/menu", json={})

    assert jawaban.status_code == 200
    assert any(satu["path"] == "/pengabdian" for satu in jawaban.json()["data"])


def test_api_alamat_aksi_dibalas_422(api, situs, kredensial_di_setelan):
    jawaban = api.post("/halaman", json={"path": "/penelitian/101/hapus"})

    assert jawaban.status_code == 422
    assert "hanya membaca" in jawaban.json()["detail"]


def test_api_bentuk_asing_dibalas_422(api, situs, kredensial_di_setelan):
    assert api.post("/halaman", json={"path": "/penelitian", "bentuk": "pdf"}).status_code == 422


def test_api_get_turnitin_memakai_kredensial_setelan(api, situs, kredensial_di_setelan):
    jawaban = api.get("/turnitin")

    assert jawaban.status_code == 200
    assert jawaban.json()["jatah"]["sisa"] == 1
    assert jawaban.json()["riwayat"][0]["status"] == "Submit"


def test_api_get_turnitin_dengan_kredensial_di_header(api, situs):
    jawaban = api.get("/turnitin", headers={"X-LPPM-Username": USERNAME_UJI, "X-LPPM-Password": PASSWORD_UJI})

    assert jawaban.status_code == 200
    assert jawaban.json()["riwayat"][0]["judul"] == JUDUL_TURNITIN_UJI
    assert api.get("/turnitin", headers={"X-LPPM-Username": USERNAME_UJI}).status_code == 422


def test_api_post_turnitin_bawaannya_uji_coba(api, situs, kredensial_di_setelan):
    jawaban = api.post("/turnitin", json={"judul": JUDUL_BARU, "tautan": TAUTAN_NASKAH_UJI})

    assert jawaban.status_code == 200
    assert jawaban.json()["uji_coba"] is True
    assert jawaban.json()["terkirim"] is False
    assert TOKEN_UJI not in jawaban.text
    assert situs.jumlah("POST", "/turnitin") == 0


@pytest.mark.parametrize(
    "badan",
    [
        {"judul": JUDUL_BARU, "tautan": "https://contoh-lain.id/naskah"},  # bukan Google Drive
        {"judul": JUDUL_TURNITIN_UJI, "tautan": TAUTAN_NASKAH_UJI, "uji_coba": False},  # judul kembar
    ],
)
def test_api_post_turnitin_yang_ditolak_dibalas_422(api, situs, kredensial_di_setelan, badan):
    assert api.post("/turnitin", json=badan).status_code == 422
    assert situs.jumlah("POST", "/turnitin") == 0


def test_api_post_turnitin_kirim(api, situs, kredensial_di_setelan):
    jawaban = api.post("/turnitin", json={"judul": JUDUL_BARU, "tautan": TAUTAN_NASKAH_UJI, "uji_coba": False})

    assert jawaban.status_code == 200
    assert jawaban.json()["diterima"] is True
    assert jawaban.json()["jatah"]["sisa"] == 0
    assert situs.jumlah("POST", "/turnitin") == 1
