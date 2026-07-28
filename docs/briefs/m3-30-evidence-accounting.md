# Brief m3-30 — evidence accounting corrections from the m3-28 review

gate:                M3
agent:               bridge
goal:                Section B's pass accounting and figure provenance match what was actually run and recorded
invariants_touched:  none
inputs:              [bridge/EVIDENCE_LATENCY.md (Section B, §B.12, §B.13), docs/reports/m3-28-t-scenario-review.md (secondary findings), bridge/evidence/*plcsim*.csv.gz]
deliverable:         bridge/EVIDENCE_LATENCY.md
done_when:           T4.11 is accounted for — either in the as-run record or in §B.12's owner-outstanding list — and no pass claim counts a step absent from both; and §B.13's "1.8 s" and "0.3093" figures either carry their provenance (which file or log line produced them) or are restated as uncommitted run observations distinct from the reproducible figures beside them
forbidden:           [changing any figure that reproduces from a committed CSV, re-running anything, editing files outside bridge/, changing code, adding dependencies]

## Context

m3-28's evidence-hygiene check passed overall — L7's six samples and
§B.3's rates reproduce digit for digit from the committed CSVs — with two
findings: "Pass: all twelve" counts T4.11, which appears in neither the
as-run record nor §B.12's outstanding list (T4.11 is the belt-feedback
fault-path test m3-27 added to §11, which postdates the live run); and two
§B.13 numbers reproduce from no committed file, both erring conservative.
Fix the accounting, not the history: what ran, ran.
