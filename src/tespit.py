"""
Tespit modülü
  Ceren KILIÇ  - İP6 (model kurulumu), İP7 (yüz tespiti), İP9 (sonuçların görüntüye aktarılması)
  Ezgi GÖZÜTOK - İP8 (plaka tespiti), İP12 (eşik): model kartına uygun ayarlar ve parçalı tespit (5. hafta)

Diğer modüllere verilen çıktı formatı (ekipçe ortak):
    [{"sinif": "yuz" veya "plaka", "kutu": [x1, y1, x2, y2], "guven": 0.87}, ...]
    x1, y1 = kutunun sol üst köşesi, x2, y2 = sağ alt köşesi (piksel)

İki tespit modu var:
  tam     : görüntünün tamamı 640 px'e küçültülüp modele verilir (4. haftadaki yöntem)
  parcali : görüntü 1280x1280'lik örtüşen parçalara bölünür, her parça ayrıca taranır,
            ek olarak tam görüntü de taranır ve sonuçlar birleştirilir.
            Model 1280 px parçalarla eğitildiği için model kartı bu yöntemi öneriyor
            (TILE_SIZE=1280, TILE_OVERLAP_PCT=15, CHECK_FULL_IMAGE=true). Küçük/uzak
            plaka ve yüzlerde fark yaratması bekleniyor; hangisinin daha iyi olduğunu
            degerlendir.py ile ölçüyoruz.

Deneme (proje ana klasöründeyken):
    python src/tespit.py foto.jpg
    python src/tespit.py foto.jpg --mod parcali
"""

import os
import sys
import argparse
import numpy as np
import cv2

MODEL_YOLU = "models/yolo26m_face_lp.pt"   # YOLO26m Face & License-Plate v3.0.0 (raporda kaynak [7])
MODEL_LINKI = ("https://github.com/H-Held/yolo26-license-plate-face-detection/"
               "releases/download/v3.0.0/yolo26m_face_lp.pt")

IMGSZ = 640            # model 1280 px parçaların 640 px'e küçültülmüş hâliyle eğitildi
PARCA = 1280           # parçalı modda parça boyutu
ORTUSME = 0.15         # parçalar arası örtüşme oranı (model kartı: %15)
NMS_IOU = 0.5          # aynı nesnenin iki kez bulunduğunu kabul etmek için IoU eşiği

# Modelin İngilizce sınıf adlarını ekibin ortak adlarına çevirir
SINIF_ADLARI = {"face": "yuz", "license-plate": "plaka"}


# ---------------- İP6 - Modeli yükle ----------------
def model_yukle(yol=MODEL_YOLU):
    from ultralytics import YOLO   # import burada: testler ultralytics olmadan da çalışsın
    if not os.path.exists(yol):
        sys.exit(f"Model dosyası yok: {yol}\nİndir:  mkdir -p models && curl -L -o {yol} {MODEL_LINKI}")
    model = YOLO(yol)
    print("Modelin sınıfları:", model.names)
    return model


# ---------------- Modelden ham tahmin ----------------
def ham_tahmin(model, goruntuler, esik, cihaz=None):
    """Bir veya birden çok görüntü (BGR numpy) için her görüntüye N x 6 dizi döndürür:
    [x1, y1, x2, y2, guven, sinif_no]. Toplu (batch) çalıştırmak tek tek çalıştırmaktan hızlıdır."""
    sonuclar = model.predict(goruntuler, imgsz=IMGSZ, conf=esik, verbose=False, device=cihaz)
    cikti = []
    for s in sonuclar:
        b = s.boxes
        if len(b) == 0:
            cikti.append(np.zeros((0, 6), dtype=np.float32))
            continue
        cikti.append(np.concatenate([
            b.xyxy.cpu().numpy(),
            b.conf.cpu().numpy()[:, None],
            b.cls.cpu().numpy()[:, None],
        ], axis=1).astype(np.float32))
    return cikti


def ortak_formata_cevir(dizi, isimler):
    """N x 6 diziyi ekibin ortak formatına çevirir."""
    tespitler = []
    for x1, y1, x2, y2, guven, sinif in dizi:
        ad = isimler[int(sinif)]
        tespitler.append({
            "sinif": SINIF_ADLARI.get(ad, ad),
            "kutu": [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))],
            "guven": round(float(guven), 4),
        })
    return tespitler


# ---------------- İP7 / İP8 - Tam görüntü tespiti ----------------
def tespit_et(model, goruntu, esik=0.25, cihaz=None):
    """4. haftadaki yöntem: görüntünün tamamı tek seferde modele verilir."""
    return ortak_formata_cevir(ham_tahmin(model, [goruntu], esik, cihaz)[0], model.names)


# ---------------- Parçalı tespit (5. hafta) ----------------
def parca_konumlari(uzunluk, parca=PARCA, ortusme=ORTUSME):
    """Bir eksen boyunca parçaların başlangıç noktaları. Son parça kenara dayanır."""
    if uzunluk <= parca:
        return [0]
    adim = int(parca * (1 - ortusme))
    konumlar = list(range(0, uzunluk - parca, adim))
    konumlar.append(uzunluk - parca)
    return konumlar


def kutu_birlestir(dizi, iou_esigi=NMS_IOU, icerme_esigi=0.7):
    """Sınıf bazında NMS: aynı nesneye ait kutulardan güveni en yüksek olanı bırakır.
    Parça kenarında kesilen nesne bir parçada yarım, diğerinde tam görünebilir; bu yüzden
    IoU'nun yanında 'küçük kutunun büyük olanın içinde kalma oranı' da kontrol edilir."""
    if len(dizi) == 0:
        return dizi
    tutulan = []
    for sinif in np.unique(dizi[:, 5]):
        d = dizi[dizi[:, 5] == sinif]
        d = d[np.argsort(-d[:, 4])]                      # güvene göre azalan
        alan = (d[:, 2] - d[:, 0]) * (d[:, 3] - d[:, 1])
        silindi = np.zeros(len(d), dtype=bool)
        for i in range(len(d)):
            if silindi[i]:
                continue
            tutulan.append(d[i])
            ix1 = np.maximum(d[i, 0], d[i + 1:, 0]); iy1 = np.maximum(d[i, 1], d[i + 1:, 1])
            ix2 = np.minimum(d[i, 2], d[i + 1:, 2]); iy2 = np.minimum(d[i, 3], d[i + 1:, 3])
            kes = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
            iou = kes / (alan[i] + alan[i + 1:] - kes + 1e-9)
            icerme = kes / (np.minimum(alan[i], alan[i + 1:]) + 1e-9)
            silindi[i + 1:] |= (iou > iou_esigi) | (icerme > icerme_esigi)
    return np.array(tutulan, dtype=np.float32)


def parcali_tespit_et(model, goruntu, esik=0.25, cihaz=None):
    """Görüntüyü 1280 px parçalara bölüp her parçayı + tam görüntüyü tarar, sonuçları birleştirir."""
    Y, G = goruntu.shape[:2]
    xs, ys = parca_konumlari(G), parca_konumlari(Y)
    if len(xs) == 1 and len(ys) == 1:                     # görüntü zaten tek parçaya sığıyor
        return tespit_et(model, goruntu, esik, cihaz)

    parcalar, kaydirmalar = [goruntu], [(0, 0)]            # ilk eleman: tam görüntü
    for y in ys:
        for x in xs:
            parcalar.append(goruntu[y:y + PARCA, x:x + PARCA])
            kaydirmalar.append((x, y))

    hepsi = []
    for dizi, (dx, dy) in zip(ham_tahmin(model, parcalar, esik, cihaz), kaydirmalar):
        if len(dizi):
            dizi = dizi.copy()
            dizi[:, [0, 2]] += dx                          # parça koordinatı -> görüntü koordinatı
            dizi[:, [1, 3]] += dy
            hepsi.append(dizi)
    if not hepsi:
        return []
    return ortak_formata_cevir(kutu_birlestir(np.concatenate(hepsi)), model.names)


def tespit(model, goruntu, mod="tam", esik=0.25, cihaz=None):
    """Tek giriş noktası: mod = 'tam' veya 'parcali'."""
    if mod == "parcali":
        return parcali_tespit_et(model, goruntu, esik, cihaz)
    return tespit_et(model, goruntu, esik, cihaz)


# ---------------- İP12 - Sınıf bazlı eşik ----------------
def esik_uygula(tespitler, esikler):
    """Düşük eşikle alınmış tespitlerden, sınıf bazlı eşiğin altında kalanları eler.
    esikler örn. {"yuz": 0.222, "plaka": 0.263}"""
    return [t for t in tespitler if t["guven"] >= esikler.get(t["sinif"], 0.25)]


# ---------------- İP9 - Kutuları görüntü üzerine çiz ----------------
RENKLER = {"yuz": (0, 255, 0), "plaka": (0, 0, 255)}   # yeşil: yüz, kırmızı: plaka (BGR)


def kutulari_ciz(goruntu, tespitler):
    cizim = goruntu.copy()
    for t in tespitler:
        x1, y1, x2, y2 = t["kutu"]
        renk = RENKLER.get(t["sinif"], (255, 255, 0))
        cv2.rectangle(cizim, (x1, y1), (x2, y2), renk, 2)
        cv2.putText(cizim, f'{t["sinif"]} {t["guven"]:.2f}', (x1, max(15, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, renk, 1)
    return cizim


# Sadece bu dosyayı tek başına denemek için
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("goruntu")
    ap.add_argument("--mod", choices=["tam", "parcali"], default="tam")
    ap.add_argument("--esik", type=float, default=0.25)
    ap.add_argument("--cihaz", default=None, help="cpu, mps (Apple) veya 0 (NVIDIA)")
    args = ap.parse_args()

    goruntu = cv2.imread(args.goruntu)
    if goruntu is None:
        sys.exit("Görüntü okunamadı.")

    model = model_yukle()
    tespitler = tespit(model, goruntu, args.mod, args.esik, args.cihaz)

    print(f"{len(tespitler)} nesne bulundu ({args.mod}):")
    for t in tespitler:
        print(f'  {t["sinif"]:10s} güven={t["guven"]:.2f} kutu={t["kutu"]}')

    os.makedirs("outputs", exist_ok=True)          # outputs/ GitHub'a gitmez
    cv2.imwrite("outputs/tespit_sonucu.jpg", kutulari_ciz(goruntu, tespitler))
    print("Kaydedildi: outputs/tespit_sonucu.jpg")
