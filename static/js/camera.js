/* SilentReport - pengambilan foto wajah lewat kamera (getUserMedia). Tanpa library.
   Foto dikirim ke server lokal bersama form; yang disimpan hanya ciri wajah terenkripsi. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };

  function toast(m) { if (window.srToast) window.srToast(m); }

  function init(box) {
    var form = box.closest("form");
    var video = $("[data-cam-video]", box), msg = $("[data-cam-msg]", box), cam = $("[data-cam-box]", box);
    var bStart = $("[data-cam-start]", box), bShoot = $("[data-cam-shoot]", box), bRe = $("[data-cam-retake]", box);
    var thumbs = $("[data-cam-thumbs]", box), input = $("[data-cam-input]", box);
    var total = parseInt(box.getAttribute("data-frames"), 10) || 5;
    var minFrames = parseInt(box.getAttribute("data-min"), 10) || 2;
    var stream = null, busy = false;

    function say(t, kind) { msg.textContent = t; msg.className = "cam-msg" + (kind ? " " + kind : ""); }

    function stop() {
      if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
      video.srcObject = null; cam.classList.remove("live");
    }

    function start() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        say("Browser ini tidak mendukung kamera pada alamat ini. Unggah foto wajah di bawah.", "bad"); return;
      }
      say("Meminta izin kamera... pilih Izinkan.");
      navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }, audio: false })
        .then(function (s) {
          stream = s; video.srcObject = s; cam.classList.add("live");
          return video.play().catch(function () {});
        }).then(function () {
          if (!stream) return;
          say("Kamera siap. Posisikan wajah di dalam bingkai.", "ok");
          bStart.hidden = true; bShoot.disabled = false; bRe.hidden = true;
        }).catch(function (err) {
          var n = err && err.name;
          if (n === "NotAllowedError" || n === "SecurityError") say("Izin kamera ditolak. Izinkan kamera pada pengaturan browser, atau unggah foto wajah di bawah.", "bad");
          else if (n === "NotFoundError" || n === "OverconstrainedError") say("Kamera tidak ditemukan. Sambungkan kamera atau unggah foto wajah di bawah.", "bad");
          else if (n === "NotReadableError") say("Kamera sedang dipakai aplikasi lain. Tutup aplikasi itu lalu coba lagi.", "bad");
          else say("Kamera tidak dapat dibuka. Unggah foto wajah di bawah.", "bad");
        });
    }

    function snap() {
      return new Promise(function (resolve) {
        var w = video.videoWidth || 640, h = video.videoHeight || 480;
        var c = document.createElement("canvas"); c.width = w; c.height = h;
        c.getContext("2d").drawImage(video, 0, 0, w, h);
        c.toBlob(function (b) { resolve(b); }, "image/jpeg", 0.9);
      });
    }

    function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

    function shoot() {
      if (busy || !stream) return;
      busy = true; bShoot.disabled = true; thumbs.innerHTML = "";
      var blobs = [], i = 0;
      function next() {
        if (i >= total) return Promise.resolve();
        say("Tahan posisi... foto " + (i + 1) + " dari " + total);
        return snap().then(function (b) {
          blobs.push(b);
          var im = document.createElement("img"); im.alt = "Foto wajah " + (i + 1); im.src = URL.createObjectURL(b); thumbs.appendChild(im);
          i++; return wait(400);
        }).then(next);
      }
      say("Bersiap... lihat ke kamera"); cam.classList.add("shooting");
      wait(900).then(next).then(function () {
        var dt = new DataTransfer();
        blobs.forEach(function (b, k) { dt.items.add(new File([b], "wajah" + (k + 1) + ".jpg", { type: "image/jpeg" })); });
        input.files = dt.files;
        stop(); cam.classList.remove("shooting");
        say(blobs.length + " foto wajah siap dikirim.", "ok");
        box.classList.remove("invalid"); bRe.hidden = false; bShoot.disabled = true;
      }).catch(function () { say("Gagal mengambil foto. Coba lagi.", "bad"); bShoot.disabled = false; })
        .then(function () { busy = false; });
    }

    bStart.addEventListener("click", start);
    bShoot.addEventListener("click", shoot);
    bRe.addEventListener("click", function () { input.value = ""; thumbs.innerHTML = ""; bRe.hidden = true; start(); });
    input.addEventListener("change", function () {  // jalur cadangan: unggah manual
      thumbs.innerHTML = "";
      Array.prototype.slice.call(input.files).slice(0, total).forEach(function (f) {
        var im = document.createElement("img"); im.alt = "Foto wajah"; im.src = URL.createObjectURL(f); thumbs.appendChild(im);
      });
      if (input.files.length) { box.classList.remove("invalid"); say(input.files.length + " foto wajah dipilih.", "ok"); }
    });

    if (form) {
      form.addEventListener("submit", function (e) {
        var n = input.files ? input.files.length : 0;
        if (n < minFrames) {
          e.preventDefault(); e.stopImmediatePropagation();
          box.classList.add("invalid");
          $("[data-cam-err]", box).textContent = "Ambil minimal " + minFrames + " foto wajah (nyalakan kamera lalu klik Ambil foto wajah).";
          toast("Foto wajah belum diambil.");
        } else stop();
      }, true);
    }
    window.addEventListener("pagehide", stop);
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-face-capture]"), init);
})();
