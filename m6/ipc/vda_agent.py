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

AN ARRIVAL IS TWO FACTS ON TWO TOPICS (M6.5). nav finishing the
polyline it was handed says nothing about the ORDER - it was given the
released nodes and only those - and the horizon being empty says what
the FLEET has released, not what the truck has driven. So the order ends
only when nav says ARRIVED for it AND `progress.reached` has counted
every released node, and _settle_arrival is asked from both cb_nav and
cb_odom because either topic may carry the fact that lands second. M6.4
anchored it on the horizon alone and carried one nav period of race for
it; that window is closed here.

AN EXTENSION IS NOT A NEW ORDER (VDA 5050 s.6.6, M6.4). An update that
only grows the base past what the truck has already been told to drive
is stitched on: the order message is replaced, Progress keeps its count
because the released prefix is unchanged BY RULE, and only the nodes
still in front of the truck go to nav as a fresh route from the pose it
stands at. Nothing stops, nothing is cancelled, `executing` never
flickers - a stitch the truck can feel is a stitch done wrong.

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

import yaml
import paho.mqtt.client as mqtt

import vda_messages as vm
import vda_orders as vo
from ros_optional import DurabilityPolicy, Node, Odometry, QoSProfile, String, rclpy, require
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
# THE FORK CYCLE, VEHICLE-SIDE (item 3). The owner's 2026-08-21 ruling
# put a dwell between a transport's two legs to stand in for the fork
# cycle; until this round the MANAGER timed it, which meant the wire
# never carried the pick and the fleet was guessing at its own trucks.
# The cycle now runs here, as the node action the order carries -
# RUNNING at arrival, FINISHED when it is done - and the manager gates
# leg 2 on the report instead of its own clock. The 3.0 s is the same
# ruling's number. THE MAST DOES NOT MOVE YET: the cycle is timed, not
# actuated - wiring the fork command through the gate is its own work
# and this constant is where it will land.
FORK_CYCLE_S = 3.0
# ------------------------------------------------------------------


def _failed(reason_code):
    """True when paho reports an UNEXPECTED end of the connection.

    VERSION2 hands a ReasonCode object, which knows the answer itself;
    the int fallback keeps this readable if the callback API ever hands
    a bare code again. A clean disconnect() is code 0 and not a loss.
    """
    return bool(getattr(reason_code, "is_failure", bool(reason_code)))


def _xy(nodes):
    """The (x, y) pairs of a list of order nodes, in travel order."""
    return [[n["nodePosition"]["x"], n["nodePosition"]["y"]] for n in nodes]


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
        self.node_action = None      # the running fork cycle, or None
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
        # AN ARRIVAL IS TWO FACTS AND THEY LAND ON TWO TOPICS, so it is
        # settled in one place (_settle_arrival) that both this callback
        # and cb_odom ask.
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
        # NAV GAVE UP ON A BODY (M6 item 5c, PROOF residual 11). BLOCKED
        # is the end of the escalation - HOLD, AVOID and NUDGE have all
        # been tried - and it is the one fact only this vehicle knows:
        # the scanners stopped the truck long ago, but nothing on the
        # wire ever said WHERE. Edge-triggered on the transition into
        # BLOCKED for our own order, reported once as a pathBlocked
        # WARNING; the fleet reads it, closes the node ahead and takes
        # the order back. The order is KEPT here - what to do about a
        # blocked route is master control's decision, not this file's.
        blocked_now = (
            self.executing and state == "BLOCKED"
            and self.nav_state != "BLOCKED"
            and goal == (self.order or {}).get("orderId"))
        self.nav_state, self.nav_goal = state, goal
        if self._settle_arrival():
            return
        if refused_now:
            # The order is KEPT - only the belief that it is being
            # driven goes. See the module docstring's recovery path.
            self.executing = False
            self.get_logger().warn(
                "nav is not driving this order: {}".format(note))
            self.publish_state("nav refused/cancelled")
            return
        if blocked_now:
            self.get_logger().warn(
                "nav is BLOCKED on this order: {}".format(note))
            self.publish_state("path blocked", [{
                "errorType": "pathBlocked", "errorLevel": "WARNING",
                "errorDescription":
                    "navigation gave up on a body in the path - {}"
                    .format(note or "no detail"),
                "errorReferences": [
                    {"referenceKey": "orderId",
                     "referenceValue": self.order["orderId"]}]}])

    def _settle_arrival(self):
        """The order is over. True when THIS call is what ended it.

        TWO FACTS, AND NEITHER ALONE IS AN ARRIVAL.

        * nav has finished the polyline it was handed, for this order.
          It cannot mean more than that: it was given the RELEASED nodes
          and nothing else, so its ARRIVED at the end of a held base is
          a WAIT - the traffic primitive - and not a completion.
          MEASURED 2026-08-22, M6.4 Gate 1, live: read as a completion,
          the agent cleared `executing` at its base end and every one of
          the 1,873 extensions the fleet published over the next 3 m
          37 s came back "no order is executing - nothing to extend";
          the truck stood three metres short of a corridor that had been
          free for two minutes and its transport never completed.
        * the truck has passed the last node the fleet released, by its
          own odometry - `progress.reached == len(progress.nodes)`.

        THE SECOND FACT IS THE M6.5 FIX and the first is not a
        pre-filter for it: they are independent. An empty horizon says
        the FLEET has released everything; a full count says the TRUCK
        has driven everything released. M6.4 carried one nav period of
        race between them - an extension that empties the horizon can be
        processed in the same period the truck reaches the end of the
        base it is still driving, and the ARRIVED that belongs to the
        OLD base would then complete the order with three nodes still in
        front of the forks. Asking both closes it.

        AND IT IS ASKED FROM BOTH CALLBACKS RATHER THAN ON THE EDGE OF
        nav's state. The two facts arrive on two topics with no ordering
        between them, so whichever lands second has to be the one that
        settles it; an edge test on nav alone would drop the arrival
        whenever the odom sample that completes the count was processed
        after nav's ARRIVED. `executing` is the once-only guard - it is
        false the moment this fires, and only a new route sets it again.
        """
        if not self.executing or self.order is None \
                or self.progress is None or self.horizon:
            return False
        if self.nav_state != "ARRIVED" \
                or self.nav_goal != self.order["orderId"]:
            return False
        if self.progress.reached != len(self.progress.nodes):
            return False
        self.executing = False
        # THE STATION ACTION STARTS WHERE ARRIVAL IS DECIDED (item 3).
        # validate_order admits an action on the final node only, so
        # this is the one place it can come due; the same state that
        # says "arrived" says the cycle is RUNNING, and drain() reports
        # FINISHED when the clock the plant does not have yet runs out.
        acts = self.order["nodes"][-1].get("actions") or []
        if acts:
            act = acts[0]
            self._set_action(act["actionId"], act["actionType"], "RUNNING")
            self.node_action = {
                "id": act["actionId"], "type": act["actionType"],
                "until": time.monotonic() + FORK_CYCLE_S}
            self.get_logger().info(
                "{} started at the station - {:.1f} s cycle".format(
                    act["actionType"], FORK_CYCLE_S))
        self.publish_state("arrived")
        return True

    def cb_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        self.pose = (p.x, p.y, 2.0 * math.atan2(q.z, q.w))
        v = msg.twist.twist.linear
        self.speed = math.hypot(v.x, v.y)
        if self.executing and self.progress.update(self.pose[:2]) \
                and not self._settle_arrival():
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
        if self.node_action is not None \
                and time.monotonic() >= self.node_action["until"]:
            act = self.node_action
            self.node_action = None
            self._set_action(act["id"], act["type"], "FINISHED")
            self.publish_state("station action finished")
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
        _, arrive_m, _, _ = vo.released_route(self.order)
        self._send_route(_xy(remaining), arrive_m, self.order["orderId"])
        if self.cancel_pending is not None:
            # The agent has just deliberately re-asked for this drive,
            # so the stop it was chasing is moot. Dropping the entry
            # here is what keeps _pump_cancel from cancelling the route
            # this method published one line ago.
            self.get_logger().info(
                "resume supersedes the cancel that was still pending")
            self.cancel_pending = None
        self.get_logger().info("supervision back - route re-issued")

    def _send_route(self, points, arrive_m, label):
        """Hand nav [where we are] + `points`, and believe it is driving.

        THE POSE PREPEND IS WHY THIS IS ONE METHOD AND NOT THREE.
        nav_core refuses a polyline of fewer than two points, so every
        route this node sends starts at the truck - which is what makes
        a single remaining node a drivable line. All three senders need
        exactly that: a fresh accept, a resume after a broker bounce,
        and an extension. `executing` becomes true here for the same
        reason in all three: a route was asked for. cb_nav is what may
        take that belief away again.
        """
        self.pub_route.publish(String(data=json.dumps(
            {"points": [list(self.pose[:2])] + [list(p) for p in points],
             "arrive_m": arrive_m, "label": label})))
        self.route_sent_at = time.monotonic()
        self.executing = True

    def _note_arrive_radius(self, last_node, arrive_m):
        """Say so when the last node asked for a radius nav cannot use."""
        raw = last_node["nodePosition"].get("allowedDeviationXY")
        if raw is not None and raw != arrive_m:
            self.get_logger().info(
                "allowedDeviationXY {!r} is not a radius nav can drive - "
                "arriving on {} m instead".format(raw, arrive_m))

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
        if verdict == "extend":
            # _extend answers '' when it took the update, or the reason
            # it would not - and an extension refused is a refusal like
            # any other, reported the same way on the same state.
            reason = self._extend(msg)
            if not reason:
                return
            verdict = "reject"
        if verdict == "reject":
            self._refuse(msg, reason)
            return
        points, arrive_m, released, horizon = vo.released_route(msg)
        self._note_arrive_radius(released[-1], arrive_m)
        self.order, self.horizon = msg, horizon
        self.progress = vo.Progress(released)
        self._register_node_action(msg)
        self._send_route(points, arrive_m, msg["orderId"])
        self.publish_state("order accepted")

    def _refuse(self, msg, reason):
        """Say no on the state stream, naming the order refused."""
        # NOT msg["orderId"]: 'not an object' is a valid rejection
        # reason, and a list has no .get to answer it with.
        oid = msg.get("orderId", "?") if isinstance(msg, dict) else "?"
        self.get_logger().warn("order rejected: {}".format(reason))
        self.publish_state("order rejected", [{
            "errorType": "orderError", "errorLevel": "WARNING",
            "errorDescription": reason,
            "errorReferences": [{"referenceKey": "orderId",
                                 "referenceValue": str(oid)}]}])

    def _extend(self, msg):
        """Stitch an update onto the order being driven (VDA 5050 s.6.6).

        Returns '' when the update was taken, else the reason it was not
        - which _on_order reports as an ordinary orderError.

        THE TRUCK DOES NOT NOTICE THIS. accept_order has already proved
        the released prefix is the base this vehicle was already
        driving, unchanged, so nothing behind the truck moved and there
        is nothing to stop for: no cancel, no empty goal, no
        actionState, and `executing` - which accept_order required to be
        true before it would say 'extend' at all - stays true from the
        first line of this method to the last.

        A CANCEL IN FLIGHT OUTRANKS AN EXTENSION. cancel_pending means
        somebody is still waiting to see this truck stop - the fleet
        through cancelOrder, or a lost broker - and _pump_cancel is
        chasing that stop until nav confirms it. An extension arriving
        into that window is a contradiction, not a refinement, and both
        quiet ways out of it are wrong: taking it would leave a stop
        nobody withdrew, armed and waiting for `executing` to go false
        again (_pump_cancel holds its empty goal while a route runs - it
        does not forget it), and clearing the cancel the way _resume
        does would let an outside message overrule a stop THIS node has
        already promised. _resume may do that because the drive it
        re-asks for is its own decision; an order arriving on the wire
        is not. So the extension is REFUSED BY NAME and the cancel is
        left exactly as it was. The fleet reads the orderError and may
        send a fresh order once the stop is confirmed.
        """
        if self.cancel_pending is not None:
            return ("a cancel is pending on this vehicle - it cannot take "
                    "on more of an order it is being stopped from driving")
        _, arrive_m, released, horizon = vo.released_route(msg)
        reached = self.progress.reached
        # THE INVARIANT accept_order PROMISED, CHECKED HERE ANYWAY.
        # _base_kept makes disagreement impossible today: it demands the
        # update carry every released node of the current order at the
        # same index with the same nodeId and sequenceId, and
        # Progress.nodes IS that released list - so nothing arriving
        # through accept_order can fail the comparison below (the guard
        # is tested by doctoring Progress directly). It is written
        # because of what being wrong would cost. `reached` is a COUNT,
        # and a count means nothing except against the list it was
        # counted on: if that list ever shifted underneath it,
        # lastNodeId would name a node the truck never passed, the
        # fleet ledger would free floor it never crossed, and the
        # remaining nodes handed to nav would start in the wrong place.
        # A base that moved under a driving truck is refused, loudly,
        # not driven.
        was = [(n["nodeId"], n["sequenceId"])
               for n in self.progress.nodes[:reached]]
        now = [(n["nodeId"], n["sequenceId"]) for n in released[:reached]]
        if was != now:      # a SHORTER new prefix is a disagreement too
            self.get_logger().error(
                "extension refused: the {} node(s) already passed read {} "
                "in the update and {} in the order being driven - the base "
                "moved under a driving truck".format(reached, now, was))
            return ("the update disagrees about the {} node(s) this "
                    "vehicle has already passed".format(reached))
        self.order, self.horizon = msg, horizon
        # THE NEW NODES, THE OLD COUNT - and the new nodes on purpose.
        # A changed allowedDeviationXY on an ALREADY-REACHED node is
        # IGNORED, and ignored by construction rather than by a check:
        # deviation is not position, it is the radius that decided a
        # node was PASSED, and that decision has been made - after this
        # rebuild Progress.update still scans j from the end down to
        # `reached` and never reads a node below it again. On the
        # not-yet-reached nodes and on the final one the new deviation
        # DOES take effect, because those radii are still in front of
        # the truck and still decide passing (Progress) and arrival
        # (arrive_m). That is exactly why the update's node list is
        # installed rather than the old one kept with a tail bolted on.
        self.progress = vo.Progress(released)
        self.progress.reached = reached
        remaining = self.progress.nodes[reached:]
        if remaining:
            self._note_arrive_radius(released[-1], arrive_m)
            self._send_route(_xy(remaining), arrive_m, msg["orderId"])
        else:
            # AN UPDATE THAT GREW ONLY THE HORIZON, ARRIVING AFTER THE
            # TRUCK PASSED THE LAST RELEASED NODE. Nothing is in front
            # to drive to, and [pose] alone is the one-point polyline
            # nav_core refuses outright - so nothing is published and
            # the drive already in flight stands. It still carries the
            # right label: an extension keeps the orderId, so cb_nav
            # goes on recognising its ARRIVED.
            self.get_logger().info(
                "extension released nothing ahead of the truck - the "
                "route already in flight stands")
        self._register_node_action(msg)
        self.publish_state("order extended")
        return ""

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

    def _register_node_action(self, msg):
        """The station action rides in WAITING from the moment the order
        is taken (spec 6.8: actions from orders are WAITING until they
        run). Idempotent by actionId, because an extension rebuilds the
        whole message with the SAME deterministic id and a re-register
        would knock a FINISHED cycle back to WAITING."""
        acts = msg["nodes"][-1].get("actions") or []
        if not acts:
            return
        aid = acts[0]["actionId"]
        if not any(a["actionId"] == aid for a in self.action_states):
            self._set_action(aid, acts[0]["actionType"], "WAITING")

    # ---- the closed-loop cancel ----
    def _begin_cancel(self, action_id=None, why=""):
        """Start asking nav to stop, and keep asking until it says it has.

        The first publish happens HERE rather than on the next drain, so
        a cancel that nav is already listening for costs nothing extra;
        everything after it is _pump_cancel's.

        A STATION ACTION DIES WITH THE ORDER (spec 6.6.3.2): whatever
        was WAITING or RUNNING when the cancel began is FAILED - the
        fork cycle it stood for is not going to happen. Swept before
        the cancelOrder's own RUNNING actionState is written below, so
        the sweep cannot eat it.
        """
        for act in self.action_states:
            if act["actionStatus"] in ("WAITING", "RUNNING"):
                act["actionStatus"] = "FAILED"
        self.node_action = None
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
    require()
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
