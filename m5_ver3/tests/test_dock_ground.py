"""F5 Task 1 ground pins that are not furniture.py's: the colour
stream, the image-bridge line, the derived staging goal.

NO ROS AND NO GAZEBO. The colour topic is spelled in model.sdf; the
bridge line is spelled in m5v3.sh; the staging pose is spelled in
config.yaml and recomputed here from tag_core + stations.py so a typed
invention cannot silently replace the derivation.
"""
import math
import os
import sys

import pytest

yaml = pytest.importorskip("yaml")

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


def test_the_colour_topic_is_the_cameras_own_image_stream(cfg):
    sdf = open(os.path.join(_M5V3, "gazebo", "forklift_ver3",
                            "model.sdf"), encoding="utf-8").read()
    assert "<topic>/forklift/gz/cam</topic>" in sdf
    assert cfg["topics"]["cam_image"] == "/forklift/gz/cam/image"
    assert cfg["topics"]["cam_depth"] == "/forklift/gz/cam/depth_image"


def test_the_image_bridge_carries_colour_as_well_as_depth():
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    assert "topics.cam_image" in script
    assert 'image_bridge "$CFG_TOPICS_CAM_DEPTH" "$CFG_TOPICS_CAM_IMAGE"' \
        in script


def test_the_staging_goal_is_tag_cores_pose_not_a_typed_invention(cfg):
    ipc = os.path.join(_REPO, "m6", "ipc")
    if ipc not in sys.path:
        sys.path.insert(0, ipc)
    import stations
    s5 = stations.STATIONS["S5"]
    dock = cfg["dock"]
    geo = tc.station_geometry(
        s5["x"], s5["y"], s5["yaw"],
        marker_ahead_m=float(dock["marker_ahead_m"]),
        fork_reach_m=float(dock["fork_reach_m"]),
        tip_standoff_m=float(dock["tip_standoff_m"]),
        staging_run_in_m=float(dock["staging_run_in_m"]))
    goal = cfg["nav"]["goals"]["station_s5_staging"]
    assert goal.get("derived") is True
    assert goal.get("route_node") is False
    assert goal.get("case_only") is True
    assert int(goal["repeat"]) == 0
    assert float(goal["x"]) == pytest.approx(geo["staging"][0])
    assert float(goal["y"]) == pytest.approx(geo["staging"][1])
    assert float(goal["travel_yaw_rad"]) == pytest.approx(s5["yaw"],
                                                          abs=1e-7)


def test_the_stage_s5_case_repeats_the_staging_goal_three_times(cfg):
    case = cfg["nav"]["cases"]["stage_s5"]
    assert case["goal"] == "station_s5_staging"
    assert int(case["repeat"]) == 3
    assert "then" not in case


def test_apriltag_ros_family_is_dock_family_without_the_tag_prefix(cfg):
    assert "tag" + cfg["apriltag"]["family"] == cfg["dock"]["family"]
    assert int(cfg["dock"]["tag_id"]) == 0
    assert float(cfg["dock"]["size_m"]) == pytest.approx(0.40)


def test_apriltag_params_file_is_addressed_to_the_node_m5v3_starts(cfg):
    params = load_yaml("apriltag.yaml")
    assert cfg["apriltag"]["node_name"] in params
    node = params[cfg["apriltag"]["node_name"]]["ros__parameters"]
    assert node["family"] == cfg["apriltag"]["family"]
    assert float(node["size"]) == pytest.approx(float(cfg["dock"]["size_m"]))
    assert node["tag"]["ids"] == [int(cfg["dock"]["tag_id"])]
    assert node["detector"]["refine"] is True
    assert node["detector"]["debug"] is False
    assert isinstance(node["detector"]["refine"], bool)
    assert isinstance(node["detector"]["debug"], bool)
    assert node["tag"]["frames"] == [cfg["apriltag"]["tag_frame"]]
    assert cfg["apriltag"]["tag_frame"] == "{}_{}".format(
        cfg["dock"]["family"], int(cfg["dock"]["tag_id"]))


def test_the_vendored_lib_path_is_the_debian_multiarch_one(cfg):
    # MEASURED on this rig 2026-08-28: ros-jazzy-apriltag unpacks
    # libapriltag.so under lib/x86_64-linux-gnu, not lib/. A path that
    # dropped the multiarch triplet would pass every offline test and
    # fail only when tag_model.py write tried to ctypes-load it.
    assert cfg["apriltag"]["lib"] == "lib/x86_64-linux-gnu/libapriltag.so"


def test_dock_is_refused_without_nav():
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    assert "--dock) DOCK=true" in script
    assert '"$NAV" = true ] || refuse' in script.split(
        'if [ "$DOCK" = true ]; then', 1)[1].split("fi", 1)[0]
    assert "--dock was given with --nav" in script


def test_apriltag_is_spawned_inside_the_dock_guard():
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    assert "spawn apriltag" in script
    guard = script.split('if [ "$DOCK" = true ]; then')
    assert any("spawn apriltag" in block.split("\nfi", 1)[0]
               for block in guard[1:]), (
        "spawn apriltag is not inside an `if [ \"$DOCK\" = true ]` block")
    assert "-r image_rect:=\"$CFG_TOPICS_CAM_IMAGE\"" in script
    assert "-r camera_info:=\"$CFG_TOPICS_CAM_INFO\"" in script
    assert "-r detections:=\"$CFG_TOPICS_APRILTAG_DETECTIONS\"" in script


def test_dock_places_furniture_with_the_create_service_not_a_world_edit():
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    assert 'python3 "$M5V3/tools/furniture.py" place' in script
    truck_at = script.index("spawn_truck")
    furn_at = script.index('python3 "$M5V3/tools/furniture.py" place')
    assert truck_at < furn_at
    assert "warehouse_ver3.sdf" not in script[furn_at:furn_at + 400]


def test_dock_label_is_a_sixth_line_on_the_state_file():
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    assert 'echo "dock=$dock"' in script
    assert "on@$(md5sum \"$APRILTAG_PARAMS\"" in script
    drive = open(os.path.join(_M5V3, "tools", "drive_goal.py"),
                 encoding="utf-8").read()
    assert '"dock"' in drive.split("fields.get(k, \"UNLABELLED\")", 1)[1][:400]


def test_cam_mount_is_the_sdf_pose_not_a_typed_invention(cfg):
    pose = ec.sdf_link_pose(os.path.join(_M5V3, "gazebo", "forklift_ver3",
                                         "model.sdf"),
                            cfg["frames"]["pallet_cam"])
    mount = cfg["vehicle"]["cam_mount"]
    for i, axis in enumerate(("x", "y", "z", "roll", "pitch", "yaw")):
        assert float(mount[axis]) == pytest.approx(pose[i], abs=1e-6)


def test_detections_topic_is_config_not_a_literal(cfg):
    assert cfg["topics"]["apriltag_detections"].startswith("/")
    assert "detections" in cfg["topics"]["apriltag_detections"]


def test_cam_optical_rpy_is_rep103_body_to_optical(cfg):
    opt = cfg["vehicle"]["cam_optical"]
    half_pi = math.pi / 2.0
    assert float(opt["roll"]) == pytest.approx(-half_pi)
    assert float(opt["pitch"]) == pytest.approx(0.0)
    assert float(opt["yaw"]) == pytest.approx(-half_pi)
    got = tc.rpy_rotate((0.0, 0.0, 1.0),
                        float(opt["roll"]), float(opt["pitch"]),
                        float(opt["yaw"]))
    assert got[0] == pytest.approx(1.0)
    assert got[1] == pytest.approx(0.0, abs=1e-9)
    assert got[2] == pytest.approx(0.0, abs=1e-9)


def test_gz_frame_id_is_the_optical_frame_not_the_link(cfg):
    sdf = open(os.path.join(_M5V3, "gazebo", "forklift_ver3",
                            "model.sdf"), encoding="utf-8").read()
    optical = cfg["frames"]["pallet_cam_optical"]
    assert optical != cfg["frames"]["pallet_cam"]
    assert "<gz_frame_id>{}</gz_frame_id>".format(optical) in sdf
    assert sdf.count("<gz_frame_id>{}</gz_frame_id>".format(
        cfg["frames"]["pallet_cam"])) == 0


def test_dock_publishes_the_optical_static_tf():
    script = open(os.path.join(_M5V3, "m5v3.sh"), encoding="utf-8").read()
    assert "spawn camopt" in script
    guard = script.split('if [ "$DOCK" = true ]; then')
    assert any("spawn camopt" in block.split("\nfi", 1)[0]
               for block in guard[1:]), (
        "spawn camopt is not inside an `if [ \"$DOCK\" = true ]` block")
    assert "--frame-id \"$CFG_FRAMES_PALLET_CAM\"" in script
    assert "--child-frame-id \"$CFG_FRAMES_PALLET_CAM_OPTICAL\"" in script
    assert "--roll \"$CFG_VEHICLE_CAM_OPTICAL_ROLL\"" in script
