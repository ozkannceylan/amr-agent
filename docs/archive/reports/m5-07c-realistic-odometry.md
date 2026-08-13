# Report m5-07c — IMU, wheel odometry and the fused pose estimate

```
brief:               docs/briefs/m5-07c-realistic-odometry.md
status:              done
files_changed:       agv/forklift/model.sdf
                     agv/forklift/config.yaml
                     agv/forklift/ekf.yaml                    (new)
                     agv/forklift/launch/vehicle.launch.py
                     agv/forklift/scripts/wheel_odometry.py   (new)
                     agv/forklift/scripts/check_odometry.py   (new)
                     agv/forklift/scripts/check_sensor_frames.py
                     agv/forklift/README.md
                     agv/forklift/EVIDENCE_ODOMETRY.md        (new)
                     docs/reports/m5-07c-realistic-odometry.md
invariants_touched:  none. Invariant 10 is what shaped the answer: three
                     pose streams now exist and exactly one of them owns
                     odom -> base_link, enforced by a launch-time refusal
                     rather than by a default
open_questions:      eight, below. Two are dependency/toolchain requests to
                     sim/, one is a repeat of m5-07b's rename request with
                     more force, one is a gz-bridge defect, and the rest are
                     for the SLAM and localisation briefs
next_suggested:      the SLAM brief can start against a drifting estimate;
                     it inherits a 17 deg heading error and the tuning
                     argument that goes with it
```

## The number

**5.21 m of position error and −17.18° of heading, over a 106.49 m path
with 1449.8° of total turning, measured against ground truth.** The wheel
odometry alone, without the IMU, gives **5.24 m and +8.84°**.

That is the deliverable. It is larger than convenient and it was not
adjusted. Full run in `agv/forklift/EVIDENCE_ODOMETRY.md`.

## Where each noise number came from

Every value is derived from **Bosch Sensortec BMI088, BST-BMI088-DS000-19
rev 1.9, 01/2024**, tables 4 and 5, read 2026-07-31.
`check_odometry.py --phase static` recomputes each derivation from the
datasheet figure and fails if `model.sdf` disagrees, so provenance is a
check and not a claim.

| Parameter | Value | Derivation |
|---|---|---|
| gyro white noise | 0.001745 rad/s | The datasheet's own *Output Noise* row, `0.1 °/s rms at BW 47 Hz`. No arithmetic — the sensor is declared at that condition |
| gyro bias | 0.002618 rad/s | TCO `±0.015 °/s/K` × a stated **10 K**. **Not** the `±1 °/s` zero-rate offset, which is measured with offset cancellation off; every AGV estimates that at power-up |
| accel white noise | 0.01076 / 0.01278 m/s² | Noise density `160 µg/√Hz` (x, y) and `190` (z) × √47 Hz × g |
| accel bias | 0.01961 m/s² | TCO `<0.2 mg/K` × 10 K, same argument |
| drive encoder | 4096 counts/rev | 1024 ppr incremental in quadrature — 0.184 mm of tread per count |
| steer encoder | 4096 counts/rev | 12-bit single-turn absolute — 0.0879° |
| steer zero offset | 1.534e-3 rad | **One count.** No calibration resolves better, so the residual *is* one count. Deliberately the smallest defensible value, because this term dominates heading |
| rolling radius | 0.1206 m | A loaded PU tyre's rolling radius is 0.5 % under its free radius, so a vehicle calibrated on a free tyre **over**-reports distance — the sign that compounds with slip rather than cancelling it |
| **wheel slip** | **not modelled** | The physics engine already produces it |
| in-run bias walk | **not modelled** | The datasheet publishes no Allan-variance figure. Inventing one would be a fabricated datum, so it is a stated limitation and **every drift figure here is a lower bound** |

The one judgement call is the 10 K excursion, and it is stated as one.

## Findings

1. **The previous brief's slip figure was mostly geometry.** m5-07b read
   4.065 m of tread against a 3.989 m path as 0.076 m of slip. A steered
   drive wheel travels `1/cos δ` further than the axle it pushes, and
   `base_link` is offset 0.50 m from that axle again. Corrected for `cos δ`
   against the rear axle's own ground-truth path, the physics engine's real
   longitudinal slip over 105 m of this profile is **−0.04 %**, against a
   naive **+3.29 %**. So the modelled encoder and calibration errors, not
   the contact model, are what this vehicle drifts on.

2. **Fusing the IMU made heading worse, and the mechanism is measured.**
   `bias × duration` predicts −17.89°; the EKF's error is −17.18°. The
   filter tracks the gyro because gz fills the message covariance from the
   declared white noise only (`3.045e-06`), the IMU is corrected at 100 Hz
   against the wheel odometry's 50 Hz, and `ekf.yaml` sets no process noise
   on purpose. **gz draws the bias sign at random per run**: three fusion
   runs gave −17.18°, −16.41° and +19.85°. The fix is a covariance change
   or an on-board zero-velocity bias estimate; both are tuning, and the
   brief put tuning in the SLAM brief.

3. **A steer zero offset does not cancel between opposite turns — it
   accumulates.** `Δψ = s·sin(δ+off)/L` over-estimates a left turn and
   under-estimates a right one, both positive errors. A single-direction
   profile would have hidden this; the manoeuvre set has both signs for
   exactly that reason. Wheel-odometry heading error is reproducible to
   0.2 % across runs (8.836 / 8.890 / 8.836°) because none of its terms is
   stochastic, and `--phase static` predicts it to 0.01° with no simulator
   at all.

4. **The IMU system rides on the model, not the world.** Verified against
   `sim/worlds/forklift_arena.sdf`, which loads no IMU system: the sensor
   still publishes. **No world file needs editing to give this vehicle an
   IMU** — unlike the three scanners, which go silent without
   `gz-sim-sensors-system`.

5. **The gz→ROS IMU bridge has an orientation defect, and it fails
   unsafely.** With `<enable_orientation>false</>` the bridged
   `sensor_msgs/Imu` carries the quaternion `(0,0,0,0)` — not a rotation —
   with `orientation_covariance[0] = 0.0`. The ROS convention for "no
   orientation in this message" is `-1`; `0` means *known exactly*. A
   consumer following the convention reads an invalid quaternion as a
   perfect heading. Nothing here consumes it (`ekf.yaml` refuses all three
   orientation flags), but it is a trap for any later IMU consumer. Open
   question 4.

6. **Does the drift exercise the degenerate aisles? Yes, comfortably.**
   Pro rata, ~0.27 m of position error across the longest 5.5 m degenerate
   stretch of `sim/worlds/WAREHOUSE_LANDMARKS.md` §5 — quoted as an order
   of magnitude, since dead-reckoning error is superlinear in distance. The
   term that will actually bite is heading: **17° at the mouth of a 3.80 m
   aisle points the scan at the wrong wall**, and even the wheel-only 8.8°
   is far outside what a scan matcher recovers from as a prior. The brief's
   "too small to exercise them" case did not occur; the "large enough that
   SLAM struggles" case may have, and that is the condition real
   installations answer with reflectors.

## How the handover was made exclusive

`ground_truth_tf` now defaults to `false` and the interim bridge does not
run. A default is not a guarantee, so the launch **refuses**:

```
ekf:=true and ground_truth_tf:=true would both publish
forklift/odom -> forklift/base_link. Exactly one source owns that edge
(CLAUDE.md invariant 10). ...
```

and, for the other way to get a wrong transform:

```
ekf:=true with wheel_odom:=false starts a filter with no odometry source.
It would publish a transform built from the IMU yaw rate alone, which is a
heading with no position in it at all - and it would still be the only
publisher of that edge, so nothing downstream would notice.
```

Both refusals were run. On the live graph `ros2 topic info /tf --verbose`
reports `Publisher count: 1`, `forklift_ekf`. tf2 does not complain about
two publishers of one edge — the listener takes whichever arrived last —
so this had to be structural rather than documented.

`ground_truth_tf:=true ekf:=false` remains a deliberate configuration, for
reproducing m5-07b's evidence and nothing else. `check_odom_tf.py` still
passes 15/15 static checks against the new default.

## Open questions

1. **Dependency, and it needs no install — but it needs pinning.**
   `robot_localization` was **already present**:
   `dpkg-query -W ros-jazzy-robot-localization` →
   `3.8.3-1noble.20260615.152020`. It arrived as an **automatic**
   dependency of `ros-jazzy-nav2-waypoint-follower`, installed by m5-07
   with `navigation2`. `apt-mark showauto` lists it, so **`apt autoremove`
   would take it if Nav2 ever left**, and the vehicle would lose its state
   estimator silently. **Request to `sim/`**: add `ros-jazzy-robot-localization`
   to `install.sh`'s `ROS_PKGS` and record it in
   `sim/setup/CONTAINER_TOOLCHAIN.md` §3.2 as
   `| ros-jazzy-robot-localization | 3.8.3-1noble.20260615.152020 |`, with a
   note that it is currently auto-marked. That file is `sim/`'s, so it is
   requested here and not written. **Nothing was installed by this brief.**

2. **Request to `sim/`, repeated from m5-07b with more force:
   `/forklift/odom` is ground truth and its name does not say so.** The
   estimate now exists and is `/forklift/odom_filtered`, so the ambiguity is
   live rather than theoretical: `sim/scenarios/run_forklift_rehearsal.py`
   reads `/forklift/odom` and would be reading truth while believing it
   reads the vehicle. The rename wanted is
   `/forklift/odom` → `/forklift/odom_ground_truth` (gz side
   `/forklift/gz/odom_ground_truth`), touching
   `sim/launch/forklift_bringup.launch.py`,
   `sim/launch/warehouse_bringup.launch.py`,
   `sim/scenarios/run_forklift_rehearsal.py` and
   `agv/forklift/scripts/forklift_io.py`. One coordinated brief.

3. **Request to `sim/`, and it now blocks SLAM: a stack brought up through
   `sim/launch/forklift_bringup.launch.py` has no `odom → base_link` and no
   IMU.** m5-07b asked for a ground-truth TF bridge entry there; the answer
   has changed. That launch file needs the **IMU bridge entry**
   (`/forklift/gz/imu@sensor_msgs/msg/Imu[gz.msgs.IMU`, remapped to
   `/forklift/imu`), `scripts/wheel_odometry.py` and the
   `robot_localization` `ekf_node` with `agv/forklift/ekf.yaml` — not the
   ground-truth bridge. `agv/forklift/launch/vehicle.launch.py` is the
   working reference for all of it.

4. **To `sim/` or to whoever owns the bridge question: the IMU orientation
   defect of finding 5.** `ros_gz_bridge` should set
   `orientation_covariance[0] = -1` when the gz message carries no
   orientation. It does not, and the failure direction is "believed
   perfectly" rather than "ignored". Not fixable from `agv/`. Until then the
   rule for this project is: **no node reads `sensor_msgs/Imu.orientation`
   from a gz-bridged IMU**, and any that must, checks the quaternion norm.

5. **To the SLAM brief: the tuning argument, handed over deliberately.**
   Fusing the gyro costs heading (finding 2). Two answers exist — declare
   the bias in the covariance the filter is given
   (`σ = √(1.745e-3² + 2.618e-3²) = 3.146e-3` rad/s, which moves the
   weighting to the wheels), or estimate the bias on board with a
   zero-velocity update whenever the vehicle stops, which is what real
   installations do. The second is the better engineering and it is a new
   node, so it is a brief and not an edit.

6. **To the localisation brief: reflectors or fiducials are now a real
   question, not a hypothetical one.** `WAREHOUSE_LANDMARKS.md` §9.2 said
   the along-aisle degeneracy is "what a real installation solves with
   reflectors or fiducial markers". With 17° of heading error entering an
   aisle, that decision has a number behind it.

7. **Container evidence only.** The owner's WSL host has never run this
   configuration and has never had `robot_localization` checked on it.

8. **One floor, one speed, one steer angle, empty forks.** Every figure is
   at 1.0 m/s on `mu = 1.0` with the carriage down. Slip came out at
   −0.04 %; a heavier load, a faster manoeuvre or a lower friction
   coefficient would change that term and nothing here bounds by how much.

## Notes

- **Nothing outside `agv/` and this report was written.** `sim/`, `plc/`,
  `hmi/` and `bridge/` were read where needed and left alone; the items
  above are requests. `git status` shows five modified and four new files,
  all under `agv/forklift/`.
- **No dependency was added.** `robot_localization` was already installed
  (open question 1); nothing was `apt install`ed by this brief.
- **No tuning knob was touched.** `ekf.yaml` sets no
  `process_noise_covariance` and no `initial_estimate_covariance` — the two
  parameters a drift figure is most easily flattered with — and says so in
  the file.
- **No ground truth reaches an estimator.** `wheel_odometry.py` subscribes
  to `/forklift/joint_states` and nothing else; `ekf.yaml` names no
  ground-truth topic; the IMU emits no orientation. `check_odometry.py` is
  the only file here that reads ground truth, it steers nothing, and it says
  so in its own header.
- `wheel_odometry.py` publishes **no transform** and contains no transform
  broadcaster, which is the cheapest way to guarantee it cannot become a
  second publisher of the edge. `check_odom_tf.py`'s existing scan for
  moving-transform broadcasters still reports only `sensor_tf.py`'s static
  one.
- `check_sensor_frames.py` was extended by one guard: `read_sdf_sensors`
  read `<lidar>` aperture fields unconditionally and would have crashed on a
  non-lidar sensor with an `AttributeError` that says nothing. It now passes
  22/22 static and 33/33 live checks including the new `imu_link` frame.
  `sensor_tf.py` needed **no** edit — it enumerates sensors out of
  `model.sdf`, so the IMU frame arrived for free.
- Runs were isolated on **both** transports (`GZ_PARTITION` and
  `ROS_DOMAIN_ID`, unique per run), headless throughout, and every process
  was confirmed gone with `ps -eo pid,args` after each. **No RTF figure was
  taken and none is quoted** (LESSONS 2026-07-30).
- Nothing committed, nothing staged, no branch created.
