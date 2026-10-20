"""Perkakas bersama untuk unit test LPPM.

Seluruh test berjalan tanpa jaringan: portal LPPM digantikan SitusTiruan yang
menjawab seperti aplikasi Laravel, sehingga bisa dijalankan kapan saja tanpa
kredensial. Nama tokoh, judul penelitian, NIDN, dan kata sandi di seluruh berkas
uji sengaja dikarang.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from lppm_mcp import konfigurasi, lppm_client  # noqa: E402

PORTAL = "https://lppm.pradita.ac.id"
USERNAME_UJI = "0000000001"
PASSWORD_UJI = "sandi-karangan-123"
TOKEN_UJI = "token-karangan-csrf"
PESAN_GAGAL_LARAVEL = "These credentials do not match our records."


def halaman_login(token: str, galat: str = "") -> str:
    """Halaman login karangan dengan bentuk yang sama seperti portal LPPM asli."""
    blok_galat = (
        f'<span class="invalid-feedback" role="alert"><strong>{galat}</strong></span>' if galat else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><title>LPPM Contoh</title></head>
<body>
<header id="header"><nav id="navbar"><ul>
  <li class="dropdown"><a href="#"><span>About Us</span></a>
    <ul><li><a href="{PORTAL}/infolppm/profil">Profil</a></li></ul></li>
  <li class="dropdown"><a href="#"><span>Publikasi</span></a>
    <ul><li class="dropdown"><a href="#"><span>Jurnal</span></a>
      <ul><li><a href="{PORTAL}/jurnal/karangan">Jurnal Karangan</a></li></ul></li></ul></li>
</ul></nav>
<a class="btn-book-a-table" href="{PORTAL}/login" title="login"><i class="fas fa-sign-in-alt"></i></a>
</header>
<main id="main"><div class="card"><div class="card-header">Login</div><div class="card-body">
  <form method="POST" action="{PORTAL}/login">
    <input type="hidden" name="_token" value="{token}">
    <label for="login">NIDN atau Email Address</label>
    <input id="login" type="text" name="login" value="" required autofocus>
    {blok_galat}
    <label for="password">Password</label>
    <input id="password" type="password" name="password" required>
    <input class="form-check-input" type="checkbox" name="remember" id="remember">
    <button type="submit" class="btn btn-primary">Login</button>
  </form>
</div></div></main>
</body></html>"""


HALAMAN_BERANDA = f"""<html><head><title>Dashboard | LPPM Contoh</title>
<meta name="csrf-token" content="{TOKEN_UJI}"></head>
<body class="sidebar-mini"><div class="wrapper">
<nav class="main-header navbar">
  <ul class="navbar-nav"><li class="nav-item"><a class="nav-link" data-widget="pushmenu" href="#"><i class="fas fa-bars"></i></a></li></ul>
  <ul class="navbar-nav ml-auto">
    <li class="nav-item dropdown"><a class="nav-link dropdown-toggle" data-toggle="dropdown" href="#">King Kong</a>
      <div class="dropdown-menu">
        <a class="dropdown-item" href="/profil">Profil Saya</a>
        <a class="dropdown-item" href="/logout" onclick="event.preventDefault();">Logout</a>
        <form id="logout-form" action="/logout" method="POST"><input type="hidden" name="_token" value="{TOKEN_UJI}"></form>
      </div></li></ul>
</nav>
<aside class="main-sidebar">
  <a href="/home" class="brand-link"><span class="brand-text">LPPM Contoh</span></a>
  <div class="sidebar"><nav class="mt-2">
    <ul class="nav nav-pills nav-sidebar flex-column" data-widget="treeview">
      <li class="nav-item"><a href="/home" class="nav-link active"><i class="nav-icon fas fa-home"></i><p>Dashboard</p></a></li>
      <li class="nav-item has-treeview"><a href="#" class="nav-link"><p>Penelitian<i class="right fas fa-angle-left"></i></p></a>
        <ul class="nav nav-treeview">
          <li class="nav-item"><a href="/penelitian" class="nav-link"><p>Daftar Penelitian</p></a></li>
          <li class="nav-item"><a href="/penelitian/create" class="nav-link"><p>Usulan Baru</p></a></li>
        </ul></li>
      <li class="nav-item"><a href="/pengabdian" class="nav-link"><p>Pengabdian (PkM)</p></a></li>
      <li class="nav-item"><a href="/surat-tugas" class="nav-link"><p>Surat Tugas</p></a></li>
      <li class="nav-item"><a href="https://siakad.pradita.ac.id" class="nav-link"><p>SIAKAD</p></a></li>
    </ul></nav></div>
</aside>
<div class="content-wrapper">
  <div class="content-header"><h1>Dashboard</h1></div>
  <section class="content"><p>Selamat datang, King Kong.</p>
    <div class="small-box"><h3>2</h3><p>Penelitian aktif</p></div></section>
</div>
<footer class="main-footer">Hak cipta LPPM Contoh</footer>
</div>
<script>var rahasia = "jangan-tampil";</script>
</body></html>"""


def halaman_penelitian(nomor: int) -> str:
    """Daftar penelitian karangan berpaginasi dua halaman, seperti paginator Laravel."""
    if nomor == 1:
        baris = """
      <tr><td>1</td><td>Rancang Bangun Aplikasi Contoh</td><td>King Kong</td><td>2025</td><td>Disetujui</td>
          <td><a href="/penelitian/101" title="Detail"><i class="fa fa-eye"></i></a>
              <a href="/penelitian/101/hapus" onclick="return confirm('Hapus?')">Hapus</a></td></tr>
      <tr><td>2</td><td>Analisis Data Karangan</td><td>Spider Man</td><td>2026</td><td>Diajukan</td>
          <td><a href="/penelitian/102">Detail</a></td></tr>"""
        paginasi = f'<ul class="pagination"><li><a class="page-link" href="{PORTAL}/penelitian?page=2" rel="next">&raquo;</a></li></ul>'
    else:
        baris = """
      <tr><td>3</td><td>Studi Kasus Fiktif</td><td>King Kong</td><td>2026</td><td>Selesai</td>
          <td><a href="/penelitian/103">Detail</a></td></tr>"""
        paginasi = f'<ul class="pagination"><li><a class="page-link" href="{PORTAL}/penelitian?page=1" rel="prev">&laquo;</a></li></ul>'
    return f"""<html><head><title>Penelitian | LPPM Contoh</title></head><body>
<aside class="main-sidebar"><nav><ul class="nav"><li><a href="/home">Dashboard</a></li></ul></nav></aside>
<div class="content-wrapper">
  <div class="content-header"><h1>Daftar Penelitian</h1></div>
  <section class="content"><div class="card">
    <div class="card-header"><h3 class="card-title">Penelitian Saya</h3></div>
    <div class="card-body">
    <table class="table">
      <thead><tr><th>No</th><th>Judul</th><th>Ketua</th><th>Tahun</th><th>Status</th><th>Aksi</th></tr></thead>
      <tbody>{baris}
      </tbody>
    </table>
    {paginasi}
  </div></div></section>
</div></body></html>"""


HALAMAN_DETAIL = f"""<html><head><title>Detail | LPPM Contoh</title></head><body>
<nav class="main-header navbar"><a href="/home">Beranda</a></nav>
<div class="content-wrapper">
  <h1>Detail Penelitian</h1>
  <form>
    <input type="hidden" name="_token" value="{TOKEN_UJI}">
    <label>Judul</label> <input type="text" value="Rancang Bangun Aplikasi Contoh" disabled>
    <label>Skema</label>
    <select disabled><option value="1">Internal</option><option value="2" selected>Hibah Karangan</option></select>
    <label>Abstrak</label> <textarea disabled>Penelitian karangan untuk pengujian.</textarea>
    <input type="password" name="password">
  </form>
  <table><tr><th>Anggota</th><td>Spider Man</td></tr></table>
</div>
<script>console.log("jangan-tampil");</script>
</body></html>"""

HALAMAN_PROFIL = """<html><head><title>LPPM Contoh</title></head><body>
<main id="main"><h2>Profil LPPM Contoh</h2><p>Lembaga karangan untuk pengujian.</p></main>
</body></html>"""

JUDUL_TURNITIN_UJI = "Kerangka Kerja Fiktif untuk Kota Gotham"
TAUTAN_NASKAH_UJI = "https://drive.google.com/file/d/naskah-karangan-123/view?usp=sharing"
AKSI_PROSES_LPPM = '<span class="text-muted">Proses LPPM</span>'


def baris_riwayat_turnitin(judul: str, tanggal: str, no_surat: str = "-", status: str = "Submit",
                           aksi: str = AKSI_PROSES_LPPM, modal: str = "") -> dict:
    """Satu baris riwayat Turnitin karangan; `modal` ditaruh di tbody sesudah barisnya, seperti di portal."""
    return {"judul": judul, "tanggal": tanggal, "no_surat": no_surat, "status": status, "aksi": aksi, "modal": modal}


def halaman_turnitin(riwayat: list[dict], dipakai: int, total: int, flash: str = "",
                     token: str = TOKEN_UJI, paginasi: str = "") -> str:
    """Halaman /turnitin karangan dengan struktur yang sama seperti portal asli per Oktober 2026."""
    baris = "".join(
        f"""
          <tr>
            <td>{nomor}</td>
            <td>{satu['judul']}</td>
            <td>{satu['tanggal']}</td>
            <td>{satu['no_surat']}</td>
            <td> <span class="badge badge-info"> {satu['status']} </span> </td>
            <td> {satu['aksi']} </td>
          </tr>
          <!-- Modal Form Perbaikan (Bootstrap 4) -->{satu['modal']}"""
        for nomor, satu in enumerate(riwayat, start=1)
    )
    return f"""<!DOCTYPE html>
<html lang="id"><head><title>Turnitin | LPPM Contoh</title><meta name="csrf-token" content="{token}"></head>
<body>
<nav class="navbar"><a class="navbar-brand" href="{PORTAL}/home">LPPM Contoh</a>
  <a class="nav-link" href="{PORTAL}/turnitin">Turnitin</a></nav>
<main class="py-4">
<div class="container my-4">
  <h3 class="mb-3">Pengajuan Cek Turnitin</h3>
  <div class="alert alert-info"> <strong>Status Pengajuan Anda:</strong> {dipakai} dari {total} jatah digunakan (Sisa {max(total - dipakai, 0)}x pengajuan) </div>
  {flash}
  <div class="card mb-4">
    <div class="card-header">Form Pengajuan Baru</div>
    <div class="card-body">
      <form action="{PORTAL}/turnitin" method="POST">
        <input type="hidden" name="_token" value="{token}">
        <div class="mb-3">
          <label for="judul_naskah" class="form-label">Judul Naskah</label>
          <input type="text" name="judul_naskah" id="judul_naskah" class="form-control " value="" required="">
        </div>
        <div class="mb-3">
          <label for="file_artikel" class="form-label">Link Google Drive Naskah</label>
          <input type="url" name="file_artikel" id="file_artikel" class="form-control " value="" placeholder="https://drive.google.com/..." required="">
        </div>
        <button type="submit" class="btn btn-primary"> Submit Pengajuan </button>
      </form>
    </div>
  </div>
  <div class="card">
    <div class="card-header">Riwayat Pengajuan Cek Turnitin</div>
    <div class="card-body">
      <table class="table table-bordered table-striped">
        <thead>
          <tr> <th>No</th> <th>Judul Naskah</th> <th>Tanggal Submit</th> <th>No. Surat</th> <th>Status</th> <th>Aksi</th> </tr>
        </thead>
        <tbody>{baris}
        </tbody>
      </table>
      {paginasi}
    </div>
  </div>
</div>
</main>
</body></html>"""


class JawabanTiruan:
    """Pengganti requests.Response seperlunya saja."""

    def __init__(self, url, status_code=200, teks="", lokasi="", jenis="text/html; charset=UTF-8"):
        """Jawaban dengan alamat, status, isi, dan (kalau pengalihan) Location."""
        self.url = url
        self.status_code = status_code
        self.text = teks
        self.headers = {"Content-Type": jenis}
        if lokasi:
            self.headers["Location"] = lokasi

    @property
    def is_redirect(self) -> bool:
        """Sama dengan requests: ada Location dan statusnya kode pengalihan."""
        return "Location" in self.headers and self.status_code in (301, 302, 303, 307, 308)


class SitusTiruan:
    """Portal LPPM tiruan yang menjawab seperti aplikasi Laravel, tanpa jaringan.

    Dipasang menggantikan sesi HTTP klien. Setiap permintaan dicatat di
    `permintaan`, dan permintaan ke host lain langsung menggagalkan uji.
    """

    def __init__(self):
        """Portal dalam keadaan belum login, dengan kredensial dan token karangan."""
        self.verify = True
        self.headers = {}
        self.username_benar = USERNAME_UJI
        self.password_benar = PASSWORD_UJI
        self.token = TOKEN_UJI
        self.token_di_form = TOKEN_UJI
        self.pesan_gagal = PESAN_GAGAL_LARAVEL
        self.action_login = f"{PORTAL}/login"
        self.masuk = False
        self.galat_tertunda = ""
        self.permintaan: list[dict] = []
        # halaman /turnitin: satu dari dua jatah sudah terpakai, sama seperti akun pemakai
        self.turnitin_total = 2
        self.turnitin_riwayat = [baris_riwayat_turnitin(JUDUL_TURNITIN_UJI, "20/10/2026 15:15")]
        self.turnitin_dipakai: int | None = None  # None: sebanyak baris riwayat
        self.turnitin_flash = ""
        self.turnitin_galat_validasi = ""  # diisi: POST berikutnya ditolak validasi Laravel
        self.turnitin_tanggal_baru = "20/10/2026 16:05"
        self.turnitin_html: str | None = None  # pengganti halaman /turnitin utuh
        self.turnitin_lanjutan: dict[str, str] = {}  # nomor halaman paginasi -> HTML
        self.turnitin_balasan: JawabanTiruan | None = None  # pengganti jawaban POST /turnitin
        self.turnitin_sesi_habis = False  # True: sesi berakhir tepat saat POST /turnitin tiba

    def sebagai_pabrik(self) -> "SitusTiruan":
        """Pengganti buat_sesi_http(): selalu mengembalikan situs ini sendiri."""
        return self

    def jumlah(self, metode: str, path: str) -> int:
        """Berapa kali sebuah path diminta dengan metode tertentu."""
        return sum(1 for satu in self.permintaan if satu["metode"] == metode and satu["path"] == path)

    def request(self, method, url, data=None, headers=None, timeout=None, allow_redirects=True):
        """Jawab satu permintaan seperti portal LPPM."""
        bagian = urlsplit(url)
        assert bagian.netloc == "lppm.pradita.ac.id", f"permintaan keluar portal: {url}"
        assert allow_redirects is False, "pengalihan harus diikuti klien sendiri"
        self.permintaan.append({"metode": method, "path": bagian.path, "url": url, "data": dict(data or {})})

        if method == "POST" and bagian.path == "/login":
            return self.proses_login(url, data or {})
        if bagian.path == "/login":
            return self.tampilkan_login(url)
        if bagian.path == "/infolppm/profil":
            return JawabanTiruan(url, teks=HALAMAN_PROFIL)
        if not self.masuk:
            return JawabanTiruan(url, 302, lokasi=f"{PORTAL}/login")
        if method == "POST":
            return self.terima_kiriman(url, bagian, data or {})
        return self.halaman_anggota(url, bagian)

    def tampilkan_login(self, url):
        """GET /login: tamu melihat form; yang sudah login dialihkan ke beranda."""
        if self.masuk:
            return JawabanTiruan(url, 302, lokasi=f"{PORTAL}/home")
        galat, self.galat_tertunda = self.galat_tertunda, ""
        html = halaman_login(self.token_di_form, galat).replace(f'action="{PORTAL}/login"', f'action="{self.action_login}"')
        return JawabanTiruan(url, teks=html)

    def proses_login(self, url, data: dict):
        """POST /login: token salah dibalas 419, kredensial salah dikembalikan ke /login."""
        if data.get("_token") != self.token:
            return JawabanTiruan(url, 419, teks="Page Expired")
        if data.get("login") == self.username_benar and data.get("password") == self.password_benar:
            self.masuk = True
            return JawabanTiruan(url, 302, lokasi=f"{PORTAL}/home")
        self.galat_tertunda = self.pesan_gagal
        return JawabanTiruan(url, 302, lokasi=f"{PORTAL}/login")

    def halaman_anggota(self, url, bagian):
        """Halaman yang hanya terbuka setelah login."""
        if bagian.path == "/home":
            return JawabanTiruan(url, teks=HALAMAN_BERANDA)
        if bagian.path == "/penelitian":
            nomor = int(parse_qs(bagian.query).get("page", ["1"])[0])
            return JawabanTiruan(url, teks=halaman_penelitian(nomor))
        if bagian.path == "/penelitian/101":
            return JawabanTiruan(url, teks=HALAMAN_DETAIL)
        if bagian.path == "/pindah":
            return JawabanTiruan(url, 302, lokasi="/penelitian/101")
        if bagian.path == "/tautan-siakad":
            return JawabanTiruan(url, 302, lokasi="https://siakad.pradita.ac.id/dashboard")
        if bagian.path == "/dokumen/surat-tugas.pdf":
            return JawabanTiruan(url, teks="%PDF-1.4 karangan", jenis="application/pdf")
        if bagian.path == "/turnitin":
            return self.tampilkan_turnitin(url, bagian)
        return JawabanTiruan(url, 404, teks="Not Found")

    def tampilkan_turnitin(self, url, bagian):
        """GET /turnitin: jatah, form, dan riwayat. Pesan flash tampil sekali, seperti session flash Laravel."""
        nomor = parse_qs(bagian.query).get("page", ["1"])[0]
        if nomor != "1":
            return JawabanTiruan(url, teks=self.turnitin_lanjutan[nomor])
        flash, self.turnitin_flash = self.turnitin_flash, ""
        if self.turnitin_html is not None:
            return JawabanTiruan(url, teks=self.turnitin_html)
        dipakai = len(self.turnitin_riwayat) if self.turnitin_dipakai is None else self.turnitin_dipakai
        paginasi = (
            f'<ul class="pagination"><li><a class="page-link" href="{PORTAL}/turnitin?page=2" rel="next">&raquo;</a></li></ul>'
            if "2" in self.turnitin_lanjutan
            else ""
        )
        html = halaman_turnitin(self.turnitin_riwayat, dipakai, self.turnitin_total, flash, self.token, paginasi)
        return JawabanTiruan(url, teks=html)

    def terima_kiriman(self, url, bagian, data: dict):
        """POST setelah login. Hanya /turnitin yang dikenal; token salah dibalas 419 seperti Laravel."""
        if bagian.path != "/turnitin":
            return JawabanTiruan(url, 405, teks="Method Not Allowed")
        if data.get("_token") != self.token:
            return JawabanTiruan(url, 419, teks="Page Expired")
        if self.turnitin_balasan is not None:
            return self.turnitin_balasan
        if self.turnitin_sesi_habis:
            self.masuk = False
            return JawabanTiruan(url, 302, lokasi=f"{PORTAL}/login")
        if self.turnitin_galat_validasi:
            self.turnitin_flash = f'<div class="alert alert-danger">{self.turnitin_galat_validasi}</div>'
        elif len(self.turnitin_riwayat) >= self.turnitin_total:
            self.turnitin_flash = '<div class="alert alert-danger">Jatah pengajuan Anda sudah habis.</div>'
        else:
            self.turnitin_riwayat.append(baris_riwayat_turnitin(data["judul_naskah"], self.turnitin_tanggal_baru))
            self.turnitin_flash = '<div class="alert alert-success">Pengajuan Cek Turnitin berhasil dikirim.</div>'
        return JawabanTiruan(url, 302, lokasi=f"{PORTAL}/turnitin")


def tolak_jaringan(*argumen, **opsi):
    """Pengganti requests.Session.request selama uji: jaringan sungguhan tidak boleh tersentuh."""
    raise AssertionError("uji mencoba menghubungi jaringan sungguhan; pakai fixture `situs`")


@pytest.fixture(autouse=True)
def setelan_terpisah(tmp_path, monkeypatch):
    """Setelan, .env, dan lppm.yaml mesin pengembang tidak boleh ikut menentukan hasil uji.

    Kredensial asli di .env proyek tidak terbaca karena akar proyek dipindah ke
    direktori sementara, dan sesi HTTP sungguhan diblokir sama sekali.
    """
    monkeypatch.setattr(requests.Session, "request", tolak_jaringan)
    for kunci in list(os.environ):
        if kunci.startswith("LPPM_"):
            monkeypatch.delenv(kunci)
    konfigurasi.atur_akar_proyek(tmp_path)
    konfigurasi.atur_setelan()
    yield
    konfigurasi.atur_akar_proyek(None)
    konfigurasi.atur_setelan()


@pytest.fixture
def situs(monkeypatch) -> SitusTiruan:
    """Portal tiruan yang dipakai setiap KlienLppm yang dibuat selama uji."""
    tiruan = SitusTiruan()
    monkeypatch.setattr(lppm_client, "buat_sesi_http", tiruan.sebagai_pabrik)
    return tiruan


@pytest.fixture
def kredensial_di_setelan():
    """Kredensial karangan, diberikan lewat atur_setelan seperti dari .env."""
    konfigurasi.atur_setelan(LPPM_USERNAME=USERNAME_UJI, LPPM_PASSWORD=PASSWORD_UJI)
