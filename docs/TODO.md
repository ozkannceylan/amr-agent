# TODO


## owner (blocking)
- PLC: build the OB30 program per plc/demo-cell/SPEC.md — tags §3.2, then logic §6.1 onward — in the commissioned TIA V21 / PLCSIM Advanced V7 project; then run PLCSIM with the bridge pointed at opc.tcp://192.168.53.1:4840 and capture watch-table evidence for gate items (a) and (b) plus EVIDENCE_LATENCY.md Section B in full — item 5 covers all seven inputs, item 6 is the signal-loss repeat against the seven-node image (EVIDENCE_SIGNAL_LOSS.md has no separate PLCSIM section, per m3-23), and Section B also wants the CPU scan-cycle value and the invariant-8 network-path confirmation. Phase 0 closed 2026-07-27; bridge connect conformance verified by m3-23.
- Hermes: define the component (which repo, how Telegram reaches it, what it may write over OPC UA) before M4 can be briefed.
- Clock: mitigated 2026-07-27, not durable. The resync + wsl --shutdown brought skew from ~3.7 s to inside the measurement bracket, but w32time is Stopped again — the fix was one-shot with nothing maintaining it, and the residual ~350 ppm re-accumulates to tens of seconds per day. Before the PLCSIM run either re-run the resync or, better, set the service to start: elevated `Set-Service w32time -StartupType Automatic; Start-Service w32time; w32tm /resync`.

## infra (fold into the next infra brief, do not issue alone)
- The root .gitattributes comment states a shebang-file count that is stale after m3-21 added bridge/tools/check_connect_conformance.py (7 should be 8, confirmed by m3-22) — correct the count or drop the number from the comment.

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
