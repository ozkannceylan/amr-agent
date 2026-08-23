"""stations.py's own table. Pure numbers, no graph and no world.

THE TWO STANDOFFS ARE DIFFERENT NUMBERS BECAUSE THEY GUARD DIFFERENT
DEVICES. Ahead is the face the truck drives at: 0.80 m of scanner
offset toward the fork tip, plus case-1 PF 1.00, plus 0.20
hysteresis, plus margin. Abeam is a wall the truck passes: PF 1.00 + 0.20
hysteresis + the 0.46 m lateral scanner mount offset. A bay 4.00 m wide
gives 2.00 m abeam, which is why 4.00 is the width.
"""
import math

import stations

AHEAD_M = 2.50
ABEAM_M = 1.66


def _gap(station, rect):
    """(dx, dy) from the station point to the rectangle, 0 when inside."""
    _n, xmin, xmax, ymin, ymax = rect
    return (max(xmin - station["x"], 0.0, station["x"] - xmax),
            max(ymin - station["y"], 0.0, station["y"] - ymax))


def test_twelve_stations_with_unique_names():
    assert len(stations.STATIONS) == 12
    names = [s["name"] for s in stations.STATIONS.values()]
    assert len(set(names)) == 12
    assert list(stations.STATIONS) == ["S{}".format(n) for n in range(1, 13)]


def test_every_station_arrives_at_the_tight_radius():
    # The whole point of the redesign: no spur is short enough to need
    # the loosened radius, so nothing declares it.
    for sid, s in stations.STATIONS.items():
        assert s["arrive_m"] == 0.25, sid


def test_every_station_is_inside_the_hall():
    xmin, xmax, ymin, ymax = stations.HALL
    for sid, s in stations.STATIONS.items():
        assert xmin < s["x"] < xmax, sid
        assert ymin < s["y"] < ymax, sid


def test_every_station_keeps_its_ahead_and_abeam_standoffs():
    for sid, s in stations.STATIONS.items():
        along_y = abs(math.sin(s["yaw"])) > 0.5
        for rect in stations.OBSTACLES:
            dx, dy = _gap(s, rect)
            if dx > 0.0 and dy > 0.0:
                continue          # diagonal: neither ahead nor abeam
            ahead, abeam = (dy, dx) if along_y else (dx, dy)
            if abeam == 0.0:
                assert ahead >= AHEAD_M, (sid, rect[0], ahead)
            if ahead == 0.0:
                assert abeam >= ABEAM_M, (sid, rect[0], abeam)


def test_no_station_sits_inside_an_obstacle():
    for sid, s in stations.STATIONS.items():
        for rect in stations.OBSTACLES:
            dx, dy = _gap(s, rect)
            assert dx > 0.0 or dy > 0.0, (sid, rect[0])


def test_obstacle_rectangles_are_well_formed():
    seen = set()
    for name, xmin, xmax, ymin, ymax in stations.OBSTACLES:
        assert xmin < xmax, name
        assert ymin < ymax, name
        assert name not in seen, name
        seen.add(name)
    assert len(stations.OBSTACLES) == 21
