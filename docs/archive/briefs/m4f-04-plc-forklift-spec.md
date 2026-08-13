# Brief m4f-04 — PLC forklift teleop program specification

```
gate:                M4
agent:               plc
goal:                plc/forklift/SPEC.md specifies FB_ForkliftTeleop completely
                     enough for the owner to build it in TIA Portal from the SCL
                     sketch alone.
invariants_touched:  none
inputs:              [docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      docs/interfaces/opcua-nodes.md section 10 (AUTHORITATIVE for
                      every node name, type, range and writability — where this
                      brief disagrees, that doc wins and the disagreement goes in
                      your report), plc/demo-cell/SPEC.md (structure template),
                      docs/LESSONS.md (binding, see list below)]
deliverable:         plc/forklift/SPEC.md
done_when:           the spec mirrors the demo-cell section structure §1-§12; every
                     requirement below appears with named constants; the SCL sketch
                     compiles by inspection (no undeclared symbol, every timer PT
                     explicit at the call site); §9 defines watch table "Forklift
                     M4 gate"; §10 gives the TIA click-path including the
                     server-interface additions per the interface doc's ruling and
                     the after-download solid-green check; §11 is an owner-executable
                     T5 procedure whose pass counts derive from its own step tables;
                     §12 lists what is deliberately not specified.
forbidden:           [editing plc/demo-cell/SPEC.md, editing docs/interfaces/,
                      inventing node names not in the interface doc, any claim that
                      any function here is a safety function, F-CPU content,
                      mentioning any deadline]
```

## Logic requirements (each traces to a LESSONS entry where noted)

1. **Structure.** FB_ForkliftTeleop, instance DB ForkliftTeleop_DB, called from the
   existing OB30 (20 ms) after FB_DemoCellControl. Global DBs per the interface
   doc's ruling. OB1 stays empty.
2. **Links.** BridgeLinkOk is CONSUMED from the existing status DB —
   FB_DemoCellControl stays its only owner (invariant 10). HmiLinkOk is computed
   here from HmiHeartbeat with the boot polarity rule: FALSE until the heartbeat
   has been seen to change at least once, stale window HMI_STALE_WINDOW := T#500MS
   (LESSONS 2026-07-28 link-boot-polarity). Timers: called unconditionally with
   IN as the state test, never inside a conditional branch that exits with the
   state; PT explicit at every call site (LESSONS dwell-timer and in-force-PT
   entries).
3. **Mode.** TeleopActive := HmiTeleopEnable AND HmiLinkOk AND BridgeLinkOk.
   Motion permissive additionally requires: no ObstacleStopLatch, all vehicle
   inputs plausible. Keep the two sets separate — a live-world set the reset
   tests, and a permissive set that adds the latches (LESSONS reset-precondition
   entry: a latch is never a term in its own clearing condition).
4. **Plausibility, affirmative form** (LESSONS analogue-validity entries): each
   Real vehicle input gets valid := (LOW < x) AND (x < HIGH) with the fault branch
   in the ELSE; windows from the interface doc. ANY implausible vehicle input
   drops motion permissive. Sweep every analogue input in this document — none
   exempted.
5. **Obstacle latch.** ObstacleStopLatch sets on ForkliftObstacleInStopZone TRUE
   (level) or implausible obstacle inputs; ForkliftResetRequired mirrors it.
   Clearing: only by monitored reset — HmiResetRequest rising edge (edge-triggered,
   CLAUDE.md §9; a held button is not a reset), evaluated only while the zone reads
   clear, inputs plausible and both links up. No automatic resume ever.
6. **Speed cap.** forkRaised from ForkliftForkHeight vs FORK_HEIGHT_SLOW_THRESHOLD
   (0.50 m); cap TRACTION_SPEED_CAP_RAISED (0.30 m/s) vs TRACTION_SPEED_MAX
   (1.50 m/s). ForkliftSpeedLimitActive mirrors the cap being in force while
   teleop is active. Implausible height ⇒ treat as raised AND inhibit fork motion.
7. **Setpoint formation** (LESSONS analogue-gating entry): each of
   ForkliftTractionSpeedRef, ForkliftSteerAngleRef, ForkliftForkSpeedRef is
   assigned in exactly one statement with a mandatory ELSE driving it to 0.0.
   Traction := clamped HmiDriveCommand × cap. Steer := clamped HmiSteerCommand
   (returns to center when not permissive — document this consequence). Fork :=
   clamped HmiForkCommand × FORK_SPEED_MAX with direction-specific soft-limit
   aborts (LESSONS soft-limit entry: at or above FORK_TRAVEL_MAX only lowering
   permitted, at or below FORK_TRAVEL_MIN only raising; never a blanket
   permissive that strands the fork on a limit).
8. **Supervision reactions** (§8): HMI link loss ⇒ all three refs 0.0 within one
   scan of the stale verdict; bridge link loss ⇒ same, plus note the vehicle-side
   behaviour is the plant holding zero commands. State both as process reactions,
   not safety functions.
9. **§11 T5 procedure** — one scenario per roadmap M4 criterion (a)-(e): T5.1
   teleoperated drive, T5.2 fork to height with both soft-limit aborts, T5.3 speed
   cap with fork raised, T5.4 obstacle latch: entry, override of live commands,
   reset refused while occupied, stuck-button no-clear, monitored reset after
   clear, T5.5 HMI heartbeat loss mid-motion, T5.6 bridge session loss mid-motion.
   Each step names the stimulus, the observed node and the expected value.

Git: repo-local owner identity; pathspec-scoped commit of exactly plc/forklift/SPEC.md
plus your report docs/reports/m4f-04-plc-forklift-spec.md; message style
`feat(plc): specify the forklift teleop program`.
