# Brief m4f-08d — the scenario doc learns H6

```
gate:                M4
agent:               sim
goal:                The scenario document's statements about the reset and the
                     stimulus survive the H6/holdable-reset commit, and the new
                     interaction rule is recorded where operators will meet it.
invariants_touched:  none
inputs:              [docs/reports/m4f-07b-h6-and-holdable-reset.md (commit
                      7675960; its sim note lists the five stale statements at
                      lines 447, 459, 507, 653, 720),
                      sim/scenarios/forklift_commissioning.md,
                      sim/scenarios/forklift_stimulus.py]
deliverable:         sim/scenarios/forklift_commissioning.md — the five stale
                     statements and one new interaction note
done_when:           the five statements reflect the holdable reset and H6 as
                     shipped (T5.4 executable from the page, finding 3 closed
                     naming 7675960); a short note where the stimulus tool is
                     introduced records the H6 interaction: hold mode re-posts
                     continuously and is safe by construction, but any step
                     that posts once and then waits longer than 1.0 s has its
                     requests returned to rest by the liveness deadman, and a
                     Bool re-asserted after such a gap is carried only once
                     posted low first; no figure or rehearsal transcript
                     changes; a subject sweep over "reset" and "stimulus" in
                     the file finds no further statement asserting the
                     momentary-only reset.
forbidden:           [editing hmi/ or plc/ files, changing any rehearsal
                      figure, mentioning any deadline]
```

Git: repo-local owner identity; leave the changes uncommitted per your standing
rule and hand the orchestrator the pathspec, or commit pathspec-scoped if your
instructions permit — either way the report is
docs/reports/m4f-08d-h6-stimulus-interaction.md and the message style is
`docs(sim): record the liveness interaction in the scenario procedure`.
