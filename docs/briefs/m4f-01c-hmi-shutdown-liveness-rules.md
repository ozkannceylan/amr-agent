# Brief m4f-01c — HMI shutdown and operator-liveness rules

```
gate:                M4
agent:               interface
goal:                Section 10.8 rules the HMI's shutdown behaviour and the
                     operator-liveness gap instead of leaving both to
                     implementation choice.
invariants_touched:  none
inputs:              [docs/reports/m4f-07-hmi-backend-ui.md (the reconciled
                      split and the crashed-browser gap), hmi/EVIDENCE_HMI.md,
                      docs/interfaces/opcua-nodes.md section 10.8]
deliverable:         docs/interfaces/opcua-nodes.md section 10.8 (two rules)
done_when:           H5 is scoped explicitly: a CLEAN shutdown writes no
                     farewell value (the stopped heartbeat is the signal, and
                     the server holding a live-looking demand under a stopped
                     counter is the property the watchdog test observes), while
                     a backend fault or dropped session fires the deadman first
                     so the final write attempt carries the current state of
                     the controls — the split m4f-07 implemented, confirmed as
                     the rule or corrected with deltas listed; a NEW H-rule
                     covers operator liveness: the UI's existing 5 Hz status
                     poll doubles as a liveness beacon, and when the beacon is
                     stale for a named-constant window the backend zeros all
                     request controls while the heartbeat continues (the HMI
                     process is healthy; the operator is gone — this is the
                     invariant-2 pattern one level up, and it must be stated as
                     process behaviour, not a safety function); the constant is
                     named with its derivation (multiple of the poll period);
                     the implementation request against hmi/ is recorded.
forbidden:           [renaming nodes, editing hmi/ files, changing any other
                      section 10 rule, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the interface
doc plus your report docs/reports/m4f-01c-hmi-shutdown-liveness-rules.md;
message style `docs(interfaces): rule the HMI shutdown split and operator
liveness`.
