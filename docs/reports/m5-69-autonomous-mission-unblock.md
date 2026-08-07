# m5-69 — make an autonomous mission run

    brief:               docs/briefs/m5-69-autonomous-mission-unblock.md
    status:              done
    invariants_touched:  none

## The one-line answer

**The mission drives.** The defect was geometry and it is fixed as geometry:
the committed spawn stood **1.00 m outside the mapped free space**, so
`SmacPlannerHybrid` refused it in **14 ms** with `205 START_OCCUPIED`. Moving
the vehicle 3.00 m further into the building gives **5 of 5 on a 4.00 m dock
leg** and **5 of 5 on a 12.24 m lane leg** — 16 missions driven in all,
`allow_unknown` still `false` and no parameter touched. The second problem
does **not** reproduce: at **3.5 x CPU oversubscription** the stack survives
intact, **`/proc/vmstat oom_kill` is 0 across the guest's whole 4-day uptime**,
and what load actually does is make bring-up take **up to 6.1 x longer** — which
a fixed wait turns into "the action server had gone" without a single process
dying.

## The rates, which are the deliverable

| route | plan | corridor min clearance | poses below the inscribed radius | **rate** | elapsed |
|---|---|---|---|---|---|
| **the committed spawn**, any goal | refused | — | — | **0 of 1**, `205 START_OCCUPIED` | 0.04 s |
| **A** — (-3.0,-5.5) → (+1.0,-5.5) | 4.000 m, 0 cusps | 0.650 m, at the terminus | 2 of 51 | **5 of 5** | 8.46–8.71 s |
| **B** — (-3.0,-5.5) → (+10.0,-5.5) | 13.442 m, 0 cusps | 0.500 m, mid-route | 13 of 157 | **0 of 5** | aborts at 10.6–34.4 s |
| **G** — (-3.0,-5.5) → (+9.0,-7.0) | 12.237 m, 0 cusps | 0.950 m | 0 of 143 | **5 of 5** | 21.46–21.96 s |

Route A elapsed spread **0.25 s** over 5, route G **0.50 s** over 5. This is
not `EVIDENCE_NAV2` §8.6's distribution straddling a criterion: the routes that
pass pass every time and the route that fails fails every time.

**Recommended showcase mission: route G** — 12.24 m, **21.7 s of continuous
driving**, mean 0.55 m/s, which is the window a safety intrusion needs. Route A
is the short alternative.

## The three findings, in the order they matter

**1. The spawn was outside the map, not at the corner of the image.** 21.6 % of
the committed grid is unmapped. At world (-6.00, -5.50) **36 of the 191 padded
footprint outline cells are UNKNOWN and 0 are lethal** — the pose is blocked by
ignorance, not by an obstacle — and the inscribed clearance is **0.430 m**
against a **0.769 m** inscribed radius, so it is invalid at **55 of 72
headings** and fits at none. Mapped free space in that aisle begins at
x = -5.00. The fix is `_SPAWN_X = '-6.00' -> '-3.00'`, chosen for **2.00 m of
margin** against §8.6's measured 0.661 m localisation excursions, not for the
shortest move that works.

**2. m5-68's GOAL was invalid too, independently — a defect the diagnosis did
not contain.** World (-1.00, -3.00) has **0.765 m of clearance against a
0.769 m inscribed radius**, under it by 4 mm, and the planner searches it to
`207 TIMEOUT` — 145 x the cost of a route that works. **Had only the spawn been
moved, the mission would have failed again for a reason nobody was looking
for.**

**3. THE MOST IMPORTANT FINDING, and it is not the spawn.** nav2 checks the
footprint's **outline** and never its interior. This vehicle's padded footprint
is **3.275 m long**, so an obstacle can sit entirely inside it and be invisible
to the planner and the controller alike. Route B is that defect arriving in a
drive: the planner emitted a plan **13 of whose 157 poses have less clearance
than the vehicle's inscribed circle**, and the vehicle drove it until it
wedged — twice replanning from a pose the planner then refused as
`START_OCCUPIED`. **It bounds every "cannot collide" claim the project makes
about the process layer.** It does not touch the safety layer, which is onboard
and hardwired and reads no costmap. nav2 warns about the same thing at every
plan: `inflation radius (0.550000) is smaller than the circumscribed radius
(2.230050)`.

The corridor-width screen this produced was **registered as a prediction before
route G was driven** ("at least 3 of 5, because length is not what killed B,
corridor width is"). It scored 5 of 5.

## The action-server death — three hypotheses, all three killed

The coordinator's ruling makes this the more valuable half, so it is stated in
full.

| K burners | peak load1 (20 cores) | repeats | rate | launches alive after | `/navigate_to_pose` after |
|---|---|---|---|---|---|
| 0 | 3.72–7.85 | 10 | 10 of 10 | 3 of 3 every repeat | present every repeat |
| 20 | 24.96–28.95 | 3 | 3 of 3 | 3 of 3 every repeat | present every repeat |
| 60 | **65.11–70.21** | 3 | 3 of 3 | 3 of 3 every repeat | present every repeat |

- **OOM killer — falsified outright.** `/proc/vmstat oom_kill 0`, a monotonic
  counter, against `uptime -s 2026-08-03` — **4 days 3 h spanning m5-68's own
  session**. The kernel has never OOM-killed anything in this guest.
- **Memory starvation short of a kill — falsified with the margin.** Stack
  resident set **1660–1683 MB** across all 19 runs; available memory never
  below **13 000 MB** of 15 808 MB. The stack uses 11 % of the guest.
- **CPU contention — falsified as a kill, and this is where the finding is.**
  What load does is stretch bring-up: navigation advertises `/plan` in
  **15–18 s** unloaded, **36–50 s** at K = 20, **74–97 s** at K = 60. **6.1 x.**
  A procedure that waits a fixed interval then sends a goal reports exactly what
  m5-68 reported. The server had not gone; it had not arrived.

**And the log signature m5-68 read is not evidence of a death.** Every
navigation log here — including the ten whose stack the driver verified alive
and serving in the same second — ends with `user interrupted with ctrl-c
(SIGINT)` and `process has died ... exit code -2`. **`exit code -2` is SIGINT:
a deliberate teardown and a crash write the identical log.** This is the
stopped-contactor lesson (2026-08-06) in a different layer.

I did not have m5-68's logs and make **no claim** about what ended its
processes. What is established is that the three mechanisms usually blamed did
not do it here, and that the one reproducible effect of load needs no process
to die.

## files_changed

| File | What |
|---|---|
| `sim/launch/warehouse_bringup.launch.py` | **THE FIX**, under the owner-approved scope grant, named as the brief requires. `_SPAWN_X` `-6.00` → `-3.00`; `_SPAWN_Y` unchanged. The comment that justified -6.00 was **answered rather than deleted** — its reasoning is still true of the world, and the point is that Nav2 plans against the grid, not against `warehouse.sdf` |
| `agv/forklift/EVIDENCE_NAV2.md` | **New section 13** (13.1 geometry, 13.2 planner bench, 13.3 the fix, 13.4 the driven rates, 13.5 the load experiment, 13.6 what it asks, 13.7 how it was run). Every figure states its n |
| `agv/forklift/scripts/start_pose_check.py` | **New.** Answers "does the grid cover this pose" using the planner's own rule — the **outline** of the **padded** footprint, traced by Bresenham, with the polygon and the padding **parsed out of `nav2.yaml`** so the tool cannot disagree with the planner. Subcommands `coverage`, `pose`, `scan`, `path`, `component`. Its distance transform is written out rather than imported, because `scipy` here is built against numpy 1.x and the interpreter carries 2.4.2 — **no dependency added** |
| `agv/forklift/scripts/mission_repeat.py` | **New.** Drives one mission N times and reports the rate. Closes §8.7 item 5. Per repeat: refuses unless the machine is alone (sweep excluded from itself), isolates `GZ_PARTITION` **and** `ROS_DOMAIN_ID`, gates each bring-up stage on a topic **carrying a message** — and on the `map -> forklift/odom` **transform** for AMCL, which is distance-triggered and publishes nothing standing — samples load/memory/RSS at 1 Hz, refuses to overwrite an existing artefact, tears down to a verified zero, and rewrites its summary after **every** repeat |
| `agv/forklift/evidence/m5-69-*` | **160 files.** 19 runs × {`run.txt`, `run.csv`, `plan.json`, `machine.csv`, `sim.log`, `localization.log`, `navigation.log`} plus 6 sweep summaries |

**Byte-identical, and deliberately so:** `nav2.yaml`, `amcl.yaml`, `ekf.yaml`,
`config.yaml`, the behaviour tree, `model.sdf`, `cmd_vel_to_tricycle.py`,
`nav2_run.py` and both `agv/forklift/launch/` files. **`allow_unknown: false`,
`xy_goal_tolerance: 0.25`, `yaw_goal_tolerance: 0.15`,
`footprint_padding: 0.27` and `inflation_radius: 0.55` are untouched.** `plc/`,
`bridge/` and `hmi/` were neither read from nor written to. **Nothing
committed, no branch, no dependency, and no PL, Category, SIL or PFH is
claimed or implied anywhere.**

## The machine, left clean — verified, not asserted

```
processes matching the autonomy pattern (sweep excluded from itself):  NONE
ros2 daemon:                                                           NONE
listening TCP:   127.0.0.1:5345 and three systemd-resolved :53 only
/dev/shm:        948 entries -> 2      (Fast-DDS segments swept)
load/memory:     1523 MB used of 15808, 14285 MB available
oom_kill:        0
```

No `gz sim`, no ROS process, no burner, nothing holding the CPU. **The
teleoperation hardening run can start from here.**

## Requests — work this brief could not do

| # | Request | Owner | Blocking? |
|---|---|---|---|
| 1 | **Rule on the outline-only collision model.** Either routes are pre-screened for corridor width (`start_pose_check.py path` is a screen, not a fix) **or** `inflation_radius` grows toward the 2.230 m circumscribed radius, which costs planning time. A `nav2.yaml` decision, not this brief's | owner, then `agv/` | No, but it bounds the process-layer collision claim |
| 2 | **A better grid is the real answer to `allow_unknown`.** 21.6 % of the committed map is unmapped; a mapping route covering the south-west corner and the dock aisle's western end would make the original spawn valid with no planner change | `sim/` | No |
| 3 | **`sim/scenarios/warehouse_mapping_route.py` line 99** cites "(-6.00, -5.50)" in a parenthetical. Its live claim (the 0.40 m lidar offset matches the spawn's) is still true — y = -5.50 did not move — but the parenthetical is now stale as a spawn reference. Not edited: outside the grant, which covers the spawn definition only | `sim/` | No |
| 4 | **`agv/forklift/evidence/field_evaluation/field-evaluation-20260807T064053Z-pid265966.log`** — m5-68 left this for `agv/` to rule on. It is a genuine artefact of a committed node in that session and was **left in place, untouched**; whether it is committed is a curation call | orchestrator | No |
| 5 | **`/dev/shm` accumulates DDS segments across runs** (948 by the end of this session, 32 MB of 7.8 GB). Nothing failed because of it; the teardown that removes processes does not remove their segments | `agv/` or infra | No |

## open_questions

1. **What actually ended m5-68's processes is still unknown**, and the three
   mechanisms testable here are all negative. The next session that sees it
   should capture `ps` and the launch's own exit status at the moment, because
   the log cannot distinguish a crash from a SIGINT.
2. **Route G spends 88 % of the heading tolerance** on its worst repeat
   (+7.55 deg of 8.594 deg), against route A's 15 %. §8.7 item 2's approach
   corridor is what buys that back, and any goal moved further along that lane
   will need it.
3. **Nav2's SUCCEEDED is scored against the believed pose.** Route A's truth
   goal error is 0.210–0.307 m; r1 is outside the 0.25 m tolerance in truth and
   inside it in belief. Between a third and a half of that is the map's own
   0.141 m registration floor. Worth saying out loud before a showcase shows a
   distance on screen.
4. **The corridor-width screen rests on n = 3 routes.** Three scores, three
   rates, same order — but that is a screen with three points behind it, not a
   proven predictor.

## next_suggested

Item 5 is now unblocked: run **route G** with an intrusion into the protective
field mid-drive — 21.7 s of driving, 5 of 5 — bringing the autonomy stack up
**first** and waiting for `/plan` rather than for a fixed interval, since that
wait is the one thing load reliably breaks.
