# M6 revize turu — 2026-08-25 (review raporundan, owner onayli sira)

Rapor: vault projects/active/amr-agent/2026-08-25-m6-review-raporu.md
Owner: "Sirayla basla hepsini coz; 1, 4 ve 5 cok onemli."

- [x] 1. Bloker deneyi kamerada: assets/m6-fleet/m6-fleet-08-blocker-
      recovery-2026-08-25.mp4 (kutu, watchdog, requeue, step-aside,
      kutu kalkinca f2'nin toparlanmasi hepsi filmde). PROOF eki yazildi.
      Ilk take koprü aclik teshisiyle atildi (PROOF'ta).
- [x] 4. record_operator: RateClock (sim saat + pencereli RTF her karede),
      on_connect'te abonelik + benzersiz client id (donmus panel kusuru),
      fleet_cli: shift seridi + idle satirlarina yas. Testler yesil.
- [x] 5b. Mid-base head-on cozucusu: floor stillness saati (0.5 m/20 s);
      cozulmus kafa kafaya wait-die'a degil dogrudan step-aside'a gider.
- [x] 5b+. Vazgecilen step-aside aracini strandlamaz: give-up cancelOrder
      cekiyor (sahada olculen kusur, ayni gun test + fix).
- [x] 5c. BLOCKED -> pathBlocked -> node kapatma: vda_agent edge raporu,
      manager _check_blocked, floor.close_node (120 s, phantom hold),
      route.plan_route avoid seti (leg kimliginin parcasi).
- [x] 5d. Rig-bagimsiz olcut turetimi:
      docs/superpowers/specs/2026-08-25-rig-independent-criteria.md
- [ ] 5a. Escalation SAHA testi: HALA OLCULEMEDI - iki denemede govde
      guvenlik katmaninda durdu ve nav lidar beslemesi dondu; bes boot
      temiz kopru vermedi. tools/preflight.sh eklendi; preflight'i
      gecen bir boot'ta tekrar denenecek (soguk makine / Windows reboot).
- [x] 2. vda5050-subset.md koda esitlendi (Amendment 2026-08-25;
      pathBlocked satiri dahil).
- [x] 3. pick/drop node aksiyonlari: order_builder son node'a
      deterministik actionId'li aksiyon koyar; vda_orders kapisi yalniz
      final node'da tek pick/drop kabul eder; vda_agent dongusu
      WAITING->RUNNING(varista)->FINISHED(3.0 s) raporlar, iptal FAILED
      eder; fleet leg 2'yi ve tamamlanmayi rapora kilitler (dwell saati
      artik yalnizca taban). Mast HENUZ hareket etmiyor (FORK_CYCLE_S
      aktuasyonun yeri).

## Review
Suite: 583 passed, 0 skipped (guen basinda 552). Kanit: PROOF.md
"M6 review revise round" bolumu; video 08; vault raporu.

- [x] E2E vitrin filmi (owner istegi, 25 og.s.): m6-fleet-09-e2e-vda5050-
      2026-08-25.mp4 - 8m23s tek cekim; konsol gorevi -> ORDER+pick ->
      RUNNING/FINISHED -> leg2+drop -> DONE kamerada. record_e2e.py +
      fastdds_loopback.xml (DDS multicast olumu koku) + paralel preflight.
      Kural: arac kodu degisince `m6.sh deploy` sart.

---

# m5-ver3 — sensör füzyonlu otonom sürüş (branch: m5-ver3, main'e dokunulmaz)

Karar: vault AMR-DEC-003, 2026-08-25. Araştırma: docs/reports/m5v3-01..04.
Sıra: önce tek araç (vitrin aracı), filo entegrasyonu (M6) ayrı karar.

- [x] F1. Gerçek sensör paketi + gerçekçilik: nav lidar TiM571 profili
      (15 Hz, 811 örnek, gürültü+bias+kuantizasyon), safety scanner'lara
      nanoScan3 zarfı+gürültü, RGB-D kamera (D455 sınıfı) + AprilTag
      istasyon işaretleri, [karar bekliyor] 3D lidar (OS0/Mid-360 sınıfı,
      yalnız vitrin aracı). Ground-truth odom KALKAR: joint state'ten
      enkoder-kuantizasyonlu tekerlek odometrisi + WheelSlip + %1-2 teker
      yarıçapı hatası. Kanıt: datasheet-vs-ölçülen gürültü tablosu, RTF.
      YAPILAN (4 görev, 2026-08-25/26; m5_ver3/, kanıt EVIDENCE_BRINGUP +
      EVIDENCE_MODEL_V3 + EVIDENCE_SENSORS): TiM571, nanoScan3 ve D455
      profilleri kuruldu; "[karar bekliyor]" 3D lidar kararı VERİLDİ —
      OS0 sınıfı takıldı, köprüye alınmadı (tüketicisi F2; abonelik
      RTF'yi 0.999 → 0.85 düşürüyor); tekerlek odometrisi
      nodes/wheel_odometry.py olarak yazıldı (1024 sayım/tur, +%1.5
      yarıçap, +0.005 rad direksiyon biası) ve dört profilde ground
      truth'a karşı ölçüldü. GROUND-TRUTH ODOM KALKMADI: modelde ÖLÇÜM
      REFERANSI olarak duruyor — yerine geçecek füzyon (EKF) F2'nin işi,
      ve F1'in kendi sürüklenme tablosu bu referans olmadan yazılamazdı.
      AÇIK KALAN: AprilTag istasyon işaretleri (bu görev planının
      kapsamında değildi).
- [x] F1.5. Yanal kayma (lateral scrub) teşhisi ve ayarı — sahip onayı
      2026-08-26, F1'in ölçtüğü 0.410'un üzerine. Tek görev; ayar yüzeyi
      YALNIZCA WheelSlip parametreleri (mu, kütle, atalet, geometri
      kapsam dışı). Kanıt: m5_ver3/EVIDENCE_LATERAL_TUNE.md.
      TEŞHİS (yeni araç: evidence_core.scrub_split, analyse basıyor):
      creep'te kaybolan yaw'ın %99.5'i DİREKSİYONLU tekerlekte, %0.5'i
      arka akstaydı — ama arka aks kaymıyordu ÇÜNKÜ kayamıyordu: iki
      arka tekerlekte WheelSlip girdisi yoktu, rijit temas yamaları
      kendi dikey ekseni etrafında dönemez, ve bedelini kayabilen tek
      yama (direksiyonlu olan, 22° kayarak) ödüyordu.
      AYAR: hiçbir uyumluluk değeri değişmedi — iki arka tekerleğe aynı
      7.0, kendi normal kuvvetleriyle (3448.3 N) eklendi.
      SONUÇ: creep oranı 0.410 → 1.0054 (3 koşu, aynı); köşe içi yaw
      salınımı %10.1 → %0.0; boyuna kayma %0.96162 → %0.95603 (0.5-2
      bandında); square yeniden tablolandı (köşe 9.142 s → 6.145 s) ve
      kapanış 0.6786 m → 0.0670 m; başlık bağımlılığı %16.6 → %11.5
      (kaybolmadı, kayda geçti); straight sürüklenmesi değişmedi
      (0.5800 → 0.5778 m); RTF 0.9989; 82 pytest + iki selftest yeşil.
      YAN BULGU (kayda geçti, düzeltilmedi): <slip_compliance_lateral>
      ile <slip_compliance_longitudinal> etkileri ADLARIYLA TERS —
      düz gidişteki boyuna kaymayı "lateral" olan belirliyor.
      GERİ ÇEKİLDİ (aynı gün, incelemede): "base_link ve mast'ta
      <inertial><pose> kendi <link><pose>'unu tekrarlıyor, kütle merkezi
      3.1 mm arkada" iddiası YANLIŞTI — o iki linkte <link><pose> hiç
      yok, dolayısıyla birleşecek bir şey de yok; hesap iki eylemsizlik
      ofsetini ikinci kez ekliyordu. Doğrusu: yalnız link pozları
      -93.551, birleşik -97.151 kg m → N_drive 4537.4 N. Yani kullanılan
      sabit ZATEN birleşik olan ve DOĞRU. Park edilen bir şey yok.
- [x] F2. Füzyon katmanı: çift EKF (robot_localization; odom EKF =
      teker+IMU+rf2o twist, map EKF = AMCL pozu); fuse (factor graph)
      paralel A/B kolu. Kanıt: WheelSlip senaryosunda EKF'li/EKF'siz
      sürüklenme, ground truth'a karşı.
      YAPILAN (4 görev, 2026-08-26; kanıt m5_ver3/EVIDENCE_FUSION.md
      §1-§11): odom-EKF gemide — teker twist [vx,vy,vyaw] + IMU [wz];
      iki karar ölçümle tersindi (vy AÇILDI: d·yaw_rate gerçek sinyal,
      corner_creep 1.06→0.19 m; ax DÜŞTÜ: tek çevrimde 5e-4→2.4e84
      sessiz patlama, ortam-hızına bağlı, kalıcı çözüm KOVARYANS SAĞLIK
      KAPISI — patlayan filtre start'ı isimli refusal'la düşürür).
      --slippery çalışma-zamanı çekiş override'ı (model bayt-aynı) +
      oturum etiketleme/karışım refusal'ı; ıslak zeminde jiroskop rotayı
      kurtarıyor, mesafeyi kurtaramıyor (F3'e ölçülü devir: 11 m'de
      +1.06 m along-track). rf2o kaynaktan pinli derlendi (--rf2o,
      VARSAYILAN KAPALI: kuru yol hatası +4.2→+1.3% ama corner_creep
      kötü, 11.6% çekirdek); fuse sudo'suz vendorlandı (--fuse,
      VARSAYILAN KAPALI: doğruluk berabere, 3.5× CPU, 25× dürüst
      gecikme). VARSAYILAN ESTIMATOR: robot_localization kalır. Map-EKF
      (AMCL pozu) F3'e taşındı — harita olmadan skorlanamaz. Suite
      82→239; faz-sonu dal incelemesi + tek düzeltme dalgası temiz.
- [x] F3. Harita + lokalizasyon: slam_toolbox offline haritası
      (warehouse_ver3, m5-08d yöntemi: kayıt→registration→mutlak skor);
      AMCL vs slam_toolbox localization A/B, aynı enstrüman tabanı.
      Kanıt: mutlak rms tablosu (m5_ver1 0.124 m referans).
      YAPILAN (3 görev, 2026-08-26/27; kanıt m5_ver3/EVIDENCE_MAP_V3.md
      ve EVIDENCE_LOCALIZATION_V3.md): 227 m'lik commissioning sürüşü
      bag'e alındı, slam_toolbox sync ile ÇEVRİMDIŞI harita kuruldu ve
      DONDURULDU (maps/warehouse_v3, md5'li build.txt + committed
      registration); registration duvar-fit ile TÜREVLENDİ, enstrüman
      TABANI rms 0.0291 / MAX 0.1179 m, mutlak açıklıklar 48.019/28.036
      m (gerçeği 48.000/28.000). --localize amcl: nav2_amcl + map_server,
      her parametre bir ÖLÇÜMDEN argümanlı (sigma_hit ve z_rand haritanın
      kendi desteğinden), map→odom tek sahipli, md5 kapısı + lokalizasyon
      sağlık kapısı + üçüncü etiket (loc=) ve karışım refusal'ı. KURU
      kabul: END 0.0382–0.1954 m (medyan 0.0395), F2'nin borcu %95.7
      ödendi; ISLAK stretch: %71–83. --localize slam (F3.3): AYNI donmuş
      poz grafiği üzerinde slam_toolbox localization; A/B tek enstrümanla.
      SONUÇ İKİ MAKALEYİ DE DOĞRULADI, farklı yarımlarda: koridorda poz
      grafiği HAREKET HALİNDEKİ along-track ofseti 0.27–0.33 m (kuru) ve
      0.69–0.79 m (ıslak) yerine 0.07–0.09 m'ye indiriyor (3–11 kat);
      DÖNÜŞTE ise AMCL kazanıyor (corner_creep END 0.0382'ye karşı
      0.3301 m, ıslak square'de 0.1326 rad'lık yön sıçraması). CPU:
      7.85–10.49 % (amcl kolu) / 13.25–14.86 % (slam kolu). Snap
      relokalizasyon GÖZLENMEDİ — sanılan bir tanesi, stop'un
      süpürmediği ZOMBI düğümlerdi (tools/_common.sh desen listesi
      düzeltildi + tests/test_sweep_patterns.py o sınıfı kilitliyor).
      TAVSİYE (EVIDENCE_LOCALIZATION_V3.md §13.10): F4 için VARSAYILAN
      AMCL kalır (forklift dönüyor); poz grafiği kolu ağaçta, bir
      bayrak uzakta. Map-EKF ERTELENDİ: medyan düzeltme AMCL'de
      19–47 mm (harita hücresi 50 mm), slam kolunda 22–135 mm;
      yumuşatıcı gecikme ekler ve okunmayan bir sayıyı iyileştirmek için
      manşet sayıyı bozar (§13.11). Suite 239→438; selftest 30→44.
- [x] F4. Nav2 sürüş: Smac Hybrid-A* (REEDS_SHEPP, gerçek min dönüş
      yarıçapı) + MPPI Ackermann (RPP yedek) + tricycle BT (Spin/BackUp
      yok) + collision monitor (VelocityPolygon) + keepout + velocity
      smoother; PLC V_Limit → /speed_limit köprüsü (zarf mimarisi ve
      ADR 0014 korunur). Kanıt: m6'nın sürüş vakaları Nav2 ile yeniden.
      YAPILAN (5 görev, 2026-08-27; kanıt m5_ver3/EVIDENCE_NAV_V3.md
      §1-§20): Nav2 kamyonu sürüyor — komut yolu (ters kinematik telde
      4e-11; slew rampaları birebir; /speed_limit dönüştürücüde çünkü
      Jazzy smoother'ında YOK, ölçüldü), Smac Hybrid REEDS_SHEPP + MPPI
      Ackermann + Spin'siz BT. İLK SÜRÜŞLER 1/5 VARDI ve teşhis görevi
      mekanizmayı buldu: yolu tutan tek critic (PathAlignCritic) 1000
      planın SIFIRINDA skorlamıştı — bir hız ayarı MPPI ufkunu sessizce
      dönüş yarıçapının altına kısmış. 4 parametreyle basit hedefler
      10-11/11 (başlık 6/6). Vaka seti 4/8: iki kaçak TEK mekanizma
      (START_OCCUPIED bay kısıtı — F5'in rejimi, iki-aşamalı yanaşma
      ŞART), biri park edilmiş ring_corner (uzun-düzlük modu, iki
      kaldıraç ölçümle elendi, mekanizma doğrulanamadı), biri fail-fast
      yakaladı. FAIL-FAST: kaçan hedef artık 130 m değil — 30 sn'de
      isimli uyarı, 91 sn'de iptal. #5714 TERSYÜZ bulundu (ileri takip
      geriden %50 kötü, committed enstrümanla). Flip: slam kolunun
      koridor avantajı kapalı döngüde yaşıyor. Monitor --monitor
      arkasında (yedek, muhafız değil: local costmap 0.36 m önce
      davranıyor); global costmap'te obstacle layer YOK (bulaşma sıfır
      kanıtlandı, F5'e devredildi). Sıçrama bütçesi §13.10b: 1.20 m
      amcl / 0.89 m slam, ÜST SINIR YOK. Suite 583→873. Faz-sonu hüküm:
      isimli sınırlamalarla KAPANDI, F4.5 yok — kaçaklar F5'in kendi
      rejimine ait.
- [x] F5. Hassas yanaşma + palet: opennav_docking SimpleNonChargingDock +
      AprilTag detected_dock_pose; spur çıkışı = undock (düz geri, MPPI
      reverse riskini atlar); DetachableJoint ile palet al/bırak
      (geometrik predicate'li attach). Kanıt: `m5_ver3/EVIDENCE_DOCKING_V3.md`
      (plugin 5/5, class 2/5 vs 0.25 m; pallet attach/lift/carry/detach;
      dry cycle ×3 `pallet-cycle-20260829-013326`). §5'in FİLM residual'ı
      ÖDENDİ: kanıt `m5_ver3/EVIDENCE_FILM.md` — dört kamera, sidecar
      WALL→SIM saati, dört çekim (üçü kusurlu, her kusur isimli bir
      reddediş veya örneklenmiş kare ile yakalandı) ve sevk edilen çekim
      `film-20260901-093823`: tek otonom palet çevrimi, 12 leg, 304.80 s,
      10/10 kare etiketiyle uyumlu. Opsiyonel SOTA (öğrenilmiş palet
      tespiti) AÇIK residual olarak kalır — §5.
- [x] G5 (F5 sonrası düzeltme dalgası, 2026-09-01). Owner filmi izledi ve
      1:40–2:24'te kamyonun SÜRMEDİĞİ bir poza vardığını gördü: palet
      çevriminin "boş Nav2 kaçağını staging'e kurtar" adımı araca
      `set_pose` ile dokunuyordu. KARAR AMR-DEC-004: "kurtarma
      müdahaleleri hiç doğru değil; git kök nedeni bul, onu çöz."
      YAPILAN (kanıt `m5_ver3/EVIDENCE_STALL.md`): sınıf önce
      DETERMİNİSTİK hale getirildi — tohumlanmış ters giriş açısı, dünya
      (−0.438, +9.736) yaw −2.7338 rad, 64 deneme; MPPI dokuz ayrı
      nav2.yaml parmak iziyle 49 denemede 3 varış, ilk 18 deneme 18/18
      başarısız. MEKANİZMA: ters girişte MPPI'nin yol critic'leri yetkiyi
      kaybediyor (PathAlignCritic `furthest=0 < 12`'de KENDİNİ KAPATIYOR,
      hedef critic'leri menzil dışı), softmax kendi önseline çöküyor ve
      kamyon YANLIŞ YÖNE ~0.081 m/s sürünüyor; terminaller `no_progress`
      ve START_OCCUPIED 205 — 205 nav2'nin planlayıcı kurtarma kümesinde
      YOK ({200, 207, 208}). Arşiv sayımı sınıfı TEK mekanizma olarak
      isimlendirdi: 55 servis-içi bitmemiş sürüşün 29'u ≥20 s sürünme
      platosu taşıyor ve 29'unun HEPSİ 0.0777–0.0901 m/s'de — 4 gün,
      12 parametre dosyası, 7 hedef, iki terminal. BEŞ ADAY NEDEN ÖLÇÜLDÜ
      VE ÇÜRÜTÜLDÜ: budama, change_penalty, vx_std, replan'ın kendisi
      (F1 pilotu: koşu başına TEK plan, ters girişte 3/5 ama dört aşım
      hatası ve 0.66 m geride donmuş plan) ve DirectionStablePath'in iki
      kolu (yalnız-yön 2/8 ters, 4/4 normal; commit 0/8 ters ve normalde
      4/4 → 2/4 GERİLEME). Commit modu replan'ların %92'sini reddetti ve
      sürünme saniyede bir milimetre oynamadı — tamamen kaldırıldığında
      etkiyi değiştirmeyen şey neden DEĞİLDİR. ÇÖZÜM AMR-DEC-005 (owner
      hükmü): ters-yoğun bacaklar MPPI'den RegulatedPurePursuit +
      `allow_reversing`'e geçti — örnekleme yok, critic yok, önsel yok,
      carrot cusp'ı geçemiyor (`findVelocitySignChange`); sürünmenin
      olduğu durum YAPISAL OLARAK ERİŞİLEMEZ. stage_s5 ters giriş 7/8
      (en uzun plato ≤3.0 s, yerine geçtiği kolda 47.5–101.0 s), normal
      4/4 29.8–31.7 s; koy çıkışı 6/6 26.8–29.0 s (MPPI 0/2 — ikisi de
      30 s'de yalnız 2.40 m, tamamı sürünme). EŞLEME MENŞE BAZLI: 17.00 m
      spawn düzlüğü MPPI'de KALIYOR (8/8; RPP 7/8), koy çıkışı için
      ikinci hedef satırı `spine_north_from_bay` — aynı poz, `same_pose_as`
      ile BEYAN edilmiş, `tests/test_nav2_params.py` iki yönde de tutuyor.
      KABUL: iki tam çevrim çifti, 48/48 leg `rc=0`, dört dock `success`
      `error 0`, SIFIR `nav2 miss recovered`, SIFIR 205. Suite 1115→1218.
      AÇIK KALAN (isimli): 17 m bacağın yanal sapma sınıfı (her iki
      kontrolcüde, ~1/8, plato TAŞIMIYOR — bu sınıf DEĞİL; MPPI'nin
      PathAlignCritic bitişi kurtarıyor, RPP'de karşılığı yok),
      `station_approach` hâlâ MPPI (ölçülmüş kanıtı silmemek için
      bilerek), RPP'de cusp direksiyon-tavanı kırpması (ters girişte
      %1.96, sevk edilen şekilde %0.06), her çiftin İLK dock'unun
      123–129 s'si açıklanmadı, `--fuse`/`--slam` kolları RPP ile
      ölçülmedi.

Bilinen riskler: MPPI Ackermann geri-viraj sapması (nav2 #5714, açık;
undock ile hafifletilir) · ros_gz köprüsü RTF yer (pointcloud köprüleme,
gz-sensors #545 hizasızlık) · gpu_lidar sığ açı hatası (gz-sim #2743).


---

# m6-ver2 — tek araç, filo emri, Nav2 üzerinde (branch: m6-ver2)

Karar: AMR-DEC-006, 2026-09-02. Spec: `m6_ver2/SPEC_ADAPTER.md` +
`SPEC_NAMESPACING.md` (AMENDMENTS §3–§10 hüküm izidir).
Kanıt: `m6_ver2/EVIDENCE_G1.md`.

- [x] G0. İki spec ve DEC-006: m5v3 yığını `/fN` ad alanında, tek `/tf`,
      önekli frame'ler, tek `map`; adapter `m6/ipc/nav_node`+`nav_core`+
      `follower`(+`avoid`) yerine geçer ve `/auto` sözleşmesi BAYT AYNI
      kalır — reddediş dilbilgisi gerçek bir `nav_core` sürülerek
      pinlendi. Filo katmanı (vda_agent, m6/fleet, cmd_mux/gate, hmi)
      hiç değişmedi.
- [x] G1-A/B/B5. Türetme aracı (13 dosya, 137 literal, ters oynatma
      donöre BAYT eşit), tek dünya + tek birleşik köprü, operatör kapısı
      `m6v2.sh`, `truck.sh` (13 çocuk, hepsi ad alanlı; toplam hücre 24
      çocuk), altı saf çekirdek (selftest 110/110, mutasyon denetimli),
      yer-gerçeği güvenlik duvarı telde kanıtlı (truth 0 abone,
      estimate 2). Suite 161 → 309 → 364.
- [x] G1-C1..C9. Dokuz saha dalgası, 19 koşu, ON ALTI kusur sınıfı
      isimlendirildi ve kırmızı testle öldürüldü (D1..D16; tablo
      `EVIDENCE_G1` §3). Üç mimari hüküm ÖLÇÜMLE alındı: §4 TRANSIT→RPP
      (m5v3 sürünme parmak izi 4 plato → 0, sekiz oturum), §5 türetilmiş
      ağaçlardan DirectionStablePath söküldü (yön-tutma 11 → 0; koridor
      taşması run-10'un +2.43 m'sinden D12 yayında +0.927 m'ye), §9 ring
      bacakları kendi poligonunu `/follow_path` ile sürer, Smac yalnız
      manevra planlar (tükenme 13/8 → 0; planner CPU p95 41.8 / max
      108.2 → 14.8 / 17.0).
- [x] G1 iki hüküm DÜRÜSTÇE bozuldu. §6'nın ima ettiği düzeltme (koy
      hedefi varış mandalını aşsın) inşa edildi, uçuruldu ve REDDEDİLDİ:
      aracı hiç oynatmadı (v 0.1159 → 0.0000 tek örnekte, kestirim
      0.2480 m — run 13'ün iptalli 0.2462 m'siyle iki milimetre farkla
      aynı duruş) ve bir sonraki emri öldürdü (`blocked: nav2 refused
      (error_code 0)`, beş kez) → §7. §5 × §8 sahada UZLAŞMAZ çıktı
      (5/5 hareket hâlinde devir ama 8 hizalama bacağının 3'ü hiç
      kapanmadı, gövde twist'i 30 s'de 14 kez işaret değiştirdi) →
      §9 tartışmalı nesneyi sildi: dönüşte artık hedef yok.
- [x] G1 BAR (`m6_ver2/logs/run19-c9-session`, 2026-09-02): ARDIŞIK İKİ
      TEMİZ FİLO EMRİ S1→S4. done=1 270.1 s, done=2 435.1 s — ikincisi
      spawn'dan değil S4'ten sürüldü (atama mesafesi 51.26 m), kuyruk 0.
      Telde 4 EN-ROUTE / 4 ARRIVED, her not boş, SIFIR BLOCKED. Zincir:
      4 sevk, remain= 4.00/43.89/43.91/43.89 m, 141 kapanma örneği, her
      zincirde en kötü artış 0.000 m. Koridor: kendi grantından en kötü
      0.260–0.330 m — bir dik açının 1.25 m yarıçapla kestiği 0.366 m
      sagitta içinde; y=10 kuzeyi +0.295 m (run-10: +2.43). Cusp:
      45 471 komutta 0 çekiş işaret dönüşü (run-16: 30 s'de 14).
      Motor-False 0, PF talebi 0, DSP tutma 0, Smac tükenmesi 0,
      sürünme platosu 0. Kestirim S4 çevresinde n=784 ort 0.0568
      p95 0.0619 — dört dalganın borçlu olduğu sayı (önceki her oturum
      `within 0.60 m of S4: None` yazıyordu). Suite 364 → 571.
- [ ] AÇIK (isimli, `EVIDENCE_G1` §6): dört araç ÖLÇÜLMEDİ — adapter
      araç başına ~%50 çekirdek, gz tek araçta %163.7; run 19'un gz
      ortalaması önceki her oturumdan 27 puan yüksek ve AÇIKLANMADI;
      sahada yalnız S1→S4 çifti sürüldü (12 istasyonun en dar
      geometrisi olan annex koyları hiç); zincir watchdog'unun gerçek
      pozitifi hiç ateşlenmedi; F-PLC hâlâ `--virtual`; koy dönüşünde
      1.703 m savrulma sınırsız; `station_approach` sınıfı m5v3'ten
      miras; deploy disiplini ertelendi (`m6v2.sh` başlığında yazılı);
      ölü nav modüllerinin testleri m6/ içinde duruyor (pin oraya
      bakıyor); üç dalga-commit sayısı arşivinden yeniden üretilemedi ve
      yerlerine arşivin kendi sayıları kullanıldı.
