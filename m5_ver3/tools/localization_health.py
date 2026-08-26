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

---- SINCE F3 TASK 3 THERE ARE TWO LOCALISERS AND THIS GATE FOLLOWS THE
     STACK, WHICH IS THREE DIFFERENCES AND ONE CHECK ----

It reads the `loc=` line m5v3.sh wrote and asks tools/evidence_core.py
three questions about the arm it names - all three of them tables that
REFUSE an arm they have not heard of rather than defaulting to the other
one's answer, which is fused_topic_key()'s rule:

  WHERE IT PUBLISHES ITS OWN POSE. nav2_amcl says `amcl_pose`,
      slam_toolbox says `pose` (loc_pose_topic_key).
  HOW IT WAS TOLD WHERE IT IS. amcl by a MESSAGE this gate publishes,
      slam_toolbox by the `map_start_pose` PARAMETER on its own command
      line, read on the configure transition (loc_seed_mechanism).
      ON THAT ARM THIS GATE MUST NOT SEND ONE. That node subscribes the
      same initial-pose topic - it is how a running localiser is
      re-placed - so a seed here would move it to the pose this gate
      already believes and the check below would become a check on the
      gate.
  WHAT THERE IS TO READ AT REST, and this one was MEASURED
      (loc_gate_source, EVIDENCE_LOCALIZATION_V3.md 13.2).
      slam_toolbox's pose topic is TRAVEL-GATED - 0.25 m of
      minimum_travel_distance and nothing has commanded the vehicle - so
      with the truck at spawn it publishes nothing at all, for 30 s,
      with the node ACTIVE and the graph deserialised. What it does
      publish from the moment it activates is `map` -> `odom` on a 50 Hz
      timer, so on that arm the gate composes that edge onto the
      estimator's `odom` -> `base_link` and checks the pose it gets -
      which is what a consumer of this stack reads anyway.
      THE COST IS THE COVARIANCE CHECK AND IT IS PRINTED. A transform
      carries none, so on that arm only the pose-against-seed bound
      runs, and the gate says which check it ran rather than letting a
      log be read as a pass it never tested. (ekf_health.py makes the
      same statement on the --fuse arm for a different reason,
      EVIDENCE_FUSION.md 11.2c.)

What does NOT change is the question: is this a localiser, or a node
that is merely running. Everything below is written for the amcl arm
because that is the arm it was built on, and every word of it still
holds there.

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
broadcasts no transform at all - with the scanner's transform PRESENT
and not one message-filter drop, so it is the seed and not the geometry
that is missing. What it logs, every two seconds, is "AMCL cannot publish
a pose or update the transform. Please set the initial pose...". So the
first thing this localiser ever says is its answer to a seed this gate
can point at.

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
import map_register                                   # noqa: E402

TOOL = "localization_health"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id",
    "topics.amcl_pose", "topics.slam_pose", "topics.initialpose",
    "topics.tf",
    "frames.map", "frames.odom", "frames.base_link",
    "vehicle.spawn.x", "vehicle.spawn.y", "vehicle.spawn.yaw",
    "map.dir", "map.name", "map.registration.file",
    "paths.traction_file",
    "localization.amcl.label", "localization.amcl.params_file",
    "localization.slam.label", "localization.slam.params_file",
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
    # WHICH ARM, AND THE GATE FOLLOWS THE STACK RATHER THAN THE OTHER
    # WAY ROUND. Until F3 Task 3 this compared the label against a single
    # config key and refused a mismatch - which was right when there was
    # one localiser and would now be wrong: a gate that tested only one
    # arm would refuse the other for being itself. What it still refuses
    # is `none` and anything evidence_core has no entry for, and both are
    # the same failure the old check was for: a gate that timed out
    # against a topic nobody publishes would report a BROKEN localiser
    # where the truth is an ABSENT or an UNKNOWN one.
    arm = core.localizer_of(loc)
    if not arm:
        cfg.refuse("the running stack has a localiser on it at all", path,
                   "the loc= line says {!r}. This gate can only be "
                   "reached from".format(loc),
                   "`m5v3.sh start --localize`, so the two have gone out "
                   "of step - and a gate",
                   "run against an UNLOCALISED stack would wait out its "
                   "whole timeout on a",
                   "topic nobody publishes and report a broken localiser "
                   "where there is none.")
    # AND IT IS CHECKED TWICE, AGAINST TWO DIFFERENT OWNERS. config.yaml
    # names the arms `--localize` accepts; tools/evidence_core.py holds
    # what each of them implies. A label that is in one and not the other
    # is the two files having drifted apart, and it is worth a refusal
    # that says which of them has not heard of it.
    labels = [cfg.s("localization.amcl.label"),
              cfg.s("localization.slam.label")]
    if arm not in labels:
        cfg.refuse("the running stack's localiser is one config.yaml "
                   "names", "{} and {}".format(path, _common.CONFIG),
                   "the loc= line says {!r} and the arms under "
                   "localization: are {}.".format(
                       arm, ", ".join(repr(name) for name in labels)),
                   "A stack was brought up by a script that knows an arm "
                   "this config does not.")
    try:
        core.loc_pose_topic_key(arm)
    except core.EvidenceError as exc:
        cfg.refuse("the running stack's localiser is one this gate knows",
                   "{} and tools/evidence_core.py".format(path), str(exc))
    return loc, arm


#: WHY A POSE FAR FROM THE SEED MEANS SOMETHING DIFFERENT ON EACH ARM,
#: and they are here rather than at the call site because each is eight
#: lines and the branch that chooses between them is one.
_WHY_NEAR_SEED_MESSAGE = (
    "THIS IS THE CHECK THE COVARIANCE CANNOT MAKE. nav2_amcl's own "
    "untouched prior",
    "carries the same 0.25 m2 this gate seeds with, so a localiser that "
    "never heard",
    "the seed passes a covariance ceiling while sitting at the map "
    "origin. Its log",
    "says 'initialPoseReceived' and 'Setting pose' when it did hear one "
    "- read the",
    "localiser's log and look for both.",
    "stop the stack and start it again.")
_WHY_NEAR_SEED_PARAMETER = (
    "THIS IS THE ONLY CHECK ON THIS ARM AND IT IS THE ONE THAT MATTERS "
    "HERE.",
    "map_start_pose is read on the configure transition; with it missing "
    "or malformed",
    "the node logs 'Map starting pose not specified' or 'Incorrect "
    "number of arguments",
    "for map starting pose' and STARTS AT THE POSE GRAPH'S OWN ORIGIN, "
    "which is where",
    "the MAPPING drive began and not where this run does. It then "
    "publishes",
    "map -> odom out of that, looking exactly like a localiser. Read the "
    "localiser's",
    "log for 'Load From File' and for either of those two lines.",
    "stop the stack and start it again.")


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    loc, arm = running_localizer(cfg)
    # THE SEED IS map_register's ARITHMETIC AND NOT A SECOND COPY OF IT.
    # `m5v3.sh start --localize slam` reads the same function through
    # `map_register.py seed` to put map_start_pose on that node's command
    # line, so the pose a localiser is STARTED at and the pose this gate
    # compares its answer against cannot disagree.
    frame, seed = map_register.seed_pose(cfg)
    params_file = cfg.s("localization.{}.params_file".format(arm))

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

    # WHERE THIS ARM PUBLISHES ITS OWN POSE, AND HOW IT WAS TOLD WHERE
    # IT IS. Both are properties of the LOCALISER and both live in
    # tools/evidence_core.py, where a test reaches them without a
    # simulator - and both REFUSE an arm they have never heard of rather
    # than defaulting to the other one's answer.
    pose_topic = cfg.s(core.loc_pose_topic_key(arm))
    seed_topic = cfg.s("topics.initialpose")
    seeds_by_message = core.loc_seed_mechanism(arm) == "message"
    # AND WHAT THERE IS TO READ AT REST, WHICH IS NOT THE SAME ON THE TWO
    # ARMS AND WAS MEASURED RATHER THAN ASSUMED. See
    # evidence_core.loc_gate_source(): amcl publishes one pose per seed
    # and it carries a covariance, so both checks run on it;
    # slam_toolbox travel-gates its pose topic and publishes nothing with
    # the truck standing at spawn, but broadcasts map -> odom on a 50 Hz
    # timer from the moment it activates - so the gate composes THAT onto
    # the estimator edge and checks the pose it gets.
    reads_edge = core.loc_gate_source(arm) == "edge"
    map_frame = cfg.s("frames.map")
    odom_frame = cfg.s("frames.odom")
    base_frame = cfg.s("frames.base_link")
    timeout = cfg.f("localization.startup_check.timeout_s")
    reseed_s = cfg.f("localization.startup_check.reseed_s")

    rclpy.init(args=None)
    node = Node("m5v3_localization_health")
    #: What the checks below run on, as (x, y, yaw, covariance-or-None).
    #: ONE LIST FOR BOTH SOURCES, so everything past the read loop is one
    #: piece of code: the two arms differ in where the answer comes from
    #: and in whether a covariance came with it, and in nothing else.
    received = []
    if reads_edge:
        # THE TWO EDGES, OFF ONE SUBSCRIPTION. `map` -> `odom` is the
        # localiser's; `odom` -> `base_link` is the estimator's; the
        # composition is where the vehicle is. Nothing is appended until
        # BOTH have been seen, because a composition missing one of them
        # is not a partial answer, it is a different pose.
        from tf2_msgs.msg import TFMessage

        edges = {}

        def on_tf(msg):
            for transform in msg.transforms:
                key = (transform.header.frame_id, transform.child_frame_id)
                if key not in ((map_frame, odom_frame),
                               (odom_frame, base_frame)):
                    continue
                t = transform.transform.translation
                r = transform.transform.rotation
                edges[key] = (t.x, t.y, math.atan2(
                    2.0 * (r.w * r.z + r.x * r.y),
                    1.0 - 2.0 * (r.y * r.y + r.z * r.z)))
            if len(edges) == 2:
                x, y, yaw = core.compose_se2(
                    edges[(map_frame, odom_frame)],
                    edges[(odom_frame, base_frame)])
                received.append((x, y, yaw, None))

        node.create_subscription(TFMessage, cfg.s("topics.tf"), on_tf,
                                 QoSProfile(depth=50))
    else:
        def on_pose(msg):
            r = msg.pose.pose.orientation
            received.append((
                msg.pose.pose.position.x, msg.pose.pose.position.y,
                math.atan2(2.0 * (r.w * r.z + r.x * r.y),
                           1.0 - 2.0 * (r.y * r.y + r.z * r.z)),
                msg.pose.covariance))

        node.create_subscription(PoseWithCovarianceStamped, pose_topic,
                                 on_pose, QoSProfile(depth=10))
    # THE PUBLISHER EXISTS ON BOTH ARMS AND IS USED ON ONE, which is
    # cheaper than a branch around every line that touches it and is the
    # honest shape besides: what differs between the arms is whether a
    # seed is SENT, not whether this process could send one. On the
    # `parameter` arm nothing is ever published, and the printed line
    # below says so where an operator is reading.
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

    print("  loc: {} {} at map ({:+.4f}, {:+.4f}) yaw {:+.5f}".format(
        loc, "seeding" if seeds_by_message else "seeded (by parameter)",
        seed[0], seed[1], seed[2]))
    print("       = world ({:+.3f}, {:+.3f}) yaw {:+.5f} through the "
          "committed registration".format(
              cfg.f("vehicle.spawn.x"), cfg.f("vehicle.spawn.y"),
              cfg.f("vehicle.spawn.yaw")))
    if reads_edge:
        print("       reading {} -> {} off {}, composed onto the "
              "estimator's".format(map_frame, odom_frame,
                                   cfg.s("topics.tf")))
        print("       {} -> {}: this arm's {} is TRAVEL-GATED and "
              "publishes nothing".format(odom_frame, base_frame,
                                         pose_topic))
        print("       with the truck standing at spawn, and the edge is "
              "what a consumer reads.")
    if not seeds_by_message:
        print("       this arm was told where it is by map_start_pose on "
              "its own command")
        print("       line, on the CONFIGURE transition. This gate "
              "publishes NOTHING on {}:".format(seed_topic))
        print("       seeding it here would move the localiser to the "
              "pose this gate already")
        print("       believes, and the check below would then be a "
              "check on this gate.")

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
            # AND ON THE `parameter` ARM THERE IS NOTHING TO SEND, so
            # this loop is a bounded WAIT and nothing else. What it is
            # waiting for is the localiser's first answer, which on that
            # arm is its first PROCESSED SCAN - the travel gates in
            # slam.yaml never suppress the first one.
            if not seeds_by_message:
                continue
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
            if seeds_by_message:
                why = (
                    "{} seed(s) went out on {} and nothing came "
                    "back.".format(seeds, seed_topic),
                    "What a silent amcl means is one of:",
                    "  - it never received a scan it could transform. Its "
                    "log says 'Message Filter",
                    "    dropping message: frame ... queue is full' - the "
                    "base_link -> nav lidar",
                    "    static transform is missing (the `lasertf` "
                    "child).",
                    "  - it never received a map. map_server was "
                    "configured but not ACTIVATED,",
                    "    and amcl blocks in on_activate waiting for one.",
                    "  - it never received this seed, in which case its "
                    "log says 'AMCL cannot",
                    "    publish a pose or update the transform. Please "
                    "set the initial pose...'",
                    "    every two seconds.")
            else:
                why = (
                    "no seed was sent and none was wanted: this arm reads "
                    "map_start_pose on",
                    "its configure transition. What it has not done is "
                    "PROCESS A SCAN - it",
                    "publishes its pose on every processed one, and the "
                    "first is never",
                    "suppressed by the travel gates. So it means one of:",
                    "  - it never received a scan it could transform. Its "
                    "log says 'Message Filter",
                    "    dropping message: frame ... queue is full' - the "
                    "base_link -> nav lidar",
                    "    static transform is missing (the `lasertf` "
                    "child).",
                    "  - it could not look up base_link -> odom at the "
                    "scan's stamp, which it",
                    "    logs as 'Failed to compute odom pose' - the "
                    "estimator underneath is",
                    "    not publishing.",
                    "  - it deserialised no graph. That happens on the "
                    "CONFIGURE transition and",
                    "    its log says 'Load From File ...' when it did.")
            cfg.refuse(
                "the localiser answered inside {:g}s".format(timeout),
                "{} (config.yaml localization.startup_check.timeout_s) "
                "and {}".format(
                    "{} on {}".format(
                        "{} -> {}".format(map_frame, odom_frame),
                        cfg.s("topics.tf")) if reads_edge else pose_topic,
                    params_file),
                *(("NOTHING ABOUT THIS LOOKS WRONG FROM ANY OTHER ANGLE: "
                   "every localisation node",
                   "is ALIVE, every lifecycle transition returned "
                   "success, and the estimator",
                   "underneath is sane.")
                  + why
                  + ("read the localiser's log named above, then stop the "
                     "stack.",)))
        x, y, yaw, covariance = received[-1]
        # ---- THE COVARIANCE, AND ONLY WHERE THERE IS ONE ----
        #
        # A ZERO MATRIX IS ABSENT AND NOT CERTAIN, and a ceiling cannot
        # fail against it: 0.0 is under every ceiling, so a gate that did
        # not ask would print a pass it never tested. It is
        # tools/ekf_health.py's own problem on the `--fuse` arm
        # (EVIDENCE_FUSION.md 11.2c) one layer up, and it is answered the
        # same way - say which check ran, and gate on what is real.
        #   WHAT MAKES THE OTHER CHECK SUFFICIENT WHEN THIS ONE IS NOT.
        #   The pose-against-seed bound is arm-agnostic and it is the one
        #   that catches the failure that matters on either arm: a
        #   localiser that never learned where it was. The covariance
        #   catches a DIFFERENT failure - a filter that came up on a
        #   global prior - and that failure has no counterpart on an arm
        #   whose start pose is a parameter read before the graph is
        #   even open.
        ceiling = cfg.f("localization.startup_check.covariance_max")
        covariance_absent = (covariance is None
                             or core.covariance_absent_in(covariance))
        worst = 0.0 if covariance is None else core.worst_of(covariance)
        try:
            if not covariance_absent:
                worst = core.require_worst_under(
                    worst, ceiling,
                    "the localiser on {}, one message after its seed "
                    "with the truck at spawn,".format(pose_topic))
        except core.EvidenceError as exc:
            cfg.refuse(
                "the localiser came up with a bounded belief",
                "{} (localization.startup_check.covariance_max) and "
                "{}".format(_common.CONFIG, params_file),
                str(exc),
                "A COVARIANCE THAT SIZE IS A GLOBAL PRIOR AND NOT A "
                "TRACK. Over this 48 m",
                "hall a uniform belief has a variance of 48^2/12 = "
                "192 m2; the seed this",
                "gate published carries 0.25. The localiser reports "
                "nothing about the",
                "difference: it stays ALIVE and publishes map -> odom "
                "either way.",
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
                "{}".format(
                    _common.CONFIG,
                    seed_topic if seeds_by_message
                    else "map_start_pose on the localiser command line"),
                str(exc),
                *(_WHY_NEAR_SEED_MESSAGE if seeds_by_message
                  else _WHY_NEAR_SEED_PARAMETER))
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

    world = frame.to_world(x, y, yaw)
    # WHICH CHECKS ACTUALLY RAN IS PRINTED, NOT ASSUMED. A gate that
    # skipped its covariance check and said nothing would read, in a log
    # six weeks later, exactly like one that passed it.
    if covariance_absent and reads_edge:
        print("  loc: healthy, and THE COVARIANCE CHECK DID NOT RUN: "
              "what this arm publishes")
        print("       at rest is a TRANSFORM, and a transform carries no "
              "covariance. The bound")
        print("       below is the whole of the gate here, and this line "
              "is here so that a")
        print("       log six weeks old cannot be read as a check that "
              "passed.")
    elif covariance_absent:
        print("  loc: healthy, and THE COVARIANCE CHECK DID NOT RUN: {} "
              "published 36".format(pose_topic))
        print("       zeros, which is ABSENT and not CERTAIN - no ceiling "
              "can fail against it,")
        print("       so this gate says so rather than reporting a pass "
              "it never tested.")
    else:
        print("  loc: healthy, worst covariance {:.6g} against a ceiling "
              "of {:g}  ({})".format(worst, ceiling, pose_topic))
    print("       pose map ({:+.4f}, {:+.4f}) yaw {:+.5f} - {:.4f} m from "
          "the seed, bound {:g}".format(x, y, yaw, off, tolerance))
    print("       = world ({:+.3f}, {:+.3f}) yaw {:+.5f}. "
          "{}".format(world[0], world[1], world[2], frame.floor()))
    if seeds_by_message:
        print("       ONE seed, one answer. This arm TRACKS from a known "
              "start; it does not")
    else:
        print("       NO seed was sent; the answer is to map_start_pose. "
              "This arm TRACKS from")
        print("       a known start; it does not")
    print("       relocalise from nothing and no kidnapped-robot "
          "recovery is claimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
