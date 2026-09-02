"""world.launch.py's arithmetic, with no simulator and no ROS.

WHY THIS SUITE CAN EXIST AT ALL. The launch file is a python module whose
whole answer - which trucks, which bridge lines, which model at which
pose, which map_server command line - is computed at IMPORT, before a
single process. So the module can be imported with `launch` and
`launch_ros` STUBBED and every one of those answers read off it directly.
That is a stronger pin than a regex over the source: what is asserted
here is the list the bridge is actually handed.

THE STUBS ARE RECORDERS AND NOT MOCKS. Each stub class keeps the
positional and keyword arguments it was constructed with, and the
LaunchDescription stub keeps the actions in order, so a test can walk the
description the same way `ros2 launch` would and ask what is in it.

WHAT IS DELIBERATELY NOT TESTED HERE: that gz starts, that the bridge
connects, that the map latches. Those are the gate's live assertions
(SPEC_NAMESPACING.md 8) and no amount of import-time reading substitutes
for them.
"""
import importlib.util
import itertools
import os
import sys
import types

import pytest

yaml = pytest.importorskip("yaml")

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, os.pardir))
_REPO = os.path.normpath(os.path.join(_M6V2, os.pardir))
_LAUNCH_FILE = os.path.join(_M6V2, "world.launch.py")

_COUNTER = itertools.count()


# ----------------------------------------------------------------------
# the stubs
# ----------------------------------------------------------------------
class Recorder(object):
    """Every launch action, reduced to the arguments it was given."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    @property
    def name(self):
        return self.kwargs.get("name")


class LaunchDescriptionStub(Recorder):
    def __init__(self, *args, **kwargs):
        Recorder.__init__(self, *args, **kwargs)
        self.actions = []

    def add_action(self, action):
        self.actions.append(action)


class LaunchConfigurationStub(Recorder):
    """`perform(context)` reads the context dict the test hands in."""

    def perform(self, context):
        return context[self.args[0]]


_STUB_CLASSES = {
    "launch": {"LaunchDescription": LaunchDescriptionStub},
    "launch.actions": {"DeclareLaunchArgument": None,
                       "ExecuteProcess": None, "OpaqueFunction": None},
    "launch.conditions": {"IfCondition": None},
    "launch.substitutions": {"LaunchConfiguration": LaunchConfigurationStub},
    "launch_ros": {},
    "launch_ros.actions": {"Node": None},
}


def _install_stubs():
    for modname, members in _STUB_CLASSES.items():
        module = types.ModuleType(modname)
        for attr, cls in members.items():
            setattr(module, attr,
                    cls if cls is not None
                    else type(str(attr), (Recorder,), {}))
        sys.modules[modname] = module
    sys.modules["launch"].actions = sys.modules["launch.actions"]
    sys.modules["launch"].conditions = sys.modules["launch.conditions"]
    sys.modules["launch"].substitutions = sys.modules["launch.substitutions"]
    sys.modules["launch_ros"].actions = sys.modules["launch_ros.actions"]


def load(vids_env=None, argv=None):
    """Import world.launch.py fresh under a chosen environment."""
    _install_stubs()
    old_env = os.environ.get("M6V2_VIDS")
    old_argv = sys.argv
    if vids_env is None:
        os.environ.pop("M6V2_VIDS", None)
    else:
        os.environ["M6V2_VIDS"] = vids_env
    sys.argv = list(argv) if argv is not None else ["ros2"]
    try:
        spec = importlib.util.spec_from_file_location(
            "m6v2_world_{}".format(next(_COUNTER)), _LAUNCH_FILE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.argv = old_argv
        if old_env is None:
            os.environ.pop("M6V2_VIDS", None)
        else:
            os.environ["M6V2_VIDS"] = old_env


@pytest.fixture(scope="module")
def one_truck():
    """f1 alone - the subset G1's gate runs, and the cheap import."""
    return load(vids_env="f1")


@pytest.fixture(scope="module")
def whole_table():
    return load()


def topics_of(args):
    """The ROS topic name each bridge argument opens."""
    return [arg.split("@", 1)[0] for arg in args]


# ----------------------------------------------------------------------
# the bridge: one line per channel
# ----------------------------------------------------------------------
def test_no_channel_is_bridged_twice(whole_table):
    # SPEC_NAMESPACING.md 5's single-writer pin. Per-truck bridges were
    # rejected because they would put a SECOND publisher on
    # /fN/gz/scan_nav, /fN/gz/odom and /clock; a union that duplicated a
    # line would arrive at the same defect through the front door.
    names = topics_of(whole_table._BRIDGE_ARGS)
    assert len(names) == len(set(names)), \
        [n for n in names if names.count(n) > 1]


def test_clock_is_bridged_exactly_once_and_first(whole_table):
    args = whole_table._BRIDGE_ARGS
    clocks = [a for a in args if a.startswith("/clock@")]
    assert len(clocks) == 1, clocks
    assert args[0] == clocks[0]
    assert clocks[0] == "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"


def test_two_clocks_in_the_configs_is_a_refusal(one_truck):
    m6 = {"f1": dict(one_truck._M6_TOPICS["f1"])}
    m6v2 = {"f1": dict(one_truck._M6V2_TOPICS["f1"])}
    m6v2["f1"]["clock"] = "/f1/clock"
    with pytest.raises(RuntimeError) as caught:
        one_truck.bridge_args(("f1",), m6, m6v2, one_truck._SCAN_FMTS)
    assert "one world, one clock" in str(caught.value)


def test_no_image_is_bridged(whole_table):
    # Not the pallet camera (dark with docking), not m6's overhead eye.
    # A bridged Image with no consumer is a claim this run does not make,
    # and RTF at four Nav2 stacks is the open question the gate has to
    # MEASURE rather than spend in advance.
    for arg in whole_table._BRIDGE_ARGS:
        assert "Image" not in arg, arg
        assert "CameraInfo" not in arg, arg
        assert "/cam" not in arg, arg
        assert "overhead" not in arg, arg


def test_ground_truth_odom_is_bridged_for_every_truck(whole_table):
    for vid in whole_table._VIDS:
        line = "/{}/gz/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry".format(vid)
        assert line in whole_table._BRIDGE_ARGS


def test_the_ground_truth_line_is_marked_as_evidence_only():
    # SPEC_ADAPTER.md Decision 4's firewall is a rule no static check can
    # enforce from here - it is about who SUBSCRIBES. What this file owes
    # the next reader is the reason the wire is open at all, written
    # beside the line that opens it.
    #   AND THE LINE IS BUILT FROM THE m5v3 KEY NOW. m6's `gz_odom` was
    # re-pointed at the adapter's estimate by
    # m6_ver2/tools/fleet_odom_firewall.py, so bridging it would open a
    # gz channel for a topic the ADAPTER publishes.
    with open(_LAUNCH_FILE, "r", encoding="utf-8") as handle:
        body = handle.read()
    head, sep, _ = body.partition('add(right["odom_ground_truth"]')
    assert sep, "the ground-truth bridge line moved"
    tail = head[-1200:]
    assert "EVIDENCE ONLY" in tail.upper()
    assert "Decision 4" in tail
    assert "score_run.py" in tail
    assert 'add(left["gz_odom"]' not in body


# ----------------------------------------------------------------------
# the ground-truth firewall - SPEC_ADAPTER.md Decision 4
# ----------------------------------------------------------------------

def test_the_fleet_key_reads_the_estimate_and_the_bridge_reads_the_truth(
        whole_table):
    """THE TWO HALVES, AND THEY MUST NOT BE THE SAME TOPIC.

    vda_agent.py and hmi_node.py subscribe m6's `topics.gz_odom`; the
    firewall points it at the adapter's estimate so route progress is
    counted on the pose the vehicle can actually see. The truth is still
    bridged for scoring, under the m5v3 family's own name.
    """
    import fleet_odom_firewall as firewall
    for vid in whole_table._VIDS:
        est = firewall.est_odom_topic(vid)
        truth = firewall.truth_odom_topic(vid)
        assert est != truth
        assert whole_table._M6_TOPICS[vid]["gz_odom"] == est
        assert whole_table._M6V2_TOPICS[vid]["odom_ground_truth"] == truth
        # the truth is on the wire, the estimate is NOT bridged from gz:
        # the adapter is its only publisher.
        assert truth in topics_of(whole_table._BRIDGE_ARGS)
        assert est not in topics_of(whole_table._BRIDGE_ARGS)


def test_an_unfirewalled_fleet_config_refuses_the_world(one_truck):
    """The failure this check exists for is SILENT.

    An m6 derivation re-run without the firewall - one `python3
    m6/tools/instantiate_vehicle.py --all` - puts the ground truth back
    under the key the fleet reads. Nothing errors: the world comes up,
    the trucks drive, and route progress is counted with an instrument
    no real truck has.
    """
    import fleet_odom_firewall as firewall
    m6 = {"f1": dict(one_truck._M6_TOPICS["f1"])}
    m6v2 = {"f1": dict(one_truck._M6V2_TOPICS["f1"])}
    m6["f1"]["gz_odom"] = firewall.truth_odom_topic("f1")
    with pytest.raises(RuntimeError) as caught:
        one_truck.agree(("f1",), m6, m6v2, one_truck._SCAN_FMTS)
    assert "ESTIMATE" in str(caught.value)
    assert "fleet_odom_firewall" in str(caught.value)


def test_a_truth_key_that_moved_on_the_m5v3_side_refuses_the_world(one_truck):
    """The bridge takes the truth from THAT key now, so it is checked."""
    m6 = {"f1": dict(one_truck._M6_TOPICS["f1"])}
    m6v2 = {"f1": dict(one_truck._M6V2_TOPICS["f1"])}
    m6v2["f1"]["odom_ground_truth"] = "/f1/est/odom"
    with pytest.raises(RuntimeError) as caught:
        one_truck.agree(("f1",), m6, m6v2, one_truck._SCAN_FMTS)
    assert "ground truth keeps its name" in str(caught.value)


def test_the_odom_pair_is_no_longer_a_shared_wire(one_truck):
    """SHARED_WIRES is "names the two families spell the same way", and
    after the firewall the odom pair is deliberately not one of them."""
    keys = [pair[0] for pair in one_truck.SHARED_WIRES]
    assert "gz_odom" not in keys
    assert [pair[1] for pair in one_truck.SHARED_WIRES].count(
        "odom_ground_truth") == 0


def test_the_ground_truth_tf_topic_is_never_bridged(whole_table):
    # The OdometryPublisher's <tf_topic> carries the ground-truth frames.
    # Bridged, they would join /tf beside the EKF's estimate of the same
    # edge - two authorities on fN/odom -> fN/base_link, and tf2 would
    # carry whichever arrived last.
    for arg in whole_table._BRIDGE_ARGS:
        assert "tf_ground_truth" not in arg, arg


def test_the_two_new_lines_are_exactly_imu_and_joint_state(whole_table):
    # The m6 per-vehicle set, spelled from m6's own launch file, plus
    # exactly two: SPEC_NAMESPACING.md 4 says "the union adds exactly two
    # gz->ROS lines per truck", and a third would be a channel nobody
    # decided to open.
    for vid in whole_table._VIDS:
        m6_set = {
            "/{}/gz/actuator/steer_cmd".format(vid),
            "/{}/gz/actuator/traction_cmd".format(vid),
            "/{}/gz/odom".format(vid),
            "/{}/gz/scan_nav".format(vid),
            "/{}/gz/drive_speed/read_a".format(vid),
            "/{}/gz/drive_speed/read_b".format(vid),
            "/{}/gz/safety_scanner_back/measurement".format(vid),
            "/{}/gz/safety_scanner_left/measurement".format(vid),
            "/{}/gz/safety_scanner_right/measurement".format(vid),
        }
        mine = {t for t in topics_of(whole_table._BRIDGE_ARGS)
                if t.startswith("/{}/".format(vid))}
        assert mine - m6_set == {"/{}/gz/imu".format(vid),
                                 "/{}/gz/joint_state".format(vid)}
        assert m6_set - mine == set()


def test_the_terminals_are_the_only_ros_to_gz_lines(whole_table):
    # ']' is ROS -> gz. sto_contactor.py is the only publisher of these
    # two, which is what puts the contactor INSIDE the command path.
    to_gz = [a for a in whole_table._BRIDGE_ARGS if "]" in a]
    assert sorted(topics_of(to_gz)) == sorted(
        "/{}/gz/actuator/{}_cmd".format(vid, which)
        for vid in whole_table._VIDS for which in ("steer", "traction"))


def test_the_fork_terminal_stays_dark(whole_table):
    # As in m6: sto_contactor publishes it, nothing in gz listens, and it
    # wakes with docking.
    for arg in whole_table._BRIDGE_ARGS:
        assert "fork_cmd" not in arg, arg


# ----------------------------------------------------------------------
# the truck subset
# ----------------------------------------------------------------------
def test_the_default_is_the_whole_table(whole_table):
    import status_contract
    assert whole_table._VIDS == tuple(sorted(status_contract.VEHICLES))


def test_a_subset_reaches_the_bridge_the_spawns_and_the_gui_gate(one_truck):
    assert one_truck._VIDS == ("f1",)
    for name in topics_of(one_truck._BRIDGE_ARGS):
        assert name == "/clock" or name.startswith("/f1/"), name
    assert one_truck._GUI_GATE_TOPICS == (
        "/f1/gz/safety_scanner_back/measurement",)


def test_the_subset_can_be_named_on_the_command_line():
    module = load(argv=["ros2", "launch", "x", 'vids:=f1 f2'])
    assert module._VIDS == ("f1", "f2")


def test_env_and_command_line_disagreeing_is_a_refusal():
    with pytest.raises(RuntimeError) as caught:
        load(vids_env="f1", argv=["ros2", "vids:=f2"])
    assert "M6V2_VIDS and vids:= name the same trucks" in str(caught.value)


def test_env_and_command_line_agreeing_is_fine():
    module = load(vids_env="f1 f2", argv=["ros2", "vids:=f1  f2"])
    assert module._VIDS == ("f1", "f2")


@pytest.mark.parametrize("bad,fragment", [
    ("", "names at least one truck"),
    ("f9", "in the VEHICLES table"),
    ("f1 f1", "no truck is named twice"),
])
def test_the_subset_refuses_by_name(one_truck, bad, fragment):
    with pytest.raises(RuntimeError) as caught:
        one_truck.resolve_vids(bad, [])
    assert fragment in str(caught.value)


# ----------------------------------------------------------------------
# the two config families, reconciled
# ----------------------------------------------------------------------
def test_a_disagreeing_wire_is_a_refusal(one_truck):
    m6 = {"f1": dict(one_truck._M6_TOPICS["f1"])}
    m6v2 = {"f1": dict(one_truck._M6V2_TOPICS["f1"])}
    m6["f1"]["gz_scan_nav"] = "/f1/gz/scan_nav_renamed"
    with pytest.raises(RuntimeError) as caught:
        one_truck.agree(("f1",), m6, m6v2, one_truck._SCAN_FMTS)
    text = str(caught.value)
    assert "the two derived configs spell one wire one way" in text
    assert "gz_scan_nav" in text and "scan_nav" in text


def test_a_renamed_back_scanner_is_a_refusal(one_truck):
    m6v2 = {"f1": dict(one_truck._M6V2_TOPICS["f1"])}
    m6v2["f1"]["safety_scan_back"] = "/f1/gz/back"
    with pytest.raises(RuntimeError) as caught:
        one_truck.agree(("f1",), one_truck._M6_TOPICS, m6v2,
                        one_truck._SCAN_FMTS)
    assert "the back scanner has one name" in str(caught.value)


def test_the_shared_wires_are_the_whole_overlap(one_truck):
    # Every key named in SHARED_WIRES must exist on both sides, or the
    # check would be comparing None to None and passing.
    left, right = one_truck._M6_TOPICS["f1"], one_truck._M6V2_TOPICS["f1"]
    for m6_key, m5v3_key in one_truck.SHARED_WIRES:
        assert m6_key in left, m6_key
        assert m5v3_key in right, m5v3_key


# ----------------------------------------------------------------------
# the shared map server
# ----------------------------------------------------------------------
def test_the_map_server_runs_off_the_donor_amcl_yaml(one_truck):
    cmd = one_truck.map_server_cmd()
    params = cmd[cmd.index("--params-file") + 1]
    assert os.path.normpath(params) == os.path.normpath(
        os.path.join(_REPO, "m5_ver3", "amcl.yaml"))
    assert os.path.isfile(params)
    # The DERIVED amcl.yaml is wrapped under <vid>: and its map_server
    # block is dead by design. Using one here would configure nobody.
    assert "vehicles" not in params


def test_the_map_server_is_un_namespaced_and_carries_the_three_addresses(
        one_truck):
    cmd = one_truck.map_server_cmd()
    assert cmd[:2] == ["nav2_map_server", "map_server"]
    assert "__node:=map_server" in cmd
    overrides = dict(
        arg.split(":=", 1) for arg in cmd if ":=" in arg and "__" not in arg)
    assert overrides["use_sim_time"] == "true"
    assert overrides["topic_name"] == "/map"
    assert overrides["frame_id"] == "map"
    assert overrides["yaml_filename"].endswith("warehouse_v3.yaml")
    assert os.path.isfile(overrides["yaml_filename"])


def test_the_map_server_lifecycle_is_state_targeted_and_refuses_by_name(
        one_truck):
    script = one_truck.map_server_lifecycle_script()
    # A request to CONFIGURE is a claim about the current state; a request
    # to BE ACTIVE is not. m5v3.sh's ruling, ported whole.
    assert 'until [ "$state" = active ]' in script
    assert "unconfigured)" in script and "inactive)" in script
    assert "REFUSED at check" in script
    assert "THE CELL IS INCOMPLETE" in script


# ----------------------------------------------------------------------
# the description itself
# ----------------------------------------------------------------------
def description(module):
    return module.generate_launch_description()


def actions_named(module, prefix):
    return [a for a in description(module).actions
            if str(a.kwargs.get("name", "")).startswith(prefix)]


def test_every_truck_gets_one_spawn_of_its_own_derived_model(whole_table):
    import status_contract
    spawns = actions_named(whole_table, "spawn_forklift_")
    assert len(spawns) == len(whole_table._VIDS)
    for vid, action in zip(whole_table._VIDS, spawns):
        args = action.kwargs["arguments"]
        assert args[args.index("-name") + 1] == "forklift_{}".format(vid)
        model = args[args.index("-file") + 1]
        assert os.path.normpath(model) == os.path.normpath(
            os.path.join(_M6V2, "vehicles", vid, "model.sdf"))
        spawn = status_contract.contract(vid)["spawn"]
        assert args[args.index("-x") + 1] == spawn["x"]
        assert args[args.index("-y") + 1] == spawn["y"]
        assert args[args.index("-z") + 1] == spawn["z"]
        assert args[args.index("-Y") + 1] == spawn["yaw"]
        assert args[args.index("-allow_renaming") + 1] == "false"


def test_the_donor_model_is_never_spawned(whole_table):
    for action in actions_named(whole_table, "spawn_forklift_"):
        model = action.kwargs["arguments"][
            action.kwargs["arguments"].index("-file") + 1]
        assert "m5_ver3" not in model.replace(os.sep, "/")


def test_the_world_is_m6s_by_reference(whole_table):
    assert os.path.normpath(whole_table._WORLD) == os.path.normpath(
        os.path.join(_REPO, "m6", "gazebo", "warehouse_ver3.sdf"))
    assert os.path.isfile(whole_table._WORLD)
    # No copy of the floor under m6_ver2/: warehouse_v3's map and its
    # registration were both fitted against m6's file.
    assert not os.path.isdir(os.path.join(_M6V2, "gazebo"))


def test_the_two_fleet_nodes_get_m6s_config_and_not_m5v3s(whole_table):
    for vid in whole_table._VIDS:
        for prefix in ("sto_contactor_", "forklift_io_"):
            action, = actions_named(whole_table, prefix + vid)
            cmd = action.kwargs["cmd"]
            config = cmd[cmd.index("--config") + 1]
            assert os.path.normpath(config) == os.path.normpath(
                os.path.join(_REPO, "m6", "vehicles", vid, "config.yaml"))


def test_the_contactor_carries_sim_time_and_forklift_io_does_not(one_truck):
    sto, = actions_named(one_truck, "sto_contactor_f1")
    io, = actions_named(one_truck, "forklift_io_f1")
    assert "use_sim_time:=true" in sto.kwargs["cmd"]
    assert "use_sim_time:=true" not in io.kwargs["cmd"]
    assert "__node:=sto_contactor_f1" in sto.kwargs["cmd"]
    assert "__node:=forklift_io_f1" in io.kwargs["cmd"]


def test_exactly_one_bridge_and_one_map_server(whole_table):
    ld = description(whole_table)
    assert len([a for a in ld.actions
                if a.kwargs.get("name") == "m6v2_bridge"]) == 1
    assert len([a for a in ld.actions
                if a.kwargs.get("name") == "map_server"]) == 1
    assert len([a for a in ld.actions
                if a.kwargs.get("name") == "map_server_lifecycle"]) == 1


def programs(module):
    """What each action RUNS, as opposed to what it is handed.

    A path on a command line is an argument - m5_ver3/amcl.yaml is the
    map_server's params file and not an amcl - so the check below reads
    the program position and never the whole line.
    """
    found = set()
    actions = list(description(module).actions)
    # An OpaqueFunction has no command line until it is performed - the
    # gz server is built in one so --headless-rendering can be ABSENT
    # rather than false - so it is performed here, headless.
    for action in list(actions):
        if "function" in action.kwargs:
            actions.extend(action.kwargs["function"]({"gui": "false"}))
    for action in actions:
        if "function" in action.kwargs:
            continue
        if "package" in action.kwargs:
            found.add("{}/{}".format(action.kwargs["package"],
                                     action.kwargs["executable"]))
            continue
        cmd = [str(x) for x in action.kwargs.get("cmd", [])]
        if not cmd:
            continue
        head = os.path.basename(cmd[0])
        if head.startswith("python") and len(cmd) > 1:
            found.add(os.path.basename(cmd[1]))
        elif head == "ros2" and cmd[1:2] == ["run"]:
            found.add("{}/{}".format(cmd[2], cmd[3]))
        else:
            found.add(head)
    return found


def test_the_plant_is_exactly_these_programs(whole_table):
    # The whole point of the file, as a list. Everything shared is here
    # and nothing per-truck is: an AMCL started from this launch would be
    # a second owner of map -> fN/odom, and a Nav2 server would be a
    # second publisher of a truck's cmd_vel. That half is truck.sh's.
    assert programs(whole_table) == {
        "gz",                            # the world server
        "bash",                          # the GUI gate, the lifecycle drive
        "ros_gz_bridge/parameter_bridge",
        "ros_gz_sim/create",
        "nav2_map_server/map_server",
        "sto_contactor.py",
        "forklift_io.py",
    }


def test_the_gui_gate_waits_for_every_spawned_trucks_back_scanner(
        whole_table):
    gui, = [a for a in description(whole_table).actions
            if a.kwargs.get("name") == "gz_gui"]
    line = gui.kwargs["cmd"][-1]
    for vid in whole_table._VIDS:
        assert "/{}/gz/safety_scanner_back/measurement".format(vid) in line
    assert line.count("gz topic -l") == len(whole_table._VIDS)


def test_the_server_is_headless_unless_the_gui_is_asked_for(one_truck):
    headless = one_truck._gz_server({"gui": "false"})[0].kwargs["cmd"]
    windowed = one_truck._gz_server({"gui": "true"})[0].kwargs["cmd"]
    assert headless[:4] == ["gz", "sim", "-s", "-r"]
    assert "--headless-rendering" in headless
    # ABSENT, not present-and-false: the flag has no false value.
    assert "--headless-rendering" not in windowed
    assert headless[-1] == one_truck._WORLD == windowed[-1]


# ----------------------------------------------------------------------
# the staleness refusal
# ----------------------------------------------------------------------
def test_a_stale_derivation_refuses_at_import_and_names_the_tool():
    """The refusal SPEC_NAMESPACING.md 3.5 exists for, exercised.

    A byte is appended to a derived file and put back in a `finally`.
    The tree is a gitignored build product and
    `instantiate_truck.py --all` remakes it, so the blast radius of a
    crash here is one command.
    """
    target = os.path.join(_M6V2, "vehicles", "f4", "config.yaml")
    if not os.path.isfile(target):
        pytest.skip("f4 has not been derived")
    with open(target, "rb") as handle:
        original = handle.read()
    try:
        with open(target, "wb") as handle:
            handle.write(original + b"\n# drift\n")
        with pytest.raises(RuntimeError) as caught:
            load(vids_env="f4")
        text = str(caught.value)
        assert "the derivation on disk is the one the tool writes" in text
        assert "instantiate_truck.py --all" in text
        assert "config.yaml" in text
    finally:
        with open(target, "wb") as handle:
            handle.write(original)
    # and clean again it imports
    assert load(vids_env="f4")._VIDS == ("f4",)
