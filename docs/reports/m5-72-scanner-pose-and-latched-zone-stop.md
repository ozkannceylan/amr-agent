# m5-72 — why teleop would not enter, and where the scanner is looking

    brief:               docs/briefs/m5-72-scanner-pose-and-latched-zone-stop.md
    status:              done — the vehicle was driven 7.83 m and watched doing it;
                         two findings are requests on other layers, named below
    invariants_touched:  none. No file outside agv/ was written, no parameter was
                         changed, and nothing in TIA, plc/ or PLCSIM was opened,
                         started, stopped or downloaded. The CPU stayed signed at
                         29FD2C52

## The one-line answer

**The scanner is right. Three separate things were wrong, none of them in
`agv/` code, and all three are now measured rather than argued: the e-stop
circuit had never been closed, a refused mode selection is consumed rather than
held, and — the finding nobody was looking for — a 310 ms hitch in the
simulator latches a protective stop with the field measurably clear, about once
every three minutes.** Teleoperation was never broken.

---

## 1. The scanner hypothesis is dead, and the returns are correct

The brief's leading hypothesis was that the front scanner's pose or frame is
wrong, so it observes a place the vehicle is not. **Refuted, at two vehicle
poses**, which is the test that separates a correct mount from a mount
displaced by a constant:

| Vehicle ground truth | front returns vs the nav lidar's view of the same racking |
|---|---|
| `x=-3.000 y=-5.500 yaw=0°` | median **0.072 m**, n = 156 |
| `x=+1.500 y=-5.500 yaw=45°` | median **0.017 m**, n = 114 |

A constant displacement would appear as the same non-zero median at both. It
does not. The nearest front return, `1.084 m at +137.5°`, is the vehicle's own
structure and falls inside the self-return clip band the node already declares.
And the demand's time profile is wrong for a mislocated sensor: the field went
`CLEAR` about 3 s after first scan in all four sessions logged that morning.

**Every field figure this project has measured was taken through a scanner
looking where the model says it looks.** That is the branch the coordinator
called "a much bigger finding", and it is closed.

**The owner's first screenshot was a true reading of a true event.** At
10:17:45 the vehicle really had been driven to a rack face and stood 1.507 m
from it — `front INTRUSION: 34 ray(s) inside, nearest 1.507 m` — inside a
contour reaching 2.210 m ahead. The reset attempted 50 s later, field still
occupied, was **correctly refused**.

## 2. The visual IS displaced, and it is cosmetic

All three `gz.msgs.LaserScan` streams publish `world_pose` as the **identity
pose**, while the front sensor's true world pose at the spawn is
`(-2.30, -5.05, 0.15)` yaw +45°. That anchors the drawn fan at the **world
origin** — which at the spawn pose is 3.00 m ahead of the vehicle and 5.50 m to
its left, in open aisle. Exactly where the owner sees it.

The reading is **byte-identical** after teleporting the vehicle 4.5 m and
rotating it 45°. So the fan does not follow the vehicle; it stands still while
the vehicle moves, and the apparent offset is therefore not constant.
**One look settles it for the owner: park the vehicle somewhere else and watch
whether the fan stays put.** `gz model --list` also returns exactly one
`Forklift` among 22 models, so the second-vehicle hypothesis is dead too.

`frame_id` and `ranges` are correct on all three sensors, and no node in this
repository consumes the advertised pose. **The Gazebo window is the one channel
that is wrong** — worth the owner knowing, because it is on camera.

## 3. What was actually blocking teleop, in order

**a. The e-stop circuit boots open and had never been closed.** The writer
session that was live when the owner asked (pid 7004, started 10:28:34) logged
its boot levels — `EStopCircuitClosed=False` — and then **not one `OPERATOR`
line for sixteen minutes**. `estop` has no link source; only the writer's
operator channel can close it. Confirmed by measurement, matching the
coordinator's read of `standin_writer.ps1:157`.

**b. The HMI RESET is not the F-side reset.** `plc/forklift-safety/SPEC.md`
§1.3 states it outright: `HmiResetRequest` is the **process** reset;
`SafetyInputStandIn.ResetButtonPressed` is the **SF-08** reset and is never a
client write. The owner was pressing the one that cannot clear an F-latch.

**c. A refused mode selection is consumed, not held.** After the reset cleared
every demand at 10:46:40.557, the mode sat at **0 for 82 s** with
`HmiDriveModeRequest` standing at 1 (Teleop). It entered 2.0 s after a fresh
**None → Teleop** edge. This is m5-71's closing note arriving as the thing that
actually stops a demonstration.

**d. And the one nobody was looking for — see §4.**

## 4. The finding this brief exists for: a spurious protective stop, measured

**At 10:39:27, vehicle standing still at the spawn pose, field measurably
clear, the protective channel opened for 94 ms and the F-side latched.**

    field_evaluation 10:39:27.889Z | ... front: nothing received for 0.310 s
        (limit 0.30 s) (front 0 ray(s) inside, rear 0)
    field_evaluation 10:39:27.909Z | SEND | ZONE 0
    writer           10:39:27.944Z | ZoneDeviceCircuitClosed := False
    writer           10:39:28.038Z | ZoneDeviceCircuitClosed := True

`front 0 ray(s) inside, rear 0` is the node saying nothing was in either field.
The verdict came from the **freshness rule**. `ZoneStopDemand` read `False`
over OPC UA at 10:38:12 and `True` at 10:43:44 with no other event between.

**How often, 180 s window, vehicle standing, GUI on:**

| Stream | n | median | q99 | max | gaps > 0.30 s |
|---|---|---|---|---|---|
| front scan | 1591 | 0.1117 s | 0.1495 s | **0.3676 s** | **1 (0.063 %)** |
| rear scan | 1591 | 0.1117 s | 0.1494 s | 0.3421 s | 1 (0.063 %) |
| `/clock` | 79 467 | 0.0020 s | 0.0067 s | 0.3330 s | 1 (0.001 %) |

`/clock` stalled in the same event, so **the whole simulator hitches** — this is
llvmpipe software rasterisation with the GUI attached, not a transport or node
problem.

**Two honest consequences.**

1. **`scan_fresh_max_s = 0.30` no longer means what its own comment says.** The
   comment reads *"THREE SCAN PERIODS"* against a nominal 10 Hz; the delivered
   period here is 0.1117 s, so the window in force is **2.69 delivered
   periods**. Three delivered periods would be 0.335 s — and the observed max
   was 0.3676 s, so even the parameter's own derivation would not have covered
   this event.
2. **I did not change it, and it should not be changed to make a demand go
   away.** It is a safety-relevant timeout whose direction is the demanding one.
   The derivation and the machine now disagree; by how much is recorded. The
   ruling is the owner's.

**The mitigation that changes no safety parameter is `./demo.sh up --headless`**
— it removes the render thread that produces the hitch. **Untested here**,
because testing it means restarting the owner's live stack mid-demonstration.
It is the first thing to measure next.

**The scanner is right and the world is wrong.** That is the brief's own
sentence and it turned out to be the answer twice: once for the visual, once
for the stall.

## 5. The bar for done: watched, not reasoned about

| Time (UTC) | Observed | By whom |
|---|---|---|
| 10:44:53.762 | `estop close -> EStopCircuitClosed := True` | **owner, at the writer console** |
| 10:46:39.297 | `reset pulse 800`, released 10:46:40.138 | **owner, at the writer console** |
| 10:46:40.557 | **`EStopDemand`, `ZoneStopDemand`, `SafetyResetRequired` all `False` in one sample**, 0.419 s after the release | the F-side monitored reset |
| 10:48:02.571 | `ForkliftDriveModeActive 0 → 1`, `VehicleModeApplied 0 → 1` | a fresh None → Teleop edge through the HMI's own `POST /control` |
| 10:48:15–24 | `TeleopActive True`, reference 1.000, **peak `ForkliftLinearSpeed` 1.000 m/s**, 37 samples above 0.01 m/s | traction held |
| 10:48:23.988 | released: reference 0.000, `TeleopActive` dropped, speed 0.000 | the deadman |

**Positive control on ground truth**, because stillness and motion must both be
shown (LESSONS 2026-08-06): `gz model -p` read `[-3.000000 -5.500000]` before
and **`[4.827640 -5.499050]`** after. **The vehicle travelled 7.83 m.** No
intrusion was logged across the whole run, which is the control case for §1.

Afterwards the vehicle was standing where its **rear** field is genuinely
occupied (`rear INTRUSION: 1 ray inside, nearest 2.628 m`) and was returned to
the spawn pose by the RUNBOOK's own `set_pose` recovery, with the entity id and
a read-back both times.

## files_changed

| File | Change |
|---|---|
| `agv/forklift/EVIDENCE_FIELD_EVALUATION.md` | **new sections 26–31**, dated 2026-08-07: environment, the dead scanner hypothesis, the visual, the spurious latch and its rate, the end-to-end run, and what none of it establishes |
| `agv/forklift/EVIDENCE_SENSOR_COVERAGE.md` | **new section 15**, the visual answer where a reader of the sensor document will look for it, pointing at the full measurement |
| `agv/forklift/evidence/m5-72/m5-72-state-watch-20260807T104609Z.csv` | the 5 Hz `/state` trace behind §5, 2217 rows, copied after its writer was verified stopped |
| `docs/reports/m5-72-scanner-pose-and-latched-zone-stop.md` | this report |

**No code was changed.** `field_evaluation.py`, `model.sdf` and `config.yaml`
were read and never written — there is no defect in them to fix, and the one
parameter a fix would have touched is the one the brief forbids moving.

Two untracked artefacts were written by the committed nodes themselves as a
side effect of the owner's run and are left in place:
`agv/forklift/evidence/field_evaluation/*.log` and a `speed-link/` sibling.

## Requests — work this brief could not do

| # | Request | Owner | Blocking? |
|---|---|---|---|
| 1 | **`RUNBOOK.md` and `demo.sh` never say a refused mode selection is consumed.** §3's closing note says to re-edge the selector "after any latch"; it does not say that a selection made *while* a demand stands is thrown away, which is the case the owner actually hit. Add it, and have `up` print it beside the boot state it already reads from the CPU | infra | **Yes, for the showcase** |
| 2 | **`demo.sh up` reads `EStopDemand True` from the CPU and does not tell the owner what closes it.** It prints the boot state; it should print the two commands — `estop close`, then `reset pulse 2000` at the writer — and say in one line that the HMI RESET is the *process* reset and reaches no F-latch (`plc/forklift-safety/SPEC.md` §1.3) | infra | **Yes, for the showcase** |
| 3 | **`demo.sh` declared the stack READY with `viz/` not serving.** Measured 2026-08-07 10:43: `http://127.0.0.1:8089/` returns connection refused. Whatever the ruling on whether the monitoring service should be on by default, a readiness check that passes with a declared component not answering is the gap | infra, and `viz/` for the service itself | No |
| 4 | **Rule on `scan_fresh_max_s`.** §4 records that its stated derivation ("three scan periods") and the machine's delivered period (0.1117 s) disagree, and that the observed stall exceeded even the derivation. This is an owner decision with a safety direction attached; an agent should not take it | owner, via ADR or a ruling | No, but it will re-appear on stage |
| 5 | **Measure the headless run.** Re-take §4's inter-arrival table under `./demo.sh up --headless` and say whether the over-limit rate goes to zero. If it does, the demonstration should be run headless and nothing else needs deciding | `agv/` or `sim/`, one short brief | No |

## open_questions

1. **The 0.063 % over-limit rate is one 180 s idle window on one machine.** It
   is an observed rate, not a bound, and m5-69 measured 6.1x under load. What it
   does establish is that the rate is **not zero**, so a demonstration long
   enough will meet a spurious protective stop.
2. **The 800 ms reset hold was accepted** where `RUNBOOK.md` §3 says 2000 ms.
   Which hold the F-program requires was not characterised; one acceptance is a
   sample, not a limit, and the RUNBOOK and the machine should be made to agree.
3. **m5-71's OQ2 is now explained in part and worse than it looked.** The rear
   protective contour reaches 3.225 m behind `base_link`, so in this warehouse's
   aisles the rear field is occupied at many ordinary parking places — the drive
   here ended in one. Whether the showcase should be staged around that, or the
   rear depth re-derived, is a directing and a `docs/safety/` question, not a
   parameter to trim.
4. **The `world_pose` finding is read off the message, not off the renderer.**
   That the message advertises identity is measured; that the GUI plugin is what
   consumes it is the explanation consistent with the geometry and was not read
   out of Gazebo's source.

## next_suggested

Run request 5 — one headless 180 s inter-arrival measurement — before the
showcase, because it is fifteen minutes of work and it decides whether the
demonstration can be driven for more than three minutes without a protective
stop nobody caused.
