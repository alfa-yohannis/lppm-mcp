# Referensi MCP LPPM

Server MCP membuka kemampuan yang sama dengan REST API dan CLI, sehingga asisten
AI bisa memakai sendiri portal LPPM Pradita. Empat dari lima tool-nya hanya
membaca. Yang kelima, `ajukan_turnitin`, bisa mengirim pengajuan cek Turnitin,
dengan uji coba sebagai bawaannya.

## Menjalankan

### 1. Pasang

Butuh Python 3.10+.

```bash
git clone https://github.com/alfa-yohannis/lppm-mcp.git
cd lppm-mcp
./lppm uji              # jalankan pertama menyiapkan .venv + dependensi
```

Atau sebagai paket:
`pip install "lppm-mcp[mcp] @ git+https://github.com/alfa-yohannis/lppm-mcp.git"`.

### 2. Isi kredensial

Isi `.env` pada akar proyek, disalin dari `.env.contoh`:

```
LPPM_WEBSITE=https://lppm.pradita.ac.id/login
LPPM_USERNAME=nama.anda@pradita.ac.id     # atau NIDN
LPPM_PASSWORD=...
```

Tool MCP tidak menerima username maupun password lewat parameter. Kredensial
selalu dibaca dari setelan server, jadi asisten tidak pernah memegang kata sandi.

### 3. Cek servernya hidup

Jalankan sekali sebelum didaftarkan:

```bash
./lppm mcp        # atau lppm-mcp kalau terpasang sebagai paket
```

Server bicara JSON-RPC lewat stdio, jadi terminal akan tampak diam menunggu
masukan. Itu memang benar. Ctrl-C untuk berhenti.

### 4. Daftarkan

Untuk Claude Code:

```bash
claude mcp add lppm-mcp -s user -- /path/ke/lppm-mcp/lppm mcp
claude mcp list                      # pastikan muncul "✔ Connected"
```

`-s user` membuatnya tersedia dari direktori mana pun. Kalau terpasang sebagai
paket, perintahnya cukup `claude mcp add lppm-mcp -s user -- lppm-mcp`.

Untuk Codex, formatnya TOML di `~/.codex/config.toml`:

```toml
[mcp_servers.lppm-mcp]
command = "/path/ke/lppm-mcp/lppm"
args = ["mcp"]
```

Atau lewat perintah, dengan `--` memisahkan opsi dari perintah servernya:

```bash
codex mcp add lppm-mcp -- /path/ke/lppm-mcp/lppm mcp
codex mcp list
```

Untuk Antigravity, sunting `~/.gemini/config/mcp_config.json` (global) atau
`.agents/mcp_config.json` (per ruang kerja):

```json
{
  "mcpServers": {
    "lppm-mcp": {
      "command": "/path/ke/lppm-mcp/lppm",
      "args": ["mcp"]
    }
  }
}
```

Untuk klien MCP lain, pakai [../examples/mcp_klien.json](../examples/mcp_klien.json).

### 5. Coba

Minta asisten Anda:

```
Cek apakah login portal LPPM saya jalan, lalu tampilkan menu yang tersedia.
```

```
Berapa sisa jatah cek Turnitin saya, dan apa status pengajuan terakhir?
```

Contoh prompt lain di [../examples/prompt_mcp.md](../examples/prompt_mcp.md).

## Mengaktifkan setelah didaftarkan

Daftar server dibaca saat klien dijalankan, jadi entri baru tidak muncul di sesi
yang sedang berlangsung:

| Klien       | Cara memuat                                          | Cara memeriksa                     |
|-------------|------------------------------------------------------|------------------------------------|
| Claude Code | mulai sesi baru                                      | `claude mcp list` → `✔ Connected`  |
| Codex       | jalankan ulang Codex                                 | `codex mcp list` → `enabled`       |
| Antigravity | tombol refresh di Manage MCP Servers, atau jalankan ulang | panel yang sama; di CLI ketik `/mcp` |

Empat tool hanya membaca dan aman diizinkan otomatis: `cek_login`,
`daftar_menu`, `ambil_halaman`, dan `daftar_turnitin`. Biarkan `ajukan_turnitin`
tetap meminta persetujuan setiap kali dipanggil, karena kiriman sungguhannya
memakai jatah cek Turnitin yang terbatas. Di Claude Code nama izinnya berbentuk
`mcp__lppm-mcp__daftar_turnitin`. Di Antigravity izinkan satu per satu dengan
pola `mcp(lppm-mcp/daftar_turnitin)`; pola `mcp(lppm-mcp/*)` ikut meloloskan
`ajukan_turnitin`.

## Tool

| Tool              | Parameter                                      | Hasil                                     |
|-------------------|------------------------------------------------|-------------------------------------------|
| `cek_login`       | (tidak ada)                                    | `{ok, beranda}` atau `{ok: false, pesan}` |
| `daftar_menu`     | (tidak ada)                                    | `{ok, beranda, jumlah, menu}`             |
| `ambil_halaman`   | `path`, `bentuk?`, `maks_karakter?`            | teks atau tabel satu halaman              |
| `daftar_turnitin` | (tidak ada)                                    | jatah dan riwayat cek Turnitin            |
| `ajukan_turnitin` | `judul`, `tautan`, `uji_coba?` (bawaan `true`), `paksa?` | rencana kiriman; menulis kalau `uji_coba=false` |

Setiap tool membalas `ok`. Kalau `ok` bernilai `false`, `pesan` menjelaskan
sebabnya: kredensial belum diisi, login ditolak, alamat di luar portal, alamat
yang tampak seperti aksi, atau pengajuan Turnitin yang ditolak.

### `cek_login`

Login dari awal dengan kredensial di setelan, lalu memakai sesi itu untuk tool
berikutnya. Berguna juga setelah `.env` diubah.

```json
{ "ok": true, "beranda": "https://lppm.pradita.ac.id/home" }
```

### `daftar_menu`

Membaca menu navigasi beranda setelah login. Tautan logout, logo, tautan ke host
lain, dan kepala grup tanpa tujuan (`href="#"`) tidak ikut; nama kepala grup
dicatat di `grup` milik anak-anaknya.

```json
{
  "ok": true,
  "beranda": "https://lppm.pradita.ac.id/home",
  "jumlah": 2,
  "menu": [
    { "nama": "Daftar Penelitian", "grup": "Penelitian", "path": "/penelitian",
      "url": "https://lppm.pradita.ac.id/penelitian" },
    { "nama": "Surat Tugas", "grup": "", "path": "/surat-tugas",
      "url": "https://lppm.pradita.ac.id/surat-tugas" }
  ]
}
```

Path dan nama di atas karangan; menu sebenarnya baru terlihat setelah login.

### `ambil_halaman`

`path` boleh path relatif (`/infolppm/profil`) atau URL penuh, asalkan di portal
LPPM. `bentuk` bernilai `teks` (bawaan) atau `tabel`. `maks_karakter` membatasi
panjang keluaran, bawaannya 20000; isi `0` untuk keluaran utuh.

Bentuk `teks` mengembalikan isi halaman tanpa menu, skrip, dan isian
tersembunyi. Nilai `<input disabled>` ikut terbaca karena halaman detail sering
menampilkan datanya di sana.

```json
{ "ok": true, "url": "https://lppm.pradita.ac.id/infolppm/profil", "judul": "...",
  "bentuk": "teks", "teks": "...", "panjang": 1834, "terpotong": false }
```

Bentuk `tabel` mengembalikan tiap tabel dengan baris berkunci nama kolom.
Tautan di dalam baris (tombol detail, unduh) dikumpulkan di `_tautan`:

```json
{
  "ok": true, "bentuk": "tabel", "jumlah_tabel": 1, "terpotong": false,
  "tabel": [{
    "nomor": 1, "judul": "Penelitian Saya",
    "kolom": ["No", "Judul", "Ketua", "Status", "Aksi"],
    "jumlah_baris": 1,
    "baris": [{ "No": "1", "Judul": "Rancang Bangun Aplikasi Contoh", "Ketua": "King Kong",
                "Status": "Disetujui", "Aksi": "",
                "_tautan": [{ "teks": "Detail", "url": "https://lppm.pradita.ac.id/penelitian/101" }] }]
  }]
}
```

Kalau tabelnya ada tapi tanpa baris, balasan membawa `catatan`: isinya mungkin
dimuat DataTables lewat AJAX, dan `./lppm petakan <path>` bisa menemukan
endpoint-nya.

Yang ditolak: alamat di host lain atau tanpa https, pengalihan ke host lain,
alamat yang path atau query-nya memuat kata aksi (`logout`, `hapus`, `delete`,
`setujui`, `batal`, `submit`, dan sejenisnya), serta berkas biner seperti PDF.

### `daftar_turnitin`

Membaca halaman `/turnitin` (hanya GET): jatah, pesan flash yang sedang tampil,
dan riwayat pengajuan cek Turnitin.

```json
{
  "ok": true,
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

`jatah` bernilai `null` kalau kotaknya tidak terbaca. `no_surat` bernilai `null`
selama portal menulis `-`. Isi kolom Aksi untuk status selain Submit belum
pernah teramati, jadi dicatat apa adanya:

- `aksi_tautan`: setiap href di kolom itu, sebagai `{teks, href, url}`; `url`
  kosong untuk href seperti `#modal` atau `javascript:`;
- `aksi_pemicu`: setiap elemen beratribut `data-*`, sebagai
  `{tag, teks, atribut, teks_modal}`, dengan `teks_modal` berisi teks modal yang
  dituju lewat `data-target` atau href `#id`;
- `ada_modal_perbaikan`: true kalau ada pemicu `data-toggle="modal"` yang
  teksnya atau modal tujuannya menyebut "perbaikan".

Contoh pemicu, dengan bentuk karangan:

```json
{ "tag": "button", "teks": "Form Perbaikan",
  "atribut": { "data-toggle": "modal", "data-target": "#perbaikan8" },
  "teks_modal": "Form Perbaikan Catatan LPPM: similarity 35%, perbaiki bab 2. ..." }
```

### `ajukan_turnitin`

Mengajukan satu naskah. `tautan` harus https ke `drive.google.com` atau
`docs.google.com`. Pengajuan ditolak tanpa mengirim apa pun kalau judulnya
kosong, tautannya tidak sah, jatahnya habis, judul yang sama sudah ada di
riwayat (tanpa membedakan huruf besar dan kecil maupun spasi berlebih), atau
form di halaman berubah. `paksa=true` hanya melewati pemeriksaan judul kembar.

Dengan `uji_coba=true` (bawaan), yang kembali adalah rencana kiriman tanpa
token CSRF, beserta jatah saat ini:

```json
{
  "ok": true, "uji_coba": true, "terkirim": false, "diterima": false,
  "metode": "POST", "action": "https://lppm.pradita.ac.id/turnitin",
  "isian": { "judul_naskah": "Judul Naskah",
             "file_artikel": "https://drive.google.com/file/d/.../view" },
  "jatah": { "dipakai": 1, "total": 2, "sisa": 1, "teks": "..." },
  "flash": [], "baris_baru": null,
  "pesan": "Uji coba: belum ada yang dikirim. Kiriman sungguhan memakai 1 dari 1 jatah yang tersisa. ..."
}
```

Dengan `uji_coba=false`, form dikirim sekali, lalu halaman tempat portal
mendarat dibaca untuk pesan flash, jatah terbaru, dan baris baru di riwayat.
`diterima` bernilai true kalau baris baru itu terlihat:

```json
{
  "ok": true, "uji_coba": false, "terkirim": true, "diterima": true,
  "jatah": { "dipakai": 2, "total": 2, "sisa": 0, "teks": "..." },
  "flash": [{ "jenis": "success", "teks": "Pengajuan Cek Turnitin berhasil dikirim." }],
  "baris_baru": { "no": 2, "judul": "Judul Naskah", "tanggal_submit": "2026-10-20T16:05",
                  "no_surat": null, "status": "Submit", "aksi_teks": "Proses LPPM" },
  "pesan": "Pengajuan terkirim dan tercatat di riwayat."
}
```

`baris_baru` berbentuk sama dengan baris `riwayat`; contoh di atas dipendekkan.
Kalau gagal, balasannya membawa `terkirim`:

```
{ "ok": false, "terkirim": false, "pesan": "Judul 'Judul Naskah' sudah ada di riwayat (...)" }
{ "ok": false, "terkirim": true, "pesan": "Pengajuan sudah dikirim, tetapi hasilnya tidak bisa dipastikan (...)" }
```

`terkirim: true` berarti permintaannya sudah berangkat, tetapi portal membalas
galat, sesi atau token CSRF-nya habis, atau pengalihannya mengarah ke luar
portal. Kiriman tidak diulang otomatis.

## Catatan untuk agen

- Semua tool hanya membaca portal LPPM, kecuali `ajukan_turnitin` dengan
  `uji_coba=false`.
- Jangan meminta kata sandi ke pemakai. Kalau `pesan` menyebut kredensial belum
  ada, minta pemakai mengisi `.env` sendiri.
- Urutan yang disarankan: `cek_login`, lalu `daftar_menu`, lalu `ambil_halaman`
  dengan path dari menu itu. Untuk halaman daftar, pakai `bentuk="tabel"`.
- Jangan membuka tautan aksi dari `_tautan` (hapus, setujui, dan sejenisnya);
  tool akan menolaknya.
- Jatah cek Turnitin terbatas (2 per pemakai per Oktober 2026). Jalankan
  `ajukan_turnitin` dengan `uji_coba=true` lebih dulu, tunjukkan judul, tautan,
  dan sisa jatahnya ke pemakai, lalu kirim dengan `uji_coba=false` hanya setelah
  pemakai menyetujuinya.
- Kalau balasannya `terkirim: true` dengan `ok: false`, jangan mengirim ulang.
  Periksa `daftar_turnitin` dulu dan laporkan hasilnya ke pemakai.
- Jangan menebak arti kolom Aksi di riwayat Turnitin di luar isinya; sampaikan
  teks, tautan, dan teks modalnya apa adanya.
- Alat khusus surat tugas, penelitian, PkM, dan unduh dokumen belum ada; lihat
  bagian Rencana di README.
