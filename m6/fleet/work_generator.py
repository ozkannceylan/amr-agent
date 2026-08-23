"""work_generator.py - which transport to ask for next. Pure.

NO BROKER, NO CLOCK, NO ROS. This file decides a station pair and
nothing else; fleet_cli's `demo` command is the only thing that turns a
pair into a submission, exactly as `submit` is the only thing that turns
an operator's two arguments into one.

SEEDED, AND THAT IS A REQUIREMENT RATHER THAN A CONVENIENCE. The
recording is shot twice - once headless with the overhead camera, once
with the Gazebo GUI - and the second take has to be the same scenario as
the first or the two videos are of two different runs. A seed is the
only thing that makes them one run.

WEIGHTED BY ROUTE LENGTH, MEASURED OVER THE ROUTER. A uniform draw over
132 ordered pairs spends most of a recording shuffling pallets between
neighbouring bays, because most pairs ARE short. Weighting by the
router's own distance - never the crow's - puts the cross-hall runs on
screen, which is the whole point of the exercise. `min_len_m` then cuts
the tail off entirely: a 6 m transport is not a fleet demonstration.

IT DRAWS WITH REPLACEMENT AND DOES NOT CARE. The fleet is a queue, not a
schedule; the same pair coming up twice in a shift is a fact about
warehouses, not a defect in this file.
"""
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))
import route                                        # noqa: E402
from stations import STATIONS                       # noqa: E402

MIN_LEN_M = 15.0


def _route_len(src, dst):
    """Metres from station `src` to station `dst` over the router, or
    None when the graph does not join them."""
    start = STATIONS[src]
    poly = route.plan_route((start["x"], start["y"]), dst)
    if poly is None:
        return None
    return sum(
        ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        for a, b in zip(poly, poly[1:]))


class WorkGenerator:
    """A seeded stream of (from_station, to_station) pairs."""

    def __init__(self, seed, min_len_m=MIN_LEN_M, stations_map=None,
                 route_len=None):
        """`stations_map` and `route_len` exist for the tests and for a
        floor that is not this one; production passes neither."""
        table = STATIONS if stations_map is None else stations_map
        length = _route_len if route_len is None else route_len
        pairs = []
        for src in table:
            for dst in table:
                if src == dst:
                    continue
                metres = length(src, dst)
                if metres is None or metres < min_len_m:
                    continue
                pairs.append((src, dst, metres))
        if not pairs:
            raise ValueError(
                "no station pair is at least {:.1f} m apart over the "
                "router - the floor cannot serve this demo"
                .format(min_len_m))
        # Sorted so the list is the same list on every machine: dict
        # iteration order is insertion order, but a caller may hand us
        # any mapping.
        self.pairs = sorted(pairs)
        self._weights = [metres for _s, _d, metres in self.pairs]
        self._rng = random.Random(seed)

    def next_pair(self):
        """One (from, to). Weighted by route length, drawn with
        replacement."""
        src, dst, _metres = self._rng.choices(
            self.pairs, weights=self._weights, k=1)[0]
        return (src, dst)
