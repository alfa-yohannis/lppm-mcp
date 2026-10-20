# Contoh LPPM

Contoh siap jalan untuk ketiga mode. Semuanya butuh Python 3.10+ dan kredensial
portal LPPM di `.env` (salin dari `.env.contoh`).

| Berkas           | Mode     | Isi                                              |
|------------------|----------|--------------------------------------------------|
| `prompt_mcp.md`  | MCP      | prompt siap salin untuk asisten AI               |
| `mcp_klien.json` | MCP      | konfigurasi server untuk klien MCP selain Claude |
| `klien_api.sh`   | REST API | memakai REST API dari `curl`                     |
| `api_sendiri.py` | REST API | menempel router ke aplikasi FastAPI sendiri      |
| `pustaka.py`     | Pustaka  | memakai `lppm_mcp` dari program Python sendiri   |

## 1. MCP

```bash
claude mcp add lppm-mcp -- /path/ke/lppm-mcp/lppm mcp
```

Lalu minta asisten Anda:

> Cek apakah login portal LPPM saya jalan, lalu tampilkan menu yang tersedia.

Prompt lain di [prompt_mcp.md](prompt_mcp.md). Untuk klien MCP selain Claude
Code, pakai [mcp_klien.json](mcp_klien.json).

## 2. REST API

```bash
./lppm api                 # terminal pertama
examples/klien_api.sh      # terminal kedua; kredensial dari .env server
```

Untuk menempelkan rutenya ke aplikasi FastAPI Anda sendiri:

```bash
.venv/bin/uvicorn examples.api_sendiri:app --port 8000
```

Buka <http://localhost:8000/docs>; rute `/lppm/...` muncul berdampingan dengan
rute milik aplikasi contoh itu sendiri.

## 3. Pustaka

```bash
.venv/bin/python examples/pustaka.py
```

Mencetak menu navigasi setelah login, lalu isi halaman profil LPPM.

## Lewat CLI

```bash
./lppm cek-login
./lppm menu
./lppm halaman /infolppm/profil
./lppm turnitin
```
