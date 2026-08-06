# EVIDENCE_STO — torque removal at the plant (m5-50)

What SS1's second stage does to this vehicle, measured. The design it
answers is `docs/superpowers/specs/2026-08-06-sls-ss1-fplc-design.md` §5;
the obligation table it satisfies is `plc/forklift-safety/SPEC.md` §11.7;
the re-qualification it owes is `agv/forklift/PLANT-CHANGE-INVENTORY.md`
§§6–10, whose measurement order §§3–7 below follow.

**Non-claims, before any figure.** The STO contactor is a **stand-in** for
the hardwired onboard inhibit CLAUDE.md's topology draws as the thick
arrow: Python, on the process side of the vehicle, simulating that path's
effect on the plant. **No Category, Performance Level, SIL or PFH is
claimed for it or implied by it** (ADR 0011 D5). It forms no demand — the
demand is the F-program's (invariant 10) — and it is not a safety
function. Nothing below is a stop-time, stop-category or deceleration
measurement.

---

## 0. Environment, and what qualifies every figure

| Item | Value |
|---|---|
| Host | The owner's WSL 2 (Ubuntu on Windows 11), ROS 2 Jazzy, Gazebo Harmonic `gz sim 8.11.0`, all from the apt/vendor stack |
| Isolation | `ROS_DOMAIN_ID=57` **and** `GZ_PARTITION=m5-50-sto`, both, for every run — gz transport is not DDS and the ROS variable does not isolate it (LESSONS 2026-07-27) |
| Date | 2026-08-06 |
| Repository state | Baseline of §3 taken at head `232f3de` with `model.sdf` at `md5 48e22f3fac3baa422e22b1a2d452cd9f`, before the plant moved. Everything from §4 on is the edited tree |
| Worlds | §§3–6 `empty.sdf`; §7 `sim/worlds/warehouse.sdf` through `sim/launch/warehouse_bringup.launch.py`, spawn `x=-4.5 y=7.0 yaw=0.0` |
| RTF | `0.959` mean during the baseline run, `0.949` during the contactor run — measured per trial and reported with the figures rather than assumed |

**Read the two halves of every observation differently** (LESSONS
2026-08-05). The residuals and the pass/fail verdicts below are properties
of the design and reproduce; the latency and distance figures are draws
and carry their n.

---

## 1. What was built

`model.sdf`'s three joint controllers no longer listen on the topics the
vehicle stack publishes. They listen on three **terminals**:

| Plugin, joint | Terminal |
|---|---|
| `JointPositionController`, `steer_joint` | `/forklift/gz/actuator/steer_cmd` |
| `JointController`, `drive_wheel_joint` | `/forklift/gz/actuator/traction_cmd` |
| `JointPositionController`, `mast_joint` | `/forklift/gz/actuator/fork_cmd` |

`scripts/sto_contactor.py` is the terminals' only publisher. While torque
is present it forwards `/forklift/gz/{steer,traction,fork}_cmd` to them
one message for one message. On `/forklift/safety/torque_off_demand`
`TRUE` it **latches open**: it forwards nothing, drives the traction
terminal to a standing `0.0` — the holding brake — and holds the steer and
fork terminals at their last forwarded values.

**Why the model moved and not a command node.** Five committed publishers
address the command topics directly (`forklift_io.py`,
`localization_run.py`, `steer_bench.py`, `safe_speed_bench.py`,
`sim/scenarios/warehouse_mapping_route.py`), so an interlock inside any
one of them would be bypassed by the other four and "deaf to commands"
would be false for four paths out of five.

**Why the brake is a standing zero rather than silence.** gz's
`JointController` holds its last command for ever. A terminal left silent
is therefore a standing order and not an absence — the same mechanism that
produced 0.0852 m of creep in `EVIDENCE_ENVELOPE.md` §9 — so the brake is
a value that is continuously published, not the absence of one.

**Why steer and fork are held rather than zeroed.** Zeroing them would
command a straightening manoeuvre and a carriage descent: motion demanded
*by* the safe state, which is the one thing it must not do.

---

## 2. The fail direction, stated because it is a choice and not an accident

The **absence** of the demand is **not** torque-off. The contactor latches
on an observed `TRUE` and releases on an observed `FALSE`; a link that
never speaks leaves it closed.

That is invariant 2 applied, not a relaxation of it: loss of supervision is
a degraded mode and not a safety event, and the controlled stop it calls
for already exists one layer up in the envelope gate's stale rule
(`EVIDENCE_ENVELOPE.md` §4 measures it at 0.5176 s against a 0.500 s
window). Inferring torque removal from network silence would put a safety
reaction on the network — the thing invariant 1 exists to prevent — and
would make every run without a bridge a dead vehicle.

The direction that **is** fail-safe here is the node's own absence: with
the contactor not running, nothing publishes the terminals and the plant
receives no command from anyone. §5 measures exactly that, because it is
also the change's most dangerous side effect.

---

## 3. The baseline, before the plant moved

Instrument: `scripts/sto_bench.py --phase endtoend --label baseline`. A
step of 4.0 rad/s published on `/forklift/gz/traction_cmd`; the clock
stops when a `/forklift/joint_states` message reports the drive shaft at
or above 0.50 rad/s. It measures the whole path — publisher, bridge,
physics, feedback publication — and the same instrument is used after the
change, so the constant offset cancels in the difference.

| | Value |
|---|---|
| trials attempted / detected | **12 / 12** |
| wall latency, mean | **0.006851 s** |
| wall latency, min / max | 0.001022 / 0.017275 s |
| sim latency, mean | 0.006750 s |
| RTF, mean over the trials | 0.959 |

Record: `evidence/m5-50-endtoend-baseline.json`.

---

## 4. The same measurement, with the contactor in the path

| | Baseline | With the contactor | Difference |
|---|---|---|---|
| trials detected | 12 / 12 | **12 / 12** | — |
| wall latency, mean | 0.006851 s | **0.008319 s** | **+0.001468 s** |
| wall latency, min | 0.001022 s | 0.001161 s | +0.000139 s |
| wall latency, max | 0.017275 s | 0.017885 s | +0.000610 s |
| sim latency, mean | 0.006750 s | 0.008250 s | +0.001500 s |
| RTF, mean | 0.959 | 0.949 | — |

Record: `evidence/m5-50-endtoend-contactor.json`.

**Read the +1.5 ms as an upper estimate of the hop and not as the hop.**
Both columns are n = 12 draws of a quantity whose own min-to-max spread is
16 ms, so the difference of the means is inside the spread of either
column. §4.1 measures the hop directly, and that is the number the
inventory's class-(i) figures should be read against.

### 4.1 The hop, measured directly

Instrument: `--phase passthrough`, 15 s at 20 Hz of a command that is
never constant (`1.5 sin(2πi/37)` rad/s), matched in order against what
appears on the terminal.

| | Value |
|---|---|
| published / seen at the terminal / matched pairs | **299 / 299 / 299** |
| `max abs(terminal − command)` | **0.0** |
| exact matches | **299 of 299** |
| hop latency, mean | **0.000403 s** |
| hop latency, min / max | 0.000242 / **0.000845 s** |

Record: `evidence/m5-50-passthrough.json`.

**The residual is a property; the latency is a draw.** The contactor
republishes the message object it received, so the zero residual is
structural and will reproduce. The 0.40 ms mean is one sample on one
machine on one day, and this repository has already watched an identical
class of figure move by 60x between runs (`EVIDENCE_ENVELOPE.md` §7's
m5-21 correction). **No upper bound is established.**

**What it buys the inventory.** At 0.40 m/s — the speed at which
`EVIDENCE_ENVELOPE.md` §3's stop distance is measured — a 0.845 ms worst
observed hop is **0.34 mm** of extra travel, against a figure of 173.8 mm
whose own two committed draws differ by 1.9 mm. The class-(i) figures are
therefore affected in principle and below their own resolution in
practice. §7 measures the one a criterion path cites rather than resting
on this arithmetic.

---

## 5. The negative control — what the change costs the reader

**This section exists because the change can flatter as easily as it can
prove** (`PLANT-CHANGE-INVENTORY.md` §8). With the contactor stopped and
everything else running unchanged:

| | Value |
|---|---|
| trials attempted / **detected** | 3 / **0** |
| `/forklift/safety/torque_off_applied` | **no publisher; the topic does not exist in the graph** |

Record: `evidence/m5-50-negative-control.json`.

**So a dead contactor and a torque-off are indistinguishable by motion.**
Both produce a vehicle that does not move under a command that reaches the
plant boundary. What tells them apart is the readback: under torque-off
`/forklift/safety/torque_off_applied` publishes `TRUE` at 20 Hz, and with
the contactor absent the topic has no publisher at all.

**The rule this forces on every future run, and it is followed in §6:** an
observation that the vehicle did not move is evidence only beside a
**positive control in the same run**. A run without one is discarded, not
repaired.

---

## 6. The observable — SS1's second stage, and it is testable

Instrument: `scripts/sto_bench.py --phase observable`. Six steps; the
graph carries the full command chain (`velocity_smoother` bypassed, the
bench publishing `/cmd_vel_smoothed` directly into `envelope_gate` →
`cmd_vel_to_tricycle` → `forklift_io` → the plant).

**Three runs, three passes of six steps.** Figures are run 2; runs 3 and 4
are recorded beside it and quoted where they differ.

| Step | What it does | Result, run 2 | Verdict |
|---|---|---|---|
| **O1** positive control | A direct plant command, torque present | **moved 0.3706 m** (run 3: 1.1958 m, run 4: 1.2960 m) | PASS |
| **O2** demand asserted | `torque_off_demand := TRUE` | `torque_off_applied` **TRUE** within 2 s, all three runs | PASS |
| **O3** deaf, direct command | 4 s of 4.0 rad/s straight at the plant | **moved 0.0000 m**, shaft 0.0000 rad/s, with **161 commands delivered to the plant boundary** | PASS |
| **O4** deaf on envelope reopen | The envelope driven fully permissive and a 0.40 m/s `Twist` fed through the real chain for 6 s | **moved 0.0000 m** while the converter formed **128 setpoints** and **128 commands** reached the plant boundary, the last of them **3.3333 rad/s** | PASS |
| **O5** release, no auto-resume | `torque_off_demand := FALSE`, then 2 s in which nobody publishes a non-zero command | `torque_off_applied` **FALSE**; vehicle crept **0.0000 m** | PASS |
| **O6** positive control after | **The same permissive envelope and the same `Twist` that produced nothing at O4** | **moved 2.3723 m** (run 3: 2.3727 m, run 4: 2.3531 m) | PASS |

Records: `evidence/m5-50-observable-run2.json`, `-run3.json`, `-run4.json`.

**O4 is the whole point, and the witness counters are why it is a
measurement rather than an assertion.** 128 tricycle setpoints were formed
and 128 commands reached the plant boundary carrying 3.3333 rad/s — the
chain was not silent, it was ignored. The vehicle moved 0.0000 m.

**O6 is the strongest available control for O4** because it is the
identical stimulus: the same envelope, the same `Twist`, the same chain,
the only difference being that the demand has fallen. It produced 2.37 m
of travel in all three runs against 0.0000 m at O4.

**What a failing run looks like.** O1 or O6 not moving means the path is
dead and the run is discarded rather than read as a pass (§5). O3 or O4
moving at all, or the witness counters reading zero, means the deafness
was never tested — a zero counter says the command was never formed, and
stillness then proves nothing.

**What these six steps do not test.** They exercise the *contactor's* half
of the obligation. The demand was published by the bench, not by the
F-program, because the bridge does not yet carry the `TorqueOffDemand`
mirror (§8, request 1). The standstill-confirmed branch of the sequencer,
the SS1 time limit, and `AT-10` / `AT-11` are Task 6's and are not touched
here.

---

## 7. Re-measured: `EVIDENCE_ENVELOPE.md` §3, with the contactor in the path

Inventory item 3, the one class-(i) figure a gate-criterion path cites.
Run through `sim/launch/warehouse_bringup.launch.py` at `x=-4.5 y=7.0
yaw=0.0` plus `envelope.launch.py feedback:=CLOSED_LOOP`, with the
contactor and a three-topic terminal bridge started by hand (§8, request
2 — that bringup does not yet start them).

| Measured | Committed (`r1`) | Committed repeat (`r13`) | **This run** |
|---|---|---|---|
| ground speed at the enable edge | +0.4000 m/s | — | **+0.4000 m/s** |
| first reduced gated command | 0.0681 s | — | **0.0720 s** |
| first zero gated command | 0.8051 s | — | **0.8086 s** |
| largest single step | 0.0250 m/s | — | **0.0250 m/s** |
| standstill after the edge | 0.850 s | — | **0.850 s** |
| **stop distance** | **0.1738 m** | **0.1719 m** | **0.1744 m** |

Record: `evidence/m5-50-r2-enable-drop-clean.csv`.

**The verdict: the figure is unchanged at its own resolution.** Three
draws now span 0.1719–0.1744 m, a 2.5 mm spread, and the added hop's
worst observed contribution is 0.34 mm. `EVIDENCE_ENVELOPE.md` §3 keeps
its figure; the dated note appended to that file records this run as a
third draw rather than a supersession.

**One run was discarded, and it is recorded rather than deleted.** An
earlier attempt at this scenario measured 0.1717 m with **two**
`forklift_io` and **two** `cmd_vel_to_tricycle` instances alive — leftovers
of the previous session that a `pkill` had failed to kill, because the
pattern matched the killing shell's own command line. The result happens to
sit inside the spread, and it is still discarded: the precondition was not
confirmed before the timed run, which makes it a run whose conditions were
never established (LESSONS 2026-08-06). The clean re-run above states the
process list it ran against.

---

## 8. What this evidence does not establish, and what it asks for

| # | Item | Owner |
|---|---|---|
| 1 | **The demand never came from the F-program.** `TorqueOffDemand`'s mirror has no ROS carrier yet, so every run here published the Bool from the bench. The bridge must publish `/forklift/safety/torque_off_demand` from `Forklift/Safety/TorqueOffDemand` | **bridge/**, with **interface** for the mirror node |
| 2 | **`sim/launch/forklift_bringup.launch.py` still bridges the old command topics and does not start the contactor.** After this change a vehicle brought up that way receives nothing at the plant — the first launch of §7 was exactly that, and it looked like a working bringup. `agv/forklift/launch/vehicle.launch.py` is corrected; the sim bringup is not this layer's file | **sim/** |
| 3 | `sim/worlds/FORKLIFT_ARENA_EVIDENCE.md` §5 and §6 are commanded-to-observed responses through the changed path, and §5's contradiction with the m5-38 traction finding is still open | **sim/** |
| 4 | The inventory's class-A supporting figures — `EVIDENCE_NAV2.md`'s case set, `EVIDENCE_LOCALIZATION.md` (a)/(b), `EVIDENCE_VEHICLE_IMAGE.md` proof 3 — are deferred with the §4.1 qualifier. No criterion cites them and the closure plan freezes autonomy as a prototype | agv/, later |
| 5 | No stop time, stop category, deceleration or integrity figure is claimed anywhere above | — |

---

## 9. How to reproduce

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=<unique> GZ_PARTITION=<unique>      # BOTH, always

# the contactor's logic, no ROS and no simulator
python3 agv/forklift/scripts/sto_contactor.py --self-check

# sections 3-6: the vehicle in an empty world
ros2 launch agv/forklift/launch/vehicle.launch.py world:=empty.sdf \
    nodes:=false tf:=false wheel_odom:=false ekf:=false imu_gate:=false
python3 agv/forklift/scripts/sto_bench.py --phase endtoend --label <tag> \
    --trials 12 --json evidence/m5-50-endtoend-<tag>.json
python3 agv/forklift/scripts/sto_bench.py --phase passthrough \
    --seconds 15 --hz 20 --json evidence/m5-50-passthrough.json

# section 6 additionally needs the command chain; the smoother is bypassed
python3 agv/forklift/scripts/envelope_gate.py --config agv/forklift/config.yaml \
    --ros-args -p use_sim_time:=true
python3 agv/forklift/scripts/cmd_vel_to_tricycle.py --config agv/forklift/config.yaml \
    --cmd-topic /cmd_vel_gated --ros-args -p use_sim_time:=true
python3 agv/forklift/scripts/forklift_io.py --config agv/forklift/config.yaml \
    --ros-args -p use_sim_time:=true
python3 agv/forklift/scripts/sto_bench.py --phase observable \
    --json evidence/m5-50-observable-run<n>.json

# section 5, the negative control: stop ONLY the contactor and repeat endtoend
# section 7: the warehouse, until sim/ carries the contactor itself
ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
ros2 run ros_gz_bridge parameter_bridge \
    /forklift/gz/actuator/steer_cmd@std_msgs/msg/Float64]gz.msgs.Double \
    /forklift/gz/actuator/traction_cmd@std_msgs/msg/Float64]gz.msgs.Double \
    /forklift/gz/actuator/fork_cmd@std_msgs/msg/Float64]gz.msgs.Double
python3 agv/forklift/scripts/sto_contactor.py --config agv/forklift/config.yaml \
    --ros-args -p use_sim_time:=true
ros2 launch agv/forklift/launch/envelope.launch.py feedback:=CLOSED_LOOP
python3 agv/forklift/scripts/envelope_run.py run --scenario enable-drop \
    --csv evidence/m5-50-<tag>.csv
```

**One recording per run and a unique tag per run** — the harnesses truncate
what they are pointed at. **Confirm the process list before every timed
run and record it**; and match a `pkill` pattern so it cannot kill the
shell that issues it (a bracketed first character does it).
