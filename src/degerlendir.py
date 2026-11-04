"""
Değerlendirme, eşik seçimi ve hata analizi - Ezgi GÖZÜTOK
  İP12: Tespit eşiğinin belirlenmesi
  İP14: Hata analizi (hangi senaryoda / hangi boyutta kaçırıyor?)
  İP15: Performans değerlendirmesi (IoU, precision, recall)

Ne yapar?
  1) toplu_tespit.py'nin kaydettiği tespitleri gerçek etiketlerle karşılaştırır.
     Eşleştirme PASCAL VOC'taki gibi: tespitler güvene göre sıralanır, her tespit
     henüz eşleşmemiş ve IoU >= 0.5 olan en iyi gerçek kutuya bağlanır.
       TP = eşleşen tespit, FP = eşleşmeyen tespit, FN = bulunamayan gerçek nesne
  2) Her sınıf için eşik taraması yapar (0.05-0.60) ve F2 skoru en yüksek eşiği seçer.
     F2, recall'a precision'dan 2 kat fazla ağırlık verir; çünkü bizim problemimizde
     kaçırılan bir yüz/plaka gizlilik ihlalidir, fazladan bulanıklık ise küçük bir kusurdur.
  3) Tam ve parçalı tespit modlarını karşılaştırır, iyi olanı seçer.
  4) Seçilen ayarlarla senaryo bazında sonuç, boyuta göre recall ve hata görselleri üretir.

Önemli kural: WIDER FACE görüntülerinde plakalar etiketlenmemiştir. Bu görüntülerde
yalnızca 'yuz' sınıfı değerlendirilir; yoksa model gerçekten var olan bir plakayı
bulduğunda haksız yere FP sayılırdı.

Çalıştırma (proje ana klasöründeyken):
    python src/degerlendir.py

Çıktılar:
    docs/sonuclar/ozet.md            -> rapora kopyalanacak tablolar (GitHub'a gider)
    docs/sonuclar/*.csv, *.png       -> tablolar ve grafikler (GitHub'a gider, kişisel veri yok)
    docs/sonuclar/esikler.json       -> seçilen eşikler (anonimlestir.py bunu kullanır)
    outputs/hata_ornekleri/*.jpg     -> en çok hata yapılan görüntüler (yüz içerir, GitHub'a gitmez)
"""

import os
import csv
import json
import argparse
from collections import defaultdict

from ortak import (OUTPUTS, SONUC_KLASORU, ESIK_DOSYASI, SINIFLAR, MODEL_KARTI_ESIKLERI,
                   test_seti_yukle, iou, yol)

IOU_ESIGI = 0.5
TARAMA = [round(0.05 * i, 2) for i in range(1, 13)]          # 0.05, 0.10, ..., 0.60
BOYUT_ARALIKLARI = [(0, 16), (16, 32), (32, 64), (64, 128), (128, 10 ** 6)]
SENARYO_ADLARI = {
    "S1": "Yakın plan, tek kişi", "S2": "Kalabalık, küçük yüzler", "S3": "Profil / eğik açı",
    "S4": "Gece / düşük ışık", "S5": "Kısmen kapanmış yüz", "S6": "Uzaktaki / eğik plaka",
    "S7": "Türk plakası", "S8": "Yüz ve plaka birlikte", "S9": "Yüz veya plaka yok",
}


# ---------------- Temel hesaplar ----------------

def degerlendirilen_siniflar(gercek):
    """WIDER FACE'te plaka etiketi yok -> yalnızca yüz değerlendirilir."""
    return ("yuz",) if gercek["kaynak"] == "wider_face" else SINIFLAR


def eslestir(gercek_kutular, tahminler, iou_esigi=IOU_ESIGI):
    """Tek görüntü + tek sınıf için açgözlü (greedy) eşleştirme.
    tahminler: [{"kutu": [...], "guven": ...}, ...]
    Döndürür: tp (tahmin_no, gercek_no) listesi, fp tahmin_no listesi, fn gercek_no listesi."""
    sira = sorted(range(len(tahminler)), key=lambda i: -tahminler[i]["guven"])
    kullanildi = [False] * len(gercek_kutular)
    tp, fp = [], []
    for i in sira:
        en_iyi, en_iyi_iou = -1, iou_esigi
        for j, g in enumerate(gercek_kutular):
            if kullanildi[j]:
                continue
            o = iou(tahminler[i]["kutu"], g)
            if o >= en_iyi_iou:
                en_iyi, en_iyi_iou = j, o
        if en_iyi >= 0:
            kullanildi[en_iyi] = True
            tp.append((i, en_iyi))
        else:
            fp.append(i)
    fn = [j for j, k in enumerate(kullanildi) if not k]
    return tp, fp, fn


def olaylar(gercekler, kayitlar, esikler):
    """Her gerçek nesne ve her yanlış tespit için bir 'olay' kaydı üretir.
    Bütün tablolar bu olay listesinden hesaplanır."""
    gt_olaylari, fp_olaylari = [], []
    for k in kayitlar:
        g = gercekler.get(k["goruntu"])
        if g is None:
            continue
        for sinif in degerlendirilen_siniflar(g):
            gercek_kutular = [n["kutu"] for n in g["nesneler"] if n["sinif"] == sinif]
            tahminler = [t for t in k["tespitler"]
                         if t["sinif"] == sinif and t["guven"] >= esikler[sinif]]
            tp, fp, fn = eslestir(gercek_kutular, tahminler)
            bulunan = {j for _, j in tp}
            for j, kutu in enumerate(gercek_kutular):
                gt_olaylari.append({"goruntu": k["goruntu"], "senaryo": k["senaryo"], "sinif": sinif,
                                    "kutu": kutu, "genislik": kutu[2] - kutu[0], "bulundu": j in bulunan})
            for i in fp:
                fp_olaylari.append({"goruntu": k["goruntu"], "senaryo": k["senaryo"], "sinif": sinif,
                                    "kutu": tahminler[i]["kutu"], "guven": tahminler[i]["guven"]})
    return gt_olaylari, fp_olaylari


def metrik(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else 0.0
    f2 = 5 * p * r / (4 * p + r) if p and r else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "P": p, "R": r, "F1": f1, "F2": f2}


def ozetle(gt_olaylari, fp_olaylari, sinif, senaryo=None):
    gt = [o for o in gt_olaylari if o["sinif"] == sinif and (senaryo is None or o["senaryo"] == senaryo)]
    fp = sum(1 for o in fp_olaylari if o["sinif"] == sinif and (senaryo is None or o["senaryo"] == senaryo))
    tp = sum(o["bulundu"] for o in gt)
    return metrik(tp, fp, len(gt) - tp)


def sizintisiz_oran(gt_olaylari, senaryo=None):
    """Gizlilik açısından en anlaşılır ölçüt: içindeki TÜM yüz/plakalar bulunan görüntülerin oranı."""
    goruntu_tamam = defaultdict(lambda: True)
    for o in gt_olaylari:
        if senaryo is None or o["senaryo"] == senaryo:
            goruntu_tamam[o["goruntu"]] &= o["bulundu"]
    if not goruntu_tamam:
        return None
    return sum(goruntu_tamam.values()) / len(goruntu_tamam)


def esik_taramasi(gercekler, kayitlar):
    """Her sınıf için ayrı ayrı: eşik -> P, R, F1, F2."""
    satirlar = []
    for esik in sorted(set(TARAMA) | set(MODEL_KARTI_ESIKLERI.values())):
        gt, fp = olaylar(gercekler, kayitlar, {s: esik for s in SINIFLAR})
        for sinif in SINIFLAR:
            satirlar.append({"esik": esik, "sinif": sinif, **ozetle(gt, fp, sinif)})
    return satirlar


def esik_sec(tarama):
    """Her sınıf için F2'yi en büyük yapan eşik (eşitlikte düşük eşik -> recall lehine)."""
    secilen = {}
    for sinif in SINIFLAR:
        adaylar = [s for s in tarama if s["sinif"] == sinif]
        secilen[sinif] = max(adaylar, key=lambda s: (round(s["F2"], 4), -s["esik"]))["esik"]
    return secilen


# ---------------- Çıktılar ----------------

def yuzde(x):
    return "–" if x is None else f"{100 * x:.1f}".replace(".", ",")


def ondalik(x):
    return "–" if x is None else f"{x:.3f}".replace(".", ",")


def tablo_md(basliklar, satirlar):
    cizgi = "| " + " | ".join(basliklar) + " |\n|" + "---|" * len(basliklar) + "\n"
    return cizgi + "".join("| " + " | ".join(str(h) for h in s) + " |\n" for s in satirlar)


def csv_yaz(ad, satirlar):
    if not satirlar:
        return
    with open(os.path.join(SONUC_KLASORU, ad), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()))
        w.writeheader()
        w.writerows(satirlar)


# Grafik renkleri: doğrulanmış kategorik paletin ilk iki sırası (yüz = mavi, plaka = turuncu)
RENK = {"yuz": "#2a78d6", "plaka": "#eb6834"}
ETIKET = {"yuz": "Yüz", "plaka": "Plaka"}


def _eksen_sade(ax):
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    ax.spines["left"].set_color("#b5b4ae")
    ax.spines["bottom"].set_color("#b5b4ae")
    ax.tick_params(colors="#52514e", labelsize=9)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)


def grafik_esik(tarama, secilen, mod):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, eksenler = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, sinif in zip(eksenler, SINIFLAR):
        s = sorted([t for t in tarama if t["sinif"] == sinif], key=lambda t: t["esik"])
        x = [t["esik"] for t in s]
        ax.plot(x, [t["R"] or 0 for t in s], color=RENK[sinif], lw=2, marker="o", ms=4, label="Recall")
        ax.plot(x, [t["P"] or 0 for t in s], color=RENK[sinif], lw=2, ls="--", label="Precision")
        ax.axvline(secilen[sinif], color="#52514e", lw=1, ls=":")
        ax.text(secilen[sinif] + 0.01, 0.04, f"seçilen {secilen[sinif]:.2f}", fontsize=8, color="#52514e")
        ax.set_title(ETIKET[sinif], fontsize=10, color="#0b0b0b")
        ax.set_xlabel("Güven eşiği", fontsize=9, color="#52514e")
        ax.set_ylim(0, 1.02)
        _eksen_sade(ax)
        ax.legend(frameon=False, fontsize=8, loc="best")
    fig.suptitle(f"Güven eşiğine göre precision ve recall ({mod} mod)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(SONUC_KLASORU, "esik_taramasi.png"), dpi=200)
    plt.close(fig)


def grafik_senaryo(senaryo_satirlari):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    senaryolar = sorted({s["senaryo"] for s in senaryo_satirlari if s["R"] is not None})
    fig, ax = plt.subplots(figsize=(8, 3.4))
    w = 0.38
    for k, sinif in enumerate(SINIFLAR):
        xs, ys = [], []
        for i, sen in enumerate(senaryolar):
            r = next((s["R"] for s in senaryo_satirlari if s["senaryo"] == sen and s["sinif"] == sinif), None)
            if r is not None:
                xs.append(i + (k - 0.5) * (w + 0.02)); ys.append(r)
        ax.bar(xs, ys, width=w, color=RENK[sinif], label=ETIKET[sinif])
    ax.set_xticks(range(len(senaryolar)), senaryolar)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Recall", fontsize=9, color="#52514e")
    _eksen_sade(ax)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper right", bbox_to_anchor=(1, 1.12))
    ax.set_title("Senaryolara göre recall", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(SONUC_KLASORU, "senaryo_recall.png"), dpi=200)
    plt.close(fig)


def grafik_boyut(boyut_satirlari):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    for sinif in SINIFLAR:
        s = [b for b in boyut_satirlari if b["sinif"] == sinif and b["adet"] > 0]
        ax.plot([b["aralik"] for b in s], [b["recall"] for b in s], color=RENK[sinif],
                lw=2, marker="o", ms=5, label=ETIKET[sinif])
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Nesne genişliği (piksel)", fontsize=9, color="#52514e")
    ax.set_ylabel("Recall", fontsize=9, color="#52514e")
    _eksen_sade(ax)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("Nesne boyutuna göre recall", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(SONUC_KLASORU, "boyut_recall.png"), dpi=200)
    plt.close(fig)


def hata_gorselleri(gt_olaylari, fp_olaylari, sayi=12):
    """En çok nesne kaçırılan görüntüleri çizer. Kırmızı: kaçırılan (FN), mavi: yanlış tespit (FP),
    yeşil: doğru tespit edilen gerçek nesne."""
    import cv2
    hedef = os.path.join(OUTPUTS, "hata_ornekleri")
    os.makedirs(hedef, exist_ok=True)
    fn_sayisi = defaultdict(int)
    for o in gt_olaylari:
        if not o["bulundu"]:
            fn_sayisi[o["goruntu"]] += 1
    fp_sayisi = defaultdict(int)
    for o in fp_olaylari:
        fp_sayisi[o["goruntu"]] += 1
    secilen = sorted(fn_sayisi, key=lambda g: -fn_sayisi[g])[:sayi]
    secilen += [g for g in sorted(fp_sayisi, key=lambda g: -fp_sayisi[g]) if g not in secilen][:sayi // 3]
    for g in secilen:
        img = cv2.imread(yol(g))
        if img is None:
            continue
        for o in gt_olaylari:
            if o["goruntu"] == g:
                x1, y1, x2, y2 = o["kutu"]
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 200, 0) if o["bulundu"] else (0, 0, 255), 2)
        for o in fp_olaylari:
            if o["goruntu"] == g:
                x1, y1, x2, y2 = o["kutu"]
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 120, 0), 2)
        sen = next(o["senaryo"] for o in gt_olaylari + fp_olaylari if o["goruntu"] == g)
        ad = f"{sen}_FN{fn_sayisi[g]}_FP{fp_sayisi[g]}_{os.path.basename(g).rsplit('.', 1)[0]}.jpg"
        cv2.imwrite(os.path.join(hedef, ad), img)
    print(f"Hata görselleri: {os.path.relpath(hedef)}/ ({len(secilen)} görüntü)")


# ---------------- Ana akış ----------------

def mod_degerlendir(gercekler, kayitlar):
    tarama = esik_taramasi(gercekler, kayitlar)
    secilen = esik_sec(tarama)
    gt, fp = olaylar(gercekler, kayitlar, secilen)
    sinif_sonuc = {s: ozetle(gt, fp, s) for s in SINIFLAR}
    ortalama_f2 = sum(sinif_sonuc[s]["F2"] for s in SINIFLAR) / len(SINIFLAR)
    sure = sum(k["sure_ms"] for k in kayitlar) / max(1, len(kayitlar))
    return {"kayitlar": kayitlar, "tarama": tarama, "secilen": secilen, "gt": gt, "fp": fp,
            "sinif_sonuc": sinif_sonuc, "ortalama_f2": ortalama_f2, "sure_ms": sure}


def main(hata_gorseli=True):
    os.makedirs(SONUC_KLASORU, exist_ok=True)
    gercekler = {g["goruntu"]: g for g in test_seti_yukle()}

    modlar = {}
    for mod in ("tam", "parcali"):
        dosya = os.path.join(OUTPUTS, f"tespitler_{mod}.json")
        if os.path.exists(dosya):
            with open(dosya, encoding="utf-8") as f:
                modlar[mod] = mod_degerlendir(gercekler, json.load(f)["kayitlar"])
    if not modlar:
        raise SystemExit("Tespit dosyası yok. Önce: python src/toplu_tespit.py")

    en_iyi = max(modlar, key=lambda m: modlar[m]["ortalama_f2"])
    S = modlar[en_iyi]
    md = [f"# 5. Hafta Değerlendirme Sonuçları\n",
          f"Test seti: {len(gercekler)} görüntü. Eşleştirme ölçütü: IoU ≥ {IOU_ESIGI}. "
          f"Eşik seçimi: her sınıf için F2 skorunu en yüksek yapan eşik.\n"]

    # 1) Mod karşılaştırması
    satirlar = []
    for mod, M in modlar.items():
        for esik_adi, esikler in (("model kartı", MODEL_KARTI_ESIKLERI), ("F2 ile seçilen", M["secilen"])):
            if esik_adi == "model kartı":
                gt, fp = olaylar(gercekler, M["kayitlar"], esikler)
                sonuc = {s: ozetle(gt, fp, s) for s in SINIFLAR}
            else:
                gt, sonuc = M["gt"], M["sinif_sonuc"]
            for sinif in SINIFLAR:
                r = sonuc[sinif]
                satirlar.append([mod, esik_adi, ETIKET[sinif], f"{esikler[sinif]:.3f}".rstrip("0").replace(".", ","), ondalik(r["P"]),
                                 ondalik(r["R"]), ondalik(r["F2"]), yuzde(sizintisiz_oran(gt)),
                                 f"{M['sure_ms']:.0f}"])
    md.append("## 1. Tespit modu ve eşik karşılaştırması\n")
    md.append(tablo_md(["Mod", "Eşik", "Sınıf", "Eşik değeri", "Precision", "Recall", "F2",
                        "Sızıntısız görüntü %", "ms/görüntü"], satirlar))
    md.append(f"\n**Seçilen mod: {en_iyi}** (ortalama F2 = {S['ortalama_f2']:.3f}). "
              f"Seçilen eşikler: yüz = {S['secilen']['yuz']:.2f}, plaka = {S['secilen']['plaka']:.2f}.\n")

    # 2) Eşik taraması
    csv_yaz("esik_taramasi.csv", [{**t, "mod": en_iyi} for t in S["tarama"]])
    grafik_esik(S["tarama"], S["secilen"], en_iyi)
    md.append("\n## 2. Eşik taraması\n")
    md.append(tablo_md(["Eşik", "Sınıf", "TP", "FP", "FN", "Precision", "Recall", "F2"],
                       [[f"{t['esik']:.3f}".rstrip("0").replace(".", ","), ETIKET[t["sinif"]], t["TP"], t["FP"], t["FN"],
                         ondalik(t["P"]), ondalik(t["R"]), ondalik(t["F2"])]
                        for t in sorted(S["tarama"], key=lambda t: (t["sinif"] != "yuz", t["esik"]))]))
    md.append("\n![Eşik taraması](esik_taramasi.png)\n")

    # 3) Senaryo bazında
    sen_satirlari = []
    for sen in sorted({g["senaryo"] for g in gercekler.values()}):
        goruntu_sayisi = sum(1 for g in gercekler.values() if g["senaryo"] == sen)
        for sinif in SINIFLAR:
            r = ozetle(S["gt"], S["fp"], sinif, sen)
            if r["TP"] + r["FP"] + r["FN"] == 0:
                continue
            sen_satirlari.append({"senaryo": sen, "aciklama": SENARYO_ADLARI.get(sen, ""), "sinif": sinif,
                                  "goruntu": goruntu_sayisi, "gercek_nesne": r["TP"] + r["FN"], **r,
                                  "sizintisiz": sizintisiz_oran([o for o in S["gt"] if o["sinif"] == sinif], sen),
                                  "fp_goruntu_basina": r["FP"] / goruntu_sayisi})
    csv_yaz("senaryo_sonuclari.csv", sen_satirlari)
    grafik_senaryo(sen_satirlari)
    md.append(f"\n## 3. Senaryo bazında sonuçlar ({en_iyi} mod, seçilen eşikler)\n")
    md.append(tablo_md(["Senaryo", "Açıklama", "Sınıf", "Gerçek nesne", "TP", "FP", "FN",
                        "Precision", "Recall", "Sızıntısız görüntü %", "FP / görüntü"],
                       [[s["senaryo"], s["aciklama"], ETIKET[s["sinif"]], s["gercek_nesne"], s["TP"], s["FP"],
                         s["FN"], ondalik(s["P"]), ondalik(s["R"]), yuzde(s["sizintisiz"]),
                         f"{s['fp_goruntu_basina']:.2f}".replace(".", ",")] for s in sen_satirlari]))
    md.append("\n![Senaryolara göre recall](senaryo_recall.png)\n")
    md.append("\nNot: WIDER FACE görüntülerinde (S1-S5) plakalar etiketli olmadığı için yalnızca yüz "
              "değerlendirilmiştir. S9'da gerçek nesne olmadığından yalnızca FP sayısı anlamlıdır.\n")

    # 4) Boyuta göre recall (hata analizi)
    boyut_satirlari = []
    for sinif in SINIFLAR:
        for alt, ust in BOYUT_ARALIKLARI:
            secim = [o for o in S["gt"] if o["sinif"] == sinif and alt <= o["genislik"] < ust]
            boyut_satirlari.append({"sinif": sinif, "aralik": f"{alt}-{ust}" if ust < 10 ** 6 else f"≥{alt}",
                                    "adet": len(secim),
                                    "recall": sum(o["bulundu"] for o in secim) / len(secim) if secim else None})
    csv_yaz("boyut_analizi.csv", boyut_satirlari)
    grafik_boyut(boyut_satirlari)
    md.append("\n## 4. Nesne boyutuna göre recall (hata analizi)\n")
    md.append(tablo_md(["Sınıf", "Genişlik (px)", "Nesne sayısı", "Recall"],
                       [[ETIKET[b["sinif"]], b["aralik"], b["adet"], ondalik(b["recall"])]
                        for b in boyut_satirlari]))
    md.append("\n![Boyuta göre recall](boyut_recall.png)\n")

    # 5) Otomatik gözlemler (rapora yazarken başlangıç noktası, kontrol edilmeli)
    md.append("\n## 5. Otomatik gözlemler\n")
    for sinif in SINIFLAR:
        s = [x for x in sen_satirlari if x["sinif"] == sinif and x["R"] is not None]
        if s:
            kotu, iyi = min(s, key=lambda x: x["R"]), max(s, key=lambda x: x["R"])
            md.append(f"- {ETIKET[sinif]}: en düşük recall {kotu['senaryo']} ({kotu['aciklama']}, "
                      f"{ondalik(kotu['R'])}), en yüksek {iyi['senaryo']} ({ondalik(iyi['R'])}).\n")
        kucuk = [b for b in boyut_satirlari if b["sinif"] == sinif and b["recall"] is not None]
        if kucuk:
            md.append(f"- {ETIKET[sinif]}: en küçük boyut grubunda ({kucuk[0]['aralik']} px) recall "
                      f"{ondalik(kucuk[0]['recall'])}, en büyük grupta ({kucuk[-1]['aralik']} px) "
                      f"{ondalik(kucuk[-1]['recall'])}.\n")
    if len(modlar) == 2:
        for sinif in SINIFLAR:
            a, b = modlar["tam"]["sinif_sonuc"][sinif], modlar["parcali"]["sinif_sonuc"][sinif]
            md.append(f"- {ETIKET[sinif]}: parçalı mod recall'u {ondalik(a['R'])} → {ondalik(b['R'])} "
                      f"olarak değiştirdi (tam → parçalı).\n")
        md.append(f"- Süre: tam {modlar['tam']['sure_ms']:.0f} ms, parçalı "
                  f"{modlar['parcali']['sure_ms']:.0f} ms / görüntü.\n")

    with open(os.path.join(SONUC_KLASORU, "ozet.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(ESIK_DOSYASI, "w", encoding="utf-8") as f:
        json.dump({"mod": en_iyi, "olcut": "F2", "secilen": S["secilen"]}, f, ensure_ascii=False, indent=1)

    print("\n".join(md))
    print(f"\nKaydedildi: {os.path.relpath(SONUC_KLASORU)}/ (ozet.md, csv, png, esikler.json)")
    if hata_gorseli:
        hata_gorselleri(S["gt"], S["fp"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gorselsiz", action="store_true", help="hata görsellerini çizme")
    main(not ap.parse_args().gorselsiz)
