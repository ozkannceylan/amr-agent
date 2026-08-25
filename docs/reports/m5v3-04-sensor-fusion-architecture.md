# m5v3-04 — Multi-sensor fusion architecture for the indoor forklift (Jazzy / Harmonic), 2025/26 SOTA

Research record, 2026-08-25, produced by a web-research agent for the
m5-ver3 track. The architecture in §0 is the agent's recommendation; the
judgement calls at the end are for the orchestrator/owner to rule on.

## 0. Recommended architecture (sensor → node → topic → consumer)

```
SENSOR (sim: gz plugin)              NODE                              TOPIC                          CONSUMER
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
wheel encoders (existing)      →  base driver                  → /odom (nav_msgs/Odometry)      → EKF-local
IMU MEMS (existing)            →  imu plugin/bridge            → /imu/data (sensor_msgs/Imu)    → EKF-local, KISS-ICP
2D nav lidar 360@10Hz (exist.) →  gz lidar → ros_gz_bridge     → /scan (LaserScan)              → AMCL, obstacle layer, rf2o
3D lidar NEW (gz gpu_lidar)    →  ros_gz_bridge                → /points (PointCloud2)          → KISS-ICP, STVL
  └─ KISS-ICP                  →  kiss_icp_node                → /kiss/odometry                 → EKF-local (twist only)
RGB-D NEW (gz rgbd_camera)     →  ros_gz_bridge/image_bridge   → /cam/color, /cam/depth, /cam/points → STVL, seg, docking
  └─ optional VO               →  rtabmap_odom | cuVSLAM       → /vo/odometry                   → EKF-local (LOW priority)
3x safety scanners (existing)  →  ros_gz_bridge                → /scan_safety_{f,l,r}           → nav2_collision_monitor (E-stop, NOT costmap)

FUSION LAYER 1 (continuous, odom frame, 30–50 Hz):
  ekf_filter_node_odom (robot_localization) : wheel /odom(vx,vyaw) + IMU(wz,ax) + lidar-odom(vx,vy,vyaw)
    → /odometry/filtered  +  TF odom→base_link                → Nav2 controller, AMCL motion model, MPPI

FUSION LAYER 2 (absolute, map frame, 5–10 Hz):
  amcl (/scan + map)  → /amcl_pose (PoseWithCovarianceStamped) ┐
  ekf_filter_node_map (robot_localization)  ────────────────────┴→ TF map→odom, /odometry/filtered_map → Nav2 planner
     (inputs: /odometry/filtered + /amcl_pose as absolute pose)

PERCEPTION LAYER:
  STVL (3D lidar /points + RGB-D /cam/points)   → local+global costmap → Nav2 planner/controller
  obstacle_layer (/scan, 2D nav lidar)          → costmap (redundant 2D floor plane)
  semantic_segmentation_layer (RGB-D + mask)    → costmap (people/vehicle class costs)
  collision_monitor (3x safety scans, raw)      → /cmd_vel_smoothed gate (slowdown/stop polygons)
  opennav_docking + SimpleNonChargingDock       → pallet approach using RGB-D/AprilTag detection
```

**Rationale for the shape:** the two-EKF pattern (continuous `odom` EKF +
absolute `map` EKF) is the robot_localization canonical layout and keeps
Nav2's controller on a smooth, jump-free frame while absolute corrections land
only on `map→odom`. Safety scanners deliberately bypass the costmap and go to
Collision Monitor — mirroring real forklift architecture (safety-rated channel
separate from navigation channel), and this project's own PLC-first doctrine.

## 1. Odometry-layer fusion — ranked

| # | Option | Jazzy | Verdict |
|---|---|---|---|
| 1 | **robot_localization EKF** (keep + extend) | ✅ 3.8.3, 2025-08-29, maintained by Tom Moore **and Steve Macenski** | Primary. Already in repo (`agv/forklift/ekf.yaml`); adding lidar-odom is a YAML change, not new code. Not abandoned, contrary to vendor-blog claims. |
| 2 | **fuse** (Locus, factor graph) | ✅ Jazzy 1.1.6 (2026-08-19); Kilted/Rolling 1.3.4 | Strong second and the best *narrative* for a fusion project: true factor graph, handles delayed/out-of-order measurements by construction. **Critically: `fuse_models` is 2D-only** — `Unicycle2D` motion model + `Odometry2D`/`Pose2D`/`Twist2D`/`Imu2D`/`Acceleration2D` sensor models. A planar forklift is exactly its design point. Everything enters as a generic pose/twist constraint, so KISS-ICP and AMCL both plug in. |
| 3 | **fusioncore_ros** (23-state UKF) | ✅ Jazzy+Humble 0.3.7, 2026-08-21 | Experimental only. Single maintainer, arXiv preprint 2605.25239, benchmarked on NCLT (outdoor RTK-GPS). Headline features (ECEF GPS, RTK gating) irrelevant indoors. A third comparison arm at most; never the production filter. |

**Recommendation:** ship robot_localization as the working filter, add
**fuse as a parallel branch** for a documented A/B — that alone makes the
project legibly a "sensor fusion" project rather than a Nav2 integration.

## 2. Lidar odometry as a fusion input — ranked

| # | Option | Jazzy | Notes |
|---|---|---|---|
| 1 | **KISS-ICP** | ⚠️ source build. v1.3.0 (2024-04-26); PR #481 "replace iron with jazzy and kilted". No apt binary. | Best if a 3D lidar is added. Publishes `/kiss/odometry`. Needs a dense PointCloud2 — 360 samples from the 2D nav lidar is too thin; pair with the new 3D lidar. |
| 2 | **rf2o_laser_odometry** | ❌ not on the build farm for Jazzy. Source forks: MAPIRlab `ros2` branch, linuxsen/rf2o_laser_odometry_ros2, Adlink-ROS. | Cheapest win: **0.9 ms/scan on one CPU core** (ICRA 2016). Works directly on the existing 2D `/scan`. Feed **twist only** (vx, vy, vyaw) into the EKF; never its integrated pose. |
| 3 | `laser_scan_matcher` / `laser_odometry` | ❌ no Jazzy release at all | Skip. |

**Benefit for a low-slip indoor vehicle — be honest:** wheel+IMU on a low-slip
warehouse floor is already good, so lidar odometry buys **little in
steady-state straight driving**. It buys a lot in three specific places:
(a) forklift front-steer geometry gives systematic heading error under tight
turns, (b) load pickup/dropoff changes effective wheel radius and mass
distribution, (c) it is the only odometry source that survives a wheel-slip
event on a wet/oily floor. Frame the demo around those three, not around
average ATE.

## 3. Visual odometry / VIO — ranked (all LOW priority)

| Option | Jazzy | Compute | Verdict |
|---|---|---|---|
| **RTAB-Map odometry** (`rtabmap_odom`) | ✅ rtabmap_ros **0.23.7, Jazzy, 2026-06-21**, maintained (Mathieu Labbe) | Moderate CPU; RGB-D full-SLAM run reached **~3 GB RAM** in a comparative study | Only officially released option. Same package can do VO *and* localization, so one dependency covers §3 and §4. |
| **Isaac ROS cuVSLAM** (`isaac_ros_visual_slam`) | ✅ "all Isaac ROS packages designed and tested compatible with ROS 2 Jazzy"; latest **Isaac ROS 4.6.0, 2026-08-18** | GPU; needs NVIDIA GPU + container | Fits the WSL2/NVIDIA rig on paper. Risk: Isaac ROS containers on WSL2 are a known integration tax and it needs a *stereo* pair, not one RGB-D. |
| OpenVINS / VINS-Fusion | ⚠️ community Jazzy forks only (RikisuT/open_vins_ros2_jazzy, mzahana/VINS-Fusion-ROS2-jazzy) | 1 core each | Research-grade, drone-oriented, unmaintained forks. Skip. |

**Answer to "is VIO worth it indoors?" — No.** With good wheel odom + IMU +
a 2D/3D lidar, VIO adds drift-prone state and a full CPU core for a marginal
odometry gain, and warehouses are exactly the low-texture/repetitive-aisle
environment VIO handles worst. **Spend the camera on perception and pallet
detection, not on odometry.** Keep VIO as an optional, clearly-labelled
experiment arm.

## 4. Localization layer — ranked

| # | Option | Jazzy | Verdict |
|---|---|---|---|
| 1 | **AMCL + EKF(map)** | ✅ Nav2 **1.3.12, 2026-08-18** | Keep as primary. Best-understood absolute accuracy in a static warehouse map; the map-frame EKF smooths particle jitter into a continuous pose. |
| 2 | **RTAB-Map localization mode (lidar + RGB-D)** | ✅ 0.23.7 | The genuine "fusion at the localization layer" option and the strongest demo differentiator: appearance-based loop closure fixes the two places AMCL fails. Cost: RAM (~GBs) and a heavier node. |
| 3 | **slam_toolbox localization mode** | ✅ | Elastic pose-graph localization; subscribes `/initialpose` so it is API-drop-in for AMCL. But community-reported as **less precise than AMCL, with occasional "snap" relocalizations** (slam_toolbox issue #285). Do not present it as an accuracy upgrade. |

Note: m5v3-01 ranks slam_toolbox localization above AMCL on the strength of a
published pose-graph-vs-AMCL comparison; this report ranks it below on the
strength of issue #285 field reports. **The two reports disagree — this is
exactly what the A/B measurement on the rig is for.** Both agree the switch is
launch-arg cheap and both must be scored against the same instrument floor.

**What actually improves absolute accuracy in a warehouse (cited AMCL failure
modes):** long feature-poor aisles cause **laser degeneracy** (unobservable
along-aisle direction); **reflective/specular surfaces** (racking uprights,
shrink-wrap, polished floors) corrupt the beam model; dynamic scene change
breaks the static-map assumption. Fixes that work, in order: (1) add vertical
structure via a 3D lidar so scan matching sees racking geometry, not just a
floor slice; (2) add a visual/appearance channel (RTAB-Map, or the Frontiers
2025 approach of adding rectangular-landmark visual observations into AMCL's
observation model); (3) fiducials/reflectors at known poses for docking-grade
accuracy.

## 5. Perception-layer fusion — ranked

| # | Option | Jazzy | Notes |
|---|---|---|---|
| 1 | **STVL (spatio_temporal_voxel_layer)** | ✅ **2.5.5, 2025-04-15**, apt `ros-jazzy-spatio-temporal-voxel-layer`; dedicated `jazzy` branch | Best multi-sensor costmap fuser. OpenVDB sparse volumes; models RGB-D as cubical frustums and 3D lidar as hourglass FOV — fuses *heterogeneous* sensor geometries natively. Linear/exponential/persistent decay handles dynamic warehouse traffic. **README's own measurement: 6× 7 Hz dense RGB-D cameras ran move_base at 20–50% CPU vs 80–110% with the stock voxel layer (5th-gen i7).** |
| 2 | Nav2 `voxel_layer` | ✅ built-in | Fallback, zero extra dependency. Nav2 docs: "if you have enough compute, use the VoxelLayer for 3D data." Costs more CPU than STVL, no time decay. |
| 3 | `obstacle_layer` on `/scan` | ✅ built-in | Keep as the cheap redundant 2D channel — `data_type` accepts LaserScan **or** PointCloud2. |
| — | **nav2_collision_monitor** (1.3.11, Jazzy) | ✅ built-in | Not a costmap. Sensor-direct E-stop/slowdown polygons, "bypassing the costmap and trajectory planners"; accepts pointclouds with `min_height`/`max_height` 2D projection. Where the three safety scanners belong. |
| — | **Semantic** | ⚠️ external | `kiwicampus/semantic_segmentation_layer` — Nav2 costmap layer taking a segmentation mask + aligned pointcloud, one observation queue per class. Nav2 has official tutorials "Navigating with Semantic Segmentation" and "Lidar-Free, Vision-Based Navigation" (Isaac Perceptor). Nav2 also supports masking dynamic classes out of the costmap update and re-inserting them, avoiding smear artifacts. |
| — | **opennav_docking** | ✅ Jazzy added **non-charging dock plugin type + `simple_non_charging_dock`**, explicitly motivated by conveyors and **pallets**; approximate dock pose refined by a vision control loop | The highest-value camera use on a forklift, upstream-supported. |

## 6. Realistic 2026 automated-forklift sensor suite (mirror this in the sim model)

| Role | Real-world part | Pinned spec | Sim (Gz Harmonic) |
|---|---|---|---|
| Safety, 3× overlapping | SICK **microScan3 / nanoScan3** safety laser scanners (safeHDDM) | nanoScan3 built for compact AGV/AMR | keep existing 3 scanners |
| Nav 2D | 2D lidar, natural-feature nav | Toyota automated forklifts: LiDAR natural-features nav, ~0.5 in positioning tolerance | existing `/scan` |
| **Nav/perception 3D** | **Ouster OS0** — Balyo strategic agreement with Ouster, deploys **OS0** on its lift trucks | OS0: **90° vertical FOV**, up to 128 ch, up to 2.6 M pts/s, 50 m @80% / 15 m @10% refl.; 90° VFOV explicitly sold for "see entire shelving units in a warehouse" | `gpu_lidar`, e.g. 32×1024, 90° VFOV, 10–20 Hz |
| Budget 3D alt | **Livox Mid-360** | 360°×59° FOV, 10 cm min range, IP67, ~$480–750 street | `gpu_lidar` 360°×59° |
| **Safety 3D camera** | SICK **safeVisionary2** — first 3D ToF at PL c | 512×424 @ 30 fps, 68°×58° FOV (protective 68°×42°), 3D safety field ≤2 m (4 m w/ reference background), warning ≤7.3 m | `rgbd_camera` |
| **Pallet + obstacle RGB-D** | Intel RealSense **D455** (or D435i) | D455: 0.6–6 m, <2% Z-error @4 m, 95 mm baseline, ≤90 fps. D435i: 0.3–3 m ideal, 87°×58°, 2% @2 m, global shutter + IMU | `rgbd_camera` on mast/fork carriage |
| Fleet reference | **Seegrid** lift trucks | "fusing data from 2D and 3D LiDAR sensors, stereo cameras, and a proprietary computer vision system"; **three safety-rated sensors creating overlapping 3D safety fields** | — |
| Ultrasonic | Listed in general AGV sensor surveys but **absent from every current forklift-AMR vendor description found** | — | **Skip** — not defensible for 2026 |

**Convergent industry pattern:** 2D safety scanners (safety-rated, PL d) + 3D
lidar (nav + payload/path volume) + stereo or RGB-D cameras (payload
detection, semantic) + IMU + wheel odometry. No ultrasonics, no GPS.

## 7. Compute notes

- **Measured/cited:** rf2o **0.9 ms/scan, 1 core**. STVL **20–50% of one
  process** with 6 dense RGB-D streams on a 5th-gen i7 (vs 80–110% for the
  voxel layer). RTAB-Map RGB-D **~3 GB RAM** in a comparative ROS 2 SLAM
  study.
- **Estimated (label as estimate, not measured):** per vehicle add ≈0.3 core
  for rf2o *or* ≈1 core for KISS-ICP on a 32-beam cloud; ≈0.2 core for a
  second robot_localization EKF; ≈0.5–1 core for STVL with 3D lidar + 1 RGB-D.
  **1 vehicle ≈ +2 cores over the current build.**
- **4 vehicles:** the naive sum (≈8 cores + 4 RGB-D render targets in Gazebo)
  is the wrong plan. The known-good pattern from the existing M6 rig (GPU
  exports + cold WSL required for four trucks) will not absorb 4×
  `rgbd_camera` + 4× `gpu_lidar` render passes. **Recommendation:
  heterogeneous fleet** — vehicle 1 carries the full fusion suite (3D lidar +
  RGB-D + all fusion nodes), vehicles 2–4 keep the current 2D sensor set.
  This is also *realistic* (mixed fleets are the norm) and keeps the fusion
  story on one showcase truck.
- **Gazebo caveat:** `rgbd_camera` and `gpu_lidar` bridge to
  `sensor_msgs/PointCloud2` via `ros_gz_bridge`, but there is an open
  gz-sensors issue (#545) where RGBD **PointCloud2 and depth/camera_info are
  visually misaligned in RViz despite sharing a frame_id** — budget debugging
  time before trusting camera pointclouds in the costmap.

## 8. Pinned sources

| Claim | URL | Version / date |
|---|---|---|
| fuse Jazzy/Kilted release | https://index.ros.org/p/fuse/ | Jazzy 1.1.6 (2026-08-19); Kilted/Rolling 1.3.4 (2026-08-17) |
| fuse_models is 2D-only | https://raw.githubusercontent.com/locusrobotics/fuse/jazzy/fuse_models/fuse_plugins.xml | jazzy branch, 11 plugins, all 2D |
| fuse_models distros | https://index.ros.org/p/fuse_models/ | jazzy 1.1.6 / kilted 1.3.4 |
| robot_localization maintained | https://index.ros.org/p/robot_localization/ | Jazzy 3.8.3 (2025-08-29), Moore + Macenski |
| fusioncore_ros | https://index.ros.org/p/fusioncore_ros/ · https://arxiv.org/html/2605.25239v1 | 0.3.7, 2026-08-21, 1 maintainer |
| FusionCore announcement | https://discourse.openrobotics.org/t/fusioncore-which-is-a-ros-2-jazzy-sensor-fusion-package-robot-localization-replacement/53502 | 2026 |
| KISS-ICP Jazzy support | https://github.com/PRBonn/kiss-icp/releases (v1.3.0, PR #481) | v1.3.0, 2024-04-26 |
| rf2o ROS 2 (source only) | https://github.com/MAPIRlab/rf2o_laser_odometry/tree/ros2 · https://github.com/linuxsen/rf2o_laser_odometry_ros2 | ros2 branch, no Jazzy binary |
| rf2o 0.9 ms cost | ICRA 2016, via repo README (mapir.isa.uma.es) | ICRA 2016 |
| laser_scan_matcher no Jazzy | https://index.ros.org/p/laser_scan_matcher/ | no Jazzy version |
| rtabmap_ros Jazzy | https://index.ros.org/p/rtabmap_ros/ | 0.23.7, 2026-06-21, M. Labbe |
| RTAB-Map lidar+visual reference | https://arxiv.org/abs/2403.06341 | 2024 |
| Isaac ROS Jazzy + cuVSLAM | https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_visual_slam/index.html · https://nvidia-isaac-ros.github.io/releases/index.html | Isaac ROS 4.6.0, 2026-08-18 |
| VINS-Fusion / OpenVINS Jazzy forks | https://github.com/mzahana/VINS-Fusion-ROS2-jazzy · https://github.com/RikisuT/open_vins_ros2_jazzy | community forks |
| slam_toolbox localization vs AMCL | https://github.com/SteveMacenski/slam_toolbox · issue #285 | issue #285 |
| AMCL + vision in corridors | https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1652251/full | 2025 |
| STVL Jazzy | https://index.ros.org/p/spatio_temporal_voxel_layer/ · https://github.com/SteveMacenski/spatio_temporal_voxel_layer/tree/jazzy | 2.5.5, 2025-04-15 |
| STVL CPU measurement + frustum/hourglass models | https://github.com/SteveMacenski/spatio_temporal_voxel_layer#readme | README |
| STVL Nav2 tutorial | https://docs.nav2.org/tutorials/docs/navigation2_with_stvl.html | Nav2 docs |
| Voxel layer params / guidance | https://docs.nav2.org/configuration/packages/costmap-plugins/voxel.html · https://docs.nav2.org/tuning/index.html | Nav2 docs |
| Collision Monitor | https://docs.ros.org/en/jazzy/p/nav2_collision_monitor/ · https://docs.nav2.org/configuration/packages/collision_monitor/configuring-collision-monitor-node.html | Jazzy 1.3.11 |
| Nav2 Jazzy version | https://index.ros.org/p/nav2_bringup/ | 1.3.12, 2026-08-18 |
| Docking: non-charging/pallet docks in Jazzy | https://docs.nav2.org/migration/Iron.html · https://github.com/open-navigation/opennav_docking · https://docs.nav2.org/tutorials/docs/using_docking.html | Iron→Jazzy migration |
| Semantic segmentation costmap layer | https://github.com/kiwicampus/semantic_segmentation_layer · https://docs.nav2.org/tutorials/docs/navigation2_with_semantic_segmentation.html | Nav2 docs |
| Vision-only nav (Isaac Perceptor) | https://docs.nav2.org/tutorials/docs/using_isaac_perceptor.html | Nav2 docs |
| Balyo → Ouster OS0 | https://www.businesswire.com/news/home/20210517005816/en/BALYO-Selects-Ousters-Digital-Lidar-for-Its-Robotic-Forklifts | 2021-05-17 |
| Ouster OS0 spec | https://data.ouster.io/downloads/datasheets/datasheet-rev7-v3p1-os0.pdf | rev7 v3.1 |
| Seegrid sensor fusion + 3 safety-rated sensors | https://seegrid.com/technology/ · https://seegrid.com/news/seegrid-elevates-amr-safety-with-advanced-layered-obstruction-detection/ | 2025 |
| SICK safeVisionary2 spec | https://www.sick.com/media/docs/2/12/112/product_information_safevisionary2_safety_camera_sensors_en_im0103112.pdf | im0103112 |
| SICK nanoScan3 / microScan3 | https://www.sick.com/media/docs/5/75/075/product_information_nanoscan3_en_im0087075.pdf | im0087075 |
| RealSense D455 / D435i | https://www.mouser.com/pdfDocs/D455ProductBriefv90.pdf · https://www.intel.com/content/www/us/en/products/sku/190004/intel-realsense-depth-camera-d435i/specifications.html | D455 brief v9.0 |
| Livox Mid-360 | https://www.livoxtech.com/mid-360 | Mid-360S 2025 |
| Toyota LiDAR natural-features nav | https://www.toyotaforklift.com/solutions/automation-solutions/transport-systems | 2025 |
| Gz Harmonic RGBD/gpu_lidar bridging + misalignment bug | https://docs.ros.org/en/jazzy/p/ros_gz_sim_demos/ · https://github.com/gazebosim/gz-sensors/issues/545 | ros_gz_sim_demos Jazzy 1.0.22 |

## 9. Judgement calls left to the owner/orchestrator

- (a) fuse being strictly 2D is a *feature* here, not a limitation — it
  matches the forklift exactly and gives a defensible factor-graph-vs-EKF
  comparison;
- (b) VIO should be declined explicitly with reasons, and the camera spent on
  STVL + semantic + `opennav_docking` pallet detection;
- (c) the 4-vehicle scale target should go heterogeneous rather than cloning
  the full sensor suite;
- (d) FusionCore is real and on the Jazzy build farm but is one person's 2026
  package benchmarked on outdoor GNSS data — cite it, optionally bench it, do
  not depend on it.
