"""
Bulanıklaştırma yöntemlerinin karşılaştırılması - Ceren KILIÇ (6. hafta planı, İP10, İP13)

Gaussian bulanıklaştırma ile pikselleştirmeyi (mozaik) farklı güçlerde ve farklı nesne
boyutlarında karşılaştırır. Tespit hatalarını işin içine katmamak için, modelin bulduğu
kutular yerine GERÇEK etiket kutuları bulanıklaştırılır; böylece yalnızca bulanıklaştırma
yönteminin kendisi ölçülür.

Sayısal ölçüt - yeniden tespit oranı: Bulanıklaştırılmış görüntü modele tekrar verilir.
Model, gizlenmiş bir yüzü/plakayı hâlâ yüz/plaka olarak bulabiliyorsa, o bölgede tanınabilir
bilgi kalmış olabilir. Bu oran ne kadar düşükse anonimleştirme o kadar güçlüdür. (Bir tanıma
testi değildir; tanınabilirliğe dair dolaylı bir göstergedir.)
Buna ek olarak her yöntemden örnek kesitler yan yana çizilir (görsel değerlendirme).

Neden keskinlik (Laplacian varyansı) kullanılmadı? Pikselleştirme blokların arasında yapay
keskin kenarlar oluşturur; bu yüzden bölge ne kadar gizlenmiş olursa olsun Laplacian değeri
yüksek çıkar ve Gaussian ile karşılaştırılamaz. (Denemede pikselleştirilmiş bölgeler orijinalden
daha "keskin" ölçüldü.) Bu ölçüt yalnızca aynı yöntemin farklı ayarlarını karşılaştırırken anlamlıdır.

Çalıştırma (proje ana klasöründeyken):
    python src/bulanik_karsilastir.py --cihaz mps
    python src/bulanik_karsilastir.py --goruntu-sayisi 30     # daha hızlı deneme

Çıktılar:
    docs/sonuclar/bulaniklastirma.md, .csv, .png   -> tablo ve grafik (GitHub'a gider)
    outputs/bulanik_karsilastirma/ornekler.jpg     -> örnek kesitler (görüntü içerir, GitHub'a gitmez)
"""

import os
import random
import argparse
from collections import defaultdict
import numpy as np
import cv2

import tespit as T
import degerlendir as D
import bulaniklastir as B
from ortak import OUTPUTS, SONUC_KLASORU, SINIFLAR, test_seti_yukle, iou, yol

TOHUM = 42
# ad: (yöntem, güç, açıklama). Güç: gauss -> çekirdek / kenar oranı (her eksende), piksel -> uzun kenardaki blok sayısı
YONTEMLER = {
    "gauss_0.25": ("gauss", 0.25, "Gaussian, çekirdek = kenar × 0,25"),
    "gauss_0.5":  ("gauss", 0.5, "Gaussian, çekirdek = kenar × 0,5 (5. haftanın ayarı)"),
    "gauss_1.0":  ("gauss", 1.0, "Gaussian, çekirdek = kenar × 1,0 (6. haftadan itibaren varsayılan)"),
    "piksel_16":  ("piksel", 16, "Pikselleştirme, uzun kenarda 16 blok"),
    "piksel_8":   ("piksel", 8, "Pikselleştirme, uzun kenarda 8 blok"),
    "piksel_4":   ("piksel", 4, "Pikselleştirme, uzun kenarda 4 blok"),
}
BOYUTLAR = [(0, 16), (16, 32), (32, 64), (64, 10 ** 6)]
BOYUT_ADI = ["<16", "16–32", "32–64", "≥64"]
YENIDEN_TESPIT_ESIGI = 0.10      # 5. haftada seçilen eşik
MOD = "parcali"


def boyut_grubu(genislik):
    return next(i for i, (a, b) in enumerate(BOYUTLAR) if a <= genislik < b)


def goruntu_sec(goruntuler, sayi):
    """Yüz ve plaka içeren görüntülerden, senaryolara dengeli dağılan bir örnek seçer.
    S2 (kalabalık) çok sayıda küçük yüz içerdiğinden ayrıca dahil edilir; S9 nesne içermediği için alınmaz."""
    rastgele = random.Random(TOHUM)
    senaryolar = defaultdict(list)
    for g in goruntuler:
        if g["nesneler"] and g["senaryo"] != "S9":
            senaryolar[g["senaryo"]].append(g)
    secilen = []
    adet = max(1, sayi // max(1, len(senaryolar)))
    for sen in sorted(senaryolar):
        secilen += rastgele.sample(senaryolar[sen], min(adet, len(senaryolar[sen])))
    return secilen


def degerlendirilen(g):
    """WIDER FACE'te plaka etiketi yok: orada yalnızca yüzler bulanıklaştırılır ve ölçülür."""
    siniflar = D.degerlendirilen_siniflar(g)
    return [n for n in g["nesneler"] if n["sinif"] in siniflar]


def yeniden_bulundu_mu(nesne, tespitler):
    return any(t["sinif"] == nesne["sinif"] and t["guven"] >= YENIDEN_TESPIT_ESIGI and iou(t["kutu"], nesne["kutu"]) >= 0.5
               for t in tespitler)


def olc(model, goruntuler, cihaz):
    """Her (yöntem, sınıf, boyut grubu) için: nesne sayısı ve yeniden tespit edilen nesne sayısı."""
    sonuc = defaultdict(lambda: {"n": 0, "bulunan": 0})
    for i, g in enumerate(goruntuler, 1):
        img = cv2.imread(yol(g["goruntu"]))
        if img is None:
            continue
        nesneler = degerlendirilen(g)
        # Referans: bulanıklaştırmadan önce model bu nesneleri buluyor mu?
        tespitler = T.tespit(model, img, MOD, YENIDEN_TESPIT_ESIGI, cihaz)
        for n in nesneler:
            s = sonuc[("orijinal", n["sinif"], boyut_grubu(n["kutu"][2] - n["kutu"][0]))]
            s["n"] += 1
            s["bulunan"] += yeniden_bulundu_mu(n, tespitler)
        for ad, (yontem, guc, _) in YONTEMLER.items():
            anonim = B.anonimlestir(img, nesneler, yontem, guc=guc)
            tespitler = T.tespit(model, anonim, MOD, YENIDEN_TESPIT_ESIGI, cihaz)
            for n in nesneler:
                s = sonuc[(ad, n["sinif"], boyut_grubu(n["kutu"][2] - n["kutu"][0]))]
                s["n"] += 1
                s["bulunan"] += yeniden_bulundu_mu(n, tespitler)
        if i % 10 == 0 or i == len(goruntuler):
            print(f"  {i}/{len(goruntuler)} görüntü")
    return sonuc


def ornek_kesitler(goruntuler, hedef):
    """Her sınıf ve boyut grubundan birer nesne: orijinal + her yöntem yan yana."""
    rastgele = random.Random(TOHUM)
    adaylar = defaultdict(list)
    for g in goruntuler:
        for n in degerlendirilen(g):
            adaylar[(n["sinif"], boyut_grubu(n["kutu"][2] - n["kutu"][0]))].append((g, n))
    satirlar = []
    hucre = 150
    for sinif in SINIFLAR:
        for b in range(len(BOYUTLAR)):
            if not adaylar[(sinif, b)]:
                continue
            g, n = rastgele.choice(adaylar[(sinif, b)])
            img = cv2.imread(yol(g["goruntu"]))
            if img is None:
                continue
            x1, y1, x2, y2 = n["kutu"]
            cx, cy, yari = (x1 + x2) // 2, (y1 + y2) // 2, max(12, int(1.2 * max(x2 - x1, y2 - y1)))
            kes = lambda im: cv2.resize(im[max(0, cy - yari):cy + yari, max(0, cx - yari):cx + yari],
                                        (hucre, hucre), interpolation=cv2.INTER_NEAREST)
            parcalar = [kes(img)] + [kes(B.anonimlestir(img, [n], y, guc=gc)) for y, gc, _ in YONTEMLER.values()]
            etiket = np.full((hucre, 110, 3), 255, np.uint8)
            cv2.putText(etiket, D.ETIKET[sinif], (6, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 40), 1)
            cv2.putText(etiket, f"{BOYUT_ADI[b].replace('–', '-').replace('≥', '>=')} px", (6, 85),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1)
            satirlar.append(np.hstack([etiket] + parcalar))
    if not satirlar:
        return
    baslik = np.full((34, satirlar[0].shape[1], 3), 255, np.uint8)
    for k, ad in enumerate(["orijinal"] + list(YONTEMLER)):
        cv2.putText(baslik, ad, (110 + k * hucre + 8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 40, 40), 1)
    os.makedirs(hedef, exist_ok=True)
    cv2.imwrite(os.path.join(hedef, "ornekler.jpg"), np.vstack([baslik] + satirlar))


def raporla(sonuc, goruntu_sayisi):
    satirlar, md_satirlar = [], []
    for ad in ["orijinal"] + list(YONTEMLER):
        for sinif in SINIFLAR:
            for b in range(len(BOYUTLAR)):
                s = sonuc.get((ad, sinif, b))
                if not s or not s["n"]:
                    continue
                satirlar.append({"yontem": ad, "sinif": sinif, "boyut": BOYUT_ADI[b], "nesne": s["n"],
                                 "yeniden_tespit": s["bulunan"] / s["n"]})
    # Sınıf bazında özet (bütün boyutlar)
    for ad in ["orijinal"] + list(YONTEMLER):
        satir = [ad, YONTEMLER[ad][2] if ad in YONTEMLER else "Bulanıklaştırma yok (karşılaştırma için)"]
        for sinif in SINIFLAR:
            n = sum(sonuc[(ad, sinif, b)]["n"] for b in range(len(BOYUTLAR)) if (ad, sinif, b) in sonuc)
            k = sum(sonuc[(ad, sinif, b)]["bulunan"] for b in range(len(BOYUTLAR)) if (ad, sinif, b) in sonuc)
            satir.append(D.yuzde(k / n) if n else "–")
        md_satirlar.append(satir)

    D.csv_yaz("bulaniklastirma.csv", satirlar)
    n_yuz = sum(s["nesne"] for s in satirlar if s["yontem"] == "orijinal" and s["sinif"] == "yuz")
    n_plaka = sum(s["nesne"] for s in satirlar if s["yontem"] == "orijinal" and s["sinif"] == "plaka")
    md = ["# Bulanıklaştırma yöntemlerinin karşılaştırılması\n",
          f"{goruntu_sayisi} görüntüdeki {n_yuz} yüz ve {n_plaka} plaka, gerçek etiket kutuları kullanılarak "
          f"bulanıklaştırılmış ve model ({MOD} mod, eşik {YENIDEN_TESPIT_ESIGI:.2f}) bulanık görüntüde tekrar "
          f"çalıştırılmıştır. Yeniden tespit oranı ne kadar düşükse anonimleştirme o kadar güçlüdür.\n",
          D.tablo_md(["Yöntem", "Açıklama", "Yüz yeniden tespit %", "Plaka yeniden tespit %"], md_satirlar),
          "\nBoyut gruplarına göre yeniden tespit oranı:\n",
          D.tablo_md(["Yöntem", "Sınıf", "Genişlik (px)", "Nesne", "Yeniden tespit %"],
                     [[s["yontem"], D.ETIKET[s["sinif"]], s["boyut"], s["nesne"], D.yuzde(s["yeniden_tespit"])]
                      for s in satirlar]),
          "\n![Yeniden tespit oranı](bulaniklastirma.png)\n",
          "\nNot: 'Orijinal' satırı, bulanıklaştırmadan önce modelin aynı nesneleri bulma oranıdır (karşılaştırma "
          "tabanı). Yeniden tespit, tanınabilirliğin doğrudan ölçüsü değil dolaylı bir göstergesidir; görsel "
          "kontrol için outputs/bulanik_karsilastirma/ornekler.jpg dosyasına bakınız.\n"]
    with open(os.path.join(SONUC_KLASORU, "bulaniklastirma.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    grafik(satirlar)
    print("\n".join(md))


def grafik(satirlar):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    adlar = ["orijinal"] + list(YONTEMLER)
    renkler = {"orijinal": "#b5b4ae", "gauss_0.25": "#a9c8ef", "gauss_0.5": "#2a78d6", "gauss_1.0": "#174a86",
               "piksel_16": "#f6c3a9", "piksel_8": "#eb6834", "piksel_4": "#9c3a12"}
    fig, eksenler = plt.subplots(1, 2, figsize=(10, 3.4), sharey=True)
    for ax, sinif in zip(eksenler, SINIFLAR):
        gruplar = [b for b in BOYUT_ADI if any(s["sinif"] == sinif and s["boyut"] == b for s in satirlar)]
        w = 0.8 / len(adlar)
        for k, ad in enumerate(adlar):
            ys = [next((s["yeniden_tespit"] for s in satirlar if s["yontem"] == ad and s["sinif"] == sinif
                        and s["boyut"] == b), 0) for b in gruplar]
            ax.bar([i + (k - len(adlar) / 2 + 0.5) * w for i in range(len(gruplar))], ys, width=w * 0.95,
                   color=renkler[ad], label=ad)
        ax.set_xticks(range(len(gruplar)), gruplar)
        ax.set_xlabel("Nesne genişliği (piksel)", fontsize=9, color="#52514e")
        ax.set_title(D.ETIKET[sinif], fontsize=10)
        ax.set_ylim(0, 1.02)
        D._eksen_sade(ax)
    eksenler[0].set_ylabel("Yeniden tespit oranı", fontsize=9, color="#52514e")
    eksenler[1].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1, 1))
    fig.suptitle("Bulanıklaştırma sonrası modelin nesneyi yeniden bulma oranı (düşük = daha iyi gizleme)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(SONUC_KLASORU, "bulaniklastirma.png"), dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--goruntu-sayisi", type=int, default=70)
    ap.add_argument("--cihaz", default=None, help="cpu, mps (Apple) veya 0 (NVIDIA)")
    args = ap.parse_args()

    goruntuler = goruntu_sec(test_seti_yukle(), args.goruntu_sayisi)
    print(f"{len(goruntuler)} görüntü, {len(YONTEMLER)} yöntem (+ orijinal) karşılaştırılıyor...")
    model = T.model_yukle()
    os.makedirs(SONUC_KLASORU, exist_ok=True)
    sonuc = olc(model, goruntuler, args.cihaz)
    raporla(sonuc, len(goruntuler))
    hedef = os.path.join(OUTPUTS, "bulanik_karsilastirma")
    ornek_kesitler(goruntuler, hedef)
    print(f"\nKaydedildi: {os.path.relpath(SONUC_KLASORU)}/bulaniklastirma.md, .csv, .png ve "
          f"{os.path.relpath(hedef)}/ornekler.jpg")
