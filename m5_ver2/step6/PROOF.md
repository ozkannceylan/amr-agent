# Step 6 — proof ledger

The inherited system's evidence lives in `m5_ver2/step5/PROOF.md` and is
step5's, not step6's. This file fills as step6's own gates run (see the
M6.1 spec's proof gates).

```
[x] Gate 1 — two vehicles fit inside real time on this machine
[ ] Gate 2 — cross-isolation, both directions            NOT RUN
[ ] Gate 3 — simultaneous autonomy                       NOT RUN
[~] Gate 4 — per-vehicle stale-link: silence half MEASURED,
                                     driving half NOT RUN
[x] Gate 5 — clean lifecycle, twice
[ ] Gate 6 — the gate debt proven closed on the floor     NOT RUN
```

**NOT RUN means nothing was measured.** Gates 2, 3, 6 and Gate 4's
driving half need the two Windows writers and a hand on two joysticks;
no agent may open the owner's panels, so this build did not run them and
does not guess at them. Each one has a numbered runbook at the foot of
this file. Everything ticked or half-ticked above was measured on this
machine, with the output kept.

---

## [x] Gate 1 — RTF with two vehicles

**Date:** 2026-08-20. **Verdict: GO** — worst measured two-vehicle mean
RTF **0.934**, best **0.995**, gate **0.90**.

### What was measured

`m5_ver2/step6/tools/rtf_spike.sh`, server-only: `gz sim -s -r
--headless-rendering` on `gazebo/warehouse_ver2.sdf`, no ROS stack, no
bridge, no writers, no GUI. It spawns `vehicles/f1/model.sdf` through
`/world/warehouse/create`, samples the real-time factor for 30 s, then
spawns `vehicles/f2/model.sdf` and samples for 60 s. Both models are the
Task 3 derivations, each carrying **three microScan3 safety scanners plus
one nav lidar** — four `gpu_lidar` sensors at 10 Hz per vehicle, eight in
the two-vehicle case, all rendered in software.

Both phases run on ONE server process, so the pair is a clean A/B: same
load order, same page cache, same render context. The physics step is the
world's 2 ms at 500 Hz.

```
wsl -e bash -lc "bash /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6/tools/rtf_spike.sh"
```

### Machine

```
kernel      5.15.167.4-microsoft-standard-WSL2
cpu         13th Gen Intel(R) Core(TM) i9-13900H, 20 threads
memory      15 GiB
gz sim      8.11.0
renderer    llvmpipe (LLVM 20.1.2, 256 bits), Mesa 25.2.8, Accelerated: no
```

The renderer is the point: `glxinfo -B` reports `Device: llvmpipe (LLVM
20.1.2, 256 bits)` / `Accelerated: no`, gz's own `~/.gz/rendering/ogre2.log`
reports `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)`, and every headless
server run prints `libEGL warning: NEEDS EXTENSION: falling back to
kms_swrast`. Eight `gpu_lidar` sensors are being rasterised on the CPU.

### The three runs, verbatim

Run 3 (2026-08-20T23:26:15+02:00), the cleanest, in full:

```
=== step6 RTF spike ===
date        2026-08-20T23:26:15+02:00
gz sim      8.11.0
partition   step6-rtf-spike
world       /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6/gazebo/warehouse_ver2.sdf
cpu         13th Gen Intel(R) Core(TM) i9-13900H, 20 threads
kernel      5.15.167.4-microsoft-standard-WSL2
spawning f1 at (-3.00, -5.50, 0.05) yaw 0.0
  f1 rests at:
  - Pose [ XYZ (m) ] [ RPY (rad) ]:
    [-3.000000 -5.500000 -0.000001]
    [0.000000 0.000000 0.000000]
sampling /world/warehouse/stats for 30s (one-vehicle)...
one-vehicle samples  296  mean RTF 0.999  min 0.944  max 1.061
spawning f2 at (3.00, -5.50, 0.05) yaw 3.14159
  f2 rests at:
  - Pose [ XYZ (m) ] [ RPY (rad) ]:
    [3.000000 -5.500000 -0.000001]
    [0.000000 0.000000 3.141590]
sampling /world/warehouse/stats for 60s (two-vehicle)...
two-vehicle samples  592  mean RTF 0.995  min 0.201  max 1.830
--- gate 1: two-vehicle mean RTF vs 0.90 ---
one vehicle  0.999
two vehicles 0.995
VERDICT: GO (0.995 >= 0.90)
```

Runs 1 and 2, same script, same machine, same day:

```
run 1  23:20:15  one-vehicle samples  295  mean RTF 0.994  min 0.207  max 1.249
run 1  23:20:15  two-vehicle samples  591  mean RTF 0.934  min 0.176  max 2.064
run 1            VERDICT: GO (0.934 >= 0.90)
run 2  23:22:33  one-vehicle samples  295  mean RTF 0.976  min 0.089  max 1.726
run 2  23:22:33  two-vehicle samples  592  mean RTF 0.983  min 0.254  max 1.403
run 2            VERDICT: GO (0.983 >= 0.90)
```

| Run | 1 vehicle, 30 s | 2 vehicles, 60 s | Verdict |
|---|---|---|---|
| 1 (cold) | 0.994 (295 samples) | **0.934** (591 samples) | GO |
| 2 | 0.976 (295 samples) | 0.983 (592 samples) | GO |
| 3 | 0.999 (296 samples) | 0.995 (592 samples) | GO |

Three runs were taken because run 1 landed 0.034 above the gate and one
sample of a noisy quantity is not a measurement. It is now clear that the
spread is HOST SCHEDULING NOISE and not the cost of the second vehicle: in
run 2 the two-vehicle mean (0.983) came out ABOVE the one-vehicle mean
(0.976), which a real per-vehicle cost cannot do. Run 1's 0.934 was the
cold-cache first run of the session, and it is quoted as the floor because
it is the worst thing this gate has seen — not because it is typical.

The per-10-s breakdown of run 1's two-vehicle phase shows the same thing:
`0.985, 0.937, 0.952, 0.838, 0.985, 0.903` — a dip and a full recovery
inside one 60 s window, not a decay. Step5's single-vehicle headless
baseline of 0.998 is reproduced here at 0.999 (run 3), so the harness
measures what step5's measured.

### Both trucks are where the table put them

`data: true` from the entity factory says the request was accepted, not
that the truck is upright and clear of geometry. The script reads the
resting pose back after each spawn. Both settle from the spawn z of 0.05
to floor level with zero roll and zero pitch, at exactly the coordinates
`ipc/status_contract.py`'s VEHICLES table declares:

| Vehicle | Table spawn | Resting pose (XYZ / RPY) |
|---|---|---|
| f1 | (-3.00, -5.50, 0.05) yaw 0.0 | (-3.000000, -5.500000, -0.000001) / (0, 0, 0.000000) |
| f2 | (3.00, -5.50, 0.05) yaw 3.14159 | (3.000000, -5.500000, -0.000001) / (0, 0, 3.141590) |

No spawn was refused, nothing tipped, nothing sank, and the two trucks sit
6.00 m apart in the open south block. **The VEHICLES table needed no
change.**

### `gz stats` does not exist on this Gazebo, and that matters

The plan's spike sampled `gz stats` and averaged its `Factor[0.99]` lines.
That is Gazebo CLASSIC's command. gz-tools for Harmonic — this tree runs
gz-sim **8.11.0** — has no `stats` verb: `gz stats` prints the general help
listing `fuel gui log model msg param plugin sdf service sim topic` and
exits 0, so an awk looking for `Factor` finds nothing and the gate reports
`NO SAMPLES` against a perfectly healthy simulator.

The real source is `gz.msgs.WorldStatistics` on `/world/warehouse/stats`,
published at 10 Hz, printed by `gz topic -e` as protobuf debug text:

```
sim_time {
  sec: 8
  nsec: 74000000
}
real_time {
  sec: 9
  nsec: 753109255
}
iterations: 4037
real_time_factor: 0.99857503342729925
step_size {
  nsec: 2000000
}
```

`rtf_spike.sh` sums the `real_time_factor:` field of those messages. The
sample counts above are the arithmetic proof that it reads them: 30 s at
10 Hz is 295-296 messages and 60 s is 591-592, which is the topic's rate,
not a number anything could have invented. `stdbuf -oL` is in the pipeline
because `gz topic -e` block-buffers into a file and `timeout` ends it with
SIGTERM, which would otherwise discard the last unflushed block.

### Verdict

**GO (0.934 >= 0.90).** Two forklifts, eight software-rendered lidars,
2 ms physics: this machine carries them inside real time with the worst
observed margin at 3.8 % and the typical margin near 10 %. Task 5 may
proceed.

The margin is honest but it is not large, and everything measured here was
measured with **no ROS stack running**. The two-vehicle stack adds two
bridges, fourteen vehicle nodes and two HMIs on the same 20 threads; that
load is not in this number and is not gated by it.

---

## Full-stack RTF — recorded beside Gate 1, gated by nothing

Gate 1's numbers are **server-only**: `gz sim -s` and two models, no ROS.
The sentence above ends by naming what that leaves unmeasured, so it was
measured. On 2026-08-21, with the whole 17-pid stack up headless (the run
recorded under Gate 5 below), `/world/warehouse/stats` was sampled twice
for 60 s each, by the same method `tools/rtf_spike.sh` uses — `stdbuf -oL
gz topic -e -t /world/warehouse/stats` under `GZ_PARTITION=step6`, summing
the `real_time_factor:` field:

| Sample | Start | Samples | Mean RTF | Min | Max |
|---|---|---|---|---|---|
| A | 08:32:51+02:00 | 577 | **0.755** | 0.030 | 1.872 |
| B | 08:34:01+02:00 | 574 | **0.734** | 0.034 | 1.886 |

Per-10 s, the two runs:

```
A   0.815, 0.799, 0.592, 0.681, 0.818, 0.845
B   0.795, 0.754, 0.553, 0.783, 0.777, 0.742
```

**This is evidence, not a verdict.** Gate 1 is a spike gate on the
simulator and it passed on its own terms; nothing in the spec gates the
number above, and no design decision is being taken from it here.

What it says: **the ROS stack costs roughly a quarter of real time.**
Server-only ran 0.934-0.995 across three runs; the same world under two
bridged vehicles, fourteen vehicle nodes, two HMIs and one bridge process
runs 0.73-0.76 — consistent across both samples and across all twelve
10-second buckets (0.553 worst, 0.845 best), so this is a LOAD FLOOR and
not the scheduling noise Gate 1 diagnosed in its own spread.

Two things follow, and both are for M6.2 rather than for this copy:

- **A 0.75 RTF does not break the 20 ms loops** — every loop in the tree
  is wall-clock timed (`rclpy` timers, `time.monotonic()` staleness), so
  they run at their real rates regardless; what stretches is *simulated*
  time per wall second. It does mean a demo run takes ~33 % longer than
  the sim clock suggests, and that any future gate written in sim seconds
  has to say which clock it means.
- **The margin to a third vehicle is now the interesting number.** Gate 1
  measured the simulator's headroom; this measures the machine's. Nothing
  here was run with the two Windows writers attached, which add two more
  processes and two UDP streams at 50 Hz.

No writer was running for either sample. Both were taken on the machine
Gate 1 names above.

---

## The live stack, 2026-08-21 — what came up

Everything below (Gate 4's silence half, Gate 5, the full-stack RTF) was
measured on this one stack, WSL-side only, **no Windows writers**. That is
not a shortcut: an agent may not open the owner's panels, and the
no-writer state is exactly what the fail-safe gates need.

```
$ ./step6.sh deploy
instantiated /mnt/c/.../m5_ver2/step6/vehicles/f1
instantiated /mnt/c/.../m5_ver2/step6/vehicles/f2
deployed 17 files to /mnt/c/.../m5_ver2/step6/deploy

$ ./step6.sh start --headless
starting the Step 6 vehicle side (partition step6, domain 96, gui false)
  world pid 18299
  plc_link_f1 pid 18673      plc_link_f2 pid 18910
  cmd_gate_f1 pid 18679      cmd_gate_f2 pid 18925
  cmd_mux_f1 pid 18687       cmd_mux_f2 pid 18971
  field_eval_f1 pid 18733    field_eval_f2 pid 19001
  encoder_link_f1 pid 18763  encoder_link_f2 pid 19047
  sensor_link_f1 pid 18780   sensor_link_f2 pid 19078
  nav_node_f1 pid 18828      nav_node_f2 pid 19103
  hmi_f1 pid 18855           hmi_f2 pid 19132

up. On Windows, one writer per vehicle:
  python m5_ver2\step6\windows\step6.py --vehicle f1 --virtual
  python m5_ver2\step6\windows\step6.py --vehicle f2 --virtual
```

(The two columns are one column in the real output, f1's eight then f2's
eight; they are folded here to fit.) **Seventeen pids, one world and two
full vehicle sets.** No `WARNING: <name> exited during startup`, no `THE
STACK IS INCOMPLETE.` — and those lines are not decorative: `start`
re-reads every recorded pid a second after the last spawn and prints one
per dead child. Seventeen silent lines is seventeen live processes.

### Two namespaces, mirrored, and no `/forklift/` anything

`ros2 topic list` under `ROS_DOMAIN_ID=96` returns **65** names: 31 under
`/f1/`, the same 31 under `/f2/`, and `/clock`, `/parameter_events`,
`/rosout`.

```
/f1/auto/cmd_vel                          /f2/auto/cmd_vel
/f1/auto/goal                             /f2/auto/goal
/f1/auto/state                            /f2/auto/state
/f1/cmd/fork_speed                        /f2/cmd/fork_speed
/f1/cmd/steer_angle                       /f2/cmd/steer_angle
/f1/cmd/traction_speed                    /f2/cmd/traction_speed
/f1/fork_height                           /f2/fork_height
/f1/gz/actuator/fork_cmd                  /f2/gz/actuator/fork_cmd
/f1/gz/actuator/steer_cmd                 /f2/gz/actuator/steer_cmd
/f1/gz/actuator/traction_cmd              /f2/gz/actuator/traction_cmd
/f1/gz/drive_speed/read_a                 /f2/gz/drive_speed/read_a
/f1/gz/drive_speed/read_b                 /f2/gz/drive_speed/read_b
/f1/gz/fork_cmd                           /f2/gz/fork_cmd
/f1/gz/odom                               /f2/gz/odom
/f1/gz/safety_scanner_back/measurement    /f2/gz/safety_scanner_back/measurement
/f1/gz/safety_scanner_left/measurement    /f2/gz/safety_scanner_left/measurement
/f1/gz/safety_scanner_right/measurement   /f2/gz/safety_scanner_right/measurement
/f1/gz/scan_nav                           /f2/gz/scan_nav
/f1/gz/steer_cmd                          /f2/gz/steer_cmd
/f1/gz/traction_cmd                       /f2/gz/traction_cmd
/f1/hmi/cmd_vel                           /f2/hmi/cmd_vel
/f1/hmi/mode                              /f2/hmi/mode
/f1/joint_states                          /f2/joint_states
/f1/linear_speed                          /f2/linear_speed
/f1/odom                                  /f2/odom
/f1/plc/status                            /f2/plc/status
/f1/safety/encoders                       /f2/safety/encoders
/f1/safety/fields                         /f2/safety/fields
/f1/safety/torque_off_applied             /f2/safety/torque_off_applied
/f1/safety/torque_off_demand              /f2/safety/torque_off_demand
/f1/vehicle/cmd_vel                       /f2/vehicle/cmd_vel
```

```
$ ros2 topic list | grep -E '^/forklift/'
(none)
```

The step5 spellings are gone from the wire, not merely unused: the whole
`/forklift/...` family returns nothing.

> **First list is not the list.** The `ros2` daemon answered the first two
> queries with 10 topics, then 4 — partial discovery, mid-fill. `ros2
> daemon stop && ros2 daemon start`, eight seconds, then the 65 above,
> stable. Anyone reading a short topic list as a missing vehicle is
> reading the daemon's cache, not the stack.

### Each vehicle bound its own PLC port

```
$ grep bound logs/plc_link_f1.log logs/plc_link_f2.log
logs/plc_link_f1.log:[INFO] [plc_link]: bound 0.0.0.0:5110, publishing /f1/plc/status and /f1/safety/torque_off_demand
logs/plc_link_f2.log:[INFO] [plc_link]: bound 0.0.0.0:5120, publishing /f2/plc/status and /f2/safety/torque_off_demand

$ ss -uln | grep -E ':(5110|5120)'
UNCONN 0 0  0.0.0.0:5110  0.0.0.0:*
UNCONN 0 0  0.0.0.0:5120  0.0.0.0:*
```

5110 and 5120 are the `VEHICLES` table's `plc_port` values. Two processes,
two ports, no EADDRINUSE: the port pair really is per vehicle and not per
project.

### Expected noise, on the record so nobody debugs it

- `forklift_io_f1` / `forklift_io_f2` log `waiting for source data:
  joint_states=False, odom=False` every ~5 s, 150 times over this run.
  **Inherited from step5 and documented in
  `gazebo/step6_world.launch.py`**: joint states are deliberately not
  bridged (no consumer), and `forklift_io` subscribes `topics.odom`
  (`/<vid>/odom`, publisher count 0) while the bridge publishes
  `topics.gz_odom` (`/<vid>/gz/odom`, which `nav_node` and the HMI sketch
  do consume). It gates two derived state scalars and the fork-target
  seed, never traction or steer.
- `sto_contactor_f1` and `sto_contactor_f2` each log `TORQUE OFF: latch
  OPEN` once at startup. That is the correct answer to a PLC that has said
  nothing — see Gate 4 below.
- `gz_server` warns `XML Element[gz_frame_id] ... not defined in SDF` five
  times per model. Inherited SDF noise, both vehicles alike.

---

## [~] Gate 4 — per-vehicle stale-link: the SILENCE half, measured

**Spec:** *silencing one vehicle's 5111-family link fails that vehicle
safe (fields False, 0/3000) and leaves the other driving.*

**Measured here: the fail-safe half, on both vehicles at once.** With no
writer on either port, neither vehicle has ever received a PLC status, and
`is_stale` reads never-received as stale — so both must sit inhibited:

```
$ ros2 topic echo /f1/plc/status std_msgs/msg/String --once
data: '{"estop_healthy": false, "motor": false, "case": 3, "v_limit": 300, "ts": 0.0}'
---
$ ros2 topic echo /f2/plc/status std_msgs/msg/String --once
data: '{"estop_healthy": false, "motor": false, "case": 3, "v_limit": 300, "ts": 0.0}'
```

Byte-identical, and every field is the safe one: `motor: false` (no
drive), `case: 3` (the most restrictive monitoring case), `v_limit: 300`
(creep), `estop_healthy: false`, `ts: 0.0` (nothing was ever timestamped
because nothing ever arrived). Repeated on the second lifecycle (pids
21060/21259) with the same two payloads.

The chain below it agrees, per vehicle:

```
[sto_contactor_f1] TORQUE OFF: latch OPEN. Traction terminal driven to
0.000 rad/s and held ... Every command is now refused, including a
permissive envelope. Only the demand falling closes this latch.
[sto_contactor_f2] TORQUE OFF: latch OPEN. ... (same)
```

Two contactors, two independent latches, from two independent
`/fN/safety/torque_off_demand` streams.

**NOT measured here: the driving half** — one vehicle's link silenced
while the OTHER keeps driving. That needs both Windows writers and a hand
on a joystick, which no agent may supply. Runbook below.

**What already covers the writer's side of it:**
`tests/test_step6_virtual_loop.py::test_a_silent_sensor_link_fails_safe`
runs the real `step6.control_loop` against `VirtualFPLC` over real UDP
sockets, parameterised `[f1]` and `[f2]`, and asserts no status payload
reports Motor True once the sensor stream stops. That is loop-level
evidence on both port pairs; it is not a floor run and does not claim to
be.

---

## [x] Gate 5 — clean lifecycle, twice

**Spec:** *`step6.sh start`/`stop` twice in a row: no port squatters, no
orphans, `stop` names everything it killed.*

### Cycle 1 — stop

```
$ ./step6.sh stop
  swept 18306 (gz sim)                 swept 18299 (step6_world.launch.py)
  swept 18307 (parameter_bridge)       swept 18309 (sto_contactor.py)
  swept 18312 (sto_contactor.py)       swept 18310 (forklift_io.py)
  swept 18313 (forklift_io.py)         swept 18673 (plc_link.py)
  swept 18910 (plc_link.py)            swept 18679 (cmd_gate.py)
  swept 18925 (cmd_gate.py)            swept 18687 (cmd_mux.py)
  swept 18971 (cmd_mux.py)             swept 18855 (hmi_node.py)
  swept 19132 (hmi_node.py)            swept 18733 (field_eval.py)
  swept 19001 (field_eval.py)          swept 18780 (sensor_link.py)
  swept 19078 (sensor_link.py)         swept 18763 (encoder_link.py)
  swept 19047 (encoder_link.py)        swept 18828 (nav_node.py)
  swept 19103 (nav_node.py)
  killed 18673 ... killed 19132        (all 16 vehicle-node pids, in
                                        pidfile order)
down.
```

(Folded two per line to fit; the real output is one per line, and the
`killed` block is sixteen consecutive lines, not an elision in the tool.)

**23 swept, 16 killed, and the arithmetic is the point.** 17 pids were
recorded; `stop` swept 23, because the world launch owns six children the
pidfile never saw — `gz sim`, `parameter_bridge`, two `sto_contactor.py`
and two `forklift_io.py`. `PATTERNS` nominates them, `ours()` confirms
each one's `GZ_PARTITION`, and every single one is named on its way out.
Nothing is killed silently and nothing is left behind.

After it:

```
$ ss -uln | grep -E ':(5110|5120)'
(both free)
$ pgrep -f 'gz sim|plc_link.py|...|forklift_io.py'
(none)
$ test -f .step6_pids
removed
```

### Cycle 2 — start, refuse, stop

`start --headless` again, immediately: **17 pids** (world 20686 through
`hmi_f2` 21536), no startup warnings, `bound 0.0.0.0:5110` and `bound
0.0.0.0:5120` again in the fresh logs, both ports in `ss`, 17 lines in the
pidfile. Both `/plc/status` payloads FAILSAFE again, identical to cycle 1.

A third `start` on top of the live stack was refused, which is the
squatter check from the other side:

```
$ ./step6.sh start --headless
already running (pid 20686, see .../m5_ver2/step6/.step6_pids). Run './step6.sh stop' first.
exit=1
```

`stop` again: the same 23 swept, the same 16 killed — and then one more
line after the two-second grace:

```
  swept 21241 (hmi_node.py)
down.
```

**That trailing line is the design working, not a leak.** `stop` sends
TERM, waits 2 s, then sweeps KILL, because "past the grace nothing exits
on its own". `hmi_f1` sat in Tk's mainloop and ignored TERM; the KILL pass
took it and *named it*. A `stop` that had printed "down." over a live HMI
is exactly the failure this second pass exists to prevent.

Final state, after the second stop:

```
$ ss -uln | grep -E ':(5110|5120)'
(both free)
$ pgrep -af 'gz sim|plc_link.py|cmd_gate.py|cmd_mux.py|field_eval.py|encoder_link.py|sensor_link.py|nav_node.py|hmi_node.py|step6_world|parameter_bridge|sto_contactor.py|forklift_io.py'
(nothing but the grep's own shell)
$ test -f .step6_pids
removed
```

**Two full cycles, zero orphans, zero held ports, every kill named.**

A third cycle was run afterwards, timed: **`start --headless` takes 8.8 s** to seventeen live pids with zero warning lines, and its `stop` ended with the same trailing `swept ... (hmi_node.py)` KILL-pass line, both ports free and the pidfile gone. The trailing line is reproducible, which is what makes it a property of Tk's mainloop rather than an event.

---

## The four gates this build did not run

Gates 2, 3, 6 and Gate 4's driving half all need **the two Windows
writers** — `windows/step6.py --vehicle f1 --virtual` and `--vehicle f2
--virtual` — plus hands on two joysticks. Those are the owner's, on
Windows, and nothing in this build ran them. They are **NOT RUN**, not
"probably fine": no number below is filled in.

What each one is still owed:

| Gate | Status | What is missing |
|---|---|---|
| 2 — cross-isolation, both directions | **NOT RUN** | F1's PF trip latching F1's Motor while F2's Motor, fields and encoders are untouched over the same window; then mirrored F2→F1. |
| 3 — simultaneous autonomy | **NOT RUN** | Two independent station-to-station runs with *overlapping* drive time, 0 motor-false samples each, arrival radii at step5's bar. |
| 4 — per-vehicle stale-link (driving half) | **NOT RUN** | One vehicle's sensor link silenced *while the other is driving*, the other unaffected. (The silence half is measured above.) |
| 6 — the gate debt proven closed | **NOT RUN** | `cmd_mux` killed under Motor True: the plant sees zeros inside `CMD_STALE_S`, no repeat of step4's 14.8 m class. |

# The owner's runbook

Each gate below is a numbered list. **One action per step.** Do them in
order, do not skip the setup, and write the numbers you record straight
into the gate's section above.

## Setup — do this once, before any gate

1. Open a WSL terminal.
2. Run `cd /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6`.
3. Run `./step6.sh deploy`. It must print `deployed 17 files`.
4. Run `./step6.sh start`. (Leave off `--headless`: you want the Gazebo window for gates 2 and 3.)
5. Count the pid lines it printed. There must be **17**.
6. Check no line says `exited during startup`. If one does, open that log in `logs/` and stop here.
7. Look at the screen: **two HMI windows**, titled `Forklift HMI - f1` and `Forklift HMI - f2`.
8. Open a Windows terminal (cmd or PowerShell).
9. Run `cd C:\Users\ozkan\projects\amr-agent`.
10. Run `python m5_ver2\step6\windows\step6.py --vehicle f1 --virtual`.
11. Check its console prints `VIRTUAL F-PLC (model) - PLCSIM Advanced is not in this loop`, then `streaming PLC state to <wsl-ip>:5110` and `listening for the back scanner on 0.0.0.0:5111`.
12. Leave that window open. Open a **second** Windows terminal.
13. Run `cd C:\Users\ozkan\projects\amr-agent`.
14. Run `python m5_ver2\step6\windows\step6.py --vehicle f2 --virtual`.
15. Check its console prints the same three lines, but with **5120** and **5121**.
16. Look at the two panels: `Forklift f1 PLC Control Panel - VIRTUAL F-PLC (model)` and `Forklift f2 PLC Control Panel - VIRTUAL F-PLC (model)`.
17. Click **RESET** once on f1's panel. Its lamp must read `MOTOR ENABLED`.
18. Click **RESET** once on f2's panel. Its lamp must read `MOTOR ENABLED`.
19. Check both HMI lamps are neutral and both read `Drive enable: ON`.

**Both trucks are now enabled.** Every gate below starts from here.

### Teardown — do this at the end of every session

1. Close f1's panel window.
2. Close f2's panel window.
3. In the WSL terminal run `./step6.sh stop`.
4. Check the last line is `down.`

## Gate 2 — cross-isolation, both directions

Run the setup first. This gate is run twice: once F1→F2, then mirrored.

1. Open a third WSL terminal.
2. Run `source /opt/ros/jazzy/setup.bash`.
3. Run `export ROS_DOMAIN_ID=96`.
4. Run `ros2 topic echo /f2/plc/status std_msgs/msg/String > /tmp/g2_f2_status.txt` and leave it running.
5. Open a fourth WSL terminal.
6. Run `source /opt/ros/jazzy/setup.bash`.
7. Run `export ROS_DOMAIN_ID=96`.
8. Run `ros2 topic echo /f2/safety/fields std_msgs/msg/String > /tmp/g2_f2_fields.txt` and leave it running.
9. On **f1's** HMI, drag the joystick forward so f1 drives toward the nearest rack face.
10. Watch f1's panel lamp. When it flips to `MOTOR STOPPED`, f1's protective field has tripped.
11. Release f1's joystick (let it spring back to centre).
12. Wait five seconds.
13. Press Ctrl-C in the third WSL terminal.
14. Press Ctrl-C in the fourth WSL terminal.
15. Run `grep -c '"motor": false' /tmp/g2_f2_status.txt`. **Record this number. The gate wants 0.**
16. Run `grep -c '"motor": true' /tmp/g2_f2_status.txt`. Record it — this is the sample count the zero above is out of.
17. Run `grep -c '"pf": false' /tmp/g2_f2_fields.txt`. **Record this number. The gate wants 0** — `pf` is the protective field and `false` means tripped, so a zero says f2's three scanners never saw f1's obstacle.
18. Look at f1's HMI: lamp red, `Drive enable: OFF`. Record that it latched.
19. Click **RESET** once on f1's panel to heal it.
20. Now mirror the whole thing: repeat steps 1-19 with `f1` and `f2` swapped everywhere (echo `/f1/...`, drive **f2** into a rack).
21. Write both directions' numbers into the Gate 2 section above.
22. Tick Gate 2 only if **both** directions recorded 0 and 0.

## Gate 3 — simultaneous autonomy

Run the setup first. Start the recording BEFORE you press GO.

1. Open a third WSL terminal.
2. Run `source /opt/ros/jazzy/setup.bash`.
3. Run `export ROS_DOMAIN_ID=96`.
4. Run `ros2 topic echo /f1/plc/status std_msgs/msg/String > /tmp/g3_f1.txt` and leave it running.
5. Open a fourth WSL terminal.
6. Run `source /opt/ros/jazzy/setup.bash`.
7. Run `export ROS_DOMAIN_ID=96`.
8. Run `ros2 topic echo /f2/plc/status std_msgs/msg/String > /tmp/g3_f2.txt` and leave it running.
9. On **f1's** HMI, click the `Auto` radio button.
10. On f1's warehouse sketch, click a station dot on the far side of the map. It turns orange.
11. Press **GO** on f1's HMI. A dashed route appears and f1 starts driving.
12. Immediately go to **f2's** HMI and click its `Auto` radio button.
13. On f2's sketch, click a **different** station dot.
14. Press **GO** on f2's HMI.
15. Look at the Gazebo window and confirm **both trucks are moving at the same time**. That overlap is the gate; if f1 already arrived, stop and rerun with a longer route for f1.
16. Wait until f1's HMI state line reads `ARRIVED`. Record the arrival error it prints, in metres.
17. Wait until f2's HMI state line reads `ARRIVED`. Record its arrival error too.
18. Press Ctrl-C in the third WSL terminal.
19. Press Ctrl-C in the fourth WSL terminal.
20. Run `grep -c '"motor": false' /tmp/g3_f1.txt`. **Record it. The gate wants 0.**
21. Run `grep -c '"motor": false' /tmp/g3_f2.txt`. **Record it. The gate wants 0.**
22. Compare both arrival errors against step5's bar in `m5_ver2/step5/PROOF.md`.
23. Write all four numbers into the Gate 3 section above.

## Gate 4, driving half — one link dies, the other truck drives on

Run the setup first. This kills f1's `sensor_link` while f2 is driving.

1. In the WSL terminal, run `sed -n '7p' .step6_pids`. That line is **`sensor_link_f1`** — the pidfile is in spawn order (line 1 world, lines 2-9 f1, lines 10-17 f2).
2. Write that pid down.
3. Open a third WSL terminal.
4. Run `source /opt/ros/jazzy/setup.bash`.
5. Run `export ROS_DOMAIN_ID=96`.
6. Run `ros2 topic echo /f2/plc/status std_msgs/msg/String > /tmp/g4_f2.txt` and leave it running.
7. On **f2's** HMI, drag the joystick forward and hold it. f2 drives.
8. While f2 is still driving, run `kill <the pid from step 2>` in the WSL terminal.
9. Watch f1's panel lamp: it must flip to `MOTOR STOPPED` within about a second. The writer's own timeout is `SENSOR_STALE_S` 0.40 s + `CYCLE_S` 0.02 to writing the six field inputs False, and the F-program's chain (< 0.45 s from the demand) runs AFTER that one, not beside it.
10. Watch f1's HMI: it must go red, `Drive enable: OFF`.
11. Check f2 is **still driving** under your joystick. That is the gate.
12. Release f2's joystick.
13. Press Ctrl-C in the third WSL terminal.
14. Run `grep -c '"motor": false' /tmp/g4_f2.txt`. **Record it. The gate wants 0.**
15. Record how long f1 took to drop (a stopwatch is enough). The writer's half of that budget is `SENSOR_STALE_S` 0.40 + `CYCLE_S` 0.02 < 0.42 s to writing the inputs False; the F-program's chain is the other half.
16. Note that f1 stays down: `kill` removed the node, so nothing will heal it. Run `./step6.sh stop`, then the setup again, before any further gate.
17. Write the numbers into the Gate 4 section above.

## Gate 6 — kill the mux under Motor True

Run the setup first. This is the step4 14.8 m class, tested on purpose.

1. In the WSL terminal, run `sed -n '4p' .step6_pids`. That line is **`cmd_mux_f1`**.
2. Write that pid down.
3. Open a third WSL terminal.
4. Run `source /opt/ros/jazzy/setup.bash`.
5. Run `export ROS_DOMAIN_ID=96`.
6. Run `ros2 topic echo /f1/gz/odom > /tmp/g6_odom.txt` and leave it running.
7. On **f1's** HMI, drag the joystick forward and hold it so f1 is driving at a steady speed.
8. While f1 is still driving, run `kill <the pid from step 2>` in the WSL terminal.
9. Watch f1 in the Gazebo window. It must stop.
10. Release f1's joystick.
11. Press Ctrl-C in the third WSL terminal.
12. Run `grep -A2 'position:' /tmp/g6_odom.txt | grep -E '^ +(x|y):' | paste - - | cat -n > /tmp/g6_xy.txt` — one numbered `x  y` pair per odometry sample, 20 per simulated second.
13. Open `/tmp/g6_xy.txt`. Find the last pair before the numbers stop changing (that is where f1 came to rest) and the pair from the moment you killed the mux, and record the straight-line distance between them.
14. **The gate wants that distance to be a `CMD_STALE_S`-sized coast: 0.25 s of travel plus a tick.** At the 300 mm/s creep limit that is under 0.1 m; at the 2800 mm/s ceiling, under 0.8 m. Anything in step4's 14.8 m class is a FAIL.
15. Check f2's HMI: it must be unaffected, still `Drive enable: ON`.
16. Run `./step6.sh stop` — f1's mux is gone and the stack is now incomplete.
17. Write the distance into the Gate 6 section above.
