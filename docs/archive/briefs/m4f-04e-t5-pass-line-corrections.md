# Brief m4f-04e — T5 pass-line corrections from the rehearsal

```
gate:                M4
agent:               plc
goal:                SPEC section 11's pass lines state what section 7 actually
                     computes, so the owner's run cannot fail against a correct
                     program.
invariants_touched:  none
inputs:              [docs/reports/m4f-08-commissioning-scenarios.md (findings
                      1 and 2), plc/forklift/SPEC.md sections 6, 7, 9, 11,
                      sim/scenarios/forklift_commissioning.md (the rehearsed
                      observations)]
deliverable:         plc/forklift/SPEC.md — section 11 steps 5.3.4 and 5.1.1
done_when:           5.3.4's Pass line matches section 7's SCALE semantics —
                     the raised-carriage cap multiplies the request fraction
                     (a 0.20 request under the 0.30 m/s cap commands
                     0.060 m/s, the rehearsed observation), it does not clamp
                     a full-speed product to 0.20 — and a subject sweep over
                     "cap" in sections 6, 9 and 11 finds no other statement
                     implying clamp semantics; 5.1.1 no longer treats
                     ForkliftObstacleStopActive FALSE at first read as a
                     guarantee — the step is rewritten to read after
                     HmiLinkOk is TRUE and one full scan has passed, or to
                     state the expected value as settled-within rather than
                     instantaneous; every affected pass count re-derives from
                     its own step table; the section 7 SCL, constants, tags
                     and all other steps stay byte-identical (verify by the
                     statement-line count as before).
forbidden:           [any change to section 7 SCL, constants or tags, editing
                      sim/ files, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly SPEC.md plus
your report docs/reports/m4f-04e-t5-pass-line-corrections.md; message style
`fix(plc): state the cap as a scale and settle the first-read race`.
