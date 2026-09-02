#!/usr/bin/env python3
"""nav2_path.py - a granted polyline becomes a Path RPP can track.

    python3 m6_ver2/nav2_adapter/nav2_path.py --selftest

NO ROS IN THIS FILE. It is arithmetic over the points m6/ipc/route.py
hands out; nav2_adapter_node.py is the shell that puts the result in a
`nav_msgs/Path` and sends it to /fN/follow_path.

WHY IT EXISTS, AND IT IS ONE SENTENCE (SPEC_ADAPTER.md AMENDMENTS 9,
G1-C8 ruling, 2026-09-03). THE TRAFFIC LEDGER GRANTS A POLYLINE.
Four waves measured one family of failures from one source - Smac
re-deciding degenerate ring geometry on every replan: exhaustion
refusals over free paint (runs 15 and 16: 13 and 8), the two-sense
chatter (14 sign flips in 30 s, 3 of 8 alignment legs never closing),
and open question 5's corridor drift at +0.9 to +2.4 m. Freespace
planning over a corridor somebody already granted was always a
translation error. This file does the translation properly: polyline in,
drivable path out, and the only thing left for nav2 to decide is the
wheel.

WHERE THIS FILE ENDS AND nav2_legs.py BEGINS, BECAUSE THERE ARE TWO
FILES AND THAT IS A CHOICE. nav2_legs.py owns the QUEUE - which parts of
a route are goals, which class each is, and every policy that reads the
truck's own yaw. THIS file owns the CURVE - the arithmetic that turns a
list of vertices into a list of poses, and it is told the sense rather
than deciding it. The seam is `flipped`, one boolean, and it is why
nav2_legs imports this and this imports nothing of nav2_legs.

WHAT RPP ACTUALLY READS OFF THE PATH, MEASURED IN ITS OWN SOURCE, AND IT
IS NOT WHAT YOU WOULD GUESS. `nav2_regulated_pure_pursuit_controller`
1.3.12 (the installed version -
/opt/ros/jazzy/share/.../package.xml; source at tag 1.3.12,
`src/regulated_pure_pursuit_controller.cpp`):

    225   // Setting the velocity direction
    226   double x_vel_sign = 1.0;
    227   if (params_->allow_reversing) {
    228     x_vel_sign = carrot_pose.pose.position.x >= 0.0 ? 1.0 : -1.0;
    229   }

`carrot_pose` is a point of the plan TRANSFORMED INTO THE ROBOT FRAME
(path_handler.cpp transformGlobalPlan), so THE DRIVING SENSE IS DECIDED
BY WHERE THE PATH GOES RELATIVE TO THE TRUCK'S OWN HEADING AND BY
NOTHING ELSE. The pose ORIENTATIONS on the path are read in exactly one
place - findVelocitySignChange (:519), and only in the branch that
compares the orientations of two poses at the SAME POSITION (:547-556),
which is an in-place rotation and which this file never emits. The goal
checkers on this stack are `nav2_controller::PositionGoalChecker`
(m6_ver2/vehicles/fN/nav2.yaml), which have no opinion about heading
either.
  SO THE ORIENTATIONS THIS FILE LAYS ARE A DECLARATION AND NOT A
COMMAND, and they are laid anyway, for three reasons that are not
decoration: they are what an operator reads off /fN/plan and off a
recorded bag when asking which way the chain was meant to be driven;
they are what makes the duplicate-pose branch above a non-question; and
they are the one place the D7 sense decision is written down at the
instant it was made. What ACTUALLY makes the truck drive the intended
sense is the geometry: the path leaves the truck's own position, so the
carrot is ahead of it or behind it according to the same comparison D7
makes, and the two agree by construction wherever the geometry has an
opinion at all.

THE ONE PROPERTY THAT IS A COMMAND IS THE ABSENCE OF A CUSP. RPP
truncates its lookahead to the first sign change in the plan
(:193-204), so ONE reversal anywhere in a 40 m path is a 40 m path
driven at a 0.0 m carrot. Every corner here is replaced by a tangent
arc, so successive segments differ by a fraction of a degree and the dot
product findVelocitySignChange takes is positive the whole way down.
cusp_at() is that same test, in python, and the suite runs it over every
route this floor can plan.
"""
import argparse
import collections
import math
import sys

import _donors                                            # noqa: F401

import follower                                           # noqa: E402


class Nav2PathError(ValueError):
    """A polyline, a corner or a number this file will not guess at."""


#: HOW FINELY THE PATH IS SAMPLED, and it is a resolution and not a
#: tuning knob. The local costmap this path is tracked against is
#: 0.05 m/cell (m6_ver2/vehicles/fN/nav2.yaml), and RPP's own carrot is
#: chosen by walking the pose list and INTERPOLATING between the two
#: poses that straddle the lookahead distance - so a spacing at twice
#: the grid is fine enough that no cell of the corridor is skipped and
#: coarse enough that a 40 m chain is four hundred poses rather than
#: four thousand. AMENDMENTS 9 says "~0.1 m"; this is that number, with
#: its two reasons.
SPACING_M = 0.10

#: BELOW THIS A VERTEX IS NOT A CORNER. route.py's graph is drawn on
#: aisle centrelines that meet at exact right angles, and a chain's
#: interior vertices are either exactly collinear or exactly square -
#: so this is a floating-point guard and not a tolerance anybody chose.
#: A polyline that needed a real angular tolerance here would be a
#: polyline this file was not built for.
STRAIGHT_RAD = 1e-9

#: WHERE A CORNER STOPS BEING A CORNER AND BECOMES A REVERSAL. At a turn
#: of pi the two tangents are antiparallel, the tangent length
#: r * tan(theta/2) goes to infinity, and there is no arc at any radius:
#: the truck has to stop and come back. That is a MANOEUVRE, which is
#: Smac's job on this contract (AMENDMENTS 9: station and spur-exit legs
#: keep NavigateToPose), so a ring chain carrying one is refused by name
#: rather than approximated.
REVERSAL_RAD = math.pi - math.radians(1.0)


#: ONE BUILT PATH.
#:   `poses`     [(x, y, yaw)] in the frame the polyline came in, ready
#:               for the shell to put through the registration.
#:   `length_m`  how far the truck drives on it - the SUM OF THE
#:               PRIMITIVES and not the granted polyline's length, which
#:               is longer by what every rounded corner cuts.
#:   `corners`   how many vertices became arcs. Zero is a straight run.
#:   `flipped`   the sense, as it was decided ONCE at dispatch: True
#:               means every orientation is the travel direction's
#:               pi-flip, which on this model is forks-first.
#:   `dropped`   how many head stubs were thrown away as parking error
#:               rather than driven (defect D14). It is on the record
#:               rather than silent because a chain that started one
#:               vertex in is a chain whose first metre nobody granted.
ChainPath = collections.namedtuple(
    "ChainPath", "poses length_m corners flipped dropped")


def sense_name(flipped):
    """The sense as an operator reads it off a leg table.

    THE MODEL CARRIES ITS FORKS AT BODY -x (SPEC_ADAPTER.md Decision 1's
    sign audit), so a pose orientation that is the pi-flip of the travel
    direction is a truck whose forks lead. Naming it here rather than in
    the log line keeps the sign audit in one file.
    """
    return "forks-first" if flipped else "counterweight-first"


def _clean(polyline):
    """The polyline as (x, y) floats with its zero-length segments gone.

    THE SAME RULE nav2_legs._clean APPLIES, for the same reason and not
    by accident: route.plan_route prepends the pose and keeps the entry
    node, so a truck standing on its own spawn node is handed that node
    twice, and a segment with no length has no heading. It is repeated
    here rather than imported because this file is BELOW nav2_legs in
    the import order and a cycle to save nine lines would be a worse
    trade than the nine lines.
    """
    points = []
    for raw in polyline:
        try:
            point = (float(raw[0]), float(raw[1]))
        except (TypeError, ValueError, IndexError):
            raise Nav2PathError(
                "the chain polyline carries {!r}, which is not an "
                "(x, y) point".format(raw))
        if not (math.isfinite(point[0]) and math.isfinite(point[1])):
            raise Nav2PathError(
                "the chain polyline carries a non-finite coordinate "
                "{!r}: a path built through one is a path whose every "
                "pose is NaN, and nav2 would take it".format(raw))
        if points and math.dist(points[-1], point) == 0.0:
            continue
        points.append(point)
    return points


def _direction(first, second):
    return math.atan2(second[1] - first[1], second[0] - first[0])


def corner_turns(points):
    """The signed turn at every interior vertex, in order.

    Positive is a left turn. The two end vertices are not corners and
    are not in the list, which is why the caller indexes this by
    `vertex - 1`.
    """
    turns = []
    for index in range(1, len(points) - 1):
        before = _direction(points[index - 1], points[index])
        after = _direction(points[index], points[index + 1])
        turns.append(follower.norm_ang(after - before))
    return turns


def tangent_m(turn_rad, radius_m):
    """How much straight each side of a corner the arc eats.

    r * tan(|theta| / 2), which is the whole of the corner arithmetic:
    it is the distance from the vertex to the point where a circle of
    radius r is tangent to each leg. At a right angle - which is every
    turn on this floor - tan(45 deg) is 1 and the tangent IS the radius.
    """
    turn = abs(float(turn_rad))
    if turn <= STRAIGHT_RAD:
        return 0.0
    if turn >= REVERSAL_RAD:
        raise Nav2PathError(
            "a turn of {:.3f} rad is a reversal, not a corner: no arc "
            "of any radius rounds it, and a chain is not allowed to "
            "carry a manoeuvre (SPEC_ADAPTER.md AMENDMENTS 9 leaves "
            "those to the station and spur-exit legs)".format(turn))
    return float(radius_m) * math.tan(turn / 2.0)


def _fit_tangents(points, turns, radius_m):
    """[tangent at each vertex], refusing a corner with no room by name.

    A CORNER IS NOT A LOCAL DECISION. Its arc eats `tangent_m` of the
    segment on EACH side, and the segment on each side is shared with
    the next corner along - so the check is per SEGMENT and it is the
    sum of the two claims on it. On this floor the answer is never close:
    the tightest pair of turns route.py can plan is ten metres apart and
    the tightest turn-to-chain-end is 3.00 m, against a 1.25 m claim.
    test_nav2_adapter_path asserts that over every route the planner can
    build, so this refusal is a statement about a floor being re-cut and
    not about a number being wrong.
    """
    tangents = [0.0] * len(points)
    for index, turn in enumerate(turns, start=1):
        tangents[index] = tangent_m(turn, radius_m)
    for index in range(len(points) - 1):
        span = math.dist(points[index], points[index + 1])
        claim = tangents[index] + tangents[index + 1]
        if claim > span + 1e-9:
            raise Nav2PathError(
                "the corners at {!r} and {!r} claim {:.3f} m of tangent "
                "between them at radius {:.3f} m and the segment "
                "joining them is only {:.3f} m long. The corner cannot "
                "be rounded and this file will not quietly shrink the "
                "radius: the radius is the truck's"
                .format(points[index], points[index + 1], claim,
                        float(radius_m), span))
    return tangents


#: A STRAIGHT SHORTER THAN THIS IS NOT A STRAIGHT, and this is a
#: floating-point guard rather than a geometric tolerance. A trim that
#: lands exactly on a corner's tangent point leaves a run-in of about
#: 1e-16 m, whose direction is whatever the subtraction rounded to - and
#: RPP reads the DOT PRODUCT of successive segments, so a segment
#: pointing at random is a CUSP two poses into a forty-metre path
#: (cusp_at, and findVelocitySignChange behind it). Below this the
#: straight is simply not emitted and the arc starts where the path
#: does.
JOINT_EPS_M = 1e-9


def _drop_head_stub(points, radius_m):
    """(points with any un-drivable head stub gone, how many went).

    DEFECT D14, MEASURED (m6_ver2/logs/run17-c8-session-a, 2026-09-02).
    route.plan_route prepends the truck's own POSE and keeps the entry
    node whenever the pose is nearer that than the second node, so a
    truck standing 0.229 m off a ring node is handed [pose, node, ...]
    with a 67 degree turn AT the node - and nav2_legs._merge_short folds
    that run forward, which puts the turn INSIDE a chunk. The builder
    then met a near-square corner with 0.229 m of run-in and refused the
    whole order by name, twice:

      adapter  leg 1/2 ring chain NOT SENT: the corners at
               (-9.9119, 10.2109) and (-10.0, 10.0) claim 0.832 m of
               tangent between them ... the segment joining them is only
               0.229 m long
      /auto/state BLOCKED "blocked: the granted polyline cannot be
                           driven as a path"

    THE REFUSAL WAS RIGHT AND THE INPUT WAS WRONG. That vertex is not a
    corner of the granted corridor: it is the truck's own parking error
    with a graph node behind it. This is _merge_short's own sentence one
    level down - "the parking error is not a leg" - said again about a
    corner, and enforced the same way: the stub is dropped, the path
    starts at the node, and the node is at most that stub behind the
    truck (0.229 m here) which is well inside the 2.00 m nav2 searches.

    ONLY A STUB THAT CANNOT CARRY ITS OWN CORNER, and only from the
    head. A granted segment on this floor is 3.00 m at the tightest
    against a 1.25 m tangent, so nothing the ledger drew can match this;
    what matches is a parking error, every time. A stub in the MIDDLE of
    a polyline is still refused by _fit_tangents, because there the
    vertex behind it IS granted and dropping it would move the corridor.
    """
    dropped = 0
    while len(points) >= 3:
        turn = follower.norm_ang(
            _direction(points[1], points[2]) - _direction(points[0],
                                                          points[1]))
        if abs(turn) <= STRAIGHT_RAD:
            break
        # WHAT THE STUB WOULD HAVE TO BE WORTH to carry this corner. A
        # REVERSAL has no tangent at any radius, so the yardstick there
        # is the radius itself - which is what a quarter turn costs and
        # therefore the least any real corner can. A 10 m leg that
        # doubles back is NOT a parking error and is still refused by
        # name; a 0.2 m one is, every time.
        need = (float(radius_m) if abs(turn) >= REVERSAL_RAD
                else tangent_m(turn, radius_m))
        if math.dist(points[0], points[1]) >= need:
            break
        points = points[1:]
        dropped += 1
    return points, dropped


def drivable_points(polyline, radius_m):
    """The polyline build_chain_path will ACTUALLY start from.

    THE SENSE HAS TO BE READ OFF THE SAME POINTS THE PATH IS BUILT FROM,
    and D14 is why this is a function rather than an implementation
    detail: the head stub a chain drops is exactly the 0.245 m of
    parking error whose heading is the truck's arrival error and not the
    corridor's. Deciding the driving sense off it (nav2_legs.chain_sense)
    gave "counterweight-first" for a truck standing in a bay it can only
    leave dead astern - the answer D5 and D7 both exist to prevent.
    """
    points, _dropped = _drop_head_stub(_clean(polyline), radius_m)
    return points


def _sample_straight(start, end, spacing_m):
    """[(x, y, heading)] from start to end, start EXCLUDED."""
    span = math.dist(start, end)
    if span <= JOINT_EPS_M:
        return []
    heading = _direction(start, end)
    steps = max(1, int(math.ceil(span / spacing_m - 1e-9)))
    out = []
    for step in range(1, steps + 1):
        scale = float(step) / steps
        out.append((start[0] + (end[0] - start[0]) * scale,
                    start[1] + (end[1] - start[1]) * scale,
                    heading))
    return out


def _sample_arc(start, heading_in, turn, radius_m, spacing_m):
    """[(x, y, heading)] round one corner arc, start EXCLUDED.

    The centre is r to the LEFT of the incoming tangent for a left turn
    and r to the right for a right turn, which is the whole of it: a
    vehicle turning left goes round a point on its left.
    """
    side = 1.0 if turn > 0.0 else -1.0
    normal = (-math.sin(heading_in) * side, math.cos(heading_in) * side)
    centre = (start[0] + radius_m * normal[0],
              start[1] + radius_m * normal[1])
    begin = math.atan2(start[1] - centre[1], start[0] - centre[0])
    span = abs(turn) * radius_m
    steps = max(1, int(math.ceil(span / spacing_m - 1e-9)))
    out = []
    for step in range(1, steps + 1):
        scale = float(step) / steps
        angle = begin + turn * scale
        out.append((centre[0] + radius_m * math.cos(angle),
                    centre[1] + radius_m * math.sin(angle),
                    follower.norm_ang(heading_in + turn * scale)))
    return out


def build_chain_path(polyline, radius_m, spacing_m=SPACING_M, flipped=False):
    """The granted polyline as a `ChainPath`.

    `flipped` IS TOLD AND NOT DECIDED. The sense is D7's rule read off
    the truck's own yaw and it belongs to nav2_legs.chain_sense; this
    file is the geometry and the geometry is the same either way. See
    the header for what nav2 does and does not read off it.

    THE VERTICES ARE NOT ON THE PATH AND THAT IS THE POINT. A square
    corner driven as a square corner is a curvature demand of infinity;
    a tricycle answers one by saturating its steer and leaving the
    corridor, which is the family run-10 measured at +2.43 m. Each
    corner becomes a tangent arc at the truck's OWN minimum radius, so
    the worst the path ever asks for is exactly what the truck can do,
    and the corridor price is the arc's sagitta -
    r * (1 - cos(theta/2)), 0.366 m at a right angle - paid on the
    inside of the turn where the ring band is widest.
    """
    try:
        radius = float(radius_m)
        spacing = float(spacing_m)
    except (TypeError, ValueError):
        raise Nav2PathError(
            "the turning radius is {!r} and the sample spacing is {!r}: "
            "a path built off a number that is not one is not a path"
            .format(radius_m, spacing_m))
    if not (math.isfinite(radius) and radius > 0.0):
        raise Nav2PathError(
            "the turning radius is {!r}, and a corner arc needs a "
            "positive one. It is the truck's own measured minimum "
            "(nav2_legs.MIN_TURN_RADIUS_M) and never a guess"
            .format(radius_m))
    if not (math.isfinite(spacing) and spacing > 0.0):
        raise Nav2PathError(
            "the sample spacing is {!r}, and a densified path needs a "
            "positive one (nav2_path.SPACING_M)".format(spacing_m))
    points = _clean(polyline)
    if len(points) < 2:
        raise Nav2PathError(
            "a chain of {} distinct point(s) has no length, so there is "
            "no path to build and nothing to drive"
            .format(len(points)))
    points, dropped = _drop_head_stub(points, radius)
    turns = corner_turns(points)
    tangents = _fit_tangents(points, turns, radius)

    poses = [(points[0][0], points[0][1], _direction(points[0], points[1]))]
    length = 0.0
    corners = 0
    cursor = points[0]
    for index in range(1, len(points) - 1):
        turn = turns[index - 1]
        vertex = points[index]
        heading_in = _direction(points[index - 1], vertex)
        if tangents[index] <= 0.0:
            # A COLLINEAR VERTEX IS NOT A CORNER and it is not a pose
            # either: the straight runs through it to the next one.
            continue
        unit_in = (math.cos(heading_in), math.sin(heading_in))
        heading_out = _direction(vertex, points[index + 1])
        unit_out = (math.cos(heading_out), math.sin(heading_out))
        enter = (vertex[0] - tangents[index] * unit_in[0],
                 vertex[1] - tangents[index] * unit_in[1])
        leave = (vertex[0] + tangents[index] * unit_out[0],
                 vertex[1] + tangents[index] * unit_out[1])
        straight = _sample_straight(cursor, enter, spacing)
        if straight:
            length += math.dist(cursor, enter)
            poses.extend(straight)
        elif len(poses) == 1:
            # THE PATH STARTS ON THE ARC. A trim lands exactly on a
            # tangent point (trim_to's corner back-off does it by
            # construction), so the head pose's heading was read off a
            # run-in that is not there. It takes the arc's own.
            poses[0] = (poses[0][0], poses[0][1], heading_in)
        arc = _sample_arc(enter, heading_in, turn, radius, spacing)
        length += abs(turn) * radius
        poses.extend(arc)
        corners += 1
        cursor = leave
    poses.extend(_sample_straight(cursor, points[-1], spacing))
    length += math.dist(cursor, points[-1])
    if flipped:
        poses = [(x, y, follower.norm_ang(yaw + math.pi))
                 for x, y, yaw in poses]
    return ChainPath(poses=poses, length_m=length, corners=corners,
                     flipped=bool(flipped), dropped=dropped)


#: HOW FAR OFF ITS OWN CORRIDOR A TRUCK MAY BE AND STILL BE ON IT.
#: Beyond this `trim_to` declines to project at all and hands back the
#: whole grant, because a trim decided off a projection metres away is a
#: corridor this file invented. It is TWICE the 0.60 m general goal
#: checker plus the corner sagitta (0.366 m) rounded up - the widest a
#: truck driving one of these paths correctly can be from the polyline
#: the ledger granted - and it is deliberately smaller than nav2's own
#: 2.00 m closest-pose search so that the honest answer and the working
#: answer are the same answer.
TRIM_NEAR_M = 2.0


def trim_to(points, xy, near_m=TRIM_NEAR_M, radius_m=None):
    """The granted polyline from where the truck stands on it, onward.

    WHY A CHAIN IS NOT ALWAYS BUILT FROM ITS OWN HEAD, AND IT IS RPP's
    ARITHMETIC AND NOT A PREFERENCE. `path_handler.cpp`
    transformGlobalPlan searches for the plan pose nearest the robot
    ONLY over the first `max_robot_pose_search_dist` of the plan
    (2.00 m in m6_ver2/vehicles/fN/nav2.yaml), and then discards every
    pose further than half the local costmap (5.00 m) from the robot. A
    forty-metre chain re-sent to a truck thirty metres along it is
    therefore searched over its first two metres, every one of those
    poses is pruned, the transformed plan comes back empty and the
    controller aborts: `throw nav2_core::InvalidPath("Resulting plan has
    0 poses in it.")`.
      AND IT IS RE-SENT: `_safety` re-dispatches the running leg on
    every SAFETY-STOP resume, and run 16 had two of those mid-order.

    THE PROJECTION AND NOT THE NEAREST VERTEX. A vertex on a ring leg is
    up to 4.00 m away; the point of this is to put the head of the path
    under the truck.

    AND IT NEVER EATS A CORNER'S TANGENT. `radius_m`, when given, is the
    turning radius the corners will be rounded at: a trim that landed
    0.30 m before a square corner would leave 0.30 m of the 1.25 m the
    arc needs, and build_chain_path refuses that BY NAME - which over a
    resume would BLOCK an order on a corner the truck was driving
    perfectly well. So the head backs off to the tangent point instead.
    That puts the path at most one tangent BEHIND the truck, which is
    still inside the 2.00 m nav2 will look through.
    """
    cleaned = _clean(points)
    if len(cleaned) < 2:
        return cleaned
    try:
        target = (float(xy[0]), float(xy[1]))
    except (TypeError, ValueError, IndexError):
        raise Nav2PathError(
            "the truck's position on its chain is {!r}, which is not an "
            "(x, y) point, and a path trimmed to one would start "
            "nowhere".format(xy))
    if not all(math.isfinite(value) for value in target):
        raise Nav2PathError(
            "the truck's position on its chain is {!r}: a path trimmed "
            "to a non-finite belief is a path sent at random".format(xy))
    best = None
    for index in range(len(cleaned) - 1):
        first, second = cleaned[index], cleaned[index + 1]
        span_x, span_y = second[0] - first[0], second[1] - first[1]
        span = span_x * span_x + span_y * span_y
        if span <= 0.0:
            continue
        scale = ((target[0] - first[0]) * span_x
                 + (target[1] - first[1]) * span_y) / span
        scale = max(0.0, min(1.0, scale))
        foot = (first[0] + span_x * scale, first[1] + span_y * scale)
        gap = math.dist(target, foot)
        # STRICTLY NEARER WINS, so among equals the EARLIEST segment
        # does - a chain that ran back past its own head would otherwise
        # be trimmed to its tail.
        if gap <= near_m and (best is None or gap < best[0] - 1e-9):
            best = (gap, index, foot)
    if best is None:
        return cleaned
    _gap, index, foot = best
    if radius_m is not None and index + 2 < len(cleaned):
        turns = corner_turns(cleaned)
        if abs(turns[index]) >= REVERSAL_RAD:
            # THE VERTEX AHEAD IS A REVERSAL, WHICH MEANS THE HEAD IS A
            # PARKING ERROR (D14, second measurement: run 17 session B).
            # The truck stops 0.247 m PAST its bay point, vda_agent
            # prepends that pose, and the route reads [pose, bay, mouth]
            # - a stub pointing south in front of a spur pointing north.
            # tangent_m refuses a reversal BY NAME, so backing off into
            # one raised before _drop_head_stub could throw the stub
            # away: "leg 1/2 ring chain NOT SENT: a turn of 3.125 rad is
            # a reversal", every leg-2 order of that session, and the
            # fleet requeued it for eight minutes.
            #   THERE IS NOTHING TO BACK OFF INTO. The stub is not
            # corridor, and the builder is about to drop it; the head
            # stays where the projection put it and _drop_head_stub does
            # the rest.
            tangent = 0.0
        else:
            tangent = tangent_m(turns[index], radius_m)
        vertex = cleaned[index + 1]
        room = math.dist(foot, vertex)
        if tangent > 0.0 and room < tangent:
            back = min(tangent, math.dist(cleaned[index], vertex))
            span = math.dist(cleaned[index], vertex)
            scale = (span - back) / span
            foot = (cleaned[index][0]
                    + (vertex[0] - cleaned[index][0]) * scale,
                    cleaned[index][1]
                    + (vertex[1] - cleaned[index][1]) * scale)
    rest = [foot] + cleaned[index + 1:]
    if len(_clean(rest)) < 2:
        # STANDING ON THE LAST POINT. There is nothing left to trim to,
        # and a one-point path is not a path; the whole grant is the
        # honest answer and the goal checker is about to end it anyway.
        return cleaned
    return rest


def cusp_at(poses):
    """The index of the first cusp in `poses`, or None. RPP's own test.

    A TRANSCRIPTION AND NOT AN OPINION. `findVelocitySignChange`
    (nav2_regulated_pure_pursuit_controller 1.3.12,
    regulated_pure_pursuit_controller.cpp:519) walks the plan taking the
    dot product of successive segments and stops at the first negative
    one; it also stops at two poses sharing a POSITION but not an
    orientation, which is an in-place rotation. Whatever it stops at
    becomes the lookahead distance (:193-204), so a cusp two metres in
    is a forty-metre path driven at a two-metre carrot - and a cusp at
    the truck's nose is a path driven at no carrot at all.
      THE BUILDER CANNOT PRODUCE ONE, which is what makes this a test
    and not a filter: every corner is an arc at the truck's own radius,
    so successive segments differ by at most spacing / r radians -
    0.08 rad at 0.10 m and 1.25 m - and the dot product is positive the
    whole way down. This function is how the suite says so over every
    route on the floor rather than over the four that were drawn by
    hand.
    """
    for index in range(1, len(poses) - 1):
        before, at, after = poses[index - 1], poses[index], poses[index + 1]
        oa = (at[0] - before[0], at[1] - before[1])
        ab = (after[0] - at[0], after[1] - at[1])
        if oa[0] * ab[0] + oa[1] * ab[1] < 0.0:
            return index
        if math.hypot(*oa) == 0.0 and before[2] != at[2]:
            return index
        if math.hypot(*ab) == 0.0 and at[2] != after[2]:
            return index
    return None


def offset_from_polyline(point, polyline):
    """How far `point` sits off the corridor the ledger granted.

    THE MEASUREMENT THE FIELD READS, in the file that builds the thing
    being measured. A rounded corner cuts the inside of its turn, so a
    built path is NOT on the granted polyline everywhere and the honest
    claim is a BOUND: the worst offset is the arc's sagitta and nothing
    else. The session reading uses the same function on ground truth,
    so what the suite asserts about the plan and what the rig measures
    about the truck are the same number computed the same way.
    """
    best = float("inf")
    for index in range(len(polyline) - 1):
        first = (float(polyline[index][0]), float(polyline[index][1]))
        second = (float(polyline[index + 1][0]),
                  float(polyline[index + 1][1]))
        span_x, span_y = second[0] - first[0], second[1] - first[1]
        span = span_x * span_x + span_y * span_y
        if span <= 0.0:
            best = min(best, math.dist(point, first))
            continue
        scale = ((point[0] - first[0]) * span_x
                 + (point[1] - first[1]) * span_y) / span
        scale = max(0.0, min(1.0, scale))
        best = min(best, math.dist(
            point, (first[0] + span_x * scale, first[1] + span_y * scale)))
    return best


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_nav2_adapter_path.py is the real suite - it runs the
    builder over route.py's own planner output for every station pair on
    the floor - and this is the version an operator can run on the rig
    with one command.
    """
    fails = []

    def check(name, condition):
        print("  {}  {}".format("pass" if condition else "FAIL", name))
        if not condition:
            fails.append(name)

    radius = 1.25
    straight = build_chain_path([(0.0, 0.0), (10.0, 0.0)], radius, 0.10)
    check("a 10 m straight densifies to 101 poses",
          len(straight.poses) == 101)
    check("its length is its length",
          abs(straight.length_m - 10.0) < 1e-9)
    check("and it carries no corner", straight.corners == 0)

    corner = build_chain_path(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], radius, 0.10)
    check("a square corner becomes one arc", corner.corners == 1)
    check("the tangent at a right angle IS the radius",
          abs(tangent_m(math.pi / 2.0, radius) - radius) < 1e-12)
    check("the vertex itself is off the path",
          min(math.dist(p[:2], (10.0, 0.0)) for p in corner.poses) > 0.4)
    check("the corridor price is the sagitta",
          abs(max(offset_from_polyline(p[:2],
                                       [(0.0, 0.0), (10.0, 0.0),
                                        (10.0, 10.0)])
                  for p in corner.poses)
              - radius * (1.0 - math.cos(math.pi / 4.0))) < 0.01)
    check("and the path carries no cusp", cusp_at(corner.poses) is None)

    flipped = build_chain_path([(0.0, 0.0), (10.0, 0.0)], radius, 0.10,
                               flipped=True)
    check("the flip moves no point",
          [p[:2] for p in flipped.poses] == [p[:2] for p in straight.poses])
    check("and turns every orientation",
          all(abs(follower.norm_ang(p[2] - math.pi)) < 1e-9
              for p in flipped.poses))
    check("forks-first is what the flip is called",
          sense_name(True) == "forks-first")

    granted = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    check("a truck at the head of its chain trims nothing away",
          trim_to(granted, (0.0, 0.0)) == granted)
    check("a truck 9 m off the corridor trims nothing either",
          trim_to([(0.0, 0.0), (40.0, 0.0)], (20.0, 9.0))
          == [(0.0, 0.0), (40.0, 0.0)])
    walked = trim_to([(0.0, 0.0), (40.0, 0.0)], (30.0, 0.2))
    check("a truck 30 m along a 40 m chain gets a 10 m path - RPP "
          "searches 2.00 m of a fresh plan and no further",
          abs(walked[0][0] - 30.0) < 1e-9 and len(walked) == 2)
    backed = trim_to(granted, (9.7, 0.0), radius_m=radius)
    check("and a trim landing inside a corner backs off to its tangent "
          "point rather than being refused for it",
          abs(backed[0][0] - (10.0 - radius)) < 1e-9)
    check("... and the path built from there still carries no cusp",
          cusp_at(build_chain_path(backed, radius, 0.10).poses) is None)

    for name, call in (
            # TEN METRES AND NOT ONE: a head stub shorter than the
            # radius is a parking error and is DROPPED (D14), so the
            # reversal this refusal is about has to be a granted leg.
            ("a reversal", lambda: build_chain_path(
                [(0.0, 0.0), (10.0, 0.0), (0.0, 0.0)], radius, 0.10)),
            ("a corner with no room", lambda: build_chain_path(
                [(0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (0.0, 1.0)],
                radius, 0.10)),
            ("one point", lambda: build_chain_path(
                [(0.0, 0.0)], radius, 0.10)),
            ("a NaN", lambda: build_chain_path(
                [(0.0, 0.0), (float("nan"), 1.0)], radius, 0.10)),
            ("a radius of zero", lambda: build_chain_path(
                [(0.0, 0.0), (1.0, 0.0)], 0.0, 0.10))):
        try:
            call()
            check("{} is refused by name".format(name), False)
        except Nav2PathError as exc:
            check("{} is refused: {}".format(name, str(exc)[:48]), True)

    print("{} problems".format(len(fails)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the chain path builder: a granted polyline becomes "
                    "a cusp-free Path at the truck's own turning radius.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the checks that need nothing but "
                             "python, and print each one")
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.selftest:
        return _selftest()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
