# forklift_commissioning.md — the five M4 gate scenarios, as a runnable procedure

The M4 criterion in `docs/roadmap.md` names five things an operator must be seen
to do, plus a recorded showcase of all five. This file is how they are run: the
process start order, the operator's steps, the observable that proves each one,
and the artifact to capture while it happens.

**The gate closes on the owner's PLCSIM Advanced run and its recording.** Every
step marked **owner** is executed by the owner against the commissioned CPU.
Everything in this file labelled **REHEARSAL EVIDENCE** was produced against
`plc/forklift/double/`, a rehearsal stand-in on loopback port 4850 — not a PLC,
not PLCSIM, and not evidence for the gate. What the rehearsal establishes is
narrower and worth having anyway: that the procedure is executable, that every
observable it names exists and is reachable, that the steps happen in an order
that works, and that four things in the surrounding documents needed correcting
before the owner met them at the CPU.

**Nothing in this file is a safety function or a safety test.** The obstacle
stop, the fork-height speed cap and the fork soft travel limits are
standard-program **process interlocks** implementing no function of
`docs/safety/SRS.md` — not SF-02, SF-03, SF-04, SF-07, SF-09 — and carry no SIL
or PL claim (ADR 0008 D3). The protective stop, the e-stop chain and safe torque
off are onboard and hardwired, appear in no launch file, no world file and no
node in this procedure, and are not exercised by any step here (invariant 1).
The recording must say so out loud while each reaction is shown.

**Authority.** `plc/forklift/SPEC.md` §11 owns the six test procedures and their
Pass lines; this file does not restate them as an alternative and does not
redefine any gate criterion. What it adds is the part §11 leaves to the
simulation layer: which processes to start in which order, with which isolation
values, what to publish or move in Gazebo, and what to capture. Where a Pass
line and an observation disagree, §11 is the specification and the disagreement
is written down as a finding, never absorbed.

---

## 1. The loop, and the order it is started in

```
   operator ──▶ commissioning HMI ──▶  PLC standard program  ──▶ bridge ──▶ Gazebo
                (OPC UA client)        (S7-1500 / PLCSIM,          (OPC UA    arena
                                        the OPC UA server)          client)    + vehicle
                        ◀────────── status nodes ◀──── PLC ◀──── plant state ◀──┘
```

Every command reaches the simulation as **HMI → PLC → bridge → Gazebo** and
every state report returns the same way (ADR 0008 D1). No step in this procedure
has a second path to the plant, and the one tool that does have one is fenced off
in §9.

### Start order — this order, not another

| # | Process | Who | Command |
|---|---|---|---|
| 1 | **PLCSIM Advanced**, CPU in RUN with the §11 build; watch table `Forklift M4 gate` open in *Monitor*; **the test double not running** | **owner** | TIA Portal |
| 2 | bridge | owner | `"$VENV/bin/python" bridge/run_bridge.py --config <forklift config>` |
| 3 | sim bringup | owner | `ros2 launch sim/launch/forklift_bringup.launch.py` |
| 4 | vehicle nodes | owner | `python3 agv/forklift/scripts/forklift_io.py --config agv/forklift/config.yaml` and `…/obstacle_zone.py --config …` |
| 5 | commissioning HMI | owner | `~/amr-hmi-venv/bin/python hmi/hmi_server.py --config hmi/config.yaml`, then open its page |

The server comes first because both clients browse it by namespace URI at
connect and a missing endpoint is a connect failure rather than a wait. The
bridge comes before the plant because its **startup rule R3** withholds the
heartbeat until all four configured input nodes carry a real sample, so it can
be started early and left to wait; `startup rule R3 satisfied` in its log is the
signal that the plant is actually publishing. The HMI comes last because
`HmiLinkOk` is `FALSE` until its counter has been seen to change, and starting
it before there is a server to write to only produces a reconnect loop.

### Isolation — both transports, every run

`ROS_DOMAIN_ID` does not isolate Gazebo: gz transport does not use DDS.
`GZ_PARTITION` does. Export both, in every shell, before every process of
steps 2–4:

```bash
export GZ_PARTITION=m4f4gate ROS_DOMAIN_ID=60
```

Pick a **fresh pair per run** if anything else on the machine may be running a
simulation. The rehearsal below used `m4f08reh1`…`m4f08reh5` with
`ROS_DOMAIN_ID` 71…75, one pair per scenario.

### Before T5.1 — three prerequisites, confirmed rather than assumed

1. **owner** — A bridge configuration that carries the **forklift group** and
   points at the **commissioned PLCSIM endpoint**. `bridge/config/bridge.yaml`
   is deliberately cell-only until the owner has read the `Forklift/` subtree
   back out of TIA Portal (`bridge-design.md` §12 item 10), and
   `bridge/config/rehearsal-forklift.yaml` carries the group but points at the
   double on 4850. **Neither file is the gate configuration**, and the gate run
   cannot start until one exists. Requested of `bridge/` in the report for this
   file.
2. **owner** — `hmi/config.yaml`, which addresses the commissioned CPU.
   `hmi/config-logic-double.yaml` is the rehearsal's and points at 4850.
3. **owner** — The address-space read-back of `SPEC.md` §10 steps 11 and 12,
   dated and recorded. Every value in `opcua-nodes.md` §10 is a design value
   until then and no gate criterion may rest on one.

Confirm all three before T5.1. If the HMI is absent, `HmiLinkOk` never becomes
`TRUE`, nothing can be enabled, and `ForkliftResetRequired` stays `TRUE` forever.

### Shutting the stack down

Signalling `ros2 launch` **does not** bring its group down. Measured by m4f-03
and again in every rehearsal run here: the launch process exits and `gz sim` and
`parameter_bridge` keep running. So:

```bash
pgrep -af "gz sim|parameter_bridge|forklift_io|obstacle_zone|run_bridge|hmi_server"
kill -TERM <exact pid> …          # then re-check, and KILL what is left
ss -ltn | grep -E "4840|4850|8090"   # no listener means the sessions are closed
```

A session is ended by observation, never by assumption. `run_forklift_rehearsal.py`
does exactly this and additionally reads `/proc/<pid>/environ` so that only pids
carrying *this run's* `GZ_PARTITION` are ever signalled.

---

## 2. The four instruments

| Instrument | What it shows | Who reads it |
|---|---|---|
| **Watch table `Forklift M4 gate`**, `SPEC.md` §9, in *Monitor* | the five groups. **Group 1 beside Group 3 is the gate's whole claim on one screen**: the operator asking and the PLC refusing | **owner** |
| **HMI metrics panel**, the lower half of the operator page | the same `Forklift/Input/`, `Forklift/Output/`, `Forklift/Status/` and `HmiLinkOk` values, read from the nodes and applied to nothing. It is the operator's own view and it belongs in the recording | owner, and the rehearsal's `/state` endpoint |
| **Bridge per-session CSV** | 20 Hz `read_rt` rows of every output slot with its value, and a 1 Hz `diagnostics` row. It is the only instrument that keeps reading while the HMI is stopped, which is what makes T5.5 measurable | both |
| **Screen recording** | the model moving in Gazebo beside the watch table and the HMI page | **owner** |

**Monitor only.** Do not use *Modify* or *Force* on any `ForkliftHmi` or
`ForkliftInput` tag during a gate run: a modified value proves nothing about the
loop and would fight the HMI's 10 Hz and the bridge's 20 Hz cyclic writes.

**One evidence CSV per session.** The bridge's `evidence.csv_path` is a *stem*;
the file actually written carries a UTC-second and pid suffix and is created
exclusively, so no restart can truncate an earlier capture. Note the file name
the bridge prints at startup into the run record before the scenario begins.

### What to capture, per scenario

1. the bridge session CSV name, from the bridge's own first log line;
2. a watch-table PNG at each step whose Pass line says *record*, framed to show
   **Group 1 and Group 3 together**;
3. the recording segment, with the reaction named out loud as **standard-program
   process logic, not a safety function**;
4. the HMI page visible in the same frame as the watch table wherever it fits.

### How the pass counts below are derived

The three rules of `SPEC.md` §11 apply unchanged. A count is the number of rows
in that scenario's own step table; a count is the specified denominator and
never a claim about a run; a step recorded as failed, not run or not executable
is not a pass by default. The rehearsal's own counts below are stated as the
harness printed them and are a count of **harness checks**, which is a different
denominator from §11's steps and is never substituted for it.

---

## 3. Scenario 1 — teleoperated drive, the PLC forming all motion setpoints

**Criterion (a).** Procedure: `SPEC.md` §11 **T5.1**, nine steps.

**Stack:** the full order of §1. `GZ_PARTITION=m4f4gate ROS_DOMAIN_ID=60`.
Nothing is moved in the world; the vehicle starts at the launch file's default
spawn, `(-6.00, 0.00)` facing `+x`, with the whole aisle ahead of it.

| Step | Operator action (**owner**, at the HMI page) | Observable |
|---|---|---|
| 5.1.1 | none — read the watch table before touching a control | Group 4: `HmiLinkOk` `TRUE`, `"DemoCellLink".BridgeLinkOk` `TRUE`, `ForkliftTeleopActive` `FALSE`, `ForkliftResetRequired` `TRUE`. Group 3: all three `…Ref` `0.0`. See the start-order note below for `ForkliftObstacleStopActive` |
| 5.1.2 | press and hold ENABLE | `ForkliftTeleopActive` stays `FALSE`, Group 3 stays `0.0` |
| 5.1.3 | release ENABLE, click RESET once | `ForkliftResetRequired` → `FALSE`; `ForkliftTeleopActive` still `FALSE`; Group 3 still `0.0` |
| 5.1.4 | press ENABLE again | `ForkliftTeleopActive` → `TRUE`, Group 3 still `0.0` |
| 5.1.5 | joystick to full forward | `ForkliftTractionSpeedRef` → `+1.00`; `ForkliftLinearSpeed` follows; the model drives in Gazebo. **PNG: Group 1 beside Group 3** |
| 5.1.6 | joystick X to ≈+0.8 rad, then ≈−0.8 rad | `ForkliftSteerAngleRef` follows the clamped request; the model steers both ways |
| 5.1.7 | joystick to full reverse | `ForkliftTractionSpeedRef` → `−1.00`; the model reverses |
| 5.1.8 | release ENABLE while driving | Group 3 all `0.0` in the same OB call, steer included; `ForkliftTeleopActive` → `FALSE`; `ForkliftResetRequired` stays `FALSE` |
| 5.1.9 | press ENABLE again | teleop returns with no reset |

**Topics behind the nodes:** `/forklift/cmd/traction_speed`,
`/forklift/cmd/steer_angle` (bridge → plant) and `/forklift/linear_speed`,
`/forklift/odom` (plant → bridge), all in `agv/forklift/README.md`.

**Capture:** bridge session CSV; watch-table PNG at 5.1.5 and 5.1.8; recording
segment covering 5.1.1 → 5.1.9 with the HMI page in frame.

### REHEARSAL EVIDENCE — scenario 1, 20 of 20 harness checks passed

`GZ_PARTITION=m4f08reh1 ROS_DOMAIN_ID=71`; bringup double 1.0 s, bridge 1.5 s,
sim 1.3 s, vehicle 2.5 s, HMI 0.5 s. Bridge session CSV
`bridge-20260729T101805Z-pid92119.csv` (1 105 801 bytes).

```
 0.001  boot  req T=+0.00 S=+0.000 F=+0.00 en=0 rst=0 | ref T=+0.000 S=+0.000 F=+0.000
              | teleop=0 stop=0 cap=0 resetreq=1 link=1 | h=-0.000 v=-0.000 d=6.830 zone=0
 0.001  ok    HmiLinkOk TRUE
 0.001  ok    ForkliftTeleopActive FALSE
 0.001  ok    ForkliftResetRequired TRUE (both link latches formed at the first scan)
 0.001  ok    all three setpoints 0.0
 2.042  ok    refused: teleop stays FALSE with a latch pending
 2.799  ok    ForkliftResetRequired -> FALSE in 0.255 s
 2.799  ok    the reset energizes nothing: teleop still FALSE
 3.004  ok    ForkliftTeleopActive -> TRUE
 7.072  ok    ForkliftTractionSpeedRef = +1.000 m/s (demand 1.00 x TRACTION_SPEED_MAX 1.00)
 7.072  ok    ForkliftLinearSpeed +1.000 tracks the setpoint
 9.579  odom  x -6.000 -> -3.502 m, moved +2.498 m
 9.579  ok    the model drove forward in Gazebo
13.659  ok    ForkliftSteerAngleRef followed the clamped request both ways: +0.8004 then -0.8004 rad
18.585  ok    ForkliftTractionSpeedRef = -1.000 m/s - the sign carries direction, there is no run bit
19.442  ok    all three refs 0.0, the steer angle included (the wheel returns to centre)
19.442  ok    ForkliftResetRequired stays FALSE - a normal stop, no latch
20.946  odom  x -3.509 -> -6.523 m
21.602  ok    teleop returns with NO reset - releasing the enable is not a fault
```

**A boot reading is taken from a panel that has values on it.** The first
rehearsal of 5.1.1 read `metrics: null` and reported three verdicts absent,
because the HMI's session reaches `CONNECTED` a cycle or two before its
read-only poll first lands. The harness now waits for both, and the operator's
equivalent is the same: do not read 5.1.1 off a panel whose metrics fields are
still blank. An absent value is not a zero.

The measured spawn distance to the crate, `d=6.830` m, is the arena header's own
arithmetic — crate face at `x = 1.55`, scanner leading the model origin by
0.72 m — read back off the loop rather than recomputed.

### Start-order note on 5.1.1's `ForkliftObstacleStopActive`

§11 5.1.1 expects `ForkliftObstacleStopActive` `FALSE` at boot "despite the field
bit's `TRUE` start value". **That reading is not guaranteed under this start
order, and both outcomes were observed.**

The vehicle layer publishes `in_stop_zone = TRUE` and `min_distance = 0.0`
whenever it has no usable scan — absence of data *is* an obstacle. When
`obstacle_zone.py` starts, it publishes that sentinel until its first scan
arrives. Whether the PLC ever sees it depends on a race with the bridge's R3
rule:

- **Sentinel not attributable** (the five scenarios below, and every
  `--scenario all` run): R3 completed 2.5–3.5 s after the vehicle nodes started,
  by which time `obstacle_zone` had a valid scan, so the first attributable
  image was a clear one and 5.1.1 read `FALSE` exactly as §11 says.
- **Sentinel attributable** (a run in which the bridge had been up for ~40 s
  before the vehicle nodes were started, so its subscription matched the new
  publisher immediately): the sentinel reached the PLC while both links were up
  and the program **correctly** latched — `ForkliftObstacleStopActive TRUE` at
  boot, on the field bit and on the `0.0` window test together.

Neither is a defect. A third run, with the vehicle nodes deliberately started
**before** the world existed, shows the guard that makes it safe: the sentinel
stood for 6.29 s (`reason=no scan received`, `12:08:55` → `12:09:01`) and
`ForkliftObstacleStopActive` stayed `FALSE` throughout, because `forklift_io`
also had nothing to publish, R3 therefore withheld the heartbeat, `BridgeLinkOk`
never became `TRUE`, and §6.1 suspends all plant-input evaluation while the
image is unattributable.

**What the owner does:** before reading 5.1.1, confirm
`"ForkliftInput".ForkliftObstacleInStopZone` reads `FALSE` in Group 2. If
`ForkliftObstacleStopActive` reads `TRUE`, record it with the cause — the zone
evaluator's no-scan sentinel, not the DB start value — and continue: 5.1.3's
reset clears it, because by then the cause is gone. A `SPEC.md` §11 revision to
state both outcomes is requested in the report for this file.

---

## 4. Scenario 2 — fork to height, and both soft-limit aborts

**Criterion (b).** Procedure: `SPEC.md` §11 **T5.2**, eight steps.

**Stack:** as §1. No world stimulus. The vehicle stays parked; this scenario
moves only the carriage.

| Step | Operator action (**owner**) | Observable |
|---|---|---|
| 5.2.1 | with the carriage parked, hold FORK DOWN | Group 2 `ForkliftForkHeight` ≈`0.00`, below `FORK_TRAVEL_MIN` 0.05; `ForkliftForkSpeedRef` stays `0.0`; `ForkliftResetRequired` stays `FALSE` |
| 5.2.2 | hold FORK UP at full | `ForkliftForkSpeedRef` → `+0.15`; the height rises at ≈0.15 m/s |
| 5.2.3 | fork demand ≈0.4 | Ref ≈`+0.06` — the demand scales |
| 5.2.4 | hold FORK UP into the limit | Ref snaps to `0.0` **with the control still held**, at `ForkliftForkHeight` ≥ 1.55. **Record the stopping height as a number** |
| 5.2.5 | hold FORK DOWN | Ref → `−0.15`; the carriage lowers — the abort is direction-scoped |
| 5.2.6 | hold FORK DOWN past 0.05 m | Ref snaps to `0.0`; FORK UP moves it again immediately |
| 5.2.7 | read Group 4 and Group 5 throughout | all latch bits `FALSE`: a soft-limit abort is a refusal of one direction, not a latch |
| 5.2.8 | mid-travel, release ENABLE | Ref → `0.0` and the carriage **holds** its height |

**Topics behind the nodes:** `/forklift/cmd/fork_speed` (bridge → plant),
`/forklift/fork_height` (plant → bridge). The fork request is a **rate**: zero
does not lower the forks, zero holds them.

**Capture:** bridge session CSV; watch-table PNG at 5.2.4 showing the stopping
height beside a still-held request; recording segment covering the full travel
in both directions.

### REHEARSAL EVIDENCE — scenario 2, 13 of 13 harness checks passed

`GZ_PARTITION=m4f08reh2 ROS_DOMAIN_ID=72`. Bridge session CSV
`bridge-20260729T101841Z-pid93464.csv` (1 799 131 bytes).

```
 0.965  ok    ForkliftForkHeight -0.0000 m is below FORK_TRAVEL_MIN 0.05
 3.467  ok    ForkliftForkSpeedRef stays 0.0 with the lower control held
 3.467  ok    and it is NOT a fault: ForkliftResetRequired stays FALSE
 5.970  ok    ForkliftForkSpeedRef = +0.1500 m/s
 8.013  ok    ref +0.0600 m/s = demand 0.4 x FORK_SPEED_MAX - the demand scales, it is not a two-state jog
15.575  ok    the ref snapped to 0.0 with the raise control still held, after 7.6 s
15.575  MEASURED  stopping height 1.5561 m; FORK_TRAVEL_MAX 1.55 m; the model's mechanical stop is 1.60 m
15.779  ok    ref -0.1500 m/s - the abort is direction-scoped and the carriage is not stranded
27.161  ok    the ref snapped to 0.0 at the lower soft limit after 11.4 s, height 0.0380 m
27.365  ok    commanding raise moves it again immediately
27.366  ok    ForkliftResetRequired and ForkliftObstacleStopActive both FALSE
36.392  ok    the carriage HOLDS 0.4651 m against gravity over 3 s (drift +0.0015 m)
```

The upper stop at **1.5561 m** sits between the soft limit 1.55 and the model's
mechanical stop 1.60, which is the 0.05 m margin §3.3 sizes at ≈3× the worst
latency-induced overshoot. The lower stop at **0.0380 m** is *below*
`FORK_TRAVEL_MIN` for the same reason in the other direction: the abort acts on
the height the PLC last read, and the carriage travels on for the remainder of
one bridge round trip.

**Reading a height across a command transition.** The first rehearsal of 5.2.8
compared the height before and after the release and read a 0.008 m difference
as a fall. It was not: the operator's panel refreshes at 5 Hz and the command
needs a write cycle and a bridge round trip, so the carriage keeps rising for a
fraction of a second after the last sample — motion it was still commanded to
make. The hold is tested **after** the carriage is at rest, and then the drift
over 3 s is `+0.0015 m`. The same effect is why the pre-positioning in scenario 3
releases the carriage well short of its target.

---

## 5. Scenario 3 — traction capped while the fork is raised

**Criterion (c).** Procedure: `SPEC.md` §11 **T5.3**, five steps.

**Stack:** as §1. No world stimulus. **Setup, not a step:** raise the carriage to
≈0.30 m first, well below `FORK_HEIGHT_SLOW_THRESHOLD` 0.50, so the crossing in
5.3.2 is short and the vehicle stays clear of the crate.

| Step | Operator action (**owner**) | Observable |
|---|---|---|
| 5.3.1 | carriage below 0.50 m, teleop active, joystick full forward | `ForkliftTractionSpeedRef` = `+1.00`; `ForkliftSpeedLimitActive` `FALSE` |
| 5.3.2 | hold FORK UP past 0.50 m with the joystick still at full | Ref drops to `+0.30` in the OB call after the crossing; `ForkliftSpeedLimitActive` → `TRUE`; the model **visibly slows** with the operator touching nothing. **Record both refs and the crossing height** |
| 5.3.3 | lower back below 0.50 m | Ref returns to `+1.00`; `ForkliftSpeedLimitActive` → `FALSE` |
| 5.3.4 | with the carriage raised, joystick to ≈0.2 | see the finding below |
| 5.3.5 | read `ForkliftLinearSpeed` at 5.3.1 and 5.3.2 | it tracks each ref, and feeds **no** verdict — there is no traction drive-fault detection on this plant |

**Capture:** bridge session CSV; watch-table PNG at 5.3.2 showing
`HmiTractionRequest` still at full beside `ForkliftTractionSpeedRef` at 0.30;
recording segment where the model slows without an operator input.

### REHEARSAL EVIDENCE — scenario 3, 9 of 9 harness checks passed

`GZ_PARTITION=m4f08reh3 ROS_DOMAIN_ID=73`. Bridge session CSV
`bridge-20260729T101933Z-pid95298.csv` (1 112 245 bytes).

```
 4.120  setup carriage parked at 0.3516 m, below FORK_HEIGHT_SLOW_THRESHOLD 0.50
 6.162  ok    ForkliftTractionSpeedRef +1.000 m/s
 6.162  ok    ForkliftSpeedLimitActive FALSE
10.148  ok    ForkliftSpeedLimitActive -> TRUE at height 0.5286 m
10.148  ok    ForkliftTractionSpeedRef dropped +1.000 -> +0.300 m/s with the operator touching nothing
10.148  MEASURED  ForkliftLinearSpeed +1.000 -> +0.300 m/s: the model visibly slows in Gazebo
12.650  ok    ref +0.060 m/s = demand 0.2 x TRACTION_SPEED_CAP_RAISED 0.30
17.654  note  reversing raised: ForkliftTractionSpeedRef -0.300 m/s - the cap applies to the
              magnitude, not to the forward direction
21.477  ok    ref back to +1.000 m/s and ForkliftSpeedLimitActive FALSE
```

The setup releases the carriage at 0.28 m and it parks at 0.3516 m. Released at
0.42 m in an earlier rehearsal it parked at 0.5026 m — *above* the threshold, so
the scenario's own precondition was gone before step 5.3.1. Same cause as the
carriage-hold reading in scenario 2: a 5 Hz panel plus a write cycle plus a
bridge round trip is about half a second of travel at the jog speed.

### FINDING — step 5.3.4's Pass line and §§7/9 predict different numbers

`SPEC.md` §11 step 5.3.4 says a demand of ≈0.2 with the carriage raised gives
`≈+0.20 m/s`, and calls that "the cap limits, it does not command". `SPEC.md`
§9's Group 3 row says the setpoint is `demand × 1.00` uncapped and
`demand × 0.30` with the fork raised, and §7 builds it that way. Those cannot
both hold: a **limit** leaves 0.2 at `+0.200 m/s`, a **scale** makes it
`+0.060 m/s`.

Observed: `+0.060 m/s`, the scale form — the double is a statement-for-statement
transliteration of §7, and `hmi/EVIDENCE_HMI.md` §B.4 independently recorded
`0.180 m/s` against a standing request of `0.60`, which is the same form.

Both readings satisfy the criterion's own words, since the criterion asks only
that traction be capped while the fork is raised. **Which form is intended is a
`plc/` ruling**, and it is not one this file may take: either §11 5.3.4's Pass
line is corrected to the scale form, or §§7 and 9 change to the limit form.
Requested in the report for this file. Until it is ruled, record the observed
value and name the form, rather than reading a mismatch as a program defect.

---

## 6. Scenario 4 — obstacle latch, override, refusal and monitored reset

**Criterion (d).** Procedure: `SPEC.md` §11 **T5.4**, ten steps, in the
**corrected held-reset form** — the reset is asserted at 5.4.4 and **held
unbroken** through 5.4.8, spanning the moment the zone clears, because the
property under test is that the edge happened *before* the cause went away.

**Stack:** as §1, plus the world stimulus below.

### The world stimulus, and the two ways it must not be done

The obstacle is `AisleCrate`, standing on the aisle centreline at `x = 2.00` with
its front face at `x = 1.55`. It is moved with the Gazebo `set_pose` service —
the same service the GUI uses when a model is dragged, and it works on a
`<static>` model:

```bash
python3 sim/scenarios/forklift_stimulus.py obstacle --to-x 8.0    # clear the zone
python3 sim/scenarios/forklift_stimulus.py obstacle --home        # put it back
```

**Clear the zone by pushing the crate FURTHER UP THE AISLE, and only as far as
the scanner can still see it.** The scanner's `range_max` is 8.0 m and the hall
is 24 m long, so a ±30° sector with nothing in range contains no valid sample at
all — and the vehicle layer reports an empty sector as `in_stop_zone = TRUE`,
`min_distance = 0.0`, its no-data sentinel, which reads at the PLC as a
transducer fault rather than as a clear path. Two ways of getting that wrong were
measured here: teleporting the crate to `(9.0, 6.0)`, out of the sector
entirely, and moving it to `x = 8.0` while the vehicle still stood 4.6 m back
down the aisle. Both left `min_distance` at `0.0` where a clear path was
intended.

The rule is therefore arithmetic, not a fixed number. With the scanner leading
the model origin by 0.72 m and the crate's near face 0.45 m ahead of its centre,
the in-sector range after the move is `x_crate − x_vehicle − 1.17`, and it must
land **between the 1.20 m stop distance and the 8.0 m range maximum**. At 5.4.6
the vehicle has stopped at `x ≈ −0.37`, so `--to-x 8.0` gives 7.04 m and is
comfortably inside both bounds and inside the PLC's 0.05…8.10 m plausibility
window.

**Confirm the move in Group 2 before reading the step**:
`"ForkliftInput".ForkliftObstacleMinDistance` must show a plausible number, not
`0.0`. A `0.0` there means the crate went out of range, not that the path is
clear, and the step must be re-run rather than reinterpreted.

### The held reset, and why a browser click cannot produce it

The HMI's RESET is **momentary by construction**: one click posts one request and
the backend writes `HmiResetRequest` `TRUE` for exactly one write cycle. Steps
5.4.4 to 5.4.7 need it standing for tens of seconds. Hold it by re-posting to the
HMI's own `/control` endpoint faster than its write rate:

```bash
python3 sim/scenarios/forklift_stimulus.py hold --teleop --traction 0.6 --reset --seconds 20
```

Every write cycle then finds the request standing and the node reads `TRUE`
continuously, which is what the program sees and what the step needs. Confirm it
in Group 1 — `"ForkliftHmi".HmiResetRequest` `TRUE` and staying `TRUE` — before
reading 5.4.6. If the hold cannot be produced, steps 5.4.4 and 5.4.7 are recorded
as **not run** under §11 rule 3; they are not a pass by default. Requested of
`hmi/` in the report: a hold-capable reset control on the page itself, so this
step does not need a second tool.

| Step | Operator action (**owner**) | Observable |
|---|---|---|
| 5.4.1 | teleop active, steady traction demand, drive at the crate | Group 2 `ForkliftObstacleMinDistance` falls and **nothing changes**: no PLC threshold exists on it |
| 5.4.2 | continue until `ForkliftObstacleInStopZone` goes `TRUE` | same OB call: `ForkliftObstacleStopActive` → `TRUE`, `ForkliftTeleopActive` → `FALSE`, Group 3 all `0.0`, `ForkliftResetRequired` → `TRUE`. **Record `HmiTractionRequest` still standing in Group 1** — the latch overrides a live command |
| 5.4.3 | hold the traction demand 10 s | Group 3 stays `0.0`. Nothing resumes, nothing creeps |
| 5.4.4 | **assert RESET and hold it** — zone still occupied | Refused. `ForkliftResetRequired` and `ForkliftObstacleStopActive` stay `TRUE` |
| 5.4.5 | release and re-assert **ENABLE**, reset still held; leave the enable asserted | Refused — the machine cannot drive itself clear. A deliberate consequence, not a defect |
| 5.4.6 | **clear the zone with the reset still held**: `obstacle --to-x 8.0` | `ForkliftObstacleInStopZone` → `FALSE` while `HmiResetRequest` still `TRUE`; both latch verdicts stay `TRUE`. Two properties in one observation |
| 5.4.7 | keep the reset held a further 10 s | The latch never clears. No edge, and no elapsed time makes one appear |
| 5.4.8 | release RESET, confirm `HmiResetRequest` `FALSE`, click it again | Latches clear on that fresh edge; `ForkliftObstacleStopActive` → `FALSE`; **nothing moves** — teleop stays `FALSE` though the enable has stood since 5.4.5 |
| 5.4.9 | release ENABLE, confirm `FALSE`, press it again | Teleop returns; the refs follow the controls again |
| 5.4.10 | **lidar transducer fault** — interrupt the scan at its source | `ForkliftObstacleStopActive` latches from the **window test** on `ForkliftObstacleMinDistance` `0.0`, and `ForkliftObstacleInStopZone` reads `TRUE` at the same moment |

For 5.4.10 the scan is stopped at its source by finishing the arena's
`ros_gz_bridge` by exact pid — it is the process that carries `/forklift/scan`
out of Gazebo, and `obstacle_zone.py` then reports `scan stale` after its 0.50 s
timeout:

```bash
pgrep -af "parameter_bridge.*forklift_arena_bridge"
kill -KILL <exact pid>
```

The command path stops with it, so this step ends the scenario: restart the sim
bringup before running another.

**Capture:** bridge session CSV; watch-table PNGs at 5.4.2 (Group 1 standing
beside Group 3 at zero), 5.4.6 (zone clear, latch standing, reset `TRUE`) and
5.4.8; the recording segment covering the approach, the stop and the whole reset
sequence, **naming the reaction as standard-program process logic and not a
safety function** as it happens.

### REHEARSAL EVIDENCE — scenario 4, 23 of 23 harness checks passed

`GZ_PARTITION=m4f08reh4 ROS_DOMAIN_ID=74`. Bridge session CSV
`bridge-20260729T102009Z-pid96590.csv` (2 256 681 bytes).

```
 4.028  ok    ForkliftObstacleMinDistance falling to 5.378 m with no PLC threshold on it
10.821  ok    ForkliftObstacleStopActive -> TRUE after 6.8 s
10.821  ok    ForkliftTeleopActive -> FALSE
10.821  ok    all three refs -> 0.0
10.821  ok    ForkliftResetRequired -> TRUE
10.821  ok    HmiTractionRequest is STILL STANDING at +0.60 - the latch overrides a live command
20.832  ok    refs stay 0.0 - nothing resumes and nothing creeps
24.866  ok    HmiResetRequest reads TRUE and stays TRUE (held by re-posting above the HMI write rate)
24.866  ok    the reset is REFUSED: CauseGone is false on C3
28.675  ok    refused - the machine cannot drive itself clear
29.393  obstacle AisleCrate -> x=8.0 : ok data: true
29.599  ok    ForkliftObstacleInStopZone -> FALSE, ForkliftObstacleMinDistance 7.041 m
29.599  ok    while HmiResetRequest still reads TRUE
29.599  ok    the latch STANDS: the field clearing does not release it, and the still-asserted
              reset supplies no edge
39.606  ok    the latch NEVER clears while it is held
40.207  ok    HmiResetRequest reads FALSE
40.412  ok    every latch clears on that FRESH rising edge, after 0.204 s
42.452  ok    NOTHING MOVES: teleop stays FALSE even though the enable has been asserted since
              5.4.5 - a level that never fell produces no edge
43.408  ok    teleop returns on that fresh edge
45.958  ok    and the refs follow the operator's controls again: +0.600 m/s
45.963  stimulus  finishing the arena scan bridge, pid 96704 (exact pid, partition m4f08reh4)
46.629  ok    ForkliftObstacleStopActive latched 0.67 s after the scan stopped
46.629  ok    ForkliftObstacleInStopZone reads TRUE at the same moment
46.629  MEASURED  ForkliftObstacleMinDistance reads 0.000 - the no-data sentinel, outside
              OBSTACLE_DISTANCE_MIN 0.05
```

**Step 5.4.10 ran**, rather than being recorded as not executable. The 0.67 s
from scan interruption to latch is the sum of the evaluator's 0.50 s scan
timeout and the PLC's 0.30 s `LIDAR_FAULT_DELAY` overlapping one bridge cycle
and one 5 Hz panel refresh, and it is quoted as the harness printed it.

---

## 7. Scenario 5 — HMI heartbeat loss zeroing all motion setpoints

**Criterion (e).** Procedure: `SPEC.md` §11 **T5.5**, six steps.

**Stack:** as §1. The HMI is stopped and restarted; nothing in the world moves.

**The instrument changes for this scenario.** The operator's panel is the thing
being stopped, so the observables come from the watch table (**owner**) and from
the **bridge's per-session CSV and 1 Hz diagnostics log**, which keeps reading
`Forklift/Output/` at 20 Hz and `Forklift/Status/` at 1 Hz throughout the outage.

| Step | Operator action (**owner**) | Observable |
|---|---|---|
| 5.5.1 | teleop active and driving, fork jogging as well. **Stop the HMI process** and note the instant | `"ForkliftLink".HmiHeartbeat` freezes at its last value |
| 5.5.2 | read `HmiLinkOk` and Group 3 | `HmiLinkOk` → `FALSE` within `HMI_STALE_TIME` (600 ms) of the last advancing beat; all three refs → `0.0` in the same OB call; `ForkliftTeleopActive` → `FALSE`; `ForkliftResetRequired` → `TRUE`. **Record the elapsed time as a number** |
| 5.5.3 | watch the model in Gazebo | It stops on the zero command. Record what it does and how quickly |
| 5.5.4 | restart the HMI, let the heartbeat advance, **do nothing for 30 s** | `HmiLinkOk` → `TRUE`; teleop does **not** return; refs stay `0.0`; `ForkliftResetRequired` stays `TRUE`. Group 5 `ResetDeviceFault` read `TRUE` through the outage and clears within one update of link-up |
| 5.5.5 | **the P6 guard**: stop the HMI, arrange for it to write `HmiResetRequest` `TRUE` from its very first cycle, restart it | `ResetDeviceFault` `TRUE` before, through and after link-up, so the edge arriving with the first attributable sample is **refused**. Then write the request `FALSE` and `TRUE` again: that fresh edge clears the latches |
| 5.5.6 | reset normally, then assert the enable | Latches clear, teleop returns on the fresh enable edge, the machine is driveable. No auto-resume anywhere in 5.5.1–5.5.5 |

**How the number in 5.5.2 is taken.** From **one clock**. `CLOCK_MONOTONIC` is
system-wide on Linux, so the HMI's own per-session CSV (`monotonic_s`, one row
per write cycle — its last row **is** the last advancing beat) and the bridge's
`read_rt` rows (`t_start_ns`, 20 Hz per output slot) may be subtracted directly.
Take the last `monotonic_s` in the HMI CSV and the first `read_rt` row for
`ForkliftTractionSpeedRef` whose value is `0.0` after it. Do not mix a wall-clock
stamp into this measurement.

**For 5.5.5**, the HMI's HTTP server starts *before* its OPC UA session, so a
`/control` post that lands in that window arms the request before any cycle
writes it:

```bash
~/amr-hmi-venv/bin/python hmi/hmi_server.py --config hmi/config.yaml &
python3 sim/scenarios/forklift_stimulus.py hold --reset --seconds 20 --rate 50
```

Start the hold in the same breath as the process. Confirm in Group 1 that
`HmiResetRequest` reads `TRUE` from the first sample after link-up; if the first
cycles wrote `FALSE`, the guard has already cleared and the step must be re-run,
not reinterpreted.

**Capture:** bridge session CSV **and** HMI session CSV (both are inputs to the
measurement); watch-table PNG immediately after the outage showing `HmiLinkOk`
`FALSE` beside three zeroed refs; watch-table PNG at 5.5.5 showing
`ResetDeviceFault` `TRUE` beside `HmiLinkOk` `TRUE`; recording segment covering
the stop, the model coming to rest, and the 30 s in which nothing resumes.

### REHEARSAL EVIDENCE — scenario 5, 14 of 14 harness checks passed

`GZ_PARTITION=m4f08reh5 ROS_DOMAIN_ID=75`. Bridge session CSV
`bridge-20260729T102111Z-pid98887.csv` (3 252 976 bytes); three HMI session CSVs,
one per HMI process, `hmi-20260729T102116Z-pid99323.csv`,
`hmi-20260729T102133Z-pid99655.csv`, `hmi-20260729T102208Z-pid100863.csv`.

```
 3.924  ok    driving at +0.550 m/s with the fork jogging at +0.1500 m/s
 5.449  MEASURED  SIGTERM to the HMI at monotonic 145584.2939
11.451  MEASURED  last HMI write cycle at monotonic 145584.2501; first bridge read of
              ForkliftTractionSpeedRef = 0.0 at monotonic 145584.8878
11.451  MEASURED  elapsed last-advancing-beat -> setpoint 0.0 = 638 ms (HMI_STALE_TIME is 600 ms)
11.451  note      the last non-zero read before that was +0.165 m/s
11.451  bridge    PLC diagnostics after the outage: {'ForkliftTeleopActive': False,
              'ForkliftObstacleStopActive': False, 'ForkliftSpeedLimitActive': False,
              'ForkliftResetRequired': True, 'HmiLinkOk': False}
16.472  odom      x -3.822 -> -3.698 -> -3.698 m
16.472  ok    the model stopped on the PLC's zero command
47.515  ok    HmiLinkOk -> TRUE ... teleop does NOT return ... refs stay 0.0
              ... ForkliftResetRequired stays TRUE
51.449  P6 arming: first reset POST accepted before the first write cycle
64.029  ok    the edge arriving with the first attributable sample is REFUSED
65.184  ok    then FALSE and TRUE again: THAT fresh edge clears the latches
68.494  ok    the machine is driveable: +0.120 m/s = demand 0.4 with ForkliftSpeedLimitActive
              True (carriage at 0.749 m)
```

**638 ms** against a 600 ms stale window. Three earlier rehearsals of the same
step measured 655, 669 and 692 ms, so four rehearsals span **638–692 ms**. The
margin is accounted for and not slack: the PLC's 20 ms OB period, the bridge's
50 ms output poll, and the read landing somewhere inside it. It is quoted as a
bound, taken between two readings of the same clock, and the figure the gate
rests on is the owner's against PLCSIM — where the CPU's scan cycle is real and
this margin will differ.

Two readings in that transcript are worth naming because they look wrong and are
not. `+0.165 m/s` is the last non-zero setpoint, not `+0.550`, because the fork
had jogged past 0.50 m and the raised-carriage cap was in force: `0.55 × 0.30`.
`+0.120 m/s` at 5.5.6 is the same cap on a demand of 0.4. The model travelled
0.122 m between the outage and coming to rest, and then stayed exactly where it
was for the rest of the scenario.

---

## 8. Appendix scenario — bridge session loss mid-motion

`SPEC.md` §11 **T5.6** is not one of the five roadmap criteria and closes no gate
item. It is run in the same stack, with the same instruments, and it is the
scenario in which the **§8 residual** is observable: while the bridge is down the
PLC's `0.0` cannot reach the plant, so the machine keeps its last commanded
traction until the bridge returns and republishes. That is a property of the
demonstration setup, not of the program — on real equipment the drive is dropped
by a wired enable and a contactor — and **no safety function is involved**.

Stimulus: `kill -9` the bridge by exact pid, note the instant, and restart it
with the same config. **Not rehearsed here**; it was outside this file's five
scenarios and is recorded as not run rather than implied.

---

## 9. The stimulus tool, and the one thing it must never be used for

`sim/scenarios/forklift_stimulus.py` carries the four stimuli this procedure
needs. `sim/scenarios/run_forklift_rehearsal.py` is the rehearsal harness that
produced every REHEARSAL EVIDENCE block above; it is not part of the owner's run.

| Subcommand | Use |
|---|---|
| `hold` | hold a set of operator controls at the HMI by re-posting to `/control` at a rate. The only way to produce the held reset of 5.4.4 and the pre-link-up reset of 5.5.5 |
| `obstacle` | move the aisle crate, and `--home` to put it back |
| `watch` | poll `/state` and print one line per change — a transition transcript rather than a wall of samples |
| `plant` | **plant smoke check only** |

**No `--once` publish appears in this procedure or in either script.** A single
publish exits on the first matching subscriber and races every other one, and
one lost start press cost a day of misread refusals. Every stimulus here is a
repeated publish at a stated rate, an HTTP post, or a service call that returns
a reply.

**`plant` bypasses the PLC and is never gate evidence.** It publishes straight
onto `/forklift/cmd/*`, which is the bridge's own output topic, so a value sent
that way has passed through no PLC logic at all and would interleave with the
bridge's publications. Use it to answer "is the machine alive" before blaming a
refusal on the program, and never during a recorded scenario.

---

## 10. What the rehearsal establishes, and what it does not

**Established, on this machine, on 2026-07-29:**

| | |
|---|---|
| Host | WSL2 Ubuntu 24.04.4 LTS, kernel `5.15.167.4-microsoft-standard-WSL2`, `/mnt/c` checkout |
| ROS 2 | Jazzy, `/opt/ros/jazzy`, Python `3.12.3` |
| Gazebo | `gz sim 8.11.0` via `ros-jazzy-gz-sim-vendor 0.0.10-1noble.20260604.111001`; `ros-jazzy-ros-gz 1.0.22-1noble.20260616.074726` |
| Render | llvmpipe software rasterisation, headless |
| OPC UA | `asyncua 2.0.1` in both venvs — the pin in `bridge/requirements.txt` |
| Server | `plc/forklift/double/server.py` on `opc.tcp://127.0.0.1:4850`, 20 ms scan |
| Bridge config | `bridge/config/rehearsal-forklift.yaml` — forklift group only, 4 in / 3 out / 5 diag, 13 nodes |
| HMI config | `hmi/config-logic-double.yaml`, page on `127.0.0.1:8090` |
| Run | `run_forklift_rehearsal.py --scenario all`, 2026-07-29 10:18:02Z → 10:22:33Z, exit 0 |
| Result | **79 harness checks, 79 passed**: 20 + 13 + 9 + 23 + 14 |
| Cleanup | every scenario ended `pgrep -af final: clean` and `listeners 4850/8090: none` |

- All five criteria have a scenario whose every step was executed through the
  full loop — HMI → PLC logic → bridge → arena and back — and every observable
  named above was read off a real node or a real topic.
- Step 5.4.10 is executable in this arena, and 5.5.5's P6 guard is reproducible.
- The five per-session bridge CSVs are 1.1 MB to 3.3 MB each; 9.7 MB with the
  seven HMI CSVs beside them. They are **not committed**: `sim/` may not write
  into `bridge/` or `hmi/`, and a 20 Hz stream is quoted rather than stored.
  Every figure above is as the harness or the process printed it. Scenario 5
  produced three HMI CSVs for its three HMI processes, which is the
  one-file-per-session rule visible in a run that restarts a client twice.

**Not established, and not claimable from anything here:**

| Not shown | Why |
|---|---|
| Anything about the TIA Portal build, its scan cycle or its timers | The double is a transliteration of `SPEC.md` §7, not the program. Any divergence resolves toward TIA and the spec |
| Anything about the commissioned CPU's address space | `opcua-nodes.md` §10 is a design value until the owner's read-back of `SPEC.md` §10 steps 11 and 12 |
| The M4 gate itself | The gate closes on the owner's PLCSIM run **and** the recorded showcase. A rehearsal against a double closes nothing |
| Any safety claim | No SRS function is exercised, no F-CPU exists on this plant, and no reaction here carries a SIL or PL claim (ADR 0008 D3) |
| T5.6 | Out of this file's five scenarios; recorded as not run |
| Real-world lidar behaviour | Software-rasterised `gpu_lidar` in a box-and-cylinder arena, with a known single-sample dropout at ±45° that the vehicle layer already handles |

---

## 11. Findings raised by the rehearsal, for the layers that own them

| # | Finding | Owner | Status |
|---|---|---|---|
| 1 | **§11 step 5.3.4's Pass line contradicts §§7 and 9** on the raised-carriage cap: a demand of 0.2 gives `+0.20 m/s` under the Pass line and `+0.060 m/s` under the specified and implemented form. Observed `+0.060` | `plc/` | **Closed by `bc6a570`.** The scale form was ruled the correct one and §11 5.3.4's Pass line now reads `≈+0.060 m/s`; §6.5 states the cap as a scale rather than a ceiling, and §9's Group 3 row says so beside it. The rehearsal reading was the specification's, and the Pass line was the defect |
| 2 | **§11 step 5.1.1's `ForkliftObstacleStopActive FALSE` is not guaranteed** under the specified start order. The zone evaluator's no-scan sentinel can be attributable, and the program then correctly latches. Both outcomes observed; a revision stating both is requested | `plc/` | **Closed by `bc6a570`.** §11 5.1.1 now states that **both readings pass**, names the race that decides which one appears, and replaces the single-value check with a pair check — the field bit and the distance are read *before* the verdict is judged, and the latch must **hold** rather than take a value. A latch found set clears at 5.1.3 and changes no later step |
| 3 | **The HMI's reset cannot be held from the page.** One click is one write cycle, and §11 5.4.4–5.4.7 need it standing across the moment the zone clears. It is producible only by re-posting to `/control` above the write rate. A hold-capable RESET control would let the gate step be run entirely from the operator's screen | `hmi/` | **Open, in flight**: `docs/briefs/m4f-07b-h6-and-holdable-reset.md` makes the RESET press-and-hold capable — `TRUE` written every cycle while held, `FALSE` on release — which is what makes T5.4's held-reset steps executable from the page. Until it lands, §6's `forklift_stimulus.py hold --reset` is the way to produce the hold, and the step is not a pass by default without it |
| 4 | **No bridge configuration exists for the gate run**: `bridge.yaml` is cell-only by choice and `rehearsal-forklift.yaml` points at the double. The forklift group against the commissioned endpoint is a one-file addition after the TIA read-back, and it is a precondition of T5.1 | `bridge/` | **Open, queued to the owner**: `docs/TODO.md`, *owner — M4 queue*, the step "after the TIA read-back: point `bridge/config/bridge.yaml` at the `Forklift` groups". It is one edit per `bridge-design.md` §2.1 and it is deliberately not made before the read-back, because browsing nodes the CPU does not publish would error |
| 5 | **An empty forward sector is a no-data condition, not a clear path** — the scanner's 8 m range against a 24 m hall. It shapes how the T5.4 stimulus must be written and is recorded in `sim/README.md` with the arena | `sim/` | **Closed by `aa593ed`**, the commit that carries this file: recorded in §6 with its arithmetic and in `sim/README.md` with the arena |
