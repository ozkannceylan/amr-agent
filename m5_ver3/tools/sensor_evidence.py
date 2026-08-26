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
import struct
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as core                          # noqa: E402

TOOL = "sensor_evidence"

# MAINTENANCE OBLIGATION: a key read below is a key listed here. Refused
# by its DOTTED name before a single subscription is made or a single CSV
# is opened.
REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id", "paths.ros_setup",
    "topics.clock", "topics.odom_ground_truth", "topics.scan_nav",
    "topics.imu", "topics.cam_depth", "topics.cam_info",
    "topics.joint_state", "topics.drive_speed_read_a", "topics.wheel_odom",
    "topics.odometry_filtered",
    "topics.safety_scan_back", "topics.points3d",
    "frames.odom", "frames.base_link", "frames.imu",
    "vehicle.imu_mount.x", "vehicle.imu_mount.y", "vehicle.imu_mount.z",
    "ekf.frequency_hz", "ekf.params_file",
    "world.file", "vehicle.model", "vehicle.name",
    "vehicle.spawn.x", "vehicle.spawn.y", "vehicle.spawn.yaw",
    "vehicle.wheelbase_m", "vehicle.wheel_radius_m",
    "vehicle.rear_axle_offset_m",
    "wheel_odom.drive_joint_name", "wheel_odom.steer_joint_name",
    "wheel_odom.counts_per_rev", "wheel_odom.wheel_radius_scale",
    "wheel_odom.steer_bias_rad",
    "drive_route.profiles",
    "evidence.dir", "evidence.wait_first_s", "evidence.min_samples",
    "evidence.qos_depth", "evidence.static.record_s",
    "evidence.drive.pre_roll_s", "evidence.drive.post_roll_s",
    "evidence.drive.timeout_factor", "evidence.drive.timeout_margin_s",
    "evidence.depth.patch_half",
    "evidence.safety.frames", "evidence.safety.capture_timeout_s",
    "evidence.gz_rate.topics", "evidence.gz_rate.sample_s",
    "evidence.gz_rate.timeout_s",
    "evidence.analyse.spawn_tolerance_m",
    "evidence.analyse.spawn_tolerance_rad",
    "evidence.analyse.max_pair_gap_s", "evidence.analyse.noise_factor",
    "evidence.analyse.clamp_tolerance_m",
    "evidence.corner.profile",
    "evidence.corner.settle_s", "evidence.corner.window_s",
    "evidence.corner.bin_s",
    "evidence.corner.steer_tol_rad", "evidence.corner.speed_min_mps",
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


def write_session_file(path, fields):
    with open(os.path.join(path, FILES["session"]), "w",
              encoding="utf-8") as handle:
        for key, value in fields:
            handle.write("{}={}\n".format(key, value))


def describe_session(cfg, session, node, profile, started_wall, exit_code,
                     safety_rows):
    """What this run was, written beside what it recorded.

    IT IS WHAT MAKES A DIRECTORY OF CSVs A SESSION. `analyse` reads
    `kind` to know whether to score a drive or a static capture and
    `profile` to know which table in config.yaml the corner angle came
    from - neither of which any CSV can say for itself. It is written on
    the way out of EVERY path, including the two that refuse, so a run
    that went wrong is still a run somebody can open.
    """
    write_session_file(session, [
        ("kind", "drive" if profile else "static"),
        ("profile", profile or ""),
        ("recorded", datetime.datetime.now().isoformat()),
        ("partition", cfg.s("isolation.gz_partition")),
        ("model", cfg.s("vehicle.model")),
        ("spawn", "{} {} {}".format(cfg.s("vehicle.spawn.x"),
                                    cfg.s("vehicle.spawn.y"),
                                    cfg.s("vehicle.spawn.yaw"))),
        ("drive_started_wall", started_wall),
        ("drive_exit", exit_code),
        ("safety_frames", safety_rows),
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

        def __init__(self, session):
            super().__init__("m5v3_sensor_evidence")
            self.cfg = cfg
            self.session = session
            self.writers = collections.OrderedDict(
                (name, Writer(os.path.join(session, FILES[name])))
                for name in ("clock", "odom_truth", "wheel_odom",
                             "ekf_odom", "scan_nav",
                             "imu", "depth", "cam_info", "joint_state",
                             "drive_read_a"))
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
            self.create_subscription(
                types.Odometry, cfg.s("topics.odometry_filtered"),
                self.cb_fused, qos)
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

        def missing(self):
            return [name for name, writer in self.writers.items()
                    if writer.n == 0]

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
        from nav_msgs.msg import Odometry
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from rosgraph_msgs.msg import Clock
        from sensor_msgs.msg import (CameraInfo, Image, Imu, JointState,
                                     LaserScan)
    except ImportError as exc:
        _common.refuse(
            TOOL, "rclpy is importable", _common.CONFIG + " (paths.ros_setup)",
            "python3 could not import ROS 2: {}".format(exc),
            "`record` runs INSIDE WSL with /opt/ros/jazzy sourced:",
            "  source {}".format(cfg.s("paths.ros_setup")),
            "`analyse` needs none of this and runs anywhere.")

    types = collections.namedtuple(
        "Types", "Clock Odometry LaserScan Imu Image CameraInfo JointState")(
            Clock, Odometry, LaserScan, Imu, Image, CameraInfo, JointState)

    kind = "drive" if args.drive else "static"
    name = args.drive or "rest"
    session = new_session(cfg, kind, name)
    print("=== m5v3 sensor evidence: record ===")
    print("date       {}".format(datetime.datetime.now().isoformat()))
    print("partition  {}".format(cfg.s("isolation.gz_partition")))
    print("session    {}".format(session))
    print("mode       {}".format(
        "drive " + args.drive if args.drive else "static, vehicle at rest"))
    sys.stdout.flush()

    rclpy.init(args=None)
    node = _make_recorder(cfg, Node, QoSProfile, types)(session)
    drive_exit = ""
    drive_started_wall = ""
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
                    node.close()
                    describe_session(cfg, session, node, args.drive,
                                     drive_started_wall, "TIMED OUT", 0)
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
                     drive_exit, safety_rows)

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


def analyse_drive(cfg, path, session, sensors):
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
    analyse_fused(cfg, path, profile, spawn, truth, score)
    return score, truth, est, joints


def analyse_fused(cfg, path, profile, spawn, truth, raw):
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


def analyse_session(cfg, path, sensors):
    session = read_session_file(cfg, path)
    print("")
    print("=" * 72)
    print("session  {}".format(os.path.basename(path)))
    print("kind     {}   profile {}   recorded {}".format(
        session.get("kind", "?"), session.get("profile", "-"),
        session.get("recorded", "?")))
    if session.get("drive_exit", "") not in ("", "0"):
        print("WARNING  drive_route.py exited {} on this run".format(
            session["drive_exit"]))
    if session.get("kind") == "drive":
        _, truth, est, joints = analyse_drive(cfg, path, session, sensors)
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
                     "joint_state",
                     "drive_read_a", "scan_nav", "imu", "depth", "cam_info"):
            full = os.path.join(path, FILES[name])
            # ekf_odom is the one stream a pre-F2 session does not carry.
            # It is skipped rather than refused, and analyse_fused() has
            # already said so in full above; a second refusal here would
            # make F1's own sessions unreadable by the tool that produced
            # their figures.
            if name == "ekf_odom" and not os.path.isfile(full):
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
    print("                   {}  (yaw rate and ax; no orientation "
          "exists)".format(cfg.s("topics.imu")))
    print("  out              {} at {} Hz".format(
        cfg.s("topics.odometry_filtered"), cfg.s("ekf.frequency_hz")))
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
    for path in paths:
        analyse_session(cfg, path, sensors)
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
    reader = subparsers.add_parser(
        "analyse", help="read recorded sessions and print the tables "
                        "(no ROS, no Gazebo)")
    reader.add_argument("session", nargs="*",
                        help="session directories; default is every session "
                             "under evidence.dir")
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
