# TODO

## infra
- m3-07 WSL environment rebuild — issued 2026-07-27, in progress. Done when sim/setup/WSL_ENVIRONMENT.md lets a clean WSL Ubuntu reach ROS 2 Jazzy + Gazebo Harmonic + asyncua 2.0.1 importing in one interpreter, with every command's real output quoted.
- m3-08 WSL loop re-run — not yet issued, blocked on m3-07. Done when the cell, test double and bridge loop from bridge/README.md is re-run under WSL and WSL evidence sections are appended without disturbing the container evidence.

## interface
- m3-03d bridge-design residual staleness — not yet issued, deliberately held until m3-05 stops reading the file. Done when §9.4 names the delivered artefact latency-<date>.csv.gz rather than .csv, and §12 open item 7 (20 Hz cadence) is marked closed to match EVIDENCE_LATENCY.md §A.4, which records the expectation met with 0 overruns.

## plc
- m3-05 TIA implementation spec — issued 2026-07-27, in progress. Done when the owner can build the program from plc/demo-cell/SPEC.md, including tag table, watch table, drive-fault handling of signal-loss case D, PLCSIM notes, and an explicit statement that ConveyorSpeedCommand is a gated Real setpoint rather than a coil.

## verifier
- m3-06 verify M3 — done when the container-side loop is independently re-run from committed instructions and the owner-executed remainder is stated explicitly.

## owner (open points, not delegated)
- PLC: implement the TIA Portal program and run PLCSIM Advanced; capture watch-table evidence for gate items (a) and (b) and the PLCSIM latency section of bridge/EVIDENCE_LATENCY.md.
- Hermes: define the component (repo, Telegram path, OPC UA client role) before M4 can be briefed.

## carried forward
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
