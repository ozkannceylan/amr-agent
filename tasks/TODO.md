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
