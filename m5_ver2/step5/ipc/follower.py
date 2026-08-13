"""follower.py - pure pursuit, speed policy and the lidar sector. No ROS.

SIGNS, DERIVED ONCE. Model yaw 0 points the forks at world -x, so the
TRAVEL heading is model yaw + pi and forward traction is NEGATIVE
linear.x (hmi_node.knob_to_twist owns that convention). Positive
angular.z is a driver-right turn; a target with negative bearing error
alpha (clockwise of the travel heading, i.e. driver-right) therefore
needs POSITIVE steer, which is why the pursuit formula below carries a
leading minus. test_follower.py locks all three signs with worked
examples.

THE GUARD BANDS SIT OUTSIDE THE WARNING FIELD. GUARD_SLOW_M (3.0) >
case-1 WF (2.5), so on a straight aisle the lidar slows the truck to
GUARD_SLOW_MPS (= the PLC creep ceiling, 300 mm/s) BEFORE WF_Clear can
drop V_Limit under a truck still doing 0.7 m/s - the latched-stop trap
Step 3 measured (0.68 s after enable). The PLC keeps the last word;
this policy exists so it rarely has to say it.
"""
import math

# ----------------------------- CONFIG -----------------------------
LOOKAHEAD_M = 1.2
WHEELBASE_M = 1.2       # front-steer tricycle, drive wheel to rear axle
CRUISE_MPS = 0.7
CORNER_MPS = 0.3
APPROACH_MPS = 0.25
APPROACH_ZONE_M = 2.0   # final-leg distance where APPROACH_MPS applies
ARRIVE_M = 0.25
CORNER_STEER_RAD = 0.3
GUARD_SLOW_M = 3.0
GUARD_HOLD_M = 1.5
GUARD_SLOW_MPS = 0.3
GUARD_HALF_ANGLE_RAD = math.radians(35.0)
REVERSE_MPS = 0.25

# THE DEAD BAND IS WHY THE PHASE CANNOT CHATTER. Enter reverse only above
# 120 deg, leave it only below 75 deg: the 45 deg band between them means
# a target sitting near the perpendicular - which is exactly what a corner
# hands you - cannot flip the truck between backing out and driving on at
# tick rate. Inside the band the phase simply keeps whatever it was.
REVERSE_ENTER_RAD = 2.0944      # 120 deg
REVERSE_EXIT_RAD = 1.3090       # 75 deg

# THE VEHICLE'S OWN MAST, MEASURED OUT OF THE GUARD. The nav lidar
# clears the mast body on the exact-astern ray by 0.04 m (model.sdf,
# nav_lidar_link comment) - the neighbouring rays hit the two mast
# uprights, body-fixed, at the bearings below (probed live 2026-08-13:
# near upright -3..-6 deg @ 1.287-1.292 m, far -26..-29 deg @
# 1.447-1.483 m). Real nav scanners ship the same feature as "contour
# masking". Each window is (travel-offset lo/hi deg, ceiling m): a
# return inside the window at or under the ceiling is the truck, not
# the world. THE COST, STATED: a genuine obstacle inside a window and
# under its ceiling is invisible to the guard - a sliver ~8 deg wide
# under 1.6/1.7 m that the unmasked neighbouring beams cover for
# anything wider than ~25 cm at that range. The uprights also shadow
# everything behind them at these bearings, so the mask hides nothing
# a shadowed beam could have seen anyway.
SELF_MASK = (
    (-9.0, -1.0, 1.6),
    (-31.0, -23.0, 1.7),
)
# ------------------------------------------------------------------


def norm_ang(a):
    """Wrap to [-pi, pi)."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def travel_yaw(model_yaw):
    """The forks lead; travel heading is the model heading flipped."""
    return norm_ang(model_yaw + math.pi)


def _project(a, b, p):
    """(clamped parameter t, point) of p projected onto segment ab."""
    ax, ay = a
    vx, vy = b[0] - ax, b[1] - ay
    length2 = vx * vx + vy * vy
    if length2 == 0.0:
        return 0.0, a
    t = max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / length2))
    return t, (ax + t * vx, ay + t * vy)


def advance(path, xy):
    """(lookahead target, distance to path end) for the truck at xy.

    Stateless: the nearest point on the whole polyline is the progress
    estimate. The graph never doubles back on itself within LOOKAHEAD_M,
    so the nearest segment is the current one in practice.
    """
    segs = list(zip(path, path[1:]))
    lengths = [math.dist(a, b) for a, b in segs]
    best = (math.inf, 0, 0.0, path[0])
    for i, (a, b) in enumerate(segs):
        t, point = _project(a, b, xy)
        d = math.dist(point, xy)
        if d < best[0]:
            best = (d, i, t, point)
    _, i, t, point = best
    to_end = lengths[i] * (1.0 - t) + sum(lengths[i + 1:])
    walk, target = LOOKAHEAD_M, path[-1]
    cursor = point
    for j in range(i, len(segs)):
        a, b = segs[j]
        start = cursor if j == i else a
        remain = math.dist(start, b)
        if walk <= remain:
            if remain > 0.0:
                f = walk / remain
                target = (start[0] + f * (b[0] - start[0]),
                          start[1] + f * (b[1] - start[1]))
            break
        walk -= remain
    return target, to_end


def steer(pose, target_xy):
    """Pure-pursuit steer angle toward target. pose = (x, y, model_yaw).

    THE ALPHA CLAMP IS A U-TURN, NOT A TUNING. Raw pursuit uses
    sin(alpha), which VANISHES for a target dead astern (sin pi = 0):
    the truck would drive straight away from its goal at cruise speed.
    Clamping |alpha| to pi/2 keeps the demand at the formula's maximum
    until the target is back in the front half-plane - a committed
    minimum-radius arc, which the corner band in target_speed slows to
    CORNER_MPS automatically (|steer| ~1.1 > CORNER_STEER_RAD). Dead
    astern exactly (alpha = -pi, the wrap's edge) turns LEFT by
    convention so the choice is deterministic, not floating-point luck.
    """
    alpha = norm_ang(
        math.atan2(target_xy[1] - pose[1], target_xy[0] - pose[0])
        - travel_yaw(pose[2]))
    if abs(alpha) > math.pi / 2.0:
        alpha = math.copysign(
            math.pi / 2.0, alpha if alpha != -math.pi else 1.0)
    return -math.atan2(2.0 * WHEELBASE_M * math.sin(alpha), LOOKAHEAD_M)


def _self_return(offset_deg, r, self_mask):
    """True when this return is the truck's own mast: inside one of the
    contour windows AND no further than that window's ceiling."""
    return any(lo <= offset_deg <= hi and r <= ceiling
               for lo, hi, ceiling in self_mask)


def sector_min(ranges, angle_min, angle_inc, range_lo, range_hi,
               forward=True, self_mask=SELF_MASK):
    """Min valid range within +-35 deg of the direction of travel.

    THE SECTOR FOLLOWS THE TRUCK, NOT THE HULL. Driving forks-first the
    sector centres on scan angle pi (the fork end is the model's -x);
    backing out it centres on angle 0, the counterweight end we are
    actually moving toward. Same half-angle, same bands - only the
    centre moves, because a guard aimed at where the truck has been is
    not a guard.

    Invalid returns (inf, nan, outside [range_lo, range_hi]) are
    skipped: silence is not an obstacle HERE because the safety layer
    already treats silence as a demand; this guard only shapes speed.
    SELF_MASK returns are skipped too - they are the vehicle's own mast.
    Those windows are absolute body bearings (offsets from pi), so they
    are checked in both directions and simply never land in the reverse
    sector. Pass self_mask=() to see the raw scan."""
    centre = math.pi if forward else 0.0
    best = math.inf
    for i, r in enumerate(ranges):
        if not (range_lo <= r <= range_hi):     # False for nan and inf
            continue
        angle = angle_min + i * angle_inc
        if abs(norm_ang(angle - centre)) > GUARD_HALF_ANGLE_RAD:
            continue
        if _self_return(math.degrees(norm_ang(angle - math.pi)), r,
                        self_mask):
            continue
        best = min(best, r)
    return best


def reverse_phase(alpha, was_reversing):
    """Should the truck be backing up? alpha is the bearing error to the
    lookahead target, measured from the TRAVEL heading.

    A tricycle cannot rotate in place, so a target behind it is either a
    committed forward arc or a straight reverse. In a spur the arc is
    what put the back scanner 0.938 m off a rack (measured 2026-08-13):
    the first half of it drives the truck at the thing it just parked in
    front of. Backing straight out spends no floor at all, and reversing
    is the direction this vehicle guards best - the PLC's back scanner
    is primary there. See the ENTER/EXIT constants for the dead band."""
    if abs(alpha) > REVERSE_ENTER_RAD:
        return True
    if abs(alpha) < REVERSE_EXIT_RAD:
        return False
    return was_reversing


def target_speed(dist_to_end, steer_rad, guard_min_m):
    """The policy: slowest applicable band wins. Returns >= 0 m/s;
    the caller applies the forward sign (negative) and the PLC cap."""
    speed = CRUISE_MPS
    if dist_to_end <= APPROACH_ZONE_M:
        speed = min(speed, APPROACH_MPS)
    if abs(steer_rad) > CORNER_STEER_RAD:
        speed = min(speed, CORNER_MPS)
    if guard_min_m < GUARD_HOLD_M:
        return 0.0
    if guard_min_m < GUARD_SLOW_M:
        speed = min(speed, GUARD_SLOW_MPS)
    return speed


def arrived(xy, goal_xy):
    return math.dist(xy, goal_xy) <= ARRIVE_M
