# m5-68 — re-validate the whole chain against F-signature 29FD2C52

    brief:               docs/briefs/m5-68-revalidation-29FD2C52.md
    status:              done (7 of the 9 items have a verdict with its n;
                         items 2 and 5 are reported NOT ACHIEVED / NOT RUN
                         with the cause diagnosed, and the cause is not safety)
    invariants_touched:  none

## The one-line answer

**Item 1 passed, so everything after it ran: the 0.02 m/s creep no longer forms
a demand, with the encoders measured inside the band that used to stop it — and
the two results the exercise existed for both landed.** A teleoperated vehicle
at **full command** now falls to **0.20 m/s** on a warning trip and stops
**1.47 m** short of the obstacle with the command still held, and the
**torque-off demand reaches the plant live against the CPU** — six leaves,
publisher count 1, the contactor opening six times and refusing **95 475**
commands at the traction terminal. Items 2 and 5 (an autonomous mission, and
safety during one) did not happen, and the cause has **moved off the safety
layer**: the committed spawn pose is outside the region the committed planner
will plan from, and this machine cannot hold the autonomy stack up beside the
rest.

## The nine items, in the owner's order

| # | Item | Verdict | n |
|---|---|---|---|
| 1 | §3 shaft-doubt band | **PROVEN — the reproduction does not reproduce.** 30.0 s of creep, both encoders in 15–26 mm/s in 176 of 262 F-samples, `ShaftDoubtTimer.Q` / `SpeedMonitorDemand` / `Ss1Demand` / `TorqueOffDemand` all **0 of 262**. Positive control inside the run: `ShaftDoubtNow` still asserts (3 times, 115/112/465 ms) — the term is alive, it just no longer holds for `SHAFT_DOUBT_TIME` | 1 run, 262 samples |
| 2 | §3 autonomous mission | **NOT ACHIEVED.** r1: goal ACCEPTED, **0 plans published**, no safety demand at any point. r2: not issued, the action server had died. The band is no longer the cause | 2 attempts |
| 3 | §1.2 / §5 teleop slows | **PROVEN — the headline new result.** Full command 1.000 m/s → **0.20 m/s** in the same 50 ms sample as the warning trip, complying in **0.40 s** against a 2.30 s budget, then a protective stop at 1.47 m | 3 trips, 1 at full command |
| 4 | §6.2 the demand reaches the plant | **PROVEN LIVE against the CPU, no double.** 6 leaves; bridge resolves **22 of 22** nodes on the committed unedited config; `publisher count 1`; contactor latched 6 times, **95 475** commands refused; `torque_off_applied` `true`. Same-run positive control | 6 episodes |
| 5 | §4 safety in autonomous | **NOT RUN** — blocked by item 2 | 0 |
| 6 | §0 boot state | **MEASURED**, two new rows: `SpeedMonitorDemand` `False`, **`TorqueOffDemand` `True`** — the vehicle boots deaf | 100 samples, 0 transitions |
| 7 | §2 e-stop | **PROVEN.** circuit → demand 71 / 79 / 41 ms; operator → standstill 271 ms (from 0.250 m/s) and 241 ms (from 0.050 m/s). One run's e-stop leg **discarded** for want of a positive control | latency 3; standstill 2 |
| 8 | §6.1 AT-10 / SS1 | **AT-10 NOT RE-MEASURABLE** — `SpeedOverLimitNow` FALSE in every sample, because the clamp now keeps the vehicle inside the limit. SS1's second stage measured: **0.95 s** and **1.016 s** against `SS1_TIME_MAX` 1 s | AT-10 0; SS1 2 |
| 9 | §1.1 scanner stops | **PROVEN, and it is a different program.** 3 protective latches; the fully recorded one stops **0.25 s** after the demand, **0.046 m** of overshoot, closest approach **1.468 m**, command held throughout | 3 latches, 1 timed |

## The narration question, answered

**No — the sentence still needs a direction qualifier, but the qualifier has
changed from an open gap to a small evidenced one, and it is now carried by a
measurement rather than a caveat.**

What F1 asked for is supplied: teleop **is** slowed by the warning field, and the
torque-off demand **does** reach the plant. What remains:

1. the full-command stop is **n = 1**, one heading, zero approach angle,
   unladen, steering straight;
2. **a turn escapes the contour** — the protective field is a straight corridor
   in the vehicle frame, and after a full-lock turn the vehicle came to rest
   **0.29 m** from an object on the process channel; no stop out of a turn was
   measured;
3. the tread-versus-body residual `m5-59` §3 records is **untouched and
   unexercised** — at full lock the clamp held the vehicle so far under the
   ceiling that no over-limit ever formed.

The supported sentence is written out in `docs/VALIDATION-M5.md` §8.1 and its
qualifying word is **straight**.

## Discipline — what was discarded rather than repaired

- **`v2r2`'s e-stop leg.** Its mode-request edge was consumed before the drive
  command, so the vehicle was not moving when the circuit opened. Reported as
  discarded; its latency, its refused reset and its post-recovery positive
  control are kept because none of them depends on prior motion.
- **`v1r1`'s protective stop** fell in a gap between two captures, so it proves
  the stop by before-and-after state and contributes **no timing or distance
  figure**.
- **`v3r2`** produced no mission result and is reported as not run, not as a
  navigation failure.
- Every reposition was **read back** before the run that used it, and the
  machine was swept by process identity on both transports before the timed
  runs, with the sweep excluded from itself.
- Every writer was stopped and verified gone **before** anything was archived;
  every archive passes `gzip -t`.

## files_changed

| File | What |
|---|---|
| `docs/VALIDATION-M5.md` | **The deliverable, rewritten.** Signature banner at the top, the claim boundary, a verdicts-at-a-glance table, the boot state, V1/V2/V3/V4/V5, AT-10 / SS1 / the demand reaching the plant, 11 findings, what a showcase may and may not say, the narration answer, and the evidence index. **No figure from `50573CD9` survives anywhere in it** — swept by value, not by memory |
| `bridge/tools/observe_safety_mirrors.py` | Extended to the **six** `Forklift/Safety/` mirrors, after probing the server rather than from the node model alone; the two new columns added to the watched set and the docstring's count corrected |
| `bridge/tools/summarize_mirrors.py` | **New.** Reads a mirror capture back three ways — transitions, a `--window` slice row by row, and a `--summary` of first/last/distinct per column. It is how every "it did not change" claim in the document is *read off a capture* rather than asserted. It computes nothing about the plant |
| `bridge/evidence/m5-68-*` | **42 files, 1.2 MB.** 18 mirror captures, 18 page captures, 2 PLCSIM-API consumer logs, the writer's session log, the field evaluation's log, the contactor's episodes, the bridge console and one plan record |

**Written outside `bridge/`:** only `docs/VALIDATION-M5.md` and this report, both
named as deliverables by the brief. `plc/`, `agv/`, `hmi/`, `sim/` and
`docs/interfaces/` were read and never written. **Nothing was downloaded,
compiled or changed in TIA and no project was opened.** Nothing committed, no
branch, no dependency added.

**Two files the committed `agv/` nodes wrote themselves as a side effect of
running:** `agv/forklift/evidence/field_evaluation/field-evaluation-20260807T064053Z-pid265966.log`
and a `speed-link/` sibling. They are `agv/`'s to rule on; a copy of the first is
archived under `bridge/evidence/` because §3.3's counts are read from it.

## Requests — work this brief could not do

| # | Request | Owner | Blocking? |
|---|---|---|---|
| 1 | **Isolate the standard program's third permissive conjunct.** Every standing `SpeedMonitorDemand` this session was accompanied by a process obstacle latch, so the refusal was over-determined. One run in open floor — provoke a shaft-doubt demand out of a slow full-lock stop with nothing else standing, then hold a full command — closes F1's last half | `plc/` or a bridge run | No; F1's plant half is proven |
| 2 | **`ForkliftStatus.ForkliftSpeedLimitActive` read `False` in every sample of every run**, including the three in which the teleop clamp was demonstrably in force. Whatever it reports, it is not the clamp, so it cannot be the lamp `m5-59` §3 recommends | `plc/` (what it means), then `hmi/` | No |
| 3 | **A start pose inside the planner's region.** The committed spawn sits at the corner of the committed grid; with `allow_unknown false` and a 0.769 m inscribed radius, `SmacPlannerHybrid` publishes no plan from it. This is what blocked items 2 and 5 | `sim/` + `agv/` | **Yes — it blocks V3 and V4** |
| 4 | **The protective contour models a vehicle going straight** (finding 7). After a full-lock turn the vehicle rested 0.29 m from an object. A swept-path question, and it bounds the "cannot crash" claim | `agv/` | No, but it is the narration's qualifier |
| 5 | **Simulation capacity** (finding 9): 13 fail-safe intrusions and 13 motion-observation gaps against 3 genuine intrusions, one cluster latching three demands while the vehicle stood still | `sim/` | No, but it bounds one showcase take |
| 6 | `Link/BridgeLinkOk` is still not addressable on the controller in force (`BadNoMatch`) | `plc/` + `interface` | No |
| 7 | `docs/TODO.md` / `docs/PLAN.md`: F1, F2, F3 and F4 are closed by this run except for request 1 | orchestrator | No |

## open_questions

1. **The narrowed window still forms a demand on the stop transient out of a
   full-lock creep**, observed twice. It is a `plc/forklift-safety/SPEC.md`
   §11.1b not-covered row arriving in a live run rather than a new defect — but
   it will look like a fault on stage and belongs in the operator's briefing.
2. **`TorqueOffDemand` does not form on an e-stop**, observed three times. That
   is the specification (`Ss1Demand := ZoneStopDemand OR SpeedMonitorDemand`,
   `EStopDemand` deliberately absent, SRS B4). Worth saying out loud before the
   mirrors show it on stage.
3. **Input-class nodes hold the previous session's values between sessions**,
   one of them in the permissive direction. Nothing rests on it here; the
   instrument that separates "not yet written" from "clear" is
   `Link/BridgeHeartbeat` advancing.
4. **Whether the bridge's 20 Hz latency capture should be archived at all.**
   This session's is 233 MB and no figure rests on it; it was left outside the
   repository.

## next_suggested

One `sim/` + `agv/` round giving the autonomy scenario a start pose inside the
planner's region, then a single session that runs only the mission and the
intrusion into it — items 2 and 5 are now one staging problem away, and nothing
in the safety layer stands between the document and them.
