# TODO

## owner (blocking)
- PLC: implement the TIA Portal program and run PLCSIM Advanced; capture watch-table evidence for gate items (a) and (b) and fill Section B of bridge/EVIDENCE_LATENCY.md. Do not start before m3-12 lands — SPEC.md still specifies the superseded conflated reset.
- Hermes: define the component (which repo, how Telegram reaches it, what it may write over OPC UA) before M4 can be briefed.
- Clock: mitigated 2026-07-27, not durable. The resync + wsl --shutdown brought skew from ~3.7 s to inside the measurement bracket, but w32time is Stopped again — the fix was one-shot with nothing maintaining it, and the residual ~350 ppm re-accumulates to tens of seconds per day. Before the PLCSIM run either re-run the resync or, better, set the service to start: elevated `Set-Service w32time -StartupType Automatic; Start-Service w32time; w32tm /resync`.

## infra
- m3-07 WSL environment rebuild — in progress, unblocked. Gazebo Sim 8.11.0 is installed via the ROS vendor packages, so investigations 1 and 7 can now be answered. Done when the gz version and the headless behaviour are recorded against a real install.
- m3-08 WSL loop re-run — not yet issued, blocked on m3-07. Done when the cell, test double and bridge loop from bridge/README.md is re-run under WSL and WSL evidence sections are appended without disturbing the container evidence.

## safety-spec
- m2-04 SRS reconciliation — not yet issued, from m2-03's findings. Done when the SRS §4 gate references match the ADR 0004 order (M9 safety, M5/M6 vehicle, M10 demonstration, M11 arm); SF-08 carries an architecture claim beside its PL c or states the inheritance; SF-03's bumper latch appears in §2's no-auto-resume list; and AT-01 gains the at-rest sub-test SC-02 observes (transfer refused with the latch set). One brief — the four items are one document's consistency.

## interface
- opcua-nodes.md §9.3 reset row still says the PLC "times the hold" — one stale phrase from the superseded gesture design, found by m3-12. Done when the phrase matches the delivered edge-triggered reset. Fold into the next interface brief rather than issuing alone.

## infra (small, in progress with the m3-09 agent)
- .gitignore entry for bridge/evidence/latency-latest.csv, the run artefact the new committed default produces. Done when check-ignore resolves to a repo rule and the committed .gz evidence stays tracked.
- sim/setup/WSL_ENVIRONMENT.md §5 items 1 and 2 — resolved by 994a929, being marked so in place by the m3-07 agent.

## verifier
- m3-06 verify M3 — done when the loop is independently re-run from committed instructions and the owner-executed remainder is stated explicitly. Run last, after m3-12 and m3-03e.

## carried forward
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
