gate:                M1
agent:               verifier (read only)
goal:                Review the three M1 interface contracts against the gate criterion and invariants.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 3, 6, 9, docs/interfaces/*, docs/briefs/m1-01..03]
deliverable:         Verdict returned to the orchestrator, filed as docs/reports/m1-04-verify.md.
done_when:           Explicit pass/fail with evidence on: VDA 5050 traceability, OPC UA direction and naming rules, handshake completeness (timeouts and fault branches), single-owner coverage with no double computation, layer boundaries respected, git hygiene.
forbidden:           [editing or creating any file, fixing defects found]
