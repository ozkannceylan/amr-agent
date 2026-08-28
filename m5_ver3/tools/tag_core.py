#!/usr/bin/env python3
"""tag_core.py - the arithmetic behind F5's station furniture. --selftest

    python3 m5_ver3/tools/tag_core.py --selftest

WHAT IS IN HERE, AND WHY IT IS A FILE OF ITS OWN. Three things F5 Task 1
needs are pure functions of numbers, and this track's rule is that those
live where a test on the Windows python can reach them
(nodes/wheel_odom_core.py's own argument, one layer over):

  THE TAG'S BITMAP. A tag36h11 marker is a 10 x 10 grid of black and
  white squares and WHICH squares is decided by the family's codeword.
  `bitmap()` is apriltag3's own `apriltag_to_image()` re-expressed - the
  same border rule, the same bit order, the same bit_x/bit_y placement -
  and `tools/tag_model.py` hands it the family definition read OUT OF
  THE VERY LIBRARY THE DETECTOR WILL USE, through ctypes. Nothing here
  carries a copied code table: a marker this repository prints and a
  marker apriltag_ros decodes are the same object by construction, and
  there is no third-party image to license.

  THE STATION GEOMETRY. Where the marker face stands, where the vehicle
  is docked when its forks are in the load, and where it STAGES - all
  three derived from m6/ipc/stations.py's station point and four
  config-tabled distances, so no pose in config.yaml is typed in.

  THE PLANNABILITY MARGIN. EVIDENCE_NAV_V3.md 20.5 item 3: the planner
  refuses to replan a truck whose footprint is in collision, and inside
  a bay it is - a footprint 2.415 m long ahead of base_link inside an
  inflation layer that marks everything within the grown INSCRIBED
  radius of an obstacle as a collision. `staging_margin()` is that
  arithmetic, and it is what says a staging pose is out of the trap zone
  BY CONSTRUCTION rather than by having got away with it once.

WHAT IS NOT IN HERE. No ROS, no gz, no file paths, no config reader.
`tools/tag_model.py` writes models with it and `tools/tag_bench.py`
scores detections with it; this file knows about neither.
"""
import math
import sys

# ----------------------------------------------------------------------
# the tag bitmap
# ----------------------------------------------------------------------

WHITE = 1
BLACK = 0


def bitmap(nbits, bit_x, bit_y, width_at_border, total_width, code):
    """The marker's own squares, as rows of 0 (black) and 1 (white).

    THIS IS apriltag3's `apriltag_to_image()` AND NOT AN INTERPRETATION
    OF IT. That function does exactly three things, in this order:

        image_u8_create(total_width, total_width)   -> all BLACK
        a one-pixel WHITE ring round the outside
        for i in 0..nbits-1: if code has bit (nbits-1-i) set,
            pixel (bit_x[i] + border_start, bit_y[i] + border_start)
            is WHITE

    with `border_start = (total_width - width_at_border) / 2`. Everything
    else - the black border ring, the data region, the quiet zone - is
    what those three rules leave behind rather than a fourth rule. Row 0
    is the TOP row, which is the image convention and is what
    `cells()` below turns into a height.

    THE BIT ORDER IS THE ONE THAT MATTERS AND IT IS EASY TO GET
    BACKWARDS. Bit i of the loop is bit (nbits - 1 - i) of the codeword,
    most significant first. Reversed, every tag rendered would be a
    valid-looking marker carrying a code the detector has never heard
    of - which does not look like a bug, it looks like a camera that
    cannot see.
    """
    if len(bit_x) != nbits or len(bit_y) != nbits:
        raise ValueError(
            "the family says {} bits and carries {} x and {} y "
            "offsets".format(nbits, len(bit_x), len(bit_y)))
    if (total_width - width_at_border) % 2:
        raise ValueError(
            "total_width {} and width_at_border {} differ by an odd "
            "number, so there is no symmetric border".format(
                total_width, width_at_border))
    rows = [[BLACK] * total_width for _ in range(total_width)]
    last = total_width - 1
    for i in range(total_width):
        rows[0][i] = WHITE
        rows[last][i] = WHITE
        rows[i][0] = WHITE
        rows[i][last] = WHITE
    border_start = (total_width - width_at_border) // 2
    for i in range(nbits):
        if code & (1 << (nbits - 1 - i)):
            rows[bit_y[i] + border_start][bit_x[i] + border_start] = WHITE
    return rows


def cell_size(size_m, width_at_border):
    """One square's edge, from the size apriltag_ros is told.

    `size` in apriltag_ros is the edge of the BLACK BORDER SQUARE - the
    thing the detector fits - and not the printed tile. A marker whose
    black square is `size` therefore has squares of size /
    width_at_border and a printed tile of total_width of them, which is
    why `tile_size()` below is bigger than the number in config.yaml and
    why that is not a discrepancy.
    """
    return float(size_m) / float(width_at_border)


def tile_size(size_m, width_at_border, total_width):
    return cell_size(size_m, width_at_border) * total_width


def cells(rows, size_m, width_at_border, colour=BLACK):
    """Every square of one colour, as (u, v, edge) in the tag's plane.

    u is to the RIGHT AS THE MARKER IS VIEWED FROM THE FRONT and v is
    UP, both from the tag's centre. Image column increases with u and
    image ROW increases DOWNWARD, which is what puts the minus sign on
    v: a marker rendered with that sign the other way is the marker's
    MIRROR IMAGE, and a mirrored 36h11 tag is almost never a valid
    36h11 codeword - so it does not decode as the wrong id, it does not
    decode at all.
    """
    edge = cell_size(size_m, width_at_border)
    total = len(rows)
    half = total / 2.0
    out = []
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            if value != colour:
                continue
            u = (col_index + 0.5 - half) * edge
            v = (half - row_index - 0.5) * edge
            out.append((u, v, edge))
    return out


def render(rows, black="#", white="."):
    """The bitmap as text, for a manifest and for a human."""
    return "\n".join("".join(white if v == WHITE else black for v in row)
                     for row in rows)


# ----------------------------------------------------------------------
# the station geometry
# ----------------------------------------------------------------------

def approach_unit(travel_yaw_rad):
    """The direction of travel down the spur, as a unit vector."""
    return (math.cos(travel_yaw_rad), math.sin(travel_yaw_rad))


def station_geometry(station_x, station_y, travel_yaw_rad,
                     marker_ahead_m, fork_reach_m, tip_standoff_m,
                     staging_run_in_m):
    """Marker, docked pose and staging pose, off m6's station point.

    EVERY ONE OF THEM IS ON THE SPUR'S OWN AXIS and the axis is
    m6/ipc/stations.py's, read-only. What this adds is four distances,
    each argued in config.yaml:

      marker_ahead_m    station point -> the MARKER FACE, along travel.
                        For the eight pick bays that is stations.py's
                        own back-panel line.
      fork_reach_m      base_link -> the fork tips, off model.sdf's own
                        hull. It is the UNGROWN reach, because a
                        collision is geometry and the growth is a
                        localisation margin.
      tip_standoff_m    how far short of the marker face the tips stop.
      staging_run_in_m  the docked pose -> the STAGING pose, backwards
                        along the same axis. This is the straight final
                        leg EVIDENCE_NAV_V3.md 16.6 measured the need
                        for.

    A DOCKED POSE IS NOT AN ARRIVAL POSE, and that is the one thing to
    read twice. m6's station point is where a truck carrying nothing
    stops; this is where the forks are at the load. They are different
    poses and this file computes the second from the first rather than
    pretending they are the same.
    """
    ux, uy = approach_unit(travel_yaw_rad)
    marker = (station_x + ux * marker_ahead_m,
              station_y + uy * marker_ahead_m)
    back = fork_reach_m + tip_standoff_m
    docked = (marker[0] - ux * back, marker[1] - uy * back)
    staging = (docked[0] - ux * staging_run_in_m,
               docked[1] - uy * staging_run_in_m)
    return {
        "unit": (ux, uy),
        "marker": marker,
        "docked": docked,
        "staging": staging,
        "docked_to_marker_m": back,
        "staging_to_marker_m": back + staging_run_in_m,
    }


def inscribed_radius(polygon):
    """The largest circle about the origin inside a convex polygon.

    nav2's inflation layer marks every cell within THIS radius of a
    lethal cell `INSCRIBED_INFLATED_OBSTACLE`, and a collision check
    reads that as a collision. It is therefore the number a standoff has
    to clear, and it is a property of the GROWN polygon because that is
    what nav2.yaml ships.
    """
    best = float("inf")
    n = len(polygon)
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        length = math.hypot(ex, ey)
        if length:
            best = min(best, abs(ex * ay - ax * ey) / length)
    return best


def forward_reach(polygon):
    """How far the footprint reaches in the FORKS direction (model -x).

    Reported POSITIVE. On this vehicle the forks are at model -x, so
    this is -min(x) over the polygon: the grown hull's leading edge in
    the direction of travel.
    """
    return -min(x for x, _ in polygon)


def staging_margin(polygon, staging_to_marker_m):
    """How far the staging footprint clears the marker's collision band.

    THE ARITHMETIC EVIDENCE_NAV_V3.md 20.5 item 3 IS ABOUT. A pose is
    refused by SmacPlannerHybrid (`ComputePathToPose::START_OCCUPIED`,
    205) when its footprint covers a cell the inflation layer has marked
    INSCRIBED_INFLATED - which is every cell within the grown polygon's
    own inscribed radius of a lethal one. So:

        margin = (base_link -> marker) - (footprint's forward reach)
                                       - (inscribed radius)

    A POSITIVE margin is a pose the planner can start from; a negative
    one is 205 by construction, whatever the run does. The minimum
    run-in that keeps it positive is returned too, because that is the
    number a shorter final leg would have to be argued against.
    """
    reach = forward_reach(polygon)
    inner = inscribed_radius(polygon)
    return {
        "forward_reach_m": reach,
        "inscribed_m": inner,
        "clearance_m": staging_to_marker_m - reach,
        "margin_m": staging_to_marker_m - reach - inner,
        "minimum_standoff_m": reach + inner,
    }


def inflation_cost(distance_m, inscribed_m, inflation_radius_m,
                   cost_scaling_factor):
    """nav2's own inflation curve, as a cell value.

    253 is INSCRIBED_INFLATED_OBSTACLE and it is a COLLISION to every
    footprint checker in nav2; 0 is free. Between them the cost is
    252 * exp(-k * (d - inscribed)), truncated to a cell value - the
    same expression tests/test_nav2_params.py already checks the
    scaling factor with, here so a pose can be scored rather than a
    parameter.
    """
    if distance_m <= inscribed_m:
        return 253
    if distance_m >= inflation_radius_m:
        return 0
    return int(252.0 * math.exp(
        -float(cost_scaling_factor) * (distance_m - inscribed_m)))


# ----------------------------------------------------------------------
# --selftest
# ----------------------------------------------------------------------

def _selftest():
    """Every claim in this file, checked against a worked example."""
    failures = []

    def check(name, got, want, tol=0.0):
        ok = (abs(got - want) <= tol) if isinstance(want, float) \
            else (got == want)
        print("{:<44} {:<22} {}".format(
            name, str(got)[:22], "ok" if ok else "WANT " + str(want)))
        if not ok:
            failures.append(name)

    # A FAMILY THAT IS NOT tag36h11, ON PURPOSE. The point of the
    # bitmap function is that it is driven by the family definition, so
    # the selftest drives it with one small enough to write out by hand:
    # 4 bits, a 4-wide border, a 6-wide tile.
    nbits = 4
    bit_x = [1, 2, 1, 2]
    bit_y = [1, 1, 2, 2]
    rows = bitmap(nbits, bit_x, bit_y, 4, 6, 0b1010)
    print(render(rows))
    check("the tile is total_width square", len(rows), 6)
    check("row 0 is the white quiet zone", rows[0], [WHITE] * 6)
    check("the black border survives it", rows[1][1], BLACK)
    check("bit 0 (MSB) is white", rows[2][2], WHITE)
    check("bit 1 is black", rows[2][3], BLACK)
    check("bit 2 is white", rows[3][2], WHITE)
    check("bit 3 is black", rows[3][3], BLACK)

    # THE SIZE ARITHMETIC. apriltag_ros' `size` is the BLACK SQUARE.
    check("cell size", cell_size(0.40, 8), 0.05, 1e-12)
    check("printed tile", tile_size(0.40, 8, 10), 0.50, 1e-12)

    # THE CELLS' PLACEMENT, on the 6-wide example: the top-left black
    # square of the border ring is at column 1, row 1.
    black = cells(rows, 0.40, 4)
    edge = 0.10
    top_left = (-1.5 * edge, +1.5 * edge)
    check("the border's top-left black square",
          min(black, key=lambda c: (-c[1], c[0]))[:2],
          top_left)
    check("v is positive UP", max(c[1] for c in black), 1.5 * edge, 1e-12)

    # THE STATION GEOMETRY, on S5's own numbers.
    geo = station_geometry(7.0, 4.25, -math.pi / 2.0,
                           marker_ahead_m=1.65, fork_reach_m=1.875,
                           tip_standoff_m=0.10, staging_run_in_m=2.00)
    check("marker face y", geo["marker"][1], 2.60, 1e-9)
    check("marker face x", geo["marker"][0], 7.00, 1e-9)
    check("docked y", geo["docked"][1], 4.575, 1e-9)
    check("staging y", geo["staging"][1], 6.575, 1e-9)
    check("staging -> marker", geo["staging_to_marker_m"], 3.975, 1e-9)

    # THE PLANNABILITY MARGIN, on nav2.yaml's own polygon.
    poly = [(-2.415, -0.450), (-1.220, -0.668995), (1.240, -0.560),
            (1.400, -0.510), (1.400, 0.510), (1.240, 0.560),
            (-1.220, 0.668995), (-2.415, 0.450)]
    check("forward reach", forward_reach(poly), 2.415, 1e-9)
    check("inscribed radius", round(inscribed_radius(poly), 4), 0.6143)
    margin = staging_margin(poly, geo["staging_to_marker_m"])
    check("clearance", round(margin["clearance_m"], 4), 1.5600)
    check("margin", round(margin["margin_m"], 4), 0.9457)
    check("minimum standoff", round(margin["minimum_standoff_m"], 4),
          3.0293)
    docked = staging_margin(poly, geo["docked_to_marker_m"])
    check("the DOCKED pose is inside the trap zone",
          docked["margin_m"] < 0.0, True)

    # THE INFLATION CURVE, against the two values that are not a curve.
    check("inside the inscribed band is a collision",
          inflation_cost(0.30, 0.6143, 2.60, 1.10), 253)
    check("beyond the radius is free",
          inflation_cost(2.70, 0.6143, 2.60, 1.10), 0)
    check("the staging clearance costs something and not everything",
          inflation_cost(1.560, 0.6143, 2.60, 1.10), 89)

    print("")
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("tag_core selftest: all checks passed")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(_selftest())
    print(__doc__)
