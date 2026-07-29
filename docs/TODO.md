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
- Build FB_ForkliftTeleop in TIA from plc/forklift/SPEC.md: DBs, tags into
  the server interface per docs/interfaces/opcua-nodes.md §10, second OB30
  call, download with the solid-green check, watch table "Forklift M4 gate".
  At that download also check m3-37 finding 7: the built program declares
  ResetEdgeMemory_1 where SPEC §3.2 says ResetEdgeMemory — align one of them.
- After the TIA read-back: point bridge/config/bridge.yaml at the Forklift
  groups (one edit per bridge-design §2.1). Until then the live config is
  deliberately cell-only — browsing nodes the CPU does not publish would
  error (m4f-06).
- Run the five commissioning scenarios per
  sim/scenarios/forklift_commissioning.md and record the showcase — the
  recording is gate evidence.
- BELT_SPEED_MIN/MAX remain design values (m3-27) — measure and record when
  convenient; not gate work.

## interface
- m4f-05d (issued) — done when bridge-design.md §8.1's restart-residual row
  states the measured masked-revert window (~5.255 ms of a 50.015 ms cycle;
  one masked revert held an open stop circuit and ObstacleInStopZone TRUE for
  4.0 s under an advancing heartbeat — m4f-06) and §12 items 11/13/14 reflect
  the m4f-06 closures.

## agv
- Carried, low: wheel_radius_m, steer_limit_rad and the fork travel exist in
  both model.sdf and config.yaml (SDF cannot be read as YAML); model.sdf is
  the named authority with a mechanical agreement check in the evidence. If
  invariant 10 is ever read strictly here, generate one file from the other.

## sim
- m4f-03 (in flight) — done when the arena + bringup run headless with every
  bridged topic at rate and cell.sdf untouched.
- m4f-08 (queued, after m4f-03/07) — done when the five scenarios are an
  owner-runnable procedure with an evidence checklist and a double rehearsal.
- Cell reskin (deferred, visual only, ARIAC licence blocker unchanged).
- M6 carried: resume the parked navigation scenario (sim/scenarios/DEFERRED.md).

## plc
- Fold into the next demo-cell plc brief: F6 (PresenceOnTimer.PT reads T#0MS
  after a CPU restart, likely §6.5's conditional call — diagnose, close or
  escalate); close SPEC §12 item 7 (rewrite-on-restart now delivered); T4.11
  reaction re-record with a per-session CSV; the §B2.9 "build B" three-delta
  label that three owner captures contradict (label only, no figure moves —
  shared with bridge); the demo-cell §4.3 "Nothing else goes into the
  interface." sentence, scope-stale after opcua-nodes §10.
- m4f-04c (issued) — done when plc/forklift/double/ runs SPEC §7
  statement-for-statement at 20 ms behind the §10 node surface, the four T5
  kernels demonstrated against it, spec ambiguities reported not fixed.
- Fold into the next forklift plc brief: SPEC §12 item 4's missing
  cross-reference to opcua-nodes §10.12 item 7 (cosmetic, m4f-04b).
- T4.11b stays blocked on bridge fault injection (below).
- M5/M9 carried: AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume
  of interrupted handshakes, dedicated F-I/O for SF-05/06/07.

## bridge
- Second witness for the masked-revert window (owner design decision,
  post-gate): a revert landing between the cycle's step-0 heartbeat read-back
  and step-4 write is erased and the restart goes undetected (~10 % of the
  cycle); both restart harnesses now trigger until one is caught and report
  the masked count (m4f-06). §8.1 rules that closing it needs a second
  witness; choosing one is the owner's.
- m4f-06b (issued) — done when bridge/config/rehearsal-forklift.yaml is
  committed, loader-validated, bridge.yaml byte-identical.
- Fault injection (SPEC §12 item 6; unblocks T4.11b): opt-in NaN/inf/
  out-of-window write that cannot be armed by accident in an evidence run.

## hmi
- m4f-07 (in flight; amended by owner direction) — done when the backend + UI
  run against the double with every write landing and the heartbeat stopping
  on kill, the UI carries the PLC-connection banner and the 5 Hz real-time
  metrics panel, and writes stay Hmi-only.

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
- Stale gate numbers across SRS.md, PL-SCENARIOS.md, plc/demo-cell/SPEC.md,
  sim/README.md, WSL_ENVIRONMENT.md, CREDITS.md, DEFERRED.md,
  bridge-design.md — inventory in docs/reports/m4r2-02-roadmap-renumber.md §3
  (README done by m4r2-04).
- README residue from m4r2-04: the architecture diagram and layer table
  predate the hmi/ layer; nothing distinguishes the M4 forklift plant from
  the RB-KAIROS vehicle (ADR 0008 D5); the M12 row keeps its short text.
- M12 Hermes: ADR 0008 D2.7 rules the operator layer for the local case only;
  the remaining m4-00 decisions stay open.

## publication
- Repository is public-ready and pushed; visibility is the owner's to flip.
  Residual, low: ADR 0007 names a hosting provider and region — an accepted
  ADR is never edited, so closing it needs a superseding ADR or owner
  acceptance as-is. Local commits since the push are unpushed until the owner
  pushes.

## carried forward, by gate
- interface (M9): the fleet-facing server interface's name is a contract
  decision (ADR 0006) — chosen deliberately at briefing, never discovered in
  TIA; opcua-nodes.md §2 still heads the fleet tree with http://DemoCell.
- plc/owner (later gate): suppress DataBlocksGlobal DB-level exposure by
  clearing each DB's "Accessible from HMI/OPC UA" attribute (opcua-nodes.md
  §9.8 open item).
- fleet (M8): confirm the handshake timeout constants.
