# m5v3-01 — Indoor AMR/forklift mapping + localization, 2025/26 SOTA vs. this rig

Research record, 2026-08-25, produced by a web-research agent for the
m5-ver3 track (sensor-fusion autonomy rebuild). Confidence flags are the
agent's own and are preserved; re-verify flagged rows before quoting them
in an ADR or evidence file.

## Headline

Vendor practice for indoor forklifts in 2026 is still **2D lidar scan-matching
against natural contours**, not 3D lidar SLAM. 3D lidar and cameras are used
for *perception* (obstacle/pallet/load), not as the primary pose source. The
archived build (slam_toolbox map + nav2_amcl runtime, 0.124 m rms) is already
on the right axis; the realism upgrade is to swap the runtime estimator to a
scan-matching pose-graph localizer, not to add a 3D lidar.

---

## (a) Map building — ranked

| # | Choice | Justification | WSL2 compute |
|---|---|---|---|
| 1 | **slam_toolbox offline (sync) from a recorded bag**, serialize `.posegraph`+`.data` **and** export `.pgm` | Nav2's officially supported SLAM library [S1]; the only 2025 head-to-head ROS 2 study rates it best for both map quality and trajectory precision [S2]. Sync + offline replay is deterministic — repeatable evidence, no dropped scans. | Zero cost at runtime (one-shot, one truck, no fleet running). README: 5x+ real-time to ~30k sq ft, 3x at 60k sq ft [S3]. |
| 2 | slam_toolbox **async** live-drive mapping | Same package, shows a "walk the truck through the plant" commissioning story that mirrors vendor onboarding (Toyota/Balyo/Seegrid all map by driving the facility once [S12][S14][S16]). | Async drops scans under load — with 1 truck fine, do not run alongside the 4-truck fleet. |
| 3 | **MOLA `mola_mapper_2d`** (2D pose-graph SLAM, ICP + loop closure) | Genuine 2026-current alternative, properly bloom-released on Jazzy [S8][S9]; useful as an independent second map to cross-check slam_toolbox. | Similar order to slam_toolbox. **Flag: GPL-3, commercial licence on request** [S9] — fine for a portfolio sim, not for shipped product. |
| — | Cartographer | Historically the other 2D option; ROS 2 Jazzy maintenance status **not verified in this pass** — do not adopt without checking. | — |
| ✗ | RTAB-Map for the 2D map | Higher compute and lower robustness to sensor disturbance than slam_toolbox in the 2025 comparison; diverged in 1 of 3 environments [S2]. | — |

**Do not use slam_toolbox lifelong mode as the mapping mode.** README calls the
node-removal variant "**highly** experimental" and recommends running the
non-full lifelong mode **in the cloud** because of its computational burden
[S3]. Legitimate use of lifelong is *multi-session*: re-map one aisle, merge,
freeze — then localize against the frozen graph [S3]. That is also what real
vendors do (re-map a zone after a rack move), so a "remap one zone and merge"
demo is realistic and cheap.

---

## (b) Runtime localization — ranked

| # | Choice | Justification | WSL2 compute |
|---|---|---|---|
| 1 | **slam_toolbox localization mode** (elastic pose-graph, rolling scan window) | Algorithmic twin of what vendors ship: BlueBotics ANT and SICK LiDAR-LOC both localize by matching the live scan to permanent environment contours, ±1 cm and ±30 mm respectively [S10][S11]. Pose-graph localization also beats AMCL in the only clean published comparison: AMCL translational RMSE 8.5 cm (empty) → **33.7 cm** (real, cluttered) vs **7.2 cm** for pose-graph in the same real environment [S4]. Exposes `/initialpose`, so the Nav2 API is unchanged [S3]. | Higher steady-state CPU than AMCL (continuous scan matching + graph query). Keep scan ≤10 Hz and ≤720 beams; budget per truck, ×4. |
| 2 | **nav2_amcl** — keep as a pinned, launch-arg-selectable fallback | Already measured on this rig at 0.124 m absolute rms against a 0.141 m floor; Nav2's default and slam_toolbox's own author recommends it for "a good out-of-the-box experience" [S3][S1]. Cheapest option when 4 trucks + PLC + fleet manager are all live. | Cheapest. Cap `max_particles` (~500) and set `update_min_d`/`update_min_a` so the filter is not resampling every scan. |
| 3 | **MOLA `mola_relocalization` / MOLA-LO** | 2025 IJRR-published framework, released on Jazzy, supports localization in a prior map [S8][S9]. Worth a bake-off row, not a default. | Moderate; GPL-3 flag again. |
| ✗ | 3D LIO (FAST-LIO2 / DLIO / LIO-SAM) as the pose source | Not what this vehicle class ships. Compute and Jazzy availability both fail — see flags below. | — |
| ✗ | RTAB-Map localization mode as the primary | Highest compute of the four in the 2025 study, and convergence failure in one of three environments [S2]. | — |

**Known caveats to test on the rig for choice #1:** slam_toolbox has **no
global relocalization service** — it refines from the first scan near the
loaded pose, or you must publish `/initialpose`; near the map origin it can
self-init [S3]. Confirm it publishes `/map` from the deserialized graph so
Nav2's static layer is fed (README's "no more .pgm" claim implies yes [S3]) —
otherwise keep `map_server` alongside it. A kidnapped-robot / lost-truck
recovery behaviour is therefore a *you-must-build-it* item, and is the honest
place where AMCL is genuinely better.

**Recommended shape:** one launch argument `localization:=slam_toolbox|amcl`,
slam_toolbox as default for the 1–2 truck "realism" runs, AMCL for the 4-truck
scale run. Publish both rms numbers against the same instrument floor — that
comparison *is* the deliverable.

---

## (c) Camera's role in localization — ranked

| # | Choice | Justification | WSL2 compute |
|---|---|---|---|
| 1 | **Camera out of the localization loop; perception only** (pallet/fork-pocket detection, load present/absent, aisle obstacle classification) | Industry consensus. Seegrid, the most camera-forward vendor, still names **3D lidar SLAM** as the navigation core and uses stereo cameras for payload detection and environment change [S16]. Jungheinrich's new EAE 212a fuses cameras + laser scanners but the pose comes from the laser stack [S15]. Visual SLAM is lighting-sensitive and fails in featureless aisles; it supplements rather than replaces lidar in production AMRs [S17, low-quality secondary]. | One RGB or RGB-D sensor on **one** truck only; Gazebo camera rendering is GPU-bound and stacks badly with 4 trucks. |
| 2 | **RTAB-Map (2D lidar + RGB-D), localization mode, single truck, as a demonstrated option** | Actively released on Jazzy (0.23.7, 2026-06-21) [S7] and the standard answer for lidar+camera fusion; a 2025 MDPI *Actuators* paper uses exactly this for AMR real-time localization [S6]. Good as a "we evaluated fusion and here is why we didn't ship it" artefact. | Highest CPU + RAM of the candidates [S2]; do not run on more than one vehicle. |
| ✗ | **ORB-SLAM3 / VIO class in the loop** | Not production practice for industrial transport robots; no maintained ROS 2 Jazzy release. | — |

---

## 3D lidar in this sim — recommendation: **no** (or perception-only, one truck)

1. **Not what the vehicle class ships.** Toyota offers reflector / natural /
   dual navigation off the *same 2D laser scanner* [S12]. Jungheinrich's older
   ERC 213a is reflector or reflector+environment [S15]. BlueBotics ANT is 2D
   laser + odometry, ±1 cm [S10]. SICK sells both reflector triangulation
   (NAV350, ±4 mm [S13]) and contour LiDAR-LOC (±30 mm, 30 Hz [S11]). Where 3D
   lidar appears (Seegrid; Balyo reportedly selecting Ouster [S14, *fetch
   blocked — title only, treat as unconfirmed*]) it is fused *with* 2D and
   cameras, largely for volumetric obstacle and payload sensing.
2. **Gazebo Harmonic makes it expensive.** The open `ros_gz` bridging issue
   reports RTF falling from ~90% to **40–60%** and topics publishing at
   ~**60% of the configured rate** once gpu_lidar bridges are added [S5]. A
   16×1800 @10 Hz scanner is ~288k points/s per truck; ×4 trucks on a shared
   WSL2 CPU is not viable. The GSoC-2025 ray-traced `gz-wgpu-rt-lidar` plugin
   may change this but is not shippable today [S5b].
3. **Jazzy availability is the weakest link** — see flags.

---

## Does-not-work-on-ROS 2-Jazzy flags

- **FAST-LIO2** — upstream `hku-mars/FAST_LIO` is a ROS 1 package. ROS 2 exists
  only as community forks targeting **Humble** (Taeyoung96 / Lee-JaeWon /
  TechShare, all crediting Ericsii's `ros2` branch). **No Jazzy binary, no
  bloom release.** Reference compute: 100 Hz on a 1.8 GHz quad i7-8550U
  [S18][S19].
- **DLIO** — ROS 2 support exists only on the unreleased `feature/ros2` branch
  of `vectr-ucla/direct_lidar_inertial_odometry`. Not a released ROS 2 package;
  no Jazzy claim [S20].
- **LIO-SAM** — `ros2` branch targets **Humble**. Jazzy compatibility request
  (issue #549, opened 2025-07-08) is **still open with no maintainer answer**
  [S21].
- **KISS-ICP** — *does* work: ROS 2 only since v0.4.0, jazzy+kilted in CI
  (PR #481), latest tagged release v1.3.0. No IMU fusion by design (pure
  point-to-point ICP odometry); IMU/GNSS fusion is a downstream package
  (FusionCore, apt for jazzy/humble) [S22].
- **slam_toolbox lifelong mode** — runs on Jazzy but is self-described
  "**highly** experimental" for true node removal; author recommends cloud
  execution [S3].
- **MOLA / mp2p_icp** — released on Jazzy, but **GPL-3** [S8][S9].
- Gazebo Harmonic is the correct pairing for Jazzy, supported to **Sept 2028**
  [S23] — no version risk there.

---

## Pinned sources

| ID | Source | URL | Version / date |
|---|---|---|---|
| S1 | Nav2 docs, Mapping and Localization | https://docs.nav2.org/setup_guides/sensors/mapping_localization.html | Nav2 1.0.0 docs, fetched 2026-08-25 |
| S2 | Comparison of SLAM algorithms for autonomous navigation systems in ROS 2 | https://www.researchgate.net/publication/396652310 · doi 10.22541/au.175199254.49549720 | preprint, 2025 (PDF fetch blocked; findings from indexed abstract) |
| S3 | slam_toolbox README, `jazzy` branch | https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/README.md | jazzy branch, fetched 2026-08-25 |
| S3b | slam_toolbox releases | https://index.ros.org/p/slam_toolbox/ | jazzy **2.8.5**, tag 2026-04-29, bloom 2026-08-17; kilted 2.9.0; lyrical 2.10.0 |
| S4 | Vega Torres, Braun, Borrmann — Occupancy Grid Map to Pose Graph-based Map | https://arxiv.org/abs/2308.05443 | arXiv 2023-08-10. **RMSE figures from indexed text; PDF extraction failed — verify before quoting** |
| S5 | ros_gz issue #368 — gpu_lidar bridging RTF | https://github.com/gazebosim/ros_gz/issues/368 | open as of 2026-08-25 |
| S5b | GSoC 2025 ray-traced GPU lidar plugin | https://discourse.openrobotics.org/t/gsoc-2025-ray-tracing-enabled-faster-than-real-time-gpu-based-lidar-plugin-for-gazebo/50714 | 2025 |
| S6 | Real-Time Localization for an AMR Based on RTAB-MAP | https://www.mdpi.com/2076-0825/14/3/117 | Actuators 14(3):117, 2025 (403 on fetch — abstract only) |
| S7 | rtabmap_ros releases | https://index.ros.org/p/rtabmap_ros/ | jazzy **0.23.7**, 2026-06-21 |
| S8 | mp2p_icp (MOLA ICP core) | https://index.ros.org/p/mp2p_icp/ | **2.12.0**, 2026-07-10, humble/jazzy/kilted |
| S9 | MOLA-LO / mola_mapper_2d / mola_relocalization; GPL-3 | https://index.ros.org/p/mola_lidar_odometry/ · https://github.com/MOLAorg/mola_mapper_2d · IJRR 44(9), 2025 | **3.1.0**, 2026-08-06 |
| S10 | BlueBotics ANT localization — ±1 cm / ±1°; 6,000+ vehicles | https://bluebotics.com/autonomous-navigation-technology/ant-localization | fetched 2026-08-25 |
| S11 | SICK LiDAR-LOC — contour-based, ±30 mm, 30 Hz | https://www.sick.com/gb/en/sick-enables-easy-set-up-contour-based-navigation-on-any-mobile-platform/w/press-LiDAR-LOC | fetched 2026-08-25 |
| S12 | Toyota — reflector / natural / dual nav off one laser scanner | https://toyota-forklifts.eu/about-toyota/news-and-editorials/toyota-material-handling-expands-automation-offer-with-natural-navigation/ | ~2017 — **oldest source; taxonomy still current, date is not** |
| S13 | SICK NAV350 reflector triangulation — ±4 mm | https://www.sick.com/media/pdf/1/41/041/dataSheet_NAV350-3232_1052928_en.pdf | NAV350-3232 |
| S14 | Balyo Geoguidance; Ouster 3D lidar report | https://www.balyo.com/agv-technology/navigation-management · robotics247 Balyo/Ouster article | **Ouster article HTTP 403 — unconfirmed** |
| S15 | Jungheinrich ERC 213a / EAE 212a | https://emag.directindustry.com/2026/04/13/amr-or-agv-insights-from-jungheinrich-and-staubli/ | 2026-04-13 (**403 — from search index**) |
| S16 | Seegrid — 3D lidar SLAM core, cameras for payload | https://seegrid.com/technology/ | fetched 2026-08-25 |
| S17 | Visual SLAM supplements lidar in production AMRs | https://techvico.com/sensor-fusion-slam-for-reliable-amr-navigation/ | **secondary/SEO-grade, low confidence** |
| S18 | FAST-LIO2 paper | https://arxiv.org/abs/2107.06829 | v1, 2021-07-14 |
| S19 | FAST-LIO ROS 2 forks target Humble | https://github.com/hku-mars/FAST_LIO · https://github.com/Taeyoung96/FAST_LIO_ROS2 | fetched 2026-08-25 |
| S20 | DLIO ROS 2 unreleased branch | https://github.com/vectr-ucla/direct_lidar_inertial_odometry/tree/feature/ros2 | branch, unreleased |
| S21 | LIO-SAM Jazzy request open | https://github.com/TixiaoShan/LIO-SAM/issues/549 | opened 2025-07-08, open |
| S22 | KISS-ICP releases / Jazzy CI / FusionCore downstream | https://github.com/PRBonn/kiss-icp/releases | v1.3.0, 2024-04-26; PR #481 |
| S23 | Gazebo Harmonic pairing + support window | https://gazebosim.org/docs/latest/releases/ | gz-sim8 8.11.0, EOL Sept 2028 |

**Confidence flags:** S2, S4, S6, S15, S17 could not be fully fetched — their
numbers come from search-index text; re-verify before they appear in any
project document. S12 is a 2017 page. S14's Ouster claim is unconfirmed.
Everything else was fetched directly.
