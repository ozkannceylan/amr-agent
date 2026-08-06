# m5-50b — the sim bringup path, and the vehicle it made deaf

brief:               Task 4b, issued in-session against
                     `docs/reports/m5-50-brake-and-torque-off.md` request 2
status:              done
invariants_touched:  none. No ADR proposal.

## The defect, confirmed by running it

`sim/launch/forklift_bringup.launch.py` carried its **own** copy of the
`ros_gz_bridge` argument list. m5-50 moved `model.sdf`'s three joint
controllers off `/forklift/gz/{steer,traction,fork}_cmd` onto three actuator
terminals behind an STO contactor and updated
`agv/forklift/launch/vehicle.launch.py`; it could not update this file.

The pre-fix file was extracted from `HEAD`
(`md5 ccecded09614bec7a492f8712334bcb6`) and launched (case E below). It came
up **exactly like a healthy bringup**: `/clock`, `/forklift/scan`,
`/forklift/odom`, `/forklift/joint_states`, `/forklift/imu`, the front
scanner's measurement channel and the three command topics all present, the
bridge node advertised, **no error in any log** — and a traction command held
for 6 s moved the vehicle **0.0000 m**, with **0 messages** reaching the
plant boundary. There is no observation short of motion that separates that
from a working plant.

## What was done: the two lists were made one, not the copy corrected

`forklift_bringup.launch.py` no longer states a bridge table, a topic name or
a message type. It **includes `agv/forklift/launch/vehicle.launch.py`** and
adds what `sim/` actually owns — which world, where to stand in it, and which
of the vehicle's optional processes the run wants. That is the same argument
`warehouse_bringup.launch.py` already made when it stopped copying *this*
file's table, applied one layer down, and it is what makes the contactor
start: it is started by the file that declares it, not by a second copy that
has to remember.

`warehouse_bringup.launch.py` had the **same shape of defect one layer up**:
not a duplicate bridge list (it already wrapped this file) but a duplicate
**process list** — its own `ExecuteProcess`/`Node` copies of `sensor_tf.py`,
`wheel_odometry.py`, `imu_gate.py` and the EKF, kept in step with
`vehicle.launch.py` by hand. That copy is gone too; `estimator` is now passed
down. It also named five `agv/` paths and now names none.

**Scenario launches: no third copy exists.** `nav_scenario.launch.py` and
`warehouse_slam.launch.py` start no bridge. `cell_bringup.launch.py` is the
M3 cell — a disjoint topic set, no forklift topic in it, correctly its own.

## The TODO item, re-checked rather than inherited

`docs/TODO.md`'s sim/M5 entry said the arena bringup "still lacks the IMU
bridge, wheel odometry, EKF, `imu_gate.py` and the new `standstill` config
key". Checked, and it was **half stale**: the IMU bridge had been added at
m5-08b and was present. The other four were genuinely absent and are now
reachable with `estimator:=true`, which fans out to the four arguments
`vehicle.launch.py` declares — that file **refuses** the invalid partial
combinations, so this layer offers none. Case D below shows the arena bringup
carrying `/forklift/odom_wheel`, `/forklift/imu_gated`,
`/forklift/wheel_standstill`, `/forklift/odom_filtered`, `/tf` and
`/tf_static`, and still moving. The `standstill` key needed no launch change:
it is read from `config.yaml` by the scripts the argument now starts.

`estimator` defaults **false** on the arena path and **true** on the
warehouse path. M4 carries no navigation claim and ran through a closed gate
without a transform tree; turning one on by default would change what a
closed gate's launch starts.

## Evidence — five runs, and the positive control is the deliverable

Environment: **WSL2** (`5.15.167.4-microsoft-standard-WSL2`, 20 cores),
ROS 2 Jazzy, Gazebo Harmonic, rendering on `llvmpipe`. Repository checkout at
`/mnt/c`. Every run isolated on **both** transports: `GZ_PARTITION=m5-50b-<case>`,
`ROS_DOMAIN_ID=58`.

**Measured alone.** Before each run, `pgrep -af` over
`gz sim|parameter_bridge|ekf_node|sto_contactor|nav2|amcl|slam_toolbox`
returned **nothing** for cases A, A2, B, D, E and F; case C's only hit was its
own driver script. Load average was recorded at each start (0.05 to 2.31,
one-minute figure). Nine orphaned `agv/` processes from earlier briefs
(`sensor_tf.py`, `wheel_odometry.py`, `imu_gate.py`, started 10:52–14:37) were
found alive in `GZ_PARTITION` `m547a`/`m548meas`/`m5-50-sto` and
`ROS_DOMAIN_ID` 79/64/57. They were **left alone and recorded** rather than
swept: they are domain-isolated from every run here and are another session's
to end. Each case verified its own teardown and left **no survivor in its own
partition**.

Stimulus: `/forklift/gz/steer_cmd` 0.0 once, then `/forklift/gz/traction_cmd`
held at **3.3333 rad/s** by repeated publication for 6 s (never `--once`,
`docs/LESSONS.md` 2026-07-28), then a zero command, then a 2 s settle.
Distance is ground truth read back from `/forklift/odom` before and after —
**read back, never assumed**; no `set_pose` call was made anywhere in this
work.

| case | launch path | arguments | terminal msgs | **distance** |
|---|---|---|---|---|
| **A** | `warehouse_bringup` | defaults | 90 | **2.4192 m** |
| **A2** | `warehouse_bringup` | defaults (repeat) | 89 | **2.4200 m** |
| **B** | `forklift_bringup` | defaults | 90 | **2.4392 m** |
| **D** | `forklift_bringup` | `estimator:=true` | 88 | **2.4200 m** |
| **C** | `forklift_bringup` | `sto_contactor:=false` | **0** | **0.0000 m** |
| **E** | **pre-fix file from `HEAD`** | world/model passed | **0** | **0.0000 m** |

A and A2 are **the deliverable**: the vehicle brought up through the warehouse
path, commanded, and **moving, with the distance**. C and E are the
discriminating control in the same series — the identical stimulus, the same
clean-looking graph, and nothing at the plant. Two runs of the headline case
are quoted because one run is a draw and not a rate (`docs/LESSONS.md`
2026-08-05); they agree to 0.8 mm.

**Graph checks on the warehouse path** (case F, read from the running graph):

- `/tf` — **`Publisher count: 1`**, sample carries
  `forklift/odom -> forklift/base_link`. Deleting the duplicate estimator
  block removed the way this file could have grown a second one (invariant 10).
- `/forklift/odom_filtered` — `Publisher count: 1`.
- `/forklift/gz/actuator/traction_cmd` — `Publisher count: 1`
  (the contactor) and `Subscription count: 1` (the bridge).
- Node set: `forklift_bridge`, `sto_contactor`, `sensor_tf`,
  `wheel_odometry`, `imu_gate`, `forklift_ekf`.

## One more carried defect, found because the bridge node was renamed

`sim/scenarios/run_forklift_rehearsal.py` kills the arena bridge by matching
the node name **`forklift_arena_bridge`** to stop `/forklift/scan` at its
source. Under the wrapper the bridge is `vehicle.launch.py`'s and is named
`forklift_bridge`, so that stimulus would have matched nothing — and it fails
**silently**: it returns `False`, the scan keeps flowing, and the scenario
measures a stale-scan reaction that was never provoked. Both names are now
matched. `sto_contactor.py` was also added to that file's survivor sweep: a
contactor left running from a previous run is a second publisher of the three
actuator terminals.

## files_changed

- `sim/launch/forklift_bringup.launch.py` — rewritten as a wrapper of
  `agv/forklift/launch/vehicle.launch.py`; no bridge table, no topic name, no
  message type. New `estimator`, `sto_contactor`, `nodes` and `seed`
  arguments; `use_sim_time` kept and documented as inert; `ground_truth_tf`
  passed `false` explicitly. The include is `GroupAction(scoped=True)`.
- `sim/launch/warehouse_bringup.launch.py` — its duplicate estimator process
  list deleted and replaced by `estimator` passed down; five `agv/` paths
  removed; `seed` argument added; stale topic table corrected to the actuator
  terminals and the rear measurement channel; include scoped.
- `sim/scenarios/run_forklift_rehearsal.py` — bridge node name matched by
  either name; `sto_contactor.py` added to the survivor sweep.
- `sim/README.md` — the contents entry, the warehouse recipe's process list,
  and a new subsection recording the defect, the fix and the two measurements.

Nothing outside `sim/` and this report was written. `plc/` was not touched at
all — the two `plc/` entries in `git status` are the owner's concurrent TIA
session. `agv/`, `bridge/`, `hmi/` and `viz/` were read and not written. No
commit and no branch was made.

## Requests — work this layer cannot do

1. **repo root, and it is load-bearing for the showcase**: `stack.sh`'s
   `SURVIVOR_PATTERNS` does not contain `sto_contactor.py`. `stack.sh stop`
   therefore leaves a contactor running, and the next `stack.sh start` has two
   publishers on the three actuator terminals. One token added to the
   `SURVIVOR_PATTERNS` string on line 130. (`COMPONENT_TOKEN[sim]` still
   matches and needs nothing.)
2. **agv/, small and honest**: `vehicle.launch.py`'s `forklift_bridge` node
   takes no `use_sim_time` parameter, so `forklift_bringup.launch.py`'s
   `use_sim_time` argument is now declared-and-inert. It is documented as
   inert rather than quietly dropped, because existing recipes and
   `warehouse_bringup` pass it. Either `agv/` adds the parameter to that Node
   or a later brief retires the argument from both `sim/` files.
3. **agv/, carried from m5-50 and unchanged by this work**: the torque-off
   demand still has no carrier. Every run here published
   `/forklift/safety/torque_off_demand` from nothing at all — the topic exists
   because the contactor subscribes to it, and `bridge/` publishes no ROS
   topic for `Forklift/Safety/TorqueOffDemand`.

## open_questions

1. **Should `sim/launch/` gain its own evidence file?** The measurements above
   live in this report and in `sim/README.md`. Every other durable record in
   this layer is a `worlds/*_EVIDENCE.md`, and a bringup is not a world. It
   was not invented here rather than guess at the convention.
2. **The nine orphaned `agv/` processes** from briefs m5-47a/m5-48/m5-50 are
   still alive in WSL in three partitions. They cost little and are isolated,
   but they are the second session in a row to leave some, and no harness in
   the repository sweeps by anything other than its own partition.
3. **`warehouse_slam.launch.py`'s lifecycle emit-before-register race** is
   untouched and still open in `docs/TODO.md`; it is a different defect in the
   same directory and was deliberately not bundled.

next_suggested:      Add `sto_contactor.py` to `stack.sh`'s `SURVIVOR_PATTERNS` (request 1) before any rehearsal of the showcase, then close the `docs/TODO.md` sim/M5 arena-bringup item against case D.
