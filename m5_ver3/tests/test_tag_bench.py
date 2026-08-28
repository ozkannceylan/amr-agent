"""tag_bench.py - AprilTag pose vs the furniture's own marker, no ROS.

F5 Task 1's detection accuracy at staging range is a number. The
recorder that captures detections lives in WSL; the scorer is here so
a Windows pytest can refuse a typed invention of the marker pose and
a leftover CSV whose poses are still in the camera frame.
"""
import math
import os

import pytest

yaml = pytest.importorskip("yaml")

import tag_bench as tb                                # noqa: E402
import tag_core as tc                                 # noqa: E402
import evidence_core as ec                            # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
_REPO = os.path.normpath(os.path.join(_M5V3, os.pardir))


def load_yaml(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def cfg():
    return load_yaml("config.yaml")


def test_expected_marker_is_tag_cores_pose_not_a_typed_invention(cfg):
    ipc = os.path.join(_REPO, "m6", "ipc")
    import sys
    if ipc not in sys.path:
        sys.path.insert(0, ipc)
    import stations
    s5 = stations.STATIONS[cfg["dock"]["station"]]
    dock = cfg["dock"]
    geo = tc.station_geometry(
        s5["x"], s5["y"], s5["yaw"],
        marker_ahead_m=float(dock["marker_ahead_m"]),
        fork_reach_m=float(dock["fork_reach_m"]),
        tip_standoff_m=float(dock["tip_standoff_m"]),
        staging_run_in_m=float(dock["staging_run_in_m"]))
    got = tb.expected_marker_xyz(s5, dock)
    assert got[0] == pytest.approx(geo["marker"][0])
    assert got[1] == pytest.approx(geo["marker"][1])
    assert got[2] == pytest.approx(float(dock["marker_z_m"]))


def test_summarise_is_detection_error_on_every_row():
    expected = (7.0, 2.6, 0.8)
    rows = [
        {"x": 7.0, "y": 2.6, "z": 0.8, "frame": "map", "id": 0},
        {"x": 7.1, "y": 2.6, "z": 0.8, "frame": "map", "id": 0},
    ]
    out = tb.summarise(rows, expected)
    assert out["n"] == 2
    assert out["min_dist_m"] == pytest.approx(0.0)
    assert out["max_dist_m"] == pytest.approx(0.1)
    assert out["mean_dist_m"] == pytest.approx(0.05)


def test_summarise_refuses_an_empty_capture():
    with pytest.raises(ValueError, match="no detections"):
        tb.summarise([], (7.0, 2.6, 0.8))


def test_an_empty_detection_array_is_not_a_detection():
    class Msg:
        detections = []
    assert tb.message_has_tag(Msg(), 0) is False


def test_a_detection_array_counts_only_the_configured_tag_id():
    class Det:
        def __init__(self, tag_id):
            self.id = tag_id
    class Msg:
        def __init__(self, ids):
            self.detections = [Det(i) for i in ids]
    assert tb.message_has_tag(Msg([1, 2]), 0) is False
    assert tb.message_has_tag(Msg([0]), 0) is True


def test_record_wait_keys_on_the_tag_id_not_an_empty_array():
    src = open(os.path.join(_M5V3, "tools", "tag_bench.py"),
               encoding="utf-8").read()
    wait = src.split("def record(", 1)[1].split("def main(", 1)[0]
    assert "message_has_tag" in wait
    assert 'got["first"] = True' in wait
    first_at = wait.index('got["first"] = True')
    has_at = wait.index("message_has_tag")
    assert has_at < first_at, (
        "record() must see the configured tag before treating a "
        "message as the first detection; empty AprilTagDetectionArray "
        "frames arrive at camera rate with nothing in them")


def test_summarise_refuses_a_pose_that_is_not_in_the_map_frame():
    rows = [{"x": 0.0, "y": 0.0, "z": 1.0, "frame": "pallet_cam_link",
             "id": 0}]
    with pytest.raises(ValueError, match="map"):
        tb.summarise(rows, (7.0, 2.6, 0.8))


def test_transform_xyz_identity_leaves_the_point():
    got = tb.transform_xyz((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0),
                           (1.0, 2.0, 3.0))
    assert got == pytest.approx((1.0, 2.0, 3.0))


def test_transform_xyz_yaw_pi_over_two_sends_x_to_y():
    half = math.pi / 4.0
    q = (0.0, 0.0, math.sin(half), math.cos(half))
    got = tb.transform_xyz((10.0, 0.0, 0.0), q, (1.0, 0.0, 0.0))
    assert got[0] == pytest.approx(10.0)
    assert got[1] == pytest.approx(1.0)
    assert got[2] == pytest.approx(0.0)


def test_expected_in_map_is_mapframe_to_map_of_the_world_xy():
    frame = ec.MapFrame(math.pi, -17.0, 10.0)
    world = (7.0, 2.6, 0.8)
    got = tb.expected_marker_in_map(world, frame)
    mx, my = frame.to_map(7.0, 2.6)
    assert got[0] == pytest.approx(mx)
    assert got[1] == pytest.approx(my)
    assert got[2] == pytest.approx(0.8)
    assert abs(got[0] - world[0]) > 10.0


def test_a_map_pose_scored_against_world_xy_is_the_origin_offset():
    frame = ec.MapFrame(math.pi, -17.0, 10.0)
    world = (7.0, 2.6, 0.8)
    mapped = tb.expected_marker_in_map(world, frame)
    rows = [{"x": mapped[0], "y": mapped[1], "z": mapped[2],
             "frame": "map", "id": 0}]
    assert tb.summarise(rows, world)["mean_dist_m"] > 10.0
    assert tb.summarise(rows, mapped)["mean_dist_m"] == pytest.approx(0.0)


def test_analyse_scores_the_map_pose_not_the_world_xy():
    src = open(os.path.join(_M5V3, "tools", "tag_bench.py"),
               encoding="utf-8").read()
    body = src.split("def analyse(", 1)[1].split("def record(", 1)[0]
    assert "expected_marker_in_map" in body
    assert "_map_frame" in body
