"""The world paint agrees with stations.py, and stays paint.

The SDF is hand-written; stations.py is the one home for the poses.
This suite is the coupling: move a station in one place only and it
fails, loudly, before Gazebo ever shows the drift.
"""
import math
import os
import re

import stations

_SDF = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "gazebo", "warehouse_ver2.sdf"))

_BLOCK = re.compile(
    r'<model name="Station(S\d+)Paint">(.*?)</model>', re.S)
_POSE = re.compile(r"<pose>([-\d.eE ]+)</pose>")


def _blocks():
    with open(_SDF, encoding="utf-8") as handle:
        return {sid: body for sid, body in _BLOCK.findall(handle.read())}


def test_exactly_the_ten_station_ids_are_painted():
    assert set(_blocks()) == set(stations.STATIONS)


def test_painted_pose_matches_stations_py():
    for sid, body in _blocks().items():
        x, y = [float(v) for v in _POSE.search(body).group(1).split()[:2]]
        assert abs(x - stations.STATIONS[sid]["x"]) < 1e-3, sid
        assert abs(y - stations.STATIONS[sid]["y"]) < 1e-3, sid


def test_paint_has_no_collision_element():
    # Collision here would put a disc under the wheels and a return in
    # every scan. The charge-bay markings set the recipe: visuals only.
    for sid, body in _blocks().items():
        assert "<collision" not in body, sid


def test_paint_is_static_and_flat():
    for sid, body in _blocks().items():
        assert "<static>true</static>" in body, sid
        # Every visual sits within 8 mm of the floor: under both scan
        # planes, same as the 6 mm charge-bay paint.
        for pose in _POSE.findall(body)[1:]:
            assert float(pose.split()[2]) <= 0.008, (sid, pose)


def test_stations_sit_on_free_floor():
    for sid, s in stations.STATIONS.items():
        for name, xmin, xmax, ymin, ymax in stations.OBSTACLES:
            dx = max(xmin - s["x"], 0.0, s["x"] - xmax)
            dy = max(ymin - s["y"], 0.0, s["y"] - ymax)
            assert math.hypot(dx, dy) >= 0.6, (sid, name)
        xw, xe, ys, yn = stations.HALL
        assert min(s["x"] - xw, xe - s["x"],
                   s["y"] - ys, yn - s["y"]) >= 0.7, sid
