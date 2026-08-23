"""nav_core.py - the autopilot's decisions, with no ROS in the room.

A REQUESTER, NOT AN AUTHORITY. Every command this file emits still
passes cmd_mux (mode), cmd_gate (Motor, staleness, V_Limit) and
sto_contactor (torque). The states exist for the OPERATOR's screen;
the safety chain neither reads nor needs them.

SAFETY-STOP HOLDS THE ROUTE. A Motor drop mid-drive is a latched ESTOP1
demand; the truck stays where the stop left it and the route is still
the route. When Motor returns (the owner's Acknowledge on the panel),
driving resumes without a re-plan - a re-plan from the same pose would
produce the same polyline and a re-click ritual would only teach the
operator to automate the click.

V_LIMIT IS OBEYED HERE TOO, not only at the gate. The gate clamping 0.7
to 0.3 keeps the COMMAND legal, but the plant is still doing 0.7 while
it decelerates - and the F-program's speed monitor reads the SHAFT.
Capping at the source means the truck approaches the limit from below
instead of through it (Step 3 measured that trap: latched stop 0.68 s
after enable near racking).

IT BACKS OUT OF A SPUR, IT DOES NOT TURN AROUND IN ONE. A station is
reached forks-first, so the route out of it starts dead astern. The
pursuit's answer to that is a committed minimum-radius arc, and in a
spur the first half of that arc drives the truck AT the rack it just
parked in front of: measured 2026-08-13 leaving S10, 1.235 m of northing
and the back scanner 0.938 m off rack B, inside the 1.0 m protective
field. So the truck reverses instead - straight, steer zero, guarded by
the counterweight-end lidar sector and by the PLC's back scanner, which
is the primary device on that side. follower.reverse_phase owns when.
"""
import json
import math

import avoid
import follower
import route
from stations import STATIONS
from status_contract import MODE_AUTO

IDLE, EN_ROUTE, HOLD = "IDLE", "EN-ROUTE", "HOLD"
SAFETY_STOP, ARRIVED = "SAFETY-STOP", "ARRIVED"
# M6.7: HOLD IS NO LONGER WHERE A TRUCK GOES TO STAY. Measured
# 2026-08-23, f2 and f3 stood at their stations indefinitely with
# guard_min 1.4846 and 1.4722 m against a 1.500 m hold band, Motor TRUE
# and every field clear. Nothing was broken; the autopilot's only move
# was to wait for the world to change, and the world was a wall.
AVOID, NUDGE, BLOCKED = "AVOID", "NUDGE", "BLOCKED"

# WAIT FIRST, AND IT IS THE CHEAPEST MOVE THERE IS. At the creep ceiling
# a truck covers 1.5 m in this, so an obstacle that was another vehicle
# has gone. Driving round a truck that is about to leave is how a floor
# gets two vehicles in one aisle facing each other.
HOLD_PATIENCE_S = 5.0
# Most of one envelope half-width: enough to change the geometry, short
# enough to stay on the corridor. 1.6 s at follower.REVERSE_MPS.
NUDGE_M = 0.40
NUDGE_MAX = 2
# A NUDGE NEEDS A DEADLINE AS WELL AS A DISTANCE, and finding that out
# is what the escalation's own tests were for. A truck that is wedged -
# or whose command is being refused somewhere downstream - never covers
# NUDGE_M, so a nudge measured only in metres never ends, and the state
# machine grows exactly the dead end it was built to remove. 0.40 m at
# follower.REVERSE_MPS is 1.6 s; four times that leaves room for the
# plant's ramp and for V_Limit holding the truck at the creep ceiling,
# and still ends.
NUDGE_TIMEOUT_S = 6.0
# WHICH WAY A POSITIVE SCAN BEARING TURNS THE TRUCK. avoid answers in
# the scan frame and follower.steer wants a world target, and whether
# the two agree is a property of how the lidar is mounted rather than
# anything either file says. It is a constant with a test on it
# (test_nav_core_escalation.test_the_scan_sign_puts_the_steer_toward_
# the_gap): get it wrong and the truck steers AWAY from the only free
# floor in the room, which is worse than not moving at all.
SCAN_SIGN = 1.0


class NavCore:

    def __init__(self, plan=route.plan_route):
        self._plan = plan
        self.mode = None
        self.state = IDLE
        self.goal = None
        self.route = None
        self.note = ""
        self.reversing = False
        self.arrive_m = follower.ARRIVE_M
        # The escalation's own memory. All three are cleared by any tick
        # that actually drives, so a truck that got going never carries
        # a stale nudge count into its next stop.
        self._stop_since = None
        self._nudges = 0
        self._nudge_from = None
        self._nudge_since = None

    def on_mode(self, mode):
        self.mode = mode
        if mode != MODE_AUTO and self.state != IDLE:
            self._cancel("mode left auto")

    def on_goal(self, station_id, pose_xy):
        if not station_id:
            self._cancel("cancelled")
            return
        if self.mode != MODE_AUTO:
            self.note = "goal refused: not in auto mode"
            return
        poly = self._plan(tuple(pose_xy), station_id)
        if poly is None:
            self.note = "goal refused: unknown station {}".format(station_id)
            return
        self.goal, self.route, self.state = station_id, poly, EN_ROUTE
        self.note, self.reversing = "", False
        # The station owns its arrival radius; its spur length set it.
        self.arrive_m = STATIONS[station_id].get(
            "arrive_m", follower.ARRIVE_M)

    def on_route(self, points, arrive_m, label):
        """An externally planned polyline - the VDA agent's door (M6.2).

        Same rules as on_goal after planning: auto mode only, the empty
        goal stays the one cancel door, and everything downstream
        (follower, guards, ARRIVED, SAFETY-STOP holding the route) is
        the same machinery. This file still plans nothing here: the
        route arrives finished, and a malformed one is refused, not
        repaired.

        MALFORMED INCLUDES NaN, AND THAT IS NOT THEORETICAL. json.loads
        reads the bare literal NaN and float("nan") passes float()
        without a murmur, so an unchecked conversion installed it:
        measured, step() then answered (-0.7, nan) - cruise traction
        with a NaN steer. The gate clamps the command, so the plant is
        safe, but arrived() is false against NaN forever, so the truck
        drives and never gets there, and state_json emits a bare NaN
        that no strict JSON parser will read. Both coordinates must be
        finite; inf fails the same test for the same reason.

        NOTHING IS ASSIGNED UNTIL EVERYTHING HAS PASSED. arrive_m used
        to be converted AFTER goal, route and state were already set, so
        an unusable radius raised with the truck EN-ROUTE and nav_node's
        handler wrote "route refused" over a vehicle that was driving -
        a note that lies to the operator. The last three lines are the
        only mutations in this method, and they run or none of them do.
        """
        if self.mode != MODE_AUTO:
            self.note = "route refused: not in auto mode"
            return
        try:
            poly = []
            for p in points:
                x, y = float(p[0]), float(p[1])
                if not (math.isfinite(x) and math.isfinite(y)):
                    raise ValueError("non-finite coordinate")
                poly.append((x, y))
        except (TypeError, ValueError, IndexError):
            self.note = "route refused: malformed points"
            return
        if len(poly) < 2:
            self.note = "route refused: fewer than two points"
            return
        try:
            # Absent is the one way to ask for the default. A radius
            # that is zero, negative or NaN is a fault in the sender,
            # and arrived() would never be true against any of them.
            radius = (follower.ARRIVE_M if arrive_m is None
                      else float(arrive_m))
            if not math.isfinite(radius) or radius <= 0.0:
                raise ValueError("arrive_m out of range")
        except (TypeError, ValueError):
            self.note = "route refused: unusable arrive_m"
            return
        self.goal, self.route, self.state = str(label), poly, EN_ROUTE
        self.note, self.reversing = "", False
        self.arrive_m = radius
        self._clear_escalation()

    def _cancel(self, why):
        self.goal, self.route, self.state, self.note = None, None, IDLE, why
        self.reversing = False
        self.arrive_m = follower.ARRIVE_M
        self._clear_escalation()

    def _clear_escalation(self):
        """Forget everything about the stop we were in.

        Called from three places and all three mean the same thing: this
        truck is no longer in the stop it was in. A tick that drives, a
        cancel, and a new route. Without the last one a truck that ended
        a leg BLOCKED would start its next leg with two nudges already
        spent against an obstacle that is no longer in front of it.
        """
        self._stop_since = None
        self._nudges = 0
        self._nudge_from = None
        self._nudge_since = None

    def _want_bearing(self):
        """Where the route wants to go, in the SCAN frame.

        The scan's fork end is angle pi and its counterweight end is 0,
        which is the same convention follower.sector_min centres on. A
        truck driving forwards therefore wants pi and a reversing one
        wants 0.
        """
        return 0.0 if self.reversing else math.pi

    def _escalate(self, pose, xy, bkts, now):
        """A stop that has a way out of itself, or an honest BLOCKED.

        Returns (linear, angular). The guard is already known to be
        stopping the truck; what is decided here is what to do about it,
        cheapest first: wait, then look for a way round, then change the
        geometry, then say so and stop.
        """
        if now is None or bkts is None:
            # THE COMPATIBILITY PATH, AND IT IS DELIBERATELY FIRST. A
            # caller from before M6.7 - or a test written against the
            # old behaviour, or a tick whose scan has gone stale - gets
            # the HOLD it expects and nothing else. An escalation driven
            # off a picture of the world that stopped arriving is worse
            # than standing still.
            self.state = HOLD
            return (0.0, 0.0)
        if self._stop_since is None:
            self._stop_since = now
        if now - self._stop_since < HOLD_PATIENCE_S:
            self.state = HOLD
            return (0.0, 0.0)
        if self._nudge_from is not None:
            far_enough = math.dist(xy, self._nudge_from) >= NUDGE_M
            out_of_time = now - self._nudge_since >= NUDGE_TIMEOUT_S
            if not (far_enough or out_of_time):
                self.state = NUDGE
                return (follower.REVERSE_MPS, 0.0)
            # The move is spent, by distance or by clock. Start the
            # cycle again from the top: the geometry may have changed
            # and the cheap answers deserve another look before the
            # expensive one. A nudge that ran out of TIME rather than
            # distance still counts against NUDGE_MAX - a truck that
            # cannot execute the move is exactly the truck that should
            # stop being asked to.
            self._nudge_from = None
            self._nudge_since = None
            self._stop_since = now
            self.state = HOLD
            return (0.0, 0.0)
        want = self._want_bearing()
        free = avoid.free_heading(bkts, want)
        if free is not None:
            self.state = AVOID
            off = SCAN_SIGN * follower.norm_ang(free - want)
            travel = follower.travel_yaw(pose[2])
            target = (pose[0] + avoid.FREE_M * math.cos(travel + off),
                      pose[1] + avoid.FREE_M * math.sin(travel + off))
            steer = follower.steer(pose, target)
            speed = follower.GUARD_SLOW_MPS
            return ((speed if self.reversing else -speed), steer)
        if self._nudges < NUDGE_MAX:
            self._nudges += 1
            self._nudge_from = xy
            self._nudge_since = now
            self.state = NUDGE
            return (follower.REVERSE_MPS, 0.0)
        self.state = BLOCKED
        bearing, near = min(bkts, key=lambda pair: pair[1])
        self.note = ("blocked: nearest {:.2f} m at {:.0f} deg, no free "
                     "heading and {} nudges spent"
                     .format(near, math.degrees(bearing), self._nudges))
        return (0.0, 0.0)

    def step(self, pose, fwd_guard_m, rev_guard_m, motor_ok, v_limit_mm_s,
             field_min_m=math.inf, buckets=None, now=None):
        """One tick: (linear.x, angular.z) under the field contract.

        TWO GUARDS IN, ONE CHOSEN HERE. nav_node reads the scan before
        anyone knows which way the truck is about to go, so it hands
        over both sector minima and the phase picks. Passing one number
        would mean guarding the end the truck is driving away from.

        AND THE SAFETY SCANNERS' OWN MINIMUM, WHICH HAS NO END TO PICK.
        Those three devices look all round and the field they feed is
        the one that moves V_Limit, so their closest return applies in
        both phases. It defaults to infinity so every caller that has no
        field report - the tests, and any node built before this
        existed - keeps exactly the behaviour it had.
        """
        if self.state in (IDLE, ARRIVED) or self.route is None:
            return (0.0, 0.0)
        xy = (pose[0], pose[1])
        if follower.arrived(xy, self.route[-1], self.arrive_m):
            self.state, self.reversing = ARRIVED, False
            return (0.0, 0.0)
        if not motor_ok:
            self.state = SAFETY_STOP
            return (0.0, 0.0)
        target, to_end = follower.advance(self.route, xy)
        alpha = follower.norm_ang(
            math.atan2(target[1] - pose[1], target[0] - pose[0])
            - follower.travel_yaw(pose[2]))
        self.reversing = follower.reverse_phase(alpha, self.reversing)
        if self.reversing:
            # Straight back at a walk. No steer: an arc is the very
            # thing the back-out exists to avoid, and a reversing
            # tricycle steers from the wrong end anyway.
            steer = 0.0
            speed = min(follower.target_speed(to_end, 0.0, rev_guard_m,
                                              field_min_m),
                        follower.REVERSE_MPS)
        else:
            steer = follower.steer(pose, target)
            speed = follower.target_speed(to_end, steer, fwd_guard_m,
                                          field_min_m)
        if speed == 0.0:
            # A STOP IS NOW A DECISION AND NOT A DESTINATION. What comes
            # back is still a full zero in the HOLD and BLOCKED cases -
            # a stopped truck sawing its steer wheel at an obstacle
            # would look alive - but AVOID and NUDGE are real commands.
            return self._escalate(pose, xy, buckets, now)
        self._clear_escalation()
        self.state = EN_ROUTE
        speed = min(speed, v_limit_mm_s / 1000.0)
        return ((speed if self.reversing else -speed), steer)

    def state_json(self, pose, guard_min_m):
        return json.dumps({
            "state": self.state, "goal": self.goal, "note": self.note,
            "route": [list(p) for p in self.route] if self.route else [],
            "pose": [pose[0], pose[1], pose[2]],
            "reversing": self.reversing,
            "arrive_m": self.arrive_m,
            "guard_min": (None if guard_min_m == float("inf")
                          else guard_min_m)})
