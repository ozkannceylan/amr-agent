"""The command path's arithmetic, checked without a simulator.

WHAT IS BEING CLAIMED. `nodes/cmd_vel_tricycle_core.py` is the INVERSE of
the kinematics `nodes/wheel_odom_core.py` integrates, in the same frame
and under the same sign discipline. So the sharpest test available is not
an assertion about a number this file also wrote down: it is a ROUND TRIP
through the estimator that ships - a twist converted to (steer, tread
speed), driven into `wheel_odom_core.WheelOdometry` as shaft angles, and
read back out as the same twist.

  IT IS NOT THE CRIB'S ROUND TRIP AND THAT IS THE POINT.
  `agv/forklift/scripts/cmd_vel_to_tricycle.py --self-check` round-trips
  against a forward model written a hundred lines below its own inverse,
  in the same file, by the same hand. That catches a typo and nothing
  else. Rounding the trip through the file that will actually be asked
  what the vehicle did catches the failure that matters: the two halves
  of this track disagreeing about which way is forward.

THE SIGNS THIS FILE LOCKS, and every one of them is the repo's rather
than this task's (m6/ipc/follower.py's header, m6/tests/test_follower.py's
header, nodes/wheel_odom_core.py's header):

  * model yaw 0 points the forks at world -x, so the TRAVEL heading is
    model yaw + pi and FORWARD TRAVEL IS A NEGATIVE `linear.x` in
    base_link - which is what wheel_odom_core publishes for it, and
    therefore what a controller reading that estimate will command for it.
  * forward traction is a NEGATIVE traction command, because the tread
    speed and the shaft rate share a sign.
  * POSITIVE STEER IS DRIVER-RIGHT, which in the base_link frame these
    messages are expressed in is a DECREASING yaw - a negative
    `angular.z`. The mirror lives on the yaw rate and never on the angle.

NO ROS AND NO GAZEBO: this runs on the Windows python the owner runs
pytest under.
"""
import math
import os
import re

import pytest

import cmd_vel_tricycle_core as core
import wheel_odom_core

yaml = pytest.importorskip("yaml")

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# The plant, as the frozen model states it. Written here rather than read
# from config.yaml so that a test of the ARITHMETIC does not silently
# become a test of a config edit; the two are compared against each other
# - and against model.sdf - at the bottom of this file.
L = 1.05
R_WHEEL = 0.12
STEER_MECH = 1.31
STEER_CMD = 1.25
KAPPA_MAX = math.tan(STEER_CMD) / L        # 2.8662568 1/m, R = 0.3488871 m
TRACTION_MAX = 0.700
CREEP = 0.005
ZERO = 0.001
YAWRATE_REFUSAL = 0.01


def convert(v, w, **over):
    kwargs = dict(wheelbase_m=L, steer_limit_rad=STEER_MECH,
                  curvature_max_1pm=KAPPA_MAX,
                  traction_max_mps=TRACTION_MAX,
                  creep_speed_mps=CREEP, zero_speed_mps=ZERO,
                  yawrate_refusal_radps=YAWRATE_REFUSAL)
    kwargs.update(over)
    return core.twist_to_tricycle(v, w, **kwargs)


# ----------------------------------------------------------------------
# the conversion, against the forward model written in the same file
# ----------------------------------------------------------------------

def test_straight_forward_is_a_negative_tread_and_a_centred_wheel():
    out = convert(-0.700, 0.0)
    assert out.steer_rad == 0.0
    assert out.wheel_mps == pytest.approx(-0.700)
    assert not out.refused


def test_straight_astern_is_a_positive_tread_and_a_centred_wheel():
    out = convert(0.700, 0.0)
    assert out.steer_rad == 0.0
    assert out.wheel_mps == pytest.approx(0.700)


def test_forward_and_driver_right_is_a_positive_steer_angle():
    # A driver-right turn while travelling forward is a DECREASING model
    # yaw, so angular.z is negative in base_link - and the wheel goes to
    # a POSITIVE angle, which is the one thing that travels from the
    # console to the steer terminal unchanged.
    out = convert(-0.300, -0.200)
    assert out.steer_rad > 0.0
    assert out.wheel_mps < 0.0


def test_forward_and_driver_left_is_a_negative_steer_angle():
    out = convert(-0.300, +0.200)
    assert out.steer_rad < 0.0


def test_the_same_wheel_angle_astern_turns_the_body_the_other_way():
    # wheel_odom_core's selftest locks this on the estimator's side
    # ("the same steer astern turns the other way"); this is the same
    # claim read through the inverse.
    forward = convert(-0.300, -0.200)
    astern = convert(+0.300, +0.200)
    assert forward.steer_rad == pytest.approx(astern.steer_rad)


def test_the_round_trip_through_the_local_forward_model_is_exact():
    # EVERY CASE, CLAMPED OR NOT: what the pair DELIVERS is what the
    # record says it delivers. The unclamped subset is checked against
    # the command itself below - the two claims are different and a test
    # that mixed them would pass a converter that reported its own
    # clamps wrongly.
    worst = 0.0
    unlimited = 0
    for v in (-0.700, -0.300, -0.050, 0.050, 0.300, 0.700):
        for w in (-0.25, -0.10, 0.0, 0.10, 0.25):
            out = convert(v, w)
            vb, wb = core.tricycle_to_twist(out.steer_rad, out.wheel_mps, L)
            worst = max(worst, abs(vb - out.v_mps), abs(wb - out.w_radps))
            if not (out.curvature_clamped or out.steer_clamped
                    or out.traction_clamped):
                unlimited += 1
                worst = max(worst, abs(vb - v), abs(wb - w))
    # 18 of the 30: the eight cruise-plus-curvature rows meet the
    # traction ceiling and the four crawl-plus-hard-yaw rows meet the
    # curvature ceiling, both of which are checked on their own below.
    assert unlimited == 18
    assert worst < 1e-12


def test_cruise_plus_a_corner_is_where_the_traction_ceiling_first_binds():
    # v_w = v / cos(delta), so at the cruise this plant has been driven
    # at ANY curvature asks the wheel for more than the measured
    # ceiling. That is not a defect of the cap, it is what the cap SAYS:
    # 0.700 m/s of tread is measured, and 0.749 m/s is not.
    out = convert(-0.700, -0.25)
    assert out.traction_clamped
    assert not out.curvature_clamped
    assert out.wheel_mps == pytest.approx(-0.700)
    assert out.w_radps / out.v_mps == pytest.approx(-0.25 / -0.700)


# ----------------------------------------------------------------------
# and the round trip that matters: through the estimator that ships
# ----------------------------------------------------------------------

def odometry():
    """wheel_odom_core with both of its deliberate errors switched OFF.

    The believed radius is the true one and the count grid is 2^22 counts
    a revolution - 0.18 um of tread - so what is left in the residual is
    this file's algebra and not the estimator's two modelled faults. The
    faults are wheel_odom_core's own subject and tests/
    test_wheel_odom_core.py is where they are measured.
    """
    return wheel_odom_core.WheelOdometry(
        wheelbase_m=L, wheel_radius_m=R_WHEEL, rear_axle_offset_m=-0.50,
        counts_per_rev=2 ** 22, wheel_radius_scale=1.0, steer_bias_rad=0.0)


def drive_the_estimator(steer_rad, wheel_mps, dt_s=0.05, steps=20):
    """Feed the estimator the shaft angles (steer, tread speed) implies.

    The tread speed IS the shaft rate times the radius, which is the
    contract tools/drive_route.py publishes on and model.sdf's
    JointController consumes - so this is the plant's own arithmetic and
    not a second opinion about it.
    """
    odom = odometry()
    shaft = 0.0
    est = None
    odom.update(0.0, shaft, steer_rad)
    for i in range(1, steps + 1):
        shaft += wheel_mps * dt_s / R_WHEEL
        est = odom.update(i * dt_s, shaft, steer_rad)
    return est


@pytest.mark.parametrize("v,w", [
    (-0.700, 0.0),                       # cruise, dead straight, forward
    (0.700, 0.0),                        # cruise astern
    (-0.300, -0.200),                    # the corner speed, driver-right
    (-0.300, +0.200),                    # the corner speed, driver-left
    (-0.0946, -0.2438),                  # the measured -1.25 rad corner
    (0.300, +0.150),                     # astern on lock
    (-0.050, -0.010),                    # a crawl with a gentle arc
])
def test_the_converter_is_the_inverse_of_the_shipped_estimator(v, w):
    out = convert(v, w)
    assert not out.refused
    est = drive_the_estimator(out.steer_rad, out.wheel_mps)
    # 2^22 counts a revolution leaves 0.18 um of tread per count and the
    # velocity is differenced out of two of them over 50 ms, so the floor
    # under this comparison is about 4 um/s. 1e-5 is that with headroom
    # and it is four orders below the smallest quantity in the table.
    assert est.vx == pytest.approx(v, abs=1e-5)
    assert est.yaw_rate == pytest.approx(w, abs=1e-5)


def test_the_estimator_reports_the_lateral_term_the_converter_never_sees():
    # base_link is 0.50 m ahead of the rear axle, so it moves sideways in
    # every turn. The CONVERSION does not care - v_By is not an input to
    # it, because the x components of v_B and v_R are identical - and
    # that is the one fact that makes the algebra a bicycle relation.
    out = convert(-0.300, -0.200)
    est = drive_the_estimator(out.steer_rad, out.wheel_mps)
    assert est.vy == pytest.approx(0.50 * est.yaw_rate, abs=1e-12)
    assert est.vy != 0.0


# ----------------------------------------------------------------------
# the curvature floor
# ----------------------------------------------------------------------

def test_a_curvature_inside_the_floor_is_untouched():
    out = convert(-0.300, -0.200)          # kappa = 0.667 1/m, R = 1.50 m
    assert not out.curvature_clamped
    assert out.w_radps == pytest.approx(-0.200)


def test_a_curvature_beyond_the_floor_is_CLAMPED_and_SAID_so():
    # R = 0.10 m: inside the wheelbase, and nothing this plant has ever
    # been driven at.
    out = convert(-0.300, -3.000)
    assert out.curvature_clamped
    assert out.w_radps / out.v_mps == pytest.approx(KAPPA_MAX)
    assert out.steer_rad == pytest.approx(STEER_CMD)
    assert not out.refused


def test_the_curvature_clamp_keeps_the_SPEED_and_gives_up_the_ARC():
    # It is the steer stop by another name and it is NOT curvature
    # preserving, which is the whole reason it is counted and logged:
    # the vehicle travels at the speed it was asked for, on a wider arc
    # than it was asked for.
    # 0.200 m/s and not the corner speed: at 0.300 the wheel would want
    # 0.9515 m/s and the traction ceiling would fire as well, so the row
    # would be measuring two clamps at once.
    out = convert(-0.200, -2.000)
    assert out.curvature_clamped and not out.traction_clamped
    assert out.v_mps == pytest.approx(-0.200)
    assert abs(out.w_radps) < 2.000


def test_the_mechanical_stop_is_a_BACKSTOP_the_measured_floor_reaches_first():
    # config.yaml's curvature ceiling is 1.25 rad of steer and the
    # mechanical stop is 1.31; a command clamped by the first can never
    # reach the second. A steer clamp firing on this stack is therefore
    # a bug and not a manoeuvre, which is why it is counted separately.
    for w in (-9.0, -3.0, 3.0, 9.0):
        out = convert(-0.300, w)
        assert abs(out.steer_rad) <= STEER_CMD + 1e-12
        assert not out.steer_clamped


def test_the_mechanical_stop_still_fires_if_the_ceiling_is_opened_past_it():
    out = convert(-0.300, -9.0, curvature_max_1pm=math.tan(1.45) / L)
    assert out.steer_clamped
    assert out.steer_rad == pytest.approx(STEER_MECH)


# ----------------------------------------------------------------------
# the traction limit, which IS curvature preserving
# ----------------------------------------------------------------------

def test_the_traction_clamp_scales_the_whole_twist_and_keeps_the_ARC():
    # v_D = v / cos(delta) grows without bound as the wheel goes over;
    # scaling it with delta HELD scales v and w together, so the vehicle
    # drives the same arc more slowly. That is why this clamp is
    # information and the curvature clamp is a warning.
    out = convert(-0.300, -0.800)          # kappa 2.667, delta 1.2276 rad
    assert out.traction_clamped
    assert out.wheel_mps == pytest.approx(-TRACTION_MAX)
    assert out.w_radps / out.v_mps == pytest.approx(-0.800 / -0.300)


def test_a_straight_run_at_cruise_does_not_hit_the_traction_clamp():
    out = convert(-0.700, 0.0)
    assert not out.traction_clamped


# ----------------------------------------------------------------------
# the one thing that is REFUSED, because no command can satisfy it
# ----------------------------------------------------------------------

def test_a_yaw_rate_at_a_standstill_is_REFUSED_and_not_clamped():
    out = convert(0.0, 0.4)
    assert out.refused
    assert out.wheel_mps == 0.0
    assert out.steer_rad is None            # HOLD - see the module header
    assert "standstill" in out.reason.lower()


def test_below_creep_but_moving_is_declined_and_is_NOT_a_refusal():
    # The crib counted this and the counter became useless: 27 "rotation
    # in place" refusals for a goal that was reached, every one of them
    # the tail of a deceleration through the band.
    out = convert(-0.003, 0.4)
    assert not out.refused
    assert out.wheel_mps == 0.0
    assert out.steer_rad is None


def test_a_standstill_with_no_yaw_rate_is_an_ordinary_stop():
    out = convert(0.0, 0.0)
    assert not out.refused
    assert out.wheel_mps == 0.0


def test_a_command_that_is_not_finite_is_REFUSED():
    for v, w in ((float("nan"), 0.0), (0.0, float("inf")),
                 (float("-inf"), 1.0)):
        out = convert(v, w)
        assert out.refused
        assert out.wheel_mps == 0.0


# ----------------------------------------------------------------------
# the speed limit, and it is curvature preserving too
# ----------------------------------------------------------------------

def test_a_speed_limit_scales_the_whole_twist():
    v, w = core.apply_speed_limit(-0.700, -0.400, 0.300)
    assert v == pytest.approx(-0.300)
    assert w / v == pytest.approx(-0.400 / -0.700)


def test_a_speed_limit_above_the_command_changes_nothing():
    assert core.apply_speed_limit(-0.200, -0.100, 0.300) == (-0.200, -0.100)


def test_a_speed_limit_of_zero_is_NO_LIMIT_and_not_a_stop():
    # nav2_msgs/SpeedLimit says so in its own comment: "When no-limit it
    # is set to 0.0". A node that read it as a stop would brake the
    # vehicle every time the limit was lifted.
    assert core.speed_limit_mps(False, 0.0, 0.700) is None
    assert core.speed_limit_mps(True, 0.0, 0.700) is None


def test_an_absolute_speed_limit_is_metres_per_second():
    assert core.speed_limit_mps(False, 0.3, 0.700) == pytest.approx(0.3)


def test_a_percentage_speed_limit_is_a_fraction_of_the_configured_maximum():
    assert core.speed_limit_mps(True, 50.0, 0.700) == pytest.approx(0.350)


def test_a_speed_limit_over_a_hundred_percent_cannot_raise_the_maximum():
    assert core.speed_limit_mps(True, 300.0, 0.700) == pytest.approx(0.700)


def test_a_negative_or_unreadable_speed_limit_is_refused_as_no_limit():
    assert core.speed_limit_mps(False, -1.0, 0.700) is None
    assert core.speed_limit_mps(False, float("nan"), 0.700) is None


# ----------------------------------------------------------------------
# the slew limiter: a step command becomes a ramp
# ----------------------------------------------------------------------

def ramp(limiter, dt_s, steer_target, wheel_target, ticks):
    """Drive the limiter and return what it moved on EVERY tick.

    THE DELTAS AND NOT THE ENDPOINTS. A ramp that reached its target in
    the right number of ticks can still have taken one illegal step and
    one short one; only the per-tick series can say it did not.
    """
    steps = []
    for _ in range(ticks):
        before_steer, before_wheel = limiter.steer_rad, limiter.wheel_mps
        steer, wheel = limiter.step(dt_s, steer_target, wheel_target)
        steps.append((abs(steer - before_steer)
                      if None not in (steer, before_steer) else 0.0,
                      abs(wheel - before_wheel)))
    return steps


def test_a_step_steer_command_leaves_this_node_as_a_ramp():
    # SEEDED AT THE CENTRE, which is what the shell reads off the
    # plant's own joint state before it publishes anything. An UNSEEDED
    # limiter adopts its first target instead - see the test below.
    limiter = core.CommandLimiter(steer_rate_limit_radps=2.0,
                                  traction_accel_mps2=0.35, steer_rad=0.0)
    # 1.25 rad at 2.0 rad/s is 0.625 s: thirteen ticks of 50 ms.
    steps = ramp(limiter, 0.05, 1.25, 0.0, 40)
    reached = next(i + 1 for i, _ in enumerate(steps)
                   if abs(limiter.steer_rad - 1.25) < 1e-12
                   and all(d == 0.0 for d, _ in steps[i + 1:]))
    assert reached == 13
    # AND NO TICK MOVED FURTHER THAN THE MODEL'S OWN AXIS LIMIT, which
    # is the assertion this file exists to make and it is made HERE, on
    # the deltas, rather than read off a counter the limiter keeps about
    # itself. The ceiling is rate x dt, not the rate: what a limiter
    # controls is the STEP.
    assert max(d for d, _ in steps) <= 2.0 * 0.05 + 1e-12


def test_no_tick_of_a_VARYING_schedule_exceeds_rate_times_ITS_OWN_interval():
    # The ceiling is `limit * dt` and dt moves: under sim time the timer
    # fires early and late, and nodes/cmd_vel_tricycle.py caps the
    # interval at one nominal period but never lengthens it. A limiter
    # that used a fixed step would be legal at 50 ms and illegal at 20.
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.0)
    for dt_s in (0.02, 0.05, 0.031, 0.05, 0.044, 0.05, 0.05, 0.05):
        before = limiter.steer_rad, limiter.wheel_mps
        steer, wheel = limiter.step(dt_s, 1.25, -0.700)
        assert abs(steer - before[0]) <= 2.0 * dt_s + 1e-12, dt_s
        assert abs(wheel - before[1]) <= 0.35 * dt_s + 1e-12, dt_s


def test_no_tick_of_a_TRACTION_step_exceeds_the_acceleration_ceiling():
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.0)
    steps = ramp(limiter, 0.05, 0.0, -0.700, 60)
    assert max(w for _, w in steps) <= 0.35 * 0.05 + 1e-12
    assert limiter.wheel_mps == pytest.approx(-0.700)


def test_the_ceiling_assertion_FAILS_when_the_ramp_exceeds_the_limit():
    # THE GUARD, GUARDED. The three assertions above are worth exactly
    # what a limiter that ignored its ceiling would cost them, so this
    # drives one that does - a limiter told 2.0 rad/s, measured against
    # a ceiling of 1.0 - and requires the same comparison to fail. It is
    # the inverse of the check and it is why the checks above are not
    # vacuous.
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.0)
    steps = ramp(limiter, 0.05, 1.25, 0.0, 5)
    assert not max(d for d, _ in steps) <= 1.0 * 0.05 + 1e-12


def test_the_ramp_step_is_exactly_the_rate_times_the_interval():
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.0)
    steer, _ = limiter.step(0.05, 1.25, 0.0)
    assert steer == pytest.approx(0.10)


def test_the_ramp_never_overshoots_the_target():
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.0)
    for _ in range(30):
        steer, _ = limiter.step(0.05, 0.01, 0.0)
    assert steer == pytest.approx(0.01)


def test_a_HOLD_target_leaves_the_steer_axis_where_it_is():
    # None means hold, and holding is not re-centring: re-centring is a
    # motion command the caller did not issue and it is the wrong
    # pre-position for the cusp that usually follows.
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.0)
    for _ in range(10):
        limiter.step(0.05, 0.6, -0.3)
    steer, wheel = limiter.step(0.05, None, 0.0)
    assert steer == pytest.approx(0.6)
    assert wheel < 0.0                      # the traction still ramps down


def test_the_traction_ramp_is_the_configured_acceleration():
    limiter = core.CommandLimiter(2.0, 0.35)
    _, wheel = limiter.step(0.05, 0.0, -0.700)
    assert wheel == pytest.approx(-0.0175)


def test_the_traction_ramp_is_symmetric_in_both_directions_of_travel():
    limiter = core.CommandLimiter(2.0, 0.35)
    for _ in range(100):
        limiter.step(0.05, 0.0, -0.700)
    _, wheel = limiter.step(0.05, 0.0, 0.0)
    assert wheel == pytest.approx(-0.700 + 0.0175)


def test_a_zero_or_backwards_interval_moves_nothing():
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.0)
    limiter.step(0.05, 1.0, -0.5)
    steer, wheel = limiter.step(0.0, 1.0, -0.5)
    assert (steer, wheel) == (pytest.approx(0.10), pytest.approx(-0.0175))
    steer, wheel = limiter.step(-0.02, 1.0, -0.5)
    assert (steer, wheel) == (pytest.approx(0.10), pytest.approx(-0.0175))


def test_the_limiter_remembers_what_it_last_published():
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.0)
    limiter.step(0.05, 1.0, -0.5)
    assert limiter.steer_rad == pytest.approx(0.10)
    assert limiter.wheel_mps == pytest.approx(-0.0175)


def test_the_limiter_can_be_seeded_so_a_node_does_not_move_the_wheel():
    limiter = core.CommandLimiter(2.0, 0.35, steer_rad=0.4)
    steer, _ = limiter.step(0.05, None, 0.0)
    assert steer == pytest.approx(0.4)


def test_an_UNSEEDED_limiter_adopts_its_first_target_rather_than_guessing():
    # Until the plant has said where the axis is there is nothing to ramp
    # FROM. Ramping from zero would assume a centred wheel, which nothing
    # has claimed, and the plant's own 2.0 rad/s limit still applies to
    # whatever this publishes - so the first command is the one tick this
    # node cannot shape, and the shell says so in its log when it happens.
    limiter = core.CommandLimiter(2.0, 0.35)
    steer, _ = limiter.step(0.05, 1.25, 0.0)
    assert steer == pytest.approx(1.25)
    steer, _ = limiter.step(0.05, 0.0, 0.0)
    assert steer == pytest.approx(1.15)


# ----------------------------------------------------------------------
# the terminal's own units
# ----------------------------------------------------------------------

def test_forward_travel_reaches_the_traction_terminal_as_a_NEGATIVE_rate():
    # model.sdf: /forklift/gz/actuator/traction_cmd is a WHEEL RATE in
    # rad/s. tools/drive_route.py publishes tread / radius onto it and
    # this is the same arithmetic, in the one place a live command uses.
    assert core.wheel_rate_radps(-0.700, R_WHEEL) == pytest.approx(-5.833333,
                                                                  abs=1e-6)
    assert core.wheel_rate_radps(0.300, R_WHEEL) == pytest.approx(2.5)


def test_the_terminal_conversion_refuses_a_radius_of_zero():
    with pytest.raises(ValueError):
        core.wheel_rate_radps(-0.700, 0.0)


# ----------------------------------------------------------------------
# the constants, against the model and against config.yaml
# ----------------------------------------------------------------------

def config():
    with open(os.path.join(_M5V3, "config.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def model_steer_limits():
    """steer_joint's <lower>, <upper> and <velocity>, out of model.sdf.

    READ AND NOT TRUSTED, which is vehicle.imu_mount's habit and
    nav_lidar_mount's: a shell cannot read XML, so config.yaml carries a
    copy of three numbers that model.sdf owns - and a copy that cannot
    say when it has gone stale is a copy that will.
    """
    with open(os.path.join(_M5V3, "gazebo", "forklift_ver3", "model.sdf"),
              encoding="utf-8") as handle:
        sdf = handle.read()
    block = re.search(r'<joint name="steer_joint".*?</joint>', sdf, re.S)
    assert block, "model.sdf no longer defines steer_joint"
    out = {}
    for tag in ("lower", "upper", "effort", "velocity"):
        found = re.search(r"<{0}>([^<]+)</{0}>".format(tag), block.group(0))
        assert found, "steer_joint has no <{}>".format(tag)
        out[tag] = float(found.group(1))
    return out


def test_the_steer_stop_in_config_is_the_stop_the_model_carries():
    limits = model_steer_limits()
    assert limits["upper"] == -limits["lower"]
    assert float(config()["vehicle"]["steer_limit_rad"]) == limits["upper"]


def test_the_steer_slew_in_config_is_the_one_the_model_carries():
    # THE NUMBER THIS TASK ADDED, and it is model.sdf's rather than a
    # choice: <velocity>2.0</velocity> on steer_joint. The node ramps its
    # own output at it so that a step command reaching the plant is a
    # step the plant was going to make a ramp of anyway.
    assert (float(config()["vehicle"]["steer_rate_limit_radps"])
            == model_steer_limits()["velocity"])


def test_the_commanded_steer_ceiling_is_INSIDE_the_mechanical_stop():
    vehicle = config()["vehicle"]
    navcmd = config()["navcmd"]
    assert (float(navcmd["steer_command_limit_rad"])
            < float(vehicle["steer_limit_rad"]))


def test_the_commanded_steer_ceiling_is_a_MEASURED_angle():
    # 1.25 rad is the hardest steer this plant has been driven at
    # (config.yaml drive_route.profiles.square, and the two-row delivered
    # table above it). Beyond it there is no measurement, only geometry.
    square = config()["drive_route"]["profiles"]["square"]
    driven = {abs(float(row["steer_rad"])) for row in square}
    assert float(config()["navcmd"]["steer_command_limit_rad"]) in driven


def test_the_curvature_ceiling_the_node_enforces_follows_from_that_angle():
    navcmd = config()["navcmd"]
    wheelbase = float(config()["vehicle"]["wheelbase_m"])
    kappa = math.tan(float(navcmd["steer_command_limit_rad"])) / wheelbase
    assert core.curvature_max(float(navcmd["steer_command_limit_rad"]),
                              wheelbase) == pytest.approx(kappa)
    assert kappa == pytest.approx(KAPPA_MAX)


def test_the_speed_ceiling_is_the_cruise_this_plant_has_been_driven_at():
    straight = config()["drive_route"]["profiles"]["straight"]
    driven = {abs(float(row["tread_mps"])) for row in straight}
    assert float(config()["navcmd"]["speed_max_mps"]) == max(driven)


def test_the_creep_deadband_is_below_the_closed_loop_smoothers_own_floor():
    # THE DEADLOCK ARITHMETIC, and it is the crib's (docs/LESSONS.md
    # 2026-08-05). A CLOSED_LOOP smoother starting from rest cannot emit
    # more than max_accel * dt on the most restrictive axis, so a creep
    # deadband at or above that floor stalls every leg: the converter
    # zeroes traction, the plant does not move, the estimate reads zero,
    # and the smoother stays pinned.
    navcmd = config()["navcmd"]
    dt = 1.0 / float(navcmd["rate_hz"])
    floor = float(navcmd["accel_mps2"]) * dt
    assert float(navcmd["creep_speed_mps"]) < floor
    assert float(navcmd["zero_speed_mps"]) < float(navcmd["creep_speed_mps"])


def test_the_node_and_the_smoother_are_told_the_same_command_rate():
    with open(os.path.join(_M5V3, "smoother.yaml"), encoding="utf-8") as handle:
        smoother = yaml.safe_load(handle)
    params = smoother["velocity_smoother"]["ros__parameters"]
    assert (float(params["smoothing_frequency"])
            == float(config()["navcmd"]["rate_hz"]))
