"""stations.py - the ten stations and the floor they must keep clear of.

THE ONE HOME for station ids, names, poses and the obstacle rectangles.
The world paint (warehouse_ver2.sdf), the router (route.py) and the HMI
sketch (hmi/map_panel.py) all read from here or are tested against it
(test_stations_sdf.py); a station moved in only one place is a test
failure, not a silent divergence.

yaw is the APPROACH heading - the travel direction on the spur - used to
orient the paint tick and nothing else. Arrival is position-only: a
tricycle cannot rotate in place (spec, "Autonomous drive").

arrive_m IS GEOMETRY, NOT TOLERANCE CREEP. A station is reached down a
spur perpendicular to its aisle, and a spur too short to straighten out
on cannot be hit tightly by ANY gain: measured 2026-08-13 at S7, the
truck missed the 0.85 m spur, could not converge, and settled into a
stable orbit 0.643-0.742 m around the station - its own minimum turning
radius (~0.69 m). A vehicle cannot reach a point inside its turning
circle. So the short-spur stations (S2, S3 at 1.1 m; S6..S9 at 0.85 m)
declare 0.80 m, which catches the FIRST pass before any lap begins, and
the rest keep 0.25 m: S1, S5 sit ON their aisle and need no turn at all,
S4 and S10 have 2.5 m and 3.0 m of spur to align in. test_route.py pins
the rule - spur length decides, not a hand-written list. Precision stays
proven where the floor allows it; where it does not, the number says so
out loud instead of the truck circling forever.

OBSTACLES mirrors warehouse_ver2.sdf's collision rectangles (rack faces
from the file header's parametric table, cabinets and conveyor from
their <pose>/<size>). The SDF stays the geometric truth; these numbers
are its shadow, and the free-floor tests are what notice a drift.

THE 2.4 m FACE STANDOFF IS A SCANNER DIMENSION, NOT A STYLE. The stations
that face a rack or the conveyor (S5..S10) park the TRUCK CENTRE 2.4 m off
that face. The side safety scanners sit about 0.8 m forward of centre,
toward the fork tip, so a fork-first approach puts them 0.8 m closer to the
face than the pose suggests: measured 2026-08-13, a 1.5-1.9 m centre
standoff parked the right scanner 0.99 m off rack B and tripped the case-1
protective field (1.0 m) with the truck exactly on its lane. 2.4 = 0.8
scanner offset + 1.0 protective field + 0.2 field hysteresis + 0.4 for the
pursuit's corner-convergence residual. test_route.py pins it so a station
cannot drift back inside the field.
"""
import math
from collections import OrderedDict

HALL = (-15.0, 15.0, -10.0, 10.0)          # inner wall faces

STATIONS = OrderedDict((
    ("S1",  {"name": "HOME",      "x": -3.0, "y": -5.5,  "yaw": 0.0,
             "arrive_m": 0.25}),                    # on the dock aisle
    ("S2",  {"name": "CHARGE-1",  "x": -9.8, "y": -6.6,  "yaw": -math.pi / 2,
             "arrive_m": 0.80}),                    # 1.1 m spur
    ("S3",  {"name": "CHARGE-2",  "x": -7.4, "y": -6.6,  "yaw": -math.pi / 2,
             "arrive_m": 0.80}),                    # 1.1 m spur
    ("S4",  {"name": "DOCK-DOOR", "x":  6.0, "y": -8.0,  "yaw": -math.pi / 2,
             "arrive_m": 0.25}),                    # 2.5 m spur, aligns in
    # S5..S10 keep 2.4 m off the face they serve (see the module note):
    # conveyor face x 14.00, rack A face y 8.90, rack B north face y 2.40,
    # rack B south face y -0.10.
    ("S5",  {"name": "CONVEYOR",  "x": 11.6, "y":  5.65, "yaw": 0.0,
             "arrive_m": 0.25}),                    # on the main aisle
    ("S6",  {"name": "PICK-A-W",  "x": -8.0, "y":  6.50, "yaw": math.pi / 2,
             "arrive_m": 0.80}),                    # 0.85 m spur
    ("S7",  {"name": "PICK-A-E",  "x":  8.0, "y":  6.50, "yaw": math.pi / 2,
             "arrive_m": 0.80}),                    # 0.85 m spur
    ("S8",  {"name": "PICK-B-W",  "x": -8.0, "y":  4.80, "yaw": -math.pi / 2,
             "arrive_m": 0.80}),                    # 0.85 m spur
    ("S9",  {"name": "PICK-B-E",  "x":  8.0, "y":  4.80, "yaw": -math.pi / 2,
             "arrive_m": 0.80}),                    # 0.85 m spur
    ("S10", {"name": "PICK-B-S",  "x": -6.0, "y": -2.50, "yaw": math.pi / 2,
             "arrive_m": 0.25}),                    # 3.0 m spur, aligns in
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
