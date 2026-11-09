# Outline Laporan Tugas Akhir: SilentReport

**BAB I Pendahuluan**
1.1 Latar belakang: pelapor korupsi dan perundungan takut identitas dan bukti bocor.
1.2 Rumusan masalah: bagaimana merancang aplikasi pelaporan yang menjaga kerahasiaan, keaslian, dan integritas.
1.3 Tujuan dan manfaat.
1.4 Batasan masalah (aplikasi web lokal, sidik jari berupa gambar, blockchain satu node).

**BAB II Landasan Teori**
2.1 Kriptografi klasik: Vigenere Cipher (dan versi extended modulo 256).
2.2 Kriptografi modern: AES-256-GCM, ChaCha20-Poly1305 (AEAD), super enkripsi.
2.3 Fungsi hash dan password hashing: SHA-256, scrypt, salt.
2.4 Derivasi kunci: HKDF.
2.5 Steganografi: LSB.
2.6 Blockchain: blok, hash, Proof-of-Work, chain of custody.
2.7 Biometrik: ekstraksi fitur ORB, pencocokan fitur, FAR/FRR.
2.8 Dongle (hardware token).

**BAB III Analisis dan Perancangan**
3.1 Analisis kebutuhan (7 kriteria dosen).
3.2 Arsitektur sistem (diagram blok: Browser, Flask, modul kripto, SQLite, dongle).
3.3 Diagram alur: registrasi, login (password + sidik jari + dongle), kirim laporan, ekstraksi stego, validasi blockchain.
3.4 Rancangan basisdata (ERD: users, reports, messages, attachments, blocks).
3.5 Manajemen kunci (tabel kunci dan label HKDF).
3.6 Model ancaman: apa yang dilindungi dan dari siapa.

**BAB IV Implementasi**
4.1 Lingkungan (Python, Flask, cryptography, OpenCV, Pillow).
4.2 Implementasi per kriteria: potongan kode dan penjelasan (lihat tabel pemetaan di README).
4.3 Tampilan aplikasi (screenshot): kunci, registrasi, login, laporan, inspeksi kripto, rantai bukti.

**BAB V Pengujian dan Pembahasan**
5.1 Pengujian fungsional per kriteria (hasil `python -m unittest`: 31 tes).
5.2 Pengujian keamanan: ciphertext tidak mengandung plaintext, tamper file ditolak (tag AEAD), pemalsuan blockchain terdeteksi, CSRF, kontrol akses.
5.3 Pengujian biometrik: tabel skor jari sama vs berbeda, penentuan ambang, FAR/FRR.
5.4 Pengujian steganografi: selisih piksel maksimum 1, tabel kapasitas, perbandingan gambar asli vs stego (PSNR bisa dihitung).
5.5 Keterbatasan dan saran pengembangan (lihat README bagian 8).

**BAB VI Penutup**: kesimpulan dan saran.

**Daftar Pustaka**
**Lampiran**: kode lengkap, hasil tes, screenshot, pembagian tugas anggota.

---
Tips presentasi (4 pertemuan terakhir): pertemuan 1 latar belakang dan rancangan, 2 demo kriteria 1-3, 3 demo kriteria 4-7, 4 pengujian dan tanya jawab.
