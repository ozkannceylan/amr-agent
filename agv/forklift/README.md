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
  comfort zone, nothing more. The two sensors named `safety_scanner_*` in
  `model.sdf` name the **device class they model**, not a property of
  this layer: a rendered depth image has no integrity, no OSSD, no fault
  reaction and no diagnostic coverage. What they contribute is the
  geometry of a real installation, measured in
  `EVIDENCE_SENSOR_COVERAGE.md`.
- **Hard real-time control loops in Python.** The joint controllers close
  their loops inside the physics engine. The Python nodes here run on
  timers and a late one degrades smoothness, never integrity
  (invariant 9).

## What is here

| File | What it is |
|---|---|
| `model.sdf` | The vehicle. Geometry, joints, gz systems, three scanners. A plain `<model>`, so any world can spawn it. |
| `config.yaml` | Every named constant the nodes use. No behavioural constant is written inline in a script. |
| `scripts/forklift_io.py` | Engineering units in, raw joint commands out; joint state and odometry in, two scalars out. |
| `scripts/obstacle_zone.py` | Forward stop-zone evaluator over `/forklift/scan`, which is the navigation lidar. |
| `scripts/sensor_coverage.py` | Reads `model.sdf` and measures what the three scanners can see. No simulator, no dependency. |
| `launch/vehicle.launch.py` | Server, spawn, bridge and both nodes, headless by default. |
| `EVIDENCE_MODEL.md` | The dated headless run that verified the model and the two nodes. |
| `EVIDENCE_SENSOR_COVERAGE.md` | The computed coverage of the three scanners, with every residual sector named. |

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
| `/forklift/gz/scan_nav` | `gz.msgs.LaserScan` | out of the model | navigation lidar: 360 ranges over 360°, 10 Hz, 0.10–8.00 m, plane z = 1.80 m, frame `nav_lidar_link` |
| `/forklift/gz/scan_safety_front` | `gz.msgs.LaserScan` | out of the model | front safety scanner: 275 ranges over 275°, 10 Hz, 0.10–5.50 m, plane z = 0.15 m, frame `safety_scanner_front_link`. **Not bridged into ROS** |
| `/forklift/gz/scan_safety_rear` | `gz.msgs.LaserScan` | out of the model | rear safety scanner: same, frame `safety_scanner_rear_link`. **Not bridged into ROS** |

### The three scanners, and which one feeds what

| Sensor | Link and `frame_id` | Pose in `base_link` (x, y, z, yaw) | Aperture, blind sector | Consumer |
|---|---|---|---|---|
| `nav_lidar` | `nav_lidar_link` | 0.550, −0.400, 1.800, 0° | 360° | `/forklift/scan`: `obstacle_zone`, and SLAM when it exists |
| `safety_scanner_front` | `safety_scanner_front_link` | 0.700, 0.450, 0.150, +45° | 275°, blind 182.5–267.5° | the safety path only — see below |
| `safety_scanner_rear` | `safety_scanner_rear_link` | −0.700, −0.450, 0.150, −135° | 275°, blind 2.5–87.5° | the safety path only — see below |

Coverage is **measured**, not asserted: `EVIDENCE_SENSOR_COVERAGE.md` computes
it from this model's own geometry and names every residual sector with its
cause and its mitigation. The headline figures, all computed and none observed
in a running simulation: the two safety scanners together cover 360.0° of the
bearings around the vehicle at 3.0 m radius and beyond; 355.0° at 2.0 m, the
missing 5.0° being the carriage shadow at 169.4–174.4°; 100% of the vehicle
outline offset by 0.50 m; 4.95 m of all-round reach against the sensors' own
5.50 m range. A pallet in the load direction costs 39.9°. The navigation
lidar's mast shadow is 29.0°, 2.50 m wide at 5 m. **No sector is claimed to be
covered by construction** — read section 11 of the evidence before designing
anything on top of these sensors.

**Why the two safety scanners feed nothing here.** They are declared, they
publish on gz transport, and `vehicle.launch.py` deliberately does not bridge
them into the ROS graph. Four reasons, recorded once:

- **Height.** At 0.15 m they see a different world from the navigation
  lidar — pallet feet, tine tips, floor returns — and that is what a
  leg-detection plane is for, not what a map is built from.
- **Aperture.** A 275° scan from a vehicle corner gives a scan matcher a
  partial, asymmetric constraint set; two of them at opposite corners give it
  two disagreeing ones.
- **The load.** A pallet occludes 39.9° of that plane in the load direction,
  which is a measured fact about the field and a moving hole in a map.
- **Architecture, and this is the one that decides it.** Their measurement
  channel is a safety device's. The device they model emits an OSSD pair on
  copper; the simulation analogue of that path is the PLCSIM Advanced API into
  the F-program (ADR 0011 decision 2), not a topic. Bridging them would place a
  safety device's channel on the process network where any node could subscribe
  and quietly become a consumer of it.

### ROS 2, after `launch/vehicle.launch.py`

| ROS topic | Type | Rate | Produced by | Meaning |
|---|---|---|---|---|
| `/forklift/cmd/traction_speed` | `std_msgs/Float64` | on demand | a consumer | ground speed request [m/s] |
| `/forklift/cmd/steer_angle` | `std_msgs/Float64` | on demand | a consumer | steer angle request [rad] |
| `/forklift/cmd/fork_speed` | `std_msgs/Float64` | on demand | a consumer | carriage rate request [m/s] |
| `/forklift/fork_height` | `std_msgs/Float64` | 10 Hz | `forklift_io` | carriage travel above fully lowered [m] |
| `/forklift/linear_speed` | `std_msgs/Float64` | 10 Hz | `forklift_io` | forward ground speed [m/s] |
| `/forklift/obstacle/in_stop_zone` | `std_msgs/Bool` | 10 Hz | `obstacle_zone` | Something inside the forward stop zone. **`TRUE` is the non-permissive state.** The evaluator sorts every sample in the ±30° sector into three classes: **clear** — `+inf`, or a finite range at or beyond `range_max`, which is the sensor reporting no echo inside its window and counts as a valid measurement at `range_max`; **distance** — a finite range inside `[range_min, range_max)`; **invalid** — `NaN`, `-inf`, or a range below `range_min`. `TRUE` when a distance is at or under 1.20 m, and `TRUE` as a fail-safe when there is no scan, when the newest one is older than 0.50 s, when the scan is structurally unusable, or when the sector holds no sample in **either** valid class. A dead or garbage sensor is all of those; an open horizon is none of them. |
| `/forklift/obstacle/min_distance` | `std_msgs/Float64` | 10 Hz | `obstacle_zone` | Nearest valid range in the sector [m]: the smallest **distance**-class sample; the scan's own `range_max` when the sector is entirely **clear** beyond range; and `0.0`, the `unknown_distance_m` sentinel from `config.yaml`, in every fail-safe case above. The clear value is the scan's number and not this node's, so it follows whatever scanner `model.sdf` declares — and the consumer's plausibility window must contain it (`docs/interfaces/opcua-nodes.md` §10.5 gives `0.05 … 8.10` m against the navigation lidar's `0.10 … 8.00` m). That coupling is why the navigation lidar's range was left at 8.00 m even though the arena is 24 × 16 m: raising it past 8.10 m would make a clear horizon read at the PLC as a transducer fault. |
| `/forklift/scan` | `sensor_msgs/LaserScan` | 10 Hz | bridge | **The navigation lidar**, renamed from `/forklift/gz/scan_nav`: 360 samples over 360°, plane z = 1.80 m, frame `nav_lidar_link`. It replaced a 181-sample 180° scanner at z = 0.25 m, so **the plane this topic reports moved up 1.55 m** — a consumer that assumed shin height is now looking at chest height, and in `sim/worlds/forklift_arena.sdf`, whose walls stop at 0.60 m, it will mostly report a clear horizon (`EVIDENCE_SENSOR_COVERAGE.md` §10). **Not gap-free.** The old scanner dropped the single sample at exactly ±45°, in the raw gz message rather than in the bridge, following vehicle orientation rather than a fixed index (m4f-03 evidence). **That was measured on the sensor this one replaced and has not been re-measured here**, so it is a warning and not a specification. The consumer rule is unchanged and stands on its own: do not assume every sample is finite, and do not read a non-finite one as a missing one — an `inf` is the sensor reporting **no echo inside its window**, which is a measurement of a clear path to `range_max`, not an absence of data. `obstacle_zone.py` classifies each sample on exactly that basis and never condemns a whole scan for containing one bad sample. |
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

The three sensor mounts — `safety_scanner_front_mount`,
`safety_scanner_rear_mount`, `nav_lidar_mount` — are `fixed` joints and appear
in no joint state. **Nothing in this directory publishes a TF from
`forklift/base_link` to the three sensor frames yet.** SLAM and Nav2 will need
it; the offsets are constants and are in the sensor table above.

### What a world has to provide

All three scanners are `gpu_lidar` sensors, because gz sim has no CPU ray
sensor. A world that spawns this model and expects any of the three scan
topics to carry anything **must** load the sensors system with a render engine:

```xml
<plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
  <render_engine>ogre2</render_engine>
</plugin>
```

`sim/worlds/cell.sdf` does. gz's stock `empty.sdf`, which is this launch
file's default world, does **not**: the vehicle drives and lifts on it,
and all three scan topics stay silent. `EVIDENCE_MODEL.md` quotes the
minimal world used for verification.

A world also has to be **worth scanning at the plane each sensor is on**. The
navigation lidar's plane is z = 1.80 m; `sim/worlds/forklift_arena.sdf` has
perimeter walls 0.60 m tall and exactly one object that reaches 1.80 m, so as
it stands that world presents this sensor with almost nothing
(`EVIDENCE_SENSOR_COVERAGE.md` §10). `sim/worlds/warehouse.sdf`, racks 2.0 m
and walls 2.5 m, does.

## Running it

Rendering on this machine is software rasterisation, so the server runs
headless and the ray budget is chosen against that: 275 + 275 + 360 = 910 rays
per 100 ms across three sensors, where there used to be 181 on one. **The
real-time cost of that has not been measured**, and no sample count or update
rate in `model.sdf` goes up until someone measures what it buys and writes the
figure down. `<visualize>true</visualize>` is set on all three, which is
necessary but not sufficient to draw the rays: the world also needs a
`VisualizeLidar` GUI plugin, and that belongs to `sim/`. Isolate both
transports whenever another simulation may be running: `ROS_DOMAIN_ID` does not
isolate Gazebo, `GZ_PARTITION` does.

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

**Every scanner pose is derived from the geometry, and the derivation is
re-runnable.** `scripts/sensor_coverage.py` reads `model.sdf` itself, so moving
a sensor, resizing the chassis or changing the fork travel changes the coverage
figures on the next run rather than silently invalidating a document. Run it
before and after touching any pose, and read
`EVIDENCE_SENSOR_COVERAGE.md` §11 first: the residual sectors are the reason
the poses are what they are.

**Steer and traction are published on receipt; the fork target is
republished every cycle.** The safe value of a steer angle and a traction
speed is zero, so letting them lapse to zero on a restart is the correct
direction. The safe value of a fork height is *hold*, so a lift that
silently returned to the floor when a process restarted would be the
wrong one.
