# TODO

## owner (blocking)
- PLC: implement the TIA Portal program and run PLCSIM Advanced; capture watch-table evidence for gate items (a) and (b) and fill Section B of bridge/EVIDENCE_LATENCY.md. Do not start before m3-12 lands — SPEC.md still specifies the superseded conflated reset.
- Hermes: define the component (which repo, how Telegram reaches it, what it may write over OPC UA) before M4 can be briefed.
- Clock: resolved 2026-07-27. w32tm /resync run elevated and wsl --shutdown performed; measured host-guest skew fell from ~3.7 s to ~0.3 s. Re-check with a fresh measurement immediately before the PLCSIM gate run.

## infra
- m3-07 WSL environment rebuild — in progress, unblocked. Gazebo Sim 8.11.0 is installed via the ROS vendor packages, so investigations 1 and 7 can now be answered. Done when the gz version and the headless behaviour are recorded against a real install.
- m3-08 WSL loop re-run — not yet issued, blocked on m3-07. Done when the cell, test double and bridge loop from bridge/README.md is re-run under WSL and WSL evidence sections are appended without disturbing the container evidence.

## safety-spec
- m2-03 ISO 13849 scenario document — issued 2026-07-27, in progress. Owner ruled this the presentation centrepiece. Done when docs/safety/PL-SCENARIOS.md carries at least 10 scenarios, each with hazard, S/F/P risk-graph derivation to PLr, covering SF, category claim, 13849-2-style validation test and AT mapping, under the SRS §5 honesty frame.

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
