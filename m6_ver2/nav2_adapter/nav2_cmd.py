#!/usr/bin/env python3
"""nav2_cmd.py - a smoothed nav2 twist becomes m6's traction and steer.

    python3 m6_ver2/nav2_adapter/nav2_cmd.py --selftest

NO ROS IN THIS FILE. The shell subscribes `/fN/cmd_vel_smoothed` and
publishes `/fN/auto/cmd_vel`; everything that could be WRONG about the
translation is here, where a test can reach it - and what is wrong on
this seam steers at the rack.

THE SEAM, IN ONE LINE:

    nav2 controller_server -> /fN/cmd_vel -> nav2_velocity_smoother
      -> /fN/cmd_vel_smoothed   (Twist: v m/s signed, w rad/s)
        -> THIS -> /fN/auto/cmd_vel  (linear.x = TRACTION m/s,
                                      angular.z = STEER ANGLE rad)
          -> cmd_mux -> cmd_gate -> forklift_io -> sto_contactor

============================== THE SIGNS ==============================

Three sentences generate everything below, and all three belong to the
repository rather than to this file:

  MODEL YAW 0 POINTS THE FORKS AT WORLD -x, so forks-first travel is a
  NEGATIVE `linear.x` in base_link. BOTH STACKS SHARE THAT MODEL, so
  nav2's ordinary reverse leg already commands the negative the m6
  command path wants: THE TRACTION SIGN PASSES THROUGH UNCHANGED and
  there is no flip in this file. A flip here would be correct on the
  bench and backwards on the floor.

  POSITIVE STEER IS DRIVER-RIGHT (cmd_vel_tricycle_core's header), which
  in base_link is a DECREASING yaw and therefore a NEGATIVE `angular.z`.

  POSITIVE `angular.z` IS A DRIVER-RIGHT TURN on m6's command path
  (cmd_gate.py's field contract), and that field carries an ANGLE and
  not a rate.

So the ONE thing this file changes is `angular.z`'s TYPE - yaw rate in,
steer angle out - and the two conventions agree on which way positive
means, so the adapter emits `angular.z = +steer_rad`. A worked example
per sign combination locks it in tests/test_nav2_adapter_cmd.py, in the
test_follower idiom, because getting it wrong is a truck that steers
toward the racking it was avoiding.

THE ARITHMETIC IS IMPORTED AND NOT COPIED.
`cmd_vel_tricycle_core.twist_to_tricycle` owns delta = atan2(L*w*sgn v,
|v|), the curvature ceiling, the mechanical stop and the
yaw-rate-at-standstill refusal. A second spelling of that atan2 would be
a second opinion about one vehicle, and the residual would look like
slip. This file is a translator between two field contracts and a cap;
it is not a kinematics.

=========================== THE V_LIMIT CAP ===========================

Three layers, all pointing the same way - "approach the limit from
below", the Step-3 lesson nav_core already obeys and that follower.py's
header carries the measurement for (V_Limit went 1500 -> 300 with the
wheels still at 700 mm/s and the F-program's speed monitor LATCHED):

  1. The adapter publishes `nav2_msgs/SpeedLimit` on `/fN/speed_limit`
     so controller_server PLANS at the permission (speed_limit_message).
  2. THIS FILE caps at source, in the translation (translate).
  3. cmd_gate still clamps, unchanged, and keeps the last word.

AND THE CAP LANDS ON TWO QUANTITIES BECAUSE V_Limit IS ONE PERMISSION
READ BY TWO DEVICES. `apply_speed_limit` scales the whole twist, which
holds w/v and therefore holds the STEER ANGLE exactly - the planner's
body speed is legal and the arc is untouched. But the F-program's speed
monitor reads the SHAFT, and the shaft carries v/cos(delta), which grows
without bound as the wheel goes over: at this vehicle's commanded lock
that is 3.16 times v. So the tread ceiling handed to
`twist_to_tricycle` is the permission too. Clamping the tread with delta
HELD scales v and w together, so that cap is curvature preserving as
well: the truck drives the same arc, more slowly.
"""
import argparse
import collections
import math
import sys

import _donors                                            # noqa: F401

import cmd_vel_tricycle_core as tri                       # noqa: E402
from status_contract import (                             # noqa: E402
    V_LIMIT_CREEP_MM_S, speed_limit_mm_s)


class Nav2CmdError(ValueError):
    """A limits block this file will not guess the missing half of."""


#: EVERY CEILING IS AN ARGUMENT, so what this file decides is a function
#: of the per-truck config.yaml and of nothing in the room. The names are
#: `twist_to_tricycle`'s own, plus the steer ANGLE the curvature ceiling
#: is derived from - config states the angle, because the angle is what
#: was measured.
Limits = collections.namedtuple(
    "Limits",
    "wheelbase_m steer_limit_rad steer_command_limit_rad curvature_max_1pm "
    "traction_max_mps creep_speed_mps zero_speed_mps yawrate_refusal_radps")

#: WHAT COMES OUT, AS A RECORD. `linear_x` and `angular_z` are the two
#: fields of `/auto/cmd_vel` and nothing else in the adapter has to know
#: how they were derived; `v_mps` and `w_radps` are the twist the pair
#: actually DELIVERS after every clamp, so a log can print what was
#: asked for beside what is going to happen.
#:
#: `angular_z` IS None WHEN THE ANSWER IS "HOLD THE STEER AXIS". That is
#: not an absence of an answer - it is a different answer from zero, and
#: zero would centre the wheel, which is a motion command nobody issued.
#: The shell republishes the last angle it sent.
AutoCmd = collections.namedtuple(
    "AutoCmd",
    "linear_x angular_z v_mps w_radps reversing "
    "curvature_clamped steer_clamped traction_clamped refused reason")

#: The keys a per-truck config's vehicle block has to carry, in the
#: order the refusal lists them.
LIMIT_KEYS = ("wheelbase_m", "steer_limit_rad", "steer_command_limit_rad",
              "traction_max_mps", "creep_speed_mps", "zero_speed_mps",
              "yawrate_refusal_radps")


def limits_from_config(block):
    """A `Limits` out of a config mapping, refusing a missing key by name.

    REFUSED HERE AND NOT AT THE FIRST TWIST. A missing ceiling that
    defaulted to something would be a vehicle limit nobody chose, driven
    at for a whole run and then measured as if it had been.
    """
    missing = [key for key in LIMIT_KEYS if key not in block]
    if missing:
        raise Nav2CmdError(
            "the vehicle limits block carries no {}. All seven are "
            "required and none has a default: {}".format(
                ", ".join(missing), ", ".join(LIMIT_KEYS)))
    values = {key: float(block[key]) for key in LIMIT_KEYS}
    return Limits(
        curvature_max_1pm=tri.curvature_max(
            values["steer_command_limit_rad"], values["wheelbase_m"]),
        **values)


#: THE VER2 TRUCK'S OWN NUMBERS, for --selftest and for the suite. Read
#: from agv/forklift/config.yaml (`model.wheelbase_m` 1.05,
#: `model.steer_limit_rad` 1.31, `limits.traction_speed_max_mps` 1.50)
#: and m5_ver3/config.yaml's `navcmd` block for the three deadbands and
#: the COMMANDED steer ceiling of 1.25 rad - the hardest angle this
#: plant has ever been driven at, with the 1.31 mechanical stop standing
#: behind it as a backstop that cannot be reached from a twist. The
#: RUNTIME builds its own from m6_ver2/vehicles/fN/config.yaml; this
#: constant is a fixture, not a source of truth.
SELFTEST_LIMITS = limits_from_config({
    "wheelbase_m": 1.05,
    "steer_limit_rad": 1.31,
    "steer_command_limit_rad": 1.25,
    "traction_max_mps": 1.50,
    "creep_speed_mps": 0.005,
    "zero_speed_mps": 0.001,
    "yawrate_refusal_radps": 0.01,
})


def limit_mps_from_v_limit(v_limit_mm_s):
    """The PLC's speed permission as a ceiling in m/s.

    status_contract.speed_limit_mm_s IS THE RULE AND IT IS IMPORTED: a
    negative or absurd V_Limit is a fault in the READING, and a fault
    must not widen a permission, so it narrows to the creep ceiling.
    Deciding that a second time here would be a second answer to "what
    does an unreadable permission mean".
    """
    return speed_limit_mm_s(v_limit_mm_s) / 1000.0


def speed_limit_message(v_limit_mm_s):
    """`nav2_msgs/SpeedLimit`'s two fields, as data for the shell.

    ABSOLUTE AND NOT A PERCENTAGE. A percentage is a fraction of
    whatever the controller thinks its maximum is, and that is a second
    number the PLC has never heard of; V_Limit is metres per second at
    the shaft and it is published as metres per second.
    """
    return {"speed_limit": limit_mps_from_v_limit(v_limit_mm_s),
            "percentage": False}


def is_reversing(linear_x, limits):
    """m6's `reversing` flag: a POSITIVE traction beyond the deadband.

    Positive linear.x is counterweight-first, which is m6's reverse and
    nav2's forward. THE DEADBAND IS THE CONVERTER'S OWN CREEP BAND
    because that is where the repo already draws this line: below it the
    sign of a command is not a direction, it is the tail of a
    deceleration (config.yaml's `cusp_speed_mps` counts cusps on the
    same number for the same reason).
    """
    return float(linear_x) > abs(limits.creep_speed_mps)


def translate(v, w, limits, limit_mps=None):
    """One smoothed twist as one `/auto/cmd_vel` message.

    `limit_mps` is the live V_Limit permission as a ceiling in m/s, or
    None for no limit. NO LIMIT IS NOT A STOP - the SpeedLimit message's
    own comment says so, and a translator that read a lifted limit as a
    brake would stop the truck every time the aisle cleared.
    """
    v, w = tri.apply_speed_limit(v, w, limit_mps)
    traction_ceiling = abs(limits.traction_max_mps)
    if limit_mps is not None:
        traction_ceiling = min(traction_ceiling, abs(limit_mps))
    out = tri.twist_to_tricycle(
        v, w,
        wheelbase_m=limits.wheelbase_m,
        steer_limit_rad=limits.steer_limit_rad,
        curvature_max_1pm=limits.curvature_max_1pm,
        traction_max_mps=traction_ceiling,
        creep_speed_mps=limits.creep_speed_mps,
        zero_speed_mps=limits.zero_speed_mps,
        yawrate_refusal_radps=limits.yawrate_refusal_radps)
    return AutoCmd(
        # NO FLIP ON EITHER FIELD, AND THAT IS THE POINT. The tread is
        # already in the repo's sign convention and the steer angle is
        # already driver-right-positive, which is what m6's angular.z
        # means. See the header.
        linear_x=out.wheel_mps,
        angular_z=out.steer_rad,
        v_mps=out.v_mps, w_radps=out.w_radps,
        reversing=is_reversing(out.wheel_mps, limits),
        curvature_clamped=out.curvature_clamped,
        steer_clamped=out.steer_clamped,
        traction_clamped=out.traction_clamped,
        refused=out.refused, reason=out.reason)


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_nav2_adapter_cmd.py is the real suite - it rounds every
    pair back through cmd_vel_tricycle_core's own forward model - and
    this is the version an operator can run on the rig, in the shell
    they are already in, without pytest. It covers the one thing this
    seam gets wrong: the signs.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    limits = SELFTEST_LIMITS

    def out(v, w, limit=None):
        return translate(v, w, limits, limit_mps=limit)

    check("the commanded curvature ceiling is derived from the ANGLE that "
          "was measured (2.8662568 1/m, R 0.3488871 m)",
          abs(limits.curvature_max_1pm - 2.8662568322503152) < 1e-12)

    row = out(-0.300, 0.0)
    check("forks-first straight is a NEGATIVE traction and a centred "
          "wheel", abs(row.linear_x + 0.300) < 1e-12
          and row.angular_z == 0.0 and row.reversing is False)
    row = out(0.250, 0.0)
    check("counterweight-first straight is a POSITIVE traction, and m6 "
          "calls that reversing", abs(row.linear_x - 0.250) < 1e-12
          and row.angular_z == 0.0 and row.reversing is True)
    check("forward + driver-right (negative angular.z IN) is a POSITIVE "
          "steer angle OUT", out(-0.300, -0.200).angular_z > 0.0)
    check("forward + driver-left is a NEGATIVE steer angle",
          out(-0.300, 0.200).angular_z < 0.0)
    check("astern with the wheel cocked right is the SAME positive angle",
          out(0.250, 0.200).angular_z > 0.0)
    check("astern with the wheel cocked left is the same negative angle",
          out(0.250, -0.200).angular_z < 0.0)
    check("the same wheel angle serves both directions",
          abs(out(-0.300, -0.300).angular_z
              - out(0.300, 0.300).angular_z) < 1e-12)

    worst = 0.0
    for v in (-0.700, -0.300, -0.050, 0.050, 0.300, 0.700):
        for w in (-0.25, -0.10, 0.0, 0.10, 0.25):
            row = out(v, w)
            back = tri.tricycle_to_twist(row.angular_z, row.linear_x,
                                         limits.wheelbase_m)
            worst = max(worst, abs(back[0] - row.v_mps),
                        abs(back[1] - row.w_radps))
    check("the round trip through the forward model is exact "
          "({:.2e})".format(worst), worst < 1e-12)

    free, capped = out(-0.700, -0.500), out(-0.700, -0.500, limit=0.300)
    check("the creep permission caps the SHAFT at 0.300 m/s",
          abs(capped.linear_x) <= 0.300 + 1e-12)
    check("and it costs the speed, never the arc",
          abs(free.angular_z - capped.angular_z) < 1e-12
          and abs(capped.w_radps / capped.v_mps
                  - free.w_radps / free.v_mps) < 1e-9)
    hard = out(-0.300, -0.800, limit=0.300)
    check("a hard arc would beat a body-only cap, and does not beat this "
          "one", abs(hard.linear_x) <= 0.300 + 1e-12
          and abs(hard.v_mps) < 0.300)
    check("no limit is NOT a stop",
          abs(out(-0.700, 0.0, limit=None).linear_x + 0.700) < 1e-12)

    check("300 mm/s is 0.300 m/s and 1500 is 1.500",
          limit_mps_from_v_limit(300) == 0.300
          and limit_mps_from_v_limit(1500) == 1.500)
    check("an unreadable V_Limit narrows to the creep ceiling ({} mm/s)"
          .format(V_LIMIT_CREEP_MM_S),
          limit_mps_from_v_limit(None) == 0.300
          and limit_mps_from_v_limit(-1) == 0.300
          and limit_mps_from_v_limit(99999) == 0.300)
    check("the SpeedLimit message is absolute and not a percentage",
          speed_limit_message(300) == {"speed_limit": 0.300,
                                       "percentage": False})

    row = out(0.0, 0.400)
    check("a yaw rate at a STANDSTILL is refused, traction zero, steer "
          "HELD", row.refused and row.linear_x == 0.0
          and row.angular_z is None)
    check("below creep but MOVING is declined and is not a refusal",
          not out(-0.003, 0.400).refused)
    check("a command that is not finite is refused",
          out(float("nan"), 0.0).refused and out(0.0, float("inf")).refused)
    check("the steer angle never leaves the mechanical stop",
          all(abs(out(-0.300, w).angular_z) <= limits.steer_limit_rad + 1e-12
              for w in (-4.0, -1.0, 0.0, 1.0, 4.0)))

    try:
        limits_from_config({"wheelbase_m": 1.05})
        check("an incomplete limits block is refused by name", False)
    except Nav2CmdError as exc:
        check("an incomplete limits block is refused by name",
              "steer_limit_rad" in str(exc))

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the smoothed-twist -> (traction, steer angle) "
                    "translation for m6_ver2's nav2 adapter. The node "
                    "that uses it is nav2_adapter_node.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-simulator checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
