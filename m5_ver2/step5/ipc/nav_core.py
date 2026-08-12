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
"""
import json

import follower
import route
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
        self.note = ""

    def _cancel(self, why):
        self.goal, self.route, self.state, self.note = None, None, IDLE, why

    def step(self, pose, guard_min_m, motor_ok, v_limit_mm_s):
        """One tick: (linear.x, angular.z) under the field contract."""
        if self.state in (IDLE, ARRIVED) or self.route is None:
            return (0.0, 0.0)
        xy = (pose[0], pose[1])
        if follower.arrived(xy, self.route[-1]):
            self.state = ARRIVED
            return (0.0, 0.0)
        if not motor_ok:
            self.state = SAFETY_STOP
            return (0.0, 0.0)
        target, to_end = follower.advance(self.route, xy)
        steer = follower.steer(pose, target)
        speed = follower.target_speed(to_end, steer, guard_min_m)
        if speed == 0.0:
            # HOLD is a full zero, steer included: a stopped truck
            # sawing its steer wheel at an obstacle would look alive.
            self.state = HOLD
            return (0.0, 0.0)
        self.state = EN_ROUTE
        speed = min(speed, v_limit_mm_s / 1000.0)
        return (-speed, steer)

    def state_json(self, pose, guard_min_m):
        return json.dumps({
            "state": self.state, "goal": self.goal, "note": self.note,
            "route": [list(p) for p in self.route] if self.route else [],
            "pose": [pose[0], pose[1], pose[2]],
            "guard_min": (None if guard_min_m == float("inf")
                          else guard_min_m)})
