"""Değerlendirme hesaplarının doğruluğu - elle hesaplanabilen küçük örneklerle."""
import json
import degerlendir as D
from ortak import iou


def test_iou():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
    assert abs(iou([0, 0, 10, 10], [5, 0, 15, 10]) - 50 / 150) < 1e-9


def test_eslestir_tp_fp_fn():
    gercek = [[0, 0, 10, 10], [100, 100, 120, 120]]
    tahmin = [{"kutu": [1, 1, 10, 10], "guven": 0.9},      # 1. gerçeğe oturur -> TP
              {"kutu": [0, 0, 10, 10], "guven": 0.5},      # aynı nesneye ikinci kutu -> FP
              {"kutu": [300, 300, 310, 310], "guven": 0.8}]  # boşluk -> FP
    tp, fp, fn = D.eslestir(gercek, tahmin)
    assert tp == [(0, 0)] and sorted(fp) == [1, 2] and fn == [1]


def test_metrik():
    m = D.metrik(8, 2, 2)
    assert abs(m["P"] - 0.8) < 1e-9 and abs(m["R"] - 0.8) < 1e-9 and abs(m["F2"] - 0.8) < 1e-9
    assert D.metrik(0, 0, 0)["P"] is None


def _ornek():
    gercekler = {
        "w.jpg": {"goruntu": "w.jpg", "kaynak": "wider_face", "senaryo": "S1",
                  "nesneler": [{"sinif": "yuz", "kutu": [0, 0, 50, 50]}]},
        "p.png": {"goruntu": "p.png", "kaynak": "pp4av", "senaryo": "S8",
                  "nesneler": [{"sinif": "yuz", "kutu": [0, 0, 20, 20]},
                               {"sinif": "plaka", "kutu": [100, 100, 140, 110]}]},
    }
    kayitlar = [
        {"goruntu": "w.jpg", "senaryo": "S1", "sure_ms": 10, "tespitler": [
            {"sinif": "yuz", "kutu": [0, 0, 50, 50], "guven": 0.9},
            {"sinif": "plaka", "kutu": [200, 200, 240, 210], "guven": 0.9}]},   # WIDER'da plaka -> sayılmamalı
        {"goruntu": "p.png", "senaryo": "S8", "sure_ms": 30, "tespitler": [
            {"sinif": "yuz", "kutu": [0, 0, 20, 20], "guven": 0.15},            # düşük güvenli doğru yüz
            {"sinif": "plaka", "kutu": [100, 100, 140, 110], "guven": 0.7},
            {"sinif": "yuz", "kutu": [500, 500, 520, 520], "guven": 0.1}]},     # düşük güvenli yanlış yüz
    ]
    return gercekler, kayitlar


def test_wider_plaka_sayilmaz_ve_esik_etkisi():
    gercekler, kayitlar = _ornek()
    gt, fp = D.olaylar(gercekler, kayitlar, {"yuz": 0.25, "plaka": 0.25})
    assert not any(o["sinif"] == "plaka" and o["goruntu"] == "w.jpg" for o in fp)
    yuz = D.ozetle(gt, fp, "yuz")
    assert (yuz["TP"], yuz["FP"], yuz["FN"]) == (1, 0, 1)        # 0.15'lik yüz eşik altında kaldı
    gt, fp = D.olaylar(gercekler, kayitlar, {"yuz": 0.05, "plaka": 0.25})
    yuz = D.ozetle(gt, fp, "yuz")
    assert (yuz["TP"], yuz["FP"], yuz["FN"]) == (2, 1, 0)
    assert D.sizintisiz_oran(gt) == 1.0


def test_esik_secimi_recall_lehine():
    gercekler, kayitlar = _ornek()
    secilen = D.esik_sec(D.esik_taramasi(gercekler, kayitlar))
    assert secilen["yuz"] <= 0.15                             # F2, düşük güvenli doğru yüzü yakalayan eşiği seçmeli


def test_tum_akis(tmp_path, monkeypatch):
    gercekler, kayitlar = _ornek()
    cikti, sonuc = tmp_path / "outputs", tmp_path / "sonuclar"
    cikti.mkdir()
    for mod in ("tam", "parcali"):
        (cikti / f"tespitler_{mod}.json").write_text(json.dumps({"kayitlar": kayitlar}))
    monkeypatch.setattr(D, "OUTPUTS", str(cikti))
    monkeypatch.setattr(D, "SONUC_KLASORU", str(sonuc))
    monkeypatch.setattr(D, "ESIK_DOSYASI", str(sonuc / "esikler.json"))
    monkeypatch.setattr(D, "test_seti_yukle", lambda: list(gercekler.values()))
    D.main(hata_gorseli=False)
    for dosya in ("ozet.md", "esikler.json", "esik_taramasi.png", "senaryo_recall.png",
                  "boyut_recall.png", "senaryo_sonuclari.csv"):
        assert (sonuc / dosya).exists(), dosya
