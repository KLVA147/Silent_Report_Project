"""Kriteria 5: pesan PENTING dienkripsi pada basisdata.

Kolom pesan yang ditandai "penting" dibungkus lagi dengan AES-256-GCM memakai
kunci DATABASE (terpisah dari kunci teks/file). Jadi isi database untuk pesan
penting adalah lapisan DB di atas lapisan super-enkripsi teks.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .keys import derive

_AAD = b"SR-db-v1"


def encrypt_field(value: str, master: bytes) -> str:
    key = derive(master, "db-aes256", 32)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, value.encode("utf-8"), _AAD)
    return base64.b64encode(nonce + ct).decode()


def decrypt_field(token: str, master: bytes) -> str:
    key = derive(master, "db-aes256", 32)
    raw = base64.b64decode(token)
    return AESGCM(key).decrypt(raw[:12], raw[12:], _AAD).decode("utf-8")
