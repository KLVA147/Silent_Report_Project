"""Kriteria 3: SUPER ENKRIPSI untuk pesan teks.

    plaintext --(1) Extended Vigenere [klasik]--> --(2) AES-256-GCM [modern]--> base64

Dekripsi dilakukan terbalik: AES-GCM dulu, baru Vigenere.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .classic import vigenere_decrypt, vigenere_encrypt
from .keys import derive

_AAD = b"SR-text-v1"


def _keys(master: bytes):
    return derive(master, "text-vigenere", 16), derive(master, "text-aes256", 32)


def encrypt_text(plaintext: str, master: bytes) -> str:
    vkey, akey = _keys(master)
    stage1 = vigenere_encrypt(plaintext.encode("utf-8"), vkey)  # lapis klasik
    nonce = os.urandom(12)
    stage2 = AESGCM(akey).encrypt(nonce, stage1, _AAD)  # lapis modern
    return base64.b64encode(nonce + stage2).decode()


def decrypt_text(token: str, master: bytes) -> str:
    vkey, akey = _keys(master)
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    stage1 = AESGCM(akey).decrypt(nonce, ct, _AAD)
    return vigenere_decrypt(stage1, vkey).decode("utf-8")


def explain(plaintext: str, master: bytes) -> dict:
    """Menampilkan tiap tahap (untuk demo presentasi dan laporan)."""
    vkey, akey = _keys(master)
    stage1 = vigenere_encrypt(plaintext.encode("utf-8"), vkey)
    nonce = os.urandom(12)
    stage2 = AESGCM(akey).encrypt(nonce, stage1, _AAD)
    return {
        "plaintext": plaintext,
        "after_vigenere_hex": stage1.hex(),
        "after_aes_gcm_b64": base64.b64encode(nonce + stage2).decode(),
    }
