# EVIDENCE — the envelope gate, measured

**Brief m5-11.** A node on the vehicle consumes the PLC-issued motion
envelope and gates commanded motion **below the velocity smoother**, so
that a dead or stale link stops the vehicle and a live envelope clamps it.
Every figure below carries the command that produced it. Sections are
filled in **as each run lands**, not at the end.

| Item | Value |
|---|---|
| Date | **2026-08-04** |
| Under test | `agv/forklift/scripts/envelope_gate.py`, its `envelope:` block in `agv/forklift/config.yaml`, `agv/forklift/launch/envelope.launch.py`, `agv/forklift/launch/navigation.launch.py` |
| Instrument | `agv/forklift/scripts/envelope_run.py` — the ROS 2 topic double **and** the recorder. **No OPC UA client, no bridge, no PLCSIM anywhere in this file** |
| Host | **the owner's WSL2 machine** (§0) |

---

## 0. Environment, and what qualifies every figure

| Item | Value |
|---|---|
| Host | **WSL2 on the owner's Windows machine** — WSL version 2.3.26.0, kernel `5.15.167.4-microsoft-standard-WSL2`, Ubuntu 24.04.4 LTS, **20 cores**, 15 GiB |
| ROS 2 | Jazzy, `rmw_fastrtps_cpp` |
| Simulator | `gz sim` **8.11.0**, headless, software rasterised |
| Smoother | `nav2_velocity_smoother` **1.3.12** — the same version `EVIDENCE_NAV2.md` measured |
| Estimator | `robot_localization` **3.8.3**, `ekf_node`, `agv/forklift/ekf.yaml` |
| Reference | `/forklift/odom` — the simulator's own pose of the model, **exact**, consumed by `envelope_run.py` only |
| Isolation | `GZ_PARTITION=m511gate` **and** `ROS_DOMAIN_ID=57`, both, always (LESSONS 2026-07-27) |
| Real-time factor | sim clock advanced **11.79 s in ~10 s wall** on an idle machine before the runs; the machine ran one simulator at a time throughout (LESSONS 2026-07-30) |

**This machine is the one the showcase runs on, and that is the point.**
`EVIDENCE_NAV2.md` and `EVIDENCE_LOCALIZATION.md` are **container**
measurements and say so; these are WSL measurements. Nothing here is
compared against a container figure as though the two environments were
one, and nothing here re-derives a container figure (LESSONS 2026-07-27).

**Two ROS 2 packages were missing on this machine and were added without a
system install.** `sim/setup/WSL_ENVIRONMENT.md` records Nav2 and the
`ros2_control` stack as **MISSING** here, and it is still accurate:
`nav2_velocity_smoother` (with `bond`, `bondcpp`, `smclib`, `nav2_common`,
`nav2_msgs`, `nav2_util`, `geographic_msgs`) and `robot_localization`
(with `diagnostic_updater` and `libgeographiclib26`) were fetched as
`.deb` files with `apt-get download` and **extracted into a user prefix**
`~/ros-overlay/prefix`, because this environment has no passwordless
`sudo`. 12 packages, ~5 MB. The versions are the archive's own and are
tabulated above. **No system package was installed, no file outside
`$HOME` was written, and no Python dependency was added to this
repository.** The report asks for `sim/setup/WSL_ENVIRONMENT.md` to record
it, since that file is outside `agv/`.

**What no figure in this file is.** Not a property of a real vehicle, not
a stopping distance a machine is certified to, and not a safety figure.
Every reaction measured here is a **degraded-mode process behaviour**
(invariant 2). No PL, SIL, Category or PFH is claimed for any of it
(ADR 0011 D5).

**Every figure carries its n.** Where an event happened once in one run,
the figure is written as an observation with **n = 1** and never as a
bound (LESSONS 2026-08-04).

## 1. The topic chain, before and after

**Verified on the running configuration rather than assumed from the
brief.** `nav2.yaml`'s `velocity_smoother` block and
`navigation.launch.py` were read, and the converter's input topic is a
launch argument (`cmd_topic`) that both files already reserve for this
node.

Before (m5-10, `EVIDENCE_NAV2.md`):

```
controller_server --/cmd_vel--> velocity_smoother --/cmd_vel_smoothed-->
    cmd_vel_to_tricycle --/forklift/cmd/{steer_angle,traction_speed}-->
        forklift_io --> gz joint commands
```

After (m5-11), one node inserted and **nothing else moved**:

```
controller_server --/cmd_vel--> velocity_smoother --/cmd_vel_smoothed-->
    ENVELOPE GATE --/cmd_vel_gated--> cmd_vel_to_tricycle
        --/forklift/cmd/*--> forklift_io --> gz joint commands
```

| Item | Before | After |
|---|---|---|
| smoother output topic | `/cmd_vel_smoothed` | unchanged |
| converter input topic | `/cmd_vel_smoothed` | **`/cmd_vel_gated`** — `navigation.launch.py`'s `cmd_topic` default changed, the converter itself untouched |
| new topics | — | `/cmd_vel_gated`, `/forklift/envelope/{motion_enable,speed_ceiling,equipment_permit}`, `/forklift/mode/{in_force,applied}`, `/forklift/vehicle/heartbeat`, `/forklift/envelope/gate_state` |
| smoother `feedback` | `CLOSED_LOOP` (nav2.yaml, m5-10) | unchanged — and §6 is the measurement of why |

**The gate is in the chain by default, not by remembering an argument.**
`navigation.launch.py` now starts the gate and points the converter at its
output; `gate:=false cmd_topic:=/cmd_vel_smoothed` restores the m5-10
chain. That is a deliberate choice of failure direction: a launch that
silently bypassed the gate would move the vehicle with no envelope at all.
**It also means `EVIDENCE_NAV2.md` §7's reproduction recipe now brings up a
gated chain and the vehicle will not move without an envelope** — the m5-11
report requests the note in that file, which is outside this brief's write
scope.

**Nothing in the chain is an OPC UA client.** The envelope arrives as the
six ROS 2 topics of `opcua-nodes.md` §12.10 and no motion value of any
granularity leaves the vehicle (ADR 0014 D1, invariant 11).

## 2. What the gate implements, and where §12 did not settle it

**The gate law**, from ADR 0014 seam (b) and `opcua-nodes.md` §12.4:

```
permissive := envelope fresh AND mode in force = Autonomous
              AND motion enable AND equipment permit AND ceiling valid
permissive      -> emit the command, clamped in MAGNITUDE to the ceiling
not permissive  -> ramp to zero at the vehicle's own decel, then hold zero
```

Every term is tested **affirmatively** with the fault in the `ELSE`
(LESSONS 2026-07-27), so a `NaN` ceiling falls to the fault branch, and a
value never received is **not fresh** rather than "not yet proven stale"
(§12.6 **V2**'s polarity, one layer out).

**The design values this layer owns**, all in `config.yaml`'s `envelope:`
block with their reasons:

| Constant | Value | Where it comes from |
|---|---|---|
| `stale_window_s` | **0.50 s** | §12.4 **E5**: "derived from the rate the bridge republishes at". That rate is **20 Hz** (§12.10), so the window is **ten publications**. It is **its own** constant, shared with no PLC- or HMI-side stale time |
| `command_timeout_s` | 0.50 s | this vehicle's own controller falling silent — a different party from the supervisor, so a different constant |
| `stop_decel_mps2` | 0.50 m/s² | the same figure `nav2.yaml` gives the smoother as `max_decel`, duplicated deliberately: the gate must ramp correctly when the smoother is not running at all. §3 checks the two against each other |
| `publish_hz` | 20.0 | matches `nav2.yaml`'s `smoothing_frequency` |
| `ceiling_max_mps` | 1.00 m/s | §12.4's plausibility window, `TRACTION_SPEED_MAX` as `plc/forklift/SPEC.md` §3.3 carries it. **A second copy of a PLC-owned datum** — carried as a bound that can only ever be more restrictive, and raised as an open question in the report rather than silently owned here |

**`stale_window_s` is a design value, not a measured one, and it is the
one number in this file that is.** **E5** says the window is derived from
the republish rate, and 20 Hz is the rate the node model *specifies*. What
nobody has measured is the **age of an envelope on the vehicle's side of a
real bridge** — ADR 0014's own open item asks for exactly that brief. The
double in this file publishes at 20 Hz with no bridge, no OPC UA session
and no PLC scan behind it, so it cannot measure that age and does not
claim to. **When that measurement exists, this window is re-derived from
it.**

**The four conservative readings**, taken where §12 specifies a datum and
not this consumer's reaction, each named in the code and each able only to
make the gate **more** restrictive:

| # | §12 says | §12 does not say | What the gate does |
|---|---|---|---|
| a | the permit is the PLC's statement that its equipment is ready to be acted on (§12.4, §12.5 **Z4**); cold start `FALSE` | what a consumer does with `FALSE` | **it is a term of the gate law**: permit `FALSE` → controlled stop. Measured in §8 |
| b | a ceiling outside `0.00…TRACTION_SPEED_MAX` "is a broken supervisor and is non-permissive to the consumer, never a bound to clamp" | — (this one §12 does settle) | non-permissive → controlled stop |
| c | a mode outside `{0,1,2}` is "a broken writer, not a mode to clamp" (§12.3) | the vehicle's reaction to one | non-permissive → controlled stop |
| d | in `Teleop` the PLC forms every setpoint and the bridge writes `/forklift/cmd/*` (§12.9 **C1**) | how the autonomous chain gets out of the way (§12.9 **C3** hands it to `agv/`) | the gate ramps to zero **first**, and only at zero **falls silent**, releasing the actuator topics. Measured in §9 |

## 3. Observation 1 — enable drops while moving

```bash
bash runscn.sh enable-drop CLOSED_LOOP r1-enable-drop
#   = warehouse_bringup x:=-4.5 y:=7.0 yaw:=0.0
#   + ros2 launch agv/forklift/launch/envelope.launch.py feedback:=CLOSED_LOOP
#   + python3 agv/forklift/scripts/envelope_run.py run \
#         --scenario enable-drop --csv r1-enable-drop.csv
```

The vehicle cruises at a commanded **0.40 m/s** on a permissive envelope
(enable `TRUE`, ceiling 0.60 m/s, permit `TRUE`, mode `Autonomous`); at
sim **t = 10.030 s** the double publishes `motion_enable = FALSE` and
publishes nothing else different. **800 state rows, 406 gated messages,
320 envelope publications** over 16.02 s.

| Measured | Value |
|---|---|
| ground speed at the enable edge | **+0.4000 m/s** |
| first **reduced** gated command | **0.0681 s** after the edge (`+0.4000 → +0.3750 m/s`) |
| first **zero** gated command | **0.8051 s** after the edge |
| mean deceleration of the emitted ramp | **0.4968 m/s²** against the gate's configured 0.50 |
| per-step deceleration, gaps ≥ 25 ms | max **0.5226**, mean **0.5090 m/s²**, n = 15 steps |
| largest single step in the emitted command | **0.0250 m/s** — exactly `0.50 m/s² × 50 ms` |
| standstill (ground truth ≤ 0.010 m/s) | **0.850 s** after the edge |
| **stop distance**, ground truth, edge → standstill | **0.1738 m** |

**Was the deceleration the smoother's limit or an abrupt zero? Neither —
it was the gate's own ramp, and the numbers say which.** An abrupt zero
would show as one step of 0.4000 m/s; the largest step measured is
**0.0250 m/s**, which is the gate's `stop_decel_mps2 × its 20 Hz period`
to the last digit, and 32 commands were emitted between the edge and zero.
The smoother is **above** the gate and is not the thing decelerating here:
it was still being handed the same 0.40 m/s command throughout. The
distance is the arithmetic of the ramp — `v²/2a = 0.16 m` plus the 68 ms
of reaction — and it came out **0.1738 m**.

**Reaction latency, n = 1.** 0.0681 s from the publication of the
non-permissive envelope to the first reduced command. It is one gate
period (50 ms) plus transport, measured once in this run; it is an
observation, not a bound.

## 4. Observation 2 — the envelope goes stale

```bash
bash runscn.sh stale CLOSED_LOOP r2-stale
#   ... envelope_run.py run --scenario stale --csv r2-stale.csv
```

Same cruise, same permissive envelope. At sim **t = 10.030 s the double
simply stops publishing.** Nothing commands a stop, nothing goes `FALSE`,
and the last envelope the gate holds still says *enable `TRUE`, ceiling
0.60, permit `TRUE`, mode Autonomous*. **This is the link dying, and it is
the failure the freshness window exists for** — a degraded mode, not a
safety event (invariant 2). **770 state rows, 614 gated messages, 191
envelope publications.**

| Measured | Value |
|---|---|
| last envelope publication | sim **t = 9.9800 s** |
| freshness window in force | **0.500 s** (`config.yaml` `envelope.stale_window_s`) |
| **detection latency**, last message → first reduced command | **0.5176 s** |
| overshoot beyond the window | **0.0176 s** — under one 50 ms gate period |
| first zero gated command | **1.2598 s** after the last message |
| the ramp alone (first reduced → zero) | 0.7422 s for 0.3770 m/s = **0.508 m/s²** against the configured 0.50 |
| standstill (ground truth ≤ 0.010 m/s) | **1.320 s** after the last message |
| **stop distance**, ground truth | **0.3715 m** |

**The latency against the design, stated the way the design is stated.**
The window is 0.500 s and detection took **0.5176 s**, n = 1: the extra
17.6 ms is the gate noticing on its own next 20 Hz tick, which is the
largest error a 20 Hz detector of a 0.5 s condition can make. The stop
distance is **2.1× the commanded-stop distance of §3**, and all of the
difference is the window: the vehicle keeps its permission for exactly as
long as the design says it may.

**The mean deceleration printed by the harness for this scenario (0.3175
m/s²) is diluted by the dead window** — it averages the 0.5 s in which the
gate was correctly still passing the command. The ramp itself is the
0.508 m/s² row above, and the largest single step emitted was **0.0230
m/s**, again the gate's own ramp and not a step to zero.

## 5. Observation 3 — the ceiling clamp

```bash
bash runscn.sh clamp CLOSED_LOOP r3-clamp
#   ... envelope_run.py run --scenario clamp --csv r3-clamp.csv
```

The command is a constant **0.60 m/s** from t = 2 s. The ceiling is
stepped **0.60 → 0.40 → 0.20 → 0.10 m/s**, each held 3 s; the first second
after each change is discarded because the smoother above is still ramping
and the comparison is about the gate. Each gated message is paired
**causally** with the smoothed message in force when it was emitted.

| ceiling [m/s] | n pairs | mean commanded (smoothed) | mean emitted (gated) | max emitted | emitted/commanded |
|---|---|---|---|---|---|
| **0.600** | 80 | 0.2760 | **0.2760** | 0.6000 | **1.0000** |
| **0.400** | 40 | 0.4270 | **0.4000** | 0.4000 | 0.9368 |
| **0.200** | 40 | 0.2258 | **0.2000** | 0.2000 | 0.8858 |
| **0.100** | 39 | 0.1254 | **0.1000** | 0.1000 | 0.7972 |

**Passed at the ceiling — not blocked, and not passed unchanged.** In the
three clamped rows the mean emitted equals the max emitted equals the
ceiling to four decimals, which means **every** paired sample was emitted
at exactly the ceiling: nothing was refused and nothing exceeded it.
`0.100 m/s` is well below the vehicle's normal cruise (0.40–0.60 m/s in
these runs, `max_velocity` 0.60 in `nav2.yaml`) and the vehicle drove at
it.

**The 0.600 row is the control, and its ratio of exactly 1.0000 is the
point:** with the ceiling at or above the command the gate passed the
command through untouched, mean for mean, and the segment's maximum
reached the full 0.6000 m/s. That row also contains the ramp-up from rest,
which is why its *mean* commanded is 0.2760 rather than 0.60 — the mean
is over the whole segment, and the emitted mean tracks it exactly.

**Why the commanded mean sits below 0.60 in the clamped rows** (0.4270 at
the 0.40 ceiling, and so on) **is the closed-loop smoother doing its
job**, not the gate: the smoother is limiting against the vehicle's
measured twist, the gate is holding the vehicle at the ceiling, so the
smoother's own output settles just above it instead of running away to
0.60. §6 measures what happens when it is *not* closed on measurement.

**The clamp preserves the arc, and that is arithmetic rather than a
measurement here.** These runs command `w = 0`, so there is no curvature
to corrupt; the scaling of both components by one factor — which is what
keeps `w/v`, and therefore the steer angle, unchanged — is checked in
`envelope_gate.py --self-check` (`over ceiling: curvature changed` is one
of its cases) and is stated in the node's own docstring.

## 6. Observation 4 — gate release, OPEN_LOOP against CLOSED_LOOP

**This is the centrepiece, and it is a measured difference, not an
argument.**

```bash
bash runscn.sh release CLOSED_LOOP r4-release-closed --speed 0.50
bash runscn.sh release OPEN_LOOP   r5-release-open   --speed 0.50
#   ... envelope_run.py run --scenario release --csv <tag>.csv --speed 0.50
```

Both runs are identical in every respect but one: the smoother's
`feedback` parameter. The gate is **closed** from the start (`enable
FALSE`), a constant **0.50 m/s** is commanded into the smoother from
t = 2 s, and the vehicle stands still for eight seconds while the smoother
does whatever its feedback setting makes it do. At **t = 10.030 s** the
double publishes `motion_enable = TRUE`.

| Measured at the release | `CLOSED_LOOP` (nav2.yaml, ADR 0014) | `OPEN_LOOP` (nav2's default) |
|---|---|---|
| smoother output the instant before release | **+0.0250 m/s** | **+0.5000 m/s** |
| gated command just before | +0.0000 | +0.0000 |
| gated command just after | **+0.0250** | **+0.5000** |
| **step in the commanded velocity** | **+0.0250 m/s** | **+0.5000 m/s** — **20×** |
| peak ground-truth acceleration, 100 ms window | **0.4096 m/s²** | **3.5249 m/s²** — **8.6×**, and **7.0× the 0.50 m/s² the whole chain is dimensioned to** |
| ground speed 0.5 s after release | 0.1230 m/s | 0.5000 m/s |
| ground speed 1.0 s after release | 0.2512 m/s | 0.5000 m/s |
| time to reach 0.45 m/s | 1.790 s | **0.190 s** |

The emitted commands, straight out of the two recordings:

```
CLOSED_LOOP                          OPEN_LOOP
t=10.0403  v=+0.0000                 t=10.0148  v=+0.0000
t=10.0733  v=+0.0250   <- release    t=10.0601  v=+0.5000   <- release
t=10.0894  v=+0.0250                 t=10.0645  v=+0.5000
t=10.1395  v=+0.0376                 t=10.1148  v=+0.5000
t=10.1894  v=+0.0504                 t=10.1647  v=+0.5000
t=10.2396  v=+0.0633                 t=10.2146  v=+0.5000
```

**The mechanism, confirmed by the numbers rather than described from the
brief.** With `OPEN_LOOP` the smoother limits acceleration against **its
own last command**, so during the eight seconds the gate held the vehicle
at zero it ramped its internal command all the way to the full 0.50 m/s
and sat there. The gate's job is to withhold, not to tell the smoother
anything, so the smoother never learned that nothing was moving. At
release the gate did exactly what it is specified to do — pass the
command through — and the command it was handed was already at cruise. The
result is a **0.5000 m/s step into a standstill** and **3.52 m/s²** of
ground-truth acceleration, on a vehicle whose chain is dimensioned for
0.50 m/s².

With `CLOSED_LOOP` the smoother limits against the EKF's **measured**
twist. The vehicle was at rest, so the smoother's own output was at rest
too — 0.0250 m/s, one 20 Hz step of its 0.50 m/s² limit — and the release
produced a step of exactly that: **the ramp starts from where the vehicle
is**.

**The lurch reported here is the lurch measured, and it is visible in
three independent places**: the emitted command (0.0250 against 0.5000),
the ground-truth acceleration (0.4096 against 3.5249 m/s²), and the time
to reach 0.45 m/s (1.790 s against 0.190 s). Each is **n = 1 event in one
run per configuration**; the difference between the configurations is
large enough that it is not a jitter figure, but the *values* are single
observations and not bounds.

**What this measurement justifies.** `nav2.yaml`'s `feedback:
"CLOSED_LOOP"` is not a preference: with a gate below the smoother,
`OPEN_LOOP` makes gate release a step. ADR 0014 seam (b) and
`opcua-nodes.md` §12.4 **E4** both specify closed loop, and this is the
number behind them.

## 7. Observation 5 — pass-through fidelity

```bash
bash runscn.sh passthrough CLOSED_LOOP r6-passthrough
#   ... envelope_run.py run --scenario passthrough --csv r6-passthrough.csv
```

A permissive envelope with the ceiling at **1.00 m/s** — the top of its
plausibility window, well above anything commanded — and a command that is
**never constant**: `v = 0.20 + 0.06 sin(2πt/5)`, `w = 0.05 sin(2πt/3)`.
A gate that rounded, quantised, held or re-published a stale value would
show up as a residual; a constant command would hide all four.

| Measured | Value |
|---|---|
| causally matched pairs (smoothed → gated) | **n = 221** |
| `max abs(gated_v − smoothed_v)` | **0.000e+00 m/s** |
| `max abs(gated_w − smoothed_w)` | **0** |
| exact matches | **221 of 221** |
| gate latency, smoothed message → gated message | max **0.0010 s**, mean **0.0004 s** |
| command range actually exercised | v ∈ [0.000, 0.2610] m/s, w ∈ [−0.0500, +0.0500] rad/s |

**The residual is zero, exactly, on both components, for every pair.**
That is a property of the design rather than a lucky rounding: while
passing, the gate emits the floats it received, and the ceiling comparison
is `speed <= ceiling`, which returns the input untouched rather than
multiplying it by a factor of 1.0.

**The latency the gate adds is 0.4 ms mean, 1.0 ms worst of 221.** The
gate emits on the command's own callback while passing and reserves its
20 Hz timer for the ramp and the held zero, so the permissive path is not
delayed by up to a period — which is what a timer-only design would have
cost.

## 8. Observation 6 — the fixed-equipment / station permit

**§12 specifies the datum and not the consumer's reaction to it, so the
conservative reading was implemented and is shown happening.**
`opcua-nodes.md` §12.4 defines `ForkliftEquipmentPermit` as the PLC's
statement that the equipment it owns is ready to be acted on; §12.5 **Z4**
records that at M5 its term set is empty; neither says what the vehicle's
control layer does when it reads `FALSE`. The gate makes it a **term of
the gate law** — permit `FALSE` is non-permissive and produces the same
controlled stop as enable `FALSE` — because the alternative reading has
the vehicle driving under a supervisor that has stated no readiness, and
the node's cold start is `FALSE` precisely because an unstated readiness
is not a granted one. **This is raised as the open question in the m5-11
report.**

```bash
bash runscn.sh permit-drop CLOSED_LOOP r7-permit-drop
#   ... envelope_run.py run --scenario permit-drop --csv r7-permit-drop.csv
```

Identical to §3 except that at t = 10.030 s it is the **permit**, not the
enable, that goes `FALSE`; the enable stays `TRUE` throughout.

| Measured | permit `FALSE` (this run) | enable `FALSE` (§3) |
|---|---|---|
| ground speed at the event | +0.4000 m/s | +0.4000 m/s |
| first reduced gated command | **0.0609 s** | 0.0681 s |
| first zero gated command | **0.7961 s** | 0.8051 s |
| mean decel of the emitted ramp | **0.5024 m/s²** | 0.4968 m/s² |
| standstill (ground truth ≤ 0.010 m/s) | **0.830 s** | 0.850 s |
| **stop distance**, ground truth | **0.1735 m** | 0.1738 m |

**The two reactions are the same reaction, and the numbers say so**: the
stop distances differ by **0.3 mm** across the two runs. That is the
intended result of making the permit a term of one gate law rather than a
second stop path — §12.7 **PS6**'s "a second path to stop the vehicle
would be a second owner of the reaction", applied one term over.

## 9. The readback, the source handover, and the defect the run found

ADR 0014 **D5.3** requires the gate's evidence to **exercise** the two
`Forklift/Vehicle/` report values rather than mention them, so that
*"checked"* is a demonstrated check. `opcua-nodes.md` §12.9 **C3** leaves
the arbitration between the two command sources, and the handover without
a step, to this layer. One scenario covers both.

```bash
bash runscn.sh mode CLOSED_LOOP r9-mode-fixed
#   ... envelope_run.py run --scenario mode --csv r9-mode-fixed.csv
```

The vehicle cruises at 0.40 m/s in `Autonomous`; at t = 8.03 s the mode in
force becomes **`Teleop`**, at t = 12.03 s it returns to **`Autonomous`**.

| sim t [s] | mode in force | **mode applied** (readback) | gate state | gated v | `/forklift/cmd/traction_speed` |
|---|---|---|---|---|---|
| 0.101 | 2 | *(nothing published yet)* | — | +0.0000 | +0.0000 |
| 1.700 | 2 | **0** None | HOLD_ZERO | +0.0000 | +0.0000 |
| 1.760 | 2 | **2** Autonomous | PASSING | +0.0000 | +0.0000 |
| 8.045 | **1** | 2 | PASSING | +0.4000 | +0.4000 |
| 8.100 | 1 | 2 | **STOPPING** | +0.3660 | +0.3660 |
| 8.840 | 1 | **1** Teleop | **SILENT** | **+0.0000** | **+0.0000** |
| 12.043 | **2** | 1 | SILENT | +0.0000 | +0.0000 |
| 12.100 | 2 | **2** | PASSING | +0.0250 | +0.0250 |

| Measured | Value |
|---|---|
| first zero gated command after the mode change | **0.7922 s** — the same controlled ramp as §3, not a step |
| last message before the silence | `t = 8.8222 s, v = +0.0000` |
| length of the silence on `/cmd_vel_gated` | **3.264 s** |
| **distance travelled during the silence** | **0.00000 m**, max abs ground speed **0.00000 m/s** |
| heartbeat | **325 monotonic increments** over the run, wrapping arithmetic at 65536 |
| mode applied on re-entry | 1 → 2 within **57 ms** of the mode returning |

**The readback follows the adopt window, not the request.** `mode applied`
stays `2` for the whole 0.79 s in which the gate is still winding the
autonomous law down, and only becomes `1` when the gate has actually
reached zero and released the topics. A readback that echoed the
commanded mode the instant it arrived would report a state the machine had
not reached — the defect LESSONS 2026-07-31 records one layer up. The
same rule is why `mode applied` is `0` (None) at t = 1.700 s: the gate had
seen the mode but had not yet applied anything.

### The defect this scenario found, and it was a moving vehicle

**The first version of this node released the actuator topics one message
too early, and the vehicle crept.** Recording `r8-mode` (the same
scenario, the same commands) shows the gate entering `SILENT` at the
**last step of its own ramp** rather than after a zero:

| Run | last gated value before the silence | ground speed through the silence | distance |
|---|---|---|---|
| `r8-mode`, before the fix | **+0.0250 m/s** | **0.0250 m/s, held** | **0.0852 m in 3.3 s** |
| `r9-mode-fixed`, after | **+0.0000 m/s** | 0.00000 m/s | **0.00000 m** |

The mechanism is exactly the one the node's own docstring warns about, one
message off: `forklift_io.py` republishes its held command at 20 Hz, so
the last value the converter ever emitted stands forever. The ramp's final
step is small, nonzero, and looks like a stopped vehicle in every log —
the vehicle would have crept at 25 mm/s until something else wrote the
topic. The fix is a guard, `zero_published`, that makes the release **one
message late by construction**: the gate falls silent only after an
explicit zero has gone out.

**It was found by measuring the ground truth through the silence, not by
reading the code**, and it is recorded here rather than quietly repaired
because it is the general lesson: *a state whose whole purpose is to stop
publishing must publish its terminal value before it stops.*

## 10. The gate in the deployed chain, under a real Nav2 goal

§3–§9 drive the smoother from a scripted command, because the six
observations need a known input. **This section is the other half: the
full stack, a real goal, the gate where `navigation.launch.py` now puts
it.**

```bash
bash rungoal.sh r12-goal-gated
#   = warehouse_bringup x:=-4.5 y:=7.0 yaw:=0.0
#   + ros2 launch agv/forklift/launch/localization.launch.py \
#         initial_pose_x:=1.584770 initial_pose_y:=12.576859 \
#         initial_pose_yaw:=-0.007915
#   + ros2 launch agv/forklift/launch/navigation.launch.py     (gate default true)
#   + envelope_run.py run --scenario supervise --drop-at 12.0  (envelope ONLY;
#         Nav2's controller_server owns /cmd_vel in this run)
#   + nav2_run.py goal --x 1.0 --y 7.0 --yaw 0.0
```

The route is `EVIDENCE_NAV2.md` §5.1's straight aisle traverse. The
envelope is permissive when the goal is accepted, and the enable drops
**12 s into the recording, while the vehicle is following the plan**.

| Measured | Value |
|---|---|
| goal | **ACCEPTED**, planner and controller running through the gate |
| ground speed at the enable edge | **+0.4370 m/s** — Nav2's own commanded cruise, not this harness's |
| first reduced gated command | **0.0393 s** after the edge |
| first zero gated command | **0.9202 s** after the edge |
| mean decel of the emitted ramp | **0.4926 m/s²** (gate set to 0.50) |
| standstill | **0.930 s** after the edge, **0.2187 m** travelled |
| what Nav2 then did | **ABORTED, error code 105**, after 235.46 s of simulated time and **217 published plans** |
| final position | world (−3.8918, +7.0097) — it stayed where the gate stopped it |

**The gate stopped a vehicle that Nav2 was actively steering, and Nav2
kept trying to steer it for another four minutes before giving up.** That
is not a defect and it is not a surprise: it is the consequence **ADR 0011
D3 named in its own rationale** — a gate-zeroed command aborts the goal
through Nav2's progress checker — observed here rather than quoted. The
gate tells Nav2 nothing, by design: it is not in the navigation stack's
feedback path, and the envelope is a permission the *vehicle's control
layer* consumes, not a message to a planner.

**What that leaves open, and it is a real one for M6**: with the envelope
withheld for a long time the goal is lost, so something has to decide what
happens next — re-issue the goal when the envelope returns, or treat the
abort as the fleet manager's business. **That is order-level behaviour and
is not this node's**; it is raised in the m5-11 report.

**The stop itself is the same stop as §3**, taken in a completely
different context (Nav2's command, a curving approach, a different speed),
which is the closest thing here to a repeat under varied conditions:

| Run | context | speed at the edge | stop distance | mean ramp decel |
|---|---|---|---|---|
| `r1-enable-drop` | scripted 0.40 m/s | +0.4000 | 0.1738 m | 0.4968 m/s² |
| `r13-enable-drop-repeat` | same, repeated after the §9 fix | +0.4000 | **0.1719 m** | 0.4947 m/s² |
| `r7-permit-drop` | permit instead of enable | +0.4000 | 0.1735 m | 0.5024 m/s² |
| `r12-goal-gated` | **Nav2's own command** | +0.4370 | **0.2187 m** | 0.4926 m/s² |

**n = 4 controlled stops, in three contexts.** The three at 0.40 m/s land
within **1.9 mm** of each other; the fourth is at a 9 % higher speed and a
proportionally longer distance. The deceleration is the gate's configured
0.50 m/s² in all four (0.4926–0.5024). **This is still not a stopping
distance the machine may be characterised by** — it is four observations
in one simulator on one host, at one speed and a bit.

## 11. What this evidence does not establish, and what it asks for

**1. It does not measure the envelope's real age.** The double publishes
at 20 Hz with **no bridge, no OPC UA session and no PLC scan** behind it.
`stale_window_s = 0.50 s` is therefore derived from the *specified*
republish rate, not from a measured age. **ADR 0014's own open item** asks
for a brief that measures PLC-write-to-topic age and jitter; when it
lands, this constant is re-derived from it and §4's overshoot is re-read
against the new window.

**2. It establishes nothing about the PLC side.** No envelope was formed
by a program, no node was written, and no `Forklift/Vehicle/` node was
read back **through the bridge**. `/forklift/mode/applied` and
`/forklift/vehicle/heartbeat` are published and exercised (§9), which is
the vehicle's half of ADR 0014 D5.3; the other half needs the bridge to
carry them and `plc/forklift/SPEC.md` to consume them. The bridge's signal
map does not yet carry this group (`opcua-nodes.md` §12.13 item 1).

**3. It is not a safety demonstration and contains no safety figure.**
Every reaction here is process behaviour in a degraded mode (invariant 2).
The onboard safety chain appears nowhere in this file, by construction.

**4. Four conservative readings are implemented, not ratified** (§2). The
permit's motion effect, the reaction to an invalid mode, the reaction to
an out-of-window ceiling and the teleop release are this layer's readings
of a document that specifies the data and not the reactions. Each is
listed in the m5-11 report as an open question for `docs/interfaces/`.

**5. The ceiling's plausibility bound is a second copy of a PLC constant.**
`envelope.ceiling_max_mps = 1.00` mirrors `TRACTION_SPEED_MAX`. One datum,
two files, which invariant 10 does not admit; it is carried as a bound
that can only be more restrictive and is raised in the report.

**6. `navigation.launch.py`'s new default changes `EVIDENCE_NAV2.md` §7's
recipe.** That file is outside this brief's write scope and the note is
requested in the report; the argument pair is `gate:=false
cmd_topic:=/cmd_vel_smoothed`.

**7. Nav2 and `robot_localization` are not installed on this machine.**
They were extracted into a user prefix (§0). `sim/setup/WSL_ENVIRONMENT.md`
still records them as MISSING, correctly, and the report asks for the note.
Two ABI collisions had to be resolved to get the full stack up — the
archive's `nav2_msgs` typesupport needed the archive's `fastcdr` /
`fastrtps` beside the system's older ones, and `nav2_smac_planner` and
`nav2_map_server` needed `libompl.so.18` and GraphicsMagick. **A system
`apt` upgrade of the ROS install would remove that layering**, and that is
the owner's call, not this brief's.

**8. Nothing here says what happens to a goal that was aborted while the
envelope was withheld** (§10). Order-level behaviour, not the gate's.

## 12. How to reproduce

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<unique>     # BOTH, always

# the arithmetic, with no ROS and no simulator
python3 agv/forklift/scripts/envelope_gate.py --self-check

# --- the six observations: bringup + the gate's own stack + one scenario ---
ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
ros2 launch agv/forklift/launch/envelope.launch.py feedback:=CLOSED_LOOP
python3 agv/forklift/scripts/envelope_run.py run \
    --scenario enable-drop --csv <tag>.csv          # section 3
#   --scenario stale                                 # section 4
#   --scenario clamp                                 # section 5
#   --scenario release --speed 0.50                  # section 6, run TWICE:
#       ros2 launch ... envelope.launch.py feedback:=OPEN_LOOP for the second
#   --scenario passthrough                           # section 7
#   --scenario permit-drop                           # section 8
#   --scenario mode                                  # section 9

# re-score a recording without re-running it
python3 agv/forklift/scripts/envelope_run.py analyse \
    --scenario enable-drop --csv <tag>.csv

# --- section 10: the deployed chain, four terminals plus the goal ---
ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
ros2 launch agv/forklift/launch/localization.launch.py \
    initial_pose_x:=1.584770 initial_pose_y:=12.576859 \
    initial_pose_yaw:=-0.007915
ros2 launch agv/forklift/launch/navigation.launch.py
python3 agv/forklift/scripts/envelope_run.py run \
    --scenario supervise --csv <tag>.csv --drop-at 12.0 --duration 45.0 &
python3 agv/forklift/scripts/nav2_run.py goal --x 1.0 --y 7.0 --yaw 0.0 \
    --csv <tag>.nav2.csv --plan <tag>.nav2.json
```

**One recording per run, and the tag is unique per run.** The harness
truncates what it is pointed at; sharing a path across runs is how a day's
data was lost once already (LESSONS 2026-07-28, and `EVIDENCE_NAV2.md`
§5.1 met it again).

### Run inventory, and which build each run used

The §9 defect was found **after** the first seven runs and fixed in the
gate. The fix touches **only** the transition into `SILENT`, which is
reachable only when the mode in force is `Teleop` — a state no run before
`r8-mode` entered. `r13-enable-drop-repeat` re-ran §3's scenario on the
fixed build and reproduced it (0.1719 m against 0.1738 m), which is the
check that the fix changed nothing else.

| Run | Section | Build | Result |
|---|---|---|---|
| `r1-enable-drop` | §3 | pre-fix | stop in 0.850 s / 0.1738 m |
| `r2-stale` | §4 | pre-fix | detected in 0.5176 s against a 0.500 s window |
| `r3-clamp` | §5 | pre-fix | emitted at the ceiling at all four values |
| `r4-release-closed` | §6 | pre-fix | step +0.0250 m/s, peak 0.4096 m/s² |
| `r5-release-open` | §6 | pre-fix | step +0.5000 m/s, peak 3.5249 m/s² |
| `r6-passthrough` | §7 | pre-fix | residual 0.000e+00 over 221 pairs |
| `r7-permit-drop` | §8 | pre-fix | stop in 0.830 s / 0.1735 m |
| `r8-mode` | §9 | pre-fix | **the defect**: 0.0852 m of creep during the silence |
| `r9-mode-fixed` | §9 | **fixed** | 0.00000 m, release after an explicit zero |
| `r12-goal-gated` | §10 | fixed | Nav2 goal accepted, gated stop, goal ABORTED 105 |
| `r13-enable-drop-repeat` | §12 | fixed | §3 reproduced: 0.850 s / 0.1719 m |

`r10` and `r11` are not in the table because they measured nothing: the
Nav2 stack failed to start on missing system libraries (§11 item 7) and
both were re-run as `r12`.

**The recordings are committed**, in `agv/forklift/evidence/` under the
prefix `m5-11-`, four files per run — the 50 Hz state CSV, the gated
messages, the envelope publications and the smoothed messages — plus each
run's printed result. Recordings over 100 kB are gzipped, the convention
the `m5-07e` files already set here. Every figure in this document is
printed by `envelope_run.py analyse`, which re-derives it from them:

```bash
python3 agv/forklift/scripts/envelope_run.py analyse \
    --scenario stale --csv agv/forklift/evidence/m5-11-r2-stale.csv
```

**The gzipped recordings must be gunzipped before `analyse` reads them**,
and the writer was stopped before anything was copied (LESSONS
2026-07-28): every run's processes were killed by the driver before its
files were touched, so no archive here is a snapshot of an open stream.
