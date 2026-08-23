"""map_panel.py's pure coordinate helpers. No Tk window is opened."""
import map_panel
import stations


def test_world_to_canvas_maps_the_hall_corners():
    xmin, xmax, ymin, ymax = stations.HALL
    assert map_panel.world_to_canvas(xmin, ymax) == (0.0, 0.0)
    assert map_panel.world_to_canvas(xmax, ymin) == (
        map_panel.WIDTH, map_panel.HEIGHT)


def test_round_trip_is_identity():
    x, y = map_panel.canvas_to_world(*map_panel.world_to_canvas(3.2, -7.1))
    assert abs(x - 3.2) < 1e-9 and abs(y - (-7.1)) < 1e-9


def test_pick_station_hits_within_the_radius():
    s1 = stations.STATIONS["S1"]
    px, py = map_panel.world_to_canvas(s1["x"], s1["y"])
    assert map_panel.pick_station(px + 5.0, py) == "S1"


def test_pick_station_misses_outside_the_radius():
    s1 = stations.STATIONS["S1"]
    px, py = map_panel.world_to_canvas(s1["x"], s1["y"])
    assert map_panel.pick_station(px + 30.0, py) is None
