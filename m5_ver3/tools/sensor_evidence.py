#!/usr/bin/env python3
"""sensor_evidence.py - what this plant's sensors actually deliver, and
what its own estimates of its motion are worth. F1 Task 4's instrument,
extended by F2 Task 1 to score the SECOND estimate beside the first.

THREE STREAMS, ONE RUN, ONE TRUTH. The ground truth
(/forklift/gz/odom, an instrument and never an input), the raw wheel
odometry (/m5v3/wheel_odom) and the EKF that fuses it with the IMU
(/m5v3/odometry/filtered) are captured together, scored against the same
transformed truth by the same function, and then subtracted from each
other - so "how much of the raw estimate's error did fusing remove" is
answered inside one session and never by comparing two runs. The
subtraction is evidence_core.compare_drift() and it is tested there.
EVIDENCE_FUSION.md is what it produces; EVIDENCE_SENSORS.md is what the
one-estimate version produced and its sessions still read, with the
missing third stream NAMED rather than skipped.

    source /opt/ros/jazzy/setup.bash               # record only
    python3 m5_ver3/tools/sensor_evidence.py record --static
    python3 m5_ver3/tools/sensor_evidence.py record --drive straight
    python3 m5_ver3/tools/sensor_evidence.py analyse            # NO ROS

TWO HALVES, AND THEY ARE DELIBERATELY NOT THE SAME PROGRAM.

  record   attaches to a plant m5v3.sh started, subscribes what the
           bridge carries, and writes one headered CSV per stream under
           config.yaml's evidence.dir. `--drive PROFILE` starts
           tools/drive_route.py ITSELF, so one command produces one
           complete run: a recording opened by hand a second after the
           drive began is a recording with the reference pose missing
           from it, and the reference pose is what every drift figure in
           EVIDENCE_SENSORS.md is measured from.
           SINCE F2 TASK 2 IT ALSO STAMPS THE PLANT. `m5v3.sh start
           --slippery` brings up a truck with a different floor under it
           from the SAME committed model, so `record` reads
           paths.traction_file - the state file that bringup writes -
           into every session it produces and REFUSES if it is not
           there. An unlabelled session cannot be told from a nominal
           one afterwards, and that is the one failure this instrument
           has no way to catch later.
  analyse  reads those CSVs and prints the tables. IT IMPORTS NO ROS AND
           CALLS NO GAZEBO. It runs on the owner's Windows python, on a
           WSL shell with nothing sourced, and on a machine that has
           never had either - because a figure that can only be
           recomputed on the rig that produced it is a figure nobody can
           check. The rclpy import lives inside record()'s own body for
           exactly that reason (nodes/wheel_odometry.py does the same).

THE ARITHMETIC IS NOT IN THIS FILE. Every statistic, every transform and
every ratio is tools/evidence_core.py, where tests/test_evidence_core.py
reaches it without a simulator. What is here is subscriptions, CSV
writing, subprocess handling, bounded waits and printing - the parts a
test cannot reach and a rig run can.

THE CONFIGURED COLUMN COMES OUT OF THE MODEL, NOT OUT OF config.yaml.
model.sdf governs every sensor and config.yaml's sensors: block says so
in its own header; it repeats the update rates only because a SHELL
cannot read XML. This is a python program, so it reads the stddev, the
bias, the rate and the range straight out of vehicle.model - and prints a
warning when config.yaml's copy of a rate disagrees with the file that
decides it, which is the diff EVIDENCE_MODEL_V3.md used to do by hand.

EVERY WAIT IS BOUNDED AND A CAPTURE THAT CANNOT COMPLETE REFUSES.
`gz topic -e -n N` waits for its N messages FOR EVER and a ROS
subscription to a topic nobody publishes waits just as long, so a
misspelt topic or a bridge that did not come up would hang this in
silence rather than refuse it - which is tools/noise_probe.sh's lesson,
measured there by hanging the probe. Every phase here carries a deadline
from config.yaml and names what did not arrive.

IT ATTACHES, IT DOES NOT START A PLANT. m5v3.sh owns bringup; this
attaches to whatever is up in this partition, exactly as rtf_probe.sh,
noise_probe.sh, slip_bench.sh and drive_route.py do. THE PARTITION IS
WHAT MAKES IT MEASURE THE RIGHT TRUCK: a concurrent m6 stack carries
topics of exactly the same name, and gz transport is not DDS.

WHAT IT DOES NOT MEASURE. The real-time factor: tools/rtf_probe.sh is
that instrument and a second one would be a second opinion about one
number. The quantization residual and the per-run lidar bias draw:
tools/noise_probe.sh and EVIDENCE_MODEL_V3.md 5.2-5.3 own those, and
this file's evidence cites them rather than re-deriving them.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import math
import os
import signal
import struct
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as core                          # noqa: E402
# F3 TASK 2's TWO, AND NEITHER OF THEM IMPORTS ROS EITHER. `analyse` has
# to carry a map-frame pose into the building, and the transform that
# does it - with the md5 gate that binds it to one grid - lives in
# map_register/map_core. They read a .pgm, a .yaml and a text file and
# nothing else, so the `analyse` half still runs on the owner's Windows
# python with nothing sourced, which is the property that makes these
# figures checkable off the rig.
import map_core                                       # noqa: E402
import map_register                                   # noqa: E402

TOOL = "sensor_evidence"

# MAINTENANCE OBLIGATION: a key read below is a key listed here. Refused
# by its DOTTED name before a single subscription is made or a single CSV
# is opened.
REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id", "paths.ros_setup",
    "topics.clock", "topics.odom_ground_truth", "topics.scan_nav",
    "topics.imu", "topics.cam_depth", "topics.cam_info",
    "topics.joint_state", "topics.drive_speed_read_a", "topics.wheel_odom",
    "topics.odometry_filtered", "topics.rf2o_odom",
    "topics.fuse_odometry_filtered",
    "topics.safety_scan_back", "topics.points3d",
    # F3 TASK 1's TWO, AND THEY ARE NOT SUBSCRIBED BY THIS PROCESS AT
    # ALL - `record --bag` hands them to `ros2 bag record` on its command
    # line. Listed here anyway, by the obligation above: a key this file
    # READS is a key this tuple names, and where the read lands is not
    # what the obligation is about.
    "topics.tf", "topics.tf_static",
    # F3 TASK 2's, AND topics.tf IS NOW READ BY THIS PROCESS RATHER THAN
    # ONLY HANDED TO `ros2 bag record`: the localiser's edge is captured
    # off /tf by a subscription of this recorder's own.
    "topics.amcl_pose", "topics.initialpose", "topics.map",
    "frames.map",
    "map.dir", "map.name", "map.registration.file",
    # F3 TASK 3's, AND EVERY ONE OF THEM IS THERE BECAUSE THERE ARE TWO
    # LOCALISERS NOW. topics.slam_pose is where the second one publishes
    # its own pose (nav2_amcl says `amcl_pose`, slam_toolbox says
    # `pose`), map.build_file is where the POSE GRAPH's md5 is committed
    # - the registration carries the grid's and nothing else - and each
    # arm names its own parameter file, which `analyse` prints so a
    # reader can open the file that decided the numbers.
    "topics.slam_pose", "map.build_file",
    "localization.amcl.label", "localization.amcl.params_file",
    "localization.slam.label", "localization.slam.params_file",
    "localization.analyse.map_gap_s",
    "frames.odom", "frames.base_link", "frames.imu",
    "vehicle.imu_mount.x", "vehicle.imu_mount.y", "vehicle.imu_mount.z",
    "ekf.frequency_hz", "ekf.params_file", "fuse.params_file",
    # ekf.rf2o_params_file IS READ BY analyse's settings block and was
    # listed by NEITHER tuple until F2 Task 4's second audit. It is the
    # item T3's report ledgered, and the first audit MISSED IT INSIDE
    # THE FILE IT WAS AUDITING - the sweep matched cfg.f()/cfg.s() calls
    # and this one is inside a .format() argument on a continuation
    # line, so a regex that stopped at the call boundary never saw it.
    # A sweep is not a proof; what makes this tuple right is that every
    # key is refused by its DOTTED name before a subscription is made.
    "ekf.rf2o_params_file",
    "world.file", "vehicle.model", "vehicle.name",
    "vehicle.spawn.x", "vehicle.spawn.y", "vehicle.spawn.yaw",
    "vehicle.wheelbase_m", "vehicle.wheel_radius_m",
    "vehicle.rear_axle_offset_m",
    "wheel_odom.drive_joint_name", "wheel_odom.steer_joint_name",
    "wheel_odom.counts_per_rev", "wheel_odom.wheel_radius_scale",
    "wheel_odom.steer_bias_rad",
    "drive_route.profiles",
    "paths.traction_file",
    "evidence.dir", "evidence.wait_first_s", "evidence.min_samples",
    "evidence.qos_depth", "evidence.static.record_s",
    "evidence.drive.pre_roll_s", "evidence.drive.post_roll_s",
    "evidence.drive.timeout_factor", "evidence.drive.timeout_margin_s",
    "evidence.depth.patch_half",
    "evidence.safety.frames", "evidence.safety.capture_timeout_s",
    "evidence.gz_rate.topics", "evidence.gz_rate.sample_s",
    "evidence.gz_rate.timeout_s",
    "evidence.bag.topics", "evidence.bag.dir", "evidence.bag.storage",
    "evidence.bag.start_timeout_s", "evidence.bag.stop_timeout_s",
    "evidence.analyse.fused_sanity_m",
    "evidence.analyse.spawn_tolerance_m",
    "evidence.analyse.spawn_tolerance_rad",
    "evidence.analyse.max_pair_gap_s", "evidence.analyse.noise_factor",
    "evidence.analyse.clamp_tolerance_m",
    "evidence.corner.profile",
    "evidence.corner.settle_s", "evidence.corner.window_s",
    "evidence.corner.bin_s",
    "evidence.corner.steer_tol_rad", "evidence.corner.speed_min_mps",
    # THESE THREE WERE READ AND NOT LISTED until F2 Task 4 audited this
    # tuple against the cfg.f()/cfg.s() calls in this file. They are the
    # per-corner window's trims and the scrub-split predicate, read at
    # print_scrub_split() and print_corner_table(); a config.yaml that
    # parses but has lost one of them would have reached those calls and
    # died on _common's KeyError rather than being refused by its DOTTED
    # name at load, which is what the obligation above exists for.
    "evidence.corner.slew_in_s", "evidence.corner.exit_s",
    "evidence.corner.split_min_deficit",
    "sensors.nav_lidar.rate_hz", "sensors.safety_scanner.rate_hz",
    "sensors.lidar_3d.rate_hz", "sensors.imu.rate_hz",
    "sensors.pallet_cam.rate_hz",
    "evidence.sdf_names.nav_lidar", "evidence.sdf_names.safety_scanner",
    "evidence.sdf_names.pallet_cam", "evidence.sdf_names.imu",
    "evidence.sdf_names.lidar_3d",
)

#: The CSV a stream lands in, by stream name. Named here rather than
#: spelled at each call site so record and analyse cannot disagree about
#: where a capture went - they are two halves of one program and the file
#: names are the only thing they share besides config.yaml.
FILES = {
    "clock": "clock.csv",
    "odom_truth": "odom_truth.csv",
    "wheel_odom": "wheel_odom.csv",
    # F2 TASK 1's THIRD STREAM. The EKF's own output, recorded beside the
    # raw estimate it is built from and the truth both are scored
    # against, so one session answers "how much did fusing buy" without
    # comparing two runs.
    "ekf_odom": "ekf_odom.csv",
    # F2 TASK 3's STREAM, AND IT IS THERE ONLY ON THE rf2o ARM. What is
    # recorded is the RELAY's output - the twist the filter actually
    # fused, lever arm corrected, covariance attached - and not
    # rf2o's raw topic, because the raw one has exactly one consumer and
    # the corrected one is exactly `vx_raw + vyaw * mount_y`, so a
    # reader who wants the raw number has it by arithmetic rather than
    # by a second CSV that could disagree with the first.
    "rf2o_odom": "rf2o_odom.csv",
    # F3 TASK 2's TWO, AND THEY ARE THERE ONLY ON THE LOCALISED ARM.
    # `map_odom` is the localiser's own edge - `map` -> `odom` as it
    # broadcasts it, once per scan - and `amcl_pose` is what the particle
    # filter believes about the vehicle, with its covariance, published
    # only when the filter UPDATES.
    #   THE TWO ARE NOT ONE STREAM WITH TWO RATES. The edge is what a
    #   consumer of this stack reads and what the absolute score is
    #   composed from; the pose is what the localiser SAYS, and its
    #   cadence and its covariance are figures of their own. A recorder
    #   that kept only one of them could answer only half of
    #   EVIDENCE_LOCALIZATION_V3.md.
    "amcl_pose": "amcl_pose.csv",
    "map_odom": "map_odom.csv",
    "scan_nav": "scan_nav.csv",
    "imu": "imu.csv",
    "depth": "depth.csv",
    "cam_info": "cam_info.csv",
    "joint_state": "joint_state.csv",
    "drive_read_a": "drive_read_a.csv",
    "safety_scan_back": "safety_scan_back.csv",
    "gz_rates": "gz_rates.csv",
    "session": "session.txt",
}
#: THE ROSBAG IS NOT IN THAT TABLE and its absence is deliberate. Every
#: entry above is a FILE this program opens and writes rows into; the bag
#: is a DIRECTORY `ros2 bag record` owns from the outside, its name is
#: config.yaml's (evidence.bag.dir) because tools/build_map.sh has to
#: read it too, and putting a directory in a table of CSV names would
#: make `FILES[x]` mean two things.


def fail(cfg, exc, owner):
    """An EvidenceError, refused in the one voice logs/ already carries.

    evidence_core has no voice of its own on purpose - it is arithmetic -
    so every refusal that starts there is named here, with the file that
    owns the answer it tested against.
    """
    cfg.refuse(str(exc), owner)


# ----------------------------------------------------------------------
# the session on disk
# ----------------------------------------------------------------------

def session_root(cfg):
    return os.path.join(_common.REPO, cfg.s("evidence.dir"))


def new_session(cfg, kind, name):
    """One directory per run, named for what it is and when it was taken.

    THE NAME IS THE PROVENANCE. A directory called
    drive-corner_creep-20260825-231145 says which profile, on which day,
    at which minute - so a table cell can name the run that produced it
    and somebody can go and look at the CSV.
    """
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(session_root(cfg),
                        "{}-{}-{}".format(kind, name, stamp))
    os.makedirs(path)
    return path


#: What a session says about a plant that was recorded before F2 Task 2
#: existed to label it. Those runs are all nominal - `--slippery` had not
#: been written - but this file will NOT write "nominal" over a blank,
#: because the whole point of the label is that it was READ off the plant
#: and not inferred. A reader gets the honest answer and the reason.
UNLABELLED = "unrecorded (session predates F2 Task 2's traction label)"


def read_traction(cfg):
    """Which plant is up, read off the state file m5v3.sh wrote.

    THE LABEL COMES FROM THE THING THAT SET THE PLANT, and this is the
    whole of that chain: `m5v3.sh start` decides the traction, writes it
    to paths.traction_file, and `record` copies it into the session it is
    about to write. Nothing here asks the simulator, and nothing here
    guesses.

    A MISSING FILE IS A REFUSAL AND NOT A DEFAULT. After F2 Task 2 the
    same `start` brings up two different plants, and a session recorded
    without a label is not a session with a gap in it - it is a row that
    will sit in the no-slip tables looking exactly like one of them. The
    file is written by EVERY start, nominal runs included, and deleted by
    stop, so its absence means this stack was not brought up by m5v3.sh -
    which is a thing the operator has to know before they measure it.
    """
    path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(path):
        cfg.refuse(
            "the running stack says which traction it is on", path,
            "paths.traction_file is not there. `m5v3.sh start` writes it "
            "on every",
            "bringup - nominal and --slippery alike - and `stop` deletes "
            "it, so this",
            "stack was not started by m5v3.sh (or was stopped under this "
            "recorder).",
            "RECORDING WITHOUT IT IS NOT ALLOWED: an unlabelled session "
            "cannot be told",
            "apart from a nominal one afterwards, and EVIDENCE_FUSION.md "
            "8 is a table",
            "of two plants. Bring the stack up with "
            "'bash m5_ver3/m5v3.sh start --headless'.")
    fields = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                fields[key] = value
    if not fields.get("traction"):
        cfg.refuse("the traction state file names a traction", path,
                   "it has no 'traction=' line. It is written whole by "
                   "m5v3.sh's",
                   "write_traction(); a file without that key is a "
                   "truncated write.")
    # AND THE ESTIMATOR ARM, BY THE SAME RULE AND FOR THE SAME REASON
    # (F2 Task 3). `--rf2o` puts a second estimator on the same plant:
    # same model, same floor, same profiles, same CSV columns, same
    # fused topic. An unlabelled session cannot be told from a wheel+imu
    # one afterwards, which is exactly what the traction label exists to
    # prevent on the other axis - so it is a REFUSAL and not a default,
    # and it is not inferred from the absence of the flag either.
    if not fields.get("arm"):
        cfg.refuse("the state file names the estimator arm", path,
                   "it has no 'arm=' line. m5v3.sh has written one on "
                   "every bringup",
                   "since F2 Task 3 - `wheel+imu` or `wheel+imu+rf2o` - "
                   "so this stack was",
                   "brought up by an older copy of that script, or the "
                   "file is a truncated",
                   "write. RECORDING WITHOUT IT IS NOT ALLOWED: the two "
                   "arms produce",
                   "sessions that are identical in every other respect. "
                   "Stop the stack and",
                   "start it again with the m5v3.sh in this tree.")
    # AND THE ABSOLUTE LAYER, BY THE SAME RULE AND FOR A THIRD REASON
    # (F3 Task 2). `--localize` puts a localiser above the same
    # estimator on the same plant: same model, same floor, same
    # profiles, same CSV columns, same fused topic, and the only visible
    # difference is an edge on /tf that no table has a column for. An
    # unlabelled session cannot be told from an unlocalised one
    # afterwards.
    #   `none` IS A VALUE AND A MISSING LINE IS NOT. A stack brought up
    #   without the flag writes loc=none; a state file with no loc= line
    #   at all was written by a script that predates this arm, and the
    #   two are different facts about the run. Neither is inferred from
    #   the other.
    if not fields.get("loc"):
        cfg.refuse("the state file names the absolute layer", path,
                   "it has no 'loc=' line. m5v3.sh has written one on "
                   "every bringup since",
                   "F3 Task 2 - `none` or `<localiser>@<map md5>` - so "
                   "this stack was brought",
                   "up by an older copy of that script, or the file is a "
                   "truncated write.",
                   "RECORDING WITHOUT IT IS NOT ALLOWED: a localised run "
                   "and an unlocalised",
                   "one differ by one edge on /tf and by nothing a CSV "
                   "can see. Stop the",
                   "stack and start it again with the m5v3.sh in this "
                   "tree.")
    return fields


#: THE `loc=` GRAMMAR, AND SINCE F3 TASK 3 IT LIVES IN evidence_core.
#: The grammar is `<localiser>@<artifact md5>` or the word `none`, and it
#: is parsed rather than looked up for evidence_core.fused_topic_key()'s
#: reason: a rebuilt map changes the md5 and nothing else, and a table
#: keyed by whole labels would stop working the first time one is.
#:   IT MOVED BECAUSE A THIRD READER APPEARED. F3 Task 2 had two -
#: this file and tools/localization_health.py, which split the string by
#: hand - and Task 3 added the questions that CANNOT be answered by
#: splitting: which topic this arm's pose comes out on, and which frozen
#: artifact the md5 belongs to. Those needed a table, tests reach a
#: table in evidence_core without a simulator, and a grammar with its
#: table in one module and its split in another is two files that can
#: disagree about one label. These two names stay here so that every
#: call site in this file reads the same as it did.
localizer_of = core.localizer_of
map_md5_of = core.loc_md5_of


def write_session_file(path, fields):
    with open(os.path.join(path, FILES["session"]), "w",
              encoding="utf-8") as handle:
        for key, value in fields:
            handle.write("{}={}\n".format(key, value))


def describe_session(cfg, session, node, profile, started_wall, exit_code,
                     safety_rows, traction, bag=None):
    """What this run was, written beside what it recorded.

    IT IS WHAT MAKES A DIRECTORY OF CSVs A SESSION. `analyse` reads
    `kind` to know whether to score a drive or a static capture and
    `profile` to know which table in config.yaml the corner angle came
    from - neither of which any CSV can say for itself. It is written on
    the way out of EVERY path, including the two that refuse, so a run
    that went wrong is still a run somebody can open.

    AND SINCE F2 TASK 2 IT ALSO CARRIES THE TRACTION, for the same
    reason and one worse. `model` below names the file the truck was
    spawned from, and after `--slippery` that file is IDENTICAL between a
    nominal run and a slippery one - the compliances were overridden
    afterwards, through a service. So the model line no longer says which
    plant this was, and these three do.
    """
    write_session_file(session, [
        ("kind", "drive" if profile else "static"),
        ("profile", profile or ""),
        ("recorded", datetime.datetime.now().isoformat()),
        ("partition", cfg.s("isolation.gz_partition")),
        ("model", cfg.s("vehicle.model")),
        ("traction", traction.get("traction", "")),
        ("slip_compliance_lateral",
         traction.get("slip_compliance_lateral", "")),
        ("slip_compliance_longitudinal",
         traction.get("slip_compliance_longitudinal", "")),
        # AND SINCE F2 TASK 3 IT CARRIES THE ESTIMATOR ARM TOO, for the
        # traction label's reason applied to the other half of the
        # stack. `arm_source` is the provenance the arm alone cannot
        # give: which parameter files the filter was handed and which
        # revision of rf2o was in the loop, so a row in EVIDENCE_FUSION
        # 10 can be traced to a pinned commit rather than to a name.
        ("arm", traction.get("arm", "")),
        ("arm_source", traction.get("arm_source", "")),
        # AND SINCE F3 TASK 2 IT CARRIES THE ABSOLUTE LAYER, for the arm
        # label's reason applied one layer up. `loc` is
        # `<localiser>@<map md5>` or the word `none`, and the md5 half is
        # what binds every absolute figure from this session to ONE grid
        # (F3 constraint 16) - `analyse` refuses to score a session
        # through a registration that belongs to a different one.
        ("loc", traction.get("loc", "")),
        ("loc_source", traction.get("loc_source", "")),
        ("spawn", "{} {} {}".format(cfg.s("vehicle.spawn.x"),
                                    cfg.s("vehicle.spawn.y"),
                                    cfg.s("vehicle.spawn.yaw"))),
        ("drive_started_wall", started_wall),
        ("drive_exit", exit_code),
        ("safety_frames", safety_rows),
        # AND SINCE F3 TASK 1 IT SAYS WHETHER THERE IS A ROSBAG IN HERE,
        # because that is the one artifact of a session that another
        # program consumes rather than reads. `bag_dir` empty means
        # `--bag` was not given; a `bag_dir` with no `bag_files` beside
        # it means the recorder could not finalise it, which is a bag
        # `ros2 bag play` refuses and a reader has to be told about
        # BEFORE they spend an hour on the map it would not build.
        ("bag_dir", (bag or {}).get("dir", "")),
        ("bag_topics", (bag or {}).get("topics", "")),
        ("bag_storage", (bag or {}).get("storage", "")),
        ("bag_files", (bag or {}).get("files", "")),
        ("bag_bytes", (bag or {}).get("bytes", "")),
    ] + [("rows_" + name, count) for name, count in node.counts()])


def read_session_file(cfg, path):
    fields = {}
    name = os.path.join(path, FILES["session"])
    if not os.path.isfile(name):
        cfg.refuse("the session {} carries a {}".format(
            os.path.basename(path), FILES["session"]), path,
            "it is written by `record` when a run finishes; a directory "
            "without one is not a session this tool produced.")
    with open(name, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            fields[key] = value
    return fields


def md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Writer(object):
    """One stream's CSV, opened on its first message.

    THE HEADER IS WRITTEN FROM THE FIRST MESSAGE and not from a constant,
    because the width of a scan is the SENSOR's to state: a capture whose
    header says beam_0..beam_810 is a capture that saw 811 beams, and if
    the model changes the file says so without this program being edited.

    THE FIRST COLUMN IS SIM TIME AND IT IS WRITTEN TO NINE DECIMALS, the
    resolution of the stamp the plant put on the message. Everything else
    gets six, which is a micrometre on a range and a microradian on a
    heading - three orders of magnitude finer than anything measured here
    and small enough to keep an 811-beam capture readable.
    """

    def __init__(self, path):
        self.path = path
        self.n = 0
        self._handle = None
        self._writer = None

    def open(self, names):
        self._handle = open(self.path, "w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._handle)
        self._writer.writerow(names)

    @property
    def is_open(self):
        return self._writer is not None

    def row(self, values):
        out = []
        for i, value in enumerate(values):
            out.append("{:.9f}".format(value) if i == 0
                       else "{:.6f}".format(value))
        self._writer.writerow(out)
        self.n += 1

    def close(self):
        if self._handle is not None:
            self._handle.close()
            self._handle = None


# ----------------------------------------------------------------------
# the gz side - the sensors the bridge does not carry
# ----------------------------------------------------------------------

def apply_isolation(cfg):
    """Put this process on this track's graph, BEFORE rclpy.init().

    MEASURED THE HARD WAY, 2026-08-25: the first run of this recorder
    refused with "nothing arrived on: clock, odom_truth, wheel_odom, ..."
    - every stream, not one - and every topic was spelled correctly. The
    domain was the answer. m5v3.sh exports ROS_DOMAIN_ID before it spawns
    the estimator, and drive_route.py puts it on the environment of the
    gz children it starts, but a tool an operator runs BY HAND inherits
    whatever shell they are in, which is domain 0 - a graph this stack
    has never published on.
      IT HAS TO HAPPEN BEFORE rclpy.init(), because the DDS participant
      reads the domain when the context is created and nothing after that
      moves it. That is why this is a function of its own with a name
      that says when it runs, rather than two lines inside record().
    GZ_PARTITION goes on for the same reason one level down: the gz-side
    captures are subprocesses of this one and inherit its environment.
    """
    os.environ["GZ_PARTITION"] = cfg.s("isolation.gz_partition")
    os.environ["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")


def gz_env(cfg):
    """The environment every gz call in this file inherits.

    THE PARTITION IS THE WHOLE POINT. gz transport is not DDS, so
    ROS_DOMAIN_ID does not scope the simulator at all; GZ_PARTITION is
    what decides which truck this instrument measures.
    """
    apply_isolation(cfg)
    return dict(os.environ)


def require_gz(cfg):
    """gz on PATH, or a refusal naming the line the operator missed."""
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, "gz")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return
    cfg.refuse("gz is on PATH", _common.CONFIG + " (paths.ros_setup)",
               "gz-tools comes from gz_tools_vendor under /opt/ros on this "
               "rig, so ROS has to be sourced:",
               "  source {}".format(cfg.s("paths.ros_setup")),
               "then run this command again. See CONTEXT.md - this stack "
               "lives inside WSL.")


class BagRecorder(object):
    """`ros2 bag record` inside the session, for the OFFLINE SLAM run.

    WHY A SUBPROCESS AND NOT A rosbag2_py WRITER IN THIS PROCESS. This
    recorder already holds ten subscriptions and writes ten CSVs on one
    thread; adding 15 Hz of 811-beam scan and 500 Hz of clock to the same
    executor would put the bag's write latency inside every rate figure
    the CSVs are used to compute. `ros2 bag record` is a separate process
    with its own executor and its own thread, exactly as
    tools/drive_route.py is a separate process rather than a function
    call - and for the same reason: one run, several instruments, none of
    them in each other's way.

    IT RECORDS THE SAME RUN AND NOT ITS OWN. It is started after every
    stream has arrived and after the filter has been checked, before the
    pre-roll, and it is stopped after the post-roll - so the bag spans
    the reference pose, the whole drive and the settle, which is what an
    offline SLAM run needs and is the same span the CSVs cover.

    IT IS STOPPED WITH SIGINT AND NOT SIGTERM, and the difference is the
    artifact. rosbag2 finalises its storage and writes metadata.yaml in
    its shutdown handler; a bag killed before that runs has no metadata
    and `ros2 bag play` refuses it by name. So the process is started in
    a session of its own (setsid) and the signal goes to the whole
    process group - `ros2` is a python launcher and the recorder is what
    it runs.
    """

    def __init__(self, cfg, session):
        self.cfg = cfg
        self.path = os.path.join(session, cfg.s("evidence.bag.dir"))
        self.keys = [k.strip() for k in cfg.s("evidence.bag.topics").split(",")
                     if k.strip()]
        # BY DOTTED KEY AND NOT BY ADDRESS. config.yaml names each topic
        # once; this resolves the key, which also means a bag list that
        # asks for a topic this stack does not carry is refused by
        # _common's own "config.yaml defines topics.X" before anything
        # is started.
        self.topics = [cfg.s("topics." + key) for key in self.keys]
        self.storage = cfg.s("evidence.bag.storage")
        self.proc = None

    def start(self):
        """Bring the bag up, and refuse if it does not start writing."""
        self.proc = subprocess.Popen(
            ["ros2", "bag", "record", "--storage", self.storage,
             "--output", self.path] + self.topics,
            stdout=open(self.path + ".log", "w", encoding="utf-8"),
            stderr=subprocess.STDOUT, start_new_session=True,
            env=dict(os.environ), cwd=_common.REPO)
        budget = self.cfg.f("evidence.bag.start_timeout_s")
        deadline = time.time() + budget
        while time.time() < deadline:
            if self.proc.poll() is not None:
                self.cfg.refuse(
                    "`ros2 bag record` stayed up", self.path + ".log",
                    "it exited {} before it wrote anything.".format(
                        self.proc.returncode),
                    "NOTHING WAS DRIVEN.")
            if self._writing():
                return
            time.sleep(0.2)
        self.stop()
        self.cfg.refuse(
            "`ros2 bag record` began writing inside {:g}s".format(budget),
            self.path + ".log (config.yaml evidence.bag.start_timeout_s)",
            "no storage file appeared under {}".format(self.path),
            "STARTING THE DRIVE ANYWAY WOULD PUT THE REFERENCE POSE "
            "OUTSIDE THE BAG.")

    def _writing(self):
        if not os.path.isdir(self.path):
            return False
        return any(name.endswith("." + self.storage)
                   for name in os.listdir(self.path))

    def stop(self):
        """SIGINT the group, then wait for metadata.yaml. See the header."""
        if self.proc is None:
            return None
        if self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGINT)
            except OSError:
                pass
        budget = self.cfg.f("evidence.bag.stop_timeout_s")
        deadline = time.time() + budget
        meta = os.path.join(self.path, "metadata.yaml")
        while time.time() < deadline:
            if self.proc.poll() is not None and os.path.isfile(meta):
                return self.summary()
            time.sleep(0.2)
        # A BAG THAT WOULD NOT CLOSE IS REPORTED AND NOT REFUSED HERE.
        # The CSVs of this run are complete and are evidence; what is
        # unusable is the bag, and the session file says so in the one
        # place a later reader will look.
        try:
            self.proc.kill()
        except OSError:
            pass
        for line in (
                "WARNING - the bag did not finalise inside "
                "{:g}s.".format(budget),
                "          {} has no metadata.yaml, so "
                "`ros2 bag play` will refuse it.".format(self.path),
                "          {}.log is what it said. The CSVs of this run "
                "are complete.".format(self.path)):
            sys.stderr.write("sensor_evidence: {}\n".format(line))
        sys.stderr.flush()
        return None

    def summary(self):
        """Bytes and storage files, for the session file. No parsing."""
        total = 0
        files = 0
        for name in sorted(os.listdir(self.path)):
            full = os.path.join(self.path, name)
            if os.path.isfile(full):
                total += os.path.getsize(full)
                if name.endswith("." + self.storage):
                    files += 1
        return {"dir": os.path.basename(self.path),
                "topics": ", ".join(self.topics),
                "storage": self.storage,
                "files": files,
                "bytes": total}


def gz_stamp(message):
    """Sim seconds off a gz message's own header.

    PROTOBUF OMITS ZERO FIELDS, so a message that lands on an exact
    second carries no nsec and one in the first second carries no sec.
    Both are defaulted rather than assumed present - drive_route.py's
    SimClock reads the clock the same way and for the same reason.
    """
    stamp = message.get("header", {}).get("stamp", {})
    return (float(stamp.get("sec", 0) or 0)
            + float(stamp.get("nsec", 0) or 0) * 1e-9)


def capture_gz_scan(cfg, topic, frames, path):
    """A fixed number of frames off an UNBRIDGED gz lidar, as a CSV.

    A COUNT AND NOT A DURATION, which is noise_probe.sh's rule: a
    duration would make the sample size depend on the real-time factor,
    and a noise figure that moves with the machine's load is not a noise
    figure. The timeout around it is the bound on WAITING and never the
    sample - a capture that hits it is refused rather than analysed
    short, because a short sample still produces a plausible-looking
    standard deviation, which is the worse failure.

    SUBSCRIBING IS NOT FREE AND THE EVIDENCE SAYS SO. gz renders a sensor
    only while something is subscribed to it, so this capture is what
    makes the safety scanner render at all. It runs in a phase of its own
    after the ROS recording has closed, so nothing else in the session is
    measured beside it.
    """
    timeout_s = cfg.s("evidence.safety.capture_timeout_s")
    result = subprocess.run(
        ["timeout", timeout_s, "gz", "topic", "-e", "-t", topic,
         "--json-output", "-n", str(frames)],
        env=gz_env(cfg), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True)
    rows = []
    width = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        ranges = message.get("ranges")
        if not ranges:
            continue
        values = []
        for value in ranges:
            # gz prints a non-finite range as the STRING "inf" or "NaN".
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                values.append(float("nan"))
        width = width or len(values)
        if len(values) != width:
            continue
        rows.append((gz_stamp(message), time.time(), values))
    if len(rows) < frames:
        cfg.refuse(
            "{} delivered {} frames inside {}s".format(topic, frames,
                                                       timeout_s),
            "{} (config.yaml evidence.safety.capture_timeout_s)".format(
                topic),
            "{} of {} frames arrived in partition {}.".format(
                len(rows), frames, gz_env(cfg)["GZ_PARTITION"]),
            "check the topic against 'gz topic -l' and that the stack is "
            "up ('bash m5_ver3/m5v3.sh status').")
    writer = Writer(path)
    writer.open(["t_sim", "t_wall"]
                + ["beam_{}".format(i) for i in range(width)])
    for t_sim, t_wall, values in rows:
        writer.row([t_sim, t_wall] + values)
    writer.close()
    return writer.n, width


def capture_gz_rate(cfg, topic):
    """The gz-side delivered rate of one topic.

    `gz topic -f` reports a rolling ten-interval window every ten
    messages and DOES NOT STOP ON ITS OWN - measured on this rig, `-d 8`
    ran until it was killed - so it is run under `timeout` and the
    windows it printed are averaged. That is the instrument
    EVIDENCE_MODEL_V3.md 2's gz column was taken with, so the two columns
    are comparable.
    """
    sample_s = cfg.s("evidence.gz_rate.sample_s")
    result = subprocess.run(
        ["timeout", sample_s, "gz", "topic", "-f", "-t", topic],
        env=gz_env(cfg), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, timeout=cfg.f("evidence.gz_rate.timeout_s"))
    rates = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("average rate:"):
            try:
                rates.append(float(line.split(":", 1)[1]))
            except ValueError:
                continue
    return rates


# ----------------------------------------------------------------------
# record - the ROS side
# ----------------------------------------------------------------------

def yaw_of(orientation):
    """The yaw of a quaternion, the full formula and not the yaw-only
    shortcut: the ground truth carries whatever roll and pitch the
    contact solver left on the chassis, and 2*atan2(z, w) is only right
    when those are zero."""
    x, y, z, w = (orientation.x, orientation.y, orientation.z, orientation.w)
    return math.atan2(2.0 * (w * z + x * y),
                      1.0 - 2.0 * (y * y + z * z))


def stamp_of(header):
    """A ROS header stamp as seconds. SIM TIME: /clock is bridged and the
    plant stamps every message from its own clock, so a rate computed
    from these stamps is the sensor's and not the day's real-time
    factor's."""
    return float(header.stamp.sec) + float(header.stamp.nanosec) * 1e-9


def _make_recorder(cfg, Node, QoSProfile, types):
    """Build the recorder class once the ROS types are in hand.

    The types are arguments rather than module-level imports so that this
    file can be imported, linted and run in its `analyse` half by a
    python with no rclpy - see the header.
    """

    class Recorder(Node):

        def __init__(self, session, arm, loc=""):
            super().__init__("m5v3_sensor_evidence")
            self.cfg = cfg
            self.session = session
            # THE STREAM LIST FOLLOWS THE ARM THE STACK SAYS IT IS ON,
            # and it follows it in BOTH directions. On the rf2o arm the
            # relay's output is a REQUIRED stream, so a run whose
            # rf2o child died on its way up is refused by name rather
            # than recorded as a wheel+imu run wearing an rf2o label; on
            # the default arm the stream is not subscribed at all, so
            # `missing()` cannot hold a bringup open waiting for a topic
            # nothing on that stack publishes.
            #   THE ARM IS READ OFF THE STATE FILE m5v3.sh WROTE, not
            #   guessed from whether the topic happens to be up: a
            #   relay that is alive but silent is precisely the failure
            #   this list exists to catch, and a list built by looking
            #   would exclude the stream in exactly that case.
            self.arm = arm
            # AND THE SAME QUESTION ON THE ABSOLUTE AXIS. `loc` is the
            # state file's own label - `<localiser>@<map md5>` or `none`
            # - and it decides two subscriptions and one required
            # stream. Read off the state file rather than guessed from
            # whether the topics happen to be up, for the arm list's
            # reason: a localiser that is alive but silent is precisely
            # the failure this list exists to catch, and a list built by
            # looking would exclude the stream in exactly that case.
            self.loc = loc
            self.localizer = localizer_of(loc)
            self.localized = bool(self.localizer)
            # AND WHICH ADDRESS THAT LOCALISER PUBLISHES ITS OWN POSE ON,
            # WHICH IS NOT THE SAME FOR THE TWO ARMS. nav2_amcl advertises
            # `amcl_pose`; slam_toolbox's localisation node advertises
            # `pose`. The mapping is evidence_core.loc_pose_topic_key() -
            # the same file that maps an ESTIMATOR arm onto its fused
            # topic, and it REFUSES a localiser it has not heard of rather
            # than defaulting, because a subscription to the other arm's
            # address does not fail: it records an empty stream under a
            # label naming a localiser that was publishing all along.
            self.loc_pose_topic = (
                cfg.s(core.loc_pose_topic_key(self.localizer))
                if self.localized else "")
            self.map_frame = cfg.s("frames.map")
            self.odom_frame = cfg.s("frames.odom")
            names = ["clock", "odom_truth", "wheel_odom", "ekf_odom"]
            if "rf2o" in arm:
                names.append("rf2o_odom")
            # THE LOCALISER'S EDGE IS A REQUIRED STREAM AND ITS POSE IS
            # NOT, AND THAT ASYMMETRY IS THE SENSOR MODEL AND NOT A
            # SOFTNESS. amcl re-broadcasts `map` -> `odom` on EVERY scan
            # whether or not it corrected, so on a healthy stack it
            # arrives at 15 Hz within a second and its ABSENCE means the
            # localiser is not broadcasting - which is a bringup that
            # should never have been recorded against.
            #   `amcl_pose` is published only when the particle filter
            #   RESAMPLES, and with the truck standing at its spawn pose
            #   it never does (amcl.yaml's update_min_d is 0.25 m). The
            #   bringup gate consumed the one publication the initial
            #   pose forced, so by the time this recorder attaches there
            #   is nothing left to wait for. Requiring it here would hang
            #   every static capture and every drive's pre-roll on a
            #   message that arrives only once the truck moves - so it is
            #   subscribed, recorded, and checked AFTER the drive
            #   instead, where its absence means the filter never
            #   updated (see record()).
            if self.localized:
                names.append("map_odom")
            names += ["scan_nav", "imu", "depth", "cam_info", "joint_state",
                      "drive_read_a"]
            if self.localized:
                names.append("amcl_pose")
            self.writers = collections.OrderedDict(
                (name, Writer(os.path.join(session, FILES[name])))
                for name in names)
            self.patch_half = cfg.i("evidence.depth.patch_half")
            self.drive_joint = cfg.s("wheel_odom.drive_joint_name")
            self.steer_joint = cfg.s("wheel_odom.steer_joint_name")
            self.depth_encoding = None

            qos = QoSProfile(depth=cfg.i("evidence.qos_depth"))
            self.create_subscription(types.Clock, cfg.s("topics.clock"),
                                     self.cb_clock, qos)
            self.create_subscription(
                types.Odometry, cfg.s("topics.odom_ground_truth"),
                self.cb_truth, qos)
            self.create_subscription(
                types.Odometry, cfg.s("topics.wheel_odom"),
                self.cb_estimate, qos)
            # THE FUSED ESTIMATE, AND IT IS A REQUIRED STREAM. A run
            # recorded without it is not a fusion run, and `missing()`
            # below refuses by this stream's name if nothing arrives -
            # which is this stack's answer to ekf_node being SILENT about
            # an input it never receives (EVIDENCE_FUSION.md 2.2). The
            # recorder is one of the three instruments that CAN say so.
            #   ITS ADDRESS FOLLOWS THE ARM SINCE F2 TASK 4, because the
            #   two estimators do not publish on the same topic: ekf_node
            #   writes topics.odometry_filtered and fuse's fixed-lag
            #   smoother writes topics.fuse_odometry_filtered. The
            #   mapping is evidence_core.fused_topic_key() - the same one
            #   tools/ekf_health.py's gate uses, tested without ROS - and
            #   it REFUSES an arm it does not recognise rather than
            #   defaulting, because a subscription to the wrong arm's
            #   address does not fail, it simply never fires.
            #   THE CSV KEEPS ITS NAME. `ekf_odom` is what every session
            #   since F2 Task 1 calls the fused stream and what
            #   analyse_fused() reads; renaming it by arm would make the
            #   two arms' sessions structurally different, which is
            #   exactly what an A/B may not have. The session's own
            #   `arm=` line says which estimator filled it.
            self.create_subscription(
                types.Odometry, cfg.s(core.fused_topic_key(arm)),
                self.cb_fused, qos)
            # THE LASER ODOMETRY, ON THE ARM THAT HAS ONE. What is
            # recorded is the RELAY's output - the twist the filter
            # fused, with its lever arm corrected and its measured
            # covariance attached - and there is no subscription at all
            # on the default arm.
            if "rf2o" in arm:
                self.create_subscription(
                    types.Odometry, cfg.s("topics.rf2o_odom"),
                    self.cb_rf2o, qos)
            # THE ABSOLUTE LAYER'S TWO, AND THERE IS NO SUBSCRIPTION AT
            # ALL WITHOUT IT. On the default stack neither topic has a
            # publisher, so a subscription would sit there forever
            # holding an empty writer open - which is what the `loc`
            # label is read for.
            if self.localized:
                # THE LOCALISER'S OWN POSE, WITH THE THREE COVARIANCE
                # ENTRIES A 2D POSE HAS. The full 6x6 is 36 numbers of
                # which 33 are structurally zero on a planar filter, and
                # a CSV that carried all of them would be a CSV nobody
                # opens.
                self.create_subscription(
                    types.PoseWithCovarianceStamped,
                    self.loc_pose_topic, self.cb_amcl_pose, qos)
                # AND THE EDGE ITSELF, OFF /tf. It is the transform a
                # consumer of this stack would look up, captured where
                # the consumer would find it rather than re-derived from
                # the pose - the two are not the same thing: amcl
                # computes the edge from its pose and the odometry AT
                # THE SCAN'S STAMP, and it re-broadcasts that edge
                # between updates while the pose stays silent.
                #   A DEEPER QUEUE THAN THE REST. /tf carries the EKF's
                #   50 Hz edge as well as the localiser's 15 Hz one, so
                #   this subscription sees about 65 messages a second of
                #   which it keeps a fifth.
                self.create_subscription(
                    types.TFMessage, cfg.s("topics.tf"), self.cb_tf, qos)
            self.create_subscription(
                types.LaserScan, cfg.s("topics.scan_nav"), self.cb_scan, qos)
            self.create_subscription(types.Imu, cfg.s("topics.imu"),
                                     self.cb_imu, qos)
            self.create_subscription(
                types.Image, cfg.s("topics.cam_depth"), self.cb_depth, qos)
            self.create_subscription(
                types.CameraInfo, cfg.s("topics.cam_info"), self.cb_info,
                qos)
            self.create_subscription(
                types.JointState, cfg.s("topics.joint_state"),
                self.cb_joint, qos)
            self.create_subscription(
                types.JointState, cfg.s("topics.drive_speed_read_a"),
                self.cb_drive, qos)

        # ------------------------------ streams ------------------------

        def cb_clock(self, msg):
            writer = self.writers["clock"]
            if not writer.is_open:
                writer.open(["t_sim", "t_wall"])
            writer.row([float(msg.clock.sec)
                        + float(msg.clock.nanosec) * 1e-9, time.time()])

        def _odometry(self, writer, msg, twist):
            if not writer.is_open:
                writer.open(["t_sim", "t_wall", "x", "y", "yaw"]
                            + (["vx", "vy", "vyaw"] if twist else []))
            row = [stamp_of(msg.header), time.time(),
                   msg.pose.pose.position.x, msg.pose.pose.position.y,
                   yaw_of(msg.pose.pose.orientation)]
            if twist:
                row += [msg.twist.twist.linear.x, msg.twist.twist.linear.y,
                        msg.twist.twist.angular.z]
            writer.row(row)

        def cb_truth(self, msg):
            # WORLD COORDINATES, recorded as they arrive and transformed
            # nowhere. The spawn frame belongs to analyse, where the
            # transform is one tested function; a recorder that
            # transformed on the way in would bake a config value into
            # the evidence and there would be no way to check it after.
            self._odometry(self.writers["odom_truth"], msg, twist=False)

        def cb_estimate(self, msg):
            self._odometry(self.writers["wheel_odom"], msg, twist=True)

        def cb_fused(self, msg):
            # SAME COLUMNS AS THE RAW ESTIMATE, on purpose: the two are
            # read by the same reduction and a column that existed on one
            # and not the other would be a reduction with a branch in it.
            self._odometry(self.writers["ekf_odom"], msg, twist=True)
            # AND THE LAST ONE IS KEPT so the drive is not spent on a
            # filter that has already blown up. See fused_pose() below
            # and EVIDENCE_FUSION.md 8.6.
            self.last_fused = (msg.pose.pose.position.x,
                               msg.pose.pose.position.y)

        def cb_rf2o(self, msg):
            # SAME COLUMNS AS THE OTHER TWO ODOMETRIES, on purpose: one
            # reduction reads all three, and a column that existed on
            # one and not the others would be a reduction with a branch
            # in it. The pose here is rf2o's own scan-matched dead
            # reckoning, carried in its own frame and flagged
            # do-not-fuse; the twist is what reaches the filter.
            self._odometry(self.writers["rf2o_odom"], msg, twist=True)

        def fused_pose(self):
            return getattr(self, "last_fused", None)

        def cb_amcl_pose(self, msg):
            writer = self.writers["amcl_pose"]
            if not writer.is_open:
                writer.open(["t_sim", "t_wall", "x", "y", "yaw",
                             "cov_xx", "cov_yy", "cov_yawyaw"])
            covariance = list(msg.pose.covariance)
            writer.row([stamp_of(msg.header), time.time(),
                        msg.pose.pose.position.x, msg.pose.pose.position.y,
                        yaw_of(msg.pose.pose.orientation),
                        covariance[0], covariance[7], covariance[35]])

        def cb_tf(self, msg):
            # ONE EDGE OUT OF A TOPIC THAT CARRIES EVERY EDGE, and the
            # match is on BOTH frame names. /tf on a localised stack
            # carries the estimator's `odom` -> `base_link` at 50 Hz and
            # the localiser's `map` -> `odom` at the scan rate; matching
            # on the child alone would take the estimator's messages too
            # on any future stack that gave `odom` a second parent, and
            # matching on the parent alone would take a `map` -> anything
            # a costmap decided to publish.
            for transform in msg.transforms:
                if transform.header.frame_id != self.map_frame:
                    continue
                if transform.child_frame_id != self.odom_frame:
                    continue
                writer = self.writers["map_odom"]
                if not writer.is_open:
                    writer.open(["t_sim", "t_wall", "x", "y", "yaw"])
                writer.row([stamp_of(transform.header), time.time(),
                            transform.transform.translation.x,
                            transform.transform.translation.y,
                            yaw_of(transform.transform.rotation)])

        def cb_scan(self, msg):
            writer = self.writers["scan_nav"]
            values = [float(v) for v in msg.ranges]
            if not writer.is_open:
                writer.open(["t_sim", "t_wall"]
                            + ["beam_{}".format(i)
                               for i in range(len(values))])
            writer.row([stamp_of(msg.header), time.time()] + values)

        def cb_imu(self, msg):
            writer = self.writers["imu"]
            if not writer.is_open:
                writer.open(["t_sim", "t_wall", "gx", "gy", "gz",
                             "ax", "ay", "az"])
            writer.row([stamp_of(msg.header), time.time(),
                        msg.angular_velocity.x, msg.angular_velocity.y,
                        msg.angular_velocity.z,
                        msg.linear_acceleration.x, msg.linear_acceleration.y,
                        msg.linear_acceleration.z])

        def cb_depth(self, msg):
            writer = self.writers["depth"]
            half = self.patch_half
            self.depth_encoding = msg.encoding
            if msg.encoding != "32FC1":
                self.cfg.refuse(
                    "the depth image arrives as 32FC1",
                    self.cfg.s("topics.cam_depth"),
                    "it arrives as {!r}, and this recorder unpacks little-"
                    "endian float32".format(msg.encoding),
                    "a patch read out of another encoding would be "
                    "numbers, not depths.")
            centre_x = msg.width // 2
            centre_y = msg.height // 2
            buffer = memoryview(msg.data)
            values = []
            for row in range(centre_y - half, centre_y + half):
                offset = row * msg.step + (centre_x - half) * 4
                values.extend(struct.unpack_from(
                    "<{}f".format(2 * half), buffer, offset))
            if not writer.is_open:
                # THE PATCH IS FLATTENED ROW-MAJOR and the column names
                # say so: px_<row>_<col> with the offsets from the image
                # centre, so a pixel in the CSV can be found in the image.
                writer.open(["t_sim", "t_wall"]
                            + ["px_{}_{}".format(r, c)
                               for r in range(-half, half)
                               for c in range(-half, half)])
            writer.row([stamp_of(msg.header), time.time()] + list(values))

        def cb_info(self, msg):
            writer = self.writers["cam_info"]
            if not writer.is_open:
                writer.open(["t_sim", "t_wall", "width", "height"])
            writer.row([stamp_of(msg.header), time.time(),
                        float(msg.width), float(msg.height)])

        def _joint(self, writer, msg, names):
            index = {}
            for wanted in names:
                try:
                    index[wanted] = list(msg.name).index(wanted)
                except ValueError:
                    self.cfg.refuse(
                        "the joint message carries " + wanted,
                        "the plant (m5_ver3/gazebo/forklift_ver3/model.sdf)",
                        "the message names: {}".format(list(msg.name)),
                        "config.yaml names it {!r}".format(wanted))
            if not writer.is_open:
                writer.open(["t_sim", "t_wall"]
                            + ["{}_pos".format(n) for n in names]
                            + ["{}_vel".format(n) for n in names])
            row = [stamp_of(msg.header), time.time()]
            row += [float(msg.position[index[n]]) if index[n] < len(
                msg.position) else float("nan") for n in names]
            row += [float(msg.velocity[index[n]]) if index[n] < len(
                msg.velocity) else float("nan") for n in names]
            writer.row(row)

        def cb_joint(self, msg):
            self._joint(self.writers["joint_state"], msg,
                        [self.steer_joint, self.drive_joint])

        def cb_drive(self, msg):
            self._joint(self.writers["drive_read_a"], msg,
                        [self.drive_joint])

        # ------------------------------ control ------------------------

        #: THE ONE RECORDED STREAM THAT IS NOT REQUIRED TO ARRIVE BEFORE
        #: THE RUN STARTS. See the stream list above: amcl publishes a
        #: pose when its filter UPDATES, and a filter whose vehicle is
        #: standing at spawn does not update. Everything else on this
        #: recorder is a sensor, a bridge or a publisher that runs on a
        #: timer, and an absent one is a stack that is not up.
        OPTIONAL_BEFORE_THE_RUN = ("amcl_pose",)

        def missing(self):
            return [name for name, writer in self.writers.items()
                    if writer.n == 0
                    and name not in self.OPTIONAL_BEFORE_THE_RUN]

        def close(self):
            for writer in self.writers.values():
                writer.close()

        def counts(self):
            return [(name, writer.n) for name, writer in self.writers.items()]

    return Recorder


def spin_until(rclpy, node, predicate, deadline):
    """Spin the node until the predicate holds or the deadline passes.

    THE DEADLINE IS WALL TIME AND THE RECORD LENGTH IS TOO, deliberately:
    a recording is a thing that happens to a machine, and a sim-time
    deadline on a stalled simulator is a deadline that never arrives -
    which is the hang this file's header refuses to allow. Sim time is
    what the CONTENTS are stamped with; that is a different question and
    analyse answers it.
    """
    while time.time() < deadline:
        if predicate():
            return True
        rclpy.spin_once(node, timeout_sec=0.05)
    return predicate()


def profile_seconds(cfg, name):
    rows = cfg.raw("drive_route.profiles").get(name)
    if not isinstance(rows, list):
        cfg.refuse("config.yaml defines drive_route.profiles." + name,
                   _common.CONFIG,
                   "it defines: {}".format(
                       ", ".join(sorted(cfg.raw("drive_route.profiles")))))
    return sum(float(row["hold_s"]) for row in rows)


def record(cfg, args):
    """One complete run: subscribe, optionally drive, write the CSVs."""
    # FIRST LINE OF THE FUNCTION AND NOT A LINE LATER: see the docstring.
    apply_isolation(cfg)
    try:
        import rclpy
        from geometry_msgs.msg import PoseWithCovarianceStamped
        from nav_msgs.msg import Odometry
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from rosgraph_msgs.msg import Clock
        from sensor_msgs.msg import (CameraInfo, Image, Imu, JointState,
                                     LaserScan)
        from tf2_msgs.msg import TFMessage
    except ImportError as exc:
        _common.refuse(
            TOOL, "rclpy is importable", _common.CONFIG + " (paths.ros_setup)",
            "python3 could not import ROS 2: {}".format(exc),
            "`record` runs INSIDE WSL with /opt/ros/jazzy sourced:",
            "  source {}".format(cfg.s("paths.ros_setup")),
            "`analyse` needs none of this and runs anywhere.")

    types = collections.namedtuple(
        "Types", "Clock Odometry LaserScan Imu Image CameraInfo JointState "
                 "PoseWithCovarianceStamped TFMessage")(
            Clock, Odometry, LaserScan, Imu, Image, CameraInfo, JointState,
            PoseWithCovarianceStamped, TFMessage)

    # WHICH PLANT THIS IS, READ BEFORE THE DIRECTORY IS EVEN CREATED. A
    # stack that cannot say leaves no half-written session behind, and
    # the operator is refused before they have spent a run on it.
    traction = read_traction(cfg)
    # AND WHICH ESTIMATOR, WHICH SINCE F2 TASK 4 DECIDES AN ADDRESS AND
    # NOT ONLY A LABEL. The two arms publish their fused estimate on
    # different topics, so an arm this recorder cannot map is an arm it
    # cannot subscribe to - and the failure would be a session that
    # records everything except the one stream it exists to record. It is
    # resolved HERE, before the session directory is created, for
    # read_traction()'s reason.
    try:
        core.fused_topic_key(traction.get("arm", ""))
    except core.EvidenceError as exc:
        cfg.refuse(
            "this recorder knows where the running arm publishes",
            "{} (the arm= line) and tools/evidence_core.py "
            "(fused_topic_key)".format(
                os.path.join(_common.REPO, cfg.s("paths.traction_file"))),
            str(exc),
            "the arm= line says: {!r}".format(traction.get("arm", "")),
            "NOTHING WAS RECORDED.")

    kind = "drive" if args.drive else "static"
    name = args.drive or "rest"
    session = new_session(cfg, kind, name)
    print("=== m5v3 sensor evidence: record ===")
    print("date       {}".format(datetime.datetime.now().isoformat()))
    print("partition  {}".format(cfg.s("isolation.gz_partition")))
    print("session    {}".format(session))
    print("traction   {}   slip compliance {} / {} on {}".format(
        traction.get("traction"),
        traction.get("slip_compliance_lateral", "?"),
        traction.get("slip_compliance_longitudinal", "?"),
        traction.get("wheels", "?")))
    print("arm        {}".format(traction.get("arm")))
    print("           {}".format(traction.get("arm_source", "?")))
    print("loc        {}".format(traction.get("loc")))
    print("           {}".format(traction.get("loc_source", "?")))
    print("mode       {}".format(
        "drive " + args.drive if args.drive else "static, vehicle at rest"))
    sys.stdout.flush()

    rclpy.init(args=None)
    node = _make_recorder(cfg, Node, QoSProfile, types)(
        session, traction.get("arm", ""), traction.get("loc", ""))
    drive_exit = ""
    drive_started_wall = ""
    # THE BAG IS BUILT HERE AND STARTED LATER. Constructing it resolves
    # every topic key through config.yaml, so a bag list naming a topic
    # this stack does not carry is refused now - before a session's worth
    # of run is spent on it - rather than by `ros2 bag record` shrugging
    # and recording nothing.
    bag = BagRecorder(cfg, session) if args.bag else None
    bag_summary = None
    try:
        # PHASE 1: EVERY STREAM HAS TO ARRIVE BEFORE ANYTHING IS TIMED.
        # A capture that opened while one bridge was still coming up
        # would carry a stream that starts late, and every rate taken
        # over it would be that stream's rate over the wrong span.
        wait_s = cfg.f("evidence.wait_first_s")
        print("waiting for the first message on every stream "
              "(bounded at {:g}s)...".format(wait_s))
        sys.stdout.flush()
        alive = spin_until(rclpy, node, lambda: not node.missing(),
                           time.time() + wait_s)
        if not alive:
            missing = node.missing()
            cfg.refuse(
                "every recorded stream delivered a message inside "
                "{:g}s".format(wait_s),
                _common.CONFIG + " (evidence.wait_first_s) and the bridge",
                "nothing arrived on: {}".format(", ".join(missing)),
                "is the stack up in partition {} "
                "('bash m5_ver3/m5v3.sh status')?".format(
                    cfg.s("isolation.gz_partition")),
                "what did arrive is left in {}".format(session))
        print("all {} streams alive.".format(len(node.writers)))
        sys.stdout.flush()

        # THE FILTER IS CHECKED BEFORE THE DRIVE IS SPENT, and the truck
        # standing at its spawn pose is the strongest moment to check it:
        # nothing has moved, so the fused estimate must still be at the
        # origin of its own odom frame. ekf_node diverges at startup on
        # most bringups of this stack and reports NOTHING - ALIVE, at
        # rate, stream arriving (EVIDENCE_FUSION.md 8.6) - so without
        # this the operator finds out sixty seconds later, in `analyse`,
        # or not at all.
        fused = node.fused_pose()
        if fused is not None:
            try:
                core.require_not_diverged(
                    [fused[0]], [fused[1]],
                    cfg.f("evidence.analyse.fused_sanity_m"),
                    "the filter, with the truck standing still at spawn,")
            except core.EvidenceError as exc:
                node.close()
                describe_session(cfg, session, node, args.drive,
                                 drive_started_wall, "NOT STARTED", 0,
                                 traction, bag_summary)
                cfg.refuse(
                    "the filter had not diverged before the drive began",
                    "{} (evidence.analyse.fused_sanity_m) and {}".format(
                        _common.CONFIG, cfg.s("ekf.params_file")),
                    str(exc),
                    "NOTHING WAS DRIVEN. ekf_node says nothing about "
                    "this: it stays ALIVE and",
                    "publishes at its configured rate. Stop the stack "
                    "and start it again -",
                    "the divergence is a startup race and it does not "
                    "recur on every bringup.",
                    "the empty session is in {}".format(session))
            print("filter sane at spawn: ({:.6f}, {:.6f}).".format(*fused))
            sys.stdout.flush()

        if bag is not None:
            print("rosbag2: {} -> {}".format(
                ", ".join(bag.topics), bag.path))
            sys.stdout.flush()
            bag.start()
            print("  recording ({} storage).".format(bag.storage))
            sys.stdout.flush()

        if args.drive:
            pre = cfg.f("evidence.drive.pre_roll_s")
            print("pre-roll {:g}s with the truck at rest (the reference "
                  "pose)...".format(pre))
            sys.stdout.flush()
            spin_until(rclpy, node, lambda: False, time.time() + pre)

            nominal = profile_seconds(cfg, args.drive)
            budget = (nominal * cfg.f("evidence.drive.timeout_factor")
                      + cfg.f("evidence.drive.timeout_margin_s"))
            log = os.path.join(session, "drive_route.log")
            print("driving {} ({:.1f}s of sim time, bounded at {:.0f}s of "
                  "wall)".format(args.drive, nominal, budget))
            print("  log    {}".format(log))
            sys.stdout.flush()
            drive_started_wall = "{:.6f}".format(time.time())
            with open(log, "w", encoding="utf-8") as handle:
                proc = subprocess.Popen(
                    [sys.executable,
                     os.path.join(_HERE, "drive_route.py"), args.drive],
                    stdout=handle, stderr=subprocess.STDOUT,
                    env=gz_env(cfg), cwd=_common.REPO)
                finished = spin_until(rclpy, node,
                                      lambda: proc.poll() is not None,
                                      time.time() + budget)
                if not finished:
                    # THE CSVs ARE STILL WRITTEN, AND SO IS session.txt.
                    # A partial recording of a run that went wrong is
                    # evidence: deleting it would leave the operator with
                    # a refusal and nothing to read, and leaving out the
                    # session file would leave `analyse` unable to open
                    # what the refusal just told them to go and look at.
                    proc.kill()
                    proc.wait()
                    # AND THE BAG CLOSES ON THIS PATH TOO, before the
                    # session file is written - so a run that timed out
                    # still leaves a playable recording of what DID
                    # happen, and the session file still says how big it
                    # is. The finally: below sees bag_summary already set
                    # and stop() is idempotent on a process that has
                    # exited.
                    if bag is not None:
                        bag_summary = bag.stop()
                        bag = None
                    node.close()
                    describe_session(cfg, session, node, args.drive,
                                     drive_started_wall, "TIMED OUT", 0,
                                     traction, bag_summary)
                    cfg.refuse(
                        "drive_route.py finished {} inside {:.0f}s".format(
                            args.drive, budget),
                        log + " (config.yaml evidence.drive.timeout_*)",
                        "the profile asks for {:.1f}s of SIM time; past "
                        "this the plant is stuck, not slow.".format(nominal),
                        "the partial capture is in {}".format(session))
            drive_exit = str(proc.returncode)
            post = cfg.f("evidence.drive.post_roll_s")
            print("drive_route exited {} - post-roll {:g}s".format(
                drive_exit, post))
            sys.stdout.flush()
            spin_until(rclpy, node, lambda: False, time.time() + post)
        else:
            seconds = cfg.f("evidence.static.record_s")
            print("recording {:g}s with the vehicle AT REST...".format(
                seconds))
            sys.stdout.flush()
            spin_until(rclpy, node, lambda: False, time.time() + seconds)
    finally:
        # THE BAG CLOSES FIRST, WHILE THE STREAMS ARE STILL LIVE. It is
        # a separate process and its shutdown takes time; closing the
        # CSVs first would only mean the bag ended up with seconds of
        # run the CSVs do not have.
        if bag is not None:
            bag_summary = bag.stop()
        node.close()
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

    print("")
    print("recorded (rows per stream):")
    for name_, count in node.counts():
        print("  {:<14} {:>7}".format(name_, count))

    # AND THE ONE STREAM THAT COULD NOT BE CHECKED BEFORE THE RUN IS
    # CHECKED AFTER IT. amcl publishes a pose when its particle filter
    # UPDATES, and it updates after amcl.yaml's update_min_d of travel -
    # so a DRIVE on the localised arm that produced not one pose is a
    # localiser that never corrected, and every absolute figure from
    # that session would be the seed re-broadcast for the length of the
    # run. It looks exactly like a good session: the edge is on /tf at
    # 15 Hz, the CSV is full, the rate table is green.
    #   ONLY ON A DRIVE. A `--static` capture has the truck standing
    #   still by definition and an empty amcl_pose there is the
    #   configuration working, not failing.
    if args.drive and node.localized:
        rows = dict(node.counts()).get("amcl_pose", 0)
        if not rows:
            describe_session(cfg, session, node, args.drive,
                             drive_started_wall, drive_exit, 0, traction,
                             bag_summary)
            cfg.refuse(
                "the localiser updated at least once during the drive",
                "{} ({}) and {} (the travel gate)".format(
                    os.path.join(session, FILES["amcl_pose"]),
                    node.loc_pose_topic,
                    cfg.s("localization.{}.params_file".format(
                        node.localizer))),
                "not one pose was published over the whole of "
                "{}.".format(args.drive),
                "THE CAPTURE IS COMPLETE AND IS IN {}".format(session),
                "but every absolute figure in it would be the initial "
                "pose, re-broadcast",
                "for the length of the run - which looks exactly like a "
                "localised session:",
                "the edge is on /tf at the scan rate and the CSV is "
                "full.",
                "read the amcl log: a filter that received scans it "
                "could not transform",
                "says 'Message Filter dropping message', and one that "
                "never received the",
                "map says nothing at all.")

    # PHASE 2: THE GZ SIDE, AFTER THE ROS RECORDING HAS CLOSED. The
    # safety scanner and the 3D lidar are not bridged, and gz renders a
    # sensor only while something is subscribed - so asking is what makes
    # them render, and asking BESIDE the ROS capture would put that cost
    # inside every rate in it.
    safety_rows = 0
    if not args.drive:
        require_gz(cfg)
        topic = cfg.s("topics.safety_scan_back")
        frames = cfg.i("evidence.safety.frames")
        print("")
        print("gz-side capture: {} frames of {}".format(frames, topic))
        sys.stdout.flush()
        safety_rows, width = capture_gz_scan(
            cfg, topic, frames, os.path.join(session,
                                             FILES["safety_scan_back"]))
        print("  {} frames of {} beams".format(safety_rows, width))
        print("")
        print("gz-side delivered rates ({}s each):".format(
            cfg.s("evidence.gz_rate.sample_s")))
        sys.stdout.flush()
        rates_path = os.path.join(session, FILES["gz_rates"])
        with open(rates_path, "w", encoding="utf-8", newline="") as handle:
            out = csv.writer(handle)
            out.writerow(["topic_key", "topic", "windows", "hz_mean",
                          "hz_min", "hz_max"])
            for key in [k.strip() for k in
                        cfg.s("evidence.gz_rate.topics").split(",")]:
                address = cfg.s("topics." + key)
                rates = capture_gz_rate(cfg, address)
                if not rates:
                    cfg.refuse(
                        "`gz topic -f` reported a rate for " + address,
                        "{} (config.yaml evidence.gz_rate.topics)".format(
                            address),
                        "it printed no 'average rate:' line in {}s.".format(
                            cfg.s("evidence.gz_rate.sample_s")),
                        "the partial session is in {}".format(session))
                out.writerow([key, address, len(rates),
                              "{:.4f}".format(core.mean(rates)),
                              "{:.4f}".format(min(rates)),
                              "{:.4f}".format(max(rates))])
                print("  {:<18} {:>8.4f} Hz over {} windows".format(
                    key, core.mean(rates), len(rates)))
                sys.stdout.flush()

    describe_session(cfg, session, node, args.drive, drive_started_wall,
                     drive_exit, safety_rows, traction, bag_summary)
    if bag_summary is not None:
        print("")
        print("rosbag2: {} storage file(s), {:.1f} MB in {}".format(
            bag_summary["files"], bag_summary["bytes"] / 1048576.0,
            bag_summary["dir"]))

    if drive_exit not in ("", "0"):
        cfg.refuse("drive_route.py exited 0",
                   os.path.join(session, "drive_route.log"),
                   "it exited {}. The capture is complete and is in "
                   "{}".format(drive_exit, session),
                   "but the manoeuvre it describes did not finish.")
    print("")
    print("session written: {}".format(session))
    print("analyse it: python3 m5_ver3/tools/sensor_evidence.py analyse "
          "{}".format(session))
    return 0


# ----------------------------------------------------------------------
# analyse - no ROS, no Gazebo, no plant
# ----------------------------------------------------------------------

def table(path, cfg, minimum=None):
    try:
        out = core.read_csv(path)
    except core.EvidenceError as exc:
        fail(cfg, exc, path)
    if minimum is not None and out.n < minimum:
        cfg.refuse(
            "{} recorded at least {} samples".format(
                os.path.basename(path), minimum),
            path + " (config.yaml evidence.min_samples)",
            "it recorded {}. A statistic over that many readings is a "
            "number, not a measurement.".format(out.n))
    return out


def rate_line(cfg, name, stamps_sim, stamps_wall, configured=None):
    try:
        sim = core.rate_from_stamps(stamps_sim)
        wall = core.rate_from_stamps(stamps_wall)
    except core.EvidenceError as exc:
        fail(cfg, exc, "the recorded stamps of " + name)
    ratio = "" if configured in (None, 0) else "{:>7.1%}".format(
        sim.hz_mean / configured)
    # THE REAL-TIME FACTOR OVER THIS CAPTURE, FOR FREE. Every row carries
    # the same messages counted twice - once by the stamp the plant put
    # on them and once by the wall clock they arrived on - so their ratio
    # IS the RTF the recording ran at. It is a cross-check on
    # tools/rtf_probe.sh rather than a second opinion: the probe samples
    # the world's own statistics topic and this is arithmetic on the
    # capture, and if the two disagreed one of them would be wrong.
    print("  {:<16} {:>9} {:>10.4f} {:>10.4f} {:>8} {:>10.5f} {:>10.5f} "
          "{:>7.4f}".format(name, sim.n,
                            sim.hz_mean, wall.hz_mean, ratio,
                            sim.dt_median, sim.dt_max,
                            wall.hz_mean / sim.hz_mean if sim.hz_mean else 0))
    return sim, wall


def noise_line(cfg, label, spread, configured, factor, extra=""):
    """One channel's measured spread against the model's own stddev."""
    ratio = spread.mean / configured if configured else float("inf")
    verdict = "within x{:g}".format(factor) if (
        1.0 / factor <= ratio <= factor) else "OUTSIDE x{:g}".format(factor)
    print("  {:<26} {:>10.6f} {:>10.6f} {:>10.6f} {:>7.3f}  {:<12} {}"
          .format(label, configured, spread.mean, spread.median, ratio,
                  verdict, extra))
    return ratio


def analyse_static(cfg, path, sensors):
    factor = cfg.f("evidence.analyse.noise_factor")
    print("")
    print("--- delivered rates, ROS side (recorder's own capture) ---")
    print("  {:<16} {:>9} {:>10} {:>10} {:>8} {:>10} {:>10} {:>7}".format(
        "stream", "samples", "hz_sim", "hz_wall", "of conf", "dt_med",
        "dt_max", "rtf"))
    configured = {
        "scan_nav": sensors[cfg.s("evidence.sdf_names.nav_lidar")][
            "update_rate"],
        "imu": sensors[cfg.s("evidence.sdf_names.imu")]["update_rate"],
        "depth": sensors[cfg.s("evidence.sdf_names.pallet_cam")][
            "update_rate"],
        "cam_info": sensors[cfg.s("evidence.sdf_names.pallet_cam")][
            "update_rate"],
    }
    tables = {}
    for name in ("clock", "odom_truth", "wheel_odom", "scan_nav", "imu",
                 "depth", "cam_info", "joint_state", "drive_read_a"):
        tables[name] = table(os.path.join(path, FILES[name]), cfg,
                             cfg.i("evidence.min_samples"))
        rate_line(cfg, name, tables[name].column("t_sim"),
                  tables[name].column("t_wall"), configured.get(name))

    print("")
    print("--- temporal spread at rest, against the model's own noise ---")
    print("  {:<26} {:>10} {:>10} {:>10} {:>7}  {:<12} {}".format(
        "channel", "configured", "measured", "median", "ratio", "verdict",
        "readings"))

    def beams_of(one):
        return len([n for n in one.names if n.startswith("beam_")])

    def scan_noise(label, one, spec):
        series = core.finite_beam_series(one, "beam_")
        free, clamped = core.split_clamped(
            series, spec.get("range_min", 0.0),
            cfg.f("evidence.analyse.clamp_tolerance_m"))
        spread, _, zeros = core.temporal_spread(free)
        noise_line(cfg, label, spread, spec["noise"]["range"]["stddev"],
                   factor,
                   "{} of {} beams finite every frame, {} of those pinned "
                   "at range_min ({} m) and left out, {} of the rest with "
                   "zero spread".format(
                       len(series), beams_of(one), len(clamped),
                       spec.get("range_min", "?"), zeros))

    scan_noise("nav_lidar range", tables["scan_nav"],
               sensors[cfg.s("evidence.sdf_names.nav_lidar")])

    safety_path = os.path.join(path, FILES["safety_scan_back"])
    if os.path.isfile(safety_path):
        scan_noise("safety_scanner_back range",
                   table(safety_path, cfg, cfg.i("evidence.min_samples")),
                   sensors[cfg.s("evidence.sdf_names.safety_scanner")])

    cam = sensors[cfg.s("evidence.sdf_names.pallet_cam")]
    patch = core.finite_beam_series(tables["depth"], "px_")
    spread, means, _ = core.temporal_spread(patch)
    noise_line(cfg, "pallet_cam depth", spread,
               cam["noise"]["depth"]["stddev"], factor,
               "{} pixels finite every frame, patch depth {:.6f} m"
               .format(len(patch), means.mean))
    centre = "px_0_0"
    if tables["depth"].has(centre):
        print("  {:<26} {:>10} {:>10.6f} {:>10} {:>7}  {:<12} {}".format(
            "  its centre pixel " + centre, "",
            core.stddev(tables["depth"].column(centre)), "", "", "",
            "one pixel, the optical axis"))

    imu = sensors[cfg.s("evidence.sdf_names.imu")]
    print("")
    print("--- the IMU at rest: white noise, and the bias under it ---")
    print("  the SPREAD is scored after each axis's own run mean is "
          "removed, and that")
    print("  mean is printed beside it as the BIAS: gz draws a bias once "
          "per run and adds")
    print("  it to every sample, so it lives in the mean and not in the "
          "spread. On this")
    print("  model bias_stddev is 0, which fixes the bias MAGNITUDE at "
          "bias_mean and")
    print("  leaves gz drawing its SIGN (model.sdf, the IMU noise block).")
    print("  {:<22} {:>10} {:>10} {:>7}  {:<12} {:>11} {:>11}".format(
        "axis", "conf sigma", "measured", "ratio", "verdict", "conf bias",
        "meas mean"))
    axes = (("gx", "angular_velocity_x"), ("gy", "angular_velocity_y"),
            ("gz", "angular_velocity_z"), ("ax", "linear_acceleration_x"),
            ("ay", "linear_acceleration_y"), ("az", "linear_acceleration_z"))
    for column, channel in axes:
        values = tables["imu"].column(column)
        noise = imu["noise"][channel]
        sd = core.stddev(core.remove_mean(values))
        ratio = sd / noise["stddev"]
        verdict = "within x{:g}".format(factor) if (
            1.0 / factor <= ratio <= factor) else "OUTSIDE x{:g}".format(
                factor)
        print("  {:<22} {:>10.6f} {:>10.6f} {:>7.3f}  {:<12} {:>+11.6f} "
              "{:>+11.6f}".format(
                  column + " (" + channel + ")", noise["stddev"], sd, ratio,
                  verdict, noise["bias_mean"], core.mean(values)))
    # THE GRAVITY IS READ OUT OF THE WORLD AND NOT ASSUMED. See
    # evidence_core.sdf_gravity: warehouse_ver3.sdf declares 9.8 and the
    # vehicle's own mass derivation uses standard 9.80665, and the
    # difference between them is a third of the bias being checked.
    world = os.path.join(_common.REPO, cfg.s("world.file"))
    try:
        gravity = core.sdf_gravity(world)
    except core.EvidenceError as exc:
        fail(cfg, exc, world)
    az_mean = core.mean(tables["imu"].column("az"))
    accel_bias = imu["noise"]["linear_acceleration_z"]["bias_mean"]
    print("  az CARRIES GRAVITY: it reads {:+.6f} m/s^2 and the world's own"
          .format(az_mean))
    print("  <gravity> is {:.5f} ({}), so the residual is {:+.6f} against a"
          .format(gravity, cfg.s("world.file"), az_mean - gravity))
    print("  configured bias magnitude of {:.6f}. NOT 9.80665: the vehicle's"
          .format(accel_bias))
    print("  mass derivation uses standard gravity and this world does not.")

    gz_path = os.path.join(path, FILES["gz_rates"])
    if os.path.isfile(gz_path):
        print("")
        print("--- delivered rates, gz side (`gz topic -f`) ---")
        rates = table(gz_path, cfg)
        for i in range(rates.n):
            key = rates.column("topic_key")[i]
            print("  {:<18} {:>10.4f} Hz over {:>3.0f} windows   "
                  "[{:.4f}, {:.4f}]".format(
                      key, rates.column("hz_mean")[i],
                      rates.column("windows")[i], rates.column("hz_min")[i],
                      rates.column("hz_max")[i]))


def print_track(score, who):
    """The end error split along the direction the truck was FACING.

    WHY THE SPLIT IS PRINTED AND NOT ONLY THE MAGNITUDE. F2 Task 2's
    whole claim is that the two halves of a dead-reckoned position error
    have different causes and different cures - the along-track half is
    the wheel odometry lying about DISTANCE, which nothing in this phase
    observes, and the cross-track half is mostly HEADING, which the gyro
    does observe. A single end error adds them and hides which moved.
    The arithmetic is evidence_core.track_error(), tested there.
    """
    split = core.track_error_of(score)
    print("  ALONG-TRACK     {:+.4f} m  ({} ran {}),   CROSS-TRACK "
          "{:+.4f} m  ({} of the path)".format(
              split.along, who, "LONG" if split.along >= 0 else "SHORT",
              split.cross, "LEFT" if split.cross >= 0 else "RIGHT"))
    print("                  split on the ground truth's COURSE: nose "
          "{:+.4f} rad, driven {:+.2f} m nose-first".format(
              core.normalise_angle(score.truth_end_yaw_rad),
              score.truth_nose_forward_m))
    print("                  (this truck drives FORKS-TRAILING, so a "
          "negative figure there is the")
    print("                   normal case and the axis is the nose "
          "turned by pi)")


def analyse_drive(cfg, path, session, sensors, diverged, withheld):
    profile = session.get("profile", "")
    spawn = core.SpawnFrame(cfg.f("vehicle.spawn.x"), cfg.f("vehicle.spawn.y"),
                            cfg.f("vehicle.spawn.yaw"))
    truth = table(os.path.join(path, FILES["odom_truth"]), cfg,
                  cfg.i("evidence.min_samples"))
    est = table(os.path.join(path, FILES["wheel_odom"]), cfg,
                cfg.i("evidence.min_samples"))
    joints = table(os.path.join(path, FILES["joint_state"]), cfg,
                   cfg.i("evidence.min_samples"))

    # THE REFERENCE POSE IS CHECKED BEFORE ANYTHING IS SCORED. Every
    # figure below is measured in a frame built from vehicle.spawn, so a
    # truck that was not standing there when the recording opened would
    # make all of them wrong by a constant - and a constant error is the
    # kind nobody spots by reading the number.
    x0, y0, yaw0 = (truth.column("x")[0], truth.column("y")[0],
                    truth.column("yaw")[0])
    off = math.hypot(x0 - spawn.x0, y0 - spawn.y0)
    dyaw = abs(core.normalise_angle(yaw0 - spawn.yaw0))
    if (off > cfg.f("evidence.analyse.spawn_tolerance_m")
            or dyaw > cfg.f("evidence.analyse.spawn_tolerance_rad")):
        cfg.refuse(
            "the truck was at vehicle.spawn when the recording opened",
            _common.CONFIG + " (vehicle.spawn, evidence.analyse."
                             "spawn_tolerance_*)",
            "the first ground-truth sample reads ({:.6f}, {:.6f}) yaw "
            "{:.6f}".format(x0, y0, yaw0),
            "config says ({:.6f}, {:.6f}) yaw {:.6f}".format(
                spawn.x0, spawn.y0, spawn.yaw0),
            "that is {:.4f} m and {:.4f} rad away. The drift frame is "
            "built on the config pose,".format(off, dyaw),
            "so every figure from this run would be wrong by a constant.")

    print("")
    print("--- {} : the estimate against the ground truth ---".format(
        profile))
    print("  reference pose  config ({:.6f}, {:.6f}) yaw {:.6f}".format(
        spawn.x0, spawn.y0, spawn.yaw0))
    print("  recorded at rest ({:.6f}, {:.6f}) yaw {:.6f}  -> {:.4f} m, "
          "{:.5f} rad off".format(x0, y0, yaw0, off, dyaw))
    print("  estimate opens at ({:.6f}, {:.6f}) yaw {:.6f}".format(
        est.column("x")[0], est.column("y")[0], est.column("yaw")[0]))

    try:
        score = core.score_drift(
            truth.rows("t_sim", "x", "y", "yaw"),
            est.rows("t_sim", "x", "y", "yaw"), spawn,
            cfg.f("evidence.analyse.max_pair_gap_s"))
    except core.EvidenceError as exc:
        fail(cfg, exc, path)

    print("  paired samples  {} over {:.3f} s of sim time".format(
        score.n, score.t1 - score.t0))
    print("  ground truth    {:.4f} m of path, turned {:+.4f} rad".format(
        score.truth_path_m, score.truth_turned_rad))
    print("  estimate        {:.4f} m of path, turned {:+.4f} rad  "
          "({:+.2f} % of path)".format(
              score.est_path_m, score.est_turned_rad,
              100.0 * (score.est_path_m / score.truth_path_m - 1.0)
              if score.truth_path_m else float("nan")))
    print("  END ERROR       {:.4f} m   (dx {:+.4f}, dy {:+.4f}), heading "
          "{:+.4f} rad".format(score.end_error_m, score.end_dx, score.end_dy,
                               score.end_yaw_error_rad))
    print_track(score, "estimate")
    print("  rms over run    {:.4f} m        worst {:.4f} m".format(
        score.rms_m, score.max_error_m))
    print("  ABSOLUTE, not anchored: no initial offset is removed.")
    # AND WHAT THE PLANT ITSELF DID ABOUT COMING HOME. The ground truth's
    # closure is a reading on the PROFILE's table - square: is written to
    # return the truck to its start and either it does or it does not -
    # and it is a different question from the estimate's drift, which is
    # everything above. Both are printed because on an out-and-back
    # profile they disagree spectacularly (EVIDENCE_SENSORS.md 3.1(b):
    # aisle's estimate closes to 0.04 m while it is 1.23 m out at the far
    # end), and a reader who has only one of them can be misled by it.
    print("  CLOSURE         ground truth {:.4f} m from its own start   "
          "estimate {:.4f} m from its".format(
              core.closure(truth.column("x"), truth.column("y")),
              core.closure(est.column("x"), est.column("y"))))
    fused = analyse_fused(cfg, path, profile, spawn, truth, score,
                          diverged)
    # AND THE LAYER ABOVE IT, WHICH IS THE ONLY ONE THAT KNOWS WHERE THE
    # VEHICLE IS. It is passed the FUSED score rather than the raw one
    # because that is what the absolute layer is stacked on: AMCL
    # corrects the estimator's edge, not the wheel odometry's, and the
    # subtraction that answers "did the map pay F2's debt" has to be
    # against the thing F2 shipped.
    analyse_localization(cfg, path, profile, session, truth, fused,
                         withheld)
    return score, truth, est, joints


def analyse_fused(cfg, path, profile, spawn, truth, raw, diverged):
    """The EKF's own output, scored against the same truth, and then
    against the raw estimate it was built from.

    THE THIRD STREAM IS OPTIONAL AND THAT IS NOT A SOFTNESS. F1's seven
    drive sessions were recorded before this filter existed, and their
    figures are the ones F2's own tables are compared against - so
    `analyse` has to be able to re-derive them, from those CSVs, and say
    plainly that there is no filter in them. What is NOT optional is the
    RECORDING: record() lists ekf_odom among the streams every run must
    deliver, and refuses by name if nothing arrives on it.

    THE SAME FRAME AND THE SAME TRANSFORM. Both estimates publish in the
    odom frame, both odom frames are the spawn pose (the stack is
    stopped and restarted before every drive), so the SpawnFrame that
    scores one scores the other. Nothing here is re-anchored.
    """
    full = os.path.join(path, FILES["ekf_odom"])
    if not os.path.isfile(full):
        print("")
        print("--- {} : NO FUSED ESTIMATE IN THIS SESSION ---".format(
            profile))
        print("  {} is not in this capture. It was recorded before F2 "
              "Task 1".format(FILES["ekf_odom"]))
        print("  added the EKF child, and the figures above are the raw "
              "wheel odometry's")
        print("  exactly as EVIDENCE_SENSORS.md 3 published them. Nothing "
              "is missing from")
        print("  this run; the filter had not been built when it was "
              "driven.")
        return None
    fused = table(full, cfg, cfg.i("evidence.min_samples"))
    # THE FILTER IS CHECKED FOR HAVING RUN AT ALL BEFORE IT IS SCORED.
    # A diverged ekf_node publishes 1e48 m at its configured rate and
    # logs nothing; scored, it produces a full drift table of numbers
    # about nothing and a `removed` column of -1e50 %. See
    # evidence_core.diverged_at() and EVIDENCE_FUSION.md 8.6.
    #   THE FUSED TABLE IS DROPPED AND THE SESSION IS NOT. The ground
    #   truth and the raw wheel odometry in a run whose FILTER blew up
    #   are untouched by that - they are different processes - and they
    #   are evidence. What must not survive is any FUSED claim about the
    #   run, so the block below is replaced by a named refusal, the
    #   comparison is not computed at all, and analyse() exits NON-ZERO
    #   at the end naming every session this happened in. A warning
    #   scrolls off the top of a long run; an exit status does not.
    gone = core.diverged_at(fused.column("x"), fused.column("y"),
                            cfg.f("evidence.analyse.fused_sanity_m"))
    if gone is not None:
        print("")
        print("--- {} : THE FILTER DIVERGED IN THIS SESSION - NO FUSED "
              "FIGURES ---".format(profile))
        print("  sample {} of {} of {} reads ({:g}, {:g}), and "
              "config.yaml's".format(
                  gone, len(fused.column("x")), FILES["ekf_odom"],
                  fused.column("x")[gone], fused.column("y")[gone]))
        print("  evidence.analyse.fused_sanity_m is {:g} m. That is not "
              "drift - the whole".format(
                  cfg.f("evidence.analyse.fused_sanity_m")))
        print("  floor is 48 m by 32 m - it is ekf_node's startup "
              "divergence, measured and")
        print("  tabulated in EVIDENCE_FUSION.md 8.6. ekf_node logs "
              "NOTHING about it.")
        print("  The ground truth and the raw wheel odometry above are "
              "UNAFFECTED and are")
        print("  this run's evidence; every FUSED figure is withheld and "
              "`analyse` will exit")
        print("  non-zero. Stop the stack and start it again - it does "
              "not recur every time.")
        diverged.append(os.path.basename(path))
        return None
    print("")
    print("--- {} : the FUSED estimate against the same ground truth "
          "---".format(profile))
    print("  EKF opens at    ({:.6f}, {:.6f}) yaw {:.6f}".format(
        fused.column("x")[0], fused.column("y")[0], fused.column("yaw")[0]))
    try:
        score = core.score_drift(
            truth.rows("t_sim", "x", "y", "yaw"),
            fused.rows("t_sim", "x", "y", "yaw"), spawn,
            cfg.f("evidence.analyse.max_pair_gap_s"))
    except core.EvidenceError as exc:
        fail(cfg, exc, full)
    print("  paired samples  {} over {:.3f} s of sim time".format(
        score.n, score.t1 - score.t0))
    print("  ground truth    {:.4f} m of path, turned {:+.4f} rad".format(
        score.truth_path_m, score.truth_turned_rad))
    print("  EKF             {:.4f} m of path, turned {:+.4f} rad  "
          "({:+.2f} % of path)".format(
              score.est_path_m, score.est_turned_rad,
              100.0 * (score.est_path_m / score.truth_path_m - 1.0)
              if score.truth_path_m else float("nan")))
    print("  END ERROR       {:.4f} m   (dx {:+.4f}, dy {:+.4f}), heading "
          "{:+.4f} rad".format(score.end_error_m, score.end_dx, score.end_dy,
                               score.end_yaw_error_rad))
    print_track(score, "EKF")
    print("  rms over run    {:.4f} m        worst {:.4f} m".format(
        score.rms_m, score.max_error_m))
    print("  CLOSURE         EKF {:.4f} m from its own start".format(
        core.closure(fused.column("x"), fused.column("y"))))

    # AND THE ONE TABLE THIS WHOLE PHASE EXISTS FOR.
    out = core.compare_drift(raw, score)
    print("")
    print("--- {} : what fusing bought (raw wheel odom -> EKF) ---".format(
        profile))
    print("  {:<16} {:>12} {:>12} {:>12} {:>10}".format(
        "figure", "raw", "EKF", "removed", "of raw"))
    for label, unit, one in (("end error", "m", out.end_error),
                             ("END HEADING", "rad", out.end_yaw),
                             # F2 TASK 2's TWO ROWS, and they are the two
                             # the slip scenario is read on: the gyro can
                             # move CROSS-track because heading is what it
                             # observes, and nothing on this stack can
                             # move ALONG-track because nothing on it
                             # observes distance (EVIDENCE_FUSION.md 8.5).
                             ("ALONG-track", "m", out.along),
                             ("CROSS-track", "m", out.cross),
                             ("rms over run", "m", out.rms),
                             ("worst", "m", out.max_error)):
        print("  {:<16} {:>+12.4f} {:>+12.4f} {:>+12.4f} {:>9.1f}% "
              "[{}]".format(label, one.before, one.after, one.removed,
                            100.0 * one.fraction, unit))
    print("  a NEGATIVE `removed` is the filter making that figure WORSE, "
          "and is not clamped.")
    print("  `removed` and the percentage are MAGNITUDES; the two columns "
          "before them keep")
    print("  their signs, which is what says WHICH WAY each estimate was "
          "wrong.")
    print("  the two scores span windows that differ by {:.3f} s at the "
          "start and {:.3f} s".format(out.span_gap_start_s,
                                      out.span_gap_end_s))
    print("  at the end: each is clipped to its own estimate's span, and "
          "the EKF joins the")
    print("  graph later than the wheel odometry does.")
    return score


def analyse_localization(cfg, path, profile, session, truth, fused,
                         withheld):
    """The ABSOLUTE pose - where the vehicle IS - against the same
    ground truth, and what the localiser cost to get it.

    THE SCORE IS THREE TRANSFORMS DEEP AND EVERY ONE OF THEM IS
    MEASURED, NONE OF THEM FITTED:

        map -> odom       the localiser's own edge, off /tf, as a
                          consumer of this stack would read it
        odom -> base_link the estimator's, at 50 Hz, composed onto it
        world <- map      the COMMITTED registration, derived once in
                          F3 Task 1 and frozen

    and what comes out is where this stack believes the vehicle is, in
    the building's own metres, beside where it actually was.

    NOTHING IS ANCHORED. No initial offset is removed, no per-run
    constant is fitted, and the estimate is not brought onto the truth at
    its first sample - which is global constraint 5 and the m5_ver1
    lineage's own withdrawn figure (WAREHOUSE_SLAM_EVIDENCE.md 12.8: an
    error measured by anchoring at the first sample is zero at the anchor
    BY CONSTRUCTION, and an estimator that is consistently 0.3 m wrong
    scores near zero).

    AND THE FLOOR IS STATED WITH THE FIGURE, EVERY TIME. The registration
    residual is the largest distance between a kept grid wall point and
    where the rigid transform says that wall is; no rigid transform fits
    this grid to this building better than that, so NO FIGURE AT OR BELOW
    IT IS A MEASUREMENT OF THE LOCALISER (EVIDENCE_MAP_V3.md 6.4). It is
    carried by the MapFrame itself so that this print site has it in hand.

    THE GRID IS CHECKED TWICE AND THE TWO CHECKS ARE DIFFERENT. The
    registration's own md5 gate says the transform belongs to the grid on
    disk NOW; the session's `loc=` label says which grid the RUN was
    taken against. A session recorded before a rebuild would pass the
    first and fail the second, and the figure it produced would be a map
    pose carried through a transform fitted to a different building.
    """
    loc = session.get("loc", "")
    if not localizer_of(loc):
        return None
    reg_path = os.path.join(_common.REPO, cfg.s("map.dir"),
                            cfg.s("map.name"),
                            cfg.s("map.registration.file"))
    try:
        record = map_register.load_registration(reg_path)
        frame = core.MapFrame.from_registration(record)
    except (map_core.MapError, core.EvidenceError) as exc:
        fail(cfg, exc, reg_path)
    # WHICH FROZEN ARTIFACT THIS SESSION's LABEL IS AN md5 OF, AND THE
    # TWO ARMS DO NOT ANSWER THE SAME. AMCL localises in the GRID, whose
    # md5 the committed registration carries because that is what it was
    # FITTED to; slam_toolbox localises in the POSE GRAPH, which the
    # registration says nothing about and which tools/build_map.sh
    # hashed into build.txt beside it. Each arm's label binds to the file
    # it actually opened.
    #   THE CHAIN IS STILL CLOSED ON BOTH ARMS, and on the slam arm it is
    #   one link longer: the session binds to the pose graph, build.txt
    #   binds that graph to the grid it was saved with, and
    #   load_registration() above has already bound the grid to this
    #   transform. A rebuild would break it at the first link.
    want = map_md5_of(loc)
    try:
        which = core.loc_md5_artifact(localizer_of(loc))
    except core.EvidenceError as exc:
        fail(cfg, exc, os.path.join(path, FILES["session"]))
    if which == "grid":
        got = str(record.get("map_md5", ""))
        owner = reg_path
        artifact_name = "a grid"
        owner_says = "the committed registration belongs to"
    else:
        build_path = os.path.join(_common.REPO, cfg.s("map.dir"),
                                  cfg.s("map.name"),
                                  cfg.s("map.build_file"))
        try:
            manifest = map_register.load_build_manifest(build_path)
        except (map_core.MapError, OSError) as exc:
            fail(cfg, exc, build_path)
        got = str(manifest.get(
            "md5_{}.{}".format(cfg.s("map.name"), which), ""))
        owner = build_path
        artifact_name = "a pose graph"
        owner_says = "the committed build manifest names one that"
    if want and not got.startswith(want):
        cfg.refuse(
            "this session was recorded against the map that is committed "
            "now",
            "{} (the loc= line) and {}".format(
                os.path.join(path, FILES["session"]), owner),
            "the session says it localised in {} whose md5 begins "
            "{!r};".format(artifact_name, want),
            "{} begins {!r}.".format(owner_says, got[:8]),
            "A REBUILT MAP HAS ITS OWN ROTATION FROM THE BUILDING (F3 "
            "constraint 16), so",
            "every absolute figure this session could produce would be a "
            "map pose carried",
            "through a transform fitted to a different grid - wrong by "
            "the difference,",
            "and with nothing in the numbers to say so.",
            "The ground truth, the raw wheel odometry and the fused "
            "estimate in this",
            "session are UNAFFECTED and are still its evidence.")

    edge_path = os.path.join(path, FILES["map_odom"])
    fused_path = os.path.join(path, FILES["ekf_odom"])
    if not os.path.isfile(edge_path) or not os.path.isfile(fused_path):
        print("")
        print("--- {} : NO ABSOLUTE POSE IN THIS SESSION ---".format(
            profile))
        print("  it is labelled {} and {} is not in the capture. Every "
              "figure above is".format(loc, FILES["map_odom"]))
        print("  the estimate in its OWN frame; nothing here says where "
              "the vehicle was.")
        withheld.append(os.path.basename(path))
        return None
    edge = table(edge_path, cfg, cfg.i("evidence.min_samples"))
    filtered = table(fused_path, cfg, cfg.i("evidence.min_samples"))

    print("")
    print("--- {} : the ABSOLUTE pose, against the same ground truth "
          "---".format(profile))
    print("  localiser       {}".format(loc))
    print("  registration    theta {:+.6f} rad, t ({:+.4f}, {:+.4f}) m "
          "- DERIVED, not asserted".format(
              frame.theta_rad, frame.t_x_m, frame.t_y_m))
    print("  INSTRUMENT FLOOR  {}".format(frame.floor()))

    try:
        in_map = core.compose_rows(
            edge.rows("t_sim", "x", "y", "yaw"),
            filtered.rows("t_sim", "x", "y", "yaw"),
            cfg.f("localization.analyse.map_gap_s"))
        in_world = core.rows_to_world(in_map, frame)
        score = core.score_drift(
            truth.rows("t_sim", "x", "y", "yaw"), in_world,
            core.world_frame(), cfg.f("evidence.analyse.max_pair_gap_s"))
    except core.EvidenceError as exc:
        fail(cfg, exc, path)

    print("  paired samples  {} over {:.3f} s of sim time".format(
        score.n, score.t1 - score.t0))
    print("  ground truth    {:.4f} m of path, turned {:+.4f} rad".format(
        score.truth_path_m, score.truth_turned_rad))
    print("  ABSOLUTE        {:.4f} m of path, turned {:+.4f} rad  "
          "({:+.2f} % of path)".format(
              score.est_path_m, score.est_turned_rad,
              100.0 * (score.est_path_m / score.truth_path_m - 1.0)
              if score.truth_path_m else float("nan")))
    print("  END ERROR       {:.4f} m   (dx {:+.4f}, dy {:+.4f}), heading "
          "{:+.4f} rad".format(score.end_error_m, score.end_dx, score.end_dy,
                               score.end_yaw_error_rad))
    print_track(score, "the absolute pose")
    print("  rms over run    {:.4f} m        worst {:.4f} m".format(
        score.rms_m, score.max_error_m))
    print("  ABSOLUTE IN BOTH SENSES: it is a position in the BUILDING, "
          "and no initial")
    print("  offset is removed from it. Read every figure above against "
          "the floor.")

    # WHAT THE ABSOLUTE LAYER BOUGHT, AND IT IS THE TABLE THIS PHASE
    # EXISTS FOR. F2 handed F3 a debt - an along-track error that grows
    # without bound because both of the filter's inputs are RATES
    # (EVIDENCE_FUSION.md 5, 8.5) - and this is the subtraction that says
    # whether the map paid it. compare_drift() is the same arithmetic
    # that measured what fusing bought over the raw estimate.
    if fused is not None:
        out = core.compare_drift(fused, score)
        print("")
        print("--- {} : what the MAP bought (odom-frame EKF -> absolute "
              "pose) ---".format(profile))
        print("  {:<16} {:>12} {:>12} {:>12} {:>10}".format(
            "figure", "EKF", "ABSOLUTE", "removed", "of EKF"))
        for label, unit, one in (("end error", "m", out.end_error),
                                 ("END HEADING", "rad", out.end_yaw),
                                 ("ALONG-track", "m", out.along),
                                 ("CROSS-track", "m", out.cross),
                                 ("rms over run", "m", out.rms),
                                 ("worst", "m", out.max_error)):
            print("  {:<16} {:>+12.4f} {:>+12.4f} {:>+12.4f} {:>9.1f}% "
                  "[{}]".format(label, one.before, one.after, one.removed,
                                100.0 * one.fraction, unit))
        print("  THE ALONG-TRACK ROW IS THE DEBT. Nothing in F2 could "
              "move it - no line of")
        print("  ekf.yaml changes the integral of a biased rate - and a "
              "map is the first")
        print("  thing on this track that observes where the vehicle IS.")
        print("  a NEGATIVE `removed` is the map making that figure "
              "WORSE, and is not clamped.")
        print("  the two scores span windows that differ by {:.3f} s at "
              "the start and {:.3f} s".format(out.span_gap_start_s,
                                              out.span_gap_end_s))
        print("  at the end: the localiser joins the graph after the "
              "filter does, because")
        print("  map_server has a 1712 x 1196 grid to read first.")

    # AND WHAT IT COST, WHICH IS THE OTHER HALF OF THE ANSWER. An
    # absolute localiser does not correct smoothly: a particle filter's
    # answer moves in STEPS and `map` -> `odom` moves with it, so a
    # controller reading map -> base_link sees the vehicle teleport. This
    # is the number a later phase's architecture decision turns on -
    # whether the absolute pose needs a second filter smoothing it - and
    # it is measured here rather than assumed either way.
    try:
        jumps = core.tf_jumps(edge.rows("t_sim", "x", "y", "yaw"))
    except core.EvidenceError as exc:
        fail(cfg, exc, edge_path)
    print("")
    # WHY THE BROADCAST RATE IS NOT A CORRECTION RATE, AND THE TWO ARMS
    # ARRIVE AT THAT FROM OPPOSITE DIRECTIONS. nav2_amcl re-sends this
    # edge on every SCAN (15 Hz); slam_toolbox re-sends it on a TIMER
    # (transform_publish_period, 50 Hz). Neither number counts
    # corrections and the line below has to say which one it is printing,
    # or a reader compares 15 with 50 and concludes something about the
    # localisers.
    print("--- {} : what the correction COST - map -> odom jump "
          "statistics ---".format(profile))
    print("  broadcasts      {} over {:.3f} s  ({:.2f} Hz - the {} arm "
          "re-sends this edge".format(
              jumps.samples, jumps.span_s,
              (jumps.samples - 1) / jumps.span_s if jumps.span_s else
              float("nan"), localizer_of(loc)))
    print("                  {}, whether or not it "
          "corrected)".format(
              "on a TIMER, transform_publish_period"
              if localizer_of(loc) == cfg.s("localization.slam.label")
              else "on EVERY SCAN"))
    if not jumps.n:
        print("  CORRECTIONS     0. The edge never changed: this "
              "localiser held the pose it")
        print("                  was seeded with for the whole run and "
              "corrected nothing.")
    else:
        print("  CORRECTIONS     {}  ({:.2f} per second of the run)".format(
            jumps.n, jumps.per_s if jumps.per_s is not None
            else float("nan")))
        print("  position step   mean {:.4f} m   median {:.4f} m   "
              "WORST {:.4f} m".format(
                  jumps.dpos.mean, jumps.dpos.median, jumps.max_dpos_m))
        print("  heading step    mean {:.5f} rad median {:.5f} rad  "
              "WORST {:.5f} rad".format(
                  jumps.dyaw.mean, jumps.dyaw.median, jumps.max_dyaw_rad))
        print("  a REPEAT IS NOT A CORRECTION: only a broadcast that "
              "DIFFERS from the one")
        print("  before it is counted, which is why these are dozens and "
              "not thousands.")

    # AND WHAT THE LOCALISER ITSELF SAID, WHICH IS NOT THE SAME STREAM.
    # The edge above is what a consumer reads; this is what the LOCALISER
    # believes, with its own covariance, published only when it updated.
    #   THE FILE KEEPS ITS NAME ON BOTH ARMS, which is `ekf_odom.csv`'s
    #   rule (that stream is filled by a factor graph on the --fuse arm
    #   and is still called ekf_odom): renaming a stream by arm would
    #   make the two arms' sessions structurally different, and two
    #   sessions that are not the same shape are not an A/B. The
    #   session's own `loc=` line says which localiser filled it.
    pose_path = os.path.join(path, FILES["amcl_pose"])
    if os.path.isfile(pose_path):
        poses = table(pose_path, cfg, 1)
        stamps = poses.column("t_sim")
        print("")
        print("--- {} : what the LOCALISER said about itself ---".format(
            profile))
        print("  updates         {} over {:.3f} s of sim time".format(
            len(stamps), stamps[-1] - stamps[0] if len(stamps) > 1 else 0.0))
        if len(stamps) > 1:
            rate = core.rate_from_stamps(stamps)
            print("                  {:.3f} Hz mean, longest gap "
                  "{:.3f} s".format(rate.hz_mean, rate.dt_max))
            # AND WHY IT PUBLISHES, WHICH IS ALSO NOT THE SAME. Both
            # arms are TRAVEL-gated rather than timed, and that is the
            # part worth saying twice - the gap column below is a
            # property of the ROUTE and the speed, not of the localiser's
            # health. What differs is the mechanism: amcl publishes when
            # the particle filter RESAMPLES, slam_toolbox on every scan
            # it PROCESSES.
            if localizer_of(loc) == cfg.s("localization.slam.label"):
                print("                  (it publishes on every scan it "
                      "PROCESSES, which is after")
                print("                   minimum_travel_distance of "
                      "travel and not on a timer)")
            else:
                print("                  (it publishes when the particle "
                      "filter RESAMPLES, which is")
                print("                   after update_min_d of travel "
                      "and not on a timer)")
        for axis, column in (("x", "cov_xx"), ("y", "cov_yy"),
                             ("yaw", "cov_yawyaw")):
            values = poses.column(column)
            stats = core.summarise(values)
            print("  covariance {:<4} first {:.6g}   last {:.6g}   worst "
                  "{:.6g}".format(axis, values[0], values[-1],
                                  stats.maximum))
        print("  THE COVARIANCE IS THE FILTER'S OWN OPINION AND NOT A "
              "SCORE. What it is worth")
        print("  against the truth is the table above; this says whether "
              "it knew.")
    return score


#: Everything both corner reductions read, prepared once. The two
#: reductions differ in WHICH stretches of the run they measure and in
#: nothing else, so they may not each build their own inputs - a
#: difference between the per-corner table and the sustained-corner
#: headline has to be the VEHICLE and never the arithmetic.
CornerInputs = collections.namedtuple(
    "CornerInputs",
    "profile target tread t_t tx ty tyaw speed t_j steer speed_at_joint")


def corner_inputs(cfg, path, session, truth, joints):
    """The ground truth and the steer reading, ready to be reduced.

    The target angle and the tread speed come from the PROFILE's own
    table - the segment with the largest steer - because the ratio is
    measured against what the table commanded. Everything else is
    measured.

    THE SPEED AND THE YAW RATE COME OFF THE GROUND TRUTH, differenced.
    Not off the estimate - the estimate is the thing being scored
    elsewhere - and not off a command, which is what the ratio is
    measured AGAINST.
      AND THE SPEED IS THE REAR AXLE'S, not base_link's. The ground truth
      is base_link, which in a turn carries a lateral term the axle does
      not; measured on corner_creep the difference is 1.7 %, on a ratio
      quoted to three figures.
    """
    profile = session.get("profile", "")
    rows = cfg.raw("drive_route.profiles").get(profile) or []
    target = 0.0
    tread = 0.0
    for row in rows:
        if abs(float(row["steer_rad"])) > abs(target):
            target = float(row["steer_rad"])
            tread = float(row["tread_mps"])
    if target == 0.0:
        return None

    steer_column = "{}_pos".format(cfg.s("wheel_odom.steer_joint_name"))
    t_j = joints.column("t_sim")
    steer = joints.column(steer_column)

    t_t = truth.column("t_sim")
    tyaw = core.unwrap(truth.column("yaw"))
    tx, ty = core.rear_axle_track(truth.column("x"), truth.column("y"),
                                  tyaw, cfg.f("vehicle.rear_axle_offset_m"))
    speed = [0.0]
    for i in range(1, len(t_t)):
        dt = t_t[i] - t_t[i - 1]
        speed.append(math.hypot(tx[i] - tx[i - 1], ty[i] - ty[i - 1]) / dt
                     if dt > 0 else 0.0)
    try:
        speed_at_joint = core.resample(
            t_t, speed, t_j, cfg.f("evidence.analyse.max_pair_gap_s"))
    except core.EvidenceError as exc:
        fail(cfg, exc, path + " (config.yaml evidence.analyse.*)")
    # THE STEER READING GOES THE OTHER WAY, ONTO THE TRUTH'S CLOCK, and
    # it is resampled PER WINDOW rather than here. The scrub split
    # differences the ground truth's own track, so its clock is the 20 Hz
    # one - but the two streams do not open on the same sim stamp (the
    # bridge connects them one at a time, and measured on
    # drive-corner_creep-20260826-071656 the joint stream opened 0.626 s
    # after the truth's). Resampling the WHOLE run would refuse on the
    # handful of truth samples before the joints existed, which no
    # reduction reads; a corner window is inside the held steer by
    # construction and therefore inside both spans. See measure_corner().
    return CornerInputs(profile=profile, target=target, tread=tread,
                        t_t=t_t, tx=tx, ty=ty, tyaw=tyaw, speed=speed,
                        t_j=t_j, steer=steer, speed_at_joint=speed_at_joint)


#: One window, measured. Written once and called from both reductions.
CornerMeasure = collections.namedtuple(
    "CornerMeasure", "fid yaw_rate rear held heading_in span inside split")


def measure_corner(cfg, path, inputs, window):
    """What the vehicle did over one window of a held corner.

    The yaw rate is the ENDPOINT difference over the window's own span
    rather than a mean of per-sample rates: the ground truth is exact and
    unwrapped, so two endpoints and a span carry no differencing noise at
    all, while a mean of 20 Hz differences would.
    """
    inside = [i for i, t in enumerate(inputs.t_t)
              if window.t0 <= t <= window.t1]
    if len(inside) < 2:
        cfg.refuse(
            "the ground truth carries samples inside the steady window",
            path, "the window is [{:.3f}, {:.3f}] s of sim time".format(
                window.t0, window.t1))
    span = inputs.t_t[inside[-1]] - inputs.t_t[inside[0]]
    yaw_rate = (inputs.tyaw[inside[-1]] - inputs.tyaw[inside[0]]) / span
    rear = core.mean([inputs.speed[i] for i in inside])
    held = core.mean([value for t, value in zip(inputs.t_j, inputs.steer)
                      if window.t0 <= t <= window.t1])
    fid = core.corner_fidelity(
        yaw_rate=yaw_rate, steer_rad=held,
        wheelbase_m=cfg.f("vehicle.wheelbase_m"),
        commanded_tread_mps=inputs.tread, measured_rear_mps=rear)
    # AND WHERE THE MISSING YAW WENT, over the same window and off the
    # same samples. fid says how much; this says which contact patch lost
    # it, and the two may not come from different windows.
    stamps = [inputs.t_t[i] for i in inside]
    try:
        split = core.scrub_split(
            stamps, [inputs.tx[i] for i in inside],
            [inputs.ty[i] for i in inside],
            [inputs.tyaw[i] for i in inside],
            core.resample(inputs.t_j, inputs.steer, stamps,
                          cfg.f("evidence.analyse.max_pair_gap_s")),
            wheelbase_m=cfg.f("vehicle.wheelbase_m"),
            tread_mps=inputs.tread)
    except core.EvidenceError as exc:
        fail(cfg, exc, path)
    return CornerMeasure(
        fid=fid, yaw_rate=yaw_rate, rear=rear, held=held,
        heading_in=core.normalise_angle(inputs.tyaw[inside[0]]),
        span=span, inside=inside, split=split)


def analyse_corner(cfg, path, inputs):
    """ONE sustained corner, against the kinematics it should obey.

    ONLY THE PROFILE config.yaml NAMES, and that is not fussiness: this
    reduction discards a 4 s settle and then averages everything left,
    which is right for a 14 s corner and wrong for square's 9.142 s ones.
    Repeated corners are analyse_corner_table()'s, with a reduction of
    their own.
    """
    if inputs.profile != cfg.s("evidence.corner.profile"):
        return None
    try:
        window = core.steady_window(
            inputs.t_j, inputs.steer, inputs.speed_at_joint, inputs.target,
            cfg.f("evidence.corner.steer_tol_rad"),
            cfg.f("evidence.corner.speed_min_mps"),
            cfg.f("evidence.corner.settle_s"),
            cfg.f("evidence.corner.window_s"))
    except core.EvidenceError as exc:
        fail(cfg, exc, path + " (config.yaml evidence.corner.*)")

    # THE WHOLE STEADY STATE IS AVERAGED, not the first window_s of it,
    # and that was measured rather than chosen. The delivered yaw rate
    # WANDERS inside a held corner - binned at 2 s on corner_creep it
    # runs 0.0722 to 0.0968 rad/s about a mean of 0.0812 - so a short
    # window lands wherever it lands: the first 6 s of that run's steady
    # state gave 0.0785 and the whole 13.6 s gave 0.0812, a 3 % swing
    # that is the sampling and not the vehicle. window_s is therefore the
    # MINIMUM stretch that will be accepted and never a cap, and the
    # wander itself is reported below rather than averaged away.
    got = measure_corner(cfg, path, inputs, window)
    fid = got.fid

    print("")
    print("--- {} : does the tricycle model hold at creep speed? ---"
          .format(inputs.profile))
    print("  steady window   [{:.3f}, {:.3f}] s of sim time, {} truth "
          "samples".format(window.t0, window.t1, len(got.inside)))
    print("  settle discarded {:g}s of held steer before it opened".format(
        cfg.f("evidence.corner.settle_s")))
    print("  steer commanded {:+.6f} rad     held (measured) {:+.6f} rad"
          .format(inputs.target, got.held))
    print("  tread commanded {:+.3f} m/s     ground speed (truth) "
          "{:.4f} m/s".format(inputs.tread, got.rear))
    print("  yaw rate        {:+.6f} rad/s  (ground truth, differenced "
          "over the window)".format(got.yaw_rate))
    # HOW STEADY THE STEADY STATE IS, printed rather than assumed. Sub
    # bins of bin_s across the same window: if the vehicle were tracking
    # a constant yaw rate these would all be the headline figure.
    bin_s = cfg.f("evidence.corner.bin_s")
    bins = []
    edge = window.t0
    while edge + bin_s <= window.t1:
        block = [i for i in got.inside
                 if edge <= inputs.t_t[i] <= edge + bin_s]
        if len(block) >= 2:
            span_b = inputs.t_t[block[-1]] - inputs.t_t[block[0]]
            bins.append((inputs.tyaw[block[-1]]
                         - inputs.tyaw[block[0]]) / span_b)
        edge += bin_s
    if len(bins) > 1:
        spread = core.summarise(bins)
        print("  its steadiness   {:g}s bins: {} of them, {:+.6f} to "
              "{:+.6f}, sd {:.6f} ({:.1%} of the mean)".format(
                  bin_s, spread.n, spread.minimum, spread.maximum,
                  spread.sd,
                  spread.sd / abs(got.yaw_rate) if got.yaw_rate else 0))
    print("")
    print("  kinematic v_tread*sin(d)/L  {:.6f} rad/s -> delivered "
          "{:.4f}".format(fid.kinematic_commanded, fid.ratio_commanded))
    print("  kinematic v_rear *tan(d)/L  {:.6f} rad/s -> delivered "
          "{:.4f}".format(fid.kinematic_measured, fid.ratio_measured))
    print("  the first carries longitudinal slip AND lateral scrub; the "
          "second only scrub.")
    print("  turning radius  kinematic {:.4f} m   MEASURED {:.4f} m".format(
        fid.kinematic_radius_m, fid.effective_radius_m))
    print_scrub_split(got.split, cfg.f("evidence.corner.split_min_deficit"))
    return fid


def split_is_informative(split, min_fraction):
    """Is the deficit big enough for a PERCENTAGE of it to mean anything?

    config.yaml's evidence.corner.split_min_deficit carries the whole
    reasoning. One predicate, used by both reductions, so the headline
    block and the per-corner table cannot disagree about when a share
    stops being a measurement.
    """
    if not split.kinematic:
        return False
    return abs(split.deficit / split.kinematic) >= min_fraction


def print_scrub_split(split, min_fraction):
    """WHICH CONTACT PATCH LOST THE YAW, printed under the ratio.

    A delivered fraction on its own does not say what to change. This
    block charges the deficit to the steered wheel and to the rear axle
    by an exact identity (evidence_core.scrub_split()), and the residual
    is printed so a reader can see the identity close rather than take
    it on the file's word.
    """
    print("")
    print("  --- where the yaw went: the steered wheel, or the rear axle? "
          "---")
    print("  rear-axle velocity in its own body frame: along {:+.6f} m/s, "
          "across {:+.6f} m/s".format(split.u_mps, split.rear_lat_mps))
    print("  steered contact:  across the wheel plane {:+.6f} m/s, along "
          "it {:+.6f} m/s".format(split.front_lat_mps,
                                  split.front_along_mps))
    print("  slip angles     steered {:+.4f} rad ({:+.2f} deg)   rear "
          "{:+.4f} rad ({:+.2f} deg)".format(
              split.front_slip_angle_rad,
              math.degrees(split.front_slip_angle_rad),
              split.rear_slip_angle_rad,
              math.degrees(split.rear_slip_angle_rad)))
    print("  the driven patch slides {:.6f} m/s in all, {:.1f} deg off its "
          "own wheel plane".format(
              split.front_slip_mps,
              math.degrees(split.front_slip_off_plane_rad)))
    print("  longitudinal slip AT THE STEERED CONTACT, in this corner: "
          "{:.4%}".format(split.tread_slip))
    print("  yaw budget      kinematic {:+.6f} = steered {:+.6f} + rear "
          "{:+.6f} + delivered {:+.6f}".format(
              split.kinematic, -split.front_term, -split.rear_term,
              split.yaw_rate))
    share = split.kinematic and split.deficit / split.kinematic
    if split_is_informative(split, min_fraction):
        print("  DEFICIT         {:+.6f} rad/s ({:.1%} of kinematic): "
              "steered wheel {:.1%}, rear axle {:.1%}".format(
                  split.deficit, share,
                  split.front_share, split.rear_share))
    else:
        print("  DEFICIT         {:+.6f} rad/s ({:.1%} of kinematic) - "
              "under config.yaml's".format(split.deficit, share))
        print("                  evidence.corner.split_min_deficit, so the "
              "two terms above are the reading")
        print("                  and no percentage of them is printed.")
    print("  identity closes to {:.3e} rad/s ({} intervals) - it is "
          "algebra, so this is rounding.".format(split.residual, split.n))


def analyse_corner_table(cfg, path, inputs):
    """EVERY held corner of the run, one row each.

    THIS IS THE INSTRUMENT FOR THE HEADING DEPENDENCE, and it exists
    because the headline reduction above cannot produce it: square turns
    four corners at ONE steer angle and ONE speed, and they do not
    deliver the same yaw rate as each other. EVIDENCE_SENSORS.md 4.2 uses
    that spread to qualify every scrub figure on this track, so it has to
    come out of the committed tool and not out of a hand reduction -
    which is the failure section 4 of that file criticises three
    paragraphs earlier.

    Both ends of every corner are trimmed, by config.yaml's
    evidence.corner.slew_in_s and .exit_s, and the count of corners FOUND
    is printed beside the count measured so a dropped one cannot go
    missing between them.
    """
    slew_in = cfg.f("evidence.corner.slew_in_s")
    exit_s = cfg.f("evidence.corner.exit_s")
    min_fraction = cfg.f("evidence.corner.split_min_deficit")
    try:
        runs = core.steady_runs(
            inputs.t_j, inputs.steer, inputs.speed_at_joint, inputs.target,
            cfg.f("evidence.corner.steer_tol_rad"),
            cfg.f("evidence.corner.speed_min_mps"),
            slew_in, exit_s, cfg.f("evidence.corner.window_s"))
    except core.EvidenceError as exc:
        fail(cfg, exc, path + " (config.yaml evidence.corner.*)")
    if not runs.windows:
        cfg.refuse(
            "at least one held corner survived the trim",
            path + " (config.yaml evidence.corner.slew_in_s, .exit_s, "
                   ".window_s)",
            "{} corner(s) were found at {:+.6f} rad and none of them kept "
            "{:g}s after {:g}s of slew-in and {:g}s of exit came off"
            .format(runs.found, inputs.target,
                    cfg.f("evidence.corner.window_s"), slew_in, exit_s))

    print("")
    print("--- {} : every held corner, at the SAME steer and the SAME "
          "speed ---".format(inputs.profile))
    print("  reduction       {:g}s of slew-in and {:g}s of exit off each "
          "corner".format(slew_in, exit_s))
    print("  corners found   {}   measured {}".format(
        runs.found, len(runs.windows)))
    # THE HELD ANGLE IS A COLUMN AND NOT AN ASSUMPTION. The kinematic
    # prediction every ratio is divided by uses the steer the axis
    # ACTUALLY held, not the angle the table asked for - the position
    # controller overshoots, and on this profile it does so by 0.009 rad,
    # which moves the ratio by 0.3 %. Printing it is what lets a reader
    # tell that difference from a difference in the vehicle.
    print("  {:>3} {:>17} {:>7} {:>11} {:>10} {:>10} {:>11} {:>10} "
          "{:>10} {:>10} {:>7}".format(
              "#", "window [s]", "span", "heading in", "held rad",
              "rear m/s", "yaw rate", "delivered", "steer lat", "rear lat",
              "front%"))
    out = []
    for n, window in enumerate(runs.windows, 1):
        got = measure_corner(cfg, path, inputs, window)
        out.append(got)
        # THE LAST THREE COLUMNS ARE THE SPLIT, ONE ROW PER CORNER. The
        # heading dependence is a fact about the delivered fraction, and
        # the question it raises immediately is whether the SAME contact
        # patch loses the yaw at every heading. Two slip velocities and
        # the steered wheel's share of the deficit answer it in the same
        # table rather than in a second reduction over the same windows.
        share = ("{:>6.1%}".format(got.split.front_share)
                 if split_is_informative(got.split, min_fraction) else
                 "{:>6}".format("-"))
        print("  {:>3} {:>8.2f}{:>9.2f} {:>7.2f} {:>+11.4f} {:>+10.6f} "
              "{:>10.4f} {:>+11.6f} {:>10.4f} {:>+10.6f} {:>+10.6f} "
              "{}".format(
                  n, window.t0, window.t1, got.span, got.heading_in,
                  got.held, got.rear, got.yaw_rate,
                  got.fid.ratio_commanded, got.split.front_lat_mps,
                  got.split.rear_lat_mps, share))
    if len(out) > 1:
        ratios = core.summarise([m.fid.ratio_commanded for m in out])
        print("  delivered       {:.4f} to {:.4f} over {} corners, "
              "spread {:.1%} of the mean".format(
                  ratios.minimum, ratios.maximum, ratios.n,
                  (ratios.maximum - ratios.minimum) / ratios.mean
                  if ratios.mean else 0))
        print("  every row is the same steer angle and the same commanded "
              "speed. What differs is")
        print("  the HEADING - see EVIDENCE_SENSORS.md 4.2.")
    return out


def traction_of(session):
    """One session's traction, as the one string everything compares by.

    The compliances are part of the key and not decoration: two slippery
    runs at different compliances are two different plants, and a table
    that mixed them would be as wrong as one that mixed wet with dry.
    A session written before F2 Task 2 has no key at all and says so
    rather than being read as nominal - see UNLABELLED.
    """
    label = session.get("traction", "")
    if not label:
        return UNLABELLED
    return "{} (slip compliance {} / {})".format(
        label, session.get("slip_compliance_lateral", "?"),
        session.get("slip_compliance_longitudinal", "?"))


#: What a session says about the ESTIMATOR that produced its fused
#: stream, when it was recorded before F2 Task 3 existed to label it.
#: Every one of those runs was in fact wheel+imu - `--rf2o` had not been
#: written - and this file will NOT write that over a blank, for
#: UNLABELLED's reason: the label is worth something only because it was
#: read off the running stack, and inferring it from an absence is
#: exactly the habit the whole chain guards against.
UNLABELLED_ARM = "unrecorded (session predates F2 Task 3's arm label)"


def arm_of(session):
    """One session's estimator arm, as the one string everything
    compares by.

    THE SECOND AXIS OF THE SAME QUESTION. `traction_of` says which PLANT
    a run was taken on; this says which ESTIMATOR was on it. The two are
    independent - all four combinations are legitimate runs and
    EVIDENCE_FUSION.md 10 uses three of them - so they are two labels
    and not one, and a set has to be uniform in both before it may be
    read out into one document.
    """
    label = session.get("arm", "")
    if not label:
        return UNLABELLED_ARM
    return label


#: What a session says about the ABSOLUTE LAYER when it was recorded
#: before F3 Task 2 existed to label it. Every one of those runs had no
#: localiser on it - `--localize` had not been written - and this file
#: will NOT write `none` over a blank, for UNLABELLED's reason: the
#: label is worth something only because it was read off the running
#: stack, and inferring it from an absence is exactly the habit the whole
#: chain guards against.
UNLABELLED_LOC = "unrecorded (session predates F3 Task 2's loc label)"


def loc_of(session):
    """One session's absolute layer, as the one string everything
    compares by.

    THE THIRD AXIS OF THE SAME QUESTION. `traction_of` says which PLANT,
    `arm_of` says which ESTIMATOR of the vehicle's own motion, and this
    says whether anything at all knew where that vehicle WAS - and
    against which map. All three are independent, all the combinations
    are legitimate runs, and a set has to be uniform in every one of
    them before it may be read out into one document.

    THE MAP's md5 IS PART OF THE KEY AND NOT DECORATION, exactly as the
    slip compliances are part of traction_of's. Two runs against two
    different grids are two different measurements, and a rebuilt map
    has its own rotation from the building (F3 constraint 16).
    """
    label = session.get("loc", "")
    if not label:
        return UNLABELLED_LOC
    return label


def _refuse_mixed(cfg, paths, sessions, label_of, subject, owner, why):
    """One `analyse` invocation, one <subject>.

    THE FAILURE THIS EXISTS TO PREVENT IS NOT A CRASH. Both `--slippery`
    and `--rf2o` produce a run that is identical to its opposite in
    every respect a table can see: same floor, same model file, same
    profiles, same CSV shape, same directory naming, same fused topic.
    Nothing downstream of the session file can tell one from the other -
    so the moment a run of each is read out by one command into one
    document, the only thing standing between a reader and a table with
    rows from two different things in it is that reader's attention.

    SO THE TOOL WILL NOT PRODUCE THAT DOCUMENT. It refuses, names every
    group and every session in it, and prints the commands that would
    have been right. It is deliberately not a warning: a warning scrolls
    off the top of a long analyse run, and every row under it still gets
    printed.

    ONE MECHANISM, TWO QUESTIONS. It was written for the traction label
    and generalised when the arm label needed exactly the same thing -
    because two copies of a MECHANISM drift the way two copies of a
    VALUE do, and the copy that gets fixed is the one that was right
    (tools/_common.sh's own argument).
    """
    groups = collections.OrderedDict()
    for path, session in zip(paths, sessions):
        groups.setdefault(label_of(session), []).append(
            os.path.basename(path))
    if len(groups) < 2:
        return
    lines = []
    for label, names in groups.items():
        lines.append("  {} - {} session(s):".format(label, len(names)))
        lines.extend("      " + name for name in names)
    lines.append("")
    lines.append("run one command per {}, for example:".format(subject))
    for label, names in groups.items():
        lines.append("  # {}".format(label))
        lines.append("  python3 m5_ver3/tools/sensor_evidence.py analyse \\")
        lines.append("      " + " \\\n      ".join(
            os.path.join(cfg.s("evidence.dir"), name) for name in names))
    cfg.refuse(
        "every session in this analyse is off the SAME {}".format(subject),
        "{} (the session.txt of each) and {}".format(
            session_root(cfg), owner),
        "{} different {}s are in this set:".format(len(groups), why),
        *lines)


def refuse_mixed_traction(cfg, paths, sessions):
    """One `analyse` invocation, one plant. See _refuse_mixed."""
    _refuse_mixed(cfg, paths, sessions, traction_of, "plant",
                  "{} (paths.traction_file)".format(_common.CONFIG),
                  "traction")


def refuse_mixed_arm(cfg, paths, sessions):
    """One `analyse` invocation, one estimator. See _refuse_mixed.

    THE ARM IS THE MORE DANGEROUS OF THE TWO TO MIX, because the whole
    of EVIDENCE_FUSION.md 10 is an A/B between the arms and its columns
    are the SAME columns. A slippery run in a dry table at least reads
    oddly; a wheel+imu run in an rf2o table reads as the arm making no
    difference, which is one of the answers the A/B could honestly have
    reached, and there would be nothing in the numbers to say it was not
    the one measured.
    """
    _refuse_mixed(cfg, paths, sessions, arm_of, "estimator arm",
                  "{} (the arm= line m5v3.sh writes)".format(_common.CONFIG),
                  "estimator arm")


def refuse_mixed_loc(cfg, paths, sessions):
    """One `analyse` invocation, one absolute layer. See _refuse_mixed.

    AND IT IS THE ONE WHOSE MIX IS HARDEST TO SEE. A slippery run in a
    dry table at least reads oddly and a wheel+imu run in an rf2o table
    reads as the arm making no difference; a localised run beside an
    unlocalised one produces tables that are simply MISSING a block for
    half the set, which reads as a recording that went wrong rather than
    as two different experiments in one document.
      IT ALSO SEPARATES TWO MAPS. The label carries the grid's md5, so a
      set half-recorded against a rebuild is refused by the same
      mechanism - which is what makes F3 constraint 16 reach the
      analysis and not only the bringup.
    """
    _refuse_mixed(cfg, paths, sessions, loc_of, "absolute layer",
                  "{} (the loc= line m5v3.sh writes)".format(_common.CONFIG),
                  "absolute layer")


def analyse_session(cfg, path, sensors, diverged, withheld):
    session = read_session_file(cfg, path)
    print("")
    print("=" * 72)
    print("session  {}".format(os.path.basename(path)))
    print("kind     {}   profile {}   recorded {}".format(
        session.get("kind", "?"), session.get("profile", "-"),
        session.get("recorded", "?")))
    print("TRACTION {}".format(traction_of(session)))
    print("ARM      {}".format(arm_of(session)))
    print("LOC      {}".format(loc_of(session)))
    if session.get("loc_source"):
        print("         {}".format(session["loc_source"]))
    if session.get("arm_source"):
        print("         {}".format(session["arm_source"]))
    if session.get("drive_exit", "") not in ("", "0"):
        print("WARNING  drive_route.py exited {} on this run".format(
            session["drive_exit"]))
    if session.get("kind") == "drive":
        _, truth, est, joints = analyse_drive(cfg, path, session,
                                              sensors, diverged, withheld)
        # ONE PREPARATION, TWO REDUCTIONS. See CornerInputs.
        inputs = corner_inputs(cfg, path, session, truth, joints)
        if inputs is not None:
            analyse_corner(cfg, path, inputs)
            analyse_corner_table(cfg, path, inputs)
        print("")
        print("--- delivered rates over the drive, ROS side ---")
        print("  {:<16} {:>9} {:>10} {:>10} {:>8} {:>10} {:>10} {:>7}".format(
            "stream", "samples", "hz_sim", "hz_wall", "of conf", "dt_med",
            "dt_max", "rtf"))
        for name in ("clock", "odom_truth", "wheel_odom", "ekf_odom",
                     "rf2o_odom", "map_odom", "amcl_pose", "joint_state",
                     "drive_read_a", "scan_nav", "imu", "depth", "cam_info"):
            full = os.path.join(path, FILES[name])
            # ekf_odom is the one stream a pre-F2 session does not carry
            # and rf2o_odom is the one only the rf2o arm has. Both are
            # skipped rather than refused, and analyse_fused() has
            # already said so in full above for the first; a refusal here
            # would make F1's own sessions unreadable by the tool that
            # produced their figures, and every wheel+imu session
            # unreadable by the tool that produced the A/B they are half
            # of. The ARM line at the top of this session's block is
            # what says which of the two an absent rf2o_odom means.
            if name in ("ekf_odom", "rf2o_odom", "map_odom",
                        "amcl_pose") and not os.path.isfile(full):
                continue
            one = table(full, cfg, cfg.i("evidence.min_samples"))
            rate_line(cfg, name, one.column("t_sim"), one.column("t_wall"))
        # THE FIRST SUBSCRIPTION MADE CAN CATCH A BACKLOG, and it shows up
        # here rather than being trimmed away. Measured on a straight run:
        # clock's capture opens at sim 10.862 and wheel_odom's at 11.430,
        # both close at 51.63, and both cover the same 40.22 s of WALL -
        # so clock's rtf column reads 1.0135 where the eight streams
        # behind it read 0.9994-0.9996. That is 0.57 s of sim delivered
        # in one burst as the subscription connected, not a world running
        # fast. The hz_sim column is unaffected: it is the plant's own
        # stamps and it reads 500.0000 either way.
        print("  (the first stream to connect can catch a backlog: its "
              "rtf column reads high by")
        print("   whatever the bridge had in flight. hz_sim is the "
              "plant's own stamp and is not affected.)")
    else:
        analyse_static(cfg, path, sensors)

    print("")
    print("--- the capture, by md5 (the CSVs stay out of the repository) ---")
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        if os.path.isfile(full):
            print("  {}  {:>12}  {}".format(md5(full), os.path.getsize(full),
                                            name))


def analyse(cfg, args):
    model = os.path.join(_common.REPO, cfg.s("vehicle.model"))
    try:
        sensors = core.sdf_sensors(model)
    except core.EvidenceError as exc:
        fail(cfg, exc, model)

    print("=== m5v3 sensor evidence: analyse ===")
    print("model      {}".format(cfg.s("vehicle.model")))
    print("sensors    {}".format(", ".join(sensors)))
    print("")
    print("--- configured, read out of the model and not out of "
          "config.yaml ---")
    print("  {:<22} {:<12} {:>6} {:>10} {:>10} {:>10} {:>10}".format(
        "sensor", "noise type", "rate", "stddev", "bias_mean", "bias_sd",
        "samples"))
    for name, spec in sensors.items():
        for channel, noise in spec["noise"].items():
            print("  {:<22} {:<12} {:>6} {:>10} {:>10} {:>10} {:>10}".format(
                "{} [{}]".format(name, channel), noise["type"] or "-",
                spec["update_rate"], noise["stddev"],
                noise["bias_mean"] if noise["bias_mean"] is not None else "-",
                noise["bias_stddev"]
                if noise["bias_stddev"] is not None else "-",
                spec.get("samples", "-")))
    # THE CROSS-CHECK EVIDENCE_MODEL_V3.md USED TO DO BY HAND. config.yaml
    # repeats these rates for the shells; the SDF decides them. A
    # disagreement is a config.yaml that has drifted away from the plant.
    for key, sensor_key in (("nav_lidar", "nav_lidar"),
                            ("safety_scanner", "safety_scanner"),
                            ("lidar_3d", "lidar_3d"), ("imu", "imu"),
                            ("pallet_cam", "pallet_cam")):
        name = cfg.s("evidence.sdf_names." + sensor_key)
        configured = cfg.f("sensors.{}.rate_hz".format(key))
        actual = sensors[name]["update_rate"]
        if abs(configured - actual) > 1e-9:
            print("  WARNING config.yaml sensors.{}.rate_hz is {} and the "
                  "model says {}".format(key, configured, actual))

    # THE ESTIMATOR'S OWN SETTINGS, PRINTED RATHER THAN COPIED BY HAND.
    # EVIDENCE_SENSORS.md 3 opens with this line because every drift
    # figure under it is a figure about THIS estimator - and a settings
    # line typed into a markdown file is a claim that nothing re-checks.
    # These are the same keys nodes/wheel_odometry.py hands to
    # wheel_odom_core.WheelOdometry, read from the same file, so a
    # config.yaml retuned since the CSVs were recorded shows up here as a
    # disagreement with the evidence file instead of quietly scoring the
    # old run under the new numbers.
    #   IT IS NOT READ OUT OF THE MODEL, and that is the difference
    #   between this block and the one above it. The SDF owns the PLANT;
    #   config.yaml owns what the vehicle BELIEVES about itself, and the
    #   gap between the two is the entire subject of section 3.
    counts = cfg.i("wheel_odom.counts_per_rev")
    radius = cfg.f("vehicle.wheel_radius_m")
    scale = cfg.f("wheel_odom.wheel_radius_scale")
    quantum_rad = 2.0 * math.pi / counts
    print("")
    print("--- the estimator's settings, read out of config.yaml and NOT "
          "out of the model ---")
    print("  vehicle          {}".format(cfg.s("vehicle.name")))
    print("  encoder          {} counts/rev   one count {:.5e} rad of "
          "shaft, {:.4f} mm of tread".format(
              counts, quantum_rad, quantum_rad * radius * 1000.0))
    print("    (the tread figure is at the PLANT's {:.3f} m wheel; the "
          "estimator steps {:.4f} mm".format(
              radius, quantum_rad * radius * scale * 1000.0))
    print("     per count because it believes the radius below)")
    print("  believed radius  {:.4f} m   = {:.3f} x {:.4f}, a deliberate "
          "{:+.1f} % scale error".format(
              radius * scale, radius, scale, (scale - 1.0) * 100.0))
    print("  steer bias       {:+.4f} rad, added to the READING and never "
          "to a command".format(cfg.f("wheel_odom.steer_bias_rad")))
    print("  no slip term, no ground truth, no transform - the plant "
          "produces the slip and F2 owns the edge")

    # THE FILTER'S OWN SETTINGS, PRINTED FOR THE REASON THE BLOCK ABOVE
    # IS. EVIDENCE_FUSION.md's tables are figures about ONE filter
    # configuration, and a configuration line typed into a markdown file
    # is a claim nothing re-checks. What is printed is what m5v3.sh
    # actually passes ekf_node: the two topics it reads, the one it
    # writes, the transform it owns and the rate it runs at. What is
    # FUSED is ekf.yaml's - two fifteen-entry matrices this file will not
    # paraphrase - and the path to it is printed so a reader can open the
    # file that decides it.
    print("")
    print("--- the filter's settings, read out of config.yaml and NOT out "
          "of ekf.yaml ---")
    print("  in               {}  (twist only; its pose covariance is a "
          "do-not-fuse flag)".format(cfg.s("topics.wheel_odom")))
    # "yaw rate and ax" UNTIL F2 TASK 3 READ IT, and it had been wrong
    # since F2 Task 2 reversed the ax ruling on a measurement
    # (EVIDENCE_FUSION.md 9). A settings line that describes a channel
    # the filter has not fused since the day before is the exact failure
    # this whole block exists to prevent, one level up.
    print("                   {}  (yaw rate ONLY - the acceleration "
          "channel is refused, EVIDENCE_FUSION.md 9)".format(
              cfg.s("topics.imu")))
    print("  in, optionally   {}  (the rf2o arm's twist, vx and vyaw; "
          "present only on a".format(cfg.s("topics.rf2o_odom")))
    print("                   session whose ARM line below says "
          "wheel+imu+rf2o - {})".format(cfg.s("ekf.rf2o_params_file")))
    print("  out              {} at {} Hz".format(
        cfg.s("topics.odometry_filtered"), cfg.s("ekf.frequency_hz")))
    # AND THE OTHER ESTIMATOR'S OUT, WHICH IS A DIFFERENT ADDRESS AND
    # NOT A DIFFERENT COLUMN. On a `fuse:` session the `ekf_odom` stream
    # below was filled from this topic by a factor graph and not by
    # ekf_node; the CSV keeps its name so that the two arms' sessions are
    # structurally identical, which is what makes them comparable, and
    # the ARM line under each session is what says which. F2 Task 4,
    # EVIDENCE_FUSION.md 11.
    print("  out, on --fuse   {} at the same {} Hz, from fuse's".format(
        cfg.s("topics.fuse_odometry_filtered"), cfg.s("ekf.frequency_hz")))
    print("                   fixed-lag smoother instead - ekf_node is "
          "not started on that arm ({})".format(cfg.s("fuse.params_file")))
    print("  transform        {} -> {}   (the only one this stack "
          "publishes)".format(cfg.s("frames.odom"),
                              cfg.s("frames.base_link")))
    print("  static transform {} -> {} at ({}, {}, {}) - without it "
          "robot_localization".format(
              cfg.s("frames.base_link"), cfg.s("frames.imu"),
              cfg.s("vehicle.imu_mount.x"), cfg.s("vehicle.imu_mount.y"),
              cfg.s("vehicle.imu_mount.z")))
    print("                   drops the IMU entirely and logs nothing")
    print("  what is fused    {} - two matrices, and the argument for "
          "each entry".format(cfg.s("ekf.params_file")))

    # AND THE LOCALISER'S, FOR THE TWO BLOCKS ABOVE'S REASON. Every
    # absolute figure below is a figure about ONE map and ONE parameter
    # file, and a configuration line typed into a markdown file is a
    # claim nothing re-checks. What is printed is what m5v3.sh actually
    # passes the two nodes - the artifact, the topics, the frames and the
    # edge - plus the md5 of the grid on disk, which is what binds the
    # numbers to an artifact rather than to a name. What the LOCALISER
    # DOES is amcl.yaml's, and the path to it is printed so a reader can
    # open the file that decides it.
    print("")
    print("--- the localiser's settings, read out of config.yaml and NOT "
          "out of amcl.yaml ---")
    print("  map              {}/{}  ({})".format(
        cfg.s("map.dir"), cfg.s("map.name"),
        cfg.s("map.registration.file")))
    try:
        _reg = map_register.load_registration(
            os.path.join(_common.REPO, cfg.s("map.dir"), cfg.s("map.name"),
                         cfg.s("map.registration.file")))
    except (map_core.MapError, core.EvidenceError) as exc:
        fail(cfg, exc, cfg.s("map.dir"))
    print("  grid md5         {}  (verified against the committed "
          "registration)".format(_reg.get("map_md5", "?")))
    # AND THE POSE GRAPH's, WHICH THE REGISTRATION DOES NOT CARRY. The
    # slam arm opens the .posegraph and the .data and never the grid, so
    # its label is an md5 of the graph and build.txt is where that hash
    # is committed. It is printed on BOTH arms: the manifest is what says
    # the two artifacts came out of one build, and a reader comparing the
    # two arms' tables needs to see that they did.
    try:
        _build = map_register.load_build_manifest(
            os.path.join(_common.REPO, cfg.s("map.dir"), cfg.s("map.name"),
                         cfg.s("map.build_file")))
    except (map_core.MapError, OSError) as exc:
        fail(cfg, exc, cfg.s("map.build_file"))
    print("  graph md5        {}  ({}, the same build)".format(
        _build.get("md5_{}.posegraph".format(cfg.s("map.name")), "?"),
        cfg.s("map.build_file")))
    print("  registration     theta {:+.9f} rad, t ({:+.6f}, {:+.6f}) m"
          .format(_reg["theta_rad"], _reg["t_x_m"], _reg["t_y_m"]))
    print("  INSTRUMENT FLOOR residual rms {:.4f} m, MAX {:.4f} m - NO "
          "ABSOLUTE FIGURE".format(_reg["residual_rms_m"],
                                   _reg["residual_max_m"]))
    print("                   AT OR BELOW THE MAX IS A MEASUREMENT OF "
          "THE LOCALISER")
    print("  in               {}  (the nav lidar, and nothing else - no "
          "safety scanner,".format(cfg.s("topics.scan_nav")))
    print("                   no 3D lidar, no ground truth)")
    print("                   {} -> {} on {}, published by the "
          "estimator".format(cfg.s("frames.odom"), cfg.s("frames.base_link"),
                             cfg.s("topics.tf")))
    print("  out              {} -> {} on {} - the ONE edge this phase "
          "adds,".format(cfg.s("frames.map"), cfg.s("frames.odom"),
                         cfg.s("topics.tf")))
    # AND THE LAST THREE ROWS ARE PRINTED FOR BOTH ARMS, WHICH IS WHAT
    # THIS BLOCK IS. It is the CONFIGURATION read out of config.yaml, not
    # a description of the set below it - the set says which arm it was
    # on, once per session, on its own LOC line - and since F3 Task 3
    # there are two localisers that differ in exactly the three things a
    # reader would otherwise have to guess: where each publishes its own
    # pose, how each is told where it starts, and which file decides what
    # it does.
    print("                   plus, on the {} arm, {} when the filter "
          "updates".format(cfg.s("localization.amcl.label"),
                           cfg.s("topics.amcl_pose")))
    print("                   plus, on the {} arm, {} on every processed "
          "scan".format(cfg.s("localization.slam.label"),
                        cfg.s("topics.slam_pose")))
    print("  seeded, {:<8} {} at bringup, from vehicle.spawn through the "
          "registration".format(cfg.s("localization.amcl.label"),
                                cfg.s("topics.initialpose")))
    print("                   above - a MESSAGE, and this stack's "
          "operator gesture")
    print("  seeded, {:<8} map_start_pose, a PARAMETER read on the "
          "configure transition,".format(cfg.s("localization.slam.label")))
    print("                   from the same spawn pose through the same "
          "registration.")
    print("                   Nothing is published on {} on that "
          "arm.".format(cfg.s("topics.initialpose")))
    print("                   NEITHER IS A KIDNAPPED-ROBOT RECOVERY. Both "
          "arms track from")
    print("                   a known start and no figure below is "
          "evidence they could not.")
    print("  what it does     {} - the motion model, the sensor model "
          "and the".format(cfg.s("localization.amcl.params_file")))
    print("                   argument for every value in both")
    print("                   {} - the mode, the travel gates, the "
          "running".format(cfg.s("localization.slam.params_file")))
    print("                   scan and the loop closure")
    # THE SAME CROSS-CHECK THE RATES GET, AND FOR THE SAME REASON. The
    # SDF decides where the IMU is bolted; config.yaml copies it because
    # a shell cannot read XML. A disagreement is a copy that has gone
    # stale, and it would move a transform this filter depends on.
    try:
        pose = core.sdf_link_pose(model, cfg.s("frames.imu"))
    except core.EvidenceError as exc:
        fail(cfg, exc, model)
    for i, axis in enumerate(("x", "y", "z")):
        configured = cfg.f("vehicle.imu_mount." + axis)
        if abs(configured - pose[i]) > 1e-9:
            print("  WARNING config.yaml vehicle.imu_mount.{} is {} and "
                  "the model says {}".format(axis, configured, pose[i]))
    if any(abs(value) > 1e-9 for value in pose[3:]):
        print("  WARNING the model mounts {} with a ROTATION {} and the "
              "static transform publishes none".format(
                  cfg.s("frames.imu"), pose[3:]))

    root = session_root(cfg)
    if args.session:
        paths = [os.path.abspath(p) for p in args.session]
    else:
        if not os.path.isdir(root):
            cfg.refuse("there is a session to analyse", root,
                       "no directory at all - run `record` first.")
        paths = [os.path.join(root, name) for name in sorted(os.listdir(root))
                 if os.path.isdir(os.path.join(root, name))]
    if not paths:
        cfg.refuse("there is a session to analyse", root,
                   "the directory is empty - run `record` first.")
    # THE SET IS CHECKED BEFORE THE FIRST TABLE IS PRINTED. Both plants
    # produce a healthy-looking session, so the guard has to be up front:
    # refusing halfway through leaves the reader with a document that is
    # already half wrong and no obvious mark where it went bad.
    #   AND THE SET IS CHECKED ON BOTH AXES. Since F2 Task 3 a session
    #   also carries which ESTIMATOR produced its fused stream, and the
    #   two questions are independent: a set can be all-nominal and
    #   still be half wheel+imu and half wheel+imu+rf2o, which is the
    #   mix EVIDENCE_FUSION.md 10's whole A/B would be destroyed by.
    _sessions = [read_session_file(cfg, p) for p in paths]
    refuse_mixed_traction(cfg, paths, _sessions)
    refuse_mixed_arm(cfg, paths, _sessions)
    # AND ON THE THIRD AXIS SINCE F3 TASK 2. A set can be all-nominal and
    # all-wheel+imu and still be half localised, which is the mix
    # EVIDENCE_LOCALIZATION_V3.md's whole comparison would be destroyed
    # by - and the difference between the two is one edge on /tf that no
    # table has a column for.
    refuse_mixed_loc(cfg, paths, _sessions)
    # EVERY SESSION WHOSE FILTER HAD BLOWN UP, COLLECTED WHILE THE
    # TABLES ARE PRINTED AND REPORTED IN THE EXIT STATUS. See
    # analyse_fused(): the run's ground truth and raw wheel odometry are
    # still evidence and are still printed, and no FUSED figure from it
    # is. A reader who scrolled past the block gets it again at the end;
    # a SCRIPT gets it in `$?`, which is the reader that never scrolls.
    diverged = []
    # AND EVERY SESSION WHOSE ABSOLUTE FIGURES WERE WITHHELD, kept apart
    # from the diverged ones because they are a different fault: a
    # session labelled as localised whose localiser stream is not in the
    # capture. The exit is non-zero either way, and the two are named
    # separately so a reader is not sent to the wrong log.
    withheld = []
    for path in paths:
        analyse_session(cfg, path, sensors, diverged, withheld)
    if withheld:
        print("")
        print("=" * 72)
        print("{} of the {} session(s) above are LABELLED LOCALISED and "
              "carry no absolute".format(len(withheld), len(paths)))
        print("figures: {}".format(", ".join(withheld)))
        print("their localiser stream is not in the capture. This exit "
              "is NON-ZERO.")
    if diverged:
        print("")
        print("=" * 72)
        print("{} of the {} session(s) above had a DIVERGED FILTER and "
              "carry no fused".format(len(diverged), len(paths)))
        print("figures: {}".format(", ".join(diverged)))
        print("ekf_node's startup divergence, EVIDENCE_FUSION.md 8.6. "
              "This exit is NON-ZERO.")
    if diverged or withheld:
        return 1
    return 0


# ----------------------------------------------------------------------

def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    profiles = cfg.raw("drive_route.profiles")
    parser = argparse.ArgumentParser(
        description="record what this plant's sensors deliver, and score "
                    "its own estimate of its motion against the ground "
                    "truth. `record` needs ROS; `analyse` needs nothing.",
        epilog="every constant lives in m5_ver3/config.yaml under "
               "evidence:, and every configured sensor figure is read "
               "out of the model itself.")
    subparsers = parser.add_subparsers(dest="command")
    recorder = subparsers.add_parser(
        "record", help="capture one run off the live plant")
    group = recorder.add_mutually_exclusive_group(required=True)
    group.add_argument("--static", action="store_true",
                       help="the vehicle AT REST, for the noise and rate "
                            "figures")
    group.add_argument("--drive", metavar="PROFILE",
                       choices=sorted(profiles) if isinstance(profiles, dict)
                       else [],
                       help="drive one of config.yaml's profiles and record "
                            "the whole of it")
    recorder.add_argument(
        "--bag", action="store_true",
        help="ALSO write a rosbag2 of config.yaml's evidence.bag.topics "
             "into the session, for an OFFLINE consumer - F3's "
             "slam_toolbox run is the one there is. Off by default: it "
             "is about 150 MB over a mapping drive and nothing in "
             "EVIDENCE_SENSORS or EVIDENCE_FUSION reads it.")
    reader = subparsers.add_parser(
        "analyse", help="read recorded sessions and print the tables "
                        "(no ROS, no Gazebo)")
    reader.add_argument("session", nargs="*",
                        help="session directories; default is every session "
                             "under evidence.dir. ONE PLANT PER "
                             "INVOCATION: a set mixing nominal and "
                             "--slippery sessions is refused, with both "
                             "groups named and the two commands that "
                             "would have been right")
    args = parser.parse_args(argv)
    if args.command == "record":
        return record(cfg, args)
    if args.command == "analyse":
        return analyse(cfg, args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\nsensor_evidence: interrupted.\n")
        sys.exit(130)
