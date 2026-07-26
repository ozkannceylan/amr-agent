gate:                M0
agent:               verifier (read only)
goal:                Independent pass/fail verdict on the roster change and ADR 0003.
invariants_touched:  none
inputs:              [CLAUDE.md sections 5, 7, 8, docs/briefs/m0-08, the branch diff against main]
deliverable:         Verdict returned to the orchestrator, filed as docs/reports/m0-09-verify-roster-distro.md by the orchestrator.
done_when:           Explicit pass/fail with evidence on: roster row added correctly with nothing else in CLAUDE.md changed; ADR 0003 format, acceptance precondition (dated, SHA-pinned verification record) and alternatives; tracking-file consistency; git hygiene.
forbidden:           [editing or creating any file, fixing defects found]
