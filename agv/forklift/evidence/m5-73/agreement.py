#!/usr/bin/env python3
"""m5-73: front-scanner vs navigation-lidar agreement, m5-72 method.

Projects every in-range front return and nav return into base_link
through the mounts model.sdf declares, then reports the median nearest
neighbour distance in xy. Also verifies that the viz stream's scan
content (angles, window, ranges) matches the measurement stream's, and
that its world_pose equals the model pose composed with the link mount.
Usage: agreement.py <prefix>  (e.g. /tmp/m573/ev/poseA)
"""
import json
import math
import statistics
import sys

FRONT_MOUNT = (0.70, 0.45, 0.7853982)   # model.sdf safety_scanner_front_link
NAV_MOUNT = (0.55, -0.40, 0.0)          # model.sdf nav_lidar_link


def load(path):
    with open(path) as f:
        return json.load(f)


def returns_in_base(msg, mount):
    mx, my, myaw = mount
    a0 = msg["angleMin"]
    step = msg["angleStep"]
    rmin, rmax = msg["rangeMin"], msg["rangeMax"]
    pts = []
    for i, r in enumerate(msg["ranges"]):
        try:
            r = float(r)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(r) or r <= rmin or r >= rmax * 0.999:
            continue
        a = a0 + i * step + myaw
        pts.append((mx + r * math.cos(a), my + r * math.sin(a)))
    return pts


def main():
    prefix = sys.argv[1]
    front = load(prefix + "-safety_scanner_front_measurement.json")
    nav = load(prefix + "-scan_nav.json")
    fp = returns_in_base(front, FRONT_MOUNT)
    np_ = returns_in_base(nav, NAV_MOUNT)
    dists = []
    for x, y in fp:
        best = min((x - nx) ** 2 + (y - ny) ** 2 for nx, ny in np_)
        dists.append(math.sqrt(best))
    dists.sort()
    n = len(dists)
    med = statistics.median(dists)
    q90 = dists[int(0.9 * (n - 1))]
    print("%s: front in-range n=%d, nav in-range n=%d" % (prefix, n, len(np_)))
    print("  agreement front->nav: median %.3f m  q90 %.3f m  max %.3f m"
          % (med, q90, dists[-1]))

    # viz stream content equality (metadata; ranges are checked live in
    # the paired-stamp test, since two one-shot captures are two scans)
    viz = load(prefix + "-viz_safety_scanner_front.json")
    for k in ("angleMin", "angleMax", "angleStep", "rangeMin", "rangeMax",
              "count", "frame"):
        a, b = front.get(k), viz.get(k)
        tag = "OK" if a == b else "MISMATCH"
        print("  viz metadata %-9s %s (%r vs %r)" % (k, tag, a, b))

    # world_pose expectation from the model pose file beside the captures
    with open(prefix + "-modelpose.txt") as f:
        lines = [l.strip() for l in f if l.strip()]
    xyz = lines[-2].strip("[] ").split()
    rpy = lines[-1].strip("[] ").split()
    mx0, my0, myaw0 = float(xyz[0]), float(xyz[1]), float(rpy[2])
    ex = mx0 + FRONT_MOUNT[0] * math.cos(myaw0) - FRONT_MOUNT[1] * math.sin(myaw0)
    ey = my0 + FRONT_MOUNT[0] * math.sin(myaw0) + FRONT_MOUNT[1] * math.cos(myaw0)
    eyaw = myaw0 + FRONT_MOUNT[2]
    wp = viz["worldPose"]
    px = wp["position"].get("x", 0.0)
    py = wp["position"].get("y", 0.0)
    qz = wp["orientation"].get("z", 0.0)
    qw = wp["orientation"].get("w", 1.0)
    pyaw = 2.0 * math.atan2(qz, qw)
    print("  viz world_pose (%.4f, %.4f, yaw %.4f) vs expected "
          "(%.4f, %.4f, yaw %.4f)  err %.4f m / %.5f rad"
          % (px, py, pyaw, ex, ey, eyaw,
             math.hypot(px - ex, py - ey), abs(pyaw - eyaw)))

    # and the measurement stream's own world_pose must still be identity
    mwp = front.get("worldPose", {})
    mp = mwp.get("position", {})
    ident = (abs(mp.get("x", 0.0)) < 1e-9 and abs(mp.get("y", 0.0)) < 1e-9
             and abs(mwp.get("orientation", {}).get("z", 0.0)) < 1e-9)
    print("  measurement stream world_pose still identity:", ident)


if __name__ == "__main__":
    main()
