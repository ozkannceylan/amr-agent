# TODO


## owner (blocking)
- PLC: build the OB30 program per plc/demo-cell/SPEC.md — tags §3.2, then logic §6.1 onward — in the commissioned TIA V21 / PLCSIM Advanced V7 project; then run PLCSIM with the bridge pointed at opc.tcp://192.168.53.1:4840 and capture watch-table evidence for gate items (a) and (b), Section B of bridge/EVIDENCE_LATENCY.md and the PLCSIM section of bridge/EVIDENCE_SIGNAL_LOSS.md. Phase 0 (endpoint commissioning, 15 nodes read by an independent client) closed 2026-07-27.
- Hermes: define the component (which repo, how Telegram reaches it, what it may write over OPC UA) before M4 can be briefed.
- Clock: mitigated 2026-07-27, not durable. The resync + wsl --shutdown brought skew from ~3.7 s to inside the measurement bracket, but w32time is Stopped again — the fix was one-shot with nothing maintaining it, and the residual ~350 ppm re-accumulates to tens of seconds per day. Before the PLCSIM run either re-run the resync or, better, set the service to start: elevated `Set-Service w32time -StartupType Automatic; Start-Service w32time; w32tm /resync`.

## infra (fold into the next infra brief, do not issue alone)
- The root .gitattributes comment states a shebang-file count that is stale after m3-21 added bridge/tools/check_connect_conformance.py (7 should be 8, confirmed by m3-22) — correct the count or drop the number from the comment.

## verifier
- m3-23 commissioning-chain verification (issued) — done when every check in the brief carries a pass/fail with evidence, including the m3-18 §2.1 vs m3-19 §3.1 browse-path diff and a re-run of the connect-conformance harness, and the owner-executed remainder is stated explicitly.

## safety-spec
- m2-04 SRS reconciliation — not yet issued, from m2-03's findings. Done when the SRS §4 gate references match the ADR 0004 order (M9 safety, M5/M6 vehicle, M10 demonstration, M11 arm); SF-08 carries an architecture claim beside its PL c or states the inheritance; SF-03's bumper latch appears in §2's no-auto-resume list; and AT-01 gains the at-rest sub-test SC-02 observes (transfer refused with the latch set). One brief — the four items are one document's consistency.


## carried forward
- interface (M6): the fleet-facing server interface's NAME is now a contract decision — ADR 0006 derives the URI from it, so it must be chosen deliberately when M6 is briefed, not discovered in TIA. Until then opcua-nodes.md §2 still heads the fleet-facing folder tree with http://DemoCell (m3-18 open question); fix it in the same brief that fixes the name.
- plc/owner (later gate): suppress DataBlocksGlobal DB-level exposure by clearing each DB's "Accessible from HMI/OPC UA" attribute; recorded as an open item in opcua-nodes.md §9.8.
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
