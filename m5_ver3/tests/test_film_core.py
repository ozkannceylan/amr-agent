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
import re
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


# ---- the cycle's leg tags ----

def test_bare_leg_strips_the_cycle_number():
    assert fc.bare_leg("c1-transit") == "transit"
    assert fc.bare_leg("c12-lower") == "lower"


@pytest.mark.parametrize("token", [
    "1", "transit", "cx-transit", "c-transit", "c1transit", "", "c1-"])
def test_bare_leg_refuses_anything_that_is_not_a_cycle_tag(token):
    """drive_goal.py prints `leg 1 ...` down the cycle's OWN stdout pipe.

    film_run.py reads that pipe line by line; a parser that took the
    second token of every `leg ` line would stamp `1` into the timeline
    and the cut would then refuse a run that was perfect.
    """
    assert fc.bare_leg(token) is None


def test_every_plan_cycle_leg_survives_its_cycle_tag():
    """The tag pallet_cycle PRINTS must come back as the table's leg name.

    pallet_cycle stamps `c<n>-` onto every leg it prints; the shot
    table and the plan hold bare names. This is the one conversion
    between them, so it is pinned against the real leg list.
    """
    legs = [step["leg"] for step in cy.plan_cycle()]
    for n in (1, 2, 10):
        assert [fc.bare_leg("c{}-{}".format(n, leg))
                for leg in legs] == legs


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


def test_plan_segments_leads_from_where_the_wide_recording_begins():
    """A pre-roll shorter than lead_s leads with what EXISTS.

    Takes 2 and 3 started the cycle 0.6-2.1 s after the wide recorder's
    first frame, so a 4.0 s lead trimmed from -2.1 s; ffmpeg clamped
    that at 0 without a word and every segment after it sat 2.1 s away
    from the printed plan.
    """
    table = [("transit", "follow", False), ("dock", "dock", True)]
    plan = fc.plan_segments(_timeline(["transit", "dock"]), table,
                            lead_s=4.0, tail_s=4.0, lead_floor=98.7)
    assert plan["lead"] == [98.7, 100.0]
    assert plan["duration"] == pytest.approx(164.0 - 98.7)


def test_plan_segments_takes_the_whole_lead_when_the_pre_roll_holds_it():
    table = [("transit", "follow", False), ("dock", "dock", True)]
    timeline = _timeline(["transit", "dock"])
    plan = fc.plan_segments(timeline, table, lead_s=4.0, tail_s=4.0,
                            lead_floor=92.0)
    assert plan["lead"] == [96.0, 100.0]
    # a floor the pre-roll clears changes nothing at all
    assert plan == fc.plan_segments(timeline, table, 4.0, 4.0)


def test_plan_segments_drops_a_lead_the_wide_recording_cannot_hold():
    """A wide recorder that started after the cycle leads with nothing."""
    table = [("transit", "follow", False), ("dock", "dock", True)]
    plan = fc.plan_segments(_timeline(["transit", "dock"]), table, 4.0,
                            4.0, lead_floor=101.0)
    assert plan["lead"] == [100.0, 100.0]


# ---- the recording's own clock ----

def _sidecars(tmp_path, name, t0, frames, fps, sim_per_wall, skip=()):
    """One recording's three sidecars, as film_record.py writes them.

    The recorder feeds a FIXED-fps container one frame per message and
    the messages arrive on the SIM clock: `frames` frames are
    frames/fps of VIDEO, and the wall span that produced them is
    (frames - 1)/fps/sim_per_wall. sim_per_wall 1.0 is a rig keeping up
    with the wall clock; 0.75 is a rig three quarters of the way there.
    """
    path = tmp_path / name
    path.write_bytes(b"")
    t1 = t0 + ((frames - 1) / float(fps)) / sim_per_wall
    for suffix, text in ((".t0", "{:.6f}".format(t0)),
                         (".t1", "{:.6f}".format(t1)),
                         (".n", "{:d}".format(frames))):
        if suffix in skip:
            continue
        (tmp_path / (name + suffix)).write_text(text + "\n")
    return str(path)


def test_clock_measures_the_recordings_own_sim_per_wall_rate():
    """4501 frames at 15 fps span 300 s of video; 400 s of wall made them."""
    clk = fc.clock(100.0, 500.0, 4501, 15)
    assert clk["rate"] == pytest.approx(0.75)
    assert clk["length_s"] == pytest.approx(4501 / 15.0)


def test_clock_at_wall_speed_is_the_bare_first_frame_offset():
    """THE DEGENERACY PIN: a rig keeping up leaves the old arithmetic.

    Every trim in this film used to be `wall - t0`. That is this
    mapping at rate 1.0, and it has to stay exactly that, or a fix for
    a slow rig is a new defect on a fast one.
    """
    clk = fc.clock(100.0, 400.0, 4501, 15)
    assert clk["rate"] == pytest.approx(1.0)
    for wall in (100.0, 137.5, 250.0, 399.0):
        assert fc.video_time(clk, wall) == pytest.approx(wall - 100.0)


def test_video_time_scales_every_wall_second_by_the_rate():
    clk = fc.clock(100.0, 500.0, 4501, 15)
    assert fc.video_time(clk, 100.0) == pytest.approx(0.0)
    assert fc.video_time(clk, 200.0) == pytest.approx(75.0)
    assert fc.video_time(clk, 500.0) == pytest.approx(300.0)


@pytest.mark.parametrize("t0, t1, n", [
    (100.0, 100.0, 4501),      # no wall span to measure the rate against
    (100.0, 90.0, 4501),       # a last frame before the first
    (100.0, 500.0, 1),         # one frame spans no video
    (100.0, 500.0, 0),
])
def test_clock_refuses_a_recording_it_cannot_measure(t0, t1, n):
    with pytest.raises(ValueError):
        fc.clock(t0, t1, n, 15)


def test_read_clock_reads_what_film_record_wrote(tmp_path):
    path = _sidecars(tmp_path, "follow.mp4", 100.0, 4501, 15, 0.75)
    clk = fc.read_clock(path, 15)
    assert clk["t0"] == pytest.approx(100.0)
    assert clk["n"] == 4501
    assert clk["rate"] == pytest.approx(0.75)
    assert clk["length_s"] == pytest.approx(4501 / 15.0)


@pytest.mark.parametrize("absent", [".t0", ".t1", ".n"])
def test_read_clock_refuses_a_recording_missing_a_sidecar(tmp_path, absent):
    """A recording without all three cannot be placed on the film's clock.

    Its footage runs on the sim clock and nothing on disk says how fast
    that clock was, so every trim would be a guess. A named refusal is
    the only honest answer; the alternative is a silent clamp at
    end-of-file, which is a leg that simply is not in the film.
    """
    path = _sidecars(tmp_path, "follow.mp4", 100.0, 4501, 15, 0.75,
                     skip=(absent,))
    with pytest.raises(ValueError, match=absent.replace(".", "[.]")):
        fc.read_clock(path, 15)


def test_read_clock_refuses_a_sidecar_that_is_not_a_number(tmp_path):
    path = _sidecars(tmp_path, "follow.mp4", 100.0, 4501, 15, 0.75)
    (tmp_path / "follow.mp4.n").write_text("many\n")
    with pytest.raises(ValueError, match="many"):
        fc.read_clock(path, 15)


def test_a_synthetic_session_puts_all_four_cameras_on_one_clock(tmp_path):
    """Four recorders start at four wall times on ONE sim clock."""
    clocks = {}
    for cam, t0 in (("follow", 100.0), ("dock", 100.7), ("wide", 99.9),
                    ("vehicle", 100.9)):
        path = _sidecars(tmp_path, cam + ".mp4", t0, 3941, 15, 0.754)
        clocks[cam] = fc.read_clock(path, 15)
    for clk in clocks.values():
        assert clk["rate"] == pytest.approx(0.754, abs=1e-9)
        assert clk["length_s"] == pytest.approx(3941 / 15.0)


# ---- the ffmpeg command ----

def _plan():
    table = [("transit", "follow", False), ("dock", "dock", True)]
    return fc.plan_segments(_timeline(["transit", "dock"]), table,
                            4.0, 4.0), table


def _clocks(sim_per_wall, **first_frames):
    """A clock per named camera, every recording 400 s of video long."""
    return {cam: fc.clock(t0, t0 + (6000 - 1) / 15.0 / sim_per_wall,
                          6000, 15)
            for cam, t0 in first_frames.items()}


def test_ffmpeg_argv_at_wall_speed_shifts_by_the_first_frame_only():
    """rate 1.0 reproduces the pre-mapping trims to the millisecond."""
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4",
               "vehicle": "v.mp4"}
    clocks = _clocks(1.0, wide=90.0, follow=80.0, dock=85.0, vehicle=87.0)
    argv = fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24,
                          0.5)
    graph = argv[argv.index("-filter_complex") + 1]
    assert "trim=6.000:10.000" in graph       # lead, wide offset 90
    assert "trim=20.000:50.000" in graph      # transit, follow offset 80
    assert "trim=45.000:79.000" in graph      # dock, offset 85, +4 tail
    assert "concat=n=3:v=1:a=0[main]" in graph
    # pip windows on the film's own clock: wall 130-96 .. 164-96
    assert "between(t,34.000,68.000)" in graph
    assert argv[0] == "ffmpeg" and argv[-1] == "out.mp4"
    assert argv.count("-i") == 4


def test_ffmpeg_argv_scales_every_trim_into_its_recordings_own_clock():
    """A rig at 0.75 x wall puts 3 s of footage in every 4 s of wall.

    Wall bounds are what the timeline holds; the file holds sim
    seconds. Unscaled, every trim lands 1/rate late and the last legs
    run off the end of the file.
    """
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4",
               "vehicle": "v.mp4"}
    clocks = _clocks(0.75, wide=90.0, follow=80.0, dock=85.0, vehicle=87.0)
    argv = fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24,
                          0.5)
    graph = argv[argv.index("-filter_complex") + 1]
    assert "trim=4.500:7.500" in graph        # lead: (96,100) - 90, x0.75
    assert "trim=15.000:37.500" in graph      # transit: (100,130) - 80
    assert "trim=33.750:59.250" in graph      # dock: (130,164) - 85
    assert "concat=n=3:v=1:a=0[main]" in graph
    # the pip window is the CONCATENATED VIDEO durations, not the wall
    # ones: lead 3.0 s, then transit 22.5 s, then dock 25.5 s
    assert "between(t,25.500,51.000)" in graph


def test_ffmpeg_argv_refuses_a_trim_past_the_end_of_its_recording():
    """The defect's own shape: a bound the file cannot satisfy.

    ffmpeg clamps such a trim at end-of-file without a word, so a leg
    that was never filmed becomes a leg that silently is not there.
    """
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    clocks = _clocks(1.0, wide=90.0, follow=80.0, dock=85.0)
    clocks["dock"] = fc.clock(85.0, 85.0 + (1035 - 1) / 15.0, 1035, 15)
    with pytest.raises(ValueError) as caught:
        fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24, 0.5)
    text = str(caught.value)
    assert "dock" in text          # the segment
    assert "79.000" in text        # the bound it asked for
    assert "69.000" in text        # the length the recording has


def test_ffmpeg_argv_tolerates_a_bound_a_few_frames_past_the_end():
    """A leg's last bound may land inside a frame interval of the end."""
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    clocks = _clocks(1.0, wide=90.0, follow=80.0, dock=85.0)
    clocks["dock"] = fc.clock(85.0, 85.0 + (1184 - 1) / 15.0, 1184, 15)
    fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24, 0.5)
    with pytest.raises(ValueError, match="78.933"):
        fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24, 0.0)


def test_ffmpeg_argv_refuses_a_segment_from_before_its_recording_began():
    """The defect's mirror: a bound EARLIER than the file's first frame.

    ffmpeg clamps a negative trim at 0 as silently as it clamps one
    past the end. The lead is the one shot allowed to come up short,
    and it does not come through here - plan_segments plans it from
    what the wide recording holds.
    """
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    clocks = _clocks(1.0, wide=90.0, follow=80.0, dock=165.0)
    with pytest.raises(ValueError) as caught:
        fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24, 0.5)
    text = str(caught.value)
    assert "dock" in text            # the segment
    assert "-35.000" in text         # the start it asked for
    assert "165.000" in text         # where that recording actually begins
    assert "0.500" in text           # the tolerance it is past


def test_ffmpeg_argv_tolerates_a_start_a_frame_before_the_first_frame():
    """A leg's first bound may land inside a frame interval of t0."""
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    clocks = _clocks(1.0, wide=90.0, follow=80.0, dock=130.3)
    fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24, 0.5)
    with pytest.raises(ValueError, match="-0.300"):
        fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24, 0.0)


def _trim_spans(graph):
    """Every trim=<in>:<out> a filter graph holds, as (start, end)."""
    return [(float(a), float(b)) for a, b in
            re.findall(r"trim=(-?[0-9.]+):(-?[0-9.]+)", graph)]


def test_a_short_lead_is_cut_and_counted_as_the_footage_that_exists():
    """The printed film length is the length of the encode.

    film_length counts what ffmpeg concatenates, so with the wide
    recorder's first frame 1.3 s before the cycle it counts 1.3 wall
    seconds of lead and not 4 - the 2.7 s that were never filmed are
    not in the file and are not in the number.
    """
    table = [("transit", "follow", False), ("dock", "dock", True)]
    plan = fc.plan_segments(_timeline(["transit", "dock"]), table,
                            lead_s=4.0, tail_s=4.0, lead_floor=98.7)
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    clocks = _clocks(0.754, wide=98.7, follow=98.0, dock=98.4)
    argv = fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24,
                          0.5)
    spans = _trim_spans(argv[argv.index("-filter_complex") + 1])
    assert spans[0][0] == 0.0        # the lead starts where the file does
    assert fc.lead_span(plan, sources, clocks) == pytest.approx(
        1.3 * 0.754, abs=1e-6)
    assert fc.film_length(plan, sources, clocks) == pytest.approx(
        sum(end - start for start, end in spans), abs=5e-3)


def test_a_full_lead_is_counted_at_the_recordings_own_rate():
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    clocks = _clocks(0.754, wide=90.0, follow=80.0, dock=85.0)
    assert fc.lead_span(plan, sources, clocks) == pytest.approx(
        4.0 * 0.754, abs=1e-6)
    # no wide recording is no lead, the same rule ffmpeg_argv follows
    assert fc.lead_span(plan, {"follow": "f.mp4"}, clocks) == 0.0


def test_the_pip_stream_ends_with_its_last_window():
    """An inset outlasting the film freezes the film's last frame.

    overlay's framesync runs until EVERY input is done, so an
    untrimmed vehicle recording holds the final frame on screen for
    the difference it is longer - and the encode is then longer than
    film_length, which is a printed number that is not the film.
    """
    table = [("transit", "follow", True), ("dock", "dock", False)]
    plan = fc.plan_segments(_timeline(["transit", "dock"]), table, 4.0, 4.0)
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4",
               "vehicle": "v.mp4"}
    clocks = _clocks(1.0, wide=90.0, follow=80.0, dock=85.0, vehicle=88.0)
    argv = fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24,
                          0.5)
    graph = argv[argv.index("-filter_complex") + 1]
    # lead 4 s, then transit 30 s with the inset over it, then dock
    assert "between(t,4.000,34.000)" in graph
    assert "[3:v]trim=0:34.000,setpts=PTS-STARTPTS,scale=" in graph
    assert fc.film_length(plan, sources, clocks) == pytest.approx(68.0)


def test_ffmpeg_argv_without_the_vehicle_camera_has_no_overlay():
    plan, _ = _plan()
    sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    clocks = _clocks(1.0, wide=90.0, follow=80.0, dock=85.0)
    argv = fc.ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24,
                          0.5)
    graph = argv[argv.index("-filter_complex") + 1]
    assert "[out]" not in argv
    assert "overlay" not in graph
    assert "concat" in graph


def test_ffmpeg_argv_refuses_a_main_camera_that_is_missing():
    plan, _ = _plan()
    with pytest.raises(ValueError, match="no recording"):
        fc.ffmpeg_argv(plan, {"wide": "w.mp4"}, _clocks(1.0, wide=90.0),
                       "out.mp4", 15, 0.25, 24, 0.5)


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
    # pitched DOWN toward the bay - and down is POSITIVE pitch, the
    # overhead cam's own +1.5708. The -0.979 first sign aimed 0.98 rad
    # above the horizon and filmed sky-grey for two takes (A/B measured
    # 2026-09-01).
    assert pitch > 0.0
    # and the follow camera looks straight down from its config height
    assert float(FILM["follow_height_m"]) == pytest.approx(7.0)


def test_film_record_budget_covers_one_cycle_with_slack():
    assert 600 <= int(FILM["record_budget_s"]) <= 2400


def test_the_eof_tolerance_is_frames_wide_and_not_legs_wide():
    """The bound that decides refuse-or-tolerate, kept between two walls.

    Below one frame interval it would refuse honest rounding; anywhere
    near a leg's length it would let a leg that was never filmed
    through as a silent clamp at end-of-file.
    """
    tolerance = float(FILM["eof_tolerance_s"])
    assert tolerance >= 1.0 / float(FILM["rate_hz"])
    assert tolerance <= 2.0
