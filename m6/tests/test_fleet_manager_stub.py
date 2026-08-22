"""The manager's two failure habits, asked without a broker.

test_fleet_manager_mqtt.py runs the real service against a real
mosquitto, which is where the protocol is proven - but two of the
manager's rules are about what happens when the wire ISN'T there, and a
broker that is up cannot be asked those. A stub paho client can: it
returns the return code paho itself returns when a publish is made off
the wire, and it drops the message exactly as paho drops it.

  1. A qos-0 publish made while disconnected is DROPPED, not queued.
     If the manager read the call as delivery it would advance the task
     to ASSIGNED on an order no truck ever heard - and the fleet's own
     dwell override would then hold that vehicle busy for a leg that
     never began. The task would be stuck forever. So the funnel reads
     the return code and the task stays where it was.
  2. The retained status document is a SCREEN and is trimmed; the
     manager's book is not. Trimming the book would weaken the
     duplicate-taskId refusal, and a taskId has to stay refused for the
     whole run rather than until its task scrolled off a display.

M6.4 ADDED A THIRD REASON TO BE HERE, and it is the strongest: TRAFFIC
IS A CLOCK-FREE DECISION. Who holds which piece of floor, whose base
grows and who yields is decided by a pure ledger and a pass over the
task list, and asking those questions against a real broker means
asking them through two vehicles' publish cadences and a 10 Hz drain -
which is how a traffic bug becomes a flaky test instead of a failing
one. The scenarios below drive the manager one state at a time, so the
head-on, the extension, the parked hulk and the deadlock all happen at
a moment the test names.

RESERVATION IS PROCESS DECONFLICTION AND NOTHING BELOW ASSERTS
OTHERWISE. No test here says a truck was stopped: the scanners, the
F-model and the onboard guards are the only things that do that, and
what is measured here is only ever what the FLEET asked for.
"""
import json
import logging
import os
import sys
import time

import pytest

mqtt = pytest.importorskip("paho.mqtt.client")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import fleet_manager as fm                          # noqa: E402
import floor as fl                                  # noqa: E402
import traffic as tr                                # noqa: E402
import vda_orders as vo                             # noqa: E402
from order_builder import leg_points                # noqa: E402
from stations import STATIONS                       # noqa: E402


class StubInfo:
    def __init__(self, rc):
        self.rc = rc

    def is_published(self):
        return self.rc == mqtt.MQTT_ERR_SUCCESS

    def wait_for_publish(self, timeout=None):
        return None


class StubClient:
    """paho's surface as the manager uses it, and its DROP semantics:
    when publish reports anything but success the message is gone, so
    the stub does not record it either."""

    def __init__(self, *args, **kwargs):
        self.rc = mqtt.MQTT_ERR_SUCCESS
        self.published = []
        self.subscriptions = []
        self.on_connect = self.on_disconnect = self.on_message = None

    def reconnect_delay_set(self, **kwargs):
        pass

    def connect_async(self, *args, **kwargs):
        pass

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def subscribe(self, topics, qos=0):
        self.subscriptions.append(topics)

    def publish(self, topic, payload, qos=0, retain=False):
        if self.rc == mqtt.MQTT_ERR_SUCCESS:
            self.published.append((topic, json.loads(payload), qos, retain))
        return StubInfo(self.rc)


@pytest.fixture
def fleet(monkeypatch):
    """A real FleetManager whose only fake part is the socket."""
    stub = StubClient()
    monkeypatch.setattr(fm.mqtt, "Client", lambda *a, **k: stub)
    manager = fm.FleetManager()
    yield manager, stub
    manager.close()


def idle(manager, serial, station_id, now):
    """A truck standing at a station, reporting as of this instant."""
    row = fm._new_vehicle()
    row.update({"connection": "ONLINE", "operating_mode": "AUTOMATIC",
                "position": (STATIONS[station_id]["x"],
                             STATIONS[station_id]["y"]),
                "state_rx": now})
    manager.vehicles[serial] = row
    return row


def submit(manager, task_id, src="S5", dst="S4"):
    manager._on_submit(json.dumps(
        {"taskId": task_id, "from": src, "to": dst}).encode())
    return manager.tasks[-1]


def orders(stub):
    return [msg for topic, msg, _, _ in stub.published
            if topic.endswith("/order")]


# ---- 1. the publish funnel ----
def test_a_leg1_that_never_reached_the_wire_leaves_the_task_queued(fleet):
    manager, stub = fleet
    now = time.monotonic()
    idle(manager, "f1", "S1", now)
    task = submit(manager, "t-1")

    stub.rc = mqtt.MQTT_ERR_NO_CONN
    manager._assign(now)
    assert orders(stub) == []                 # dropped, as paho drops it
    assert task["state"] == "QUEUED"
    assert task["assignee"] is None and task["order_id"] is None
    assert manager.tasks[0] is task            # still the queue head

    stub.rc = mqtt.MQTT_ERR_SUCCESS
    manager._assign(now)
    assert task["state"] == "ASSIGNED_LEG1" and task["assignee"] == "f1"
    assert len(orders(stub)) == 1
    assert orders(stub)[0]["orderId"] == task["order_id"]


def test_a_leg2_that_never_reached_the_wire_stays_in_the_dwell(fleet):
    manager, stub = fleet
    now = time.monotonic()
    idle(manager, "f1", "S1", now)
    task = submit(manager, "t-2")
    manager._assign(now)
    task["state"] = "DWELL"
    manager.dwell_until[task["task_id"]] = now - 0.1
    leg1_order = task["order_id"]

    stub.rc = mqtt.MQTT_ERR_NO_CONN
    manager._expire_dwells(now)
    assert task["state"] == "DWELL" and task["order_id"] == leg1_order
    assert task["task_id"] in manager.dwell_until   # the deadline stands
    assert len(orders(stub)) == 1                   # leg 1 only

    stub.rc = mqtt.MQTT_ERR_SUCCESS
    manager._expire_dwells(now)
    assert task["state"] == "ASSIGNED_LEG2"
    assert len(orders(stub)) == 2
    assert task["task_id"] not in manager.dwell_until


def test_a_dropped_publish_is_not_a_refusal_and_stands_nobody_down(fleet):
    """The vehicle did nothing wrong: _refuse_order's brake is for an
    order the builder or the graph could not make, and applying it here
    would stand a whole fleet down for an outage that fixes itself."""
    manager, stub = fleet
    now = time.monotonic()
    idle(manager, "f1", "S1", now)
    submit(manager, "t-3")
    stub.rc = mqtt.MQTT_ERR_NO_CONN
    manager._assign(now)
    assert manager.vehicles["f1"]["not_eligible"] is False
    assert manager.refused == []


class Catcher(logging.Handler):
    """The manager's own log, caught at the source.

    NOT caplog: pytest's capture handler sits on the ROOT logger and
    another test file in this suite leaves it detached by the time this
    one runs - the warning then reaches stderr through logging's
    last-resort handler and the fixture sees nothing. Listening on the
    logger the manager actually holds is both simpler and immune to
    whatever else the suite has done to logging.
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.said = []

    def emit(self, record):
        self.said.append(record.getMessage())


def test_the_wire_warning_is_throttled_but_the_retry_is_not(fleet):
    manager, stub = fleet
    now = time.monotonic()
    idle(manager, "f1", "S1", now)
    submit(manager, "t-4")
    stub.rc = mqtt.MQTT_ERR_NO_CONN
    catcher = Catcher()
    manager.log.addHandler(catcher)
    manager.log.setLevel(logging.WARNING)
    try:
        for _ in range(20):
            manager._assign(now)
    finally:
        manager.log.removeHandler(catcher)
    said = [m for m in catcher.said if "not published" in m]
    assert len(said) == 1                  # twenty tries, one line
    assert "DROPPED" in said[0] and "QUEUED" in said[0]
    assert manager.tasks[0]["state"] == "QUEUED"


def test_a_cancel_that_could_not_be_sent_is_not_forgotten(fleet):
    """The one flow cancelOrder exists in cannot be retried by a timer -
    it fires on a vehicle RETURNING - so a dropped cancel must at least
    leave the order id where the next return will find it."""
    manager, stub = fleet
    now = time.monotonic()
    row = idle(manager, "f1", "S1", now)
    task = submit(manager, "t-5")
    manager._assign(now)
    order_id = task["order_id"]        # the requeue below clears the task's
    manager._on_connection("f1", row, {"connectionState": "CONNECTIONBROKEN"})
    assert manager.stale["f1"] == order_id
    assert task["state"] == "QUEUED"

    stub.rc = mqtt.MQTT_ERR_NO_CONN
    manager._on_connection("f1", row, {"connectionState": "ONLINE"})
    assert manager.stale.get("f1") == order_id

    stub.rc = mqtt.MQTT_ERR_SUCCESS
    manager._on_connection("f1", row,
                           {"connectionState": "CONNECTIONBROKEN"})
    manager._on_connection("f1", row, {"connectionState": "ONLINE"})
    assert "f1" not in manager.stale
    cancels = [msg for topic, msg, _, _ in stub.published
               if topic.endswith("/instantActions")]
    assert len(cancels) == 1
    assert cancels[0]["actions"][0]["actionType"] == "cancelOrder"


# ---- 2. the screen is trimmed, the book is not ----
def _done(manager, task_id, when):
    task = submit(manager, task_id)
    task["state"] = "DONE"
    task["done_ts"] = when
    return task


def test_the_document_keeps_the_last_five_completions_and_a_count(fleet):
    manager, _ = fleet
    now = time.monotonic()
    for i in range(8):
        _done(manager, "t-{}".format(i), 1000.0 + i)
    live = submit(manager, "t-live")

    doc = manager._status(now)
    assert doc["done_count"] == 8
    assert [t["task_id"] for t in doc["tasks"]] == \
        ["t-live", "t-3", "t-4", "t-5", "t-6", "t-7"]
    assert doc["tasks"][0]["state"] == live["state"]
    assert len(manager.tasks) == 9          # the book keeps every one


def test_trimming_does_not_weaken_the_duplicate_task_id_refusal(fleet):
    manager, _ = fleet
    for i in range(8):
        _done(manager, "t-{}".format(i), 1000.0 + i)
    doc = manager._status(time.monotonic())
    assert "t-0" not in [t["task_id"] for t in doc["tasks"]]

    # ...and it is still refused, by the door itself, not by a helper.
    manager._on_submit(json.dumps(
        {"taskId": "t-0", "from": "S5", "to": "S4"}).encode())
    assert len(manager.tasks) == 8
    assert manager.refused[-1] == {"taskId": "t-0",
                                   "why": "taskId t-0 is already known"}


def test_a_completion_changes_the_shape_so_the_screen_is_republished(
        fleet):
    manager, _ = fleet
    now = time.monotonic()
    for i in range(8):
        _done(manager, "t-{}".format(i), 1000.0 + i)
    before = manager._shape(manager._status(now))
    _done(manager, "t-8", 1008.0)
    assert manager._shape(manager._status(now)) != before


# ---- the cancel that has to be chased (M6.3 Fleet Gate 4) ----
# One successful publish is not one landed cancel. The gate measured a
# vehicle that received a cancelOrder, reported the action FINISHED and
# kept driving for 37.09 s. The agent now confirms its own stop against
# nav; this side keeps the manager honest about what it has SEEN, which
# is only ever the vehicle's own state stream.


def cancels(stub):
    return [msg for topic, msg, _, _ in stub.published
            if topic.endswith("/instantActions")]


def driving(order_id, x=0.0, y=0.0):
    return {"operatingMode": "AUTOMATIC",
            "agvPosition": {"x": x, "y": y},
            "orderId": order_id,
            "nodeStates": [{"nodeId": "wp1", "sequenceId": 0,
                            "released": True}]}


def _returned_holding(manager, stub):
    """A vehicle lost mid-task and back on the wire, cancel sent."""
    now = time.monotonic()
    row = idle(manager, "f1", "S1", now)
    task = submit(manager, "t-chase")
    manager._assign(now)
    order_id = task["order_id"]
    manager._on_connection("f1", row,
                           {"connectionState": "CONNECTIONBROKEN"})
    manager._on_connection("f1", row, {"connectionState": "ONLINE"})
    assert len(cancels(stub)) == 1
    assert "f1" not in manager.stale
    assert manager.cancelled["f1"]["order_id"] == order_id
    return row, order_id, now


def test_a_cancel_the_vehicle_ignores_is_re_sent(fleet):
    manager, stub = fleet
    row, order_id, now = _returned_holding(manager, stub)
    still = driving(order_id)

    manager._on_state("f1", row, still, now)          # the grace starts here
    assert len(cancels(stub)) == 1
    manager._on_state("f1", row, still, now + 1.0)    # inside the grace
    assert len(cancels(stub)) == 1, "shouted over the reply it waits for"
    manager._on_state("f1", row, still, now + 4.0)    # past grace and period
    assert len(cancels(stub)) == 2, "the cancel was never chased"
    manager._on_state("f1", row, still, now + 5.0)    # throttled
    assert len(cancels(stub)) == 2
    manager._on_state("f1", row, still, now + 9.0)
    assert len(cancels(stub)) == 3

    # THE VEHICLE'S OWN STATE ENDS THE CHASE, never our publish.
    manager._on_state("f1", row, dict(still, orderId="", nodeStates=[]),
                      now + 10.0)
    assert "f1" not in manager.cancelled
    manager._on_state("f1", row, dict(still, orderId="", nodeStates=[]),
                      now + 30.0)
    assert len(cancels(stub)) == 3, "still chasing an order it let go of"


def test_a_vehicle_that_never_lets_go_is_named_and_the_chase_stops(fleet):
    manager, stub = fleet
    row, order_id, now = _returned_holding(manager, stub)
    still = driving(order_id)
    for step in range(0, 40, 4):
        manager._on_state("f1", row, still, now + step)
    assert len(cancels(stub)) == 1 + fm.CANCEL_RETRY_MAX, (
        "the manager kept shouting past its own cap")
    assert "f1" not in manager.cancelled
    named = [r for r in manager.refused if r["taskId"] == order_id]
    assert named and "never dropped" in named[0]["why"], (
        "a truck that ignored every cancelOrder is not on the "
        "operator's screen")
    # And it stays stopped: no further state re-arms the chase.
    manager._on_state("f1", row, still, now + 100.0)
    assert len(cancels(stub)) == 1 + fm.CANCEL_RETRY_MAX


# =====================================================================
# M6.4 - the manager runs traffic
# =====================================================================
# The dock aisle is one straight corridor of graph nodes, which is why
# every scenario below is staged on it: two trucks on one aisle is the
# whole problem, and these are its coordinates.
S1_XY = (STATIONS["S1"]["x"], STATIONS["S1"]["y"])       # (-3.0, -5.5)
WEST = (-6.0, -5.5)          # one dock node west of S1
EAST = (0.0, -5.5)           # one dock node east of S1
# S4 is the other shape a station comes in and the one M6.4's Gate 2
# broke on: a 2.5 m spur off the dock aisle, so the truck that is in it
# has exactly one way out and that way is somebody else's way in.
S4_XY = (STATIONS["S4"]["x"], STATIONS["S4"]["y"])       # (6.0, -8.0)
S4_ENTRY = (6.0, -5.5)       # the junction the spur lands on
FAR_EAST = (8.0, -5.5)       # one dock node east of that junction


def traffic_fleet(monkeypatch, traffic_on=True):
    stub = StubClient()
    monkeypatch.setattr(fm.mqtt, "Client", lambda *a, **k: stub)
    manager = fm.FleetManager(traffic_on=traffic_on)
    return manager, stub


@pytest.fixture
def floor(monkeypatch):
    manager, stub = traffic_fleet(monkeypatch)
    yield manager, stub
    manager.close()


@pytest.fixture
def open_floor(monkeypatch):
    """The same manager with --no-traffic: every route granted whole."""
    manager, stub = traffic_fleet(monkeypatch, traffic_on=False)
    yield manager, stub
    manager.close()


class Truck:
    """A vehicle the manager can hear, with no broker in between.

    It carries the three habits the traffic loop is built on. It takes
    orders through the VEHICLE'S OWN DOOR (vda_orders.accept_order, the
    same function vda_agent calls), so an order the real truck would
    refuse is refused here too. It drives only the RELEASED part of what
    it was given and stops at the end of it, with no pause action and
    nothing to un-stick - which is what makes a horizon a traffic
    primitive rather than a hint. And its orderUpdateId moves only when
    it has taken an update, because that field is the only thing the
    manager is allowed to read an extension back from.
    """

    def __init__(self, manager, stub, serial, xy, mode="AUTOMATIC"):
        self.manager, self.stub, self.serial = manager, stub, serial
        self.xy = (float(xy[0]), float(xy[1]))
        self.mode = mode
        self.order = None
        self.reached = 0
        self.last = ("", 0)
        self.errors = []
        self.seen = 0
        self.row = manager.vehicles.setdefault(serial, fm._new_vehicle())
        self.row["connection"] = "ONLINE"

    # ---- what the manager said to this truck ----
    def inbox(self):
        topic = "uagv/v2/amragent/{}/order".format(self.serial)
        return [m for t, m, _, _ in self.stub.published if t == topic]

    def legs(self):
        """Distinct orderIds, in the order they arrived. An extension
        rides the SAME orderId, so counting messages would count it as
        a leg."""
        out = []
        for msg in self.inbox():
            if not out or out[-1] != msg["orderId"]:
                out.append(msg["orderId"])
        return out

    def take(self):
        for msg in self.inbox()[self.seen:]:
            self._take(msg)
        self.seen = len(self.inbox())
        return self

    def _take(self, msg):
        verdict, reason = vo.accept_order(msg, self.order,
                                          bool(self.node_states()), self.mode)
        if verdict == "ignore":
            return
        if verdict == "reject":
            self.errors = [{
                "errorType": "orderError", "errorLevel": "WARNING",
                "errorDescription": reason,
                "errorReferences": [{"referenceKey": "orderId",
                                     "referenceValue": msg["orderId"]}]}]
            return
        if verdict == "accept":
            self.reached, self.last = 0, ("", 0)
        self.order = msg

    # ---- what this truck is driving ----
    def released(self):
        return [] if self.order is None \
            else [n for n in self.order["nodes"] if n["released"]]

    def horizon(self):
        return [] if self.order is None \
            else [n for n in self.order["nodes"] if not n["released"]]

    def node_states(self):
        return [{"nodeId": n["nodeId"], "sequenceId": n["sequenceId"],
                 "released": True} for n in self.released()[self.reached:]] \
            + [{"nodeId": n["nodeId"], "sequenceId": n["sequenceId"],
                "released": False} for n in self.horizon()]

    def drive(self):
        """To the end of the released base and no further - the truck
        stops there by itself, which is the whole point of a horizon."""
        rel = self.released()
        if rel:
            node = rel[-1]
            self.xy = (node["nodePosition"]["x"], node["nodePosition"]["y"])
            self.last = (node["nodeId"], node["sequenceId"])
            self.reached = len(rel)
        return self

    def refuse_next_update(self):
        """The one refusal that is a TIMING answer: the truck cannot take
        this update right now (a cancel in flight, a mode that flicked)
        and says so against the order it is already driving."""
        self.errors = [{
            "errorType": "orderError", "errorLevel": "WARNING",
            "errorDescription": "busy - try again",
            "errorReferences": [{"referenceKey": "orderId",
                                 "referenceValue": self.order["orderId"]}]}]
        return self

    def state(self, now):
        msg = {"operatingMode": self.mode,
               "agvPosition": {"x": self.xy[0], "y": self.xy[1]},
               "orderId": "" if self.order is None else self.order["orderId"],
               "orderUpdateId": 0 if self.order is None
               else self.order["orderUpdateId"],
               "lastNodeId": self.last[0],
               "lastNodeSequenceId": self.last[1],
               "nodeStates": self.node_states(), "errors": list(self.errors)}
        self.errors = []
        self.manager._on_state(self.serial, self.row, msg, now)
        return msg


def turn(manager, trucks, now):
    """One drain's worth of work, without the inbox: every truck reports,
    then the dwells, then the floor, then one assignment - and the trucks
    read whatever the manager said, so a turn is a whole round trip.

    `stuck` is cleared where drain() clears it - once, before the two
    calls that write it - so a leg-2 sentence survives the turn that
    found it, exactly as it does on the wire."""
    for truck in trucks:
        truck.take().state(now)
    manager.floor.stuck.clear()
    manager._expire_dwells(now)
    manager.floor.traffic_pass(now)
    manager._assign(now)
    for truck in trucks:
        truck.take()


def base_of(truck):
    return [n["nodeId"] for n in truck.released()]


def horizon_of(truck):
    return [n["nodeId"] for n in truck.horizon()]


def head_on(manager, stub, now, to1="S4"):
    """The M6.3 jam, staged: f1 west of S1 and f2 east of it, both told
    to pick up at S1. f1's own dropoff decides whether it then drives
    back east through f2 (the jam, `to1="S4"`) or away west (the
    corridor draining, `to1="S2"`).

    This is Gate 4's own scenario (2026-08-22: f2 held 2.65 m behind f1
    with no way out but an operator) reduced to two trucks, one aisle
    and no clock. Returns (f1, f2). f1 wins t-1 on the tie-break: both
    trucks are 3.0 m from S1 and fleet_core keeps the lower serial.
    """
    f1 = Truck(manager, stub, "f1", WEST)
    f2 = Truck(manager, stub, "f2", EAST)
    submit(manager, "t-1", "S1", to1)
    submit(manager, "t-2", "S1", "S4")
    turn(manager, (f1, f2), now)          # f1 takes t-1: it is the nearer
    turn(manager, (f1, f2), now)          # f2 takes t-2, or what is left
    return f1, f2


def drains(manager, stub, now):
    """The same two trucks, but f1's transport takes it AWAY from f2:
    it picks up at S1 and drives west to S2, so the node f2 is waiting
    for comes free under it. Returns (f1, f2) with f1 already gone; one
    more turn is what extends f2's base."""
    f1, f2 = head_on(manager, stub, now, to1="S2")
    f1.drive()                            # f1 lands on S1
    turn(manager, (f1, f2), now)          # ...arrives; the dwell starts
    manager.dwell_until["t-1"] = now - 1.0
    turn(manager, (f1, f2), now)          # leg 2 goes out, westward
    f1.drive()                            # and f1 drives away to S2
    return f1, f2


# ---- 3. the base is what the floor granted ----
def test_a_taken_corridor_comes_back_as_a_partial_base(floor):
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = head_on(manager, stub, now)

    # f1 was nearest and got its whole leg: one hop east onto S1.
    assert base_of(f1) == ["wp1", "S1"] and horizon_of(f1) == []
    # f2 wants S1 too, and S1 is under f1's reservation. It is given the
    # node it is standing on and the rest as horizon - an honest wait,
    # not a re-route and not a pause action.
    assert horizon_of(f2) == ["S1"], "f2 was routed onto a taken node"
    assert base_of(f2) == ["wp1"]
    assert vo.validate_order(f2.inbox()[-1]) == "", \
        "the manager published a horizon order the vehicle would reject"
    doc = manager._status(now)
    assert doc["traffic"]["enabled"] is True
    assert doc["traffic"]["waiting"]["f2"] == "(-3.0,-5.5)"
    assert doc["traffic"]["bases"]["t-2"] == [1, 1]


def test_a_second_vehicle_is_held_at_a_node_and_never_given_a_zero_base(
        floor):
    """A grant of nothing is not an order. When even the node under the
    truck belongs to somebody else there is no base to send, so the leg
    simply does not go out this pass - rather than an order with a
    horizon first node, which the vehicle's own door refuses."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", S1_XY)
    f2 = Truck(manager, stub, "f2", S1_XY)      # nose to tail on one node
    submit(manager, "t-1", "S1", "S4")
    submit(manager, "t-2", "S1", "S4")
    for _ in range(4):
        turn(manager, (f1, f2), now)

    assert len(f1.legs()) == 1
    assert f2.inbox() == [], "an order went out on a floor grant of nothing"
    queued = [t for t in manager.tasks if t["state"] == "QUEUED"]
    assert [t["task_id"] for t in queued] == ["t-2"]
    # ...and it is said once, not ten times a second.
    assert manager.floor.said_blocked["f2"].startswith("f2 leg1")


def test_the_base_grows_by_one_update_id_when_the_corridor_drains(floor):
    """The extension, end to end: f2 waits, f1 leaves S1, f2's base grows
    and the order that carries it is orderUpdateId 1 on the SAME orderId
    with the already-driven part untouched."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = head_on(manager, stub, now, to1="S2")
    before = f2.inbox()[-1]
    assert before["orderUpdateId"] == 0
    assert horizon_of(f2) == ["S1"]

    f1.drive()                              # f1 lands on S1
    turn(manager, (f1, f2), now)            # ...arrives, dwell starts
    assert manager.tasks[0]["state"] == "DWELL"
    assert len(f2.inbox()) == 1, "S1 is still under f1's body"

    manager.dwell_until["t-1"] = now - 1.0
    turn(manager, (f1, f2), now)            # f1's leg 2 goes out, westward
    assert len(f2.inbox()) == 1, "f1 has not moved off S1 yet"
    f1.drive()                              # ...and f1 drives away to S2
    turn(manager, (f1, f2), now)

    grown = f2.inbox()[-1]
    assert grown["orderUpdateId"] == 1
    assert grown["orderId"] == before["orderId"], "a new leg, not a growth"
    assert vo.accept_order(grown, before, True, "AUTOMATIC") == ("extend", "")
    assert [n["nodeId"] for n in grown["nodes"] if n["released"]] == \
        ["wp1", "S1"]
    assert f2.legs() == [before["orderId"]], "the truck saw a second leg"
    # AND THE TRUCK NEVER RE-DRIVES WHAT IT PASSED: lastNodeId only ever
    # moves forward across the update.
    f2.take()
    assert f2.last == ("", 0), "the truck had not reached wp1 yet"
    f2.drive()
    assert f2.last[0] == "S1"


def test_an_extension_waits_for_the_vehicle_to_confirm_the_last_one(floor):
    """orderUpdateId must be exactly one more than the EXECUTING order,
    so a manager that fired the next extension before the truck had
    taken the previous one would be sending updates the vehicle is
    required to refuse. The confirmation is read from the state's own
    orderUpdateId - never from a route count, because a horizon-only
    extension publishes no new route at all."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = drains(manager, stub, now)

    f1.state(now)                                 # f1 is off S1
    manager.floor.traffic_pass(now)                    # the extension goes out
    assert len(f2.inbox()) == 2
    trf = next(t for t in manager.tasks
               if t["task_id"] == "t-2")["traffic"]
    assert trf["pending"] == (1, 2)
    for _ in range(5):                            # f2 has not answered yet
        manager.floor.traffic_pass(now)
    assert len(f2.inbox()) == 2, "a second update before the first landed"

    f2.take().state(now)                          # ...now it has
    assert trf["pending"] is None and trf["update_id"] == 1
    assert trf["released"] == 2


def test_a_refused_extension_is_a_timing_answer_and_the_task_survives(
        floor):
    """A truck may refuse an update for a reason that is pure timing.
    The leg it is driving is untouched by that, so requeueing the whole
    transport would throw away a job because the fleet asked half a
    second early. The pending extension is dropped and the next pass
    asks again."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = drains(manager, stub, now)
    task = next(t for t in manager.tasks if t["task_id"] == "t-2")

    f1.state(now)                             # f1 is off S1
    manager.floor.traffic_pass(now)
    assert task["traffic"]["pending"] == (1, 2)
    f2.seen = len(f2.inbox())                 # the update never landed
    f2.refuse_next_update().state(now)

    assert task["state"] == "ASSIGNED_LEG1", "a refused update lost the task"
    assert task["assignee"] == "f2"
    assert task["traffic"]["pending"] is None
    assert task["traffic"]["ext_refused"] == 1
    assert manager.vehicles["f2"]["not_eligible"] is False
    manager.floor.traffic_pass(now)                # ...and it is asked again
    assert len(f2.inbox()) == 3
    assert f2.inbox()[-1]["orderUpdateId"] == 1


# ---- 4. deadlock ----
def deadlocked(manager, stub, now):
    """f1 stopped on S1 asking for the node east of it, f2 stopped on
    that node asking for S1. Nose to nose, each standing on exactly what
    the other needs.

    Stopped one step SHORT of the traffic pass on purpose: the cycle is
    what the tests below want to look at before anything is done about
    it. Returns (f1, f2).
    """
    f1, f2 = head_on(manager, stub, now)
    f1.drive()                                # f1 lands on S1
    turn(manager, (f1, f2), now)              # arrived, dwell starts
    manager.dwell_until["t-1"] = now - 1.0
    for truck in (f1, f2):
        truck.take().state(now)
    manager._expire_dwells(now)               # leg 2 goes east, into f2
    f1.take()
    return f1, f2


def test_a_swap_deadlock_is_named_and_never_pretended_resolved(floor):
    """WAIT-DIE CANNOT BREAK THIS ONE AND THE FLEET SAYS SO.

    Once every truck in a cycle has stopped at the end of its base it
    holds exactly one element - the node under its own body, everything
    behind it having been released as it passed. So the contested
    element is always GROUND UNDER A VEHICLE, and the youngest yielding
    keeps precisely that and frees nothing at all. The cycle re-forms
    next pass, and again, and again: a livelock dressed as a resolution.
    The manager measures what the yield freed, and when it freed nothing
    it refuses the younger task by name instead of claiming a fix.
    """
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = deadlocked(manager, stub, now)

    assert base_of(f1) == ["wp1"], "f1's leg 2 should stop on S1 itself"
    assert manager.floor.waiting_on("f1") == (0.0, -5.5)
    assert manager.floor.waiting_on("f2") == S1_XY
    assert set(manager.floor.find_cycle() or []) == {"f1", "f2"}

    manager.floor.traffic_pass(now)
    doc = manager._status(now)
    assert doc["traffic"]["blocked"], "the deadlock is nowhere on the screen"
    said = doc["traffic"]["blocked"][-1]
    assert said["vehicles"] == ["f1", "f2"] and said["task"] == "t-2"
    assert "swap deadlock" in said["why"] and "has to be moved" in said["why"]
    assert doc["traffic"]["yields"] == [], "a yield that freed nothing"
    assert any("swap deadlock" in r["why"] for r in doc["refused"])
    # The YOUNGER task is the one refused, and it goes back to the head
    # of the queue rather than being lost.
    assert manager.tasks[0]["task_id"] == "t-2"
    assert manager.tasks[0]["state"] == "QUEUED"


def test_a_yield_that_frees_floor_is_logged_and_the_task_is_kept(floor):
    """The other half of wait-die, which IS reachable: a hold can outrun
    the base the vehicle was told about, because the ledger grants before
    the extension is published and an extension can fail to land (the
    wire drops, the truck refuses it). Floor the truck was never told
    about is floor the fleet may take back, so here the youngest yields
    for real - and keeps its task, its route and its submit time."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = deadlocked(manager, stub, now)
    younger = next(t for t in manager.tasks if t["task_id"] == "t-2")
    submitted = younger["submitted_ts"]
    # An extension that was granted and never landed: the ledger holds
    # one element more than the truck's base.
    manager.floor.hold("f2", tr.route_elements([(0.0, -5.5), (3.0, -5.5)]))
    manager.floor.hold("f2", tr.route_elements([(0.0, -5.5), S1_XY]))
    assert len(manager.floor.held_by("f2")) == 3

    manager.floor.traffic_pass(now)
    doc = manager._status(now)
    assert doc["traffic"]["yields"], "nothing was recorded as a yield"
    gave = doc["traffic"]["yields"][-1]
    assert gave["vehicle"] == "f2" and gave["with"] == ["f1"]
    assert gave["freed"] == 2 and gave["task"] == "t-2"
    assert doc["traffic"]["blocked"] == []
    # THE TASK IS NOT LOST AND ITS AGE IS NOT RESTAMPED. Restamping is
    # the livelock: the oldest task in the cell would become the
    # youngest on the floor and yield to whoever it just gave way to.
    assert younger["state"] == "ASSIGNED_LEG1"
    assert younger["assignee"] == "f2"
    assert younger["submitted_ts"] == submitted
    assert "f2" in doc["traffic"]["yielded"]


def test_the_retry_pass_walks_the_tasks_oldest_first(floor):
    """THE ANTI-LIVELOCK RULE, asked directly. Walk the tasks in any
    other order and a younger task re-grabs the corridor the older one
    just yielded, six passes run and nothing moves. The key is the
    SUBMIT time, and neither a yield nor a requeue rewrites it."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = head_on(manager, stub, now)
    order = []
    manager.floor.retry_hold = lambda task: order.append(task["task_id"])
    manager.tasks.sort(key=lambda t: t["task_id"], reverse=True)
    manager.floor.traffic_pass(now)
    assert order == ["t-1", "t-2"], "the younger task was served first"

    # A requeue puts a task back at the HEAD of the queue and leaves its
    # submit time exactly where it was.
    before = dict((t["task_id"], t["submitted_ts"]) for t in manager.tasks)
    manager._requeue("t-1", "measured")
    assert all(t["submitted_ts"] == before[t["task_id"]]
               for t in manager.tasks)


# ---- 5. loss, and the parked hulk ----
def test_a_lost_truck_frees_the_corridor_and_keeps_the_node_under_it(floor):
    """The owner's loss ruling, on the floor. The task requeues and the
    corridor reopens - a truck that is gone must not lock a hall - but
    the node its BODY is on stays held, under a name of its own, so
    nobody is routed through a hulk. It comes back only on a fresh idle
    state, which is the same clause list that re-earns eligibility."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", WEST)
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)
    assert len(manager.floor.held_by("f1")) > 1

    manager._on_connection("f1", f1.row, {"connectionState":
                                          "CONNECTIONBROKEN"})
    assert manager.floor.held_by("f1") == []
    assert manager.floor.parked["f1"] == WEST
    assert manager.floor.owner_of(WEST) == "parked:f1"
    assert manager.tasks[0]["state"] == "QUEUED"
    doc = manager._status(now)
    assert doc["traffic"]["holds"]["parked:f1"] == ["(-6.0,-5.5)"]

    # A second truck may now have the aisle - but not that one node.
    f2 = Truck(manager, stub, "f2", EAST)
    turn(manager, (f2,), now)
    assert manager.tasks[0]["assignee"] == "f2"
    assert manager.floor.owner_of(WEST) == "parked:f1"

    # ...and the hulk is released the moment it stands up again.
    manager._on_connection("f1", f1.row, {"connectionState": "ONLINE"})
    f1.order = None
    f1.state(now)
    assert "f1" not in manager.floor.parked
    assert manager.floor.owner_of(WEST) == "f1"


def test_set_standing_runs_from_every_state_including_a_restart(floor):
    """THE ONE WAY THIS LEDGER COULD PUT TWO TRUCKS ON ONE NODE.

    resolve_deadlock frees everything the loser holds EXCEPT the node it
    was last told the truck stands on, so a vehicle whose standing node
    is unset gets the ground under it handed to somebody else. A
    restarted manager is the case that bites: it has no tasks and cannot
    know the route an adopted truck is driving (a nodeState carries no
    position), so what it does know - the body's own node - has to reach
    the ledger from the very first state.
    """
    manager, stub = floor
    now = time.monotonic()
    adopted = Truck(manager, stub, "f9", EAST)
    adopted.order = {"orderId": "o-somebody-elses", "orderUpdateId": 0,
                     "nodes": [], "edges": []}
    adopted.state(now)                 # the first state a restart ever sees
    assert manager.floor.standing["f9"] == EAST
    assert manager.floor.owner_of(EAST) == "f9"
    assert manager.floor.held_by("f9") == [EAST]

    # And it follows the truck rather than accumulating behind it.
    adopted.xy = (3.0, -5.5)
    adopted.state(now)
    assert manager.floor.owner_of(EAST) is None
    assert manager.floor.held_by("f9") == [(3.0, -5.5)]


def test_a_hold_asks_only_for_the_route_ahead_of_the_truck(floor):
    """Never the original full route. The elements behind the truck were
    released as it passed them, and asking for them again would draw a
    wait-for edge BACKWARDS - at whoever has legitimately taken the floor
    we just left - and invent a cycle that is not there."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", (-12.5, -5.5))
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)
    trf = manager.tasks[0]["traffic"]
    assert trf["hold_points"][0] == (-12.5, -5.5)

    f1.drive()                               # to the end of its base: S1
    turn(manager, (f1,), now)
    index, ahead = manager.floor.remaining(trf)
    assert ahead == [S1_XY], "the hold would have reached back down the aisle"
    assert index == len(trf["hold_points"]) - 1
    assert manager.floor.held_by("f1") == [S1_XY]
    # A second truck may take the aisle behind it without a cycle.
    f2 = Truck(manager, stub, "f2", (-12.5, -5.5))
    f2.state(now)
    assert manager.floor.owner_of((-12.5, -5.5)) == "f2"
    assert manager.floor.find_cycle() is None


# ---- 6. --no-traffic ----
def test_no_traffic_grants_every_route_whole(open_floor):
    """The flag the gates use to reproduce the M6.3 jam deliberately.
    Nothing is reserved, nothing is horizon, and two trucks are sent at
    each other exactly as they were before M6.4 - which is what makes
    the traffic run a contrast rather than a claim."""
    manager, stub = open_floor
    now = time.monotonic()
    f1, f2 = head_on(manager, stub, now)

    for truck in (f1, f2):
        assert truck.horizon() == [], "traffic reserved something"
        assert all(n["released"] for n in truck.inbox()[-1]["nodes"])
    assert horizon_of(f2) == []
    assert base_of(f2) == ["wp1", "S1"], "f2 was sent onto f1's node"
    assert manager.floor.held_by("f1") == []
    assert manager.floor.held_by("f2") == []
    doc = manager._status(now)
    assert doc["traffic"] == {"enabled": False, "holds": {}, "waiting": {},
                              "yielded": [], "bases": {"t-1": [2, 0],
                                                       "t-2": [2, 0]},
                              "stuck": {}, "yields": [], "blocked": [],
                              "idle": []}


def test_the_traffic_block_is_json_and_reads_like_a_floor(floor):
    """The retained document is the operator's record: every element in
    it is a string a person can read, because a frozenset of coordinate
    pairs is neither JSON nor a sentence."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = head_on(manager, stub, now)
    doc = manager._status(now)
    text = json.dumps(doc)              # the real test: it serialises
    assert "traffic" in json.loads(text)
    assert doc["traffic"]["holds"]["f1"] == [
        "(-6.0,-5.5)", "(-6.0,-5.5)-(-3.0,-5.5)", "(-3.0,-5.5)"]
    assert doc["traffic"]["holds"]["f2"] == ["(0.0,-5.5)"]
    assert doc["traffic"]["waiting"] == {"f2": "(-3.0,-5.5)"}
    assert all("traffic" not in t for t in doc["tasks"])
    # An edge is one piece of floor whichever way you drive it, and it
    # prints as its two ends.
    assert fl._element_str(tr.edge((1.0, 0.0), (2.0, 0.0))) == \
        fl._element_str(tr.edge((2.0, 0.0), (1.0, 0.0))) == \
        "(1.0,0.0)-(2.0,0.0)"
    assert fl._element_str((1.0, 0.0)) == "(1.0,0.0)"


def test_the_floor_is_part_of_the_documents_shape(floor):
    """A jam is a discrete fact and must not wait out the 2 s tick. The
    hold LISTS are reduced to counts in the shape, though: they change
    every time a truck passes a node, which is progress rather than
    news."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = drains(manager, stub, now)
    before = manager._shape(manager._status(now))
    f1.state(now)                          # f1 is off S1
    manager.floor.traffic_pass(now)             # ...so f2's base grows
    assert manager._shape(manager._status(now)) != before


def test_a_truck_that_cannot_start_is_on_the_screen_by_name(floor):
    """Handing the whole prefix back clears the vehicle's `waiting`
    record - it has to, or a truck with no task of its own would sit in
    the wait-for graph and be picked as a deadlock loser - so a truck
    stuck at the door would otherwise show neither a hold nor a wait.
    The sentence rides the document instead, and it is rebuilt every
    pass rather than accumulated."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", S1_XY)
    f2 = Truck(manager, stub, "f2", S1_XY)
    submit(manager, "t-1", "S1", "S4")
    submit(manager, "t-2", "S1", "S4")
    for _ in range(3):
        turn(manager, (f1, f2), now)

    doc = manager._status(now)
    assert f2.inbox() == []
    assert "cannot start leg1 of t-2 to S1" in doc["traffic"]["stuck"]["f2"]
    assert "f2" not in doc["traffic"]["holds"]
    assert "f2" not in doc["traffic"]["waiting"]
    # ...and it is not a fact that outlives the pass that found it.
    manager.tasks[:] = []
    turn(manager, (f1, f2), now)
    assert manager._status(now)["traffic"]["stuck"] == {}


def test_a_leg_two_that_cannot_start_is_on_the_screen_too(floor):
    """THE SENTENCE MUST SURVIVE THE PASS THAT WROTE IT, and leg 2 is
    written by _expire_dwells - which drain() runs BEFORE _assign. A
    clear at the top of _assign therefore erased every leg-2 sentence
    before _publish_status could ever see it: the operator watched a
    truck sit at a pickup with an empty `stuck`, which reads as a fleet
    that has forgotten it. drain() clears once, up front, instead.

    The floor is made to grant f1 nothing for one pass rather than
    staged geometrically: a dwelling truck owns the node under its own
    body, so the only way leg 2 sees a grant of nothing on this graph is
    a truck standing where somebody else already stands - and what this
    test is about is the ORDER of the three calls in drain(), not the
    shape of the jam that gets there.
    """
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = head_on(manager, stub, now, to1="S4")
    f1.drive()                                # f1 lands on S1
    turn(manager, (f1, f2), now)              # ...arrives; the dwell starts
    assert manager.tasks[0]["state"] == "DWELL"
    legs_before = len(f1.legs())

    real_hold = manager.floor.hold
    manager.floor.hold = lambda v, els: [] if v == "f1" else real_hold(v, els)
    manager.dwell_until["t-1"] = now - 1.0
    manager.floor.stuck.clear()               # drain()'s one clear, up front
    manager._expire_dwells(now)               # ...leg 2 finds no floor
    manager.floor.hold = real_hold

    assert len(f1.legs()) == legs_before, "leg 2 went out on a grant of nothing"
    assert manager.tasks[0]["state"] == "DWELL"
    assert "cannot start leg2 of t-1 to S4" in manager.floor.stuck["f1"]
    # ...and the assignment that follows it in the same drain leaves it
    # alone. This is the whole regression.
    manager._assign(now)
    doc = manager._status(now)
    assert "cannot start leg2 of t-1 to S4" in doc["traffic"]["stuck"]["f1"]


# ---- 7. the guarantee has to survive the vehicle's own publish cadence ----
def stale_state(truck, now, order_id=""):
    """A state the truck published BEFORE it accepted the leg the fleet
    just sent it: the previous orderId (or none), the previous lastNode
    (or none), and nothing left to drive. Every real vehicle emits one -
    it reports on a 2 s cadence and the fleet assigns at 10 Hz."""
    truck.manager._on_state(truck.serial, truck.row, {
        "operatingMode": truck.mode,
        "agvPosition": {"x": truck.xy[0], "y": truck.xy[1]},
        "orderId": order_id, "orderUpdateId": 0,
        "lastNodeId": "", "lastNodeSequenceId": 0,
        "nodeStates": [], "errors": []}, now)


def test_a_state_that_predates_the_leg_may_not_free_the_floor_it_holds(
        floor):
    """THE GUARANTEE, AND THE ONE WAY IT WAS LOST.

    Measured 2026-08-22 on this manager: a fully granted corridor
    collapsed to the single node under the truck the first time a state
    arrived carrying the PREVIOUS orderId, and the next vehicle was then
    handed the floor f1 had already been released onto. Silently - no
    log line, no refusal, nothing on the operator's screen. It was not
    an edge case either: a vehicle publishes every 2 s and the fleet
    assigns at 10 Hz, so almost every leg has that window, and a leg
    granted WHOLE never healed, because there was no horizon left to
    retry for.

    A stale state says where the truck is and nothing else.
    """
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", WEST)
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)
    granted = manager.floor.held_by("f1")
    assert len(granted) == 3, "the leg should have been granted whole"

    stale_state(f1, now)                  # published before it accepted
    assert manager.floor.held_by("f1") == granted, \
        "a state that predates the leg freed the corridor under it"
    assert manager.floor.standing["f1"] == WEST
    turn(manager, (f1,), now)
    assert manager.floor.held_by("f1") == granted

    # AND THE SECOND TRUCK IS STILL REFUSED THAT FLOOR.
    f2 = Truck(manager, stub, "f2", EAST)
    submit(manager, "t-2", "S1", "S4")
    turn(manager, (f2, f1), now)
    assert manager.floor.owner_of(S1_XY) == "f1"
    assert horizon_of(f2) == ["S1"], "f2 was handed a node f1 is driving to"


def test_the_dwell_to_leg_two_boundary_has_the_same_window(floor):
    """The other place a stale orderId arrives: the truck is still
    reporting leg 1 when leg 2 goes out. Reading leg 1's lastNodeId
    against leg 2's node map would be worse than useless - leg 2's "wp2"
    is not leg 1's "wp2" - so nothing is read from it at all."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", (-12.5, -5.5))
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)
    leg1 = f1.order["orderId"]
    f1.drive()
    turn(manager, (f1,), now)                       # arrived; dwell starts
    manager.dwell_until["t-1"] = now - 1.0
    turn(manager, (f1,), now)                       # leg 2 goes out, east
    trf = manager.tasks[0]["traffic"]
    granted = manager.floor.held_by("f1")
    assert trf["last_xy"] == S1_XY and len(granted) > 1

    stale_state(f1, now, order_id=leg1)             # leg 1's id, still
    assert manager.floor.held_by("f1") == granted
    assert trf["last_xy"] == S1_XY, "the truck moved in the ledger"


def test_a_base_the_ledger_stopped_backing_is_re_claimed_and_shouted(
        floor):
    """The invariant check behind the fix. A released node is a promise
    the fleet cannot withdraw - VDA 5050 has no way to shrink a base -
    so the reservation behind it must outlive every pass. The retry
    re-asserts the hold whether or not there is horizon left to win, and
    when the ledger comes back short it says so at ERROR instead of
    letting a silent hole ride."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", WEST)
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)
    assert manager.tasks[0]["traffic"]["released"] == 2   # granted whole

    manager.floor.release_all("f1", keep=WEST)            # the hole
    catcher = Catcher()
    manager.log.addHandler(catcher)
    manager.log.setLevel(logging.ERROR)
    try:
        for _ in range(20):
            manager.floor.traffic_pass(now)
    finally:
        manager.log.removeHandler(catcher)

    assert manager.floor.owner_of(S1_XY) == "f1", "the base was not re-taken"
    said = [m for m in catcher.said if "WENT MISSING" in m]
    assert len(said) == 1, "twenty passes, one line"
    assert "f1" in said[0] and "fleet bug" in said[0]


# ---- 8. the spur handover (M6.5, owner ruling) ----
# M6.4's Gate 2 could not be passed at a spur station and the reason was
# structural, not a race a wider margin fixes: the occupant released the
# junction in the millisecond it arrived, the truck queued for the same
# station took it inside one 100 ms pass, and three seconds later the
# occupant's leg 2 asked for its only way out and got a swap deadlock
# wait-die cannot break. The owner's ruling is that the junction stays
# held through the dwell and leg 2's hold takes it over with nothing
# freed in between.


def station_pair(manager, stub, now):
    """Both trucks to S4: f2 from two nodes east of the spur (it wins
    the head task at 4.50 m) and f1 from three nodes west of it (8.50 m,
    and its own dropoff then takes it away west, so nothing below is a
    head-on dressed up as a handover). Returns (f1, f2)."""
    f1 = Truck(manager, stub, "f1", EAST)
    f2 = Truck(manager, stub, "f2", FAR_EAST)
    submit(manager, "t-1", "S4", "S5")
    submit(manager, "t-2", "S4", "S3")
    turn(manager, (f1, f2), now)          # f2 takes t-1: it is the nearer
    turn(manager, (f1, f2), now)          # f1 takes t-2, or what is left
    return f1, f2


def roll(manager, trucks, now):
    """One turn with both trucks driving to the end of whatever base
    they hold - and the assertion that carries this whole section: NO
    SWAP DEADLOCK, at any point, ever."""
    for truck in trucks:
        truck.drive()
    turn(manager, trucks, now)
    assert manager.floor.blocked == [], (
        "a swap deadlock was detected: {}".format(manager.floor.blocked))


def test_a_dwelling_truck_keeps_the_spur_junction_it_came_in_by(floor):
    """THE HANDOVER, END TO END. The second truck's hold is refused for
    as long as the first dwells, granted once leg 2 has gone out and
    taken the occupant away, and no swap deadlock is detected at any
    point on the way - which is the exact failure M6.4 Gate 2 run A
    measured at 11:34:23."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = station_pair(manager, stub, now)
    assert manager.tasks[0]["assignee"] == "f2"
    assert manager.tasks[1]["assignee"] == "f1"

    roll(manager, (f1, f2), now)                  # f2 lands in the spur
    assert manager.tasks[0]["state"] == "DWELL"
    # THE JUNCTION IS STILL THE OCCUPANT'S, and the queued truck's hold
    # is refused on it rather than granted the moment the spur filled.
    assert manager.floor.owner_of(S4_ENTRY) == "f2"
    assert manager.floor.held_by("f2") == [
        S4_ENTRY, tr.edge(S4_ENTRY, S4_XY), S4_XY]
    assert manager.floor.waiting_on("f1") == S4_ENTRY
    assert manager.tasks[1]["traffic"]["released"] == 2, \
        "the queued truck was handed the junction the occupant needs"
    assert manager.floor.find_cycle() is None

    # ...and it stays refused for as long as the dwell lasts.
    roll(manager, (f1, f2), now)
    assert manager.floor.owner_of(S4_ENTRY) == "f2"
    assert manager.tasks[1]["traffic"]["released"] == 2

    # THE DWELL ENDS AND LEG 2 TAKES THE JUNCTION OVER. Nothing was
    # freed in between, so there is no pass in which the queued truck
    # could have taken it.
    manager.dwell_until["t-1"] = now - 1.0
    roll(manager, (f1, f2), now)
    assert manager.tasks[0]["state"] == "ASSIGNED_LEG2"
    assert manager.floor.owner_of(S4_ENTRY) == "f2"
    assert base_of(f2)[:2] == ["wp1", "wp2"], (
        "leg 2 did not get the junction it had been holding: {}".format(
            base_of(f2)))

    # The occupant drives away east; the queued truck follows it in.
    for _ in range(4):
        roll(manager, (f1, f2), now)
    assert manager.tasks[0]["state"] == "DONE"
    assert manager.tasks[1]["state"] == "DWELL", (
        "the second truck never got the station: {}".format(
            manager.tasks[1]["state"]))
    assert manager.floor.standing["f1"] == S4_XY
    assert manager.refused == []


def test_an_aisle_station_keeps_nothing_it_does_not_need(floor):
    """The other half of the ruling: it is the SPUR junction, read off
    the graph, and not simply the node before the last one. S1 sits on
    its aisle and has no such node, so an arrival there releases the
    corridor behind it exactly as it did before M6.5 - a truck dwelling
    on an aisle must not sterilise the node behind it as well."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", (-12.5, -5.5))
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)
    f1.drive()
    turn(manager, (f1,), now)
    assert manager.tasks[0]["state"] == "DWELL"
    assert manager.floor.held_by("f1") == [S1_XY]
    assert manager.floor.spur_entry(S1_XY) is None
    assert manager.floor.spur_entry(S4_XY) == S4_ENTRY


# ---- 9. the idle hold has a clock on it (M6.5) ----
def test_an_idle_trucks_hold_is_given_back_after_the_timeout(floor):
    """A truck with no task holds the ground under its body, which is
    right for one that has just finished and wrong for one that has
    stood in a corridor since the last shift. At four vehicles that
    single node is the difference between a busy floor and a jammed
    one."""
    import fleet_cli
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", EAST)
    f1.state(now)
    manager.floor.traffic_pass(now)
    assert manager.floor.owner_of(EAST) == "f1"

    manager.floor.traffic_pass(now + fl.IDLE_HOLD_S - 0.1)
    assert manager.floor.owner_of(EAST) == "f1", "the clock ran early"

    catcher = Catcher()
    manager.log.addHandler(catcher)
    manager.log.setLevel(logging.WARNING)
    try:
        for i in range(20):
            manager.floor.traffic_pass(now + fl.IDLE_HOLD_S + i)
            f1.state(now + fl.IDLE_HOLD_S + i)   # ...and it keeps reporting
    finally:
        manager.log.removeHandler(catcher)

    assert manager.floor.owner_of(EAST) is None, (
        "an idle truck still holds the aisle after the timeout")
    said = [m for m in catcher.said if "with no task" in m]
    assert len(said) == 1, "twenty passes, one line: {}".format(said)
    assert "f1" in said[0] and "STILL THERE" in said[0]
    # IT IS ON THE OPERATOR'S SCREEN, because a truck that no longer
    # reserves the node it is standing on reads as a forgotten one.
    doc = manager._status(now)
    shown = doc["traffic"]["idle"]
    assert [(e["vehicle"], e["node"], e["freed"]) for e in shown] == \
        [("f1", "(0.0,-5.5)", 1)]
    assert "idle timeout" in "\n".join(fleet_cli.traffic_lines(doc))
    # ...and a second truck may now have that node.
    f2 = Truck(manager, stub, "f2", EAST)
    f2.state(now)
    assert manager.floor.owner_of(EAST) == "f2"


def test_a_truck_parked_in_a_station_spur_keeps_its_node_forever(floor):
    """The exception the ruling names. Nothing is ever routed to a spur
    but the truck being sent to that station, so the hold costs no
    corridor - and dropping it would send a second truck into an
    occupied dead end."""
    manager, stub = floor
    now = time.monotonic()
    f2 = Truck(manager, stub, "f2", S4_XY)
    f2.state(now)
    assert manager.floor.owner_of(S4_XY) == "f2"
    for i in range(5):
        later = now + fl.IDLE_HOLD_S * (i + 1)
        manager.floor.traffic_pass(later)
        f2.state(later)
    assert manager.floor.owner_of(S4_XY) == "f2"
    assert manager._status(now)["traffic"]["idle"] == []


def test_a_dwelling_truck_is_not_an_idle_one(floor):
    """The two M6.5 rules meet here. A truck standing in a spur through
    its fork cycle has a task, so the clock never starts on it - and the
    junction it is keeping for leg 2 is not taken away underneath it,
    however long the dwell runs."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = station_pair(manager, stub, now)
    roll(manager, (f1, f2), now)
    assert manager.tasks[0]["state"] == "DWELL"

    for i in range(5):
        later = now + fl.IDLE_HOLD_S * (i + 1)
        manager.floor.traffic_pass(later)
        for truck in (f1, f2):
            truck.take().state(later)
    assert manager.tasks[0]["state"] == "DWELL"
    assert manager.floor.held_by("f2") == [
        S4_ENTRY, tr.edge(S4_ENTRY, S4_XY), S4_XY]
    assert "f2" not in manager.floor.idle_hold
    assert manager._status(now)["traffic"]["idle"] == []


# ---- 10. the rolling hulk's pin follows it back (M6.5) ----
def test_a_hulk_that_returns_somewhere_else_takes_its_pin_with_it(floor):
    """M6.4 Gate 5 run 1, closed. With no agent alive nothing publishes
    an empty goal, so nav drove a dead truck 2.93 m onto floor the fleet
    had already granted to its replacement while the pin still sat where
    it died. The pin cannot follow a silent truck - nothing can - but
    the first thing the truck says on its way back moves it, and that
    happens BEFORE it re-earns eligibility, which is the window the old
    code left open."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", WEST)
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)

    manager._on_connection("f1", f1.row,
                           {"connectionState": "CONNECTIONBROKEN"})
    assert manager.floor.parked["f1"] == WEST
    assert manager.floor.owner_of(WEST) == "parked:f1"

    # It comes back rolled one node west, still holding the order the
    # fleet has already given to somebody else - so it is NOT eligible
    # yet, and the old code left the pin at WEST until it was.
    manager._on_connection("f1", f1.row, {"connectionState": "ONLINE"})
    assert manager.vehicles["f1"]["not_eligible"] is True
    f1.xy = (-9.8, -5.5)
    f1.state(now)

    assert manager.vehicles["f1"]["not_eligible"] is True, \
        "the pin has to move BEFORE eligibility is re-earned"
    assert manager.floor.parked["f1"] == (-9.8, -5.5)
    assert manager.floor.owner_of((-9.8, -5.5)) == "parked:f1"
    assert manager.floor.owner_of(WEST) is None, \
        "the fleet is still routing around floor the truck has left"
    doc = manager._status(now)
    assert doc["traffic"]["holds"]["parked:f1"] == ["(-9.8,-5.5)"]

    # ...and the pin is dropped, not moved, onto floor somebody else has
    # legitimately taken in the meantime.
    f2 = Truck(manager, stub, "f2", (-7.4, -5.5))
    f2.state(now)
    f1.xy = (-7.4, -5.5)
    f1.state(now)
    assert "f1" not in manager.floor.parked
    assert manager.floor.owner_of((-7.4, -5.5)) == "f2"


def contiguous(held):
    """A hold is a RUN of floor: node, the edge to the next node, that
    node, and so on. Anything else means release_through's index has
    stopped being a position on the route the truck is driving."""
    if not held or len(held) % 2 == 0:
        return False                      # a hold never ends on an edge
    for i, element in enumerate(held):
        if i % 2 == 0:
            if isinstance(element, frozenset):
                return False
        elif element != tr.edge(held[i - 1], held[i + 1]):
            return False
    return True


def test_leg_two_out_of_a_spur_frees_nothing_under_the_truck(floor):
    """THE STATE THE HANDOVER TESTS ABOVE DRIVE STRAIGHT PAST, and the
    one the bug lived in: leg 2 has gone out and the truck has not moved
    yet, so it reports the station node it is still standing on.

    The ledger stores a hold in travel order and release_through frees by
    POSITION in it. Leg 1 left `[junction, edge, station]`; leg 2 drives
    those same three the other way. Measured 2026-08-22: without the
    re-seat in traffic.hold the index of the station was 2, that first
    state freed the junction the truck was about to drive onto, the
    fleet's own invariant check shouted THE FLOOR UNDER A LIVE BASE WENT
    MISSING, and with an older task waiting for that junction the retry
    pass handed it over while leg 2 still had it as released base - two
    vehicles released onto one node, and no cycle to detect it.
    """
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = station_pair(manager, stub, now)
    roll(manager, (f1, f2), now)                  # f2 arrives, dwells
    manager.dwell_until["t-1"] = now - 1.0
    for truck in (f1, f2):
        truck.drive()
    turn(manager, (f1, f2), now)                  # leg 2 goes out
    assert manager.tasks[0]["state"] == "ASSIGNED_LEG2"

    catcher = Catcher()
    manager.log.addHandler(catcher)
    manager.log.setLevel(logging.ERROR)
    try:
        f2.xy = S4_XY                             # it has NOT moved yet
        f2.last = ("wp1", 0)                      # leg 2's first node: S4
        f2.take().state(now)
        manager.floor.traffic_pass(now)
    finally:
        manager.log.removeHandler(catcher)

    assert manager.floor.owner_of(S4_ENTRY) == "f2", (
        "the junction under the truck was freed on its own leg-2 state")
    assert contiguous(manager.floor.held_by("f2")), (
        "the hold is not a run of floor any more: {}".format(
            manager.floor.held_by("f2")))
    assert manager.floor.held_by("f2")[:3] == [
        S4_XY, tr.edge(S4_ENTRY, S4_XY), S4_ENTRY], (
        "the hold is not in leg 2's travel order")
    assert catcher.said == [], (
        "the traffic path logged an error: {}".format(catcher.said))
    # ...and the truck waiting for that junction did not get it.
    assert S4_ENTRY not in manager.floor.held_by("f1")
    assert manager.floor.blocked == []


def test_the_waiting_truck_is_not_handed_the_junction_when_it_is_older(
        floor):
    """The same state with the QUEUED task older than the occupant's, so
    the oldest-first retry pass runs BEFORE the occupant's own re-hold
    could repair a hole. That ordering is what turned the over-release
    from a log line into two vehicles released onto one node."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = station_pair(manager, stub, now)
    older = next(t for t in manager.tasks if t["task_id"] == "t-2")
    occupant = next(t for t in manager.tasks if t["task_id"] == "t-1")
    older["submitted_ts"] = occupant["submitted_ts"] - 10.0

    roll(manager, (f1, f2), now)
    manager.dwell_until["t-1"] = now - 1.0
    for truck in (f1, f2):
        truck.drive()
    turn(manager, (f1, f2), now)
    f2.xy, f2.last = S4_XY, ("wp1", 0)
    f2.take().state(now)
    manager.floor.traffic_pass(now)

    assert manager.floor.owner_of(S4_ENTRY) == "f2"
    assert manager.floor.held_by("f1") == [(3.0, -5.5)]
    assert [n["nodeId"] for n in f1.released()] == ["wp1", "wp2"], (
        "the waiting truck was released onto the occupant's way out")
    assert manager.floor.find_cycle() is None
    assert manager.floor.blocked == []


# ---- 4. four vehicles ----
# M6.5 grew the VEHICLES table to four. The manager has never read that
# table - it learns its fleet off the wire, which is exactly why growing
# the fleet is not a code change - so what is worth asking here is the
# thing that IS arithmetic: with more work than trucks, does every truck
# get one and does the surplus wait? Two trucks could not tell a fleet
# that spreads from one that hands the nearest truck everything.
def test_four_trucks_take_one_transport_each_and_the_fifth_task_waits(
        floor):
    """Assignment spreads over four; the fifth transport queues.

    One truck parked near each of four pickups, five transports out at
    once. `_assign` places at most one task per pass, so five passes are
    given - one more than there are trucks - and the fifth task has
    nowhere to go: every vehicle is executing an order and a busy truck
    is not idle-confirmed.
    """
    manager, stub = floor
    now = time.monotonic()
    trucks = (Truck(manager, stub, "f1", WEST),
              Truck(manager, stub, "f2", FAR_EAST),
              Truck(manager, stub, "f3", (-8.0, 5.65)),
              Truck(manager, stub, "f4", (8.0, 5.65)))
    for i, (src, dst) in enumerate(
            (("S2", "S1"), ("S4", "S1"), ("S6", "S10"),
             ("S7", "S10"), ("S5", "S1"))):
        submit(manager, "t-{}".format(i + 1), src, dst)
    for _ in range(5):
        turn(manager, trucks, now)

    taken = [t for t in manager.tasks if t["assignee"]]
    assert len(taken) == 4, (
        "four idle trucks and five transports took {} tasks"
        .format(len(taken)))
    assert sorted(t["assignee"] for t in taken) == ["f1", "f2", "f3", "f4"], (
        "the fleet did not spread the work: {}"
        .format([(t["task_id"], t["assignee"]) for t in taken]))
    waiting = [t for t in manager.tasks if t["state"] == "QUEUED"]
    assert len(waiting) == 1 and waiting[0]["assignee"] is None
    # Every truck was told something, and no truck was told twice.
    for truck in trucks:
        assert len(truck.legs()) == 1, (
            "{} was given {} orders".format(truck.serial, len(truck.legs())))
    # Four trucks on one floor and the ledger still owns each node once.
    doc = manager._status(now)
    assert doc["traffic"]["enabled"] is True
    assert len(doc["vehicles"]) == 4
