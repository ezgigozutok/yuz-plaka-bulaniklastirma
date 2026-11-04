"""Bulanıklaştırma yalnızca kutuların içini değiştirmeli."""
import numpy as np
import bulaniklastir as B


def _desenli(h=200, w=300):
    rng = np.random.default_rng(0)
    return rng.integers(0, 255, (h, w, 3), dtype=np.uint8)


def test_kutu_genislet_sinirda_kalir():
    assert B.kutu_genislet([0, 0, 100, 100], (120, 120), 0.15) == [0, 0, 115, 115]


def test_sadece_kutu_degisir():
    img = _desenli()
    kutu = [100, 50, 160, 110]
    for yontem in ("gauss", "piksel"):
        sonuc = B.anonimlestir(img, [{"sinif": "yuz", "kutu": kutu, "guven": 0.9}], yontem)
        x1, y1, x2, y2 = B.kutu_genislet(kutu, (300, 200))
        maske = np.ones(img.shape[:2], bool)
        maske[y1:y2, x1:x2] = False
        assert np.array_equal(sonuc[maske], img[maske])                       # dışarısı aynı
        assert B.keskinlik(sonuc[y1:y2, x1:x2]) < 0.1 * B.keskinlik(img[y1:y2, x1:x2])   # içerisi bulanık
    assert img is not sonuc


def test_tespit_yoksa_ayni():
    img = _desenli()
    assert np.array_equal(B.anonimlestir(img, []), img)
