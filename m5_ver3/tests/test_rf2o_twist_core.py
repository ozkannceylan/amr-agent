"""The rf2o relay's arithmetic, as pure logic - F2 Task 3.

WHY THERE IS A RELAY AT ALL, because that is what these tests are about.
`rf2o_laser_odometry` publishes an Odometry that is wrong in three ways
this stack cannot live with, and not one of them is fixable from a
parameter:

  1. ITS FRAME IS NOT THE SCAN'S FRAME. rf2o lays its beams out from
     -fovh/2 to +fovh/2 about the sensor's x axis and never reads
     `angle_min`. forklift_ver3's nav lidar is a 270 deg window from
     +0.7853982 to +5.4977871 rad - centred on model -x on purpose, so
     the blind 90 deg points astern - so rf2o's entire solution is the
     true one rotated by pi. Measured: the truck driving FORWARDS at a
     ground-truth -0.6948 m/s of body vx was published as `linear.x`
     **+0.58**.
  2. THE TWIST COVARIANCE IS ALL ZEROS, never assigned, and
     robot_localization does not ignore a zero variance on a channel it
     is fusing - it substitutes a small number and then believes that
     channel almost absolutely.
  3. THE PUBLISHED `linear.x` IS THE SCANNER'S FORWARD SPEED, and the
     message says `child_frame_id: base_link` anyway. The scanner stands
     0.55 m forward and 0.40 m to starboard of base_link, so in any turn
     the two differ by the lever-arm term.

All three corrections are arithmetic, so all three live in
nodes/rf2o_twist_core.py where a test reaches them without a simulator, a
lidar or ROS - this track's split for every node it has (conftest.py).

THE FOURTH THING TESTED HERE IS A GUARD AND NOT A CORRECTION. A scan
matcher's output is the solution of a least-squares system over a
degenerate-able geometry, divided by a scan-to-scan time difference: it
can produce NaN and it can produce inf. A single NaN reaching
robot_localization poisons the whole state vector permanently, so the
relay drops non-finite samples and counts them. It drops nothing else -
there is no magnitude gate and no scale factor, because a threshold or a
gain fitted to make the tables look better is exactly the hand this
track keeps out of its covariances.
"""
import math

import pytest

import rf2o_twist_core as core


# model.sdf's nav_lidar_link <pose>, which config.yaml copies, and its
# nav_lidar aperture, which the scan message carries.
MOUNT_X = 0.55
MOUNT_Y = -0.40
ANGLE_MIN = 0.7853982
ANGLE_MAX = 5.4977871
CENTRE = core.scan_centre_rad(ANGLE_MIN, ANGLE_MAX)


# ----------------------------------------------------------------------
# the frame rf2o thinks it is in
# ----------------------------------------------------------------------

def test_this_plants_aperture_centre_is_pi():
    assert CENTRE == pytest.approx(math.pi, abs=1e-6)


def test_a_conventionally_written_symmetric_scan_needs_no_rotation():
    # The correction has to be the identity for every lidar spelled the
    # usual way, or it would be a new source of error on a stack that
    # never had this problem.
    assert core.scan_centre_rad(-2.3561945, 2.3561945) == 0.0
    assert core.scan_centre_rad(-math.pi, math.pi) == 0.0


def test_the_centre_is_the_MIDDLE_of_the_window_and_not_its_width():
    # fovh is |max - min| and rf2o computes that itself. What it never
    # computes - and what this is - is where the window sits.
    assert core.scan_centre_rad(1.0, 3.0) == 2.0
    assert core.scan_centre_rad(0.0, 1.0) == 0.5


def test_a_pi_rotation_is_exactly_a_sign_flip_in_the_plane():
    x, y = core.rotate(1.0, 2.0, math.pi)
    assert x == pytest.approx(-1.0)
    assert y == pytest.approx(-2.0)


def test_a_zero_rotation_is_the_identity_to_the_bit():
    assert core.rotate(0.7, -0.3, 0.0) == (0.7, -0.3)


def test_the_rotation_is_the_standard_one_and_not_its_inverse():
    # +90 deg takes body +x onto body +y. Getting this backwards would
    # be invisible on this plant, where the correction is pi and its own
    # inverse - and wrong on every other one.
    x, y = core.rotate(1.0, 0.0, math.pi / 2)
    assert x == pytest.approx(0.0, abs=1e-12)
    assert y == pytest.approx(1.0)


# ----------------------------------------------------------------------
# the lever arm
# ----------------------------------------------------------------------

def test_a_straight_run_is_not_corrected_by_the_lever_arm_at_all():
    # With no yaw rate the scanner and the vehicle have the same
    # velocity, whatever the offset between them. A correction that
    # touched this case would be moving the one profile the whole track
    # measures its distance error on.
    assert core.base_vx(-0.7000, 0.0, MOUNT_Y) == pytest.approx(-0.7000)


def test_the_lever_arm_is_yaw_rate_times_the_LATERAL_offset():
    # v_laser = v_base + w x r, with r the mount in base_link and
    # w = (0, 0, yaw_rate). The cross product's x component is -w*ry, so
    # v_base_x = v_laser_x + w*ry - and the LONGITUDINAL offset does not
    # enter the x equation at all.
    assert core.base_vx(0.0, 1.0, MOUNT_Y) == pytest.approx(-0.40)
    assert core.base_vx(0.0, -1.0, MOUNT_Y) == pytest.approx(+0.40)


def test_the_longitudinal_offset_cannot_reach_vx():
    # Guarding against the easiest possible mistake in this function -
    # using the wrong component of the mount. A scanner mounted straight
    # ahead on the centreline induces no vx error at all, however far
    # forward it is.
    assert core.base_vx(-0.5, 0.3, 0.0) == pytest.approx(-0.5)


def test_the_lever_arm_at_this_plants_worst_measured_yaw_rate():
    # EVIDENCE_FUSION.md 2.4 measures the square's peak yaw rate at
    # 0.2687 rad/s. At the nav lidar's y offset that is 0.1075 m/s of
    # apparent forward speed the vehicle does not have - 15 % of its
    # 0.70 m/s cruise, and it is a BIAS over the whole of a corner
    # rather than noise about it.
    error = core.base_vx(0.0, 0.2687, MOUNT_Y)
    assert error == pytest.approx(-0.10748, abs=1e-5)
    assert abs(error) > 0.15 * 0.70


def test_the_lever_arms_sign_follows_the_turn_and_reverses_with_it():
    left = core.base_vx(-0.70, +0.25, MOUNT_Y)
    right = core.base_vx(-0.70, -0.25, MOUNT_Y)
    assert left != right
    assert (left + right) / 2.0 == pytest.approx(-0.70)


# ----------------------------------------------------------------------
# the two corrections together, on one message
# ----------------------------------------------------------------------

def test_the_measured_forward_run_comes_out_NEGATIVE_like_every_other_estimate():
    # MEASURED ON THIS RIG, drive-straight-20260826-123131: the truck's
    # ground-truth body vx reached -0.6948 m/s and the wheel odometry's
    # -0.7473, both negative because forward on this vehicle is
    # base_link -x. rf2o published +0.58. Without this correction the
    # filter would be told the truck was reversing.
    out = core.decide(vx_raw=0.58, vy_raw=0.0, yaw_rate_raw=0.0,
                      centre_rad=CENTRE, mount_y=MOUNT_Y)
    assert out.publish is True
    assert out.vx < 0.0
    assert out.vx == pytest.approx(-0.58)


def test_the_rotation_is_applied_BEFORE_the_lever_arm():
    # Order matters and the two orders differ by 2*yaw_rate*mount_y.
    # Rotating the sum would put the lever-arm term on the wrong axis by
    # the aperture's centre bearing.
    out = core.decide(vx_raw=0.58, vy_raw=0.0, yaw_rate_raw=0.2687,
                      centre_rad=CENTRE, mount_y=MOUNT_Y)
    assert out.vx == pytest.approx(-0.58 + 0.2687 * MOUNT_Y)
    wrong_order = core.base_vx(0.58, 0.2687, MOUNT_Y) * -1.0
    assert out.vx != pytest.approx(wrong_order)


def test_the_yaw_rate_passes_through_both_corrections_untouched():
    # A rotation of the frame by a constant does not change an angular
    # velocity and neither does a lever arm.
    out = core.decide(vx_raw=0.58, vy_raw=0.0, yaw_rate_raw=-0.2687,
                      centre_rad=CENTRE, mount_y=MOUNT_Y)
    assert out.yaw_rate == pytest.approx(-0.2687)


def test_on_a_conventional_lidar_only_the_lever_arm_survives():
    # The rotation must vanish when the scan is symmetric, so this file
    # is not a plant-specific hack wearing a general name.
    out = core.decide(vx_raw=-0.70, vy_raw=0.0, yaw_rate_raw=0.25,
                      centre_rad=0.0, mount_y=MOUNT_Y)
    assert out.vx == pytest.approx(core.base_vx(-0.70, 0.25, MOUNT_Y))


def test_zero_is_not_mistaken_for_missing():
    # A truck standing still publishes an entirely valid twist of zeros
    # and it must reach the filter: "the estimate says nothing is
    # moving" is information, and dropping it would make the arm silent
    # exactly when the vehicle is stopped - which robot_localization
    # reads as a sensor that has gone away.
    out = core.decide(0.0, 0.0, 0.0, CENTRE, MOUNT_Y)
    assert out.publish is True
    assert out.vx == pytest.approx(0.0, abs=1e-15)
    assert out.yaw_rate == 0.0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_vx_is_DROPPED_and_the_reason_names_it(bad):
    out = core.decide(bad, 0.0, 0.0, CENTRE, MOUNT_Y)
    assert out.publish is False
    assert "vx" in out.reason


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_non_finite_yaw_rate_is_DROPPED_TOO(bad):
    # And it must drop the WHOLE sample rather than publish a good vx
    # beside a bad yaw rate: the lever-arm correction multiplies the two
    # together, so a NaN yaw rate is a NaN vx one line later anyway.
    out = core.decide(0.58, 0.0, bad, CENTRE, MOUNT_Y)
    assert out.publish is False
    assert "yaw" in out.reason


def test_a_non_finite_vy_is_dropped_even_though_vy_is_never_fused():
    # It enters the rotation, so a NaN there is a NaN vx on any scanner
    # whose aperture centre is not a multiple of pi.
    out = core.decide(0.58, float("nan"), 0.0, CENTRE, MOUNT_Y)
    assert out.publish is False
    assert "vy" in out.reason


def test_the_finite_check_is_not_fooled_by_inf_times_zero():
    # inf * 0 is NaN. A vx that is finite beside an infinite yaw rate
    # would pass a check made only on the inputs it was written for.
    assert core.decide(0.0, 0.0, float("inf"), CENTRE, MOUNT_Y).publish \
        is False


# ----------------------------------------------------------------------
# the covariance this relay is allowed to write
# ----------------------------------------------------------------------

def test_an_all_zero_covariance_is_read_as_ABSENT():
    assert core.covariance_is_absent([0.0] * 36) is True


def test_a_covariance_with_ONE_non_zero_entry_is_not_absent():
    # The check is deliberately over the WHOLE matrix and not the
    # diagonal: a future rf2o that filled only the off-diagonal terms
    # would still be a version with an opinion, and this relay must not
    # overwrite it silently.
    for index in (0, 7, 35, 3, 30):
        cov = [0.0] * 36
        cov[index] = 1e-9
        assert core.covariance_is_absent(cov) is False


def test_the_absence_test_is_not_fooled_by_a_short_matrix():
    # Anything that is not 36 numbers is not a covariance, and reading it
    # as "all zeros, so absent" would let the relay overwrite whatever it
    # actually was.
    with pytest.raises(ValueError):
        core.covariance_is_absent([0.0] * 9)


def test_a_NaN_in_the_incoming_covariance_is_not_absent_either():
    cov = [0.0] * 36
    cov[0] = float("nan")
    assert core.covariance_is_absent(cov) is False


# ----------------------------------------------------------------------
# the mount the lever-arm correction is only valid for
# ----------------------------------------------------------------------

def test_an_unrotated_mount_is_accepted():
    assert core.mount_rotation_is_zero((0.0, 0.0, 0.0)) is True


@pytest.mark.parametrize("rpy", [(0.1, 0.0, 0.0), (0.0, 0.1, 0.0),
                                 (0.0, 0.0, 0.1),
                                 (0.0, 0.0, math.pi / 2)])
def test_ANY_mount_rotation_is_refused_because_the_two_term_form_is_wrong(rpy):
    # base_vx() is v_laser_x + w*ry, which assumes the laser LINK's x
    # axis IS base_link's x axis. Rotate the mount and the published
    # lin_speed is a component of a velocity in a frame this arithmetic
    # never sees. It is REFUSED rather than corrected because correcting
    # it needs the scanner's own vy, which rf2o hard-codes to zero.
    assert core.mount_rotation_is_zero(rpy) is False


def test_the_mount_rotation_check_has_no_tolerance_to_hide_a_small_error():
    assert core.mount_rotation_is_zero((0.0, 0.0, 1e-9)) is False
