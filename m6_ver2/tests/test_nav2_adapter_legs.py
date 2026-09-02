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


def _flat(points):
    """[x0, y0, x1, y1, ...] - a point list pytest.approx can read."""
    return [coordinate for point in points for coordinate in point]


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
    """Every junction, and since D12 every long leg AFTER one.

    The three ring legs are 7.0, 20.0 and 17.0 m, all clear of
    SPLIT_ABOVE_M, and each is entered off a right angle - so each is
    opened by its own ALIGN_M alignment leg. The spur exit that starts
    the route is not (it is not a transit) and neither is the station
    spur that ends it.
    """
    start = (7.0, 4.25)
    legs = nav2_legs.plan_legs(_plan(start, "S9"))
    a = nav2_legs.ALIGN_M
    # APPROX AND NOT EQUALITY, since AMENDMENTS 8: two of these three
    # heads are interpolated PAST a collinear vertex (the ring legs
    # carry a node every 3.00-4.00 m and ALIGN_M is 4.51), so the
    # arithmetic that places them is a walk and not one multiply.
    assert _flat(leg.points[0] for leg in legs) == pytest.approx(_flat([
        (7.0, 4.25),
        (7.0, 10.0), (7.0 - a, 10.0),
        (0.0, 10.0), (0.0, 10.0 - a),
        (0.0, -10.0), (-a, -10.0),
        (-17.0, -10.0)]))
    assert _flat(leg.points[-1] for leg in legs) == pytest.approx(_flat([
        (7.0, 10.0),
        (7.0 - a, 10.0), (0.0, 10.0),
        (0.0, 10.0 - a), (0.0, -10.0),
        (-a, -10.0), (-17.0, -10.0),
        (-17.0, -14.9)]))
    assert [leg.klass for leg in legs] == [
        nav2_legs.SPUR_EXIT,
        nav2_legs.ALIGN, nav2_legs.TRANSIT,
        nav2_legs.ALIGN, nav2_legs.TRANSIT,
        nav2_legs.ALIGN, nav2_legs.TRANSIT,
        nav2_legs.STATION_SPUR]


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


def test_every_leg_class_runs_rpp():
    """SPEC_ADAPTER.md AMENDMENTS 4 (G1-C4, AMR-DEC-005 extended).

    THIS TEST USED TO SAY `transit runs mppi` AND IT WAS MEASURED WRONG.
    With AMENDMENTS 3's bidirectional goal heading every transit leg is
    driven forks-first, which on this model is nav2-REVERSE - the
    reversal-heavy class AMR-DEC-005 had already moved off MPPI on the
    m5_ver3 side. Run 7 then measured the m5v3 creep fingerprint
    verbatim on m6v2's transit legs (four plateaus, means 0.0816-0.0905
    m/s inside EVIDENCE_STALL's 0.0777-0.0901 band, DSP holding flip
    plans, the orbit at the leg end, 6 BLOCKEDs in 10 legs), so the
    spec's own sanctioned fallback - RPP for all legs - was taken.
    """
    assert nav2_legs.controller_for(nav2_legs.STATION_SPUR)[0] == "rpp"
    assert nav2_legs.controller_for(nav2_legs.SPUR_EXIT)[0] == "rpp"
    assert nav2_legs.controller_for(nav2_legs.TRANSIT)[0] == "rpp"


def test_no_leg_class_names_mppi_while_the_controller_stays_configured():
    """AMENDMENTS 4's two halves, and the second one is the easy one to
    lose.

    THE TABLE stops naming MPPI. THE STACK does not stop carrying it:
    drive_goal's donor table still maps `mppi` onto the primary tree,
    the derived nav2.yaml still declares BOTH controller plugins, and
    bt_navigator still boots on the primary tree as its default. That is
    deliberate - the fallback has to stay one config key away, because
    the counter-evidence AMENDMENTS 4 weighed (m5v3's clean spawn
    straight, MPPI 8/8 against RPP 7/8) is real. A change that DELETED
    MPPI would pass the first half of this test and throw the second.
    """
    import drive_goal
    assert "mppi" not in [c for c, _k in nav2_legs.CLASS_TREE.values()]
    assert "nav.bt_xml" not in [k for _c, k in nav2_legs.CLASS_TREE.values()]
    # the donor table is untouched and still knows the way back
    assert drive_goal.CONTROLLER_TREE["mppi"] == "nav.bt_xml"
    assert drive_goal.DEFAULT_CONTROLLER == "mppi"


def test_the_only_tree_change_left_in_a_route_is_into_the_station_spur():
    """WHAT AMENDMENTS 4 DID TO THE LEG BOUNDARIES, stated as a
    property over the whole floor rather than over one fixture.

    The adapter has two doors between legs (nav2_adapter_node._advance_to):
    same tree is a TRUE PREEMPTION and the truck never stops; a
    different tree is nav2's own instruction - cancel, wait for the
    result, send - and the truck decelerates into the boundary. With
    the transit row on the RPP tree the ONLY tree change left in any
    route is the last one, into the bay. The spur-exit -> transit
    boundary - which used to cost a full stop at every undock - is now
    a preemption.
    """
    for station_id in sorted(STATIONS):
        legs = nav2_legs.plan_legs(_plan(F1_SPAWN, station_id))
        changes = [i for i in range(1, len(legs))
                   if legs[i].tree_key != legs[i - 1].tree_key]
        assert changes in ([], [len(legs) - 1]), (station_id, changes)
        if changes:
            assert legs[changes[0]].klass == nav2_legs.STATION_SPUR
    # and the undock shape, which is the one that changed: out of S1's
    # bay, up the spur, then east along the ring - one tree throughout.
    # THREE LEGS SINCE D12 AND STILL ONE TREE, which is the claim this
    # test makes: the alignment leg was given the transit's own row
    # precisely so that adding it costs no cancel.
    out = nav2_legs.plan_legs([(-13.0, 4.25), (-13.0, 10.0), (0.0, 10.0)])
    assert [leg.klass for leg in out] == [nav2_legs.SPUR_EXIT,
                                          nav2_legs.ALIGN,
                                          nav2_legs.TRANSIT]
    assert {leg.tree_key for leg in out} == {"nav.bt_xml_rpp"}


# ----------------------------------------------------------------------
# DEFECT D10: A BAY MOUTH IS NOT TAKEN AT SPEED
# (run 8 and run 9, 2026-09-02)
#
# AMENDMENTS 4 put the spur exit and the transit that follows it on ONE
# tree, so the boundary between them stopped being a cancel and became a
# true preemption - and the very first undock after that measured what a
# preemption there costs.
#
#   adapter  leg 1/5 spur exit  end=(-13.00, 10.00) goal_yaw=-1.571
#                               truck_yaw=-1.565 turn=-0.006
#   adapter  leg 2/5 transit    end=( 0.00, 10.00) goal_yaw=-3.142
#                               truck_yaw=-1.544 turn=-1.598
#   bt_navigator  "Received goal preemption request"  (accepted - the
#                 whole run logged ZERO "Preemption request was rejected")
#
# The truck was doing 0.30 m/s at the mouth and was handed a goal a
# quarter turn away. It never stopped. Ground truth: (-13.35, 9.12) ->
# (-12.60, 10.00) -> (-11.83, 10.75) -> (-10.50, 11.80) ->
# (-8.58, 12.36) - a sweeping arc 2.36 m NORTH of the ring centreline,
# into the rack line, where the LEFT protective field demanded
# (`PF b/r/l=T/T/F`), Motor latched False and the order died.
#   IT IS NOT THE LOCALISER. The estimate ran median 0.102 m, p95
# 0.112 m, max 0.187 m against ground truth for the whole session: the
# truck really was out there and the stack knew it.
#   AND IT IS NOT ONE BAD PLAN. bt_navigator's direction-hold node
# refused eleven fresh plans across that arc - "fresh plan flips the
# driving direction at |v| = 0.301 m/s (hold_speed 0.050), -1 -> +1,
# 12.59 m of the accepted plan left ... keeping the accepted plan" -
# because a goal a quarter turn away is a goal the planner can reach
# driving either way, and it changes its mind every replan. So the path
# being tracked stayed the one built at the mouth while the truck drove
# off it.
#
# AND THE CANCEL DOOR IS NOT A STOP, WHICH IS RUN 9's OWN LESSON. The
# first cut of this fix sent the mouth boundary through nav2's
# cancel-then-send door, on the theory that the door was what used to
# make the truck stop there. It is not. Measured, run 9:
#
#   bt_navigator 1788327959.428  "Client requested to cancel the goal"
#   bt_navigator 1788327959.439  "Begin navigating from (-4.13, 1.31)"
#
# ELEVEN MILLISECONDS. nav2 answers a cancel at once and the adapter
# sends at once, so the truck coasts through the boundary at whatever it
# was doing - 0.273 m/s on the very next direction-hold line - and the
# same arc happened again, to the metre: (-12.04, 10.65) ->
# (-8.37, 12.40), the same protective field, the same latch.
#
# THE RULE, SECOND CUT: a leg out of a bay is NOT HANDED OVER AT ALL.
# It runs to its own goal like a final leg, RPP's
# approach_velocity_scaling_dist brings it down over the last metre, and
# nav2's SUCCEEDED for a non-final leg (defect D9's branch) starts the
# next one from a standstill - where the direction hold accepts every
# plan and the planner may choose a driving direction freely.
# ----------------------------------------------------------------------

def test_two_legs_of_one_tree_drive_through_the_boundary():
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S9"))
    pair = [(legs[i], legs[i + 1]) for i in range(len(legs) - 1)
            if legs[i].klass == nav2_legs.TRANSIT
            and legs[i + 1].klass == nav2_legs.TRANSIT][0]
    assert nav2_legs.drives_through(*pair)


def test_a_tree_change_never_drives_through():
    """nav2's own refusal, in the one place it can be asked cheaply."""
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S5"))
    assert legs[-1].klass == nav2_legs.STATION_SPUR
    assert not nav2_legs.drives_through(legs[-2], legs[-1])


def test_a_bay_mouth_is_not_handed_over_at_all_but_driven_to():
    """D10, second cut. The two legs share a tree since AMENDMENTS 4, so
    nav2 has no objection to this boundary at all - which is exactly why
    the refusal has to be ours, and why it cannot be a door: BOTH doors
    hand over at P with the truck still moving."""
    out = nav2_legs.plan_legs(RUN5_OUT_OF_S1)
    assert out[0].klass == nav2_legs.SPUR_EXIT
    assert out[0].tree_key == out[1].tree_key
    assert nav2_legs.drives_through(out[0], out[1])
    # ... and it is never asked, because the leg is never handed over
    assert nav2_legs.runs_to_its_goal(out[0])
    assert not nav2_legs.should_preempt(
        0.01, nav2_legs.runs_to_its_goal(out[0]))


def test_the_undock_route_stops_exactly_twice():
    """THE WHOLE ROUTE OUT OF A BAY, leg by leg.

    The mouth is driven to (D10) and the bay at the far end is driven
    to because it is final. NOTHING ELSE STOPS - AMENDMENTS 8 took the
    alignment leg's stop away, because a leg that stops can stop in the
    middle of its own turn and run 15 measured it doing exactly that.
    Every other leg, alignment legs included, hands over at P.
    """
    legs = nav2_legs.plan_legs(route.plan_route((-13.0, 4.25), "S9"))
    driven = [nav2_legs.runs_to_its_goal(leg) for leg in legs]
    assert driven[0] is True                 # the mouth (D10)
    assert driven[-1] is True                # the bay (it is final)
    assert driven.count(True) == 2, [leg.klass for leg in legs]
    for leg, stops in zip(legs, driven):
        if leg.klass in (nav2_legs.TRANSIT, nav2_legs.ALIGN) \
                and not leg.final:
            assert stops is False, leg.end
    # AND THE LONG LEGS ARE STILL THE MAJORITY OF THE DRIVING: the
    # alignment legs cost ALIGN_M each and nothing else.
    handed = [leg for leg, stops in zip(legs, driven) if not stops]
    assert len(handed) >= 2


def test_an_unknown_leg_class_is_refused_by_name():
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.controller_for("freespace")
    assert "freespace" in str(caught.value)
    assert "station spur" in str(caught.value)


def test_every_leg_carries_its_controller_and_its_tree_key():
    legs = nav2_legs.plan_legs(_plan(F1_SPAWN, "S5"))
    # AMENDMENTS 4: the transit leg carries rpp and the RPP tree now.
    assert legs[0].controller == "rpp"
    assert legs[0].tree_key == "nav.bt_xml_rpp"
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
        "rpp", "nav.bt_xml_rpp")
    keys = [key for _c, key in nav2_legs.CLASS_TREE.values()]
    assert keys.count("nav.bt_xml_station") == 1
    # AND THE PRIMARY TREE IS NAMED BY NOBODY (AMENDMENTS 4). It is
    # still written by the derivation and still passed to bt_navigator
    # as `default_nav_to_pose_bt_xml`, so MPPI stays configured and
    # reachable - but no goal this adapter builds carries it, because
    # every goal names its tree explicitly.
    assert "nav.bt_xml" not in keys


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
                        goal=(100.0, 100.0),
                        klass=nav2_legs.STATION_SPUR, controller="rpp",
                        tree_key="nav.bt_xml_station", final=True)
    assert nav2_legs.leg_yaw(leg, stations=moved) == 0.5
    # the real table has no station out there, so the same leg reads its
    # own last segment instead - and, being a transit now, the truck's
    # yaw with it (D7)
    assert nav2_legs.leg_yaw(leg, 0.0) == 0.0


def test_a_leg_with_no_last_segment_is_refused_by_name():
    leg = nav2_legs.Leg(points=[(1.0, 1.0), (1.0, 1.0)], start=(1.0, 1.0),
                        end=(1.0, 1.0), goal=(1.0, 1.0),
                        klass=nav2_legs.TRANSIT,
                        controller="rpp", tree_key="nav.bt_xml_rpp",
                        final=True)
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.leg_yaw(leg)
    assert "no last segment" in str(caught.value)


def test_a_station_without_a_heading_is_refused_by_name():
    broken = {"S5": {"x": 0.0, "y": 0.0, "arrive_m": 0.25}}
    leg = nav2_legs.Leg(points=[(-1.0, 0.0), (0.0, 0.0)], start=(-1.0, 0.0),
                        end=(0.0, 0.0), goal=(0.0, 0.0),
                        klass=nav2_legs.STATION_SPUR,
                        controller="rpp", tree_key="nav.bt_xml_station",
                        final=True)
    with pytest.raises(nav2_legs.Nav2LegsError) as caught:
        nav2_legs.leg_yaw(leg, stations=broken)
    assert "approach heading" in str(caught.value)


# ----------------------------------------------------------------------
# the preempt threshold
# ----------------------------------------------------------------------

def test_the_preempt_point_sits_outside_both_controllers_endgames():
    """P IS STILL 1.5 AND THE REASON IS NOW TWO REASONS.

    It was measured against MPPI: inside 1.4 m the GoalCritic takes over
    as a point attraction, so an intermediate leg end reached inside it
    would be driven as if it were a goal. AMENDMENTS 4 moved every leg
    onto RPP, and the number did NOT move with them, because RPP's own
    endgame is SHORTER: approach_velocity_scaling_dist 1.0 m and
    max_lookahead_dist 0.95 m in the derived nav2.yaml. So 1.5 m clears
    1.4, 1.0 and 0.95 alike, and the pin below keeps naming MPPI's
    number because that is the largest of the three and therefore the
    one that binds.
    """
    assert nav2_legs.PREEMPT_AT_M > nav2_legs.MPPI_GOAL_THRESHOLD_M
    assert nav2_legs.PREEMPT_AT_M == 1.5
    assert nav2_legs.MPPI_GOAL_THRESHOLD_M == 1.4


def test_the_preempt_fires_below_the_threshold_and_not_above():
    assert nav2_legs.should_preempt(1.49, runs_to_its_goal=False)
    assert not nav2_legs.should_preempt(1.51, runs_to_its_goal=False)


def test_a_leg_that_runs_to_its_goal_is_never_preempted():
    # THE ARGUMENT IS NO LONGER `final`, AND THAT IS D10. The final leg
    # was the only leg that ran to its own goal until run 9 measured
    # what a hand-over at a bay mouth costs; the spur exit joined it,
    # and the caller now asks nav2_legs which legs those are rather
    # than reading one field of the tuple.
    assert not nav2_legs.should_preempt(0.01, runs_to_its_goal=True)


def test_a_non_finite_distance_is_refused_by_name():
    with pytest.raises(nav2_legs.Nav2LegsError):
        nav2_legs.should_preempt(float("nan"), runs_to_its_goal=False)


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
                        goal=(100.0, 105.0),
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
        start=(-13.0, 10.0), end=(-20.0, 10.0), goal=(-20.0, 10.0),
        klass=nav2_legs.TRANSIT,
        controller="rpp", tree_key="nav.bt_xml_rpp", final=False)
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
    assert not nav2_legs.should_preempt(
        0.01, nav2_legs.runs_to_its_goal(legs[0]))


# ----------------------------------------------------------------------
# THE ALIGNMENT LEG - DEFECT D12, MEASURED (run 12, 2026-09-02)
#
# D10 made the spur exit run to its own goal so the truck STOPS at the
# mouth instead of coasting through it, and run-12 shows that stop
# happening. What run-12 also shows is that stopping is not enough:
#
#   adapter  leg 1/5 spur exit end=(-13.00, 10.00) goal_yaw=-1.571
#                              truck_yaw=-1.604 turn=+0.033
#   adapter  leg 2/5 transit   end=( 0.00, 10.00) goal_yaw=-3.142
#                              truck_yaw=-1.552 turn=-1.589    <- 13 m
#   adapter  leg 2/5 transit   end=( 0.00, 10.00) goal_yaw=-3.142
#                              truck_yaw=-1.566 turn=-1.576    <- again
#   /auto/state BLOCKED "blocked: no progress - best 10.99 m, 30 s
#                        without closing"   at truth (-10.50, 10.41)
#
# and the same shape 110 s later on a leg entered off a RING corner
# rather than a mouth:
#
#   adapter  leg 3/5 transit end=(-20.00, -10.00) goal_yaw=+1.571
#                            truck_yaw=+0.495 turn=+1.076      <- 20 m
#   /auto/state BLOCKED "blocked: no progress - best 20.67 m, 30 s
#                        without closing"   at truth (-19.09, 11.20)
#
# GROUND TRUTH SAYS WHAT IT DID: from a standstill at the mouth it ran
# out to (-10.63, 10.92), stopped, came back to (-10.75, 9.76), dithered
# for twelve seconds around (-10.85, 9.5), went west to (-11.52, 9.77)
# and set off on the same arc again. It is not D11's excursion - the
# worst northward offset in that stretch was +0.927 m against run-10's
# +2.43 - and it is not a creep: the speeds are 0.02-0.30 m/s, no
# plateau. It is the SAME quarter-turn D10 named, now oscillating
# instead of arcing, because AMENDMENTS 5 removed the node that used to
# hold the mouth-built plan against every replan. Nothing carries the
# truck out of the corridor any more; nothing converges either.
#
# THE FIX IS TO STOP ASKING ONE GOAL TO DO TWO THINGS. A goal 13 m away
# and a quarter turn round is a turn AND a transit, and SmacPlannerHybrid
# re-decides the turn on every replan because both senses reach it. So a
# long leg entered off a turn is opened by a SHORT on-ring goal: the
# truck resolves the quarter turn against a goal it can see and the long
# goal is then sent to a truck that is already aligned - turn about zero,
# one sense, one plan.
#
# ----------------------------------------------------------------------
# AND THE SHORT GOAL WAS TOO SHORT, AND IT STOPPED ON IT - AMENDMENTS 8
# (G1-C7 ruling, measured run 15, 2026-09-03)
#
# Run 15 drove thirteen alignment legs and completed thirteen. It also
# blocked four times, and two of those were STANDING STILL when the
# watchdog called them:
#
#   align 6/8 end=(-2.75, -10.00) goal_yaw=+0.000 truck_yaw=+1.583
#                                              -> COMPLETED
#   [WARN] f1.planner_server: GridBased plugin failed to plan from
#          (-14.70, 20.34) to (-10.14, 19.82): "exceeded maximum
#          iterations"                              x5, and x5 again
#   /auto/state BLOCKED "blocked: no progress - best 4.40 m, 30 s
#                        without closing"  truth [-2.7078, -10.5319,
#                                                 -0.9048]
#
# THE MAP FRAME IS THE SAME TWO POSES. Through the committed
# registration (world = (-17.079, 9.854) - map, the seed's own pi
# rotation) the planner's start is world (-2.38, -10.49) and its goal is
# world (-6.94, -9.97) - the alignment leg's own end at (-2.75, -10.00)
# missed by 0.53 m and 0.90 rad, and then the 4.59 m transit after it,
# planned from that pose over free paint, ten times refused.
#
# SO THE ALIGNMENT LEG COMPLETED IN THE MIDDLE OF ITS OWN TURN. Its
# checker is the transit's 0.60 m box and it is POSITION ONLY - a
# tricycle cannot rotate in place, so nothing in nav2 was ever going to
# hold it to a heading - and ALIGN_M 2.75 less that box is 2.15 m, which
# is barely over the quarter arc itself (pi/2 x 1.25 = 1.96 m). The
# truck was declared arrived while it was still turning, stopped there
# skewed and off the line, and handed the planner exactly the start pose
# a 1.25 m-radius Hybrid-A* cannot close a short goal from.
#
# TWO CHANGES, AND THEY ARE ONE IDEA: the goal has to sit past the END
# of the turn, and the leg must not stop on it.
#   ALIGN_M = quarter arc + P + one straightening length, so the point
# at which the leg HANDS OVER (P short of its goal) is already a
# wheelbase of straight running past the arc.
#   AND ALIGN LEAVES DRIVEN_TO_ITS_GOAL. It preempts at P like any
# transit, so the long goal is dispatched from a MOVING, on-axis pose
# and run-15's standing-start class cannot be built at all: the only
# leg class that still stops mid-route is the spur exit, whose stop is
# on the bay's own axis at a graph node (D10).
# ----------------------------------------------------------------------

def _drivable(start, station):
    """A planned route, or None when there is nothing to drive.

    Standing ON the station asked for gives a polyline of one repeated
    point, which split_legs refuses BY NAME - that refusal is its own
    test and is not what these sweeps are about.
    """
    poly = route.plan_route(start, station)
    if poly is None or len(nav2_legs._clean(poly)) < 2:
        return None
    return poly


def _classes(poly):
    return [leg.klass for leg in nav2_legs.plan_legs(poly)]


def _lengths(poly):
    return [nav2_legs.leg_length_m(leg.points)
            for leg in nav2_legs.plan_legs(poly)]


def test_the_align_class_is_in_the_table_and_runs_the_transit_tree():
    """An alignment leg is a transit in every way but its length."""
    assert nav2_legs.ALIGN in nav2_legs.CLASS_TREE
    assert (nav2_legs.controller_for(nav2_legs.ALIGN)
            == nav2_legs.controller_for(nav2_legs.TRANSIT))


def _align_leg(length=None):
    """A bare ALIGN leg, for the class questions that need no route."""
    length = nav2_legs.ALIGN_M if length is None else length
    return nav2_legs.Leg(points=[(0.0, 0.0), (length, 0.0)],
                         start=(0.0, 0.0), end=(length, 0.0),
                         goal=(length, 0.0), klass=nav2_legs.ALIGN,
                         controller="rpp", tree_key="nav.bt_xml_rpp",
                         final=False)


def test_an_alignment_leg_hands_over_in_motion_like_any_transit():
    """AMENDMENTS 8. The align stop was the defect, not the fix.

    Run 15 completed thirteen alignment legs and two of them completed
    MID-TURN, against a position-only 0.60 m box, 0.53 m off the line
    and 0.90 rad skew - and the transit dispatched from that standstill
    was refused by Smac ten times over free paint. A leg that stops is
    a leg that can stop in the wrong place; a leg that hands over at P
    cannot, because at P it is still being driven.
    """
    assert nav2_legs.ALIGN not in nav2_legs.DRIVEN_TO_ITS_GOAL
    assert nav2_legs.runs_to_its_goal(_align_leg()) is False
    assert nav2_legs.should_preempt(
        nav2_legs.PREEMPT_AT_M - 0.01,
        nav2_legs.runs_to_its_goal(_align_leg())) is True


def test_the_spur_exit_is_the_only_class_that_still_stops():
    """D10 keeps its stop and it is now the ONLY one (AMENDMENTS 8).

    Which matters for a reason the tuple cannot show on its own: a spur
    exit stops ON THE BAY'S OWN AXIS at a graph node, having driven
    5.75 m dead astern in a straight line. It is the one standstill
    this file can build, and it is not a pose in the middle of a turn.
    """
    assert nav2_legs.DRIVEN_TO_ITS_GOAL == (nav2_legs.SPUR_EXIT,)


def test_the_alignment_length_is_an_arc_a_handover_and_a_straightening():
    """ARITHMETIC, AND EVERY TERM IS SOMEBODY ELSE'S MEASUREMENT.

    quarter arc  pi/2 x 1.25 m, the model's measured minimum turning
                 radius (m5_ver3/config.yaml nav.min_radius_m), through
                 the right angle every turn on this floor is;
    P            because the leg HANDS OVER P short of its own goal
                 now, so P is inside the leg and not after it;
    straighten   one wheelbase (m5_ver3/config.yaml vehicle.wheelbase_m)
                 of straight running before the handover.
    """
    assert nav2_legs.MIN_TURN_RADIUS_M == 1.25
    assert nav2_legs.STRAIGHTEN_M == 1.05
    assert nav2_legs.QUARTER_ARC_M == pytest.approx(
        math.pi / 2.0 * nav2_legs.MIN_TURN_RADIUS_M)
    assert nav2_legs.QUARTER_ARC_M == pytest.approx(1.9635, abs=1e-4)
    assert nav2_legs.ALIGN_M == pytest.approx(
        nav2_legs.QUARTER_ARC_M + nav2_legs.PREEMPT_AT_M
        + nav2_legs.STRAIGHTEN_M)
    assert nav2_legs.ALIGN_M == pytest.approx(4.5135, abs=1e-4)
    # AND THE OLD NUMBER'S OWN MARGIN IS WHAT IT REPLACES. nav2 may
    # declare the leg finished 0.60 m short of the goal, so at 2.75 the
    # earliest legal completion was 2.15 m along a leg whose first
    # 1.96 m IS the arc: 0.19 m of straight running, under a fifth of a
    # wheelbase. Run 15 was declared arrived inside that twice, 0.53 m
    # off the line at 0.90 rad of skew.
    old = 2.75 - nav2_legs.TRANSIT_GOAL_CHECKER_M - nav2_legs.QUARTER_ARC_M
    assert 0.0 < old < nav2_legs.STRAIGHTEN_M / 5.0
    assert (nav2_legs.ALIGN_M - nav2_legs.PREEMPT_AT_M
            - nav2_legs.QUARTER_ARC_M) == pytest.approx(
                nav2_legs.STRAIGHTEN_M)


def test_the_handover_happens_a_straightening_past_the_end_of_the_turn():
    """THE PROPERTY THE NUMBER EXISTS FOR, stated without the number.

    The long goal leaves when the truck is P from the alignment goal.
    That instant has to be past the arc, and past it by enough straight
    running that the body is ALONG the axis and not merely on it.
    """
    handover = nav2_legs.ALIGN_M - nav2_legs.PREEMPT_AT_M
    assert handover > nav2_legs.QUARTER_ARC_M
    assert handover - nav2_legs.QUARTER_ARC_M == pytest.approx(
        nav2_legs.STRAIGHTEN_M)


def test_nav2_can_never_declare_an_alignment_leg_reached():
    """Run 15's own mechanism, closed by arithmetic.

    The align leg runs the transit tree, whose FollowPath names the
    0.60 m `general_goal_checker`. P is outside that box, so the leg is
    superseded before nav2 could ever call it finished - which is what
    makes the mid-turn completion unconstructable rather than unlikely.
    """
    assert nav2_legs.PREEMPT_AT_M > nav2_legs.TRANSIT_GOAL_CHECKER_M


def test_the_split_length_is_derived_from_the_preempt_point():
    """NOT A TUNED NUMBER. Below ALIGN_M + PREEMPT_AT_M the remainder
    would be shorter than P, and _merge_short folds any non-final run
    shorter than P forward - so the split would be undone in the next
    line of the same function. The threshold IS that arithmetic."""
    assert nav2_legs.SPLIT_ABOVE_M == (nav2_legs.ALIGN_M
                                       + nav2_legs.PREEMPT_AT_M)
    assert nav2_legs.ALIGN_M > nav2_legs.PREEMPT_AT_M


def test_the_long_eastbound_leg_off_the_s1_mouth_is_split():
    """Run-12's first BLOCKED, as a unit test.

    The route out of S1 to S4: spur exit to the mouth, then 13 m of ring
    east. That second leg is what died.
    """
    poly = _plan((-13.0, 4.25), "S4")
    legs = nav2_legs.plan_legs(poly)
    klasses = [leg.klass for leg in legs]
    assert nav2_legs.SPUR_EXIT in klasses
    exit_at = klasses.index(nav2_legs.SPUR_EXIT)
    assert klasses[exit_at + 1] == nav2_legs.ALIGN, klasses
    align = legs[exit_at + 1]
    assert nav2_legs.leg_length_m(align.points) == pytest.approx(
        nav2_legs.ALIGN_M, abs=1e-9)
    # AND IT IS ON THE RING, not off it: the alignment goal is a point
    # of the leg it opens, so it cannot invent a pose off the corridor.
    assert align.end[1] == pytest.approx(10.0, abs=1e-9)
    assert legs[exit_at + 2].klass == nav2_legs.TRANSIT


def test_the_alignment_leg_and_its_remainder_are_the_original_leg():
    """The split adds a vertex; it does not move the route."""
    poly = _plan((-13.0, 4.25), "S4")
    legs = nav2_legs.plan_legs(poly)
    aligned = [index for index, leg in enumerate(legs)
               if leg.klass == nav2_legs.ALIGN]
    assert aligned
    for index in aligned:
        head, tail = legs[index], legs[index + 1]
        assert head.end == tail.start
        whole = nav2_legs.leg_length_m(head.points) + \
            nav2_legs.leg_length_m(tail.points)
        # collinear by construction, so the two add up to the one
        assert whole == pytest.approx(
            math.dist(head.start, tail.end), abs=1e-6)


#: EVERY POSE ON THIS FLOOR A ROUTE CAN START FROM: the twelve bays and
#: the four spawn nodes status_contract declares. The sweeps below are
#: over all of them because the property they pin is about the SHAPE of
#: a leg queue, and one route cannot show that.
ALL_STARTS = tuple(sorted(
    [(float(s["x"]), float(s["y"])) for s in STATIONS.values()]
    + [(-17.0, 10.0), (-10.0, 10.0), (10.0, 10.0), (17.0, 10.0)]))


def _every_queue():
    """(start, station, legs) for every route this floor can plan."""
    for start in ALL_STARTS:
        for station in sorted(STATIONS):
            poly = _drivable(start, station)
            if poly is None:
                continue
            yield start, station, nav2_legs.plan_legs(poly)


def test_no_standing_start_is_ever_handed_a_long_goal():
    """THE PIN AMENDMENTS 8 EXISTS FOR, over every route on the floor.

    Run 15's fatal shape was: a leg completes, the truck STOPS wherever
    that completion caught it, and the next goal - 4.59 m away and a
    quarter turn round - is planned from there. Smac refused it ten
    times.

    With ALIGN out of DRIVEN_TO_ITS_GOAL there is exactly one class
    left that hands a standstill to another leg, and it is the spur
    exit. So two things have to hold everywhere:

      * the leg BEFORE any standstill is a spur exit and never an
        alignment leg - a stop can only happen at a bay mouth, on the
        bay's own axis, at a graph node;
      * the leg AFTER it is never longer than ALIGN_M + P. A standing
        truck is never shown a goal further than the alignment leg
        would have been, whether it got one or not.
    """
    for start, station, legs in _every_queue():
        for index in range(1, len(legs)):
            if not nav2_legs.runs_to_its_goal(legs[index - 1]):
                continue
            where = "{} -> {} leg {}".format(start, station, index)
            assert legs[index - 1].klass == nav2_legs.SPUR_EXIT, where
            assert nav2_legs.leg_length_m(legs[index].points) \
                <= nav2_legs.SPLIT_ABOVE_M + 1e-9, where


def test_the_only_legs_driven_to_their_goals_are_the_mouth_and_the_bay():
    """The other half of the same sentence: no leg in the MIDDLE of a
    route stops except a spur exit, and the last one always does."""
    for start, station, legs in _every_queue():
        where = "{} -> {}".format(start, station)
        assert nav2_legs.runs_to_its_goal(legs[-1]) is True, where
        for leg in legs[:-1]:
            assert nav2_legs.runs_to_its_goal(leg) is (
                leg.klass == nav2_legs.SPUR_EXIT), where


def test_the_alignment_goal_may_sit_past_a_collinear_vertex():
    """WHY THE HEAD IS WALKED ALONG THE CHUNK AND NOT ALONG SEGMENT ONE.

    route.py draws the ring legs with a node every 3.00 to 4.00 m ("the
    widest gap on either leg is 4.00 m"), and ALIGN_M is 4.51. A rule
    that refused to place the head past the chunk's first VERTEX would
    therefore refuse it on every east-west ring chunk on this floor -
    196 of them, including all three that carried run-15's BLOCKEDs -
    and D12 would quietly stop existing where it was measured.
      A chunk is near-collinear by construction (COLLINEAR_RAD), so a
    point past one of its vertices is still a point of this leg on this
    leg's heading. Walking is therefore free; refusing is not.
    """
    legs = nav2_legs.plan_legs(_plan((-13.0, 4.25), "S4"))
    align = [leg for leg in legs if leg.klass == nav2_legs.ALIGN][0]
    assert math.dist(align.points[0], align.points[1]) == pytest.approx(3.0)
    assert math.dist(align.points[0], align.points[1]) < nav2_legs.ALIGN_M
    assert align.points[1] == (-10.0, 10.0)         # the vertex, kept
    assert align.end == pytest.approx((-13.0 + nav2_legs.ALIGN_M, 10.0))
    assert nav2_legs.leg_length_m(align.points) == pytest.approx(
        nav2_legs.ALIGN_M)
    # and the head is ON the leg: same heading as the segment it opened
    assert abs(follower.norm_ang(
        math.atan2(align.end[1] - align.points[1][1],
                   align.end[0] - align.points[1][0])
        - math.atan2(align.points[1][1] - align.points[0][1],
                     align.points[1][0] - align.points[0][0]))) < 1e-12


def test_the_split_still_reaches_every_long_chunk_on_the_floor():
    """The sweep behind the sentence above: every chunk over the
    threshold gets its alignment leg, whatever its node spacing."""
    seen = 0
    for start, station, legs in _every_queue():
        for index in range(1, len(legs)):
            leg = legs[index]
            if leg.klass != nav2_legs.TRANSIT:
                continue
            if legs[index - 1].klass == nav2_legs.ALIGN:
                seen += 1
                continue
            # NOT OPENED BY AN ALIGNMENT LEG - so it has to be a chunk
            # the threshold left whole, which is the only other way a
            # transit is allowed to exist off a turn.
            assert nav2_legs.leg_length_m(leg.points) \
                <= nav2_legs.SPLIT_ABOVE_M + 1e-9, (start, station, index)
    assert seen > 100, seen


def test_a_mouth_to_mouth_hop_is_now_its_own_alignment_leg():
    """THE BAND THE NEW THRESHOLD CLOSES, NAMED RATHER THAN HIDDEN.

    SPLIT_ABOVE_M followed ALIGN_M from 4.25 m to 6.01 m, so chunks in
    between stopped being split. On this floor that band holds exactly
    one shape: the 6.00 m hop between two adjacent pick bays on one
    ring leg (S1<->S2, S3<->S4, S5<->S6, S7<->S8), eight chunks in all.

    It is NOT a regression, and the arithmetic says why. Under 2.75 the
    6.00 m chunk was split into an alignment leg that STOPPED 2.75 m
    along - mid-arc, by the measurement above - and a 3.25 m transit
    dispatched from that skewed standstill: run-15's own fatal shape.
    Now it is one goal, 6.00 m, driven from the mouth stop and handed
    over at P into the bay. One decision instead of two.
    """
    legs = nav2_legs.plan_legs(_plan((-13.0, 4.25), "S2"))
    assert [leg.klass for leg in legs] == [
        nav2_legs.SPUR_EXIT, nav2_legs.TRANSIT, nav2_legs.STATION_SPUR]
    hop = legs[1]
    assert nav2_legs.leg_length_m(hop.points) == pytest.approx(6.0)
    assert nav2_legs.leg_length_m(hop.points) <= nav2_legs.SPLIT_ABOVE_M
    assert nav2_legs.runs_to_its_goal(hop) is False


def test_a_leg_at_the_head_of_a_route_is_never_split():
    """The first leg starts under the TRUCK and not off a turn.

    Run-12 drove three of them clean - `leg 1/2 transit end=(-13.00,
    10.00)` from (-10.50, 10.41) among them - and the truck's own
    heading, which is what decides whether there is a turn at all, is
    not in this file's hands at split time. A split there would be a
    guess, and this file does not guess (leg_yaw's own refusal).
    """
    poly = _plan(F1_SPAWN, "S5")
    legs = nav2_legs.plan_legs(poly)
    assert legs[0].klass != nav2_legs.ALIGN


def test_a_short_leg_off_a_turn_is_left_whole():
    """Under the threshold the leg IS the alignment leg."""
    poly = [(-13.0, 4.25), (-13.0, 10.0), (-13.0 + 3.0, 10.0)]
    klasses = _classes(poly)
    assert nav2_legs.ALIGN not in klasses, klasses


def test_a_long_leg_off_a_turn_is_split_wherever_the_turn_is():
    """Run-12's SECOND blocked was at a ring corner and not a mouth.

    `leg 3/5 transit end=(-20.00, -10.00) turn=+1.076`, dispatched at
    the corner (-20, 10), best 20.67 m, 30 s without closing, truth
    (-19.09, 11.20). So the rule is about the TURN and not about bays -
    which is also the cheaper rule to state.
    """
    poly = [(-13.0, 10.0), (-20.0, 10.0), (-20.0, -10.0)]
    legs = nav2_legs.plan_legs(poly)
    klasses = [leg.klass for leg in legs]
    assert klasses[0] == nav2_legs.TRANSIT       # head of the route
    assert klasses[1] == nav2_legs.ALIGN, klasses
    assert legs[1].start == (-20.0, 10.0)
    assert legs[1].end == pytest.approx((-20.0, 10.0 - nav2_legs.ALIGN_M))


def test_the_alignment_goal_takes_the_bidirectional_transit_yaw():
    """It is a transit leg, so it obeys AMENDMENTS 3 like every other.

    A forklift does not turn round to go somewhere; the alignment leg
    exists to let it settle into ONE of the two senses, so it must be
    allowed both.
    """
    poly = _plan((-13.0, 4.25), "S4")
    legs = nav2_legs.plan_legs(poly)
    align = [leg for leg in legs if leg.klass == nav2_legs.ALIGN][0]
    east = math.atan2(align.end[1] - align.start[1],
                      align.end[0] - align.start[0])
    # standing at the mouth on the bay heading: a quarter turn away, so
    # the flip wins - the sense the truck already drives in.
    got = nav2_legs.leg_yaw(align, current_yaw=-1.5708)
    assert got == pytest.approx(follower.norm_ang(east + math.pi))
    # and pointing along it already, it keeps it
    assert nav2_legs.leg_yaw(align, current_yaw=east) == pytest.approx(east)


def test_no_alignment_leg_is_ever_born_inside_the_preempt_point():
    """D9's rule, applied to the leg this task adds.

    Every alignment leg is ALIGN_M long and ALIGN_M > PREEMPT_AT_M, so
    _merge_short can never fold one forward - which would silently put
    the long goal back at the turn.
    """
    for station in sorted(STATIONS):
        for start in (F1_SPAWN, (-13.0, 4.25), (-7.0, -4.25)):
            poly = _drivable(start, station)
            if poly is None:
                continue
            for leg in nav2_legs.plan_legs(poly):
                if leg.klass != nav2_legs.ALIGN:
                    continue
                assert nav2_legs.leg_length_m(leg.points) > \
                    nav2_legs.PREEMPT_AT_M


def test_every_split_leaves_a_remainder_that_is_still_a_leg():
    """The other half of the same rule, over every route on the floor."""
    for station in sorted(STATIONS):
        for start in (F1_SPAWN, (-13.0, 4.25), (-7.0, -4.25)):
            poly = _drivable(start, station)
            if poly is None:
                continue
            legs = nav2_legs.plan_legs(poly)
            for index, leg in enumerate(legs):
                if leg.klass != nav2_legs.ALIGN:
                    continue
                assert index + 1 < len(legs)
                rest = legs[index + 1]
                assert nav2_legs.leg_length_m(rest.points) >= \
                    nav2_legs.PREEMPT_AT_M


def test_the_split_never_changes_where_a_route_ends():
    """The last point of the last leg is the last point of the route."""
    for station in sorted(STATIONS):
        for start in (F1_SPAWN, (-13.0, 4.25), (-7.0, -4.25)):
            poly = _drivable(start, station)
            if poly is None:
                continue
            legs = nav2_legs.plan_legs(poly)
            assert legs[-1].end == tuple(poly[-1])
            assert legs[-1].final is True
            assert legs[0].start == nav2_legs._clean(poly)[0]


def test_a_station_spur_is_never_turned_into_an_alignment_leg():
    """The bay's own leg keeps its 0.25 m checker and its bay heading.

    A spur is 5.75 m - over the threshold - and it is entered off a
    right-angle turn at the mouth, so it is exactly the shape this rule
    matches. It must not: the alignment goal would be a pose inside the
    spur with a transit heading, and the truck would arrive at the bay
    on a heading the bay does not admit (D5).
    """
    poly = _plan(F1_SPAWN, "S1")
    legs = nav2_legs.plan_legs(poly)
    assert legs[-1].klass == nav2_legs.STATION_SPUR
    assert legs[-1].tree_key == "nav.bt_xml_station"
    for leg in legs:
        if leg.klass == nav2_legs.ALIGN:
            assert nav2_legs.station_at(leg.end) is None


# ----------------------------------------------------------------------
# DEFECT D13: THE BAY-ARRIVAL LIVELOCK (run 13, 2026-09-03)
#
# nav2's `station_goal_checker` and the fleet's own arrival radius are
# THE SAME NUMBER - 0.25 m - with zero margin between them, sampled by
# two consumers off two beliefs at two instants. A goal AT the station
# point is therefore a goal nav2 declares reached the millimetre the
# truck crosses the fleet's own boundary, and run 13 measured what that
# costs: nav2 SUCCEEDED with the estimate 0.2473 m out and the ground
# truth 0.3121 m out, the truck stood there, and re-sending the same
# goal fourteen times moved it nowhere - a re-issued goal cannot move a
# truck that is already inside the checker.
#
# SO THE GOAL MOVES AND THE CHECKER DOES NOT (SPEC_ADAPTER.md
# AMENDMENTS 6). The station leg's goal is the station point advanced
# ARRIVE_BIAS_M along the approach axis; the same 0.25 m checker then
# fires ARRIVE_BIAS_M earlier in station-point terms, and the truck
# stops with margin inside the radius the fleet is reading.
# ----------------------------------------------------------------------

#: What the estimate read when nav2 declared the bay reached, run 13
#: (m6_ver2/logs/run13-c5-session-b, 09:15:11 and thirteen repeats).
RUN13_STOP_M = 0.2473
#: And where the truck actually was at that instant.
RUN13_TRUTH_M = 0.3121


def test_the_run13_stop_is_the_boundary_it_was_measured_at():
    """The defect, stated in its own numbers before the fix is asked for.

    nav2 was satisfied and the fleet was not - by 0.0027 m on the
    estimate and by 0.0621 m on the truth. Nothing here is about the
    fix; it is the reading the fix has to beat.
    """
    assert RUN13_STOP_M < follower.ARRIVE_M
    assert RUN13_TRUTH_M > follower.ARRIVE_M


def test_the_bias_pulls_the_run13_stop_inside_the_fleet_radius():
    """The regression: run 13's own stop, with the goal 0.10 m deeper.

    The truck stops where the checker was satisfied - RUN13_STOP_M short
    of the GOAL, on the goal's own approach axis. Move the goal
    ARRIVE_BIAS_M deeper and the same stop is ARRIVE_BIAS_M nearer the
    STATION POINT, which is the only distance the fleet and the adapter
    ever measure.
    """
    bay = nav2_legs.plan_legs(_plan(F1_SPAWN, "S1"))[-1]
    assert bay.klass == nav2_legs.STATION_SPUR
    yaw = float(STATIONS["S1"]["yaw"])
    for reading in (RUN13_STOP_M, RUN13_TRUTH_M):
        stop = (bay.goal[0] - reading * math.cos(yaw),
                bay.goal[1] - reading * math.sin(yaw))
        assert math.dist(stop, bay.end) == pytest.approx(
            reading - nav2_legs.ARRIVE_BIAS_M, abs=1e-9)
        assert follower.arrived(stop, bay.end, follower.ARRIVE_M)


def test_the_station_goal_is_the_point_advanced_along_the_approach_axis():
    """Every bay on the floor, and the heading is not touched."""
    for station_id, station in sorted(STATIONS.items()):
        poly = _drivable(F1_SPAWN, station_id)
        if poly is None:
            continue
        bay = nav2_legs.plan_legs(poly)[-1]
        assert bay.klass == nav2_legs.STATION_SPUR, station_id
        yaw = float(station["yaw"])
        assert bay.goal[0] == pytest.approx(
            bay.end[0] + nav2_legs.ARRIVE_BIAS_M * math.cos(yaw), abs=1e-12)
        assert bay.goal[1] == pytest.approx(
            bay.end[1] + nav2_legs.ARRIVE_BIAS_M * math.sin(yaw), abs=1e-12)
        assert math.dist(bay.goal, bay.end) == pytest.approx(
            nav2_legs.ARRIVE_BIAS_M, abs=1e-12)
        assert nav2_legs.leg_yaw(bay) == yaw, station_id


def test_the_approach_axis_is_the_spur_the_legs_own_polyline_runs_on():
    """The bias runs down the SPUR and not off it.

    The axis is taken from the bay's declared approach heading - the one
    number leg_yaw already sends as the goal's orientation, so a goal's
    position and its heading cannot disagree. This is the claim that
    makes that the same axis the leg is on: for every station leg the
    real planner builds, the leg's own last segment is collinear with
    the declared heading to within the tolerance this file already
    grants a truck's parking error.
    """
    for station_id in sorted(STATIONS):
        poly = _drivable(F1_SPAWN, station_id)
        if poly is None:
            continue
        bay = nav2_legs.plan_legs(poly)[-1]
        tail = bay.points[-2]
        segment = math.atan2(bay.end[1] - tail[1], bay.end[0] - tail[0])
        yaw = float(STATIONS[station_id]["yaw"])
        assert abs(follower.norm_ang(segment - yaw)) \
            <= nav2_legs.COLLINEAR_RAD, station_id
        # and the goal is therefore FURTHER along that segment's own
        # line than its end is, which is what "past the point" means
        assert math.dist(tail, bay.goal) > math.dist(tail, bay.end)


def test_no_other_legs_goal_moves_off_its_own_end():
    """One class aims past its end. Every other leg sends what it ends on."""
    seen = set()
    for station_id in sorted(STATIONS):
        for start in (F1_SPAWN, (-13.0, 4.25), (-7.0, -4.25)):
            poly = _drivable(start, station_id)
            if poly is None:
                continue
            for leg in nav2_legs.plan_legs(poly):
                seen.add(leg.klass)
                if leg.klass == nav2_legs.STATION_SPUR:
                    continue
                assert leg.goal == (float(leg.end[0]), float(leg.end[1])), \
                    (station_id, leg.klass)
    assert seen == set(nav2_legs.CLASS_TREE)


def test_the_bay_clearance_is_measured_off_the_floor_the_sdf_paints():
    """The room behind each station point, and it is READ and not assumed.

    S1 (-13.000, 4.250) is approached on -pi/2, so the ray runs SOUTH
    down x = -13.000. warehouse_ver3.sdf's rack rows either side of that
    bay are RackNW1 (line 310: pose -15.750, line 313: size 0.500 ->
    x in [-16.000, -15.500]) and RackNW2 (line 326: pose -10.000, line
    329: size 1.000 -> x in [-10.500, -9.500]); neither contains
    x = -13.000, and neither do their RackSW twins - the bay is cut
    RIGHT THROUGH (stations.py, "THE STATIONS ARE IN OPEN CROSS-AISLES").
    The first box the ray meets is AnnexA (line 518: pose -13.500
    -16.000, line 521: size 2.000 4.000 -> x in [-14.500, -12.500],
    y in [-18.000, -14.000]), whose north face is y = -14.000:
    4.250 - (-14.000) = 18.250 m.

    S4 (-7.000, -4.250) is approached on +pi/2 and the ray runs NORTH
    down x = -7.000, clear of RackSW3/RackNW3 (pose -4.250, size 0.500)
    and of RackSW2/RackNW2, to WallNorth (line 255: pose y 14.100, line
    256: size y 0.200), inner face y = 14.000: 14.000 - (-4.250) =
    18.250 m.

    The shallow bays are the annex's four, whose backs the SDF paints at
    y = -17.900 (BayS9Back and its three siblings): 3.000 m. That is the
    number the bias is bounded by, and it is 16 times it.
    """
    assert nav2_legs.bay_clearance_m("S1") == pytest.approx(18.250, abs=1e-9)
    assert nav2_legs.bay_clearance_m("S4") == pytest.approx(18.250, abs=1e-9)
    tightest = min(nav2_legs.bay_clearance_m(s) for s in STATIONS)
    assert tightest == pytest.approx(3.000, abs=1e-9)
    assert tightest - nav2_legs.LEAD_OVERHANG_M == pytest.approx(1.600,
                                                                abs=1e-9)
    for station_id in STATIONS:
        room = (nav2_legs.bay_clearance_m(station_id)
                - nav2_legs.LEAD_OVERHANG_M)
        assert room >= nav2_legs.ARRIVE_BIAS_M, station_id


def test_the_leading_overhang_is_the_derived_footprints_own_number():
    """1.400 m is not a guess: it is the footprint nav2 is configured with.

    The derivation copies the donor's costmap footprint through
    unchanged, so the donor is the one file that has to agree - and it
    is the tracked one.
    """
    import ast
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    donor = os.path.normpath(os.path.join(
        here, os.pardir, os.pardir, "m5_ver3", "nav2.yaml"))
    polygons = []
    with open(donor, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith("footprint:"):
                polygons.append(ast.literal_eval(
                    stripped.split(":", 1)[1].strip().strip('"')))
    assert polygons, "the donor nav2.yaml declares no footprint"
    for polygon in polygons:
        assert max(x for x, _y in polygon) == pytest.approx(
            nav2_legs.LEAD_OVERHANG_M, abs=1e-9)


def test_a_bay_that_cannot_take_the_bias_is_refused_by_name(monkeypatch):
    """No silent shrink: the leg is not built at all.

    S9's bay is 3.000 m deep and the truck reaches 1.400 m past its own
    origin into it, so 1.600 m is everything there is. A bias of 1.700
    does not quietly become 1.600 - it is a floor the vehicle does not
    fit on, and the honest answer is a refusal that names the station
    and shows its arithmetic.
    """
    poly = _drivable(F1_SPAWN, "S9")
    assert poly is not None
    monkeypatch.setattr(nav2_legs, "ARRIVE_BIAS_M", 1.7)
    with pytest.raises(nav2_legs.Nav2LegsError) as excinfo:
        nav2_legs.plan_legs(poly)
    said = str(excinfo.value)
    assert "S9" in said
    assert "3.000" in said and "1.400" in said
    assert "1.600" in said and "1.700" in said


def test_a_bias_the_bay_can_take_is_not_refused(monkeypatch):
    """The other side of the same boundary, so the refusal is a boundary."""
    poly = _drivable(F1_SPAWN, "S9")
    monkeypatch.setattr(nav2_legs, "ARRIVE_BIAS_M", 1.5)
    bay = nav2_legs.plan_legs(poly)[-1]
    assert math.dist(bay.goal, bay.end) == pytest.approx(1.5, abs=1e-9)
