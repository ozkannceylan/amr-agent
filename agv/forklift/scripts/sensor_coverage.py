#!/usr/bin/env python3
"""sensor_coverage.py - measure the forklift's scanner coverage from model.sdf.

WHAT THIS IS. A geometric measurement of what the three scanners declared
in ../model.sdf can and cannot see, computed from the model file itself.
It reads the poses, apertures and ranges out of the SDF and ray-casts them
against the vehicle's own geometry, also read out of the SDF. Nothing is
typed in twice, so the numbers follow the model when the model changes and
a stale figure is a re-run away from being caught.

WHAT THIS IS NOT.

  * Not a simulation. No Gazebo, no renderer, no physics. Every figure it
    prints is a computation on planar geometry.
  * Not a safety claim of any kind. A computed sight line is not a
    protective field: no integrity, no OSSD, no fault reaction, no
    response time, no stopping distance (invariant 1).
  * Not a statement about the world. The vehicle occludes itself and that
    is all this measures. Racking, other vehicles, people and dust are
    the world's business.

THE OCCLUDER SET IS THE VISUAL SET, AND THAT MATTERS. A gz `gpu_lidar` is
a rendering sensor: it sees what the renderer draws, which is <visual>
geometry. A shape declared only as <collision> is invisible to it. This
model has such a shape - the mast's 0.10 x 0.72 x 2.00 collision box,
whose visual counterpart is two 0.09 rails and a crossmember. So the
script computes coverage twice, and the difference between the two is
itself a finding:

  visual      what the simulated sensor will report
  physical    visual + collision, what the vehicle's body actually blocks

A coverage claim is made on the PHYSICAL set, because it is the smaller
one. The visual set is reported beside it so a live run can be checked
against the right number.

Usage:

    python3 agv/forklift/scripts/sensor_coverage.py            # full report
    python3 agv/forklift/scripts/sensor_coverage.py --step 0.05
    python3 agv/forklift/scripts/sensor_coverage.py --nav-sweep

Every arc this prints is quantised to the bearing step (default 0.1 deg),
so a boundary is that step, never finer.
"""

import argparse
import math
import os
import xml.etree.ElementTree as ET

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODEL = os.path.normpath(os.path.join(_HERE, '..', 'model.sdf'))

# Links whose pose the mast joint moves, and the joint that moves them.
_LIFTED_LINKS = ('carriage', 'fork_left', 'fork_right')
# Links the steer joint rotates, and the axis it rotates them about.
_STEERED_LINKS = ('steer_link', 'drive_wheel')
_STEER_AXIS_XY = (0.55, 0.0)


# --------------------------------------------------------------------------
# small 3D pose helpers. Poses in SDF are x y z roll pitch yaw.
# --------------------------------------------------------------------------

def parse_pose(text):
    if text is None:
        return (0.0,) * 6
    parts = [float(v) for v in text.split()]
    while len(parts) < 6:
        parts.append(0.0)
    return tuple(parts[:6])


def rot_matrix(roll, pitch, yaw):
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                       for j in range(3)) for i in range(3))


def mat_vec(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def compose(parent, child):
    """Compose two (x, y, z, R) poses given as (translation, matrix)."""
    pt, pr = parent
    ct, cr = child
    t = tuple(pt[i] + mat_vec(pr, ct)[i] for i in range(3))
    return (t, mat_mul(pr, cr))


def pose_to_tm(pose):
    x, y, z, r, p, yw = pose
    return ((x, y, z), rot_matrix(r, p, yw))


# --------------------------------------------------------------------------
# cross sections: the polygon a solid cuts out of the horizontal plane z
# --------------------------------------------------------------------------

_BOX_EDGES = [(0, 1), (1, 3), (3, 2), (2, 0),
              (4, 5), (5, 7), (7, 6), (6, 4),
              (0, 4), (1, 5), (2, 6), (3, 7)]


def convex_hull(points):
    pts = sorted(set((round(p[0], 9), round(p[1], 9)) for p in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

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


def box_section(tm, size, z):
    """Polygon cut from a box by the plane z. Exact for any orientation."""
    (tx, ty, tz), rot = tm
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                local = (sx * hx, sy * hy, sz * hz)
                w = mat_vec(rot, local)
                corners.append((tx + w[0], ty + w[1], tz + w[2]))
    hits = []
    for i, j in _BOX_EDGES:
        a, b = corners[i], corners[j]
        if (a[2] - z) * (b[2] - z) > 0:
            continue
        if abs(a[2] - b[2]) < 1e-12:
            if abs(a[2] - z) < 1e-12:
                hits.append((a[0], a[1]))
                hits.append((b[0], b[1]))
            continue
        t = (z - a[2]) / (b[2] - a[2])
        if -1e-9 <= t <= 1 + 1e-9:
            hits.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    if len(hits) < 3:
        return None
    return convex_hull(hits)


def cylinder_section(tm, radius, length, z, facets=24):
    """Polygon cut from a cylinder by the plane z.

    Handles the two orientations this model uses and refuses anything
    else rather than approximating it silently.
    """
    (tx, ty, tz), rot = tm
    axis = mat_vec(rot, (0.0, 0.0, 1.0))
    if abs(axis[2]) > 0.99:                       # upright: a circle
        dz = abs(z - tz)
        if dz > length / 2.0:
            return None
        return [(tx + radius * math.cos(2 * math.pi * k / facets),
                 ty + radius * math.sin(2 * math.pi * k / facets))
                for k in range(facets)]
    if abs(axis[2]) > 0.01:
        raise ValueError('cylinder axis is neither vertical nor horizontal')
    dz = abs(z - tz)                              # lying down: a rectangle
    if dz >= radius:
        return None
    half_chord = math.sqrt(radius * radius - dz * dz)
    ax = (axis[0], axis[1])
    norm = math.hypot(*ax)
    ax = (ax[0] / norm, ax[1] / norm)
    perp = (-ax[1], ax[0])
    pts = []
    for sa in (-1, 1):
        for sp in (-1, 1):
            pts.append((tx + sa * (length / 2.0) * ax[0] + sp * half_chord * perp[0],
                        ty + sa * (length / 2.0) * ax[1] + sp * half_chord * perp[1]))
    return convex_hull(pts)


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------

class Solid(object):
    def __init__(self, link, name, kind, tm, geom):
        self.link = link
        self.name = name
        self.kind = kind          # 'visual' or 'collision'
        self.tm = tm
        self.geom = geom          # ('box', size) or ('cylinder', r, l)

    def section(self, z):
        if self.geom[0] == 'box':
            return box_section(self.tm, self.geom[1], z)
        return cylinder_section(self.tm, self.geom[1], self.geom[2], z)

    def z_span(self):
        (tx, ty, tz), rot = self.tm
        if self.geom[0] == 'box':
            hx, hy, hz = [s / 2.0 for s in self.geom[1]]
            half = sum(abs(rot[2][k]) * h for k, h in enumerate((hx, hy, hz)))
        else:
            axis = mat_vec(rot, (0.0, 0.0, 1.0))
            half = abs(axis[2]) * self.geom[2] / 2.0 + \
                math.sqrt(max(0.0, 1.0 - axis[2] ** 2)) * self.geom[1]
        return (tz - half, tz + half)


class Sensor(object):
    def __init__(self, name, link, x, y, z, yaw, a_min, a_max, samples,
                 r_min, r_max, rate, topic, frame):
        self.name = name
        self.link = link
        self.x, self.y, self.z, self.yaw = x, y, z, yaw
        self.a_min, self.a_max = a_min, a_max
        self.samples = samples
        self.r_min, self.r_max = r_min, r_max
        self.rate = rate
        self.topic = topic
        self.frame = frame

    @property
    def aperture(self):
        return self.a_max - self.a_min

    def bearing_window(self):
        """Aperture expressed as absolute bearings in the vehicle frame."""
        return (self.yaw + self.a_min, self.yaw + self.a_max)


def read_geometry(elem):
    geom = elem.find('geometry')
    if geom is None:
        return None
    box = geom.find('box')
    if box is not None:
        return ('box', tuple(float(v) for v in box.findtext('size').split()))
    cyl = geom.find('cylinder')
    if cyl is not None:
        return ('cylinder', float(cyl.findtext('radius')),
                float(cyl.findtext('length')))
    return None


def load_model(path):
    root = ET.parse(path).getroot()
    model = root.find('model')
    solids, sensors = [], []
    for link in model.findall('link'):
        lname = link.get('name')
        lpose = parse_pose(link.findtext('pose'))
        ltm = pose_to_tm(lpose)
        for kind in ('visual', 'collision'):
            for elem in link.findall(kind):
                geom = read_geometry(elem)
                if geom is None:
                    continue
                tm = compose(ltm, pose_to_tm(parse_pose(elem.findtext('pose'))))
                solids.append(Solid(lname, elem.get('name'), kind, tm, geom))
        for sensor in link.findall('sensor'):
            spose = parse_pose(sensor.findtext('pose'))
            stm = compose(ltm, pose_to_tm(spose))
            (sx, sy, sz), srot = stm
            yaw = math.atan2(srot[1][0], srot[0][0])
            hor = sensor.find('lidar/scan/horizontal')
            rng = sensor.find('lidar/range')
            sensors.append(Sensor(
                sensor.get('name'), lname, sx, sy, sz, yaw,
                float(hor.findtext('min_angle')), float(hor.findtext('max_angle')),
                int(hor.findtext('samples')),
                float(rng.findtext('min')), float(rng.findtext('max')),
                float(sensor.findtext('update_rate')),
                sensor.findtext('topic'), sensor.findtext('gz_frame_id')))
    return solids, sensors


def occluders(solids, z, kinds=('visual',), lift=0.0, steer=0.0,
              skip_links=()):
    """Polygons blocking the horizontal plane z, in the vehicle frame."""
    out = []
    for solid in solids:
        if solid.kind not in kinds or solid.link in skip_links:
            continue
        tm = solid.tm
        if solid.link in _LIFTED_LINKS and lift:
            (tx, ty, tz), rot = tm
            tm = ((tx, ty, tz + lift), rot)
        if solid.link in _STEERED_LINKS and steer:
            (tx, ty, tz), rot = tm
            ax, ay = _STEER_AXIS_XY
            c, s = math.cos(steer), math.sin(steer)
            dx, dy = tx - ax, ty - ay
            tm = ((ax + c * dx - s * dy, ay + s * dx + c * dy, tz),
                  mat_mul(rot_matrix(0, 0, steer), rot))
        poly = Solid(solid.link, solid.name, solid.kind, tm, solid.geom).section(z)
        if poly and len(poly) >= 3:
            out.append((solid.link + '/' + solid.name, poly))
    return out


# --------------------------------------------------------------------------
# visibility
# --------------------------------------------------------------------------

def _seg_hits_poly(p0, p1, poly):
    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

    n = len(poly)
    inside = True
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        if cross(ax, ay, bx, by, p1[0], p1[1]) < 0:
            inside = False
            break
    if inside:
        return True
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        d1 = cross(p0[0], p0[1], p1[0], p1[1], a[0], a[1])
        d2 = cross(p0[0], p0[1], p1[0], p1[1], b[0], b[1])
        d3 = cross(a[0], a[1], b[0], b[1], p0[0], p0[1])
        d4 = cross(a[0], a[1], b[0], b[1], p1[0], p1[1])
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
    return False


def blocked(p0, p1, polys):
    for _name, poly in polys:
        if _seg_hits_poly(p0, p1, poly):
            return True
    return False


def blocker(p0, p1, polys):
    """Name of the first shape on the sight line, or None."""
    for name, poly in polys:
        if _seg_hits_poly(p0, p1, poly):
            return name
    return None


def wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a <= -math.pi:
        a += 2 * math.pi
    return a


def why_not(sensor, pt, polys):
    """None when the sensor sees the point, else the reason it does not."""
    dx, dy = pt[0] - sensor.x, pt[1] - sensor.y
    dist = math.hypot(dx, dy)
    if dist > sensor.r_max:
        return 'beyond range (%.2f m)' % dist
    if dist < sensor.r_min:
        return 'inside range_min (%.2f m)' % dist
    rel = wrap(math.atan2(dy, dx) - sensor.yaw)
    if rel < sensor.a_min - 1e-12 or rel > sensor.a_max + 1e-12:
        return 'in the blind sector (%.1f deg off boresight)' % deg(rel)
    hit = blocker((sensor.x, sensor.y), pt, polys)
    if hit is not None:
        return 'occluded by ' + hit
    return None


def sees(sensor, pt, polys):
    return why_not(sensor, pt, polys) is None


# --------------------------------------------------------------------------
# arcs
# --------------------------------------------------------------------------

def arcs_from_flags(flags, step_deg, want=True):
    """Contiguous runs of `want` in a circular boolean list, in degrees."""
    n = len(flags)
    if all(f == want for f in flags):
        return [(0.0, 360.0, 360.0)]
    if not any(f == want for f in flags):
        return []
    start = 0
    while flags[start] == want:
        start += 1
    runs, i = [], 0
    cur = None
    while i < n:
        idx = (start + i) % n
        if flags[idx] == want:
            if cur is None:
                cur = idx
        else:
            if cur is not None:
                runs.append((cur, (idx - 1) % n))
                cur = None
        i += 1
    if cur is not None:
        runs.append((cur, (start - 1) % n))
    out = []
    for a, b in runs:
        a_deg = a * step_deg
        width = (((b - a) % n) + 1) * step_deg
        out.append((a_deg, (a_deg + width) % 360.0, width))
    return out


def measure(flags, step_deg):
    return sum(1 for f in flags if f) * step_deg


def fmt_arcs(arcs, limit=12):
    if not arcs:
        return 'none'
    txt = ', '.join('[%6.1f, %6.1f) %5.1f deg' % a for a in arcs[:limit])
    if len(arcs) > limit:
        txt += ', ... (%d more)' % (len(arcs) - limit)
    return txt


# --------------------------------------------------------------------------
# the vehicle's plan outline, and an offset of it
# --------------------------------------------------------------------------

def plan_hull(solids, kinds=('visual', 'collision'), skip_links=()):
    pts = []
    for solid in solids:
        if solid.kind not in kinds or solid.link in skip_links:
            continue
        lo, hi = solid.z_span()
        for z in (lo + 1e-4, (lo + hi) / 2.0, hi - 1e-4):
            poly = solid.section(z)
            if poly:
                pts.extend(poly)
    return convex_hull(pts)


def offset_samples(hull, distance, per_edge=40, arc_steps=12):
    """Points on the hull grown by `distance`, walked once round."""
    out = []
    n = len(hull)
    for i in range(n):
        a = hull[i]
        b = hull[(i + 1) % n]
        ex, ey = b[0] - a[0], b[1] - a[1]
        length = math.hypot(ex, ey)
        if length < 1e-9:
            continue
        nx, ny = ey / length, -ex / length      # outward for a CCW hull
        for k in range(per_edge):
            t = k / float(per_edge)
            out.append((a[0] + t * ex + distance * nx,
                        a[1] + t * ey + distance * ny))
        prev = hull[(i + 1) % n]
        nxt = hull[(i + 2) % n]
        e2x, e2y = nxt[0] - prev[0], nxt[1] - prev[1]
        l2 = math.hypot(e2x, e2y)
        if l2 < 1e-9:
            continue
        n2x, n2y = e2y / l2, -e2x / l2
        a0 = math.atan2(ny, nx)
        a1 = math.atan2(n2y, n2x)
        sweep = wrap(a1 - a0)
        for k in range(1, arc_steps):
            ang = a0 + sweep * k / float(arc_steps)
            out.append((b[0] + distance * math.cos(ang),
                        b[1] + distance * math.sin(ang)))
    return out


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def deg(rad):
    return rad * 180.0 / math.pi


def bearings(step_deg):
    n = int(round(360.0 / step_deg))
    return n, [math.radians(i * step_deg) for i in range(n)]


def section(title):
    print('')
    print('=' * 74)
    print(title)
    print('=' * 74)


def report_inventory(solids, sensors):
    section('1. SENSORS, AS DECLARED IN model.sdf')
    print('%-22s %-22s %7s %7s %7s %8s %6s' %
          ('sensor', 'frame (gz_frame_id)', 'x', 'y', 'z', 'yaw deg', 'ap deg'))
    for s in sensors:
        print('%-22s %-22s %7.3f %7.3f %7.3f %8.1f %6.1f' %
              (s.name, s.frame, s.x, s.y, s.z, deg(s.yaw), deg(s.aperture)))
    print('')
    print('%-22s %8s %9s %9s %8s %9s  %s' %
          ('sensor', 'samples', 'res deg', 'range m', 'rate Hz', 'blind deg',
           'topic'))
    for s in sensors:
        res = deg(s.aperture) / (s.samples - 1) if s.samples > 1 else 0.0
        print('%-22s %8d %9.4f %4.2f-%4.2f %8.1f %9.1f  %s' %
              (s.name, s.samples, res, s.r_min, s.r_max, s.rate,
               max(0.0, 360.0 - deg(s.aperture)), s.topic))
    total = sum(s.samples for s in sensors)
    print('')
    print('total rays per 100 ms cycle: %d  (one sensor of 181 before this '
          'layout)' % total)
    print('')
    print('self check - no sensor may render its own mounting:')
    for s in sensors:
        own = [n for n, _p in occluders(solids, s.z, kinds=('visual', 'collision'))
               if n.startswith(s.link + '/')]
        print('   %-22s own geometry crossing its plane: %s' %
              (s.name, ', '.join(own) if own else 'none'))


def report_occluders(solids, z, lift, kinds, label):
    polys = occluders(solids, z, kinds=kinds, lift=lift)
    print('')
    print('-- occluders crossing z = %.2f m, %s, lift = %.2f m' % (z, label, lift))
    if not polys:
        print('   none')
    for name, poly in polys:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        print('   %-34s x [%6.3f, %6.3f]  y [%6.3f, %6.3f]' %
              (name, min(xs), max(xs), min(ys), max(ys)))
    return polys


def coverage_flags(sensor, polys, radius, angs):
    out = []
    for a in angs:
        pt = (radius * math.cos(a), radius * math.sin(a))
        out.append(sees(sensor, pt, polys))
    return out


def norm360(d):
    return d % 360.0


def causes(sensors, polys, radius, angs, step, flags):
    """For every uncovered bearing, why each sensor missed it."""
    tally = {}
    for i, ok in enumerate(flags):
        if ok:
            continue
        pt = (radius * math.cos(angs[i]), radius * math.sin(angs[i]))
        for s in sensors:
            reason = why_not(s, pt, polys)
            reason = reason.split(' (')[0]
            key = (s.name, reason)
            tally[key] = tally.get(key, 0) + 1
    return sorted(tally.items(), key=lambda kv: -kv[1])


def print_causes(tally, step):
    for (name, reason), count in tally:
        print('        %-22s %-34s %5.1f deg' % (name, reason, count * step))


def report_safety(solids, sensors, step, load_poly=None):
    front = [s for s in sensors if s.name == 'safety_scanner_front'][0]
    rear = [s for s in sensors if s.name == 'safety_scanner_rear'][0]
    n, angs = bearings(step)
    z = front.z

    section('2. THE TWO SAFETY SCANNERS - PLANE, OCCLUDERS, APERTURE')
    print('scan planes: front z = %.3f m, rear z = %.3f m -> %s' %
          (front.z, rear.z,
           'COPLANAR' if abs(front.z - rear.z) < 1e-9 else 'NOT coplanar'))
    for s in (front, rear):
        lo, hi = s.bearing_window()
        print('%-22s mounted (%6.3f, %6.3f), boresight %6.1f deg: covers '
              '[%5.1f, %5.1f) deg, blind [%5.1f, %5.1f) deg' %
              (s.name, s.x, s.y, norm360(deg(s.yaw)),
               norm360(deg(lo)), norm360(deg(hi)),
               norm360(deg(hi)), norm360(deg(lo))))
    print('(vehicle bearings: 0 deg is +x, the drive end; 180 deg is the '
          'fork direction; 90 deg is +y, left)')
    ap_flags_f, ap_flags_r = [], []
    for a in angs:
        ap_flags_f.append(front.a_min <= wrap(a - front.yaw) <= front.a_max)
        ap_flags_r.append(rear.a_min <= wrap(a - rear.yaw) <= rear.a_max)
    both = [f and r for f, r in zip(ap_flags_f, ap_flags_r)]
    either = [f or r for f, r in zip(ap_flags_f, ap_flags_r)]
    print('')
    print('APERTURE ONLY, occlusion ignored (direction, not sight line):')
    print('  front covers %6.1f deg   rear covers %6.1f deg' %
          (measure(ap_flags_f, step), measure(ap_flags_r, step)))
    print('  union        %6.1f deg   overlap     %6.1f deg' %
          (measure(either, step), measure(both, step)))
    print('  union gaps   : %s' % fmt_arcs(arcs_from_flags(either, step, False)))
    print('  overlap arcs : %s' % fmt_arcs(arcs_from_flags(both, step, True)))

    for kinds, label in ((('visual',), 'visual set (what the gpu_lidar sees)'),
                         (('visual', 'collision'), 'physical set (visual + collision)')):
        section('3. SAFETY SCANNER SIGHT LINES - %s' % label.upper())
        polys = report_occluders(solids, z, 0.0, kinds, label)
        if load_poly:
            polys = polys + [load_poly]
        print('')
        print('Bearings are measured about the MODEL ORIGIN, at the stated')
        print('radius. A circle of radius under 0.86 m lies partly inside the')
        print('vehicle, so the near field is measured in section 4 instead.')
        print('')
        print('%8s %9s %9s %9s %9s   %s' %
              ('radius', 'front', 'rear', 'either', 'both', 'uncovered arcs'))
        for radius in (1.0, 2.0, 3.0, 4.0, 5.0, 5.5):
            ff = coverage_flags(front, polys, radius, angs)
            fr = coverage_flags(rear, polys, radius, angs)
            either_f = [a or b for a, b in zip(ff, fr)]
            both_f = [a and b for a, b in zip(ff, fr)]
            print('%6.1f m %8.1fd %8.1fd %8.1fd %8.1fd   %s' %
                  (radius, measure(ff, step), measure(fr, step),
                   measure(either_f, step), measure(both_f, step),
                   fmt_arcs(arcs_from_flags(either_f, step, False), limit=6)))
            if measure(either_f, step) < 360.0:
                print_causes(causes((front, rear), polys, radius, angs, step,
                                    either_f), step)
        print('(d = degrees of the 360 deg around the model origin; the')
        print(' indented lines are why each scanner missed the uncovered')
        print(' bearings, and they sum to more than the gap because both')
        print(' scanners miss every one of them.)')

    print('')
    print('DETECTION RADIUS ABOUT THE ORIGIN. The 5.50 m range is measured')
    print('from the sensor, and both sensors sit 0.83 m off the origin, so')
    print('the radius guaranteed all the way round is smaller. Swept at')
    print('1.0 deg bearing steps and 0.05 m radius steps, physical set:')
    polys = occluders(solids, z, kinds=('visual', 'collision'))
    _n, coarse = bearings(1.0)
    worst = (999.0, 0.0)
    reach = []
    for i, a in enumerate(coarse):
        best = 0.0
        r = front.r_max
        while r >= 0.9:
            pt = (r * math.cos(a), r * math.sin(a))
            if sees(front, pt, polys) or sees(rear, pt, polys):
                best = r
                break
            r -= 0.05
        reach.append(best)
        if best < worst[0]:
            worst = (best, i * 1.0)
    print('  smallest all-round radius : %.2f m, at bearing %.1f deg' % worst)
    print('  largest                   : %.2f m' % max(reach))
    print('  mean over bearings        : %.2f m' % (sum(reach) / len(reach)))

    return front, rear


def report_hull(solids, sensors, step):
    front = [s for s in sensors if s.name == 'safety_scanner_front'][0]
    rear = [s for s in sensors if s.name == 'safety_scanner_rear'][0]
    section('4. PERIMETER COVERAGE ON AN OFFSET OF THE VEHICLE OUTLINE')
    hull = plan_hull(solids, skip_links=('safety_scanner_front_link',
                                         'safety_scanner_rear_link',
                                         'nav_lidar_link'))
    xs = [p[0] for p in hull]
    ys = [p[1] for p in hull]
    print('plan outline (convex hull of every visual and collision shape):')
    print('  x [%6.3f, %6.3f]  y [%6.3f, %6.3f]  %d vertices' %
          (min(xs), max(xs), min(ys), max(ys), len(hull)))
    print('')
    print('A point on the offset curve counts as covered when one scanner')
    print('has it in aperture, in range and with a clear sight line.')
    print('')
    print('%8s %9s %9s %9s %9s' %
          ('offset', 'points', 'front', 'rear', 'either'))
    polys = occluders(solids, front.z, kinds=('visual', 'collision'))
    misses = {}
    for dist in (0.10, 0.30, 0.50, 1.00, 2.00):
        pts = offset_samples(hull, dist)
        cf = cr = ce = 0
        for p in pts:
            sf = sees(front, p, polys)
            sr = sees(rear, p, polys)
            cf += sf
            cr += sr
            if sf or sr:
                ce += 1
            else:
                misses.setdefault(dist, []).append(p)
        print('%6.2f m %9d %8.1f%% %8.1f%% %8.1f%%' %
              (dist, len(pts), 100.0 * cf / len(pts),
               100.0 * cr / len(pts), 100.0 * ce / len(pts)))
    for dist in sorted(misses):
        pts = misses[dist]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        print('')
        print('  uncovered at offset %.2f m: %d of the sampled points,' %
              (dist, len(pts)))
        print('    x [%6.3f, %6.3f]  y [%6.3f, %6.3f]' %
              (min(xs), max(xs), min(ys), max(ys)))
        tally = {}
        for p in pts:
            for s in (front, rear):
                reason = why_not(s, p, polys).split(' (')[0]
                tally[(s.name, reason)] = tally.get((s.name, reason), 0) + 1
        for (name, reason), count in sorted(tally.items(), key=lambda kv: -kv[1]):
            print('    %-22s %-34s %4d points' % (name, reason, count))


def report_states(solids, sensors, step):
    """Coverage under the vehicle's own moving parts and under a load."""
    front = [s for s in sensors if s.name == 'safety_scanner_front'][0]
    rear = [s for s in sensors if s.name == 'safety_scanner_rear'][0]
    n, angs = bearings(step)
    z = front.z
    section('5. WHAT THE VEHICLE\'S OWN MOTION DOES TO THE SAFETY PLANE')
    print('Carriage travel and steer angle both move geometry through the')
    print('scan plane. Measured at radius 2.0 m, physical occluder set.')
    print('')
    print('%8s %8s %9s %-38s %s' %
          ('lift m', 'steer', 'either', 'uncovered arcs', 'what crosses the plane'))
    for lift, steer in ((0.00, 0.0), (0.04, 0.0), (0.05, 0.0), (0.075, 0.0),
                        (0.10, 0.0), (0.11, 0.0), (0.20, 0.0), (0.80, 0.0),
                        (1.60, 0.0), (0.00, 1.31), (0.00, -1.31)):
        polys = occluders(solids, z, kinds=('visual', 'collision'),
                          lift=lift, steer=steer)
        ff = coverage_flags(front, polys, 2.0, angs)
        fr = coverage_flags(rear, polys, 2.0, angs)
        either_f = [a or b for a, b in zip(ff, fr)]
        cov = measure(either_f, step)
        moving = sorted(set(n.split('/')[0] for n, _p in polys
                            if n.split('/')[0] in _LIFTED_LINKS))
        print('%8.3f %8.2f %8.1fd %-38s %s' %
              (lift, steer, cov,
               fmt_arcs(arcs_from_flags(either_f, step, False), limit=2),
               ', '.join(moving) if moving else 'no lifted part'))

    section('6. LOAD OCCLUSION - A PALLET IN FRONT OF THE FORKS')
    print('Load modelled on sim/worlds/forklift_arena.sdf\'s Pallet: 1.20 m')
    print('along x, 1.00 m along y, deck 0.16 m tall. Two cases: the pallet')
    print('standing on the floor as the forks enter it, and the pallet')
    print('carried on the tines at a given lift.')
    print('')
    print('%-30s %6s %9s %9s   %s' %
          ('case', 'lift', 'crosses z', 'either', 'uncovered arcs'))
    pallet_x = (-2.05, -0.85)
    pallet_y = (-0.50, 0.50)
    cases = [('pallet on the floor, entering', 0.00, 0.00, 0.16),
             ('pallet on the tines', 0.00, 0.10, 0.26),
             ('pallet on the tines', 0.05, 0.15, 0.31),
             ('pallet on the tines', 0.10, 0.20, 0.36),
             ('pallet on the tines', 0.30, 0.40, 0.56),
             ('pallet on the tines', 1.60, 1.70, 1.86)]
    for label, lift, lo, hi in cases:
        crosses = lo <= z <= hi
        polys = occluders(solids, z, kinds=('visual', 'collision'), lift=lift)
        if crosses:
            polys = polys + [('load/pallet',
                              [(pallet_x[0], pallet_y[0]),
                               (pallet_x[1], pallet_y[0]),
                               (pallet_x[1], pallet_y[1]),
                               (pallet_x[0], pallet_y[1])])]
        ff = coverage_flags(front, polys, 2.0, angs)
        fr = coverage_flags(rear, polys, 2.0, angs)
        either_f = [a or b for a, b in zip(ff, fr)]
        cov = measure(either_f, step)
        print('%-30s %6.2f %9s %8.1fd   %s' %
              (label, lift, 'yes' if crosses else 'no', cov,
               fmt_arcs(arcs_from_flags(either_f, step, False), limit=3)))
        if cov < 360.0:
            print_causes(causes((front, rear), polys, 2.0, angs, step,
                                either_f), step)
    print('')
    print('A 2D scan plane is only occluded by what intersects it. This')
    print('model\'s pallet clears the 0.15 m plane once the tines are above')
    print('0.06 m of travel, and the tines themselves clear it above 0.10 m.')
    print('That is a property of a rectangular pallet with a flat deck; a')
    print('real load overhangs, sags and is strapped, and ISO 3691-4 treats')
    print('load occlusion in the load direction as a residual to be handled')
    print('by field switching and speed, not by mounting.')


def report_nav(solids, sensors, step):
    nav = [s for s in sensors if s.name == 'nav_lidar'][0]
    n, angs = bearings(step)
    section('7. NAVIGATION LIDAR - SHADOWS OF THE VEHICLE\'S OWN STRUCTURE')
    print('Bearings are measured AT THE SENSOR, which is the frame a scan')
    print('is published in. A shadow is a bearing whose ray leaves the')
    print('sensor and hits the vehicle.')
    for kinds, label in ((('visual',), 'visual set'),
                         (('visual', 'collision'), 'physical set')):
        print('')
        print('-- %s' % label)
        for lift in (0.0, 0.8, 1.18, 1.20, 1.40, 1.60):
            polys = occluders(solids, nav.z, kinds=kinds, lift=lift,
                              skip_links=('nav_lidar_link',))
            flags = []
            for a in angs:
                pt = (nav.x + 20.0 * math.cos(a), nav.y + 20.0 * math.sin(a))
                flags.append(not blocked((nav.x, nav.y), pt, polys))
            shadow = 360.0 - measure(flags, step)
            fork_axis_clear = flags[int(round(180.0 / step)) % n]
            arcs = arcs_from_flags(flags, step, False)
            width5 = ', '.join('%.2f m' % (2 * 5.0 * math.sin(math.radians(a[2]) / 2))
                               for a in arcs)
            print('   lift %4.2f m: shadow %5.1f deg, fork axis (180 deg) %s, '
                  'arcs %s' %
                  (lift, shadow, 'clear' if fork_axis_clear else 'BLOCKED',
                   fmt_arcs(arcs, limit=6)))
            print('                width of each shadow at 5 m range: %s' % width5)

    section('8. WHY THE NAVIGATION LIDAR IS MOUNTED ABOVE THE GUARD')
    print('A 360 deg aperture is only worth its cost where the sensor')
    print('clears the body. Same computation, same model, at candidate')
    print('mounting heights and positions:')
    print('')
    print('%-42s %10s %10s' % ('candidate mount', 'shadow', 'usable'))
    candidates = [
        ('ahead of the counterweight  (0.90, 0.00, 0.55)', 0.90, 0.00, 0.55),
        ('beside the chassis          (0.00, 0.50, 0.55)', 0.00, 0.50, 0.55),
        ('inside the chassis band     (0.00, 0.00, 0.45)', 0.00, 0.00, 0.45),
        ('on the guard deck           (0.30, -0.40, 0.75)', 0.30, -0.40, 0.75),
        ('under the guard roof        (0.30, -0.40, 1.20)', 0.30, -0.40, 1.20),
        ('on the guard roof, centred  (0.55, 0.00, 1.80)', 0.55, 0.00, 1.80),
        ('on the guard roof, aft      (-0.50, -0.40, 1.80)', -0.50, -0.40, 1.80),
        ('AS DECLARED                 (%.2f, %.2f, %.2f)' % (nav.x, nav.y, nav.z),
         nav.x, nav.y, nav.z),
    ]
    for label, cx, cy, cz in candidates:
        polys = occluders(solids, cz, kinds=('visual', 'collision'),
                          skip_links=('nav_lidar_link',))
        inside = [n for n, poly in polys
                  if _seg_hits_poly((cx, cy), (cx, cy), poly)]
        if inside:
            print('%-42s %s' % (label, 'mount is inside ' + inside[0]))
            continue
        flags = []
        for a in angs:
            pt = (cx + 20.0 * math.cos(a), cy + 20.0 * math.sin(a))
            flags.append(not blocked((cx, cy), pt, polys))
        shadow = 360.0 - measure(flags, step)
        print('%-42s %8.1f d %8.1f d' % (label, shadow, 360.0 - shadow))


def report_resolution(sensors):
    section('9. ANGULAR RESOLUTION AGAINST RANGE')
    print('Spacing between adjacent rays, in metres, at range:')
    print('')
    print('%-22s %9s %8s %8s %8s %8s' %
          ('sensor', 'res deg', '1 m', '2 m', '5 m', '8 m'))
    for s in sensors:
        res = s.aperture / (s.samples - 1)
        row = [2 * r * math.sin(res / 2) for r in (1.0, 2.0, 5.0, 8.0)]
        print('%-22s %9.4f %8.3f %8.3f %8.3f %8.3f' %
              (s.name, deg(res), row[0], row[1], row[2], row[3]))
    print('')
    print('Arena features (sim/worlds/forklift_arena.sdf) against the')
    print('navigation lidar plane, for the record:')
    print('  perimeter walls  top z = 0.60 m')
    print('  AisleCrate       top z = 0.90 m')
    print('  CrateNorth       top z = 1.00 m')
    print('  LoadBox          top z = 0.86 m')
    print('  PillarSouth      top z = 2.60 m')


def yaw_sweep(solids, sensors, step):
    """Sensitivity of the residual to the mount angle. NOT a proposal.

    The design block fixes the blind sector on the corner diagonal, so
    yaw 45 / 225 deg is the layout. This measures what a different mount
    angle would buy, so the choice is an informed one rather than an
    untested one.
    """
    front = [s for s in sensors if s.name == 'safety_scanner_front'][0]
    rear = [s for s in sensors if s.name == 'safety_scanner_rear'][0]
    n, angs = bearings(step)
    polys = occluders(solids, front.z, kinds=('visual', 'collision'))
    section('SAFETY SCANNER YAW SENSITIVITY (sensitivity study, not a change)')
    print('%8s %10s %10s %10s %10s' %
          ('delta', 'at 1.5 m', 'at 2.0 m', 'at 3.0 m', 'gap at 2 m'))
    base_f, base_r = front.yaw, rear.yaw
    for delta_deg in (-10.0, -7.5, -5.0, -2.5, 0.0, 2.5, 5.0, 7.5, 10.0):
        d = math.radians(delta_deg)
        front.yaw, rear.yaw = base_f + d, base_r + d
        row = []
        for radius in (1.5, 2.0, 3.0):
            ff = coverage_flags(front, polys, radius, angs)
            fr = coverage_flags(rear, polys, radius, angs)
            row.append(measure([a or b for a, b in zip(ff, fr)], step))
        ff = coverage_flags(front, polys, 2.0, angs)
        fr = coverage_flags(rear, polys, 2.0, angs)
        gaps = arcs_from_flags([a or b for a, b in zip(ff, fr)], step, False)
        print('%7.1fd %9.1fd %9.1fd %9.1fd   %s' %
              (delta_deg, row[0], row[1], row[2], fmt_arcs(gaps, limit=3)))
        if delta_deg in (0.0, 5.0):
            print_causes(causes((front, rear), polys, 2.0, angs, step,
                                [a or b for a, b in zip(ff, fr)]), step)
    front.yaw, rear.yaw = base_f, base_r


def nav_sweep(solids, step, z=1.80):
    section('NAV LIDAR POSITION SWEEP (design aid, not a result)')
    polys_v = occluders(solids, z, kinds=('visual',),
                        skip_links=('nav_lidar_link',))
    polys_p = occluders(solids, z, kinds=('visual', 'collision'),
                        skip_links=('nav_lidar_link',))
    n, angs = bearings(step)
    print('%8s %8s %12s %12s %10s %10s' %
          ('x', 'y', 'shadow vis', 'shadow phys', 'axis vis', 'axis phys'))
    for x in (-0.55, -0.25, 0.0, 0.25, 0.50, 0.55):
        for y in (0.0, -0.10, -0.20, -0.30, -0.35, -0.40):
            row = []
            for polys in (polys_v, polys_p):
                flags = []
                for a in angs:
                    pt = (x + 20.0 * math.cos(a), y + 20.0 * math.sin(a))
                    flags.append(not blocked((x, y), pt, polys))
                row.append((360.0 - measure(flags, step),
                            flags[int(round(180.0 / step)) % n]))
            print('%8.2f %8.2f %11.1fd %11.1fd %10s %10s' %
                  (x, y, row[0][0], row[1][0],
                   'clear' if row[0][1] else 'BLOCKED',
                   'clear' if row[1][1] else 'BLOCKED'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', default=_MODEL)
    ap.add_argument('--step', type=float, default=0.1,
                    help='bearing step in degrees (default 0.1)')
    ap.add_argument('--nav-sweep', action='store_true',
                    help='sweep navigation lidar positions and stop')
    ap.add_argument('--yaw-sweep', action='store_true',
                    help='sweep safety scanner mount angles and stop')
    args = ap.parse_args()

    solids, sensors = load_model(args.model)
    print('sensor_coverage.py on %s' % os.path.relpath(args.model, os.getcwd()))
    print('bearing step %.2f deg; every arc below is quantised to it.' % args.step)
    print('GEOMETRY ONLY. No simulator ran. Not a safety claim.')

    if args.nav_sweep:
        nav_sweep(solids, args.step)
        return
    if args.yaw_sweep:
        yaw_sweep(solids, sensors, args.step)
        return

    report_inventory(solids, sensors)
    report_safety(solids, sensors, args.step)
    report_hull(solids, sensors, args.step)
    report_states(solids, sensors, args.step)
    report_nav(solids, sensors, args.step)
    report_resolution(sensors)
    print('')


if __name__ == '__main__':
    main()
