"""instantiate_truck.py - derive one truck's whole m5v3 artifact set.

m5_ver3 is written for ONE truck in a partition of its own: every gz
topic is absolute under /forklift/gz/, every ROS frame is REP-105's bare
name, every params file is addressed to a root-namespace node, and every
path is a singleton. Four of those stacks in one world would share all
four - one /forklift/gz/scan_nav, four publishers of odom -> base_link,
four nodes called /local_costmap/local_costmap, one .pids file. This
tool is the only thing that may vary any of it: a counted, mechanical
rewrite of the donor set into m6_ver2/vehicles/<vid>/, gitignored build
products with a manifest. THE DONOR IS NEVER EDITED.

The count assertion is the safety of the mechanism, and the value
assertion is its second half: a rewrite that finds fewer literals than
the donor holds, or finds a key whose value is not the one this tool was
written against, is a rewrite that has silently stopped covering what it
claims to cover. Both refuse by name.

THE TWO POPULATIONS OF `/forklift/`, WHICH ARE NOT ONE. The donor spells
its gz namespace `/forklift/gz/...` and it also cites the m5-ver2 crib
by REPO PATH - `agv/forklift/nav2.yaml`, `agv/forklift/ekf.yaml`,
`agv/forklift/README.md`. A blanket `/forklift/` -> `/<vid>/` rewrite,
which is what m6/tools/instantiate_vehicle.py does against a donor that
has no such citations, turns those into `agv/f1/nav2.yaml`: a false
statement about a file that exists. So the blanket rule here is
`/forklift/gz/` and the crib paths are asserted UNMOVED. The two
populations partition every `/forklift/` in the donor set exactly, and
the tool checks that they still do before it rewrites anything.

COMMENTS ARE REWRITTEN WITH THE CODE. A derived ekf.yaml whose comment
says `/forklift/gz/odom is the simulator's own pose` names a topic that
does not exist in the m6v2 world. The donor's comments carry the
constraints its values were chosen under, so they are part of the
artifact, not decoration around it - inertness is not a licence to
drift (SPEC_NAMESPACING.md 2, on the dark pallet camera frame).

WHAT THE ROOT-KEY WRAP DOES TO amcl.yaml's `map_server:`. A bare
top-level node key addresses only the root-namespace node, so every
node-keyed params file gets indented under `<vid>:` (nav2's own
RewrittenYaml root_key transform). amcl.yaml carries TWO keys, `amcl:`
and `map_server:`, and wrapped, the second one goes DEAD - `/f1/
map_server` is nobody. That is by design and not an oversight: there is
ONE map_server in this world, un-namespaced, and the world launch runs
it off the DONOR m5_ver3/amcl.yaml whose bare `map_server:` key matches
`/map_server` exactly (SPEC_NAMESPACING.md 4). Four servers latching
four copies of one frozen grid could differ only by mistake.

WHAT IS DELIBERATELY NOT REWRITTEN:
  - topics.steer_cmd / traction_cmd / fork_cmd keep their donor value
    (blanket-rewritten to this truck's gz terminals and nothing more).
    AMR-DEC-006 put the command seam at the adapter, upstream of
    cmd_mux/cmd_gate/forklift_io, so these three keys are DARK here and
    the single-writer rule stays where the contactor is.
  - topics.map, topics.clock, topics.tf/tf_static and frames.map are
    the shared four: one grid, one clock, one transform tree, one map
    frame. Asserted unchanged rather than left alone, so a donor edit
    that renamed one of them would be caught here.
  - `<child_model>pallet_s5</child_model>` in model.sdf: four
    DetachableJoints naming one child model. Dark with docking, and it
    needs a per-vid ruling before pallet work wakes
    (SPEC_NAMESPACING.md 9.2). Counted and left.
  - apriltag.yaml's `frames: ["tag36h11_0"]` and config's
    apriltag.tag_frame: a tag is a WORLD object, but four detectors
    broadcasting one frame name is the same edge collision as four
    odom frames. Dark with the camera; the ruling belongs with
    pallet_s5's.
  - ekf_rf2o.yaml is copied but NOT wrapped: the laser-odometry arm is
    off (`--rf2o` is never passed on this branch) and the wrap list is
    the spec's. Copied for completeness; it is not a runnable params
    file until it is wrapped.
  - every other m5_ver3/ path in the derived config - docks.yaml, the
    map dir, the slam and fuse params files, the bt_direction source
    tree. The manifest lists them under donor_pointed_paths so the next
    reader sees what is still shared rather than discovering it.

Usage:
  python3 m6_ver2/tools/instantiate_truck.py --all
  python3 m6_ver2/tools/instantiate_truck.py --vid f1
  python3 m6_ver2/tools/instantiate_truck.py --all --check
"""

import argparse
import hashlib
import json
import os
import re
import sys

TOOL = "instantiate_truck"
# Bumped when the transform changes shape, so a manifest written by an
# older tool is refused rather than trusted.
TOOL_VERSION = "1"

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, ".."))
REPO = os.path.normpath(os.path.join(_M6V2, ".."))
OUT_ROOT = os.path.join(_M6V2, "vehicles")
MANIFEST = "MANIFEST.json"

sys.path.insert(0, os.path.join(REPO, "m6", "ipc"))

SPEC = "m6_ver2/SPEC_NAMESPACING.md"
DEC006 = "AMR-DEC-006"

GZ_PREFIX = "/forklift/gz/"
CRIB_PREFIX = "agv/forklift/"
M5V3_PREFIX = "/m5v3/"
VID_RE = re.compile(r"^f[1-9][0-9]*$")

# The ground-truth OdometryPublisher's own frame names, and the
# seven <gz_frame_id> literals every bridged message is stamped
# with. Both lists are model.sdf's, in the order it writes them.
GT_FRAMES = ("forklift/odom", "forklift/base_link")
SDF_FRAME_NAMES = [
    "safety_scanner_back_link", "safety_scanner_left_link",
    "safety_scanner_right_link", "nav_lidar_link", "nav_lidar_3d_link",
    "pallet_cam_optical", "imu_link",
]


def refuse(check, owner, *lines):
    """Say no, name the check and the file that owns it, and exit 1.

    Same shape as m5_ver3/tools/_common.py's refuse() - a refusal reads
    the same however it is spelled - but not imported from there: this
    tool reads the donor's BYTES and must not depend on its code.
    """
    pad = " " * (len(TOOL) + 2)
    out = ["{}: REFUSED at check '{}'".format(TOOL, check),
           "{}owned by: {}".format(pad, owner)]
    out.extend("{}{}".format(pad, line) for line in lines)
    sys.stderr.write("\n".join(out) + "\n")
    sys.stderr.flush()
    raise SystemExit(1)


# --------------------------------------------------------------------
# BYTES IN, BYTES OUT. The donor set is mixed CRLF (config.yaml,
# nav2.yaml, docking.yaml, apriltag.yaml) and LF (the rest), and a
# derivation that normalised line endings would rewrite every line of
# four files while claiming to have rewritten twenty literals. newline=""
# on both ends is what keeps the residue pin meaningful.
# --------------------------------------------------------------------

def read_text(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text(path, body):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(body)


def sha256(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------
# The dotted-key locator. The donor yamls are plain block mappings with
# comment lines and two block scalars; nothing in them is addressed by
# this tool that lives inside a sequence, so a line scanner is enough
# and it keeps every byte it does not target.
# --------------------------------------------------------------------

_KEY = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z_][A-Za-z0-9_]*):"
                  r"(?P<rest>.*)$")
_BLOCK = re.compile(r"^[>|][-+]?$")


def key_lines(text):
    """dotted key -> line index. Keys seen twice map to None (ambiguous)."""
    found = {}
    stack = []
    block_indent = None
    for number, raw in enumerate(text.split("\n")):
        line = raw.rstrip("\r")
        stripped = line.strip()
        if block_indent is not None:
            if stripped and (len(line) - len(line.lstrip(" "))) > block_indent:
                continue
            block_indent = None
        if not stripped or stripped.startswith("#"):
            continue
        match = _KEY.match(line)
        if match is None:
            continue
        indent = len(match.group("indent"))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, match.group("key")))
        dotted = ".".join(key for _, key in stack)
        found[dotted] = None if dotted in found else number
        rest = match.group("rest").strip()
        if _BLOCK.match(rest):
            block_indent = indent
    return found


_VALUE = re.compile(r"^(?P<head> *[A-Za-z_][A-Za-z0-9_]*: *)"
                    r"(?P<value>.*?)(?P<tail> *)$")


def _split_value(line, dotted, name):
    match = _VALUE.match(line)
    if match is None:
        refuse("the line under a keyed rule is a scalar assignment",
               "{} 3.3".format(SPEC),
               "{} in {} reads {!r}".format(dotted, name, line))
    value = match.group("value")
    if " #" in value:
        refuse("no keyed value carries a trailing comment",
               "{} 3.3".format(SPEC),
               "{} in {} does, and this tool would eat it"
               .format(dotted, name))
    quote = ""
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        quote, value = value[0], value[1:-1]
    return match.group("head"), quote, value, match.group("tail")


def get_value(text, index, dotted, name):
    lines = text.split("\n")
    line = lines[index].rstrip("\r")
    return _split_value(line, dotted, name)[2]


def set_value(text, index, dotted, name, expect, new):
    """Replace one scalar, refusing when it is not the value we expect."""
    lines = text.split("\n")
    carriage = "\r" if lines[index].endswith("\r") else ""
    head, quote, value, tail = _split_value(lines[index].rstrip("\r"),
                                            dotted, name)
    if value != expect:
        refuse("the donor value under a keyed rule is the one recorded",
               "{} 3.3".format(SPEC),
               "{} in {} reads {!r}".format(dotted, name, value),
               "and this tool was written against {!r}.".format(expect),
               "A rewrite onto a value it does not recognise is a guess.")
    lines[index] = "{}{}{}{}{}{}".format(head, quote, new, quote, tail,
                                         carriage)
    return "\n".join(lines)


def locate(index_of, dotted, name):
    """One dotted key's line, out of a key_lines() index.

    The index is built ONCE per file and reused: every rewrite below
    replaces a line in place, so no rule can move another rule's key.
    """
    index = index_of.get(dotted, "missing")
    if index == "missing":
        refuse("every keyed rule finds its key",
               "{} 3.3".format(SPEC),
               "{} is not in {}".format(dotted, name))
    if index is None:
        refuse("every keyed rule finds its key exactly once",
               "{} 3.3".format(SPEC),
               "{} appears more than once in {}".format(dotted, name))
    return index


# --------------------------------------------------------------------
# The rules.
# --------------------------------------------------------------------

class Rule(object):
    """One dotted key, its donor value, and what becomes of it.

    kind:
      frame  - gains the `<vid>/` prefix (REP-105 name -> per-truck name)
      topic  - gains the `/<vid>` prefix (a bare shared topic name)
      set    - becomes the template, `{vid}` expanded
      spawn  - becomes VEHICLES[vid]["spawn"][axis]
      same   - asserted unchanged; a shared name, checked not ignored
      dark   - asserted unchanged; DEC-006 leaves it to the adapter
    """

    __slots__ = ("dotted", "kind", "donor", "target")

    def __init__(self, dotted, kind, donor, target=None):
        self.dotted = dotted
        self.kind = kind
        self.donor = donor
        self.target = target

    @property
    def rewrites(self):
        return self.kind in ("frame", "topic", "set", "spawn")

    def new_value(self, vid, spawn):
        if self.kind == "frame":
            return "{}/{}".format(vid, self.donor)
        if self.kind == "topic":
            return "/{}{}".format(vid, self.donor)
        if self.kind == "set":
            return self.target.format(vid=vid)
        if self.kind == "spawn":
            return spawn[self.target]
        return None


def _derived(name):
    return "m6_ver2/vehicles/{vid}/" + name


CONFIG_RULES = [
    # ---- FRAMES: every REP-105 name gains the truck, except `map` ----
    Rule("frames.odom", "frame", "odom"),
    Rule("frames.base_link", "frame", "base_link"),
    Rule("frames.imu", "frame", "imu_link"),
    Rule("frames.nav_lidar", "frame", "nav_lidar_link"),
    Rule("frames.rf2o_odom", "frame", "rf2o_odom"),
    Rule("frames.pallet_cam", "frame", "pallet_cam_link"),
    Rule("frames.pallet_cam_optical", "frame", "pallet_cam_optical"),
    # ONE map frame for four trucks: four AMCLs each own a distinct
    # map -> <vid>/odom edge under it.
    Rule("frames.map", "same", "map"),

    # ---- BARE SHARED TOPIC NAMES gain the truck ----
    Rule("topics.cmd_vel", "topic", "/cmd_vel"),
    Rule("topics.cmd_vel_smoothed", "topic", "/cmd_vel_smoothed"),
    Rule("topics.cmd_vel_monitored", "topic", "/cmd_vel_monitored"),
    Rule("topics.speed_limit", "topic", "/speed_limit"),
    Rule("topics.initialpose", "topic", "/initialpose"),
    Rule("topics.amcl_pose", "topic", "/amcl_pose"),
    Rule("topics.slam_pose", "topic", "/pose"),
    Rule("topics.dock_robot", "topic", "/dock_robot"),
    Rule("topics.undock_robot", "topic", "/undock_robot"),

    # ---- THE SHARED FOUR, asserted rather than assumed ----
    Rule("topics.map", "same", "/map"),
    Rule("topics.clock", "same", "/clock"),
    Rule("topics.tf", "same", "/tf"),
    Rule("topics.tf_static", "same", "/tf_static"),

    # ---- DARK per DEC-006: the command seam is the adapter's ----
    Rule("topics.steer_cmd", "dark", "/forklift/gz/actuator/steer_cmd"),
    Rule("topics.traction_cmd", "dark", "/forklift/gz/actuator/traction_cmd"),
    Rule("topics.fork_cmd", "dark", "/forklift/gz/actuator/fork_cmd"),

    # ---- ISOLATION: this world, this domain ----
    Rule("isolation.gz_partition", "set", "m5v3", "m6"),
    Rule("isolation.ros_domain_id", "set", "97", "96"),
    # The offline replay arm keeps its own domain; still not 96.
    Rule("isolation.map_ros_domain_id", "same", "98"),

    # ---- THE SINGLETONS, one per truck ----
    Rule("paths.log_dir", "set", "m5_ver3/logs", "m6_ver2/logs/{vid}"),
    Rule("paths.pidfile", "set", "m5_ver3/.m5v3_pids",
         "m6_ver2/vehicles/{vid}/.pids"),
    Rule("paths.traction_file", "set", "m5_ver3/.m5v3_traction",
         "m6_ver2/vehicles/{vid}/.traction"),

    # ---- THE DERIVED ARTIFACTS point at this truck's copies ----
    Rule("vehicle.model", "set", "m5_ver3/gazebo/forklift_ver3/model.sdf",
         _derived("model.sdf")),
    Rule("ekf.params_file", "set", "m5_ver3/ekf.yaml", _derived("ekf.yaml")),
    Rule("smoother.params_file", "set", "m5_ver3/smoother.yaml",
         _derived("smoother.yaml")),
    Rule("monitor.params_file", "set", "m5_ver3/collision_monitor.yaml",
         _derived("collision_monitor.yaml")),
    Rule("localization.amcl.params_file", "set", "m5_ver3/amcl.yaml",
         _derived("amcl.yaml")),
    Rule("nav.params_file", "set", "m5_ver3/nav2.yaml", _derived("nav2.yaml")),
    Rule("nav.bt_xml", "set",
         "m5_ver3/behavior_trees/navigate_to_pose_tricycle_v3.xml",
         _derived("navigate_to_pose_tricycle_v3.xml")),
    Rule("nav.bt_xml_rpp", "set",
         "m5_ver3/behavior_trees/navigate_to_pose_tricycle_v3_rpp.xml",
         _derived("navigate_to_pose_tricycle_v3_rpp.xml")),

    # ---- THE POSE, from the one table that holds it ----
    Rule("vehicle.spawn.x", "spawn", "-17.00", "x"),
    Rule("vehicle.spawn.y", "spawn", "10.00", "y"),
    Rule("vehicle.spawn.z", "spawn", "0.05", "z"),
    Rule("vehicle.spawn.yaw", "spawn", "3.14159", "yaw"),
]

NAV2_RULES = [
    # The local costmap rolls in the ESTIMATE's frame, which is now this
    # truck's; the global one is the shared map and stays.
    Rule("local_costmap.local_costmap.ros__parameters.global_frame",
         "frame", "odom"),
    Rule("local_costmap.local_costmap.ros__parameters.robot_base_frame",
         "frame", "base_link"),
    Rule("global_costmap.global_costmap.ros__parameters.global_frame",
         "same", "map"),
    Rule("global_costmap.global_costmap.ros__parameters.robot_base_frame",
         "frame", "base_link"),
    # Absolute, so no namespace touches it: one latched grid, four
    # static layers reading it.
    Rule("global_costmap.global_costmap.ros__parameters."
         "static_layer.map_topic", "same", "/map"),
    Rule("bt_navigator.ros__parameters.global_frame", "same", "map"),
    Rule("bt_navigator.ros__parameters.robot_base_frame",
         "frame", "base_link"),
    Rule("behavior_server.ros__parameters.local_frame", "frame", "odom"),
    Rule("behavior_server.ros__parameters.global_frame", "same", "map"),
    Rule("behavior_server.ros__parameters.robot_base_frame",
         "frame", "base_link"),
]

MONITOR_RULES = [
    Rule("collision_monitor.ros__parameters.base_frame_id",
         "frame", "base_link"),
    # base_shift_correction carries each source's points forward through
    # <vid>/odom -> <vid>/base_link, so the edge has to be this truck's.
    Rule("collision_monitor.ros__parameters.odom_frame_id", "frame", "odom"),
]

DOCKING_RULES = [
    # DARK with the camera, and rewritten anyway: a dark file that names
    # bare `odom` is a file that would drive on whichever truck's edge
    # arrived last on the day docking wakes.
    Rule("docking_server.ros__parameters.base_frame", "frame", "base_link"),
    Rule("docking_server.ros__parameters.fixed_frame", "frame", "odom"),
]


class Source(object):
    """One donor file and what the pipeline does to it.

    `kept` names literals that must come out of the pipeline with the
    count they went in with. Leaving a literal alone is a decision, and
    a decision nothing checks is a decision that expires quietly.
    """

    __slots__ = ("src", "name", "rules", "wrap", "sdf_frames", "kept")

    def __init__(self, src, name, rules=(), wrap=False, sdf_frames=False,
                 kept=()):
        self.src = src
        self.name = name
        self.rules = list(rules)
        self.wrap = wrap
        self.sdf_frames = sdf_frames
        self.kept = list(kept)


SOURCES = [
    # config.yaml:644 spells `forklift/odom` and `forklift/base_link` in
    # a comment ABOUT m5-ver2's fleet-prefixed frames - history, not
    # this truck's names, and it stays as written.
    Source("m5_ver3/config.yaml", "config.yaml", CONFIG_RULES,
           kept=(("gt_frame_mentions_kept", GT_FRAMES),)),
    Source("m5_ver3/nav2.yaml", "nav2.yaml", NAV2_RULES, wrap=True),
    Source("m5_ver3/amcl.yaml", "amcl.yaml", wrap=True),
    Source("m5_ver3/ekf.yaml", "ekf.yaml", wrap=True),
    Source("m5_ver3/smoother.yaml", "smoother.yaml", wrap=True),
    Source("m5_ver3/collision_monitor.yaml", "collision_monitor.yaml",
           MONITOR_RULES, wrap=True),
    Source("m5_ver3/docking.yaml", "docking.yaml", DOCKING_RULES, wrap=True),
    Source("m5_ver3/apriltag.yaml", "apriltag.yaml", wrap=True),
    Source("m5_ver3/ekf_rf2o.yaml", "ekf_rf2o.yaml"),
    # `pallet_s5` names the DetachableJoint's child model. Dark with
    # docking, and it needs a per-vid ruling before pallet work
    # wakes (SPEC_NAMESPACING.md 9.2) - counted, not moved.
    Source("m5_ver3/gazebo/forklift_ver3/model.sdf", "model.sdf",
           sdf_frames=True, kept=(("pallet_s5_kept", ("pallet_s5",)),)),
    Source("m5_ver3/behavior_trees/navigate_to_pose_tricycle_v3.xml",
           "navigate_to_pose_tricycle_v3.xml"),
    Source("m5_ver3/behavior_trees/navigate_to_pose_tricycle_v3_rpp.xml",
           "navigate_to_pose_tricycle_v3_rpp.xml"),
]

_BY_NAME = dict((source.name, source) for source in SOURCES)


def source(name):
    return _BY_NAME[name]


# --------------------------------------------------------------------
# Step 1 - the blanket prefix rewrites.
# --------------------------------------------------------------------

_ORIGIN = re.compile(re.escape(GZ_PREFIX) + "|" + re.escape(M5V3_PREFIX))


def blanket_origins(body):
    """The ordered prefix provenance the rewrite is about to collapse.

    Both prefixes land on `/<vid>/`, so this list is the only thing that
    tells the inverse which one a derived occurrence came from.
    """
    return _ORIGIN.findall(body)


def _check_populations(body, name):
    gz = body.count(GZ_PREFIX)
    crib = body.count(CRIB_PREFIX)
    total = body.count("/forklift/")
    if gz + crib != total:
        refuse("/forklift/ is the gz namespace plus the crib paths",
               "{} 6".format(SPEC),
               "{} holds {} of them: {} under {} and {} under {}."
               .format(name, total, gz, GZ_PREFIX, crib, CRIB_PREFIX),
               "The remainder is a third spelling this tool cannot",
               "classify, and it will not guess which side it is on.")
    return gz, crib


def blanket(body, vid, name):
    gz, crib = _check_populations(body, name)
    m5v3 = body.count(M5V3_PREFIX)
    out = body.replace(GZ_PREFIX, "/{}/gz/".format(vid))
    out = out.replace(M5V3_PREFIX, "/{}/".format(vid))
    if out.count("/{}/".format(vid)) != gz + m5v3:
        refuse("the blanket rewrite moved every literal it counted",
               "{} 3.1".format(SPEC),
               "{}: counted {} + {}, wrote {}"
               .format(name, gz, m5v3, out.count("/{}/".format(vid))))
    if GZ_PREFIX in out or M5V3_PREFIX in out:
        refuse("no donor prefix survives the blanket rewrite",
               "{} 3.1".format(SPEC), name)
    if out.count(CRIB_PREFIX) != crib:
        refuse("the crib paths are not rewritten",
               "{} 3.1".format(SPEC),
               "{}: {} of agv/forklift/ went in, {} came out"
               .format(name, crib, out.count(CRIB_PREFIX)))
    return out, {"forklift_gz": gz, "m5v3": m5v3, "agv_forklift_kept": crib}


def unblanket(body, vid, origins, name):
    """Put the two prefixes back, in the order they were collapsed."""
    pattern = re.compile(re.escape("/{}/gz/".format(vid)) + "|"
                         + re.escape("/{}/".format(vid)))
    taken = [0]

    def pick(match):
        if taken[0] >= len(origins):
            refuse("the inverse has an origin for every derived prefix",
                   "{} 5".format(SPEC),
                   "{} carries more /{}/ than the donor had prefixes"
                   .format(name, vid))
        origin = origins[taken[0]]
        taken[0] += 1
        want = ("/{}/gz/" if origin == GZ_PREFIX else "/{}/").format(vid)
        if match.group(0) != want:
            refuse("the inverse's origins line up with the derived file",
                   "{} 5".format(SPEC),
                   "{}: occurrence {} reads {!r}, its origin was {!r}"
                   .format(name, taken[0], match.group(0), origin))
        return origin

    out = pattern.sub(pick, body)
    if taken[0] != len(origins):
        refuse("the inverse consumed every origin",
               "{} 5".format(SPEC),
               "{}: {} of {} used".format(name, taken[0], len(origins)))
    return out


# --------------------------------------------------------------------
# Step 2 - the SDF's frame-bearing literals.
#
# Only the strings gz STAMPS ON A MESSAGE move: the seven <gz_frame_id>
# elements and the ground-truth publisher's <odom_frame>/<robot_base_
# frame>. The <parent>/<child> link names are SDF-internal and already
# scoped by the model, so prefixing them would break the model and fix
# nothing.
# --------------------------------------------------------------------

_GZ_FRAME = re.compile(r"(<gz_frame_id>)([^<]+)(</gz_frame_id>)")


def sdf_frames(body, vid, name):
    seen = [match.group(2) for match in _GZ_FRAME.finditer(body)]
    if seen != SDF_FRAME_NAMES:
        refuse("model.sdf stamps the seven frames this tool knows",
               "{} 2".format(SPEC),
               "found {}".format(seen),
               "expected {}".format(SDF_FRAME_NAMES))
    out = _GZ_FRAME.sub(lambda m: "{}{}/{}{}".format(m.group(1), vid,
                                                     m.group(2), m.group(3)),
                        body)
    counts = {"gz_frame_id": len(seen)}
    # The ground-truth publisher's own frames, live at 2226-2227 and
    # named again in the comment above them. The comment is rewritten
    # with the element: a note that spells the old frame is a note that
    # will be believed.
    for literal, key in zip(GT_FRAMES, ("gt_odom_frame", "gt_base_frame")):
        counts[key] = out.count(literal)
        out = out.replace(literal, "{}/{}".format(vid, literal))
        if out.count("{}/{}".format(vid, literal)) != counts[key]:
            refuse("every ground-truth frame literal moved",
                   "{} 2".format(SPEC), "{} in {}".format(literal, name))
    return out, counts


def unsdf_frames(body, vid):
    out = body
    for literal in GT_FRAMES:
        out = out.replace("{}/{}".format(vid, literal), literal)
    return _GZ_FRAME.sub(
        lambda m: "{}{}{}".format(m.group(1),
                                  m.group(2)[len(vid) + 1:], m.group(3)), out)


# --------------------------------------------------------------------
# Step 4 - the root-key wrap.
# --------------------------------------------------------------------

def wrap(body, vid, name):
    lines = body.split("\n")
    carriage = "\r" if len(lines) > 1 and lines[0].endswith("\r") else ""
    out = [("  " + line) if line.strip() else line for line in lines]
    out.insert(0, "{}:{}".format(vid, carriage))
    wrapped = "\n".join(out)
    # ONE line added, TWO spaces on every non-empty line, and nothing
    # else - unwrap() reads both back off and the donor has to return.
    if len(out) != len(lines) + 1 or unwrap(wrapped, vid, name) != body:
        refuse("the wrap adds one line and two spaces and nothing else",
               "{} 3.4".format(SPEC), name)
    return wrapped, {"wrap_lines_in": len(lines), "wrap_lines_out": len(out)}


def unwrap(body, vid, name):
    lines = body.split("\n")
    if lines[0].rstrip("\r") != vid + ":":
        refuse("the wrapped file opens with the vid key",
               "{} 3.4".format(SPEC), "{} opens {!r}".format(name, lines[0]))
    out = []
    for line in lines[1:]:
        if not line.strip():
            out.append(line)
            continue
        if not line.startswith("  "):
            refuse("every non-empty wrapped line carries the two spaces",
                   "{} 3.4".format(SPEC), "{}: {!r}".format(name, line[:40]))
        out.append(line[2:])
    return "\n".join(out)


# --------------------------------------------------------------------
# The pipeline.
# --------------------------------------------------------------------

def _spawn_of(vid):
    from status_contract import VEHICLES
    if not VID_RE.match(vid or "") or vid not in VEHICLES:
        refuse("the vid is one the fleet table knows",
               "m6/ipc/status_contract.py VEHICLES",
               "{!r} is not among {}".format(vid, sorted(VEHICLES)))
    return dict(VEHICLES[vid]["spawn"])


def derive_text(src, vid, body=None, spawn=None):
    """Donor bytes -> this truck's bytes, with the counts that prove it."""
    spawn = spawn or _spawn_of(vid)
    body = read_text(os.path.join(REPO, src.src)) if body is None else body
    out, counts = blanket(body, vid, src.name)
    if src.sdf_frames:
        out, more = sdf_frames(out, vid, src.name)
        counts.update(more)
    rewritten = asserted = 0
    index_of = key_lines(out) if src.rules else {}
    for rule in src.rules:
        index = locate(index_of, rule.dotted, src.name)
        expect = rule.donor.replace(GZ_PREFIX, "/{}/gz/".format(vid))
        expect = expect.replace(M5V3_PREFIX, "/{}/".format(vid))
        if rule.rewrites:
            out = set_value(out, index, rule.dotted, src.name, expect,
                            rule.new_value(vid, spawn))
            rewritten += 1
        else:
            got = get_value(out, index, rule.dotted, src.name)
            if got != expect:
                refuse("a key this tool leaves alone still holds its value",
                       "{} 3.3 / {}".format(SPEC, DEC006),
                       "{} in {} reads {!r}, not {!r}."
                       .format(rule.dotted, src.name, got, expect),
                       "Leaving a key alone is a claim about it, so the",
                       "claim is checked and not assumed.")
            asserted += 1
    counts["keyed_rewritten"] = rewritten
    counts["keyed_asserted"] = asserted
    for key, literals in src.kept:
        before = sum(body.count(literal) for literal in literals)
        after = sum(out.count(literal) for literal in literals)
        if before != after:
            refuse("a literal this tool leaves alone is still there",
                   "{} 6".format(SPEC),
                   "{}: {} went in {} times and came out {}"
                   .format(src.name, "/".join(literals), before, after))
        counts[key] = after
    if src.wrap:
        out, more = wrap(out, vid, src.name)
        counts.update(more)
    return out, counts


def invert_text(src, body, vid, origins):
    """This truck's bytes -> donor bytes. The residue pin's other half."""
    spawn = _spawn_of(vid)
    out = unwrap(body, vid, src.name) if src.wrap else body
    index_of = key_lines(out) if src.rules else {}
    for rule in reversed(src.rules):
        if not rule.rewrites:
            continue
        index = locate(index_of, rule.dotted, src.name)
        expect = rule.donor.replace(GZ_PREFIX, "/{}/gz/".format(vid))
        expect = expect.replace(M5V3_PREFIX, "/{}/".format(vid))
        out = set_value(out, index, rule.dotted, src.name,
                        rule.new_value(vid, spawn), expect)
    if src.sdf_frames:
        out = unsdf_frames(out, vid)
    return unblanket(out, vid, origins, src.name)


def donor_pointed_paths(config_body):
    """Every VALUE in the derived config still reading out of m5_ver3/.

    Values only, never comments: a comment that cites the donor is
    history, and a path that resolves at run time is a dependency.
    """
    lines = config_body.split("\n")
    out = set()
    for dotted, index in key_lines(config_body).items():
        if index is None:
            continue
        match = _VALUE.match(lines[index].rstrip("\r"))
        if match is None:
            continue
        value = match.group("value")
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        if value.startswith("m5_ver3/"):
            out.add(value)
    return sorted(out)


def instantiate(vid, out_root=OUT_ROOT):
    """Write <out_root>/<vid>/ and its manifest; return the manifest."""
    spawn = _spawn_of(vid)
    out_dir = os.path.join(out_root, vid)
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"tool": TOOL, "tool_version": TOOL_VERSION, "vid": vid,
                "spawn": spawn, "sources": {}}
    config = None
    for src in SOURCES:
        donor = read_text(os.path.join(REPO, src.src))
        body, counts = derive_text(src, vid, body=donor, spawn=spawn)
        write_text(os.path.join(out_dir, src.name), body)
        manifest["sources"][src.name] = {
            "src": src.src, "donor_sha256": sha256(donor),
            "derived_sha256": sha256(body), "wrapped": bool(src.wrap),
            "counts": counts,
        }
        if src.name == "config.yaml":
            config = body
    if config is None:
        refuse("config.yaml is one of the sources",
               "{} 3".format(SPEC),
               "the source table lost it")
    # WHAT IS STILL SHARED WITH THE DONOR, named. G1 moves the eight
    # artifact paths and the three singletons; everything else in the
    # derived config still reads out of m5_ver3/, and a reader should
    # not have to grep to find that out.
    manifest["donor_pointed_paths"] = donor_pointed_paths(config)
    write_text(os.path.join(out_dir, MANIFEST),
               json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def check(vid, out_root=OUT_ROOT):
    """Name every way the derivation on disk is not the one we would write."""
    out_dir = os.path.join(out_root, vid)
    path = os.path.join(out_dir, MANIFEST)
    if not os.path.exists(path):
        return ["{}: no {} - nothing has been derived for {}"
                .format(out_dir, MANIFEST, vid)]
    problems = []
    try:
        recorded = json.loads(read_text(path))
    except ValueError as error:
        return ["{}: unreadable ({})".format(path, error)]
    if recorded.get("tool_version") != TOOL_VERSION:
        problems.append("{}: written by tool version {}, this is {}"
                        .format(path, recorded.get("tool_version"),
                                TOOL_VERSION))
    spawn = _spawn_of(vid)
    for src in SOURCES:
        entry = recorded.get("sources", {}).get(src.name)
        target = os.path.join(out_dir, src.name)
        if entry is None:
            problems.append("{}: not in the manifest".format(src.name))
            continue
        donor = read_text(os.path.join(REPO, src.src))
        if sha256(donor) != entry["donor_sha256"]:
            problems.append("{}: the donor moved since it was derived"
                            .format(src.src))
        if not os.path.exists(target):
            problems.append("{}: derived file is missing".format(src.name))
            continue
        body, _ = derive_text(src, vid, body=donor, spawn=spawn)
        if read_text(target) != body:
            problems.append("{}: on disk is not what this tool writes"
                            .format(src.name))
    return problems


def main():
    parser = argparse.ArgumentParser(
        description="derive one truck's m5v3 artifact set into "
                    "m6_ver2/vehicles/<vid>/")
    parser.add_argument("--vid", help="one truck id, f1..f4")
    parser.add_argument("--all", action="store_true",
                        help="every truck in the fleet table")
    parser.add_argument("--check", action="store_true",
                        help="verify the derivation on disk, write nothing")
    args = parser.parse_args()
    from status_contract import VEHICLES
    if args.all == bool(args.vid):
        parser.error("name --vid or pass --all, not both and not neither")
    vids = sorted(VEHICLES) if args.all else [args.vid]
    if args.check:
        problems = []
        for vid in vids:
            problems.extend("{}: {}".format(vid, line)
                            for line in check(vid))
        if problems:
            refuse("the derivation on disk is the one this tool writes",
                   "{} 3.5".format(SPEC), *problems)
        print("{}: {} up to date".format(TOOL, " ".join(vids)))
        return
    for vid in vids:
        manifest = instantiate(vid)
        moved = sum(entry["counts"]["forklift_gz"]
                    + entry["counts"]["m5v3"]
                    + entry["counts"]["keyed_rewritten"]
                    for entry in manifest["sources"].values())
        print("{}: {} <- {} files, {} literals, spawn {} {} yaw {}"
              .format(TOOL, os.path.join("m6_ver2", "vehicles", vid),
                      len(SOURCES), moved, manifest["spawn"]["x"],
                      manifest["spawn"]["y"], manifest["spawn"]["yaw"]))


if __name__ == "__main__":
    main()
