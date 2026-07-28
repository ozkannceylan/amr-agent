# Brief m3-31 — §11 pass claims count what actually exists

gate:                M3
agent:               plc
goal:                every pass claim in SPEC.md §11 counts exactly the steps the section defines after m3-29, and no claim counts a step recorded as failed or outstanding
invariants_touched:  none
inputs:              [plc/demo-cell/SPEC.md §11 (as revised by m3-29), docs/reports/m3-30-evidence-accounting.md (open questions), bridge/EVIDENCE_LATENCY.md §B.7 roster and §B.13 (read only)]
deliverable:         plc/demo-cell/SPEC.md
done_when:           each scenario's pass criterion states its step count as derived from that scenario's current step list; T1's criterion does not silently count the step the evidence records as failed (T1.4) as passable-by-default; and the criteria are stated so a future added step changes the outstanding list, not the denominator
forbidden:           [editing files outside plc/, changing any scenario step or detection logic (m3-29 owns those and has landed), touching bridge/ evidence, adding dependencies]

## Context

m3-30 fixed the evidence-side accounting and found the source strings live
in SPEC.md §11: "Pass: all twelve" predates both m3-27's T4.11 and
m3-29's T4.6/T4.6b/T4.7 revision, and T1's "Pass: all six" counts T1.4,
which the recorded run failed. Verify the current §11 step lists yourself
after m3-29's changes — the correct counts are whatever the document now
defines, not the numbers named here.
