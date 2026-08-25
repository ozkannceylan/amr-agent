# m5v3-03 — Realism for the Jazzy + Harmonic forklift sim: sensors, physics, pallets, camera, performance

Research record, 2026-08-25, produced by a web-research agent for the
m5-ver3 track. XML fragments are ready-to-adapt SDF; every number traces to
the pinned sources in §7.

## 0. Headline finding (affects everything below)

**No respected reference sim ships sensor noise.** Verified by reading the
actual files: Clearpath `clearpath_common/jazzy` `hokuyo_ust.urdf.xacro`
(gpu_lidar, `update_rate 40`, ±135°, range 0.06–30, res 0.01) — **no
`<noise>` block**; `sick_lms1xx.urdf.xacro` (default 50 Hz) — none;
`microstrain_imu.urdf.xacro` — none; `intel_realsense.urdf.xacro`
(`rgbd_camera`, 30 Hz, 640×480, clip 0.3/100) — none. TurtleBot4 `jazzy`
`rplidar.urdf.xacro` (62 Hz, 640 samples, 0.164–12.0 m, res 0.01) — none.
→ Realism is *ours to add*; there is no upstream config to copy. Everything
below is derived from real datasheets + the SDF 1.11 `noise.sdf` schema that
ships with Harmonic.

## 1. Sensor noise — concrete SDF values

`noise.sdf` (SDF 1.11, sdformat14 = Harmonic) supports: `type` ∈ {none,
gaussian, gaussian_quantized}, `mean`, `stddev`, `bias_mean`, `bias_stddev`,
`dynamic_bias_stddev`, `dynamic_bias_correlation_time` (docs suggest ~3600 s
scale), `precision` (quantization step, gaussian_quantized only). **All
default 0.** IMU takes noise per-axis under `angular_velocity/{x,y,z}` and
`linear_acceleration/{x,y,z}`.

**Nav lidar — model on SICK TiM571** (270°, 15 Hz, 0.33°, 0.05–25 m,
systematic error ±60 mm, statistical error <20 mm @90% remission, <10 mm @10%
remission to 6 m):

```xml
<update_rate>15</update_rate>  <!-- NOT 40; see §5 -->
<horizontal><samples>811</samples><min_angle>-2.35619</min_angle><max_angle>2.35619</max_angle></horizontal>
<range><min>0.05</min><max>25.0</max><resolution>0.01</resolution></range>
<noise><type>gaussian_quantized</type><mean>0.0</mean><stddev>0.02</stddev>
       <bias_mean>0.0</bias_mean><bias_stddev>0.02</bias_stddev><precision>0.001</precision></noise>
```

`stddev 0.02` = the datasheet statistical error; `bias_stddev 0.02` makes
±60 mm ≈ 3σ systematic; `precision 0.001` = mm telegram quantization. If you
prefer Hokuyo UST-10LX (270°, 0.25°, 40 Hz, ±40 mm, 0.06–10 m):
`stddev 0.013`, `bias_stddev 0.013`, 1081 samples.

**Safety scanners — model on SICK nanoScan3** (275°, 0.17°, protective field
3 m, warning field 10 m, 70 ms response, 905 nm). Even though this project's
scanners are lidar-class sensors in the model, target the *safety scanner
envelope*: `update_rate 14` (≈70 ms), `max 3.0` (protective) / `10.0`
(warning), `stddev 0.02`.

**IMU — MEMS class, at 100 Hz.** Two defensible sets; pick one and note it in
the model:

- *PX4-derived* (noise density × √rate): gyro `stddev 0.0034` rad/s,
  `bias_stddev 0.0087`, `dynamic_bias_stddev 3.88e-5`,
  `dynamic_bias_correlation_time 1000`; accel `stddev 0.04` m/s²,
  `bias_stddev 0.196`, `dynamic_bias_stddev 0.006`,
  `dynamic_bias_correlation_time 300`.
- *ADIS-class / rotors lineage, quieter*: gyro `stddev 2e-4`,
  `bias_stddev 8e-7`; accel `stddev 1.7e-2`, `bias_stddev 1e-3`.

Also set `<enable_orientation>false</enable_orientation>` — a sim IMU that
emits perfect quaternions makes EKF tuning meaningless.

**Depth camera — known Gazebo limitation.** gz-sensors applies only
*additive* Gaussian noise to depth; gz-sensors issue #416 (open since
2024-03-09) calls this "completely useless" and proposes multiplicative +
stereo-disparity noise. Real D435 error is ~quadratic: <1% (2.5–5 mm) at 1 m,
~4 cm RMS at 2 m. **Recommendation:** set `stddev 0.008` in SDF as a floor,
and if pallet-pose fidelity matters, add a tiny ROS node applying
σ(z) ≈ 0.005–0.01·z² plus 0.5–1% dropout on the depth image. Do not claim
depth realism from the SDF alone.

**Odometry.** `AckermannSteering`/tricycle odom is *exact*
(`odom_publish_frequency` default 50 Hz). Realism recipe: (a) do **not**
bridge gz odom into `/odom`; (b) add the `WheelSlip` system
(`slip_compliance_lateral`, `slip_compliance_longitudinal`,
`wheel_normal_force`, `wheel_radius`) so the drive wheel actually slips;
(c) compute odom in ROS from joint states with encoder quantization (e.g.
1024 CPR → 6.1e-3 rad steps) + a 1–2% wheel-radius scale error and a small
steer-angle bias; (d) fuse with the IMU in `robot_localization`. That single
change is what makes SLAM/AMCL behave like the real thing.

## 2. Physics for a forklift

- Harmonic default engine is DART. `max_step_size 0.002` (not 0.001) buys ~2×
  RTF headroom with no visible loss for a 2 m/s vehicle; keep
  `real_time_factor 1.0`.
- **Inertia is the #1 instability cause.** A 2–3 t counterbalance truck with
  placeholder inertia tensors will jitter and creep. Derive `ixx/iyy/izz`
  from the real mass distribution (mast + counterweight are most of it).
- Friction: drive/steer wheel `mu = mu2 = 0.9` (polyurethane on concrete),
  castors `mu 0.05` so the tricycle doesn't fight itself. Load-dependent
  behaviour comes free once mass is right.
- **Fork lift:** prismatic joint on the carriage with realistic limits/effort,
  driven by a position controller. Do **not** try to lift the pallet by
  friction between tine and pallet.

## 3. Pallet pickup — VERDICT: feasible, via DetachableJoint

Harmonic's `DetachableJoint` system (gz-sim 8) does exactly this. SDF params:
`<parent_link>`, `<child_model>`, `<child_model_link>`, plus
detach/attach/state topics (`/model/<name>/detachable_joint/{detach,attach}`).
**Re-attach is supported** in Harmonic — but *not while parent and child are
in contact*, so the child must be repositioned first. Parent needs
`<self_collide>` enabled; no kinematic loops.

**Recommended pattern:** pallet is a separate model; each forklift carries its
own `DetachableJoint` with *custom per-vehicle topics* (required when several
plugins act on one model). A small ROS node gates `attach` on a geometric
predicate (fork tip inside pocket volume, yaw error < ~5°, height error <
~2 cm) rather than on contact physics. This gives repeatable pickup, keeps
RTF, and still exercises the whole perception→alignment→engage chain
honestly. Friction-only tine insertion at 4 vehicles is the classic RTF and
jitter killer — avoid.

## 4. Camera role — VERDICT: both, staged

Real vendors converged on *3D camera at the forks* + lidar for navigation:

- **Fox Robotics FoxBot Mk3** (ProMat 2025): cameras built into the **mast**
  identify pallet **pockets** and auto-adjust fork-tine width; lidar + cameras
  for obstacles.
- **Third Wave TWA Reach**: automotive-grade 3D lidar + vision, with
  **additional 3D cameras near the forks** specifically to locate the pallet.
- **Balyo**: Ouster 3D lidar for reflectorless geoguidance/SLAM + safety
  bubble; a **dedicated pallet camera** identifies pallet type and structural
  soundness before picking.

**Recommendation for this sim:**

1. **Markers first (AprilTag) for station/dock handover.** `apriltag_ros`
   3.3.0 released into Jazzy 2025-08-29. Gazebo tag models exist
   (`koide3/gazebo_apriltag`, Harmonic fork by `rickarmstrong`). Feed the tag
   pose into **`opennav_docking`** as the external detection pose
   (`use_external_detection_pose`, `external_detection_timeout`,
   `filter_coef`, `dock_direction`); `SimpleNonChargingDock` covers
   pallet-style, non-charging docking. Deterministic, demo-safe, and matches
   how station handover is actually commissioned.
2. **Learned detector second, for the pallet itself.** Train/fine-tune on
   **LOCO** (tum-fml/loco: 37,988 images, 5,593 annotated, 152,421
   annotations, classes pallet / small load carrier / stillage / forklift /
   pallet truck, COCO format, **CC0-1.0**) and/or reuse
   **NVIDIA-AI-IOT/sdg_pallet_model** (monocular RGB → per-side-face pallet
   boxes, trained purely on Omniverse Replicator synthetic data, TensorRT).
   Get 6-DoF by fitting the detected face plane against the sim depth cloud.
   Recent literature (ADAPT, arXiv 2503.14331; Springer "geometric cues from
   synthetic data"; MDPI/Wiley 2025 keypoint work at 95.1% detection / 94.2%
   keypoint @105.6 FPS) all follows this RGB-detect-then-depth-fit shape.

Do **not** make the demo depend on the learned model. Markers carry the demo;
the detector is the SOTA layer on top.

## 5. Performance — keeping 4 vehicles real-time

**The ROS bridge, not physics, is the bottleneck.** ros_gz issue #368
measured: ~90% RTF steady with sensor bridges *off*; **40–60% with lidar
bridges on**; **31–33% with uncapped sensor rate** — and the bridge only
delivered ~60% of the configured rate (47/35 Hz against a 62 Hz target).

Budget for 4 trucks:

- One `gz sim -s -r --headless-rendering` server (EGL; **OGRE2 only**),
  `sensors` system with `<render_engine>ogre2</render_engine>`.
- Nav lidar **15 Hz** (matches TiM571 anyway — free realism *and* free RTF).
  Safety scans 10–14 Hz. Pallet depth camera **320×240 @ 6–10 Hz**, and only
  subscribed during engagement — gz skips rendering when nothing subscribes.
- Bridge only what ROS consumes; **never bridge point clouds** — bridge depth
  image + camera_info and convert in ROS. Run `ros_gz_bridge` as composable
  nodes, one container per namespace.
- `max_step_size 0.002`, DART.
- Known accuracy caveat: gz-sim issue #2743 (open, 2025-01-29, Fortress
  **and** Harmonic, Humble/Jazzy) — `gpu_lidar` is measurably less accurate
  than the CPU ray sensor at shallow incidence. Relevant to racking legs and
  pallet faces seen obliquely; no fix, no workaround upstream.

**WSL2 specifics:** WSLg + GPU works on Garden/Harmonic after ogre-next fixes
(Open Robotics Discourse). Pin the dGPU with
`MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` (case-insensitive substring, per the
microsoft/wslg wiki). `LIBGL_ALWAYS_SOFTWARE=1` is the documented fallback for
the d3d12/mesa path (gz-rendering issue #852) — but it destroys GPU-lidar
throughput, so treat it as diagnosis-only, never as the 4-vehicle config.

## 6. Reference projects — what to take from each

| Project | Take |
|---|---|
| `aws-robotics/aws-robomaker-small-warehouse-world` (ros2 branch; Jazzy doc 1.0.5) | World + racking/pallet-jack/box assets; Nav2 demos assume it. Models also on Fuel under `OpenRobotics/models/aws_robomaker_warehouse_*` |
| `open-navigation/opennav_docking` + Nav2 docking tutorial | Station handover: dock plugins, `getRefinedPose` sensor refinement, `isDocked` stop condition, BT nodes. Non-charging dock = pallet station |
| `nav2_loopback_sim` (Jazzy 1.3.11) | Frictionless-plane sim for fleet-logic and behaviour tests without paying Gazebo's RTF — ideal for the 4-vehicle *dispatch* tests |
| Nav2 `cloned_tb3_simulation_launch.py` + `nav2_multirobot_param_all.yaml` (new in Jazzy) | The canonical multi-robot namespacing pattern; robots declared as `name={x,y,yaw}` on the command line |
| Nav2 Smac Hybrid-A* | Tricycle planner: set `minimum_turning_radius` to the true kinematic value; keep `analytic_expansion_max_length` ≥ 4–5× that or planning times spike |
| `koide3/gazebo_apriltag` (+ `rickarmstrong/gazebo_apriltag` harmonic branch) | Ready tag models/textures for station markers |
| `tum-fml/loco` | CC0 pallet/SLC/stillage dataset, COCO format |
| `NVIDIA-AI-IOT/sdg_pallet_model` | Pretrained monocular pallet-face detector + the synthetic-data recipe |
| MDPI *Sensors* 25(16):5206 (2025) — tricycle forklift in Gazebo | Closest published analogue: SLAM + AMCL + Nav + base/motion controller on a tricycle forklift |
| `Anastasios03git/autonomous-warehouse-amr` (Discourse, 2026-08-10) | Jazzy + Harmonic + Nav2 warehouse AMR: SmacPlanner2D + RPP + **Collision Monitor** + EKF + YAML missions. Community note: costmap replanning beats the Collision Monitor on gradual obstacles; the monitor earns its keep only on sudden close-range appearance inside the controller lookahead |
| `alitekes1/ros2-ackermann-vehicle-gz-sim-harmonic-nav2` | Ackermann + Harmonic + Nav2 + AMCL/SLAM wiring reference |

## 7. Pinned sources

| # | Source | URL | Version / date |
|---|---|---|---|
| 1 | SDF `noise.sdf` schema | https://raw.githubusercontent.com/gazebosim/sdformat/sdf14/sdf/1.11/noise.sdf | SDF 1.11 (Harmonic) |
| 2 | SDF `imu.sdf` schema | https://raw.githubusercontent.com/gazebosim/sdformat/sdf14/sdf/1.11/imu.sdf | SDF 1.11 |
| 3 | Clearpath sensor xacros | https://github.com/clearpathrobotics/clearpath_common/tree/jazzy/clearpath_sensors_description/urdf | jazzy branch |
| 4 | TurtleBot4 rplidar xacro | https://raw.githubusercontent.com/turtlebot/turtlebot4/jazzy/turtlebot4_description/urdf/sensors/rplidar.urdf.xacro | jazzy |
| 5 | SICK TiM571 datasheet | https://www.sick.com/media/pdf/4/44/444/dataSheet_TiM571-2050101_1075091_en.pdf | TiM571-2050101 |
| 6 | SICK nanoScan3 product info | https://www.sick.com/media/docs/5/75/075/product_information_nanoscan3_en_im0087075.pdf | nanoScan3 |
| 7 | Hokuyo UST-10LX spec | https://www.hokuyo-aut.jp/dl/UST-10LX_Specification.pdf | UST-10LX |
| 8 | PX4 gazebo IMU plugin params | https://github.com/PX4/PX4-SITL_gazebo-classic (include/gazebo_imu_plugin.h) | main |
| 9 | RealSense D435 depth accuracy | https://support.intelrealsense.com/hc/en-us/community/posts/360038458794 | Intel support |
| 10 | Depth-camera noise limitation | https://github.com/gazebosim/gz-sensors/issues/416 | open, 2024-03-09 |
| 11 | GPU lidar accuracy defect | https://github.com/gazebosim/gz-sim/issues/2743 | open, 2025-01-29 |
| 12 | DetachableJoint system | https://gazebosim.org/api/sim/8/detachablejoints.html | gz-sim 8 (Harmonic) |
| 13 | WheelSlip system | https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1WheelSlip.html | gz-sim 8 |
| 14 | AckermannSteering (odom 50 Hz) | https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1AckermannSteering.html | gz-sim 8 |
| 15 | Bridge RTF measurements | https://github.com/gazebosim/ros_gz/issues/368 | ros_gz_bridge 0.244.9 |
| 16 | Headless rendering (EGL, OGRE2 only) | https://gazebosim.org/api/sim/9/headless_rendering.html | gz-sim |
| 17 | WSLg GPU support in Harmonic | https://discourse.openrobotics.org/t/wslg-with-gpu-support-available-on-latest-version-of-gazebo-garden-and-harmonic/48128 | Open Robotics |
| 18 | d3d12/mesa test failures | https://github.com/gazebosim/gz-rendering/issues/852 | mesa 22.2.5 |
| 19 | WSLg GPU selection | https://github.com/microsoft/wslg/wiki/GPU-selection-in-WSLg | wiki |
| 20 | AWS small warehouse world | https://github.com/aws-robotics/aws-robomaker-small-warehouse-world/tree/ros2 · https://docs.ros.org/en/jazzy/p/aws_robomaker_small_warehouse_world/ | Jazzy 1.0.5 |
| 21 | opennav_docking / Nav2 docking tutorial | https://github.com/open-navigation/opennav_docking · https://docs.nav2.org/tutorials/docs/using_docking.html | Nav2 1.0.0 |
| 22 | nav2_loopback_sim | https://docs.ros.org/en/jazzy/p/nav2_loopback_sim/ | Jazzy 1.3.11 |
| 23 | Nav2 Iron→Jazzy migration (cloned_tb3 multirobot) | https://docs.nav2.org/migration/Iron.html | Jazzy |
| 24 | Smac Hybrid-A* config | https://docs.nav2.org/configuration/packages/smac/configuring-smac-hybrid.html | Nav2 1.0.0 |
| 25 | apriltag_ros Jazzy release 3.3.0 | https://github.com/ros2-gbp/apriltag_ros-release · https://index.ros.org/p/apriltag_ros/ | 3.3.0-1, 2025-08-29 |
| 26 | Gazebo AprilTag models | https://github.com/koide3/gazebo_apriltag (+ rickarmstrong fork, harmonic) | — |
| 27 | LOCO dataset | https://github.com/tum-fml/loco | CC0-1.0, ICMLA 2020 |
| 28 | NVIDIA SDG pallet model | https://github.com/NVIDIA-AI-IOT/sdg_pallet_model | master |
| 29 | ADAPT autonomous forklift | https://arxiv.org/abs/2503.14331 | 2025-03 |
| 30 | Tricycle forklift Gazebo/ROS | https://www.mdpi.com/1424-8220/25/16/5206 | Sensors 25(16):5206, 2025 |
| 31 | Fox Robotics FoxBot Mk3 | https://foxrobotics.com/blog/foxbot-mk3-takes-on-more-warehouse-work-with-new-capabilities | ProMat 2025-03-12 |
| 32 | Third Wave TWA Reach | https://www.therobotreport.com/third-wave-automation-picks-series-c-funding-automated-forklifts/ | — |
| 33 | Balyo geoguidance + Ouster 3D lidar | https://www.balyo.com/hubfs/Press%20Release/EN/balyo_pr_ouster_EN.pdf · https://www.balyo.com/agv-technology/navigation-management | 2021-05 |
| 34 | Warehouse AMR (Jazzy+Harmonic+Nav2) | https://discourse.openrobotics.org/t/-/57292 · https://github.com/Anastasios03git/autonomous-warehouse-amr | 2026-08-10 |
