# EVIDENCE — warehouse world bringup (m5-08)

The M5 autonomy world (`worlds/warehouse.sdf`) loads, spawns the in-house
forklift and puts its topics on the ROS graph. Captured before any SLAM or
Nav2 work, so that the autonomy briefs start from a world that is known to
run rather than from one that is assumed to.

The landmark availability of this world — where localisation will be strong
and where it will be weak — is a separate document: `WAREHOUSE_LANDMARKS.md`.

| Item | Value |
|---|---|
| Date | **2026-07-31** |
| Under test | `sim/worlds/warehouse.sdf` and `sim/launch/warehouse_bringup.launch.py` as committed by this change |
| Vehicle | `agv/forklift/model.sdf`, unmodified and not read for anything but its declared sensor and geometry values |
| Host | project container, Ubuntu 24.04, kernel 6.18.5 |
| Gazebo | `gz sim 8.11.0` (Harmonic), headless, ogre2 on llvmpipe |
| ROS 2 | Jazzy |
| Transport isolation | `GZ_PARTITION=m5-08-warehouse` **and** `ROS_DOMAIN_ID=57`. Both, because gz transport does not use DDS and `ROS_DOMAIN_ID` alone does not isolate a simulation (docs/LESSONS.md 2026-07-27) |
| Machine state | **shared**. Another agent was running a simulator in `agv/` during this capture |

## 0. What this file does NOT claim

**No real-time factor and no timing figure.** The machine was shared for the
whole of this capture, and a contended RTF is worthless
(docs/LESSONS.md 2026-07-30). The rates in section 3 are recorded as
evidence that data flows at the rate the sensors declare; they are not a
performance measurement, and an RTF figure for this world on an uncontended
machine is **owed**, because this world carries substantially more geometry
than the M4 arena that the existing figures were taken in.

**No GUI capture.** The `VisualizeLidar` block is present in the world file
and follows the arena's pattern, but no GUI was started in this run, so the
beams were not seen here. The arena's measured GUI findings
(`FORKLIFT_ARENA_EVIDENCE.md` section 9) are the reference and were not
re-taken.

**Nothing about SLAM, Nav2, the PLC, the bridge or the HMI.** This launch
puts a plant and a vehicle on the wire and stops there.

## 1. The world loads and the model list is what the file says

`gz model --list` against the running server, after the spawn:

```
Available models:
    - Floor
    - WallNorth
    - WallSouthWest
    - WallSouthEast
    - WallEast
    - WallWest
    - DoorGap
    - RackRowA_West
    - RackRowA_East
    - RackRowB_West
    - RackRowB_East
    - RackRowC_West
    - RackRowC_East
    - BuildingColumns
    - ConveyorStation
    - TransferStationFrame
    - ChargeBay1Marking
    - ChargeBay1Cabinet
    - ChargeBay2Marking
    - ChargeBay2Cabinet
    - SafetyZoneMarking
    - Forklift
```

21 world models plus the spawned vehicle. `gz sdf -k worlds/warehouse.sdf`
reports `Valid.`

Geometry count, from the file: **196 collisions and 208 visuals**, of which
one of each is the floor plane and the rest are boxes — so 195 box
collisions against 207 box visuals. The excess 12 visuals are the three
painted outlines (4 strips each), which have no collision because paint is
not an obstacle.

An overlap check over the 195 collision boxes finds six intersecting pairs
and all six are intended: the dock door's two posts and its lintel are set
into the south wall segments, and the transfer station frame's header meets
its own two posts. Both are static-to-static, so no contact is solved for
either.

The only warnings in the whole launch log are three `gz_frame_id` notices
from the vehicle model, which are the same three the arena bringup produces
and are a known sdformat schema complaint, not an error. No `[ERROR]` line
and no `process has died` line appears in the log.

## 2. The vehicle spawns and its topics are bridged

Spawn pose `(-6.00, -5.50, 0.05)`, yaw 0: the dock aisle, west half.

`ros2 topic list`:

```
/clock
/forklift/gz/fork_cmd
/forklift/gz/steer_cmd
/forklift/gz/traction_cmd
/forklift/joint_states
/forklift/odom
/forklift/safety_scanner_front/measurement
/forklift/scan
/parameter_events
/rosout
```

That is the M4 contract table exactly (`agv/forklift/README.md`), which is
the point of this launch including `forklift_bringup.launch.py` rather than
restating it: the rear safety scanner's measurement channel is absent here
for the same documented reason it is absent there.

## 3. Data actually arrives (`ros2 topic hz`)

A bridge entry for a gz topic nobody publishes logs `Creating GZ->ROS Bridge`
exactly as a working one does, so the check is the rate, never the log.

```
=== ros2 topic hz /forklift/scan (45 s window) ===
average rate: 9.991
	min: 0.094s max: 0.105s std dev: 0.00301s window: 11
average rate: 9.961
	min: 0.094s max: 0.106s std dev: 0.00256s window: 21
average rate: 9.984
	min: 0.094s max: 0.106s std dev: 0.00239s window: 32
average rate: 9.983
	min: 0.094s max: 0.106s std dev: 0.00216s window: 42

=== ros2 topic hz /forklift/odom (45 s window) ===
average rate: 20.000
	min: 0.049s max: 0.052s std dev: 0.00061s window: 22
average rate: 19.939
	min: 0.049s max: 0.055s std dev: 0.00093s window: 42
average rate: 19.960
	min: 0.049s max: 0.055s std dev: 0.00077s window: 63
average rate: 19.971
	min: 0.049s max: 0.055s std dev: 0.00067s window: 84
```

The navigation lidar declares 10 Hz and the odometry publisher 20 Hz, and
both arrive at that rate in **wall** time.

Read that carefully. `ros2 topic hz` measures wall-clock arrival, so a
simulation running well behind real time would show a proportionally lower
rate here. It did not. That is *consistent with* this world keeping up with
real time in this window, and it is **not** a real-time-factor measurement:
see section 0.

## 4. Scan message fields, and one that matters

From a captured `/forklift/scan` message:

```
frame_id           nav_lidar_link
angle_min          -3.1415927410125732
angle_max          +3.1415927410125732
angle_increment     0.017501909285783768
range_min          0.10000000149011612
range_max          8.0
n ranges           360
```

`angle_increment` is `2*pi/359`, not `2*pi/360`: gz spreads `samples` rays
**inclusively** over `[min, max]`, so the first and last ray coincide at
`+-pi` and the spacing is 1.0028 deg rather than 1.0000 deg. Anything that
reconstructs bearings from `angle_min` and a computed increment, rather than
from the message's own `angle_increment`, accumulates half a degree of error
by the far side of the sweep. `scenarios/tools/landmark_map.py` uses the
same convention and this message is what confirmed it.

`frame_id` is `nav_lidar_link`, i.e. the `gz_frame_id` of the model reaches
the ROS message intact through this launch.

## 5. Charging bay register

**This section is the citable one.** A later fleet brief that needs the
parking targets reads the table below and does not re-measure the SDF.

| Name | Kind | Centre (x, y) | Size (x, y, z) | Extent |
|---|---|---|---|---|
| `ChargeBay1Marking` | painted outline, no collision | (-9.80, -7.70) | 1.80 x 3.20 x 0.006 | x in [-10.70, -8.90], y in [-9.30, -6.10] |
| `ChargeBay1Cabinet` | solid, collides | (-9.80, -9.675) | 0.90 x 0.65 x 2.00 | x in [-10.25, -9.35], y in [-10.00, -9.35] |
| `ChargeBay2Marking` | painted outline, no collision | (-7.40, -7.70) | 1.80 x 3.20 x 0.006 | x in [-8.30, -6.50], y in [-9.30, -6.10] |
| `ChargeBay2Cabinet` | solid, collides | (-7.40, -9.675) | 0.90 x 0.65 x 2.00 | x in [-7.85, -6.95], y in [-10.00, -9.35] |

Both bays stand in the dock apron against the south wall, west of the dock
door approach. The two outlines are 0.60 m apart. Each cabinet's back face
is on the south wall's inner face at y = -10.00 and its front face is at
y = -9.35, which is 0.05 m from its bay outline's near edge.

**Which vehicle dimension the bay was sized from, and why.** Not the
`1.40 x 0.90` chassis box: that box is only the body shell. The vehicle's
real plan envelope, read from `agv/forklift/model.sdf` with the forks
lowered and the steering straight, is

| Extreme | Value | What it is |
|---|---|---|
| x min | -1.875 | the fork tines |
| x max | +0.860 | the counterweight |
| y min | -0.520 | the rear safety scanner bracket |
| y max | +0.520 | the front safety scanner bracket |

so **2.735 m long by 1.040 m wide**. Using the chassis box would have
understated the length by 1.335 m and the vehicle would have overhung its
own bay by more than a metre of forks. A 3.20 x 1.80 outline holds the real
envelope with **0.23 m at each end and 0.38 m at each side**.

**The bay's long axis is y, so a vehicle parks along y**, heading +y or -y
(yaw = +-90 deg). Which end faces the cabinet is a docking decision and
belongs to the later fleet brief; the geometry admits both.

Checked rather than asserted: a `1.040 x 2.735` envelope centred on each
bay's centre, swept from the floor to z = 2.10, intersects **no** collision
box in the world. The same check on the launch file's spawn pose
`(-6.00, -5.50)` at yaw 0 is also clear.

**What each part shows at each scan plane.**

| Part | At z = 1.80 (navigation lidar) | At z = 0.15 (safety scanners) |
|---|---|---|
| Marking | nothing. It is 6 mm of paint on the floor | nothing, same reason |
| Cabinet | a 0.90 x 0.65 rectangle, free standing 0.65 m in front of the south wall | the same 0.90 x 0.65 rectangle |

The cabinet is a full-height box, so its footprint is identical at both
planes; what differs is the company it keeps. At 1.80 m it is one of only
four free-standing things in the apron (the two cabinets, the two dock door
posts, and the apron columns); at 0.15 m it stands in front of a wall that
the safety scanner sees anyway at 0.65 m more range.

**Reconciliation with the M3-era `ChargerStation`: it is gone, not kept.**
The old world carried a `ChargerStation` model, a 0.80 x 0.80 x 1.20 block
against the **west** wall at (-14.50, -6.00), written in the m3 round before
any vehicle existed. Two reasons it was removed rather than left beside the
new bays:

1. Two different things called a charger in one world is exactly the
   ambiguity a later fleet brief would trip over.
2. It topped out at z = 1.20, which is **0.60 m below the navigation scan
   plane**, so the vehicle could never have seen it. As a charging *station*
   it was a placeholder that no vehicle could dock with.

`scenarios/tools/make_map.py` referenced it by name in its copied rectangle
list; that list no longer exists (see the note in that file). The only
surviving mentions are in dated historical records — `BRINGUP_EVIDENCE.md`
and two files in `docs/reports/` — which record what the world was on their
date and are correct as history.

## 6. What is owed

| Item | Owed to |
|---|---|
| ~~A real-time-factor figure for this world, taken on an uncontended machine~~ | **ANSWERED 2026-07-31 by m5-08b**, which had the machine to itself: `real_time_factor: 0.99934892417589938` for the bringup alone, and 0.9831 simulation seconds per wall second measured across a 179 s drive with slam_toolbox also running. `WAREHOUSE_SLAM_EVIDENCE.md` section 2 |
| A GUI capture showing the navigation lidar beams in this world | the M5 recording work |
| A decision on which scan plane a STATIC Nav2 map of this world represents | m5-10 (Nav2 configuration) |
