"""Kriteria 1 (bagian dongle): aplikasi hanya hidup jika dongle USB terpasang.

Dongle = flashdisk berisi file kunci `.silentreport.key` (secret acak 32 byte).
Server hanya menyimpan SHA-256 dari secret itu (dongle.sha256) untuk memverifikasi.
Secret yang sama menjadi MASTER KEY: tanpa dongle, data tidak bisa didekripsi.

Catatan keterbatasan (jujur untuk laporan): ini dongle berbasis file kunci.
Kalau file disalin ke flashdisk lain, tetap dianggap valid. Peningkatan:
ikat ke serial hardware USB (pyudev di Linux / WMI di Windows).
"""
import glob
import hashlib
import hmac
import json
import os
import secrets
import string
import sys

KEYFILE = ".silentreport.key"


class DongleError(Exception):
    pass


def candidate_dirs(extra=()):
    dirs = [d for d in extra if d]
    # sumber kebenaran yang SAMA dengan wizard setup: drive yang bisa dipilih untuk dibuat dongle
    # harus juga drive yang dicari saat aplikasi memeriksa dongle.
    dirs += [d["path"] for d in removable_drives()]
    if sys.platform.startswith("win"):
        dirs += ["{}:\\".format(c) for c in string.ascii_uppercase[3:]]  # D: .. Z:
    elif sys.platform == "darwin":
        dirs += glob.glob("/Volumes/*")
    else:
        dirs += glob.glob("/media/*/*") + glob.glob("/run/media/*/*") + glob.glob("/mnt/*")
    return dirs


def _read_secret(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
        secret = bytes.fromhex(obj["secret"])
        return secret if len(secret) == 32 else None
    except Exception:
        return None


def find_dongle(registry_path: str, extra_dirs=()):
    """Return secret bytes jika dongle valid terpasang, selain itu None."""
    try:
        with open(registry_path, "r", encoding="utf-8") as fh:
            expected = fh.read().strip()
    except OSError:
        return None
    for d in candidate_dirs(extra_dirs):
        secret = _read_secret(os.path.join(d, KEYFILE))
        if secret and hmac.compare_digest(hashlib.sha256(secret).hexdigest(), expected):
            return secret
    return None


def create_dongle(target_dir: str, registry_path: str) -> None:
    """Menulis kunci ke 'flashdisk' (target_dir) dan mendaftarkan hash-nya."""
    os.makedirs(target_dir, exist_ok=True)
    secret = secrets.token_bytes(32)
    key_path = os.path.join(target_dir, KEYFILE)
    with open(key_path, "w", encoding="utf-8") as fh:
        json.dump({"app": "SilentReport", "version": 1, "secret": secret.hex()}, fh)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    os.makedirs(os.path.dirname(registry_path) or ".", exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as fh:
        fh.write(hashlib.sha256(secret).hexdigest())


def _drive_label(path: str) -> str:
    return os.path.basename(path.rstrip("\\/")) or path


def removable_drives(extra=(), include_all=False):
    """Daftar kandidat flashdisk untuk wizard setup: [{'path','label'}].

    Windows : drive bertipe REMOVABLE (flashdisk). include_all=True menampilkan semua drive selain C:.
    Linux   : titik mount di /media, /run/media, /mnt.
    macOS   : /Volumes/* (kecuali volume sistem).
    'extra' (mis. SR_DONGLE_PATH) selalu ikut, berguna untuk uji coba tanpa flashdisk.
    """
    found = []
    if sys.platform.startswith("win"):
        try:
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i, letter in enumerate(string.ascii_uppercase):
                if not bitmask & (1 << i):
                    continue
                root = "{}:\\".format(letter)
                kind = ctypes.windll.kernel32.GetDriveTypeW(root)  # 2 = REMOVABLE
                if kind == 2 or (include_all and letter != "C"):
                    found.append(root)
        except Exception:
            found = ["{}:\\".format(c) for c in string.ascii_uppercase[3:] if os.path.exists("{}:\\".format(c))]
    elif sys.platform == "darwin":
        found = [p for p in glob.glob("/Volumes/*") if not os.path.islink(p)]
    else:
        try:
            with open("/proc/mounts", encoding="utf-8") as fh:
                for line in fh:
                    mp = line.split()[1].replace("\\040", " ")
                    if mp.startswith(("/media/", "/run/media/", "/mnt/")):
                        found.append(mp)
        except OSError:
            found = glob.glob("/media/*/*") + glob.glob("/run/media/*/*")
    for e in extra:
        if e and os.path.isdir(e) and e not in found:
            found.append(e)
    out = []
    for p in dict.fromkeys(found):
        if os.access(p, os.W_OK):
            out.append({"path": p, "label": _drive_label(p)})
    return out
