"""vda_agent.py - the vehicle's VDA 5050 client. Wiring only.

Decisions live in vda_orders.py / vda_messages.py (pure); this file
moves bytes: paho-mqtt on one side, rclpy on the other. The paho
network thread only ENQUEUES; a 10 Hz rclpy timer drains the queue and
does all work in the ROS thread, so no lock guards any state.

SAFETY: this channel is reporting and process command only (M1
invariant). safetyState narrates what the F-model already did; a lost
broker is degraded mode -> controlled stop through the NORMAL chain
(the empty goal), never a safety path. If this agent dies the truck
keeps driving its current route - the panel and the chain own stopping.

Supervision loss (M1 s.7): on disconnect publish the empty goal, KEEP
the order; on reconnect re-issue the remaining released nodes as a
fresh route from the current pose.

PAHO 2.x IS WHAT IS INSTALLED (2.1.0, measured). The client is built
with an explicit CallbackAPIVersion.VERSION2 and the callbacks carry
that API's signatures - `reason_code` objects rather than an int `rc`.
Naming the version is not optional: paho 2.x defaults to VERSION1 with
a DeprecationWarning and would then hand these methods the wrong
argument count at the worst possible moment, on a reconnect.

ONE Counters PER PROCESS, and that is the whole rule: headerId is a
per-topic counter and Counters keys on the topic NAME alone, which is
correct here because THIS PROCESS IS ONE VEHICLE. status_contract binds
VID once at import from env VEHICLE; a second vehicle is a second
process with its own counters. Sharing one instance across vehicles
would merge two vehicles' headerId sequences into one - do not.
"""
import json
import math
import os
import queue
import time

import rclpy
import yaml
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String

import paho.mqtt.client as mqtt

import vda_messages as vm
import vda_orders as vo
from status_contract import (
    AUTO_GOAL_TOPIC, AUTO_ROUTE_TOPIC, AUTO_STATE_TOPIC, CONFIG_PATH,
    FIELDS_TOPIC, MODE_TOPIC, STATUS_TOPIC, VID, MODE_AUTO,
    STATUS_STALE_S, is_stale, parse_status)

# ----------------------------- CONFIG -----------------------------
MQTT_HOST = "127.0.0.1"
MQTT_PORT = int(os.environ.get("VDA_MQTT_PORT", "1883"))
DRAIN_HZ = 10.0
STATE_PERIOD_S = 2.0
DRIVING_MPS = 0.02
# ------------------------------------------------------------------


def _failed(reason_code):
    """True when paho reports an UNEXPECTED end of the connection.

    VERSION2 hands a ReasonCode object, which knows the answer itself;
    the int fallback keeps this readable if the callback API ever hands
    a bare code again. A clean disconnect() is code 0 and not a loss.
    """
    return bool(getattr(reason_code, "is_failure", bool(reason_code)))


class VdaAgent(Node):

    def __init__(self):
        super().__init__("vda_agent")
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            topics = yaml.safe_load(handle)["topics"]
        self.counters = vm.Counters()    # one per process = one vehicle
        self.inbox = queue.Queue()
        # vehicle-side truth
        self.pose = (0.0, 0.0, 0.0)
        self.speed = 0.0
        self.mode = None
        self.motor = False
        self.estop_healthy = False
        self.status_rx = None
        self.pf_violated = True     # unknown reads as violated
        self.nav_state = ""
        self.nav_goal = ""
        # order context
        self.order = None            # the accepted order message
        self.progress = None
        self.horizon = []
        self.executing = False
        self.action_states = []
        self.last_state_pub = 0.0

        self.pub_route = self.create_publisher(String, AUTO_ROUTE_TOPIC, 10)
        self.pub_goal = self.create_publisher(String, AUTO_GOAL_TOPIC, 10)
        latched = QoSProfile(
            depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, MODE_TOPIC, self.cb_mode, latched)
        self.create_subscription(String, STATUS_TOPIC, self.cb_status, 10)
        self.create_subscription(String, FIELDS_TOPIC, self.cb_fields, 10)
        self.create_subscription(String, AUTO_STATE_TOPIC, self.cb_nav, 10)
        self.create_subscription(
            Odometry, topics["gz_odom"], self.cb_odom, 10)
        self.create_timer(1.0 / DRAIN_HZ, self.drain)

        self.mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                              client_id="vda-{}".format(VID))
        self.mq.will_set(vm.topic(VID, "connection"), json.dumps(
            vm.connection_payload(
                self.counters.header("connection", VID),
                "CONNECTIONBROKEN")), qos=1, retain=True)
        self.mq.on_connect = self._on_connect
        self.mq.on_disconnect = self._on_disconnect
        self.mq.on_message = self._on_message
        self.mq.connect_async(MQTT_HOST, MQTT_PORT)
        self.mq.loop_start()

    # ---- paho thread: enqueue only ----
    def _on_connect(self, client, userdata, flags, reason_code,
                    properties=None):
        self.inbox.put(("connected", None))

    def _on_disconnect(self, client, userdata, flags, reason_code,
                       properties=None):
        if _failed(reason_code):
            self.inbox.put(("lost", None))

    def _on_message(self, client, userdata, msg):
        self.inbox.put((msg.topic, msg.payload))

    # ---- ROS thread: everything else ----
    def cb_mode(self, msg):
        self.mode = msg.data
        self.publish_state("mode change")

    def cb_status(self, msg):
        state = parse_status(msg.data.encode())
        self.status_rx = time.monotonic()
        motor = bool(state["motor"]) if state else False
        healthy = bool(state["estop_healthy"]) if state else False
        changed = (motor, healthy) != (self.motor, self.estop_healthy)
        self.motor, self.estop_healthy = motor, healthy
        if changed:
            self.publish_state("safety change")

    def cb_fields(self, msg):
        try:
            self.pf_violated = vm.any_pf_false(json.loads(msg.data))
        except ValueError:
            self.pf_violated = True

    def cb_nav(self, msg):
        try:
            nav = json.loads(msg.data)
        except ValueError:
            return
        if not isinstance(nav, dict):
            return
        state, goal = nav.get("state", ""), nav.get("goal", "")
        arrived_now = (state == "ARRIVED" and self.nav_state != "ARRIVED"
                       and self.executing
                       and goal == self.order["orderId"])
        self.nav_state, self.nav_goal = state, goal
        if arrived_now:
            self.progress.complete()
            self.executing = False
            self.publish_state("arrived")

    def cb_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        self.pose = (p.x, p.y, 2.0 * math.atan2(q.z, q.w))
        v = msg.twist.twist.linear
        self.speed = math.hypot(v.x, v.y)
        if self.executing and self.progress.update(self.pose[:2]):
            self.publish_state("node reached")

    def drain(self):
        while True:
            try:
                kind, payload = self.inbox.get_nowait()
            except queue.Empty:
                break
            if kind == "connected":
                self._announce()
            elif kind == "lost":
                self._supervision_lost()
            elif kind.endswith("/order"):
                self._on_order(payload)
            elif kind.endswith("/instantActions"):
                self._on_actions(payload)
        if time.monotonic() - self.last_state_pub >= STATE_PERIOD_S:
            self.publish_state("periodic")

    def _announce(self):
        self.mq.subscribe([(vm.topic(VID, "order"), 0),
                           (vm.topic(VID, "instantActions"), 0)])
        self.mq.publish(vm.topic(VID, "connection"), json.dumps(
            vm.connection_payload(
                self.counters.header("connection", VID), "ONLINE")),
            qos=1, retain=True)
        self.publish_factsheet()
        if self.order is not None and not self.executing \
                and self.progress.reached < len(self.progress.nodes):
            self._resume()
        self.publish_state("connected")

    def _supervision_lost(self):
        self.get_logger().warn("broker lost - controlled stop, order kept")
        if self.executing:
            self.pub_goal.publish(String(data=""))
            self.executing = False

    def _resume(self):
        remaining = self.progress.nodes[self.progress.reached:]
        points = [list(self.pose[:2])] + [
            [n["nodePosition"]["x"], n["nodePosition"]["y"]]
            for n in remaining]
        _, arrive_m, _, _ = vo.released_route(self.order)
        self.pub_route.publish(String(data=json.dumps(
            {"points": points, "arrive_m": arrive_m,
             "label": self.order["orderId"]})))
        self.executing = True
        self.get_logger().info("supervision back - route re-issued")

    def operating_mode(self):
        return "AUTOMATIC" if self.mode == MODE_AUTO else "MANUAL"

    def _on_order(self, payload):
        try:
            msg = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError):
            self.get_logger().warn("unreadable order dropped")
            return
        verdict, reason = vo.accept_order(
            msg, self.order["orderId"] if self.order else "",
            self.order["orderUpdateId"] if self.order else 0,
            self.executing, self.operating_mode())
        if verdict == "ignore":
            return
        if verdict == "reject":
            # NOT msg["orderId"]: 'not an object' is a valid rejection
            # reason, and a list has no .get to answer it with.
            oid = msg.get("orderId", "?") if isinstance(msg, dict) else "?"
            self.get_logger().warn("order rejected: {}".format(reason))
            self.publish_state("order rejected", [{
                "errorType": "orderError", "errorLevel": "WARNING",
                "errorDescription": reason,
                "errorReferences": [{"referenceKey": "orderId",
                                     "referenceValue": str(oid)}]}])
            return
        points, arrive_m, released, horizon = vo.released_route(msg)
        raw_dev = released[-1]["nodePosition"].get("allowedDeviationXY")
        if raw_dev is not None and raw_dev != arrive_m:
            self.get_logger().info(
                "allowedDeviationXY {!r} is not a radius nav can drive - "
                "arriving on {} m instead".format(raw_dev, arrive_m))
        self.order, self.horizon = msg, horizon
        self.progress = vo.Progress(released)
        route = [list(self.pose[:2])] + [list(p) for p in points]
        self.pub_route.publish(String(data=json.dumps(
            {"points": route, "arrive_m": arrive_m,
             "label": msg["orderId"]})))
        self.executing = True
        self.publish_state("order accepted")

    def _on_actions(self, payload):
        try:
            body = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError):
            return
        actions = body.get("actions", []) if isinstance(body, dict) else []
        extras = []
        for act in actions if isinstance(actions, list) else []:
            if not isinstance(act, dict):
                continue
            aid = str(act.get("actionId", "?"))
            kind = act.get("actionType", "")
            if kind == "cancelOrder":
                self.pub_goal.publish(String(data=""))
                self.order, self.progress = None, None
                self.horizon, self.executing = [], False
                self._set_action(aid, kind, "FINISHED")
            elif kind == "stateRequest":
                self._set_action(aid, kind, "FINISHED")
            elif kind == "factsheetRequest":
                self.publish_factsheet()
                self._set_action(aid, kind, "FINISHED")
            else:
                # A FAILED actionState says the action did not run; it
                # does not say WHY, and errors[] is where a fleet
                # manager looks for that. Reported once, on the state
                # this handling produces - the FAILED actionState is
                # the standing record afterwards.
                self._set_action(aid, kind, "FAILED")
                extras.append({
                    "errorType": "unsupportedAction",
                    "errorLevel": "WARNING",
                    "errorDescription":
                        "actionType {!r} is not implemented - the "
                        "factsheet declares what is".format(kind),
                    "errorReferences": [
                        {"referenceKey": "actionId",
                         "referenceValue": aid}]})
        self.publish_state("actions handled", extras)

    def _set_action(self, aid, kind, status):
        self.action_states = [a for a in self.action_states
                              if a["actionId"] != aid]
        self.action_states.append({"actionId": aid, "actionType": kind,
                                   "actionStatus": status})

    def order_ctx(self):
        if self.order is None:
            return {}
        last_id, last_seq = self.progress.last_node()
        remaining = self.progress.nodes[self.progress.reached:]
        node_states = [{"nodeId": n["nodeId"],
                        "sequenceId": n["sequenceId"], "released": True}
                       for n in remaining]
        node_states += [{"nodeId": n["nodeId"],
                         "sequenceId": n["sequenceId"], "released": False}
                        for n in self.horizon]
        return {"orderId": self.order["orderId"],
                "orderUpdateId": self.order["orderUpdateId"],
                "lastNodeId": last_id, "lastNodeSequenceId": last_seq,
                "nodeStates": node_states,
                "edgeStates": [],
                "newBaseRequest": bool(self.horizon) and not remaining}

    def publish_state(self, why, extra_errors=()):
        """Build one state and send it. `why` is the trigger, logged at
        debug so a state stream can be read back against its causes.

        EVERY LIST HANDED TO build_state IS A COPY. build_state stores
        what it is given, so a state dict holding self.action_states
        would keep changing after it was published - and json.dumps
        below is not the only reader of it.
        """
        now = time.monotonic()
        motor = self.motor and not is_stale(
            self.status_rx, now, STATUS_STALE_S)
        errors, safety = vm.errors_and_safety(
            motor, self.estop_healthy, self.pf_violated)
        state = vm.build_state(
            self.counters.header("state", VID), self.order_ctx(),
            self.pose, self.speed > DRIVING_MPS, self.operating_mode(),
            list(errors) + list(extra_errors), safety,
            list(self.action_states))
        self.mq.publish(vm.topic(VID, "state"), json.dumps(state), qos=0)
        self.last_state_pub = now
        self.get_logger().debug("state published: {}".format(why))

    def publish_factsheet(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle)
        self.mq.publish(vm.topic(VID, "factsheet"), json.dumps(
            vm.build_factsheet(
                self.counters.header("factsheet", VID), cfg)),
            qos=0, retain=True)

    def close(self):
        """Say OFFLINE and let go of the broker.

        One teardown, called by main()'s finally AND by the integration
        test's fixture. The test needs it for a reason worth naming: a
        paho loop thread left running reconnects, and a second client
        carrying the same client_id kicks the first off the broker - so
        a leaked agent from an earlier test evicts the next test's.
        """
        try:
            self.mq.publish(vm.topic(VID, "connection"), json.dumps(
                vm.connection_payload(
                    self.counters.header("connection", VID), "OFFLINE")),
                qos=1, retain=True).wait_for_publish(timeout=2.0)
        except Exception:
            pass
        try:
            self.mq.disconnect()
        except Exception:
            pass
        self.mq.loop_stop()


def main():
    rclpy.init()
    node = VdaAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
