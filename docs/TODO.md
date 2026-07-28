# TODO


## owner (blocking)
- PLC program: BUILT AND VERIFIED 2026-07-27. FB_DemoCellControl (SCL) from OB30 at 20 ms, instance DB DemoCellControl_DB, CPU in RUN. Cold start read via asyncua without the bridge — BridgeLinkOk False, CellProcessStopActive True, CellResetRequired True, ConveyorSpeedCommand 0.0 — the specified behaviour, confirming wire-NC/program-NO and both latches before a bridge exists. This observation belongs in the gate evidence; capture it there rather than losing it to the chat log.
- PLC: run T1 to T4 end to end with the bridge pointed at opc.tcp://192.168.53.1:4840 and capture watch-table evidence for gate items (a) and (b) plus EVIDENCE_LATENCY.md Section B in full — item 5 covers all seven inputs, item 6 is the signal-loss repeat against the seven-node image (EVIDENCE_SIGNAL_LOSS.md has no separate PLCSIM section, per m3-23), and Section B also wants the CPU scan-cycle value and the invariant-8 network-path confirmation. No bridge work blocks this: m3-21 delivered the ServerInterfaces browse path and m3-23 verified it by re-running the harness.
- Hermes: define the component (which repo, how Telegram reaches it, what it may write over OPC UA) before M4 can be briefed.
- Clock: mitigated 2026-07-27, not durable. The resync + wsl --shutdown brought skew from ~3.7 s to inside the measurement bracket, but w32time is Stopped again — the fix was one-shot with nothing maintaining it, and the residual ~350 ppm re-accumulates to tens of seconds per day. Before the PLCSIM run either re-run the resync or, better, set the service to start: elevated `Set-Service w32time -StartupType Automatic; Start-Service w32time; w32tm /resync`.

## infra (fold into the next infra brief, do not issue alone)
- The root .gitattributes comment states a shebang-file count that is stale after m3-21 added bridge/tools/check_connect_conformance.py (7 should be 8, confirmed by m3-22) — correct the count or drop the number from the comment.

## owner (F1 — program defect, SPEC exonerated by m3-28)
- ProductPresentAtSensor never formed in the TIA build: the beam blocked six times at a constant 0.5400 m (inside the detect window) with the link and cycle up, yet the verdict stayed False in all 3,907 observer rows. Top hypotheses: PRESENT_THRESHOLD mis-entered, or a dead presence call site. ONE watch-table observation discriminates: block the beam and watch PresenceOnTimer.ET — if it counts up, the threshold path is fine and the verdict latch is dead; if it stays 0, the comparison never goes true (check the constant as entered). Note: T4.6b also depends on this fix — the step-20 dwell it freezes during is unreachable until presence detection works, so the m3-29 rebuild alone does not make it runnable.

## owner (spec changes landed after the program was built — re-implement in TIA)
- Case-D re-arm (m3-29, SPEC §6.6/§7 part 3): add static PositionFrozen (Bool, FALSE) and constant POSITION_WINDOW_TIME (T#1s); add temps windowRunning/windowExpired; change PositionWindowTimer PT to the new constant and add PosWindowArmed to its IN; replace the §7 part 3 window block so the verdict forms at expiry and PositionRef re-samples on the release call, both statics cleared in the ELSE; d2 := beltMoving AND PositionFrozen; add .PositionRef, .PositionFrozen, .PositionWindowTimer.ET to watch-table Group 4; do NOT add PositionFrozen to the reset clear list. Detection bound ≤3.2 s from freeze. Note: T4.7 is inverted — the monitored reset is now refused while the image still claims motion; restart the simulation first.
- Dwell timer: SPEC now calls it unconditionally outside the CASE with IN := (SeqStep = 20), because a call site inside branch 20 stops executing at step exit. The reported fix (IN := FALSE on leaving step 20) works only if that release executes in the same scan as the exit — confirm it does, or adopt the spec's form, so program and spec do not drift.
- Belt feedback plausibility (m3-27, SPEC §6.2.2): five constants, two statics, one temp, seven code sites. A NaN belt position currently disarms both soft-limit aborts in the built program. Adding statics reinitialises the instance DB, so ResetDeviceFault starts TRUE again and the reset contact must be seen open once. A healthy run should look identical after the change — anything faulting during a normal cycle means the constants are wrong, not the logic. Nothing in the bridge, the DBs, the 15 nodes or the server interface changes.

## plc (carried, needs a measurement not a decision)
- BELT_SPEED_MIN/MAX are design values at ±1.00 m/s with no measured drive maximum behind them. Confirm against the drive or the cell's achievable speed and record the source.

## plc
- m3-31 pass-string accounting (issued, from m3-30's open questions) — done when every §11 pass criterion counts the steps the section currently defines and none counts a failed or outstanding step by default.


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
