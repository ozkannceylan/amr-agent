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
  `EVIDENCE_SENSOR_COVERAGE.md`. **Their safe channel is not here at
  all** — it is not a topic on either transport, and the section below
  says where it does live.
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
| `scripts/obstacle_zone.py` | Forward stop-zone evaluator over the front safety scanner's **non-safe measurement channel**. |
| `scripts/sensor_tf.py` | Publishes `/tf_static` for the three sensor frames, reading every number out of `model.sdf`. |
| `scripts/sensor_coverage.py` | Reads `model.sdf` and measures what the three scanners can see. No simulator, no dependency. |
| `scripts/check_sensor_frames.py` | Checks that `model.sdf`, `config.yaml`, this README and `/tf_static` agree. Static by default, `--live` against a running graph. |
| `scripts/obstacle_matrix.py` | Drives `obstacle_zone.py` through its contracted cases, including the ones a rendered scanner cannot produce. |
| `launch/vehicle.launch.py` | Server, spawn, bridge, sensor TF and both nodes, headless by default. |
| `EVIDENCE_MODEL.md` | The dated headless run that verified the model and the two nodes. |
| `EVIDENCE_SENSOR_COVERAGE.md` | The computed coverage of the three scanners, with every residual sector named. §13 is the one measured section: the rear scanner's self-return band, from a live headless run. |
| `EVIDENCE_SENSOR_TF.md` | The dated runs behind the sensor frames and the measurement-channel consumer. |

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
| `/forklift/gz/safety_scanner_front/measurement` | `gz.msgs.LaserScan` | out of the model | front safety scanner, **non-safe measurement channel**: 275 ranges over 275°, 10 Hz, 0.10–5.50 m, plane z = 0.15 m, frame `safety_scanner_front_link`. Bridged into ROS |
| `/forklift/gz/safety_scanner_rear/measurement` | `gz.msgs.LaserScan` | out of the model | rear safety scanner, **non-safe measurement channel**: same, frame `safety_scanner_rear_link`. **Not bridged into ROS** — no process consumer exists for it |

### Two channels per safety scanner, and only one of them is a topic

The device class modelled — a 275° safety laser scanner of the
microScan3 class (ADR 0011, fact F8) — emits **two outputs from one
device**:

| Channel | What it is | Where it lives here | Who may consume it |
|---|---|---|---|
| **safe channel** | the OSSD pair, or safe bits over PROFIsafe: the protective-field verdict | **nowhere in this directory.** Derived by field evaluation (m5-12) and delivered to the F-program through the PLCSIM Advanced API, ADR 0011 decision 2 — this project's analogue of the copper an OSSD pair runs on | the F-program, and nothing else |
| **measurement channel** | the raw distance profile the datasheet provides for HMI, diagnostics and process use, **while stating it must not be used for safety-related tasks** | the `gpu_lidar` scan, on the gz and ROS topics named `.../measurement` above | process functions. Today: `obstacle_zone.py` |

**The measurement channel is non-safe and must never implement a safety
function.** Nothing computed from it is a protective stop, a safe speed,
an enable or a reset, whatever the device it came from is called.

The naming rule, so a later reader cannot confuse the two: **every
channel a subscriber can reach is a measurement channel, and says
`measurement` in its name. The safe channel has no topic, on either
transport, ever.** `scripts/check_sensor_frames.py` section 4 checks
both halves of that sentence rather than leaving it as a promise.

**Why a process function reading a safety device is not a layer
violation.** The process function consumes the device's *process* output;
the safety function consumes the device's *safe* output. They are two
outputs of one device and they travel two paths that never meet. What
ADR 0011 forbids is a safety scanner feeding a **navigation** consumer —
SLAM, AMCL, a costmap — and that prohibition is unchanged: **the
navigation lidar is the only SLAM input**, on `/forklift/scan`, and no
scanner channel reaches a costmap.

### The three scanners, and which one feeds what

| Sensor | Link and `frame_id` | Pose in `base_link` (x, y, z, yaw) | Aperture, blind sector | Consumer |
|---|---|---|---|---|
| `nav_lidar` | `nav_lidar_link` | 0.550, −0.400, 1.800, 0° | 360° | `/forklift/scan`: **SLAM, AMCL and the Nav2 costmaps, and nothing else feeds them** |
| `safety_scanner_front` | `safety_scanner_front_link` | 0.700, 0.450, 0.150, +45° | 275°, blind 182.5–267.5° | measurement channel → `obstacle_zone` (process). Safe channel → the F-program, off-network |
| `safety_scanner_rear` | `safety_scanner_rear_link` | −0.700, −0.450, 0.150, −135° | 275°, blind 2.5–87.5° | measurement channel → nobody yet, so it is not bridged. Safe channel → the F-program, off-network |

The pose column is **parsed**, not decorative: `check_sensor_frames.py`
section 2 reads these three rows out of this file and compares them to
`model.sdf` sample by sample, so a hand edit that disagrees with the model
fails a check instead of ageing quietly.

Coverage is **measured**, not asserted: `EVIDENCE_SENSOR_COVERAGE.md` computes
it from this model's own geometry and names every residual sector with its
cause and its mitigation. The headline coverage figures are computed and were
not observed in a running simulation: the two safety scanners together cover
360.0° of the bearings around the vehicle at 3.0 m radius and beyond; 355.0° at
2.0 m, the missing 5.0° being the carriage shadow at 169.4–174.4°; 100% of the
vehicle outline offset by 0.50 m; 4.95 m of all-round reach against the
sensors' own 5.50 m range. A pallet in the load direction costs 39.9°. The
navigation lidar's mast shadow is 29.0°, 2.50 m wide at 5 m. **No sector is
claimed to be covered by construction** — read section 11 of the evidence
before designing anything on top of these sensors.

One figure there **is** measured, in §13, and it is a property of one device
rather than of the pair: **the rear scanner spends 21.8% of its rays on the
vehicle's own mast rails and fork carriage**, at bearings 93.5–152.7° and
0.090–0.780 m, rising to 29.8% and 1.022 m while the tines cross the scan
plane. It costs no coverage, no mount angle removes it, and it is residual
**R8**. A protective field drawn into that sector would be permanently
violated, which is a constraint on the field design and not a licence to
filter the samples.

**Why neither safety scanner feeds SLAM, and why that is a different
question from the one above.** The front scanner's measurement channel is
bridged, for a *process* consumer. It still feeds no navigation consumer,
and would not even if the architecture allowed it. Four reasons, recorded
once:

- **Height.** At 0.15 m they see a different world from the navigation
  lidar — pallet feet, tine tips, floor returns — and that is what a
  leg-detection plane is for, not what a map is built from.
- **Aperture.** A 275° scan from a vehicle corner gives a scan matcher a
  partial, asymmetric constraint set; two of them at opposite corners give it
  two disagreeing ones.
- **The load.** A pallet occludes 39.9° of that plane in the load direction,
  which is a measured fact about the field and a moving hole in a map.
- **Architecture, and this is the one that decides it.** ADR 0011 rules
  that a safety scanner does not feed a navigation consumer. That is the
  prohibition, and bridging a *process* channel for a *process* function
  does not touch it.

**Why the rear channel is not bridged.** Nothing consumes it. A
measurement channel goes onto the process network when something on that
network consumes it, and not before: an unconsumed channel is an
invitation to a drive-by subscriber, and the subscriber that must never
appear is a navigation one. When a consumer for it exists, its ROS name
is `/forklift/safety_scanner_rear/measurement`, by the same pattern as
the front one.

### ROS 2, after `launch/vehicle.launch.py`

| ROS topic | Type | Rate | Produced by | Meaning |
|---|---|---|---|---|
| `/forklift/cmd/traction_speed` | `std_msgs/Float64` | on demand | a consumer | ground speed request [m/s] |
| `/forklift/cmd/steer_angle` | `std_msgs/Float64` | on demand | a consumer | steer angle request [rad] |
| `/forklift/cmd/fork_speed` | `std_msgs/Float64` | on demand | a consumer | carriage rate request [m/s] |
| `/forklift/fork_height` | `std_msgs/Float64` | 10 Hz | `forklift_io` | carriage travel above fully lowered [m] |
| `/forklift/linear_speed` | `std_msgs/Float64` | 10 Hz | `forklift_io` | forward ground speed [m/s] |
| `/forklift/safety_scanner_front/measurement` | `sensor_msgs/LaserScan` | 10 Hz | bridge | **The front safety scanner's non-safe measurement channel**, renamed from `/forklift/gz/safety_scanner_front/measurement`: 275 samples over 275°, plane z = 0.15 m, range 0.10–5.50 m, frame `safety_scanner_front_link`. Read by `obstacle_zone`. **Not a safety signal**, whatever the device is called, and forbidden to SLAM, AMCL and every costmap. |
| `/forklift/obstacle/in_stop_zone` | `std_msgs/Bool` | 10 Hz | `obstacle_zone` | Something inside the forward stop zone, computed from the **front safety scanner's measurement channel** at z = 0.15 m — the low plane the M4 showcase demonstrated, not the 1.80 m navigation plane. **`TRUE` is the non-permissive state.** The ±30° sector is centred on the vehicle's driving direction, which is `obstacle.sector_centre_rad` = −45° in this sensor's own angle coordinate because the sensor is mounted on a corner at +45°. The evaluator sorts every sample in that sector into three classes: **clear** — `+inf`, or a finite range at or beyond `range_max`, which is the sensor reporting no echo inside its window and counts as a valid measurement at `range_max`; **distance** — a finite range inside `[range_min, range_max)`; **invalid** — `NaN`, `-inf`, or a range below `range_min`. `TRUE` when a distance is at or under 1.20 m, and `TRUE` as a fail-safe when there is no scan, when the newest one is older than 0.50 s, when the scan is structurally unusable, or when the sector holds no sample in **either** valid class. A dead or garbage sensor is all of those; an open horizon is none of them. |
| `/forklift/obstacle/min_distance` | `std_msgs/Float64` | 10 Hz | `obstacle_zone` | Nearest valid range in the sector [m]: the smallest **distance**-class sample; the scan's own `range_max` when the sector is entirely **clear** beyond range; and `0.0`, the `unknown_distance_m` sentinel from `config.yaml`, in every fail-safe case above. The clear value is the scan's number and not this node's, so it follows whatever scanner `model.sdf` declares — and the consumer's plausibility window must contain it. Since this node reads the front safety scanner, that value is now **5.50 m**, comfortably inside the `0.05 … 8.10` m window of `docs/interfaces/opcua-nodes.md` §10.5, so **no interface change is owed by this consumer**. The window still bounds the *navigation* lidar's 8.00 m range, which is a separate open item. |
| `/forklift/scan` | `sensor_msgs/LaserScan` | 10 Hz | bridge | **The navigation lidar**, renamed from `/forklift/gz/scan_nav`: 360 samples over 360°, plane z = 1.80 m, frame `nav_lidar_link`. **This is the vehicle's only SLAM, AMCL and costmap input**, and it is no longer read by `obstacle_zone`: it replaced a 181-sample 180° scanner at z = 0.25 m, so **the plane this topic reports moved up 1.55 m**, and in `sim/worlds/forklift_arena.sdf`, whose walls stop at 0.60 m and whose tallest crate stops at 1.00 m, it reports a clear horizon in front of an obstacle a process stop must see (`EVIDENCE_SENSOR_TF.md` §4 measures exactly that: 60 of 60 forward samples clear at 1.80 m with a crate 0.85 m ahead at 0.15 m). **Not gap-free.** The old scanner dropped the single sample at exactly ±45°, in the raw gz message rather than in the bridge, following vehicle orientation rather than a fixed index (m4f-03 evidence). **That was measured on the sensor this one replaced and has not been re-measured here**, so it is a warning and not a specification. The consumer rule is unchanged and stands on its own: do not assume every sample is finite, and do not read a non-finite one as a missing one — an `inf` is the sensor reporting **no echo inside its window**, which is a measurement of a clear path to `range_max`, not an absence of data. `obstacle_zone.py` classifies each sample on exactly that basis and never condemns a whole scan for containing one bad sample. |
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
in no joint state. Their transforms are published instead, as static TF.

### TF

`scripts/sensor_tf.py` publishes one latched `/tf_static` message
carrying three transforms:

| Parent | Child | Source of the numbers |
|---|---|---|
| `forklift/base_link` | `safety_scanner_front_link` | `model.sdf`, read at start-up |
| `forklift/base_link` | `safety_scanner_rear_link` | `model.sdf`, read at start-up |
| `forklift/base_link` | `nav_lidar_link` | `model.sdf`, read at start-up |

Three properties are worth knowing before changing any of it:

- **No number is typed anywhere but `model.sdf`.** The node parses the
  model at start-up, so moving a sensor moves its transform on the next
  run. `config.yaml`'s `frames:` block is a mirror for the Python side,
  the same status the `model:` block has, and `check_sensor_frames.py`
  diffs it against the model.
- **The child frame is the frame the scan itself names.** Each child is
  the sensor's `<gz_frame_id>`, which is what lands in
  `header.frame_id`, so a TF lookup for a scan's own frame resolves. The
  parent is `model.sdf`'s own `<robot_base_frame>`, so the sensor frames
  land on the tree the odometry already declares rather than beside it.
  The parent carries the model name and the children do not; that
  asymmetry is Gazebo's, and renaming either side to tidy it stops the
  lookups working.
- **The node refuses rather than guesses.** If a sensor link is not a
  fixed child of `base_link`, if `<gz_frame_id>` names a different link,
  if the `<sensor>` pose is not identity, or if `base_link` is displaced
  from the model origin, it names the failing check and exits non-zero
  instead of publishing a transform the model does not justify.

A URDF plus `robot_state_publisher` was the alternative and is the right
answer **later**: the day TF is needed for the *moving* joints — steer,
drive wheel, mast — a URDF earns its keep. Today it would be a second
geometric description of a vehicle that already has one, kept equal to
the first by hand. Three `static_transform_publisher` processes were the
other alternative and are worse in the same direction: the poses would
live in a launch file, in triplicate, with nothing checking them against
the model.

**Not published here:** `odom → base_link`. That is a localisation
transform and it belongs to the brief that brings up SLAM.

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
`gui`, `server` (set false to spawn into a server someone else started),
`nodes`, and `tf` (the sensor transforms, separate from `nodes` because
SLAM needs them when the two process nodes are off).

Checking the vehicle rather than trusting it. The first two need no
simulator and no ROS; the third needs a running graph, and the fourth
starts `obstacle_zone` itself:

```bash
/usr/bin/python3 agv/forklift/scripts/sensor_tf.py --print
/usr/bin/python3 agv/forklift/scripts/check_sensor_frames.py
/usr/bin/python3 agv/forklift/scripts/check_sensor_frames.py --live
ROS_DOMAIN_ID=79 /usr/bin/python3 agv/forklift/scripts/obstacle_matrix.py
```

In the session container `python3` is 3.11 and ROS is built against
3.12, so these are run as `/usr/bin/python3` or through `ros2 launch`
(`sim/setup/CONTAINER_TOOLCHAIN.md` §3.3).

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
