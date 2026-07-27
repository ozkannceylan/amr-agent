# TODO

## interface
- m3-03c bridge-design path corrections — done when bridge-design.md §1/§9.4/§10/§12 name bridge/ instead of fleet/bridge/, the fleet/README exception request is marked resolved by ADR 0005, and §9.2's L1 definition is amended to the slot-take hold time.

## plc
- m3-05 TIA implementation spec — done when the owner can build the program from plc/demo-cell/SPEC.md, including tag table, watch table, drive-fault handling of signal-loss case D, and PLCSIM notes.

## verifier
- m3-06 verify M3 — done when the container-side loop is independently re-run from committed instructions and the owner-executed remainder is stated explicitly.

## owner (open points, not delegated)
- PLC: implement the TIA Portal program and run PLCSIM Advanced; capture watch-table evidence for gate items (a) and (b) and the PLCSIM latency section of bridge/EVIDENCE_LATENCY.md.
- Hermes: define the component (repo, Telegram path, OPC UA client role) before M4 can be briefed.

## carried forward
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
