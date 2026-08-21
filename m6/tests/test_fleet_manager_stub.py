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
