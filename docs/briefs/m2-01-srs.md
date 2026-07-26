gate:                M2
agent:               safety-spec
goal:                Safety requirements spec where every safety function has a trigger, a reaction and an acceptance test.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2 (invariants 1, 2, 7), 3, 9, docs/interfaces/opcua-nodes.md (informational safety mirrors), docs/interfaces/handshake-tables.md, docs/adr/0002 (platform, arm out of scope until M9)]
deliverable:         docs/safety/SRS.md
done_when:           Each safety function has: ID, trigger, reaction with performance target, safe state, reset behavior (monitored, edge-triggered, manual), and one verifiable acceptance test executable against PLCSIM Advanced + simulation; the wire-NC/program-NO and edge-vs-level conventions are stated; the network-loss boundary is explicit (degraded mode, handled outside the safety program).
forbidden:           [writing code or F-logic, redefining interface contracts, putting any safety function on MQTT/OPC UA, covering arm safety functions (M9), editing other directories]
