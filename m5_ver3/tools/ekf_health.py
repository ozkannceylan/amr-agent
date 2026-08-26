#!/usr/bin/env python3
"""ekf_health.py - did the filter come up, or did it come up BROKEN?

    python3 m5_ver3/tools/ekf_health.py      # exit 0 healthy, 1 refused

ONE READ OF ONE MESSAGE, AND IT IS A BRINGUP GATE AND NOT AN INSTRUMENT.
m5v3.sh runs this once, after the EKF child is up and while the truck is
still standing where it was spawned, and refuses the whole bringup if it
says no. It measures nothing, records nothing and writes no session.

WHY IT EXISTS. robot_localization's ekf_node can diverge during its first
cycles on this stack - covariance 5.0e-4 to 2.4e84 in ONE 20 ms cycle,
the pose to 1e48 m - and it does it SILENTLY. The process stays up, so
`status` reads ALIVE; the publisher keeps its configured rate, so every
rate check is green; the recorder's stream arrives, so `record` starts
happily. EVIDENCE_FUSION.md 8.6 measured it at 13 of 14 bringups of the
configuration that fused the IMU's ax channel, and 9 records what
dropping that channel did to the rate. THE CHANNEL IS GONE AND THIS GATE
STAYS: an instability that was silent once is a thing this stack now
asks about out loud, every time, so that no future change can reintroduce
it and be found out three tables later.

THE COVARIANCE AND NOT THE POSE, deliberately. A pose far from the origin
is ambiguous at bringup - the truck could legitimately have been driven -
but a covariance is not: this filter starts with ~1e-9 on its diagonal
and a healthy one is still at 1e-4 when this runs. config.yaml's
ekf.startup_check.covariance_max is the ceiling and the derivation is
beside it there. The arithmetic is evidence_core.require_covariance_under()
and it is tested there, without ROS and without a simulator.

THE WAIT IS BOUNDED, which is tools/noise_probe.sh's lesson: `ros2 topic
echo --once` waits for its message FOR EVER, so a filter that never
published at all would hang the bringup in silence instead of refusing
it. A read that times out is a refusal naming the topic.
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as core                          # noqa: E402

TOOL = "ekf_health"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id",
    "topics.odometry_filtered",
    "ekf.startup_check.covariance_max", "ekf.startup_check.timeout_s",
    "ekf.params_file",
)


def read_once(cfg):
    """One message off the filter's output topic, as text, or a refusal.

    The isolation keys go on the environment for tools/
    sensor_evidence.py's reason: a tool an operator runs by hand
    inherits whatever shell they are in, which is domain 0 - a graph
    this stack has never published on.
    """
    env = dict(os.environ)
    env["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")
    env["GZ_PARTITION"] = cfg.s("isolation.gz_partition")
    topic = cfg.s("topics.odometry_filtered")
    timeout = cfg.f("ekf.startup_check.timeout_s")
    try:
        done = subprocess.run(
            ["ros2", "topic", "echo", "--once", topic],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        cfg.refuse(
            "the filter published a message inside "
            "{:g}s".format(timeout),
            "{} (config.yaml ekf.startup_check.timeout_s)".format(topic),
            "nothing arrived on that topic at all. ekf_node is SILENT "
            "about an input",
            "that never arrives, so the thing to check is the topic and "
            "not the log:",
            "  ros2 topic list | grep {}".format(topic),
            "EVIDENCE_FUSION.md 2.6.")
    except OSError as exc:
        cfg.refuse("ros2 is on the PATH", _common.CONFIG + " (paths.ros_setup)",
                   "could not run `ros2 topic echo`: {}".format(exc),
                   "this gate runs INSIDE WSL with /opt/ros/jazzy sourced.")
    return done.stdout.decode("utf-8", "replace")


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    ceiling = cfg.f("ekf.startup_check.covariance_max")
    text = read_once(cfg)
    try:
        worst = core.require_covariance_under(
            text, ceiling,
            "the filter, one message after bringup with the truck at spawn,")
    except core.EvidenceError as exc:
        cfg.refuse(
            "the filter came up without diverging",
            "{} (ekf.startup_check.covariance_max) and {}".format(
                _common.CONFIG, cfg.s("ekf.params_file")),
            str(exc),
            "ekf_node reports NOTHING about this: it stays ALIVE and "
            "publishes at its",
            "configured rate, so every other check on this stack is "
            "green. The message",
            "it published is above.",
            "NOTHING IS WRONG WITH THE PLANT - stop the stack and start "
            "it again.")
    print("  ekf: healthy, worst covariance {:.6g} against a ceiling of "
          "{:g}".format(worst, ceiling))
    return 0


if __name__ == "__main__":
    sys.exit(main())
