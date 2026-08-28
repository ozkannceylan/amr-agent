"""furniture.py's spawn request - F5 Task 1.

NO GAZEBO AND NO WORLD EDIT. Constraint 21: AprilTag markers are
spawned into the running world the same way the truck is
(sdf_filename + pose on /world/<name>/create). These tests pin the
request string and the pose arithmetic so a marker that faced the
wrong way, or a write into warehouse_ver3.sdf, would fail here rather
than as a camera that cannot see.
"""
import math
import os

import pytest

yaml = pytest.importorskip("yaml")

import furniture as furn                              # noqa: E402
import tag_core as tc                                 # noqa: E402
import tag_model as tm                                # noqa: E402

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
    import sys
    if ipc not in sys.path:
        sys.path.insert(0, ipc)
    import stations
    return stations.STATIONS["S5"]


def test_describe_needs_nothing_but_config(capsys):
    import _common
    loaded = _common.load_config(furn.TOOL, furn.REQUIRED_KEYS)
    assert furn.describe(loaded) == 0
    out = capsys.readouterr().out
    assert "tag36h11_0" in out
    assert "warehouse_ver3" not in out


def test_the_create_request_names_a_file_not_an_inline_sdf():
    pose = {"x": 7.0, "y": 2.6, "z": 0.8, "yaw": math.pi / 2.0}
    req = furn.create_request("/tmp/tag36h11_0.sdf", "tag36h11_0", pose)
    assert "sdf_filename:" in req
    assert "sdf:" not in req.split("sdf_filename")[0]
    assert 'name: "tag36h11_0"' in req
    assert "allow_renaming: false" in req
    assert "x: 7.0" in req or "x: 7.000" in req
    assert "orientation:" in req
    assert "w:" in req and "z:" in req


def test_the_spawn_pose_is_tag_cores_marker_facing_the_truck(cfg, s5):
    geo = tc.station_geometry(
        s5["x"], s5["y"], s5["yaw"],
        marker_ahead_m=float(cfg["dock"]["marker_ahead_m"]),
        fork_reach_m=float(cfg["dock"]["fork_reach_m"]),
        tip_standoff_m=float(cfg["dock"]["tip_standoff_m"]),
        staging_run_in_m=float(cfg["dock"]["staging_run_in_m"]))
    pose = tm.spawn_pose(geo["marker"], s5["yaw"],
                         float(cfg["dock"]["marker_z_m"]))
    assert pose["x"] == pytest.approx(7.0)
    assert pose["y"] == pytest.approx(2.60)
    assert pose["z"] == pytest.approx(0.80)
    assert pose["yaw"] == pytest.approx(math.pi / 2.0)


def test_yaw_quaternion_is_a_rotation_about_world_up():
    x, y, z, w = tc.yaw_quaternion(math.pi / 2.0)
    assert x == pytest.approx(0.0)
    assert y == pytest.approx(0.0)
    assert z == pytest.approx(math.sin(math.pi / 4.0))
    assert w == pytest.approx(math.cos(math.pi / 4.0))


def test_the_model_path_is_under_this_tree_not_the_world_file(cfg):
    path = furn.model_path(cfg["dock"])
    assert path.endswith("tag36h11_0.sdf")
    assert "m5_ver3" in path.replace("\\", "/")
    assert "warehouse_ver3" not in path


def test_furniture_never_opens_the_committed_world_file():
    src = open(furn.__file__, encoding="utf-8").read()
    assert "warehouse_ver3.sdf" not in src
    assert "/create" in src or "create_request" in src


def test_config_keys_the_spawner_reads_all_exist(cfg):
    import _common
    loaded = _common.Config(furn.TOOL, cfg)
    for key in furn.REQUIRED_KEYS:
        loaded.raw(key)
