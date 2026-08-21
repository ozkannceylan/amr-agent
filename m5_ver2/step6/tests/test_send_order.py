"""send_order's pure order builder against the vda_orders validator.

main() needs a broker and a truck, so the builder is the part a suite can
hold - and it is the part that matters, because what it emits is what the
vehicle's own door (vda_orders.validate_order) either takes or refuses.
The hand-written polyline pins the SHAPE; the sweep pins it against real
plan_route output from all over the floor, which is the only input this
tool ever actually gets.
"""
import os
import sys

import pytest

# send_order imports paho at module level and Windows has no paho, so the
# import must be asked for before the module is reached, not after.
pytest.importorskip("paho.mqtt.client")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "tools")))

import route                                        # noqa: E402
import send_order as so                             # noqa: E402
import vda_orders as vo                             # noqa: E402
from stations import STATIONS                       # noqa: E402


def test_built_orders_validate_and_route():
    poly = [(-3.0, -5.5), (0.0, -5.5), (0.0, 5.65), (6.0, -8.0)]
    msg = so.build_order("o-t1", poly, "S4", 0.25)
    assert vo.validate_order(msg) == ""
    pts, arrive, rel, hor = vo.released_route(msg)
    assert pts == [(-3.0, -5.5), (0.0, -5.5), (0.0, 5.65), (6.0, -8.0)]
    assert arrive == 0.25 and hor == []
    assert rel[-1]["nodeId"] == "S4"
    assert rel[0]["nodeId"] == "wp1"


def test_every_planned_route_builds_an_order_the_vehicle_accepts():
    """The tool's real input is plan_route's output minus the pose, so
    that is what the shape has to survive: every station, from a coarse
    grid of the whole hall. Includes the poses that plan a SINGLE node -
    a truck already standing on its goal's aisle node - which is a legal
    M1 order (edges 'empty for single-node order') and drivable, because
    the vehicle prepends its own pose before handing nav the polyline.
    """
    poses = [(x / 2.0, y / 2.0)
             for x in range(-28, 29, 3) for y in range(-18, 19, 3)]
    singles = 0
    for sid, station in STATIONS.items():
        for pose in poses:
            poly = route.plan_route(pose, sid)
            assert poly is not None, (sid, pose)
            msg = so.build_order("o-" + sid, poly[1:], sid,
                                 station["arrive_m"])
            assert vo.validate_order(msg) == "", (sid, pose)
            pts, arrive, rel, hor = vo.released_route(msg)
            assert pts == [tuple(p) for p in poly[1:]], (sid, pose)
            assert arrive == station["arrive_m"]
            assert rel[-1]["nodeId"] == sid and hor == []
            assert len(msg["edges"]) == len(rel) - 1
            singles += len(rel) == 1
    assert singles, "no single-node route in the sweep - S1 and S5 sit " \
                    "on their aisle and a pose beside one plans exactly " \
                    "that, so the zero-edge order went untested"


def test_only_the_station_node_carries_an_arrival_radius():
    """arrive_m is the STATION's spur geometry (stations.py's whole
    point), not a waypoint tolerance. A corner that wore it would let
    Progress tick off a node the truck merely passed within 0.8 m of
    while still driving elsewhere; the waypoints stay silent so Progress
    applies DEFAULT_DEV_M, which is its own number to change.
    """
    msg = so.build_order("o-t2", [(0.0, -5.5), (0.0, 5.65), (8.0, 6.5)],
                         "S7", 0.80)
    devs = [n["nodePosition"].get("allowedDeviationXY")
            for n in msg["nodes"]]
    assert devs == [None, None, 0.80]
    assert [n["nodeId"] for n in msg["nodes"]] == ["wp1", "wp2", "S7"]
    assert vo.validate_order(msg) == ""


def test_the_edges_run_between_the_nodes_they_name():
    """validate_order refuses an edge that does not join its neighbours,
    so this only has to prove the builder fills endNodeId at all - the
    empty string it starts each edge with is a real failure mode.
    """
    msg = so.build_order("o-t3", [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
                         "S1", 0.25)
    assert [(e["edgeId"], e["startNodeId"], e["endNodeId"])
            for e in msg["edges"]] == [("e0", "wp1", "wp2"),
                                       ("e1", "wp2", "S1")]
    assert [e["sequenceId"] for e in msg["edges"]] == [1, 3]
    assert vo.validate_order(msg) == ""
