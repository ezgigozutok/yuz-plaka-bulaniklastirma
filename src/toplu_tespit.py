"""
Toplu tespit - Ezgi GÖZÜTOK (İP7, İP8)

Modeli test setinin tamamında (S1-S9, varsa S7 dahil) çalıştırır ve tespitleri ortak
formatta kaydeder. Tespitler bilerek DÜŞÜK bir eşikle (0.05) alınır; böylece eşik
taraması (İP12) için modeli tekrar tekrar çalıştırmaya gerek kalmaz, degerlendir.py
istediği eşiği sonradan uygular.

Çalıştırma (proje ana klasöründeyken):
    python src/toplu_tespit.py                   # iki mod da (tam + parcali)
    python src/toplu_tespit.py --mod tam
    python src/toplu_tespit.py --cihaz mps       # Apple M serisi işlemcide daha hızlı

Çıktı (outputs/ GitHub'a gitmez):
    outputs/tespitler_tam.json
    outputs/tespitler_parcali.json
"""

import os
import json
import time
import argparse
import cv2

import tespit as T
from ortak import OUTPUTS, test_seti_yukle, yol

HAM_ESIK = 0.05


def calistir(model, goruntuler, mod, cihaz):
    kayitlar, toplam = [], time.time()
    for i, g in enumerate(goruntuler, 1):
        img = cv2.imread(yol(g["goruntu"]))
        if img is None:
            print(f"  ! Okunamadı, atlanıyor: {g['goruntu']}")
            continue
        bas = time.time()
        tespitler = T.tespit(model, img, mod, HAM_ESIK, cihaz)
        sure = (time.time() - bas) * 1000
        kayitlar.append({
            "goruntu": g["goruntu"], "senaryo": g["senaryo"],
            "boyut": [img.shape[1], img.shape[0]],
            "sure_ms": round(sure, 1), "tespitler": tespitler,
        })
        if i % 20 == 0 or i == len(goruntuler):
            print(f"  [{mod}] {i}/{len(goruntuler)}  (son görüntü {sure:.0f} ms)")
    print(f"  [{mod}] bitti: {time.time() - toplam:.0f} sn")
    return kayitlar


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", choices=["tam", "parcali", "ikisi"], default="ikisi")
    ap.add_argument("--cihaz", default=None, help="cpu, mps (Apple) veya 0 (NVIDIA)")
    args = ap.parse_args()

    goruntuler = test_seti_yukle()
    senaryolar = sorted({g["senaryo"] for g in goruntuler})
    print(f"Test seti: {len(goruntuler)} görüntü, senaryolar: {', '.join(senaryolar)}")

    model = T.model_yukle()
    T.ham_tahmin(model, [cv2.imread(yol(goruntuler[0]["goruntu"]))], HAM_ESIK, args.cihaz)  # ısınma turu

    os.makedirs(OUTPUTS, exist_ok=True)
    for mod in (["tam", "parcali"] if args.mod == "ikisi" else [args.mod]):
        kayitlar = calistir(model, goruntuler, mod, args.cihaz)
        hedef = os.path.join(OUTPUTS, f"tespitler_{mod}.json")
        with open(hedef, "w", encoding="utf-8") as f:
            json.dump({"mod": mod, "ham_esik": HAM_ESIK, "kayitlar": kayitlar}, f, ensure_ascii=False)
        print(f"Kaydedildi: {os.path.relpath(hedef)}")

    print("\nSıradaki adım: python src/degerlendir.py")
