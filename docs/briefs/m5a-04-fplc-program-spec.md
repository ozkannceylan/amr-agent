# Brief m5a-04 — F-program specification for the forklift twin

```
gate:                M5 (early)
agent:               plc
goal:                plc/forklift-safety/SPEC.md specifies the F-program
                     completely enough for the owner to build it in TIA Safety
                     from the description alone — F-LAD, not SCL.
invariants_touched:  none — the demand forms inside the CPU (invariant 1);
                     the standard program stays independent (invariant 7:
                     the F-program must remain correct if the standard
                     program halts)
inputs:              [docs/adr/0009-*.md, docs/safety/TWIN-DEMO-MAP.md,
                      docs/safety/SRS.md (SF-01, SF-07, SF-08 and their ATs),
                      plc/forklift/SPEC.md (the standard side it couples to),
                      plc/demo-cell/SPEC.md (document conventions)]
deliverable:         plc/forklift-safety/SPEC.md
done_when:           the spec mirrors the house structure adapted to F: §1
                     scope and non-claims; §2 the feasibility checkpoint
                     FIRST (Safety Advanced V21 licence present, empty
                     F-project compiles, F-runtime group reaches RUN on the
                     1513F-1 PN PLCSIM instance — with the abort-to-fallback
                     rule if any fails); §3 F-tags and the F-DB the standard
                     program reads; §4 F-runtime group setup click-path
                     (F-monitoring time, safety administration, password
                     handling stated honestly for a simulation context); §5
                     the two demand latches in F-LAD described
                     element-by-element (network by network, each contact,
                     coil and F-block named): EStopDemand from the simulated
                     e-stop F-DI (wire-NC/program-NO), ZoneStopDemand from
                     the zone F-DI, both latching, cleared only by the SF-08
                     monitored reset (edge-triggered, refused while the
                     cause stands, no auto-resume); §6 the coupling contract:
                     which F-DB flags the standard FB_ForkliftTeleop reads
                     (read-only from standard side) and the rule that the
                     F-program never reads teleop state; §7 the simulated
                     input strategy for the demonstration (how the e-stop and
                     zone F-inputs are driven on PLCSIM — engineering
                     stand-in, stated as such); §8 watch table "Forklift F
                     gate"; §9 the T6 demonstration procedure: e-stop trip
                     mid-drive, reset refused under demand, monitored reset,
                     zone trip with the forklift driven into the marked zone,
                     each step naming node, expected value and the SRS/AT
                     reference; §10 what is deliberately not specified.
                     Every SRS reference by exact SF/AT id; every ISO 13849
                     mention cites the existing derivation, never a new
                     number.
forbidden:           [SCL for F-logic (F-LAD/F-FBD description only), editing
                      plc/forklift/SPEC.md (separate brief), claiming any
                      achieved PL, editing docs/safety/, mentioning any
                      deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the new SPEC
plus your report docs/reports/m5a-04-fplc-program-spec.md; message style
`feat(plc): specify the forklift twin F-program`.
