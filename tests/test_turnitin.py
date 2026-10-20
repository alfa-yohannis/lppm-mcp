"""Uji pengajuan dan pemantauan cek Turnitin: pembaca halaman, pemeriksaan isian, dan alur kirim.

Halaman dan kiriman ke /turnitin dijawab SitusTiruan; tidak ada yang keluar ke
jaringan. Judul, nomor surat, dan tautan Google Drive di sini dikarang.
"""

from __future__ import annotations

import json

import pytest

from lppm_mcp.lppm_client import (
    KATA_AKSI,
    PATH_POST_DIIZINKAN,
    AlamatDitolak,
    KlienLppm,
    LppmError,
)
from lppm_mcp.turnitin import (
    PESAN_BELUM_TERLIHAT,
    HasilTidakPasti,
    PengajuanDitolak,
    ajukan_turnitin,
    baca_form_pengajuan,
    baca_halaman_turnitin,
    cari_baris_baru,
    daftar_turnitin,
    periksa_tautan,
    tanggal_iso,
)
from conftest import (
    JUDUL_TURNITIN_UJI,
    PASSWORD_UJI,
    PORTAL,
    TAUTAN_NASKAH_UJI,
    TOKEN_UJI,
    USERNAME_UJI,
    JawabanTiruan,
    baris_riwayat_turnitin,
    halaman_turnitin,
)

URL_TURNITIN = f"{PORTAL}/turnitin"
JUDUL_BARU = "Rancangan Sistem Karangan untuk Kota Metropolis"

# Salinan apa adanya dari struktur halaman asli yang diamati 20 Oktober 2026
# (isi tabel fiktif, token disamarkan menjadi "-").
HALAMAN_TURNITIN_CONTOH = """<div class="container my-4">
  <h3 class="mb-3">Pengajuan Cek Turnitin</h3>
  <div class="alert alert-info"> <strong>Status Pengajuan Anda:</strong> 1 dari 2 jatah digunakan (Sisa 1x pengajuan) </div>
  <div class="alert alert-success">Pengajuan Cek Turnitin berhasil dikirim.</div>
  <div class="card mb-4">
    <div class="card-header">Form Pengajuan Baru</div>
    <div class="card-body">
      <form action="https://lppm.pradita.ac.id/turnitin" method="POST">
        <input type="hidden" name="_token" value="-">
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
        <tbody>
          <tr>
            <td>1</td>
            <td>Kerangka Kerja Fiktif untuk Kota Gotham</td>
            <td>20/10/2026 15:15</td>
            <td>-</td>
            <td> <span class="badge badge-info"> Submit </span> </td>
            <td> <span class="text-muted">Proses LPPM</span> </td>
          </tr>
          <!-- Modal Form Perbaikan (Bootstrap 4) -->
        </tbody>
      </table>
    </div>
  </div>
</div>"""

# Kolom Aksi untuk status selain "Submit" belum pernah diamati. Bentuk di bawah
# hanya dugaan yang lazim di Bootstrap 4, dipakai untuk memastikan pembacanya
# mencatat apa adanya tanpa bergantung pada bentuk tertentu.
AKSI_UNDUH = (
    f'<a href="{PORTAL}/turnitin/7/surat" class="btn btn-success btn-sm">Unduh Surat</a> '
    '<a href="https://drive.google.com/file/d/laporan-karangan/view" target="_blank">Laporan</a>'
)
AKSI_PERBAIKAN = (
    '<button type="button" class="btn btn-warning btn-sm" data-toggle="modal" '
    'data-target="#perbaikan8">Form Perbaikan</button>'
)
MODAL_PERBAIKAN = f"""
          <div class="modal fade" id="perbaikan8" tabindex="-1" role="dialog">
            <div class="modal-dialog"><div class="modal-content">
              <div class="modal-header"><h5 class="modal-title">Form Perbaikan</h5>
                <button type="button" class="close" data-dismiss="modal">&times;</button></div>
              <form action="{PORTAL}/turnitin/8/perbaikan" method="POST">
                <input type="hidden" name="_token" value="{TOKEN_UJI}">
                <div class="modal-body">
                  <div class="alert alert-warning">Catatan LPPM: similarity 35%, perbaiki bab 2.</div>
                  <input type="text" name="judul_naskah" value="Judul Lama Karangan">
                  <input type="url" name="file_artikel" value="">
                </div>
                <div class="modal-footer">
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Tutup</button>
                  <button type="submit" class="btn btn-primary">Kirim Perbaikan</button>
                </div>
              </form>
            </div></div>
          </div>"""
AKSI_CATATAN = '<a href="#catatan9" data-toggle="modal" title="Lihat catatan"><i class="fa fa-eye"></i></a>'
MODAL_CATATAN = '<div class="modal fade" id="catatan9"><div class="modal-body">Catatan Reviewer: lengkap.</div></div>'


@pytest.fixture
def klien(situs) -> KlienLppm:
    """Klien berkredensial karangan yang bicara dengan portal tiruan."""
    return KlienLppm(USERNAME_UJI, PASSWORD_UJI)


def jumlah_kiriman(situs) -> int:
    """Banyaknya POST ke /turnitin yang sampai di portal tiruan."""
    return situs.jumlah("POST", "/turnitin")


# --- membaca halaman ---------------------------------------------------------


def test_halaman_contoh_asli_terbaca_utuh():
    status = baca_halaman_turnitin(HALAMAN_TURNITIN_CONTOH, URL_TURNITIN)

    assert (status.jatah.dipakai, status.jatah.total, status.jatah.sisa) == (1, 2, 1)
    assert status.jatah.teks == "Status Pengajuan Anda: 1 dari 2 jatah digunakan (Sisa 1x pengajuan)"
    assert status.flash == [{"jenis": "success", "teks": "Pengajuan Cek Turnitin berhasil dikirim."}]
    assert status.ada_form is True
    assert len(status.riwayat) == 1
    baris = status.riwayat[0]
    assert baris.no == 1
    assert baris.judul == "Kerangka Kerja Fiktif untuk Kota Gotham"
    assert baris.tanggal_submit == "2026-10-20T15:15"
    assert baris.tanggal_submit_teks == "20/10/2026 15:15"
    assert baris.no_surat is None
    assert baris.status == "Submit"
    assert baris.aksi_teks == "Proses LPPM"
    assert baris.aksi_tautan == []
    assert baris.aksi_pemicu == []
    assert baris.ada_modal_perbaikan is False


def test_form_contoh_asli_terbaca():
    form = baca_form_pengajuan(HALAMAN_TURNITIN_CONTOH, URL_TURNITIN)

    assert form.action == URL_TURNITIN
    assert form.token == "-"  # token di contoh sudah disamarkan
    assert repr(form) == f"FormPengajuan(action='{URL_TURNITIN}')"


@pytest.mark.parametrize(
    "kalimat, sisa",
    [
        ("2 dari 2 jatah digunakan (Sisa 0x pengajuan)", 0),
        ("0 dari 2 jatah digunakan (Sisa 2x pengajuan)", 2),
        ("1 dari 2 jatah digunakan", 1),  # tanpa keterangan sisa: dihitung sendiri
        ("1 dari 2 jatah digunakan (Sisa 0x pengajuan)", 0),  # angka tidak sejalan: yang terkecil
    ],
)
def test_sisa_jatah(kalimat, sisa):
    html = f'<div class="alert alert-info"><strong>Status Pengajuan Anda:</strong> {kalimat}</div>'

    assert baca_halaman_turnitin(html).jatah.sisa == sisa


def test_jatah_tidak_terbaca_menjadi_none():
    assert baca_halaman_turnitin("<div class='alert alert-info'>Selamat datang</div>").jatah is None


def test_flash_galat_tanpa_tombol_tutup_dan_tanpa_pesan_milik_modal():
    html = (
        '<div class="alert alert-info">Status Pengajuan Anda: 1 dari 2 jatah digunakan</div>'
        '<div class="alert alert-danger alert-dismissible"><button type="button" class="close" '
        'data-dismiss="alert">&times;</button>Pengajuan gagal disimpan.</div>'
        '<form method="POST" action="/turnitin"><input name="file_artikel" class="form-control is-invalid">'
        '<div class="invalid-feedback">Link naskah harus berupa URL yang valid.</div></form>'
        '<div class="modal" id="m"><div class="alert alert-warning">Catatan milik modal</div></div>'
    )

    assert baca_halaman_turnitin(html).flash == [
        {"jenis": "danger", "teks": "Pengajuan gagal disimpan."},
        {"jenis": "danger", "teks": "Link naskah harus berupa URL yang valid."},
    ]


def test_kolom_aksi_dicatat_apa_adanya():
    """Tautan unduh, pemicu modal, dan teks modalnya tercatat tanpa ditafsirkan."""
    riwayat = [
        baris_riwayat_turnitin("Naskah Selesai Karangan", "01/09/2026 10:00", "001/LPPM/IX/2026", "Selesai",
                               AKSI_UNDUH),
        baris_riwayat_turnitin("Naskah Perlu Diperbaiki", "02/09/2026 11:30", "-", "Perbaikan", AKSI_PERBAIKAN,
                               MODAL_PERBAIKAN),
    ]
    status = baca_halaman_turnitin(halaman_turnitin(riwayat, 2, 2), URL_TURNITIN)

    selesai, perbaikan = status.riwayat
    assert selesai.no_surat == "001/LPPM/IX/2026"
    assert selesai.aksi_teks == "Unduh Surat Laporan"
    assert selesai.aksi_tautan == [
        {"teks": "Unduh Surat", "href": f"{PORTAL}/turnitin/7/surat", "url": f"{PORTAL}/turnitin/7/surat"},
        {"teks": "Laporan", "href": "https://drive.google.com/file/d/laporan-karangan/view",
         "url": "https://drive.google.com/file/d/laporan-karangan/view"},
    ]
    assert selesai.ada_modal_perbaikan is False

    assert perbaikan.aksi_teks == "Form Perbaikan"
    assert perbaikan.aksi_tautan == []
    [pemicu] = perbaikan.aksi_pemicu
    assert pemicu["tag"] == "button"
    assert pemicu["atribut"] == {"data-toggle": "modal", "data-target": "#perbaikan8"}
    assert "Catatan LPPM: similarity 35%, perbaiki bab 2." in pemicu["teks_modal"]
    assert TOKEN_UJI not in pemicu["teks_modal"]
    assert "×" not in pemicu["teks_modal"] and "Tutup" not in pemicu["teks_modal"]
    assert perbaikan.ada_modal_perbaikan is True


def test_isi_modal_tidak_menjadi_flash_atau_form_pengajuan():
    """Modal yang muncul sebelum form pun (dengan isian judul_naskah sendiri) tidak tertukar."""
    html = halaman_turnitin([], 1, 2).replace('<div class="container my-4">',
                                              '<div class="container my-4">' + MODAL_PERBAIKAN)

    assert baca_halaman_turnitin(html).flash == []
    assert baca_halaman_turnitin(html).ada_form is True
    assert baca_form_pengajuan(html, URL_TURNITIN).action == URL_TURNITIN


def test_pemicu_modal_lain_tidak_dianggap_perbaikan():
    riwayat = [baris_riwayat_turnitin("Naskah Lain", "03/09/2026 08:00", "-", "Proses", AKSI_CATATAN, MODAL_CATATAN)]

    [baris] = baca_halaman_turnitin(halaman_turnitin(riwayat, 1, 2), URL_TURNITIN).riwayat
    assert baris.aksi_tautan == [{"teks": "Lihat catatan", "href": "#catatan9", "url": ""}]
    assert baris.aksi_pemicu[0]["atribut"] == {"data-toggle": "modal"}
    assert baris.aksi_pemicu[0]["teks_modal"] == "Catatan Reviewer: lengkap."
    assert baris.ada_modal_perbaikan is False


def test_baris_kosong_bercolspan_dilewati():
    html = halaman_turnitin([], 0, 2).replace(
        "<tbody>", '<tbody><tr><td colspan="6" class="text-center">Belum ada pengajuan</td></tr>'
    )

    assert baca_halaman_turnitin(html).riwayat == []


@pytest.mark.parametrize(
    "teks, iso",
    [
        ("20/10/2026 15:15", "2026-10-20T15:15"),
        ("20/10/2026 15:15:09", "2026-10-20T15:15:09"),
        ("2026-10-20 15:15:09", "2026-10-20T15:15:09"),
        ("20/10/2026", "2026-10-20"),
        ("kemarin sore", None),
    ],
)
def test_tanggal_submit_menjadi_iso(teks, iso):
    assert tanggal_iso(teks) == iso


# --- pemeriksaan isian ---------------------------------------------------------


@pytest.mark.parametrize(
    "tautan",
    [
        "https://drive.google.com/file/d/abc/view?usp=sharing",
        "https://docs.google.com/document/d/abc/edit",
        "  https://DRIVE.google.com/file/d/abc/view  ",
    ],
)
def test_tautan_google_drive_dan_docs_diterima(tautan):
    assert periksa_tautan(tautan) == tautan.strip()


@pytest.mark.parametrize(
    "tautan",
    [
        "http://drive.google.com/file/d/abc/view",  # tanpa TLS
        "https://contoh-lain.id/file/d/abc",  # host lain
        "https://drive.google.com.contoh-lain.id/file/d/abc",  # menyaru lewat subdomain
        "https://drive.google.com@contoh-lain.id/file/d/abc",  # menyaru lewat userinfo
        "https://drive.google.com:8443/file/d/abc",  # port lain
        "https://drive.google.com/",  # tanpa berkas
        "drive.google.com/file/d/abc",  # tanpa skema
        "https://drive.google.com/file/d/abc def",  # ada spasi
        "",
    ],
)
def test_tautan_tidak_sah_ditolak_sebelum_menghubungi_portal(klien, situs, tautan):
    with pytest.raises(PengajuanDitolak, match="Tautan naskah harus https"):
        ajukan_turnitin(klien, JUDUL_BARU, tautan)
    assert situs.permintaan == []


def test_judul_kosong_ditolak_sebelum_menghubungi_portal(klien, situs):
    with pytest.raises(PengajuanDitolak, match="Judul naskah tidak boleh kosong"):
        ajukan_turnitin(klien, "   ", TAUTAN_NASKAH_UJI)
    assert situs.permintaan == []


# --- membaca lewat klien -------------------------------------------------------


def test_daftar_turnitin_login_lalu_membaca(klien, situs):
    status = daftar_turnitin(klien)

    assert [(satu["metode"], satu["path"]) for satu in situs.permintaan] == [
        ("GET", "/login"),
        ("POST", "/login"),
        ("GET", "/home"),
        ("GET", "/turnitin"),
    ]
    assert status.url == URL_TURNITIN
    assert (status.jatah.dipakai, status.jatah.sisa) == (1, 1)
    assert [baris.judul for baris in status.riwayat] == [JUDUL_TURNITIN_UJI]


def test_riwayat_berpaginasi_dibaca_semua_dan_ikut_diperiksa(klien, situs):
    situs.turnitin_total, situs.turnitin_dipakai = 3, 2
    situs.turnitin_lanjutan = {
        "2": halaman_turnitin([baris_riwayat_turnitin("Judul Lama di Halaman Dua", "01/02/2026 09:00")], 2, 3),
    }

    assert [baris.judul for baris in daftar_turnitin(klien).riwayat] == [
        JUDUL_TURNITIN_UJI,
        "Judul Lama di Halaman Dua",
    ]
    with pytest.raises(PengajuanDitolak, match="sudah ada di riwayat"):
        ajukan_turnitin(klien, "judul lama di halaman dua", TAUTAN_NASKAH_UJI)


# --- uji coba dan penolakan -----------------------------------------------------


def test_uji_coba_mengembalikan_rencana_tanpa_mengirim(klien, situs):
    hasil = ajukan_turnitin(klien, f"  {JUDUL_BARU}  ", TAUTAN_NASKAH_UJI)

    assert hasil.uji_coba is True
    assert hasil.terkirim is False and hasil.diterima is False
    assert (hasil.metode, hasil.action) == ("POST", URL_TURNITIN)
    assert hasil.isian == {"judul_naskah": JUDUL_BARU, "file_artikel": TAUTAN_NASKAH_UJI}
    assert (hasil.jatah.dipakai, hasil.jatah.total, hasil.jatah.sisa) == (1, 2, 1)
    assert "Uji coba" in hasil.pesan
    assert TOKEN_UJI not in json.dumps(hasil.sebagai_dict())
    assert jumlah_kiriman(situs) == 0


def test_judul_kembar_ditolak_tanpa_peka_huruf_dan_spasi(klien, situs):
    with pytest.raises(PengajuanDitolak, match="sudah ada di riwayat"):
        ajukan_turnitin(klien, "  kerangka KERJA   fiktif untuk  kota gotham ", TAUTAN_NASKAH_UJI, uji_coba=False)
    assert jumlah_kiriman(situs) == 0


def test_paksa_melewati_pemeriksaan_judul_kembar(klien, situs):
    hasil = ajukan_turnitin(klien, JUDUL_TURNITIN_UJI, TAUTAN_NASKAH_UJI, paksa=True)

    assert hasil.uji_coba is True
    assert hasil.isian["judul_naskah"] == JUDUL_TURNITIN_UJI
    assert jumlah_kiriman(situs) == 0


@pytest.mark.parametrize("paksa", [False, True])
def test_jatah_habis_ditolak_walau_dipaksa(klien, situs, paksa):
    situs.turnitin_riwayat.append(baris_riwayat_turnitin("Naskah Kedua Karangan", "20/10/2026 15:40"))

    with pytest.raises(PengajuanDitolak, match=r"sudah habis \(2 dari 2 terpakai\)"):
        ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False, paksa=paksa)
    assert jumlah_kiriman(situs) == 0


def test_riwayat_tidak_terbaca_padahal_jatah_terpakai(klien, situs):
    """Tanpa riwayat, judul kembar tidak bisa diperiksa; hanya paksa yang meneruskan."""
    situs.turnitin_riwayat, situs.turnitin_dipakai = [], 1

    with pytest.raises(LppmError, match="Riwayat pengajuan tidak terbaca"):
        ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI)
    assert ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, paksa=True).uji_coba is True


def test_jatah_tidak_terbaca_tidak_dikirim(klien, situs):
    situs.turnitin_html = HALAMAN_TURNITIN_CONTOH.replace("1 dari 2 jatah digunakan", "jatah sedang dihitung")

    with pytest.raises(LppmError, match="Jatah pengajuan tidak terbaca"):
        ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)
    assert jumlah_kiriman(situs) == 0


def test_form_yang_hilang_dilaporkan(klien, situs):
    awal, akhir = HALAMAN_TURNITIN_CONTOH.index("<form"), HALAMAN_TURNITIN_CONTOH.index("</form>") + len("</form>")
    situs.turnitin_html = HALAMAN_TURNITIN_CONTOH[:awal] + HALAMAN_TURNITIN_CONTOH[akhir:]

    with pytest.raises(LppmError, match="Form pengajuan Turnitin tidak ada"):
        ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)
    assert jumlah_kiriman(situs) == 0


def test_form_dengan_isian_asing_tidak_dikirim(klien, situs):
    """Isian baru di form berarti halamannya berubah; uji coba pun melaporkannya."""
    situs.turnitin_html = HALAMAN_TURNITIN_CONTOH.replace(
        '<button type="submit"',
        '<select name="jenis_naskah"><option value="jurnal">Jurnal</option></select><button type="submit"',
    )

    with pytest.raises(LppmError, match=r"belum dikenal \(jenis_naskah\)"):
        ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI)
    assert jumlah_kiriman(situs) == 0


def test_form_yang_dikirim_ke_path_lain_ditolak(klien, situs):
    situs.turnitin_html = HALAMAN_TURNITIN_CONTOH.replace(
        'action="https://lppm.pradita.ac.id/turnitin"', 'action="https://lppm.pradita.ac.id/turnitin/simpan"'
    )

    with pytest.raises(AlamatDitolak, match="bukan tujuan kiriman yang diizinkan"):
        ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)
    assert situs.jumlah("POST", "/turnitin/simpan") == 0


# --- kiriman sungguhan -----------------------------------------------------------


def test_kirim_mengirim_sekali_lalu_membaca_hasilnya(klien, situs):
    hasil = ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)

    [kiriman] = [satu for satu in situs.permintaan if satu["metode"] == "POST" and satu["path"] == "/turnitin"]
    assert kiriman["url"] == URL_TURNITIN
    assert kiriman["data"] == {"_token": TOKEN_UJI, "judul_naskah": JUDUL_BARU, "file_artikel": TAUTAN_NASKAH_UJI}
    assert hasil.terkirim is True and hasil.diterima is True and hasil.uji_coba is False
    assert hasil.flash == [{"jenis": "success", "teks": "Pengajuan Cek Turnitin berhasil dikirim."}]
    assert (hasil.jatah.dipakai, hasil.jatah.total, hasil.jatah.sisa) == (2, 2, 0)
    assert hasil.baris_baru.judul == JUDUL_BARU
    assert hasil.baris_baru.no == 2
    assert hasil.baris_baru.tanggal_submit == "2026-10-20T16:05"
    assert hasil.baris_baru.status == "Submit"
    assert hasil.baris_baru.no_surat is None
    assert TOKEN_UJI not in json.dumps(hasil.sebagai_dict())


def test_kiriman_yang_ditolak_validasi_portal_tidak_dianggap_diterima(klien, situs):
    situs.turnitin_galat_validasi = "Link naskah harus dapat dibuka LPPM."

    hasil = ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)

    assert hasil.terkirim is True and hasil.diterima is False
    assert hasil.baris_baru is None
    assert hasil.flash == [{"jenis": "danger", "teks": "Link naskah harus dapat dibuka LPPM."}]
    assert hasil.pesan == PESAN_BELUM_TERLIHAT
    assert hasil.jatah.sisa == 1
    assert jumlah_kiriman(situs) == 1


def riwayat_karangan(*baris: tuple[str, str]) -> list:
    """Baris riwayat hasil pembaca halaman, dari pasangan (judul, tanggal) karangan."""
    html = halaman_turnitin([baris_riwayat_turnitin(judul, tanggal) for judul, tanggal in baris], len(baris), 3)
    return baca_halaman_turnitin(html, URL_TURNITIN).riwayat


def test_baris_baru_dicari_dari_selisih_riwayat():
    lama = (JUDUL_TURNITIN_UJI, "20/10/2026 15:15")
    sebelum = riwayat_karangan(lama)
    sama_judul = riwayat_karangan(lama, (JUDUL_TURNITIN_UJI, "20/10/2026 16:05"))
    dipendekkan = riwayat_karangan(lama, (JUDUL_BARU[:20] + "...", "20/10/2026 16:05"))

    # judul kembar yang dipaksa: baris lama tidak terhitung sebagai baris baru
    assert cari_baris_baru(sebelum, sama_judul, JUDUL_TURNITIN_UJI).tanggal_submit_teks == "20/10/2026 16:05"
    # judul yang dipendekkan portal: satu-satunya baris baru yang dipakai
    assert cari_baris_baru(sebelum, dipendekkan, JUDUL_BARU).judul == JUDUL_BARU[:20] + "..."
    assert cari_baris_baru(sebelum, sebelum, JUDUL_BARU) is None


@pytest.mark.parametrize(
    "balasan",
    [
        JawabanTiruan(URL_TURNITIN, 419, teks="Page Expired"),  # token basi
        JawabanTiruan(URL_TURNITIN, 500, teks="Server Error"),
        JawabanTiruan(URL_TURNITIN, 302, lokasi="https://siakad.pradita.ac.id/dashboard"),  # host lain
        JawabanTiruan(URL_TURNITIN, 307, lokasi=f"{PORTAL}/turnitin/simpan"),  # minta POST diulang
    ],
)
def test_hasil_tidak_pasti_tidak_pernah_dikirim_ulang(klien, situs, balasan):
    situs.turnitin_balasan = balasan

    with pytest.raises(HasilTidakPasti, match="Periksa riwayat"):
        ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)
    assert [satu["path"] for satu in situs.permintaan if satu["metode"] == "POST"] == ["/login", "/turnitin"]
    assert all(satu["url"].startswith(PORTAL) for satu in situs.permintaan)


def test_sesi_habis_saat_kirim_tidak_login_ulang_lalu_mengirim_lagi(klien, situs):
    situs.turnitin_sesi_habis = True

    with pytest.raises(HasilTidakPasti, match="sesi atau token CSRF-nya tidak berlaku"):
        ajukan_turnitin(klien, JUDUL_BARU, TAUTAN_NASKAH_UJI, uji_coba=False)
    assert jumlah_kiriman(situs) == 1
    assert situs.jumlah("POST", "/login") == 1
    assert klien.sudah_login is False


# --- penjaga POST di klien --------------------------------------------------------


@pytest.mark.parametrize(
    "alamat",
    [
        "/penelitian/create",
        "/turnitin/7/hapus",
        "/turnitin/",
        "/turnitin?aksi=1",
        "/login",
        "https://siakad.pradita.ac.id/turnitin",
        "http://lppm.pradita.ac.id/turnitin",
    ],
)
def test_kirim_form_hanya_ke_path_yang_diizinkan(klien, situs, alamat):
    with pytest.raises(AlamatDitolak):
        klien.kirim_form(alamat, {"judul_naskah": JUDUL_BARU})
    assert situs.permintaan == []


def test_kirim_form_butuh_login_lebih_dulu(klien, situs):
    """Token CSRF hanya berlaku untuk sesi tempat form-nya dibaca, jadi klien tidak login sendiri di sini."""
    with pytest.raises(LppmError, match="Belum login"):
        klien.kirim_form("/turnitin", {"_token": TOKEN_UJI})
    assert situs.permintaan == []


def test_penjaga_baca_saja_untuk_get_tidak_dilonggarkan(klien, situs):
    assert PATH_POST_DIIZINKAN == frozenset({"/turnitin"})
    assert {"submit", "kirim", "ajukan"} <= KATA_AKSI
    for alamat in ("/turnitin/ajukan", "/turnitin/7/kirim", "/turnitin?aksi=submit"):
        with pytest.raises(AlamatDitolak, match="hanya membaca"):
            klien.ambil_halaman(alamat)
    assert situs.permintaan == []
