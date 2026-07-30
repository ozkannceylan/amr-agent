# Brief m5a-04c — the safety SPEC records the as-built edge networks

```
gate:                M5 (early)
agent:               plc
goal:                plc/forklift-safety/SPEC.md's primary text describes the
                     program that runs: manual edge detection, because this
                     F-instruction set has no R_TRIG/F_TRIG.
invariants_touched:  none
inputs:              [plc/forklift-safety/SPEC.md (section 5.0 note 4 already
                      carries the fallback — it was applied), the as-built
                      facts below from the 2026-07-30 TIA session]
deliverable:         plc/forklift-safety/SPEC.md — sections 3.2, 5 and the
                     watch-table rows that name the edge statics
done_when:           the note-4 fallback is promoted to the primary
                     description: N3 and N4 form the edges manually
                     (ResetButtonPressed AND NOT ResetMemory /
                     NOT ResetButtonPressed AND ResetMemory) and a new final
                     network N14 = ResetMemory := ResetButtonPressed runs
                     after every edge consumer; the network count reads 14,
                     the static list reads 10 (single ResetMemory replaces the
                     two edge statics); section 3.2 and the watch table agree;
                     the R_TRIG/F_TRIG form is kept as a note for CPUs that
                     have them, clearly marked not-this-build; a sweep over
                     R_TRIG, F_TRIG and the two retired static names finds no
                     sentence still presenting them as the build.
forbidden:           [changing any demand-latch or reset-window semantics
                      (they are as specified and live-verified), touching
                      plc/forklift/SPEC.md, mentioning any deadline]
```

As-built facts (2026-07-30 handover): D1-D7 fully applied; FB2 interface
3 in / 4 out / 10 static / 2 constant; FB1 call has the three input pins bound
to SafetyInputStandIn and all four output pins empty — the F write set is
InstF_Forklift_Safety alone. Live-verified: monitored reset end to end
(arm → 200 ms hold → release → both demand latches clear), upper bound twice
(held past 3 s ⇒ SafetyResetFault TRUE, reset refused), mirrors tracking the
demands within one scan.

Git: repo-local owner identity; pathspec-scoped commit of exactly SPEC.md plus
your report docs/reports/m5a-04c-asbuilt-edge-networks.md; message style
`docs(plc): record the as-built edge networks`.
