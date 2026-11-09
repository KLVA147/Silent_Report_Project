"""Kriteria 7: aset penting diamankan dengan BLOCKCHAIN SEDERHANA.

Aset penting aplikasi = barang bukti laporan. Setiap peristiwa pada barang bukti
(diserahkan, diakses, status berubah) dicatat sebagai blok:

    hash = SHA-256( index | timestamp | data | prev_hash | nonce )

  - prev_hash menghubungkan blok ke blok sebelumnya (rantai),
  - Proof-of-Work sederhana: hash harus diawali DIFFICULTY nol heksadesimal,
  - mengubah data blok mana pun membuat hash berubah dan rantai setelahnya tidak valid.
"""
import hashlib
import json
import time

DIFFICULTY = 3
GENESIS_PREV = "0" * 64


def compute_hash(index: int, timestamp: float, data: str, prev_hash: str, nonce: int) -> str:
    raw = "{}|{}|{}|{}|{}".format(index, repr(timestamp), data, prev_hash, nonce)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mine_block(index: int, data: dict, prev_hash: str) -> dict:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    ts = round(time.time(), 3)
    nonce = 0
    target = "0" * DIFFICULTY
    while True:
        h = compute_hash(index, ts, payload, prev_hash, nonce)
        if h.startswith(target):
            return {
                "idx": index,
                "ts": ts,
                "data": payload,
                "prev_hash": prev_hash,
                "nonce": nonce,
                "hash": h,
            }
        nonce += 1


def validate_chain(blocks: list) -> tuple:
    """Return (valid: bool, bad_index: int|None, reason: str)."""
    prev = GENESIS_PREV
    for i, b in enumerate(blocks):
        if b["idx"] != i:
            return False, b["idx"], "Nomor blok tidak berurutan"
        if b["prev_hash"] != prev:
            return False, b["idx"], "prev_hash tidak cocok (rantai terputus)"
        h = compute_hash(b["idx"], b["ts"], b["data"], b["prev_hash"], b["nonce"])
        if h != b["hash"]:
            return False, b["idx"], "Isi blok telah diubah (hash tidak cocok)"
        if not h.startswith("0" * DIFFICULTY):
            return False, b["idx"], "Proof-of-Work tidak terpenuhi"
        prev = b["hash"]
    return True, None, "Rantai valid"
