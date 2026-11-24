# Yanlış pozitiflerin gözle incelenmesi

Tespit modu: parcali, eşikler: yüz 0,10, plaka 0,10. Her yanlış tespit, güven değeri gösterilmeden tek tek incelenmiştir.

| Senaryo | Sınıf | Yanlış tespit | Gerçek nesne (etiket eksik) | Model hatası | Belirsiz | İncelenmedi |
|---|---|---|---|---|---|---|
| S9 | Plaka | 32 | 29 | 1 | 2 | 0 |
| S9 | Yüz | 4 | 3 | 0 | 1 | 0 |


Kesin karar verilen 33 tespitin 32 tanesi (%97) aslında etiketlenmemiş gerçek nesnedir.
 Bu tespitler modelin değil veri setinin hatasıdır; yani raporlanan precision değeri, modelin gerçek başarısını bir miktar düşük göstermektedir.

