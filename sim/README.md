# sim

## This layer must not access

- MuJoCo. Simulation is Gazebo only (invariant 12).
- Production logic. Worlds, launch files and scenarios exercise the stack; they must not reimplement fleet, PLC or safety behavior, and simulated safety shortcuts must not leak into agv/, fleet/ or plc/ (invariants 7, 11).
- Layer bypasses. Test scenarios drive the system through its real interfaces (VDA 5050 topics, OPC UA nodes), never by injecting state directly into another layer's internals (invariant 11).
- Secrets. Simulation configs carry no credentials, certificates or tailnet keys (invariant 13).

Owns: Gazebo warehouse worlds, launch files, and end-to-end test scenarios.

---

## Contents

```
sim/
  worlds/cell.sdf                   M3 fixed-equipment demonstration cell
                                    (conveyor, product, photo-eye, panel)
  worlds/CELL_EVIDENCE.md           dated verification record of the cell run
  launch/cell_bringup.launch.py     one-command headless cell bringup + bridge
  worlds/forklift_arena.sdf         M4 forklift commissioning arena
                                    (24 x 16 hall, drive aisle, obstacle props)
  worlds/FORKLIFT_ARENA_EVIDENCE.md dated verification record of the arena run
  launch/forklift_bringup.launch.py one-command headless arena bringup + spawn
  worlds/warehouse.sdf              M5 autonomy world: 30 x 20 hall, three
                                    rack rows cut by a central cross aisle,
                                    two end aisles, building columns, dock
                                    door, transfer station, two charging
                                    bays, safety zone marking
  worlds/WAREHOUSE_EVIDENCE.md      dated bringup record of that world, and
                                    the citable charging bay register
  worlds/WAREHOUSE_LANDMARKS.md     measured landmark availability at the
                                    navigation scan plane, produced BEFORE
                                    any SLAM run; names the degenerate
                                    stretches
  worlds/WAREHOUSE_SLAM_EVIDENCE.md the SLAM mapping run, read against that
                                    prediction stretch by stretch
  worlds/BRINGUP_EVIDENCE.md        HISTORICAL ONLY: the retired RB-KAIROS
                                    platform's headless run, in the world as
                                    it was before m5-08
  launch/warehouse_bringup.launch.py  one-command headless bringup + forklift
                                    spawn + the vehicle's estimator stack
                                    (wraps forklift_bringup)
  launch/warehouse_slam.launch.py   slam_toolbox online_async against a
                                    running warehouse bringup
  config/slam_toolbox_warehouse.yaml  its parameters; every non-default
                                    carries its reason on the line above it
  maps/warehouse/                   THE warehouse map. warehouse.pgm/.yaml
                                    for AMCL, warehouse.posegraph/.data to
                                    resume mapping. Built by SLAM, not
                                    rasterised
  setup/install.sh                  idempotent environment setup (run as root)
  scenarios/
    forklift_commissioning.md       M4 gate procedure: the five criteria as
                                    owner-runnable scenarios, with the evidence
                                    checklist and the rehearsal record
    forklift_stimulus.py            the M4 stimuli: hold a control at the HMI,
                                    move the aisle crate, transcribe /state
    run_forklift_rehearsal.py       rehearsal harness for the five scenarios
                                    against the PLC logic double
    warehouse_mapping_route.py      the stated mapping route, driven as a
                                    scripted stimulus; the route is a
                                    constant in the file
    tools/landmark_map.py           landmark availability of a world at a
                                    scan plane, from geometry alone
    tools/make_map.py               deterministic map generator (world -> map),
                                    rectangles read from the SDF at run time.
                                    Has NO committed output; see below
    tools/mapping_evidence.py       record and read a mapping run: /tf
                                    publishers, the three pose streams, the
                                    named degenerate stretches, the closures
    nav_scenario.launch.py          Nav2 stack of the parked scenario
                                    (map_server, AMCL, planner, DWB
                                    controller, behaviors, bt_navigator);
                                    parked, not runnable, see DEFERRED.md
    run_scenario.py                 scripted NavigateToPose run + evidence;
                                    parked, not runnable, see DEFERRED.md
    EVIDENCE_NAV.md                 dated capture of a successful headless run
```

## Reproducible setup

Target: Ubuntu 24.04 (noble), amd64. The container's outbound HTTPS goes
through a proxy; `api.github.com` is blocked but
`raw.githubusercontent.com` and plain `git clone` work. Everything below
respects that.

The whole recipe is automated in `sim/setup/install.sh` (idempotent,
check-before-do, safe to re-run). What it does, step by step:

### 1. python3 -> 3.12 (container quirk)

The container ships python3.11 as the default `python3`, but ROS 2 Jazzy on
noble is built against python3.12. Without the switch, every ROS Python
entry point fails on import.

```
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 2
update-alternatives --set python3 /usr/bin/python3.12
```

### 2. ROS 2 apt source (proxy-safe)

Do not use the `ros-apt-source` release-asset method: it needs
`api.github.com`, which the proxy blocks. Fetch the key directly from
`raw.githubusercontent.com` and use the plain-http package mirror:

```
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main" \
  > /etc/apt/sources.list.d/ros2.list
apt-get update
```

### 3. Packages

```
apt-get install -y \
  ros-jazzy-ros-base ros-jazzy-xacro \
  ros-jazzy-robot-state-publisher ros-jazzy-joint-state-publisher \
  ros-jazzy-gz-sim-vendor ros-jazzy-ros-gz \
  ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-slam-toolbox \
  python3-colcon-common-extensions python3-rosdep python3-vcstool git
```

`ros-jazzy-gz-sim-vendor` provides Gazebo Harmonic (gz sim 8), per ADR 0003.

`ros2_control` is deliberately absent. It was here for the retired vehicle
platform's vendor mecanum drive; the forklift drives through gz
joint-controller plugins and a vehicle node. If a later gate needs it, add it
to `install.sh`'s `ROS_PKGS` and re-verify.

## The warehouse world (M5 autonomy)

**Current work.** The owner ruled on 2026-07-30 that M5's SLAM and Nav2
autonomy runs in the warehouse world rather than in the M4 commissioning
arena: autonomy needs aisles and racks to be meaningful, and M6 enlarges
this same world to ten stations, so the map artifact and the Nav2 tuning
carry forward instead of being discarded. The arena keeps its M4
commissioning role, and neither world includes the other.

`worlds/warehouse.sdf` was rewritten for that at m5-08 and
`launch/warehouse_bringup.launch.py` now spawns the in-house forklift. That
launch wraps `forklift_bringup.launch.py` for the world, the spawn and the
bridge — there is one topic contract for this vehicle and one launch file
that states it — and adds the one thing an autonomy world needs that a
commissioning arena does not: **the vehicle's own pose estimate.**

```
export GZ_PARTITION=myrun ROS_DOMAIN_ID=42     # isolate BOTH transports
ros2 launch sim/launch/warehouse_bringup.launch.py
```

That starts `agv/forklift/scripts/sensor_tf.py`, `scripts/wheel_odometry.py`
and the `robot_localization` EKF with `agv/forklift/ekf.yaml` (all three are
`agv/`'s; this layer starts them and owns none of them). **The EKF is the
sole publisher of `forklift/odom -> forklift/base_link`, and no launch file
in `sim/` bridges the simulator's ground-truth transform or offers an
argument that would** — `ros2 topic info /tf --verbose` on this bringup
reports `Publisher count: 1`, captured in
`worlds/WAREHOUSE_SLAM_EVIDENCE.md` §3. Pass `estimator:=false` for the bare
plant, which then has no transform tree and cannot carry SLAM, AMCL or Nav2.

### SLAM, and the map

```
ros2 launch sim/launch/warehouse_slam.launch.py      # beside the bringup
```

`online_async`, not `online_sync`: rendering here is llvmpipe software
rasterisation and a scan match that overruns the 0.1 s scan period stalls a
synchronous callback. **`async_slam_toolbox_node` is a lifecycle node and
does nothing whatever until it is transitioned** — started as a plain `Node`
it logs one line, subscribes to nothing and publishes no transform, with no
warning of any kind. That launch file emits the configure and activate
transitions; the check that it worked is `/map` on the topic list, never a
clean log.

`maps/warehouse/` is the map that run produced, in both forms: the
`.pgm`/`.yaml` pair AMCL consumes and the `.posegraph`/`.data` pair that
lets mapping resume rather than restart. It was built from the vehicle's own
scans against its own drifting odometry, over the route stated in
`scenarios/warehouse_mapping_route.py`, and read against
`worlds/WAREHOUSE_LANDMARKS.md` stretch by stretch. Both documents are worth
reading before any localisation parameter is chosen.

### The honesty rule the world obeys

A long featureless aisle is a **degenerate direction** for scan matching and
no slam_toolbox parameter fixes it. Everything in this world is there
because a real warehouse has it — rack uprights, rack ends, stock present in
some bays and absent in others, cross and end aisles, building columns, a
dock door frame, a transfer station frame, a charging area. **Nothing was
scattered into an aisle because scan matching struggles without it**, and
where the honest world still leaves a degenerate stretch, that stretch is
measured and named rather than landscaped away.

`worlds/WAREHOUSE_LANDMARKS.md` is that measurement, produced from geometry
**before** any SLAM run, so the SLAM result can be read against a prediction
instead of being the only number anyone sees. It names three degenerate
stretches, all in the fully-loaded east half of the hall. Read it before
tuning any localisation parameter against this world.

### Charging bays

Two bays in the dock apron, added at m5-08 on the owner's instruction:
`ChargeBay1Marking` / `ChargeBay1Cabinet` and `ChargeBay2Marking` /
`ChargeBay2Cabinet`. **Geometry plus names and nothing else** — no docking
behaviour, no approach logic, no charging state, no PLC or fleet
interaction; that planning arrives with fleet management at M6. The poses,
the sizing arithmetic and what each part shows at each scan plane are in
`worlds/WAREHOUSE_EVIDENCE.md` section 5, which is the document a later
fleet brief cites rather than re-measuring the SDF. The M3-era
`ChargerStation` placeholder was **replaced** by these, not kept beside
them.

### The rasteriser, which now has no committed output

`scenarios/tools/make_map.py` rasterizes the static world geometry rather
than SLAM-mapping it, because that is deterministic, reproducible in seconds
and diffable against the world file. Its rectangles are read from the SDF at
run time; the hand-copied list it used to carry could not survive a change
to the world, and did not.

**`scenarios/maps/` was DELETED on 2026-07-31 by m5-08b.** It held a grid
rasterized from the pre-m5-08 world for the retired vehicle — a picture of a
building this repository no longer contains. Its source of truth was gone,
its only consumers are the two parked scripts beside it (whose Nav2
parameter file m5-09 had already deleted), and it is regenerable in seconds
by the tool above. The generator is the artifact; its output was not. And
with `maps/warehouse/` now holding a map that has an owner, keeping a second
one that is nobody's would be a datum with two answers (invariant 10).

`make_map.py` itself is untouched and still useful — as the second opinion
against the SLAM map, and as the generator for whatever static map m5-10
decides Nav2 wants. It still requires an explicit `--z` and has no default,
because which scan plane a static map represents — the navigation lidar's
1.80 m, or a lower plane carrying what a vehicle can collide with — remains
a Nav2 configuration decision belonging to **m5-10**. That question is
untouched by the deletion.

## What is still parked

| File | Status |
|---|---|
| `scenarios/nav_scenario.launch.py` | the Nav2 node set of the retired platform's scenario; `params_file` is a required argument with no file to satisfy it |
| `scenarios/run_scenario.py` | the scripted NavigateToPose run; still names the retired vehicle's odometry topic |
| `worlds/BRINGUP_EVIDENCE.md` | historical record of the retired platform in the pre-m5-08 world; cite nothing from it |

Whether the two scenario scripts survive migration is **m5-10 briefing
work**. Full status: `sim/scenarios/DEFERRED.md`.

### Nav2 configuration: nothing carried forward

There is no Nav2 parameter file in this repository. The parked scenario's
one was written entirely around the retired vehicle — omni motion model, its
scan, odometry and command topics, its frame tree, its footprint — and the
owner ruled it is **not a migration candidate**. It was deleted by m5-09
(ADR 0010 D1). The forklift's configuration is written from scratch at
m5-10: tricycle kinematics, one navigation lidar, its own frame tree.

Two settings from the parked run are worth carrying into that brief as
container findings rather than as configuration, because they are properties
of the host and not of the vehicle:

- `lifecycle_manager` needed `bond_timeout: 0.0`; bond heartbeats starve at
  RTF ~0.1 and would otherwise take the servers down.
- Speeds had to be capped low (0.45 m/s in the parked run) for the slow
  headless sim to track commands.

### Known behavior

- The ~0.1 headless real-time factor recorded for the pre-m5-08 world was
  the retired platform's figure, and it included an RGBD camera this project
  does not carry. **Superseded 2026-07-31 by m5-08b**, which had the machine
  to itself: this world runs at `real_time_factor: 0.99934892417589938`
  headless with the vehicle and its estimator, and at 0.9831 simulation
  seconds per wall second with slam_toolbox running as well
  (`worlds/WAREHOUSE_SLAM_EVIDENCE.md` §2).
- **The EKF integrates about 0.0023 rad/s of heading on a stationary
  vehicle** — 8° per minute — because it fuses a modelled gyro bias against
  a wheel odometry that correctly reports zero yaw rate, with no
  zero-velocity update. Consequence for anyone mapping: the map frame is
  anchored to the vehicle's heading ESTIMATE at the first scan, so idling
  the stack before driving rotates the finished map away from the building
  by that much. Start the drive as soon as slam_toolbox is active. Measured
  twice per run in `worlds/WAREHOUSE_SLAM_EVIDENCE.md` §8.
- The world's south wall has a free 4 m opening marked by the `DoorGap`
  posts/lintel; the PLC-controlled door and the conveyor/charger handshakes
  act there at M6 (ADR 0010). The blocks are geometry only — no
  fleet, PLC or safety behavior is simulated here (see the first section).
- Two `python3` interpreters are on PATH here. `/usr/local/bin/python3` is
  3.11 and runs the stdlib-only tools in `scenarios/tools/`;
  `rclpy` is built for 3.12 and imports only under `/usr/bin/python3`. A
  script that subscribes to a topic must be run with the latter.

---

# Demonstration cell (M3)

`worlds/cell.sdf` + `launch/cell_bringup.launch.py` are the M3 gate work
under ADR 0004: prove the Gazebo-to-PLC signal loop with **fixed equipment
only**, before any mobile robot. There is no vehicle in this world and
none belongs in it. The warehouse world above is the M5 autonomy world and
the two Nav2 scenario scripts beside it are still parked; neither is
touched by this.

## What is in the cell

```
        +y
         ^
         |            [ProductSensor]   emitter post at y = +0.75
         |                   :          single beam, z = 0.60, aimed at -y
      ---+---[ Conveyor frame 8.0 x 1.0 x 0.4, belt top z = 0.46 ]----> +x
         |            [ProductBox]      0.3 m cube, starts at x = -1.00
         |                   :
         |            [SensorReflector] post at y = -0.80
         |
      [OperatorPanel] pedestal at (-2.60, -1.40), geometry only
```

- **Conveyor** — a belt slab on a prismatic joint, driven by gz
  `JointController` as a raw signed velocity. Mechanical travel is
  ±2.50 m. The product rides the belt by friction; it is transported, not
  teleported (the evidence file shows `boxX` tracking `beltPos` with a
  constant offset).
- **ProductBox** — the transported product, 0.30 m cube, 2 kg.
- **ProductSensor** — a retro-reflective photo-eye, modelled as a
  single-beam `gpu_lidar` firing across the belt at x = +0.50 towards a
  reflector post. It publishes a **distance**, not a detected bit.
- **OperatorPanel** — a pedestal with a green Start, a black Stop and a
  red process-stop mushroom on the upper row, and a blue Reset on the
  lower row. Geometry only: the contacts themselves are ROS topics created
  by the bridge, because a pushbutton has no physics worth simulating.

## Signal table

This table is the I/O list for the cell. It is the direct input to the
m3-02 OPC UA node model; the names in the first column are *proposed*
signal names in the project's PascalCase tag style, and m3-02 owns the
authoritative tag and node naming.

Direction is written from the PLC's point of view, because the PLC is the
owner of every process decision in this cell:

- **cell → PLC (PLC input)** — raw device state the program reads.
- **PLC → cell (PLC output)** — raw actuator command the program writes.

| Signal | ROS 2 topic | Message type | Field | Direction | Physical meaning |
|---|---|---|---|---|---|
| `ConveyorSpeedCmd` | `/cell/conveyor/cmd_speed` | `std_msgs/msg/Float64` | `data` | PLC → cell | Belt surface velocity command, m/s, signed. Positive transports the product towards +x, negative reverses, `0.0` stops. Applied as given: no ramp, no limit, no interlock in the cell. Verified at ±0.15 m/s. |
| `ConveyorBeltPosition` | `/cell/conveyor/joint_state` | `sensor_msgs/msg/JointState` | `position[0]` | cell → PLC | Belt travel from home, m. Raw encoder value. Range −2.50 … +2.50 (mechanical stops). `name[0]` is `belt_joint`. |
| `ConveyorBeltSpeed` | `/cell/conveyor/joint_state` | `sensor_msgs/msg/JointState` | `velocity[0]` | cell → PLC | Measured belt velocity, m/s, signed. The read-back of `ConveyorSpeedCmd`; the PLC compares the two, the cell does not. |
| `ProductSensorRange` | `/cell/product_sensor/scan` | `sensor_msgs/msg/LaserScan` | `ranges[0]` | cell → PLC | Photo-eye beam distance, m. **1.440** with the belt clear (beam reaches the reflector), **0.540** with the product in the beam. `range_min` 0.05, `range_max` 3.0, `frame_id` `ProductSensor/post/beam`. **No threshold is applied in the cell** — converting this range into a `ProductPresent` bit is a process decision and belongs to the PLC. |
| `PanelStartContact` | `/cell/panel/start` | `std_msgs/msg/Bool` | `data` | cell → PLC | Start pushbutton contact, wired **NO**. `true` = contact closed = button pressed. |
| `PanelStopContact` | `/cell/panel/stop` | `std_msgs/msg/Bool` | `data` | cell → PLC | Stop pushbutton contact, wired **NC**. `true` = contact closed = button *not* pressed. `false` = pressed, or broken wire. |
| `PanelResetContact` | `/cell/panel/reset` | `std_msgs/msg/Bool` | `data` | cell → PLC | Monitored reset pushbutton contact, wired **NO**. `true` = contact closed = button held. `false` = released, or broken wire. Momentary: the cell publishes the level while the button is held and does **not** latch, stretch, debounce or edge-detect it. **The reset energizes nothing in the cell** — it is an input only, and every reset decision (the rising edge, which latches clear) is PLC logic. |
| `PanelProcessStopContact` | `/cell/panel/process_stop` | `std_msgs/msg/Bool` | `data` | cell → PLC | **Process** stop mushroom contact, wired **NC**. `true` = closed = not pressed. `false` = pressed, or broken wire. See the warning below. |
| *(diagnostic)* | `/cell/product_box/pose` | `geometry_msgs/msg/PoseArray` | `poses[0]` | cell → observer | Ground-truth product pose in the `cell` frame. **Not a PLC signal** — a real conveyor has no product-position transducer. It exists so belt transport is observable headless. Do not model it as an OPC UA node. |
| *(infrastructure)* | `/clock` | `rosgraph_msgs/msg/Clock` | `clock` | cell → observer | Simulation time. Not a PLC signal. |

### Polarity: wire NC, program NO

The two stop contacts are published as **NC contact state**, matching how
they are wired on real equipment, so that a lost signal reads as "stopped"
rather than "running" (see *Domain conventions* in `CLAUDE.md`). The cell
publishes the contact; it does not invert, latch, debounce or edge-detect
it. All of that is PLC work.

Start and **Reset** are the other case, and the difference is deliberate.
`CLAUDE.md` §9's "wire NC, program NO" is a rule about *stop and safety*
devices: they are wired closed so a broken wire fails to the stopped state.
A reset has the opposite fail-safe direction — it must fail to *not reset* —
so it is wired **NO** and reads `true` only while a hand is on it. Wiring a
reset NC would mean a cut wire, a welded contact or an absent publisher
continuously asserted "reset", which is precisely the automatic resume §9
forbids after a stop.

The reset is a button, not a state: the cell offers the contact and nothing
else. It clears no fault here, drives no actuator and never touches belt
state. The monitored reset behaviour §9 requires lives in the PLC program,
which triggers on the **rising edge** of this contact.

### Update rates measured in this container

| Topic | Rate | Why |
|---|---|---|
| `/cell/product_sensor/scan` | 30 Hz | sensor `update_rate` in the SDF |
| `/cell/conveyor/joint_state` | ~500 Hz | physics rate; gz's `JointStatePublisher` has no rate parameter, so the bridge decides how to decimate to the PLC scan rate |
| `/cell/product_box/pose` | 10 Hz | `PosePublisher` `update_frequency` |

### There is no initial value

ROS topics are not retained. Until something publishes, the four panel
contacts and the conveyor command have **no** value on the wire. Choosing
the value the PLC sees before the first publish is a bridge decision
(m3-04), and it must be the safe one: contacts read as pressed, belt
command reads as zero. For the NO reset that safe value is `false` —
**not** pressed — because a reset that defaults to asserted would clear a
latch the instant the bridge started.

### The red button is a PROCESS stop

`/cell/panel/process_stop` is a process stop implemented in the standard
program. It is **not** a safety function, it carries no safety integrity,
and it must never be labelled, demonstrated or recorded as an emergency
stop. The safety e-stop chain is hardwired to the F-CPU and never crosses
the network (invariant 1, ADR 0004). Nothing in `docs/safety/SRS.md`
depends on this topic.

## Running it

```
source /opt/ros/jazzy/setup.bash
ros2 launch /home/user/amr-agent/sim/launch/cell_bringup.launch.py
```

Headless by default. Options: `gui:=true` (Gazebo GUI client),
`world:=<abs path>`. The cell needs only `/opt/ros/jazzy` — no additional
workspace.

Drive the cell from a second terminal:

```
# run the belt forward, then stop, then reverse
ros2 topic pub -1 /cell/conveyor/cmd_speed std_msgs/msg/Float64 "{data: 0.15}"
ros2 topic pub -1 /cell/conveyor/cmd_speed std_msgs/msg/Float64 "{data: 0.0}"
ros2 topic pub -1 /cell/conveyor/cmd_speed std_msgs/msg/Float64 "{data: -0.15}"

# watch the photo-eye (1.440 clear, 0.540 blocked)
ros2 topic echo /cell/product_sensor/scan --field ranges

# watch the belt encoder and the product
ros2 topic echo /cell/conveyor/joint_state
ros2 topic echo /cell/product_box/pose

# press and release panel contacts
ros2 topic pub -1 /cell/panel/start        std_msgs/msg/Bool "{data: true}"
ros2 topic pub -1 /cell/panel/stop         std_msgs/msg/Bool "{data: false}"
ros2 topic pub -1 /cell/panel/process_stop std_msgs/msg/Bool "{data: false}"

# press the reset (NO: true = held), then release it
ros2 topic pub -1 /cell/panel/reset        std_msgs/msg/Bool "{data: true}"
ros2 topic pub -1 /cell/panel/reset        std_msgs/msg/Bool "{data: false}"

# confirm a contact crossed the bridge into Gazebo
stdbuf -oL gz topic -e -t /cell/panel/start
```

At 0.15 m/s the product needs about 9 s of belt travel to reach the beam
and about 2 s to pass through it. Real time factor is ~1.0 headless.

## Expected evidence after bringup

- `gz model --list` shows exactly `Floor`, `Conveyor`, `ProductBox`,
  `ProductSensor`, `SensorReflector`, `OperatorPanel` — and no vehicle.
- `ros2 topic list` shows the eight `/cell/*` topics plus `/clock`.
- `/cell/product_sensor/scan` reads 1.440 m clear and 0.540 m blocked.
- Commanding 0.15 m/s moves both `beltPos` and the product box; the box
  keeps a constant offset from the belt, so it is carried, not slipping.
- Publishing `true` then `false` on `/cell/panel/reset` is visible on the
  gz side and changes **nothing** in the cell: belt position, belt velocity
  and the beam range are the same before, during and after the press,
  whether the belt is idle or running.
- The launch log has zero error and zero warning lines.

The dated capture of exactly these checks from this container is in
`worlds/CELL_EVIDENCE.md`. The reset contact was added after that capture
and is evidenced separately, from WSL, in its Appendix A.

## Design notes

- **Why a prismatic belt rather than a velocity-controlled box.** Setting
  the product's velocity directly would make the "conveyor" a fiction that
  only works when a product happens to exist. A driven belt with the
  product carried by friction fails the way the real thing fails — the
  belt can run with nothing on it, and a product can be placed anywhere on
  it — which is what makes the PLC handshake worth testing. The cost is a
  finite ±2.50 m travel, which is a mechanical stop, not a control limit.
- **Why 2 ms physics steps.** Friction transport is contact-driven and
  jitters at coarse steps. The cell is small enough that 500 Hz still runs
  at real time headless, which keeps M3's latency measurements honest.
- **Why a lidar for a photo-eye.** A contact sensor would need the product
  to touch the sensor, which a real non-contact photo-eye does not. A
  one-sample `gpu_lidar` across the belt to a reflector reproduces the
  real device's geometry, including the fact that the switching distance
  is a commissioning parameter rather than a property of the sensor.
- **Why the panel has no physics.** A modelled pushbutton would need a
  simulated finger. The contacts are ROS signals so a human, a test script
  or the m3-04 bridge drives them exactly as it will drive real wired
  contacts.
- **What is deliberately absent.** No sequencing, no interlock, no timer,
  no latch, no debounce, no threshold, no start/stop/reset behaviour. The
  belt turns whenever a velocity is commanded, including while the
  process-stop contact reads pressed, and pressing the reset does nothing
  observable in the cell because there is no latch here for it to clear.
  That is not an oversight: making the cell refuse
  a command would put process logic in the simulation layer, and the whole
  point of M3 is that the logic lives in the TIA Portal program
  (invariants 5, 6 and 9).

---

# Forklift commissioning arena (M4)

`worlds/forklift_arena.sdf` + `launch/forklift_bringup.launch.py` are the M4
gate work under ADR 0008: the same PLC-owned loop as M3, now with a
**teleoperated forklift** as the plant instead of a conveyor. An operator drives
it from the commissioning HMI and every command passes
**HMI → PLC standard program → bridge → simulation**, with every state report
returning the same way.

The M3 cell is **not** embedded here and this arena is not embedded in it.
Neither world file includes the other; the coupled cell-plus-vehicle scenario is
roadmap M6 work (the coupled AT-07 case, ADR 0010). The vehicle itself lives in
`agv/forklift/model.sdf` — `sim/` owns worlds, `agv/` owns the vehicle — and the
bringup spawns it in.

**Nothing here is a safety device.** The obstacle props are process furniture.
The forklift's obstacle stop, fork-height speed cap and fork soft travel limits
are standard-program **process interlocks** implementing no function of
`docs/safety/SRS.md` and carrying no SIL or PL claim (ADR 0008 D3). The
protective stop, the e-stop chain and safe torque off are onboard and hardwired
and appear in no world file, no launch file and no scenario step.

## What is in the arena

```
            +y            north wall, inner face y = +7.90
    .........+.................................................
    .        |  [PalletZone 2.4 x 2.0 marking]                .
    .        |   [Pallet + LoadBox] at (-7.50, +4.50)         .
    .        |            [CrateNorth] (-4.50, +4.20)         .
    . . . . .+. . . . . . . . . . . . . . . . . . . . . . . .  aisle edge y = +2.00
    .        |                                                .
    .        |  [spawn (-6.00, 0)] >>>      [AisleCrate]      .
 ===+========+=============== drive aisle, centreline y = 0 =======> +x
    .        |                       straddling it at x = 2.00 .
    . . . . .+. . . . . . . . . . . . . . . . . . . . . . . .  aisle edge y = -2.00
    .        |     [PillarSouth] (-2.00, -3.20)               .
    .........+.................................................
      west wall                                    east wall x = +11.90
      x = -11.90
```

A 24.0 × 16.0 m hall, origin at its centre, with 0.60 m perimeter walls so the
vehicle's scanner terminates on them instead of running out to its range
maximum. Box and cylinder primitives only, one directional light, no mesh and no
texture: rendering on the target machine is llvmpipe software rasterisation, and
adding any of those changes the figures in `worlds/FORKLIFT_ARENA_EVIDENCE.md`.

**`AisleCrate` is the stop-zone prop**, and its placement is arithmetic rather
than taste. It stands *on* the aisle centreline with its front face square to
the aisle at `x = 1.55`, so a vehicle driving straight up the aisle meets it head
on and the scenario repeats without steering. The stop zone is the ±30° sector
of a scanner whose process stop distance is 1.20 m, so a prop more than
`1.20 × sin 30° = 0.60` m off the driving line can never be inside both the
sector and the distance at once. The world file's header carries the full
derivation.

**What the scanner sees** is decided by height: the scanner sweeps one
horizontal plane at `z = 0.25` in the vehicle frame, so the walls, `AisleCrate`,
`PillarSouth`, `CrateNorth` and `LoadBox` return, while the floor markings and
the `Pallet` deck (topping out at 0.16 m) do not. A pallet the scanner cannot
see while the load on it can is the real geometry of a low pallet under a
truck-mounted scanner.

**An empty forward sector reads clear at `range_max`, since `74c7d5f`.** The
scanner's `range_max` is 8.0 m and the hall is 24 m long, so a vehicle in the
middle of the aisle with nothing ahead of it has no in-range return in the
sector, and the vehicle layer reports that as `in_stop_zone = false`,
`min_distance = 8.0` — the scan's own `range_max`, not a sentinel. The
fail-safe (`in_stop_zone = true`, `min_distance = 0.0`) remains for a scan that
is missing, stale (over 0.50 s old) or structurally unusable, or a sector with
no sample in either valid class — never for an open horizon. Before `74c7d5f`
the evaluator read an open horizon as no-data, and the obstacle scenario
worked around it by keeping `AisleCrate` inside the scanner's range; that
workaround is retired, and `sim/scenarios/forklift_commissioning.md` §6
records it as a build difference rather than a live constraint.

## Running it

The arena needs `gz-sim-sensors-system` with a render engine, because the
vehicle's scanner is a `gpu_lidar`; this world loads it and gz's stock
`empty.sdf` does not. Isolate **both** transports — `ROS_DOMAIN_ID` does not
isolate Gazebo, `GZ_PARTITION` does:

```
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=myrun ROS_DOMAIN_ID=42

ros2 launch sim/launch/forklift_bringup.launch.py
```

Headless by default. Options: `gui:=true`, `world:=`, `model:=`, `name:=`,
`x:= y:= z:= yaw:=` (spawn pose, default `-6.00, 0.00, 0.05` facing `+x`, in the
open west half of the drive aisle with the whole aisle and the crate ahead).

The launch starts the gz server, spawns `agv/forklift/model.sdf` once, and runs
one `ros_gz_bridge` carrying `/clock`, the three raw joint commands
(ROS → gz) and the three feedback topics (gz → ROS). It deliberately does
**not** start the two vehicle nodes, which `agv/forklift/launch/vehicle.launch.py`
owns; run them against this world directly, which is what the commissioning
procedure does:

```
python3 agv/forklift/scripts/forklift_io.py    --config agv/forklift/config.yaml
python3 agv/forklift/scripts/obstacle_zone.py  --config agv/forklift/config.yaml
```

It also starts no PLC, no bridge process and no HMI. Those are `plc/`,
`bridge/` and `hmi/` processes; this launch only puts the plant on the wire.

**Signalling `ros2 launch` does not bring its group down.** Measured repeatedly:
the launch process exits and `gz sim` and `parameter_bridge` keep running. Check
with `pgrep -af` and finish each survivor by exact pid.

The dated capture of the arena — thirteen models, seven bridged topics with
their measured rates, the wiring direction of each, and a scripted traction pulse
read back on the bridged odometry — is in `worlds/FORKLIFT_ARENA_EVIDENCE.md`.

## The commissioning scenarios

`scenarios/forklift_commissioning.md` is the M4 gate procedure: the five roadmap
criteria as an owner-runnable sequence, each with its exact process start order
and isolation values, its operator steps at the HMI, the node, topic and
watch-table row that prove it, and the artifact to capture. It mirrors the six
test procedures of `plc/forklift/SPEC.md` §11, which owns them; it restates none
of them as an alternative and redefines no gate criterion.

Two helpers support it:

```
# hold a control set at the HMI - the only way to HOLD the momentary reset
python3 sim/scenarios/forklift_stimulus.py hold --teleop --traction 0.6 --reset --seconds 20

# move the aisle crate, and put it back
python3 sim/scenarios/forklift_stimulus.py obstacle --to-x 8.0
python3 sim/scenarios/forklift_stimulus.py obstacle --home

# one line per change, out of the HMI's own /state endpoint
python3 sim/scenarios/forklift_stimulus.py watch --seconds 60
```

```
# the rehearsal harness: all five scenarios against the PLC logic double
python3 sim/scenarios/run_forklift_rehearsal.py --scenario all
```

**No `--once` publish appears anywhere in either script.** A single publish exits
on the first matching subscriber and races every other one. Every stimulus is a
repeated publish at a stated rate, an HTTP post to the HMI's own endpoint, or a
gz service call that returns a reply.

`forklift_stimulus.py plant` is the exception that proves the rule: it drives the
vehicle's raw command topics directly, which **bypasses the PLC entirely** and is
therefore never gate evidence. It exists to show the machine alive before a
refusal is blamed on the program, and it must not run during a recorded scenario.

**The gate closes on the owner's PLCSIM Advanced run and its recording.** The
rehearsal recorded in `forklift_commissioning.md` ran against
`plc/forklift/double/`, a stand-in on loopback port 4850. It establishes that the
procedure is executable and that every observable it names is reachable; it
establishes nothing about the TIA Portal build.
