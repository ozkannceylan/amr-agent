# Brief m5r-04 — public README milestone table and narrative per ADR 0010

```
gate:                restructure round
agent:               infra
goal:                README.md's milestone table and gate-order narrative match
                     ADR 0010, repairing the 2026-07-30 hand-edit that dropped
                     two rows and forked the numbering; assets/CREDITS.md's one
                     gate line follows.
invariants_touched:  none
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md,
                      README.md, assets/CREDITS.md line ~60,
                      docs/roadmap.md (as revised by m5r-02)]
deliverable:         README.md (milestone section and gate-order prose) and the
                     single stale gate line in assets/CREDITS.md
done_when:           the milestone table reads M0-M3 done, M4 "closing —
                     showcase recording and gate verification pending", M5
                     "Sensored autonomous forklift" planned, M6 "VDA 5050 fleet
                     at scale" planned, M7 "LLM operations layer + final
                     demonstration" planned, with no arm and no separate Hermes
                     row; the "Next gate" line no longer contradicts the table;
                     the "Archived rows" paragraph is rewritten to say what
                     ADR 0010 rules (safety and autonomy land on the forklift
                     twin, fleet at scale follows, the LLM layer closes the
                     program, the arm is out of scope); the gate-order
                     paragraph cites ADR 0010; the video lead, the M3 story
                     section and all other README content are untouched;
                     assets/CREDITS.md's "vehicle enters the demonstration at
                     M6" line reads M5.
forbidden:           [editing any file other than README.md and
                      assets/CREDITS.md, restructuring README sections beyond
                      the milestone/gate-order content, removing or reordering
                      the showcase media, committing (the orchestrator
                      commits), mentioning any deadline]
```

Note: the owner's own commits 46caa95/0007b16 are the edit being repaired —
their intent (forklift-first, archived rows onto the twin) is exactly what
ADR 0010 records; only the numbering and the two silently deleted rows need
repair. Keep the owner's tone: short rows, no criteria dumps (criteria live in
docs/roadmap.md).

Do not commit. Leave both files modified and write your report to
docs/reports/m5r-04-readme-milestones.md (also uncommitted).
