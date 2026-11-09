"""Tes otomatis: membuktikan 7 kriteria tugas akhir terpenuhi.

Jalankan dari folder project:   python -m unittest tests.test_criteria -v
"""
import base64
import io
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest

import cv2
import numpy as np
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from sr_crypto import blockchain, dbcrypto, dongle, keys, stego, textcrypto  # noqa: E402
from sr_crypto.classic import vigenere_decrypt  # noqa: E402
from sr_crypto import face as facemod  # noqa: E402
from tools import face_sim as sim  # noqa: E402
from tools.gen_demo_fingerprint import make_fingerprint, rescan  # noqa: E402


def png(img):
    return cv2.imencode(".png", img)[1].tobytes()


def face_files(person="A", seed=0, n=5):
    """Frame 'webcam' (JPEG) sebagai berkas unggahan multipart."""
    return [(io.BytesIO(raw), "wajah{}.jpg".format(i)) for i, raw in enumerate(sim.session(person, seed, n))]


def photo_bytes(w=200, h=160, seed=0):
    rng = np.random.RandomState(seed)
    arr = rng.randint(0, 256, (h, w, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "data")
        self.usb = os.path.join(self.tmp, "usb")
        os.makedirs(self.data)
        dongle.create_dongle(self.usb, os.path.join(self.data, "dongle.sha256"))
        self.app = create_app(self.data, [self.usb])
        self.master = dongle.find_dongle(os.path.join(self.data, "dongle.sha256"), [self.usb])
        self.fa = make_fingerprint(1234)
        self.fb = make_fingerprint(777)
        self.c = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def csrf(self, client, url="/login"):
        html = client.get(url).get_data(as_text=True)
        return re.search(r'name="csrf" value="([^"]+)"', html).group(1)

    def person_of(self, finger):
        return "B" if finger is self.fb else "A"

    def register(self, client, name, role="reporter", finger=None, code="", face=None):
        return client.post("/register", data={
            "csrf": self.csrf(client, "/register"), "username": name, "password": "Passw0rd!!",
            "role": role, "officer_code": code,
            "fingerprint": (io.BytesIO(png(finger if finger is not None else self.fa)), "f.png"),
            "face": face if face is not None else face_files(self.person_of(finger), 0, 5),
        }, content_type="multipart/form-data")

    def login(self, client, name, finger=None, password="Passw0rd!!", face=None, person="A"):
        return client.post("/login", data={
            "csrf": self.csrf(client, "/login"), "username": name, "password": password,
            "fingerprint": (io.BytesIO(png(finger if finger is not None else rescan(self.fa))), "f.png"),
            "face": face if face is not None else face_files(person, 1000, 4),
        }, content_type="multipart/form-data")

    def post(self, client, url, data, page=None):
        data = dict(data)
        data["csrf"] = self.csrf(client, page or url)
        return client.post(url, data=data, content_type="multipart/form-data")

    def newuser(self, name="pelapor1", role="reporter", finger=None, code=""):
        c = self.app.test_client()
        self.register(c, name, role, finger, code)
        self.login(c, name, rescan(finger if finger is not None else self.fa), person=self.person_of(finger))
        return c

    def dbrows(self, sql, args=()):
        con = sqlite3.connect(os.path.join(self.data, "silentreport.db"))
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, args).fetchall()
        con.close()
        return rows


class K1_BiometrikDanDongle(Base):
    def test_tanpa_dongle_seluruh_aplikasi_terkunci(self):
        # proses boleh menyala (menunggu dongle), tetapi TIDAK ADA fitur/data yang bisa dipakai
        locked = create_app(self.data, [os.path.join(self.tmp, "tidak_ada")]).test_client()
        for url in ("/login", "/register", "/dashboard", "/report/1", "/chain", "/att/1/download", "/inspect"):
            self.assertEqual(locked.get(url).status_code, 423, url)
        self.assertEqual(locked.get("/api/dongle").get_json()["present"], False)
        # file statis (css/js) tetap dilayani agar layar kunci tampil rapi
        self.assertEqual(locked.get("/static/css/app.css").status_code, 200)

    def test_status_dongle_berubah_otomatis(self):
        self.assertEqual(self.c.get("/api/dongle").get_json(),
                         {"app": "SilentReport", "configured": True, "present": True})
        os.remove(os.path.join(self.usb, dongle.KEYFILE))
        self.assertEqual(self.c.get("/api/dongle").get_json()["present"], False)

    def test_app_terkunci_saat_dongle_dicabut(self):
        self.assertEqual(self.c.get("/login").status_code, 200)
        os.remove(os.path.join(self.usb, dongle.KEYFILE))  # cabut dongle
        r = self.c.get("/login")
        self.assertEqual(r.status_code, 423)
        self.assertIn("Terkunci", r.get_data(as_text=True))

    def test_dongle_palsu_ditolak(self):
        fake = os.path.join(self.tmp, "usb_palsu")
        os.makedirs(fake)
        with open(os.path.join(fake, dongle.KEYFILE), "w") as fh:
            fh.write('{"secret": "%s"}' % ("ab" * 32))
        reg = os.path.join(self.data, "dongle.sha256")
        self.assertIsNone(dongle.find_dongle(reg, [fake]))

    def test_login_sidik_jari_sama_lolos(self):
        self.register(self.c, "ani")
        r = self.login(self.c, "ani", rescan(self.fa))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/dashboard").status_code, 200)

    def test_login_sidik_jari_orang_lain_ditolak(self):
        self.register(self.c, "ani")
        r = self.login(self.c, "ani", self.fb)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.c.get("/dashboard").status_code, 302)

    def test_login_password_salah_ditolak(self):
        self.register(self.c, "ani")
        r = self.login(self.c, "ani", rescan(self.fa), password="salahsalah")
        self.assertEqual(r.status_code, 401)

    def test_template_sidik_jari_tidak_tersimpan_polos(self):
        self.register(self.c, "ani")
        raw = self.dbrows("SELECT bio_template FROM users")[0][0]
        # yang tersimpan = nonce(12)+ciphertext+tag(16): bukan kelipatan 32 byte deskriptor ORB
        self.assertNotEqual(len(base64.b64decode(raw)) % 32, 0)
        # tanpa kunci DB yang benar tidak bisa dibuka
        with self.assertRaises(InvalidTag):
            AESGCM(os.urandom(32)).decrypt(base64.b64decode(raw)[:12], base64.b64decode(raw)[12:], b"SR-db-v1")
        # dengan kunci DB yang benar: terbuka menjadi deskriptor ORB (kelipatan 32 byte)
        inner = base64.b64decode(dbcrypto.decrypt_field(raw, self.master))
        self.assertEqual(len(inner) % 32, 0)
        self.assertGreater(len(inner), 0)


class K1b_BiometrikWajah(Base):
    def test_login_wajah_sama_lolos(self):
        self.register(self.c, "ani")
        r = self.login(self.c, "ani", rescan(self.fa))
        self.assertEqual(r.status_code, 302)

    def test_wajah_orang_lain_ditolak_walau_password_dan_sidik_jari_benar(self):
        self.register(self.c, "ani")
        r = self.login(self.c, "ani", rescan(self.fa), face=face_files("B", 2000, 4))
        self.assertEqual(r.status_code, 401)
        self.assertIn("wajah", r.get_data(as_text=True))
        self.assertEqual(self.c.get("/dashboard").status_code, 302)

    def test_tanpa_foto_wajah_ditolak(self):
        self.register(self.c, "ani")
        r = self.c.post("/login", data={"csrf": self.csrf(self.c), "username": "ani", "password": "Passw0rd!!",
                                        "fingerprint": (io.BytesIO(png(rescan(self.fa))), "f.png")},
                        content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_gambar_tanpa_wajah_ditolak_dengan_pesan_jelas(self):
        self.register(self.c, "ani")
        blank = [(io.BytesIO(photo_bytes(320, 240, seed=i)), "x.png") for i in range(3)]
        r = self.login(self.c, "ani", rescan(self.fa), face=blank)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Wajah tidak terdeteksi", r.get_data(as_text=True))

    def test_pesan_kualitas_wajah_tidak_membocorkan_akun(self):
        blank = lambda: [(io.BytesIO(photo_bytes(320, 240, seed=i)), "x.png") for i in range(3)]
        self.register(self.c, "ani")
        a = self.login(self.c, "ani", rescan(self.fa), face=blank())
        b = self.login(self.c, "tidak_ada", rescan(self.fa), face=blank())
        self.assertEqual(a.status_code, b.status_code)

    def test_registrasi_wajib_foto_wajah(self):
        r = self.c.post("/register", data={
            "csrf": self.csrf(self.c, "/register"), "username": "ani", "password": "Passw0rd!!", "role": "reporter",
            "fingerprint": (io.BytesIO(png(self.fa)), "f.png")}, content_type="multipart/form-data")
        self.assertEqual(self.dbrows("SELECT COUNT(*) FROM users")[0][0], 0)
        self.assertIn("Foto wajah wajib", r.get_data(as_text=True))

    def test_registrasi_menolak_foto_campuran_dua_orang(self):
        mix = face_files("A", 0, 3) + face_files("B", 0, 3)
        r = self.register(self.c, "ani", face=mix)
        self.assertEqual(self.dbrows("SELECT COUNT(*) FROM users")[0][0], 0)
        self.assertIn("tidak konsisten", r.get_data(as_text=True))

    def test_registrasi_menolak_terlalu_sedikit_foto_layak(self):
        r = self.register(self.c, "ani", face=face_files("A", 0, 2))
        self.assertEqual(self.dbrows("SELECT COUNT(*) FROM users")[0][0], 0)

    def test_template_wajah_terenkripsi_dan_bukan_foto(self):
        self.register(self.c, "ani")
        raw = self.dbrows("SELECT face_template FROM users")[0][0]
        blob = base64.b64decode(raw)
        with self.assertRaises(InvalidTag):  # tanpa kunci DB tidak bisa dibuka
            AESGCM(os.urandom(32)).decrypt(blob[:12], blob[12:], b"SR-db-v1")
        sigs = facemod.template_from_bytes(base64.b64decode(dbcrypto.decrypt_field(raw, self.master)))
        self.assertEqual(len(sigs), 5)
        self.assertEqual(sigs[0].shape, (facemod.GRID ** 2, facemod.BINS))
        self.assertNotIn(b"\xff\xd8\xff", base64.b64decode(dbcrypto.decrypt_field(raw, self.master)))  # bukan JPEG

    def test_akun_lama_tanpa_template_wajah_didaftarkan_saat_login_pertama(self):
        self.register(self.c, "ani")
        con = sqlite3.connect(os.path.join(self.data, "silentreport.db"))
        con.execute("UPDATE users SET face_template=NULL")
        con.commit(); con.close()
        self.assertEqual(self.login(self.c, "ani", rescan(self.fa)).status_code, 302)
        self.assertIsNotNone(self.dbrows("SELECT face_template FROM users")[0][0])
        # setelah itu wajah orang lain ditolak
        c2 = self.app.test_client()
        self.assertEqual(self.login(c2, "ani", rescan(self.fa), face=face_files("B", 3000, 4)).status_code, 401)

    def test_dua_orang_berbeda_tidak_tertukar(self):
        self.register(self.c, "ani")
        c2 = self.app.test_client()
        self.register(c2, "budi", finger=self.fb)
        self.assertEqual(self.login(self.app.test_client(), "budi", rescan(self.fb), person="B").status_code, 302)
        self.assertEqual(self.login(self.app.test_client(), "budi", rescan(self.fb), face=face_files("A", 4000, 4)).status_code, 401)


class ModulWajah(unittest.TestCase):
    def test_orang_sama_lebih_dekat_dari_orang_beda_dengan_celah_aman(self):
        tmpl = {p: facemod.enroll(sim.session(p, 0, 6)) for p in "AB"}
        asli, penipu = [], []
        for p, o in (("A", "B"), ("B", "A")):
            for k in range(5):
                asli.append(facemod.score(tmpl[p], facemod.usable_signatures(sim.session(p, 800 + k * 4, 4), 2)))
                penipu.append(facemod.score(tmpl[p], facemod.usable_signatures(sim.session(o, 900 + k * 4, 4), 2)))
        self.assertLess(max(asli), facemod.FACE_THRESHOLD)
        self.assertGreater(min(penipu), facemod.FACE_THRESHOLD)

    def test_serialisasi_template_bolak_balik(self):
        sigs = facemod.enroll(sim.session("A", 0, 5))
        back = facemod.template_from_bytes(facemod.template_to_bytes(sigs))
        self.assertEqual(len(back), len(sigs))
        self.assertLess(facemod.distance(sigs[0], back[0]), 1e-3)  # float16 hampir tanpa kehilangan

    def test_dua_wajah_dalam_satu_gambar_ditolak(self):
        import cv2

        def tile(name, size=320):  # potong sekitar wajah supaya ukurannya sebanding, seperti dua orang di depan kamera
            raw = sim.variant(name, 1, 0.0)
            x, y, side = facemod.detect(facemod._decode_gray(raw))
            c = int(side * 2.2)
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            x0, y0 = max(0, x + side // 2 - c // 2), max(0, y + side // 2 - c // 2)
            return cv2.resize(img[y0:y0 + c, x0:x0 + c], (size, size))

        ok, buf = cv2.imencode(".jpg", np.hstack([tile("A"), tile("B")]))
        with self.assertRaises(facemod.FaceError) as cm:
            facemod.extract_signature(buf.tobytes())
        self.assertIn("lebih dari satu wajah", str(cm.exception))

    def test_gambar_rusak_ditolak(self):
        with self.assertRaises(facemod.FaceError):
            facemod.extract_signature(b"bukan gambar")


class K2_LoginKriptografi(Base):
    def test_password_disimpan_sebagai_hash_scrypt(self):
        self.register(self.c, "ani")
        pw = self.dbrows("SELECT pw_hash FROM users")[0][0]
        self.assertTrue(pw.startswith("scrypt$"))
        self.assertNotIn("Passw0rd", pw)

    def test_salt_berbeda_hash_berbeda(self):
        self.register(self.c, "ani")
        self.register(self.c, "budi")
        h = [r[0] for r in self.dbrows("SELECT pw_hash FROM users")]
        self.assertNotEqual(h[0], h[1])  # password sama, hash beda karena salt


class K3_SuperEnkripsiTeks(Base):
    def test_roundtrip_unicode(self):
        t = "Pak X menerima suap Rp5.000.000 \U0001F4B8 di ruang rapat, 12/10/2026!"
        self.assertEqual(textcrypto.decrypt_text(textcrypto.encrypt_text(t, self.master), self.master), t)

    def test_dua_lapis_klasik_lalu_modern(self):
        t = "rahasia"
        tok = textcrypto.encrypt_text(t, self.master)
        raw = base64.b64decode(tok)
        # lapis modern (AES-GCM) dibuka dulu -> hasilnya BUKAN plaintext (masih lapis Vigenere)
        stage1 = AESGCM(keys.derive(self.master, "text-aes256", 32)).decrypt(raw[:12], raw[12:], b"SR-text-v1")
        self.assertNotEqual(stage1, t.encode())
        # lapis klasik (Vigenere) dibuka -> plaintext
        self.assertEqual(vigenere_decrypt(stage1, keys.derive(self.master, "text-vigenere", 16)), t.encode())

    def test_enkripsi_probabilistik(self):
        a = textcrypto.encrypt_text("sama", self.master)
        b = textcrypto.encrypt_text("sama", self.master)
        self.assertNotEqual(a, b)

    def test_data_diubah_terdeteksi(self):
        tok = bytearray(base64.b64decode(textcrypto.encrypt_text("halo", self.master)))
        tok[-1] ^= 1
        with self.assertRaises(InvalidTag):
            textcrypto.decrypt_text(base64.b64encode(bytes(tok)).decode(), self.master)

    def test_di_database_tidak_ada_plaintext(self):
        c = self.newuser()
        self.post(c, "/report/new", {"title": "Judul Rahasia XYZ", "category": "Korupsi",
                                     "message": "isi pesan unik QWERTY123"}, page="/report/new")
        row = self.dbrows("SELECT title FROM reports")[0][0]
        body = self.dbrows("SELECT body FROM messages")[0][0]
        self.assertNotIn("Judul Rahasia", row)
        self.assertNotIn("QWERTY123", body)
        self.assertIn("QWERTY123", c.get("/report/1").get_data(as_text=True))


class K4_EnkripsiFileBeda(Base):
    def test_file_chacha20_bukan_algoritma_teks(self):
        c = self.newuser()
        secret = b"%PDF-1.4 ISI DOKUMEN RAHASIA 0123456789" * 20
        self.post(c, "/report/new", {"title": "t", "category": "Korupsi", "message": "m",
                                     "evidence_file": (io.BytesIO(secret), "bukti.pdf")}, page="/report/new")
        path = self.dbrows("SELECT path FROM attachments")[0][0]
        with open(path, "rb") as fh:
            stored = fh.read()
        self.assertNotIn(b"ISI DOKUMEN RAHASIA", stored)
        key = keys.derive(self.master, "file-chacha20", 32)
        self.assertEqual(ChaCha20Poly1305(key).decrypt(stored[:12], stored[12:], b"SR-file-v1"), secret)
        # kunci file BERBEDA dari kunci teks/DB, dan AES-GCM teks tidak bisa membukanya
        self.assertNotEqual(key, keys.derive(self.master, "text-aes256", 32))
        with self.assertRaises(InvalidTag):
            AESGCM(keys.derive(self.master, "text-aes256", 32)).decrypt(stored[:12], stored[12:], b"SR-text-v1")
        r = c.get("/att/1/download")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, secret)

    def test_file_dimodifikasi_ditolak(self):
        c = self.newuser()
        self.post(c, "/report/new", {"title": "t", "category": "Korupsi", "message": "m",
                                     "evidence_file": (io.BytesIO(b"data penting" * 10), "a.txt")}, page="/report/new")
        path = self.dbrows("SELECT path FROM attachments")[0][0]
        with open(path, "rb") as fh:
            b = bytearray(fh.read())
        b[20] ^= 0xFF
        with open(path, "wb") as fh:
            fh.write(bytes(b))
        self.assertEqual(c.get("/att/1/download").status_code, 500)


class K5_PesanPentingDiDatabase(Base):
    def test_pesan_penting_punya_lapisan_db(self):
        c = self.newuser()
        self.post(c, "/report/new", {"title": "t", "category": "Korupsi", "message": "pesan biasa",
                                     "important": ""}, page="/report/new")
        self.post(c, "/report/1", {"message": "PESAN PENTING SEKALI", "important": "1"})
        rows = self.dbrows("SELECT body, important FROM messages ORDER BY id")
        biasa, penting = rows[0], rows[1]
        self.assertEqual((biasa["important"], penting["important"]), (0, 1))
        # pesan biasa: langsung bisa didekripsi lapisan teks
        self.assertEqual(textcrypto.decrypt_text(biasa["body"], self.master), "pesan biasa")
        # pesan penting: lapisan teks GAGAL (masih terbungkus lapisan DB)
        with self.assertRaises(Exception):
            textcrypto.decrypt_text(penting["body"], self.master)
        inner = dbcrypto.decrypt_field(penting["body"], self.master)
        self.assertEqual(textcrypto.decrypt_text(inner, self.master), "PESAN PENTING SEKALI")
        self.assertIn("PESAN PENTING SEKALI", c.get("/report/1").get_data(as_text=True))


class K6_Steganografi(Base):
    def test_embed_extract_dan_tak_kasat_mata(self):
        cover = photo_bytes()
        msg = b"pesan rahasia: ruang 12, jam 09.00"
        out = stego.embed(cover, msg)
        self.assertEqual(stego.extract(out), msg)
        a = np.array(Image.open(io.BytesIO(cover)).convert("RGB")).astype(int)
        b = np.array(Image.open(io.BytesIO(out)).convert("RGB")).astype(int)
        self.assertLessEqual(np.abs(a - b).max(), 1)  # perubahan maks 1 level per kanal

    def test_gambar_tanpa_pesan(self):
        with self.assertRaises(stego.StegoError):
            stego.extract(photo_bytes())

    def test_kapasitas_terlampaui(self):
        with self.assertRaises(stego.StegoError):
            stego.embed(photo_bytes(10, 10), b"x" * 1000)

    def test_alur_aplikasi(self):
        c = self.newuser()
        self.post(c, "/report/new", {"title": "t", "category": "Perundungan (bullying)", "message": "m",
                                     "evidence_image": (io.BytesIO(photo_bytes(seed=5)), "foto.jpg"),
                                     "secret_note": "difoto di gedung B lantai 2"}, page="/report/new")
        path = self.dbrows("SELECT path FROM attachments")[0][0]
        self.assertTrue(path.endswith(".png"))
        r = c.get("/att/1/extract")
        self.assertEqual(r.status_code, 200)
        self.assertIn("gedung B lantai 2", r.get_data(as_text=True))
        self.assertIn("UTUH", r.get_data(as_text=True))
        self.assertEqual(c.get("/att/1/preview").mimetype, "image/png")
        # catatan rahasia tidak tampil sebagai teks biasa di file gambar
        with open(path, "rb") as fh:
            self.assertNotIn(b"gedung B", fh.read())


class K7_Blockchain(Base):
    def _chain(self):
        c = self.newuser()
        self.post(c, "/report/new", {"title": "t", "category": "Korupsi", "message": "m",
                                     "evidence_file": (io.BytesIO(b"bukti" * 50), "b.txt")}, page="/report/new")
        c.get("/att/1/download")
        return c

    def test_rantai_valid_dan_berurutan(self):
        self._chain()
        blocks = [dict(r) for r in self.dbrows("SELECT * FROM blocks ORDER BY idx")]
        self.assertGreaterEqual(len(blocks), 2)
        self.assertTrue(blockchain.validate_chain(blocks)[0])
        self.assertTrue(all(b["hash"].startswith("000") for b in blocks))
        for i in range(1, len(blocks)):
            self.assertEqual(blocks[i]["prev_hash"], blocks[i - 1]["hash"])

    def test_pemalsuan_data_terdeteksi(self):
        self._chain()
        blocks = [dict(r) for r in self.dbrows("SELECT * FROM blocks ORDER BY idx")]
        blocks[0]["data"] = blocks[0]["data"].replace("DISERAHKAN", "DIHAPUS")
        ok, bad, _ = blockchain.validate_chain(blocks)
        self.assertFalse(ok)
        self.assertEqual(bad, 0)

    def test_pemalsuan_lewat_database_terdeteksi_di_halaman(self):
        c = self._chain()
        con = sqlite3.connect(os.path.join(self.data, "silentreport.db"))
        con.execute("UPDATE blocks SET data = replace(data,'BUKTI_DIUNDUH','TIDAK_ADA') WHERE idx=1")
        con.commit()
        con.close()
        self.assertIn("TIDAK VALID", c.get("/chain").get_data(as_text=True))

    def test_hash_bukti_dicatat(self):
        self._chain()
        import hashlib, json
        d = json.loads(self.dbrows("SELECT data FROM blocks WHERE idx=0")[0][0])
        self.assertEqual(d["evidence_sha256"], hashlib.sha256(b"bukti" * 50).hexdigest())


class WizardSetupDanLauncher(unittest.TestCase):
    """Alur pengguna akhir: buka aplikasi pertama kali -> pilih flashdisk -> dongle dibuat."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "data")
        self.usb = os.path.join(self.tmp, "flashdisk")
        os.makedirs(self.usb)
        self.app = create_app(self.data, [self.usb])
        self.c = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def csrf(self, url):
        return re.search(r'name="csrf" value="([^"]+)"', self.c.get(url).get_data(as_text=True)).group(1)

    def test_pemakaian_pertama_diarahkan_ke_setup(self):
        r = self.c.get("/login")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/setup"))
        html = self.c.get("/setup").get_data(as_text=True)
        self.assertIn(self.usb, html)  # flashdisk muncul di daftar

    def test_setup_membuat_dongle_dan_membuka_aplikasi(self):
        r = self.c.post("/setup", data={"csrf": self.csrf("/setup"), "drive": self.usb})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(os.path.exists(os.path.join(self.usb, dongle.KEYFILE)))
        self.assertTrue(os.path.exists(os.path.join(self.data, "dongle.sha256")))
        first = self.c.get("/login")  # setelah setup, aplikasi langsung terbuka
        self.assertEqual(first.status_code, 200)
        # kode undangan petugas ditampilkan SEKALI (pesan flash), lalu hilang
        self.assertIn(self.app.config["OFFICER_CODE"], first.get_data(as_text=True))
        self.assertNotIn(self.app.config["OFFICER_CODE"], self.c.get("/login").get_data(as_text=True))
        # setup tidak bisa diulang untuk menimpa kunci
        self.assertEqual(self.c.get("/setup").status_code, 302)

    def test_setup_menolak_path_di_luar_daftar_flashdisk(self):
        evil = os.path.join(self.tmp, "folder_lain")
        os.makedirs(evil)
        self.c.post("/setup", data={"csrf": self.csrf("/setup"), "drive": evil})
        self.assertFalse(os.path.exists(os.path.join(evil, dongle.KEYFILE)))
        self.assertFalse(os.path.exists(os.path.join(self.data, "dongle.sha256")))

    def test_setup_tanpa_csrf_ditolak(self):
        self.assertEqual(self.c.post("/setup", data={"drive": self.usb}).status_code, 400)

    def test_setup_menolak_bila_ada_data_tanpa_dongle(self):
        # data lama + dongle hilang: jangan buat kunci baru (data lama jadi yatim)
        con = sqlite3.connect(os.path.join(self.data, "silentreport.db"))
        con.execute("INSERT INTO users (username,pw_hash,role,bio_template,created) VALUES ('a','x','reporter','y',0)")
        con.commit(); con.close()
        html = self.c.get("/setup").get_data(as_text=True)
        self.assertIn("Data lama ditemukan", html)
        self.assertNotIn('name="drive"', html)  # tidak ada form pembuatan dongle
        with self.c.session_transaction() as sess:
            token = sess["csrf"]
        self.c.post("/setup", data={"csrf": token, "drive": self.usb})  # coba paksa lewat POST
        self.assertFalse(os.path.exists(os.path.join(self.data, "dongle.sha256")))

    def test_tombol_tutup_aplikasi_nonaktif_kecuali_launcher(self):
        self.c.post("/setup", data={"csrf": self.csrf("/setup"), "drive": self.usb})
        self.assertNotIn("Tutup aplikasi", self.c.get("/login").get_data(as_text=True))
        self.assertEqual(self.c.post("/quit", data={"csrf": self.csrf("/login")}).status_code, 404)
        self.assertEqual(self.c.post("/quit", data={}).status_code, 400)  # tanpa csrf

    def test_dongle_di_drive_pilihan_wizard_pasti_ditemukan(self):
        # regresi: drive yang ditawarkan wizard harus ikut dicari saat memeriksa dongle
        mount = os.path.join(self.tmp, "mnt", "dalam", "USB1")
        reg = os.path.join(self.data, "dongle.sha256")
        orig = dongle.removable_drives
        dongle.removable_drives = lambda extra=(), include_all=False: [{"path": mount, "label": "USB1"}]
        try:
            dongle.create_dongle(mount, reg)
            self.assertIsNotNone(dongle.find_dongle(reg, []))  # tanpa 'extra' sama sekali
        finally:
            dongle.removable_drives = orig

    def test_tidak_ada_drive_terpilih_otomatis_bila_lebih_dari_satu(self):
        usb2 = os.path.join(self.tmp, "flashdisk2")
        os.makedirs(usb2)
        two = create_app(os.path.join(self.tmp, "d2"), [self.usb, usb2]).test_client()
        html = two.get("/setup", follow_redirects=True).get_data(as_text=True)
        self.assertIn(self.usb, html); self.assertIn(usb2, html)
        self.assertNotIn("checked", html.split("Pilih flashdisk")[1].split("</form>")[0])

    def test_launcher_folder_data_dan_probe(self):
        import launcher
        self.assertTrue(launcher.default_data_dir().lower().endswith(("silentreport",)))
        self.assertIsNone(launcher.probe(59999))  # port kosong -> tidak ada layanan


class Keamanan(Base):
    def test_post_tanpa_csrf_ditolak(self):
        self.assertEqual(self.c.post("/login", data={"username": "a"}).status_code, 400)

    def test_pelapor_lain_tidak_bisa_lihat_laporan(self):
        c1 = self.newuser("pelapor1")
        self.post(c1, "/report/new", {"title": "t", "category": "Korupsi", "message": "m",
                                      "evidence_file": (io.BytesIO(b"x" * 30), "a.txt")}, page="/report/new")
        c2 = self.newuser("pelapor2", finger=self.fb)
        self.assertEqual(c2.get("/report/1").status_code, 404)
        self.assertEqual(c2.get("/att/1/download").status_code, 404)

    def test_petugas_bisa_dan_butuh_kode(self):
        c = self.app.test_client()
        r = self.register(c, "petugas1", "officer", code="salah")
        self.assertEqual(r.status_code, 200)  # tetap di halaman registrasi
        self.assertEqual(self.dbrows("SELECT COUNT(*) FROM users")[0][0], 0)
        self.register(c, "petugas1", "officer", code=self.app.config["OFFICER_CODE"])
        self.assertEqual(self.dbrows("SELECT role FROM users")[0][0], "officer")

    def test_pelapor_tidak_bisa_buka_inspeksi_atau_ubah_status(self):
        c = self.newuser()
        self.assertEqual(c.get("/inspect").status_code, 403)

    def test_belum_login_diarahkan(self):
        self.assertEqual(self.c.get("/dashboard").status_code, 302)
        self.assertEqual(self.c.get("/report/1").status_code, 302)

    def test_alur_petugas_ubah_status_tercatat_blockchain(self):
        cp = self.newuser("pelapor1")
        self.post(cp, "/report/new", {"title": "t", "category": "Korupsi", "message": "m"}, page="/report/new")
        co = self.newuser("petugas1", "officer", finger=self.fb, code=self.app.config["OFFICER_CODE"])
        self.assertEqual(co.get("/report/1").status_code, 200)
        self.post(co, "/report/1/status", {"status": "diterima"}, page="/report/1")
        self.assertIn('st done cur">Diterima', cp.get("/report/1").get_data(as_text=True))
        acts = [r[0] for r in self.dbrows("SELECT data FROM blocks")]
        self.assertTrue(any("STATUS_DITERIMA" in a for a in acts))
        self.assertEqual(co.get("/inspect").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
