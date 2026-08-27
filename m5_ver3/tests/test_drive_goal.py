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
                        repeat=1, note="")


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
    for name in ("aisle_end", "ring_corner", "spine_cross"):
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
