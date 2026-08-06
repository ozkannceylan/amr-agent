# m5-61 — send the WARN line

    brief:               docs/briefs/m5-61-warn-sender.md
    status:              done
    invariants_touched:  none

## The one-line answer

**`WarningFieldClear` has read `True` for the first time in this project.**
A real box in Gazebo, inside the warning contour and outside the protective
one, produced a `WARN 0` line on the existing 45015 link, which the stand-in
writer turned into a `SafetyInputStandIn.WarningFieldClear` change and the
F-program turned into `WarningFieldClearValid` **17 ms later** — the limit
selector that had been permanently FALSE now moves in both directions.
**n = 4 warning intrusions, 4 member changes; n = 5 controls, 0 verdicts and
0 lines.** F3's precondition for tomorrow's F1 is met.

## What was built — three edits, all additive

| File | Change |
|---|---|
| `agv/forklift/scripts/field_evaluation.py` | `WriterLink` gained `warn_line()`, `publish_warn()` and `sent_warn`; the warning level is threaded through `service()` / `_poll_connect()` / `_connected()`; one `WARN` line is sent on every (re)connect **after** the `ZONE` line and at every transition; `close()` clears `sent_warn`; `cb_evaluate()` inverts OCCUPIED into the wire's CLEAR once, at the boundary |
| `agv/forklift/config.yaml` | `field.link.warn_clear_digit: 1` / `warn_occupied_digit: 0`, with the polarity argument and the F3 history beside them |
| `agv/forklift/EVIDENCE_FIELD_EVALUATION.md` | new **§18–§25**, written as the run landed |

**The protocol was not invented.** `bridge/STANDIN-WRITER-DESIGN.md` §3
already defines `WARN 1` / `WARN 0` on 45015 and the writer already parses it;
this node was made to match a receiving end that was built and running-tested
(m5-57). Nothing outside `agv/` and this report was written.

## The three things the brief said would not be relearned

**1. Silence is never readable as "clear", and a clear verdict is always a
fresh claim.** Tested rather than asserted (§21). The node was `SIGTERM`ed with
the writer live: `WarningFieldClear` went FALSE in **14 ms** with **no `WARN 0`
ever sent for it** — the writer converts silence on its own, which is why this
node deliberately adds nothing to its own death behaviour. On restart the first
two lines on the new connection were `ZONE 0` then `WARN 0`, both demanding;
the permissive level came back **2.06 s later**, when SF-04's clear-hold had
run again on the new node. It is re-earned, never inherited.

**2. The protective path was not disturbed.** Four warning-only intrusions
produced **zero `ZONE` lines**. A protective intrusion run with the sender live
reproduced the committed shape exactly, with the zone line ahead of the warning
line by 3 ms on the wire — the send order is structural (`publish()` before
`publish_warn()` in `cb_evaluate`, `ZONE` before `WARN` in `_connected`), not
incidental. No protective code path was edited and no committed protective
figure was re-measured or restated.

**3. The startup order was planned, not recovered from.** Writer first (it owns
both listeners and refuses a second instance by mutex), then Gazebo and the
node, so a live `WARN 1` existed before anything else was attempted. No reset
was needed, none was attempted, and the vehicle never moved.

## The hazard you asked me to measure rather than fix

**`FIELD_LINK_STALE_MAX` — the `WARN` sender cannot make it worse, and here is
the measurement.**

| Reading | Value |
|---|---|
| Traffic added by the sender | **10 lines in 6 min 14 s = +1.4 %** of the link's traffic |
| Stale reaps across the whole writer session | **0**, over **998.6 s** of link |
| Writer cycles / overruns / write failures | **23 291 / 0 / 0** |

**And the direction is favourable by construction.** The writer sets
`$st.linkLastMs` in its `WARN` arm exactly as in its `ZONE` and `PING` arms, so
an added line type can only ever **shorten** the maximum gap between lines.

**What is still not satisfied, and I did not silently fix it.** m5-59's rule is
*window ≥ 3 × ping period + one writer cycle*; this node pings at **2 Hz**,
giving **1.55 s against a 1 s window**, and m5-59 asks `agv/` to raise it to
5 Hz. **I did not make that change**, for two reasons: it re-times the
**protective** path's link, which this brief forbids me to disturb, and
`FIELD_LINK_STALE_MAX` is `plc/`'s to rule. It is a one-line config change
(`field.link.ping_period_s: 0.50` → `0.20`) and it wants its own brief with its
own protective-path re-observation. Measured position for that decision: **0
reaps in 998.6 s at 2 Hz**, one session on one machine, not a bound.

## files_changed

| File | What |
|---|---|
| `agv/forklift/scripts/field_evaluation.py` | **The deliverable.** The `WARN` sender |
| `agv/forklift/config.yaml` | The two digits, named with their derivation |
| `agv/forklift/EVIDENCE_FIELD_EVALUATION.md` | **§18–§25**, dated 2026-08-06 |
| `agv/forklift/evidence/m5-61-stimulus-{A,B,C}-*.log` | As-run stimulus records, every reposition read back |
| `agv/forklift/evidence/m5-61-stimulus-driver-{A,B,C}.py` | The drivers, so the run is reproducible |
| `agv/forklift/evidence/m5-61-consumer-witness-{warning,protective}.log` | The consumer's view, UTC-stamped |
| `agv/forklift/evidence/m5-61-observe-consumer-sequenceA.log` | The same sequence through the project's own instrument, `bridge/standin_writer/testing/observe_consumer.ps1` |
| `agv/forklift/evidence/m5-61-writer-session-nocycle.log` | The writer's session log, `CYCLE` stripped |
| `agv/forklift/evidence/field_evaluation/field-evaluation-20260806T19{5030,5723}Z-*.log` | The node's own transition logs, both sessions |
| `docs/reports/m5-61-warn-sender.md` | This report |

`plc/`, `bridge/`, `hmi/`, `sim/` and `docs/interfaces/` were **read and never
written**. The stand-in writer was run and its own gitignored session log was
read; nothing in `bridge/` was edited. Nothing was downloaded, compiled or
changed in TIA and no project was opened. **Nothing committed, no branch, no
dependency added.**

## Requests — work this brief could not do

| # | Request | Owner | Blocking? |
|---|---|---|---|
| 1 | **`ForkliftWarning.ForkliftWarningFieldOccupied` read `True` for the whole session, with both fields demonstrably clear.** It is the standard-side node fed by the ROS-topic carrier that still does not exist (m5-47's own hand-on 1). It sits at its start value and is not `agv/`'s to write | `bridge` + `interface` | No, but it is a lying lamp source if anything reads it |
| 2 | A `plc/` ruling on `FIELD_LINK_STALE_MAX` versus the keepalive, against the measurement above; and then an `agv/` brief for the 5 Hz ping **with a protective-path re-observation in the same run** | `plc`, then `agv` | No |
| 3 | The UTC-stamped read-only witness used in §20.2 is a throwaway. If it is wanted again it belongs beside `observe_consumer.ps1`; a PLCSIM-API reader may not live in `agv/` | `bridge` | No |

## open_questions

1. **`ForkliftStatus.ForkliftSpeedLimitActive` read `False` throughout, even
   with the warning field occupied.** That is finding **F4** — the warning
   ceiling is autonomous-mode only and the vehicle was in neither mode — and it
   lands in tomorrow's TIA session. This brief closes F3's half: the **limit
   selector** moves. The vehicle-side *effect* of the reduced limit remains
   unobserved and should not be claimed until F4 lands.
2. **No fresh latch was formed by the protective stimulus.** `ZoneStopDemand`
   and `SafetyResetRequired` stood `True` before, during and after the session,
   from an e-stop circuit open since before it. The protective run shows the
   channel reaching the F-program, not a latch forming; the fresh-latch form is
   m5-12b §4.3's and was not re-run.
3. **The rear device's last ingested scan again read 4.00 % invalid samples**,
   the same unexplained reading m5-47 recorded, still under the 5 % fault
   threshold and still unexplained.
4. **`agv/`'s keepalive rate is now load-bearing at both ends of one link.** It
   times the protective verdict's liveness and now the warning verdict's too;
   any future change to it re-times two paths, not one.

## next_suggested

Run the TIA session as written; after it, the acceptance run that re-records the
1.000 m/s drive-at-a-wall clip must have the field evaluation up and sending
`WARN 1` before the vehicle is asked for anything above 0.30 m/s.
