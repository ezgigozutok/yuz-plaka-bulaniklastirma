"""
Ortak yardımcılar - tüm modüllerin kullandığı yollar, test seti okuma ve IoU.

Ortak tespit formatı (ekipçe belirlendi, 4. hafta):
    {"sinif": "yuz" | "plaka", "kutu": [x1, y1, x2, y2], "guven": 0-1}
"""

import os
import json

PROJE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJE, "data")
OUTPUTS = os.path.join(PROJE, "outputs")
SONUC_KLASORU = os.path.join(PROJE, "docs", "sonuclar")   # sadece sayısal özetler (kişisel veri yok) -> GitHub'a gider

TEST_SETI = os.path.join(DATA, "test_seti.json")          # veri_hazirla.py üretir (S1-S6, S8, S9)
TEST_SETI_S7 = os.path.join(DATA, "test_seti_s7.json")    # etiketle.py üretir (S7 - Türk plakası)

SINIFLAR = ("yuz", "plaka")

# Model kartındaki önerilen sınıf bazlı eşikler (en yüksek F1) - kaynak [7]
MODEL_KARTI_ESIKLERI = {"yuz": 0.222, "plaka": 0.263}
ESIK_DOSYASI = os.path.join(SONUC_KLASORU, "esikler.json")  # degerlendir.py'nin seçtiği eşikler


def yol(goreli):
    """Test setindeki göreli yolu (data/...) mutlak yola çevirir."""
    return goreli if os.path.isabs(goreli) else os.path.join(PROJE, goreli)


def test_seti_yukle():
    """Ana test setini ve varsa S7'yi birlikte döndürür."""
    if not os.path.exists(TEST_SETI):
        raise SystemExit("data/test_seti.json yok. Önce: python src/veri_indir.py && python src/veri_hazirla.py")
    with open(TEST_SETI, encoding="utf-8") as f:
        goruntuler = json.load(f)
    if os.path.exists(TEST_SETI_S7):
        with open(TEST_SETI_S7, encoding="utf-8") as f:
            goruntuler += json.load(f)
    return goruntuler


def esikleri_yukle():
    """degerlendir.py eşik seçtiyse onu, yoksa model kartındaki eşikleri döndürür."""
    if os.path.exists(ESIK_DOSYASI):
        with open(ESIK_DOSYASI, encoding="utf-8") as f:
            return json.load(f)["secilen"]
    return dict(MODEL_KARTI_ESIKLERI)


def iou(a, b):
    """İki kutunun kesişim / birleşim oranı (rapordaki Denklem 1)."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    kesisim = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    alan_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    alan_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    birlesim = alan_a + alan_b - kesisim
    return kesisim / birlesim if birlesim > 0 else 0.0
