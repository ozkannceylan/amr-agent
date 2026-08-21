"""fleet_core.py - who drives what, decided pure. No ROS, no MQTT, no clock.

The fleet layer's three standing invariants (fleet/README.md) bind here
even though this file talks to nothing. NO ROS: the manager is paho-only
and this module is not even that. The ONLY path to a vehicle is VDA 5050
over MQTT, so nothing decided below is anything a vehicle cannot simply
be TOLD in an order - there is no back channel to invent. And losing the
fleet layer must only DEGRADE, never endanger: what lives here is process
decision, while the safety chain sits onboard and in the F-CPU, beyond
this file's reach by construction.

Owner rulings (2026-08-21) are the shape of the task model:

  - A transport is TWO LEGS, A->B: an order to the pickup station, a
    dwell standing in for the fork cycle, an order to the dropoff. That
    is why the machine has a DWELL wedged between two ASSIGNED states
    instead of one order per task.
  - On loss mid-task the task RETURNS TO THE QUEUE HEAD and the other
    vehicle may take it; the lost vehicle gets nothing until it is
    idle-confirmed again. requeue_to_head is the first half of that
    ruling; the not_eligible flag idle_confirmed refuses is the second.

Everything is injected: distances as distance_fn, ages as state_age_s
already measured against the manager's clock - which is how the hard
questions (all lost, all busy, no route) get asked without a broker.

Vehicles are {serial: {connection, operating_mode, position,
executing_order, state_age_s, lost, not_eligible}}; tasks are a list of
{task_id, from, to, state, assignee, history}, index 0 the queue head.
The manager owns those dicts; only requeue_to_head reorders them.
"""

IDLE_FRESH_S = 3.0   # a state older than this cannot confirm idleness:
                     # silence is not stillness, and an order sent on a
                     # stale state is sent to a truck that may be driving

# The task machine. There is NO dwell_done event: the dwell timer is the
# manager's, and a timer expiring is not something that happened to the
# task - it is permission for the manager to build leg 2. The one event
# that leaves DWELL is leg2_sent, reported once the order is actually on
# the wire, so a dwell whose publish failed is still a dwell.
_TRANSITIONS = {
    "QUEUED":        {"leg1_sent": "ASSIGNED_LEG1"},
    "ASSIGNED_LEG1": {"leg1_arrived": "DWELL"},
    "DWELL":         {"leg2_sent": "ASSIGNED_LEG2"},
    "ASSIGNED_LEG2": {"leg2_arrived": "DONE"},
    "DONE":          {},
}


def idle_confirmed(vehicle):
    """True only when every clause holds - and each one is a refusal
    somebody has to live with. ONLINE and AUTOMATIC: a broken link or a
    teleop truck takes no orders. No executing_order: never two orders
    on one vehicle. A state present and no older than IDLE_FRESH_S:
    idleness is a fact about NOW, not the last thing we heard. Not lost,
    and not not_eligible - the manager sets that flag after a rejection
    or a loss-return and clears it on the first state that satisfies
    every other clause here, which is what "re-earns eligibility" means.
    """
    age = vehicle.get("state_age_s")
    return (vehicle.get("connection") == "ONLINE"
            and vehicle.get("operating_mode") == "AUTOMATIC"
            and vehicle.get("executing_order") is None
            and age is not None and age <= IDLE_FRESH_S
            and not vehicle.get("lost")
            and not vehicle.get("not_eligible"))


def nearest_idle(vehicles, pickup_station, distance_fn):
    """The idle vehicle closest to pickup_station, or None.

    distance_fn(position_xy, station_id) -> float | None, and None means
    no route: the graph is the aisle centrelines, so "far" and "cannot
    get there" are different answers and only the first competes. The
    distance is the router's, never the crow's - the point of asking a
    graph at all. A vehicle with no reported position is never asked.
    Serials are walked sorted and ties keep the incumbent, so an exact
    tie goes to the lower serial: arbitrary, but the same arbitrary
    answer every time, which is what a fleet log needs.
    """
    best = None
    for serial in sorted(vehicles):
        vehicle = vehicles[serial]
        if not idle_confirmed(vehicle) or vehicle.get("position") is None:
            continue
        dist = distance_fn(vehicle["position"], pickup_station)
        if dist is None:
            continue
        if best is None or dist < best[0]:
            best = (dist, serial)
    return None if best is None else best[1]


def next_assignment(vehicles, tasks, distance_fn):
    """(task, serial) for the one assignment to make now, or None.

    FIFO is a promise, not a hint. Only the FIRST QUEUED task is ever
    considered: if nobody idle can take it the answer is None, and the
    tasks behind it wait however long that costs. Tasks that are not
    QUEUED are in flight, not skipped - an ASSIGNED head is somebody
    already driving, so the queued task behind it is genuinely the head
    of the queue and another idle vehicle may have it.
    """
    head = next((t for t in tasks if t["state"] == "QUEUED"), None)
    if head is None:
        return None
    serial = nearest_idle(vehicles, head["from"], distance_fn)
    return None if serial is None else (head, serial)


def requeue_to_head(tasks, task_id, why):
    """Put a task back at the front, in place. The owner's loss ruling.

    Index 0, ahead of every other QUEUED task: the interrupted transport
    is the oldest work in the cell and re-queueing it behind newer tasks
    would punish it twice. The assignee is cleared - it is nobody's
    again - and why is written into history, because a task that visits
    QUEUED twice is exactly the thing an operator will ask about.
    """
    for index, task in enumerate(tasks):
        if task["task_id"] == task_id:
            break
    else:
        raise ValueError("no such task: {!r}".format(task_id))
    task = tasks.pop(index)
    task["state"] = "QUEUED"
    task["assignee"] = None
    task.setdefault("history", []).append(
        "requeued to head: {}".format(why))
    tasks.insert(0, task)


def advance(task, event):
    """The new state after event, or ValueError naming state and event.

    It returns rather than assigns: the caller writes the state only
    once the side effect the event claims has actually happened, so an
    order that failed to publish cannot leave a task believing it is
    ASSIGNED. DONE accepts nothing at all.
    """
    state = task["state"]
    allowed = _TRANSITIONS.get(state)
    if allowed is None:
        raise ValueError("unknown task state {!r}".format(state))
    if event not in allowed:
        raise ValueError(
            "event {!r} is illegal in state {!r}".format(event, state))
    return allowed[event]
