@echo off
rem === Membuat SilentReport.exe (satu file) dengan PyInstaller. Jalankan SEKALI di Windows. ===
cd /d "%~dp0"
python -m venv .buildenv
".buildenv\Scripts\python.exe" -m pip install --quiet -r requirements.txt pyinstaller
".buildenv\Scripts\pyinstaller.exe" --noconfirm --onefile --name SilentReport ^
  --add-data "templates;templates" --add-data "static;static" --add-data "models;models" ^
  --collect-all skimage ^
  --collect-submodules sr_crypto launcher.py
if exist dist\SilentReport.exe (
  copy /y dist\SilentReport.exe SilentReport.exe >nul
  echo.
  echo Berhasil: SilentReport.exe dibuat. Klik dua kali untuk membuka aplikasi.
) else (
  echo Build gagal. Lihat pesan galat di atas.
)
pause
