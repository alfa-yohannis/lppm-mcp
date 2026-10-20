# LPPM MCP

Aplikasi untuk memakai portal LPPM Universitas Pradita
(<https://lppm.pradita.ac.id>) dari asisten AI, terminal, atau program lain.
Isinya alat umum yang tidak bergantung pada isi portal (cek login, daftar menu
setelah login, dan pembaca halaman yang mengembalikan teks atau tabel), ditambah
satu alat khusus: [cek Turnitin](#cek-turnitin), untuk memantau jatah dan
riwayat pengajuan serta mengajukan naskah baru. Alat khusus untuk surat tugas,
penelitian, PkM, dan unduh dokumen menyusul setelah halamannya dipetakan;
daftarnya ada di bagian [Rencana](#rencana).

Pasangannya adalah [siakad-mcp](https://github.com/alfa-yohannis/siakad-mcp)
(data pengajaran) dan [sister-mcp](https://github.com/alfa-yohannis/sister-mcp)
(pengisian BKD). Ketiganya berdiri sendiri: kode, dokumentasi, contoh, dan
pengujiannya terpisah.

Tersedia dalam tiga bentuk, semuanya dari paket yang sama:

| Mode     | Untuk siapa                    | Referensi                    |
|----------|--------------------------------|------------------------------|
| MCP      | asisten AI (Claude Code, dsb.) | [docs/MCP.md](docs/MCP.md)   |
| REST API | aplikasi apa pun lewat HTTP    | [docs/API.md](docs/API.md)   |
| Pustaka  | program Python Anda sendiri    | [bagian Pustaka](#3-pustaka) |

Ada juga CLI (`./lppm menu`, `./lppm halaman`, `./lppm turnitin`, dan
seterusnya) untuk pemakaian langsung dari terminal; lihat
[docs/CLI.md](docs/CLI.md).

## Memakainya lewat asisten AI

Server MCP-nya bisa didaftarkan ke Claude Code, Codex, dan Antigravity. Yang
tercepat, untuk Claude Code dari klona repositori ini:

```bash
claude mcp add lppm-mcp -s user -- /path/ke/lppm-mcp/lppm mcp
```

Langkah untuk ketiga klien dan pengaturan izin pemanggilan tool ada di
[docs/MCP.md](docs/MCP.md).

## Prasyarat

- Python 3.10 atau lebih baru
- Akun portal LPPM yang aktif (NIDN atau email, dan password)

## Pasang

Ada dua cara, pilih salah satu.

A. Berdiri sendiri. Klona lalu jalankan; cocok kalau Anda hanya mau memakai
aplikasinya:

```bash
git clone https://github.com/alfa-yohannis/lppm-mcp.git
cd lppm-mcp
./lppm uji          # jalankan pertama menyiapkan .venv + dependensi sendiri
```

Virtualenv dibuat dengan `python3`. Kalau versi itu terlalu baru untuk sebagian
dependensi, pilih interpreter lain: `LPPM_PYTHON=python3.12 ./lppm uji`.

B. Sebagai paket, kalau aplikasi Anda sendiri yang akan memakainya. Paketnya
belum ada di PyPI, jadi pasang dari repositorinya:

```bash
pip install "lppm-mcp[api,mcp] @ git+https://github.com/alfa-yohannis/lppm-mcp.git"
pip install "git+https://github.com/alfa-yohannis/lppm-mcp.git"   # pustaka saja
```

## Kredensial

Salin contohnya lalu isi sendiri:

```bash
cp .env.contoh .env       # LPPM_USERNAME (NIDN atau email), LPPM_PASSWORD
```

`.env` tidak ikut ter-commit. Kredensial hanya dibaca dari `.env`, environment,
atau `atur_setelan()` di kode, tidak pernah dari `lppm.yaml`, dan tidak pernah
dicetak ke layar maupun log. Tool MCP sengaja tidak menerima kata sandi lewat
parameter, jadi asisten AI tidak pernah memegangnya. REST API boleh menerimanya
per permintaan supaya satu server bisa melayani beberapa dosen.

Login baru berjalan saat sebuah perintah atau tool membutuhkan halaman. Kalau
sesi portal habis di tengah jalan, klien login ulang sekali secara otomatis.

## Menjalankan

### 1. MCP

```bash
claude mcp add lppm-mcp -- /path/ke/lppm-mcp/lppm mcp   # dari klona
claude mcp add lppm-mcp -- lppm-mcp                     # setelah pip install
```

Cek servernya hidup tanpa mendaftarkannya dulu:

```bash
./lppm mcp        # bicara JSON-RPC lewat stdio; Ctrl-C untuk berhenti
```

Lalu minta asisten Anda, misalnya: *"Menu apa saja yang ada di portal LPPM
setelah saya login?"* atau *"Berapa sisa jatah cek Turnitin saya?"* Ada lima
tool. Empat hanya membaca: `cek_login`, `daftar_menu`, `ambil_halaman`, dan
`daftar_turnitin`. Yang kelima, `ajukan_turnitin`, bisa mengirim pengajuan cek
Turnitin, tetapi bawaannya uji coba. Rinciannya di [docs/MCP.md](docs/MCP.md).

### 2. REST API

```bash
./lppm api                  # http://localhost:8000
PORT=9001 ./lppm api        # ganti port
uvicorn lppm_mcp.api:app --port 8000   # kalau terpasang sebagai paket
```

Dokumentasi interaktif ada di `/docs`. Coba:

```bash
curl -X POST localhost:8000/halaman -H 'Content-Type: application/json' \
  -d '{"path": "/infolppm/profil"}'
curl localhost:8000/turnitin          # jatah dan riwayat cek Turnitin
```

Untuk menempelkannya ke aplikasi FastAPI Anda sendiri:

```python
from lppm_mcp.api import router
app.include_router(router, prefix="/lppm")
```

Endpoint selengkapnya di [docs/API.md](docs/API.md).

### 3. Pustaka

```python
from lppm_mcp import KlienLppm

klien = KlienLppm()                        # kredensial dari .env; belum login
for menu in klien.daftar_navigasi():       # login berjalan di sini
    print(menu["grup"], menu["nama"], menu["path"])

halaman = klien.ambil_halaman("/infolppm/profil")
print(halaman.judul())
print(halaman.teks())
print(halaman.tabel())                     # tiap baris berkunci nama kolom
```

Kredensial dan alamat portal boleh diberikan dari kode tanpa berkas apa pun:

```python
from lppm_mcp import KlienLppm, atur_setelan

atur_setelan(LPPM_USERNAME="0000000000", LPPM_PASSWORD="...")
klien = KlienLppm()
klien_lain = KlienLppm(base_url="https://lppm.kampus-lain.ac.id")
```

Cek Turnitin dari kode:

```python
from lppm_mcp import KlienLppm, ajukan_turnitin, daftar_turnitin

klien = KlienLppm()
status = daftar_turnitin(klien)                    # jatah dan riwayat
print(status.jatah.sisa, [baris.status for baris in status.riwayat])

tautan = "https://drive.google.com/file/d/.../view"
rencana = ajukan_turnitin(klien, "Judul Naskah", tautan)                 # uji coba
hasil = ajukan_turnitin(klien, "Judul Naskah", tautan, uji_coba=False)   # memakai 1 jatah
print(hasil.diterima, hasil.flash, hasil.baris_baru)
```

Semua kegagalan berupa exception biasa (`LppmError`, `LoginDitolak`,
`AlamatDitolak`, `PengajuanDitolak`, `HasilTidakPasti`, `KonfigurasiError`);
pustaka tidak pernah memanggil `sys.exit`. Contoh utuh:
[examples/pustaka.py](examples/pustaka.py).

### CLI

```bash
./lppm cek-login                      # kredensial di .env bisa dipakai?
./lppm menu                           # menu navigasi setelah login
./lppm halaman /infolppm/profil       # isi halaman sebagai teks
./lppm halaman <path> --tabel         # tabel di halaman itu
./lppm petakan <path>                 # form, tabel, tautan, endpoint AJAX
./lppm turnitin                       # jatah dan riwayat cek Turnitin
./lppm turnitin ajukan --judul ... --tautan ...   # uji coba; --kirim untuk mengirim
```

Terpasang sebagai paket, perintahnya `lppm-cek-login`, `lppm-menu`,
`lppm-halaman`, `lppm-petakan`, `lppm-turnitin`, dan `lppm-mcp` dengan argumen
yang sama. Argumen selengkapnya di [docs/CLI.md](docs/CLI.md).

## Cek Turnitin

Portal LPPM menerima pengajuan cek Turnitin di `/turnitin`. Jatahnya terbatas,
per Oktober 2026 dua kali per pemakai, dan setiap pengajuan yang diterima
memakai satu jatah.

```bash
./lppm turnitin                       # jatah dan riwayat pengajuan
./lppm turnitin --json                # sama, dalam JSON
./lppm turnitin ajukan --judul "Judul Naskah" \
    --tautan "https://drive.google.com/file/d/.../view"            # uji coba
./lppm turnitin ajukan --judul "Judul Naskah" \
    --tautan "https://drive.google.com/file/d/.../view" --kirim    # mengirim
```

Contoh keluaran `./lppm turnitin` (judulnya karangan):

```
Jatah cek Turnitin: 1 dari 2 terpakai, sisa 1
https://lppm.pradita.ac.id/turnitin

Riwayat (1):
  No | Judul Naskah | Tanggal Submit | No. Surat | Status | Aksi
  1 | Kerangka Kerja Fiktif untuk Kota Gotham | 20/10/2026 15:15 | - | Submit | Proses LPPM
```

Pengajuan ditolak sebelum menghubungi portal kalau judulnya kosong atau
tautannya bukan https ke `drive.google.com` atau `docs.google.com`. Sesudah
halaman `/turnitin` dibaca, pengajuan juga ditolak kalau jatahnya habis atau
judul yang sama sudah ada di riwayat. Perbandingan judul tidak membedakan huruf
besar dan kecil maupun spasi berlebih, dan `--paksa` melewatinya.

Tanpa `--kirim` perintahnya hanya uji coba: yang dicetak adalah rencana kiriman
(alamat form beserta isiannya, tanpa token CSRF) dan sisa jatah. Pustaka, MCP,
dan REST API memakai bawaan yang sama, `uji_coba=True`. Dengan `--kirim`, form
dikirim sekali, lalu portal dibaca ulang untuk pesan flash, jatah terbaru, dan
baris riwayat yang baru. Kalau baris baru itu tidak terlihat, kode keluarnya 1.

Kiriman tidak pernah diulang otomatis. Kalau hasilnya tidak bisa dipastikan,
misalnya karena sesi habis, token CSRF basi, galat server, atau pengalihan ke
luar portal, yang muncul `HasilTidakPasti`. Periksa riwayat dengan
`./lppm turnitin` sebelum mencoba lagi.

Kolom Aksi di riwayat baru pernah teramati berisi "Proses LPPM" untuk status
Submit. Untuk status lain isinya dicatat apa adanya: teksnya di `aksi_teks`,
setiap href di `aksi_tautan`, dan elemen beratribut `data-*` di `aksi_pemicu`
beserta teks modal yang dituju. `ada_modal_perbaikan` bernilai true kalau ada
pemicu modal yang teksnya atau modal tujuannya menyebut "perbaikan".

## Setelan

Semua setelan opsional. Yang menang, dari yang paling khusus:

```
argumen pemanggil -> atur_setelan() -> environment -> .env -> lppm.yaml -> nilai bawaan
```

Di environment dan `.env` namanya berawalan `LPPM_` dan huruf besar
(`LPPM_BASE_URL`); di `lppm.yaml` tanpa awalan dan huruf kecil (`base_url`).
Salin `lppm.yaml.contoh` menjadi `lppm.yaml` kalau perlu mengubah sesuatu.

| `lppm.yaml`           | Bawaan                             | Keterangan                                        |
|-----------------------|------------------------------------|---------------------------------------------------|
| `website`             | `https://lppm.pradita.ac.id/login` | halaman login; alamat portal diturunkan darinya   |
| `base_url`            | `https://lppm.pradita.ac.id`       | alamat portal, kalau perlu disebut terpisah       |
| `nama_instansi`       | `Pradita`                          | label pada judul REST API dan instruksi MCP       |
| `field_username`      | dikenali dari form                 | nama isian username; per Oktober 2026 `login`     |
| `batas_login_detik`   | `60`                               | GET dan POST login                                |
| `batas_halaman_detik` | `120`                              | GET halaman biasa                                 |
| `maks_pengalihan`     | `10`                               | pengalihan yang diikuti per permintaan            |
| `umur_sesi_detik`     | `900`                              | lama sesi login disimpan REST API                 |
| `user_agent`          | Chrome 126 di X11                  | User-Agent permintaan HTTP                        |

`LPPM_USERNAME` dan `LPPM_PASSWORD` hanya dibaca dari `atur_setelan()`,
environment, dan `.env`. Alamat portal dan halaman login harus https dan berada
di host yang sama, karena ke sanalah kata sandi dikirim.

## Akar proyek

Akar proyek menentukan letak `.env`, `lppm.yaml`, dan `data/`, serta titik hitung
path relatif:

- dijalankan dari klona repositori ini: direktori repositori itu sendiri
- dipasang sebagai paket: direktori kerja proyek pemakai

Direktori di atasnya tidak pernah ikut ditelusuri, jadi hasilnya tidak berubah
hanya karena aplikasi dipindah. Untuk menentukan sendiri, setel
`LPPM_AKAR_PROYEK` atau panggil `atur_akar_proyek()`.

## Rancangan

```
pyproject.toml             metadata paket, dependensi, dan perintah terpasang
lppm                       peluncur untuk pemakaian berdiri sendiri
lppm.yaml.contoh           contoh setelan non-rahasia
lppm_mcp/__init__.py       API publik paket ini
lppm_mcp/konfigurasi.py    akar proyek, setelan, kredensial, sesi HTTP
lppm_mcp/lppm_client.py    KlienLppm: login Laravel, login ulang, batas portal, ambil halaman, kirim form
lppm_mcp/halaman.py        Halaman: judul, teks, tabel, tautan, menu navigasi (tanpa jaringan)
lppm_mcp/menu.py           MenuLppm: dasar menu khusus situs, termasuk penelusuran paginasi
lppm_mcp/turnitin.py       MenuTurnitin: jatah, riwayat, dan pengajuan cek Turnitin
lppm_mcp/cli.py            CLI (lppm-cek-login, lppm-menu, lppm-halaman, lppm-turnitin)
lppm_mcp/api.py            REST API: router yang bisa ditempel + app siap pakai
lppm_mcp/mcp_server.py     MCP server (perintah lppm-mcp)
lppm_mcp/petakan_form.py   alat bantu memetakan halaman saat menambah kemampuan
tests/                     unit test dengan portal tiruan, tanpa jaringan
docs/                      referensi CLI, REST API, dan MCP
examples/                  contoh prompt, konfigurasi klien MCP, klien API, pustaka
```

## Catatan perilaku portal LPPM

Diamati dari halaman login publik (GET tanpa kredensial) pada Oktober 2026,
ditambah halaman `/turnitin` sesudah login pada 20 Oktober 2026. Halaman sesudah
login lainnya belum dipetakan.

- Halaman loginnya berbentuk bawaan Laravel UI. Form di `/login` dikirim dengan
  POST ke action `https://lppm.pradita.ac.id/login`, berisi isian tersembunyi
  `_token` (token CSRF, 40 karakter), `login` (berlabel "NIDN atau Email
  Address"), `password`, dan kotak centang `remember`. Halaman login tidak
  memasang `<meta name="csrf-token">`; tokennya hanya ada di form.
- Nama isian dan action tidak ditanam di kode. Klien membaca ulang form setiap
  kali login, dan `remember` tidak dikirim karena memang tidak dicentang.
- Portal memasang dua cookie, `XSRF-TOKEN` dan `lppm_pradita_university_session`,
  dengan `Max-Age=7200` (sesi dua jam) dan `domain=.pradita.ac.id`. Karena cookie
  berlaku untuk seluruh domain kampus, klien tidak mengikuti pengalihan ke host
  lain.
- Perilaku gagal login belum diamati, karena pemetaan ini tidak mengirim POST.
  Klien mengikuti pola bawaan Laravel UI: gagal berarti dialihkan kembali ke
  `/login` dengan pesan di `.invalid-feedback`, token basi dibalas HTTP 419, dan
  percobaan yang terlalu sering dibalas HTTP 429 atau pesan throttle.
- Halaman publik memakai templat Yummy (BootstrapMade), dengan menu `/infolppm/*`
  dan `/artikel`. Halaman itu juga memuat aset `/lte/plugins/...` dari AdminLTE,
  tanda bahwa halaman sesudah login kemungkinan memakai AdminLTE. Itu belum
  dipastikan; pembaca menu dan isi sudah mengenali kedua templat.
- Halaman `/turnitin` memuat kotak `.alert-info` "Status Pengajuan Anda: 1 dari
  2 jatah digunakan (Sisa 1x pengajuan)", form POST ke `/turnitin` berisi
  `_token`, `judul_naskah` (teks, wajib), dan `file_artikel` (url, wajib,
  dengan placeholder `https://drive.google.com/...`), lalu tabel riwayat
  berkolom No, Judul Naskah, Tanggal Submit (`dd/mm/yyyy HH:MM`), No. Surat
  (`-` selama belum ada), Status (badge, mis. "Submit"), dan Aksi.
- Sesudah pengajuan, `/turnitin` menampilkan flash `.alert-success` "Pengajuan
  Cek Turnitin berhasil dikirim." Bentuk pesan galatnya belum teramati;
  pembacanya mengikuti bawaan Laravel (`.alert-danger` dan `.invalid-feedback`).
- Kolom Aksi baru teramati untuk status Submit, berisi teks "Proses LPPM" tanpa
  tautan. Di dalam `<tbody>` ada komentar HTML "Modal Form Perbaikan
  (Bootstrap 4)", tanda bahwa status lain kemungkinan membawa modal perbaikan
  per baris. Isi kolom itu untuk status lain, termasuk tautan unduh surat atau
  laporan, dan nama-nama status selain Submit belum pernah terlihat.

## Keamanan dan batasan

- Verifikasi sertifikat TLS selalu aktif dan tidak ada setelan untuk
  mematikannya.
- Setiap permintaan dibatasi ke host portal LPPM. Alamat lain, alamat `http://`,
  dan pengalihan ke host lain ditolak sebelum dikirim.
- GET hanya membaca. Alamat yang path atau query-nya memuat kata aksi
  (`logout`, `hapus`, `delete`, `setujui`, `tolak`, `batal`, `submit`, `kirim`,
  `ajukan`, `verifikasi`, dan beberapa lainnya; daftar lengkapnya `KATA_AKSI` di
  `lppm_client.py`) ditolak, karena aplikasi Laravel kadang memasang aksi
  seperti hapus pada tautan GET di baris tabel.
- Selain login, satu-satunya penulisan adalah pengajuan cek Turnitin lewat
  `KlienLppm.kirim_form()`. Method itu hanya mengirim POST ke path di
  `PATH_POST_DIIZINKAN` (sekarang hanya `/turnitin`, tanpa query), hanya
  setelah login, dan tepat sekali. Pengalihan sesudahnya diikuti sebagai GET
  selama masih di host portal; pengalihan 307/308 yang meminta POST diulang ke
  alamat lain tidak diikuti.
- Kredensial tidak muncul di `repr()`, di pesan galat, maupun di keluaran CLI.
  Pesan galat dari portal disamarkan kalau kebetulan menggemakan username atau
  kata sandi.
- Berkas biner (PDF dan sejenisnya) ditolak `ambil_halaman`; unduh dokumen
  termasuk Rencana.

## Rencana

Selain Turnitin, alat khusus situs belum dibuat karena halamannya belum
dipetakan. Tempatnya sudah disiapkan: tiap menu menjadi satu modul yang mewarisi
`MenuLppm` (`lppm_mcp/menu.py`), seperti `lppm_mcp/turnitin.py`, lalu
didaftarkan ke CLI, REST API, dan MCP.

| Kemampuan     | Tool MCP (rencana)                         | Modul (rencana)             |
|---------------|--------------------------------------------|-----------------------------|
| Surat tugas   | `daftar_surat_tugas`                       | `lppm_mcp/surat_tugas.py`   |
| Penelitian    | `daftar_penelitian`, `detail_penelitian`   | `lppm_mcp/penelitian.py`    |
| PkM           | `daftar_pkm`, `detail_pkm`                 | `lppm_mcp/pengabdian.py`    |
| Unduh dokumen | `unduh_dokumen`                            | `lppm_mcp/dokumen.py`       |

Yang perlu dipetakan dari halaman sesudah login, dengan akun pemakai sendiri:

1. Beranda: alamat pendaratan setelah login (Laravel UI biasanya `/home`),
   templatnya, dan ada tidaknya `<meta name="csrf-token">`.
2. Menu navigasi: path dan grup untuk surat tugas, penelitian, PkM, dan dokumen,
   serta apakah menunya berbeda per peran (dosen, reviewer).
3. Halaman daftar penelitian dan PkM: kolom tabel; paginasi server
   (`?page=N`) atau DataTables lewat AJAX (endpoint, parameter, bentuk JSON);
   filter seperti tahun, skema, dan status.
4. Halaman detail: letak id di URL, bentuk datanya (tabel kunci-nilai atau
   `<input disabled>`), anggota, mitra, dana, dan status.
5. Surat tugas: berdiri sebagai menu sendiri atau lampiran penelitian/PkM; nomor,
   tanggal, dan bentuk berkasnya.
6. Unduhan dokumen: route-nya, `Content-Type` dan `Content-Disposition`
   (nama berkas), dan apakah berkasnya di penyimpanan portal atau di tautan luar
   seperti Google Drive.
7. Tombol aksi di baris tabel: apakah hapus, ajukan, dan sejenisnya memakai GET
   atau form POST/DELETE. Hasilnya menentukan apakah `KATA_AKSI` perlu disesuaikan.
8. Perilaku sesi: lama sesi bertahan dan apakah login berulang memicu throttle.
9. Form isian, kalau kelak ada kebutuhan menulis: field, validasi, dan enctype.

## Menambah kemampuan baru

```bash
./lppm cek-login                 # 1. pastikan kredensial di .env benar
./lppm menu                      # 2. temukan path menu yang dituju
./lppm petakan <path>            # 3. petakan halamannya ke data/form_<path>.json
./lppm halaman <path> --tabel    #    lihat isi tabelnya
# 4. tulis modul yang mewarisi MenuLppm, beserta dataclass untuk barisnya
# 5. daftarkan di cli.py, api.py, dan mcp_server.py
# 6. tambahkan uji dengan HTML karangan di tests/
```

`./lppm petakan` hanya melakukan GET. Nilai token CSRF dan isian password tidak
ikut dicatat, dan `data/` sudah masuk `.gitignore`.

Tool atau perintah yang menulis ke portal mengikuti pola Turnitin. Ia menerima
`uji_coba` yang bawaannya True dan mengembalikan rencana kiriman tanpa
mengirimnya; di CLI, kiriman sungguhan butuh `--kirim`. Kirimannya lewat
`KlienLppm.kirim_form()` setelah path tujuannya ditambahkan ke
`PATH_POST_DIIZINKAN`, dan instruksi MCP-nya meminta asisten menjalankan uji
coba lebih dulu lalu meminta persetujuan pemakai.

## Konvensi penulisan skrip

- Satu kelas untuk satu tanggung jawab; alur bersama tinggal di kelas dasar,
  yang khas per menu ada di subkelasnya.
- Setiap kelas, method, dan fungsi punya docstring.
- Fungsi ditulis datar, tanpa fungsi bersarang di dalam fungsi.
- Nama variabel dan fungsi ditulis utuh dan deskriptif (`sesi_http`,
  `form_login`), tanpa singkatan satu-dua huruf.
- Komentar hanya untuk hal yang tidak terbaca dari kodenya.
- Nilai rahasia tidak pernah dicetak.

## Pengujian

```bash
./lppm uji
```

181 unit test, semuanya berjalan tanpa jaringan dan tanpa kredensial: portal
digantikan `SitusTiruan` di `tests/conftest.py` yang menjawab seperti aplikasi
Laravel, termasuk halaman `/turnitin` dan POST pengajuannya. Selama uji, akar
proyek dipindah ke direktori sementara supaya `.env` asli tidak terbaca, dan
sesi HTTP sungguhan diblokir. Nama tokoh, judul
penelitian, NIDN, dan kata sandi di berkas uji dan dokumentasi seluruhnya
dikarang.
