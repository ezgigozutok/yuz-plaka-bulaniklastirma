"""
Bulanıklaştırma ve anonimleştirme
  İP10: Bulanıklaştırma yönteminin uygulanması
  İP11: Anonimleştirilmiş görüntülerin oluşturulması

Girdi: görüntü (BGR numpy) + ortak formattaki tespitler
Çıktı: yalnızca tespit edilen bölgeleri bulanıklaştırılmış YENİ görüntü (orijinal değişmez)

Neden kutu genişletme? Modelin kutusu yüzün/plakanın kenarını tam kapsamayabilir;
kenarda kalan birkaç piksel (ör. plakanın son karakteri) okunabilir kalırsa anonimleştirme
başarısız olur. Bu yüzden kutu her yönden kutu boyunun %15'i kadar büyütülür.

Neden çekirdek boyu kutuya göre? Sabit bir Gaussian çekirdeği (ör. 15x15) küçük bir
plakayı iyi gizler ama 400 px'lik bir yüzü neredeyse hiç bozmaz. Çekirdek boyu kutunun
kısa kenarına oranlandığında her boyuttaki nesne aynı ölçüde bulanıklaşır.

İki yöntem var:
  gauss  : Gaussian bulanıklaştırma (rapordaki yöntem, OpenCV GaussianBlur)
  piksel : pikselleştirme (mozaik) - karşılaştırma için
"""

import cv2
import numpy as np

GENISLETME = 0.15      # kutuyu her yönden kutu boyunun bu oranı kadar büyüt
CEKIRDEK_ORANI = 0.5   # Gaussian çekirdek boyu = kutunun kısa kenarı x bu oran
PIKSEL_BLOK = 8        # pikselleştirmede kısa kenar boyunca kaç blok kalacağı


def kutu_genislet(kutu, goruntu_boyutu, oran=GENISLETME):
    """Kutuyu büyütür ve görüntü sınırları dışına taşmasını engeller. goruntu_boyutu = (genişlik, yükseklik)"""
    x1, y1, x2, y2 = kutu
    G, Y = goruntu_boyutu
    dx, dy = int((x2 - x1) * oran), int((y2 - y1) * oran)
    return [max(0, x1 - dx), max(0, y1 - dy), min(G, x2 + dx), min(Y, y2 + dy)]


def tek_sayi(n):
    n = max(3, int(n))
    return n if n % 2 == 1 else n + 1


def bolge_bulaniklastir(bolge, yontem="gauss"):
    h, w = bolge.shape[:2]
    if h < 2 or w < 2:
        return bolge
    if yontem == "piksel":
        olcek = max(1, min(h, w) // PIKSEL_BLOK)
        kucuk = cv2.resize(bolge, (max(1, w // olcek), max(1, h // olcek)), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(kucuk, (w, h), interpolation=cv2.INTER_NEAREST)
    k = tek_sayi(min(h, w) * CEKIRDEK_ORANI)
    return cv2.GaussianBlur(bolge, (k, k), 0)


def anonimlestir(goruntu, tespitler, yontem="gauss", genisletme=GENISLETME):
    """Tespit edilen her bölgeyi bulanıklaştırır; görüntünün geri kalanına dokunmaz."""
    cikti = goruntu.copy()
    Y, G = goruntu.shape[:2]
    for t in tespitler:
        x1, y1, x2, y2 = kutu_genislet(t["kutu"], (G, Y), genisletme)
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        cikti[y1:y2, x1:x2] = bolge_bulaniklastir(cikti[y1:y2, x1:x2], yontem)
    return cikti


def keskinlik(bolge):
    """Laplacian varyansı: bölgedeki ayrıntı miktarı. Bulanıklaştırma sonrası belirgin düşmeli.
    Farklı ayarların etkisini sayısal karşılaştırmak için (İP10)."""
    gri = cv2.cvtColor(bolge, cv2.COLOR_BGR2GRAY) if bolge.ndim == 3 else bolge
    return float(cv2.Laplacian(gri, cv2.CV_64F).var())
