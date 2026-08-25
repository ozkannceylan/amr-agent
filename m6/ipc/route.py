"""route.py - the waypoint graph and the router. Pure, no ROS.

THE GRAPH IS THE AISLE CENTRELINES AND NOTHING ELSE. A route that
exists in this graph therefore drives aisle middles by construction -
the reason the owner chose a fixed graph over grid planning.

THE FLOOR HAS TWO ROAD CLASSES AND THE GRAPH KNOWS ABOUT NEITHER.
Speed is follower.target_speed's job, decided from what the scanners
see. What the graph does is put the truck on a centreline, and the
centrelines are drawn so a highway gives a scanner more than
FIELD_SLOW_M (3.30 m) and a pick aisle gives it less. test_route.py
asserts both, which is what keeps the two files honest about each
other.

  RING   a closed loop, x = +-20.00 and y = +-10.00, 120.00 m round.
         EVERY STATION IS ENTERED OFF IT. The bays face the ring
         because the ring is 8.00 m wide and the pick aisle is 5.00,
         and a 5.00 m corridor is not enough for this vehicle to line
         up a 4.00 m bay in (stations.py has the measurement).
  SPINE  x = 0.00 from y = -10.00 to +10.00, joining the ring's two
         long legs through the middle of the block area
  PICK   y = 0.00 from x = -20.00 to +20.00. A shortcut and not an
         address: it carries no station, and it is the one corridor
         narrow enough that follower.target_speed creeps down it.

THE NORTH LEG CARRIES THE SPAWN NODES. -17, -10, +10 and +17 are the
four poses status_contract.VEHICLES declares - the only x-positions on
that leg that are not a bay spur foot. They are nodes because
nearest_node and floor._standing_from both snap a pose to the nearest
node, and four trucks whose nearest node is the same node are four
trucks the traffic ledger will hand one piece of floor to at startup.

EVERY STATION HAS EXACTLY ONE SPUR and it is at least 2.50 m long. See
stations.py for why a shorter one cannot be arrived at.
"""
import heapq
import math

from stations import STATIONS

RING_X = (-20.0, 20.0)          # the two N-S ring legs
RING_Y = (-10.0, 10.0)          # the two E-W ring legs
SPINE_X = 0.0
PICK_Y = 0.0

# ONE NODE LIST FOR BOTH RING LEGS. Every station spur now lands on a
# ring leg - the eight pick bays open onto the block edge and the four
# annex bays onto the wall side - so the two legs carry the same twelve
# x-positions and the graph is symmetric north to south. The annex bays
# moved to +-17 / +-10 for exactly this: at their old +-14 / +-6 the
# south leg would have carried junctions 1.00 m apart.
#   +-13, +-7   the eight pick-bay spur feet
#   +-17, +-10  the four annex spur feet, and the four spawn poses
#   +-20, 0     the ring corners and the spine junction
#   +-3.5       NOT AN ADDRESS, A PLACE TO STAND. Without them the gap
#               from +-7 to the spine junction is 7.00 m, and
#               floor.ASIDE_MAX_M is 5.00: a truck stepped aside once
#               has nowhere to go a second time and the fleet correctly
#               reports UNRESOLVABLE for ever. Measured 2026-08-23 on
#               the staged swap - the step-aside fired, the deadlock
#               re-formed one node east, and there was no third node
#               inside the bound. With these the widest gap on either
#               leg is 4.00 m.
LEG_X = (-20.0, -17.0, -13.0, -10.0, -7.0, -3.5, 0.0, 3.5,
         7.0, 10.0, 13.0, 17.0, 20.0)
# THE PICK AISLE CARRIES NO STATION AT ALL NOW, so it needs only the
# junctions that make it a through route. It is the one creep corridor
# and it is a SHORTCUT, not an address.
PICK_X = (-20.0, -10.0, 0.0, 10.0, 20.0)
# Node y-positions along each N-S run (the ring legs and the spine).
LEG_Y = (-10.0, 0.0, 10.0)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _run(points):
    """Consecutive pairs of a sorted run, for linking."""
    ordered = sorted(points)
    return zip(ordered, ordered[1:])


def build_graph():
    """Adjacency {node: set(node)}; nodes are (x, y) tuples."""
    graph = {}

    def link(a, b):
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)

    for y in RING_Y:
        for a, b in _run(LEG_X):
            link((a, y), (b, y))
    for a, b in _run(PICK_X):
        link((a, PICK_Y), (b, PICK_Y))
    for x in RING_X + (SPINE_X,):
        for a, b in _run(LEG_Y):
            link((x, a), (x, b))
    # THE SPUR FOOT IS ON THE RING LEG THE BAY OPENS ONTO, and the sign
    # of the station's y is what says which. A bay in the north row
    # opens NORTH; one in the south row opens SOUTH; the annex opens
    # north onto the same south leg. Nothing lands on the pick aisle.
    for s in STATIONS.values():
        link((s["x"], s["y"]), (s["x"], 10.0 if s["y"] > 0 else -10.0))
    return graph


def dijkstra(graph, start, goal):
    """Shortest node path start->goal, or None. Plain heap Dijkstra."""
    if start not in graph or goal not in graph:
        return None
    best, queue = {start: 0.0}, [(0.0, start, [start])]
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node == goal:
            return path
        if cost > best.get(node, math.inf):
            continue
        for nbr in graph[node]:
            c = cost + _dist(node, nbr)
            if c < best.get(nbr, math.inf):
                best[nbr] = c
                heapq.heappush(queue, (c, nbr, path + [nbr]))
    return None


def nearest_node(nodes, xy):
    return min(nodes, key=lambda n: _dist(n, xy))


def plan_route(pose_xy, station_id, avoid=()):
    """[pose_xy, entry node, ..., station point], or None if unknown.

    The pose is prepended so the follower's first segment starts under
    the truck instead of snapping it sideways onto the graph.

    `avoid` (M6 item 5c) is a collection of graph nodes to plan as if
    they were not there - the fleet closes a node for a while when a
    vehicle reports a physical body on it (nav's BLOCKED), and a new
    leg must go round rather than be granted floor nobody can drive.
    The nodes leave the graph entirely, edges and all; a goal that is
    itself avoided therefore has no route, and None is the honest
    answer the callers already survive. The default is the empty tuple,
    so every existing caller plans on the whole floor unchanged.
    """
    station = STATIONS.get(station_id)
    if station is None:
        return None
    graph = build_graph()
    if avoid:
        shut = {tuple(n) for n in avoid}
        graph = {n: [m for m in nbrs if m not in shut]
                 for n, nbrs in graph.items() if n not in shut}
        if not graph:
            return None
    goal = (station["x"], station["y"])
    if goal not in graph:
        return None
    path = dijkstra(graph, nearest_node(graph, pose_xy), goal)
    if path is None:
        return None
    poly = [tuple(pose_xy)] + path
    # Entering via a node the truck already stands past would command a
    # U-turn onto the node; drop it when the pose is nearer the second.
    if len(poly) > 2 and _dist(poly[0], poly[2]) < _dist(poly[1], poly[2]):
        poly.pop(1)
    return poly
