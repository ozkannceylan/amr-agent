# TODO


## owner (blocking)
- PLC: build the OB30 program per plc/demo-cell/SPEC.md — tags §3.2, then logic §6.1 onward — in the commissioned TIA V21 / PLCSIM Advanced V7 project; then run PLCSIM with the bridge pointed at opc.tcp://192.168.53.1:4840 and capture watch-table evidence for gate items (a) and (b), Section B of bridge/EVIDENCE_LATENCY.md and the PLCSIM section of bridge/EVIDENCE_SIGNAL_LOSS.md. Phase 0 (endpoint commissioning, 15 nodes read by an independent client) closed 2026-07-27.
- Hermes: define the component (which repo, how Telegram reaches it, what it may write over OPC UA) before M4 can be briefed.
- Clock: mitigated 2026-07-27, not durable. The resync + wsl --shutdown brought skew from ~3.7 s to inside the measurement bracket, but w32time is Stopped again — the fix was one-shot with nothing maintaining it, and the residual ~350 ppm re-accumulates to tens of seconds per day. Before the PLCSIM run either re-run the resync or, better, set the service to start: elevated `Set-Service w32time -StartupType Automatic; Start-Service w32time; w32tm /resync`.

## interface
- m3-18 opcua-nodes commissioning corrections — done when the ServerInterfaces browse path with both namespace URIs is stated, §9.8's node-count claim is scoped to the DemoCell interface with the DataBlocksGlobal open item recorded, the dated commissioned-environment facts are in the document, and no "times the hold" phrasing survives.
- m3-19 bridge-design commissioning corrections — done when the connect sequence normatively requires resolving both namespaces by URI and deriving keep-alive from the granted (clamped) session timeout.

## bridge
- m3-20 evidence environment record — done when both EVIDENCE files carry the dated commissioned-stack subsection, marked as proving endpoint and node exposure only.
- m3-21 connect conformance (blocked on m3-19) — done when a recorded test-double run shows both namespaces resolved by URI under ServerInterfaces and keep-alive derived from a deliberately clamped granted session timeout.

## safety-spec
- m2-04 SRS reconciliation — not yet issued, from m2-03's findings. Done when the SRS §4 gate references match the ADR 0004 order (M9 safety, M5/M6 vehicle, M10 demonstration, M11 arm); SF-08 carries an architecture claim beside its PL c or states the inheritance; SF-03's bumper latch appears in §2's no-auto-resume list; and AT-01 gains the at-rest sub-test SC-02 observes (transfer refused with the latch set). One brief — the four items are one document's consistency.


## carried forward
- interface (M6): the fleet-facing server interface's NAME is now a contract decision — ADR 0006 derives the URI from it, so it must be chosen deliberately when M6 is briefed, not discovered in TIA.
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
