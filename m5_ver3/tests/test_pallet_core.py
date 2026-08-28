"""pallet_core.py's arithmetic - F5 Task 3.

NO ROS AND NO GAZEBO. Pocket geometry is the fork spacing; attach is a
measured predicate (constraint 23), never contact. A pallet whose
pockets missed the tines would fail here rather than as a joint that
will not take.
"""
import math
import os
import sys

import pytest

yaml = pytest.importorskip("yaml")

import dock_core as dc                                # noqa: E402
import evidence_core as ec                            # noqa: E402
import pallet_core as pc                              # noqa: E402
import tag_core as tc                                 # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
_REPO = os.path.normpath(os.path.join(_M5V3, os.pardir))
_SDF = os.path.join(_M5V3, "gazebo", "forklift_ver3", "model.sdf")


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


def test_fork_spacing_is_the_tine_centres_in_the_model(cfg):
    left = ec.sdf_link_pose(_SDF, "fork_left")
    right = ec.sdf_link_pose(_SDF, "fork_right")
    spacing = pc.fork_spacing_m(left[1], right[1])
    assert spacing == pytest.approx(0.56)
    assert float(cfg["pallet"]["fork_spacing_m"]) == pytest.approx(spacing)
    assert float(cfg["pallet"]["tine_width_m"]) == pytest.approx(0.12)
    assert float(cfg["pallet"]["tine_height_m"]) == pytest.approx(0.05)


def test_pocket_opening_clears_the_tine_on_both_sides(cfg):
    opening = pc.pocket_opening_m(
        float(cfg["pallet"]["tine_width_m"]),
        float(cfg["pallet"]["pocket_clearance_y_m"]))
    assert opening == pytest.approx(0.16)
    assert opening > float(cfg["pallet"]["tine_width_m"])


def test_a_tip_in_the_pocket_attaches_and_a_miss_does_not(cfg):
    pal = cfg["pallet"]
    depth = float(pal["depth_m"])
    opening = pc.pocket_opening_m(
        float(pal["tine_width_m"]), float(pal["pocket_clearance_y_m"]))
    z_min, z_max = pc.pocket_z(
        float(pal["height_m"]), float(pal["deck_thickness_m"]))
    pockets = [
        pc.pocket_aabb(y, opening, depth, z_min, z_max)
        for y in pc.pocket_centres_y(float(pal["fork_spacing_m"]))
    ]
    tips = [(0.0, y, 0.0) for y in pc.pocket_centres_y(float(pal["fork_spacing_m"]))]
    assert pc.attach_ok(
        tips, pockets, 0.0, 0.0,
        float(pal["yaw_max_rad"]), float(pal["height_max_m"]))
    miss = [(0.0, 0.0, 0.0), tips[1]]
    assert not pc.attach_ok(
        miss, pockets, 0.0, 0.0,
        float(pal["yaw_max_rad"]), float(pal["height_max_m"]))


def test_yaw_or_height_out_of_bound_refuses_even_when_xy_is_in(cfg):
    pal = cfg["pallet"]
    opening = pc.pocket_opening_m(
        float(pal["tine_width_m"]), float(pal["pocket_clearance_y_m"]))
    z_min, z_max = pc.pocket_z(
        float(pal["height_m"]), float(pal["deck_thickness_m"]))
    pockets = [
        pc.pocket_aabb(y, opening, float(pal["depth_m"]), z_min, z_max)
        for y in pc.pocket_centres_y(float(pal["fork_spacing_m"]))
    ]
    tips = [(0.0, y, 0.0) for y in pc.pocket_centres_y(float(pal["fork_spacing_m"]))]
    yaw_max = float(pal["yaw_max_rad"])
    z_lim = float(pal["height_max_m"])
    assert not pc.attach_ok(tips, pockets, yaw_max + 0.01, 0.0, yaw_max, z_lim)
    assert not pc.attach_ok(tips, pockets, 0.0, z_lim + 0.001, yaw_max, z_lim)


def test_s5_spawn_sits_between_the_marker_and_the_docked_pose(cfg, s5):
    geo = tc.station_geometry(
        s5["x"], s5["y"], s5["yaw"],
        marker_ahead_m=float(cfg["dock"]["marker_ahead_m"]),
        fork_reach_m=float(cfg["dock"]["fork_reach_m"]),
        tip_standoff_m=float(cfg["dock"]["tip_standoff_m"]),
        staging_run_in_m=float(cfg["dock"]["staging_run_in_m"]))
    pose = pc.spawn_pose(
        geo["marker"], s5["yaw"],
        wall_clearance_m=float(cfg["pallet"]["wall_clearance_m"]),
        depth_m=float(cfg["pallet"]["depth_m"]),
        height_m=float(cfg["pallet"]["height_m"]),
        tag_thickness_m=float(cfg["dock"]["tag_thickness_m"]))
    assert pose["x"] == pytest.approx(7.0)
    assert pose["y"] == pytest.approx(3.03)
    assert pose["z"] == pytest.approx(float(cfg["pallet"]["height_m"]) / 2.0)
    assert pose["yaw"] == pytest.approx(dc.pose_yaw(s5["yaw"]))
    assert geo["marker"][1] < pose["y"] < geo["docked"][1]


def test_docked_tips_land_in_the_pockets(cfg, s5):
    pal = cfg["pallet"]
    geo = tc.station_geometry(
        s5["x"], s5["y"], s5["yaw"],
        marker_ahead_m=float(cfg["dock"]["marker_ahead_m"]),
        fork_reach_m=float(cfg["dock"]["fork_reach_m"]),
        tip_standoff_m=float(cfg["dock"]["tip_standoff_m"]),
        staging_run_in_m=float(cfg["dock"]["staging_run_in_m"]))
    pallet = pc.spawn_pose(
        geo["marker"], s5["yaw"],
        wall_clearance_m=float(pal["wall_clearance_m"]),
        depth_m=float(pal["depth_m"]),
        height_m=float(pal["height_m"]),
        tag_thickness_m=float(cfg["dock"]["tag_thickness_m"]))
    pose_yaw = dc.pose_yaw(s5["yaw"])
    tine_z = 0.075
    opening = pc.pocket_opening_m(
        float(pal["tine_width_m"]), float(pal["pocket_clearance_y_m"]))
    z_min, z_max = pc.pocket_z(
        float(pal["height_m"]), float(pal["deck_thickness_m"]))
    pockets = [
        pc.pocket_aabb(y, opening, float(pal["depth_m"]), z_min, z_max)
        for y in pc.pocket_centres_y(float(pal["fork_spacing_m"]))
    ]
    tips = []
    for y in pc.pocket_centres_y(float(pal["fork_spacing_m"])):
        world = pc.fork_tip_world(
            geo["docked"][0], geo["docked"][1], pose_yaw,
            float(cfg["dock"]["fork_reach_m"]), y, tine_z)
        tips.append(pc.world_to_local(
            (pallet["x"], pallet["y"], pallet["z"]), pallet["yaw"], world))
    yaw_err = pc.wrap_angle(pose_yaw - pallet["yaw"])
    height_err = tine_z - (pallet["z"] + (z_min + z_max) / 2.0)
    assert pc.attach_ok(
        tips, pockets, yaw_err, height_err,
        float(pal["yaw_max_rad"]), float(pal["height_max_m"]))
