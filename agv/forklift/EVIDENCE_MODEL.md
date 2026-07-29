# EVIDENCE — the forklift model and the two vehicle nodes (m4f-02)

Dated headless capture of `agv/forklift/`: that the model spawns, that each
of its three driven joints responds to its own explicit gz command topic,
that the two ROS nodes publish at their declared rates through a real
`ros_gz_bridge`, that the lift holds its height under gravity, and that
the stop-zone evaluator reports the obstacle state whenever it has no
usable data.

**Simulation only, and not a safety claim.** Everything below was produced
by Gazebo on a software rasteriser. Nothing here is evidence about a real
vehicle, a real scanner or a protective field. `obstacle/in_stop_zone` is
a process comfort zone computed in Python from a bridged topic; the
protective stop, the e-stop chain and safe torque off are onboard,
hardwired, and appear nowhere in this run (invariant 1). See "What this
does not establish" at the end.

| Item | Value |
|---|---|
| Date | **2026-07-29**, 06:15–07:05 local |
| Host | WSL2 Ubuntu 24.04.4 LTS, kernel `5.15.167.4-microsoft-standard-WSL2`, headless |
| Repo | `/mnt/c/Users/ozkan/projects/amr-agent` (Windows checkout, driven from WSL) |
| ROS 2 | Jazzy, `/opt/ros/jazzy`, `python3 3.12.3` |
| Gazebo | `Gazebo Sim, version 8.11.0` via `ros-jazzy-gz-sim-vendor 0.0.10-1noble.20260604.111001` |
| ros_gz | `ros-jazzy-ros-gz 1.0.22-1noble.20260616.074726` |
| Render | `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)`, `GL_VERSION = 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2` |
| Server | `gz sim -s -r --headless-rendering`, server only, no GUI client |
| Real-time factor | `real_time_factor: 1.01883416843774` |
| Isolation | `GZ_PARTITION=m4f02model`, `ROS_DOMAIN_ID=61` |
| Under test | `model.sdf`, `config.yaml`, `scripts/forklift_io.py`, `scripts/obstacle_zone.py`, `launch/vehicle.launch.py` as committed |

Both transports are isolated, not just ROS: `ROS_DOMAIN_ID` does not
isolate Gazebo, because gz transport does not use DDS. Every run below
cleaned up by signalling only the pids it had started.

## 0. The world these runs used, and why it is not in this repository

`model.sdf` is a plain `<model>`. Worlds belong to `sim/`, so the world
below was written to a scratch directory outside the repository and is
quoted here in full so the run is reproducible. The single thing it
supplies that gz's stock `empty.sdf` does not is the sensors system: with
`empty.sdf` the vehicle drives and lifts, and the scanner is silent.

```xml
<sdf version="1.8">
  <world name="m4f02">
    <physics type="ode">
      <max_step_size>0.002</max_step_size>
      <real_time_factor>1.0</real_time_factor>
      <real_time_update_rate>500</real_time_update_rate>
    </physics>
    <plugin name="gz::sim::systems::Physics" filename="libgz-sim-physics-system.so"/>
    <plugin name="gz::sim::systems::UserCommands" filename="libgz-sim-user-commands-system.so"/>
    <plugin name="gz::sim::systems::SceneBroadcaster" filename="libgz-sim-scene-broadcaster-system.so"/>
    <plugin name="gz::sim::systems::Sensors" filename="libgz-sim-sensors-system.so">
      <render_engine>ogre2</render_engine>
    </plugin>
    <light name="sun" type="directional"> ... </light>
    <model name="Floor">   <!-- 60 x 60 plane, mu 1.0 --> ... </model>
    <model name="TestWall"><!-- static box 0.20 x 3.00 x 1.00 at x = 4.0 --> ... </model>
  </world>
</sdf>
```

The wall gives the scanner something real to measure. With the vehicle at
the origin and the scanner at `x = 0.72`, the near face of the wall sits
`4.0 - 0.10 - 0.72 = 3.18` m away, which is the number section 5 has to
reproduce for the scan to be believable.

---

## 1. The model spawns, and its systems advertise the contracted names

Spawned by service into the running server, from the model file as
committed:

```
=== spawn agv/forklift/model.sdf ===
data: true

=== gz topics under /forklift ===
/forklift/gz/fork_cmd
/forklift/gz/joint_state
/forklift/gz/odom
/forklift/gz/scan
/forklift/gz/scan/points
/forklift/gz/steer_cmd
/forklift/gz/traction_cmd

=== model in the world ===
Requesting state for world [m4f02]...

Available models:
    - Floor
    - TestWall
    - Forklift
```

Not one model-scoped default topic appears. `/forklift/gz/scan/points` is
the point-cloud companion the `gpu_lidar` publishes alongside the ranges;
nothing subscribes to it and the launch file does not bridge it.

The file is also strict-XML parseable, which `sim/worlds/cell.sdf` is not
(a `--` inside a comment, `sim/setup/WSL_ENVIRONMENT.md` §5.5). Any future
tooling that reads SDF with `xml.etree` will not have to special-case this
file:

```
xml.etree: model.sdf parses OK
```

## 2. Each joint responds to its own explicit gz command topic

One raw `gz topic -e` message, quoted as gz prints it, to fix the shape of
everything summarised below. Only the `pose` blocks, which are all
identity here, are elided:

```
=== RAW joint_state echo, one message, as gz prints it ===
header {
  stamp {
    sec: 10
    nsec: 240000000
  }
}
name: "Forklift"
id: 14
joint {
  name: "steer_joint"
  id: 53
  parent: "base_link"
  child: "steer_link"
  axis1 {
    xyz {
      z: 1
    }
    limit_lower: -1.31
    limit_upper: 1.31
    damping: 80
    position: -1.4588029561503328e-17
    velocity: 3.3181797329368154e-19
  }
}
joint {
  name: "drive_wheel_joint"
  id: 54
  parent: "steer_link"
  child: "drive_wheel"
  axis1 {
    xyz {
      y: 1
    }
    limit_lower: -1e+16
    limit_upper: 1e+16
    damping: 0.05
    position: -3.0787321913270846e-19
    velocity: -3.6989594022168165e-19
  }
}
joint {
  name: "mast_joint"
  id: 57
  parent: "mast"
  child: "carriage"
  axis1 {
    xyz {
      z: 1
    }
    limit_upper: 1.6
    damping: 8000
    position: -5.0194564512955053e-14
    velocity: 1.156307783630676e-18
  }
}
```

The three declared joints carry the limits `config.yaml` mirrors, and the
kinematic chain reads back as designed: the drive wheel hangs off
`steer_link`, not off the chassis, so steering carries the wheel with it.

### 2.1 Steer — `gz topic -t /forklift/gz/steer_cmd -m gz.msgs.Double -p 'data: ...'`

```
=== A. at rest ===
joint                                  position                 velocity
steer_joint             -1.4597871159043337e-17   4.6436134481685576e-19
drive_wheel_joint       -4.0608366575953211e-19  -4.6514840879035553e-18
mast_joint              -5.0194587783962293e-14  -6.0962182450784654e-18

=== B. steer: publish 0.60 rad to /forklift/gz/steer_cmd ===
steer_joint                 0.55342429510378344    0.0040076565774844752

=== C. steer: publish -1.31 rad (the mechanical stop) ===
steer_joint                 -1.3100000000110361   2.1316282072803006e-14
```

Three seconds after a 0.60 rad step the joint is at 0.553 and still
closing; four seconds after a step to the mechanical stop it is at
-1.3100000000110361 and stopped. The approach is asymptotic by design:
the integral has to build against the moment of scrubbing a loaded wheel
that is standing still.

### 2.2 Traction — `/forklift/gz/traction_cmd`, and the unit chain end to end

```
=== D. traction: publish 4.0 rad/s to /forklift/gz/traction_cmd ===
drive_wheel_joint            20.084255779742477       3.9999999999845994

--- odom after 5 s at 4.0 rad/s (expect ~0.48 m/s forward) ---
twist {
  linear {
    x: 0.4799968925779739
```

4.0 rad/s at a 0.12 m wheel is 0.48 m/s, and the odometry reports
0.4799968925779739. The wheel radius in `config.yaml` is therefore the
wheel radius in `model.sdf`, demonstrated rather than asserted.

The steer joint stayed still while this happened:

```
steer_joint               0.0016229985239581196  -0.00070137213088949935
```

That line is the fix for a defect worth recording. With the controller's
`d_gain` set to 500 and then 1500 the same measurement read `-0.0445` at
`-2.0000000018674458` rad/s, the joint hunting at its rate limit while
the vehicle rolled. The derivative term is an explicit force evaluated
once per physics step, so it is stable only while `d_gain` stays under
roughly inertia/step, here `0.13 / 0.002 = 65`. Raised past that it does
not damp, it oscillates; at `d_gain 1200` the joint stopped responding to
its topic altogether while still reporting a live command. The damping
that actually settles this joint is `<dynamics><damping>` on the joint,
which the engine integrates implicitly.

### 2.3 Fork — `/forklift/gz/fork_cmd`, rate limited on the way up

```
=== E. fork: publish 0.80 m to /forklift/gz/fork_cmd ===
--- t = 2s after the fork command ---
mast_joint                  0.30951562860508086      0.15000000001522656
--- t = 4s after the fork command ---
mast_joint                  0.62031562863662781      0.15000000001521857
--- t = 6s after the fork command ---
mast_joint                  0.80513396874391441    0.0025961681422832367
--- t = 8s after the fork command ---
mast_joint                  0.80569262640066719   9.6151558937052073e-13
--- t = 18s after the fork command ---
mast_joint                  0.80569262640022332  -1.1053449822107098e-12
```

The rise runs at `0.150000000015` m/s, which is the joint's declared
`<velocity>` limit reproduced to eleven figures. The physics engine
enforces it: that was not assumed, it was found by commanding a step and
reading the rate back.

Lowering is governed differently and deliberately:

```
=== F2. fork lowers on a smaller command: 0.20 m ===
--- t = 2s after the lower command ---
mast_joint                  0.51330748663467751     -0.14024951665076946
--- t = 4s after the lower command ---
mast_joint                  0.22242072102247812     -0.14024272320543585
--- t = 6s after the lower command ---
mast_joint                  0.18045794012312014  -7.3574826786604319e-13
```

0.140 m/s down, under the same 0.15 limit. An earlier tuning let the
controller push the carriage down as well as gravity, and it came down at
`-0.16974939797667` m/s — *through* a limit that says 0.15. The rate limit
was measured not to bind against a gravity-assisted descent, so lowering
is now gravity through the damping rather than a push.

## 3. The fork holds its height under gravity at zero command

Continuing from the 0.80 m command above, with nothing further published
to any topic:

```
=== F. fork holds under gravity with no further command ===
--- 5s after the last fork command ---
mast_joint                   0.8048450188024201  -0.00020432853671118953
--- 10s after the last fork command ---
mast_joint                   0.8039113804653556  -0.00016495436217272078
--- 15s after the last fork command ---
mast_joint                  0.80315845397582808  -0.00013320123633398656
--- 20s after the last fork command ---
mast_joint                  0.80254981788196489  -0.00010753326485079054
```

Over twenty seconds the carriage moves 2.3 mm, **towards** its target
rather than away from it, at a rate that halves as it goes. It is settling
out an overshoot, not sinking.

Getting that right needed one correction that is easy to get backwards.
gz's PID forms its error as (position − target) and negates the sum, so
while the carriage sits *below* its target the integral term is negative,
and it is `i_min` — the clamp that reads as the downward one — that bounds
how hard the lift can push **up**. Sized the intuitive way round, the
carriage stopped and held 15.7 mm short of an 0.80 m target, because the
integral was allowed 200 N of the 882 N the assembly weighs and position
error had to supply the rest:

```
mast_joint                  0.78426416504736085   1.4226744782241951e-12
```

The same inversion in the other direction buried the carriage 0.15 m under
a lowering target.

## 4. Both nodes publish at their declared rates, through a real bridge

Started by the committed launch file, which brings up the server, spawns
the model, runs one `ros_gz_bridge` and both nodes:

```
[create-2] [INFO] [spawn_forklift]: Requesting list of world names.
[obstacle_zone-5] [INFO] [obstacle_zone]: obstacle_zone up: sector +-0.5236 rad, stop distance 1.20 m, scan timeout 0.50 s, rate 10.0 Hz
[forklift_io-4] [INFO] [forklift_io]: forklift_io up: wheel radius 0.120 m, steer limit +-1.310 rad, fork travel 0.00 to 1.60 m, fork rate limit 0.150 m/s
```

```
=== ROS topics this directory owns ===
/forklift/cmd/fork_speed
/forklift/cmd/steer_angle
/forklift/cmd/traction_speed
/forklift/fork_height
/forklift/gz/fork_cmd
/forklift/gz/steer_cmd
/forklift/gz/traction_cmd
/forklift/joint_states
/forklift/linear_speed
/forklift/obstacle/in_stop_zone
/forklift/obstacle/min_distance
/forklift/odom
/forklift/scan
```

`ros2 topic hz`, quoted as printed:

```
=== A. declared rates, ros2 topic hz as printed ===
--- /forklift/fork_height ---
average rate: 9.999
	min: 0.100s max: 0.100s std dev: 0.00016s window: 30
--- /forklift/linear_speed ---
average rate: 10.000
	min: 0.100s max: 0.100s std dev: 0.00013s window: 30
--- /forklift/obstacle/in_stop_zone ---
average rate: 10.001
	min: 0.100s max: 0.100s std dev: 0.00014s window: 30
--- /forklift/obstacle/min_distance ---
average rate: 10.000
	min: 0.100s max: 0.100s std dev: 0.00013s window: 30
```

All four declared topics are at their configured 10 Hz. The sources they
are derived from, for the record:

```
=== A2. bridged source rates, for the record ===
--- /forklift/scan ---
average rate: 9.962
	min: 0.095s max: 0.114s std dev: 0.00294s window: 30
--- /forklift/odom ---
average rate: 20.001
	min: 0.049s max: 0.051s std dev: 0.00022s window: 30
--- /forklift/joint_states ---
average rate: 496.785
	min: 0.002s max: 0.002s std dev: 0.00015s window: 30
```

The scanner and the odometry publish at the rates `model.sdf` asks for.
Joint state does not have a rate to ask for: that system publishes once
per physics iteration, and an `<update_rate>` child was added and measured
to change nothing (2467 messages in 5 s with it, 2466 without). 496.785 Hz
in a 500 Hz world is what it is. The nodes consume it on their own timers
and drop the rest, but a world that bridges this topic is choosing that
traffic and should know it.

## 5. Commands are converted and clamped; the zone crosses its threshold

Unit conversion, requested in m/s and read back on the gz topic in rad/s:

```
=== B. unit conversion: 0.30 m/s in, rad/s out at the gz topic ===
--- /forklift/gz/traction_cmd (expect 0.30 / 0.12 = 2.5 rad/s) ---
2.5
```

The steer request is clamped to the mechanical stop rather than rejected:

```
=== D. steer command is clamped to the mechanical stop ===
--- /forklift/gz/steer_cmd after asking for 2.50 rad (limit 1.31) ---
1.31
```

Driving at 0.30 m/s at the wall, with all four vehicle-side topics logged
on one timeline so the command and its consequence are the same evidence:

```
   t[s]    fork_height   linear_speed   min_distance in_stop_zone
   0.50      -0.000000       0.300000       2.276373        False
   1.00      -0.000000       0.300000       2.126365        False
   1.50      -0.000000       0.300000       1.976356        False
   2.00      -0.000000       0.300000       1.826347        False
   2.50      -0.000000       0.300000       1.676337        False
   3.00      -0.000000       0.300000       1.526328        False
   3.50      -0.000000       0.300000       1.376318        False
   4.00      -0.000000       0.300000       1.226307        False
   4.50      -0.000000       0.300000       1.076296         True
   5.00      -0.000000       0.300000       0.926285         True
   5.50      -0.000000       0.300000       0.776274         True
```

Three things at once. The measured speed is 0.300000 for a 0.30 m/s
request. `min_distance` falls by 0.150 m every 0.5 s, which is 0.30 m/s,
so the scanner and the odometry agree about how fast the vehicle is
moving. And `in_stop_zone` turns itself True between 1.226307 and
1.076296, bracketing the 1.20 m threshold in `config.yaml`, with no
command involved.

The starting range in an earlier run of the same script was
`3.18019437789917` m against the 3.18 m the wall geometry predicts.

Fork rate limiting, in engineering units: a 0.50 m/s request against a
0.15 m/s limit.

```
   t[s]    fork_height   linear_speed   min_distance in_stop_zone
   2.00       0.154216      -0.000609       0.186068         True
   ...
   4.80       0.573522      -0.000267       0.187203         True
```

0.419306 m in 2.80 s is **0.14975 m/s**. The request was clamped by the
node, and the target it integrates is what the carriage follows.

Then the request goes to zero, which holds rather than lowers:

```
--- after the zero rate request: does it hold? ---
   t[s]    fork_height   linear_speed   min_distance in_stop_zone
   1.00       0.811563      -0.000052       0.187875         True
   5.00       0.812314       0.000000       0.188036         True
  13.00       0.813483       0.000000       0.188084         True
```

1.9 mm over twelve seconds, converging.

## 6. Absence of data is an obstacle

The cases a rendered scanner cannot easily be made to produce were driven
directly against `obstacle_zone.py`, with no Gazebo running at all:

```
obstacle_zone fault matrix: sector +-30 deg, stop 1.20 m, timeout 0.50 s, window [0.10, 8.00] m

ok   clear sector               in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   obstacle dead ahead        in_stop_zone=True  min_distance=0.8000     (expected True / 0.800)
ok   obstacle at +10 deg        in_stop_zone=True  min_distance=1.1500     (expected True / 1.150)
ok   obstacle at -90 deg        in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   obstacle just outside      in_stop_zone=False min_distance=1.2500     (expected False / 1.250)
ok   all samples NaN            in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all samples +inf           in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all samples -inf           in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all below range_min        in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all above range_max        in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   empty ranges               in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   range window NaN           in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   range window inverted      in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   one valid among NaN        in_stop_zone=False min_distance=2.0000     (expected False / 2.000)
ok   clear again before stall   in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   publisher stopped 3 s      in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   recovers when it returns   in_stop_zone=False min_distance=5.0000     (expected False / 5.000)

RESULT: PASS (0 failing case(s))
```

The node's own log distinguishes *why*, which matters when the same
verdict has several causes:

```
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=no scan received
[INFO] [obstacle_zone]: in_stop_zone=False min_distance=5.000 reason=sector clear
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.800 reason=obstacle in sector
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=no valid sample in sector
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=scan geometry unusable
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=scan range window unusable
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=scan stale
[INFO] [obstacle_zone]: in_stop_zone=False min_distance=5.000 reason=sector clear
```

Three cases are worth naming. **`one valid among NaN` returns False at
2.000**: a scan is not condemned for containing bad samples, only for
containing no good ones, which is why validity is an affirmative test per
sample rather than a rejection of the whole message. **`range window NaN`
returns True**: the window a sample is judged against is itself checked
for plausibility first, because a NaN window cannot qualify anything.
**`publisher stopped 3 s` returns True**, and it recovers on its own when
data returns — the staleness verdict is a level, not a latch, and it is
judged against the node's own monotonic clock at receipt, never against
the header stamp of the thing being watched.

### 6.1 Beyond-range is a measurement, not an absence — re-run 2026-07-29, 14:46–14:51

**Why two expectations in the matrix above are now wrong.** That run
recorded `all samples +inf` as `True / 0.000` and passed itself on it. The
expectation was the defect, not the code. On **2026-07-29** a teleop
session on the arena took a **process stop every time the vehicle's
heading opened up**: `/forklift/scan` healthy at 10 Hz, the ±30° forward
sector entirely beyond the scanner's 8 m range and therefore entirely
`inf`, and the affirmative validity test — finite AND inside
`[range_min, range_max]` — read a full sector of `inf` as *no valid data*
and published the fail-safe pair into open space. A rangefinder that
returns beyond-range is not failing to answer. It is answering: **clear to
`range_max`**. The two rows that change are `all samples +inf` and
`all above range_max`; both are now `False / 8.000`.

The rule is therefore three classes, and only the last is an absence:

| Class | What the sensor said | Contributes | Fail-safe? |
|---|---|---|---|
| `CLEAR` | `+inf`, or a finite range ≥ `range_max` | `range_max` | never |
| `DISTANCE` | a finite range inside `[range_min, range_max)` | that range | only via the 1.20 m threshold, as before |
| `INVALID` | `NaN`, `-inf`, or a range below `range_min` | nothing | only if **nothing else** in the sector is valid |

Both valid classes are affirmative comparisons, tested in that order, so a
`NaN` still reaches neither and is `INVALID`. The fail-safe now fires on a
missing, stale or structurally unusable scan, or on a sector with no sample
in **either** valid class — a dead or garbage sensor still stops the
machine, an open horizon does not.

| Item | Value |
|---|---|
| Date | **2026-07-29**, 14:46–14:51 local |
| Isolation | `GZ_PARTITION=m4f02c`, `ROS_DOMAIN_ID=71` |
| Environment | As the header table: WSL2 Ubuntu 24.04.4 LTS, ROS 2 Jazzy, `python3 3.12.3`, Gazebo Sim 8.11.0 (`ros-jazzy-gz-sim-vendor 0.0.10-1noble.20260604.111001`), `ros-jazzy-ros-gz 1.0.22-1noble.20260616.074726`, `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)`, headless |
| Under test | `scripts/obstacle_zone.py` as committed by this change; `model.sdf`, `config.yaml` and `launch/vehicle.launch.py` unchanged |
| Note | An unrelated simulation was running on another partition and another domain throughout. It shared the CPU and the software rasteriser with these runs; it did not share a transport with them, and no pid outside this run was signalled |

The matrix is driven the same way as the one above — the node started as
its own process, real messages on the real topics, no Gazebo — with two
rows re-expected and four rows added:

```
obstacle_zone fault matrix: sector +-30 deg, stop 1.20 m, timeout 0.50 s, window [0.10, 8.00] m

ok   clear sector               in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   obstacle dead ahead        in_stop_zone=True  min_distance=0.8000     (expected True / 0.800)
ok   obstacle at +10 deg        in_stop_zone=True  min_distance=1.1500     (expected True / 1.150)
ok   obstacle at -90 deg        in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   obstacle just outside      in_stop_zone=False min_distance=1.2500     (expected False / 1.250)
ok   all samples NaN            in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all samples +inf           in_stop_zone=False min_distance=8.0000     (expected False / 8.000)
ok   all samples -inf           in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all below range_min        in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all above range_max        in_stop_zone=False min_distance=8.0000     (expected False / 8.000)
ok   empty ranges               in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   range window NaN           in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   range window inverted      in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   one valid among NaN        in_stop_zone=False min_distance=2.0000     (expected False / 2.000)
ok   inf sector, one finite 2.0 in_stop_zone=False min_distance=2.0000     (expected False / 2.000)
ok   inf sector, obstacle 0.8   in_stop_zone=True  min_distance=0.8000     (expected True / 0.800)
ok   inf sector, one NaN        in_stop_zone=False min_distance=8.0000     (expected False / 8.000)
ok   inf sector, one below min  in_stop_zone=False min_distance=8.0000     (expected False / 8.000)
ok   clear again before stall   in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   publisher stopped 3 s      in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   recovers when it returns   in_stop_zone=False min_distance=5.0000     (expected False / 5.000)

RESULT: PASS (0 failing case(s))
```

The four added rows are the ones that decide whether the fix is a fix or a
hole. **`inf sector, obstacle 0.8` returns `True / 0.800`**: an open
horizon does not blind the detector, which is the case worth being sure
of. **`inf sector, one finite 2.0` returns `False / 2.000`**: a `CLEAR`
sample contributes `range_max`, so the minimum is still the real object.
**`inf sector, one NaN` returns `False / 8.000`**: a scan is not condemned
for containing a bad sample, exactly as before. And **`inf sector, one
below min` returns `False / 8.000`**, which is a residual and is written
out at the end of this section rather than left to be found.

Everything the old matrix established about a dead sensor is unchanged:
`all samples NaN`, `all samples -inf`, `all below range_min`, `empty
ranges`, both unusable windows and `publisher stopped 3 s` are still
`True / 0.000`. The node's own reason strings, which is where the *why*
lives, gained exactly one member:

```
[INFO] [obstacle_zone]: in_stop_zone=False min_distance=5.000 reason=sector clear
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.800 reason=obstacle in sector
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=no valid sample in sector
[INFO] [obstacle_zone]: in_stop_zone=False min_distance=8.000 reason=sector clear beyond range
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=scan geometry unusable
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=scan range window unusable
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=scan stale
```

#### The same thing on a rendered scan, and the rule that produced the false stop

A synthetic `inf` is not the defect; the defect was a real scanner looking
at nothing. Two headless Gazebo runs on the minimal world of section 0,
vehicle spawned at the origin, once facing the wall and once facing away
from it, with **one real message from each run evaluated under both
rules** — the rule as committed before this change, and the three-class
rule:

```
=== facing OPEN SPACE (yaw = pi, wall behind the vehicle) ===
scan: 181 samples, angle [-1.5708, 1.5708] rad, window [0.10, 8.00] m

   t[s]   min_distance in_stop_zone
   0.51       8.000000        False
   2.02       8.000000        False
   4.01       8.000000        False
   6.01       8.000000        False

one real scan, forward sector +-30 deg: 0 DISTANCE, 61 CLEAR, 0 INVALID
  rule at ce7153b : in_stop_zone=True  min_distance=0.000  reason=no valid sample in sector
  three-class rule: in_stop_zone=False min_distance=8.000  reason=sector clear beyond range
```

That is the teleop false stop, reproduced and then removed on the same
message: sixty-one rays, every one of them a `CLEAR` measurement, zero
invalid samples, and a rule that called the lot of them missing data.

```
=== facing the WALL (yaw = 0, near face 3.18 m ahead of the scanner) ===

   t[s]   min_distance in_stop_zone
   0.50       3.180194        False
   2.00       3.180194        False
   4.00       3.180194        False
   6.00       3.180194        False

one real scan, forward sector +-30 deg: 51 DISTANCE, 10 CLEAR, 0 INVALID
  rule at ce7153b : in_stop_zone=False min_distance=3.180  reason=sector clear
  three-class rule: in_stop_zone=False min_distance=3.180  reason=sector clear
```

`3.180194` is the same wall range section 5 measured, so the distance path
is untouched by this change. The sector is genuinely mixed on real data —
the wall is 3.00 m wide and the ±30° sector is 3.67 m wide at 3.18 m, so
ten rays at the sector edges miss it and come back `CLEAR` — and the
verdict is still the wall. Neither run produced a single `INVALID` sample:
the `±45°` dropout of `README.md` sits outside a ±30° sector.

The node's log across the open-space run is the whole change in two lines:

```
[INFO] [obstacle_zone]: in_stop_zone=True min_distance=0.000 reason=no scan received
[INFO] [obstacle_zone]: in_stop_zone=False min_distance=8.000 reason=sector clear beyond range
```

Before any data, the fail-safe. With data that says *nothing out there*,
`8.000` — which is the **scan's own** `range_max` and not a constant of
this node, so it follows whatever scanner the model declares. That couples
two documents: `model.sdf`'s `<range><max>` must stay inside the
plausibility window the consumer applies to this value
(`docs/interfaces/opcua-nodes.md` §10.5 gives `0.05 … 8.10` m against the
scanner's `0.10 … 8.00` m, so `8.00` is inside it with 0.10 m to spare).
Raising the scanner's range past `8.10` without moving that window would
make a clear horizon read at the PLC as a transducer fault — the same
class of mistake as the one this section fixes, one layer along.

#### Residual, stated rather than discovered

**A below-`range_min` return is skipped, not treated as an obstacle.**
`-inf` and any range under `range_min` are `INVALID`, which is what the
matrix rows `all samples -inf` and `all below range_min` pin at
`True / 0.000`. But an `INVALID` sample is ignored whenever *some other*
sample in the sector is valid — that is the pre-existing "a scan is not
condemned for containing a bad sample" rule, unchanged here. It is now
reachable in a combination it was not reachable in before: `inf sector,
one below min` returns `False / 8.000`. On a scanner that reports
too-close as a below-minimum return rather than as a short range, that ray
is the most non-permissive thing the sensor can say, and this node
currently drops it. Nothing in this run establishes which behaviour the
scanner in `model.sdf` has; it returned no `INVALID` sample in either
live run. Deciding it is an owner call and is carried in the report for
this change, not settled here.

## 7. Every constant is in `config.yaml`, and it agrees with the model

The two files hold the same numbers because SDF cannot be read as YAML.
Checked mechanically rather than by eye:

```
mirrored value                config.yaml      model.sdf  agree
wheel_radius_m                       0.12           0.12  yes
steer_limit_rad                      1.31           1.31  yes
steer_limit_rad (lower)             -1.31          -1.31  yes
fork_travel_min_m                     0.0            0.0  yes
fork_travel_max_m                     1.6            1.6  yes
fork_speed_max_mps                   0.15           0.15  yes

gz topics declared in model.sdf : ['/forklift/gz/fork_cmd', '/forklift/gz/joint_state', '/forklift/gz/odom', '/forklift/gz/scan', '/forklift/gz/steer_cmd', '/forklift/gz/traction_cmd']
gz topics declared in config.yaml: ['/forklift/gz/fork_cmd', '/forklift/gz/joint_state', '/forklift/gz/odom', '/forklift/gz/scan', '/forklift/gz/steer_cmd', '/forklift/gz/traction_cmd']
sets identical: True

RESULT: PASS
```

Every key declared in `config.yaml` is read by a script or by the launch
file, and the only numeric literals left in the two nodes are `1.0 / rate`
to turn a frequency into a period, `0.0` as the initial stopped command,
and `0.0` in the divide-by-zero guard on `angle_increment`. No rate, no
limit, no threshold and no topic name is written inline.

## What this does not establish

1. **Nothing about safety.** No protective field, no e-stop chain, no STO.
   `in_stop_zone` is a process signal computed in Python over a bridged
   topic and carries no integrity claim (invariant 1).
2. **Nothing about localisation or navigation.** The odometry here is
   ground truth from the simulator, not a solution. AMCL, a map and Nav2
   are separate work and none of them ran.
3. **Nothing about VDA 5050.** No order, no state message, no broker, no
   supervision watchdog. This is the layer underneath that.
4. **Nothing about a payload.** No pallet was lifted. The fork travel and
   hold figures are for the unloaded carriage; a payload changes the
   weight the integral has to hold and the tuning would have to be
   re-measured against it.
5. **Nothing about a warehouse world.** The runs used a floor and one wall.
   Behaviour among racking, in a doorway, or beside another vehicle is
   `sim/`'s to exercise.
6. **Nothing about hardware acceleration.** Rendering was llvmpipe, and
   the scanner budget of 181 samples at 10 Hz was chosen against that.
   Raising either without re-measuring would be a change to a figure this
   run establishes.
7. **The steer angle was verified standing still**, which is the hardest
   case for the controller and the least representative of driving. Steer
   tracking while turning under way is not measured here.
