#!/usr/bin/env python3
"""drive_route.py - put the truck through a known manoeuvre, on purpose.

    source /opt/ros/jazzy/setup.bash
    python3 m5_ver3/tools/drive_route.py straight
    python3 m5_ver3/tools/drive_route.py square --dry-run

WHAT IT IS FOR. F1's odometry has to be READ against something, and it
cannot be read against a truck standing still. This drives a fixed,
repeatable profile so that /m5v3/wheel_odom and the ground truth can be
compared over a manoeuvre whose shape is known in advance. config.yaml's
drive_route: block holds every profile and the derivation of every number
in them; this file holds the mechanism and no constants.

IT IS OPEN LOOP AND THAT IS THE HONEST SHAPE. It reads no pose, closes no
loop and corrects nothing: a controller in the loop would make every
divergence a statement about the controller as well as about the
odometry, and the whole point of the bench is that it is not. What the
truck ACTUALLY did is the ground truth's to say, and Task 4's evidence
tables are where it says it.

THE SCHEDULE RUNS ON SIM TIME, READ OFF THE PLANT'S OWN CLOCK. A wall
clock would make the distance covered depend on the day's real-time
factor, so the same profile would sweep a different piece of floor on a
loaded machine - which is the difference between a repeatable manoeuvre
and one that has to be re-measured every run. `gz topic -e` on the clock
is one long-lived subprocess and this file steps its schedule off it.

IT ADDRESSES THE MOTOR TERMINALS DIRECTLY, ON THE GZ SIDE. m5-ver3 runs
no vehicle stack yet, so there is no /forklift/cmd/* layer to publish to
and no reason to bridge one - config.yaml's topics.traction_cmd comment
and tools/slip_bench.sh both make that call already, and this file makes
the same one. The unit conversions are the ones
agv/forklift/scripts/forklift_io.py documents:

    tread speed [m/s]  ->  wheel rate [rad/s]  =  speed / wheel_radius
    steer angle [rad]  ->  steer angle [rad]   =  passed through

forklift_io.py CLAMPS a steer command to the mechanical stop because it
is taking commands from a live stack and has to make one of them legal.
This file REFUSES one instead, before it drives anything: it is reading a
table somebody wrote down, and a table that asks for an impossible angle
is a table to correct rather than a command to soften.

WHAT LEAVING IT IS. Every exit path commands a STANDING ZERO on the
traction terminal, including Ctrl-C and including a refusal partway
through. That is not politeness: model.sdf's JointController holds its
last command FOR EVER, so a publisher that simply stops leaves a standing
order and not a silence - measured in m6, a truck ran 14.8 m on one after
its publisher died. A standing zero on this model is the holding brake.
  IT IS NOT A BRAKE FOR A SAFETY PURPOSE and nothing here is a safety
  function. Protective stop, e-stop and safe torque off are onboard and
  hardwired, and no message this file sends can trigger or release one.

IT DRIVES A LIVE PLANT AND IT DOES NOT START ONE. m5v3.sh owns bringup;
this attaches to whatever is up in this partition, exactly as
tools/rtf_probe.sh and tools/slip_bench.sh do. THE PARTITION IS WHAT
MAKES IT DRIVE THE RIGHT TRUCK: a concurrent m6 stack carries a traction
terminal of exactly the same name, and gz transport is not DDS, so
ROS_DOMAIN_ID would not separate them.
"""
import argparse
import json
import os
import select
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402

TOOL = "drive_route"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id", "paths.ros_setup",
    "topics.clock", "topics.traction_cmd", "topics.steer_cmd",
    "vehicle.wheel_radius_m", "vehicle.steer_limit_rad",
    "drive_route.clock_timeout_s", "drive_route.profiles",
)


class Segment(object):
    """One row of a profile: two standing orders and how long to hold."""

    def __init__(self, hold_s, tread_mps, steer_rad):
        self.hold_s = hold_s
        self.tread_mps = tread_mps
        self.steer_rad = steer_rad


def read_profile(cfg, name):
    """The named profile, checked row by row before anything is driven.

    EVERY REFUSAL HAPPENS BEFORE THE FIRST COMMAND. A profile with a bad
    row halfway down would otherwise be discovered with the truck already
    at cruise, and the operator's next problem would be a moving vehicle
    rather than a typo.
    """
    profiles = cfg.raw("drive_route.profiles")
    if not isinstance(profiles, dict) or name not in profiles:
        cfg.refuse("config.yaml defines drive_route.profiles." + name,
                   _common.CONFIG,
                   "it defines: {}".format(
                       ", ".join(sorted(profiles))
                       if isinstance(profiles, dict)
                       else "<not a mapping>"))
    rows = profiles[name]
    if not isinstance(rows, list) or not rows:
        cfg.refuse("the profile is a non-empty list of segments",
                   _common.CONFIG,
                   "drive_route.profiles.{} reads {!r}".format(name, rows))

    limit = cfg.f("vehicle.steer_limit_rad")
    out = []
    for i, row in enumerate(rows):
        where = "drive_route.profiles.{}[{}]".format(name, i)
        if not isinstance(row, dict):
            cfg.refuse("every segment is a mapping", _common.CONFIG,
                       "{} reads {!r}".format(where, row))
        try:
            hold_s = float(row["hold_s"])
            tread = float(row["tread_mps"])
            steer = float(row["steer_rad"])
        except (KeyError, TypeError, ValueError) as exc:
            cfg.refuse("every segment has numeric hold_s, tread_mps and "
                       "steer_rad", _common.CONFIG,
                       "{} reads {!r}".format(where, row),
                       "the value that would not read: {}".format(exc))
        if hold_s <= 0.0:
            cfg.refuse("every segment holds for a positive time",
                       _common.CONFIG,
                       "{} holds for {} s".format(where, hold_s))
        # THE MECHANICAL STOP IS A REFUSAL AND NOT A CLAMP. A clamp would
        # drive a profile the table does not describe and the geometry in
        # config.yaml's comment would then be a claim about a manoeuvre
        # nobody performed. forklift_io.py clamps because it is taking
        # commands from a live stack; this is reading a table that was
        # written down, and a table can be corrected.
        if abs(steer) > limit:
            cfg.refuse("every steer angle is inside the mechanical stop",
                       _common.CONFIG,
                       "{} asks for {:+.6f} rad".format(where, steer),
                       "vehicle.steer_limit_rad is {:+.6f}".format(limit))
        out.append(Segment(hold_s, tread, steer))
    return out


def describe(name, segments, radius_m):
    """The schedule, printed before it is driven and by --dry-run alone.

    The distances are NOMINAL - what the commands ask for. The tyre slips
    (that is what config.yaml's wheel_slip: block is about) and each
    command lands a fraction of a second late, so what the truck covers
    is smaller and is the ground truth's to report.
    """
    print("profile    {}".format(name))
    print("segments   {}".format(len(segments)))
    print("")
    print("   #   hold_s   t_end_s   tread_mps    omega_rad_s   "
          "steer_rad     ds_m")
    t_end = 0.0
    signed = 0.0
    travelled = 0.0
    for i, seg in enumerate(segments):
        t_end += seg.hold_s
        ds = seg.tread_mps * seg.hold_s
        signed += ds
        travelled += abs(ds)
        print("  {:2d}   {:6.3f}   {:7.3f}   {:+9.3f}   {:+12.4f}   "
              "{:+9.6f}   {:+6.3f}".format(
                  i, seg.hold_s, t_end, seg.tread_mps,
                  seg.tread_mps / radius_m, seg.steer_rad, ds))
    print("")
    print("sim time   {:.3f} s".format(t_end))
    print("nominal    {:.3f} m of tread, net {:+.3f} m along model +x"
          .format(travelled, signed))
    # The sign, spelled out every run rather than left to be remembered.
    print("           negative tread is FORWARD - forks first, model -x,"
          " the travel direction")
    return t_end


def gz_env(cfg):
    """The environment every gz call in this file inherits.

    THE PARTITION IS THE WHOLE POINT. gz transport is not DDS, so
    ROS_DOMAIN_ID does not scope the simulator at all; GZ_PARTITION is
    what decides which truck this bench drives, and config.yaml is where
    it is written so start, stop, status, the probes and this cannot
    disagree about which graph they are on.
    """
    env = dict(os.environ)
    env["GZ_PARTITION"] = cfg.s("isolation.gz_partition")
    env["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")
    return env


def require_gz(cfg):
    """gz on PATH, or a refusal that names the line the operator missed.

    gz-tools for Harmonic comes from gz_tools_vendor under /opt/ros on
    this rig, so ROS has to be sourced even though this file starts no
    ROS node. The shell tools on this track source it themselves; a
    python process cannot, so it says what to type instead.
    """
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, "gz")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return
    cfg.refuse("gz is on PATH", _common.CONFIG + " (paths.ros_setup)",
               "gz-tools comes from gz_tools_vendor under /opt/ros on this "
               "rig, so ROS has to be sourced even though this",
               "bench starts no ROS node:",
               "  source {}".format(cfg.s("paths.ros_setup")),
               "then run this command again. See CONTEXT.md - this stack "
               "lives inside WSL.")


class SimClock(object):
    """The plant's own clock, as a stream of sim seconds.

    ONE LONG-LIVED SUBSCRIBER AND NOT ONE CALL PER POLL. `gz topic -e -n 1`
    per poll would pay a process start for every question; this opens the
    subscription once and reads it.

    IT IS BOUNDED, AND THAT IS NOT THE SAME AS THE SCHEDULE. `gz topic -e`
    waits for its next message FOR EVER, so a stack that is not up would
    hang this bench in silence rather than refuse it. select() puts a
    deadline on each read; a read that times out is a plant that has
    stopped publishing, which is a refusal.
    """

    def __init__(self, cfg, env):
        self.cfg = cfg
        self.topic = cfg.s("topics.clock")
        self.timeout_s = cfg.f("drive_route.clock_timeout_s")
        # NAMED FROM THE ENVIRONMENT THIS FILE BUILT, not from its own.
        # gz_env() puts the partition on the CHILD's environment; this
        # process never carries it, so a refusal that read os.environ
        # would tell the operator the partition was unset - which is
        # true of the wrong process and useless about the right one.
        self.partition = env["GZ_PARTITION"]
        # stdbuf -oL for the reason rtf_probe.sh needs it: gz topic -e
        # block-buffers into a pipe, and a block that is never filled is
        # a clock that never arrives.
        self.proc = subprocess.Popen(
            ["stdbuf", "-oL", "gz", "topic", "-e", "-t", self.topic,
             "--json-output"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=env, text=True)

    def read(self):
        """The next sim time on the wire, in seconds."""
        while True:
            ready, _, _ = select.select([self.proc.stdout], [], [],
                                        self.timeout_s)
            if not ready:
                self.cfg.refuse(
                    "the world published a clock within "
                    "{:g}s".format(self.timeout_s),
                    "{} (config.yaml topics.clock)".format(self.topic),
                    "nothing arrived on that topic.",
                    "is the stack up in partition {} "
                    "('bash m5_ver3/m5v3.sh status')?".format(
                        self.partition))
            line = self.proc.stdout.readline()
            if not line:
                self.cfg.refuse(
                    "the clock subscription stayed open",
                    "{} (config.yaml topics.clock)".format(self.topic),
                    "`gz topic -e` exited. Did the world stop?")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # gz prints one JSON object per line; a partial line is a
                # write that has not finished, not a malformed message.
                continue
            # Protobuf omits zero fields, so every read is defaulted - a
            # message that lands on an exact second carries no nsec.
            sim = msg.get("sim", {})
            if not isinstance(sim, dict):
                continue
            return float(sim.get("sec", 0)) + float(sim.get("nsec", 0)) * 1e-9

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            pass


class Terminals(object):
    """The two motor terminals, as one-shot standing orders.

    ONE PUBLISH PER SETPOINT, NOT A STREAM. model.sdf's JointController
    and JointPositionController each hold their last command for ever, so
    a repeated publish would buy nothing and a missing one is not a
    silence - it is the previous order still standing.
    """

    def __init__(self, cfg, env):
        self.cfg = cfg
        self.env = env
        self.traction = cfg.s("topics.traction_cmd")
        self.steer = cfg.s("topics.steer_cmd")
        self.radius_m = cfg.f("vehicle.wheel_radius_m")

    def _publish(self, topic, value, fatal=True):
        result = subprocess.run(
            ["gz", "topic", "-t", topic, "-m", "gz.msgs.Double",
             "-p", "data: {:.9f}".format(value)],
            env=self.env, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return True
        detail = "gz topic -p exited {}: {}".format(
            result.returncode, (result.stderr or "").strip())
        if not fatal:
            # THE EXIT PATH REPORTS AND DOES NOT REFUSE. A second refusal
            # raised on the way out of the first one would replace the
            # message that says what actually went wrong with a message
            # about the tidying up - and the operator would then go and
            # read the wrong file. What they need to know here is only
            # that the standing zero did not land.
            for line in (
                    "WARNING - the standing zero did NOT reach " + topic,
                    "          " + detail,
                    "          THE LAST COMMAND IS STILL STANDING: this "
                    "model's controller holds it for ever."):
                sys.stderr.write("drive_route: {}\n".format(line))
            sys.stderr.flush()
            return False
        self.cfg.refuse(
            "the terminal accepted a command", topic, detail,
            "is the stack up in partition {} "
            "('bash m5_ver3/m5v3.sh status')?".format(
                self.env["GZ_PARTITION"]))

    def command(self, tread_mps, steer_rad):
        """THE STEER GOES FIRST AND THEN THE TRACTION, every time.

        The other order would run the truck at the new speed on the old
        steer angle for as long as the second publish takes, which on a
        corner is the difference between an arc and a corner cut.
        """
        self._publish(self.steer, steer_rad)
        # forklift_io.py's conversion: rad/s at the wheel is m/s of tread
        # over the rolling radius. The TRUE radius, because this is a
        # command to the plant - the odometry's believed radius is a
        # different number and belongs to a different file.
        self._publish(self.traction, tread_mps / self.radius_m)

    def standing_zero(self):
        """What every exit path leaves behind. See the file header."""
        return self._publish(self.traction, 0.0, fatal=False)


def run(cfg, segments):
    env = gz_env(cfg)
    clock = SimClock(cfg, env)
    terminals = Terminals(cfg, env)
    try:
        t0 = clock.read()
        print("clock      {} reads {:.3f} s of sim time".format(
            cfg.s("topics.clock"), t0))
        print("partition  {}".format(env["GZ_PARTITION"]))
        print("")
        deadline = t0
        for i, seg in enumerate(segments):
            deadline += seg.hold_s
            terminals.command(seg.tread_mps, seg.steer_rad)
            print("  seg {:2d}  tread {:+7.3f} m/s  steer {:+9.6f} rad  "
                  "until t = {:.3f}".format(
                      i, seg.tread_mps, seg.steer_rad, deadline))
            sys.stdout.flush()
            while clock.read() < deadline:
                pass
        print("")
        print("profile complete at t = {:.3f} s of sim time".format(deadline))
    finally:
        # THE LAST THING THAT HAPPENS, WHATEVER HAPPENED. A refusal, a
        # Ctrl-C and a clean finish all leave the traction terminal at a
        # standing zero, because on this model a silent terminal is a
        # standing order rather than an absence.
        landed = terminals.standing_zero()
        clock.close()
        if landed:
            print("traction terminal left at a standing zero.")


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    profiles = cfg.raw("drive_route.profiles")
    parser = argparse.ArgumentParser(
        description="drive one of config.yaml's profiles on the live "
                    "m5-ver3 plant. It drives; it records nothing.",
        epilog="the profiles and every number in them live in "
               "m5_ver3/config.yaml under drive_route:.")
    parser.add_argument(
        "profile",
        choices=sorted(profiles) if isinstance(profiles, dict) else [],
        help="which profile to drive")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print the schedule and exit without touching the plant")
    args = parser.parse_args(argv)

    segments = read_profile(cfg, args.profile)
    radius_m = cfg.f("vehicle.wheel_radius_m")
    print("=== m5v3 drive route ===")
    describe(args.profile, segments, radius_m)
    print("")
    if args.dry_run:
        print("--dry-run: nothing was commanded and nothing moved.")
        return 0
    require_gz(cfg)
    run(cfg, segments)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # run()'s finally has already left the standing zero by the time
        # this is reached; this only keeps the traceback out of the log.
        sys.stderr.write("\ndrive_route: interrupted.\n")
        sys.exit(130)
