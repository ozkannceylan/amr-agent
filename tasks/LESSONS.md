
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

## M8 E3 words / self-mask (2026-09-12)

Birincisi, ve en pahalisi: AYNI kareyi IKI kez siniflandirmadan bir
farki bir degisiklige baglayamazsin. Tag kablolamasi 113 karenin 57'sini
`none` -> `pallet_absent` yapti; sadece self-mask tasiyan 427 karenin
SIFIRI bozuldu. Tek tabloda suclu belli oldu. Es-kare (paired)
olcum olmasaydi "0.884'ten 0.32'ye dustu, iyi" diyip regresyonu icine
gomerdik.

Ikincisi: BIR REFERANS SUTUNU SADECE BIR DERINLIKTE REFERANSTIR. Bu
rigde AprilTag paletin uzerinde degil, rafin arka panelinde - paletten
0.85 m geride. Kamera da merkez hattan 0.40 m kacik oldugu icin ikisi
dunyada ayni cizgide olmasina ragmen FARKLI piksel sutununa dusuyor:
stagingde 12 px, 1.5 m'de 27, 1.0 m'de 57. METRE cinsinden ise kayma
yok (-0.4019 / -0.3979 / -0.3994). Ders: referansi piksel olarak degil,
METRE olarak tasi ve cikarmayi derinligin bilindigi yerde yap.

Ucuncusu, olcerek ogrenildi: SENSOR KUYRUGUNU BOSALTAN DONGUDEN
SUBPROCESS CAGIRMA. Palet pozunu `gz model -p` ile spin dongusunun
icinden okumak cycle 0'i 83 kareden 1 KAREYE dusurdu (5 derinlikli
derinlik kuyrugu doldu ve dustu). Ayni okuma kendi thread'inde calisinca
45 kare geldi. Olcum aletinin kendisi olcumu bozabilir.

Dorduncusu: DUNYA DURUMUNU KOSU SIRASINDA OKU, sadece uclarinda degil.
Dock catallari paletin ICINE suruyor, yani plugin'in "temiz" dedigi bir
cevrim temiz bir dunya ile BITMIYOR - olculen 0.2372 / 0.0696 / 0.4715 m.
Uclarda okuyunca butun cevrim sayilamaz hale geliyordu, hicbir seye
dokunulmadan once alinan yaklasma dahil.

Besincisi: bir esigi degil, KELIMEYI duzelt. C1/C2 duzeltmesinde her
esik dogru calisiyordu ve canli yanlis-abort hala 0.884'tu. Sorun
"segmentasyon reddetti" sorusuna tek bir kelimeyle - `pallet_absent` -
cevap vermekti. Kelime bir DUNYA IDDIASIDIR ve kanit ister; kanit yoksa
dogru cikti SESSIZLIKTIR (ve sessizlik `proceed` degildir).
