# M6V2 SPEC — Namespacing & Instantiation of four m5v3 stacks in one world

> **AMENDED BY AMR-DEC-006 (2026-09-02), read this first.**
> This spec stands EXCEPT:
> - §3.3's override of `topics.steer_cmd/traction_cmd/fork_cmd` to the
>   pre-contactor topics is **SUPERSEDED**: the command seam is
>   SPEC_ADAPTER.md's — Nav2 → smoother → adapter → `/fN/auto/cmd_vel`
>   → cmd_mux → cmd_gate → forklift_io → sto_contactor. m5v3's navcmd
>   SHELL does not port at all (its core is imported by the adapter),
>   so those three keys are dark in the derived configs and the
>   single-writer rule is kept at the contactor with no rewiring.
> - §7 T4's ported child list drops `navcmd` accordingly (smoother
>   stays; the adapter node replaces navcmd downstream of it).
> - New code lives under `m6_ver2/` (adapter modules in
>   `m6_ver2/nav2_adapter/`); `m6/` and `m5_ver3/` stay byte-untouched.
> The frame scheme below (§2: one `/tf`, prefixed frames, shared `map`)
> is CONFIRMED by DEC-006 and overrides SPEC_ADAPTER.md's
> per-truck-`/fN/tf` sentence.

Scope: branch `m6-ver2`. Four trucks f1..f4, each running the m5_ver3
autonomy stack, one gz world (`m6/gazebo/warehouse_ver3.sdf`, partition
`m6`), one ROS domain (96), beside the untouched m6 fleet layer. Donor
`m5_ver3/` is never edited; `main` untouched; ground-truth odom
instrument-only; docking/D455/image-bridge dark.

---

## 1. Namespace scheme — ROS namespace `/<vid>` on every per-truck child

**Decision: whole-stack node namespacing via `--ros-args -r __ns:=/<vid>`
on every per-truck spawn line, not per-name rewriting.**

Grounding and why per-name rewriting is impossible anyway:

- m5v3 spawns every stack child with `ros2 run ... --ros-args -r
  __node:=<name>` and no namespace (`m5_ver3/m5v3.sh:2223-2225` ekf,
  `2402-2404` amcl, `2664-2668` planner, `2689-2696` controller,
  `2731-2740` bt_navigator, `2756-2760` lifecycle manager, `2281-2288`
  smoother, `2338` collision monitor).
- The costmaps are **sub-nodes with no command line**:
  `config.yaml:4270` (`costmap_sections: "local_costmap global_costmap"`)
  and the comment above it say the servers construct them; their FQNs
  are `<parent_ns>/local_costmap/local_costmap` and cannot be renamed
  with `-r __node:=`. Four un-namespaced controller servers would create
  four nodes all named `/local_costmap/local_costmap` — a hard
  collision. Namespacing is the only mechanism that renames them, and
  it renames everything else (node names, actions, services, lifecycle
  addressing, bond topics) in the same stroke. Standard Nav2
  multi-robot practice.

**How each child gets it:** the per-truck runner (§4) appends three
remaps to *every* spawn line, uniformly:

```
--ros-args -r __ns:=/<vid> -r tf:=/tf -r tf_static:=/tf_static
```

(the tf pair is §2's shared-tree remap; match sides are **relative** so
they fire under the namespace). The python children
(`wheel_odometry.py`, `rf2o_twist.py` — spawned bare at
`m5v3.sh:2072, 1944`) get the same `--ros-args` block: without it four
`/wheel_odometry` nodes collide by name. No launch-file machinery is
required; `ros2 run` + `__ns` is exactly launch's `PushRosNamespace`
at the rcl layer.

**What this does to the params-file top-level keys — actual rcl/rclcpp
behavior, stated:**

- A node resolves overrides from a `--params-file` by matching keys
  against its **fully qualified name**. The working spellings for node
  `/f1/controller_server` are: exact FQN key (`/f1/controller_server:`),
  **namespace-nested keys** (`f1:` → `controller_server:` →
  `ros__parameters:` — the parser joins nested map keys into the FQN),
  and wildcards (`/**:` any node, `/**/controller_server:` that name in
  any namespace; wildcard support has been in `rcl_yaml_param_parser`
  since Galactic and is in Jazzy).
- A bare top-level `controller_server:` addresses **only the
  root-namespace node**. Handed to `/f1/controller_server` it
  contributes nothing and the server comes up **silently on package
  defaults** — the exact failure `config.yaml:4266-4268` documents and
  `check_nav_params` exists to refuse (`m5v3.sh:1369`). This is why
  nav2_bringup's own multi-robot launch rewrites its params with
  `RewrittenYaml(root_key=namespace)`.

**Chosen key form: the root-key wrap.** The derivation tool (§3)
indents each node-keyed yaml by two spaces and prepends `<vid>:` as the
sole top-level key — mechanically identical to nav2's proven
`RewrittenYaml root_key` transform, and it composes correctly with the
already-two-level costmap keys (`nav2.yaml:1767` `local_costmap:` →
nested `local_costmap:` → `ros__parameters:` becomes
`/f1/local_costmap/local_costmap`). Alternatives weighed: FQN-per-key
rewrite works but touches seven keys per file instead of one line;
`/**` wildcards are rejected because our derived files carry
**per-truck frame literals** — a wildcard-keyed f1 file mistakenly
handed to f2's node would configure the wrong truck without complaint,
where the root-key form refuses cross-application structurally.
Affected files and their top-level keys: `nav2.yaml` (7 keys:
planner_server:330, controller_server:555, local_costmap:1767,
global_costmap:1975, bt_navigator:2130, behavior_server:2214,
nav_lifecycle_manager:2258), `amcl.yaml` (map_server:73 — dead once
wrapped, see §4; amcl:97), `ekf.yaml` (m5v3_ekf:110), `smoother.yaml`
(velocity_smoother:71), `collision_monitor.yaml` (collision_monitor:142),
and dark `docking.yaml`/`apriltag.yaml`.

**Command-line remap/lifecycle consequences the port must carry**
(silent-breakage class, pinned by test in §5):
- Absolute-match remaps stop firing under a namespace. `-r /cmd_vel:=…`
  (`m5v3.sh:2696, 2714`), `-r /cmd_vel_smoothed:=…` (`2288`),
  `-r /odometry/filtered:=…` (`2236`) must become relative matches
  (`cmd_vel:=`, `odometry/filtered:=`) in the ported runner.
- `ros2 lifecycle get|set "/$node"` (`m5v3.sh:1295-1300, 1359`) becomes
  `"/$VID/$node"`; likewise `tools/nav_health.py`'s six-node wait.
- `-p` overrides are unaffected; the m5v3 pattern of passing every
  topic and frame as `-p` from config survives untouched — only the
  *values* change, and they come from the derived config.

## 2. Frames — `<vid>/`-prefixed REP-105 frames, one shared `map`, one `/tf` tree

**Decision: single `/tf`+`/tf_static`; frames `<vid>/odom`,
`<vid>/base_link`, `<vid>/<sensor>_link`; ONE shared `map` frame; four
AMCLs each owning a distinct `map -> <vid>/odom` edge.**

- tf2 permits any number of child edges under one parent; conflict
  exists only when two authorities publish the *same* edge — exactly
  the recorded defect (`m6/CONTEXT.md:263-290`: all trucks emitting
  `forklift/odom`, "the second one wins, silently"). With prefixed
  frames, `/f1/amcl` publishes `map -> f1/odom` (its `global_frame_id`
  stays `map`, `odom_frame_id` becomes `f1/odom` — both passed `-p` at
  `m5v3.sh:2409-2411`), each `/fN/m5v3_ekf` publishes
  `fN/odom -> fN/base_link` (`-p` at `2229-2233`), and the static
  mounts hang below (`imutf` `m5v3.sh:2091`, `lasertf` `1885`). Four
  disjoint edge sets, one connected tree, one RViz/bag view.
- Costmap/BT frames per truck (all file literals, rewritten in the
  derived `nav2.yaml`): local costmap `global_frame: odom → <vid>/odom`,
  `robot_base_frame: base_link → <vid>/base_link` (`nav2.yaml:1771-1772`);
  global costmap `global_frame: map` **unchanged**,
  `robot_base_frame → <vid>/base_link` (`1979-1980`); bt_navigator
  `global_frame: map` unchanged, `robot_base_frame → <vid>/base_link`
  (`2133-2134`); behavior_server `local_frame → <vid>/odom`,
  `global_frame: map` unchanged, `robot_base_frame → <vid>/base_link`
  (`2225-2227`). `collision_monitor.yaml:165,174` likewise.
- Alternative weighed: fully-namespaced TF (`/fN/tf` per truck, bare
  frames) — Nav2's default multi-robot shape, zero frame rewrites.
  Rejected: it leaves the recorded defect standing, and
  `m6/CONTEXT.md:282-289` is explicit that the frames must be
  namespaced in the derived model **before the first consumer appears**
  — the first consumer is this branch. Shared-map-frame also gives the
  fleet layer world-frame poses for free.
- `<vid>/map` per truck rejected with the per-truck map_server (§4):
  four "map" frames that are the same floor are four spellings of one
  fact.

**Who rewrites `model.sdf` frames: the m6v2 instantiation tool (§3),
extending the counted-rewrite mechanism exactly where
`m6/CONTEXT.md:286-289` says the fix belongs.** The uniform rule:
*every frame-bearing literal gains the `<vid>/` prefix*. No new names
are invented — the ground-truth OdometryPublisher frames become
`f1/forklift/odom` / `f1/forklift/base_link`, preserving the donor's
deliberate distinction between the reference's frame names and the
estimate's (`model.sdf:2204-2220`; ground truth stays instrument-only,
its `<tf_topic>` is never bridged, so these names appear only in
scored message headers, never on `/tf`).

**Every frame-bearing literal in `m5_ver3/gazebo/forklift_ver3/model.sdf`:**

| line | literal | rewrite |
|---|---|---|
| 456 | `<gz_frame_id>safety_scanner_back_link` | `<vid>/safety_scanner_back_link` |
| 533 | `<gz_frame_id>safety_scanner_left_link` | `<vid>/safety_scanner_left_link` |
| 610 | `<gz_frame_id>safety_scanner_right_link` | `<vid>/safety_scanner_right_link` |
| 707 | `<gz_frame_id>nav_lidar_link` | `<vid>/nav_lidar_link` |
| 979 | `<gz_frame_id>nav_lidar_3d_link` | `<vid>/nav_lidar_3d_link` |
| 1128 | `<gz_frame_id>pallet_cam_optical` | `<vid>/pallet_cam_optical` (dark but rewritten — inertness is not a licence to drift) |
| 1258 | `<gz_frame_id>imu_link` | `<vid>/imu_link` |
| 2226 | `<odom_frame>forklift/odom` | `<vid>/forklift/odom` |
| 2227 | `<robot_base_frame>forklift/base_link` | `<vid>/forklift/base_link` |

(`forklift/odom`/`forklift/base_link` also appear in the comment at
2211-2212 — the tool counts whole-file occurrences, 2 live + 2 comment
each, and pins the total.) The mirrored `config.yaml frames:` block
moves **in the same pass**: `config.yaml:653` odom, `657` base_link,
`661` imu_link, `666` nav_lidar_link, `676` rf2o_odom, `688`
pallet_cam_link, `693` pallet_cam_optical all gain `<vid>/`;
**`683 map: "map"` stays unchanged** — the one shared frame.

## 3. Config derivation — build-time counted rewrite into gitignored per-vid trees

**Decision: template + counted mechanical rewrite (the
`instantiate_vehicle.py` mechanism, grown up), one derived file set per
vid under `m6_ver2/vehicles/<vid>/`, gitignored build products with a
manifest. Runtime parameterization rejected** — the residue that
*cannot* be runtime-parameterized decides it: BT XML ports take
literals (`behavior_trees/navigate_to_pose_tricycle_v3.xml:112`,
`odom_topic="/m5v3/odometry/filtered"` at `:204` and `_rpp.xml:73`),
SDF plugins take literals, nav2.yaml frame keys are file-borne, and the
root-key wrap (§1) is a file transform by nature. One mechanism for all
of it, with the count assertion as the safety
(`m6/tools/instantiate_vehicle.py:10-13, 40-51`).

Derived per vid: `model.sdf`, `config.yaml`, `nav2.yaml`, `amcl.yaml`,
`ekf.yaml`, `smoother.yaml`, `collision_monitor.yaml`,
`navigate_to_pose_tricycle_v3.xml`, `navigate_to_pose_tricycle_v3_rpp.xml`
(+ dark `docking.yaml`/`apriltag.yaml`/`ekf_rf2o.yaml` for
completeness). `plugin_lib_names`' `m5v3_direction_stable_bt_node` and
the `bt_direction_stable` `.so` are **shared read-only** — four
bt_navigators dlopen one library — no copy, no rewrite (`m5v3` in that
name has no `/m5v3/` and escapes the prefix rule by construction).

**Transform pipeline per file (ordered; every step counted):**
1. Blanket prefix rewrites: `/forklift/` → `/<vid>/` (model.sdf: 48
   occurrences; config.yaml topics; nav2.yaml scan topics at 1813,
   2061) and `/m5v3/` → `/<vid>/` (config.yaml `topics.wheel_odom:403`,
   `odometry_filtered:413`, `collision_monitor_state:604`,
   `navcmd_status:628`, rf2o/fuse/apriltag entries; BT XMLs'
   `odom_topic`). No collision with the fleet layer's names
   (`/f1/plc/…`, `/f1/auto/…`, `/f1/safety/…` —
   `status_contract.py:264-275`).
2. Keyed frame rewrites per §2's inventory.
3. Keyed value overrides (dotted-key aware, each refusing if the key's
   current value isn't the donor's):
   - ~~steer/traction/fork_cmd re-point~~ **SUPERSEDED by DEC-006**
     (see amendment header; the three keys go dark in derived configs).
   - Bare shared names gain the vid: `topics.cmd_vel:574 /cmd_vel →
     /<vid>/cmd_vel`, `cmd_vel_smoothed:575`, `cmd_vel_monitored:598`,
     `speed_limit:622`, `initialpose:522 → /<vid>/initialpose`,
     `amcl_pose:521 → /<vid>/amcl_pose`, `slam_pose:548`,
     `dock_robot/undock_robot:340-341` (dark). **`topics.map:523 "/map"`
     and `topics.clock:297 "/clock"` stay unchanged** (shared, §4);
     `topics.tf/tf_static:501-502` stay `/tf`,`/tf_static`.
   - Isolation: `isolation.gz_partition:36 "m5v3" → "m6"`,
     `isolation.ros_domain_id:37 "97" → "96"` (`map_ros_domain_id:52
     "98"` stays — offline arm, still ≠ 96).
   - Singleton paths: `paths.pidfile:2280 → "m6_ver2/vehicles/<vid>/.pids"`,
     `paths.traction_file:2293 → "m6_ver2/vehicles/<vid>/.traction"`,
     `paths.log_dir:2267 → "m6_ver2/logs/<vid>"`.
   - Derived-artifact paths: `ekf.params_file`, `nav.params_file`,
     `nav.bt_xml`, `nav.bt_xml_rpp`, `smoother.params_file`,
     `monitor.params_file`, `localization.amcl.params_file`,
     `vehicle.model` → the `m6_ver2/vehicles/<vid>/…` copies.
   - `vehicle.spawn.{x,y,z,yaw}` → the `VEHICLES` table's pose for the
     vid (`m6/ipc/status_contract.py:52-65`) — one source, the pose the
     world owner also spawns at, and the pose the AMCL initialpose seed
     reads.
4. Root-key wrap `<vid>:` (+2-space indent) on the six node-keyed yamls
   (§1). Count check: line-count out = in + 1, every non-empty line
   gained exactly two leading spaces.
5. Manifest per vid: donor sha256 per source, per-literal
   expected/observed counts, tool version. The world owner refuses a
   stale or missing derivation the way `m6_world.launch.py:110-119`
   already refuses, extended with the sha check.

**The remaining m5v3 singletons, dispositioned:**
`GZ_PARTITION`/`ROS_DOMAIN_ID` exports come from the derived config per
truck; the **sweep** cannot stay keyed on partition alone — `ours()`
(`m5v3.sh:538-541`) on `GZ_PARTITION=m6` would nominate the neighbor
trucks *and* the whole m6 fleet (`m6.sh:48,140` uses the same key). The
per-truck runner therefore exports `M6V2_VID=<vid>` on every child and
its `ours()` requires **both** lines in `/proc/<pid>/environ`. The
`M5V3_PATTERNS` list (`tools/_common.sh:185-196`) carries over minus
`gz sim`, `parameter_bridge`, `image_bridge`, `nav2_map_server`,
`apriltag_node`, `opennav_docking`, `detected_dock.py` (world-owned or
dark).

## 4. The shared world — one owner: the m6v2 world launch; one bridge; one map_server

**Decision: bringup of the plant (server, four model spawns, the
bridge, the shared map_server, and the fleet's per-truck
io/contactor pair) has ONE owner — a new `m6_ver2/world.launch.py`
grown from `m6_world.launch.py`'s pattern. m5v3's spawn machinery is
not reused per truck; the per-truck runner owns only the ROS stack.**
The new launch spawns the **forklift_ver3-derived** models
(`-name forklift_<vid>`, poses from `contract(vid)`, exactly the
`m6_world.launch.py:317-345` shape) — the ver3 model carries the same
frozen safety scanners and actuator terminals the fleet layer needs, so
`sto_contactor`/`forklift_io` run against it unchanged.

**Bridge: ONE shared parameter_bridge, owned by the world launch,
carrying the deduplicated union.** Per-truck bridges rejected: the m6
bridge already carries, per vid, the terminals (ROS→gz), gt odom,
scan_nav, read_a/read_b, and the three safety scans, plus `/clock` once
(`m6_world.launch.py:145-209`); a per-truck m5v3-shaped bridge would
put a **second publisher** on `/fN/gz/scan_nav`, `/fN/gz/odom`,
`/clock`. One bridge line per channel, one owner. The union adds
exactly two gz→ROS lines per truck to the m6 set: `/<vid>/gz/imu` and
`/<vid>/gz/joint_state`. `image_bridge` and cam_info: DARK. Bridge args
are built from each vid's *derived* config the way
`m6_world.launch.py:139-149` already does, so bridge and model can only
agree.

**Command seam:** see the DEC-006 amendment header — SPEC_ADAPTER.md
§Decision-1 owns it.

**Map server: ONE shared `/map_server` + four AMCLs subscribing
`/map`. Per-truck map_servers rejected.** The artifact is one frozen,
md5-gated grid (`config.yaml:516-520`); four servers would be four
copies of an immutable latched publication that could differ only by
mistake. The transient-local `/map` serves late-joining AMCLs and all
four global-costmap static layers (`nav2.yaml:2012 map_topic: /map`,
absolute — untouched by any namespace). Mechanics: the world launch
runs `nav2_map_server` un-namespaced with the **donor**
`m5_ver3/amcl.yaml` (its bare `map_server:73` key matches
`/map_server`; zero derived bytes) plus the same
`-p yaml_filename/topic/frame` overrides `m5v3.sh:2379-2390` passes,
and drives its lifecycle. Each truck runner gates its `/fN/amcl`
activation on `/map` being latched. Each namespaced AMCL gets
`-p map_topic:=/map` (absolute; parameters are not remapped by `__ns`).

## 5. What stays byte-identical, and how drift is refused

Byte-identical from the m5v3 donor (the §3 transform list is
exhaustive; everything else is untouched bytes): every parameter
**value** — MPPI and RPP controller blocks, DSP ports except
`odom_topic`, costmap layer stacks/footprints/inflation, EKF matrices,
AMCL particle/beam config, smoother limits, collision-monitor polygons,
BT tree structure and `Timeout msec="335000"`, lifecycle timeouts, and
the shared `.so`s.

Drift refusal (all G1 tests, `m6_ver2/tests/`):
- **Count pins**: for every (file, literal) pair in the inventory, the
  tool asserts observed==expected and the test re-asserts against the
  checked-in expected table.
- **Residue pin**: apply the recorded inverse mapping to each derived
  file (unwrap root key, strip `<vid>/` and `/<vid>/`, restore keyed
  overrides) and require byte-equality with the donor.
- **Regeneration idempotence**: run the tool twice; identical bytes and
  manifest.
- **Addressing pin**: parse each wrapped yaml and assert every donor
  node key reappears exactly once under `<vid>:` and that the six
  `NAV_SECTIONS` (`m5v3.sh:426-433`) resolve to `/f1/...` FQNs.
- **Single-writer pins**: the bridge-args builder's output contains no
  duplicated topic across all lines + `/clock` exactly once.
- **Frame-defect regression**: assert no two vids' derived model.sdf
  share any frame literal, and that `frame_id`s observed live on
  `/f1/gz/odom` vs `/f2/gz/odom` differ (m6/CONTEXT.md:273-275's
  measured defect, inverted into a gate).

## 6. Counted-rewrite literal inventory (per source file)

- `gazebo/forklift_ver3/model.sdf`: `/forklift/` ×48 (46 lines: 16
  topic elements incl. pallet attach/detach/state `2245-2247`, sensors,
  actuators, `odom_topic`/`tf_topic` `2224-2225`; remainder comments);
  `forklift/odom` ×2, `forklift/base_link` ×2 (live 2226-2227 + comment
  2211-2212); 7 `gz_frame_id` literals (§2 table). Dark literal
  flagged, not rewritten in G1: `<child_model>pallet_s5</child_model>`
  (2243) — see open questions.
- `config.yaml`: `/forklift/` topic values (309, 313, 317, 328-330,
  344, 348-350, 357, 362, 374, 385, 397, 488 + comments); `/m5v3/`
  values (335, 339, 403, 413, 436-437, 466, 604, 628); 7 frame values
  (§2); keyed overrides (§3.3); isolation pair (36-37); paths triple
  (2267, 2280, 2293); params-file paths; spawn quad.
- `nav2.yaml`: scan topic ×2 (1813, 2061); frame lines ×6 (1771, 1772,
  1980, 2134, 2225, 2227); root-key wrap over 7 node keys. Unchanged by
  assertion: 1979/2133/2226 (`map`), 2012 (`/map`).
- `collision_monitor.yaml`: 165, 174; wrap.
- `amcl.yaml`, `ekf.yaml`, `smoother.yaml`: wrap only (zero topic/frame
  literals — verified).
- `behavior_trees/*.xml`: `/m5v3/odometry/filtered` (v3:204, rpp:73 +
  comment mentions; whole-file count pinned).
- Whole-file counts are measured off the donor at tool-authoring time
  and checked in as the expected table.

## 7. G1 build-task list (one module, one owner each)

1. **T1 `m6_ver2/tools/instantiate_truck.py`** — the derivation tool:
   transform pipeline §3, inventory table §6, manifest writer,
   `--all`/per-vid CLI; imports `VEHICLES`. (Sole writer of
   `m6_ver2/vehicles/`.)
2. **T2 `.gitignore` + `m6_ver2/vehicles/` manifest schema** —
   build-product hygiene, mirroring `.gitignore:55-61`'s m6 precedent.
3. **T3 `m6_ver2/world.launch.py`** — gz server (world by reference, no
   copy), four ver3-derived spawns, ONE union bridge, shared map_server
   + its lifecycle, per-truck `sto_contactor`/`forklift_io`, GUI gate
   on all four back scanners, staleness refusal against T1's manifest.
4. **T4 `m6_ver2/truck.sh <vid>`** — per-truck stack runner ported from
   m5v3.sh's stack half (static TFs, wheel odom, EKF, smoother,
   monitor arm, AMCL, four Nav2 servers + lifecycle manager; navcmd
   NOT ported per DEC-006): reads derived config, appends `__ns`/tf
   remaps, relative-match remap fixes, ns-aware lifecycle driving,
   `/map`-latched gate, VID-scoped `ours()`/sweep, per-vid
   pid/traction/log files.
5. **T5 `m6_ver2/m6v2.sh`** — fleet wrapper: preflight (renderer gate,
   derivation freshness), `start` = world + 4×T4, `status`, `stop`
   (VID-sweeps then world), state files per truck.
6. **T6 `m6_ver2/tests/`** — the pin suite of §5 plus a live smoke
   assertion set (four disjoint TF edge sets under one `map`, one
   publisher per terminal, `ros2 node list` shows
   `/fN/local_costmap/local_costmap` ×4).

## 8. Test plan (pins)

Static (pytest, no sim): §5's count/residue/idempotence/addressing/
single-writer pins; `test_vehicles_table`-style rule tests for the
derived spawn/initialpose agreement with `VEHICLES`. Live (gated, one
bringup): frame-defect regression; `tf2_echo map f1/base_link` and
`map f2/base_link` resolve simultaneously; a goal to f1 moves only f1's
terminals; STO demand on f1 stops f1 mid-goal. RTF re-measured against
`m6/CONTEXT.md:256-258`'s 0.575 baseline before any figure is quoted.

## 9. Open questions

1. ~~Fleet-layer command arbitration~~ — RESOLVED by AMR-DEC-006 (the
   adapter feeds `/fN/auto/cmd_vel`; mux/gate keep authority).
2. **`pallet_s5`** (`model.sdf:2243`): four DetachableJoints naming one
   child model — dark with docking, but the literal needs a per-vid
   ruling before pallet work wakes.
3. **`m6.sh` coexistence**: its partition-keyed sweep (`m6.sh:140`)
   will nominate the truck stacks — acceptable as fleet-wide stop, but
   `m6.sh start`'s world half must be declared off-limits in the m6v2
   runbook (two servers otherwise).
4. **Load**: 4× (EKF+AMCL+Nav2+DSP) on a 0.575-RTF world is unmeasured;
   the G1 gate must measure before claiming.
5. Confirm no scorer greps the literal `forklift/odom`
   (`m6/tools/score_run.py`) before the gt-frame prefix lands.
