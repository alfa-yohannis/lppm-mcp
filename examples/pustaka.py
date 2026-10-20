#!/usr/bin/env python3
"""Contoh memakai lppm-mcp sebagai pustaka dari program Python sendiri.

Isi kredensial di .env pada akar proyek (salin dari .env.contoh), lalu:

    .venv/bin/python examples/pustaka.py

Kredensial juga boleh diberikan dari kode lewat atur_setelan(), seperti
dicontohkan di bawah dalam keadaan dikomentari.
"""

from __future__ import annotations

import sys

from lppm_mcp import KlienLppm, KonfigurasiError, LppmError


def main() -> int:
    """Cetak menu navigasi setelah login, lalu isi halaman profil LPPM."""
    # Setelan dari kode, untuk aplikasi yang menyimpan konfigurasinya sendiri:
    # from lppm_mcp import atur_setelan
    # atur_setelan(LPPM_USERNAME="0000000000", LPPM_PASSWORD="...")

    try:
        klien = KlienLppm()  # belum menghubungi portal
        menu = klien.daftar_navigasi()  # login berjalan di sini
        halaman = klien.ambil_halaman("/infolppm/profil")
    except (LppmError, KonfigurasiError) as galat:
        print(f"Gagal: {galat}", file=sys.stderr)
        return 1

    print(f"Menu setelah login ({klien.url_beranda}):")
    for satu in menu:
        grup = f"{satu['grup']} > " if satu["grup"] else ""
        print(f"  {grup}{satu['nama']:<40} {satu['path']}")

    print(f"\n{halaman.judul()}\n")
    print(halaman.teks()[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
