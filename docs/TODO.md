# TODO

## sim
- m3-01 fixed equipment world — done when conveyor, product sensor and operator panel run headless in Gazebo with a documented ROS 2 signal table and captured evidence.

## interface
- m3-02 cell I/O nodes — done when every m3-01 signal has an OPC UA node mirroring its PLC tag, with direction and single owner, and the demo e-stop is labelled a process stop.

## bridge
- m3-04 bridge implementation — done when signals traverse both directions against the cell and an OPC UA test double, with measured latency and exercised signal-loss cases.

## plc
- m3-05 TIA implementation spec — done when the owner can build the program from plc/demo-cell/SPEC.md, including watch table and PLCSIM notes.

## verifier
- m3-06 verify M3 — done when the container-side loop is independently re-run and the owner-executed remainder is stated explicitly.

## carried forward
- fleet (M7): confirm handshake timeout constants.
- plc (M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
- sim (M5): resume the parked navigation scenario (sim/scenarios/DEFERRED.md).
