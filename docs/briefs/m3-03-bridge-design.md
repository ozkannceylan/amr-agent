gate:                M3
agent:               fleet
goal:                A bridge design document that precedes any bridge code.
invariants_touched:  none
inputs:              [docs/adr/0004, docs/interfaces/opcua-nodes.md (after m3-02), sim signal table from m3-01, CLAUDE.md invariants 4, 5, 6, 9, 11]
deliverable:         docs/interfaces/bridge-design.md
done_when:           The document states: the bridge is an OPC UA client and a ROS 2 node, nothing else; a signal map table (ROS 2 topic ↔ OPC UA node, direction, type, conversion); the update model (poll or subscribe, rate, and why); the explicit no-logic rule with examples of what would be a violation (sequencing, interlock, timer, debounce that changes meaning); startup and reconnect behaviour; what the PLC observes when the bridge stops (heartbeat/liveness node semantics) and what the equipment must do, so the PLC program can be written against it; measurement method for latency and update rate; failure and restart behaviour with no auto-resume of equipment.
forbidden:           [writing code, adding dependencies without listing them for owner approval in the report, defining control logic, editing directories other than docs/interfaces/ and the report]
