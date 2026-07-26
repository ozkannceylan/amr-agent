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
  worlds/warehouse.sdf              M3 warehouse world (walls, racks, DoorGap,
                                    ConveyorStation, ChargerStation)
  worlds/BRINGUP_EVIDENCE.md        dated verification record of the headless run
  launch/warehouse_bringup.launch.py  one-command headless bringup
  setup/install.sh                  idempotent environment setup (run as root)
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
