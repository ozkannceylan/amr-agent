gate:                M0
agent:               verifier (read only)
goal:                Independent pass/fail verdict on every M0 gate criterion.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 4, 6, 7, docs/briefs/m0-01..03, the repository tree]
deliverable:         Verdict returned to the orchestrator, filed as docs/reports/m0-04-verify.md by the orchestrator (verifier has no write access).
done_when:           Each criterion has an explicit pass or fail with evidence: section 4 tree exists; every top level README opens with "This layer must not access" and names concrete dependencies; ADR 0001 exists, status accepted, all 13 invariants preserved; docs/roadmap.md has the full gate table with only M0 current and nothing closed; .claude/settings.json contains the empty attribution block; no application code exists anywhere; no secrets in the repository.
forbidden:           [editing or creating any file, fixing defects found, running write operations of any kind]
