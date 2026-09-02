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
from stations import HALL, OBSTACLES, STATIONS            # noqa: E402


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

#: THE SHORT ON-RING GOAL THAT OPENS A LONG LEG ENTERED OFF A TURN
#: (defect D12, run 12, 2026-09-02). Its own class rather than a flag on
#: a transit, because everything that reads a leg has to be able to see
#: it: the adapter logs the class on dispatch, and an operator reading
#: `leg 2/6 align` on a rig is reading the reason a 13 m goal did not go
#: out at the turn. Since AMENDMENTS 8 it is NOT in DRIVEN_TO_ITS_GOAL -
#: it hands over at P like any transit, and what makes it an alignment
#: leg is its LENGTH and nothing else. See _align_split and ALIGN_M for
#: both measurements.
ALIGN = "align"

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
    # THE ALIGNMENT LEG RUNS THE TRANSIT'S OWN TREE, and that is not a
    # convenience: it is half of what makes the split cheap. nav2
    # refuses a preemption that changes the BT XML, so a leg on a
    # different tree would cost a cancel at the boundary it was added
    # to smooth. Same tree, same 0.60 m checker; the only thing this row
    # changes about the leg is that it is short and that it stops.
    (ALIGN, ("rpp", "nav.bt_xml_rpp")),
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

#: THE GOAL CHECKER EVERY LEG BUT THE BAY'S IS DECIDED BY - nav2.yaml's
#: `general_goal_checker.xy_goal_tolerance`, named by the RPP tree's
#: FollowPath (instantiate_truck.GENERAL_CHECKER). Carried here for the
#: same reason as the line above: it is not this file's parameter, it is
#: the REASON one of this file's numbers has the value it has. AND IT IS
#: POSITION ONLY, because a tricycle cannot rotate in place - so nothing
#: in nav2 has an opinion about the HEADING a leg finishes on, and any
#: leg allowed to finish may finish in the middle of its own turn.
TRANSIT_GOAL_CHECKER_M = 0.60

#: THE MODEL'S OWN MINIMUM TURNING RADIUS, measured on this rig and
#: declared in m5_ver3/config.yaml `nav.min_radius_m` (EVIDENCE_NAV_V3
#: 2.1 / 20.5 item 4) - not the geometric one the steer stop implies.
#: Carried here because an arc length needs a radius; changing it here
#: changes nothing about the truck, which is why it is quoted from the
#: file that does.
MIN_TURN_RADIUS_M = 1.25

#: HOW FAR THE TRUCK DRIVES TO TURN THROUGH A RIGHT ANGLE. Every turn on
#: this floor IS a right angle - route.py's ring, spine and pick aisle
#: meet square and every spur leaves its ring leg square - so the
#: quarter arc is THE turn, and at the minimum radius it is the longest
#: version of it. Arithmetic, not a knob.
QUARTER_ARC_M = math.pi / 2.0 * MIN_TURN_RADIUS_M

#: HOW MUCH STRAIGHT RUNNING MAKES A TURN FINISHED. Off the end of the
#: arc the truck is ON the new axis and not yet ALONG it: the steer is
#: still over and the body is still coming round. One WHEELBASE is the
#: length scale of that - m5_ver3/config.yaml `vehicle.wheelbase_m`,
#: 1.05 m, the steer wheel at body x = +0.55 and the rear axle at
#: -0.50 - and the bicycle model says what it buys: dpsi/ds =
#: tan(steer)/L, so nulling run-15's own WORST residual skew (0.90 rad,
#: measured at an alignment goal) at a steer of 0.75 rad - well inside
#: the 1.25 rad command limit - takes 0.90 x 1.05 / tan(0.75) = 1.01 m.
#: One wheelbase covers the worst thing this rig has actually done.
STRAIGHTEN_M = 1.05

#: HOW FAR ALONG A LEG ITS ALIGNMENT GOAL SITS (defect D12; the
#: arithmetic is SPEC_ADAPTER.md AMENDMENTS 8, G1-C7, 2026-09-03).
#:   IT IS A SUM OF THREE MEASUREMENTS AND NOT A CHOICE.
#:
#:     quarter arc  1.96 m   the turn itself, at the measured radius
#:     P            1.50 m   because the leg HANDS OVER P short of its
#:                           own goal now - P is inside this length
#:     straighten   1.05 m   one wheelbase of straight before that
#:     -------------------
#:     ALIGN_M      4.51 m
#:
#:   WHAT 2.75 GOT WRONG, MEASURED (run 15). The alignment leg used to
#: be driven to its goal against the transit tree's POSITION-ONLY
#: 0.60 m checker, so nav2 could declare it finished 0.60 m short: the
#: earliest legal completion sat 2.15 m along a leg whose first 1.96 m
#: IS the arc. That is 0.19 m of straight running - under a fifth of a
#: wheelbase - and a truck is not straight after 0.19 m. Twice in one
#: session it landed inside it: `align 6/8 end=(-2.75, -10.00)
#: -> COMPLETED`
#: with the truck at (-2.71, -10.53) on -0.90 rad, 0.53 m off the line
#: and mid-arc. Smac was then asked for the 4.59 m transit out of that
#: pose and refused it ten times - "exceeded maximum iterations", over
#: free paint - and the order died on the closing watchdog, standing
#: still.
#:   SO THE NUMBER IS BUILT ROUND THE HANDOVER AND NOT ROUND THE GOAL.
#: The instant that matters is not where this leg ends, it is where the
#: NEXT one is dispatched - ALIGN_M - P along the leg - and that instant
#: now sits one wheelbase of straight running past the end of the arc.
#: The goal itself is never reached at all: P is outside the 0.60 m
#: checker, so the leg is superseded before nav2 could call it finished
#: (see runs_to_its_goal, and _selftest pins the inequality).
#:   THE FIELD RESULT, MEASURED AND NOT RULED ON (run 16, wave G1-C7,
#: 2026-09-02). This constant does what it was built to do and it costs
#: something the ruling did not price, and both halves are recorded here
#: because the next wave needs both.
#:   WHAT IT DELIVERS: 5 of 5 transits opened by an alignment leg were
#: dispatched WITH THE TRUCK MOVING, v = -0.269 to -0.311 m/s, and the
#: two off a straight ring run went out at turn = -0.042 and -0.084 rad.
#: Run 15's same legs went out from a standstill at turn 0.78 to 1.56.
#: The handover-in-motion is real, it is on the adapter's own leg line,
#: and 9 of 9 preemptions were accepted by nav2.
#:   WHAT IT COSTS: 3 of 8 alignment legs never closed. All three died
#: on the closing watchdog at a right-angle turn with `best` equal to
#: ALIGN_M itself - 4.55 m off the S1 mouth, 4.73 m off the NW ring
#: corner, 4.26 m off (0, -10) - and the body twist FLIPPED SIGN 14
#: times in 30 s on the first and 6 on the second. That is not a
#: planner refusal (Smac answered) and it is not a creep (0 plateaus):
#: it is the TWO-SENSE TIE this file already names at FLIP_ABOVE_RAD,
#: reached because the goal is now far enough that both senses cost
#: about the same, with nothing holding a choice across replans since
#: AMENDMENTS 5 stripped DirectionStablePath. D12's original 2.75 m
#: bought its way out of that by being SHORT - "short enough that the
#: quarter turn is the ONLY thing in the plan" - and run 15 closed 13
#: of 13 on it.
#:   SO THE TWO RULINGS MEET HERE AND THE OWNER OWNS THE MEETING.
#: AMENDMENTS 8 requires the handover to sit past the arc, which
#: requires ALIGN_M >= arc + P + straighten; AMENDMENTS 5 removed the
#: node that held a driving sense across replans. Nothing inside this
#: file can satisfy both. The session that measured it kept every byte:
#: m6_ver2/logs/run16-c7-session (READING.txt, the C7 addendum, and the
#: body-twist sign runs). NOTHING IS QUIETLY TUNED AROUND IT.
ALIGN_M = QUARTER_ARC_M + PREEMPT_AT_M + STRAIGHTEN_M

#: THE LENGTH ABOVE WHICH A LEG ENTERED OFF A TURN IS SPLIT, and it is
#: ARITHMETIC AND NOT A TUNING KNOB. Split at ALIGN_M, the remainder is
#: (length - ALIGN_M); for that remainder to survive _merge_short it
#: must be at least PREEMPT_AT_M. So the threshold is exactly the sum,
#: and a leg shorter than it is left whole - it IS its own alignment
#: leg, being short enough that its goal is in sight from the turn.
#:   MEASURED, run 12: the two legs that died were 13.0 m and 20.0 m.
#: The one that survived the same manoeuvre was 7.0 m, and it is over
#: this threshold too - the rule does not claim 7 m was safe, only that
#: the two which were not are covered and that no leg is split into
#: pieces this file would then throw away.
#:   AND IT FOLLOWED ALIGN_M FROM 4.25 TO 6.01 (AMENDMENTS 8), which
#: closes a band, and the band is NAMED because it is a behaviour
#: change: on this floor the only chunks between the two thresholds are
#: the eight 6.00 m hops between two adjacent pick bays on one ring leg
#: (S1<->S2, S3<->S4, S5<->S6, S7<->S8). Those used to be split; they
#: are now driven whole. That is not a loss. Split, the 6.00 m hop was
#: an alignment leg that STOPPED 2.75 m along - by the measurement
#: above, mid-arc - followed by a 3.25 m transit dispatched from that
#: skewed standstill, which is precisely run-15's fatal shape. Whole,
#: it is one goal from the mouth stop, handed over at P into the bay.
SPLIT_ABOVE_M = ALIGN_M + PREEMPT_AT_M

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

#: HOW FAR PAST THE STATION POINT A STATION LEG AIMS (defect D13, run
#: 13, 2026-09-03; SPEC_ADAPTER.md AMENDMENTS 6).
#:   THE DEFECT IS TWO CONSUMERS ON ONE NUMBER WITH NO MARGIN. nav2's
#: `station_goal_checker` xy tolerance and the fleet's own arrival
#: radius are BOTH 0.25 m - ON_STATION_M above is that same number a
#: third time - read off two beliefs at two instants. A goal AT the
#: station point is therefore a goal nav2 declares reached the
#: millimetre the truck crosses the boundary the FLEET is watching, and
#: run 13 measured the coin landing the wrong way up: nav2 SUCCEEDED
#: with the estimate 0.2473 m out and the truth 0.3121 m out. Re-issuing
#: the order cannot mend that - a re-sent goal does not move a truck
#: already inside the checker - and the route went out fourteen times.
#:   SO THE GOAL MOVES AND THE CHECKER DOES NOT. With the goal
#: ARRIVE_BIAS_M deeper the same 0.25 m tolerance fires ARRIVE_BIAS_M
#: EARLIER in station-point terms: the truck has to reach 0.15 m of the
#: point before nav2 is satisfied, so run 13's own stop becomes 0.1473 m
#: on the estimate and 0.2121 m on the truth - both inside 0.25 with
#: margin, and the two facts close in one tick.
#:   0.10 AND NOT MORE, and the ceiling is not the bay: it is the
#: MEANING. This is a margin on an arrival, not a re-aiming of the bay.
#: At half the checker (0.125) a goal could be satisfied by a truck
#: standing on the FAR side of the station point, and "arrived" would
#: stop being a statement about where the pallet is. 0.10 is 40% of the
#: radius and leaves the arrival annulus one-sided.
#:   0.10 AND NOT LESS, because the number it has to beat is measured:
#: the gap run 13 fell through was 0.0027 m on the estimate and 0.0621 m
#: on the truth, and the registration's own residual - the margin
#: nav2_watch.arrival_is_short already grants for exactly this reason -
#: is 0.1179 m MAX. A bias under that is a bias inside the noise of the
#: transform the two beliefs are compared through.
#:   AND IT IS BOUNDED BY THE BAY, MEASURED AND NOT ASSUMED. See
#: bay_clearance_m: the deepest constraint on this floor is the annex's
#: 3.000 m, which leaves 1.600 m once LEAD_OVERHANG_M is paid - sixteen
#: times this. A station whose bay cannot take it is REFUSED by name at
#: leg build rather than quietly given a smaller one.
ARRIVE_BIAS_M = 0.10

#: HOW FAR THE TRUCK REACHES PAST ITS OWN ORIGIN, DEEPER INTO THE BAY.
#: The footprint nav2 is actually configured with - m5_ver3/nav2.yaml's
#: costmap polygon, copied through the derivation unchanged into
#: m6_ver2/vehicles/<vid>/nav2.yaml - spans x in [-2.415, +1.400]: 2.415
#: m of tines at body -x and 1.400 m at +x, which is the 3.815 m over
#: the tines that ALIGN_M already quotes.
#:   AND IT IS THE +x END THAT LEADS. A station leg ends on the BAY's
#: own approach heading, and the truck LEAVES the bay forks-first
#: (SPEC_ADAPTER.md Decision 1's sign audit: forks-first is negative
#: linear.x, and the spur exit drives out on the bay heading) - so it
#: goes IN on positive linear.x, +x first. Move the goal deeper by b and
#: it is this end that arrives b deeper.
LEAD_OVERHANG_M = 1.400

#: ONE LEG, DECIDED. `points` is the whole run (>= 2 points), `end` is
#: where the leg ENDS - the point every distance in the adapter is
#: measured to - `goal` is what goes in the NavigateToPose message and
#: is the same thing for every class but one (goal_point, D13), `klass`
#: is the row of CLASS_TREE that names the tree, and `final` says
#: whether this leg is allowed to run to completion.
Leg = collections.namedtuple(
    "Leg", "points start end goal klass controller tree_key final")


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
            "{!r} is not a leg class. This file knows exactly four, "
            "nav2.yaml declares two controller plugins and since "
            "AMENDMENTS 4 the table names one of them: {}".format(
                klass, ", ".join(
                    "{} -> {}".format(name, CLASS_TREE[name][0])
                    for name in CLASS_TREE)))
    return CLASS_TREE[klass]


#: LEG CLASSES THAT ARE DRIVEN TO THEIR OWN GOAL rather than handed
#: over at P. It is a tuple and not a bare comparison because the day a
#: class earns or loses a stop, the place to say so is here and not
#: inside an `if` - and ALIGN has now done both (AMENDMENTS 8). See
#: runs_to_its_goal() for both measurements.
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

    AND THE ALIGNMENT LEG IS NOT ONE OF THEM, WHICH IS THE SECOND
    MEASUREMENT (defect D12 continued; AMENDMENTS 8, run 15,
    2026-09-03). D12 added the alignment leg and put it in this tuple on
    the D10 argument - "the quarter turn must be FINISHED before the
    long goal is sent, so the leg that turns must stop". Run 15 drove
    thirteen of them, completed thirteen, and blocked twice STANDING
    STILL:

      adapter  align 6/8 end=(-2.75, -10.00) goal_yaw=+0.000
                         truck_yaw=+1.583        -> COMPLETED
      planner  GridBased plugin failed to plan from (-14.70, 20.34) to
               (-10.14, 19.82): "exceeded maximum iterations"   x10
      /auto/state BLOCKED "blocked: no progress - best 4.40 m, 30 s
                           without closing"  truth [-2.71, -10.53,
                                                    -0.90]

    A STOP IS NOT AN ALIGNMENT. This leg's checker is the transit
    tree's, 0.60 m and POSITION ONLY (TRANSIT_GOAL_CHECKER_M: a tricycle
    cannot rotate in place, so no goal checker on this stack has an
    opinion about heading). ALIGN_M was 2.75, so the earliest legal
    completion sat 2.15 m along a leg whose first 1.96 m is the arc -
    0.19 m of straight running - and "arrived" was therefore declarable
    with the truck still coming round. Twice it was: 0.53 m off the
    line at 0.90 rad of skew. The next leg was then planned from that
    pose, 4.59 m over free paint, and Smac refused it ten times.
      SO THE LEG STOPS BEING A STOP. ALIGN_M grew to arc + P +
    straighten, and the leg hands over at P like any transit - which
    means the handover happens one wheelbase of STRAIGHT running past
    the end of the arc, with the truck MOVING and on the axis. The long
    goal is never dispatched from a standstill at all, and because P is
    outside the 0.60 m checker the alignment goal is superseded before
    nav2 could ever declare it reached. Run-15's start pose is not
    unlikely now; it is unconstructable.

    THE COST, STATED: one stop per undock, of about a second, at a
    corner a 3.815 m tricycle with a 1.25 m turning radius was going to
    slow down for anyway. It was two stops per turn before AMENDMENTS 8,
    and the second one was the defect.
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


def _align_split(chunks):
    """Long chunks entered off a turn, opened by a short on-ring goal.

    Returns (chunks, indices) - the new chunk list and the set of
    indices that are ALIGNMENT legs.

    DEFECT D12, MEASURED (run 12, 2026-09-02). D10 already stops the
    truck at a mouth; run-12 shows that a stop is not an alignment. From
    a standstill at the S1 mouth on the bay's heading, handed a goal
    13 m east and a quarter turn round:

        adapter  leg 2/5 transit end=(0.00, 10.00) goal_yaw=-3.142
                                 truck_yaw=-1.552 turn=-1.589
        adapter  leg 2/5 transit end=(0.00, 10.00)   (dispatched again)
        /auto/state BLOCKED "blocked: no progress - best 10.99 m, 30 s
                             without closing"  at truth (-10.50, 10.41)

    and the same shape at a RING CORNER 110 s later - `leg 3/5 transit
    end=(-20.00, -10.00) turn=+1.076`, 20 m, BLOCKED at best 20.67 m,
    truth (-19.09, 11.20). Ground truth for the first: out to
    (-10.63, 10.92), back to (-10.75, 9.76), twelve seconds of dither
    round (-10.85, 9.5), west to (-11.52, 9.77), and away on the same
    arc again.
      IT IS NOT D11 AND IT IS NOT A CREEP. The worst northward offset
    over that stretch was +0.927 m against run-10's +2.43 - AMENDMENTS 5
    took the amplifier out and the excursion with it - and the speeds
    run 0.02 to 0.30 m/s with no plateau. What is left is the quarter
    turn D10 named, now OSCILLATING rather than arcing: with nothing
    holding the mouth-built plan, SmacPlannerHybrid re-decides which
    sense to drive on every replan, because at a quarter turn both
    senses reach the goal (FLIP_ABOVE_RAD's own tie) and a goal 13 m
    away gives neither any advantage the other lacks.
      SO THE GOAL IS ASKED TO DO ONE THING. A short goal ALIGN_M along
    the leg is reachable one way and awkward the other, so the sense is
    decided by geometry rather than by the third decimal place of a
    replan, and the long goal is then sent to a truck already pointing
    along it - turn about zero, one plan, no cusp.
      AND IT IS SENT WITH THE TRUCK MOVING (AMENDMENTS 8). D12's first
    cut had the alignment leg STOP on its goal, on D10's argument; run
    15 measured that stop landing mid-arc against a position-only
    0.60 m checker and killing the leg after it. ALIGN_M now covers arc
    + P + a straightening length, so the hand-over at P is already past
    the turn - see ALIGN_M and runs_to_its_goal.

    WHY "OFF A TURN" AND NOT "OFF A MOUTH". The second BLOCKED was at a
    ring corner with no bay in sight. Every boundary split_legs makes IS
    a turn (COLLINEAR_RAD) or a spur foot, so "chunk index >= 1" says
    "entered off a turn" exactly, in the one place that already knows.
    The head of a route is left alone: it starts under the TRUCK, whose
    heading this file is not told at split time, so whether there is a
    turn there at all is not a question the geometry can answer - and
    run-12 drove three of those clean.

    WHAT IS NEVER SPLIT: a chunk that is not a TRANSIT. A station spur
    is 5.75 m and is entered off a right angle, so it matches on shape -
    but its goal is the BAY's pose and its checker is the 0.25 m one,
    and an alignment goal inside a spur would put the truck on a heading
    the bay does not admit (D5). A spur exit is not split for the same
    reason from the other end.
    """
    out, aligned = [], set()
    for index, points in enumerate(chunks):
        final = index == len(chunks) - 1
        head, at = None, None
        if index and classify(points, final) == TRANSIT:
            head, at = _align_head(points)
        if head is None:
            out.append(list(points))
            continue
        aligned.add(len(out))
        out.append([tuple(p) for p in points[:at + 1]] + [head])
        rest = [head] + [tuple(p) for p in points[at + 1:]]
        if math.dist(rest[0], rest[1]) == 0.0:
            # THE HEAD LANDED EXACTLY ON A VERTEX. Keeping both would
            # hand the remainder a zero-length first segment, and a
            # segment with no length has no heading (leg_yaw's refusal).
            rest = rest[1:]
        out.append(rest)
    return out, aligned


def _align_head(points):
    """(the alignment goal on this chunk, the vertex index it follows).

    (None, None) when the chunk earns no split.

    ON THE LEG AND NOT BESIDE IT: the point is ALIGN_M along the CHUNK'S
    OWN POLYLINE, so it is a point of the corridor the route already
    committed to and never a pose this file invented.

    ALONG THE CHUNK AND NOT ALONG ITS FIRST SEGMENT, and AMENDMENTS 8 is
    what forced the difference. The first cut of D12 refused to place
    the head past the chunk's first VERTEX, on the argument that a goal
    past a vertex would be on a heading that is not this leg's. With
    ALIGN_M at 2.75 that refusal cost nothing, because route.py's ring
    legs carry a node every 3.00 to 4.00 m ("the widest gap on either
    leg is 4.00 m"). At 4.51 it would cost everything: 196 of this
    floor's long chunks have a first segment shorter than that,
    including all three that carried run-15's BLOCKEDs, and D12 would
    have quietly stopped existing exactly where it was measured.
      AND THE ARGUMENT IT REPLACES WAS ALREADY ANSWERED BY split_legs. A
    chunk is near-collinear BY CONSTRUCTION - every vertex inside one
    turns by at most COLLINEAR_RAD - so a point past one of its vertices
    is a point of this leg on this leg's heading, to within the same 15
    degrees this file already grants a truck's parking error. The
    alignment leg keeps the vertices it walks over, so its own last
    segment is a real segment of the granted corridor.
    """
    if leg_length_m(points) <= SPLIT_ABOVE_M:
        return None, None
    walked = 0.0
    for index in range(len(points) - 1):
        first, second = points[index], points[index + 1]
        step = math.dist(first, second)
        if step <= 0.0:
            continue
        if walked + step >= ALIGN_M:
            scale = (ALIGN_M - walked) / step
            return (first[0] + (second[0] - first[0]) * scale,
                    first[1] + (second[1] - first[1]) * scale), index
        walked += step
    # UNREACHABLE ON A CHUNK OVER THE THRESHOLD, and it is a refusal
    # rather than a fall-through: SPLIT_ABOVE_M is ALIGN_M + P, so a
    # chunk that got here is longer than ALIGN_M and the walk above
    # cannot run out of polyline. If it ever does, the threshold and
    # the walk have stopped agreeing and no goal is the honest answer.
    raise Nav2LegsError(
        "a chunk {:.3f} m long ran out of polyline {:.3f} m into it, "
        "which SPLIT_ABOVE_M ({:.3f} m) says is impossible"
        .format(leg_length_m(points), ALIGN_M, SPLIT_ABOVE_M))


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


def _station_yaw(station_id, stations):
    """The bay's declared approach heading, or a refusal that says so.

    ONE READING FOR TWO USES. leg_yaw sends it as the goal's ORIENTATION
    and goal_point advances the goal ALONG it; a station whose heading
    was read twice could have its position and its heading disagree.
    """
    try:
        return float(stations[station_id]["yaw"])
    except (KeyError, TypeError, ValueError):
        raise Nav2LegsError(
            "station {} declares no usable approach heading, and a "
            "bay's heading is the one thing a spur leg cannot work "
            "out for itself".format(station_id))


def _collision_boxes(obstacles, hall):
    """Every (name, x0, x1, y0, y1) the world paints, walls included.

    OBSTACLES IS NOT THE WHOLE FLOOR. stations.py's tuple mirrors
    warehouse_ver3.sdf's racks and its dock annex; the four hall walls
    are in HALL as the INNER FACES they are, and four of the eight pick
    bays are approached straight at one of them (S3, S4, S7, S8 all run
    north into WallNorth's 14.000). A clearance measured without them
    would report "nothing in the way" across a building.
    """
    x0, x1, y0, y1 = (float(v) for v in hall)
    walls = (("WallWest", x0 - 0.2, x0, y0, y1),
             ("WallEast", x1, x1 + 0.2, y0, y1),
             ("WallSouth", x0, x1, y0 - 0.2, y0),
             ("WallNorth", x0, x1, y1, y1 + 0.2))
    return tuple(obstacles) + walls


def _ray_box_m(origin, direction, box):
    """Distance to where a ray enters an axis-aligned box, or None.

    The ordinary slab test. A ray that STARTS inside the box returns
    0.0, which is the honest answer to "how much room is there" and is
    caught by the caller as a bay with none.
    """
    _name, x0, x1, y0, y1 = box
    near, far = 0.0, float("inf")
    for lo, hi, start, step in ((x0, x1, origin[0], direction[0]),
                                (y0, y1, origin[1], direction[1])):
        if abs(step) < 1e-12:
            if start < lo or start > hi:
                return None
            continue
        first, second = (lo - start) / step, (hi - start) / step
        if first > second:
            first, second = second, first
        near, far = max(near, first), min(far, second)
        if near > far:
            return None
    return near if far >= 0.0 else None


def bay_clearance_m(station_id, stations=STATIONS, obstacles=OBSTACLES,
                    hall=HALL):
    """Metres from a station point to the first painted box AHEAD of it.

    "Ahead" is the bay's own approach heading - the direction the truck
    is travelling when it arrives - so this is exactly the room a goal
    moved deeper eats into, and the room the truck's LEAD_OVERHANG_M is
    already standing in.

    MEASURED OFF THE PAINT AND NOT OFF A BELIEF ABOUT IT.
    stations.OBSTACLES mirrors warehouse_ver3.sdf rectangle for
    rectangle (test_stations_sdf.py is what notices a drift), and HALL
    carries the wall faces, so this is the SDF's own geometry reached
    without parsing XML in a file that must import on a python with no
    ROS on it.

    WHAT IT ACTUALLY READS ON THIS FLOOR. The eight pick bays are cut
    RIGHT THROUGH their rack rows (stations.py: "THE STATIONS ARE IN
    OPEN CROSS-AISLES, NOT IN POCKETS"), so the ray out of S1 runs south
    down x = -13.000 between RackNW1 (x in [-16.000, -15.500]) and
    RackNW2 (x in [-10.500, -9.500]), past their RackSW twins, and stops
    on AnnexA's north face at y = -14.000: 18.250 m. S4's runs north
    down x = -7.000 to WallNorth's inner face at 14.000: 18.250 m again.
    The four annex bays are the shallow ones - 3.000 m to their own back
    panels - and they are what bounds the bias for the whole floor.
    """
    try:
        station = stations[station_id]
        origin = (float(station["x"]), float(station["y"]))
    except (KeyError, TypeError, ValueError):
        raise Nav2LegsError(
            "station {!r} is not on this floor, so there is no bay to "
            "measure the room in".format(station_id))
    yaw = _station_yaw(station_id, stations)
    direction = (math.cos(yaw), math.sin(yaw))
    best = float("inf")
    for box in _collision_boxes(obstacles, hall):
        reach = _ray_box_m(origin, direction, box)
        if reach is not None and reach < best:
            best = reach
    if not math.isfinite(best):
        raise Nav2LegsError(
            "nothing at all stands ahead of station {} on its own "
            "approach heading, which means this floor has no walls - a "
            "clearance of infinity is a measurement nobody made"
            .format(station_id))
    return best


def goal_point(end, klass, stations=STATIONS, obstacles=OBSTACLES,
               hall=HALL):
    """The xy that goes in this leg's NavigateToPose goal.

    EVERY CLASS BUT ONE SENDS ITS OWN END, and that is not a default: an
    intermediate leg end is a point on a granted corridor and moving it
    would move the corridor. Only the BAY has a reason to aim past
    itself, and the reason is ARRIVE_BIAS_M's - two consumers on one
    0.25 m radius with no margin between them (D13).

    ALONG THE BAY'S OWN DECLARED HEADING, which is the axis the spur
    runs on and the same number leg_yaw puts in the goal's orientation.
    The leg's last segment samples that same axis - test_nav2_adapter_
    legs pins that it does, for every station leg the planner can build
    - but it is the truck's parking error near the bay and it INVERTS if
    the truck ever stands past the point, which would aim the bias back
    out of the spur. One number decides both, and it is the declared one.

    AND THE BAY HAS TO HAVE THE ROOM. bay_clearance_m is the paint; the
    truck's own +x end is already LEAD_OVERHANG_M into it; what is left
    is what a bias may spend. A station that cannot pay is refused BY
    NAME here, at leg build, with its arithmetic - never shrunk to fit,
    because a bias that quietly becomes something else is a margin
    nobody can check against the run it was supposed to explain.
    """
    end = (float(end[0]), float(end[1]))
    if klass != STATION_SPUR:
        return end
    station_id = station_at(end, stations=stations)
    if station_id is None:
        raise Nav2LegsError(
            "the leg ending at {!r} was classed a station spur and there "
            "is no station within {:.2f} m of it, so there is no bay to "
            "aim into".format(end, ON_STATION_M))
    clearance = bay_clearance_m(station_id, stations=stations,
                                obstacles=obstacles, hall=hall)
    room = clearance - LEAD_OVERHANG_M
    if room < ARRIVE_BIAS_M:
        raise Nav2LegsError(
            "station {} has {:.3f} m of bay ahead of its point and the "
            "truck reaches {:.3f} m past its own origin, which leaves "
            "{:.3f} m for an arrival bias of {:.3f} m. The bias is not "
            "shrunk to fit: a bay that cannot take it is a floor to be "
            "redrawn, not a tolerance to be quietly lowered"
            .format(station_id, clearance, LEAD_OVERHANG_M, room,
                    ARRIVE_BIAS_M))
    yaw = _station_yaw(station_id, stations)
    return (end[0] + ARRIVE_BIAS_M * math.cos(yaw),
            end[1] + ARRIVE_BIAS_M * math.sin(yaw))


def plan_legs(polyline):
    """The whole leg queue for a released polyline.

    THE FIRST POINT IS THE POSE. Both doors that reach this file prepend
    it - route.plan_route does it so the first segment starts under the
    truck instead of snapping it sideways onto the graph, and
    vda_agent._send_route does it for the same reason on an extension -
    so `polyline[0]` is where the truck is and the spur-exit test has
    something to read.
    """
    chunks, aligned = _align_split(split_legs(polyline))
    legs = []
    for index, points in enumerate(chunks):
        final = index == len(chunks) - 1
        klass = ALIGN if index in aligned else classify(points, final=final)
        controller, tree_key = controller_for(klass)
        legs.append(Leg(points=points, start=points[0], end=points[-1],
                        goal=goal_point(points[-1], klass),
                        klass=klass, controller=controller,
                        tree_key=tree_key, final=final))
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
        # THE SAME READING goal_point ADVANCES ALONG (D13). One number,
        # so a bay's goal position and its goal heading cannot disagree.
        return _station_yaw(station, stations)
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

    check("the alignment goal is arc {:.2f} + P {:.2f} + straighten "
          "{:.2f} = {:.2f} m, and the split follows at {:.2f} m"
          .format(QUARTER_ARC_M, PREEMPT_AT_M, STRAIGHTEN_M, ALIGN_M,
                  SPLIT_ABOVE_M),
          abs(ALIGN_M - (QUARTER_ARC_M + PREEMPT_AT_M + STRAIGHTEN_M))
          < 1e-12 and abs(SPLIT_ABOVE_M - (ALIGN_M + PREEMPT_AT_M))
          < 1e-12)
    check("the alignment leg hands over {:.2f} m past the END of its "
          "quarter arc, so the long goal leaves a truck that is moving "
          "and straight (AMENDMENTS 8)".format(STRAIGHTEN_M),
          ALIGN_M - PREEMPT_AT_M - QUARTER_ARC_M > 0.0)
    check("and nav2 can never call an alignment leg finished: P "
          "({:.2f} m) is outside the transit checker ({:.2f} m), so the "
          "leg is superseded first".format(PREEMPT_AT_M,
                                           TRANSIT_GOAL_CHECKER_M),
          PREEMPT_AT_M > TRANSIT_GOAL_CHECKER_M)

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
    check("and its GOAL sits {:.2f} m past the point on that same "
          "heading, while every other leg sends its own end (D13)"
          .format(ARRIVE_BIAS_M),
          abs(math.dist(legs[1].goal, legs[1].end) - ARRIVE_BIAS_M) < 1e-12
          and abs(leg_yaw(legs[1])
                  - math.atan2(legs[1].goal[1] - legs[1].end[1],
                               legs[1].goal[0] - legs[1].end[0])) < 1e-9
          and legs[0].goal == tuple(float(v) for v in legs[0].end))
    _worst = min(bay_clearance_m(name) for name in STATIONS)
    check("every bay on this floor has room for the bias: the shallowest "
          "is {:.3f} m and the truck reaches {:.3f} m into it, leaving "
          "{:.3f} m against {:.3f} m asked"
          .format(_worst, LEAD_OVERHANG_M, _worst - LEAD_OVERHANG_M,
                  ARRIVE_BIAS_M),
          _worst - LEAD_OVERHANG_M >= ARRIVE_BIAS_M)
    check("S1's bay is measured at 18.250 m and S4's at 18.250 m - the "
          "pick bays are cut right through their rack rows",
          abs(bay_clearance_m("S1") - 18.25) < 1e-9
          and abs(bay_clearance_m("S4") - 18.25) < 1e-9)
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
          runs_to_its_goal(out[0]) and runs_to_its_goal(out[-1]))
    check("and NOTHING between them stops - the alignment legs hand "
          "over at P like the transits they open (AMENDMENTS 8)",
          not any(runs_to_its_goal(leg) for leg in out[1:-1]))
    check("so the only standstill a route can build is the bay mouth, "
          "and the leg after it is never longer than ALIGN_M + P",
          all(leg_length_m(out[index].points) <= SPLIT_ABOVE_M + 1e-9
              for index in range(1, len(out))
              if runs_to_its_goal(out[index - 1])))
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
    check("S5 -> S9 splits at every junction turn, and D12 opens each "
          "long one with its own alignment leg (eight legs)",
          len(out) == 8 and out[-1].klass == STATION_SPUR
          and [leg.klass for leg in out] == [
              SPUR_EXIT, ALIGN, TRANSIT, ALIGN, TRANSIT, ALIGN, TRANSIT,
              STATION_SPUR])

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
                                           end=(0.0, 0.0), goal=(0.0, 0.0),
                                           klass=TRANSIT,
                                           controller="rpp",
                                           tree_key="nav.bt_xml_rpp",
                                           final=True)),
                       "a leg with no last segment"),
                      (lambda: bay_clearance_m("S99"),
                       "a bay measured at a station that is not on this "
                       "floor"),
                      (lambda: goal_point((0.0, 0.0), STATION_SPUR),
                       "a station goal built where there is no station "
                       "(D13)")):
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
