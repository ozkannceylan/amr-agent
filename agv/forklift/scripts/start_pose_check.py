#!/usr/bin/env python3
"""start_pose_check.py - does the committed grid cover the pose the vehicle
is asked to plan from?

WHY THIS EXISTS. m5-68 issued an autonomous mission from the committed spawn
pose and `SmacPlannerHybrid` published 0 plans in 100 s. The diagnosis
offered was "the spawn sits at the corner of the committed grid". That is a
GEOMETRY claim, and a geometry claim is answered by measuring the geometry -
not by relaxing `allow_unknown`, which is the tuning move that makes the
symptom go away and the vehicle plan through space nothing has ever seen.

WHAT IT MEASURES, and it measures the planner's OWN rule rather than a
plausible-looking proxy:

  1. `nav2_costmap_2d::FootprintCollisionChecker` traces the footprint's
     OUTLINE with a Bresenham raytrace and takes the worst cell on it. It
     does NOT fill the polygon. A tool that fills the polygon reports cells
     the planner never reads, so this one traces the outline the same way.
  2. The footprint it traces is the PADDED one. `nav2.yaml` sets
     `footprint_padding: 0.27`, and `costmap_2d::padFootprint` pushes each
     vertex outward along the sign of its own coordinate. The unpadded
     polygon is not what the planner checks.
  3. With `allow_unknown: false` a NO_INFORMATION cell under that outline is
     as fatal as a lethal one. Both are counted and both are reported, and
     they are NOT summed: "the outline crosses unmapped space" and "the
     outline crosses a rack" are different defects with different fixes.
  4. Separately from the outline test, the INSCRIBED-CIRCLE clearance is
     reported - the distance from the pose to the nearest cell that is not
     free. A pose whose clearance is below the padded polygon's inscribed
     radius (0.769 m) cannot be valid at ANY yaw, so it is a defect of the
     pose and not of the heading it was given.

WHAT IT IS NOT. It is not a claim that a plan exists. Two poses can each be
valid and lie in components the vehicle cannot drive between; `--component`
answers that question by eroding the free space to the inscribed radius and
labelling what is left, and it is a NECESSARY condition, not a sufficient
one. The planner bench (`nav2_run.py plan`) is what settles a route, and
this tool exists to stop that bench being run from a pose that cannot work.

WHAT IT READS. `sim/maps/warehouse/warehouse.yaml` and its `.pgm`, through
`register_map.load_registration()`, which verifies the grid md5 - so a
rebuilt map fails here instead of producing a plausible wrong answer. The
footprint and the padding come from `agv/forklift/nav2.yaml`, parsed from
the file rather than restated, so this tool cannot disagree with the planner
about the shape it is checking.

Usage:
  python3 agv/forklift/scripts/start_pose_check.py coverage
  python3 agv/forklift/scripts/start_pose_check.py pose --x -6.0 --y -5.5
  python3 agv/forklift/scripts/start_pose_check.py scan \\
      --x0 -12 --x1 12 --y0 -5.5 --y1 -5.5 --step 0.5
  python3 agv/forklift/scripts/start_pose_check.py path \\
      --plan agv/forklift/evidence/m5-69-dockB-r1-plan.json
  python3 agv/forklift/scripts/start_pose_check.py component \\
      --from=-6.0,-5.5 --to=1.0,7.0
      # the `=` is required for a negative coordinate: argparse reads a bare
      # `-6.0,-5.5` as an option name, not as this option's value.

All poses are WORLD-frame metres and radians, the frame every launch file
and every scenario states its poses in.
"""

import argparse
import json
import math
import os
import sys
from collections import deque

import numpy as np

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, '..', '..', '..'))
_MAP_DIR = os.path.join(_REPO_ROOT, 'sim', 'maps', 'warehouse')
_NAV2_YAML = os.path.normpath(os.path.join(_THIS_DIR, '..', 'nav2.yaml'))


# --------------------------------------------------------------------------- #
# the committed inputs, each read from the file that owns it
# --------------------------------------------------------------------------- #

def load_registration(path=None):
    """Through register_map.py, which verifies the grid md5 (invariant 10)."""
    if _MAP_DIR not in sys.path:
        sys.path.insert(0, _MAP_DIR)
    try:
        import register_map
    except ImportError:
        raise SystemExit(
            'cannot import {}/register_map.py, which owns the world->map '
            'transform.'.format(_MAP_DIR))
    if path is None:
        path = register_map.DEFAULT_REGISTRATION
    return register_map.load_registration(path)


def load_map_yaml(path=None):
    """resolution, origin and the two thresholds, from the map yaml itself."""
    if path is None:
        path = os.path.join(_MAP_DIR, 'warehouse.yaml')
    record = {}
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.split('#')[0].strip()
            if ':' not in line:
                continue
            key, _, value = line.partition(':')
            record[key.strip()] = value.strip()
    origin = [float(v) for v in
              record['origin'].strip('[]').replace(',', ' ').split()]
    return {
        'image': os.path.join(os.path.dirname(os.path.abspath(path)),
                              record['image']),
        'resolution': float(record['resolution']),
        'origin': (origin[0], origin[1]),
        'occupied_thresh': float(record['occupied_thresh']),
        'free_thresh': float(record['free_thresh']),
        'mode': record.get('mode', 'trinary'),
    }


def load_footprint(path=None):
    """The polygon and the padding, PARSED FROM nav2.yaml.

    Both costmaps state the same polygon; this reads every `footprint:` and
    `footprint_padding:` it finds and REFUSES if they disagree, because a
    check run against one costmap's shape while the planner uses the other's
    is a check of nothing."""
    if path is None:
        path = _NAV2_YAML
    polys, pads = [], []
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            stripped = line.split('#')[0].strip()
            if stripped.startswith('footprint:'):
                text = stripped.partition(':')[2].strip().strip('"\'')
                pts = [float(v) for v in
                       text.replace('[', ' ').replace(']', ' ')
                           .replace(',', ' ').split()]
                polys.append(tuple(zip(pts[0::2], pts[1::2])))
            elif stripped.startswith('footprint_padding:'):
                pads.append(float(stripped.partition(':')[2].strip()))
    if not polys or not pads:
        raise SystemExit('{}: no footprint / footprint_padding found'
                         .format(path))
    if len(set(polys)) != 1:
        raise SystemExit('{}: the costmaps state DIFFERENT footprints; this '
                         'tool cannot say which one the planner checks'
                         .format(path))
    if len(set(pads)) != 1:
        raise SystemExit('{}: the costmaps state DIFFERENT footprint_padding '
                         'values ({})'.format(path, sorted(set(pads))))
    return polys[0], pads[0]


def pad_footprint(poly, pad):
    """costmap_2d::padFootprint - each vertex outward along its own sign."""
    return tuple((x + math.copysign(pad, x), y + math.copysign(pad, y))
                 for x, y in poly)


def inscribed_radius(poly):
    """The largest circle about the origin that fits inside the polygon."""
    best = float('inf')
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg == 0.0:
            continue
        best = min(best, abs((x1 - x0) * (0.0 - y0) - (0.0 - x0) * (y1 - y0))
                   / seg)
    return best


# --------------------------------------------------------------------------- #
# the grid
# --------------------------------------------------------------------------- #

def read_pgm(path):
    with open(path, 'rb') as handle:
        data = handle.read()
    idx, fields = 0, []
    while len(fields) < 4:
        while data[idx:idx + 1].isspace():
            idx += 1
        if data[idx:idx + 1] == b'#':
            while data[idx:idx + 1] != b'\n':
                idx += 1
            continue
        start = idx
        while not data[idx:idx + 1].isspace():
            idx += 1
        fields.append(data[start:idx])
    idx += 1
    if fields[0] != b'P5':
        raise SystemExit('{}: not a binary PGM'.format(path))
    width, height = int(fields[1]), int(fields[2])
    need = width * height
    return np.frombuffer(data[idx:idx + need],
                         dtype=np.uint8).reshape(height, width)


def classify(pixels, meta):
    """map_server's trinary rule: occ = (255 - value)/255.

    free (+1) below free_thresh, occupied (-1) above occupied_thresh,
    NO_INFORMATION (0) in between. 205, the value SLAM writes for unmapped,
    lands at occ = 0.19608 against free_thresh 0.196 - it is unknown by six
    parts in a hundred thousand, which is why this rule is applied rather
    than a "205 means unknown" shortcut that would silently stop being true
    if either threshold moved."""
    occ = (255.0 - pixels.astype(np.float64)) / 255.0
    out = np.zeros(pixels.shape, dtype=np.int8)
    out[occ < meta['free_thresh']] = 1
    out[occ > meta['occupied_thresh']] = -1
    return out


class Grid(object):
    def __init__(self, registration=None, map_yaml=None, nav2_yaml=None):
        self.rec = load_registration(registration)
        self.meta = load_map_yaml(map_yaml)
        self.pixels = read_pgm(self.meta['image'])
        self.cls = classify(self.pixels, self.meta)
        self.height, self.width = self.cls.shape
        self.res = self.meta['resolution']
        self.origin = self.meta['origin']
        self.raw_footprint, self.padding = load_footprint(nav2_yaml)
        self.footprint = pad_footprint(self.raw_footprint, self.padding)
        self.inscribed = inscribed_radius(self.footprint)
        self._dist = None
        self._label = None

    # -- frames ----------------------------------------------------------- #
    def world_to_map(self, x, y, yaw=0.0):
        th = self.rec['theta_rad']
        c, s = math.cos(th), math.sin(th)
        return (c * x - s * y + self.rec['t_x_m'],
                s * x + c * y + self.rec['t_y_m'], yaw + th)

    def map_to_world(self, mx, my, myaw=0.0):
        th = self.rec['theta_rad']
        c, s = math.cos(-th), math.sin(-th)
        dx, dy = mx - self.rec['t_x_m'], my - self.rec['t_y_m']
        return (c * dx - s * dy, s * dx + c * dy, myaw - th)

    def map_to_cell(self, mx, my):
        col = int(math.floor((mx - self.origin[0]) / self.res))
        row = self.height - 1 - int(math.floor((my - self.origin[1])
                                               / self.res))
        return col, row

    def cell_to_map(self, col, row):
        return (self.origin[0] + (col + 0.5) * self.res,
                self.origin[1] + (self.height - 1 - row + 0.5) * self.res)

    # -- the planner's own footprint test ---------------------------------- #
    def outline_cells(self, x, y, yaw):
        mx, my, myaw = self.world_to_map(x, y, yaw)
        c, s = math.cos(myaw), math.sin(myaw)
        corners = []
        for px, py in self.footprint:
            corners.append(self.map_to_cell(mx + c * px - s * py,
                                            my + s * px + c * py))
        cells = []
        for i in range(len(corners)):
            cells += _raytrace(corners[i], corners[(i + 1) % len(corners)])
        return cells

    def footprint_verdict(self, x, y, yaw=0.0):
        counts = {'free': 0, 'unknown': 0, 'lethal': 0, 'off_grid': 0}
        for col, row in self.outline_cells(x, y, yaw):
            if not (0 <= row < self.height and 0 <= col < self.width):
                counts['off_grid'] += 1
                continue
            value = int(self.cls[row, col])
            counts['free' if value == 1 else
                   ('unknown' if value == 0 else 'lethal')] += 1
        counts['valid'] = (counts['unknown'] == 0 and counts['lethal'] == 0
                           and counts['off_grid'] == 0)
        return counts

    # -- clearance and connectivity ---------------------------------------- #
    @property
    def dist(self):
        """Metres from every cell to the nearest cell that is not free."""
        if self._dist is None:
            self._dist = _edt(self.cls == 1) * self.res
        return self._dist

    def clearance(self, x, y):
        col, row = self.map_to_cell(*self.world_to_map(x, y)[:2])
        if not (0 <= row < self.height and 0 <= col < self.width):
            return 0.0
        return float(self.dist[row, col])

    @property
    def components(self):
        """Connected components of the free space eroded to the inscribed
        radius. Two poses in different components are not drivable between,
        whatever either one's own verdict says."""
        if self._label is None:
            self._label = _label(self.dist >= self.inscribed)
        return self._label

    def component_of(self, x, y):
        col, row = self.map_to_cell(*self.world_to_map(x, y)[:2])
        labels, _ = self.components
        if not (0 <= row < self.height and 0 <= col < self.width):
            return 0
        return int(labels[row, col])

    def classify_cell(self, x, y):
        col, row = self.map_to_cell(*self.world_to_map(x, y)[:2])
        if not (0 <= row < self.height and 0 <= col < self.width):
            return 'off_grid'
        return {1: 'free', 0: 'unknown', -1: 'lethal'}[int(self.cls[row, col])]


def _raytrace(a, b):
    """Bresenham, the walk costmap_2d::lineCost takes along each edge."""
    (c0, r0), (c1, r1) = a, b
    cells = []
    dc, dr = abs(c1 - c0), abs(r1 - r0)
    sc = 1 if c1 > c0 else -1
    sr = 1 if r1 > r0 else -1
    err = dc - dr
    col, row = c0, r0
    while True:
        cells.append((col, row))
        if col == c1 and row == r1:
            return cells
        step = 2 * err
        if step > -dr:
            err -= dr
            col += sc
        if step < dc:
            err += dc
            row += sr


def _edt(mask):
    """Exact Euclidean distance transform (Felzenszwalb & Huttenlocher), in
    cells, from every True cell to the nearest False cell.

    Written here rather than imported: `scipy.ndimage` on this machine is
    built against numpy 1.x and the interpreter carries 2.4.2, so importing
    it raises. Adding a dependency to answer a geometry question is not a
    trade this brief may make."""
    big = float(mask.shape[0] + mask.shape[1]) ** 2
    field = np.where(mask, big, 0.0)

    def dt1d(f):
        n = f.shape[0]
        d = np.empty(n)
        v = np.zeros(n, dtype=int)
        z = np.empty(n + 1)
        k = 0
        z[0], z[1] = -np.inf, np.inf
        for q in range(1, n):
            s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k])
            while s <= z[k]:
                k -= 1
                s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) \
                    / (2 * q - 2 * v[k])
            k += 1
            v[k], z[k], z[k + 1] = q, s, np.inf
        k = 0
        for q in range(n):
            while z[k + 1] < q:
                k += 1
            d[q] = (q - v[k]) ** 2 + f[v[k]]
        return d

    out = np.empty_like(field)
    for col in range(field.shape[1]):
        out[:, col] = dt1d(field[:, col])
    for row in range(field.shape[0]):
        out[row, :] = dt1d(out[row, :])
    return np.sqrt(out)


def _label(mask):
    """8-connected components. Returns (labels, sizes-by-label)."""
    labels = np.zeros(mask.shape, dtype=np.int32)
    sizes = [0]
    current = 0
    rows, cols = mask.shape
    for r0 in range(rows):
        for c0 in range(cols):
            if not mask[r0, c0] or labels[r0, c0]:
                continue
            current += 1
            size = 0
            queue = deque([(r0, c0)])
            labels[r0, c0] = current
            while queue:
                r, c = queue.popleft()
                size += 1
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        rr, cc = r + dr, c + dc
                        if (0 <= rr < rows and 0 <= cc < cols
                                and mask[rr, cc] and not labels[rr, cc]):
                            labels[rr, cc] = current
                            queue.append((rr, cc))
            sizes.append(size)
    return labels, sizes


# --------------------------------------------------------------------------- #
# subcommands
# --------------------------------------------------------------------------- #

def _report_pose(grid, label, x, y, yaw):
    mx, my, myaw = grid.world_to_map(x, y, yaw)
    col, row = grid.map_to_cell(mx, my)
    counts = grid.footprint_verdict(x, y, yaw)
    clear = grid.clearance(x, y)
    comp = grid.component_of(x, y)
    print('{}'.format(label))
    print('  world      ({:+.3f}, {:+.3f}) yaw {:+.4f} rad'.format(x, y, yaw))
    print('  map        ({:+.3f}, {:+.3f}) yaw {:+.4f} rad   cell '
          '({}, {})'.format(mx, my, myaw, col, row))
    print('  cell class {}'.format(grid.classify_cell(x, y)))
    print('  padded-footprint OUTLINE, {} cells: free {}  UNKNOWN {}  '
          'LETHAL {}  off-grid {}'.format(
              sum(counts[k] for k in
                  ('free', 'unknown', 'lethal', 'off_grid')),
              counts['free'], counts['unknown'], counts['lethal'],
              counts['off_grid']))
    print('  inscribed clearance {:.3f} m against inscribed radius {:.3f} m '
          '-> {}'.format(clear, grid.inscribed,
                         'fits' if clear >= grid.inscribed else
                         'DOES NOT FIT AT ANY YAW'))
    print('  passable component {}'.format(comp if comp else
                                           '0 (none - below inscribed '
                                           'radius)'))
    print('  VERDICT: {}'.format(
        'VALID start for allow_unknown false' if counts['valid'] else
        'INVALID for allow_unknown false'))
    return counts


def cmd_coverage(args):
    grid = Grid(args.registration, args.map_yaml, args.nav2_yaml)
    total = grid.width * grid.height
    free = int((grid.cls == 1).sum())
    unknown = int((grid.cls == 0).sum())
    lethal = int((grid.cls == -1).sum())
    print('grid       {} x {} cells at {:.3f} m = {:.2f} x {:.2f} m'.format(
        grid.width, grid.height, grid.res,
        grid.width * grid.res, grid.height * grid.res))
    print('map md5    {}'.format(grid.rec.get('map_md5')))
    print('cells      free {} ({:.1f} %)  unknown {} ({:.1f} %)  '
          'lethal {} ({:.1f} %)'.format(
              free, 100.0 * free / total, unknown, 100.0 * unknown / total,
              lethal, 100.0 * lethal / total))
    print('footprint  padded {} vertices, padding {:.3f} m, inscribed radius '
          '{:.3f} m'.format(len(grid.footprint), grid.padding, grid.inscribed))

    for name, mask in (('KNOWN (free or lethal)', grid.cls != 0),
                       ('FREE', grid.cls == 1)):
        rows = np.where(mask.any(axis=1))[0]
        cols = np.where(mask.any(axis=0))[0]
        x0 = grid.origin[0] + cols[0] * grid.res
        x1 = grid.origin[0] + (cols[-1] + 1) * grid.res
        y1 = grid.origin[1] + (grid.height - rows[0]) * grid.res
        y0 = grid.origin[1] + (grid.height - 1 - rows[-1]) * grid.res
        corners = [grid.map_to_world(a, b)[:2] for a, b in
                   ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        print('{:22s} map x [{:+.3f}, {:+.3f}]  y [{:+.3f}, {:+.3f}]'
              .format(name + ' bbox', x0, x1, y0, y1))
        print('{:22s} world corners {}'.format(
            '', ' '.join('({:+.2f},{:+.2f})'.format(*c) for c in corners)))

    labels, sizes = grid.components
    order = sorted(range(1, len(sizes)), key=lambda i: -sizes[i])
    area = [s * grid.res * grid.res for s in sizes]
    print('passable components at clearance >= {:.3f} m: {} total'.format(
        grid.inscribed, len(sizes) - 1))
    for i in order[:6]:
        if area[i] < 0.5:
            break
        print('   #{:<3d} {:8.1f} m^2'.format(i, area[i]))

    if args.sketch:
        _sketch(grid, labels, order[0] if order else 0, args.step)


def _sketch(grid, labels, biggest, step):
    print('\nworld-frame sketch, 1 char = {:.1f} m. "#" lethal, "." free, '
          '" " unmapped,\n"O" free with >= {:.3f} m clearance in the largest '
          'passable component.'.format(step, grid.inscribed))
    ys = np.arange(10.0, -10.0 - step / 2, -step)
    xs = np.arange(-15.0, 15.0 + step / 2, step)
    for y in ys:
        line = ''
        for x in xs:
            col, row = grid.map_to_cell(*grid.world_to_map(x, y)[:2])
            if not (0 <= row < grid.height and 0 <= col < grid.width):
                line += '?'
                continue
            value = int(grid.cls[row, col])
            if value == -1:
                line += '#'
            elif value == 0:
                line += ' '
            elif labels[row, col] == biggest:
                line += 'O'
            else:
                line += '.'
        print('{:+6.1f} |{}|'.format(y, line))


def cmd_pose(args):
    grid = Grid(args.registration, args.map_yaml, args.nav2_yaml)
    counts = _report_pose(grid, 'pose under test', args.x, args.y, args.yaw)
    if args.yaw_sweep:
        print('\n  yaw sweep, {} headings over the full circle:'
              .format(args.yaw_sweep))
        bad = 0
        for i in range(args.yaw_sweep):
            yaw = 2.0 * math.pi * i / args.yaw_sweep
            c = grid.footprint_verdict(args.x, args.y, yaw)
            if not c['valid']:
                bad += 1
        print('    {} of {} headings INVALID'.format(bad, args.yaw_sweep))
    return 0 if counts['valid'] else 1


def cmd_scan(args):
    grid = Grid(args.registration, args.map_yaml, args.nav2_yaml)
    print('{:>8s} {:>8s} {:>8s} {:>8s} {:>8s} {:>6s} {:>5s}  verdict'.format(
        'world x', 'world y', 'free', 'unknown', 'lethal', 'clear', 'comp'))
    n_valid = 0
    xs = _span(args.x0, args.x1, args.step)
    ys = _span(args.y0, args.y1, args.step)
    for y in ys:
        for x in xs:
            c = grid.footprint_verdict(x, y, args.yaw)
            clear = grid.clearance(x, y)
            comp = grid.component_of(x, y)
            n_valid += bool(c['valid'])
            print('{:8.2f} {:8.2f} {:8d} {:8d} {:8d} {:6.3f} {:5d}  {}'
                  .format(x, y, c['free'], c['unknown'], c['lethal'],
                          clear, comp, 'VALID' if c['valid'] else 'invalid'))
    print('\n{} of {} poses VALID at yaw {:+.4f}'.format(
        n_valid, len(xs) * len(ys), args.yaw))


def _span(a, b, step):
    if abs(b - a) < 1e-9:
        return [a]
    n = int(round(abs(b - a) / step))
    return [a + (b - a) * i / n for i in range(n + 1)]


def cmd_path(args):
    """Score a plan `nav2_run.py plan --plan <json>` wrote.

    WHY THIS IS A SEPARATE QUESTION FROM "does it plan". nav2's collision
    check traces the footprint OUTLINE and takes the worst cell on it; it
    never looks inside the polygon. This vehicle's padded footprint is
    3.275 m long, so an obstacle can sit ENTIRELY INSIDE it and the check
    still passes - the planner will happily emit a corridor narrower than
    the vehicle's inscribed circle, and the drive then fails downstream as
    a controller that cannot make progress or as a replan whose new start
    is occupied. m5-69 13.4 is that failure, 5 times in 5.

    So this reports the MINIMUM INSCRIBED CLEARANCE along the path, which
    the outline test cannot see, beside the outline verdict at every pose.
    """
    grid = Grid(args.registration, args.map_yaml, args.nav2_yaml)
    with open(args.plan, 'r', encoding='utf-8') as handle:
        payload = json.load(handle)
    poses = payload.get(args.key) or payload.get('first_plan_map')
    if not poses:
        raise SystemExit('{}: no `{}` array in this plan record'
                         .format(args.plan, args.key))
    worst = None
    n_invalid = 0
    rows = []
    for mx, my, myaw in poses:
        wx, wy, wyaw = grid.map_to_world(mx, my, myaw)
        counts = grid.footprint_verdict(wx, wy, wyaw)
        clear = grid.clearance(wx, wy)
        rows.append((wx, wy, clear, counts))
        n_invalid += 0 if counts['valid'] else 1
        if worst is None or clear < worst[2]:
            worst = (wx, wy, clear, counts)
    print('plan {}  ({} poses, key `{}`)'.format(args.plan, len(poses),
                                                 args.key))
    print('  outline INVALID at {} of {} poses'.format(n_invalid, len(poses)))
    print('  inscribed radius              {:.3f} m'.format(grid.inscribed))
    print('  MINIMUM inscribed clearance   {:.3f} m at world ({:+.3f}, '
          '{:+.3f})'.format(worst[2], worst[0], worst[1]))
    below = sum(1 for r in rows if r[2] < grid.inscribed)
    print('  poses whose inscribed circle does NOT fit: {} of {}'
          .format(below, len(poses)))
    if args.verbose:
        for wx, wy, clear, counts in rows:
            print('    ({:+8.3f}, {:+8.3f})  clear {:6.3f}  unknown {:3d}  '
                  'lethal {:3d}  {}'.format(
                      wx, wy, clear, counts['unknown'], counts['lethal'],
                      'ok' if counts['valid'] else 'INVALID'))
    if below:
        print('\nTHIS PLAN THREADS A CORRIDOR THE VEHICLE DOES NOT FIT IN. '
              'The planner will emit it, because it checks the outline only.')
        return 1
    return 0


def cmd_component(args):
    grid = Grid(args.registration, args.map_yaml, args.nav2_yaml)
    poses = []
    for label, text in (('from', args.frm), ('to', args.to)):
        x, y = [float(v) for v in text.split(',')]
        poses.append((label, x, y))
    comps = []
    for label, x, y in poses:
        print()
        _report_pose(grid, '{} ({}, {})'.format(label, x, y), x, y, args.yaw)
        comps.append(grid.component_of(x, y))
    print()
    if 0 in comps:
        print('NOT COMPARABLE: at least one pose is below the inscribed '
              'radius, so it belongs to no passable component.')
        return 1
    if comps[0] == comps[1]:
        print('SAME passable component ({}). Connectivity does not exclude a '
              'drivable route. Whether one EXISTS for a steered vehicle that '
              'cannot rotate in place is the planner bench\'s question, not '
              'this one\'s: this test ignores heading entirely.'
              .format(comps[0]))
        return 0
    print('DIFFERENT passable components ({} and {}). No footprint-clearing '
          'route exists between them in this grid, whatever the planner is '
          'asked.'.format(*comps))
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--registration', default=None)
    parser.add_argument('--map-yaml', default=None)
    parser.add_argument('--nav2-yaml', default=None)
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('coverage', help='what the committed grid covers')
    p.add_argument('--sketch', action='store_true')
    p.add_argument('--step', type=float, default=1.0)
    p.set_defaults(func=cmd_coverage)

    p = sub.add_parser('pose', help='is one world pose a valid start')
    p.add_argument('--x', type=float, required=True)
    p.add_argument('--y', type=float, required=True)
    p.add_argument('--yaw', type=float, default=0.0)
    p.add_argument('--yaw-sweep', type=int, default=0,
                   help='also test N headings over the full circle')
    p.set_defaults(func=cmd_pose)

    p = sub.add_parser('scan', help='sweep a line or box of world poses')
    p.add_argument('--x0', type=float, required=True)
    p.add_argument('--x1', type=float, required=True)
    p.add_argument('--y0', type=float, required=True)
    p.add_argument('--y1', type=float, required=True)
    p.add_argument('--step', type=float, default=0.5)
    p.add_argument('--yaw', type=float, default=0.0)
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser(
        'path', help='score a plan record for corridor width, which the '
                     "planner's outline-only check cannot see")
    p.add_argument('--plan', required=True,
                   help='a JSON record written by nav2_run.py plan/goal')
    p.add_argument('--key', default='first_plan_map',
                   help='which pose array to score')
    p.add_argument('--verbose', action='store_true')
    p.set_defaults(func=cmd_path)

    p = sub.add_parser('component', help='are two poses connected at all')
    p.add_argument('--from', dest='frm', required=True, metavar='X,Y')
    p.add_argument('--to', required=True, metavar='X,Y')
    p.add_argument('--yaw', type=float, default=0.0)
    p.set_defaults(func=cmd_component)

    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == '__main__':
    sys.exit(main())
