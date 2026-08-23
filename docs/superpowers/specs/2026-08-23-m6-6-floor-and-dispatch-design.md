# M6.6 — a floor the fleet can work, and work to do on it

    date:     2026-08-23
    scope:    m6/ only. Nothing under m5_ver2/, agv/, bridge/, fleet/, hmi/,
              sim/ or viz/ is edited.
    owner:    approved 2026-08-23 (hall size, two road classes, auto-RESET)
    replaces: nothing. warehouse_ver2.sdf stays in the tree, frozen.

---

## 1. Why

The M6 acceptance recording shows four trucks that barely leave their
corner of a 30 x 20 m hall. Three causes were measured, not guessed:

1. **The spawn poses divide the floor on purpose.** `ipc/status_contract.py`
   lines 65-81 say so in as many words: "Every station has a truck within
   8.60 m and no truck has to cross the hall to start a transport it is
   chosen for." Combined with `fleet_core.nearest_idle`, each truck serves
   its own quarter and nothing else.
2. **Work only arrives by hand.** The single entry point is
   `fleet_cli.py submit FROM TO`. The acceptance run moved **144.2 m in
   1024 s at 0.176 transports/min** because that is how many transports
   were typed.
3. **The main aisle runs at 0.30 m/s, not 0.70.** The aisle gives a
   fork-corner safety scanner **2.79 m** of lateral clearance against a
   **2.70 m** re-clear threshold — nine centimetres — so
   `follower.FIELD_SLOW_M` holds the truck at the creep ceiling for the
   whole of every main-aisle transit rather than let the field take
   `V_Limit` away under wheels doing 0.7 m/s. `PROOF.md` residual 4 names
   it an owner call and says "the real fix is the floor."

This spec is that fix, plus the work to drive on it.

**Out of scope, deliberately:** Nav2, AMCL/SLAM, RViz, and local obstacle
avoidance. The autopilot stays pure pursuit over the graph router. Those
are separate pieces of work and mixing them in would make every number
below unattributable.

---

## 2. What isolates this change

`m6/ipc/stations.py` and `m6/gazebo/warehouse_ver2.sdf` are **byte-identical
copies** of step 5's files, not shared ones (md5 `67efbeb4...` and
`5ba18a00...`, verified 2026-08-23 across both paths). m6 owns its copies.

Therefore: **every measured figure in `m5_ver2/step5/PROOF.md` and in
M5's videos stays valid.** Only M6's own numbers are re-measured, and
`m6/PROOF.md` gains a new section rather than losing its old ones.

---

## 3. The floor — `m6/gazebo/warehouse_ver3.sdf`

### 3.1 The rule that sizes every corridor

A truck runs at `CRUISE_MPS` (0.70) only where every safety scanner is
further than `follower.FIELD_SLOW_M` (**3.30 m**) from anything. The
fork-corner devices sit at model (-0.68, **±0.46**), so for a truck on a
corridor centreline:

    clearance = corridor_clear_width / 2 - 0.46

Setting that at or above 3.30 gives a **minimum cruise corridor of
7.52 m**. Everything narrower is a creep corridor by construction, and
that is not a defect — it is how the two road classes are defined.

### 3.2 Two road classes

| Class | Clear width | Scanner clearance | Margin over threshold | Speed |
|---|---|---|---|---|
| **Highway** (ring + spine) | 8.00 m | 3.54 m | +0.24 m over 3.30 | 0.70 m/s |
| **Pick aisle** | 5.00 m | 2.04 m | +0.84 m over PF+hyst 1.20 | 0.30 m/s |

A pick aisle is inside the 2.50 m warning field on purpose. The truck
reaches it already at creep, because `FIELD_SLOW_M` (3.30) fires before
`WF` (2.50) drops — which is the whole point of that band and the reason
it exists (`follower.target_speed`, measured 2026-08-22 22:40:28).

### 3.3 Geometry, on a 0.50 m grid

Hall shell, inner wall faces: **x = ±24.00, y in [-18.00, +14.00]**
(48 x 32 m, 1536 m², against 600 m² today — **2.56x**). The hall is not
centred on y: the southern 4.00 m strip is a **dock annex**, a solid
block with four bays cut through it (§3.4).

    RING   centrelines  x = -20.00, x = +20.00, y = -10.00, y = +10.00
           bands        8.00 m wide; wall side 4.00 m, block side 4.00 m
           loop length  2 x (40.00 + 20.00) = 120.00 m

    SPINE  centreline   x = 0.00,  band x in [-4.00, +4.00],  8.00 m
           runs         y = -10.00 to y = +10.00

    PICK   centreline   y = 0.00,  band y in [-2.50, +2.50],  5.00 m
           runs         x = -20.00 to x = +20.00 (crosses the spine)

    BLOCKS inner area   x in [-16.00, 16.00], y in [-6.00, 6.00]
           west block   x in [-16.00, -4.00]   east block  x in [4.00, 16.00]
           north racks  y in [ 2.50,  6.00]    3.50 m deep, back to back
           south racks  y in [-6.00, -2.50]    3.50 m deep, back to back

    ANNEX  block        x in [-24.00, 24.00], y in [-18.00, -14.00]
           four bays    4.00 m wide, cut through, mouths on the south
                        ring leg's wall side

### 3.4 Bays — the only way a station is reached

**Every station is entered down a spur of at least 2.50 m, so every
station declares `arrive_m` 0.25.** This is the point of the redesign
and it retires `PROOF.md` residual 6 (the minimum-turning-radius orbit)
by geometry rather than by tolerance: the measured rule is that a 0.85 m
spur cannot be hit by any gain and a 2.50-3.00 m spur is hit at 0.25 m
(S4 and S10 prove both halves today).

Two standoffs govern a bay, and they are different numbers because they
guard different devices:

    AHEAD  2.50 m to the face the truck drives at, and every bay is
           drawn to give 2.60. 0.80 scanner offset + 1.00 PF + 0.20
           hysteresis + 0.50 margin. (stations.py derives 2.40 today.
           The floor gives 0.10 m over the threshold on purpose: at
           exactly 2.50 the assertion sits on a float knife-edge and
           -15.40 - -17.90 evaluates to 2.4999999999999982.)
    ABEAM  1.66 m to each wall beside the truck.
           1.00 PF + 0.20 hysteresis + 0.46 scanner mount offset.
           A 4.00 m wide bay gives 2.00 m — 0.34 m of margin.

**Pick bays** — 4.00 m wide, cut through a 3.50 m rack row:

    bay mouth      y = ±2.50 (the pick aisle edge)
    back panel     y in ±[5.90, 6.00]; the face the truck sees is ±5.90
    station centre y = ±3.30          (= 5.90 - 2.60)
    spur           3.30 m from the pick-aisle centreline      >= 2.50 OK
    parked truck   y in [2.10, 4.50] — 0.40 m of tail at the mouth

**Annex bays** — 4.00 m wide, cut through the 4.00 m annex block:

    bay mouth      y = -14.00 (the south ring leg's wall side)
    back panel     y in [-18.00, -17.90]; the face is -17.90
    station centre y = -15.30         (= -17.90 + 2.60)
    spur           5.30 m from the south ring centreline      >= 2.50 OK
    parked truck   y in [-16.50, -14.10] — fully inside the bay

The annex bays are 4.00 m deep for exactly that last line. A shallower
recess parks the truck out in the ring band, where a passer-by on the
centreline clears it by 1.34 m — 0.14 m over PF+hysteresis. That is
`PROOF.md` residual 3 rebuilt from scratch, and the depth is what
prevents it.

### 3.5 The twelve stations

| id | name | x | y | yaw | spur | reached from |
|---|---|---|---|---|---|---|
| S1 | PICK-NW-1 | -13.00 | +3.30 | +π/2 | 3.30 | pick aisle |
| S2 | PICK-NW-2 | -7.00 | +3.30 | +π/2 | 3.30 | pick aisle |
| S3 | PICK-SW-1 | -13.00 | -3.30 | -π/2 | 3.30 | pick aisle |
| S4 | PICK-SW-2 | -7.00 | -3.30 | -π/2 | 3.30 | pick aisle |
| S5 | PICK-NE-1 | +7.00 | +3.30 | +π/2 | 3.30 | pick aisle |
| S6 | PICK-NE-2 | +13.00 | +3.30 | +π/2 | 3.30 | pick aisle |
| S7 | PICK-SE-1 | +7.00 | -3.30 | -π/2 | 3.30 | pick aisle |
| S8 | PICK-SE-2 | +13.00 | -3.30 | -π/2 | 3.30 | pick aisle |
| S9 | DOCK-DOOR | -14.00 | -15.30 | -π/2 | 5.30 | south ring leg |
| S10 | CHARGE-1 | -6.00 | -15.30 | -π/2 | 5.30 | south ring leg |
| S11 | CHARGE-2 | +6.00 | -15.30 | -π/2 | 5.30 | south ring leg |
| S12 | CONVEYOR | +14.00 | -15.30 | -π/2 | 5.30 | south ring leg |

All twelve: `arrive_m` **0.25**.

**The north ring leg (y = +10.00) carries no station.** That is what
makes it the honest place to park the fleet — see §4.2.

### 3.6 The graph — `m6/ipc/route.py`

The router keeps its shape: aisle centrelines only, Dijkstra, one spur
per station, pose prepended by `plan_route`. What changes is the node
table.

    RING_Y   = (-10.00, +10.00)      RING_X = (-20.00, +20.00)
    SPINE_X  = 0.00                  PICK_Y = 0.00

    north ring leg  x in (-20, -12, -6, 0, 6, 12, 20)   at y = +10.00
    south ring leg  x in (-20, -14, -6, 0, 6, 14, 20)   at y = -10.00
    west/east legs  y in (-10, 0, +10)                  at x = ∓20.00
    spine           y in (-10, 0, +10)                  at x = 0.00
    pick aisle      x in (-20, -13, -7, 0, 7, 13, 20)   at y = 0.00
    spurs           (x, ±3.30) - (x, 0.00)   for the eight pick stations
                    (x, -15.30) - (x, -10.00) for the four annex stations

The north leg's node list carries -12, -6, +6 and +12 for one reason:
**those are the four spawn poses (§4.2), and each truck must snap to its
own node.** Four trucks whose nearest node is the same node are four
trucks the traffic ledger will hand one piece of floor to.

Longest single leg on this floor is **45.60 m** — S12 (+14.00, -15.30) to
S1 (-13.00, +3.30): 5.30 spur, 14.00 west along the south ring, 10.00
north up the spine, 13.00 west down the pick aisle, 3.30 spur. Today's
longest is 33.65 m (S2 to S5), so a leg grows by about a third and no
more: the ring and the spine keep everything reachable, which is what
they are for. **Route length is not where the gain is.** The gain is speed
(0.70 against 0.30 on every highway metre), twelve stations spread over
2.56x the floor area, and work that never stops arriving. The measured
target is in §7.

### 3.7 What the world file carries

`warehouse_ver3.sdf` is written to the same rules as ver2 and keeps its
parametric rack table in the header. It carries, and nothing else:

* the 48 x 28 shell with four wall alcoves,
* four rack blocks (3.50 m deep, back-to-back runs) with eight bays cut
  through them,
* the twelve station paints, poses read from `stations.py` and pinned by
  `test_stations_sdf.py`,
* charge-bay and dock-door markings, moved to the new alcoves,
* the conveyor deck, moved to the east alcove,
* physics, plugins and the GUI block from ver2, unchanged,
* one new static model, `OverheadCam` (§6.1).

`stations.OBSTACLES` mirrors the new collision rectangles, as it does
today. The SDF stays the geometric truth; `stations.py` is its shadow.

---

## 4. The work — dispatch and spawns

### 4.1 What is NOT changed, and why

`fleet_core.nearest_idle` and `next_assignment` stay exactly as they are.
A truck finishes a transport **at its dropoff station**, not at a home
pose, so under continuous work the fleet scatters on its own within two
transports. A cost function with fairness terms, or a global matching
over the queue, would add a second planner to reason about and would not
change the recording. YAGNI.

### 4.2 Spawn poses — `ipc/status_contract.py`

The quarter-division goes. The four trucks stand in a row on the **north
ring leg**, which carries no station:

    f1 (-12.00, +10.00)   f2 (-6.00, +10.00)
    f3 ( +6.00, +10.00)   f4 (+12.00, +10.00)    all yaw = travel +x

Spacing is **6.00 m**, and both of its constraints are derived, not
chosen:

* a neighbour's body edge sits 6.00 - 0.46 - 0.52 = **5.02 m** from a
  scanner, outside the 2.70 m re-clear threshold, so four parked trucks
  do not sit in each other's warning fields and none of them starts
  under a reduced `V_Limit`;
* **each pose is its own graph node** (§3.6). `route.nearest_node` and
  `floor._standing_from` both snap a pose to the nearest node, so four
  trucks sharing one nearest node are four trucks the ledger will hand
  one piece of floor to at startup.

`test_fleet_spawn_fairness.py` (new) asserts, over the router, that
**every truck is nearest to at least one station and none is nearest to
more than four** — with ties SHARED, not awarded. The floor is mirror
symmetric about x = 0 and so is the spawn row, so f2 and f3 are exactly
equidistant from every mirrored pair. `fleet_core.nearest_idle` breaks
that tie by serial, deterministically and to the lower one, so a strict
count hands f2 six stations and f3 none and is measuring alphabetical
order rather than the floor. Shared, the row above scores **3.0 each**,
measured. If a future row fails it, the row moves; the assertion is the
contract, not the coordinates.

### 4.3 The work generator — `m6/fleet/work_generator.py` (new, pure)

No MQTT, no ROS, no clock of its own — the same rule the rest of
`fleet/` follows.

    WorkGenerator(stations, route_len_fn, seed, min_len_m=15.0)
      .next_pair()  -> (from_id, to_id)

* Pairs are sampled with weight proportional to route length, so
  cross-hall transports dominate and adjacent-station shuffles are rare.
* `from == to` is rejected; pairs shorter than `min_len_m` are rejected.
* **Seeded and deterministic.** The same seed yields the same sequence,
  which is what lets the GUI take (§6.2) replay the headless take's
  scenario exactly.

### 4.4 The CLI — `fleet_cli.py demo`

    fleet_cli.py demo --duration 600 --in-flight 4 --seed 7 [--dry-run]

Submits through the existing `submit` path — no second wire — whenever
`queued + in flight < --in-flight`. `--dry-run` prints the sequence it
would submit and needs no broker, which is how it is tested.

---

## 5. Auto-RESET during a recording — owner ruling, 2026-08-23

`PROOF.md` residual 10: a protective demand latches and only a panel
RESET clears it. A ten-minute recording with no operator loses a truck
for the rest of the run on the first latch; four latches inside 0.56 s
ended the 0-of-8 acceptance run.

**Ruling: the demo runs with an automatic operator, and it says so.**

* `tools/scripted_writer.py` gains a watchdog: on a latched truck it
  presses RESET over the existing UDP command socket.
* Every press is logged with a timestamp, the vehicle, and the cause the
  fields report gave.
* The press count and its log go into `PROOF.md` beside the run, labelled
  **demo-only automatic operator**. `PROOF.md` already declares
  `scripted_writer` as "the operator is synthetic; the production path
  under test is not", and this extends that sentence rather than
  contradicting it.
* **The nan/stale rule is not touched.** A scan that does not arrive is
  still a violated field. Auto-RESET clears the latch afterwards; it never
  makes a scanner less honest.
* If a run needs more than four presses, the run is investigated before
  it is published.

---

## 6. The recording

### 6.1 Take 1 — headless, overhead camera (the main video)

`warehouse_ver3.sdf` carries a static `OverheadCam` model:

    pose      (0, -2, 38, 0, 1.5708, 0)    looking straight down
    sensor    camera, 1600 x 900, 20 Hz, horizontal fov 1.40 rad
    coverage  2 * 38 * tan(0.70) = 64.0 m wide, 36.0 m tall
    the hall  48.0 m wide, 32.0 m tall, centred on y = -2.00 — it fits

`m6/tools/record_overhead.py` (new) subscribes the bridged
`sensor_msgs/Image`, pipes raw frames into `ffmpeg`, and writes H.264
mp4 at 20 fps. `gz sim` runs `--headless`, so the **0.137 of integrated
RTF the GUI costs** (measured 2026-08-23) is spent on physics and
sensors instead.

### 6.2 Take 2 — GUI, same seed (the short visual cut)

The same `demo --seed 7` scenario, `m6.sh start` without `--headless`,
captured from the WSLg display with `ffmpeg x11grab`. Shorter — a few
transports, not the full run — because it costs the RTF that take 1
protects.

Both files land in `assets/m6-fleet/` beside the existing two.

---

## 7. Acceptance — what makes the recording publishable

Measured off the run itself, not asserted:

1. **Fleet distance ≥ 800 m** over a 10-minute run. The current
   acceptance figure is 144.2 m over 1024 s.
2. **≥ 12 transports completed.**
3. **All four trucks move in every 2-minute window** — no truck parked
   for the whole recording.
4. **Every arrival inside its own `arrive_m`**, which is now 0.25 for all
   twelve stations.
5. **Integrated RTF ≥ 0.40 with a floor ≥ 0.020**, i.e. no scan
   starvation. Measured with `tools/rtf_spike.sh` before and after the
   world change.
6. **Auto-RESET presses logged and ≤ 4.**

If (5) fails on the new world, the one lever pulled is the nav lidar:
**360 samples down to 180**. That is stated here so it is a decision
already made rather than one taken under pressure, and the guard's
`sector_min` reads angles, not indices, so it needs no code change.

---

## 8. Files

**New**

    m6/gazebo/warehouse_ver3.sdf
    m6/fleet/work_generator.py
    m6/tools/record_overhead.py
    m6/tests/test_work_generator.py
    m6/tests/test_fleet_spawn_fairness.py

**Changed**

    m6/ipc/stations.py            HALL, twelve STATIONS, new OBSTACLES
    m6/ipc/route.py               ring + spine + pick-aisle node table
    m6/ipc/status_contract.py     VEHICLES spawn poses
    m6/gazebo/m6_world.launch.py  world file, camera bridge
    m6/tools/scripted_writer.py   latch watchdog + RESET log
    m6/fleet/fleet_cli.py         `demo` subcommand
    m6/m6.sh                      world name, recorder wiring
    m6/tests/test_stations_sdf.py twelve ids against ver3
    m6/tests/test_route.py        the new graph and the spur rules
    m6/README_m6.md               the floor, the demo command, the takes
    m6/PROOF.md                   a new M6.6 section; nothing removed

**Untouched, and checked by `git status` at the end**

    m5_ver2/**   agv/**   bridge/**   fleet/**   hmi/**   sim/**   viz/**
    m6/gazebo/warehouse_ver2.sdf   (frozen, kept for the archived runs)

---

## 9. Testing

The m6 suite is 485 tests today and must be green at the end.

**Re-pinned:** `test_stations_sdf.py` (twelve ids, ver3 paint),
`test_route.py` (the new graph). `test_follower.py` constants are
unchanged and must stay unchanged — if a follower constant has to move to
make this floor work, the floor is wrong, not the constant.

**New assertions, written against the rules rather than the numbers:**

* every station's spur ≥ 2.50 m, and therefore every `arrive_m` = 0.25
* every highway centreline gives ≥ 3.30 m of scanner clearance
* every pick-aisle centreline gives ≥ 1.20 m of scanner clearance
* every bay centreline gives ≥ 1.20 m of scanner clearance from both walls
* no graph node lies inside an `OBSTACLES` rectangle
* `stations.OBSTACLES` matches `warehouse_ver3.sdf`'s collision rectangles
* no truck is the nearest to more than four of the twelve stations
* the work generator is deterministic under a seed, emits no self-pair,
  and emits no pair shorter than `min_len_m`

---

## 10. Risks

1. **RTF on a larger, denser world.** Mitigated by measuring with
   `rtf_spike.sh` before the stack is brought up, and by the pre-agreed
   nav-lidar lever in §7.
2. **The pick aisle is one lane.** Two trucks cannot pass in a 5.00 m
   aisle; the traffic ledger serialises it and the second truck waits or
   steps aside. This is accepted — it is correct behaviour and it is
   worth seeing on the recording.
3. **A pick-bay truck leaves 0.40 m of tail at the mouth** (y = 2.10
   against a mouth at 2.50), because a 3.50 m rack row is as deep as the
   inner block allows. A passer-by in the same aisle sees it in a warning
   field and creeps; it never sees it in a protective one. The ledger
   prevents the fleet from routing one there while the other holds it.
   The four ANNEX bays are 4.00 m deep and have no tail at all.
4. **The spawn row still leans east/west** for the first four
   assignments. It washes out after two transports because trucks end at
   their dropoff. `test_fleet_spawn_fairness` bounds how far it can lean.
