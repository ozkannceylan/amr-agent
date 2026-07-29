# Brief m4f-04b — plc/ prose alignment with the steer ruling

```
gate:                M4
agent:               plc
goal:                plc/ no longer describes the steer-gating question as
                     unresolved, and plc/README.md knows the forklift spec
                     exists.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md section 10.6 (the ruling,
                      commit ae93667), plc/forklift/SPEC.md, plc/README.md]
deliverable:         plc/ prose aligned with the ruling: SPEC.md sections 6.4,
                     7 (the SCL comment) and 12 item 2, plus the plc/README.md
                     forklift row
done_when:           the three SPEC sites cite the ruling instead of calling it
                     unresolved — no code, constant, tag or logic text changes,
                     since the ruling ratifies what the spec built; the README
                     gains the forklift/SPEC.md row and one sentence stating the
                     forklift program is standard-program process interlocks
                     (ADR 0008 D3); nothing else changes.
forbidden:           [any change to SCL statements, constants, tags, tables or
                      test steps; editing docs/interfaces/; mentioning any
                      deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the two plc/
files plus your report docs/reports/m4f-04b-spec-ruled-references.md; message
style `docs(plc): cite the steer ruling and list the forklift spec`.
