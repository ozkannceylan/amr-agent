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
from order_builder import build_leg_order, leg2_start   # noqa: E402
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
