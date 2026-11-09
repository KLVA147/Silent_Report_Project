# SilentReport: Aplikasi Pelaporan Anonim Berbasis Kriptografi

Chat aman antara **pelapor** (anonim, pakai nama samaran) dan **petugas** (mis. inspektorat kampus)
untuk melaporkan korupsi, perundungan, atau pelecehan. Dibuat untuk memenuhi 7 kriteria Tugas Akhir Kriptografi.

> **Pengguna biasa:** cukup klik dua kali `SilentReport.exe` / `SilentReport.bat`. Lihat `PANDUAN_PENGGUNA.md`.
> Bagian 2-4 di bawah hanya untuk pengembang.

## 0. Membuat SilentReport.exe (sekali, oleh pengembang, di Windows)

```
build_exe.bat      -> menghasilkan SilentReport.exe (satu file, tanpa perlu Python di komputer pengguna)
```
Bagikan `SilentReport.exe` saja. Data pengguna disimpan di `%APPDATA%\SilentReport`, bukan di folder program.
Linux/macOS: `./build_exe.sh` (hasil di `dist/`). Catatan: build `.exe` harus dijalankan di Windows.

## 1. Pemetaan kriteria dosen ke kode

| # | Kriteria dosen | Implementasi | File / fungsi |
|---|---|---|---|
| 1 | Login biometrik, aplikasi hanya hidup dengan dongle | Biometrik **dua modalitas**: sidik jari (ORB + BFMatcher) dan **wajah lewat kamera** (histogram LBP + jarak chi-square). Aplikasi **terkunci (HTTP 423)** tanpa dongle USB, juga bila dongle dicabut saat berjalan | `sr_crypto/biometric.py`, `sr_crypto/face.py`, `sr_crypto/dongle.py`, `app.py` (`guard`, `login`) |
| 2 | Login memakai algoritma kriptografi | Password di-hash **scrypt + salt acak** (n=2^14), dibandingkan dengan `hmac.compare_digest` | `sr_crypto/passwords.py` |
| 3 | Pesan teks: super enkripsi (klasik + modern) | **Extended Vigenere** (klasik) lalu **AES-256-GCM** (modern) | `sr_crypto/classic.py`, `sr_crypto/textcrypto.py` |
| 4 | Pesan file: kriptografi beda dari teks | **ChaCha20-Poly1305** dengan kunci sendiri | `sr_crypto/filecrypto.py` |
| 5 | Pesan penting dienkripsi di basisdata | Pesan bertanda "penting" dibungkus lagi **AES-256-GCM kunci DB** (terpisah dari kunci teks) | `sr_crypto/dbcrypto.py`, `app.py` (`store_message`) |
| 6 | Pesan gambar: steganografi | **LSB** pada kanal R,G,B; catatan rahasia dienkripsi lalu disisipkan ke foto bukti, disimpan PNG | `sr_crypto/stego.py` |
| 7 | Aset penting: blockchain sederhana | Rantai blok SHA-256 + Proof-of-Work (3 nol) untuk **chain of custody barang bukti** | `sr_crypto/blockchain.py`, `app.py` (`add_block`) |

**Manajemen kunci:** satu master secret 32 byte ada di dongle USB. Semua kunci diturunkan dengan **HKDF-SHA256**
dengan label berbeda (`text-vigenere`, `text-aes256`, `file-chacha20`, `db-aes256`). Tanpa dongle, database dan file
di disk tidak bisa dibuka.

## 2. Instalasi

Butuh Python 3.10+.

```bash
python -m venv venv
# Windows:  venv\Scripts\activate        Linux/Mac:  source venv/bin/activate
pip install -r requirements.txt
```

## 3. Membuat dongle (sekali saja)

```bash
# Windows (flashdisk E:)   : python make_dongle.py E:\
# Linux  (flashdisk)       : python make_dongle.py /media/$USER/NAMA_FLASHDISK
# Uji coba tanpa flashdisk : python make_dongle.py ./fake_usb
```

Ini menulis file `.silentreport.key` ke flashdisk dan mendaftarkan hash-nya di `data/dongle.sha256`.
Menjalankan ulang akan mengganti kunci, sehingga **data lama tidak terbaca**. Simpan flashdisknya baik-baik.

## 4. Menjalankan

```bash
# Windows PowerShell:  $env:SR_DONGLE_PATH="E:\"      (tidak perlu jika flashdisk terdeteksi otomatis)
# Linux/Mac:           export SR_DONGLE_PATH=./fake_usb
python app.py
```

Buka http://127.0.0.1:5000. Konsol menampilkan **kode undangan petugas** (juga tersimpan di `data/officer_code.txt`).
Tanpa dongle, aplikasi tetap menyala tetapi **seluruh halaman terkunci** (HTTP 423) dan terbuka otomatis saat dongle terpasang. Pada pemakaian pertama, wizard `/setup` membuat dongle.

## 5. Skenario demo untuk presentasi (urut)

Gambar sidik jari demo ada di `demo_fingerprints/` (buat ulang dengan `python tools/gen_demo_fingerprint.py`).

1. **Dongle:** buka aplikasi tanpa dongle (layar **Aplikasi terkunci**). Colok dongle: aplikasi terbuka otomatis. Cabut lagi: terkunci kembali.
2. **Registrasi pelapor:** nama samaran `pelapor1`, sidik jari `jari_A_daftar.png`.
3. **Login:**
   - `jari_A_login.png` (jari sama, scan ulang) **berhasil**.
   - `jari_B.png` (jari orang lain) **ditolak**.
   - Password salah **ditolak**.
4. **Buat laporan:** isi teks, centang "penting", lampirkan satu file (PDF/dokumen) dan satu foto beserta catatan rahasia.
5. **Registrasi petugas** (jendela incognito), peran Petugas, masukkan kode undangan, sidik jari `jari_B.png`. Login sebagai petugas.
6. **Menu "Inspeksi kripto":** tunjukkan isi **mentah** database (ciphertext, hash scrypt, template terenkripsi). Coba demo Vigenere lalu AES. Ini bukti kuat untuk dosen.
7. **Steganografi:** buka laporan, klik **Ekstrak pesan tersembunyi** pada foto. Bandingkan foto asli dan hasil stego (tampak sama).
8. **Blockchain:** menu **Rantai bukti** menampilkan blok, hash, dan status VALID. Ubah status laporan, unduh bukti, lalu lihat blok baru bertambah.
9. **Pembuktian pemalsuan:** ubah satu blok langsung di database (`UPDATE blocks SET data=...`), muat ulang menu Rantai bukti, status berubah **TIDAK VALID**.

## 5b. Fitur antarmuka

- Tema terang/gelap (tombol di header, pilihan diingat), responsif untuk HP dan laptop.
- Form: validasi langsung, tampilkan/sembunyikan password, indikator kekuatan password, penghitung karakter, tombol berstatus loading.
- Unggah file: seret-lepas, pratinjau gambar, pembatasan ukuran.
- Detail laporan: gelembung percakapan, progres status, kirim dengan Ctrl+Enter, perbesar foto bukti, salin hash.
- Daftar laporan: statistik ringkas, pencarian dan filter status.
- Rantai bukti: tampilan timeline dengan penanda blok yang rusak.
- Layar "Aplikasi terkunci" saat dongle dicabut. Semua fitur tetap berfungsi dasar bila JavaScript mati.

## 5c. Biometrik wajah (kamera)

Login kini **tiga faktor**: password, sidik jari, dan wajah (selain dongle sebagai syarat aplikasi bisa dipakai).

**Alur:** browser meminta izin kamera (`getUserMedia`, hanya jalan di `127.0.0.1`/localhost atau HTTPS) lalu mengambil
5-6 foto otomatis. Server mendeteksi wajah (LBP cascade), memotong dan menormalkan cahaya, lalu menghitung histogram
LBP seragam per sel (grid 6x6 x 59 bin) sebagai **tanda tangan wajah**. Yang disimpan di database hanya tanda tangan itu,
**dienkripsi AES-256-GCM dengan kunci DB** (dari dongle). **Foto tidak disimpan.** Saat login, jarak chi-square ke template
dihitung; lolos bila median jarak <= ambang (bawaan 0,18).

**Kontrol kualitas:** menolak gambar tanpa wajah, lebih dari satu wajah, terlalu gelap/terang, atau buram, dengan pesan yang jelas.
Saat pendaftaran, foto yang menyimpang dari foto "tengah" dibuang dan pendaftaran ditolak bila kurang dari 70% foto konsisten
(mencegah dua orang tercampur dalam satu template). Pesan kualitas tidak bergantung pada akun, jadi tidak membocorkan apakah
nama pengguna ada. Akun dari versi lama (tanpa template wajah) mendaftarkan wajahnya otomatis pada login pertama.

**Kalibrasi ambang dengan wajah asli (sangat disarankan sebelum demo):**
```bash
# foto_uji/budi/*.jpg  foto_uji/sari/*.jpg  ... (min. 2 orang, 8+ foto/orang, cahaya dan waktu berbeda)
python tools/calibrate_face.py foto_uji
# lalu pasang ambang yang disarankan, mis.:  $env:SR_FACE_THRESHOLD="0.182"   (Linux/Mac: export ...)
```

**Hasil uji yang sudah saya jalankan (jujur apa adanya):** hanya ada **dua wajah nyata** di lingkungan pengembangan
(foto astronot dan Grace Hopper) dan variasinya disimulasikan dari satu foto per orang (geser, rotasi, skala, cahaya, noise,
kompresi JPEG; `tools/face_sim.py`). Pada simulasi itu orang yang sama berjarak maks 0,14 dan orang berbeda min 0,22, tanpa salah
terima atau salah tolak pada 480 sesi uji. **Angka ini bukan akurasi sebenarnya**: variasi antar-sesi nyata (hari berbeda,
ekspresi, kacamata) lebih besar, dan dengan banyak orang akan ada pasangan wajah yang mirip. Alur kamera diuji di Chromium dengan
kamera virtual (registrasi, login wajah sama berhasil, wajah orang lain ditolak, izin kamera ditolak, unggah foto cadangan).

## 6. Pengujian otomatis

```bash
python -m unittest tests.test_criteria -v
```

56 tes memverifikasi: dongle dicabut, sidik jari asli/palsu, hash scrypt + salt, dua lapis enkripsi teks (dibuka manual per lapis),
file ChaCha20 beda dari AES, lapisan DB pada pesan penting, steganografi (maks. perubahan piksel = 1), blockchain valid dan
pemalsuan terdeteksi, serta CSRF dan kontrol akses.

## 7. Struktur project

```
silentreport/
  launcher.py            peluncur pengguna akhir (port, jendela, folder data)
  SilentReport.bat/.sh/.command   klik dua kali untuk membuka
  build_exe.bat/.sh      membuat program mandiri dengan PyInstaller
  PANDUAN_PENGGUNA.md    panduan untuk pengguna awam
  app.py                 aplikasi Flask (rute, alur, kontrol akses)
  db.py                  skema SQLite
  make_dongle.py         pembuat dongle
  sr_crypto/             semua modul kriptografi dan biometrik (satu file per kriteria)
  models/                detektor wajah (LBP cascade, lisensi BSD)
  static/js/camera.js    pengambilan foto wajah lewat kamera
  tools/calibrate_face.py  kalibrasi ambang wajah dengan foto asli
  tools/face_sim.py      simulator webcam untuk pengujian
  templates/             tampilan HTML (Jinja2)
  static/css/app.css     gaya antarmuka (tema terang/gelap, responsif)
  static/js/app.js       interaksi sisi klien (tanpa library)
  icons.py               ikon SVG garis (tanpa emoji)
  tools/gen_demo_fingerprint.py   pembuat sidik jari demo
  tests/test_criteria.py          tes 7 kriteria
  demo_fingerprints/     gambar sidik jari demo
  data/                  database dan file terenkripsi (dibuat otomatis)
```

## 8. Keterbatasan (tulis jujur di laporan)

- **Wajah tanpa deteksi keaslian (liveness):** foto atau layar HP berisi wajah yang diperlihatkan ke kamera dapat lolos. Karena itu wajah dipakai
  **bersama** password, sidik jari, dan dongle, bukan sebagai satu-satunya faktor. Peningkatan: tantangan acak (kedip/tengok), kamera inframerah, atau model anti-spoofing.
- **Wajah memakai metode klasik (LBPH)**, bukan jaringan saraf: lebih sensitif pada cahaya dan pose, dan kurang akurat dibanding model deep learning (mis. SFace/ArcFace).
  Ambang bawaan belum dikalibrasi dengan banyak orang nyata (lihat bagian 5c).
- **Kamera butuh konteks aman:** berfungsi di `127.0.0.1` dan HTTPS. Mengakses dari komputer lain lewat `http://IP` biasa akan diblokir browser.

- **Biometrik:** tanpa sensor fisik, sidik jari berupa **file gambar**. Gambar demo bersifat sintetis. Untuk sensor asli, ganti sumber gambar dengan SDK sensor atau WebAuthn. Ambang kecocokan (60) diukur pada data sintetis: jari sama minimum ~100, jari berbeda maksimum ~35. Pada sidik jari nyata ambang perlu dikalibrasi ulang.
- **Dongle:** berbasis file kunci. Jika file disalin ke flashdisk lain, tetap dianggap valid. Peningkatan: ikat ke serial hardware USB.
- **Steganografi LSB** sekuensial. Rentan jika gambar dikompres ulang (JPEG) atau dianalisis steganalisis. Peningkatan: urutan piksel acak berbasis kunci.
- **Blockchain** berjalan pada satu node (tanpa jaringan peer-to-peer). Fungsinya sebagai rantai bukti yang tahan-ubah, bukan konsensus terdistribusi. Penyerang dengan akses penuh ke database bisa menghitung ulang seluruh rantai. Peningkatan: jangkar hash terakhir ke pihak ketiga.
- **Vigenere** hanya lapisan klasik sesuai syarat tugas. Keamanan sebenarnya datang dari AES-256-GCM.
- Server untuk demo/lokal (`127.0.0.1`, tanpa HTTPS). Untuk produksi: HTTPS, WSGI server, rotasi kunci.
- Metadata (ukuran pesan, waktu, nama samaran) tidak disembunyikan.

## 9. Saran pembagian kerja (kelompok 1-3 orang)

- Orang 1: dongle, biometrik, login (kriteria 1-2) dan UI.
- Orang 2: super enkripsi teks, enkripsi file, enkripsi DB (kriteria 3-5).
- Orang 3: steganografi, blockchain, pengujian dan laporan (kriteria 6-7).
