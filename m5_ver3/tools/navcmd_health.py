#!/usr/bin/env python3
"""navcmd_health.py - is the command path a LINE, or three processes that
have never spoken to each other?

    python3 m5_ver3/tools/navcmd_health.py    # exit 0 healthy, 1 refused

WHY IT EXISTS. `m5v3.sh start` already proves that both command-path
children are ALIVE, that the smoother reached ACTIVE and that the
estimator underneath is sane. None of that is the question. The command
path is four hops -

    topics.cmd_vel  ->  velocity_smoother  ->  topics.cmd_vel_smoothed
      ->  nodes/cmd_vel_tricycle.py  ->  topics.traction_cmd (ROS)
        ->  the parameter bridge  ->  topics.traction_cmd (gz)

- and EVERY ONE of them fails silently. A remap that did not land, a
subscription spelt against the wrong config key, a bridge line written
`[` where it needed `]`: in all three cases every process is up, every
log is clean, `status` reads ALIVE, and NOTHING IS PUBLISHED - which at
rest is exactly what a healthy command path looks like too. That
ambiguity is the whole reason for this file.

WHAT IT DOES. It publishes ONE KIND OF COMMAND - a ZERO twist, the only
command that cannot move this vehicle - and reads the answer back off the
GZ SIDE of the traction terminal, which is the far end of the last hop.
Nothing shorter proves the line: reading the ROS side would leave the
bridge untested, and reading the smoother's output would leave the
converter untested.

  A ZERO TWIST IS NOT A NO-OP AND THAT IS THE POINT. It engages the
  converter, runs the whole chain and lands a standing zero on the
  traction terminal - which is where model.sdf's JointController already
  is, having been spawned at `initial_velocity 0.0` seconds earlier. So
  the plant does not move, and tools/drive_route.py's own exit rule says
  what the value means: a silent terminal on this model is a standing
  ORDER, not an absence, and a standing zero is what pins the shaft.
  IT IS NOT A BRAKE FOR A SAFETY PURPOSE and this file is not a safety
  function.

  AND THE STEER TERMINAL IS DELIBERATELY NOT COMMANDED. A zero twist is
  below the creep deadband, so the converter answers it with zero
  traction and a HELD steer axis (nodes/cmd_vel_tricycle_core.py's
  header argues why holding and not re-centring). A gate that demanded a
  steer message would be demanding that this stack move the wheel at
  every bringup, which is a motion nobody asked for.

WHAT IT IS NOT. It is not an instrument: it measures nothing, records
nothing and writes no session. tools/drive_twist.py is the instrument.
It is a BRINGUP GATE, run once by `m5v3.sh start` with the truck standing
where it was spawned, and it refuses the whole bringup if it says no.

  IT IS ALSO NOT A CHECK ON WHAT THE CONVERTER COMPUTES. The arithmetic
  is nodes/cmd_vel_tricycle_core.py's and pytest reaches it without a
  simulator; three hundred assertions about the conversion would still
  not tell you whether the messages arrive. This asks only that.

NO rclpy. `ros2 topic pub` and `gz topic -e` are two subprocesses, which
is tools/ekf_health.py's shape and for its reason: a gate that has to
import a middleware to ask whether a message arrived has one more thing
that can be wrong with it than the question deserves.
"""
import json
import os
import select
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402

TOOL = "navcmd_health"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id",
    "topics.cmd_vel", "topics.cmd_vel_smoothed", "topics.traction_cmd",
    "topics.navcmd_status", "navcmd.rate_hz", "navcmd.health_timeout_s",
)


def gz_env(cfg):
    """The environment the gz-side listener inherits.

    THE PARTITION IS THE WHOLE POINT and it is drive_route.gz_env()'s
    argument: gz transport is not DDS, so ROS_DOMAIN_ID does not scope
    the simulator at all. A concurrent m6 stack carries a traction
    terminal of exactly this name.
    """
    env = dict(os.environ)
    env["GZ_PARTITION"] = cfg.s("isolation.gz_partition")
    env["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")
    return env


def status_line(cfg, timeout_s):
    """The converter's own heartbeat, read once. Its text, or None.

    IT IS READ FIRST, BEFORE ANYTHING IS COMMANDED, and that ordering is
    the point: the status topic publishes whether or not the node has
    ever heard a command, so a read here separates "the converter is
    running" from "the converter heard me" - and the two failures send an
    operator to different files.
    """
    try:
        done = subprocess.run(
            ["ros2", "topic", "echo", "--once",
             cfg.s("topics.navcmd_status")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return None
    except OSError as exc:
        cfg.refuse("ros2 is on the PATH", _common.CONFIG + " (paths.ros_setup)",
                   "could not run `ros2 topic echo`: {}".format(exc),
                   "this gate runs INSIDE WSL with /opt/ros/jazzy sourced.")
    text = done.stdout.decode("utf-8", "replace")
    return text if "engaged" in text else None


def terminal_value(cfg, timeout_s):
    """One gz.msgs.Double off the GZ side of the traction terminal.

    SUBSCRIBED BEFORE THE COMMAND IS SENT, never after. The converter
    publishes a bounded burst and then disengages; a listener opened
    afterwards would wait for a message that is not coming and report an
    open circuit that is not there.

    `stdbuf -oL` for tools/rtf_probe.sh's reason: `gz topic -e`
    block-buffers into a pipe, and a block that is never filled is a
    reading that never arrives.
    """
    topic = cfg.s("topics.traction_cmd")
    listener = subprocess.Popen(
        ["stdbuf", "-oL", "gz", "topic", "-e", "-t", topic, "--json-output"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env=gz_env(cfg), text=True)
    period = 1.0 / cfg.f("navcmd.rate_hz")
    publisher = subprocess.Popen(
        ["ros2", "topic", "pub", "-r", "{:g}".format(cfg.f("navcmd.rate_hz")),
         cfg.s("topics.cmd_vel"), "geometry_msgs/msg/Twist",
         "{linear: {x: 0.0, y: 0.0, z: 0.0}, "
         "angular: {x: 0.0, y: 0.0, z: 0.0}}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = timeout_s
        while deadline > 0.0:
            ready, _, _ = select.select([listener.stdout], [], [], period)
            deadline -= period
            if not ready:
                continue
            line = (listener.stdout.readline() or "").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # gz prints one JSON object per line; a partial line is a
                # write that has not finished, not a malformed message.
                continue
            # Protobuf omits zero fields, so a standing zero arrives as
            # an EMPTY object - which is the very message this gate
            # expects and the one a naive `msg["data"]` would lose.
            return float(msg.get("data", 0.0))
        return None
    finally:
        for proc in (publisher, listener):
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                pass


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    timeout_s = cfg.f("navcmd.health_timeout_s")

    status = status_line(cfg, timeout_s)
    if status is None:
        cfg.refuse(
            "the converter published its own status inside "
            "{:g}s".format(timeout_s),
            "{} (config.yaml topics.navcmd_status, "
            "navcmd.status_every_s)".format(cfg.s("topics.navcmd_status")),
            "nothing arrived on that topic. The node's status timer runs "
            "whether or not",
            "it has ever heard a command, so a silence here is the NODE "
            "and not the path:",
            "read m5_ver3/logs/navcmd.log, which will name the config key "
            "it refused on.")

    value = terminal_value(cfg, timeout_s)
    if value is None:
        cfg.refuse(
            "one commanded ZERO reached the plant's traction terminal "
            "inside {:g}s".format(timeout_s),
            "{} (gz side) - the whole chain from {}".format(
                cfg.s("topics.traction_cmd"), cfg.s("topics.cmd_vel")),
            "the converter is ALIVE and talking (its status was read "
            "above), the smoother",
            "is ACTIVE, and a zero twist was published at {:g} Hz for the "
            "whole budget -".format(cfg.f("navcmd.rate_hz")),
            "and nothing came out at the far end. FOUR HOPS CAN SWALLOW "
            "IT AND EACH IS",
            "SILENT:",
            "  1. {} -> the smoother's subscription (a remap that did "
            "not land)".format(cfg.s("topics.cmd_vel")),
            "  2. the smoother -> {} (it is ACTIVE, so this is a "
            "remap too)".format(cfg.s("topics.cmd_vel_smoothed")),
            "  3. {} -> the converter (config.yaml "
            "topics.cmd_vel_smoothed)".format(
                cfg.s("topics.cmd_vel_smoothed")),
            "  4. the ROS side of {} -> gz, which is the parameter "
            "bridge's".format(cfg.s("topics.traction_cmd")),
            "     ONE ROS -> gz line: written `[` instead of `]` it "
            "carries the other way",
            "     and nothing on the gz side ever hears it.",
            "Read them in that order:",
            "  ros2 topic hz {}".format(cfg.s("topics.cmd_vel_smoothed")),
            "  ros2 topic hz {}".format(cfg.s("topics.traction_cmd")),
            "  gz topic -l | grep {}".format(cfg.s("topics.traction_cmd")))

    if value != 0.0:
        cfg.refuse(
            "a ZERO twist arrived as a ZERO wheel rate",
            "{} and nodes/cmd_vel_tricycle_core.py".format(
                cfg.s("topics.traction_cmd")),
            "the terminal received {:+.6f} rad/s for a command of "
            "v = 0, w = 0.".format(value),
            "A zero twist is below the creep deadband, so the converter "
            "answers it with a",
            "STANDING ZERO on the traction terminal and a HELD steer "
            "axis. A non-zero",
            "value here means something else is commanding this terminal "
            "at the same",
            "time - tools/drive_route.py and tools/slip_bench.sh both "
            "address the gz side",
            "of it directly, and gz transport takes the LAST WRITE.",
            "Nothing else on this stack publishes there.")

    print("  navcmd: the command path is one line. A zero twist on {} "
          "arrived at".format(cfg.s("topics.cmd_vel")))
    print("          {} (gz side) as {:+.6f} rad/s - through the "
          "smoother,".format(cfg.s("topics.traction_cmd"), value))
    print("          the converter and the bridge, four hops, none of "
          "them silent any more.")
    print("          The steer terminal was NOT commanded: a zero twist "
          "HOLDS the axis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
