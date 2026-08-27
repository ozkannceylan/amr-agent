# EVIDENCE_NAV_V3.md — Nav2 drives the truck (F4)

**§1 – §12 are F4 Task 1: THE COMMAND PATH.** The line a Nav2 controller
will eventually push a `cmd_vel` down — a velocity smoother, a tricycle
converter, two motor terminals — built, limited, and measured with **no
Nav2 anywhere in the room**, which is the only way a figure about the
path can avoid being a figure about the planner as well.

Everything below was measured on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, gz-sim 8.11.0, RTX 4050) on **2026-08-27**, **headless**, on the
**nominal plant** (`traction=nominal`), the **default estimator arm**
(`arm=wheel+imu`) and **without localisation** (`loc=none`). Every figure
names the instrument that produced it and every session names the
smoother it was taken behind.

**The dry bar is what this task is accepted on** (F4 constraint 19).
Nothing here is a safety claim: the converter inhibits nothing, latches
nothing and stops nothing, and `/speed_limit` is a **demonstrated
interface** and not an envelope that is enforced by anything. The
sentence this track keeps verbatim, from `docs/reports/m5v3-02` §5,
belongs beside every mention of it: the collision monitor **"does not
provide hard real-time safety certifications"** and does not replace a
safety-rated PLC. It complements the F-PLC; it is not the F-PLC.

---

## 0. The answer, before the working

| | |
|---|---|
| **the path, end to end** (terminal ÷ commanded, settled) | **1.0000** on `straight`, `creep`, `corner_creep`; **0.7071** on `corner_cruise`, which is the traction clamp doing exactly `cos(0.785398)` |
| **the plant's own controller** (achieved ÷ terminal) | **1.0000** in every settled window of every profile |
| **the conversion, LIVE on the wire** | worst `|dv|` **4.0e-11 m/s**, worst `|dw|` **2.1e-10 rad/s**, over 79–240 settled terminal samples per profile — including both clamps and a standing speed limit |
| **the conversion, against the ESTIMATOR that ships** | round trip through `wheel_odom_core.WheelOdometry`, 7 cases, **≤ 1e-5** against a quantisation floor of ~4e-6 m/s |
| **steer slew at the terminal** | worst step **0.100000 rad/tick** = the configured 2.0 rad/s ramp, exactly; never above it |
| **tread slew at the terminal** | worst step **0.017500 m/s/tick** = the configured 0.35 m/s² ramp, exactly; never above it |
| **the corner, against `drive_route`'s own** | the twist path put **−0.785398 rad** and **−0.3000 m/s** on the terminals — `drive_route.profiles.corner_creep`'s row to five decimals — and the plant delivered **1.006** of the commanded yaw rate against F1.5's **1.005** |
| **the speed limit, at the ACTUATOR TERMINAL** | tread **−0.7000 → −0.3000 → −0.7000 m/s** as `nav2_msgs/SpeedLimit` went 0.3 m/s → lifted; `terminal ÷ commanded` **0.4286** = 0.300/0.700 |
| **the stop from cruise** | terminal to zero **2.03 s** (0.344 m/s² of tread), truck at rest **2.07 s**, **1.019 m** travelled against the **0.690 m** `v²/2a` predicts |
| **THE RULING THIS TASK REVERSED** | the crib's `feedback: CLOSED_LOOP` **ships as OPEN_LOOP** on this stack, on the A/B in §6 |
| **what it costs idle** | `smoother` **3.67 %** and `navcmd` **0.77 %** of one core; **zero messages** on either terminal until something commands |

---

## 1. The rig, the sessions, and what every figure was taken on

Six sessions, all under `logs/evidence/`, all recorded by
`tools/drive_twist.py record`, all on the nominal plant with the shipping
estimator and no localisation:

| session | profile | smoother |
|---|---|---|
| `twist-straight-20260827-072834` | `straight` | `OPEN_LOOP`, md5 `9cccb236` |
| `twist-creep-20260827-072951` | `creep` | `OPEN_LOOP`, md5 `9cccb236` |
| `twist-corner_creep-20260827-073046` | `corner_creep` | `OPEN_LOOP`, md5 `9cccb236` |
| `twist-corner_cruise-20260827-073145` | `corner_cruise` | `OPEN_LOOP`, md5 `9cccb236` |
| `twist-speed_limit-20260827-073236` | `speed_limit` | `OPEN_LOOP`, md5 `9cccb236` |
| `twist-straight-20260827-072725` | `straight` | **`CLOSED_LOOP`**, md5 `0e111fc8` — §6's control |

**THE SMOOTHER IS PART OF THE LABEL, AND IT HAD TO BE.** This track
already refuses to table a slippery run beside a nominal one, an `rf2o`
run beside a `wheel+imu` one, or a localised run beside an unlocalised
one — every one of those because the CSVs are otherwise identical and
nothing in the numbers says which is which. §6's A/B is exactly that
failure in a new place: two runs of one profile, on one plant, with one
estimator, differing in **one line of one file**. So
`tools/drive_twist.py` writes `smoother_feedback=` and `smoother_md5=`
into every session's `session.txt`, hashed off the file on disk at the
moment it was used — which is `m5v3.sh`'s own rule for the frozen map's
`loc=` label, one layer across.

Each session holds six headered CSVs — what was commanded, what the
smoother made of it, what each terminal carried, what the axes did and
what the truck did — plus `session.txt`. They are not committed
(`logs/` is git-ignored and they run to 12 500 rows of joint state
apiece); `straight`'s six carry md5s `b60be1d4`, `af7c0c09`, `ce617ade`,
`b9a463ef`, `1873658a`, `26cbf35c`.

---

## 2. The datasheet: every limit, where it came from, and what keeps it honest

| quantity | value | source | what checks it |
|---|---|---|---|
| wheelbase `L` | 1.05 m | `model.sdf` link poses, via `config.yaml vehicle.wheelbase_m` | — |
| drive wheel radius `r` | 0.12 m | `model.sdf` `drive_wheel` collision | — |
| **steer stop** | **±1.31 rad** | `model.sdf` `steer_joint` `<lower>/<upper>` | `test_cmd_vel_tricycle_core.py` reads the SDF and fails on a disagreement |
| **steer slew** | **2.0 rad/s** | `model.sdf` `steer_joint` `<velocity>` | the same test, the same way |
| drive joint ceiling | 40 rad/s = **4.8 m/s** of tread | `model.sdf` `drive_wheel_joint` `<velocity>` | quoted, not used — see below |
| **commanded steer ceiling** | **1.25 rad** | `drive_route.profiles.square` — the hardest steer this plant has ever been driven at | a test asserts it is IN that table, and inside the stop |
| **curvature ceiling** | **2.8662568 1/m**, R **0.3488871 m** | derived once, `cmd_vel_tricycle_core.curvature_max()` | a test recomputes it from the angle |
| **tread ceiling** | **0.700 m/s** | `drive_route.profiles.straight` cruise — every straight-line figure on this track | a test asserts it equals that table's maximum |
| **acceleration** | **0.35 m/s²** | `drive_route.profiles.straight`'s own ramp, 0.175 m/s per 0.5 s | `test_smoother_params.py` recomputes both files' copies |
| creep deadband | 0.005 m/s | must be under `accel × dt` = 0.017500 | a test asserts it |
| standstill | 0.001 m/s | 1 mm/s | a test asserts it is under the deadband |
| yaw-rate refusal | 0.01 rad/s | 20× below the plant's own measured corner rates | — |

**THE TREAD CEILING IS A MEASUREMENT-COVERAGE CAP AND NOT A MOTOR
LIMIT**, and the two are 6.9× apart. `model.sdf` will accept 4.8 m/s of
tread; this stack will not command more than 0.700, because above it this
plant has never been driven and no figure on this track describes it.

**THE CURVATURE CEILING IS ALSO A MEASUREMENT AND THE MECHANICAL STOP
STANDS BEHIND IT.** 1.31 rad is a turning radius of 0.2802 m and nothing
has ever driven there; 1.25 rad is `square`'s four corners. A twist
clamped at 1.25 can never reach 1.31, so **a mechanical steer clamp on
this stack is a bug and not a manoeuvre** — which is why the converter
counts the two separately, and why its status topic raises the level for
the second one and not for the first.

### 2.1 What the plant DELIVERS at that ceiling — the number F4 Task 2 needs

The ceiling is what is **commanded**. What the plant does with it is
`EVIDENCE_LATERAL_TUNE.md`'s measurement, restated here as a radius
because that is the form a planner's `minimum_turning_radius` takes:

| | commanded | delivered, four-corner mean | delivered, worst single corner |
|---|---|---|---|
| yaw rate at 0.300 m/s of tread, δ = 1.25 rad | 0.271136 rad/s | **0.246312** (0.908) | **0.2277** (0.840) |
| curvature | 2.8662568 1/m | **2.6038 1/m** | **2.4071 1/m** |
| **radius** | **0.3489 m** | **0.3841 m** | **0.4154 m** |

The four corners are **11.5 % apart** because they are at four different
headings, and no single number removes that. **A planner sized on the
commanded 0.3489 m would plan arcs this vehicle cannot drive.** The
honest floor to hand F4 Task 2 is the worst single corner: **0.4154 m**.

---

## 3. The command path, as a line

F4 constraint 18: one line, no bypass.

```
Nav2's controller (F4 Task 2)
  -> /cmd_vel
    -> velocity_smoother              (child `smoother`, smoother.yaml)
      -> /cmd_vel_smoothed
        -> nodes/cmd_vel_tricycle.py  (child `navcmd`, config.yaml navcmd:)
          -> /forklift/gz/actuator/steer_cmd     [rad]
             /forklift/gz/actuator/traction_cmd  [rad/s]
             ... over the parameter bridge's TWO ROS -> gz lines
```

**BOTH CHILDREN GO UP WITH THE STACK AND NEITHER IS BEHIND A FLAG.** A
line that exists on some arms and not others is not one line; the
open-loop verification in §7 needs the path with no Nav2 in it; and F4
Task 2's `--nav` arm stacks a planner on top of a path that is already
there, which is the shape `--localize` already has over the estimator.
The default stack is **eight children** (nine with a window) and the
`--localize amcl` stack is **eleven**.

**GROUND TRUTH IS NOT IN THE LOOP.** Nothing on this path subscribes
`topics.odom_ground_truth`; `tests/test_cmd_vel_tricycle_shell.py`
asserts the string does not occur in the converter at all. The one thing
that could have closed a loop — the smoother's feedback — is fed the
**estimate**, addressed per estimator arm from `m5v3.sh` so a parameter
file cannot pin the wrong one, and §6 rules that it is not read at all.

### 3.1 The bringup gate, and why it is not the one that already exists

Every check `m5v3.sh start` already made is satisfied by **three
processes that have never spoken to each other**: the smoother ACTIVE
with nothing subscribed to its output, a converter ALIVE with a misspelt
subscription, a bridge line written `[` where it needed `]`. In all three
cases every log is clean, `status` reads ALIVE, and **nothing is
published** — which at rest is exactly what a healthy command path looks
like too.

So `tools/navcmd_health.py` publishes **one zero twist** — the only
command that cannot move this vehicle — and reads the answer back off the
**gz side** of the traction terminal, which is the far end of the last
hop. Measured on every bringup in this task:

```
  navcmd: the command path is one line. A zero twist on /cmd_vel arrived at
          /forklift/gz/actuator/traction_cmd (gz side) as +0.000000 rad/s - through the smoother,
          the converter and the bridge, four hops, none of them silent any more.
          The steer terminal was NOT commanded: a zero twist HOLDS the axis.
```

A zero twist is below the creep deadband, so the converter answers it
with a standing zero on the traction terminal and a **held** steer axis —
which is why the gate does not demand a steer message. A gate that did
would be demanding that this stack move the wheel at every bringup.

---

## 4. The conversion, checked three ways

`nodes/cmd_vel_tricycle_core.py` is the **inverse** of the kinematics
`nodes/wheel_odom_core.py` integrates. That is the whole specification,
and it is checked at three different distances from the wire.

**(a) AGAINST THE ESTIMATOR THAT SHIPS.** `tests/test_cmd_vel_tricycle_core.py`
converts a twist to `(steer, tread)`, drives *that pair into
`wheel_odom_core.WheelOdometry` as shaft angles*, and reads the twist
back out. Seven cases — cruise both ways, the corner speed both hands,
the measured −1.25 rad corner, astern on lock, a crawl on a gentle arc —
all inside **1e-5**, against a quantisation floor of about 4e-6 m/s at
2²² counts a revolution.

  This is deliberately **not** the crib's round trip.
  `agv/forklift/scripts/cmd_vel_to_tricycle.py --self-check` rounds the
  trip through a forward model written a hundred lines below its own
  inverse, by the same hand; that catches a typo. Rounding it through the
  file that will actually be asked what the vehicle did catches **the two
  halves of this track disagreeing about which way is forward**.

**(b) ON THE RIG, WITHOUT PYTEST.** `python3 nodes/cmd_vel_tricycle_core.py
--selftest` → **21/21 checks passed**, covering the signs, the three
limits, the refusal and the ramp.

**(c) LIVE, ON THE WIRE.** For every traction sample inside a settled
window, `tools/drive_twist.py analyse` takes the steer angle in force and
the tread the terminal carried, puts the pair back through the forward
model, and compares it with what the core says that pair *should* have
been given the smoothed twist that reached the node and the speed limit
standing at the time:

| profile | settled samples | worst `|dv|` | worst `|dw|` |
|---|---|---|---|
| `straight` | 240 | **4.000e-11 m/s** | 0.000e+00 rad/s |
| `creep` | 240 | 0.000e+00 | 0.000e+00 |
| `corner_creep` | 200 | 1.045e-11 | 3.669e-11 |
| `corner_cruise` (traction clamp active) | 79 | 1.683e-10 | 2.142e-10 |
| `speed_limit` (envelope standing) | 240 | 4.000e-11 | 0.000e+00 |

**IT IS THE CLAMPED TWIST AND NOT THE COMMANDED ONE**, which is the whole
difference between a round trip and a complaint. Where the converter
clamps — the traction ceiling on a corner at cruise, the envelope on a
limited segment — the terminal is *deliberately* not the conversion of
what arrived, and comparing it against that reported the node's own
design as a 0.2 m/s error before this was fixed.

---

## 5. The slew, at the terminals

`model.sdf`'s traction terminal is a **raw velocity command with no
ramp** — the plugin's own comment says so — and its steer axis carries a
2.0 rad/s limit the physics enforces whatever is commanded. The converter
ramps both in its **own output**, so the delivered arc is a function of a
ramp that is written down rather than of a slew somebody has to measure
afterwards. `config.yaml drive_route.profiles.square` records what the
second costs: 0.057250 rad of yaw lost per corner, and a corner time that
had to be re-derived around it.

| profile | worst steer step | worst tread step |
|---|---|---|
| `straight` | **0.000000 rad** (end to end) | 0.017500 m/s over 0.0520 s |
| `creep` | **0.000000 rad** | 0.017500 m/s over 0.0500 s |
| `corner_creep` | **0.100000 rad** over 0.0500 s | 0.017500 m/s over 0.0500 s |
| `corner_cruise` | 0.075098 rad over 0.0580 s | 0.017500 m/s over 0.0500 s |
| `speed_limit` | **0.000000 rad** | 0.017500 m/s over 0.0500 s |
| **the ramp** | **0.100000 rad/tick** (2.0 rad/s × 0.05 s) | **0.017500 m/s/tick** (0.35 m/s² × 0.05 s) |

**The worst step is the ramp, exactly, and never more.**

**THE STEP IS THE THING COMPARED AND NOT THE RATE**, and the difference
is not pedantry. The limiter advances `limit × dt` per tick with `dt`
capped at one nominal period whatever the timer actually did
(`forklift_io.py`'s rule: under-travel is the conservative direction). A
tick that fires 6 ms early therefore carries the full period's step over
a 0.044 s interval and reads as **0.3977 m/s²** — above a limit the ramp
never exceeded. The analyser prints the step, the interval and the rate
side by side so a reader can see which is which rather than being told.

---

## 6. The velocity smoother: four measured facts, and one reversed ruling

### 6.1 Four things measured about the node itself

1. **`enable_stamped_cmd_vel` DEFAULTS TO FALSE on this Jazzy.** `ros2
   node info` on the running node reads `geometry_msgs/msg/Twist` on both
   `/cmd_vel` and `/cmd_vel_smoothed`. **This corrects the research this
   phase was planned from** — `docs/reports/m5v3-02` §5 says "Jazzy
   defaults to `TwistStamped`", and on this rig it does not.
   `smoother.yaml` states the parameter explicitly anyway, and a test
   asserts the converter's subscription agrees with it.
2. **`autostart_node: true` drives it to ACTIVE unaided.** The log reads
   `Auto-starting node` / `Configuring` / `Activating` and `ros2
   lifecycle get` reads `active [3]` with no external transition. So
   `m5v3.sh` **polls** for that state (`smoother_active()`) instead of
   driving the transitions the way it drives the localisation arm's — a
   different mechanism, not a second copy of one.
3. **It publishes NOTHING when idle.** `ros2 topic hz /cmd_vel_smoothed`
   reported no messages at all over 4 s with the node ACTIVE and nothing
   commanding; after a burst it emits its own deceleration ramp to zero
   and then stops. That is what lets it be a default stack child without
   fighting the two gz-side benches.
4. **IT HAS NO `/speed_limit` INTERFACE, AND THAT WAS READ RATHER THAN
   ASSUMED.** §9's placement of the envelope hook in the converter turns
   on this, so it is a measurement and not a deduction from the
   parameter list. On the **shipping** stack, ACTIVE, with this file's
   own remaps and `bond_heartbeat_period: 0.0`:

   ```
   $ ros2 node info /velocity_smoother
   /velocity_smoother
     Subscribers:
       /clock: rosgraph_msgs/msg/Clock
       /cmd_vel: geometry_msgs/msg/Twist
       /parameter_events: rcl_interfaces/msg/ParameterEvent
     Publishers:
       /cmd_vel_smoothed: geometry_msgs/msg/Twist
       /parameter_events: rcl_interfaces/msg/ParameterEvent
       /rosout: rcl_interfaces/msg/Log
       /velocity_smoother/transition_event: lifecycle_msgs/msg/TransitionEvent
   ```

   **Three subscriptions and none of them is `/speed_limit`** — so the
   smoother was never a candidate for the hook, and `docs/reports/m5v3-02`
   §5 is right that the interface belongs to the **controller server**,
   which this task does not run. This read also carries fact 1 in
   passing (`geometry_msgs/msg/Twist` on both sides, not `TwistStamped`)
   and shows the bond gone, which is what `bond_heartbeat_period: 0.0`
   is for.

   And the other end of the same question, on the same stack:

   ```
   $ ros2 topic info /speed_limit -v
   Type: nav2_msgs/msg/SpeedLimit
   Publisher count: 0
   Subscription count: 1
     Node name: m5v3_cmd_vel_tricycle
   ```

   **One subscriber, and it is the converter.** Zero publishers at rest
   is the honest state of a demonstrated interface whose PLC has not
   arrived: `tools/drive_twist.py` is the only thing on this track that
   has ever published there.

### 6.2 And two about `scale_velocities`, measured in isolation

On domain 99, no simulator: the smoother against a fake odometry holding
a constant twist, with `/cmd_vel` held at zero.

| fake measured twist | first smoothed output | what it says |
|---|---|---|
| `vx −0.7000, vy 0, wz 0` | `−0.682500` | the step is **exactly** `accel × dt` = 0.017500 |
| `vx −0.7000, vy +0.0200, wz 0` | `vy +0.020000` | a measured lateral term is **copied through**: `max_accel[1]` is 0, so the change allowed on that axis is nothing |
| `vx −0.7000, vy 0, wz −0.0300` | `wz −0.029250` | `scale_velocities` scales the CHANGE on **every** axis by the most restrictive axis's factor — here **η = 0.025**, taken from the linear axis. A measured yaw rate therefore decays **40× slower than its own limit**. |

The second is why the converter **reports** a lateral term against
`d·angular.z` instead of warning that something upstream believes the
base is holonomic: on this chain the commonest cause of a non-zero
`linear.y` is the vehicle turning, because `base_link` stands 0.50 m
forward of the rear axle and the smoother copies the estimate's own
`d·ω` straight through.

### 6.3 THE A/B: `CLOSED_LOOP` is the crib's ruling and it does not survive here

One profile, one plant, one estimator, **one line of one file changed**:

| | `CLOSED_LOOP` (`072725`, md5 `0e111fc8`) | `OPEN_LOOP` (`072834`, md5 `9cccb236`) |
|---|---|---|
| terminal ÷ commanded, settled | 0.9999 | **1.0000** |
| delivered ÷ commanded | 0.9624 | **0.9841** |
| live conversion round trip, worst `|dv|` | 3.879e-03 m/s | **4.000e-11 m/s** |
| ramp UP to cruise | 0.150 m/s² | **0.344 m/s²** |
| stop from cruise: terminal to zero | **never, inside the record** | **2.03 s** |
| stop from cruise: truck at rest | not reached — still at 0.23 m/s after 6 s | **2.07 s, 1.019 m** |
| smoothed `|w|` on a DEAD STRAIGHT profile | up to **0.016787 rad/s** | **0.000000** |
| steer terminal travel, same profile | **−0.222626 rad** (12.8°) | **0.000000 rad** |

**The last two rows are the finding, not the first six.** A profile that
commands `w = 0` from end to end put a 12.8° swing into the steer axis,
because §6.2's η drag keeps a measured yaw rate alive through every
deceleration and the converter faithfully converts it.

**WHY IT FAILS HERE, AND IT IS THIS TRACK'S WHOLE SUBJECT.** The estimate
a `CLOSED_LOOP` smoother closes on is F1/F2's deliberately **bad**
instrument: quantised onto a 1024-count grid, 1.5 % long by construction,
and filtered. A limiter closed on it inherits its lag, so every tick the
ramp advances 0.0175 m/s from a number that is already behind the
vehicle. The crib's own failure mode — *the vehicle not following* — was
measured **not arising**: `achieved ÷ terminal` is **1.0000** in every
settled window of every profile, because `model.sdf`'s `JointController`
is a velocity controller and tracks its order to 0.04 %.

**WHAT IS GIVEN UP IS BOUNDED AND IS NOT GIVEN UP.** If the vehicle ever
does stop following, `OPEN_LOOP` will ramp away from it — and the command
that reaches the plant is still ramp-limited **a second time, at the
wheel**, by the converter's own limiter. The step the crib is afraid of
cannot reach the terminal on this chain.

**RULING: `feedback: OPEN_LOOP` ships.** `smoother.yaml` carries the
table and the argument; `tests/test_smoother_params.py` asserts the
value, so the reversal cannot be undone by accident.

---

## 7. What the path delivered, profile by profile

Settled windows only: `evidence.corner.settle_s` (4 s) discarded,
`evidence.corner.window_s` (3 s) minimum averaged — the same two numbers
`sensor_evidence.py` uses on a held corner, because a command path has
the same two problems.

| profile | commanded `v, w` | terminal `steer, tread` | achieved `steer, tread` | delivered `v, w` (truth) |
|---|---|---|---|---|
| `straight` | −0.7000, +0.0000 | +0.00000, −0.7000 | +0.00001, −0.7000 | −0.6889, −0.0000 |
| `creep` | −0.3000, +0.0000 | +0.00000, −0.3000 | +0.00001, −0.3000 | −0.2965, −0.0000 |
| `corner_creep` | −0.2121, +0.2020 | **−0.78540, −0.3000** | −0.78586, −0.3000 | −0.2014, **+0.2032** |
| `corner_cruise` | −0.7000, +0.6667 | −0.78540, **−0.7000** | −0.78573, −0.7000 | −0.3380, +0.5190 |
| `speed_limit` §1 | −0.7000, +0.0000 | +0.00000, −0.7000 | +0.00002, −0.7000 | −0.6777, +0.0000 |
| `speed_limit` §2 (0.3 m/s) | −0.7000, +0.0000 | +0.00000, **−0.3000** | +0.00001, −0.3000 | −0.2992, −0.0000 |
| `speed_limit` §3 (lifted) | −0.7000, +0.0000 | +0.00000, −0.7000 | +0.00001, −0.7000 | −0.6874, −0.0000 |

**FOUR RATIOS AND NOT ONE**, because "delivered ÷ commanded" folds four
different things into one number and only the first is this phase's
subject:

| profile / segment | terminal ÷ cmd | achieved ÷ terminal | delivered ÷ achieved | delivered ÷ cmd |
|---|---|---|---|---|
| | *the command path* | *the plant's controller* | *THE TYRE (F1.5's subject)* | *the product* |
| `straight` | **1.0000** | **1.0000** | 0.9841 | 0.9841 |
| `creep` | **1.0000** | **1.0000** | 0.9884 | 0.9884 |
| `corner_creep` | **1.0000** | **1.0000** | 0.9500 | 0.9496 |
| `corner_cruise` | **0.7071** | **1.0000** | 0.6831 | 0.4829 |
| `speed_limit` §1 | **1.0000** | **1.0000** | 0.9682 | 0.9682 |
| `speed_limit` §2 | **0.4286** | **1.0000** | 0.9973 | 0.4274 |
| `speed_limit` §3 | **1.0000** | **1.0000** | 0.9820 | 0.9820 |

The two columns that are not 1.0000 in the first two rows are **the two
clamps working**: `corner_cruise`'s 0.7071 is `cos(0.785398)` to four
decimals — the traction ceiling scaling a whole twist that asked the
wheel for 0.989949 m/s — and `speed_limit` §2's 0.4286 is 0.300/0.700.
Neither is an error and both are curvature preserving.

### 7.1 The corner, against `drive_route`'s own corner

`twist_route.profiles.corner_creep` is the exact kinematic equivalent of
`drive_route.profiles.corner_creep`'s held row, and this is the check
that makes the two benches comparable:

| | `drive_route` (gz terminals, direct) | `drive_twist` (twist through the whole path) |
|---|---|---|
| steer at the terminal | −0.785398 rad, by table | **−0.78540 rad**, by conversion |
| tread at the terminal | −0.300 m/s, by table | **−0.3000 m/s**, by conversion |
| delivered yaw rate | 0.203768 rad/s (F1.5) | **0.2032 rad/s** |
| delivered ÷ kinematic | **1.005** (F1.5) | **1.006** |

**The command path reproduced the terminal path's manoeuvre to five
decimals and the plant's answer to 0.3 %.** Every layer this task added —
the smoother's ramp, the converter's arithmetic, the steer slew, the
bridge — is inside that.

### 7.2 The one thing the plant does that the path does not

`corner_cruise` delivers **0.6831** of the tread it achieved and yaws
**1.073** of the rate the achieved pair predicts kinematically: at cruise
on the commanded lock the rear contact patches scrub, so the truck
translates less and turns more than the geometry says. That is
`EVIDENCE_LATERAL_TUNE.md`'s heading-dependent spread at hard steer, seen
from the other end, and it is **the plant and not the path** — `terminal
÷ commanded` and `achieved ÷ terminal` are both exactly what they should
be on that row. Recorded, not tuned around (F4 constraint 19).

---

## 8. The stop, which is the figure a controller inherits

| profile | entry body / tread | terminal to zero | truck at rest | travelled | `v²/2a` |
|---|---|---|---|---|---|
| `straight` | 0.6948 / 0.7000 | 2.03 s (0.344 m/s² of tread) | 2.07 s | **1.019 m** | 0.690 m |
| `speed_limit` | 0.6938 / 0.7000 | 2.05 s (0.341) | 2.11 s | **1.041 m** | 0.688 m |
| `creep` | 0.2990 / 0.3000 | 0.91 s (0.331) | 0.97 s | 0.208 m | 0.128 m |
| `corner_creep` | 0.2283 / 0.3000 | 0.88 s (0.340) | 0.94 s | 0.148 m | 0.074 m |
| `corner_cruise` | 0.4403 / 0.7000 | 2.65 s (0.264) | 2.66 s | 0.909 m | 0.277 m |

**THE STOPPING DISTANCE FROM CRUISE IS 1.02–1.04 m AND NOT THE 0.69 m
THE RAMP PREDICTS**, and the 48 % is dead time rather than a slow ramp:
the truck holds cruise for about **0.25 s** after the zero arrives (one
smoother tick, one converter tick and the plant's own response), which is
0.17 m at 0.695 m/s, and the rest is the S-shape at either end of the
ramp. The tread ramp itself ran at 0.331–0.344 m/s² against the 0.350
configured.

  **`corner_cruise`'s 2.65 s is the converter's own wheel-domain limiter
  and not a slow smoother.** On that arc the body twist ramps down at
  0.35 m/s², so the tread TARGET falls at `0.35 / cos(0.785398)` =
  0.495 m/s² — faster than the converter will move the wheel. The tread
  therefore sits clamped at 0.700 for the first 0.59 s and then ramps at
  its own 0.35, which is 2.59 s in total against the 2.65 measured.
  **The wheel-domain limiter binding on a corner is the reason it
  exists**: without it the terminal would have taken a 0.495 m/s² step
  the smoother never saw.

---

## 9. `/speed_limit`, demonstrated

`nav2_msgs/SpeedLimit` on nav2's own topic name, published by
`tools/drive_twist.py` from the profile's own table, read at the
**actuator terminal**:

| segment | published | tread at the terminal | terminal ÷ commanded |
|---|---|---|---|
| 1 | *(nothing — no limit standing)* | **−0.7000 m/s** | 1.0000 |
| 2 | `percentage: false, speed_limit: 0.300` | **−0.3000 m/s** | **0.4286** |
| 3 | `percentage: false, speed_limit: 0.000` | **−0.7000 m/s** | 1.0000 |

`0.0` is **NO LIMIT** and not a stop — the message's own comment says so
("When no-limit it is set to 0.0"), and a node that read it as a stop
would brake the vehicle every time a limit was lifted. The limit scales
the **whole** twist, so it is curvature preserving; a percentage is a
percentage of the configured maximum and cannot raise it.

**IT IS AN INTERFACE THAT HAS BEEN DEMONSTRATED. IT IS NOT A SAFETY
CLAIM.** The PLC that will publish it arrives in a later integration
phase. Nothing on this path inhibits motion, latches a fault or performs
a stop; protective stop, e-stop and safe torque off are onboard and
hardwired in the plant this models, and no message on any of these topics
can trigger or release one. The collision monitor — which this phase does
not run — **"does not provide hard real-time safety certifications"** and
does not replace a safety-rated PLC. It complements the F-PLC; it is not
the F-PLC.

**AND IT IS IN THE CONVERTER BECAUSE THE SMOOTHER HAS NO SUCH
INTERFACE**, which was READ off the running node and not assumed:
§6.1 fact 4 is the `ros2 node info` output — three subscriptions, none
of them this one. The research puts the hook on the **controller
server**, which this task does not run, so the converter is the only
place a limit could have been demonstrated at all today — and it is also
the place an envelope belongs, being the last node before the terminals
and therefore the one no upstream publisher can get round.

**TWO SUBSCRIBERS ARE EXPECTED AND THEY COMPOSE.** F4 Task 2's controller
server subscribes the same topic through its own `speed_limit_topic` and
clamps the speed it **plans** at; the converter clamps the speed it
**delivers**, last, where no upstream publisher can get round it. Two
ceilings on one quantity is a `min()`, which is idempotent — and the
second is the only one that is still true when the thing publishing
`cmd_vel` is a bench rather than a planner.

---

## 10. What it costs when nothing is commanding

Measured over 30 s of wall clock on the **`--localize amcl`** stack
(eleven children), reading each node's own `/proc` — and the *node's*,
not the `ros2 run` wrapper's:

| child | idle CPU, % of one core |
|---|---|
| `smoother` | **3.67 %** |
| `navcmd` | **0.77 %** |
| `amcl` | 4.60 % |
| `ekf` | 12.23 % |
| `odom` | 27.80 % |

RTF on that stack: **mean 0.9984, median 0.9999, floor 0.9284** over 296
samples in 30 s (`tools/rtf_probe.sh`).

And the claim the whole engagement rule rests on — **8 s of idle, with
both children up**:

| topic | messages in 8 s |
|---|---|
| `/cmd_vel` | **0** |
| `/cmd_vel_smoothed` | **0** |
| `/forklift/gz/actuator/steer_cmd` (ROS) | **0** |
| `/forklift/gz/actuator/traction_cmd` (ROS) | **0** |
| `/forklift/gz/actuator/traction_cmd` (**gz side**) | **0** |
| `/m5v3/navcmd/status` | 6 (the 1 Hz heartbeat) |

**That is why `tools/drive_route.py` and `tools/slip_bench.sh` still
work.** They address the gz side of the same two terminals directly and
gz transport takes the last write; what keeps the two from fighting is
not the bridge, it is that the converter publishes nothing until a twist
arrives and stops again once it has left a standing zero.

---

## 11. Both arms, and the sweep

F4 constraint 20. Both bringups on the committed tree, headless:

| arm | children | result |
|---|---|---|
| **default** | 8 | all ALIVE; `ekf` healthy (worst covariance 0.22248 / ceiling 100); `velocity_smoother active`; **navcmd gate passed** |
| **`--localize amcl`** | 11 | all ALIVE; `ekf` healthy (0.11988); `velocity_smoother active`; **navcmd gate passed**; `map_server active`, `amcl active`, `loc: healthy` (0.23049 / ceiling 1); `loc=amcl@735cdbc6` |

**AND `stop` FINDS BOTH NEW CHILDREN, WRAPPER AND NODE.** The sweep is
what catches the process `ros2 run` forked, and F3 Task 3 paid a whole
measurement session for a missing pattern. Measured on the `--localize`
stack:

```
  swept 87698 (velocity_smoother)     <- the `ros2 run` wrapper
  swept 87758 (velocity_smoother)     <- the node itself
  swept 87726 (cmd_vel_tricycle.py)
  ...
=== survivors? ===
  none
```

`tests/test_sweep_patterns.py` **parses `m5v3.sh` itself** for both new
spawns and requires a pattern for each, in both estimator scopes.

---

## 12. What F4 Task 2 inherits

1. **The command path exists on every arm** and takes a
   `geometry_msgs/Twist` on `/cmd_vel`. A controller server needs no
   knowledge of the geometry below it.
2. **`minimum_turning_radius` must be ≥ 0.4154 m**, not the 0.3489 m the
   commanded ceiling implies and not the 0.2802 m the mechanical stop
   implies. §2.1 is the derivation and the 11.5 % spread is why the worst
   corner and not the mean.
3. **Stopping distance from cruise is 1.02–1.04 m**, 48 % more than
   `v²/2a`, with about 0.25 s of dead time in the chain. A collision
   look-ahead or a goal tolerance sized on 0.69 m is sized on arithmetic
   rather than on this vehicle.
4. **The cruise + corner combination is speed-limited by the wheel.** At
   0.700 m/s any real curvature meets the traction ceiling and the
   converter scales the twist — curvature preserving, but the delivered
   body speed on the commanded lock is 0.495 m/s and the truck actually
   made 0.338. A controller that plans cruise through a corner will get a
   slower corner, and it will get it silently unless it reads
   `/m5v3/navcmd/status`'s `traction_clamps`.
5. **`/speed_limit` is already wired at the terminal.** Task 2's
   controller server may subscribe the same topic; the two compose.
6. **`refusals` and `steer_clamps` on the status topic are the checks
   that Task 2's behaviour tree kept `Spin` out.** A tricycle cannot
   rotate in place; `nav2`'s `Spin` sends `v = 0` exactly, which is the
   one thing the converter refuses.

---

## 13. What this task did NOT do

- **No planner, no controller, no behaviour tree, no costmap.** Every
  twist in this file came from a table in `config.yaml`.
- **No closed loop of any kind.** `drive_twist` reads no pose and
  corrects nothing; the ground truth it records is an instrument.
- **No collision monitor**, and therefore no polygon, no slowdown and no
  stop action. Task 3 owns it.
- **No wet set.** Every figure here is `traction=nominal`. The clamps and
  the ramps are properties of the path and would not move; the
  `delivered ÷ achieved` column would, and it is the tyre's.
- **No `--rf2o` or `--fuse` arm.** The smoother's `odom_topic` follows
  the estimator arm and is not read at all under the shipping
  `OPEN_LOOP` ruling, so neither arm can change a figure in this file —
  but neither was brought up, and this sentence is the honest form of
  that.
- **No repeatability set.** Each profile is one run. The two `straight`
  runs in §6 are the only pair, and they differ by design.
