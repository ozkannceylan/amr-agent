"""stations.py - the ten stations and the floor they must keep clear of.

THE ONE HOME for station ids, names, poses and the obstacle rectangles.
The world paint (warehouse_ver2.sdf), the router (route.py) and the HMI
sketch (hmi/map_panel.py) all read from here or are tested against it
(test_stations_sdf.py); a station moved in only one place is a test
failure, not a silent divergence.

yaw is the APPROACH heading - the travel direction on the spur - used to
orient the paint tick and nothing else. Arrival is position-only: a
tricycle cannot rotate in place (spec, "Autonomous drive").

OBSTACLES mirrors warehouse_ver2.sdf's collision rectangles (rack faces
from the file header's parametric table, cabinets and conveyor from
their <pose>/<size>). The SDF stays the geometric truth; these numbers
are its shadow, and the free-floor tests are what notice a drift.
"""
import math
from collections import OrderedDict

HALL = (-15.0, 15.0, -10.0, 10.0)          # inner wall faces

STATIONS = OrderedDict((
    ("S1",  {"name": "HOME",      "x": -3.0, "y": -5.5,  "yaw": 0.0}),
    ("S2",  {"name": "CHARGE-1",  "x": -9.8, "y": -6.6,  "yaw": -math.pi / 2}),
    ("S3",  {"name": "CHARGE-2",  "x": -7.4, "y": -6.6,  "yaw": -math.pi / 2}),
    ("S4",  {"name": "DOCK-DOOR", "x":  6.0, "y": -8.0,  "yaw": -math.pi / 2}),
    ("S5",  {"name": "CONVEYOR",  "x": 13.0, "y":  5.65, "yaw": 0.0}),
    ("S6",  {"name": "PICK-A-W",  "x": -8.0, "y":  7.0,  "yaw": math.pi / 2}),
    ("S7",  {"name": "PICK-A-E",  "x":  8.0, "y":  7.0,  "yaw": math.pi / 2}),
    ("S8",  {"name": "PICK-B-W",  "x": -8.0, "y":  4.3,  "yaw": -math.pi / 2}),
    ("S9",  {"name": "PICK-B-E",  "x":  8.0, "y":  4.3,  "yaw": -math.pi / 2}),
    ("S10", {"name": "PICK-B-S",  "x": -6.0, "y": -1.6,  "yaw": math.pi / 2}),
))

OBSTACLES = (
    ("RackA_W",   -10.00, -3.10,  8.90, 10.00),
    ("RackA_E",     3.10, 10.00,  8.90, 10.00),
    ("RackB_W",   -10.00, -3.10, -0.10,  2.40),
    ("RackB_E",     3.10, 10.00, -0.10,  2.40),
    ("Conveyor",   14.00, 14.90,  3.50,  6.50),
    ("ChargeCab1", -10.25, -9.35, -10.00, -9.35),
    ("ChargeCab2",  -7.85, -6.95, -10.00, -9.35),
    ("DoorPostW",    3.80,  4.00, -10.25, -9.95),
    ("DoorPostE",    8.00,  8.20, -10.25, -9.95),
)
