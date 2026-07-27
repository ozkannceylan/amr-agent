# TODO

## owner (blocking)
- PLC: implement the TIA Portal program and run PLCSIM Advanced; capture watch-table evidence for gate items (a) and (b) and fill Section B of bridge/EVIDENCE_LATENCY.md. Do not start before m3-12 lands — SPEC.md still specifies the superseded conflated reset.
- Hermes: define the component (which repo, how Telegram reaches it, what it may write over OPC UA) before M4 can be briefed.
- Clock: mitigated 2026-07-27, not durable. The resync + wsl --shutdown brought skew from ~3.7 s to inside the measurement bracket, but w32time is Stopped again — the fix was one-shot with nothing maintaining it, and the residual ~350 ppm re-accumulates to tens of seconds per day. Before the PLCSIM run either re-run the resync or, better, set the service to start: elevated `Set-Service w32time -StartupType Automatic; Start-Service w32time; w32tm /resync`.

## interface + sim (issued as follow-ups 2026-07-27, from m3-06 finding 2)
- Superseded "hold time" reset wording survives in five places: opcua-nodes.md §9.3 and §9.5, bridge-design.md §5 map row (interface), sim/README.md twice (sim). Done when all five match the delivered edge-triggered reset and SPEC.md §6.7, which times nothing.

## bridge (issued as follow-up 2026-07-27, from m3-06 finding 3)
- L6 scenario dependence. The committed 4.000 ms figure is a JointController property that the verifier measured at 2.000 ms from rest and 1384 ms reversing off the mechanical stop; no document states the dependence. Done when EVIDENCE_LATENCY.md Section C carries a dated note citing the m3-06 report.

## safety-spec
- m2-04 SRS reconciliation — not yet issued, from m2-03's findings. Done when the SRS §4 gate references match the ADR 0004 order (M9 safety, M5/M6 vehicle, M10 demonstration, M11 arm); SF-08 carries an architecture claim beside its PL c or states the inheritance; SF-03's bumper latch appears in §2's no-auto-resume list; and AT-01 gains the at-rest sub-test SC-02 observes (transfer refused with the latch set). One brief — the four items are one document's consistency.

## interface
- opcua-nodes.md §9.3 reset row still says the PLC "times the hold" — one stale phrase from the superseded gesture design, found by m3-12. Done when the phrase matches the delivered edge-triggered reset. Fold into the next interface brief rather than issuing alone.


## carried forward
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
