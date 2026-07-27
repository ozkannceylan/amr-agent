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
  worlds/warehouse.sdf              warehouse world for the vehicle work, now M5
                                    (walls, racks, DoorGap, ConveyorStation,
                                    ChargerStation)
  worlds/BRINGUP_EVIDENCE.md        dated verification record of the headless run
  launch/warehouse_bringup.launch.py  one-command headless bringup
  setup/install.sh                  idempotent environment setup (run as root)
  scenarios/
    tools/make_map.py               deterministic map generator (world -> map)
    maps/map.yaml, map.pgm          occupancy grid of warehouse.sdf (generated)
    config/nav2_params.yaml         Nav2 parameters for the RB-KAIROS bringup
    nav_scenario.launch.py          Nav2 stack (map_server, AMCL, planner,
                                    DWB controller, behaviors, bt_navigator)
    run_scenario.py                 scripted NavigateToPose run + evidence
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
  ros-jazzy-ros2-control ros-jazzy-gz-ros2-control \
  ros-jazzy-controller-manager ros-jazzy-joint-state-broadcaster \
  ros-jazzy-joint-trajectory-controller \
  ros-jazzy-navigation2 ros-jazzy-nav2-bringup \
  python3-colcon-common-extensions python3-rosdep python3-vcstool git
```

`ros-jazzy-gz-sim-vendor` provides Gazebo Harmonic (gz sim 8), per ADR 0003.

### 4. Robotnik vendor workspace (ADR 0002)

Cloned unmodified at the `jazzy-devel` branch into
`/opt/m3-feasibility/ws/src` and built with colcon:

```
mkdir -p /opt/m3-feasibility/ws/src && cd /opt/m3-feasibility/ws/src
git clone -b jazzy-devel https://github.com/RobotnikAutomation/robotnik_description.git
git clone -b jazzy-devel https://github.com/RobotnikAutomation/robotnik_simulation.git
git clone -b jazzy-devel https://github.com/RobotnikAutomation/robotnik_sensors.git
git clone -b jazzy-devel https://github.com/RobotnikAutomation/robotnik_common.git
git clone -b jazzy-devel https://github.com/RobotnikAutomation/teleop_panel.git
cd /opt/m3-feasibility/ws
source /opt/ros/jazzy/setup.bash && colcon build --symlink-install
```

### 5. Robotnik controller debs (required, easy to miss)

The rbkairos ros2_control profile declares
`robotnik_base_control: robotnik_controllers/RBKairosController`. That
mecanum controller is **not** in the cloned sources; Robotnik ships it as
prebuilt debs inside `robotnik_simulation/debs/`. Without them the
controller spawner fails and the base never accepts velocity commands:

```
apt-get install -y \
  /opt/m3-feasibility/ws/src/robotnik_simulation/debs/ros-jazzy-robotnik-common-msgs_*.deb \
  /opt/m3-feasibility/ws/src/robotnik_simulation/debs/ros-jazzy-robotnik-controllers-msgs_*.deb \
  /opt/m3-feasibility/ws/src/robotnik_simulation/debs/ros-jazzy-robotnik-controllers_*.deb
```

## Running the bringup

```
source /opt/ros/jazzy/setup.bash
source /opt/m3-feasibility/ws/install/setup.bash
ros2 launch /home/user/amr-agent/sim/launch/warehouse_bringup.launch.py
```

Headless by default. Options: `gui:=true` (Gazebo GUI client),
`robot_id:=<name>`, `x:= y:= z:=` (spawn pose, default -10, -6, 0.15 in
the open area south of the racks), `world:=<abs path>`.

### Design choice: vendor spawn path with ros2_control

The launch file starts the gz server with `sim/worlds/warehouse.sdf`,
bridges `/clock`, and then includes the **unmodified** vendor launch
`robotnik_gazebo_ignition/spawn_robot.launch.py` with `robot:=rbkairos`
and `run_rviz:=False`. The vendor launch provides robot_state_publisher,
the entity spawner, the sensor ros_gz_bridge and the ros2_control spawners
(gz_ros2_control + `robotnik_controllers/RBKairosController`). This was
chosen over any hand-rolled drive plugin because it keeps vendor files
untouched, exercises the same controller stack a real RB-KAIROS uses, and
was verified working headless in this container (see
`worlds/BRINGUP_EVIDENCE.md`). The controller spawners' 60 s timeouts
absorb the slow headless startup.

### Expected evidence after bringup

- `gz model --list` shows the world models (WallNorth..., RackA1...,
  DoorGap, ConveyorStation, ChargerStation) plus `robot`.
- `ros2 topic echo /clock --once` returns advancing sim time.
- `ros2 topic echo /robot/front_laser/scan --once` returns a 270-sample
  scan with finite ranges (walls/racks visible); `/robot/rear_laser/scan`
  likewise.
- `/robot/robotnik_base_control/odom` publishes; publishing
  `geometry_msgs/Twist` on `/robot/robotnik_base_control/cmd_vel_unstamped`
  moves the base and odometry integrates.
- `ros2 control list_controllers -c /robot/controller_manager` lists
  `joint_state_broadcaster` and `robotnik_base_control` as `active`.

The dated capture of exactly these checks from this container is in
`worlds/BRINGUP_EVIDENCE.md`.

## Navigation scenario (M5, deferred)

This is not current work. Under ADR 0004 the vehicle and navigation gates
move behind the fixed-equipment loop; this scenario is parked unverified
and its status is recorded in `sim/scenarios/DEFERRED.md`.

Localization + Nav2 goal navigation on top of the bringup above. Three
steps, three terminals, all with both setups sourced
(`/opt/ros/jazzy/setup.bash` then `/opt/m3-feasibility/ws/install/setup.bash`):

```
# 1. world + robot (as above)
ros2 launch /home/user/amr-agent/sim/launch/warehouse_bringup.launch.py

# 2. Nav2 stack against the running bringup
ros2 launch /home/user/amr-agent/sim/scenarios/nav_scenario.launch.py

# 3. scripted run: initial pose -> AMCL localized -> NavigateToPose goal
python3 /home/user/amr-agent/sim/scenarios/run_scenario.py
```

Step 3 exits 0 only if the action result is STATUS_SUCCEEDED, and rewrites
`scenarios/EVIDENCE_NAV.md` with the captured initial `/amcl_pose`, pose
samples, result status, distance and durations. The committed file is the
record of the verified run in this container.

### Map: generated, not SLAM-mapped

`scenarios/maps/` is produced by `scenarios/tools/make_map.py`, which
rasterizes the known static geometry of `worlds/warehouse.sdf` (every
rectangle in the script is copied from the SDF model poses). This was
chosen over slam_toolbox mapping because it is deterministic, reproducible
in seconds, and diffable against the world file; at the container's ~0.1
real-time factor a SLAM mapping drive would take an hour and produce a
slightly different map every time. The overhead DoorGap lintel is
deliberately excluded (the lidar never sees it; the vehicle drives under
it). If the world changes, re-run the script.

### Nav2 configuration notes

- All nodes run on sim time; tolerances in `config/nav2_params.yaml` are
  sim seconds.
- Frames come from the vendor stack: `map -> robot_odom ->
  robot_base_footprint`. AMCL consumes `/robot/front_laser/scan` (omni
  motion model, since the base is mecanum).
- The controller is DWB in a diff-drive-style configuration (vy locked to
  0) even though the base is holonomic: it is the configuration verified
  to reach goals here. Nav2's `cmd_vel` (Twist, `enable_stamped_cmd_vel:
  false`) is remapped to the vendor controller's
  `/robot/robotnik_base_control/cmd_vel_unstamped`.
- `lifecycle_manager` runs with `bond_timeout: 0.0`; bond heartbeats
  starve at RTF ~0.1 and would otherwise take the servers down.
- Speeds are capped at 0.45 m/s so the slow headless sim tracks commands.

### Expected output

Nav2 activation takes a few minutes wall-clock. `run_scenario.py` then
logs `AMCL localized`, `goal accepted`, periodic pose samples, and finally
`result: status 4 (SUCCEEDED)`. The default goal (-6.0, 1.5) is in Aisle A;
from the spawn at (-10, -6) the planned path runs north past the west end
of rack row B and turns east between the rack rows (~11 m). Expect roughly
10x the sim duration in wall-clock time.

### Known behavior

- Headless real-time factor is ~0.1 on this CPU-only container because the
  lidars and the RGBD camera render through ogre2 on llvmpipe. Functional
  for bringup and CI-style checks; wall-clock patience required.
- Gazebo prints SDF warnings (`gz_frame_id ... not defined in SDF`) while
  converting the vendor URDF; they are cosmetic and come from vendor
  sensor definitions, not from this world.
- The world's south wall has a free 4 m opening marked by the `DoorGap`
  posts/lintel; the PLC-controlled door and the conveyor/charger handshakes
  act there in later gates (M6/M7). The blocks are geometry only — no
  fleet, PLC or safety behavior is simulated here (see the first section).

---

# Demonstration cell (M3)

`worlds/cell.sdf` + `launch/cell_bringup.launch.py` are the M3 gate work
under ADR 0004: prove the Gazebo-to-PLC signal loop with **fixed equipment
only**, before any mobile robot. There is no vehicle in this world and
none belongs in it. The warehouse world and its navigation scenario above
are the deferred M5 vehicle work and are untouched by this.

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
`world:=<abs path>`. The Robotnik vendor workspace is **not** needed for
this cell — only `/opt/ros/jazzy`.

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
