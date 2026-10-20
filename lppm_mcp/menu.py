"""Dasar bersama untuk menu khusus portal LPPM: Turnitin, surat tugas, penelitian, PkM.

Baru MenuTurnitin (lppm_mcp/turnitin.py) yang memakainya. Menu lain bisa
ditulis setelah halamannya dipetakan (lihat README, bagian Rencana). Yang sudah
pasti sama untuk semua menu berbentuk daftar ditulis sekali di sini:

    path menunya, yang boleh dipindah lewat setelan tanpa menyunting kode
    baris tabel daftarnya, termasuk halaman lanjutan dari paginasi Laravel

Menu baru cukup mewarisi MenuLppm, menetapkan `path_bawaan` dan `kunci_path`,
lalu memetakan baris tabel ke dataclass miliknya sendiri:

    class DaftarPenelitian(MenuLppm):
        path_bawaan = "/penelitian"            # dugaan; pastikan dari ./lppm menu
        kunci_path = "LPPM_PATH_PENELITIAN"

Menu yang menulis ke portal mengikuti MenuTurnitin: method penulisnya menerima
`uji_coba` yang bawaannya True dan mengembalikan rencana kiriman tanpa
mengirimnya, lalu mengirim lewat `KlienLppm.kirim_form()`. Path tujuannya perlu
ditambahkan ke PATH_POST_DIIZINKAN di lppm_client.py lebih dulu.
"""

from __future__ import annotations

from lppm_mcp.halaman import Halaman, tautan_berikutnya
from lppm_mcp.konfigurasi import baca_pengaturan
from lppm_mcp.lppm_client import KlienLppm, LppmError


class MenuLppm:
    """Satu menu portal LPPM berbentuk daftar, untuk satu sesi login."""

    path_bawaan: str = ""
    kunci_path: str = ""
    # batas penelusuran paginasi, supaya tautan "next" yang berputar tidak membuat macet
    maks_halaman: int = 50

    def __init__(self, klien: KlienLppm):
        """Menu ini memakai sesi `klien`; login berjalan saat halaman pertama diminta."""
        self.klien = klien

    def path(self) -> str:
        """Path menu ini; portal lain bisa menaruhnya di alamat berbeda lewat setelan."""
        if self.kunci_path:
            return baca_pengaturan(self.kunci_path, self.path_bawaan)
        return self.path_bawaan

    def halaman(self) -> Halaman:
        """Halaman pertama menu ini."""
        if not self.path():
            raise LppmError(f"{type(self).__name__} belum menetapkan path_bawaan")
        return self.klien.ambil_halaman(self.path())

    def telusuri(self, halaman: Halaman) -> list[Halaman]:
        """`halaman` beserta halaman lanjutannya, mengikuti tautan rel="next" paginasi Laravel.

        Berhenti setelah `maks_halaman` halaman, atau saat tautan lanjutannya
        menunjuk halaman yang sudah dibaca.
        """
        semua, terlihat = [halaman], {halaman.url}
        while len(semua) < self.maks_halaman:
            lanjutan = tautan_berikutnya(halaman.html, halaman.url)
            if not lanjutan or lanjutan in terlihat:
                break
            terlihat.add(lanjutan)
            halaman = self.klien.ambil_halaman(lanjutan)
            semua.append(halaman)
        return semua

    def baris(self, nomor_tabel: int = 1) -> list[dict]:
        """Seluruh baris satu tabel daftar, halaman demi halaman mengikuti tautan rel="next".

        `nomor_tabel` dihitung dari 1, sama dengan `nomor` pada Halaman.tabel().
        Halaman yang tabelnya lebih sedikit dari itu dilewati tanpa galat.
        """
        semua: list[dict] = []
        for halaman in self.telusuri(self.halaman()):
            tabel = halaman.tabel()
            if len(tabel) >= nomor_tabel:
                semua.extend(tabel[nomor_tabel - 1]["baris"])
        return semua
