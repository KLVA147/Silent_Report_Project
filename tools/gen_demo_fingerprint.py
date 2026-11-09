"""Membuat gambar sidik jari DEMO (sintetis) untuk menguji login biometrik.

    python tools/gen_demo_fingerprint.py demo_fingerprints

Menghasilkan:
  jari_A_daftar.png  -> dipakai saat registrasi
  jari_A_login.png   -> jari yang SAMA, discan ulang (noise + rotasi kecil) -> harus lolos
  jari_B.png         -> jari ORANG LAIN -> harus ditolak
"""
import os
import sys

import cv2
import numpy as np


def make_fingerprint(seed: int, size: int = 300) -> np.ndarray:
    rng = np.random.RandomState(seed)
    noise = rng.randn(size, size).astype(np.float32)
    field = cv2.GaussianBlur(noise, (0, 0), 18)
    field = field / (np.abs(field).max() + 1e-6)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cy = cx = size / 2
    radius = np.sqrt((xx - cx) ** 2 + ((yy - cy) * 0.8) ** 2)
    phase = radius * 0.55 + field * 14.0
    ridges = (np.sin(phase) * 0.5 + 0.5)
    detail = cv2.GaussianBlur(rng.randn(size, size).astype(np.float32), (0, 0), 1.2)
    ridges = np.clip(ridges * 0.8 + detail * 0.35, 0, 1)
    mask = (radius < size * 0.46).astype(np.float32)
    img = 255 - (ridges * mask * 200 + (1 - mask) * 0)
    img = np.where(mask > 0, 255 - ridges * 210, 235)
    return np.clip(img, 0, 255).astype(np.uint8)


def rescan(img: np.ndarray, seed: int = 99) -> np.ndarray:
    """Simulasi scan ulang jari yang sama: rotasi kecil, geser, noise sensor."""
    rng = np.random.RandomState(seed)
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), 3.0, 1.0)
    m[:, 2] += (3, -2)
    out = cv2.warpAffine(img, m, (w, h), borderValue=235)
    out = out.astype(np.float32) + rng.randn(h, w) * 6
    return np.clip(out, 0, 255).astype(np.uint8)


def main(outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    a = make_fingerprint(seed=1234)
    cv2.imwrite(os.path.join(outdir, "jari_A_daftar.png"), a)
    cv2.imwrite(os.path.join(outdir, "jari_A_login.png"), rescan(a))
    cv2.imwrite(os.path.join(outdir, "jari_B.png"), make_fingerprint(seed=777))
    print("Gambar demo dibuat di", outdir)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo_fingerprints")
