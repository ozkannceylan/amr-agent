"""order_builder - the fleet's order factory, held against the vehicle's
own door.

What the factory emits is what vda_orders.validate_order either takes or
refuses, so validation is the assertion in nearly every test here and
released_route is asked to hand the polyline back unchanged: an order the
vehicle accepts but reads as a different route would pass a shape test and
still drive somewhere else.

The sweep is the real proof. send_order's suite swept every station from a
grid of the whole hall, which is the input a hand-driven probe gets; the
fleet's input is narrower and completely enumerable - a transport is
station to station, so all 10x9 ordered pairs ARE the input space, and
every one of them is built and validated below.
"""
import itertools
import os
import sys

import pytest

# fleet/ is a plain directory, not a package (m5_ver2/CLAUDE.md), so the
# module is reached by path here rather than in conftest - the suite's
# shared path list is the node dirs only (ipc, hmi, windows), which is
# where route, stations and vda_orders come from.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import route                                        # noqa: E402
import vda_orders as vo                             # noqa: E402
from order_builder import (build_leg_order, leg2_start,   # noqa: E402
                           leg_points)
from stations import STATIONS                       # noqa: E402


def test_a_built_leg_order_is_one_the_vehicle_accepts():
    """Validation, then the round trip: the points the vehicle would read
    back are exactly plan_route's output minus the pose, the arrival
    radius is the station's own, and nothing is horizon - there is no
    stitching in M1, so an order that hid a node behind released=False
    would strand the truck short of the station.
    """
    msg = build_leg_order("ft-deadbeef", (-3.0, -5.5), "S7")
    assert vo.validate_order(msg) == ""
    poly = route.plan_route((-3.0, -5.5), "S7")
    pts, arrive, rel, hor = vo.released_route(msg)
    assert pts == [tuple(p) for p in poly[1:]]
    assert arrive == STATIONS["S7"]["arrive_m"] == 0.80
    assert hor == []
    assert rel[0]["nodeId"] == "wp1" and rel[-1]["nodeId"] == "S7"
    assert len(msg["edges"]) == len(rel) - 1
    assert msg["orderUpdateId"] == 0
    # arrive_m is the STATION's spur geometry, not a waypoint tolerance:
    # a corner wearing it would let Progress tick off a node the truck
    # merely passed near. The waypoints stay silent for DEFAULT_DEV_M.
    devs = [n["nodePosition"].get("allowedDeviationXY")
            for n in msg["nodes"]]
    assert devs == [None] * (len(msg["nodes"]) - 1) + [0.80]


def test_the_builder_stamps_no_header():
    """The manager stamps the VDA header at publish - send_order's main
    does the same, one Counters per topic. A headerId minted here would
    count an order that may never reach the wire, and the header carries
    a timestamp that would then be older than the send.
    """
    msg = build_leg_order("ft-1", (0.0, 0.0), "S1")
    assert set(msg) == {"orderId", "orderUpdateId", "nodes", "edges"}


def test_the_order_id_is_carried_verbatim():
    """The caller owns the id, prefix and all: the manager mints 'ft-'
    ids so a fleet order is legible in a vehicle's state next to a
    hand-sent 'o-' one. A builder that decorated the id would break the
    manager's own match against state.orderId.
    """
    for order_id in ("ft-0011aabb", "o-legacy", "x"):
        msg = build_leg_order(order_id, (0.0, 0.0), "S4")
        assert msg["orderId"] == order_id


def test_leg_two_is_planned_from_where_leg_one_ended():
    """S4 -> S7, the second leg of a transport. leg2_start hands back the
    pickup's own coordinates and the order that follows starts there:
    its first node IS S4, because the station is a graph node and the
    pose plan_route prepends is dropped on top of it.
    """
    s4 = (STATIONS["S4"]["x"], STATIONS["S4"]["y"])
    assert leg2_start("S4") == s4
    msg = build_leg_order("ft-leg2", leg2_start("S4"), "S7")
    poly = route.plan_route(s4, "S7")
    first = msg["nodes"][0]["nodePosition"]
    assert (first["x"], first["y"]) == tuple(poly[1]) == s4
    assert vo.validate_order(msg) == ""


def test_an_unknown_station_is_no_order_and_no_start():
    """Two different refusals for two different callers. The builder
    answers None because the manager's drain loop must survive a bad task
    without dying; leg2_start raises ValueError because there is no
    honest (x, y) to return and a silent (0, 0) would send a truck across
    the hall. SystemExit is send_order's answer - a CLI may exit; the
    manager is a service and may not.
    """
    assert build_leg_order("ft-x", (0.0, 0.0), "S11") is None
    assert build_leg_order("ft-x", (0.0, 0.0), "") is None
    with pytest.raises(ValueError):
        leg2_start("S11")


def test_every_ordered_station_pair_builds_an_order_the_vehicle_accepts():
    """All 90 legs a transport can be. Each is planned from the
    from-station's coordinates, which is exactly how leg 2 is planned and
    close enough to leg 1 (the vehicle stands somewhere on the floor, and
    send_order's grid sweep already pinned that half). Every one must
    validate, round-trip its polyline, end on its station wearing that
    station's radius, and number its waypoints wp1..wpN-1.
    """
    pairs = 0
    for a, b in itertools.permutations(STATIONS, 2):
        start = leg2_start(a)
        msg = build_leg_order("ft-{}{}".format(a, b), start, b)
        assert msg is not None, (a, b)
        assert vo.validate_order(msg) == "", (a, b)
        pts, arrive, rel, hor = vo.released_route(msg)
        poly = route.plan_route(start, b)
        assert pts == [tuple(p) for p in poly[1:]], (a, b)
        assert arrive == STATIONS[b]["arrive_m"], (a, b)
        assert rel[-1]["nodeId"] == b and hor == [], (a, b)
        assert len(msg["edges"]) == len(rel) - 1, (a, b)
        assert [n["nodeId"] for n in rel[:-1]] == [
            "wp{}".format(i + 1) for i in range(len(rel) - 1)], (a, b)
        pairs += 1
    assert pairs == 90


# ---- M6.4: the base/horizon split ----
# The fleet reserves the floor a leg needs and gets back the part it may
# have. What it may have becomes the VDA 5050 BASE and the rest goes out
# as horizon, so the truck drives to the end of what was granted and
# stops there on its own. These tests are about the SHAPE of that order;
# who decides the number is fleet_manager's business, and traffic.py's.


def test_the_points_the_order_names_are_the_points_the_fleet_reserves():
    """One list, not two. The ledger holds graph nodes and the order
    names graph nodes, and a leg whose reservation was planned separately
    from its order would reserve a corridor the truck is not driving."""
    for start, station in (((-3.0, -5.5), "S7"), ((0.0, 0.0), "S1")):
        msg = build_leg_order("ft-p", start, station)
        assert leg_points(start, station) == [
            (n["nodePosition"]["x"], n["nodePosition"]["y"])
            for n in msg["nodes"]]
    assert leg_points((0.0, 0.0), "S11") is None


def test_a_horizon_order_is_one_the_vehicle_accepts():
    """The door is the assertion, as everywhere else in this file: an
    order whose edges disagree with their end nodes is refused by
    validate_order ("edge released must match its end node"), and that
    is the rule the split is easiest to get wrong."""
    for released in range(1, len(leg_points((-3.0, -5.5), "S7")) + 1):
        msg = build_leg_order("ft-h", (-3.0, -5.5), "S7",
                              released_count=released)
        assert vo.validate_order(msg) == "", released


def test_the_released_horizon_split_lands_where_it_was_asked():
    points = leg_points((-3.0, -5.5), "S7")
    msg = build_leg_order("ft-h", (-3.0, -5.5), "S7", released_count=2)
    assert [n["released"] for n in msg["nodes"]] == \
        [True, True] + [False] * (len(points) - 2)
    # Edge i joins node i to node i+1 and copies node i+1: only e0 (wp1
    # to wp2) is inside the base.
    assert [e["released"] for e in msg["edges"]] == \
        [True] + [False] * (len(points) - 2)
    pts, arrive, rel, hor = vo.released_route(msg)
    assert pts == points[:2]
    assert [n["nodeId"] for n in rel] == ["wp1", "wp2"]
    assert [n["nodeId"] for n in hor] == \
        ["wp{}".format(i) for i in range(3, len(points))] + ["S7"]
    # The truck stops at wp2, so the radius it is judged by is wp2's own
    # default and not the station's - the station is still horizon.
    assert arrive == 0.25 != STATIONS["S7"]["arrive_m"]


def test_released_count_none_is_the_leg_delivered_whole():
    """The pre-M6.4 behaviour, unchanged, and what --no-traffic asks
    for."""
    for station in STATIONS:
        whole = build_leg_order("ft-w", (0.0, 0.0), station)
        asked = build_leg_order("ft-w", (0.0, 0.0), station,
                                released_count=len(whole["nodes"]))
        assert whole == asked
        assert all(n["released"] for n in whole["nodes"])
        assert all(e["released"] for e in whole["edges"])


def test_a_released_count_past_the_end_or_below_one_is_clamped():
    """Clamped, not crashed - the manager computes this number from a
    granted prefix and an off-by-one there must not take the fleet's
    drain loop down. A count of 0 is clamped to 0 and the door then
    refuses the order out loud, which is the honest end of that path:
    an order with no base is not an order."""
    points = leg_points((0.0, 0.0), "S4")
    assert build_leg_order("ft-c", (0.0, 0.0), "S4", released_count=99) == \
        build_leg_order("ft-c", (0.0, 0.0), "S4")
    none = build_leg_order("ft-c", (0.0, 0.0), "S4", released_count=0)
    assert [n["released"] for n in none["nodes"]] == [False] * len(points)
    assert vo.validate_order(none) == \
        "no released base - the first node is horizon"


def test_an_extension_is_the_same_order_one_update_higher():
    """Re-built from the same three inputs, a longer base is an order
    vda_orders calls 'extend' rather than a new one: same nodes, same
    ids, same sequenceIds, same coordinates, nothing already driven
    changed."""
    first = build_leg_order("ft-x", (-3.0, -5.5), "S7", released_count=2)
    assert first["orderUpdateId"] == 0
    grown = build_leg_order("ft-x", (-3.0, -5.5), "S7", released_count=4,
                            update_id=1)
    assert grown["orderUpdateId"] == 1
    assert vo.accept_order(grown, first, True, "AUTOMATIC") == ("extend", "")
    whole = build_leg_order("ft-x", (-3.0, -5.5), "S7", update_id=2)
    assert vo.accept_order(whole, grown, True, "AUTOMATIC") == ("extend", "")
    # ...and the nodes never moved under the truck.
    for a, b in zip(first["nodes"], whole["nodes"]):
        assert a["nodeId"] == b["nodeId"]
        assert a["sequenceId"] == b["sequenceId"]
        assert a["nodePosition"]["x"] == b["nodePosition"]["x"]
        assert a["nodePosition"]["y"] == b["nodePosition"]["y"]


def test_the_router_never_revisits_a_node_so_the_ledger_may_key_on_one():
    """THE BOUND ON THE LEDGER'S ELEMENT IDENTITY, pinned here.

    traffic.py names a node by its (x, y) and nothing else, so a route
    that drove through one node twice would collapse the two visits into
    a single reservation - it would look like the truck never left. That
    is safe today for a reason that belongs to the ROUTER, not to the
    ledger: plan_route is a shortest path over a graph whose nodes are
    dict keys, and dijkstra never puts one on a path twice. If route.py
    ever gains a via-point or a re-plan, this test fails first and the
    ledger needs a (node, visit) identity before it ships.
    """
    for a in STATIONS:
        for b in STATIONS:
            if a == b:
                continue
            points = leg_points(leg2_start(a), b)
            assert len(set(points)) == len(points), (a, b)
