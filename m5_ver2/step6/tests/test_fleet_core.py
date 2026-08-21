"""fleet_core - assignment, queue and state machine. Pure.

Nothing here needs a broker or a truck, so the matrix is the spec: every
idle clause gets its own breaker, the FIFO promise gets a test that would
catch a skipped head, and the state machine is asked for its refusals as
well as its happy path.
"""
import os
import sys

import pytest

# fleet/ is a plain directory, not a package (m5_ver2/CLAUDE.md), and the
# tools/ tests reach their modules the same way: by path, here, rather
# than in conftest - the suite's shared path list is the node dirs only.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

from fleet_core import (IDLE_FRESH_S, advance, idle_confirmed,   # noqa: E402
                        nearest_idle, next_assignment, requeue_to_head)


def veh(**over):
    v = {"connection": "ONLINE", "operating_mode": "AUTOMATIC",
         "position": (0.0, 0.0), "executing_order": None,
         "state_age_s": 1.0, "lost": False, "not_eligible": False}
    v.update(over)
    return v


def task(tid="t1", state="QUEUED", **over):
    t = {"task_id": tid, "from": "S1", "to": "S4",
         "state": state, "assignee": None, "history": []}
    t.update(over)
    return t


@pytest.mark.parametrize("breaker", [
    {"connection": "CONNECTIONBROKEN"}, {"connection": "OFFLINE"},
    {"connection": None}, {"operating_mode": "MANUAL"},
    {"operating_mode": None}, {"executing_order": "ft-x"},
    {"state_age_s": IDLE_FRESH_S + 0.1}, {"state_age_s": None},
    {"lost": True}, {"not_eligible": True}])
def test_every_idle_clause_bites(breaker):
    assert idle_confirmed(veh()) is True
    assert idle_confirmed(veh(**breaker)) is False


def test_nearest_idle_picks_the_shorter_route_not_the_crow_flies():
    vehicles = {"f1": veh(position=(1.0, 0.0)),
                "f2": veh(position=(2.0, 0.0))}
    fn = lambda pos, sid: 10.0 if pos == (1.0, 0.0) else 3.0
    assert nearest_idle(vehicles, "S4", fn) == "f2"


def test_nearest_idle_tie_breaks_by_serial():
    vehicles = {"f2": veh(), "f1": veh()}
    assert nearest_idle(vehicles, "S4", lambda p, s: 5.0) == "f1"


def test_no_route_and_no_position_never_win():
    vehicles = {"f1": veh(position=None), "f2": veh()}
    assert nearest_idle(vehicles, "S4", lambda p, s: None) is None
    assert nearest_idle(vehicles, "S4",
                        lambda p, s: 5.0) == "f2"   # f1 has no position


def test_fifo_head_is_never_skipped():
    vehicles = {"f1": veh(executing_order="ft-busy")}
    tasks = [task("t1"), task("t2")]
    assert next_assignment(vehicles, tasks, lambda p, s: 1.0) is None
    vehicles["f1"] = veh()
    got = next_assignment(vehicles, tasks, lambda p, s: 1.0)
    assert got == (tasks[0], "f1")


def test_head_that_is_not_queued_yields_the_next_queued():
    # An ASSIGNED head is in flight, not skippable-vs-waiting: the next
    # QUEUED task behind it may be assigned to another idle vehicle.
    vehicles = {"f2": veh()}
    tasks = [task("t1", state="ASSIGNED_LEG1", assignee="f1"), task("t2")]
    got = next_assignment(vehicles, tasks, lambda p, s: 1.0)
    assert got == (tasks[1], "f2")


def test_requeue_to_head_goes_in_front_of_other_queued():
    tasks = [task("t1", state="ASSIGNED_LEG1", assignee="f1"),
             task("t2"), task("t3")]
    requeue_to_head(tasks, "t1", "vehicle lost")
    assert [t["task_id"] for t in tasks][0] == "t1"
    head = tasks[0]
    assert head["state"] == "QUEUED" and head["assignee"] is None
    assert "vehicle lost" in head["history"][-1]


def test_state_machine_happy_path_and_illegal_moves():
    t = task()
    for event, want in (("leg1_sent", "ASSIGNED_LEG1"),
                        ("leg1_arrived", "DWELL"),
                        ("leg2_sent", "ASSIGNED_LEG2"),
                        ("leg2_arrived", "DONE")):
        t["state"] = advance(t, event)
        assert t["state"] == want
    with pytest.raises(ValueError):
        advance(t, "leg1_sent")          # DONE accepts nothing
    with pytest.raises(ValueError):
        advance(task(), "leg2_arrived")  # QUEUED can't finish
