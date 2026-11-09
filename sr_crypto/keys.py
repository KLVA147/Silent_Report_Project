"""Derivasi kunci.

Satu "master secret" (32 byte) disimpan di dongle USB. Semua kunci aplikasi
diturunkan dari master secret itu dengan HKDF-SHA256 dan label berbeda, sehingga:
  - kunci teks, kunci file, dan kunci database SALING BERBEDA,
  - tanpa dongle, tidak ada kunci -> data di database/disk tidak bisa dibuka.
"""
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def derive(master: bytes, label: str, length: int = 32) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=b"SilentReport-v1",
        info=label.encode("utf-8"),
    ).derive(master)
