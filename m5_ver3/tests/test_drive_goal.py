"""The driven-goal bench, as arithmetic - F4 Task 2.

WHAT IS REACHED HERE AND WHAT IS NOT. `tools/drive_goal.py` keeps its
rclpy import inside record()'s own body, which is
tools/sensor_evidence.py's split and exists for this reason: everything
that DECIDES anything - the half turn between a travel heading and a
pose yaw, the arrival arithmetic, the cusp count, the plan lookup, the
steer-activity reduction - runs on the Windows python with no simulator
anywhere. What is not reached is the wiring, and the wiring is what the
bringup gate and the rig runs are for.

THE ONE THAT MATTERS MOST IS THE HALF TURN. This vehicle's forks are at
model -x, so a goal table written as pose yaws would have every entry
pointing the truck the wrong way round - and a run driven that way
arrives COUNTERWEIGHT-FIRST, with the nav lidar's 90 degree blind sector
leading, and still reports SUCCESS. Nothing downstream can see it. So
config.yaml's table says the TRAVEL heading and exactly one function
adds the pi.
"""
import math
import os

import pytest

import drive_goal
import evidence_core as ec


# ----------------------------------------------------------------------
# the half turn
# ----------------------------------------------------------------------

def test_a_travel_heading_becomes_a_pose_yaw_a_half_turn_away():
    assert drive_goal.pose_yaw(0.0) == pytest.approx(math.pi)
    assert drive_goal.pose_yaw(math.pi) == pytest.approx(0.0, abs=1e-12)


def test_the_half_turn_is_WRAPPED_and_not_allowed_to_walk_off_the_circle():
    for travel in (-3.0, -1.5, 0.0, 1.5, 3.0, 3.1415926):
        assert -math.pi - 1e-9 <= drive_goal.pose_yaw(travel) <= math.pi + 1e-9


def test_the_forks_end_up_pointing_along_the_TRAVEL_heading():
    # THE PROPERTY, STATED AS GEOMETRY RATHER THAN AS AN ANGLE. The
    # forks are at model -x, so their world direction is the pose yaw
    # plus pi - and that has to come back out as the travel heading the
    # table asked for.
    for travel in (-2.4, -math.pi / 2, 0.0, 0.7, math.pi / 2):
        forks = ec.normalise_angle(drive_goal.pose_yaw(travel) + math.pi)
        assert forks == pytest.approx(ec.normalise_angle(travel), abs=1e-12)


def test_it_is_its_own_inverse_which_is_what_a_half_turn_is():
    for travel in (-3.0, -0.2, 0.0, 1.1, 3.0):
        assert drive_goal.pose_yaw(drive_goal.pose_yaw(travel)) \
            == pytest.approx(ec.normalise_angle(travel), abs=1e-12)


# ----------------------------------------------------------------------
# the arrival
# ----------------------------------------------------------------------

_GOAL = drive_goal.Goal(name="t", x=-20.0, y=0.0, travel_yaw=-math.pi / 2,
                        pose_yaw=drive_goal.pose_yaw(-math.pi / 2),
                        repeat=1, note="", controller="mppi",
                        bt_xml="behavior_trees/t.xml")


def test_an_exact_arrival_scores_zero_on_every_axis():
    dx, dy, dist, dyaw = drive_goal.arrival(
        _GOAL, (_GOAL.x, _GOAL.y, _GOAL.pose_yaw))
    assert (dx, dy, dist) == (0.0, 0.0, 0.0)
    assert dyaw == pytest.approx(0.0, abs=1e-12)


def test_the_distance_is_a_distance_and_the_components_carry_their_sign():
    dx, dy, dist, _ = drive_goal.arrival(_GOAL, (-20.3, 0.4, 0.0))
    assert dx == pytest.approx(-0.3)
    assert dy == pytest.approx(0.4)
    assert dist == pytest.approx(0.5)


def test_the_heading_error_is_WRAPPED_and_never_a_near_full_turn():
    # A truck arriving at -179 deg against a goal of +179 deg is 2 deg
    # out, not 358. This is SpawnFrame's trap in the smallest place it
    # can appear.
    goal = _GOAL._replace(pose_yaw=math.radians(179.0))
    _, _, _, dyaw = drive_goal.arrival(goal, (goal.x, goal.y,
                                              math.radians(-179.0)))
    assert abs(dyaw) == pytest.approx(math.radians(2.0), abs=1e-9)


# ----------------------------------------------------------------------
# the nearest it ever GOT, which is a different question from where it
# stopped
# ----------------------------------------------------------------------
#
# WHY THIS INSTRUMENT EXISTS. `arrival()` scores where the truck came to
# REST. On a run that did not arrive that is wherever the controller
# gave up - 6.7 m past the goal on one of F4 Task 2's runs and 40 m on
# another - and that number says the run failed without saying why. The
# scan below says how close it came and WHICH WAY it was out when it was
# closest, which is the difference between "it never got there" and "it
# went past on the wrong side by 0.97 m".
#
# THE SYNTHETIC PASS-BY. A truck driving due EAST along y = -1, past a
# goal at the origin whose own travel heading is due east. The closest
# point is directly south of the goal at x = 0, the distance is 1.0, and
# the vehicle is on the RIGHT of the goal's heading - so `across` must
# be NEGATIVE. Every one of those four is a different way of getting the
# frame wrong.

_PASSBY_GOAL = drive_goal.Goal(
    name="passby", x=0.0, y=0.0, travel_yaw=0.0,
    pose_yaw=drive_goal.pose_yaw(0.0), repeat=1, note="",
    controller="mppi", bt_xml="behavior_trees/t.xml")

#: (t, x, y, yaw) driving east along y = -1 from x = -3 to x = +3.
_PASSBY = [(10.0 + i, -3.0 + i, -1.0, math.pi) for i in range(7)]


def test_the_closest_approach_is_the_NEAREST_row_and_not_the_last_one():
    near = drive_goal.closest_approach(_PASSBY_GOAL, _PASSBY, 10.0, 20.0)
    assert near.t == pytest.approx(13.0)
    assert near.x == pytest.approx(0.0)
    assert near.distance == pytest.approx(1.0)
    # and the LAST row is 3 m away, which is what `arrival()` would have
    # scored on a run that ended here
    assert drive_goal.arrival(
        _PASSBY_GOAL, _PASSBY[-1][1:])[2] == pytest.approx(math.hypot(3.0,
                                                                      1.0))


def test_the_components_at_that_row_carry_their_SIGN():
    near = drive_goal.closest_approach(_PASSBY_GOAL, _PASSBY, 10.0, 20.0)
    assert near.dx == pytest.approx(0.0)
    assert near.dy == pytest.approx(-1.0)


def test_ACROSS_is_measured_against_the_GOALs_travel_heading():
    # Driving east, one metre SOUTH of the goal, is one metre to the
    # RIGHT of the goal's own heading - so `across` is negative and
    # `along` is nothing at all.
    near = drive_goal.closest_approach(_PASSBY_GOAL, _PASSBY, 10.0, 20.0)
    assert near.along == pytest.approx(0.0)
    assert near.across == pytest.approx(-1.0)


def test_the_SAME_pass_by_on_a_goal_facing_the_other_way_flips_ACROSS():
    # THE CHECK THAT CATCHES A FRAME TAKEN FROM THE VEHICLE. The truck's
    # own heading is identical in both cases; only the GOAL's travel
    # heading turns, and `across` has to turn with it.
    goal = _PASSBY_GOAL._replace(travel_yaw=math.pi,
                                 pose_yaw=drive_goal.pose_yaw(math.pi))
    near = drive_goal.closest_approach(goal, _PASSBY, 10.0, 20.0)
    assert near.across == pytest.approx(+1.0)
    assert near.distance == pytest.approx(1.0)


def test_the_split_is_a_ROTATION_and_loses_nothing():
    near = drive_goal.closest_approach(_PASSBY_GOAL, _PASSBY, 10.0, 20.0)
    assert math.hypot(near.along, near.across) == pytest.approx(
        near.distance)


def test_the_window_is_the_GOAL_and_not_the_whole_recording():
    # Before the goal was sent the truck stood at the spawn and after
    # the result the bench is watching it coast; neither is an approach.
    # Here the window excludes the row that is actually nearest.
    near = drive_goal.closest_approach(_PASSBY_GOAL, _PASSBY, 14.0, 20.0)
    assert near.t == pytest.approx(14.0)
    assert near.distance == pytest.approx(math.hypot(1.0, 1.0))


def test_a_window_with_no_sample_in_it_is_None_and_not_a_distance():
    # A run whose action was rejected has no approach to report, and
    # reporting a huge number would read as one.
    assert drive_goal.closest_approach(
        _PASSBY_GOAL, _PASSBY, 100.0, 200.0) is None


def test_the_heading_error_at_the_closest_row_is_the_arrival_rule():
    # Same wrapping, same reference: the GOAL's pose yaw, not its travel
    # heading.
    near = drive_goal.closest_approach(_PASSBY_GOAL, _PASSBY, 10.0, 20.0)
    assert near.dyaw == pytest.approx(
        drive_goal.arrival(_PASSBY_GOAL, _PASSBY[3][1:])[3])


# ----------------------------------------------------------------------
# the resting pose
# ----------------------------------------------------------------------

def test_the_window_is_half_open_so_a_sample_is_never_counted_twice():
    assert drive_goal.window([0.0, 1.0, 2.0, 3.0], 1.0, 3.0) == [1, 2]


def test_a_heading_near_pi_is_averaged_as_a_VECTOR_and_not_as_a_NUMBER():
    # THE FAILURE THIS PREVENTS PUTS THE ANSWER ON THE OTHER SIDE OF THE
    # MAP. Two samples at +179 and -179 degrees average to 0 as numbers -
    # dead ahead - and to 180 as unit vectors, which is where the truck
    # is pointing.
    rows = [(0.0, 1.0, 2.0, math.radians(179.0)),
            (0.1, 1.0, 2.0, math.radians(-179.0))]
    _x, _y, yaw = drive_goal.mean_pose(rows, [0, 1])
    assert abs(abs(yaw) - math.pi) < math.radians(1.0)


def test_the_position_is_a_plain_mean():
    rows = [(0.0, 1.0, 2.0, 0.0), (0.1, 3.0, 6.0, 0.0)]
    x, y, _ = drive_goal.mean_pose(rows, [0, 1])
    assert (x, y) == (2.0, 4.0)


# ----------------------------------------------------------------------
# the plan the vehicle was actually following
# ----------------------------------------------------------------------

_PLANS = [(1.0, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]),
          (2.0, [(0.0, 1.0, 0.0), (1.0, 1.0, 0.0)]),
          (3.0, [(0.0, 2.0, 0.0), (1.0, 2.0, 0.0)])]


def _xy(poses):
    return [(x, y) for x, y, _ in poses]


# ----------------------------------------------------------------------
# which way the planner meant the vehicle to go
# ----------------------------------------------------------------------

def test_a_path_that_advances_along_its_own_heading_is_nav2_FORWARD():
    # Which on this vehicle is COUNTERWEIGHT-FIRST, with the nav lidar's
    # 90 degree blind sector leading.
    assert drive_goal.plan_directions(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]) == (2, 0)


def test_a_path_that_advances_AGAINST_its_heading_is_nav2_REVERSE():
    # Which on this vehicle is FORKS-FIRST - its ordinary direction of
    # travel, and the one the scanner aperture is centred on.
    assert drive_goal.plan_directions(
        [(0.0, 0.0, math.pi), (1.0, 0.0, math.pi)]) == (0, 1)


def test_a_cusp_shows_up_as_BOTH_kinds_of_segment_in_one_path():
    poses = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0, 0.0)]
    assert drive_goal.plan_directions(poses) == (1, 1)


def test_a_repeated_pose_is_not_a_segment_at_all():
    poses = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    assert drive_goal.plan_directions(poses) == (1, 0)


def test_the_plan_STANDING_at_a_time_is_the_most_recent_one_before_it():
    assert drive_goal.plan_standing_at(_PLANS, 2.5) == _PLANS[1][1]
    assert drive_goal.plan_standing_at(_PLANS, 3.0) == _PLANS[2][1]


def test_before_the_first_plan_there_is_no_plan_and_that_is_not_an_error():
    # A truth sample from the prelude, before anything was planned, has
    # no plan to be measured against - and reporting a deviation from
    # the FIRST plan there would be a deviation from a path that did not
    # exist yet.
    assert drive_goal.plan_standing_at(_PLANS, 0.5) is None


def test_a_deviation_is_measured_against_the_plan_of_the_moment():
    # THE WHOLE REASON EVERY PLAN IS RECORDED. The tree replans at 1 Hz;
    # scored against the plan the run started with, a vehicle perfectly
    # tracking the third plan would read 2.0 m off.
    against_first = ec.point_to_polyline(0.5, 2.0, _xy(_PLANS[0][1]))
    against_standing = ec.point_to_polyline(
        0.5, 2.0, _xy(drive_goal.plan_standing_at(_PLANS, 3.5)))
    assert against_first == pytest.approx(2.0)
    assert against_standing == pytest.approx(0.0)


def test_a_plan_is_carried_into_the_BUILDING_before_it_is_compared():
    # THE BUG A WHOLE RUN PAID FOR. nav2 publishes /plan in the MAP
    # frame and the ground truth is the world's; warehouse_v3's map is
    # a half turn and 19 m from the building, so a deviation computed
    # without the registration read about 20 m on a vehicle that was
    # tracking its path. plans_of() takes the frame for that reason and
    # the analyser passes it.
    import evidence_core

    class _Table(object):
        def __init__(self, rows):
            self.rows = rows

        def column(self, name):
            index = ("t_s", "plan", "i", "x", "y", "yaw").index(name)
            return [row[index] for row in self.rows]

    table = _Table([(0.0, 1, 0, 1.0, 0.0, 0.0), (0.0, 1, 1, 2.0, 0.0, 0.0)])
    frame = evidence_core.MapFrame(math.pi, 10.0, 0.0)
    raw = drive_goal.plans_of(table)[0][1]
    moved = drive_goal.plans_of(table, frame)[0][1]
    assert raw[0][:2] == (1.0, 0.0)
    assert moved[0][0] == pytest.approx(9.0)


# ----------------------------------------------------------------------
# the steer terminal
# ----------------------------------------------------------------------

def test_the_total_travel_and_the_worst_step_answer_DIFFERENT_questions():
    # A wheel sawing back and forth has a big total and small steps; one
    # hard correction has the reverse. A single figure would hide both.
    saw = [(0.0, 0.0), (0.1, 0.1), (0.2, 0.0), (0.3, 0.1), (0.4, 0.0),
           (0.5, 0.1), (0.6, 0.0)]
    once = [(0.0, 0.0), (0.1, 0.0), (0.2, 0.4), (0.3, 0.4), (0.4, 0.4)]
    saw_total, saw_worst, saw_range = drive_goal.steer_activity(saw)
    one_total, one_worst, one_range = drive_goal.steer_activity(once)
    assert saw_total > one_total
    assert saw_worst < one_worst
    assert saw_range < one_range


def test_a_held_axis_has_no_activity_at_all():
    assert drive_goal.steer_activity(
        [(0.0, 0.3), (0.1, 0.3), (0.2, 0.3)]) == (0.0, 0.0, 0.0)


def test_one_sample_is_not_a_step():
    assert drive_goal.steer_activity([(0.0, 0.3)]) == (0.0, 0.0, 0.0)


# ----------------------------------------------------------------------
# curvature, and what the converter calls a command
# ----------------------------------------------------------------------

def test_a_curvature_is_w_over_v():
    assert drive_goal.curvature_of(-0.7, 0.35, 0.005) == pytest.approx(-0.5)


def test_below_the_CREEP_DEADBAND_the_ratio_is_not_a_curvature():
    # cmd_vel_tricycle_core says so itself: under navcmd.creep_speed_mps
    # it answers with a standing zero and a HELD steer axis, because
    # "the requested curvature is not a number the controller meant".
    assert drive_goal.curvature_of(0.001, 0.35, 0.005) is None
    assert drive_goal.curvature_of(-0.005, 0.35, 0.005) is None


# ----------------------------------------------------------------------
# the jump response
# ----------------------------------------------------------------------

_CMD = [(10.0, 0.0, -0.70, 0.00),
        (10.1, 0.0, -0.70, 0.20),
        (10.2, 0.0, -0.70, -0.10),
        (10.3, 0.0, -0.60, 0.00),
        (12.0, 0.0, -0.70, 0.00)]


def test_the_response_is_a_RANGE_and_not_a_difference_of_endpoints():
    # A controller that swings and comes back inside the window shows
    # NOTHING in a first-to-last subtraction, and a swing is exactly
    # what a jump is expected to produce. Here w goes +0.20 -> -0.10 and
    # ends where it started.
    dv, dw, n = drive_goal.jump_response(10.0, _CMD, 1.0)
    assert n == 4
    assert dv == pytest.approx(0.10)
    assert dw == pytest.approx(0.30)


def test_a_window_with_nothing_in_it_is_None_and_not_a_zero_response():
    # A jump during a stretch with no commands is a jump nobody
    # answered, which is a different fact from one answered with zero.
    assert drive_goal.jump_response(50.0, _CMD, 1.0) is None
    assert drive_goal.jump_response(12.0, _CMD, 1.0) is None


# ----------------------------------------------------------------------
# the real-time factor
# ----------------------------------------------------------------------

def test_the_rtf_is_sim_seconds_per_wall_second():
    rows = [(0.0, 100.0, 0.0, 0.0), (5.0, 110.0, 0.0, 0.0)]
    assert drive_goal.real_time_factor(rows) == pytest.approx(0.5)


def test_a_stalled_wall_clock_is_None_rather_than_an_infinite_factor():
    rows = [(0.0, 100.0, 0.0, 0.0), (5.0, 100.0, 0.0, 0.0)]
    assert drive_goal.real_time_factor(rows) is None
    assert drive_goal.real_time_factor(rows[:1]) is None


# ----------------------------------------------------------------------
# the table, read through _common
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def cfg():
    import _common
    return _common.load_config("test_drive_goal", drive_goal.REQUIRED_KEYS)


def test_every_goal_in_config_yaml_reads_back(cfg):
    for name in cfg.raw("nav.goals"):
        goal = drive_goal.read_goal(cfg, name)
        assert goal.name == name
        # EVERY GOAL IS DRIVEN AT LEAST ONCE FOR THE EVIDENCE, EXCEPT THE
        # ONE THAT CANNOT BE DRIVEN AT ALL. F4 Task 2.5 added a goal
        # inside RackSW3 to demonstrate the fail-fast in the direction
        # that fails; it carries `repeat: 0` because it is not part of
        # the shipped set, and `route_node: false` because it is not a
        # place on the road graph.
        # AND F4 TASK 3 ADDED A SECOND KIND OF ZERO. A goal reached only
        # through nav.cases carries `case_only: true` and no repeat of
        # its own, because the CASE owns that count -
        # tests/test_nav2_params.py holds both directions of that flag.
        row = cfg.raw("nav.goals")[name]
        if row.get("route_node") is False or row.get("case_only") is True:
            assert goal.repeat == 0
        else:
            assert goal.repeat >= 1
        assert goal.pose_yaw == pytest.approx(
            drive_goal.pose_yaw(goal.travel_yaw))


def test_a_goal_that_is_not_in_the_table_is_REFUSED_by_name(cfg):
    class _Stop(Exception):
        pass

    lines = []

    def refuse(check, owner, *rest):
        lines.extend([check, owner] + list(rest))
        raise _Stop()

    original, cfg.refuse = cfg.refuse, refuse
    try:
        with pytest.raises(_Stop):
            drive_goal.read_goal(cfg, "not_a_goal")
    finally:
        cfg.refuse = original
    text = "\n".join(lines)
    # THE REFUSAL LISTS THE ONES THAT DO EXIST, which is this track's
    # rule everywhere: an operator who is refused needs the answer and
    # not only the complaint.
    for name in cfg.raw("nav.goals"):
        assert name in text


def test_the_goal_is_carried_into_the_MAP_by_the_committed_registration(cfg):
    # NOT BY A SECOND COPY OF THE TRANSFORM. goal_in_map() calls
    # map_register.load_registration(), which hashes the grid on disk
    # against the registration on its way past - so a goal is never
    # carried into a map the transform no longer belongs to.
    goal = drive_goal.read_goal(cfg, cfg.s("nav.default_goal"))
    frame, at = drive_goal.goal_in_map(cfg, goal)
    back = frame.to_world(*at)
    assert back[0] == pytest.approx(goal.x, abs=1e-9)
    assert back[1] == pytest.approx(goal.y, abs=1e-9)
    assert back[2] == pytest.approx(goal.pose_yaw, abs=1e-9)


def test_the_map_pose_is_NOT_the_world_pose_which_is_why_it_is_transformed(
        cfg):
    # The frozen grid is about a half turn from the building
    # (registration.yaml theta_rad = -3.1383). A goal sent in world
    # coordinates would land on the other side of the map with every
    # magnitude exactly right.
    goal = drive_goal.read_goal(cfg, cfg.s("nav.default_goal"))
    _frame, at = drive_goal.goal_in_map(cfg, goal)
    assert math.hypot(at[0] - goal.x, at[1] - goal.y) > 1.0


def test_the_bench_writes_and_reads_the_SAME_stream_names():
    # A recorder and an analyser that disagree about a filename produce
    # a session that records everything and analyses nothing.
    assert set(drive_goal.STREAMS) >= {
        "cmd_vel", "cmd_vel_smoothed", "steer_cmd", "traction_cmd",
        "ground_truth", "map_odom", "odom_base", "plan", "feedback"}
    for columns in drive_goal.STREAMS.values():
        assert columns[0] == "t_s"


def test_only_the_controller_stream_carries_BOTH_clocks():
    # The real-time factor is the ratio of the two, and the controller's
    # is the only stream that runs at a fixed rate for the whole drive.
    both = [name for name, cols in drive_goal.STREAMS.items()
            if "t_wall" in cols]
    assert both == ["cmd_vel"]


def test_this_bench_never_publishes_a_TWIST_anywhere():
    # F4 constraint 18: the command path has ONE publisher at a time.
    # A bench that raced the controller for /cmd_vel would be measuring
    # the race. It publishes exactly one thing - an action goal.
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "tools", "drive_goal.py"),
              encoding="utf-8") as handle:
        body = handle.read()
    assert "create_publisher" not in body


# ----------------------------------------------------------------------
# THE NO-PROGRESS GUARD, F4 Task 2.5
#
# nav2's own SimpleProgressChecker asks whether the vehicle MOVED. The
# failure this phase measured is a vehicle that moved 130.199 m without
# moving TOWARD anything, so the question has to be asked about the
# GOAL. ClosingWatch is that question and nothing else: it is fed the
# straight-line distance from the BELIEVED pose to the goal and it gives
# up when that distance stops improving.
# ----------------------------------------------------------------------

def _watch(closing_m=0.50, allowance_s=30.0):
    return drive_goal.ClosingWatch(closing_m, allowance_s)


def test_a_vehicle_that_keeps_closing_is_never_given_up_on():
    watch = _watch()
    d = 20.0
    for i in range(400):
        assert watch.step(i * 0.5, d) is None
        d -= 0.05
    assert d < 1.0


def test_a_vehicle_that_stops_closing_is_given_up_on_AT_the_allowance():
    watch = _watch(0.50, 30.0)
    assert watch.step(0.0, 10.0) is None
    # holding station: every sample is the same distance
    assert watch.step(30.0, 10.0) is None       # exactly at, not past
    verdict = watch.step(30.1, 10.0)
    assert verdict is not None
    assert verdict.t == pytest.approx(30.1)
    assert verdict.distance == pytest.approx(10.0)


def test_it_is_a_FAILURE_TO_IMPROVE_and_not_a_speed_test():
    # THE DISTINCTION THAT MAKES IT DIFFERENT FROM SimpleProgressChecker.
    # This vehicle is moving 0.3 m every sample and covers 9 m of ground,
    # in a circle. Nothing about its MOTION is wrong; it is not getting
    # anywhere.
    watch = _watch(0.50, 30.0)
    fired = None
    for i in range(120):
        t = i * 0.5
        d = 8.0 + math.sin(i * 0.3) * 0.4          # orbiting, never closing
        fired = fired or watch.step(t, d)
    assert fired is not None
    assert fired.t <= 31.0


def test_closing_by_LESS_than_the_margin_does_not_reset_the_clock():
    # A vehicle creeping in at a centimetre a second is not closing, and
    # a rule that reset on any improvement at all would never fire.
    watch = _watch(0.50, 30.0)
    fired = None
    for i in range(200):
        t = i * 0.5
        fired = fired or watch.step(t, 10.0 - i * 0.002)   # 0.001 m/s
    assert fired is not None


def test_the_mark_moves_when_the_vehicle_earns_it_and_the_clock_restarts():
    watch = _watch(0.50, 30.0)
    assert watch.step(0.0, 10.0) is None
    assert watch.step(20.0, 9.4) is None           # earned a new mark
    assert watch.step(45.0, 9.4) is None           # 25 s since THAT mark
    assert watch.step(51.0, 9.4) is not None       # 31 s since it


def test_a_jump_AWAY_from_the_goal_cannot_provoke_it():
    # A map -> odom correction that moves the belief away is not an
    # improvement, so it neither resets the mark nor counts as progress -
    # it can only delay this guard, never trigger it early.
    watch = _watch(0.50, 30.0)
    assert watch.step(0.0, 10.0) is None
    assert watch.step(1.0, 10.65) is None          # a 0.65 m step away
    assert watch.step(2.0, 9.40) is None           # and back past the mark
    assert watch.step(31.0, 9.40) is None          # clock ran from t=2.0
    assert watch.step(33.5, 9.40) is not None


def test_the_first_sample_is_a_mark_and_not_a_verdict():
    assert _watch().step(1000.0, 42.0) is None


def test_no_progress_at_is_the_same_rule_over_a_whole_recording():
    # ONE IMPLEMENTATION, TWO ENTRY POINTS. `record` steps it live and
    # `analyse` runs it over a session that is already on disk; if these
    # two could disagree the bench would report one thing and have done
    # another.
    samples = [(i * 0.5, 10.0) for i in range(200)]
    fired = drive_goal.no_progress_at(samples, 0.50, 30.0)
    assert fired is not None and fired.t == pytest.approx(30.5)
    closing = [(i * 0.5, 10.0 - i * 0.1) for i in range(90)]
    assert drive_goal.no_progress_at(closing, 0.50, 30.0) is None


def test_an_empty_recording_has_no_verdict_rather_than_a_default_one():
    assert drive_goal.no_progress_at([], 0.50, 30.0) is None


# ----------------------------------------------------------------------
# THE CURVATURE-FOLLOWING GAIN, F4 Task 2.5 - the diagnosis instrument
#
# The deviation figure says how FAR the vehicle is from its path. It
# cannot say whether the vehicle is STEERING the path, because a plan
# re-anchored at the robot every second puts the robot on the path by
# construction. This asks the other question: of the yaw rate the plan's
# own curvature required, how much did the controller command?
# ----------------------------------------------------------------------

def test_a_controller_that_obeys_the_plan_has_a_gain_of_one():
    required = [0.10, 0.20, -0.15, 0.05]
    got = drive_goal.curvature_following(required, list(required))
    assert got.gain == pytest.approx(1.0)
    assert got.n == 4


def test_a_controller_that_ignores_the_plan_has_a_gain_of_ZERO():
    # THIS IS THE MEASURED CASE. The plan asked for a turn on every
    # sample and the controller commanded a straight line.
    got = drive_goal.curvature_following([0.10, 0.20, 0.30], [0.0, 0.0, 0.0])
    assert got.gain == pytest.approx(0.0)


def test_a_controller_at_half_authority_reads_a_half():
    got = drive_goal.curvature_following([0.2, 0.4], [0.1, 0.2])
    assert got.gain == pytest.approx(0.5)


def test_a_plan_that_never_asked_for_a_turn_has_NO_gain_not_a_zero_one():
    # DIVIDING BY NOTHING. A straight plan puts no demand on the
    # controller, so there is nothing to be a fraction of, and reporting
    # 0.0 there would read as a broken controller on a straight line.
    assert drive_goal.curvature_following([0.0, 0.0], [0.1, 0.2]).gain is None


def test_the_gain_is_a_REGRESSION_and_not_a_ratio_of_means():
    # Two samples whose means cancel: a ratio of means would read 0.0
    # and say the controller did nothing, when it tracked perfectly.
    got = drive_goal.curvature_following([0.3, -0.3], [0.3, -0.3])
    assert got.gain == pytest.approx(1.0)


def test_an_empty_pair_is_refused_rather_than_answered():
    with pytest.raises(ec.EvidenceError):
        drive_goal.curvature_following([], [])


def test_the_two_series_must_be_the_same_length():
    with pytest.raises(ec.EvidenceError):
        drive_goal.curvature_following([0.1, 0.2], [0.1])


def test_the_demand_the_gain_is_a_fraction_OF_is_reported_beside_it():
    # A GAIN WITHOUT ITS DEMAND IS UNREADABLE, and that is the trap this
    # instrument set on its first use: a fixed controller never leaves
    # its line, so its plan asks for nothing and a gain over that
    # nothing is quantisation. Both numbers are printed and both are
    # quoted wherever either is.
    loud = drive_goal.curvature_following([0.09, -0.09], [0.0, 0.0])
    quiet = drive_goal.curvature_following([0.001, -0.001], [0.0, 0.0])
    assert loud.gain == pytest.approx(0.0)
    assert quiet.gain == pytest.approx(0.0)
    assert loud.demand_rms > quiet.demand_rms * 50


def test_the_demand_rms_is_an_RMS_and_not_a_mean():
    # A leg that turns one way and then the other has a mean demand of
    # zero and is not a plan that asked for nothing.
    got = drive_goal.curvature_following([0.2, -0.2], [0.0, 0.0])
    assert got.demand_rms == pytest.approx(0.2)
    assert got.required.mean == pytest.approx(0.0)


# ----------------------------------------------------------------------
# THE PLAN'S OWN CURVATURE, and the merge that reads one per command
# ----------------------------------------------------------------------

def _arc(radius, count=40, step=0.05):
    """A planned path of `count` poses on a circle of `radius`."""
    poses = []
    for i in range(count):
        theta = i * step / radius
        poses.append((radius * math.sin(theta),
                      radius * (1.0 - math.cos(theta)), theta))
    return poses


def test_the_curvature_of_a_planned_arc_is_one_over_its_radius():
    got = drive_goal.plan_curvature_at(_arc(1.25), 0.0, 0.0, 4)
    assert got == pytest.approx(1.0 / 1.25, rel=1e-3)


def test_a_straight_plan_has_no_curvature_in_it():
    poses = [(x * 0.1, 0.0, 0.0) for x in range(20)]
    assert drive_goal.plan_curvature_at(
        poses, 0.5, 0.0, 4) == pytest.approx(0.0)


def test_the_curvature_is_read_where_the_VEHICLE_is_not_at_the_start():
    # Straight for a metre, then a left turn. Asked at the start the
    # answer is zero; asked a metre along it is the turn. A plan is
    # re-anchored at the vehicle every second, so an instrument that
    # read the head of the path would answer a different question every
    # cycle.
    straight = [(x * 0.1, 0.0, 0.0) for x in range(11)]
    turn = [(1.0 + 1.25 * math.sin(i * 0.04 / 1.25),
             1.25 * (1.0 - math.cos(i * 0.04 / 1.25)), i * 0.04 / 1.25)
            for i in range(1, 30)]
    poses = straight + turn
    assert drive_goal.plan_curvature_at(
        poses, 0.0, 0.0, 4) == pytest.approx(0.0)
    assert drive_goal.plan_curvature_at(poses, 1.05, 0.02, 4) > 0.5


def test_the_tail_of_a_path_has_no_span_left_and_is_None_not_zero():
    poses = [(x * 0.1, 0.0, 0.0) for x in range(6)]
    assert drive_goal.plan_curvature_at(poses, 0.5, 0.0, 4) is None


def test_a_one_pose_plan_is_None_and_not_an_index_error():
    assert drive_goal.plan_curvature_at([(0.0, 0.0, 0.0)], 0.0, 0.0, 4) is None


def test_the_demand_walk_scores_one_pair_per_command_in_the_window():
    plans = [(0.0, _arc(1.25, count=200, step=0.05))]
    truth = [(i * 0.05, 0.0, 0.0, 0.0) for i in range(40)]
    cmd = [(i * 0.05, 0.0, -0.30, -0.24) for i in range(40)]
    required, commanded = drive_goal.curvature_demand(
        cmd, truth, plans, 0.0, 2.0, 0.05, 4)
    assert len(required) == len(commanded) == 40
    # 1/1.25 per metre driven at 0.30 m/s IS 0.24 rad/s
    assert required[0] == pytest.approx(0.24, rel=1e-2)


def test_a_command_below_the_follow_deadband_is_not_a_curvature_sample():
    # At a stop the demand per metre is real and the yaw rate it asks
    # for is zero; scoring it would flatter any gain toward its own
    # intercept.
    poses = _arc(1.25, count=200, step=0.05)
    cmd = [(0.0, 0.0, -0.30, -0.24), (0.05, 0.0, -0.001, 0.0)]
    truth = [(0.0, 0.0, 0.0, 0.0), (0.05, 0.0, 0.0, 0.0)]
    required, _ = drive_goal.curvature_demand(
        cmd, truth, [(0.0, poses)], 0.0, 2.0, 0.05, 4)
    assert len(required) == 1


def test_commands_before_the_first_plan_are_not_scored_against_nothing():
    poses = _arc(1.25, count=200, step=0.05)
    cmd = [(0.0, 0.0, -0.30, -0.24), (5.0, 0.0, -0.30, -0.24)]
    truth = [(0.0, 0.0, 0.0, 0.0), (5.0, 0.0, 0.0, 0.0)]
    required, _ = drive_goal.curvature_demand(
        cmd, truth, [(1.0, poses)], 0.0, 10.0, 0.05, 4)
    assert len(required) == 1


def test_the_demand_walk_honours_its_window():
    poses = _arc(1.25, count=200, step=0.05)
    cmd = [(i * 1.0, 0.0, -0.30, -0.24) for i in range(10)]
    truth = [(i * 1.0, 0.0, 0.0, 0.0) for i in range(10)]
    required, _ = drive_goal.curvature_demand(
        cmd, truth, [(0.0, poses)], 3.0, 6.0, 0.05, 4)
    assert len(required) == 4


# ----------------------------------------------------------------------
# THE APPROACH CORRIDOR, F4 Task 2.5 - deliverable 4's instrument
#
# A goal box is latched on the BELIEVED pose, so the box decides how far
# into its own endgame the vehicle drives, and on a tricycle the endgame
# is where the heading is spent. This table is what each candidate box
# would have COST in arrival heading, read off one approach.
# ----------------------------------------------------------------------

class _Goal(object):
    x = 0.0
    y = 0.0
    pose_yaw = math.pi
    travel_yaw = 0.0
    name = "test"


def _closing(dyaw_at):
    """Rows walking in from 3 m to 0.1 m along -x, heading given by d."""
    rows = []
    for i in range(291):
        d = 3.0 - i * 0.01
        rows.append((100.0 + i * 0.05, -d, 0.0,
                     ec.normalise_angle(math.pi + dyaw_at(d))))
    return rows


def test_each_box_reports_the_FIRST_row_inside_it():
    rows = _closing(lambda d: 0.0)
    rungs, closest = drive_goal.approach_corridor(
        _Goal(), rows, rows, 0.0, 1e9, ["1.00", "0.50"], 0.50)
    assert [r.box for r in rungs] == [1.0, 0.5]
    assert rungs[0].believed == pytest.approx(1.0, abs=0.011)
    assert rungs[1].believed == pytest.approx(0.5, abs=0.011)
    assert closest == pytest.approx(0.1, abs=0.011)


def test_a_box_the_run_never_reached_is_ABSENT_and_not_a_met_rung():
    # THE FAILURE THIS PREVENTS. Reporting the closest approach against
    # a box it never entered would put a number in the row and read as
    # a box that was satisfied.
    rows = _closing(lambda d: 0.0)
    rungs, _ = drive_goal.approach_corridor(
        _Goal(), rows, rows, 0.0, 1e9, ["1.00", "0.05"], 0.50)
    assert [r.box for r in rungs] == [1.0]


def test_the_heading_column_is_read_AT_that_row_and_not_at_the_end():
    # The heading degrades as the vehicle closes, which is the whole
    # finding: a table that reported one heading for every box would
    # say nothing.
    rows = _closing(lambda d: 0.5 - 0.15 * d)
    rungs, _ = drive_goal.approach_corridor(
        _Goal(), rows, rows, 0.0, 1e9, ["2.00", "1.00", "0.25"], 0.50)
    got = [r.dyaw for r in rungs]
    assert got[0] < got[1] < got[2]
    assert got[0] == pytest.approx(0.2, abs=0.01)
    assert got[2] == pytest.approx(0.4625, abs=0.01)


def test_the_rungs_come_out_LARGEST_box_first():
    rows = _closing(lambda d: 0.0)
    rungs, _ = drive_goal.approach_corridor(
        _Goal(), rows, rows, 0.0, 1e9, ["0.30", "2.00", "1.00"], 0.50)
    assert [r.box for r in rungs] == [2.0, 1.0, 0.3]


def test_the_walk_is_CUT_where_the_run_gave_up_and_came_back():
    # A run that misses comes back at its goal from a heading the first
    # pass never had. The second pass must not supply rungs the first
    # one did not reach.
    approach = _closing(lambda d: 0.0)[:251]          # in to 0.5 m
    away, t = [], approach[-1][0]
    for i in range(1, 200):                            # back out to 2.5 m
        away.append((t + i * 0.05, -(0.5 + i * 0.01), 0.0, math.pi))
    back = []
    for i in range(1, 200):                            # and in again
        back.append((away[-1][0] + i * 0.05,
                     -(2.5 - i * 0.013), 0.0, math.pi))
    rows = approach + away + back
    rungs, closest = drive_goal.approach_corridor(
        _Goal(), rows, rows, 0.0, 1e9, ["1.00", "0.50", "0.20"], 0.50)
    assert [r.box for r in rungs] == [1.0, 0.5]
    assert closest == pytest.approx(0.5, abs=0.011)


def test_a_run_that_ARRIVES_is_never_cut():
    rows = _closing(lambda d: 0.0)
    walk = drive_goal.first_approach(_Goal(), rows, 0.0, 1e9, 0.50)
    assert len(walk) == len(rows)


def test_an_empty_window_is_no_corridor_rather_than_an_empty_one():
    rungs, closest = drive_goal.approach_corridor(
        _Goal(), [], [], 0.0, 1e9, ["1.00"], 0.50)
    assert rungs == [] and closest is None


def test_the_truth_column_is_the_truth_AT_that_moment_not_at_rest():
    # The box is evaluated on the BELIEF and the truth is one moving
    # localisation offset behind it. Printing only one of the two would
    # make the other look like an instrument error.
    believed = _closing(lambda d: 0.0)
    truth = [(t, x - 0.09, y, yaw) for t, x, y, yaw in believed]
    rungs, _ = drive_goal.approach_corridor(
        _Goal(), believed, truth, 0.0, 1e9, ["1.00"], 0.50)
    assert rungs[0].truth == pytest.approx(rungs[0].believed + 0.09, abs=0.011)


# ----------------------------------------------------------------------
# THE CONFIGURATION HASH, F4 Task 2.5
#
# `nav=on@<md5>` is nav2.yaml's raw BYTES, so a comment-only edit
# re-labels a configuration and `analyse` then refuses to table a
# measured set beside the very file it was measured on. That is not
# hypothetical: it happened to F4 Task 2's shipped set (`d430334b` ->
# `6555ac39`, comments only) and twice more during F4 Task 2.5. This is
# the same file hashed as a CONFIGURATION instead.
# ----------------------------------------------------------------------

def _yaml(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_a_comment_only_edit_does_not_change_the_CONFIG_hash(tmp_path):
    plain = "node:@  ros__parameters:@    x: 1.0@    y: 2@"
    noisy = ("# an argument nobody had written down yet@node:@"
             "  ros__parameters:@    x: 1.0@    # and why@    y: 2@")
    a = _yaml(tmp_path / "a.yaml", plain.replace("@", chr(10)))
    b = _yaml(tmp_path / "b.yaml", noisy.replace("@", chr(10)))
    assert open(a, "rb").read() != open(b, "rb").read()
    assert drive_goal.config_md5(a) == drive_goal.config_md5(b)


def test_key_ORDER_is_not_a_configuration_change(tmp_path):
    a = _yaml(tmp_path / "a.yaml",
              "node:@  ros__parameters:@    x: 1.0@    y: 2@".replace(
                  "@", chr(10)))
    b = _yaml(tmp_path / "b.yaml",
              "node:@  ros__parameters:@    y: 2@    x: 1.0@".replace(
                  "@", chr(10)))
    assert drive_goal.config_md5(a) == drive_goal.config_md5(b)


def test_the_config_hash_moves_when_a_VALUE_moves(tmp_path):
    a = _yaml(tmp_path / "a.yaml",
              "node:@  ros__parameters:@    x: 1.0@".replace("@", chr(10)))
    b = _yaml(tmp_path / "b.yaml",
              "node:@  ros__parameters:@    x: 1.00001@".replace("@", chr(10)))
    assert drive_goal.config_md5(a) != drive_goal.config_md5(b)


def test_the_two_hashes_of_the_SHIPPED_file_are_not_the_same_number(cfg):
    # They are not interchangeable and the session records both. If they
    # were equal by construction this pair would be checking nothing.
    import hashlib
    path = os.path.join(drive_goal._common.REPO, cfg.s("nav.params_file"))
    with open(path, "rb") as handle:
        raw = handle.read()
    assert drive_goal.config_md5(path) != hashlib.md5(raw).hexdigest()[:8]


def test_nav_label_carries_the_tree_the_budget_and_BOTH_hashes(cfg):
    label = drive_goal.nav_label(cfg)
    for key in ("nav_params", "nav_params_md5", "nav_config_md5",
                "nav_bt", "nav_bt_md5", "nav_budget_ms"):
        assert key in label, key
    assert int(label["nav_budget_ms"]) == 335000
    assert len(label["nav_config_md5"]) == 8


def test_the_budget_on_the_session_is_the_one_in_the_TREE(cfg):
    # The `nav=` label does not hash the behaviour tree at all, so two
    # runs behind two DIFFERENT trees wear the same label. F4 Task 2.5
    # put a navigation budget in that tree, which makes it a live hazard
    # rather than a theoretical one.
    import re as _re
    body = open(os.path.join(drive_goal._common.REPO, cfg.s("nav.bt_xml")),
                encoding="utf-8").read()
    found = _re.search(r'<Timeout[^>]*msec="([0-9]+)"', body)
    assert int(drive_goal.nav_label(cfg)["nav_budget_ms"]) == int(
        found.group(1))


# ----------------------------------------------------------------------
# THE ALIGN-GATE SCAN, F4 Task 2.5 fix round 1
#
# The figure the whole diagnosis turns on - "0 of 1000 plans could ever
# have cleared PathAlignCritic's gate" - was a one-off script when it
# was first read. It is an instrument now, because a claim that a
# critic never ran is the last claim on this track that should live in
# somebody's shell history.
# ----------------------------------------------------------------------

def test_the_reachable_index_is_where_the_horizon_runs_out_of_path():
    # 0.10 m between poses, 0.84 m of horizon -> index 8.
    poses = [(x * 0.1, 0.0, 0.0) for x in range(40)]
    assert drive_goal.plan_reach(poses, 0.84) == 8
    assert drive_goal.plan_reach(poses, 2.01) == 20


def test_a_horizon_longer_than_the_PLAN_stops_at_the_last_pose():
    poses = [(x * 0.1, 0.0, 0.0) for x in range(6)]
    assert drive_goal.plan_reach(poses, 99.0) == 5


def test_the_walk_is_on_ARC_LENGTH_and_not_on_distance_from_the_start():
    # THE CHECK THAT MATTERS ON A REEDS-SHEPP PATH. This plan goes out
    # 1.0 m and comes straight back, so its last pose is 0.0 m from its
    # first and its arc length is 2.0 m. A walk on displacement would
    # never reach a 1.5 m horizon at all; a walk on arc length reaches
    # it half way back.
    there = [(x * 0.1, 0.0, 0.0) for x in range(11)]
    back = [(1.0 - x * 0.1, 0.0, 0.0) for x in range(1, 11)]
    assert drive_goal.plan_reach(there + back, 1.5) == 15
    assert drive_goal.plan_reach(there + back, 2.0) == 20


def test_a_one_pose_plan_reaches_nothing():
    assert drive_goal.plan_reach([(0.0, 0.0, 0.0)], 5.0) == 0


def test_the_gate_scan_counts_the_plans_that_could_have_CLEARED_it():
    poses = [(x * 0.1, 0.0, 0.0) for x in range(60)]
    plans = [(1.0, poses), (2.0, poses), (3.0, poses)]
    truth = [(t * 0.5, 0.0, 0.0, 0.0) for t in range(20)]
    speeds = [0.30] * 20
    window = drive_goal.MppiWindow(horizon_m=0.84, gate=20, steps=56,
                                   model_dt=0.05, vx_max=0.30)
    scan = drive_goal.align_gate_scan(plans, truth, speeds, window,
                                      0.0, 10.0, 0.05)
    assert scan.n == 3
    assert scan.cleared == 0            # index 8 against a gate of 20
    assert scan.index.maximum == 8


def test_a_wider_gate_or_a_longer_horizon_is_what_changes_it():
    poses = [(x * 0.1, 0.0, 0.0) for x in range(60)]
    plans = [(1.0, poses)]
    truth = [(t * 0.5, 0.0, 0.0, 0.0) for t in range(20)]
    speeds = [0.30] * 20
    tight = drive_goal.MppiWindow(0.84, 20, 56, 0.05, 0.30)
    loose = drive_goal.MppiWindow(0.84, 5, 56, 0.05, 0.30)
    longer = drive_goal.MppiWindow(2.01, 20, 134, 0.05, 0.30)
    assert drive_goal.align_gate_scan(
        plans, truth, speeds, tight, 0.0, 10.0, 0.05).cleared == 0
    assert drive_goal.align_gate_scan(
        plans, truth, speeds, loose, 0.0, 10.0, 0.05).cleared == 1
    assert drive_goal.align_gate_scan(
        plans, truth, speeds, longer, 0.0, 10.0, 0.05).cleared == 1


def test_plans_published_AT_A_STANDSTILL_are_dropped_and_counted():
    # A horizon is a speed times a time, so at rest it is zero and the
    # index would be an artefact rather than a measurement.
    poses = [(x * 0.1, 0.0, 0.0) for x in range(60)]
    plans = [(1.0, poses), (5.0, poses)]
    truth = [(1.0, 0.0, 0.0, 0.0), (5.0, 0.0, 0.0, 0.0)]
    speeds = [0.30, 0.001]
    window = drive_goal.MppiWindow(0.84, 20, 56, 0.05, 0.30)
    scan = drive_goal.align_gate_scan(plans, truth, speeds, window,
                                      0.0, 10.0, 0.05)
    assert scan.n == 1 and scan.at_rest == 1


def test_the_scan_is_an_UPPER_BOUND_and_the_docstring_says_so():
    assert "UPPER BOUND" in drive_goal.align_gate_scan.__doc__


def test_an_empty_window_scans_nothing_rather_than_answering_zero():
    window = drive_goal.MppiWindow(0.84, 20, 56, 0.05, 0.30)
    assert drive_goal.align_gate_scan([], [], [], window,
                                      0.0, 10.0, 0.05) is None


# ----------------------------------------------------------------------
# THE HEADING ACCOUNTING - what killed suspects (b) and (c)
# ----------------------------------------------------------------------

def _drive(psi, seconds=40.0, speed=0.30, step=0.05):
    """A vehicle driving EAST at `speed` with a constant heading error."""
    rows, speeds, t, x, y = [], [], 0.0, -12.0, 0.0
    while t < seconds:
        rows.append((t, x, y, ec.normalise_angle(psi + math.pi)))
        speeds.append(-speed)
        x += speed * math.cos(psi) * step
        y += speed * math.sin(psi) * step
        t += step
    return rows, speeds


def test_a_constant_heading_error_accounts_for_ALL_of_the_drift():
    rows, speeds = _drive(-0.08)
    got = drive_goal.heading_account(_Goal(), rows, speeds, 0.0, 1e9, 3.0)
    assert got.ratio == pytest.approx(1.0, abs=0.02)
    assert got.measured < 0.0 and got.predicted < 0.0


def test_a_vehicle_pointing_the_RIGHT_way_drifts_nowhere():
    rows, speeds = _drive(0.0)
    got = drive_goal.heading_account(_Goal(), rows, speeds, 0.0, 1e9, 3.0)
    assert abs(got.measured) < 1e-6
    assert abs(got.predicted) < 1e-6


def test_the_sign_follows_the_heading():
    left, sl = _drive(+0.08)
    right, sr = _drive(-0.08)
    assert drive_goal.heading_account(
        _Goal(), left, sl, 0.0, 1e9, 3.0).measured > 0.0
    assert drive_goal.heading_account(
        _Goal(), right, sr, 0.0, 1e9, 3.0).measured < 0.0


def test_the_window_STOPS_before_the_endgame():
    # THE ONE THAT MATTERS. Past the goal the vehicle hooks round and psi
    # sweeps through a right angle; integrating that would not be an
    # account of the transit, it would be an account of the pirouette.
    rows, speeds = _drive(-0.08, seconds=90.0)
    got = drive_goal.heading_account(_Goal(), rows, speeds, 0.0, 1e9, 3.0)
    # 12 m of approach at 0.30 m/s, stopped 3 m short = 30 s of it
    assert got.n < len(rows)
    assert got.ratio == pytest.approx(1.0, abs=0.02)


def test_a_run_with_no_TRANSIT_in_it_has_no_account():
    # A window that opens already inside the margin is all endgame and
    # no transit, and a ratio of two numbers that are both noise is not
    # a finding.
    rows = [(t * 0.05, -1.0, 0.0, math.pi) for t in range(50)]
    assert drive_goal.heading_account(
        _Goal(), rows, [-0.3] * 50, 0.0, 1e9, 3.0) is None


def test_the_ratio_is_None_rather_than_infinite_when_nothing_drifted():
    rows, speeds = _drive(0.0)
    got = drive_goal.heading_account(_Goal(), rows, speeds, 0.0, 1e9, 3.0)
    assert got.ratio is None


def test_mppi_window_multiplies_the_three_numbers_into_a_DISTANCE(
        tmp_path):
    # THE WHOLE OF 16.2 IN ONE ASSERTION. `time_steps` is a COUNT and
    # the horizon is a DISTANCE, and F4 Task 2 shipped a file where the
    # two had come apart because nothing multiplied them together. This
    # is the one place that does, so it gets a test of its own rather
    # than being covered only through the scan that calls it.
    path = tmp_path / "nav2.yaml"
    path.write_text(
        "controller_server:@  ros__parameters:@    FollowPath:@"
        "      time_steps: 56@      model_dt: 0.05@      vx_max: 0.300@"
        "      PathAlignCritic:@        offset_from_furthest: 20@"
        .replace("@", chr(10)), encoding="utf-8")
    got = drive_goal.mppi_window(str(path))
    assert got.steps == 56
    assert got.model_dt == pytest.approx(0.05)
    assert got.vx_max == pytest.approx(0.300)
    assert got.gate == 20
    assert got.horizon_m == pytest.approx(0.84)


def test_the_horizon_follows_the_SPEED_and_not_only_the_count(tmp_path):
    # The coupling that broke: the same 56 steps at the two transit
    # ceilings this track has used are 1.96 m and 0.84 m of look-ahead,
    # and only one of them clears the vehicle's 1.25 m turning radius.
    def written(vx):
        path = tmp_path / ("n%s.yaml" % vx)
        body = ("controller_server:@  ros__parameters:@    FollowPath:@"
                "      time_steps: 56@      model_dt: 0.05@"
                "      vx_max: %s@      PathAlignCritic:@"
                "        offset_from_furthest: 20@" % vx)
        path.write_text(body.replace("@", chr(10)), encoding="utf-8")
        return drive_goal.mppi_window(str(path)).horizon_m
    assert written("0.700") == pytest.approx(1.96)
    assert written("0.300") == pytest.approx(0.84)
    assert written("0.300") < 1.25 < written("0.700")


def test_mppi_window_reads_the_SHIPPED_file_and_agrees_with_the_label(cfg):
    import os as _os
    got = drive_goal.mppi_window(
        _os.path.join(drive_goal._common.REPO, cfg.s("nav.params_file")))
    label = drive_goal.nav_label(cfg)
    assert int(label["nav_time_steps"]) == got.steps
    assert int(label["nav_align_gate"]) == got.gate
    assert got.horizon_m == pytest.approx(got.steps * got.model_dt
                                          * got.vx_max)


# ======================================================================
# F4 TASK 3 - THE CASE TABLE AND THE CUSP
# ======================================================================

def test_plan_cusps_finds_NOTHING_in_a_path_driven_one_way():
    # A straight run of poses all heading the way they advance has no
    # direction change in it, and a cusp counter that invented one would
    # make every ordinary leg on this track look like a manoeuvre.
    poses = [(float(i), 0.0, 0.0) for i in range(10)]
    assert drive_goal.plan_cusps(poses) == []
    assert drive_goal.plan_directions(poses) == (9, 0)


def test_plan_cusps_finds_the_ONE_reversal_and_says_where_it_is():
    # Out 3 m heading +x, then back 2 m still heading +x: one sign
    # change, at the turning point, 3 m along the path.
    poses = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0),
             (3.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    cusps = drive_goal.plan_cusps(poses)
    assert len(cusps) == 1
    index, x, y, s, run = cusps[0]
    assert index == 3
    assert (x, y) == (3.0, 0.0)
    assert s == pytest.approx(3.0)
    # and the run AFTER it is the 2 m back
    assert run == pytest.approx(2.0)


def test_the_RUN_is_what_separates_a_manoeuvre_from_lattice_noise():
    # THE READING THAT COST A PROBE. SmacPlannerHybrid emits an SE2
    # lattice and a one-pose blip - forward 0.07 m and back again - is a
    # sign change in the arithmetic and nothing at all in the vehicle.
    # The fifth field is what lets a caller tell them apart; this
    # function does not filter, because a threshold is a policy.
    poses = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0),
             (1.93, 0.0, 0.0), (3.0, 0.0, 0.0), (4.0, 0.0, 0.0)]
    cusps = drive_goal.plan_cusps(poses)
    assert len(cusps) == 2
    assert cusps[0][4] == pytest.approx(0.07)      # one pose - noise
    assert cusps[1][4] == pytest.approx(2.07)      # a real run


def test_plan_cusps_ignores_a_REPEATED_pose_rather_than_dividing_by_it():
    poses = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0),
             (2.0, 0.0, 0.0)]
    assert drive_goal.plan_cusps(poses) == []


def test_plan_cusps_and_plan_directions_agree_about_what_a_cusp_IS():
    # Two functions, one definition. `plan_directions` counts the
    # segments each way and `plan_cusps` finds the changes between them,
    # so the number of cusps can never exceed the smaller count.
    poses = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0, 0.0),
             (1.5, 0.0, 0.0), (1.0, 0.0, 0.0)]
    forward, reverse = drive_goal.plan_directions(poses)
    # four segments, alternating, so three changes between them - and a
    # cusp count can never exceed one less than the segment count.
    assert forward + reverse == 4
    assert len(drive_goal.plan_cusps(poses)) == 3
    assert len(drive_goal.plan_cusps(poses)) <= forward + reverse - 1


def test_every_case_in_config_yaml_reads_back(cfg):
    for name in cfg.raw("nav.cases"):
        case = drive_goal.read_case(cfg, name)
        assert case.name == name
        assert case.repeat >= 1
        assert case.first.name in cfg.raw("nav.goals")
        if case.second is None:
            assert case.when is None
            assert case.preempt_at_m is None
        else:
            assert case.when in drive_goal.CASE_WHEN
            if case.when == "preempt":
                assert case.preempt_at_m > 0.0
            else:
                assert case.preempt_at_m is None


def _refusing_cfg(cfg, rows, table="nav.cases"):
    """The real config with ONE table swapped, and a refusal that raises.

    `table` IS AN ARGUMENT SINCE G5 TASK 8, because the row-level checks
    it feeds now live on nav.goals as well as nav.cases and a second
    copy of this fixture for the second table is a second thing to keep
    in step with `refuse`.
    """
    class _Stop(Exception):
        pass

    lines = []

    class _Wrapped(object):
        def __init__(self, inner):
            self._inner = inner

        def raw(self, key):
            if key == table:
                return rows
            return self._inner.raw(key)

        def s(self, key):
            return self._inner.s(key)

        def f(self, key):
            return self._inner.f(key)

        def refuse(self, check, owner, *rest):
            lines.extend([check, owner] + list(rest))
            raise _Stop()

    return _Wrapped(cfg), lines, _Stop


def test_a_case_that_is_not_in_the_table_is_REFUSED_by_name(cfg):
    wrapped, lines, stop = _refusing_cfg(cfg, {"only": {"goal": "x",
                                                        "repeat": "1"}})
    with pytest.raises(stop):
        drive_goal.read_case(wrapped, "nope")
    assert "nav.cases names the case that was asked for" in lines[0]
    assert any("only" in line for line in lines)


def test_a_second_goal_with_NO_RULE_is_refused(cfg):
    # Two different experiments wearing one name: a goal sent mid-drive
    # and a goal sent after the first finished are not the same run.
    wrapped, lines, stop = _refusing_cfg(cfg, {
        "bad": {"goal": "spine_north", "then": "aisle_end", "repeat": "1"}})
    with pytest.raises(stop):
        drive_goal.read_case(wrapped, "bad")
    assert "`when` is one of" in lines[0]


def test_a_PREEMPT_with_no_trigger_is_refused(cfg):
    wrapped, lines, stop = _refusing_cfg(cfg, {
        "bad": {"goal": "spine_north", "then": "aisle_end",
                "when": "preempt", "repeat": "1"}})
    with pytest.raises(stop):
        drive_goal.read_case(wrapped, "bad")
    assert "preempt_at_m" in lines[0]


def test_a_PREEMPT_trigger_of_zero_or_less_is_refused(cfg):
    # It is a REMAINING distance: zero fires only on a goal already
    # reached and a negative one never fires at all.
    for value in ("0.0", "-1.0"):
        wrapped, lines, stop = _refusing_cfg(cfg, {
            "bad": {"goal": "spine_north", "then": "aisle_end",
                    "when": "preempt", "preempt_at_m": value,
                    "repeat": "1"}})
        with pytest.raises(stop):
            drive_goal.read_case(wrapped, "bad")
        assert "positive" in lines[0]


def test_a_case_naming_a_goal_that_does_not_exist_is_refused_by_the_GOAL(cfg):
    # read_case delegates to read_goal, so the refusal names the goal
    # table rather than the case table - which is the file the operator
    # has to go and edit.
    wrapped, lines, stop = _refusing_cfg(cfg, {
        "bad": {"goal": "no_such_pose", "repeat": "1"}})
    with pytest.raises(stop):
        drive_goal.read_case(wrapped, "bad")
    assert "nav.goals names the goal that was asked for" in lines[0]


def test_a_case_session_and_a_goal_session_are_BOTH_found(cfg, tmp_path,
                                                          monkeypatch):
    # F4 Task 3 names a case's session `case-<name>-<stamp>` because
    # neither of its two goals is what was driven. `sessions_in` has to
    # take both prefixes or the whole case set is invisible to `analyse`.
    root = tmp_path / "evidence"
    for name in ("goal-spine_north-20260827-120000",
                 "case-aisle_transit-20260827-130000",
                 "twist-straight-20260827-140000"):
        (root / name).mkdir(parents=True)
        (root / name / "session.txt").write_text("kind=goal\n",
                                                 encoding="utf-8")

    class _Cfg(object):
        def s(self, key):
            assert key == "evidence.dir"
            return "evidence"

    monkeypatch.setattr(drive_goal._common, "REPO", str(tmp_path))
    found = drive_goal.sessions_in(_Cfg())
    assert found == ["case-aisle_transit-20260827-130000",
                     "goal-spine_north-20260827-120000"]


# ======================================================================
# F4 TASK 3 - THE THREE INSTRUMENTS THE CASES NEEDED
# ======================================================================

def test_preempt_response_reads_a_switch_that_cost_NOTHING():
    # 20 Hz either side, the same speed throughout: a controller that
    # never noticed. The gap is one period and the recovery is instant.
    rows = [(t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 80)]
    got = drive_goal.preempt_response(rows, 2.0, 1.0)
    assert got.gap_s == pytest.approx(0.05)
    assert got.min_v_after == pytest.approx(0.300)
    assert got.mean_v_before == pytest.approx(0.300)
    assert got.mean_v_after == pytest.approx(0.300)
    assert got.recover_s == pytest.approx(0.0)
    assert got.n_before == 20 and got.n_after == 20


def test_preempt_response_finds_a_HOLE_in_the_command_stream():
    # The failure this block exists to catch: nav2 aborts the running
    # goal, the tree halts, and nothing publishes for a while - which at
    # the terminals is a vehicle braking in the middle of an aisle for a
    # re-task that changed nothing about where it was going next.
    before = [(t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 40)]
    after = [(2.0 + 0.4 + t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 12)]
    got = drive_goal.preempt_response(before + after, 2.0, 1.0)
    assert got.gap_s == pytest.approx(0.45, abs=1e-9)
    assert got.n_after == 12


def test_preempt_response_reports_a_STOP_and_how_long_it_lasted():
    before = [(t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 40)]
    after = ([(2.0 + t / 20.0, 0.0, 0.0, 0.0) for t in range(0, 10)]
             + [(2.5 + t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 10)])
    got = drive_goal.preempt_response(before + after, 2.0, 1.0)
    assert got.min_v_after == pytest.approx(0.0)
    assert got.recover_s == pytest.approx(0.5, abs=1e-9)


def test_preempt_response_is_None_when_the_window_has_no_two_sides():
    rows = [(t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 20)]
    assert drive_goal.preempt_response(rows, 5.0, 1.0) is None
    assert drive_goal.preempt_response(rows, -5.0, 1.0) is None


def test_the_mean_either_side_is_reported_so_min_v_can_be_READ(cfg):
    # A small `min_v_after` on a leg that was slowing anyway is not a
    # preemption cost, which is why the two means are in the tuple.
    before = [(t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 40)]
    after = [(2.0 + t / 20.0, 0.0, -0.030, 0.0) for t in range(0, 20)]
    got = drive_goal.preempt_response(before + after, 2.0, 1.0)
    assert got.mean_v_before == pytest.approx(0.300)
    assert got.mean_v_after == pytest.approx(0.030)
    assert got.recover_s is None


def test_driven_cusps_finds_the_sign_change_and_ignores_the_deadband():
    rows = ([(t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 10)]
            + [(0.5 + t / 20.0, 0.0, 0.001, 0.0) for t in range(0, 4)]
            + [(0.7 + t / 20.0, 0.0, +0.300, 0.0) for t in range(0, 10)])
    got = drive_goal.driven_cusps(rows, 0.005)
    assert len(got) == 1
    t_c, v_a, v_b = got[0]
    assert t_c == pytest.approx(0.7)
    assert v_a == pytest.approx(-0.300)
    assert v_b == pytest.approx(+0.300)


def test_driven_cusps_counts_NOTHING_in_a_one_direction_run():
    rows = [(t / 20.0, 0.0, -0.300, 0.0) for t in range(0, 40)]
    assert drive_goal.driven_cusps(rows, 0.005) == []


def test_a_crossing_INSIDE_the_deadband_is_not_a_direction(cfg):
    # navcmd.creep_speed_mps: under it the converter answers with a
    # standing zero and a HELD steer axis, so the sign of the command is
    # not a direction the vehicle ever took.
    rows = [(t / 20.0, 0.0, v, 0.0) for t, v in
            enumerate([-0.3, -0.3, -0.002, +0.002, -0.3, -0.3])]
    assert drive_goal.driven_cusps(rows, 0.005) == []


def test_heading_swing_is_zero_on_a_run_that_held_its_route():
    # travel heading = pose yaw + pi, so a pose yaw of pi is a travel
    # heading of 0 - which is what the goal below asks for.
    truth = [(float(i), 0.0, 0.0, math.pi) for i in range(20)]
    speeds = [0.300] * 20
    got = drive_goal.heading_swing(0.0, truth, speeds, 0.0, 19.0, 0.05)
    assert got.n == 20
    assert got.sd == pytest.approx(0.0, abs=1e-12)
    assert got.worst == pytest.approx(0.0, abs=1e-12)


def test_heading_swing_drops_the_samples_the_vehicle_was_NOT_driving():
    # A heading held at a standstill is not a heading the vehicle is
    # driving, and a run that stops for thirty seconds would otherwise
    # report whatever it was pointing at, thirty seconds' worth.
    truth = ([(float(i), 0.0, 0.0, math.pi) for i in range(10)]
             + [(float(10 + i), 0.0, 0.0, math.pi + 1.0) for i in range(10)])
    speeds = [0.300] * 10 + [0.0] * 10
    got = drive_goal.heading_swing(0.0, truth, speeds, 0.0, 19.0, 0.05)
    assert got.n == 10
    assert got.worst == pytest.approx(0.0, abs=1e-12)


def test_heading_swing_windows_on_the_TIMES_it_is_given():
    truth = [(float(i), 0.0, 0.0, math.pi + (0.4 if i >= 10 else 0.0))
             for i in range(20)]
    speeds = [0.300] * 20
    early = drive_goal.heading_swing(0.0, truth, speeds, 0.0, 9.0, 0.05)
    late = drive_goal.heading_swing(0.0, truth, speeds, 10.0, 19.0, 0.05)
    assert early.worst == pytest.approx(0.0, abs=1e-12)
    assert late.worst == pytest.approx(0.4)
    assert late.sd == pytest.approx(0.0, abs=1e-12)


def test_heading_swing_wraps_at_pi_rather_than_reporting_2pi_of_swing():
    # The one arithmetic that could make a straight run look unstable: a
    # travel heading either side of +-pi is a hair of swing, not a whole
    # turn.
    truth = [(0.0, 0.0, 0.0, 0.0 + 0.01), (1.0, 0.0, 0.0, 0.0 - 0.01)]
    speeds = [0.300, 0.300]
    got = drive_goal.heading_swing(math.pi, truth, speeds, 0.0, 1.0, 0.05)
    assert got.worst < 0.02


def test_heading_swing_is_None_when_nothing_was_driven():
    truth = [(float(i), 0.0, 0.0, math.pi) for i in range(5)]
    assert drive_goal.heading_swing(0.0, truth, [0.0] * 5, 0.0, 4.0,
                                    0.05) is None


# ======================================================================
# F4 TASK 3 FIX ROUND 1 - THE DIRECTION SPLIT (#5714's own instrument)
# ======================================================================

def test_deviation_by_direction_splits_a_run_that_went_both_ways():
    # THE #5714 A/B AS ARITHMETIC. Each truth sample is attributed to the
    # direction the CONTROLLER was commanding at the time, and scored
    # against the plan standing at the time - so one run that reverses
    # gives two populations off one instrument, and neither of them is a
    # hand-cut window.
    plans = [(0.0, [(i / 10.0, 0.0, 0.0) for i in range(101)])]
    truth = [(float(i), float(i), 0.10 if i < 5 else 0.30, 0.0)
             for i in range(10)]
    cmd = [(float(i), 0.0, -0.30 if i < 5 else +0.30, 0.0)
           for i in range(10)]
    fwd, rev = drive_goal.deviation_by_direction(
        truth, cmd, plans, 0.0, 9.0, 0.005)
    # nav2 FORWARD is positive linear.x; nav2 REVERSE is negative
    assert rev.n == 5 and fwd.n == 5
    assert rev.mean == pytest.approx(0.10)
    assert fwd.mean == pytest.approx(0.30)
    assert rev.worst == pytest.approx(0.10)
    assert fwd.worst == pytest.approx(0.30)


def test_deviation_by_direction_gives_None_for_a_direction_never_driven():
    # Every ordinary leg on this track is a nav2 REVERSE leg, so the
    # FORWARD half is empty on almost every session and must read as
    # absent rather than as zero.
    plans = [(0.0, [(i / 10.0, 0.0, 0.0) for i in range(101)])]
    truth = [(float(i), float(i), 0.05, 0.0) for i in range(6)]
    cmd = [(float(i), 0.0, -0.30, 0.0) for i in range(6)]
    fwd, rev = drive_goal.deviation_by_direction(
        truth, cmd, plans, 0.0, 5.0, 0.005)
    assert fwd is None
    assert rev.n == 6


def test_deviation_by_direction_ignores_the_creep_deadband():
    # Below navcmd.creep_speed_mps the sign of a command is not a
    # direction (the converter answers with a standing zero and a HELD
    # steer axis), so those samples belong to neither population.
    plans = [(0.0, [(i / 10.0, 0.0, 0.0) for i in range(101)])]
    truth = [(float(i), float(i), 0.05, 0.0) for i in range(6)]
    cmd = [(0.0, 0.0, -0.30, 0.0), (1.0, 0.0, -0.30, 0.0),
           (2.0, 0.0, 0.001, 0.0), (3.0, 0.0, -0.001, 0.0),
           (4.0, 0.0, -0.30, 0.0), (5.0, 0.0, -0.30, 0.0)]
    fwd, rev = drive_goal.deviation_by_direction(
        truth, cmd, plans, 0.0, 5.0, 0.005)
    assert fwd is None
    assert rev.n == 4


def test_deviation_by_direction_uses_the_plan_STANDING_at_each_sample():
    # The same rule every other deviation figure on this track obeys: the
    # tree replans at 1 Hz and a sample is scored against the path that
    # existed when it was taken, never against the first or the last.
    plans = [(0.0, [(i / 10.0, 0.0, 0.0) for i in range(101)]),
             (3.0, [(i / 10.0, 1.0, 0.0) for i in range(101)])]
    truth = [(float(i), float(i), 0.0, 0.0) for i in range(6)]
    cmd = [(float(i), 0.0, -0.30, 0.0) for i in range(6)]
    _fwd, rev = drive_goal.deviation_by_direction(
        truth, cmd, plans, 0.0, 5.0, 0.005)
    # samples 0-2 are 0.0 from the first plan, 3-5 are 1.0 from the second
    assert rev.n == 6
    assert rev.mean == pytest.approx(0.5)
    assert rev.worst == pytest.approx(1.0)


def test_deviation_by_direction_windows_on_the_times_it_is_given():
    plans = [(0.0, [(i / 10.0, 0.0, 0.0) for i in range(101)])]
    truth = [(float(i), float(i), 0.10, 0.0) for i in range(10)]
    cmd = [(float(i), 0.0, -0.30, 0.0) for i in range(10)]
    _f, rev = drive_goal.deviation_by_direction(
        truth, cmd, plans, 2.0, 4.0, 0.005)
    assert rev.n == 3


def test_deviation_by_direction_is_empty_both_ways_with_no_plan():
    fwd, rev = drive_goal.deviation_by_direction(
        [(0.0, 0.0, 0.0, 0.0)], [(0.0, 0.0, -0.3, 0.0)], [], 0.0, 1.0,
        0.005)
    assert fwd is None and rev is None


# ----------------------------------------------------------------------
# WHICH CONTROLLER A CASE RUNS, G5 TASK 7
#
# `read_case` resolves the controller and the tree that selects it at
# the same moment it resolves the goals, and for the same reason: a case
# naming a controller that does not exist has to be a refusal before the
# stack is touched rather than a bt_navigator that cannot open a tree
# forty metres into a drive.
# ----------------------------------------------------------------------

def test_the_STAGE_case_resolves_to_RPP_and_to_the_RPP_TREE(cfg):
    case = drive_goal.read_case(cfg, "stage_s5")
    assert case.controller == "rpp"
    assert case.bt_xml == cfg.s("nav.bt_xml_rpp")
    assert case.bt_xml != cfg.s("nav.bt_xml")


def test_a_case_with_NO_controller_key_is_MPPI_and_the_PRIMARY_tree(cfg):
    # Every case was this before the key existed, and a case that says
    # nothing must still say MPPI rather than nothing.
    for name in ("aisle_transit", "station_approach", "reverse_out",
                 "ring_stress"):
        case = drive_goal.read_case(cfg, name)
        assert case.controller == drive_goal.DEFAULT_CONTROLLER
        assert case.bt_xml == cfg.s("nav.bt_xml")


def test_an_UNKNOWN_controller_is_REFUSED_and_the_refusal_NAMES_BOTH(cfg):
    wrapped, lines, stop = _refusing_cfg(cfg, {
        "bad": {"goal": "spine_north", "repeat": "1",
                "controller": "dwb"}})
    with pytest.raises(stop):
        drive_goal.read_case(wrapped, "bad")
    assert "`controller` is one of" in lines[0]
    joined = " ".join(lines)
    assert "FollowPath" in joined and "FollowPathRPP" in joined


def test_the_two_controller_names_map_to_the_two_config_KEYS(cfg):
    # The table is the only place the name -> file mapping lives, and
    # both files it names have to be addresses config.yaml actually
    # holds.
    assert list(drive_goal.CONTROLLER_TREE) == ["mppi", "rpp"]
    assert drive_goal.DEFAULT_CONTROLLER in drive_goal.CONTROLLER_TREE
    for key in drive_goal.CONTROLLER_TREE.values():
        assert os.path.isfile(os.path.join(drive_goal._common.REPO,
                                           cfg.s(key)))


def test_EVERY_case_in_the_table_resolves_without_a_refusal(cfg):
    # read_case is where a typo in this table is caught, so the table
    # itself has to be walked rather than sampled.
    import yaml as _yaml
    with open(drive_goal._common.CONFIG, encoding="utf-8") as handle:
        table = _yaml.safe_load(handle)["nav"]["cases"]
    for name in table:
        case = drive_goal.read_case(cfg, name)
        assert case.controller in drive_goal.CONTROLLER_TREE
        assert case.bt_xml


def test_nav_label_records_the_TREE_IT_WAS_GIVEN_and_ITS_hash(cfg):
    # A run behind the approach tree that wore the primary tree's label
    # would be tabled by `analyse` with runs it has nothing to do with.
    # That hazard is exactly why nav_bt_md5 was put on the session in
    # the first place; a second tree is what makes it live.
    primary = drive_goal.nav_label(cfg)
    variant = drive_goal.nav_label(cfg, cfg.s("nav.bt_xml_rpp"))
    assert primary["nav_bt"] == cfg.s("nav.bt_xml")
    assert variant["nav_bt"] == cfg.s("nav.bt_xml_rpp")
    assert primary["nav_bt_md5"] != variant["nav_bt_md5"]
    # and the nav2.yaml half of the label is the SAME for both, because
    # one parameter file declares both controllers.
    assert primary["nav_config_md5"] == variant["nav_config_md5"]


def test_BOTH_trees_carry_the_SAME_navigation_budget(cfg):
    # The budget is the tree's guard and `analyse` reads it off the
    # session. The two trees differ in one attribute and it is not this
    # one, so a stage run and a transit run are bounded alike.
    assert (drive_goal.nav_label(cfg)["nav_budget_ms"]
            == drive_goal.nav_label(cfg,
                                    cfg.s("nav.bt_xml_rpp"))["nav_budget_ms"])


# ----------------------------------------------------------------------
# WHICH CONTROLLER A GOAL RUNS, G5 TASK 8
#
# The pallet cycle's transit leg is a BARE `--goal spine_north` - it has
# no case to carry the choice - and it was the last leg in a cycle that
# needed a recovery. So nav.goals took the same optional `controller:`
# key nav.cases has, resolved by the same function, off the same table
# of two names. These pin the mechanism AND the one rule that keeps it
# from moving anything else: a case never inherits from its goals.
# ----------------------------------------------------------------------

def _cycle_transit_goal(origin):
    """The goal name the pallet cycle's transit leg sends from `origin`.

    THE GOAL IS NOT TYPED IN HERE. tools/pallet_cycle.plan_cycle() is
    the list of legs the acceptance run actually drives, and this reads
    the goal name out of it - so a cycle re-plumbed to a different goal
    cannot leave these tests passing about a leg nothing runs any more.
    """
    import pallet_cycle
    legs = [step for step in pallet_cycle.plan_cycle(origin)
            if step["tool"] == "drive_goal.py" and "--goal" in step["argv"]]
    assert len(legs) == 1, legs
    return legs[0]["argv"][legs[0]["argv"].index("--goal") + 1]


def test_the_BAY_EXIT_transit_the_pallet_cycle_drives_resolves_to_RPP(cfg):
    # G5 TASK 9, and it is the leg the whole key exists for: out of the
    # S5 bay through a Reeds-Shepp cusp, `no_progress` 2 of 2 on MPPI
    # and arrived 6 of 6 on RPP.
    goal = drive_goal.read_goal(cfg, _cycle_transit_goal("bay"))
    assert goal.controller == "rpp"
    assert goal.bt_xml == cfg.s("nav.bt_xml_rpp")
    assert goal.bt_xml != cfg.s("nav.bt_xml")


def test_the_SPAWN_transit_the_pallet_cycle_drives_resolves_to_MPPI(cfg):
    # THE OTHER HALF OF THE SPLIT. 17 m of open corridor, 8 of 8 on
    # MPPI against 7 of 8 on RPP, so it stays where it was measured -
    # and it is pinned, because "absent means mppi" is exactly the kind
    # of fact that drifts back without one.
    goal = drive_goal.read_goal(cfg, _cycle_transit_goal("spawn"))
    assert goal.controller == "mppi"
    assert goal.bt_xml == cfg.s("nav.bt_xml")


def test_the_TWO_transit_goals_are_ONE_POSE_under_TWO_NAMES(cfg):
    # ONE TARGET, TWO ROWS. What differs is the origin and therefore
    # the controller; the destination must not differ at all, or the
    # cycle's second transit is driving somewhere nobody wrote down.
    spawn = drive_goal.read_goal(cfg, _cycle_transit_goal("spawn"))
    bay = drive_goal.read_goal(cfg, _cycle_transit_goal("bay"))
    assert bay.name != spawn.name
    assert bay.x == pytest.approx(spawn.x)
    assert bay.y == pytest.approx(spawn.y)
    assert bay.travel_yaw == pytest.approx(spawn.travel_yaw)
    assert bay.pose_yaw == pytest.approx(spawn.pose_yaw)
    assert bay.controller != spawn.controller


def test_a_goal_with_NO_controller_key_is_MPPI_and_the_PRIMARY_tree(cfg):
    # Every goal was this before the key existed, and a goal that says
    # nothing must still say MPPI rather than nothing. `spine_north` is
    # back in this list since G5 Task 9: Task 8's key moved off it onto
    # the bay-exit row that needed it.
    for name in ("spine_north", "ring_corner", "aisle_end", "station_s5",
                 "station_s5_staging", "ring_s5_junction", "rack_sw3"):
        goal = drive_goal.read_goal(cfg, name)
        assert goal.controller == drive_goal.DEFAULT_CONTROLLER, name
        assert goal.bt_xml == cfg.s("nav.bt_xml"), name


def test_EVERY_goal_in_the_table_resolves_without_a_refusal(cfg):
    import yaml as _yaml
    with open(drive_goal._common.CONFIG, encoding="utf-8") as handle:
        table = _yaml.safe_load(handle)["nav"]["goals"]
    for name in table:
        goal = drive_goal.read_goal(cfg, name)
        assert goal.controller in drive_goal.CONTROLLER_TREE, name
        assert goal.bt_xml, name


def test_an_UNKNOWN_controller_on_a_GOAL_is_REFUSED_naming_nav_goals(cfg):
    wrapped, lines, stop = _refusing_cfg(cfg, {
        "bad": {"x": "0.0", "y": "0.0", "travel_yaw_rad": "0.0",
                "repeat": "1", "controller": "dwb"}}, table="nav.goals")
    with pytest.raises(stop):
        drive_goal.read_goal(wrapped, "bad")
    assert "nav.goals.bad's `controller` is one of" in lines[0]
    # and the OWNER line points at the table the reader has to edit,
    # which is the whole reason `where` is an argument.
    assert "nav.goals" in lines[1]
    joined = " ".join(lines)
    assert "FollowPath" in joined and "FollowPathRPP" in joined


def test_a_CASE_does_NOT_inherit_the_controller_of_the_goal_it_names(cfg):
    # THE RULE, WITH A LIVE WITNESS. `stage_s5` is `rpp` and the goal it
    # names carries no key at all, so the two DISAGREE and the CASE
    # wins: a case is one run and one tree, and the case is the errand.
    case = drive_goal.read_case(cfg, "stage_s5")
    assert case.controller == "rpp"
    assert case.first.controller == "mppi"
    assert case.bt_xml == cfg.s("nav.bt_xml_rpp")
    assert case.first.bt_xml == cfg.s("nav.bt_xml")


def test_a_CASE_still_reads_MPPI_over_goals_that_agree_with_it(cfg):
    # AND THE OTHER DIRECTION. `aisle_transit` is a SHIPPED EVIDENCE
    # case measured behind MPPI over two goals that are both MPPI, so
    # nothing about it may move when the goal table is re-split.
    case = drive_goal.read_case(cfg, "aisle_transit")
    assert case.first.name == "spine_north"
    assert case.first.controller == "mppi"
    assert case.controller == "mppi"
    assert case.bt_xml == cfg.s("nav.bt_xml")


def test_the_CASE_that_DOES_name_rpp_still_gets_it_over_a_MPPI_goal(cfg):
    # The other direction of the same rule: `stage_s5` names `rpp` and
    # its goal names nothing, and the CASE wins there too.
    case = drive_goal.read_case(cfg, "stage_s5")
    assert case.first.controller == "mppi"
    assert case.controller == "rpp"
    assert case.bt_xml == cfg.s("nav.bt_xml_rpp")


def test_ONE_resolver_answers_for_BOTH_tables(cfg):
    # A goal row and a case row carrying the same key must resolve the
    # same way, or the two tables mean two different things by one word.
    for controller, key in drive_goal.CONTROLLER_TREE.items():
        row = {"controller": controller}
        assert drive_goal.read_controller(cfg, "nav.goals.x", row) == \
            drive_goal.read_controller(cfg, "nav.cases.x", row)
        assert drive_goal.read_controller(cfg, "nav.goals.x", row) == \
            (controller, cfg.s(key))
    assert drive_goal.read_controller(cfg, "nav.goals.x", {}) == \
        (drive_goal.DEFAULT_CONTROLLER,
         cfg.s(drive_goal.CONTROLLER_TREE[drive_goal.DEFAULT_CONTROLLER]))


def test_describe_of_a_BARE_goal_PRINTS_the_controller_and_the_tree(
        cfg, capsys):
    drive_goal.describe(
        cfg, drive_goal.read_goal(cfg, "spine_north_from_bay"))
    out = capsys.readouterr().out
    assert "controller rpp" in out
    assert cfg.s("nav.bt_xml_rpp") in out


def test_describe_of_the_OTHER_transit_row_prints_the_OTHER_answer(
        cfg, capsys):
    # THE TWO ROWS ARE ONE POSE AND THE PRINT IS THE ONLY PLACE AN
    # OPERATOR SEES WHICH ONE THEY ASKED FOR. If `describe` read the
    # same answer for both, the split would be invisible on the rig.
    drive_goal.describe(cfg, drive_goal.read_goal(cfg, "spine_north"))
    out = capsys.readouterr().out
    assert "controller mppi" in out
    assert cfg.s("nav.bt_xml_rpp") not in out


def test_describe_of_a_CASE_gives_ONE_controller_answer_not_three(
        cfg, capsys):
    # describe_case prints the case's controller and then describes both
    # goals. If the goals printed theirs too, `aisle_transit` would
    # report mppi AND rpp for one run.
    drive_goal.describe_case(cfg, drive_goal.read_case(cfg, "aisle_transit"))
    out = capsys.readouterr().out
    assert out.count("controller ") == 1
    assert "controller mppi" in out
    assert cfg.s("nav.bt_xml_rpp") not in out


def test_the_two_controller_GLOSSES_name_the_two_nav2_plugins(cfg):
    # One string for both printers, and each half names the nav2.yaml
    # ENTRY - so a reader of either output can find it in that file.
    # It must NOT sort the two by class of leg: G5 Task 8 put a transit
    # leg on RPP, so "the approach legs" would be a lie on the rig.
    assert "FollowPathRPP" in drive_goal.controller_note("rpp")
    assert "FollowPath " in drive_goal.controller_note("mppi")
    assert "RPP" not in drive_goal.controller_note("mppi")
    for name in drive_goal.CONTROLLER_TREE:
        gloss = drive_goal.controller_note(name)
        assert "transit leg" not in gloss and "approach leg" not in gloss
