#!/usr/bin/env python3
"""nav2_state.py - the contract the fleet layer is not being told about.

    python3 m6_ver2/nav2_adapter/nav2_state.py --selftest

NO ROS IN THIS FILE. The rclpy shell (nav2_adapter_node.py) owns the
subscriptions, the action client and the two timers; everything that
could be WRONG about what the wire SAYS is here, where a test can reach
it without a simulator.

WHAT THIS FILE IS FOR. m6/ipc/nav_node.py + nav_core.py are being
retired as the motion engine, and the fleet layer above them
(vda_agent.py, vda_orders.py, the HMI) is NOT being modified. So the
adapter has to present the same `/[vid]/auto/state` document, in the
same words, with the same rules about which word appears when - because
those words are read by code that has no idea any of this changed.

WHAT THE FLEET ACTUALLY BRANCHES ON, and it is only two things
(vda_agent.cb_nav): BLOCKED for our label, and ARRIVED for our label.
Everything else in the vocabulary is the OPERATOR's screen. That is not
a licence to be sloppy with the rest - IDLE with a note and an empty
goal is what ends `executing` on the fleet side, and getting that wrong
strands an order - but it is why the state machine below is a reporter
and not a controller. It requests nothing and inhibits nothing;
cmd_mux, cmd_gate and sto_contactor keep every word they had.

AVOID AND NUDGE ARE RESERVED AND NEVER EMITTED (Decision 3). nav2's
costmap and the BT recoveries replace m6.7's escalation, so no path in
this file assigns either - and state_json refuses to put one on the wire
even if a caller sets it by hand. The words stay in the contract
document because a reader of an old log needs them.

THREE THINGS THAT LOOK LIKE DETAILS AND ARE NOT:

  EN-ROUTE IS ASSIGNED SYNCHRONOUSLY ON ACCEPTANCE. vda_agent measures
  NAV_SETTLE_S (0.3 s) from the moment it published the route; a state
  tick inside that window that still said IDLE would be read as "nav is
  not driving this order" and the agent would drop `executing` on a
  truck that is about to move. So acceptance sets the word, not the
  first action feedback.

  NOTHING IS ASSIGNED UNTIL EVERYTHING HAS PASSED. nav_core.on_route's
  rule, kept for nav_core's reason: a refusal that landed after `state`
  was already EN-ROUTE wrote "route refused" over a vehicle that was
  driving, which is a note that lies to the operator.

  SAFETY-STOP HOLDS THE ROUTE. A Motor drop is a latched demand; the
  truck stays where the stop left it and the route is still the route.
  When Motor returns, driving resumes with no operator ritual - a
  re-plan from the same pose gives the same polyline and a re-click only
  teaches the operator to automate the click.
"""
import argparse
import collections
import json
import math
import sys

import _donors                                            # noqa: F401

import follower                                           # noqa: E402
import route as route_module                              # noqa: E402
from stations import STATIONS                             # noqa: E402
from status_contract import MODE_AUTO                     # noqa: E402


class Nav2StateError(ValueError):
    """A state word or a payload this file will not put on the wire."""


# --------------------------- the vocabulary ---------------------------
# Spelled here and pinned against nav_core's own constants by
# tests/test_nav2_adapter_state.py. They are re-declared rather than
# imported because nav_core is the module being RETIRED: the adapter has
# to keep saying these words after that file is gone, and a test that
# compares the two is worth more than an import that hides the day they
# diverge.
IDLE, EN_ROUTE, HOLD = "IDLE", "EN-ROUTE", "HOLD"
SAFETY_STOP, ARRIVED = "SAFETY-STOP", "ARRIVED"
AVOID, NUDGE, BLOCKED = "AVOID", "NUDGE", "BLOCKED"

#: The whole contract vocabulary, including the two reserved words.
STATES = (IDLE, EN_ROUTE, HOLD, SAFETY_STOP, ARRIVED, AVOID, NUDGE,
          BLOCKED)
#: What this adapter is allowed to publish. AVOID and NUDGE are not in
#: it: Decision 3 retired them as emitted states.
EMITTED = (IDLE, EN_ROUTE, HOLD, SAFETY_STOP, ARRIVED, BLOCKED)

# ------------------------- the refusal grammar -------------------------
# BYTE FOR BYTE. Each of these is pinned by driving a real
# nav_core.NavCore into the refusal and comparing its `note`; the three
# that live in the rclpy shell are pinned against nav_node.py's source
# text, because that file cannot be imported without ROS.
ROUTE_REFUSED_MALFORMED = "route refused: malformed points"
ROUTE_REFUSED_SHORT = "route refused: fewer than two points"
ROUTE_REFUSED_ARRIVE_M = "route refused: unusable arrive_m"
ROUTE_REFUSED_MODE = "route refused: not in auto mode"
ROUTE_REFUSED_NO_POSE = "route refused: no pose yet"
ROUTE_REFUSED_UNREADABLE = "route refused: unreadable request"
GOAL_REFUSED_MODE = "goal refused: not in auto mode"
GOAL_REFUSED_NO_POSE = "goal refused: no pose yet"
NOTE_CANCELLED = "cancelled"
NOTE_MODE_LEFT_AUTO = "mode left auto"

#: THE BOOT POSTURE (Decision 6 step 5). Until the localiser's health
#: gate passes, `/auto/state` runs IDLE with this note and routes are
#: refused. It is a note and not a state word because the contract has
#: no word for "not ready" and inventing one would break every reader.
NOTE_LOCALISER_NOT_READY = "localiser not ready"
#: THE NO-PICTURE POSTURE (Decision 4). Nothing fresh within
#: nav2_pose.SENSOR_STALE_S: zeros flow, the route is HELD, and the
#: operator is told which of the two silences it is.
NOTE_POSE_STALE = "pose stale"


def goal_refused_unknown(station_id):
    """nav_core.on_goal's refusal, with the id the HMI actually sent."""
    return "goal refused: unknown station {}".format(station_id)


#: What `/auto/state` carries, in the order nav_core wrote it. The keys
#: are the contract; the ORDER is not, and is kept only so a diff of two
#: captured payloads reads the way an operator expects.
STATE_KEYS = ("state", "goal", "note", "route", "pose", "reversing",
              "arrive_m", "guard_min")


def _finite_or_none(value):
    """A float for JSON, or None where there is no number.

    THE NaN RULE, AND IT IS NOT THEORETICAL. nav_core's own docstring
    records the measured failure: an unchecked float() installed a NaN,
    `arrived()` was false against it for ever, and `state_json` emitted a
    bare NaN that no strict JSON parser will read. Routes can no longer
    carry one (they are refused at the door) but a TF composition can
    hand this file one, so the DUMP refuses it too - as `null`, which is
    the JSON for "there is no number here" and is exactly what nav_core
    already writes for an infinite `guard_min`.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class NavState(object):
    """The `/auto/state` document, and the rules about which word appears.

    It holds no clock and no I/O: the shell ticks it. `reversing` is set
    from the COMMAND (nav2_cmd.is_reversing on the traction actually
    published), not from a plan, because that is what the HMI's arrow
    means.
    """

    def __init__(self, plan=route_module.plan_route):
        self._plan = plan
        self.mode = None
        self.state = IDLE
        self.goal = None
        self.route = None
        self.note = NOTE_LOCALISER_NOT_READY
        self.reversing = False
        self.arrive_m = follower.ARRIVE_M
        #: False at boot (the localiser has not passed its gate) and
        #: again whenever the estimate goes stale. One flag, two
        #: reasons, and `pose_absent_note` says which.
        self.pose_ok = False
        self.pose_absent_note = NOTE_LOCALISER_NOT_READY
        #: The label ARRIVED was latched for. Per label, so a new order
        #: over the top of an arrival starts driving again.
        self._arrived_for = None

    # ------------------------------ inputs ------------------------------

    def on_mode(self, mode):
        """The vehicle's mode changed. Leaving auto cancels, by name."""
        self.mode = mode
        if mode != MODE_AUTO and self.state != IDLE:
            self.cancel(NOTE_MODE_LEFT_AUTO)

    def set_pose_ok(self, ok, absent_note=NOTE_POSE_STALE):
        """Does the adapter have a believed pose it may act on?

        THE STREAM KEEPS FLOWING EITHER WAY, and that is the one
        deliberate contract deviation in this file (Decision 4, named):
        nav_node stops publishing `/auto/state` entirely on a stale pose.
        Silence was the worse behaviour - the HMI's lamp simply froze -
        and nothing downstream depends on the gap.
        """
        ok = bool(ok)
        if ok and not self.pose_ok:
            self.pose_ok = True
            self.pose_absent_note = ""
            if self.state == HOLD:
                self.state = EN_ROUTE if self.route else IDLE
                self.note = ""
            elif self.state == IDLE and self.note == NOTE_LOCALISER_NOT_READY:
                self.note = ""
        elif not ok:
            self.pose_ok = False
            self.pose_absent_note = absent_note
            if self.state == EN_ROUTE:
                self.state = HOLD
                self.note = absent_note
        return self.pose_ok

    def on_route(self, points, arrive_m, label):
        """An externally planned polyline - the VDA agent's door.

        Returns True when it was ACCEPTED. Every refusal writes the note
        and touches nothing else; the last four lines are the only
        mutations here and they run or none of them do.
        """
        if self.mode != MODE_AUTO:
            self.note = ROUTE_REFUSED_MODE
            return False
        if not self.pose_ok:
            self.note = ROUTE_REFUSED_NO_POSE
            return False
        try:
            poly = []
            for point in points:
                x, y = float(point[0]), float(point[1])
                if not (math.isfinite(x) and math.isfinite(y)):
                    raise ValueError("non-finite coordinate")
                poly.append((x, y))
        except (TypeError, ValueError, IndexError):
            self.note = ROUTE_REFUSED_MALFORMED
            return False
        if len(poly) < 2:
            self.note = ROUTE_REFUSED_SHORT
            return False
        try:
            # Absent is the one way to ask for the default. Zero,
            # negative or NaN is a fault in the sender, and the arrival
            # test would never be true against any of them.
            radius = (follower.ARRIVE_M if arrive_m is None
                      else float(arrive_m))
            if not math.isfinite(radius) or radius <= 0.0:
                raise ValueError("arrive_m out of range")
        except (TypeError, ValueError):
            self.note = ROUTE_REFUSED_ARRIVE_M
            return False
        self._accept(str(label), poly, radius)
        return True

    def on_goal(self, station_id, pose_xy):
        """The HMI's station GO, and the one cancel door.

        AN EMPTY GOAL IS THE CANCEL and it is the ONLY cancel: that is
        what vda_agent's 5 s pump publishes and what it confirms on
        (IDLE plus no goal). KEPT, PLANNED THROUGH route.py EXACTLY AS
        TODAY (Decision 5) - route.py is pure, it stays, and the
        polyline it returns enters the same leg runner as a vda route.
        """
        if not station_id:
            self.cancel(NOTE_CANCELLED)
            return False
        if self.mode != MODE_AUTO:
            self.note = GOAL_REFUSED_MODE
            return False
        if not self.pose_ok:
            self.note = GOAL_REFUSED_NO_POSE
            return False
        poly = self._plan(tuple(pose_xy), station_id)
        if poly is None:
            self.note = goal_refused_unknown(station_id)
            return False
        self._accept(str(station_id), [tuple(p) for p in poly],
                     STATIONS[station_id].get("arrive_m",
                                              follower.ARRIVE_M))
        return True

    def _accept(self, label, poly, radius):
        self.goal, self.route, self.state = label, poly, EN_ROUTE
        self.note, self.reversing = "", False
        self.arrive_m = radius
        self._arrived_for = None

    def cancel(self, why=NOTE_CANCELLED):
        """Drop everything and say why. IDLE + no goal, in one tick."""
        self.goal, self.route, self.state, self.note = None, None, IDLE, why
        self.reversing = False
        self.arrive_m = follower.ARRIVE_M
        self._arrived_for = None

    # ----------------------------- verdicts -----------------------------

    def check_arrival(self, xy):
        """Latch ARRIVED the first tick the belief is inside `arrive_m`.

        Returns True only on the tick that LATCHES it. THE SAME
        MEASUREMENT MADE TWICE: vda_orders.Progress counts the released
        nodes on the same estimate at its own radius, and this reads the
        final point at the station's. Both now run on
        `/fN/est/odom` (Decision 4), which is what restores the
        invariant that made them agree in the first place.

        AND IT IS A LATCH. The vehicle rolling on past its own tolerance
        - which a 0.25 m checker at creep can easily do - does not
        un-arrive it, because the fleet has already been told.
        """
        if self.route is None or self.goal is None:
            return False
        if self._arrived_for == self.goal:
            return False
        if not follower.arrived((float(xy[0]), float(xy[1])),
                                self.route[-1], self.arrive_m):
            return False
        self._arrived_for = self.goal
        self.state, self.reversing = ARRIVED, False
        return True

    def accept_arrival(self):
        """Latch ARRIVED on NAV2's verdict rather than on our own radius.

        THE SAME LATCH, THROUGH THE OTHER DOOR. `check_arrival` is the
        adapter's own 20 Hz reading; this is the one the goal checker
        took, and the two are the same 0.25 m over two beliefs that can
        straddle it (nav2_watch.arrival_is_short, defect D6). It is
        idempotent for the same reason check_arrival is: the fleet has
        already been told.
        """
        if self.route is None or self.goal is None:
            return False
        if self._arrived_for == self.goal:
            return False
        self._arrived_for = self.goal
        self.state, self.reversing = ARRIVED, False
        return True

    def block(self, note):
        """A named nav2 failure or the adapter's own watchdog.

        THE GOAL IS KEPT AND THAT IS LOAD-BEARING. vda_agent reports
        `pathBlocked` only when the BLOCKED state carries OUR orderId; a
        BLOCKED that cleared the goal would be a body on the floor that
        nobody upstream ever hears about, and the fleet would keep
        granting the same corridor.
        """
        if not note:
            raise Nav2StateError(
                "BLOCKED without a note: `note` is the wire's only WHY "
                "and vda_agent quotes it verbatim into a VDA "
                "errorDescription")
        self.state, self.note = BLOCKED, note
        self.reversing = False
        return True

    def hold(self, note=""):
        """A BT recovery is running, or a leg is settling."""
        self.state, self.note = HOLD, note
        self.reversing = False
        return True

    def safety_stop(self):
        """Motor False or `/plc/status` stale. The route is HELD."""
        self.state = SAFETY_STOP
        self.reversing = False
        return True

    def resume(self):
        """Motor came back. Re-goal the current leg, no operator ritual.

        Returns True when this call is what resumed it, so the shell
        knows to re-send the leg goal. From anything but SAFETY-STOP it
        is not a transition and says so.
        """
        if self.state != SAFETY_STOP or self.route is None:
            return False
        self.state, self.note = EN_ROUTE, ""
        return True

    # ------------------------------ output ------------------------------

    def state_json(self, pose, guard_min_m):
        """The 10 Hz document, as strict JSON.

        `guard_min` is follower.sector_min on the live scan and is
        REPORTING ONLY (Decision 1): the speed policy that used to read
        it has no control role left, and the number stays on the wire
        because the HMI draws it.
        """
        if self.state not in EMITTED:
            raise Nav2StateError(
                "{!r} is not a state this adapter may publish. The "
                "contract vocabulary is {}; AVOID and NUDGE are reserved "
                "words and Decision 3 retired them as emitted states."
                .format(self.state, "/".join(EMITTED)))
        payload = collections.OrderedDict((
            ("state", self.state),
            ("goal", self.goal),
            ("note", self.note),
            ("route", [list(p) for p in self.route] if self.route else []),
            ("pose", [_finite_or_none(pose[0]), _finite_or_none(pose[1]),
                      _finite_or_none(pose[2])]),
            ("reversing", bool(self.reversing)),
            ("arrive_m", self.arrive_m),
            ("guard_min", (None if guard_min_m == float("inf")
                           else _finite_or_none(guard_min_m))),
        ))
        # allow_nan=False so a bug can never put a bare NaN on the wire:
        # the substitution above is the rule, and this is the check that
        # the rule was applied.
        return json.dumps(payload, allow_nan=False)


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_nav2_adapter_state.py is the real suite - it pins every
    string against nav_core and nav_node themselves, which this cannot
    do without importing the module being retired - and this is the
    version an operator can run on the rig without pytest.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    def driving():
        state = NavState()
        state.on_mode(MODE_AUTO)
        state.set_pose_ok(True)
        state.on_route([(0.0, 10.0), (7.0, 10.0)], 0.25, "order-1")
        return state

    boot = NavState()
    check("the boot posture is IDLE with the localiser note",
          boot.state == IDLE and boot.note == NOTE_LOCALISER_NOT_READY)
    boot.on_mode(MODE_AUTO)
    check("a route before the localiser is ready is refused 'no pose'",
          not boot.on_route([(0.0, 10.0), (7.0, 10.0)], 0.25, "L")
          and boot.note == ROUTE_REFUSED_NO_POSE)

    state = driving()
    check("acceptance assigns EN-ROUTE synchronously, with no note",
          state.state == EN_ROUTE and state.goal == "order-1"
          and state.note == "")
    check("a refusal over a driving truck changes NOTHING but the note",
          not state.on_route([(0.0, 0.0)], 0.25, "order-2")
          and state.state == EN_ROUTE and state.goal == "order-1"
          and state.note == ROUTE_REFUSED_SHORT)

    check("ARRIVED latches on the first tick inside arrive_m",
          not state.check_arrival((3.0, 10.0))
          and state.check_arrival((6.8, 10.0))
          and state.state == ARRIVED)
    check("and it answers True exactly once",
          not state.check_arrival((6.8, 10.0)) and state.state == ARRIVED)
    check("ARRIVED keeps the goal, because the fleet settles on it",
          state.goal == "order-1")

    state = driving()
    state.block("blocked: planner refused (error_code 205)")
    check("BLOCKED keeps the goal, or the fleet never hears about it",
          state.state == BLOCKED and state.goal == "order-1")

    state = driving()
    state.safety_stop()
    check("SAFETY-STOP holds the route and the goal",
          state.state == SAFETY_STOP and state.goal == "order-1"
          and state.route == [(0.0, 10.0), (7.0, 10.0)])
    check("Motor returning resumes without an operator ritual",
          state.resume() and state.state == EN_ROUTE)
    check("and resume from anywhere else is not a transition",
          not state.resume())

    state = driving()
    state.set_pose_ok(False)
    check("a stale pose HOLDS and says so, route intact",
          state.state == HOLD and state.note == NOTE_POSE_STALE
          and state.route is not None)
    check("and a fresh sample puts it back EN-ROUTE",
          state.set_pose_ok(True) and state.state == EN_ROUTE)

    state = driving()
    state.cancel()
    check("cancel is IDLE, no goal, 'cancelled', inside one tick",
          state.state == IDLE and state.goal is None
          and state.route is None and state.note == NOTE_CANCELLED)

    state = driving()
    state.on_mode("teleop")
    check("leaving auto cancels by name",
          state.state == IDLE and state.note == NOTE_MODE_LEFT_AUTO)

    state = driving()
    payload = json.loads(state.state_json((1.0, 2.0, 0.5), 3.0))
    check("the document carries exactly the eight contract keys",
          tuple(payload) == STATE_KEYS)
    text = state.state_json((float("nan"), 2.0, float("inf")),
                            float("inf"))
    check("a non-finite pose becomes null and never a bare NaN",
          "NaN" not in text and "Infinity" not in text
          and json.loads(text)["pose"] == [None, 2.0, None])
    check("an infinite guard_min is null, exactly as nav_core writes it",
          json.loads(text)["guard_min"] is None)

    state = driving()
    state.state = AVOID
    try:
        state.state_json((0.0, 0.0, 0.0), 1.0)
        check("a retired state word is refused by name", False)
    except Nav2StateError:
        check("a retired state word is refused by name", True)

    check("the station GO plans through route.py and takes its radius",
          _station_go_check())

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def _station_go_check():
    state = NavState()
    state.on_mode(MODE_AUTO)
    state.set_pose_ok(True)
    if not state.on_goal("S5", (-17.0, 10.0)):
        return False
    unknown = NavState()
    unknown.on_mode(MODE_AUTO)
    unknown.set_pose_ok(True)
    unknown.on_goal("S99", (-17.0, 10.0))
    return (state.route[-1] == (7.0, 4.25) and state.arrive_m == 0.25
            and state.state == EN_ROUTE
            and unknown.note == goal_refused_unknown("S99"))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the /auto/state contract state machine for "
                    "m6_ver2's nav2 adapter. The node that uses it is "
                    "nav2_adapter_node.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-simulator checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
