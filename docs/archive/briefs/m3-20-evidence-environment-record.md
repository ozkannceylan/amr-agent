# Brief m3-20 — evidence files: commissioned-target environment record

gate:                M3
agent:               bridge
goal:                both bridge evidence files record the commissioned Windows/PLC stack as the target environment for the pending PLCSIM sections
invariants_touched:  none
inputs:              [bridge/EVIDENCE_LATENCY.md, bridge/EVIDENCE_SIGNAL_LOSS.md, the phase-0 facts below]
deliverable:         dated commissioned-environment subsections in bridge/EVIDENCE_LATENCY.md and bridge/EVIDENCE_SIGNAL_LOSS.md
done_when:           each file's environment section carries a dated phase-0 subsection with the facts below, clearly marked as the environment the owner-executed PLCSIM sections will run against, with existing container and WSL evidence untouched
forbidden:           [changing any measured figure or existing evidence section, editing bridge code or config, editing files outside bridge/, filling Section B or any PLCSIM measurement section (owner-executed), adding dependencies]

## Phase-0 commissioning facts (owner-verified in tool, 2026-07-27)

- TIA Portal V21; S7-PLCSIM Advanced V7.0 (V3.0 removed — broken virtual
  adapter service and unsupported with TIA V21).
- CPU 1513-1 PN, firmware V3.1, OPC UA runtime license "large" (compiler
  demanded large after the firmware change; small was not accepted).
- PLCSIM instance on TCP/IP Single Adapter, <Local>; instance IP
  192.168.53.1/24; host virtual adapter 192.168.53.241/24.
- OPC UA endpoint opc.tcp://192.168.53.1:4840, security None, anonymous
  access via CPU-level "Disable access control" (V3.x firmware has no
  guest-authentication checkbox).
- Browse path: Objects -> ServerInterfaces (Siemens namespace
  `http://www.siemens.com/simatic-s7-opcua`) -> DemoCell (namespace
  `http://DemoCell`).
- Session timeout observed clamped: requested 3600000 ms, granted 30000 ms.
- Independent verification 2026-07-27: 15 DemoCell nodes read with an
  asyncua client from Windows, all at start values. Bridge not involved.

State plainly in both subsections that phase 0 proves the endpoint and
node exposure only; no PLC program logic and no bridge involvement is
claimed by it.
