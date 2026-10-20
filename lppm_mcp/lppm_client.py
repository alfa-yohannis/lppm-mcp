"""Klien portal LPPM Pradita: login, ambil halaman, dan menu navigasi.

Portal LPPM (https://lppm.pradita.ac.id) adalah aplikasi Laravel dengan login
bawaan Laravel UI. Per Oktober 2026 halaman loginnya seperti ini:

    GET  /login   form POST ke /login berisi _token (CSRF), login (NIDN atau
                  email), password, dan kotak centang remember
    POST /login   sukses dialihkan ke beranda; gagal dialihkan kembali ke /login
                  dengan pesan galat di bawah isiannya
    cookie        lppm_pradita_university_session dan XSRF-TOKEN, berumur dua
                  jam, berlaku untuk seluruh .pradita.ac.id

Nama isian, token, dan action tidak ditanam di kode. Semuanya dibaca dari form
setiap kali login, jadi perubahan kecil di halaman login tidak mematahkan apa pun.

Login baru dijalankan saat halaman pertama diminta, lalu diulang sekali secara
otomatis kalau sesinya ternyata sudah habis (dialihkan ke /login, HTTP 401 atau
419). Kredensial dibaca dari setelan saat itu juga dan tidak pernah dicetak.

Setiap permintaan dibatasi ke host portal LPPM, termasuk pengalihannya. Cookie
sesinya berlaku untuk seluruh .pradita.ac.id, jadi pengalihan ke host lain tidak
diikuti. GET hanya membaca: alamat yang tampak seperti aksi (logout, hapus,
setujui, dan sejenisnya) ditolak sebelum dikirim. Selain login, paket ini
menulis ke portal hanya lewat `kirim_form()`, yang hanya mau mengirim POST ke
path di PATH_POST_DIIZINKAN dan tidak pernah mengulang kirimannya.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from lppm_mcp.halaman import Halaman
from lppm_mcp.konfigurasi import (
    KonfigurasiError,
    baca_angka,
    baca_kredensial,
    baca_pengaturan,
    buat_sesi_http,
)

# alamat bawaan; portal lain diatur lewat LPPM_WEBSITE/LPPM_BASE_URL di .env atau
# website:/base_url: di lppm.yaml, tanpa menyentuh kode
LPPM_BASE_URL_BAWAAN = "https://lppm.pradita.ac.id"
PATH_LOGIN_BAWAAN = "/login"

BATAS_LOGIN_BAWAAN_DETIK = 60
BATAS_HALAMAN_BAWAAN_DETIK = 120
MAKS_PENGALIHAN_BAWAAN = 10

# Nama isian username yang dikenal, dipakai kalau form login punya lebih dari
# satu isian teks. Portal LPPM sendiri memakai "login".
NAMA_FIELD_USERNAME = ("login", "email", "username", "nidn")
JENIS_TANPA_NILAI = {"submit", "button", "reset", "image", "file"}

# Kata pada path atau query yang menandai aksi yang mengubah data. Aplikasi
# Laravel kadang memasang aksi seperti hapus pada tautan GET biasa, dan tautan
# itu bisa terbawa dari tombol di baris tabel. Alat yang hanya membaca tidak
# boleh membukanya.
KATA_AKSI = frozenset({
    "logout", "keluar", "signout",
    "delete", "destroy", "hapus", "remove",
    "approve", "reject", "setujui", "tolak", "terima",
    "verifikasi", "validasi",
    "batal", "batalkan", "cancel",
    "submit", "kirim", "ajukan",
    "reset",
})

# Path yang boleh menerima POST lewat kirim_form(), selain login. Setiap path di
# sini punya alat penulis dengan uji coba di modulnya sendiri; menambah path
# berarti menambah alat seperti itu juga.
PATH_POST_DIIZINKAN = frozenset({"/turnitin"})


class LppmError(RuntimeError):
    """Kegagalan yang berasal dari portal LPPM (halaman berubah, HTTP galat, dan sejenisnya)."""


class LoginDitolak(LppmError):
    """Portal menolak kredensialnya, atau sesi tidak bisa dipulihkan dengan login ulang."""


class AlamatDitolak(LppmError):
    """Alamat di luar portal LPPM, atau tampak seperti aksi yang mengubah data."""


@dataclass
class FormLogin:
    """Form login yang dibaca dari halaman login. Tidak pernah memuat kredensial."""

    action: str
    method: str
    field_username: str
    field_password: str
    isian_bawaan: dict[str, str] = field(default_factory=dict)


def batas_login() -> int:
    """Batas waktu GET dan POST login, dalam detik."""
    return baca_angka("LPPM_BATAS_LOGIN_DETIK", BATAS_LOGIN_BAWAAN_DETIK)


def batas_halaman() -> int:
    """Batas waktu GET halaman biasa, dalam detik."""
    return baca_angka("LPPM_BATAS_HALAMAN_DETIK", BATAS_HALAMAN_BAWAAN_DETIK)


def maks_pengalihan() -> int:
    """Banyaknya pengalihan (redirect) yang diikuti per permintaan."""
    return baca_angka("LPPM_MAKS_PENGALIHAN", MAKS_PENGALIHAN_BAWAAN)


def asal_url(url: str) -> str:
    """'https://lppm.pradita.ac.id/login' -> 'https://lppm.pradita.ac.id'; "" kalau bukan URL penuh."""
    bagian = urlsplit(url or "")
    return f"{bagian.scheme}://{bagian.netloc}" if bagian.scheme and bagian.netloc else ""


def periksa_alamat_dasar(alamat_dasar: str, alamat_login: str) -> None:
    """Tolak alamat portal yang bukan https, dan halaman login yang berada di host lain."""
    dasar, login = urlsplit(alamat_dasar), urlsplit(alamat_login)
    if dasar.scheme != "https" or not dasar.netloc:
        raise KonfigurasiError(f"Alamat portal LPPM harus https://..., bukan {alamat_dasar!r}")
    if login.scheme != "https" or login.netloc.lower() != dasar.netloc.lower():
        raise KonfigurasiError(
            f"Halaman login {alamat_login!r} harus https dan berada di {dasar.netloc}; "
            "periksa LPPM_WEBSITE dan LPPM_BASE_URL"
        )


def tentukan_alamat(base_url: str = "", url_login: str = "") -> tuple[str, str]:
    """Alamat portal dan halaman loginnya: dari argumen, lalu setelan, lalu bawaan.

    LPPM_WEBSITE (alamat halaman login, seperti di .env.contoh) cukup untuk
    menentukan keduanya; LPPM_BASE_URL dipakai kalau portalnya perlu disebut
    terpisah. Keduanya harus https dan berada di host yang sama, karena ke
    sanalah kata sandi dikirim.
    """
    if base_url:
        alamat_dasar = base_url.rstrip("/")
        alamat_login = url_login or alamat_dasar + PATH_LOGIN_BAWAAN
    else:
        alamat_login = url_login or baca_pengaturan("LPPM_WEBSITE")
        alamat_dasar = (
            baca_pengaturan("LPPM_BASE_URL") or asal_url(alamat_login) or LPPM_BASE_URL_BAWAAN
        ).rstrip("/")
        alamat_login = alamat_login or alamat_dasar + PATH_LOGIN_BAWAAN
    periksa_alamat_dasar(alamat_dasar, alamat_login)
    return alamat_dasar, alamat_login


def cari_form_login(sup: BeautifulSoup):
    """Form pertama yang memuat isian password, atau None."""
    for form in sup.find_all("form"):
        if form.find("input", {"type": "password"}) is not None:
            return form
    return None


def tebak_field_username(form, nama_password: str) -> str:
    """Nama isian username: satu-satunya isian teks di form, atau yang namanya dikenal."""
    calon = [
        masukan["name"]
        for masukan in form.find_all("input")
        if masukan.get("name")
        and masukan["name"] != nama_password
        and (masukan.get("type") or "text").lower() in ("text", "email", "tel", "number")
    ]
    if len(calon) == 1:
        return calon[0]
    for nama in NAMA_FIELD_USERNAME:
        if nama in calon:
            return nama
    return ""


def token_meta(sup: BeautifulSoup) -> str:
    """Token CSRF dari <meta name="csrf-token">, kalau halaman memasangnya."""
    meta = sup.find("meta", {"name": "csrf-token"})
    return (meta.get("content") or "") if meta is not None else ""


def baca_form_login(html: str, url_halaman: str, field_username: str = "") -> FormLogin:
    """Baca form login: action, method, nama isian username/password, dan isian bawaannya.

    Form yang dipilih adalah yang memuat isian password. Isian bawaan mencakup
    token CSRF `_token` dan input tersembunyi lain. Kotak centang yang tidak
    dicentang (mis. remember) tidak ikut, sama seperti di browser.
    """
    sup = BeautifulSoup(html or "", "lxml")
    form = cari_form_login(sup)
    if form is None:
        raise LppmError(f"Form login tidak ditemukan di {url_halaman}")
    nama_password = form.find("input", {"type": "password"}).get("name") or ""
    if not nama_password:
        raise LppmError("Isian password pada form login tidak bernama")
    nama_username = field_username or tebak_field_username(form, nama_password)
    if not nama_username:
        raise LppmError("Isian username tidak ditemukan pada form login; setel LPPM_FIELD_USERNAME")

    isian = {}
    for masukan in form.find_all("input"):
        nama = masukan.get("name")
        jenis = (masukan.get("type") or "text").lower()
        if not nama or nama in (nama_username, nama_password) or jenis in JENIS_TANPA_NILAI:
            continue
        if jenis in ("checkbox", "radio"):
            if masukan.has_attr("checked"):
                isian[nama] = masukan.get("value", "on")
            continue
        isian[nama] = masukan.get("value", "")
    if not isian.get("_token"):
        isian["_token"] = token_meta(sup)
    if not isian["_token"]:
        raise LppmError(f"Token CSRF tidak ditemukan di {url_halaman}")

    return FormLogin(
        action=urljoin(url_halaman, form.get("action") or url_halaman),
        method=(form.get("method") or "GET").upper(),
        field_username=nama_username,
        field_password=nama_password,
        isian_bawaan=isian,
    )


def pesan_galat(html: str) -> list[str]:
    """Pesan galat Laravel yang dirender di halaman (.invalid-feedback, .alert-danger)."""
    sup = BeautifulSoup(html or "", "lxml")
    hasil = []
    for blok in sup.select(".invalid-feedback, .alert-danger, .alert-warning, .text-danger, .help-block"):
        teks = " ".join(blok.get_text(" ").split())[:200]
        if teks and teks not in hasil:
            hasil.append(teks)
    return hasil


def samarkan(teks: str, *rahasia: str) -> str:
    """Ganti setiap kemunculan nilai rahasia dengan ***, untuk pesan yang ditampilkan."""
    for nilai in rahasia:
        if nilai:
            teks = teks.replace(nilai, "***")
    return teks


def kata_aksi(alamat: str) -> str:
    """Kata aksi pada path atau query sebuah alamat, mis. "hapus"; "" kalau tidak ada."""
    bagian = urlsplit(alamat)
    for kata in re.split(r"[^a-z0-9]+", f"{bagian.path}?{bagian.query}".lower()):
        if kata in KATA_AKSI:
            return kata
    return ""


def adalah_jenis_teks(jenis: str) -> bool:
    """Content-Type yang bisa dibaca sebagai halaman: HTML, teks, JSON, atau XML."""
    jenis = (jenis or "").lower()
    return jenis.startswith("text/") or any(kata in jenis for kata in ("html", "json", "xml"))


class KlienLppm:
    """Sesi portal LPPM milik satu dosen.

    Kredensial boleh diberikan langsung. Kalau dikosongkan, dibaca dari setelan
    (atur_setelan, environment, atau .env) saat login pertama. Membuat objek
    ini belum menghubungi portal sama sekali.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        base_url: str = "",
        url_login: str = "",
    ):
        """Siapkan sesi tanpa login. Alamat yang bukan https atau beda host ditolak di sini."""
        self._username = username or ""
        self._password = password or ""
        self.base_url, self.url_login = tentukan_alamat(base_url, url_login)
        self.sesi_http = buat_sesi_http()
        self.url_beranda = ""
        self.sudah_login = False
        self.jumlah_login = 0
        # login ulang dan permintaan halaman tidak boleh bersilangan antar-thread
        self._kunci = threading.RLock()

    def __repr__(self) -> str:
        """Ringkasan tanpa kredensial, aman muncul di log atau traceback."""
        return f"KlienLppm(base_url={self.base_url!r}, sudah_login={self.sudah_login})"

    def kredensial(self) -> tuple[str, str]:
        """Username dan password: dari argumen, yang kosong diambil dari setelan."""
        wajib = [
            kunci
            for kunci, nilai in (("LPPM_USERNAME", self._username), ("LPPM_PASSWORD", self._password))
            if not nilai
        ]
        dari_setelan = baca_kredensial(*wajib) if wajib else {}
        return (
            self._username or dari_setelan["LPPM_USERNAME"],
            self._password or dari_setelan["LPPM_PASSWORD"],
        )

    def alamat_lengkap(self, path_atau_url: str) -> str:
        """URL penuh di bawah portal. Alamat di host lain atau tanpa https ditolak."""
        alamat = urljoin(self.base_url + "/", (path_atau_url or "").strip())
        bagian, dasar = urlsplit(alamat), urlsplit(self.base_url)
        if bagian.scheme != dasar.scheme or bagian.netloc.lower() != dasar.netloc.lower():
            raise AlamatDitolak(
                f"{path_atau_url!r} berada di luar portal LPPM ({self.base_url}); "
                "hanya halaman di bawahnya yang boleh diambil"
            )
        return alamat

    def minta(
        self,
        metode: str,
        path_atau_url: str,
        *,
        data: dict | None = None,
        headers: dict | None = None,
        batas: int | None = None,
    ):
        """Kirim satu permintaan dan ikuti pengalihannya selama masih di dalam portal.

        Pengalihan diikuti sendiri, tidak oleh requests, supaya cookie sesi yang
        berlaku untuk seluruh .pradita.ac.id tidak pernah terkirim ke host lain.
        Sama seperti browser, pengalihan 301/302/303 dilanjutkan sebagai GET
        tanpa badan.
        """
        alamat = self.alamat_lengkap(path_atau_url)
        batas = batas or batas_halaman()
        for _ in range(maks_pengalihan() + 1):
            jawaban = self.minta_sekali(metode, alamat, data=data, headers=headers, batas=batas)
            if not jawaban.is_redirect:
                return jawaban

            tujuan = urljoin(alamat, jawaban.headers.get("Location", ""))
            try:
                alamat = self.alamat_lengkap(tujuan)
            except AlamatDitolak as galat:
                raise AlamatDitolak(
                    f"{path_atau_url} dialihkan ke luar portal LPPM ({tujuan}); pengalihan itu tidak diikuti"
                ) from galat
            if jawaban.status_code in (301, 302, 303):
                metode, data = "GET", None
        raise LppmError(f"Terlalu banyak pengalihan dari {path_atau_url}")

    def minta_sekali(
        self,
        metode: str,
        path_atau_url: str,
        *,
        data: dict | None = None,
        headers: dict | None = None,
        batas: int | None = None,
    ):
        """Kirim tepat satu permintaan ke dalam portal tanpa mengikuti pengalihannya."""
        alamat = self.alamat_lengkap(path_atau_url)
        try:
            return self.sesi_http.request(
                metode, alamat, data=data, headers=headers, timeout=batas or batas_halaman(), allow_redirects=False
            )
        except requests.RequestException as galat:
            raise LppmError(f"Permintaan ke {alamat} gagal: {galat}") from galat

    def di_halaman_login(self, jawaban) -> bool:
        """Apakah jawaban ini berakhir di halaman login."""
        return urlsplit(jawaban.url).path.rstrip("/") == urlsplit(self.url_login).path.rstrip("/")

    def sesi_habis(self, jawaban) -> bool:
        """Tanda sesi sudah tidak berlaku: dialihkan ke halaman login, atau HTTP 401/419."""
        return jawaban.status_code in (401, 419) or self.di_halaman_login(jawaban)

    def tandai_masuk(self, url_beranda: str) -> None:
        """Catat bahwa sesi sudah login, beserta alamat beranda tempat portal mendarat."""
        self.url_beranda = url_beranda
        self.sudah_login = True
        self.jumlah_login += 1

    def login(self) -> "KlienLppm":
        """Login ke portal; error kalau form login berubah atau kredensialnya ditolak."""
        with self._kunci:
            username, password = self.kredensial()
            halaman_login = self.minta("GET", self.url_login, batas=batas_login())
            if halaman_login.status_code >= 400:
                raise LppmError(f"Halaman login membalas HTTP {halaman_login.status_code}")
            if not self.di_halaman_login(halaman_login):
                # Laravel mengalihkan tamu yang sesinya masih hidup langsung ke
                # beranda. Form ber-password di beranda (mis. ganti sandi) sengaja
                # tidak disentuh: kredensial hanya dikirim dari halaman login.
                self.tandai_masuk(halaman_login.url)
                return self

            form = baca_form_login(
                halaman_login.text, halaman_login.url, baca_pengaturan("LPPM_FIELD_USERNAME")
            )
            if form.method != "POST":
                raise LppmError("Form login tidak memakai POST, jadi kredensial tidak dikirim")
            # action di luar portal ditolak di sini, sebelum kredensial ikut terkirim
            self.alamat_lengkap(form.action)

            isian = dict(form.isian_bawaan)
            isian[form.field_username] = username
            isian[form.field_password] = password
            jawaban = self.minta(
                "POST", form.action, data=isian, headers={"Referer": halaman_login.url}, batas=batas_login()
            )
            self.periksa_hasil_login(jawaban, username, password)
            self.tandai_masuk(jawaban.url)
            return self

    def periksa_hasil_login(self, jawaban, username: str, password: str) -> None:
        """Pastikan POST login berhasil. Pesan dari portal disamarkan dari kredensialnya."""
        if jawaban.status_code == 419:
            raise LppmError("Token CSRF ditolak portal (HTTP 419); coba login lagi")
        if jawaban.status_code == 429:
            raise LoginDitolak("Terlalu banyak percobaan login (HTTP 429); tunggu sebentar lalu coba lagi")
        if jawaban.status_code >= 400:
            raise LppmError(f"Login gagal: portal membalas HTTP {jawaban.status_code}")
        if self.di_halaman_login(jawaban):
            pesan = samarkan("; ".join(pesan_galat(jawaban.text)), username, password)
            raise LoginDitolak(
                "Login LPPM ditolak; periksa LPPM_USERNAME dan LPPM_PASSWORD"
                + (f". Pesan portal: {pesan}" if pesan else "")
            )

    def ambil(self, path_atau_url: str):
        """GET satu alamat di portal setelah login. Sesi yang habis dipulihkan sekali.

        Hanya membaca: alamat di luar portal dan alamat yang tampak seperti aksi
        (logout, hapus, dan sejenisnya) ditolak sebelum login maupun dikirim.
        """
        alamat = self.alamat_lengkap(path_atau_url)
        aksi = kata_aksi(alamat)
        if aksi:
            raise AlamatDitolak(
                f"{path_atau_url} tampak seperti aksi yang mengubah data ({aksi!r}); klien ini hanya membaca"
            )
        with self._kunci:
            if not self.sudah_login:
                self.login()
            jawaban = self.minta("GET", alamat)
            if self.sesi_habis(jawaban):
                self.sudah_login = False
                self.login()
                jawaban = self.minta("GET", alamat)
                if self.sesi_habis(jawaban):
                    raise LoginDitolak("Sesi LPPM habis dan login ulang tidak memulihkannya")
        if jawaban.status_code >= 400:
            raise LppmError(f"{alamat} membalas HTTP {jawaban.status_code}")
        return jawaban

    def ambil_halaman(self, path_atau_url: str) -> Halaman:
        """Satu halaman portal sebagai Halaman (alamat akhir dan HTML-nya). Berkas biner ditolak."""
        jawaban = self.ambil(path_atau_url)
        jenis = jawaban.headers.get("Content-Type", "text/html")
        if not adalah_jenis_teks(jenis):
            raise LppmError(f"{jawaban.url} berisi {jenis}, bukan halaman; mengunduh berkas belum didukung")
        return Halaman(url=jawaban.url, html=jawaban.text, status=jawaban.status_code, jenis=jenis)

    def daftar_navigasi(self) -> list[dict]:
        """Menu navigasi yang tersedia setelah login, dibaca dari beranda."""
        with self._kunci:
            if not self.sudah_login:
                self.login()
            beranda = self.url_beranda or "/"
        return self.ambil_halaman(beranda).menu(self.base_url)

    def alamat_kiriman(self, path_atau_url: str) -> str:
        """URL penuh tujuan POST. Hanya path di PATH_POST_DIIZINKAN, tanpa query, yang diterima."""
        alamat = self.alamat_lengkap(path_atau_url)
        bagian = urlsplit(alamat)
        if bagian.path not in PATH_POST_DIIZINKAN or bagian.query or bagian.fragment:
            raise AlamatDitolak(
                f"{path_atau_url} bukan tujuan kiriman yang diizinkan; klien ini hanya mengirim form ke "
                + ", ".join(sorted(PATH_POST_DIIZINKAN))
            )
        return alamat

    def kirim_form(self, path_atau_url: str, isian: dict, *, referer: str = ""):
        """POST satu form ke path yang diizinkan, tepat sekali, lalu ikuti pengalihannya sebagai GET.

        Klien harus sudah login, karena token CSRF di `isian` diambil dari
        halaman form pada sesi yang sama. Kiriman tidak pernah diulang, juga
        saat sesinya ternyata habis: pengulangan bisa membuat portal mencatatnya
        dua kali. Jawaban yang dikembalikan berasal dari halaman tempat portal
        mendarat setelah pengalihan.
        """
        alamat = self.alamat_kiriman(path_atau_url)
        with self._kunci:
            if not self.sudah_login:
                raise LppmError("Belum login; buka halaman form-nya dulu supaya token CSRF-nya berasal dari sesi ini")
            jawaban = self.minta_sekali("POST", alamat, data=isian, headers={"Referer": referer or alamat})
            if jawaban.is_redirect:
                jawaban = self.lanjutkan_sesudah_kiriman(alamat, jawaban)
            if self.sesi_habis(jawaban):
                self.sudah_login = False
                raise LoginDitolak(
                    f"Portal menolak kiriman ke {alamat} karena sesi atau token CSRF-nya tidak berlaku lagi; "
                    "kiriman tidak diulang"
                )
        if jawaban.status_code >= 400:
            raise LppmError(f"Kiriman ke {alamat} dibalas HTTP {jawaban.status_code}")
        return jawaban

    def lanjutkan_sesudah_kiriman(self, alamat: str, jawaban):
        """Ikuti pengalihan sesudah POST sebagai GET, seperti browser, selama masih di dalam portal.

        Pengalihan 307/308 meminta POST yang sama diulang ke alamat lain, yang
        belum tentu ada di PATH_POST_DIIZINKAN, jadi tidak diikuti.
        """
        tujuan = urljoin(alamat, jawaban.headers.get("Location", ""))
        if jawaban.status_code not in (301, 302, 303):
            raise LppmError(
                f"Portal meminta kiriman diulang ke {tujuan} (HTTP {jawaban.status_code}); permintaan itu tidak diikuti"
            )
        try:
            return self.minta("GET", tujuan)
        except AlamatDitolak as galat:
            raise LppmError(
                f"Kiriman ke {alamat} dialihkan ke luar portal LPPM ({tujuan}); pengalihan itu tidak diikuti"
            ) from galat
