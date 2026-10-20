# Contoh prompt untuk MCP LPPM

Permintaan siap salin untuk asisten AI setelah server `lppm-mcp` didaftarkan
(lihat [../docs/MCP.md](../docs/MCP.md)). Kredensial diambil sendiri dari
`.env`; asisten tidak perlu dan tidak boleh menanyakan kata sandi.

## Memeriksa akses

```
Cek apakah login portal LPPM saya masih jalan.
```

```
Menu apa saja yang ada di portal LPPM setelah saya login? Kelompokkan per grup.
```

## Membaca halaman

```
Baca halaman profil LPPM (/infolppm/profil) dan ringkas tugas lembaganya.
```

```
Buka menu penelitian di portal LPPM dan tampilkan tabelnya: judul, ketua,
tahun, dan status tiap penelitian saya.
```

```
Dari tabel penelitian tadi, buka halaman detail penelitian yang paling baru
dan sebutkan anggota serta skemanya.
```

## Cek Turnitin

```
Berapa sisa jatah cek Turnitin saya? Tampilkan riwayat pengajuannya beserta
status dan nomor suratnya.
```

```
Saya mau mengajukan naskah "Judul Naskah Saya" untuk cek Turnitin, tautannya
https://drive.google.com/file/d/.../view. Jalankan uji coba dulu dan tunjukkan
rencananya beserta sisa jatah. Jangan kirim sebelum saya setuju.
```

## Memetakan menu baru

```
Saya mau menambah alat untuk surat tugas. Cari menunya di portal LPPM, baca
halamannya sebagai tabel, lalu sebutkan kolom, tautan di tiap baris, dan apakah
isinya dimuat lewat AJAX.
```

## Yang perlu diketahui

- `cek_login`, `daftar_menu`, `ambil_halaman`, dan `daftar_turnitin` hanya
  membaca. `ajukan_turnitin` memakai satu jatah cek Turnitin kalau dijalankan
  dengan `uji_coba=False`; bawaannya uji coba.
- Tautan aksi seperti hapus, setujui, atau logout ditolak, walaupun muncul di
  `_tautan` sebuah baris tabel.
- Alat khusus surat tugas, penelitian, PkM, dan unduh dokumen belum ada. Untuk
  sementara isinya dibaca lewat `ambil_halaman`.
