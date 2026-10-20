"""Pengajuan cek Turnitin LPPM (/turnitin): jatah, riwayat, dan pengajuan baru.

Per Oktober 2026 halaman itu berisi tiga bagian:

    jatah      kotak .alert-info "Status Pengajuan Anda: 1 dari 2 jatah digunakan
               (Sisa 1x pengajuan)"
    form       POST ke /turnitin berisi _token, judul_naskah, dan file_artikel
               (tautan Google Drive naskah)
    riwayat    tabel No, Judul Naskah, Tanggal Submit (dd/mm/yyyy HH:MM), No. Surat
               ("-" kalau belum ada), Status, dan Aksi

Sesudah pengajuan, pesan flash .alert-success "Pengajuan Cek Turnitin berhasil
dikirim." tampil sekali di atas form. Bentuk pesan galatnya belum teramati;
yang dibaca adalah bentuk bawaan Laravel, yaitu .alert-danger dan
.invalid-feedback.

Kolom Aksi baru teramati berisi teks "Proses LPPM" untuk status "Submit". Isinya
untuk status lain belum pernah terlihat, jadi pembacanya mencatat apa adanya
tanpa menafsirkan: teksnya, setiap href, dan atribut data-* tiap elemen (mis.
data-toggle dan data-target pemicu modal "Form Perbaikan") beserta teks modal
yang dituju.

`ajukan_turnitin()` menulis ke portal dan memakai satu jatah. Bawaannya uji coba:
isian dan jatahnya diperiksa, lalu rencana kirimannya dikembalikan tanpa
mengirim apa pun. Kiriman sungguhan dikirim tepat sekali. Kalau hasilnya tidak
bisa dipastikan, yang muncul HasilTidakPasti, dan pemakai perlu memeriksa
riwayatnya sebelum mencoba lagi.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from lppm_mcp.halaman import (
    Halaman,
    alamat_tujuan,
    baris_milik,
    buang_semua,
    ganti_isian_dengan_nilai,
    kolom_tabel,
    rapikan,
    teks_tautan,
)
from lppm_mcp.lppm_client import KlienLppm, LppmError, token_meta
from lppm_mcp.menu import MenuLppm

PATH_TURNITIN = "/turnitin"
FIELD_TOKEN = "_token"
FIELD_JUDUL = "judul_naskah"
FIELD_TAUTAN = "file_artikel"
ISIAN_DIKENAL = frozenset({FIELD_TOKEN, FIELD_JUDUL, FIELD_TAUTAN})
HOST_TAUTAN_NASKAH = frozenset({"drive.google.com", "docs.google.com"})

POLA_JATAH = re.compile(r"(\d+)\s*dari\s*(\d+)\s*jatah", re.IGNORECASE)
POLA_SISA = re.compile(r"sisa\s*(\d+)", re.IGNORECASE)

# kepala kolom tabel riwayat setelah huruf kecil dan tanpa spasi atau tanda baca
KOLOM_RIWAYAT = {
    "no": "no",
    "judulnaskah": "judul",
    "tanggalsubmit": "tanggal_submit",
    "nosurat": "no_surat",
    "status": "status",
    "aksi": "aksi",
}
FORMAT_WAKTU = (
    ("%d/%m/%Y %H:%M", "minutes"),
    ("%d/%m/%Y %H:%M:%S", "seconds"),
    ("%Y-%m-%d %H:%M:%S", "seconds"),  # bawaan Laravel kalau templatnya tidak memformat
)
FORMAT_TANGGAL = ("%d/%m/%Y", "%Y-%m-%d")
TANDA_KOSONG = "-–— "

PEMILIH_TOMBOL_TUTUP = ".close, .btn-close, [data-dismiss], [data-bs-dismiss]"
ATRIBUT_SASARAN = ("data-target", "data-bs-target", "href")
KATA_PERBAIKAN = "perbaik"

PESAN_UJI_COBA = (
    "Uji coba: belum ada yang dikirim. Kiriman sungguhan memakai 1 dari {sisa} jatah yang tersisa. "
    "Pastikan berkas di Google Drive bisa dibuka LPPM."
)
PESAN_DITERIMA = "Pengajuan terkirim dan tercatat di riwayat."
PESAN_BELUM_TERLIHAT = (
    "Kiriman sampai ke portal, tetapi baris barunya tidak terlihat di riwayat. Baca flash untuk "
    "pesan portal, dan periksa riwayat sebelum mencoba lagi."
)
PESAN_TIDAK_PASTI = (
    "Pengajuan sudah dikirim, tetapi hasilnya tidak bisa dipastikan ({galat}). Periksa riwayat "
    "(./lppm turnitin atau tool daftar_turnitin) sebelum mencoba lagi, karena setiap kiriman yang "
    "diterima memakai satu jatah."
)


class PengajuanDitolak(LppmError):
    """Pengajuan tidak dikirim karena isian, jatah, atau riwayatnya tidak memenuhi syarat."""


class HasilTidakPasti(LppmError):
    """Kiriman sudah berangkat, tetapi diterima atau tidaknya oleh portal tidak bisa dipastikan."""


@dataclass
class JatahTurnitin:
    """Jatah pengajuan milik akun ini, dari kotak "Status Pengajuan Anda"."""

    dipakai: int
    total: int
    sisa: int
    teks: str


@dataclass
class BarisTurnitin:
    """Satu baris tabel Riwayat Pengajuan Cek Turnitin.

    Kolom Aksi disimpan apa adanya: `aksi_tautan` berisi setiap href (teks, href
    mentah, dan alamat lengkapnya), `aksi_pemicu` setiap elemen beratribut data-*
    beserta teks modal yang dituju. `ada_modal_perbaikan` hanya ringkasan: ada
    pemicu data-toggle="modal" yang teksnya atau modal tujuannya menyebut
    "perbaikan".
    """

    no: int | None
    judul: str
    tanggal_submit: str | None
    tanggal_submit_teks: str
    no_surat: str | None
    status: str
    aksi_teks: str
    aksi_tautan: list[dict] = field(default_factory=list)
    aksi_pemicu: list[dict] = field(default_factory=list)
    ada_modal_perbaikan: bool = False


@dataclass
class StatusTurnitin:
    """Isi halaman Pengajuan Cek Turnitin: jatah, pesan flash, form, dan riwayat."""

    url: str
    jatah: JatahTurnitin | None
    flash: list[dict]
    ada_form: bool
    riwayat: list[BarisTurnitin]

    def sebagai_dict(self) -> dict:
        """Bentuk JSON untuk CLI, REST API, dan MCP."""
        return asdict(self)


@dataclass
class FormPengajuan:
    """Form Pengajuan Baru yang dibaca dari halaman. Token CSRF tidak ikut tercetak."""

    action: str
    token: str = field(repr=False)


@dataclass
class HasilPengajuan:
    """Hasil ajukan_turnitin().

    Pada uji coba, `isian` dan `action` adalah rencana kiriman (tanpa token CSRF)
    dan `jatah` adalah jatah saat ini. Sesudah kiriman sungguhan, `jatah`,
    `flash`, dan `baris_baru` dibaca dari halaman tempat portal mendarat.
    `diterima` bernilai True kalau baris baru itu ditemukan di riwayat.
    """

    uji_coba: bool
    terkirim: bool
    diterima: bool
    action: str
    isian: dict[str, str]
    jatah: JatahTurnitin | None
    flash: list[dict] = field(default_factory=list)
    baris_baru: BarisTurnitin | None = None
    pesan: str = ""
    metode: str = "POST"

    def sebagai_dict(self) -> dict:
        """Bentuk JSON untuk CLI, REST API, dan MCP."""
        return asdict(self)


# --- isian -------------------------------------------------------------------


def kunci_judul(judul: str) -> str:
    """Bentuk pembanding judul: spasi dirapikan, huruf besar dan kecil disamakan."""
    return rapikan(judul).casefold()


def periksa_judul(judul: str) -> str:
    """Judul yang spasinya sudah dirapikan; judul kosong ditolak."""
    judul = rapikan(judul)
    if not judul:
        raise PengajuanDitolak("Judul naskah tidak boleh kosong")
    return judul


def periksa_tautan(tautan: str) -> str:
    """Tautan naskah tanpa spasi di tepinya; selain https ke Google Drive atau Docs ditolak."""
    tautan = (tautan or "").strip()
    try:
        bagian = urlsplit(tautan)
    except ValueError:
        bagian = urlsplit("")
    if (
        bagian.scheme != "https"
        or bagian.netloc.lower() not in HOST_TAUTAN_NASKAH
        or not bagian.path.strip("/")
        or any(huruf.isspace() for huruf in tautan)
    ):
        raise PengajuanDitolak(
            "Tautan naskah harus https ke drive.google.com atau docs.google.com, "
            f"mis. https://drive.google.com/file/d/.../view, bukan {tautan!r}"
        )
    return tautan


def tanggal_iso(teks: str) -> str | None:
    """'20/10/2026 15:15' -> '2026-10-20T15:15'; None kalau formatnya tidak dikenal."""
    for pola, presisi in FORMAT_WAKTU:
        try:
            return datetime.strptime(teks, pola).isoformat(timespec=presisi)
        except ValueError:
            continue
    for pola in FORMAT_TANGGAL:
        try:
            return datetime.strptime(teks, pola).date().isoformat()
        except ValueError:
            continue
    return None


# --- membaca halaman ---------------------------------------------------------


def di_luar_modal(elemen: Tag) -> bool:
    """Elemen yang bukan bagian dari modal Bootstrap, mis. modal Form Perbaikan."""
    return elemen.find_parent(class_="modal") is None


def teks_bersih(elemen: Tag) -> str:
    """Teks yang terlihat dari sebuah elemen, tanpa tombol tutup (×) dan isian tersembunyi."""
    salinan = copy.copy(elemen)
    buang_semua(salinan.select(PEMILIH_TOMBOL_TUTUP))
    ganti_isian_dengan_nilai(salinan)
    return rapikan(salinan.get_text(" "))


def jatah_dari(sup: BeautifulSoup) -> JatahTurnitin | None:
    """Jatah dari kotak "Status Pengajuan Anda"; None kalau kalimatnya tidak ditemukan."""
    for kotak in sup.select(".alert"):
        teks = teks_bersih(kotak)
        cocok = POLA_JATAH.search(teks)
        if cocok is None or not di_luar_modal(kotak):
            continue
        dipakai, total = int(cocok.group(1)), int(cocok.group(2))
        sisa = max(total - dipakai, 0)
        tertulis = POLA_SISA.search(teks)
        if tertulis is not None:
            # kalau kedua angka tidak sejalan, yang lebih kecil dipakai supaya jatah tidak terlampaui
            sisa = min(sisa, int(tertulis.group(1)))
        return JatahTurnitin(dipakai=dipakai, total=total, sisa=sisa, teks=teks)
    return None


def jenis_pesan(kotak: Tag) -> str:
    """'success', 'danger', dan seterusnya dari kelas alert-*; galat isian Laravel dihitung 'danger'."""
    kelas_semua = kotak.get("class") or []
    for kelas in kelas_semua:
        if kelas.startswith("alert-") and kelas != "alert-dismissible":
            return kelas.removeprefix("alert-")
    return "danger" if "invalid-feedback" in kelas_semua else "info"


def flash_dari(sup: BeautifulSoup) -> list[dict]:
    """Pesan flash dan galat isian: setiap .alert selain kotak jatah, serta .invalid-feedback.

    Pesan di dalam modal atau tabel riwayat tidak ikut, karena itu milik baris
    tertentu, bukan hasil permintaan terakhir.
    """
    hasil = []
    for kotak in sup.select(".alert, .invalid-feedback"):
        if not di_luar_modal(kotak) or kotak.find_parent("table") is not None:
            continue
        teks = teks_bersih(kotak)
        if teks and not POLA_JATAH.search(teks):
            hasil.append({"jenis": jenis_pesan(kotak), "teks": teks})
    return hasil


def cari_form_pengajuan(sup: BeautifulSoup) -> Tag | None:
    """Form Pengajuan Baru: form di luar modal yang memuat isian judul_naskah."""
    for form in sup.find_all("form"):
        if di_luar_modal(form) and form.find(attrs={"name": FIELD_JUDUL}) is not None:
            return form
    return None


def kunci_kolom(nama: str) -> str:
    """'No. Surat' -> 'nosurat'."""
    return re.sub(r"[^0-9a-z]", "", nama.lower())


def tabel_riwayat(sup: BeautifulSoup) -> tuple[Tag | None, Tag | None, list[str]]:
    """Tabel riwayat, baris kepalanya, dan nama baku tiap kolom; dikenali dari kolom Judul Naskah.

    Kolom yang tidak dikenal bernama "" dan diabaikan pembaca barisnya.
    """
    for tabel in sup.find_all("table"):
        if not di_luar_modal(tabel):
            continue
        kolom, baris_kepala = kolom_tabel(tabel)
        baku = [KOLOM_RIWAYAT.get(kunci_kolom(nama), "") for nama in kolom]
        if "judul" in baku:
            return tabel, baris_kepala, baku
    return None, None, []


def tautan_aksi(sel: Tag, url_halaman: str) -> list[dict]:
    """Setiap href di sel Aksi: teksnya, nilai href mentah, dan alamat lengkapnya.

    `url` kosong untuk href yang tidak menuju halaman, seperti "#modal" atau
    "javascript:".
    """
    return [
        {"teks": teks_tautan(elemen), "href": elemen["href"], "url": alamat_tujuan(elemen["href"], url_halaman)}
        for elemen in sel.find_all(href=True)
    ]


def teks_modal(pemicu: Tag, sup: BeautifulSoup) -> str:
    """Teks elemen yang dituju pemicu lewat data-target, data-bs-target, atau href "#id"."""
    for nama in ATRIBUT_SASARAN:
        sasaran = (pemicu.get(nama) or "").strip()
        if sasaran.startswith("#") and len(sasaran) > 1:
            modal = sup.find(id=sasaran[1:])
            if modal is not None:
                return teks_bersih(modal)
    return ""


def pemicu_aksi(sel: Tag, sup: BeautifulSoup) -> list[dict]:
    """Elemen di sel Aksi yang membawa atribut data-*, dicatat apa adanya beserta teks modal tujuannya."""
    hasil = []
    for elemen in sel.find_all(True):
        atribut = {nama: nilai for nama, nilai in elemen.attrs.items() if nama.startswith("data-")}
        if atribut:
            hasil.append({
                "tag": elemen.name,
                "teks": teks_tautan(elemen),
                "atribut": atribut,
                "teks_modal": teks_modal(elemen, sup),
            })
    return hasil


def memicu_modal_perbaikan(pemicu: dict) -> bool:
    """Pemicu data-toggle="modal" yang teksnya atau teks modal tujuannya menyebut "perbaikan"."""
    atribut = pemicu["atribut"]
    toggle = (atribut.get("data-toggle") or atribut.get("data-bs-toggle") or "").lower()
    return toggle == "modal" and KATA_PERBAIKAN in f"{pemicu['teks']} {pemicu['teks_modal']}".lower()


def baris_turnitin(sel: dict[str, Tag], sup: BeautifulSoup, url_halaman: str) -> BarisTurnitin:
    """Satu baris riwayat dari sel-selnya, yang dikunci nama kolom baku."""
    teks = {kunci: rapikan(isi.get_text(" ")) for kunci, isi in sel.items()}
    nomor = teks.get("no", "")
    tanggal = teks.get("tanggal_submit", "")
    no_surat = teks.get("no_surat", "")
    sel_aksi = sel.get("aksi")
    pemicu = pemicu_aksi(sel_aksi, sup) if sel_aksi is not None else []
    return BarisTurnitin(
        no=int(nomor) if nomor.isdigit() else None,
        judul=teks.get("judul", ""),
        tanggal_submit=tanggal_iso(tanggal),
        tanggal_submit_teks=tanggal,
        # portal menulis "-" selama nomor surat belum ada
        no_surat=no_surat if no_surat.strip(TANDA_KOSONG) else None,
        status=teks.get("status", ""),
        aksi_teks=teks.get("aksi", ""),
        aksi_tautan=tautan_aksi(sel_aksi, url_halaman) if sel_aksi is not None else [],
        aksi_pemicu=pemicu,
        ada_modal_perbaikan=any(memicu_modal_perbaikan(satu) for satu in pemicu),
    )


def riwayat_dari(sup: BeautifulSoup, url_halaman: str) -> list[BarisTurnitin]:
    """Baris tabel riwayat, urut seperti di halaman.

    Baris yang jumlah selnya tidak cocok dengan kolomnya (mis. baris "belum ada
    data" ber-colspan) dilewati.
    """
    tabel, baris_kepala, kolom = tabel_riwayat(sup)
    if tabel is None:
        return []
    hasil = []
    for baris in baris_milik(tabel):
        if baris is baris_kepala or baris.find_parent("thead") is not None:
            continue
        sel = baris.find_all(["td", "th"], recursive=False)
        if len(sel) == len(kolom):
            hasil.append(baris_turnitin(dict(zip(kolom, sel)), sup, url_halaman))
    return hasil


def baca_halaman_turnitin(html: str, url_halaman: str = "") -> StatusTurnitin:
    """Jatah, pesan flash, keberadaan form, dan riwayat dari satu halaman Turnitin. Tanpa jaringan."""
    sup = BeautifulSoup(html or "", "lxml")
    return StatusTurnitin(
        url=url_halaman,
        jatah=jatah_dari(sup),
        flash=flash_dari(sup),
        ada_form=cari_form_pengajuan(sup) is not None,
        riwayat=riwayat_dari(sup, url_halaman),
    )


def baca_form_pengajuan(html: str, url_halaman: str) -> FormPengajuan:
    """Action dan token CSRF Form Pengajuan Baru. Form yang berubah ditolak sebelum apa pun dikirim.

    Isian di luar _token, judul_naskah, dan file_artikel dianggap tanda bahwa
    form-nya berubah. Mengirim tanpa mengisinya bisa membuat jatah terpakai untuk
    pengajuan yang salah, jadi modul ini perlu diperbarui dulu.
    """
    sup = BeautifulSoup(html or "", "lxml")
    form = cari_form_pengajuan(sup)
    if form is None:
        raise LppmError(
            "Form pengajuan Turnitin tidak ada di halaman; mungkin jatahnya sudah habis atau halamannya berubah"
        )
    if (form.get("method") or "GET").upper() != "POST":
        raise LppmError("Form pengajuan Turnitin tidak lagi memakai POST; tidak ada yang dikirim")
    nama_isian = {
        isian["name"] for isian in form.find_all(["input", "select", "textarea", "button"]) if isian.get("name")
    }
    asing = sorted(nama_isian - ISIAN_DIKENAL)
    if asing:
        raise LppmError(
            f"Form pengajuan Turnitin memuat isian yang belum dikenal ({', '.join(asing)}); tidak ada yang "
            "dikirim. Perbarui lppm_mcp/turnitin.py lebih dulu."
        )
    if FIELD_TAUTAN not in nama_isian:
        raise LppmError(f"Form pengajuan Turnitin tidak lagi memuat isian {FIELD_TAUTAN}; tidak ada yang dikirim")
    masukan_token = form.find("input", attrs={"name": FIELD_TOKEN})
    token = (masukan_token.get("value") or "") if masukan_token is not None else ""
    token = token or token_meta(sup)
    if not token:
        raise LppmError("Token CSRF form pengajuan Turnitin tidak ditemukan")
    return FormPengajuan(action=urljoin(url_halaman, form.get("action") or url_halaman), token=token)


# --- memeriksa dan mencocokkan ----------------------------------------------


def periksa_kelayakan(status: StatusTurnitin, judul: str, *, paksa: bool) -> JatahTurnitin:
    """Pastikan jatah masih ada dan judulnya belum ada di riwayat. `paksa` melewati pemeriksaan judul."""
    jatah = status.jatah
    if jatah is None:
        raise LppmError(
            "Jatah pengajuan tidak terbaca di halaman Turnitin; tidak ada yang dikirim supaya jatah tidak terlampaui"
        )
    if jatah.sisa <= 0:
        raise PengajuanDitolak(
            f"Jatah pengajuan cek Turnitin sudah habis ({jatah.dipakai} dari {jatah.total} terpakai)"
        )
    if paksa:
        return jatah
    if jatah.dipakai > 0 and not status.riwayat:
        raise LppmError(
            f"Riwayat pengajuan tidak terbaca padahal {jatah.dipakai} jatah sudah terpakai, jadi judul kembar "
            "tidak bisa diperiksa. Ulangi dengan paksa=True (CLI: --paksa) kalau tetap ingin mengajukan."
        )
    for baris in status.riwayat:
        if kunci_judul(baris.judul) == kunci_judul(judul):
            raise PengajuanDitolak(
                f"Judul {judul!r} sudah ada di riwayat (diajukan {baris.tanggal_submit_teks or '-'}, "
                f"status {baris.status or '-'}). Ulangi dengan paksa=True (CLI: --paksa) kalau memang "
                "ingin mengajukannya lagi."
            )
    return jatah


def kunci_baris(baris: BarisTurnitin) -> tuple[str, str]:
    """Pengenal baris riwayat untuk membandingkan sebelum dan sesudah kiriman."""
    return kunci_judul(baris.judul), baris.tanggal_submit_teks


def cari_baris_baru(sebelum: list[BarisTurnitin], sesudah: list[BarisTurnitin], judul: str) -> BarisTurnitin | None:
    """Baris riwayat yang muncul sesudah kiriman.

    Baris baru yang judulnya sama didahulukan. Kalau tidak ada, misalnya karena
    portal memendekkan judul panjang, satu-satunya baris baru yang dipakai.
    """
    lama = Counter(kunci_baris(satu) for satu in sebelum)
    baru = []
    for satu in sesudah:
        kunci = kunci_baris(satu)
        if lama[kunci] > 0:
            lama[kunci] -= 1
        else:
            baru.append(satu)
    for satu in baru:
        if kunci_judul(satu.judul) == kunci_judul(judul):
            return satu
    return baru[0] if len(baru) == 1 else None


# --- menu ---------------------------------------------------------------------


class MenuTurnitin(MenuLppm):
    """Menu Pengajuan Cek Turnitin untuk satu sesi LPPM."""

    path_bawaan = PATH_TURNITIN
    # kunci_path sengaja kosong: /turnitin juga satu-satunya tujuan POST yang
    # diizinkan klien, jadi path-nya tidak bisa dipindah lewat setelan

    def status(self) -> StatusTurnitin:
        """Jatah dan riwayat pengajuan saat ini."""
        return self.status_dari(self.halaman())

    def status_dari(self, halaman: Halaman) -> StatusTurnitin:
        """Status dari `halaman`, dengan riwayat dari halaman paginasi lanjutannya kalau ada."""
        status = baca_halaman_turnitin(halaman.html, halaman.url)
        for lanjutan in self.telusuri(halaman)[1:]:
            status.riwayat.extend(baca_halaman_turnitin(lanjutan.html, lanjutan.url).riwayat)
        return status

    def status_sesudah(self, jawaban) -> StatusTurnitin:
        """Status sesudah kiriman, dibaca dari halaman tempat portal mendarat.

        Kalau portal mendarat di halaman lain, pesan flash-nya tetap diambil dari
        sana, lalu jatah dan riwayatnya dibaca ulang dari /turnitin.
        """
        mendarat = Halaman(url=jawaban.url, html=jawaban.text, status=jawaban.status_code)
        if urlsplit(mendarat.url).path.rstrip("/") == self.path():
            return self.status_dari(mendarat)
        flash = baca_halaman_turnitin(mendarat.html, mendarat.url).flash
        return replace(self.status(), flash=flash)

    def ajukan(self, judul: str, tautan: str, *, uji_coba: bool = True, paksa: bool = False) -> HasilPengajuan:
        """Ajukan satu naskah untuk dicek Turnitin. Bawaannya uji coba: tidak ada yang dikirim.

        Judul dan tautan diperiksa lebih dulu tanpa menghubungi portal. Sesudah
        itu halaman /turnitin dibaca untuk jatah, riwayat, dan token CSRF.
        Pengajuan ditolak kalau jatahnya habis atau judul yang sama sudah ada di
        riwayat; `paksa=True` melewati pemeriksaan judul saja. Dengan
        `uji_coba=False` form dikirim tepat sekali.
        """
        judul = periksa_judul(judul)
        tautan = periksa_tautan(tautan)
        halaman = self.halaman()
        sebelum = self.status_dari(halaman)
        jatah = periksa_kelayakan(sebelum, judul, paksa=paksa)
        form = baca_form_pengajuan(halaman.html, halaman.url)
        action = self.klien.alamat_kiriman(form.action)
        isian = {FIELD_JUDUL: judul, FIELD_TAUTAN: tautan}
        if uji_coba:
            return HasilPengajuan(
                uji_coba=True,
                terkirim=False,
                diterima=False,
                action=action,
                isian=isian,
                jatah=jatah,
                pesan=PESAN_UJI_COBA.format(sisa=jatah.sisa),
            )

        try:
            jawaban = self.klien.kirim_form(action, {FIELD_TOKEN: form.token, **isian}, referer=halaman.url)
            sesudah = self.status_sesudah(jawaban)
        except LppmError as galat:
            raise HasilTidakPasti(PESAN_TIDAK_PASTI.format(galat=galat)) from galat
        baris_baru = cari_baris_baru(sebelum.riwayat, sesudah.riwayat, judul)
        return HasilPengajuan(
            uji_coba=False,
            terkirim=True,
            diterima=baris_baru is not None,
            action=action,
            isian=isian,
            jatah=sesudah.jatah,
            flash=sesudah.flash,
            baris_baru=baris_baru,
            pesan=PESAN_DITERIMA if baris_baru is not None else PESAN_BELUM_TERLIHAT,
        )


def daftar_turnitin(klien: KlienLppm) -> StatusTurnitin:
    """Jatah dan riwayat pengajuan cek Turnitin milik akun `klien`. Hanya membaca."""
    return MenuTurnitin(klien).status()


def ajukan_turnitin(
    klien: KlienLppm, judul: str, tautan: str, *, uji_coba: bool = True, paksa: bool = False
) -> HasilPengajuan:
    """Ajukan satu naskah untuk dicek Turnitin; uraiannya di MenuTurnitin.ajukan()."""
    return MenuTurnitin(klien).ajukan(judul, tautan, uji_coba=uji_coba, paksa=paksa)
