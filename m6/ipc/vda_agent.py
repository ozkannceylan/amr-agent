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

A CANCEL IS A CONVERSATION, NOT A SHOUT (M6.3 Fleet Gate 4, measured
2026-08-22). Every stop this node performs goes through the empty goal
on /auto/goal, and a single publish of it is not a stop - it is a
request that may reach nobody. It did: a respawned agent published the
empty goal 1.1 s after creating the publisher, before DDS had matched
nav_node's subscription; the message was dropped, the cancelOrder
actionState still said FINISHED, and the truck drove another 37.09 s
and 6.743 m along a route the fleet had already handed to another
vehicle. So the empty goal is now REPUBLISHED every drain until cb_nav
shows nav is no longer driving our route, the actionState stays RUNNING
until that is seen, and a cancel that is never confirmed goes FAILED
with an errors[] entry rather than quietly claiming a stop nobody
watched. _begin_cancel / _pump_cancel own that loop and both the
cancelOrder action and the supervision-loss stop go through it.

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

THE AGENT BELIEVES NAV, NOT ITSELF. Publishing a route is a request,
not an outcome: nav_core refuses one it cannot drive (not in auto,
malformed, no pose yet) and cancels one already running when the mode
leaves auto, and it says so in /auto/state's `note` while the agent,
believing its own publish, would go on reporting a truck that drives.
cb_nav therefore reconciles - a nav that has gone IDLE with a refusal
or cancel note and no goal ends `executing`, loudly, on the state.

  THE ORDER SURVIVES THAT. Only `executing` is cleared; order and
  Progress stay, so the recovery path is: mode returns to AUTOMATIC ->
  a cancelOrder clears it, or the next broker bounce reconnects and
  _resume re-issues the remaining released nodes from the current pose
  (it fires only when not executing, which is now true). _resume checks
  AUTOMATIC itself before it publishes, so supervision returning during
  a teleop shift holds the order instead of asking for a drive nav
  would only refuse again.
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
# HOW LONG A FRESHLY PUBLISHED ROUTE IS GIVEN BEFORE cb_nav IS ALLOWED
# TO CALL IT REFUSED. nav_node publishes /auto/state at 10 Hz
# (TICK_HZ 20, STATE_EVERY 2), so a state message already in flight
# when the route goes out is at most 0.1 s old and still describes the
# world BEFORE the route - three periods of margin.
#
# WITHOUT THIS THE RECONCILER EATS ITS OWN RECOVERY, and the sequence
# is ordinary, not exotic: cancelOrder (or a supervision loss) publishes
# the empty goal, nav answers _cancel("cancelled") - IDLE, goal None,
# note "cancelled" - and every state it sends afterwards repeats that
# note. Publish the next route and the in-flight one arrives looking
# exactly like a refusal of the route that has not been read yet, so
# the agent would stop believing a truck that is about to drive and
# strand the order (ARRIVED is only read while executing).
NAV_SETTLE_S = 0.3
# HOW LONG A CANCEL KEEPS ASKING BEFORE IT ADMITS IT DID NOT SEE A STOP.
# The empty goal goes out at DRAIN_HZ, so this is fifty attempts - far
# past any DDS discovery window (Fleet Gate 4's miss was one publish
# inside ~1 s of node startup) and still short enough that an operator
# reading a FAILED actionState is reading about a truck that is
# probably still moving NOW, not one that stopped a minute ago.
CANCEL_CONFIRM_S = 5.0
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
        self.cancel_pending = None   # the closed-loop cancel, or None
        self.last_state_pub = 0.0
        self.route_sent_at = 0.0     # NAV_SETTLE_S is measured from here

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
        # PAHO'S DEFAULT BACKOFF IS UNBOUNDED IN PRACTICE - it doubles
        # from 1 s to 120 s, and M6.2 Gate 4 (VDA 4) measured what that
        # costs: 28.1 s of silence between a broker returning and this
        # vehicle noticing. A truck standing still with an order kept is
        # waiting on this timer, so it is capped where an operator can
        # wait: retries every 1-8 s, forever.
        self.mq.reconnect_delay_set(min_delay=1, max_delay=8)
        self.mq.connect_async(MQTT_HOST, MQTT_PORT)
        self.mq.loop_start()

    # ---- paho thread: enqueue only ----
    def _on_connect(self, client, userdata, flags, reason_code,
                    properties=None):
        self.inbox.put(("connected", None))

    def _on_disconnect(self, client, userdata, flags, reason_code,
                       properties=None):
        if _failed(reason_code):
            # NOTHING IS SAID FROM HERE - this thread enqueues, full
            # stop. paho is already retrying on its own thread inside
            # 1-8 s (reconnect_delay_set above); the drain reports that
            # cadence about 0.1 s later, from the ROS thread, where the
            # rest of this node speaks.
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
        # A report that is not an object is a report this node cannot
        # read, and any_pf_false would answer False for it - "no
        # violation", from a shape nobody understood. Same rule as the
        # unreadable packet above it: not knowing reads as violated.
        try:
            report = json.loads(msg.data)
        except ValueError:
            self.pf_violated = True
            return
        self.pf_violated = (vm.any_pf_false(report)
                            if isinstance(report, dict) else True)

    def cb_nav(self, msg):
        try:
            nav = json.loads(msg.data)
        except ValueError:
            return
        if not isinstance(nav, dict):
            return
        state, goal = nav.get("state", ""), nav.get("goal", "")
        note = nav.get("note", "")
        arrived_now = (state == "ARRIVED" and self.nav_state != "ARRIVED"
                       and self.executing
                       and goal == self.order["orderId"])
        # NAV STOPPED AND IT WAS NOT AN ARRIVAL. IDLE with a note is
        # nav_core saying it refused the route or cancelled the drive;
        # a route it accepted would have made `goal` our orderId, so an
        # empty goal beside that note means nothing of ours is running.
        # "mode left auto" is admitted by name because it is the one
        # note that matters most and the one an operator will see.
        refused_now = (
            self.executing and state == "IDLE" and note
            and (goal in ("", None) or note == "mode left auto")
            and time.monotonic() - self.route_sent_at >= NAV_SETTLE_S)
        self.nav_state, self.nav_goal = state, goal
        if arrived_now:
            self.progress.complete()
            self.executing = False
            self.publish_state("arrived")
        elif refused_now:
            # The order is KEPT - only the belief that it is being
            # driven goes. See the module docstring's recovery path.
            self.executing = False
            self.get_logger().warn(
                "nav is not driving this order: {}".format(note))
            self.publish_state("nav refused/cancelled")

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
        # AFTER the inbox and BEFORE the periodic state: a cancel that
        # confirms on this pass should say so on this pass's state.
        self._pump_cancel()
        if time.monotonic() - self.last_state_pub >= STATE_PERIOD_S:
            self.publish_state("periodic")

    def _announce(self):
        self.mq.subscribe([(vm.topic(VID, "order"), 0),
                           (vm.topic(VID, "instantActions"), 0)])
        self.mq.publish(vm.topic(VID, "connection"), json.dumps(
            vm.connection_payload(
                self.counters.header("connection", VID), "ONLINE")),
            qos=1, retain=True)
        self.get_logger().info("broker connected - ONLINE published")
        self.publish_factsheet()
        if self.order is not None and not self.executing \
                and self.progress.reached < len(self.progress.nodes):
            self._resume()
        self.publish_state("connected")

    def _supervision_lost(self):
        self.get_logger().warn(
            "broker lost - controlled stop, order kept - paho retrying "
            "inside 1-8 s")
        if self.executing:
            # THE SAME CLOSED LOOP AS A cancelOrder, minus the
            # actionStates: nobody asked for this stop, so there is
            # nothing to report FINISHED - but it still has to be SEEN,
            # and this is the path that runs with the broker already
            # gone, where nothing downstream would ever notice a goal
            # that missed.
            self._begin_cancel(why="broker lost")

    def _resume(self):
        """Re-issue the remaining released nodes from the pose we are at.

        THE MODE IS CHECKED HERE AND NOWHERE ELSE ON THIS PATH. The
        accept branch gets its AUTOMATIC guarantee from accept_order,
        but nothing re-asks it on the way back from a broker bounce -
        and a shift that went to teleop while the link was down would
        have this method request a drive nav_core can only refuse. The
        order is HELD, not dropped: the truck is standing still, the
        released nodes are still the work, and the next reconnect in
        AUTOMATIC issues them.
        """
        if self.operating_mode() != "AUTOMATIC":
            self.get_logger().warn(
                "supervision back but not in AUTOMATIC - order held, "
                "not driving")
            return
        remaining = self.progress.nodes[self.progress.reached:]
        points = [list(self.pose[:2])] + [
            [n["nodePosition"]["x"], n["nodePosition"]["y"]]
            for n in remaining]
        _, arrive_m, _, _ = vo.released_route(self.order)
        self.pub_route.publish(String(data=json.dumps(
            {"points": points, "arrive_m": arrive_m,
             "label": self.order["orderId"]})))
        self.route_sent_at = time.monotonic()
        self.executing = True
        if self.cancel_pending is not None:
            # The agent has just deliberately re-asked for this drive,
            # so the stop it was chasing is moot. Dropping the entry
            # here is what keeps _pump_cancel from cancelling the route
            # this method published one line ago.
            self.get_logger().info(
                "resume supersedes the cancel that was still pending")
            self.cancel_pending = None
        self.get_logger().info("supervision back - route re-issued")

    def operating_mode(self):
        return "AUTOMATIC" if self.mode == MODE_AUTO else "MANUAL"

    def _on_order(self, payload):
        try:
            msg = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError):
            self.get_logger().warn("unreadable order dropped")
            return
        # The whole current order goes in, not just its ids: an update
        # is judged against the nodes the truck was already told to
        # drive (vda_orders s.6.6 stitching).
        verdict, reason = vo.accept_order(
            msg, self.order, self.executing, self.operating_mode())
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
        # An 'extend' verdict falls in here with the accepts for now: the
        # base it carries is legal by rule, so re-issuing it from the
        # pose the truck stands at drives the right floor - it just
        # restarts the progress count. Carrying Progress across a stitch
        # is the next change in this file.
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
        self.route_sent_at = time.monotonic()
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
                # THE ORDER IS DROPPED HERE AND THE STOP IS CHASED IN
                # _pump_cancel. Ownership of the work ends the moment
                # the fleet asks - there is no version of this where the
                # agent keeps driving an order it was told to cancel -
                # but the actionState stays RUNNING until nav says it
                # stopped, because FINISHED is a claim about the truck
                # and not about this process. _begin_cancel reads
                # self.order for the id it is cancelling, so it goes
                # first.
                self._begin_cancel(action_id=aid)
                self.order, self.progress = None, None
                self.horizon = []
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

    # ---- the closed-loop cancel ----
    def _begin_cancel(self, action_id=None, why=""):
        """Start asking nav to stop, and keep asking until it says it has.

        The first publish happens HERE rather than on the next drain, so
        a cancel that nav is already listening for costs nothing extra;
        everything after it is _pump_cancel's.
        """
        now = time.monotonic()
        self.cancel_pending = {
            "action_id": action_id,
            "order_id": ((self.order or {}).get("orderId")
                         or self.nav_goal or ""),
            "began": now,
            "deadline": now + CANCEL_CONFIRM_S,
            "sent": 0,
            "why": why}
        if action_id is not None:
            self._set_action(action_id, "cancelOrder", "RUNNING")
        self.executing = False
        self._pump_cancel()

    def _cancel_confirmed(self):
        """True only when nav has SAID it is not driving our route.

        SILENCE IS NOT CONFIRMATION, and that is the whole lesson of
        Fleet Gate 4: a just-restarted agent has heard no /auto/state at
        all, and reading that emptiness as a stop is exactly the lie the
        gate caught. So nav_state has to be something nav actually
        published. nav_core._cancel sets IDLE with goal None from ANY
        state including ARRIVED, so IDLE with no goal is the plain
        answer; a goal that is no longer ours covers the case where the
        truck has since been given other work and this cancel is moot.
        """
        if not self.nav_state:
            return False
        if self.nav_state == "IDLE" and not self.nav_goal:
            return True
        target = self.cancel_pending["order_id"]
        return bool(target) and self.nav_goal != target

    def _pump_cancel(self):
        """One pass of a pending cancel: confirm it, give up, or ask again."""
        pending = self.cancel_pending
        if pending is None:
            return
        now = time.monotonic()
        if self._cancel_confirmed():
            self.cancel_pending = None
            if pending["action_id"] is not None:
                self._set_action(pending["action_id"], "cancelOrder",
                                 "FINISHED")
            self.get_logger().info(
                "cancel confirmed by nav after {} publish(es), {:.2f} s"
                .format(pending["sent"], now - pending["began"]))
            self.publish_state("cancel confirmed")
            return
        if now >= pending["deadline"]:
            self.cancel_pending = None
            if pending["action_id"] is not None:
                self._set_action(pending["action_id"], "cancelOrder",
                                 "FAILED")
            self.get_logger().error(
                "cancel NOT confirmed in {:.1f} s and {} publishes - nav "
                "never reported it stopped driving {!r}. Assume this "
                "truck is STILL MOVING.".format(
                    CANCEL_CONFIRM_S, pending["sent"],
                    pending["order_id"] or "its route"))
            self.publish_state("cancel unconfirmed", [{
                "errorType": "cancelUnconfirmed",
                "errorLevel": "WARNING",
                "errorDescription":
                    "the empty goal went out {} times over {:.1f} s and "
                    "nav never reported a stop - this vehicle may still "
                    "be driving".format(pending["sent"], CANCEL_CONFIRM_S),
                "errorReferences": [
                    {"referenceKey": "orderId",
                     "referenceValue": pending["order_id"] or ""}]}])
            return
        if self.executing:
            # A ROUTE IS RUNNING AGAIN - _resume or a fresh order has
            # deliberately re-asked for a drive, and an empty goal
            # published now would cancel THAT. The entry stays; the
            # confirmation above reads nav's own goal and answers on a
            # later pass.
            return
        if pending["sent"] == 0 \
                and self.pub_goal.get_subscription_count() == 0:
            # The retry loop below already covers this; the line exists
            # for whoever reads the log next, because Fleet Gate 4 spent
            # 37.09 s and 6.743 m inside exactly this window with
            # nothing in any log to say so.
            self.get_logger().warn(
                "nav has not matched {} yet - this empty goal reaches "
                "nobody; retrying at {:.0f} Hz until nav says it stopped"
                .format(AUTO_GOAL_TOPIC, DRAIN_HZ))
        self.pub_goal.publish(String(data=""))
        pending["sent"] += 1

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
