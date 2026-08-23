"""avoid.py - where the free floor is, from one scan. Pure, no ROS.

follower.sector_min ANSWERS "HOW CLOSE". THIS ONE ANSWERS "WHERE", and
until M6.7 nothing did. The nav lidar is 360 rays over the whole circle
and the autopilot reduced them to one number per direction of travel -
so a truck knew an obstacle was 1.47 m away and had no idea whether
there was three metres of clear floor beside it. Measured 2026-08-23,
that is exactly the state f2 and f3 stood in indefinitely.

WHAT THIS FILE IS NOT. It has no memory, no map, no clock and no
opinion about routes. One scan in, one heading out. It cannot know that
the gap it just offered is a dead end, and it is not asked to - going
round a body is an avoidance and finding another way to the station is
a re-route, which is the fleet's job and route.py's.

THE WINDOW IS THE VEHICLE, NOT A CONSTANT. A heading is free only if
everything the truck's WIDTH would sweep is free, so the half-width
tested at range r is atan2(HALF_ENVELOPE_M + WINDOW_MARGIN_M, r): about
18 degrees each side at 2.00 m, about 8 at 5.00. A fixed angular window
is too wide near and too narrow far, and too narrow far is how a truck
steers confidently into a gap it does not fit through.

THE MASK IS FOLLOWER'S, IMPORTED AND NOT RESTATED. follower.SELF_MASK is
the measured list of bearings where this vehicle sees its own mast
(probed live 2026-08-13). A second copy here would be a second thing to
keep true, and the first time they disagreed a truck would treat its own
upright as a wall - or worse, treat a wall as its own upright. That is
also why _self_return is called across the module boundary rather than
reimplemented: the rule and its data belong together, and there is only
one of each.
"""
import math

import follower

# 5 degrees. The nav lidar is 360 samples over 360 degrees, so a bucket
# is exactly five rays and no bucket is ever empty for want of rays.
BUCKET_RAD = 0.0873
HALF_ENVELOPE_M = 0.52      # the plan envelope is 1.04 m wide
WINDOW_MARGIN_M = 0.15
# A HEADING THAT CLEARS BY LESS THAN THE HOLD BAND IS NOT A HEADING.
# follower.GUARD_HOLD_M is 1.50: offer 1.60 m of free floor and the
# guard stops the truck on it anyway, which is worse than saying no -
# it spends the escalation and gets nowhere.
FREE_M = 2.00
# 60 degrees off the pursuit's own heading. Further than that is not an
# avoidance, it is a re-route.
MAX_SWING_RAD = 1.047


def buckets(ranges, angle_min, angle_inc, range_lo, range_hi,
            self_mask=follower.SELF_MASK):
    """((bearing, nearest), ...) over the whole circle, BUCKET_RAD wide.

    `nearest` is inf for a bucket with no valid return, which reads as
    "nothing there" - and that is the right direction here because this
    file only ever GRANTS floor. The safety layer is what treats silence
    as an obstacle, and it does that independently of this.
    """
    count = int(round(2.0 * math.pi / BUCKET_RAD))
    nearest = [math.inf] * count
    for index, value in enumerate(ranges):
        if not (range_lo <= value <= range_hi):   # False for nan and inf
            continue
        angle = follower.norm_ang(angle_min + index * angle_inc)
        # The mask's windows are offsets from the fork end, exactly as
        # follower.sector_min reads them.
        if follower._self_return(
                math.degrees(follower.norm_ang(angle - math.pi)),
                value, self_mask):
            continue
        slot = int((angle + math.pi) / BUCKET_RAD) % count
        if value < nearest[slot]:
            nearest[slot] = value
    return tuple(
        (follower.norm_ang(-math.pi + (slot + 0.5) * BUCKET_RAD),
         nearest[slot])
        for slot in range(count))


def _window_clear(bkts, centre, half_rad, reach_m):
    """True when every bucket within half_rad of centre is clear."""
    for bearing, nearest in bkts:
        if abs(follower.norm_ang(bearing - centre)) <= half_rad:
            if nearest < reach_m:
                return False
    return True


def free_heading(bkts, want_rad, reach_m=FREE_M):
    """The bearing NEAREST want_rad whose window is clear, or None.

    NEAREST AND NOT WIDEST. The widest gap in the room is often behind
    the truck; what is wanted is the smallest deviation from the route
    that gets past the thing in the way, because every degree of
    deviation is floor the pursuit then has to win back.

    Ties go to the lower bearing, so the answer is the same answer every
    time - a fleet log that reads differently on two identical scans is
    a log nobody can use.
    """
    half_rad = math.atan2(HALF_ENVELOPE_M + WINDOW_MARGIN_M, reach_m)
    best = None
    for bearing, _nearest in bkts:
        swing = abs(follower.norm_ang(bearing - want_rad))
        if swing > MAX_SWING_RAD:
            continue
        if not _window_clear(bkts, bearing, half_rad, reach_m):
            continue
        rank = (swing, bearing)
        if best is None or rank < best:
            best = rank
    return None if best is None else best[1]
