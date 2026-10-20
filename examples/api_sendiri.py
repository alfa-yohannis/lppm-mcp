#!/usr/bin/env python3
"""Contoh menempelkan REST API LPPM ke aplikasi FastAPI milik sendiri.

Rute paket ini dikumpulkan di `router`, jadi tidak harus dijalankan sebagai
server terpisah dan bisa hidup berdampingan dengan rute Anda sendiri.

    pip install "lppm-mcp[api] @ git+https://github.com/alfa-yohannis/lppm-mcp.git"
    uvicorn examples.api_sendiri:app --port 8000

Lalu buka http://localhost:8000/docs; rute /lppm/... muncul bersama /versi.
"""

from __future__ import annotations

from fastapi import FastAPI

from lppm_mcp import __version__
from lppm_mcp.api import router

# Kalau portal LPPM kampus Anda beralamat lain, tetapkan sekali di sini alih-alih
# menyediakan lppm.yaml. Setelan dari kode mengalahkan environment dan berkas.
# from lppm_mcp import atur_setelan
# atur_setelan(website="https://lppm.kampuslain.ac.id/login")

app = FastAPI(title="Aplikasi Saya", version="0.1.0")

# Prefix bebas; endpoint jadi /lppm/sesi, /lppm/menu, /lppm/halaman, dan /lppm/turnitin
app.include_router(router, prefix="/lppm", tags=["lppm"])


@app.get("/versi", summary="Rute milik aplikasi ini sendiri")
def versi() -> dict:
    """Versi aplikasi contoh dan versi lppm-mcp yang terpasang."""
    return {"aplikasi": "0.1.0", "lppm_mcp": __version__}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8000)
