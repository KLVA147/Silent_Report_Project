import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    pw_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('reporter','officer')),
    bio_template TEXT NOT NULL,          -- template sidik jari, terenkripsi (AES-GCM DB key)
    face_template TEXT,                  -- tanda tangan wajah (LBP), terenkripsi AES-GCM DB key; NULL = akun lama
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,                 -- super enkripsi teks
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'baru',
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id),
    sender_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,                  -- super enkripsi; jika important=1 dibungkus lagi lapisan DB
    important INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id),
    kind TEXT NOT NULL CHECK (kind IN ('file','image')),
    name TEXT NOT NULL,                  -- nama file asli, super enkripsi teks
    path TEXT NOT NULL,                  -- file di disk (file: ChaCha20, image: PNG stego)
    sha256 TEXT NOT NULL,                -- hash isi yang disimpan/dicatat di blockchain
    uploader_id INTEGER NOT NULL REFERENCES users(id),
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
    idx INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    data TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    nonce INTEGER NOT NULL,
    hash TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(path: str) -> None:
    conn = connect(path)
    conn.executescript(SCHEMA)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)")]
    if "face_template" not in cols:  # migrasi dari versi sebelum fitur wajah
        conn.execute("ALTER TABLE users ADD COLUMN face_template TEXT")
    conn.commit()
    conn.close()
