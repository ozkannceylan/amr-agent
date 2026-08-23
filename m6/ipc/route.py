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

  RING   a closed loop, x = +-20.00 and y = +-10.00, 120.00 m round
  SPINE  x = 0.00 from y = -10.00 to +10.00, joining the ring's two
         long legs through the middle of the block area
  PICK   y = 0.00 from x = -20.00 to +20.00, the one creep aisle

THE NORTH LEG CARRIES THE SPAWN NODES. -12, -6, +6 and +12 are the four
poses status_contract.VEHICLES declares. They are nodes because
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

# Node x-positions along each E-W run.
NORTH_X = (-20.0, -12.0, -6.0, 0.0, 6.0, 12.0, 20.0)   # spawns at +-12, +-6
SOUTH_X = (-20.0, -14.0, -6.0, 0.0, 6.0, 14.0, 20.0)   # annex spur feet
PICK_X = (-20.0, -13.0, -7.0, 0.0, 7.0, 13.0, 20.0)    # pick spur feet
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

    for a, b in _run(NORTH_X):
        link((a, 10.0), (b, 10.0))
    for a, b in _run(SOUTH_X):
        link((a, -10.0), (b, -10.0))
    for a, b in _run(PICK_X):
        link((a, PICK_Y), (b, PICK_Y))
    for x in RING_X + (SPINE_X,):
        for a, b in _run(LEG_Y):
            link((x, a), (x, b))
    # THE SPUR FOOT IS ON THE RUN THE STATION FACES, never the nearer
    # one by arithmetic: a pick bay opens onto the pick aisle even
    # though the ring is not much further, and a route that entered a
    # bay from the ring would drive through a rack to do it.
    for s in STATIONS.values():
        foot_y = PICK_Y if abs(s["y"]) < 10.0 else -10.0
        link((s["x"], s["y"]), (s["x"], foot_y))
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


def plan_route(pose_xy, station_id):
    """[pose_xy, entry node, ..., station point], or None if unknown.

    The pose is prepended so the follower's first segment starts under
    the truck instead of snapping it sideways onto the graph.
    """
    station = STATIONS.get(station_id)
    if station is None:
        return None
    graph = build_graph()
    goal = (station["x"], station["y"])
    path = dijkstra(graph, nearest_node(graph, pose_xy), goal)
    if path is None:
        return None
    poly = [tuple(pose_xy)] + path
    # Entering via a node the truck already stands past would command a
    # U-turn onto the node; drop it when the pose is nearer the second.
    if len(poly) > 2 and _dist(poly[0], poly[2]) < _dist(poly[1], poly[2]):
        poly.pop(1)
    return poly
