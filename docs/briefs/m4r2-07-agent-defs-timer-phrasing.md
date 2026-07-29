# Brief m4r2-07 — agent definitions match the client-logic ruling

```
gate:                M4
agent:               infra (owner-approved for exactly these two files)
goal:                The hmi and bridge agent definitions carry the section
                     10.1 client-logic ruling instead of the retired flat
                     phrasing.
invariants_touched:  none
inputs:              [docs/reports/m4f-01d-section10-consistency.md,
                      docs/interfaces/opcua-nodes.md section 10.1,
                      .claude/agents/hmi.md, .claude/agents/bridge.md]
deliverable:         .claude/agents/hmi.md and .claude/agents/bridge.md — the
                     client-logic sentence in each
done_when:           neither file says "no timer" flatly; each states the
                     ruling's test — a client may own timers that watch its
                     own cycle or its own input channel (the bridge's cycle,
                     the HMI's write cadence and page-liveness window), never
                     a timer that watches the plant, and no interlock, latch,
                     sequencing, setpoint formation or reaction to plant
                     state; nothing else in either file changes.
forbidden:           [editing any other agent definition or CLAUDE.md,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the two
definitions plus your report docs/reports/m4r2-07-agent-defs-timer-phrasing.md;
message style `docs(infra): align the client agent definitions with the
client-logic ruling`.
