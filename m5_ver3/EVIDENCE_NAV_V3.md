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

---

# F4 TASK 2 — THE PLANNER, THE CONTROLLER AND THE FIRST DRIVEN GOALS

**§14 – §15 are F4 Task 2.** Everything above is the COMMAND PATH with
no Nav2 in the room. This is Nav2 in the room: a planner, a controller,
two costmaps, a behaviour tree and one lifecycle manager over the stack
that already knew where it was — and a `navigate_to_pose` goal driven
down the line §1–§12 measured.

Everything below was measured on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, nav2 **1.3.12**, gz-sim 8.11.0, RTX 4050) on **2026-08-27**,
**headless**, on the **nominal plant** (`traction=nominal`), the
**default estimator arm** (`arm=wheel+imu`) and on the **shipping
localiser** (`loc=amcl@735cdbc6`). Every figure names the instrument
that produced it.

**The dry bar is what this task is accepted on** (F4 constraint 19), and
nothing here is a safety claim. `footprint_padding`, every inflation
radius and every tolerance in `nav2.yaml` are PROCESS values evaluated
in a costmap built over a network-carried scan. No safety scanner
appears in any costmap, by name or by topic — none of the three is
bridged to ROS at all. The collision monitor, which **this task does not
run**, "does not provide hard real-time safety certifications" and does
not replace a safety-rated PLC. It complements the F-PLC; it is not the
F-PLC.

---

## 14. THE NAV ARM

### 14.1 What `--nav` starts, and the one thing it refuses

Five more children, none of which exists without the flag:

| child | what it is |
|---|---|
| `planner_server` | `nav2_smac_planner::SmacPlannerHybrid`, `REEDS_SHEPP` |
| `controller_server` | `nav2_mppi_controller::MPPIController`, `motion_model: Ackermann` |
| `behavior_server` | one behaviour, `nav2_behaviors::Wait`, which does not move the vehicle |
| `bt_navigator` | on `behavior_trees/navigate_to_pose_tricycle_v3.xml` — no `Spin`, no `BackUp` |
| `nav_lifecycle_manager` | the ONLY nav2 lifecycle manager on this track, with its bond switched off |

**SIXTEEN children headless on the `--localize amcl --nav` stack**,
seventeen with a window — eleven of them F1–F4 Task 1's and five this
arm's. `status` names every one.

**`--nav` REQUIRES `--localize` AND IS REFUSED WITHOUT IT BY NAME**,
before the GPU preflight and before any child:

```
m5v3: REFUSED at check '--nav was given with a localiser'
      owned by: ./m5_ver3/m5v3.sh (the start flags)
      --nav puts a planner and a controller over a stack that
      does not know where it is. THIS IS NOT A PREFERENCE.
      The global costmap's frame is map, and
      Costmap2DROS::on_activate BLOCKS until it can transform
      map -> base_link. Without a
      localiser NOTHING publishes map -> odom at all, so that
      transition never returns:
      five children ALIVE for ever, one of them wedged in a
      lifecycle transition, and no log line that reads as an
      error.
      NOTHING WAS STARTED. Add a localiser:
        ./m5_ver3/m5v3.sh start --headless --localize --nav
        ./m5_ver3/m5v3.sh start --headless --localize slam --nav
```

**AND THE FIVE GO UP LAST, AFTER THE LOCALISER IS ACTIVE.** That is the
same refusal's mechanism used as an ordering rather than as a message:
`Costmap2DROS::on_activate` blocks in a `canTransform` loop until its
own `global_frame` → `robot_base_frame` resolves, and for
`global_costmap` that is `map` → `base_link`. `localize_lifecycle()`
runs at the end of `start()`, so the nav children are spawned after it
and `assert_children_alive` — which used to be a block inside `start()`
— is a function now, because the same question has to be asked twice.

### 14.2 The bringup gate, and the question nothing else can ask

`tools/nav_health.py` runs on every `--nav` bringup. Two checks, and the
second is the one five ALIVE processes cannot answer between them:

```
  nav:    6 lifecycle nodes ACTIVE - controller_server, planner_server,
          behavior_server, bt_navigator, local_costmap/local_costmap,
          global_costmap/global_costmap
  nav:    the planner PLANS. 2 m ahead of the seed, 29 poses in 0.0100 s
          map (-0.0793, -0.1458) -> (+1.9207, -0.1392), planner_id GridBased
          NOTHING WAS COMMANDED: compute_path_to_pose is the PLANNER's action
          and never reaches the controller. The truck did not move.
```

**SIX LIFECYCLE NODES BEHIND FOUR NAMES.** Each costmap is a lifecycle
node of its own inside its server, in a namespace of its own; a costmap
stalled in `configuring` leaves its parent reporting `active` and
`status` reporting ALIVE.

**AND THE PLAN IS THE POINT.** A `global_costmap` whose static layer
never received the frozen grid is wall-to-wall `NO_INFORMATION`, and
with `allow_unknown: false` the planner then refuses every goal — after
`max_planning_time`, once, into its own log. Every process up, every
log clean, and the first anybody would hear of it is a goal that times
out minutes into a measured run.

The gate commands no motion: `compute_path_to_pose` is the planner's
action and never reaches the controller.

### 14.3 The footprint, computed off the model and grown per axis

`evidence_core.sdf_footprint()` reads
`gazebo/forklift_ver3/model.sdf`, carries every `<collision>` and every
`<visual>` of every `<link>` through that link's pose and its own,
projects them onto z = 0 and hulls them. Eight vertices:

```
  [-1.875000,-0.340000]   the LEFT tine's tip and outer edge  (a VISUAL)
  [-0.680000,-0.558995]   safety_scanner_left's housing corner:
                          0.46 + 0.07*sqrt(2), a 0.14 m box at 45 deg
  [ 0.700000,-0.450000]   the chassis corner (1.40 x 0.90)
  [ 0.860000,-0.400000]   the counterweight corner (0.24 x 0.80 at 0.74)
  ... and the same four mirrored in +y
```

circumscribed **1.9056 m**, inscribed **0.5037 m**, 2.735 × 1.118 m.

**THE VISUALS COUNT.** Both tines, the two mast rails, the four
overhead-guard posts and the pallet camera's bracket are modelled as
visuals; a hull taken off the collisions alone is a footprint a metre
short at the fork end, and a footprint that is too SMALL looks exactly
like a correct one from every angle a costmap has.

**AND IT IS GROWN PER AXIS, WHICH IS §15.2's SECOND RUNG.** +0.54 m on
x (F3's worst absolute error, 0.5321 m) and +0.11 m on y (its worst
cross-track error, 0.1044 m), because
`EVIDENCE_LOCALIZATION_V3.md` §9 measured the two to be **five times
apart** and on this vehicle the body's x axis IS the direction of travel.
`footprint_padding` cannot express that — nav2's `padFootprint` moves
both axes by one number — so the POLYGON carries it and the padding is
**0.0**:

| | model hull | grown per axis | the same margin ISOTROPIC at 0.54 |
|---|---|---|---|
| x | [−1.8750, +0.8600] | [−2.4150, +1.4000] | [−2.4150, +1.4000] |
| y | ±0.5590 | **±0.6690** | ±1.0990 |
| circumscribed | 1.9056 | **2.4566** | 2.5703 |
| **inscribed** | 0.5037 | **0.6143** | **1.0439** |

The inscribed radius is the row that mattered: nav2 marks every cell
within it of an obstacle `INSCRIBED_INFLATED_OBSTACLE`, so an inflation
radius below it is a hard band with no slope in it at all. §15.2 rung 2
is what that cost.

`tests/test_nav2_params.py` recomputes the hull from the model, applies
the two margins and fails on a disagreement over a micrometre.

### 14.4 THE SCANNER SEES ITS OWN TRUCK, and the obstacle layer clears it

The local costmap's obstacle layer marks and clears from
`/forklift/gz/scan_nav`. The crib turned its own obstacle layer OFF over
exactly this and measured "9 of 360 rays at 1.334 m and 1.503 m". Here,
one scan off the running stack, truck at the spawn:

```
angle_min 0.7853982  angle_max 5.4977870  inc 0.0058178  n=811
returns under 2.0 m: 50 of 811
   23 rays  bearing +2.4493..+2.5773 rad (7.33 deg)  range 0.6004..0.6939 m
        mid ray lands at base_link (+0.026, -0.019)
   14 rays  bearing +2.6180..+2.6936 rad (4.33 deg)  range 1.4149..1.4990 m
        mid ray lands at base_link (-0.747, +0.285)
   13 rays  bearing +3.0311..+3.1009 rad (4.00 deg)  range 1.2485..1.3527 m
        mid ray lands at base_link (-0.746, -0.302)
```

Three pieces of this truck stand in the z = 1.80 m scan plane and the
ray count places each one to within 3 cm of where `model.sdf` puts it:
**nav_lidar_3d's housing** (r = 0.045 at base_link, z 1.76–1.84),
**mast_rail_left** (0.09 sq at (−0.78, +0.30), z 0.05–2.05) and
**mast_rail_right**. Bearing π in that frame is DEAD AHEAD OF TRAVEL, so
all three are in the forward quarter, 0.60–1.50 m out.

**WHAT MAKES THE LAYER HONEST IS `footprint_clearing_enabled`, AND IT IS
MEASURED RATHER THAN ARGUED.** All three land INSIDE the footprint
polygon, and nav2's obstacle layer paints its own footprint FREE on
every update before the layers are combined. One read of
`/local_costmap/costmap` with the truck standing at the spawn:

```
local costmap 200x200 at 0.050 m, origin (-4.950, -4.950) frame odom
  3D lidar housing     odom (+0.000, +0.000)  cost 0
  mast rail left       odom (-0.780, +0.300)  cost 0
  mast rail right      odom (-0.780, -0.300)  cost 0
  fork tip             odom (-1.875, +0.000)  cost 0
  counterweight        odom (+0.860, +0.000)  cost 0
  cells: lethal(100) 770, inscribed(99) 6047, unknown(-1) 0, free(0) 33183
```

The 770 lethal cells are the north wall, 4.00 m away and inside the
10 × 10 m rolling window. Not one of them is the vehicle.

**THE COVERAGE HOLE IS STATED AND NOT SOLVED.** A ray that STOPS on a
mast rail does not clear beyond it. The three obstructions subtend
7.33°, 4.33° and 4.00° — **15.66° of the aperture's 270°, 50 of 811
rays** — and a real obstacle in those three narrow sectors would be
neither marked nor cleared. The fix is a self-occlusion mask on the
scan, which is its own brief and its own measurement.

**AND IT CANNOT SEE WHAT MATTERS MOST.** At z = 1.80 m a pallet, a
dropped load and a person are all invisible. The sensor that could see
them is a safety scanner, and none of the three is bridged to ROS at
all. This layer's honest scope is STRUCTURE ABOVE 1.80 m that the frozen
map does not carry.

### 14.5 Every parameter, verified on the running node

**READ BACK, NOT TRUSTED.** `nav2.yaml` is `--params-file`d into four
servers, and rclcpp applies NOTHING from a block addressed to the wrong
node and says nothing about it. Worse, a parameter this build does not
DECLARE is ignored in silence — which is what `enforce_path_inversion`
would have been if Jazzy 1.3.12 had not carried it. On the shipping
stack (`nav=on@d430334b`):

```
FollowPath.enforce_path_inversion         Boolean value is: True
FollowPath.PathAngleCritic.mode           Integer value is: 2
FollowPath.CostCritic.consider_footprint  Boolean value is: True
FollowPath.motion_model                   String value is: Ackermann
FollowPath.AckermannConstraints.min_turning_r   Double value is: 1.25
FollowPath.vx_min                         Double value is: -0.3
FollowPath.vx_max                         Double value is: 0.3
FollowPath.wz_max                         Double value is: 0.24
FollowPath.model_dt                       Double value is: 0.05
FollowPath.batch_size                     Integer value is: 1000
general_goal_checker.plugin
                    String value is: nav2_controller::PositionGoalChecker
general_goal_checker.xy_goal_tolerance    Double value is: 0.6
controller_frequency                      Double value is: 20.0
enable_stamped_cmd_vel                    Boolean value is: False
odom_topic                    String value is: /m5v3/odometry/filtered
speed_limit_topic                         String value is: /speed_limit
GridBased.motion_model_for_search         String value is: REEDS_SHEPP
GridBased.minimum_turning_radius          Double value is: 1.25
GridBased.reverse_penalty                 Double value is: 1.0
GridBased.cost_penalty                    Double value is: 6.0
GridBased.allow_unknown                   Boolean value is: False
GridBased.tolerance                       Double value is: 0.1
/global_costmap  inflation_layer.inflation_radius      Double: 2.6
/global_costmap  inflation_layer.cost_scaling_factor   Double: 1.1
/global_costmap  footprint  [[-2.415000,-0.450000],[-1.220000,-0.668995],
                             [1.240000,-0.560000],[1.400000,-0.510000],
                             [1.400000,0.510000],[1.240000,0.560000],
                             [-1.220000,0.668995],[-2.415000,0.450000]]
/global_costmap  footprint_padding 0.0   robot_base_frame  base_link
/global_costmap  global_frame  map       static_layer.map_topic  /map
/local_costmap   global_frame  odom
/local_costmap   obstacle_layer.scan.topic  /forklift/gz/scan_nav
```

**FIVE THINGS THAT MATTER IN THAT LIST.** `enforce_path_inversion` IS
declared by this build and is on — it splits a Reeds-Shepp path at its
cusps and hands the optimiser one directional segment at a time.
`PathAngleCritic.mode` is 2 and not the shipped 0, which on a vehicle
whose ordinary leg is a nav2 REVERSE leg would have penalised every one
of them. `enable_stamped_cmd_vel` is FALSE on both sides of `/cmd_vel`,
which §6.1 fact 1 measured rather than read from a table. The goal
checker is the POSITION-ONLY one and it has no `yaw_goal_tolerance` to
read back, which is §15.2 rung 13. And the `odom_topic` the controller
closes on is the ESTIMATOR's, passed from `m5v3.sh` per arm, never the
ground truth (F2 constraint 13, F4 constraint 18).

### 14.6 THREE nav2 COMPLAINTS, AND THE SHIPPED FILE HAS NONE OF THEM

At the first three configurations this task tried, nav2 said three
things about the costmaps — twice at ERROR — and it was right all three
times:

```
[ERROR] [global_costmap]: The configured inflation radius (0.600) is
        smaller than the computed inscribed radius (1.044) of your
        footprint ...
[ERROR] [computeCircumscribedCost]: The inflation radius (0.600000) is
        smaller than the circumscribed radius (2.570336) If this is an
        SE2-collision checking plugin, it cannot use costmap potential
        field to speed up collision checking ... This may significantly
        slow down planning times!
[WARN]  [controller_server]: Inconsistent configuration in collision
        checking. Please verify the robot's shape settings in both the
        costmap and the cost critic.
```

The first said the inflation layer was a hard band with no slope in it.
The second said the planner was doing a full-footprint check on every
expansion. The third said the cost critic was scoring the CENTRE of a
truck whose front is 2.415 m away from it. §15.2's ladder is what each
of them cost.

**ON THE SHIPPED FILE, ALL FIVE NAV LOGS ARE CLEAN**, on a bringup taken
for this line:

```
--- planner_server              (nothing)
--- controller_server
[WARN]  [controller_server]: Parameter controller_server.verbose not found
--- bt_navigator               (nothing)
--- behavior_server            (nothing)
--- nav_lifecycle_manager      (nothing)
```

The one survivor is nav2 looking for a parameter of its own that this
file does not set, and it is recorded rather than silenced.

### 14.7 What the arm costs this rig

Measured over 30 s of wall clock on the `--localize amcl --nav` stack
(sixteen children), reading each node's own `/proc` — the NODE's and not
the `ros2 run` wrapper's, which is `EVIDENCE_FUSION.md` §10.4's
instrument:

| child | idle CPU, % of one core |
|---|---|
| `world` (gz server) | 88.35 % |
| `odom` | 29.36 % |
| `bridge` | 20.63 % |
| `ekf` | 13.80 % |
| **`controller_server`** | **11.66 %** |
| **`planner_server`** | **11.20 %** |
| **`bt_navigator`** | **8.60 %** |
| **`behavior_server`** | **7.77 %** |
| `amcl` | 5.67 % |
| **`nav_lifecycle_manager`** | **4.43 %** |
| `map_server` | 4.27 % |
| `smoother` | 4.17 % |
| `navcmd` | 0.87 % |
| **THE NAV ARM, TOTAL** | **43.66 %** |

**43.66 % OF ONE CORE WITH NOTHING TO DO**, against the localisation
arm's 9.94 % and the command path's 5.04 %. That is five idle event
loops and not MPPI: the optimiser does not run until a goal arrives, and
§15.4 reports the rate it held when one had.

RTF on that stack, idle, `tools/rtf_probe.sh`: **mean 0.9976, median
0.9999, floor 0.8535** over 295 samples in 30 s — against the
eleven-child localisation stack's 0.9984 / 0.9999 / 0.9284 (§10). The
median does not move; the floor does.

### 14.8 The refusals this task added, and how each was exercised

Every one lands **before the GPU preflight** and every one printed
"NOTHING WAS STARTED". Run with the stack down, `m5v3.sh status`
afterwards reading `not running (no pid file)`:

| # | what was broken | the check that said no |
|---|---|---|
| 1 | `--nav` with no `--localize` | `--nav was given with a localiser` |
| 2 | `local_costmap:` misspelt in `nav2.yaml` | `the nav parameter file is addressed to local_costmap` |
| 3 | `map_topic: /map_v2` against `config.yaml`'s `/map` | `nav2.yaml's map_topic is config.yaml's topics.map` |
| 4 | the behaviour tree moved away | `the behaviour tree exists` |

**NUMBER 2 IS THE ONE NOTHING ELSE COULD HAVE CAUGHT.** `local_costmap`
is a SUB-NODE: it has no process, `status` never names it and the sweep
never nominates it. On nav2's defaults it is a 3 × 3 m window with a
CIRCULAR footprint of radius 0.10 m — a fifth of this vehicle's
inscribed radius — and it would report every path through every rack as
clear.

**NUMBER 3 IS THE READ-BACK EARNING ITS KEEP.** The refusal quotes the
line and its number:

```
m5v3: REFUSED at check 'nav2.yaml's map_topic is .../config.yaml's topics.map'
      config.yaml says '/map' and these lines say something else:
      1230:        map_topic: /map_v2
      global_costmap's static layer subscribes there. Wrong, it
      waits for a latched message that has already been published
      and the costmap stays wall-to-wall NO_INFORMATION - which
      with allow_unknown: false refuses every goal.
```

### 14.9 Both arms, and the sweep

F4 constraint 20. Every arm this change can reach, brought up on the
committed tree, headless:

| arm | children | result |
|---|---|---|
| **`--localize amcl --nav`** | **16** | all ALIVE; `ekf` healthy; `velocity_smoother active`; navcmd gate passed; `map_server`/`amcl` active, `loc: healthy` (0.242 / ceiling 1); **six nav lifecycle nodes ACTIVE, 29 poses planned in 0.0080 s**; `nav=on@d430334b` |
| **`--localize amcl`, NO `--nav`** | **11** | all ALIVE; `ekf` healthy (0.22404 / 100); navcmd gate passed; `loc: healthy` (0.24219 / 1); **`nav=off`** |
| **`--localize slam`, NO `--nav`** | **10** | all ALIVE; `ekf` healthy (0.22488 / 100); navcmd gate passed; `loc: healthy`, covariance check correctly NOT run; `loc=slam@4bb88852`; **`nav=off`** |

**NOTHING REGRESSED ON THE ARMS THIS TASK DID NOT TOUCH.** The eleven-
and ten-child stacks are the ones F3 measured, with one line added to
their state file.

**AND `stop` FINDS ALL FIVE NEW CHILDREN, WRAPPER AND NODE.** `ros2 run`
forks, so each is two processes and the pidfile knows about one. From
the `--nav` stack:

```
  swept 91451 (planner_server)          <- the `ros2 run` wrapper
  swept 91462 (planner_server)          <- the node itself
  swept 91459 (controller_server)
  swept 91487 (controller_server)
  swept 91484 (behavior_server)
  swept 91512 (behavior_server)
  swept 91509 (bt_navigator)
  swept 91532 (bt_navigator)
  swept 91529 (nav2_lifecycle_manager)
  swept 91548 (nav2_lifecycle_manager)
  ...
  survivors: 0
```

`tests/test_sweep_patterns.py` **parses `m5v3.sh` itself** for all five
new spawns and requires a pattern for each; a second test requires every
one of them to sit inside a condition naming the `NAV` arm, which is
AMR-LES-023's own lesson applied to a SPAWN rather than to a check —
and F4 Task 2 is the first phase where getting it wrong would START a
process rather than refuse one. A stale `controller_server` on domain 97
does not merely publish: it publishes a TWIST, and the command path
takes it.


---

## 15. THE FIRST DRIVEN GOALS

> **THREE OF THIS SECTION'S CONCLUSIONS ARE SUPERSEDED BY §16 AND ARE
> MARKED WHERE THEY SIT.** Every MEASUREMENT below stands exactly as F4
> Task 2 took it — they are measurements of a different `nav2.yaml` and
> §16 does not re-run them. What §16 changes is what three of them were
> read to MEAN: §15.4's reading of the deviation figure, §15.7 item 1's
> "it is not the controller", and §15.7 item 5 / §15.9 item 7's jump
> budget. Nothing here has been edited except to add those pointers.


### 15.0 The answer, before the working

| | |
|---|---|
| **the arm comes up and PLANS** | six lifecycle nodes ACTIVE, 29 poses in 0.010–0.014 s, on every bringup |
| **the controller HOLDS ITS RATE** | 20.017 Hz mean, 20.000 median, over 1182 commands of a 59 s drive — against `controller_frequency: 20.0` |
| **the controller TRACKS ITS PLAN** | deviation from the plan standing at the time: **mean 0.040–0.113 m, max 0.182–0.414 m** over five runs and 21 500 commands |
| **the RTF survives the whole stack** | **0.9963 – 0.9998** measured over the drives themselves, sixteen children up |
| **the command path is untouched** | worst steer step **0.100000 rad/tick** on every run — F4 Task 1's 2.0 rad/s ramp, exactly, never above it |
| **THE ARRIVAL IS NOT REPEATABLE, AND THAT IS THE PHASE'S HEADLINE** | the headline goal, three times: **SUCCESS, ABORT, CANCELLED**. `ring_corner` and `aisle_end`: ABORT |
| **the one arrival, scored absolutely** | truth **0.5348 m** from the goal, believed **0.5411 m**, the two **0.0141 m** apart |
| **AND IT TURNED ON 0.0078 m** | its CLOSEST APPROACH in the pose the checker sees was **0.5922 m** against a **0.60 m** box; the run that aborted came within 0.9918 m. §15.3b |
| **the jumps went OVER the budget** | worst single `map` → `odom` step **0.6490 m** against the **0.2591 m** §13.10 handed over — 2.5× |
| **and the largest single finding** | a FREESPACE planner does not reproduce the road graph, and eight aborted goals are the measurement of it |

**THIS SECTION IS MOSTLY A LADDER OF FAILURES AND IT IS KEPT WHOLE.**
Thirteen goals were driven for this task and three of them arrived. Each
failure named a different thing, every named thing became a derivation
in `nav2.yaml`, and the ones that are still open are named as open. A
wrong turn that has been measured is worth more than one that has been
tidied away (`EVIDENCE_FUSION.md` §4's rule).

### 15.1 The three goals, and where they came from

`config.yaml`'s `nav.goals:`. Every one is a NODE of `m6/ipc/route.py`'s
road graph — read-only to this track, copied here as values, and
`tests/test_nav2_params.py` rebuilds the graph and asserts each pose is
in it, so the copy says when it has gone stale.

| goal | world | travel heading | route | repeat |
|---|---|---|---|---|
| `spine_north` | (0.00, +10.00) | +0.0000 (EAST) | 17 m straight down the ring's north leg | **×3** |
| `ring_corner` | (+20.00, +10.00) | +0.0000 (EAST) | 37 m of the same leg | ×1 |
| `aisle_end` | (+20.00, 0.00) | −1.5708 (SOUTH) | 47 m: the north leg, the NE corner, the east leg | ×1 |

**THE HEADING IS WRITTEN AS A TRAVEL HEADING AND NOT AS A POSE YAW, AND
THAT IS THE ONE PLACE THE TABLE COULD SILENTLY LIE.** This vehicle's
forks are at model −x, so the direction it TRAVELS is `yaw + π`. A table
of pose yaws would have every entry a half turn from the direction a
reader pictures, and an entry written the obvious way would arrive
COUNTERWEIGHT-FIRST, with the nav lidar's 90° blind sector leading, and
would still report SUCCESS. `drive_goal.pose_yaw()` is the one function
that adds the π and `tests/test_drive_goal.py` locks it four ways.

**AND THE FIRST CUT OF THE TABLE DID EXACTLY THAT.** `vehicle.spawn.yaw`
is π, so the counterweight points west and the FORKS POINT EAST: from
the spawn, forks-first travel is EASTWARD, which is what
`EVIDENCE_MAP_V3.md` §2.2's first leg ("ring N east") has said all
along. The first three goals were all put WEST and SOUTH of the spawn —
every one of them behind the forks. §15.2 rung 1 is what that measured.

### 15.2 THE LADDER — thirteen goals, and what each rung moved

`nav` is the `nav=on@<md5>` label `m5v3.sh` writes off `nav2.yaml` at the
moment of the bringup. **Every rung below is a different `nav2.yaml`,
and `analyse` refuses to table two of them together** — which it did,
five ways, when this task ran it over the whole set:

```
drive_goal: REFUSED at check 'every session in this analyse is off the SAME stack'
            5 different traction/arm/loc/nav combinations are in this set:
              nominal  wheel+imu  amcl@735cdbc6  on@1a7e99f1 - 2 session(s)
              nominal  wheel+imu  amcl@735cdbc6  on@b570a292 - 1 session(s)
              nominal  wheel+imu  amcl@735cdbc6  on@502a93f5 - 1 session(s)
              nominal  wheel+imu  amcl@735cdbc6  on@9ed03df7 - 4 session(s)
              nominal  wheel+imu  amcl@735cdbc6  on@5cc02ba3 - 2 session(s)
```

| # | `nav2.yaml` | goal | result | driven | what it measured, and what moved |
|---|---|---|---|---|---|
| 1 | `1a7e99f1` | `aisle_end` (−20, 0) | ABORT 205 | 5.23 m | **the goal table was a half turn out.** All three goals were behind the forks; the planner solved this one COUNTERWEIGHT-FIRST (361 of 361 commands positive) at the creep cap. And the analyser compared a MAP-frame plan against WORLD-frame truth and read 20 m of "deviation" for a vehicle tracking to 0.065 m. → the table, and `plans_of()` takes the registration |
| 2 | `1a7e99f1` | `spine_cross` (0, 0) | ABORT 205 | 7.30 m | **the margin was the wrong SHAPE.** Tracking mean 0.100 m / max 0.376 m, and the ISOTROPIC 0.54 m padding put the polygon over RackNW2's corner. Its inscribed radius was 1.0439 m — above the inflation, so the layer was a hard band with no slope. → the polygon carries the margin per axis (+0.54 x, +0.11 y), padding 0.0, `consider_footprint: true` |
| 3 | `b570a292` | `spine_cross` | ABORT 205 | 8.11 m | inflation at 1.00 m still left a 3.00 m uninflated strip down a 5.00 m rack gap → 2.00 m |
| 4 | `502a93f5` | `spine_cross` | ABORT 104 | 12.01 m | **MPPI reported every one of 1000 sampled trajectories in collision** inside that gap: `Optimizer fail to compute path`, then `Controller patience exceeded`, and the control loop at **4.76 Hz**. → inflation 2.60 m, `cost_scaling_factor` 3.0 → 1.10, `cost_penalty` 2.0 → 6.0 |
| 5 | `9ed03df7` | `spine_cross` | ABORT 205 | 27.26 m | **a freespace planner is not a road graph.** It threaded the gap anyway, drove past the goal and looped to the south ring leg. → the GOALS moved to where the two routes agree |
| 6 | `9ed03df7` | `spine_north` | **SUCCESS** | 17.51 m | truth error 0.4787 m, believed 0.3355 m; deviation mean 0.109 / max 0.685 m |
| 7 | `9ed03df7` | `spine_north` | **SUCCESS** | 17.64 m | truth error 0.6073 m, believed 0.4457 m; deviation mean 0.097 / max 0.552 m |
| 8 | `9ed03df7` | `spine_north` | ABORT 205 | — | **two of three is not a repeatability claim.** → `GoalCritic`/`PathFollowCritic` 1.4 → 2.50 m |
| 9 | `5cc02ba3` | `spine_north` | ABORT 205 | — | **worse.** `PathFollowCritic`'s threshold is the range inside which path-following STOPS; 2.50 m takes it away for most of an approach |
| 10 | `5cc02ba3` | `spine_north` | CANCELLED | — | worse again → reverted to 1.4 |
| 11 | `16963750` | `spine_north` | CANCELLED | 21 m east | **the box was smaller than the error the pose carries WHILE MOVING.** Closest approach **0.5304 m** of truth and **0.5508 m** of belief against a 0.25 m box (`…120921`, the instrument's own figure — §15.3b); the checker never latched and MPPI did not turn the vehicle round — it drove 260 s into the far wall. → the transit ceiling to 0.300 m/s (a speed the truck can stop out of), then the box to 0.60 m |
| 12 | `8712475c` | `spine_north` | ABORT 205 | — | reached the goal POSITION to **0.1520 m** of truth (0.1640 m of belief) and could not finish: heading 1.82 rad out |
| 13 | `8712475c` | `spine_north` | CANCELLED | — | reached it to **0.0101 m** of truth (0.0409 m of belief) and could not finish: heading 1.11 rad out. → `nav2_controller::PositionGoalChecker` |

Rungs 12 and 13 are the crib's own finding, reproduced independently:
`agv/forklift/nav2.yaml` carries a `staging_goal_checker` because
`EVIDENCE_NAV2.md` §8.3 measured the `(xy, yaw)` pair to be **jointly
unreachable in an endgame correction** on this kinematic machine —
heading costs 2.1–2.6 m of travel per radian. That is a fact about a
tricycle rather than about a floor, and it transfers.

### 15.3 THE SHIPPED SET — five runs, one `nav2.yaml`, `nav=on@d430334b`

Stack stopped and started before every one; `traction=nominal`,
`arm=wheel+imu`, `loc=amcl@735cdbc6`, headless.

| session | goal | result | sim time | driven | arrival (TRUTH) | arrival (BELIEVED) | truth − believed |
|---|---|---|---|---|---|---|---|
| `…130956` | `spine_north` | **SUCCESS** | 59.06 s | 17.295 m | **0.5348 m**, +1.6920 rad | 0.5411 m | **0.0141 m** |
| `…131222` | `spine_north` | ABORT 205 | 130.5 s | 23.759 m | 6.6691 m | 6.7128 m | 0.0461 m |
| `…131600` | `spine_north` | CANCELLED | 479.5 s | **130.199 m** | 14.2651 m | 14.2706 m | 0.0768 m |
| `…132535` | `ring_corner` | ABORT 205 | 212.8 s | 37.050 m | 12.7769 m | 12.7613 m | 0.0304 m |
| `…133039` | `aisle_end` | ABORT 205 | 222.7 s | 26.563 m | 40.2602 m | 40.2198 m | 0.0768 m |

**ONE ARRIVAL IN FIVE, AND THE HEADLINE GOAL IS ONE IN THREE.** The
`repeat: 3` this table was asked for was recorded; what it repeats is
not an arrival.

**THE ONE ARRIVAL, SCORED THE WAY F3 SCORES ANYTHING.** Ground truth
against the goal in the BUILDING's frame, and beside it the pose the
stack BELIEVED — `map` → `base_link` off `/tf`, composed on the
estimator's timeline and carried into the building by the committed
registration, nothing anchored. The goal checker only ever saw the
second one.

  truth 0.5348 m, believed 0.5411 m, and **the two are 0.0141 m apart** —
  which is under `registration.yaml`'s own instrument floor
  (rms 0.0291 m). At the moment of arrival the localiser was as good as
  the ruler. **The 0.53 m is the CONTROLLER and not the localiser.**

**AND THE HEADING WAS 1.6920 rad OUT.** The position-only checker
allowed it, deliberately (§14's `general_goal_checker`), and
`drive_goal.py` prints it because nothing else would. An approach pose
on this stack today delivers a POSITION and not a heading.

### 15.3b THE CLOSEST APPROACH — the row the goal box is about

**THE ARRIVAL TABLE SCORES WHERE THE TRUCK STOPPED, WHICH ON A RUN THAT
DID NOT ARRIVE IS WHEREVER THE CONTROLLER GAVE UP.** 6.7 m past the goal
on one of these and 40 m on another. That says the run failed and says
nothing about why. `drive_goal.py analyse` therefore also scans the
ground truth between the goal being SENT and the result for the row
NEAREST the goal, and reports the signed components there — in the
building's frame, and projected onto the GOAL's own travel heading,
which is the only frame in which "cross-track" means anything at a
goal. `across` is positive to the LEFT of that heading.

**AND IT SCANS THE BELIEVED POSE THE SAME WAY, because the box is
evaluated on `map` → `base_link` and never on the truth.** Printing only
one of the two would make the other look like an instrument error.

| session | result | TRUTH closest | ALONG | ACROSS | BELIEVED closest | box |
|---|---|---|---|---|---|---|
| `…130956` | **SUCCESS** | 0.7314 m | −0.5064 | −0.5277 | **0.5922 m** | 0.60 m |
| `…131222` | ABORT 205 | 0.9683 m | +0.1295 | **−0.9596** | 0.9918 m | 0.60 m |
| `…131600` | CANCELLED | 9.6556 m | −9.6556 | −0.0129 | — | 0.60 m |
| `…132535` `ring_corner` | ABORT 205 | 12.7456 m | −9.6311 | −8.3481 | — | 0.60 m |
| `…133039` `aisle_end` | ABORT 205 | 31.5844 m | −3.2042 | −31.4214 | — | 0.60 m |

**THE ONE ARRIVAL IN THIS TASK TURNED ON 0.0078 m.** `…130956` came
within **0.5922 m** of the goal in the pose the checker sees, against a
**0.60 m** box — eight millimetres of margin — and its ground truth
never came inside the box at all (0.7314 m). `…131222` missed by
0.3918 m on the same reading and was sent round a Reeds-Shepp loop it
did not come back from. **That is what "one in three" is made of**: not
two different behaviours, but one behaviour either side of a hair.

**AND THE TRUTH AND THE BELIEF AGREE AT THAT MOMENT.** 0.1401 m apart on
`…130956` and 0.0238 m on `…131222`, against a registration floor of
rms 0.0291 m / MAX 0.1179 m. The gap between the truck and the box is
the CONTROLLER's, not the localiser's.

**THE TWO RUNS THAT REACHED THE GOAL AND COULD NOT FINISH** — §15.2
rungs 12 and 13, on `nav=on@8712475c`, which `analyse` will not table
beside the rows above:

| session | TRUTH closest | ALONG | ACROSS | BELIEVED closest | heading there |
|---|---|---|---|---|---|
| `…123524` | **0.1520 m** | +0.1516 | −0.0112 | 0.1640 m | −1.3185 rad, 1.82 rad out |
| `…124352` | **0.0101 m** | +0.0095 | −0.0033 | 0.0409 m | −2.0335 rad, 1.11 rad out |

Both are a hand's width from the goal in POSITION and neither could
finish, because the checker in force then demanded the heading too.
That is the pair that produced §14's `PositionGoalChecker` ruling.

### 15.4 What the controller did, and it is not what failed

| | `…130956` | `…131222` | `…131600` | `…132535` | `…133039` |
|---|---|---|---|---|---|
| `/cmd_vel` messages | 1182 | 2620 | 9599 | 4162 | 4462 |
| rate, mean / median | 20.017 / 20.000 | 20.070 / 20.000 | 20.017 / 20.000 | 19.559 / 20.000 | 20.034 / 20.000 |
| worst tick | 0.058 s | 0.052 s | 0.210 s | **5.090 s** | 0.064 s |
| RTF over the drive | 0.9998 | 0.9963 | 0.9988 | 0.9968 | 0.9982 |
| **deviation from plan, mean** | **0.0445 m** | **0.0427 m** | 0.1131 m | 0.0402 m | 0.1125 m |
| deviation, max | 0.1816 m | 0.2320 m | 0.3803 m | 0.2445 m | 0.4143 m |
| steer travel | 20.06 rad | 48.68 rad | 164.57 rad | 82.34 rad | 142.87 rad |
| worst steer step | **0.100000** | **0.100000** | **0.100000** | **0.100000** | **0.100000** |
| cusps (direction changes) | 0 | 0 | 1 | **16** | 2 |

> **SUPERSEDED READING — §16.1a.** The rate figure stands. "HELD ITS
> PATH" does not: the tree replans at 1 Hz **from the vehicle's own
> pose**, so every plan starts underneath the truck and a controller
> that never turns at all is never more than one cycle's drift from its
> path. 0.043 m is what one second of a 0.024 m/s lateral drift looks
> like. The deviation figure is small here **because the plan keeps
> moving to where the truck is**, and the same runs' curvature-following
> gain — the figure that does not have this problem — is 0.049, −0.011
> and −0.052. The paragraph below is left as written.

**THE CONTROLLER HELD ITS RATE AND HELD ITS PATH.** 20.0 Hz median on
every run, and a deviation from the plan standing at the time of
**0.040–0.113 m mean** over 21 500 commanded twists. nav2 issue #5714
says Ackermann robots deviate from the global path in turns, worst in
REVERSE turns, and on this vehicle **every ordinary leg is a nav2
reverse leg** — 100 % of the commands on three of the five runs.
**THIS STACK DOES NOT REPRODUCE #5714 AT THIS ENVELOPE** — and there IS
a measurement of the other envelope, because the ladder left one on
disk. `…120921` is §15.2 rung 11, driven at the 0.700 m/s ceiling on the
same goal and the same plan shape, and the instrument reports its
deviation from the plan standing at the time as **mean 0.3140 m, median
0.3460 m, max 0.9384 m** over 5986 samples:

| envelope | deviation, mean | median | max |
|---|---|---|---|
| **0.700 m/s** (`…120921`, `nav=on@16963750`) | **0.3140 m** | 0.3460 m | **0.9384 m** |
| 0.300 m/s (the five shipped runs) | 0.040 – 0.113 m | 0.035 – 0.089 m | 0.182 – 0.414 m |

> **SUPERSEDED READING — §16.1a.** Both envelopes carry the identical
> defect (`PathAlignCritic` never scored on either), and the reason the
> figure is 7× larger at 0.700 m/s is that the vehicle covers 2.33× the
> ground between replans, so the same uncorrected heading error shows up
> as more distance from a path that is re-anchored at the same rate. It
> is a measurement of the REPLAN RATE against the speed, not of the
> controller's tracking, and it is not a #5714 datum in either
> direction.

**SEVEN TIMES THE MEAN AND TWICE THE WORST, FOR 2.3× THE SPEED.** That is
not a #5714 measurement on its own - the two are different `nav2.yaml`s
and `analyse` refuses to table them together, which is why they are two
rows here and not one table - but it is the first figure on this track
that says the tracking error is strongly speed-dependent, and it is
where a diagnosis of #5714 on this vehicle should start.

**THE WORST STEER STEP IS THE RAMP, EXACTLY, ON EVERY RUN.**
0.100000 rad per tick is F4 Task 1's 2.0 rad/s at 0.05 s
(`EVIDENCE_NAV_V3.md` §5). The command path below the controller is
unchanged and still enforces every limit it enforced with a table
driving it.

**ONE TICK IN 4162 TOOK 5.09 SECONDS**, on `ring_corner`, and it is
recorded rather than explained: the controller's own log carries no
error at that moment and the RTF over the same drive was 0.9968. It is
the only tick over 0.21 s in 21 500.

### 15.5 What the planner did, and it is what failed

| | `…130956` | `…131222` | `…131600` | `…132535` | `…133039` |
|---|---|---|---|---|---|
| plans published | 58 | 127 | **459** | 138 | 95 |
| first plan | 170 poses, 16.989 m | 170, 17.000 m | 170, 16.960 m | 358, **37.338 m** | 434, **45.709 m** |
| first plan direction | 0 fwd / 169 **REV** | 0 / 169 | 0 / 169 | 0 / 357 | 0 / 433 |
| last plan direction | 7 / 19 | **75 fwd** / 0 | 2 / 147 | **187 fwd** / 4 | **444 fwd** / 26 |

**EVERY FIRST PLAN IS FORKS-FIRST AND SOME LAST PLANS ARE NOT.** The
planner opens with the route a reader would draw — the ring leg, driven
the way the truck faces — and after the vehicle has overshot or been
turned round it solves the new problem counterweight-first. That is
correct Reeds-Shepp behaviour and it is also how a missed goal becomes
a 130 m drive: `…131600` published **459 plans in 479 s** and drove
**130.199 m** to cover a straight-line 2.910 m.

**AND `aisle_end`'s FIRST PLAN IS 45.709 m, WHICH IS THE ROAD GRAPH's
OWN ROUTE.** The graph's route for that goal is about 47 m — the north
leg, the north-east corner, the east leg — and the freespace shortcut
across the rack block is 38 m. At the shipped inflation the planner took
the long way. **That is §15.2 rung 5's fix working**, and it is the one
place in this task where the costmap successfully told a freespace
planner about a road graph.

### 15.6 The jumps, and what the controller did about them

`evidence_core.tf_jumps()` counts CORRECTIONS and not re-broadcasts:
nav2_amcl re-sends `map` → `odom` on every scan whether or not the
filter updated, so counting broadcasts would report a 15 Hz correction
rate and a mean jump of zero.

| session | corrections / broadcasts | per s | worst step | worst heading step |
|---|---|---|---|---|
| `…130956` | 66 / 1017 over 67.1 s | 0.98 | 0.2071 m | 0.0135 rad |
| `…131222` | 93 / 2100 over 138.5 s | 0.67 | 0.1561 m | 0.0088 rad |
| `…131600` | 473 / 7388 over 487.5 s | 0.97 | 0.1123 m | 0.0215 rad |
| `…132535` | 138 / 3345 over 220.7 s | 0.63 | **0.6490 m** | 0.0234 rad |
| `…133039` | 95 / 3504 over 231.2 s | 0.41 | 0.0630 m | 0.0087 rad |
| **§13.10's budget** | | | **0.2591 m** | **0.0764 rad** |

**THE HEADING STEPS STAYED WELL INSIDE THE BUDGET AND THE POSITION STEPS
DID NOT.** `ring_corner`'s worst single `map` → `odom` correction was
**0.6490 m — 2.5× the peak F3 handed over**, on the same arm, the same
map and the same plant. F3 measured its peaks with `drive_route.py`
driving a table; this is the same localiser with a CONTROLLER CLOSING A
LOOP ON IT, and the loop feeds the localiser a different motion history.
**The budget §13.10 handed over is not conservative once the loop is
closed**, and that is the answer to the question the contract asked.

**AND WHAT THE CONTROLLER DID ABOUT THEM IS BOUNDED.** The window is
`nav.analyse.jump_response_s` = 1.0 s, which is 20 controller ticks and
15 scan periods:

| session | jumps with a response | largest response | worst `w` swing after any jump |
|---|---|---|---|
| `…130956` | 64 of 66 | a 0.0142 m step moved `v` by 0.3003 m/s and `w` by 0.1929 rad/s | 0.1929 rad/s |
| `…131222` | 93 of 93 | a 0.0373 m step moved `v` by 0.0905 m/s and `w` by 0.0029 rad/s | 0.0653 rad/s |
| `…131600` | 473 of 473 | a 0.0233 m step moved `v` by 0.2714 m/s and `w` by 0.2091 rad/s | 0.2091 rad/s |

**THE RESPONSE IS A RANGE AND NOT A DIFFERENCE OF ENDPOINTS**, because a
controller that swings and comes back inside the window would show
nothing in a first-to-last subtraction — and a swing is exactly what a
jump is expected to produce. The worst yaw-rate swing measured after any
correction is **0.2091 rad/s**, which is 87 % of `wz_max` (0.240) — so a
jump CAN saturate this controller's angular envelope. It did not
destabilise it: the deviation from the plan over those same runs is the
table in §15.4.

**AND THE LARGEST `v` SWING IS THE WHOLE ENVELOPE.** 0.3003 m/s after a
0.0142 m step, on the run that arrived. That is not the jump — it is the
GoalCritic pulling the speed down 1.4 m from the goal, and the window
happened to contain it. A jump-response figure taken near a goal is a
figure about the arrival.

### 15.7 What is still open, named

1. **THE ARRIVAL.** One in five, one in three on the headline. The
   measured causes, in the order they were seen: the box is smaller than
   the error the pose carries while moving (fixed, §15.2 rung 11); the
   `(xy, yaw)` pair is jointly unreachable (fixed, rung 13); and a
   CLOSED-LOOP MISS DISTANCE AT THE GOAL that is NOT fixed and is the
   whole of what is left.
     **EVERY FIGURE HERE IS §15.3b's, PRINTED BY
     `drive_goal.py analyse`.** On the shipped `nav2.yaml`
     (`nav=on@d430334b`) the three `spine_north` runs came within
     **0.5922 m, 0.9918 m and (never — 9.66 m) of the goal in the pose
     the checker sees**, against a 0.60 m box: one inside by 0.0078 m,
     one outside by 0.3918 m, one that never approached at all. The
     component that misses is ACROSS the goal's own travel heading:
     **−0.5277 m and −0.9596 m** on the two that got there, both to the
     RIGHT of the arrival heading.
     **AND IT IS NOT THE TRACKING AND NOT THE LOCALISER.**
     > **SUPERSEDED — §16.2. IT WAS THE CONTROLLER.** "Not the
     > localiser" stands and §16.1(b) strengthens it. "Not the tracking"
     > does not: `PathAlignCritic`, the only critic that penalises
     > deviation ALONG the path, never scored on any tick of any run
     > here, and the entire lateral miss is the integral of the
     > uncorrected heading error that left (94.8 % and 103.2 % of it).
     > The deviation figure quoted below cannot see it, for §16.1a's
     > reason. The paragraph is left as written.

     `…131222`
     followed the plan standing at the time to a mean of **0.0427 m**
     and its truth and belief were **0.0238 m** apart at the closest
     row — under the registration's own rms floor. The vehicle went
     where the plan said and the plan did not go through the goal.
     **THE SAME MEASUREMENT ON THE PREVIOUS CONFIGURATION IS WORSE AND
     IS ALSO ON DISK.** `…120921` (`nav=on@16963750`, 0.700 m/s) came
     within 0.5304 m of truth and 0.5508 m of belief — outside the
     0.25 m box standing then by a factor of two — with a plan
     deviation of mean 0.3140 m. `analyse` refuses to table it beside
     the rows above and this paragraph does not either; it is quoted
     as a separate configuration.
     **ONE FIGURE THIS FILE PREVIOUSLY QUOTED IS WITHDRAWN.** An
     earlier draft cited a closest approach of 0.3398 m from session
     `goal-spine_north-20260827-122050`. That session was deleted
     during the task and the figure was hand-derived from a scan this
     tool did not then carry, so it cannot be re-read. The instrumented
     figure for the same configuration is `…120921`'s 0.5304 m above,
     and it is the one that stands.
2. **WHAT HAPPENS AFTER A MISS.** Nav2 does not stop. The tree replans,
   the planner solves the new problem, and a vehicle 6 m past its goal
   drives 130 m and 459 plans trying to come back. A goal that cannot be
   reached should fail FAST, and nothing in this configuration makes it.
3. **THE FREESPACE PLANNER AND THE ROAD GRAPH.** Moved, not removed
   (§15.2 rung 5, §15.5). The answer is nav2's Route Server
   (`docs/reports/m5v3-02` §4), which is edge-constrained and maps onto
   `m6/ipc/route.py`'s graph one edge for one edge. It is a whole server
   and it belongs to a later phase.
4. **THE 5.09 s CONTROL TICK**, once in 21 500.
5. **THE 0.6490 m JUMP.** §13.10's budget is not conservative under a
   closed loop.
     **SUPERSEDED — §16.8 and `EVIDENCE_LOCALIZATION_V3.md` §13.10a.**
     The finding is right and the number is low: over the whole
     driven-goal corpus the worst single closed-loop step is
     **0.8310 m**, on a run that ARRIVED down the longest route in the
     goal table. The heading half of the contract held.

### 15.8 What this task did NOT do

- **No collision monitor**, and therefore no polygon, no slowdown and no
  stop action. F4 Task 3 owns it, and §14.4's coverage hole is one of
  the things it is for.
- **No wet set.** Every figure here is `traction=nominal`. The stopping
  distance the whole envelope is derived from is a dry figure and the
  slippery plant's is not measured.
- **No `--rf2o` or `--fuse` arm, and no `--localize slam` GOAL.** The
  nav children read the estimator arm only as an address
  (`odom_topic`), and the localiser only through `/tf`, so neither arm
  can change a figure here — but neither was DRIVEN, and this sentence
  is the honest form of that. F4 Task 3's flip experiment is the slam
  arm's.
- **No mid-path goal update, no station-class approach and no
  deliberate reverse-out segment.** Those are Task 3's driving cases.
- **No docking claim of any kind.** The goals are road-graph nodes in
  open corridors; the 0.25 m tolerance is the station CLASS and not a
  station, and §15.3's arrival errors are what an approach pose costs
  today.
- **No `nav2_route`.** §15.2's largest finding names it as the answer
  and this task did not run it.

### 15.9 What F4 Task 3 inherits

1. **THE ARRIVAL IS THE OPEN PROBLEM AND IT IS NOT THE CONTROLLER'S
   TRACKING.**
     > **SUPERSEDED — §16. IT WAS THE CONTROLLER, AND THE ARRIVAL IS NO
     > LONGER OPEN.** `PathAlignCritic` never scored; the fix is four
     > parameters; the set is 5 of 5. This item is left whole because
     > the reasoning that produced it — "the deviation is small, so the
     > tracking is fine" — is the exact trap §16.1a is about, and a
     > later task is better served by seeing it than by not.

   One goal in five arrived; the controller held 20.0 Hz and
   0.040–0.113 m of deviation on every run. §15.7 lists the three
   measured causes and which two are fixed. A driving case that assumes
   a goal completes has to read that list first.
     **AND §15.3b IS THE ROW TO START FROM.** `drive_goal.py analyse`
     prints, for every session, the CLOSEST the vehicle came to the goal
     between the goal being sent and the result — in truth AND in the
     pose the checker sees — with the miss split ALONG and ACROSS the
     goal's own travel heading. On the shipped runs that is 0.5922 m
     (arrived, by 0.0078 m) and 0.9918 m (did not), with the ACROSS
     component carrying −0.53 m and −0.96 m of it. Nothing has to be
     re-driven to read those: the sessions are on disk and the scan runs
     with no ROS.
2. **The envelope is CREEP in both directions, 0.300 m/s**, from §8's
   own stop table against the goal box. A case that wants transit speed
   back has to say what it does about the arrival.
3. **The goal checker holds a POSITION and no heading**, and §15.2 rungs
   12–13 are why. An arrival heading is F5's, through the docking
   server's straight final leg.
     **RE-EXAMINED AND CONFIRMED ON BETTER EVIDENCE — §16.6.** Both
     rungs were driven by the controller §16 fixes, so the ruling was
     right with a confound in it. Asked again with the pair actually
     configured, the position half is reachable to **0.0062 m of
     belief** and the heading at that moment is **0.324 rad** out;
     §16.6's corridor table is the curve, and it says the straight
     final leg has to be about **1.5 m**.
4. **A freespace planner is not the road graph, measured.** §15.2's
   ladder and §15.5. Any case whose route crosses the rack block is a
   case about that finding rather than about the controller.
5. **The `nav=on@<md5>` label is live and `analyse` refuses across it.**
   Five different `nav2.yaml`s were refused into one table during this
   task; a case set that retunes anything has to re-record.
6. **`consider_footprint: true` on the CostCritic**, and the 43.66 % of
   a core the arm costs idle. A case that adds critics starts there.
7. **THE JUMP BUDGET DID NOT SURVIVE CONTACT.**
     > **SUPERSEDED — §16.8. Size it on 0.85 m, not 0.65 m.** §15.6's
     > 0.6490 m was the worst in F4 Task 2's own five runs; over the
     > whole corpus it is **0.8310 m**.

   §15.6: the worst single
   `map` → `odom` correction under a closed loop was **0.6490 m**
   against the **0.2591 m** `EVIDENCE_LOCALIZATION_V3.md` §13.10 handed
   over. The heading steps stayed well inside. A phase that sizes
   anything on that contract should size it on 0.65 m.


---

# F4 TASK 2.5 — WHY THE TRUCK MISSED

**§16 is F4 Task 2.5.** §15 measured one arrival in five and named the
miss as open. This is the diagnosis, the mechanism, the fix, the
fail-fast and the re-measured set. Same rig, same day (2026-08-27),
**headless**, `traction=nominal`, `arm=wheel+imu`, `loc=amcl@735cdbc6`,
dry. Every figure names the instrument that produced it and every
rejected hypothesis is here with the measurement that killed it.

Nothing here is a safety claim. No collision monitor is run, no safety
scanner is bridged, and every tolerance below is a PROCESS value.

## 16. THE DIAGNOSIS

### 16.0 The answer, before the working

| | |
|---|---|
| **THE MECHANISM** | `PathAlignCritic` — the heaviest critic in `nav2.yaml` at `cost_weight: 14.0`, and the only one that penalises deviation ALONG the path — **never scored once on any control tick of any run in §15** |
| why | it returns early unless `furthest_reached_path_point >= offset_from_furthest`. That index is the PREDICTION HORIZON measured in path points, the gate was 20, and the horizon reached **2–8 at the median and 12 at its very best** |
| how many plans could ever have cleared it | **0 of 1000** on the five shipped runs; 10 of 274 on the 0.700 m/s configuration §15.2 rung 11 withdrew. `drive_goal.align_gate_scan()` |
| **the provenance, and it is the whole lesson** | rung 11 lowered the transit ceiling 0.700 → 0.300 m/s, correctly, on the stop table. `time_steps: 56` was a COUNT. The horizon is a DISTANCE: it went from 1.96 m to **0.84 m**, under the vehicle's own 1.25 m turning radius, and nothing in the file knew the two were coupled |
| **what that did to the truck** | the controller commanded **5–9 %** of the yaw rate the plan's curvature required (gain 0.049, −0.011, −0.052), held whatever heading it had, and **integrated it** |
| **and the miss is that integral, to 6 %** | `…130956` predicted **−1.5435 m** from the heading error alone against **−1.5844 m** measured (**ratio 0.974**); `…131222` **−1.0149** against **−0.9579** (**1.059**). Nothing is left over for the localiser, the jumps or the replans. `drive_goal.heading_account()` |
| **proved twice on the rig before anything moved** | `cost_weight` × **100** at the shipped gate: indistinguishable from baseline. The gate alone 20 → 5: behaviour changed completely, into a limit cycle |
| **THE FIX** | horizon `time_steps` 56 → **134** (2.01 m), `prune_distance` 2.0 → **2.5**, `PathAlignCritic.offset_from_furthest` 20 → **12**, `use_path_orientations` false → **true** |
| **THE ACCEPTANCE** | **10 arrivals in 11** on one set of parameters, against §15.3's **1 in 5**. The headline `spine_north` **6 of 6** against 1 of 3; `aisle_end` **2 of 2** |
| **AND THE ONE PLACE IT DID NOT REACH ITS BAR** | `ring_corner`, the same straight leg carried to 37 m, is **2 of 3**. The loop is MARGINALLY STABLE there and the outcome is bimodal — heading swing 0.20 rad when it locks on, 0.55 when it does not. A horizon rung aimed at it was tried and REJECTED on measurement. §16.4c |
| the arrival, scored at rest | truth **0.4474 – 0.5859 m**, belief **0.4588 – 0.5063 m**, the two 0.006 – 0.086 m apart, both inside the unchanged **0.60 m** box |
| and the arrival HEADING, which nothing demands | **−0.0126 to +0.0817 rad** on the straight approaches, against **1.6920 rad** on §15.3's one arrival |
| the fail-fast | §16.7 — a goal-relative watchdog in the bench and a 335 s budget in the tree, demonstrated both directions |
| the 0.25 m station class | §16.6 — position-only stays, and the argument is now a measured CURVE rather than an assertion |
| the jump budget | §16.8 — `EVIDENCE_LOCALIZATION_V3.md` §13.10a, **0.8310 m closed loop against 0.2591 m open**, and it is the LONGEST ROUTE rather than the worst driving that produces it |

### 16.1 The suspect list, and the measurement that killed each

The brief left five suspects open. Four are dead and each died to a
number. **All four were killed OFFLINE, on sessions §15 had already
recorded, before the rig was touched** — `drive_goal.py analyse` and
`plans_of()` need no ROS.

**(a) "the plan's end is not the goal."** DEAD. Every `/plan` is
recorded with its poses, so this is a direct read. Across the three
`spine_north` runs — 644 plans — the last pose of every plan is the goal
to **0.0000 m**, with a single exception at 0.0092 m. `ring_corner`'s
and `aisle_end`'s are the same. **The planner put the path through the
goal every time and the vehicle did not follow it there.**

**(b) "the 0.6490 m map → odom steps relocate the goal mid-approach."**
DEAD, and it is the same measurement that kills (c). On the two runs
that actually reached the goal's along-track station the worst single
correction was **0.2071 m** and **0.1561 m** — the 0.6490 m step is
`ring_corner`'s, a different run. More decisively: **the lateral miss is
fully accounted for without any jump at all.** Integrating the vehicle's
own ground speed against its heading error over the transit —
`∫ |v| · sin(ψ) dt`, both off the ground truth, ψ measured against the
goal's own travel heading — predicts

`drive_goal.heading_account()`, over the transit — the window opens
when the goal is SENT and stops 3.0 m short of it along track
(`nav.analyse.transit_margin_m`), because past that the vehicle hooks
round and integrating the pirouette would not be an account of the
transit:

| run | predicted from the heading alone | measured `across` change | ratio | ψ mean |
|---|---|---|---|---|
| `…130956` | **−1.5435 m** | −1.5844 m | **0.974** | −0.1053 rad |
| `…131222` | **−1.0149 m** | −0.9579 m | **1.059** | −0.0693 rad |

A residual of 2.6 % and 5.9 % is not room for a 0.65 m teleport. **The
vehicle drove in a straight line that was pointing 4.0°–6.0° off, for
seventeen metres.**

> **THE COMMITTED INSTRUMENT'S FIGURES, AND THEY MOVED FROM THE ONE-OFF
> THIS SECTION WAS FIRST WRITTEN FROM** (0.948 and 1.032, off
> −1.4894/−1.5714 and −0.9616/−0.9319). That script opened its window at
> t+9 s, a number chosen by hand to skip the launch transient;
> `heading_account()` opens at the goal being sent and closes on a
> config'd along-track margin, which is a rule rather than a choice.
> **Both readings say the same thing** and the instrument's are the ones
> that stand, because they can be re-run.

**(c) "459 replans re-anchor the path and the controller orbits a moving
target."** DEAD. The replans are downstream of the mechanism, not
upstream of it: the miss accumulates at a CONSTANT rate equal to
`|v|·sin(ψ)` (above), which contains no term for replanning, and the
plan terminus is fixed (a). The 459 plans of `…131600` are what a
vehicle that has already missed produces while trying to come back —
which is §16.7's problem, not this one's.

**(d) "the prediction horizon against the 1.02 m stopping distance."**
NOT DEAD — **and it is not about stopping.** The horizon is the
mechanism's cause, and the quantity it is short against is the turning
radius rather than the stopping distance. §16.2.

**(e) "the goal-checker geometry compounding it."** DEAD AS A CAUSE. The
box is 0.60 m and the miss is 0.9918 m in the pose the checker sees; a
box that contained that miss would be 1.65× the moving error budget F3
handed over and would not be a fix, it would be a bigger target. The
fixed controller arrives **with the box unchanged** (§16.5).

**AND THE ONE THE LIST DID NOT HAVE, WHICH IS THE ANSWER:** a critic
that was configured, weighted, enabled, read back on the running node
by §14.5 — and structurally unable to score.

#### 16.1a The question §15.4 left: why does it miss at the speed where tracking is TIGHT?

The brief put it directly: deviation from the plan is 0.040–0.113 m mean
at 0.300 m/s and 0.3140 m at 0.700 m/s, so why is the miss at 0.300?

**BECAUSE THE DEVIATION FIGURE IS NOT A TRACKING FIGURE ON THIS STACK,
AND §15.4 SAYS SO WITHOUT MEANING TO.** It is the distance from the
truth to *the plan standing at the time*, and the tree replans at 1 Hz
from the vehicle's own pose — so **every plan starts underneath the
vehicle**. A controller that never turns at all is therefore never more
than one replan cycle's worth of drift from its path, and 0.043 m is
what one second of a 0.024 m/s drift looks like. The figure is small
because the plan keeps moving to where the truck is.

The 0.700 m/s run is the same defect read through the same flawed
instrument: at 2.33× the speed the vehicle covers 2.33× the ground
between replans, so the same heading error shows up as 7× the
"deviation". **Both envelopes have the identical defect.** §16.2's
CURVATURE FOLLOWING gain is the figure that does not have this problem,
and it reads 0.049 / −0.011 / −0.052 at 0.300 m/s — a controller
ignoring its plan, at the speed where the deviation figure said it was
tracking beautifully.

### 16.2 THE MECHANISM, in the shipped binary's own source

nav2 **1.3.12**, tag `1.3.12` = commit `6be3614`,
`nav2_mppi_controller/src/critics/path_align_critic.cpp`, the third
statement of `score()`:

```cpp
  // Don't apply when first getting bearing w.r.t. the path
  utils::setPathFurthestPointIfNotSet(data);
  // Up to furthest only, closest path point is always 0 from path handler
  const size_t path_segments_count = *data.furthest_reached_path_point;
  float path_segments_flt = static_cast<float>(path_segments_count);
  if (path_segments_count < offset_from_furthest_) {
    return;
  }
```

and `nav2_mppi_controller/tools/utils.hpp`, which is **installed on this
rig** and was read there:

```cpp
inline size_t findPathFurthestReachedPoint(const CriticData & data)
{
  const auto traj_x = xt::view(data.trajectories.x, xt::all(), -1, ...);
  ...
    max_id_by_trajectories = std::max(max_id_by_trajectories, min_id_by_path);
  return max_id_by_trajectories;
}
```

**`furthest_reached_path_point` IS NOT A TUNABLE.** It takes the LAST
point (`-1`) of every sampled trajectory, finds the path index nearest
it and returns the largest over the batch. It is the **prediction
horizon expressed in path points**, and nothing else.

**THE FOUR NUMBERS, AND THREE OF THEM WERE ALREADY ON DISK.**

| | value | where it comes from |
|---|---|---|
| the horizon | `time_steps` 56 × `model_dt` 0.05 × `vx_max` 0.300 = **0.84 m** | `nav2.yaml`, read back on the running node in §14.5 |
| the plan's pose spacing | **0.0675 – 0.1060 m**, medians 0.083 – 0.105 | measured over the 1000 plans of the five shipped runs |
| ⇒ the reachable path index | **medians 2 – 8, best 12** | the two above, per plan, per run — `drive_goal.align_gate_scan()` |
| the gate | `offset_from_furthest` **20** | `nav2.yaml` — the upstream default, and the one line in that file with **no derivation beside it** |

`drive_goal.align_gate_scan()`, given the window §14.5 read back off
the running node for those runs — `time_steps` 56, `model_dt` 0.05,
`vx_max` 0.300, gate 20:

| session | plans | reachable index (mean / median / max) | could clear a gate of 20 |
|---|---|---|---|
| `…130956` | 57 | 8.23 / 8 / **11** | **0 of 57** |
| `…131222` | 126 | 5.56 / 4 / **12** | **0 of 126** |
| `…131600` | 457 | 6.55 / 7 / **8** | **0 of 457** |
| `…132535` `ring_corner` | 190 | 4.78 / 3 / **8** | **0 of 190** |
| `…133039` `aisle_end` | 170 | 3.19 / 2 / **8** | **0 of 170** |
| **the shipped set** | **1000** | | **0 of 1000** |
| `…120921` at **0.700 m/s** (horizon 1.96 m) | 274 | 4.57 / 2 / **27** | **10 of 274** |

The scan covers the **1000 plans published while the vehicle was
moving**; seventeen more were published at a standstill and are dropped
AND COUNTED, because a horizon is a speed times a time and at rest it is
zero — those seventeen would fail the gate by more, not less.

**AND THE INDEX IS AN UPPER BOUND**, which makes `0 of 1000` the
stronger claim rather than the weaker one: it is what a trajectory that
followed the plan EXACTLY would reach, and a real sample curves away
from the path and reaches the same index or a lower one.

> **THE COMMITTED INSTRUMENT'S FIGURES, AND THEY MOVED SLIGHTLY FROM THE
> ONE-OFF SCAN THIS SECTION WAS FIRST WRITTEN FROM** (1005 plans, best
> index 13, and 11 of 275 at 0.700 m/s). Two rules changed when the scan
> became a function: it resolves the horizon to the NEAREST path pose
> rather than the first one at or beyond it — which is what nav2's own
> `findPathFurthestReachedPoint` does with the trajectory's last point,
> and it lowers the index by one wherever the horizon lands between
> poses — and it drops plans below `nav.analyse.follow_speed_mps`
> instead of an ad-hoc threshold. **Neither reading changes the
> finding**: the gate was never cleared on any of them.

**AND THE SAME INSTRUMENT ON THE FIXED STACK IS THE MIRROR IMAGE.**
`goal-spine_north-…180105`, one of §16.5's arrivals, scanned against its
own window (134 × 0.05 × 0.300 = 2.01 m, gate 12):

```
          54 plan(s) scanned, 1 dropped at a standstill
            reachable path index: mean 18.81, median 18.0, max 28.0
          COULD HAVE CLEARED THE GATE: **52 of 54**
```

**0 of 1000 before and 52 of 54 after**, on the one quantity the whole
diagnosis turns on. That block prints on every `analyse` now, so the
next task to move the speed and not the count will see it go back to
zero on its own runs.

**WHAT WAS LEFT DOING THE STEERING.** `PathFollowCritic` pulls only the
trajectory's LAST point toward ONE path point (`furthest + 5`);
`GoalCritic` acts inside 1.4 m; `PathAngleCritic` returns early below
`max_angle_to_furthest` = 1.0 rad, so it is a turn-around critic and not
an alignment one. **Not one of them costs a vehicle for driving
parallel to its path, half a metre to the side of it.**

**THE INSTRUMENT THAT SHOWS IT DIRECTLY.**
`drive_goal.curvature_following()` takes the plan's own curvature at the
vehicle, multiplies by the speed being driven — that IS a yaw rate — and
regresses what the controller commanded on it through the origin. 1.0 is
a controller that obeys, 0.0 is one that ignores:

| run | demand rms | **GAIN** |
|---|---|---|
| `…130956` | 0.0917 rad/s | **0.049** |
| `…131222` | 0.0636 rad/s | **−0.011** |
| `…131600` | 0.0092 rad/s | **−0.052** |

A demand of 0.06–0.09 rad/s is a quarter of `wz_max` (0.240). **The plan
was asking for a quarter of the vehicle's whole angular authority and
getting five per cent of it.**

**AND THE PROVENANCE IS THE PART WORTH KEEPING.** `time_steps: 56` was
derived in this file against the **0.700 m/s** ceiling — its comment
still read "1.96 m of look-ahead" when this task opened it. §15.2 rung
11 then took the ceiling to 0.300 m/s on the stop table, correctly, and
**a count of steps multiplied by a smaller speed is a shorter
distance**. 0.84 m is below the vehicle's own 1.25 m minimum turning
radius: inside a horizon shorter than the radius it may turn on, every
turn looks nearly free and the cost surface is blind to where it leads.
**The speed change switched the critic off, and nothing in the file
named the coupling.** `tests/test_nav2_params.py` now derives the count
from the speed, so the next task to move one and not the other fails a
test instead of a goal.

### 16.3 The two-sided proof, on the rig, before anything was fixed

A structural claim deserves a structural test, and one run either side of
a hair is not one. Both rungs are single goals on the headline route,
stack stopped and restarted for each.

**NULL TEST — `cost_weight` 14.0 → 1400.0, gate left at 20.**
*Hypothesis:* the critic never scores. *Prediction:* multiplying an
inert critic's weight by one hundred changes nothing. *Run:*
`goal-spine_north-20260827-162800`, `nav=on@5097c0e5`. *Verdict:*
**CONFIRMED.** ABORT 205; curvature-following gain **0.089** against the
baseline's 0.057; closest approach 3.04 m. A hundredfold change in the
largest weight in the file is not visible in the vehicle's behaviour,
which is only possible if the term is never added.

**POSITIVE CONTROL — weight back to 14.0, gate 20 → 5, horizon
untouched.** *Hypothesis:* the gate is what silences it. *Prediction:*
the behaviour changes completely. *Run:*
`goal-spine_north-20260827-163615`, `nav=on@9697ed42`. *Verdict:*
**CONFIRMED, and it went unstable** — commanded curvature pinned at
±0.80 (the minimum turning radius) for the whole run, the heading
sweeping through 2π repeatedly, 443 plans, ABORT 205. Aligning a 0.84 m
trajectory to a 0.5 m stub of path on a 1.25 m radius is not a corridor,
it is a point attractor. **The gate was the switch; it was not the
fix.**

### 16.4 THE LADDER

`nav` is the `nav=on@<md5>` label. `analyse` refuses to table two of them
together, so every rung is its own group and this table is assembled by
hand from per-rung output.

| # | `nav2.yaml` | what moved | goal | result | closest (belief) | gain | what it measured |
|---|---|---|---|---|---|---|---|
| 0 | `6555ac39` | nothing — §15's file, comments only | `spine_north` | CANCELLED at 479.7 s, 440 plans | 10.7963 m | 0.057 | **the failure reproduces on this bringup** |
| 1 | `5097c0e5` | `PathAlignCritic.cost_weight` ×100 | `spine_north` | ABORT 205, 361.6 s | 3.0353 m | 0.089 | **nothing changed — the critic is inert** |
| 2 | `9697ed42` | weight back; `offset_from_furthest` 20 → 5 | `spine_north` | ABORT 205, 457.8 s | 3.5992 m | 0.173 | **the critic is live and the loop limit-cycles** |
| 3 | `008e5781` | `time_steps` 56 → 134, `prune_distance` 2.0 → 2.5, gate → 12 | `spine_north` | **SUCCESS**, 57.5 s, 56 plans | **0.5792 m** | — | **across 1.586 → 0.155 m; heading error 0.105 → 0.002 rad** |
| 4 | `21ac4916` | + `SimpleGoalChecker` at 0.25 m / 0.15 rad | `spine_north` | ABORT 205, 454.4 s | **0.0062 m** | — | the POSITION half of the station class is met to six millimetres; the heading there is 0.324 rad out. §16.6 |
| 5 | `d9b69c48` | reverted to `PositionGoalChecker` 0.60 m; every derivation written | ×5 | **4 of 5** — `spine_north` 3/3, `aisle_end` SUCCESS, **`ring_corner` no_progress** | | | **the 37 m leg oscillates**: ±0.3 rad, ~20 s period, rising, 1.5 m off the line by t+35 s |
| 6 | `f5255467` | `use_path_orientations` false → **true** | `ring_corner` | **SUCCESS**, 127.6 s | 0.5980 m | **0.648** | **the damping term.** §16.4a |
| **7** | `e2ad0354` | `time_steps` 134 → 152 (the WHOLE 2.269 m manoeuvre), `prune_distance` 2.5 → 2.8 | `ring_corner` ×2 | **1 of 2** | 0.5925 m / 7.3915 m | 0.619 / 0.456 | **REJECTED, and §16.4c is the measurement.** 13 % more work per tick and the oscillation statistic did not move. **Reverted.** |

**RUNGS 1, 2 AND 7 ARE REJECTED RUNGS AND THEY ARE HERE FOR THE SAME
REASON THE ARRIVALS ARE.** The shipped file is rung 6; rung 3's numbers
are in it unchanged.

#### 16.4a Rung 6, because a fix that only works on short legs is not one

Rung 3 arrived three times out of three on the 17 m headline and rung 5
still lost `ring_corner` — **the same straight leg carried on to 37 m**.
That is not a harder leg. It is the same leg with room for an
oscillation to develop, and the oscillation is a property of what the
critic was costing:

```cpp
  summed_path_dist += sqrtf(dx * dx + dy * dy);        // false
```

— the DISTANCE from each trajectory point to the path, and nothing else.
That is proportional feedback on cross-track error, and cross-track
error on a steered vehicle is a **double integrator** of the steer
angle: steer changes heading, heading changes cross-track rate. Round a
double integrator, proportional feedback oscillates; the only damping
was however far MPPI could see, 2.01 m against a 1.25 m radius. Measured
on `goal-ring_corner-20260827-172326`: heading swinging ±0.3 rad with a
period near 20 s and a **rising** amplitude, 1.54 m off the line by
t+35 s, then a limit cycle at the minimum radius, abandoned by the
watchdog at t+72.0 s.

`use_path_orientations: true` adds the path's own per-pose heading to
the cost — `sqrtf(dx*dx + dy*dy + dyaw*dyaw)` — which is the rate term
the loop was missing: a trajectory heading across the path is penalised
**before** it has got anywhere. `ring_corner` then arrived in 127.6 s
with a curvature-following gain of **0.648** against 0.161 on the run
that failed.

**AND THE ORIENTATIONS ARE WORTH READING HERE, WHICH IS NOT UNIVERSAL.**
`SmacPlannerHybrid` is a FEASIBLE planner: every pose carries the
heading a vehicle of this turning radius would hold there, and §14.5's
`PathAngleCritic.mode: 2` already reads the same field for the same
reason. On a planner emitting geometric waypoints this would be scoring
noise.

#### 16.4c `ring_corner` IS MARGINALLY STABLE, AND RUNG 7 DID NOT FIX IT

**THE SHIPPED CONFIGURATION ARRIVES ON `ring_corner` TWICE IN THREE, AND
THAT IS THE ONE PLACE THIS TASK DID NOT REACH ITS OWN BAR.** It is
stated first and argued after.

Three runs on the shipped parameters — `f5255467` and `3148d052` differ
by COMMENTS ONLY, which is not an assertion: reversing the four
comment edits reproduces `f5255467` byte for byte and
`yaml.safe_load` returns identical parameter trees, which is what
`nav_config_md5` (both **`53a33d67`**) exists to say:

| run | `nav=` | ψ standard deviation | ψ max | result |
|---|---|---|---|---|
| `…173139` | `f5255467` | **0.2072 rad** | 0.5759 | ARRIVED |
| `…174429` | `f5255467` | **0.1957 rad** | 0.4873 | ARRIVED |
| `…180823` | `3148d052` | **0.5447 rad** | 1.2113 | abandoned, `no_progress` |

ψ is the vehicle's travel heading against the goal's, off the ground
truth. **The outcome is bimodal**: a run either locks onto its route at
ψ ≈ 0.20 rad of swing, or it oscillates at ≈ 0.55 and does not recover.
It is not a slow degradation — it is which side of a stability boundary
the run lands on. §15's own `ring_corner` runs sit at **1.33 – 1.47 rad**
for comparison, and rung 5's at 1.22: rung 6 moved the statistic by
**six times** and the residual is what is left.

**IT IS THE LONGEST STRAIGHT LEG AND THAT IS THE POINT.** `spine_north`
is the same leg stopped at 17 m and it has arrived **six times from
six**; `ring_corner` carries it to 37 m. A leg is not harder for being
longer — it is the same leg with room for an oscillation to develop, and
20 m is where this one does.

**RUNG 7: THE HORIZON WAS THE OBVIOUS NEXT LEVER AND IT IS NOT THE
LEVER.** §16.2's fix sized `time_steps` at 134 — 2.01 m, the quarter
turn at the minimum radius rounded up — on an argument that a
RECEDING-horizon optimiser needs only enough of a manoeuvre to prefer
starting it, not all of it. The obvious reading of 16.4c is that the
argument was too thin, so it was tested: `time_steps` 152, a horizon of
**2.28 m** holding the whole 2.269 m correction, `prune_distance` 2.8.

| run | ψ sd | ψ max | closest (belief) | result |
|---|---|---|---|---|
| `…182158` | **0.2255 rad** | 0.4867 | 0.5925 m | ARRIVED |
| `…182541` | **0.5703 rad** | 1.1048 | 7.3915 m | ABORT 205 |

**THE SAME BIMODALITY, THE SAME TWO CLUSTERS, ONE ARRIVAL IN TWO
AGAINST TWO IN THREE.** The statistic the change was made to move did
not move. It cost 13 % more work per tick — the controller still holds
20.000 Hz median, with the worst tick at 0.070 s against 0.064–0.068 —
and bought nothing measurable, so **it was reverted** and `nav2.yaml` is
byte-identical to the file the acceptance set was driven on. The
receding-horizon argument stands, not because it was proved but because
the experiment that would have overturned it did not.

**WHAT THE RESIDUAL LOOKS LIKE, AND THE LEVER NOBODY HAS PULLED.** On a
failing run the PLAN oscillates with the vehicle: the tree replans at
1 Hz **from the vehicle's own pose and heading**, so a heading that is
swinging produces a Reeds-Shepp path that swings, which the controller
then follows. That is a planner-controller loop at 1 Hz around the
20 Hz one, and neither the align critic's gate nor its horizon reaches
it. The untried levers, in the order they look promising, are
`PathAlignCritic.cost_weight` (14.0, the upstream default for a
differential base with an order more angular authority than this
vehicle's 0.24 rad/s), and the 1 Hz `RateController` in the tree
itself. Both are named in §16.9 and neither is touched here, because
this task's discipline is one mechanism confirmed by measurement before
any change and the mechanism behind this residual is not confirmed.

#### 16.4b One thing rung 6 did NOT fix, and it is the planner's

`ring_corner` arrives, and it spends the middle of its route **1.2 –
1.5 m north of the geometric straight line** between spawn and goal. That
is not the controller. It is read straight off the **first plan** —
published before the vehicle had moved, on both the failing and the
passing configuration:

| x (world) | −17.0 | −10.6 | −4.0 | +2.5 | +9.0 | +15.6 | +18.2 |
|---|---|---|---|---|---|---|---|
| y, rung 6 | +9.95 | +11.11 | +11.22 | +11.29 | +11.47 | +11.44 | +10.53 |
| y, rung 5 | +9.97 | +10.51 | +11.27 | +11.25 | +11.52 | +11.42 | +10.69 |

The costmap's inflation gradient bows the route off the rack line and
brings it back to the goal at the end. **It is §15.2 rung 5's finding
again** — a freespace planner is not a road graph — and it is named as
open in §16.9 rather than tuned here. What matters for an arrival is the
`across` at the GOAL, and that is +0.0592 m.

### 16.5 THE ACCEPTANCE SET

Stack **stopped and started before every one**; `traction=nominal`,
`arm=wheel+imu`, `loc=amcl@735cdbc6`, headless, dry. The same three
goals and the same repeat counts §15.3 was asked for, on `config.yaml`'s
unchanged goal table, driven by the same
`tools/drive_goal.py record --goal G`.

**ELEVEN RUNS ON ONE SET OF PARAMETERS, AND THE `nav=` LABEL CANNOT SAY
SO — WHICH IS WHY `nav_config_md5` NOW EXISTS.** They were driven behind
two byte-different `nav2.yaml`s, `f5255467` and `3148d052`, and the
difference between those files is **four comment edits**. That is
demonstrated rather than asserted: reversing the four reproduces
`f5255467` byte for byte, and `yaml.safe_load` returns identical
parameter trees — both files hash to `nav_config_md5` **`53a33d67`**.
`analyse` will still refuse to table them together, because its
mixed-set refusal keys on the byte hash; §16.9 item 6 is that ledger
entry. The two groups are therefore printed as two groups.

| | | |
|---|---|---|
| **the headline goal, `spine_north`** | **6 of 6** | against §15.3's 1 of 3 |
| `aisle_end` | **2 of 2** | |
| `ring_corner` | **2 of 3** | §16.4c — the one place this task did not reach its bar |
| **all three** | **10 of 11** | against §15.3's **1 of 5** |

#### The set on `nav=on@f5255467`, five goals and five arrivals

| session | goal | result | sim s | driven | arrival TRUTH | arrival BELIEF | truth−belief | heading |
|---|---|---|---|---|---|---|---|---|
| `…173700` | `spine_north` | **SUCCESS** | 57.2 | 16.357 m | **0.5090 m** | 0.4710 m | 0.0380 m | −0.0246 rad |
| `…173929` | `spine_north` | **SUCCESS** | 57.6 | 16.446 m | **0.5684 m** | 0.4933 m | 0.0751 m | −0.2983 rad |
| `…174159` | `spine_north` | **SUCCESS** | 56.9 | 16.405 m | **0.4474 m** | 0.4636 m | 0.0162 m | −0.0126 rad |
| `…174429` | `ring_corner` | **SUCCESS** | 126.9 | 37.151 m | **0.4568 m** | 0.5055 m | 0.0487 m | −0.3079 rad |
| `…174805` | `aisle_end` | **SUCCESS** | 161.9 | 47.453 m | **0.5859 m** | 0.5001 m | 0.0858 m | −0.0477 rad |

`…173139` is a sixth on the same file — rung 6's own `ring_corner`,
**SUCCESS**, 127.6 s, truth 0.4493 m.

#### The set on `nav=on@3148d052`, the committed bytes

| session | goal | result | sim s | driven | arrival TRUTH | arrival BELIEF | truth−belief | heading |
|---|---|---|---|---|---|---|---|---|
| `…180105` | `spine_north` | **SUCCESS** | 56.5 | 16.351 m | **0.5133 m** | 0.4858 m | 0.0275 m | −0.0585 rad |
| `…180329` | `spine_north` | **SUCCESS** | 57.7 | 16.368 m | **0.4646 m** | 0.4588 m | 0.0058 m | +0.0145 rad |
| `…180557` | `spine_north` | **SUCCESS** | 57.0 | 16.396 m | **0.5396 m** | 0.4712 m | 0.0684 m | +0.0817 rad |
| `…180823` | `ring_corner` | **abandoned** `no_progress` | 122.7 | 29.021 m | 14.6594 m | 14.6702 m | 0.0107 m | +0.8197 rad |
| `…181145` | `aisle_end` | **SUCCESS** | 156.3 | 45.908 m | **0.5524 m** | 0.5063 m | 0.0461 m | −0.2082 rad |

**BOTH INSTRUMENTS ARE INSIDE THE BOX ON EVERY ARRIVAL.** The arrival is
scored AT REST, where the moving along-track offset has closed and truth
and belief agree to **0.0058 – 0.0858 m**: TRUTH **0.4474 – 0.5859 m**
and BELIEF **0.4588 – 0.5063 m**, against a **0.60 m** box. §16.6 is why
that is the row the criterion is evaluated on, and why the
closest-approach row below sits one moving offset outside it by
construction.

**AND THE HEADING IS DELIVERED WITHOUT BEING DEMANDED.** −0.0126 to
+0.0817 rad on four of the six headline runs, against **1.6920 rad** on
§15.3's one arrival. The larger ones — −0.298, −0.308, −0.208 — are the
route's own arrival heading after a corner and not an error; nothing on
this stack requires either (§16.6, §16.9 item 3).

#### The closest approach, which is the row the box latches on

| session | CLOSEST truth | CLOSEST belief | ALONG | ACROSS |
|---|---|---|---|---|
| `…173700` | 0.6868 m | **0.5978 m** | −0.5977 | **−0.0139** |
| `…173929` | 0.7294 m | **0.5897 m** | −0.5253 | **+0.2680** |
| `…174159` | 0.6073 m | **0.5829 m** | −0.5811 | **−0.0455** |
| `…174429` | 0.5899 m | **0.5948 m** | −0.5935 | **−0.0392** |
| `…174805` | 0.7050 m | **0.5864 m** | −0.5728 | **−0.1260** |
| `…180105` | 0.6829 m | **0.5943 m** | −0.5920 | **+0.0524** |
| `…180329` | 0.6441 m | **0.5924 m** | −0.5875 | **−0.0754** |
| `…180557` | 0.7131 m | **0.5895 m** | −0.5881 | **−0.0403** |
| `…181145` | 0.6896 m | **0.5828 m** | −0.5808 | **−0.0476** |

**THE MISS IS NOW ALL ALONG-TRACK.** `across` is **−0.126 to +0.268 m**
against §15.3b's **−0.5277 m and −0.9596 m**: the component that carried
the whole of the old failure is gone. What is left is the box's own
radius — every `along` is between −0.525 and −0.598 m against a 0.60 m
box, because `stateful` latches the first time the belief is inside and
the vehicle then stops. **The box IS the arrival error now, and the
controller is not.**

#### What the controller did

| | `…180105` | `…180329` | `…180557` | `…180823` | `…181145` |
|---|---|---|---|---|---|
| `/cmd_vel` messages | 1130 | 1158 | 1142 | 2457 | 3128 |
| rate, mean Hz | 20.021 | 20.056 | 20.023 | 20.017 | 20.018 |
| RTF over the drive | 0.9999 | 0.9980 | 0.9997 | 0.9986 | 0.9992 |
| deviation from plan, mean | 0.0617 m | 0.0516 m | 0.0499 m | 0.0788 m | 0.0462 m |
| deviation, max | 0.2745 m | 0.1580 m | 0.1356 m | 0.2863 m | 0.1915 m |
| **curvature-following GAIN** | **0.209** | **0.232** | **0.407** | 0.425 | **0.479** |
| worst steer step | 0.062707 | 0.100000 | 0.100000 | 0.100000 | 0.099970 |
| cusps | 0 | 0 | 0 | 1 | 0 |
| plans published | 55 | 56 | 56 | 118 | 150 |
| worst `map`→`odom` step | 0.0851 m | 0.1396 m | 0.1300 m | 0.5067 m | 0.6376 m |
| worst heading step | 0.0086 rad | 0.0098 rad | 0.0110 rad | 0.0228 rad | 0.0186 rad |

**THE GAIN AND ITS DEMAND ARE READ TOGETHER, ALWAYS.** 0.209 on a
straight `spine_north` is not a worse controller than 0.479 on
`aisle_end`: a closed loop that never leaves its line has a plan that
asks for almost nothing, and the gain over almost nothing is
quantisation. What matters is that where the plan DOES ask — the
corner-carrying routes — the controller now delivers **0.4 – 0.65** of
it, against **0.049, −0.011 and −0.052** in §15.

**THE COMMAND PATH IS UNTOUCHED AND SAYS SO.** The worst steer step is
**0.100000 rad/tick** wherever the controller asked for a full step —
F4 Task 1's 2.0 rad/s ramp at 0.05 s, exactly, as on all five of §15.4's
runs. `…180105`'s 0.062707 is simply a run that never asked for one. F4
constraint 18 holds: `--nav` added a publisher to the top of that path
and changed nothing about it.

**THE RATE HELD AT THE LONGER HORIZON.** `time_steps` went 56 → 134,
which is 2.4× the samples per tick, and the controller holds
**20.017 – 20.056 Hz mean, 20.000 median**, with the real-time factor at
0.998 – 1.000. That was the standing risk in the fix and it is measured
rather than assumed.

**AND THERE ARE NO CUSPS.** Zero direction changes on every arrival,
against **16** on §15.4's `ring_corner`. A vehicle that tracks its path
does not need the planner to turn it round.

#### Both arms, and the sweep

F4 constraint 20. Every arm this change can reach, on the committed
tree (`nav2.yaml` **`3148d052`**), headless.

| arm | children | result |
|---|---|---|
| **`--localize amcl --nav`** | **16** | the eleven runs above, and every one of §16.5's bringups. `nav=on@3148d052` |
| **`--localize amcl`, NO `--nav`** | **11** | all ALIVE; GPU preflight `D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`; `ekf` healthy (**0.213961** against a ceiling of 100); navcmd gate passed — one zero twist in, read off the gz side of the traction terminal; `map_server` + `amcl` ACTIVE, `loc: healthy` (**0.243005** against a ceiling of 1), seeded at map (−0.0793, −0.1458); **`nav=off`** |

```
  world  lasertf  bridge  imgbridge  odom  imutf  ekf  smoother
  navcmd  map_server  amcl                     11 alive, 0 dead.
  nav        off     no --nav: nothing plans, nothing follows a path,
                     and the only thing that has ever published
                     /cmd_vel on this stack is a bench
```

and `stop` took it down clean — `killed … (odom)`, `killed … (navcmd)`,
`swept … (gz sim)`, `down.`, then `not running (no pid file)`.

**NOTHING THIS TASK TOUCHED CAN REACH THAT ARM AND THE RUN IS HERE TO
SHOW IT RATHER THAN TO ARGUE IT.** `nav2.yaml` and the behaviour tree
are read only by `--nav`; `config.yaml`'s new `nav.budget`,
`nav.watchdog` and four `nav.analyse` keys are read only by
`tools/drive_goal.py`, which is a bench and not a child; and
`tools/evidence_core.py`'s two additions (`correlation()`, `read_csv`'s
`allow_empty`) are library functions with no caller on a bringup path.
The one thing that COULD have reached it is `drive_goal.py`'s new
`nav_label()` fields — and `record` is not run on this arm, which
refuses a stack whose state file says `nav=off`.

**`--localize slam` was NOT re-driven**, for §15.8's reason unchanged:
the nav children read the localiser only through `/tf`, so that arm
cannot change a figure here — but it was not driven, and this sentence
is the honest form of that.

### 16.6 THE 0.25 m STATION CLASS, RE-EXAMINED AFTER THE FIX

§15.2 rungs 12–13 ruled the `(xy, yaw)` pair "jointly unreachable" and
§14's `PositionGoalChecker` came out of it. **Both of those runs were
driven by a controller that was not following its path** (§16.2), so the
ruling was right with a confound nobody could see. It was therefore
asked again, with the controller fixed and the pair actually configured.

**RUNG 4, `nav=on@21ac4916`: `nav2_controller::SimpleGoalChecker` at
0.25 m and 0.15 rad — the station class, both halves.**

- It reached the goal POSITION to **0.0062 m of belief and 0.0478 m of
  truth**. Six millimetres. **The position half of the station class is
  met by this stack now**, and that is a change from §15.
- It never latched. The heading THERE was **0.324 rad** out, and it then
  drove 454 s and 441 plans and aborted.

**AND THE REASON IS A CURVE RATHER THAN A NUMBER.**
`drive_goal.py analyse`'s new CORRIDOR block walks that one approach —
cut where the run gave up, so no second pass contributes — and reports
the heading error at the moment the BELIEF first came inside each
candidate box:

| box | believed | truth | heading error |
|---|---|---|---|
| 2.00 m | 1.9995 | 2.0916 | 0.0752 rad (4.3°) |
| 1.50 m | 1.4947 | 1.5939 | **0.0239 rad (1.4°)** |
| 1.00 m | 0.9969 | 1.1093 | 0.1078 rad (6.2°) |
| 0.75 m | 0.7457 | 0.8480 | 0.1896 rad (10.9°) |
| **0.60 m** | 0.5996 | 0.6942 | 0.2456 rad (14.1°) |
| 0.50 m | 0.4983 | 0.5857 | 0.2815 rad (16.1°) |
| 0.40 m | 0.3977 | 0.4802 | 0.3204 rad (18.4°) |
| 0.30 m | 0.2988 | 0.3777 | 0.3658 rad (21.0°) |
| **0.25 m** | 0.2492 | 0.3274 | **0.3941 rad (22.6°)** |
| 0.20 m | 0.2000 | 0.2657 | 0.4200 rad (24.1°) |
| 0.15 m | 0.1488 | 0.2080 | 0.4428 rad (25.4°) |

0.10 m is **absent** because the run never reached it (0.1037 m was its
closest), which is the instrument refusing to report a rung as met.

**THE HEADING GETS WORSE THE CLOSER IT GETS, MONOTONICALLY, AND IT IS
KINEMATICS RATHER THAN TUNING.** Inside 1.4 m `PathFollowCritic` and
`GoalCritic` have swapped places — both carry `threshold_to_consider:
1.4` — and inside 0.5 m `PathAlignCritic` and `PathAngleCritic` have
stopped. **The last metre and a half is steered by a point attraction
with no path and no heading in it**, and a tricycle nulling a residual
lateral offset against a 1.25 m minimum radius pays for it in yaw.

**THE RULING: POSITION-ONLY STAYS, AND WHAT CHANGED IS THE ARGUMENT.**
It is no longer "the pair is unreachable" — the position half is
reachable to six millimetres. It is: **the pair is not reachable in ONE
APPROACH, because closing the position costs the heading at a measured
rate.**

**AND THE POSITION-ONLY BOX BUYS THE HEADING BACK, WHICH IS THE RESULT
THAT DECIDES IT.** On rung 3, position-only at 0.60 m, the box latched
at 0.5792 m of belief with the heading **0.0363 rad** out — because it
latched while the vehicle was still on the straight approach leg and
never entered the point attraction at all. Its arrival heading was
**0.0329 rad**, against **1.6920 rad** on §15.3's one arrival. *A
position-only checker on a fixed controller delivers a better arrival
heading than a heading-aware one on this machine.*

**WHAT F5's DOCKING INHERITS, CONCRETELY.** A station-class arrival needs
a **STRAIGHT FINAL LEG along the dock axis**, and the table above is what
says how long: the heading is still inside 0.15 rad at **1.50 m** and
0.0239 rad there, so a final leg of about a metre and a half of straight
approach is what buys the pair. That is exactly what a docking server's
`slowdown_radius` / `v_linear_min` straight run-in is for
(`docs/reports/m5v3-02` §3), and it is now a number rather than a hope.

**AND THE BOX IS A LATCH CRITERION ON A BELIEF, WHICH IS WHY TWO NUMBERS
ARE ALWAYS PRINTED.** `stateful` latches the first time the BELIEVED
pose is inside, and the truth at that instant is one moving
localisation offset behind it — 0.054–0.080 m on these runs. So the
CLOSEST-approach truth sits just outside any box by construction, and the
figure the arrival is scored on is the one taken **at rest**, where
belief and truth agree to 0.0064–0.0801 m. Both are in §16.5's table and
neither is quoted without the other.

### 16.7 THE FAIL-FAST

§15.7 item 2: *"a goal that cannot be reached should fail FAST, and
nothing in this configuration makes it."* Measured, before it existed:
**130.199 m driven and 459 plans published for a goal 2.910 m away**,
and a second run that reached 479.7 s and was ended by the bench's
last-resort timeout rather than failed by the stack.

**THERE ARE TWO GUARDS AND THEY ANSWER DIFFERENT QUESTIONS.** Neither is
a safety function and neither inhibits motion; both only ever end a
goal.

#### 16.7a Why nav2's own progress checker cannot be the answer

`nav2_controller::SimpleProgressChecker` requires
`required_movement_radius` of MOVEMENT in `movement_time_allowance` —
0.30 m in 15 s here. **A vehicle that has driven past its goal and is
orbiting satisfies that completely**, because it is moving 0.30 m every
second. `…131600` moved 130.199 m while never coming within 9.6556 m of
its goal and the checker was satisfied on every one of its 9599 ticks.
Tightening it cannot reach the failure: it asks whether the vehicle
MOVED, and the question is whether it moved TOWARD anything.
`nav2_controller::PoseProgressChecker`, the only other one this build
ships, adds `required_movement_angle` — a WEAKER test, satisfied by
turning on the spot. Neither is goal-relative and there is no third.

#### 16.7b The bench's guard: `ClosingWatch`, and it IS goal-relative

`drive_goal.ClosingWatch` is stepped on `map` → `base_link` — **the pose
the goal checker itself sees** — composed live from the two `/tf` edges.
A MARK is kept, the smallest distance the run has earned; beating it by
`required_closing_m` moves the mark and restarts the clock; going
`closing_allowance_s` without moving the mark ends the run as
`outcome=no_progress`, a NAMED line in `session.txt` with the distance,
the mark and the elapsed time beside it. `config.yaml nav.watchdog` owns
both numbers, `no_progress_at()` is the same object run over a recording
so `record` and `analyse` cannot disagree, and 9 tests hold the rule.

**A LOCALISATION JUMP CANNOT PROVOKE IT, and the asymmetry is why.** The
rule fires on a FAILURE TO IMPROVE. A correction that moves the belief
AWAY from the goal is not an improvement, so it neither moves the mark
nor counts as progress; one that moves it TOWARD the goal moves the mark
and makes the rule *more* lenient. The worst closed-loop correction
measured is 0.6490 m (§16.8) and in either direction it can only delay
this guard.

**BOTH NUMBERS WERE SIZED ON THE RECORDED FAILURES, AND THE RULE WAS RUN
AGAINST EVERY SESSION ON DISK BEFORE IT WAS WRITTEN.**
`drive_goal.no_progress_at()` over all 32 scoreable driven-goal sessions
— fourteen different `nav2.yaml`s, every rung of §15's ladder and this
one's:

| | sessions | the rule fires |
|---|---|---|
| runs that **ARRIVED** | 20 | **0** |
| runs that **MISSED** | 24 | **20** |

**Zero false positives across twenty arrivals and twenty catches out of
twenty-four misses**, at `required_closing_m` 0.50 m and
`closing_allowance_s` 30.0 s. 30 s at the transit ceiling is **9.0 m of
travel for less than half a metre of net approach**, which no leg of
this floor's road graph does.

**THE FOUR IT DOES NOT CATCH ARE NOT ESCAPES.** `…111235` aborted on its
own after **18.2 s** and `…182541` after 140.0 s with nav2's own
error 205; a guard with a 30 s allowance has nothing to catch in a run
that fails faster than its own window. `…125858` (112.0 s) was still
closing when it aborted. And `…180823` **was abandoned by the LIVE
watchdog** at t+72.0 s and is simply not reproduced by this replay of
the rule — which is a difference in the POSE, not in the rule, and
§16.7b's last paragraph is about it.

**THE LIVE GUARD AND THIS REPLAY OF IT CAN DISAGREE ON A MARGINAL RUN,
AND THE REASON IS STATED RATHER THAN SMOOTHED.** `ClosingWatch` is one
object with two callers, but they are fed two reconstructions of the
same pose: live, `record` composes `map` → `base_link` on every
estimator message against the LATEST `map` → `odom` — a zero-order
hold, which is all a running node can do — while `analyse` uses
`evidence_core.compose_rows()`, which INTERPOLATES the parent because
that is what a tf2 listener would have returned. On a run whose
distance to the goal is swinging by metres, centimetres of difference
are enough to move a mark across the threshold. Neither reading is
wrong; the live one is the one that acted.

**WHAT IT COST THE FAILURES THAT ARE ALREADY ON DISK**, had it existed:

| run | ran for | the rule fires at | saved |
|---|---|---|---|
| `…161742` | 479.7 s | t+43.4 s | 436 s |
| `…131600` | 479.5 s | t+45.9 s | 434 s |
| `…124352` | 479.6 s | t+87.0 s | 393 s |
| `…165050` | 454.4 s | t+88.1 s | 366 s |
| `…131222` | 130.5 s | t+86.1 s | 44 s |

**AND IT CAUGHT ONE IN THE FIELD, UNPLANNED.** Rung 5's `ring_corner`
(`goal-ring_corner-20260827-172326`) is the run that forced rung 6, and
it is the first failure this stack has ever produced with the guard
armed. It ended at **t+72.0 s** as `outcome=no_progress`, 25.0968 m from
its goal, having gone 30.0 s without closing half a metre on its best of
25.4396 m. The equivalent run in §15 (`…132535`, same goal, same floor)
ran **212.8 s** and 199 plans before anyone knew.

**WHAT IT ASSUMES, STATED.** That the route CLOSES on the goal. A goal
whose road-graph route must first travel AWAY from it would trip this
legitimately, and the tree's budget below is the guard that covers that
case. None of `nav.goals` is such a route.

#### 16.7c The tree's guard: a 335 s navigation budget

The watchdog is the bench's. **A consumer that is not this bench gets
nothing from it**, so the second guard is nav2-side: a BT.CPP
`<Timeout msec="335000">` wrapping the whole of
`navigate_to_pose_tricycle_v3.xml`. When it expires it halts the tree
and returns FAILURE, and `navigate_to_pose` ABORTS.

**THE OBVIOUS CONSTRUCTION IS A TIMER THAT CAN NEVER EXPIRE**, and it is
worth writing down because it looks correct. A `ReactiveSequence` with
an inverted `<TimeExpired>` beside the pipeline does not work, and both
halves of that were read in the sources this rig has.
**BehaviorTree.CPP 4.9.0**, `src/controls/reactive_sequence.cpp`, the
RUNNING branch of `tick()`:

```cpp
        // reset the previous children, to make sure that they are
        // in IDLE state the next time we tick them
        for(size_t i = 0; i < childrenCount(); i++)
        { if(i != index) { haltChild(i); } }
```

— every child except the running one, the earlier ones included. And
**nav2 1.3.12**, `plugins/condition/time_expired_condition.cpp`:

```cpp
  if (!BT::isStatusActive(status())) {
    start_ = node_->now();
    return BT::NodeStatus::FAILURE;
  }
```

A halted node's status is IDLE, which is not active. The condition would
re-anchor its clock on every one of the tree's 100 ticks a second, for
ever. `<Timeout>` is a DECORATOR: it arms once when its
child starts running and is not re-armed while that child keeps running.

**AND IT SITS OUTSIDE THE TOP-LEVEL `RecoveryNode`.** Inside, each of
the six retries would re-arm it and the bound would be seven times the
number written.

**THE NUMBER IS DERIVED AND `config.yaml nav.budget` OWNS THE
DERIVATION:**

```
budget_s = ceil(longest_route_m / (vx_max * speed_fraction)
                + recovery_allowance_s)
         = ceil(45.709 / (0.300 * 0.5) + 30.0) = ceil(334.73) = 335
```

45.709 m is the longest first plan this track has measured — `aisle_end`'s,
the road graph's own 47 m route (§15.5). `speed_fraction` 0.5 lets a
route be half-speed from end to end and still arrive; the fixed
controller drives at 96 % of the ceiling. 30.0 s is six retries of this
tree's own `Wait 5.0`. `tests/test_nav2_params.py` recomputes it from
`config.yaml` and `nav2.yaml`, checks the attribute, and checks that it
sits outside the `RecoveryNode`.

**TWO THINGS IT IS NOT, AND BOTH ARE RECORDED RATHER THAN HIDDEN.** It
is a TIME bound and cannot tell a slow legitimate route from an orbit —
that is what 16.7b is for, and the two are complementary by design. And
its clock is BT.CPP's `TimerQueue`, `std::chrono::steady` — **WALL
time**, where everything else on this track is the plant's. The RTF
measured over these drives is 0.9963 – 1.0000, so 335 s of wall clock is
333.8 – 335.0 s of sim, and the budget carries 2× of margin rather than
being a tight bound partly for that reason.

#### 16.7d Demonstrated, both directions

**THE DIRECTION THAT PASSES** is §16.5: eleven runs, ten arrivals, and
`outcome=ran` on every one of the ten — neither guard fired on any of
them, and the rule fires on none of the **twenty** arrivals in 16.7b's
table. The eleventh is `ring_corner` `…180823`, which the watchdog
abandoned at t+72.0 s and which §16.4c is about: that is the guard doing
its job on a real failure, unplanned, and it is the run that forced the
rejected rung 7.

**THE DIRECTION THAT FAILS** needs a goal that cannot be reached, so
`config.yaml` carries one: **`rack_sw3`, world (−4.250, −4.250) — the
centre of `RackSW3`**, a 0.500 × 3.500 × 4.000 box in
`m6/gazebo/warehouse_ver3.sdf`, LETHAL in the frozen grid. It is a real
object on this floor with a name — the same rack `CONTEXT.md` records
being put across the `m5_ver2` spawn pose. It carries `route_node:
false` and `repeat: 0`, and `tests/test_nav2_params.py` checks **both**
directions of that flag: every other goal must still be a node of
`m6/ipc/route.py`'s graph, and this one must still NOT be, and must
still sit inside the rack the world file puts there. A demonstration
goal that had quietly become reachable would pass every other test in
that file and demonstrate nothing.

**AND IT WAS DRIVEN, TWICE, WITH THE WATCHDOG ARMED AND DISARMED**, on
the committed configuration (`nav=on@3148d052`, `nav_config_md5
53a33d67`, tree `b7fc74a6`):

| | armed | disarmed |
|---|---|---|
| session | `goal-rack_sw3-…181552` | `goal-rack_sw3-…181633` |
| what ended it | **the bench's watchdog** | **the tree's own recovery, exhausted** |
| when | **t+30.03 s** | **t+90.75 s** |
| what the session says | `outcome=no_progress`, 19.0769 m from the goal, 30.02 s without closing 0.50 m on its best of 19.0769 m | `outcome=ran`, `action_status=6`, **`error_code=208`** |
| `/cmd_vel` published | **0 rows** | **0 rows** |
| `/plan` published | **0** | **0** |

**THE PLANNER REFUSED IT AND SAID SO**, four times over, in
`m5_ver3/logs/planner_server.log`:

```
[WARN] [planner_server]: GridBased plugin failed to plan from
       (-0.09, -0.11) to (-12.88, 14.06): "no valid path found"
```

**208 IS `ComputePathToPose::NO_VALID_PATH`** and it is the tree's own
answer: six retries of clear-the-costmaps-and-wait, then FAILURE, then
`bt_navigator` aborting the action. That is what §14's tricycle tree was
built to do — "if it still cannot plan, STOP AND REPORT" — and it had
never been exercised on a goal that genuinely could not be planned.

**BOTH GUARDS LAND WELL INSIDE THE 335 s BUDGET, AND THE BUDGET
THEREFORE DID NOT FIRE.** That is stated rather than presented as a
third demonstration: on this floor's failure modes the goal-relative
guard fires at 30 s and the tree's own retries at 91 s, so the tree's
budget is a BACKSTOP for a consumer that has neither — which is exactly
what it is for, and it has not been observed firing. What it is
demonstrated to do is load, arm and not interfere: every one of the
eleven arrivals in §16.5 ran under it.

**AND THE TRUCK NEVER MOVED, WHICH THE BENCH NOW REPORTS RATHER THAN
REFUSING.** Four of the nine recorded streams are empty on this session
because the controller published nothing at all. `analyse` used to
refuse a session with an empty capture — correctly, in general — and
would therefore have been unable to read the most important run this
task produced. `load()` now passes `allow_empty` for the five streams
that exist only because nav2 produced something, still refuses an empty
POSE stream by name, and `analyse_session` prints:

```
STILL     THE CONTROLLER NEVER PUBLISHED A TWIST, so every block below
          this one is absent rather than empty. 0 plan(s) were published
          and the vehicle did not move: on this track that is what a
          goal the planner REFUSES looks like from the outside.
```

**WHAT IT COST THE FAILURES ALREADY ON DISK**, had it existed:

| run | ran for | the rule fires at | saved |
|---|---|---|---|
| `…161742` | 479.7 s | t+43.4 s | **436 s** |
| `…131600` | 479.5 s | t+45.9 s | 434 s |
| `…163615` | 457.8 s | t+47.0 s | 411 s |
| `…124352` | 479.6 s | t+87.0 s | 393 s |
| `…165050` | 454.4 s | t+88.1 s | 366 s |

§15.7 item 2's 130.199 m and 459 plans are now 43 seconds and about
forty.

### 16.8 THE JUMP BUDGET, AND WHAT THE CLOSED LOOP DID TO IT

§15.6 handed over a worst single `map` -> `odom` step of **0.6490 m**
against `EVIDENCE_LOCALIZATION_V3.md` §13.10's **0.2591 m**, and called
the contract not conservative. This task owns the amendment, and it is
written where the contract lives: **`EVIDENCE_LOCALIZATION_V3.md`
§13.10a**, a labelled addendum with every F3 original intact and a
pointer at §13.10's own heading so nobody reads the contract without it.

**THE FINDING IS RIGHT AND BOTH OF ITS FIRST NUMBERS WERE WRONG, AND
THIS SECTION KEEPS THE WORKING.** It was drafted against the 30
driven-goal sessions that existed before §16.5's acceptance set, and
the acceptance set falsified two of its claims. They are struck below
rather than rewritten away, because a bound that moved and a reason that
inverted are both things a later phase needs to see happen.

Measured with `evidence_core.tf_jumps()` over **all 44 driven-goal
sessions on disk**, same arm, same map, same plant, dry:

| | §13.10, OPEN LOOP | CLOSED LOOP |
|---|---|---|
| worst single **position** step | 0.2591 m | **0.8310 m — 3.21x** |
| worst single **heading** step | 0.0764 rad | **0.0641 rad — 0.84x** |

> ~~worst single position step **0.6490 m — 2.50x**~~
> **WITHDRAWN.** That was the worst over the 30 sessions on disk when
> this section was drafted, and it is `ring_corner` `...132535`'s. The
> acceptance set added fourteen runs and the worst over all 44 is
> **0.8310 m** — `goal-aisle_end-...172610`, and 3.21x rather than
> 2.50x. Every consumer below carries the amended figure.

**THE HEADING HALF SURVIVED CONTACT AND THE POSITION HALF DID NOT.**

> ~~**AND THE STEP SIZE IS A PROPERTY OF THE CONTROLLER.** The 30
> sessions were driven behind fourteen different `nav2.yaml`s, some of
> which tracked their paths and most of which did not: all 30 ->
> 0.6490 m, the 8 that ARRIVED -> 0.4524 m, the 3 arrivals on the fixed
> controller -> 0.0841 m. A vehicle that wanders accumulates odometry
> error between AMCL updates and AMCL corrects all of it in one step;
> the worst steps belong to the worst driving.~~
> **REFUTED BY THE TABLE BELOW.** The reasoning was plausible and the
> sample was the argument's own: at 30 sessions the arrivals were all
> short `spine_north` runs, so "arrived" and "17 m route" were the same
> column and the fit was to the wrong one. §16.5's eleven arrivals
> include `ring_corner` and `aisle_end`, and the largest correction in
> the whole corpus is now on a run that ARRIVED.

| grouped by | n | worst position step |
|---|---|---|
| all 44 | 44 | **0.8310 m** |
| the 20 that ARRIVED | 20 | **0.8310 m** |
| the 24 that MISSED | 24 | 0.6490 m |
| goal `spine_north` — a 17 m route | 26 | 0.5110 m |
| goal `ring_corner` — 37 m | 8 | 0.6499 m |
| goal **`aisle_end` — 47 m** | 6 | **0.8310 m** |

**THE ROUTE SORTS IT AND THE DRIVING DOES NOT.** AMCL corrects the
odometry error accumulated since its last update, and how much that is
depends on how far the run got and which part of this floor it crossed
— so a run that fails early never reaches the far end of the east leg,
and the misses look BETTER than the arrivals rather than worse. The
median correction over the same 44 sessions is **0.0115 – 0.0933 m**,
which straddles §8's own 0.019 – 0.047 m band rather than leaving it:
what moved is the tail.

**THE THREE CONSUMERS ARE BACK-ANNOTATED AND THEIR CONCLUSIONS HOLD.**
`nav2.yaml` §(A)'s error-budget table, its `inflation_radius` lower
bound, and `tests/test_nav2_params.py`'s `WORST_MAP_ODOM_STEP_M`. The
lateral surprise those two derivations are built on — worst cross-track
0.1044 m plus the worst single step — goes from **0.3635 m to
0.9354 m**, and `inflation_radius: 2.60` clears both, with **2.8x** to
spare at the amended bound.

> ~~goes from 0.3635 m to **0.7534 m** ... clears both with 3.5x to
> spare~~
> **WITHDRAWN with the 0.6490 m it was computed from.** 0.1044 + 0.8310
> = 0.9354 m, and 2.60 / 0.9354 = 2.78. `nav2.yaml` (the section (A)
> table and the `inflation_radius` derivation) and
> `tests/test_nav2_params.py`'s `test_the_inflation_covers_the_LATERAL_surprise`
> all carry 0.9354 and assert it; this paragraph is the one that lagged
> them and it no longer does.

**No value in this tree moved because of the amendment; what moved is
the margin, and every site says so.** A test asserts the conclusion at
BOTH bounds — `WORST_MAP_ODOM_STEP_OPEN_LOOP_M` is kept beside the
amended constant for exactly that — so the next reader can see at a
glance that neither binds it.

### 16.9 What is still open, named

1. **`ring_corner` IS 2 IN 3 AND THE LOOP IS MARGINALLY STABLE THERE.**
   §16.4c. This is the residual and it is the first thing a follow-up
   takes. The mechanism behind it is NOT confirmed — what is measured is
   that the outcome is bimodal (heading swing 0.20 rad against 0.55),
   that it needs about 20 m of straight leg to develop, that the PLAN
   oscillates with the vehicle because the tree replans at 1 Hz from the
   vehicle's own heading, and that the prediction horizon is not the
   lever (rung 7, rejected). The two levers nobody has pulled are
   `PathAlignCritic.cost_weight` — 14.0 is the upstream default for a
   differential base with an order more angular authority than this
   vehicle's 0.24 rad/s — and the tree's own 1 Hz `RateController`.
   **Neither is touched here**, because this task's rule is one
   mechanism confirmed by measurement before any change, and a
   parameter changed on a hunch is what §16.2 is a story about.
2. **THE FREESPACE PLANNER AND THE ROAD GRAPH, AGAIN, AND NOW WITH A
   NUMBER.** §16.4b: the inflation gradient bows `ring_corner`'s route
   **1.2 – 1.5 m** off the geometric line for the middle of its length.
   The vehicle tracks that route to 0.02 – 0.10 m and arrives, so it
   costs nothing today — but a route that is not the road graph's is
   still not the road graph's. §15.7 item 3's answer stands: nav2's
   Route Server, and it is a whole server.
3. **THE ARRIVAL HEADING IS DELIVERED AND NOT GUARANTEED.** §16.6. The
   checker holds a position; the heading it happens to arrive with is
   0.03 rad on the headline and 0.29 rad after a corner
   (`ring_corner`, `aisle_end`), and nothing enforces either.
4. **THE ENDGAME HAS NO PATH IN IT.** Inside 1.4 m only `GoalCritic`
   acts and inside 0.5 m nothing holds the heading at all. §16.6's curve
   is the cost of that, and the cheap experiment nobody has run is
   `GoalAngleCritic.threshold_to_consider` raised from 0.5 toward 1.4 —
   which is the one lever that might make a heading-aware checker fit
   without a docking server. It is named here and NOT tried, because
   this task's bar was the arrival.
5. **THE BUDGET IN THE TREE IS A TIME BOUND AND NOT A PROGRESS BOUND**,
   and it is a WALL clock in a sim-time stack (§16.7). A per-goal
   budget needs either a monitor process or a BT port fed from the goal.
6. **THE `nav=` LABEL STILL HASHES COMMENTS, AND THE SESSION NOW SAYS
   SO.** `nav=on@<md5>` is `nav2.yaml`'s raw bytes, so a
   documentation-only edit re-labels a configuration and `analyse` then
   refuses to table a measured set beside the very file it was measured
   on. It bit §15 (`d430334b` → `6555ac39`, comments only) and it bit
   this task twice, once while a run was recording.
     **HALF OF IT IS FIXED.** `record` now writes **`nav_config_md5`**
   beside `nav_params_md5` — the same file `yaml.safe_load`ed and
   dumped canonically with sorted keys, so it moves if and only if a
   VALUE moves — plus `nav_bt_md5` and `nav_budget_ms`, because the
   `nav=` label never hashed the behaviour tree at all and this task put
   a navigation budget in it. Two sessions carrying the same
   `nav_config_md5` were driven by the same stack whatever the prose
   around it said, and `analyse` prints both and names the difference
   when they disagree.
     **THE OTHER HALF IS NOT.** `nav=on@<md5>` itself is written by
   `m5v3.sh`, which cannot canonicalise YAML in bash, so making the
   LABEL mean the configuration needs a shared helper and a change to
   the bringup path. `analyse`'s mixed-set refusal still keys on the
   byte hash. That is the ledger entry.
7. **THE 5.09 s CONTROL TICK** (§15.4), once in 21 500, still
   unexplained. Nothing in this task's 40 000-odd further commands
   reproduced it.
8. **NO WET SET, NO `--rf2o`, NO `--fuse`, NO `--localize slam` GOAL.**
   Every figure in §16 is `traction=nominal` on the default estimator
   and the shipping localiser. §13.10a's wet partner does not exist.

### 16.10 What this task did NOT do

- **It did not touch the plant, the estimator, the localiser or the
  map.** `model.sdf`, `ekf.yaml`, `amcl.yaml` and `maps/warehouse_v3/`
  are byte-identical. The `map` → `odom` amendment is a MEASUREMENT of
  AMCL, not a change to it.
- **It did not touch the command path.** F4 constraint 18 holds: the
  worst steer step on every run in §16.5 is 0.100000 rad/tick, F4 Task
  1's 2.0 rad/s ramp exactly.
- **No collision monitor, no docking, no `nav2_route`, no mid-path goal
  update** — §15.8's list is unchanged by this task.
- **It did not re-run §15's set.** §15's figures stand as F4 Task 2 took
  them; §16's are a different `nav2.yaml` and `analyse` refuses to table
  the two together, which is the label doing its job.
