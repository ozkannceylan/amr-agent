"""order_builder.py - the fleet's own VDA 5050 order factory. Pure.

One leg of a transport is one full-route order: the manager asks for a
route to a station and gets back a message the vehicle's door
(vda_orders.validate_order) accepts, or None. No MQTT, no clock, no ROS -
what leaves here is a dict, and only fleet_manager puts it on a wire.

THE PLANNER IS THE VEHICLE'S OWN. route.plan_route is the same router
the on-board HMI path uses, reading the same graph from ipc/route.py and
the same stations from ipc/stations.py. The route the fleet sends is
therefore the route the vehicle would have planned; master control never
invents a second planner, and there is exactly one home for the graph.

THE POSE IS NOT A NODE. plan_route prepends the start point so the
follower's first segment starts under the truck, but an order must not
name that as a waypoint: vda_agent prepends the vehicle's CURRENT pose
again before it hands nav the polyline, and the start this was planned
from is already stale by then. So the order carries poly[1:] - wp1..wpN-1
and the station itself, last, wearing the station's arrival radius.

M6.4 GAVE IT A HORIZON. `released_count` splits the same node list
into the VDA 5050 base the fleet has reserved and the horizon it has
not, and `update_id` stamps orderUpdateId so the base can be extended
later with the same nodes. Nothing else about the order moves: the
reservation decision belongs to floor.py and the ledger, and this
file only ever writes down what it was told.

THIS IS send_order.build_order's LINEAGE, OWNED FLEET-SIDE. tools/
send_order.py is frozen as a superseded low-level probe (its own header
says so), and the duplication between these two node loops is accepted
deliberately: a frozen file is not a dependency to import through. The
fleet layer may not reach into tools/, and this builder is now the one
that has to keep up with the order shape. If the M1 subset changes, this
file changes and send_order stays wrong on purpose.

NO TWO NODES LAND ON THE SAME POINT, so nothing filters for it: graph
nodes are dict keys and cannot share coordinates, dijkstra never repeats
one, and the pose-drop only ever removes a point. A leg-2 order does
start ON the truck (the pickup station is a node and the truck is parked
at it), which is a zero-length FIRST segment for the follower, not a
duplicate node - and follower._project and follower.advance both guard a
zero-length segment explicitly.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))
import route                                        # noqa: E402
from stations import STATIONS                       # noqa: E402


def leg_points(start_xy, station_id):
    """The graph points one leg's order names, in travel order, or None.

    THE FLEET RESERVES WHAT THE ORDER NAMES, so the traffic ledger and
    the order must be planned from one list rather than two: this is
    that list, and build_leg_order below is its only other caller. The
    pose is already dropped (see the module note), so every point here
    is a graph node the truck will actually stand on - which is exactly
    what traffic.route_elements wants.
    """
    poly = route.plan_route(start_xy, station_id)
    return None if poly is None else [tuple(p) for p in poly[1:]]


def build_leg_order(order_id, start_xy, station_id, released_count=None,
                    update_id=0):
    """The order for one leg, or None when there is no route.

    None covers both refusals plan_route has - an unknown station id and
    a graph that does not join the two - because the manager's drain loop
    must survive either without dying; it requeues the task instead.

    Interleaved sequenceIds (node 2i, edge 2i+1). Only the station node
    carries allowedDeviationXY, and it is that station's spur geometry
    (stations.py), which says nothing about a corner - the waypoints stay
    silent so vda_orders.Progress applies its own default to them.

    RELEASED_COUNT IS THE BASE, THE REST IS HORIZON. `None` keeps the
    pre-M6.4 behaviour - a leg delivered whole - and is what a fleet with
    traffic switched off still asks for. A number releases the first
    `released_count` nodes and marks everything after them
    `released: false`: the vehicle drives to the end of its base and
    stops there on its own, with no pause action, because that is what
    VDA 5050 already says a base end is. AN EDGE'S released FOLLOWS ITS
    END NODE, never its start - edge i joins node i to node i+1, so it is
    released exactly when node i+1 is, and validate_order refuses any
    other pairing. `released_count` is clamped into 0..len(points); 0 is
    not an order (the door refuses a first node that is horizon) and the
    caller is expected to hold its truck rather than ask for one.

    update_id STAMPS orderUpdateId, and an extension is the SAME order
    id, the same nodes at the same indices and coordinates, one higher
    update id and a longer base - which is precisely what
    vda_orders.accept_order calls 'extend'. Re-building with the same
    (order_id, start_xy, station_id) is what makes that true: the router
    is deterministic, so the nodes cannot drift under the vehicle.

    NO HEADER IS STAMPED HERE. The manager stamps the common M1 header at
    publish, exactly as send_order's main does: headerId counts what went
    out on a topic and timestamp says when, and both are lies if minted
    for an order still being decided about.
    """
    points = leg_points(start_xy, station_id)
    if points is None:
        return None
    cut = len(points) if released_count is None \
        else max(0, min(int(released_count), len(points)))
    arrive_m = STATIONS[station_id]["arrive_m"]
    nodes, edges = [], []
    for i, (x, y) in enumerate(points):
        last = i == len(points) - 1
        node = {"nodeId": station_id if last else "wp{}".format(i + 1),
                "sequenceId": 2 * i, "released": i < cut, "actions": [],
                "nodePosition": {"x": float(x), "y": float(y),
                                 "mapId": "warehouse"}}
        if last:
            node["nodePosition"]["allowedDeviationXY"] = float(arrive_m)
        nodes.append(node)
        if not last:
            # The edge's end node is node i+1, and that is whose release
            # it must copy.
            edges.append({"edgeId": "e{}".format(i),
                          "sequenceId": 2 * i + 1,
                          "released": (i + 1) < cut,
                          "startNodeId": node["nodeId"],
                          "endNodeId": "", "actions": []})
    for edge, node in zip(edges, nodes[1:]):
        edge["endNodeId"] = node["nodeId"]
    return {"orderId": order_id, "orderUpdateId": int(update_id),
            "nodes": nodes, "edges": edges}


def leg2_start(pickup_station_id):
    """The pickup station's (x, y). ValueError on an unknown station id.

    LEG 2 IS PLANNED FROM WHERE LEG 1 ENDED, NOT FROM THE LIVE POSE. Leg
    2 is only built after the vehicle reported ARRIVED at the pickup and
    stood through the dwell, so the truck is at this station by
    definition; planning from its last reported pose would let a metre of
    localisation noise pick a different entry node than the station's own
    spur, and the resulting order would ask a parked truck to leave the
    spur sideways. The station is a graph node; starting from it is exact.

    ValueError, not send_order's SystemExit: a CLI may exit on a typo,
    but this is called inside the manager's drain loop and a task with a
    bad station id must not take the fleet service down with it.
    """
    station = STATIONS.get(pickup_station_id)
    if station is None:
        raise ValueError("unknown station {!r} - known: {}".format(
            pickup_station_id, ", ".join(STATIONS)))
    return (station["x"], station["y"])
