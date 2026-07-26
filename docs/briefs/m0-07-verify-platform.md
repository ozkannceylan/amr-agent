gate:                M0
agent:               verifier (read only)
goal:                Independent pass/fail verdict on the platform-decision addendum.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 6, 7, 8, docs/briefs/m0-05..06, the repository tree]
deliverable:         Verdict returned to the orchestrator, filed as docs/reports/m0-07-verify-platform.md by the orchestrator.
done_when:           Each criterion has an explicit pass or fail with evidence: ADR 0002 exists in section 8 format, status accepted, content matches the owner decision, no unverifiable vendor claims, no invariant altered; roadmap has an M9 row with the three closure conditions, existing gates unreordered, current gate still M1, nothing newly marked complete; tracking files consistent; commits conventional with no attribution.
forbidden:           [editing or creating any file, fixing defects found]
