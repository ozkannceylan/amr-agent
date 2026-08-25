"""route.py's graph and router. Pure geometry, no ROS.

THE RULES ARE ASSERTED, NOT THE COORDINATES. A test that pins a node
list is a test that has to be rewritten every time the floor moves; a
test that pins 'every highway centreline clears a safety scanner by
3.30 m' is the reason the floor is drawn the way it is.
"""
import math

import route
import stations

SCANNER_ABEAM_M = 0.46      # follower.py: fork-corner devices at +-0.46
FIELD_SLOW_M = 3.30         # follower.FIELD_SLOW_M
PF_HYST_M = 1.20            # case-1 PF 1.00 + 0.20 hysteresis
MIN_SPUR_M = 2.50


def _connected(graph):
    seen, stack = set(), [next(iter(graph))]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(graph[n])
    return seen


def _clearance(x, y):
    """Nearest obstacle to the point, over all rectangles."""
    best = math.inf
    for _n, xmin, xmax, ymin, ymax in stations.OBSTACLES:
        dx = max(xmin - x, 0.0, x - xmax)
        dy = max(ymin - y, 0.0, y - ymax)
        best = min(best, math.hypot(dx, dy))
    return best


def test_graph_is_one_component():
    graph = route.build_graph()
    assert _connected(graph) == set(graph)


def test_every_edge_is_axis_aligned():
    # A diagonal edge is a typo cutting through racking.
    graph = route.build_graph()
    for a, nbrs in graph.items():
        for b in nbrs:
            assert a[0] == b[0] or a[1] == b[1], (a, b)


def test_edges_are_undirected():
    graph = route.build_graph()
    for a, nbrs in graph.items():
        for b in nbrs:
            assert a in graph[b]


def test_every_station_point_is_a_graph_node():
    graph = route.build_graph()
    for sid, s in stations.STATIONS.items():
        assert (s["x"], s["y"]) in graph, sid


def test_every_station_can_reach_every_station():
    graph = route.build_graph()
    points = [(s["x"], s["y"]) for s in stations.STATIONS.values()]
    for a in points:
        for b in points:
            assert route.dijkstra(graph, a, b) is not None


def test_every_spur_is_long_enough_for_the_tight_radius():
    # A vehicle cannot reach a point inside its own turning circle.
    # Measured 2026-08-13: a 0.85 m spur orbits at 0.643-0.742 m.
    graph = route.build_graph()
    for sid, s in stations.STATIONS.items():
        point = (s["x"], s["y"])
        assert len(graph[point]) == 1, (sid, "a station has ONE spur")
        foot = next(iter(graph[point]))
        assert math.dist(point, foot) >= MIN_SPUR_M, (sid, foot)


def test_highway_centrelines_clear_a_scanner_by_the_field_band():
    # Where this holds the truck runs at CRUISE_MPS. Where it does not,
    # follower.target_speed holds it at the creep ceiling - by design on
    # a pick aisle, by accident nowhere.
    for x in route.RING_X:
        for y in (-10.0, 0.0, 10.0):
            assert _clearance(x, y) - SCANNER_ABEAM_M >= FIELD_SLOW_M, (x, y)
    for y in route.RING_Y:
        for x in route.LEG_X:
            assert _clearance(x, y) - SCANNER_ABEAM_M >= FIELD_SLOW_M, (x, y)
    for y in route.LEG_Y:
        assert _clearance(route.SPINE_X, y) - SCANNER_ABEAM_M >= FIELD_SLOW_M


def test_pick_aisle_centreline_clears_a_scanner_by_the_protective_band():
    # A pick aisle is INSIDE the warning field on purpose and outside the
    # protective one always. Its own two ends sit on the ring legs and
    # are highway, so they are excluded - what is asked here is the run
    # between them.
    inner = [x for x in route.PICK_X if abs(x) < 20.0]
    assert inner, "the pick aisle has no run of its own"
    for x in inner:
        gap = _clearance(x, route.PICK_Y) - SCANNER_ABEAM_M
        assert gap >= PF_HYST_M, (x, gap)
    # ...and at least the middle of it is a creep corridor, which is the
    # whole reason it is 5.00 m and not 8.00.
    assert min(_clearance(x, route.PICK_Y) - SCANNER_ABEAM_M
               for x in inner) < FIELD_SLOW_M


def test_no_station_is_entered_off_the_pick_aisle():
    """REVISION B, AND IT IS THE POINT OF IT. A tricycle cannot line up
    a 4.00 m bay off a 5.00 m corridor: measured 2026-08-23, f1 and f2
    both went in skewed and stopped with the back protective field
    violated at 0.977 m, unrecoverable. Every bay opens onto the 8.00 m
    ring instead, so every spur foot is on a ring leg."""
    graph = route.build_graph()
    for sid, s in stations.STATIONS.items():
        foot = next(iter(graph[(s["x"], s["y"])]))
        assert abs(foot[1]) == 10.0, (sid, foot)


def test_no_node_lies_inside_or_against_the_racking():
    # 0.52 m plan half-envelope plus margin.
    graph = route.build_graph()
    for (x, y) in graph:
        assert _clearance(x, y) >= 0.6, (x, y)


def test_dijkstra_takes_the_short_way_home():
    # S1 to S2: out of the cross-aisle onto the north ring leg, east
    # past f2's spawn node, into the next one. Never round the ring and
    # never down the pick aisle - which carries no station at all.
    graph = route.build_graph()
    path = route.dijkstra(graph, (-13.0, 4.25), (-7.0, 4.25))
    assert path == [(-13.0, 4.25), (-13.0, 10.0), (-10.0, 10.0),
                    (-7.0, 10.0), (-7.0, 4.25)]


def test_plan_route_starts_at_the_pose_and_ends_at_the_station():
    poly = route.plan_route((0.0, 10.0), "S6")
    assert poly[0] == (0.0, 10.0)
    assert poly[-1] == (13.0, 4.25)
    assert len(poly) >= 3


def test_plan_route_refuses_an_unknown_station():
    assert route.plan_route((0.0, 0.0), "S99") is None


def test_the_longest_leg_is_what_the_spec_says():
    # S12 to S1: 4.90 spur + 17.00 west along the south ring + 20.00
    # north up the spine + 13.00 west along the north ring + 5.75 spur.
    # If this moves, the floor moved and the spec is stale.
    graph = route.build_graph()
    path = route.dijkstra(graph, (17.0, -14.90), (-13.0, 4.25))
    length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
    assert abs(length - 60.65) < 0.01, length


def test_plan_route_can_be_asked_to_avoid_a_node():
    """M6 review item 5c: a node a physical body was reported on is
    closed for a while, and a NEW leg must plan around it. The S9->S12
    leg runs the south ring; with the ring's centre node (0.0,-10.0)
    avoided, the loop still joins the two ends the long way round, so
    the route exists, is longer, and never names the node."""
    direct = route.plan_route((-17.0, -14.9), "S12")
    assert (0.0, -10.0) in direct
    around = route.plan_route((-17.0, -14.9), "S12",
                              avoid={(0.0, -10.0)})
    assert around is not None
    assert (0.0, -10.0) not in around
    d = sum(math.dist(a, b) for a, b in zip(direct, direct[1:]))
    a = sum(math.dist(x, y) for x, y in zip(around, around[1:]))
    assert a > d


def test_avoiding_the_goal_is_an_honest_none():
    """A closed node that IS the station leaves no route, and None is
    the answer the callers already survive - the task is held or
    requeued, not driven into the body standing on the dot."""
    station = (17.0, -14.9)              # S12's own node
    assert route.plan_route((-17.0, -14.9), "S12",
                            avoid={station}) is None
