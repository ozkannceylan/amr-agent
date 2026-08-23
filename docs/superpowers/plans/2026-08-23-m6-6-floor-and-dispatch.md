# M6.6 — Floor and Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This plan is written to be executed by Grok in Cursor, not by its
> author.** It assumes no memory of the design conversation. Everything
> needed is either here or in the spec named below. Read the spec once
> before Task 1; do not read it again per task.

**Spec:** `docs/superpowers/specs/2026-08-23-m6-6-floor-and-dispatch-design.md`

**Goal:** Replace M6's 30 x 20 m floor with a 48 x 32 m two-road-class
warehouse whose twelve stations are all reachable to 0.25 m, give the
fleet a work generator so trucks never stand idle, and record two videos
of the result.

**Architecture:** `m6/` owns byte-identical *copies* of step 5's
`stations.py` and `warehouse_ver2.sdf` — they are not shared files. So
this work edits only `m6/`, and every measured figure in
`m5_ver2/step5/PROOF.md` survives untouched. `stations.py` stays the one
home for station poses and obstacle rectangles; `warehouse_ver3.sdf` is
its geometric twin and `test_stations_sdf.py` is the coupling that fails
when they drift. The autopilot (`follower.py`, `nav_core.py`) is **not
edited** — the floor is sized to its existing constants, not the other
way round.

**Tech Stack:** Python 3.12 (plain files, no package, no colcon), ROS 2
Jazzy, Gazebo (gz sim), pytest, paho-mqtt, ffmpeg. Runs under WSL2;
the PLC side runs on Windows.

---

## Global Constraints

- **Scope is `m6/` only.** Nothing under `m5_ver2/`, `agv/`, `bridge/`,
  `fleet/` (repo root), `hmi/` (repo root), `sim/`, `viz/`, `plc/` or
  `m1..m5/` may be edited. Verify with `git status` before every commit.
- **`m6/gazebo/warehouse_ver2.sdf` is frozen.** Do not edit or delete it.
  The new world is a new file, `warehouse_ver3.sdf`.
- **No follower constant may change.** `m6/ipc/follower.py` is not in the
  file list. If the floor appears to need `FIELD_SLOW_M`, `GUARD_SLOW_M`,
  `CRUISE_MPS`, `ARRIVE_M` or a band edge moved, the floor is wrong —
  stop and report, do not tune.
- **The tree is not a package.** Tests reach `fleet/` and `tools/` by
  `sys.path.insert` inside the test file (see the pattern in
  `m6/tests/test_fleet_core.py:14-16`). `conftest.py` already puts
  `ipc/`, `hmi/` and `windows/` on the path — do not add to it.
- **Test command, and the `source` is not optional:**
  ```bash
  cd /mnt/c/Users/ozkan/projects/amr-agent
  source /opt/ros/jazzy/setup.bash
  python3 -m pytest m6/tests/ -q
  ```
  Without the `source`, the suite aborts with `Interrupted: 7 errors
  during collection` and that is not a failure of your change.
- **A skip is a failure.** It means a module did not import. Baseline is
  `485 passed, 0 skipped`.
- **Rig preconditions for any run** (Tasks 9 and 10 only):
  ```bash
  wsl --shutdown            # from Windows, before starting WSL
  export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
  ```
  Every real-time-factor figure in `m6/PROOF.md` was measured with those
  two variables set. A run without them measures a different machine.
- **Commit after every task.** Working branch is `m6`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `m6/ipc/stations.py` | the one home for HALL, the twelve stations, the obstacle rectangles | 1 |
| `m6/tests/test_stations.py` (new) | the station table's own rules: ids, names, radii, standoffs | 1 |
| `m6/ipc/route.py` | the waypoint graph (ring, spine, pick aisle, spurs) and the router | 2 |
| `m6/tests/test_route.py` | the graph's rules, re-pinned to the new floor | 2 |
| `m6/gazebo/warehouse_ver3.sdf` (new) | the geometric truth: shell, racks, bays, annex, paint, overhead camera | 3, 8 |
| `m6/tests/test_stations_sdf.py` | the coupling between the SDF and `stations.py` | 3 |
| `m6/ipc/status_contract.py` | `VEHICLES` spawn poses | 4 |
| `m6/tests/test_fleet_spawn_fairness.py` (new) | no truck owns more than a third of the floor | 4 |
| `m6/fleet/work_generator.py` (new) | seeded station-pair sampling weighted by route length | 5 |
| `m6/tests/test_work_generator.py` (new) | determinism, refusals, weighting | 5 |
| `m6/fleet/fleet_cli.py` | the `demo` subcommand that keeps the queue full | 6 |
| `m6/tools/scripted_writer.py` | the latch watchdog and its RESET log | 7 |
| `m6/tools/record_overhead.py` (new) | overhead camera frames into ffmpeg | 8 |
| `m6/gazebo/m6_world.launch.py` | world file, camera bridge | 8, 9 |
| `m6/hmi/map_panel.py` | canvas sized from HALL instead of hard-coded | 9 |
| `m6/README_m6.md`, `m6/PROOF.md` | the floor, the demo command, the measured run | 10 |

---

## Task 1: The station table

**Files:**
- Modify: `m6/ipc/stations.py` (whole file)
- Test: `m6/tests/test_stations.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `stations.HALL` = `(-24.0, 24.0, -18.0, 14.0)`;
  `stations.STATIONS` — an `OrderedDict` of twelve entries keyed `"S1"`
  through `"S12"`, each a dict with keys `name` (str), `x` (float),
  `y` (float), `yaw` (float), `arrive_m` (float);
  `stations.OBSTACLES` — a tuple of 29 five-tuples
  `(name, xmin, xmax, ymin, ymax)`.
  Task 2 reads `STATIONS` and `OBSTACLES`. Task 3 reads all three.

- [ ] **Step 1: Write the failing test**

Create `m6/tests/test_stations.py`:

```python
"""stations.py's own table. Pure numbers, no graph and no world.

THE TWO STANDOFFS ARE DIFFERENT NUMBERS BECAUSE THEY GUARD DIFFERENT
DEVICES. Ahead is the face the truck drives at: 0.80 m of scanner
offset toward the fork tip, plus case-1 PF 1.00, plus 0.20 hysteresis,
plus margin. Abeam is a wall the truck passes: PF 1.00 + 0.20
hysteresis + the 0.46 m lateral scanner mount offset. A bay 4.00 m wide
gives 2.00 m abeam, which is why 4.00 is the width.
"""
import math

import stations

AHEAD_M = 2.50
ABEAM_M = 1.66


def _gap(station, rect):
    """(dx, dy) from the station point to the rectangle, 0 when inside."""
    _n, xmin, xmax, ymin, ymax = rect
    return (max(xmin - station["x"], 0.0, station["x"] - xmax),
            max(ymin - station["y"], 0.0, station["y"] - ymax))


def test_twelve_stations_with_unique_names():
    assert len(stations.STATIONS) == 12
    names = [s["name"] for s in stations.STATIONS.values()]
    assert len(set(names)) == 12
    assert list(stations.STATIONS) == ["S{}".format(n) for n in range(1, 13)]


def test_every_station_arrives_at_the_tight_radius():
    # The whole point of the redesign: no spur is short enough to need
    # the loosened radius, so nothing declares it.
    for sid, s in stations.STATIONS.items():
        assert s["arrive_m"] == 0.25, sid


def test_every_station_is_inside_the_hall():
    xmin, xmax, ymin, ymax = stations.HALL
    for sid, s in stations.STATIONS.items():
        assert xmin < s["x"] < xmax, sid
        assert ymin < s["y"] < ymax, sid


def test_every_station_keeps_its_ahead_and_abeam_standoffs():
    for sid, s in stations.STATIONS.items():
        along_y = abs(math.sin(s["yaw"])) > 0.5
        for rect in stations.OBSTACLES:
            dx, dy = _gap(s, rect)
            if dx > 0.0 and dy > 0.0:
                continue          # diagonal: neither ahead nor abeam
            ahead, abeam = (dy, dx) if along_y else (dx, dy)
            if abeam == 0.0:
                assert ahead >= AHEAD_M, (sid, rect[0], ahead)
            if ahead == 0.0:
                assert abeam >= ABEAM_M, (sid, rect[0], abeam)


def test_no_station_sits_inside_an_obstacle():
    for sid, s in stations.STATIONS.items():
        for rect in stations.OBSTACLES:
            dx, dy = _gap(s, rect)
            assert dx > 0.0 or dy > 0.0, (sid, rect[0])


def test_obstacle_rectangles_are_well_formed():
    seen = set()
    for name, xmin, xmax, ymin, ymax in stations.OBSTACLES:
        assert xmin < xmax, name
        assert ymin < ymax, name
        assert name not in seen, name
        seen.add(name)
    assert len(stations.OBSTACLES) == 29
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m6/tests/test_stations.py -q
```

Expected: failures on the count (10, not 12) and on the `arrive_m`
assertion (S2, S3, S6-S9 declare 0.80).

- [ ] **Step 3: Rewrite `m6/ipc/stations.py`**

Replace the whole file with this. Keep the module docstring's habit of
saying *why* a number is what it is — the numbers below are derived, and
the derivations are the only defence against someone rounding them.

```python
"""stations.py - the twelve stations and the floor they must keep clear of.

THE ONE HOME for station ids, names, poses and the obstacle rectangles.
The world paint (warehouse_ver3.sdf), the router (route.py) and the HMI
sketch (hmi/map_panel.py) all read from here or are tested against it
(test_stations_sdf.py); a station moved in only one place is a test
failure, not a silent divergence.

yaw is the APPROACH heading - the travel direction on the spur - used to
orient the paint tick, and read by test_stations.py to know which axis is
'ahead'. Arrival is position-only: a tricycle cannot rotate in place.

EVERY STATION DECLARES 0.25 m, AND THAT IS THE POINT OF THIS FLOOR.
Measured 2026-08-13 at the old S7: a truck cannot reach a point inside
its own turning circle, so a 0.85 m spur produced a stable orbit at
0.643-0.742 m and the station had to declare 0.80 m to catch the first
pass. The old S4 (2.5 m spur) and S10 (3.0 m spur) hit 0.25 m. So the
floor is drawn with NO SHORT SPURS: the shortest here is 3.30 m. The
loosened radius is not in this file because nothing on this floor needs
it.

TWO STANDOFFS, NOT ONE, BECAUSE THEY GUARD DIFFERENT DEVICES.
  AHEAD  2.50 m to the face the truck drives at.
         0.80 (the side scanners sit that far toward the fork tip) +
         1.00 (case-1 protective field) + 0.20 (hysteresis) + 0.50.
         Measured 2026-08-13: a 1.5-1.9 m centre standoff parked the
         right scanner 0.99 m off a rack face and tripped case 1 with
         the truck exactly on its lane.
  ABEAM  1.66 m to a wall the truck passes.
         1.00 (PF) + 0.20 (hysteresis) + 0.46 (lateral scanner mount
         offset). A bay 4.00 m wide gives 2.00 m. That is why bays are
         4.00 m wide and not 3.60.

OBSTACLES mirrors warehouse_ver3.sdf's collision rectangles. The SDF
stays the geometric truth; these numbers are its shadow, and
test_stations_sdf.py is what notices a drift.

THE HALL IS NOT CENTRED ON y. The southern strip y in [-18.00, -14.00]
is the dock annex - a solid block with four bays cut through it. Its
bays are 4.00 m deep on purpose: a shallower recess parks the truck out
in the ring band, where a passer-by on the centreline clears it by
1.34 m, which is 0.14 m over PF+hysteresis. That is PROOF.md residual 3
(f1 parked on S1) rebuilt from scratch, and the depth is what prevents
it.
"""
import math
from collections import OrderedDict

HALL = (-24.0, 24.0, -18.0, 14.0)          # inner wall faces: 48 x 32 m

_N, _S = math.pi / 2, -math.pi / 2

STATIONS = OrderedDict((
    # Eight pick bays, 4.00 m wide, cut through the 3.50 m rack rows.
    # Bay mouth at y = +-2.50 (the pick aisle edge), back panel face at
    # +-5.90, so the station sits at +-(5.90 - 2.60) = +-3.30 and the
    # spur from the pick-aisle centreline is 3.30 m. THE BAY IS DRAWN TO
    # 2.60 AND THE THRESHOLD IS 2.50, deliberately: at exactly 2.50 the
    # assertion sits on a float knife-edge - (-15.40) - (-17.90)
    # evaluates to 2.4999999999999982 and fails a >= 2.50 test that is
    # geometrically satisfied. 0.10 m of margin costs nothing and buys
    # an assertion that means what it says.
    ("S1",  {"name": "PICK-NW-1", "x": -13.0, "y":   3.30, "yaw": _N,
             "arrive_m": 0.25}),
    ("S2",  {"name": "PICK-NW-2", "x":  -7.0, "y":   3.30, "yaw": _N,
             "arrive_m": 0.25}),
    ("S3",  {"name": "PICK-SW-1", "x": -13.0, "y":  -3.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S4",  {"name": "PICK-SW-2", "x":  -7.0, "y":  -3.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S5",  {"name": "PICK-NE-1", "x":   7.0, "y":   3.30, "yaw": _N,
             "arrive_m": 0.25}),
    ("S6",  {"name": "PICK-NE-2", "x":  13.0, "y":   3.30, "yaw": _N,
             "arrive_m": 0.25}),
    ("S7",  {"name": "PICK-SE-1", "x":   7.0, "y":  -3.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S8",  {"name": "PICK-SE-2", "x":  13.0, "y":  -3.30, "yaw": _S,
             "arrive_m": 0.25}),
    # Four annex bays, 4.00 m wide and 4.00 m DEEP, cut through the dock
    # annex. Mouth at y = -14.00, back panel face at -17.90, so the
    # station sits at -17.90 + 2.60 = -15.30 and the spur from the south
    # ring centreline (y = -10.00) is 5.30 m. The truck parks entirely
    # inside the bay: y in [-16.50, -14.10].
    ("S9",  {"name": "DOCK-DOOR", "x": -14.0, "y": -15.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S10", {"name": "CHARGE-1",  "x":  -6.0, "y": -15.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S11", {"name": "CHARGE-2",  "x":   6.0, "y": -15.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S12", {"name": "CONVEYOR",  "x":  14.0, "y": -15.30, "yaw": _S,
             "arrive_m": 0.25}),
))

# The rack rows run x in [-16, -4] (west block) and [4, 16] (east block),
# 3.50 m deep at y in +-[2.50, 6.00]. Four 4.00 m bays are cut through
# each side's pair of rows; what is left is the twelve segments below.
# The bay BACK PANELS are separate rectangles because they are the face
# the truck's ahead-standoff is measured against.
OBSTACLES = (
    ("RackNW1",   -16.00, -15.00,   2.50,   6.00),
    ("RackNW2",   -11.00,  -9.00,   2.50,   6.00),
    ("RackNW3",    -5.00,  -4.00,   2.50,   6.00),
    ("RackNE1",     4.00,   5.00,   2.50,   6.00),
    ("RackNE2",     9.00,  11.00,   2.50,   6.00),
    ("RackNE3",    15.00,  16.00,   2.50,   6.00),
    ("RackSW1",   -16.00, -15.00,  -6.00,  -2.50),
    ("RackSW2",   -11.00,  -9.00,  -6.00,  -2.50),
    ("RackSW3",    -5.00,  -4.00,  -6.00,  -2.50),
    ("RackSE1",     4.00,   5.00,  -6.00,  -2.50),
    ("RackSE2",     9.00,  11.00,  -6.00,  -2.50),
    ("RackSE3",    15.00,  16.00,  -6.00,  -2.50),
    ("BayS1Back",  -15.00, -11.00,   5.90,   6.00),
    ("BayS2Back",   -9.00,  -5.00,   5.90,   6.00),
    ("BayS5Back",    5.00,   9.00,   5.90,   6.00),
    ("BayS6Back",   11.00,  15.00,   5.90,   6.00),
    ("BayS3Back",  -15.00, -11.00,  -6.00,  -5.90),
    ("BayS4Back",   -9.00,  -5.00,  -6.00,  -5.90),
    ("BayS7Back",    5.00,   9.00,  -6.00,  -5.90),
    ("BayS8Back",   11.00,  15.00,  -6.00,  -5.90),
    # The dock annex: five solid segments with four bays between them.
    ("AnnexW",     -24.00, -16.00, -18.00, -14.00),
    ("AnnexA",     -12.00,  -8.00, -18.00, -14.00),
    ("AnnexB",      -4.00,   4.00, -18.00, -14.00),
    ("AnnexC",       8.00,  12.00, -18.00, -14.00),
    ("AnnexE",      16.00,  24.00, -18.00, -14.00),
    ("BayS9Back",  -16.00, -12.00, -18.00, -17.90),
    ("BayS10Back",  -8.00,  -4.00, -18.00, -17.90),
    ("BayS11Back",   4.00,   8.00, -18.00, -17.90),
    ("BayS12Back",  12.00,  16.00, -18.00, -17.90),
)
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
python3 -m pytest m6/tests/test_stations.py -q
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add m6/ipc/stations.py m6/tests/test_stations.py
git commit -m "m6.6: twelve stations, none of them down a short spur"
```

The rest of the suite is expected to be RED after this commit —
`test_route.py` and `test_stations_sdf.py` still describe the old floor.
Task 2 and Task 3 fix them. Do not attempt to fix them here.

---

## Task 2: The graph

**Files:**
- Modify: `m6/ipc/route.py` (whole file)
- Test: `m6/tests/test_route.py` (rewrite)

**Interfaces:**
- Consumes: `stations.STATIONS`, `stations.OBSTACLES` (Task 1).
- Produces: `route.build_graph() -> dict[(float,float), set]`,
  `route.dijkstra(graph, start, goal) -> list | None`,
  `route.nearest_node(nodes, xy) -> (float, float)`,
  `route.plan_route(pose_xy, station_id) -> list | None`, and the module
  constants `RING_X`, `RING_Y`, `SPINE_X`, `PICK_Y`, `NORTH_X`,
  `SOUTH_X`, `PICK_X`, `LEG_Y`. `fleet/order_builder.py` and
  `fleet/floor.py` already import `plan_route`, `dijkstra`, `nearest_node`
  and `build_graph`; **those four names and their signatures must not
  change.**

- [ ] **Step 1: Write the failing test**

Replace `m6/tests/test_route.py` entirely:

```python
"""route.py's graph and router. Pure geometry, no ROS.

THE RULES ARE ASSERTED, NOT THE COORDINATES. A test that pins a node
list is a test that has to be rewritten every time the floor moves; a
test that pins 'every highway centreline clears a safety scanner by
3.30 m' is the reason the floor is drawn the way it is.
"""
import math

import route
import stations

SCANNER_ABEAM_M = 0.46      # follower.py: fork-corner devices at +-0.46
FIELD_SLOW_M = 3.30         # follower.FIELD_SLOW_M
PF_HYST_M = 1.20            # case-1 PF 1.00 + 0.20 hysteresis
MIN_SPUR_M = 2.50


def _connected(graph):
    seen, stack = set(), [next(iter(graph))]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(graph[n])
    return seen


def _clearance(x, y):
    """Nearest obstacle to the point, over all rectangles."""
    best = math.inf
    for _n, xmin, xmax, ymin, ymax in stations.OBSTACLES:
        dx = max(xmin - x, 0.0, x - xmax)
        dy = max(ymin - y, 0.0, y - ymax)
        best = min(best, math.hypot(dx, dy))
    return best


def test_graph_is_one_component():
    graph = route.build_graph()
    assert _connected(graph) == set(graph)


def test_every_edge_is_axis_parallel():
    # A diagonal edge is a typo cutting through racking.
    graph = route.build_graph()
    for a, nbrs in graph.items():
        for b in nbrs:
            assert a[0] == b[0] or a[1] == b[1], (a, b)


def test_edges_are_symmetric():
    graph = route.build_graph()
    for a, nbrs in graph.items():
        for b in nbrs:
            assert a in graph[b]


def test_every_station_point_is_a_graph_node():
    graph = route.build_graph()
    for sid, s in stations.STATIONS.items():
        assert (s["x"], s["y"]) in graph, sid


def test_every_station_reachable_from_every_station():
    graph = route.build_graph()
    points = [(s["x"], s["y"]) for s in stations.STATIONS.values()]
    for a in points:
        for b in points:
            assert route.dijkstra(graph, a, b) is not None


def test_every_spur_is_long_enough_for_the_tight_radius():
    # A vehicle cannot reach a point inside its own turning circle.
    # Measured 2026-08-13: a 0.85 m spur orbits at 0.643-0.742 m.
    graph = route.build_graph()
    for sid, s in stations.STATIONS.items():
        point = (s["x"], s["y"])
        assert len(graph[point]) == 1, (sid, "a station has ONE spur")
        foot = next(iter(graph[point]))
        assert math.dist(point, foot) >= MIN_SPUR_M, (sid, foot)


def test_highway_centrelines_clear_a_scanner_by_the_field_band():
    # Where this holds the truck runs at CRUISE_MPS. Where it does not,
    # follower.target_speed holds it at the creep ceiling - by design on
    # a pick aisle, by accident nowhere.
    for x in route.RING_X:
        for y in (-10.0, 0.0, 10.0):
            assert _clearance(x, y) - SCANNER_ABEAM_M >= FIELD_SLOW_M, (x, y)
    for y in route.RING_Y:
        for x in route.NORTH_X if y > 0 else route.SOUTH_X:
            assert _clearance(x, y) - SCANNER_ABEAM_M >= FIELD_SLOW_M, (x, y)
    for y in route.LEG_Y:
        assert _clearance(route.SPINE_X, y) - SCANNER_ABEAM_M >= FIELD_SLOW_M


def test_pick_aisle_centreline_clears_a_scanner_by_the_protective_band():
    # A pick aisle is INSIDE the warning field on purpose and outside the
    # protective one always. Only the four SPUR FEET are checked: PICK_X
    # also carries the spine crossing at x = 0 and the two ring ends at
    # x = +-20, and those are highway - 4.26 m of clearance at x = 0,
    # which would fail a creep assertion and should.
    feet = sorted({s["x"] for s in stations.STATIONS.values()
                   if abs(s["y"]) < 10.0})
    assert feet == [-13.0, -7.0, 7.0, 13.0]
    for x in feet:
        gap = _clearance(x, route.PICK_Y) - SCANNER_ABEAM_M
        assert gap >= PF_HYST_M, (x, gap)
        assert gap < FIELD_SLOW_M, (x, gap, "this should be a creep aisle")


def test_no_node_lies_inside_or_against_the_racking():
    # 0.52 m plan half-envelope plus margin.
    graph = route.build_graph()
    for (x, y) in graph:
        assert _clearance(x, y) >= 0.6, (x, y)


def test_dijkstra_takes_the_short_way_home():
    # S2 (-7, +3.30) to S4 (-7, -3.30): down the spur, straight across
    # the pick aisle, up the other spur. Never around the ring.
    graph = route.build_graph()
    path = route.dijkstra(graph, (-7.0, 3.30), (-7.0, -3.30))
    assert path == [(-7.0, 3.30), (-7.0, 0.0), (-7.0, -3.30)]


def test_plan_route_starts_at_the_pose_and_ends_at_the_station():
    poly = route.plan_route((0.0, 10.0), "S6")
    assert poly[0] == (0.0, 10.0)
    assert poly[-1] == (13.0, 3.30)
    assert len(poly) >= 3


def test_plan_route_refuses_an_unknown_station():
    assert route.plan_route((0.0, 0.0), "S99") is None


def test_the_longest_leg_is_what_the_spec_says():
    # S12 to S1: 5.30 spur + 14.00 ring + 10.00 spine + 13.00 pick +
    # 3.30 spur. If this moves, the floor moved and the spec is stale.
    graph = route.build_graph()
    path = route.dijkstra(graph, (14.0, -15.30), (-13.0, 3.30))
    length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
    assert abs(length - 45.60) < 0.01, length
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_route.py -q
```

Expected: `AttributeError: module 'route' has no attribute 'RING_X'`
plus failures on every geometric assertion.

- [ ] **Step 3: Rewrite `m6/ipc/route.py`**

```python
"""route.py - the waypoint graph and the router. Pure, no ROS.

THE GRAPH IS THE CORRIDOR CENTRELINES AND NOTHING ELSE. A route that
exists in this graph therefore drives corridor middles by construction -
the reason the owner chose a fixed graph over grid planning.

THE FLOOR HAS TWO ROAD CLASSES AND THE GRAPH KNOWS ABOUT NEITHER.
Speed is follower.target_speed's business, decided from what the
scanners see. What the graph does is guarantee the truck is on a
centreline, and the centrelines are drawn so that a highway gives a
scanner more than FIELD_SLOW_M (3.30 m) and a pick aisle gives it less.
test_route.py asserts both, which is what keeps the two files honest
about each other.

  RING   a closed loop, x = +-20.00 and y = +-10.00, 120.00 m round
  SPINE  x = 0.00 from y = -10.00 to +10.00, joining the ring's two
         long legs through the middle of the block area
  PICK   y = 0.00 from x = -20.00 to +20.00, the one creep aisle

THE NORTH LEG CARRIES THE SPAWN NODES. -12, -6, +6 and +12 are the four
poses status_contract.VEHICLES declares. They are nodes because
nearest_node and floor._standing_from both snap a pose to the nearest
node, and four trucks whose nearest node is the same node are four
trucks the traffic ledger will hand one piece of floor to at startup.

EVERY STATION HAS EXACTLY ONE SPUR and it is at least 2.50 m long. See
stations.py for why a shorter one cannot be arrived at.
"""
import heapq
import math

from stations import STATIONS

RING_X = (-20.0, 20.0)          # the two N-S ring legs
RING_Y = (-10.0, 10.0)          # the two E-W ring legs
SPINE_X = 0.0
PICK_Y = 0.0

# Node x-positions along each E-W run.
NORTH_X = (-20.0, -12.0, -6.0, 0.0, 6.0, 12.0, 20.0)   # spawns at +-12, +-6
SOUTH_X = (-20.0, -14.0, -6.0, 0.0, 6.0, 14.0, 20.0)   # annex spur feet
PICK_X = (-20.0, -13.0, -7.0, 0.0, 7.0, 13.0, 20.0)    # pick spur feet
# Node y-positions along each N-S run (the ring legs and the spine).
LEG_Y = (-10.0, 0.0, 10.0)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _run(points):
    """Consecutive pairs of a sorted run, for linking."""
    ordered = sorted(points)
    return zip(ordered, ordered[1:])


def build_graph():
    """Adjacency {node: set(node)}; nodes are (x, y) tuples."""
    graph = {}

    def link(a, b):
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)

    for a, b in _run(NORTH_X):
        link((a, 10.0), (b, 10.0))
    for a, b in _run(SOUTH_X):
        link((a, -10.0), (b, -10.0))
    for a, b in _run(PICK_X):
        link((a, PICK_Y), (b, PICK_Y))
    for x in RING_X + (SPINE_X,):
        for a, b in _run(LEG_Y):
            link((x, a), (x, b))
    # THE SPUR FOOT IS ON THE RUN THE STATION FACES, never the nearer
    # one by arithmetic: a pick bay opens onto the pick aisle even
    # though the ring is not much further, and a route that entered a
    # bay from the ring would drive through a rack to do it.
    for s in STATIONS.values():
        foot_y = PICK_Y if abs(s["y"]) < 10.0 else -10.0
        link((s["x"], s["y"]), (s["x"], foot_y))
    return graph


def dijkstra(graph, start, goal):
    """Shortest node path start->goal, or None. Plain heap Dijkstra."""
    if start not in graph or goal not in graph:
        return None
    best, queue = {start: 0.0}, [(0.0, start, [start])]
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node == goal:
            return path
        if cost > best.get(node, math.inf):
            continue
        for nbr in graph[node]:
            c = cost + _dist(node, nbr)
            if c < best.get(nbr, math.inf):
                best[nbr] = c
                heapq.heappush(queue, (c, nbr, path + [nbr]))
    return None


def nearest_node(nodes, xy):
    return min(nodes, key=lambda n: _dist(n, xy))


def plan_route(pose_xy, station_id):
    """[pose_xy, entry node, ..., station point], or None if unknown.

    The pose is prepended so the follower's first segment starts under
    the truck instead of snapping it sideways onto the graph.
    """
    station = STATIONS.get(station_id)
    if station is None:
        return None
    graph = build_graph()
    goal = (station["x"], station["y"])
    path = dijkstra(graph, nearest_node(graph, pose_xy), goal)
    if path is None:
        return None
    poly = [tuple(pose_xy)] + path
    # Entering via a node the truck already stands past would command a
    # U-turn onto the node; drop it when the pose is nearer the second.
    if len(poly) > 2 and _dist(poly[0], poly[2]) < _dist(poly[1], poly[2]):
        poly.pop(1)
    return poly
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
python3 -m pytest m6/tests/test_route.py m6/tests/test_stations.py -q
```

Expected: all pass. If `test_every_spur_is_long_enough_for_the_tight_radius`
fails with "a station has ONE spur", a station point coincides with a run
node — check `PICK_X` and `SOUTH_X` against the station x-positions.

- [ ] **Step 5: Commit**

```bash
git add m6/ipc/route.py m6/tests/test_route.py
git commit -m "m6.6: a ring, a spine and one creep aisle"
```

---

## Task 3: The world

**Files:**
- Create: `m6/gazebo/warehouse_ver3.sdf`
- Modify: `m6/tests/test_stations_sdf.py`

**Interfaces:**
- Consumes: `stations.HALL`, `stations.STATIONS`, `stations.OBSTACLES`.
- Produces: an SDF world named `warehouse` (the *name inside the file*
  must stay `warehouse` — every `/world/warehouse/*` topic, launch file
  and script keys on it). Task 8 adds one model to this file; Task 9
  points the launch file at it.

- [ ] **Step 1: Write the failing test**

Replace `m6/tests/test_stations_sdf.py`:

```python
"""The world paint agrees with stations.py, and stays paint.

The SDF is hand-written; stations.py is the one home for the poses and
the obstacle rectangles. This suite is the coupling: move a station or a
rack in one place only and it fails, loudly, before Gazebo ever shows
the drift.
"""
import os
import re

import stations

_SDF = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "gazebo", "warehouse_ver3.sdf"))

_BLOCK = re.compile(r'<model name="Station(S\d+)Paint">(.*?)</model>', re.S)
_OBS = re.compile(r'<model name="(\w+)">\s*<static>true</static>\s*'
                  r'<pose>([-\d.eE ]+)</pose>(.*?)</model>', re.S)
_SIZE = re.compile(r"<collision.*?<box><size>([-\d.eE ]+)</size>", re.S)
_POSE = re.compile(r"<pose>([-\d.eE ]+)</pose>")


def _text():
    with open(_SDF, encoding="utf-8") as handle:
        return handle.read()


def _blocks():
    return {sid: body for sid, body in _BLOCK.findall(_text())}


def test_the_world_is_still_named_warehouse():
    # Every /world/warehouse/* topic, launch file and script keys on it.
    assert '<world name="warehouse">' in _text()


def test_exactly_the_twelve_station_ids_are_painted():
    assert set(_blocks()) == set(stations.STATIONS)


def test_painted_pose_matches_stations_py():
    for sid, body in _blocks().items():
        x, y = [float(v) for v in _POSE.search(body).group(1).split()[:2]]
        assert abs(x - stations.STATIONS[sid]["x"]) < 1e-3, sid
        assert abs(y - stations.STATIONS[sid]["y"]) < 1e-3, sid


def test_paint_has_no_collision_element():
    # Collision here would put a disc under the wheels and a return in
    # every scan. Visuals only.
    for sid, body in _blocks().items():
        assert "<collision" not in body, sid


def test_every_obstacle_rectangle_has_a_collision_body_in_the_world():
    """OBSTACLES is the SDF's shadow, so every rectangle must be real.

    Each obstacle model is written with its collision box centred on the
    model pose, so the rectangle is recoverable from pose +- size/2.
    """
    found = {}
    for name, pose, body in _OBS.findall(_text()):
        size = _SIZE.search(body)
        if size is None:
            continue
        px, py = [float(v) for v in pose.split()[:2]]
        sx, sy = [float(v) for v in size.group(1).split()[:2]]
        found[name] = (px - sx / 2, px + sx / 2, py - sy / 2, py + sy / 2)
    for name, xmin, xmax, ymin, ymax in stations.OBSTACLES:
        assert name in found, name
        for want, got in zip((xmin, xmax, ymin, ymax), found[name]):
            assert abs(want - got) < 1e-3, (name, want, got)


def test_the_hall_shell_matches_stations_hall():
    xmin, xmax, ymin, ymax = stations.HALL
    assert "48" in _text() or abs((xmax - xmin) - 48.0) < 1e-9
    assert abs((ymax - ymin) - 32.0) < 1e-9
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_stations_sdf.py -q
```

Expected: `FileNotFoundError` for `warehouse_ver3.sdf`.

- [ ] **Step 3: Write `m6/gazebo/warehouse_ver3.sdf`**

Start from `m6/gazebo/warehouse_ver2.sdf` — copy it, then edit. Keep
byte-for-byte: `<physics>`, every `<plugin>`, the `<gui>` block, the
`Floor` model's material, the light, and the world **name**
`warehouse`.

Change these, and nothing else:

1. **Header comment.** Rewrite it to describe this floor: the two road
   classes, the derivation `clear_width / 2 - 0.46 >= 3.30`, the
   ASCII sketch below, and a line saying `warehouse_ver2.sdf` is frozen
   and is not this file's parent in any build sense — it is its
   ancestor in history only.

   ```
    +y
     ^   north wall, inner face y = +14.00
     |  ===== RING, centreline y = +10.00, 8.00 m clear (CRUISE) =====
     |  ####[bay]####[bay]####  |S|  ####[bay]####[bay]####   racks
     |  ----- PICK AISLE, centreline y = 0.00, 5.00 m (CREEP) -----
     |  ####[bay]####[bay]####  |P|  ####[bay]####[bay]####   racks
     |  ===== RING, centreline y = -10.00, 8.00 m clear (CRUISE) =====
     |  ####[S9]####[S10]##[S11]####[S12]####   DOCK ANNEX
     +===========================================================> +x
        west ring leg x = -20.00      east ring leg x = +20.00
        spine |S|/|P| x = 0.00, 8.00 m clear, y = -10.00 to +10.00
   ```

2. **The shell.** Floor plane and four walls to `stations.HALL` —
   x in [-24, 24], y in [-18, +14]. Wall thickness and height keep
   ver2's values.

3. **Delete** `RackRowA`, `RackRowB`, `ConveyorStation`, both charge
   bays, `DoorGap` and every station paint from ver2. Grep for each name
   afterwards; each must return nothing.

4. **Add 29 obstacle models**, one per row of `stations.OBSTACLES`, each
   named exactly as the tuple's first field. Each is a static model whose
   `<pose>` is the rectangle centre and whose collision box `<size>` is
   the rectangle's extent. Rack segments and annex segments are 4.00 m
   tall; bay back panels are 4.00 m tall too (a scanner must see them).
   Template — `RackNW1` is `(-16.00, -15.00, 2.50, 6.00)`, so centre
   `(-15.50, 4.25)` and size `(1.00, 3.50)`:

   ```xml
   <model name="RackNW1">
     <static>true</static>
     <pose>-15.500 4.250 2.000 0 0 0</pose>
     <link name="link">
       <collision name="collision">
         <geometry><box><size>1.000 3.500 4.000</size></box></geometry>
       </collision>
       <visual name="visual">
         <geometry><box><size>1.000 3.500 4.000</size></box></geometry>
         <material>
           <ambient>0.45 0.45 0.48 1</ambient>
           <diffuse>0.55 0.55 0.58 1</diffuse>
         </material>
       </visual>
     </link>
   </model>
   ```

   The `<pose>` z is half the height (2.000) so the box sits on the floor.
   `test_every_obstacle_rectangle_has_a_collision_body_in_the_world`
   reads only x and y, so the z value is free — but keep it at half
   height or the boxes float.

5. **Add twelve station paints**, one per station, named
   `Station<ID>Paint`. Copy ver2's paint recipe exactly — visuals only,
   no collision. `<pose>` is the station's `x y 0 0 0 <yaw>`; the tick
   visual keeps its local offset so it rotates with the model.
   Template for S1 at `(-13.00, 3.30)` with yaw `+pi/2`:

   ```xml
   <model name="StationS1Paint">
     <static>true</static>
     <pose>-13.000 3.300 0 0 0 1.570796</pose>
     <link name="link">
       <visual name="disc">
         <pose>0 0 0.003 0 0 0</pose>
         <geometry><cylinder><radius>0.40</radius><length>0.006</length></cylinder></geometry>
         <material><ambient>0.10 0.35 0.75 1</ambient><diffuse>0.10 0.35 0.75 1</diffuse></material>
       </visual>
       <visual name="core">
         <pose>0 0 0.004 0 0 0</pose>
         <geometry><cylinder><radius>0.26</radius><length>0.006</length></cylinder></geometry>
         <material><ambient>0.92 0.92 0.95 1</ambient><diffuse>0.92 0.92 0.95 1</diffuse></material>
       </visual>
       <visual name="tick">
         <pose>0.330 0.000 0.005 0 0 0.000</pose>
         <geometry><box><size>0.30 0.08 0.006</size></box></geometry>
         <material><ambient>0.10 0.35 0.75 1</ambient><diffuse>0.10 0.35 0.75 1</diffuse></material>
       </visual>
     </link>
   </model>
   ```

6. **Add corridor paint** — visuals only, no collision — so the two road
   classes are visible on video: a 0.20 m wide white stripe down each
   ring centreline and the spine, and a 0.15 m yellow dashed stripe down
   the pick-aisle centreline. This is what makes the recording legible;
   it is not optional.

- [ ] **Step 4: Run the tests and watch them pass**

```bash
python3 -m pytest m6/tests/test_stations_sdf.py -q
grep -c 'RackRowA\|RackRowB\|ConveyorStation\|DoorGap' m6/gazebo/warehouse_ver3.sdf
```

Expected: `7 passed`, and the grep prints `0`.

- [ ] **Step 5: Check the world actually loads**

```bash
source /opt/ros/jazzy/setup.bash
timeout 25 gz sim -s -r --headless-rendering \
  /mnt/c/Users/ozkan/projects/amr-agent/m6/gazebo/warehouse_ver3.sdf
```

Expected: it runs for 25 s with no `Error` or `Unable to find` lines. An
SDF parse error here is far cheaper to find than during Task 9.

- [ ] **Step 6: Commit**

```bash
git add m6/gazebo/warehouse_ver3.sdf m6/tests/test_stations_sdf.py
git commit -m "m6.6: the world the station table describes"
```

---

## Task 4: The spawn poses

**Files:**
- Modify: `m6/ipc/status_contract.py:52-81` (the `VEHICLES` table and its
  comment block)
- Test: `m6/tests/test_fleet_spawn_fairness.py` (create)

**Interfaces:**
- Consumes: `route.build_graph`, `route.dijkstra`, `stations.STATIONS`.
- Produces: `status_contract.VEHICLES` with the same four keys `f1`-`f4`
  and the same `plc_port` / `sensor_port` values as today. **Only the
  `spawn` sub-dicts change.** `m6_world.launch.py:335-338` reads
  `c["spawn"]["x"|"y"|"z"|"yaw"]` as strings — keep them strings.

- [ ] **Step 1: Write the failing test**

Create `m6/tests/test_fleet_spawn_fairness.py`:

```python
"""The four spawns do not divide the floor between them.

M6's recording showed four trucks in four corners. The cause was in
status_contract's own comment: "Every station has a truck within 8.60 m
and no truck has to cross the hall." That was deliberate then and is
the defect now, so it gets an assertion rather than a comment.
"""
import collections
import math

import route
import stations
import status_contract


def _spawn_xy(vid):
    spawn = status_contract.VEHICLES[vid]["spawn"]
    return (float(spawn["x"]), float(spawn["y"]))


def _route_len(graph, a, b):
    path = route.dijkstra(graph, route.nearest_node(graph, a), b)
    assert path is not None, (a, b)
    return sum(math.dist(p, q) for p, q in zip(path, path[1:]))


def test_every_spawn_is_its_own_graph_node():
    # nearest_node and floor._standing_from both snap a pose to the
    # nearest node. Four trucks sharing one nearest node are four trucks
    # the ledger will hand one piece of floor to at startup.
    graph = route.build_graph()
    feet = [route.nearest_node(graph, _spawn_xy(v))
            for v in status_contract.VEHICLES]
    assert len(set(feet)) == len(feet), feet
    for vid in status_contract.VEHICLES:
        assert _spawn_xy(vid) in graph, vid


def test_no_truck_owns_more_than_a_third_of_the_floor():
    """Ties are SHARED, not awarded.

    The floor is mirror symmetric about x = 0 and so is the spawn row,
    so f2 and f3 are exactly equidistant from every mirrored pair of
    stations. fleet_core.nearest_idle breaks that tie by serial -
    deterministically, and to the lower one - so a strict count hands f2
    six of the twelve and f3 none, and measures alphabetical order
    rather than the floor. Shared, the row scores 3.0 each: measured
    2026-08-23, before this test was written.
    """
    graph = route.build_graph()
    share = collections.Counter()
    for sid, s in stations.STATIONS.items():
        goal = (s["x"], s["y"])
        metres = {v: _route_len(graph, _spawn_xy(v), goal)
                  for v in status_contract.VEHICLES}
        best = min(metres.values())
        winners = [v for v, m in metres.items() if m - best < 0.01]
        for v in winners:
            share[v] += 1.0 / len(winners)
    assert set(share) == set(status_contract.VEHICLES), dict(share)
    assert max(share.values()) <= 4.0, dict(share)


def test_parked_trucks_are_outside_each_other_warning_fields():
    # 2.50 warning field + 0.20 hysteresis. A scanner sits 0.46 m off
    # centre and a body edge 0.52 m off the neighbour's centre.
    poses = sorted(_spawn_xy(v) for v in status_contract.VEHICLES)
    for a, b in zip(poses, poses[1:]):
        gap = math.dist(a, b) - 0.46 - 0.52
        assert gap >= 2.70, (a, b, gap)


def test_no_spawn_sits_on_a_station_spur():
    for vid in status_contract.VEHICLES:
        x, y = _spawn_xy(vid)
        for sid, s in stations.STATIONS.items():
            assert math.dist((x, y), (s["x"], s["y"])) > 5.0, (vid, sid)
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_fleet_spawn_fairness.py -q
```

Expected: `test_every_spawn_is_its_own_graph_node` fails — the old poses
`(-3.0, -5.5)` and `(3.0, 5.65)` are not on the new graph at all.

- [ ] **Step 3: Edit the table**

In `m6/ipc/status_contract.py`, replace the four `spawn` dicts and the
comment block at lines 65-81 with:

```python
VEHICLES = {
    "f1": {"plc_port": 5110, "sensor_port": 5111,
           "spawn": {"x": "-12.00", "y": "10.00", "z": "0.05",
                     "yaw": "3.14159"}},
    "f2": {"plc_port": 5120, "sensor_port": 5121,
           "spawn": {"x": "-6.00", "y": "10.00", "z": "0.05",
                     "yaw": "3.14159"}},
    "f3": {"plc_port": 5130, "sensor_port": 5131,
           "spawn": {"x": "6.00", "y": "10.00", "z": "0.05",
                     "yaw": "3.14159"}},
    "f4": {"plc_port": 5140, "sensor_port": 5141,
           "spawn": {"x": "12.00", "y": "10.00", "z": "0.05",
                     "yaw": "3.14159"}},
}
# THE FOUR POSES ARE NOT A DIVISION OF THE FLOOR, AND THAT IS THE POINT.
# Until M6.6 they were: each truck stood nearest to the stations on its
# own quarter, no truck had to cross the hall, and the recording showed
# exactly that. The four now stand in a row on the NORTH RING LEG, which
# carries no station at all - so the first assignment sends every one of
# them somewhere, and after two transports the fleet is scattered by its
# own work rather than by this table (a truck finishes a transport at
# its DROPOFF station, not at a home pose).
#
# SPACING IS 6.00 m AND BOTH OF ITS CONSTRAINTS ARE DERIVED.
#   A neighbour's body edge sits 6.00 - 0.46 - 0.52 = 5.02 m from a
#   scanner, outside the 2.70 m re-clear threshold, so four parked
#   trucks do not sit in each other's warning fields and none of them
#   starts under a reduced V_Limit.
#   Each pose IS A GRAPH NODE (route.NORTH_X carries -12, -6, +6, +12).
#   nearest_node and floor._standing_from both snap a pose to the
#   nearest node, and four trucks whose nearest node is the same node
#   are four trucks the traffic ledger will hand one piece of floor to.
#
# yaw 3.14159 points the forks at world +x: model yaw 0 puts them at
# -x, so pi is the row facing east down the north leg.
#
# test_fleet_spawn_fairness.py holds all three of those, and it holds
# them as RULES: if a pose has to move, move it and let the assertions
# say whether the new one is honest.
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
python3 -m pytest m6/tests/test_fleet_spawn_fairness.py m6/tests/test_status_contract.py -q
```

Expected: all pass, and the shared-ownership counter reads **3.0 for
each of the four trucks** — that is the measured value, not a bound. If
`test_no_truck_owns_more_than_a_third_of_the_floor` fails, report the
counter it printed and stop. Do **not** move the poses inward to
`-6/-2/+2/+6`: that breaks the 6.00 m spacing rule. A persistent lean
means the station table needs re-balancing, which is a spec change and
not an implementation choice.

- [ ] **Step 5: Commit**

```bash
git add m6/ipc/status_contract.py m6/tests/test_fleet_spawn_fairness.py
git commit -m "m6.6: four trucks in a row on a leg with no stations"
```

---

## Task 5: The work generator

**Files:**
- Create: `m6/fleet/work_generator.py`
- Test: `m6/tests/test_work_generator.py`

**Interfaces:**
- Consumes: `stations.STATIONS`, `route.plan_route` (Tasks 1, 2).
- Produces: `work_generator.WorkGenerator(seed, min_len_m=15.0,
  stations_map=None, route_len=None)` with one public method
  `next_pair() -> (str, str)` and one public attribute `pairs` (the
  sorted list of candidate `(from, to, length)` triples). Task 6 calls
  `WorkGenerator(seed=...).next_pair()`.

- [ ] **Step 1: Write the failing test**

Create `m6/tests/test_work_generator.py`:

```python
"""work_generator - which transport to ask for next. Pure.

No broker, no clock, no ROS: this file decides a station pair and
nothing else, which is what makes the decision reproducible. A seeded
generator is not a convenience here - the GUI take of the recording has
to replay the headless take's scenario exactly, and a seed is the only
thing that makes two runs the same run.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import work_generator as wg                                  # noqa: E402
from stations import STATIONS                                # noqa: E402


def test_the_same_seed_gives_the_same_sequence():
    a = [wg.WorkGenerator(seed=7).next_pair() for _ in range(20)]
    b = [wg.WorkGenerator(seed=7).next_pair() for _ in range(20)]
    assert a[0] == b[0]
    one = wg.WorkGenerator(seed=7)
    two = wg.WorkGenerator(seed=7)
    assert [one.next_pair() for _ in range(20)] == \
           [two.next_pair() for _ in range(20)]


def test_a_different_seed_gives_a_different_sequence():
    one = wg.WorkGenerator(seed=7)
    two = wg.WorkGenerator(seed=8)
    assert [one.next_pair() for _ in range(20)] != \
           [two.next_pair() for _ in range(20)]


def test_it_never_asks_for_a_transport_to_the_same_station():
    gen = wg.WorkGenerator(seed=3)
    for _ in range(500):
        src, dst = gen.next_pair()
        assert src != dst


def test_every_pair_names_a_real_station():
    gen = wg.WorkGenerator(seed=4)
    for _ in range(200):
        for sid in gen.next_pair():
            assert sid in STATIONS


def test_no_pair_is_shorter_than_the_minimum():
    gen = wg.WorkGenerator(seed=5, min_len_m=15.0)
    lengths = {(a, b): d for a, b, d in gen.pairs}
    for _ in range(300):
        assert lengths[gen.next_pair()] >= 15.0


def test_long_routes_are_favoured_over_short_ones():
    # Weight is proportional to length, so the longest quartile of pairs
    # must come up more often than the shortest quartile. Without this
    # the recording is full of shuffles between neighbouring bays.
    gen = wg.WorkGenerator(seed=11)
    ordered = sorted(gen.pairs, key=lambda p: p[2])
    cut = len(ordered) // 4
    short = {(a, b) for a, b, _d in ordered[:cut]}
    long_ = {(a, b) for a, b, _d in ordered[-cut:]}
    drawn = [gen.next_pair() for _ in range(2000)]
    assert sum(p in long_ for p in drawn) > sum(p in short for p in drawn)


def test_it_refuses_a_minimum_no_pair_can_meet():
    with pytest.raises(ValueError, match="no station pair"):
        wg.WorkGenerator(seed=1, min_len_m=500.0)
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_work_generator.py -q
```

Expected: `ModuleNotFoundError: No module named 'work_generator'`.

- [ ] **Step 3: Write `m6/fleet/work_generator.py`**

```python
"""work_generator.py - which transport to ask for next. Pure.

NO BROKER, NO CLOCK, NO ROS. This file decides a station pair and
nothing else; fleet_cli's `demo` command is the only thing that turns a
pair into a submission, exactly as `submit` is the only thing that turns
an operator's two arguments into one.

SEEDED, AND THAT IS A REQUIREMENT RATHER THAN A CONVENIENCE. The
recording is shot twice - once headless with the overhead camera, once
with the Gazebo GUI - and the second take has to be the same scenario as
the first or the two videos are of two different runs. A seed is the
only thing that makes them one run.

WEIGHTED BY ROUTE LENGTH, MEASURED OVER THE ROUTER. A uniform draw over
132 ordered pairs spends most of a recording shuffling pallets between
neighbouring bays, because most pairs ARE short. Weighting by the
router's own distance - never the crow's - puts the cross-hall runs on
screen, which is the whole point of the exercise. `min_len_m` then cuts
the tail off entirely: a 6 m transport is not a fleet demonstration.

IT DRAWS WITH REPLACEMENT AND DOES NOT CARE. The fleet is a queue, not a
schedule; the same pair coming up twice in a shift is a fact about
warehouses, not a defect in this file.
"""
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))
import route                                        # noqa: E402
from stations import STATIONS                       # noqa: E402

MIN_LEN_M = 15.0


def _route_len(src, dst):
    """Metres from station `src` to station `dst` over the router, or
    None when the graph does not join them."""
    start = STATIONS[src]
    poly = route.plan_route((start["x"], start["y"]), dst)
    if poly is None:
        return None
    return sum(
        ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        for a, b in zip(poly, poly[1:]))


class WorkGenerator:
    """A seeded stream of (from_station, to_station) pairs."""

    def __init__(self, seed, min_len_m=MIN_LEN_M, stations_map=None,
                 route_len=None):
        """`stations_map` and `route_len` exist for the tests and for a
        floor that is not this one; production passes neither."""
        table = STATIONS if stations_map is None else stations_map
        length = _route_len if route_len is None else route_len
        pairs = []
        for src in table:
            for dst in table:
                if src == dst:
                    continue
                metres = length(src, dst)
                if metres is None or metres < min_len_m:
                    continue
                pairs.append((src, dst, metres))
        if not pairs:
            raise ValueError(
                "no station pair is at least {:.1f} m apart over the "
                "router - the floor cannot serve this demo"
                .format(min_len_m))
        # Sorted so the list is the same list on every machine: dict
        # iteration order is insertion order, but a caller may hand us
        # any mapping.
        self.pairs = sorted(pairs)
        self._weights = [metres for _s, _d, metres in self.pairs]
        self._rng = random.Random(seed)

    def next_pair(self):
        """One (from, to). Weighted by route length, drawn with
        replacement."""
        src, dst, _metres = self._rng.choices(
            self.pairs, weights=self._weights, k=1)[0]
        return (src, dst)
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
python3 -m pytest m6/tests/test_work_generator.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add m6/fleet/work_generator.py m6/tests/test_work_generator.py
git commit -m "m6.6: work that keeps arriving, weighted toward the far end"
```

---

## Task 6: The `demo` command

**Files:**
- Modify: `m6/fleet/fleet_cli.py` (add `cmd_demo`, register the
  subparser in `main`)
- Test: `m6/tests/test_fleet_cli.py` (append)

**Interfaces:**
- Consumes: `work_generator.WorkGenerator` (Task 5),
  `fleet_cli.build_submission`, `fleet_cli._status_reader`,
  `fleet_cli.SUBMIT_TOPIC` (all existing).
- Produces: `fleet_cli.demo_plan(seed, count, min_len_m) -> list[dict]`
  — the submission bodies the run would send, in order — and a `demo`
  subcommand. Task 10 runs the subcommand.

- [ ] **Step 1: Write the failing test**

Append to `m6/tests/test_fleet_cli.py`:

```python
def test_demo_plan_is_deterministic_and_well_formed():
    a = fleet_cli.demo_plan(seed=7, count=25, min_len_m=15.0)
    b = fleet_cli.demo_plan(seed=7, count=25, min_len_m=15.0)
    assert [(t["from"], t["to"]) for t in a] == \
           [(t["from"], t["to"]) for t in b]
    assert len(a) == 25
    assert len({t["taskId"] for t in a}) == 25
    for body in a:
        assert body["from"] != body["to"]
        assert set(body) == {"taskId", "from", "to"}


def test_demo_dry_run_prints_the_plan_and_needs_no_broker(capsys):
    rc = fleet_cli.main(["demo", "--seed", "7", "--count", "5",
                         "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 5
    for line in out:
        assert "->" in line


def test_demo_refuses_a_non_positive_in_flight():
    assert fleet_cli.main(["demo", "--in-flight", "0", "--dry-run"]) == 2
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_fleet_cli.py -q -k demo
```

Expected: `AttributeError: module 'fleet_cli' has no attribute 'demo_plan'`.

- [ ] **Step 3: Add the command**

At the top of `m6/fleet/fleet_cli.py`, beside the existing imports, add:

```python
from work_generator import MIN_LEN_M, WorkGenerator
```

`fleet/` is already on `sys.path` for anything importing `fleet_cli`, so
this is a plain sibling import.

Then add, above `def main(`:

```python
# ---- the demo driver ----
# A RECORDING NEEDS WORK THAT DOES NOT STOP ARRIVING. `submit` is the
# operator's command and stays exactly what it was: two station ids, one
# transport, one line of output. `demo` is the SHIFT - it keeps
# `--in-flight` transports alive for `--duration` seconds and gets its
# pairs from work_generator, seeded, so the run can be shot twice and be
# the same run both times.
#
# IT SUBMITS THROUGH build_submission AND SUBMIT_TOPIC, the same funnel
# `submit` uses. There is no second wire and no second refusal list; a
# pair the manager will not take comes back in the status document's
# REFUSED section exactly as a typed one does.
DEMO_POLL_S = 2.0


def demo_plan(seed, count, min_len_m=MIN_LEN_M):
    """The `count` submission bodies this seed would send, in order.

    Pure and broker-free, which is what --dry-run prints and what the
    tests assert against: the plan is decidable without a fleet.
    """
    gen = WorkGenerator(seed=seed, min_len_m=min_len_m)
    return [build_submission(*gen.next_pair()) for _ in range(count)]


def _in_flight(doc):
    """How many tasks the manager is not finished with."""
    tasks = _list(doc, "tasks")
    return sum(1 for t in tasks
               if isinstance(t, dict) and t.get("state") != "DONE")


def cmd_demo(args):
    if args.in_flight < 1:
        return _die("--in-flight must be at least 1", 2)
    if args.duration <= 0:
        return _die("--duration must be positive", 2)
    if args.dry_run:
        for body in demo_plan(args.seed, args.count, args.min_len):
            print("{}  {} -> {}".format(
                body["taskId"], body["from"], body["to"]))
        return 0
    gen = WorkGenerator(seed=args.seed, min_len_m=args.min_len)
    client, inbox = _status_reader(args.host, args.port, "demo")
    if client is None:
        return 1
    deadline = time.time() + args.duration
    sent, doc = 0, None
    try:
        while time.time() < deadline:
            fresh = _await(inbox, DEMO_POLL_S)
            if fresh is not None:
                doc = _parse(fresh)
            if doc is None:
                continue
            # ONE SUBMISSION PER PASS, not a burst to the target. The
            # retained document is republished on change and on a 2 s
            # tick, so a burst would be sized against a count the
            # manager has not seen yet and the queue would overshoot.
            if _in_flight(doc) >= args.in_flight:
                continue
            body = build_submission(*gen.next_pair())
            client.publish(SUBMIT_TOPIC, json.dumps(body), qos=1)
            doc = None          # do not re-count a stale document
            sent += 1
            print("{}  {} -> {}".format(
                body["taskId"], body["from"], body["to"]), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        _close(client)
    print("demo: {} transports submitted over {:.0f} s"
          .format(sent, args.duration))
    return 0
```

In `main`, after the `status` subparser is built, add:

```python
    demo = commands.add_parser(
        "demo", help="keep the fleet fed for a recording")
    demo.add_argument("--duration", type=float, default=600.0,
                      help="seconds to keep submitting (default 600)")
    demo.add_argument("--in-flight", type=int, default=4,
                      help="transports to keep alive (default 4)")
    demo.add_argument("--seed", type=int, default=7,
                      help="the pair sequence's seed (default 7)")
    demo.add_argument("--min-len", type=float, default=MIN_LEN_M,
                      help="shortest route worth a transport, metres")
    demo.add_argument("--count", type=int, default=25,
                      help="pairs to print under --dry-run (default 25)")
    demo.add_argument("--dry-run", action="store_true",
                      help="print the plan and exit; needs no broker")
```

and replace the dispatch line at the foot of `main`:

```python
    if args.command == "submit":
        return cmd_submit(args)
    if args.command == "demo":
        return cmd_demo(args)
    return cmd_status(args)
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
python3 -m pytest m6/tests/test_fleet_cli.py -q
python3 m6/fleet/fleet_cli.py demo --seed 7 --count 8 --dry-run
```

Expected: the suite passes, and the second command prints eight
`ft-xxxxxxxx  Sn -> Sm` lines with no broker running.

- [ ] **Step 5: Commit**

```bash
git add m6/fleet/fleet_cli.py m6/tests/test_fleet_cli.py
git commit -m "m6.6: fleet_cli demo - a shift, not a transport"
```

---

## Task 7: The latch watchdog

**Files:**
- Modify: `m6/tools/scripted_writer.py`
- Test: `m6/tests/test_scripted_writer.py` (append)

**Interfaces:**
- Consumes: `scripted_writer.apply_command`, `m6.ACK_PULSE_S` (existing).
- Produces: `scripted_writer.latch_watch(live, state, now, last_reset,
  hold_s) -> (bool, str | None)` — `(should_press_reset, log_line)`.

**Owner ruling, 2026-08-23:** a recording runs with an automatic
operator and says so. `PROOF.md` residual 10 — a protective demand
latches and only a panel RESET clears it; four latches inside 0.56 s
ended the 0-of-8 acceptance run. Every press is logged. **The nan/stale
rule is not touched:** an undelivered scan is still a violated field.
This clears the latch *afterwards*; it never makes a scanner less honest.

- [ ] **Step 1: Write the failing test**

Append to `m6/tests/test_scripted_writer.py`:

```python
def test_watchdog_presses_reset_when_motor_is_down_and_estop_is_not():
    live = {"motor": False, "line": "MOTOR STOPPED"}
    state = {"estop": False}
    press, line = scripted_writer.latch_watch(
        live, state, now=100.0, last_reset=0.0, hold_s=3.0)
    assert press is True
    assert "RESET" in line and "100.0" in line


def test_watchdog_is_silent_while_motor_is_up():
    live = {"motor": True, "line": "MOTOR ENABLED"}
    press, line = scripted_writer.latch_watch(
        live, {"estop": False}, now=100.0, last_reset=0.0, hold_s=3.0)
    assert press is False
    assert line is None


def test_watchdog_never_presses_through_a_held_estop():
    # An e-stop is the operator's own hand. Acknowledging it away would
    # be inventing an operator action nobody asked for.
    live = {"motor": False, "line": "E-STOP"}
    press, _line = scripted_writer.latch_watch(
        live, {"estop": True}, now=100.0, last_reset=0.0, hold_s=3.0)
    assert press is False


def test_watchdog_waits_out_its_hold_before_pressing_again():
    live = {"motor": False, "line": "MOTOR STOPPED"}
    press, _line = scripted_writer.latch_watch(
        live, {"estop": False}, now=101.0, last_reset=100.0, hold_s=3.0)
    assert press is False
    press, _line = scripted_writer.latch_watch(
        live, {"estop": False}, now=104.0, last_reset=100.0, hold_s=3.0)
    assert press is True
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_scripted_writer.py -q -k watchdog
```

Expected: `AttributeError: ... has no attribute 'latch_watch'`.

- [ ] **Step 3: Add the watchdog**

Add to `m6/tools/scripted_writer.py`, above `def serve(`:

```python
# ---- the latch watchdog: a demo-only automatic operator ----
# OWNER RULING, 2026-08-23. PROOF.md residual 10: a protective demand
# LATCHES and only a panel RESET clears it. A ten-minute recording has no
# operator in it, so the first latch costs a truck for the rest of the
# run - and in the 0-of-8 acceptance run four latches inside 0.56 s cost
# all of it. So a recording gets an automatic operator, and it SAYS SO:
# every press below is printed with its timestamp and the line the writer
# was reading, and the count goes into PROOF.md beside the run labelled
# demo-only automatic operator.
#
# WHAT IT DOES NOT DO, AND THIS IS THE WHOLE OF THE HONESTY. It does not
# touch a scanner, a field verdict, the nan rule or the staleness rule -
# an undelivered scan is still a violated field and still demands a stop.
# It presses the button a person would have pressed, after the stop has
# already happened. And it will not press through a HELD e-stop: that is
# the operator's own hand and acknowledging it away would be inventing an
# action nobody asked for.
RESET_HOLD_S = 3.0      # a press per 3 s at most: the F-program wants a
                        # rising edge and the loop makes the falling one
                        # ACK_PULSE_S later; pressing faster than that
                        # stacks edges the PLC never sees separately.


def latch_watch(live, state, now, last_reset, hold_s=RESET_HOLD_S):
    """(press_reset, log_line). Pure - the caller owns the socket."""
    if live.get("motor"):
        return (False, None)
    if state.get("estop"):
        return (False, None)
    if now - last_reset < hold_s:
        return (False, None)
    return (True, "AUTO-RESET t={:.1f} after: {}".format(
        now, str(live.get("line", "")).replace("\n", " | ")))
```

Then wire it into `serve`. Inside the `while state["run"]:` loop, after
the `last_print` block and before the `ctl.recvfrom` call, add:

```python
        if auto_reset:
            press, line = latch_watch(live, state, now, last_reset)
            if press:
                last_reset = now
                resets[0] += 1
                state["ack_until"] = now + m6.ACK_PULSE_S
                print(line, flush=True)
```

Give `serve` the three new parameters — change its signature to
`def serve(state, live, ctl, auto_reset=False, resets=None):` and open
the body with:

```python
    resets = [0] if resets is None else resets
    last_reset = 0.0
```

In `main`, add the flag and report the count on the way out:

```python
    ap.add_argument("--auto-reset", action="store_true",
                    help="press RESET on a latched truck (recordings "
                         "only; every press is logged)")
```

pass `auto_reset=args.auto_reset, resets=resets` where `serve` is
called, and print `"auto-resets: {}".format(resets[0])` in the same
place the writer prints its closing lines.

- [ ] **Step 4: Run the tests and watch them pass**

```bash
python3 -m pytest m6/tests/test_scripted_writer.py -q
```

Expected: all pass, including the pre-existing ones.

- [ ] **Step 5: Commit**

```bash
git add m6/tools/scripted_writer.py m6/tests/test_scripted_writer.py
git commit -m "m6.6: an automatic operator for a recording, and it says so"
```

---

## Task 8: The overhead camera and the recorder

**Files:**
- Modify: `m6/gazebo/warehouse_ver3.sdf` (add one model)
- Modify: `m6/gazebo/m6_world.launch.py` (add one bridge entry)
- Create: `m6/tools/record_overhead.py`

**Interfaces:**
- Consumes: nothing from earlier tasks except the world file.
- Produces: gz topic `/world/warehouse/model/OverheadCam/link/link/sensor/overhead/image`
  bridged to ROS as `sensor_msgs/msg/Image` on the same name; and a
  script `record_overhead.py --out FILE [--seconds N]`.

- [ ] **Step 1: Add the camera to the world**

Append to `warehouse_ver3.sdf`, before `</world>`:

```xml
<!-- THE RECORDING'S EYE, AND IT IS IN THE WORLD RATHER THAN THE GUI.
     gz sim's own video recorder needs a GUI, and the GUI costs 0.137 of
     integrated real-time factor (measured 2026-08-23) on a rig that is
     already the binding constraint. A camera sensor renders one 1600x900
     frame at 20 Hz in the SERVER, so the main take can run --headless
     and spend that 0.137 on physics and the sixteen gpu_lidars instead.
     z = 38 with hfov 1.40 covers 64.0 x 36.0 m; the hall is 48 x 32 and
     is centred on y = -2.00, which is where this sits.

     THE YAW IS NOT DECORATION AND IT IS NOT ZERO. A gz camera looks
     down its own +X with image-right at -Y and image-up at +Z. Pitch
     alone (0, pi/2, 0) lands image-right on world -Y and image-up on
     world +X: the picture comes out rotated a quarter turn, and -
     because hfov sizes the WIDTH - the hall's 48 m X extent is then
     squeezed into the 36 m the SHORT axis covers, so both ends of the
     floor are cropped and trucks drive out of frame. Yaw = +pi/2 puts
     image-right on world +X (64.0 m for 48) and image-up on world +Y
     (36.0 m for 32): north up, east right, whole floor. -->
<model name="OverheadCam">
  <static>true</static>
  <pose>0 -2 38 0 1.5707963 1.5707963</pose>
  <link name="link">
    <sensor name="overhead" type="camera">
      <always_on>1</always_on>
      <update_rate>20</update_rate>
      <topic>overhead/image</topic>
      <camera>
        <horizontal_fov>1.40</horizontal_fov>
        <image><width>1600</width><height>900</height>
               <format>R8G8B8</format></image>
        <clip><near>1.0</near><far>60.0</far></clip>
      </camera>
    </sensor>
  </link>
</model>
```

- [ ] **Step 2: Bridge it**

In `m6/gazebo/m6_world.launch.py`, in the **world-level** bridge
argument list (the one built once, not the per-vehicle one), add:

```python
    # The overhead camera, gz -> ROS. ONE camera for the world, not one
    # per vehicle: it is the recording's eye, not a truck's sensor, and
    # nothing in ipc/ subscribes to it.
    "/overhead/image@sensor_msgs/msg/Image[gz.msgs.Image",
```

- [ ] **Step 3: Write the recorder**

Create `m6/tools/record_overhead.py`:

```python
"""record_overhead.py - the overhead camera into an mp4. WSL side.

WHY NOT gz sim's OWN RECORDER: it lives in the GUI, and the GUI costs
0.137 of integrated real-time factor (measured 2026-08-23) on a rig
where the floor of that number is what decides whether sixteen
gpu_lidars keep delivering. The main take therefore runs --headless and
this script is its camera operator.

IT WRITES WHAT IT WAS GIVEN AND NOTHING ELSE. No overlay, no timestamp
burn-in, no re-scaling: an artefact in this file is an artefact nobody
can tell from an artefact in the simulation. The frame that arrives is
the frame that lands in the file.

A DROPPED FRAME IS NOT SMOOTHED OVER. ffmpeg is fed at the rate frames
arrive and the output is stamped at the sensor's own 20 Hz, so a run
whose real-time factor collapsed produces a SHORTER video, not a
smooth one. That is the honest direction: the recording should look
like what the rig did.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m6/tools/record_overhead.py --out /tmp/m6-fleet.mp4 --seconds 620
"""
import argparse
import subprocess
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

TOPIC = "/overhead/image"
FPS = 20


def ffmpeg(path, width, height, fps=FPS):
    """A raw-frame sink. -y because a re-take overwrites its own take."""
    return subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
         "-video_size", "{}x{}".format(width, height),
         "-framerate", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-pix_fmt", "yuv420p", path],
        stdin=subprocess.PIPE)


class Recorder(Node):

    def __init__(self, path, seconds):
        super().__init__("record_overhead")
        self._path, self._seconds = path, seconds
        self._sink = None
        self._frames = 0
        self._t0 = None
        self.create_subscription(Image, TOPIC, self._frame, 10)

    def _frame(self, msg):
        if msg.encoding != "rgb8":
            self.get_logger().error(
                "expected rgb8, got {!r} - the camera's <format> and this "
                "script disagree".format(msg.encoding))
            raise SystemExit(2)
        if self._sink is None:
            self._sink = ffmpeg(self._path, msg.width, msg.height)
            self._t0 = self.get_clock().now()
            self.get_logger().info(
                "recording {}x{} to {}".format(
                    msg.width, msg.height, self._path))
        try:
            self._sink.stdin.write(bytes(msg.data))
        except BrokenPipeError:
            self.get_logger().error("ffmpeg went away")
            raise SystemExit(3)
        self._frames += 1
        elapsed = (self.get_clock().now() - self._t0).nanoseconds / 1e9
        if elapsed >= self._seconds:
            raise SystemExit(0)

    def close(self):
        if self._sink is not None:
            self._sink.stdin.close()
            self._sink.wait()
        print("wrote {} frames ({:.1f} s at {} fps) to {}".format(
            self._frames, self._frames / float(FPS), FPS, self._path))


def main():
    ap = argparse.ArgumentParser(description="the overhead camera to mp4")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=620.0)
    args = ap.parse_args()
    rclpy.init()
    node = Recorder(args.out, args.seconds)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Prove the camera and the pipe both work**

```bash
source /opt/ros/jazzy/setup.bash
cd /mnt/c/Users/ozkan/projects/amr-agent
gz sim -s -r --headless-rendering m6/gazebo/warehouse_ver3.sdf &
sleep 8
ros2 run ros_gz_bridge parameter_bridge \
  /overhead/image@sensor_msgs/msg/Image[gz.msgs.Image &
sleep 3
python3 m6/tools/record_overhead.py --out /tmp/overhead-smoke.mp4 --seconds 10
ls -l /tmp/overhead-smoke.mp4
kill %1 %2
```

Expected: a non-empty mp4 of roughly 10 s. If `msg.encoding` is not
`rgb8`, change the world's `<format>` rather than the script — the
script's error message is the contract.

- [ ] **Step 5: Commit**

```bash
git add m6/gazebo/warehouse_ver3.sdf m6/gazebo/m6_world.launch.py \
        m6/tools/record_overhead.py
git commit -m "m6.6: an eye over the floor that costs no GUI"
```

---

## Task 9: Wire the stack to the new floor

**Files:**
- Modify: `m6/gazebo/m6_world.launch.py:67` (the `_WORLD` path and the
  comment above it)
- Modify: `m6/hmi/map_panel.py:23-24`
- Modify: `m6/m6.sh` (the deploy manifest, if it names the world)
- Modify: `m6/deploy/MANIFEST`

**Interfaces:**
- Consumes: everything from Tasks 1-8.
- Produces: a stack that starts on `warehouse_ver3.sdf` with four trucks
  at their new poses.

- [ ] **Step 1: Point the launch file at the new world**

In `m6/gazebo/m6_world.launch.py`, replace line 67 and rewrite the
comment block above it:

```python
# M6.6'S OWN WORLD. warehouse_ver2.sdf is FROZEN and stays in this
# directory: every M6.1-M6.5 figure in PROOF.md was measured on it and a
# figure whose floor was edited under it is not a figure. ver3 is the
# 48 x 32 m two-road-class relayout (spec:
# docs/superpowers/specs/2026-08-23-m6-6-floor-and-dispatch-design.md).
# The world NAME inside the file stays "warehouse", so _WORLD_NAME and
# every /world/warehouse/* topic hold. ONE world for every vehicle.
_WORLD = os.path.join(_HERE, "warehouse_ver3.sdf")
```

- [ ] **Step 2: Size the HMI sketch from the hall instead of a constant**

In `m6/hmi/map_panel.py`, replace lines 23-24:

```python
# PX PER METRE, AND THE CANVAS FOLLOWS THE FLOOR. Until M6.6 the two
# numbers below were independent - 15.0 px/m and a hard-coded 450 x 300
# that happened to be 30 x 20 m at that scale. A floor change then moved
# the sketch's contents without moving its frame. Now the frame is
# derived: 11.0 px/m over a 48 x 32 m hall gives 528 x 352, which fits
# four HMI windows on one screen.
SCALE = 11.0
WIDTH = (stations.HALL[1] - stations.HALL[0]) * SCALE
HEIGHT = (stations.HALL[3] - stations.HALL[2]) * SCALE
```

- [ ] **Step 3: Update the deploy manifest**

```bash
grep -rn "warehouse_ver2" m6/deploy/MANIFEST m6/m6.sh
```

Wherever it names `warehouse_ver2.sdf`, add `warehouse_ver3.sdf`
alongside it — **do not remove ver2**, it is frozen but still shipped.
If the manifest's file count is asserted anywhere (`m6.sh deploy` prints
`deployed 31 files`), update that number and the README line that quotes
it.

- [ ] **Step 4: Run the whole suite**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m6/tests/ -q
```

Expected: **all pass, 0 skipped.** The count will be higher than 485
(Tasks 1-7 added roughly 30 tests). A skip is a failure — it means a
module did not import.

- [ ] **Step 5: Bring the stack up once and look at it**

```bash
# Windows first: wsl --shutdown
export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
cd /mnt/c/Users/ozkan/projects/amr-agent/m6
./m6.sh deploy && ./m6.sh start
```

Expected: the printed pid count matches the manifest, no line says
`exited during startup`, four HMI windows appear and each sketch shows
the new floor with twelve stations. Then `./m6.sh down`.

- [ ] **Step 6: Commit**

```bash
git add -A m6/
git status --short          # nothing outside m6/ may appear
git commit -m "m6.6: the stack starts on the new floor"
```

---

## Task 10: The measured run and the two videos

**Files:**
- Create: `assets/m6-fleet/m6-fleet-03-new-floor-1x-2026-08-XX.mp4`
- Create: `assets/m6-fleet/m6-fleet-04-new-floor-gui-2026-08-XX.mp4`
- Modify: `m6/PROOF.md` (append an M6.6 section; remove nothing)
- Modify: `m6/README_m6.md` (the floor, the `demo` command, the takes)

**Interfaces:** consumes everything. Produces the deliverable.

- [ ] **Step 1: Measure the rig before the run**

```bash
# Windows: wsl --shutdown, then in WSL:
export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
bash /mnt/c/Users/ozkan/projects/amr-agent/m6/tools/rtf_spike.sh
```

Record the integrated RTF and its floor. **Acceptance criterion 5:
integrated RTF ≥ 0.40 with a floor ≥ 0.020.** If the floor is under
0.020, pull the one pre-agreed lever and only that one: in
`m6/gazebo/forklift_ver2/model.sdf`, change the nav lidar's
`<samples>360</samples>` to `180`. `follower.sector_min` reads angles,
not indices, so no code changes. Re-measure, and note both figures in
PROOF.

- [ ] **Step 2: Take 1 — headless, overhead camera**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent/m6
./m6.sh deploy && ./m6.sh start --headless
# four Windows terminals, one per vehicle:
#   python m6\tools\scripted_writer.py --vehicle fN --virtual \
#          --ctl-port 591N --auto-reset
# then in WSL, two terminals:
python3 tools/record_overhead.py --out /tmp/m6-take1.mp4 --seconds 620 &
python3 fleet/fleet_cli.py demo --duration 600 --in-flight 4 --seed 7
```

- [ ] **Step 3: Score the run against the six criteria**

From the run's own logs and odometry:

1. Fleet distance ≥ **800 m** over the 10 minutes (baseline: 144.2 m in
   1024 s).
2. **≥ 12** transports completed.
3. Every truck moves in **every 2-minute window**.
4. Every arrival inside **0.25 m**.
5. Integrated RTF ≥ **0.40**, floor ≥ **0.020**.
6. Auto-RESET presses logged and **≤ 4**.

Write every number down as measured, pass or fail. A failed criterion is
reported, not smoothed — `m6/PROOF.md`'s own convention is that an
unticked gate is not a passed one.

- [ ] **Step 4: Take 2 — GUI, same seed**

```bash
./m6.sh start                     # no --headless
# same four scripted_writers, same --auto-reset
ffmpeg -f x11grab -framerate 25 -video_size 1920x1080 -i "$DISPLAY" \
       -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
       /tmp/m6-take2.mp4 &
python3 fleet/fleet_cli.py demo --duration 180 --in-flight 4 --seed 7
```

Three minutes, not ten: this take costs the RTF that take 1 protects.

- [ ] **Step 5: Land the videos and write the run up**

```bash
cp /tmp/m6-take1.mp4 assets/m6-fleet/m6-fleet-03-new-floor-1x-$(date +%F).mp4
cp /tmp/m6-take2.mp4 assets/m6-fleet/m6-fleet-04-new-floor-gui-$(date +%F).mp4
```

Append to `m6/PROOF.md` a section headed `## M6.6 — the new floor,
measured`, carrying: the six criteria with their measured values and a
`[x]`/`[ ]` each; the before/after RTF pair from Step 1; the auto-RESET
log lines verbatim, labelled **demo-only automatic operator**; and the
seed, so the run can be replayed. Remove nothing that is already in the
file.

Update `m6/README_m6.md`: the floor's dimensions and two road classes,
the twelve stations, the `demo` command in the run order, the
`--auto-reset` flag with its ruling, and the two new videos.

- [ ] **Step 6: Commit**

```bash
git add -A m6/ assets/m6-fleet/
git status --short
git commit -m "m6.6: four trucks working one floor, measured"
```

---

## Self-Review Notes

Spec coverage checked section by section: §3.1-3.3 → Task 1 and Task 3;
§3.4-3.5 → Task 1; §3.6 → Task 2; §4.1 is a decision not to change code
and needs no task; §4.2 → Task 4; §4.3 → Task 5; §4.4 → Task 6; §5 →
Task 7; §6.1 → Task 8; §6.2 → Task 10 Step 4; §7 → Task 10 Step 3; §8's
file list is the File Structure table above; §9 → the tests inside Tasks
1-6; §10's risks are handled at Task 10 Step 1 (RTF), Task 2's
`test_pick_aisle_centreline_clears_a_scanner_by_the_protective_band`
(one-lane aisle), Task 1's `AHEAD_M`/`ABEAM_M` (bay-mouth tail) and
Task 4's fairness assertion (spawn lean).

Names used across tasks and defined once: `stations.HALL`,
`stations.STATIONS`, `stations.OBSTACLES` (Task 1); `route.RING_X`,
`RING_Y`, `SPINE_X`, `PICK_Y`, `NORTH_X`, `SOUTH_X`, `PICK_X`, `LEG_Y`,
`build_graph`, `dijkstra`, `nearest_node`, `plan_route` (Task 2);
`work_generator.WorkGenerator`, `.next_pair`, `.pairs`, `MIN_LEN_M`
(Task 5); `fleet_cli.demo_plan`, `cmd_demo` (Task 6);
`scripted_writer.latch_watch`, `RESET_HOLD_S` (Task 7).
