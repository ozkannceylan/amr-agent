# Brief m5r-09 — verification of the ADR 0010 restructure round

```
gate:                restructure round (closing)
agent:               verifier
goal:                independent confirmation that the m5r round left the
                     repository consistent under ADR 0010.
invariants_touched:  none (read only)
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md,
                      docs/briefs/m5r-01..08, docs/reports/m5r-01..08,
                      the full report directory, git log of 2026-07-30]
deliverable:         docs/reports/m5r-09-restructure-verification.md only
done_when:           each check below has a cited-artifact verdict:
                     1. No live document (everything except docs/adr/,
                        docs/briefs/, docs/reports/, docs/LESSONS.md) carries
                        a pre-ADR-0010 gate reference — verified by an
                        independent whitespace-normalised sweep for M5-M12
                        tokens and the old gate names, not by trusting the
                        m5r reports' own sweeps.
                     2. roadmap.md, PLAN.md, TODO.md, CLAUDE.md §6 and
                        README.md agree with each other and with ADR 0010
                        (gate set, M4 closing status, open decisions).
                     3. The four ADR 0010 D6 open decisions are recorded as
                        open wherever they surface, and no m5r deliverable
                        resolved any of them.
                     4. M0-M4 criteria are unchanged (roadmap M0-M4 rows
                        byte-comparable to the pre-round state via git), and
                        the `Forklift M4 gate` watch-table name survives
                        everywhere it appeared.
                     5. Every m5r agent wrote only inside its area plus its
                        report, and every 2026-07-30 commit is pathspec-clean
                        (no unrelated file swept in), conventional, and free
                        of attribution (message AND author fields).
                     6. TODO/PLAN reconcile against the full report
                        directory (LESSONS 2026-07-27 check-26 rule).
forbidden:           [editing anything except the report, re-running any
                      sweep as an edit, ruling on ADR 0010's substance]
```
