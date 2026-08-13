# Brief m4f-04f — the double's K2 label matches the scale ruling

```
gate:                M4
agent:               plc
goal:                The logic double's kernel evidence carries the corrected
                     cap semantics label, proven by a re-run rather than an
                     edited transcript.
invariants_touched:  none
inputs:              [docs/reports/m4f-04e-t5-pass-line-corrections.md,
                      plc/forklift/double/check_kernels.py,
                      plc/forklift/double/EVIDENCE_DOUBLE.md]
deliverable:         plc/forklift/double/ — the K2 check label in
                     check_kernels.py, and a fresh dated kernel run appended
                     to EVIDENCE_DOUBLE.md
done_when:           K2's label states scale semantics (the cap multiplies the
                     request; 0.2 × 0.30 = 0.060 m/s) instead of "the cap
                     LIMITS, it does not command"; the assertion values are
                     unchanged (they were already correct); a fresh full
                     check_kernels.py run against the double is appended to
                     the evidence with its output quoted as printed, the old
                     transcript left intact above it; logic.py and server.py
                     byte-identical.
forbidden:           [editing logic.py or server.py or SPEC.md, editing the
                      old transcript in place, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the two
double files plus your report docs/reports/m4f-04f-double-k2-label.md; message
style `fix(plc): relabel the cap kernel and re-run the double checks`.
