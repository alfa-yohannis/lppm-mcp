# Referensi CLI LPPM

## Menjalankan

### 1. Pasang

Butuh Python 3.10+.

```bash
git clone https://github.com/alfa-yohannis/lppm-mcp.git
cd lppm-mcp
./lppm uji            # jalankan pertama menyiapkan .venv + dependensi
```

Terpasang lewat pip, perintahnya `lppm-cek-login`, `lppm-menu`, `lppm-halaman`,
`lppm-petakan`, dan `lppm-turnitin` dengan argumen yang sama persis:
`./lppm menu` dan `lppm-menu` setara.

### 2. Isi kredensial

```bash
cp .env.contoh .env   # LPPM_USERNAME (NIDN atau email), LPPM_PASSWORD
```

### 3. Cek, lalu lihat menunya

```bash
./lppm cek-login
./lppm menu
```

## Semua sub-perintah

Dijalankan dari akar proyek, yaitu direktori berisi `lppm`.

```bash
./lppm cek-login        # kredensial di .env bisa dipakai login?
./lppm menu ...         # menu navigasi setelah login
./lppm halaman ...      # isi satu halaman sebagai teks atau tabel
./lppm petakan ...      # petakan halaman saat menambah kemampuan
./lppm turnitin ...     # jatah, riwayat, dan pengajuan cek Turnitin
./lppm api              # REST API
./lppm mcp              # MCP server
./lppm uji              # unit test
```

Semua perintah hanya membaca portal, kecuali `./lppm turnitin ajukan --kirim`.
Kredensial selalu dibaca dari setelan (`.env`, environment) dan tidak pernah
dicetak. Kegagalan dilaporkan sebagai satu baris `Gagal: ...` di stderr dengan
kode keluar 1.

## `./lppm cek-login`

```bash
./lppm cek-login
# Login LPPM OK, beranda: https://lppm.pradita.ac.id/home
```

Tanpa argumen. Kalau `.env` belum diisi, pesannya menyebut kunci yang kurang
(`LPPM_USERNAME`, `LPPM_PASSWORD`) tanpa menghubungi portal.

## `./lppm menu`

```bash
./lppm menu
./lppm menu --json | jq '.[].path'
```

| Argumen  | Keterangan              |
|----------|-------------------------|
| `--json` | Cetak JSON, bukan daftar |

Satu baris per tautan menu. Submenu ditulis bersama induknya, mis.
`Penelitian > Daftar Penelitian  /penelitian` (contoh karangan).

## `./lppm halaman`

```bash
./lppm halaman /infolppm/profil
./lppm halaman <path> --tabel
./lppm halaman <path> --tabel --json > tabel.json
./lppm halaman https://lppm.pradita.ac.id/artikel --maks 2000
```

| Argumen   | Wajib | Keterangan                                                |
|-----------|-------|-----------------------------------------------------------|
| `path`    | ya    | path atau URL penuh di bawah portal LPPM                  |
| `--tabel` |       | tampilkan tabelnya, bukan teks                            |
| `--maks`  |       | potong keluaran sepanjang N karakter; `0` berarti utuh    |
| `--json`  |       | cetak JSON                                                |

Bentuk teks membuang menu, skrip, dan isian tersembunyi. Bentuk tabel menulis
satu baris per rekam dengan sel dipisah ` | `, lalu tautan baris itu (tombol
detail atau unduh) di bawahnya.

Ditolak: alamat di host lain atau tanpa https, pengalihan ke host lain, alamat
yang memuat kata aksi (`logout`, `hapus`, `delete`, `setujui`, dan sejenisnya),
dan berkas biner seperti PDF.

## `./lppm petakan`

```bash
./lppm petakan /infolppm/profil
./lppm petakan <path> --semua-opsi
```

| Argumen        | Keterangan                                         |
|----------------|----------------------------------------------------|
| `path`         | path atau URL penuh di bawah portal LPPM           |
| `--semua-opsi` | tulis seluruh pilihan `<select>`, bukan 12 pertama |

Mencetak dan menyimpan struktur halaman ke `data/form_<path>.json`: form beserta
field, label, dan pilihannya; kolom tiap tabel; tautan di bagian isi; endpoint
AJAX yang dipanggil skrip halaman; dan apakah halaman memakai DataTables. Hanya
melakukan GET. Nilai token CSRF dan isian password ditulis `<disamarkan>`.

## `./lppm turnitin`

```bash
./lppm turnitin
./lppm turnitin --json | jq '.jatah'
```

| Argumen  | Keterangan |
|----------|------------|
| `--json` | cetak JSON |

Membaca halaman `/turnitin` (hanya GET): jatah, pesan flash yang sedang tampil,
dan riwayat pengajuan. Contoh dengan data karangan:

```
Jatah cek Turnitin: 1 dari 2 terpakai, sisa 1
https://lppm.pradita.ac.id/turnitin

Riwayat (1):
  No | Judul Naskah | Tanggal Submit | No. Surat | Status | Aksi
  1 | Kerangka Kerja Fiktif untuk Kota Gotham | 20/10/2026 15:15 | - | Submit | Proses LPPM
```

Tautan di kolom Aksi dicetak di bawah barisnya (`-> teks: url`), begitu pula
elemen beratribut `data-*` seperti pemicu modal (`<button data-toggle="modal"
data-target="#...">`) beserta teks modal yang dituju. Isi kolom Aksi untuk
status selain Submit belum pernah teramati, jadi dicetak apa adanya.

Bentuk `--json` membawa `jatah` (`dipakai`, `total`, `sisa`, `teks`), `flash`
(`jenis`, `teks`), `ada_form`, dan `riwayat`. Tiap baris riwayat berisi `no`,
`judul`, `tanggal_submit` (ISO 8601, mis. `2026-10-20T15:15`),
`tanggal_submit_teks`, `no_surat` (`null` selama portal menulis `-`), `status`,
`aksi_teks`, `aksi_tautan`, `aksi_pemicu`, dan `ada_modal_perbaikan`.

## `./lppm turnitin ajukan`

```bash
./lppm turnitin ajukan --judul "Judul Naskah" --tautan "https://drive.google.com/file/d/.../view"
./lppm turnitin ajukan --judul "Judul Naskah" --tautan "https://drive.google.com/file/d/.../view" --kirim
```

| Argumen    | Wajib | Keterangan                                                          |
|------------|-------|---------------------------------------------------------------------|
| `--judul`  | ya    | judul naskah                                                        |
| `--tautan` | ya    | https ke `drive.google.com` atau `docs.google.com`                  |
| `--kirim`  |       | benar-benar mengirim dan memakai satu jatah; tanpa ini hanya uji coba |
| `--paksa`  |       | tetap ajukan walau judul yang sama sudah ada di riwayat             |
| `--json`   |       | cetak JSON                                                          |

Tanpa `--kirim` tidak ada yang dikirim. Judul dan tautan diperiksa, halaman
`/turnitin` dibaca untuk jatah, riwayat, dan form-nya, lalu rencana kirimannya
dicetak:

```
Uji coba: belum ada yang dikirim. Kiriman sungguhan memakai 1 dari 1 jatah yang tersisa. Pastikan berkas di Google Drive bisa dibuka LPPM.
Jatah: 1 dari 2 terpakai, sisa 1

POST https://lppm.pradita.ac.id/turnitin
  judul_naskah  Judul Naskah
  file_artikel  https://drive.google.com/file/d/.../view

Tidak ada yang dikirim. Tambahkan --kirim untuk mengajukan sungguhan (memakai 1 jatah).
```

Dengan `--kirim`, form dikirim sekali. Yang dicetak sesudahnya adalah pesan
flash dari portal, jatah terbaru, dan baris baru di riwayat. Kode keluarnya 1
kalau baris baru itu tidak terlihat; baca pesan flash-nya untuk sebabnya.

Pengajuan ditolak tanpa mengirim apa pun kalau:

- judulnya kosong, atau tautannya bukan https ke `drive.google.com` atau
  `docs.google.com` (diperiksa sebelum menghubungi portal);
- jatahnya habis (`--paksa` tidak melewati ini);
- judul yang sama sudah ada di riwayat, tanpa membedakan huruf besar dan kecil
  maupun spasi berlebih (kecuali dengan `--paksa`);
- form di halaman berubah, misalnya ada isian baru atau action-nya pindah dari
  `/turnitin`.

Kiriman tidak pernah diulang otomatis. Kalau portal membalas dengan galat, sesi
atau token CSRF-nya ternyata habis, atau pengalihannya mengarah ke luar portal,
pesannya diawali "Pengajuan sudah dikirim, tetapi hasilnya tidak bisa
dipastikan". Jalankan `./lppm turnitin` untuk memeriksa riwayat sebelum mencoba
lagi.

## Kredensial

Dibaca dari `.env` di akar proyek:

```
LPPM_WEBSITE=https://lppm.pradita.ac.id/login
LPPM_USERNAME=...
LPPM_PASSWORD=...
```

`LPPM_WEBSITE` menentukan halaman login sekaligus alamat portal. REST API bisa
menerima kredensial per permintaan; MCP selalu memakai setelan ini.
