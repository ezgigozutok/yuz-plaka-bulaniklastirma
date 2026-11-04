"""
S7 (Türk plakası) için basit etiketleme aracı - Ezgi GÖZÜTOK

Test setindeki diğer senaryolar açık veri setlerinden geldi; Türk plakası içeren
etiketli bir açık set bulunamadığı için S7 görüntülerini ekip kendisi topluyor.
Bu araç fotoğraflardaki yüz ve plakaları elle işaretleyip ortak formatta kaydeder.

Etiketleme sırasında MODELİN tahminleri gösterilmez: aksi hâlde etiketleyen kişi
modelin kaçırdığı nesneleri de gözden kaçırmaya eğilimli olur ve recall olduğundan
yüksek çıkar.

Hazırlık:
    Fotoğrafları data/turk_plaka/ klasörüne koyun (JPG/PNG; iPhone HEIC ise JPG'ye çevirin).
    Bu klasör .gitignore'da, GitHub'a gitmez.

Çalıştırma:
    python src/etiketle.py                  # etiketleme penceresini açar
    python src/etiketle.py --test-setine-ekle   # etiketleri data/test_seti_s7.json'a yazar

Tuşlar:
    fareyle sürükle : kutu çiz
    p / y           : sıradaki kutuların sınıfı plaka / yüz (başta plaka)
    z               : son kutuyu sil
    boşluk veya n   : kaydet ve sonraki görüntü
    b               : önceki görüntü
    q               : kaydet ve çık
"""

import os
import json
import argparse
import cv2

from ortak import PROJE, DATA, TEST_SETI_S7

KLASOR = os.path.join(DATA, "turk_plaka")
ETIKET_DOSYASI = os.path.join(KLASOR, "etiketler.json")
EKRAN_EN = 1400          # büyük fotoğraflar ekrana sığsın diye bu genişliğe küçültülür
RENK = {"yuz": (0, 200, 0), "plaka": (0, 0, 255)}


def etiketleri_oku():
    if os.path.exists(ETIKET_DOSYASI):
        with open(ETIKET_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    return {}


def etiketleri_yaz(etiketler):
    with open(ETIKET_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(etiketler, f, ensure_ascii=False, indent=1)


def etiketle():
    dosyalar = sorted(f for f in os.listdir(KLASOR) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if not dosyalar:
        raise SystemExit(f"{KLASOR} içinde görüntü yok.")
    etiketler = etiketleri_oku()
    durum = {"sinif": "plaka", "bas": None, "simdi": None}
    i = 0

    def fare(olay, x, y, *_):
        if olay == cv2.EVENT_LBUTTONDOWN:
            durum["bas"] = (x, y)
        elif olay == cv2.EVENT_MOUSEMOVE and durum["bas"]:
            durum["simdi"] = (x, y)
        elif olay == cv2.EVENT_LBUTTONUP and durum["bas"]:
            (ax, ay), olcek = durum["bas"], durum["olcek"]
            x1, x2 = sorted((ax, x)); y1, y2 = sorted((ay, y))
            if x2 - x1 > 3 and y2 - y1 > 3:
                kutular.append({"sinif": durum["sinif"],
                                "kutu": [int(x1 / olcek), int(y1 / olcek), int(x2 / olcek), int(y2 / olcek)]})
            durum["bas"] = durum["simdi"] = None

    cv2.namedWindow("etiketle")
    cv2.setMouseCallback("etiketle", fare)
    while 0 <= i < len(dosyalar):
        ad = dosyalar[i]
        img = cv2.imread(os.path.join(KLASOR, ad))
        olcek = min(1.0, EKRAN_EN / img.shape[1])
        durum["olcek"] = olcek
        ekran = cv2.resize(img, None, fx=olcek, fy=olcek)
        kutular = etiketler.get(ad, {}).get("nesneler", [])
        while True:
            goster = ekran.copy()
            for k in kutular:
                x1, y1, x2, y2 = [int(v * olcek) for v in k["kutu"]]
                cv2.rectangle(goster, (x1, y1), (x2, y2), RENK[k["sinif"]], 2)
            if durum["bas"] and durum["simdi"]:
                cv2.rectangle(goster, durum["bas"], durum["simdi"], RENK[durum["sinif"]], 1)
            cv2.putText(goster, f"{i + 1}/{len(dosyalar)}  sinif: {durum['sinif']}  (p/y z n b q)",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow("etiketle", goster)
            tus = cv2.waitKey(20) & 0xFF
            if tus == ord("p"):
                durum["sinif"] = "plaka"
            elif tus == ord("y"):
                durum["sinif"] = "yuz"
            elif tus == ord("z") and kutular:
                kutular.pop()
            elif tus in (ord(" "), ord("n"), ord("b"), ord("q")):
                etiketler[ad] = {"boyut": [img.shape[1], img.shape[0]], "nesneler": kutular}
                etiketleri_yaz(etiketler)
                if tus == ord("q"):
                    i = -1
                else:
                    i += -1 if tus == ord("b") else 1
                    i = max(i, 0) if tus == ord("b") else i
                break
    cv2.destroyAllWindows()
    print(f"{len(etiketler)} görüntünün etiketi kaydedildi: {os.path.relpath(ETIKET_DOSYASI, PROJE)}")


def test_setine_ekle():
    etiketler = etiketleri_oku()
    if not etiketler:
        raise SystemExit("Önce etiketleme yapın: python src/etiketle.py")
    kayitlar = [{
        "goruntu": os.path.relpath(os.path.join(KLASOR, ad), PROJE),
        "kaynak": "ekip", "grup": "turk_plaka", "senaryo": "S7",
        "nesneler": e["nesneler"],
    } for ad, e in sorted(etiketler.items())]
    with open(TEST_SETI_S7, "w", encoding="utf-8") as f:
        json.dump(kayitlar, f, ensure_ascii=False, indent=1)
    plaka = sum(n["sinif"] == "plaka" for k in kayitlar for n in k["nesneler"])
    yuz = sum(n["sinif"] == "yuz" for k in kayitlar for n in k["nesneler"])
    print(f"S7: {len(kayitlar)} görüntü, {plaka} plaka, {yuz} yüz -> {os.path.relpath(TEST_SETI_S7, PROJE)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-setine-ekle", action="store_true")
    args = ap.parse_args()
    test_setine_ekle() if args.test_setine_ekle else etiketle()
