"""client_core.py - the VDA 5050 client's decisions, with no ROS or MQTT.

The shells feed events in; this returns EFFECTS out, as tuples the glue
executes verbatim:

    ("publish", subtopic, payload_dict, qos, retain)   MQTT out
    ("goal", "S7" | "")                                /auto/goal out

ONE DECISION OWNS THE GOAL. _desired_goal() is the only place that says
what /auto/goal should carry, and every input ends by reconciling the wire
against it. Supervision lost, paused, mode not auto, no order - each is a
reason for "", and "" through the same seam the HMI STOP uses is a
controlled stop by construction: nav parks, the gate keeps gating, torque
stays where the PLC put it.

SUPERVISION LOSS (SF-09, SC-12): on_broker(False) makes the desired goal ""
- controlled stop - and touches NOTHING else: the order is kept, no error
minted. on_broker(True) makes it the order's target again and the truck
resumes with no operator reset - permitted precisely because this never was
a safety stop. The watchdog PERIOD lives in the shell (the MQTT keepalive);
the reaction lives here.
"""
import actions_core
import factsheet_core
import order_core
import protocol
import state_core


class Client:

    def __init__(self, ident, stations, cfg):
        self.ident = ident
        self.cfg = cfg                  # map_id, state_interval_s, battery %
        self.book = order_core.OrderBook(stations)
        self.actions = actions_core.ActionBook()
        self.headers = protocol.Headers()
        self.nav = self.plc = self.fields = None
        self.mode = None
        self.paused = False
        self.battery = {"charge_pct": cfg["battery_charge_pct"],
                        "charging": False}
        self.connected = False
        self._goal_wire = ""            # what /auto/goal last heard from us
        self._last_state_s = None
        self._last_nav_state = None

    # ----- the one goal decision -----

    def _desired_goal(self):
        if not self.connected or self.paused or self.mode != "auto":
            return ""
        return self.book.target() or ""

    def _reconcile(self):
        want = self._desired_goal()
        if want == self._goal_wire:
            return []
        self._goal_wire = want
        return [("goal", want)]

    def _state_event(self, now_s):
        head = protocol.header(self.ident, self.headers, "state", now_s)
        payload = state_core.build_state(
            head, self.book, self.actions, self.nav, self.plc, self.fields,
            self.mode, self.paused, self.battery, self.cfg["map_id"])
        self._last_state_s = now_s
        return ("publish", "state", payload, 0, False)

    def _factsheet_event(self, now_s):
        head = protocol.header(self.ident, self.headers, "factsheet", now_s)
        payload = factsheet_core.build_factsheet(head, self.cfg["factsheet"])
        return ("publish", "factsheet", payload, 0, True)

    # ----- inputs from the broker side -----

    def on_broker(self, connected, now_s):
        self.connected = connected
        out = []
        if connected:
            out.append(("publish", "connection", protocol.connection_payload(
                self.ident, self.headers, protocol.ONLINE, now_s), 1, True))
            out.append(self._factsheet_event(now_s))   # on connect, spec 6.15
            out.append(self._state_event(now_s))
        return out + self._reconcile()

    def shutdown(self, now_s):
        """Graceful exit: OFFLINE, then the shell disconnects (spec 6.14)."""
        return [("goal", ""), ("publish", "connection",
                protocol.connection_payload(self.ident, self.headers,
                                            protocol.OFFLINE, now_s), 1, True)]

    def on_order(self, msg, now_s):
        if not protocol.addressed_to(msg, self.ident):
            return []
        verdict = self.book.receive(msg)
        if verdict == "ignored":
            return []
        return [self._state_event(now_s)] + self._reconcile()

    def on_instant_actions(self, msg, now_s):
        if not protocol.addressed_to(msg, self.ident):
            return []
        out = []
        for effect, arg in self.actions.receive(msg):
            if effect == "pause":
                self.paused = arg
            elif effect == "cancel":
                self.book.cancel()
            elif effect == "charging":
                self.battery["charging"] = arg
            elif effect == "factsheet":
                out.append(self._factsheet_event(now_s))
            # "state" needs no arm: every branch below publishes state
        out.append(self._state_event(now_s))
        return out + self._reconcile()

    # ----- inputs from the vehicle side -----

    def on_nav_state(self, nav, now_s):
        self.nav = nav
        out = []
        if (nav.get("state") == "ARRIVED"
                and nav.get("goal") == self.book.target()
                and self.book.arrived(nav["goal"])):
            out.append(self._state_event(now_s))
        elif nav.get("state") != self._last_nav_state:
            out.append(self._state_event(now_s))   # driving flip is an event
        self._last_nav_state = nav.get("state")
        return out + self._reconcile()

    def on_plc_status(self, plc, now_s):
        self.plc = plc
        return []

    def on_fields(self, fields, now_s):
        self.fields = fields
        return []

    def on_mode(self, mode, now_s):
        if mode == self.mode:
            return []
        self.mode = mode
        return [self._state_event(now_s)] + self._reconcile()

    def tick(self, now_s):
        """The 30 s floor (spec 6.10): event-driven, at latest every
        state_interval_s. Only while connected - a dead broker hears
        nothing and the backlog would be stale news on reconnect."""
        if not self.connected:
            return []
        if (self._last_state_s is None
                or now_s - self._last_state_s >= self.cfg["state_interval_s"]):
            return [self._state_event(now_s)]
        return []
