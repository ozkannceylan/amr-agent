# Brief m5a-02 — roadmap note for the early opening

```
gate:                M5 (early)
agent:               arch-docs
goal:                docs/roadmap.md records that M5's cell-scope core is
                     opened early under ADR 0009, with M4 unchanged.
invariants_touched:  none
inputs:              [docs/adr/0009-*.md, docs/roadmap.md]
deliverable:         docs/roadmap.md — one note under the current-gate line
done_when:           a two-sentence note states: M4 remains the current gate
                     with its criteria unchanged; M5's cell-scope functions
                     (SF-01, SF-08, SF-07 pattern) are opened early on the
                     forklift twin per ADR 0009 with its fallback rule; no
                     table row changes.
forbidden:           [any table change, renumbering, editing ADRs or PLAN.md,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly roadmap.md
plus your report docs/reports/m5a-02-roadmap-early-note.md; message style
`docs(infra): note the early cell-scope safety opening`.
