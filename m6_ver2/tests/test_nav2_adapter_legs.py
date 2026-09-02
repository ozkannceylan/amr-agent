"""nav2_legs.py - the leg split, the class table and the preempt number.

THE FIXTURES ARE REAL ROUTES AND NOT DRAWINGS. Every polyline below
comes out of m6/ipc/route.py's own planner over m6/ipc/stations.py's own
floor, so a change to either shows up here as a failing split rather
than as a truck that decelerates into a junction it should have driven
through.
"""
import math

import pytest

import follower
import route
from stations import STATIONS

import nav2_legs


F1_SPAWN = (-17.0, 10.0)


def _plan(pose, station_id):
    poly = route.plan_route(pose, station_id)
    assert poly is not None, "route.py could not plan the fixture"
    return poly


# ----------------------------------------------------------------------
# the split
# ----------------------------------------------------------------------

def test_the_planner_hands_over_a_doubled_first_point():
    # THE REASON split_legs HAS TO DROP ZERO-LENGTH SEGMENTS AT ALL, and
    # it is not hypothetical: plan_route prepends the pose and then only
    # drops the entry node when the pose is nearer the SECOND node, so a
    # truck standing exactly on its spawn node gets that node twice.
    poly = _plan(F1_SPAWN, "S5")
    assert poly[0] == poly[1] == F1_SPAWN


def test_spawn_to_s5_is_a_transit_and_a_spur():
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S5"))
    assert len(legs) == 2
    assert legs[0].points[0] == F1_SPAWN
    assert legs[0].points[-1] == (7.0, 10.0)        # the S5 spur foot
    assert legs[1].points == [(7.0, 10.0), (7.0, 4.25)]
    assert [leg.klass for leg in legs] == [
        nav2_legs.TRANSIT, nav2_legs.STATION_SPUR]
    assert [leg.final for leg in legs] == [False, True]


def test_the_ring_run_is_one_leg_and_not_eight_goals():
    # Eight collinear nodes between the spawn and the spur foot. One
    # goal per node is the thing Decision 2 rejected as a steady state -
    # the truck would decelerate into every one of them.
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S5"))
    assert len(legs[0].points) == 8
    assert {p[1] for p in legs[0].points} == {10.0}


def test_s5_to_s9_splits_at_every_junction_turn():
    start = (7.0, 4.25)
    legs = nav2_legs.plan_legs(_plan(start, "S9"))
    assert [leg.points[0] for leg in legs] == [
        (7.0, 4.25), (7.0, 10.0), (0.0, 10.0), (0.0, -10.0), (-17.0, -10.0)]
    assert [leg.points[-1] for leg in legs] == [
        (7.0, 10.0), (0.0, 10.0), (0.0, -10.0), (-17.0, -10.0),
        (-17.0, -14.9)]
    assert [leg.klass for leg in legs] == [
        nav2_legs.SPUR_EXIT, nav2_legs.TRANSIT, nav2_legs.TRANSIT,
        nav2_legs.TRANSIT, nav2_legs.STATION_SPUR]


def test_the_spur_foot_splits_even_when_the_run_is_straight():
    # THE CASE THE COLLINEARITY RULE ALONE CANNOT SEE. A truck standing
    # 0.20 m north of the ring centreline on the S5 spur's own x plans
    # [pose, spur foot, station] - three points on one line - and a
    # split made only at turns would hand the whole thing to MPPI and
    # lose the station goal checker. The spur foot is a split BY NAME.
    pose = (7.0, 12.0)
    poly = _plan(pose, "S5")
    assert len(poly) == 3 and poly[1] == (7.0, 10.0)
    legs = nav2_legs.plan_legs(poly)
    assert len(legs) == 2
    assert legs[0].klass == nav2_legs.TRANSIT
    assert legs[1].klass == nav2_legs.STATION_SPUR
    # ... AND THE SAME RUN FROM 0.20 m OUT IS ONE LEG, because a run
    # shorter than the hand-over distance is not a leg at all (D9). It
    # is the STATION SPUR that survives, so the 0.25 m goal checker -
    # the whole reason this split exists - is still the one that decides
    # the arrival.
    close = nav2_legs.plan_legs(_plan((7.0, 10.2), "S5"))
    assert len(close) == 1
    assert close[0].klass == nav2_legs.STATION_SPUR
    assert close[0].tree_key == "nav.bt_xml_station"


def test_a_two_point_polyline_is_one_leg():
    legs = nav2_legs.plan_legs([(0.0, 10.0), (7.0, 10.0)])
    assert len(legs) == 1 and legs[0].final


def test_a_polyline_shorter_than_two_points_is_refused_by_name():
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.plan_legs([(0.0, 0.0)])
    assert "fewer than two points" in str(caught.value)


def test_a_polyline_of_one_repeated_point_is_refused_by_name():
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.plan_legs([(1.0, 1.0), (1.0, 1.0)])
    assert "no length" in str(caught.value)


# ----------------------------------------------------------------------
# the classification
# ----------------------------------------------------------------------

def test_the_spur_foot_of_every_station_comes_from_the_graph():
    # ONE HOME. route.build_graph() links each station to exactly one
    # node; this reads that edge rather than re-spelling the rule
    # ("(s.x, +-10.0)") a second time in a second file.
    feet = nav2_legs.spur_feet()
    assert set(feet) == set(STATIONS)
    for sid, foot in feet.items():
        station = (STATIONS[sid]["x"], STATIONS[sid]["y"])
        assert foot[0] == station[0]
        assert abs(foot[1]) == 10.0


def test_a_leg_that_starts_on_a_station_is_the_dead_astern_leg():
    # The truck parked at S5 with 0.18 m of arrival error still counts
    # as standing on the station: it is the pose it will back out of.
    start = (7.0, 4.43)
    legs = nav2_legs.plan_legs(_plan(start, "S1"))
    assert legs[0].klass == nav2_legs.SPUR_EXIT


def test_a_leg_that_starts_a_metre_off_a_station_is_a_transit():
    start = (7.0, 5.4)
    legs = nav2_legs.plan_legs(_plan(start, "S1"))
    assert legs[0].klass == nav2_legs.TRANSIT


def test_the_station_at_a_point_is_none_off_the_floor():
    assert nav2_legs.station_at((7.0, 4.25)) == "S5"
    assert nav2_legs.station_at((0.0, 0.0)) is None


# ----------------------------------------------------------------------
# the class -> controller/tree table
# ----------------------------------------------------------------------

def test_the_table_names_only_controllers_nav2_yaml_declares():
    # PRODUCER PIN. drive_goal.CONTROLLER_TREE is the m5v3 table this
    # one generalises; a third controller name here would be a name
    # bt_navigator cannot open forty metres into a drive.
    #   AND THE TREE KEY IS THE DONOR'S EXCEPT ON ONE ROW. m5v3 had one
    # tree per CONTROLLER because it had one goal checker; this branch
    # has one tree per LEG CLASS because the station spur finishes on a
    # 0.25 m box and the spur exit does not. So the station spur's key
    # is the RPP tree's, with the checker changed, and every other row
    # is still exactly drive_goal's answer.
    import drive_goal
    for klass, (controller, tree_key) in nav2_legs.CLASS_TREE.items():
        assert controller in drive_goal.CONTROLLER_TREE, klass
        donor_key = drive_goal.CONTROLLER_TREE[controller]
        if klass == nav2_legs.STATION_SPUR:
            assert tree_key == "nav.bt_xml_station"
            assert donor_key == "nav.bt_xml_rpp"
        else:
            assert tree_key == donor_key, klass


def test_the_spur_classes_run_rpp_and_transit_runs_mppi():
    assert nav2_legs.controller_for(nav2_legs.STATION_SPUR)[0] == "rpp"
    assert nav2_legs.controller_for(nav2_legs.SPUR_EXIT)[0] == "rpp"
    assert nav2_legs.controller_for(nav2_legs.TRANSIT)[0] == "mppi"


def test_an_unknown_leg_class_is_refused_by_name():
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.controller_for("freespace")
    assert "freespace" in str(caught.value)
    assert "station spur" in str(caught.value)


def test_every_leg_carries_its_controller_and_its_tree_key():
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S5"))
    assert legs[0].controller == "mppi" and legs[0].tree_key == "nav.bt_xml"
    assert legs[1].controller == "rpp"
    assert legs[1].tree_key == "nav.bt_xml_station"


def test_only_the_station_spur_runs_the_station_tree():
    """THE 0.25 m BOX IS FOR THE LEG THAT ENDS IN A BAY AND NO OTHER.

    The spur EXIT is RPP too - a station is left dead-astern - but it is
    preempted 1.5 m from its end like any transit leg, so it never
    reaches a goal checker at all and a tighter box on it would only
    narrow the tube its plan is built in.
    """
    assert nav2_legs.controller_for(nav2_legs.STATION_SPUR) == (
        "rpp", "nav.bt_xml_station")
    assert nav2_legs.controller_for(nav2_legs.SPUR_EXIT) == (
        "rpp", "nav.bt_xml_rpp")
    assert nav2_legs.controller_for(nav2_legs.TRANSIT) == (
        "mppi", "nav.bt_xml")
    keys = [key for _c, key in nav2_legs.CLASS_TREE.values()]
    assert keys.count("nav.bt_xml_station") == 1


# ----------------------------------------------------------------------
# leg_yaw - the heading the goal at a leg's end is approached on
# ----------------------------------------------------------------------

def test_a_station_leg_ends_on_the_bays_own_heading():
    """A bay does not get to choose - the truck arrives forks-first on
    the heading stations.STATIONS declares, and SmacPlannerHybrid plans
    the whole approach around it."""
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S5"))
    assert legs[-1].klass == nav2_legs.STATION_SPUR
    assert nav2_legs.leg_yaw(legs[-1]) == float(STATIONS["S5"]["yaw"])


def test_a_transit_leg_ends_pointing_along_its_last_segment():
    # ... FOR A TRUCK ALREADY POINTING THAT WAY. Since D7 the transit
    # row is bidirectional and the truck's own yaw picks the half; the
    # section at the bottom of this file is where that is pinned.
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S5"))
    leg = legs[0]
    want = math.atan2(leg.end[1] - leg.points[-2][1],
                      leg.end[0] - leg.points[-2][0])
    assert nav2_legs.leg_yaw(leg, want) == want


def test_leg_yaw_reads_one_station_table_and_not_two():
    """The id and the heading come out of the SAME table.

    station_at() takes the table as an argument for exactly this: a
    lookup that found the station in one dict and its yaw in another
    would answer confidently after a bay moved in only one of them.
    """
    moved = {"S5": {"x": 100.0, "y": 100.0, "yaw": 0.5, "arrive_m": 0.25}}
    leg = nav2_legs.Leg(points=[(99.0, 100.0), (100.0, 100.0)],
                        start=(99.0, 100.0), end=(100.0, 100.0),
                        klass=nav2_legs.STATION_SPUR, controller="rpp",
                        tree_key="nav.bt_xml_station", final=True)
    assert nav2_legs.leg_yaw(leg, stations=moved) == 0.5
    # the real table has no station out there, so the same leg reads its
    # own last segment instead - and, being a transit now, the truck's
    # yaw with it (D7)
    assert nav2_legs.leg_yaw(leg, 0.0) == 0.0


def test_a_leg_with_no_last_segment_is_refused_by_name():
    leg = nav2_legs.Leg(points=[(1.0, 1.0), (1.0, 1.0)], start=(1.0, 1.0),
                        end=(1.0, 1.0), klass=nav2_legs.TRANSIT,
                        controller="mppi", tree_key="nav.bt_xml", final=True)
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.leg_yaw(leg)
    assert "no last segment" in str(caught.value)


def test_a_station_without_a_heading_is_refused_by_name():
    broken = {"S5": {"x": 0.0, "y": 0.0, "arrive_m": 0.25}}
    leg = nav2_legs.Leg(points=[(-1.0, 0.0), (0.0, 0.0)], start=(-1.0, 0.0),
                        end=(0.0, 0.0), klass=nav2_legs.STATION_SPUR,
                        controller="rpp", tree_key="nav.bt_xml_station",
                        final=True)
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.leg_yaw(leg, stations=broken)
    assert "approach heading" in str(caught.value)


# ----------------------------------------------------------------------
# the preempt threshold
# ----------------------------------------------------------------------

def test_the_preempt_point_sits_outside_the_mppi_endgame():
    # THE WHOLE REASON P IS 1.5 AND NOT 1.0. Inside 1.4 m MPPI's
    # GoalCritic takes over as a point attraction, so an intermediate
    # leg end reached inside it would be driven as if it were a goal.
    assert nav2_legs.PREEMPT_AT_M > nav2_legs.MPPI_GOAL_THRESHOLD_M
    assert nav2_legs.PREEMPT_AT_M == 1.5
    assert nav2_legs.MPPI_GOAL_THRESHOLD_M == 1.4


def test_the_preempt_fires_below_the_threshold_and_not_above():
    assert nav2_legs.should_preempt(1.49, final=False)
    assert not nav2_legs.should_preempt(1.51, final=False)


def test_the_final_leg_is_never_preempted():
    # Only the final leg runs to actual completion (Decision 2).
    assert not nav2_legs.should_preempt(0.01, final=True)


def test_a_non_finite_distance_is_refused_by_name():
    with pytest.raises(nav2_legs.Nav2LegsError):
        nav2_legs.should_preempt(float("nan"), final=False)


# ----------------------------------------------------------------------
# the selftest
# ----------------------------------------------------------------------

def test_the_selftest_is_green():
    assert nav2_legs._selftest() == 0


def test_the_collinear_tolerance_admits_a_parking_error_and_not_a_turn():
    assert nav2_legs.COLLINEAR_RAD < math.pi / 2.0
    assert nav2_legs.COLLINEAR_RAD > math.radians(5.0)


# ----------------------------------------------------------------------
# D5 - THE LEG OUT OF A BAY, run4, 2026-09-02
#
# m6_ver2/logs/run4-spur-exit-turnaround. After the pick at S1 the fleet
# hands back a route that starts with the truck's POSE - 0.245 m off the
# bay, its own arrival error - and then the STATION POINT itself:
#
#   [(-12.9968, 4.4952), (-13.0, 4.25), (-13.0, 10.0), (-10.0, 10.0), ...]
#
# TWO THINGS WENT WRONG WITH THAT AND THEY COMPOUND.
#
#   1. That 0.245 m first segment is a LEG, and being the route's first
#      it took the SPUR EXIT class with it. The real exit - the bay to
#      the spur mouth - was then a TRANSIT.
#   2. leg_yaw gave that exit the heading of its own last segment,
#      +1.5708 (north). The truck was standing at the bay on the bay's
#      heading, -1.5708. So the goal at the spur mouth demanded a 180
#      degree TURN inside a 5.75 m dead-end spur, and SmacPlannerHybrid
#      planned one: measured, the truck swung out to (-11.32, 7.87) with
#      yaw 2.51, cusped, and reversed north-west out of the aisle
#      entirely, ending at (-13.59, 11.45) where the adapter's own
#      watchdog fired at 30 s without closing. On a later repeat the
#      same manoeuvre put it at (-10.42, 12.36) and a PROTECTIVE field
#      latched Motor False.
#
# A SPUR IS DRIVEN AT THE BAY'S OWN HEADING IN BOTH DIRECTIONS. The
# truck backs in and drives out, or drives in and backs out; either way
# it does not turn round in the aisle it cannot turn round in.
# ----------------------------------------------------------------------

#: The route the fleet published as ft-260b29ed, verbatim off the wire.
RUN4_OUT_OF_S1 = [
    (-12.996778498620323, 4.495172559486896), (-13.0, 4.25), (-13.0, 10.0),
    (-10.0, 10.0), (-7.0, 10.0), (-3.5, 10.0), (0.0, 10.0), (0.0, 0.0),
    (0.0, -10.0), (-3.5, -10.0), (-7.0, -10.0), (-7.0, -4.25)]


def _leg_ending_at(legs, point):
    matches = [leg for leg in legs if leg.end == point]
    assert len(matches) == 1, "no single leg ends at {}".format(point)
    return matches[0]


def test_the_real_exit_out_of_a_bay_is_the_spur_exit():
    legs = nav2_legs.plan_legs(RUN4_OUT_OF_S1)
    exit_leg = _leg_ending_at(legs, (-13.0, 10.0))
    # THE POSE, not the bay point: since D9 the 0.245 m of parking error
    # in front of it is folded into this leg rather than being a leg.
    assert exit_leg.start == RUN4_OUT_OF_S1[0]
    assert exit_leg.points[1] == (-13.0, 4.25)
    assert exit_leg.klass == nav2_legs.SPUR_EXIT
    assert exit_leg.tree_key == "nav.bt_xml_rpp"
    assert exit_leg.controller == "rpp"


def test_the_parking_error_is_not_a_leg_at_all():
    # 0.245 m from the pose to the bay it is standing on. It is the
    # truck's own arrival error with a goal drawn on it: it neither
    # leaves the bay nor arrives anywhere, and since D9 it is not a leg
    # - a run shorter than PREEMPT_AT_M would be dispatched and
    # displaced in the same tick.
    legs = nav2_legs.plan_legs(RUN4_OUT_OF_S1)
    assert legs[0].klass == nav2_legs.SPUR_EXIT
    assert nav2_legs.leg_length_m(legs[0].points) > nav2_legs.PREEMPT_AT_M
    assert not any(math.dist(leg.start, leg.end) < nav2_legs.ON_STATION_M
                   for leg in legs)


def test_a_spur_exit_ends_on_the_bays_own_heading():
    # THE 180 DEGREE TURN, REFUSED. The last segment points north
    # (+1.5708); the bay's heading is -1.5708; the truck is standing on
    # the bay ON that heading, and the way out is straight.
    legs = nav2_legs.plan_legs(RUN4_OUT_OF_S1)
    exit_leg = _leg_ending_at(legs, (-13.0, 10.0))
    segment = math.atan2(exit_leg.end[1] - exit_leg.points[-2][1],
                         exit_leg.end[0] - exit_leg.points[-2][0])
    assert abs(segment - math.pi / 2.0) < 1e-9
    assert nav2_legs.leg_yaw(exit_leg) == float(STATIONS["S1"]["yaw"])
    assert abs(abs(nav2_legs.leg_yaw(exit_leg) - segment) - math.pi) < 1e-9


def test_every_spur_exit_leaves_on_its_own_bays_heading():
    # Every bay on the floor, not just the one that was measured.
    for station_id, station in STATIONS.items():
        poly = _plan((station["x"], station["y"]), "S12"
                     if station_id != "S12" else "S1")
        legs = nav2_legs.plan_legs(poly)
        exits = [leg for leg in legs if leg.klass == nav2_legs.SPUR_EXIT]
        assert len(exits) == 1, station_id
        assert nav2_legs.leg_yaw(exits[0]) == float(station["yaw"]), station_id


def test_the_spur_exit_reads_one_station_table_and_not_two():
    moved = {"S5": {"x": 100.0, "y": 100.0, "yaw": 0.5, "arrive_m": 0.25}}
    leg = nav2_legs.Leg(points=[(100.0, 100.0), (100.0, 105.0)],
                        start=(100.0, 100.0), end=(100.0, 105.0),
                        klass=nav2_legs.SPUR_EXIT, controller="rpp",
                        tree_key="nav.bt_xml_rpp", final=False)
    assert nav2_legs.leg_yaw(leg, stations=moved) == 0.5
    # the real table has no bay out there, so the same leg falls back to
    # its own last segment rather than inventing a heading - and reads
    # the truck's yaw for the half of it, as any transit does (D7)
    assert nav2_legs.leg_yaw(leg, math.pi / 2.0) == math.pi / 2.0


# ----------------------------------------------------------------------
# DEFECT D7: A TRANSIT GOAL'S HEADING IS BIDIRECTIONAL (run5, 2026-09-02)
#
# D5 above fixed the SPUR and left the AISLE, and the aisle killed the
# next run. The "along the last segment" rule is ONE heading for a
# vehicle that drives both ways: a goal yaw equal to the travel
# direction is a goal that says COUNTERWEIGHT FIRST, because this model
# carries its forks at body -x (SPEC_ADAPTER.md Decision 1's sign audit:
# forks-first is NEGATIVE linear.x).
#
# WHAT THAT COST, MEASURED. The truck came out of S1 northbound on the
# bay's own heading (D5, right), stood at the spur mouth (-13.0, 10.0)
# with its body on -1.75 rad and its forks pointing north, and the next
# leg - eastbound down the ring to (0.0, 10.0) - was handed goal yaw
# 0.0. That is a demand to end up pointing forks-WEST while travelling
# east, and SmacPlannerHybrid is heading-aware, so it planned the
# turnaround: the truck left the corridor to (-14.73, 8.65), swung north
# to (-12.13, 11.53) - a metre and a half past the ring centreline -
# came back to (-12.51, 9.63), and the closing watchdog fired at 30 s
# without closing, "blocked: no progress - best 12.22 m". Six BLOCKEDs
# in one order, at (-12.512, 9.631), (-20.580, 11.967), (0.878, 11.861),
# (-13.042, 11.308), (-11.775, 9.628) and (-13.053, 11.290). Not one of
# them was a floor that was not clear.
#
# THE RULE (SPEC_ADAPTER.md AMENDMENTS 3). A TRANSIT leg's goal yaw is
# the travel direction OR its pi-flip, whichever is the smaller rotation
# from the truck's current yaw. STATION legs keep the station heading
# and SPUR_EXIT keeps the bay's (D5) - a bay's approach is not the
# truck's to choose.
# ----------------------------------------------------------------------

#: The route the fleet published as ft-9c5d9392, verbatim off run-5's
#: wire at 04:35:01. The leg out of S1 that never left the aisle.
RUN5_OUT_OF_S1 = [
    (-13.008174938513886, 4.498870345515123), (-13.0, 4.25), (-13.0, 10.0),
    (-10.0, 10.0), (-7.0, 10.0), (-3.5, 10.0), (0.0, 10.0), (0.0, 0.0),
    (0.0, -10.0), (-3.5, -10.0), (-7.0, -10.0), (-7.0, -4.25)]

#: The truck's own body yaw at the spur mouth, quoted off the same wire:
#: the STATE row the watchdog blocked on, 04:36:05, pose
#: (-12.5122, 9.6312, -1.7512).
RUN5_MOUTH_YAW = -1.7512


def _turn(goal_yaw, current_yaw):
    """How far the truck is being asked to rotate, in radians."""
    return abs(follower.norm_ang(goal_yaw - current_yaw))


def test_the_eastbound_leg_out_of_s1_takes_the_pi_flip():
    """RUN 5's OWN GEOMETRY, and the answer that would have driven it."""
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    east = _leg_ending_at(legs, (0.0, 10.0))
    assert east.klass == nav2_legs.TRANSIT
    # the travel direction, which is what the old rule returned
    segment = math.atan2(east.end[1] - east.points[-2][1],
                         east.end[0] - east.points[-2][0])
    assert segment == 0.0
    # ... and it demanded MORE than a quarter turn of a truck standing at
    # the mouth. That demand is the in-aisle turnaround.
    assert _turn(segment, RUN5_MOUTH_YAW) > math.pi / 2.0
    # THE FLIP IS THE ANSWER, and no turnaround is demanded.
    got = nav2_legs.leg_yaw(east, RUN5_MOUTH_YAW)
    assert abs(follower.norm_ang(got - math.pi)) < 1e-9
    assert _turn(got, RUN5_MOUTH_YAW) <= math.pi / 2.0
    assert _turn(got, RUN5_MOUTH_YAW) < _turn(segment, RUN5_MOUTH_YAW)


def test_a_transit_leg_keeps_the_travel_direction_when_that_is_nearer():
    """The flip is not a preference - it is a MINIMUM, and a truck
    already pointing along its leg is asked for nothing."""
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    east = _leg_ending_at(legs, (0.0, 10.0))
    assert nav2_legs.leg_yaw(east, 0.0) == 0.0
    assert nav2_legs.leg_yaw(east, 0.4) == 0.0
    assert nav2_legs.leg_yaw(east, -0.4) == 0.0


def test_the_westbound_case_is_the_same_rule_mirrored():
    """The southern ring leg, driven west, off the same route."""
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    west = _leg_ending_at(legs, (-7.0, -10.0))
    assert west.klass == nav2_legs.TRANSIT
    segment = math.atan2(west.end[1] - west.points[-2][1],
                         west.end[0] - west.points[-2][0])
    assert abs(abs(segment) - math.pi) < 1e-12
    # A truck standing on +1.20 is more than a quarter turn from pi, so
    # the flip - 0.0, forks west, driving west forks-first - is nearer.
    got = nav2_legs.leg_yaw(west, 1.2)
    assert abs(follower.norm_ang(got - 0.0)) < 1e-9
    assert _turn(got, 1.2) <= math.pi / 2.0
    # its mirror, below the axis, gets the same answer
    got = nav2_legs.leg_yaw(west, -1.2)
    assert abs(follower.norm_ang(got - 0.0)) < 1e-9
    # and one already within a quarter turn of pi keeps pi
    got = nav2_legs.leg_yaw(west, 2.4)
    assert abs(follower.norm_ang(got - math.pi)) < 1e-9


def test_the_tie_at_a_quarter_turn_goes_to_the_flip_and_says_so():
    """THE TIE IS NOT A CORNER CASE HERE - IT IS THE SPUR MOUTH.

    |delta| == pi/2 exactly is a truck that parked perfectly: body yaw
    -1.5708 at (-13.0, 10.0) with an eastbound leg, which is run-5's
    geometry with the localiser's error taken out. Both answers are a
    quarter turn, so the rule has to pick one BY NAME - and it cannot
    pick the travel direction, because that is the answer D7 was raised
    against and a well-parked truck would get the defect back.
      The same tie stands at every right-angled junction on this floor,
    which is why it is a rule and not a footnote.
    """
    assert nav2_legs.QUARTER_TURN_RAD == math.pi / 2.0
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    east = _leg_ending_at(legs, (0.0, 10.0))
    for mouth in (-math.pi / 2.0, math.pi / 2.0):
        got = nav2_legs.leg_yaw(east, mouth)
        assert _turn(got, mouth) == pytest.approx(math.pi / 2.0)
        assert abs(follower.norm_ang(got - math.pi)) < 1e-9, mouth


def test_a_transit_leg_asked_without_a_current_yaw_is_refused_by_name():
    """The heading is a fact about the TRUCK, and this file will not
    guess which way it is pointing - guessing is exactly D7."""
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    east = _leg_ending_at(legs, (0.0, 10.0))
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.leg_yaw(east)
    assert "which way the truck is pointing" in str(caught.value)


def test_a_bays_own_legs_ignore_the_trucks_heading_entirely():
    """STATION and SPUR_EXIT are D5's rows and D7 does not touch them:
    a bay's approach is the bay's, whatever the truck is doing."""
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    spur = _leg_ending_at(legs, (-7.0, -4.25))
    exit_leg = _leg_ending_at(legs, (-13.0, 10.0))
    assert spur.klass == nav2_legs.STATION_SPUR
    assert exit_leg.klass == nav2_legs.SPUR_EXIT
    for yaw in (None, 0.0, math.pi, -1.7512, 2.9):
        assert nav2_legs.leg_yaw(spur, yaw) == float(STATIONS["S4"]["yaw"])
        assert nav2_legs.leg_yaw(exit_leg, yaw) == float(STATIONS["S1"]["yaw"])


def test_no_leg_of_the_s1_to_s4_order_demands_more_than_a_quarter_turn():
    """THE WHOLE ORDER, DRIVEN ON PAPER. Each leg's goal yaw is the next
    leg's current yaw - which is what a truck that reaches its goals
    actually does - and no transit on the way asks for more than the 90
    degrees a right-angled junction already is."""
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    current = float(STATIONS["S1"]["yaw"])          # standing in the bay
    for leg in legs:
        goal = nav2_legs.leg_yaw(leg, current)
        if leg.klass == nav2_legs.TRANSIT:
            assert _turn(goal, current) <= math.pi / 2.0 + 1e-12, leg.end
        current = goal


# ----------------------------------------------------------------------
# DEFECT D8: THE TIE IS A BAND (run6, 2026-09-02)
#
# D7 above put the rule in and run 6 reproduced run 5 anyway, with the
# adapter's own leg table naming the reason in one line:
#
#   leg 3/6 transit tree=nav.bt_xml end=(0.00, 10.00)
#           goal_yaw=+0.000 truck_yaw=-1.550 turn=+1.550
#
# THE TWO CANDIDATES DIFFER BY PI, so the two rotations SUM to pi:
# |delta_flip| == pi - |delta_dir|, exactly. "Whichever is smaller" is
# therefore one comparison with ONE degenerate point, |delta| == pi/2 -
# and on this floor that point is not a curiosity, it is EVERY junction.
# The waypoint graph's turns are all right angles and every spur meets
# its ring leg at one, so a truck standing at a spur mouth is at pi/2 to
# the leg it is about to drive BY CONSTRUCTION.
#
# AT THAT POINT THE CRITERION HAS NO OPINION, AND NEAR IT THE OPINION IT
# HAS IS SMALLER THAN THE ERROR THE TRUCK PARKS WITH. Run 6's five mouth
# yaws, off the adapter's own log against a bay heading of -1.5708:
# -1.550, -1.474, -1.565, -1.581, -1.574 - up to 0.097 rad out. The one
# that was 0.021 rad on the wrong side of pi/2 was handed goal yaw 0.0,
# planned the turnaround, left the corridor to (-13.05, 11.35) and the
# watchdog fired: "blocked: no progress - best 13.06 m, 30 s without
# closing". A rule that lets a tenth of a radian of localiser noise pick
# between "drive on" and "turn round in the aisle" is not a rule.
#
# SO THE TIE IS A BAND, and its width is COLLINEAR_RAD - the same 15
# degrees this file already grants a truck's parking error when it asks
# whether two segments are the same straight line. Inside the band the
# flip wins, for the reason the tie does: the flip is the sense the
# truck is already driving in - it left the bay forks-first and the ring
# is run forks-first - and nav2's own direction-hold node refuses a plan
# that flips the driving direction under way ("fresh plan flips the
# driving direction at |v| = 0.272 m/s ... keeping the accepted plan",
# bt_navigator, run 6), so a goal that demands the flip mid-leg is a
# goal that will not be driven at all.
# ----------------------------------------------------------------------

#: Every yaw the truck actually stood at when a ring leg was dispatched
#: out of a spur mouth in run 6, off the adapter's own leg table. The
#: bay heading is -1.5708 and not one of them is it.
RUN6_MOUTH_YAWS = (-1.550, -1.474, -1.565, -1.581, -1.574)


def test_the_tie_band_is_this_files_own_parking_tolerance():
    assert nav2_legs.TIE_BAND_RAD == nav2_legs.COLLINEAR_RAD
    assert nav2_legs.FLIP_ABOVE_RAD == (math.pi / 2.0
                                        - nav2_legs.COLLINEAR_RAD)


def test_every_mouth_yaw_run_6_measured_takes_the_flip():
    """THE REGRESSION, ONE ROW PER MEASUREMENT. Eastbound out of the S1
    mouth and westbound out of it: whichever way the ring leg runs, a
    truck standing on the bay's heading drives on."""
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    east = _leg_ending_at(legs, (0.0, 10.0))
    for mouth in RUN6_MOUTH_YAWS:
        got = nav2_legs.leg_yaw(east, mouth)
        assert abs(follower.norm_ang(got - math.pi)) < 1e-9, mouth
        # and the sense is kept: the goal is a HALF TURN from the travel
        # direction, which is what "forks-first" means on this model
        assert abs(abs(follower.norm_ang(got - 0.0)) - math.pi) < 1e-9


def test_the_westbound_mouth_is_the_same_measurement_mirrored():
    """Run 6's other one: end=(-20.00, 10.00) goal_yaw=+0.000
    truck_yaw=-1.474, which is the leg that took the truck the long way
    round the ring and stalled at 'best 20.26 m'."""
    west = nav2_legs.Leg(
        points=[(-13.0, 10.0), (-17.0, 10.0), (-20.0, 10.0)],
        start=(-13.0, 10.0), end=(-20.0, 10.0), klass=nav2_legs.TRANSIT,
        controller="mppi", tree_key="nav.bt_xml", final=False)
    for mouth in RUN6_MOUTH_YAWS:
        got = nav2_legs.leg_yaw(west, mouth)
        assert abs(follower.norm_ang(got - 0.0)) < 1e-9, mouth


def test_the_travel_direction_still_wins_when_it_is_clearly_nearer():
    """THE BAND IS A BAND AND NOT A NEW DEFAULT. Run 6's own recovery
    leg - end=(-13.00, 10.00) truck_yaw=-0.517 - is a truck genuinely
    pointing down its leg, and it keeps the travel direction."""
    legs = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    east = _leg_ending_at(legs, (0.0, 10.0))
    assert nav2_legs.leg_yaw(east, -0.517) == 0.0
    assert nav2_legs.leg_yaw(east, 1.2) == 0.0
    # ... right up to the edge of the band, and over it
    inside = nav2_legs.FLIP_ABOVE_RAD - 1e-6
    assert nav2_legs.leg_yaw(east, -inside) == 0.0
    outside = nav2_legs.FLIP_ABOVE_RAD + 1e-6
    assert abs(follower.norm_ang(
        nav2_legs.leg_yaw(east, -outside) - math.pi)) < 1e-9


# ----------------------------------------------------------------------
# DEFECT D9: A LEG BORN INSIDE THE PREEMPT DISTANCE IS NOT A LEG
# (run6, 2026-09-02)
#
# route.plan_route prepends the truck's pose and keeps the entry node
# whenever the pose is nearer THAT than the second node - so a truck
# standing 0.047 m off its spawn node is handed both, and split_legs
# duly split between them, because 0.047 m of parking error points
# NORTH and the ring leg after it points east.
#
# WHAT A 0.047 m LEG DOES, MEASURED. It is born already inside
# PREEMPT_AT_M, so it is dispatched and superseded in the same breath -
# two NavigateToPose goals at a single-goal server inside 41 ms - and
# bt_navigator answered the pair with one line:
#
#   Begin navigating from (-0.08, -0.10) to (-0.08, -0.15)
#   Received goal preemption request
#   Begin navigating from (-0.08, -0.10) to (-4.08, -0.16)
#   Goal succeeded                       <- 19 ms later, 4 m short
#
# The 0.047 m goal was inside the 0.60 m goal checker before it was
# sent, so the tree returned SUCCESS - against the label of the goal
# that had just displaced it. The adapter read a non-final leg's
# SUCCEEDED, had nothing to do with it, and stood still until its own
# watchdog called it: "blocked: no progress - best 4.00 m, 30 s without
# closing". Twice, on the same 4 m of empty aisle.
#
# So a leg shorter than the distance at which legs are handed over is
# not a leg: it is the truck's parking error with a goal drawn on it,
# and it is merged into the leg that follows. The rule is D5's - "the
# parking error is not a leg" - stated where it can be enforced.
# ----------------------------------------------------------------------

#: The route the fleet published as ft-29f5e81c, verbatim off run-6's
#: wire at 06:20:01. The truck was 0.047 m off its spawn node.
RUN6_OFF_THE_SPAWN = [
    (-17.000398284298246, 9.954715559641215), (-17.0, 10.0),
    (-13.0, 10.0), (-13.0, 4.25)]


def test_the_parking_error_at_the_spawn_is_not_a_leg_of_its_own():
    legs = nav2_legs.plan_legs(RUN6_OFF_THE_SPAWN)
    assert [leg.klass for leg in legs] == [nav2_legs.TRANSIT,
                                           nav2_legs.STATION_SPUR]
    assert legs[0].start == (-17.000398284298246, 9.954715559641215)
    assert legs[0].end == (-13.0, 10.0)
    assert legs[0].points[1] == (-17.0, 10.0)


def test_no_leg_that_can_be_preempted_is_born_already_inside_p():
    """The property, over every route the floor can plan: a leg that is
    handed over at 1.5 m and is shorter than that is a goal sent and
    displaced in one tick."""
    for station_id, station in STATIONS.items():
        other = "S12" if station_id != "S12" else "S1"
        for pose in ((-17.0, 10.0), (-17.05, 9.95), (0.0, 10.04),
                     (station["x"] + 0.04, station["y"] - 0.04)):
            legs = nav2_legs.plan_legs(_plan(pose, station_id))
            for leg in legs[:-1]:
                assert nav2_legs.leg_length_m(leg.points) >= \
                    nav2_legs.PREEMPT_AT_M, (pose, station_id, leg.end)
        # and out of every bay, which is where the parking error lives
        legs = nav2_legs.plan_legs(
            _plan((station["x"] + 0.04, station["y"] - 0.04), other))
        for leg in legs[:-1]:
            assert nav2_legs.leg_length_m(leg.points) >= \
                nav2_legs.PREEMPT_AT_M, (station_id, other, leg.end)


def test_the_merged_leg_keeps_the_heading_of_its_own_last_segment():
    """Merging is not a re-split: the goal still sits on the leg's last
    segment, which is the ring leg and not the parking error."""
    legs = nav2_legs.plan_legs(RUN6_OFF_THE_SPAWN)
    assert nav2_legs.leg_yaw(legs[0], math.pi) == pytest.approx(
        -math.pi, abs=1e-9)
    assert nav2_legs.leg_yaw(legs[0], 0.0) == 0.0


def test_a_short_FINAL_leg_is_left_alone():
    """There is nothing after it to merge into, and the final leg is
    never preempted anyway - should_preempt says so in one line."""
    legs = nav2_legs.plan_legs([(-13.0, 10.0), (-13.0, 9.6)])
    assert len(legs) == 1
    assert legs[0].final
    assert not nav2_legs.should_preempt(0.01, final=True)
