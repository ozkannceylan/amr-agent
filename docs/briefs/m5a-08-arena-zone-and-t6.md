# Brief m5a-08 — the marked safety zone and the T6 scenario

```
gate:                M5 (early)
agent:               sim
goal:                The arena carries the marked safety zone and the scenario
                     document gains the F-layer demonstration, fallback-safe.
invariants_touched:  none
inputs:              [docs/adr/0009-*.md, docs/safety/TWIN-DEMO-MAP.md,
                      plc/forklift-safety/SPEC.md section 9 (the T6 steps —
                      wait for it if absent), sim/worlds/forklift_arena.sdf,
                      sim/scenarios/forklift_commissioning.md]
deliverable:         sim/worlds/forklift_arena.sdf (zone marking only) and
                     sim/scenarios/forklift_commissioning.md (T6 section)
done_when:           the arena gains a visually marked zone (floor marking,
                     no physics change, placed so the forklift can be driven
                     into it across open floor) with the world's existing
                     style; the scenario doc gains the T6 section mirroring
                     the F-spec's procedure — e-stop trip mid-drive, reset
                     refused, monitored reset, zone trip — each step naming
                     the stimulus (the F-inputs are driven TIA-side per the
                     F-spec's section 7, marked owner), the observable (HMI
                     safety banner/lamps, refs zero, watch table rows) and
                     the SRS/AT reference from the TWIN-DEMO-MAP; the section
                     opens with the fallback sentence (T6 runs only when the
                     F-program exists; the M4 scenarios stand alone without
                     it); recording checklist lines carry the ISO 13849
                     naming discipline from the map; no rehearsal transcript
                     or existing figure changes.
forbidden:           [physics or model changes, editing agv/ plc/ hmi/
                      docs/interfaces/ files, touching existing scenario
                      steps or figures, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the two sim
files plus your report docs/reports/m5a-08-arena-zone-and-t6.md; message style
`feat(sim): add the safety zone and the F-layer scenario`.
