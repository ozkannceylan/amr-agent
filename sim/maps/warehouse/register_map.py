#!/usr/bin/env python3
"""register_map.py - derive T(world -> map) from a committed occupancy grid.

WHY THIS FILE EXISTS, AND WHY IT LIVES HERE

  A SLAM map's frame is its own. `map` is anchored wherever the estimator
  happened to think the vehicle was when the mapper processed its first
  scan, and it is rotated from the building by whatever heading error the
  estimator carried at that instant. That is not a defect - AMCL localises
  inside the map and never asks where the building is.

  But a LOCALISATION SCORE does ask. Scoring AMCL means differencing its
  `map -> base_link` against the simulator's world-frame ground truth, and
  that difference is meaningless without the transform between the two
  frames. If that transform is taken from the run being scored - by
  anchoring the estimate onto truth at the first sample - the score is
  circular: an estimator that is consistently 0.3 m wrong scores near zero
  (docs/reports/m5-08c-slam-judge.md finding 2).

  So the transform has to be fixed BEFORE the run and DERIVED FROM THE
  ARTIFACT, not from the run. This tool derives it, prints it with its
  residual, and writes it beside the map it registers so the pair travels
  together. One owner, one file (CLAUDE.md invariant 10).

  IT MUST BE RE-DERIVED FOR EVERY REGENERATED MAP, and that is enforced
  rather than requested: the registration file records the md5 of the grid
  it was derived from, and `load_registration()` REFUSES a grid whose md5
  does not match. A rebuilt map draws a new gyro bias sign, a new idle and
  a new first-scan pose; its rotation is a different number, and nothing
  downstream may ever carry this one across a rebuild.

WHAT IS DERIVED, PLAINLY

      p_map = R(theta) * p_world + t

  theta and t are found by least squares: the four perimeter walls are
  extracted from the grid as point sets, the same four walls are read from
  the world file as lines, and the single rigid SE(2) transform that best
  carries the world lines onto the grid points is solved for. Nothing is
  asserted, nothing is copied from a prose paragraph, and no number from a
  run enters the calculation.

WHAT THE RESIDUAL MEANS, AND WHY IT IS THE HEADLINE

  A grid built by a scan matcher is not exactly rigid: its walls can be
  slightly non-perpendicular to each other, and no rigid transform can fix
  that. The residual printed below is the largest perpendicular distance
  between a wall point in the grid and where the transform says that wall
  should be. IT IS THE FLOOR UNDER EVERY LOCALISATION NUMBER MEASURED
  THROUGH THIS TRANSFORM, and it is printed first for that reason. A
  localisation error smaller than the residual is not a measurement of the
  localiser.

METHOD, IN FULL, SO IT CAN BE ARGUED WITH

  1. Parse the PGM (P5, binary) and its yaml. Cells are classified with
     the yaml's own thresholds, not with hard-coded numbers.
  2. Read the perimeter walls out of the world SDF: each wall model's box
     pose and size, reduced to the INNER FACE - the face nearer the hall
     centre, which is the surface a lidar sees.
  3. For each wall, take the extreme occupied cell per grid row (east and
     west walls) or per grid column (north and south walls). EVERY row or
     column is taken; there is no pre-filter. What is not on the wall is
     removed by the trimming rule in step 4 and by nothing else.
  4. THE TRIMMING RULE - a wall is a line. Seed with a repeated-median
     line (50 % breakdown), drop every extreme further than --trim-cells
     cells from it, refit by least squares, repeat to convergence. See
     `fit_line_robust` for why the seed cannot be least squares and what
     happens when it is. Kept and dropped counts are printed per wall, so
     a wall fitted from a remnant is visible rather than hidden, and a
     wall whose survivors fall under --min-points is REFUSED rather than
     fitted.
  5. Solve for theta by scanning it and solving t in closed form at each
     step (the objective is quadratic in t and one-dimensional in theta),
     then refine by ternary search, over the KEPT points only. Report the
     per-wall rotation as well as the common one: their SPREAD is the
     grid's internal shear, which a rigid transform cannot absorb and
     which the residual therefore contains.

  Standard library only. No numpy, no yaml module, no ROS.

USAGE

  python3 sim/maps/warehouse/register_map.py derive
  python3 sim/maps/warehouse/register_map.py derive --write
  python3 sim/maps/warehouse/register_map.py show
  python3 sim/maps/warehouse/register_map.py derive \\
      --map /path/other.yaml --world /path/other.sdf --write --out /path/reg.yaml

  `derive` alone prints and writes nothing. `--write` is the deliberate
  act of committing a registration.
"""

import argparse
import hashlib
import math
import os
import re
import sys
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, '..', '..', '..'))

DEFAULT_MAP_YAML = os.path.join(_THIS_DIR, 'warehouse.yaml')
DEFAULT_WORLD = os.path.join(_REPO_ROOT, 'sim', 'worlds', 'warehouse.sdf')
DEFAULT_REGISTRATION = os.path.join(_THIS_DIR, 'warehouse_registration.yaml')

#: The four perimeter wall models of sim/worlds/warehouse.sdf, and the
#: outward direction of each. The NAMES are read from the world file; only
#: which side of the hall each one is on is stated here, because that is a
#: property of the building and not of the file format. A wall model that
#: is not on this list is not used for registration.
WALL_MODELS = {
    'WallNorth': (0.0, 1.0),
    'WallSouthWest': (0.0, -1.0),
    'WallSouthEast': (0.0, -1.0),
    'WallEast': (1.0, 0.0),
    'WallWest': (-1.0, 0.0),
}


# --------------------------------------------------------------------------- #
# reading the artifacts
# --------------------------------------------------------------------------- #

def md5(path):
    digest = hashlib.md5()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_map_yaml(path):
    """The nav2 map yaml, parsed without a yaml module.

    Only the six scalar keys nav2 writes are understood; anything else in
    the file is ignored rather than guessed at."""
    out = {}
    with open(path, 'r', encoding='utf-8') as handle:
        text = handle.read()
    for key in ('image', 'mode'):
        match = re.search(r'^\s*{}\s*:\s*(\S+)\s*$'.format(key), text,
                          re.MULTILINE)
        if match:
            out[key] = match.group(1).strip()
    for key in ('resolution', 'occupied_thresh', 'free_thresh', 'negate'):
        match = re.search(r'^\s*{}\s*:\s*([-+0-9.eE]+)'.format(key), text,
                          re.MULTILINE)
        if match:
            out[key] = float(match.group(1))
    match = re.search(
        r'^\s*origin\s*:\s*\[\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*,'
        r'\s*([-+0-9.eE]+)\s*\]', text, re.MULTILINE)
    if not match:
        raise SystemExit('no origin: [x, y, yaw] in {}'.format(path))
    out['origin'] = tuple(float(match.group(i)) for i in (1, 2, 3))
    for required in ('image', 'resolution'):
        if required not in out:
            raise SystemExit('no {}: in {}'.format(required, path))
    out.setdefault('occupied_thresh', 0.65)
    out.setdefault('free_thresh', 0.196)
    out.setdefault('negate', 0.0)
    return out


def read_pgm(path):
    """A binary PGM (P5). Returns (width, height, maxval, bytes).

    Written out rather than taken from a library because the whole point
    of this tool is that it introduces no dependency."""
    with open(path, 'rb') as handle:
        data = handle.read()
    if data[:2] != b'P5':
        raise SystemExit('{} is not a binary PGM (P5)'.format(path))
    fields = []
    index = 2
    while len(fields) < 3:
        while index < len(data) and data[index:index + 1].isspace():
            index += 1
        if data[index:index + 1] == b'#':
            while index < len(data) and data[index:index + 1] not in b'\r\n':
                index += 1
            continue
        start = index
        while index < len(data) and not data[index:index + 1].isspace():
            index += 1
        fields.append(int(data[start:index]))
    index += 1                       # exactly one whitespace byte after maxval
    width, height, maxval = fields
    pixels = data[index:index + width * height]
    if len(pixels) != width * height:
        raise SystemExit('{}: {} pixel bytes for a {}x{} image'.format(
            path, len(pixels), width, height))
    return width, height, maxval, pixels


def occupied_mask(width, height, maxval, pixels, meta):
    """Occupied cells, by the yaml's OWN thresholds.

    nav2's trinary convention: p = (maxval - value) / maxval is the
    occupancy probability, and p > occupied_thresh is occupied. `negate: 1`
    inverts the greyscale first. Reading the thresholds from the file the
    map ships with is the difference between measuring this artifact and
    measuring an assumption about it."""
    negate = meta['negate'] > 0.5
    limit = meta['occupied_thresh']
    out = bytearray(width * height)
    table = bytearray(maxval + 1)
    for value in range(maxval + 1):
        shade = (maxval - value) if not negate else value
        table[value] = 1 if (shade / float(maxval)) > limit else 0
    for index, value in enumerate(pixels):
        out[index] = table[value]
    return out


def read_world_walls(path, models=WALL_MODELS):
    """Inner faces of the perimeter walls, from the world file itself.

    Returns a list of (name, normal, offset) with the OUTWARD unit normal
    and the offset d of the inner face, so that a point on the face
    satisfies n . p = d. Both come from the model's <pose> and its box
    <size>: the inner face is the one nearer the hall centre, which is the
    surface a lidar at z = 1.80 m returns from."""
    with open(path, 'r', encoding='utf-8') as handle:
        text = handle.read()
    walls = []
    for name, normal in sorted(models.items()):
        block = re.search(
            r'<model\s+name="{}">(.*?)</model>'.format(re.escape(name)),
            text, re.DOTALL)
        if not block:
            raise SystemExit(
                'world file {} has no <model name="{}">; the perimeter has '
                'changed shape and this tool must be updated rather than '
                'guessed around'.format(path, name))
        body = block.group(1)
        pose = re.search(r'<pose>\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+'
                         r'([-+0-9.eE]+)', body)
        size = re.search(r'<size>\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+'
                         r'([-+0-9.eE]+)', body)
        if not pose or not size:
            raise SystemExit('{}: no box pose/size found'.format(name))
        centre = (float(pose.group(1)), float(pose.group(2)))
        half = (float(size.group(1)) / 2.0, float(size.group(2)) / 2.0)
        # Outward normal, so the inner face is half a thickness back
        # towards the hall centre.
        axis = 0 if abs(normal[0]) > 0.5 else 1
        offset = abs(centre[axis]) - half[axis]
        walls.append((name, normal, offset))
    return walls


# --------------------------------------------------------------------------- #
# extracting the walls from the grid
# --------------------------------------------------------------------------- #

def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        raise SystemExit('median of an empty set')
    mid = n // 2
    return ordered[mid] if n % 2 else 0.5 * (ordered[mid - 1] + ordered[mid])


def extract_wall(mask, width, height, meta, normal):
    """Candidate points on one wall, in MAP metres.

    The candidate is the extreme occupied cell in the outward direction:
    for an east-facing normal, the rightmost occupied cell of each row;
    for a north-facing normal, the topmost occupied cell of each column.

    EVERY row or column that has an occupied cell contributes one
    candidate, and NOTHING IS FILTERED HERE. An earlier version of this
    function kept only the candidates within a fixed distance of the
    median extreme, which is an axis-aligned band; the walls of this grid
    are rotated ~1.8 deg from the grid axes, so across the 30 m hall a
    +-0.60 m band clips 1.05 m of genuine wall - and it clips it at the
    two ENDS, which are the points that determine the angle best. Measured
    on the m5-08b grid: the band threw away 82 of 343 real north-wall
    points and 42 of 404 real south-wall points, and moved the fitted
    north angle by 0.04 deg. A band cannot be widened out of this, because
    a band wide enough to hold a tilted wall is wide enough to hold the
    racking in front of it. Selection is the trimming rule's job
    (`fit_line_robust`) and no other's."""
    resolution = meta['resolution']
    ox, oy, _ = meta['origin']

    def to_world(col, row):
        # nav2 convention: origin is the LOWER-LEFT corner of the image, and
        # PGM row 0 is the TOP row. Cell centres.
        return (ox + (col + 0.5) * resolution,
                oy + (height - 1 - row + 0.5) * resolution)

    points = []
    if abs(normal[0]) > 0.5:                       # east or west wall
        cols = range(width - 1, -1, -1) if normal[0] > 0 else range(width)
        for row in range(height):
            base = row * width
            for col in cols:
                if mask[base + col]:
                    points.append(to_world(col, row))
                    break
    else:                                          # north or south wall
        rows = range(height) if normal[1] > 0 else range(height - 1, -1, -1)
        for col in range(width):
            for row in rows:
                if mask[row * width + col]:
                    points.append(to_world(col, row))
                    break
    return points


def repeated_median_line(points, normal):
    """Siegel's repeated-median line. Returns (unit normal, offset).

    This is the SEED for the trimming rule, and it is a repeated median
    rather than anything cheaper because it is the standard fit with a
    50 % breakdown point: it returns the line the majority of the points
    lie on even when almost half of them lie on a different surface
    entirely. Slope = median over i of (median over j of the pairwise
    slope through i and j); intercept = median of the residual offsets at
    that slope.

    The wall is parametrised as `d = slope * t + intercept` with t along
    the wall and d along its normal, which is well conditioned here
    because the walls are within a couple of degrees of the grid axes -
    the vertical-line degeneracy of a y-on-x fit cannot be reached.

    O(n^2) in pure Python: ~0.4 s for the 614-point walls of this grid,
    which is the whole cost of the tool."""
    axis = 0 if abs(normal[0]) > 0.5 else 1     # along the wall's normal
    tan = 1 - axis                              # along the wall
    slopes = []
    n = len(points)
    for i in range(n):
        ti, di = points[i][tan], points[i][axis]
        inner = []
        for j in range(n):
            if i == j:
                continue
            tj, dj = points[j][tan], points[j][axis]
            if abs(tj - ti) < 1e-9:
                continue
            inner.append((dj - di) / (tj - ti))
        if inner:
            slopes.append(_median(inner))
    if not slopes:
        return None
    slope = _median(slopes)
    intercept = _median([p[axis] - slope * p[tan] for p in points])
    vec = (-slope, 1.0) if axis == 1 else (1.0, -slope)
    length = math.hypot(vec[0], vec[1])
    vec = (vec[0] / length, vec[1] / length)
    if vec[0] * normal[0] + vec[1] * normal[1] < 0.0:
        vec = (-vec[0], -vec[1])
    on_line = (intercept, 0.0) if axis == 0 else (0.0, intercept)
    return vec, vec[0] * on_line[0] + vec[1] * on_line[1]


def fit_line_robust(points, normal, resolution, min_points, tolerance_cells):
    """Fit a wall line, discarding what is not on the wall.

    WHAT IS BEING DISCARDED. Rack row A stands against the north wall and
    the dock stations against the south, so in every column where the wall
    itself was never observed the extreme occupied cell is a rack or a
    station face a few tens of centimetres in front of it. Those points
    are not noise on the wall - they are a different surface - and
    averaging them in tilts the fitted line and inflates the residual with
    a quantity that is not registration error. Measured on the m5-08b
    grid, leaving them in fitted the north wall with an rms of 0.304 m
    (six cells) and turned its apparent rotation the wrong way, -1.32 deg
    against +1.81 deg on the east and west walls.

    THE RULE, STATED ONCE AND APPLIED TO ALL FOUR WALLS EQUALLY: seed with
    a repeated-median line, drop every point further than
    `tolerance_cells` cells from the current line, refit by least squares,
    repeat until the kept set stops changing. No wall gets its own
    tolerance, no wall gets its own seed, and no point is removed by hand.
    If the survivors fall under `min_points` the wall is REFUSED rather
    than fitted, because a line through the few points that happen to
    agree is not a measurement of a wall.

    THE SEED CANNOT BE LEAST SQUARES, AND THIS IS THE MEASUREMENT THAT
    SAYS SO. A least-squares seed is dragged towards the contaminating
    surface, and the trim then converges onto THAT surface and reports a
    tight fit to it. On the m5-08b north wall, seeded by least squares and
    trimmed at 2, 3, 4 and 6 cells, this function returns -1.61, -1.80,
    -1.43 and -1.32 deg - the sign of the racking, not of the building -
    with an rms as low as 0.0295 m. A small residual against the wrong
    surface is the worst failure available here, because it looks like
    success. Seeded by the repeated median the same four tolerances return
    +1.69, +1.69, +1.69 and +1.69 deg at an rms of 0.021-0.026 m,
    agreeing with the east and west walls to within the grid's own shear.

    CHOOSING `tolerance_cells`. It must be larger than the wall's own
    scatter, so that a converged fit is not cut off by its own threshold,
    and smaller than the standoff of the nearest non-wall surface. On this
    grid the wall scatter is ~0.02 m rms and rack row A stands 0.35-0.55 m
    off the north wall, so anything from 2 to 6 cells (0.10-0.30 m) is
    inside that window - and across that whole window the fitted angle
    moves by less than 0.01 deg. The default of 3 cells (0.15 m) is the
    middle of it. The choice is therefore not load-bearing; the SEED is.

    Returns (normal, offset, rms, kept_points, dropped) or None."""
    tolerance = tolerance_cells * resolution
    seed = repeated_median_line(points, normal)
    if seed is None:
        return None
    unit, offset = seed
    kept = list(points)
    for _ in range(20):
        survivors = [p for p in kept
                     if abs(unit[0] * p[0] + unit[1] * p[1] - offset)
                     <= tolerance]
        if len(survivors) < min_points:
            break
        if len(survivors) == len(kept):
            break
        kept = survivors
        fit = fit_line(kept, normal)
        if fit is None:
            break
        unit, offset = fit[0], fit[1]
    fit = fit_line(kept, normal)
    if fit is None:
        return None
    return fit[0], fit[1], fit[2], kept, len(points) - len(kept)


def fit_line(points, normal):
    """Least-squares line through a wall's points.

    Returns (unit normal in the MAP frame, offset, rms residual). The
    normal's sign is chosen to agree with the world wall's outward normal,
    so the two are directly comparable."""
    n = len(points)
    if n < 2:
        return None
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    syy = sum((p[1] - my) ** 2 for p in points)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    # Total least squares: the direction is the principal axis.
    angle = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    direction = (math.cos(angle), math.sin(angle))
    fitted = (-direction[1], direction[0])
    if fitted[0] * normal[0] + fitted[1] * normal[1] < 0.0:
        fitted = (-fitted[0], -fitted[1])
    offset = fitted[0] * mx + fitted[1] * my
    rms = math.sqrt(sum((fitted[0] * p[0] + fitted[1] * p[1] - offset) ** 2
                        for p in points) / n)
    return fitted, offset, rms


# --------------------------------------------------------------------------- #
# the transform
# --------------------------------------------------------------------------- #

def _solve_t(theta, walls):
    """The translation that best satisfies every wall at this theta.

    For wall i the constraint on a grid point p is

        R(theta) n_i . (p - t) = d_i

    which is linear in t, so t is the solution of a 2x2 normal equation.
    Returns (t, sse, residual_by_wall)."""
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    a11 = a12 = a22 = b1 = b2 = 0.0
    rotated = []
    for _, normal, offset, points in walls:
        nx = normal[0] * cos_t - normal[1] * sin_t
        ny = normal[0] * sin_t + normal[1] * cos_t
        rotated.append((nx, ny))
        for px, py in points:
            residual = nx * px + ny * py - offset      # = n . t  when perfect
            a11 += nx * nx
            a12 += nx * ny
            a22 += ny * ny
            b1 += nx * residual
            b2 += ny * residual
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-12:
        raise SystemExit(
            'the extracted walls are degenerate: they do not span two '
            'directions, so no translation is determined. Check the --band '
            'and the extracted point counts.')
    tx = (a22 * b1 - a12 * b2) / det
    ty = (a11 * b2 - a12 * b1) / det
    sse = 0.0
    per_wall = []
    for (nx, ny), (name, _, offset, points) in zip(rotated, walls):
        errs = [nx * px + ny * py - (nx * tx + ny * ty) - offset
                for px, py in points]
        sse += sum(e * e for e in errs)
        per_wall.append((name, errs))
    return (tx, ty), sse, per_wall


def derive_transform(walls, theta_hint=0.0, span_rad=math.radians(8.0)):
    """theta and t of p_map = R(theta) p_world + t, by least squares.

    theta is one-dimensional and the objective is quadratic in t, so the
    solve is a scan over theta with t eliminated in closed form, refined by
    ternary search. No initial guess is trusted: the scan spans +-8 deg
    around the hint, which is wider than any drift this stack has produced.
    """
    steps = 401
    best = None
    for index in range(steps):
        theta = theta_hint - span_rad + 2.0 * span_rad * index / (steps - 1)
        _, sse, _ = _solve_t(theta, walls)
        if best is None or sse < best[1]:
            best = (theta, sse)
    lo = best[0] - 2.0 * span_rad / (steps - 1)
    hi = best[0] + 2.0 * span_rad / (steps - 1)
    for _ in range(80):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        if _solve_t(m1, walls)[1] <= _solve_t(m2, walls)[1]:
            hi = m2
        else:
            lo = m1
    theta = 0.5 * (lo + hi)
    translation, sse, per_wall = _solve_t(theta, walls)
    return theta, translation, sse, per_wall


# --------------------------------------------------------------------------- #
# the registration file
# --------------------------------------------------------------------------- #

_REG_HEADER = """\
# warehouse_registration.yaml - T(world -> map) for the grid named below.
#
# DERIVED, NOT ASSERTED. Every number in this file was computed by
# register_map.py from the committed grid and the committed world file; no
# figure from any run entered the calculation. Re-derive with
#
#     python3 sim/maps/warehouse/register_map.py derive
#
# THIS FILE IS BOUND TO ONE GRID. map_md5 below is the md5 of the .pgm this
# transform was derived from. A regenerated map draws a new gyro bias sign,
# a new pre-drive idle and a new first-scan pose, so its rotation from the
# building is a DIFFERENT NUMBER: load_registration() refuses a grid whose
# md5 does not match, and nothing downstream may carry this transform
# across a rebuild.
#
# THE RESIDUAL IS THE FLOOR. residual_max_m is the largest perpendicular
# distance between a wall point in the grid and where this transform says
# that wall is. No rigid transform fits this grid to the building better
# than that, so no localisation error smaller than it is a measurement of
# the localiser.
#
#   p_map = R(theta) * p_world + t
#
"""


def write_registration(path, record):
    lines = [_REG_HEADER]
    for key in ('map_yaml', 'map_image', 'map_md5', 'map_yaml_md5',
                'world_sdf', 'world_md5', 'derived_utc', 'tool'):
        lines.append('{}: {}\n'.format(key, record[key]))
    lines.append('\n')
    for key in ('theta_rad', 'theta_deg', 't_x_m', 't_y_m'):
        lines.append('{}: {:.9f}\n'.format(key, record[key]))
    lines.append('\n')
    for key in ('residual_rms_m', 'residual_max_m', 'shear_deg'):
        lines.append('{}: {:.6f}\n'.format(key, record[key]))
    lines.append('n_wall_points: {}\n'.format(record['n_wall_points']))
    lines.append('trim_cells: {}\n'.format(record['trim_cells']))
    lines.append('\n# per wall: extremes taken, extremes kept by the trimming\n'
                 '# rule, its own rotation from the building, and max\n'
                 '# residual against the common transform\n')
    lines.append('walls:\n')
    for wall in record['walls']:
        lines.append('  - name: {}\n'.format(wall['name']))
        lines.append('    extremes: {}\n'.format(wall['extremes']))
        lines.append('    points: {}\n'.format(wall['points']))
        lines.append('    dropped: {}\n'.format(wall['dropped']))
        lines.append('    angle_deg: {:.4f}\n'.format(wall['angle_deg']))
        lines.append('    fit_rms_m: {:.4f}\n'.format(wall['fit_rms_m']))
        lines.append('    residual_max_m: {:.4f}\n'.format(
            wall['residual_max_m']))
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(''.join(lines))


def load_registration(path=DEFAULT_REGISTRATION, verify=True):
    """Read a registration and (by default) verify it against its grid.

    Returns a dict with theta_rad, t_x_m, t_y_m, residual_max_m and the
    provenance fields. RAISES if the grid beside it is not the grid the
    transform was derived from - which is the whole mechanism that stops a
    rebuilt map being scored through a stale transform."""
    if not os.path.exists(path):
        raise SystemExit(
            'no registration at {}. Derive one first:\n'
            '    python3 sim/maps/warehouse/register_map.py derive --write'
            .format(path))
    record = {}
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            if line.startswith('#') or line.startswith(' ') or ':' not in line:
                continue
            key, _, value = line.partition(':')
            record[key.strip()] = value.strip()
    for key in ('theta_rad', 't_x_m', 't_y_m', 'residual_max_m',
                'residual_rms_m'):
        if key not in record:
            raise SystemExit('{} has no {}:'.format(path, key))
        record[key] = float(record[key])
    if verify:
        image = os.path.join(os.path.dirname(os.path.abspath(path)),
                             record.get('map_image', ''))
        if not os.path.exists(image):
            raise SystemExit('{} names a grid {} that does not exist'.format(
                path, image))
        actual = md5(image)
        if actual != record.get('map_md5'):
            raise SystemExit(
                'REGISTRATION IS STALE. {} was derived from a grid with md5\n'
                '  {}\nand {} now has md5\n  {}\n'
                'A regenerated map has its own rotation from the building. '
                'Re-derive:\n'
                '    python3 sim/maps/warehouse/register_map.py derive '
                '--write'.format(path, record.get('map_md5'), image, actual))
    return record


def world_to_map(record, x, y, yaw=None):
    """Carry a world-frame pose into the map frame through a registration."""
    cos_t = math.cos(record['theta_rad'])
    sin_t = math.sin(record['theta_rad'])
    mx = cos_t * x - sin_t * y + record['t_x_m']
    my = sin_t * x + cos_t * y + record['t_y_m']
    if yaw is None:
        return mx, my
    turned = yaw + record['theta_rad']
    return mx, my, math.atan2(math.sin(turned), math.cos(turned))


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def cmd_derive(args):
    meta = read_map_yaml(args.map)
    image = os.path.join(os.path.dirname(os.path.abspath(args.map)),
                         meta['image'])
    width, height, maxval, pixels = read_pgm(image)
    mask = occupied_mask(width, height, maxval, pixels, meta)
    world_walls = read_world_walls(args.world)

    print('# T(world -> map), derived from the committed artifacts')
    print('')
    print('grid   {}  {} x {} cells at {:.3f} m, origin ({:+.3f}, {:+.3f})'
          .format(os.path.basename(image), width, height, meta['resolution'],
                  meta['origin'][0], meta['origin'][1]))
    print('       md5 {}'.format(md5(image)))
    print('       occupied cells {} of {}, at occupied_thresh {:.3f} read '
          'from the yaml'.format(sum(mask), width * height,
                                 meta['occupied_thresh']))
    print('world  {}'.format(os.path.relpath(args.world, _REPO_ROOT)))
    print('       md5 {}'.format(md5(args.world)))
    print('')

    # One point set per SIDE of the hall. The south wall is two models with
    # a dock door between them and one inner face, so they are merged: they
    # are one line in the building and must be one line here.
    sides = {}
    for name, normal, offset in world_walls:
        key = (round(normal[0], 6), round(normal[1], 6))
        entry = sides.setdefault(key, {'names': [], 'normal': normal,
                                       'offset': offset})
        entry['names'].append(name)
        if abs(entry['offset'] - offset) > 1e-9:
            raise SystemExit(
                'wall models {} share a normal but not an inner face '
                '({:.3f} vs {:.3f}); they are not one line and this tool '
                'must be told how to treat them'.format(
                    '+'.join(entry['names']), entry['offset'], offset))

    walls = []
    print('Trimming rule: a wall is a line. Seed with a repeated-median fit')
    print('(50 % breakdown), drop every extreme further than {} cells '
          '({:.3f} m)'.format(args.trim_cells, args.trim_cells *
                              meta['resolution']))
    print('from it, refit, repeat to convergence. Applied to all four walls')
    print('identically. See fit_line_robust for why the seed is not least')
    print('squares.')
    print('')
    print('| wall | models | extremes | kept | dropped | fit rms | '
          'own rotation |')
    print('|---|---|---|---|---|---|---|')
    rows = []
    for key in sorted(sides):
        entry = sides[key]
        normal = entry['normal']
        label = '+'.join(entry['names'])
        points = extract_wall(mask, width, height, meta, normal)
        if len(points) < args.min_points:
            raise SystemExit(
                'wall {} yielded only {} extreme cells, under the '
                '--min-points floor of {}. This grid does not contain '
                'enough of that wall to register against.'.format(
                    label, len(points), args.min_points))
        robust = fit_line_robust(points, normal, meta['resolution'],
                                 args.min_points, args.trim_cells)
        if robust is None:
            raise SystemExit('wall {}: no line could be fitted'.format(label))
        unit, offset, rms, kept, dropped = robust
        if len(kept) < args.min_points:
            raise SystemExit(
                'wall {}: the trimming rule left {} of {} extremes, under '
                'the --min-points floor of {}. A line through the few points '
                'that happen to agree is not a measurement of a wall, so '
                'this wall is REFUSED rather than fitted. Either the grid '
                'does not contain this wall or --trim-cells is too '
                'tight.'.format(label, len(kept), len(points),
                                args.min_points))
        own = math.atan2(unit[1], unit[0]) - math.atan2(normal[1], normal[0])
        own = math.atan2(math.sin(own), math.cos(own))
        rows.append((label, len(kept), rms, math.degrees(own), len(points),
                     dropped))
        print('| {} | {} | {} | {} | {} | {:.4f} m | {:+.4f} deg |'.format(
            _side_name(normal), label, len(points), len(kept), dropped, rms,
            math.degrees(own)))
        # The TRIMMED set is what the transform is solved over. Feeding the
        # untrimmed set here would put the racking back into the residual
        # after the fit had just removed it from the angle.
        walls.append((label, normal, entry['offset'], kept))

    angles = [row[3] for row in rows]
    shear = max(angles) - min(angles)
    theta, translation, sse, per_wall = derive_transform(walls)
    total = sum(len(w[3]) for w in walls)
    residuals = [abs(e) for _, errs in per_wall for e in errs]
    rms = math.sqrt(sse / total)
    worst = max(residuals)

    print('')
    print('The four rotations above are the SAME wall angle measured four')
    print('ways. Their spread is the grid\'s internal shear: {:.4f} deg.'
          .format(shear))
    print('A rigid transform cannot absorb it, so it appears in the residual.')
    print('')
    print('## T(world -> map)')
    print('')
    print('    p_map = R(theta) * p_world + t')
    print('')
    print('    theta = {:+.6f} rad = {:+.4f} deg'.format(theta,
                                                         math.degrees(theta)))
    print('    t     = ({:+.4f}, {:+.4f}) m'.format(*translation))
    print('')
    print('    residual rms {:.4f} m over {} wall points'.format(rms, total))
    print('    residual MAX {:.4f} m   <- THE FLOOR UNDER EVERY LOCALISATION'
          .format(worst))
    print('                              NUMBER MEASURED THROUGH THIS '
          'TRANSFORM')
    print('')
    print('| wall | max residual | rms residual |')
    print('|---|---|---|')
    wall_records = []
    for (label, errs), row in zip(per_wall, rows):
        wall_max = max(abs(e) for e in errs)
        wall_rms = math.sqrt(sum(e * e for e in errs) / len(errs))
        print('| {} | {:.4f} m | {:.4f} m |'.format(label, wall_max, wall_rms))
        wall_records.append({
            'name': label,
            'points': row[1],
            'extremes': row[4],
            'dropped': row[5],
            'angle_deg': row[3],
            'fit_rms_m': row[2],
            'residual_max_m': wall_max,
        })

    record = {
        'map_yaml': os.path.basename(args.map),
        'map_image': meta['image'],
        'map_md5': md5(image),
        'map_yaml_md5': md5(args.map),
        'world_sdf': os.path.relpath(args.world, _REPO_ROOT),
        'world_md5': md5(args.world),
        'derived_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'tool': 'sim/maps/warehouse/register_map.py',
        'theta_rad': theta,
        'theta_deg': math.degrees(theta),
        't_x_m': translation[0],
        't_y_m': translation[1],
        'residual_rms_m': rms,
        'residual_max_m': worst,
        'shear_deg': shear,
        'n_wall_points': total,
        'trim_cells': args.trim_cells,
        'walls': wall_records,
    }
    if args.write:
        write_registration(args.out, record)
        print('')
        print('written: {}'.format(os.path.relpath(args.out, _REPO_ROOT)))
    else:
        print('')
        print('(nothing written; pass --write to commit this registration)')
    return 0


def _side_name(normal):
    if normal[0] > 0.5:
        return 'east'
    if normal[0] < -0.5:
        return 'west'
    return 'north' if normal[1] > 0.5 else 'south'


def cmd_show(args):
    record = load_registration(args.out, verify=not args.no_verify)
    print('# {}'.format(os.path.relpath(args.out, _REPO_ROOT)))
    print('')
    print('  p_map = R(theta) * p_world + t')
    print('  theta = {:+.6f} rad = {:+.4f} deg'.format(
        record['theta_rad'], math.degrees(record['theta_rad'])))
    print('  t     = ({:+.4f}, {:+.4f}) m'.format(record['t_x_m'],
                                                  record['t_y_m']))
    print('  residual rms {:.4f} m, MAX {:.4f} m'.format(
        record['residual_rms_m'], record['residual_max_m']))
    print('  derived from {} md5 {} on {}'.format(
        record.get('map_image'), record.get('map_md5'),
        record.get('derived_utc')))
    if args.no_verify:
        print('')
        print('  NOT VERIFIED against the grid (--no-verify)')
    else:
        print('')
        print('  grid md5 verified: this transform belongs to this map')
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    der = sub.add_parser('derive', help='fit the walls and print the transform')
    der.add_argument('--map', default=DEFAULT_MAP_YAML,
                     help='map yaml (default: %(default)s)')
    der.add_argument('--world', default=DEFAULT_WORLD,
                     help='world SDF the walls are read from')
    der.add_argument('--out', default=DEFAULT_REGISTRATION,
                     help='registration file written by --write')
    der.add_argument('--write', action='store_true',
                     help='write the registration file. Without this the '
                          'tool prints and commits nothing')
    der.add_argument('--trim-cells', type=float, default=3.0,
                     help='THE TRIMMING RULE. Drop every extreme further '
                          'than this many cells from the fitted wall line, '
                          'refit, repeat to convergence (default: '
                          '%(default)s cells = 0.15 m at 0.05 m/cell). Must '
                          'sit above the wall\'s own scatter and below the '
                          'standoff of the nearest non-wall surface; on '
                          'this building anything from 2 to 6 moves the '
                          'fitted angle by under 0.01 deg')
    der.add_argument('--min-points', type=int, default=100,
                     help='REFUSE a wall whose extremes, or whose survivors '
                          'of the trimming rule, fall under this count '
                          '(default: %(default)s)')
    der.set_defaults(func=cmd_derive)

    show = sub.add_parser('show', help='print a committed registration')
    show.add_argument('--out', default=DEFAULT_REGISTRATION)
    show.add_argument('--no-verify', action='store_true',
                      help='do not check the grid md5. For inspecting a '
                           'superseded registration only')
    show.set_defaults(func=cmd_show)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
