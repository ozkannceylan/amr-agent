"""dock_core.py's arithmetic - F5 Task 2.

NO ROS AND NO GAZEBO. Curvature bounds, the docked pose, the staging
offset sign and the AprilTag-to-dock translation are numbers; they live
where a test on the Windows python can reach them.
"""
import math
import os
import sys

import pytest

yaml = pytest.importorskip("yaml")

import dock_core as dc                                # noqa: E402
import drive_goal                                     # noqa: E402
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
def s5():
    ipc = os.path.join(_REPO, "m6", "ipc")
    if ipc not in sys.path:
        sys.path.insert(0, ipc)
    import stations
    return stations.STATIONS["S5"]


def test_pose_yaw_is_drive_goals_half_turn():
    for travel in (-math.pi / 2, 0.0, math.pi / 2, 2.4):
        assert dc.pose_yaw(travel) == pytest.approx(drive_goal.pose_yaw(travel))


def test_v_over_omega_at_the_bound_is_the_plant_radius(cfg):
    radius = float(cfg["dock"]["min_radius_m"])
    vmin = float(cfg["dock"]["v_linear_min"])
    wmax = dc.v_angular_max(vmin, radius)
    assert wmax == pytest.approx(vmin / radius)
    assert dc.curvature_respects_radius(vmin, wmax, radius)
    assert not dc.curvature_respects_radius(vmin, wmax * 1.01, radius)


def test_the_yaml_omega_cap_is_that_bound(cfg):
    radius = float(cfg["dock"]["min_radius_m"])
    vmin = float(cfg["dock"]["v_linear_min"])
    assert float(cfg["dock"]["v_angular_max"]) == pytest.approx(
        dc.v_angular_max(vmin, radius))
    nav = load_yaml("nav2.yaml")
    planned = nav["planner_server"]["ros__parameters"]["GridBased"][
        "minimum_turning_radius"]
    assert radius == pytest.approx(float(planned))


def test_docked_world_is_tag_core_plus_the_half_turn(cfg, s5):
    dock = cfg["dock"]
    pose = dc.docked_world(s5, dock)
    geo = tc.station_geometry(
        s5["x"], s5["y"], s5["yaw"],
        marker_ahead_m=float(dock["marker_ahead_m"]),
        fork_reach_m=float(dock["fork_reach_m"]),
        tip_standoff_m=float(dock["tip_standoff_m"]),
        staging_run_in_m=float(dock["staging_run_in_m"]))
    assert pose["x"] == pytest.approx(geo["docked"][0])
    assert pose["y"] == pytest.approx(geo["docked"][1])
    assert pose["travel_yaw"] == pytest.approx(s5["yaw"])
    assert pose["pose_yaw"] == pytest.approx(dc.pose_yaw(s5["yaw"]))
    forks = tc.approach_unit(s5["yaw"])
    body_x = (math.cos(pose["pose_yaw"]), math.sin(pose["pose_yaw"]))
    assert body_x[0] == pytest.approx(-forks[0], abs=1e-9)
    assert body_x[1] == pytest.approx(-forks[1], abs=1e-9)


def test_staging_x_offset_is_positive_because_plus_x_points_at_the_aisle(
        cfg, s5):
    dock = cfg["dock"]
    pose = dc.docked_world(s5, dock)
    geo = tc.station_geometry(
        s5["x"], s5["y"], s5["yaw"],
        marker_ahead_m=float(dock["marker_ahead_m"]),
        fork_reach_m=float(dock["fork_reach_m"]),
        tip_standoff_m=float(dock["tip_standoff_m"]),
        staging_run_in_m=float(dock["staging_run_in_m"]))
    offset = dc.staging_x_offset(
        pose["pose_yaw"], geo["staging"], geo["docked"])
    assert offset == pytest.approx(float(dock["staging_run_in_m"]))
    assert offset > 0.0
    assert float(dock["staging_x_offset"]) == pytest.approx(offset)


def test_tag_to_dock_translation_is_negative_into_the_tag(cfg):
    # SimpleChargingDock's converted +X points into the tag (package
    # default translation_x is -0.20). The docked base_link sits on
    # the camera side, so the offset is minus (fork_reach + standoff).
    dock = cfg["dock"]
    tx = dc.tag_to_dock_translation_x(
        float(dock["fork_reach_m"]), float(dock["tip_standoff_m"]))
    assert tx == pytest.approx(
        -(float(dock["fork_reach_m"]) + float(dock["tip_standoff_m"])))
    assert tx < 0.0
    assert float(dock["external_detection_translation_x"]) == pytest.approx(tx)
    assert float(dock["external_detection_translation_y"]) == pytest.approx(0.0)


def test_dock_backwards_is_true_because_forks_are_minus_x(cfg):
    # F5's plan wrote `dock_backwards: false (forks-first)`. On this
    # truck forks are model -x, so forks-first is reverse. False would
    # command +x, counterweight-first, camera looking at the aisle.
    assert str(cfg["dock"]["dock_backwards"]).lower() == "true"


def test_overlap_of_nav_and_dock_is_refused():
    assert dc.overlap_refused(True, True) is True
    assert dc.overlap_refused(True, False) is False
    assert dc.overlap_refused(False, True) is False
    assert dc.overlap_refused(False, False) is False


def test_failed_to_detect_is_a_named_error():
    assert dc.named_error(904) == "FAILED_TO_DETECT_DOCK"
    assert dc.named_error(903) == "FAILED_TO_STAGE"
    assert dc.named_error(901) == "DOCK_NOT_IN_DB"
    assert dc.named_error(0) == "NONE"


def test_align_omega_turns_toward_the_docked_yaw():
    # Nav2's position latch leaves heading 0.67–1.37 rad (T1). A
    # feasible arc is v_min with this ω; spin-in-place is not a plant
    # command.
    assert dc.align_omega(0.0, 0.4, 0.08) == pytest.approx(0.08)
    assert dc.align_omega(0.4, 0.0, 0.08) == pytest.approx(-0.08)
    assert dc.align_omega(0.0, 0.0, 0.08) == pytest.approx(0.0)
    assert dc.curvature_respects_radius(0.10, dc.align_omega(0.0, 1.0, 0.08), 1.25)


def test_station_class_is_the_f4_quarter_metre(cfg):
    assert float(cfg["dock"]["station_class_m"]) == pytest.approx(0.25)
    # isDocked uses this number, not the package's 0.05 m charger default.
    assert float(cfg["dock"]["docking_threshold"]) == pytest.approx(
        float(cfg["dock"]["station_class_m"]))
    assert float(cfg["dock"]["slowdown_radius"]) < float(
        cfg["dock"]["docking_threshold"])


def test_arrival_scores_xy_and_heading_against_the_docked_pose():
    target = {"x": 7.0, "y": 4.575, "pose_yaw": math.pi / 2}
    dx, dy, dist, dyaw = dc.arrival(target, (7.0, 4.575, math.pi / 2))
    assert dist == pytest.approx(0.0)
    assert dyaw == pytest.approx(0.0)
    _, _, dist, dyaw = dc.arrival(target, (7.10, 4.575, math.pi / 2 + 0.2))
    assert dist == pytest.approx(0.10)
    assert dyaw == pytest.approx(0.2)
