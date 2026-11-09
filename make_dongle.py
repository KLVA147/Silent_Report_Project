"""Membuat dongle: menulis kunci ke flashdisk dan mendaftarkan hash-nya.

Contoh:
    Windows : python make_dongle.py E:\\
    Linux   : python make_dongle.py /media/user/FLASHDISK
    Uji coba tanpa flashdisk: python make_dongle.py ./fake_usb   (lalu set SR_DONGLE_PATH=./fake_usb)

PERINGATAN: menjalankan ulang akan MENGGANTI kunci -> data lama tidak bisa dibuka lagi.
"""
import os
import sys

from sr_crypto import dongle

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    base = os.path.dirname(os.path.abspath(__file__))
    registry = os.path.join(base, "data", "dongle.sha256")
    if os.path.exists(registry) and input("Dongle sudah terdaftar, ganti? Data lama tidak terbaca (y/N): ").lower() != "y":
        sys.exit("Dibatalkan.")
    dongle.create_dongle(sys.argv[1], registry)
    print("Dongle dibuat di", os.path.abspath(sys.argv[1]))
