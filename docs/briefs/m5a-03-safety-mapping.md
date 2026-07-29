# Brief m5a-03 — the twin demonstration mapped onto the SRS

```
gate:                M5 (early)
agent:               safety-spec
goal:                One addendum states exactly which SRS functions and
                     acceptance sub-cases the forklift-twin demonstration
                     exercises, with ISO 13849 references, and what it does
                     not claim.
invariants_touched:  none
inputs:              [docs/adr/0009-*.md, docs/safety/SRS.md,
                      docs/safety/ PL scenario document (m2-03),
                      docs/roadmap.md M5 row]
deliverable:         docs/safety/TWIN-DEMO-MAP.md
done_when:           for each of SF-01, SF-08 and the SF-07 pattern the
                     addendum names: the SRS trigger/reaction text it
                     instantiates on the twin, the AT sub-cases the
                     demonstration exercises versus the ones it defers, the
                     PL target with its derivation reference from the
                     existing PL scenarios, and the wording the recording
                     must use; the non-claims are explicit — SF-02/03/04
                     onboard functions out of scope at this gate, simulation
                     demonstrates acceptance-test logic and claims no
                     achieved PL, simulated F-I/O stimulus is an engineering
                     stand-in for hardwired inputs; one page, table-first.
forbidden:           [editing SRS.md or the PL scenarios (addendum only),
                      inventing new SF numbers or PL values, code,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the addendum
plus your report docs/reports/m5a-03-safety-mapping.md; message style
`docs(safety): map the twin demonstration onto the SRS`.
