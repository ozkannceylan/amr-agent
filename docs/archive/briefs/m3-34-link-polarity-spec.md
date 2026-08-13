# Brief m3-34 — link boot polarity, the reset guard, and the 4.11 procedure

gate:                M3
agent:               plc
goal:                SPEC.md's link verdict is false until the heartbeat is seen alive, the stuck-reset guard survives a restart, and §11's belt-plausibility test uses a method that can actually latch
invariants_touched:  none
inputs:              [plc/demo-cell/SPEC.md (§6.1, §6.7, §11 T4.9b and T4.11, §12), docs/LESSONS.md (the 2026-07-28 rows on link polarity and the 4.11 window method), docs/briefs/m3-33-evidence-writeup.md (the T4.9b and T4.11 timeline sections), plc/demo-cell/evidence/watch-table/ (read only)]
deliverable:         plc/demo-cell/SPEC.md
done_when:           §6.1 specifies BridgeLinkOk as FALSE until the heartbeat has been observed to change at least once since CPU start (and states the boot-window consequence it closes); §6.7's ResetDeviceFault behaviour is re-derived against the corrected verdict so a reset held across any restart cannot clear latches at link-up (T4.9b's recorded failure becomes impossible by construction); §8's cold-start narrative and §11 T4.9b are reconciled to the corrected boot behaviour; §11 T4.11's latch step is re-specified onto the §12 item 6 fault-injection facility (reaction path kept as demonstrated); and the owner's implementation delta is stated precisely
forbidden:           [editing files outside plc/, changing the heartbeat mechanism itself or anything bridge-side, weakening the no-auto-resume or edge-triggered-reset conventions, redefining the M3 exit criterion, writing TIA code]

## The two findings, as recorded

1. **T4.9b failed as specified.** The build implements `BridgeLinkOk := NOT
   HeartbeatStaleTimer.Q`, which boots TRUE for the whole stale window. In
   that window the reset input's start value FALSE satisfied "seen open with
   the link up", ResetDeviceFault cleared on the first scan, and a reset held
   from before link-up registered as a rising edge the moment real samples
   arrived — clearing every latch (2026-07-28 17:02:19-36, code-confirmed).
   The spec's own §6.1 wording permitted this reading; fix the spec, then the
   owner fixes the build. Note the side effect to reconcile: with a
   pessimistic boot verdict, the §7 part-4 stop latch (gated on linkOk) will
   no longer latch from start-value contacts at boot — §8's cold-start
   description and the m3-26 cold-start observation must be restated
   accordingly, deliberately, not left contradicting.
2. **T4.11's window method cannot latch.** Zeroing the setpoint recovers the
   plant in ~100-150 ms, under BELT_FAULT_DELAY; five recorded presses prove
   the reaction path and disprove the latch step. Re-specify the latch test
   on §12 item 6 (bridge fault injection, explicitly opt-in), mark it
   blocked-on-that-facility, and keep the reaction-path demonstration as the
   run recorded it.
