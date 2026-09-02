#!/usr/bin/env python3
"""nav2_legs.py - a granted polyline becomes a queue of NavigateToPose
goals, and each one knows which controller drives it.

    python3 m6_ver2/nav2_adapter/nav2_legs.py --selftest

NO ROS IN THIS FILE. It is arithmetic over the points m6/ipc/route.py
hands out, so a test can reach everything that could be WRONG about the
split without a simulator; nav2_adapter_node.py is the shell that sends
the goals.

WHY THERE ARE LEGS AT ALL, AND WHY THEY ARE NOT NODES (Decision 2).
Three shapes were weighed and two rejected:

  ONE GOAL TO THE FAR END lets SmacPlannerHybrid pick its own corridor.
  The traffic ledger granted a SPECIFIC polyline; a freespace shortcut
  through an ungranted aisle breaks the fleet's floor model, and the
  fleet has no way to notice.

  NavigateThroughPoses keeps the corridor but is ONE action, one
  behaviour tree and therefore ONE controller for the whole route - the
  tree travels in the goal's `behavior_tree` field. That kills the
  per-leg controller rule below, which is the whole reason a spur is
  driven differently from an aisle.

  ONE GOAL PER GRAPH NODE keeps both and makes the truck decelerate into
  every node on the way. Rejected as the steady state; kept as the
  mechanism, which is what a LEG is: the maximal run of nodes the truck
  can drive without changing its mind.

A LEG IS A MAXIMAL NEAR-COLLINEAR RUN, SPLIT AT JUNCTION TURNS AND AT
THE STATION SPUR FOOT. The second rule is not implied by the first and
it earns its place on a real case: a truck standing 0.20 m off the ring
centreline ON a spur's own x plans [pose, spur foot, station] - three
points on one straight line - and a split made only at turns would hand
the whole thing to the transit tree and lose the station goal checker.
  THE SPUR FOOT, SINGULAR: the foot of the station this route ENDS at,
and not every foot it drives past. Eleven of the twelve spur feet are
ordinary ring nodes to a truck on its way somewhere else, and splitting
at them would put a goal boundary every four metres down the north leg -
which is the per-node behaviour this whole file exists to remove.

THE PREEMPT POINT IS A DISTANCE AND ITS REASON IS A DIFFERENT FILE'S
NUMBER. See PREEMPT_AT_M.
"""
import argparse
import collections
import math
import sys

import _donors                                            # noqa: F401

import follower                                           # noqa: E402
import route                                              # noqa: E402
from stations import STATIONS                             # noqa: E402


class Nav2LegsError(ValueError):
    """A polyline, a leg class or a distance this file will not guess at."""


# ----------------------------- the classes -----------------------------

#: The final leg, whose end is a station point. Driven by RPP against
#: the 0.25 m `station_goal_checker`: it is the only leg that runs to
#: actual completion, and it is the one that ends in a bay.
STATION_SPUR = "station spur"
#: The first leg of a route whose start pose stands on a station point -
#: the DEAD-ASTERN start. A station is reached forks-first, so the way
#: out of it is backwards; m6/ipc/nav_core.py's header has the
#: measurement that settled it (leaving S10, 2026-08-13: a committed
#: minimum-radius arc put the back scanner 0.938 m off rack B, inside
#: the 1.0 m protective field).
SPUR_EXIT = "spur exit"
#: Everything else. Aisle running, on the ring, the spine or the pick.
TRANSIT = "transit"

#: LEG CLASS -> (controller name, the config.yaml key holding its tree).
#: This generalises m5v3's per-origin rule (G5 Task 7) to per-leg, and
#: it is deliberately shaped like drive_goal.CONTROLLER_TREE - one
#: table, two controller names, and a refusal on a third. The tree FILE
#: PATHS are not here: they live in the per-truck
#: m6_ver2/vehicles/fN/config.yaml nav block, because the path is a
#: deployment fact and the mapping is a control fact.
#:
#: TWO TREES AND ONE CONTROLLER, SINCE SPEC_ADAPTER.md AMENDMENTS 4
#: (G1-C4, 2026-09-02, AMR-DEC-005 extended). The transit row used to
#: read ("mppi", "nav.bt_xml") and it was measured wrong: AMENDMENTS 3
#: made every transit goal bidirectional, so every transit leg is driven
#: FORKS-FIRST, which on this model is nav2-reverse - the reversal-heavy
#: class AMR-DEC-005 had already taken off MPPI on the m5_ver3 side.
#: Run 7 then found m5v3's creep fingerprint verbatim on m6v2's transit
#: legs: four plateaus with means 0.0816-0.0905 m/s inside
#: EVIDENCE_STALL's 0.0777-0.0901 band, the direction-hold node holding
#: flip plans through them, the orbit at the leg end, and 6 BLOCKEDs in
#: 10 legs. The spec's own sanctioned fallback - RPP for all legs - was
#: taken. MPPI STAYS CONFIGURED and its tree stays derived: it is
#: bt_navigator's `default_nav_to_pose_bt_xml` and one table row from
#: being driven again, because the counter-evidence is real (m5v3's
#: clean 17 m spawn straight, MPPI 8/8 against RPP 7/8) and RPP's
#: unrecovered lateral-excursion class, ~1 in 8 on long straights with
#: no cross-track term, is NAMED rather than solved. Its net is the
#: closing watchdog and the fleet's own requeue.
#:   THE TREE STILL CARRIES TWO DECISIONS, not one: which controller its
#: ControllerSelector defaults to, and - since M6V2-G1-B5 - which goal
#: checker its FollowPath names. That second one is why there are still
#: THREE trees behind two rows. The station spur runs into a BAY and is
#: the only leg allowed to complete, so it names the 0.25 m
#: `station_goal_checker`; the spur exit and the transit get preempted
#: 1.5 m from their ends and keep the 0.60 m one. A separate tree is
#: what says that, because a goal checker is an attribute of a
#: behaviour tree and there is no other door.
#:   AND IT IS THE ONE TREE CHANGE LEFT IN A ROUTE. nav2 refuses a
#: preemption that changes the BT XML, so a tree boundary costs a
#: cancel and a stop (nav2_adapter_node._advance_to). With the transit
#: row on the RPP tree the only such boundary is the last one, into the
#: bay - the spur-exit-to-transit boundary, which used to stop the truck
#: at the mouth of every undock, is now a true preemption.
#:   AND EVERY ROW NAMES ONE. Two goal checkers are declared in the
#: derived nav2.yaml, and nav2_controller only falls back to "the only
#: plugin loaded" when there IS only one - see
#: m6_ver2/tools/instantiate_truck.py STATION_CHECKER, which read that
#: branch out of the installed binary. A tree that named no checker
#: would abort every FollowPath on this stack.
CLASS_TREE = collections.OrderedDict((
    (STATION_SPUR, ("rpp", "nav.bt_xml_station")),
    (SPUR_EXIT, ("rpp", "nav.bt_xml_rpp")),
    (TRANSIT, ("rpp", "nav.bt_xml_rpp")),
))

# ----------------------------- the numbers -----------------------------

#: WHERE THE NEXT LEG IS SENT, in metres of BELIEVED distance still to
#: run on this one. `navigate_to_pose` is a single-goal server, so nav2
#: displaces the running goal itself and F4 Task 3's `Preempt`
#: instrument already measured what that switch costs (a ~0.05 s class
#: gap in the command stream).
#:   1.5 AND NOT 1.0, AND THE REASON WAS MPPI'S. Inside
#: MPPI_GOAL_THRESHOLD_M the GoalCritic takes over as a point
#: attraction and the path critics hand off; a leg end reached inside
#: that would be driven as if it were a destination - decelerated into,
#: hooked round - which is exactly the per-node behaviour legs exist to
#: remove. P sits OUTSIDE it, so an intermediate leg end never enters
#: the endgame at all.
#:   AMENDMENTS 4 MOVED THE LEGS AND NOT THIS NUMBER, because RPP's own
#: endgame is SHORTER than MPPI's on every measure the derived nav2.yaml
#: declares: `approach_velocity_scaling_dist` 1.0 m and
#: `max_lookahead_dist` 0.95 m. 1.5 clears 1.4, 1.0 and 0.95 alike, so
#: the largest of the three is still what binds - and it is still MPPI's,
#: which is why the constant below stays.
PREEMPT_AT_M = 1.5
#: MPPI's own GoalCritic `threshold_to_consider`, m5_ver3/nav2.yaml.
#: Carried here as the REASON for the number above and pinned by test;
#: it is not a parameter of this file and changing it here changes
#: nothing in nav2. It outlived AMENDMENTS 4 on purpose: no leg names
#: MPPI any more, but it is still the widest endgame this stack has
#: configured and therefore still the one P has to clear.
MPPI_GOAL_THRESHOLD_M = 1.4

#: HOW STRAIGHT "STRAIGHT ON" IS. The waypoint graph's own turns are all
#: right angles, and the only non-right angle a route ever carries is
#: the prepended pose's approach onto its entry node - a truck standing
#: off the centreline by its own parking error. 15 deg is comfortably
#: clear of 90 and admits a truck up to about a quarter of a leg length
#: off line without manufacturing a leg out of its parking error.
COLLINEAR_RAD = math.radians(15.0)

#: WHERE THE TWO CANDIDATE HEADINGS ARE THE SAME ROTATION AWAY, and it
#: is arithmetic rather than a tuning knob. The two differ by pi, so for
#: any delta in (-pi, pi], |wrap(delta + pi)| == pi - |delta| EXACTLY:
#: "whichever of the two is the smaller rotation" is the single test
#: |delta| < pi/2 - no second atan2, and no race between two magnitudes
#: that differ by an ulp.
QUARTER_TURN_RAD = math.pi / 2.0

#: HOW WIDE THE TIE IS, AND IT IS A BAND AND NOT A POINT (defect D8,
#: run6). At exactly a quarter turn the criterion above has NO OPINION,
#: and on this floor that is not a corner case - it is EVERY junction.
#: The waypoint graph's turns are all right angles and every spur meets
#: its ring leg at one, so a truck standing at a spur mouth is at pi/2
#: to the leg it is about to drive BY CONSTRUCTION, and what decides it
#: is then the third decimal place of the localiser.
#:   MEASURED, run 6: the five yaws the truck actually stood at when a
#: ring leg was dispatched out of the S1 mouth were -1.550, -1.474,
#: -1.565, -1.581 and -1.574 against a bay heading of -1.5708 - up to
#: 0.097 rad out. The one that landed 0.021 rad on the wrong side of
#: pi/2 was handed the travel direction, planned the turnaround, left
#: the corridor to (-13.05, 11.35) and died on the watchdog: "blocked:
#: no progress - best 13.06 m, 30 s without closing". That is D7's own
#: defect reached through D7's own rule.
#:   SO THE BAND IS COLLINEAR_RAD - the same tolerance this file already
#: grants a truck's parking error when it asks whether two segments are
#: the same straight line - and inside it the FLIP wins. Not by coin
#: toss: the flip is the sense the truck is already driving in (it
#: leaves a bay forks-first and runs the ring forks-first), and nav2's
#: own direction-hold node refuses a fresh plan that flips the driving
#: direction under way - "fresh plan flips the driving direction at
#: |v| = 0.272 m/s ... keeping the accepted plan", bt_navigator, run 6 -
#: so a goal that demands the other sense mid-leg is a goal that will
#: not be driven at all.
TIE_BAND_RAD = COLLINEAR_RAD

#: The one comparison leg_yaw makes. Above this the pi-flip wins.
FLIP_ABOVE_RAD = QUARTER_TURN_RAD - TIE_BAND_RAD

#: HOW CLOSE COUNTS AS STANDING ON A STATION. follower.ARRIVE_M is the
#: radius at which this same estimate LATCHED the arrival, so a truck
#: that has just arrived is by construction inside it and no other
#: number would agree with the one that put it there.
ON_STATION_M = follower.ARRIVE_M

#: ONE LEG, DECIDED. `points` is the whole run (>= 2 points), `end` is
#: what goes in the NavigateToPose goal, `klass` is the row of
#: CLASS_TREE that names the tree, and `final` says whether this leg is
#: allowed to run to completion.
Leg = collections.namedtuple(
    "Leg", "points start end klass controller tree_key final")


_SPUR_FEET = {}


def spur_feet():
    """{station id: the one graph node its spur leaves from}.

    READ OFF THE GRAPH AND NOT RE-SPELLED. route.build_graph() links
    each station to exactly one node and the rule for which one ("the
    ring leg the bay opens onto, and the sign of the station's y says
    which") lives there. Repeating it here would be a second opinion
    about the floor, and the day a bay is re-cut it would be the copy
    that stayed right.
    """
    if not _SPUR_FEET:
        graph = route.build_graph()
        for station_id, station in STATIONS.items():
            point = (station["x"], station["y"])
            neighbours = graph.get(point) or ()
            if len(neighbours) != 1:
                raise Nav2LegsError(
                    "station {} has {} edges in route.build_graph() and a "
                    "spur has exactly one: this is not a spur any more, "
                    "and the leg classifier cannot say where it starts"
                    .format(station_id, len(neighbours)))
            _SPUR_FEET[station_id] = tuple(next(iter(neighbours)))
    return dict(_SPUR_FEET)


def station_at(xy, radius_m=ON_STATION_M, stations=STATIONS):
    """The station whose point `xy` stands on, or None.

    `stations` is an argument so that leg_yaw() below can ask WHICH
    station and then ask that same table for its heading. A lookup that
    took the id from one table and the yaw from another would be two
    opinions about the floor the day a bay moves.
    """
    x, y = float(xy[0]), float(xy[1])
    for station_id, station in stations.items():
        if math.dist((x, y), (station["x"], station["y"])) <= radius_m:
            return station_id
    return None


def controller_for(klass):
    """(controller name, config key of its tree) for a leg class.

    REFUSED BY NAME ON AN UNKNOWN CLASS, and refused HERE rather than at
    the action server: a goal carrying a `behavior_tree` bt_navigator
    cannot open is a failure forty metres into a drive, and the operator
    reads it as a nav fault instead of as a table with a typo in it.
    """
    if klass not in CLASS_TREE:
        raise Nav2LegsError(
            "{!r} is not a leg class. This file knows exactly three, "
            "nav2.yaml declares two controller plugins and since "
            "AMENDMENTS 4 the table names one of them: {}".format(
                klass, ", ".join(
                    "{} -> {}".format(name, CLASS_TREE[name][0])
                    for name in CLASS_TREE)))
    return CLASS_TREE[klass]


#: LEG CLASSES THAT ARE DRIVEN TO THEIR OWN GOAL rather than handed
#: over at P. It is a tuple and not a bare comparison because the day a
#: second class earns a stop, the place to say so is here and not
#: inside an `if`. See runs_to_its_goal() for the measurement.
DRIVEN_TO_ITS_GOAL = (SPUR_EXIT,)


def runs_to_its_goal(leg):
    """Is this leg driven to its own goal instead of handed over at P?

    TWO CLASSES OF LEG, FOR TWO DIFFERENT REASONS.

    THE FINAL LEG, always, and that is Decision 2: there is nothing to
    hand over to, and it is the one leg whose completion the goal
    checker is allowed to decide.

    THE SPUR EXIT, and that is DEFECT D10 (runs 8 and 9, 2026-09-02).
    AMENDMENTS 4 put the spur exit and the transit after it on ONE
    tree, so for the first time nav2 allowed a hand-over at a bay
    MOUTH - and took it:

      adapter  leg 1/5 spur exit end=(-13.00, 10.00) goal_yaw=-1.571
                                 truck_yaw=-1.565 turn=-0.006
      adapter  leg 2/5 transit   end=( 0.00, 10.00) goal_yaw=-3.142
                                 truck_yaw=-1.544 turn=-1.598
      bt_navigator "Received goal preemption request"

    The truck was doing 0.30 m/s and was handed a goal a QUARTER TURN
    away, which by construction is what a mouth hands you: a spur meets
    its ring leg at a right angle and the bay fixes the heading it is
    left on (D5). It did not stop. Ground truth ran (-13.35, 9.12) ->
    (-12.60, 10.00) -> (-11.83, 10.75) -> (-10.50, 11.80) ->
    (-8.58, 12.36): a sweeping arc 2.36 m north of the ring centreline,
    into the rack line, where the LEFT protective field demanded
    (`PF b/r/l=T/T/F`), Motor latched False and the order died.
      THE BELIEF WAS NOT THE DEFECT - the estimate held median 0.102 m,
    p95 0.112 m, max 0.187 m against ground truth all session. Nor was
    it one bad plan: a goal a quarter turn away can be reached driving
    either way, the planner changes its mind every replan, and
    bt_navigator's direction-hold node refused eleven fresh plans across
    that arc ("fresh plan flips the driving direction at |v| = 0.301 m/s
    (hold_speed 0.050), -1 -> +1, 12.59 m of the accepted plan left ...
    keeping the accepted plan"). So the path being tracked stayed the
    one built at the mouth while the truck drove off it.

    AND IT IS NOT A DOOR, WHICH IS RUN 9's OWN LESSON. The first cut of
    this fix routed the mouth through nav2's cancel-then-send door, on
    the theory that the door was what used to stop the truck there. It
    is not:

      bt_navigator 1788327959.428  "Client requested to cancel the goal"
      bt_navigator 1788327959.439  "Begin navigating from (-4.13, 1.31)"

    ELEVEN MILLISECONDS. nav2 answers a cancel at once, the adapter
    sends at once, and the truck coasts through the boundary at whatever
    it was doing - 0.273 m/s on the next direction-hold line - and the
    same arc happened again to the metre. BOTH DOORS HAND OVER AT P
    WITH THE TRUCK MOVING; only a leg that runs to its own goal stops
    it, because only then does RPP's approach_velocity_scaling_dist
    (1.0 m) get to bring it down. nav2 then reports SUCCEEDED for a
    non-final leg and defect D9's branch starts the next one from a
    standstill - where the direction hold accepts every plan.

    THE COST, STATED: one stop per undock, of about a second, at a
    corner a 3.815 m tricycle with a 1.25 m turning radius was going to
    slow down for anyway.
    """
    return leg.final or leg.klass in DRIVEN_TO_ITS_GOAL


def drives_through(leg_from, leg_to):
    """May the handover from `leg_from` into `leg_to` be a PREEMPTION?

    True: nav2 displaces the running goal itself. False: the adapter
    must use nav2's own cancel-then-send door
    (nav2_adapter_node._advance_to). THE POLICY LIVES HERE, in the pure
    module, because it is a statement about the leg classes; the shell
    only owns the mechanics of the two doors.

    ONE REASON, AND IT IS NAV2's AND NOT OURS: "Preemption with a new
    BT is invalid since it would require cancellation of the previous
    goal instead of true preemption" (bt_navigator 1.3.12, measured
    2026-09-02). Since AMENDMENTS 4 that is exactly one boundary per
    route, the last one, into a bay.
      AND NEITHER DOOR IS A STOP - see runs_to_its_goal, which is where
    D10 lives. A boundary the truck must not take at speed is not a
    door problem: it is a leg that has to be driven to its goal.
    """
    return leg_from.tree_key == leg_to.tree_key


def _clean(polyline):
    """The polyline with its zero-length segments dropped.

    NOT COSMETIC. route.plan_route prepends the pose and then drops the
    entry node only when the pose is nearer the SECOND node, so a truck
    standing exactly on its spawn node - which is every truck at boot -
    is handed that node twice. A zero-length segment has no heading, and
    a split that asked one for its heading would split there every time.
    """
    points = []
    for raw in polyline:
        try:
            point = (float(raw[0]), float(raw[1]))
        except (TypeError, ValueError, IndexError):
            raise Nav2LegsError(
                "the polyline carries {!r}, which is not an (x, y) "
                "point".format(raw))
        if not (math.isfinite(point[0]) and math.isfinite(point[1])):
            raise Nav2LegsError(
                "the polyline carries a non-finite coordinate {!r}: a "
                "route is refused for this at the door and must never "
                "reach the leg runner".format(raw))
        if points and math.dist(points[-1], point) == 0.0:
            continue
        points.append(point)
    return points


def leg_length_m(points):
    """How far the truck drives on this leg, along its own polyline."""
    return sum(math.dist(points[index], points[index + 1])
               for index in range(len(points) - 1))


def _merge_short(chunks):
    """Chunks with every non-final run shorter than P folded forward.

    A LEG BORN INSIDE THE PREEMPT DISTANCE IS NOT A LEG (defect D9,
    run6). PREEMPT_AT_M is the distance at which a leg is handed over,
    so a run shorter than it is dispatched and superseded in the same
    tick - two NavigateToPose goals at a SINGLE-goal server inside
    41 ms - and bt_navigator answered that pair with one line:

        Begin navigating from (-0.08, -0.10) to (-0.08, -0.15)
        Received goal preemption request
        Begin navigating from (-0.08, -0.10) to (-4.08, -0.16)
        Goal succeeded                     <- 19 ms later, 4 m short

    The 0.047 m goal was inside the 0.60 m goal checker before it was
    sent, so the tree returned SUCCESS against the label of the goal
    that had just displaced it, and the truck stood on its spawn node
    until the adapter's own watchdog called it - twice, on 4 m of empty
    aisle.
      WHERE 0.047 m OF LEG COMES FROM: route.plan_route prepends the
    truck's pose and keeps the entry node whenever the pose is nearer
    THAT than the second node, so a truck standing just off its spawn is
    handed both - and 0.047 m of parking error pointing north followed
    by a ring leg pointing east is a TURN, which is exactly what
    split_legs splits at. This is D5's sentence ("the parking error is
    not a leg") stated where it can be enforced for every route and not
    only for the one out of a bay.
      FORWARD AND NOT BACKWARD, because the shared vertex is the next
    leg's start and the goal must stay on the LAST segment - the ring
    leg's heading, not the parking error's. The final chunk has nothing
    after it and is left alone: the final leg is never preempted
    (should_preempt), so being short costs it nothing.
    """
    merged = []
    for points in chunks:
        if merged and leg_length_m(merged[-1]) < PREEMPT_AT_M:
            merged[-1] = merged[-1] + list(points[1:])
        else:
            merged.append(list(points))
    return merged


def split_legs(polyline):
    """The polyline as a list of point-lists, one per leg.

    A vertex ends a leg when the heading turns by more than
    COLLINEAR_RAD, or when the vertex is a station spur foot. The vertex
    itself belongs to BOTH legs: it is the end of one goal and the start
    of the next, which is what makes the queue continuous.

    Then every non-final run shorter than PREEMPT_AT_M is folded into
    the one after it - see _merge_short, which is defect D9.
    """
    points = _clean(polyline)
    if len(points) < 2:
        if len(polyline) < 2:
            raise Nav2LegsError(
                "a route of fewer than two points is not a polyline: "
                "{} given".format(len(polyline)))
        raise Nav2LegsError(
            "the polyline has no length - every point is the same point "
            "{!r}, so there is nothing to drive".format(points[0]))
    # THE FOOT OF THIS ROUTE'S OWN STATION AND OF NO OTHER. See the
    # header: a foot the truck merely drives past is a ring node.
    final_station = station_at(points[-1])
    feet = set()
    if final_station is not None:
        feet.add(spur_feet()[final_station])
    legs, current = [], [points[0]]
    for index in range(1, len(points)):
        current.append(points[index])
        if index == len(points) - 1:
            break
        before = math.atan2(points[index][1] - points[index - 1][1],
                            points[index][0] - points[index - 1][0])
        after = math.atan2(points[index + 1][1] - points[index][1],
                           points[index + 1][0] - points[index][0])
        turns = abs(follower.norm_ang(after - before)) > COLLINEAR_RAD
        if turns or points[index] in feet:
            legs.append(current)
            current = [points[index]]
    legs.append(current)
    return _merge_short(legs)


def classify(leg_points, final):
    """The class of one leg, from the geometry and stations.STATIONS.

    PRECEDENCE, STATED: a leg that both leaves a station and ends at one
    is a STATION SPUR. The end governs, because the end is what picks
    the goal checker the arrival is decided against.

    A SPUR EXIT IS DECIDED BY WHERE IT STARTS AND NOT BY ITS ORDINAL,
    and that is defect D5's own sentence (run4, 2026-09-02). The route
    the fleet hands back after a pick begins with the truck's POSE -
    0.245 m off the bay, its own arrival error - and then the STATION
    POINT itself, so the FIRST leg is that 0.245 m of parking error and
    the real exit is the SECOND one. Asking "is this leg first" gave the
    class to the parking error and left the bay-to-mouth leg a TRANSIT:
    the transit tree, the 0.60 m goal checker, and - through leg_yaw -
    a goal heading that demanded a 180 degree turn inside a dead-end
    spur (at the time that was also MPPI's tree; AMENDMENTS 4 has since
    moved the transit row onto RPP, which changes the controller and
    changes nothing about the heading this paragraph is here for). The
    truck drove it, left the aisle, and latched a protective field.
      A leg that ENDS on a station is not leaving one, whatever it
    started on: that is the degenerate leg above, and it is a transit
    of the truck's own parking error.
    """
    if final and station_at(leg_points[-1]) is not None:
        return STATION_SPUR
    if (station_at(leg_points[0]) is not None
            and station_at(leg_points[-1]) is None):
        return SPUR_EXIT
    return TRANSIT


def plan_legs(polyline):
    """The whole leg queue for a released polyline.

    THE FIRST POINT IS THE POSE. Both doors that reach this file prepend
    it - route.plan_route does it so the first segment starts under the
    truck instead of snapping it sideways onto the graph, and
    vda_agent._send_route does it for the same reason on an extension -
    so `polyline[0]` is where the truck is and the spur-exit test has
    something to read.
    """
    chunks = split_legs(polyline)
    legs = []
    for index, points in enumerate(chunks):
        klass = classify(points, final=(index == len(chunks) - 1))
        controller, tree_key = controller_for(klass)
        legs.append(Leg(points=points, start=points[0], end=points[-1],
                        klass=klass, controller=controller,
                        tree_key=tree_key,
                        final=(index == len(chunks) - 1)))
    return legs


def leg_yaw(leg, current_yaw=None, stations=STATIONS):
    """The heading the goal at this leg's end is approached on.

    A `Leg` carries its points and no heading, and SmacPlannerHybrid is
    HEADING-AWARE: the goal's orientation shapes the whole plan, so a
    goal sent without one is a goal sent with yaw 0 - which on this
    floor is a quarter turn out of every aisle.

    THREE ANSWERS, AND WHICH ONE APPLIES IS THE SAME QUESTION classify()
    ALREADY ASKED. A leg that ends ON a station ends at the BAY's own
    approach heading, because that is the heading the truck has to
    arrive on and the bay is not free to choose it. A SPUR EXIT ends on
    that SAME heading - the one it is standing on - because a spur is a
    dead end and the truck cannot turn round in it. Every other leg -
    every TRANSIT - ends pointing along itself OR along its own
    reverse, whichever is the smaller rotation from where the truck is
    pointing NOW, which is what `current_yaw` is for.

    THE TRANSIT ROW IS DEFECT D7, MEASURED (run5, 2026-09-02), AND IT IS
    D5's OWN MISTAKE ONE FLOOR UP. "Along the last segment" is ONE
    heading for a vehicle that drives both ways: this model carries its
    forks at body -x (SPEC_ADAPTER.md Decision 1's sign audit -
    forks-first is NEGATIVE linear.x), so a goal yaw equal to the travel
    direction is a goal that says COUNTERWEIGHT FIRST. The truck came
    out of S1 northbound on the bay's heading, stood at the spur mouth
    (-13.0, 10.0) on -1.75 with its forks north, and was handed goal yaw
    0.0 for the eastbound ring leg - a demand to end up pointing
    forks-WEST while driving east. Smac planned the turnaround: out of
    the corridor to (-14.73, 8.65), north past the ring centreline to
    (-12.13, 11.53), back to (-12.51, 9.63), and the closing watchdog
    fired at 30 s. Six BLOCKEDs in one order and not one of them was a
    floor that was not clear.
      A FORKLIFT DOES NOT TURN ROUND TO GO SOMEWHERE. It drives the
    other way, and the two goal poses that mean "drive along this leg"
    differ by exactly pi. The rule picks the one already under the
    truck; see FLIP_ABOVE_RAD for why that is one comparison and where
    its tie goes.

    WHY THE BAY'S TWO ROWS ARE NOT BIDIRECTIONAL. A station heading is
    not a preference about which end goes first, it is the pose the bay
    admits - 4.00 m wide, entered off the ring band, with the standoffs
    in stations.py measured against one approach. The truck may drive it
    forwards or backwards; it may not arrive rotated.

    THE SPUR EXIT ROW IS DEFECT D5, MEASURED (run4, 2026-09-02). The
    exit's last segment points north (+1.5708) and the truck is standing
    at the bay on -1.5708, so "along itself" asked for a 180 degree turn
    inside a 5.75 m dead-end spur - and SmacPlannerHybrid, which is
    heading-aware, planned one: the truck swung to (-11.32, 7.87) at yaw
    2.51, cusped, reversed north-west out of the aisle to (-13.59,
    11.45) and the watchdog fired at 30 s without closing; a repeat put
    it at (-10.42, 12.36) and a protective field latched Motor False.
    The truck backs into a bay and drives out of it, or drives in and
    backs out; either way its BODY yaw does not change in the spur.

    THE LAST SEGMENT AND NOT THE WHOLE LEG. A leg is near-collinear by
    construction (COLLINEAR_RAD), so the two are the same to within 15
    degrees - but only the last segment is the one the goal sits on, and
    a leg whose last segment has no length has no heading at all rather
    than a heading of zero. That case is refused: `_clean` drops
    zero-length segments before any leg is made, so a leg that has one
    was not built by split_legs and the atan2 would be an invention.
    """
    station = station_at(leg.end, stations=stations)
    if station is None and leg.klass == SPUR_EXIT:
        # THE BAY BEING LEFT, and only for a leg this file already
        # called a spur exit: a transit that merely passes a bay keeps
        # its own heading.
        station = station_at(leg.start, stations=stations)
    if station is not None:
        try:
            return float(stations[station]["yaw"])
        except (KeyError, TypeError, ValueError):
            raise Nav2LegsError(
                "station {} declares no usable approach heading, and a "
                "bay's heading is the one thing a spur leg cannot work "
                "out for itself".format(station))
    tail = leg.points[-2] if len(leg.points) > 1 else leg.start
    if math.dist(tuple(tail), tuple(leg.end)) == 0.0:
        raise Nav2LegsError(
            "the leg ending at {!r} has no last segment, so it has no "
            "heading: split_legs drops zero-length segments, and a leg "
            "carrying one did not come from it".format(leg.end))
    direction = math.atan2(leg.end[1] - tail[1], leg.end[0] - tail[0])
    if current_yaw is None:
        raise Nav2LegsError(
            "the transit leg ending at {!r} was asked for its goal "
            "heading without being told which way the truck is pointing, "
            "and this file will not guess: a transit goal is the travel "
            "direction OR its pi-flip, and only the truck's own yaw says "
            "which (defect D7)".format(leg.end))
    try:
        delta = follower.norm_ang(direction - float(current_yaw))
    except (TypeError, ValueError):
        raise Nav2LegsError(
            "the truck's current yaw is {!r}, which is not an angle, and "
            "a goal heading decided off it would be a heading decided at "
            "random".format(current_yaw))
    if not math.isfinite(delta):
        raise Nav2LegsError(
            "the truck's current yaw is {!r}: a goal heading decided off "
            "a non-finite belief is a goal sent at random"
            .format(current_yaw))
    if abs(delta) >= FLIP_ABOVE_RAD:
        return follower.norm_ang(direction + math.pi)
    return direction


def should_preempt(distance_to_end_m, runs_to_its_goal):
    """Is it time to send the next leg?

    THE ARGUMENT USED TO BE `final` AND IT IS NOW THE ANSWER
    runs_to_its_goal() GIVES - defect D10. The final leg was the only
    leg driven to its own goal until run 9 measured what a hand-over at
    a bay mouth costs; the caller asks this file which legs those are
    rather than reading one field of the tuple, so a new class joining
    them is one line up there and none down here.
    """
    try:
        distance = float(distance_to_end_m)
    except (TypeError, ValueError):
        raise Nav2LegsError(
            "the distance to the leg end is {!r}, which is not a "
            "number".format(distance_to_end_m))
    if not math.isfinite(distance):
        raise Nav2LegsError(
            "the distance to the leg end is {!r}: a preempt decided off "
            "a non-finite belief is a goal sent at random".format(distance))
    if runs_to_its_goal:
        return False
    return distance < PREEMPT_AT_M


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_nav2_adapter_legs.py is the real suite - it runs the
    split over route.py's own planner output - and this is the version
    an operator can run on the rig, in the shell they are already in,
    without pytest.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    check("the preempt point sits OUTSIDE the widest endgame configured "
          "({:.2f} m > {:.2f} m)".format(PREEMPT_AT_M,
                                         MPPI_GOAL_THRESHOLD_M),
          PREEMPT_AT_M > MPPI_GOAL_THRESHOLD_M)

    feet = spur_feet()
    check("every one of the {} stations has exactly one spur foot on a "
          "ring leg".format(len(feet)),
          len(feet) == len(STATIONS)
          and all(abs(foot[1]) == 10.0 for foot in feet.values()))

    spawn = (-17.0, 10.0)
    legs = plan_legs(route.plan_route(spawn, "S5"))
    check("spawn -> S5 is a transit and a spur, and not ten goals",
          [leg.klass for leg in legs] == [TRANSIT, STATION_SPUR])
    check("the ring run is ONE leg of eight collinear nodes",
          len(legs[0].points) == 8)
    check("every leg is driven by rpp - the transit row moved there in "
          "AMENDMENTS 4",
          all(leg.controller == "rpp" for leg in legs))
    check("the spur runs the STATION tree and the transit the RPP one",
          legs[1].tree_key == "nav.bt_xml_station"
          and legs[0].tree_key == "nav.bt_xml_rpp")
    check("no leg class names MPPI or the primary tree, which stay "
          "configured for bt_navigator's default (AMENDMENTS 4)",
          not [row for row in CLASS_TREE.values()
               if row[0] == "mppi" or row[1] == "nav.bt_xml"])
    check("the spur ends on S5's own approach heading",
          abs(leg_yaw(legs[1]) - float(STATIONS["S5"]["yaw"])) < 1e-12)
    segment = math.atan2(legs[0].end[1] - legs[0].points[-2][1],
                         legs[0].end[0] - legs[0].points[-2][0])
    check("a transit leg ends pointing along its last segment when the "
          "truck is already pointing that way",
          abs(leg_yaw(legs[0], segment) - segment) < 1e-12)
    # D7: the same leg, a truck facing the other way, and the goal that
    # does NOT ask it to turn round in the aisle (run5, six BLOCKEDs).
    backwards = follower.norm_ang(segment + math.pi)
    check("and it ends pointing along its own REVERSE when that is the "
          "smaller rotation - a forklift drives both ways (D7)",
          abs(follower.norm_ang(leg_yaw(legs[0], backwards) - backwards))
          < 1e-12)
    check("the tie at a quarter turn goes to the flip, which is the spur "
          "mouth of a truck that parked perfectly (D7)",
          abs(follower.norm_ang(
              leg_yaw(legs[0], follower.norm_ang(segment + FLIP_ABOVE_RAD))
              - backwards)) < 1e-12)

    out = plan_legs(route.plan_route((7.0, 4.25), "S9"))
    check("leaving a station is a dead-astern SPUR EXIT",
          out[0].klass == SPUR_EXIT)
    check("and the only tree change left in the route is the last one, "
          "into the bay (AMENDMENTS 4)",
          [i for i in range(1, len(out))
           if out[i].tree_key != out[i - 1].tree_key] == [len(out) - 1])
    check("the bay MOUTH is driven to and not handed over - the truck "
          "does not take a quarter turn at 0.3 m/s (D10)",
          runs_to_its_goal(out[0]) and runs_to_its_goal(out[-1])
          and not any(runs_to_its_goal(leg) for leg in out[1:-1]))
    check("and nav2 itself objects to exactly one boundary, the bay's",
          [i for i in range(len(out) - 1)
           if not drives_through(out[i], out[i + 1])] == [len(out) - 2])
    check("and it leaves on S5's OWN heading - a spur is a dead end and "
          "the truck does not turn round in it (D5)",
          abs(leg_yaw(out[0]) - float(STATIONS["S5"]["yaw"])) < 1e-12)

    # THE ROUTE THE FLEET HANDS BACK AFTER A PICK: the pose 0.245 m off
    # the bay, then the bay itself, then the mouth. The parking error is
    # a leg and it must not take the spur exit's class with it (D5).
    parked = plan_legs([(-12.9968, 4.4952), (-13.0, 4.25), (-13.0, 10.0),
                        (-10.0, 10.0), (-7.0, 10.0)])
    exits = [leg for leg in parked if leg.klass == SPUR_EXIT]
    check("the parking error is not a leg of its own, and the leg it is "
          "folded into is the bay-to-mouth exit (D5, D9)",
          len(exits) == 1 and exits[0].start == (-12.9968, 4.4952)
          and exits[0].end == (-13.0, 10.0)
          and abs(leg_yaw(exits[0]) - float(STATIONS["S1"]["yaw"])) < 1e-12)
    check("no leg that can be preempted is born already inside P (D9)",
          all(leg_length_m(leg.points) >= PREEMPT_AT_M
              for leg in parked[:-1]))
    check("S5 -> S9 splits at every junction turn (five legs)",
          len(out) == 5 and out[-1].klass == STATION_SPUR)

    straight = plan_legs(route.plan_route((7.0, 12.0), "S5"))
    check("a straight run THROUGH a spur foot still splits there",
          len(straight) == 2 and straight[1].klass == STATION_SPUR)
    close = plan_legs(route.plan_route((7.0, 10.2), "S5"))
    check("... and from inside P it is ONE leg, the station spur, so the "
          "0.25 m checker still decides the arrival (D9)",
          len(close) == 1 and close[0].klass == STATION_SPUR)

    check("a doubled first point is not a leg boundary",
          len(split_legs([(0.0, 0.0), (0.0, 0.0), (5.0, 0.0)])) == 1)
    check("the preempt fires below P and not above",
          should_preempt(1.49, runs_to_its_goal=False)
          and not should_preempt(1.51, runs_to_its_goal=False))
    check("a leg that runs to its own goal is never preempted",
          not should_preempt(0.01, runs_to_its_goal=True))

    check("only the station spur names the station tree",
          [name for name, (_c, key) in CLASS_TREE.items()
           if key == "nav.bt_xml_station"] == [STATION_SPUR])
    check("every leg class names a tree key",
          all(key.startswith("nav.bt_xml")
              for _c, key in CLASS_TREE.values()))

    for bad, what in ((lambda: controller_for("freespace"),
                       "an unknown leg class"),
                      (lambda: plan_legs([(0.0, 0.0)]),
                       "a one-point polyline"),
                      (lambda: plan_legs([(1.0, 1.0), (1.0, 1.0)]),
                       "a polyline with no length"),
                      (lambda: should_preempt(float("nan"),
                                              runs_to_its_goal=False),
                       "a non-finite distance"),
                      (lambda: leg_yaw(legs[0]),
                       "a transit leg asked for a heading without the "
                       "truck's own yaw (D7)"),
                      (lambda: leg_yaw(legs[0], float("nan")),
                       "a transit heading decided off a non-finite yaw"),
                      (lambda: leg_yaw(Leg(points=[(0.0, 0.0), (0.0, 0.0)],
                                           start=(0.0, 0.0),
                                           end=(0.0, 0.0), klass=TRANSIT,
                                           controller="rpp",
                                           tree_key="nav.bt_xml_rpp",
                                           final=True)),
                       "a leg with no last segment")):
        try:
            bad()
            check("{} is refused by name".format(what), False)
        except Nav2LegsError:
            check("{} is refused by name".format(what), True)

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the leg split, the class table and the preempt "
                    "threshold for m6_ver2's nav2 adapter. The node that "
                    "uses it is nav2_adapter_node.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-simulator checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
