"""LPPM MCP: baca portal LPPM Pradita sebagai pustaka, CLI, REST API, atau MCP.

Tiga cara memakainya, semuanya dari paket yang sama:

    pustaka   from lppm_mcp import KlienLppm
              klien = KlienLppm()                        # kredensial dari .env
              print(klien.daftar_navigasi())             # login berjalan di sini
              print(klien.ambil_halaman("/infolppm/profil").teks())

    REST API  from lppm_mcp.api import router
              app_saya.include_router(router, prefix="/lppm")

    MCP       from lppm_mcp.mcp_server import server
              server.run()                               # atau lewat perintah `lppm-mcp`

Menu khusus situs mewarisi `MenuLppm`. Yang sudah ada baru Turnitin:

    from lppm_mcp import KlienLppm, ajukan_turnitin, daftar_turnitin
    status = daftar_turnitin(KlienLppm())                       # jatah dan riwayat
    rencana = ajukan_turnitin(KlienLppm(), judul, tautan)       # uji coba, tidak mengirim

Menu surat tugas, penelitian, dan PkM menyusul; lihat README bagian Rencana.

Setelan bisa diberikan tanpa berkas apa pun, berguna buat proyek yang menyimpan
konfigurasinya sendiri:

    from lppm_mcp import atur_setelan
    atur_setelan(LPPM_USERNAME="...", LPPM_PASSWORD="...")

Impor di sini sengaja hanya menyentuh modul inti. `lppm_mcp.api` butuh FastAPI
dan `lppm_mcp.mcp_server` butuh paket mcp, jadi keduanya diimpor sendiri oleh
yang memerlukan. Pemakai pustaka tidak dipaksa memasang keduanya.
"""

from __future__ import annotations

__version__ = "0.1.0"

from lppm_mcp.halaman import BENTUK_HALAMAN, Halaman, isi_halaman
from lppm_mcp.konfigurasi import (
    KonfigurasiError,
    akar_proyek,
    atur_akar_proyek,
    atur_setelan,
    baca_pengaturan,
)
from lppm_mcp.lppm_client import AlamatDitolak, KlienLppm, LoginDitolak, LppmError
from lppm_mcp.menu import MenuLppm
from lppm_mcp.turnitin import (
    BarisTurnitin,
    HasilPengajuan,
    HasilTidakPasti,
    JatahTurnitin,
    MenuTurnitin,
    PengajuanDitolak,
    StatusTurnitin,
    ajukan_turnitin,
    baca_halaman_turnitin,
    daftar_turnitin,
)

__all__ = [
    # sesi dan halaman
    "KlienLppm",
    "Halaman",
    "MenuLppm",
    "isi_halaman",
    "BENTUK_HALAMAN",
    # Turnitin
    "MenuTurnitin",
    "daftar_turnitin",
    "ajukan_turnitin",
    "baca_halaman_turnitin",
    "StatusTurnitin",
    "JatahTurnitin",
    "BarisTurnitin",
    "HasilPengajuan",
    # setelan
    "atur_setelan",
    "atur_akar_proyek",
    "baca_pengaturan",
    "akar_proyek",
    # kesalahan
    "LppmError",
    "LoginDitolak",
    "AlamatDitolak",
    "PengajuanDitolak",
    "HasilTidakPasti",
    "KonfigurasiError",
    "__version__",
]
