"""tag_core.py's arithmetic - F5 Task 1.

NO ROS, NO GAZEBO, NO APRILTAG LIBRARY. The bitmap is driven by a
hand-sized family so a reversed bit order fails here rather than as a
camera that cannot see. The station poses are recomputed off
m6/ipc/stations.py (read-only) and config.yaml dock:, and the
plannability margin is recomputed off nav2.yaml's grown footprint - the
same two files a staging pose that sat inside START_OCCUPIED would have
been written against.
"""
import ast
import math
import os
import subprocess
import sys

import pytest

yaml = pytest.importorskip("yaml")

import tag_core as tc                                 # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
_REPO = os.path.normpath(os.path.join(_M5V3, os.pardir))


def load_yaml(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def cfg():
    return load_yaml("config.yaml")


@pytest.fixture(scope="module")
def dock(cfg):
    return cfg["dock"]


@pytest.fixture(scope="module")
def s5():
    ipc = os.path.join(_REPO, "m6", "ipc")
    if ipc not in sys.path:
        sys.path.insert(0, ipc)
    import stations
    return stations.STATIONS["S5"]


@pytest.fixture(scope="module")
def grown_polygon():
    tree = load_yaml("nav2.yaml")
    text = tree["global_costmap"]["global_costmap"]["ros__parameters"][
        "footprint"]
    return [tuple(p) for p in ast.literal_eval(text)]


def geo_of(dock, s5):
    return tc.station_geometry(
        s5["x"], s5["y"], s5["yaw"],
        marker_ahead_m=float(dock["marker_ahead_m"]),
        fork_reach_m=float(dock["fork_reach_m"]),
        tip_standoff_m=float(dock["tip_standoff_m"]),
        staging_run_in_m=float(dock["staging_run_in_m"]))


# ----------------------------------------------------------------------
# the bitmap
# ----------------------------------------------------------------------

def test_the_bitmap_is_driven_by_the_family_definition_not_a_copied_table():
    rows = tc.bitmap(4, [1, 2, 1, 2], [1, 1, 2, 2], 4, 6, 0b1010)
    assert len(rows) == 6
    assert rows[0] == [tc.WHITE] * 6
    assert rows[1][1] == tc.BLACK
    assert rows[2][2] == tc.WHITE
    assert rows[2][3] == tc.BLACK
    assert rows[3][2] == tc.WHITE
    assert rows[3][3] == tc.BLACK


def test_a_reversed_bit_order_would_paint_the_wrong_squares():
    rows = tc.bitmap(4, [1, 2, 1, 2], [1, 1, 2, 2], 4, 6, 0b1010)
    reversed_msb_last = tc.bitmap(4, [1, 2, 1, 2], [1, 1, 2, 2], 4, 6, 0b0101)
    assert rows[2][2] != reversed_msb_last[2][2]


def test_apriltag_ros_size_is_the_black_square(dock):
    size = float(dock["size_m"])
    width = int(dock["width_at_border"])
    total = int(dock["total_width"])
    assert tc.cell_size(size, width) == pytest.approx(size / width)
    assert tc.tile_size(size, width, total) == pytest.approx(
        size / width * total)
    assert tc.tile_size(size, width, total) > size


def test_v_is_positive_UP_so_a_mirrored_tag_cannot_silently_decode():
    rows = tc.bitmap(4, [1, 2, 1, 2], [1, 1, 2, 2], 4, 6, 0b1010)
    black = tc.cells(rows, 0.40, 4)
    assert max(c[1] for c in black) == pytest.approx(1.5 * 0.10)


# ----------------------------------------------------------------------
# station geometry, pinned to S5 and to config.yaml
# ----------------------------------------------------------------------

def test_the_marker_faces_the_oncoming_truck(s5):
    yaw = tc.face_yaw(s5["yaw"])
    assert yaw == pytest.approx(math.pi / 2.0)
    ux, uy = tc.approach_unit(s5["yaw"])
    fx, fy = math.cos(yaw), math.sin(yaw)
    assert fx == pytest.approx(-ux)
    assert fy == pytest.approx(-uy)


def test_the_showcase_station_is_m6s_S5(dock, s5):
    assert dock["station"] == "S5"
    assert s5["name"] == "PICK-NE-1"
    assert s5["x"] == pytest.approx(7.0)
    assert s5["y"] == pytest.approx(4.25)


def test_the_marker_sits_on_the_pick_bay_back_panel(dock, s5):
    geo = geo_of(dock, s5)
    assert geo["marker"][0] == pytest.approx(s5["x"])
    assert geo["marker"][1] == pytest.approx(2.60)
    assert abs(s5["y"] - geo["marker"][1]) == pytest.approx(
        float(dock["marker_ahead_m"]))


def test_fork_reach_is_the_same_number_as_the_monitor_hull(cfg, dock):
    assert float(dock["fork_reach_m"]) == pytest.approx(
        abs(float(cfg["monitor"]["geometry"]["fork_tip_x_m"])))


def test_the_docked_pose_puts_the_tips_one_standoff_short_of_the_marker(
        dock, s5):
    geo = geo_of(dock, s5)
    assert geo["docked_to_marker_m"] == pytest.approx(
        float(dock["fork_reach_m"]) + float(dock["tip_standoff_m"]))
    assert geo["staging_to_marker_m"] == pytest.approx(
        geo["docked_to_marker_m"] + float(dock["staging_run_in_m"]))


def test_staging_is_straight_back_along_the_spur(dock, s5):
    geo = geo_of(dock, s5)
    ux, uy = geo["unit"]
    dx = geo["docked"][0] - geo["staging"][0]
    dy = geo["docked"][1] - geo["staging"][1]
    assert dx == pytest.approx(ux * float(dock["staging_run_in_m"]))
    assert dy == pytest.approx(uy * float(dock["staging_run_in_m"]))


# ----------------------------------------------------------------------
# plannability: staging is outside START_OCCUPIED, docked is inside
# ----------------------------------------------------------------------

def test_the_staging_pose_clears_the_grown_footprints_trap_zone(
        dock, s5, grown_polygon):
    geo = geo_of(dock, s5)
    margin = tc.staging_margin(grown_polygon, geo["staging_to_marker_m"])
    assert margin["margin_m"] > 0.0, (
        "staging pose is inside START_OCCUPIED by {:.3f} m; raise "
        "dock.staging_run_in_m".format(-margin["margin_m"]))


def test_the_docked_pose_is_inside_the_trap_zone_by_construction(
        dock, s5, grown_polygon):
    geo = geo_of(dock, s5)
    docked = tc.staging_margin(grown_polygon, geo["docked_to_marker_m"])
    assert docked["margin_m"] < 0.0, (
        "a docked pose the planner could start from would make undock "
        "unnecessary, and EVIDENCE_NAV_V3.md 20.5 item 3 measured the "
        "opposite")


def test_the_minimum_standoff_is_reach_plus_inscribed(grown_polygon):
    margin = tc.staging_margin(grown_polygon, 10.0)
    assert margin["minimum_standoff_m"] == pytest.approx(
        margin["forward_reach_m"] + margin["inscribed_m"])
    assert margin["forward_reach_m"] == pytest.approx(2.415)


def test_inflation_cost_is_a_collision_inside_the_inscribed_band():
    assert tc.inflation_cost(0.30, 0.6143, 2.60, 1.10) == 253
    assert tc.inflation_cost(2.70, 0.6143, 2.60, 1.10) == 0


def test_selftest_exits_zero():
    path = os.path.join(_M5V3, "tools", "tag_core.py")
    result = subprocess.run(
        [sys.executable, path, "--selftest"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
