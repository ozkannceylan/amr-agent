"""follower.py's geometry. Pure math, no ROS.

THE SIGN TESTS ARE THE CONTRACT. Model yaw 0 points the forks at world
-x (hmi_node.knob_to_twist docstring); facing -x, world +y is the
driver's RIGHT, and positive angular.z is a driver-right turn. Forward
is negative linear.x. Every assertion below is derived from those three
sentences; if one fails after an edit, the edit changed the vehicle's
sign convention, not the test's opinion.
"""
import math

import field_eval
import follower


def test_travel_yaw_is_the_fork_direction():
    assert abs(follower.norm_ang(
        follower.travel_yaw(0.0) - math.pi)) < 1e-9


def test_straight_ahead_needs_no_steer():
    assert abs(follower.steer((0.0, 0.0, 0.0), (-2.0, 0.0))) < 1e-6


def test_target_to_driver_right_steers_positive():
    # Facing -x, target at world +y = driver's right.
    assert follower.steer((0.0, 0.0, 0.0), (-2.0, 1.0)) > 0.05


def test_target_to_driver_left_steers_negative():
    assert follower.steer((0.0, 0.0, 0.0), (-2.0, -1.0)) < -0.05


def test_target_behind_commands_a_committed_turn():
    # Dead astern: alpha wraps to -pi and raw pursuit computes
    # sin(pi) = 0 - "drive straight on, away from the goal". The alpha
    # clamp turns it into a firm turn instead.
    assert abs(follower.steer((0.0, 0.0, 0.0), (2.0, 0.0))) > 0.8


def test_target_behind_right_turns_right():
    # Behind and to the driver's right (facing -x, +y is right):
    # commit to a right (positive) turn, not a left one.
    assert follower.steer((0.0, 0.0, 0.0), (2.0, 1.0)) > 0.8


def _target_at(pose, alpha, distance):
    """The point `distance` away whose bearing error from pose is alpha."""
    bearing = follower.travel_yaw(pose[2]) + alpha
    return (pose[0] + distance * math.cos(bearing),
            pose[1] + distance * math.sin(bearing))


def test_a_full_lookahead_target_steers_exactly_as_before():
    # THE LONG-LEG PIN. advance() walks LOOKAHEAD_M along the polyline,
    # so on a straight leg the target really is LOOKAHEAD_M away and the
    # true-distance denominator equals the old constant one. This test
    # is what says the fix touched only the short-target case.
    pose = (0.0, 0.0, 0.0)
    alpha = 0.5
    target = _target_at(pose, alpha, follower.LOOKAHEAD_M)
    expected = -math.atan2(
        2.0 * follower.WHEELBASE_M * math.sin(alpha), follower.LOOKAHEAD_M)
    assert abs(follower.steer(pose, target) - expected) < 1e-9


def test_a_short_end_clamped_target_steers_harder():
    # THE S7 SPUR, IN NUMBERS. The spur is 0.85 m but LOOKAHEAD_M is
    # 1.2, so advance() clamps the target to the station and the old
    # fixed denominator threw away a third of the steer demand exactly
    # where it was needed. Measured 2026-08-13: the truck overshot the
    # station by 0.76 m and swung its tail into rack A.
    pose = (8.3, 5.65, -math.pi / 2)        # forks north, 0.3 m east of it
    target = (8.0, 6.5)                     # S7, 0.901 m away
    alpha = follower.norm_ang(
        math.atan2(target[1] - pose[1], target[0] - pose[0])
        - follower.travel_yaw(pose[2]))
    old = -math.atan2(
        2.0 * follower.WHEELBASE_M * math.sin(alpha), follower.LOOKAHEAD_M)
    got = follower.steer(pose, target)
    assert abs(got) > abs(old) + 0.1        # strictly, and by a margin
    assert got < 0.0                        # target is west = driver-left


def test_a_short_target_dead_ahead_still_needs_no_steer():
    # Tighter geometry must not invent a steer demand out of nothing.
    pose = (8.0, 5.65, -math.pi / 2)
    assert abs(follower.steer(pose, (8.0, 6.5))) < 1e-9


def test_the_denominator_floor_keeps_the_steer_finite():
    # At the goal point the true distance goes to zero. The floor keeps
    # the formula defined and pins the answer to LD_MIN_M.
    pose = (0.0, 0.0, 0.0)
    alpha = -0.9273
    target = _target_at(pose, alpha, 0.05)
    got = follower.steer(pose, target)
    assert math.isfinite(got)
    expected = -math.atan2(
        2.0 * follower.WHEELBASE_M * math.sin(alpha), follower.LD_MIN_M)
    assert abs(got - expected) < 1e-6


def test_advance_walks_the_lookahead_along_the_path():
    path = [(0.0, 0.0), (-10.0, 0.0)]
    target, to_end = follower.advance(path, (-3.0, 0.2))
    assert abs(target[0] - (-3.0 - follower.LOOKAHEAD_M)) < 1e-6
    assert abs(target[1]) < 1e-9
    assert abs(to_end - 7.0) < 1e-6


def test_advance_clamps_to_the_path_end():
    path = [(0.0, 0.0), (-2.0, 0.0)]
    target, to_end = follower.advance(path, (-1.5, 0.0))
    assert target == (-2.0, 0.0)
    assert abs(to_end - 0.5) < 1e-6


def test_advance_tolerates_a_zero_length_first_segment():
    # route.plan_route duplicates the first point when the pose sits on
    # a graph node; advance() must not divide by zero or stall there.
    path = [(0.0, 0.0), (0.0, 0.0), (-10.0, 0.0)]
    target, to_end = follower.advance(path, (0.0, 0.0))
    assert abs(target[0] - (-follower.LOOKAHEAD_M)) < 1e-6
    assert abs(to_end - 10.0) < 1e-6


def test_cruise_on_a_straight_clear_leg():
    v = follower.target_speed(10.0, 0.0, math.inf)
    assert v == follower.CRUISE_MPS


def test_corner_slows_to_corner_speed():
    v = follower.target_speed(10.0, 0.5, math.inf)
    assert v == follower.CORNER_MPS


def test_approach_zone_slows_regardless_of_steer():
    v = follower.target_speed(1.5, 0.0, math.inf)
    assert v == follower.APPROACH_MPS


def test_guard_slow_band_caps_speed():
    v = follower.target_speed(10.0, 0.0, 2.5)
    assert v == follower.GUARD_SLOW_MPS


def test_the_guard_band_sits_outside_the_warning_field_it_protects():
    """THE BAND'S WHOLE PURPOSE, asked as arithmetic.

    follower's own header states the rule: the lidar must have the truck
    down to the creep ceiling BEFORE a warning field can drop V_Limit
    under wheels still doing 0.7 m/s, because the F-program's speed
    monitor demands a stop the instant either channel reads above
    V_Limit and the demand LATCHES (virtual_fplc._healthy, measured live
    in step 3). The band was 3.0 m against a 2.5 m field and looked like
    it kept that rule. It did not, and the reason is that the two
    numbers are measured from DIFFERENT SENSORS.

    The warning field is evaluated at the safety scanners, and the two
    that see an obstacle dead ahead are the FORK-CORNER pair at model
    (-0.68, +-0.46). The guard is evaluated at the nav lidar, at model
    (0.55, -0.40) - 1.23 m further back. So a 3.0 m guard reading is
    1.77 m at the fork corners, three quarters of a metre INSIDE the
    field it was supposed to stay out of.

    Measured 2026-08-22, 22:19:20: f2 ran west down the dock aisle at
    0.699 m/s with its nav guard reporting 5.2 m and clear; its fork
    corners reached 2.33 m off parked f1 on S1, both warning fields
    dropped, V_Limit went 1500 -> 300 with the wheels at 700 mm/s, and
    the speed monitor latched. The truck needed a panel RESET to move
    again, and it did it twice.
    """
    mount_offset = 0.55 + 0.68        # nav lidar to fork corner, model.sdf
    reclear = field_eval.FIELDS[1][1] + field_eval.HYSTERESIS_M
    assert follower.GUARD_SLOW_M >= reclear + mount_offset, (
        "the guard fires {:.2f} m INSIDE the warning field at the fork "
        "corners".format(reclear + mount_offset - follower.GUARD_SLOW_M))
    # And it still has to leave the truck room to actually slow down:
    # 0.70 -> 0.30 m/s took 0.35 m on the odometry of the same run.
    assert follower.GUARD_SLOW_M >= reclear + mount_offset + 0.35
    # The HOLD band is not touched by any of this and stays inside it.
    assert follower.GUARD_HOLD_M < follower.GUARD_SLOW_M


def test_guard_hold_band_stops():
    assert follower.target_speed(10.0, 0.0, 1.2) == 0.0


def test_sector_min_sees_only_the_travel_sector():
    # 360 rays, angle_min=-pi, 1 deg steps. Travel direction is angle pi
    # (the fork end, model -x). A 2 m return within the sector counts; a
    # 0.5 m return behind the truck (angle 0) does not.
    n = 360
    inc = 2.0 * math.pi / n
    ranges = [math.inf] * n
    ranges[0] = 2.0          # angle_min + 0*inc = -pi == pi (wrapped): in sector
    ranges[180] = 0.5        # angle 0: dead astern, out of sector
    got = follower.sector_min(ranges, -math.pi, inc, 0.10, 8.0)
    assert abs(got - 2.0) < 1e-9


def test_sector_min_ignores_out_of_range_returns():
    n = 360
    inc = 2.0 * math.pi / n
    ranges = [math.inf] * n
    ranges[0] = 0.05         # below range_lo: sensor noise, not a wall
    assert follower.sector_min(ranges, -math.pi, inc, 0.10, 8.0) == math.inf


def _scan360():
    """360 rays, angle_min=-pi, 1 deg steps. Index i is bearing i-180 deg;
    travel is bearing 180 (index 0, the wrap), so travel-offset in
    degrees is i - 360 for the indices near the end of the sweep."""
    return [math.inf] * 360, 2.0 * math.pi / 360


def test_self_mask_hides_the_near_mast_upright():
    # 1.29 m at bearing 176 deg = travel-offset -4: inside the near
    # upright's window and under its ceiling. That is the truck's own
    # mast, not the world - the guard must see nothing at all.
    ranges, inc = _scan360()
    ranges[356] = 1.29
    assert follower.sector_min(ranges, -math.pi, inc, 0.10, 8.0) == math.inf


def test_self_mask_does_not_hide_a_real_return_beside_it():
    # The mast return is dropped; the 2.5 m wall dead ahead still wins.
    ranges, inc = _scan360()
    ranges[356] = 1.29       # offset -4: mast
    ranges[0] = 2.5          # offset 0: real
    got = follower.sector_min(ranges, -math.pi, inc, 0.10, 8.0)
    assert abs(got - 2.5) < 1e-9


def test_unmasked_bearings_still_guard_between_the_uprights():
    # Offset -15 sits BETWEEN the two windows: a 1.3 m return there is
    # world, and it must beat the masked 1.2 m mast return.
    ranges, inc = _scan360()
    ranges[356] = 1.2        # offset -4: masked
    ranges[345] = 1.3        # offset -15: unmasked, wins
    got = follower.sector_min(ranges, -math.pi, inc, 0.10, 8.0)
    assert abs(got - 1.3) < 1e-9


def test_self_mask_ceiling_lets_a_far_obstacle_through():
    # 1.9 m at offset -4 is BEYOND the 1.6 m ceiling - it cannot be the
    # mast, so it is an obstacle and the guard must report it.
    ranges, inc = _scan360()
    ranges[356] = 1.9
    got = follower.sector_min(ranges, -math.pi, inc, 0.10, 8.0)
    assert abs(got - 1.9) < 1e-9


def test_reverse_phase_enters_above_120_degrees():
    # Target dead astern: backing straight out beats a U-turn.
    assert follower.reverse_phase(math.pi, False)
    assert follower.reverse_phase(-math.pi, False)


def test_reverse_phase_stays_forward_below_75_degrees():
    assert not follower.reverse_phase(math.radians(60.0), False)
    assert not follower.reverse_phase(math.radians(-60.0), False)


def test_reverse_phase_holds_its_state_in_the_dead_band():
    # 90 deg is between EXIT (75) and ENTER (120): whatever the phase
    # was, it stays - that 45 deg band is what stops the chatter.
    a = math.radians(90.0)
    assert follower.reverse_phase(a, True)
    assert not follower.reverse_phase(a, False)
    assert follower.reverse_phase(-a, True)
    assert not follower.reverse_phase(-a, False)


def test_reverse_phase_exits_only_below_the_exit_angle():
    # Reversing at 100 deg keeps reversing; at 70 deg it lets go.
    assert follower.reverse_phase(math.radians(100.0), True)
    assert not follower.reverse_phase(math.radians(70.0), True)


def test_reverse_sector_watches_the_counterweight_end():
    # forward=False centres the same +-35 deg window on angle 0, the
    # counterweight end. A 2 m return there counts.
    ranges, inc = _scan360()
    ranges[180] = 2.0        # angle 0: dead astern, the way we are going
    got = follower.sector_min(
        ranges, -math.pi, inc, 0.10, 8.0, forward=False)
    assert abs(got - 2.0) < 1e-9


def test_reverse_sector_ignores_the_forward_mast_return():
    # The mast sits on the pi side; reversing, it is not even in the
    # sector, let alone a reason to hold.
    ranges, inc = _scan360()
    ranges[356] = 1.29       # the near mast upright
    ranges[180] = 2.0
    got = follower.sector_min(
        ranges, -math.pi, inc, 0.10, 8.0, forward=False)
    assert abs(got - 2.0) < 1e-9


def test_forward_sector_ignores_a_return_behind_the_counterweight():
    # The mirror of the above: forward, the reverse sector's obstacle is
    # none of the guard's business.
    ranges, inc = _scan360()
    ranges[180] = 0.5
    assert follower.sector_min(ranges, -math.pi, inc, 0.10, 8.0) == math.inf


def test_arrival_is_a_quarter_metre():
    assert follower.arrived((0.0, 0.0), (0.20, 0.10))
    assert not follower.arrived((0.0, 0.0), (0.30, 0.0))


def test_arrival_radius_can_be_widened_per_station():
    # A short-spur station cannot be hit to 0.25 m by any gain (the truck
    # orbits its own turning circle), so it declares its own radius.
    assert not follower.arrived((0.0, 0.0), (0.7, 0.0))
    assert follower.arrived((0.0, 0.0), (0.7, 0.0), 0.8)


def test_the_safety_scanners_have_their_own_slow_band():
    """The band the nav lidar structurally cannot provide.

    GUARD_SLOW_M keeps the truck out of a warning field it is driving
    INTO; nothing kept it out of one it is driving PAST, because the
    lidar guard is a +-35 deg cone about the travel heading and a rack
    face 2.75 m off the shoulder is nowhere near it. Measured
    2026-08-22 22:40:28.215: f3 westbound on the main aisle, right
    scanner 2.307 m off rack A, warning dropped, V_Limit 1500 -> 300,
    and the encoders on that same sample read -700/-700. Motor went
    false 8 ms later and stayed false - the speed monitor's demand
    latches - while the wheels spent 300 ms coming down to zero.

    The floor is why it is not a tuning problem: the main aisle gives a
    fork-corner scanner 2.79 m against a 2.70 m re-clear threshold, nine
    centimetres, and no pursuit holds a line that well.
    """
    reclear = field_eval.FIELDS[1][1] + field_eval.HYSTERESIS_M
    assert follower.FIELD_SLOW_M > reclear, (
        "the band is inside the field it exists to keep the truck out of")
    # Room to come down from cruise to the creep ceiling inside it.
    assert follower.FIELD_SLOW_M >= reclear + 0.35

    clear = follower.target_speed(10.0, 0.0, math.inf, math.inf)
    assert clear == follower.CRUISE_MPS
    near = follower.target_speed(10.0, 0.0, math.inf,
                                 follower.FIELD_SLOW_M - 0.01)
    assert near == follower.GUARD_SLOW_MPS
    # It is a SLOW band and never a hold: a protective stop is the
    # F-program's to demand and this file may not pre-empt it.
    assert follower.target_speed(10.0, 0.0, math.inf, 0.0) == \
        follower.GUARD_SLOW_MPS
    # And it does not widen anything: the other bands still win when
    # they are slower.
    assert follower.target_speed(1.0, 0.0, math.inf, 0.0) == \
        follower.APPROACH_MPS
    assert follower.target_speed(10.0, 0.0, 1.0, math.inf) == 0.0


def test_the_field_band_defaults_to_absent():
    """Every caller built before this band existed keeps its behaviour."""
    assert follower.target_speed(10.0, 0.0, math.inf) == follower.CRUISE_MPS
