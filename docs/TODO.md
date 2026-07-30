# TODO

Open items only. M4 (forklift commissioning, ADR 0008) is the open gate,
in closing; the m5r restructure round (ADR 0010) is in flight and its
brief queue lives in docs/PLAN.md.

## owner — build COMPLETE on the CPU (2026-07-30 TIA handover, live-verified)
- FB_ForkliftTeleop (§7 + §13) in OB30; D1-D7 applied; mirrors and stand-in
  DBs served; 23/23 nodes with correct access read back; monitored reset and
  its 3 s upper bound observed live; first live teleop drive done and
  captured (owner video, Screen Recording 2026-07-30 085503.mp4 — informal
  evidence, the formal showcase recording still to be made per the scenario
  checklists).
- Before the T6 recording, read from TIA and write down (handover items 1-6):
  the F-collective signature (online/offline, dated); F-runtime monitoring
  time and F-OB cycle time; verify RESET_HOLD_MIN (200 ms) covers ≥5 F-OB
  cycles — if it does not, raising it is an SRS-window deviation recorded as
  an open item, never a silent tune; OB30 and CPU max cycle times; the
  safety access-protection password decision (or an explicit out-of-scope
  line); the HmiStaleTimer.PT watch row showing T#600MS.
- Copy the TIA evidence PNGs into plc/forklift/evidence/ and
  plc/forklift-safety/evidence/ — the orchestrator commits them.
- Run T5.1-T5.6 (plc/forklift/SPEC.md §11) and T6 (safety SPEC §9.1) per
  sim/scenarios/forklift_commissioning.md §12, then record the showcase with
  the TWIN-DEMO-MAP naming discipline (nothing early-opened presented as M4
  evidence; "the operator drove the device from the engineering interface,
  the safety program did X").

## owner — M4 queue, in order
- Restored (m5r-09 finding 1, half-closed sub-item lost with its parent):
  m3-37 finding 7 — the built program declares ResetEdgeMemory_1 where
  plc/forklift/SPEC.md §3.2 says ResetEdgeMemory; align one of them at the
  next TIA session and sweep the browse names for TIA's silent "_1"
  suffixes while there (LESSONS 2026-07-30/#81).
- First WSL run of ./stack.sh (m4f-10): the readiness timeouts are
  uncalibrated — no bringup ever ran in the container; expect to tune, and
  report which component start lines disagree with the docs, if any.
- First PLCSIM session of the gate: one watch-table capture at a CPU cold
  start with the bridge down — all seven Group 1 inputs at their DB start
  values — closes m3-37 findings 1, 2, 8 and 9 at once (it also carries §11
  4.8's cold-start half and 4.9b form (b)). In the same session: the Group 1 +
  Group 2 capture with the cell running.
- Clock durability before any measurement run: elevated `Set-Service w32time
  -StartupType Automatic; Start-Service w32time; w32tm /resync` (the
  2026-07-27 resync was one-shot; the service does not stay started).
- Stop the still-live m3-26-era bridge session with SIGTERM before new bridge
  work: its clean shutdown prints the build-G R1/R2/R3 ratio set m3-36 wants,
  and its CSV is archived only after the process is gone (LESSONS 2026-07-28).
- After the TIA read-back: point bridge/config/bridge.yaml at the Forklift
  groups (one edit per bridge-design §2.1). Until then the live config is
  deliberately cell-only — browsing nodes the CPU does not publish would
  error (m4f-06). bridge/config/rehearsal-forklift.yaml is the double-facing
  config and is not the gate config.
- Run T5 per plc/forklift/SPEC.md §11 (T5.4 corrected 2026-07-29 — hold the
  reset unbroken, now executable from the page's press-and-hold RESET) and
  the five commissioning scenarios per sim/scenarios/forklift_commissioning.md
  (H6 note in its §9: a stimulus step that posts once and waits >1 s decays
  to rest by design), then record the showcase — the recording is gate
  evidence.
- BELT_SPEED_MIN/MAX remain design values (m3-27) — measure and record when
  convenient; not gate work.


## M5 — open items
- Monitoring service directory: ADR 0011 D4 recommends `agv/` but does not
  rule it; `viz/` is the alternative and the ADR 0005 test names the
  question — done when the first monitoring brief rules it.
- F-DI order number and its parameterisation (1oo2 equivalent, discrepancy
  time, input delay) are unfixed pending the m5-03 verdict — done when the
  F-program spec carries owner-verified values.
- plc/forklift-safety/SPEC.md open item 1 is answered in direction, not in
  fact: ADR 0011 F3 gives the probable cause (TIA V18/V19 defaulting above
  the supported safety-system-version list) — done when m5-03 settles it.
- Later gates: the M6 deep-research brief (ADR 0010 D6d) and the
  m4-00-hermes-survey decisions for M7 (D6c) — each done when owner-ruled.

## sim
- Cell reskin (deferred, visual only, ARIAC licence blocker unchanged).
- `--` inside XML comments breaks ElementTree in warehouse.sdf:16,
  forklift_arena.sdf:326 and cell.sdf:15 (m5r-07 OQ5, reproduced by
  m5r-09; the LESSONS 2026-07-27 cell.sdf mechanism) — one brief, comment
  text only.
- forklift_commissioning.md §1/§10 quote HMI port 8090, which is the
  rehearsal config's; hmi/config.yaml binds 8088 — align the doc with the
  config it names (m4f-10 OQ3).
- sim/README.md:50 lists scenarios/EVIDENCE_NAV.md, which exists only once
  a run produces it (DEFERRED.md:28) — mark it "(generated by the first
  run)" with the next sim touch (m5r-07 OQ6).
- M5 carried: resume the parked navigation scenario on the forklift
  (sim/scenarios/DEFERRED.md); the platform migration off RB-KAIROS is
  M5-briefing work (ADR 0010 D1).

## interface
- Carried (fold into the next interface brief): opcua-nodes.md §10.1 still
  describes the shared-project two-FB arrangement; the as-built forklift
  project runs one standard FB with both link verdicts inside it (m4f-04j).
  Add the heartbeat browse-path read-back note its report requests.
- Carried, low (fold into the next interface brief): bridge-design.md §7.2
  and opcua-nodes.md §9.7 still share the flat "No timer, threshold or
  reaction exists in the bridge" sentence that §10.1's ruling rephrased
  everywhere else — scope it the same way (own-cycle timers allowed, process
  timing forbidden); m4r2-07 report has the context.
- Carried, low: opcua-nodes.md §11.8 open item 1 is answered by m5a-06b but
  its closure mark needs a §11 edit that brief forbade — one line with the
  next interface touch.
- Carried (M6 briefing): vda5050-subset.md still defines
  typeSpecification.seriesName as RB-KAIROS per ADR 0002, with agvClass
  CARRIER and an agvKinematic that depends on the vehicle's steering model —
  redefine against the forklift (ADR 0010 D1) in its own brief; a field-value
  change, not a renumber (m5r-08 open question 1).

## hmi
- Carried, low: EVIDENCE_HMI.md §C's browser pass predates the m4f-07b change
  (7675960) and was not re-run — the endpoint pass proves the behaviour, the
  page's new DOM handlers are unexercised. The owner's live session exercises
  the page naturally; capture one screenshot of the held RESET there and the
  §D residual row closes.

## bridge
- Second witness for the masked-revert window (owner design decision,
  post-gate): a revert landing between the cycle's step-0 heartbeat read-back
  and step-4 write is erased and the restart goes undetected — measured
  median 5.255 ms of a 50.015 ms cycle, 10.5 %, with 4.0 s of exposure in the
  measuring run (m4f-05d). §8.1 requires a second witness; choosing one is
  the owner's. Consider also a bridge-side masked-revert counter so the
  property shows in production evidence, not only harness runs.
- Fault injection (SPEC §12 item 6; unblocks T4.11b): opt-in NaN/inf/
  out-of-window write that cannot be armed by accident in an evidence run.

## plc
- Fold into the next demo-cell plc brief: F6 (PresenceOnTimer.PT reads T#0MS
  after a CPU restart, likely §6.5's conditional call — diagnose, close or
  escalate); close SPEC §12 item 7 (rewrite-on-restart now delivered); T4.11
  reaction re-record with a per-session CSV; the §B2.9 "build B" three-delta
  label that three owner captures contradict (label only, no figure moves —
  shared with bridge); the demo-cell §4.3 "Nothing else goes into the
  interface." sentence, scope-stale after opcua-nodes §10.
- T4.11b stays blocked on bridge fault injection (above).
- Carried, low: plc/forklift/SPEC.md §12 item 7 is stale (its own item 7 —
  distinct from demo-cell's) — close with the next forklift plc touch
  (m5r-06 OQ3).
- M5/M6 carried: AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume
  of interrupted handshakes; dedicated F-I/O — forklift functions at M5,
  fixed-cell SF-05/06 with the stations at M6.

## agv
- Carried, small: agv/forklift/launch/vehicle.launch.py is the model's
  standalone test rig (own gz server and spawn). Used inside the composed
  stack it puts a second forklift into the arena — observed live 2026-07-29.
  Its file header and the README contract table should say "standalone rig;
  in the composed stack run the two scripts directly", or the launch should
  gain a no-sim argument. One small brief.
- Carried, low: wheel_radius_m, steer_limit_rad and the fork travel exist in
  both model.sdf and config.yaml (SDF cannot be read as YAML); model.sdf is
  the named authority with a mechanical agreement check in the evidence. If
  invariant 10 is ever read strictly here, generate one file from the other.
- Carried, low: EVIDENCE_MODEL.md could carry its own all-181-sample
  flat-wall dump so the ±45° scanner dropout claim stands on the vehicle's
  own evidence rather than on m4f-03's (m4f-02b note).

## verifier
- m4f-09 (queued, after the owner evidence) — done when every M4 criterion
  has a cited-artifact verdict and the tracking files reconcile against the
  full report directory.

## safety-spec
- m2-04 residue (substance only — m5r-05 carries the gate renumbering):
  SF-08 carries an architecture claim beside its PL c or states the
  inheritance; SF-03's bumper latch appears in §2's no-auto-resume list;
  AT-01 gains the at-rest sub-test SC-02 observes. One brief.
- Carried, low: SF-02's old "review" half collapsed into M5 with no later
  review point (m5r-05 OQ3) — decide at M5 briefing whether a review lands
  at M6.

## docs residue
- README architecture diagram and layer table predate the hmi/ layer
  (m4r2-04 residue) — one infra brief when convenient.
- CLAUDE.md §4's repository layout does not list stack.sh (m5r-09
  finding 4) — one line with the next contract touch, owner-approved.
- assets/rb-kairos-gazebo.png and its reproduced BSD-3-Clause notice
  illustrate nothing after ADR 0010 (m5r-04 OQ2) — keep or remove is the
  owner's call, one line either way.

## publication
- Repository is public-ready and pushed; visibility is the owner's to flip.
  Residual, low: ADR 0007 names a hosting provider and region — an accepted
  ADR is never edited, so closing it needs a superseding ADR or owner
  acceptance as-is. Local commits since the push are unpushed until the owner
  pushes.

## carried forward, by gate
- interface (M6): the fleet-facing server interface's name is a contract
  decision (ADR 0006) — chosen deliberately at briefing, never discovered in
  TIA; opcua-nodes.md §2 still heads the fleet tree with http://DemoCell.
- plc/owner (later gate): suppress DataBlocksGlobal DB-level exposure by
  clearing each DB's "Accessible from HMI/OPC UA" attribute (opcua-nodes.md
  §9.8 open item).
- fleet (M6): confirm the handshake timeout constants.
