"""The fleet manager against a real broker and two scripted trucks.

Runs a private mosquitto on 18884 - NOT 18883, which is
test_vda_agent_mqtt.py's, so the two integration files can never collide
even when a runner interleaves them - and the manager itself as a real
subprocess, argparse and clean shutdown included. A restart in here is a
kill and a respawn, which is the only honest way to ask what a restarted
manager knows.

THE BROKER NEEDS ITS LIBRARIES ON THE SPAWN LINE. tools/install_broker.sh
unpacks libwrap, libdlt and libwebsockets beside the binary rather than
into the system, so the loader finds none of them by default and the
child exits 127 - a broker that "started" and is not listening, which
reads as a paho timeout three assertions later. step6.sh spells the same
path in BROKER_LIB; this is the third and last place it exists.

THE FAKE TRUCKS ARE PURE PAHO. No rclpy, no nav, no Gazebo: a fake takes
an order, reports the nodes it has left, and lands on the last one when
the test tells it to. What it publishes is built by the vehicle's OWN
message builders (ipc/vda_messages.py, which are pure), so the manager
is reading state documents shaped exactly like a real truck's - the
arrival test in particular (orderId ours, nodeStates empty) is only worth
anything if nodeStates comes from the same code the agent uses.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time

import pytest

mqtt = pytest.importorskip("paho.mqtt.client")

VENDORED = os.path.expanduser("~/.local/mosquitto-vendored")
BROKER = os.path.join(VENDORED, "usr", "sbin", "mosquitto")
BROKER_LIB = os.path.join(VENDORED, "usr", "lib", "x86_64-linux-gnu")
pytestmark = pytest.mark.skipif(
    not os.path.exists(BROKER),
    reason="vendored mosquitto missing - run tools/install_broker.sh")

PORT = "18884"

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))
FLEET_MANAGER = os.path.normpath(
    os.path.join(_HERE, "..", "fleet", "fleet_manager.py"))

import fleet_manager as fm                          # noqa: E402
import vda_messages as vm                           # noqa: E402
import vda_orders as vo                             # noqa: E402
from stations import STATIONS                       # noqa: E402

S1 = (STATIONS["S1"]["x"], STATIONS["S1"]["y"])
S5 = (STATIONS["S5"]["x"], STATIONS["S5"]["y"])
DOCK_W = (-8.0, -5.5)          # a dock-aisle node, 5 m short of S1


def _wait_listening(port, timeout_s=5.0):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.2):
                return True
        except OSError:
            time.sleep(0.05)
    return False


class FakeVehicle:
    """A truck on the wire and nothing more: it answers orders, reports
    what it has left to drive, and arrives when the test says so.

    It carries the real agent's two habits that the manager's rules are
    built around - a will that says CONNECTIONBROKEN, and an orderId
    that SURVIVES arrival (nodeStates empties, orderId does not).
    """

    def __init__(self, vid, pose, port, mode="AUTOMATIC"):
        self.vid = vid
        self.pose = (float(pose[0]), float(pose[1]), 0.0)
        self.mode = mode
        self.port = port
        self.counters = vm.Counters()
        self.order_id = ""
        self.remaining = []
        self.last_node = ("", 0)
        self.errors = []
        self.cancels = []
        self.reject_next = False
        self.manual_after_reject = False
        self.alive = True
        self.lock = threading.RLock()
        self._connect()
        self._start_heartbeat()

    def _hdr(self, name):
        return self.counters.header(vm.topic(self.vid, name), self.vid)

    def _connect(self):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id="fake-{}".format(self.vid))
        client.will_set(
            vm.topic(self.vid, "connection"),
            json.dumps(vm.connection_payload(
                self._hdr("connection"), "CONNECTIONBROKEN")),
            qos=1, retain=True)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect("127.0.0.1", int(self.port))
        client.loop_start()
        self.mq = client

    def _start_heartbeat(self):
        self.beat = threading.Thread(target=self._heartbeat, daemon=True)
        self.beat.start()

    def _heartbeat(self):
        # Faster than the real agent's 2 s so the manager's freshness
        # clause (IDLE_FRESH_S 3.0) is never the thing under test here.
        while self.alive:
            time.sleep(0.4)
            if self.alive:
                self.publish_state()

    def _on_connect(self, client, userdata, flags, reason_code,
                    properties=None):
        client.subscribe([(vm.topic(self.vid, "order"), 1),
                          (vm.topic(self.vid, "instantActions"), 1)])
        client.publish(vm.topic(self.vid, "connection"), json.dumps(
            vm.connection_payload(self._hdr("connection"), "ONLINE")),
            qos=1, retain=True)
        self.publish_state()

    def _on_message(self, client, userdata, msg):
        try:
            body = json.loads(msg.payload.decode())
        except ValueError:
            return
        with self.lock:
            if msg.topic.endswith("/order"):
                self._take(body)
            else:
                for act in body.get("actions", []):
                    if act.get("actionType") != "cancelOrder":
                        continue
                    self.cancels.append(
                        (time.monotonic(), act.get("actionId")))
                    self.order_id, self.remaining = "", []
                    self.last_node = ("", 0)
        self.publish_state()

    def _take(self, order):
        if self.reject_next:
            self.reject_next = False
            if self.manual_after_reject:
                # The teleop switch that caused the refusal is only now
                # visible in the states - the real race Gate 3 walks.
                self.mode = "MANUAL"
            self.errors = [{
                "errorType": "orderError", "errorLevel": "WARNING",
                "errorDescription": "vehicle not in AUTOMATIC",
                "errorReferences": [{"referenceKey": "orderId",
                                     "referenceValue": order["orderId"]}]}]
            return
        self.order_id = order["orderId"]
        self.remaining = [n for n in order["nodes"] if n["released"]]

    def arrive(self):
        """Land on the last node of the current order. The orderId is
        KEPT - that is the whole reason the manager cannot read orderId
        alone as "busy"."""
        with self.lock:
            if not self.remaining:
                return
            node = self.remaining[-1]
            self.pose = (node["nodePosition"]["x"],
                         node["nodePosition"]["y"], 0.0)
            self.last_node = (node["nodeId"], node["sequenceId"])
            self.remaining = []
        self.publish_state()

    def publish_state(self):
        with self.lock:
            ctx = {"orderId": self.order_id, "orderUpdateId": 0,
                   "lastNodeId": self.last_node[0],
                   "lastNodeSequenceId": self.last_node[1],
                   "nodeStates": [{"nodeId": n["nodeId"],
                                   "sequenceId": n["sequenceId"],
                                   "released": True}
                                  for n in self.remaining],
                   "edgeStates": []}
            # errors[] is one-shot, exactly as the agent's is: the
            # rejection rides the state it produced and the standing
            # record afterwards is the absence of the order.
            errors, self.errors = self.errors, []
            payload = json.dumps(vm.build_state(
                self._hdr("state"), ctx, self.pose, bool(self.remaining),
                self.mode, errors,
                {"eStop": "NONE", "fieldViolation": False}, []))
        try:
            self.mq.publish(vm.topic(self.vid, "state"), payload, qos=0)
        except Exception:
            pass                    # a yanked fake has no socket left

    def yank(self):
        """Drop the TCP connection without a DISCONNECT, so the broker
        publishes the will - what a killed agent looks like from here."""
        self.alive = False
        self.mq.loop_stop()
        try:
            self.mq.socket().close()
        except Exception:
            pass

    def revive(self):
        """Come back still holding the order. The M6.2 agent keeps AND
        resumes a kept order across a reconnect, which is what makes the
        manager's cancelOrder a race worth measuring."""
        self.alive = True
        self._connect()
        self._start_heartbeat()

    def close(self):
        self.alive = False
        try:
            self.mq.publish(vm.topic(self.vid, "connection"), json.dumps(
                vm.connection_payload(self._hdr("connection"), "OFFLINE")),
                qos=1, retain=True).wait_for_publish(timeout=1.0)
        except Exception:
            pass
        try:
            self.mq.disconnect()
        except Exception:
            pass
        self.mq.loop_stop()


class Rig:
    """The broker's other clients: one probe that hears everything the
    manager says, plus the spawner for managers and fakes."""

    def __init__(self, port, logdir):
        self.port = port
        self.logdir = logdir
        self.fakes = []
        self.managers = []
        self.orders = []        # (t, serial, order)
        self.actions = []       # (t, serial, message)
        self.statuses = []      # (t, document)
        self.lock = threading.Lock()
        subscribed = threading.Event()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id="probe-fleet")
        client.on_connect = lambda c, u, f, rc, p=None: c.subscribe(
            [("uagv/v2/amragent/+/order", 1),
             ("uagv/v2/amragent/+/instantActions", 1),
             (fm.STATUS_TOPIC, 1)])
        client.on_subscribe = lambda *a, **k: subscribed.set()
        client.on_message = self._on_message
        client.connect("127.0.0.1", int(port))
        client.loop_start()
        assert subscribed.wait(5.0), "the probe never got its SUBACK"
        self.mq = client

    def _on_message(self, client, userdata, msg):
        try:
            body = json.loads(msg.payload.decode())
        except ValueError:
            return
        now = time.monotonic()
        with self.lock:
            if msg.topic == fm.STATUS_TOPIC:
                self.statuses.append((now, body))
            elif msg.topic.endswith("/order"):
                self.orders.append((now, msg.topic.split("/")[3], body))
            else:
                self.actions.append((now, msg.topic.split("/")[3], body))

    def orders_for(self, serial, since=0.0):
        with self.lock:
            return [(t, o) for t, s, o in self.orders
                    if s == serial and t >= since]

    def actions_since(self, since=0.0):
        with self.lock:
            return [(t, s, a) for t, s, a in self.actions if t >= since]

    def status(self, since=0.0):
        with self.lock:
            docs = [d for t, d in self.statuses if t >= since]
        return docs[-1] if docs else None

    def find_status(self, test, since=0.0):
        """The first RECORDED document that satisfied test.

        Some of what this test asks about is true for half a second -
        a truck that is back but has not yet been cancelled, say - and
        polling the latest document would miss it and call that a bug.
        The probe kept every document; ask those.
        """
        with self.lock:
            docs = [d for t, d in self.statuses if t >= since]
        return next((d for d in docs if test(d)), None)

    def fake(self, vid, pose, **kw):
        veh = FakeVehicle(vid, pose, self.port, **kw)
        self.fakes.append(veh)
        return veh

    def manager(self):
        path = os.path.join(self.logdir,
                            "manager-{}.log".format(len(self.managers)))
        handle = open(path, "wb")
        proc = subprocess.Popen(
            [sys.executable, FLEET_MANAGER, "--port", self.port],
            stdout=handle, stderr=subprocess.STDOUT,
            env={**os.environ, "VDA_MQTT_PORT": self.port})
        self.managers.append([proc, handle, path])
        return proc

    def kill(self, proc):
        """No SIGINT: a restart test must not hand the dying manager a
        chance to say a graceful last word it would not get in a crash."""
        proc.kill()
        proc.wait(timeout=5)

    def submit(self, task_id, src, dst):
        self.mq.publish(fm.SUBMIT_TOPIC, json.dumps(
            {"taskId": task_id, "from": src, "to": dst}),
            qos=1).wait_for_publish(timeout=2.0)

    def logs(self):
        out = []
        for _proc, handle, path in self.managers:
            handle.flush()
            with open(path, "r", errors="replace") as fh:
                out.append("\n--- {} ---\n{}".format(
                    os.path.basename(path), fh.read()[-2500:]))
        return "".join(out)

    def close(self):
        for veh in self.fakes:
            veh.close()
        for proc, handle, _path in self.managers:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            handle.close()
        self.mq.loop_stop()
        self.mq.disconnect()


@pytest.fixture()
def rig(tmp_path):
    broker = subprocess.Popen(
        [BROKER, "-p", PORT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ, "LD_LIBRARY_PATH": BROKER_LIB})
    assert _wait_listening(int(PORT)), (
        "vendored mosquitto did not listen on {} (exit {!r}) - check "
        "LD_LIBRARY_PATH={}".format(PORT, broker.poll(), BROKER_LIB))
    rig = Rig(PORT, str(tmp_path))
    yield rig
    rig.close()
    broker.terminate()
    broker.wait(timeout=5)


def wait_for(pred, timeout_s, what, rig=None):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        value = pred()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("timed out after {}s waiting for {}{}".format(
        timeout_s, what, "" if rig is None else rig.logs()))


def ready(rig, serials):
    """The document says every named truck is ONLINE, AUTOMATIC, placed
    and freshly heard from - the manager's own idle clauses, read back
    off the operator's screen."""
    doc = rig.status()
    if doc is None:
        return None
    for serial in serials:
        row = doc["vehicles"].get(serial)
        if not row or row["connection"] != "ONLINE" \
                or row["operating_mode"] != "AUTOMATIC" \
                or row["position"] is None \
                or row["state_age_s"] is None or row["state_age_s"] > 3.0:
            return None
    return doc


def when(rig, test):
    """The latest document if it satisfies test, else None - and it is
    read ONCE, so the assertion afterwards holds the same snapshot the
    predicate approved."""
    doc = rig.status()
    return doc if doc is not None and test(doc) else None


def task_named(doc, task_id):
    return next((t for t in doc["tasks"] if t["task_id"] == task_id), None)


def check_leg(order, serial, station):
    """Every order this manager publishes is held against the vehicle's
    own door, not against a shape this test invented."""
    assert vo.validate_order(order) == "", \
        "the manager published an order the vehicle would reject"
    assert order["orderId"].startswith("ft-"), order["orderId"]
    assert order["nodes"][-1]["nodeId"] == station
    assert order["nodes"][-1]["nodePosition"]["allowedDeviationXY"] == \
        STATIONS[station]["arrive_m"], "the station's own arrival radius"
    # M1 s.3: serialNumber names the vehicle the topic addresses.
    assert order["serialNumber"] == serial
    assert order["headerId"] >= 1 and order["manufacturer"] == "amragent"


def test_two_transports_walk_leg_dwell_leg_to_done(rig):
    """Assignment, the dwell, leg 2 and DONE - twice, in parallel."""
    f1 = rig.fake("f1", S1)          # standing on the pickup
    f2 = rig.fake("f2", S5)          # the far side of the hall
    rig.manager()
    wait_for(lambda: ready(rig, ("f1", "f2")), 15.0,
             "both trucks ready in the status document", rig)
    rig.submit("t-1", "S1", "S4")
    rig.submit("t-2", "S1", "S4")
    wait_for(lambda: rig.orders_for("f1") and rig.orders_for("f2"), 15.0,
             "one leg-1 order to each truck", rig)
    for serial in ("f1", "f2"):
        check_leg(rig.orders_for(serial)[0][1], serial, "S1")
    # Two tasks, two trucks, never twice on one: the second assignment
    # happens a drain pass after the first, when f1's own state has not
    # caught up yet and only the fleet's book knows it is taken.
    doc = wait_for(lambda: when(rig, lambda d: len(
        [t for t in d["tasks"] if t["assignee"]]) == 2), 10.0,
        "both tasks assigned", rig)
    assert {t["assignee"] for t in doc["tasks"]} == {"f1", "f2"}

    arrived_at = time.monotonic()
    f1.arrive()
    f2.arrive()
    wait_for(lambda: len(rig.orders_for("f1")) == 2
             and len(rig.orders_for("f2")) == 2, 15.0,
             "a leg-2 order to each truck once the dwell ran out", rig)
    for serial in ("f1", "f2"):
        stamp, order = rig.orders_for(serial)[1]
        check_leg(order, serial, "S4")
        assert order["nodes"][0]["nodePosition"]["x"] == S1[0], \
            "leg 2 must start at the pickup station, not at a live pose"
        assert stamp - arrived_at >= fm.DWELL_S - 0.1, \
            "leg 2 went out before the dwell was over"

    f1.arrive()
    f2.arrive()
    doc = wait_for(lambda: when(rig, lambda d: len(d["tasks"]) == 2 and all(
        t["state"] == "DONE" for t in d["tasks"])), 15.0,
        "both tasks DONE in the retained document", rig)
    assert doc["queue_len"] == 0
    assert all(t["done_ts"] for t in doc["tasks"])


def test_a_dwelling_truck_is_not_idle_and_the_queue_waits_for_it(rig):
    """THE DOUBLE-BOOKING PROBE, and the queueing gate in one run.

    Three tasks, two trucks. The third can only go to whoever frees
    first - and the trap is the dwell: a truck standing at the pickup
    reports its orderId with an EMPTY nodeStates, which is the wire's
    own word for "nothing left to drive". Read that alone and the fleet
    hands it a second transport while it still owes a leg 2. So the
    assertion below is made INSIDE the dwell window, where a manager
    that trusted the wire would already have double-booked f1.
    """
    f1 = rig.fake("f1", S1)
    rig.fake("f2", S5)
    rig.manager()
    wait_for(lambda: ready(rig, ("f1", "f2")), 15.0, "both trucks ready", rig)
    for task_id in ("t-a", "t-b", "t-c"):
        rig.submit(task_id, "S1", "S4")
    wait_for(lambda: when(rig, lambda d: len(
        [t for t in d["tasks"] if t["assignee"]]) == 2), 15.0,
        "two of the three tasks assigned", rig)
    doc = rig.status()
    assert task_named(doc, "t-c")["state"] == "QUEUED", "FIFO: c is last"
    assert doc["queue_len"] == 1

    f1.arrive()                      # leg 1 done - the dwell starts
    wait_for(lambda: when(rig, lambda d: task_named(d, "t-a")["state"]
                          == "DWELL"), 10.0, "t-a dwelling", rig)
    time.sleep(1.0)                  # still inside DWELL_S, at 10 Hz
    doc = rig.status()
    assert task_named(doc, "t-a")["state"] == "DWELL"
    assert task_named(doc, "t-c")["assignee"] is None, \
        "a dwelling truck was handed the queued task"
    assert len(rig.orders_for("f1")) == 1, \
        "a second order reached a truck that still owes a leg 2"
    assert doc["vehicles"]["f1"]["executing_order"], \
        "the dwelling truck must not read as idle on the screen either"

    wait_for(lambda: len(rig.orders_for("f1")) == 2, 10.0,
             "f1's leg-2 order once the dwell ran out", rig)
    f1.arrive()                      # t-a DONE - now f1 really is free
    doc = wait_for(lambda: when(rig, lambda d: task_named(d, "t-c")
                                ["assignee"] == "f1"), 15.0,
                   "the queued task going to the truck that freed", rig)
    assert task_named(doc, "t-a")["state"] == "DONE"
    assert doc["queue_len"] == 0
    assert len(rig.orders_for("f1")) == 3


def test_a_rejection_requeues_to_the_head_and_the_other_truck_takes_it(rig):
    """The nearest truck refuses on the wire; the task does not die."""
    f1 = rig.fake("f1", S1)
    rig.fake("f2", S5)
    f1.reject_next = True
    f1.manual_after_reject = True
    rig.manager()
    wait_for(lambda: ready(rig, ("f1", "f2")), 15.0, "both trucks ready", rig)
    rig.submit("t-9", "S1", "S4")
    wait_for(lambda: rig.orders_for("f1"), 15.0,
             "the nearest truck was asked first", rig)
    refused = rig.orders_for("f1")[0][1]["orderId"]
    wait_for(lambda: rig.orders_for("f2"), 15.0,
             "the other truck picked the requeued task up", rig)
    check_leg(rig.orders_for("f2")[0][1], "f2", "S1")
    assert rig.orders_for("f2")[0][1]["orderId"] != refused

    doc = wait_for(lambda: when(rig, lambda d: (task_named(d, "t-9") or {})
                                .get("assignee") == "f2"), 10.0,
                   "t-9 reassigned to f2 in the document", rig)
    task = task_named(doc, "t-9")
    assert any("requeued to head" in line for line in task["history"]), \
        task["history"]
    assert doc["vehicles"]["f1"]["not_eligible"] is True, \
        "the refusing truck must stand down until it is clean again"
    assert doc["vehicles"]["f1"]["operating_mode"] == "MANUAL"


def test_a_lost_truck_gives_its_task_back_and_is_cancelled_on_return(rig):
    """The owner's loss ruling, end to end, including the return race."""
    f1 = rig.fake("f1", DOCK_W)      # 5 m from S1 - nearest, and driving
    rig.fake("f2", S5)
    rig.manager()
    wait_for(lambda: ready(rig, ("f1", "f2")), 15.0, "both trucks ready", rig)
    rig.submit("t-loss", "S1", "S4")
    wait_for(lambda: rig.orders_for("f1"), 15.0,
             "the nearest truck took the task", rig)
    stale = rig.orders_for("f1")[0][1]["orderId"]

    f1.yank()                        # the will fires; f1 keeps the order
    doc = wait_for(lambda: when(rig, lambda d: d["vehicles"].get(
        "f1", {}).get("lost")), 15.0, "f1 marked lost in the document", rig)
    assert doc["vehicles"]["f1"]["connection"] == "CONNECTIONBROKEN"
    wait_for(lambda: rig.orders_for("f2"), 15.0,
             "the other truck took the requeued task", rig)
    doc = rig.status()
    assert task_named(doc, "t-loss")["assignee"] == "f2"

    mark = time.monotonic()
    f1.revive()                      # back, still holding the stale order
    wait_for(lambda: f1.cancels, 15.0,
             "cancelOrder to the returning truck", rig)
    sent = [(t, s, a) for t, s, a in rig.actions_since(mark) if s == "f1"]
    assert len(sent) == 1, "the cancel must be sent once, not repeatedly"
    action = sent[0][2]
    assert action["serialNumber"] == "f1"
    assert action["actions"][0]["actionType"] == "cancelOrder"
    assert action["actions"][0]["actionId"], "a cancel needs an actionId"
    assert stale not in ("", None)
    # A RETURNED TRUCK RE-EARNS ELIGIBILITY, it is not simply given it -
    # and it re-earns it fast (the cancel clears its order within the
    # second), so the document that showed it back and still standing
    # down is looked for in the record, not in the latest snapshot.
    wait_for(lambda: rig.find_status(
        lambda d: d["vehicles"].get("f1", {}).get("lost") is False
        and d["vehicles"]["f1"]["not_eligible"] is True, since=mark),
        10.0, "f1 back ONLINE and standing down", rig)


def test_a_restarted_manager_adopts_by_waiting_and_says_the_queue_is_empty(
        rig):
    """No journal, no double booking, and no startup cancelOrder."""
    f1 = rig.fake("f1", DOCK_W)
    first = rig.manager()
    wait_for(lambda: ready(rig, ("f1",)), 15.0, "the truck is ready", rig)
    rig.submit("t-restart", "S1", "S4")
    wait_for(lambda: rig.orders_for("f1"), 15.0, "f1 is driving a leg", rig)
    assert f1.remaining, "f1 must still be mid-leg when the manager dies"

    rig.kill(first)
    mark = time.monotonic()
    rig.manager()
    doc = wait_for(lambda: rig.status(since=mark), 15.0,
                   "the new manager's own status document", rig)
    # NO JOURNAL, and the document says so rather than inventing a queue.
    assert doc["tasks"] == [] and doc["queue_len"] == 0
    assert doc["manager"] == "ONLINE"

    time.sleep(2.0)                  # room to misbehave, at 10 Hz
    assert not rig.orders_for("f1", since=mark), \
        "the restarted manager handed a second order to a driving truck"
    assert not rig.actions_since(mark), \
        "the restarted manager cancelled an order it never sent"
    assert rig.status(since=mark)["vehicles"]["f1"]["executing_order"], \
        "an adopted truck must not read as idle while it drives"

    # ADOPT-BY-WAITING FINISHES ITSELF: the leg lands, nothing is left to
    # drive, and the truck is eligible again with no cancel anywhere.
    f1.arrive()
    rig.submit("t-restart-2", "S1", "S4")
    wait_for(lambda: rig.orders_for("f1", since=mark), 15.0,
             "the freed truck takes the resubmitted task", rig)
    check_leg(rig.orders_for("f1", since=mark)[0][1], "f1", "S1")
    assert not rig.actions_since(mark), "still no cancelOrder anywhere"


def test_submissions_are_refused_with_a_reason_the_operator_can_read(rig):
    """The admin wire's door. Unknown stations and A-to-A never queue."""
    rig.fake("f1", S1)
    rig.manager()
    wait_for(lambda: ready(rig, ("f1",)), 15.0, "the truck is ready", rig)
    rig.submit("t-bad-1", "S99", "S4")
    rig.submit("t-bad-2", "S4", "S4")
    doc = wait_for(lambda: when(rig, lambda d: len(d["refused"]) == 2),
                   10.0, "two refusals in the document", rig)
    whys = " ".join(r["why"] for r in doc["refused"])
    assert "unknown from station" in whys and "same station" in whys
    assert doc["tasks"] == [] and doc["queue_len"] == 0
    assert not rig.orders_for("f1"), "a refused task must reach no truck"
