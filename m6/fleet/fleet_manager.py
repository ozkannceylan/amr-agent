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

THE FLOOR IS RESERVED BEFORE IT IS DRIVEN (M6.4). Every leg is planned
whole and then held in traffic.py's ledger, edge by edge and node by
node; what the ledger grants becomes the order's VDA 5050 BASE and what
it refuses goes out as horizon, so a truck whose corridor is taken drives
to the end of what it was given and stops there on its own, with no pause
action and nothing to un-stick. As the corridor drains the base is
extended with orderUpdateId + 1. THIS IS PROCESS DECONFLICTION AND NEVER
A COLLISION CLAIM: the scanners, the F-model and the onboard guards are
the only things that stop a truck, exactly as before traffic existed.
What the ledger buys is that the fleet never ASKS two vehicles onto one
piece of floor, so the guards are not the plan. `--no-traffic` skips the
ledger entirely and grants every route whole, which is the M6.3
behaviour and is how the gates reproduce the jam on purpose.

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
import traffic as tr                                # noqa: E402
import vda_messages as vm                           # noqa: E402
import vda_orders as vo                             # noqa: E402
from order_builder import (build_leg_order, leg2_start,   # noqa: E402
                           leg_points)
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
YIELDS_SHOWN = 5         # the traffic block is a screen, not a log
BLOCKED_SHOWN = 5        # ditto, for deadlocks wait-die cannot break
# A vehicle may refuse an extension for a reason that is pure timing -
# a cancel already in flight, a mode that flicked - and the honest
# answer to that is the next pass, not a requeue. Past this many the
# refusal stops being a race and is named on the operator's screen.
EXT_REFUSED_MAX = 5
HOLDS_SHOWN = 8          # elements per vehicle in the status document


def _node_str(node):
    return "({:.1f},{:.1f})".format(node[0], node[1])


def _element_str(element):
    """A ledger element as something an operator can read: a node is
    "(1.0,0.0)" and the floor between two nodes is "(1.0,0.0)-(2.0,0.0)".
    The pair is sorted because the element itself is undirected - one
    corridor segment is one piece of floor whichever way you drive it -
    so the same segment prints the same string every time."""
    if not isinstance(element, frozenset):
        return _node_str(element)
    ends = sorted(element)
    if len(ends) == 1:                    # degenerate; never built here
        ends = ends * 2
    return "{}-{}".format(_node_str(ends[0]), _node_str(ends[1]))


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

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, traffic_on=True):
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
        # ---- the floor ----
        self.traffic_on = bool(traffic_on)
        self.floor = tr.Reservations()
        self.graph = route.build_graph()
        self.standing = {}       # serial -> the graph node under the truck
        self.parked = {}         # serial -> the node a lost hulk sits on
        self.yields = []         # bounded; who gave way to whom, and why
        self.blocked = []        # bounded; deadlocks wait-die cannot break
        self.said_blocked = {}   # serial -> the last "no floor" line said
        self.said_lost = {}      # serial -> the last "floor went missing"
        self.stuck = {}          # serial -> why it could not be started
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
        # THE ORDER OF THESE THREE IS THE ANTI-LIVELOCK RULE.
        # _traffic_pass first: every leg already on the floor gets its
        # corridor back, oldest task first, before anything new takes a
        # bite out of it. Then the dwelled tasks send leg 2 - also in
        # submit order - and only then is a brand-new task assigned,
        # which is the youngest thing in the cell by definition.
        #
        # WHAT THAT DOES NOT GUARANTEE, said out loud: a leg 2 and a new
        # assignment are not part of the oldest-first pass, so floor
        # that comes free during this drain can still go to a younger
        # task's leg 2 rather than to an older task's retry that has
        # already run. The retry gets it on the next pass 100 ms later,
        # which is why this is an ordering preference and not a
        # priority system - and why nothing above claims one.
        self._traffic_pass(now)
        # REBUILT EVERY DRAIN, never accumulated: `stuck` answers "which
        # truck could not be started RIGHT NOW and why", and a stale
        # entry would leave a vehicle on the operator's screen as blocked
        # long after the task went to somebody else. It is cleared HERE
        # rather than inside _assign because _expire_dwells runs first:
        # a leg 2 that cannot find floor writes its sentence through the
        # same _no_floor, and a clear inside _assign would wipe it before
        # _publish_status ever saw it.
        self.stuck.clear()
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
        if task is not None:
            if task.get("order_id"):
                self.stale[serial] = task["order_id"]
            self._requeue(task["task_id"],
                          "{} on {}".format(why, serial))
        self._park(serial)

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
        fresh = fc.idle_confirmed(
            dict(veh, not_eligible=False, state_age_s=0.0))
        if fresh:
            # THE FRESH IDLE STATE IS WHAT FREES A PARKED HULK, and it
            # is the same clause list that re-earns eligibility: a
            # vehicle that is ONLINE, AUTOMATIC, placed, unlost and
            # driving nothing has stood up again, so the node the fleet
            # was holding under its body is its own once more.
            self._unpark(serial)
        if veh["not_eligible"] and fresh:
            veh["not_eligible"] = False
            self.log.info("%s re-earned eligibility", serial)
        self._traffic_state(serial, veh, msg)
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
            if self._extension_refused(serial, task, err):
                return
            veh["not_eligible"] = True
            self.log.warning("%s rejected %s: %s", serial,
                             task["order_id"],
                             err.get("errorDescription", ""))
            self._requeue(task["task_id"], "rejected by {}: {}".format(
                serial, err.get("errorDescription", "")))
            return

    def _extension_refused(self, serial, task, err):
        """True when this orderError is about a base EXTENSION we have
        in the air, and not about the leg itself.

        A REFUSED EXTENSION IS A TIMING ANSWER, NOT A FAULT. The order
        the truck is driving is untouched by a rejected update - it
        keeps the base it already had and goes on standing at the end of
        it - so requeueing the task here would throw away a transport
        because the fleet asked half a second early (a cancel already in
        flight, a mode that flicked). The pending extension is dropped
        and the next pass asks again; only a run of them is worth the
        operator's refusal list, and even then the task stays.

        WHICH ERROR IS WHICH IS ASKED OF OUR OWN BOOK, not of the error
        text: an extension is outstanding exactly when `pending` is set,
        and the vehicle cannot have refused a leg it already accepted.
        """
        trf = task.get("traffic")
        if trf is None or trf.get("pending") is None:
            return False
        update, _released = trf["pending"]
        trf["pending"] = None
        trf["ext_refused"] += 1
        self.log.info(
            "%s refused the extension of %s to orderUpdateId %d (%s) - "
            "the leg it is driving is untouched; asking again next pass",
            serial, task["order_id"], update,
            err.get("errorDescription", ""))
        if trf["ext_refused"] >= EXT_REFUSED_MAX:
            trf["ext_refused"] = 0
            self._note_refusal(
                task["order_id"],
                "{} refused {} base extensions in a row - the truck is "
                "stopped at the end of its base".format(
                    serial, EXT_REFUSED_MAX))
        return True

    def _check_arrival(self, serial, order_id, node_states, now):
        """Nothing left to drive on the order we sent = ARRIVED."""
        task = self._task_of(serial)
        if task is None or node_states or not order_id:
            return
        if order_id != task.get("order_id"):
            return
        if task["state"] == "ASSIGNED_LEG1":
            task["state"] = fc.advance(task, "leg1_arrived")
            self._drop_traffic(task, serial)
            self.dwell_until[task["task_id"]] = now + DWELL_S
            task["history"].append(
                "arrived {} - dwell {:.1f}s".format(task["from"], DWELL_S))
            self.log.info("%s arrived at %s with %s - dwelling",
                          serial, task["from"], order_id)
        elif task["state"] == "ASSIGNED_LEG2":
            task["state"] = fc.advance(task, "leg2_arrived")
            self._drop_traffic(task, serial)
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
        # `stuck` is cleared in _drain, before _expire_dwells - see the
        # comment there. It must NOT be cleared here.
        pick = fc.next_assignment(view, self.tasks, self._distance)
        if pick is None:
            return
        task, serial = pick
        note = self._distances(view, task["from"], serial)
        order_id = "ft-{}".format(uuid.uuid4().hex[:8])
        order, trf = self._leg_order(serial, task, order_id,
                                     view[serial]["position"],
                                     task["from"], "leg1")
        if order is None:
            return
        if not self._publish_order(serial, order, task, "leg1"):
            self._release(serial)
            return
        task["traffic"] = trf
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
        # Oldest submission first, for the same reason the retry pass
        # is: two dwells expiring in one drain must not hand the aisle
        # to whichever of them the queue happens to list first.
        for task in sorted(self.tasks,
                           key=lambda t: (t.get("submitted_ts") or 0.0,
                                          t["task_id"])):
            if task["state"] != "DWELL":
                continue
            if now < self.dwell_until.get(task["task_id"], 0.0):
                continue
            self._send_leg2(task)

    def _send_leg2(self, task):
        serial = task["assignee"]
        order_id = "ft-{}".format(uuid.uuid4().hex[:8])
        order, trf = self._leg_order(serial, task, order_id,
                                     leg2_start(task["from"]),
                                     task["to"], "leg2")
        if order is None:
            return
        if not self._publish_order(serial, order, task, "leg2"):
            self._release(serial)
            return
        task["traffic"] = trf
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

    # ---- the floor (M6.4) ----
    def _parked_name(self, serial):
        return "parked:{}".format(serial)

    def _release(self, serial):
        """Give the floor back, keeping the ground under the truck. A
        vehicle always owns the node it is standing on - that is the one
        reservation that is a physical fact rather than a plan."""
        if not self.traffic_on:
            return
        self.floor.release_all(serial, keep=self.standing.get(serial))
        self.floor.clear_yield(serial)

    def _drop_traffic(self, task, serial=None):
        """This leg is over - arrived, requeued or refused - so the
        corridor goes back to the floor and the truck keeps its own node,
        which is where the next leg's hold will start."""
        serial = serial or task.get("assignee")
        task.pop("traffic", None)
        if serial:
            self._release(serial)

    def _park(self, serial):
        """A truck that is GONE must not lock the floor - and must not be
        driven through either.

        Everything it held is freed, so its task can go to somebody else
        and the corridor reopens. The one node its body is standing on is
        kept, under a name of its own, until it reports a fresh idle
        state. `parked:<serial>` is a DIFFERENT OWNER on purpose: it waits
        on nothing, so it can never appear in a wait-for cycle and can
        never be chosen to yield the hulk out from under itself - which
        is exactly what would happen if the node stayed under the serial,
        because a lost vehicle has no task and therefore no age.
        """
        if not self.traffic_on:
            return
        node = self.standing.get(serial)
        self.floor.release_all(serial)
        self.floor.clear_yield(serial)
        if node is None or self.floor.owner_of(node) is not None:
            return
        self.floor.hold(self._parked_name(serial), [node])
        self.parked[serial] = node
        self.log.warning("%s is holding %s where it stopped - nothing is "
                         "routed through a parked hulk until it reports a "
                         "fresh idle state", serial, _node_str(node))

    def _unpark(self, serial):
        node = self.parked.pop(serial, None)
        if node is None:
            return
        self.floor.release_all(self._parked_name(serial))
        self.log.info("%s stood up again - %s is the vehicle's own node "
                      "once more", serial, _node_str(node))

    def _standing_from(self, msg, trf, veh):
        """The graph node under this truck, or None when nothing says.

        Its own `lastNodeId` wherever the fleet built the order that
        named it, and the nearest graph node to the reported pose only
        for a truck the fleet has no order for - a restarted manager's
        adopted vehicle, or an idle one. WHILE A LEG OF OURS IS RUNNING
        THE POSE IS NEVER ASKED: nearest_node would happily name the node
        the truck is driving TOWARDS, and release_through on that would
        free the floor still underneath it.

        THE MAP IS KEYED BY (nodeId, sequenceId). A node id is unique
        inside one of our orders today - dijkstra never repeats a node,
        so a leg's route never revisits one - but sequenceId is the
        identity VDA 5050 itself uses to tell two visits apart, and
        reading both costs nothing. The LEDGER's element identity is
        still the coordinate, so a route that genuinely revisited a node
        would collapse the two visits into one element; that is bounded
        by the router, and test_traffic pins the router's half of it.
        """
        if trf is not None:
            key = (msg.get("lastNodeId"), msg.get("lastNodeSequenceId"))
            node = trf["node_xy"].get(key)
            if node is None:
                node = next((xy for (nid, _seq), xy in trf["node_xy"].items()
                             if nid == key[0]), None)
            return trf["last_xy"] if node is None else node
        pos = veh.get("position")
        return None if pos is None else route.nearest_node(self.graph, pos)

    def _traffic_state(self, serial, veh, msg):
        """Where the truck is, written into the ledger - from EVERY
        state, before anything resolves.

        set_standing IS NOT BOOKKEEPING. resolve_deadlock frees
        everything the loser holds EXCEPT the node it was last told the
        truck stands on, so a vehicle whose standing node is unset or
        stale gets the ground under it handed to somebody else. That is
        the one way this ledger could ever put two trucks on one node, so
        it happens first, from every state, task or no task, and on a
        restarted manager's very first state too.
        """
        task = self._task_of(serial)
        trf = task.get("traffic") if task else None
        # A STATE THAT PREDATES THE LEG IS NOT A STATE ABOUT NO LEG, and
        # confusing the two cost this fleet its whole guarantee once
        # (measured 2026-08-22: one such state collapsed a fully granted
        # corridor to the single node under the truck, and the next
        # vehicle was then handed floor f1 was already driving onto -
        # silently). A vehicle publishes on its own 2 s cadence and the
        # fleet assigns at 10 Hz, so between the publish of a leg and
        # the truck's acceptance of it EVERY state carries the previous
        # orderId - or none at all. The same window opens again at the
        # dwell-to-leg-2 boundary. So a stale state may say where the
        # truck is and NOTHING ELSE: no release, no progress, and not
        # even a node id read out of the new leg's map (leg 2's "wp2" is
        # not leg 1's "wp2", and reading one for the other would move
        # the truck sideways in the ledger).
        stale = trf is not None and msg.get("orderId") != task.get("order_id")
        node = trf["last_xy"] if stale \
            else self._standing_from(msg, trf, veh)
        if node is None:
            return
        self.standing[serial] = node
        if not self.traffic_on:
            return
        self.floor.set_standing(serial, node)
        if stale:
            return                    # where it is, and nothing else
        if trf is None:
            # NO LEG OF OURS ON THIS TRUCK. A restarted manager is exactly
            # here: a nodeState carries no position, so the route an
            # adopted vehicle is driving is genuinely unknowable from the
            # wire. The fleet reserves the ONE thing it does know - the
            # ground under the body - and adopts the rest by waiting,
            # which is the M6.3 rule already. An idle truck gets the same
            # treatment, because nobody may be routed through a parked
            # vehicle either.
            if self.floor.held_by(serial) != [node]:
                self.floor.release_all(serial, keep=node)
            return
        trf["last_xy"] = node
        self.floor.release_through(serial, node)
        self._read_update(msg, trf)

    def _read_update(self, msg, trf):
        """An extension is confirmed by orderUpdateId IN THE STATE and by
        nothing else.

        Counting released nodes off the wire would be wrong twice over: a
        horizon-only extension publishes no new route at all (the truck is
        already standing at the end of its base and simply gets more of
        it), and nodeStates SHRINK as the truck drives, so a count would
        read progress as a rejection.
        """
        upd = msg.get("orderUpdateId")
        if not isinstance(upd, int) or isinstance(upd, bool):
            return
        pending = trf.get("pending")
        if pending is not None and upd >= pending[0]:
            trf["update_id"], trf["released"] = upd, pending[1]
            trf["pending"] = None
            trf["ext_refused"] = 0
        elif upd > trf["update_id"]:
            trf["update_id"] = upd

    def _leg_order(self, serial, task, order_id, start_xy, station_id, leg):
        """(order, traffic state), or (None, None) when this leg may not
        go out yet.

        The leg is planned WHOLE, held in the ledger, and only the part
        the floor granted is released; the rest rides as horizon. A grant
        of nothing is not an order - the first node is the vehicle's own
        and a base has to start somewhere - so the truck simply is not
        given the leg this pass. That is the spec's honest wait: no
        re-route, no pause action, no half-order.
        """
        points = leg_points(start_xy, station_id)
        if points is None:
            self._refuse_order(task, serial, leg, "no route")
            return None, None
        standing = self.standing.get(serial)
        if standing is None:
            standing = route.nearest_node(self.graph, start_xy)
            self.standing[serial] = standing
        # THE HOLD BEGINS UNDER THE TRUCK. traffic's wait-for graph is
        # only sound while every hold is a contiguous prefix of the route
        # STARTING AT THE VEHICLE'S OWN NODE (traffic.py's second rule); a
        # request that began further along would leave the ground under
        # the truck unowned. The common case needs no prepend at all - a
        # truck standing at S1 asked for a route to or from S1 gets a
        # route whose first node IS S1.
        hold_points = list(points) if points[0] == standing \
            else [standing] + list(points)
        offset = len(hold_points) - len(points)
        if self.traffic_on:
            self.floor.set_standing(serial, standing)
            grant = self.floor.hold(serial, tr.route_elements(hold_points))
            released = max(0, (len(grant) + 1) // 2 - offset)
        else:
            released = len(points)
        if released < 1:
            self._no_floor(serial, task, leg, station_id)
            self._release(serial)          # hand the prefix straight back
            return None, None
        self.said_blocked.pop(serial, None)
        order = build_leg_order(order_id, start_xy, station_id,
                                released_count=released)
        node_xy = {(n["nodeId"], n["sequenceId"]):
                   (n["nodePosition"]["x"], n["nodePosition"]["y"])
                   for n in order["nodes"]}
        if released < len(points):
            self.log.info("%s gets %d of %d nodes to %s as base and %d as "
                          "horizon - the rest of the corridor is taken",
                          serial, released, len(points), station_id,
                          len(points) - released)
        return order, {"points": points, "hold_points": hold_points,
                       "offset": offset, "start_xy": tuple(start_xy),
                       "station": station_id, "node_xy": node_xy,
                       "released": released, "update_id": 0,
                       "pending": None, "last_xy": hold_points[0],
                       "ext_refused": 0}

    def _no_floor(self, serial, task, leg, station_id):
        """Said ONCE per stuck truck, not ten times a second. _assign runs
        at 10 Hz and a corridor stays taken for whole seconds, so the line
        repeats only when the sentence itself changes."""
        said = "{} {} {}".format(serial, leg, station_id)
        # THE OPERATOR'S SCREEN GETS IT EVEN THOUGH THE LEDGER CANNOT.
        # Handing the prefix back clears this vehicle's `waiting` record
        # - it has to, or a truck with no task of its own would sit in
        # the wait-for graph and be picked as a deadlock loser - so a
        # truck stuck at the door would otherwise show neither a hold
        # nor a wait, which reads as a fleet that has simply forgotten
        # it. This says the sentence instead.
        self.stuck[serial] = (
            "cannot start {} of {} to {} - the route is taken".format(
                leg, task["task_id"], station_id))
        if self.said_blocked.get(serial) == said:
            return
        self.said_blocked[serial] = said
        self.log.info(
            "%s cannot start %s of %s to %s - not one node of the route is "
            "free under it; the task waits rather than driving into "
            "somebody", serial, leg, task["task_id"], station_id)

    def _in_flight(self):
        return [t for t in self.tasks
                if t.get("traffic") and t.get("assignee")
                and t["state"] in ("ASSIGNED_LEG1", "ASSIGNED_LEG2")]

    def _traffic_pass(self, now):
        """One pass of the floor: retry every held-back hold OLDEST TASK
        FIRST, then resolve whatever deadlocked.

        OLDEST FIRST IS NOT A PREFERENCE, IT IS THE ANTI-LIVELOCK RULE.
        Walk the tasks in any other order and a younger task re-grabs the
        corridor the older one just yielded, the older one yields again,
        and six passes later nothing at all has moved - measured on this
        ledger, not feared. The key is the SUBMIT time, and nothing in
        this file ever rewrites it: a yield keeps it and requeue_to_head
        keeps it, so the task that has waited longest goes on winning.
        """
        if not self.traffic_on:
            return
        for task in sorted(self._in_flight(),
                           key=lambda t: (t.get("submitted_ts") or 0.0,
                                          t["task_id"])):
            self._retry_hold(task)
        self._resolve()

    def _remaining(self, trf):
        """(index into hold_points, the route from the truck forward).

        NEVER THE ORIGINAL FULL ROUTE. The elements behind the truck have
        already been released as it passed them, and asking for them again
        would draw a wait-for edge BACKWARDS - at whichever vehicle has
        legitimately taken the floor we just left - and invent a cycle
        that is not there.
        """
        pts = trf["hold_points"]
        try:
            index = pts.index(trf["last_xy"])
        except ValueError:
            index = 0
        return index, pts[index:]

    def _retry_hold(self, task):
        """Ask the floor again for the horizon, and publish the longer
        base when it grew."""
        trf, serial = task["traffic"], task["assignee"]
        if trf["pending"] is not None:
            # ONE EXTENSION IN THE AIR AT A TIME. orderUpdateId must be
            # exactly one more than the executing order, so a second
            # update sent before the truck confirmed the first is an
            # update the truck is REQUIRED to refuse.
            return
        # THE HOLD IS RE-ASSERTED EVERY PASS, INCLUDING FOR A LEG THAT
        # WAS GRANTED WHOLE. It is not duplicated state: the ledger is
        # the only record of who owns what, this is the only record of
        # what the truck was PROMISED, and asking one against the other
        # is what turns "the fleet quietly stopped backing a base" into
        # a line somebody reads. hold() takes nothing that is not free
        # or already ours, so re-asking is free of consequence when
        # nothing is wrong.
        index, pts = self._remaining(trf)
        # MEASURED BEFORE THE RE-HOLD, because the re-hold is also the
        # repair: ask afterwards and the hole has already closed.
        before = self.floor.held_by(serial)
        grant = self.floor.hold(serial, tr.route_elements(pts))
        gained = (len(grant) + 1) // 2 if grant else 0
        base = index - trf["offset"]     # order index of the standing node
        self._check_floor(serial, task, trf, base,
                          (len(before) + 1) // 2 if before else 0, gained)
        released = max(trf["released"],
                       min(base + gained, len(trf["points"])))
        if released <= trf["released"]:
            return
        self.floor.clear_yield(serial)
        update = trf["update_id"] + 1
        order = build_leg_order(task["order_id"], trf["start_xy"],
                                trf["station"], released_count=released,
                                update_id=update)
        if self._publish_extension(serial, task, order, released, update):
            trf["pending"] = (update, released)

    def _check_floor(self, serial, task, trf, base, held, gained):
        """Does the ledger still back the base this truck was given?

        A RELEASED NODE IS A PROMISE THE FLEET CANNOT WITHDRAW - VDA 5050
        has no way to shrink a base - so the reservation behind it has to
        outlive every pass until the truck drives off it. If the re-hold
        above came back short of what the base still covers, some floor
        was freed that should not have been: the re-hold has just taken
        back whatever was still free, and what is left is a line loud
        enough to find. It is throttled per vehicle because the pass runs
        at 10 Hz and the sentence would otherwise bury itself.

        A YIELDED VEHICLE IS EXCLUDED, and that is not an exception being
        made for a bug: resolve_deadlock gives up floor on purpose, and
        the hole it leaves is written down in the spec and in _resolve
        rather than re-reported here every 100 ms.
        """
        owed = trf["released"] - base    # base nodes still ahead of it
        if held >= owed or self.floor.yielded(serial):
            self.said_lost.pop(serial, None)
            return
        said = "{}/{}/{}".format(serial, task["order_id"], owed - held)
        if self.said_lost.get(serial) == said:
            return
        self.said_lost[serial] = said
        self.log.error(
            "THE FLOOR UNDER A LIVE BASE WENT MISSING: %s had been "
            "released onto %d node(s) of %s that the ledger no longer "
            "backed; the re-hold took %d of them straight back. This is "
            "a fleet bug, not a traffic decision - the truck is entitled "
            "to drive there and nothing here can stop it.",
            serial, owed - held, task["order_id"], max(0, gained - held))

    def _publish_extension(self, serial, task, order, released, update):
        """Stamp, validate, publish - and NEVER requeue on a failure.

        An extension that does not go out costs nothing: the truck is
        standing at the end of a base it was legally given and will still
        be standing there next pass, when the fleet asks again. Only a leg
        is worth _refuse_order's brake.
        """
        if order is None:
            self.log.error("the extension of %s would not build - the "
                           "graph answered differently than it did when "
                           "the leg went out", task["order_id"])
            return False
        topic = vm.topic(serial, "order")
        order.update(self.counters.header(topic, serial))
        reason = vo.validate_order(order)
        if reason:
            self.log.error("REFUSING to extend %s on %s: %s",
                           task["order_id"], serial, reason)
            return False
        info = self.mq.publish(topic, json.dumps(order), qos=0)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            self._wire_failed("extension", task, serial, info.rc)
            return False
        horizon = len(task["traffic"]["points"]) - released
        self.log.info("%s: base extended to %d released + %d horizon as "
                      "orderUpdateId %d on %s", task["order_id"], released,
                      horizon, update, serial)
        task["history"].append(
            "base {} released + {} horizon (upd {})".format(
                released, horizon, update))
        del task["history"][:-HISTORY_MAX]
        return True

    def _parked_at_base_end(self, serial):
        """True when this truck has stopped where the fleet told it to.

        A vehicle still driving its base is NOT a candidate for a yield,
        however deadlocked the ledger looks - see _resolve.
        """
        task = self._task_of(serial)
        trf = task.get("traffic") if task else None
        if trf is None:
            return True                  # holding a node and nothing else
        released = trf["released"]
        if not 1 <= released <= len(trf["points"]):
            return False
        return trf["last_xy"] == trf["points"][released - 1]

    def _resolve(self):
        """Every cycle on the floor, until there are none - and an honest
        answer where wait-die cannot break one.

        LOOPED, NOT ASKED ONCE: find_cycle returns ONE cycle, and four
        trucks can hold two disjoint ones at the same moment.

        ONLY BETWEEN TRUCKS THAT HAVE ACTUALLY STOPPED. A wait-for edge
        appears the instant a hold is refused, which is usually while both
        trucks are still driving the base they already have. Yielding
        there would free floor a vehicle has ALREADY been told it may
        drive - VDA 5050 does not let a released node be taken back - so
        the fleet would be handing one truck's live base to another.
        Waiting costs nothing: driving frees the floor BEHIND a truck,
        never the floor it is blocked on, so the cycle survives until
        every member is parked at its base end, which is exactly when
        yielding is safe.

        THE SWAP DEADLOCK IS NOT SOLVABLE HERE AND IS NOT PRETENDED AWAY.
        When two trucks stand on the nodes each other needs, the contested
        element is the GROUND UNDER A VEHICLE: the youngest yields, keeps
        the node it stands on (it must - nothing else would be true),
        frees nothing at all, and the same cycle re-forms on the next
        pass. That signature - a resolve that freed no element - is
        detected here and answered by refusing the younger task with a
        named reason, in the refusal list and in the traffic block, where
        an operator can read it and go and move a truck. The spec's
        "breaks the cycle by construction" holds for the REACH case,
        where what the yielder gives up is floor ahead of it.
        """
        for _ in range(len(self.vehicles) + 1):
            cycle = self.floor.find_cycle()
            if not cycle:
                return
            if not all(self._parked_at_base_end(v) for v in cycle):
                # A cycle whose members are still driving defers the
                # whole pass, including any OTHER cycle that is fully
                # parked - find_cycle answers with one cycle and there
                # is no way to ask it for the next. With two vehicles
                # there is only ever one; M6.5's four can hold two, and
                # this is where that has to be looked at again.
                return
            ages = {t["assignee"]: t.get("submitted_ts") or 0.0
                    for t in self._in_flight()}
            held = {v: len(self.floor.held_by(v)) for v in cycle}
            loser = self.floor.resolve_deadlock(ages)
            if loser is None:
                return
            freed = held.get(loser, 0) - len(self.floor.held_by(loser))
            task = self._task_of(loser)
            others = [v for v in cycle if v != loser]
            if freed <= 0:
                self._unresolvable(cycle, loser, task)
                return
            self.yields.append({"vehicle": loser, "with": others,
                                "freed": freed, "ts": time.time(),
                                "task": None if task is None
                                else task["task_id"]})
            del self.yields[:-YIELDS_SHOWN]
            if task is not None:
                task["history"].append(
                    "yielded to {} - youngest task in the deadlock".format(
                        ", ".join(others)))
                del task["history"][:-HISTORY_MAX]
            self.log.warning(
                "deadlock %s - %s carries the youngest task and yields %d "
                "element(s). It keeps its task and its route and holds "
                "again the moment the corridor drains",
                " -> ".join(cycle), loser, freed)

    def _unresolvable(self, cycle, loser, task):
        why = ("swap deadlock {} - each truck stands on the floor the "
               "other needs, so the youngest yielding frees nothing and "
               "wait-die cannot break it. A vehicle has to be moved"
               .format(" <-> ".join(sorted(cycle))))
        self.log.error("UNRESOLVABLE: %s (%s was the youngest)", why, loser)
        self.blocked.append({"vehicles": sorted(cycle), "why": why,
                             "ts": time.time(),
                             "task": None if task is None
                             else task["task_id"]})
        del self.blocked[:-BLOCKED_SHOWN]
        if task is None:
            return
        self._note_refusal(task["task_id"], why)
        self._requeue(task["task_id"], why)

    def _traffic_doc(self):
        """The traffic block of the status document - who holds what, who
        waits on whom, who yielded, and every task's base/horizon split.

        The elements are rendered to strings HERE and not in the CLI: the
        retained document is the operator's record of the floor, and a
        frozenset of coordinate pairs is not JSON.
        """
        holds, waiting, yielded = {}, {}, []
        if self.traffic_on:
            names = sorted(self.vehicles) + \
                [self._parked_name(s) for s in sorted(self.parked)]
            for name in names:
                held = self.floor.held_by(name)
                if held:
                    holds[name] = [_element_str(e)
                                   for e in held[:HOLDS_SHOWN]]
                    if len(held) > HOLDS_SHOWN:
                        holds[name].append(
                            "+{} more".format(len(held) - HOLDS_SHOWN))
                want = self.floor.waiting_on(name)
                if want is not None:
                    waiting[name] = _element_str(want)
                if self.floor.yielded(name):
                    yielded.append(name)
        bases = {}
        for task in self.tasks:
            trf = task.get("traffic")
            if trf:
                bases[task["task_id"]] = [
                    trf["released"], len(trf["points"]) - trf["released"]]
        return {"enabled": self.traffic_on, "holds": holds,
                "waiting": waiting, "yielded": yielded, "bases": bases,
                "stuck": dict(self.stuck) if self.traffic_on else {},
                "yields": list(self.yields), "blocked": list(self.blocked)}

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
                # THE TRAFFIC BLOCK IS NOT A TASK FIELD ON THE WIRE.
                # It is keyed and valued by coordinate TUPLES, which
                # json.dumps cannot key a dict with; the operator reads
                # the same facts, rendered, in the document's own
                # `traffic` section below.
                "tasks": [{k: v for k, v in t.items() if k != "traffic"}
                          for t in live + done[-DONE_SHOWN:]],
                "done_count": len(done),
                "queue_len": sum(1 for t in self.tasks
                                 if t["state"] == "QUEUED"),
                "refused": list(self.refused),
                "traffic": self._traffic_doc()}

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
                    t["order_id"]] for t in doc["tasks"]],
             # THE FLOOR IS PART OF THE SHAPE. A jam is a discrete fact -
             # who waits on what, who yielded, how long each base is -
             # and an operator watching a stuck truck must not have to
             # wait out the 2 s tick to see it move. The HOLD LISTS are
             # deliberately reduced to counts: they change every time a
             # truck passes a node, which is real progress but not worth
             # a retained republish of its own.
             "f": [doc["traffic"]["enabled"],
                   {k: len(v) for k, v in doc["traffic"]["holds"].items()},
                   doc["traffic"]["waiting"], doc["traffic"]["yielded"],
                   doc["traffic"]["bases"], doc["traffic"]["stuck"],
                   len(doc["traffic"]["yields"]),
                   len(doc["traffic"]["blocked"])]},
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
        """Back to the head - and the corridor it was holding goes back
        to the floor, minus the node under its truck.

        THE SUBMIT TIME IS NOT TOUCHED, here or anywhere else. It is the
        key wait-die orders the floor by, and a requeue that restamped it
        would make the oldest task in the cell the youngest one on the
        floor - which is the livelock the whole oldest-first rule exists
        to prevent.
        """
        task = next((t for t in self.tasks if t["task_id"] == task_id), None)
        if task is not None:
            self._drop_traffic(task)
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
    # THE GATES USE THIS TO REPRODUCE THE JAM ON PURPOSE. With traffic
    # off every route is granted whole, which is exactly the M6.3
    # manager - two trucks routed at each other meet in the aisle and an
    # operator has to separate them. Running the same scenario both ways
    # is what makes the traffic evidence a contrast rather than a claim.
    parser.add_argument("--no-traffic", action="store_true",
                        help="grant every route whole - no reservation, "
                             "no horizon holds (the M6.3 behaviour)")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s fleet %(levelname)s %(message)s")
    manager = FleetManager(args.host, args.port,
                           traffic_on=not args.no_traffic)
    manager.log.info("fleet manager up - broker %s:%s, dwell %.1fs, "
                     "traffic %s", args.host, args.port, DWELL_S,
                     "OFF (--no-traffic: every route granted whole)"
                     if args.no_traffic else "on")
    try:
        manager.run()
    except KeyboardInterrupt:
        pass
    finally:
        manager.close()


if __name__ == "__main__":
    main()
