#!/usr/bin/env python3
"""ekf_health.py - did the estimator come up, or did it come up BROKEN?

    python3 m5_ver3/tools/ekf_health.py      # exit 0 healthy, 1 refused

ONE GATE, BOTH ARMS, AND IT ASKS THE RUNNING STACK WHICH ONE IT IS.
Since F2 Task 4 this track has two estimators and they publish on
different topics - robot_localization's ekf_node on
topics.odometry_filtered, fuse's fixed-lag smoother on
topics.fuse_odometry_filtered. This file reads the `arm=` line
`m5v3.sh start` has already written to paths.traction_file by the time it
runs, and picks the topic from it (evidence_core.fused_topic_key, tested
there without ROS). It is ONE gate rather than one per arm because the
question is the same question - "is this thing still an estimator, or is
it a wreck that is still publishing" - and a second copy of it would be a
second thing to keep in step.
  IT KEEPS ITS NAME. `ekf_health` is what m5v3.sh, config.yaml, the
  evidence files and two task reports call it; renaming it to
  `estimator_health` would be a churn across five files to say something
  the first paragraph of this docstring already says.
  THE CEILING IS NOT PARAMETERISED BY ARM AND THAT IS DELIBERATE.
  config.yaml's ekf.startup_check.covariance_max is a claim about a
  filter that has just started with the truck at spawn - 100.0, against a
  measured healthy band of 0.08 to 0.23 and a divergence that misses it
  by eighty-two orders of magnitude - and not a claim about
  robot_localization. Two ceilings would be two standards, and grading
  the two arms of an A/B against different standards is a thing that
  should never happen by accident. config.yaml's fuse: block argues it
  where the absent key would have been.

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
  EXCEPT ON AN ARM THAT PUBLISHES NO COVARIANCE, WHICH F2 TASK 4 FOUND.
  `fuse_models::Odometry2DPublisher` 1.1.5 ships 36 zeros on the pose and
  36 on the twist of every message, silently (EVIDENCE_FUSION.md 11.2).
  Against that matrix the ceiling above cannot fail, and a gate that
  cannot fail is worse than no gate because its line is read as an
  answer. So this file asks covariance_is_absent() FIRST and, on such an
  arm, gates on the POSE against evidence.analyse.fused_sanity_m and
  PRINTS that it did. The ambiguity the paragraph above rejects the pose
  for does not exist there: this runs from `m5v3.sh start`, seconds after
  the spawn, before anything has commanded the truck.

THE WAIT IS BOUNDED, which is tools/noise_probe.sh's lesson: `ros2 topic
echo --once` waits for its message FOR EVER, so a filter that never
published at all would hang the bringup in silence instead of refusing
it. A read that times out is a refusal naming the topic.
"""
import math
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as core                          # noqa: E402

TOOL = "ekf_health"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id",
    "topics.odometry_filtered", "topics.fuse_odometry_filtered",
    "ekf.startup_check.covariance_max", "ekf.startup_check.timeout_s",
    "ekf.params_file", "paths.traction_file", "fuse.params_file",
    "evidence.analyse.fused_sanity_m",
)


def arm_topic(cfg):
    """Which topic to read, decided by the arm the running stack is on.

    A MISSING STATE FILE IS A REFUSAL AND NOT A DEFAULT, which is
    tools/sensor_evidence.py's `record` rule and it is here for a
    sharper version of the same reason. Guessing `topics.odometry_filtered`
    would, on the fuse arm, point this gate at a topic NOBODY IS
    PUBLISHING ON - and a topic with no publisher cannot diverge, so the
    gate would either time out (loud, and wrong about why) or, if
    somebody later made the timeout forgiving, pass a stack it never
    looked at.
    """
    path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(path):
        cfg.refuse(
            "the running stack says which estimator arm it is on", path,
            "paths.traction_file is not there. `m5v3.sh start` writes it "
            "on every",
            "bringup - before the estimator is spawned - and `stop` "
            "deletes it, so this",
            "stack was not started by m5v3.sh (or was stopped under this "
            "gate).",
            "THIS GATE CANNOT GUESS: the two arms publish on different "
            "topics, and a",
            "read of the wrong one is an empty stream rather than a "
            "wrong answer.")
    with open(path, "r", encoding="utf-8") as handle:
        arm = core.parse_state_file(handle.read()).get("arm", "")
    try:
        key = core.fused_topic_key(arm)
    except core.EvidenceError as exc:
        cfg.refuse("the state file names an estimator arm this gate can "
                   "read", path,
                   str(exc),
                   "the arm= line says: {!r}".format(arm),
                   "the mapping is tools/evidence_core.py's "
                   "fused_topic_key().")
    return cfg.s(key)


def read_once(cfg, topic):
    """One message off the active arm's output topic, as text, or a
    refusal.

    The isolation keys go on the environment for tools/
    sensor_evidence.py's reason: a tool an operator runs by hand
    inherits whatever shell they are in, which is domain 0 - a graph
    this stack has never published on.
    """
    env = dict(os.environ)
    env["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")
    env["GZ_PARTITION"] = cfg.s("isolation.gz_partition")
    timeout = cfg.f("ekf.startup_check.timeout_s")
    # RETRY UNTIL timeout_s, BECAUSE echo DOES NOT WAIT.
    # `ros2 topic echo --once` returns immediately with "does not appear
    # to be published yet / Could not determine the type" when discovery
    # has not yet matched the publisher - measured, and the refusal
    # below this function used to fire on that miss (once in eight
    # bringups in EVIDENCE_FUSION.md 11.5; again 2026-08-28). The 20 s
    # budget in config.yaml is a claim about waiting; without the loop
    # it is never spent. A real silence still refuses: subprocess
    # TimeoutExpired if a matched publisher never sends, or the loop
    # emptying if discovery never matches.
    deadline = time.monotonic() + timeout
    last = ""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            break
        try:
            done = subprocess.run(
                ["ros2", "topic", "echo", "--once", topic],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=remaining, env=env)
        except subprocess.TimeoutExpired:
            cfg.refuse(
                "the estimator published a message inside "
                "{:g}s".format(timeout),
                "{} (config.yaml ekf.startup_check.timeout_s)".format(topic),
                "nothing arrived on that topic at all. Both estimators on "
                "this track are SILENT",
                "about an input that never arrives, so the thing to check is "
                "the topic and",
                "not the log - and check that it is the ACTIVE arm's topic, "
                "which is the one",
                "the state file's arm= line decides:",
                "  ros2 topic list | grep {}".format(topic),
                "EVIDENCE_FUSION.md 2.6.")
        except OSError as exc:
            cfg.refuse("ros2 is on the PATH",
                       _common.CONFIG + " (paths.ros_setup)",
                       "could not run `ros2 topic echo`: {}".format(exc),
                       "this gate runs INSIDE WSL with /opt/ros/jazzy sourced.")
        last = done.stdout.decode("utf-8", "replace")
        if not core.echo_is_undiscovered(last):
            return last
        time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    cfg.refuse(
        "the estimator published a message inside "
        "{:g}s".format(timeout),
        "{} (config.yaml ekf.startup_check.timeout_s)".format(topic),
        "every `ros2 topic echo --once` in that window returned the "
        "immediate discovery miss rather than a message. Last output:",
        *[line for line in last.splitlines()[:4]] or ["(nothing at all)"],
        "EVIDENCE_FUSION.md 2.6.")


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    ceiling = cfg.f("ekf.startup_check.covariance_max")
    topic = arm_topic(cfg)
    text = read_once(cfg, topic)
    # AN ESTIMATOR THAT PUBLISHES NO COVARIANCE CANNOT BE GATED ON ONE,
    # AND THIS GATE SAYS SO RATHER THAN PASSING.
    # `fuse_models::Odometry2DPublisher` 1.1.5 fills the pose AND twist
    # covariances of every message it publishes with zeros - measured on
    # this rig with and without predict_to_current_time, with and without
    # covariance_throttle_period, and with nothing in its log
    # (EVIDENCE_FUSION.md 11.2). Against that matrix the check below
    # cannot fail: 0.0 is under every ceiling. A gate that cannot fail is
    # worse than no gate, because the line it prints is READ as an
    # answer.
    #   SO THE POSE IS ASKED INSTEAD, AND ONLY THEN. ekf_health's own
    #   docstring says the covariance and NOT the pose, deliberately,
    #   because a pose far from the origin is ambiguous - the truck could
    #   legitimately have been driven. That ambiguity does not exist on
    #   the branch below: this gate runs from `m5v3.sh start`, seconds
    #   after the truck was spawned and before anything has commanded it,
    #   so an estimate outside evidence.analyse.fused_sanity_m of its own
    #   origin has not drifted - it has broken. It is the same bound and
    #   the same arithmetic `analyse` refuses a diverged session's fused
    #   figures with (evidence_core.require_not_diverged), so the two
    #   instruments draw the line in the same place.
    #   THE ARM WITH A COVARIANCE IS UNTOUCHED BY THIS. On
    #   robot_localization's arm covariance_is_absent() is false, this
    #   branch is not taken, and the CHECK and the CEILING are what
    #   EVIDENCE_FUSION.md 9.4 and 10 measured.
    #     THE PRINTED LINE IS NOT CHARACTER FOR CHARACTER 9.4's, AND
    #     SAYING SO COST A CORRECTION. Both branches now append the
    #     topic - "  (/m5v3/odometry/filtered)" - because a gate that
    #     picks its topic by arm has to say which one it read, and a
    #     comment claiming the output was unchanged would have been the
    #     kind of stale line 9.3's own settings block was written to
    #     stop. The FIGURE and the ceiling either side of it are 9.4's;
    #     the suffix is new and 9.4 and 10.3 are annotated where they
    #     quote the old form.
    #   AND THE CLASSIFICATION ITSELF IS INSIDE A REFUSAL, because it
    #   can fail. covariance_is_absent() delegates its parse to
    #   worst_covariance(), which RAISES on a read with no covariance in
    #   it at all - and that read happens: `ros2 topic echo --once`
    #   returns immediately with "topic does not appear to be published
    #   yet / Could not determine the type" if it is asked before the
    #   publisher has been discovered, which is a race this gate runs
    #   inside by design (one second after the child was spawned).
    #   MEASURED: it lost that race once in eight bringups of
    #   EVIDENCE_FUSION.md 11.5's batch, and the first cut of this
    #   branch let the exception out as a TRACEBACK - which m5v3.sh then
    #   correctly refused the bringup on, but with the wrong message and
    #   over a stack that was in fact healthy.
    try:
        absent = core.covariance_is_absent(text)
    except core.EvidenceError as exc:
        cfg.refuse(
            "the read off {} carried a message to check".format(topic),
            "{} (config.yaml ekf.startup_check.timeout_s) and "
            "tools/evidence_core.py".format(topic),
            str(exc),
            "`ros2 topic echo --once` returns IMMEDIATELY, without "
            "waiting, when it",
            "cannot resolve the topic's type - which is what a publisher "
            "this gate asked",
            "about before discovery had finished looks like. What came "
            "back:",
            *[line for line in text.splitlines()[:4]] or ["(nothing at all)"],
            "THE STACK IS PROBABLY FINE. '{}' says whether every child "
            "is alive;".format("m5v3.sh status"),
            "stop and start again.")
    if absent:
        bound = cfg.f("evidence.analyse.fused_sanity_m")
        try:
            x, y = core.position_of(text)
            core.require_not_diverged(
                [x], [y], bound,
                "the estimator on {}, one message after bringup with the "
                "truck at spawn,".format(topic))
        except core.EvidenceError as exc:
            cfg.refuse(
                "the estimator came up without diverging",
                "{} (evidence.analyse.fused_sanity_m) and {}".format(
                    _common.CONFIG, cfg.s("fuse.params_file")),
                str(exc),
                "THIS ARM PUBLISHES NO COVARIANCE AT ALL - 36 zeros on "
                "the pose and 36 on",
                "the twist - so the covariance ceiling this gate uses on "
                "the other arm",
                "cannot fail here and the POSE is what was checked. "
                "EVIDENCE_FUSION.md 11.2.",
                "The message it published is above.",
                "NOTHING IS WRONG WITH THE PLANT - stop the stack and "
                "start it again.")
        print("  ekf: healthy, pose {:.6g} m from the odom origin against "
              "a bound of {:g}  ({})".format(
                  math.hypot(x, y), bound, topic))
        print("       THIS ARM PUBLISHES NO COVARIANCE (36 zeros, "
              "measured - EVIDENCE_FUSION.md 11.2),")
        print("       so the covariance ceiling was NOT the check. The "
              "pose was.")
        return 0
    try:
        worst = core.require_covariance_under(
            text, ceiling,
            "the estimator on {}, one message after bringup with the "
            "truck at spawn,".format(topic))
    except core.EvidenceError as exc:
        cfg.refuse(
            "the estimator came up without diverging",
            "{} (ekf.startup_check.covariance_max) and {}".format(
                _common.CONFIG, cfg.s("ekf.params_file")),
            str(exc),
            "the estimator reports NOTHING about this: it stays ALIVE and "
            "publishes at its",
            "configured rate, so every other check on this stack is "
            "green. The message",
            "it published is above.",
            "NOTHING IS WRONG WITH THE PLANT - stop the stack and start "
            "it again.")
    print("  ekf: healthy, worst covariance {:.6g} against a ceiling of "
          "{:g}  ({})".format(worst, ceiling, topic))
    return 0


if __name__ == "__main__":
    sys.exit(main())
