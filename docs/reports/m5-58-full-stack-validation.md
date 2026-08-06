# m5-58 — full stack validation

    brief:               docs/briefs/m5-58-full-stack-validation.md
    status:              done (with two of the five validations reported as
                         not achieved, and the reason for each diagnosed)
    invariants_touched:  none

## The one-line answer

**The safety layer works and the run proved it: the scanner stops the vehicle,
the e-stop stops it, and an operator holding a full command at a wall cannot
crash — three runs, closest approach 1.11–1.33 m, with a positive control in
every one.** It also found the thing that would have been discovered on stage:
**the F-program's SLS and SS1 demands do not reach the vehicle**, and a
threshold band between two documents stops every autonomous mission at its
first metre.

## What was validated, and the verdicts

| | Verdict | n |
|---|---|---|
| V1 the scanner **stops** | **PROVEN** | 3 |
| V1 the scanner **slows** | **NOT AS ASKED** — the warning ceiling is autonomous-mode only; in teleop the warning field trips and the vehicle does not slow (observed twice, at 1.000 m/s through a 3.499 m trip). Autonomous leg not measured | 2 (the negative) |
| V1 the control case (object outside both contours → no verdict) | **PROVEN** | whole session |
| V2 the **e-stop** | **PROVEN**, ≈ 207 ms and ≈ 250 ms operator-to-standstill, plus three separate observations of the reset discipline | 2 |
| V3 an **autonomous mission** | **NOT ACHIEVED.** Goal accepted, path planned, vehicle moved 0.227 m, safety latched. Cause diagnosed and reproduced on demand | 3 attempts |
| V4 **safety in autonomous** | **NOT RUN** — blocked by V3. No result claimed | 0 |
| V5 the **operator drives at a wall** | **PROVEN**, and it is the strongest result in the set | 3 |
| AT-10 limit exceeded → demand | **PROVEN** on the CPU (over-limit → latch 135 ms, latch → torque-off 1 155 ms) | 1 |
| AT-11 torque removal → deaf to commands | **CANNOT BE RUN YET** — the demand does not reach the contactor; the observation available is the opposite one | — |

Everything above is in `docs/VALIDATION-M5.md` with its numbers, its runs and
its positive controls. **No PL, Category, SIL or PFH is claimed or implied
anywhere in either document.**

## The four findings that need a brief

1. **`SpeedMonitorDemand` and `TorqueOffDemand` reach neither the standard
   program nor the vehicle.** No mirror node under `Forklift/Safety/` (read
   back off the controller in force: four leaves, not six); no publisher on
   `/forklift/safety/torque_off_demand` (`ros2 topic info -v`: publisher count
   **0**, subscription count 1, the subscriber being `sto_contactor`); and no
   permissive conjunct — measured, the vehicle drove **2.4 s and 1.2 m at
   0.500 m/s** with all three demands standing, and again **19 s at 1.000 m/s**.
   `plc/forklift-safety/SPEC.md` §11.2 already assigns this to
   `plc/forklift/SPEC.md`'s standard-side brief and to `interface`. **Two
   briefs, `plc/` and `interface/`.** This is the highest-value item in the
   report.
2. **The shaft-doubt band.** The motion observation calls the vehicle moving
   above **1.4 mm/s**; the speed monitor calls a reading near zero below
   **30.8 mm/s**. A healthy vehicle anywhere between them is diagnosed as a
   failed shaft — and **Nav2's from-rest speed is 0.025 m/s, inside the band**,
   so every mission latches within seconds of starting. Reproduced deliberately
   at a 0.02 m/s creep with the encoders reading 15–26 mm/s
   (`bridge/evidence/m5-58-consumer-creep-shaftdoubt.log`). Neither threshold
   is wrong alone and nobody derived the window between them — the same shape
   as the 2026-08-05 smoother/converter deadband. **`plc/` and `agv/` jointly:
   one admissible window, stated in one place.**
3. **Nothing sends `WARN` on the 45015 field link.** `field_evaluation.py` is
   the sender named by `plc/forklift-safety/SPEC.md` §11.2 and implements only
   `ZONE`. So `WarningFieldClear` is permanently `FALSE`, the 300 mm/s SLS
   limit is permanently enforced, and the 0.60 m/s envelope ceiling cannot be
   used without an over-limit demand. **`agv/` brief.** (This is the other half
   of m5-57's finding 2; both halves of the warning verdict now have an owner.)
4. **The field evaluation fail-safe-trips on scan staleness under load.** Seven
   trips this session, 30–160 ms each, at 30 s – 6 min intervals: with Gazebo
   software-rendering three lidars plus Nav2, AMCL, the bridge, the HMI and
   PLCSIM on one machine, the 10 Hz scan stream misses the node's 0.30 s
   window. The node is right; the machine cannot feed it. **`sim/` — a capacity
   finding that bounds what one showcase take can contain.**

## files_changed

| File | What |
|---|---|
| `docs/VALIDATION-M5.md` | **The deliverable.** Nine sections, written to be narrated from: the claim boundary, the boot state, the five validations with their numbers and positive controls, AT-10/AT-11, the findings table, a summary of what a showcase may and may not say, and the evidence index |
| `docs/reports/m5-58-full-stack-validation.md` | This report |
| `bridge/config/bridge.yaml` | The **warning group** declared on the commissioned configuration, after probing the server and reading `Forklift/Warning/ForkliftWarningFieldOccupied` back off the controller in force (LESSONS 2026-08-06). Without it the §14.16 ceiling has no producer |
| `bridge/tools/check_write_allowlist.py` | Its model of `bridge.yaml` updated to match — 7 inputs, 8 allowlist keys. Re-run: **all config-side checks pass** |
| `bridge/tools/observe_safety_mirrors.py` | **New.** Read-only OPC UA witness of the PLC's own view: 23 nodes at up to 20 Hz to CSV, transitions to the console. It is the second witness on a different protocol stack from the writer's consumer observer, and neither can echo the other |
| `bridge/standin_writer/standin_writer.ps1` | `-CommandFile`: the operator's commands read from a file through the **same** `Invoke-Command2`, same grammar, same refusals, same log. No new command and no new capability — it exists because a script-started writer has no console and could otherwise drive none of the three channels |
| `bridge/STANDIN-WRITER-DESIGN.md` | New §4.1 specifying the above, including the UTF-8-without-BOM requirement (a BOM is refused loudly, correctly, and confusingly) |
| `bridge/evidence/m5-58-*` | 7 gzipped mirror captures, 4 transition logs, 2 F-program consumer logs, the writer's whole session log. One file per run, named for the run |

**Written outside `bridge/`:** only `docs/VALIDATION-M5.md` and this report,
both named as deliverables by the brief. `plc/`, `hmi/`, `viz/` and `sim/` were
read and never written. **Nothing was downloaded, compiled or changed in TIA;
no project was opened.** Nothing committed, no branch, no dependency added.

**Two untracked files appeared under `agv/forklift/evidence/`** —
`field_evaluation/field-evaluation-20260806T181110Z-pid226902.log` and
`speed-link/safe-speed-link-20260806T181539Z-pid227432.log`. They were written
by the committed `agv/` nodes themselves as a side effect of running them, not
by this agent. The first is the correlated half of the writer's session log
that `plc/forklift-safety/SPEC.md` §7.6 requires, so it is probably worth
keeping; both are `agv/`'s to rule on.

## How the run was conducted

**No layer was a double.** Real writer against the real PLCSIM API, real CPU
(`safecell3`, signature `50573CD9`), real `hmi_server.py` with its own OPC UA
session, real Gazebo scanners and field evaluation, real bridge, real vehicle
with its STO contactor. The only substitution anywhere is the **operator's
keyboard**: the HMI page's request loop and the writer's console are driven
from files, both through the committed code paths. That is stated in the
document's opening.

**Every claim that something did not happen carries a positive control in the
same run** — the same command moving the vehicle with the inhibit absent. This
is applied in V1, V2 and V5 without exception.

**Every figure states its n**, and where a figure is one draw it says so.

## open_questions

1. **Should the warning field reduce speed in teleop as well as autonomous?**
   §14.16 bounds `ForkliftSpeedCeiling` only, and the teleop setpoint does not
   pass through it. Measured twice: the warning field trips at 3.499 m and a
   full-command vehicle continues at 1.000 m/s to the protective boundary. This
   may be exactly what is intended — but it is not what a viewer will assume
   from a teleop clip. **A design question for `plc/`, not a defect.**
2. **After a safety latch, re-entering a drive mode needs a fresh mode-request
   edge**; holding the request through the latch does not re-enter. Observed
   twice. Correct restart discipline — worth a line in the procedure, because
   on stage it will look like a fault.
3. **The motion-present observation flaps** between `TRUE` and `FALSE` roughly
   twice a second while the vehicle is at rest under load. Bounded and
   fail-safe, but it is what puts `MotionPresent` `TRUE` beside a near-zero
   reading, and it is finding 2's other half. `agv/`.
4. **`FIELD_LINK_STALE_MAX` = 1 s against a 1 Hz keepalive** — m5-57's open
   question 1, still open, still `plc/`'s. It did not cost this run: the field
   evaluation pings at 2 Hz.
5. **Writer cadence over a long session**: 77 290 cycles, **1 561 overruns
   (2.0 %)**, **zero write failures**, eleven writes per cycle, across 64
   minutes with the whole stack contending. Against m5-57's 0.10 % on a quiet
   machine. One sample each; not a bound.

## Three lessons this run earned, for `docs/LESSONS.md`

*(the orchestrator's file, not mine — offered, not written)*

1. **A display that truncates a numeric string fabricates data.** A twelve-character
   truncation rendered `-6.58672215e-05` as `-6.586722156`, an impossible
   −6.6 m/s on a 1.5 m/s vehicle, and it was one step from entering this report
   as a defect. It was caught by counting samples over the traction limit —
   zero, in every run. **Format numbers as numbers; never slice a number as a
   string.**
2. **A seed or a goal given in the wrong frame is discarded, not repaired.**
   The first mission attempt used world coordinates where the stack wanted map
   coordinates, and the committed registration (θ = −0.0079 rad, t = (6.029,
   5.541)) exists precisely to convert them. Nav2 said so exactly — *"Start
   Coordinates … was outside bounds"* — and the run was thrown away rather than
   argued with.
3. **A reposition is verified in the simulator's frame, not the estimator's.**
   `gz service set_pose` returned `true` and the read-back on `/forklift/odom`
   read `0.0 0.0` both before and after, because odom starts at the origin
   wherever the vehicle is. The read-back proved nothing until it was moved to
   `gz model -m Forklift -p`. The 2026-08-06 lesson names the service; this is
   the same trap one layer along, in the *instrument* rather than the call.

## next_suggested

One `plc/` brief coupling `SpeedMonitorDemand` and `TorqueOffDemand` into the
standard program and out to the plant, with the `interface` mirror-node round
beside it — it is the difference between "the safety functions exist" and "the
safety functions act", and it is the only finding here that changes what the
showcase can claim.
