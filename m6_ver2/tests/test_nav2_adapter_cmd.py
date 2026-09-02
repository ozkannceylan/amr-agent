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
    msg = nav2_cmd.speed_limit_message(300, 1.500)
    assert msg == {"speed_limit": 0.300, "percentage": False}
    assert nav2_cmd.speed_limit_message(1500, 1.500)["speed_limit"] == 1.500


def test_the_message_round_trips_through_the_readers_own_rule():
    msg = nav2_cmd.speed_limit_message(300, 1.500)
    assert tri.speed_limit_mps(
        msg["percentage"], msg["speed_limit"], 0.700) == 0.300


def test_the_published_permission_may_narrow_the_envelope():
    # 300 mm/s under a 0.700 envelope is a real restriction and it is
    # published as one: this is what the message is FOR.
    assert nav2_cmd.speed_limit_message(300, 0.700) == {
        "speed_limit": 0.300, "percentage": False}


def test_the_published_permission_may_never_widen_the_envelope():
    # D4, RUN3, MEASURED. V_Limit 1500 on a controller configured for
    # 0.300 published `speed_limit 1.5`; nav2's setSpeedLimit REPLACES
    # the configured maximum, so the message raised the envelope by five
    # and /f1/cmd_vel carried -1.5 on the next row.
    for v_limit in (1500, 700, 301, 99999, None, -1):
        msg = nav2_cmd.speed_limit_message(v_limit, 0.300)
        assert msg["speed_limit"] <= 0.300 + 1e-12, v_limit
        assert msg["percentage"] is False


def test_an_envelope_is_required_to_publish_a_permission_at_all():
    # A message sent without knowing what it is narrowing is the defect,
    # not a convenience: there is no default.
    with pytest.raises(TypeError):
        nav2_cmd.speed_limit_message(1500)


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
        "envelope_max_mps": 1.50,
        "creep_speed_mps": 0.005, "zero_speed_mps": 0.001,
        "yawrate_refusal_radps": 0.01})
    assert built == LIMITS


def test_a_limits_block_with_no_envelope_is_refused_by_name():
    # THE EIGHTH CEILING IS NOT OPTIONAL. A `translate` that defaulted
    # the envelope to "no envelope" is exactly the D4 truck: it would
    # drive at whatever the PLC happened to permit, which on this rig is
    # five times what nav2 is configured for.
    with pytest.raises(nav2_cmd.Nav2CmdError) as caught:
        nav2_cmd.limits_from_config({
            "wheelbase_m": 1.05, "steer_limit_rad": 1.31,
            "steer_command_limit_rad": 1.25, "traction_max_mps": 0.700,
            "creep_speed_mps": 0.005, "zero_speed_mps": 0.001,
            "yawrate_refusal_radps": 0.01})
    assert "envelope_max_mps" in str(caught.value)


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


# ----------------------------------------------------------------------
# D4 - THE SPEED LIMIT THAT WIDENED THE ENVELOPE, run3, 2026-09-02
#
# m6_ver2/logs/run3-speed-limit-latch/wire.jsonl, the rows either side of
# the S1 spur entry. Four numbers per row: what /f1/cmd_vel carried, and
# what /f1/auto/cmd_vel carried a moment later (the velocity smoother
# sits between them, which is why the second column RAMPS rather than
# stepping). The last row is followed at sim 125.91 by
#   {"motor": false, "v_limit": 300, "case": 1}
# - the WARNING field dropping the permission 1500 -> 300 by design,
# onto a wheel already turning at 0.700 m/s, and the F-program's speed
# monitor latching. THE FIXTURE IS THE DEFECT, and every assertion below
# is about what the same rows do now.
# ----------------------------------------------------------------------

#: (sim_s, nav2 linear.x, nav2 angular.z, adapter traction, adapter steer)
RUN3 = (
    (120.00, -0.3052, -0.1928, -0.3639, 0.5794),
    (121.00, -0.2866, -0.2236, -0.3711, 0.6825),
    (122.00, -0.2537, -0.2029, -0.3397, 0.7028),
    (122.60, -0.2049, -0.1087, -0.2350, 0.4254),
    (122.80, 0.0000, 0.0000, -0.1703, 0.4697),
    (123.00, -1.5000, -0.5679, -0.1773, 0.5420),
    (123.20, -1.5000, -0.4676, -0.2709, 0.6113),
    (123.40, -1.5000, -0.3918, -0.3552, 0.6064),
    (123.60, -1.5000, -0.2589, -0.4264, 0.5573),
    (123.80, -1.5000, -0.1858, -0.4895, 0.4901),
    (124.00, -1.5000, 0.4413, -0.5473, 0.4103),
    (124.20, -1.5000, 0.5620, -0.5719, 0.0010),
    (124.40, -1.5000, 0.6593, -0.6495, -0.3294),
    (124.60, -1.5000, 0.8231, -0.7000, -0.5751),
    (124.80, -1.5000, 0.8434, -0.7000, -0.7892),
    (125.00, -1.5000, 0.8299, -0.7000, -0.8994),
    (125.20, -1.5000, 0.7118, -0.7000, -0.7949),
    (125.40, -1.5000, 0.7190, -0.7000, -0.8287),
    (125.80, -1.5000, 0.7209, -0.7000, -0.8322),
)

#: The permission the warning field imposed at sim 125.91, in m/s.
RUN3_PERMISSION_MPS = 0.300
#: The permission in force for every row above it.
RUN3_FREE_MPS = 1.500
#: nav2.yaml's own ceiling for both configured controllers, in m/s.
RUN3_ENVELOPE_MPS = 0.300

#: f1's DERIVED numbers, as run3 had them: config.yaml
#: `navcmd.speed_max_mps` 0.700 and nav2.yaml `FollowPath.vx_max` 0.300.
#: A fixture, not a source of truth - the runtime reads both files.
FIELD_LIMITS = nav2_cmd.limits_from_config({
    "wheelbase_m": 1.05,
    "steer_limit_rad": 1.31,
    "steer_command_limit_rad": 1.25,
    "traction_max_mps": 0.700,
    "envelope_max_mps": RUN3_ENVELOPE_MPS,
    "creep_speed_mps": 0.005,
    "zero_speed_mps": 0.001,
    "yawrate_refusal_radps": 0.01,
})


def _f(v, w, limit_mps=None):
    return nav2_cmd.translate(v, w, FIELD_LIMITS, limit_mps=limit_mps)


def _smoothed_of(row):
    """The twist that actually REACHED the adapter on a run3 row.

    Recovered from the pair the adapter PUBLISHED through
    cmd_vel_tricycle_core's own forward model, because /f1/cmd_vel is
    upstream of the velocity smoother and is therefore not what the
    translation was handed.
    """
    _sim, _nv, _nw, wheel, steer = row
    return tri.tricycle_to_twist(steer, wheel, FIELD_LIMITS.wheelbase_m)


def test_the_run3_rows_are_the_defect_as_it_was_measured():
    # Not a check on this code - a check that the fixture still says
    # what the log says, so the assertions below are about something.
    assert max(abs(row[3]) for row in RUN3) == 0.700
    assert min(row[1] for row in RUN3) == -1.500
    # AND THE WHEEL WAS OVER THE COMING PERMISSION LONG BEFORE THE JUMP:
    # at 120.00 nav2 asked for 0.3052 of BODY and the shaft ran 0.3639,
    # because v_w = v / cos(delta) and delta was 0.58 rad.
    assert abs(RUN3[0][3]) > RUN3_PERMISSION_MPS
    assert abs(RUN3[0][1]) < RUN3_PERMISSION_MPS + 1e-2


def test_no_run3_row_leaves_the_terminals_above_the_envelope():
    for row in RUN3:
        smoothed = _smoothed_of(row)
        for v, w in (smoothed, (row[1], row[2])):
            out = _f(v, w, limit_mps=RUN3_FREE_MPS)
            assert abs(out.linear_x) <= RUN3_ENVELOPE_MPS + 1e-12, row


def test_no_run3_row_leaves_the_terminals_above_the_permission_that_arrived():
    # THE WHOLE POINT. The warning field drops V_Limit 1500 -> 300 by
    # design, and the truck has to be ALREADY under 300 when it does.
    for row in RUN3:
        out = _f(*_smoothed_of(row), limit_mps=RUN3_FREE_MPS)
        assert abs(out.linear_x) <= RUN3_PERMISSION_MPS + 1e-12, row


def test_the_warning_field_drop_changes_nothing_at_the_terminals():
    # The last row before the latch, computed under both permissions:
    # the same command, because the envelope was already the binding
    # ceiling. A drop that changes nothing cannot be a step change the
    # F-monitor sees.
    v, w = _smoothed_of(RUN3[-1])
    free = _f(v, w, limit_mps=RUN3_FREE_MPS)
    dropped = _f(v, w, limit_mps=RUN3_PERMISSION_MPS)
    assert abs(free.linear_x - dropped.linear_x) < 1e-12
    assert abs(free.angular_z - dropped.angular_z) < 1e-12


# ----------------------------------------------------------------------
# the margin, at the numbers the run measured
# ----------------------------------------------------------------------

def test_the_permission_caps_the_shaft_at_the_measured_steer_angle():
    # C1's numbers: permission 300 mm/s, steer 0.58 rad. The BODY may
    # be 0.300 and the shaft 0.385 at that angle - which is the reading
    # the F-program takes.
    v, w = _smoothed_of(RUN3[0])
    out = _f(v, w, limit_mps=0.300)
    assert abs(out.linear_x) <= 0.300 + 1e-12
    assert abs(out.v_mps) < 0.300
    assert abs(abs(out.angular_z) - 0.5794) < 1e-3


def test_the_envelope_alone_caps_the_shaft_when_nothing_is_restricted():
    # NO PERMISSION RESTRICTION AND STILL 0.300 AT THE SHAFT: the
    # envelope is a ceiling on this truck whatever the PLC allows, and
    # cos(delta) keeps the body below it in every curve.
    v, w = _smoothed_of(RUN3[0])
    out = _f(v, w, limit_mps=None)
    assert abs(out.linear_x) <= RUN3_ENVELOPE_MPS + 1e-12
    assert abs(out.v_mps) < RUN3_ENVELOPE_MPS
    straight = _f(-1.500, 0.0, limit_mps=None)
    assert abs(straight.linear_x) <= RUN3_ENVELOPE_MPS + 1e-12
    assert abs(abs(straight.v_mps) - RUN3_ENVELOPE_MPS) < 1e-12


def test_the_shaft_ceiling_is_the_lowest_of_the_three():
    # measurement coverage 0.700, nav2's envelope 0.300, the PLC's
    # permission - and the answer is a min(), which is idempotent.
    assert abs(_f(-1.500, 0.0).linear_x) == RUN3_ENVELOPE_MPS
    assert abs(_f(-1.500, 0.0, limit_mps=0.100).linear_x) == 0.100
    assert abs(_f(-1.500, 0.0, limit_mps=1.500).linear_x) == RUN3_ENVELOPE_MPS
    assert abs(_f(-0.050, 0.0, limit_mps=1.500).linear_x) == 0.050


def test_the_envelope_cap_costs_the_speed_and_never_the_arc():
    v, w = _smoothed_of(RUN3[13])
    free = nav2_cmd.translate(v, w, LIMITS)
    capped = _f(v, w)
    assert abs(free.angular_z - capped.angular_z) < 1e-12
    assert abs(capped.w_radps / capped.v_mps
               - free.w_radps / free.v_mps) < 1e-9


def test_the_envelope_is_a_ceiling_and_not_a_stop():
    # It narrows, it does not refuse: a truck that stopped every time
    # nav2 asked for more than its envelope would never leave a station.
    out = _f(-1.500, -0.5679, limit_mps=RUN3_FREE_MPS)
    assert not out.refused
    assert out.linear_x < 0.0
    assert out.reversing is False
