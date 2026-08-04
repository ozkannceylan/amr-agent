#!/usr/bin/env python3
"""footprint_from_model.py - derive the Nav2 footprint polygon from
model.sdf, rather than eyeballing it.

WHY THIS EXISTS. `nav2.yaml` gives both costmaps a POLYGON footprint, not a
`robot_radius`. For this vehicle that is not a nicety: the forks reach
1.875 m behind base_link while the body is 0.90 m wide, so the smallest
circle containing the vehicle has a radius of 1.906 m - wider than half a
3.80 m rack aisle. A radius model would make every aisle in the building
impassable, and the vehicle would refuse work it can do.

WHAT IT COMPUTES. The convex hull, in the base_link XY plane, of every
`<collision>` and `<visual>` primitive in `agv/forklift/model.sdf` that can
reach the space a costmap reasons about. Each primitive is placed by its
link pose composed with its own pose, projected onto the floor, and reduced
to its corner points; the hull of all of them is the polygon.

THE THREE DECISIONS IT MAKES, STATED RATHER THAN BURIED:

  1. COLLISION *AND* VISUAL. A costmap footprint answers "where is the
     machine", not "what does the physics engine collide". The overhead
     guard and the mast rails are visual-only in this model and they are
     still parts of the vehicle that hit a rack.
  2. THE STEER AXIS IS TAKEN AT FULL LOCK, BOTH WAYS. The drive wheel and
     its yoke rotate with `steer_joint`, so their projection depends on a
     joint angle. Taking them at +-`steer_limit_rad` and hulling all three
     postures makes the footprint valid at every steer angle instead of at
     the one the vehicle happened to be in.
  3. THE CARRIAGE AND FORKS ARE TAKEN AT THE LOWERED POSITION, which is
     where `mast_joint` sits at spawn and the only position that changes
     the FLOOR projection at all - the mast is prismatic in z, so lifting
     moves nothing in XY.

WHAT IT IS NOT. It is not a safety envelope. It is the polygon a costmap
uses to decide whether a cell is lethal for this vehicle, a process
function; the protective field and the protective stop are onboard and
hardwired and appear in no costmap (invariant 1).

Usage:
  python3 agv/forklift/scripts/footprint_from_model.py
  python3 agv/forklift/scripts/footprint_from_model.py --check "<polygon>"
"""

import argparse
import math
import os
import sys
import xml.etree.ElementTree as ET

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_DEFAULT_MODEL = os.path.join(_FORKLIFT_DIR, 'model.sdf')
_DEFAULT_CONFIG = os.path.join(_FORKLIFT_DIR, 'config.yaml')

#: Links whose XY projection turns with `steer_joint`.
_STEERED_LINKS = ('steer_link', 'drive_wheel')


def _pose(elem):
    """(x, y, z, roll, pitch, yaw) of an SDF <pose>, zero if absent.

    ROLL AND PITCH ARE READ, NOT DISCARDED, and that is the whole reason
    this function returns six numbers instead of three: every wheel in this
    model is a cylinder rolled 90 deg, so a projection that ignored roll
    would put the wheel's DIAMETER across the vehicle instead of its
    0.10 m width and invent 40 mm of width the vehicle does not have.
    """
    node = elem.find('pose') if elem is not None else None
    if node is None or not (node.text or '').strip():
        return (0.0,) * 6
    v = [float(t) for t in node.text.split()]
    while len(v) < 6:
        v.append(0.0)
    return tuple(v[:6])


def _rot(roll, pitch, yaw):
    """R = Rz(yaw) Ry(pitch) Rx(roll), SDF's own convention."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp,     cp * sr,                cp * cr),
    )


def _apply(rot, t, p):
    return tuple(t[i] + sum(rot[i][j] * p[j] for j in range(3))
                 for i in range(3))


def _compose(outer, inner):
    """outer o inner, both six-element poses."""
    ro = _rot(*outer[3:])
    x, y, z = _apply(ro, outer[:3], inner[:3])
    ri = _rot(*inner[3:])
    m = tuple(tuple(sum(ro[i][k] * ri[k][j] for k in range(3))
                    for j in range(3)) for i in range(3))
    # back out RPY from the composed matrix
    pitch = math.asin(max(-1.0, min(1.0, -m[2][0])))
    roll = math.atan2(m[2][1], m[2][2])
    yaw = math.atan2(m[1][0], m[0][0])
    return (x, y, z, roll, pitch, yaw)


#: Points around a cylinder's rim. 64 is 5.6 deg of arc; at the 0.12 m
#: wheel radius the chord error is 0.14 mm, three orders under the grid.
_RIM = 64


def _corners(geom, frame):
    """Floor-projected extreme points of one primitive, in base_link."""
    rot = _rot(*frame[3:])
    t = frame[:3]
    box = geom.find('box')
    cyl = geom.find('cylinder')
    local = []
    if box is not None:
        sx, sy, sz = [float(v) for v in box.find('size').text.split()]
        for dx in (-sx / 2.0, sx / 2.0):
            for dy in (-sy / 2.0, sy / 2.0):
                for dz in (-sz / 2.0, sz / 2.0):
                    local.append((dx, dy, dz))
    elif cyl is not None:
        r = float(cyl.find('radius').text)
        h = float(cyl.find('length').text)
        for i in range(_RIM):
            a = 2.0 * math.pi * i / _RIM
            for dz in (-h / 2.0, h / 2.0):
                local.append((r * math.cos(a), r * math.sin(a), dz))
    return [_apply(rot, t, p)[:2] for p in local]


def _hull(points):
    """Monotone chain convex hull, counter-clockwise."""
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return ((a[0] - o[0]) * (b[1] - o[1]) -
                (a[1] - o[1]) * (b[0] - o[0]))

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def collect(model_path, steer_limit_rad):
    """Every projected corner point of the vehicle, with its source."""
    root = ET.parse(model_path).getroot()
    model = root.find('model')
    points = []
    sources = []
    for link in model.findall('link'):
        link_name = link.get('name')
        link_pose = _pose(link)
        postures = [0.0]
        if link_name in _STEERED_LINKS:
            postures = [0.0, +steer_limit_rad, -steer_limit_rad]
        for prim in list(link.findall('collision')) + list(
                link.findall('visual')):
            geom = prim.find('geometry')
            if geom is None:
                continue
            prim_pose = _pose(prim)
            for delta in postures:
                # A steered link turns about its own origin.
                turned = link_pose[:5] + (link_pose[5] + delta,)
                frame = _compose(turned, prim_pose)
                pts = _corners(geom, frame)
                for p in pts:
                    points.append(p)
                    sources.append((p, link_name, prim.get('name'), delta))
    return points, sources


def polygon_string(hull):
    return '[' + ','.join('[{:.3f},{:.3f}]'.format(x, y)
                          for x, y in hull) + ']'


def pad_nav2(hull, padding):
    """nav2_costmap_2d::padFootprint - each coordinate is pushed OUTWARD by
    the padding along its own sign, which is not the same as offsetting the
    polygon by a distance."""
    out = []
    for x, y in hull:
        out.append((x + math.copysign(padding, x) if x else x + padding,
                    y + math.copysign(padding, y) if y else y + padding))
    return out


#: The committed grid, and its own registration to the world. Read for the
#: `--aisle` scan only; nothing here writes to sim/.
_MAP_DIR = os.path.normpath(os.path.join(_FORKLIFT_DIR, '..', '..',
                                         'sim', 'maps', 'warehouse'))


def _load_grid():
    """The committed .pgm and the transform that places it in the world.

    Reached through sim/maps/warehouse/register_map.py, the module that
    DERIVED the transform and verifies the grid's md5 (invariant 10)."""
    import yaml
    if _MAP_DIR not in sys.path:
        sys.path.insert(0, _MAP_DIR)
    import register_map
    rec = register_map.load_registration(register_map.DEFAULT_REGISTRATION)
    with open(os.path.join(_MAP_DIR, 'warehouse.yaml'), encoding='utf-8') as f:
        meta = yaml.safe_load(f)
    path = os.path.join(_MAP_DIR, meta['image'])
    with open(path, 'rb') as f:
        raw = f.read()
    parts = raw.split(b'\n', 3)
    w, h = [int(t) for t in parts[1].split()]
    return rec, meta, w, h, parts[3]


def aisle_scan(args):
    """How much lateral room the PADDED polygon has, along a named line.

    THE QUESTION THIS ANSWERS. The aisle is nominally 3.80 m and the padded
    vehicle is 1.638 m wide, which sounds comfortable. It is not everywhere:
    the building's columns stand proud of the rack faces, and where one does
    the free width falls to 2.40 m. The number that matters to a plan is the
    HALF-WIDTH LEFT OVER after the padded polygon, because that is the whole
    budget the planner's own detours and the controller's tracking error
    have to share.
    """
    rec, meta, w, h, pix = _load_grid()
    res = meta['resolution']
    ox, oy = meta['origin'][0], meta['origin'][1]
    th = rec['theta_rad']
    c, s = math.cos(th), math.sin(th)

    def free(x, y):
        mx = c * x - s * y + rec['t_x_m']
        my = s * x + c * y + rec['t_y_m']
        col = int((mx - ox) / res)
        row = h - 1 - int((my - oy) / res)
        if col < 0 or col >= w or row < 0 or row >= h:
            return False
        return pix[row * w + col] >= 250

    half = args.half_width
    print('aisle scan along y = {:+.2f} m (world), x from {:+.1f} to {:+.1f}'
          .format(args.line_y, args.x_from, args.x_to))
    print('grid {} md5-checked by register_map.py, resolution {:.3f} m'
          .format(meta['image'], res))
    print('padded half width {:.3f} m (footprint_padding {:.2f} m)'
          .format(half, args.padding))
    print('')
    print('  x        free y interval        width   HALF-WIDTH LEFT OVER')
    worst = None
    x = args.x_from
    step = args.x_step
    while x <= args.x_to + 1e-9:
        lo = hi = args.line_y
        while lo > args.line_y - 4.0 and free(x, lo - res):
            lo -= res
        while hi < args.line_y + 4.0 and free(x, hi + res):
            hi += res
        width = hi - lo
        # the vehicle's centreline may sit anywhere in [lo+half, hi-half]
        room = (width - 2 * half) / 2.0
        flag = ''
        if worst is None or room < worst[1]:
            worst = (x, room, lo, hi)
        if room < args.flag_below:
            flag = '   <-- pinch'
        print('  {:+6.2f}   {:+6.2f} .. {:+6.2f}   {:5.2f}   {:+6.3f} m{}'
              .format(x, lo, hi, width, room, flag))
        x += step
    print('')
    print('WORST on this line: x = {:+.2f}, free {:+.2f} .. {:+.2f} '
          '({:.2f} m), leaving {:+.3f} m each side of the padded polygon.'
          .format(worst[0], worst[2], worst[3], worst[3] - worst[2], worst[1]))
    print('That leftover is the ENTIRE budget for the plan\'s own detours '
          'and the controller\'s tracking error, and the measured 0.263 m '
          'localization worst case is already inside the padding.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--aisle', action='store_true',
                        help='instead of deriving the polygon, scan the '
                             'committed grid along a line and report how '
                             'much lateral room the PADDED polygon leaves')
    parser.add_argument('--line-y', type=float, default=7.0,
                        help='world y of the line to scan (default: aisle A)')
    parser.add_argument('--x-from', type=float, default=-13.0)
    parser.add_argument('--x-to', type=float, default=13.0)
    parser.add_argument('--x-step', type=float, default=0.5)
    parser.add_argument('--half-width', type=float, default=0.819,
                        help='padded half width [m]; the derivation above '
                             'prints it')
    parser.add_argument('--flag-below', type=float, default=0.45)
    parser.add_argument('--model', default=_DEFAULT_MODEL)
    parser.add_argument('--config', default=_DEFAULT_CONFIG)
    parser.add_argument('--padding', type=float, default=0.27,
                        help='footprint_padding as nav2.yaml sets it')
    parser.add_argument('--turning-radius', type=float, default=1.05,
                        help='minimum_turning_radius as nav2.yaml sets it')
    parser.add_argument('--check', default=None,
                        help='a polygon string to compare the derivation '
                             'against; exits nonzero if they differ')
    args = parser.parse_args(argv)

    if args.aisle:
        return aisle_scan(args)

    import yaml
    with open(args.config, encoding='utf-8') as fh:
        cfg = yaml.safe_load(fh)
    steer_limit = cfg['model']['steer_limit_rad']
    rear_axle_x = cfg['model']['rear_axle_offset_m']

    points, sources = collect(args.model, steer_limit)
    hull = _hull(points)

    print('footprint derived from {}'.format(os.path.relpath(args.model)))
    print('  primitives projected   {} corner points from '
          '{} collision/visual elements'.format(
              len(points), len(set(s[2] for s in sources))))
    print('  steer postures         0, +-{:.4f} rad (the mechanical stop)'
          .format(steer_limit))
    print('')
    print('THE HULL, {} vertices, counter-clockwise, base_link frame'
          .format(len(hull)))
    for x, y in hull:
        # which primitive put this vertex on the hull
        owner = min(sources,
                    key=lambda s: (s[0][0] - x) ** 2 + (s[0][1] - y) ** 2)
        print('  [{:+7.3f}, {:+7.3f}]   {} / {}'.format(
            x, y, owner[1], owner[2]))
    print('')
    print('footprint: "{}"'.format(polygon_string(hull)))
    print('')

    length = max(p[0] for p in hull) - min(p[0] for p in hull)
    width = max(p[1] for p in hull) - min(p[1] for p in hull)
    circum = max(math.hypot(x, y) for x, y in hull)
    print('DERIVED DIMENSIONS')
    print('  length (x)             {:.3f} m'.format(length))
    print('  width  (y)             {:.3f} m'.format(width))
    print('  circumscribed radius   {:.3f} m about base_link'.format(circum))
    print('    -> a `robot_radius` model would need {:.3f} m of clear space '
          'each side,'.format(circum))
    print('       against the 1.90 m half width of a 3.80 m aisle. THAT is '
          'why this is a polygon.')

    padded = pad_nav2(hull, args.padding)
    plength = max(p[0] for p in padded) - min(p[0] for p in padded)
    pwidth = max(p[1] for p in padded) - min(p[1] for p in padded)
    print('')
    print('PADDED BY {:.2f} m, the way nav2 pads (per coordinate, outward)'
          .format(args.padding))
    print('  padded length          {:.3f} m'.format(plength))
    print('  padded width           {:.3f} m'.format(pwidth))

    # The swept circle on the tightest planned arc, about the rear axle.
    cx, cy = rear_axle_x, args.turning_radius
    sweep = max(math.hypot(x - cx, y - cy) for x, y in hull)
    psweep = max(math.hypot(x - cx, y - cy) for x, y in padded)
    print('')
    print('THE SWEPT CIRCLE on the tightest PLANNED arc '
          '(R = {:.2f} m about the rear axle at x = {:+.2f})'.format(
              args.turning_radius, rear_axle_x))
    print('  outermost point        {:.3f} m unpadded, {:.3f} m padded'
          .format(sweep, psweep))
    print('  swept circle           {:.3f} m across padded'.format(2 * psweep))
    print('    -> the vehicle CANNOT turn round inside a 3.80 m aisle, which '
          'is correct')
    print('       for a forklift and is what makes the refusal case a real '
          'measurement.')

    if args.check is not None:
        want = args.check.strip()
        got = polygon_string(hull)
        same = (_norm(want) == _norm(got))
        print('')
        print('CHECK against nav2.yaml: {}'.format(
            'IDENTICAL' if same else 'DIFFERENT'))
        if not same:
            print('  nav2.yaml : {}'.format(want))
            print('  derived   : {}'.format(got))
            return 1
    return 0


def _norm(poly):
    """Compare polygons as an unordered set of rounded vertices."""
    body = poly.strip().strip('[]')
    nums = [float(t) for t in body.replace('[', ' ').replace(']', ' ')
            .replace(',', ' ').split()]
    pts = [(round(nums[i], 3), round(nums[i + 1], 3))
           for i in range(0, len(nums), 2)]
    return sorted(pts)


if __name__ == '__main__':
    sys.exit(main())
