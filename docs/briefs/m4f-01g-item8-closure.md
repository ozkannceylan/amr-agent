# Brief m4f-01g — §10.12 item 8 closed by the implementation

```
gate:                M4
agent:               interface
goal:                The node model's request register reflects that H6 and the
                     holdable reset are implemented and evidenced.
invariants_touched:  none
inputs:              [docs/reports/m4f-07b-h6-and-holdable-reset.md (commit
                      7675960), docs/interfaces/opcua-nodes.md sections 10.8
                      and 10.12, hmi/EVIDENCE_HMI.md sections D and E]
deliverable:         docs/interfaces/opcua-nodes.md — section 10.12 item 8 and
                     the two citations naming EVIDENCE_HMI.md section D
done_when:           item 8 is marked closed naming 7675960 with the two
                     kernels (K1 liveness, K2 held-reset T5.4) cited; the
                     section 10.8 prose citation and item 8's citation both
                     point at the evidence section that now carries the gap
                     row's closure (section E) rather than the superseded
                     section D wording; the honestly-recorded residual (the
                     browser DOM pass not re-run in that session) is carried,
                     not erased; nothing else changes.
forbidden:           [changing any H- or P-rule, editing hmi/ files,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the doc plus
your report docs/reports/m4f-01g-item8-closure.md; message style
`docs(interfaces): close the liveness request against its implementation`.
