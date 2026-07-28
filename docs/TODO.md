# TODO

Open items only. M3 closed 2026-07-28; M4 (forklift commissioning, ADR 0008)
is the open gate and its brief queue lives in docs/PLAN.md.

## owner — M4 queue, in order
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
- Build FB_ForkliftTeleop in TIA from plc/forklift/SPEC.md once m4f-04 lands:
  DBs, tags into the server interface per docs/interfaces/opcua-nodes.md §10,
  second OB30 call, download with the solid-green check, watch table
  "Forklift M4 gate". At that download also check m3-37 finding 7: the built
  program declares ResetEdgeMemory_1 where SPEC §3.2 says ResetEdgeMemory —
  align one of them.
- Run the five commissioning scenarios per
  sim/scenarios/forklift_commissioning.md and record the showcase — the
  recording is gate evidence.
- BELT_SPEED_MIN/MAX remain design values (m3-27) — measure and record when
  convenient; not gate work.

## interface
- m4f-01 (in flight) — done when opcua-nodes.md §10 defines the forklift node
  group, §9.8 is scoped, and the server-interface ruling is stated.
- m4f-05 (queued, after m4f-01) — done when bridge-design.md carries the
  plural output section and the forklift groups with the HMI-group exclusion.
  Fold in the two carried rows: §8.1 has no restart-detection row although the
  shipped code's log line cites it, and §2's cycle description predates the
  once-per-cycle heartbeat read-back.

## agv
- m4f-02 (in flight) — done when agv/forklift/ spawns headless, all three
  joints respond, both nodes publish at declared rates, evidence recorded.

## sim
- m4f-03 (queued, after m4f-02) — done when the arena + bringup run headless
  with every bridged topic at rate and cell.sdf untouched.
- m4f-08 (queued, after m4f-03/04/07) — done when the five scenarios are an
  owner-runnable procedure with an evidence checklist and a double rehearsal.
- Cell reskin (deferred, visual only, ARIAC licence blocker unchanged).
- M6 carried: resume the parked navigation scenario (sim/scenarios/DEFERRED.md).

## plc
- m4f-04 (queued, after m4f-01) — done when plc/forklift/SPEC.md §1–§12 is
  owner-buildable from its SCL sketch alone.
- Fold into the next demo-cell plc brief: F6 (PresenceOnTimer.PT reads T#0MS
  after a CPU restart, likely §6.5's conditional call — diagnose, close or
  escalate); close SPEC §12 item 7 (rewrite-on-restart now delivered); T4.11
  reaction re-record with a per-session CSV; the §B2.9 "build B" three-delta
  label that three owner captures contradict (label only, no figure moves —
  shared with bridge); the §4.3 sentence "Nothing else goes into the
  interface." is scope-stale now that opcua-nodes.md §10 extends DemoCell
  (m4f-01 report).
- T4.11b stays blocked on bridge fault injection (below).
- M5/M9 carried: AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume
  of interrupted handshakes, dedicated F-I/O for SF-05/06/07.

## bridge
- m4f-06 (queued, after m4f-05) — done when a double run proves every slot
  both ways, the HMI-group negative test, rewrite-on-restart over the full
  slot set, and the cell conformance unchanged.
- Fault injection (SPEC §12 item 6; unblocks T4.11b): opt-in NaN/inf/
  out-of-window write that cannot be armed by accident in an evidence run.

## hmi
- m4f-07 (queued, after m4f-06's double serves the forklift nodes; roster
  landed with m4r2-03) — done when the
  backend + UI run against the double, every write lands, and the heartbeat
  stops on kill.

## verifier
- m4f-09 (queued, last) — done when every M4 criterion has a cited-artifact
  verdict and the tracking files reconcile against the full report directory.

## safety-spec
- m2-04 SRS reconciliation (gate refs now per ADR 0008): SRS §4 references
  match M5 safety, M6/M7 vehicle chain, M10 demonstration, M11 arm; SF-08
  carries an architecture claim beside its PL c or states the inheritance;
  SF-03's bumper latch appears in §2's no-auto-resume list; AT-01 gains the
  at-rest sub-test SC-02 observes. One brief.

## owner — M5 entry, carried (was the M4 entry before ADR 0008)
- The ADR 0007 tool question, unchanged: does this install run an F-CPU on
  PLCSIM Advanced V7 (STEP 7 Safety Advanced V21 licence; 1513F-1 PN in the
  catalogue; an empty F-project reaching RUN with the F-runtime group
  executing; what F-I/O the catalogue offers)? The answers feed M5's first
  brief. No M5 brief until they exist.

## docs sweep (post-gate, one brief)
- Stale gate numbers across README.md (m4r2-04 covers the README), SRS.md,
  PL-SCENARIOS.md, plc/demo-cell/SPEC.md, sim/README.md, WSL_ENVIRONMENT.md,
  CREDITS.md, DEFERRED.md, bridge-design.md — inventory in
  docs/reports/m4r2-02-roadmap-renumber.md §3.
- M12 Hermes: ADR 0008 D2.7 rules the operator layer for the local case only;
  the remaining m4-00 decisions stay open.

## publication
- Repository is public-ready and pushed; visibility is the owner's to flip.
  Residual, low: ADR 0007 names a hosting provider and region — an accepted
  ADR is never edited, so closing it needs a superseding ADR or owner
  acceptance as-is. README gate table is stale until m4r2-04 lands.

## carried forward, by gate
- interface (M9): the fleet-facing server interface's name is a contract
  decision (ADR 0006) — chosen deliberately at briefing, never discovered in
  TIA; opcua-nodes.md §2 still heads the fleet tree with http://DemoCell.
- plc/owner (later gate): suppress DataBlocksGlobal DB-level exposure by
  clearing each DB's "Accessible from HMI/OPC UA" attribute (opcua-nodes.md
  §9.8 open item).
- fleet (M8): confirm the handshake timeout constants.
