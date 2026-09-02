"""nav2_legs.py - the leg split, the class table and the preempt number.

THE FIXTURES ARE REAL ROUTES AND NOT DRAWINGS. Every polyline below
comes out of m6/ipc/route.py's own planner over m6/ipc/stations.py's own
floor, so a change to either shows up here as a failing split rather
than as a truck that decelerates into a junction it should have driven
through.
"""
import math

import pytest

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
    pose = (7.0, 10.2)
    poly = _plan(pose, "S5")
    assert len(poly) == 3 and poly[1] == (7.0, 10.0)
    legs = nav2_legs.plan_legs(poly)
    assert len(legs) == 2
    assert legs[0].klass == nav2_legs.TRANSIT
    assert legs[1].klass == nav2_legs.STATION_SPUR


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
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S5"))
    leg = legs[0]
    want = math.atan2(leg.end[1] - leg.points[-2][1],
                      leg.end[0] - leg.points[-2][0])
    assert nav2_legs.leg_yaw(leg) == want


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
    # own last segment instead
    assert nav2_legs.leg_yaw(leg) == 0.0


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
