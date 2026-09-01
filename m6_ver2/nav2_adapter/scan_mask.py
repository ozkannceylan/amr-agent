#!/usr/bin/env python3
"""scan_mask.py - the truck's own mast, taken out of the scan.

    python3 m6_ver2/nav2_adapter/scan_mask.py --selftest

NO ROS IN THIS FILE. It takes a list of ranges and the two angle numbers
off a `sensor_msgs/LaserScan` and returns a new list; the shell
republishes `/fN/gz/scan_nav` as `/fN/scan_nav_masked`, which is what
AMCL and both costmaps subscribe to.

WHY THIS EXISTS, AND IT IS NOT A TUNING. The ver2-lineage nav lidar sees
its own mast. Probed live 2026-08-13: the near upright at -3..-6 deg and
1.287-1.292 m, the far upright at -26..-29 deg and 1.447-1.483 m, both
BODY-FIXED - they travel with the vehicle and they are there on every
scan. m6/ipc/follower.py already skips them, but only for the SPEED
guard (`sector_min`, `SELF_MASK`), because that was the only consumer
m6 had. Nav2 has three more, and none of them knows:

  the AMCL likelihood field scores those beams against a map that has
  no mast in it, on every particle;
  the LOCAL costmap marks them, which puts OCCUPIED CELLS ON THE ROBOT,
  under its own footprint;
  SmacPlannerHybrid then refuses to plan from inside an occupied
  footprint - `ComputePathToPose` 205 START_OCCUPIED, which is the class
  m5v3 measured from inside a bay and the exact refusal this adapter
  would otherwise collect on every single plan.

Real nav scanners ship this feature and call it CONTOUR MASKING; the
windows below are the same idea with the vehicle's numbers in them.

THE COST, STATED, AND IT IS follower's OWN SENTENCE: a genuine obstacle
inside a window and under its ceiling is invisible - a sliver about
8 deg wide under 1.6/1.7 m that the unmasked neighbouring beams cover
for anything wider than roughly 25 cm at that range. The uprights also
SHADOW everything behind them at those bearings, so the mask hides
nothing a shadowed beam could have seen anyway.

A MASKED RETURN BECOMES `inf` AND NOT A LARGE NUMBER. `inf` is
LaserScan's own "no return", it fails every `range_min <= r <=
range_max` test that reads this scan afterwards, and it is what a
scanner with contour masking in its own firmware puts on the wire. A
large finite number would be an obstacle at that distance instead.

THE GEOMETRY IS follower's AND NOT THIS FILE'S. `SELF_MASK` is imported,
and the predicate that reads it is called rather than restated - the
question "is this return the truck's own mast" has one answer on this
vehicle, and a second spelling of it is a second hull.
"""
import argparse
import collections
import math
import sys

import _donors                                            # noqa: F401

import follower                                           # noqa: E402


class Nav2ScanError(ValueError):
    """A scan or a mask window this file will not guess at."""


#: THE VEHICLE'S OWN CONTOUR, imported. Each window is (offset lo deg,
#: offset hi deg, ceiling m) where the offset is the bearing measured
#: from the FORK ray - the same absolute body bearing follower.sector_min
#: checks - and a return inside a window at or under its ceiling is the
#: truck rather than the world.
SELF_MASK = follower.SELF_MASK

#: WHAT COMES OUT. `n_masked` is the observable seam: a filter whose
#: effect nobody can count is a filter nobody can tell has stopped
#: working, and this number belongs in the shell's per-child log.
Masked = collections.namedtuple("Masked", "ranges n_masked")


def _check_windows(self_mask):
    for window in self_mask:
        try:
            lo, hi, ceiling = (float(window[0]), float(window[1]),
                               float(window[2]))
        except (TypeError, ValueError, IndexError):
            raise Nav2ScanError(
                "{!r} is not a contour window: each one is (lo deg, hi "
                "deg, ceiling m)".format(window))
        if not (math.isfinite(lo) and math.isfinite(hi)
                and math.isfinite(ceiling)):
            raise Nav2ScanError(
                "the contour window {!r} carries a non-finite "
                "number".format(window))
        if lo > hi:
            raise Nav2ScanError(
                "the contour window {!r} has lo above hi, so it matches "
                "nothing at all - a mask that silently masks nothing is "
                "how the 205 refusals come back".format(window))
        if ceiling <= 0.0:
            raise Nav2ScanError(
                "the contour window {!r} has a ceiling of {}: a window "
                "with no depth is not a window".format(window, ceiling))


def mask_ranges(ranges, angle_min, angle_increment, self_mask=SELF_MASK,
                invalid=math.inf):
    """The scan with the vehicle's own mast returns removed.

    The input list is never mutated: the shell holds the raw message and
    a costmap that read a half-filtered scan would mark half a mast.

    INVALID RETURNS ARE LEFT EXACTLY AS THEY ARRIVED. `inf` and `nan`
    already mean "no return" to every reader downstream, and rewriting
    them here would be this file having an opinion about a beam it did
    not filter.
    """
    try:
        angle_min = float(angle_min)
        angle_increment = float(angle_increment)
    except (TypeError, ValueError):
        raise Nav2ScanError(
            "the scan's angle_min/angle_increment are {!r}/{!r}, which "
            "are not numbers".format(angle_min, angle_increment))
    if not (math.isfinite(angle_min) and math.isfinite(angle_increment)):
        raise Nav2ScanError(
            "the scan's angle_min/angle_increment are {!r}/{!r}: a "
            "bearing computed off one is not a bearing".format(
                angle_min, angle_increment))
    if angle_increment == 0.0:
        raise Nav2ScanError(
            "the scan's angle_increment is zero, so every ray in it has "
            "the same bearing and no contour window can be applied")
    _check_windows(self_mask)
    out = list(ranges)
    n_masked = 0
    for index, value in enumerate(out):
        try:
            r = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(r):
            continue
        angle = angle_min + index * angle_increment
        offset_deg = math.degrees(follower.norm_ang(angle - math.pi))
        # follower._self_return IS THE PREDICATE AND IT IS CALLED, NOT
        # COPIED. It is underscored because m6 had one consumer; the
        # alternative here is two spellings of the same hull, and the
        # day the mast is re-probed one of them gets fixed.
        if follower._self_return(offset_deg, r, self_mask):
            out[index] = invalid
            n_masked += 1
    return Masked(ranges=out, n_masked=n_masked)


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_nav2_adapter_scan_mask.py is the real suite - it
    cross-pins this filter against follower.sector_min, which is the
    reader that has been right about this mast since M6 - and this is
    the version an operator can run on the rig without pytest.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    angle_min, angle_inc, n = -math.pi, math.radians(1.0), 360

    def index_at(offset_deg):
        angle = follower.norm_ang(math.radians(offset_deg) + math.pi)
        return int(round((angle - angle_min) / angle_inc)) % n

    def scan(**hits):
        rays = [8.0] * n
        for offset, r in hits.items():
            rays[index_at(float(offset))] = r
        return rays

    check("a clear scan comes back unchanged, and as a COPY",
          mask_ranges(scan(), angle_min, angle_inc).n_masked == 0)

    for offset, r, which in ((-3.0, 1.287, "near upright, lo bearing"),
                             (-6.0, 1.292, "near upright, hi bearing"),
                             (-26.0, 1.447, "far upright, lo bearing"),
                             (-29.0, 1.483, "far upright, hi bearing")):
        out = mask_ranges(scan(**{str(offset): r}), angle_min, angle_inc)
        check("the {} ({:+.0f} deg at {:.3f} m) is the truck".format(
                  which, offset, r),
              out.n_masked == 1
              and out.ranges[index_at(offset)] == math.inf)

    check("a return past a window's ceiling is the WORLD",
          mask_ranges(scan(**{"-5.0": 3.400}),
                      angle_min, angle_inc).n_masked == 0)
    check("a close body BETWEEN the uprights survives",
          mask_ranges(scan(**{"-15.0": 1.300}),
                      angle_min, angle_inc).n_masked == 0)
    check("a close body dead astern of the mast survives",
          mask_ranges(scan(**{"0.0": 1.290}),
                      angle_min, angle_inc).n_masked == 0)

    rays = scan(**{"-5.0": 1.290, "-27.0": 1.470, "-15.0": 2.500})
    masked = mask_ranges(rays, angle_min, angle_inc).ranges
    with_mask = follower.sector_min(rays, angle_min, angle_inc, 0.05, 25.0)
    without = follower.sector_min(masked, angle_min, angle_inc, 0.05, 25.0,
                                  self_mask=())
    check("masking the SCAN gives what masking the READER gives "
          "({:.3f} m both ways)".format(with_mask),
          with_mask == without == 2.500)
    check("and the raw list was not touched",
          rays[index_at(-5.0)] == 1.290)

    check("an empty mask masks nothing",
          mask_ranges(rays, angle_min, angle_inc,
                      self_mask=()).n_masked == 0)
    check("an empty scan is an empty scan",
          mask_ranges([], angle_min, angle_inc).ranges == [])

    for bad, what in (
            (lambda: mask_ranges(scan(), angle_min, 0.0),
             "a zero angle_increment"),
            (lambda: mask_ranges(scan(), float("nan"), angle_inc),
             "a non-finite angle_min"),
            (lambda: mask_ranges(scan(), angle_min, angle_inc,
                                 self_mask=((1.0, -1.0, 1.6),)),
             "a window with lo above hi")):
        try:
            bad()
            check("{} is refused by name".format(what), False)
        except Nav2ScanError:
            check("{} is refused by name".format(what), True)

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the contour filter that keeps m6_ver2's nav lidar "
                    "from mapping its own mast. The node that uses it "
                    "republishes /fN/gz/scan_nav as "
                    "/fN/scan_nav_masked.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-simulator checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
