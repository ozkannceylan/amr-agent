"""film_core.py's arithmetic - and the film's config invariants.

NO ROS AND NO GAZEBO. The follow camera's smoothing, the gz request
bodies, the timeline-to-segments plan and the ffmpeg command are
arithmetic this file pins. Beyond the arithmetic, two INVARIANTS the
config promises are locked here:

  - film.shots names exactly pallet_cycle.plan_cycle()'s legs, in
    order. The cut refuses a timeline that drifts from the table at
    run time; this is the same refusal before the run, because a film
    tool that silently shoots half a cycle is worse than one that
    refuses to start.
  - the camera SDFs agree with config.yaml on every topic, rate and
    pixel they share. A camera SDF and a config key that name the same
    thing differently are two cameras, and the cut would find out at
    1280x720.
"""
import math
import os
import xml.etree.ElementTree as ET

import pytest

yaml = pytest.importorskip("yaml")

import film_core as fc                                # noqa: E402
import pallet_cycle as cy                            # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
_REPO = os.path.normpath(os.path.join(_M5V3, os.pardir))


def load_yaml(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_sdf(name):
    root = ET.parse(os.path.join(_M5V3, "gazebo", name)).getroot()
    sensor = root.find(".//sensor")
    image = sensor.find("camera/image")
    static = root.find("model/static")
    return {
        "model": root.find("model").get("name"),
        "static": static is not None and static.text.strip() == "true",
        "topic": sensor.find("topic").text.strip(),
        "rate": int(sensor.find("update_rate").text),
        "hfov": float(sensor.find("camera/horizontal_fov").text),
        "width": int(image.find("width").text),
        "height": int(image.find("height").text),
    }


CFG = load_yaml("config.yaml")
FILM = CFG["film"]


# ---- the smoothing ----

def test_follow_step_moves_toward_the_truck_without_overshoot():
    assert fc.follow_step(0.0, 0.0, 10.0, -4.0, 0.5) == (5.0, -2.0)
    assert fc.follow_step(5.0, -2.0, 10.0, -4.0, 0.5) == (7.5, -3.0)


def test_follow_step_at_alpha_one_lands_on_the_truck():
    assert fc.follow_step(1.0, 1.0, 4.0, 9.0, 1.0) == (4.0, 9.0)


@pytest.mark.parametrize("alpha", [0.0, -0.1, 1.0001])
def test_follow_step_refuses_an_impossible_alpha(alpha):
    with pytest.raises(ValueError):
        fc.follow_step(0.0, 0.0, 1.0, 1.0, alpha)


def test_config_smoothing_is_inside_the_tested_band():
    assert 0.0 < float(FILM["follow_smooth"]) <= 1.0


# ---- the gz request bodies ----

def test_parse_pose_pitch_down_matches_the_follow_quaternion():
    pose = fc.parse_pose("0 0 7 0 1.5707963267948966 0")
    assert (pose["qx"], pose["qy"], pose["qz"], pose["qw"]) == pytest.approx(
        fc._Q_DOWN, abs=1e-9)


def test_parse_pose_quaternion_is_always_normal():
    pose = fc.parse_pose("12.5 3.0 9.0 0 -0.979 3.141")
    norm = sum(pose[k] ** 2 for k in ("qx", "qy", "qz", "qw"))
    assert norm == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("text", ["1 2 3", "1 2 3 4 5 6 7", ""])
def test_parse_pose_refuses_anything_but_six_fields(text):
    with pytest.raises(ValueError):
        fc.parse_pose(text)


def test_pose_request_carries_name_position_and_orientation():
    body = fc.pose_request("film_follow", 1.5, -2.25, 7.0, fc._Q_DOWN)
    assert 'name: "film_follow"' in body
    assert "x: 1.500000000" in body
    assert "y: -2.250000000" in body
    assert "z: 7.000000000" in body
    assert "w: 0.707106781" in body


def test_create_request_carries_the_pose_not_the_sdf():
    pose = fc.parse_pose(FILM["dock_pose"])
    body = fc.create_request("m5_ver3\\gazebo\\film_dock.sdf",
                             "film_dock", pose)
    assert 'sdf_filename: "m5_ver3/gazebo/film_dock.sdf"' in body
    assert 'name: "film_dock"' in body
    assert "x: 12.5" in body


# ---- the shot table ----

def test_shot_table_reads_pip_as_a_boolean():
    table = fc.shot_table([{"leg": "a", "cam": "follow", "pip": "true"},
                           {"leg": "b", "cam": "dock", "pip": "false"},
                           {"leg": "c", "cam": "dock"}])
    assert table == [("a", "follow", True),
                     ("b", "dock", False),
                     ("c", "dock", False)]


def test_film_shots_name_exactly_plan_cycles_legs_in_order():
    """The INVARIANT the config comment promises: one row per leg.

    A pallet_cycle leg with no shot is a leg the film silently skips;
    a shot naming a leg that no longer exists is a refusal at cut time
    that this pins BEFORE the rig is even on.
    """
    table = fc.shot_table(FILM["shots"])
    assert [row[0] for row in table] == [
        step["leg"] for step in cy.plan_cycle()]


@pytest.mark.parametrize("cam", ["follow", "dock"])
def test_shot_table_names_only_filming_cameras(cam):
    assert all(row[1] in ("follow", "dock") for row in fc.shot_table(
        FILM["shots"]))


# ---- the plan ----

def _timeline(legs, start=100.0, gap=30.0, end=None):
    t = start
    rows = []
    for leg in legs:
        rows.append({"leg": leg, "t": t})
        t += gap
    return {"cycle_start": start,
            "cycle_end": t if end is None else end,
            "outcome": "done", "legs": rows}


def test_plan_segments_is_continuous_and_holds_the_tail():
    table = [("transit", "follow", False), ("dock", "dock", True)]
    plan = fc.plan_segments(_timeline(["transit", "dock"]), table,
                            lead_s=4.0, tail_s=4.0)
    assert plan["lead"] == [96.0, 100.0]
    assert plan["segments"][0] == {"leg": "transit", "cam": "follow",
                                   "start": 100.0, "end": 130.0,
                                   "pip": False}
    assert plan["segments"][1]["end"] == 160.0 + 4.0
    # no gaps, no overlaps
    assert plan["segments"][0]["end"] == plan["segments"][1]["start"]
    assert plan["duration"] == plan["segments"][-1]["end"] - plan["lead"][0]


def test_plan_segments_pip_windows_follow_their_segments():
    table = [("a", "follow", True), ("b", "dock", False), ("c", "dock",
                                                           True)]
    plan = fc.plan_segments(_timeline(["a", "b", "c"]), table, 4.0, 4.0)
    assert plan["pip_windows"] == [[100.0, 130.0], [160.0, 194.0]]


def test_plan_segments_refuses_legs_the_table_does_not_name():
    table = [("transit", "follow", False), ("dock", "dock", True)]
    with pytest.raises(ValueError, match="shot table"):
        fc.plan_segments(_timeline(["transit"]), table, 4.0, 4.0)


def test_plan_segments_refuses_a_cycle_that_did_not_finish():
    table = [("transit", "follow", False)]
    timeline = _timeline(["transit"])
    timeline["outcome"] = "stopped"
    with pytest.raises(ValueError, match="outcome"):
        fc.plan_segments(timeline, table, 4.0, 4.0)


# ---- the ffmpeg command ----

def _plan():
    table = [("transit", "follow", False), ("dock", "dock", True)]
    return fc.plan_segments(_timeline(["transit", "dock"]), table,
                            4.0, 4.0), table


def test_ffmpeg_argv_shifts_every_camera_by_its_own_first_frame():
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4",
               "vehicle": "v.mp4"}
    offsets = {"wide": 90.0, "follow": 80.0, "dock": 85.0,
               "vehicle": 87.0}
    argv = fc.ffmpeg_argv(plan, sources, offsets, "out.mp4", 15, 0.25,
                          24)
    graph = argv[argv.index("-filter_complex") + 1]
    assert "trim=6.000:10.000" in graph       # lead, wide offset 90
    assert "trim=20.000:50.000" in graph      # transit, follow offset 80
    assert "trim=45.000:79.000" in graph       # dock, offset 85, +4 tail
    assert "concat=n=3:v=1:a=0[main]" in graph
    # pip windows on the film's own clock: wall 130-96 .. 164-96
    assert "between(t,34.000,68.000)" in graph
    assert argv[0] == "ffmpeg" and argv[-1] == "out.mp4"
    assert argv.count("-i") == 4


def test_ffmpeg_argv_without_the_vehicle_camera_has_no_overlay():
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    argv = fc.ffmpeg_argv(plan, sources, {}, "out.mp4", 15, 0.25, 24)
    graph = argv[argv.index("-filter_complex") + 1]
    assert "[out]" not in argv
    assert "overlay" not in graph
    assert "concat" in graph


def test_ffmpeg_argv_refuses_a_main_camera_that_is_missing():
    plan, _ = _plan()
    with pytest.raises(ValueError, match="no recording"):
        fc.ffmpeg_argv(plan, {"wide": "w.mp4"}, {}, "out.mp4", 15, 0.25,
                       24)


# ---- the camera SDFs against config ----

@pytest.mark.parametrize("sdf_name, model_key, topic_key", [
    ("film_follow.sdf", "follow_model", "follow_topic"),
    ("film_dock.sdf", "dock_model", "dock_topic"),
    ("film_overhead.sdf", "wide_model", "wide_topic"),
])
def test_camera_sdfs_agree_with_config(sdf_name, model_key, topic_key):
    sdf = load_sdf(sdf_name)
    # A camera SDF and a config key that name the same topic
    # differently are two cameras, and the cut finds out at 1280x720.
    assert sdf["model"] == FILM[model_key]
    assert sdf["topic"] == FILM[topic_key]
    assert sdf["rate"] == int(FILM["rate_hz"])
    assert sdf["width"] == int(FILM["width_px"])
    assert sdf["height"] == int(FILM["height_px"])


def test_the_follow_camera_is_movable_and_the_fixed_ones_are_static():
    follow = load_sdf("film_follow.sdf")
    dock = load_sdf("film_dock.sdf")
    wide = load_sdf("film_overhead.sdf")
    assert follow["static"] is False
    assert dock["static"] is True
    assert wide["static"] is True


def test_the_dock_pose_is_six_fields_over_the_s5_bay():
    fields = [float(v) for v in FILM["dock_pose"].split()]
    assert len(fields) == 6
    x, y, z, _r, pitch, _yaw = fields
    # over the +x side of the bay, high enough to clear the 4 m racks
    assert 9.0 < x < 16.0 and 2.0 < y < 5.0
    assert z > 5.0
    # pitched DOWN toward the bay
    assert pitch < 0.0
    # and the follow camera looks straight down from its config height
    assert float(FILM["follow_height_m"]) == pytest.approx(7.0)


def test_film_record_budget_covers_one_cycle_with_slack():
    assert 600 <= int(FILM["record_budget_s"]) <= 2400