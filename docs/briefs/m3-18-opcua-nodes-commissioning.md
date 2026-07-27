# Brief m3-18 — opcua-nodes.md commissioning corrections

gate:                M3
agent:               interface
goal:                opcua-nodes.md states the commissioned server's real browse path, scopes its node-count claim to the DemoCell interface, and records the verified endpoint facts
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md, docs/adr/ (ADR 0006), docs/interfaces/bridge-design.md (read only), the phase-0 facts below]
deliverable:         docs/interfaces/opcua-nodes.md
done_when:           the four items below are each verifiable in the document, and an independent whitespace-normalised sweep finds no surviving statement that assumes DemoCell sits directly under Objects, that a requested session parameter is honored as requested, or that the server exposes only the interface nodes
forbidden:           [editing bridge-design.md or any other file, writing code, editing bridge/ or plc/, adding dependencies, inventing values not in this brief]

## Phase-0 commissioning facts (owner-verified in tool, 2026-07-27)

These are measured facts from a running system, not proposals.

1. **Browse path.** DemoCell is NOT directly under Objects. The path is
   Objects -> ServerInterfaces (Siemens namespace
   `http://www.siemens.com/simatic-s7-opcua`) -> DemoCell (namespace
   `http://DemoCell`). Any client must resolve BOTH namespace indices by
   URI at connect time and must never assume the parent folder shares the
   interface namespace. State this in the browse-path / addressing section.

2. **Node-count claim, §9.8.** Siemens auto-publishes all DBs under
   DataBlocksGlobal in its own namespace, so "exactly 15 nodes visible"
   is false as stated. Scope the claim to the DemoCell server interface
   ("exactly 15 nodes under the DemoCell interface") and add an open item:
   suppress DB-level exposure via per-DB "Accessible from HMI/OPC UA"
   flags at a later gate.

3. **Verified environment record.** Add a dated commissioned-environment
   subsection recording: TIA Portal V21; S7-PLCSIM Advanced V7.0 (V3.0
   removed — broken virtual adapter service and unsupported with TIA V21);
   CPU 1513-1 PN firmware V3.1; OPC UA runtime license "large" (compiler
   demanded large after the firmware change); PLCSIM instance on TCP/IP
   Single Adapter <Local>, instance IP 192.168.53.1/24, host virtual
   adapter 192.168.53.241/24; endpoint opc.tcp://192.168.53.1:4840,
   security None, anonymous access via CPU-level "Disable access control"
   (V3.x firmware has no guest-authentication checkbox; disabling access
   control grants the Anonymous user full rights including OPC UA);
   independently verified 2026-07-27 by an asyncua client from Windows
   reading all 15 DemoCell nodes at start values, bridge not involved.

4. **Residual check.** Verify no reset row still says the PLC "times the
   hold" (superseded edge-triggered reset, m3-12); fix if found.

Location lists above are starting points, not exhaustive — verify by
independent search (LESSONS 2026-07-27).
