#!/usr/bin/env python3
"""plant.py - the m5-ver3 plant as an INSTRUMENT for the M8 benches.

    python3 m8/bench/plant.py probe      # what the running plant looks like

Three questions the benches share, answered in one place:

  IS THE PLANT UP.  m5v3.sh start writes paths.traction_file; a bench
  whose state file is missing prints NOT_RUN and exits 2 BEFORE it
  imports yaml or rclpy (m8/tests/test_benches_not_run.py holds that).
  With the file present the stack's own labels (traction / arm / loc /
  nav / dock / docking) are read and refused by name if a bench needs
  one that is off - the m5-ver3 mix refusal, one layer up.

  WHERE THINGS TRULY ARE.  gz world state: set_pose / create / remove
  for staging a condition, `gz model -p` to read a model back, the
  ground-truth Odometry for the truck. Ground truth is a SCORE, not a
  command: nothing here feeds a controller.

  WHAT THE CAMERA SHOULD SEE.  bench/geom.py through config.yaml's
  vehicle.cam_mount / cam_optical and the pallet's own dimensions.

rclpy is imported inside functions only. This file publishes nothing a
consumer reads: /initialpose (the AMCL seed dock_bench.stage already
uses) is the one topic it writes, and only when a bench teleports.
Frames never leave the rig (R3): captures stay in memory, results are
numbers.
"""
from __future__ import annotations

import datetime
import json
import math
import os
import re
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
_REPO = os.path.normpath(os.path.join(_M8, os.pardir))
_TOOLS = os.path.join(_REPO, "m5_ver3", "tools")
_IPC = os.path.join(_REPO, "m6", "ipc")
for _p in (_M8, _TOOLS, _IPC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bench import geom  # noqa: E402

# config.yaml paths.traction_file. Checked against the parsed config once
# the plant is up; before that it is the cheap "is anything running" test.
STATE_FILE = os.path.join(_REPO, "m5_ver3", ".m5v3_traction")
RESULTS_DIR = os.path.join(_M8, "bench", "results")

REQUIRED_KEYS = (
    "isolation.gz_partition", "isolation.ros_domain_id",
    "world.name", "vehicle.name", "vehicle.spawn.z",
    "vehicle.cam_mount.x", "vehicle.cam_mount.y", "vehicle.cam_mount.z",
    "vehicle.cam_mount.roll", "vehicle.cam_mount.pitch", "vehicle.cam_mount.yaw",
    "vehicle.cam_optical.x", "vehicle.cam_optical.y", "vehicle.cam_optical.z",
    "vehicle.cam_optical.roll", "vehicle.cam_optical.pitch",
    "vehicle.cam_optical.yaw",
    "topics.cam_depth", "topics.cam_info", "topics.odom_ground_truth",
    "topics.initialpose",
    "frames.map", "frames.pallet_cam_optical",
    "dock.station", "dock.marker_ahead_m", "dock.fork_reach_m",
    "dock.tip_standoff_m", "dock.staging_run_in_m", "dock.tag_thickness_m",
    "pallet.name", "pallet.model_dir", "pallet.wall_clearance_m",
    "pallet.depth_m", "pallet.length_m", "pallet.height_m",
    "pallet.deck_thickness_m",
    "map.dir", "map.name", "map.registration.file",
    "localization.initial_pose.cov_x_m2", "localization.initial_pose.cov_y_m2",
    "localization.initial_pose.cov_yaw_rad2",
    "paths.traction_file", "timing.spawn_service_timeout_ms",
)

STATE_LINES_NEEDED = ("traction", "arm", "loc", "nav", "dock", "docking")


# ------------------------------------------------------------- NOT_RUN
def state_file_present() -> bool:
    return os.path.isfile(STATE_FILE)


def plant_reachable() -> tuple:
    """(True, '') when THIS process can measure the plant, else (False, why).

    Three cheap questions, none of which imports yaml or rclpy:
      1. is the plant up - m5v3.sh's state file exists;
      2. can this python see a vehicle graph - rclpy is importable
         (the Windows test python cannot, and must print NOT_RUN even
         while the plant runs in WSL);
      3. is this shell a plant session - GZ_PARTITION is set. Unset
         means pytest or a bare shell, not a wrong partition; a WRONG
         one is refused loudly by Plant(), not hidden as NOT_RUN.
    """
    if not os.path.isfile(STATE_FILE):
        return False, "no state file: the plant is not up ({})".format(STATE_FILE)
    import importlib.util
    if importlib.util.find_spec("rclpy") is None:
        return False, ("rclpy is not importable: this python cannot see the vehicle "
                       "graph (run inside WSL with /opt/ros/jazzy sourced)")
    if not os.environ.get("GZ_PARTITION"):
        return False, ("GZ_PARTITION is unset: this shell is not a plant session "
                       "(export GZ_PARTITION=m5v3 ROS_DOMAIN_ID=97 first)")
    return True, ""


def not_run(bench: str, *lines: str) -> int:
    """The refusal every plant bench prints when there is no plant.

    The wording is pinned by m8/tests/test_benches_not_run.py: NOT_RUN,
    and a sentence saying what this process did NOT do.
    """
    print("NOT_RUN: {} needs the m5-ver3 plant".format(bench))
    print("  required: gz-sim 8.11, forklift_ver3, warehouse_ver3,")
    print("            pallet_cam D455 depth, GPU preflight, mix refusals")
    print("  looked for: {}".format(STATE_FILE))
    print("  bring it up: ./m5_ver3/m5v3.sh start --headless --localize amcl --nav --dock")
    for line in lines:
        print("  " + line)
    return 2


# --------------------------------------------------------------- Plant
class Plant(object):
    """A running m5-ver3 stack, its labels, its geometry, its gz services."""

    def __init__(self, tool: str):
        import _common                                      # noqa: E402
        import dock_core as dc                              # noqa: E402
        import evidence_core as ec                          # noqa: E402
        import furniture as furn                            # noqa: E402
        import map_register                                 # noqa: E402
        import pallet_core as pc                            # noqa: E402
        import pallet_model as pm                           # noqa: E402
        import stations                                     # noqa: E402
        import tag_core as tc                               # noqa: E402

        self.tool = tool
        self._common = _common
        self._ec = ec
        self._furn = furn
        self._tc = tc
        self.cfg = _common.load_config(tool, REQUIRED_KEYS)
        cfg = self.cfg

        state_path = os.path.join(_REPO, cfg.s("paths.traction_file"))
        if os.path.normpath(state_path) != os.path.normpath(STATE_FILE):
            cfg.refuse("plant.STATE_FILE is config.yaml paths.traction_file",
                       _common.CONFIG, "config says {}".format(state_path),
                       "plant.py says {}".format(STATE_FILE))
        if not os.path.isfile(state_path):
            cfg.refuse("the stack said which plant it is", state_path,
                       "there is no state file. m5v3.sh start writes it.")
        with open(state_path, encoding="utf-8") as handle:
            self.state = ec.parse_state_file(handle.read())
        for key in STATE_LINES_NEEDED:
            if key not in self.state:
                cfg.refuse("the state file carries {}=".format(key), state_path,
                           "it carries: {}".format(", ".join(self.state)))
        for key in ("nav", "dock", "docking"):
            if not str(self.state.get(key, "")).startswith("on@"):
                cfg.refuse("the running stack has --{}".format(key), state_path,
                           "{}={!r}".format(key, self.state.get(key)),
                           "  ./m5_ver3/m5v3.sh start --headless --localize amcl --nav --dock")
        if not str(self.state.get("loc", "")).startswith("amcl@"):
            cfg.refuse("the running stack localises with AMCL", state_path,
                       "loc={!r}; the tag bar (rms 0.0706 m) was taken on "
                       "loc=amcl".format(self.state.get("loc")))

        # Isolation: the benches must be in the plant's own partition and
        # domain or every gz service call and every subscription is a
        # call into an empty room.
        want_part = cfg.s("isolation.gz_partition")
        want_dom = cfg.s("isolation.ros_domain_id")
        have_part = os.environ.get("GZ_PARTITION", "")
        have_dom = os.environ.get("ROS_DOMAIN_ID", "")
        if have_part != want_part or have_dom != want_dom:
            cfg.refuse("the bench runs in the plant's partition and domain",
                       _common.CONFIG + " (isolation)",
                       "want GZ_PARTITION={} ROS_DOMAIN_ID={}".format(want_part, want_dom),
                       "have GZ_PARTITION={!r} ROS_DOMAIN_ID={!r}".format(have_part, have_dom))

        self.world = cfg.s("world.name")
        self.truck = cfg.s("vehicle.name")
        self.spawn_z = cfg.f("vehicle.spawn.z")
        self.pallet_name = cfg.s("pallet.name")

        st_name = cfg.s("dock.station")
        if st_name not in stations.STATIONS:
            cfg.refuse("dock.station is a key of m6/ipc/stations.py",
                       _common.CONFIG, "it reads {!r}".format(st_name))
        self.station = stations.STATIONS[st_name]
        self.geo = tc.station_geometry(
            self.station["x"], self.station["y"], self.station["yaw"],
            marker_ahead_m=cfg.f("dock.marker_ahead_m"),
            fork_reach_m=cfg.f("dock.fork_reach_m"),
            tip_standoff_m=cfg.f("dock.tip_standoff_m"),
            staging_run_in_m=cfg.f("dock.staging_run_in_m"))
        self.travel_yaw = float(self.station["yaw"])
        self.pose_yaw = dc.pose_yaw(self.travel_yaw)
        self.unit = self.geo["unit"]            # along travel, toward the bay
        self.staging_xy = self.geo["staging"]
        self.docked_xy = self.geo["docked"]

        self.pallet_design = pc.spawn_pose(
            self.geo["marker"], self.travel_yaw,
            wall_clearance_m=cfg.f("pallet.wall_clearance_m"),
            depth_m=cfg.f("pallet.depth_m"),
            height_m=cfg.f("pallet.height_m"),
            tag_thickness_m=cfg.f("dock.tag_thickness_m"))
        self.pallet_dims = dict(
            depth_m=cfg.f("pallet.depth_m"), length_m=cfg.f("pallet.length_m"),
            height_m=cfg.f("pallet.height_m"),
            deck_thickness_m=cfg.f("pallet.deck_thickness_m"))
        self.pallet_sdf = pm.model_path({
            "name": self.pallet_name, "model_dir": cfg.s("pallet.model_dir")})

        self.chain = geom.CameraChain(
            [cfg.f("vehicle.cam_mount." + k) for k in ("x", "y", "z", "roll", "pitch", "yaw")],
            [cfg.f("vehicle.cam_optical." + k) for k in ("x", "y", "z", "roll", "pitch", "yaw")])
        self.cam_mount = [cfg.f("vehicle.cam_mount." + k)
                          for k in ("x", "y", "z", "roll", "pitch", "yaw")]

        reg_path = os.path.join(_REPO, cfg.s("map.dir"), cfg.s("map.name"),
                                cfg.s("map.registration.file"))
        try:
            self.map_frame = ec.MapFrame.from_registration(
                map_register.load_registration(reg_path))
        except Exception as exc:
            cfg.refuse("the committed registration belongs to the grid on disk",
                       reg_path, str(exc))
        self.registration_path = reg_path
        self.timeout_ms = str(cfg.s("timing.spawn_service_timeout_ms"))

    # ---------------------------------------------------------- labels
    def labels(self) -> dict:
        return {k: self.state.get(k) for k in
                ("traction", "arm", "loc", "nav", "dock", "docking", "monitor",
                 "partition", "log_dir")}

    def pallet_truth(self, pose=None) -> geom.PalletTruth:
        """PalletTruth from a gz readback (x, y, z, roll, pitch, yaw)."""
        if pose is None:
            pose = self.gz_model_pose(self.pallet_name)
        return geom.PalletTruth((pose[0], pose[1], pose[2]), pose[5], **self.pallet_dims)

    # --------------------------------------------------------- geometry
    def base_for_camera_range(self, cam_range_m: float) -> tuple:
        """base_link (x, y, yaw) that puts the camera `cam_range_m` short
        of the pallet's design face, along the spur, heading-aligned."""
        face = geom.PalletTruth(
            (self.pallet_design["x"], self.pallet_design["y"], self.pallet_design["z"]),
            self.pallet_design["yaw"], **self.pallet_dims).face_centre()
        # camera sits cam_mount.x along the base's +x; the forks (and the
        # face) are at -x, so the camera is |x| toward the face already.
        along = float(cam_range_m) + abs(self.cam_mount[0])
        ux, uy = self.unit
        return (face[0] - ux * along, face[1] - uy * along, self.pose_yaw)

    def staging_base(self) -> tuple:
        return (self.staging_xy[0], self.staging_xy[1], self.pose_yaw)

    def camera_range_of(self, base_xy) -> float:
        """Horizontal camera -> design face distance for a base xy."""
        face = geom.PalletTruth(
            (self.pallet_design["x"], self.pallet_design["y"], self.pallet_design["z"]),
            self.pallet_design["yaw"], **self.pallet_dims).face_centre()
        ux, uy = self.unit
        along = (face[0] - base_xy[0]) * ux + (face[1] - base_xy[1]) * uy
        return along - abs(self.cam_mount[0])

    # ------------------------------------------------------ gz services
    def _gz_service(self, service, reqtype, req, reptype="gz.msgs.Boolean"):
        cmd = ["gz", "service", "-s", service, "--reqtype", reqtype,
               "--reptype", reptype, "--timeout", self.timeout_ms, "--req", req]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return (proc.stdout or "") + (proc.stderr or "")
        except Exception as exc:
            return "gz service failed: {}".format(exc)

    def gz_set_pose(self, name, x, y, z, yaw) -> bool:
        req = ('name: "{}", position: {{x: {:.9f}, y: {:.9f}, z: {:.9f}}}, '
               'orientation: {{z: {:.9f}, w: {:.9f}}}').format(
                   name, x, y, z, math.sin(yaw / 2.0), math.cos(yaw / 2.0))
        reply = self._gz_service("/world/{}/set_pose".format(self.world),
                                 "gz.msgs.Pose", req)
        return "data: true" in reply

    def gz_create(self, sdf_path, name, pose) -> bool:
        req = self._furn.create_request(sdf_path, name, pose)
        reply = self._gz_service("/world/{}/create".format(self.world),
                                 "gz.msgs.EntityFactory", req)
        return "data: true" in reply

    def gz_remove(self, name) -> bool:
        reply = self._gz_service("/world/{}/remove".format(self.world),
                                 "gz.msgs.Entity",
                                 'name: "{}", type: MODEL'.format(name))
        return "data: true" in reply

    def gz_model_pose(self, name):
        """(x, y, z, roll, pitch, yaw) of a model, or None if absent.

        `gz model -m NAME -p` prints (measured 2026-09-11, gz 8.11):

            Model: [444]
              - Name: pallet_s5
              - Pose [ XYZ (m) ] [ RPY (rad) ]:
                [6.999710 3.030110 0.072000]
                [0.000000 0.000000 1.570790]

        The header carries the ENTITY ID, not the name; the parse keys
        on the `- Name:` line and takes the two triplets after it.
        """
        try:
            proc = subprocess.run(["gz", "model", "-m", name, "-p"],
                                  capture_output=True, text=True, timeout=30)
        except Exception:
            return None
        text = proc.stdout or ""
        head = text.find("- Name: {}\n".format(name))
        if head < 0:
            head = text.find("- Name: {}\r\n".format(name))
        if head < 0:
            return None
        trip = re.findall(r"\[\s*(-?\d+\.?\d*(?:e-?\d+)?)\s+(-?\d+\.?\d*(?:e-?\d+)?)\s+"
                          r"(-?\d+\.?\d*(?:e-?\d+)?)\s*\]", text[head:])
        if len(trip) < 2:
            return None
        xyz = tuple(float(v) for v in trip[0])
        rpy = tuple(float(v) for v in trip[1])
        return xyz + rpy

    def teleport_truck(self, base) -> None:
        x, y, yaw = base
        if not self.gz_set_pose(self.truck, x, y, self.spawn_z, yaw):
            self.cfg.refuse("gz set_pose put the truck at ({:.3f}, {:.3f})".format(x, y),
                            "/world/{}/set_pose".format(self.world),
                            "the service did not answer data: true")

    def pallet_place_or_reseat(self) -> str:
        """The pallet at its design pose: teleport if present, spawn if not.

        Teleport first for pallet_place.reseat's reason (a respawn leaves
        a ghost the DetachableJoint can join). Returns 'reseated' or
        'placed'.
        """
        d = self.pallet_design
        if self.gz_model_pose(self.pallet_name) is not None:
            if not self.gz_set_pose(self.pallet_name, d["x"], d["y"], d["z"], d["yaw"]):
                self.cfg.refuse("gz set_pose reseated the pallet",
                                "/world/{}/set_pose".format(self.world), "no data: true")
            return "reseated"
        if not os.path.isfile(self.pallet_sdf):
            self.cfg.refuse("the pallet SDF is on disk", self.pallet_sdf,
                            "python3 m5_ver3/tools/pallet_model.py write")
        if not self.gz_create(self.pallet_sdf, self.pallet_name, d):
            self.cfg.refuse("the create service accepted the pallet",
                            "/world/{}/create".format(self.world), "no data: true")
        return "placed"

    # ---------------------------------------------------------- session
    def session_dir(self, bench: str) -> tuple:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = "{}-{}".format(bench, stamp)
        path = os.path.join(RESULTS_DIR, name)
        os.makedirs(path, exist_ok=True)
        return name, path

    def environment(self) -> dict:
        def _cmd(args):
            try:
                return subprocess.run(args, capture_output=True, text=True,
                                      timeout=20).stdout.strip()
            except Exception as exc:
                return "unavailable: {}".format(exc)
        renderer = ""
        try:
            log = os.path.expanduser("~/.gz/rendering/ogre2.log")
            with open(log, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if "GL_RENDERER" in line:
                        renderer = line.strip()
        except OSError:
            renderer = "ogre2.log unreadable"
        return {
            "host": _cmd(["hostname"]),
            "kernel": _cmd(["uname", "-r"]),
            "gz_sim": _cmd(["gz", "sim", "--version"]).splitlines()[0]
            if _cmd(["gz", "sim", "--version"]) else "",
            "ros_distro": os.environ.get("ROS_DISTRO", ""),
            "nvidia_smi": _cmd(["nvidia-smi", "--query-gpu=name,driver_version",
                                "--format=csv,noheader"]),
            "gl_renderer_last": renderer,
            "gz_partition": os.environ.get("GZ_PARTITION", ""),
            "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", ""),
            "gallium_driver": os.environ.get("GALLIUM_DRIVER", ""),
            "python": sys.version.split()[0],
            "state": self.labels(),
            "registration": {
                "path": os.path.relpath(self.registration_path, _REPO),
                "theta_rad": self.map_frame.theta_rad,
                "t_x_m": self.map_frame.t_x_m, "t_y_m": self.map_frame.t_y_m,
                "residual_rms_m": self.map_frame.residual_rms_m,
                "residual_max_m": self.map_frame.residual_max_m,
            },
        }


# --------------------------------------------------------------- Capture
class Capture(object):
    """One rclpy node: depth + CameraInfo + truth Odometry + TF.

    capture(n) returns n Frame dicts with the raw 32FC1 bytes, the
    CameraInfo intrinsics, the latest truth pose at arrival and, when
    the tree resolves, map -> pallet_cam_optical at the frame stamp.
    """

    def __init__(self, plant: Plant, node_name="m8_bench_capture"):
        try:
            import rclpy
            from rclpy.node import Node
            from rclpy.time import Time
            from tf2_ros import Buffer, TransformListener
            from geometry_msgs.msg import PoseWithCovarianceStamped
            from nav_msgs.msg import Odometry
            from sensor_msgs.msg import CameraInfo, Image
        except ImportError as exc:
            plant.cfg.refuse("rclpy, tf2_ros, sensor_msgs and nav_msgs are importable",
                             plant._common.CONFIG + " (paths.ros_setup)",
                             "python3 could not import what this bench needs: {}".format(exc),
                             "it runs INSIDE WSL with /opt/ros/jazzy sourced.")
        self.plant = plant
        self.rclpy = rclpy
        self.Time = Time
        self._PoseCov = PoseWithCovarianceStamped
        cfg = plant.cfg
        if not rclpy.ok():
            rclpy.init(args=None)
        self.node = Node(node_name)
        self.node.set_parameters([rclpy.parameter.Parameter(
            "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
        self.buf = Buffer()
        self._listener = TransformListener(self.buf, self.node)
        self.info = None
        self.truth = None          # (stamp, (x,y,z), (qx,qy,qz,qw))
        self._frames = []
        self._want = 0
        self._on_frame = None
        self.depth_topic = cfg.s("topics.cam_depth")
        self.info_topic = cfg.s("topics.cam_info")
        self.truth_topic = cfg.s("topics.odom_ground_truth")
        self.map_frame = cfg.s("frames.map")
        self.optical_frame = cfg.s("frames.pallet_cam_optical")
        self._seed_pub = self.node.create_publisher(
            PoseWithCovarianceStamped, cfg.s("topics.initialpose"), 1)
        self.node.create_subscription(CameraInfo, self.info_topic, self._cb_info, 10)
        self.node.create_subscription(Odometry, self.truth_topic, self._cb_truth, 20)
        self.node.create_subscription(Image, self.depth_topic, self._cb_depth, 5)

    # callbacks
    def _cb_info(self, msg):
        if len(msg.k) >= 6:
            self.info = {"fx": float(msg.k[0]), "fy": float(msg.k[4]),
                         "cx": float(msg.k[2]), "cy": float(msg.k[5]),
                         "width": int(msg.width), "height": int(msg.height),
                         "frame_id": msg.header.frame_id}

    def _cb_truth(self, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.truth = (t, (p.x, p.y, p.z), (q.x, q.y, q.z, q.w))

    def _lookup_map_optical(self, stamp_msg):
        try:
            tf = self.buf.lookup_transform(self.map_frame, self.optical_frame,
                                           self.Time.from_msg(stamp_msg))
        except Exception:
            try:
                tf = self.buf.lookup_transform(self.map_frame, self.optical_frame,
                                               self.Time())
            except Exception:
                return None
        t = tf.transform.translation
        r = tf.transform.rotation
        return {"t": (t.x, t.y, t.z), "q": (r.x, r.y, r.z, r.w)}

    def _cb_depth(self, msg):
        if msg.encoding not in ("32FC1", "32FC1;"):
            return
        frame = {
            "stamp": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
            "wall": time.time(),
            "frame_id": msg.header.frame_id,
            "width": int(msg.width), "height": int(msg.height),
            "step": int(msg.step), "encoding": msg.encoding,
            "data": bytes(msg.data),
            "truth": self.truth,
            "info": dict(self.info) if self.info else None,
            "map_optical": self._lookup_map_optical(msg.header.stamp),
        }
        if self._on_frame is not None:
            self._on_frame(frame)
            return
        if len(self._frames) < self._want:
            self._frames.append(frame)

    # public
    def spin_wall(self, seconds: float) -> None:
        end = time.time() + seconds
        while self.rclpy.ok() and time.time() < end:
            self.rclpy.spin_once(self.node, timeout_sec=0.05)

    def wait_ready(self, timeout_s: float) -> bool:
        end = time.time() + timeout_s
        while time.time() < end:
            self.rclpy.spin_once(self.node, timeout_sec=0.05)
            if self.info is not None and self.truth is not None:
                return True
        return False

    def capture(self, n: int, timeout_s: float) -> list:
        """n depth frames, or fewer if timeout_s wall seconds pass."""
        self._frames = []
        self._want = int(n)
        end = time.time() + timeout_s
        while self.rclpy.ok() and len(self._frames) < self._want and time.time() < end:
            self.rclpy.spin_once(self.node, timeout_sec=0.05)
        out = self._frames
        self._frames = []
        self._want = 0
        return out

    def stream(self, on_frame, until, poll_s=0.05) -> None:
        """Call on_frame(frame) for every depth frame until until() is True."""
        self._on_frame = on_frame
        try:
            while self.rclpy.ok() and not until():
                self.rclpy.spin_once(self.node, timeout_sec=poll_s)
        finally:
            self._on_frame = None

    def seed_amcl(self, base, hold_s: float = 2.0) -> tuple:
        """/initialpose at the registered map pose of a WORLD base pose.

        The same mechanism dock_bench.stage uses after its teleport. The
        truck is static afterwards, so map -> odom is the seed's mean:
        an absolute figure through this chain carries the registration
        residual AND the seed, exactly as the tag bar did.
        """
        cfg = self.plant.cfg
        x, y, yaw = base
        mx, my, myaw = self.plant.map_frame.to_map(x, y, yaw)
        msg = self._PoseCov()
        msg.header.frame_id = self.map_frame
        msg.pose.pose.position.x = float(mx)
        msg.pose.pose.position.y = float(my)
        msg.pose.pose.orientation.z = math.sin(myaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(myaw / 2.0)
        cov = [0.0] * 36
        cov[0] = cfg.f("localization.initial_pose.cov_x_m2")
        cov[7] = cfg.f("localization.initial_pose.cov_y_m2")
        cov[35] = cfg.f("localization.initial_pose.cov_yaw_rad2")
        msg.pose.covariance = cov
        end = time.time() + hold_s
        while time.time() < end:
            msg.header.stamp = self.node.get_clock().now().to_msg()
            self._seed_pub.publish(msg)
            self.rclpy.spin_once(self.node, timeout_sec=0.1)
        return (mx, my, myaw)

    def close(self) -> None:
        try:
            self.node.destroy_node()
        except Exception:
            pass
        try:
            self.rclpy.shutdown()
        except Exception:
            pass


# ------------------------------------------------------------ helpers
def decode(frame: dict) -> tuple:
    """Row-major metres from a captured frame (m8_core.wire's decoder)."""
    from m8_core.wire import decode_depth_32fc1
    return decode_depth_32fc1(frame["data"], frame["width"], frame["height"], frame["step"])


def depth_frame(frame: dict, depths=None):
    """m8_core DepthFrame with CameraInfo intrinsics, as the nodes build it."""
    from m8_core.pocket import DEFAULT_FX, DEFAULT_FY
    from m8_nodes.io import frame_from_buffer
    info = frame.get("info") or {}
    return frame_from_buffer(
        depths if depths is not None else decode(frame),
        frame["width"], frame["height"], frame["stamp"],
        frame.get("frame_id") or "pallet_cam_optical",
        fx=info.get("fx", DEFAULT_FX), fy=info.get("fy", DEFAULT_FY),
        cx=info.get("cx"), cy=info.get("cy"))


def depth_at(depths, width, height, u, v, half=1):
    """Median finite depth in a (2*half+1)^2 patch, or None."""
    vals = []
    for vv in range(int(v) - half, int(v) + half + 1):
        for uu in range(int(u) - half, int(u) + half + 1):
            if 0 <= uu < width and 0 <= vv < height:
                z = depths[vv * width + uu]
                if math.isfinite(z) and z > 0.0:
                    vals.append(z)
    if not vals:
        return None
    vals.sort()
    return vals[len(vals) // 2]


def static_truth(plant: Plant, truck6, pallet6, info: dict) -> dict:
    """What the camera should see for a STATIC truck and pallet.

    truck6 / pallet6 are gz readbacks (x, y, z, roll, pitch, yaw). The
    pocket-pair centre and the face line go through bench/geom.py into
    the optical frame; the face's four corners are projected with the
    CameraInfo intrinsics so a bench can say how much of C1's plane ROI
    the pallet actually covers. Ground truth is a score, not a command.
    """
    base_pos = (truck6[0], truck6[1], truck6[2])
    quat = geom.quat_from_rpy(truck6[3], truck6[4], truck6[5])
    pallet = plant.pallet_truth(pallet6)
    chain = plant.chain
    pocket = pallet.pocket_pair_centre()
    p_opt = chain.world_to_optical(pocket, base_pos, quat)
    left, right = pallet.face_ends_at_pocket_height()
    yaw_opt = geom.face_yaw_in_optical(
        chain.world_to_optical(left, base_pos, quat),
        chain.world_to_optical(right, base_pos, quat))
    fx, fy, cx, cy = info["fx"], info["fy"], info["cx"], info["cy"]
    w, h = info["width"], info["height"]
    corners_px = []
    for c in pallet.face_corners():
        uv = geom.project(chain.world_to_optical(c, base_pos, quat), fx, fy, cx, cy)
        if uv is not None:
            corners_px.append(uv)
    face_bbox = geom.bbox(corners_px) if len(corners_px) == 4 else None
    image_box = (0.0, float(w), 0.0, float(h))
    # The A1 FIXED ROIs. m8_core.pocket derives its ROI per frame now,
    # so these two columns no longer describe what C1 looked at - they
    # are kept, unchanged, so a re-run is comparable with the E1 and E3
    # baseline tables that quote them. What C1 actually used is in the
    # roi_* columns, straight off the observation.
    roi_plane = (w // 6, (5 * w) // 6, h // 4, (3 * h) // 4)
    roi_band = (0, w, h // 3, (2 * h) // 3)
    pocket_px = geom.project(p_opt, fx, fy, cx, cy)
    return {
        "pocket_world": pocket,
        "pocket_opt": p_opt,                    # (lateral X, height Y, range Z)
        "face_yaw_opt": yaw_opt,
        "pocket_px": pocket_px,
        "face_bbox_px": face_bbox,
        "face_in_image": geom.overlap_fraction(face_bbox, image_box) * (w * h) /
        max(1.0, (face_bbox[1] - face_bbox[0]) * (face_bbox[3] - face_bbox[2]))
        if face_bbox else 0.0,
        "face_frac_of_plane_roi": geom.overlap_fraction(face_bbox, roi_plane),
        "face_frac_of_band_roi": geom.overlap_fraction(face_bbox, roi_band),
        "camera_world": chain.camera_world(base_pos, quat),
        "truck6": tuple(truck6), "pallet6": tuple(pallet6),
    }


def write_json(path, data) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, default=_json_default)
        handle.write("\n")


def _json_default(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, bytes):
        return "<{} bytes>".format(len(obj))
    return str(obj)


# --------------------------------------------------------------- probe
def probe() -> int:
    ok, why = plant_reachable()
    if not ok:
        return not_run("plant probe", "why: " + why,
                       "this process did not synthesize anything")
    plant = Plant("plant_probe")
    print("=== m8 bench plant probe ===")
    for k, v in plant.labels().items():
        print("  {:<10} {}".format(k, v))
    print("  staging    ({:.3f}, {:.3f}) yaw {:+.4f}  camera range {:.3f} m".format(
        plant.staging_xy[0], plant.staging_xy[1], plant.pose_yaw,
        plant.camera_range_of(plant.staging_xy)))
    d = plant.pallet_design
    print("  pallet     design ({:.3f}, {:.3f}, {:.3f}) yaw {:+.4f}".format(
        d["x"], d["y"], d["z"], d["yaw"]))
    print("  pallet gz  {}".format(plant.gz_model_pose(plant.pallet_name)))
    print("  truck gz   {}".format(plant.gz_model_pose(plant.truck)))
    cap = Capture(plant, "m8_bench_probe")
    ok = cap.wait_ready(20.0)
    print("  info       {}".format(cap.info))
    print("  truth      {}".format(cap.truth))
    if not ok:
        cap.close()
        print("  no CameraInfo/truth within 20 s")
        return 1
    t0 = time.time()
    frames = cap.capture(15, 10.0)
    dt = time.time() - t0
    print("  frames     {} in {:.2f} s wall ({:.1f} Hz)".format(
        len(frames), dt, len(frames) / dt if dt > 0 else 0.0))
    if frames:
        f = frames[0]
        print("  frame0     {}x{} step {} {} stamp {:.3f} tf={}".format(
            f["width"], f["height"], f["step"], f["encoding"], f["stamp"],
            "yes" if f["map_optical"] else "no"))
        t1 = time.perf_counter()
        depths = decode(f)
        t2 = time.perf_counter()
        from m8_core.abort import classify
        from m8_core.pocket import observe
        df = depth_frame(f, depths)
        t3 = time.perf_counter()
        obs = observe(df)
        t4 = time.perf_counter()
        reason = classify(df)
        t5 = time.perf_counter()
        print("  decode {:.3f} s  build {:.3f} s  observe {:.3f} s  classify {:.3f} s".format(
            t2 - t1, t3 - t2, t4 - t3, t5 - t4))
        print("  observe    {}".format(obs))
        print("  classify   {}".format(reason))
        finite = [z for z in depths if math.isfinite(z) and z > 0]
        print("  depth      finite {}/{}  min {:.3f} max {:.3f}".format(
            len(finite), len(depths), min(finite) if finite else float("nan"),
            max(finite) if finite else float("nan")))
    cap.close()
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["probe"]:
        return probe()
    print("python3 m8/bench/plant.py probe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
