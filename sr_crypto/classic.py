"""Algoritma KLASIK: Extended Vigenere Cipher (modulo 256 pada byte).

Vigenere biasa hanya untuk huruf A-Z. Versi extended bekerja pada byte (0-255)
sehingga semua karakter (huruf kecil, angka, tanda baca, emoji, bahasa Indonesia)
tetap bisa dienkripsi dan didekripsi tanpa kehilangan data.

    C[i] = (P[i] + K[i mod len(K)]) mod 256
    P[i] = (C[i] - K[i mod len(K)]) mod 256
"""


def vigenere_encrypt(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("Kunci Vigenere tidak boleh kosong")
    k = len(key)
    return bytes((b + key[i % k]) % 256 for i, b in enumerate(data))


def vigenere_decrypt(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("Kunci Vigenere tidak boleh kosong")
    k = len(key)
    return bytes((b - key[i % k]) % 256 for i, b in enumerate(data))
