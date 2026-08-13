gate:                M1
agent:               interface
goal:                Document the OPC UA node model the PLC serves and the fleet manager consumes.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 3, 9 (naming: PascalCase, mirror PLC tags), docs/adr/0001]
deliverable:         docs/interfaces/opcua-nodes.md
done_when:           Every node for conveyor, door, charger and station handshake is listed with name, data type, access (read/write from client view), update semantics and owning side; PLC is server, fleet manager is client (invariant 4); no fleet-management data lives on the PLC (invariant 5); names are PascalCase physical+meaning.
forbidden:           [writing code, inverting the server/client direction, placing order/traffic data on the PLC, editing other directories]
