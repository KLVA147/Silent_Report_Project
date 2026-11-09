"""Biometrik WAJAH (kamera) - tambahan faktor login.

Alur:  frame kamera -> deteksi wajah (LBP cascade) -> potong + normalisasi cahaya
       -> histogram LBP seragam per sel (grid 6x6, 59 bin)  = "tanda tangan wajah"
       -> bandingkan dengan template terdaftar memakai jarak chi-square.

Yang disimpan hanya tanda tangan (vektor angka) yang dienkripsi dengan kunci DB (dongle),
BUKAN foto wajah.

Jujur untuk laporan: ini metode KLASIK (LBPH), bukan jaringan saraf. Cukup untuk demo dan
syarat tugas, tetapi lebih lemah daripada model deep learning, sensitif pada cahaya/pose, dan
TIDAK punya deteksi keaslian (liveness): foto wajah yang diperlihatkan ke kamera bisa lolos.
Itulah sebabnya wajah dipakai SEBAGAI TAMBAHAN password + sidik jari + dongle, bukan pengganti.
"""
import os
import struct
import sys

import cv2
import numpy as np
from skimage.feature import Cascade, local_binary_pattern

WORK_WIDTH = 640          # frame diperkecil ke lebar ini sebelum deteksi
MIN_FACE = 60             # sisi wajah minimum (piksel pada lebar kerja)
FACE_SIZE = 96
GRID = 6
BINS = 59                 # 'nri_uniform' untuk P=8
MIN_ENROLL_FRAMES = 3
MIN_LOGIN_FRAMES = 2
MAX_ENROLL_FRAMES = 8
MIN_SHARPNESS = 6.0       # variansi Laplacian pada potongan wajah 96x96
BRIGHTNESS_RANGE = (35, 225)
FACE_THRESHOLD = float(os.environ.get("SR_FACE_THRESHOLD", "0.18"))  # lihat tools/calibrate_face.py
ENROLL_CONSISTENCY = 0.22  # jarak maks sebuah foto pendaftaran ke foto 'tengah' (medoid); lebih jauh = dibuang
ENROLL_KEEP_RATIO = 0.70   # minimal sekian persen foto harus konsisten, jika tidak pendaftaran ditolak

_ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MODEL = os.path.join(_ROOT, "models", "lbpcascade_frontalface_opencv.xml")
_cascade = None
_WEIGHTS = np.outer([0.6, 1.0, 1.2, 1.2, 1.0, 0.6], [0.6, 1.0, 1.2, 1.2, 1.0, 0.6]).astype(np.float32).reshape(-1)
_WEIGHTS /= _WEIGHTS.sum()


class FaceError(Exception):
    """Masalah kualitas gambar. Pesannya aman ditampilkan ke pengguna (tidak membocorkan identitas)."""


def _detector() -> Cascade:
    global _cascade
    if _cascade is None:
        _cascade = Cascade(_MODEL)
    return _cascade


def _decode_gray(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FaceError("Gambar wajah tidak valid.")
    h, w = img.shape
    if w > WORK_WIDTH:
        img = cv2.resize(img, (WORK_WIDTH, int(h * WORK_WIDTH / w)), interpolation=cv2.INTER_AREA)
    return img


def detect(gray: np.ndarray):
    """Return kotak wajah terbesar (x, y, sisi). Error bila tidak ada atau lebih dari satu wajah."""
    h, w = gray.shape
    side = min(h, w)
    if side < MIN_FACE:
        raise FaceError("Gambar terlalu kecil.")
    found = _detector().detect_multi_scale(
        img=gray.astype(np.float64) / 255.0, scale_factor=1.2, step_ratio=1,
        min_size=(MIN_FACE, MIN_FACE), max_size=(side, side), min_neighbor_number=6)
    if len(found) == 0:
        raise FaceError("Wajah tidak terdeteksi. Hadapkan wajah lurus ke kamera dan perbaiki pencahayaan.")
    boxes = sorted(((int(f["c"]), int(f["r"]), int(f["width"]), int(f["height"])) for f in found),
                   key=lambda b: b[2] * b[3], reverse=True)
    x, y, bw, bh = boxes[0]
    for ox, oy, ow, oh in boxes[1:]:
        cx, cy = ox + ow / 2, oy + oh / 2
        inside = x <= cx <= x + bw and y <= cy <= y + bh
        if not inside and ow * oh >= 0.7 * bw * bh:
            raise FaceError("Terdeteksi lebih dari satu wajah. Pastikan hanya satu orang di depan kamera.")
    return x, y, max(bw, bh)


def _crop(gray: np.ndarray, box) -> np.ndarray:
    x, y, s = box
    pad = int(s * 0.12)
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(gray.shape[1], x + s + pad), min(gray.shape[0], y + s + pad)
    face = gray[y0:y1, x0:x1]
    face = cv2.resize(face, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA)
    face = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(face)
    return cv2.GaussianBlur(face, (3, 3), 0.8)


def signature(face96: np.ndarray) -> np.ndarray:
    lbp = local_binary_pattern(face96, 8, 1, method="nri_uniform").astype(np.int32)
    cell = FACE_SIZE // GRID
    out = np.zeros((GRID * GRID, BINS), dtype=np.float32)
    for r in range(GRID):
        for c in range(GRID):
            block = lbp[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell]
            hist = np.bincount(block.ravel(), minlength=BINS).astype(np.float32)
            out[r * GRID + c] = hist / max(hist.sum(), 1.0)
    return out


def extract_signature(image_bytes: bytes) -> np.ndarray:
    """Gambar -> tanda tangan wajah (36x59). Melempar FaceError bila kualitas tidak memadai."""
    gray = _decode_gray(image_bytes)
    box = detect(gray)
    face = _crop(gray, box)
    mean = float(face.mean())
    if not BRIGHTNESS_RANGE[0] <= mean <= BRIGHTNESS_RANGE[1]:
        raise FaceError("Pencahayaan terlalu gelap atau terlalu terang.")
    if cv2.Laplacian(face, cv2.CV_64F).var() < MIN_SHARPNESS:
        raise FaceError("Gambar wajah buram. Tahan kamera dan wajah tetap diam sebentar.")
    return signature(face)


def distance(a: np.ndarray, b: np.ndarray) -> float:
    """Chi-square simetris terbobot per sel; nilai 0 (identik) sampai 1 (sangat berbeda)."""
    num = (a - b) ** 2
    den = a + b + 1e-9
    per_cell = 0.5 * (num / den).sum(axis=1)
    return float((per_cell * _WEIGHTS).sum())


def enroll(frames) -> list:
    """Daftar 3-8 foto -> daftar tanda tangan.

    Foto yang tidak layak dibuang. Dari yang layak dicari foto 'tengah' (medoid); foto yang jauh dari
    medoid (mis. orang lain lewat di belakang) dibuang. Jika yang konsisten kurang dari 70% atau kurang
    dari 3 foto, pendaftaran ditolak supaya template tidak tercampur wajah berbeda.
    """
    sigs, last_err = [], None
    for raw in frames[:MAX_ENROLL_FRAMES]:
        try:
            sigs.append(extract_signature(raw))
        except FaceError as exc:
            last_err = exc
    if len(sigs) < MIN_ENROLL_FRAMES:
        raise FaceError("Hanya {} dari minimal {} foto wajah yang layak. {}".format(
            len(sigs), MIN_ENROLL_FRAMES, last_err or ""))
    n = len(sigs)
    dist = np.array([[distance(a, b) for b in sigs] for a in sigs])
    medoid = int(np.argmin(dist.mean(axis=1)))
    kept = [sigs[i] for i in range(n) if dist[medoid, i] <= ENROLL_CONSISTENCY]
    if len(kept) < MIN_ENROLL_FRAMES or len(kept) < ENROLL_KEEP_RATIO * n:
        raise FaceError("Foto wajah tidak konsisten (ada lebih dari satu orang atau posisi berubah-ubah). "
                        "Ulangi pengambilan dengan pencahayaan yang baik.")
    return kept


def usable_signatures(frames, minimum: int):
    """Ambil tanda tangan dari frame yang layak. Perlu minimal 'minimum' frame, jika tidak FaceError."""
    sigs, last_err = [], None
    for raw in frames[:MAX_ENROLL_FRAMES]:
        try:
            sigs.append(extract_signature(raw))
        except FaceError as exc:
            last_err = exc
    if len(sigs) < minimum:
        raise last_err or FaceError("Foto wajah tidak ada. Nyalakan kamera lalu ambil foto wajah.")
    return sigs


def score(template: list, probes: list) -> float:
    """Median dari (jarak terdekat ke tiap template) untuk setiap frame probe. Makin kecil makin mirip."""
    per_frame = [min(distance(t, p) for t in template) for p in probes]
    return float(np.median(per_frame))


def verify(template: list, probes: list):
    s = score(template, probes)
    return s <= FACE_THRESHOLD, s


def template_to_bytes(sigs: list) -> bytes:
    arr = np.stack(sigs).astype(np.float16)
    return struct.pack(">H", len(sigs)) + arr.tobytes()


def template_from_bytes(raw: bytes) -> list:
    n = struct.unpack(">H", raw[:2])[0]
    arr = np.frombuffer(raw[2:], dtype=np.float16).astype(np.float32).reshape(n, GRID * GRID, BINS)
    return [arr[i] for i in range(n)]
