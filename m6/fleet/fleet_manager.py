"""fleet_manager.py - master control. The cell's one decision-maker.

Transport tasks in, VDA 5050 orders out. This file is WIRING and
SEQUENCING only: who drives what is fleet_core's (pure), what an order
looks like is order_builder's (pure), and what a vehicle will accept is
vda_orders' (pure, and the vehicle's own door). What is left here is a
broker, a clock and a queue.

NO ROS LIVES HERE, and that is the fleet layer's first standing
invariant: the manager is paho-only, with no VEHICLE, no rclpy and no
DDS domain. The ONLY path to a truck is VDA 5050 over MQTT - orders and
instantActions, nothing else - so the worst this process can command is
a route and a cancel. And losing it must DEGRADE, never endanger: kill
it and every truck keeps its current order, the on-board guards keep
guarding and the F-CPU keeps the chain. Nothing below can reach a
safety function, by construction.

THE PAHO THREAD ONLY ENQUEUES. Every callback puts a tuple in the inbox
and returns; a 10 Hz plain-sleep loop drains it and does ALL the work
single-threaded, so no lock guards any state in this file. There is no
executor here to borrow - vda_agent gets its drain from an rclpy timer,
this gets it from time.sleep, and that is the whole difference.

NO WILL IS SET. A vehicle's death is a protocol event and its will says
CONNECTIONBROKEN; the FLEET's death is not - no truck is waiting to be
told about it - and the honest signal is the retained status document
going stale. An operator reading a two-minute-old `ts` knows exactly
what a "manager: DEAD" flag would have said, and a stale timestamp
cannot lie the way a retained flag can.

WHAT COUNTS AS EXECUTING - the double-booking question. A truck that has
ARRIVED still reports its orderId forever (the M6.2 agent KEEPS the
order), so orderId alone would mean no vehicle is ever idle again. The
wire test is therefore orderId AND a non-empty nodeStates: something
still to drive. That is also what makes the restart honest - a truck
finishing an ft- leg is simply not idle, so a restarted manager adopts
it BY WAITING and never has to cancel anything.

  AND THE DWELL IS NOT IDLE EITHER. Between ARRIVED at the pickup and
  leg 2 going out the truck stands still with nothing left to drive,
  which by the rule above reads as idle - and a second transport would
  land on it. So the fleet's own book overrides an empty nodeStates
  while a task of ours is in flight on that vehicle. It is not a lie in
  the status document either: that order is exactly what the fleet
  believes that truck is holding.

THE STATUS DOCUMENT'S AGES ARE COMPUTED AT BUILD TIME, never stamped
when the state arrived. A dead feed therefore shows an age that GROWS,
which is the Gate 6 carry-in: the operator's screen must never show a
vehicle nobody has heard from as EN-ROUTE. Receipt is monotonic, so
state_age_s is a number every time - fleet_core's idle rule compares it
and raises on anything else, by design.

cancelOrder EXISTS IN EXACTLY ONE FLOW: a vehicle that was LOST comes
back holding an order whose task the fleet has given to somebody else.
The M6.2 agent resumes a kept order on reconnect, so the race is real -
it may drive for the seconds the cancel takes to land, and Gate 4
measures that window instead of pretending it away. Startup cancels
nothing, ever.

AND THE CANCEL IS CHASED, because one publish is not a stop. Fleet
Gate 4 (2026-08-22) measured a cancelOrder that the agent received,
acknowledged and could not act on - its own goal publisher was younger
than DDS discovery - and the truck drove 37.09 s more. The agent now
confirms its stop against nav (vda_agent._pump_cancel); this side keeps
the second half of the same honesty: `cancelled` remembers what each
returning vehicle was told to drop, every state that still shows that
order executing past a grace earns ONE more cancelOrder, throttled, and
a vehicle that never lets go is named in the refusal list where the
operator reads it. The manager still cannot force a stop - nothing here
can - but it can refuse to look away.

NO JOURNAL. The queue is in memory and the manager re-syncs from the
wire alone (retained connections, then the states themselves). A
restarted manager therefore has NO tasks, says so in the document, and
the operator resubmits. That is written down here, in the docs and in
the status the operator reads, rather than discovered.
"""
import argparse
import json
import logging
import math
import os
import queue
import sys
import time
import uuid

import paho.mqtt.client as mqtt

_HERE = os.path.dirname(os.path.abspath(__file__))
for _dir in (_HERE, os.path.normpath(os.path.join(_HERE, "..", "ipc"))):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
import fleet_core as fc                             # noqa: E402
import route                                        # noqa: E402
import vda_messages as vm                           # noqa: E402
import vda_orders as vo                             # noqa: E402
from order_builder import build_leg_order, leg2_start   # noqa: E402
from stations import STATIONS                       # noqa: E402

MQTT_HOST = "127.0.0.1"
MQTT_PORT = int(os.environ.get("VDA_MQTT_PORT", "1883"))
DRAIN_HZ = 10.0
STATUS_PERIOD_S = 2.0
DWELL_S = 3.0            # the fork cycle, simulated (owner ruling)
SUBMIT_TOPIC = "fleet/task/submit"
STATUS_TOPIC = "fleet/status"
REFUSED_MAX = 10         # the status document is a screen, not a log
HISTORY_MAX = 20         # ditto, per task
DONE_SHOWN = 5           # ditto, per finished task: the book keeps all
WIRE_WARN_S = 2.0        # a 10 Hz retry must not write 10 Hz of log
# CHASING A CANCEL THE VEHICLE HAS NOT ACTED ON. The grace is the
# agent's own confirm loop getting on with it (it republishes the empty
# goal at 10 Hz and gives up at 5 s); only past that is silence worth a
# second message. The retry period is two vehicle state periods, so one
# retry is answered before the next is due, and the cap is where an
# unheard cancel stops being a race and becomes a broken vehicle.
CANCEL_GRACE_S = 3.0
CANCEL_RETRY_S = 4.0
CANCEL_RETRY_MAX = 4


def _xy(pos):
    """(x, y) from an agvPosition, or None when it is not two reals.

    A coordinate that is not a finite number is not a position to plan
    from: route.plan_route would answer with a nearest node chosen by a
    nan comparison, which is a route to somewhere nobody asked for.
    """
    if not isinstance(pos, dict):
        return None
    out = []
    for axis in ("x", "y"):
        value = pos.get(axis)
        try:
            if isinstance(value, bool) or not math.isfinite(value):
                return None
        except (TypeError, OverflowError):
            return None
        out.append(float(value))
    return (out[0], out[1])


def _new_vehicle():
    return {"connection": None, "operating_mode": None, "position": None,
            "executing_order": None, "state_rx": None,
            "lost": False, "not_eligible": False}


class FleetManager:

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT):
        self.log = logging.getLogger("fleet")
        # ONE Counters FOR THE WHOLE MANAGER, and it is correct here for
        # the reason vda_agent's one-per-process rule is: headerId counts
        # what went out ON A TOPIC. The keys below are full topics, and
        # two vehicles never share one, so the counters are per-vehicle
        # per-topic without the manager having to keep a dict of them.
        self.counters = vm.Counters()
        self.inbox = queue.Queue()
        self.vehicles = {}       # serial -> registry row
        self.tasks = []          # index 0 is the queue head (fleet_core)
        self.refused = []        # bounded; the operator's refusal list
        self.stale = {}          # serial -> orderId a lost truck kept
        self.cancelled = {}      # serial -> a cancel we are still chasing
        self.dwell_until = {}    # task_id -> monotonic deadline
        self.stop = False
        self.last_status = 0.0
        self.last_shape = None
        self.last_wire_warn = 0.0
        self.connected = False
        self.screen_said = False
        self.mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                              client_id="fleet-manager")
        self.mq.on_connect = self._on_connect
        self.mq.on_disconnect = self._on_disconnect
        self.mq.on_message = self._on_message
        self.mq.reconnect_delay_set(min_delay=1, max_delay=8)
        self.mq.connect_async(host, port)
        self.mq.loop_start()

    # ---- paho thread: enqueue only, nothing else, ever ----
    def _on_connect(self, client, userdata, flags, reason_code,
                    properties=None):
        self.inbox.put(("connected", None))

    def _on_disconnect(self, client, userdata, flags, reason_code,
                       properties=None):
        self.inbox.put(("lost", None))

    def _on_message(self, client, userdata, msg):
        self.inbox.put((msg.topic, msg.payload))

    # ---- main thread: everything else ----
    def run(self):
        period = 1.0 / DRAIN_HZ
        while not self.stop:
            self.drain()
            time.sleep(period)

    def drain(self):
        now = time.monotonic()
        while True:
            try:
                kind, payload = self.inbox.get_nowait()
            except queue.Empty:
                break
            if kind == "connected":
                self.connected = True
                self._subscribe()
            elif kind == "lost":
                self.connected = False
                self.log.warning("broker lost - retrying inside 1-8 s; "
                                 "the trucks keep their orders")
            elif kind == SUBMIT_TOPIC:
                self._on_submit(payload)
            else:
                self._on_vehicle(kind, payload, now)
        self._expire_dwells(now)
        self._assign(now)
        self._publish_status(now)

    def _subscribe(self):
        """The whole re-sync: retained connections arrive on the SUBACK
        and the states follow within one publish period. There is
        nothing else to recover from - see the module note on no
        journal - and nothing is sent to anybody here."""
        self.mq.subscribe(
            [(vm.topic("+", name), 0)
             for name in ("connection", "state", "factsheet")]
            + [(SUBMIT_TOPIC, 1)])
        self.log.info("subscribed - vehicles and the admin wire")

    # ---- the vehicle registry ----
    def _on_vehicle(self, topic, payload, now):
        parts = topic.split("/")
        if len(parts) != 5:
            return
        serial, name = parts[3], parts[4]
        try:
            msg = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError):
            self.log.warning("unreadable %s from %s dropped", name, serial)
            return
        if not isinstance(msg, dict):
            return
        veh = self.vehicles.setdefault(serial, _new_vehicle())
        if name == "connection":
            self._on_connection(serial, veh, msg)
        elif name == "state":
            self._on_state(serial, veh, msg, now)
        # factsheet is subscribed but read by nobody yet: it is what
        # puts a truck in the status document before it has said a
        # state, and M6.4 wants its geometry for traffic.

    def _on_connection(self, serial, veh, msg):
        state = msg.get("connectionState")
        veh["connection"] = state
        # OFFLINE is a clean goodbye and CONNECTIONBROKEN is the will.
        # Both mean the fleet has lost its only path to that truck, and
        # the owner's loss ruling is about the TASK, not about how
        # politely the link ended.
        if state in ("CONNECTIONBROKEN", "OFFLINE") and not veh["lost"]:
            self._lost(serial, veh, state)
        elif state == "ONLINE" and veh["lost"]:
            self._returned(serial, veh)

    def _lost(self, serial, veh, why):
        veh["lost"] = True
        task = self._task_of(serial)
        self.log.warning("%s is gone (%s)%s", serial, why,
                         "" if task is None else
                         " mid-{}".format(task["state"]))
        if task is None:
            return
        if task.get("order_id"):
            self.stale[serial] = task["order_id"]
        self._requeue(task["task_id"],
                      "{} on {}".format(why, serial))

    def _returned(self, serial, veh):
        """Back on the wire - and its kept order is now somebody else's
        task. It re-earns eligibility the ordinary way (a clean idle
        state clears not_eligible); the cancel is about STOPPING it."""
        veh["lost"] = False
        veh["not_eligible"] = True
        order_id = self.stale.get(serial)
        if not order_id:
            return
        if not self._instant(serial, "cancelOrder"):
            # THE ENTRY STAYS. A cancel that never left this process is
            # not a cancel, and forgetting the order id would leave the
            # only record of what that truck is holding nowhere at all;
            # kept, the next time it comes back the cancel is retried.
            # There is no retry sooner than that, and the honest reason
            # is that a manager whose socket is down has no way to reach
            # the vehicle anyway - it is not driving on our word.
            self.log.error("%s returned holding %s and the cancelOrder "
                           "could not be published - it may resume",
                           serial, order_id)
            return
        del self.stale[serial]
        # WHAT WAS SENT IS NOT WHAT WAS DONE. The entry moves rather
        # than vanishing: `stale` answers "what is this truck holding
        # that we have not told it about", and `cancelled` answers "what
        # have we told it to drop and not seen it drop yet".
        self.cancelled[serial] = {"order_id": order_id, "first": None,
                                  "last_sent": None, "tries": 0}
        self.log.warning(
            "%s returned holding %s - cancelOrder sent. The agent "
            "resumes a kept order on reconnect, so it may drive until "
            "the cancel lands; that window is real (Gate 4 measures it)",
            serial, order_id)

    def _on_state(self, serial, veh, msg, now):
        veh["operating_mode"] = msg.get("operatingMode")
        position = _xy(msg.get("agvPosition"))
        if position is not None:
            veh["position"] = position
        order_id = msg.get("orderId") or None
        node_states = msg.get("nodeStates")
        node_states = node_states if isinstance(node_states, list) else []
        # AN ORDER STILL BEING DRIVEN, not merely the last one heard of
        # (module note: an arrived truck reports its orderId forever).
        veh["executing_order"] = order_id if node_states else None
        veh["state_rx"] = now
        self._chase_cancel(serial, veh, now)
        # ELIGIBILITY IS RE-EARNED BEFORE THIS STATE'S OWN REFUSALS ARE
        # READ, so a rejection cannot clear the flag it is about to set.
        # The clause list is fleet_core's, asked with the flag itself
        # taken out and the age zero - this state IS now.
        if veh["not_eligible"] and fc.idle_confirmed(
                dict(veh, not_eligible=False, state_age_s=0.0)):
            veh["not_eligible"] = False
            self.log.info("%s re-earned eligibility", serial)
        self._check_rejection(serial, veh, msg)
        self._check_arrival(serial, order_id, node_states, now)

    def _chase_cancel(self, serial, veh, now):
        """Is the truck still driving the order we cancelled? Ask again.

        ONE RETRY PER STATE THAT STILL SHOWS IT, and never faster than
        CANCEL_RETRY_S: the vehicle answers on its own 2 s cadence and a
        manager that shouted at 10 Hz would be talking over the reply it
        is waiting for. The moment the order leaves the vehicle's state
        the entry goes - that, and not our own publish, is what "the
        cancel landed" means.
        """
        entry = self.cancelled.get(serial)
        if entry is None:
            return
        if entry["first"] is None:
            entry["first"] = entry["last_sent"] = now
        if veh["executing_order"] != entry["order_id"]:
            del self.cancelled[serial]
            self.log.info("%s let go of %s - the cancel landed", serial,
                          entry["order_id"])
            return
        if now - entry["first"] < CANCEL_GRACE_S \
                or now - entry["last_sent"] < CANCEL_RETRY_S:
            return
        if entry["tries"] >= CANCEL_RETRY_MAX:
            del self.cancelled[serial]
            self.log.error(
                "%s is STILL driving %s after %d cancelOrders over %.0f s "
                "- this fleet has no other lever; the truck needs the "
                "panel", serial, entry["order_id"], CANCEL_RETRY_MAX,
                now - entry["first"])
            self._note_refusal(
                entry["order_id"],
                "{} never dropped this order after {} cancelOrders".format(
                    serial, CANCEL_RETRY_MAX))
            return
        entry["last_sent"] = now
        entry["tries"] += 1
        if self._instant(serial, "cancelOrder"):
            self.log.warning(
                "%s still shows %s executing %.1f s after the cancel - "
                "re-sent (%d of %d)", serial, entry["order_id"],
                now - entry["first"], entry["tries"], CANCEL_RETRY_MAX)

    def _check_rejection(self, serial, veh, msg):
        """An orderError naming OUR in-flight orderId. Anything else in
        errors[] is the truck's business - safetyStop is the chain
        talking, and a task is not requeued because a truck is stopped."""
        task = self._task_of(serial)
        if task is None or not task.get("order_id"):
            return
        errors = msg.get("errors")
        for err in errors if isinstance(errors, list) else []:
            if not isinstance(err, dict) \
                    or err.get("errorType") != "orderError":
                continue
            refs = err.get("errorReferences")
            if not any(isinstance(r, dict)
                       and r.get("referenceKey") == "orderId"
                       and r.get("referenceValue") == task["order_id"]
                       for r in (refs if isinstance(refs, list) else [])):
                continue
            veh["not_eligible"] = True
            self.log.warning("%s rejected %s: %s", serial,
                             task["order_id"],
                             err.get("errorDescription", ""))
            self._requeue(task["task_id"], "rejected by {}: {}".format(
                serial, err.get("errorDescription", "")))
            return

    def _check_arrival(self, serial, order_id, node_states, now):
        """Nothing left to drive on the order we sent = ARRIVED."""
        task = self._task_of(serial)
        if task is None or node_states or not order_id:
            return
        if order_id != task.get("order_id"):
            return
        if task["state"] == "ASSIGNED_LEG1":
            task["state"] = fc.advance(task, "leg1_arrived")
            self.dwell_until[task["task_id"]] = now + DWELL_S
            task["history"].append(
                "arrived {} - dwell {:.1f}s".format(task["from"], DWELL_S))
            self.log.info("%s arrived at %s with %s - dwelling",
                          serial, task["from"], order_id)
        elif task["state"] == "ASSIGNED_LEG2":
            task["state"] = fc.advance(task, "leg2_arrived")
            task["done_ts"] = time.time()
            task["history"].append("arrived {} - DONE".format(task["to"]))
            self.log.info("%s completed %s at %s", serial,
                          task["task_id"], task["to"])

    # ---- the assignment loop ----
    def _view(self, now):
        """The registry as fleet_core wants it: ages as numbers, and the
        fleet's own book overriding an empty order during the dwell."""
        view = {}
        for serial, veh in self.vehicles.items():
            age = None if veh["state_rx"] is None \
                else float(now - veh["state_rx"])
            row = dict(veh, state_age_s=age)
            if row["executing_order"] is None:
                held = self._task_of(serial)
                if held is not None:
                    row["executing_order"] = (held.get("order_id")
                                              or held["task_id"])
            view[serial] = row
        return view

    def _distance(self, position, station_id):
        """Graph length to the station, or None when there is no route.

        The router is the vehicle's own (ipc/route.py), so "far" here
        means far to DRIVE. None is not a big number: a station the
        graph cannot reach is not a candidate at any distance.
        """
        poly = route.plan_route(position, station_id)
        if poly is None:
            return None
        return sum(math.hypot(b[0] - a[0], b[1] - a[1])
                   for a, b in zip(poly, poly[1:]))

    def _assign(self, now):
        view = self._view(now)
        pick = fc.next_assignment(view, self.tasks, self._distance)
        if pick is None:
            return
        task, serial = pick
        note = self._distances(view, task["from"], serial)
        order_id = "ft-{}".format(uuid.uuid4().hex[:8])
        order = build_leg_order(order_id, view[serial]["position"],
                                task["from"])
        if not self._publish_order(serial, order, task, "leg1"):
            return
        task["order_id"] = order_id
        task["assignee"] = serial
        task["state"] = fc.advance(task, "leg1_sent")
        task["history"].append("leg1 -> {} as {} on {}".format(
            task["from"], order_id, serial))
        self.log.info("assigned %s to %s (%s)", task["task_id"], serial,
                      note)

    def _distances(self, view, station, chosen):
        """The nearest-idle evidence, logged at the moment of choosing:
        who was eligible, how far each was, and who won. Gate 1 reads
        this line rather than re-deriving the decision afterwards."""
        parts = []
        for serial in sorted(view):
            row = view[serial]
            if not fc.idle_confirmed(row) or row["position"] is None:
                continue
            dist = self._distance(row["position"], station)
            parts.append("{} {}{}".format(
                serial, "no route" if dist is None
                else "{:.2f} m".format(dist),
                " <-- chosen" if serial == chosen else ""))
        return "nearest idle to {}: {}".format(station, ", ".join(parts))

    def _expire_dwells(self, now):
        """A dwell that has run out is PERMISSION to build leg 2 - the
        task machine has no dwell_done event, and the only thing that
        leaves DWELL is the leg-2 order actually going out."""
        for task in list(self.tasks):
            if task["state"] != "DWELL":
                continue
            if now < self.dwell_until.get(task["task_id"], 0.0):
                continue
            self._send_leg2(task)

    def _send_leg2(self, task):
        serial = task["assignee"]
        order_id = "ft-{}".format(uuid.uuid4().hex[:8])
        order = build_leg_order(order_id, leg2_start(task["from"]),
                                task["to"])
        if not self._publish_order(serial, order, task, "leg2"):
            return
        task["order_id"] = order_id
        task["state"] = fc.advance(task, "leg2_sent")
        task["history"].append("leg2 -> {} as {} on {}".format(
            task["to"], order_id, serial))
        self.dwell_until.pop(task["task_id"], None)
        self.log.info("dwell done - %s drives %s to %s as %s",
                      serial, task["task_id"], task["to"], order_id)

    # ---- the wire ----
    def _publish_order(self, serial, order, task, leg):
        """Stamp, VALIDATE, publish. True when it went out.

        Validation runs on the exact object that becomes the bytes,
        header and all, because the vehicle's door reads those same
        bytes. qos 0 matches what the agent's subscription grants -
        anything higher here would be reliability on the first hop
        only, which is theatre dressed as a guarantee.

        AND THE RETURN CODE IS READ, because qos 0 has no memory: paho
        DROPS a qos-0 publish made while the client is off the wire and
        reports MQTT_ERR_NO_CONN - it does not queue it the way it
        queues qos 1. A caller that took the call itself as delivery
        would advance the task on an order no truck ever heard, and the
        fleet's own dwell override would then hold that vehicle busy
        for a leg that never began: a task stuck forever and a truck
        with it. So a failed publish is a False, the task stays exactly
        where it was, and the next drain sends it again.
        """
        if order is None:
            self._refuse_order(task, serial, leg, "no route")
            return False
        topic = vm.topic(serial, "order")
        # M1 s.3: headerId counts what went out ON THIS TOPIC and
        # serialNumber names the vehicle the topic addresses - the
        # target's id, not the manager's. The manager has no serial.
        order.update(self.counters.header(topic, serial))
        reason = vo.validate_order(order)
        if reason:
            self._refuse_order(task, serial, leg, reason)
            return False
        info = self.mq.publish(topic, json.dumps(order), qos=0)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            self._wire_failed(leg, task, serial, info.rc)
            return False
        return True

    def _wire_failed(self, leg, task, serial, rc):
        """The broker link is down and the order did not go. NOT a
        refusal: nothing is wrong with the order, the vehicle stays
        eligible and the task keeps its place - this is the one failure
        here that fixes itself, because paho reconnects inside 1-8 s
        and the drain that follows resends.

        THE LOG IS THROTTLED BECAUSE THE RETRY IS NOT. The drain runs at
        10 Hz, so an outage of one minute would otherwise be six hundred
        identical lines standing between the operator and the line that
        matters. One line per WIRE_WARN_S says the same thing.
        """
        now = time.monotonic()
        if now - self.last_wire_warn < WIRE_WARN_S:
            return
        self.last_wire_warn = now
        self.log.warning(
            "%s for %s not published to %s (paho rc %s) - a qos 0 "
            "publish made off the wire is DROPPED, so %s stays %s and "
            "the next drain resends", leg, task["task_id"], serial, rc,
            task["task_id"], task["state"])

    def _refuse_order(self, task, serial, leg, why):
        """SHOULD NEVER FIRE - order_builder's suite validates all 10x9
        station pairs and a submission with an unknown station is
        refused at the door. So this is a bug in the builder or the
        graph, not an operating case: it is LOUD, the task goes back to
        the head instead of forward as ASSIGNED, and the vehicle is
        stood down so the next pass asks somebody else rather than
        re-asking the same pair ten times a second."""
        self.log.error("REFUSING to publish %s for %s on %s: %s",
                       leg, task["task_id"], serial, why)
        self._note_refusal(task["task_id"], "{}: {}".format(leg, why))
        self.vehicles[serial]["not_eligible"] = True
        self._requeue(task["task_id"], "unbuildable {}: {}".format(leg, why))

    def _instant(self, serial, action_type):
        """True when the action reached the socket. Same qos-0 reading
        as _publish_order: off the wire it is dropped, not queued."""
        topic = vm.topic(serial, "instantActions")
        msg = dict(self.counters.header(topic, serial))
        msg["actions"] = [{"actionId": uuid.uuid4().hex,
                           "actionType": action_type,
                           "blockingType": "HARD",
                           "actionParameters": []}]
        info = self.mq.publish(topic, json.dumps(msg), qos=0)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    # ---- the admin wire ----
    def _on_submit(self, payload):
        try:
            body = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError):
            self._note_refusal("?", "unreadable submission")
            return
        if not isinstance(body, dict):
            self._note_refusal("?", "submission is not an object")
            return
        task_id = body.get("taskId")
        src, dst = body.get("from"), body.get("to")
        why = self._why_refused(task_id, src, dst)
        if why:
            self._note_refusal(
                task_id if isinstance(task_id, str) and task_id else "?", why)
            self.log.warning("refused %r: %s", task_id, why)
            return
        self.tasks.append(
            {"task_id": task_id, "from": src, "to": dst, "state": "QUEUED",
             "assignee": None, "order_id": None, "done_ts": None,
             "submitted_ts": time.time(),
             "history": ["submitted {} -> {}".format(src, dst)]})
        self.log.info("queued %s: %s -> %s", task_id, src, dst)

    def _why_refused(self, task_id, src, dst):
        if not isinstance(task_id, str) or not task_id:
            return "taskId must be a non-empty string"
        if any(t["task_id"] == task_id for t in self.tasks):
            return "taskId {} is already known".format(task_id)
        if src not in STATIONS:
            return "unknown from station {!r}".format(src)
        if dst not in STATIONS:
            return "unknown to station {!r}".format(dst)
        if src == dst:
            return "from and to are the same station"
        return ""

    def _note_refusal(self, task_id, why):
        self.refused.append({"taskId": task_id, "why": why})
        del self.refused[:-REFUSED_MAX]

    # ---- the operator's screen ----
    def _status(self, now, manager="ONLINE"):
        view = self._view(now)
        vehicles = {}
        for serial, row in view.items():
            age = row["state_age_s"]
            pos = row["position"]
            vehicles[serial] = {
                "connection": row["connection"],
                "operating_mode": row["operating_mode"],
                "position": None if pos is None
                else [round(pos[0], 3), round(pos[1], 3)],
                "executing_order": row["executing_order"],
                # COMPUTED HERE, not stamped on arrival: a feed that
                # died an hour ago shows 3600.0, never a frozen row
                # that still looks like a truck driving.
                "state_age_s": None if age is None else round(age, 1),
                "lost": bool(row["lost"]),
                "not_eligible": bool(row["not_eligible"])}
        # THE DOCUMENT IS TRIMMED AND THE BOOK IS NOT. Every task the
        # fleet has ever taken stays in self.tasks - that list is what
        # answers "is this taskId already known", and a duplicate
        # submission has to be refused for the whole run, not until the
        # task it collides with scrolled off a screen. What is retained
        # is a SCREEN: the work in flight, plus the last few
        # completions for the operator who wants to see the shift
        # moving, plus a count of the rest. Left whole, the retained
        # document would grow by a task every transport and be
        # republished every 2 s for the length of a shift.
        live = [t for t in self.tasks if t["state"] != "DONE"]
        done = sorted((t for t in self.tasks if t["state"] == "DONE"),
                      key=lambda t: t.get("done_ts") or 0.0)
        return {"ts": time.time(), "manager": manager,
                "vehicles": vehicles,
                "tasks": [dict(t) for t in live + done[-DONE_SHOWN:]],
                "done_count": len(done),
                "queue_len": sum(1 for t in self.tasks
                                 if t["state"] == "QUEUED"),
                "refused": list(self.refused)}

    def _shape(self, doc):
        """What "on change" means. Position and age move continuously -
        publishing on those would be a 10 Hz retained document - so the
        change test is the DISCRETE facts and the 2 s tick carries the
        numbers that drift."""
        return json.dumps(
            {"m": doc["manager"], "q": doc["queue_len"],
             "r": len(doc["refused"]), "d": doc["done_count"],
             "v": {s: [r["connection"], r["operating_mode"],
                       r["executing_order"], r["lost"], r["not_eligible"]]
                   for s, r in doc["vehicles"].items()},
             "t": [[t["task_id"], t["state"], t["assignee"],
                    t["order_id"]] for t in doc["tasks"]]},
            sort_keys=True)

    def _publish_status(self, now):
        doc = self._status(now)
        shape = self._shape(doc)
        if shape == self.last_shape \
                and now - self.last_status < STATUS_PERIOD_S:
            return
        self.last_shape, self.last_status = shape, now
        self.mq.publish(STATUS_TOPIC, json.dumps(doc), qos=1, retain=True)
        # SAID ONCE, AND ONLY WITH THE LINK UP, because it is the moment
        # the operator's screen begins to exist: `fleet_cli.py status`
        # has nothing to render until a retained document reaches the
        # broker. Publishes made before the CONNACK are queued by paho
        # (qos 1) and are not on the broker yet, so claiming a live
        # screen for one of those would be the wrong kind of confident.
        if self.connected and not self.screen_said:
            self.screen_said = True
            self.log.info("first status published on %s, retained - the "
                          "operator's screen is live", STATUS_TOPIC)

    # ---- shutdown ----
    def _requeue(self, task_id, why):
        fc.requeue_to_head(self.tasks, task_id, why)
        self.dwell_until.pop(task_id, None)
        for task in self.tasks:
            if task["task_id"] == task_id:
                task["order_id"] = None
                # The history is a screen row, not an audit trail; a
                # task that loops between trucks must not grow the
                # retained document without bound.
                del task["history"][:-HISTORY_MAX]
                break

    def _task_of(self, serial):
        """The task this vehicle is holding, or None. DONE is over and
        QUEUED has no assignee, so what is left is genuinely in flight."""
        for task in self.tasks:
            if task["assignee"] == serial and task["state"] != "DONE":
                return task
        return None

    def close(self):
        """Say OFFLINE in the document itself, then let go.

        The manager sets no will, so this is the ONLY moment the fleet
        can announce its own absence; after this the retained ts is what
        tells the truth, growing older by the second.
        """
        try:
            doc = self._status(time.monotonic(), "OFFLINE")
            self.mq.publish(STATUS_TOPIC, json.dumps(doc), qos=1,
                            retain=True).wait_for_publish(timeout=2.0)
        except Exception:
            pass
        try:
            self.mq.disconnect()
        except Exception:
            pass
        self.mq.loop_stop()


def main():
    parser = argparse.ArgumentParser(
        description="the fleet manager - transport tasks become orders")
    parser.add_argument("--host", default=MQTT_HOST)
    # The same env var vda_agent and send_order read, so a rig moved off
    # 1883 moves the trucks and their master control together.
    parser.add_argument("--port", type=int, default=MQTT_PORT)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s fleet %(levelname)s %(message)s")
    manager = FleetManager(args.host, args.port)
    manager.log.info("fleet manager up - broker %s:%s, dwell %.1fs",
                     args.host, args.port, DWELL_S)
    try:
        manager.run()
    except KeyboardInterrupt:
        pass
    finally:
        manager.close()


if __name__ == "__main__":
    main()
