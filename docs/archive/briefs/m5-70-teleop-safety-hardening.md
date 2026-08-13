# m5-70 — harden the teleoperation safety story for the recording

    gate:                M5
    agent:               bridge (owns the whole-chain run)
    goal:                Make every safety claim the owner will narrate over a teleoperation recording rest on repeated measurement rather than a single draw, and remove the one link hazard that could spoil the take.
    invariants_touched:  none
    inputs:
      - docs/VALIDATION-M5.md — the current figures and §8.1's carefully worded sentence
      - docs/reports/m5-68-revalidation.md — what was measured, what was discarded, and why
      - docs/reports/m5-61-warn-sender.md — the keepalive measurement and why it was not raised
      - docs/reports/m5-59-validation-fix-triage.md — FIELD_LINK_STALE_MAX and its zero margin
      - plc/forklift-safety/SPEC.md §7.2 and §11
      - docs/LESSONS.md
    deliverable:         docs/VALIDATION-M5.md updated, and docs/reports/m5-70-teleop-safety-hardening.md
    done_when:           Every teleoperation safety claim states an n greater than one, the discarded e-stop leg has a successor with a positive control, and a full-length teleoperation run completes with no stale reap.
    forbidden:
      - touching TIA, or anything under plc/ except as a request in the report
      - changing a threshold to make a run pass
      - carrying forward any figure not measured against F-signature 29FD2C52
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. Why this brief exists

**Owner ruling:** autonomy is not forced. The showcase will be recorded with
**teleoperation**, and what must be shown is that the **safety functions are
functional and active while a human drives.**

That narrows the target and raises the bar on what is left. The safety chain is
proven — but several of the figures the owner would speak over are **n = 1**,
one leg was discarded, and one link hazard could spoil a take. Fix those three
things and the recording rests on measurement.

## 2. What is thin, and what to do about it

### a. The full-command stop is n = 1

m5-68 measured the vehicle at full command falling to 0.20 m/s in the same
50 ms sample as the warning trip and stopping **1.47 m** short. One run, one
heading, unladen.

**Repeat it.** Enough times to state a distribution rather than a figure, and
across more than one approach heading. Report the spread, not just the best.

### b. The e-stop leg was discarded, correctly

`v2r2` was thrown away because there was **no motion before it**, so it had no
positive control. That was the right call. It now needs a successor: the e-stop
measured with the vehicle demonstrably moving first, and repeated.

### c. The "straight" qualifier is real and must survive

m5-68 found that after a full-lock turn the vehicle rested **0.29 m** from an
object, because the protective contour is a straight corridor a turn escapes.
`VALIDATION-M5.md` §8.1 writes the supported sentence and deliberately never
writes the bare one.

**Do not try to make the qualifier go away.** Measure it properly instead: how
close, at what steer angles, repeatably. A limitation the owner can state
precisely is an asset on stage; one they discover mid-question is not.

## 3. The link hazard, and it gates the recording

`FIELD_LINK_STALE_MAX` is **1 s against a 2 Hz keepalive**. m5-61 measured
**0 stale reaps across 998.6 s**, so it is not fragile today — but the judge
found that after F4, **one mid-clip stale reap costs a visible ~2 s slowdown**
in a 1.000 m/s take. That is a spoiled recording.

Raise the keepalive. Two constraints m5-61 named when it declined to do this
itself, and both hold:

- it **re-times the protective path's link**, so the protective path must be
  **re-observed in the same run** and shown unchanged;
- **`FIELD_LINK_STALE_MAX` itself belongs to `plc/`.** If the fix needs that
  constant to move, request it — do not change it.

Then prove it: a **full-length teleoperation run**, at least as long as the
intended take, with **zero stale reaps** and the protective path still behaving.

## 4. The rules

- **Stillness is not evidence.** Every "it did not move" carries a positive
  control in the same run.
- **Every figure states its n**, and where a distribution exists, report the
  distribution.
- A run whose precondition was never confirmed is **discarded, not repaired** —
  m5-68 discarded three and was right to.

## 5. What the document must end up saying

`docs/VALIDATION-M5.md` is narrated from. When you are done it must let the
owner say, without hedging and without overclaiming:

- what the scanner does at the warning boundary, with an n
- what it does at the protective boundary, with an n
- what the e-stop does, with an n and a positive control
- **what the system does not cover** — the turn case, the laden case, and
  anything else you find

Write the last one as plainly as the first three. It is the part that makes the
rest credible.

## 6. Working discipline

- Read `docs/LESSONS.md` first.
- Write results as they land.
- **Do not commit.** The orchestrator commits by pathspec.
