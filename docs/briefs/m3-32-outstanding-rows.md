# Brief m3-32 — outstanding rows for the re-specified case-D tests

gate:                M3
agent:               bridge
goal:                Section B's outstanding list covers every §11 step the m3-29 revision changed or added, so the evidence and the spec agree on what has not run
invariants_touched:  none
inputs:              [bridge/EVIDENCE_LATENCY.md (§B.7 roster, §B.12), plc/demo-cell/SPEC.md §11 as of m3-29 (read only), docs/reports/m3-29-case-d-rearm.md]
deliverable:         bridge/EVIDENCE_LATENCY.md
done_when:           §B.12 carries owner-outstanding rows for the revised T4.6 (mid-motion freeze with elapsed time recorded), T4.6b (at-rest D1) and the inverted T4.7 (reset refused while the image claims motion), each noting it postdates the recorded run and requires the m3-29 rebuild; the §B.7 roster's rows for the old T4.6/T4.7 are annotated as superseded by the revision rather than renumbered or deleted; and a rebuild-baseline row records that the program version at the next download must be captured with the evidence
forbidden:           [changing any measured figure, editing files outside bridge/, re-running anything, touching plc/, adding dependencies]

## Context

m3-29 re-specified case-D detection (re-armed freeze window, ≤3.2 s bound)
and split the scenario: T4.6 is now the mid-motion test, T4.6b the at-rest
D1 test, T4.7 inverted so the monitored reset is refused while the image
still claims motion. All three postdate the recorded live run, which was
made against the m3-05 build. m3-29's report explicitly requests these
rows and the rebuild baseline; m3-30 already established the pattern —
outstanding rows, never a bigger denominator. What ran, ran.
