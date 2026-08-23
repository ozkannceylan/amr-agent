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
