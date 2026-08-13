# m5-58 — full stack validation

    gate:                M5 — this is the run the showcase is recorded from
    agent:               bridge (owns the whole-chain run; reads every layer)
    goal:                Prove, on the real chain with no double anywhere, that the safety layer does what the project claims — the scanner slows then stops, the e-stop works, autonomous missions run, and safety acts in BOTH autonomous and teleoperated driving.
    invariants_touched:  none
    inputs:
      - docs/PLAN.md — "STATE OF THE WORLD", the layer table
      - plc/forklift/TIA-BUILD-PROCEDURE.md — the progress block and record table; the CPU is at 360/360
      - plc/forklift-safety/SPEC.md §11, plc/forklift/SPEC.md §14 and §14.16
      - docs/safety/SRS.md — AT-02, AT-03, AT-04 in their restated M5 forms, and AT-10/AT-11
      - bridge/EVIDENCE_ENVELOPE_BRIDGE.md, bridge/EVIDENCE_WARNING_SLOT.md
      - agv/forklift/EVIDENCE_FIELD_EVALUATION.md, EVIDENCE_STO.md, EVIDENCE_SPEED_LINK.md
      - hmi/EVIDENCE_HMI.md §J and §K, viz/EVIDENCE_MONITORING.md
      - docs/LESSONS.md
    deliverable:         docs/VALIDATION-M5.md and docs/reports/m5-58-full-stack-validation.md
    done_when:           Each of the five validations below has a verdict, the run that produced it, and — where it asserts something did not happen — a positive control in the same run.
    forbidden:
      - any double, stand-in server or test harness in place of a real layer. The writer is the real writer, the CPU is the real CPU, the HMI is the real page
      - improvising a source by hand. A value typed into a watch table proves the watch table works
      - claiming or implying an achieved PL, Category, SIL or PFH
      - downloading, compiling or changing anything in TIA — the owner's build is finished and signed
      - reporting a pass you did not observe, or averaging a run that behaved differently

---

## 1. What the owner asked for, in their words

Five things, in their order of priority:

1. **the laser scanners work** — does it slow down, and does it stop?
2. **the e-stop works**
3. **autonomous missions can be given**
4. **safety is active in autonomous**
5. **safety is active in teleoperation too** — *an operator driving at a wall
   must not be able to crash*

Everything below serves those five. If a sixth thing is interesting but not one
of them, it goes in the report, not in the run.

## 2. The chain, and it must be real end to end

`HMI → PLC standard program → OPC UA → bridge → vehicle → Gazebo`, with the
safety path `scanner → field evaluation → stand-in writer → F-program → mirrors
→ bridge → the vehicle's inhibit`.

**No layer may be a double.** This project has repeatedly found that the first
real run changes the job — the envelope gate was measured thoroughly against a
topic double and the live run rewrote the task. If a layer will not come up, say
so and stop rather than substituting.

## 3. The five validations

### V1 — the scanner slows, then stops

- **Slows:** an object in the **warning field** (3.35 m) → the standard program
  drops the ceiling to **0.20 m/s** → the vehicle actually slows. Report the
  commanded and achieved speed before and after, not just the ceiling value.
- **Stops:** the object in the **protective field** (1.35 m) → the F-program
  latches → the vehicle stops. Report the distance at standstill against the
  field boundary.
- **Control case, and it is what makes the rest mean anything:** an object
  plainly visible to the scanner but **outside** each contour → no verdict.
- **The latch holds** when the field clears. Recovery only by the monitored
  reset.

### V2 — the e-stop works

The cell e-stop through the real chain: demand latched, envelope withdrawn,
vehicle stopped, and **nothing resuming by itself**. Report the reaction time
from the e-stop to standstill, and the reset discipline — cleared on release,
not on press, and only with the cause gone.

### V3 — an autonomous mission can be given

A goal accepted and driven. If it completes, say so with the time and the error;
if it does not, say what happened. **The owner has ruled autonomy a prototype**,
so a route that needs several attempts is a finding to record, not a failure to
hide — but "we can command it and it goes" must be answerable yes or no.

### V4 — safety is active in autonomous

Mid-mission intrusion. The vehicle is driving under Nav2, an object enters the
protective field, and the **PLC withdraws the envelope** while Nav2 is still
asking for motion. Report what Nav2 does afterwards, honestly.

### V5 — safety is active in teleoperation

**The operator drives at a wall and cannot crash.** Hold a full-speed teleop
command toward an obstacle and show the vehicle stopping anyway, with the
operator's command still being sent. Report the closest approach.

This is the owner's own test and the most convincing one in the set. Give it its
own recording and its own numbers.

## 4. AT-10 and AT-11 — the speed link landed, so run them

**The link is proven** (m5-57, commit `cf01467`, report
`docs/reports/m5-57-writer-speed-link.md` — read it before you start). So run:
the speed monitor demanding on a limit exceeded, on a discrepancy, and on
silence; the sequencer's controlled stop then torque removal; and **after
torque removal the vehicle deaf to commands even with the envelope reopened**.

### Handover from m5-57 — three things that will cost you a run

1. **With no field source running, `WarningFieldClear` is FALSE**, the reduced
   limit is in force, and **no monitored reset can be accepted** while the
   vehicle is above it. This cost m5-57 a run. Plan the field source into your
   startup order, not into your recovery.
2. **`FIELD_LINK_STALE_MAX` is 1 s against a 1 Hz keepalive — zero margin.**
   Measured, the link was reaped 10 ms before the fourth keepalive. The
   direction is safe, but the real field evaluation may trip continuously and
   it now costs the warning verdict too. **If this blocks a validation, do not
   silently retune it** — the value is `plc/`'s to rule. Raise the keepalive
   rate on your side if that clears it, say exactly what you changed and why,
   and record the underlying finding for the plc agent either way.
3. **The machine was left clean:** writer stopped, mutex free, nothing on 45015
   or 45016, no vehicle-side process alive. `SpeedChainSeen` is TRUE and **only
   a cold start clears it** — so if a test needs it FALSE, plan the cold start.

Also unrun and left to you if it fits: the **CPU-restart republish** in its new
shape, where the speed members deliberately do not participate.

## 5. Rules that come from this project's own scars

- **Stillness is not evidence.** A stopped process and a real inhibit look
  identical. Every "it did not move" carries a **positive control in the same
  run** — the same command moving it when the inhibit is absent.
- **Every figure states its n.** One clean run is an illustration, not a result.
  Where a behaviour matters, repeat it.
- **Check the machine is yours** before each timed run and record what you
  checked. `gz service set_pose` returns true and silently does nothing without
  an entity id; read the pose back.
- **One evidence file per session**, uniquely named; a repeat that reuses its
  predecessor's names destroys the comparison.
- A run whose precondition was never confirmed is **discarded, not repaired**.

## 6. The deliverable is a document the owner can read

`docs/VALIDATION-M5.md` is written for the owner and for the showcase: five
sections, each with what was asked, what was observed, the numbers, and a plain
verdict. It is the thing they will narrate from, so it says what is proven and
what is not — and never blurs them.

## 7. Working discipline

- Read `docs/LESSONS.md` first.
- **Write each validation into the document as it lands.** Do not hold five for
  the end.
- **Do not commit.** The orchestrator commits by pathspec.
