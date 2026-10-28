"""
Tespit modülü - Ceren KILIÇ
İP6: YOLO modelinin kurulması
İP7: Yüz tespiti
İP9: Tespit sonuçlarının görüntüye aktarılması

Diğer modüllere verilen çıktı formatı (ekipçe ortak):
    [{"sinif": "yuz" veya "plaka", "kutu": [x1, y1, x2, y2], "guven": 0.87}, ...]
    x1, y1 = kutunun sol üst köşesi, x2, y2 = sağ alt köşesi (piksel)

Deneme (proje ana klasöründeyken):
    python src/tespit.py foto.jpg
"""

import sys
import cv2
from ultralytics import YOLO

MODEL_YOLU = "models/yolo26m_face_lp.pt"   # YOLO26m Face & License-Plate (raporda kaynak [7])

# Modelin İngilizce sınıf adlarını ekibin ortak adlarına çevirir
SINIF_ADLARI = {"face": "yuz", "license-plate": "plaka"}


# İP6 - Modeli yükle
def model_yukle(yol=MODEL_YOLU):
    model = YOLO(yol)
    print("Modelin sınıfları:", model.names)   # hangi sınıf adlarını kullandığını görmek için
    return model


# İP7 - Tespit (eşik değeri Ezgi'nin İP12 testleriyle belirlenecek)
def tespit_et(model, goruntu, esik=0.25):
    sonuc = model.predict(goruntu, conf=esik, verbose=False)[0]
    tespitler = []
    for kutu in sonuc.boxes:
        x1, y1, x2, y2 = kutu.xyxy[0].tolist()
        tespitler.append({
            "sinif": SINIF_ADLARI.get(sonuc.names[int(kutu.cls[0])], sonuc.names[int(kutu.cls[0])]),
            "kutu": [int(x1), int(y1), int(x2), int(y2)],
            "guven": float(kutu.conf[0]),
        })
    return tespitler


# İP9 - Kutuları görüntü üzerine çiz (görsel kontrol için)
def kutulari_ciz(goruntu, tespitler):
    cizim = goruntu.copy()
    for t in tespitler:
        x1, y1, x2, y2 = t["kutu"]
        cv2.rectangle(cizim, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(cizim, f'{t["sinif"]} {t["guven"]:.2f}', (x1, max(15, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return cizim


# Sadece bu dosyayı tek başına denemek için
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanım: python src/tespit.py foto.jpg")
        sys.exit(1)

    goruntu = cv2.imread(sys.argv[1])   # deneme amaçlı basit okuma
    if goruntu is None:
        sys.exit("Görüntü okunamadı.")

    model = model_yukle()
    tespitler = tespit_et(model, goruntu)

    print(f"{len(tespitler)} nesne bulundu:")
    for t in tespitler:
        print(f'  {t["sinif"]:10s} güven={t["guven"]:.2f} kutu={t["kutu"]}')

    import os
    os.makedirs("outputs", exist_ok=True)          # outputs/ GitHub'a gitmez
    cv2.imwrite("outputs/tespit_sonucu.jpg", kutulari_ciz(goruntu, tespitler))
    print("Kaydedildi: outputs/tespit_sonucu.jpg")
