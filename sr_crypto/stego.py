"""Kriteria 6: pesan GAMBAR diamankan dengan STEGANOGRAFI (LSB).

Konsep: bit paling tidak signifikan (LSB) dari tiap kanal warna (R,G,B) diganti
dengan bit pesan rahasia. Perubahan maksimal 1 dari 255 per kanal, jadi gambar
tampak identik di mata manusia.

Format data yang disisipkan:
    [ 4 byte magic "SRST" ][ 4 byte panjang payload (big-endian) ][ payload ]

Gambar hasil WAJIB disimpan sebagai PNG (lossless). JPEG akan merusak bit LSB.
"""
import io
import struct

import numpy as np
from PIL import Image, ImageOps

MAGIC = b"SRST"
HEADER_BITS = 64


class StegoError(Exception):
    pass


def _load_rgb(image_bytes: bytes) -> np.ndarray:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as exc:
        raise StegoError("File bukan gambar yang valid") from exc
    return np.array(img, dtype=np.uint8)


def capacity_bytes(image_bytes: bytes) -> int:
    arr = _load_rgb(image_bytes)
    return max(0, (arr.size - HEADER_BITS) // 8)


def embed(cover_bytes: bytes, payload: bytes) -> bytes:
    arr = _load_rgb(cover_bytes)
    flat = arr.reshape(-1)
    data = MAGIC + struct.pack(">I", len(payload)) + payload
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    if bits.size > flat.size:
        raise StegoError(
            "Gambar terlalu kecil: kapasitas {} byte, pesan {} byte".format(
                (flat.size - HEADER_BITS) // 8, len(payload)
            )
        )
    flat[: bits.size] = (flat[: bits.size] & 0xFE) | bits
    out = io.BytesIO()
    Image.fromarray(flat.reshape(arr.shape)).save(out, format="PNG")
    return out.getvalue()


def extract(stego_bytes: bytes) -> bytes:
    arr = _load_rgb(stego_bytes)
    flat = arr.reshape(-1)
    if flat.size < HEADER_BITS:
        raise StegoError("Gambar terlalu kecil")
    header = np.packbits(flat[:HEADER_BITS] & 1).tobytes()
    if header[:4] != MAGIC:
        raise StegoError("Tidak ada pesan tersembunyi pada gambar ini")
    length = struct.unpack(">I", header[4:8])[0]
    if HEADER_BITS + length * 8 > flat.size:
        raise StegoError("Header pesan rusak")
    body = flat[HEADER_BITS : HEADER_BITS + length * 8] & 1
    return np.packbits(body).tobytes()
