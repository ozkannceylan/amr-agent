# FORKLIFT_ARENA_EVIDENCE.md — verified headless run of the M4 commissioning arena

Dated capture of `sim/worlds/forklift_arena.sdf` and
`sim/launch/forklift_bringup.launch.py`: that the launch brings up the arena
headless and spawns `agv/forklift/model.sdf` into it, that all seven bridged
topics carry traffic at a measured rate, that the bridge is wired in the
direction each topic is declared in, and that a scripted `gz topic` traction
pulse moves the vehicle by an amount visible on the bridged ROS odometry.

**Sections 1 to 8 are that M4 record and are not re-run.** Section 9 was added
later, at M5, and is a different run on a different machine against a different
sensor set: it measures what the world's new `<gui>` block and the M5 three
scanner set cost to render, and it carries its own inputs table. Read the two as
two dated captures, not as one document.

**Simulation only, and not a safety claim.** Everything below was produced by
Gazebo on a software rasteriser. Nothing here is evidence about a real
vehicle, a real scanner or a protective field. The obstacle props in this
world are process furniture; the protective stop, the e-stop chain and safe
torque off are onboard, hardwired, and appear nowhere in this run
(invariant 1). See "What this does not establish" at the end.

| Item | Value |
|---|---|
| Date | **2026-07-29**, 07:25–07:45 local |
| Host | WSL2 Ubuntu 24.04.4 LTS, kernel `5.15.167.4-microsoft-standard-WSL2` |
| Repo | `/mnt/c/Users/ozkan/projects/amr-agent` (Windows checkout, driven from WSL) |
| ROS 2 | Jazzy, `/opt/ros/jazzy`, `Python 3.12.3` |
| Gazebo | `gz sim 8.11.0` via `ros-jazzy-gz-sim-vendor 0.0.10-1noble.20260604.111001` |
| ros_gz | `ros-jazzy-ros-gz 1.0.22-1noble.20260616.074726` |
| Render | `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)`, `GL_VERSION = 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2` |
| Server | `gz sim -r -s <world>`, server only, no GUI client (`gui:=false`, the default) |
| Real-time factor | `real_time_factor: 0.99984002559590468` |
| Isolation | `GZ_PARTITION=m4f03arena`, `ROS_DOMAIN_ID=42` |
| `LIBGL_ALWAYS_SOFTWARE` | unset, deliberately (`DISPLAY` was `:0`) |
| Under test | `sim/worlds/forklift_arena.sdf`, `sim/launch/forklift_bringup.launch.py` as committed |

Both transports are isolated, not just ROS: `ROS_DOMAIN_ID` does not isolate
Gazebo, because gz transport does not use DDS. The five runs below used
`GZ_PARTITION` values `m4f03arena`, `m4f03scan`, `m4f03seam`, `m4f03seam2`
and `m4f03raw` with `ROS_DOMAIN_ID` 42 to 46, and each cleaned up by
signalling only the pids it had started.

Summary of the four required checks:

| Check | Result |
|---|---|
| Headless launch spawns the forklift into the arena | PASS — 13 models listed, `Entity creation successful`, 0 ERROR and 0 WARN lines |
| Bridge covers `/clock`, scan, odometry, joint states and the three gz commands | PASS — 7 topics, direction confirmed by publisher/subscriber counts |
| Every bridged topic has a measured rate | PASS — all seven quoted below as `ros2 topic hz` printed them |
| A scripted gz-topic traction pulse shows on the bridged odometry | PASS — `odom_x` moved `-6.000000` to `-3.121976`, 0.480000 m/s steady |

---

## 1. Bringup

```
$ ros2 launch /mnt/c/Users/ozkan/projects/amr-agent/sim/launch/forklift_bringup.launch.py
(readiness probe: /forklift/odom present in ros2 topic list after 1 s wall clock)

$ gz model --list

Requesting state for world [forklift_arena]...

Available models:
    - Floor
    - WallWest
    - WallEast
    - WallSouth
    - WallNorth
    - AisleMarking
    - PalletZoneMarking
    - Pallet
    - LoadBox
    - AisleCrate
    - PillarSouth
    - CrateNorth
    - Forklift
```

Twelve arena models and the spawned vehicle. No conveyor, no photo-eye and no
operator panel: the fixed-equipment cell is not embedded here, and the coupled
cell plus vehicle scenario is roadmap M6 work (ADR 0010).

```
$ ros2 topic list
/clock
/forklift/gz/fork_cmd
/forklift/gz/steer_cmd
/forklift/gz/traction_cmd
/forklift/joint_states
/forklift/odom
/forklift/scan
/parameter_events
/rosout
```

Seven bridged topics and nothing else. The vehicle-side nodes are absent by
design: `/forklift/cmd/*`, `/forklift/fork_height`, `/forklift/linear_speed`
and `/forklift/obstacle/*` are produced by `forklift_io.py` and
`obstacle_zone.py`, which `agv/forklift/launch/vehicle.launch.py` owns and
this launch deliberately does not start.

```
$ gz topic -e -t /world/forklift_arena/stats -n 1
sim_time {
  sec: 5
  nsec: 80000000
}
real_time {
  sec: 7
  nsec: 898694835
}
iterations: 2540
real_time_factor: 0.99984002559590468
step_size {
  nsec: 2000000
}
```

2 ms steps at real time, headless, with the sensors system rendering on
llvmpipe. The 24 x 16 arena is light enough that the 500 Hz physics of
`cell.sdf` carries over unchanged.

```
=== render engine, from the ogre2 log this run wrote ===
07:25:59: GL_VERSION = 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2
07:25:59: GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)
```

Read from the log rather than assumed: a `/dev/dri` node and a GL 4.5 context
prove nothing about acceleration on this machine.

## 2. The bridge is wired in the direction each topic is declared in

`ros2 topic info`, as printed. A gz→ROS topic shows the bridge as the
**publisher**; a ROS→gz topic shows it as the **subscriber**.

```
--- /clock
Type: rosgraph_msgs/msg/Clock
Publisher count: 1
Subscription count: 1

--- /forklift/scan
Type: sensor_msgs/msg/LaserScan
Publisher count: 1
Subscription count: 0

--- /forklift/odom
Type: nav_msgs/msg/Odometry
Publisher count: 1
Subscription count: 0

--- /forklift/joint_states
Type: sensor_msgs/msg/JointState
Publisher count: 1
Subscription count: 0

--- /forklift/gz/steer_cmd
Type: std_msgs/msg/Float64
Publisher count: 0
Subscription count: 1

--- /forklift/gz/traction_cmd
Type: std_msgs/msg/Float64
Publisher count: 0
Subscription count: 1

--- /forklift/gz/fork_cmd
Type: std_msgs/msg/Float64
Publisher count: 0
Subscription count: 1
```

`/clock` is the only topic with a count on both sides, and that is the
`use_sim_time:=true` default taking effect: the bridge publishes the clock and
subscribes to it as its own time source. It is the one observable difference
this launch has from `cell_bringup.launch.py`.

The launch log states the same thing in the bridge's own words:

```
[parameter_bridge-3] [INFO] [forklift_arena_bridge]: Creating GZ->ROS Bridge: [/clock (gz.msgs.Clock) -> /clock (rosgraph_msgs/msg/Clock)] (Lazy 0)
[parameter_bridge-3] [INFO] [forklift_arena_bridge]: Creating ROS->GZ Bridge: [/forklift/gz/steer_cmd (std_msgs/msg/Float64) -> /forklift/gz/steer_cmd (gz.msgs.Double)] (Lazy 0)
[parameter_bridge-3] [INFO] [forklift_arena_bridge]: Creating ROS->GZ Bridge: [/forklift/gz/traction_cmd (std_msgs/msg/Float64) -> /forklift/gz/traction_cmd (gz.msgs.Double)] (Lazy 0)
[parameter_bridge-3] [INFO] [forklift_arena_bridge]: Creating ROS->GZ Bridge: [/forklift/gz/fork_cmd (std_msgs/msg/Float64) -> /forklift/gz/fork_cmd (gz.msgs.Double)] (Lazy 0)
[parameter_bridge-3] [INFO] [forklift_arena_bridge]: Creating GZ->ROS Bridge: [/forklift/gz/scan (gz.msgs.LaserScan) -> /forklift/gz/scan (sensor_msgs/msg/LaserScan)] (Lazy 0)
[parameter_bridge-3] [INFO] [forklift_arena_bridge]: Creating GZ->ROS Bridge: [/forklift/gz/odom (gz.msgs.Odometry) -> /forklift/gz/odom (nav_msgs/msg/Odometry)] (Lazy 0)
[parameter_bridge-3] [INFO] [forklift_arena_bridge]: Creating GZ->ROS Bridge: [/forklift/gz/joint_state (gz.msgs.Model) -> /forklift/gz/joint_state (sensor_msgs/msg/JointState)] (Lazy 0)
```

## 3. Every bridged topic, with its measured rate

`ros2 topic hz`, quoted as printed. Four topics arrive from gz on their own:

```
--- /clock ---
average rate: 500.044
	min: 0.001s max: 0.003s std dev: 0.00012s window: 3505
--- /forklift/scan ---
average rate: 9.999
	min: 0.096s max: 0.102s std dev: 0.00095s window: 64
--- /forklift/odom ---
average rate: 20.001
	min: 0.049s max: 0.051s std dev: 0.00024s window: 122
--- /forklift/joint_states ---
average rate: 499.812
	min: 0.001s max: 0.005s std dev: 0.00015s window: 3503
```

The three command topics carry nothing until something publishes on them, so
they were driven at 20 Hz with `ros2 topic pub -r 20 ... '{data: 0.0}'` while
being measured. **The figure below is therefore the stimulus rate, not a
property of the bridge**; what it establishes is that the topic exists with
the declared type and accepts traffic. A zero on each of the three is the
state the vehicle is already in, so the measurement disturbs nothing.

```
--- /forklift/gz/steer_cmd ---
average rate: 20.001
	min: 0.049s max: 0.050s std dev: 0.00015s window: 105
--- /forklift/gz/traction_cmd ---
average rate: 19.999
	min: 0.050s max: 0.050s std dev: 0.00016s window: 125
--- /forklift/gz/fork_cmd ---
average rate: 19.999
	min: 0.041s max: 0.059s std dev: 0.00121s window: 123
```

### The joint-state rate is the world's, and it is a deliberate choice

`499.812` Hz in a 500 Hz world. gz's `JointStatePublisher` has no working rate
parameter — `agv/forklift/EVIDENCE_MODEL.md` measured an `<update_rate>` child
to change nothing, 2467 messages in 5 s with it against 2466 without — and it
publishes once per physics iteration. m4f-02 measured `496.785` Hz in its own
500 Hz world and left the decision to whoever bridged the topic.

This launch bridges it **as-is**. Decimating it here would be the bridge
deciding what a consumer needs, which is exactly the logic the bridge is not
allowed to hold, and the vehicle nodes already rate-limit everything they
derive from it (`fork_height` and `linear_speed` at 10 Hz, the fork target at
20 Hz). Any consumer that cannot afford ~500 Hz sets its own QoS or its own
timer; the arena states the traffic it carries rather than hiding it.

## 4. The scanner publishes, which is what the sensors system is there for

```
frame_id        : Forklift/base_link/safety_scanner
samples         : 181
angle_min/max   : -1.5707963 / 1.5707963 rad
angle_increment : 0.0174533 rad (1.0000 deg)
range_min/max   : 0.100 / 8.000 m

  index   bearing[deg]      range[m]
      0        -90.0        7.900483
     45        -45.0             inf
     90          0.0        6.830417
    135         45.0             inf
    180         90.0        7.900483

finite samples  : 41 of 181
nearest return  : 3.805794 m at index 177 (87.0 deg)
farthest return : 7.969610 m at index 8 (-82.0 deg)
```

Two of those numbers are the arena checking its own arithmetic, with the
vehicle at the launch's default spawn `x = -6.00, y = 0.00`:

- **Dead ahead, `6.830417` m.** The scanner leads the model origin by 0.72 m,
  so it stands at `x = -5.28`; `AisleCrate`'s front face is at `x = 1.55`.
  `1.55 - (-5.28) = 6.83`. The measurement puts the scanner at `-5.280417`.
- **Both beams, `7.900483` m.** The north and south walls are 0.20 thick and
  centred on `y = +-8.00`, so their inner faces are at `+-7.90`. The
  measurement puts the vehicle on the aisle centreline to within 0.5 mm.

`inf` at `+-45 deg` is **not** an arena defect and the next section says why.

### A single-sample dropout at exactly +-45 deg, in the sensor and not the bridge

The five sampled bearings above unluckily included both diagonals, which made
a real artefact look like a pattern. Dumping every sample shows what it
actually is — a one-sample hole in the middle of an object that is otherwise
returned continuously:

```
  idx  43    -47.0 deg   4.56028413772583
  idx  44    -46.0 deg   4.481344699859619
  idx  45    -45.0 deg   inf
  idx  46    -44.0 deg   4.3658833503723145
  idx  47    -43.0 deg   4.442789077758789
  idx  48    -42.0 deg   4.526336193084717
```

That is `PillarSouth` at about 4.4 m, present either side of the hole. Parked
in the south-west corner instead, where a flat wall fills the whole
neighbourhood, the same hole appears in a smooth ramp:

```
  idx  43    -47.0 deg   3.9597270488739014
  idx  44    -46.0 deg   4.021979331970215
  idx  45    -45.0 deg   inf
  idx  46    -44.0 deg   4.185474872589111
```

It is **not** a fixed bad index. Turned 180 deg in the same corner, so the
same wall sits on the diagonal from the other side, the sample returns:

```
  idx  45    -45.0 deg   3.0710039138793945
  idx 135     45.0 deg   3.0710039138793945
```

And it is **not** the bridge. The raw gz message already carries it, read from
`gz topic -e -t /forklift/gz/scan -n 1` in the same running world as the
bridged echo beside it:

```
=== RAW gz.msgs.LaserScan ranges, indices 42..48, from gz topic -e ===
raw ranges count : 181
  idx  42   inf
  idx  43   4.56028413772583
  idx  44   4.4813446998596191
  idx  45   inf
  idx  46   4.3658833503723145
  idx  47   4.4427890777587891
  idx  48   4.5263361930847168

=== BRIDGED /forklift/scan, same indices, same running world ===
  idx  43    -47.0 deg   4.56028413772583
  idx  44    -46.0 deg   4.481344699859619
  idx  45    -45.0 deg   inf
  idx  46    -44.0 deg   4.3658833503723145
  idx  47    -43.0 deg   4.442789077758789
  idx  48    -42.0 deg   4.526336193084717
```

Raw and bridged agree sample for sample, so the bridge is translating
faithfully and the dropout originates in the gz `gpu_lidar`. A 180 deg field
is rendered across more than one camera face and the sample landing exactly on
the seam falls through, marginally: whether it does depends on the geometry in
front of it, which is why turning the vehicle round recovers it.

**Why it does not affect this gate.** The stop zone is the `+-30 deg` sector of
`agv/forklift/config.yaml`, indices 60 to 120, and the seam is outside it at
indices 45 and 135. Independently of that, `obstacle_zone.py` judges validity
**per sample** and condemns a scan only when it contains no good sample at all
— `one valid among NaN returns False at 2.000` in `EVIDENCE_MODEL.md` — so a
single dropped ray is absorbed by design rather than by luck. The finding is
recorded because a consumer written later must not assume that every sample in
this scan is finite.

## 5. A scripted gz-topic traction pulse, read on the bridged odometry

The command is published on the **gz** side with `gz topic`, deliberately
bypassing the ROS command topics, so that the motion read back on the bridged
`/forklift/odom` is evidence about the gz→ROS half of the bridge and about the
plant, and about nothing else.

```
   t[s]   sim_stamp        odom_x       odom_y      twist_vx
   0.50       71.750     -6.000000     0.000000      0.000000
   1.00       72.250     -6.000000     0.000000      0.000000
   1.50       72.750     -6.000000     0.000000      0.000000
   2.00       73.250     -6.000000     0.000000      0.000000
   2.50       73.750     -6.000000     0.000000      0.000000
   3.00       74.250     -6.000000     0.000000      0.000000
        gz topic -t /forklift/gz/traction_cmd -m gz.msgs.Double -p "data: 4.0"
   3.88       74.250     -6.000000     0.000000      0.000000
   4.00       75.250     -5.979729    -0.000030      0.343476
   4.50       75.750     -5.741175    -0.000434      0.479999
   5.00       76.250     -5.501176    -0.000911      0.479999
   5.50       76.750     -5.261177    -0.001444      0.479999
   6.00       77.250     -5.021178    -0.002021      0.480000
   6.50       77.750     -4.781179    -0.002633      0.480000
   7.00       78.250     -4.541179    -0.003274      0.480000
   7.50       78.750     -4.301180    -0.003937      0.480000
   8.00       79.250     -4.061181    -0.004617      0.480000
   8.50       79.750     -3.821182    -0.005311      0.480000
   9.00       80.250     -3.581183    -0.006016      0.480000
        gz topic -t /forklift/gz/traction_cmd -m gz.msgs.Double -p "data: 0.0"
   9.87       80.250     -3.581183    -0.006016      0.480000
  10.00       81.250     -3.123030    -0.007384      0.121875
  10.50       81.750     -3.121976    -0.007387      0.000000
  11.00       82.250     -3.121976    -0.007387      0.000000
  11.50       82.750     -3.121976    -0.007387      0.000000
  12.00       83.250     -3.121976    -0.007387      0.000000
  12.50       83.750     -3.121976    -0.007387      0.000000
  13.00       84.250     -3.121976    -0.007387      0.000000
  13.50       84.750     -3.121976    -0.007387      0.000000
  14.00       85.250     -3.121976    -0.007387      0.000000
  14.50       85.750     -3.121976    -0.007387      0.000000
  15.00       86.250     -3.121976    -0.007387      0.000000

x at pulse on   : -6.000000
x at pulse off  : -3.581183
x at end        : -3.121976
travel under pulse : 2.418817 m in 6.0 s
coast after pulse  : 0.459207 m
```

Four things this shows at once.

- **The position changes, and it is the bridged odometry that says so.** The
  vehicle starts at the spawn `x = -6.000000` and ends at `-3.121976`, having
  moved 2.878 m up the aisle without leaving it (`odom_y` stays inside
  7.4 mm).
- **The unit chain is intact.** 4.0 rad/s at the 0.12 m wheel is 0.48 m/s, and
  `twist_vx` reads `0.480000`. Independently, the position samples from
  `t = 4.50` to `t = 9.00` give `2.159992 m / 4.50 s = 0.479998 m/s`. m4f-02
  measured `0.4799968925779739` for the same command in its own world, so the
  arena has not changed the vehicle.
- **The stamps are simulation time.** `sim_stamp` advances 0.500 per 0.500 s
  of wall clock, which is the real-time factor of section 1 seen from the ROS
  side, and it is the `use_sim_time:=true` default in effect.
- **Zero means stop, and stopping takes distance.** The tricycle coasts
  0.459 m after the command goes to zero and is stationary by `t = 10.50`.
  There is no braking model in this world and none belongs here: `0.0` is a
  raw velocity command applied as given, and deciding when to send it is the
  PLC's job.

The two rows sampled at `3.88` and `9.87` are the timer tick during which the
`gz topic` call is made; they repeat the previous sample because the pulse
process had not yet returned.

## 6. The other direction: a ROS publish moves the joint

Section 5 exercised gz→ROS. This one exercises ROS→gz and reads the result
back through the bridge, so both halves are shown on the same run.
`ros2 topic pub -r 10 /forklift/gz/steer_cmd std_msgs/msg/Float64 '{data: 0.60}'`,
with `/forklift/joint_states` read after each step:

```
--- joint states at rest
joint                       position                 velocity
steer_joint              -0.00017171240789471      3.8616536621461e-06
drive_wheel_joint              23.98493560813      2.3569618377093e-15
mast_joint               -5.0194565116749e-14      4.0154926079312e-18

--- 5 s after publishing 0.60 rad on the ROS side of /forklift/gz/steer_cmd
joint                       position                 velocity
steer_joint                  0.56972682821894       0.0074666304334876
drive_wheel_joint             23.984935606388     -4.3513545977552e-10
mast_joint               -5.0194349095251e-14     -2.7131584579322e-18

--- 5 s after commanding 0.0 rad again
joint                       position                 velocity
steer_joint                 0.047713754551784       -0.012847094640605
drive_wheel_joint             23.984935606167      2.4078085345232e-11
mast_joint               -5.0194576821402e-14      8.9633952920736e-19
```

0.570 rad five seconds after a 0.60 rad request, still closing, and back
through 0.048 rad five seconds after the request returns to zero. That is the
asymptotic approach m4f-02 characterised (0.553 at three seconds there), so
the steer behaves in this arena as it did on the bare test world. The drive
wheel angle is unchanged to nine figures across all three reads, which is the
vehicle standing still while it steers.

## 7. Launch log

```
total lines : 19
ERROR lines : 0
WARN lines  : 0

=== spawn ===
[create-2] [INFO] [spawn_forklift]: Requesting list of world names.
[create-2] [INFO] [spawn_forklift]: Entity creation successful.
```

Nineteen lines total, none of them an error or a warning. The spawn is
resolved by asking the running server for its world name rather than by
hard-coding one, so overriding `world:=` on the command line stays correct
without a second argument having to be remembered.

One further line appears only once traffic crosses ROS→gz, and its absence
before that is why section 3 had to drive the command topics to measure them:

```
[parameter_bridge-3] [INFO] [forklift_arena_bridge]: Passing message from ROS std_msgs/msg/Float64 to Gazebo gz.msgs.Double (showing msg only once per type)
```

## 8. Isolation and cleanup

Every process signalled was one this run had started, matched against observed
`pgrep -af` output rather than assumed:

```
=== pgrep before signal (my run only) ===
54571 /usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch .../sim/launch/forklift_bringup.launch.py
54644 /bin/sh -c ruby .../gz sim -r -s .../sim/worlds/forklift_arena.sdf --force-version 8
54646 gz sim -r -s .../sim/worlds/forklift_arena.sdf
54647 /opt/ros/jazzy/lib/ros_gz_bridge/parameter_bridge /clock@... -r __node:=forklift_arena_bridge ...
=== pgrep after SIGINT ===
killing leftover pid 54571
killing leftover pid 54644
killing leftover pid 54646
killing leftover pid 54647
(none left)
=== other agents' processes, untouched ===
(none running)
```

**`SIGINT` to the launch pid did not bring the group down inside 6 s**, so the
four pids were killed individually by exact pid. Recorded because it is a
property of this bringup a later scenario script has to plan for: signal the
launch, then verify with `pgrep` and finish the job, rather than assuming the
signal was enough. The gz server command line carries the world path and the
bridge carries its node name, so a pattern of `forklift_arena` matches this
run and nothing else on the machine.

## 9. Render budget of the M5 sensor set, and the beams on screen

**Separate run, separate date, separate machine from sections 1 to 8.** Those
sections are the M4 record: one 181-sample scanner on `/forklift/gz/scan`, WSL2
on the owner's laptop, 2026-07-29. This section was taken on 2026-07-31 in the
project container against the M5 sensor set that brief m5-04 landed, and it does
not restate or replace anything above. Where the two disagree on a topic name or
a sample count, the M4 record is describing a model that no longer exists.

| Item | Value |
|---|---|
| Date | **2026-07-31**, 06:49–07:14 UTC |
| Host | project container, 4 cores (`nproc` = 4) |
| Gazebo | `gz sim --versions` → `8.11.0` |
| Render | `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)`, `GL_VERSION = 4.5 (Compatibility Profile) Mesa 25.2.8-0ubuntu0.24.04.2`, read from `/root/.gz/rendering/ogre2.log` after deleting it before the run |
| Display | `Xvfb :99 -screen 0 1600x1000x24`, GUI window 1200x1000 |
| World | `sim/worlds/forklift_arena.sdf` md5 `7a37ebe5a5ef290a32675170b5ce76f8` |
| Model | `agv/forklift/model.sdf` md5 `878819c911a7aea3b600faa56e2e52f6` |
| Sensor set | 910 rays per sweep at 10 Hz: 360 (`scan_nav`) + 275 + 275 (the two safety scanners' measurement channels) |
| Isolation | `GZ_PARTITION=m505_render`, `ROS_DOMAIN_ID=82` (and `m505_shot` / 84 for §9.4) |
| ERROR lines | 0 in the server log, 0 in either GUI log |

**Not a safety claim, and the pictures are the reason to say so twice.** Two of
the four window captures below show a *safety scanner* drawing beams. Those
beams are the device's **non-safe measurement channel** rendered by a debug
plugin. They are not a protective field, they are not an OSSD state, and no
screen in this project ever shows a protective field, because the safety
function is onboard and hardwired and has no topic on either transport
(invariant 1; `agv/forklift/README.md`).

### 9.1 What the world had to gain for beams to be possible

`<visualize>true</visualize>` on the sensor is necessary and not sufficient in
Harmonic. The `<gui>` block added to `forklift_arena.sdf` loads `VisualizeLidar`
alongside `MinimalScene`, `GzSceneManager`, `InteractiveViewControl`,
`CameraTracking`, `EntityContextMenuPlugin`, `WorldControl`, `WorldStats` and
`Screenshot`. Read back from the committed file:

```
gui plugins: ['MinimalScene', 'GzSceneManager', 'InteractiveViewControl',
              'CameraTracking', 'EntityContextMenuPlugin', 'WorldControl',
              'WorldStats', 'VisualizeLidar', 'Screenshot']
```

The plugin binary is present in this container at
`/opt/ros/jazzy/opt/gz_sim_vendor/lib/gz-sim-8/plugins/gui/libVisualizeLidar.so`.

### 9.2 Beams are three clicks in, and the first ones are the wrong sensor

The instrument for "is the plugin actually drawing" is not the picture, it is
`gz topic -i`: `VisualizeLidar` subscribes to exactly the topic its combo box
has selected, so a subscriber on a scan topic **is** a beam being drawn, and no
subscriber is no beam. Measured, in order, on one GUI session:

| GUI state | `gz topic -i -t /forklift/gz/scan_nav` | front safety scanner |
|---|---|---|
| GUI up, no interaction | `No subscribers on topic [/forklift/gz/scan_nav]` | `No subscribers` |
| after pressing refresh | `No subscribers` | **`Subscribers: tcp://192.0.2.2:43705`** |
| after selecting `scan_nav` | **`Subscribers: tcp://192.0.2.2:43705`** | `No subscribers` |

So: the world loads the plugin, the plugin comes up with an **empty** topic list
and draws nothing, and pressing refresh selects **entry zero of a sorted list**,
which is `/forklift/gz/safety_scanner_front/measurement`. The navigation lidar is
entry two. The combo box contents, read off the open dropdown, were exactly:

```
/forklift/gz/safety_scanner_f...     <- selected by refresh
/forklift/gz/safety_scanner_r...
/forklift/gz/scan_nav
```

The same three-step sequence was repeated on a second, fresh GUI session with
the same result, including `No subscribers` before the first click.

### 9.3 The render budget, measured

`real_time_factor` on `/stats` is published **once per physics iteration** in
this world — 500 Hz, not the 5 Hz a reader would assume — and it is an
instantaneous value: one 60-sample capture ranged `0.4803` to `3.3703` with a
median of `1.0000`. It is useless as a single reading. Every figure below is
therefore the ratio of differences between two `/stats` messages 60 s of wall
clock apart, with both messages kept verbatim. The worked example, from the
Rays measurement:

```
--- /stats at t0 ---
sim_time  { sec: 836 nsec: 154000000 }
real_time { sec: 950 nsec: 396211256 }
iterations: 418077
real_time_factor: 1.0009979950010159
step_size { nsec: 2000000 }

--- /stats at t1 (+60 s wall) ---
sim_time  { sec: 889 nsec: 630000000 }
real_time { sec: 1010 nsec: 531226926 }
iterations: 444815
real_time_factor: 1.42360001395128
step_size { nsec: 2000000 }

RESULT  d_sim=53.476 s  d_real=60.135 s  d_iterations=26738  RTF(window)=0.8893
```

Session B is the primary set: one server process, one GUI attached to it, the
navigation lidar selected directly, and only the plugin's own controls changed
between rows. Session A ran first and had the front safety scanner selected
before the navigation lidar; it is kept because it is the run the Rays/Strips
comparison was first taken on.

| # | Configuration | `d_sim` | `d_real` | RTF over the window |
|---|---|---|---|---|
| F | **headless**, server only, no GUI client | `60.006` | `60.128` | **`0.9980`** |
| G | GUI attached, `VisualizeLidar` loaded, **no topic selected** | `55.118` | `60.139` | **`0.9165`** |
| H | GUI, beams **on**, navigation lidar, Triangle Strips | `53.668` | `60.147` | **`0.8923`** |
| I | GUI, beams **off** (checkbox), subscription still held | `55.164` | `60.132` | **`0.9174`** |
| J | GUI, beams **on**, navigation lidar, **Rays** | `53.476` | `60.135` | **`0.8893`** |
| K | GUI, beams **off** again (drift bracket) | `54.968` | `60.162` | **`0.9137`** |

Session A, same instrument, front safety scanner selected first:

| # | Configuration | RTF over the window |
|---|---|---|
| C | GUI, beams on, navigation lidar, Rays | `0.8221` |
| D | GUI, beams on, navigation lidar, Triangle Strips | `0.8371` |
| E | GUI, beams off (checkbox), subscription held | `0.8397` |

What the numbers say:

- **Headless is still real time at 910 rays.** `0.9980`. Adding two scanners
  and moving from 181 rays to 910 did not cost the headless run its real-time
  factor; the M4 figure it is being compared against is `0.99984`.
- **The GUI costs about 8 points of RTF, and the beams cost about 2.5.**
  `0.9980` → `0.9165` for attaching the GUI at all; `0.9174`/`0.9137` → `0.8923`
  for switching the navigation lidar's beams on. The GUI is roughly three times
  the cost of the thing it was added to show.
- **Rays and Triangle Strips cost the same here**, `0.8893` against `0.8923`,
  which is inside the drift bracket the two beams-off readings define
  (`0.9174`, `0.9137`). At 360 rays the mode is a viewer's choice, not a budget
  decision. Points was not measured.
- **Between-session spread is larger than the beam cost.** Session A sits about
  0.08 below session B at every equivalent state. The two sessions differ in
  that A had selected the front safety scanner before the navigation lidar, so
  the plausible cause is a lidar visual left in the scene by the first
  selection — unproven, and the reason the deltas above are all taken *within*
  a session and never across the two.
- The GUI's own `WorldStats` readout, cropped from the captures at the moment
  of measurement, showed `92.57 %` during row H and `88.42 %` during row J. It
  corroborates the order of magnitude and is not what the table is computed
  from.

**Is the GUI usable in this container?** Yes, at 1200x1000 with beams on: the
window is responsive to clicks, the beams update, and the simulation holds
`0.89` of real time. That is a finding about *this* container, on `llvmpipe`,
with 4 cores, and the showcase runs on the owner's machine — which reports the
same `llvmpipe (LLVM 20.1.2, 256 bits)` (`sim/setup/WSL_ENVIRONMENT.md` §4.7)
but is not the same box and has not been re-measured. **Every figure in this
section is container evidence and does not transfer** (LESSONS 2026-07-27).

### 9.4 The captured artifacts

Five files, in `sim/worlds/evidence/`:

| File | What it shows |
|---|---|
| `m5-05-gui-no-beams.png` | the GUI as this world opens it: `VisualizeLidar` docked, combo box **empty**, no beams anywhere. This is the beams-off control for the table above |
| `m5-05-beams-safety-scanner-front-strips.png` | what one press of refresh gives you: the **front safety scanner's measurement channel**, `Min. Range 0.100000`, `Max. Range 5.500000`, Triangle Strips. Not a protective field |
| `m5-05-beams-nav-lidar-strips.png` | the **navigation lidar** selected: `Min. Range 0.100000`, `Max. Range 8.000000`, Triangle Strips, the full 360° disc |
| `m5-05-beams-nav-lidar-rays.png` | the same sensor in **Rays**, panel showing `/forklift/gz/scan_nav` and `Visual Type: Rays`. This is the beam capture the gate asks for |
| `m5-05-beams-nav-lidar-3dview-service.png` | the same beams captured through the `/gui/screenshot` service instead of the window manager |
| `m5-05-beams-nav-lidar-launch-guitrue.png` | the composed path: `ros2 launch sim/launch/forklift_bringup.launch.py gui:=true`, world + spawn + ROS bridge + GUI in one command, navigation lidar beams drawn |

The four window captures are X11 root-window grabs, cropped to the 1200x1000 GUI
window. They include the plugin's panel deliberately: **which scanner is on
screen is not guessable from the beams**, and a beam picture with no panel in it
is a caption waiting to go wrong.

`/gui/screenshot` behaves differently from what its request field suggests, and
this was measured rather than assumed:

```
--- request A: full file path "<dir>/shots/scene_a.png" ---   data: true
--- request B: directory path "<dir>/shots"               ---   data: true
--- request C: empty                                      ---   data: true
--- files under <dir>/shots ---
2026-07-31T07:13:50.188986108.png
2026-07-31T07:13:54.546317036.png
```

Two requests, two files, **neither named as asked**: the string is a directory
and the plugin names the file from the capture timestamp. The third request
returned `data: true` and wrote no file that a `find / -xdev -name '*.png'`
newer than the request could locate. The service output is 831x952 — the 3D
view only, no panel.

### 9.5 One thing the pictures show that is not about rendering

In `m5-05-beams-nav-lidar-strips.png` the navigation lidar's disc floats
**above** the arena's walls and crates. That is correct and it is the geometry
`agv/forklift/README.md` warns about in prose: the navigation plane is at
z = 1.80 m, the arena's walls stop at 0.60 m and its tallest crate at 1.00 m, so
this sensor reports a clear horizon over an obstacle a process stop has to see.
The obstacle evaluator reads the front safety scanner at z = 0.15 m for exactly
that reason. Nothing in this section changes that; it is recorded because the
picture makes the argument in one glance and the prose takes a paragraph.

### 9.6 The launch file's own `gui:=true` path, and what it costs the scan rate

Rows F to K attached `gz sim -g` by hand to a server started by hand, which is
the controlled arrangement but is not what anybody types. The composed path was
run separately, `GZ_PARTITION=m505_guitrue` / `ROS_DOMAIN_ID=85`, on `Xvfb :97`:

```
ros2 launch sim/launch/forklift_bringup.launch.py gui:=true
```

One command brought up the world, the spawn, the ROS bridge and the GUI: 8
`Creating ... Bridge` lines, **0 ERROR lines**, and after the same three clicks
the navigation lidar beams were on screen
(`worlds/evidence/m5-05-beams-nav-lidar-launch-guitrue.png`). `gz topic -i -t
/forklift/gz/scan_nav` showed **two** subscribers in this configuration, which
is the correct count and a useful cross-check: one is `ros_gz_bridge`, one is
`VisualizeLidar`.

The number worth carrying forward is what the GUI does to the bridged sensor
rate on this box:

| Configuration | `ros2 topic hz /forklift/scan`, first window |
|---|---|
| headless (`gui:=false`, the default) | `average rate: 9.995`, min `0.098s` max `0.104s`, window 12 |
| `gui:=true` | `average rate: 8.488`, min `0.101s` max `0.132s`, window 10 |

The scanner is declared at 10 Hz in both cases. Attaching the GUI costs about
1.5 Hz of it, which is the same story the RTF table tells — the simulation runs
slower, so a sensor tied to simulation time publishes less often in wall-clock
terms. **Any consumer whose timeout assumes 10 Hz must be checked against 8.5 Hz
before a GUI run is used for anything but looking at.** The obstacle evaluator's
0.50 s staleness window survives this comfortably; nothing else was checked.

## What this does not establish

1. **Nothing about safety.** No protective field, no e-stop chain, no STO. The
   obstacle props are geometry, and the stop-zone threshold that will act on
   them is a process parameter evaluated outside this world (invariant 1).
2. **Nothing about the PLC loop.** Under ADR 0008 every command reaches the
   simulation through HMI → PLC → bridge and every state report returns the
   same way. This run drove the plant directly from a shell, which is
   commissioning stimulus, not the gate's command path.
3. **Nothing about the vehicle nodes.** `forklift_io.py` and
   `obstacle_zone.py` were not started here; `agv/forklift/launch/vehicle.launch.py`
   owns them and `agv/forklift/EVIDENCE_MODEL.md` is their record. No topic
   under `/forklift/cmd/`, `/forklift/fork_height`, `/forklift/linear_speed`
   or `/forklift/obstacle/` existed during this run.
4. **Nothing about lifting a load.** `Pallet` and `LoadBox` were spawned and
   stood still. Nothing was picked up, no fork was raised against a payload,
   and the m4f-02 carriage tuning figures remain figures for the **unloaded**
   carriage. The mass arithmetic in the world file argues the load is
   plausible against the controller's measured clamp; it does not show that it
   lifts.
5. **Nothing about the stop-zone scenario.** The arena is placed so that
   driving the aisle centreline meets `AisleCrate` head on, and the arithmetic
   for where the zone trips is written into the world file. The scenario
   itself, and the PLC reaction it is there to demonstrate, are later work.
6. **Nothing about navigation.** No map, no AMCL, no Nav2, no VDA 5050. The
   odometry above is simulator ground truth, not a localisation solution, and
   the forklift carried no navigation claim at M4 (ADR 0008 D5; ADR 0010
   D1/D2 give it one at M5, which nothing in this run anticipates).
7. **Nothing about hardware acceleration.** Rendering was llvmpipe. The
   scanner budget of 181 samples at 10 Hz and the arena's texture-free,
   shadow-free scene were chosen against that, and raising either without
   re-measuring changes the figures above.
8. **Nothing about a GUI.** `gui:=true` exists as an argument and was not
   exercised; every figure in sections 1 to 8 comes from a server-only run.
   **Superseded by section 9**, which attaches a GUI and measures it — on a
   different date, a different machine and a different sensor set. The
   render-budget rows use `gz sim -g` attached to a server started by hand, to
   keep the configuration under control; `gui:=true` is exercised separately in
   §9.6 and works, at a measured cost to the bridged scan rate.
9. **Nothing about the owner's machine, for section 9.** Section 9 is container
   evidence. The container and the owner's WSL host both report `llvmpipe (LLVM
   20.1.2, 256 bits)`, which makes the numbers plausible there and does not make
   them measured there. The showcase recording is on the owner's machine and
   needs its own capture (LESSONS 2026-07-27: evidence is qualified by the
   environment that produced it).
10. **Nothing about a moving vehicle, for section 9.** Every render-budget row
   was taken with the forklift standing at its spawn pose. Driving it changes
   what the scanners hit and what the beam visual has to redraw, and none of
   these figures cover that.
