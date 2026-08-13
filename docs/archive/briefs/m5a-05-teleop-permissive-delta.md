# Brief m5a-05 — the teleop permissive learns the safety demand

```
gate:                M5 (early)
agent:               plc
goal:                plc/forklift/SPEC.md gains the F-demand term in the
                     motion permissive and the Safety/ mirror writes, as a
                     delta the owner applies on top of the built program.
invariants_touched:  none — standard reads F-data, never the reverse
inputs:              [plc/forklift-safety/SPEC.md section 6 (the coupling
                      contract — authoritative), plc/forklift/SPEC.md,
                      docs/interfaces/opcua-nodes.md section 11 (Safety/
                      mirrors, once m5a-06 lands — check for it; if absent,
                      state the mirror names as proposed and flag)]
deliverable:         plc/forklift/SPEC.md — a delta section (new section 13)
                     plus the minimal SCL delta in section 7
done_when:           the motion permissive gains exactly one new term —
                     safetyDemandClear, read from the F-DB flags the coupling
                     contract names, affirmative form (clear := NOT EStopDemand
                     AND NOT ZoneStopDemand read from F-data) — and the three
                     setpoints' single-assignment ELSE-zero structure is
                     untouched; the standard program copies the F-demand
                     states to the Safety/ mirror tags each cycle
                     (unconditional assignments, mirrors read-only to
                     clients); the delta is written as an explicit
                     before/after so the owner can apply it in TIA without
                     re-reading the whole spec; the statement-line count
                     change is stated exactly (this delta DOES change section
                     7 — say by how many statements and re-derive the fence
                     hash discipline accordingly); T5 pass lines are checked
                     for impact (a standing F-demand must read as motion
                     refused, not as a defect) and amended where needed with
                     counts re-derived; a note states the fallback: with no
                     F-program present the F-DB flags read as clear and the
                     delta is inert.
forbidden:           [changing any interlock beyond adding the one term,
                      touching the HMI/obstacle logic, editing
                      plc/forklift-safety/SPEC.md or docs/interfaces/,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly SPEC.md plus
your report docs/reports/m5a-05-teleop-permissive-delta.md; message style
`feat(plc): couple the teleop permissive to the safety demand`.
