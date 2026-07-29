# Brief m4r2-05 — hmi in the CLAUDE.md area list

```
gate:                M4
agent:               infra (owner-approved for exactly this edit)
goal:                CLAUDE.md section 7's valid-area list includes hmi, making
                     the already-practised feat(hmi) scope de jure.
invariants_touched:  none — executes ADR 0008's consequence, same footing as
                     m4r2-03
inputs:              [CLAUDE.md section 7, docs/adr/0008-*.md,
                      docs/reports/m4f-07-hmi-backend-ui.md (the note)]
deliverable:         CLAUDE.md section 7 — the valid-areas line only
done_when:           the line reads the existing areas plus hmi, nothing else
                     in the file changes (git diff shows one line).
forbidden:           [any other CLAUDE.md change, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly CLAUDE.md
plus your report docs/reports/m4r2-05-claudemd-hmi-area.md; message style
`docs(infra): add hmi to the commit area list`.
