# Panduan Pengguna SilentReport

Tidak perlu VS Code, tidak perlu mengetik perintah.

## Membuka aplikasi
1. Colok **flashdisk dongle** (jika sudah punya).
2. Klik dua kali **SilentReport** (`SilentReport.exe`, atau `SilentReport.bat` di Windows).
3. Jendela aplikasi terbuka sendiri. Jangan tutup jendela hitam di belakangnya selama aplikasi dipakai.

Pertama kali dipakai pada komputer baru, `SilentReport.bat` memasang kebutuhan dirinya sendiri dan butuh internet
beberapa menit. Setelah itu tidak perlu internet. Dengan `SilentReport.exe` hasil build, tidak ada pemasangan apa pun.

## Pemakaian pertama (hanya sekali, oleh pengelola)
1. Colok flashdisk yang akan menjadi dongle.
2. Aplikasi menampilkan **Pengaturan awal**. Pilih flashdisk, lalu klik **Buat dongle**.
3. **Catat kode undangan petugas** yang tampil (hanya muncul sekali).
4. Buat salinan cadangan file `.silentreport.key` dari flashdisk ke flashdisk lain. Jika kunci hilang, data tidak bisa dibuka.

## Mengirim laporan dan barang bukti
1. Colok dongle. Jika belum, aplikasi menampilkan layar **terkunci** dan terbuka otomatis begitu dongle terdeteksi.
2. **Daftar** dengan nama samaran, password, gambar sidik jari, dan **foto wajah lewat kamera**:
   klik **Nyalakan kamera**, pilih **Izinkan** pada pertanyaan browser, hadap lurus ke kamera di tempat terang
   (hanya satu orang di layar), lalu klik **Ambil foto wajah**. Beberapa foto diambil otomatis selama beberapa detik.
3. **Masuk** dengan password, sidik jari, dan wajah (ambil foto wajah dengan cara yang sama).
   Foto wajah tidak disimpan, hanya ciri wajah yang dienkripsi.
4. **Buat laporan**, isi uraian, lampirkan file atau foto bukti, lalu **Kirim laporan**.

## Menutup aplikasi
Klik **Tutup aplikasi** di bagian bawah halaman. Setelah itu dongle boleh dicabut.
Mencabut dongle saat aplikasi masih terbuka langsung mengunci aplikasi. Colok lagi untuk melanjutkan.

## Masalah umum
| Gejala | Penyebab dan solusi |
|---|---|
| Layar terkunci terus padahal flashdisk terpasang | Itu bukan flashdisk dongle yang benar, atau file `.silentreport.key` terhapus. Pakai flashdisk yang dipakai saat pengaturan awal. |
| Flashdisk tidak muncul di Pengaturan awal | Klik "Tampilkan semua drive". |
| Login sidik jari ditolak | Gunakan gambar sidik jari yang sama jenisnya dengan yang didaftarkan. |
| "Wajah tidak terdeteksi" | Cari tempat lebih terang, hadap lurus ke kamera, dekatkan wajah, dan pastikan hanya satu orang di layar. |
| "Izin kamera ditolak" | Klik ikon kamera/gembok di bilah alamat lalu izinkan kamera. Atau pakai jalur "Unggah foto wajah" di bawah kamera. |
| Login wajah sering ditolak | Daftar ulang wajah di cahaya yang sama dengan saat login. Pengelola dapat mengkalibrasi ambang (lihat README bagian 5c). |
| Port sibuk | Tutup SilentReport yang lain, atau jalankan ulang. |
