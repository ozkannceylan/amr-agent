"""The agent against a real broker - order in, route out, honest wires.

Runs a private mosquitto on 18883 (no collision with a live stack) and
a real rclpy context. Skips, loudly, when paho or the vendored broker
is absent - a skip here is an environment statement, not a pass.

THE BROKER NEEDS ITS LIBRARIES ON THE SPAWN LINE. tools/install_broker.sh
unpacks libwrap, libdlt and libwebsockets beside the binary rather than
into the system, so the loader finds none of them by default and the
child exits 127 - a broker that "started" and is not listening, which
reads as a paho timeout three assertions later. m6.sh spells the same
path in BROKER_LIB; this is the second and last place it exists.
"""
import json
import os
import socket
import subprocess
import sys
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


def _ensure_f1_config():
    """vehicles/ is gitignored; the agent reads f1's derived config.yaml.

    On the owner's rig `m6.sh deploy` has already written it. In CI the
    checkout is clean, so this is the same tool the deploy uses, for
    one vehicle, before rclpy.init().
    """
    root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = os.path.join(root, "vehicles", "f1", "config.yaml")
    if os.path.isfile(cfg):
        return
    script = os.path.join(root, "tools", "instantiate_vehicle.py")
    subprocess.check_call([sys.executable, script, "f1"])


@pytest.fixture()
def rig():
    from std_msgs.msg import String
    _ensure_f1_config()
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
    # live stack runs at ROS_DOMAIN_ID 96 (m6.sh:48), and this test
    # publishes /f1/auto/route - on 96 that is a real forklift being
    # handed a real route by a test run. 89 is nobody's. VEHICLE is SET,
    # not defaulted, for the same reason: inheriting f2 from an operator
    # shell would aim every topic here at the other truck.
    os.environ["ROS_DOMAIN_ID"] = "89"
    os.environ["VEHICLE"] = "f1"
    rclpy.init()
    agent = helper = probe = None
    try:
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
    finally:
        if probe is not None:
            probe.loop_stop()
        if agent is not None:
            # close() before destroy_node(): a leaked paho loop reconnects,
            # and the next test's agent carries the same client_id, so the
            # broker would evict whichever of the two connected first.
            agent.close()
            agent.destroy_node()
        if helper is not None:
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
    """AN ARRIVAL IS TWO FACTS (M6.5): nav has finished the polyline it
    was handed AND the truck's own odometry puts it past the last node
    the fleet released. So the odometry is published here rather than
    left at the origin - a real truck's always is, and nav_node stops a
    truck whose pose has gone stale, so an ARRIVED with no odometry
    behind it is not a state this vehicle can be in."""
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    odom = odom_publisher(helper)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    drive_to(odom, 6.0, -8.0)                 # the truck reaches S4
    spin([agent, helper], 0.5)
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


# ---- the closed-loop cancel (M6.3 Fleet Gate 4) ----
# Fleet Gate 4 measured a cancelOrder that was received, acknowledged
# FINISHED, and did not stop the truck: the empty goal it published went
# out of a publisher younger than DDS discovery and reached nobody,
# while nav drove the stale route for another 37.09 s and 6.743 m. These
# four tests are that bug, asked four ways. THE RIG HAS NO nav_node, so
# "unheard" is the default here and does not need faking - nothing
# answers /auto/goal until a test publishes an /auto/state that says so.


def cancel_action(probe, action_id="a-cancel"):
    probe.publish("uagv/v2/amragent/f1/instantActions", json.dumps(
        {"actions": [{"actionId": action_id, "actionType": "cancelOrder",
                      "blockingType": "HARD", "actionParameters": []}]}),
        qos=0)


def action_status(caught, action_id):
    """The last actionStatus reported for this action, or None."""
    last = None
    for topic, payload in caught["mqtt"]:
        if not topic.endswith("/state"):
            continue
        for act in payload.get("actionStates", []):
            if act["actionId"] == action_id:
                last = act["actionStatus"]
    return last


def test_a_cancel_keeps_asking_until_nav_says_it_stopped(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert agent.executing, "the order was never taken up"

    cancel_action(probe)
    spin([agent, helper], 1.0)
    # NOTHING HAS ANSWERED, so the agent is still asking. One publish
    # would have been the bug; a second is the fix.
    unheard = len(caught["goal"])
    assert unheard >= 5, (
        "the empty goal went out {} times in a second - a cancel nobody "
        "answered has to keep asking".format(unheard))
    assert caught["goal"] == [""] * unheard
    assert agent.cancel_pending is not None
    assert action_status(caught, "a-cancel") == "RUNNING", (
        "FINISHED is a claim about the truck, and no truck has said "
        "anything yet")
    # The order is gone from the agent all the same: it stopped owning
    # the work the moment the fleet asked.
    assert agent.order is None and not agent.executing

    # nav_core._cancel: IDLE, goal None, note set. That is a stop SEEN.
    nav_pub.publish(String(data=json.dumps(
        {"state": "IDLE", "goal": None, "note": "cancelled",
         "route": [], "pose": [0.0, 0.0, 0.0]})))
    spin([agent, helper], 0.6)
    assert agent.cancel_pending is None, "the cancel never closed"
    assert action_status(caught, "a-cancel") == "FINISHED"
    settled = len(caught["goal"])
    spin([agent, helper], 0.5)
    assert len(caught["goal"]) == settled, (
        "the agent kept publishing empty goals after nav confirmed")


def test_a_cancel_nav_never_confirms_reports_FAILED(rig, monkeypatch):
    from std_msgs.msg import String
    import vda_agent
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    monkeypatch.setattr(vda_agent, "CANCEL_CONFIRM_S", 0.5)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert agent.executing

    cancel_action(probe, "a-never")
    spin([agent, helper], 1.5)     # well past the shortened deadline
    assert agent.cancel_pending is None, "the deadline never fired"
    assert action_status(caught, "a-never") == "FAILED", (
        "a stop nobody confirmed must not report FINISHED")
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    said = [e for s in states for e in s["errors"]
            if e["errorType"] == "cancelUnconfirmed"]
    assert said, "the state stream never told the fleet the cancel failed"
    assert "may still be driving" in said[-1]["errorDescription"]


def test_supervision_loss_chases_its_stop_the_same_way(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert agent.executing
    before = len(caught["goal"])

    agent._supervision_lost()
    spin([agent, helper], 0.8)
    assert len(caught["goal"]) - before >= 4, (
        "the broker-loss stop was published once and forgotten")
    assert agent.cancel_pending is not None
    # NOBODY ASKED FOR THIS ONE, so it wears no actionState at all.
    assert not [a for a in agent.action_states
                if a["actionType"] == "cancelOrder"]
    # And the ORDER SURVIVES it - that is M1 s.7, unchanged.
    assert agent.order["orderId"] == "o-int-1"

    nav_pub.publish(String(data=json.dumps(
        {"state": "IDLE", "goal": None, "note": "cancelled",
         "route": [], "pose": [0.0, 0.0, 0.0]})))
    spin([agent, helper], 0.6)
    assert agent.cancel_pending is None
    assert agent.order["orderId"] == "o-int-1"


def test_an_unmatched_nav_is_named_before_the_retries_begin(rig):
    """The belt beside the braces: the retry loop already covers a
    publisher DDS has not matched, but Fleet Gate 4 spent 37 s inside
    exactly that window with nothing in any log to say so."""
    agent, helper, caught, mode_pub, nav_pub, probe = rig

    class Unmatched:
        def __init__(self):
            self.sent = []

        def get_subscription_count(self):
            return 0

        def publish(self, msg):
            self.sent.append(msg.data)

    said = []

    class Log:
        def __getattr__(self, _level):
            return said.append

    agent.pub_goal = Unmatched()
    agent.get_logger = lambda: Log()
    agent.executing = True
    agent.nav_state = ""
    agent._begin_cancel(action_id="a-blind")
    for _ in range(4):
        agent._pump_cancel()

    assert agent.pub_goal.sent == [""] * 5, "the retry stopped at one"
    assert any("has not matched" in m for m in said), (
        "nothing in the log names the window the goal was lost in")
    assert sum("has not matched" in m for m in said) == 1, (
        "one line, not one per retry")


# ---- the growing base (VDA 5050 s.6.6, M6.4) ----
# An update that only adds floor past what the truck was already told to
# drive is stitched onto the order in flight: same orderId, one higher
# orderUpdateId, released prefix untouched. Nothing about it may be
# visible to the truck - no stop, no cancel, and above all no count
# reset, because lastNodeId walking backwards is a lie the fleet's
# traffic ledger acts on (it frees the floor behind a vehicle).


def growing_order(released_n, update_id, devs=None, order_id="o-grow",
                  count=5):
    """Five nodes on a line at y=0, x = 0, 2, 4, 6, 8.

    The first `released_n` are base, the rest horizon. `devs` sets
    allowedDeviationXY per node id - the radius that decides passing
    (Progress) and, on the last released node, arrival (arrive_m).

    `count` is how many of those five the message carries at all, and
    it exists for one shape only: an update that SHRINKS the horizon.
    This fleet's order_builder cannot make one - it rebuilds the same
    full point list every time and only ever moves the release cut - so
    the shrink is written here, directly, and pinned by the tests that
    use it rather than left to be discovered.
    """
    devs = devs or {}
    nodes = []
    for i in range(count):
        nid = "wp{}".format(i)
        pos = {"x": 2.0 * i, "y": 0.0, "mapId": "warehouse"}
        if nid in devs:
            pos["allowedDeviationXY"] = devs[nid]
        nodes.append({"nodeId": nid, "sequenceId": 2 * i,
                      "released": i < released_n, "actions": [],
                      "nodePosition": pos})
    edges = [{"edgeId": "e{}".format(i), "sequenceId": 2 * i + 1,
              "released": i + 1 < released_n,
              "startNodeId": "wp{}".format(i),
              "endNodeId": "wp{}".format(i + 1), "actions": []}
             for i in range(count - 1)]
    return {"orderId": order_id, "orderUpdateId": update_id,
            "nodes": nodes, "edges": edges}


def send_order(probe, order):
    probe.publish("uagv/v2/amragent/f1/order", json.dumps(order), qos=0)


def odom_publisher(helper):
    """The truck's own odometry, on the topic config.yaml names for it."""
    import yaml
    from nav_msgs.msg import Odometry
    from status_contract import CONFIG_PATH
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        topic = yaml.safe_load(handle)["topics"]["gz_odom"]
    return helper.create_publisher(Odometry, topic, 10)


def drive_to(pub, x, y):
    from nav_msgs.msg import Odometry
    msg = Odometry()
    msg.pose.pose.position.x = float(x)
    msg.pose.pose.position.y = float(y)
    msg.pose.pose.orientation.w = 1.0
    pub.publish(msg)


def states_of(caught, order_id):
    return [p for t, p in caught["mqtt"]
            if t.endswith("/state") and p["orderId"] == order_id]


def test_an_extension_drives_only_what_is_left(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    odom = odom_publisher(helper)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    send_order(probe, growing_order(2, 0, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    assert len(caught["route"]) == 1, "the first order never went to nav"
    assert agent.executing
    # The truck drives its two released nodes and stands on the second.
    # wp2..wp4 are horizon: it has been told nothing about them.
    drive_to(odom, 2.0, 0.0)
    spin([agent, helper], 0.5)
    assert agent.progress.reached == 2, "the truck never passed its base"
    assert states_of(caught, "o-grow")[-1]["newBaseRequest"], (
        "a truck standing on the end of its base with a horizon left "
        "is asking for more of it")

    before = len(caught["route"])
    send_order(probe, growing_order(
        4, 1, {"wp1": 2.5, "wp2": 1.5, "wp3": 0.5}))
    spin([agent, helper], 1.5)
    assert len(caught["route"]) == before + 1, "the extension never drove"
    route = caught["route"][-1]
    assert route["label"] == "o-grow", "an extension keeps its orderId"
    assert route["points"] == [[2.0, 0.0], [4.0, 0.0], [6.0, 0.0]], (
        "the truck was sent back over floor it had already driven: "
        "{}".format(route["points"]))
    assert route["arrive_m"] == 0.5, "the new final node sets arrival"
    # NOT A STOP IN ANY FORM. No empty goal, no cancelOrder actionState,
    # and `executing` never flickered - this is the whole point of s.6.6.
    assert caught["goal"] == [], "an extension published a stop"
    assert agent.executing, "an extension stopped the truck"
    states = states_of(caught, "o-grow")
    assert not [a for s in states for a in s["actionStates"]
                if a["actionType"] == "cancelOrder"]

    # THE COUNT SURVIVED. reached is a count, and it is still counting
    # the same two nodes - so lastNodeId cannot have moved.
    assert agent.progress.reached == 2
    seq = [s["lastNodeSequenceId"] for s in states]
    assert seq == sorted(seq), (
        "lastNodeSequenceId walked backwards: {}".format(seq))
    ids = [s["lastNodeId"] for s in states]
    assert "" not in ids[ids.index("wp1"):], (
        "lastNodeId went back to nothing: {}".format(ids))
    updates = [s["orderUpdateId"] for s in states]
    assert updates == sorted(updates) and updates[-1] == 1, (
        "the state stream never followed the update: {}".format(updates))
    assert states[-1]["nodeStates"] == [
        {"nodeId": "wp2", "sequenceId": 4, "released": True},
        {"nodeId": "wp3", "sequenceId": 6, "released": True},
        {"nodeId": "wp4", "sequenceId": 8, "released": False}], (
        "the state does not describe the grown base")
    assert not states[-1]["newBaseRequest"], "there is base left to drive"


def test_navs_arrival_at_the_end_of_a_base_does_not_end_the_order(rig):
    """THE DEFECT M6.4 GATE 1 FOUND, ON THE FLOOR, 2026-08-22.

    A horizon-held truck drives its base and stops. nav, which was handed
    the released nodes and nothing else, reports ARRIVED - and the agent
    read that as "the order is done", cleared `executing`, and refused
    every extension that followed with "no order is executing - nothing
    to extend". Measured live: 1,873 refusals over 3 m 37 s, a truck
    three metres short of floor that had been free for two minutes, and
    a transport that never completed. A held vehicle could never be let
    go, which is the whole of M6.4.

    The base end is a WAIT, not an arrival. `executing` must survive it,
    and the order must still be extendable afterwards.
    """
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    odom = odom_publisher(helper)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    send_order(probe, growing_order(2, 0, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    drive_to(odom, 2.0, 0.0)                 # the truck reaches wp1
    spin([agent, helper], 0.5)
    assert agent.progress.reached == 2

    # nav finished the polyline it was given. That is all it said.
    nav_pub.publish(String(data=json.dumps(
        {"state": "ARRIVED", "goal": "o-grow", "note": ""})))
    spin([agent, helper], 1.0)
    assert agent.executing, (
        "the end of a base was read as the end of the order - every "
        "extension after this is refused and the truck never moves again")
    last = states_of(caught, "o-grow")[-1]
    assert last["newBaseRequest"], "a held truck must still be asking"
    assert [n["nodeId"] for n in last["nodeStates"]] ==         ["wp2", "wp3", "wp4"], "the horizon was thrown away"

    # ...and the extension the fleet has been waiting to send lands.
    before = len(caught["route"])
    send_order(probe, growing_order(5, 1, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    # orderError only: this rig has no PLC behind it, so a safetyStop
    # rides every state it publishes and says nothing about the update.
    refusals = [e for s in states_of(caught, "o-grow") for e in s["errors"]
                if e["errorType"] == "orderError"]
    assert refusals == [], "the extension was refused: {}".format(refusals)
    assert len(caught["route"]) == before + 1, "the extension never drove"
    assert caught["route"][-1]["points"] == [
        [2.0, 0.0], [4.0, 0.0], [6.0, 0.0], [8.0, 0.0]], (
        "the truck was not sent on from where it stood")
    assert agent.progress.reached == 2, "the count reset on the update"


def test_a_new_deviation_binds_ahead_of_the_truck_and_not_behind(rig):
    """The M6.4 ruling on allowedDeviationXY, both halves.

    _base_kept lets an update change a released node's deviation - it is
    not position. On a node ALREADY PASSED the change is ignored: the
    radius only ever decided whether the truck passed it, and it did.
    On the nodes still in front, and on the final one, it takes effect,
    because those radii still decide passing and arrival.
    """
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    odom = odom_publisher(helper)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    send_order(probe, growing_order(2, 0, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    drive_to(odom, 2.0, 0.0)
    spin([agent, helper], 0.5)
    assert agent.progress.reached == 2

    # wp1 is behind the truck and its radius is widened tenfold; wp2 is
    # in front and gets 1.5 m, nearly twice DEFAULT_DEV_M.
    send_order(probe, growing_order(
        4, 1, {"wp1": 2.5, "wp2": 1.5, "wp3": 0.5}))
    spin([agent, helper], 1.5)
    assert agent.progress.reached == 2, "a passed node was recounted"
    assert agent.progress.last_node() == ("wp1", 2)

    # 1.4 m short of wp2: inside the 1.5 m the update asked for, outside
    # the 0.8 m default it would have had otherwise, and 0.6 m from wp3,
    # which asked for 0.5 - so exactly one node has been passed.
    drive_to(odom, 5.4, 0.0)
    spin([agent, helper], 0.5)
    assert agent.progress.reached == 3, (
        "the deviation the update set on the node ahead did not bind")
    assert agent.progress.last_node() == ("wp2", 4)


def test_an_extension_is_refused_while_a_cancel_is_pending(rig, monkeypatch):
    """A stop in flight outranks an order asking for more driving.

    The reachable way in: a supervision loss begins a cancel and KEEPS
    the order, so `executing` is false and cancel_pending is set; a
    fresh order is accepted into that (only _resume clears a pending
    cancel, and the accept path is not _resume), which leaves a truck
    executing with an unconfirmed stop still being chased. An extension
    of THAT order is the contradiction the guard names.
    """
    from std_msgs.msg import String
    import vda_agent
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    # The rig has no nav_node, so no cancel here can ever be confirmed;
    # the deadline is moved out of the way rather than raced.
    monkeypatch.setattr(vda_agent, "CANCEL_CONFIRM_S", 60.0)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    send_order(probe, growing_order(2, 0))
    spin([agent, helper], 1.5)
    assert agent.executing

    agent._supervision_lost()
    spin([agent, helper], 0.3)
    assert agent.cancel_pending is not None
    send_order(probe, growing_order(2, 0, order_id="o-mid"))
    spin([agent, helper], 1.5)
    assert agent.executing and agent.order["orderId"] == "o-mid"
    assert agent.cancel_pending is not None, "the stop was already closed"

    routes, goals = len(caught["route"]), len(caught["goal"])
    send_order(probe, growing_order(4, 1, order_id="o-mid"))
    spin([agent, helper], 1.5)
    assert len(caught["route"]) == routes, "an extension drove into a stop"
    assert agent.order["orderUpdateId"] == 0, "the update was taken anyway"
    assert agent.progress.reached == 0 and len(agent.progress.nodes) == 2
    assert agent.cancel_pending is not None, "the extension ate the cancel"
    assert len(caught["goal"]) == goals, "the extension published a stop"
    said = [e for s in states_of(caught, "o-mid") for e in s["errors"]
            if e["errorType"] == "orderError"]
    assert said, "the refusal never reached the fleet"
    assert "cancel is pending" in said[-1]["errorDescription"]
    assert said[-1]["errorReferences"] == [
        {"referenceKey": "orderId", "referenceValue": "o-mid"}]


def test_a_reached_prefix_that_disagrees_is_refused_not_driven(rig):
    """The guard accept_order makes unreachable, fired directly.

    _base_kept already refuses an update whose released prefix differs
    from the order being driven, and Progress.nodes IS that prefix, so
    no message on the wire can reach this branch - the disagreement has
    to be manufactured. It is manufactured in Progress rather than in
    the order because released_route hands back the order's own node
    dicts BY REFERENCE: editing one in place would edit the order too,
    and the door would refuse the update before the guard was asked.
    """
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    odom = odom_publisher(helper)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    send_order(probe, growing_order(2, 0, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    drive_to(odom, 2.0, 0.0)
    spin([agent, helper], 0.5)
    assert agent.progress.reached == 2

    agent.progress.nodes[0] = dict(agent.progress.nodes[0], nodeId="ghost")
    routes = len(caught["route"])
    send_order(probe, growing_order(4, 1, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    assert len(caught["route"]) == routes, "a moved base was driven"
    assert agent.order["orderUpdateId"] == 0, "the moved base was taken"
    assert agent.progress.reached == 2, "the count was touched anyway"
    assert agent.executing, "a refused extension must not stop the truck"
    assert caught["goal"] == []
    said = [e for s in states_of(caught, "o-grow") for e in s["errors"]
            if e["errorType"] == "orderError"]
    assert said and "already passed" in said[-1]["errorDescription"]


# ---- the arrival anchor (M6.5) ----
# M6.4 carried one nav-state period of race in `arrived_now`: it asked
# whether the HORIZON was empty, which says what the fleet has released
# and nothing about what the truck has driven. An arrival is now two
# facts - nav has finished the polyline it was handed, and the truck has
# passed the last released node by its own odometry - and neither of
# them alone ends an order.


def nav_says(nav_pub, state, goal="o-grow", note=""):
    from std_msgs.msg import String
    nav_pub.publish(String(data=json.dumps(
        {"state": state, "goal": goal, "note": note})))


def test_an_extension_that_empties_the_horizon_does_not_arrive_early(rig):
    """THE ONE NAV PERIOD OF RACE, STAGED.

    The truck is standing at the end of a two-node base with three nodes
    of horizon in front of it. The fleet's extension - which releases
    all five and empties the horizon - is processed FIRST, and the
    ARRIVED that belongs to the OLD base is processed after it, inside
    the same nav period. There is nothing exotic about that ordering:
    orders arrive on the MQTT inbox and are drained at 10 Hz, nav's
    state arrives on a ROS subscription, and no rule sequences the two.

    On the horizon-anchored test both conditions then read true and the
    order completed with three nodes and six metres still in front of
    the forks - the fleet would have been told the pallet was delivered
    at wp4 while the truck stood at wp1.
    """
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    odom = odom_publisher(helper)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    send_order(probe, growing_order(2, 0, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    drive_to(odom, 2.0, 0.0)                     # the truck reaches wp1
    spin([agent, helper], 0.5)
    assert agent.progress.reached == 2

    send_order(probe, growing_order(5, 1, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    assert agent.horizon == [], "the extension did not empty the horizon"
    assert agent.progress.reached == 2, "the count moved on an update"

    nav_says(nav_pub, "ARRIVED")                 # ...belonging to wp1
    spin([agent, helper], 1.0)
    assert agent.executing, (
        "the order was completed at wp1 with wp2..wp4 still to drive - "
        "the fleet would have been told the transport was finished")
    assert agent.progress.reached == 2
    last = states_of(caught, "o-grow")[-1]
    assert [n["nodeId"] for n in last["nodeStates"]] == \
        ["wp2", "wp3", "wp4"], "the state claimed there was nothing left"
    assert last["lastNodeId"] == "wp1"

    # ...and the real arrival, when the truck has actually driven the
    # nodes it was given, still closes the order.
    nav_says(nav_pub, "EN-ROUTE")
    spin([agent, helper], 0.5)
    drive_to(odom, 8.0, 0.0)
    spin([agent, helper], 0.5)
    nav_says(nav_pub, "ARRIVED")
    spin([agent, helper], 1.0)
    assert not agent.executing, "the anchor never let the order finish"
    done = [s for s in states_of(caught, "o-grow") if s["nodeStates"] == []]
    assert done and done[-1]["lastNodeId"] == "wp4"


def test_an_update_that_only_shrinks_the_horizon_keeps_the_truck_driveable(
        rig):
    """THE MIRROR, PINNED (M6.4's carry item 5).

    An update that takes nodes OFF the horizon and releases nothing new
    is unreachable through this fleet - order_builder rebuilds the same
    full point list every time and only ever moves the release cut, and
    _base_kept refuses anything that moves the released prefix - so this
    is a property of the agent read alone. The message is therefore
    written by hand. What must not happen is a wedge: the truck stands
    at its base end with nothing in front, and it has to stay executing,
    stay unstopped and still take the next release.
    """
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    odom = odom_publisher(helper)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    send_order(probe, growing_order(2, 0, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    drive_to(odom, 2.0, 0.0)
    spin([agent, helper], 0.5)
    nav_says(nav_pub, "ARRIVED")                 # the base end: a WAIT
    spin([agent, helper], 1.0)
    assert agent.executing
    routes = len(caught["route"])

    # wp3 and wp4 are taken off the horizon; wp0 and wp1 stay released
    # and nothing new is released, so there is nothing to drive to.
    send_order(probe, growing_order(2, 1, {"wp1": 0.25}, count=3))
    spin([agent, helper], 1.5)
    refusals = [e for s in states_of(caught, "o-grow") for e in s["errors"]
                if e["errorType"] == "orderError"]
    assert refusals == [], "the shrink was refused: {}".format(refusals)
    assert agent.executing, "the truck was left believing nothing drives it"
    assert agent.progress.reached == 2, "the count reset on the shrink"
    assert len(caught["route"]) == routes, "there was nothing to drive"
    assert caught["goal"] == [], "a horizon shrink stopped the truck"
    last = states_of(caught, "o-grow")[-1]
    assert [n["nodeId"] for n in last["nodeStates"]] == ["wp2"]
    assert last["newBaseRequest"], "a held truck must still be asking"

    # AND IT IS STILL DRIVEABLE: the next release moves it.
    send_order(probe, growing_order(3, 2, {"wp1": 0.25}, count=3))
    spin([agent, helper], 1.5)
    assert len(caught["route"]) == routes + 1, "the truck was wedged"
    assert caught["route"][-1]["points"] == [[2.0, 0.0], [4.0, 0.0]]


def test_a_horizon_shrunk_to_nothing_still_ends_the_order(rig):
    """The same shape at its limit, and the wedge M6.4 named: an update
    that leaves the truck with everything released and everything
    driven, arriving AFTER nav has already reported ARRIVED at what was
    then a base end.

    Anchored on the horizon and edge-triggered on nav's state, that
    order could never complete: the horizon condition only became true
    after the ARRIVED that would have read it, and nav - which
    republishes its state at 10 Hz and has nothing new to say - never
    gives that edge again. Anchored on the count and asked from both
    callbacks, the next state nav sends settles it.
    """
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    odom = odom_publisher(helper)
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    send_order(probe, growing_order(2, 0, {"wp1": 0.25}))
    spin([agent, helper], 1.5)
    drive_to(odom, 2.0, 0.0)
    spin([agent, helper], 0.5)
    nav_says(nav_pub, "ARRIVED")
    spin([agent, helper], 1.0)
    assert agent.executing, "the base end is a wait, not an arrival"

    send_order(probe, growing_order(2, 1, {"wp1": 0.25}, count=2))
    spin([agent, helper], 1.0)
    assert agent.horizon == []
    nav_says(nav_pub, "ARRIVED")        # nav's next periodic state
    spin([agent, helper], 1.0)
    assert not agent.executing, (
        "the truck is standing on the last node of a fully released "
        "order and the fleet will never be told it arrived")
    done = [s for s in states_of(caught, "o-grow") if s["nodeStates"] == []]
    assert done and done[-1]["lastNodeId"] == "wp1"


def test_nav_blocked_is_reported_as_pathBlocked_once(rig):
    """Item 5c's vehicle half: nav's BLOCKED - the end of the
    escalation, a body it could not get around - reaches the fleet as
    ONE pathBlocked WARNING naming the order. Once, on the edge into
    BLOCKED: the fleet acts on the first report, and a 10 Hz nav state
    repeated into errors[] would bury the screen it is for. The order
    is KEPT - what to do about a blocked route is master control's
    decision, and its cancelOrder arrives through the ordinary door."""
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert agent.executing, "the order was never taken up"
    for _ in range(3):        # a nav state repeated is one report
        nav_pub.publish(String(data=json.dumps(
            {"state": "BLOCKED", "goal": "o-int-1",
             "note": "gave up after 2 nudges - body 1.1 m ahead",
             "route": [], "pose": [3.0, -8.0, 0.0]})))
        spin([agent, helper], 0.4)
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    reports = [s for s in states
               if any(e.get("errorType") == "pathBlocked"
                      for e in s.get("errors", []))]
    assert len(reports) == 1, \
        "expected exactly one pathBlocked report, got {}".format(
            len(reports))
    err = next(e for e in reports[0]["errors"]
               if e["errorType"] == "pathBlocked")
    assert err["errorLevel"] == "WARNING"
    assert any(r.get("referenceKey") == "orderId"
               and r.get("referenceValue") == "o-int-1"
               for r in err["errorReferences"])
    assert "body" in err["errorDescription"]
    # the order is kept and the agent still believes it is executing -
    # the stop already happened in the plant, and the fleet's cancel is
    # what takes the work away
    assert agent.order["orderId"] == "o-int-1"
    assert agent.executing


def order_with_pick():
    msg = valid_order()
    msg["nodes"][-1]["actions"] = [{
        "actionId": "o-int-1:pick", "actionType": "pick",
        "blockingType": "HARD", "actionParameters": []}]
    return msg


def test_the_fork_cycle_runs_at_the_station_and_reports_itself(rig):
    """Item 3, the vehicle half: the pick rides the order as WAITING,
    goes RUNNING on the state that says arrived, and FINISHES on the
    vehicle's own clock - the wire carries the cycle the manager used
    to time blind."""
    from std_msgs.msg import String
    import vda_agent as va
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(order_with_pick()), qos=0)
    spin([agent, helper], 1.5)
    assert agent.executing
    waiting = [a for a in agent.action_states
               if a["actionId"] == "o-int-1:pick"]
    assert waiting and waiting[0]["actionStatus"] == "WAITING"
    # arrival: nav says ARRIVED and odometry has counted every node
    from nav_msgs.msg import Odometry
    odom = helper.create_publisher(
        Odometry, agent_topics(agent), 10)
    msg = Odometry()
    msg.pose.pose.position.x, msg.pose.pose.position.y = 6.0, -8.0
    for _ in range(3):
        odom.publish(msg)
        spin([agent, helper], 0.3)
    nav_pub.publish(String(data=json.dumps(
        {"state": "ARRIVED", "goal": "o-int-1", "note": "",
         "route": [], "pose": [6.0, -8.0, 0.0]})))
    spin([agent, helper], 1.0)
    assert not agent.executing, "arrival never settled"
    running = [s for t, s in caught["mqtt"] if t.endswith("/state")
               and any(a.get("actionId") == "o-int-1:pick"
                       and a.get("actionStatus") == "RUNNING"
                       for a in s.get("actionStates", []))]
    assert running, "the cycle never reported RUNNING"
    spin([agent, helper], va.FORK_CYCLE_S + 1.0)
    finished = [a for a in agent.action_states
                if a["actionId"] == "o-int-1:pick"]
    assert finished[0]["actionStatus"] == "FINISHED"
    states = [s for t, s in caught["mqtt"] if t.endswith("/state")]
    assert any(any(a.get("actionId") == "o-int-1:pick"
                   and a.get("actionStatus") == "FINISHED"
                   for a in s.get("actionStates", []))
               for s in states), "FINISHED never reached the wire"


def agent_topics(agent):
    """The odom topic the agent subscribed - read from its config, so
    the test cannot drift from the wiring."""
    import yaml
    from status_contract import CONFIG_PATH
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["topics"]["gz_odom"]


def test_a_cancel_fails_the_cycle_it_interrupts(rig):
    """spec 6.6.3.2: cancelOrder cancels the actions with the order. A
    WAITING pick must go FAILED, not linger as a promise."""
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(order_with_pick()), qos=0)
    spin([agent, helper], 1.5)
    assert agent.executing
    probe.publish("uagv/v2/amragent/f1/instantActions", json.dumps(
        {"actions": [{"actionId": "cx", "actionType": "cancelOrder",
                      "blockingType": "HARD"}]}), qos=0)
    spin([agent, helper], 1.0)
    pick = next(a for a in agent.action_states
                if a["actionId"] == "o-int-1:pick")
    assert pick["actionStatus"] == "FAILED"
