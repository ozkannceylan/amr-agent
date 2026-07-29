# agv/forklift

An in-house tricycle forklift: an SDF model, its named constants, and the
two vehicle-side ROS 2 nodes that turn it into something the rest of the
project can command in engineering units.

## This layer must not access

- **OPC UA, in any form.** No `asyncua`, no client, no server, no node id.
  The vehicle's only fleet-facing interface is VDA 5050 over the broker
  (invariants 3, 4, 11).
- **`bridge/` internals.** The Gazebo-to-PLC signal bridge is a separate
  layer with its own boundary. Nothing here imports from it, reads its
  config, or writes to its evidence paths (ADR 0005).
- **`fleet/`.** Order assignment, traffic and zone reservation belong to
  the fleet manager. This directory executes motion; it does not decide
  what motion is worth executing (invariants 5, 6).
- **`plc/`.** Interlocks, handshakes and fixed equipment are the PLC's.
  The vehicle never reads a PLC tag directly.
- **`hmi/`.** The commissioning HMI is an operator surface over the PLC.
  It is not upstream of the vehicle and nothing here calls into it.
- **Safety, from anywhere on the network.** Protective stop, e-stop and
  safe torque off are onboard and hardwired. No topic in the table below
  triggers or releases a safety function, and none may be presented as
  though it does (invariant 1). `obstacle/in_stop_zone` is a process
  comfort zone, nothing more.
- **Hard real-time control loops in Python.** The joint controllers close
  their loops inside the physics engine. The Python nodes here run on
  timers and a late one degrades smoothness, never integrity
  (invariant 9).

## What is here

| File | What it is |
|---|---|
| `model.sdf` | The vehicle. Geometry, joints, gz systems, scanner. A plain `<model>`, so any world can spawn it. |
| `config.yaml` | Every named constant the nodes use. No behavioural constant is written inline in a script. |
| `scripts/forklift_io.py` | Engineering units in, raw joint commands out; joint state and odometry in, two scalars out. |
| `scripts/obstacle_zone.py` | Forward stop-zone evaluator over the scanner. |
| `launch/vehicle.launch.py` | Server, spawn, bridge and both nodes, headless by default. |
| `EVIDENCE_MODEL.md` | The dated headless run that verified all of the above. |

There is deliberately **no world file here.** Worlds belong to `sim/`.
This directory owns a vehicle.

## The contract

Everything below is a name other layers may depend on. The gz topics are
stated explicitly in `model.sdf` rather than left to the model-scoped
defaults, precisely so they survive the model being spawned under another
name.

### gz transport, consumed and produced by the model

| gz topic | gz type | Direction | Meaning |
|---|---|---|---|
| `/forklift/gz/steer_cmd` | `gz.msgs.Double` | into the model | steer angle target [rad] |
| `/forklift/gz/traction_cmd` | `gz.msgs.Double` | into the model | drive wheel spin rate [rad/s] |
| `/forklift/gz/fork_cmd` | `gz.msgs.Double` | into the model | carriage travel target [m] |
| `/forklift/gz/joint_state` | `gz.msgs.Model` | out of the model | position and rate of the three driven joints |
| `/forklift/gz/odom` | `gz.msgs.Odometry` | out of the model | ground-truth pose and body twist |
| `/forklift/gz/scan` | `gz.msgs.LaserScan` | out of the model | 181 planar ranges, 180 deg forward |

### ROS 2, after `launch/vehicle.launch.py`

| ROS topic | Type | Rate | Produced by | Meaning |
|---|---|---|---|---|
| `/forklift/cmd/traction_speed` | `std_msgs/Float64` | on demand | a consumer | ground speed request [m/s] |
| `/forklift/cmd/steer_angle` | `std_msgs/Float64` | on demand | a consumer | steer angle request [rad] |
| `/forklift/cmd/fork_speed` | `std_msgs/Float64` | on demand | a consumer | carriage rate request [m/s] |
| `/forklift/fork_height` | `std_msgs/Float64` | 10 Hz | `forklift_io` | carriage travel above fully lowered [m] |
| `/forklift/linear_speed` | `std_msgs/Float64` | 10 Hz | `forklift_io` | forward ground speed [m/s] |
| `/forklift/obstacle/in_stop_zone` | `std_msgs/Bool` | 10 Hz | `obstacle_zone` | Something inside the forward stop zone. **`TRUE` is the non-permissive state.** The evaluator sorts every sample in the ±30° sector into three classes: **clear** — `+inf`, or a finite range at or beyond `range_max`, which is the sensor reporting no echo inside its window and counts as a valid measurement at `range_max`; **distance** — a finite range inside `[range_min, range_max)`; **invalid** — `NaN`, `-inf`, or a range below `range_min`. `TRUE` when a distance is at or under 1.20 m, and `TRUE` as a fail-safe when there is no scan, when the newest one is older than 0.50 s, when the scan is structurally unusable, or when the sector holds no sample in **either** valid class. A dead or garbage sensor is all of those; an open horizon is none of them. |
| `/forklift/obstacle/min_distance` | `std_msgs/Float64` | 10 Hz | `obstacle_zone` | Nearest valid range in the sector [m]: the smallest **distance**-class sample; the scan's own `range_max` when the sector is entirely **clear** beyond range; and `0.0`, the `unknown_distance_m` sentinel from `config.yaml`, in every fail-safe case above. The clear value is the scan's number and not this node's, so it follows whatever scanner `model.sdf` declares — and the consumer's plausibility window must contain it (`docs/interfaces/opcua-nodes.md` §10.5 gives `0.05 … 8.10` m against this scanner's `0.10 … 8.00` m). |
| `/forklift/scan` | `sensor_msgs/LaserScan` | 10 Hz | bridge | The scanner, renamed from the gz topic. **Not gap-free.** The gz `gpu_lidar` drops the single sample at exactly +-45 deg. It is the sensor and not the bridge: the `inf` is already in the raw gz message, it appears in the middle of an object returned continuously either side of it, it reproduces against a flat wall, and it follows the vehicle's orientation rather than sitting at a fixed index, so turning the vehicle recovers that ray and loses another (m4f-03 evidence). A consumer of this topic must therefore not assume every sample is finite — and must not read a non-finite one as a missing one: an `inf` here is the sensor reporting **no echo inside its window**, which is a measurement of a clear path to `range_max` and not an absence of data. `obstacle_zone.py` classifies each sample on exactly that basis and never condemns a whole scan for containing one bad sample. This particular `inf` is moot for it either way: `±45°` is outside the `±30°` sector it evaluates. |
| `/forklift/odom` | `nav_msgs/Odometry` | 20 Hz | bridge | odometry, renamed from the gz topic |
| `/forklift/joint_states` | `sensor_msgs/JointState` | physics rate | bridge | joint state, renamed from the gz topic |
| `/forklift/gz/*_cmd` | `std_msgs/Float64` | on change | `forklift_io` | the raw joint commands, same name both sides |

Commands keep their gz name across the bridge because they **are** the
model's raw inputs and the identity is worth seeing. Feedback is renamed,
because a consumer should not have to know it came from a simulator.

### Joint names, as they appear in `/forklift/joint_states`

| Joint | Type | Range | Driven by |
|---|---|---|---|
| `steer_joint` | revolute about z | -1.31 to 1.31 rad | `JointPositionController` |
| `drive_wheel_joint` | revolute about y | continuous | `JointController`, velocity |
| `mast_joint` | prismatic along z | 0 to 1.6 m | `JointPositionController` |
| `rear_wheel_left_joint`, `rear_wheel_right_joint` | revolute about y | continuous | nothing, passive |

### What a world has to provide

The scanner is a `gpu_lidar`. A world that spawns this model and expects
`/forklift/gz/scan` to carry anything **must** load the sensors system
with a render engine:

```xml
<plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
  <render_engine>ogre2</render_engine>
</plugin>
```

`sim/worlds/cell.sdf` does. gz's stock `empty.sdf`, which is this launch
file's default world, does **not**: the vehicle drives and lifts on it,
and the scan topic stays silent. `EVIDENCE_MODEL.md` quotes the minimal
world used for verification.

## Running it

Rendering on this machine is software rasterisation, so the server runs
headless and the scanner budget (181 samples, 10 Hz) is chosen against
that. Isolate both transports whenever another simulation may be running:
`ROS_DOMAIN_ID` does not isolate Gazebo, `GZ_PARTITION` does.

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=myrun ROS_DOMAIN_ID=61

ros2 launch agv/forklift/launch/vehicle.launch.py world:=/path/to/world.sdf
```

Useful arguments: `world`, `world_name`, `name`, `x`, `y`, `z`, `yaw`,
`gui`, `server` (set false to spawn into a server someone else started)
and `nodes`.

Driving it by hand, publishing at a rate rather than `--once`, because a
single message races any subscriber that has not finished matching:

```bash
ros2 topic pub -r 5 /forklift/cmd/traction_speed std_msgs/msg/Float64 '{data: 0.30}'
ros2 topic pub -r 5 /forklift/cmd/steer_angle    std_msgs/msg/Float64 '{data: 0.40}'
ros2 topic pub -r 5 /forklift/cmd/fork_speed     std_msgs/msg/Float64 '{data: 0.10}'
```

`fork_speed` is a **rate** request that is integrated into a position
target. Zero does not lower the forks; zero holds them, which is what a
lift control lever does.

## Two design points worth knowing before changing anything

**`model.sdf` owns the geometry; `config.yaml` mirrors the few numbers the
nodes need.** SDF cannot be read as YAML, so `wheel_radius_m`,
`steer_limit_rad` and the fork travel limits exist in both files. If they
ever disagree, `model.sdf` is right. `EVIDENCE_MODEL.md` records the check.

**Steer and traction are published on receipt; the fork target is
republished every cycle.** The safe value of a steer angle and a traction
speed is zero, so letting them lapse to zero on a restart is the correct
direction. The safe value of a fork height is *hold*, so a lift that
silently returned to the floor when a process restarted would be the
wrong one.
