#!/usr/bin/env python3
"""cmd_vel_tricycle_core.py - a body twist becomes a steer angle and a
tread speed, as arithmetic.

    python3 m5_ver3/nodes/cmd_vel_tricycle_core.py --selftest

NO ROS AND NO GAZEBO IN THIS FILE, which is what lets this track's pytest
run on the Windows python where there is no rclpy at all.
nodes/cmd_vel_tricycle.py is the shell that subscribes, limits and
publishes; everything that could be WRONG about the conversion is here,
where a test can reach it. It is nodes/wheel_odom_core.py against
nodes/wheel_odometry.py, one layer down the same split.

WHAT IT IS. THE INVERSE OF THE KINEMATICS wheel_odom_core INTEGRATES, and
that sentence is the whole specification. That file takes a steer angle
and a tread speed and reports a base_link twist; this one takes a
base_link twist and reports the steer angle and tread speed that would
produce it. Written any other way the two halves of this track would be
two opinions about one vehicle, and the residual would look like slip.

    /cmd_vel  ->  nav2_velocity_smoother  ->  /cmd_vel_smoothed
              ->  THIS  ->  steer angle [rad]  +  wheel rate [rad/s]
                            at config.yaml's topics.steer_cmd and
                            topics.traction_cmd, which are model.sdf's
                            own motor terminals.

WHAT IT IS NOT. It is not a controller: it measures nothing and corrects
nothing, so the same twist twice gives the same pair twice. It is not a
safety function: nothing here inhibits motion, latches a fault or
performs a stop, and a refused command is a command not issued rather
than a machine state. It is not real time: the physical loop closes in
model.sdf's joint controllers, so a late call here costs smoothness.

============================== THE GEOMETRY ==============================

config.yaml's vehicle: block, which took it from model.sdf's link poses:
ONE steered, driven wheel LEADING at x = +0.55; TWO passive wheels
TRAILING on an axle at x = -0.50. So

    L = wheelbase                    = 0.55 - (-0.50) = 1.05 m
    d = base_link ahead of rear axle = 0.50 m
    r = drive wheel radius           = 0.12 m

THE ONE FACT THAT MAKES THE ALGEBRA A BICYCLE RELATION, and it is not an
approximation. The rear axle midpoint R is the only point of a tricycle
whose velocity is purely longitudinal, because the two passive wheels
cannot slide sideways. base_link B stands d FORWARD of R, purely along
+x, so for a rigid body

    v_B = v_R + omega x (B - R) = (v_R, 0, 0) + (0, d*omega, 0)

and the x components of v_B and v_R are IDENTICAL. Only a lateral term
appears, so the offset drops out of THIS conversion entirely - while
remaining the reason wheel_odom_core integrates the rear axle and places
base_link on the result afterwards. The lateral term is real and it is
that file's to report; it is not an input here and there is nowhere for
it to enter.

With delta the steer angle and v_w the driven wheel's TREAD speed, the
kinematics wheel_odom_core integrates are

    v = v_w * cos(delta)                                             (1)
    w = v_w * sin(delta) / L                                         (2)

and dividing (2) by (1) gives the bicycle relation w = v tan(delta) / L.
Solved for the two actuators:

    delta = atan2( L * w * sign(v), |v| )                            (3)
    v_w   = v / cos(delta)                                           (4)

(3) is written as an atan2 so that it returns a value in (-pi/2, +pi/2)
with the right sign and NEVER divides by v. It is correct in reverse
without a second case: substituting (2)/(1) into it gives
atan(tan(delta)) = delta for v of either sign.

THE TERMINAL CARRIES v_w AND NOT v, and that is a contract this file did
not invent. model.sdf's COMMAND TOPICS note says traction_cmd is a WHEEL
RATE in rad/s; tools/drive_route.py publishes `tread / wheel_radius` onto
it; wheel_odom_core reads the same shaft back. Feeding it v instead would
under-drive every turn by cos(delta) - 3.6 % at 15 deg and 68 % at this
vehicle's own commanded lock.

============================== THE SIGNS ==============================

THEY ARE THE REPO'S AND NOT THIS FILE'S, and every one of them is stated
in nodes/wheel_odom_core.py's header, m6/ipc/follower.py's and
m6/tests/test_follower.py's:

  MODEL YAW 0 POINTS THE FORKS AT WORLD -x, so the TRAVEL heading is
  model yaw + pi. FORWARD TRAVEL - forks first - is therefore a NEGATIVE
  `linear.x` in base_link, a NEGATIVE tread speed and a NEGATIVE wheel
  rate at the terminal. There is no flip anywhere in this file and there
  must not be one: what wheel_odom_core PUBLISHES for forward travel is
  what a controller reading that estimate will COMMAND for it, and a
  conversion that quietly re-defined forward would be correct on the
  bench and backwards on the floor.
    SO Nav2 IS NOT LIED TO EITHER. A planner working in base_link sees a
    vehicle whose +x is counterweight-first; forks-first travel is its
    REVERSE, which is a thing Reeds-Shepp planning and an Ackermann
    controller already have a representation for. The convention is
    carried by the transform tree and the odometry, once, and never by a
    sign hidden in a converter.

  POSITIVE STEER IS DRIVER-RIGHT. In base_link - the frame a
  geometry_msgs/Twist is expressed in by that message's own contract - a
  driver-right turn is a DECREASING yaw and therefore a NEGATIVE
  `angular.z`. Check it against (2): v_w < 0 (forward) and delta > 0
  (driver-right) give w < 0. wheel_odom_core's selftest locks the same
  fact from the other side ("positive steer forward is a driver-right
  turn, model yaw down, world +y").

  AND angular.z HERE IS A YAW RATE, rad/s - not the STEER ANGLE that
  m6/ipc/cmd_gate.py's field contract puts in the same field on the
  fleet's command path. Those two are not the same quantity, and a
  residual between them looks nearly right at one speed and is wrong at
  every other. This file is the conversion that stands between them.

===================== THE THREE PLACES GEOMETRY STOPS =====================

1. THE CURVATURE CEILING, AND IT IS MEASURED RATHER THAN MECHANICAL.
   model.sdf's steer stop is +-1.31 rad, which is a turning radius of
   L/tan(1.31) = 0.2802 m. This plant has never been driven there. The
   hardest steer it HAS been driven at is 1.25 rad - config.yaml's
   `square` profile and the two-row delivered table above it - so the
   ceiling this file enforces is

       kappa_max = tan(1.25) / 1.05 = 2.8662568 1/m,  R = 0.3488871 m

   and the mechanical stop stands behind it as a backstop that cannot be
   reached from a twist. Past 1.25 rad there is no measurement, only
   geometry, and the plant's own answer at that angle is already 0.908 of
   what the geometry promises with an 11.5 % spread across headings
   (EVIDENCE_LATERAL_TUNE.md; config.yaml drive_route.profiles.square).
     WHAT THE PLANT DELIVERS AT THE CEILING is therefore NOT kappa_max:
     measured, 2.6038 1/m (R = 0.3841 m) at the four-corner mean and
     2.4071 1/m (R = 0.4154 m) at the worst single corner. That is the
     number a planner's minimum_turning_radius has to respect and it is
     handed over in EVIDENCE_NAV_V3.md rather than applied here - this
     file converts, it does not plan.

2. THE TRACTION LIMIT. v_w = v / cos(delta) grows without bound as the
   wheel goes over, so it can exceed the speed the plant has been driven
   at even when v does not. CLAMPING v_w IS CURVATURE PRESERVING, and
   that is worth stating because it is not obvious: from (1) and (2),
   scaling v_w with delta HELD scales v and w together, so the arc is
   unchanged and the vehicle simply drives it more slowly.

3. THE STANDSTILL. Below the creep deadband the ratio w/v is not a
   curvature anybody meant, and AT a standstill with a yaw rate demanded
   there is no (delta, v_w) at all: one steered wheel standing a
   wheelbase ahead of the rear axle cannot turn the body without
   travelling. That one is REFUSED - see below.

=================== CLAMP OR REFUSE, AND WHY IT IS CLAMP ===================

config.yaml's `vehicle.steer_limit_rad` comment already draws this line
for this track, and it draws it by WHICH THING IS BEING CORRECTED:
tools/drive_route.py REFUSES a steer angle outside the stop because it is
reading a table somebody wrote down, and a table that asks for an
impossible angle is a table to correct;
agv/forklift/scripts/forklift_io.py CLAMPS because it is taking commands
from a live stack in real time and has to make one of them legal.

THIS NODE IS ON THE LIVE SIDE OF THAT LINE, and three things follow:

  A REFUSAL HERE IS NOT A STOP - IT IS THE PREVIOUS ORDER STANDING.
  model.sdf's JointController holds its last command FOR EVER (measured
  in m6: a truck ran 14.8 m on one after its publisher died). So a node
  that answered an over-tight arc by publishing nothing would leave the
  vehicle driving the OLD arc, which is strictly worse than the closest
  legal one. A table can be corrected before anything moves; a command
  cannot.

  THE COMMAND IS RE-ISSUED TWENTY TIMES A SECOND, WITH FEEDBACK. A
  clamped command that is 5 % off is corrected on the next cycle by the
  controller that measured the result. A table is driven once.

  SO THE CLAMP MUST BE VISIBLE, BECAUSE IT IS NOT CURVATURE PRESERVING.
  The vehicle turns less sharply than asked, which is a real deviation:
  every clamp is COUNTED, published on the node's own status topic and
  logged throttled. A clamp that nobody can see is the failure this whole
  argument is trying to avoid, moved one layer down.

WHAT IS STILL REFUSED, AND IT IS THE CASE WHERE NO COMMAND EXISTS: a
non-finite command, and a yaw rate demanded at a standstill. Neither has
a closest legal value to fall back to - "the nearest arc to an in-place
rotation" is not a thing - so those are counted as refusals, the traction
goes to zero and the steer axis is HELD.

  HELD, AND NOT RE-CENTRED. Re-centring is itself a motion command the
  caller did not issue, and it is the wrong pre-position for the cusp
  that usually follows a refused rotation.

  AND A REFUSAL IS COUNTED ONLY AT A STANDSTILL, which is narrower than
  the creep deadband. The crib counted the whole band and the counter
  became useless: its first measured run reported 27 "rotation in place"
  refusals for a goal that was reached, every one of them the tail of a
  deceleration through the band. The counter exists to prove that
  nothing upstream is commanding a differential base, and nav2's Spin
  sends v = 0 exactly.

========================= THE SPEED LIMIT =========================

nav2_msgs/SpeedLimit, on nav2's own topic name. It scales the WHOLE
twist - v and w together - so it is curvature preserving for limit 2's
reason: the vehicle drives the same arc more slowly. `speed_limit: 0.0`
is NO LIMIT and not a stop; the message's own comment says so, and a node
that read it as a stop would brake every time a limit was lifted.

  IT IS A DEMONSTRATED INTERFACE AND NOT A SAFETY CLAIM. The PLC that
  will publish it arrives in a later integration phase; what is wired
  here is the hook and a test publisher for it. Nothing on this path
  inhibits motion or latches anything, and the disclaimer this track
  keeps verbatim belongs beside it: the collision monitor "does not
  provide hard real-time safety certifications" and does not replace a
  safety-rated PLC. It complements the F-PLC; it is not the F-PLC.
"""
import argparse
import collections
import math
import sys

#: One conversion, decided. A plain record so the shell can publish it
#: and a test can read it, and neither has to reach into the arithmetic.
#:
#: `steer_rad` IS None WHEN THE ANSWER IS "HOLD". That is not an absence
#: of an answer: it is the answer, and it is a different one from zero.
#: Zero would centre the wheel, which is a motion command nobody issued.
#:
#: `v_mps` and `w_radps` are the twist the pair below actually DELIVERS,
#: after every clamp - so a caller can log what was asked for beside what
#: is going to happen without recomputing (1) and (2) itself.
Conversion = collections.namedtuple(
    "Conversion",
    "steer_rad wheel_mps v_mps w_radps "
    "curvature_clamped steer_clamped traction_clamped refused reason")


def curvature_max(steer_command_limit_rad, wheelbase_m):
    """The tightest curvature a steer-angle ceiling permits, 1/m.

    ONE PLACE, because config.yaml states the ANGLE (which is what was
    measured) and three consumers want the CURVATURE: this file's clamp,
    smoother.yaml's angular limits and the evidence file's handover row.
    A second spelling of tan(1.25)/1.05 is a second opinion about the
    plant's tightest arc.
    """
    wheelbase_m = float(wheelbase_m)
    if wheelbase_m <= 0.0:
        raise ValueError(
            "wheelbase_m must be positive, got {!r} - check config.yaml "
            "vehicle.wheelbase_m".format(wheelbase_m))
    return math.tan(float(steer_command_limit_rad)) / wheelbase_m


def wheel_rate_radps(tread_mps, wheel_radius_m):
    """Tread speed [m/s] as the terminal's own wheel rate [rad/s].

    THE TRUE RADIUS, because this is a command to the PLANT. The radius
    the vehicle BELIEVES is wheel_odom_core's and is deliberately a
    different number; an actuator driven through the believed radius
    would make the estimator's modelled scale error disappear, which is
    the one thing on this track that must not happen.
    """
    wheel_radius_m = float(wheel_radius_m)
    if wheel_radius_m <= 0.0:
        raise ValueError(
            "wheel_radius_m must be positive, got {!r} - check config.yaml "
            "vehicle.wheel_radius_m".format(wheel_radius_m))
    return float(tread_mps) / wheel_radius_m


def speed_limit_mps(percentage, speed_limit, speed_max_mps):
    """A nav2_msgs/SpeedLimit's two fields as one ceiling, or None.

    None means NO LIMIT, and there are three ways to mean it: the
    message's own `0.0` (its comment: "When no-limit it is set to 0.0"),
    a negative value, and a value that is not a number. All three are the
    same instruction - stop limiting - and none of them is a stop.

    A PERCENTAGE IS A PERCENTAGE OF THE CONFIGURED MAXIMUM and cannot
    raise it: 300 % of a plant that has only ever been driven at 0.7 m/s
    is still 0.7 m/s, because the ceiling above this one is a
    measurement and not a preference.
    """
    try:
        value = float(speed_limit)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0.0:
        return None
    ceiling = abs(float(speed_max_mps))
    if percentage:
        return min(ceiling, ceiling * value / 100.0)
    return min(ceiling, value)


def apply_speed_limit(v, w, limit_mps):
    """Scale a twist under a speed ceiling, curvature preserving.

    v AND w TOGETHER, never v alone. Scaling one component and not the
    other silently changes the arc - it is the same corruption
    `scale_velocities: false` produces in the smoother, and this node
    reads the RATIO as a steer angle.
    """
    if limit_mps is None or abs(v) <= limit_mps:
        return v, w
    if v == 0.0:
        return v, w
    scale = limit_mps / abs(v)
    return v * scale, w * scale


def tricycle_to_twist(steer_rad, wheel_mps, wheelbase_m):
    """The FORWARD model - (1) and (2) - read the other way.

    v = v_w cos(delta),  w = v_w sin(delta) / L.

    It exists so the conversion can be checked by ROUND TRIP rather than
    by inspection. It is deliberately the same three lines
    wheel_odom_core.update() integrates, stated here so that --selftest
    needs no import; tests/test_cmd_vel_tricycle_core.py does the round
    trip through THAT FILE instead, which is the check that matters -
    a round trip through one author's algebra proves only that the
    author was consistent.
    """
    return (wheel_mps * math.cos(steer_rad),
            wheel_mps * math.sin(steer_rad) / float(wheelbase_m))


def twist_to_tricycle(v, w, wheelbase_m, steer_limit_rad, curvature_max_1pm,
                      traction_max_mps, creep_speed_mps, zero_speed_mps,
                      yawrate_refusal_radps):
    """A base_link twist as (steer angle, tread speed). See the header.

    Pure: no node, no clock, no state. Every limit is an argument, so
    what this function decides is a function of config.yaml and of
    nothing in the room.
    """
    try:
        v = float(v)
        w = float(w)
    except (TypeError, ValueError):
        v = w = float("nan")
    if not (math.isfinite(v) and math.isfinite(w)):
        return Conversion(
            steer_rad=None, wheel_mps=0.0, v_mps=0.0, w_radps=0.0,
            curvature_clamped=False, steer_clamped=False,
            traction_clamped=False, refused=True,
            reason="the command is not finite (v={!r}, w={!r})".format(v, w))

    # ---- the standstill, which is the one thing with no legal answer ----
    if abs(v) < abs(creep_speed_mps):
        standstill = abs(v) <= abs(zero_speed_mps)
        turning = abs(w) > abs(yawrate_refusal_radps)
        if standstill and turning:
            return Conversion(
                steer_rad=None, wheel_mps=0.0, v_mps=0.0, w_radps=0.0,
                curvature_clamped=False, steer_clamped=False,
                traction_clamped=False, refused=True,
                reason=("a yaw rate of {:+.4f} rad/s was demanded at a "
                        "STANDSTILL (v={:+.5f} m/s): one steered wheel a "
                        "wheelbase ahead of the rear axle cannot turn the "
                        "body without travelling, so there is no (steer, "
                        "tread) pair that produces it".format(w, v)))
        return Conversion(
            steer_rad=None, wheel_mps=0.0, v_mps=0.0, w_radps=0.0,
            curvature_clamped=False, steer_clamped=False,
            traction_clamped=False, refused=False,
            reason=("|v| = {:.5f} m/s is under the {:.5f} m/s creep "
                    "deadband: the requested curvature is not a number the "
                    "controller meant. Traction zero, steer HELD."
                    .format(abs(v), abs(creep_speed_mps))))

    # ---- the curvature ceiling, and it costs the ARC and not the SPEED --
    curvature_clamped = False
    kappa = w / v
    if abs(kappa) > abs(curvature_max_1pm):
        w = math.copysign(abs(curvature_max_1pm) * abs(v), w)
        curvature_clamped = True

    # ---- (3), written so nothing divides by v ----
    steer = math.atan2(wheelbase_m * w * (1.0 if v >= 0.0 else -1.0), abs(v))

    # ---- and the mechanical stop, which stands BEHIND the ceiling ----
    steer_clamped = False
    if steer > abs(steer_limit_rad):
        steer, steer_clamped = abs(steer_limit_rad), True
    elif steer < -abs(steer_limit_rad):
        steer, steer_clamped = -abs(steer_limit_rad), True

    # ---- (4). cos(delta) cannot be zero: both ceilings are inside pi/2
    # by construction and both have already been applied.
    wheel = v / math.cos(steer)

    traction_clamped = False
    if abs(wheel) > abs(traction_max_mps):
        wheel = math.copysign(abs(traction_max_mps), wheel)
        traction_clamped = True

    delivered_v, delivered_w = tricycle_to_twist(steer, wheel, wheelbase_m)
    reason = ""
    if curvature_clamped:
        reason = ("curvature clamped from {:+.4f} to {:+.4f} 1/m "
                  "(R {:.4f} m) - the SPEED is kept and the ARC is not"
                  .format(kappa, delivered_w / delivered_v,
                          abs(1.0 / curvature_max_1pm)))
    elif traction_clamped:
        reason = ("tread speed clamped to {:+.4f} m/s - the arc is "
                  "unchanged and the vehicle drives it slower"
                  .format(wheel))
    return Conversion(
        steer_rad=steer, wheel_mps=wheel,
        v_mps=delivered_v, w_radps=delivered_w,
        curvature_clamped=curvature_clamped, steer_clamped=steer_clamped,
        traction_clamped=traction_clamped, refused=False, reason=reason)


class CommandLimiter(object):
    """What the two terminals are allowed to do between one tick and the
    next: a step command leaves this node as a RAMP.

    WHY THE NODE RAMPS SOMETHING THE PLANT WILL RAMP ANYWAY. model.sdf's
    steer_joint carries <velocity>2.0</velocity>, so the axis cannot slew
    faster than that whatever is commanded - and config.yaml's `square`
    profile records what the difference costs when nobody accounts for
    it: every corner loses the yaw of its own first fraction of a second,
    measured at 0.057250 rad per corner, and the corner time had to be
    re-derived around it. A command that is already a ramp is a command
    whose delivered arc is a function of the ramp this file wrote, and
    not of a slew somebody has to measure afterwards.
      AND THE TRACTION HAS NO RAMP AT ALL. model.sdf's traction terminal
      is a raw velocity command - the plugin's own comment says "Raw
      velocity, no ramp" - so a step to cruise puts the largest slip of a
      run into its first tenth of a second. config.yaml's `straight`
      profile carries the ramp in its TABLE for exactly that reason;
      this is the same ramp, for a command nobody tabulated.

    THE STATE IS WHAT WAS LAST PUBLISHED, so the ramp continues across
    ticks where no command arrived - which is what makes a lost command
    stream a controlled stop rather than a standing order.

    steer_rad MAY BE SEEDED, and the default is None rather than 0.0.
    Until something has been commanded the axis is wherever the simulator
    left it, and publishing a zero would be this node moving the wheel on
    startup.
    """

    def __init__(self, steer_rate_limit_radps, traction_accel_mps2,
                 steer_rad=None, wheel_mps=0.0):
        self.steer_rate_limit_radps = abs(float(steer_rate_limit_radps))
        self.traction_accel_mps2 = abs(float(traction_accel_mps2))
        if self.steer_rate_limit_radps <= 0.0:
            raise ValueError(
                "steer_rate_limit_radps must be positive - check "
                "config.yaml vehicle.steer_rate_limit_radps")
        if self.traction_accel_mps2 <= 0.0:
            raise ValueError(
                "traction_accel_mps2 must be positive - check config.yaml "
                "navcmd.accel_mps2")
        self.steer_rad = None if steer_rad is None else float(steer_rad)
        self.wheel_mps = float(wheel_mps)

    # THERE IS NO "WORST RATE I ASKED FOR" COUNTER HERE, AND THERE WAS.
    # It was a self-report - the limiter recording, against its own
    # previous value, that it had obeyed its own ceiling - and NOTHING
    # CALLED IT, so the attribute stayed at 0.0 for the life of every
    # node and the one unit assertion that read it was true whatever the
    # ramp did. Two reasons it is gone rather than wired up:
    #   A CLAIM CHECKED BY THE THING MAKING IT IS NOT A CHECK. `step()`
    #   computes the new value THROUGH _towards(), so a counter fed from
    #   the same arithmetic can only ever agree with it; the failure it
    #   was supposed to catch - a ramp that moved further than the limit
    #   - is unreachable from inside this class.
    #   AND THE HONEST INSTRUMENT ALREADY EXISTS, one layer out.
    #   tools/drive_twist.py's max_step() differences the TERMINAL's own
    #   recorded stream, which is what actually reached the wire rather
    #   than what this object believed it published, and
    #   EVIDENCE_NAV_V3.md 5 is the table. The unit suite now asserts the
    #   per-tick ceiling directly, by driving a step and checking every
    #   delta - see tests/test_cmd_vel_tricycle_core.py.

    def step(self, dt_s, steer_target, wheel_target):
        """One tick. `steer_target` None means HOLD - see the header.

        A ZERO OR BACKWARDS INTERVAL MOVES NOTHING, which is
        wheel_odom_core.update()'s rule and it is the same rule: the
        first tick of a run is not an interval, and neither is a repeated
        or a rewound clock. Under sim time both happen - a paused world
        stamps the same instant twice.
        """
        dt_s = float(dt_s)
        if dt_s > 0.0:
            if steer_target is not None:
                if self.steer_rad is None:
                    # NOTHING HAS BEEN COMMANDED YET, so there is no held
                    # angle to ramp from. Starting the ramp at the target
                    # would be a step; starting it at zero would assume
                    # the axis is centred, which nothing has said. The
                    # shell seeds this from the plant's own joint state
                    # where it can, and falls back to the target here.
                    self.steer_rad = float(steer_target)
                else:
                    self.steer_rad = _towards(
                        self.steer_rad, float(steer_target),
                        self.steer_rate_limit_radps * dt_s)
            self.wheel_mps = _towards(
                self.wheel_mps, float(wheel_target),
                self.traction_accel_mps2 * dt_s)
        return self.steer_rad, self.wheel_mps


def _towards(current, target, step):
    """`current` moved at most `step` towards `target`, never past it."""
    delta = target - current
    if abs(delta) <= step:
        return target
    return current + math.copysign(step, delta)


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_cmd_vel_tricycle_core.py is the real suite - it rounds the
    trip through wheel_odom_core itself, which this cannot do without an
    import - and this is the version an operator can run on the rig, in
    the shell they are already in, without pytest. It covers the three
    things a command path gets wrong: the signs, the limits and the ramp.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    L = 1.05
    kappa = curvature_max(1.25, L)

    def conv(v, w, **over):
        kwargs = dict(wheelbase_m=L, steer_limit_rad=1.31,
                      curvature_max_1pm=kappa, traction_max_mps=0.700,
                      creep_speed_mps=0.005, zero_speed_mps=0.001,
                      yawrate_refusal_radps=0.01)
        kwargs.update(over)
        return twist_to_tricycle(v, w, **kwargs)

    check("the commanded curvature ceiling is 2.8662568 1/m "
          "(R 0.3488871 m)", abs(kappa - 2.8662568322503152) < 1e-12)

    out = conv(-0.700, 0.0)
    check("forward is a NEGATIVE linear.x, a NEGATIVE tread and a "
          "centred wheel",
          out.steer_rad == 0.0 and abs(out.wheel_mps + 0.700) < 1e-15)
    check("and it reaches the terminal as a negative wheel rate",
          wheel_rate_radps(out.wheel_mps, 0.12) < 0.0)

    out = conv(0.700, 0.0)
    check("astern is a POSITIVE tread on the same centred wheel",
          abs(out.wheel_mps - 0.700) < 1e-15)

    out = conv(-0.300, -0.200)
    check("forward + driver-right (negative angular.z) is a POSITIVE "
          "steer angle", out.steer_rad > 0.0 and out.wheel_mps < 0.0)
    check("forward + driver-left is a NEGATIVE steer angle",
          conv(-0.300, 0.200).steer_rad < 0.0)

    # THE UNLIMITED CASES ONLY, and the ceilings are checked on their
    # own below. Eight of these thirty meet the traction ceiling (any
    # curvature at cruise asks the wheel for v/cos delta) and four meet
    # the curvature one, which is what those ceilings ARE rather than a
    # gap in this check.
    worst = 0.0
    for v in (-0.700, -0.300, -0.050, 0.050, 0.300, 0.700):
        for w in (-0.25, -0.10, 0.0, 0.10, 0.25):
            out = conv(v, w)
            back = tricycle_to_twist(out.steer_rad, out.wheel_mps, L)
            worst = max(worst, abs(back[0] - out.v_mps),
                        abs(back[1] - out.w_radps))
            if not (out.curvature_clamped or out.steer_clamped
                    or out.traction_clamped):
                worst = max(worst, abs(back[0] - v), abs(back[1] - w))
    check("the round trip through the forward model is exact "
          "({:.2e})".format(worst), worst < 1e-12)

    out = conv(-0.300, -3.000)
    check("a curvature past the ceiling is CLAMPED and not refused",
          out.curvature_clamped and not out.refused)
    check("the mechanical stop stands BEHIND the measured ceiling and is "
          "never reached", not out.steer_clamped
          and abs(out.steer_rad - 1.25) < 1e-12)
    # 0.200 m/s and not the corner speed: at 0.300 the wheel would want
    # 0.9515 m/s and the traction ceiling would fire as well, so the row
    # would be measuring two clamps at once.
    out = conv(-0.200, -2.000)
    check("the curvature clamp keeps the speed and gives up the arc",
          out.curvature_clamped and not out.traction_clamped
          and abs(out.v_mps + 0.200) < 1e-12
          and abs(abs(out.w_radps / out.v_mps) - kappa) < 1e-12)

    out = conv(-0.300, -0.800)
    check("the traction clamp IS curvature preserving",
          out.traction_clamped
          and abs(out.w_radps / out.v_mps - (-0.800 / -0.300)) < 1e-12)

    out = conv(0.0, 0.4)
    check("a yaw rate at a standstill is REFUSED, traction zero, steer "
          "HELD", out.refused and out.wheel_mps == 0.0
          and out.steer_rad is None)
    check("below creep but MOVING is declined and is not a refusal",
          not conv(-0.003, 0.4).refused)
    check("a command that is not finite is refused",
          conv(float("nan"), 0.0).refused)

    check("a speed limit scales the whole twist",
          apply_speed_limit(-0.700, -0.400, 0.300)[0] == -0.300)
    check("a speed limit of 0.0 is NO LIMIT and not a stop",
          speed_limit_mps(False, 0.0, 0.700) is None)
    check("a percentage limit is a fraction of the configured maximum",
          abs(speed_limit_mps(True, 50.0, 0.700) - 0.350) < 1e-15)

    # SEEDED AT THE CENTRE, which is what the shell reads off the plant's
    # own joint state. An UNSEEDED limiter adopts its first target
    # instead - there is no held angle to ramp from - and says so.
    limiter = CommandLimiter(2.0, 0.35, steer_rad=0.0)
    check("a step steer command leaves this node as a ramp of "
          "rate x dt", abs(limiter.step(0.05, 1.25, 0.0)[0] - 0.10) < 1e-15)
    ticks = 1
    while abs(limiter.steer_rad - 1.25) > 1e-12 and ticks < 100:
        limiter.step(0.05, 1.25, 0.0)
        ticks += 1
    check("1.25 rad at 2.0 rad/s is thirteen ticks of 50 ms", ticks == 13)
    limiter = CommandLimiter(2.0, 0.35)
    check("the traction ramp is accel x dt",
          abs(limiter.step(0.05, 0.0, -0.700)[1] + 0.0175) < 1e-15)
    limiter = CommandLimiter(2.0, 0.35, steer_rad=0.4)
    check("a HOLD target leaves the steer axis where it is",
          limiter.step(0.05, None, 0.0)[0] == 0.4)

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    # The denominator is derived from the checks that ran and never typed
    # beside them: a hand-written count is how a suite silently leaves a
    # check behind (LESSONS 2026-07-28).
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the Twist -> tricycle arithmetic for m5-ver3. The "
                    "node that uses it is nodes/cmd_vel_tricycle.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-Gazebo checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
