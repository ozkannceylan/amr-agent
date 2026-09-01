"""nav2_cmd.py - the signs, the V_Limit cap and the SpeedLimit message.

THE SIGN TESTS ARE THE CONTRACT, and they are written in the
test_follower idiom - one named scenario per sign combination - because
getting this wrong steers at the rack. Three sentences generate every
assertion below and they belong to the repo, not to this file:

  MODEL YAW 0 POINTS THE FORKS AT WORLD -x, so forks-first travel is a
  NEGATIVE linear.x, a NEGATIVE tread and a NEGATIVE wheel rate.
  POSITIVE STEER IS DRIVER-RIGHT (cmd_vel_tricycle_core), which in
  base_link is a DECREASING yaw and therefore a NEGATIVE angular.z in.
  POSITIVE angular.z IS A DRIVER-RIGHT TURN on m6's command path
  (cmd_gate's field contract), and it carries an ANGLE and not a rate.

So the adapter's whole job on this seam is: pass linear.x through
unchanged, and change angular.z's TYPE from rate to angle without
changing which way it means.
"""
import math

import pytest

import cmd_vel_tricycle_core as tri

import nav2_cmd


LIMITS = nav2_cmd.SELFTEST_LIMITS


def _t(v, w, limit_mps=None):
    return nav2_cmd.translate(v, w, LIMITS, limit_mps=limit_mps)


# ----------------------------------------------------------------------
# the six worked examples
# ----------------------------------------------------------------------

def test_forks_first_straight_is_negative_traction_and_a_centred_wheel():
    out = _t(-0.300, 0.0)
    assert out.linear_x < 0.0
    assert abs(out.linear_x + 0.300) < 1e-12
    assert out.angular_z == 0.0
    assert out.reversing is False


def test_counterweight_first_straight_is_positive_traction():
    # THE SPUR BACK-OUT. m6 calls this reverse; nav2 calls it forward,
    # and neither name changes the number on the wire.
    out = _t(0.250, 0.0)
    assert out.linear_x > 0.0
    assert abs(out.linear_x - 0.250) < 1e-12
    assert out.angular_z == 0.0
    assert out.reversing is True


def test_forward_driver_right_is_a_positive_steer_angle():
    out = _t(-0.300, -0.200)
    assert out.linear_x < 0.0 and out.angular_z > 0.0


def test_forward_driver_left_is_a_negative_steer_angle():
    out = _t(-0.300, 0.200)
    assert out.linear_x < 0.0 and out.angular_z < 0.0


def test_reverse_with_the_wheel_cocked_right_is_still_a_positive_angle():
    # SAME WHEEL, OPPOSITE TRAVEL. With the steer axis to the driver's
    # right a truck driving forwards turns right and a truck backing out
    # turns the other way round the same circle - so the YAW RATE flips
    # sign and the ANGLE does not. The adapter reports the angle.
    out = _t(0.250, 0.200)
    assert out.linear_x > 0.0 and out.angular_z > 0.0


def test_reverse_with_the_wheel_cocked_left_is_a_negative_angle():
    out = _t(0.250, -0.200)
    assert out.linear_x > 0.0 and out.angular_z < 0.0


def test_the_same_wheel_angle_serves_both_directions():
    forward = _t(-0.300, -0.300)
    astern = _t(0.300, 0.300)
    assert abs(forward.angular_z - astern.angular_z) < 1e-12


# ----------------------------------------------------------------------
# it IMPORTS the kinematics, it does not own them
# ----------------------------------------------------------------------

def test_the_conversion_is_cmd_vel_tricycle_cores_own():
    out = _t(-0.300, -0.200)
    theirs = tri.twist_to_tricycle(
        -0.300, -0.200, wheelbase_m=LIMITS.wheelbase_m,
        steer_limit_rad=LIMITS.steer_limit_rad,
        curvature_max_1pm=LIMITS.curvature_max_1pm,
        traction_max_mps=LIMITS.traction_max_mps,
        creep_speed_mps=LIMITS.creep_speed_mps,
        zero_speed_mps=LIMITS.zero_speed_mps,
        yawrate_refusal_radps=LIMITS.yawrate_refusal_radps)
    assert out.angular_z == theirs.steer_rad
    assert out.linear_x == theirs.wheel_mps


def test_the_curvature_ceiling_is_derived_and_not_typed():
    assert LIMITS.curvature_max_1pm == tri.curvature_max(
        LIMITS.steer_command_limit_rad, LIMITS.wheelbase_m)
    assert abs(LIMITS.curvature_max_1pm - 2.8662568322503152) < 1e-12


def test_the_round_trip_through_the_forward_model_is_exact():
    worst = 0.0
    for v in (-0.300, -0.050, 0.050, 0.300):
        for w in (-0.25, -0.10, 0.0, 0.10, 0.25):
            out = _t(v, w)
            back = tri.tricycle_to_twist(
                out.angular_z, out.linear_x, LIMITS.wheelbase_m)
            worst = max(worst, abs(back[0] - out.v_mps),
                        abs(back[1] - out.w_radps))
    assert worst < 1e-12


# ----------------------------------------------------------------------
# the V_Limit cap at source
# ----------------------------------------------------------------------

def test_the_creep_permission_caps_the_shaft_and_keeps_the_arc():
    # THE F-PROGRAM'S SPEED MONITOR READS THE SHAFT, so the cap has to
    # land on the tread and not only on the body speed - and clamping
    # the tread with the steer angle HELD scales v and w together, so
    # the truck drives the same arc more slowly.
    free = _t(-0.700, -0.500)
    capped = _t(-0.700, -0.500, limit_mps=0.300)
    assert abs(capped.linear_x) <= 0.300 + 1e-12
    assert abs(free.angular_z - capped.angular_z) < 1e-12
    assert abs(capped.w_radps / capped.v_mps
               - free.w_radps / free.v_mps) < 1e-9


def test_a_hard_arc_would_beat_a_body_only_cap():
    # v/cos(delta) grows without bound as the wheel goes over: capping
    # |v| alone leaves the SHAFT above the permission, which is the one
    # quantity the F-program monitors.
    out = _t(-0.300, -0.800, limit_mps=0.300)
    assert abs(out.v_mps) < 0.300
    assert abs(out.linear_x) <= 0.300 + 1e-12


def test_no_limit_is_not_a_stop():
    out = _t(-0.700, 0.0, limit_mps=None)
    assert abs(out.linear_x + 0.700) < 1e-12


def test_the_limit_is_the_permission_in_metres_per_second():
    assert nav2_cmd.limit_mps_from_v_limit(300) == 0.300
    assert nav2_cmd.limit_mps_from_v_limit(1500) == 1.500


def test_an_unreadable_v_limit_becomes_the_creep_ceiling():
    # status_contract's rule, imported and not re-decided: not knowing
    # means assuming the most demanding permission, and here the most
    # demanding is the slowest.
    assert nav2_cmd.limit_mps_from_v_limit(None) == 0.300
    assert nav2_cmd.limit_mps_from_v_limit(-1) == 0.300
    assert nav2_cmd.limit_mps_from_v_limit(99999) == 0.300


# ----------------------------------------------------------------------
# the /speed_limit message
# ----------------------------------------------------------------------

def test_the_speed_limit_message_is_absolute_and_not_a_percentage():
    msg = nav2_cmd.speed_limit_message(300)
    assert msg == {"speed_limit": 0.300, "percentage": False}
    assert nav2_cmd.speed_limit_message(1500)["speed_limit"] == 1.500


def test_the_message_round_trips_through_the_readers_own_rule():
    msg = nav2_cmd.speed_limit_message(300)
    assert tri.speed_limit_mps(
        msg["percentage"], msg["speed_limit"], 0.700) == 0.300


# ----------------------------------------------------------------------
# the reversing flag
# ----------------------------------------------------------------------

def test_reversing_is_a_positive_command_beyond_the_deadband():
    assert nav2_cmd.is_reversing(0.250, LIMITS) is True
    assert nav2_cmd.is_reversing(-0.250, LIMITS) is False
    assert nav2_cmd.is_reversing(0.0, LIMITS) is False
    assert nav2_cmd.is_reversing(0.001, LIMITS) is False


# ----------------------------------------------------------------------
# what has no legal answer
# ----------------------------------------------------------------------

def test_a_yaw_rate_at_a_standstill_is_refused_and_the_steer_is_held():
    out = _t(0.0, 0.400)
    assert out.refused
    assert out.linear_x == 0.0
    assert out.angular_z is None
    assert "STANDSTILL" in out.reason


def test_a_command_that_is_not_finite_is_refused():
    assert _t(float("nan"), 0.0).refused
    assert _t(0.0, float("inf")).refused


def test_below_creep_is_declined_and_is_not_a_refusal():
    out = _t(-0.003, 0.400)
    assert not out.refused
    assert out.linear_x == 0.0 and out.angular_z is None


def test_a_held_steer_is_not_a_centred_wheel():
    # angular_z None means HOLD. Publishing 0.0 there would be the
    # adapter moving the wheel on its own account.
    assert _t(0.0, 0.400).angular_z is None


def test_limits_from_a_config_block_refuse_a_missing_key_by_name():
    with pytest.raises(nav2_cmd.Nav2CmdError) as caught:
        nav2_cmd.limits_from_config({"wheelbase_m": 1.05})
    assert "steer_limit_rad" in str(caught.value)


def test_limits_from_a_config_block_build_the_same_record():
    built = nav2_cmd.limits_from_config({
        "wheelbase_m": 1.05, "steer_limit_rad": 1.31,
        "steer_command_limit_rad": 1.25, "traction_max_mps": 1.50,
        "creep_speed_mps": 0.005, "zero_speed_mps": 0.001,
        "yawrate_refusal_radps": 0.01})
    assert built == LIMITS


# ----------------------------------------------------------------------
# the selftest
# ----------------------------------------------------------------------

def test_the_selftest_is_green():
    assert nav2_cmd._selftest() == 0


def test_the_steer_angle_never_leaves_the_mechanical_stop():
    for w in (-4.0, -1.0, 0.0, 1.0, 4.0):
        out = _t(-0.300, w)
        assert abs(out.angular_z) <= LIMITS.steer_limit_rad + 1e-12
        assert abs(out.angular_z) <= math.pi / 2.0
