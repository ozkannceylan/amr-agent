"""nav2_path.py - the granted polyline as a Path the truck can drive.

WHY THIS FILE EXISTS AT ALL (SPEC_ADAPTER.md AMENDMENTS 9). Four waves
measured one family from one source: SmacPlannerHybrid re-deciding
degenerate ring geometry on every replan. The traffic ledger GRANTS a
polyline; asking a freespace planner to rediscover it was always a
translation error. So the adapter builds the ring chain's Path itself
and hands it to /fN/follow_path, and this file is what says the Path is
drivable BEFORE a truck is asked to drive it.

THE FIXTURES ARE REAL ROUTES, exactly as test_nav2_adapter_legs.py's
are: every polyline comes out of m6/ipc/route.py over m6/ipc/stations.py.
"""
import math

import pytest

import follower
import route
from stations import STATIONS

import nav2_legs
import nav2_path


F1_SPAWN = (-17.0, 10.0)
R = nav2_legs.MIN_TURN_RADIUS_M


def _plan(pose, station_id):
    poly = route.plan_route(pose, station_id)
    assert poly is not None, "route.py could not plan the fixture"
    return poly


def _chain(poly):
    """The one ring chain of a planned route."""
    legs = nav2_legs.plan_legs(poly)
    chains = [leg for leg in legs if leg.klass == nav2_legs.RING_CHAIN]
    assert len(chains) == 1, [leg.klass for leg in legs]
    return chains[0]


def _seg_dirs(poses):
    out = []
    for index in range(len(poses) - 1):
        first, second = poses[index], poses[index + 1]
        out.append(math.atan2(second[1] - first[1], second[0] - first[0]))
    return out


# ----------------------------------------------------------------------
# the straight: densify, endpoints, headings
# ----------------------------------------------------------------------

def test_a_straight_run_is_densified_and_keeps_both_ends():
    built = nav2_path.build_chain_path(
        [(0.0, 0.0), (10.0, 0.0)], radius_m=R, spacing_m=0.10, flipped=False)
    assert built.poses[0][:2] == pytest.approx((0.0, 0.0))
    assert built.poses[-1][:2] == pytest.approx((10.0, 0.0))
    assert built.length_m == pytest.approx(10.0)
    assert built.corners == 0
    gaps = [math.dist(built.poses[i][:2], built.poses[i + 1][:2])
            for i in range(len(built.poses) - 1)]
    assert max(gaps) <= 0.10 + 1e-9
    assert len(built.poses) == 101
    assert all(pose[2] == pytest.approx(0.0) for pose in built.poses)


def test_the_flip_turns_every_orientation_and_moves_no_point():
    along = nav2_path.build_chain_path(
        [(0.0, 0.0), (10.0, 0.0)], radius_m=R, spacing_m=0.10, flipped=False)
    flipped = nav2_path.build_chain_path(
        [(0.0, 0.0), (10.0, 0.0)], radius_m=R, spacing_m=0.10, flipped=True)
    assert [p[:2] for p in flipped.poses] == [p[:2] for p in along.poses]
    assert all(abs(follower.norm_ang(p[2] - math.pi)) < 1e-9
               for p in flipped.poses)
    assert flipped.flipped is True and along.flipped is False


# ----------------------------------------------------------------------
# the corner: a square vertex becomes a tangent arc
# ----------------------------------------------------------------------

def test_a_square_corner_becomes_a_tangent_arc_and_the_vertex_goes():
    # East then north, the corner at (10, 0). At a quarter turn the
    # tangent is r * tan(45 deg) = r exactly, so the arc runs from
    # (10 - r, 0) to (10, r) and the VERTEX ITSELF is not on the path.
    built = nav2_path.build_chain_path(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        radius_m=R, spacing_m=0.10, flipped=False)
    assert built.corners == 1
    assert min(math.dist(pose[:2], (10.0, 0.0))
               for pose in built.poses) == pytest.approx(
                   R * (math.sqrt(2.0) - 1.0), abs=0.02)
    assert built.poses[0][:2] == pytest.approx((0.0, 0.0))
    assert built.poses[-1][:2] == pytest.approx((10.0, 10.0))
    # length = (10 - r) + quarter arc + (10 - r)
    assert built.length_m == pytest.approx(
        20.0 - 2.0 * R + math.pi / 2.0 * R)


def test_the_corner_sagitta_is_the_whole_corridor_price_of_a_turn():
    granted = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    built = nav2_path.build_chain_path(
        granted, radius_m=R, spacing_m=0.05, flipped=False)
    worst = max(nav2_path.offset_from_polyline(pose[:2], granted)
                for pose in built.poses)
    assert worst == pytest.approx(R * (1.0 - math.cos(math.pi / 4.0)),
                                  abs=0.01)
    assert worst < 0.50


def test_no_pose_on_a_built_path_turns_tighter_than_the_radius():
    built = nav2_path.build_chain_path(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        radius_m=R, spacing_m=0.10, flipped=False)
    dirs = _seg_dirs(built.poses)
    for index in range(len(dirs) - 1):
        turn = abs(follower.norm_ang(dirs[index + 1] - dirs[index]))
        if turn <= 1e-9:
            continue                       # a straight has no radius
        # A CHORD OF A CIRCLE IS 2 r sin(theta / 2), so the radius the
        # truck is actually asked for reads straight back off the two
        # samples - and it may never be smaller than its own minimum.
        chord = math.dist(built.poses[index + 1][:2],
                          built.poses[index + 2][:2])
        assert chord / (2.0 * math.sin(turn / 2.0)) >= R - 1e-6


def test_the_heading_of_every_pose_is_the_path_s_own_tangent():
    built = nav2_path.build_chain_path(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        radius_m=R, spacing_m=0.10, flipped=False)
    for index, direction in enumerate(_seg_dirs(built.poses)):
        assert abs(follower.norm_ang(
            built.poses[index][2] - direction)) < 0.05


# ----------------------------------------------------------------------
# THE ONE PROPERTY RPP READS - and it is not the orientations.
# ----------------------------------------------------------------------

def test_the_built_path_is_cusp_free_by_rpp_s_own_test():
    # nav2_regulated_pure_pursuit_controller 1.3.12,
    # regulated_pure_pursuit_controller.cpp:519 findVelocitySignChange:
    # the dot product of successive segments, negative == a cusp. A cusp
    # truncates the lookahead to the cusp distance, which is where a
    # 40 m path would be driven at a 0.0 m carrot.
    for poly in ([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
                 _chain(_plan((-13.0, 4.25), "S4")).points):
        built = nav2_path.build_chain_path(
            poly, radius_m=R, spacing_m=0.10, flipped=False)
        assert nav2_path.cusp_at(built.poses) is None


def test_a_duplicate_pose_with_a_turned_orientation_is_a_cusp_too():
    # RPP's SECOND branch: two poses at the same POSITION with different
    # orientations is an in-place rotation, and it stops the lookahead
    # just as a reversal does. The builder never emits one; cusp_at is
    # what would notice.
    poses = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0),
             (2.0, 0.0, 0.0)]
    assert nav2_path.cusp_at(poses) == 1


# ----------------------------------------------------------------------
# the refusals - all by name
# ----------------------------------------------------------------------

def test_a_reversal_in_the_polyline_is_refused_by_name():
    with pytest.raises(nav2_path.Nav2PathError) as excinfo:
        nav2_path.build_chain_path(
            [(0.0, 0.0), (10.0, 0.0), (0.0, 0.0)],
            radius_m=R, spacing_m=0.10, flipped=False)
    assert "reversal" in str(excinfo.value)


def test_a_corner_with_no_room_for_its_tangent_is_refused_by_name():
    # Two square corners 1.00 m apart: each claims r = 1.25 m of tangent
    # off a segment that is 1.00 m long.
    with pytest.raises(nav2_path.Nav2PathError) as excinfo:
        nav2_path.build_chain_path(
            [(0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (0.0, 1.0)],
            radius_m=R, spacing_m=0.10, flipped=False)
    message = str(excinfo.value)
    assert "tangent" in message and "1.000 m" in message


def test_a_polyline_of_one_point_is_refused_by_name():
    with pytest.raises(nav2_path.Nav2PathError):
        nav2_path.build_chain_path([(0.0, 0.0)], radius_m=R,
                                   spacing_m=0.10, flipped=False)


def test_a_non_finite_coordinate_is_refused_by_name():
    with pytest.raises(nav2_path.Nav2PathError):
        nav2_path.build_chain_path([(0.0, 0.0), (float("nan"), 1.0)],
                                   radius_m=R, spacing_m=0.10,
                                   flipped=False)


def test_a_radius_or_spacing_that_is_not_positive_is_refused_by_name():
    for override in ({"radius_m": 0.0}, {"radius_m": -1.0},
                     {"spacing_m": 0.0}, {"spacing_m": -0.1}):
        call = {"radius_m": R, "spacing_m": 0.10, "flipped": False}
        call.update(override)
        with pytest.raises(nav2_path.Nav2PathError):
            nav2_path.build_chain_path([(0.0, 0.0), (5.0, 0.0)], **call)


# ----------------------------------------------------------------------
# THE FLOOR ITSELF - the assertion AMENDMENTS 9 asks for by name
# ----------------------------------------------------------------------

def test_every_route_on_this_floor_builds_a_path_without_a_refusal():
    """Not a sample: every station pair route.py can plan.

    AMENDMENTS 9 says a corner too tight to round "should not exist on
    this floor" and asks for it to be ASSERTED against route.py's own
    geometry rather than assumed. This is that assertion, and it is the
    one test that would notice a bay being re-cut.
    """
    built_any = 0
    for start in STATIONS:
        origin = (STATIONS[start]["x"], STATIONS[start]["y"])
        for goal in STATIONS:
            if goal == start:
                continue
            poly = route.plan_route(origin, goal)
            assert poly is not None
            for leg in nav2_legs.plan_legs(poly):
                if leg.klass != nav2_legs.RING_CHAIN:
                    continue
                built = nav2_legs.chain_path(leg, current_yaw=0.0)
                assert nav2_path.cusp_at(built.poses) is None
                assert built.length_m > 0.0
                built_any += 1
    assert built_any >= 100, built_any


def test_the_worst_corridor_price_on_this_floor_is_one_sagitta():
    """Every corner on this floor is square, so the price is one number."""
    worst = 0.0
    for goal in STATIONS:
        poly = route.plan_route(F1_SPAWN, goal)
        for leg in nav2_legs.plan_legs(poly):
            if leg.klass != nav2_legs.RING_CHAIN:
                continue
            built = nav2_legs.chain_path(leg, current_yaw=0.0)
            worst = max(worst, max(
                nav2_path.offset_from_polyline(pose[:2], leg.points)
                for pose in built.poses))
    assert worst == pytest.approx(R * (1.0 - math.cos(math.pi / 4.0)),
                                  abs=0.02)
    assert worst < 0.50


# ----------------------------------------------------------------------
# the sense, resolved ONCE per chain
# ----------------------------------------------------------------------

def test_the_sense_is_the_d7_rule_read_off_the_chain_s_first_segment():
    """One decision for a whole chain, and it is D7's own comparison.

    leg_yaw asks it of a leg's LAST segment because that is where its
    goal sits. A chain has no goal on the way; what it has is a truck at
    its HEAD, so the same rule is asked of the first segment - the one
    the truck is about to drive.
    """
    leg = _chain(_plan((-13.0, 4.25), "S4"))
    first = math.atan2(leg.points[1][1] - leg.points[0][1],
                       leg.points[1][0] - leg.points[0][0])
    assert nav2_legs.chain_sense(leg, first) is False
    assert nav2_legs.chain_sense(
        leg, follower.norm_ang(first + math.pi)) is True
    # AND THE TIE GOES TO THE FLIP, which is FLIP_ABOVE_RAD's own rule
    # (D8): a truck standing at a spur mouth is at a quarter turn to the
    # ring BY CONSTRUCTION.
    assert nav2_legs.chain_sense(
        leg, follower.norm_ang(first - math.pi / 2.0)) is True


def test_a_chain_sense_decided_off_no_yaw_at_all_is_refused_by_name():
    leg = _chain(_plan((-13.0, 4.25), "S4"))
    with pytest.raises(nav2_legs.Nav2LegsError):
        nav2_legs.chain_sense(leg, None)
    with pytest.raises(nav2_legs.Nav2LegsError):
        nav2_legs.chain_sense(leg, float("nan"))


def test_the_sense_is_one_answer_for_the_whole_chain_and_not_per_corner():
    leg = _chain(_plan((-13.0, 4.25), "S4"))
    built = nav2_legs.chain_path(leg, current_yaw=math.pi)
    sides = set()
    for index, direction in enumerate(_seg_dirs(built.poses)):
        delta = abs(follower.norm_ang(built.poses[index][2] - direction))
        sides.add(delta > math.pi / 2.0)
    assert len(sides) == 1, sides


# ----------------------------------------------------------------------
# THE PATH STARTS WHERE THE TRUCK IS, AND RPP's OWN SOURCE IS WHY
#
# A fresh FollowPath goal is not searched end to end for the pose
# nearest the robot. path_handler.cpp bounds that search to the first
# `max_robot_pose_search_dist` of the plan:
#
#   auto closest_pose_upper_bound =
#     nav2_util::geometry_utils::first_after_integrated_distance(
#     global_plan_.poses.begin(), global_plan_.poses.end(),
#     max_robot_pose_search_dist);
#   auto transformation_begin = nav2_util::geometry_utils::min_by(
#     global_plan_.poses.begin(), closest_pose_upper_bound, ...);
#
# and then discards everything further than half the local costmap from
# the robot:
#
#   const double max_costmap_extent = getCostmapMaxExtent();
#   auto transformation_end = std::find_if(transformation_begin, end,
#     [&](const auto & p) {
#       return euclidean_distance(p, robot_pose) > max_costmap_extent; });
#   ...
#   if (transformed_plan.poses.empty()) {
#     throw nav2_core::InvalidPath("Resulting plan has 0 poses in it."); }
#
# m6_ver2/vehicles/fN/nav2.yaml sets max_robot_pose_search_dist 2.00 and
# a 10 x 10 m local costmap (extent 5.00 m). So a forty-metre chain
# RE-SENT to a truck thirty metres along it would be searched only over
# its first two metres, every one of those poses is more than five
# metres away, the transformed plan comes back EMPTY and the controller
# aborts on INVALID_PATH (103).
#   THAT IS NOT HYPOTHETICAL: `_safety` re-sends the running leg on
# every SAFETY-STOP resume, and run 16 had two of them mid-order. So a
# chain is built from WHERE THE TRUCK STANDS ON IT.
# ----------------------------------------------------------------------

MAX_ROBOT_POSE_SEARCH_M = 2.00          # nav2.yaml, FollowPathRPP


def test_a_chain_is_built_from_where_the_truck_stands_on_it():
    granted = [(0.0, 0.0), (40.0, 0.0)]
    trimmed = nav2_path.trim_to(granted, (30.0, 0.2))
    assert trimmed[0] == pytest.approx((30.0, 0.0))
    assert trimmed[-1] == pytest.approx((40.0, 0.0))
    built = nav2_path.build_chain_path(trimmed, radius_m=R, spacing_m=0.10)
    assert built.length_m == pytest.approx(10.0)


def test_a_truck_at_the_head_of_its_chain_trims_nothing_away():
    granted = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    trimmed = nav2_path.trim_to(granted, (0.0, 0.0))
    assert trimmed == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]


def test_a_truck_too_far_off_the_corridor_trims_nothing():
    """Not on the line at all: the honest answer is the whole grant.

    A trim decided off a projection metres away would be a corridor this
    file invented. RPP pulls a truck back onto a plan it can see, and
    the ClosingWatch is what says so when it cannot.
    """
    granted = [(0.0, 0.0), (40.0, 0.0)]
    assert nav2_path.trim_to(granted, (20.0, 9.0)) == granted


def test_the_trim_never_eats_the_tangent_of_the_corner_it_lands_before():
    """A trim that starts inside a corner has nowhere to put the arc.

    The corner needs r * tan(theta/2) of straight on each side. A truck
    standing 0.30 m before a square corner would leave 0.30 m, and the
    builder refuses that BY NAME - which would BLOCK an order over a
    resume. So the trim backs off to the tangent point instead: the path
    starts at most one tangent behind the truck, which is well inside
    the 2.00 m nav2 will search.
    """
    granted = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    trimmed = nav2_path.trim_to(granted, (9.7, 0.0), radius_m=R)
    assert trimmed[0] == pytest.approx((10.0 - R, 0.0))
    built = nav2_path.build_chain_path(trimmed, radius_m=R, spacing_m=0.10)
    assert built.corners == 1
    assert nav2_path.cusp_at(built.poses) is None
    # and the truck is still inside nav2's own search window: the pose
    # nearest it sits less than 2.00 m of INTEGRATED distance down the
    # path, which is the only measure transformGlobalPlan takes.
    assert _arc_to(built.poses, (9.7, 0.0)) < MAX_ROBOT_POSE_SEARCH_M


def test_a_resume_anywhere_on_any_chain_stays_inside_the_search_window():
    """THE PROPERTY, OVER EVERY CHAIN THIS FLOOR CAN PLAN.

    A SAFETY-STOP can land the truck anywhere on a chain, and the
    re-sent path has to put the truck inside nav2's own 2.00 m
    closest-pose search or the controller aborts on an empty plan. So:
    walk every chain at half-metre steps, re-build from there, and
    measure how far along the rebuilt path the truck actually is.
    """
    worst = 0.0
    for goal in ("S4", "S9", "S12"):
        for start in ((-13.0, 4.25), F1_SPAWN):
            legs = nav2_legs.plan_legs(_plan(start, goal))
            for leg in legs:
                if leg.klass != nav2_legs.RING_CHAIN:
                    continue
                whole = nav2_legs.chain_path(leg, current_yaw=0.0)
                walked = 0.0
                for index in range(len(whole.poses) - 1):
                    walked += math.dist(whole.poses[index][:2],
                                        whole.poses[index + 1][:2])
                    if index % 5:
                        continue
                    here = whole.poses[index][:2]
                    built = nav2_legs.chain_path(leg, current_yaw=0.0,
                                                 start_xy=here)
                    assert nav2_path.cusp_at(built.poses) is None
                    lead = min(
                        _arc_to(built.poses, here),
                        MAX_ROBOT_POSE_SEARCH_M + 1.0)
                    worst = max(worst, lead)
    assert worst < MAX_ROBOT_POSE_SEARCH_M, worst


def _arc_to(poses, xy):
    """Integrated distance from a path's head to the pose nearest `xy`."""
    walked, best, best_at = 0.0, float("inf"), 0.0
    for index, pose in enumerate(poses):
        if index:
            walked += math.dist(poses[index - 1][:2], pose[:2])
        gap = math.dist(pose[:2], xy)
        if gap < best:
            best, best_at = gap, walked
    return best_at


# ----------------------------------------------------------------------
# DEFECT D14: THE PARKING ERROR IS NOT A CORNER
# (measured 2026-09-02, m6_ver2/logs/run17-c8-session-a)
#
# route.plan_route prepends the truck's own POSE and then keeps the entry
# node whenever the pose is nearer that than the second node - so a truck
# standing 0.229 m off a ring node is handed [pose, node, ...] with a 67
# degree turn AT the node. nav2_legs._merge_short folds a run shorter
# than P forward, which puts that turn INSIDE a chunk, and the chain
# builder then met a square-ish corner with 0.229 m of run-in and refused
# the whole order BY NAME:
#
#   adapter  leg 1/2 ring chain NOT SENT: the corners at
#            (-9.911900771893245, 10.210864485560869) and (-10.0, 10.0)
#            claim 0.832 m of tangent between them at radius 1.250 m and
#            the segment joining them is only 0.229 m long
#   /auto/state BLOCKED "blocked: the granted polyline cannot be driven
#                        as a path"                      x2, two orders
#
# THE REFUSAL WAS RIGHT AND THE INPUT WAS WRONG. That vertex is not a
# corner of the granted corridor - it is the truck's own parking error
# with a graph node behind it, which is the sentence _merge_short already
# makes one level down ("the parking error is not a leg"). A head stub
# too short to carry its own corner is DROPPED, and the path starts at
# the node instead - which is at most that stub behind the truck and
# therefore still inside nav2's 2.00 m search.
# ----------------------------------------------------------------------

def test_a_head_stub_too_short_for_its_own_corner_is_dropped():
    granted = [(-9.9119, 10.2109), (-10.0, 10.0), (-13.0, 10.0),
               (-13.0, 4.25)]
    built = nav2_path.build_chain_path(granted, radius_m=R, spacing_m=0.10)
    assert built.dropped == 1
    assert built.poses[0][:2] == pytest.approx((-10.0, 10.0))
    assert built.corners == 1                 # the real one, at (-13, 10)
    assert nav2_path.cusp_at(built.poses) is None


def test_run_17s_own_polyline_builds_instead_of_being_refused():
    """The route that BLOCKED twice, verbatim off its own wire."""
    granted = [(-9.911900771893245, 10.210864485560869), (-10.0, 10.0),
               (-13.0, 10.0), (-13.0, 4.25)]
    built = nav2_path.build_chain_path(granted, radius_m=R, spacing_m=0.10)
    assert built.dropped == 1
    assert built.length_m > 8.0


def test_a_granted_vertex_with_room_is_never_dropped():
    """The rule is about a STUB and not about a head.

    Every chain that starts on the corridor keeps its own first point:
    the drop fires only when the first segment cannot carry the tangent
    the corner after it needs, which on this floor is only ever a
    parking error (granted segments are 3.00 m at the tightest).
    """
    for granted in ([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
                    [(0.0, 0.0), (10.0, 0.0)],
                    [(0.0, 0.0), (1.3, 0.0), (1.3, 10.0)]):
        built = nav2_path.build_chain_path(granted, radius_m=R,
                                           spacing_m=0.10)
        assert built.dropped == 0, granted
        assert built.poses[0][:2] == pytest.approx(granted[0])


def test_a_head_stub_that_doubles_back_is_dropped_and_not_a_reversal():
    """The other half of the same parking error: the truck parked PAST
    its node, so the stub points back the way the route goes. A reversal
    is refused by name - and it must not be, because it is not in the
    corridor at all."""
    granted = [(0.2, 0.0), (0.0, 0.0), (10.0, 0.0)]
    built = nav2_path.build_chain_path(granted, radius_m=R, spacing_m=0.10)
    assert built.dropped == 1
    assert built.poses[0][:2] == pytest.approx((0.0, 0.0))
    assert built.length_m == pytest.approx(10.0)


def test_the_drop_never_eats_the_whole_polyline():
    """The loop is bounded by the polyline and leaves a drivable one."""
    zigzag = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.2, 0.1),
              (0.2, 0.0), (10.0, 0.0)]
    built = nav2_path.build_chain_path(zigzag, radius_m=R, spacing_m=0.10)
    assert built.dropped == 4
    assert built.poses[0][:2] == pytest.approx((0.2, 0.0))
    assert built.poses[-1][:2] == pytest.approx((10.0, 0.0))
    assert nav2_path.cusp_at(built.poses) is None


def test_a_trim_in_front_of_a_reversal_does_not_refuse_the_order():
    """D14, SECOND MEASUREMENT (run17-c8-session-b, 2026-09-02).

    The truck stops 0.247 m PAST its bay point and vda_agent prepends
    that pose, so the route reads [pose, bay, mouth] - a stub pointing
    south in front of a spur pointing north, a turn of pi at the bay.
    trim_to backs its head off the corner ahead, and tangent_m refuses a
    reversal BY NAME - so the back-off raised before _drop_head_stub
    could throw the stub away:

      adapter  leg 1/2 ring chain NOT SENT: a turn of 3.125 rad is a
               reversal, not a corner
      /auto/state BLOCKED, every leg-2 order, for eight minutes of
               requeue

    There is nothing to back off INTO: the stub is not corridor. The
    head stays where the projection put it and the drop does the rest.
    """
    granted = [(-13.004068249189379, 4.497599190050925), (-13.0, 4.25),
               (-13.0, 10.0), (-10.0, 10.0)]
    trimmed = nav2_path.trim_to(granted, (-13.004, 4.4976), radius_m=R)
    built = nav2_path.build_chain_path(trimmed, radius_m=R, spacing_m=0.10,
                                       flipped=True)
    assert built.dropped == 1
    assert built.poses[0][:2] == pytest.approx((-13.0, 4.25))
    assert built.corners == 1
    assert nav2_path.cusp_at(built.poses) is None
