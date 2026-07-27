gate:                M3
agent:               arch-docs
goal:                Record the bridge as its own top level layer, and the asyncua dependency, as an accepted ADR.
invariants_touched:  none
inputs:              [docs/adr/0004, docs/interfaces/bridge-design.md, docs/reports/m3-03-bridge-design.md, CLAUDE.md sections 2, 4, 8]
deliverable:         docs/adr/0005-bridge-layer-and-opcua-client.md
done_when:           ADR follows the section 8 format, status accepted, and records two decisions with their consequences: the bridge lives at top level bridge/ rather than inside fleet/, and asyncua is the OPC UA client and test double library, pinned, with its licence stated.
forbidden:           [changing any invariant, editing ADR 0001-0004, writing code, editing directories other than docs/adr/ and the report]
