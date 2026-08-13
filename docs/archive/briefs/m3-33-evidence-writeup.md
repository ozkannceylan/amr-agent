# Brief m3-33 — write the 2026-07-28 live run into the evidence documents

gate:                M3
agent:               bridge
goal:                EVIDENCE_LATENCY.md Section B is completed and EVIDENCE_SIGNAL_LOSS.md gains its PLCSIM section, from the committed artifacts of the 2026-07-28 owner-session run
invariants_touched:  none
inputs:              [bridge/evidence/*2026-07-28* (CSVs and logs, all gzipped), plc/demo-cell/evidence/watch-table/ (owner captures, timestamp-named), bridge/EVIDENCE_LATENCY.md, bridge/EVIDENCE_SIGNAL_LOSS.md, plc/demo-cell/SPEC.md §11, the timeline below]
deliverable:         bridge/EVIDENCE_LATENCY.md and bridge/EVIDENCE_SIGNAL_LOSS.md (one logical change)
done_when:           Section B's items are each filled or explicitly owner-outstanding with a reason; the §B.7 roster reflects this run step by step with verdicts (including 4.9b FAILED with its finding and 4.11 partial); EVIDENCE_SIGNAL_LOSS.md carries the PLCSIM section item 6 requires; every figure quoted reproduces from a committed artifact or is marked as a transcript observation with its timestamp; and the three artifact limitations below are stated plainly
forbidden:           [changing any m3-26 or earlier figure, re-running anything, editing code or config, editing files outside bridge/, claiming a pass for 4.9b or for 4.11's latch step, softening a finding]

## Artifact map and limitations

- `latency-2026-07-28-plcsim-t1t4.csv.gz` — 20 Hz per-event CSV, **window
  17:49–18:00 only**: the final clean cycle, the capstone L7 rounds, the full
  traverse and the 4.6 re-measure. LIMITATION 1: the bridge truncates the CSV
  at every start and the bridge restarted ~7 times, so earlier windows are
  lost at 20 Hz (LESSONS 2026-07-28).
- `bridgelog-2026-07-28-sessionA-t4-era.log.gz` — 1 Hz diagnostics 15:14–17:23
  (T4.1-4.10 era, first 4.6/4.6b/4.7, 4.9, old L7 rounds).
- `bridgelog-…-sessionB-t48 / sessionC-t49b / sessionD-final` — the 4.8 R3
  demonstration, the 4.9b run, and 17:49+ respectively.
- `plc-observe-2026-07-28-t4a-caseAB.csv.gz` — 5 Hz read-only observer through
  4.1/4.2/4.4, **including CurrentSessionCount for 4.10**.
- `plc-observe-2026-07-28-capstone.csv.gz` — 5 Hz through the capstone.
- `plc-observe-2026-07-28-final-cycle-press.csv.gz` — the final cycle's start
  press at 5 Hz (start=True, cmd 0.15, position marching).
- `cmdlog-*.gz` — LIMITATION 2: nearly empty, treat as absent.
- `plc/demo-cell/evidence/watch-table/` — 71 owner captures named by
  timestamp; map to events by time, reference by filename (read-only, outside
  your scope to edit).
- LIMITATION 3: the observer sees the server, not Group 4; PositionFrozen and
  friends exist only in the owner captures.

## Program builds during the run

Rebuild baseline `plc/demo-cell/SPEC.md @ 39a21b6`. Downloads during the day:
the three-delta build (dwell/belt/case-D, ~13:00), the PRESENCE_FILTER
constant fix (~14:38 in force), a full re-download restoring project/CPU
consistency (~17:33), BELT_SPEED ±0.10 (~17:35), restore ±1.00 (~17:45).
State which build each result was taken against.

## Timeline (orchestrator transcript, wall clock 2026-07-28)

T1 (all six): 15:06:16 start hold; 15:06:27 reset hold (1.1b); 15:06:37 stop
press → ProcessStop+ResetRequired latch (polarity); 15:06:49 process_stop
press; 15:07:00 reset clears. T1.4 re-run against the PT-fixed build:
17:14:37 reset, 17:14:48 running, presence TRUE 17:14:55 (ET filled 100 ms,
owner capture), clean end 17:15:06.

T2 (all eight): first full cycle 15:07:06 start → presence 15:07:18 → dwell →
return → clean end 15:07:29. T2.5: start 15:08:25, presence 15:08:37,
process_stop 15:08:36.127 → stopped+latched by 15:08:38.6 (box parked in
beam). T2.6: 30 s unchanged. T2.7 reset 15:09:17 (nothing moves). T2.8 start
15:09:26 → end 15:09:37.

T4.1 (A): cycle from 15:12:18, kill -9 at 15:12:27.385; observer: cmd 0.0,
cycle down, ResetRequired TRUE, link FALSE, heartbeat frozen 11873, session
count 2. Belt kept running in Gazebo (§8 residual). T4.2: restart 15:12:33,
30 s hands-off, no resume, first command 0.0. T4.3: reset 15:13:31, start
15:13:47, clean end 15:13:55. T4.4 (B): cycle from 15:13:55, SIGTERM
15:14:04.722; identical PLC state; session closed immediately (graceful).
T4.10: observer session-count transitions t=0→2, 20.89→3, 33.55→2, 110.7→1,
118.1→2 with the SIGKILL at t≈11.5-12 (anchor: heartbeat freeze in the same
CSV): SIGKILL hold ≈22 s (beyond the 10 s granted timeout — report raw, no
interpretation), SIGTERM immediate.

T4.6 first valid run (superseded by the re-measure): transport caught
16:38:10, gz kill 16:38:13.721, fault seen by 16:38:17.389 (1 Hz lag).
T4.7: reset REFUSED 16:38:23 (ResetRequired and DriveFault stay TRUE), start
inert 16:38:30; revive; readback live 16:38:50; reset honoured 16:38:57;
separate start re-ran the cycle 16:39:08. T4.6b (D i): dwell kill
16:33:32.399 (presence TRUE), step-30 command against dead cell, fault
16:33:36.428; presence stayed TRUE; PositionFrozen stayed FALSE (owner
capture); reset honoured immediately 16:33:50. Accidental D-iii at
16:32:24-49: gz killed with the cell idle, a start against the dead cell
faulted via D1 within ~1 s — record as the idle variant.

T4.6 RE-MEASURE (authoritative): forward transport 17:59:32, gz kill
17:59:35.618, ConveyorDriveFault TRUE by 17:59:38.417 — **2.79 s** at 0.25 s
poll granularity; derive the exact figure from the 20 Hz CSV (last changing
ConveyorBeltPosition → DriveFault TRUE) and quote that.

T4.5 (C): cycle started 16:51:00; owner STOP ~16:51:30 (session survived,
command frozen +0.15, belt kept running — record as the STOP residual), RUN →
warm restart: inputs reverted to start values, stop circuits read open,
process-stop latched, ResetRequired TRUE, command 0.0, nothing ran. FINDING
(write-cache): the bridge writes on change and never repaired the reverted
inputs; stop circuits stayed FALSE at the PLC until force-toggled (~17:05);
the monitored reset then cleared normally. Owner captures 17:16:56/17:17:12/
17:17:28 are the before/STOP/after triple of a second STOP-RUN.

T4.8: pre-check 17:00:07 (bridge down): all seven inputs at §3.1 start
values, heartbeat 0, link FALSE, latches set, session count 1. Fresh bridge
17:00:09; panel levels published one by one 3 s apart; the R3 withheld line
shrank input by input; heartbeat began 17:00:32 only after the seventh.

T4.9: 16:40:24 reset held, stop latched at 16:40:34, 10 s held — never
clears; released 16:40:44, fresh edge 16:40:55 clears.

T4.9b: FAILED as specified — fresh bridge 17:02:19 with reset held TRUE from
before link-up; heartbeat began 17:02:30; by 17:02:36 every latch was clear.
Root cause (code-confirmed): BridgeLinkOk := NOT staleTimer.Q boots TRUE for
the stale window, ResetDeviceFault cleared on the first scan, and the held
reset registered as an edge at link-up. Record as the finding, cite the
2026-07-28 LESSONS row, and cross-reference the m3-34 spec correction.

T4.11: reaction path DEMONSTRATED, latch step NOT testable as specified.
With ±0.10 downloaded, start presses at 17:30:45 and 17:36:50 produced
~100-150 ms speed blips to 0.15 in the CSV: C5 dropped the cycle and zeroed
the setpoint within one scan, but the plant recovered under the 200 ms
BELT_FAULT_DELAY so BeltFeedbackFaultLatch never formed. Cite the CSV blips.
Final clean cycle with restored constants: 17:51:50 start → presence
17:52:00 → clean end 17:52:11.

T3: cycle rate and latency statistics from the 20 Hz CSV window (count/min/
median/p95/max, never a bare mean); L7 from the capstone rounds
(process_stop presses 17:58:12, 17:58:36, 17:58:59) plus T2.5's press; CPU
cycle time (owner, TIA): shortest 1.004 ms / current 1.023 ms / longest
2.556 ms against the 20 ms OB30; session timeout granted as requested
(10 000 ms — min(request, cap)); environment per §B.0; invariant-8 network
path confirmed by m3-26 (unchanged).

Operational notes to record where relevant: one start press (17:49:38) was
lost to a --once publish race and never reached the bridge (tooling, not
program — CSV shows no write); the wedged-bridge misread at 17:41-46 was a
stale-log artifact on the orchestrator side, not a PLC event.
