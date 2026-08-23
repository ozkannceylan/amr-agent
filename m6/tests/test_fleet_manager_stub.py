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
# The pick aisle (y = 0) is the new floor's one straight corridor.
S1_XY = (STATIONS["S1"]["x"], STATIONS["S1"]["y"])       # (-13.0, 3.3)
WEST = (STATIONS["S1"]["x"], 0.0)  # S1's spur foot - one hop from S1
EAST = (-7.0, 0.0)           # next pick node east (S2/S4 feet)
# S4 is the other shape a station comes in: a spur off the pick aisle,
# so the truck that is in it has exactly one way out and that way is
# somebody else's way in.
S2_XY = (STATIONS["S2"]["x"], STATIONS["S2"]["y"])       # (-7.0, 3.3)
S4_XY = (STATIONS["S4"]["x"], STATIONS["S4"]["y"])       # (-7.0, -3.3)
S4_ENTRY = (STATIONS["S4"]["x"], 0.0)  # the junction the spur lands on
FAR_EAST = (0.0, 0.0)        # next pick node east of that junction


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
        self.seen_instant = 0
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

    def instants(self):
        topic = "uagv/v2/amragent/{}/instantActions".format(self.serial)
        return [m for t, m, _, _ in self.stub.published if t == topic]

    def take(self):
        # THE CANCEL IS READ FIRST, in the order the wire delivered it:
        # a truck that is handed a cancelOrder and a new order in the
        # same pass has to let go before it can take the second, which
        # is exactly what vda_orders.accept_order refuses to do the
        # other way round ("an order is executing - cancelOrder first").
        for msg in self.instants()[self.seen_instant:]:
            for action in msg.get("actions") or []:
                if action.get("actionType") == "cancelOrder":
                    self.order, self.reached, self.last = None, 0, ("", 0)
        self.seen_instant = len(self.instants())
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


def head_on(manager, stub, now, to1="S4", to2="S4"):
    """The M6.3 jam, staged: f1 west of S1 and f2 east of it, both told
    to pick up at S1. f1's own dropoff decides whether it then drives
    back east through f2 (the jam, `to1="S4"`) or away west (the
    corridor draining, `to1="S3"`).

    This is Gate 4's own scenario (2026-08-22: f2 held 2.65 m behind f1
    with no way out but an operator) reduced to two trucks, one aisle
    and no clock. Returns (f1, f2). f1 wins t-1 on the tie-break: both
    trucks are 3.0 m from S1 and fleet_core keeps the lower serial.
    """
    f1 = Truck(manager, stub, "f1", WEST)
    f2 = Truck(manager, stub, "f2", EAST)
    submit(manager, "t-1", "S1", to1)
    submit(manager, "t-2", "S1", to2)
    turn(manager, (f1, f2), now)          # f1 takes t-1: it is the nearer
    turn(manager, (f1, f2), now)          # f2 takes t-2, or what is left
    return f1, f2


def drains(manager, stub, now):
    """The same two trucks, but f1's transport takes it AWAY from f2:
    it picks up at S1 and drives south to S3, so the node f2 is waiting
    for comes free under it. Returns (f1, f2) with f1 already gone; one
    more turn is what extends f2's base."""
    f1, f2 = head_on(manager, stub, now, to1="S3")
    f1.drive()                            # f1 lands on S1
    turn(manager, (f1, f2), now)          # ...arrives; the dwell starts
    manager.dwell_until["t-1"] = now - 1.0
    turn(manager, (f1, f2), now)          # leg 2 goes out, westward
    f1.drive()                            # and f1 drives away to S3
    return f1, f2


# ---- 3. the base is what the floor granted ----
def test_a_taken_corridor_comes_back_as_a_partial_base(floor):
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = head_on(manager, stub, now)

    # f1 was nearest and got its whole spur: the foot it stands on, then S1.
    assert base_of(f1) == ["wp1", "S1"] and horizon_of(f1) == []
    # f2 wants S1 too. From the next pick node that is two hops, so the
    # foot (wp2) and S1 are both under f1's reservation. f2 is given the
    # node it is standing on and the rest as horizon - an honest wait,
    # not a re-route and not a pause action.
    assert horizon_of(f2) == ["wp2", "S1"], "f2 was routed onto a taken node"
    assert base_of(f2) == ["wp1"]
    assert vo.validate_order(f2.inbox()[-1]) == "", \
        "the manager published a horizon order the vehicle would reject"
    doc = manager._status(now)
    assert doc["traffic"]["enabled"] is True
    assert doc["traffic"]["waiting"]["f2"] == "(-13.0,0.0)"
    # ONE OF THREE, not one of two: on this floor S1 is down a spur, so
    # f2's route is the node under it, S1's foot, and S1.
    assert doc["traffic"]["bases"]["t-2"] == [1, 2]


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
    f1, f2 = head_on(manager, stub, now, to1="S3")
    before = f2.inbox()[-1]
    assert before["orderUpdateId"] == 0
    assert horizon_of(f2) == ["wp2", "S1"]

    f1.drive()                              # f1 lands on S1
    turn(manager, (f1, f2), now)            # ...arrives, dwell starts
    assert manager.tasks[0]["state"] == "DWELL"
    assert len(f2.inbox()) == 1, "S1 is still under f1's body"

    manager.dwell_until["t-1"] = now - 1.0
    turn(manager, (f1, f2), now)            # f1's leg 2 goes out, westward
    assert len(f2.inbox()) == 1, "f1 has not moved off S1 yet"
    f1.drive()                              # ...and f1 drives away to S3
    turn(manager, (f1, f2), now)

    grown = f2.inbox()[-1]
    assert grown["orderUpdateId"] == 1
    assert grown["orderId"] == before["orderId"], "a new leg, not a growth"
    assert vo.accept_order(grown, before, True, "AUTOMATIC") == ("extend", "")
    assert [n["nodeId"] for n in grown["nodes"] if n["released"]] == \
        ["wp1", "wp2", "S1"]
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
    assert trf["pending"] == (1, 3)
    for _ in range(5):                            # f2 has not answered yet
        manager.floor.traffic_pass(now)
    assert len(f2.inbox()) == 2, "a second update before the first landed"

    f2.take().state(now)                          # ...now it has
    assert trf["pending"] is None and trf["update_id"] == 1
    assert trf["released"] == 3


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
    assert task["traffic"]["pending"] == (1, 3)
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
def deadlocked(manager, stub, now, to2="S4"):
    """f1 stopped on S1 asking for the node east of it, f2 stopped on
    that node asking for S1. Nose to nose, each standing on exactly what
    the other needs.

    Stopped one step SHORT of the traffic pass on purpose: the cycle is
    what the tests below want to look at before anything is done about
    it. Returns (f1, f2).
    """
    f1, f2 = head_on(manager, stub, now, to2=to2)
    f1.drive()                                # f1 lands on S1
    turn(manager, (f1, f2), now)              # arrived, dwell starts
    manager.dwell_until["t-1"] = now - 1.0
    for truck in (f1, f2):
        truck.take().state(now)
    manager._expire_dwells(now)               # leg 2 goes east, into f2
    f1.take()
    # AND F1 DRIVES TO THE END OF THAT BASE, which is one node on this
    # floor and was none on the last. _resolve refuses to touch a cycle
    # whose members are still driving - freeing a released node is a
    # thing VDA 5050 does not allow - and f1's leg-2 base is now S1 plus
    # the spur foot beneath it, because a station is down a spur here.
    # Without this drive f1 stands at the START of its base, the cycle
    # is real but nobody is parked, and the pass correctly does nothing.
    f1.drive()
    f1.state(now)
    return f1, f2


def boxed_in(manager):
    """Every free neighbour of f2's node taken by somebody else, so the
    fleet has nowhere to step it aside to and must fall back on the
    honest refusal. The owners are ledger names, not vehicles: what the
    choice reads is who owns the floor, and a serial that is not in the
    registry proves it does not sneak a look at the registry.

    ONE NAME PER FREE NEIGHBOUR, GENERATED RATHER THAN LISTED. This was
    a fixed pair of names against a floor whose nodes had three
    neighbours. On M6.6's floor a pick-aisle node has four - two spurs,
    two corridor - so a pair left one neighbour free, the step-aside
    succeeded, and the test that exists to prove the REFUSAL was reading
    an empty blocked list. A helper that boxes a truck in has to box it
    in however many doors the floor gives it.
    """
    node = manager.floor.standing["f2"]
    free = [n for n in sorted(manager.floor.graph[node])
            if manager.floor.owner_of(n) is None]
    for index, nbr in enumerate(free):
        manager.floor.hold("box{}".format(index), [nbr])
    return free


def test_a_swap_deadlock_asks_the_younger_truck_to_step_aside(floor):
    """WAIT-DIE CANNOT BREAK THIS ONE, SO THE FLEET MOVES A TRUCK.

    Once every truck in a cycle has stopped at the end of its base it
    holds exactly one element - the node under its own body, everything
    behind it having been released as it passed. So the contested
    element is GROUND UNDER A VEHICLE, and the youngest yielding keeps
    precisely that and frees nothing at all. Naming it was M6.5's answer
    and it left the floor jammed; this is the M6.5 fix-up's: the younger
    truck is cancelled, requeued and sent a one-node order to a free
    node next door, and the older one drives through the floor that
    frees.
    """
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = deadlocked(manager, stub, now)

    # S1 IS DOWN A SPUR ON THIS FLOOR, so f1's leg 2 stops two nodes
    # along rather than one: S1 itself and the spur foot beneath it,
    # both of which f1 already holds (floor._dwell_entry keeps the
    # junction a dwelling truck came in by). The node after that is
    # f2's, and that is where the base ends.
    assert base_of(f1) == ["wp1", "wp2"], \
        "f1's leg 2 should stop on the spur it is standing in"
    assert manager.floor.waiting_on("f1") == EAST
    # ...and f2 waits on that same spur foot, not on S1: the foot is
    # what f1 is holding and what f2 must cross to reach the station.
    assert manager.floor.waiting_on("f2") == WEST
    assert set(manager.floor.find_cycle() or []) == {"f1", "f2"}
    order_id = f2.order["orderId"]

    manager.floor.traffic_pass(now)
    doc = manager._status(now)

    # NAMED, and named as a move rather than as a wall.
    aside = doc["traffic"]["aside"]
    assert aside, "the step-aside is nowhere on the operator's screen"
    said = aside[-1]
    assert said["vehicle"] == "f2" and said["for"] == ["f1"]
    # INTO A FREE BAY, which is the best answer this floor has: S2's
    # spur is 3.30 m away, it is not on f1's route, and it takes the
    # truck off the corridor entirely instead of one node along it.
    assert said["from"] == "(-7.0,0.0)" and said["to"] == "(-7.0,3.3)"
    assert said["task"] == "t-2"
    assert doc["traffic"]["blocked"] == [], (
        "a floor that is being cleared is not a BLOCKED floor")
    assert doc["traffic"]["yields"] == [], "a yield that freed nothing"
    assert any("step aside" in r["why"] for r in doc["refused"])

    # The YOUNGER task is the one taken away, and it goes back to the
    # head of the queue rather than being lost.
    assert manager.tasks[0]["task_id"] == "t-2"
    assert manager.tasks[0]["state"] == "QUEUED"

    # AND THE ORDER IT WAS DRIVING IS CANCELLED. Without this the truck
    # goes on executing an order the fleet no longer owns, never reports
    # idle, and _idle_floor's adopted-truck exemption holds its node for
    # ever - measured 2026-08-22, Gate 3.
    assert manager.cancelled["f2"]["order_id"] == order_id
    assert len(cancels(stub)) == 1


def test_a_swap_deadlock_with_nowhere_to_go_is_named_and_not_pretended(floor):
    """The bound: no free neighbour is the honest floor, unchanged.

    A fleet that could always move a truck would be claiming a floor
    this one does not have. When every node next door belongs to
    somebody else the answer is M6.5's - refuse the younger task by
    name, on the screen, where an operator reads it and goes and moves a
    truck - and the cancel still goes out, because the task has still
    been taken away.
    """
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = deadlocked(manager, stub, now)
    taken = boxed_in(manager)
    assert taken, "the staging reserved nothing - this proves nothing"

    manager.floor.traffic_pass(now)
    doc = manager._status(now)

    assert doc["traffic"]["aside"] == [], "moved a truck onto taken floor"
    said = doc["traffic"]["blocked"][-1]
    assert said["vehicles"] == ["f1", "f2"] and said["task"] == "t-2"
    assert "swap deadlock" in said["why"]
    assert "nowhere free next to it" in said["why"]
    assert any("swap deadlock" in r["why"] for r in doc["refused"])
    assert manager.tasks[0]["task_id"] == "t-2"
    assert manager.tasks[0]["state"] == "QUEUED"
    assert len(cancels(stub)) == 1


def test_the_step_aside_target_is_the_nearest_free_node_off_the_others_route(
        floor):
    """The choice itself, asked without moving anything.

    f2 stands on the pick-aisle node at x = -7. Four nodes touch it:
    the spur foot at x = -13, which f1 is holding; S4's bay 3.30 m
    south, which is free but is the next node of f1's own route; S2's
    bay 3.30 m north, which is neither; and the aisle node at x = 0,
    7.00 m east, which is free and quiet but is BEYOND ASIDE_MAX_M.

    So the answer is S2's bay, and the two rules that pick it are worth
    saying out loud. Floor the blocked trucks still have to drive is a
    PREFERENCE, which is what takes S4 out. ASIDE_MAX_M (5.00 m) is a
    BOUND, which is what takes the aisle node out - and the bound is why
    the far node does not simply inherit the answer when the near one
    is taken. A bay is a better step aside than a corridor node in any
    case: it puts the truck off the aisle entirely rather than one node
    further along it.
    """
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = deadlocked(manager, stub, now)
    assert manager.floor.standing["f2"] == EAST

    # 1. THE PREFERENCE. S4 is 3.30 m away and so is S2; S4 is the next
    #    node of f1's own route and S2 is nobody's, so S2 wins.
    assert manager.floor.step_aside_target("f2", ["f1"]) == S2_XY

    # 2. A PREFERENCE THAT RUNS OUT YIELDS, IT DOES NOT REFUSE. With S2
    #    taken the only candidate left inside the bound is the one on
    #    f1's route, and a truck moved onto floor the other still has to
    #    drive is a worse answer than a jam only in theory - f1 arrives
    #    there later, by which time f2 has its own task and is gone.
    manager.floor.hold("f9", [S2_XY])
    assert manager.floor.step_aside_target("f2", ["f1"]) == S4_XY

    # 3. THE BOUND, WHICH IS NOT A PREFERENCE. With both bays taken the
    #    aisle node 7.00 m east is free, quiet, and on nobody's route -
    #    and it is still refused, because ASIDE_MAX_M is 5.00 m and
    #    seven metres driven as a single node with no route is not a
    #    step aside. None is the honest answer and an operator reads it.
    manager.floor.hold("f8", [S4_XY])
    assert manager.floor.step_aside_target("f2", ["f1"]) is None
    assert manager.floor.owner_of(FAR_EAST) is None, (
        "the aisle node was free and was still correctly refused")


def test_a_truck_stepped_aside_too_often_stops_being_shuffled(floor):
    """The other bound: a cap, so a jam the moves are not clearing is
    named instead of turning into a shift of shunting.

    The count is per vehicle and it is reset by PROGRESS - a leg that
    actually arrives - not by the clock, because a truck that has been
    moved three times and driven nowhere is the exact shape of a floor
    the fleet cannot untangle.
    """
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = deadlocked(manager, stub, now)
    manager.floor.aside_count["f2"] = fl.ASIDE_MAX

    manager.floor.traffic_pass(now)
    doc = manager._status(now)

    assert doc["traffic"]["aside"] == [], "shuffled past its own cap"
    why = doc["traffic"]["blocked"][-1]["why"]
    assert "swap deadlock" in why
    assert "stepped aside {} times".format(fl.ASIDE_MAX) in why
    assert manager.tasks[0]["task_id"] == "t-2"


def test_a_staged_swap_deadlock_clears_and_both_transports_complete(floor):
    """END TO END, and the only test here that asks for the whole thing.

    The same nose-to-nose jam that ended M6.5's Gate 3 with 0 of 4
    transports: f1 on S1 driving east, f2 standing on the node it needs
    and wanting S1. The fleet cancels f2, requeues its task, moves it
    one node onto the connector, and from there both transports finish
    with no operator in it anywhere.
    """
    manager, stub = floor
    now = time.monotonic()
    # The two transports END at different stations on purpose. Sent to
    # the same one, the first truck to arrive parks IN the spur and keeps
    # it (floor._idle_floor exempts a truck parked in a station, because
    # nothing else is ever routed there) - a real property of this floor,
    # and one that would answer a question this test is not asking.
    f1, f2 = deadlocked(manager, stub, now, to2="S3")

    for step in range(40):
        turn(manager, (f1, f2), now + step)
        for truck in (f1, f2):
            truck.drive()
        if all(t["state"] == "DONE" for t in manager.tasks):
            break
    states = {t["task_id"]: t["state"] for t in manager.tasks}
    assert states == {"t-1": "DONE", "t-2": "DONE"}, states
    assert manager.floor.aside == {}, "a step-aside never finished"
    assert manager.floor.asides[-1]["state"] == "done"


# The spine's north junction: a node OFF the pick aisle from which the
# only way to S1 runs through EAST, which is what makes the crossing a
# crossing. It has to be a real graph node - route.nearest_node snaps a
# pose to one, and a truck staged between two nodes stands on neither.
NORTH = (0.0, 10.0)
# The spine node under NORTH: f2's first hop, and what the crossing
# staging holds to keep f2's leg-1 base one node long.
SPINE_MID = (0.0, 0.0)


def crossing(manager, stub, now):
    """The deadlock wait-die WAS designed for, and the one this fleet
    can still resolve by yielding: two trucks whose routes cross at a
    node NEITHER of them is standing on.

    f1 stands on S1 with its leg 2 heading east through the junction;
    f2 stands at the top of the central connector with the junction
    reserved ahead of it and a base that stops under its own wheels. So
    what f1 waits for is floor f2 has RESERVED and not floor f2 is
    standing on, which is the whole difference between this and a swap.

    Two pieces of staging, both of them things the fleet does to itself:
    the junction is somebody else's for the turn f2 is assigned in, so
    f2's leg 1 is granted its own node and no more; and the extension
    that would have grown that base is published to a truck that never
    reads it, which is exactly the state a dropped wire or a refused
    update leaves behind (floor.retry_hold grants BEFORE the vehicle
    confirms, and trf["released"] does not move until it does).
    """
    f1 = Truck(manager, stub, "f1", S1_XY)
    f2 = Truck(manager, stub, "f2", NORTH)
    submit(manager, "t-1", "S1", "S4")           # f1: east through EAST
    submit(manager, "t-2", "S1", "S2")           # f2: south through EAST to S1
    turn(manager, (f1, f2), now)                 # f1 takes t-1: it is on S1
    f1.drive()
    # BLOCKED AT ITS OWN FIRST HOP, which on this floor is the spine
    # node under it and not EAST. The point of the staging is that f2's
    # leg 1 is granted its own node AND NO MORE, so it is parked at the
    # end of a one-node base; holding EAST would leave the spine free
    # and f2 would be granted two nodes and be parked at neither end.
    manager.floor.hold("f9", [SPINE_MID])
    turn(manager, (f1, f2), now)            # f1 arrives+dwells, f2 takes t-2
    manager.floor.release_all("f9")
    # The ledger reaches the junction; the truck is never told, so its
    # base stays one node long and it is parked at the end of it.
    manager.floor.traffic_pass(now)
    manager.dwell_until["t-1"] = now - 1.0
    # ONLY f1 REPORTS FROM HERE. f2 reading its own extension is what
    # would move trf["released"] on and take it off the end of its base;
    # a truck that never read it is the state a dropped wire leaves.
    f1.take().state(now)
    manager._expire_dwells(now)                  # f1's leg 2, stopped on S1
    f1.take()
    return f1, f2


def test_a_yield_that_frees_the_contested_floor_is_a_resolution(floor):
    """The other half of wait-die, and it is still here.

    A yield is a resolution when what it frees is what the other truck
    was blocked on - the REACH case, where the loser gives up floor
    AHEAD of itself. It keeps its task, its route and its submit time,
    and the older truck drives on. Nothing is cancelled and nobody is
    moved: a step-aside is what happens when this cannot work, not
    instead of it.
    """
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = crossing(manager, stub, now)
    younger = next(t for t in manager.tasks if t["task_id"] == "t-2")
    submitted = younger["submitted_ts"]
    assert manager.floor.standing["f2"] == NORTH, "f2 drove off the spine"
    # THE CONTESTED NODE IS S1'S SPUR FOOT. f2 has reserved the whole run
    # west of it and stopped at the foot, which is the last thing f1
    # needs to leave its own spur - and neither truck is standing on it,
    # which is what makes this a crossing and not a swap.
    assert manager.floor.waiting_on("f1") == WEST
    assert manager.floor.waiting_on("f2") == S1_XY
    assert manager.floor.owner_of(WEST) == "f2", (
        "the contested node is not reserved ahead of f2")

    manager.floor.traffic_pass(now)
    doc = manager._status(now)
    assert doc["traffic"]["yields"], "nothing was recorded as a yield"
    gave = doc["traffic"]["yields"][-1]
    assert gave["vehicle"] == "f2" and gave["with"] == ["f1"]
    # SIX ELEMENTS, not two: on this floor f2's reservation runs the
    # spine and the pick aisle - three nodes and three edges - and all
    # of it is floor AHEAD of the truck, which is what makes the yield
    # a resolution rather than a gesture.
    assert gave["freed"] == 6 and gave["task"] == "t-2"
    assert doc["traffic"]["blocked"] == []
    assert doc["traffic"]["aside"] == [], "a yield that worked moved a truck"
    assert manager.floor.owner_of(WEST) is None, (
        "the floor f1 was blocked on is still f2's")
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
    assert doc["traffic"]["holds"]["parked:f1"] == ["(-13.0,0.0)"]

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
    adopted.xy = FAR_EAST
    adopted.state(now)
    assert manager.floor.owner_of(EAST) is None
    assert manager.floor.held_by("f9") == [FAR_EAST]


def test_a_hold_asks_only_for_the_route_ahead_of_the_truck(floor):
    """Never the original full route. The elements behind the truck were
    released as it passed them, and asking for them again would draw a
    wait-for edge BACKWARDS - at whoever has legitimately taken the floor
    we just left - and invent a cycle that is not there."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", (-20.0, 0.0))
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)
    trf = manager.tasks[0]["traffic"]
    assert trf["hold_points"][0] == (-20.0, 0.0)

    f1.drive()                               # to the end of its base: S1
    turn(manager, (f1,), now)
    index, ahead = manager.floor.remaining(trf)
    assert ahead == [S1_XY], "the hold would have reached back down the aisle"
    assert index == len(trf["hold_points"]) - 1
    # THE SPUR, AND NOTHING WEST OF IT. A dwelling truck keeps the
    # junction it came in by (floor._dwell_entry) - here the foot at
    # x = -13 - and gives back everything behind it, which on this floor
    # is the whole run from x = -20. The old floor's S1 sat ON the aisle
    # and had no foot to keep, which is why this used to be one element.
    assert manager.floor.held_by("f1") == [
        WEST, tr.edge(WEST, S1_XY), S1_XY]
    # A second truck may take the aisle behind it without a cycle.
    f2 = Truck(manager, stub, "f2", (-20.0, 0.0))
    f2.state(now)
    assert manager.floor.owner_of((-20.0, 0.0)) == "f2"
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
    assert base_of(f2) == ["wp1", "wp2", "S1"], "f2 was sent onto f1's node"
    assert manager.floor.held_by("f1") == []
    assert manager.floor.held_by("f2") == []
    doc = manager._status(now)
    assert doc["traffic"] == {"enabled": False, "holds": {}, "waiting": {},
                              "yielded": [], "bases": {"t-1": [2, 0],
                                                       "t-2": [3, 0]},
                              "stuck": {}, "yields": [], "blocked": [],
                              "idle": [], "aside": []}


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
        "(-13.0,0.0)", "(-13.0,0.0)-(-13.0,3.3)", "(-13.0,3.3)"]
    assert doc["traffic"]["holds"]["f2"] == ["(-7.0,0.0)"]
    # f2 waits on the SPUR FOOT, not on the station: the foot is what
    # f1 is holding while it dwells and what f2 must cross to reach S1.
    assert doc["traffic"]["waiting"] == {"f2": "(-13.0,0.0)"}
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
    assert horizon_of(f2) == ["wp2", "S1"], \
        "f2 was handed a node f1 is driving to"


def test_the_dwell_to_leg_two_boundary_has_the_same_window(floor):
    """The other place a stale orderId arrives: the truck is still
    reporting leg 1 when leg 2 goes out. Reading leg 1's lastNodeId
    against leg 2's node map would be worse than useless - leg 2's "wp2"
    is not leg 1's "wp2" - so nothing is read from it at all."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", (-20.0, 0.0))
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
    """Both trucks to S4: f2 from one node east of the spur (it wins the
    head task at 10.30 m) and f1 from the west end of the pick aisle
    (16.30 m, and its own dropoff then takes it away west, so nothing
    below is a head-on dressed up as a handover). Returns (f1, f2).

    NEITHER TRUCK MAY START ON THE SPUR FOOT. EAST is S4's own foot on
    this floor, so a truck staged there is 3.30 m from the station and
    wins every tie in this section by standing in the doorway - which
    inverted the two roles and made the handover a test of nothing.
    """
    f1 = Truck(manager, stub, "f1", (-20.0, 0.0))
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


def test_a_dwelling_truck_gives_back_the_corridor_behind_it(floor):
    """The other half of the ruling: the junction kept is the SPUR
    junction, read off the graph, and NOT simply "one more node".

    THIS TEST USED TO BE `test_an_aisle_station_keeps_nothing_it_does_
    not_need`, and it was renamed rather than deleted because M6.6 took
    its subject away. The old floor had two shapes of station - S1 sat
    ON the dock aisle with no spur at all, S4 was 2.5 m down one - and
    the claim was that an arrival at the first kind released the whole
    corridor behind it. On this floor there is no first kind: every one
    of the twelve stations is down a spur of at least 3.30 m, which is
    what retires the turning-radius orbit (stations.py).

    So the invariant is asked the only way this floor allows. A truck
    that drove the pick aisle from x = -20 and is dwelling at S1 keeps
    exactly three elements - the foot, the edge up the spur, and the
    station - and gives back every metre of aisle behind the foot. One
    node of sterilised corridor is the ruling; two would be a truck
    holding floor it is not on and does not need.
    """
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", (-20.0, 0.0))
    submit(manager, "t-1", "S1", "S4")
    turn(manager, (f1,), now)
    f1.drive()
    turn(manager, (f1,), now)
    assert manager.tasks[0]["state"] == "DWELL"
    assert manager.floor.held_by("f1") == [WEST, tr.edge(WEST, S1_XY), S1_XY]
    # ...and the aisle it drove to get here is somebody else's again.
    assert manager.floor.owner_of((-20.0, 0.0)) is None
    assert manager.floor.owner_of(tr.edge((-20.0, 0.0), WEST)) is None
    # THE JUNCTION IS READ OFF THE GRAPH. Every station has one now; a
    # plain corridor node has none, and that is the distinction the
    # ruling rests on.
    assert manager.floor.spur_entry(S1_XY) == WEST
    assert manager.floor.spur_entry(S4_XY) == S4_ENTRY
    assert manager.floor.spur_entry(FAR_EAST) is None


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
        [("f1", "(-7.0,0.0)", 1)]
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
    # ONTO A NODE, because the pin is nearest_node of what the truck
    # reports and a coordinate between two nodes pins to whichever is
    # nearer - which would be testing route.nearest_node here, not the
    # pin. (-20, 0) is the pick aisle's west end, one node west of WEST.
    f1.xy = (-20.0, 0.0)
    f1.state(now)

    assert manager.vehicles["f1"]["not_eligible"] is True, \
        "the pin has to move BEFORE eligibility is re-earned"
    assert manager.floor.parked["f1"] == (-20.0, 0.0)
    assert manager.floor.owner_of((-20.0, 0.0)) == "parked:f1"
    assert manager.floor.owner_of(WEST) is None, \
        "the fleet is still routing around floor the truck has left"
    doc = manager._status(now)
    assert doc["traffic"]["holds"]["parked:f1"] == ["(-20.0,0.0)"]

    # ...and the pin is dropped, not moved, onto floor somebody else has
    # legitimately taken in the meantime.
    f2 = Truck(manager, stub, "f2", EAST)
    f2.state(now)
    f1.xy = EAST
    f1.state(now)
    assert "f1" not in manager.floor.parked
    assert manager.floor.owner_of(EAST) == "f2"


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
    # THE NODE UNDER IT AND NOTHING ELSE. f1 starts at the pick aisle's
    # west end and has driven as far as S1's foot by now; what matters
    # is that its hold stops there and does not include the junction
    # the occupant is leaving by.
    assert manager.floor.held_by("f1") == [WEST]
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
              Truck(manager, stub, "f3", (-12.0, 10.0)),
              Truck(manager, stub, "f4", (12.0, 10.0)))
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


def test_the_step_aside_bounds_are_the_measured_ones():
    """The two numbers the 2026-08-22 run gave back, pinned to it.

    ASIDE_S was 60 s, written against an arithmetic that used 0.30 m/s
    and counted only the driving. The live move took 199 s end to end -
    a cancelOrder handshake, a publish, the vehicle taking the order,
    and a drive that creeps for most of its length - so the fleet gave
    up on a move that was going to succeed and said the floor needed a
    person. The rate is now the measured one and the timeout is derived
    from it and from the longest move the distance bound allows, so the
    two can never drift apart again.
    """
    assert fl.ASIDE_MAX_M == 5.0          # the longest AISLE edge
    assert abs(fl.ASIDE_RATE_MPS - 11.15 / 199.0) < 1e-9
    assert fl.ASIDE_S == 2.0 * fl.ASIDE_MAX_M / fl.ASIDE_RATE_MPS
    # Which has to be long enough for the move the bound allows, at the
    # rate the floor actually delivers, with room over.
    assert fl.ASIDE_S > fl.ASIDE_MAX_M / fl.ASIDE_RATE_MPS
    # And the connector, the edge that caused all this, is now out.
    assert 11.15 > fl.ASIDE_MAX_M
