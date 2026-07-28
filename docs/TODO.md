# TODO

## publication — BLOCKED, owner decisions required (pub-01, 2026-07-28)
The repository is still PRIVATE on GitHub with 53 commits unpushed, so nothing
has leaked. Verdict is no-go until these are settled; full detail and ten
decisions in docs/reports/pub-01-public-readiness-audit.md.
- BLOCKER 1: docs/reports/m4-00-hermes-survey.md details the owner's other private infrastructure (provider, region, host and tailnet node names, co-tenant stacks, deploy chain, a table of where each secret lives, GitHub Secret names, which controls are untested, fail-open mechanisms, a route-to-the-PLC checklist). Present in two committed revisions (58718d2, c7d1b29), so deleting it at HEAD is not enough. Decide: history rewrite (filter-repo + force-push, safe while private and unpushed) or a fresh-history public repo. Identifiers have also spread to docs/TODO.md, docs/briefs/m4r-01 and — immutably — docs/adr/0007.
- BLOCKER 2: no LICENSE at any path. Choose MIT (portfolio default) or Apache-2.0 (better if employer adoption is likely).
- BLOCKER 3: plc/demo-cell/evidence/watch-table/"Screenshot 2026-07-28 144116.png" is a full-desktop capture including the personal taskbar; only 3 of 71 captures were sampled, so the set is not certified clean.
- BLOCKER 4 (owner call): §7's spirit — two committed absolute paths into a named tool's scratch directory with a session UUID (docs/reports/m3-26:96, docs/briefs/pub-02:15), plus the structural disclosure of CLAUDE.md, .claude/settings.json and ten agent files carrying a vendor model id. Decide whether the agentic working model is part of the portfolio story or is stripped before publication.


## owner (blocking)
- PLC program: BUILT AND VERIFIED 2026-07-27. FB_DemoCellControl (SCL) from OB30 at 20 ms, instance DB DemoCellControl_DB, CPU in RUN. Cold start read via asyncua without the bridge — BridgeLinkOk False, CellProcessStopActive True, CellResetRequired True, ConveyorSpeedCommand 0.0 — the specified behaviour, confirming wire-NC/program-NO and both latches before a bridge exists. This observation belongs in the gate evidence; capture it there rather than losing it to the chat log.
- PLC: run T1 to T4 end to end with the bridge pointed at opc.tcp://192.168.53.1:4840 and capture watch-table evidence for gate items (a) and (b) plus EVIDENCE_LATENCY.md Section B in full — item 5 covers all seven inputs, item 6 is the signal-loss repeat against the seven-node image (EVIDENCE_SIGNAL_LOSS.md has no separate PLCSIM section, per m3-23), and Section B also wants the CPU scan-cycle value and the invariant-8 network-path confirmation. No bridge work blocks this: m3-21 delivered the ServerInterfaces browse path and m3-23 verified it by re-running the harness.
- Hermes: m4-00 survey done 2026-07-28, revised same day against the real repository, github.com/ozkannceylan/hermes-assistant at fd645b8 (docs/reports/m4-00-hermes-survey.md, ten decisions; the rookie-assistant findings are §9, superseded). Hermes is NousResearch hermes-agent (Python 3.13, pinned v2026.7.7.2) on the inherited Rookie VPS/tailnet. Decisions before M4 is briefed, headline five: (1) rule invariant 8 — Hermes holds the OPC UA client over the tailnet, or the tailnet carries intent only and a cell-side executor writes; note the framework's SSRF guard blocks RFC1918 and the Tailscale CGNAT range for its web tool, so any Hermes-side path is terminal/binary-shaped regardless; (2) rule what "Telegram-triggered" means — Hermes runs ten cron jobs, a 6-hourly heartbeat and subagents, so a command need not have a human in the loop; (3) ADR 0004's "same server" premise is contradicted by the deployment (Hetzner box vs laptop PLC); (4) the Command node group must be designed — no existing node may legitimately take a command; (5) topology has no operator/AI-assistant box, placement needs an ADR. Integration code should NOT live in hermes-assistant: the agent pushes to the repository that deploys it, gated only by gitleaks. Caveat for all future briefs: no checkout is authoritative about what the VPS runs (the repo's synced config already disagrees with the deploy-managed one).
- Clock: mitigated 2026-07-27, not durable. The resync + wsl --shutdown brought skew from ~3.7 s to inside the measurement bracket, but w32time is Stopped again — the fix was one-shot with nothing maintaining it, and the residual ~350 ppm re-accumulates to tens of seconds per day. Before the PLCSIM run either re-run the resync or, better, set the service to start: elevated `Set-Service w32time -StartupType Automatic; Start-Service w32time; w32tm /resync`.

## infra (fold into the next infra brief, do not issue alone)
- The root .gitattributes comment states a shebang-file count that is stale after m3-21 added bridge/tools/check_connect_conformance.py (7 should be 8, confirmed by m3-22) — correct the count or drop the number from the comment.

## owner (F1 — RESOLVED 2026-07-28, one durability step left)
- Root cause found live: PresenceOnTimer's PT in force was T#1M_40S (100 s) against the spec's 100 ms — the watch table exposed it while the interface default read T#100ms. After the owner's fix a full cycle ran clean on the live loop: reset, start, ProductPresentAtSensor True 3 s after start, dwell, cycle complete, no soft-limit abort, no reset required. Durability step: confirm the fix is an explicit PT := T#100MS at the call site (an instance-DB-only correction dies at the next reinitialisation), and capture the corrected build as the rebuild baseline. F1's resolution unlocks T1.4, T2.2-2.4 and T4.6b.

## bridge (new finding, 2026-07-28 live session)
- Reconnect path does not catch exceptions from in-flight requests: when the CPU download dropped the session mid-read, run_bridge died on an unhandled exception in _output_path instead of reconnecting. Done when an in-flight request failure routes into the §8.1 reconnect path and a bounce-during-read test proves it against the test double.

## live run 2026-07-28 — COMPLETE (agent-drivable part)
- T1 6/6 rerun with the real 100 ms filter; T2 8/8; T4: 4.1-4.4 ✓, 4.5 ✓ (STOP/RUN, plus the write-cache finding), 4.6 ✓ re-measured 2.79 s freeze-to-fault (inside the 2.1-3.2 s bound, 20 Hz CSV), 4.6b ✓ (D1 ~1 s), 4.7 ✓ (reset refused while image claims motion, honoured after revive), 4.8 ✓ (R3 proven input by input), 4.9 ✓, 4.9b FAILED with finding (link boot polarity), 4.10 ✓ (SIGKILL ~22 s hold vs SIGTERM immediate), 4.11 reaction path ✓ / latch step untestable as specified (finding). Cycle times: 1.004/1.023/2.556 ms on a 20 ms OB30. Rebuild baseline SPEC @ 39a21b6 + the three-delta and PT-fix downloads. Raw artifacts committed in bridge/evidence/*2026-07-28*.

## owner (m3-34 delta — SPEC §6.8, re-implement in TIA)
- Add static HeartbeatSeenAlive : Bool := FALSE; latch it on the first observed heartbeat change; AND it into the BridgeLinkOk verdict. Replace ResetDeviceFault's single-branch clear with the per-link-session re-arm form (re-armed whenever BridgeLinkOk is FALSE). Add the new static to watch-table Group 4. Then verify green diff circles and the in-force PTs BEFORE testing, and re-run §11 4.2, 4.3, 4.5, 4.8 and 4.9b against the rebuild — the corrected cold-start signature reads CellProcessStopActive FALSE at boot (deliberate change, documented in SPEC).

## bridge
- m3-35 session-lifecycle conformance (issued) — done when a recorded double run proves reconnect-on-in-flight-failure, full slot rewrite on server restart, and per-session evidence CSVs. When it lands, reconcile EVIDENCE_LATENCY §B2.12 rows 20-21 (written as open requests) in the same commit.
- Fault injection (SPEC §12 item 6, blocks T4.11b) — opt-in mode that writes a nominated DemoCell/Input Real as NaN/inf/out-of-window; cannot be enabled by accident in an evidence run. Brief after m3-35 lands (same files).

## plc (fold into the next plc brief)
- F6 (m3-33, §B2.12 row 22): PresenceOnTimer.PT reads T#100MS before a CPU restart and T#0MS after, in five captures. Likely the §6.5-blessed conditional call site: at boot range=0.0 is implausible, rangeValid is FALSE, the presence call never executes, so PT shows the DB start value until the first valid range — diagnose against §6.5 and close or escalate.

## owner (M4 pre-gate feasibility, ADR 0007's tool question — do in TIA while M3 closes)
- Does this install run an F-CPU on PLCSIM Advanced V7? Check: STEP 7 Safety Advanced V21 license present; 1513F-1 PN addable from the catalogue; an empty F-project compiles and downloads to a PLCSIM instance and reaches RUN with the F-runtime group executing; what F-I/O the catalogue offers and whether PLCSIM accepts it. The answers are the input to M4's first brief — the tool rules, not the spec (phase-0 lesson).

## owner (spec changes landed after the program was built — re-implement in TIA)
- Case-D re-arm (m3-29, SPEC §6.6/§7 part 3): add static PositionFrozen (Bool, FALSE) and constant POSITION_WINDOW_TIME (T#1s); add temps windowRunning/windowExpired; change PositionWindowTimer PT to the new constant and add PosWindowArmed to its IN; replace the §7 part 3 window block so the verdict forms at expiry and PositionRef re-samples on the release call, both statics cleared in the ELSE; d2 := beltMoving AND PositionFrozen; add .PositionRef, .PositionFrozen, .PositionWindowTimer.ET to watch-table Group 4; do NOT add PositionFrozen to the reset clear list. Detection bound ≤3.2 s from freeze. Note: T4.7 is inverted — the monitored reset is now refused while the image still claims motion; restart the simulation first.
- Dwell timer: SPEC now calls it unconditionally outside the CASE with IN := (SeqStep = 20), because a call site inside branch 20 stops executing at step exit. The reported fix (IN := FALSE on leaving step 20) works only if that release executes in the same scan as the exit — confirm it does, or adopt the spec's form, so program and spec do not drift.
- Belt feedback plausibility (m3-27, SPEC §6.2.2): five constants, two statics, one temp, seven code sites. A NaN belt position currently disarms both soft-limit aborts in the built program. Adding statics reinitialises the instance DB, so ResetDeviceFault starts TRUE again and the reset contact must be seen open once. A healthy run should look identical after the change — anything faulting during a normal cycle means the constants are wrong, not the logic. Nothing in the bridge, the DBs, the 15 nodes or the server interface changes.

## plc (carried, needs a measurement not a decision)
- BELT_SPEED_MIN/MAX are design values at ±1.00 m/s with no measured drive maximum behind them. Confirm against the drive or the cell's achievable speed and record the source.


## bridge (from m3-27, SPEC §12 open item 6)
- Opt-in fault-injection mode: a genuine NaN cannot currently be injected from the cell, so SPEC §11 step 4.11 has to exercise the belt-feedback path by narrowing a constant instead. Done when the bridge can inject an implausible or NaN belt sample under an explicit opt-in that cannot be enabled by accident in an evidence run.

## sim (deferred, after M3 closes — do not start before the owner's evidence lands)
- Cell reskin from harvested assets. Research (2026-07-27, scratchpad sim-research.md) recommends harvesting ARIAC 2025 conveyor/break-beam visuals onto the existing joints, optionally placing the cell inside Fuel Depot (CC-BY 4.0). Visual only: the /cell/... topic contract and the node model must not change. Blocker to resolve first — ariac_gz, the package holding every mesh, declares "TODO: License declaration" and the repo has no top-level LICENSE; NIST's only terms statement is a US-only §105 non-copyright note, so clarify terms with the maintainers before any mesh enters this repository. Adopting ARIAC's own plugins is out of scope: it would add ariac_interfaces and change the signal contract, which needs an ADR.

## safety-spec
- m2-04 SRS reconciliation — not yet issued, from m2-03's findings. Done when the SRS §4 gate references match the ADR 0004 order (M9 safety, M5/M6 vehicle, M10 demonstration, M11 arm); SF-08 carries an architecture claim beside its PL c or states the inheritance; SF-03's bumper latch appears in §2's no-auto-resume list; and AT-01 gains the at-rest sub-test SC-02 observes (transfer refused with the latch set). One brief — the four items are one document's consistency.


## carried forward
- interface (M6): the fleet-facing server interface's NAME is now a contract decision — ADR 0006 derives the URI from it, so it must be chosen deliberately when M6 is briefed, not discovered in TIA. Until then opcua-nodes.md §2 still heads the fleet-facing folder tree with http://DemoCell (m3-18 open question); fix it in the same brief that fixes the name.
- plc/owner (later gate): suppress DataBlocksGlobal DB-level exposure by clearing each DB's "Accessible from HMI/OPC UA" attribute; recorded as an open item in opcua-nodes.md §9.8.
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
