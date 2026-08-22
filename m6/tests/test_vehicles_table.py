"""The VEHICLES table and the per-vehicle contract."""
import math

import pytest

import route
import status_contract as sc
from stations import STATIONS


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
