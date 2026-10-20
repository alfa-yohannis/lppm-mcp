# Referensi REST API LPPM

## Menjalankan

### 1. Pasang

Butuh Python 3.10+.

```bash
pip install "lppm-mcp[api] @ git+https://github.com/alfa-yohannis/lppm-mcp.git"
```

### 2. Hidupkan servernya

```bash
uvicorn lppm_mcp.api:app --port 8000     # setelah pip install
./lppm api                               # dari klona; PORT=9001 untuk ganti port
```

### 3. Pastikan hidup

```bash
curl -s localhost:8000/openapi.json | head -c 80
```

Dokumentasi interaktif di <http://localhost:8000/docs>, skema mesin di
`/openapi.json`.

### 4. Permintaan pertama

```bash
curl -X POST localhost:8000/sesi -H 'Content-Type: application/json' -d '{}'
```

Contoh lengkap yang bisa dijalankan: [../examples/klien_api.sh](../examples/klien_api.sh).

### Menempel ke aplikasi FastAPI sendiri

Rute dikumpulkan di `router`, jadi tidak harus dijalankan sebagai server
terpisah:

```python
from fastapi import FastAPI
from lppm_mcp.api import router

app = FastAPI()
app.include_router(router, prefix="/lppm")
```

Contoh utuh: [../examples/api_sendiri.py](../examples/api_sendiri.py).

## Kredensial

Setiap badan permintaan boleh membawa `username` (NIDN atau email) dan
`password` portal LPPM. Isi keduanya, atau kosongkan keduanya supaya server
memakai `LPPM_USERNAME` dan `LPPM_PASSWORD` dari setelannya sendiri (`.env`).
Mengisi salah satu saja dibalas `422`.

`GET /turnitin` tidak berbadan, jadi kredensialnya dikirim lewat header
`X-LPPM-Username` dan `X-LPPM-Password` dengan aturan yang sama: isi keduanya
atau kosongkan keduanya.

Klien per kredensial disimpan di memori server selama 15 menit
(`umur_sesi_detik`). Login berjalan saat pertama dibutuhkan, dan diulang sendiri
kalau sesi portal habis. Password tidak disimpan apa adanya sebagai kunci; yang
dipakai sidik SHA-256-nya.

## Endpoint

Semua endpoint hanya membaca portal, kecuali `POST /turnitin` dengan
`"uji_coba": false`.

### `POST /sesi`

```json
{ "username": "", "password": "" }
```

```json
{ "ok": true, "beranda": "https://lppm.pradita.ac.id/home" }
```

### `POST /menu`

Badan sama seperti `/sesi`. Yang dikembalikan menu navigasi beranda setelah
login:

```json
{
  "beranda": "https://lppm.pradita.ac.id/home",
  "data": [
    { "nama": "Daftar Penelitian", "grup": "Penelitian", "path": "/penelitian",
      "url": "https://lppm.pradita.ac.id/penelitian" }
  ]
}
```

Isi `data` di atas karangan; menu sebenarnya baru terlihat setelah login.

### `POST /halaman`

```json
{ "path": "/infolppm/profil", "bentuk": "teks", "maks_karakter": 0 }
```

| Field           | Bawaan  | Keterangan                                              |
|-----------------|---------|---------------------------------------------------------|
| `path`          | wajib   | path atau URL penuh di bawah portal LPPM                |
| `bentuk`        | `teks`  | `teks` atau `tabel`                                     |
| `maks_karakter` | `0`     | potong keluaran sepanjang ini; `0` berarti utuh         |

Bentuk `teks`:

```json
{ "url": "https://lppm.pradita.ac.id/infolppm/profil", "judul": "...", "bentuk": "teks",
  "teks": "...", "panjang": 1834, "terpotong": false }
```

Bentuk `tabel`: tiap tabel membawa `nomor`, `judul`, `kolom`, `jumlah_baris`,
dan `baris`. Tiap baris berkunci nama kolom, dan tautan di dalamnya dikumpulkan
di `_tautan`. Baris yang jumlah selnya tidak cocok dengan kolomnya dikunci nomor
urut sel (`"1"`, `"2"`, ...). Tabel tanpa baris memunculkan `catatan` tentang
kemungkinan isi yang dimuat lewat AJAX.

### `GET /turnitin`

Jatah dan riwayat pengajuan cek Turnitin. Hanya membaca.

```bash
curl localhost:8000/turnitin
curl localhost:8000/turnitin -H 'X-LPPM-Username: ...' -H 'X-LPPM-Password: ...'
```

```json
{
  "url": "https://lppm.pradita.ac.id/turnitin",
  "jatah": { "dipakai": 1, "total": 2, "sisa": 1,
             "teks": "Status Pengajuan Anda: 1 dari 2 jatah digunakan (Sisa 1x pengajuan)" },
  "flash": [],
  "ada_form": true,
  "riwayat": [{
    "no": 1, "judul": "Kerangka Kerja Fiktif untuk Kota Gotham",
    "tanggal_submit": "2026-10-20T15:15", "tanggal_submit_teks": "20/10/2026 15:15",
    "no_surat": null, "status": "Submit",
    "aksi_teks": "Proses LPPM", "aksi_tautan": [], "aksi_pemicu": [],
    "ada_modal_perbaikan": false
  }]
}
```

`jatah` bernilai `null` kalau kotaknya tidak terbaca, dan `no_surat` bernilai
`null` selama portal menulis `-`. Kolom Aksi dicatat apa adanya karena isinya
untuk status selain Submit belum pernah teramati: `aksi_tautan` berisi setiap
href (`{teks, href, url}`), `aksi_pemicu` setiap elemen beratribut `data-*`
(`{tag, teks, atribut, teks_modal}`), dan `ada_modal_perbaikan` bernilai true
kalau ada pemicu `data-toggle="modal"` yang menyebut "perbaikan".

### `POST /turnitin`

Mengajukan satu naskah. Bawaannya uji coba, yang tidak mengirim apa pun.

```json
{ "judul": "Judul Naskah", "tautan": "https://drive.google.com/file/d/.../view",
  "uji_coba": true, "paksa": false }
```

| Field      | Bawaan | Keterangan                                                          |
|------------|--------|---------------------------------------------------------------------|
| `judul`    | wajib  | judul naskah                                                        |
| `tautan`   | wajib  | https ke `drive.google.com` atau `docs.google.com`                  |
| `uji_coba` | `true` | `true`: kembalikan rencana kiriman; `false`: kirim dan pakai satu jatah |
| `paksa`    | `false`| tetap ajukan walau judul yang sama sudah ada di riwayat             |

Badan ini juga boleh membawa `username` dan `password`, seperti endpoint lain.

Dengan `uji_coba: true`, balasannya rencana kiriman tanpa token CSRF:

```json
{
  "uji_coba": true, "terkirim": false, "diterima": false,
  "metode": "POST", "action": "https://lppm.pradita.ac.id/turnitin",
  "isian": { "judul_naskah": "Judul Naskah",
             "file_artikel": "https://drive.google.com/file/d/.../view" },
  "jatah": { "dipakai": 1, "total": 2, "sisa": 1, "teks": "..." },
  "flash": [], "baris_baru": null, "pesan": "Uji coba: belum ada yang dikirim. ..."
}
```

Dengan `uji_coba: false`, form dikirim sekali. Balasannya membawa `flash` dari
portal, `jatah` terbaru, dan `baris_baru` dari riwayat; `diterima` bernilai true
kalau baris baru itu terlihat. Kiriman yang sampai tetapi tidak tercatat tetap
dibalas `200` dengan `diterima: false`, dan `flash` biasanya menjelaskan
sebabnya.

Pengajuan dibalas `422` tanpa mengirim apa pun kalau judulnya kosong,
tautannya tidak sah, jatahnya habis, atau judul yang sama sudah ada di riwayat
(kecuali `paksa: true`). Galat sesudah kiriman berangkat dibalas `502` dengan
`detail` yang diawali "Pengajuan sudah dikirim, tetapi hasilnya tidak bisa
dipastikan". Periksa `GET /turnitin` sebelum mencoba lagi, karena kiriman tidak
pernah diulang otomatis.

## Status galat

| Status | Sebab                                                                  |
|--------|------------------------------------------------------------------------|
| `400`  | kredensial tidak dikirim dan setelan server juga belum punya           |
| `401`  | login ditolak portal, atau sesi tidak pulih setelah login ulang        |
| `422`  | badan tidak sah, alamat di luar portal, alamat yang tampak seperti aksi, atau pengajuan Turnitin yang ditolak sebelum dikirim |
| `502`  | portal membalas galat, halaman bukan HTML, jaringan gagal, atau hasil pengajuan Turnitin yang tidak pasti |

## Batas yang sudah diketahui

- Alamat di host lain, alamat tanpa https, dan pengalihan ke host lain ditolak.
  Cookie sesi portal berlaku untuk seluruh `.pradita.ac.id`, jadi pembatasan
  ini menjaga cookie itu tetap di portal LPPM.
- Alamat yang memuat kata aksi (`logout`, `hapus`, `delete`, `setujui`, `batal`,
  `submit`, dan sejenisnya) ditolak `422`.
- Satu-satunya POST ke portal selain login adalah pengajuan cek Turnitin, dan
  tujuannya hanya `/turnitin`. Jatahnya terbatas (2 per pemakai per Oktober
  2026), jadi jalankan uji coba lebih dulu dan kirim hanya setelah pemakai
  setuju.
- Berkas biner seperti PDF belum bisa diunduh lewat API ini; lihat bagian
  Rencana di README.
