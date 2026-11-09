#!/usr/bin/env bash
# Jalankan: ./SilentReport.sh  (Linux)   -- pertama kali: chmod +x SilentReport.sh
cd "$(dirname "$0")" || exit 1
command -v python3 >/dev/null || { echo "Python 3 belum terpasang."; exit 1; }
if [ ! -x .venv/bin/python ]; then
  echo "Pemasangan pertama kali (butuh internet)..."
  python3 -m venv .venv && .venv/bin/pip install --quiet -r requirements.txt || { rm -rf .venv; echo "Pemasangan gagal."; exit 1; }
fi
exec .venv/bin/python launcher.py
