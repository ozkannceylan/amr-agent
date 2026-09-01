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
the whole thing to MPPI and lose the station goal checker.
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
CLASS_TREE = collections.OrderedDict((
    (STATION_SPUR, ("rpp", "nav.bt_xml_rpp")),
    (SPUR_EXIT, ("rpp", "nav.bt_xml_rpp")),
    (TRANSIT, ("mppi", "nav.bt_xml")),
))

# ----------------------------- the numbers -----------------------------

#: WHERE THE NEXT LEG IS SENT, in metres of BELIEVED distance still to
#: run on this one. `navigate_to_pose` is a single-goal server, so nav2
#: displaces the running goal itself and F4 Task 3's `Preempt`
#: instrument already measured what that switch costs (a ~0.05 s class
#: gap in the command stream).
#:   1.5 AND NOT 1.0, AND THE REASON IS MPPI'S. Inside
#: MPPI_GOAL_THRESHOLD_M the GoalCritic takes over as a point
#: attraction and the path critics hand off; a leg end reached inside
#: that would be driven as if it were a destination - decelerated into,
#: hooked round - which is exactly the per-node behaviour legs exist to
#: remove. P sits OUTSIDE it, so an intermediate leg end never enters
#: the endgame at all.
PREEMPT_AT_M = 1.5
#: MPPI's own GoalCritic `threshold_to_consider`, m5_ver3/nav2.yaml.
#: Carried here as the REASON for the number above and pinned by test;
#: it is not a parameter of this file and changing it here changes
#: nothing in nav2.
MPPI_GOAL_THRESHOLD_M = 1.4

#: HOW STRAIGHT "STRAIGHT ON" IS. The waypoint graph's own turns are all
#: right angles, and the only non-right angle a route ever carries is
#: the prepended pose's approach onto its entry node - a truck standing
#: off the centreline by its own parking error. 15 deg is comfortably
#: clear of 90 and admits a truck up to about a quarter of a leg length
#: off line without manufacturing a leg out of its parking error.
COLLINEAR_RAD = math.radians(15.0)

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


def station_at(xy, radius_m=ON_STATION_M):
    """The station whose point `xy` stands on, or None."""
    x, y = float(xy[0]), float(xy[1])
    for station_id, station in STATIONS.items():
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
            "{!r} is not a leg class. This file knows exactly three, and "
            "nav2.yaml declares exactly two controller plugins behind "
            "them: {}".format(klass, ", ".join(
                "{} -> {}".format(name, CLASS_TREE[name][0])
                for name in CLASS_TREE)))
    return CLASS_TREE[klass]


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


def split_legs(polyline):
    """The polyline as a list of point-lists, one per leg.

    A vertex ends a leg when the heading turns by more than
    COLLINEAR_RAD, or when the vertex is a station spur foot. The vertex
    itself belongs to BOTH legs: it is the end of one goal and the start
    of the next, which is what makes the queue continuous.
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
    return legs


def classify(leg_points, first, final):
    """The class of one leg, from the geometry and stations.STATIONS.

    PRECEDENCE, STATED: a leg that both leaves a station and ends at one
    is a STATION SPUR. The end governs, because the end is what picks
    the goal checker the arrival is decided against.
    """
    if final and station_at(leg_points[-1]) is not None:
        return STATION_SPUR
    if first and station_at(leg_points[0]) is not None:
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
        klass = classify(points, first=(index == 0),
                         final=(index == len(chunks) - 1))
        controller, tree_key = controller_for(klass)
        legs.append(Leg(points=points, start=points[0], end=points[-1],
                        klass=klass, controller=controller,
                        tree_key=tree_key,
                        final=(index == len(chunks) - 1)))
    return legs


def should_preempt(distance_to_end_m, final):
    """Is it time to send the next leg?

    THE FINAL LEG IS NEVER PREEMPTED - there is nothing to preempt it
    with, and it is the one leg whose completion the goal checker is
    allowed to decide.
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
    if final:
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

    check("the preempt point sits OUTSIDE MPPI's endgame ({:.2f} m > "
          "{:.2f} m)".format(PREEMPT_AT_M, MPPI_GOAL_THRESHOLD_M),
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
    check("the spur is driven by rpp and the transit by mppi",
          legs[1].controller == "rpp" and legs[0].controller == "mppi")

    out = plan_legs(route.plan_route((7.0, 4.25), "S9"))
    check("leaving a station is a dead-astern SPUR EXIT",
          out[0].klass == SPUR_EXIT)
    check("S5 -> S9 splits at every junction turn (five legs)",
          len(out) == 5 and out[-1].klass == STATION_SPUR)

    straight = plan_legs(route.plan_route((7.0, 10.2), "S5"))
    check("a straight run THROUGH a spur foot still splits there",
          len(straight) == 2 and straight[1].klass == STATION_SPUR)

    check("a doubled first point is not a leg boundary",
          len(split_legs([(0.0, 0.0), (0.0, 0.0), (5.0, 0.0)])) == 1)
    check("the preempt fires below P and not above",
          should_preempt(1.49, final=False)
          and not should_preempt(1.51, final=False))
    check("the final leg is never preempted",
          not should_preempt(0.01, final=True))

    for bad, what in ((lambda: controller_for("freespace"),
                       "an unknown leg class"),
                      (lambda: plan_legs([(0.0, 0.0)]),
                       "a one-point polyline"),
                      (lambda: plan_legs([(1.0, 1.0), (1.0, 1.0)]),
                       "a polyline with no length"),
                      (lambda: should_preempt(float("nan"), final=False),
                       "a non-finite distance")):
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
