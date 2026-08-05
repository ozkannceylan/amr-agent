# m5-24 — Phase 1: one vehicle behind a real wall

    brief:               docs/briefs/m5-24-vehicle-image-phase1.md
    status:              done
    files_changed:
      - agv/forklift/vehicles/allocation.yaml            (new) the one owner of serial -> domain
      - agv/forklift/vehicles/F001.yaml                  (new) one vehicle's identity
      - agv/forklift/scripts/vehicle_identity.py         (new) the single reader of both, with --self-check
      - agv/forklift/scripts/vehicle_image.py            (new) the launcher; the systemd unit's stand-in
      - agv/forklift/launch/vehicle_image.launch.py      (new) everything the vehicle's computer runs
      - agv/forklift/scripts/check_contract_topics.py    (new) diffs the README contract against a live graph
      - agv/forklift/EVIDENCE_VEHICLE_IMAGE.md           (new) the recorded run
      - agv/forklift/README.md                           (edited) the new files, and the two-sides recipe
      - docs/reports/m5-24-vehicle-image-phase1.md       (this file)
    invariants_touched:  none. One ADR-vs-brief disagreement, resolved and reported below (§2)
    open_questions:      six, §4
    next_suggested:      a sim/ brief for the world-only entry point (§3), then ADR 0016 Phase 2

---

## 1. What was built, and what proves it

Two sides where there was one launch tree. The **sim side** is Gazebo and the
world and **not one ROS process**, so it joins no DDS domain at all. The
**vehicle image** is one command reading one per-vehicle config, starting the
seventeen processes a forklift's own computer would run — gz bridges including
`/clock`, sensor TF, wheel odometry, the gyro gate, the EKF, map server and
AMCL, the full Nav2 stack, the envelope gate, the converter and `forklift_io`
— inside **that vehicle's own DDS domain**.

The five things the brief asked to be shown, all in
`agv/forklift/EVIDENCE_VEHICLE_IMAGE.md`, one run, 2026-08-05, machine
verified clear first:

| | Result |
|---|---|
| **1. from a different domain, no `/forklift` topic** | **Shown, three times.** Domains 0, 10 and 52, `ros2 topic list --no-daemon --spin-time 5`: `/parameter_events` and `/rosout` — the querying process's own two — and nothing else. `ros2 node list`: empty. The contract checker in `--expect-absent` mode: 0 of 29 rows present, PASS (§3) |
| **2. inside the domain, the whole contract** | **29 of 29 contract rows on the wire, 0 missing**, diffed by `check_contract_topics.py` against README's own table. 23 nodes, seven managed ones all `active [3]`, `/tf` publisher count **2** on two disjoint edges (`forklift_ekf`, `amcl`) (§4) |
| **3. a Nav2 goal ACCEPTED** | **ACCEPTED.** It then aborted (`error_code 104`) without completing — reported, not tuned; see open question 1 (§5) |
| **4. m5-11 §7 residual `0.000e+00`** | **`0.000e+00`, 220 of 220 pairs exact**, run inside the vehicle image. Latency mean 0.0005 s / max 0.0011 s, reported as one draw and not as a bound (§6) |
| **5. both compatibility recipes** | **Both run.** `gate:=false cmd_topic:=/cmd_vel_smoothed` came up Nav2-active with the gate absent and SmacPlannerHybrid loaded; the m5-11 envelope chain came up and gave `0.000e+00`, 220 of 220 (§7) |

Identity is injected and the injection refuses rather than guesses:
`vehicle_identity.py --self-check` exercises eight ways of getting the
allocation wrong — unallocated serial, duplicate domain, ID outside the safe
0–101 range, operator domain inside the vehicle band, a per-vehicle file
carrying its own domain — and each is a refusal before any process starts.
`vehicle_image.launch.py` additionally refuses to start if the environment it
was handed is not the allocated domain.

**One defect found, in my own composition, before any proof was taken.**
`IncludeLaunchDescription` on Jazzy does not scope launch configurations, and
`DeclareLaunchArgument` applies its default only when the configuration is not
already set. `localization.launch.py` and `navigation.launch.py` both declare
`params_file`, so included in that order **Nav2 was started with
`amcl.yaml`**: `NavfnPlanner` instead of `SmacPlannerHybrid`, `base_link`
instead of `forklift/base_link`, sixty seconds of costmap timeouts and no
error that named the cause. Fixed with one `GroupAction(scoped=True)` per
include, recorded in evidence §1.1, and proposed as a LESSONS entry in §5.

## 2. The one disagreement between the ADR and the brief

**ADR 0016 D2 says the serial → domain allocation table is "one sim-side file
with one owner (the launcher that spawns the fleet)". Brief §3 rules it to
`agv/forklift/vehicles/allocation.yaml`.** The ADR wins on precedence, and I
say so here as instructed. I implemented the **constraint** — exactly one file
owns the mapping, no other file restates a domain ID, one code path reads it —
at the brief's location, for two reasons:

1. `sim/` is not this agent's to write, so the ADR's location was not
   available to me; and
2. at Phase 1 the reader **is** the vehicle image. No fleet launcher exists
   yet, so a sim-side table would mean a vehicle reading a simulation file to
   learn its own identity — which is backwards from the deployment story
   ADR 0016 D5 tells, where the machine's own config is what a real integrator
   installs and the allocation is site infrastructure.

**This is an owner decision, not mine, and ADR 0016 is still `proposed`.**
Either the file moves to `sim/` under a sim brief (and the vehicle image reads
it across the layer boundary), or D2's sentence is amended in the round that
accepts the ADR. Whichever is chosen, the constraint above is what has to
survive, and it is enforced by `vehicle_identity.py` rather than documented.

Reserved as the brief directed: **10** operator/monitoring, **51–54**
vehicles, **F001 = 51**. 52–54 are deliberately *not* written as placeholder
rows — a row means a vehicle exists.

## 3. Requested in `sim/` — precise enough to be a brief

Everything below was worked around from `agv/` and none of it was edited.

1. **`sim/launch/warehouse_world.launch.py` (new) — the sim side.** Starts
   `sim/worlds/warehouse.sdf` on a gz server, headless by default with a `gui`
   argument, and **starts nothing else**: no spawn, no `ros_gz_bridge`, no
   estimator, no vehicle node. Today the evidence run used the bare
   `gz sim -r -s -v 2 sim/worlds/warehouse.sdf`, which is exactly what this
   file should wrap. Its header should say that a vehicle is started
   separately by `agv/forklift/scripts/vehicle_image.py` and that
   `GZ_PARTITION` is the shared boundary while `ROS_DOMAIN_ID` is each
   vehicle's own.
2. **`sim/launch/warehouse_bringup.launch.py` (header only, no behaviour
   change).** It remains the compatibility path — one ROS graph, one ambient
   domain — and both m5-10 and m5-11 recipes still depend on it. Its header
   should name it as such and point at the split shape, so a reader does not
   take it for the current one.
3. **Who owns the spawn, decided before Phase 2.** The vehicle image performs
   its own `ros_gz_sim create` from the pose in `vehicles/<serial>.yaml`, which
   is the analogue of a machine arriving on a floor that already exists. When
   Phase 2 makes the model name and gz topic prefix per-instance values
   (ADR 0016 D4), that spawn either keeps this home or moves to a sim-side
   fleet launcher — the same question as §2 and best answered with it.
4. **`sim/setup/WSL_ENVIRONMENT.md` §12.5 (optional).** Its verified bringup
   recipe is now one of two shapes; the vehicle-image recipe could sit beside
   it so a future session does not read the compatibility path as the only one.

## 4. Open questions

1. **The Nav2 route no longer completes — on either chain, and it is not the
   vehicle image.** The same goal (`EVIDENCE_NAV2.md` §5.1's aisle traverse,
   plan 5.693 m, unchanged) gave: committed **SUCCEEDED in 13.40 s, 0.183 m**;
   today ungated on the untouched m5-10 chain **TIMEOUT at 90 s, 0.628 m, 7
   rotation-in-place refusals**; today in the vehicle image **ABORTED 104 at
   72 s, 2.536 m, 3 refusals**. The untouched chain shows it too, so the
   failure is not introduced here — but the gated run is the worse of the two
   and n = 1 each. A brief that may change tuning should re-measure both,
   with repeats, against the m5-21 system-package stack (which also moved the
   §7 latency by up to 60x). **This brief was forbidden to change any Nav2,
   AMCL, EKF or smoother value and did not.**
2. **`obstacle_zone.py` now runs in a navigation-capable stack for the first
   time.** `warehouse_bringup` deliberately does not start it; the vehicle
   image does, because it is one of the vehicle's own process nodes. Nothing
   consumes its output and no costmap sees it, so the expected effect is none
   — but it is a difference from the shape every prior Nav2 measurement was
   taken in, and it is named rather than left for someone to find.
3. **A LESSONS entry is owed** (I cannot write that file): *2026-08-05 | Two
   launch files were included one after the other and both declared
   `params_file` | `IncludeLaunchDescription` does not scope launch
   configurations and `DeclareLaunchArgument` skips its default when the
   configuration is already set, so Nav2 silently ran on `amcl.yaml` — default
   planner, default base frame, no error | Wrap every include in
   `GroupAction(..., scoped=True)`, and check what a stack says it LOADED
   rather than that it started.*
4. **The initial pose is a derived duplicate.** `vehicles/F001.yaml` carries
   the spawn pose (world frame, owned) and the initial pose (map frame,
   derived from it by `localization_run.py map-pose` under the committed
   registration). The derivation is recorded in the file with its command and
   date, but nothing re-checks it: move the spawn pose or rebuild the map and
   the second value ages quietly. A check could be added to
   `vehicle_identity.py` at the cost of making it read the registration.
5. **The envelope still comes from the double, inside the vehicle's own
   domain.** That is not the crossing the bridge will be (ADR 0016 D3b). Until
   the bridge gains its per-vehicle vehicle-facing endpoint, no run has
   exercised supervision *across* the boundary this brief drew.
6. **Nothing here measured cost.** The 17 processes were not profiled, so
   ADR 0016 §3's 2.8-core / 1.17 GB figure is unchanged and unconfirmed by
   this run.

## 5. Scope

`model.sdf` untouched. No second vehicle, no container, no dependency added
(everything imports `yaml`, `rclpy` and the standard library). Nothing outside
`agv/` was written except this report. Nothing was committed and no branch was
created; the working tree carries the eight paths listed at the top.
