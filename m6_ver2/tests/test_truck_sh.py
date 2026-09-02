"""The pins on m6_ver2/truck.sh - SPEC_NAMESPACING.md 1, 3 and 5.

THIS SUITE READS A SHELL SCRIPT AS TEXT, AND THAT IS THE ONLY WAY THE
THING IT PINS CAN BE PINNED AT ALL. Every failure below is SILENT at run
time: a remap whose match side is absolute simply does not fire, so the
node keeps its default topic and comes up healthy on the wrong address;
a spawn line that lost its `__ns` produces a second node with the same
name in the root namespace, which ROS 2 permits; a sweep that asks only
about the partition kills the neighbour trucks and the whole m6 fleet
layer with them. None of the three raises anything, none is visible in a
log, and all three need a four-truck bringup to observe - which is
exactly the class of thing a source pin is for.

NO PROCESS IS STARTED FROM HERE. The two `bash` invocations are the
argument parser's refusals, which exit before the script sources
anything at all.
"""
import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, ".."))
TRUCK_SH = os.path.join(_M6V2, "truck.sh")
COMMON_SH = os.path.join(_M6V2, "tools", "_truck_common.sh")


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


TRUCK = read(TRUCK_SH)
COMMON = read(COMMON_SH)


def logical_lines(text):
    """The script's lines with comments dropped and continuations joined.

    A `spawn` command spans up to a dozen physical lines, and every pin
    below asks whether a flag is present SOMEWHERE in ONE command - so
    the command has to be one string. This is a quote-aware scan rather
    than a regex because both are needed and neither is optional: an
    apostrophe inside a double-quoted refusal line ("this truck's five
    channels") must not read as an open quote, and the embedded
    `python3 -c '...'` program must stay whole across its own newlines.
    """
    out, buffer_ = [], []
    single = double = False
    index, end = 0, len(text)
    while index < end:
        char = text[index]
        if char == "#" and not single and not double:
            newline = text.find("\n", index)
            index = end if newline < 0 else newline
            continue
        continued = (char == "\\" and not single
                     and text[index + 1:index + 2] == "\n")
        if continued:
            buffer_.append(" ")
            index += 2
            continue
        if char == "'" and not double:
            single = not single
        elif char == '"' and not single:
            double = not double
        if char == "\n" and not single and not double:
            line = "".join(buffer_)
            if line.strip():
                out.append(line)
            buffer_ = []
            index += 1
            continue
        buffer_.append(char)
        index += 1
    tail = "".join(buffer_)
    if tail.strip():
        out.append(tail)
    return out


LINES = logical_lines(TRUCK)

#: Every child truck.sh starts, as (name, whole command). `spawn` is
#: the only door: nothing else in this script forks a ROS process.
SPAWNS = [(match.group(1), line) for line in LINES
          for match in [re.search(r"\bspawn\s+(\S+)\s", line)]
          if match and not line.lstrip().startswith("spawn()")]


def test_the_spawn_table_is_the_stack():
    """Fourteen children, and the list is checked rather than counted.

    A child added without a pattern in _truck_common.sh is a child
    `stop` orphans while still printing "down." - the maintenance
    obligation both files carry, made mechanical here.
    """
    names = [name for name, _ in SPAWNS]
    assert names == [
        "imutf", "lasertf", "odom", "ekf", "smoother", "monitor",
        "scanmask", '"$CFG_LOCALIZATION_AMCL_NODE_NAME"',
        '"$CFG_NAV_PLANNER_NODE_NAME"', '"$CFG_NAV_CONTROLLER_NODE_NAME"',
        '"$CFG_NAV_BEHAVIOR_NODE_NAME"', '"$CFG_NAV_BT_NODE_NAME"',
        '"$CFG_NAV_LIFECYCLE_NODE_NAME"', "adapter",
    ], names


def test_every_ros_child_is_namespaced_and_shares_the_tree():
    """`${NS[@]}` on every spawn line, and it is the whole of §1 and §2.

    Without it nav2's COSTMAP SUB-NODES - which have no command line, so
    `-r __node:=` cannot reach them - collide by name across four
    trucks, and every namespaced node publishes tf on /<vid>/tf so the
    four trees never meet.
    """
    for name, line in SPAWNS:
        assert '"${NS[@]}"' in line, name


def test_the_namespace_array_carries_all_three_remaps():
    # Read off the raw source: bash allows a bare newline inside `( )`,
    # so this one is not a logical line the way a command is.
    array = re.findall(r"NS=\((.*?)\)", TRUCK, re.S)
    assert len(array) == 1
    text = array[0]
    assert '-r "__ns:=/$VID"' in text
    assert '-r "tf:=$CFG_TOPICS_TF"' in text
    assert '-r "tf_static:=$CFG_TOPICS_TF_STATIC"' in text


def test_the_one_shot_children_are_namespaced_too():
    """nav2_seed is a gate rather than a stack child, and it is still ours.

    It runs in the foreground and is not in the pidfile, but it is a ROS
    process on a shared graph: unnamespaced it would be /nav2_seed four
    times over, and a hung one could not be swept by vid.
    """
    seed = [line for line in LINES
            if "nav2_seed.py" in line and "python3" in line]
    assert len(seed) == 1
    assert '"${NS[@]}"' in seed[0]
    assert "--vid" in seed[0]


#: Every `-r` remap on a spawn line, as (match side, replacement).
REMAPS = [(match.group(1), match.group(2))
          for _, line in SPAWNS
          for match in re.finditer(r'-r\s+"?([^:\s"]+):=([^\s"]+)"?', line)]


def test_remap_match_sides_are_relative():
    """THE SILENT-BREAKAGE PIN (SPEC_NAMESPACING.md 1).

    m5v3.sh writes `-r /cmd_vel:=...`, `-r /cmd_vel_smoothed:=...` and
    `-r /odometry/filtered:=...`. Under `__ns` an absolute match side
    matches NOTHING: the remap never fires, the node keeps its default
    name, and the failure is a smoother subscribed to the right topic by
    luck or a controller publishing where nobody listens. Only the
    REPLACEMENT may be absolute.
    """
    for match_side, replacement in REMAPS:
        if match_side.startswith("__"):
            continue
        assert not match_side.startswith("/"), (match_side, replacement)
    # And the three the port had to change are all present, relative.
    sides = [side for side, _ in REMAPS]
    for side in ("cmd_vel", "cmd_vel_smoothed", "odometry/filtered"):
        assert side in sides, side


def test_the_tf_pair_lands_on_the_shared_tree():
    """`tf`/`tf_static` are remapped OUT of the namespace, not into it."""
    for match_side, replacement in REMAPS:
        if match_side in ("tf", "tf_static"):
            assert replacement in ("$CFG_TOPICS_TF", "$CFG_TOPICS_TF_STATIC")


def test_no_two_children_share_a_node_name():
    """Eight static transform publishers in four namespaces, all named.

    m5v3 could leave `static_transform_publisher` unnamed because it ran
    one truck; two of them in ONE namespace is a name collision, and
    `ros2 node list` on four trucks would be unreadable either way.
    """
    names = [match.group(1) for _, line in SPAWNS
             for match in [re.search(r"-r __node:=(\S+)", line)] if match]
    assert len(names) == len(set(names)), names
    assert len(names) == len(SPAWNS), "every child is named"


def test_the_world_is_not_started_here():
    """SPEC_NAMESPACING.md 4: one server, one bridge, one map_server.

    A per-truck bridge is a second publisher on /clock; a per-truck
    map_server is a second latched copy of one frozen grid. Both are
    the world launch's, and this pin is what keeps them there.
    """
    for _, line in SPAWNS:
        for forbidden in ("gz sim", "parameter_bridge", "image_bridge",
                          "nav2_map_server", "map_server"):
            assert forbidden not in line, (forbidden, line[:60])


def test_the_world_gate_refuses_by_name():
    """/map and this truck's bridged channels, before anything starts."""
    body = TRUCK[TRUCK.index("check_world() {"):]
    body = body[:body.index("\n}\n")]
    for key in ("$CFG_TOPICS_CLOCK", "$CFG_TOPICS_MAP",
                "$CFG_TOPICS_SCAN_NAV", "$CFG_TOPICS_IMU",
                "$CFG_TOPICS_JOINT_STATE",
                "$CFG_TOPICS_DRIVE_SPEED_READ_A"):
        assert key in body, key
    assert "NOTHING WAS STARTED." in body
    assert "m6v2.sh" in body


def test_health_gate_addresses_are_namespaced():
    """Every lifecycle and node-list address carries the truck.

    `ros2 lifecycle get /amcl` names nobody on this branch, and a loop
    polling it would spend its whole budget against a node that reached
    ACTIVE ten seconds in.
    """
    for call in re.findall(r'ros2 lifecycle (?:get|set) "([^"]+)"', TRUCK):
        assert call.startswith("/$VID/"), call
    assert 'grep -q "^/$VID/$node$"' in TRUCK
    assert 'action="/$VID/navigate_to_pose"' in TRUCK


def test_amcl_reads_the_shared_map_and_the_masked_scan():
    amcl = [line for _, line in SPAWNS
            if "CFG_LOCALIZATION_AMCL_EXECUTABLE" in line]
    assert len(amcl) == 1
    line = amcl[0]
    # THE PARAMETERS ARE NOT REMAPPED BY __ns, so map_topic stays the
    # one shared absolute name and scan_topic is the masked address.
    assert '-p map_topic:="$CFG_TOPICS_MAP"' in line
    assert '-p scan_topic:="$MASKED_SCAN"' in line
    assert '-p global_frame_id:="$CFG_FRAMES_MAP"' in line
    assert '-p odom_frame_id:="$CFG_FRAMES_ODOM"' in line
    assert '-p base_frame_id:="$CFG_FRAMES_BASE_LINK"' in line


def test_the_masked_scan_is_asked_for_and_never_spelled():
    """One spelling, and it lives in the derivation tool.

    The costmaps' copy of this address is a FILE literal - they are
    sub-nodes with no command line - so if this script composed the name
    itself there would be two copies and no mechanism that could notice
    them diverging. It asks the module that wrote the file, and then
    check_address proves the file agrees.
    """
    assert "instantiate_truck.masked_scan_topic" in TRUCK
    assert "scan_nav_masked" not in TRUCK
    assert 'check_address "$NAV_PARAMS" topic "$MASKED_SCAN"' in TRUCK


def test_the_adapter_gets_the_command_path_and_a_world_frame():
    adapter = [line for name, line in SPAWNS if name == "adapter"][0]
    assert '-r "cmd_vel_smoothed:=$adapter_in"' in adapter
    assert '--world-frame "$WORLD_FRAME"' in adapter
    # The monitor is what moves that address, and nothing else.
    assert 'adapter_in="$CFG_TOPICS_CMD_VEL_MONITORED"' in TRUCK
    assert 'local adapter_in="$CFG_TOPICS_CMD_VEL_SMOOTHED"' in TRUCK


def test_every_config_variable_it_reads_is_declared():
    """The dotted-name maintenance obligation, made mechanical.

    m5_ver3/tools/_common.sh refuses a config that parses but has been
    reorganised - by DOTTED NAME, before anything starts - and it can
    only do that for keys the caller declared. A key read but not
    declared reaches the first spawn as an empty string on a command
    line, which is a node addressed to nothing.
    """
    declared = re.search(r"REQUIRED_KEYS=\((.*?)\n\)", TRUCK, re.S).group(1)
    keys = set(declared.split())
    # The three every m5v3 script gets for free (_common.sh _COMMON_KEYS).
    keys |= {"isolation.gz_partition", "isolation.ros_domain_id",
             "paths.ros_setup"}
    allowed = set("CFG_" + key.upper().replace(".", "_") for key in keys)
    used = set(re.findall(r"\$\{?(CFG_[A-Z0-9_]+)", TRUCK))
    assert used - allowed == set(), sorted(used - allowed)


def test_declared_keys_are_all_read():
    """And the obligation the other way: a key nobody reads is noise."""
    declared = re.search(r"REQUIRED_KEYS=\((.*?)\n\)", TRUCK, re.S).group(1)
    used = set(re.findall(r"\$\{?(CFG_[A-Z0-9_]+)", TRUCK))
    # THE TWO THE DONOR'S OWN HELPER READS. btdir_paths() in
    # m5_ver3/tools/_common.sh - sourced, never copied - builds the BT
    # plugin's build-tree paths off bt_direction.workspace and
    # bt_direction.package, so truck.sh declares them and never spells
    # them. A caller that stopped declaring them would get bash's
    # unbound-variable abort from inside somebody else's file.
    indirect = {"bt_direction.workspace", "bt_direction.package"}
    unread = [key for key in declared.split()
              if key not in indirect
              and "CFG_" + key.upper().replace(".", "_") not in used]
    assert unread == [], unread


# ----------------------------------------------------------------------
# tools/_truck_common.sh - the sweep, and the seam it stands on.
# ----------------------------------------------------------------------

def test_ownership_needs_the_partition_AND_the_truck():
    """The pin that stops one truck's stop from taking the world down.

    m5v3.sh's ours() asks only about GZ_PARTITION because its partition
    named exactly one stack. Here the partition is `m6` and it is
    carried by the three neighbour trucks, by m6.sh's whole fleet layer
    and by the world launch - so a sweep keyed on it alone would kill
    all of them, quietly, on a routine `truck.sh f2 stop`.
    """
    body = COMMON[COMMON.index("truck_ours() {"):]
    body = body[:body.index("\n}\n")]
    assert 'grep -qxF "GZ_PARTITION=$GZ_PARTITION"' in body
    assert 'grep -qxF "M6V2_VID=$M6V2_VID"' in body
    assert body.count("|| return 1") >= 3
    # And the vid reaches every child's environment.
    assert 'export M6V2_VID="$vid"' in COMMON


def test_the_sweep_patterns_drop_the_world_and_add_this_track():
    patterns = re.search(r"M6V2_PATTERNS=\((.*?)\)", COMMON, re.S).group(1)
    for world_owned in ('"gz sim"', '"parameter_bridge"', '"image_bridge"',
                        '"nav2_map_server"', '"apriltag_node"',
                        '"opennav_docking"', '"detected_dock.py"'):
        assert world_owned not in patterns, world_owned
    for mine in ('"scan_mask_node.py"', '"nav2_adapter_node.py"',
                 '"nav2_seed.py"'):
        assert mine in patterns, mine
    # wheel_odometry.py is spawned through `python3 -c`, so the pattern
    # has to be the SCRIPT NAME and the -c program has to carry it.
    assert '"wheel_odometry.py"' in patterns
    assert "import wheel_odometry" in TRUCK


def test_the_sweep_never_matches_its_own_scripts():
    body = COMMON[COMMON.index("truck_sweep() {"):]
    for script in ("truck.sh", "m6v2.sh", "m5v3.sh", "m6.sh"):
        assert "*{}*".format(script) in body, script


def test_the_config_repoint_is_read_back():
    """The seam's own gate.

    _truck_common.sh sources the donor's _common.sh and then re-points
    CONFIG at the derived per-vid file. If that silently failed, every
    name would be m5v3's: the wrong partition, the wrong domain, bare
    frames, colliding topics - and `status` would look perfect. So the
    override is PROVEN, by reading back the one key the two files must
    differ on.
    """
    assert 'CONFIG="$VEHICLE_DIR/config.yaml"' in COMMON
    assert '[ "$CFG_ISOLATION_GZ_PARTITION" = "$M6V2_PARTITION" ]' in COMMON
    assert 'M6V2_PARTITION="m6"' in COMMON
    # And the donor is SOURCED, never copied or edited.
    assert '. "$_M6V2_DONOR_COMMON"' in COMMON
    assert "m5_ver3/tools/_common.sh" in COMMON


def test_the_donor_node_is_pointed_at_this_trucks_config():
    """wheel_odometry.py declares no ROS parameters. See truck.sh.

    Run as-is it reads the DONOR config: it would publish
    /m5v3/wheel_odom (absolute, so the namespace does not touch it) and
    - the part no remap can repair - stamp its Odometry with the bare
    REP-105 frame names, which the EKF would then drop the sensor for.
    """
    odom = [line for name, line in SPAWNS if name == "odom"][0]
    assert "_common.CONFIG = config" in odom
    assert '"$CONFIG"' in odom
    assert "wheel_odometry.main()" in odom


# ----------------------------------------------------------------------
# The script itself, run - and only where running it starts nothing.
# ----------------------------------------------------------------------
BASH = shutil.which("bash")


@pytest.mark.skipif(BASH is None, reason="no bash on this machine")
def test_bash_parses_both_files():
    for path in (TRUCK_SH, COMMON_SH):
        done = subprocess.run([BASH, "-n", path], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        assert done.returncode == 0, done.stdout.decode("utf-8", "replace")


@pytest.mark.skipif(BASH is None, reason="no bash on this machine")
@pytest.mark.parametrize("argv", [
    ["nope", "start"],       # not a vehicle id
    ["f1", "fly"],           # not a subcommand
    ["f1", "start", "--go"],  # not an option
    [],                      # nothing at all
])
def test_the_argument_parser_refuses_before_it_sources_anything(argv):
    """Exit 2, and NOTHING is started - these run before the source line."""
    done = subprocess.run([BASH, TRUCK_SH] + argv, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    assert done.returncode == 2, done.stdout.decode("utf-8", "replace")
    assert b"usage:" in done.stdout
