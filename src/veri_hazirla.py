"""
Test setini hazırlar - Ceren KILIÇ (İP3)

Ne yapar?
  1) PP4AV ve WIDER FACE etiketlerini okur
  2) Hepsini ekibin ortak formatına çevirir: {"sinif": "yuz"/"plaka", "kutu": [x1, y1, x2, y2]}
  3) Rapordaki Tablo 1 senaryolarına (S1-S9) göre görüntü seçer
  4) Sonuçları kaydeder:
       data/test_seti.json  -> seçilen görüntüler + gerçek kutular (Ezgi'nin değerlendirmesi için)
       test_seti.csv        -> hangi görüntü hangi senaryoda (GitHub'a gider, herkes aynı listeyi kullanır)

Çalıştırma (proje ana klasöründeyken):
    python src/veri_hazirla.py            # test setini oluştur
    python src/veri_hazirla.py --kontrol  # etiketleri görüntü üzerine çizip outputs/ klasörüne kaydet

Not: S7 (Türk plakası) ekip tarafından toplanacağı için burada yok.
"""

import os
import csv
import json
import random
import argparse
import statistics
from PIL import Image

# ---------------- Ayarlar ----------------
SENARYO_BASINA = 40      # her senaryodan kaç görüntü seçilecek
TOHUM = 42               # rastgele seçim her çalıştırmada aynı sonucu versin diye

# PP4AV etiketlerindeki sınıf numaraları. --kontrol ile gözle doğrulayın!
PP4AV_SINIFLAR = {0: "yuz", 1: "plaka"}

PROJE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJE, "data")
PP4AV_KLASOR = os.path.join(DATA, "pp4av")
WIDER_GORUNTU = os.path.join(DATA, "wider_face", "WIDER_val", "images")
WIDER_ETIKET = os.path.join(DATA, "wider_face", "wider_face_split", "wider_face_val_bbx_gt.txt")


# ---------------- 1) Etiketleri okuma ----------------

def wider_oku():
    """WIDER FACE: dosya adı / yüz sayısı / her yüz için 'x y w h bulanik ifade aydinlatma gecersiz ortulme poz'"""
    with open(WIDER_ETIKET) as f:
        satirlar = [s.strip() for s in f if s.strip()]

    goruntuler, i = [], 0
    while i < len(satirlar):
        ad, n = satirlar[i], int(satirlar[i + 1])
        i += 2
        nesneler = []
        for s in satirlar[i:i + max(n, 1)]:          # yüz yoksa bile bir satır sıfır var
            x, y, w, h, _, _, aydinlatma, gecersiz, ortulme, poz = map(int, s.split()[:10])
            if n == 0 or gecersiz == 1 or w <= 0 or h <= 0:
                continue
            nesneler.append({
                "sinif": "yuz",
                "kutu": [x, y, x + w, y + h],          # sol üst + boyut -> iki köşe
                "aydinlatma": aydinlatma, "ortulme": ortulme, "poz": poz,
            })
        i += max(n, 1)
        goruntuler.append({
            "goruntu": os.path.relpath(os.path.join(WIDER_GORUNTU, ad), PROJE),
            "kaynak": "wider_face",
            "grup": ad.split("/")[0],
            "nesneler": nesneler,
        })
    return goruntuler


def pp4av_oku():
    """PP4AV: her .png'nin yanında aynı adlı .txt, satır başına 'sinif cx cy w h' (0-1 arası oranlar)"""
    goruntuler = []
    for sehir in sorted(os.listdir(PP4AV_KLASOR)):
        klasor = os.path.join(PP4AV_KLASOR, sehir)
        # 'data' zip'lerin olduğu klasör; 'fisheye' balıkgözü lensle çekilmiş, bozuk perspektifli -> şimdilik dışarıda
        if sehir in ("data", "fisheye") or not os.path.isdir(klasor):
            continue
        for dosya in sorted(os.listdir(klasor)):
            if not dosya.endswith(".png"):
                continue
            yol = os.path.join(klasor, dosya)
            G, Y = Image.open(yol).size              # görüntüyü açmadan boyutunu okur, hızlı
            nesneler = []
            etiket = yol[:-4] + ".txt"
            if os.path.exists(etiket):
                with open(etiket) as f:
                    for s in f:
                        p = s.split()
                        if len(p) < 5:
                            continue
                        cx, cy, w, h = map(float, p[1:5])
                        nesneler.append({
                            "sinif": PP4AV_SINIFLAR.get(int(p[0]), p[0]),
                            "kutu": [int((cx - w / 2) * G), int((cy - h / 2) * Y),
                                     int((cx + w / 2) * G), int((cy + h / 2) * Y)],
                        })
            goruntuler.append({
                "goruntu": os.path.relpath(yol, PROJE),
                "kaynak": "pp4av",
                "grup": sehir,
                "nesneler": nesneler,
            })
    return goruntuler


# ---------------- 2) Senaryolar (rapor Tablo 1) ----------------

def gen(n):
    return n["kutu"][2] - n["kutu"][0]

def yuzler(g):
    return [n for n in g["nesneler"] if n["sinif"] == "yuz"]

def plakalar(g):
    return [n for n in g["nesneler"] if n["sinif"] == "plaka"]

def gece_mi(g):
    return "night" in g["grup"]

# Her senaryo: (kod, açıklama, görüntünün senaryoya uyup uymadığını söyleyen kural)
# Sayısal eşikler (100 px, 20 px...) bizim seçimimiz; gerekirse değiştirilebilir.
SENARYOLAR = [
    ("S1", "Yakın plan, tek kişi",
     lambda g: g["kaynak"] == "wider_face" and len(yuzler(g)) == 1 and gen(yuzler(g)[0]) >= 100),
    ("S2", "Kalabalık, çok sayıda küçük yüz",
     lambda g: g["kaynak"] == "wider_face" and len(yuzler(g)) >= 20
               and statistics.median(gen(y) for y in yuzler(g)) < 20),
    ("S3", "Profil / eğik açılı yüz",
     lambda g: g["kaynak"] == "wider_face" and len(yuzler(g)) <= 10
               and any(y["poz"] == 1 and gen(y) >= 30 for y in yuzler(g))),
    ("S4", "Gece / düşük ışık",
     lambda g: (g["kaynak"] == "wider_face" and len(yuzler(g)) <= 10
                and any(y["aydinlatma"] == 1 and gen(y) >= 30 for y in yuzler(g)))
               or (g["kaynak"] == "pp4av" and gece_mi(g) and g["nesneler"])),
    ("S5", "Kısmen kapanmış yüz",
     lambda g: g["kaynak"] == "wider_face" and len(yuzler(g)) <= 10
               and any(y["ortulme"] >= 1 and gen(y) >= 30 for y in yuzler(g))),
    ("S6", "Uzaktaki / eğik plaka",
     lambda g: g["kaynak"] == "pp4av" and not gece_mi(g) and plakalar(g)
               and max(gen(p) for p in plakalar(g)) < 40),
    ("S8", "Yüz ve plaka birlikte",
     lambda g: g["kaynak"] == "pp4av" and not gece_mi(g) and yuzler(g) and plakalar(g)),
    ("S9", "Yüz veya plaka yok",
     lambda g: g["kaynak"] == "pp4av" and not g["nesneler"]),
]


def test_seti_olustur(tumu):
    rastgele = random.Random(TOHUM)
    kullanilan, secilenler = set(), []

    print(f"\n{'Senaryo':8s}{'Aday':>7s}{'Seçilen':>9s}   Açıklama")
    for kod, aciklama, kural in SENARYOLAR:
        adaylar = [g for g in tumu if g["goruntu"] not in kullanilan and kural(g)]
        secim = rastgele.sample(adaylar, min(SENARYO_BASINA, len(adaylar)))
        for g in secim:
            kullanilan.add(g["goruntu"])
            secilenler.append({**g, "senaryo": kod})
        print(f"{kod:8s}{len(adaylar):7d}{len(secim):9d}   {aciklama}")
    return secilenler


def kaydet(secilenler):
    # Tam etiketlerle JSON (data/ içinde, GitHub'a gitmez)
    json_yolu = os.path.join(DATA, "test_seti.json")
    with open(json_yolu, "w", encoding="utf-8") as f:
        json.dump(secilenler, f, ensure_ascii=False, indent=1)

    # Kısa liste CSV (proje ana klasöründe, GitHub'a gider)
    csv_yolu = os.path.join(PROJE, "test_seti.csv")
    with open(csv_yolu, "w", newline="", encoding="utf-8") as f:
        yaz = csv.writer(f)
        yaz.writerow(["senaryo", "kaynak", "goruntu", "yuz_sayisi", "plaka_sayisi"])
        for g in secilenler:
            yaz.writerow([g["senaryo"], g["kaynak"], g["goruntu"], len(yuzler(g)), len(plakalar(g))])

    print(f"\nToplam {len(secilenler)} görüntü seçildi.")
    print(f"Kaydedildi: {os.path.relpath(json_yolu, PROJE)}")
    print(f"Kaydedildi: {os.path.relpath(csv_yolu, PROJE)}")


# ---------------- 3) Gözle kontrol ----------------

def kontrol(pp4av, sayi=4):
    """Hem yüz hem plaka içeren birkaç PP4AV görüntüsüne etiketleri çizer.
    Yeşil = 'yuz', kırmızı = 'plaka'. Renkler ters çıkarsa PP4AV_SINIFLAR'daki 0 ve 1'i değiştirin."""
    import cv2
    os.makedirs(os.path.join(PROJE, "outputs"), exist_ok=True)
    ornekler = [g for g in pp4av if yuzler(g) and plakalar(g)]
    for g in random.Random(TOHUM).sample(ornekler, min(sayi, len(ornekler))):
        img = cv2.imread(os.path.join(PROJE, g["goruntu"]))
        for n in g["nesneler"]:
            renk = (0, 255, 0) if n["sinif"] == "yuz" else (0, 0, 255)
            x1, y1, x2, y2 = n["kutu"]
            cv2.rectangle(img, (x1, y1), (x2, y2), renk, 2)
        cikti = os.path.join(PROJE, "outputs", "kontrol_" + os.path.basename(g["goruntu"]))
        cv2.imwrite(cikti, img)
        print("Çizildi:", os.path.relpath(cikti, PROJE))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kontrol", action="store_true", help="etiketleri çizip gözle kontrol et")
    args = ap.parse_args()

    print("PP4AV etiketleri okunuyor...")
    pp4av = pp4av_oku()
    print(f"  {len(pp4av)} görüntü (fisheye hariç)")

    if args.kontrol:
        kontrol(pp4av)
    else:
        print("WIDER FACE etiketleri okunuyor...")
        wider = wider_oku()
        print(f"  {len(wider)} görüntü")
        kaydet(test_seti_olustur(pp4av + wider))
