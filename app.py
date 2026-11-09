"""SilentReport - aplikasi pelaporan anonim berbasis kriptografi.

Jalankan:  python app.py      (dongle USB harus terpasang, lihat README)
"""
import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_file, session, url_for)

import db
from icons import icon
from sr_crypto import (biometric, blockchain, dbcrypto, dongle, face, filecrypto,
                       keys, passwords, stego, textcrypto)

BASE = os.path.dirname(os.path.abspath(__file__))
STATUSES = ["baru", "diterima", "diverifikasi", "ditindaklanjuti", "selesai", "ditolak"]
CATEGORIES = ["Korupsi", "Perundungan (bullying)", "Pelecehan", "Gratifikasi", "Lainnya"]
WIB = timezone(timedelta(hours=7))
MAX_FAILS, LOCK_SECONDS = 5, 60


def create_app(data_dir=None, dongle_dirs=None):
    app = Flask(__name__)
    app.jinja_env.globals["icon"] = icon
    data_dir = data_dir or os.environ.get("SR_DATA_DIR") or os.path.join(BASE, "data")
    files_dir = os.path.join(data_dir, "files")
    os.makedirs(files_dir, exist_ok=True)
    registry = os.path.join(data_dir, "dongle.sha256")
    db_path = os.path.join(data_dir, "silentreport.db")
    if dongle_dirs is None:
        dongle_dirs = [os.environ["SR_DONGLE_PATH"]] if os.environ.get("SR_DONGLE_PATH") else []

    # Kriteria 1: aplikasi hanya BISA DIPAKAI dengan dongle. Proses boleh menyala dan menunggu,
    # tetapi setiap halaman (kecuali setup/status) terkunci dan tidak ada data yang bisa dibuka
    # sampai dongle valid terpasang (dicek pada SETIAP permintaan di guard()).
    db.init_schema(db_path)
    app.secret_key = secrets.token_bytes(32)  # sesi login berlaku selama proses berjalan
    app.config.update(
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        ALLOW_QUIT=False,  # diaktifkan oleh launcher agar tombol "Tutup aplikasi" berfungsi
    )

    # Kode undangan petugas (dibuat otomatis saat pertama kali jalan)
    code_path = os.path.join(data_dir, "officer_code.txt")
    if not os.path.exists(code_path):
        with open(code_path, "w") as fh:
            fh.write(secrets.token_urlsafe(8))
    with open(code_path) as fh:
        officer_code = fh.read().strip()
    app.config["OFFICER_CODE"] = officer_code

    fails = {}  # username -> (jumlah, waktu_terakhir)

    # ------------------------------------------------------------------ util
    def tenc(s):
        return textcrypto.encrypt_text(s, g.master)

    def tdec(s):
        return textcrypto.decrypt_text(s, g.master)

    @app.template_filter("dt")
    def fmt_dt(ts):
        return datetime.fromtimestamp(ts, WIB).strftime("%d %b %Y %H:%M WIB")

    @app.context_processor
    def inject():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return {"csrf_token": lambda: session["csrf"], "user": g.get("user"),
                "STATUSES": STATUSES, "CATEGORIES": CATEGORIES}

    # ------------------------------------------------------------ keamanan
    @app.before_request
    def guard():
        ep = request.endpoint
        if ep in ("static", "api_dongle"):
            return None
        if request.method == "POST":
            tok = request.form.get("csrf", "")
            if not tok or not hmac.compare_digest(tok, session.get("csrf", "")):
                abort(400, "Token CSRF tidak valid")
        g.master, g.db, g.user = None, None, None
        if ep in ("setup", "quit_app"):
            return None
        if not os.path.exists(registry):          # pemakaian pertama: dongle belum dibuat
            return redirect(url_for("setup"))
        s = dongle.find_dongle(registry, dongle_dirs)  # dicek tiap request
        if s is None:
            return render_template("lock.html"), 423
        g.master = s
        g.db = db.connect(db_path)
        if "uid" in session:
            g.user = g.db.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
        return None

    @app.teardown_request
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def login_required(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if g.user is None:
                return redirect(url_for("login"))
            return fn(*a, **kw)
        return wrapper

    def officer_required(fn):
        @wraps(fn)
        @login_required
        def wrapper(*a, **kw):
            if g.user["role"] != "officer":
                abort(403)
            return fn(*a, **kw)
        return wrapper

    def get_report_or_404(rid):
        r = g.db.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
        if r is None:
            abort(404)
        if g.user["role"] != "officer" and r["owner_id"] != g.user["id"]:
            abort(404)  # 404 agar keberadaan laporan orang lain tidak bocor
        return r

    # --------------------------------------------------------- blockchain
    def add_block(data: dict):
        last = g.db.execute("SELECT * FROM blocks ORDER BY idx DESC LIMIT 1").fetchone()
        idx = 0 if last is None else last["idx"] + 1
        prev = blockchain.GENESIS_PREV if last is None else last["hash"]
        b = blockchain.mine_block(idx, data, prev)
        g.db.execute(
            "INSERT INTO blocks (idx,ts,data,prev_hash,nonce,hash) VALUES (?,?,?,?,?,?)",
            (b["idx"], b["ts"], b["data"], b["prev_hash"], b["nonce"], b["hash"]),
        )
        g.db.commit()

    def log_event(rid, action, evidence_sha="", note=""):
        add_block({"report": rid, "action": action, "actor": g.user["username"],
                   "role": g.user["role"], "evidence_sha256": evidence_sha, "note": note})

    # ---------------------------------------------------------- pesan
    def store_message(rid, sender_id, text, important):
        body = tenc(text)                       # kriteria 3: super enkripsi
        if important:                           # kriteria 5: lapisan enkripsi DB
            body = dbcrypto.encrypt_field(body, g.master)
        g.db.execute(
            "INSERT INTO messages (report_id,sender_id,body,important,created) VALUES (?,?,?,?,?)",
            (rid, sender_id, body, 1 if important else 0, time.time()),
        )
        g.db.commit()

    def read_message(row):
        body = row["body"]
        if row["important"]:
            body = dbcrypto.decrypt_field(body, g.master)
        return tdec(body)

    # ------------------------------------------------------- lampiran
    def save_attachment(rid, upload, kind, secret_note=""):
        raw = upload.read()
        if not raw:
            raise ValueError("File kosong")
        name = os.path.basename(upload.filename or "bukti")
        token = secrets.token_hex(16)
        if kind == "file":
            stored = filecrypto.encrypt_bytes(raw, g.master)     # kriteria 4: ChaCha20-Poly1305
            sha_evidence = hashlib.sha256(raw).hexdigest()
            path = os.path.join(files_dir, token + ".bin")
            action = "BUKTI_FILE_DISERAHKAN"
        else:
            payload = json.dumps({"laporan": rid, "catatan": secret_note, "waktu": time.time()})
            hidden = tenc(payload).encode()                      # pesan rahasia dienkripsi dulu
            stored = stego.embed(raw, hidden)                    # kriteria 6: LSB steganografi
            sha_evidence = hashlib.sha256(stored).hexdigest()
            path = os.path.join(files_dir, token + ".png")
            action = "BUKTI_GAMBAR_DISERAHKAN"
        with open(path, "wb") as fh:
            fh.write(stored)
        g.db.execute(
            "INSERT INTO attachments (report_id,kind,name,path,sha256,uploader_id,created) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, kind, tenc(name), path, sha_evidence, g.user["id"], time.time()),
        )
        g.db.commit()
        log_event(rid, action, sha_evidence, "")        # kriteria 7: blockchain

    def handle_uploads(rid):
        f = request.files.get("evidence_file")
        if f and f.filename:
            save_attachment(rid, f, "file")
        img = request.files.get("evidence_image")
        if img and img.filename:
            save_attachment(rid, img, "image", request.form.get("secret_note", "").strip())

    # ================================================== SETUP & STATUS DONGLE
    @app.route("/api/dongle")
    def api_dongle():
        """Dipakai layar terkunci untuk mendeteksi flashdisk secara otomatis."""
        present = os.path.exists(registry) and dongle.find_dongle(registry, dongle_dirs) is not None
        return {"app": "SilentReport", "configured": os.path.exists(registry), "present": present}

    def _has_users():
        try:
            conn = db.connect(db_path)
            n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            conn.close()
            return n > 0
        except Exception:
            return False

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        """Wizard pemakaian pertama: pilih flashdisk lalu buat dongle."""
        if os.path.exists(registry):
            return redirect(url_for("index"))
        drives = dongle.removable_drives(dongle_dirs, include_all=bool(request.args.get("semua")))
        orphan = _has_users()  # ada data tetapi dongle hilang: JANGAN buat kunci baru
        if request.method == "POST" and not orphan:
            target = request.form.get("drive", "")
            if target not in [d["path"] for d in drives]:
                flash("Flashdisk tidak valid. Pilih dari daftar.", "err")
            else:
                try:
                    dongle.create_dongle(target, registry)
                except OSError as exc:
                    flash("Gagal menulis ke flashdisk: {}".format(exc), "err")
                else:
                    flash("Dongle berhasil dibuat. Kode undangan petugas: {} "
                          "(catat sekarang, hanya ditampilkan sekali).".format(officer_code), "ok")
                    return redirect(url_for("index"))
        return render_template("setup.html", drives=drives, orphan=orphan,
                               show_all=bool(request.args.get("semua")))

    @app.route("/quit", methods=["POST"])
    def quit_app():
        if not app.config.get("ALLOW_QUIT"):
            abort(404)
        threading.Timer(0.6, os._exit, args=(0,)).start()
        return render_template("closed.html")

    def read_face_frames():
        files = [f for f in request.files.getlist("face") if f and f.filename]
        return [f.read() for f in files[:face.MAX_ENROLL_FRAMES]]

    def pack_face(sigs):
        return dbcrypto.encrypt_field(base64.b64encode(face.template_to_bytes(sigs)).decode(), g.master)

    def unpack_face(token):
        return face.template_from_bytes(base64.b64decode(dbcrypto.decrypt_field(token, g.master)))

    # ======================================================== AUTENTIKASI
    @app.route("/")
    def index():
        return redirect(url_for("dashboard" if g.user else "login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "reporter")
            finger = request.files.get("fingerprint")
            face_frames = read_face_frames()
            if not (3 <= len(username) <= 30) or not username.replace("_", "").isalnum():
                flash("Nama samaran 3-30 karakter (huruf/angka/_).", "err")
            elif len(password) < 8:
                flash("Password minimal 8 karakter.", "err")
            elif role not in ("reporter", "officer"):
                flash("Peran tidak valid.", "err")
            elif role == "officer" and not hmac.compare_digest(
                    request.form.get("officer_code", ""), officer_code):
                flash("Kode undangan petugas salah.", "err")
            elif not finger or not finger.filename:
                flash("Gambar sidik jari wajib diunggah.", "err")
            elif not face_frames:
                flash("Foto wajah wajib diambil dengan kamera.", "err")
            elif g.db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                flash("Nama sudah dipakai.", "err")
            else:
                try:
                    desc = biometric.extract_template(finger.read())
                    face_sigs = face.enroll(face_frames)
                except (biometric.BiometricError, face.FaceError) as exc:
                    flash(str(exc), "err")
                else:
                    tpl = dbcrypto.encrypt_field(
                        base64.b64encode(biometric.template_to_bytes(desc)).decode(),
                        g.master)
                    g.db.execute(
                        "INSERT INTO users (username,pw_hash,role,bio_template,face_template,created) "
                        "VALUES (?,?,?,?,?,?)",
                        (username, passwords.hash_password(password), role, tpl,
                         pack_face(face_sigs), time.time()))
                    g.db.commit()
                    flash("Registrasi berhasil. Silakan login.", "ok")
                    return redirect(url_for("login"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            finger = request.files.get("fingerprint")
            n, last = fails.get(username, (0, 0))
            if n >= MAX_FAILS and time.time() - last < LOCK_SECONDS:
                flash("Terlalu banyak percobaan gagal. Coba lagi sebentar.", "err")
                return render_template("login.html"), 429
            # Gerbang kualitas wajah: tidak bergantung pada akun mana pun, jadi pesannya tidak
            # membocorkan apakah nama pengguna ada. Bukan dihitung sebagai percobaan gagal.
            frames = read_face_frames()
            try:
                probes = face.usable_signatures(frames, face.MIN_LOGIN_FRAMES)
            except face.FaceError as exc:
                flash(str(exc), "err")
                return render_template("login.html"), 400
            row = g.db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            ok = False
            if row and passwords.verify_password(password, row["pw_hash"]) and finger and finger.filename:
                try:
                    probe = biometric.extract_template(finger.read())
                    raw = base64.b64decode(
                        dbcrypto.decrypt_field(row["bio_template"], g.master))
                    ok = biometric.is_match(biometric.template_from_bytes(raw), probe)
                except biometric.BiometricError:
                    ok = False
                if ok:  # faktor ketiga: wajah
                    if row["face_template"]:
                        ok = face.verify(unpack_face(row["face_template"]), probes)[0]
                    else:  # akun dari versi lama: daftarkan wajah pada login pertama ini
                        try:
                            g.db.execute("UPDATE users SET face_template=? WHERE id=?",
                                         (pack_face(face.enroll(frames)), row["id"]))
                            g.db.commit()
                        except face.FaceError:
                            ok = False
            elif not row:
                passwords.verify_password(password, "scrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA==$"
                                          "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")  # samakan waktu
            if ok:
                fails.pop(username, None)
                session.clear()
                session["uid"] = row["id"]
                session["csrf"] = secrets.token_urlsafe(24)
                return redirect(url_for("dashboard"))
            fails[username] = (n + 1 if time.time() - last < LOCK_SECONDS else 1, time.time())
            flash("Login gagal: password, sidik jari, atau wajah tidak cocok.", "err")
            return render_template("login.html"), 401
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ============================================================ LAPORAN
    @app.route("/dashboard")
    @login_required
    def dashboard():
        if g.user["role"] == "officer":
            rows = g.db.execute(
                "SELECT r.*, u.username AS owner FROM reports r JOIN users u ON u.id=r.owner_id "
                "ORDER BY r.created DESC").fetchall()
        else:
            rows = g.db.execute(
                "SELECT r.*, u.username AS owner FROM reports r JOIN users u ON u.id=r.owner_id "
                "WHERE r.owner_id=? ORDER BY r.created DESC", (g.user["id"],)).fetchall()
        reports = [dict(r, title_plain=tdec(r["title"])) for r in rows]
        return render_template("dashboard.html", reports=reports)

    @app.route("/report/new", methods=["GET", "POST"])
    @login_required
    def new_report():
        if g.user["role"] != "reporter":
            abort(403)
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            text = request.form.get("message", "").strip()
            category = request.form.get("category", "Lainnya")
            if not title or not text or category not in CATEGORIES:
                flash("Judul, kategori, dan isi laporan wajib diisi.", "err")
                return render_template("new_report.html")
            cur = g.db.execute(
                "INSERT INTO reports (owner_id,title,category,status,created) VALUES (?,?,?,?,?)",
                (g.user["id"], tenc(title), category, "baru", time.time()))
            g.db.commit()
            rid = cur.lastrowid
            store_message(rid, g.user["id"], text, bool(request.form.get("important")))
            try:
                handle_uploads(rid)
            except (stego.StegoError, ValueError) as exc:
                flash("Laporan dibuat, tetapi lampiran gagal: {}".format(exc), "err")
            return redirect(url_for("view_report", rid=rid))
        return render_template("new_report.html")

    @app.route("/report/<int:rid>", methods=["GET", "POST"])
    @login_required
    def view_report(rid):
        r = get_report_or_404(rid)
        if request.method == "POST":
            text = request.form.get("message", "").strip()
            if text:
                store_message(rid, g.user["id"], text, bool(request.form.get("important")))
            try:
                handle_uploads(rid)
            except (stego.StegoError, ValueError) as exc:
                flash("Lampiran gagal: {}".format(exc), "err")
            return redirect(url_for("view_report", rid=rid))
        msgs = []
        for m in g.db.execute(
                "SELECT m.*, u.username, u.role FROM messages m JOIN users u ON u.id=m.sender_id "
                "WHERE report_id=? ORDER BY m.id", (rid,)).fetchall():
            msgs.append(dict(m, text=read_message(m)))
        atts = []
        for a in g.db.execute("SELECT * FROM attachments WHERE report_id=? ORDER BY id", (rid,)):
            atts.append(dict(a, name_plain=tdec(a["name"])))
        owner = g.db.execute("SELECT username FROM users WHERE id=?", (r["owner_id"],)).fetchone()
        return render_template("report.html", r=r, title=tdec(r["title"]), msgs=msgs,
                               atts=atts, owner=owner["username"])

    @app.route("/report/<int:rid>/status", methods=["POST"])
    @officer_required
    def set_status(rid):
        get_report_or_404(rid)
        status = request.form.get("status")
        if status not in STATUSES:
            abort(400)
        g.db.execute("UPDATE reports SET status=? WHERE id=?", (status, rid))
        g.db.commit()
        log_event(rid, "STATUS_" + status.upper())
        return redirect(url_for("view_report", rid=rid))

    def get_attachment(aid):
        a = g.db.execute("SELECT * FROM attachments WHERE id=?", (aid,)).fetchone()
        if a is None:
            abort(404)
        get_report_or_404(a["report_id"])  # cek hak akses
        return a

    @app.route("/att/<int:aid>/preview")
    @login_required
    def att_preview(aid):
        a = get_attachment(aid)
        if a["kind"] != "image":
            abort(404)
        return send_file(a["path"], mimetype="image/png")

    @app.route("/att/<int:aid>/download")
    @login_required
    def att_download(aid):
        a = get_attachment(aid)
        with open(a["path"], "rb") as fh:
            stored = fh.read()
        name = tdec(a["name"])
        if a["kind"] == "file":
            try:
                data = filecrypto.decrypt_bytes(stored, g.master)
            except Exception:
                abort(500, "File rusak atau telah dimodifikasi (autentikasi gagal)")
            if hashlib.sha256(data).hexdigest() != a["sha256"]:
                abort(500, "Hash file tidak cocok dengan catatan blockchain")
            mime = "application/octet-stream"
        else:
            data, mime = stored, "image/png"
            name = os.path.splitext(name)[0] + "_stego.png"
        log_event(a["report_id"], "BUKTI_DIUNDUH", a["sha256"])
        return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=name)

    @app.route("/att/<int:aid>/extract")
    @login_required
    def att_extract(aid):
        a = get_attachment(aid)
        if a["kind"] != "image":
            abort(404)
        with open(a["path"], "rb") as fh:
            stored = fh.read()
        try:
            hidden = stego.extract(stored).decode()
            info = json.loads(tdec(hidden))
        except Exception:
            abort(500, "Gagal mengekstrak pesan tersembunyi")
        intact = hashlib.sha256(stored).hexdigest() == a["sha256"]
        log_event(a["report_id"], "PESAN_STEGO_DIBUKA", a["sha256"])
        return render_template("extract.html", a=a, name=tdec(a["name"]), info=info, intact=intact)

    # ========================================================= BLOCKCHAIN
    @app.route("/chain")
    @login_required
    def chain():
        rows = [dict(b) for b in g.db.execute("SELECT * FROM blocks ORDER BY idx")]
        valid, bad, reason = blockchain.validate_chain(rows)
        for b in rows:
            b["parsed"] = json.loads(b["data"])
        if g.user["role"] != "officer":  # pelapor hanya melihat blok miliknya
            own = {r["id"] for r in g.db.execute(
                "SELECT id FROM reports WHERE owner_id=?", (g.user["id"],))}
            rows = [b for b in rows if b["parsed"].get("report") in own]
        return render_template("chain.html", blocks=rows, valid=valid, bad=bad, reason=reason,
                               difficulty=blockchain.DIFFICULTY)

    # ================================================= DEMO / BUKTI (UJIAN)
    @app.route("/inspect", methods=["GET", "POST"])
    @officer_required
    def inspect():
        """Halaman bukti untuk dosen: tampilkan isi MENTAH database vs hasil dekripsi."""
        demo = None
        if request.method == "POST":
            demo = textcrypto.explain(request.form.get("plain", "")[:500], g.master)
        users = g.db.execute("SELECT id,username,role,pw_hash,bio_template FROM users").fetchall()
        msgs = g.db.execute("SELECT id,report_id,important,body FROM messages ORDER BY id DESC LIMIT 10").fetchall()
        return render_template("inspect.html", demo=demo, users=users, msgs=msgs)

    return app


if __name__ == "__main__":
    application = create_app()
    print("\n=== SilentReport (mode pengembang) ===")
    print("Kode undangan petugas:", application.config["OFFICER_CODE"])
    print("Untuk pengguna biasa, jalankan launcher.py atau klik SilentReport.bat\n")
    application.run(host="127.0.0.1", port=5000, debug=False)
