#!/usr/bin/env bash
# Membuat program mandiri (Linux/macOS) dengan PyInstaller. Jalankan sekali.
cd "$(dirname "$0")" || exit 1
python3 -m venv .buildenv && .buildenv/bin/pip install --quiet -r requirements.txt pyinstaller || exit 1
.buildenv/bin/pyinstaller --noconfirm --onefile --name SilentReport \
  --add-data "templates:templates" --add-data "static:static" --add-data "models:models" --collect-all skimage \
  --collect-submodules sr_crypto launcher.py && echo "Selesai: dist/SilentReport"
