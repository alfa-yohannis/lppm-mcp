"""Membaca isi halaman portal LPPM: judul, teks, tabel, tautan, dan menu navigasi.

Semua fungsi di sini bekerja pada HTML yang sudah diambil dan tidak menyentuh
jaringan, jadi bisa diuji dengan halaman karangan.

Isi halaman dicari di wadah yang lazim dipakai templat Laravel: <main> (templat
publik LPPM), .content-wrapper (AdminLTE), lalu #content atau .content. Kalau
tidak ada satu pun, seluruh <body> dipakai setelah kerangkanya (header, nav,
sidebar, footer) dibuang.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

BENTUK_HALAMAN = ("teks", "tabel")

PEMILIH_ISI = ("main", "[role=main]", ".content-wrapper", "#content", ".content")
PEMILIH_KERANGKA = (
    "header, footer, nav, aside, [role=navigation], .navbar, .sidebar, "
    ".main-header, .main-sidebar, .main-footer, #preloader"
)
PEMILIH_NAVIGASI = "nav, aside, [role=navigation], .navbar, .sidebar, .main-sidebar, .nav-sidebar"

TAG_TANPA_TEKS = ["script", "style", "noscript", "template", "svg", "iframe", "head"]
TAG_BLOK = [
    "address", "article", "blockquote", "dd", "div", "dl", "dt", "fieldset",
    "figcaption", "figure", "form", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
    "label", "legend", "li", "ol", "p", "pre", "section", "table", "ul",
]
TAG_JUDUL = ("h1", "h2", "h3", "h4", "h5", "h6")
TAG_KEPALA_GRUP = ("button", "span", "p", "strong", *TAG_JUDUL)

# isian yang nilainya terlihat di layar; hidden, password, dan tombol tidak
JENIS_MASUKAN_TERLIHAT = {"", "text", "email", "number", "date", "datetime-local", "month", "tel", "url", "time"}
SKEMA_BUKAN_TUJUAN = ("javascript:", "mailto:", "tel:", "data:")
TEKS_LOGOUT = {"logout", "log out", "keluar", "sign out"}
# tautan logo menuju beranda yang sama dengan menu Dashboard, tapi bernama aplikasi
KELAS_LOGO = {"brand-link", "navbar-brand", "logo"}

CATATAN_TABEL_KOSONG = (
    "Tidak ada baris tabel di HTML halaman ini. Kalau halamannya memakai DataTables, "
    "isinya dimuat lewat AJAX; jalankan `./lppm petakan <path>` untuk menemukan endpoint-nya."
)


@dataclass
class Halaman:
    """Satu halaman portal yang sudah diambil: alamat akhirnya beserta HTML-nya."""

    url: str
    html: str = field(repr=False)
    status: int = 200
    jenis: str = "text/html"

    def judul(self) -> str:
        """Judul halaman: heading pertama di bagian isi, atau <title>."""
        return judul_halaman(self.html)

    def teks(self) -> str:
        """Isi halaman sebagai teks yang enak dibaca."""
        return teks_halaman(self.html)

    def tabel(self) -> list[dict]:
        """Seluruh tabel di halaman ini."""
        return tabel_halaman(self.html, self.url)

    def menu(self, base_url: str) -> list[dict]:
        """Tautan navigasi yang menuju portal di `base_url`."""
        return menu_navigasi(self.html, self.url, base_url)


def rapikan(teks: str) -> str:
    """Satukan spasi, tab, dan baris baru yang berlebih menjadi satu spasi."""
    return " ".join((teks or "").split())


def buang_semua(elemen_semua) -> None:
    """Hapus elemen dari pohon HTML; yang sudah ikut terhapus bersama induknya dilewati."""
    for elemen in elemen_semua:
        if not elemen.decomposed:
            elemen.decompose()


def pilih_isi(sup: BeautifulSoup) -> Tag | None:
    """Wadah isi halaman menurut PEMILIH_ISI, atau None kalau tidak ada."""
    for pemilih in PEMILIH_ISI:
        wadah = sup.select_one(pemilih)
        if wadah is not None:
            return wadah
    return None


def wadah_isi(sup: BeautifulSoup) -> Tag:
    """Bagian isi halaman; kalau tidak dikenali, body yang kerangkanya sudah dibuang."""
    wadah = pilih_isi(sup)
    if wadah is not None:
        return wadah
    wadah = sup.body or sup
    buang_semua(wadah.select(PEMILIH_KERANGKA))
    return wadah


def judul_halaman(html: str) -> str:
    """Heading pertama di bagian isi; kalau tidak ada, isi <title>."""
    sup = BeautifulSoup(html or "", "lxml")
    wadah = pilih_isi(sup)
    kepala = wadah.find(["h1", "h2", "h3"]) if wadah is not None else None
    if kepala is not None and rapikan(kepala.get_text(" ")):
        return rapikan(kepala.get_text(" "))
    return rapikan(sup.title.get_text(" ")) if sup.title else ""


def ganti_isian_dengan_nilai(wadah: Tag) -> None:
    """Tulis nilai isian yang terlihat sebagai teks; isian tersembunyi dan password dibuang.

    Halaman detail di aplikasi Laravel sering menampilkan datanya di dalam
    <input disabled>, jadi nilainya perlu ikut terbaca. Dari <select> hanya
    pilihan yang terpilih yang ditulis.
    """
    for masukan in wadah.find_all("input"):
        jenis = (masukan.get("type") or "").lower()
        nilai = masukan.get("value") or ""
        if jenis in JENIS_MASUKAN_TERLIHAT and nilai.strip():
            masukan.replace_with(NavigableString(f" {nilai} "))
        else:
            masukan.decompose()
    for pilihan in wadah.find_all("select"):
        terpilih = pilihan.find("option", selected=True)
        teks = rapikan(terpilih.get_text(" ")) if terpilih is not None else ""
        pilihan.replace_with(NavigableString(f" {teks} "))


def teks_halaman(html: str) -> str:
    """Isi halaman sebagai teks: satu blok per baris, sel tabel dipisah " | ".

    Kerangka halaman (menu, header, footer), skrip, dan isian tersembunyi tidak
    ikut, termasuk token CSRF.
    """
    sup = BeautifulSoup(html or "", "lxml")
    buang_semua(sup.find_all(TAG_TANPA_TEKS))
    wadah = wadah_isi(sup)
    ganti_isian_dengan_nilai(wadah)

    for baris in wadah.find_all("tr"):
        sel = [rapikan(satu.get_text(" ")) for satu in baris.find_all(["th", "td"], recursive=False)]
        baris.replace_with(NavigableString("\n" + " | ".join(sel) + "\n"))
    for pemisah in wadah.find_all("br"):
        pemisah.replace_with(NavigableString("\n"))
    for blok in wadah.find_all(TAG_BLOK):
        blok.insert_before(NavigableString("\n"))
        blok.insert_after(NavigableString("\n"))

    baris_teks = (rapikan(satu) for satu in wadah.get_text().split("\n"))
    return "\n".join(satu for satu in baris_teks if satu)


def alamat_tujuan(href: str, url_halaman: str) -> str:
    """Alamat lengkap sebuah href, atau "" kalau href itu tidak menuju halaman mana pun."""
    href = (href or "").strip()
    if not href or href.startswith("#") or href.lower().startswith(SKEMA_BUKAN_TUJUAN):
        return ""
    return urljoin(url_halaman, href).split("#")[0]


def path_dari(alamat: str) -> str:
    """'https://host/penelitian?page=2' -> '/penelitian?page=2'."""
    bagian = urlsplit(alamat)
    return (bagian.path or "/") + (f"?{bagian.query}" if bagian.query else "")


def teks_tautan(tautan: Tag) -> str:
    """Teks sebuah tautan; tombol berikon tanpa teks memakai title atau aria-label-nya."""
    teks = rapikan(tautan.get_text(" "))
    if teks:
        return teks
    for atribut in ("title", "aria-label", "data-original-title", "data-bs-original-title"):
        if rapikan(tautan.get(atribut) or ""):
            return rapikan(tautan[atribut])
    return ""


def tautan_di(elemen: Tag, url_halaman: str) -> list[dict]:
    """Tautan di dalam sebuah elemen: teksnya dan alamat lengkapnya."""
    hasil = []
    for tautan in elemen.find_all("a", href=True):
        alamat = alamat_tujuan(tautan["href"], url_halaman)
        if alamat:
            hasil.append({"teks": teks_tautan(tautan), "url": alamat})
    return hasil


def tautan_isi(html: str, url_halaman: str) -> list[dict]:
    """Tautan di bagian isi halaman (tanpa menu), tanpa duplikat, urut seperti di halaman."""
    sup = BeautifulSoup(html or "", "lxml")
    hasil, terlihat = [], set()
    for satu in tautan_di(wadah_isi(sup), url_halaman):
        if satu["url"] not in terlihat:
            terlihat.add(satu["url"])
            hasil.append(satu)
    return hasil


def tautan_berikutnya(html: str, url_halaman: str) -> str:
    """Alamat halaman lanjutan dari paginasi Laravel (<a rel="next">), atau ""."""
    sup = BeautifulSoup(html or "", "lxml")
    tautan = sup.find("a", rel="next", href=True)
    return alamat_tujuan(tautan["href"], url_halaman) if tautan is not None else ""


def adalah_judul(tag) -> bool:
    """Elemen yang lazim menjadi judul sebuah tabel: heading atau .card-title."""
    if not isinstance(tag, Tag):
        return False
    return tag.name in TAG_JUDUL or "card-title" in (tag.get("class") or [])


def judul_tabel(tabel: Tag) -> str:
    """Keterangan tabel: <caption>, atau judul terdekat sebelum tabel."""
    keterangan = tabel.find("caption")
    if keterangan is not None and rapikan(keterangan.get_text(" ")):
        return rapikan(keterangan.get_text(" "))
    sebelumnya = tabel.find_previous(adalah_judul)
    return rapikan(sebelumnya.get_text(" ")) if sebelumnya is not None else ""


def jumlah_sel(baris: Tag) -> int:
    """Banyaknya sel <th>/<td> pada satu baris tabel."""
    return len(baris.find_all(["th", "td"], recursive=False))


def baris_milik(tabel: Tag) -> list[Tag]:
    """Seluruh baris milik tabel ini sendiri, tanpa baris tabel lain yang bersarang di dalamnya."""
    return [baris for baris in tabel.find_all("tr") if baris.find_parent("table") is tabel]


def beri_nama_unik(nama_kolom: list[str]) -> list[str]:
    """Nama kolom kosong jadi "kolom_N"; nama kembar diberi akhiran _2, _3, dan seterusnya."""
    hasil, terpakai = [], {}
    for urutan, nama in enumerate(nama_kolom, start=1):
        dasar = nama or f"kolom_{urutan}"
        terpakai[dasar] = terpakai.get(dasar, 0) + 1
        hasil.append(dasar if terpakai[dasar] == 1 else f"{dasar}_{terpakai[dasar]}")
    return hasil


def kolom_tabel(tabel: Tag) -> tuple[list[str], Tag | None]:
    """Nama kolom tabel beserta baris kepalanya.

    Diambil dari baris <thead> yang selnya paling banyak. Tanpa <thead>, baris
    pertama dipakai kalau isinya <th> semua. Tabel tanpa keduanya tidak punya
    nama kolom.
    """
    semua_baris = baris_milik(tabel)
    di_thead = [baris for baris in semua_baris if baris.find_parent("thead") is not None]
    if di_thead:
        baris_kepala = max(di_thead, key=jumlah_sel)
    elif semua_baris and not semua_baris[0].find_all("td", recursive=False) and jumlah_sel(semua_baris[0]):
        baris_kepala = semua_baris[0]
    else:
        return [], None
    nama = [rapikan(sel.get_text(" ")) for sel in baris_kepala.find_all(["th", "td"], recursive=False)]
    return beri_nama_unik(nama), baris_kepala


def tabel_halaman(html: str, url_halaman: str = "") -> list[dict]:
    """Seluruh tabel di halaman, tiap baris jadi dict berkunci nama kolom.

    Baris yang jumlah selnya tidak cocok dengan kolomnya (mis. baris "data
    kosong" ber-colspan) dikunci nomor urut sel, mulai dari "1". Tautan di dalam
    baris dikumpulkan di `_tautan`, karena tombol detail dan unduh biasanya ada
    di sana.
    """
    sup = BeautifulSoup(html or "", "lxml")
    hasil = []
    for nomor, tabel in enumerate(sup.find_all("table"), start=1):
        kolom, baris_kepala = kolom_tabel(tabel)
        semua_rekam = []
        for baris in baris_milik(tabel):
            if baris is baris_kepala or baris.find_parent("thead") is not None:
                continue
            isi = [rapikan(sel.get_text(" ")) for sel in baris.find_all(["th", "td"], recursive=False)]
            if not isi:
                continue
            if kolom and len(isi) == len(kolom):
                rekam = dict(zip(kolom, isi))
            else:
                rekam = {str(urutan): nilai for urutan, nilai in enumerate(isi, start=1)}
            tautan = tautan_di(baris, url_halaman)
            if tautan:
                rekam["_tautan"] = tautan
            semua_rekam.append(rekam)
        hasil.append({
            "nomor": nomor,
            "judul": judul_tabel(tabel),
            "kolom": kolom,
            "jumlah_baris": len(semua_rekam),
            "baris": semua_rekam,
        })
    return hasil


def adalah_kepala_grup(elemen: Tag) -> bool:
    """Elemen pembuka submenu: tautan tanpa tujuan (href="#"), tombol toggle, atau label teks."""
    if elemen.name == "a":
        href = (elemen.get("href") or "").strip().lower()
        return (
            not href
            or href.startswith("#")
            or href.startswith("javascript:")
            or elemen.has_attr("data-toggle")
            or elemen.has_attr("data-bs-toggle")
        )
    return elemen.name in TAG_KEPALA_GRUP


def grup_tautan(tautan: Tag) -> str:
    """Jalur menu induk sebuah tautan, mis. "Penelitian" atau "Publikasi > Jurnal".

    Submenu dikenali dari bentuk yang dipakai templat Bootstrap dan AdminLTE:
    daftar (<ul>, <ol>, atau <div> dropdown) yang didahului kepala grup. Kepala
    itu tautan pembuka di <li> yang sama, atau elemen tanpa tujuan seperti
    tautan href="#" dan tombol toggle.
    """
    jalur = []
    for leluhur in tautan.parents:
        if leluhur.name in ("nav", "aside", "body", "html", "[document]"):
            break
        if leluhur.name not in ("ul", "ol", "div"):
            continue
        # True: hanya elemen, bukan teks spasi di antara tag
        kepala = leluhur.find_previous_sibling(True)
        if kepala is None:
            continue
        di_dalam_li = leluhur.parent is not None and leluhur.parent.name == "li"
        if di_dalam_li or adalah_kepala_grup(kepala):
            nama = teks_tautan(kepala) if kepala.name == "a" else rapikan(kepala.get_text(" "))
            if nama:
                jalur.append(nama)
    return " > ".join(reversed(jalur))


def adalah_logout(alamat: str, nama: str) -> bool:
    """Tautan yang mengakhiri sesi. Tidak boleh masuk daftar menu, apalagi dibuka."""
    return "logout" in urlsplit(alamat).path.lower() or nama.lower() in TEKS_LOGOUT


def menu_navigasi(html: str, url_halaman: str, base_url: str) -> list[dict]:
    """Tautan menu navigasi yang menuju portal di `base_url`, urut seperti di halaman.

    Yang dibaca tautan di dalam wadah navigasi (nav, sidebar, navbar). Halaman
    tanpa wadah seperti itu dibaca seluruh tautannya. Logout, logo, tautan ke
    host lain, dan kepala grup yang tidak menuju ke mana pun (href="#") tidak
    ikut. Nama kepala grup dicatat di `grup` milik anak-anaknya.
    """
    sup = BeautifulSoup(html or "", "lxml")
    wadah_semua = sup.select(PEMILIH_NAVIGASI)
    if wadah_semua:
        tautan_semua = [tautan for wadah in wadah_semua for tautan in wadah.find_all("a", href=True)]
    else:
        tautan_semua = sup.find_all("a", href=True)

    host_portal = urlsplit(base_url).netloc.lower()
    hasil, terlihat = [], set()
    for tautan in tautan_semua:
        alamat = alamat_tujuan(tautan["href"], url_halaman)
        nama = teks_tautan(tautan)
        if not alamat or urlsplit(alamat).netloc.lower() != host_portal:
            continue
        if adalah_logout(alamat, nama) or KELAS_LOGO & set(tautan.get("class") or []):
            continue
        if alamat in terlihat:
            continue
        terlihat.add(alamat)
        hasil.append({
            "nama": nama or path_dari(alamat),
            "grup": grup_tautan(tautan),
            "path": path_dari(alamat),
            "url": alamat,
        })
    return hasil


def potong_tabel(tabel_semua: list[dict], maks_karakter: int) -> tuple[list[dict], bool]:
    """Ambil baris tabel selama JSON-nya masih muat dalam `maks_karakter`; 0 berarti utuh.

    `jumlah_baris` tiap tabel tetap menyebut jumlah aslinya, jadi pemotongan
    terlihat dari selisihnya.
    """
    if maks_karakter <= 0:
        return tabel_semua, False
    terpakai, terpotong, hasil = 0, False, []
    for tabel in tabel_semua:
        baris_muat = []
        for baris in tabel["baris"]:
            ukuran = len(json.dumps(baris, ensure_ascii=False))
            if terpotong or terpakai + ukuran > maks_karakter:
                terpotong = True
                break
            terpakai += ukuran
            baris_muat.append(baris)
        hasil.append(tabel | {"baris": baris_muat})
    return hasil, terpotong


def isi_halaman(halaman: Halaman, bentuk: str = "teks", maks_karakter: int = 0) -> dict:
    """Isi halaman dalam bentuk yang diminta, siap dikirim lewat CLI, REST API, atau MCP.

    `bentuk` "teks" mengembalikan isi halaman sebagai teks; "tabel"
    mengembalikan seluruh tabelnya. `maks_karakter` membatasi panjang teks atau
    JSON baris tabel (0 berarti utuh), dan `terpotong` menandai kalau batas itu
    tercapai.
    """
    if bentuk not in BENTUK_HALAMAN:
        raise ValueError(f"bentuk harus salah satu dari {', '.join(BENTUK_HALAMAN)}, bukan {bentuk!r}")
    hasil = {"url": halaman.url, "judul": halaman.judul(), "bentuk": bentuk}
    if bentuk == "teks":
        teks = halaman.teks()
        terpotong = 0 < maks_karakter < len(teks)
        return hasil | {
            "teks": teks[:maks_karakter] if terpotong else teks,
            "panjang": len(teks),
            "terpotong": terpotong,
        }

    tabel, terpotong = potong_tabel(halaman.tabel(), maks_karakter)
    hasil |= {"jumlah_tabel": len(tabel), "tabel": tabel, "terpotong": terpotong}
    if not any(satu["jumlah_baris"] for satu in tabel):
        hasil["catatan"] = CATATAN_TABEL_KOSONG
    return hasil
