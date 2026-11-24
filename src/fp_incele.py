"""
Yanlış pozitiflerin gözle incelenmesi - Ceren KILIÇ (6. hafta planı, İP14)

5. haftada S9 ("yüz veya plaka yok") görüntülerinde 31 yanlış plaka ve 4 yanlış yüz
tespiti çıktı. Ama S9 görüntüleri, PP4AV'de HİÇ etiket olmayan görüntülerden seçildi;
yani veri setinde gözden kaçmış, uzakta kalmış GERÇEK bir plaka da "yanlış" sayılmış
olabilir. Bu araç her yanlış tespiti tek tek gösterir, siz de karar verirsiniz:

    g : gerçekten yüz/plaka var (etiket eksik, model haklı)
    h : model hatası (orada yüz/plaka yok)
    b : belirsiz (karar verilemiyor: çok küçük, bulanık vb.)
    z : önceki tespite dön        q : kaydet ve çık

Etiketleme sırasında tespitin GÜVEN DEĞERİ gösterilmez: yüksek güven görmek, kişiyi
"herhalde doğrudur" demeye iter (etiketle.py'deki gibi önyargıyı önlemek için).

Çalıştırma (proje ana klasöründeyken, önce toplu_tespit.py çalışmış olmalı):
    python src/fp_incele.py                      # S9'daki yanlış tespitleri incele
    python src/fp_incele.py --senaryo S6 S8      # başka senaryolar da incelenebilir
    python src/fp_incele.py --ozet               # kararların özetini çıkar
    python src/fp_incele.py --terminal           # pencere tuşlara tepki vermiyorsa (ör. macOS + conda):
                                                 # kesitler Önizleme'de açılır, kararlar terminale yazılır

Çıktılar:
    docs/sonuclar/fp_kararlar.json   -> verilen kararlar (görüntü yolu + kutu; kişisel veri yok, GitHub'a gider)
    docs/sonuclar/fp_inceleme.md     -> özet tablo
    outputs/fp_inceleme/*.jpg        -> incelenen kesitlerin toplu görünümü (görüntü içerir, GitHub'a gitmez)
"""

import os
import json
import argparse
from collections import Counter

from ortak import OUTPUTS, SONUC_KLASORU, test_seti_yukle, esikleri_yukle, yol
import degerlendir as D

KARAR_DOSYASI = os.path.join(SONUC_KLASORU, "fp_kararlar.json")
KARARLAR = {"g": "gercek", "h": "hata", "b": "belirsiz"}
KARAR_ADI = {"gercek": "Gerçek nesne (etiket eksik)", "hata": "Model hatası", "belirsiz": "Belirsiz"}
ETIKET = {"yuz": "Yüz", "plaka": "Plaka"}
EKRAN = 640          # kesit bu boyuta büyütülerek gösterilir


def anahtar(o):
    """Bir yanlış tespiti tekil olarak tanımlar (görüntü + sınıf + kutu)."""
    return f'{o["goruntu"]}|{o["sinif"]}|{",".join(map(str, o["kutu"]))}'


def kararlari_oku():
    if os.path.exists(KARAR_DOSYASI):
        with open(KARAR_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    return {}


def kararlari_yaz(kararlar):
    os.makedirs(SONUC_KLASORU, exist_ok=True)
    with open(KARAR_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(kararlar, f, ensure_ascii=False, indent=1, sort_keys=True)


def yanlis_tespitler(senaryolar):
    """5. haftanın seçtiği ayarlarla (mod + eşik) belirtilen senaryolardaki FP olaylarını döndürür."""
    esik_bilgisi = {}
    if os.path.exists(os.path.join(SONUC_KLASORU, "esikler.json")):
        with open(os.path.join(SONUC_KLASORU, "esikler.json"), encoding="utf-8") as f:
            esik_bilgisi = json.load(f)
    mod = esik_bilgisi.get("mod", "parcali")
    dosya = os.path.join(OUTPUTS, f"tespitler_{mod}.json")
    if not os.path.exists(dosya):
        raise SystemExit(f"{os.path.relpath(dosya)} yok. Önce: python src/toplu_tespit.py --mod {mod}")
    with open(dosya, encoding="utf-8") as f:
        kayitlar = json.load(f)["kayitlar"]
    gercekler = {g["goruntu"]: g for g in test_seti_yukle()}
    _, fp = D.olaylar(gercekler, kayitlar, esikleri_yukle())
    fp = [o for o in fp if o["senaryo"] in senaryolar]
    return sorted(fp, key=lambda o: (o["senaryo"], o["sinif"], o["goruntu"], o["kutu"])), mod


def kesit(img, kutu, cerceve=True):
    """Kutuyu bağlamıyla birlikte (kutunun 4 katı, en az 160 px) keser ve EKRAN boyutuna büyütür."""
    import cv2
    Y, G = img.shape[:2]
    x1, y1, x2, y2 = kutu
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    yari = max(80, 2 * max(x2 - x1, y2 - y1))
    a1, b1 = int(max(0, cx - yari)), int(max(0, cy - yari))
    a2, b2 = int(min(G, cx + yari)), int(min(Y, cy + yari))
    parca = img[b1:b2, a1:a2].copy()
    olcek = EKRAN / max(parca.shape[:2])
    parca = cv2.resize(parca, None, fx=olcek, fy=olcek, interpolation=cv2.INTER_CUBIC)
    if cerceve:
        p1 = (int((x1 - a1) * olcek) - 3, int((y1 - b1) * olcek) - 3)
        p2 = (int((x2 - a1) * olcek) + 3, int((y2 - b1) * olcek) + 3)
        cv2.rectangle(parca, p1, p2, (255, 120, 0), 2)
    return parca


def incele(fp, kararlar):
    import cv2
    if not fp:
        print("İncelenecek yanlış tespit yok.")
        return
    # Kaldığı yerden devam: ilk kararsız tespitten başla
    i = next((k for k, o in enumerate(fp) if anahtar(o) not in kararlar), len(fp))
    if i == len(fp):
        print("Hepsi zaten incelenmiş. Baştan gözden geçiriliyor (q ile çıkabilirsiniz).")
        i = 0
    cv2.namedWindow("fp_incele")
    onbellek = {}
    while 0 <= i < len(fp):
        o = fp[i]
        if o["goruntu"] not in onbellek:
            onbellek = {o["goruntu"]: cv2.imread(yol(o["goruntu"]))}
        img = onbellek[o["goruntu"]]
        if img is None:
            print(f"  ! Okunamadı: {o['goruntu']}")
            i += 1
            continue
        ekran = kesit(img, o["kutu"])
        ekran = cv2.copyMakeBorder(ekran, 70, 0, 0, max(0, 640 - ekran.shape[1]), cv2.BORDER_CONSTANT, value=(30, 30, 30))
        onceki = kararlar.get(anahtar(o))
        w = o["kutu"][2] - o["kutu"][0]
        cv2.putText(ekran, f"{i + 1}/{len(fp)}  {o['senaryo']}  {ETIKET[o['sinif']]}  genislik {w}px",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(ekran, f"g: gercek  h: hata  b: belirsiz  z: geri  q: cik   [{onceki or '-'}]",
                    (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.imshow("fp_incele", ekran)
        tus = cv2.waitKey(0) & 0xFF
        if chr(tus) in KARARLAR:
            kararlar[anahtar(o)] = KARARLAR[chr(tus)]
            kararlari_yaz(kararlar)
            i += 1
        elif tus == ord("z"):
            i = max(0, i - 1)
        elif tus == ord("q"):
            break
    cv2.destroyAllWindows()
    kararlari_yaz(kararlar)
    print(f"{sum(anahtar(o) in kararlar for o in fp)}/{len(fp)} tespit için karar kaydedildi: "
          f"{os.path.relpath(KARAR_DOSYASI)}")


def incele_terminal(fp, kararlar):
    """Pencereye klavye odağı verilemeyen sistemler için: kesitler numaralı dosyalar olarak
    kaydedilip Önizleme'de (macOS) açılır, karar terminale yazılıp Enter'a basılır."""
    import sys
    import cv2
    import subprocess
    if not fp:
        print("İncelenecek yanlış tespit yok.")
        return
    klasor = os.path.join(OUTPUTS, "fp_inceleme", "kesitler")
    os.makedirs(klasor, exist_ok=True)
    for f in os.listdir(klasor):
        os.remove(os.path.join(klasor, f))
    dosyalar, onbellek = [], {}
    for i, o in enumerate(fp, 1):
        if o["goruntu"] not in onbellek:
            onbellek = {o["goruntu"]: cv2.imread(yol(o["goruntu"]))}
        img = onbellek[o["goruntu"]]
        if img is None:
            dosyalar.append(None)
            continue
        ekran = cv2.copyMakeBorder(kesit(img, o["kutu"]), 50, 0, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
        cv2.putText(ekran, f"{i}/{len(fp)}  {o['senaryo']}  {ETIKET[o['sinif']]}  genislik {o['kutu'][2] - o['kutu'][0]}px",
                    (10, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        ad = os.path.join(klasor, f"{i:02d}.jpg")
        cv2.imwrite(ad, ekran)
        dosyalar.append(ad)
    print(f"{len(fp)} kesit kaydedildi: {os.path.relpath(klasor)}/")
    if sys.platform == "darwin":
        subprocess.run(["open", "-a", "Preview"] + [d for d in dosyalar if d])
        print("Önizleme'de açıldı. Önizleme'de ok tuşlarıyla resimler arasında gezebilirsiniz.")
    print("Her resim için terminale g (gerçek), h (hata), b (belirsiz) yazıp Enter'a basın. "
          "z: geri, q: çık\n")
    i = next((k for k, o in enumerate(fp) if anahtar(o) not in kararlar), 0)
    while 0 <= i < len(fp):
        o = fp[i]
        onceki = kararlar.get(anahtar(o), "-")
        try:
            cevap = input(f"  Resim {i + 1:02d}/{len(fp)} ({ETIKET[o['sinif']]}) [{onceki}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if cevap in KARARLAR:
            kararlar[anahtar(o)] = KARARLAR[cevap]
            kararlari_yaz(kararlar)
            i += 1
        elif cevap == "z":
            i = max(0, i - 1)
        elif cevap == "q":
            break
        else:
            print("    Sadece g, h, b, z veya q yazın.")
    kararlari_yaz(kararlar)
    print(f"\n{sum(anahtar(o) in kararlar for o in fp)}/{len(fp)} tespit için karar kaydedildi.")


def ozet_hesapla(fp, kararlar):
    """Senaryo + sınıf bazında karar sayıları. Kararsız olanlar 'incelenmedi' sayılır."""
    tablo = {}
    for o in fp:
        k = (o["senaryo"], o["sinif"])
        tablo.setdefault(k, Counter())[kararlar.get(anahtar(o), "incelenmedi")] += 1
    return tablo


def ozet(fp, kararlar, mod):
    import cv2
    import numpy as np
    tablo = ozet_hesapla(fp, kararlar)
    satirlar, md = [], []
    for (sen, sinif), c in sorted(tablo.items()):
        toplam = sum(c.values())
        satirlar.append([sen, ETIKET[sinif], toplam, c["gercek"], c["hata"], c["belirsiz"], c["incelenmedi"]])
    md.append("# Yanlış pozitiflerin gözle incelenmesi\n")
    esik_metni = ", ".join(f"{ETIKET[s].lower()} {e:.2f}".replace(".", ",") for s, e in esikleri_yukle().items())
    md.append(f"Tespit modu: {mod}, eşikler: {esik_metni}. Her yanlış tespit, güven değeri "
              f"gösterilmeden tek tek incelenmiştir.\n")
    md.append(D.tablo_md(["Senaryo", "Sınıf", "Yanlış tespit", KARAR_ADI["gercek"], KARAR_ADI["hata"],
                          KARAR_ADI["belirsiz"], "İncelenmedi"], satirlar))
    gercek = sum(c["gercek"] for c in tablo.values())
    hata = sum(c["hata"] for c in tablo.values())
    if gercek + hata:
        md.append(f"\nKesin karar verilen {gercek + hata} tespitin {gercek} tanesi (%{100 * gercek / (gercek + hata):.0f}) "
                  f"aslında etiketlenmemiş gerçek nesnedir.")
        if gercek:
            md.append(" Bu tespitler modelin değil veri setinin hatasıdır; yani raporlanan precision değeri, "
                      "modelin gerçek başarısını bir miktar düşük göstermektedir.")
        md.append("\n")
    with open(os.path.join(SONUC_KLASORU, "fp_inceleme.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("\n".join(md))

    # Rapor için toplu görünüm: her karar türünden kesitler yan yana (GitHub'a gitmez)
    hedef = os.path.join(OUTPUTS, "fp_inceleme")
    os.makedirs(hedef, exist_ok=True)
    for karar in ("gercek", "hata", "belirsiz"):
        secim = [o for o in fp if kararlar.get(anahtar(o)) == karar][:12]
        if not secim:
            continue
        kucukler = []
        for o in secim:
            img = cv2.imread(yol(o["goruntu"]))
            if img is not None:
                kucukler.append(cv2.resize(kesit(img, o["kutu"]), (240, 240)))
        while len(kucukler) % 4:
            kucukler.append(np.full((240, 240, 3), 255, np.uint8))
        satir = [np.hstack(kucukler[k:k + 4]) for k in range(0, len(kucukler), 4)]
        cv2.imwrite(os.path.join(hedef, f"{karar}.jpg"), np.vstack(satir))
    print(f"\nKaydedildi: {os.path.relpath(SONUC_KLASORU)}/fp_inceleme.md, {os.path.relpath(hedef)}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--senaryo", nargs="+", default=["S9"])
    ap.add_argument("--ozet", action="store_true", help="kararların özetini çıkar")
    ap.add_argument("--terminal", action="store_true", help="kararları terminale yazarak ver")
    args = ap.parse_args()

    fp, mod = yanlis_tespitler(set(args.senaryo))
    sayilar = Counter((o["senaryo"], o["sinif"]) for o in fp)
    print(f"Mod: {mod} | " + ", ".join(f"{s} {ETIKET[c]}: {n}" for (s, c), n in sorted(sayilar.items())))
    kararlar = kararlari_oku()
    if args.ozet:
        ozet(fp, kararlar, mod)
    elif args.terminal:
        incele_terminal(fp, kararlar)
        print("Özet için: python src/fp_incele.py --ozet")
    else:
        incele(fp, kararlar)
        print("Özet için: python src/fp_incele.py --ozet")
