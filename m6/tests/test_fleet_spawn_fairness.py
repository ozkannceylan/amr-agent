"""The four spawns do not divide the floor between them.

M6's recording showed four trucks in four corners. The cause was in
status_contract's own comment: "Every station has a truck within 8.60 m
and no truck has to cross the hall." That was deliberate then and is
the defect now, so it gets an assertion rather than a comment.
"""
import collections
import math

import route
import stations
import status_contract


def _spawn_xy(vid):
    spawn = status_contract.VEHICLES[vid]["spawn"]
    return (float(spawn["x"]), float(spawn["y"]))


def _route_len(graph, a, b):
    path = route.dijkstra(graph, route.nearest_node(graph, a), b)
    assert path is not None, (a, b)
    return sum(math.dist(p, q) for p, q in zip(path, path[1:]))


def test_every_spawn_is_its_own_graph_node():
    # nearest_node and floor._standing_from both snap a pose to the
    # nearest node. Four trucks sharing one nearest node are four trucks
    # the ledger will hand one piece of floor to at startup.
    graph = route.build_graph()
    feet = [route.nearest_node(graph, _spawn_xy(v))
            for v in status_contract.VEHICLES]
    assert len(set(feet)) == len(feet), feet
    for vid in status_contract.VEHICLES:
        assert _spawn_xy(vid) in graph, vid


def test_no_truck_owns_more_than_a_third_of_the_floor():
    """Ties are SHARED, not awarded.

    The floor is mirror symmetric about x = 0 and so is the spawn row,
    so f2 and f3 are exactly equidistant from every mirrored pair of
    stations. fleet_core.nearest_idle breaks that tie by serial -
    deterministically, and to the lower one - so a strict count hands f2
    six of the twelve and f3 none, and measures alphabetical order
    rather than the floor. Shared, the row scores 3.0 each: measured
    2026-08-23, before this test was written.
    """
    graph = route.build_graph()
    share = collections.Counter()
    for sid, s in stations.STATIONS.items():
        goal = (s["x"], s["y"])
        metres = {v: _route_len(graph, _spawn_xy(v), goal)
                  for v in status_contract.VEHICLES}
        best = min(metres.values())
        winners = [v for v, m in metres.items() if m - best < 0.01]
        for v in winners:
            share[v] += 1.0 / len(winners)
    assert set(share) == set(status_contract.VEHICLES), dict(share)
    assert max(share.values()) <= 4.0, dict(share)


def test_parked_trucks_are_outside_each_other_warning_fields():
    # 2.50 warning field + 0.20 hysteresis. A scanner sits 0.46 m off
    # centre and a body edge 0.52 m off the neighbour's centre.
    poses = sorted(_spawn_xy(v) for v in status_contract.VEHICLES)
    for a, b in zip(poses, poses[1:]):
        gap = math.dist(a, b) - 0.46 - 0.52
        assert gap >= 2.70, (a, b, gap)


def test_no_spawn_sits_on_a_station_spur():
    for vid in status_contract.VEHICLES:
        x, y = _spawn_xy(vid)
        for sid, s in stations.STATIONS.items():
            assert math.dist((x, y), (s["x"], s["y"])) > 5.0, (vid, sid)
