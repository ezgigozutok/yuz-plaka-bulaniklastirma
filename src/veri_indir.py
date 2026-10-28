"""
Test veri setlerini indirir ve açar - Ceren KILIÇ (İP3)

İndirilenler:
  1) PP4AV        -> yüz + plaka etiketli sürüş görüntüleri  (Trinh vd., WACV 2023)
  2) WIDER FACE   -> sadece validation kısmı + yüz etiketleri (Yang vd., CVPR 2016)

Kurulum (bir kere):
    pip install huggingface_hub

Çalıştırma (proje ana klasöründeyken):
    python src/veri_indir.py

Her şey "data/" klasörüne iner. Bu klasör .gitignore'da olduğu için GitHub'a gitmez.
"""

import os
import zipfile
import urllib.request
from huggingface_hub import hf_hub_download, snapshot_download

# Betik nereden çalıştırılırsa çalıştırılsın, proje ana klasöründeki data/ kullanılır
PROJE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERI = os.path.join(PROJE, "data")
PP4AV_KLASOR = os.path.join(VERI, "pp4av")
WIDER_KLASOR = os.path.join(VERI, "wider_face")

WIDER_ETIKET_URL = "http://shuoyang1213.me/WIDERFACE/support/bbx_annotation/wider_face_split.zip"


def zip_ac(zip_yolu, hedef):
    print(f"  Açılıyor: {os.path.basename(zip_yolu)}")
    with zipfile.ZipFile(zip_yolu) as z:
        z.extractall(hedef)


def pp4av_indir():
    print("\n[1/2] PP4AV indiriliyor (biraz sürebilir)...")
    klasor = snapshot_download(
        repo_id="khaclinh/pp4av",
        repo_type="dataset",
        local_dir=PP4AV_KLASOR,
        allow_patterns=["data/*", "README.md"],
    )
    for dosya in os.listdir(os.path.join(klasor, "data")):
        if dosya.endswith(".zip"):
            zip_ac(os.path.join(klasor, "data", dosya), PP4AV_KLASOR)
    print("  PP4AV tamam.")


def wider_indir():
    print("\n[2/2] WIDER FACE (validation) indiriliyor...")
    os.makedirs(WIDER_KLASOR, exist_ok=True)

    # Görüntüler (Hugging Face kopyası)
    goruntu_zip = hf_hub_download(
        repo_id="CUHK-CSE/wider_face",
        repo_type="dataset",
        filename="data/WIDER_val.zip",
        local_dir=WIDER_KLASOR,
    )
    zip_ac(goruntu_zip, WIDER_KLASOR)

    # Etiketler (resmî siteden)
    etiket_zip = os.path.join(WIDER_KLASOR, "wider_face_split.zip")
    print("  Etiketler indiriliyor...")
    urllib.request.urlretrieve(WIDER_ETIKET_URL, etiket_zip)
    zip_ac(etiket_zip, WIDER_KLASOR)
    print("  WIDER FACE tamam.")


if __name__ == "__main__":
    os.makedirs(VERI, exist_ok=True)
    for adim in (pp4av_indir, wider_indir):
        try:
            adim()
        except Exception as hata:
            print(f"  HATA ({adim.__name__}): {hata}")
            print("  Bu hatayı Claude'a yapıştır ya da elle indirmeyi dene.")
    print("\nBitti. 'data/' klasörünün içine bakabilirsin.")
