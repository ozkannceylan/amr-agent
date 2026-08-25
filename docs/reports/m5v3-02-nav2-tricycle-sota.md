# m5v3-02 — SOTA Nav2 stack for the front-steer tricycle forklift (Jazzy / Nav2 1.3.x)

Research record, 2026-08-25, produced by a web-research agent for the
m5-ver3 track. Verified-in-source claims are marked; §8 lists open gaps.

## 0. Recommended stack (one line each)

| Slot | Choice | Why |
|---|---|---|
| Global planner | `SmacPlannerHybrid`, `motion_model_for_search: REEDS_SHEPP` | Only Jazzy planner that is both kinematically feasible for car-like models and emits reverse segments; Lattice is for drivetrains Hybrid can't express, and needs a bespoke control set generated for a 1.2 m wheelbase. |
| Local controller | `MPPI` w/ `motion_model: Ackermann`, `AckermannConstraints.min_turning_r` | Only Jazzy controller with a real Ackermann trajectory model, native reverse (`vx_min < 0`) and dynamic-obstacle avoidance in one. |
| Controller fallback | `RegulatedPurePursuit` (`use_rotate_to_heading: false`) | ~10x cheaper; keep as the 4-vehicle fleet config if MPPI×4 blows the WSL2 budget. RPP *does* reverse in Jazzy (cusp detection), contrary to its README. |
| Spur entry + exit | `opennav_docking` (`nav2_docking`) with `SimpleNonChargingDock` + AprilTag `detected_dock_pose` | Purpose-built vision-servo final approach; `undock` drives straight back out along the dock axis — exactly the "reverse out of the spur" primitive. |
| Route layer (M6+) | `nav2_route` Route Server (`compute_and_track_route`) | Edge-constrained graph nav; maps 1:1 onto VDA 5050 nodes/edges; ~44 ms for a 1 M-node graph vs 50–400 ms freespace. |
| BT shape | `navigate_through_poses` variant: RouteServer → (sparse nodes) → SmacHybrid → MPPI; `DockRobot`/`UndockRobot` BT nodes for the spur; no `Spin`/`BackUp` recoveries | Vehicle cannot rotate in place, so every rotate-based recovery must be stripped from the tree. |
| Filters | Keepout filter (aisle masks) + external `/speed_limit` publisher (PLC) + `nav2_velocity_smoother` + `nav2_collision_monitor` | Chain order: controller → velocity_smoother (`cmd_vel_smoothed`) → collision_monitor (`cmd_vel`). |
| Drive conversion | `ros2_control` `tricycle_controller` (Jazzy) | Replaces the archived custom cmd_vel→tricycle converter; takes base-link Twist, emits traction + steer. |

## 1. Planner — SmacPlannerHybrid (Reeds-Shepp)

- **Consensus is Hybrid-A\* for forklifts.** Nav2's own plugin-selection guide
  lists Smac Hybrid-A* under "Non-circular or Circular **Ackermann**"; Lattice
  is listed for "arbitrary shaped, any model" where you need custom primitives.
  Lattice's advantage — `allow_reverse_expansion` doubling the branching
  factor — is already covered by Reeds-Shepp in Hybrid.
- **Reversing:** `REEDS_SHEPP` + `reverse_penalty` (Jazzy default **2.0**,
  useful range 1.3–5.0). Set high (3.0–5.0) so the planner only reverses where
  it must — i.e. out of the spur, not in aisles.
- **Verified Jazzy defaults** (from `jazzy` branch `smac_planner_hybrid.cpp`):
  `minimum_turning_radius 0.4`, `angle_quantization_bins 72`,
  `reverse_penalty 2.0`, `change_penalty 0.0`, `non_straight_penalty 1.2`,
  `cost_penalty 2.0`, `retrospective_penalty 0.015`,
  `analytic_expansion_ratio 3.5`, `analytic_expansion_max_length 3.0`,
  `analytic_expansion_max_cost 200.0`,
  `analytic_expansion_max_cost_override false`, `tolerance 0.25`,
  `max_planning_time 5.0`, `allow_primitive_interpolation false`,
  `motion_model_for_search "DUBIN"` (must be changed).
- **Spur entry tuning:** the analytic expansion *is* the spur entry — the
  final Reeds-Shepp shot to goal. Set `analytic_expansion_max_length` ≥ spur
  depth (default 3.0 m truncates longer spurs and the planner will refuse the
  shot); raise `analytic_expansion_ratio` above 3.5 to attempt shots earlier;
  set `analytic_expansion_max_cost_override: true` if rack inflation makes the
  only legal entry path exceed cost 200 — the documented knob for "goal in a
  tight/inflated pocket".
- **`minimum_turning_radius`:** 1.2/tan(max_steer); pad ~10–15% above the
  mechanical value so the controller can track what the planner emits.
- **NOT in Jazzy:** `goal_heading_mode` (DEFAULT/BIDIRECTIONAL/ALL_DIRECTION)
  — confirmed absent from the Jazzy source; Kilted/Rolling feature. Kilted
  also adds Smac-planner switching and OMNI analytic expansion in Lattice.

## 2. Controller — MPPI vs RPP vs Vector Pursuit

- **MPPI (Jazzy):** motion models Differential / Omni / **Ackermann**
  (`min_turning_r`). Reverse via `vx_min` (default **-0.35**),
  `PreferForwardCritic` to bias forward, and `PathAngleCritic` **mode 1/2** to
  honour the planner's directional intent on Reeds-Shepp paths — mode 0 will
  fight reverse segments. Defaults `batch_size 1000`, `time_steps 56`,
  `iteration_count 1`; `model_dt` **must** equal 1/controller_frequency
  (0.05 for 20 Hz).
- **MPPI known weakness, open as of 2025-11-24:** nav2 issue #5714 —
  Ackermann/bicycle robots deviate from the global path in turns, worst in
  reverse turns; no maintainer fix, no workaround published. Budget explicit
  critic tuning (PathAlign/PathFollow/PathAngle weights) for the spur. **The
  single biggest tuning risk in this stack.**
- **Compute:** "50+ Hz on a modest 4th-gen i5" for one robot; Nav2's tuning
  guide calls MPPI "moderately higher compute cost" than DWB and much higher
  than the geometric controllers. Kilted's Eigen rewrite gives **40–45%**
  speedup — not backported to Jazzy.
- **RPP (Jazzy):** *does* reverse — `findVelocitySignChange()` detects path
  cusps by dot-product, shortens lookahead to the cusp, and
  `x_vel_sign = carrot.x >= 0 ? 1 : -1` yields negative linear velocity.
  Mandatory: `use_rotate_to_heading: false` (README explicitly excludes
  ackermann, "which cannot rotate in place"). Jazzy adds `stateful` — once XY
  tolerance is met it stops re-correcting XY, which matters for the 0.25 m
  station tolerance.
- **Vector Pursuit** (`blackcoffeerobotics/vector_pursuit_controller`,
  **v1.1.0, 2025-05-25** added Jazzy-compliant params/launch, `jazzy` branch
  exists): screw-theory geometric tracker, listed in Nav2's own
  controller-selection guide for Ackermann, RPP-class compute, better
  high-speed turning than RPP. Good middle option for the 4-vehicle fleet;
  source build only (Humble binaries only on the index).

## 3. Precision approach — Docking Server

- **In Jazzy** as `nav2_docking`/`opennav_docking` (migrated into Nav2
  June 2024). `ChargingDock` **and** `NonChargingDock` plugin types — docs
  explicitly cover "non-charging infrastructure such as static locations
  (ex. conveyors) or dynamic locations (ex. **pallets**)".
- **Detection:** subscribe `detected_dock_pose`
  (`geometry_msgs/PoseStamped`); works out of the box with
  `image_proc/TrackMarkerNode` AprilTags and isaac_ros;
  `external_detection_translation_x/y` +
  `external_detection_rotation_yaw/pitch/roll` map tag → dock pose.
- **Jazzy controller params (verified in source):** `k_phi 3.0`,
  `k_delta 2.0`, `beta 0.4`, `lambda 2.0`, `v_linear_min 0.1`,
  `v_linear_max 0.25`, `v_angular_max 0.75`, `slowdown_radius 0.25`,
  `use_collision_detection true`, `projection_time 5.0`,
  `simulation_time_step 0.1`, `dock_collision_threshold 0.3`. Server:
  `controller_frequency 50.0`, `dock_prestaging_tolerance 0.5`,
  `max_retries 3`, `undock_linear_tolerance 0.05`,
  `undock_angular_tolerance 0.05`, `staging_x_offset -0.7`,
  **`dock_backwards` (bool, default false)**.
- **`dock_backwards` exists in Jazzy at server level** — Kilted only moves it
  to a per-plugin `dock_direction`. Undock rotates the dock pose by π and
  drives to the staging pose: **the straight reverse out of the spur is a
  first-class primitive, not custom code**.
- The approach controller is the `SmoothControlLaw` (Park's graceful control
  law) with trajectory-projection collision checking against the local costmap
  footprint — same math as `nav2_graceful_controller`, so there is no reason
  to run graceful_controller separately. It emits (v, ω); for the tricycle the
  resulting curvature must be clamped to ≥ min turning radius — Jazzy's
  docking controller has **no explicit min-turning-radius clamp**, so bound it
  via the `v_linear_min`/`v_angular_max` ratio (v/ω ≥ R_min ⇒ with v_min 0.1
  and R_min 1.2, ω_max ≤ 0.083 rad/s — a deliberate retune; defaults command
  infeasible curvature).
- **Accuracy:** no published figure from Open Navigation. Tolerance knobs are
  `docking_threshold` (0.05 m) and detector quality; AprilTag rigs in the wild
  report cm-level. The 0.25 m station tolerance is comfortably inside this.

## 4. Route server + VDA 5050

- **`nav2_route` is released for Jazzy (1.3.12)** as well as Humble 1.1.20,
  Kilted 1.4.2, Lyrical 1.5.1 — but *not* Rolling per the index. Beta call was
  **2025-04-12** (18k-line PR, 98% coverage). Authors: Macenski (Open
  Navigation) + Wallace (Locus).
- API: actions `compute_route`, `compute_and_track_route`; services
  `set_route_graph` (hot-swap graph), `<DynamicEdgesScorer>/adjust_edges`
  (close/cost an edge at runtime), `<ReroutingService>/reroute`.
- Edge scorers: Distance, Time, Costmap, **DynamicEdges**, Penalty, Semantic,
  Start/GoalPoseOrientation. Operations: **AdjustSpeedLimit** (per-edge speed
  limit publish), **CollisionMonitor** (detects blockage ahead → reroute),
  ReroutingService, TimeMarker, TriggerEvent.
- Three usable architectures: (a) dense route path straight to controller,
  (b) sparse route nodes → Planner Server for local freespace, (c) hybrid —
  follow route when clear, plan around when blocked. **(b) is the right one
  here**: route enforces aisle discipline, SmacHybrid still produces the
  feasible Reeds-Shepp curve through each node.
- **VDA 5050 mapping.** Nav2 documents the **VDA5050 LIF Editor**
  (bekirbostanci, web tool, `bekirbostanci/vda5050_lif_editor`) which exports
  **the same layout as both a VDA 5050 LIF file and a Route Server GeoJSON
  graph** — the fleet's LIF and the vehicle's route graph come from one source
  of truth. Cleanest published order→Nav2 mapping; directly fits full-route
  VDA 5050 orders.
- Real stacks: `tum-fml/vda5050_connector` (VDA 5050 1.1, 4 nodes: state
  handler / NavToNode handler → Nav2 goals / VDA action handler);
  `inorbit-ai/ros_amr_interop/vda5050_connector` (OTTO Motors + InOrbit +
  Ekumen, shipped in OTTO 2.28, NVIDIA-verified against **Isaac Mission
  Dispatch**). Open-RMF's route is different: fleet adapters map RMF paths
  onto Nav2 action APIs (`free_fleet` + zenoh-bridge-ros2dds), no VDA 5050
  natively.

## 5. Safety / realism plumbing

- **PLC V_Limit → `/speed_limit`.** Publish `nav2_msgs/SpeedLimit` (fields:
  header, `percentage` bool, `speed_limit`) directly from the PLC bridge. The
  Controller Server subscribes to `speed_limit_topic` and clamps — **the Speed
  Filter costmap plugin is not required**; Nav2 docs explicitly bless "an
  external server to publish these messages". Use `percentage: false` and
  absolute m/s so 0.3 means 0.3. `speed_limit: 0.0` = no limit.
  Approach-from-below falls out naturally: controller max = min(configured,
  limit), and the velocity smoother's deceleration limits shape the descent.
- **Collision monitor (Jazzy).** Actions stop / slowdown / limit / approach.
  Jazzy adds **VelocityPolygon** (different zones per commanded velocity — one
  zone for 0.7 m/s cruise, a tighter one for 0.3 m/s creep, one for reverse),
  plus a separate **CollisionDetector** node that only reports
  (`collision_detector_state`) without touching velocity — ideal for driving
  an HMI/PLC lamp. Also dynamic enable/disable of sources & polygons, and a
  source-timeout watchdog. Kilted adds debounce params.
- **Explicit disclaimer to keep in the design doc:** collision monitor "does
  not provide hard real-time safety certifications" and does not replace a
  safety-rated PLC. It complements the F-PLC; it is not the F-PLC.
- **Keepout filters** for rack faces / no-go aisles; **ZoneParameterFilter**
  (spatially varying param overrides) is Kilted-only.
- **Footprint.** Give the real polygon, not a radius — Nav2 explicitly
  recommends geometric footprint for non-circular robots so planners can enter
  tight spaces. For fork overhang: publish an **asymmetric polygon** (origin
  at rear axle, forks extending +x well past the body). Republish a *larger*
  footprint on `~/footprint` when laden — Nav2 documents exactly this case
  ("picking up a pallet"). Prefer footprint geometry over `footprint_padding`,
  which inflates isotropically and will forbid legal spur entries.
- **Velocity smoother**: Jazzy defaults to `TwistStamped` and applies
  deceleration on command timeout.

## 6. Multi-robot (4 vehicles, WSL2)

- Jazzy: `cloned_tb3_simulation_launch.py` (N robots, one shared
  `nav2_multirobot_params_all.yaml`, namespaces as launch args) and
  `unique_tb3_simulation_launch.py` (per-robot params). >2 robots requires
  editing the unique launch script. Simple Commander API gained a `namespace`
  constructor field in Jazzy. **The full namespace-based bringup revamp is
  Kilted, not Jazzy** — expect launch-file surgery.
- **Compute is the binding constraint, and RMW choice dominates it.** Nav2
  tuning guide (Dec 2025, TB4 sim): **Zenoh 4.5%, FastDDS 6.8%, CycloneDDS
  18.3%** CPU. Intra-process (ConstSharedPtr): Zenoh → 5.8%, FastDDS → 7.8%,
  CycloneDDS → 16.1% (only Cyclone benefits). For 4 stacks on WSL2: use
  `rmw_zenoh` or FastDDS, **not** CycloneDDS; use composed/single-process
  bringup.
- Reference: Open Navigation's AMD Ryzen AI demo — full Nav2 + 3D lidar +
  camera perception + localization averaged **10.85% of a 16-core, 60 W
  platform** (single robot). ×4 plus Gazebo Harmonic physics is the real
  budget question; Open Navigation's **robotics workload benchmark** is the
  published tool for measuring it.
- Cheapest wins for 4×: drop MPPI to RPP or Vector Pursuit on 3 of 4, share
  one map server, lower local costmap update rates, and prefer the Route
  Server (44 ms/1 M nodes) over repeated freespace global replans.

## 7. Pinned sources

| # | Source | URL | Version / date |
|---|---|---|---|
| 1 | nav2_smac_planner README (jazzy) | https://raw.githubusercontent.com/ros-navigation/navigation2/jazzy/nav2_smac_planner/README.md | Jazzy branch |
| 2 | smac_planner_hybrid.cpp param defaults | https://raw.githubusercontent.com/ros-navigation/navigation2/jazzy/nav2_smac_planner/src/smac_planner_hybrid.cpp | Jazzy branch |
| 3 | Smac Hybrid-A* config docs | https://docs.nav2.org/configuration/packages/smac/configuring-smac-hybrid.html | Nav2 rolling docs |
| 4 | MPPI README (Jazzy API) | https://api.nav2.org/nav2-jazzy/html/md_nav2_mppi_controller_README.html | Jazzy |
| 5 | MPPI Ackermann reverse-turn tracking issue | https://github.com/ros-navigation/navigation2/issues/5714 | open, last update 2025-11-24 |
| 6 | RPP cusp/reverse logic | https://raw.githubusercontent.com/ros-navigation/navigation2/jazzy/nav2_regulated_pure_pursuit_controller/src/regulated_pure_pursuit_controller.cpp | Jazzy branch |
| 7 | Vector Pursuit controller | https://index.ros.org/p/vector_pursuit_controller/ · https://github.com/blackcoffeerobotics/vector_pursuit_controller/tree/jazzy | v1.1.0, 2025-05-25 |
| 8 | Nav2 Docking framework (Jazzy) | https://api.nav2.org/nav2-jazzy/html/md_nav2_docking_README.html | Jazzy |
| 9 | docking_server.cpp (dock_backwards, undock) | https://raw.githubusercontent.com/ros-navigation/navigation2/jazzy/nav2_docking/opennav_docking/src/docking_server.cpp | Jazzy branch |
| 10 | Docking controller.cpp gains/collision | https://raw.githubusercontent.com/ros-navigation/navigation2/jazzy/nav2_docking/opennav_docking/src/controller.cpp | Jazzy branch |
| 11 | opennav_docking repo | https://github.com/open-navigation/opennav_docking | migrated into Nav2 June 2024 |
| 12 | Nav2 Route Server README (Jazzy) | https://api.nav2.org/nav2-jazzy/html/md_nav2_route_README.html | Jazzy |
| 13 | nav2_route release matrix | https://index.ros.org/p/nav2_route/ | Jazzy **1.3.12**, Kilted 1.4.2, Lyrical 1.5.1, Humble 1.1.20 |
| 14 | Route Server beta call | https://discourse.openrobotics.org/t/nav2-request-for-beta-testing-nav2-route-server/43189 | 2025-04-12 |
| 15 | VDA5050 LIF Editor → Route graph tutorial | https://docs.nav2.org/tutorials/docs/route_server_tools/route_graph_generation_lif_editor.html · https://github.com/bekirbostanci/vda5050_lif_editor | current |
| 16 | TUM VDA5050 ROS connector | https://github.com/tum-fml/vda5050_connector | VDA 5050 v1.1 |
| 17 | OTTO/InOrbit/Ekumen VDA5050 connector | https://github.com/inorbit-ai/ros_amr_interop/tree/galactic-devel/vda5050_connector | OTTO 2.28 |
| 18 | NVIDIA Isaac Mission Dispatch | https://github.com/NVIDIA-ISAAC/isaac_mission_dispatch | VDA5050-compatible |
| 19 | Collision Monitor README (jazzy) | https://raw.githubusercontent.com/ros-navigation/navigation2/jazzy/nav2_collision_monitor/README.md | Jazzy branch |
| 20 | Speed Filter / SpeedLimit msg | https://docs.nav2.org/configuration/packages/costmap-plugins/speed_filter.html · https://api.nav2.org/msgs/jazzy/speedlimit.html | Jazzy msg |
| 21 | Footprint setup guide | https://docs.nav2.org/setup_guides/footprint/setup_footprint.html | current |
| 22 | Iron→Jazzy migration (what IS in Jazzy) | https://docs.nav2.org/migration/Iron.html | Jazzy |
| 23 | Jazzy→Kilted migration (what is NOT in Jazzy) | https://docs.nav2.org/migration/Jazzy.html | Kilted |
| 24 | Nav2 tuning guide — RMW/composition CPU, plugin selection | https://docs.nav2.org/tuning/index.html | Dec 2025 measurements |
| 25 | nav2_bringup multi-robot launch | https://github.com/ros-navigation/navigation2/blob/main/nav2_bringup/README.md · https://index.ros.org/p/nav2_bringup/ | Jazzy 1.3.x |
| 26 | Open Navigation AMD demo (10.85%/16-core) | https://github.com/open-navigation/opennav_amd_demonstrations | 2025 |
| 27 | Open Navigation robotics workload benchmark | https://discourse.openrobotics.org/t/nav2-open-navigations-robotics-workload-benchmark-release/56909 | 2025 |
| 28 | ros2_control tricycle_controller (Jazzy) | https://control.ros.org/jazzy/doc/ros2_controllers/tricycle_controller/doc/userdoc.html | Jazzy |
| 29 | AprilTag docking walkthrough (Jazzy) | https://automaticaddison.com/autonomous-docking-with-apriltags-using-nav2-ros-2-jazzy/ | ROS 2 Jazzy |

## 8. Gaps / unresolved

- No published docking-accuracy number from Open Navigation; must be measured
  on the rig.
- MPPI Ackermann reverse-turn tracking (#5714) is open with no maintainer
  answer — real risk for the reverse-out-of-spur segment; the docking server's
  undock primitive sidesteps it, another argument for routing spur exit
  through `UndockRobot` rather than through the controller.
- Docking approach controller has no min-turning-radius clamp in Jazzy; gains
  must be derived from R_min = 1.2/tan(max_steer) by hand.
- No public benchmark of 4 simultaneous Nav2+AMCL stacks on one WSL2 host; the
  Open Navigation workload benchmark is the tool to generate that number
  locally.
