"""Petakan halaman portal LPPM: form, field, tabel, tautan, dan endpoint AJAX-nya.

Dipakai saat menyiapkan kemampuan baru (lihat README, bagian Rencana). Halaman
Laravel sering memuat tabelnya lewat AJAX (DataTables), jadi endpoint yang
dipanggil skripnya ikut didaftar. Perintah ini hanya melakukan GET dan tidak
pernah mengirim form. Nilai token CSRF dan isian password tidak ikut dicatat.

Pakai:
    ./lppm petakan /infolppm/profil
    ./lppm petakan <path> --semua-opsi
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from bs4 import BeautifulSoup

from lppm_mcp.halaman import Halaman, rapikan, tautan_isi
from lppm_mcp.konfigurasi import KonfigurasiError, simpan_ke_data
from lppm_mcp.lppm_client import KlienLppm, LppmError

MAKS_OPSI_TAMPIL = 12
MAKS_CETAK_KARAKTER = 6000
POLA_AJAX = re.compile(r"""(?:url|ajax)\s*:\s*[`'"]([^`'"]+)[`'"]""")
# nilai isian ini tidak pernah ditulis ke layar maupun ke data/
NAMA_DISAMARKAN = {"_token", "password", "password_confirmation", "current_password"}


def nilai_aman(field) -> str:
    """Nilai sebuah isian; token CSRF dan password disamarkan."""
    nama = field.get("name") or ""
    jenis = (field.get("type") or "").lower()
    nilai = field.get("value") or ""
    if nilai and (nama in NAMA_DISAMARKAN or jenis == "password"):
        return "<disamarkan>"
    return nilai


def label_field(form, field) -> str:
    """Teks <label for=...> milik sebuah isian, kalau ada di form yang sama."""
    if not field.get("id"):
        return ""
    label = form.find("label", attrs={"for": field["id"]})
    return rapikan(label.get_text(" ")) if label is not None else ""


def ringkas_field(form, field, *, semua_opsi: bool) -> dict:
    """Ringkas satu <input>/<select>/<textarea> jadi dict yang enak dibaca."""
    ringkasan = {
        "tag": field.name,
        "name": field.get("name"),
        "id": field.get("id"),
        "label": label_field(form, field),
        "type": field.get("type", "select" if field.name == "select" else field.name),
        "value": nilai_aman(field),
        "wajib": field.has_attr("required"),
    }
    if field.name == "select":
        opsi = [
            {"value": pilihan.get("value", ""), "label": rapikan(pilihan.get_text(" "))}
            for pilihan in field.find_all("option")
        ]
        ringkasan["jumlah_opsi"] = len(opsi)
        ringkasan["opsi"] = opsi if semua_opsi else opsi[:MAKS_OPSI_TAMPIL]
    return ringkasan


def ringkas_form(form, *, semua_opsi: bool) -> dict:
    """Ringkas satu <form> beserta seluruh field-nya."""
    field = form.find_all(["input", "select", "textarea"])
    return {
        "id": form.get("id"),
        "action": form.get("action", ""),
        "method": (form.get("method") or "get").upper(),
        "enctype": form.get("enctype", ""),
        "jumlah_field": len(field),
        "field": [ringkas_field(form, satu, semua_opsi=semua_opsi) for satu in field if satu.get("name")],
    }


def petakan_halaman(halaman: Halaman, *, semua_opsi: bool = False) -> dict:
    """Struktur sebuah halaman: form, tabel, tautan di bagian isi, dan endpoint AJAX."""
    sup = BeautifulSoup(halaman.html, "lxml")
    return {
        "url": halaman.url,
        "status": halaman.status,
        "judul": halaman.judul(),
        "form": [ringkas_form(form, semua_opsi=semua_opsi) for form in sup.find_all("form")],
        "tabel": [
            {"nomor": tabel["nomor"], "judul": tabel["judul"], "kolom": tabel["kolom"],
             "jumlah_baris": tabel["jumlah_baris"]}
            for tabel in halaman.tabel()
        ],
        "tautan_isi": tautan_isi(halaman.html, halaman.url),
        # tabel yang kosong biasanya berarti isinya datang dari endpoint di bawah ini
        "endpoint_ajax": sorted(set(POLA_AJAX.findall(halaman.html))),
        "datatables": "datatable(" in halaman.html.lower(),
    }


def nama_berkas_peta(path: str) -> str:
    """'/penelitian/create?x=1' -> 'form_penelitian_create_x_1.json'."""
    nama = re.sub(r"[^A-Za-z0-9]+", "_", path.split("://")[-1]).strip("_") or "beranda"
    return f"form_{nama}.json"


def baca_argumen(argumen_baris: list[str] | None = None) -> argparse.Namespace:
    """Argumen baris perintah `lppm-petakan`."""
    pengurai = argparse.ArgumentParser(
        description="Petakan form, tabel, tautan, dan endpoint AJAX satu halaman portal LPPM. Hanya GET."
    )
    pengurai.add_argument("path", help="Path atau URL penuh di bawah portal LPPM")
    pengurai.add_argument("--semua-opsi", action="store_true", help="Tulis seluruh pilihan <select>, bukan 12 pertama")
    return pengurai.parse_args(argumen_baris)


def main(argumen_baris: list[str] | None = None) -> int:
    """Petakan satu halaman, cetak ringkasannya, lalu simpan ke data/form_<path>.json."""
    argumen = baca_argumen(argumen_baris)
    halaman = KlienLppm().ambil_halaman(argumen.path)
    peta = petakan_halaman(halaman, semua_opsi=argumen.semua_opsi)
    print(json.dumps(peta, ensure_ascii=False, indent=2)[:MAKS_CETAK_KARAKTER])
    print(f"\ntersimpan: {simpan_ke_data(nama_berkas_peta(argumen.path), peta)}")
    return 0


def jalankan() -> int:
    """Titik masuk perintah `lppm-petakan`."""
    try:
        return main()
    except (LppmError, KonfigurasiError) as galat:
        print(f"Gagal: {galat}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(jalankan())
