gate:                M2
agent:               verifier (read only)
goal:                Review the SRS against the M2 gate criterion and the safety invariants.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 6, 9, docs/safety/SRS.md, docs/interfaces/*]
deliverable:         Verdict returned to the orchestrator, filed as docs/reports/m2-02-verify.md.
done_when:           Explicit pass/fail with evidence: every function has trigger+reaction+acceptance test; no safety function depends on the network or the standard program (invariants 1, 7); network loss is degraded mode (invariant 2); reset is monitored and edge-triggered; conventions section matches CLAUDE.md 9; consistency with the interface docs' informational-mirror stance; git hygiene.
forbidden:           [editing or creating any file, fixing defects found]
