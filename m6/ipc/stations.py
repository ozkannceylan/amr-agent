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

THE BAYS FACE THE RING AND NOT THE PICK AISLE, since 2026-08-23.
A tricycle with a 1.29 m minimum turning radius cannot enter a 4.00 m
bay squarely off a 5.00 m corridor - it goes in skewed and its back
scanner ends up against a side wall. Measured on the first full
four-truck run: f1 stopped at (-13.35, 3.59) and f2 at (6.65, 3.60),
both inside their own bay with the BACK protective field violated at
0.977 m and 0.975 m, and neither recoverable, because a monitored reset
does not take while the cause stands. Two of four trucks were parked for
good by minute six. The bay is still 4.00 m; what changed is that it is
entered off the 8.00 m ring band instead, which gives the truck three
more metres to line up in before it commits.

THE STATIONS ARE IN OPEN CROSS-AISLES, NOT IN POCKETS. See OBSTACLES
for the measurement that settled it: a truck 2.80 m long needs 1.20 m of
protective clearance ahead, so a pocket has to be over 4.00 m deep and a
3.50 m rack row cannot give one. The gap is cut right through instead.

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
    # Eight pick bays, 4.00 m wide, cut through the 3.50 m rack rows -
    # AND THEY OPEN ONTO THE RING, WHICH IS THE WHOLE OF REVISION B.
    # They faced the 5.00 m pick aisle until 2026-08-23, and a tricycle
    # with a 1.29 m minimum turning radius cannot enter a 4.00 m bay
    # squarely off a 5.00 m corridor: it goes in skewed and its back
    # scanner ends up against a side wall. Measured on the first full
    # run - f1 stopped at (-13.35, 3.59) and f2 at (6.65, 3.60), both
    # inside their own bay with the BACK protective field violated at
    # 0.977 m and 0.975 m, neither recoverable because the cause stood.
    # Two of four trucks were parked for good by minute six.
    #
    # The bay is the same 4.00 m. What changed is the road it is entered
    # from: the ring band is 8.00 m, so the truck has three more metres
    # to line up in before it commits. Mouth at y = +-6.00 (the block
    # edge), back panel face at +-2.60, station at +-(2.60 + 2.60) =
    # +-5.20, spur from the ring centreline 4.80 m.
    ("S1",  {"name": "PICK-NW-1", "x": -13.0, "y":   4.25, "yaw": _S,
             "arrive_m": 0.25}),
    ("S2",  {"name": "PICK-NW-2", "x":  -7.0, "y":   4.25, "yaw": _S,
             "arrive_m": 0.25}),
    ("S3",  {"name": "PICK-SW-1", "x": -13.0, "y":  -4.25, "yaw": _N,
             "arrive_m": 0.25}),
    ("S4",  {"name": "PICK-SW-2", "x":  -7.0, "y":  -4.25, "yaw": _N,
             "arrive_m": 0.25}),
    ("S5",  {"name": "PICK-NE-1", "x":   7.0, "y":   4.25, "yaw": _S,
             "arrive_m": 0.25}),
    ("S6",  {"name": "PICK-NE-2", "x":  13.0, "y":   4.25, "yaw": _S,
             "arrive_m": 0.25}),
    ("S7",  {"name": "PICK-SE-1", "x":   7.0, "y":  -4.25, "yaw": _N,
             "arrive_m": 0.25}),
    ("S8",  {"name": "PICK-SE-2", "x":  13.0, "y":  -4.25, "yaw": _N,
             "arrive_m": 0.25}),
    # Four annex bays, 4.00 m wide and 4.00 m DEEP, cut through the dock
    # annex and entered from the south ring leg's wall side - which was
    # already an 8.00 m approach and is why these four never got stuck.
    # Their x moved to +-17 / +-10 so that both ring legs carry the SAME
    # node list and no junction sits 1.00 m from another.
    ("S9",  {"name": "DOCK-DOOR", "x": -17.0, "y": -14.90, "yaw": _S,
             "arrive_m": 0.25}),
    ("S10", {"name": "CHARGE-1",  "x": -10.0, "y": -14.90, "yaw": _S,
             "arrive_m": 0.25}),
    ("S11", {"name": "CHARGE-2",  "x":  10.0, "y": -14.90, "yaw": _S,
             "arrive_m": 0.25}),
    ("S12", {"name": "CONVEYOR",  "x":  17.0, "y": -14.90, "yaw": _S,
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
    # The bay back panels are at the row's INNER face now, because the
    # mouth is at its outer one. They are what the pick aisle sees.,,,,,,,,
    # The dock annex: five solid segments with four bays between them.
    ("AnnexW",     -24.00, -19.00, -18.00, -14.00),
    ("AnnexA",     -15.00, -12.00, -18.00, -14.00),
    ("AnnexB",      -8.00,   8.00, -18.00, -14.00),
    ("AnnexC",      12.00,  15.00, -18.00, -14.00),
    ("AnnexE",      19.00,  24.00, -18.00, -14.00),
    ("BayS9Back",  -19.00, -15.00, -18.00, -17.90),
    ("BayS10Back", -12.00,  -8.00, -18.00, -17.90),
    ("BayS11Back",   8.00,  12.00, -18.00, -17.90),
    ("BayS12Back",  15.00,  19.00, -18.00, -17.90),
)
