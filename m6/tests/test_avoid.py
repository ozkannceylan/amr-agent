"""avoid - where the free floor is, from one scan. Pure geometry.

THE SCANS BELOW ARE BUILT, NOT CAPTURED, and every one of them is a
shape with a name: a clear room, a wall with a gap on one side, a gap
too narrow for the truck, a wall with no gap at all. A capture would
prove that this file agreed with one afternoon; a shape proves the rule.
"""
import math

import avoid
import follower

N = 360
ANGLE_MIN = -math.pi
ANGLE_INC = 2.0 * math.pi / N


def scan(default=8.0, blocked=(), value=1.0):
    """A 360-ray scan at `default`, with each (lo_deg, hi_deg) span in
    `blocked` set to `value`. Ray i is at ANGLE_MIN + i * ANGLE_INC."""
    out = [default] * N
    for lo, hi in blocked:
        for i in range(N):
            deg = math.degrees(follower.norm_ang(ANGLE_MIN + i * ANGLE_INC))
            if lo <= deg <= hi:
                out[i] = value
    return out


def bkts(ranges):
    return avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)


def test_the_histogram_covers_the_whole_circle_once():
    b = bkts(scan())
    assert len(b) == int(round(2.0 * math.pi / avoid.BUCKET_RAD))
    bearings = [x for x, _r in b]
    assert len(set(bearings)) == len(bearings), "two buckets, one bearing"
    for bearing, _r in b:
        assert -math.pi <= bearing <= math.pi


def test_a_clear_room_offers_the_heading_that_was_asked_for():
    free = avoid.free_heading(bkts(scan()), 0.0)
    assert free is not None
    assert abs(free) <= avoid.BUCKET_RAD, free


def test_a_wall_with_a_gap_on_one_side_offers_the_gap():
    # Everything from -60 to +25 degrees is a wall at 1.0 m. The only
    # free floor inside MAX_SWING is to the LEFT of it, and the answer
    # has to clear the wall edge by the vehicle's own half-window.
    #
    # THE BOUND IS BUCKET ARITHMETIC AND IS DERIVED, NOT GUESSED. The ray
    # at +25 deg lands in the bucket CENTRED at 22.58 deg (bucket k is
    # centred at -180 + 5.0019 * (k + 0.5)), and the window the vehicle
    # needs at FREE_M is atan2(0.67, 2.00) = 18.51 deg each side. So the
    # first centre that can be free is 22.58 + 18.51 = 41.09, and the
    # first bucket at or past it is 42.59.
    b = bkts(scan(blocked=((-60.0, 25.0),)))
    free = avoid.free_heading(b, 0.0)
    assert free is not None
    assert free > 0.0, "steered into the wall rather than round it"
    assert math.degrees(free) >= 41.0, math.degrees(free)
    assert abs(free) <= avoid.MAX_SWING_RAD


def test_a_gap_narrower_than_the_truck_is_not_offered():
    # A wall with a 10-degree slot in it. The window the vehicle needs
    # at FREE_M is about 37 degrees wide, so the slot is not floor.
    b = bkts(scan(blocked=((-90.0, -5.0), (5.0, 90.0))))
    assert avoid.free_heading(b, 0.0) is None


def test_a_wall_with_no_gap_at_all_answers_None():
    assert avoid.free_heading(bkts(scan(blocked=((-180.0, 180.0),))), 0.0) \
        is None


def test_free_floor_beyond_the_swing_bound_is_not_offered():
    # Blocked everywhere except behind: the free floor is real and it is
    # 180 degrees away, which is a re-route and not an avoidance.
    b = bkts(scan(blocked=((-100.0, 100.0),)))
    assert avoid.free_heading(b, 0.0) is None


def test_the_trucks_own_mast_is_not_a_wall():
    # SELF_MASK's near upright: -3 to -6 degrees off the fork end, under
    # 1.6 m. In the scan frame the fork end is pi, so those rays sit
    # near +-pi. Unmasked they would block the reverse heading.
    ranges = [8.0] * N
    for i in range(N):
        off = math.degrees(follower.norm_ang(
            ANGLE_MIN + i * ANGLE_INC - math.pi))
        if -6.0 <= off <= -3.0:
            ranges[i] = 1.29
    b = avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)
    masked = avoid.free_heading(b, math.pi)
    assert masked is not None, "the truck's own mast was read as a wall"
    assert abs(follower.norm_ang(masked - math.pi)) <= avoid.BUCKET_RAD, \
        "the mast pushed the answer off the heading that was asked for"

    # THE CONTROL, AND IT IS A SHOVE RATHER THAN A WALL. The mast is only
    # three degrees wide, so unmasked it does not close the room - it
    # pushes the answer off pi until the vehicle's own window clears the
    # two buckets it lands in (centred 172.6 and 177.6 deg), which puts
    # the answer at -162.5 deg: 17.5 deg of shove. A truck steering that
    # far off its reverse heading to miss its own upright is the defect
    # the mask prevents, and three buckets is the bound that catches it
    # without pinning a number the bucket width owns.
    raw = avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0,
                        self_mask=())
    unmasked = avoid.free_heading(raw, math.pi)
    assert unmasked is not None
    assert abs(follower.norm_ang(unmasked - math.pi)) > 3 * avoid.BUCKET_RAD, \
        "the staging put nothing where the mask is - this proves nothing"


def test_invalid_returns_are_dropped_not_counted_as_close():
    ranges = [float("inf")] * N
    ranges[0] = float("nan")
    ranges[1] = 0.01           # below range_lo
    ranges[2] = 99.0           # above range_hi
    b = avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)
    assert all(r == math.inf for _x, r in b)
    assert avoid.free_heading(b, 0.0) is not None


def test_the_same_scan_gives_the_same_answer():
    ranges = scan(blocked=((-60.0, 25.0),))
    first = avoid.free_heading(bkts(ranges), 0.0)
    for _ in range(5):
        assert avoid.free_heading(bkts(ranges), 0.0) == first
