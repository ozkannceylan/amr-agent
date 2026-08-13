# Brief m4r2-06 — bridge and adr in the CLAUDE.md area list

```
gate:                M4
agent:               infra (owner-approved for exactly this edit)
goal:                CLAUDE.md section 7's valid-area list describes practice:
                     bridge (19 commits) and adr (2 commits) become legal.
invariants_touched:  none — bridge/ has been a contract layer since ADR 0005;
                     the list simply never caught up
inputs:              [CLAUDE.md section 7,
                      docs/reports/m4r2-05-claudemd-hmi-area.md (the finding)]
deliverable:         CLAUDE.md section 7 — the valid-areas line only
done_when:           the line gains bridge (after agv, before hmi) and adr
                     (after interfaces), nothing else in the file changes
                     (git diff shows one line, real content under
                     --ignore-cr-at-eol).
forbidden:           [any other CLAUDE.md change, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly CLAUDE.md
plus your report docs/reports/m4r2-06-claudemd-bridge-adr-areas.md; message
style `docs(infra): add bridge and adr to the commit area list`.
