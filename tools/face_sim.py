"""Simulator webcam untuk uji tanpa kamera: variasi nyata dari foto wajah yang tersedia.

Dua identitas nyata yang tersedia offline: 'A' (foto astronot, scikit-image) dan 'B' (Grace Hopper,
contoh matplotlib). Variasi: geser, rotasi, skala, gamma/cahaya, noise sensor, blur, kompresi JPEG.
CATATAN: variasi dari SATU foto lebih mudah dikenali daripada variasi antar-sesi sungguhan, sehingga
hasil di sini bukan pengganti kalibrasi dengan wajah asli (lihat tools/calibrate_face.py).
"""
import os

import cv2
import numpy as np


def _load(name: str) -> np.ndarray:
    if name == "A":
        import skimage.data as d
        return cv2.cvtColor(d.astronaut(), cv2.COLOR_RGB2BGR)
    import matplotlib
    p = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "sample_data", "grace_hopper.jpg")
    return cv2.imread(p)


def base_frame(name: str, size=(640, 480)) -> np.ndarray:
    """Foto diletakkan di bingkai 4:3 seperti keluaran webcam (latar polos)."""
    img = _load(name)
    w, h = size
    scale = min(w / img.shape[1], h / img.shape[0]) * 1.0
    img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    canvas = np.full((h, w, 3), 128, np.uint8)
    y0, x0 = (h - img.shape[0]) // 2, (w - img.shape[1]) // 2
    canvas[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
    return canvas


def variant(name: str, seed: int, strength: float = 1.0, size=(640, 480)) -> bytes:
    """Satu 'frame webcam' (JPEG) dengan variasi acak berdasarkan seed."""
    rng = np.random.RandomState(seed)
    img = base_frame(name, size)
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-5, 5) * strength, 1 + rng.uniform(-0.06, 0.06) * strength)
    m[:, 2] += (rng.uniform(-0.03, 0.03) * w * strength, rng.uniform(-0.03, 0.03) * h * strength)
    img = cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REPLICATE)
    gamma = 1 + rng.uniform(-0.25, 0.25) * strength
    img = (255 * (img / 255.0) ** gamma).astype(np.float32)
    img = img * (1 + rng.uniform(-0.12, 0.12) * strength) + rng.uniform(-12, 12) * strength
    img += rng.randn(*img.shape) * rng.uniform(2, 6) * strength
    img = np.clip(img, 0, 255).astype(np.uint8)
    if rng.rand() < 0.4:
        img = cv2.GaussianBlur(img, (3, 3), 0.7)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(rng.randint(60, 92))])
    return buf.tobytes()


def session(name: str, seed0: int, n: int, strength: float = 1.0):
    return [variant(name, seed0 + i, strength) for i in range(n)]
