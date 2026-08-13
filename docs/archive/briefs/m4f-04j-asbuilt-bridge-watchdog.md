# Brief m4f-04j — the SPEC records the as-built bridge watchdog

```
gate:                M4
agent:               plc
goal:                plc/forklift/SPEC.md describes the program that runs: the
                     bridge link verdict lives inside FB_ForkliftTeleop, because
                     this TIA project has no demo cell.
invariants_touched:  none — invariant 10 holds with a new single owner
inputs:              [plc/forklift/SPEC.md, the owner decision of 2026-07-30
                      recorded below, docs/interfaces/opcua-nodes.md section 10]
deliverable:         plc/forklift/SPEC.md — sections 3.1b, 4.1, 7 (watchdog
                     part), 9 group 5, and the section 12 OB30 note
done_when:           the DemoCellLink/FB_DemoCellControl references are gone
                     (sweep proves zero remain): the FB computes its own bridge
                     link verdict from ForkliftLink.BridgeHeartbeat with
                     HEARTBEAT_STALE_TIME = T#500MS, statics
                     LastBridgeHeartbeat, BridgeSeenAlive, BridgeStaleTimer,
                     verdict BridgeSeenAlive AND NOT BridgeStaleTimer.Q with
                     the pessimistic boot polarity; section 9 group 5 carries
                     .BridgeSeenAlive and .BridgeStaleTimer.ET instead of the
                     skipped DemoCellLink row; the section 7 statement counts
                     and fence hash are re-derived and stated (the fence
                     changes — say from what to what); section 12's OB30 note
                     records that this project runs ONE standard FB plus the
                     F-runtime (the two-FB assumption was the shared-project
                     case); the owner decision and its date are named where
                     the change is described.
forbidden:           [changing any behaviour beyond describing the as-built
                      one, touching the safety SPEC (separate brief), editing
                      docs/interfaces/, mentioning any deadline]
```

Owner decision (2026-07-30, from the TIA session handover): the forklift TIA
project (safe_amr) contains no demo cell — no FB_DemoCellControl, no
DemoCellLink DB, none of M3's nodes. The bridge watchdog was therefore built
inside FB_ForkliftTeleop, reading ForkliftLink.BridgeHeartbeat, with the same
stale window and boot polarity the cell used. No new server node; the interface
untouched; the rest of section 7 verbatim.

Git: repo-local owner identity; pathspec-scoped commit of exactly SPEC.md plus
your report docs/reports/m4f-04j-asbuilt-bridge-watchdog.md; message style
`docs(plc): record the as-built bridge watchdog`.
