
## 2026-09-01 — "done rc=0" bir demo kanıtı değildir
Owner düzeltmesi: sevk edilen E2E filmde set_pose'lu Nav2 kurtarması
vardı; döngü "done" bitti diye filmi doğru saydım. Ders: bir demo
artefaktı MÜDAHALESİZLİK invariant'ına karşı doğrulanır, çıkış koduna
karşı değil - kurtarma/reseed/set_pose olayları sayılır ve sıfır
olduğu KANITLANIR (film cut'ı kurtarmalı döngüyü adıyla reddetmeli).
Kök neden dururken workaround'u sevk etme; owner'a kurtarmanın
varlığını sevkten ÖNCE söyle, sonra değil.

## 2026-09-11 — zeminsiz fixture yeşil kalır, saha düşer
M8 A1'in çevrimdışı süiti 79 test yeşildi; aynı kod sahada C1'i ZEMİNE
oturttu (EVIDENCE_M8_E1) ve C2'yi 540/540 iptale soktu (E3). Sebep tek
bir şeydi: her fixture kareyi dolduran TEK bir düzlemdi - hiçbirinde
zemin yoktu. Ders: bir algılama fixture'ı, sahada BASKIN olan yüzeyi
içermiyorsa hiçbir şey ölçmez. Fixture'ı önce sahanın geometrisinden
kur (kamera yüksekliği, pitch, gerçek nesne boyutları), sonra kodu.
İkinci ders, aynı hatanın matematik tarafı: piksel koordinatlarında
bir düzlem `z = a x + b y + c` DEĞİLDİR; TERS derinlikte lineerdir
(`1/Z = alpha x + beta y + gamma`). A1'in modeli kendi band'ındaki
zemine 0.426 m artık rms ile oturuyordu - yani "intercept" hiçbir
zaman bir mesafe değildi. Yanlış modele eşik takmak düzeltme değildir.
Üçüncüsü: türetilmiş ROI kullanan bir sınıflandırıcı ROI'sini LOGLAMAK
zorunda - yoksa "pallet_absent" ile "segmentasyon kaçırdı" ayrılamaz.

## 2026-09-12 - en buyuk blob palet degildir
M8 C1 ilk saha kosusunda staging'de 0/30 verdi. Sebep esikte degildi:
zemin uzerinde duran EN BUYUK bilesen bir DUVAR idi (0.807 x 1.356 m,
2.64 m'de), palet ise karenin %2.9'u. "En buyugu al, sonra kapilardan
gecir" sirasi, kapilarin hepsi dogru olmasina ragmen dogru nesneyi hic
denemedi. Ders: aday secimini kapilardan ONCE yapma - tum adaylari
sirala, her birini tam kapi setinden gecir, ilk gecen kazansin.
Ikincisi, olcerek ogrenildi: 1.0 m'de aracin KENDI CATALLARI palet ile
menzil olarak SUREKLI (komsu hucre adimi p99 0.055 m, birlesme
noktasinda adim YOK), yani derinlik-farkindali baglanti da ayiramaz.
Cozum bir esik degil, bir self-mask (mast/catal joint state) - ve o
m8_core'da yok. Yanlis poz uretmek yerine REDDETMEK birakildi.
Ucuncusu: "observed 0/30" bir teshis degildir. Her reddedisin ADI
olmali (`_refuse()` + trace) ve bench o adi loglamali; aksi halde
"palet yok" ile "segmentasyon kacirdi" ayni cumle olur.
