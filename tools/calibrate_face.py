"""Kalibrasi ambang pengenalan wajah dengan FOTO ASLI anggota kelompok.

Mengapa perlu: ambang bawaan (0.18) diukur dari simulasi dua foto. Pencahayaan, kamera, dan wajah
kelompok Anda berbeda, jadi ukur sendiri dengan alat ini.

Siapkan folder seperti ini (minimal 2 orang, tiap orang minimal 8 foto dari sesi/cahaya berbeda,
disarankan 12-15; foto bisa dari kamera laptop, jepret di waktu atau tempat berbeda):

    foto_uji/
      budi/   f01.jpg f02.jpg ...
      sari/   f01.jpg ...
      dewi/   ...

Jalankan:
    python tools/calibrate_face.py foto_uji

Alat memakai 5 foto pertama tiap orang sebagai pendaftaran, sisanya diuji (per 3 foto, meniru login):
  - ASLI   : foto orang yang sama vs template-nya
  - PENIPU : foto orang lain vs template tersebut
lalu menyarankan ambang. Pasang dengan variabel lingkungan SR_FACE_THRESHOLD sebelum menjalankan aplikasi.
"""
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sr_crypto import face  # noqa: E402

EXT = ("*.jpg", "*.jpeg", "*.png", "*.bmp")


def load_person(folder):
    files = sorted(sum((glob.glob(os.path.join(folder, e)) for e in EXT), []))
    sigs, skipped = [], []
    for f in files:
        try:
            with open(f, "rb") as fh:
                sigs.append(face.extract_signature(fh.read()))
        except face.FaceError as exc:
            skipped.append((os.path.basename(f), str(exc)))
    return sigs, skipped


def groups(sigs, size=3):
    return [sigs[i:i + size] for i in range(0, len(sigs) - size + 1, size)] or ([sigs] if sigs else [])


def main(root):
    people = {}
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isdir(d):
            sigs, skipped = load_person(d)
            print("{:<14} {} foto terpakai, {} dilewati".format(name, len(sigs), len(skipped)))
            for fn, why in skipped:
                print("   dilewati {}: {}".format(fn, why))
            if len(sigs) >= 8:
                people[name] = sigs
            else:
                print("   -> diabaikan (butuh minimal 8 foto yang layak)")
    if len(people) < 2:
        sys.exit("Butuh minimal 2 orang dengan >= 8 foto layak masing-masing.")
    genuine, impostor = [], []
    for name, sigs in people.items():
        tmpl = sigs[:5]
        for grp in groups(sigs[5:]):
            genuine.append(face.score(tmpl, grp))
        for other, osigs in people.items():
            if other != name:
                for grp in groups(osigs[5:]):
                    impostor.append(face.score(tmpl, grp))
    g, i = np.array(genuine), np.array(impostor)
    print("\nASLI   n={:<4} min={:.3f} rata2={:.3f} p95={:.3f} maks={:.3f}".format(len(g), g.min(), g.mean(), np.percentile(g, 95), g.max()))
    print("PENIPU n={:<4} min={:.3f} rata2={:.3f} p5={:.3f}  maks={:.3f}".format(len(i), i.min(), i.mean(), np.percentile(i, 5), i.max()))
    ths = np.linspace(0.05, 0.40, 71)
    frr = np.array([(g > t).mean() for t in ths]); far = np.array([(i <= t).mean() for t in ths])
    k = int(np.argmin(np.abs(frr - far)))
    print("\nAmbang  FRR(asli ditolak)  FAR(penipu lolos)")
    for t in (0.12, 0.15, 0.18, 0.21, 0.24, 0.27):
        print("{:.2f}    {:>6.1f}%           {:>6.1f}%".format(t, 100 * (g > t).mean(), 100 * (i <= t).mean()))
    if g.max() >= i.min():
        print("\nTitik seimbang (EER): ambang {:.3f} dengan FRR {:.1f}% dan FAR {:.1f}%".format(ths[k], 100 * frr[k], 100 * far[k]))
    if g.max() < i.min():
        rec = (g.max() + i.min()) / 2
        print("Data terpisah bersih. Ambang disarankan (tengah celah): {:.3f}".format(rec))
    else:
        rec = float(np.clip(ths[k], 0.12, 0.30))
        print("PERHATIAN: sebaran asli dan penipu SALING TUMPANG TINDIH. Perbaiki pencahayaan/foto uji,")
        print("atau terima FAR/FRR di atas. Untuk aplikasi keamanan, utamakan FAR rendah. Ambang disarankan: {:.3f}".format(rec))
    print("\nPasang sebelum menjalankan aplikasi:")
    print("   PowerShell:  $env:SR_FACE_THRESHOLD=\"{:.3f}\"".format(rec))
    print("   Linux/Mac :  export SR_FACE_THRESHOLD={:.3f}".format(rec))


if __name__ == "__main__":
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit(__doc__)
    main(sys.argv[1])
