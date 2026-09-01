
## 2026-09-01 — "done rc=0" bir demo kanıtı değildir
Owner düzeltmesi: sevk edilen E2E filmde set_pose'lu Nav2 kurtarması
vardı; döngü "done" bitti diye filmi doğru saydım. Ders: bir demo
artefaktı MÜDAHALESİZLİK invariant'ına karşı doğrulanır, çıkış koduna
karşı değil - kurtarma/reseed/set_pose olayları sayılır ve sıfır
olduğu KANITLANIR (film cut'ı kurtarmalı döngüyü adıyla reddetmeli).
Kök neden dururken workaround'u sevk etme; owner'a kurtarmanın
varlığını sevkten ÖNCE söyle, sonra değil.
