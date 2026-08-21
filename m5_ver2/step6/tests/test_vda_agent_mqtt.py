"""The agent against a real broker - order in, route out, honest wires.

Runs a private mosquitto on 18883 (no collision with a live stack) and
a real rclpy context. Skips, loudly, when paho or the vendored broker
is absent - a skip here is an environment statement, not a pass.

THE BROKER NEEDS ITS LIBRARIES ON THE SPAWN LINE. tools/install_broker.sh
unpacks libwrap, libdlt and libwebsockets beside the binary rather than
into the system, so the loader finds none of them by default and the
child exits 127 - a broker that "started" and is not listening, which
reads as a paho timeout three assertions later. step6.sh spells the same
path in BROKER_LIB; this is the second and last place it exists.
"""
import json
import os
import socket
import subprocess
import threading
import time

import pytest

mqtt = pytest.importorskip("paho.mqtt.client")
rclpy = pytest.importorskip("rclpy")

VENDORED = os.path.expanduser("~/.local/mosquitto-vendored")
BROKER = os.path.join(VENDORED, "usr", "sbin", "mosquitto")
BROKER_LIB = os.path.join(VENDORED, "usr", "lib", "x86_64-linux-gnu")
pytestmark = pytest.mark.skipif(
    not os.path.exists(BROKER),
    reason="vendored mosquitto missing - run tools/install_broker.sh")

PORT = "18883"


def _wait_listening(port, timeout_s=5.0):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.2):
                return True
        except OSError:
            time.sleep(0.05)
    return False


@pytest.fixture()
def rig():
    from std_msgs.msg import String
    broker = subprocess.Popen(
        [BROKER, "-p", PORT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ, "LD_LIBRARY_PATH": BROKER_LIB})
    assert _wait_listening(int(PORT)), (
        "vendored mosquitto did not listen on {} (exit {!r}) - check "
        "LD_LIBRARY_PATH={}".format(PORT, broker.poll(), BROKER_LIB))
    os.environ["VDA_MQTT_PORT"] = PORT
    # BOTH TRANSPORTS ARE FENCED, AND THE ROS ONE IS THE DANGEROUS HALF.
    # MQTT is private already (its own broker on 18883). DDS is not: the
    # live stack runs at ROS_DOMAIN_ID 96 (step6.sh:48), and this test
    # publishes /f1/auto/route - on 96 that is a real forklift being
    # handed a real route by a test run. 89 is nobody's. VEHICLE is SET,
    # not defaulted, for the same reason: inheriting f2 from an operator
    # shell would aim every topic here at the other truck.
    os.environ["ROS_DOMAIN_ID"] = "89"
    os.environ["VEHICLE"] = "f1"
    rclpy.init()
    import vda_agent
    agent = vda_agent.VdaAgent()
    caught = {"route": [], "goal": [], "mqtt": []}
    helper = rclpy.create_node("test_helper")
    from status_contract import AUTO_ROUTE_TOPIC, AUTO_GOAL_TOPIC, \
        MODE_TOPIC, AUTO_STATE_TOPIC
    from rclpy.qos import DurabilityPolicy, QoSProfile
    helper.create_subscription(
        String, AUTO_ROUTE_TOPIC,
        lambda m: caught["route"].append(json.loads(m.data)), 10)
    helper.create_subscription(
        String, AUTO_GOAL_TOPIC,
        lambda m: caught["goal"].append(m.data), 10)
    latched = QoSProfile(
        depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    mode_pub = helper.create_publisher(String, MODE_TOPIC, latched)
    nav_pub = helper.create_publisher(String, AUTO_STATE_TOPIC, 10)
    # The probe subscribes FROM its on_connect and the fixture waits for
    # the SUBACK: subscribing on the caller's thread races the CONNACK,
    # and a lost subscription here fails as "the agent published
    # nothing", which is a lie about the agent.
    subscribed = threading.Event()
    probe = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="probe")
    probe.on_connect = lambda c, u, f, rc, p=None: c.subscribe(
        "uagv/v2/amragent/f1/#", qos=1)
    probe.on_subscribe = lambda *a, **k: subscribed.set()
    probe.on_message = lambda c, u, m: caught["mqtt"].append(
        (m.topic, json.loads(m.payload.decode())))
    probe.connect("127.0.0.1", int(PORT))
    probe.loop_start()
    assert subscribed.wait(5.0), "probe never got its SUBACK"
    yield agent, helper, caught, mode_pub, nav_pub, probe
    probe.loop_stop()
    # close() before destroy_node(): a leaked paho loop reconnects, and
    # the next test's agent carries the same client_id, so the broker
    # would evict whichever of the two connected first.
    agent.close()
    agent.destroy_node()
    helper.destroy_node()
    rclpy.try_shutdown()
    broker.terminate()
    broker.wait(timeout=5)


def spin(nodes, seconds):
    from rclpy.executors import SingleThreadedExecutor
    end = time.monotonic() + seconds
    ex = SingleThreadedExecutor()
    for n in nodes:
        ex.add_node(n)
    while time.monotonic() < end:
        ex.spin_once(timeout_sec=0.05)
    for n in nodes:
        ex.remove_node(n)


def valid_order():
    return {"orderId": "o-int-1", "orderUpdateId": 0,
            "nodes": [
                {"nodeId": "wp0", "sequenceId": 0, "released": True,
                 "actions": [], "nodePosition":
                     {"x": 0.0, "y": 0.0, "mapId": "warehouse"}},
                {"nodeId": "S4", "sequenceId": 2, "released": True,
                 "actions": [], "nodePosition":
                     {"x": 6.0, "y": -8.0, "mapId": "warehouse",
                      "allowedDeviationXY": 0.25}}],
            "edges": [
                {"edgeId": "e0", "sequenceId": 1, "released": True,
                 "startNodeId": "wp0", "endNodeId": "S4", "actions": []}]}


def test_online_retained_and_order_to_route(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    assert any(t.endswith("/connection") and p["connectionState"] == "ONLINE"
               for t, p in caught["mqtt"])
    assert any(t.endswith("/factsheet") for t, p in caught["mqtt"])
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert caught["route"], "no route published for a valid order"
    req = caught["route"][0]
    assert req["label"] == "o-int-1" and req["arrive_m"] == 0.25
    assert req["points"][-1] == [6.0, -8.0]
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    assert any(s["orderId"] == "o-int-1" for s in states)


def test_teleop_order_is_rejected_on_the_wire(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="teleop"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert not caught["route"]
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    assert any(any(e["errorType"] == "orderError" for e in s["errors"])
               for s in states)


def test_arrival_closes_the_order(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    nav_pub.publish(String(data=json.dumps(
        {"state": "ARRIVED", "goal": "o-int-1"})))
    spin([agent, helper], 1.0)
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    done = [s for s in states if s["orderId"] == "o-int-1"
            and s["nodeStates"] == []]
    assert done and done[-1]["lastNodeId"] == "S4"


def test_unsupported_instant_action_fails_and_says_why(rig):
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    probe.publish("uagv/v2/amragent/f1/instantActions", json.dumps(
        {"actions": [{"actionId": "a-9", "actionType": "startCharging",
                      "blockingType": "NONE", "actionParameters": []}]}),
        qos=0)
    spin([agent, helper], 1.0)
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    failed = [s for s in states
              if any(a["actionId"] == "a-9" and a["actionStatus"] == "FAILED"
                     for a in s["actionStates"])]
    assert failed, "the unsupported action never reported FAILED"
    said_why = [e for e in failed[0]["errors"]
                if e["errorType"] == "unsupportedAction"]
    assert said_why and said_why[0]["errorReferences"] == [
        {"referenceKey": "actionId", "referenceValue": "a-9"}]


def test_nav_refusal_stops_the_agent_believing_it_drives(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert agent.executing, "the order was never taken up"
    before = len([p for t, p in caught["mqtt"] if t.endswith("/state")])
    # What nav_core publishes when the mode leaves auto mid-drive:
    # _cancel("mode left auto") -> IDLE, goal None, note set.
    nav_pub.publish(String(data=json.dumps(
        {"state": "IDLE", "goal": None, "note": "mode left auto",
         "route": [], "pose": [0.0, 0.0, 0.0]})))
    spin([agent, helper], 1.0)
    assert not agent.executing, "the agent still believes it is driving"
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    assert len(states) > before, "no state told the fleet manager"
    # The order is KEPT - only the belief that it is running is gone.
    assert agent.order["orderId"] == "o-int-1"
    assert agent.progress is not None
    assert states[-1]["orderId"] == "o-int-1"


def test_a_stale_nav_note_does_not_cancel_a_fresh_route(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert agent.executing
    # The cancelOrder-then-new-order sequence: nav's "cancelled" note
    # repeats on every state it sends, so the one already in flight when
    # the route goes out looks exactly like a refusal of a route nav has
    # not read yet. Restamping route_sent_at IS "the route just went
    # out" - the spin below stays inside NAV_SETTLE_S on purpose.
    agent.route_sent_at = time.monotonic()
    nav_pub.publish(String(data=json.dumps(
        {"state": "IDLE", "goal": None, "note": "cancelled",
         "route": [], "pose": [0.0, 0.0, 0.0]})))
    spin([agent, helper], 0.2)
    assert agent.executing, "a state older than the route cancelled it"


def test_resume_without_automatic_holds_the_order(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    routes = len(caught["route"])
    # The shift went to teleop while the broker was down; supervision
    # comes back and asks for the drive again.
    agent.mode = "teleop"
    agent.executing = False
    agent._resume()
    spin([agent, helper], 0.5)
    assert len(caught["route"]) == routes, "asked nav for a refused drive"
    assert not agent.executing
    assert agent.order["orderId"] == "o-int-1", "the order was dropped"
