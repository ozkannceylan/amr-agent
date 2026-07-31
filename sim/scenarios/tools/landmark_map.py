#!/usr/bin/env python3
"""landmark_map.py - landmark availability of a world at a scan plane.

WHAT THIS ANSWERS. Before any SLAM run, from geometry alone: standing at a
given point in the world, how much structure does a planar lidar see, and
does that structure pin the sensor's position in BOTH axes or only one?

WHY IT EXISTS. A long featureless aisle is a degenerate direction for scan
matching and no slam_toolbox parameter fixes it. If the only number anyone
ever sees is the SLAM result, a bad map looks like a tuning problem. This
script produces the PREDICTION the SLAM result is read against.

HOW IT WORKS.

  1. It parses the world SDF and takes the cross section of every box
     <visual> at the scan plane's z, because a gpu_lidar renders the scene
     and the visual geometry is what it returns. It does NOT copy a
     rectangle list out of the SDF by hand: a copied list goes stale the
     moment the world changes. Every rectangle comes from the file under
     test at run time.
  2. From each sample pose it casts the sensor's own ray set (same sample
     count, same angular limits, same range window as the sensor declared
     in agv/forklift/model.sdf) and finds the nearest hit per ray.
  3. For every hit it records the surface normal, and it reports the
     translation information matrix

         J = sum over hits of n n^T

     which is the standard point to plane scan matching information for
     translation. Every surface in this world is axis aligned, so J is
     diagonal and its two entries are simply the number of returns landing
     on x facing and on y facing surfaces. The ratio of the smaller to the
     larger is the anisotropy: 1.00 is perfectly conditioned, 0.00 means
     one axis carries no information at all and scan matching cannot tell
     where along it the sensor is.

WHAT IT IS NOT. This is a visibility computation, not a simulation of a
sensor. It has no noise, no beam divergence, no incidence angle dropout and
no reflectivity. It models the WORLD, not the vehicle: a real scan also
loses the sector its own mast occludes, which `--vehicle` adds when a
comparison against a live scan is wanted. It therefore states an UPPER
BOUND on the structure available at a pose. A pose it calls degenerate is
degenerate; a pose it calls well constrained may still be harder in a live
run than these numbers suggest.

`--vehicle` IS FOR COMPARING AGAINST A LIVE SCAN AND FOR NOTHING ELSE. The
mast rails return to the sensor at a fixed bearing and a fixed range, so
they tell a localiser nothing about where the vehicle is, and counting them
raises the anisotropy of a degenerate pose without making it any less
degenerate. The landmark tables are computed from the world alone.

Usage:
  python3 landmark_map.py [--world PATH] [--markdown]
  python3 landmark_map.py --exclude ChargeBay1Cabinet ChargeBay2Cabinet
  python3 landmark_map.py --pose X Y [--vehicle YAW] [--dump-ranges FILE]

No external dependency. Python standard library only.
"""

import argparse
import math
import os
import sys
import xml.etree.ElementTree as ET

# ----------------------------------------------------------------- sensor
# Quoted from agv/forklift/model.sdf, link nav_lidar_link / sensor nav_lidar.
# agv/ owns these numbers; this file reads them and never edits them.
PLANE_Z = 1.80
SAMPLES = 360
ANGLE_MIN = -3.1415927
ANGLE_MAX = 3.1415927
RANGE_MIN = 0.10
RANGE_MAX = 8.00
# gz spreads `samples` rays inclusively over [min, max], so the increment is
# (max - min) / (samples - 1) and the first and last ray coincide at +-pi.
# Confirmed against the angle_increment field of a live /forklift/scan
# message (worlds/WAREHOUSE_LANDMARKS.md section 6).
ANGLE_INC = (ANGLE_MAX - ANGLE_MIN) / (SAMPLES - 1)

# Sensor offset in the vehicle frame, for --vehicle only.
LIDAR_DX, LIDAR_DY = 0.55, -0.40
# The only vehicle geometry that crosses z = 1.80 IN THE RENDER is the pair
# of mast rails, 0.09 x 0.09 x 2.00 visuals at (-0.78, +-0.30, 1.05) in the
# model frame. The mast's 0.72 m wide collision box is NOT what the sensor
# sees, for the reason in the note on <visual> above.
MAST = [(-0.825, -0.735, 0.255, 0.345), (-0.825, -0.735, -0.345, -0.255)]

# Declared reporting boundaries. They are reporting boundaries, not physical
# constants: nothing changes at 0.05 or at 0.20 except the word in the table.
ANISO_DEGENERATE = 0.05
ANISO_WEAK = 0.20


# ------------------------------------------------------------------ world
def _pose(el):
    p = el.find('pose')
    if p is None:
        return [0.0] * 6
    v = [float(x) for x in p.text.split()]
    return v + [0.0] * (6 - len(v))


def load_rects(world_path, z, exclude=(), kind='visual'):
    """Cross section of every box <visual> (default) or <collision> at z.

    A gpu_lidar RENDERS THE SCENE, so what it returns is decided by the
    <visual> geometry and not by the <collision> geometry. The two are
    written identically for every solid in this world, and main() prints
    both counts so that a divergence shows up instead of being assumed
    away; but the default here is the one the sensor actually uses.

    Returns [(x0, x1, y0, y1, model_name)]. Rotated boxes are rejected
    loudly: an axis aligned cross section of a rotated box is wrong, and a
    silently wrong occluder would corrupt every figure downstream.
    """
    root = ET.parse(world_path).getroot()
    world = root.find('world')
    rects = []
    for model in world.findall('model'):
        name = model.get('name')
        if name in exclude:
            continue
        mp = _pose(model)
        for link in model.findall('link'):
            lp = _pose(link)
            for col in link.findall(kind):
                cp = _pose(col)
                box = col.find('geometry/box')
                if box is None:
                    continue                      # planes, cylinders: none here
                rot = [mp[i] + lp[i] + cp[i] for i in (3, 4, 5)]
                if any(abs(r) > 1e-9 for r in rot):
                    raise SystemExit(
                        f'{name}/{col.get("name")} is rotated {rot}; this '
                        'script only handles axis aligned boxes')
                sx, sy, sz = [float(v) for v in box.find('size').text.split()]
                cx = mp[0] + lp[0] + cp[0]
                cy = mp[1] + lp[1] + cp[1]
                cz = mp[2] + lp[2] + cp[2]
                if not (cz - sz / 2 <= z <= cz + sz / 2):
                    continue
                rects.append((cx - sx / 2, cx + sx / 2,
                              cy - sy / 2, cy + sy / 2, name))
    return rects


# -------------------------------------------------------------- ray cast
def cast(ox, oy, dx, dy, rects):
    """Nearest hit along a ray. Returns (t, normal_axis) or (inf, None)."""
    best, axis = math.inf, None
    for x0, x1, y0, y1, _ in rects:
        tmin, tmax = 0.0, math.inf
        enter = None
        for lo, hi, o, d, ax in ((x0, x1, ox, dx, 'x'), (y0, y1, oy, dy, 'y')):
            if abs(d) < 1e-12:
                if o < lo or o > hi:
                    tmin = math.inf
                    break
                continue
            t1, t2 = (lo - o) / d, (hi - o) / d
            if t1 > t2:
                t1, t2 = t2, t1
            if t1 > tmin:
                tmin, enter = t1, ax
            tmax = min(tmax, t2)
            if tmin > tmax:
                tmin = math.inf
                break
        if tmin < best and tmin > 0.0 and tmin != math.inf and tmin <= tmax:
            best, axis = tmin, enter
    return best, axis


def scan(ox, oy, rects):
    """One full sweep. Returns per ray (range, normal_axis, bearing)."""
    out = []
    for k in range(SAMPLES):
        a = ANGLE_MIN + k * ANGLE_INC
        dx, dy = math.cos(a), math.sin(a)
        t, axis = cast(ox, oy, dx, dy, rects)
        if t < RANGE_MIN or t > RANGE_MAX:
            out.append((math.inf, None, a))
        else:
            out.append((t, axis, a))
    return out


def inside(ox, oy, rects, margin=0.0):
    for x0, x1, y0, y1, name in rects:
        if x0 - margin <= ox <= x1 + margin and y0 - margin <= oy <= y1 + margin:
            return name
    return None


# --------------------------------------------------------------- metrics
def metrics(ox, oy, rays):
    finite = [r for r in rays if r[0] != math.inf]
    nx = sum(1 for r in finite if r[1] == 'x')
    ny = sum(1 for r in finite if r[1] == 'y')
    lo, hi = min(nx, ny), max(nx, ny)
    aniso = (lo / hi) if hi else 0.0
    weak = 'x' if nx < ny else ('y' if ny < nx else '-')

    # longest circular run of rays with no return, in degrees
    flags = [r[0] == math.inf for r in rays]
    gap = run = 0
    for f in flags + flags:
        run = run + 1 if f else 0
        gap = max(gap, run)
    gap = min(gap, SAMPLES)

    yaw_info = 0.0
    for t, axis, a in finite:
        px, py = t * math.cos(a), t * math.sin(a)
        n = (1.0, 0.0) if axis == 'x' else (0.0, 1.0)
        yaw_info += (n[0] * -py + n[1] * px) ** 2

    if not finite:
        verdict = 'no returns'
    elif aniso < ANISO_DEGENERATE:
        verdict = f'single axis, {weak} free'
    elif aniso < ANISO_WEAK:
        verdict = f'weak in {weak}'
    else:
        verdict = 'both axes'

    return {
        'n': len(finite), 'nx': nx, 'ny': ny, 'aniso': aniso,
        'gap': gap * ANGLE_INC * 180.0 / math.pi,
        'rmean': (sum(r[0] for r in finite) / len(finite)) if finite else 0.0,
        'rmax': max((r[0] for r in finite), default=0.0),
        'yaw': yaw_info, 'verdict': verdict, 'weak': weak,
    }


# ------------------------------------------------------------ pose sets
# Named lines through the world. Each entry is (line name, poses, note).
# Sensor poses, not vehicle poses: the navigation lidar leads the model
# origin by (0.55, -0.40), so a vehicle placed to put its lidar here sits
# at (x - 0.55, y + 0.40) when its yaw is zero.
def pose_sets(step=2.0):
    def line_x(y, x0, x1):
        n = int(round((x1 - x0) / step)) + 1
        return [(round(x0 + i * step, 3), y) for i in range(n)]

    def line_y(x, y0, y1):
        n = int(round((y1 - y0) / step)) + 1
        return [(x, round(y0 + i * step, 3)) for i in range(n)]

    return [
        ('Aisle A (y = +7.00)', line_x(7.00, -13.0, 13.0), 'x',
         'between RackRowA and RackRowB'),
        ('Aisle B (y = +0.65)', line_x(0.65, -13.0, 13.0), 'x',
         'between RackRowB and RackRowC'),
        ('Dock aisle (y = -5.50)', line_x(-5.50, -13.0, 13.0), 'x',
         'apron lane south of RackRowC'),
        ('Cross aisle (x = 0.00)', line_y(0.00, -8.0, 8.0), 'y',
         'the central cross aisle'),
        ('West end aisle (x = -13.00)', line_y(-13.00, -8.0, 8.0), 'y',
         'between the rack ends and the west wall'),
        ('East end aisle (x = +13.00)', line_y(13.00, -8.0, 8.0), 'y',
         'between the rack ends and the east wall'),
    ]


def along_track(x, y, rects, axis, d=0.25):
    """Displace the sensor +-d along the line and see what the scan does.

    Returns (rms, top10) averaged over the two directions:

      rms    RMS range difference over the rays returning in both sweeps.
             This is the point to point residual a scan matcher minimises.
      top10  the share of the squared residual carried by the ten largest
             single ray differences. It separates two very different ways
             of being matchable: a residual spread over hundreds of rays is
             a pose the matcher settles into from anywhere, while a residual
             carried almost entirely by ten grazing rays is a pose that
             matches only from a good initial guess, because those ten rays
             are the only thing that changed.
    """
    ref = scan(x, y, rects)
    rmss, shares = [], []
    for s in (+d, -d):
        px, py = (x + s, y) if axis == 'x' else (x, y + s)
        if inside(px, py, rects):
            continue
        cur = scan(px, py, rects)
        sq = sorted(((a[0] - b[0]) ** 2 for a, b in zip(ref, cur)
                     if a[0] != math.inf and b[0] != math.inf), reverse=True)
        if not sq:
            continue
        tot = sum(sq)
        rmss.append(math.sqrt(tot / len(sq)))
        shares.append(sum(sq[:10]) / tot if tot > 0 else 1.0)
    if not rmss:
        return 0.0, 1.0
    return sum(rmss) / len(rmss), sum(shares) / len(shares)


# ------------------------------------------------------------------ main
def fmt_table(rows, md):
    hdr = ('pose', 'n', 'Nx', 'Ny', 'aniso', 'maxgap', 'rmean', 'yawinfo',
           'rms25', 'top10', 'verdict')
    if md:
        out = ['| ' + ' | '.join(hdr) + ' |',
               '|' + '---|' * len(hdr)]
        for r in rows:
            out.append('| ' + ' | '.join(r) + ' |')
        return '\n'.join(out)
    w = [max(len(hdr[i]), max((len(r[i]) for r in rows), default=0))
         for i in range(len(hdr))]
    out = ['  '.join(h.ljust(w[i]) for i, h in enumerate(hdr))]
    out.append('  '.join('-' * w[i] for i in range(len(hdr))))
    for r in rows:
        out.append('  '.join(r[i].ljust(w[i]) for i in range(len(hdr))))
    return '\n'.join(out)


def row_for(x, y, rects, axis=None, label=None):
    m = metrics(x, y, scan(x, y, rects))
    if axis:
        rms, top10 = along_track(x, y, rects, axis)
    else:
        rms, top10 = float('nan'), float('nan')
    m['rms25'], m['top10'] = rms, top10
    return [label or f'({x:+6.2f},{y:+6.2f})', str(m['n']), str(m['nx']),
            str(m['ny']), f"{m['aniso']:.3f}", f"{m['gap']:.0f}",
            f"{m['rmean']:.2f}", f"{m['yaw']:.0f}",
            '-' if axis is None else f'{rms:.3f}',
            '-' if axis is None else f'{100 * top10:.0f}%',
            m['verdict']], m


def sweep(x, y, axis, rects, span=3.0, step=0.05):
    """Along track scan matching residual.

    Takes the sweep at (x, y) as the reference, then displaces the sensor
    along `axis` and reports the RMS range difference over the rays that
    return in BOTH sweeps. This is the quantity a scan matcher minimises,
    reduced to one dimension. A corridor whose residual stays near zero over
    metres of displacement is one the matcher cannot localise along; a
    residual with a second minimum at the rack bay pitch is an aliased
    corridor, where the matcher has more than one answer that fits.
    """
    ref = scan(x, y, rects)
    out = []
    n = int(round(span / step))
    for i in range(-n, n + 1):
        d = i * step
        px, py = (x + d, y) if axis == 'x' else (x, y + d)
        if inside(px, py, rects):
            out.append((d, None))
            continue
        cur = scan(px, py, rects)
        pairs = [(a[0], b[0]) for a, b in zip(ref, cur)
                 if a[0] != math.inf and b[0] != math.inf]
        if not pairs:
            out.append((d, None))
            continue
        rms = math.sqrt(sum((p - q) ** 2 for p, q in pairs) / len(pairs))
        out.append((d, rms))
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_world = os.path.normpath(
        os.path.join(here, '..', '..', 'worlds', 'warehouse.sdf'))

    ap = argparse.ArgumentParser()
    ap.add_argument('--world', default=default_world)
    ap.add_argument('--z', type=float, default=PLANE_Z)
    ap.add_argument('--geometry', choices=('visual', 'collision'),
                    default='visual',
                    help='which geometry the cross section comes from. A '
                         'gpu_lidar renders visuals; collision is offered '
                         'for comparison')
    ap.add_argument('--exclude', nargs='*', default=[],
                    help='model names to leave out of the world')
    ap.add_argument('--markdown', action='store_true')
    ap.add_argument('--pose', nargs=2, type=float, metavar=('X', 'Y'),
                    help='report one sensor pose instead of the pose sets')
    ap.add_argument('--vehicle', type=float, metavar='YAW',
                    help='with --pose: also occlude with the vehicle mast, '
                         'for comparison against a live scan. Only yaw 0 is '
                         'supported, because a rotated mast is not an AABB')
    ap.add_argument('--dump-ranges', metavar='FILE',
                    help='with --pose: write the 360 predicted ranges, one '
                         'per line, inf as "inf"')
    ap.add_argument('--step', type=float, default=2.0,
                    help='sample spacing along each line [m]')
    ap.add_argument('--sweep', nargs=3, metavar=('X', 'Y', 'AXIS'),
                    help='along track scan matching residual through a pose')
    args = ap.parse_args()

    rects = load_rects(args.world, args.z, exclude=set(args.exclude),
                       kind=args.geometry)
    other = load_rects(args.world, args.z, exclude=set(args.exclude),
                       kind=('collision' if args.geometry == 'visual'
                             else 'visual'))
    print(f'world       {args.world}')
    print(f'scan plane  z = {args.z:.2f} m, {SAMPLES} rays over '
          f'[{ANGLE_MIN:.4f}, {ANGLE_MAX:.4f}] rad, range '
          f'{RANGE_MIN:.2f} to {RANGE_MAX:.2f} m')
    print(f'occluders   {len(rects)} box {args.geometry} cross sections at '
          f'this plane ({len(other)} in the other geometry set'
          + ('; THEY DIFFER' if len(other) != len(rects) else ', same count')
          + ')'
          + (f' (excluding {", ".join(args.exclude)})' if args.exclude else ''))
    print()

    if args.sweep:
        x, y, axis = float(args.sweep[0]), float(args.sweep[1]), args.sweep[2]
        curve = sweep(x, y, axis, rects)
        print(f'along {axis} residual through ({x:+.2f}, {y:+.2f})')
        print('  d[m]   rms[m]')
        for d, r in curve:
            if abs(d * 20 - round(d * 20)) > 1e-6:
                pass
            if round(d / 0.25, 6) == round(round(d / 0.25), 6):
                print(f'  {d:+5.2f}  ' + ('  -  ' if r is None else f'{r:.3f}'))
        vals = [(d, r) for d, r in curve if r is not None and abs(d) > 1e-9]
        pos = [(d, r) for d, r in vals if d > 0]
        neg = [(d, r) for d, r in vals if d < 0]
        for tag, half in (('+', pos), ('-', neg)):
            for thr in (0.05, 0.10, 0.25):
                hit = next((d for d, r in sorted(half, key=lambda t: abs(t[0]))
                            if r >= thr), None)
                print(f'  first |d| with rms >= {thr:.2f} m on the {tag} side: '
                      + ('none within the span' if hit is None
                         else f'{abs(hit):.2f} m'))
        return

    if args.pose:
        x, y = args.pose
        if args.vehicle is not None:
            if abs(args.vehicle) > 1e-9:
                raise SystemExit('--vehicle supports yaw 0 only')
            rects = rects + [(x - LIDAR_DX + m[0], x - LIDAR_DX + m[1],
                              y - LIDAR_DY + m[2], y - LIDAR_DY + m[3],
                              'Forklift/mast_rail') for m in MAST]
        rays = scan(x, y, rects)
        m = metrics(x, y, rays)
        row, _ = row_for(x, y, rects)
        print(fmt_table([row], args.markdown))
        if args.dump_ranges:
            with open(args.dump_ranges, 'w', newline='\n') as f:
                for t, _, _ in rays:
                    f.write('inf\n' if t == math.inf else f'{t:.4f}\n')
            print(f'\nwrote {args.dump_ranges}')
        return

    for name, poses, axis, note in pose_sets(args.step):
        rows = []
        worst = None
        for (x, y) in poses:
            blocked = inside(x, y, rects)
            if blocked:
                rows.append([f'({x:+6.2f},{y:+6.2f})', '-', '-', '-', '-',
                             '-', '-', '-', '-', '-', f'inside {blocked}'])
                continue
            r, m = row_for(x, y, rects, axis)
            rows.append(r)
            if worst is None or m['aniso'] < worst[1]['aniso']:
                worst = ((x, y), m)
        print(f'### {name}   ({note})')
        print()
        print(fmt_table(rows, args.markdown))
        if worst:
            (wx, wy), m = worst
            print(f'\nworst conditioned: ({wx:+.2f}, {wy:+.2f}) '
                  f'aniso {m["aniso"]:.3f}, {m["verdict"]}')
        print()


if __name__ == '__main__':
    sys.exit(main())
