"""nav2_pose.py - the believed pose, and the frame it is carried into.

THE ARITHMETIC IS DATA IN AND DATA OUT. tf2 is not imported here and it
is not imported by the module either: the shell matches the two edges
off the shared /tf and hands this file two tuples, exactly as
drive_goal.on_tf does live. That is what lets the composition be tested
at all - a zero-order hold is a rule about WHICH sample, and a rule is
testable only where the samples are arguments.

THE REGISTRATION IS THE COMMITTED ONE AND ITS GRID IS CHECKED. The
numbers below are read out of m5_ver3/maps/warehouse_v3/registration.yaml
through map_register.load_registration, which refuses a transform whose
.pgm has changed underneath it. Nothing here is typed in except the
answers, and the answers are what a rebuild is supposed to break.
"""
import math
import os

import pytest

import evidence_core as ec
import map_register

import nav2_pose


REG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir, os.pardir, "m5_ver3", "maps", "warehouse_v3",
    "registration.yaml")

F1_SPAWN = (-17.0, 10.0, 3.14159)


def _frame():
    return nav2_pose.load_frame(os.path.normpath(REG))


# ----------------------------------------------------------------------
# the TF pair
# ----------------------------------------------------------------------

def test_two_identity_edges_compose_to_the_identity():
    anchor = nav2_pose.TfSample(t=1.0, x=0.0, y=0.0, yaw=0.0)
    child = nav2_pose.TfSample(t=1.1, x=2.0, y=3.0, yaw=0.5)
    out = nav2_pose.compose(anchor, child)
    assert (out.x, out.y) == (2.0, 3.0)
    assert abs(out.yaw - 0.5) < 1e-12


def test_the_anchor_rotates_the_child_and_then_translates_it():
    # map -> odom is a quarter turn and a metre east; odom -> base_link
    # puts the truck a metre along its own +x.
    anchor = nav2_pose.TfSample(t=1.0, x=1.0, y=0.0, yaw=math.pi / 2.0)
    child = nav2_pose.TfSample(t=1.0, x=1.0, y=0.0, yaw=0.0)
    out = nav2_pose.compose(anchor, child)
    assert abs(out.x - 1.0) < 1e-12
    assert abs(out.y - 1.0) < 1e-12
    assert abs(out.yaw - math.pi / 2.0) < 1e-12


def test_the_composed_stamp_is_the_childs_zero_order_hold():
    # THE PARENT IS HELD, NOT INTERPOLATED - which is all a running node
    # can do (drive_goal.on_tf's own rule, and its measured cost:
    # centimetres against an offline replay that interpolates).
    anchor = nav2_pose.TfSample(t=1.00, x=0.0, y=0.0, yaw=0.0)
    child = nav2_pose.TfSample(t=1.37, x=1.0, y=0.0, yaw=0.0)
    assert nav2_pose.compose(anchor, child).t == 1.37


def test_no_anchor_yet_is_not_an_error_it_is_the_boot_posture():
    child = nav2_pose.TfSample(t=1.0, x=1.0, y=0.0, yaw=0.0)
    assert nav2_pose.compose(None, child) is None
    assert nav2_pose.compose(child, None) is None


def test_a_malformed_sample_is_refused_by_name():
    child = nav2_pose.TfSample(t=1.0, x=1.0, y=0.0, yaw=0.0)
    with pytest.raises(nav2_pose.Nav2PoseError):
        nav2_pose.compose(nav2_pose.TfSample(1.0, float("nan"), 0.0, 0.0),
                          child)


def test_a_sample_is_built_from_the_frame_names_the_shell_matched():
    # The shell matches on BOTH frame names (one shared /tf carries
    # every edge, so a parent alone is not enough) and this is the
    # record it fills in.
    assert nav2_pose.TfSample._fields == ("t", "x", "y", "yaw")


# ----------------------------------------------------------------------
# the registration inverse
# ----------------------------------------------------------------------

def test_the_committed_transform_is_the_one_on_disk():
    frame = _frame()
    record = map_register.load_registration(os.path.normpath(REG))
    assert frame.theta_rad == record["theta_rad"] == -3.138328398
    assert frame.t_x_m == record["t_x_m"] == -17.111857467
    assert frame.t_y_m == record["t_y_m"] == 9.798692466


def test_the_inverse_is_the_explicit_formula_and_not_a_second_rotation():
    # p_world = R(-theta).(p_map - t), yaw_world = yaw_map - theta.
    # AT A HALF TURN A ROTATION IS VERY NEARLY ITS OWN INVERSE
    # (theta is -179.813 deg), so applying the wrong one leaves every
    # magnitude exactly right and puts the truck on the other side of
    # the building. That is why this is written out longhand.
    frame = _frame()
    theta, tx, ty = frame.theta_rad, frame.t_x_m, frame.t_y_m
    for mx, my, myaw in ((0.0, 0.0, 0.0), (12.5, -3.25, 1.0),
                         (-0.079305540, -0.145762011, 0.003261602)):
        dx, dy = mx - tx, my - ty
        want = (math.cos(-theta) * dx - math.sin(-theta) * dy,
                math.sin(-theta) * dx + math.cos(-theta) * dy,
                ec.normalise_angle(myaw - theta))
        got = nav2_pose.to_world(frame, mx, my, myaw)
        assert abs(got[0] - want[0]) < 1e-9
        assert abs(got[1] - want[1]) < 1e-9
        assert abs(ec.normalise_angle(got[2] - want[2])) < 1e-9


def test_the_spawn_round_trips_through_the_committed_numbers():
    frame = _frame()
    in_map = frame.to_map(*F1_SPAWN)
    assert abs(in_map[0] - (-0.079305540)) < 1e-9
    assert abs(in_map[1] - (-0.145762011)) < 1e-9
    assert abs(in_map[2] - 0.003261602) < 1e-9
    back = nav2_pose.to_world(frame, *in_map)
    assert abs(back[0] - F1_SPAWN[0]) < 1e-9
    assert abs(back[1] - F1_SPAWN[1]) < 1e-9
    assert abs(ec.normalise_angle(back[2] - F1_SPAWN[2])) < 1e-9


def test_the_inverse_is_map_frames_own_spelling():
    # ONE SPELLING OF THE TRANSFORM ON THIS TRACK. A second copy of a
    # MECHANISM drifts the way a second copy of a VALUE does.
    frame = _frame()
    assert nav2_pose.to_world(frame, 1.0, 2.0, 0.3) == frame.to_world(
        1.0, 2.0, 0.3)


def test_the_residual_floor_travels_with_the_frame():
    frame = _frame()
    assert frame.residual_max_m == 0.117891
    assert "0.1179" in nav2_pose.floor_sentence(frame)


def test_a_registration_that_is_not_there_is_refused_by_name():
    with pytest.raises(nav2_pose.Nav2PoseError) as caught:
        nav2_pose.load_frame(os.path.normpath(
            os.path.join(os.path.dirname(REG), "no_such_registration.yaml")))
    assert "no_such_registration.yaml" in str(caught.value)


# ----------------------------------------------------------------------
# staleness
# ----------------------------------------------------------------------

def test_the_budgets_are_the_ones_nav_node_measured():
    assert nav2_pose.SENSOR_STALE_S == 0.5
    assert nav2_pose.POSE_CANCEL_S == 1.0
    assert nav2_pose.POSE_CANCEL_S > nav2_pose.SENSOR_STALE_S


def test_a_fresh_sample_is_fresh():
    assert nav2_pose.pose_health(10.0, 9.9) == nav2_pose.FRESH


def test_half_a_second_of_silence_is_a_pose_that_is_gone():
    # The pose is GONE at this budget - zeros flow, routes are refused
    # "no pose" and the state note is "pose stale". The word STALE names
    # the note the operator reads; CANCEL below names what happens next.
    assert nav2_pose.pose_health(10.0, 9.5) == nav2_pose.STALE
    assert nav2_pose.pose_health(10.0, 9.49) == nav2_pose.STALE


def test_a_full_second_of_silence_cancels_the_goal():
    assert nav2_pose.pose_health(10.0, 9.0) == nav2_pose.CANCEL
    assert nav2_pose.pose_health(10.0, 8.0) == nav2_pose.CANCEL


def test_never_having_had_a_sample_is_the_worst_case_and_not_the_best():
    assert nav2_pose.pose_health(10.0, None) == nav2_pose.CANCEL


def test_the_staleness_rule_is_status_contracts_own():
    import status_contract
    assert status_contract.is_stale(9.5, 10.0, nav2_pose.SENSOR_STALE_S)
    assert not status_contract.is_stale(9.6, 10.0, nav2_pose.SENSOR_STALE_S)


# ----------------------------------------------------------------------
# the world-frame Odometry rows
# ----------------------------------------------------------------------

def test_the_odometry_rows_carry_the_world_pose_and_the_body_twist():
    rows = nav2_pose.odometry_rows(
        stamp_s=12.5, world_pose=(-17.0, 10.0, 3.14159),
        body_twist=(-0.300, -0.050), frame_id="map",
        child_frame_id="f1/base_link")
    assert rows["header"]["stamp_s"] == 12.5
    assert rows["header"]["frame_id"] == "map"
    assert rows["child_frame_id"] == "f1/base_link"
    assert rows["pose"]["position"]["x"] == -17.0
    assert rows["pose"]["position"]["y"] == 10.0
    assert rows["pose"]["position"]["z"] == 0.0
    # THE TWIST IS THE EKF's BODY VELOCITY AND NOT A DIFFERENCE OF
    # POSES: vda_agent's `driving` flag reads it, and a differenced
    # estimate would make a standing truck look alive on noise.
    assert rows["twist"]["linear"]["x"] == -0.300
    assert rows["twist"]["angular"]["z"] == -0.050


def test_the_orientation_is_a_yaw_only_quaternion():
    rows = nav2_pose.odometry_rows(
        0.0, (0.0, 0.0, math.pi / 2.0), (0.0, 0.0), "map", "f1/base_link")
    q = rows["pose"]["orientation"]
    assert abs(q["z"] - math.sin(math.pi / 4.0)) < 1e-12
    assert abs(q["w"] - math.cos(math.pi / 4.0)) < 1e-12
    assert q["x"] == 0.0 and q["y"] == 0.0
    yaw = math.atan2(2.0 * q["w"] * q["z"], 1.0 - 2.0 * q["z"] ** 2)
    assert abs(yaw - math.pi / 2.0) < 1e-12


def test_a_non_finite_pose_never_reaches_the_wire():
    with pytest.raises(nav2_pose.Nav2PoseError):
        nav2_pose.odometry_rows(
            0.0, (float("nan"), 0.0, 0.0), (0.0, 0.0), "map", "f1/base_link")


def test_an_unnamed_frame_is_refused_by_name():
    with pytest.raises(nav2_pose.Nav2PoseError) as caught:
        nav2_pose.odometry_rows(0.0, (0.0, 0.0, 0.0), (0.0, 0.0), "",
                                "f1/base_link")
    assert "frame_id" in str(caught.value)


# ----------------------------------------------------------------------
# the selftest
# ----------------------------------------------------------------------

def test_the_selftest_is_green():
    assert nav2_pose._selftest() == 0
