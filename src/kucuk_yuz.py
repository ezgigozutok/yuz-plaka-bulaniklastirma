"""
Küçük yüzler için iyileştirme denemesi - Ceren KILIÇ (6. hafta planı, İP14)

5. haftanın hata analizi: kaçırılan yüzlerin büyük kısmı 16 pikselden dar. Model,
1280 px'lik parçaların 640 px'e küçültülmüş hâliyle eğitildi; yani modele giren her
görüntü/parça 640 px'e iner. 16 px'lik bir yüz, 1024 px'lik bir WIDER FACE görüntüsünde
640'a inince ~10 px kalır ve model onu göremez.

Bu betik, yeniden eğitim yapmadan, sadece modele görüntüyü nasıl verdiğimizi değiştiren
ayarları dener ve 5. haftadaki yöntemle aynı ölçütlerle karşılaştırır:

    referans        : 5. haftanın seçtiği ayar (parçalı, parça 1280 px, giriş 640 px)
    tam_960 / 1280  : görüntünün tamamı daha büyük girişle (daha az küçültme)
    parca_640       : 640 px'lik parçalar -> parçalar hiç küçültülmez (yüzler ~2 kat büyük görünür)
    parca_1280_g1280: 1280 px parçalar, 1280 px girişle (benzer büyütme, daha az parça)

Adil karşılaştırma için hepsinde aynı eşik (5. haftada seçilen 0,10) kullanılır; ayrıca
her ayar için F2'yi en yüksek yapan eşik de ayrıca raporlanır.

Çalıştırma (proje ana klasöründeyken):
    python src/kucuk_yuz.py --cihaz mps              # Apple M serisi (önerilir)
    python src/kucuk_yuz.py --ayar referans parca_640   # yalnızca seçilen ayarlar
    python src/kucuk_yuz.py --sadece-degerlendir     # tespitler zaten varsa modeli çalıştırmadan özetle

Çıktılar:
    outputs/tespitler_ky_<ayar>.json   -> ham tespitler (GitHub'a gitmez)
    docs/sonuclar/kucuk_yuz.md, .csv, .png -> karşılaştırma tablosu ve grafik (GitHub'a gider)

Not: Ayar, aynı test seti üzerinde seçildiği için seçilen ayarın sonuçları biraz iyimser olabilir
(test setine uydurma riski). Bu durum raporda bir sınırlılık olarak belirtilmelidir.
"""

import os
import json
import time
import argparse
import cv2

import tespit as T
import degerlendir as D
from ortak import OUTPUTS, SONUC_KLASORU, SINIFLAR, test_seti_yukle, esikleri_yukle, yol

HAM_ESIK = 0.05

# ad: (mod, giriş boyutu, parça boyutu, açıklama)
AYARLAR = {
    "referans":         ("parcali", 640, 1280, "5. hafta: parça 1280, giriş 640"),
    "tam_960":          ("tam", 960, None, "Tam görüntü, giriş 960"),
    "tam_1280":         ("tam", 1280, None, "Tam görüntü, giriş 1280"),
    "parca_640":        ("parcali", 640, 640, "Parça 640, giriş 640"),
    "parca_1280_g1280": ("parcali", 1280, 1280, "Parça 1280, giriş 1280"),
}
KUCUK = (0, 16)          # hata analizindeki en küçük boyut grubu
ORTA = (16, 32)


def dosya(ad):
    return os.path.join(OUTPUTS, f"tespitler_ky_{ad}.json")


def calistir(model, goruntuler, ad, cihaz):
    mod, imgsz, parca, _ = AYARLAR[ad]
    kayitlar, bas_toplam = [], time.time()
    for i, g in enumerate(goruntuler, 1):
        img = cv2.imread(yol(g["goruntu"]))
        if img is None:
            print(f"  ! Okunamadı, atlanıyor: {g['goruntu']}")
            continue
        bas = time.time()
        tespitler = T.tespit(model, img, mod, HAM_ESIK, cihaz, imgsz=imgsz, parca=parca or T.PARCA)
        kayitlar.append({"goruntu": g["goruntu"], "senaryo": g["senaryo"], "boyut": [img.shape[1], img.shape[0]],
                         "sure_ms": round((time.time() - bas) * 1000, 1), "tespitler": tespitler})
        if i % 40 == 0 or i == len(goruntuler):
            print(f"  [{ad}] {i}/{len(goruntuler)}")
    with open(dosya(ad), "w", encoding="utf-8") as f:
        json.dump({"ayar": ad, "ham_esik": HAM_ESIK, "kayitlar": kayitlar}, f, ensure_ascii=False)
    print(f"  [{ad}] bitti: {time.time() - bas_toplam:.0f} sn -> {os.path.relpath(dosya(ad))}")


def boyut_recall(gt, sinif, aralik):
    secim = [o for o in gt if o["sinif"] == sinif and aralik[0] <= o["genislik"] < aralik[1]]
    return (sum(o["bulundu"] for o in secim) / len(secim)) if secim else None, len(secim)


def ayar_ozeti(gercekler, kayitlar, esikler):
    gt, fp = D.olaylar(gercekler, kayitlar, esikler)
    sonuc = {s: D.ozetle(gt, fp, s) for s in SINIFLAR}
    return gt, fp, sonuc


def karsilastir(adlar):
    gercekler = {g["goruntu"]: g for g in test_seti_yukle()}
    sabit = esikleri_yukle()
    satirlar, md_satirlar, boyutlar = [], [], {}
    for ad in adlar:
        if not os.path.exists(dosya(ad)):
            print(f"  - {ad}: tespit dosyası yok, atlanıyor")
            continue
        with open(dosya(ad), encoding="utf-8") as f:
            kayitlar = json.load(f)["kayitlar"]
        gt, _, sonuc = ayar_ozeti(gercekler, kayitlar, sabit)
        y, p = sonuc["yuz"], sonuc["plaka"]
        k_r, k_n = boyut_recall(gt, "yuz", KUCUK)
        o_r, _ = boyut_recall(gt, "yuz", ORTA)
        f2_secilen = D.esik_sec(D.esik_taramasi(gercekler, kayitlar))
        _, _, f2_sonuc = ayar_ozeti(gercekler, kayitlar, f2_secilen)
        sure = sum(k["sure_ms"] for k in kayitlar) / max(1, len(kayitlar))
        boyutlar[ad] = [boyut_recall(gt, "yuz", a)[0] for a in D.BOYUT_ARALIKLARI]
        satir = {"ayar": ad, "aciklama": AYARLAR[ad][3],
                 "yuz_P": y["P"], "yuz_R": y["R"], "yuz_F2": y["F2"], "yuz_FP": y["FP"],
                 "yuz_R_0_16": k_r, "yuz_R_16_32": o_r, "kucuk_yuz_sayisi": k_n,
                 "plaka_P": p["P"], "plaka_R": p["R"],
                 "sizintisiz": D.sizintisiz_oran(gt),
                 "f2_yuz_esik": f2_secilen["yuz"], "f2_yuz_R": f2_sonuc["yuz"]["R"], "f2_yuz_F2": f2_sonuc["yuz"]["F2"],
                 "ms": sure}
        satirlar.append(satir)
        o = D.ondalik
        md_satirlar.append([ad, satir["aciklama"], o(y["P"]), o(y["R"]), o(y["F2"]), y["FP"], o(k_r), o(o_r),
                            o(p["P"]), o(p["R"]), D.yuzde(satir["sizintisiz"]), f"{sure:.0f}"])
    if not satirlar:
        raise SystemExit("Karşılaştırılacak tespit yok. Önce: python src/kucuk_yuz.py")

    os.makedirs(SONUC_KLASORU, exist_ok=True)
    D.csv_yaz("kucuk_yuz.csv", satirlar)
    esik_metni = ", ".join(f"{D.ETIKET[s]} {sabit[s]:.2f}" for s in SINIFLAR)
    md = ["# Küçük yüzler için iyileştirme denemesi\n",
          f"Test seti: {len(gercekler)} görüntü. Tüm ayarlarda aynı eşik kullanılmıştır ({esik_metni}).\n",
          D.tablo_md(["Ayar", "Açıklama", "Yüz P", "Yüz R", "Yüz F2", "Yüz FP", "R (<16 px)", "R (16–32 px)",
                      "Plaka P", "Plaka R", "Sızıntısız %", "ms/görüntü"], md_satirlar),
          "\nHer ayar için ayrıca F2'yi en yüksek yapan yüz eşiği:\n",
          D.tablo_md(["Ayar", "Yüz eşiği", "Yüz R", "Yüz F2"],
                     [[s["ayar"], f'{s["f2_yuz_esik"]:.2f}'.replace(".", ","), D.ondalik(s["f2_yuz_R"]),
                       D.ondalik(s["f2_yuz_F2"])] for s in satirlar]),
          "\n![Boyuta göre yüz recall](kucuk_yuz.png)\n"]
    ref = next((s for s in satirlar if s["ayar"] == "referans"), None)
    if ref:
        en_iyi = max(satirlar, key=lambda s: s["yuz_F2"])
        md.append("\n## Otomatik gözlemler (rapora yazmadan önce kontrol edin)\n")
        for s in satirlar:
            if s is ref:
                continue
            md.append(f"- {s['ayar']}: yüz recall {D.ondalik(ref['yuz_R'])} → {D.ondalik(s['yuz_R'])}, "
                      f"<16 px recall {D.ondalik(ref['yuz_R_0_16'])} → {D.ondalik(s['yuz_R_0_16'])}, "
                      f"yüz FP {ref['yuz_FP']} → {s['yuz_FP']}, süre {ref['ms']:.0f} → {s['ms']:.0f} ms.\n")
        md.append(f"- Yüz F2'ye göre en iyi ayar: **{en_iyi['ayar']}** ({D.ondalik(en_iyi['yuz_F2'])}).\n")
    with open(os.path.join(SONUC_KLASORU, "kucuk_yuz.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    grafik(boyutlar)
    print("\n".join(md))
    print(f"\nKaydedildi: {os.path.relpath(SONUC_KLASORU)}/kucuk_yuz.md, .csv, .png")


def grafik(boyutlar):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    etiketler = [f"{a}-{b}" if b < 10 ** 6 else f"≥{a}" for a, b in D.BOYUT_ARALIKLARI]
    renkler = ["#52514e", "#2a78d6", "#eb6834", "#1f9e74", "#9b59b6"]
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    for (ad, r), renk in zip(boyutlar.items(), renkler):
        ax.plot(etiketler, [v if v is not None else float("nan") for v in r], marker="o", ms=4, lw=2,
                color=renk, ls="--" if ad == "referans" else "-", label=ad)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Yüz genişliği (piksel)", fontsize=9, color="#52514e")
    ax.set_ylabel("Recall", fontsize=9, color="#52514e")
    D._eksen_sade(ax)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("Ayarlara göre yüz recall (boyut gruplarına göre)", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(SONUC_KLASORU, "kucuk_yuz.png"), dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ayar", nargs="+", choices=list(AYARLAR), default=list(AYARLAR))
    ap.add_argument("--cihaz", default=None, help="cpu, mps (Apple) veya 0 (NVIDIA)")
    ap.add_argument("--sadece-degerlendir", action="store_true")
    args = ap.parse_args()

    if not args.sadece_degerlendir:
        goruntuler = test_seti_yukle()
        print(f"Test seti: {len(goruntuler)} görüntü | ayarlar: {', '.join(args.ayar)}")
        model = T.model_yukle()
        T.ham_tahmin(model, [cv2.imread(yol(goruntuler[0]["goruntu"]))], HAM_ESIK, args.cihaz)  # ısınma
        for ad in args.ayar:
            if os.path.exists(dosya(ad)):
                print(f"  [{ad}] zaten var, atlanıyor (yeniden çalıştırmak için dosyayı silin)")
                continue
            calistir(model, goruntuler, ad, args.cihaz)
    karsilastir(args.ayar)
