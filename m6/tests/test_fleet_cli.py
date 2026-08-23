"""fleet_cli's two pure halves: what a submission IS, and what the
operator's screen SAYS.

main() needs a broker and a fleet, so what a suite can hold is the
payload builder and the renderer - and they are the halves that matter.
The builder is what the manager's admin door will read, so its refusals
have to agree with that door's; the renderer is the only thing an
operator ever sees of the fleet, and the one property it must have is
that a document which has stopped being updated READS as stale rather
than as two trucks driving. That is the Gate 6 carry-in, asked here
against a frozen document instead of a rig.
"""
import json
import os
import sys

import pytest

# fleet_cli imports paho at module level and Windows has no paho, so the
# import must be asked for before the module is reached, not after.
pytest.importorskip("paho.mqtt.client")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import fleet_cli as cli                             # noqa: E402
from stations import STATIONS                       # noqa: E402

# A document exactly as fleet_manager._status builds one: one truck
# driving our leg, one truck lost mid-task with its feed 42 s cold, one
# task in flight, one waiting, one finished, and a refusal.
NOW = 1760000000.0
DOC = {
    "ts": NOW - 0.4,
    "manager": "ONLINE",
    "vehicles": {
        "f1": {"connection": "ONLINE", "operating_mode": "AUTOMATIC",
               "position": [-3.0, -5.5], "executing_order": "ft-0344caf5",
               "state_age_s": 0.3, "lost": False, "not_eligible": False},
        "f2": {"connection": "CONNECTIONBROKEN",
               "operating_mode": "AUTOMATIC", "position": [6.0, -8.0],
               "executing_order": None, "state_age_s": 42.0,
               "lost": True, "not_eligible": True},
    },
    "tasks": [
        {"task_id": "ft-1a2b3c4d", "from": "S1", "to": "S4",
         "state": "ASSIGNED_LEG1", "assignee": "f1",
         "order_id": "ft-0344caf5", "done_ts": None,
         "submitted_ts": NOW - 12.5,
         "history": ["submitted S1 -> S4",
                     "leg1 -> S1 as ft-0344caf5 on f1"]},
        {"task_id": "ft-99887766", "from": "S5", "to": "S2",
         "state": "QUEUED", "assignee": None, "order_id": None,
         "done_ts": None, "submitted_ts": NOW - 3.0,
         "history": ["submitted S5 -> S2",
                     "requeued to head: CONNECTIONBROKEN on f2"]},
        {"task_id": "ft-00110011", "from": "S3", "to": "S7",
         "state": "DONE", "assignee": "f1", "order_id": "ft-77aa11bb",
         "done_ts": NOW - 60.0, "submitted_ts": NOW - 300.0,
         "history": ["arrived S7 - DONE"]},
    ],
    "done_count": 7,
    "queue_len": 1,
    "refused": [{"taskId": "ft-deadbeef",
                 "why": "unknown from station 'S99'"}],
}


def _line(text, starts_with):
    """The one rendered line beginning with that token."""
    hits = [ln for ln in text.splitlines() if ln.startswith(starts_with)]
    assert len(hits) == 1, (starts_with, hits)
    return hits[0]


# ---- what a submission is ----
def test_a_submission_is_the_three_fields_the_manager_reads():
    body = cli.build_submission("S1", "S4")
    assert set(body) == {"taskId", "from", "to"}
    assert (body["from"], body["to"]) == ("S1", "S4")
    assert body["taskId"].startswith("ft-") and len(body["taskId"]) == 11


def test_two_submissions_never_share_a_task_id():
    ids = {cli.build_submission("S1", "S4")["taskId"] for _ in range(200)}
    assert len(ids) == 200


def test_an_operator_may_name_the_task():
    assert cli.build_submission("S1", "S4", "night-shift-7")["taskId"] \
        == "night-shift-7"


@pytest.mark.parametrize("bad", ["", "   ", 7, True])
def test_an_empty_task_id_is_refused_here_not_at_the_manager(bad):
    with pytest.raises(ValueError) as caught:
        cli.build_submission("S1", "S4", bad)
    assert "task-id" in str(caught.value)


@pytest.mark.parametrize("src,dst,role", [
    ("S99", "S4", "FROM"), ("S1", "sink", "TO"),
    ("s1", "S4", "FROM"), ("S1", None, "TO")])
def test_an_unknown_station_is_refused_and_the_real_ones_are_listed(
        src, dst, role):
    with pytest.raises(ValueError) as caught:
        cli.build_submission(src, dst)
    message = str(caught.value)
    assert role in message
    # The list is the stations file's own, not a hand-written copy: a
    # station added there has to show up in this refusal.
    for station in STATIONS:
        assert station in message


def test_a_transport_that_goes_nowhere_is_refused():
    with pytest.raises(ValueError) as caught:
        cli.build_submission("S4", "S4")
    assert "same station" in str(caught.value)


# ---- what the screen says ----
def test_the_screen_carries_every_vehicle_and_every_task():
    text = cli.render(DOC, NOW)
    head = _line(text, "fleet/status")
    assert "manager ONLINE" in head and "queue 1" in head \
        and "done 7" in head and "document age 0.4 s" in head

    f1 = _line(text, "f1")
    assert "ONLINE" in f1 and "AUTOMATIC" in f1 and "ft-0344caf5" in f1
    assert "-3.00, -5.50" in f1 and " 0.3 " in f1

    f2 = _line(text, "f2")
    assert "CONNECTIONBROKEN" in f2 and "LOST" in f2 \
        and "standby" in f2 and "42.0" in f2

    live = _line(text, "ft-1a2b3c4d")
    assert "ASSIGNED_LEG1" in live and "S1" in live and "S4" in live \
        and "f1" in live and "ft-0344caf5" in live and "12.5" in live
    assert "leg1 -> S1 as ft-0344caf5 on f1" in live

    queued = _line(text, "ft-99887766")
    assert "QUEUED" in queued and "3.0" in queued
    # The requeue reason is the answer to the question an operator asks
    # about a task that visited the queue twice, so it is on the row.
    assert "requeued to head: CONNECTIONBROKEN on f2" in queued

    assert "ft-deadbeef" in text and "unknown from station 'S99'" in text


def test_the_columns_are_fixed_width_so_a_watch_does_not_reflow():
    text = cli.render(DOC, NOW)
    lines = text.splitlines()
    header = lines.index(cli._head(cli.VEHICLE_COLS))
    rows = [lines[header], lines[header + 1], lines[header + 2]]
    # Every cell boundary lands on the same column in the header and in
    # both vehicle rows, whatever the values are.
    edge = 0
    for _, width in cli.VEHICLE_COLS[:-1]:
        edge += width + 1
        assert {row[edge - 1] for row in rows} == {" "}, edge


def test_four_vehicles_render_four_rows_the_columns_still_hold():
    """M6.5 put four trucks on the floor; the screen was never told a number.

    `render` walks `sorted(vehicles)` and the widths are fixed, so the
    only things a bigger fleet can break are the count in the header and
    a VEHICLE column too narrow for the ids - both checked here rather
    than assumed. It is the CLI half of "the code is already N-generic".
    """
    doc = dict(DOC, vehicles=dict(DOC["vehicles"], **{
        "f3": {"connection": "ONLINE", "operating_mode": "AUTOMATIC",
               "position": [-8.0, 5.65], "executing_order": None,
               "state_age_s": 0.5, "lost": False, "not_eligible": False},
        "f4": {"connection": "ONLINE", "operating_mode": "MANUAL",
               "position": [8.0, 5.65], "executing_order": None,
               "state_age_s": 0.2, "lost": False, "not_eligible": True},
    }))
    text = cli.render(doc, NOW)
    assert "VEHICLES (4)" in text

    lines = text.splitlines()
    head = lines.index(cli._head(cli.VEHICLE_COLS))
    rows = lines[head + 1:head + 5]
    assert [row.split()[0] for row in rows] == ["f1", "f2", "f3", "f4"]
    # f3 and f4 are readable, not just present.
    assert "-8.00, 5.65" in rows[2] and "AUTOMATIC" in rows[2]
    assert "MANUAL" in rows[3] and "standby" in rows[3]
    # And every cell boundary still lands on the same column in all five.
    edge = 0
    for _, width in cli.VEHICLE_COLS[:-1]:
        edge += width + 1
        assert {line[edge - 1] for line in [lines[head]] + rows} == {" "}, edge


def test_a_value_too_long_for_its_column_is_visibly_cut():
    doc = dict(DOC, tasks=[dict(DOC["tasks"][0],
                                task_id="a-very-long-operator-task-id")])
    row = _line(cli.render(doc, NOW), "a-very-long")
    assert row.startswith("a-very-long~")


def test_the_task_age_is_measured_against_the_readers_own_clock():
    later = cli.render(DOC, NOW + 100.0)
    assert "112.5" in _line(later, "ft-1a2b3c4d")
    # ...and the VEHICLE age is not: that number was computed by the
    # manager when the document was built, and this tool does not do
    # arithmetic on somebody else's clock. It says the document's age
    # instead, which is what makes the row readable.
    assert "42.0" in _line(later, "f2")


def test_a_document_nobody_is_updating_reads_as_stale():
    fresh = cli.render(DOC, NOW)
    assert "STALE" not in fresh
    stale = cli.render(DOC, NOW + 612.0)
    assert "STALE" in stale and "612.4" in stale
    assert "older again" in stale


def test_a_manager_that_said_goodbye_says_so():
    text = cli.render(dict(DOC, manager="OFFLINE"), NOW)
    assert "OFFLINE" in text and "nothing is assigning work" in text


def test_an_empty_fleet_renders_the_two_things_worth_saying():
    text = cli.render({"ts": NOW, "manager": "ONLINE", "vehicles": {},
                       "tasks": [], "queue_len": 0, "done_count": 0,
                       "refused": []}, NOW)
    assert "no truck has published on this broker" in text
    # The no-journal restart, said where the operator will look for it.
    assert "resubmit" in text


@pytest.mark.parametrize("doc", [
    {}, {"ts": "not a number"}, {"vehicles": []}, {"tasks": {}},
    {"vehicles": {"f1": None}}, {"tasks": [None, 7]},
    {"vehicles": {"f1": {"position": [1.0]}}},
    {"vehicles": {"f1": {"position": "here", "state_age_s": "old"}}},
    {"tasks": [{"submitted_ts": None, "history": []}]},
    {"refused": [None, {"taskId": None}]}])
def test_a_malformed_document_still_renders(doc):
    """The renderer is the LAST thing between the operator and the
    fleet, and a traceback there is a screen that says nothing at all.
    Every field is read defensively for that reason."""
    text = cli.render(doc, NOW)
    assert "fleet/status" in text and "VEHICLES" in text


# ---- the liveness reading, which is what makes submit honest ----
def test_no_retained_document_means_nobody_took_the_submission():
    assert "no fleet manager has ever published" \
        in cli._liveness(None, NOW)


def test_a_retained_document_from_a_dead_manager_is_not_liveness():
    old = json.dumps(dict(DOC, ts=NOW - 600.0)).encode()
    assert "not running" in cli._liveness(old, NOW)
    assert cli._liveness(json.dumps(DOC).encode(), NOW) is None
    assert "OFFLINE" in cli._liveness(
        json.dumps(dict(DOC, manager="OFFLINE")).encode(), NOW)
    assert "readable JSON" in cli._liveness(b"{not json", NOW)


# ---- the floor (M6.4) ----
# The TRAFFIC section is how an operator tells a truck that is WAITING
# from a truck that is broken: a held-back vehicle is standing at the
# end of its base on purpose, and the element it wants is named beside
# it. The strings are the manager's own - a frozenset of coordinate
# pairs is neither JSON nor a sentence - and this tool only lays them
# out.
TRAFFIC = {
    "enabled": True,
    "holds": {"f1": ["(-3.0,-5.5)"],
              "f2": ["(0.0,-5.5)", "(0.0,-5.5)-(3.0,-5.5)", "(3.0,-5.5)"],
              "parked:f3": ["(-6.0,-5.5)"]},
    "waiting": {"f1": "(0.0,-5.5)"},
    "yielded": ["f1"],
    "bases": {"ft-1a2b3c4d": [1, 4]},
    "stuck": {"f4": "cannot start leg1 of ft-99887766 to S5 - the route "
                    "is taken"},
    "yields": [{"vehicle": "f1", "with": ["f2"], "freed": 2,
                "task": "ft-1a2b3c4d", "ts": NOW}],
    "blocked": [],
    "aside": [],
}


def test_the_screen_shows_who_holds_what_and_who_is_waiting():
    text = cli.render(dict(DOC, traffic=TRAFFIC), NOW)
    assert "TRAFFIC (on)" in text
    holds = _line(text, "  f2         holds")
    assert "(0.0,-5.5)" in holds and "(0.0,-5.5)-(3.0,-5.5)" in holds
    waits = _line(text, "  f1         WAITS")
    assert "(0.0,-5.5)" in waits and "(yielded)" in waits
    assert "parked:f3  holds  (-6.0,-5.5)" in text
    assert "base 1 released + 4 horizon" in _line(text, "  ft-1a2b3c4d")
    assert "gave way: f1 (ft-1a2b3c4d) to f2" in text
    # A truck can be STUCK while holding and waiting for nothing: the
    # fleet hands the whole prefix back rather than sit in the wait-for
    # graph with no task, so the sentence is all the operator gets - and
    # a blank row would read as a fleet that had forgotten the truck.
    stuck = _line(text, "  f4         STUCK")
    assert "cannot start leg1 of ft-99887766 to S5" in stuck
    assert "f4" not in TRAFFIC["holds"] and "f4" not in TRAFFIC["waiting"]


def test_a_deadlock_the_fleet_cannot_break_is_shouted_not_hidden():
    doc = dict(DOC, traffic=dict(TRAFFIC, blocked=[
        {"vehicles": ["f1", "f2"], "task": "ft-1a2b3c4d", "ts": NOW,
         "why": "swap deadlock f1 <-> f2 - a vehicle has to be moved"}]))
    text = cli.render(doc, NOW)
    assert "** BLOCKED: swap deadlock f1 <-> f2 - a vehicle has to be " \
        "moved **" in text


def test_a_truck_the_fleet_moved_is_named_and_not_a_mystery_drive():
    """The one order in this system with no task behind it.

    A step-aside carries no taskId, no base and no assignment, so
    without its own row an operator watching a truck leave the node it
    had been standing on for a minute would find nothing on the screen
    that explains it. The row names who it was moved for, which is the
    question that would otherwise be asked out loud.
    """
    doc = dict(DOC, traffic=dict(TRAFFIC, aside=[
        {"vehicle": "f3", "from": "(0.0,-5.5)", "to": "(0.0,5.7)",
         "for": ["f2"], "task": "ft-1a2b3c4d", "state": "done", "ts": NOW}]))
    text = cli.render(doc, NOW)
    assert "step aside: f3 (0.0,-5.5) -> (0.0,5.7) to clear f2" in text
    assert "(done)" not in text

    moving = dict(DOC, traffic=dict(TRAFFIC, aside=[
        {"vehicle": "f3", "from": "(0.0,-5.5)", "to": "(0.0,5.7)",
         "for": ["f2"], "task": "ft-1a2b3c4d", "state": "cancelling",
         "ts": NOW}]))
    assert "(cancelling)" in _line(cli.render(moving, NOW), "  step aside")


def test_a_fleet_running_without_traffic_says_so_on_the_screen():
    """--no-traffic is the M6.3 manager, and an operator reading a
    screen that simply showed an empty floor would think the fleet was
    deconflicting when nothing was."""
    text = cli.render(dict(DOC, traffic={
        "enabled": False, "holds": {}, "waiting": {}, "yielded": [],
        "bases": {}, "yields": [], "blocked": []}), NOW)
    assert "TRAFFIC (OFF - --no-traffic" in text
    assert "holds" not in text


def test_an_empty_floor_and_a_pre_m6_4_document_are_different_answers():
    """A document with no `traffic` block was written by a manager that
    had no floor to report, and printing "(none)" for it would claim an
    empty hall rather than an old document."""
    empty = cli.render(dict(DOC, traffic={
        "enabled": True, "holds": {}, "waiting": {}, "yielded": [],
        "bases": {}, "stuck": {}, "yields": [], "blocked": []}), NOW)
    assert "nothing reserved" in empty
    assert "TRAFFIC" not in cli.render(DOC, NOW)
    for junk in (None, [], "on", 7):
        assert cli.traffic_lines(dict(DOC, traffic=junk)) == []


def test_demo_plan_is_deterministic_and_well_formed():
    a = cli.demo_plan(seed=7, count=25, min_len_m=15.0)
    b = cli.demo_plan(seed=7, count=25, min_len_m=15.0)
    assert [(t["from"], t["to"]) for t in a] == \
           [(t["from"], t["to"]) for t in b]
    assert len(a) == 25
    assert len({t["taskId"] for t in a}) == 25
    for body in a:
        assert body["from"] != body["to"]
        assert set(body) == {"taskId", "from", "to"}


def test_demo_dry_run_prints_the_plan_and_needs_no_broker(capsys):
    rc = cli.main(["demo", "--seed", "7", "--count", "5",
                   "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 5
    for line in out:
        assert "->" in line


def test_demo_refuses_a_non_positive_in_flight():
    assert cli.main(["demo", "--in-flight", "0", "--dry-run"]) == 2
