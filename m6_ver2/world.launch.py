"""world.launch.py - the m6v2 plant, and only the plant.

ONE WORLD, ONE BRIDGE, ONE MAP. This file owns everything the four
trucks SHARE and nothing they own privately: the gz server, one spawn of
each truck's DERIVED ver3 model, ONE parameter_bridge carrying the
deduplicated union of every vehicle's terminals and sensors, ONE
map_server latching the frozen grid the four AMCLs localise in, and the
fleet layer's two plant-side nodes per truck (sto_contactor,
forklift_io). The ROS autonomy stack - EKF, AMCL, the four Nav2 servers,
the smoother, the adapter - belongs to m6_ver2/truck.sh, one process
group per truck, and this file starts none of it.

WHY THE SPLIT IS HERE AND NOT SOMEWHERE ELSE (SPEC_NAMESPACING.md 4).
  m5_ver3's m5v3.sh brings up the plant AND the stack for one truck in a
  partition of its own. Four copies of that would put four gz servers on
  one partition, four parameter_bridges publishing /fN/gz/scan_nav twice
  over, four map_servers latching four copies of one immutable grid and
  four publishers on /clock - two opinions about now. Everything in that
  list is a SHARED resource, so it has one owner, and this is it.

WHAT IS SPAWNED IS THE m6v2 DERIVATION, NEVER A DONOR.
  m6_ver2/vehicles/<vid>/model.sdf, written by
  m6_ver2/tools/instantiate_truck.py from m5_ver3's forklift_ver3 model.
  The donor spells every gz topic absolutely under /forklift/gz/ and
  every frame as a bare REP-105 name, so two spawns of THAT file would
  share every terminal and every frame - one steer command driving four
  trucks, four publishers of odom -> base_link. The derived files are
  gitignored build products, so a missing OR STALE one is a refusal at
  import that names the tool. There is deliberately no fallback to the
  donor: it would start, look like a launch, and be wrong in exactly the
  way this file exists to prevent.

THE TWO CONFIG FAMILIES, AND WHY BOTH ARE READ.
  m6_ver2/vehicles/<vid>/config.yaml is m5_ver3's config, derived - it
  owns the names the AUTONOMY stack uses (imu, joint_state, scan_nav,
  clock, map, tf) and it is the config that was rewritten in the same
  pass as the model.sdf spawned here.
  m6/vehicles/<vid>/config.yaml is agv/forklift's config, derived by
  m6's own tool - it owns the names the FLEET layer uses, and
  sto_contactor.py and forklift_io.py read ITS spelling
  (gz_actuator_steer_cmd, gz_steer_cmd, safety_torque_off_demand,
  fork_height, ...), which the m5v3 schema does not have at all.
  So both are read, and because two derivations feeding one wire is
  exactly how a rename goes silently wrong, agree() below refuses unless
  the six names the two families BOTH spell are byte-identical. That
  check is the reason this file may take the bridge's names from one
  family and spawn the other family's model.

WHAT THE BRIDGE CARRIES, AND WHY EACH LINE IS THERE.
  The m6 per-vehicle set unchanged (m6/gazebo/m6_world.launch.py:145-209
  - the two actuator terminals ROS->gz, ground-truth odom, the nav lidar,
  the drive shaft's two reading channels and the three safety scanners
  gz->ROS), plus /clock ONCE, plus exactly two new gz->ROS lines per
  truck: /<vid>/gz/imu and /<vid>/gz/joint_state, which the m5v3 stack's
  EKF and wheel_odometry consume and m6 never had a use for.
  GROUND-TRUTH ODOM IS BRIDGED FOR EVIDENCE ONLY. SPEC_ADAPTER.md
  Decision 4 puts a firewall between it and the command path: nothing in
  the adapter or the fleet path may consume /<vid>/gz/odom, and the
  estimate travels on /<vid>/est/odom instead. It is on the wire here so
  m6/tools/score_run.py can still score a run against the truth, and for
  no other reason. Its <tf_topic> is NOT bridged, so the ground-truth
  frames never reach /tf.
  NO IMAGE IS BRIDGED. Not the pallet camera (dark with docking), not
  the overhead camera m6_world.launch.py carries for its recording: an
  Image channel with no consumer is a claim this run does not make, and
  four Nav2 stacks on a 0.575-RTF world (m6/CONTEXT.md:256-258) is the
  open question G1 has to MEASURE (SPEC_NAMESPACING.md 9.4) rather than
  spend in advance.
  The fork terminal is likewise unbridged, exactly as in m6: sto_contactor
  publishes it, nothing in gz listens, and it wakes with docking.

Usage (after sourcing /opt/ros/jazzy/setup.bash) - though the operator's
door is m6_ver2/m6v2.sh and not this file:
  ros2 launch m6_ver2/world.launch.py
  ros2 launch m6_ver2/world.launch.py gui:=true
  M6V2_VIDS="f1" ros2 launch m6_ver2/world.launch.py
  ros2 launch m6_ver2/world.launch.py vids:="f1 f2"
"""

import os
import sys

import yaml
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                            OpaqueFunction)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, os.pardir))
_M6 = os.path.join(_REPO, "m6")
_DONOR = os.path.join(_REPO, "m5_ver3")

SPEC = "m6_ver2/SPEC_NAMESPACING.md"
TOOL = "world.launch.py"

# THE WORLD IS m6's, BY REFERENCE AND NEVER BY COPY. warehouse_ver3.sdf
# is the 48 x 32 m two-road-class floor every M6.6+ figure was measured
# on, the floor m5_ver3/maps/warehouse_v3 was mapped from, and the floor
# registration.yaml was fitted against. A copy under m6_ver2/ would be a
# second thing to keep in step with three artifacts that cannot be
# regenerated cheaply. The world NAME inside the file stays "warehouse",
# so every /world/warehouse/* service - m6.sh's `home`, the set_pose this
# branch will want - holds.
_WORLD = os.path.join(_M6, "gazebo", "warehouse_ver3.sdf")
_WORLD_NAME = "warehouse"

# The fleet layer's two plant-side nodes. They are agv/'s, reused
# byte-untouched by m6 and byte-untouched again here: sto_contactor is
# the ONLY publisher of the actuator terminals, which is what puts it
# INSIDE the command path rather than beside it.
_SCRIPTS = os.path.join(_REPO, "agv", "forklift", "scripts")
_IO_SCRIPT = os.path.join(_SCRIPTS, "forklift_io.py")
_STO_SCRIPT = os.path.join(_SCRIPTS, "sto_contactor.py")

# The one home for the vehicle table and for the names config.yaml has
# never heard of - the three safety scanners among them. Imported
# ENV-FREE, for m6_world.launch.py's reason: VEHICLE names ONE truck and
# this process serves all of them.
sys.path.insert(0, os.path.join(_M6, "ipc"))
import status_contract                                    # noqa: E402

# The derivation tool, imported for check() - the same function
# `instantiate_truck.py --check` runs, so the launch and the operator
# entrypoint cannot disagree about what "up to date" means.
sys.path.insert(0, os.path.join(_HERE, "tools"))
import instantiate_truck                                  # noqa: E402

_ALL_VIDS = tuple(sorted(status_contract.VEHICLES))

_M6V2_VEHICLES = os.path.join(_HERE, "vehicles")
_M6_VEHICLES = os.path.join(_M6, "vehicles")


def refuse(check, owner, *lines):
    """Say no, name the check and the file that owns it.

    Raised rather than exited, because this runs at IMPORT: `ros2 launch`
    prints the traceback with the message in it, and a bare SystemExit
    from a launch file reads as a launch that ended normally.
    """
    pad = " " * (len(TOOL) + 2)
    out = ["{}: REFUSED at check '{}'".format(TOOL, check),
           "{}owned by: {}".format(pad, owner)]
    out.extend("{}{}".format(pad, line) for line in lines)
    raise RuntimeError("\n" + "\n".join(out))


# ----------------------------------------------------------------------
# WHICH TRUCKS. One resolver, two doors, and a refusal when they differ.
# ----------------------------------------------------------------------
def resolve_vids(env_value, argv, all_vids=_ALL_VIDS):
    """The truck ids this launch serves, from env or from `vids:=`.

    WHY THE SUBSET EXISTS AT ALL. G1's gate runs ONE truck: four Nav2
    stacks on a world already measured at 0.575 RTF is the open question
    (SPEC_NAMESPACING.md 9.4), and a bringup that cannot be narrowed
    cannot answer it one truck at a time. The default is the whole table,
    so nothing has to be said to get the cell this branch is for.

    WHY IT IS RESOLVED AT IMPORT AND NOT AS A SUBSTITUTION. Every spawn,
    every bridge argument and every GUI-gate topic below is built at
    module level, which is m6_world.launch.py's shape and the reason its
    refusals can be import-time. A LaunchConfiguration is not readable
    until an OpaqueFunction executes, so a `vids:=` substitution would
    have to move the whole description inside one and take the refusals
    with it. Instead the SAME token is read off argv here - `ros2 launch`
    puts `vids:=f1` on the command line verbatim - and DeclareLaunchArgument
    below keeps it visible to `ros2 launch -s`.

    BOTH DOORS AT ONCE IS A REFUSAL AND NOT A PRECEDENCE RULE. m6v2.sh
    exports M6V2_VIDS; an operator who then also types vids:= has two
    answers to one question, and picking one of them silently is how the
    gate gets measured on a fleet nobody asked for.
    """
    from_argv = None
    for word in argv or ():
        if word.startswith("vids:="):
            from_argv = word[len("vids:="):]
    chosen, door = None, None
    if from_argv is not None and env_value is not None \
            and from_argv.split() != str(env_value).split():
        refuse("M6V2_VIDS and vids:= name the same trucks",
               "{} 7-T3".format(SPEC),
               "the environment says '{}' and the command line says '{}'"
               .format(env_value, from_argv),
               "NOTHING WAS STARTED. m6_ver2/m6v2.sh sets M6V2_VIDS; drop",
               "the vids:= word, or run ros2 launch with a clean env.")
    if from_argv is not None:
        chosen, door = from_argv, "the vids:= launch argument"
    elif env_value is not None:
        chosen, door = env_value, "M6V2_VIDS in the environment"
    if chosen is None:
        return tuple(all_vids)
    vids = tuple(chosen.split())
    if not vids:
        refuse("the truck subset names at least one truck",
               "{} 7-T3".format(SPEC),
               "{} is empty.".format(door),
               "Leave it unset for the whole table: {}"
               .format(" ".join(all_vids)))
    unknown = [vid for vid in vids if vid not in all_vids]
    if unknown:
        refuse("every named truck is in the VEHICLES table",
               "m6/ipc/status_contract.py (VEHICLES)",
               "{} names {}, which the table does not have."
               .format(door, ", ".join(unknown)),
               "The table holds: {}".format(" ".join(all_vids)))
    seen = [vid for i, vid in enumerate(vids) if vid in vids[:i]]
    if seen:
        refuse("no truck is named twice",
               "{} 7-T3".format(SPEC),
               "{} repeats {}.".format(door, ", ".join(sorted(set(seen)))))
    return vids


_VIDS = resolve_vids(os.environ.get("M6V2_VIDS"), sys.argv)


# ----------------------------------------------------------------------
# THE REFUSALS. Everything below runs at import, before a single process.
# ----------------------------------------------------------------------
for _path in (_WORLD, _IO_SCRIPT, _STO_SCRIPT):
    if not os.path.isfile(_path):
        refuse("every shared file this launch opens exists",
               TOOL, "no such file: {}".format(_path))

_M6V2_MODELS = {vid: os.path.join(_M6V2_VEHICLES, vid, "model.sdf")
                for vid in _VIDS}
_M6V2_CONFIGS = {vid: os.path.join(_M6V2_VEHICLES, vid, "config.yaml")
                 for vid in _VIDS}
_M6_CONFIGS = {vid: os.path.join(_M6_VEHICLES, vid, "config.yaml")
               for vid in _VIDS}

# A BUILD PRODUCT IS NOT "MISSING", IT HAS NOT BEEN MADE, and what the
# operator needs is the command that makes it. m6's derived pair is
# checked by existence only - its own tool owns its freshness, and this
# branch does not write under m6/.
for _vid in _VIDS:
    if not os.path.isfile(_M6_CONFIGS[_vid]):
        refuse("m6's derived vehicle config exists",
               "m6/tools/instantiate_vehicle.py",
               "no derived config for {}: {}".format(_vid, _M6_CONFIGS[_vid]),
               "sto_contactor.py and forklift_io.py read THAT spelling and",
               "the m5v3 schema does not carry it. Make it:",
               "  ( cd {} && python3 tools/instantiate_vehicle.py --all )"
               .format(os.path.join("<repo>", "m6")))

# THE m6v2 DERIVATION IS CHECKED, NOT MERELY COUNTED. Existence is the
# weaker half: a derived model.sdf left over from a donor that has since
# moved spawns a truck whose frames, topics and params no longer match
# the config the stack is about to be handed, and every symptom of that
# is a silence - a costmap with no scan, an AMCL with no map, a bridge
# on names nothing publishes. instantiate_truck.check() re-derives from
# the donor bytes and compares, which is the only test that can see it.
_STALE = []
for _vid in _VIDS:
    _STALE.extend("{}: {}".format(_vid, _line)
                  for _line in instantiate_truck.check(_vid, _M6V2_VEHICLES))
if _STALE:
    refuse("the derivation on disk is the one the tool writes",
           "{} 3.5".format(SPEC), *(
               list(_STALE)
               + ["NOTHING WAS STARTED. Re-derive:",
                  "  python3 m6_ver2/tools/instantiate_truck.py --all"]))


def _read_topics(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["topics"]


_M6_TOPICS = {vid: _read_topics(_M6_CONFIGS[vid]) for vid in _VIDS}
_M6V2_TOPICS = {vid: _read_topics(_M6V2_CONFIGS[vid]) for vid in _VIDS}
_SCAN_FMTS = {vid: status_contract.contract(vid)["scan_topic"]
              for vid in _VIDS}


# ----------------------------------------------------------------------
# THE TWO FAMILIES, RECONCILED
# ----------------------------------------------------------------------
#: Six wires that BOTH derived configs name, m6's key on the left and
#: m5v3's on the right. They are the whole overlap: the model spawned is
#: the m5v3-derived one and most of the bridge is built from m6's names,
#: so if any of these six pairs ever disagreed the bridge would open a
#: channel the model does not publish on, and the missing data would look
#: like a sensor fault in four different subsystems.
SHARED_WIRES = (
    ("gz_actuator_steer_cmd", "steer_cmd"),
    ("gz_actuator_traction_cmd", "traction_cmd"),
    ("gz_odom", "odom_ground_truth"),
    ("gz_scan_nav", "scan_nav"),
    ("gz_imu", "imu"),
    ("gz_joint_state", "joint_state"),
)


def agree(vids, m6_topics, m6v2_topics, scan_fmts):
    """Refuse unless the two derivations spell one wire one way.

    Also the back scanner, which is a third spelling of the same wire:
    m5v3's config carries it as `safety_scan_back` and m6 has never heard
    of the scanners at all, so status_contract's scan_topic format is the
    one home and this is where the m5v3 side is held to it.
    """
    for vid in vids:
        left, right = m6_topics[vid], m6v2_topics[vid]
        for m6_key, m5v3_key in SHARED_WIRES:
            if left.get(m6_key) != right.get(m5v3_key):
                refuse("the two derived configs spell one wire one way",
                       "{} 4".format(SPEC),
                       "{}: m6/vehicles/{}/config.yaml topics.{} is {!r}"
                       .format(vid, vid, m6_key, left.get(m6_key)),
                       "{}: m6_ver2/vehicles/{}/config.yaml topics.{} is {!r}"
                       .format(vid, vid, m5v3_key, right.get(m5v3_key)),
                       "One of the two derivation tools has moved under the",
                       "other. NOTHING WAS STARTED.")
        want = scan_fmts[vid].format("back")
        if right.get("safety_scan_back") != want:
            refuse("the back scanner has one name",
                   "m6/ipc/status_contract.py (scan_topic)",
                   "{}: contract says {!r}".format(vid, want),
                   "{}: m6_ver2/vehicles/{}/config.yaml topics."
                   "safety_scan_back is {!r}"
                   .format(vid, vid, right.get("safety_scan_back")))


agree(_VIDS, _M6_TOPICS, _M6V2_TOPICS, _SCAN_FMTS)


# ----------------------------------------------------------------------
# THE BRIDGE. '[' is gz to ROS, ']' is ROS to gz.
# ----------------------------------------------------------------------
def bridge_args(vids, m6_topics, m6v2_topics, scan_fmts):
    """The deduplicated union, one line per channel, /clock first.

    ONE BRIDGE PROCESS CARRIES EVERY TRUCK. Every argument is a fully
    namespaced topic, so a second bridge would buy nothing but a second
    thing to start, stop and sweep - and a second PUBLISHER on every
    channel both of them carried, which is the defect
    SPEC_NAMESPACING.md 4 rejects per-truck bridges over.

    THE DUPLICATE CHECK IS PART OF THE BUILDER AND NOT A TEST OF IT.
    A test can only fail after someone runs it; this refuses at import,
    on the machine, with the topic named. It is SPEC_NAMESPACING.md 5's
    single-writer pin, enforced where the list is made.
    """
    args, seen, clock = [], {}, None

    def add(topic, line):
        if topic in seen:
            refuse("one line per channel in the bridge",
                   "{} 5 (single-writer pins)".format(SPEC),
                   "{} is bridged twice:".format(topic),
                   "  {}".format(seen[topic]), "  {}".format(line))
        seen[topic] = line
        args.append(line)

    for vid in vids:
        left, right = m6_topics[vid], m6v2_topics[vid]
        # /clock IS THE WORLD'S, NOT A TRUCK'S. It carries no per-vehicle
        # prefix, so no rewrite touches it in either family and all of
        # them must agree: two clocks on one world would be two opinions
        # about now. Bridged once, below, ahead of everything.
        for name, value in (("m6", left["clock"]),
                            ("m6v2", right["clock"])):
            if clock is None:
                clock = value
            elif value != clock:
                refuse("one world, one clock", "{} 4".format(SPEC),
                       "{}'s {} config says {} and another says {}"
                       .format(vid, name, value, clock))
        # ROS -> gz: THE ACTUATOR TERMINALS, and only those. That vehicle's
        # sto_contactor.py is their only publisher, so bridging the
        # TERMINALS rather than the command topics puts the contactor
        # inside the path: with its latch open, nothing any ROS publisher
        # does reaches the plant.
        add(left["gz_actuator_steer_cmd"],
            "{}@std_msgs/msg/Float64]gz.msgs.Double"
            .format(left["gz_actuator_steer_cmd"]))
        add(left["gz_actuator_traction_cmd"],
            "{}@std_msgs/msg/Float64]gz.msgs.Double"
            .format(left["gz_actuator_traction_cmd"]))
        # gz -> ROS: GROUND TRUTH, FOR EVIDENCE ONLY. SPEC_ADAPTER.md
        # Decision 4's firewall - nothing in the adapter or the fleet
        # path may consume this; the estimate rides /<vid>/est/odom. It
        # is here so m6/tools/score_run.py can score the run against the
        # truth it hardcodes, and for no other reason.
        add(left["gz_odom"],
            "{}@nav_msgs/msg/Odometry[gz.msgs.Odometry".format(
                left["gz_odom"]))
        add(left["gz_scan_nav"],
            "{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan"
            .format(left["gz_scan_nav"]))
        # The drive shaft's two reading channels: one shaft, two
        # JointStatePublisher systems on drive_wheel_joint, a
        # single-channel TESTED system and never a two-channel one.
        # gz.msgs.Model IS the joint-state type on the gz side.
        for key in ("gz_drive_speed_read_a", "gz_drive_speed_read_b"):
            add(left[key],
                "{}@sensor_msgs/msg/JointState[gz.msgs.Model"
                .format(left[key]))
        # The three microScan3s, named by the contract because
        # config.yaml has never heard of them.
        for corner in ("back", "left", "right"):
            topic = scan_fmts[vid].format(corner)
            add(topic, "{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan"
                       .format(topic))
        # THE TWO LINES m6 NEVER HAD. m5v3's wheel_odometry reads the
        # joint states and its EKF fuses the IMU; without these the
        # estimator comes up on one sensor and says nothing about it.
        add(right["imu"], "{}@sensor_msgs/msg/Imu[gz.msgs.IMU"
                          .format(right["imu"]))
        add(right["joint_state"],
            "{}@sensor_msgs/msg/JointState[gz.msgs.Model"
            .format(right["joint_state"]))
    args.insert(0, "{}@rosgraph_msgs/msg/Clock[gz.msgs.Clock".format(clock))
    return args


_BRIDGE_ARGS = bridge_args(_VIDS, _M6_TOPICS, _M6V2_TOPICS, _SCAN_FMTS)


# ----------------------------------------------------------------------
# THE SHARED MAP SERVER
# ----------------------------------------------------------------------
# ONE FROZEN GRID, SERVED ONCE, OFF THE DONOR'S OWN PARAMS FILE.
# m5_ver3/amcl.yaml carries a bare `map_server:` key, which addresses the
# ROOT-namespace node and therefore matches /map_server exactly - so this
# server needs ZERO derived bytes. The derived per-truck amcl.yaml is
# wrapped under `<vid>:` and its map_server block is DEAD by design
# (instantiate_truck.py's header says so): four servers latching four
# copies of one immutable grid could differ only by mistake.
# Everything on the command line below is an ADDRESS the donor config
# already owns - the artifact's path, the topic, the frame - passed as
# `-p` overrides so amcl.yaml cannot hold a second copy of any of them.
# This is m5v3.sh:2379-2390, un-namespaced.
with open(os.path.join(_DONOR, "config.yaml"), "r",
          encoding="utf-8") as _handle:
    _DONOR_CFG = yaml.safe_load(_handle)

_LOC = _DONOR_CFG["localization"]
_MAP_SERVER_NODE = _LOC["map_server"]["node_name"]
_AMCL_PARAMS = os.path.join(_REPO, _LOC["amcl"]["params_file"])
_MAP_DIR = os.path.join(_REPO, _DONOR_CFG["map"]["dir"],
                        _DONOR_CFG["map"]["name"])
_MAP_YAML = os.path.join(_MAP_DIR, _DONOR_CFG["map"]["name"] + ".yaml")
_LIFECYCLE_TIMEOUT_S = int(_LOC["lifecycle_timeout_s"])

for _path in (_AMCL_PARAMS, _MAP_YAML):
    if not os.path.isfile(_path):
        refuse("the donor's map artifacts are where its config says",
               "m5_ver3/config.yaml", "no such file: {}".format(_path),
               "The donor is never edited on this branch, so this is a",
               "checkout problem and not a derivation one.")

# THE GRID'S md5 IS NOT CHECKED HERE, AND THAT IS DELIBERATE. The binding
# between this .pgm and the registration that carries map coordinates
# into m6 world coordinates lives in map_register.load_registration,
# which the adapter calls on every truck - so a grid that moved under the
# registration is refused by the thing that would be WRONG about it,
# once per truck, rather than by a second copy of the check here.


def map_server_cmd(node_name=_MAP_SERVER_NODE, params=_AMCL_PARAMS,
                   map_yaml=_MAP_YAML, topic=None, frame=None):
    """`ros2 run nav2_map_server map_server ...`, as m5v3.sh spells it."""
    topic = _DONOR_CFG["topics"]["map"] if topic is None else topic
    frame = _DONOR_CFG["frames"]["map"] if frame is None else frame
    return [_LOC["map_server"]["package"], _LOC["map_server"]["executable"],
            "--ros-args", "-r", "__node:={}".format(node_name),
            "--params-file", params,
            "-p", "use_sim_time:=true",
            "-p", "yaml_filename:={}".format(map_yaml),
            "-p", "topic_name:={}".format(topic),
            "-p", "frame_id:={}".format(frame)]


def map_server_lifecycle_script(node_name=_MAP_SERVER_NODE,
                                budget=_LIFECYCLE_TIMEOUT_S):
    """Drive /map_server to ACTIVE, then say so and exit.

    THE TARGET IS A STATE AND NOT A SEQUENCE OF COMMANDS - m5v3.sh's
    ruling at :1360-1385, which cost a bringup. A request to CONFIGURE is
    a claim about the current state; a request to BE ACTIVE is not. So
    this drives what it finds: unconfigured gets a configure, inactive
    gets an activate, active is done, a transition in progress is waited
    out. Idempotent, and it cannot race whatever else moved the node.

    WHY IT IS A PROCESS AND NOT A launch_ros LIFECYCLE HANDLER. The same
    loop, in the same words, drives the four namespaced AMCLs from
    truck.sh - one mechanism for one job across two files, and the
    failure prints the same sentence from either.

    A TIMEOUT IS A LOUD REFUSAL THAT LEAVES THE CELL UP, which is the
    m5v3 rule: the four truck runners each gate their AMCL on /map being
    latched, so a map_server that never activated stops the trucks at
    their own gate, by name, instead of being repaired by a teardown that
    would take the world with it.
    """
    return (
        'node="{node}"; budget={budget}; deadline=$(( $(date +%s) + $budget ));'
        ' state="";'
        ' until [ "$state" = active ]; do'
        '   state="$(ros2 lifecycle get "/$node" 2>/dev/null | cut -d" " -f1)";'
        '   case "$state" in'
        '     unconfigured) ros2 lifecycle set "/$node" configure || true ;;'
        '     inactive) ros2 lifecycle set "/$node" activate || true ;;'
        '     active) break ;;'
        '   esac;'
        '   if [ "$(date +%s)" -ge "$deadline" ]; then'
        '     echo "{tool}: REFUSED at check \'/$node reached ACTIVE inside'
        ' ${{budget}}s\'";'
        '     echo "  owned by: m5_ver3/config.yaml'
        ' (localization.lifecycle_timeout_s)";'
        '     echo "  it is in state \'${{state:-unreadable}}\' and this'
        ' launch has been driving it towards active for the whole budget.";'
        '     echo "  AN INACTIVE map_server PUBLISHES NO MAP, and every'
        ' AMCL on this cell blocks in on_activate waiting for one.";'
        '     echo "  THE CELL IS INCOMPLETE, and what is left of it is'
        ' STILL UP.";'
        '     exit 1;'
        '   fi;'
        '   sleep 1;'
        ' done;'
        ' echo "{tool}: /$node active - the grid is latched on {topic}"'
    ).format(node=node_name, budget=budget, tool=TOOL,
             topic=_DONOR_CFG["topics"]["map"])


# ----------------------------------------------------------------------
# THE GUI GATE
# ----------------------------------------------------------------------
# The client waits for the back scanner of EVERY truck this launch
# spawns, and it has to: gz-sim 8.11.0's GuiRunner discards every
# /world/*/state message that arrives before its initial state_async
# response is processed, and VisualizeLidar's SensorTopic components are
# created by the render thread a beat AFTER the spawn - so a GUI let in
# after f1's scanners advertised but before f4's draws f4's three fans at
# the world origin, for the life of the window. Measured 2026-08-12; the
# full reasoning is m6/gazebo/m6_world.launch.py's. Built from _VIDS, so
# a one-truck gate is exactly as correct as a four-truck one.
_GUI_GATE_TOPICS = tuple(_SCAN_FMTS[vid].format("back") for vid in _VIDS)


def _gz_server(context, *args, **kwargs):
    """The world server. -s is server-only; the GUI is a second process.

    Built in a function rather than declared, because
    --headless-rendering has to be ABSENT from the command line when the
    GUI is wanted rather than present with a false value.

    THE PARTITION COMES FROM THE ENVIRONMENT AND IS NOT SET HERE.
    m6_ver2/m6v2.sh exports GZ_PARTITION before `ros2 launch`, every
    child inherits it, and it is what `ours()` reads back to decide the
    sweep may kill a process. A partition named on this command line
    would be a second home for it - and the one the SWEEP does not read.
    """
    cmd = ["gz", "sim", "-s", "-r"]
    if LaunchConfiguration("gui").perform(context).lower() != "true":
        cmd.append("--headless-rendering")
    cmd += ["-v", "2", _WORLD]
    return [ExecuteProcess(cmd=cmd, name="gz_server", output="screen")]


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        "gui", default_value="false",
        description="Also start the Gazebo GUI client (headless if false)"))
    # DECLARED SO `ros2 launch -s` LISTS IT, resolved at import by
    # resolve_vids() off this same argv. See that function's header for
    # why a substitution cannot do this job.
    ld.add_action(DeclareLaunchArgument(
        "vids", default_value=" ".join(_ALL_VIDS),
        description="Which trucks to spawn and bridge (also M6V2_VIDS)"))

    ld.add_action(OpaqueFunction(function=_gz_server))

    ld.add_action(ExecuteProcess(
        cmd=["bash", "-c",
             "until {}; do sleep 0.5; done; sleep 2; "
             "exec gz sim -g -v 2".format(
                 " && ".join("gz topic -l 2>/dev/null | grep -qF '{}'"
                             .format(t) for t in _GUI_GATE_TOPICS))],
        name="gz_gui",
        output="screen",
        condition=IfCondition(LaunchConfiguration("gui")),
    ))

    ld.add_action(Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="m6v2_bridge",
        output="screen",
        arguments=_BRIDGE_ARGS,
    ))

    # THE MAP GOES UP WITH THE WORLD AND NOT WITH A TRUCK, because it is
    # not a truck's. Both processes start here; the second one blocks
    # until `ros2 lifecycle get` can answer, so their order on this list
    # buys nothing and costs nothing.
    ld.add_action(ExecuteProcess(
        cmd=["ros2", "run"] + map_server_cmd(),
        name="map_server", output="screen"))
    ld.add_action(ExecuteProcess(
        cmd=["bash", "-c", map_server_lifecycle_script()],
        name="map_server_lifecycle", output="screen"))

    # ONE LOOP FOR THE WHOLE TRUCK SIDE: three processes per truck, all
    # pointed at that truck's derived files - the MODEL from m6_ver2's
    # derivation, the CONFIG for the two fleet nodes from m6's, because
    # those two read m6's spelling and would KeyError on m5v3's.
    for vid in _VIDS:
        c = status_contract.contract(vid)
        ld.add_action(Node(
            package="ros_gz_sim",
            executable="create",
            name="spawn_forklift_{}".format(vid),
            output="screen",
            arguments=[
                "-world", _WORLD_NAME,
                "-file", _M6V2_MODELS[vid],
                # THE MODEL NAME IS THE TRUCK ID, and it is what anything
                # addressing ONE truck through a gz service spells -
                # m6.sh's `home` and tools/rtf_spike.sh both say
                # forklift_<vid>, so the three must agree.
                "-name", "forklift_{}".format(vid),
                "-x", c["spawn"]["x"],
                "-y", c["spawn"]["y"],
                "-z", c["spawn"]["z"],
                "-Y", c["spawn"]["yaw"],
                "-allow_renaming", "false",
            ],
        ))
        # The two fleet nodes, started exactly as m6_world.launch.py
        # starts them - the contactor carries use_sim_time, forklift_io
        # does not - with the same __node remap, so two instances of one
        # script do not both call themselves sto_contactor.
        ld.add_action(ExecuteProcess(
            cmd=[sys.executable, _STO_SCRIPT, "--config", _M6_CONFIGS[vid],
                 "--ros-args", "-p", "use_sim_time:=true",
                 "-r", "__node:=sto_contactor_{}".format(vid)],
            name="sto_contactor_{}".format(vid),
            output="screen",
        ))
        ld.add_action(ExecuteProcess(
            cmd=[sys.executable, _IO_SCRIPT, "--config", _M6_CONFIGS[vid],
                 "--ros-args",
                 "-r", "__node:=forklift_io_{}".format(vid)],
            name="forklift_io_{}".format(vid),
            output="screen",
        ))

    return ld
