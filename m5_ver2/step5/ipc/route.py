"""route.py - the waypoint graph and the router. Pure, no ROS.

THE GRAPH IS THE AISLE CENTRELINES AND NOTHING ELSE. Nodes sit on the
main aisle (y = 5.65), the dock aisle (y = -5.5), the three connectors
(x = -12.5, 0.0, +12.0) and one short spur per station. A route that
exists in this graph therefore drives aisle middles by construction -
the reason the owner chose a fixed graph over grid planning (spec,
"Owner decisions").

Every station's (x, y) is itself a node, joined to the aisle whose
centreline is nearer. That is why several aisle x-positions repeat
station x-coordinates: the spur must land on a node, not between two.
"""
import heapq
import math

from stations import STATIONS

MAIN_Y, DOCK_Y = 5.65, -5.5
MAIN_X = (-12.5, -8.0, -3.0, 0.0, 3.0, 8.0, 12.0, 13.0)
DOCK_X = (-12.5, -9.8, -7.4, -6.0, -3.0, 0.0, 3.0, 6.0, 8.0, 12.0)
CONNECT_X = (-12.5, 0.0, 12.0)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def build_graph():
    """Adjacency {node: set(node)}; nodes are (x, y) tuples."""
    graph = {}

    def link(a, b):
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)

    for y, xs in ((MAIN_Y, MAIN_X), (DOCK_Y, DOCK_X)):
        run = sorted(xs)
        for a, b in zip(run, run[1:]):
            link((a, y), (b, y))
    for x in CONNECT_X:
        link((x, MAIN_Y), (x, DOCK_Y))
    for s in STATIONS.values():
        aisle_y = MAIN_Y if abs(s["y"] - MAIN_Y) <= abs(s["y"] - DOCK_Y) \
            else DOCK_Y
        if s["y"] != aisle_y:
            link((s["x"], s["y"]), (s["x"], aisle_y))
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
