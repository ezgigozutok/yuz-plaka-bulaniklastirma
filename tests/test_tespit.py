"""Parçalı tespit: parça koordinatları doğru görüntü koordinatına çevrilmeli, tekrarlar silinmeli.
Gerçek model yerine beyaz dikdörtgenleri 'yüz' olarak bulan sahte bir model kullanılır."""
import numpy as np
import cv2
import tespit as T


class _Dizi:
    def __init__(self, a): self.a = np.asarray(a, dtype=np.float32)
    def cpu(self): return self
    def numpy(self): return self.a


class _Kutular:
    def __init__(self, satirlar):
        a = np.asarray(satirlar, dtype=np.float32).reshape(-1, 6)
        self.xyxy, self.conf, self.cls, self.n = _Dizi(a[:, :4]), _Dizi(a[:, 4]), _Dizi(a[:, 5]), len(a)
    def __len__(self): return self.n


class _Sonuc:
    def __init__(self, satirlar): self.boxes = _Kutular(satirlar)


class SahteModel:
    names = {0: "face", 1: "license-plate"}
    def __init__(self): self.cagri = 0
    def predict(self, goruntuler, **_):
        sonuclar = []
        for g in goruntuler:
            self.cagri += 1
            gri = cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)
            konturlar, _ = cv2.findContours((gri > 200).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            satirlar = []
            for k in konturlar:
                x, y, w, h = cv2.boundingRect(k)
                satirlar.append([x, y, x + w, y + h, 0.9, 0])
            sonuclar.append(_Sonuc(satirlar))
        return sonuclar


def test_parca_konumlari():
    assert T.parca_konumlari(1000) == [0]
    k = T.parca_konumlari(1920)
    assert k[0] == 0 and k[-1] == 1920 - 1280
    k = T.parca_konumlari(4000)
    assert all(b - a <= 1280 for a, b in zip(k, k[1:])) and k[-1] == 4000 - 1280


def test_parcali_koordinat_ve_tekrar():
    img = np.zeros((1080, 1920, 3), np.uint8)
    nesneler = [(50, 50, 90, 90), (900, 500, 960, 560), (1800, 1000, 1850, 1050)]  # ortadaki iki parçada da var
    for x1, y1, x2, y2 in nesneler:
        img[y1:y2, x1:x2] = 255
    model = SahteModel()
    sonuc = T.parcali_tespit_et(model, img)
    assert model.cagri == 3                                  # tam görüntü + 2 parça
    bulunan = sorted(tuple(t["kutu"]) for t in sonuc)
    assert bulunan == sorted(nesneler)
    assert all(t["sinif"] == "yuz" for t in sonuc)


def test_kucuk_goruntude_tek_cagri():
    img = np.zeros((600, 800, 3), np.uint8)
    model = SahteModel()
    T.parcali_tespit_et(model, img)
    assert model.cagri == 1


def test_esik_uygula():
    t = [{"sinif": "yuz", "guven": 0.2}, {"sinif": "plaka", "guven": 0.2}, {"sinif": "plaka", "guven": 0.3}]
    assert len(T.esik_uygula(t, {"yuz": 0.15, "plaka": 0.263})) == 2
