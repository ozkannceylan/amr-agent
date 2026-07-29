# Brief m4f-01d — section 10 consistency after the HMI wave

```
gate:                M4
agent:               interface
goal:                Section 10 says what it means about client timers and about
                     who owns the steer range.
invariants_touched:  none — invariant 10 is applied, not changed
inputs:              [docs/reports/m4f-01c-hmi-shutdown-liveness-rules.md (the
                      proposed one-clause amendment), docs/reports/m4f-07-hmi-
                      backend-ui.md (its question 4), docs/interfaces/opcua-
                      nodes.md sections 10.1, 10.6, 10.8, hmi/config.yaml]
deliverable:         docs/interfaces/opcua-nodes.md — the section 10.1 client-
                     logic row and one ownership statement for the steer range
done_when:           section 10.1's "no logic in either client" row no longer
                     reads "no timer" flatly, since H2 requires a self-cycle
                     timer, H6 a beacon window and the bridge its own cycle —
                     the amended row distinguishes the timers a client needs to
                     produce its own cadence and liveness verdicts from the
                     process logic a client must never carry (no interlock, no
                     latch, no setpoint formation, no reaction to plant state);
                     the steer range is ruled with one owner named — the PLC's
                     clamp is authoritative and the HMI's copy is display
                     scaling that cannot apply a value the PLC would not, or
                     the opposite is ruled and the deltas listed — and wherever
                     the HMI keeps its copy, the document says that copy is
                     derived and names section 10.6 as its source; a subject
                     sweep over "timer", "steer range" and the constant's value
                     finds no statement left contradicting either ruling.
forbidden:           [changing H1-H6 or P1-P6 semantics, renaming nodes,
                      editing hmi/ or plc/ files, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the interface
doc plus your report docs/reports/m4f-01d-section10-consistency.md; message
style `docs(interfaces): scope the client-logic rule and rule the steer range`.
