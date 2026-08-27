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
     **AND IT IS NOT THE TRACKING AND NOT THE LOCALISER.** `…131222`
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
   TRACKING.** One goal in five arrived; the controller held 20.0 Hz and
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
4. **A freespace planner is not the road graph, measured.** §15.2's
   ladder and §15.5. Any case whose route crosses the rack block is a
   case about that finding rather than about the controller.
5. **The `nav=on@<md5>` label is live and `analyse` refuses across it.**
   Five different `nav2.yaml`s were refused into one table during this
   task; a case set that retunes anything has to re-record.
6. **`consider_footprint: true` on the CostCritic**, and the 43.66 % of
   a core the arm costs idle. A case that adds critics starts there.
7. **THE JUMP BUDGET DID NOT SURVIVE CONTACT.** §15.6: the worst single
   `map` → `odom` correction under a closed loop was **0.6490 m**
   against the **0.2591 m** `EVIDENCE_LOCALIZATION_V3.md` §13.10 handed
   over. The heading steps stayed well inside. A phase that sizes
   anything on that contract should size it on 0.65 m.
