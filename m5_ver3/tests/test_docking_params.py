"""F5 Task 2 pins: docking.yaml, docks.yaml, the cmd_vel remap.

NO ROS AND NO GAZEBO. The plugin type, the curvature bound, the
staging offset sign, dock_backwards and the map-frame dock pose are
all recomputed from config.yaml + tag_core + the committed
registration. A typed invention in docking.yaml or docks.yaml fails
here rather than as a truck that docks 31 m off.
"""
import math
import os
import sys

import pytest

yaml = pytest.importorskip("yaml")

import dock_core as dc                                # noqa: E402
import evidence_core as ec                            # noqa: E402
import map_register                                   # noqa: E402
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
def docking():
    return load_yaml("docking.yaml")


@pytest.fixture(scope="module")
def docks():
    return load_yaml("docks.yaml")


def test_docking_yaml_is_addressed_to_the_nodes_m5v3_starts(cfg, docking):
    assert cfg["docking"]["node_name"] in docking
    assert cfg["docking"]["lifecycle"]["node_name"] in docking


def test_the_plugin_is_simple_non_charging_dock(cfg, docking):
    params = docking[cfg["docking"]["node_name"]]["ros__parameters"]
    name = cfg["docking"]["plugin_name"]
    assert params["dock_plugins"] == [name]
    plugin = params[name]
    assert plugin["plugin"] == cfg["docking"]["plugin_type"]
    assert plugin["plugin"] == "opennav_docking::SimpleNonChargingDock"
    assert plugin["use_external_detection_pose"] is True


def test_dock_backwards_and_curvature_bound_match_config(cfg, docking):
    params = docking[cfg["docking"]["node_name"]]["ros__parameters"]
    assert params["dock_backwards"] is True
    ctrl = params["controller"]
    vmin = float(cfg["dock"]["v_linear_min"])
    vmax = float(cfg["dock"]["v_linear_max"])
    radius = float(cfg["dock"]["min_radius_m"])
    assert ctrl["v_linear_min"] == pytest.approx(vmin)
    assert ctrl["v_linear_max"] == pytest.approx(vmax)
    assert ctrl["v_angular_max"] == pytest.approx(
        dc.v_angular_max(vmin, radius))
    plugin = params[cfg["docking"]["plugin_name"]]
    assert plugin["staging_x_offset"] == pytest.approx(
        float(cfg["dock"]["staging_x_offset"]))
    assert plugin["external_detection_translation_x"] == pytest.approx(
        float(cfg["dock"]["external_detection_translation_x"]))
    assert plugin["docking_threshold"] == pytest.approx(
        float(cfg["dock"]["docking_threshold"]))
    assert plugin["docking_threshold"] == pytest.approx(
        float(cfg["dock"]["station_class_m"]))
    assert ctrl["slowdown_radius"] == pytest.approx(
        float(cfg["dock"]["slowdown_radius"]))
    # isDocked is XY. If slowdown_radius >= docking_threshold the
    # tricycle reaches v≈0, ω=ω_max before the plugin can latch.
    assert float(cfg["dock"]["slowdown_radius"]) < float(
        cfg["dock"]["docking_threshold"])
    assert params["dock_approach_timeout"] == pytest.approx(
        float(cfg["dock"]["dock_approach_timeout"]))
    assert ctrl["use_collision_detection"] is False
    assert ctrl["use_collision_detection"] == (
        str(cfg["dock"]["use_collision_detection"]).lower() == "true")


def test_undock_tolerances_are_prestaging_not_charger_breakaway(cfg, docking):
    params = docking[cfg["docking"]["node_name"]]["ros__parameters"]
    assert float(params["undock_linear_tolerance"]) == pytest.approx(
        float(cfg["dock"]["dock_prestaging_tolerance"]))
    assert float(params["undock_angular_tolerance"]) == pytest.approx(
        float(cfg["dock"]["undock_angular_tolerance"]))
    assert float(cfg["dock"]["undock_angular_tolerance"]) > 0.05


def test_docks_yaml_pose_is_the_docked_base_link_in_map(cfg, docks):
    ipc = os.path.join(_REPO, "m6", "ipc")
    if ipc not in sys.path:
        sys.path.insert(0, ipc)
    import stations
    s5 = stations.STATIONS[cfg["dock"]["station"]]
    pose = dc.docked_world(s5, cfg["dock"])
    path = os.path.join(_REPO, cfg["map"]["dir"], cfg["map"]["name"],
                        cfg["map"]["registration"]["file"])
    frame = ec.MapFrame.from_registration(map_register.load_registration(path))
    mx, my, myaw = frame.to_map(pose["x"], pose["y"], pose["pose_yaw"])
    row = docks["docks"][cfg["docking"]["dock_id"]]
    assert row["type"] == cfg["docking"]["plugin_name"]
    assert row["frame"] == cfg["frames"]["map"]
    assert row["id"] == str(cfg["dock"]["tag_id"])
    assert row["pose"][0] == pytest.approx(mx, abs=1e-5)
    assert row["pose"][1] == pytest.approx(my, abs=1e-5)
    assert row["pose"][2] == pytest.approx(myaw, abs=1e-5)


def test_m5v3_spawns_the_docking_server_inside_the_dock_guard():
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    assert "spawn docking" in script
    assert "spawn detdock" in script
    guard = script.split('if [ "$DOCK" = true ]; then')
    assert any("spawn docking" in block.split("\nfi", 1)[0]
               for block in guard[1:]), (
        "spawn docking is not inside an `if [ \"$DOCK\" = true ]` block")
    assert "-r cmd_vel:=\"$CFG_TOPICS_CMD_VEL\"" in script or \
        '-r cmd_vel:="$CFG_TOPICS_CMD_VEL"' in script
    assert "detected_dock_pose:=" in script
    assert "dock_database:=" in script


def test_the_cmd_vel_remap_is_the_smoother_input(cfg):
    assert cfg["topics"]["cmd_vel"] == "/cmd_vel"
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    docking = script.split("spawn docking", 1)[1].split("\n\n", 1)[0]
    assert "CFG_TOPICS_CMD_VEL" in docking
    assert "cmd_vel_smoothed" not in docking


def test_sweep_nominates_the_docking_server():
    common = open(os.path.join(_M5V3, "tools", "_common.sh"),
                  encoding="utf-8").read()
    assert '"opennav_docking"' in common or '"docking_server"' in common
    assert "detected_dock.py" in common


def test_dock_bench_required_keys_resolve(cfg):
    tools = os.path.join(_M5V3, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import _common
    import dock_bench as db
    loaded = _common.load_config(db.TOOL, db.REQUIRED_KEYS)
    assert loaded.s("topics.undock_robot") == cfg["topics"]["undock_robot"]
    assert loaded.s("docking.dock_id") == cfg["docking"]["dock_id"]
    source = open(os.path.join(tools, "dock_bench.py"), encoding="utf-8").read()
    assert 'sub.add_parser("undock")' in source
    assert 'sub.add_parser("stage")' in source
    assert "_align_for_tag" in source
    assert "authority=dock" in source
    assert "cancel_all_goals_async" not in source
    assert "_cancel_action" in source
    assert "_align_for_tag" in source
