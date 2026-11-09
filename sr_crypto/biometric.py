"""Kriteria 1 (bagian biometrik): login dengan sidik jari.

Pendekatan: gambar sidik jari -> grayscale 300x300 -> CLAHE -> fitur ORB (OpenCV).
Template (deskriptor ORB) disimpan terenkripsi di database. Saat login, fitur
gambar baru dicocokkan (BFMatcher + Lowe ratio test). Jika jumlah kecocokan
>= THRESHOLD maka dianggap pemilik yang sama.

Catatan jujur untuk laporan: tanpa sensor fingerprint fisik, gambar sidik jari
diunggah sebagai file (bisa hasil scan/foto jari, atau gambar demo dari
tools/gen_demo_fingerprint.py). Untuk sensor asli, ganti sumber gambar dengan
SDK sensor atau WebAuthn/Windows Hello; alur pencocokan templatenya sama.
"""
import cv2
import numpy as np

SIZE = 300
THRESHOLD = 60  # terukur: jari sama min ~100, jari berbeda maks ~35 (lihat README)
RATIO = 0.75
MIN_FEATURES = 40


class BiometricError(Exception):
    pass


def extract_template(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise BiometricError("File sidik jari bukan gambar yang valid")
    img = cv2.resize(img, (SIZE, SIZE))
    img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(img)
    orb = cv2.ORB_create(nfeatures=500, fastThreshold=10)
    _, desc = orb.detectAndCompute(img, None)
    if desc is None or len(desc) < MIN_FEATURES:
        raise BiometricError("Fitur sidik jari terlalu sedikit, gunakan gambar yang lebih jelas")
    return desc


def match_score(template: np.ndarray, probe: np.ndarray) -> int:
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(probe, template, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < RATIO * p[1].distance]
    return len(good)


def is_match(template: np.ndarray, probe: np.ndarray) -> bool:
    return match_score(template, probe) >= THRESHOLD


def template_to_bytes(desc: np.ndarray) -> bytes:
    return desc.astype(np.uint8).tobytes()


def template_from_bytes(raw: bytes) -> np.ndarray:
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 32)
