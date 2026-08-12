"""route.py's graph and router. Pure geometry, no ROS."""
import math

import route
import stations


def _connected(graph):
    seen, stack = set(), [next(iter(graph))]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(graph[n])
    return seen


def test_graph_is_one_component():
    graph = route.build_graph()
    assert _connected(graph) == set(graph)


def test_every_edge_is_axis_parallel():
    # A diagonal edge is a typo cutting through racking.
    graph = route.build_graph()
    for a, nbrs in graph.items():
        for b in nbrs:
            assert a[0] == b[0] or a[1] == b[1], (a, b)


def test_edges_are_symmetric():
    graph = route.build_graph()
    for a, nbrs in graph.items():
        for b in nbrs:
            assert a in graph[b]


def test_every_station_point_is_a_graph_node():
    graph = route.build_graph()
    for sid, s in stations.STATIONS.items():
        assert (s["x"], s["y"]) in graph, sid


def test_every_station_reachable_from_every_station():
    graph = route.build_graph()
    points = [(s["x"], s["y"]) for s in stations.STATIONS.values()]
    for a in points:
        for b in points:
            assert route.dijkstra(graph, a, b) is not None


def test_dijkstra_takes_the_short_way_home():
    # S1 HOME (-3,-5.5) to S10 PICK-B-S (-6,-1.6): straight west along the
    # dock aisle then up the spur - never via the end aisles.
    graph = route.build_graph()
    path = route.dijkstra(graph, (-3.0, -5.5), (-6.0, -1.6))
    assert path == [(-3.0, -5.5), (-6.0, -5.5), (-6.0, -1.6)]


def test_plan_route_starts_at_the_pose_and_ends_at_the_station():
    poly = route.plan_route((-2.7, -5.3), "S7")
    assert poly[0] == (-2.7, -5.3)
    assert poly[-1] == (8.0, 7.0)
    assert len(poly) >= 3


def test_plan_route_refuses_an_unknown_station():
    assert route.plan_route((0.0, 0.0), "S99") is None


def test_nodes_and_stations_keep_clear_of_the_racking():
    # 0.52 m plan half-envelope plus margin. Spur endpoints are the
    # closest approaches by design; they still clear by >= 0.6 m.
    graph = route.build_graph()
    for (x, y) in graph:
        for name, xmin, xmax, ymin, ymax in stations.OBSTACLES:
            dx = max(xmin - x, 0.0, x - xmax)
            dy = max(ymin - y, 0.0, y - ymax)
            assert math.hypot(dx, dy) >= 0.6, ((x, y), name)


def test_ten_stations_with_unique_names():
    assert len(stations.STATIONS) == 10
    names = [s["name"] for s in stations.STATIONS.values()]
    assert len(set(names)) == 10
