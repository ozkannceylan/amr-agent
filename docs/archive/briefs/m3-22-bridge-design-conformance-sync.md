# Brief m3-22 — bridge-design.md sync after connect conformance

gate:                M3
agent:               interface
goal:                bridge-design.md reflects that the connect conformance it required has been delivered and evidenced
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md, docs/reports/m3-21-bridge-connect-conformance.md, bridge/EVIDENCE_CONNECT.md (read only)]
deliverable:         docs/interfaces/bridge-design.md
done_when:           §12 item 9 is marked resolved by the m3-21 delivery, the §9.4 evidence table lists bridge/EVIDENCE_CONNECT.md alongside the existing evidence files, and a sweep finds no other statement in the document still describing the single-namespace client behaviour as current
forbidden:           [editing opcua-nodes.md or any other file, editing bridge/ code or evidence, restating measurements beyond citing the evidence file, adding dependencies]

## Context

m3-21 delivered the client conformance the design's §3.1 N1–N6 and §3.2
S1–S6 require: bridge.yaml carries both namespace URIs and a per-element
qualified interface path; opcua_side.py resolves both indices by URI at
every session establishment and derives keep-alive as granted/3; the test
double serves the ServerInterfaces shape on deliberately different indices
and grants a timeout different from the request in both directions. The
recorded harness run is bridge/EVIDENCE_CONNECT.md (22/22, below-request
and above-request grants, 800-cycle full loop at 20.0 Hz). Cite it; do not
re-derive its numbers. Location hints are starting points — verify by
independent whitespace-normalised search (LESSONS 2026-07-27).
