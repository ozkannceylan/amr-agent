# Brief m5-18 — PLr targets for the M5 functions, and the claim boundary landed

```
gate:                M5
agent:               safety-spec
goal:                every M5 safety function carries a PLr target derived
                     from a documented risk assessment, and the ADR 0011 D5
                     claim boundary is landed in the safety documents.
invariants_touched:  none
inputs:              [docs/safety/SRS.md, docs/safety/PL-SCENARIOS.md (the
                      existing risk-graph derivations — the method to follow),
                      docs/adr/0011-sensored-autonomy-architecture.md D5 and
                      its facts block (scanner class, SLS/STO definitions,
                      ISO 3691-4 notes), docs/adr/0014-motion-control-locus.md
                      D5, agv/forklift/EVIDENCE_SENSOR_COVERAGE.md (the
                      residual sectors R1-R8 — a risk assessment that ignores
                      the measured blind sectors is fiction),
                      plc/forklift-safety/SPEC.md section 1.3]
deliverable:         docs/safety/ — the M5 function rows and derivations,
                     plus the two corrections below
done_when:           the M5 functions — the scanner protective stop (two
                     scanners, the measured residual sectors named as
                     exposure qualifiers), SLS with its speed source stated,
                     and the SS1 sequencing between them — each carry an S/F/P
                     derivation in PL-SCENARIOS' existing pattern with a PLr
                     target, and NO achieved PL, Category, SIL or PFH is
                     claimed anywhere for this project's own chain; the
                     ADR 0011 D5 non-claim list is landed once in SRS.md where
                     a reader of any safety claim will pass it; the
                     "Category 3 is claimed" wording in PL-SCENARIOS is
                     re-verbed so no sentence claims an achieved architecture
                     (the judge marked it permanent grep-bait — sweep the
                     verb, not the noun); and the three safety documents'
                     "gate order of ADR 0010" attributions gain "as amended by
                     ADR 0013" or cite docs/roadmap.md as the live source,
                     whichever each sentence already leans toward.
forbidden:           [claiming any achieved PL, Category, SIL or PFH for this
                      project's chain; quoting the microScan3's datasheet
                      figures except as the modelled component's data with the
                      ADR 0011 D5 guard sentence beside them; presuming the
                      m5-03 F-I/O verdict (PLr targets are demands on the
                      function, valid under either signal-path outcome — say
                      so once); editing files outside docs/safety/;
                      renumbering anything; committing (the orchestrator
                      commits)]
```

## Notes

The derivation discipline is already in LESSONS and PL-SCENARIOS practice:
PLr belongs to the hazard, not to the function named in a scenario title; F is
the person's exposure to the hazard zone, never the fault rate; a fault
scenario inherits S, F and P from the demand scenario its fault disables.
Follow the house pattern.

The measured residuals matter here. R3 (load occlusion, 39.9°) and R8 (rear
self-occlusion band, 21.8% of that aperture) are measured facts about where
the protective field cannot see. A person in a residual sector is exposure the
risk graph must account for — with the mitigation (reduced field plus creep
speed in the load direction, ISO 3691-4's 0.3 m/s cap for muted detection)
stated as the risk reduction it is, not as the sector's elimination.

Do not commit. Leave files modified and write your report to
docs/reports/m5-18-plr-derivation.md.
