#!/usr/bin/env python3
"""nav2_seed.py - one honest seed per truck, and the two gates behind it.

    python3 m6_ver2/nav2_adapter/nav2_seed.py --vid f1   # 0 healthy, 1 refused

A SEED YOU DID NOT READ BACK IS NOT A SEED. That is m5v3's G5 lesson and
it is the whole reason this file exists rather than a `ros2 topic pub`
in m6_ver2/truck.sh. Publishing a PoseWithCovarianceStamped is one line;
knowing that a localiser RECEIVED it, believed it, and answered near it
is four checks, and every one of them fails silently. nav2_amcl compares
`header.frame_id` against its own `global_frame_id` and IGNORES a pose in
any other frame with a single warning line; an AMCL that came up on a
GLOBAL PRIOR publishes `map` -> `<vid>/odom` exactly as confidently as a
localised one; and with the truck standing still it publishes exactly ONE
pose per seed, so a reader that arrived late waits for a second one that
never comes.

---- WHAT IT CHECKS, IN ORDER, AND WHY THE ORDER IS THE DESIGN ----

  1. THE FILTER IS STILL A FILTER. robot_localization's ekf_node can
     diverge in its first cycles - covariance to 1e84 in a single 20 ms
     step - and stay UP, at rate, saying nothing, so every other check
     here would be green over a filter that has stopped being one
     (m5_ver3 EVIDENCE_FUSION.md 8.6, 9). One message off
     topics.odometry_filtered, worst magnitude against
     ekf.startup_check.covariance_max.
  2. BOTH ENDS DISCOVERED. Subscribe the pose topic and wait until AMCL
     is subscribed to the seed topic AND publishing on the pose topic.
     A seed sent into an undiscovered graph is a seed nobody received,
     and the symptom is identical to a seed that was rejected.
  3. THE SEED, ONCE. vehicle.spawn is the truck's KNOWN TRUTH at boot -
     it is the pose m6_ver2/world.launch.py spawned the model at, out of
     the one table that holds it (status_contract.VEHICLES) - carried
     into the MAP frame through the committed registration.
  4. THE READ-BACK. AMCL's own first answer, checked against the
     covariance ceiling and against the seed's own position.

TWO GATES IN ONE PROCESS, AND THAT IS DELIBERATE. m5v3 runs
tools/ekf_health.py and tools/localization_health.py as two subprocesses
because the first can be a bare `ros2 topic echo`. Here the second has to
PUBLISH before it READS, so it needs a node either way - and a second
process would be a second discovery, a second wait and a second chance to
time out on a stack that is perfectly healthy.

NOTHING HERE IS RE-DERIVED. The world -> map transform is
evidence_core.MapFrame's, loaded through map_register.load_registration
so the md5 binding refuses a transform whose grid was rebuilt; the
covariance and pose bounds are evidence_core's; the config reader is
nav2_adapter_node.vehicle_config, so the seed and the node it gates
cannot read two different files. At warehouse_v3's -179.813 deg a
rotation is very nearly its own inverse, which is exactly why none of
this is spelled twice.
"""
import argparse
import math
import os
import sys
import time

import _donors                                            # noqa: F401

import evidence_core as core                              # noqa: E402
import nav2_pose                                          # noqa: E402
from nav2_adapter_node import own_args, vehicle_config    # noqa: E402
from status_contract import VEHICLES                      # noqa: E402

TOOL = "nav2_seed"

#: MAINTENANCE OBLIGATION, the same one every other reader on this track
#: carries: a key read below is a key listed here.
REQUIRED_KEYS = (
    "frames.map",
    "topics.initialpose", "topics.amcl_pose", "topics.odometry_filtered",
    "map.dir", "map.name", "map.registration.file",
    "localization.initial_pose.cov_x_m2",
    "localization.initial_pose.cov_y_m2",
    "localization.initial_pose.cov_yaw_rad2",
    "localization.startup_check.timeout_s",
    "localization.startup_check.covariance_max",
    "localization.startup_check.pose_tolerance_m",
    "localization.startup_check.reseed_s",
    "ekf.startup_check.covariance_max",
    "ekf.startup_check.timeout_s",
)

#: How long to wait for AMCL to discover this process and be discovered
#: by it, as a FRACTION of the localiser's own startup budget rather
#: than as a number of its own: a second constant here would be a second
#: opinion about how slow this graph is.
DISCOVERY_FRACTION = 0.5


def seed_in_map(cfg, vid):
    """`VEHICLES[vid].spawn` in the MAP frame, through the registration.

    THE POSE THE WORLD SPAWNED THE MODEL AT, AND NOT A SECOND SPELLING
    OF IT. m6_ver2/world.launch.py spawns from this same table and
    tools/instantiate_truck.py writes `vehicle.spawn` from it too, so
    all three agree by construction. map_register.seed_pose does exactly
    this for m5v3 off `vehicle.spawn`; here it takes the pose as an
    argument because there are four of them.
    """
    frame = nav2_pose.load_frame(os.path.join(
        _donors.REPO, cfg.s("map.dir"), cfg.s("map.name"),
        cfg.s("map.registration.file")))
    spawn = VEHICLES[vid]["spawn"]
    return frame, frame.to_map(float(spawn["x"]), float(spawn["y"]),
                               float(spawn["yaw"]))


def _selftest(vid):
    """Everything but the graph: the config, the registration, the pose.

    NO ROS AND NO SIMULATOR. What it cannot check is the only thing this
    tool exists for - whether a localiser answered - and it says so
    rather than printing a pass it never tested.
    """
    cfg = vehicle_config(vid, TOOL, REQUIRED_KEYS)
    frame, seed = seed_in_map(cfg, vid)
    spawn = VEHICLES[vid]["spawn"]
    fails = []
    print("nav2_seed selftest for {}".format(vid))
    print("  spawn  world ({}, {}) yaw {}".format(
        spawn["x"], spawn["y"], spawn["yaw"]))
    print("  seed   map ({:+.4f}, {:+.4f}) yaw {:+.5f}".format(*seed))
    print("  {}".format(nav2_pose.floor_sentence(frame)))
    back = nav2_pose.to_world(frame, seed[0], seed[1], seed[2])
    # THE HALF TURN, CHECKED. warehouse_v3's theta is -179.813 deg and a
    # rotation that near a half turn is very nearly its own inverse, so
    # a transform applied backwards leaves every MAGNITUDE exactly right
    # and puts the truck on the other side of the building. A round trip
    # is the cheapest thing that catches it.
    for name, got, want in (("x", back[0], float(spawn["x"])),
                            ("y", back[1], float(spawn["y"])),
                            ("yaw", math.cos(back[2] - float(spawn["yaw"])),
                             1.0)):
        if abs(got - want) > 1e-6:
            fails.append(name)
            print("  FAIL round trip {}: {!r} != {!r}".format(name, got, want))
    print("  pass  the registration round-trips the spawn")
    print("  gates this tool runs live: the filter's covariance "
          "(<= {}), the seed read-back (<= {}, within {} m)".format(
              cfg.s("ekf.startup_check.covariance_max"),
              cfg.s("localization.startup_check.covariance_max"),
              cfg.s("localization.startup_check.pose_tolerance_m")))
    print("  NOT CHECKED HERE: whether a localiser answered. That needs "
          "a graph, and it is what this tool is for.")
    print("{} problems".format(len(fails)))
    return 1 if fails else 0


def _wait(node, rclpy, deadline, ready):
    """Spin until `ready()` or the wall deadline. Returns ready()'s answer."""
    while time.monotonic() < deadline:
        if ready():
            return True
        rclpy.spin_once(node, timeout_sec=0.1)
    return ready()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description="seed this truck's AMCL from the pose the world "
                    "spawned it at, and refuse by name if it did not "
                    "answer near it.")
    parser.add_argument("--vid", required=True,
                        help="f1..f4 - m6/ipc/status_contract's own ids")
    parser.add_argument("--selftest", action="store_true",
                        help="the config, the registration and the "
                             "world<->map round trip. No ROS.")
    args = parser.parse_args(own_args(argv))
    if args.vid not in VEHICLES:
        parser.error("{!r} is not a fleet vehicle id: {}".format(
            args.vid, sorted(VEHICLES)))
    if args.selftest:
        return _selftest(args.vid)

    cfg = vehicle_config(args.vid, TOOL, REQUIRED_KEYS)
    frame, seed = seed_in_map(cfg, args.vid)
    try:
        import rclpy
        from geometry_msgs.msg import PoseWithCovarianceStamped
        from nav_msgs.msg import Odometry
        from rclpy.qos import QoSProfile
    except ImportError as exc:
        import _common
        _common.refuse(
            TOOL, "rclpy is importable",
            "{} (paths.ros_setup)".format(_common.CONFIG),
            "python3 could not import ROS 2: {}".format(exc),
            "this tool runs INSIDE WSL with /opt/ros/jazzy sourced -",
            "m6_ver2/truck.sh sources it before it runs this gate.")

    seed_topic = cfg.s("topics.initialpose")
    pose_topic = cfg.s("topics.amcl_pose")
    filtered_topic = cfg.s("topics.odometry_filtered")
    map_frame = cfg.s("frames.map")

    rclpy.init(args=sys.argv)
    node = rclpy.create_node("nav2_seed_" + args.vid)
    try:
        # ---------------- GATE 1: IS THE FILTER STILL A FILTER? -------
        filtered = []
        node.create_subscription(
            Odometry, filtered_topic,
            lambda msg: filtered.append(list(msg.pose.covariance)),
            QoSProfile(depth=10))
        budget = cfg.f("ekf.startup_check.timeout_s")
        if not _wait(node, rclpy, time.monotonic() + budget,
                     lambda: bool(filtered)):
            cfg.refuse(
                "the filter published inside {:.0f}s".format(budget),
                "{} (ekf.startup_check.timeout_s)".format(_common_config()),
                "nothing arrived on {}.".format(filtered_topic),
                "THE EKF IS THE ONLY PUBLISHER OF "
                "{} -> {} on this truck, and every".format(
                    cfg.s("frames.odom"), cfg.s("frames.base_link")),
                "costmap on it BLOCKS in canTransform() until that edge "
                "exists.",
                "read the ekf and odom logs under this truck's log dir.")
        ceiling = cfg.f("ekf.startup_check.covariance_max")
        try:
            worst = core.require_worst_under(
                core.worst_of(filtered[-1]), ceiling,
                "the filter on {}, with the truck at spawn,".format(
                    filtered_topic))
        except core.EvidenceError as exc:
            cfg.refuse(
                "the filter came up sane, and not merely alive",
                "{} (ekf.startup_check.covariance_max)".format(
                    _common_config()),
                str(exc),
                "robot_localization CAN DIVERGE IN ITS FIRST CYCLES and "
                "stay up, at rate,",
                "saying nothing - so every other check here would be "
                "green over a filter",
                "that has stopped being one.")
        print("  ekf: worst covariance {:.3g} against a ceiling of "
              "{:.3g}".format(worst, ceiling))

        # ------------- GATE 2: BOTH ENDS DISCOVERED, THEN SEED -------
        answers = []
        node.create_subscription(
            PoseWithCovarianceStamped, pose_topic,
            lambda msg: answers.append((
                msg.pose.pose.position.x, msg.pose.pose.position.y,
                2.0 * math.atan2(msg.pose.pose.orientation.z,
                                 msg.pose.pose.orientation.w),
                list(msg.pose.covariance))),
            QoSProfile(depth=10))
        publisher = node.create_publisher(
            PoseWithCovarianceStamped, seed_topic, QoSProfile(depth=1))
        budget = cfg.f("localization.startup_check.timeout_s")
        discovery = budget * DISCOVERY_FRACTION
        if not _wait(node, rclpy, time.monotonic() + discovery,
                     lambda: (publisher.get_subscription_count() > 0
                              and node.count_publishers(pose_topic) > 0)):
            cfg.refuse(
                "AMCL and this gate found each other inside "
                "{:.0f}s".format(discovery),
                "{} (localization.startup_check.timeout_s)".format(
                    _common_config()),
                "{} has {} subscriber(s) and {} has {} publisher(s).".format(
                    seed_topic, publisher.get_subscription_count(),
                    pose_topic, node.count_publishers(pose_topic)),
                "A SEED SENT INTO AN UNDISCOVERED GRAPH IS A SEED NOBODY "
                "RECEIVED, and from",
                "the outside that looks exactly like a seed that was "
                "rejected.",
                "IF THE COUNTS ARE ZERO the localiser is probably not "
                "namespaced: this",
                "truck's AMCL answers on {} and nowhere else.".format(
                    pose_topic))

        message = PoseWithCovarianceStamped()
        # THE FRAME IS THE ONE AMCL WILL ACCEPT AND NOTHING ELSE. It
        # compares header.frame_id against its own global_frame_id and
        # IGNORES a pose in any other frame, with one warning line and
        # no other effect - which looks exactly like a seed that was
        # never sent. It is the SHARED `map`, not a per-truck name.
        message.header.frame_id = map_frame
        # THE STAMP IS LEFT AT ZERO, DELIBERATELY, and m5v3 measured
        # why: AMCL uses it to look up the odometry between the stamp
        # and now, that lookup fails by a handful of milliseconds
        # whatever stamp is used, and it falls back to the identity -
        # which is the right answer here, because the truck has not
        # moved since it was spawned.
        message.pose.pose.position.x = seed[0]
        message.pose.pose.position.y = seed[1]
        message.pose.pose.orientation.z = math.sin(seed[2] / 2.0)
        message.pose.pose.orientation.w = math.cos(seed[2] / 2.0)
        covariance = [0.0] * 36
        covariance[0] = cfg.f("localization.initial_pose.cov_x_m2")
        covariance[7] = cfg.f("localization.initial_pose.cov_y_m2")
        covariance[35] = cfg.f("localization.initial_pose.cov_yaw_rad2")
        message.pose.covariance = covariance
        publisher.publish(message)
        print("  seed: {} at map ({:+.4f}, {:+.4f}) yaw {:+.5f}".format(
            seed_topic, *seed))
        print("        = world ({}, {}) yaw {} through the committed "
              "registration".format(VEHICLES[args.vid]["spawn"]["x"],
                                    VEHICLES[args.vid]["spawn"]["y"],
                                    VEHICLES[args.vid]["spawn"]["yaw"]))
        print("        {}".format(nav2_pose.floor_sentence(frame)))

        # ---------------- GATE 3: THE READ-BACK ----------------------
        # ONE RESEED, AND ONLY ONE. With the truck standing still AMCL
        # publishes exactly one pose per seed, so a seed that crossed a
        # discovery race produces silence rather than an error. A second
        # one is cheap and is not a weakening of the gate: what is
        # checked is unchanged and the budget is the same.
        reseed_s = cfg.f("localization.startup_check.reseed_s")
        deadline = time.monotonic() + budget
        if not _wait(node, rclpy, min(time.monotonic() + reseed_s, deadline),
                     lambda: bool(answers)):
            publisher.publish(message)
            print("  seed: no answer in {:.0f}s, re-seeded once".format(
                reseed_s))
        if not _wait(node, rclpy, deadline, lambda: bool(answers)):
            cfg.refuse(
                "the localiser answered its seed inside "
                "{:.0f}s".format(budget),
                "{} (localization.startup_check.timeout_s)".format(
                    _common_config()),
                "nothing arrived on {} after two seeds on {}.".format(
                    pose_topic, seed_topic),
                "WITH THE TRUCK STANDING STILL AMCL PUBLISHES EXACTLY "
                "ONE POSE PER SEED,",
                "so silence here is a seed that was not received or was "
                "not accepted -",
                "and it accepts a pose only in its own global_frame_id, "
                "which is '{}'.".format(map_frame),
                "read this truck's amcl log.")

        x, y, yaw, answer_cov = answers[-1]
        ceiling = cfg.f("localization.startup_check.covariance_max")
        absent = core.covariance_absent_in(answer_cov)
        if not absent:
            try:
                worst = core.require_worst_under(
                    core.worst_of(answer_cov), ceiling,
                    "the localiser on {}, one message after its seed "
                    "with the truck at spawn,".format(pose_topic))
            except core.EvidenceError as exc:
                cfg.refuse(
                    "the localiser came up with a bounded belief",
                    "{} (localization.startup_check.covariance_max)".format(
                        _common_config()),
                    str(exc),
                    "A COVARIANCE THAT SIZE IS A GLOBAL PRIOR AND NOT A "
                    "TRACK. Over this 48 m",
                    "hall a uniform belief has a variance of "
                    "48^2/12 = 192 m2; the seed this",
                    "gate published carries "
                    "{}.".format(cfg.s("localization.initial_pose.cov_x_m2")),
                    "stop this truck and start it again.")
            print("  amcl: worst covariance {:.3g} against a ceiling of "
                  "{:.3g}".format(worst, ceiling))
        else:
            # A ZERO MATRIX IS ABSENT AND NOT CERTAIN, and a ceiling
            # cannot fail against it. Say which check ran rather than
            # letting a log be read as a pass that was never tested.
            print("  amcl: NO COVARIANCE on that message (all zero), so "
                  "the ceiling check did not run")

        tolerance = cfg.f("localization.startup_check.pose_tolerance_m")
        try:
            off = core.require_pose_near(
                x, y, seed[0], seed[1], tolerance,
                "the localiser on {}".format(pose_topic))
        except core.EvidenceError as exc:
            cfg.refuse(
                "the localiser answered near the pose it was seeded with",
                "{} (localization.startup_check.pose_tolerance_m)".format(
                    _common_config()),
                str(exc),
                "THIS IS THE CHECK THE COVARIANCE CANNOT MAKE: a "
                "localiser that never",
                "received the seed reports a perfectly tight belief "
                "about the wrong place,",
                "and every goal this truck is then given is a goal in "
                "somebody else's aisle.",
                "IT IS ALSO WHERE A CROSS-WIRED TRUCK SHOWS UP. Four "
                "AMCLs seed on four",
                "topics; a seed that reached the wrong one answers "
                "7.00 m away, which is",
                "the spacing of the spawn row.")
        print("  amcl: answered {:.3f} m from its seed, against a "
              "tolerance of {:.2f} m".format(off, tolerance))
        print("{}: {} is seeded and localised.".format(TOOL, args.vid))
        return 0
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:                                 # pragma: no cover
            pass


def _common_config():
    """The config path the refusals name - this truck's, not the donor's.

    vehicle_config() rebound it; read back rather than re-derived so a
    refusal can never name a file this process did not open.
    """
    import _common
    return _common.CONFIG


if __name__ == "__main__":
    sys.exit(main())
