# src

| Dosya | İş paketi | Ne yapar |
|---|---|---|
| `veri_indir.py` | İP3 | PP4AV ve WIDER FACE (val) veri setlerini `data/` içine indirir |
| `veri_hazirla.py` | İP3, İP4 | Etiketleri ortak formata çevirir, S1–S9 senaryolarına göre 320 görüntü seçer |
| `etiketle.py` | İP3 (S7) | Türk plakalı fotoğraflar için elle etiketleme aracı |
| `tespit.py` | İP6–İP9 | Modeli yükler; tam ve parçalı (1280 px) tespit, sınıf bazlı eşik, kutu çizimi |
| `toplu_tespit.py` | İP7, İP8 | Modeli tüm test setinde çalıştırır, tespitleri `outputs/` içine kaydeder |
| `degerlendir.py` | İP12, İP14, İP15 | Precision/recall, eşik taraması, senaryo ve boyut bazında hata analizi |
| `bulaniklastir.py` | İP10, İP11 | Tespit edilen bölgeleri Gaussian veya piksel yöntemiyle bulanıklaştırır |
| `anonimlestir.py` | İP16 | Uçtan uca prototip: görüntü → tespit → bulanıklaştırma → çıktı |
| `ortak.py` | – | Ortak yollar, test seti okuma, IoU |
| `fp_incele.py` | İP14 | Yanlış tespitleri (varsayılan S9) tek tek gösterir; gerçek nesne / model hatası diye işaretlenir |
| `kucuk_yuz.py` | İP14 | Küçük yüzler için farklı giriş ve parça boyutlarını test setinde karşılaştırır |
| `etiketle.html` | İP3 (S7) | `etiketle.py`'nin tarayıcı sürümü (macOS + Anaconda'da OpenCV penceresi tuş almadığı için). Aynı `etiketler.json` formatını üretir |
| `bulanik_karsilastir.py` | İP10, İP13 | Gaussian ve pikselleştirmeyi farklı güç ve nesne boyutlarında karşılaştırır (yeniden tespit oranı + örnek görseller) |

Ortak tespit formatı: `{"sinif": "yuz" | "plaka", "kutu": [x1, y1, x2, y2], "guven": 0–1}`
