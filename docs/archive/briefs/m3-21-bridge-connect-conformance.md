# Brief m3-21 — bridge connect conformance to the commissioned server

gate:                M3
agent:               bridge
goal:                the bridge client resolves the commissioned ServerInterfaces browse path via both namespace URIs and derives keep-alive from the granted session timeout, proven against the test double
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md (as revised by m3-19), docs/interfaces/opcua-nodes.md (as revised by m3-18), bridge/]
deliverable:         bridge client connect logic (and the test double, extended to serve the Siemens-shaped path) conformant with the revised design
done_when:           a recorded test-double run shows the client resolving both namespaces by URI under Objects/ServerInterfaces/DemoCell with no hard-coded namespace index, and logging a keep-alive interval derived from a granted session timeout the double deliberately clamps below the requested value
forbidden:           [adding process logic to the bridge (thresholds, latches, timers beyond connection keep-alive, sequencing, interlocks), editing files outside bridge/, changing docs/interfaces/, adding dependencies, connecting to the live PLCSIM endpoint (owner-executed)]

## Context

Phase-0 commissioning (2026-07-27) established: browse path
Objects -> ServerInterfaces (`http://www.siemens.com/simatic-s7-opcua`)
-> DemoCell (`http://DemoCell`); the S7-1500 clamps session timeouts
(3600000 ms requested, 30000 ms granted). The live config namespace move
landed in commit 50621cd. This brief brings the connect logic and the
test double into line so the owner's next run needs no bridge-side
surprises. Verify current behaviour first; change only what the revised
design requires. Runs execute in WSL from the committed instructions.
