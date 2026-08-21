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

import follower
import route
from stations import STATIONS
from status_contract import MODE_AUTO

IDLE, EN_ROUTE, HOLD = "IDLE", "EN-ROUTE", "HOLD"
SAFETY_STOP, ARRIVED = "SAFETY-STOP", "ARRIVED"


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
        """
        if self.mode != MODE_AUTO:
            self.note = "route refused: not in auto mode"
            return
        try:
            poly = [(float(p[0]), float(p[1])) for p in points]
        except (TypeError, ValueError, IndexError):
            self.note = "route refused: malformed points"
            return
        if len(poly) < 2:
            self.note = "route refused: fewer than two points"
            return
        self.goal, self.route, self.state = str(label), poly, EN_ROUTE
        self.note, self.reversing = "", False
        self.arrive_m = float(arrive_m) if arrive_m else follower.ARRIVE_M

    def _cancel(self, why):
        self.goal, self.route, self.state, self.note = None, None, IDLE, why
        self.reversing = False
        self.arrive_m = follower.ARRIVE_M

    def step(self, pose, fwd_guard_m, rev_guard_m, motor_ok, v_limit_mm_s):
        """One tick: (linear.x, angular.z) under the field contract.

        TWO GUARDS IN, ONE CHOSEN HERE. nav_node reads the scan before
        anyone knows which way the truck is about to go, so it hands
        over both sector minima and the phase picks. Passing one number
        would mean guarding the end the truck is driving away from.
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
            speed = min(follower.target_speed(to_end, 0.0, rev_guard_m),
                        follower.REVERSE_MPS)
        else:
            steer = follower.steer(pose, target)
            speed = follower.target_speed(to_end, steer, fwd_guard_m)
        if speed == 0.0:
            # HOLD is a full zero, steer included: a stopped truck
            # sawing its steer wheel at an obstacle would look alive.
            self.state = HOLD
            return (0.0, 0.0)
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
