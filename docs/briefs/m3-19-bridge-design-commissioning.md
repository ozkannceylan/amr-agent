# Brief m3-19 — bridge-design.md commissioning corrections

gate:                M3
agent:               interface
goal:                the bridge design requires connect-time resolution of both server namespaces by URI and derives keep-alive from the granted, not requested, session timeout
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md, docs/adr/ (ADR 0006), the phase-0 facts below]
deliverable:         docs/interfaces/bridge-design.md
done_when:           the design's connect sequence states both requirements below as normative, and an independent whitespace-normalised sweep finds no surviving statement assuming DemoCell hangs directly under Objects or that a requested session parameter is honored as requested
forbidden:           [editing opcua-nodes.md or any other file, writing or changing bridge code or config, adding logic to the bridge design (thresholds, latches, timers, sequencing, interlocks), adding dependencies]

## Phase-0 commissioning facts (owner-verified in tool, 2026-07-27)

1. **Namespace resolution at connect.** The commissioned browse path is
   Objects -> ServerInterfaces (Siemens namespace
   `http://www.siemens.com/simatic-s7-opcua`) -> DemoCell (namespace
   `http://DemoCell`). The bridge must resolve BOTH namespaces by URI at
   connect time (never by hard-coded index) and must never assume the
   parent folder shares the interface namespace.

2. **Session timeout clamp.** The S7-1500 clamps the session timeout: a
   requested 3600000 ms was granted as 30000 ms. The bridge must read the
   granted (revised) session timeout from the connect response and derive
   its keep-alive interval from that value; it must never assume its
   request was honored.

Both are connection-management requirements, not process logic; they
belong in the connect/reconnect section of the design. Location hints are
starting points, not exhaustive — verify by independent search (LESSONS
2026-07-27). If the design's signal-loss or reconnect cases quote timeout
numbers derived from the old assumption, update them to reference the
granted value.
