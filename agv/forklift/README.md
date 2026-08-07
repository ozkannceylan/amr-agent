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
  says where it is intended to live and what about that path is still
  unproven.
- **Hard real-time control loops in Python.** The joint controllers close
  their loops inside the physics engine. The Python nodes here run on
  timers and a late one degrades smoothness, never integrity
  (invariant 9).

## What is here

| File | What it is |
|---|---|
| `model.sdf` | The vehicle. Geometry, joints, gz systems, three scanners and an IMU. A plain `<model>`, so any world can spawn it. |
| `config.yaml` | Every named constant the nodes use. No behavioural constant is written inline in a script. |
| `scripts/forklift_io.py` | Engineering units in, raw joint commands out; joint state and odometry in, two scalars out. |
| `scripts/obstacle_zone.py` | Forward stop-zone evaluator over the front safety scanner's **non-safe measurement channel**. |
| `scripts/field_evaluation.py` | The protective- **and warning**-field evaluation, phases 1 and 2 of `FIELD-EVALUATION.md`. A **model of what a safety-rated scanner does inside its own housing** — two contours, per-device verdicts, OSSD-equivalent pair, union aggregation — feeding a **stand-in for wiring** over one dedicated TCP link. **Not a safety function; no Category, no PL, no SIL, no PFH** (ADR 0011 D5); SF-04, the warning function, carries no claim at all. The **protective** verdict publishes **no topic**; the **warning** verdict is process data and publishes one, `/forklift/warning_field/occupied`, at the evaluation tick so that its absence is visible. It latches nothing and enforces no speed. Evidence: `EVIDENCE_FIELD_EVALUATION.md`. |
| `scripts/safe_speed_channels.py` | **The drive shaft, read twice, plus the corroboration a claimed zero speed is checked against.** Puts a reading head on each of `model.sdf`'s two reads of `drive_wheel_joint` — its own mounting phase on the count grid, its own read jitter — and publishes two signed tread speeds for the F-program to cross-compare. **A SINGLE-CHANNEL TESTED SYSTEM: one shaft, two readings of it, never a two-channel one.** Beside them it publishes a **motion-present STAND-IN** for the mechanical fault exclusion a real system argues on the shaft coupling, taken from the navigation lidar. **Not a safety function; no Category, no PL, no SIL, no PFH** (ADR 0011 D5) — the readings reach the F-program as **standard data**. It limits nothing and latches nothing. `--selftest` exercises the head model and the observation with no ROS. Evidence: `EVIDENCE_ODOMETRY.md` §15. |
| `scripts/safe_speed_bench.py` | The instrument behind that section: `--drive` runs the speed profile and prints a per-segment table with an **achieved** column, so a held or blocked segment is visibly held; `--analyse` reads the recorded CSV with no ROS and prints the channel noise, the run-length of noise excursions at several thresholds, and the **derivation** of the discrepancy threshold and discrepancy time from them. |
| `scripts/safe_speed_link.py` | **The carrier that puts those readings on the wire to the stand-in writer** (`plc/forklift-safety/SPEC.md` §11.2): one TCP connection, WSL client → Windows listener on port 45016, `SPD A/B <int mm/s>`, `MOT <p> <v>`, `PING`. It decides nothing, forms no verdict and holds no reading — **a channel goes silent rather than repeat**, so a reading that stops arriving stops being sent and the writer's frozen freshness sequence is what the F-program reads as a missing channel. Never scales and never sends a non-finite or out-of-Int-range value. Not an OPC UA client. **Not a safety function; no Category, no PL, no SIL, no PFH** (ADR 0011 D5). `--selftest` runs with no ROS and no network. Evidence: `EVIDENCE_SPEED_LINK.md`. |
| `scripts/speed_link_rig.py` | The local proving rig behind that evidence, and **not the stand-in writer**: `sink` models the writer half of §11.2 (45016 listener, one client, 50 ms cycle, sequences that advance only on a fresh line, the 250 ms motion-silence rule) and **writes to no PLC**; `plant` stimulates the producer's two gz reads and a scan so the chain runs with no Gazebo, and can go **silent** the way a dead source does; `inject` publishes values the producer cannot emit, each with a positive control. |
| `scripts/sensor_tf.py` | Publishes `/tf_static` for the four sensor frames, reading every number out of `model.sdf`. |
| `scripts/scan_viz_repeater.cc` + `.sh` | **GUI anchor repair, visualization only** (m5-73): republishes each gz scan on `/forklift/gz/viz/*` with `world_pose` replaced by the sensor's **live** world pose and nothing else changed, because on this Gazebo build that field is the sensor's static SDF pose and the `VisualizeLidar` plugin anchors every fan to it — at the world origin, for this model. C++ because gz-transport has no Python bindings on this stack; the `.sh` wrapper builds the single source on first use into an uncommitted `build/`. Started by `vehicle.launch.py lidar_viz:=`, default = `gui`. No vehicle node reads the viz topics and the measurement channels are untouched (`EVIDENCE_SENSOR_COVERAGE.md` §16). Not a safety function: no Category, no PL, no SIL, no PFH. |
| `scripts/wheel_odometry.py` | Tricycle dead reckoning from the vehicle's own joint states, through two modelled encoders. Publishes an estimate and **no transform**, plus the encoder-derived standstill verdict. |
| `scripts/imu_gate.py` | Stops offering the gyro's yaw rate to the EKF while the encoders report the wheels standing still — the interval in which that reading is bias and not rotation. Suppresses; never rewrites a sample; **estimates no bias**; fails open. |
| `ekf.yaml` | `robot_localization` parameters. The EKF is the **sole** publisher of `forklift/odom → forklift/base_link`. Its `imu0` is the **gated** IMU topic. |
| `scripts/sensor_coverage.py` | Reads `model.sdf` and measures what the three scanners can see. No simulator, no dependency. |
| `scripts/check_sensor_frames.py` | Checks that `model.sdf`, `config.yaml`, this README and `/tf_static` agree. Static by default, `--live` against a running graph. |
| `scripts/obstacle_matrix.py` | Drives `obstacle_zone.py` through its contracted cases, including the ones a rendered scanner cannot produce. |
| `scripts/check_odometry.py` | The instrument behind `EVIDENCE_ODOMETRY.md`: geometry and noise-model checks with no ROS, then the IMU alone, the wheel odometry alone against a known motion, the fusion, and the fused heading over an idle. The **only** thing here allowed to read ground truth, and only as a reference — and `--phase idle` reads none at all. |
| `scripts/check_odom_tf.py` | Checks that `odom → base_link` is published by the model, bridged onto `/tf`, resolvable and tracking. Static by default; `--live [--drive]` measures rate, chain and residual on a running graph. |
| `launch/vehicle.launch.py` | Server, spawn, bridge, sensor TF, the wheel odometry, the gyro gate, the EKF and both process nodes, headless by default. Refuses to start two publishers of one transform, or a gate with nothing to gate on. Carries an optional `seed` for reproducible sensor-noise draws. |
| `EVIDENCE_MODEL.md` | The dated headless run that verified the model and the two nodes. |
| `EVIDENCE_SENSOR_COVERAGE.md` | The computed coverage of the three scanners, with every residual sector named. §13 is the one measured section: the rear scanner's self-return band, from a live headless run. |
| `EVIDENCE_SENSOR_TF.md` | The dated runs behind the sensor frames and the measurement-channel consumer. |
| `EVIDENCE_ODOMETRY.md` | The dated runs behind the motion estimate: the IMU's noise against its datasheet, the wheel odometry against a known motion, real slip separated from the `cos δ` geometry, and the **measured drift** of the fused estimate. §12 is brief m5-07d's: the standstill handling, the idle hold, and the same route re-measured to show the drift while moving is unchanged. |
| `EVIDENCE_ODOM_TF.md` | The dated run behind `odom → base_link`: measured rate, captured `tf2` lookups, the residual against the odometry topic, and the seam where the EKF takes the edge over. |
| `amcl.yaml` | `nav2_amcl` and `nav2_map_server` parameters. Every non-default carries its reason in the file; the motion model is `DifferentialMotionModel` because a tricycle cannot translate sideways. |
| `launch/localization.launch.py` | The vehicle's **localization** stack: `map_server` over the frozen committed grid and `amcl` over `/forklift/scan` and the EKF's `forklift/odom → forklift/base_link`. Started against a running bringup; starts no plant, vehicle or estimator. AMCL becomes the sole publisher of `map → forklift/odom`. References `sim/maps/warehouse/` **read only**. |
| `scripts/localization_run.py` | The instrument behind `EVIDENCE_LOCALIZATION.md`: named open-loop drive profiles (dwell, reverse, forward, converge) that **subscribe to nothing**, a world→map pose conversion through the module that owns the registration, and an absolute scorer that apportions every heading change between AMCL and the EKF underneath it. |
| `EVIDENCE_LOCALIZATION.md` | The dated runs behind AMCL against the frozen map, scored **absolutely** through the committed registration with the 0.141 m floor stated beside every figure: steady state over the full mapping route, convergence from a 1.166 m / 10° wrong prior, a 128.7 s dwell in the worst degenerate stretch, and that stretch traversed fork first against a forward control. |
| `nav2.yaml` | The Nav2 stack, written for a **tricycle**: `SmacPlannerHybrid` with `REEDS_SHEPP` (reverse comes from the motion model, not from `allow_reverse_expansion`, which is a Lattice parameter), `RegulatedPurePursuit` with `use_rotate_to_heading: false` and `allow_reversing: true`, a **polygon** footprint padded by the measured localization error, and a `CLOSED_LOOP` velocity smoother. Every non-default carries its reason in the file. Contains no safety parameter. |
| `behavior_trees/navigate_to_pose_tricycle.xml` | The navigate-to-pose tree with nav2's `Spin` and `BackUp` recoveries **removed**: `Spin` has no `(δ, v_D)` solution on this vehicle and a blind reverse duplicates the planner without the map. What is left is clear the costmaps, wait, replan — and if it still cannot plan, stop and report. |
| `launch/navigation.launch.py` | The vehicle's **navigation** stack: planner, controller, behaviours, velocity smoother, `bt_navigator`, the Twist→tricycle converter and `forklift_io.py`. Started against a running bringup and localization. Registers every lifecycle handler before emitting the first transition. **It now starts the envelope gate as well, and `cmd_topic` defaults to the gate's output** — `gate:=false cmd_topic:=/cmd_vel_smoothed` restores the m5-10 chain. |
| `scripts/envelope_gate.py` | **The vehicle-side enforcer of the PLC's motion envelope** (ADR 0014 seam (b)), sitting **below** the velocity smoother: enable false, permit false, an invalid ceiling or mode, or an envelope older than the freshness window → a controlled ramp to zero on the vehicle's own deceleration; otherwise the command passes, clamped in **magnitude** to the ceiling with both components scaled so the arc survives. Reports its applied mode and a heartbeat back. In teleop it ramps to zero and **falls silent**, because the PLC owns the actuator topics there. It is **not** a safety function and **not** an OPC UA client. `--self-check` exercises the arithmetic with no ROS. |
| `launch/envelope.launch.py` | The gate's own measurement stack: the velocity smoother with `feedback` **overridable from the command line**, the gate, the converter and `forklift_io.py`, and no planner, controller or localizer. It is what makes the open-loop / closed-loop comparison a one-variable experiment. |
| `scripts/envelope_run.py` | The instrument behind `EVIDENCE_ENVELOPE.md`, and the **ROS 2 topic double** that stands in for the PLC: it publishes the six §12.10 envelope topics on a script — including the one interesting thing a double can do, **stop publishing** — records every stage of the chain in four files, and scores the run. No OPC UA, no bridge, no PLCSIM. |
| `EVIDENCE_ENVELOPE.md` | The dated runs behind the gate, on **the owner's WSL machine**: the controlled stop on an enable drop and on a stale envelope, the ceiling clamp at four values, pass-through fidelity, the permit, the readback and the source handover — and the measured open-loop / closed-loop difference at gate release that justifies `nav2.yaml`'s `CLOSED_LOOP`. |
| `scripts/cmd_vel_to_tricycle.py` | The one place a body twist becomes a steer angle and a drive-wheel **tread** speed: `δ = atan2(L·w·sign(v), \|v\|)`, `v_D = v / cos δ`. Closes no loop and holds no state but the last commanded steer. Refuses rotation in place — at a standstill only — and counts it. |
| `scripts/nav2_run.py` | The instrument behind `EVIDENCE_NAV2.md`: `goal` sends one world-frame goal through the committed registration and records the run at 10 Hz, `analyse` scores it absolutely, `plan` asks the planner alone for a path with no simulator, and `convcheck` checks the Twist→tricycle conversion against a **commanded motion**. Reads ground truth as a reference and drives nothing that navigates. |
| `scripts/footprint_from_model.py` | Derives the Nav2 footprint polygon from `model.sdf` (convex hull of every collision and visual primitive, steer axis at both stops) and checks it against `nav2.yaml`. `--aisle` scans the committed grid and reports how much lateral room the padded polygon actually leaves. No simulator. |
| `EVIDENCE_NAV2.md` | The dated runs behind autonomy: the five Jazzy parameter traps each probed on a running node, the footprint derivation, the Twist→tricycle conversion checked against a **commanded motion**, and four measured cases — a straight aisle traverse, a reverse segment, a goal in the named degenerate stretch, and a goal the planner refuses, with what refusal looks like from outside. |
| `vehicles/allocation.yaml` | **The one owner of the serial → DDS domain mapping** (ADR 0016 D1, invariant 10). No other file in this repository pairs a serial with a domain ID, and no per-vehicle config carries one. It also reserves the operator/monitoring domain and the vehicle band. |
| `vehicles/F001.yaml` | **One forklift's identity**: its VDA 5050 `serialNumber`, its spawn pose (world frame, a simulation datum) and its initial pose (map frame, the datum a real vehicle is given). Everything that makes this machine *this* machine, and nothing that is true of every forklift. |
| `scripts/vehicle_identity.py` | The single reader of the two files above. Joins them, validates the allocation and **refuses** — an unallocated serial, a duplicate domain, an ID outside the safe 0–101 range, a per-vehicle file carrying its own domain. `--self-check` exercises every refusal with no ROS. |
| `scripts/vehicle_image.py` | **Starts one vehicle's own computer.** The stand-in for the systemd unit a real forklift would run (ADR 0016 D5): it resolves the identity, puts the process into that vehicle's DDS domain and hands over to the launch below. |
| `launch/vehicle_image.launch.py` | **Everything the vehicle's own computer runs**, in one launch and one domain: the gz bridges including `/clock`, sensor TF, wheel odometry, the gyro gate, the EKF, map server and AMCL, the whole Nav2 stack, the envelope gate, the converter and `forklift_io`. It starts **no** Gazebo server — the sim side owns the world. Refuses if the domain it was handed is not the allocated one. |
| `scripts/check_contract_topics.py` | Parses the ROS contract table below out of this file and diffs it against a running graph. `--expect-absent` inverts the verdict, which is how "the vehicle is not visible from this domain" is a pass with a name rather than an empty screen. |
| `EVIDENCE_VEHICLE_IMAGE.md` | The dated run behind ADR 0016 Phase 1: the vehicle image inside its own domain, the boundary demonstrated by failing to cross it from three other domains, the contract diffed from inside, a Nav2 goal accepted, and the m5-11 §7 observation re-run. |
| `evidence/` | The raw recordings, leg marks, captured `/tf` publisher lists and verbatim scorer output for `m5-07e`, `m5-08e` and `m5-11`. Every figure in the evidence files above is recomputable from them. |

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
| `/forklift/gz/drive_speed/read_a` | `gz.msgs.Model` | out of the model | **One of two reads of `drive_wheel_joint`**, published by its own `JointStatePublisher` instance at the physics rate. Bridged into ROS **only with `safe_speed:=true`**, un-renamed. See "One shaft, two readings" below |
| `/forklift/gz/drive_speed/read_b` | `gz.msgs.Model` | out of the model | The second read of the **same** joint, from a second instance. Same rate, same value: it is the same shaft. What makes the two READINGS differ is the reading head, and the heads are modelled in `scripts/safe_speed_channels.py`, not here |
| `/forklift/gz/odom` | `gz.msgs.Odometry` | out of the model | **ground-truth** pose and body twist, 20 Hz. Straight out of the simulator: no slip, no drift. See "Odometry in two phases" below |
| `/forklift/gz/tf_ground_truth` | `gz.msgs.Pose_V` | out of the model | `forklift/odom → forklift/base_link`, 20 Hz, from the **same ground-truth pose** as the row above. **Retired as a source on 2026-07-31**: the EKF owns that edge now and `ground_truth_tf` defaults to `false`, so nothing bridges this onto `/tf`. It is still published, as the **reference** estimator error is measured against, and read only by `scripts/check_odometry.py` |
| `/forklift/gz/imu` | `gz.msgs.IMU` | out of the model | 6-axis MEMS IMU, 100 Hz, frame `imu_link`, noise from the BMI088 datasheet. **No orientation output** — `<enable_orientation>false</>`, because gz derives orientation from the link pose and it would be ground truth. The IMU *system* is carried by the model, not the world, so no world file needs editing |
| `/forklift/gz/scan_nav` | `gz.msgs.LaserScan` | out of the model | navigation lidar: 360 ranges over 360°, 10 Hz, 0.10–8.00 m, plane z = 1.80 m, frame `nav_lidar_link` |
| `/forklift/gz/safety_scanner_front/measurement` | `gz.msgs.LaserScan` | out of the model | front safety scanner, **non-safe measurement channel**: 275 ranges over 275°, 10 Hz, 0.10–5.50 m, plane z = 0.15 m, frame `safety_scanner_front_link`. Bridged into ROS |
| `/forklift/gz/safety_scanner_rear/measurement` | `gz.msgs.LaserScan` | out of the model | rear safety scanner, **non-safe measurement channel**: same, frame `safety_scanner_rear_link`. **Bridged into ROS since 2026-08-06 (m5-12b)**, under the name reserved for it, because a consumer now exists: `scripts/field_evaluation.py` needs both devices |

### Two channels per safety scanner, and only one of them is a topic

The device class modelled — a 275° safety laser scanner of the
microScan3 class (ADR 0011, fact F8) — emits **two outputs from one
device**:

| Channel | What it is | Where it lives here | Who may consume it |
|---|---|---|---|
| **safe channel** | the OSSD pair, or safe bits over PROFIsafe: the protective-field verdict | **on no topic, on either transport.** Derived from the same rays by `scripts/field_evaluation.py` (m5-12b, phase 1 of `FIELD-EVALUATION.md`), which is a **model of what the device does inside its own housing** and carries no claim. It leaves the vehicle on **one dedicated TCP connection** to the stand-in writer of `plc/forklift-safety/SPEC.md` §7.2 — never on the process network | the F-program, through the stand-in writer, and nothing else |
| **measurement channel** | the raw distance profile the datasheet provides for HMI, diagnostics and process use, **while stating it must not be used for safety-related tasks** | the `gpu_lidar` scan, on the gz and ROS topics named `.../measurement` above | process functions. Today: `obstacle_zone.py` (front). `field_evaluation.py` reads both, and its **protective** verdict is *not* a measurement channel and *not* a topic. Its **warning** verdict is neither the safe channel nor a measurement channel but a **process verdict**: SF-04 carries no PL claim, trips a speed reduction rather than a stop, and is backed unconditionally by SF-03, so it may — and does — have a topic (m5-47) |

**By which path the safe channel reaches the F-program is settled.**
ADR 0011 decision 2 named configured F-I/O driven by tag name through the
S7-PLCSIM Advanced API. `plc/forklift-safety/FIO-FEASIBILITY.md` ran that
probe in the tool and the named fallback is what stands: the standard-DB
**stand-in for wiring** of `plc/forklift-safety/SPEC.md`, written by the
stand-in writer, labelled a stand-in wherever it appears. Nothing in this
directory changes under either answer, and no Category, Performance
Level, SIL or PFH is claimed for any of it (ADR 0011 D5).

**The measurement channel is non-safe and must never implement a safety
function.** Nothing computed from it is a protective stop, a safe speed,
an enable or a reset, whatever the device it came from is called.

The naming rule, so a later reader cannot confuse the two: **every
channel a subscriber can reach is a measurement channel, and says
`measurement` in its name. The safe channel has no topic, on either
transport, ever.** `scripts/check_sensor_frames.py` section 4 checks
both halves of that sentence rather than leaving it as a promise.

**How the safe channel reaches the F-program is design intent, not
settled fact.** ADR 0011 decision 2 makes it **configured F-I/O** — an
ET 200SP F-DI parameterised as the scanner's OSSD pair — whose channel
values the **S7-PLCSIM Advanced API drives by tag name**, this project's
analogue of the copper an OSSD pair runs on. **That path has never been
run.** The two tool questions it rests on — whether this PLCSIM Advanced
version and its safety system version simulate F-I/O at all, and whether
the API writes a configured F-DI's channel values by tag name — are
settled *in the tool* by `plc/forklift-safety/FIO-FEASIBILITY.md` under
brief **m5-03**, whose verdict section is blank as this is written. If
either answers no, the fallback ADR 0011 decision 2 names is the
**standard-DB stand-in** of `plc/forklift-safety/SPEC.md`, labelled a
stand-in wherever it appears. Nothing in this directory changes under
either answer: the safe channel is not a topic on either path, and no
file here stimulates it.

**One device, one ray cast: the split is not redundancy.** Both channels
come out of the *same* `gpu_lidar` render. That is honest device
modelling — a real scanner derives its safe output from its own
measurement core too — but it means the two channels **share every
failure of the rays**, and nothing here may be read as two independent
channels. `EVIDENCE_SENSOR_COVERAGE.md` makes it concrete: **R7** is a
live instance, where the mast's 0.72 m collision slab is `<visual>`-less
and the simulated shadow is 8.9° against a physical 29.0°, so a target
inside that wedge is invisible to the process stop **and** to the field
evaluation on the same scan; **R8** is the converse, where the rear
device's own body returns would sit inside any protective field drawn
over that sector. What the split buys is naming hygiene and consumer
separation — one channel on the network, one never on it. It buys no
diversity, no second opinion and no fault detection, and no document in
this project may present it as though it does.

**Why a process function reading a safety device is not a layer
violation.** The process function consumes the device's *process* output;
the safety function consumes the device's *safe* output. Downstream of
the sensor they are two outputs of one device travelling two paths that
never meet — upstream of it they are one measurement, per the note
above. What
ADR 0011 forbids is a safety scanner feeding a **navigation** consumer —
SLAM, AMCL, a costmap — and that prohibition is unchanged: **the
navigation lidar is the only SLAM input**, on `/forklift/scan`, and no
scanner channel reaches a costmap.

### One shaft, two readings — the safe-speed encoder

`model.sdf` carries **two `JointStatePublisher` instances on
`drive_wheel_joint`**, on the two `/forklift/gz/drive_speed/read_*` topics
above. `scripts/safe_speed_channels.py` puts a **reading head** on each —
its own mounting phase on the count grid, its own read jitter — and
publishes two signed drive-wheel tread speeds for the F-program to
cross-compare.

**Its honest name is a SINGLE-CHANNEL TESTED SYSTEM, and that name is
used in every artefact.** One shaft, one measured quantity, two readings
of it. That is what a real safe encoder is
(`docs/safety/SLS-STANDARDS-BASIS.md` F4, which records a manufacturer's
own classification of exactly this architecture). The arrangement is
**never called two-channel**: both readings die together with the shaft
they read, and the phrase would claim a redundancy that does not exist.

| | |
|---|---|
| What the two reads buy | **Diagnostic coverage of the reading path.** A head that freezes, drifts or stops publishing is visible to a comparison; a single head's failure is not |
| What they do **not** buy | Any cover for the shaft, its bearing or its coupling. Both readings are of one physical quantity, and a lie in that quantity is a lie in both |
| What closes that hole | A **motion-present observation**, off the shaft entirely — see below |
| The comparison the F-program makes | Disagreement of more than **0.0308 m/s** sustained for more than **200 ms**. Both figures are **derived from the measured channel noise** — `EVIDENCE_ODOMETRY.md` §15 — because a discrepancy time chosen for convenience is either a nuisance-demand generator or a blind window, and both failures are quiet |
| The claim attached | **None.** No Category, no Performance Level, no SIL, no PFH (ADR 0011 D5). The readings reach the F-program as **standard data** over the process path, which is a stand-in for a safe measurement channel and is labelled one wherever it appears |

**The motion-present check is a STAND-IN, and is labelled one.** Two
readings of one shaft agree perfectly while a decoupled encoder reports
zero and the vehicle rolls. Real systems close that hole with a
**mechanical fault exclusion** argued on the coupling — a construction
argument made once at design time, not a monitored signal
(`SLS-STANDARDS-BASIS.md` F4, citing the standard's own table on loss of
the encoder-to-motor connection). This project has no such argument
available, so it substitutes an **observation**: the change in the
navigation lidar's range profile between scans, which shares no shaft,
no bearing and no cable with the drive axis. It reads the **95th
percentile** of the per-ray change and not the median, and that choice is
measured rather than assumed (§15.5): a wall parallel to the direction of
travel returns the same profile from every point along it, so a majority
of usable rays do not change while the vehicle drives, and the median
read *not moving* for 1037 of 6538 sustained-motion samples.

**Why the readings may be topics when the scanner's safe verdict may
not.** These are readings, not verdicts. The verdict they feed — the SLS
demand — is formed inside the F-program and has no topic on either
transport, exactly as before. Their names carry no `safe_`, `ossd` or
`protective` token, and that is enforced by
`scripts/check_sensor_frames.py` section 4 rather than left to style:
they were called `/forklift/safe_speed/*` while being built and the
checker refused them, correctly, because a mechanical rule cannot tell a
reading from a verdict.

**Who limits and who monitors.** The **standard** program lowers the
envelope speed ceiling; the **F-program** measures the real speed from
these two readings and demands a stop if it is exceeded. That split is
the certified pattern rather than this project's invention
(`SLS-STANDARDS-BASIS.md` F5), it keeps the ceiling's single owner
(invariant 10), and it is why **no speed value ever leaves the
F-program** — only a demand (ADR 0014).

**Off by default.** Both the bridge and the node are conditioned on
`safe_speed:=true`, because the two reads publish at the physics rate.
Forgetting the argument is safe: with the node absent the F-program
receives no readings, and a missing measurement reads as a demand.

### The four sensors, and which one feeds what

| Sensor | Link and `frame_id` | Pose in `base_link` (x, y, z, yaw) | Aperture, blind sector | Consumer |
|---|---|---|---|---|
| `nav_lidar` | `nav_lidar_link` | 0.550, −0.400, 1.800, 0° | 360° | `/forklift/scan`: **SLAM, AMCL and the Nav2 costmaps, and nothing else feeds them** |
| `safety_scanner_front` | `safety_scanner_front_link` | 0.700, 0.450, 0.150, +45° | 275°, blind 182.5–267.5° | measurement channel → `obstacle_zone` (process) and `field_evaluation`. Safe channel → the F-program, off-network, through the stand-in writer (see above) |
| `safety_scanner_rear` | `safety_scanner_rear_link` | −0.700, −0.450, 0.150, −135° | 275°, blind 2.5–87.5° | measurement channel → `field_evaluation`, and bridged since 2026-08-06 for it. Safe channel → the F-program, off-network, through the stand-in writer (see above) |
| `imu` | `imu_link` | −0.500, 0.000, 0.250, 0° | 6 axes, 100 Hz, **no orientation output** | `/forklift/imu`: the EKF, and it fuses the **yaw rate only**. Mounted on the rear axle line, where a tricycle's instantaneous centre of rotation always lies, so a steady turn produces no centripetal term |

The pose column is **parsed**, not decorative: `check_sensor_frames.py`
section 2 reads these four rows out of this file and compares them to
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

**Why the rear channel is bridged now, and was not before.** The rule
never changed: a measurement channel goes onto the process network when
something on that network consumes it, and not before, because an
unconsumed channel is an invitation to a drive-by subscriber and the
subscriber that must never appear is a navigation one. What changed on
2026-08-06 is that the consumer exists — `scripts/field_evaluation.py`
needs **both** devices, since the protective verdict is the union of the
two and the fork direction is the rear device's to watch. It took the
name this file had already reserved for it,
`/forklift/safety_scanner_rear/measurement`, verbatim.

### ROS 2, after `launch/vehicle.launch.py`

| ROS topic | Type | Rate | Produced by | Meaning |
|---|---|---|---|---|
| `/forklift/cmd/traction_speed` | `std_msgs/Float64` | on demand | a consumer | ground speed request [m/s] |
| `/cmd_vel` | `geometry_msgs/Twist` | 20 Hz while a goal is active | `controller_server` | The controller's body twist. **`Twist`, not `TwistStamped`**: on Jazzy `enable_stamped_cmd_vel` defaults false and `nav2.yaml` pins it, because a subscriber of the wrong type receives nothing and logs nothing about it |
| `/cmd_vel_smoothed` | `geometry_msgs/Twist` | 20 Hz | `velocity_smoother` | The same twist, ramp limited **closed loop against `/forklift/odom_filtered`** and scaled as a whole so the curvature `w/v` survives. **Read by the envelope gate**, which now sits between this topic and the converter (ADR 0014 seam (b), m5-11) — inserted through `navigation.launch.py`'s `cmd_topic` argument, whose default is now `/cmd_vel_gated`. **Closed loop is not a preference here**: with a gate below it, an open-loop smoother goes on ramping while the vehicle is held at zero and hands over a step at release — measured at **+0.5000 m/s and 3.52 m/s²** against **+0.0250 m/s and 0.41 m/s²** closed loop (`EVIDENCE_ENVELOPE.md` §6) |
| `/cmd_vel_gated` | `geometry_msgs/Twist` | 20 Hz | `envelope_gate` | **The envelope gate's output, and what the converter now reads.** While the envelope is permissive it is the message above, emitted unchanged unless the speed ceiling bites, in which case both components are scaled by one factor so the arc survives. While it is not — enable `FALSE`, permit `FALSE`, an invalid ceiling or mode, or an envelope older than `envelope.stale_window_s` — it is a controlled ramp to zero at `envelope.stop_decel_mps2` and then a held zero. **It is not a safety signal**: loss of the envelope is a degraded mode, not a safety event (invariant 2), and the onboard protective stop reaches no topic. Measured in `EVIDENCE_ENVELOPE.md` |
| `/forklift/envelope/motion_enable` | `std_msgs/Bool` | 20 Hz | the bridge (a double at M5) | **The PLC's permission for autonomous motion** (`opcua-nodes.md` §12.4). **It permits; it never commands** — `TRUE` is not an instruction to move. `FALSE` is the non-permissive value and is what a cold start reads |
| `/forklift/envelope/speed_ceiling` | `std_msgs/Float64` | 20 Hz | the bridge (a double at M5) | **An upper bound on the magnitude of ground speed [m/s], unsigned**, not a setpoint and not a target. A value outside `0.00 … envelope.ceiling_max_mps` is a broken supervisor and is non-permissive to this consumer, never a bound to clamp |
| `/forklift/envelope/equipment_permit` | `std_msgs/Bool` | 20 Hz | the bridge (a double at M5) | **The fixed-equipment / station permit** (ADR 0012 D1): *is the equipment I own ready for you to act on it?* — **never** *may you be here?*, which is the fleet manager's zone reservation and reaches no node and no topic here. `FALSE` is non-permissive to the gate, which is this layer's conservative reading of a reaction §12 does not specify |
| `/forklift/mode/in_force` | `std_msgs/UInt16` | 20 Hz | the bridge (a double at M5) | **The authoritative answer to "what mode is the machine in"**: `0` None, `1` Teleop, `2` Autonomous (`opcua-nodes.md` §12.3). The gate applies the autonomous law only in `2`; in `1` it ramps to zero and then **falls silent**, because the PLC owns `/forklift/cmd/*` in teleop |
| `/forklift/mode/applied` | `std_msgs/UInt16` | 20 Hz | `envelope_gate` | **A readback, never a second answer** to the question above. It reports what the gate is applying **now**, so it lags the mode in force by the adopt window rather than echoing it |
| `/forklift/vehicle/heartbeat` | `std_msgs/UInt16` | 20 Hz | `envelope_gate` | The gate's own cycle counter, wrapping at 65536. Its only meaning is "the vehicle's control layer completed a cycle recently"; it carries no process information and is **not** a second bridge heartbeat |
| `/forklift/envelope/gate_state` | `std_msgs/UInt16` | 20 Hz | `envelope_gate` | Diagnostic of that node: `0` PASSING, `1` STOPPING, `2` HOLD_ZERO, `3` SILENT. Not a vehicle state and not a PLC datum |
| `/forklift/nav/tricycle_refusals` | `std_msgs/UInt32` | on demand | `cmd_vel_to_tricycle` | Monotonic count of **rotation-in-place requests refused at a standstill**. A nonzero count means something upstream is commanding a differential base — it is the standing check that nav2's `Spin` recovery has not come back. Not a safety signal and not a machine state |
| `/forklift/cmd/steer_angle` | `std_msgs/Float64` | on demand | a consumer | steer angle request [rad] |
| `/forklift/cmd/fork_speed` | `std_msgs/Float64` | on demand | a consumer | carriage rate request [m/s] |
| `/forklift/fork_height` | `std_msgs/Float64` | 10 Hz | `forklift_io` | carriage travel above fully lowered [m] |
| `/forklift/linear_speed` | `std_msgs/Float64` | 10 Hz | `forklift_io` | forward ground speed [m/s] |
| `/forklift/safety_scanner_front/measurement` | `sensor_msgs/LaserScan` | 10 Hz | bridge | **The front safety scanner's non-safe measurement channel**, renamed from `/forklift/gz/safety_scanner_front/measurement`: 275 samples over 275°, plane z = 0.15 m, range 0.10–5.50 m, frame `safety_scanner_front_link`. Read by `obstacle_zone` and by `field_evaluation`. **Not a safety signal**, whatever the device is called, and forbidden to SLAM, AMCL and every costmap. |
| `/forklift/safety_scanner_rear/measurement` | `sensor_msgs/LaserScan` | 10 Hz | bridge | **The rear safety scanner's non-safe measurement channel**, renamed from `/forklift/gz/safety_scanner_rear/measurement`: same shape as the front one, frame `safety_scanner_rear_link`. Bridged 2026-08-06 because `field_evaluation` consumes it. **Not a safety signal**, and forbidden to SLAM, AMCL and every costmap. Expect a large near-field band on this device: 61 of its 275 rays land on the vehicle's own mast rails and carriage at 0.090–0.780 m (residual **R8**, measured in `EVIDENCE_SENSOR_COVERAGE.md` §13). Those returns are real and are not filtered out anywhere; what `field_evaluation` does with them is draw its **field boundary inside them**, which is device geometry, not a filter. |
| `/forklift/warning_field/occupied` | `std_msgs/Bool` | 20 Hz | `field_evaluation` | **The WARNING field's verdict, and the only field verdict that has a topic.** `TRUE` demands a **speed reduction** to the creep ceiling; it never stops anything, and it is not the protective verdict, which crosses only the dedicated link and appears on no transport. Derived at **3.35 m** of depth in `FIELD-EVALUATION.md` §6.1 — larger than the protective 1.35 m by exactly the distance the vehicle and a walking intruder close while the reduction runs. **`TRUE` is the demanding state and every failure reads it**: a dead, stale, frozen, discrepant or faulted device is `TRUE`, and an empty horizon is not — a beyond-range return is a measurement. Occupation asserts on one scan; release needs three clear scans **and then** SF-04's 2 s clear-hold. **Published at the evaluation tick and not on transitions**, so that its ABSENCE is visible: a consumer that republishes the last value it saw would turn this node's death into a standing order to keep driving fast, so **every consumer owes a stale rule of its own — no message inside its window means occupied**. SF-04 carries **no PL claim** and is backed unconditionally by SF-03. **No consumer exists yet** (m5-47). |
| `/forklift/drive_speed/channel_a` | `std_msgs/Float64` | 20 Hz, **only with `safe_speed:=true`** | `safe_speed_channels` | **One of two readings of the drive shaft**, signed drive-wheel tread speed [m/s]. `model.sdf` carries two `JointStatePublisher` instances on `drive_wheel_joint`; this node puts a reading head on each — its own mounting phase on the count grid, its own read jitter — and differences the quantised angle over one publish interval. **The arrangement is a SINGLE-CHANNEL TESTED SYSTEM: one shaft, two readings of it, never a two-channel one**, because both readings die together with the shaft they read. It is a **model of what a safe encoder does**, reaching the F-program as **standard data**: no Category, no Performance Level, no SIL, no PFH (ADR 0011 D5). **Tread speed, not body speed** — the drive wheel is steered, so body speed is this × cos δ and never larger, which makes the monitor conservative and keeps the steer axis out of the measurement. **A stale channel goes SILENT rather than repeating**, so every consumer owes a stale rule: no message inside its window means **no reading**, which is a missing measurement and reads in the demanding direction. |
| `/forklift/drive_speed/channel_b` | `std_msgs/Float64` | 20 Hz, **only with `safe_speed:=true`** | `safe_speed_channels` | The second reading of the **same** shaft, with an independently drawn mounting phase and an independently drawn jitter per sample. Everything in the row above applies. The F-program cross-compares the two and demands when they disagree by more than **0.0308 m/s** for longer than **200 ms** — both derived from the measured channel noise in `EVIDENCE_ODOMETRY.md` §15, not chosen. |
| `/forklift/drive_speed/motion_present` | `std_msgs/Bool` | 20 Hz, **only with `safe_speed:=true`** | `safe_speed_channels` | **A STAND-IN, and labelled one.** Two readings of one shaft lie together if the shaft or its coupling fails, so a claimed zero speed is corroborated against an observation that does not pass through the shaft: the change in the **navigation lidar's** range profile between scans. Real systems close this hole with a **mechanical fault exclusion** argued on the coupling — a construction argument, not a monitored signal (`docs/safety/SLS-STANDARDS-BASIS.md` F4) — and this project has none available, so it substitutes an observation and says so. **`TRUE` is the demanding state and every uncertainty reads it**: no scan, a stale scan, too few usable ray pairs, an empty horizon. A wrong `TRUE` costs a withheld standstill confirmation, which SS1 pays for with its timeout; a wrong `FALSE` would corroborate a lying encoder. |
| `/forklift/drive_speed/motion_observation_valid` | `std_msgs/Bool` | 20 Hz, **only with `safe_speed:=true`** | `safe_speed_channels` | Whether the observation above could be made at all. `FALSE` never softens the verdict — it accompanies `motion_present` `TRUE`. It exists so a consumer can tell *observed to be moving* from *could not observe*, which are the same demand and different diagnoses. |
| `/forklift/obstacle/in_stop_zone` | `std_msgs/Bool` | 10 Hz | `obstacle_zone` | Something inside the forward stop zone, computed from the **front safety scanner's measurement channel** at z = 0.15 m — the low plane the M4 showcase demonstrated, not the 1.80 m navigation plane. **`TRUE` is the non-permissive state.** The ±30° sector is centred on the vehicle's driving direction, which is `obstacle.sector_centre_rad` = −45° in this sensor's own angle coordinate because the sensor is mounted on a corner at +45°. The evaluator sorts every sample in that sector into three classes: **clear** — `+inf`, or a finite range at or beyond `range_max`, which is the sensor reporting no echo inside its window and counts as a valid measurement at `range_max`; **distance** — a finite range inside `[range_min, range_max)`; **invalid** — `NaN`, `-inf`, or a range below `range_min`. `TRUE` when a distance is at or under 1.20 m, and `TRUE` as a fail-safe when there is no scan, when the newest one is older than 0.50 s, when the scan is structurally unusable, or when the sector holds no sample in **either** valid class. A dead or garbage sensor is all of those; an open horizon is none of them. |
| `/forklift/obstacle/min_distance` | `std_msgs/Float64` | 10 Hz | `obstacle_zone` | Nearest valid range in the sector [m]: the smallest **distance**-class sample; the scan's own `range_max` when the sector is entirely **clear** beyond range; and `0.0`, the `unknown_distance_m` sentinel from `config.yaml`, in every fail-safe case above. The clear value is the scan's number and not this node's, so it follows whatever scanner `model.sdf` declares — and the consumer's plausibility window must contain it. Since this node reads the front safety scanner, that value is now **5.50 m**, comfortably inside the `0.05 … 8.10` m window of `docs/interfaces/opcua-nodes.md` §10.5, so **no interface change is owed by this consumer**. The window still bounds the *navigation* lidar's 8.00 m range, which is a separate open item. |
| `/forklift/scan` | `sensor_msgs/LaserScan` | 10 Hz | bridge | **The navigation lidar**, renamed from `/forklift/gz/scan_nav`: 360 samples over 360°, plane z = 1.80 m, frame `nav_lidar_link`. **This is the vehicle's only SLAM, AMCL and costmap input**, and it is no longer read by `obstacle_zone`: it replaced a 181-sample 180° scanner at z = 0.25 m, so **the plane this topic reports moved up 1.55 m**, and in `sim/worlds/forklift_arena.sdf`, whose walls stop at 0.60 m and whose tallest crate stops at 1.00 m, it reports a clear horizon in front of an obstacle a process stop must see (`EVIDENCE_SENSOR_TF.md` §4 measures exactly that: 60 of 60 forward samples clear at 1.80 m with a crate 0.85 m ahead at 0.15 m). **Not gap-free.** The old scanner dropped the single sample at exactly ±45°, in the raw gz message rather than in the bridge, following vehicle orientation rather than a fixed index (m4f-03 evidence). **That was measured on the sensor this one replaced and has not been re-measured here**, so it is a warning and not a specification. The consumer rule is unchanged and stands on its own: do not assume every sample is finite, and do not read a non-finite one as a missing one — an `inf` is the sensor reporting **no echo inside its window**, which is a measurement of a clear path to `range_max`, not an absence of data. `obstacle_zone.py` classifies each sample on exactly that basis and never condemns a whole scan for containing one bad sample. |
| `/forklift/odom` | `nav_msgs/Odometry` | 20 Hz | bridge | **Ground-truth** odometry, renamed from the gz topic. The name does not say so, and that is a known defect this directory could not fix alone: `/forklift/odom` is a cross-layer contract (`sim/launch/forklift_bringup.launch.py` bridges it, `sim/scenarios/run_forklift_rehearsal.py` reads it). The EKF has now landed, so `/forklift/odom` is the name the **estimate** should carry and this stream should move to `/forklift/odom_ground_truth`. Requested in `docs/reports/m5-07b-odom-tf.md` and again in `m5-07c-realistic-odometry.md`; not taken here. **Read by no estimator** — only by `scripts/check_odometry.py`, as the reference |
| `/forklift/imu` | `sensor_msgs/Imu` | 100 Hz | bridge | The IMU, renamed from `/forklift/gz/imu`, frame `imu_link`. **Angular velocity and linear acceleration only.** The orientation field arrives as the zero quaternion `(0,0,0,0)` with `orientation_covariance[0] = 0.0`, which by the ROS convention reads as *known exactly* rather than the `-1` that means *absent* — **do not consume it**, it would be simulator ground truth even if it were well formed. The EKF fuses the **yaw rate only**, and it fuses it from `/forklift/imu_gated` rather than from here; the accelerometer is not fused, because a 0.0196 m/s² bias integrated twice is 98 m of position error over 100 s |
| `/forklift/imu_gated` | `sensor_msgs/Imu` | 100 Hz **while moving**, silent while standing | `imu_gate` | **The gyro as a rotation sensor**, which it is only while the vehicle can rotate. Every message is forwarded byte for byte from `/forklift/imu` except while `/forklift/wheel_standstill` is true and fresh, when none is. `ekf.yaml` names this topic and never the raw one. **A gap is the signal, not a fault** — the gate suppresses rather than rewrites, so a zeroed rate can never be mistaken for a reading the device took. It **estimates no bias and carries nothing into motion**, so the drift while driving is unchanged (`EVIDENCE_ODOMETRY.md` §12.4, re-shown at §13.9 — one gyro sample in 12 100 differs). Fails **open** in every direction |
| `/forklift/wheel_standstill` | `std_msgs/Bool` | 50 Hz | `wheel_odometry` | **A rate test over a trailing 0.50 s window**: the drive count's spread is 0 and the steer count's is at most 1. A tricycle's centre of rotation lies on its rear axle line and its drive wheel does not, so a held drive count bounds the body rotation over that window at **0.0101°** — which is why a gyro reading taken in this condition is bias rather than rotation. The drive term carries that bound and its tolerance is zero; the steer term is a **rate guard with no bound behind it**, at 0.176 °/s. **It is a rate and not a total**, because a test of the form "unchanged since t₀" with t₀ receding fails under any creep however slow — which is what the steer axis's post-drive relaxation did, for 2.11° of heading over a 210 s idle (`EVIDENCE_ODOMETRY.md` §13). **It is an estimator input, not a machine state**: it does not mean the vehicle is enabled, parked, safe or stopped, it inhibits nothing and it latches nothing. One consumer, `imu_gate` |
| `/forklift/odom_wheel` | `nav_msgs/Odometry` | 50 Hz | `wheel_odometry` | **One sensor's opinion**, not the vehicle's pose: tricycle dead reckoning from `/forklift/joint_states` through two modelled encoders. Twist in the body frame, including the real lateral term `d·yawrate` that `base_link` has because it stands 0.50 m ahead of the rear axle. **Publishes no transform**, and its pose covariance is deliberately useless (1000) because dead-reckoning pose error is unbounded — the EKF fuses the twist and never the pose |
| `/forklift/odom_filtered` | `nav_msgs/Odometry` | 50 Hz | `forklift_ekf` | **The estimate.** `robot_localization` fusing `odom_wheel` (`vx`, `vy`, `vyaw`) with the IMU (`vyaw`). This node, and no other, publishes `forklift/odom → forklift/base_link` |
| `/tf` | `tf2_msgs/TFMessage` | 50 Hz | `forklift_ekf` | `forklift/odom → forklift/base_link`, **the vehicle's own motion estimate**. It drifts while it drives, which is the point: **−12.88° of heading over 110.74 s of driving**, on a 106.49 m path with 1449.8° of turning (`EVIDENCE_ODOMETRY.md` §12.4; the same route measured −12.98° with the gyro gate off, and brief m5-07c's own run of it gave 5.21 m / −17.18° whole-run). **It does not drift while the vehicle stands still**: 0.00° over a 240 s idle, against the −35.79° the ungated gyro would have integrated (§12.3). **Exactly one publisher, measured** — `ros2 topic info /tf --verbose` reports `Publisher count: 1` — and enforced: the launch refuses to start the retired ground-truth bridge alongside it. Every consumer needs `use_sim_time:=true` and must **wait** for the transform rather than assume it at start-up |
| `/forklift/joint_states` | `sensor_msgs/JointState` | physics rate | bridge | joint state, renamed from the gz topic |
| `/forklift/safety/torque_off_demand` | `std_msgs/Bool` | on change, from the bridge | F-program, via the bridge | **The SS1 sequencer's second stage, formed inside the CPU** (`plc/forklift-safety/SPEC.md` §11.7) and consumed here. `TRUE` removes torque at the plant. **This layer forms it nowhere**: one datum, one owner (invariant 10). Its ABSENCE is not torque-off — loss of supervision is a degraded mode and not a safety event (invariant 2), and the controlled stop that calls for is the envelope gate's stale rule, one layer up. So the contactor latches on an observed `TRUE` and releases on an observed `FALSE`, and a link that never speaks leaves it closed. |
| `/forklift/safety/torque_off_applied` | `std_msgs/Bool` | 20 Hz | `sto_contactor` | **What the contactor did**, published as a readback for the monitoring plane. Nothing commands from it. It is the one signal that tells "the vehicle cannot move" from "the vehicle is not moving": with the contactor **not running** the plant is equally motionless, and this topic then has no publisher at all — which is how a dead contactor is told from a torque-off (measured, `EVIDENCE_STO.md` §5). |
| `/forklift/gz/*_cmd` | `std_msgs/Float64` | on change | `forklift_io` | the raw joint commands. **They no longer reach the model directly** (m5-50): `model.sdf`'s three joint controllers listen on `/forklift/gz/actuator/*_cmd`, the motor terminals, and `sto_contactor` is the terminals' only publisher and forwards these to them one message for one message while torque is present. Measured residual **0.0** over **299 of 299** pairs, hop **0.40 ms** mean / **0.84 ms** max. |
| `/forklift/gz/actuator/*_cmd` | `std_msgs/Float64` | on change | `sto_contactor` | **The motor terminals.** What the model actually listens on, and the reason the interlock cannot be bypassed: five committed publishers address the command topics directly, so an interlock in any one command node would be bypassed by the other four. **The contactor is a STAND-IN for the hardwired onboard inhibit** — Python, on the process side — and no Category, Performance Level, SIL or PFH is claimed for it or implied by it (ADR 0011 D5). |

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

The tree has two halves on two topics, and both are needed before a scan
can be put on a map:

```
  map                     absent. No SLAM, no AMCL yet, and the name is
   |                      not decided (M6 has four vehicles)
   |
  forklift/odom           /tf, 50 Hz, from the EKF (forklift_ekf).
   |                      THE ESTIMATE. It drifts, and that is the point
   |
  forklift/base_link
   |
   +-- nav_lidar_link                  /tf_static, from sensor_tf.py
   +-- safety_scanner_front_link       /tf_static, from sensor_tf.py
   +-- safety_scanner_rear_link        /tf_static, from sensor_tf.py
   +-- imu_link                        /tf_static, from sensor_tf.py
```

**Exactly one publisher of `forklift/odom → forklift/base_link`, and it
is checked rather than asserted**: `ros2 topic info /tf --verbose` reports
`Publisher count: 1`, `forklift_ekf`. The launch file refuses to start
with the retired ground-truth bridge enabled as well, because tf2 does
not complain about two publishers of one edge — the listener takes
whichever arrived last, so the symptom is a pose that alternates between
drifting and perfect with no error anywhere.

`EVIDENCE_ODOMETRY.md` is the dated run behind the estimate:
**5.21 m of position error and −17.18° of heading over a 106.49 m path
with 1449.8° of turning.** `EVIDENCE_ODOM_TF.md` remains the dated run
behind the transform's *plumbing*, taken while ground truth still filled
it: 20.000 Hz measured, the chain resolved through a real `tf2` buffer,
residual max 0.000e+00 m over 253 paired samples.

Three things every consumer of this tree inherits:

- **`use_sim_time:=true`, mandatory.** Every message is stamped with the
  simulation clock. A consumer on the system clock asks for a transform
  ~1.8e9 s newer than any it holds and reports a *missing transform*
  rather than a misconfigured node.
- **Wait for the transform, bounded.** A `TransformListener` fills its
  own buffer, so "published" and "answerable" are different moments
  (`EVIDENCE_SENSOR_TF.md` §2, and both `tf2_echo` captures in
  `EVIDENCE_ODOM_TF.md` §4 show it).
- **The names carry the model prefix on the parent pair and not on the
  sensor frames.** That asymmetry is Gazebo's; renaming either side to
  tidy it stops the lookups resolving.

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

### Three pose streams, one owner

The vehicle estimates its own pose the way a real AGV does, and there are
now **three** streams a reader could mistake for each other. The rule for
telling them apart:

| Stream | What it is | Who may read it |
|---|---|---|
| `/forklift/odom` | **Ground truth**, straight out of the simulator. 20 Hz | The measurement harness, and nothing else. **No estimator, ever** |
| `/forklift/odom_wheel` | **One sensor's opinion.** Tricycle dead reckoning from this vehicle's own joint states, with its encoder and calibration errors. 50 Hz. Publishes **no transform** | The EKF, as a measurement — exactly as the IMU is |
| `/forklift/odom_filtered` | **The estimate.** The EKF fusing the two above. 50 Hz | Anything that navigates. It alone publishes `forklift/odom → forklift/base_link` |

Two more topics sit beside them and neither is a pose: `/forklift/wheel_standstill`, the encoder verdict that the wheels are not turning, and `/forklift/imu_gated`, the gyro stream the filter is actually offered. Both are described in the topic table above.

`/forklift/odom`'s name still does not say it is ground truth. That is a
known defect this directory cannot fix alone — it is a cross-layer
contract — and the request to rename it `/forklift/odom_ground_truth`
stands in `docs/reports/m5-07b-odom-tf.md` and `m5-07c-realistic-odometry.md`.

**Phase 1 is over.** Between briefs m5-07b and m5-07c the transform was
the simulator's ground truth, bridged onto `/tf` as a scaffold because
nothing on the vehicle could produce a motion estimate and SLAM cannot
start without one. `ground_truth_tf` now defaults to **`false`**, the
bridge node does not run, and `ekf:=true ground_truth_tf:=true` is a
launch-time **refusal**, not a warning.

**Why that mattered.** With ground-truth odometry the degenerate aisle
stretches of `sim/worlds/WAREHOUSE_LANDMARKS.md` cannot bite, AMCL has
nothing to correct, and any "error against ground truth" figure is
circular — an estimator scored against its own input cannot be wrong.

**What the estimate is made of:**

| Source | Contributes | Error model |
|---|---|---|
| `scripts/wheel_odometry.py` | `vx`, `vy`, `vyaw` | 4096-count drive encoder, 4096-count steer encoder, a **one-count** steer zero offset, a 0.5 % rolling-radius calibration error. **No slip term** — the physics engine already produces slip |
| the IMU, via `/forklift/imu_gated` | `vyaw` only, **and only while the wheels are turning** | Bosch BMI088 datasheet: 0.1 °/s rms white noise, 0.15 °/s bias from the TCO over a stated 10 K. The bias is not in the message covariance and is not estimated on board — it integrates into heading exactly as an uncompensated MEMS gyro's does, which is the drift gate M5 exists to correct |

**One interval is treated differently, and only one.** While both encoder counts hold, `scripts/imu_gate.py` stops offering the gyro's yaw rate to the filter, because in that interval the vehicle knows independently that the rate is zero to within 0.0101° — a tricycle cannot rotate without its drive wheel travelling. That is a zero angular rate update, and it is the reason a map's frame no longer depends on how long the stack idled before driving. **It changes nothing while the vehicle moves**: no covariance, no process noise, no datasheet number, and no bias estimate carried out of the stop. `EVIDENCE_ODOMETRY.md` §12 measures both halves of that claim.

**Neither the pose nor the orientation is fused, and each refusal has its
own reason.** A dead-reckoned *pose* has unbounded error, so fusing it
would hand the filter the integrator's drift as a measurement. The IMU's
*orientation* is worse than useless: gz derives it from the link's pose in
the simulator, so it is ground truth wearing a sensor's name, and a real
strapdown IMU with no magnetometer has no absolute heading at all. It is
refused twice — `<enable_orientation>false</>` in `model.sdf` and all
three orientation flags false in `ekf.yaml`.

**The orientation trap, for anyone who adds an IMU consumer later.**
Measured on the bridged message: the quaternion arrives as `(0,0,0,0)`,
which is not a rotation, and `orientation_covariance[0]` arrives as `0.0`
— whereas the ROS convention for "no orientation in this message" is
`-1`, and `0` means *known exactly*. A consumer following the convention
would read an invalid quaternion as a perfect heading.
`EVIDENCE_ODOMETRY.md` §3.3.

**Fusing the IMU made heading worse, and that is reported rather than
tuned away.** 8.84° for the wheel odometry alone against 17.18° for the
EKF, because the filter tracks the gyro — the message covariance carries
the sensor's white noise and not its bias, the IMU is corrected at twice
the wheel odometry's rate, and `ekf.yaml` sets no process noise on
purpose. `bias × duration` predicts 17.89° and 17.18° was measured.
The fix is a weighting change or an on-board bias estimate; both are
tuning, and the tuning argument belongs to the SLAM brief.

**Still not published here:** `map → odom`. That is a localisation
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

## Running it as a vehicle image, which is what a second forklift would be

**Since ADR 0016 Phase 1 there are two sides to a run**, and the split is the
point: adding a forklift is adding a machine, not adding processes to a shared
graph.

| Side | What it is | Where it runs |
|---|---|---|
| **sim side** | Gazebo and the world. **No ROS process at all**, so it joins no DDS domain | one `GZ_PARTITION`, shared — one world is one warehouse floor |
| **vehicle image** | everything the vehicle's own computer runs, listed in the table above | **its own `ROS_DOMAIN_ID`**, allocated in `vehicles/allocation.yaml` |

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=myrun          # the SIMULATOR's boundary. Shared.

# the sim side: the floor
gz sim -r -s sim/worlds/warehouse.sdf

# the vehicle: it sets ROS_DOMAIN_ID itself, from the allocation table
python3 agv/forklift/scripts/vehicle_image.py --vehicle F001
```

Three things follow from the domain and they are not optional:

- **Every hand-run tool has to pick a domain.** `ros2 topic echo` against F001
  needs `ROS_DOMAIN_ID=51`; a session that forgets sees an **empty graph** and
  may read it as a dead stack. The number is read from
  `vehicles/allocation.yaml`, never remembered.
- **`GZ_PARTITION` and `ROS_DOMAIN_ID` are different boundaries.** gz transport
  is not DDS, so the domain does not isolate the simulator and the partition
  does not isolate the ROS graph. Set both.
- **The wall is checkable, and it is checked rather than claimed.**
  `EVIDENCE_VEHICLE_IMAGE.md` §3 runs `ros2 topic list` from three other
  domains and finds no `/forklift` topic in any of them.

`launch/vehicle.launch.py` and the `warehouse_bringup` recipes below are
unchanged and still run; the vehicle image includes the first of them rather
than restating its bridge table.

## Running it

Rendering on this machine is software rasterisation, so the server runs
headless and the ray budget is chosen against that: 275 + 275 + 360 = 910 rays
per 100 ms across three sensors, where there used to be 181 on one. **The
real-time cost of that has not been measured**, and no sample count or update
rate in `model.sdf` goes up until someone measures what it buys and writes the
figure down. `<visualize>true</visualize>` is set on all three, which is
necessary but not sufficient to draw the rays: the world also needs a
`VisualizeLidar` GUI plugin, and that belongs to `sim/`. **And the topic to
select in that plugin is one of the three `/forklift/gz/viz/*` streams, not a
measurement channel**: on this Gazebo build the `world_pose` field the plugin
anchors its drawing to is the sensor's static SDF pose — identity here, since
`model.sdf` mounts every scanner via its link — so a fan drawn from a
measurement channel stands at the world origin whatever the vehicle does.
`scripts/scan_viz_repeater.cc` (launch argument `lidar_viz`, on whenever
`gui` is) republishes each scan with a live anchor and nothing else changed;
`EVIDENCE_SENSOR_COVERAGE.md` section 16 is the measurement. Isolate both
transports whenever another simulation may be running: `ROS_DOMAIN_ID` does not
isolate Gazebo, `GZ_PARTITION` does.

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=myrun ROS_DOMAIN_ID=61

ros2 launch agv/forklift/launch/vehicle.launch.py world:=/path/to/world.sdf
```

Useful arguments: `world`, `world_name`, `name`, `x`, `y`, `z`, `yaw`,
`gui`, `server` (set false to spawn into a server someone else started),
`nodes`, `tf` (the sensor transforms, separate from `nodes` because SLAM
needs them when the two process nodes are off), `wheel_odom` (the
dead reckoning, separate from `ekf` so it can be verified on its own),
`ekf` (**default `true`**, the sole publisher of `odom → base_link`),
`ground_truth_tf` (**default `false` since the EKF took that edge over**;
`ekf:=true ground_truth_tf:=true` is refused at launch — see "Three pose
streams, one owner"), `imu_gate` (**default `true`**, the zero angular
rate update; setting it false remaps the filter back onto the raw IMU and
reproduces the m5-07c configuration exactly rather than leaving the
filter without an IMU, and `imu_gate:=true wheel_odom:=false` is refused
at launch), `lidar_viz` (**default = the value of `gui`**, the
`/forklift/gz/viz/*` anchor-repaired scan streams the `VisualizeLidar`
plugin should be pointed at — see the scripts table entry), and `seed`
(**default empty**, a `gz sim --seed` value that fixes the sign and
magnitude every sensor bias is drawn with — a measurement facility, so
that a before-and-after compares two runs of one vehicle rather than two
draws; no node reads it).

Checking the vehicle rather than trusting it. The first two need no
simulator and no ROS; the third needs a running graph, and the fourth
starts `obstacle_zone` itself:

```bash
/usr/bin/python3 agv/forklift/scripts/sensor_tf.py --print
/usr/bin/python3 agv/forklift/scripts/check_sensor_frames.py
/usr/bin/python3 agv/forklift/scripts/check_sensor_frames.py --live
ROS_DOMAIN_ID=79 /usr/bin/python3 agv/forklift/scripts/obstacle_matrix.py

/usr/bin/python3 agv/forklift/scripts/check_odom_tf.py
/usr/bin/python3 agv/forklift/scripts/check_odom_tf.py --live --drive

/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase static
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --print-world > /tmp/flat.sdf
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase imu
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase wheel
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase fusion
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase idle --idle 60
```

`check_odom_tf.py --drive` **moves the vehicle** — three straight and
turning legs at 0.5 m/s, then a stop — because a motion transform can
only be checked against motion. Give it clear floor: the arena run in
`EVIDENCE_ODOM_TF.md` spawns at `x:=-6.0 y:=-6.0`, where the arc meets no
obstacle. Its `--live` mode needs the retired configuration,
`ekf:=false ground_truth_tf:=true`, because it checks the ground-truth
transform specifically.

`check_odometry.py`'s four live phases each need the stack up; the
driven ones **move the vehicle 106 m** through two sustained turns and
want the flat world `--print-world` emits, not the arena. `--phase
static` needs neither ROS nor a simulator. `--phase idle` commands the
vehicle to rest and asks whether the fused heading holds; it **reads no
ground truth at all**, because the question is whether a number moved
while nothing happened and the vehicle's own encoders are what establish
that nothing did. Both driven phases and the idle phase need
`nodes:=true`, the default: `forklift_io.py` is what turns a speed
command into the model's raw input, and without it the profile commands
motion that never happens. The phases are separate on
purpose: the IMU is verified alone, then the wheel odometry alone against
a known motion, and only then the fusion. `EVIDENCE_ODOMETRY.md` §10 is
the full recipe.

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

**Driving it under the envelope gate, which is what autonomous mode now
means.** With `navigation.launch.py` up, the vehicle will not move until
something publishes an envelope: no envelope is a **stale** envelope and
the gate holds zero, which is the intended failure direction and not a
broken stack. At M5 no PLC is connected, so the envelope comes from the
double:

```bash
python3 agv/forklift/scripts/envelope_run.py run \
    --scenario supervise --csv /tmp/run.csv --drop-at 12.0 --duration 45.0

# the gate's arithmetic, with no ROS and no simulator
python3 agv/forklift/scripts/envelope_gate.py --self-check
```

`EVIDENCE_ENVELOPE.md` §12 is the full recipe, including the two-run
open-loop / closed-loop comparison, which needs
`launch/envelope.launch.py` rather than the navigation stack.

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
