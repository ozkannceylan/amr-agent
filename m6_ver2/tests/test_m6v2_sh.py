"""m6v2.sh's shape, read off the script and off the one it grew from.

A SHELL SCRIPT CANNOT BE IMPORTED, so this is the repo's source-pin
idiom: m5_ver3/tests/test_sweep_patterns.py parses `m5v3.sh` and asserts
against what it finds rather than against a table typed beside it, for
the reason that file's header gives - "a child added to start() and not
to the table passes". The same rule holds here and it holds ACROSS TWO
FILES: the m6v2 fleet child list is DEFINED as m6.sh's minus nav_node.py,
so it is parsed out of both scripts and compared, and a child added to
m6.sh has to be answered for here.

NOTHING IS EXECUTED except `bash -n`, and that only where a bash exists.
"""
import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, os.pardir))
_REPO = os.path.normpath(os.path.join(_M6V2, os.pardir))
_M6V2_SH = os.path.join(_M6V2, "m6v2.sh")
_M6_SH = os.path.join(_REPO, "m6", "m6.sh")


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def source():
    return read(_M6V2_SH)


@pytest.fixture(scope="module")
def m6_source():
    return read(_M6_SH)


#: `spawn "<name>_$vid" "$vid" python3 "<path>"` - the per-truck fleet
#: children, in the order the script starts them. Both scripts write the
#: loop the same way, which is what makes the comparison below possible.
_PER_VID_SPAWN = re.compile(
    r'spawn\s+"([a-z_0-9]+)_\$vid"\s+"\$vid"\s+python3\s+"([^"]+)"')

#: Every spawn line, whatever its shape, folded onto one line first.
_ANY_SPAWN = re.compile(r'(?m)^\s*(?:[A-Z_]+="[^"]*"\s+)?spawn\s+(\S+)\s+(\S+)\s+(.*)$')


def fold(text):
    """Backslash-newline continuations joined, runs of blanks squeezed."""
    folded = re.sub(r"\\\n\s*", " ", text)
    return "\n".join(re.sub(r"[ \t]{2,}", " ", line)
                     for line in folded.splitlines())


def per_vid_children(text):
    """[(name, script basename)] in spawn order."""
    return [(name, os.path.basename(path))
            for name, path in _PER_VID_SPAWN.findall(fold(text))]


# ----------------------------------------------------------------------
# the child list, defined against m6.sh rather than typed out
# ----------------------------------------------------------------------
def test_the_fleet_child_list_is_m6s_minus_nav_node(source, m6_source):
    # AMR-DEC-006 retires nav_node.py as the motion engine; the Nav2
    # adapter under truck.sh replaces it. Nothing else about the fleet
    # set changes, and "nothing else" is what this asserts - including
    # the ORDER, which is load-bearing: field_eval before sensor_link, so
    # the link never sends a verdict from a device that has not been
    # evaluated yet.
    m6_children = per_vid_children(m6_source)
    assert m6_children, "m6.sh's per-vehicle spawn loop stopped parsing"
    expected = [pair for pair in m6_children if pair[1] != "nav_node.py"]
    assert per_vid_children(source) == expected


def test_nav_node_is_started_by_nothing_here(source):
    # The NAME still appears, in the comment that says why it does not
    # run - which is the point. What must be absent is a spawn of it.
    spawned = " ".join(" ".join(match) for match in
                       _ANY_SPAWN.findall(fold(source)))
    assert "nav_node" not in spawned
    assert "AMR-DEC-006" in source


def test_m6_still_starts_the_nav_node_this_branch_drops(m6_source):
    # The claim above is only interesting while m6.sh still has one. When
    # m6 retires it too, this test is the reminder that the subtraction
    # has become a no-op and the two lists are simply equal.
    assert "nav_node.py" in dict(
        (script, name) for name, script in per_vid_children(m6_source))


def test_the_children_run_from_m6_source_and_not_from_the_deploy(source):
    for name, script in per_vid_children(source):
        del name
        assert script.endswith(".py")
    folded = fold(source)
    assert '$IPC/plc_link.py' in folded
    assert 'local IPC="$M6/ipc"' in folded
    assert "$M6/hmi/hmi_node.py" in folded
    # No frozen image is consulted at all - there is no DEPLOY here - and
    # that is a NAMED leftover rather than an oversight.
    assert "DEPLOY" not in folded
    assert "discipline RETURNS the day" in source


def test_the_hmi_and_the_fleet_manager_run_from_source(source):
    folded = fold(source)
    assert 'spawn fleet - python3 "$M6/fleet/fleet_manager.py"' in folded


# ----------------------------------------------------------------------
# the truck runner is the only door to a truck's stack
# ----------------------------------------------------------------------
@pytest.mark.parametrize("verb", ["start", "status", "stop"])
def test_every_truck_verb_goes_through_truck_sh(source, verb):
    assert 'bash "$TRUCK" "$vid" {}'.format(verb) in source


def test_truck_sh_is_the_only_path_and_is_refused_when_missing(source):
    assert 'TRUCK="$M6V2_DIR/truck.sh"' in source
    assert "the per-truck runner exists" in source


def test_this_script_spawns_no_autonomy_child(source):
    # The interface: m6v2.sh owns the order, the environment, the fleet
    # children and the ledger. Everything a truck runs is truck.sh's.
    spawned = " ".join(" ".join(match) for match in
                       _ANY_SPAWN.findall(fold(source)))
    for word in ("amcl", "ekf", "planner_server", "controller_server",
                 "bt_navigator", "behavior_server", "velocity_smoother",
                 "collision_monitor", "wheel_odometry", "nav2_adapter",
                 "lifecycle_manager", "map_server", "static_transform"):
        assert word not in spawned, word


def test_the_world_and_the_broker_and_the_fleet_are_what_it_does_spawn(source):
    names = sorted({match[0].strip('"')
                    for match in _ANY_SPAWN.findall(fold(source))
                    if "$vid" not in match[0]})
    assert names == ["broker", "fleet", "world"]


def test_the_world_is_started_with_the_truck_subset_in_the_environment(source):
    folded = fold(source)
    assert ('spawn world - M6V2_VIDS="${VIDS[*]}" '
            'ros2 launch "$WORLD_LAUNCH" "gui:=$GUI"') in folded
    assert 'WORLD_LAUNCH="$M6V2_DIR/world.launch.py"' in source
    # It rides the `env` the spawn execs - the broker's loader path does
    # the same - so it reaches the child and not the whole cell.
    assert "export M6V2_VIDS" not in source


# ----------------------------------------------------------------------
# the environment, and what it lets stop kill
# ----------------------------------------------------------------------
def test_the_isolation_pair_is_m6_and_96(source):
    assert 'export GZ_PARTITION="${GZ_PARTITION:-m6}"' in source
    assert 'export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-96}"' in source


def test_the_isolation_pair_is_checked_against_the_derivation(source):
    # It has two homes on purpose - stop must not need a yaml parse - so
    # the disagreement is refused rather than silently resolved.
    assert "check_isolation" in source
    assert "isolation.gz_partition" in source
    assert "isolation.ros_domain_id" in source


def test_the_fastdds_profile_defaults_to_m6s_and_that_file_exists(source):
    assert ('export FASTRTPS_DEFAULT_PROFILES_FILE='
            '"${FASTRTPS_DEFAULT_PROFILES_FILE:-$M6/tools/fastdds_loopback.xml}"'
            ) in source
    assert os.path.isfile(
        os.path.join(_REPO, "m6", "tools", "fastdds_loopback.xml"))


def test_every_child_carries_the_m6v2_marker(source):
    assert "export M6V2=1" in source


def test_ownership_needs_the_partition_and_the_marker(source):
    body = re.search(r"(?ms)^ours\(\) \{.*?^\}", source).group(0)
    assert 'grep -qxF "GZ_PARTITION=$GZ_PARTITION"' in body
    assert "grep -q '^M6V2'" in body
    # Partition alone would nominate a live m6 fleet: m6.sh exports the
    # same one. Both lines, or the sweep is a stranger's.
    assert body.count("grep -q") >= 2


def test_this_ledger_walk_keeps_ours_and_says_why(source):
    """The G2 tear reaches two scripts and is FIXED in only one.

    truck.sh's start() and status() had to stop asking truck_ours()
    whether a child is alive: /proc/<pid>/environ can be served SHORT,
    and _truck_common.sh's configure() exports M6V2_VID LAST of the
    three, so the very last line of the block is the one a torn read
    loses. Measured 2026-09-02 on the three-truck cell: one "no" in 2400
    asks of a live bt_navigator, and the step that said no was the
    M6V2_VID line every time.

    THIS SCRIPT'S ANSWER IS NOT THE SAME ANSWER, for two reasons that
    are both checkable below.

    Its marker is exported EARLY - `export M6V2=1` sits in the header
    block, above ours(), above spawn() and above every command - so the
    variable ours() greps for is near the FRONT of a child's environ
    rather than at the end of it, which is the position a short read
    takes last.

    And ours() is doing a second job here that child_alive() cannot do
    at all: recorded() proves a pid is one of THIS FAMILY (its cmdline
    carries m6), but m6.sh's plain cell carries m6 too. It is the M6V2
    marker, and only the marker, that separates this cell's world from
    the neighbour cell's - which is the distinction plain_m6_cell() is
    built on. Dropping ours() here to buy a tear that has not been
    measured here would sell that.

    So the ledger walk leads with the kernel and keeps ownership behind
    it. If the marker export ever moves below the machinery, this pin
    fails and the reasoning above has to be re-made rather than assumed.
    """
    assert source.index("export M6V2=1") < source.index("ours() {")
    assert source.index("export M6V2=1") < source.index("spawn() {")
    assert source.index("export M6V2=1") < source.index("status() {")

    status = re.search(r"(?ms)^status\(\) \{.*?^\}", source).group(0)
    assert 'kill -0 "$pid"' in status
    assert 'recorded "$pid"' in status
    assert 'ours "$pid"' in status

    # start()'s already-up check asks the kernel and the family, and
    # NOT the marker: there a "no" permits a second cell, so the pid
    # that is merely unreadable must still count as up.
    up = source[source.index("# ALREADY UP?"):]
    up = up[:up.index('rm -f "$PIDFILE"')]
    assert 'kill -0 "$pid"' in up
    assert 'recorded "$pid"' in up


def test_the_sweep_patterns_are_m6s_minus_nav_node_plus_this_world(source,
                                                                   m6_source):
    def patterns(text):
        block = re.search(r"(?ms)^PATTERNS=\((.*?)\)\n", fold(text)).group(1)
        return re.findall(r'"([^"]+)"', block)
    theirs = [p for p in patterns(m6_source) if p != "nav_node.py"]
    mine = patterns(source)
    assert "nav_node.py" not in mine
    assert "world.launch.py" in mine
    assert [p.replace("m6_world.launch.py", "world.launch.py")
            for p in theirs] == mine


def test_the_marked_sweep_needs_no_pattern_list(source):
    # truck.sh owns its children's names. A second copy of that list here
    # would be the copy that kept working after the first one changed, so
    # the residue is caught by ours() applied directly over /proc.
    assert "sweep_marked" in source
    body = re.search(r"(?ms)^sweep_marked\(\) \{.*?^\}", source).group(0)
    assert "/proc/[0-9]*" in body
    assert "ours " in body


def test_the_sweep_never_matches_its_own_family_of_scripts(source):
    for script in ("m6v2.sh", "truck.sh", "m6.sh", "m5v3.sh"):
        assert "*{}*".format(script) in source


# ----------------------------------------------------------------------
# the refusals
# ----------------------------------------------------------------------
@pytest.mark.parametrize("phrase", [
    "no plain m6 world is up in partition",
    "TWO SERVERS IN",
    "ONE PARTITION IS ONE WORLD WITH TWO OWNERS",
    "the derivation on disk is the one the tool writes",
    "python3 m6_ver2/tools/instantiate_truck.py --all",
    "every named truck is in the VEHICLES table",
    "the fleet's odom key reads the adapter's estimate",
    "the per-truck runner exists",
    "the vendored MQTT broker is installed",
    "is free for the broker",
    "the VEHICLES table is readable",
    "NOTHING WAS STARTED.",
    "THE CELL IS INCOMPLETE.",
])
def test_the_refusal_is_present_and_says_what_it_is(source, phrase):
    assert phrase in source


def test_the_renderer_gate_refuses_and_reads_its_numbers_from_the_config(
        source):
    assert "gpu_preflight" in source
    assert "gpu.gallium_driver" in source
    assert "gpu.d3d12_adapter_name" in source
    assert "gpu.required_renderer" in source
    assert 'export GALLIUM_DRIVER="$driver"' in source
    assert 'export MESA_D3D12_DEFAULT_ADAPTER_NAME="$adapter"' in source
    assert "llvmpipe measures a different machine" in source
    # The capture-then-match form, because `writer | grep -q` fails OPEN
    # under pipefail (m6.sh:227-240, measured).
    assert 'info="$(glxinfo -B 2>&1)"' in source
    assert "| grep -q" not in re.search(
        r"(?ms)^gpu_preflight\(\) \{.*?^\}", source).group(0)


def test_the_derivation_freshness_gate_runs_the_tools_own_check(source):
    assert 'python3 "$DERIVE" --vid "$vid" --check' in source
    assert 'DERIVE="$M6V2_DIR/tools/instantiate_truck.py"' in source


def test_the_fleet_config_is_derived_and_firewalled_in_one_step(source):
    """SPEC_ADAPTER.md Decision 4, wired into preflight.

    THE TWO HALVES ARE ONE COMMAND ON PURPOSE. m6's own tool writes
    m6/vehicles/<vid>/config.yaml with topics.gz_odom naming the
    SIMULATOR'S GROUND TRUTH, and vda_agent.py subscribes that key to
    count route progress. A preflight that made the file and left the
    override to an operator would come up looking exactly like a
    correct one - so the tool that makes it is the tool that firewalls
    it, and start() runs that one.
    """
    assert 'FIREWALL="$M6V2_DIR/tools/fleet_odom_firewall.py"' in source
    assert 'python3 "$FIREWALL" --vid "$vid"' in source
    # and the OLD shape is gone: existence alone is not the gate any
    # more, because a file that exists can be the unfirewalled one.
    assert 'instantiate_vehicle.py --all )' not in source


def test_the_firewall_tool_exists_and_names_the_key_the_fleet_reads():
    import sys
    tools = os.path.join(_M6V2, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import fleet_odom_firewall as firewall
    assert firewall.ODOM_KEY == "topics.gz_odom"
    assert firewall.est_odom_topic("f1") == "/f1/est/odom"
    assert firewall.truth_odom_topic("f1") == "/f1/gz/odom"


def test_a_plain_m6_cell_is_detected_by_environment_and_not_by_name(source):
    body = re.search(r"(?ms)^plain_m6_cell\(\) \{.*?^\}", source).group(0)
    assert 'grep -qxF "GZ_PARTITION=$GZ_PARTITION"' in body
    assert "grep -q '^M6V2' && continue" in body
    assert "m6_world.launch.py" in body


# ----------------------------------------------------------------------
# the ledger, the logs and the CLI
# ----------------------------------------------------------------------
def test_the_ledger_and_the_logs_live_under_m6_ver2(source):
    assert 'PIDFILE="$M6V2_DIR/.m6v2_pids"' in source
    assert 'LOGDIR="$M6V2_DIR/logs"' in source
    assert 'VIDFILE="$M6V2_DIR/.m6v2_vids"' in source


def test_the_logs_directory_is_gitignored():
    ignore = read(os.path.join(_REPO, ".gitignore"))
    assert "m6_ver2/logs/" in ignore
    assert "m6_ver2/vehicles/" in ignore


def test_the_ledger_carries_a_name_beside_every_pid(source):
    # m6.sh keeps the names in a shell array, which is enough for a
    # script with no `status`. This one has one.
    assert """echo "$$ $2" >> "$1"; shift 2; exec "$@\"""" in source
    assert source.count('while read -r pid name; do') >= 3


def test_the_three_verbs_and_the_two_flags(source):
    for verb in ("start|--start", "status|--status", "stop|--stop"):
        assert verb in source
    assert "--gui)" in source
    assert "--vids)" in source
    # Default headless, the other way round from m6.sh.
    assert re.search(r"(?m)^GUI=false\b", source)


def test_an_unrecognised_word_is_a_refusal_and_not_a_shrug(source):
    tail = source.split('case "${1:-}" in', 1)[1]
    assert tail.count('echo "$USAGE"; exit 2') >= 3


def test_stop_takes_the_trucks_down_before_the_world(source):
    body = re.search(r"(?ms)^stop\(\) \{.*?^\}", source).group(0)
    assert body.index('bash "$TRUCK" "$vid" stop') < body.index("sweep TERM")
    assert body.index("sweep TERM") < body.index("sweep KILL")


def test_stop_reads_the_partition_back_off_a_recorded_pid(source):
    body = re.search(r"(?ms)^stop\(\) \{.*?^\}", source).group(0)
    assert "sed -n 's/^GZ_PARTITION=//p'" in body
    assert "recorded " in body


# ----------------------------------------------------------------------
# and the syntax, where a bash exists to say so
# ----------------------------------------------------------------------
def test_bash_n_is_clean():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash on this machine")
    done = subprocess.run([bash, "-n", _M6V2_SH],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert done.returncode == 0, done.stdout.decode("utf-8", "replace")


# ----------------------------------------------------------------------
# the marker is a scalar and the module path is a path, and the export
# order is what made that matter (live regression, 2026-09-02)
# ----------------------------------------------------------------------
#: The one path in this script that is expanded when a FUNCTION RUNS
#: rather than when the file is read. Every other `$VAR/...` above is
#: resolved in the prelude, before the marker export can reach it, which
#: is exactly why the bug this pins was invisible until a truck was
#: started: `export M6V2=1` overwrote `M6V2="$REPO/m6_ver2"`, and
#: derived_get went looking in `1/vehicles/f1/config.yaml`.
_DERIVED_GET_PATH = re.compile(
    r'print\(node\)\'\s+"\$\{?(\w+)\}?/vehicles/\$1/config\.yaml"')


def test_derived_get_reads_a_path_and_not_the_cell_marker(source):
    found = _DERIVED_GET_PATH.search(fold(source))
    assert found, "derived_get no longer names <var>/vehicles/$1/config.yaml"
    var = found.group(1)
    exported = set(re.findall(r"(?m)^export (\w+)=", source))
    assert var not in exported, (
        "derived_get expands ${} at CALL time and this script exports the "
        "same name as a scalar - the export wins and every derived value "
        "reads as empty".format(var))


#: Source the script, let its usage branch exit, and print the wanted
#: variable from the EXIT trap - the only place a sourced script's
#: state can still be read after it has exited.
_TRAP_READ = (
    """trap 'printf "%s" "${!M6V2_WANT}"' EXIT; """
    '. "$1" >/dev/null 2>&1')


def test_the_module_path_survives_the_marker_export():
    """The prelude, run for real: the path variable still names a
    directory with truck.sh in it AFTER every export has happened."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash on this machine")
    found = _DERIVED_GET_PATH.search(fold(read(_M6V2_SH)))
    assert found, "derived_get no longer names <var>/vehicles/$1/config.yaml"
    # THE REAL FILE IS SOURCED, NOT A COPY: $REPO is computed from
    # BASH_SOURCE, so a copy in a tmp dir would resolve to a tmp answer
    # and the test would pass over the bug it is here for. Sourced with
    # no argument the dispatch falls to its usage branch and exits 2,
    # which is what makes the EXIT trap the place to read from - nothing
    # is started, nothing is swept, and every export has already run.
    env = dict(os.environ, M6V2_WANT=found.group(1))
    done = subprocess.run(
        [bash, "-c",
         _TRAP_READ,
         "_", _M6V2_SH],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    resolved = done.stdout.decode("utf-8", "replace").strip()
    # Git Bash resolves $REPO to a POSIX /c/... path that ntpath cannot
    # see; translate the drive prefix before asking this OS's isdir.
    resolved = re.sub(r"^/([a-zA-Z])/", lambda m: m.group(1) + ":/",
                      resolved)
    assert os.path.isdir(resolved), (
        "derived_get would read under {!r}, which is not a directory"
        .format(resolved))
    assert os.path.isfile(os.path.join(resolved, "truck.sh")), (
        "derived_get's base {!r} is not m6_ver2/".format(resolved))
