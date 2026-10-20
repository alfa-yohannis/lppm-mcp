#!/usr/bin/env bash
# Contoh memakai REST API LPPM dari baris perintah.
# Jalankan API-nya lebih dulu: ./lppm api
#
# Badan permintaan di sini tidak membawa kredensial, jadi server memakai
# LPPM_USERNAME/LPPM_PASSWORD dari .env-nya sendiri. Untuk mengirimnya per
# permintaan, tambahkan "username" dan "password" ke badan JSON.
#
#   examples/klien_api.sh

set -euo pipefail

API="${LPPM_API:-http://localhost:8000}"

echo "== cek kredensial"
curl -s -X POST "$API/sesi" -H 'Content-Type: application/json' -d '{}'

echo -e "\n\n== menu navigasi setelah login"
curl -s -X POST "$API/menu" -H 'Content-Type: application/json' -d '{}' |
	python3 -c '
import json, sys
for satu in json.load(sys.stdin)["data"]:
    grup = satu["grup"] + " > " if satu["grup"] else ""
    print("  ", grup + satu["nama"], " ", satu["path"])
'

echo -e "\n== isi halaman profil LPPM, 400 karakter pertama"
curl -s -X POST "$API/halaman" -H 'Content-Type: application/json' \
	-d '{"path": "/infolppm/profil", "maks_karakter": 400}' |
	python3 -c 'import json, sys; isi = json.load(sys.stdin); print("  ", isi["judul"]); print(isi["teks"])'
