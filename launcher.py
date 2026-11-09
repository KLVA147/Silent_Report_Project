"""Peluncur SilentReport untuk PENGGUNA AKHIR (tanpa VS Code, tanpa mengetik perintah).

Fungsi:
  - memilih port bebas (5000-5010) dan menyalakan server lokal,
  - memakai folder data milik pengguna (bukan folder kode), aman saat dikemas jadi .exe,
  - membuka jendela aplikasi (mode app Edge/Chrome bila ada, jika tidak browser biasa),
  - bila SilentReport sudah berjalan, hanya membuka jendelanya (tidak menjalankan dua kali).

Aplikasi tetap TERKUNCI sampai dongle terpasang: layar kunci memeriksa dongle otomatis.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from werkzeug.serving import make_server

HOST = "127.0.0.1"
PORTS = range(5000, 5011)


def default_data_dir() -> str:
    override = os.environ.get("SR_DATA_DIR")
    if override:
        return override
    if sys.platform.startswith("win"):
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, "SilentReport")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/SilentReport")
    root = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(root, "silentreport")


def probe(port: int):
    """Return True jika SilentReport sudah berjalan di port itu, None jika tidak ada layanan."""
    try:
        with urllib.request.urlopen("http://{}:{}/api/dongle".format(HOST, port), timeout=0.8) as r:
            return json.load(r).get("app") == "SilentReport"
    except Exception:
        return None


def _app_window_cmds(url: str):
    """Perintah membuka jendela tanpa bilah alamat (terasa seperti aplikasi)."""
    cands = []
    if sys.platform.startswith("win"):
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                          os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    elif sys.platform == "darwin":
        cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome"):
        w = shutil.which(name)
        if w:
            cands.append(w)
    return [[c, "--app=" + url, "--window-size=1100,800"] for c in cands if os.path.exists(c)]


def open_window(url: str) -> None:
    for cmd in _app_window_cmds(url):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            continue
    webbrowser.open(url)


def main() -> int:
    for port in PORTS:  # sudah berjalan? cukup buka jendela
        if probe(port):
            print("SilentReport sudah berjalan. Membuka jendela...")
            open_window("http://{}:{}/".format(HOST, port))
            return 0

    from app import create_app

    data_dir = default_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    application = create_app(data_dir)
    application.config["ALLOW_QUIT"] = True

    server = None
    for port in PORTS:
        if probe(port) is None:
            try:
                server = make_server(HOST, port, application, threaded=True)
                break
            except OSError:
                continue
    if server is None:
        print("Tidak ada port kosong (5000-5010). Tutup program lain lalu coba lagi.")
        return 1

    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://{}:{}/".format(HOST, port)
    print("=" * 56)
    print(" SilentReport berjalan di", url)
    print(" Data tersimpan di      :", data_dir)
    print(" Kode undangan petugas  :", application.config["OFFICER_CODE"])
    print(" Untuk keluar: klik 'Tutup aplikasi' di bagian bawah halaman,")
    print(" atau tutup jendela hitam ini.")
    print("=" * 56)
    open_window(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    if getattr(sys, "frozen", False):  # saat dikemas PyInstaller
        os.chdir(os.path.dirname(sys.executable))
    sys.exit(main())
