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
      bayrak uzakta. Map-EKF ERTELENDİ: medyan düzeltme 19–94 mm,
      yumuşatıcı gecikme ekler ve okunmayan bir sayıyı iyileştirmek için
      manşet sayıyı bozar (§13.11). Suite 239→438; selftest 30→44.
- [ ] F4. Nav2 sürüş: Smac Hybrid-A* (REEDS_SHEPP, gerçek min dönüş
      yarıçapı) + MPPI Ackermann (RPP yedek) + tricycle BT (Spin/BackUp
      yok) + collision monitor (VelocityPolygon) + keepout + velocity
      smoother; PLC V_Limit → /speed_limit köprüsü (zarf mimarisi ve
      ADR 0014 korunur). Kanıt: m6'nın sürüş vakaları Nav2 ile yeniden.
- [ ] F5. Hassas yanaşma + palet: opennav_docking SimpleNonChargingDock +
      AprilTag detected_dock_pose; spur çıkışı = undock (düz geri, MPPI
      reverse riskini atlar); DetachableJoint ile palet al/bırak
      (geometrik predicate'li attach). Opsiyonel SOTA katmanı:
      LOCO/sdg_pallet_model öğrenilmiş palet tespiti (demo markera
      dayanır). Kanıt: docking doğruluğu (0.25 m toleransa karşı), film.

Bilinen riskler: MPPI Ackermann geri-viraj sapması (nav2 #5714, açık;
undock ile hafifletilir) · ros_gz köprüsü RTF yer (pointcloud köprüleme,
gz-sensors #545 hizasızlık) · gpu_lidar sığ açı hatası (gz-sim #2743).
