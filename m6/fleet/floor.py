"""floor.py - the floor the trucks drive on, and who is promised what.

RESERVATION IS PROCESS DECONFLICTION AND NEVER A COLLISION CLAIM. Nothing
in this file stops a truck. The scanners, the F-model and the onboard
guards are the only things that do, exactly as before traffic existed.
What the ledger buys is that the fleet never ASKS two vehicles onto one
piece of floor, so the guards are not the plan. That sentence is the
whole licence this layer has to reason about where a vehicle may be:
read it again before changing anything here.

This is the manager's other half. `Floor` owns traffic.py's Reservations
ledger and the per-task traffic record - the base/horizon split, the
extension in the air, the node the truck was last seen standing on - and
it runs the traffic loop: holds, releases, the extension bookkeeping,
deadlock resolution, the idle sweep, the hulk pin and the `traffic` block
of the status document. fleet_manager.py keeps the registry, the queue,
assignment, the wire and the dwell timer, and calls in here.

NO ROS LIVES HERE (the directory's first invariant), and no paho either:
this file is a clock and the fleet's own book and nothing else. The one
thing it ever puts on a wire it puts there by asking the manager to -
a longer base is a decision the floor makes and the manager publishes
(`self.fleet._publish_extension`).

THE LEDGER IS THE FLOOR'S OWN AND NOBODY ELSE'S. traffic.py's
Reservations is pure - no MQTT, no ROS, no clock - and this is where the
clock and the fleet's book meet it. Nothing outside this file holds a
reference to it: "who owns this piece of floor" is a question you ask the
floor, which is why the ledger's whole vocabulary is repeated below in
the floor's own name and why everything here, the manager and the tests
included, goes through those names rather than reaching past them.

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

  AND A HOLD NOW HAS TWO SHAPES M6.4 DID NOT HAVE (M6.5, both measured
  before they were written). A truck that has arrived in a STATION SPUR
  keeps the junction it came in by for the length of the dwell, because
  a spur has exactly one way out and it is the same one the next truck
  wants in - releasing it on arrival is what made M6.4's Gate 2
  unpassable (_dwell_entry). And a truck with NO TASK stops holding the
  aisle after IDLE_HOLD_S, because at four vehicles one forgotten truck
  is the difference between a busy floor and a jammed one - unless it is
  parked in a spur, which is nobody's corridor (_idle_floor).
"""
import logging
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
for _dir in (_HERE, os.path.normpath(os.path.join(_HERE, "..", "ipc"))):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
import route                                        # noqa: E402
import traffic as tr                                # noqa: E402
from order_builder import build_leg_order, leg_points   # noqa: E402
from stations import STATIONS                       # noqa: E402

YIELDS_SHOWN = 5         # the traffic block is a screen, not a log
BLOCKED_SHOWN = 5        # ditto, for deadlocks wait-die cannot break
# A vehicle may refuse an extension for a reason that is pure timing -
# a cancel already in flight, a mode that flicked - and the honest
# answer to that is the next pass, not a requeue. Past this many the
# refusal stops being a race and is named on the operator's screen.
EXT_REFUSED_MAX = 5
HOLDS_SHOWN = 8          # elements per vehicle in the status document
# AN IDLE TRUCK MAY NOT HOLD THE AISLE FOREVER (M6.5). A vehicle the
# fleet is not driving keeps the ground under its body reserved, which
# is right for a truck that just finished and wrong for one that has
# been standing in a corridor since the last shift: at four vehicles
# that single node is the difference between a busy floor and a jammed
# one. Past this, the hold is given back and said out loud. THE TRUCK
# IS STILL THERE - reservation is process deconfliction, so what is
# given up is the fleet's promise not to route through it, never a
# claim that the floor is clear. The scanners remain what stop anybody
# sent that way. A vehicle parked IN a station spur is the exception
# and keeps its node: nothing else is ever routed to a spur but the
# truck being sent to that station, so the hold costs no corridor and
# dropping it would send a second truck into an occupied dead end.
IDLE_HOLD_S = 30.0
IDLE_SHOWN = 5           # the traffic block is a screen, not a log


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


class Floor:
    """The cell's floor: the ledger, the traffic loop and the records.

    It holds the manager rather than the other way round for the things
    the floor cannot know on its own - which task a vehicle is carrying,
    what the queue thinks, and how to reach the wire. Everything it asks
    for is named `self.fleet.<something>` so the direction of the
    dependency is readable at every call site: the floor reads the
    fleet's book and the fleet's wire, and the fleet reaches the floor
    only through `self.floor`.
    """

    def __init__(self, fleet, traffic_on=True):
        self.fleet = fleet
        # THE SAME LOGGER THE MANAGER USES, by name and therefore by
        # object: the floor's sentences and the manager's are one
        # operator's log, and a handler put on "fleet" catches both.
        self.log = logging.getLogger("fleet")
        self.traffic_on = bool(traffic_on)
        self._res = tr.Reservations()
        self.graph = route.build_graph()
        self.standing = {}       # serial -> the graph node under the truck
        self.parked = {}         # serial -> the node a lost hulk sits on
        self.yields = []         # bounded; who gave way to whom, and why
        self.blocked = []        # bounded; deadlocks wait-die cannot break
        self.said_blocked = {}   # serial -> the last "no floor" line said
        self.said_lost = {}      # serial -> the last "floor went missing"
        self.idle_hold = {}      # serial -> {node, since, freed}
        self.idle_freed = []     # bounded; idle holds the clock took back
        self.stuck = {}          # serial -> why it could not be started

    # ---- the ledger, in the floor's own name ----
    # ONE PATH TO THE LEDGER AND NO SECOND ONE. `_res` is storage and is
    # never reached past these twelve names - not from here, not from the
    # manager, not from a test - so a caller that wants to watch or stand
    # in for a ledger call has exactly one place to do it, and the floor
    # itself sees the same object every caller does.
    def hold(self, vehicle, elements):
        return self._res.hold(vehicle, elements)

    def release_through(self, vehicle, node):
        self._res.release_through(vehicle, node)

    def release_all(self, vehicle, keep=None):
        self._res.release_all(vehicle, keep=keep)

    def owner_of(self, element):
        return self._res.owner_of(element)

    def held_by(self, vehicle):
        return self._res.held_by(vehicle)

    def waiting_on(self, vehicle):
        return self._res.waiting_on(vehicle)

    def find_cycle(self):
        return self._res.find_cycle()

    def resolve_deadlock(self, ages):
        return self._res.resolve_deadlock(ages)

    def set_standing(self, vehicle, node):
        self._res.set_standing(vehicle, node)

    def yielded(self, vehicle):
        return self._res.yielded(vehicle)

    def clear_yield(self, vehicle):
        self._res.clear_yield(vehicle)

    def clear_wait(self, vehicle):
        self._res.clear_wait(vehicle)

    # ---- the holds (M6.4) ----
    def _parked_name(self, serial):
        return "parked:{}".format(serial)

    def release(self, serial):
        """Give the floor back, keeping the ground under the truck.

        The node under a vehicle is the one reservation that is a
        physical fact rather than a plan, and it is kept here for that
        reason - but it is NOT true any more that a vehicle always owns
        the node it is standing on. IDLE_HOLD_S takes that node back
        from a truck nobody is driving, deliberately and out loud
        (_idle_floor), which is the one place this fleet lets the ledger
        stop describing where a truck is.
        """
        if not self.traffic_on:
            return
        self.release_all(serial, keep=self.standing.get(serial))
        self.clear_yield(serial)

    def drop_traffic(self, task, serial=None):
        """This leg is over - arrived, requeued or refused - so the
        corridor goes back to the floor and the truck keeps its own node,
        which is where the next leg's hold will start."""
        serial = serial or task.get("assignee")
        task.pop("traffic", None)
        if serial:
            self.release(serial)

    # ---- the spur handover (M6.5, owner ruling) ----
    def spur_entry(self, node):
        """The one node a spur station is reached and left through, or
        None when the station sits on its aisle and has no such node.

        IT IS READ OFF THE GRAPH, NOT OFF A LIST OF STATION IDS. A
        station at the end of a spur has exactly ONE neighbour in
        route.build_graph - the junction its spur lands on - and that is
        the whole property this rule needs: the way in is the way out.
        S1 and S5 sit ON their aisles, have two neighbours or more, and
        are correctly not spurs; a station moved in stations.py takes
        its answer with it.
        """
        neighbours = self.graph.get(node) or ()
        return next(iter(neighbours)) if len(neighbours) == 1 else None

    def _dwell_entry(self, serial):
        """The junction a DWELLING truck keeps under the owner's ruling.

        M6.4's Gate 2 measured what releasing it costs (run A, 11:34):
        the occupant let the junction go in the millisecond it arrived,
        the truck queued for the same station took it inside one 100 ms
        pass, and three seconds later the occupant's leg 2 asked for its
        only way out and got a swap deadlock wait-die cannot break. A
        spur station therefore could not be handed from one vehicle to
        another at all.

        So the junction stays held with the station node through the
        dwell, and leg 2's hold - which starts at the station and runs
        out through that same junction - takes it over with nothing
        freed in between.

        THE COST IS BIGGER THAN "THE NEXT TRUCK WAITS", and it is worth
        writing down rather than discovering. Every junction on this
        graph is an AISLE node: seven of the ten stations are spurs, and
        their junctions have degree 3 or 4. Two of them serve two
        stations each - (-8.0, 5.65) is the way into both S6 and S8, and
        (8.0, 5.65) into both S7 and S9 - so a truck dwelling at S6
        holds the only way into S8 as well, and in both cases it closes
        the main aisle to ALL transit through that x. For DWELL_S, which
        is 3.0 s. That is the ruling's accepted price and the thing to
        watch first if the acceptance run's waiting time looks wrong.

        DERIVED, NEVER STORED. The pin exists exactly while a task of
        ours is in DWELL on this vehicle at that station, so there is no
        flag to leak, nothing to clear on a requeue, and a hold that
        some other path gives back is simply taken again by the next
        state (_hold_standing asks this same question).
        """
        task = self.fleet._task_of(serial)
        if task is None or task["state"] != "DWELL":
            return None
        station = STATIONS.get(task["from"])
        if station is None:
            return None
        node = (station["x"], station["y"])
        if self.standing.get(serial) != node:
            return None
        return self.spur_entry(node)

    def _release_to(self, task, trf, node):
        """How far release_through may free as this state is read: the
        node under the truck, EXCEPT where leg 1 has just ended in a
        spur, where it is the junction one step behind it. The ledger
        therefore never sees that junction free, not even for the
        microseconds between this release and end_leg1's re-take."""
        if task["state"] != "ASSIGNED_LEG1" or node != trf["points"][-1]:
            return node
        entry = self.spur_entry(node)
        pts = trf["hold_points"]
        if entry is None or entry not in pts:
            return node
        return entry if pts.index(entry) < pts.index(node) else node

    def end_leg1(self, task, serial):
        """Leg 1 is over and the dwell begins. The corridor behind the
        truck goes back to the floor - and a spur's entry node does not
        (see _dwell_entry). A station on an aisle has no entry node and
        this is drop_traffic exactly as before."""
        entry = self._dwell_entry(serial)
        task.pop("traffic", None)
        if not self.traffic_on:
            return
        if entry is None or self.owner_of(entry) != serial:
            self.release(serial)
            return
        self.release_through(serial, entry)
        self.clear_yield(serial)

    def _hold_standing(self, serial, node):
        """What a vehicle with NO LEG OF OURS may hold: the ground under
        its body, plus the spur junction while it dwells. An idle hold
        the clock has already taken back is not taken again - that is
        the whole of IDLE_HOLD_S; the truck re-earns it by moving."""
        entry = self._dwell_entry(serial)
        want = [node] if entry is None \
            else [entry, tr.edge(entry, node), node]
        if self.held_by(serial) == want:
            self.clear_wait(serial)
            return
        stamp = self.idle_hold.get(serial)
        if stamp is not None and stamp["freed"] and stamp["node"] == node:
            return
        self.release_all(serial)
        if entry is not None and self.owner_of(entry) is not None:
            want = [node]        # the junction is not this truck's to keep
        self.hold(serial, want)
        # AND IT WAITS FOR NOTHING. release_all(keep=) used to clear
        # the wait as a side effect and this path no longer goes
        # through it: a truck with no leg of ours running has no
        # task, therefore no age, therefore would be picked as the
        # youngest in any cycle it appeared in - and wait-die would
        # free the ground under it, or the junction it is keeping
        # for leg 2 while it dwells.
        self.clear_wait(serial)

    def _idle_floor(self, now):
        """The IDLE_HOLD_S sweep, once per traffic pass.

        The clock starts when a vehicle with no task of ours is first
        seen standing on a node and restarts every time it moves, so a
        truck that is working - or one an operator is driving around in
        teleop - never ages. A vehicle executing an order the fleet does
        not own (a restarted manager's adopted truck) is not idle
        either: the fleet adopts it by waiting, and taking the floor out
        from under it would be the opposite.

        SAID ONCE, because the pass runs at 10 Hz: the release sets the
        flag that both suppresses the line and stops _hold_standing
        taking the node straight back.

        WHAT HAPPENS NEXT IS NOT PRETENDED AWAY. The truck is still
        standing there and the ledger has stopped saying so, so:
        * another vehicle may be routed onto that node, and what stops
          it is its scanners - a jam an operator can see and clear,
          which is the trade this rule makes against a corridor closed
          for a shift by a truck nobody is driving;
        * the freed truck re-acquires its ground the ordinary way, by
          being given work: leg_order asks for the whole route from its
          standing node and takes it if it is free. If somebody else has
          taken it in the meantime that hold comes back empty, the task
          cannot start, and the fleet says exactly that on the operator's
          screen (_no_floor, "the route is taken"). There is no third
          lever here and there never was: this fleet's answer to a floor
          it cannot untangle is to name it and let a person move a
          truck, the same answer wait-die gives a swap deadlock.
        """
        for serial in sorted(self.fleet.vehicles):
            node = self.standing.get(serial)
            veh = self.fleet.vehicles[serial]
            busy = (self.fleet._task_of(serial) is not None
                    or veh["executing_order"] is not None)
            stamp = self.idle_hold.get(serial)
            if busy or node is None:
                self.idle_hold.pop(serial, None)
                continue
            if stamp is not None and stamp["freed"] and stamp["node"] == node:
                continue                       # already given back
            held = self.held_by(serial)
            if not held:
                self.idle_hold.pop(serial, None)
                continue
            if stamp is None or stamp["node"] != node:
                self.idle_hold[serial] = {"node": node, "since": now,
                                          "freed": False}
                continue
            if now - stamp["since"] < IDLE_HOLD_S:
                continue
            if self.spur_entry(node) is not None:
                continue          # parked IN a station: the spur is its own
            stamp["freed"] = True
            self.release_all(serial)
            self.clear_yield(serial)
            self.idle_freed.append({"vehicle": serial,
                                    "node": _node_str(node),
                                    "freed": len(held), "ts": time.time()})
            del self.idle_freed[:-IDLE_SHOWN]
            self.log.warning(
                "%s has stood on %s with no task for %.0f s - its hold is "
                "given back so one parked truck cannot jam an aisle. THE "
                "TRUCK IS STILL THERE: this gives up the fleet's promise "
                "not to route through it, not a claim that the floor is "
                "clear, and the scanners remain what stop anybody sent "
                "that way", serial, _node_str(node), now - stamp["since"])

    def park(self, serial):
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
        self.release_all(serial)
        self.clear_yield(serial)
        if node is None or self.owner_of(node) is not None:
            return
        self.hold(self._parked_name(serial), [node])
        self.parked[serial] = node
        self.log.warning("%s is holding %s where it stopped - nothing is "
                         "routed through a parked hulk until it reports a "
                         "fresh idle state", serial, _node_str(node))

    def unpark(self, serial):
        node = self.parked.pop(serial, None)
        if node is None:
            return
        self.release_all(self._parked_name(serial))
        self.log.info("%s stood up again - %s is the vehicle's own node "
                      "once more", serial, _node_str(node))

    def _follow_hulk(self, serial, node):
        """THE PIN FOLLOWS THE TRUCK BACK (M6.5).

        A parked pin is only parked where the ledger last SAW the
        vehicle, and M6.4's Gate 5 run 1 measured the gap: with no agent
        alive nothing publishes an empty goal, so nav drove a dead truck
        2.93 m onto floor the fleet had already granted to its
        replacement while the hulk's pin still sat where it died. The
        pin cannot follow a vehicle that is silent - nothing can - but
        the moment it speaks again it can, and it must do so BEFORE the
        vehicle re-earns eligibility, because until then the fleet is
        still routing other trucks around a node that is not the one it
        is on.

        A node somebody else legitimately took while it was away is not
        taken back: the pin is dropped and the sentence says so, which
        is the honest state (that is exactly the run-1 case, where the
        hulk's own re-hold was refused).
        """
        pinned = self.parked.get(serial)
        if pinned is None or pinned == node:
            return
        self.release_all(self._parked_name(serial))
        owner = self.owner_of(node)
        if owner is not None:
            del self.parked[serial]
            self.log.warning(
                "%s came back on %s, which %s already holds - the pin is "
                "dropped rather than moved onto somebody else's floor; "
                "nothing is reserved under that truck until it reports a "
                "fresh idle state", serial, _node_str(node), owner)
            return
        self.hold(self._parked_name(serial), [node])
        self.parked[serial] = node
        self.log.warning(
            "%s rolled from %s to %s while the fleet could not hear it - "
            "the hulk's pin moves with it and %s is free again",
            serial, _node_str(pinned), _node_str(node), _node_str(pinned))

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

    def note_state(self, serial, veh, msg):
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
        task = self.fleet._task_of(serial)
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
        self.set_standing(serial, node)
        # BEFORE THE STALE RETURN, because a stale state still says WHERE
        # the truck is, and where a returning hulk is happens to be the
        # only thing this needs.
        self._follow_hulk(serial, node)
        if stale:
            return                    # where it is, and nothing else
        if trf is None:
            # NO LEG OF OURS ON THIS TRUCK. A restarted manager is exactly
            # here: a nodeState carries no position, so the route an
            # adopted vehicle is driving is genuinely unknowable from the
            # wire. The fleet reserves the ONE thing it does know - the
            # ground under the body - and adopts the rest by waiting,
            # which is the M6.3 rule already. An idle truck gets the same
            # treatment, because nobody may be routed through a truck
            # standing in an aisle either - until IDLE_HOLD_S decides
            # that one forgotten truck may not close a corridor for a
            # whole shift and _idle_floor hands the node back. Past
            # that, this branch stops re-taking it and the fleet WILL
            # route another vehicle onto it: the ruling accepting a jam
            # it can see over one it cannot.
            self._hold_standing(serial, node)
            return
        trf["last_xy"] = node
        self.release_through(serial, self._release_to(task, trf, node))
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

    def extension_refused(self, serial, task, err):
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
            self.fleet._note_refusal(
                task["order_id"],
                "{} refused {} base extensions in a row - the truck is "
                "stopped at the end of its base".format(
                    serial, EXT_REFUSED_MAX))
        return True

    def leg_order(self, serial, task, order_id, start_xy, station_id, leg):
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
            self.fleet._refuse_order(task, serial, leg, "no route")
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
            self.set_standing(serial, standing)
            grant = self.hold(serial, tr.route_elements(hold_points))
            released = max(0, (len(grant) + 1) // 2 - offset)
        else:
            released = len(points)
        if released < 1:
            self._no_floor(serial, task, leg, station_id)
            self.release(serial)          # hand the prefix straight back
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
        return [t for t in self.fleet.tasks
                if t.get("traffic") and t.get("assignee")
                and t["state"] in ("ASSIGNED_LEG1", "ASSIGNED_LEG2")]

    def traffic_pass(self, now):
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
        # FIRST, so floor an idle truck has been sitting on since the
        # last shift is available to the retries in this same pass.
        self._idle_floor(now)
        for task in sorted(self._in_flight(),
                           key=lambda t: (t.get("submitted_ts") or 0.0,
                                          t["task_id"])):
            self.retry_hold(task)
        self._resolve()

    def remaining(self, trf):
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

    def retry_hold(self, task):
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
        index, pts = self.remaining(trf)
        # MEASURED BEFORE THE RE-HOLD, because the re-hold is also the
        # repair: ask afterwards and the hole has already closed.
        before = self.held_by(serial)
        grant = self.hold(serial, tr.route_elements(pts))
        gained = (len(grant) + 1) // 2 if grant else 0
        base = index - trf["offset"]     # order index of the standing node
        self._check_floor(serial, task, trf, base,
                          (len(before) + 1) // 2 if before else 0, gained)
        released = max(trf["released"],
                       min(base + gained, len(trf["points"])))
        if released <= trf["released"]:
            return
        self.clear_yield(serial)
        update = trf["update_id"] + 1
        order = build_leg_order(task["order_id"], trf["start_xy"],
                                trf["station"], released_count=released,
                                update_id=update)
        if self.fleet._publish_extension(serial, task, order, released,
                                         update):
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
        if held >= owed or self.yielded(serial):
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

    def _parked_at_base_end(self, serial):
        """True when this truck has stopped where the fleet told it to.

        A vehicle still driving its base is NOT a candidate for a yield,
        however deadlocked the ledger looks - see _resolve.
        """
        task = self.fleet._task_of(serial)
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
        for _ in range(len(self.fleet.vehicles) + 1):
            cycle = self.find_cycle()
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
            held = {v: len(self.held_by(v)) for v in cycle}
            loser = self.resolve_deadlock(ages)
            if loser is None:
                return
            freed = held.get(loser, 0) - len(self.held_by(loser))
            task = self.fleet._task_of(loser)
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
                self.fleet._note_history(
                    task, "yielded to {} - youngest task in the "
                    "deadlock".format(", ".join(others)))
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
        self.fleet._note_refusal(task["task_id"], why)
        self.fleet._requeue(task["task_id"], why)

    def doc(self):
        """The traffic block of the status document - who holds what, who
        waits on whom, who yielded, and every task's base/horizon split.

        The elements are rendered to strings HERE and not in the CLI: the
        retained document is the operator's record of the floor, and a
        frozenset of coordinate pairs is not JSON.
        """
        holds, waiting, yielded = {}, {}, []
        if self.traffic_on:
            names = sorted(self.fleet.vehicles) + \
                [self._parked_name(s) for s in sorted(self.parked)]
            for name in names:
                held = self.held_by(name)
                if held:
                    holds[name] = [_element_str(e)
                                   for e in held[:HOLDS_SHOWN]]
                    if len(held) > HOLDS_SHOWN:
                        holds[name].append(
                            "+{} more".format(len(held) - HOLDS_SHOWN))
                want = self.waiting_on(name)
                if want is not None:
                    waiting[name] = _element_str(want)
                if self.yielded(name):
                    yielded.append(name)
        bases = {}
        for task in self.fleet.tasks:
            trf = task.get("traffic")
            if trf:
                bases[task["task_id"]] = [
                    trf["released"], len(trf["points"]) - trf["released"]]
        return {"enabled": self.traffic_on, "holds": holds,
                "waiting": waiting, "yielded": yielded, "bases": bases,
                "stuck": dict(self.stuck) if self.traffic_on else {},
                "yields": list(self.yields), "blocked": list(self.blocked),
                # An operator who finds a truck no longer reserving the
                # node it is standing on must be able to read WHY on the
                # same screen, and not have to go and find the log.
                "idle": list(self.idle_freed)}
