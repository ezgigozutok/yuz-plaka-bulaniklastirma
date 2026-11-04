"""
Uçtan uca anonimleştirme (prototip) - İP16'nın ilk hâli

Görüntü oku -> yüz ve plakaları tespit et -> sınıf bazlı eşik uygula -> bulanıklaştır -> kaydet

Çalıştırma (proje ana klasöründeyken):
    python src/anonimlestir.py foto.jpg
    python src/anonimlestir.py klasor/ --mod parcali --yontem piksel
    python src/anonimlestir.py foto.jpg --kutular      # yanına tespit kutulu hâlini de kaydeder

Eşikler: degerlendir.py çalıştırıldıysa docs/sonuclar/esikler.json'daki seçilen eşikler,
çalıştırılmadıysa model kartındaki eşikler (yüz 0.222, plaka 0.263) kullanılır.

Çıktı: outputs/anonim/<dosya_adı>_anonim.jpg
"""

import os
import sys
import time
import argparse
import cv2

import tespit as T
from bulaniklastir import anonimlestir
from ortak import OUTPUTS, esikleri_yukle

UZANTILAR = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def dosyalari_bul(girdi):
    if os.path.isdir(girdi):
        return [os.path.join(girdi, f) for f in sorted(os.listdir(girdi)) if f.lower().endswith(UZANTILAR)]
    return [girdi]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("girdi", help="görüntü dosyası veya klasör")
    ap.add_argument("--mod", choices=["tam", "parcali"], default="parcali")
    ap.add_argument("--yontem", choices=["gauss", "piksel"], default="gauss")
    ap.add_argument("--kutular", action="store_true", help="tespit kutularını çizilmiş hâlini de kaydet")
    ap.add_argument("--cikti", default=os.path.join(OUTPUTS, "anonim"))
    ap.add_argument("--cihaz", default=None, help="cpu, mps (Apple) veya 0 (NVIDIA)")
    args = ap.parse_args()

    dosyalar = dosyalari_bul(args.girdi)
    if not dosyalar:
        sys.exit("Görüntü bulunamadı.")
    esikler = esikleri_yukle()
    print(f"Eşikler: {esikler}  |  mod: {args.mod}  |  yöntem: {args.yontem}")

    model = T.model_yukle()
    os.makedirs(args.cikti, exist_ok=True)
    for dosya in dosyalar:
        img = cv2.imread(dosya)
        if img is None:
            print(f"  ! Okunamadı: {dosya} (iPhone HEIC ise JPG olarak dışa aktarın)")
            continue
        bas = time.time()
        tespitler = T.esik_uygula(T.tespit(model, img, args.mod, 0.05, args.cihaz), esikler)
        sonuc = anonimlestir(img, tespitler, args.yontem)
        sure = (time.time() - bas) * 1000

        ad = os.path.splitext(os.path.basename(dosya))[0]
        cv2.imwrite(os.path.join(args.cikti, f"{ad}_anonim.jpg"), sonuc)
        if args.kutular:
            cv2.imwrite(os.path.join(args.cikti, f"{ad}_kutular.jpg"), T.kutulari_ciz(img, tespitler))
        yuz = sum(t["sinif"] == "yuz" for t in tespitler)
        print(f"  {os.path.basename(dosya)}: {yuz} yüz, {len(tespitler) - yuz} plaka, {sure:.0f} ms")

    print(f"Kaydedildi: {os.path.relpath(args.cikti)}/")
