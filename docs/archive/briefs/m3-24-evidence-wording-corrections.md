# Brief m3-24 — evidence and config wording corrections from m3-23

gate:                M3
agent:               bridge
goal:                bridge/ wording matches the verified behaviour: two-direction timeout revision, the commissioned endpoint named where the owner swaps it in, and no figure a harness does not print
invariants_touched:  none
inputs:              [docs/reports/m3-23-verify-commissioning.md (findings F3, F4, F5, F6), bridge/EVIDENCE_LATENCY.md, bridge/EVIDENCE_SIGNAL_LOSS.md, bridge/EVIDENCE_CONNECT.md, bridge/config/bridge.yaml, bridge/tools/check_connect_conformance.py (read only)]
deliverable:         the wording correction set inside bridge/
done_when:           no bridge/ file describes the session-timeout revision as one-directional clamping (EVIDENCE_LATENCY.md §B.0.3's both-directions statement is the reference); bridge.yaml's endpoint comment names opc.tcp://192.168.53.1:4840 as the commissioned value the owner swaps in for the PLCSIM run; every check count stated in bridge/ matches what the harness actually prints, or the count is removed — run the harness read-only if needed to confirm what it prints
forbidden:           [changing any measured figure or log excerpt, changing code behaviour (comments and prose only), editing files outside bridge/, editing docs/ (the stale figures in past reports and PLAN are handled by the orchestrator), adding dependencies]

## Context

m3-23 verified the m3-18 to m3-22 chain (pass-with-findings) and re-ran the
connect-conformance harness with results matching the committed evidence
value for value. Four wording findings remain in bridge/: the "clamp"
framing survives one-directionally in the two older evidence files (F3,
F4) although the grant can land above or below the request; the "22/22
checks" figure is not what the harness prints — the verifier counted 18
checks from 19 call sites (F5); and bridge.yaml's endpoint comment never
names the commissioned endpoint the owner must swap in (F6). Enumerated
locations are a starting point — sweep bridge/ independently with
whitespace-normalised searches for "clamp", "22/22" and endpoint mentions.
