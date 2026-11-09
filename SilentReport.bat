@echo off
chcp 65001 >nul
title SilentReport
cd /d "%~dp0"
rem === Klik dua kali file ini untuk membuka SilentReport (Windows) ===
if exist "SilentReport.exe" (
  start "" "SilentReport.exe"
  exit /b
)
where python >nul 2>nul
if errorlevel 1 (
  echo Python belum terpasang. Unduh dari https://www.python.org/downloads/ lalu centang "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Pemasangan pertama kali. Mohon tunggu beberapa menit dan pastikan terhubung ke internet...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo Pemasangan gagal. Periksa koneksi internet lalu jalankan lagi.
    rmdir /s /q .venv
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" launcher.py
if errorlevel 1 pause
