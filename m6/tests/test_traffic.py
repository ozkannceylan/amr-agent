"""traffic.py - the floor's ledger. Pure: no MQTT, no ROS, no clock.

Reservation is PROCESS deconfliction. It is not an anti-collision
system and these tests assert nothing about safety: the scanners, the
F-model and the onboard guards are what stop a truck.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import traffic as tr  # noqa: E402

A, B, C, D = (0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)


def test_an_edge_is_the_same_floor_in_both_directions():
    assert tr.edge(A, B) == tr.edge(B, A)


def test_route_elements_interleave_nodes_and_edges_in_travel_order():
    assert tr.route_elements([A, B, C]) == [
        A, tr.edge(A, B), B, tr.edge(B, C), C]


def test_a_free_route_is_granted_whole():
    r = tr.Reservations()
    want = tr.route_elements([A, B, C])
    assert r.hold("f1", want) == want
    assert r.waiting_on("f1") is None


def test_a_taken_element_truncates_the_grant_and_records_the_wait():
    r = tr.Reservations()
    r.hold("f2", [C])
    want = tr.route_elements([A, B, C])
    got = r.hold("f1", want)
    assert got == [A, tr.edge(A, B), B]          # stops before C
    assert r.waiting_on("f1") == C
    assert r.owner_of(C) == "f2"


def test_a_grant_never_has_a_hole():
    r = tr.Reservations()
    r.hold("f2", [B])
    got = r.hold("f1", tr.route_elements([A, B, C]))
    assert got == [A]                             # not [A, ..., C]


def test_head_on_is_caught_by_the_undirected_edge():
    r = tr.Reservations()
    r.hold("f1", tr.route_elements([A, B, C]))
    got = r.hold("f2", tr.route_elements([C, B, A]))
    assert got == []                              # C is f1's already
    assert r.waiting_on("f2") == C


def test_release_through_frees_the_past_and_keeps_the_present():
    r = tr.Reservations()
    r.hold("f1", tr.route_elements([A, B, C]))
    r.release_through("f1", B)
    assert r.owner_of(A) is None
    assert r.owner_of(tr.edge(A, B)) is None
    assert r.owner_of(B) == "f1"
    assert r.owner_of(tr.edge(B, C)) == "f1"


def test_release_all_can_keep_the_node_under_the_truck():
    r = tr.Reservations()
    r.hold("f1", tr.route_elements([A, B, C]))
    r.release_all("f1", keep=B)
    assert r.owner_of(B) == "f1" and r.owner_of(C) is None


def test_no_cycle_when_only_one_waits():
    r = tr.Reservations()
    r.hold("f1", [A, B])
    r.hold("f2", [B])                             # f2 waits on f1
    assert r.find_cycle() is None


def test_a_mutual_wait_is_a_cycle_and_the_youngest_yields():
    # f1 stands at A reaching for C; f2 stands at D reaching back for B.
    # Each holds what the other's next step needs. Yielding frees the
    # REACHED-FOR elements, not the ground under the yielder - which is
    # why the oldest can then move and the cycle is genuinely broken.
    r = tr.Reservations()
    r.set_standing("f1", A)
    r.set_standing("f2", D)
    r.hold("f1", tr.route_elements([A, B]))       # A, edge(A,B), B
    r.hold("f2", tr.route_elements([D, C]))       # D, edge(C,D), C
    assert r.hold("f1", tr.route_elements([A, B, C])) == \
        tr.route_elements([A, B])                 # C is f2's
    assert r.hold("f2", tr.route_elements([D, C, B])) == \
        tr.route_elements([D, C])                 # B is f1's
    assert set(r.find_cycle()) == {"f1", "f2"}
    loser = r.resolve_deadlock({"f1": 100.0, "f2": 200.0})
    assert loser == "f2"                          # younger task yields
    assert r.yielded("f2") is True
    assert r.owner_of(D) == "f2"                  # still standing there
    assert r.owner_of(C) is None                  # the reach is released
    assert r.find_cycle() is None
    assert r.hold("f1", tr.route_elements([A, B, C])) == \
        tr.route_elements([A, B, C])              # the oldest may move


def test_a_yielded_vehicle_holds_again_once_the_corridor_drains():
    r = tr.Reservations()
    r.set_standing("f1", A)
    r.set_standing("f2", D)
    r.hold("f1", tr.route_elements([A, B]))
    r.hold("f2", tr.route_elements([D, C]))
    r.hold("f1", tr.route_elements([A, B, C]))
    r.hold("f2", tr.route_elements([D, C, B]))
    assert r.resolve_deadlock({"f1": 100.0, "f2": 200.0}) == "f2"
    r.release_all("f1")                # f1 finished and left the aisle
    r.clear_yield("f2")
    assert r.yielded("f2") is False
    assert r.hold("f2", tr.route_elements([D, C, B, A])) == \
        tr.route_elements([D, C, B, A])           # the way is open now


# ---- what is STORED is travel order (M6.5) ----
# release_through frees by POSITION in the held list, so that list has to
# mean "in the direction this vehicle is driving". A vehicle that turns
# round - a truck leaving the station spur it drove into - asks for the
# same two elements in the opposite order, and hold() has to re-seat them
# rather than leave them where the previous leg put them.


def test_a_reversed_re_hold_re_seats_what_the_vehicle_already_owns():
    r = tr.Reservations()
    r.hold("f1", tr.route_elements([A, B]))
    assert r.held_by("f1") == [A, tr.edge(A, B), B]

    # The next leg starts at B and drives back through A to C.
    want = tr.route_elements([B, A, C])
    assert r.hold("f1", want) == want
    assert r.held_by("f1") == want, (
        "the ledger kept the old leg's order: {}".format(r.held_by("f1")))


def test_release_through_frees_nothing_ahead_after_a_reversal():
    """THE BUG THIS PINS, measured 2026-08-22 on the manager: leaving the
    old order in place made `held.index(node)` a position on the PREVIOUS
    route, so the first state of the new leg freed the element the truck
    was about to drive onto - and a second vehicle was handed floor the
    first still had as released base, with no cycle to detect."""
    r = tr.Reservations()
    r.hold("f1", tr.route_elements([A, B]))
    r.hold("f1", tr.route_elements([B, A, C]))
    r.release_through("f1", B)                 # still standing on B
    assert r.owner_of(A) == "f1", "the floor ahead of the truck was freed"
    assert r.held_by("f1") == tr.route_elements([B, A, C])

    r.release_through("f1", A)                 # ...now it has moved on
    assert r.owner_of(B) is None
    assert r.held_by("f1") == [A, tr.edge(A, C), C]


def test_a_vehicle_with_no_leg_can_be_told_it_waits_for_nothing():
    """A truck with no task has no age, so wait-die would pick it as the
    youngest in any cycle it appeared in and free the ground under it.
    release_all cleared the wait as a side effect; a manager that re-holds
    instead needs to say it."""
    r = tr.Reservations()
    r.hold("f2", [B])
    r.hold("f1", tr.route_elements([A, B]))
    assert r.waiting_on("f1") == B
    r.clear_wait("f1")
    assert r.waiting_on("f1") is None
    assert r.find_cycle() is None
    assert r.owner_of(A) == "f1", "clearing a wait must not free floor"
