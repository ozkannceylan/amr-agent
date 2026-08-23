"""stations.py - the twelve stations and the floor they must keep clear of.

THE ONE HOME for station ids, names, poses and the obstacle rectangles.
The world paint (warehouse_ver3.sdf), the router (route.py) and the HMI
sketch (hmi/map_panel.py) all read from here or are tested against it
(test_stations_sdf.py); a station moved in only one place is a test
failure, not a silent divergence.

yaw is the APPROACH heading - the travel direction on the spur - used to
orient the paint tick, and read by test_stations.py to know which axis is
'ahead'. Arrival is position-only: a tricycle cannot rotate in place.

EVERY STATION DECLARES 0.25 m, AND THAT IS THE POINT OF THIS FLOOR.
Measured 2026-08-13 at the old S7: a truck cannot reach a point inside
its own turning circle, so a 0.85 m spur produced a stable orbit at
0.643-0.742 m and the station had to declare 0.80 m to catch the first
pass. The old S4 (2.5 m spur) and S10 (3.0 m spur) hit 0.25 m. So the
floor is drawn with NO SHORT SPURS: the shortest here is 3.30 m. The
loosened radius is not in this file because nothing on this floor needs
it.

TWO STANDOFFS, NOT ONE, BECAUSE THEY GUARD DIFFERENT DEVICES.
  AHEAD  2.50 m to the face the truck drives at.
         0.80 (the side scanners sit that far toward the fork tip) +
         1.00 (case-1 protective field) + 0.20 (hysteresis) + 0.50.
         Measured 2026-08-13: a 1.5-1.9 m centre standoff parked the
         right scanner 0.99 m off a rack face and tripped case 1 with
         the truck exactly on its lane.
  ABEAM  1.66 m to a wall the truck passes.
         1.00 (PF) + 0.20 (hysteresis) + 0.46 (lateral scanner mount
         offset). A bay 4.00 m wide gives 2.00 m. That is why bays are
         4.00 m wide and not 3.60.

OBSTACLES mirrors warehouse_ver3.sdf's collision rectangles. The SDF
stays the geometric truth; these numbers are its shadow, and
test_stations_sdf.py is what notices a drift.

THE HALL IS NOT CENTRED ON y. The southern strip y in [-18.00, -14.00]
is the dock annex - a solid block with four bays cut through it. Its
bays are 4.00 m deep on purpose: a shallower recess parks the truck out
in the ring band, where a passer-by on the centreline clears it by
1.34 m, which is 0.14 m over PF+hysteresis. That is PROOF.md residual 3
(f1 parked on S1) rebuilt from scratch, and the depth is what prevents
it.
"""
import math
from collections import OrderedDict

HALL = (-24.0, 24.0, -18.0, 14.0)          # inner wall faces: 48 x 32 m

_N, _S = math.pi / 2, -math.pi / 2

STATIONS = OrderedDict((
    # Eight pick bays, 4.00 m wide, cut through the 3.50 m rack rows.
    # Bay mouth at y = +-2.50 (the pick aisle edge), back panel face at
    # +-5.90, so the station sits at +-(5.90 - 2.60) = +-3.30 and the
    # spur from the pick-aisle centreline is 3.30 m. THE BAY IS DRAWN TO
    # 2.60 AND THE THRESHOLD IS 2.50, deliberately: at exactly 2.50 the
    # assertion sits on a float knife-edge - (-15.40) - (-17.90)
    # evaluates to 2.4999999999999982 and fails a >= 2.50 test that is
    # geometrically satisfied. 0.10 m of margin costs nothing and buys
    # an assertion that means what it says.
    ("S1",  {"name": "PICK-NW-1", "x": -13.0, "y":   3.30, "yaw": _N,
             "arrive_m": 0.25}),
    ("S2",  {"name": "PICK-NW-2", "x":  -7.0, "y":   3.30, "yaw": _N,
             "arrive_m": 0.25}),
    ("S3",  {"name": "PICK-SW-1", "x": -13.0, "y":  -3.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S4",  {"name": "PICK-SW-2", "x":  -7.0, "y":  -3.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S5",  {"name": "PICK-NE-1", "x":   7.0, "y":   3.30, "yaw": _N,
             "arrive_m": 0.25}),
    ("S6",  {"name": "PICK-NE-2", "x":  13.0, "y":   3.30, "yaw": _N,
             "arrive_m": 0.25}),
    ("S7",  {"name": "PICK-SE-1", "x":   7.0, "y":  -3.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S8",  {"name": "PICK-SE-2", "x":  13.0, "y":  -3.30, "yaw": _S,
             "arrive_m": 0.25}),
    # Four annex bays, 4.00 m wide and 4.00 m DEEP, cut through the dock
    # annex. Mouth at y = -14.00, back panel face at -17.90, so the
    # station sits at -17.90 + 2.60 = -15.30 and the spur from the south
    # ring centreline (y = -10.00) is 5.30 m. The truck parks entirely
    # inside the bay: y in [-16.50, -14.10].
    ("S9",  {"name": "DOCK-DOOR", "x": -14.0, "y": -15.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S10", {"name": "CHARGE-1",  "x":  -6.0, "y": -15.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S11", {"name": "CHARGE-2",  "x":   6.0, "y": -15.30, "yaw": _S,
             "arrive_m": 0.25}),
    ("S12", {"name": "CONVEYOR",  "x":  14.0, "y": -15.30, "yaw": _S,
             "arrive_m": 0.25}),
))

# The rack rows run x in [-16, -4] (west block) and [4, 16] (east block),
# 3.50 m deep at y in +-[2.50, 6.00]. Four 4.00 m bays are cut through
# each side's pair of rows; what is left is the twelve segments below.
# The bay BACK PANELS are separate rectangles because they are the face
# the truck's ahead-standoff is measured against.
OBSTACLES = (
    ("RackNW1",   -16.00, -15.00,   2.50,   6.00),
    ("RackNW2",   -11.00,  -9.00,   2.50,   6.00),
    ("RackNW3",    -5.00,  -4.00,   2.50,   6.00),
    ("RackNE1",     4.00,   5.00,   2.50,   6.00),
    ("RackNE2",     9.00,  11.00,   2.50,   6.00),
    ("RackNE3",    15.00,  16.00,   2.50,   6.00),
    ("RackSW1",   -16.00, -15.00,  -6.00,  -2.50),
    ("RackSW2",   -11.00,  -9.00,  -6.00,  -2.50),
    ("RackSW3",    -5.00,  -4.00,  -6.00,  -2.50),
    ("RackSE1",     4.00,   5.00,  -6.00,  -2.50),
    ("RackSE2",     9.00,  11.00,  -6.00,  -2.50),
    ("RackSE3",    15.00,  16.00,  -6.00,  -2.50),
    ("BayS1Back",  -15.00, -11.00,   5.90,   6.00),
    ("BayS2Back",   -9.00,  -5.00,   5.90,   6.00),
    ("BayS5Back",    5.00,   9.00,   5.90,   6.00),
    ("BayS6Back",   11.00,  15.00,   5.90,   6.00),
    ("BayS3Back",  -15.00, -11.00,  -6.00,  -5.90),
    ("BayS4Back",   -9.00,  -5.00,  -6.00,  -5.90),
    ("BayS7Back",    5.00,   9.00,  -6.00,  -5.90),
    ("BayS8Back",   11.00,  15.00,  -6.00,  -5.90),
    # The dock annex: five solid segments with four bays between them.
    ("AnnexW",     -24.00, -16.00, -18.00, -14.00),
    ("AnnexA",     -12.00,  -8.00, -18.00, -14.00),
    ("AnnexB",      -4.00,   4.00, -18.00, -14.00),
    ("AnnexC",       8.00,  12.00, -18.00, -14.00),
    ("AnnexE",      16.00,  24.00, -18.00, -14.00),
    ("BayS9Back",  -16.00, -12.00, -18.00, -17.90),
    ("BayS10Back",  -8.00,  -4.00, -18.00, -17.90),
    ("BayS11Back",   4.00,   8.00, -18.00, -17.90),
    ("BayS12Back",  12.00,  16.00, -18.00, -17.90),
)
