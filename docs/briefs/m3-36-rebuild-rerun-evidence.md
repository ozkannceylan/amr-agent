# Brief m3-36 — write the §6.8 rebuild re-runs into the evidence

gate:                M3
agent:               bridge
goal:                the five re-run steps are recorded against the corrected build, and the outstanding rows they close are closed
invariants_touched:  none
inputs:              [bridge/evidence/*rerun68*, bridge/evidence/plc-observe-2026-07-28-t45-rerun.csv.gz, bridge/EVIDENCE_LATENCY.md (Section B part 2, §B2.12 rows 14-21), bridge/EVIDENCE_SIGNAL_LOSS.md, bridge/EVIDENCE_LIFECYCLE.md, plc/demo-cell/SPEC.md §6.8 and §11, docs/reports/m3-34-link-polarity-spec.md, the timeline below]
deliverable:         bridge/EVIDENCE_LATENCY.md and bridge/EVIDENCE_SIGNAL_LOSS.md (one logical change)
done_when:           a new dated subsection records the five re-runs against build E with a verdict each; every §B2.12 row these close is marked closed with a pointer, and the rows they do not close say what is still missing; the rewrite-on-restart figure is derived from the committed log rather than copied from this brief; and the observer's blind spots are stated rather than glossed
forbidden:           [changing any earlier figure, re-running anything, editing code or config, editing files outside bridge/, claiming T4.11b or the T4.11 reaction re-record as done, calling the gate closed — that is the verifier's ruling]

## Build E

`plc/demo-cell/SPEC.md` §6.8 as committed at `0080bff`, implemented by the
owner and downloaded 2026-07-28 ~19:15. Owner's pre-run verification with the
bridge down: `HeartbeatStaleTimer.PT` `T#500MS`, `HeartbeatSeenAlive` TRUE
(the bridge had written briefly after the download), `BridgeLinkOk` FALSE,
`ResetDeviceFault` **TRUE** (the re-arm working — it was cleared-and-stuck in
build C/D), `LinkLostLatch` TRUE, `ProcessStopLatch` **FALSE** (the corrected
signature: the panel is no longer accused of a stop never seen), block
comparison circles solid green. Record that verification as the build's
provenance.

## Timeline, wall clock 2026-07-28 (orchestrator transcript)

**4.8** — pre-check 19:20:5x with the bridge down: PLC at start values,
`BridgeLinkOk` FALSE, heartbeat static (observer row in `o68_pre`, not
committed; the committed observer file starts later — say so). Fresh bridge
19:20:57; the R3 withheld line shrank input by input (4 → 3 → 2 → 1) as
`stop`, `process_stop`, `start`, `reset` were published 3 s apart; heartbeat
began 19:21:19 only after the seventh input. Link TRUE by 19:21:20.

**4.2** — 30 s hands-off from 19:21:26: no state change, `CellCycleRunning`
FALSE throughout, `CellResetRequired` TRUE (the `LinkLostLatch` from the
outage). No auto-resume.

**4.3** — reset 19:21:56 → latches cleared 19:21:58 and **nothing moved**;
separate start 19:22:05 → cycle ran, presence TRUE 19:22:15, clean end
19:22:26.

**4.9b, bridge-restart form (the form that matters — see the 2026-07-28
LESSONS row).** Process-stop pressed 19:22:29 to latch. Bridge `kill -9`
19:22:36. Bridge restarted 19:22:40 and `reset TRUE` published as the first
reset sample of the new session — the contact held from before link-up.
Heartbeat began 19:22:47, link TRUE 19:22:48. **The latches did not clear**:
`CellProcessStopActive` and `CellResetRequired` stayed TRUE through 19:23:10
while the observer confirmed `PanelResetPressed` TRUE at the PLC. Release
alone did not clear them (19:23:15). A fresh edge cleared them 19:23:16.
This is the exercise of the per-link-session guard and it is the pass build C
could not produce.

**4.5** — cycle started 19:25:12, belt transporting. Owner took the CPU to
STOP and back to RUN around 19:25:43. Three things to record together:
1. The bridge **detected the restart under a live session** — committed log
   line: `BridgeHeartbeat reads 0 but this session last wrote <N>` — and
   rewrote **7 of 7** input nodes. Derive the detection-to-rewrite interval
   from the two committed log timestamps yourself and quote that; it closes
   the F5 finding of part 2, whose comparable figure was 4 min 31.1 s.
2. The PLC's reaction: cycle down, `CellResetRequired` TRUE by 19:25:44 (the
   link-lost latch), and **`CellProcessStopActive` stayed FALSE** — the
   corrected signature. In build C the reverted stop contacts latched a
   process stop; state the contrast and cite part 2's §B2.12a captures as the
   before-side.
3. Recovery: reset 19:29:11 cleared the latch, separate start 19:29:18 ran a
   full clean cycle with presence at 19:29:25, clean end 19:29:35.

## Observer blind spots to state, not gloss

The 5 Hz observer file recorded **no** heartbeat decrease and **no**
`BridgeLinkOk` FALSE sample across the restart, because the revert-and-rewrite
window was far shorter than its 200 ms period. The evidence for the drop is
the 20 ms-resolution PLC reaction (the link-lost latch appearing) plus the
bridge log; the observer's silence is a sampling artefact and must be labelled
as one. Do not present it as "the link never dropped".
