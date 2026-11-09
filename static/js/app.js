/* SilentReport - interaksi sisi klien. Tanpa library. Semua fitur aman bila JS mati (progressive enhancement). */
(function () {
  "use strict";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; }
  }

  /* ---------- Tema terang/gelap ---------- */
  function applyTheme(t) { document.documentElement.setAttribute("data-theme", t); }
  var saved = store("sr-theme");
  applyTheme(saved || (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  var themeBtn = $("#theme-toggle");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next); store("sr-theme", next);
  });

  /* ---------- Menu mobile ---------- */
  var menuBtn = $("#menu-btn"), nav = $("#nav");
  if (menuBtn && nav) menuBtn.addEventListener("click", function () {
    var open = nav.classList.toggle("open");
    menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
  });

  /* ---------- Toast ---------- */
  function toast(msg) {
    var box = $("#toasts");
    if (!box) return;
    var t = document.createElement("div");
    t.className = "toast"; t.setAttribute("role", "status"); t.textContent = msg;
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, 2600);
  }
  window.srToast = toast;

  /* ---------- Alert dapat ditutup + hilang otomatis (yang sukses) ---------- */
  $$(".alert").forEach(function (a) {
    var x = $(".x", a);
    if (x) x.addEventListener("click", function () { a.remove(); });
    if (a.classList.contains("ok") && a.textContent.indexOf("Kode undangan") === -1) setTimeout(function () { a.remove(); }, 6000);
  });

  /* ---------- Tampilkan/sembunyikan password ---------- */
  $$("[data-toggle-password]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = $("#" + btn.getAttribute("data-toggle-password"));
      if (!input) return;
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "Sembunyikan" : "Tampilkan";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
    });
  });

  /* ---------- Indikator kekuatan password ---------- */
  var pw = $("[data-strength]");
  if (pw) {
    var bar = $("#pw-bar"), lab = $("#pw-label");
    pw.addEventListener("input", function () {
      var v = pw.value, score = 0;
      if (v.length >= 8) score++;
      if (v.length >= 12) score++;
      if (/[a-z]/.test(v) && /[A-Z]/.test(v)) score++;
      if (/\d/.test(v)) score++;
      if (/[^A-Za-z0-9]/.test(v)) score++;
      var names = ["Sangat lemah", "Lemah", "Cukup", "Baik", "Kuat", "Sangat kuat"];
      var colors = ["#b91c1c", "#b91c1c", "#b45309", "#ca8a04", "#047857", "#047857"];
      if (!v) { bar.style.width = "0"; lab.textContent = "Minimal 8 karakter. Kombinasikan huruf besar, angka, dan simbol."; return; }
      bar.style.width = Math.max(score / 5 * 100, 8) + "%"; bar.style.background = colors[score];
      lab.textContent = "Kekuatan: " + names[score];
    });
  }

  /* ---------- Dropzone file (klik, seret-lepas, pratinjau) ---------- */
  function fmtSize(n) {
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
    return (n / 1048576).toFixed(1) + " MB";
  }
  $$(".dz").forEach(function (dz) {
    var input = $("input[type=file]", dz);
    var nameEl = $(".name", dz), sizeEl = $(".size", dz), thumb = $("img", dz), clear = $(".dz-clear", dz);
    var maxMb = parseFloat(dz.getAttribute("data-max-mb") || "16");
    function show() {
      var f = input.files && input.files[0];
      if (!f) { dz.classList.remove("has-file"); if (thumb) thumb.removeAttribute("src"); return; }
      if (f.size > maxMb * 1048576) {
        toast("File terlalu besar. Maksimal " + maxMb + " MB.");
        input.value = ""; dz.classList.remove("has-file"); return;
      }
      nameEl.textContent = f.name; sizeEl.textContent = fmtSize(f.size);
      if (thumb) {
        if (f.type.indexOf("image/") === 0) { thumb.src = URL.createObjectURL(f); thumb.style.display = ""; }
        else thumb.style.display = "none";
      }
      dz.classList.add("has-file");
    }
    input.addEventListener("change", show);
    ["dragenter", "dragover"].forEach(function (ev) {
      dz.addEventListener(ev, function () { dz.classList.add("over"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      dz.addEventListener(ev, function () { dz.classList.remove("over"); });
    });
    if (clear) clear.addEventListener("click", function (e) {
      e.preventDefault(); e.stopPropagation(); input.value = ""; show();
    });
  });

  /* ---------- Penghitung karakter ---------- */
  $$("textarea[data-max]").forEach(function (ta) {
    var out = ta.parentNode.querySelector(".counter");
    var max = parseInt(ta.getAttribute("data-max"), 10);
    function upd() { if (out) out.textContent = ta.value.length + " / " + max; }
    ta.addEventListener("input", upd); upd();
  });

  /* ---------- Validasi form ringan + tombol loading ---------- */
  $$("form[data-validate]").forEach(function (form) {
    form.setAttribute("novalidate", "novalidate");
    form.addEventListener("submit", function (e) {
      var ok = true, first = null;
      $$(".field[data-required]", form).forEach(function (field) {
        var el = $("input, textarea, select", field);
        var empty = !el.value.trim();
        var tooShort = el.hasAttribute("minlength") && el.value.length < parseInt(el.getAttribute("minlength"), 10);
        var bad = (el.required && empty) || (!empty && tooShort);
        field.classList.toggle("invalid", bad);
        if (bad) { ok = false; if (!first) first = el; }
      });
      $$(".dz[data-required]", form).forEach(function (dz) {
        var input = $("input[type=file]", dz);
        var bad = !(input.files && input.files.length);
        dz.classList.toggle("invalid", bad);
        if (bad) { ok = false; toast("Lengkapi file yang wajib diunggah."); }
      });
      if (!ok) { e.preventDefault(); if (first) first.focus(); return; }
      var btn = $("button[type=submit].btn", form);
      if (btn) {
        setTimeout(function () { btn.classList.add("loading"); btn.disabled = true; }, 0);
        var lbl = btn.getAttribute("data-loading");
        if (lbl) btn.textContent = lbl;
      }
    });
    $$("input, textarea, select", form).forEach(function (el) {
      el.addEventListener("input", function () {
        var f = el.closest(".field"); if (f) f.classList.remove("invalid");
      });
    });
  });

  /* ---------- Kolom wajib sidik jari/peran petugas ---------- */
  var role = $("#role");
  var codeField = $("#officer-code-field");
  if (role && codeField) {
    var sync = function () { codeField.style.display = role.value === "officer" ? "" : "none"; };
    role.addEventListener("change", sync); sync();
  }

  /* ---------- Chat: gulir ke pesan terbaru, Ctrl+Enter kirim ---------- */
  var chat = $("#chat");
  if (chat) chat.scrollTop = chat.scrollHeight;
  $$("textarea[data-submit-hotkey]").forEach(function (ta) {
    ta.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); if (ta.form.requestSubmit) ta.form.requestSubmit(); else ta.form.submit(); }
    });
  });

  /* ---------- Salin hash ---------- */
  $$("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      function done() { toast("Hash disalin"); }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback);
      else fallback();
      function fallback() {
        var t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select();
        try { document.execCommand("copy"); done(); } catch (e) { toast("Gagal menyalin"); }
        t.remove();
      }
    });
  });

  /* ---------- Lightbox gambar ---------- */
  var lb = $("#lightbox");
  if (lb) {
    var lbImg = $("img", lb);
    $$("[data-zoom]").forEach(function (img) {
      img.addEventListener("click", function () { lbImg.src = img.getAttribute("data-zoom"); lb.classList.add("on"); });
    });
    lb.addEventListener("click", function () { lb.classList.remove("on"); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") lb.classList.remove("on"); });
  }

  /* ---------- Pencarian dan filter daftar laporan ---------- */
  var q = $("#filter-q"), st = $("#filter-status"), cnt = $("#filter-count");
  if (q || st) {
    var items = $$(".report-item");
    var run = function () {
      var term = (q ? q.value : "").trim().toLowerCase(), status = st ? st.value : "";
      var shown = 0;
      items.forEach(function (it) {
        var okT = !term || it.getAttribute("data-text").indexOf(term) !== -1;
        var okS = !status || it.getAttribute("data-status") === status;
        it.style.display = okT && okS ? "" : "none";
        if (okT && okS) shown++;
      });
      if (cnt) cnt.textContent = shown + " dari " + items.length + " laporan";
      var none = $("#no-match"); if (none) none.style.display = shown ? "none" : "";
    };
    if (q) q.addEventListener("input", run);
    if (st) st.addEventListener("change", run);
    run();
  }

  /* ---------- Konfirmasi tindakan ---------- */
  $$("[data-confirm]").forEach(function (el) {
    el.addEventListener("submit", function (e) {
      if (!window.confirm(el.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  /* ---------- Layar terkunci: periksa dongle otomatis ---------- */
  if ($("[data-poll-dongle]")) {
    var misses = 0;
    setInterval(function () {
      fetch("/api/dongle", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) {
        misses = 0;
        if (j.present || !j.configured) location.reload();
      }).catch(function () {
        misses++;
        var st = $("#dongle-status");
        if (misses > 2 && st) st.textContent = "Aplikasi tidak merespons. Pastikan jendela SilentReport masih terbuka.";
      });
    }, 2000);
  }
  var pr = $("[data-poll-reload]");
  if (pr) setTimeout(function () { location.reload(); }, parseInt(pr.getAttribute("data-poll-reload"), 10) || 4000);

  /* ---------- Tandai tautan navigasi aktif ---------- */
  $$("#nav a").forEach(function (a) {
    if (a.getAttribute("href") === location.pathname) a.classList.add("active");
  });
})();
