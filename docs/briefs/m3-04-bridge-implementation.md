gate:                M3
agent:               bridge
goal:                The bridge process implementing the approved design, proven bidirectional against the cell and an OPC UA test double.
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md, docs/interfaces/opcua-nodes.md section 9, docs/adr/0004, docs/adr/0005, sim/ cell world and launch]
deliverable:         bridge/ package: layer README, ROS 2 node + OPC UA client, pinned requirements, config file, OPC UA test double, evidence files
done_when:           In this container: the bridge connects to the test double, all six input nodes carry real cell samples, the speed command flows from the double into the cell and moves the product, the heartbeat obeys the startup rule, latency and update rate are measured by the bridge's own instrumentation and written to bridge/EVIDENCE_LATENCY.md with raw CSV, and each signal-loss case in the design is exercised and recorded.
forbidden:           [control logic, sequencing, interlocks, thresholds, latching, meaning-changing debounce, timers gating signals, re-issuing commands after an outage, writing nodes not marked client-writable, inverting server/client direction, editing directories other than bridge/ and the report]
