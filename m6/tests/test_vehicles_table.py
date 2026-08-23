"""The VEHICLES table and the per-vehicle contract."""
import math
import os
import re

import pytest

import field_eval
import follower
import route
import status_contract as sc
from stations import STATIONS

_GAZEBO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "gazebo"))
_WORLD_SDF = os.path.join(_GAZEBO, "warehouse_ver3.sdf")
_TRUCK_SDF = os.path.join(_GAZEBO, "forklift_ver2", "model.sdf")

#: The safety scan plane, from forklift_ver2/model.sdf's side view. Every
#: solid below is kept or dropped on whether this height passes through it:
#: the forks (z 0.05..0.10) and the chassis (0.20..0.70) are invisible to
#: the safety scanners and the mast, the carriage and the three wheels are
#: not, which is not something a bounding box would have told us.
_SCAN_Z = 0.15


def _first_pose(body):
    """The first <pose> in a block, as six floats. Missing means zero."""
    found = re.search(r"<pose>([^<]+)</pose>", body)
    if not found:
        return [0.0] * 6
    return ([float(v) for v in found.group(1).split()] + [0.0] * 6)[:6]


def _boxes(text, scan_z, frame=(0.0, 0.0)):
    """[(name, xmin, xmax, ymin, ymax)] for the collisions the plane cuts.

    <box> and <cylinder> only, and a cylinder becomes its bounding square:
    a scanner reading is a distance to a surface, and squaring a wheel can
    only report it nearer than it is.
    """
    out = []
    for link in re.finditer(r'<link name="([^"]+)">(.*?)</link>', text, re.S):
        body = link.group(2)
        head = body.split("<collision", 1)[0].split("<visual", 1)[0]
        lp = _first_pose(head.split("<inertial", 1)[0])
        for coll in re.finditer(
                r'<collision name="([^"]+)">(.*?)</collision>', body, re.S):
            cbody = coll.group(2)
            cp = _first_pose(cbody)
            # Only a link that OWNS a solid has to be square to the world:
            # the three scanner links carry a mount yaw and no collision at
            # all, and refusing them would refuse the vehicle.
            assert lp[3] == lp[4] == lp[5] == 0.0, link.group(1)
            assert cp[5] == 0.0, coll.group(1)
            box = re.search(r"<box>\s*<size>([^<]+)</size>", cbody)
            cyl = re.search(r"<cylinder>\s*<radius>([\d.]+)</radius>\s*"
                            r"<length>([\d.]+)</length>", cbody)
            if box:
                assert cp[3] == cp[4] == 0.0, coll.group(1)
                sx, sy, sz = [float(v) for v in box.group(1).split()]
            elif cyl:
                # The wheels are laid on their side (roll pi/2), so their
                # roll and pitch are NOT refused - the bounding square is
                # the same square whichever way the axis points, and this
                # asserts it is the larger of the two dimensions so that
                # squaring a wheel can only ever over-state it.
                radius, length = float(cyl.group(1)), float(cyl.group(2))
                assert 2.0 * radius >= length, coll.group(1)
                sx = sy = sz = 2.0 * radius
            else:
                continue             # the ground plane, which is the floor
            x = frame[0] + lp[0] + cp[0]
            y = frame[1] + lp[1] + cp[1]
            z = lp[2] + cp[2]
            if not (z - sz / 2.0 <= scan_z <= z + sz / 2.0):
                continue
            out.append((link.group(1) + "/" + coll.group(1),
                        x - sx / 2.0, x + sx / 2.0,
                        y - sy / 2.0, y + sy / 2.0))
    return out


def _world_solids():
    """Everything in the hall a safety scanner can see, from the SDF.

    Read out of warehouse_ver3.sdf rather than out of stations.OBSTACLES:
    that tuple is documented as the SDF's shadow and nothing tests it
    against the file, so a wall that moved in the world and not in the
    shadow would leave this guard passing on stale numbers. A model's own
    <pose> is composed in. Models with no scan-plane collision (station
    paint, the overhead camera, the floor plane) are skipped: the camera
    is pitched to look down, the paints carry a yaw, and neither is a
    solid a scanner can see.
    """
    text = open(_WORLD_SDF, encoding="utf-8").read()
    out = []
    for model in re.finditer(r'<model name="([^"]+)">(.*?)</model>',
                             text, re.S):
        body = model.group(2)
        mp = _first_pose(body.split("<link", 1)[0])
        solids = list(_boxes(body, _SCAN_Z, (mp[0], mp[1])))
        if not solids:
            continue
        assert mp[3] == mp[4] == mp[5] == 0.0, model.group(1)
        for solid in solids:
            out.append((model.group(1) + "/" + solid[0],) + solid[1:])
    return out


def _truck_solids():
    """The truck's own scan-plane contour, in the MODEL frame."""
    return _boxes(open(_TRUCK_SDF, encoding="utf-8").read(), _SCAN_Z)


def _mounts():
    """{name: (x, y)} for the three safety scanners, from the truck SDF."""
    text = open(_TRUCK_SDF, encoding="utf-8").read()
    return {m.group(1): tuple(_first_pose(m.group(2))[:2])
            for m in re.finditer(
                r'<link name="safety_scanner_(\w+)_link">(.*?)</link>',
                text, re.S)}


def _place(rects, x, y, yaw):
    """Model-frame rectangles put down at a pose, axis-aligned again."""
    cos, sin = math.cos(yaw), math.sin(yaw)
    out = []
    for name, x0, x1, y0, y1 in rects:
        xs = [x + cos * cx - sin * cy
              for cx, cy in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
        ys = [y + sin * cx + cos * cy
              for cx, cy in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
        out.append((name, min(xs), max(xs), min(ys), max(ys)))
    return out


def _nearest(xy, rects):
    """(distance, name) from a point to the nearest rectangle."""
    best = (math.inf, None)
    for name, x0, x1, y0, y1 in rects:
        dx = max(x0 - xy[0], 0.0, xy[0] - x1)
        dy = max(y0 - xy[1], 0.0, xy[1] - y1)
        best = min(best, (math.hypot(dx, dy), name))
    return best


def _pose(vid):
    spawn = sc.VEHICLES[vid]["spawn"]
    return (float(spawn["x"]), float(spawn["y"]), float(spawn["yaw"]))


def test_table_has_exactly_the_four_vehicles_with_disjoint_ports():
    """Four since M6.5 - f3 and f4 joined with the fleet.

    The membership assertion is spelled out rather than counted: this
    table IS the fleet, and a vehicle appearing or vanishing from it
    should have to be written down here, in a test, on purpose.
    """
    assert set(sc.VEHICLES) == {"f1", "f2", "f3", "f4"}
    ports = [v[k] for v in sc.VEHICLES.values()
             for k in ("plc_port", "sensor_port")]
    assert len(ports) == len(set(ports))
    assert 5100 not in ports and 5101 not in ports   # step5's family


def test_every_vehicle_carries_a_whole_spawn_pose():
    """A pose short of a key spawns a truck at the origin, or not at all.

    The launch file and m6.sh's `home` both index all four of these by
    name, and neither has anywhere to put a KeyError: the launch dies at
    import for every vehicle, and home prints a shrug over a live
    simulator. Generic over the table, so a fifth vehicle is covered the
    moment it is added.
    """
    for vid, v in sc.VEHICLES.items():
        assert set(v["spawn"]) == {"x", "y", "z", "yaw"}, vid
        for key, text in v["spawn"].items():
            assert isinstance(text, str), (vid, key)
            float(text)          # every one of them is a number in a string


def test_no_vehicle_is_parked_where_the_fleet_has_to_drive():
    """The poses against the floor plan, which M6.5 got wrong once.

    An idle truck HOLDS the node under it (floor.py `_hold_standing`)
    and `IDLE_HOLD_S` gives that node back after 30 s with the truck
    still standing on it (`_idle_floor`, which says so in its own
    warning). A spawn pose is therefore a fleet decision, not a scenic
    one: park a truck on the junction a spur station is reached through
    and the first half-minute of every run has the fleet's busiest node
    held by a truck with no task, and the next half-minute has the fleet
    routing somebody through a truck it can no longer see, with the
    scanners left as the stop.

    Two rules, both read off the graph rather than off a list of
    coordinates, so a station that moves in stations.py moves these with
    it:

    1. NO SPUR JUNCTION. A spur station is a node with exactly one
       neighbour (`floor.spur_entry`'s own test) and that neighbour is
       the only way in and out of it. f3 and f4 sat on the two worst of
       them - (-8.0, 5.65) serves S6 and S8, (8.0, 5.65) serves S5, S7
       and S9 - until this test existed.
    2. ON A STATION, OR CLEAR OF ONE. f1 parks exactly on S1, which is a
       legitimate place for a truck to stand. What is not legitimate is
       parking 0.40 m off a station point: that is the trap in
       (12.0, 5.65), quiet floor by the ledger and the middle of S5 by
       the tape measure.
    """
    graph = route.build_graph()
    spur_junctions = {
        junction
        for s in STATIONS.values()
        for junction in graph.get((s["x"], s["y"]), ())
        if len(graph[(s["x"], s["y"])]) == 1}
    station_points = {(s["x"], s["y"]) for s in STATIONS.values()}
    assert spur_junctions, "the graph grew no spurs - this test proves nothing"

    for vid, v in sorted(sc.VEHICLES.items()):
        xy = (float(v["spawn"]["x"]), float(v["spawn"]["y"]))
        assert xy not in spur_junctions, (
            "{} spawns on {}, the only way in to a spur station"
            .format(vid, xy))
        for point in station_points:
            gap = math.hypot(xy[0] - point[0], xy[1] - point[1])
            assert gap == 0.0 or gap >= 1.0, (
                "{} spawns {:.2f} m from station {} - either stand on it "
                "or stand clear of it".format(vid, gap, point))


def test_the_world_the_scanners_see_was_actually_read():
    """The parser above, guarded - a regex that matches nothing passes
    every clearance test underneath it silently.

    The three counts are structural, not a transcript of the file: four
    perimeter walls and no door posts (ver3 has no dock cut), the truck's
    mast, carriage and three wheels, and exactly the three safety scanners
    the PLC has channels for. 29 named obstacles plus 4 walls is 33
    scan-plane boxes; a vanished rack run drops that count.
    """
    world = _world_solids()
    names = [n for n, *_ in world]
    assert sum("Wall" in n for n in names) == 4, names
    assert sum("DoorGap" in n for n in names) == 0, names
    assert len(world) >= 33, "the rack runs vanished from the parse"

    truck = _truck_solids()
    assert sorted(n.split("/")[0] for n, *_ in truck) == [
        "carriage", "drive_wheel", "mast",
        "rear_wheel_left", "rear_wheel_right"], truck

    assert sorted(_mounts()) == ["back", "left", "right"]


def test_no_parked_truck_starts_inside_its_own_warning_field():
    """The rule M6.5's acceptance run bought at full price.

    Task 4 chose f3's and f4's poses off the ROUTE GRAPH and validated
    them with the raw closest lidar return - which is the truck's own
    structure on every truck and therefore identical on all four. It never
    read field_eval. Both poses stood a FORK-CORNER scanner inside its own
    2.5 m warning field against an end wall: f3 1.82 m off the west wall,
    f4 2.32 m off the east, measured live 2026-08-22. A truck whose
    warning field is occupied gets V_Limit 300 from the F-program, so both
    crawled at 0.30 m/s from their first cycle - and neither the graph
    rules above nor the raw-range check could see it.

    THE THRESHOLD IS THE RE-CLEARING ONE, NOT THE FIELD RADIUS. A Device
    starts violated, like a cold OSSD, so a spawned truck has to clear its
    field from the wrong side and needs WF + HYSTERESIS_M to do it. Both
    numbers are field_eval's; nothing here writes a distance down.

    THE OTHER THREE TRUCKS ARE SOLIDS. At four vehicles a parked truck is
    part of the floor plan for its neighbours, and their contour is read
    from the vehicle SDF at the scan plane - which is why the forks (below
    the plane) and the chassis (above it) are not in it.
    """
    _, warn = field_eval.FIELDS[1]
    need = warn + field_eval.HYSTERESIS_M
    world, truck, mounts = _world_solids(), _truck_solids(), _mounts()

    for vid in sorted(sc.VEHICLES):
        x, y, yaw = _pose(vid)
        floor = list(world)
        for other in sorted(sc.VEHICLES):
            if other != vid:
                ox, oy, oyaw = _pose(other)
                floor += [(other + ":" + n, a, b, c, d) for n, a, b, c, d
                          in _place(truck, ox, oy, oyaw)]
        for name, (mx, my) in sorted(mounts.items()):
            sx = x + math.cos(yaw) * mx - math.sin(yaw) * my
            sy = y + math.sin(yaw) * mx + math.cos(yaw) * my
            gap, what = _nearest((sx, sy), floor)
            assert gap > need, (
                "{} parks with its {} scanner {:.3f} m from {} - inside "
                "its own warning field, so it creeps at the PLC's 300 mm/s "
                "from the first cycle ({:.2f} m needed to clear it)"
                .format(vid, name, gap, what, need))


def test_every_parked_truck_can_turn_out_of_its_pose():
    """At rest is not enough: the first MOVE is what latched f3.

    f3 shipped 2.50 m off the west wall and its transport's first leg
    turned south. It crept west into the turn and put its right scanner
    0.971 m from that wall - PROTECTIVE - eight seconds into the
    acceptance run of 2026-08-22, and its hulk held the west cross aisle
    for the remaining ten minutes. The pose was inside no obstacle, on a
    quiet node, and unable to leave.

    THE SWING ALLOWANCE IS THE PURSUIT'S OWN TURNING CIRCLE, not a number
    chosen to make the poses pass. Pure pursuit commands R = L_d / 2 sin a,
    tightest at a = pi/2, so R = LOOKAHEAD_M / 2 = 0.60 m - wider than the
    vehicle's mechanical minimum (wheelbase / tan(steer limit) = 0.28 m),
    which is why the pursuit and not the steering stop is the binding
    number. Add the scanner ring radius, because the swing is about the
    truck centre and the scanners sit off it, and the protective threshold
    the field has to clear from its cold start.

    THE RULE PREDICTS THE RUN IT WAS WRITTEN FROM. f3's old pose scores
    2.500 - 0.821 - 0.600 = 1.079 m of scanner clearance through the turn
    against the 1.20 m it needs; the truck measured 0.971 m at the latch.
    A rule 0.108 m off the event it explains is worth keeping.

    The other trucks are NOT solids here. A parked truck moves; a wall does
    not, and this asks whether the FLOOR lets a truck turn around.
    """
    prot, _ = field_eval.FIELDS[1]
    ring = max(math.hypot(*m) for m in _mounts().values())
    swing = follower.LOOKAHEAD_M / 2.0
    need = prot + field_eval.HYSTERESIS_M + ring + swing
    world = _world_solids()

    for vid in sorted(sc.VEHICLES):
        x, y, _yaw = _pose(vid)
        gap, what = _nearest((x, y), world)
        assert gap >= need, (
            "{} parks {:.3f} m from {}: turning out of it brings a scanner "
            "within {:.3f} m of it, and the protective field needs "
            "{:.2f} m ({:.2f} m of floor needed at the pose)"
            .format(vid, gap, what, gap - ring - swing,
                    prot + field_eval.HYSTERESIS_M, need))


def test_the_writers_vehicle_flag_offers_exactly_the_table():
    """The table's one duplication, guarded against drift.

    windows/m6.py spells its --vehicle choices as a literal tuple and
    cannot read them from here: status_contract binds its per-vehicle
    constants once, at first import, off env VEHICLE - and the writer
    sets that env FROM the parsed flag, so the parser has to be built
    before this module may be imported at all. This test is the price of
    that ordering, and it has been paid once: f3 and f4 reached the table
    at M6.5 and this failed until they reached m6.VEHICLE_IDS too. A
    fifth vehicle must reach that tuple the same way.

    tools/scripted_writer.py is NOT a third spelling: it builds its own
    parser but takes m6.VEHICLE_IDS for the choices, so guarding this one
    tuple guards both writers.
    """
    import m6            # conftest stamped VEHICLE, so importing is safe

    assert tuple(m6.VEHICLE_IDS) == tuple(sorted(sc.VEHICLES))
    # argparse keeps no public accessor for a built action.
    choices = m6._parser._option_string_actions["--vehicle"].choices
    assert tuple(choices) == tuple(sorted(sc.VEHICLES))


def test_contract_namespaces_every_ros_name():
    c = sc.contract("f2")
    assert c["status_topic"] == "/f2/plc/status"
    assert c["fields_topic"] == "/f2/safety/fields"
    assert c["encoders_topic"] == "/f2/safety/encoders"
    assert c["scan_topic"].format("back") == \
        "/f2/gz/safety_scanner_back/measurement"
    assert c["vehicle_cmd_topic"] == "/f2/vehicle/cmd_vel"
    assert c["hmi_cmd_topic"] == "/f2/hmi/cmd_vel"
    assert c["plc_port"] == 5120 and c["sensor_port"] == 5121


def test_module_constants_follow_the_env_vehicle():
    # conftest sets VEHICLE=f1 for the whole suite.
    assert sc.VID == "f1"
    assert sc.STATUS_TOPIC == "/f1/plc/status"
    assert sc.PLC_PORT == 5110 and sc.SENSOR_PORT == 5111
    assert sc.CONFIG_PATH.replace("\\", "/").endswith(
        "m6/vehicles/f1/config.yaml")


def test_unknown_vehicle_refused():
    with pytest.raises(SystemExit):
        sc.contract("f9")


def test_env_free_from_import_reads_the_table():
    # The launch file (both vehicles from one process) and
    # tools/instantiate_vehicle.py import this module with no VEHICLE.
    # A subprocess because conftest sets VEHICLE for the whole suite,
    # which takes the guarded branch and hides the else branch entirely.
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "VEHICLE"}
    ipc = os.path.dirname(os.path.abspath(sc.__file__))
    src = (
        "import sys; sys.path.insert(0, {!r});"
        "from status_contract import VEHICLES, contract;"
        "print(sorted(VEHICLES), contract('f2')['status_topic'])"
    ).format(ipc)
    done = subprocess.run([sys.executable, "-c", src], env=env,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == \
        "['f1', 'f2', 'f3', 'f4'] /f2/plc/status"


def test_env_free_per_vehicle_constant_still_refused():
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "VEHICLE"}
    ipc = os.path.dirname(os.path.abspath(sc.__file__))
    src = (
        "import sys; sys.path.insert(0, {!r});"
        "import status_contract; status_contract.STATUS_TOPIC"
    ).format(ipc)
    done = subprocess.run([sys.executable, "-c", src], env=env,
                          capture_output=True, text=True)
    assert done.returncode != 0
    assert "env VEHICLE is not set" in done.stderr
    assert "STATUS_TOPIC" in done.stderr
