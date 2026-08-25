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

- [ ] F1. Gerçek sensör paketi + gerçekçilik: nav lidar TiM571 profili
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
- [ ] F2. Füzyon katmanı: çift EKF (robot_localization; odom EKF =
      teker+IMU+rf2o twist, map EKF = AMCL pozu); fuse (factor graph)
      paralel A/B kolu. Kanıt: WheelSlip senaryosunda EKF'li/EKF'siz
      sürüklenme, ground truth'a karşı.
- [ ] F3. Harita + lokalizasyon: slam_toolbox offline haritası
      (warehouse_ver3, m5-08d yöntemi: kayıt→registration→mutlak skor);
      AMCL vs slam_toolbox localization A/B, aynı enstrüman tabanı.
      Kanıt: mutlak rms tablosu (m5_ver1 0.124 m referans).
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
