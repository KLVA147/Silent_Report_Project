"""Kriteria 4: pesan FILE dienkripsi dengan algoritma yang BERBEDA dari teks.

Teks  : Vigenere + AES-256-GCM
File  : ChaCha20-Poly1305 (stream cipher modern, kunci sendiri)
"""
import os

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from .keys import derive

_AAD = b"SR-file-v1"


def encrypt_bytes(data: bytes, master: bytes) -> bytes:
    key = derive(master, "file-chacha20", 32)
    nonce = os.urandom(12)
    return nonce + ChaCha20Poly1305(key).encrypt(nonce, data, _AAD)


def decrypt_bytes(blob: bytes, master: bytes) -> bytes:
    key = derive(master, "file-chacha20", 32)
    return ChaCha20Poly1305(key).decrypt(blob[:12], blob[12:], _AAD)
