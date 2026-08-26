#!/usr/bin/env python3
"""localization_health.py - did the LOCALISER come up localised, or did
it come up merely alive?

    python3 m5_ver3/tools/localization_health.py   # exit 0 healthy, 1 refused

IT IS tools/ekf_health.py's ARGUMENT ONE LAYER UP, AND IT IS A SIBLING
RATHER THAN A BRANCH OF IT. That gate asks whether the ESTIMATOR is still
an estimator: it reads one message off the active arm's output topic and
refuses a covariance over a ceiling, because `robot_localization` can
diverge in its first cycles and stay ALIVE, at rate, saying nothing. This
one asks whether the LOCALISER knows where it is. The question is
different, the failure modes are different, and - decisively - the
MECHANISM is different: this gate has to PUBLISH before it can READ, and
ekf_health's one-shot `ros2 topic echo` subprocess cannot be made to do
both in the right order. What the two share is the arithmetic, and that
is in tools/evidence_core.py where a test reaches it without a simulator,
imported by both.

---- WHY IT HAS TO PUBLISH, AND WHY THE ORDER IS THE WHOLE DESIGN ----

nav2_amcl publishes on `amcl_pose` when the particle filter RESAMPLES, or
when publication is forced. With the truck standing at spawn it never
resamples: amcl.yaml's `update_min_d` is 0.25 m and nothing has commanded
the vehicle. What forces a publication is an initial pose - it clears
`pf_init_`, and the next scan publishes. So there is exactly ONE message
per seed, and a reader that subscribed after the seed was sent would wait
for a second one that never comes, hit its timeout, and refuse a stack
that is in fact perfectly healthy.

    subscribe, wait for BOTH ends to be discovered, seed, then read.

MEASURED ON THIS RIG, 2026-08-26, and it is why the seed is a message
rather than nav2's `set_initial_pose` parameter: with that parameter
false and no message, amcl processes no scan, publishes no pose and
broadcasts no transform at all - it logs "Waiting for the initial pose"
and nothing else. So the first thing this localiser ever says is its
answer to a seed this gate can point at.

---- THE SEED IS THE MEASUREMENT HARNESS AND IT IS LABELLED AS SUCH ----

What is published is `vehicle.spawn` - the pose m5v3.sh spawned the truck
at - carried into the map frame through the COMMITTED registration, which
is the same transform every absolute figure in
EVIDENCE_LOCALIZATION_V3.md passes through. On a real forklift there is
no world frame and no world->map transform; what there is is an operator
typing a pose into a screen, and that is exactly what this stands in for
(agv/forklift/launch/localization.launch.py makes the same split and
keeps the conversion out of the vehicle's own launch file).

A KIDNAPPED-ROBOT RECOVERY IS NOT CLAIMED ANYWHERE. amcl.yaml runs with
both recovery alphas at zero and this gate hands the filter its answer,
so this stack tracks from a known start and cannot find itself from
nothing. It is a known limitation and the evidence file records it.

---- WHAT IT CHECKS, AND WHY ONE CHECK WOULD NOT DO ----

  the COVARIANCE against localization.startup_check.covariance_max.
      A ceiling four times the seed's own largest entry and two hundred
      times under the variance of a uniform prior over this hall. It
      catches a filter that came up on a global prior.
  the POSE against the SEED, within
      localization.startup_check.pose_tolerance_m. This is the check the
      covariance CANNOT make: a localiser that never received the seed
      does not diverge - it answers from nav2's own untouched prior,
      which carries the same 0.25 m2, at the map origin. Only the
      distance to the seed can tell the two apart.

Both refuse by name and both print what they measured.

THE WAIT IS BOUNDED, which is tools/noise_probe.sh's lesson: a read that
waits for ever turns a localiser that never published into a bringup that
hangs in silence rather than one that refuses.
"""
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as core                          # noqa: E402
import map_core as mc                                 # noqa: E402
import map_register                                   # noqa: E402

TOOL = "localization_health"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id",
    "topics.amcl_pose", "topics.initialpose",
    "frames.map",
    "vehicle.spawn.x", "vehicle.spawn.y", "vehicle.spawn.yaw",
    "map.dir", "map.name", "map.registration.file",
    "paths.traction_file",
    "localization.label", "localization.params_file",
    "localization.initial_pose.cov_x_m2",
    "localization.initial_pose.cov_y_m2",
    "localization.initial_pose.cov_yaw_rad2",
    "localization.startup_check.timeout_s",
    "localization.startup_check.covariance_max",
    "localization.startup_check.pose_tolerance_m",
    "localization.startup_check.reseed_s",
)


def running_localizer(cfg):
    """Which absolute layer the running stack says it is on.

    A STACK THAT SAYS `none` IS A REFUSAL AND NOT A PASS, which is
    tools/ekf_health.py's arm rule applied to this axis. This gate can
    only ever be run from `m5v3.sh start --localize`, so a state file
    that says otherwise means the two have gone out of step - and the
    failure that would follow is the worst kind: a gate that timed out
    against a topic nobody publishes, reported as a broken localiser
    rather than as an absent one.
    """
    path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(path):
        cfg.refuse(
            "the running stack says which absolute layer it is on", path,
            "paths.traction_file is not there. `m5v3.sh start` writes it "
            "on every",
            "bringup - before the localiser is spawned - and `stop` "
            "deletes it, so this",
            "stack was not started by m5v3.sh (or was stopped under this "
            "gate).")
    with open(path, "r", encoding="utf-8") as handle:
        loc = core.parse_state_file(handle.read()).get("loc", "")
    if not loc:
        cfg.refuse("the state file names an absolute layer", path,
                   "it has no 'loc=' line. m5v3.sh has written one on "
                   "every bringup since",
                   "F3 Task 2 - `none` or `<localiser>@<map md5>` - so "
                   "this stack was brought",
                   "up by an older copy of that script, or the file is a "
                   "truncated write.")
    if loc.split("@", 1)[0] != cfg.s("localization.label"):
        cfg.refuse("the running stack is on the localiser this gate "
                   "tests", path,
                   "the loc= line says {!r} and this gate is "
                   "{!r}'s.".format(loc, cfg.s("localization.label")),
                   "A gate run against a stack that has no localiser on "
                   "it would time out",
                   "reading a topic nobody publishes, and report a "
                   "BROKEN localiser where",
                   "the truth is an ABSENT one.")
    return loc


def seed_pose(cfg):
    """vehicle.spawn, in the MAP frame, through the committed
    registration.

    THE REGISTRATION IS VERIFIED HERE TOO, and that is not a duplicate of
    the bringup's md5 check - it is the other half of it.
    `m5v3.sh` hashes the .pgm and the .yaml against the registration
    before it starts anything; map_register.load_registration() hashes
    the .pgm against the registration again at the moment the transform
    is USED. The first says nothing was started against a stale map; the
    second says no NUMBER was produced through one. F3 constraint 16 is
    both.
    """
    path = os.path.join(_common.REPO, cfg.s("map.dir"), cfg.s("map.name"),
                        cfg.s("map.registration.file"))
    try:
        record = map_register.load_registration(path)
        frame = core.MapFrame.from_registration(record)
    except (mc.MapError, core.EvidenceError) as exc:
        cfg.refuse("the committed registration belongs to the grid on "
                   "disk", path, str(exc))
    return frame, frame.to_map(cfg.f("vehicle.spawn.x"),
                               cfg.f("vehicle.spawn.y"),
                               cfg.f("vehicle.spawn.yaw"))


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    loc = running_localizer(cfg)
    frame, seed = seed_pose(cfg)

    # THE ISOLATION GOES ON THE ENVIRONMENT BEFORE rclpy.init(), which is
    # tools/sensor_evidence.py's rule and it is here for its reason: a
    # tool an operator runs by hand inherits whatever shell they are in,
    # and that is domain 0 - a graph this stack has never published on.
    os.environ["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")
    os.environ["GZ_PARTITION"] = cfg.s("isolation.gz_partition")
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from geometry_msgs.msg import PoseWithCovarianceStamped
    except ImportError as exc:
        _common.refuse(
            TOOL, "rclpy is importable", _common.CONFIG + " (paths.ros_setup)",
            "python3 could not import ROS 2: {}".format(exc),
            "this gate runs INSIDE WSL with /opt/ros/jazzy sourced - "
            "`m5v3.sh start` sources it before it runs this.")

    pose_topic = cfg.s("topics.amcl_pose")
    seed_topic = cfg.s("topics.initialpose")
    timeout = cfg.f("localization.startup_check.timeout_s")
    reseed_s = cfg.f("localization.startup_check.reseed_s")

    rclpy.init(args=None)
    node = Node("m5v3_localization_health")
    received = []
    node.create_subscription(PoseWithCovarianceStamped, pose_topic,
                             received.append, QoSProfile(depth=10))
    publisher = node.create_publisher(PoseWithCovarianceStamped, seed_topic,
                                      QoSProfile(depth=1))

    message = PoseWithCovarianceStamped()
    # THE FRAME IS THE ONE amcl WILL ACCEPT AND NOTHING ELSE. nav2_amcl
    # compares header.frame_id against its own global_frame_id and
    # IGNORES a pose in any other frame, with one warning line and no
    # other effect - which would look exactly like a seed that was never
    # sent.
    message.header.frame_id = cfg.s("frames.map")
    # THE STAMP IS LEFT AT ZERO, DELIBERATELY, AND THE CONSEQUENCE IS
    # MEASURED. amcl uses it to look up the odometry between the stamp
    # and now, so that a pose sent from the past can be brought forward;
    # on this stack that lookup FAILS by a handful of milliseconds
    # whatever stamp is used, because amcl's own now() runs ahead of the
    # last transform a 50 Hz publisher put on the graph ("Failed to
    # transform initial pose in time ... Requested time 271.702000 but
    # the latest data is at time 271.694000"). It falls back to the
    # identity, which is the RIGHT answer here: the truck has not moved
    # since it was spawned, so there is no intervening odometry to
    # integrate. A clock this gate does not have cannot make that better
    # and could make it worse.
    message.pose.pose.position.x = seed[0]
    message.pose.pose.position.y = seed[1]
    message.pose.pose.orientation.z = math.sin(seed[2] / 2.0)
    message.pose.pose.orientation.w = math.cos(seed[2] / 2.0)
    covariance = [0.0] * 36
    covariance[0] = cfg.f("localization.initial_pose.cov_x_m2")
    covariance[7] = cfg.f("localization.initial_pose.cov_y_m2")
    covariance[35] = cfg.f("localization.initial_pose.cov_yaw_rad2")
    message.pose.covariance = covariance

    print("  loc: {} seeding at map ({:+.4f}, {:+.4f}) yaw {:+.5f}".format(
        loc, seed[0], seed[1], seed[2]))
    print("       = world ({:+.3f}, {:+.3f}) yaw {:+.5f} through the "
          "committed registration".format(
              cfg.f("vehicle.spawn.x"), cfg.f("vehicle.spawn.y"),
              cfg.f("vehicle.spawn.yaw")))

    deadline = time.time() + timeout
    seeds = 0
    last_seed = 0.0
    try:
        while time.time() < deadline and not received:
            rclpy.spin_once(node, timeout_sec=0.1)
            if received:
                break
            # BOTH ENDS DISCOVERED BEFORE THE SEED IS SENT, AND THAT IS
            # WHAT MAKES THE ORDER RELIABLE RATHER THAN LUCKY. The
            # subscription count says amcl is listening on
            # topics.initialpose; the publisher count says amcl is
            # advertising the pose topic and this node has found it. Sent
            # before either, the seed is dropped by a transport that has
            # nowhere to put it, or answered by a publication this node
            # is not yet connected to receive.
            ready = (publisher.get_subscription_count() >= 1
                     and node.count_publishers(pose_topic) >= 1)
            if not ready:
                continue
            if seeds and (time.time() - last_seed) < reseed_s:
                continue
            publisher.publish(message)
            last_seed = time.time()
            seeds += 1
            if seeds > 1:
                print("       re-seeded ({} sent): nothing had arrived on "
                      "{} after {:g}s".format(seeds, pose_topic, reseed_s))
        if not received:
            cfg.refuse(
                "the localiser answered inside {:g}s".format(timeout),
                "{} (config.yaml localization.startup_check.timeout_s) "
                "and {}".format(pose_topic,
                                cfg.s("localization.params_file")),
                "{} seed(s) went out on {} and nothing came back.".format(
                    seeds, seed_topic),
                "NOTHING ABOUT THIS LOOKS WRONG FROM ANY OTHER ANGLE: "
                "both nodes are ALIVE,",
                "both lifecycle transitions returned success, and the "
                "estimator underneath",
                "is sane. What a silent amcl means is one of:",
                "  - it never received a scan it could transform. Its log "
                "says 'Message Filter",
                "    dropping message: frame ... queue is full' - the "
                "base_link -> nav lidar",
                "    static transform is missing (the `lasertf` child).",
                "  - it never received a map. map_server was configured "
                "but not ACTIVATED,",
                "    and amcl blocks in on_activate waiting for one.",
                "  - it never received this seed, in which case its log "
                "says 'Waiting for the",
                "    initial pose' every two seconds.",
                "read the amcl log named above, then stop the stack.")
        latest = received[-1]
        quaternion = latest.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (quaternion.w * quaternion.z
                   + quaternion.x * quaternion.y),
            1.0 - 2.0 * (quaternion.y * quaternion.y
                         + quaternion.z * quaternion.z))
        x = latest.pose.pose.position.x
        y = latest.pose.pose.position.y
        ceiling = cfg.f("localization.startup_check.covariance_max")
        try:
            worst = core.require_worst_under(
                core.worst_of(latest.pose.covariance), ceiling,
                "the localiser on {}, one message after its seed with "
                "the truck at spawn,".format(pose_topic))
        except core.EvidenceError as exc:
            cfg.refuse(
                "the localiser came up with a bounded belief",
                "{} (localization.startup_check.covariance_max) and "
                "{}".format(_common.CONFIG,
                            cfg.s("localization.params_file")),
                str(exc),
                "A COVARIANCE THAT SIZE IS A GLOBAL PRIOR AND NOT A "
                "TRACK. Over this 48 m",
                "hall a uniform belief has a variance of 48^2/12 = "
                "192 m2; the seed this",
                "gate published carries 0.25. amcl reports nothing about "
                "the difference:",
                "it stays ALIVE and publishes map -> odom either way.",
                "stop the stack and start it again.")
        tolerance = cfg.f("localization.startup_check.pose_tolerance_m")
        try:
            off = core.require_pose_near(
                x, y, seed[0], seed[1], tolerance,
                "the localiser on {}".format(pose_topic))
        except core.EvidenceError as exc:
            cfg.refuse(
                "the localiser answered near the pose it was seeded with",
                "{} (localization.startup_check.pose_tolerance_m) and "
                "{}".format(_common.CONFIG, seed_topic),
                str(exc),
                "THIS IS THE CHECK THE COVARIANCE CANNOT MAKE. nav2_amcl's "
                "own untouched",
                "prior carries the same 0.25 m2 this gate seeds with, so a "
                "localiser that",
                "never heard the seed passes a covariance ceiling while "
                "sitting at the map",
                "origin. Its log says 'initialPoseReceived' and 'Setting "
                "pose' when it did",
                "hear one - read {} and look for both.".format(
                    "amcl.log"),
                "stop the stack and start it again.")
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

    world = frame.to_world(x, y, yaw)
    print("  loc: healthy, worst covariance {:.6g} against a ceiling of "
          "{:g}  ({})".format(worst, ceiling, pose_topic))
    print("       pose map ({:+.4f}, {:+.4f}) yaw {:+.5f} - {:.4f} m from "
          "the seed, bound {:g}".format(x, y, yaw, off, tolerance))
    print("       = world ({:+.3f}, {:+.3f}) yaw {:+.5f}. "
          "{}".format(world[0], world[1], world[2], frame.floor()))
    print("       ONE seed, one answer. This arm TRACKS from a known "
          "start; it does not")
    print("       relocalise from nothing and no kidnapped-robot "
          "recovery is claimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
