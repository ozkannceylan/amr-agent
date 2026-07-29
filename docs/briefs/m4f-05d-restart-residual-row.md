# Brief m4f-05d — restart-residual row at its measured size

```
gate:                M4
agent:               interface
goal:                bridge-design.md states the restart blind spot at the size
                     m4f-06 measured, and its §12 reflects the m4f-06 closures.
invariants_touched:  none
inputs:              [docs/reports/m4f-06-bridge-forklift-slots.md,
                      bridge/EVIDENCE_CONNECT.md section m4f-06,
                      docs/interfaces/bridge-design.md sections 8.1 and 12]
deliverable:         docs/interfaces/bridge-design.md — the section 8.1
                     restart-residual row, and section 12 items 11, 13, 14
done_when:           the residual row carries the measured mechanism — a server
                     revert landing between the cycle's step-0 heartbeat
                     read-back and its step-4 heartbeat write is erased by that
                     write and the restart goes undetected; measured 5.255 ms
                     of a 50.015 ms cycle; one masked revert left an open stop
                     circuit and ForkliftObstacleInStopZone TRUE for 4.0 s
                     under an advancing heartbeat; pre-existing and not
                     forklift-specific — and states that both restart harnesses
                     trigger until a revert is caught and report the masked
                     count; the second-witness requirement stays as written and
                     is marked an open owner decision; section 12 item 11 is
                     closed naming 71d3b76, item 13's requesting half marked
                     satisfied per EVIDENCE_LATENCY.md, item 14's bridge half
                     confirmed per EVIDENCE_LIFECYCLE.md section 1.2; a subject
                     sweep over "residual", "restart" and "heartbeat" in the
                     file finds no statement still asserting the old
                     understated size.
forbidden:           [changing the second-witness rule itself, code, any file
                      other than the design doc and your report, mentioning any
                      deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the design
doc plus your report docs/reports/m4f-05d-restart-residual-row.md; message
style `docs(interfaces): state the restart blind spot at its measured size`.
