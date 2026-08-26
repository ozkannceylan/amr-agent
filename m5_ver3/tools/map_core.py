#!/usr/bin/env python3
"""map_core.py - the arithmetic behind the map, and nothing else.

    python3 m5_ver3/tools/map_core.py --selftest

IT IS tools/evidence_core.py's ARGUMENT APPLIED TO A SECOND ARTIFACT. That
file exists because a statistic that can only be recomputed on the rig
that produced it is a statistic nobody can check; this one exists for the
same reason and holds the same kind of thing - grid reading, line fitting,
a rigid transform, a distance between two rectangles. It imports no ROS,
opens no simulator and reads no file it was not handed. Every function
here is reached by tests/test_map_core.py on geometry the test builds
itself, and tools/map_register.py is the shell that puts real files in
front of it.

WHY IT IS A SECOND MODULE AND NOT MORE OF evidence_core. What is in
evidence_core is what a SENSOR delivered and what an ESTIMATE was worth
against ground truth - a time series and its statistics. What is here is
GEOMETRY: an occupancy grid, the world's own rectangles, and the rigid
transform between them. The two share `mean` and an exception type and
nothing else, and those are imported rather than copied, which is this
tree's rule about mechanisms.

THREE QUESTIONS, ONE READER OF THE WORLD. The world SDF is parsed once,
here, into rectangles, and two different questions are asked of them:
where the walls TRULY are (which is what a map is scored against) and
where the obstacles TRULY are (which is what a drive has to miss). Two
readers of one file would eventually disagree about a wall.

THE METHOD IS m5_ver1's AND THE DATA IS NOT. sim/maps/warehouse/
register_map.py registered a map of a DIFFERENT warehouse - a different
hall, a different lidar, a different vehicle - and none of its numbers
mean anything here. What is cribbed is the discipline, and the part of it
that is load-bearing is the SEED:

  A least-squares seed is dragged towards whatever stands in front of the
  wall, and the trim then converges onto THAT surface and reports a tight
  residual against it. A small residual against the wrong surface is the
  worst failure available here, because it looks like success.
  (docs/LESSONS.md 93, measured 2026-08-04 on the m5-08b grid: seeded by
  least squares the same wall fitted at -1.61, -1.80, -1.43 and -1.32 deg
  at four trim widths; seeded by the repeated median, +1.69 at all four.)

So `fit_line_robust` seeds with Siegel's repeated median, which has a
50 percent breakdown point, and only then trims and refits by least
squares. `tests/test_map_core.py` asserts both halves of that: that the
robust seed recovers a wall with 40 percent contamination in front of it,
and that the least-squares fit of the same points does not.

AND NOTHING IS FILTERED AT EXTRACTION. `extract_extremes` returns one
candidate per grid line and applies no distance test of its own, because
a fixed band around the median extreme is an AXIS-ALIGNED band and a
wall that is rotated off the grid axes leaves that band at its two ENDS -
which are the points that determine the angle best. Selection is the
trimming rule's job and no other's.
"""
import collections
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import evidence_core as core                           # noqa: E402


class MapError(core.EvidenceError):
    """Something this module was handed cannot be measured.

    IT INHERITS evidence_core's ERROR ON PURPOSE. A shell that already
    catches EvidenceError and turns it into a house refusal - which is
    what tools/sensor_evidence.py's fail() does - catches this too, so
    there is one refusal voice and not two. This module still raises its
    own name so a traceback says which arithmetic said no.
    """


#: The occupancy grid as it is on disk: a P5 header and a byte per cell.
Grid = collections.namedtuple("Grid", "width height maxval pixels")

#: One fitted straight line. `normal` is a unit vector pointing the way
#: the WORLD says the surface faces, `offset` is n.p for any p on it, and
#: `kept` is the points that survived the trim - the ones the transform
#: is allowed to see.
LineFit = collections.namedtuple("LineFit", "normal offset rms kept dropped")

#: An axis-aligned footprint out of the world SDF, in world metres.
Box = collections.namedtuple("Box", "name x0 x1 y0 y1")

#: How far off the grid axes the transform search looks, and how finely.
#: 8 degrees is wider than any rotation this stack has ever produced, and
#: the scan REFUSES a minimum that lands on its own edge rather than
#: reporting it - a clipped answer is not an answer.
DEFAULT_SPAN_RAD = math.radians(8.0)
DEFAULT_STEPS = 401
#: How many trim-and-refit passes before the loop is called converged.
TRIM_PASSES = 20


# ----------------------------------------------------------------------
# the occupancy grid, as nav2's map_saver writes it
# ----------------------------------------------------------------------

def parse_pgm(data):
    """A binary P5 PGM, or a MapError naming what was wrong with it.

    P5 ONLY, AND A SHORT READ IS A REFUSAL. nav2's map_saver writes P5
    and nothing else; a P2 (ascii) grid would parse into different
    numbers under the same name, and a truncated payload padded with
    zeros would read as a band of OCCUPIED cells along one edge - a
    fabricated wall, in the file this module exists to fit walls in.
    """
    if not data[:2] == b"P5":
        raise MapError("the grid is a binary P5 PGM: its first two bytes "
                       "are {!r}".format(bytes(data[:2])))
    fields = []
    index = 2
    while len(fields) < 3:
        if index >= len(data):
            raise MapError("the PGM header ended before width, height and "
                           "maxval had all been read")
        ch = data[index:index + 1]
        if ch.isspace():
            index += 1
            continue
        if ch == b"#":
            while index < len(data) and data[index:index + 1] != b"\n":
                index += 1
            continue
        start = index
        while index < len(data) and not data[index:index + 1].isspace():
            index += 1
        try:
            fields.append(int(data[start:index]))
        except ValueError:
            raise MapError("the PGM header field at byte {} is not a "
                           "number: {!r}".format(start, data[start:index]))
    # EXACTLY ONE WHITESPACE BYTE after maxval, which is the format's own
    # rule. Skipping "all whitespace" would eat the first pixel of a grid
    # whose first cell happens to be 0x20 or 0x0a.
    index += 1
    width, height, maxval = fields
    wanted = width * height
    payload = data[index:index + wanted]
    if len(payload) != wanted:
        raise MapError(
            "the PGM carries {} x {} = {} cells; the file has {} bytes "
            "of payload".format(width, height, wanted, len(payload)))
    return Grid(width, height, maxval, bytearray(payload))


_YAML_STR = r"^\s*{}\s*:\s*(\S+)\s*$"
_YAML_NUM = r"^\s*{}\s*:\s*([-+0-9.eE]+)"
_YAML_ORIGIN = (r"^\s*origin\s*:\s*\[\s*([-+0-9.eE]+)\s*,\s*"
                r"([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*\]")


def parse_map_yaml(text):
    """The six scalars nav2 writes beside a grid. Anything else is ignored.

    IT IS A REGEX READER AND NOT A YAML PARSER, which is deliberate. This
    module is the arithmetic and it is imported by things that have no
    business acquiring a dependency; more to the point, a full parser
    would silently accept a file with the right keys under the wrong
    node. Six names, read by name, and a refusal for the three that
    decide where a cell IS.
    """
    meta = {}
    for key in ("image", "mode"):
        found = re.search(_YAML_STR.format(key), text, re.MULTILINE)
        if found:
            meta[key] = found.group(1)
    for key, fallback in (("resolution", None), ("occupied_thresh", 0.65),
                          ("free_thresh", 0.196), ("negate", 0.0)):
        found = re.search(_YAML_NUM.format(key), text, re.MULTILINE)
        if found:
            meta[key] = float(found.group(1))
        elif fallback is not None:
            meta[key] = fallback
    found = re.search(_YAML_ORIGIN, text, re.MULTILINE)
    if found:
        meta["origin"] = tuple(float(g) for g in found.groups())
    for key in ("image", "resolution", "origin"):
        if key not in meta:
            raise MapError("the map yaml names {}: without it a cell has "
                           "no position at all".format(key))
    return meta


def occupied_mask(grid, meta):
    """One boolean per cell, at the THRESHOLD THE GRID SHIPS WITH.

    `occupied_thresh` and `negate` are read out of the map's own yaml and
    are never assumed, because reading them is the difference between
    measuring this artifact and measuring an assumption about it. The
    free threshold is deliberately not consulted: what a wall fit needs
    is the OCCUPIED class, and everything else - free and unknown alike -
    is simply not a candidate.
    """
    negate = meta.get("negate", 0.0) > 0.5
    limit = meta["occupied_thresh"]
    maxval = float(grid.maxval)
    table = [False] * (grid.maxval + 1)
    for value in range(grid.maxval + 1):
        shade = value if negate else (grid.maxval - value)
        table[value] = (shade / maxval) > limit
    return [table[v] for v in grid.pixels]


def cell_centre(meta, height, col, row):
    """Where a cell's CENTRE is in map metres, by nav2's own convention.

    THE IMAGE ORIGIN IS ITS LOWER-LEFT CORNER AND PGM ROW 0 IS THE TOP
    ROW, so the row index has to be flipped. Getting this backwards
    mirrors the map about its own middle and still produces a plausible
    wall fit, which is why it has a test of its own.
    """
    res = meta["resolution"]
    ox, oy = meta["origin"][0], meta["origin"][1]
    return (ox + (col + 0.5) * res,
            oy + (height - 1 - row + 0.5) * res)


def extract_extremes(mask, width, height, meta, normal, windows=None):
    """One wall candidate per grid line: the OUTERMOST occupied cell.

    EVERY row (for an east/west wall) or column (for a north/south one)
    that has an occupied cell contributes exactly one point, and NOTHING
    IS FILTERED HERE - see the module header for the measurement that
    says why a band cannot be used.

    `windows` is the ONE selection this function will make, and it is a
    selection along the TANGENT and never along the normal. It exists
    because a floor can put a different true surface in front of the same
    wall over different stretches of it - warehouse_ver3's south wall has
    the dock annex over 28.00 m of its length and the four bay backs over
    the other 20.00 m - and asking "where is the annex front" is a
    different question from "where is the south wall". A caller that uses
    it says which world rectangles the windows came from; a window
    somebody drew by eye would be the band this function refuses to be.
    """
    horizontal = abs(normal[0]) > 0.5
    points = []
    if horizontal:
        cols = range(width - 1, -1, -1) if normal[0] > 0 else range(width)
        for row in range(height):
            for col in cols:
                if mask[row * width + col]:
                    point = cell_centre(meta, height, col, row)
                    if _inside(point[1], windows):
                        points.append(point)
                    break
    else:
        rows = range(height) if normal[1] > 0 else range(height - 1, -1, -1)
        for col in range(width):
            for row in rows:
                if mask[row * width + col]:
                    point = cell_centre(meta, height, col, row)
                    if _inside(point[0], windows):
                        points.append(point)
                    break
    return points


def _inside(value, windows):
    if not windows:
        return True
    return any(lo <= value <= hi for lo, hi in windows)


# ----------------------------------------------------------------------
# fitting one wall
# ----------------------------------------------------------------------

def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        raise MapError("a median of no values was asked for")
    half = n // 2
    if n % 2:
        return ordered[half]
    return 0.5 * (ordered[half - 1] + ordered[half])


def _basis(normal):
    """The wall's own (tangent, normal) frame, as unit vectors."""
    length = math.hypot(normal[0], normal[1])
    if length < 1e-12:
        raise MapError("a wall normal of zero length was given")
    n = (normal[0] / length, normal[1] / length)
    return (-n[1], n[0]), n


def repeated_median_line(points, normal):
    """Siegel's repeated median, in the wall's own frame. Returns (a, b)
    for d = a t + b, where t runs along the wall and d across it.

    IT IS THE SEED AND NOT THE ANSWER. Its value is its 50 percent
    breakdown point: half the points may lie on something that is not the
    wall and the line still comes back on the wall. It is O(n^2) in pure
    python and that is the whole cost of this module - about a second for
    a 1000-point wall, once, offline.
    """
    if len(points) < 3:
        raise MapError("a repeated median needs at least three points; "
                       "{} were given".format(len(points)))
    tangent, n = _basis(normal)
    ts = [p[0] * tangent[0] + p[1] * tangent[1] for p in points]
    ds = [p[0] * n[0] + p[1] * n[1] for p in points]
    slopes = []
    for i in range(len(ts)):
        inner = []
        for j in range(len(ts)):
            dt = ts[j] - ts[i]
            if abs(dt) > 1e-12:
                inner.append((ds[j] - ds[i]) / dt)
        if inner:
            slopes.append(_median(inner))
    if not slopes:
        raise MapError("every candidate on this wall has the same tangent "
                       "coordinate: it is a point, not a line")
    slope = _median(slopes)
    intercept = _median([d - slope * t for t, d in zip(ts, ds)])
    return slope, intercept


def _line_from_seed(slope, intercept, normal):
    """The (a, b) parametrisation as a unit normal and an offset."""
    tangent, n = _basis(normal)
    scale = math.sqrt(1.0 + slope * slope)
    unit = ((-slope * tangent[0] + n[0]) / scale,
            (-slope * tangent[1] + n[1]) / scale)
    return unit, intercept / scale


def fit_line(points, normal):
    """Total least squares: the line that minimises PERPENDICULAR scatter.

    NOT y-on-x AND NOT x-on-y. A wall that runs up the image has an
    infinite slope in one of those and a zero residual in the other, and
    the whole point of a residual here is that it is a DISTANCE. The
    returned normal is flipped to agree with the direction the world says
    the surface faces, so an offset is always positive-outward.
    """
    if len(points) < 2:
        raise MapError("a line needs at least two points; {} were "
                       "given".format(len(points)))
    n = float(len(points))
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    syy = sum((p[1] - my) ** 2 for p in points)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    angle = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    direction = (math.cos(angle), math.sin(angle))
    unit = (-direction[1], direction[0])
    if unit[0] * normal[0] + unit[1] * normal[1] < 0.0:
        unit = (-unit[0], -unit[1])
    offset = unit[0] * mx + unit[1] * my
    rms = math.sqrt(sum((unit[0] * p[0] + unit[1] * p[1] - offset) ** 2
                        for p in points) / n)
    return unit, offset, rms


def fit_line_robust(points, normal, resolution, min_points, tolerance_cells):
    """Seed with the repeated median, then trim and refit by least squares.

    THE ORDER IS THE WHOLE POINT and the module header carries the
    measurement. The tolerance has to sit ABOVE the wall's own scatter
    and BELOW the standoff of the nearest thing that is not the wall;
    inside that window the answer does not move, which is asserted in
    tests/test_map_core.py rather than asserted here.
    """
    if len(points) < min_points:
        raise MapError(
            "this wall has {} candidates against a floor of {}: a fit to "
            "fewer is a fit to a remnant".format(len(points), min_points))
    slope, intercept = repeated_median_line(points, normal)
    unit, offset = _line_from_seed(slope, intercept, normal)
    if unit[0] * normal[0] + unit[1] * normal[1] < 0.0:
        unit, offset = (-unit[0], -unit[1]), -offset
    tolerance = tolerance_cells * resolution
    kept = list(points)
    dropped = 0
    rms = 0.0
    for _ in range(TRIM_PASSES):
        survivors = [p for p in kept
                     if abs(unit[0] * p[0] + unit[1] * p[1] - offset)
                     <= tolerance]
        if len(survivors) < min_points:
            raise MapError(
                "trimming this wall at {:.3f} m left {} candidates of {}, "
                "against a floor of {}: the tolerance is below the wall's "
                "own scatter".format(tolerance, len(survivors), len(points),
                                     min_points))
        if len(survivors) == len(kept):
            break
        kept = survivors
        unit, offset, rms = fit_line(kept, normal)
    unit, offset, rms = fit_line(kept, normal)
    dropped = len(points) - len(kept)
    return LineFit(unit, offset, rms, kept, dropped)


# ----------------------------------------------------------------------
# the rigid transform world -> map
# ----------------------------------------------------------------------

def rotate(vector, theta):
    """A vector turned by theta. Public because the CALLER needs it.

    THE GRID IS NOT IN THE WORLD'S FRAME AND ON THIS TRACK IT IS HALF A
    TURN FROM IT. slam_toolbox's map frame is the odom frame, and this
    stack's odom frame is the vehicle at spawn, which stands at yaw pi -
    so the world's WEST wall is the grid's EAST side. `extract_extremes`
    decides which way to scan a grid line from the normal it is handed,
    so it has to be handed the normal IN MAP COORDINATES, which is this.
      A HINT IS ENOUGH FOR THAT and the exact angle is not needed: the
    scan direction only has to be right to within a quarter turn, and
    the transform is solved afterwards.
    """
    c, s = math.cos(theta), math.sin(theta)
    return (c * vector[0] - s * vector[1], s * vector[0] + c * vector[1])


_rotate = rotate


def solve_translation(walls, theta):
    """The translation that best fits every wall at a FIXED rotation.

    The objective is quadratic in t and one-dimensional in theta, so t is
    eliminated in closed form at each theta and only theta is searched.
    A world point p on wall i satisfies n_i . p = d_i; a map point q is
    R(theta) p + t, so the residual is (R(theta) n_i) . (q - t) - d_i.
    """
    a11 = a12 = a22 = b1 = b2 = 0.0
    for _, normal, offset, points in walls:
        nx, ny = _rotate(normal, theta)
        for qx, qy in points:
            r = nx * qx + ny * qy - offset
            a11 += nx * nx
            a12 += nx * ny
            a22 += ny * ny
            b1 += nx * r
            b2 += ny * r
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-9:
        raise MapError(
            "the walls given span only one direction, so no translation "
            "across the other one is determined by them. Two walls facing "
            "each other are one constraint, not two.")
    return ((a22 * b1 - a12 * b2) / det, (a11 * b2 - a12 * b1) / det)


def _residuals(walls, theta, t):
    out = []
    for name, normal, offset, points in walls:
        nx, ny = _rotate(normal, theta)
        base = nx * t[0] + ny * t[1] + offset
        out.append((name, [nx * qx + ny * qy - base for qx, qy in points]))
    return out


def _sse(walls, theta):
    t = solve_translation(walls, theta)
    total = 0.0
    for _, values in _residuals(walls, theta, t):
        total += sum(v * v for v in values)
    return total, t


def derive_transform(walls, hint=0.0, span_rad=DEFAULT_SPAN_RAD,
                     steps=DEFAULT_STEPS):
    """The rigid SE(2) that carries the WORLD onto this MAP.

        p_map = R(theta) p_world + t

    ROTATION AND TRANSLATION AND NOTHING ELSE. No scale: a map whose
    metres are not metres is a broken map and absorbing that into a scale
    factor would hide it in exactly the figure that exists to reveal it.
    No per-wall freedom: what a rigid transform CANNOT absorb is the
    grid's internal shear, and leaving it in the residual is what makes
    the residual mean something.

    NO INITIAL GUESS IS TRUSTED. The angle is found by scanning `steps`
    values across +-span_rad of the hint and then refining by ternary
    search - and a scan whose best value lands on its own EDGE is
    REFUSED, because the answer is then outside the window and a number
    at the edge is a clip rather than a minimum.
    """
    if len(walls) < 2:
        raise MapError("a transform needs at least two walls; {} were "
                       "given".format(len(walls)))
    thetas = [hint - span_rad + 2.0 * span_rad * i / (steps - 1.0)
              for i in range(steps)]
    scores = [_sse(walls, th)[0] for th in thetas]
    best = min(range(steps), key=lambda i: scores[i])
    if best in (0, steps - 1):
        raise MapError(
            "the best rotation found is at the edge of a +-{:.3f} deg "
            "scan, so the true one is outside it. Widen the scan rather "
            "than reporting an angle that was clipped."
            .format(math.degrees(span_rad)))
    lo = thetas[best - 1]
    hi = thetas[best + 1]
    for _ in range(80):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        if _sse(walls, m1)[0] < _sse(walls, m2)[0]:
            hi = m2
        else:
            lo = m1
    theta = 0.5 * (lo + hi)
    total, t = _sse(walls, theta)
    per_wall = []
    count = 0
    worst = 0.0
    for name, values in _residuals(walls, theta, t):
        count += len(values)
        top = max(abs(v) for v in values) if values else 0.0
        worst = max(worst, top)
        per_wall.append({
            "name": name,
            "points": len(values),
            "residual_rms_m": math.sqrt(sum(v * v for v in values)
                                        / len(values)) if values else 0.0,
            "residual_max_m": top,
        })
    return {
        "theta_rad": theta,
        "theta_deg": math.degrees(theta),
        "t_x_m": t[0],
        "t_y_m": t[1],
        "residual_rms_m": math.sqrt(total / count) if count else 0.0,
        "residual_max_m": worst,
        "n_wall_points": count,
        "walls": per_wall,
    }


def world_to_map(reg, x, y, yaw=None):
    """A world pose through a derived registration. See derive_transform."""
    theta = reg["theta_rad"]
    c, s = math.cos(theta), math.sin(theta)
    mx = c * x - s * y + reg["t_x_m"]
    my = s * x + c * y + reg["t_y_m"]
    if yaw is None:
        return (mx, my)
    return (mx, my, core.normalise_angle(yaw + theta))


def map_to_world(reg, x, y, yaw=None):
    theta = reg["theta_rad"]
    c, s = math.cos(theta), math.sin(theta)
    dx = x - reg["t_x_m"]
    dy = y - reg["t_y_m"]
    wx = c * dx + s * dy
    wy = -s * dx + c * dy
    if yaw is None:
        return (wx, wy)
    return (wx, wy, core.normalise_angle(yaw - theta))


# ----------------------------------------------------------------------
# what the world actually is
# ----------------------------------------------------------------------

_MODEL = r'<model\s+name="{}"\s*>(.*?)</model>'
_ANY_MODEL = r'<model\s+name="([^"]+)"\s*>(.*?)</model>'
_POSE = r"<pose>\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+" \
        r"([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*</pose>"
_SIZE = r"<box>\s*<size>\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+" \
        r"([-+0-9.eE]+)\s*</size>"


def _model_bodies(text):
    return re.findall(_ANY_MODEL, text, re.DOTALL)


def _model_body(text, name):
    found = re.search(_MODEL.format(re.escape(name)), text, re.DOTALL)
    if not found:
        raise MapError(
            "the world SDF has no model named {!r}. The perimeter or the "
            "obstacle set has changed shape, and this is a tool to update "
            "rather than a name to guess around.".format(name))
    return found.group(1)


def _pose_before_links(body):
    """The model's own pose - the one that stands before its first link."""
    head = body.split("<link", 1)[0]
    found = re.search(_POSE, head)
    return [float(g) for g in found.groups()] if found else [0.0] * 6


def _elements(body, tag):
    return re.findall(r"<{0}[^>]*>(.*?)</{0}>".format(tag), body, re.DOTALL)


def _box_of(body, name, tags=("collision", "visual")):
    """(pose, size) of the first box in the first element that has one."""
    model_pose = _pose_before_links(body)
    for tag in tags:
        for element in _elements(body, tag):
            size = re.search(_SIZE, element)
            if not size:
                continue
            pose = re.search(_POSE, element)
            local = [float(g) for g in pose.groups()] if pose else [0.0] * 6
            yaw = model_pose[5] + local[5]
            if abs(yaw) > 1e-9:
                raise MapError(
                    "model {!r} carries a box at yaw {:.6f} rad. This "
                    "module measures AXIS-ALIGNED footprints, and "
                    "projecting a rotated box onto the axes would silently "
                    "make it bigger than it is.".format(name, yaw))
            return ([model_pose[i] + local[i] for i in range(3)],
                    [float(g) for g in size.groups()])
    return None


def sdf_box(text, name):
    """One named model's axis-aligned footprint, in world metres."""
    found = _box_of(_model_body(text, name), name)
    if found is None:
        raise MapError(
            "model {!r} has no box geometry: its footprint is not a "
            "rectangle and this module will not invent one.".format(name))
    centre, size = found
    return Box(name,
               centre[0] - size[0] / 2.0, centre[0] + size[0] / 2.0,
               centre[1] - size[1] / 2.0, centre[1] + size[1] / 2.0)


def sdf_obstacles(text):
    """Every model a vehicle could hit: a box COLLISION and nothing else.

    A VISUAL IS NOT AN OBSTACLE and neither is a plane. warehouse_ver3's
    floor paint, its lane marks, its station discs and the pallet loads
    on top of the racking are all visual-only - they carry no <collision>
    at all - and the floor's own collision is a <plane>. Including any of
    them would report a clearance figure about a thing the truck drives
    straight over.
    """
    boxes = []
    for name, body in _model_bodies(text):
        found = _box_of(body, name, tags=("collision",))
        if found is None:
            continue
        centre, size = found
        boxes.append(Box(name,
                         centre[0] - size[0] / 2.0, centre[0] + size[0] / 2.0,
                         centre[1] - size[1] / 2.0, centre[1] + size[1] / 2.0))
    return boxes


def outer_face(box, normal):
    """The offset d of the face on the FAR side: max(n.p).

    inner_face's pair. Together the two give a wall its thickness, and a
    building its fabric - see grid_census, which needs both to tell a
    wall cell from a cell that is genuinely outside the building.
    """
    corners = ((box.x0, box.y0), (box.x0, box.y1),
               (box.x1, box.y0), (box.x1, box.y1))
    return max(normal[0] * x + normal[1] * y for x, y in corners)


def inner_face(box, normal):
    """The offset d of the face a lidar inside the hall sees: min(n.p).

    IT DOES NOT ASSUME THE HALL IS CENTRED ON THE ORIGIN.
    warehouse_ver3's floor is centred on y = -2.00, so an inner face
    taken as abs(centre) - half - which is what the m5_ver1 tool did, on
    a hall that WAS centred - would be wrong on this floor by 2.00 m on
    two of the four walls and right on the other two.
    """
    corners = ((box.x0, box.y0), (box.x0, box.y1),
               (box.x1, box.y0), (box.x1, box.y1))
    return min(normal[0] * x + normal[1] * y for x, y in corners)


# ----------------------------------------------------------------------
# does the drive fit the floor
# ----------------------------------------------------------------------

def rect_distance(px, py, box):
    """Point to axis-aligned rectangle. Zero inside, never negative."""
    dx = max(box.x0 - px, 0.0, px - box.x1)
    dy = max(box.y0 - py, 0.0, py - box.y1)
    return math.hypot(dx, dy)


def truck_polygon(x, y, yaw, fore, aft, half_width):
    """The vehicle's outline about a base_link pose, four corners.

    `fore` REACHES TOWARDS MODEL -x, because that is this vehicle's
    travel direction: model yaw 0 points the forks at world -x, so the
    fork tips are at NEGATIVE model x and the counterweight at positive.
    A tool that put the long end the other way round would report a
    generous clearance in front of the forks and a mean one behind the
    counterweight, on a truck that drives forks first.
    """
    local = ((-fore, -half_width), (-fore, half_width),
             (aft, half_width), (aft, -half_width))
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x + c * lx - s * ly, y + s * lx + c * ly) for lx, ly in local]


def box_polygon(box):
    return [(box.x0, box.y0), (box.x1, box.y0),
            (box.x1, box.y1), (box.x0, box.y1)]


def _axes(poly):
    out = []
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        ex, ey = bx - ax, by - ay
        length = math.hypot(ex, ey)
        if length > 1e-12:
            out.append((-ey / length, ex / length))
    return out


def _project(poly, axis):
    values = [p[0] * axis[0] + p[1] * axis[1] for p in poly]
    return min(values), max(values)


def _segment_distance(px, py, ax, ay, bx, by):
    ex, ey = bx - ax, by - ay
    length2 = ex * ex + ey * ey
    if length2 < 1e-18:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * ex + (py - ay) * ey) / length2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * ex), py - (ay + t * ey))


def polygon_distance(a, b):
    """Distance between two CONVEX polygons; zero when they overlap.

    Separating axis first, because an overlap has to answer zero and not
    a small positive number - a truck 0.1 m inside a rack leg is not
    0.1 m of clearance.
    """
    for axis in _axes(a) + _axes(b):
        alo, ahi = _project(a, axis)
        blo, bhi = _project(b, axis)
        if ahi < blo or bhi < alo:
            break
    else:
        return 0.0
    best = float("inf")
    for poly, other in ((a, b), (b, a)):
        for px, py in poly:
            for i in range(len(other)):
                ax, ay = other[i]
                bx, by = other[(i + 1) % len(other)]
                best = min(best, _segment_distance(px, py, ax, ay, bx, by))
    return best


def path_clearance(xs, ys, yaws, boxes, fore, aft, half_width):
    """The worst gap between the driven outline and any obstacle.

    THIS IS THE CHECK A PROFILE'S FLOOR ARITHMETIC IS A PREDICTION OF.
    config.yaml's drive_route: block argues, corridor by corridor, that a
    manoeuvre fits; this measures what the truck ACTUALLY swept against
    the world's own rectangles, and the two are meant to be read
    together. It takes the recorded ground truth and not the estimate,
    because where the truck was is not a thing an estimator is asked.
    """
    radius = math.hypot(max(fore, aft), half_width)
    best = {"clearance_m": float("inf"), "index": -1, "obstacle": "",
            "x": 0.0, "y": 0.0}
    for i in range(len(xs)):
        poly = None
        for box in boxes:
            # A CHEAP REJECT FIRST. The outline is inside a circle of
            # `radius` about base_link, so anything further than the
            # current best plus that radius cannot win, and building its
            # polygon would be wasted.
            coarse = rect_distance(xs[i], ys[i], box) - radius
            if coarse >= best["clearance_m"]:
                continue
            if poly is None:
                poly = truck_polygon(xs[i], ys[i], yaws[i], fore, aft,
                                     half_width)
            gap = polygon_distance(poly, box_polygon(box))
            if gap < best["clearance_m"]:
                best = {"clearance_m": gap, "index": i, "obstacle": box.name,
                        "x": xs[i], "y": ys[i]}
    return best


# ----------------------------------------------------------------------
# does the map cover the floor
# ----------------------------------------------------------------------

def hall_rectangle(faces):
    """The building's inner rectangle from four (normal, offset) faces.

    A face n.p = d is a half-plane n.p <= d for everything inside, so an
    axis normal of (+1, 0) at d = 24.000 is `x <= 24.000` and one of
    (-1, 0) at the same d is `x >= -24.000`. Four of them are a
    rectangle, and it is derived from the world SDF rather than typed in
    because a hall that changes shape has to change this number too.
    """
    limits = {}
    for normal, offset in faces:
        if abs(normal[0]) > 0.5:
            key = "x1" if normal[0] > 0 else "x0"
            limits[key] = offset if normal[0] > 0 else -offset
        elif abs(normal[1]) > 0.5:
            key = "y1" if normal[1] > 0 else "y0"
            limits[key] = offset if normal[1] > 0 else -offset
        else:
            raise MapError(
                "a hall face has a normal of ({:+.4f}, {:+.4f}), which is "
                "not an axis. This builds an axis-aligned rectangle and "
                "will not pretend a diagonal wall is one."
                .format(normal[0], normal[1]))
    for key in ("x0", "x1", "y0", "y1"):
        if key not in limits:
            raise MapError(
                "the hall is four faces and {} is missing: a rectangle "
                "cannot be built from fewer".format(key))
    return Box("hall", limits["x0"], limits["x1"], limits["y0"],
               limits["y1"])


def overlap_area(a, b):
    """The area two axis-aligned rectangles share. Zero if they miss."""
    dx = min(a.x1, b.x1) - max(a.x0, b.x0)
    dy = min(a.y1, b.y1) - max(a.y0, b.y0)
    return max(0.0, dx) * max(0.0, dy)


def open_floor_area(hall, boxes):
    """The hall's area less every obstacle footprint inside it.

    IT ASSUMES THE OBSTACLES DO NOT OVERLAP EACH OTHER, which is true of
    warehouse_ver3 - twelve rack segments, five annex blocks, four bay
    backs and four walls, none of them touching - and would over-count
    the deduction if it ever stopped being true. Stated rather than
    checked, because checking it needs a polygon library this module
    does not have and the world is one file anybody can read.
    """
    return (hall.x1 - hall.x0) * (hall.y1 - hall.y0) - sum(
        overlap_area(hall, box) for box in boxes)


def _contains(box, x, y):
    return box.x0 <= x <= box.x1 and box.y0 <= y <= box.y1


def grid_census(grid, meta, reg, hall, building, to_world):
    """Every cell counted, and told WHERE it is in three zones.

    THE QUESTION IS WHETHER THE MAP COVERS THE FLOOR, and there are two
    halves to it that a single number would hide. How much of the open
    floor is marked FREE - which is coverage - and how much of what the
    map claims falls OUTSIDE the building altogether, which is the
    opposite and is the shape a diverged run takes.

    THREE ZONES AND NOT TWO, AND THE MIDDLE ONE IS THE WALLS THEMSELVES.
    `hall` is the building's INNER rectangle - the four walls' inner
    faces - and a wall's own occupied cells sit ON that line, so a scan
    whose return lands two centimetres proud of it is outside `hall` and
    is not outside anything. `building` is the same four walls' OUTER
    faces; the band between the two is the fabric of the building and a
    cell there is a wall, not a finding. Measured on warehouse_v3: 933
    occupied cells fall in that 0.20 m band and none at all beyond it, so
    reporting the first number as "outside the building" would have
    turned the walls into evidence of divergence.

    `to_world` is passed in rather than imported so this stays pure
    arithmetic over whatever transform the caller derived.
    """
    counts = {"occupied_hall": 0, "occupied_fabric": 0,
              "occupied_outside": 0, "free_hall": 0, "free_fabric": 0,
              "free_outside": 0, "unknown": 0}
    occupied = occupied_mask(grid, meta)
    negate = meta.get("negate", 0.0) > 0.5
    free_limit = meta.get("free_thresh", 0.196)
    for row in range(grid.height):
        base = row * grid.width
        for col in range(grid.width):
            value = grid.pixels[base + col]
            shade = (value if negate else (grid.maxval - value)) / float(
                grid.maxval)
            if not occupied[base + col] and shade >= free_limit:
                counts["unknown"] += 1
                continue
            x, y = cell_centre(meta, grid.height, col, row)
            wx, wy = to_world(reg, x, y)
            if _contains(hall, wx, wy):
                zone = "_hall"
            elif _contains(building, wx, wy):
                zone = "_fabric"
            else:
                zone = "_outside"
            counts[("occupied" if occupied[base + col] else "free")
                   + zone] += 1
    counts["cells"] = grid.width * grid.height
    counts["cell_area_m2"] = meta["resolution"] ** 2
    return counts


# ----------------------------------------------------------------------
# the absolute score
# ----------------------------------------------------------------------

def span_between(a, b):
    """How far apart two facing surfaces are, from their fitted lines.

    IT NEEDS NO REGISTRATION AND THAT IS WHY IT IS THE SCORE. A span is a
    distance between two things INSIDE the map, so the transform that
    carries the map onto the world cannot flatter it: a grid whose metres
    are 1 % long reports a 48.00 m hall as 48.48 m however it is
    registered.
    """
    dot = a.normal[0] * b.normal[0] + a.normal[1] * b.normal[1]
    if dot > -0.9:
        raise MapError(
            "a span is measured between two surfaces that FACE each "
            "other; these two normals have a dot product of {:+.4f}, so "
            "the number would be a projection and not a width"
            .format(dot))
    return a.offset + b.offset


def wall_rotation(fit, world_normal):
    """How far this fitted wall sits off where the world says it faces."""
    return core.normalise_angle(
        math.atan2(fit.normal[1], fit.normal[0])
        - math.atan2(world_normal[1], world_normal[0]))


# ----------------------------------------------------------------------
# --selftest
# ----------------------------------------------------------------------

def _selftest():
    """The three claims this module would be useless if it got wrong.

    IT IS NOT tests/test_map_core.py AND DOES NOT TRY TO BE. The pytest
    file is the suite; this is what an operator on the rig can run with
    nothing installed, and it checks the three things that would make
    every figure downstream wrong without looking wrong: that a rigid
    transform comes back out, that a contaminated wall is fitted to the
    WALL, and that an overlap reads zero.
    """
    failures = []

    def check(label, ok):
        if not ok:
            failures.append(label)

    theta, tx, ty = math.radians(-0.4535), 6.0292, 5.5415
    c, s = math.cos(theta), math.sin(theta)
    walls = []
    for name, normal, offset, lo, hi in (
            ("N", (0.0, 1.0), 14.0, -24.0, 24.0),
            ("E", (1.0, 0.0), 24.0, -18.0, 14.0),
            ("W", (-1.0, 0.0), 24.0, -18.0, 14.0)):
        pts = []
        n = lo
        while n <= hi:
            x = offset * normal[0] if abs(normal[0]) > 0.5 else n
            y = offset * normal[1] if abs(normal[1]) > 0.5 else n
            pts.append((c * x - s * y + tx, s * x + c * y + ty))
            n += 0.10
        walls.append((name, normal, offset, pts))
    reg = derive_transform(walls)
    check("the rigid transform is recovered",
          abs(reg["theta_rad"] - theta) < 1e-6
          and abs(reg["t_x_m"] - tx) < 1e-5
          and abs(reg["t_y_m"] - ty) < 1e-5)
    check("a recovered transform has no residual",
          reg["residual_max_m"] < 1e-6)

    wall = [(x / 20.0, 14.0) for x in range(-400, 160)]
    rack = [(x / 20.0, 13.5) for x in range(161, 400)]
    fit = fit_line_robust(wall + rack, (0.0, 1.0), 0.05, 50, 3.0)
    check("a contaminated wall is fitted to the WALL",
          abs(fit.offset - 14.0) < 1e-6 and fit.dropped == len(rack))
    _, dragged, _ = fit_line(wall + rack, (0.0, 1.0))
    check("and the least-squares fit of the same points is dragged",
          dragged < 13.95)

    box = Box("b", -1.0, 1.0, -1.0, 1.0)
    check("an overlap is zero clearance",
          polygon_distance(truck_polygon(0.0, 0.0, 0.0, 1.9, 0.9, 0.6),
                           box_polygon(box)) == 0.0)
    check("and a gap is the gap",
          abs(polygon_distance(truck_polygon(5.0, 0.0, 0.0, 1.0, 1.0, 0.5),
                               box_polygon(box)) - 3.0) < 1e-9)

    for label in failures:
        sys.stderr.write("map_core --selftest FAILED: {}\n".format(label))
    if failures:
        return 1
    print("map_core --selftest: 6 checks passed.")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--selftest"]:
        return _selftest()
    sys.stderr.write(
        "map_core.py is imported, not run. Its only argument is "
        "--selftest;\nthe program that puts files in front of it is "
        "tools/map_register.py.\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
