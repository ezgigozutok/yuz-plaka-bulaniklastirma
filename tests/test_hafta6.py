"""6. hafta eklemeleri: parametreli parça boyutu, bulanıklaştırma gücü, yanlış pozitif özeti."""
import numpy as np
import tespit as T
import bulaniklastir as B
import fp_incele as F


def test_parca_640_kenari_kaplar():
    konum = T.parca_konumlari(1920, 640)
    assert konum[0] == 0 and konum[-1] == 1920 - 640
    assert all(b - a <= 640 for a, b in zip(konum, konum[1:]))       # parçalar arasında boşluk yok


def test_varsayilan_parca_degismedi():
    assert T.parca_konumlari(1920) == T.parca_konumlari(1920, T.PARCA)


def test_guc_arttikca_daha_bulanik():
    rng = np.random.default_rng(0)
    bolge = rng.integers(0, 255, (80, 80, 3), dtype=np.uint8)
    hafif = B.keskinlik(B.bolge_bulaniklastir(bolge, "gauss", 0.25))
    guclu = B.keskinlik(B.bolge_bulaniklastir(bolge, "gauss", 1.0))
    assert guclu < hafif
    kaba = B.bolge_bulaniklastir(bolge, "piksel", 4)
    assert len(np.unique(kaba.reshape(-1, 3), axis=0)) <= 4 * 4 + 4   # ~4x4 blok


def test_varsayilan_bulaniklastirma_degismedi():
    rng = np.random.default_rng(1)
    bolge = rng.integers(0, 255, (60, 90, 3), dtype=np.uint8)
    for y in ("gauss", "piksel"):
        assert np.array_equal(B.bolge_bulaniklastir(bolge, y), B.bolge_bulaniklastir(bolge, y, None))


def test_fp_ozeti():
    fp = [{"goruntu": "a.png", "senaryo": "S9", "sinif": "plaka", "kutu": [1, 2, 3, 4]},
          {"goruntu": "a.png", "senaryo": "S9", "sinif": "plaka", "kutu": [5, 6, 7, 8]},
          {"goruntu": "b.png", "senaryo": "S9", "sinif": "yuz", "kutu": [1, 1, 9, 9]}]
    kararlar = {F.anahtar(fp[0]): "gercek", F.anahtar(fp[1]): "hata"}
    tablo = F.ozet_hesapla(fp, kararlar)
    assert tablo[("S9", "plaka")] == {"gercek": 1, "hata": 1}
    assert tablo[("S9", "yuz")] == {"incelenmedi": 1}


def test_genis_plaka_da_bulaniklasir():
    """Hata düzeltmesi: geniş ve alçak bölgelerde (plaka) güç kısa kenara göre seçildiği için
    yazı okunur kalıyor, pikselleştirme hiçbir şey değiştirmiyordu."""
    import cv2
    img = np.full((120, 300, 3), 70, np.uint8)
    cv2.rectangle(img, (100, 50), (210, 74), (0, 210, 240), -1)
    cv2.putText(img, "RK-131-F", (102, 71), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    kutu = [100, 50, 210, 74]
    once = B.keskinlik(img[50:74, 100:210])
    for yontem in ("gauss", "piksel"):
        sonuc = B.anonimlestir(img, [{"sinif": "plaka", "kutu": kutu, "guven": 0.9}], yontem)
        assert not np.array_equal(sonuc[50:74, 100:210], img[50:74, 100:210])
        if yontem == "gauss":
            assert B.keskinlik(sonuc[50:74, 100:210]) < 0.05 * once
