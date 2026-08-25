"""wheel_odom_core.py's arithmetic. Pure math, no ROS, no Gazebo.

    python3 -m pytest m5_ver3/tests/ -q

THE SIGN TESTS ARE THE CONTRACT, and they are m6/tests/test_follower.py's
contract restated for an ESTIMATOR rather than a controller. Model yaw 0
points the forks at world -x, so the travel heading is model yaw + pi;
forward travel is therefore a NEGATIVE tread speed and a negative shaft
rate; and facing the travel direction, world +y is the driver's right and
a POSITIVE steer angle is what turns that way. If an assertion below
fails after an edit, the edit changed the vehicle's sign convention and
not this file's opinion.

WHAT THESE TESTS ARE ABOUT, IN ONE SENTENCE. This node exists to be WRONG
in two named, measurable ways - the drive reading is floored onto a count
grid, and the radius it multiplies by is 1.5 % too large - because an
odometry that agrees with the simulator's ground truth is ground truth
with extra steps and gives the F2 EKF nothing to correct. So the tests
below check that the designed errors are EXACTLY the designed size, not
that the estimate is accurate.

THE NUMBERS ARE config.yaml's, WRITTEN OUT HERE ON PURPOSE. A test that
read config.yaml would pass for any value in it, including a value that
had been changed by accident: it would be checking that the code reads the
file, which is the shell's job and not the arithmetic's. These are the
constants the arithmetic was derived against, and the day they stop
matching config.yaml's wheel_odom: block is a day somebody has to look.
"""
import math

import pytest

import wheel_odom_core

# config.yaml, section VEHICLE (seeded from agv/forklift/config.yaml).
WHEELBASE_M = 1.05
WHEEL_RADIUS_M = 0.12
REAR_AXLE_OFFSET_M = -0.50
# config.yaml, section WHEEL ODOMETRY.
COUNTS_PER_REV = 1024
WHEEL_RADIUS_SCALE = 1.015
STEER_BIAS_RAD = 0.005

COUNT_RAD = 2.0 * math.pi / COUNTS_PER_REV


def core(scale=1.0, bias=0.0, counts_per_rev=COUNTS_PER_REV):
    """One estimator, with the two error terms defaulted OFF.

    A test about quantisation must not also be a test about the scale
    error: with both on, an assertion that fails names neither of them.
    The tests that are about an error term switch that term on by hand
    and say which one they are measuring.
    """
    return wheel_odom_core.WheelOdometry(
        wheelbase_m=WHEELBASE_M,
        wheel_radius_m=WHEEL_RADIUS_M,
        rear_axle_offset_m=REAR_AXLE_OFFSET_M,
        counts_per_rev=counts_per_rev,
        wheel_radius_scale=scale,
        steer_bias_rad=bias)


def drive(odom, shaft_rad, steer_rad, steps, dt_s=0.002, t0=0.0):
    """Turn the shaft through `shaft_rad` in `steps` equal increments.

    Returns the last estimate. The first call only seeds the encoder -
    one reading is not an interval - so `steps` intervals need steps + 1
    samples.

    NO TEST BELOW PARKS THE SHAFT ON A COUNT EDGE, and the halves in
    figures like 1000.5 counts are that rule showing. n * q / q is not n
    in binary - at n = 1000 it is 999.9999999999999, which floors to 999 -
    so a test that asked for exactly 1000 counts would be asking which
    side of an edge a double landed on. No encoder can answer that
    question and no consumer may depend on the answer, so the tests stand
    half a count clear of it and the assertions stay exact.
    """
    odom.update(t0, 0.0, steer_rad)
    last = None
    for i in range(1, steps + 1):
        last = odom.update(t0 + i * dt_s, shaft_rad * i / steps, steer_rad)
    return last


# --------------------------- the count grid ---------------------------

def test_one_count_is_two_pi_over_the_configured_resolution():
    enc = wheel_odom_core.DriveEncoder(COUNTS_PER_REV)
    assert enc.count_rad == pytest.approx(COUNT_RAD, rel=1e-15)
    # 1024 counts on a 0.12 m wheel is 0.7363 mm of tread per count. That
    # figure is what makes the quantisation VISIBLE at this track's
    # sample rates; config.yaml carries the derivation.
    assert enc.count_rad * WHEEL_RADIUS_M == pytest.approx(7.3631e-4, rel=1e-4)


def test_the_reading_is_floored_onto_the_grid_and_never_rounded():
    enc = wheel_odom_core.DriveEncoder(COUNTS_PER_REV)
    # A real incremental encoder reports the last edge it SAW. It does not
    # round to the nearest edge, which would require it to know about an
    # edge that has not happened yet.
    assert enc.count(0.0) == 0
    assert enc.count(0.999 * COUNT_RAD) == 0
    assert enc.count(1.000 * COUNT_RAD) == 1
    assert enc.count(1.001 * COUNT_RAD) == 1
    assert enc.count(-0.001 * COUNT_RAD) == -1
    assert enc.angle(7.4 * COUNT_RAD) == pytest.approx(7.0 * COUNT_RAD)


def test_the_grid_is_symmetric_in_counts_and_not_in_angle():
    # Astern is the same grid read the other way, and flooring is not an
    # odd function: an estimator that assumed count(-x) == -count(x) would
    # gain a count every time the vehicle changed direction.
    enc = wheel_odom_core.DriveEncoder(COUNTS_PER_REV)
    assert enc.count(-1.5 * COUNT_RAD) == -2
    assert enc.count(1.5 * COUNT_RAD) == 1


# ------------------------- quantisation steps -------------------------

def test_travel_is_always_a_whole_number_of_counts_of_tread():
    odom = core()
    # 12.7 counts of shaft, and the 0.7 is not travelled: it has not
    # crossed an edge yet and the vehicle has no way to know it is there.
    est = drive(odom, 12.7 * COUNT_RAD, 0.0, steps=1)
    assert est.count == 12
    assert est.x == pytest.approx(12.0 * COUNT_RAD * WHEEL_RADIUS_M,
                                  rel=1e-12)


def test_a_sub_count_shaft_movement_is_no_movement_at_all():
    """Zero-speed hold. A vehicle that has not crossed an edge has not
    moved, and it says so - no creep, no dither, no fractional count."""
    odom = core()
    odom.update(0.000, 0.0, 0.0)
    for i, frac in enumerate((0.10, 0.30, 0.60, 0.90, 0.99)):
        est = odom.update(0.002 * (i + 1), frac * COUNT_RAD, 0.0)
        assert est.count == 0
        assert est.x == 0.0 and est.y == 0.0 and est.yaw == 0.0
        assert est.vx == 0.0 and est.vy == 0.0 and est.yaw_rate == 0.0


def test_a_standing_shaft_holds_the_pose_for_ever():
    """The same hold over a long stand, with both error terms ON. A
    quantiser that leaked a fraction of a count per sample would walk the
    truck across the floor while it sat still: the plant publishes this
    channel once per physics step, which is 1.8 million samples an hour.
    """
    odom = core(scale=WHEEL_RADIUS_SCALE, bias=STEER_BIAS_RAD)
    odom.update(0.0, 3.3 * COUNT_RAD, 0.2)
    est = None
    for i in range(1, 5001):
        est = odom.update(0.002 * i, 3.3 * COUNT_RAD, 0.2)
    assert est.x == 0.0 and est.y == 0.0 and est.yaw == 0.0


def test_crossing_one_edge_moves_exactly_one_count_of_tread():
    odom = core()
    odom.update(0.000, 0.9 * COUNT_RAD, 0.0)
    est = odom.update(0.002, 1.1 * COUNT_RAD, 0.0)
    assert est.count == 1
    assert est.x == pytest.approx(COUNT_RAD * WHEEL_RADIUS_M, rel=1e-12)
    # And the speed is that step over the interval - the quantiser's
    # output differenced, never the plant's own rate rounded.
    assert est.vx == pytest.approx(COUNT_RAD * WHEEL_RADIUS_M / 0.002,
                                   rel=1e-12)


def test_the_sub_count_residue_is_kept_and_not_thrown_away():
    """Counts are differenced from an ABSOLUTE angle, never accumulated
    from per-sample differences. Quantising each difference instead would
    discard the residue every sample and lose most of a slow run: 0.6 of
    a count per sample, floored, is zero for ever."""
    odom = core()
    odom.update(0.0, 0.0, 0.0)
    est = None
    for i in range(1, 101):
        est = odom.update(0.002 * i, i * 0.605 * COUNT_RAD, 0.0)
    assert est.count == 60
    assert est.x == pytest.approx(60.0 * COUNT_RAD * WHEEL_RADIUS_M,
                                  rel=1e-12)


# --------------------------- the three signs --------------------------

def test_forward_travel_runs_along_the_model_yaw_plus_pi():
    """Sign 1. The truck spawns at yaw 3.14159 with its forks at world
    +x, so driving FORWARD from there must increase x. config.yaml's
    VEHICLE block and m6/ipc/follower.py's header are the two places that
    say so."""
    odom = core()
    odom.reset(x=0.0, y=0.0, yaw=math.pi)
    est = drive(odom, -500.0 * COUNT_RAD, 0.0, steps=50)
    assert est.x > 0.20
    assert est.y == pytest.approx(0.0, abs=1e-12)
    assert est.yaw == pytest.approx(math.pi, abs=1e-12)


def test_forward_traction_is_negative_linear_x():
    """Sign 2. The twist is in base_link, so forward is the direction the
    forks point, which is the model's own -x."""
    odom = core()
    est = drive(odom, -500.0 * COUNT_RAD, 0.0, steps=50)
    assert est.vx < 0.0
    assert est.x < 0.0            # model yaw 0: forward is world -x too
    # Astern is the mirror of it, read off the same grid.
    odom = core()
    est = drive(odom, +500.0 * COUNT_RAD, 0.0, steps=50)
    assert est.vx > 0.0
    assert est.x > 0.0


def test_positive_steer_in_forward_travel_is_a_driver_right_turn():
    """Sign 3. Facing the travel direction, world +y is the driver's
    right (m6/tests/test_follower.py's header), and a positive steer
    angle is what turns that way. In the MODEL frame that is a DECREASING
    yaw, and the difference between those two sentences is the whole
    reason this test exists."""
    odom = core()
    # yaw 0, so the travel heading is pi: the driver faces world -x and
    # the driver's right is world +y.
    est = drive(odom, -70.0, +0.2, steps=400)
    assert est.yaw < 0.0                 # model frame: clockwise
    assert est.yaw_rate < 0.0
    assert est.y > 0.0                   # world +y: the driver's right
    assert est.x < 0.0                   # and it went forward doing it


def test_negative_steer_in_forward_travel_turns_the_other_way():
    odom = core()
    est = drive(odom, -70.0, -0.2, steps=400)
    assert est.yaw > 0.0
    assert est.y < 0.0


def test_positive_steer_astern_turns_the_opposite_way():
    """The steer angle is a wheel heading, not a turn direction: reverse
    the tread and the same steer swaps the sense of the turn. A vehicle
    that had this wrong would look right for a whole forward run."""
    odom = core()
    est = drive(odom, +70.0, +0.2, steps=400)
    assert est.yaw > 0.0


# ---------------------------- the kinematics --------------------------

def test_a_quarter_turn_matches_the_closed_form_arc():
    """The integrator is exact over a constant-curvature step, so a turn
    taken in 400 of them has to land where one closed-form arc says.

    Rear-axle turn radius R = L / tan(delta) = 1.05 / tan(0.2) =
    5.17983 m. A quarter turn is R * pi/2 = 8.13552 m of rear-axle arc,
    which is 8.13552 / cos(0.2) = 8.30093 m of tread, i.e. 69.1744 rad of
    shaft at r = 0.12 m. Driven FORWARD (negative shaft) at delta = +0.2
    that takes the model yaw from 0 to -pi/2, and the closed form puts
    the rear axle at (-R, +R) from where it started.
    """
    odom = core()
    est = drive(odom, -69.17439, +0.2, steps=400)
    radius = WHEELBASE_M / math.tan(0.2)
    assert est.yaw == pytest.approx(-math.pi / 2.0, abs=2e-3)
    # The rear axle started at (-0.50, 0), because base_link stands
    # 0.50 m forward of it; it ends at (-0.50 - R, +R). base_link is then
    # 0.50 m along the new model heading, which by now points at -y.
    assert est.x == pytest.approx(-0.50 - radius, abs=5e-3)
    assert est.y == pytest.approx(radius - 0.50, abs=5e-3)


def test_base_link_carries_the_lateral_velocity_the_rear_axle_does_not():
    """base_link stands 0.50 m off the rear axle, and the rear axle is
    the only point of a tricycle whose velocity is purely longitudinal.
    Reporting vy = 0 - what differential-drive odometry copied onto a
    tricycle does - would tell the F2 EKF the body is not doing something
    it is doing."""
    odom = core()
    est = drive(odom, -20.0, +0.3, steps=200)
    d = -REAR_AXLE_OFFSET_M
    assert est.vy == pytest.approx(d * est.yaw_rate, rel=1e-12)
    assert est.vy != 0.0


def test_a_straight_run_has_no_lateral_velocity():
    odom = core()
    est = drive(odom, -20.0, 0.0, steps=200)
    assert est.vy == 0.0
    assert est.yaw_rate == 0.0


def test_the_chord_branch_and_the_arc_branch_agree_at_the_seam(monkeypatch):
    """The integrator switches from the exact arc to its own straight-line
    limit at a threshold, and a discontinuity there would be a kink in
    every nearly straight leg.

    THE SAME INPUT IS RUN DOWN BOTH BRANCHES, by moving the threshold
    rather than the steer angle: two different steer angles would be two
    different arcs, and their disagreement would say nothing about the
    seam. The tolerance is what the two spellings cost each other here:
    -2.4 m of tread at delta = 4.4e-7 is dpsi = -1.0e-6 rad, where the
    chord's truncation is s*dpsi^2/24 = 1e-13 m and the arc's
    cancellation is s/dpsi * 1e-16 = 2.4e-10 m. Both are a millionth of
    one count of tread.
    """
    def run():
        return drive(core(), -20.0, 4.4e-7, steps=1)

    monkeypatch.setattr(wheel_odom_core, "_STRAIGHT_RAD", 1e-12)
    arc = run()
    monkeypatch.setattr(wheel_odom_core, "_STRAIGHT_RAD", 1e-3)
    chord = run()
    assert arc.yaw == chord.yaw
    assert arc.x == pytest.approx(chord.x, abs=1e-9)
    assert arc.y == pytest.approx(chord.y, abs=1e-9)


# ---------------------------- the error terms -------------------------

def test_scale_error_over_a_known_straight_is_exactly_the_designed_drift():
    """1000 counts of shaft at r = 0.12 m is 0.736310778 m of ground. The
    estimator believes r * 1.015 = 0.1218 m, so it reports 0.747355440 m
    and the drift is 0.011044662 m - 1.5 % of that distance, and 1.5 % of
    every distance, for ever. That is the term the F2 EKF exists to
    correct, and it is why nothing may compare this node with ground
    truth by an equality."""
    truth = 1000.0 * COUNT_RAD * WHEEL_RADIUS_M
    odom = core(scale=WHEEL_RADIUS_SCALE)
    est = drive(odom, 1000.5 * COUNT_RAD, 0.0, steps=1)
    assert truth == pytest.approx(0.736310778, rel=1e-9)
    assert est.x == pytest.approx(0.747355440, rel=1e-9)
    assert est.x - truth == pytest.approx(0.011044662, abs=1e-9)
    assert est.x - truth == pytest.approx(0.015 * truth, rel=1e-12)


def test_without_the_scale_error_the_straight_lands_on_the_count_grid():
    """The same run with the term switched off, which is what proves the
    drift above belongs to the scale error and not to the quantiser."""
    odom = core(scale=1.0)
    est = drive(odom, 1000.5 * COUNT_RAD, 0.0, steps=1)
    assert est.x == pytest.approx(1000.0 * COUNT_RAD * WHEEL_RADIUS_M,
                                  rel=1e-12)


def test_the_scale_error_compounds_the_same_way_however_it_is_sampled():
    """It is a scale, so the size of the count it multiplies does not
    matter: one step of 1000 counts and 1000 steps of one count land in
    the same place."""
    a = drive(core(scale=WHEEL_RADIUS_SCALE), 1000.5 * COUNT_RAD, 0.0,
              steps=1)
    b = drive(core(scale=WHEEL_RADIUS_SCALE), 1000.5 * COUNT_RAD, 0.0,
              steps=1000)
    assert a.x == pytest.approx(b.x, rel=1e-12)


def test_the_steer_bias_curves_a_run_the_wheels_call_straight():
    """The bias is on the READING, so the wheel is dead straight and the
    estimator believes it is turning. Over 1000 counts the rear axle
    covers s_R = 0.736301 m and the estimator invents
    dpsi = s_R * tan(0.005) / L = 3.50624e-3 rad of heading - 0.2 deg out
    of nothing, per 0.74 m of floor."""
    odom = core(bias=STEER_BIAS_RAD)
    est = drive(odom, 1000.5 * COUNT_RAD, 0.0, steps=1)
    s_r = 1000.0 * COUNT_RAD * WHEEL_RADIUS_M * math.cos(STEER_BIAS_RAD)
    assert est.yaw == pytest.approx(
        s_r * math.tan(STEER_BIAS_RAD) / WHEELBASE_M, rel=1e-9)
    assert est.yaw == pytest.approx(3.50624e-3, rel=1e-5)


def test_the_steer_bias_is_added_to_the_reading_and_not_to_the_command():
    """Sensor side, not actuator side: a wheel truly at -0.005 rad reads
    as dead straight, and the estimator integrates a straight line."""
    odom = core(bias=STEER_BIAS_RAD)
    est = drive(odom, -20.0, -STEER_BIAS_RAD, steps=100)
    assert est.yaw == 0.0
    assert est.y == 0.0


# ------------------------- what is not an estimate --------------------

def test_the_first_reading_is_not_an_estimate():
    """One reading is not an interval. Returning a zero-speed estimate for
    it would put a fabricated sample at the head of every run."""
    odom = core()
    assert odom.update(0.0, 1.234, 0.0) is None


def test_no_interval_is_not_a_small_interval():
    odom = core()
    odom.update(1.0, 0.0, 0.0)
    assert odom.update(1.0, 5.0 * COUNT_RAD, 0.0) is None
    # And time running backwards is refused rather than integrated: it
    # means the world was reset under the node, not that the truck
    # reversed.
    assert odom.update(0.5, 9.0 * COUNT_RAD, 0.0) is None
    # The state survives both refusals intact, so the next good sample
    # differences against the last GOOD one and no counts are lost.
    est = odom.update(1.002, 9.0 * COUNT_RAD, 0.0)
    assert est.count == 9


def test_reset_puts_base_link_where_it_is_told():
    odom = core()
    odom.reset(x=-17.0, y=10.0, yaw=math.pi)
    est = drive(odom, -100.0 * COUNT_RAD, 0.0, steps=10)
    assert est.y == pytest.approx(10.0, abs=1e-12)
    assert est.x > -17.0
