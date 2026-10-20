"""Perintah baris perintah LPPM.

    lppm-cek-login   cek kredensial di setelan (.env) bisa dipakai login
    lppm-menu        menu navigasi portal setelah login
    lppm-halaman     isi satu halaman portal sebagai teks atau tabel
    lppm-turnitin    jatah dan riwayat cek Turnitin, serta pengajuan baru

Dari klona repositori, semuanya dipanggil lewat peluncur: `./lppm cek-login`,
`./lppm menu`, `./lppm halaman <path>`, dan `./lppm turnitin`. Kredensial selalu
dibaca dari setelan dan tidak pernah dicetak. Semua perintah hanya membaca
portal, kecuali `lppm-turnitin ajukan --kirim`.

Pakai:
    lppm-cek-login
    lppm-menu --json
    lppm-halaman /infolppm/profil
    lppm-halaman <path> --tabel
    lppm-turnitin
    lppm-turnitin ajukan --judul "..." --tautan https://drive.google.com/...   # uji coba
    lppm-turnitin ajukan --judul "..." --tautan ... --kirim                   # mengirim
"""

from __future__ import annotations

import argparse
import json
import sys

from lppm_mcp.halaman import isi_halaman
from lppm_mcp.konfigurasi import KonfigurasiError
from lppm_mcp.lppm_client import KlienLppm, LppmError
from lppm_mcp.turnitin import (
    BarisTurnitin,
    HasilPengajuan,
    JatahTurnitin,
    StatusTurnitin,
    ajukan_turnitin,
    daftar_turnitin,
)


def cetak_json(data) -> int:
    """Keluaran untuk dipipa ke perkakas lain."""
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def jalankan_aman(perintah) -> int:
    """Jalankan satu perintah CLI dengan penanganan kesalahan yang seragam.

    Kesalahan pustaka dicetak sebagai satu baris pesan di stderr dengan kode
    keluar 1, supaya pemakai CLI langsung tahu apa yang perlu dibetulkan.
    """
    try:
        return perintah()
    except (LppmError, KonfigurasiError) as galat:
        print(f"Gagal: {galat}", file=sys.stderr)
        return 1


def label_menu(satu: dict) -> str:
    """'Penelitian > Usulan Baru' untuk submenu, nama saja untuk menu tingkat atas."""
    return f"{satu['grup']} > {satu['nama']}" if satu["grup"] else satu["nama"]


def cetak_tabel(isi: dict) -> None:
    """Tabel halaman sebagai teks: sel dipisah " | ", tautan baris di bawahnya."""
    if not isi["tabel"]:
        print("Tidak ada tabel di halaman ini.")
    for tabel in isi["tabel"]:
        print(f"[Tabel {tabel['nomor']}] {tabel['judul']}  ({tabel['jumlah_baris']} baris)")
        if tabel["kolom"]:
            print("  " + " | ".join(tabel["kolom"]))
        for baris in tabel["baris"]:
            print("  " + " | ".join(nilai for kunci, nilai in baris.items() if kunci != "_tautan"))
            for tautan in baris.get("_tautan", []):
                print(f"      -> {tautan['teks'] or '(tanpa teks)'}: {tautan['url']}")
        print()
    if isi.get("catatan"):
        print(isi["catatan"])


def ringkas_jatah(jatah: JatahTurnitin | None) -> str:
    """'1 dari 2 terpakai, sisa 1', atau keterangan bahwa kotak jatahnya tidak terbaca."""
    if jatah is None:
        return "tidak terbaca di halaman"
    return f"{jatah.dipakai} dari {jatah.total} terpakai, sisa {jatah.sisa}"


def cetak_flash(flash: list[dict]) -> None:
    """Pesan flash portal, satu per baris, dengan jenisnya di depan."""
    for pesan in flash:
        print(f"[{pesan['jenis']}] {pesan['teks']}")


def cetak_baris_turnitin(baris: BarisTurnitin) -> None:
    """Satu baris riwayat dengan sel dipisah " | ", lalu tautan dan pemicu di kolom Aksi."""
    sel = [
        str(baris.no) if baris.no is not None else "-",
        baris.judul,
        baris.tanggal_submit_teks or "-",
        baris.no_surat or "-",
        baris.status or "-",
        baris.aksi_teks or "-",
    ]
    print("  " + " | ".join(sel))
    for tautan in baris.aksi_tautan:
        print(f"      -> {tautan['teks'] or '(tanpa teks)'}: {tautan['url'] or tautan['href']}")
    for pemicu in baris.aksi_pemicu:
        atribut = " ".join(f'{nama}="{nilai}"' for nama, nilai in pemicu["atribut"].items())
        print(f"      <{pemicu['tag']} {atribut}> {pemicu['teks']}".rstrip())
        if pemicu["teks_modal"]:
            print(f"        modal: {pemicu['teks_modal']}")


def cetak_status_turnitin(status: StatusTurnitin) -> None:
    """Jatah, pesan flash, dan riwayat pengajuan sebagai teks."""
    print(f"Jatah cek Turnitin: {ringkas_jatah(status.jatah)}")
    print(f"{status.url}\n")
    cetak_flash(status.flash)
    if not status.riwayat:
        print("Belum ada riwayat pengajuan.")
        return
    print(f"Riwayat ({len(status.riwayat)}):")
    print("  No | Judul Naskah | Tanggal Submit | No. Surat | Status | Aksi")
    for baris in status.riwayat:
        cetak_baris_turnitin(baris)


def cetak_hasil_pengajuan(hasil: HasilPengajuan) -> None:
    """Rencana kiriman (uji coba) atau hasil kiriman sungguhan sebagai teks."""
    print(hasil.pesan)
    print(f"Jatah: {ringkas_jatah(hasil.jatah)}\n")
    print(f"{hasil.metode} {hasil.action}")
    lebar = max(len(nama) for nama in hasil.isian)
    for nama, nilai in hasil.isian.items():
        print(f"  {nama:<{lebar}}  {nilai}")
    if hasil.uji_coba:
        print("\nTidak ada yang dikirim. Tambahkan --kirim untuk mengajukan sungguhan (memakai 1 jatah).")
        return
    print()
    cetak_flash(hasil.flash)
    if hasil.baris_baru is not None:
        print("Baris baru di riwayat:")
        cetak_baris_turnitin(hasil.baris_baru)


def main_cek_login(argumen_baris: list[str] | None = None) -> int:
    """Login dengan kredensial dari setelan, lalu laporkan berandanya."""
    argparse.ArgumentParser(
        description="Cek kredensial LPPM di setelan (.env) bisa dipakai login."
    ).parse_args(argumen_baris)
    klien = KlienLppm().login()
    print(f"Login LPPM OK, beranda: {klien.url_beranda}")
    return 0


def main_menu(argumen_baris: list[str] | None = None) -> int:
    """Cetak menu navigasi portal yang terlihat setelah login."""
    pengurai = argparse.ArgumentParser(description="Menu navigasi portal LPPM setelah login.")
    pengurai.add_argument("--json", action="store_true", help="Cetak JSON, bukan daftar")
    argumen = pengurai.parse_args(argumen_baris)

    klien = KlienLppm()
    menu = klien.daftar_navigasi()
    if argumen.json:
        return cetak_json(menu)
    if not menu:
        print("Tidak ada tautan menu di beranda.")
        return 1

    print(f"{len(menu)} tautan menu, dibaca dari {klien.url_beranda}\n")
    lebar = max(len(label_menu(satu)) for satu in menu)
    for satu in menu:
        print(f"  {label_menu(satu):<{lebar}}  {satu['path']}")
    return 0


def main_halaman(argumen_baris: list[str] | None = None) -> int:
    """Cetak isi satu halaman portal sebagai teks, atau tabel-tabelnya."""
    pengurai = argparse.ArgumentParser(
        description="Isi satu halaman portal LPPM sebagai teks atau tabel. Hanya membaca."
    )
    pengurai.add_argument("path", help="Path atau URL penuh di bawah portal LPPM, mis. /infolppm/profil")
    pengurai.add_argument("--tabel", action="store_true", help="Tampilkan tabelnya, bukan teks")
    pengurai.add_argument("--maks", type=int, default=0, metavar="N",
                          help="Potong keluaran sepanjang N karakter; 0 berarti utuh")
    pengurai.add_argument("--json", action="store_true", help="Cetak JSON")
    argumen = pengurai.parse_args(argumen_baris)

    halaman = KlienLppm().ambil_halaman(argumen.path)
    isi = isi_halaman(halaman, "tabel" if argumen.tabel else "teks", argumen.maks)
    if argumen.json:
        return cetak_json(isi)

    print(f"{isi['judul']}\n{isi['url']}\n")
    if argumen.tabel:
        cetak_tabel(isi)
    else:
        print(isi["teks"])
    if isi["terpotong"]:
        print("\n(terpotong; naikkan --maks untuk melihat semuanya)")
    return 0


def pengurai_turnitin() -> argparse.ArgumentParser:
    """Argumen `lppm-turnitin` beserta sub-perintah `ajukan`."""
    pengurai = argparse.ArgumentParser(
        description="Jatah dan riwayat pengajuan cek Turnitin di portal LPPM. Tanpa sub-perintah hanya membaca."
    )
    pengurai.add_argument("--json", action="store_true", help="Cetak JSON")
    sub_perintah = pengurai.add_subparsers(dest="aksi", metavar="ajukan")
    ajukan = sub_perintah.add_parser(
        "ajukan",
        help="ajukan satu naskah; tanpa --kirim hanya uji coba",
        description=(
            "Ajukan satu naskah untuk dicek Turnitin. Tanpa --kirim hanya uji coba: isian dan jatah "
            "diperiksa, lalu rencana kirimannya dicetak tanpa mengirim apa pun."
        ),
    )
    ajukan.add_argument("--judul", required=True, help="Judul naskah")
    ajukan.add_argument("--tautan", required=True,
                        help="Tautan Google Drive naskah: https://drive.google.com/... atau https://docs.google.com/...")
    ajukan.add_argument("--kirim", action="store_true",
                        help="Benar-benar mengirim dan memakai satu jatah; tanpa ini hanya uji coba")
    ajukan.add_argument("--paksa", action="store_true",
                        help="Tetap ajukan walau judul yang sama sudah ada di riwayat")
    # SUPPRESS supaya `--json` sebelum `ajukan` tidak tertimpa nilai bawaan sub-perintah
    ajukan.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Cetak JSON")
    return pengurai


def main_turnitin(argumen_baris: list[str] | None = None) -> int:
    """Cetak jatah dan riwayat cek Turnitin, atau ajukan satu naskah (`ajukan`).

    Pengajuan tanpa --kirim hanya uji coba. Kode keluar 1 kalau kiriman sungguhan
    tidak terlihat di riwayat sesudahnya.
    """
    argumen = pengurai_turnitin().parse_args(argumen_baris)
    klien = KlienLppm()
    if argumen.aksi != "ajukan":
        status = daftar_turnitin(klien)
        if argumen.json:
            return cetak_json(status.sebagai_dict())
        cetak_status_turnitin(status)
        return 0

    hasil = ajukan_turnitin(klien, argumen.judul, argumen.tautan, uji_coba=not argumen.kirim, paksa=argumen.paksa)
    if argumen.json:
        cetak_json(hasil.sebagai_dict())
    else:
        cetak_hasil_pengajuan(hasil)
    return 0 if hasil.uji_coba or hasil.diterima else 1


def jalankan_cek_login() -> int:
    """Titik masuk perintah `lppm-cek-login`."""
    return jalankan_aman(main_cek_login)


def jalankan_menu() -> int:
    """Titik masuk perintah `lppm-menu`."""
    return jalankan_aman(main_menu)


def jalankan_halaman() -> int:
    """Titik masuk perintah `lppm-halaman`."""
    return jalankan_aman(main_halaman)


def jalankan_turnitin() -> int:
    """Titik masuk perintah `lppm-turnitin`."""
    return jalankan_aman(main_turnitin)


if __name__ == "__main__":
    sys.exit(jalankan_halaman())
