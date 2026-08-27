"""The twist bench's arithmetic and its refusals, without a simulator.

`tools/drive_twist.py` is two programs in one file - a DRIVE that needs
ROS and an ANALYSE that needs nothing - which is tools/sensor_evidence.py's
own split. Everything below is on the second side of it, and the module
imports on the Windows python because every ROS import in that file lives
inside `record()`.

WHAT IS WORTH LOCKING HERE, and it is not the plumbing:

  THE TABLE IS REFUSED AND NOT CLAMPED. config.yaml's
  vehicle.steer_limit_rad comment draws the line - the CONVERTER clamps
  because it takes live commands, a TABLE is corrected because somebody
  wrote it down - and this bench is on the table's side of it. A profile
  that asks for something the converter would clamp is refused BEFORE the
  first command, and a profile that says `expect_clamp` and then does not
  produce one is refused too, because a row that asks to observe a clamp
  and gets none is a row whose table has drifted away from the limits.

  EVERY SHIPPED PROFILE STILL PASSES THAT CHECK. That is the regression
  this file exists for: navcmd:'s ceilings and twist_route:'s tables are
  written against each other, and either one can move.

  THE SLEW IS READ AS A STEP AND NOT AS A RATE. The limiter controls the
  STEP per tick; dividing by an interval the timer shortened reports a
  rate above the limit for a ramp that never exceeded it.

  AND THE DELIVERED SPEED IS SIGNED THE WAY base_link's OWN linear.x IS.
  Forward travel - forks first - is NEGATIVE, and an instrument that
  reported it positive would make every delivered/commanded ratio on this
  track negative.
"""
import math
import os

import pytest

import _common
import drive_twist as bench
import evidence_core as ec

yaml = pytest.importorskip("yaml")

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def real_config():
    return _common.load_config(bench.TOOL, bench.REQUIRED_KEYS)


def fake_config(rows, **over):
    """A Config carrying ONE profile called `t`, on the real ceilings.

    The vehicle and the navcmd ceilings are the shipped ones, so a
    refusal here is a refusal the live bench would make; only the table
    is synthetic.
    """
    with open(os.path.join(_M5V3, "config.yaml"), encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    data["twist_route"]["profiles"] = {"t": rows}
    for key, value in over.items():
        data["navcmd"][key] = value
    return _common.Config(bench.TOOL, data)


def row(hold_s="5.0", v="-0.300", w="0.000", **extra):
    out = {"hold_s": hold_s, "v_mps": v, "w_radps": w}
    out.update(extra)
    return out


# ----------------------------------------------------------------------
# the table, checked before anything is published
# ----------------------------------------------------------------------

def test_every_shipped_profile_is_inside_the_limits_it_was_written_against():
    # THE REGRESSION THIS FILE EXISTS FOR. navcmd:'s ceilings and
    # twist_route:'s tables are written against each other and either can
    # move; a profile that had drifted outside would be discovered on the
    # rig, with the stack up, instead of here.
    cfg = real_config()
    for name in cfg.raw("twist_route.profiles"):
        segments = bench.read_profile(cfg, name)
        assert segments


def test_the_corner_profiles_reproduce_drive_routes_own_steer_and_tread():
    # THE CROSS-CHECK THAT MAKES THE TWO BENCHES COMPARABLE.
    # twist_route.profiles.corner_creep is the exact kinematic equivalent
    # of drive_route.profiles.corner_creep's held row: -0.785398 rad of
    # steer at -0.300 m/s of tread. If either table moves, the delivered
    # yaw rate of one stops being comparable with the delivered yaw rate
    # of the other, and the whole point of having both disappears.
    cfg = real_config()
    lim = bench.limits(cfg)
    held = [seg for seg in bench.read_profile(cfg, "corner_creep")
            if seg.w_radps != 0.0]
    assert len(held) == 1
    out = bench.convert(lim, held[0].v_mps, held[0].w_radps)
    assert out.steer_rad == pytest.approx(-0.785398, abs=1e-5)
    assert out.wheel_mps == pytest.approx(-0.300, abs=1e-5)


def test_the_cruise_corner_asks_for_the_SAME_arc_at_the_higher_speed():
    cfg = real_config()
    lim = bench.limits(cfg)
    creep = [s for s in bench.read_profile(cfg, "corner_creep")
             if s.w_radps != 0.0][0]
    cruise = [s for s in bench.read_profile(cfg, "corner_cruise")
              if s.w_radps != 0.0][0]
    assert (cruise.w_radps / cruise.v_mps
            == pytest.approx(creep.w_radps / creep.v_mps, rel=1e-4))


def test_a_profile_this_track_does_not_have_is_refused_by_name():
    with pytest.raises(SystemExit):
        bench.read_profile(real_config(), "no_such_profile")


def test_a_segment_with_no_time_is_refused():
    with pytest.raises(SystemExit):
        bench.read_profile(fake_config([row(hold_s="0.0")]), "t")


def test_a_segment_that_is_not_a_mapping_is_refused():
    with pytest.raises(SystemExit):
        bench.read_profile(fake_config(["3.0"]), "t")


def test_an_empty_profile_is_refused():
    with pytest.raises(SystemExit):
        bench.read_profile(fake_config([]), "t")


def test_a_curvature_the_converter_would_CLAMP_is_refused_in_a_table():
    # R = 0.10 m at the corner speed: inside the wheelbase, and past the
    # measured ceiling. The converter would make it legal; a table is
    # corrected instead.
    with pytest.raises(SystemExit):
        bench.read_profile(fake_config([row(v="-0.300", w="3.000")]), "t")


def test_a_tread_speed_the_converter_would_CLAMP_is_refused_in_a_table():
    # v / cos(delta) at cruise on any real curvature is over the ceiling.
    with pytest.raises(SystemExit):
        bench.read_profile(fake_config([row(v="-0.700", w="0.500")]), "t")


def test_a_row_that_SAYS_expect_clamp_is_allowed_exactly_that_clamp():
    segments = bench.read_profile(
        fake_config([row(v="-0.700", w="0.500", expect_clamp="traction")]),
        "t")
    assert segments[0].expect_clamp == "traction"


def test_expecting_the_WRONG_clamp_is_still_refused():
    with pytest.raises(SystemExit):
        bench.read_profile(
            fake_config([row(v="-0.700", w="0.500",
                             expect_clamp="curvature")]), "t")


def test_expecting_a_clamp_that_does_not_happen_is_refused():
    # A row that asks to observe a clamp and produces none is a row whose
    # table has drifted away from the limits it was written against -
    # which is exactly as wrong as a row that clamps by accident.
    with pytest.raises(SystemExit):
        bench.read_profile(
            fake_config([row(v="-0.300", w="0.000",
                             expect_clamp="traction")]), "t")


def test_a_clamp_this_node_does_not_have_is_refused_by_name():
    with pytest.raises(SystemExit):
        bench.read_profile(
            fake_config([row(expect_clamp="handbrake")]), "t")


def test_a_command_with_no_executable_answer_is_refused():
    # A yaw rate at a standstill. The converter refuses it live; a table
    # that contains one is refused before anything is published.
    with pytest.raises(SystemExit):
        bench.read_profile(fake_config([row(v="0.000", w="0.400")]), "t")


def test_a_negative_speed_limit_is_refused():
    # nav2_msgs/SpeedLimit spells NO LIMIT as 0.0; a negative value has
    # no meaning on that message at all.
    with pytest.raises(SystemExit):
        bench.read_profile(
            fake_config([row(speed_limit_mps="-1.0")]), "t")


def test_a_speed_limit_of_zero_is_a_legal_row_and_means_LIFTED():
    segments = bench.read_profile(
        fake_config([row(speed_limit_mps="0.000")]), "t")
    assert segments[0].speed_limit_mps == 0.0


def test_a_row_that_says_nothing_about_the_limit_carries_None():
    # None and 0.0 are different instructions: one is "leave the envelope
    # where it is" and the other is "lift it".
    assert bench.read_profile(fake_config([row()]), "t")[0] \
        .speed_limit_mps is None


# ----------------------------------------------------------------------
# the ceilings the bench checks against are the node's own
# ----------------------------------------------------------------------

def test_the_bench_and_the_node_share_one_curvature_ceiling():
    cfg = real_config()
    lim = bench.limits(cfg)
    assert lim["curvature_max_1pm"] == pytest.approx(
        math.tan(cfg.f("navcmd.steer_command_limit_rad"))
        / cfg.f("vehicle.wheelbase_m"))
    assert lim["steer_command_limit_rad"] < lim["steer_limit_rad"]


def test_describe_prints_every_shipped_profile_without_refusing(capsys):
    cfg = real_config()
    for name in sorted(cfg.raw("twist_route.profiles")):
        total = bench.describe(cfg, name, bench.read_profile(cfg, name))
        assert total > 0.0
    assert "negative v_mps is FORWARD" in capsys.readouterr().out


def test_describe_carries_a_standing_speed_limit_across_rows(capsys):
    # The envelope stands until another message replaces it, so a row
    # that says nothing is driven UNDER the last row that spoke. A table
    # printed any other way would say the truck went back to cruise.
    cfg = fake_config([row(v="-0.700", w="0.000", speed_limit_mps="0.300"),
                       row(v="-0.700", w="0.000")])
    bench.describe(cfg, "t", bench.read_profile(cfg, "t"))
    out = capsys.readouterr().out
    assert "under a standing 0.300 m/s limit" in out


# ----------------------------------------------------------------------
# the analysis arithmetic
# ----------------------------------------------------------------------

def table(names, rows):
    columns = {name: [r[i] for r in rows] for i, name in enumerate(names)}
    return ec.Table("<test>", names, columns, len(rows))


def test_the_window_takes_the_samples_inside_it_and_no_others():
    assert bench.window([0.0, 1.0, 2.0, 3.0], 1.0, 3.0) == [1, 2]


def test_a_ratio_against_a_standstill_is_a_dash_and_never_an_infinity():
    assert bench._ratio_text(0.5, 0.0) == "-"
    assert bench._ratio_text(0.5, float("nan")) == "-"
    assert bench._ratio_text(-0.35, -0.70) == "0.5000"


def test_the_delivered_speed_is_NEGATIVE_when_the_truck_drives_FORWARD():
    # Forward is forks first, which is model -x - and the spawn stands at
    # yaw pi, so the truck moving along world +x IS moving forward. An
    # instrument that reported that positive would make every ratio on
    # this track negative.
    rows = [(t, -17.0 + 0.7 * t, 10.0, math.pi, 0.0, 0.0)
            for t in (0.0, 0.1, 0.2, 0.3, 0.4)]
    got = table(("t_s", "x", "y", "yaw", "vx", "wz"), rows)
    v, w = bench.body_motion(got, list(range(5)))
    assert v == pytest.approx(-0.7, abs=1e-9)
    assert w == pytest.approx(0.0, abs=1e-9)


def test_the_delivered_yaw_rate_is_differenced_from_the_HEADING():
    rows = [(t, 0.0, 0.0, 0.2 * t, 0.0, 0.0)
            for t in (0.0, 0.1, 0.2, 0.3, 0.4)]
    got = table(("t_s", "x", "y", "yaw", "vx", "wz"), rows)
    _, w = bench.body_motion(got, list(range(5)))
    assert w == pytest.approx(0.2, abs=1e-9)


def test_a_window_with_too_few_samples_reports_nothing_rather_than_a_zero():
    rows = [(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), (0.1, 0.1, 0.0, 0.0, 0.0, 0.0)]
    got = table(("t_s", "x", "y", "yaw", "vx", "wz"), rows)
    v, w = bench.body_motion(got, [0, 1])
    assert math.isnan(v) and math.isnan(w)


def test_the_slew_is_reported_as_a_STEP_with_the_interval_beside_it():
    # The limiter controls the step per tick. A tick that fires 6 ms early
    # still carries the full period's step, and dividing by the short
    # interval reports a rate above the limit for a ramp that never
    # exceeded it - so both numbers are printed and the step is the one
    # that is compared.
    worst = bench.max_step([0.0, 0.05, 0.094], [0.0, 0.0175, 0.035])
    assert worst.step == pytest.approx(0.0175)
    assert worst.dt == pytest.approx(0.05)
    assert worst.rate == pytest.approx(0.35)


def test_a_zero_or_backwards_interval_is_not_a_slew():
    worst = bench.max_step([0.0, 0.0, -1.0], [0.0, 1.0, 2.0])
    assert worst.step == 0.0


def test_the_streams_a_session_carries_are_the_command_path_end_to_end():
    # The claim the whole bench rests on: what was asked for, what the
    # smoother made of it, what reached each terminal, what the AXES did
    # and what the TRUCK did.
    assert list(bench.STREAMS) == [
        "cmd_vel", "cmd_vel_smoothed", "steer_cmd", "traction_cmd",
        "joint_state", "ground_truth"]


def test_the_bench_never_reads_the_ground_truth_into_the_control_loop():
    # F2 constraint 13 and F4 constraint 18. It RECORDS the ground truth -
    # that is what it is for - and it publishes only into topics.cmd_vel
    # and topics.speed_limit. Nothing it publishes is derived from a
    # measurement of any kind: the profile is a table.
    with open(os.path.join(_M5V3, "tools", "drive_twist.py"),
              encoding="utf-8") as handle:
        body = handle.read()
    published = body.split("def record(", 1)[1]
    for line in published.splitlines():
        if "pub_cmd.publish" in line or "pub_limit.publish" in line:
            assert "truth" not in line and "gt" not in line
