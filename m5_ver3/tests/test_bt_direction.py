"""The DirectionStablePath decorator, pinned from four sides - G5 Task 5.

WHAT THIS FILE IS FOR. AMR-DEC-004 ships ONE change: a nav2 behaviour-tree
decorator that refuses to swap the planned driving direction under a
moving truck. That one change is spread over four files that have to
agree - the C++ source, config.yaml, nav2.yaml and the tree XML - and
three of those agreements are a STRING COPIED. This file is where a copy
that has drifted fails on the Windows python, before a rig is booked.

WHAT IT DOES NOT DO, STATED. There is no C++ unit test here and there is
not meant to be one. The logic this node contains - a sign, a comparison
and a threshold - is not what can go wrong; what can go wrong is whether
bt_navigator LOADS it, whether the tree PLACES it where the flip
happens, and whether it changes the outcome on the adverse entry. All
three are measurements on the rig, and EVIDENCE_NAV_V3.md is where they
are written down. This file checks the things a parser can check.

NO ROS AND NO GAZEBO: four files off disk, one YAML parse and some
string searching, exactly as tests/test_nav2_params.py is.
"""
import os
import re

import pytest

yaml = pytest.importorskip("yaml")

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
_REPO = os.path.normpath(os.path.join(_M5V3, os.pardir))


def read(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load(read("config.yaml"))


@pytest.fixture(scope="module")
def nav(cfg):
    return yaml.safe_load(read(cfg["nav"]["params_file"].split("/", 1)[1]))


@pytest.fixture(scope="module")
def tree(cfg):
    return read(cfg["nav"]["bt_xml"].split("/", 1)[1])


@pytest.fixture(scope="module")
def body(tree):
    """The tree with its prose removed. Every claim about STRUCTURE is
    made against this: the header argues at length about Spin, BackUp and
    a RecoveryNode, and a search that read the comments would find every
    node this file is asserting the absence or the position of."""
    return re.sub(r"<!--.*?-->", "", tree, flags=re.DOTALL)


@pytest.fixture(scope="module")
def source(cfg):
    return read(os.path.join(*cfg["bt_direction"]["source_dir"]
                             .split("/")[1:]),
                "src", "direction_stable_path.cpp")


@pytest.fixture(scope="module")
def cmake(cfg):
    return read(os.path.join(*cfg["bt_direction"]["source_dir"]
                             .split("/")[1:]), "CMakeLists.txt")


# ----------------------------------------------------------------------
# the package exists where config.yaml says it does
# ----------------------------------------------------------------------

def test_the_source_tree_config_yaml_names_actually_exists(cfg):
    root = os.path.join(_REPO, cfg["bt_direction"]["source_dir"])
    for part in ("package.xml", "CMakeLists.txt",
                 os.path.join("src", "direction_stable_path.cpp")):
        assert os.path.isfile(os.path.join(root, part)), part


def test_the_package_xml_declares_the_name_config_yaml_uses(cfg):
    package = read(os.path.join(*cfg["bt_direction"]["source_dir"]
                                .split("/")[1:]), "package.xml")
    found = re.search(r"<name>([^<]+)</name>", package)
    assert found and found.group(1) == cfg["bt_direction"]["package"], (
        "colcon selects this package by the name in package.xml and "
        "install_bt_direction.sh passes --packages-select from "
        "config.yaml; a rename in one of them is a build that selects "
        "nothing and reports success")


def test_the_CMAKE_TARGET_is_the_name_nav2_yaml_will_dlopen(cfg, cmake):
    # bt_navigator resolves plugin_lib_names with BT::SharedLibrary,
    # which is `dlopen("lib" + name + ".so")` off the loader path. So the
    # CMake target, config.yaml's key and nav2.yaml's list are three
    # copies of ONE string and this is the first of the two pins.
    assert 'set(PLUGIN_LIB {})'.format(
        cfg["bt_direction"]["library"]) in cmake


def test_BT_PLUGIN_EXPORT_is_defined_because_its_ABSENCE_IS_SILENT(cmake):
    # MEASURED, 2026-09-01, on the first build of this package. Without
    # this definition BT.CPP's BTCPP_EXPORT expands to `static`,
    # BT_REGISTER_NODES compiles to a file-local function, the library
    # builds and links with no warning at all, and the entry point
    # bt_navigator dlsym()s is simply not there. The install script's
    # loader probe is what caught it; this is what stops it coming back.
    assert re.search(
        r"target_compile_definitions\(\s*\$\{PLUGIN_LIB\}\s+PRIVATE\s+"
        r"BT_PLUGIN_EXPORT\s*\)", cmake)


# ----------------------------------------------------------------------
# nav2.yaml loads it, and loads NOTHING ELSE
# ----------------------------------------------------------------------

def test_bt_navigator_is_told_to_load_the_library(cfg, nav):
    names = nav["bt_navigator"]["ros__parameters"]["plugin_lib_names"]
    assert cfg["bt_direction"]["library"] in names


def test_the_list_names_ONLY_ours_and_that_is_a_MEASUREMENT(nav):
    # nav2 1.3.12 loads its own sixty-one BT nodes UNCONDITIONALLY and
    # `plugin_lib_names` is additive on top of them - the parameter's own
    # default is the empty list. Measured 2026-09-01: a bt_navigator
    # started with plugin_lib_names ["nav2_wait_action_bt_node"] - one of
    # nav2's own - refused to configure with
    #   Failed to create navigator id navigate_to_pose.
    #   Exception: ID [Wait] already registered
    # So naming any of nav2's own here is not redundancy, it is a FATAL
    # at configure time.
    names = nav["bt_navigator"]["ros__parameters"]["plugin_lib_names"]
    assert len(names) == 1
    assert not [n for n in names if n.startswith("nav2_")]


# ----------------------------------------------------------------------
# the tree PLACES it where the flip happens
# ----------------------------------------------------------------------

def test_the_decorator_is_in_the_tree_at_all(cfg, body):
    assert "<{}".format(cfg["bt_direction"]["node_id"]) in body


def test_it_wraps_the_ComputePathToPose_RECOVERY_NODE(cfg, body):
    # The recovery structure is not this task's to change: what reaches
    # the decorator has to be whatever the recovery branch finally
    # SUCCEEDED with, so the decorator is OUTSIDE the RecoveryNode and
    # the RecoveryNode is unchanged inside it.
    node = cfg["bt_direction"]["node_id"]
    found = re.search(
        r"<{}[^>]*>\s*<RecoveryNode[^>]*name=\"ComputePathToPose\"".format(node),
        body)
    assert found, (
        "the decorator no longer wraps the ComputePathToPose RecoveryNode")
    assert re.search(r"</RecoveryNode>\s*</{}>".format(node), body)


def test_it_is_INSIDE_the_RateController_and_not_outside_it(cfg, body):
    # Outside it, the decorator would be ticked at bt_loop_duration
    # (10 ms) and would compare a fresh plan against a plan from 10 ms
    # ago - which is not a replan and cannot flip. Inside, it sees
    # exactly one plan per replan, which is the event that flips.
    node = cfg["bt_direction"]["node_id"]
    assert re.search(r'<RateController[^>]*>\s*<{}'.format(node), body)
    assert re.search(r'</{}>\s*</RateController>'.format(node), body)


def test_the_REPLAN_RATE_and_the_RETRY_COUNTS_are_untouched(body):
    # The fix keeps the 1 Hz replan deliberately: removing it (the F1
    # pilot) removed the flips AND the terminal overrun correction with
    # them. Nothing else in this pipeline moved either.
    assert '<RateController hz="1.0">' in body
    assert '<RecoveryNode number_of_retries="1" name="ComputePathToPose">' in body
    assert '<RecoveryNode number_of_retries="6" name="NavigateRecovery">' in body


def test_the_tree_still_has_no_Spin_and_no_BackUp(body):
    # This file adds a node to the tree, so it repeats F4 Task 2's claim
    # about the tree rather than assuming test_nav2_params.py's copy of
    # it still covers a file this task edited.
    for name in ("Spin", "BackUp", "DriveOnHeading", "AssistedTeleop"):
        assert "<{}".format(name) not in body


# ----------------------------------------------------------------------
# the two values the XML has to REPEAT
# ----------------------------------------------------------------------

def attribute(body, node, name):
    found = re.search(r"<{}([^>]*)>".format(node), body)
    assert found, "the tree has no <{}> in it".format(node)
    got = re.search(r'{}="([^"]*)"'.format(name), found.group(1))
    assert got, "<{}> has no {} attribute".format(node, name)
    return got.group(1)


def test_hold_speed_IS_config_yamls_number_and_not_a_second_opinion(
        cfg, body):
    # A BT port takes a literal - it cannot read config.yaml - so the
    # threshold is written twice and this is what keeps the two equal.
    # The number itself is argued in config.yaml: above every measured
    # creep plateau (0.078-0.093 m/s) and below every cusp and stop.
    want = float(cfg["nav"]["direction_hold"]["hold_speed_mps"])
    assert want == 0.05
    assert float(attribute(body, cfg["bt_direction"]["node_id"],
                           "hold_speed")) == want


def test_the_odom_topic_IS_the_FUSED_estimators_address(cfg, body):
    # topics.odometry_filtered and NOT topics.odom_ground_truth, which is
    # F2 global constraint 13, and not the raw wheel odometry either: the
    # speed this node gates on is the one the controller is driving at.
    got = attribute(body, cfg["bt_direction"]["node_id"], "odom_topic")
    assert got == cfg["topics"]["odometry_filtered"]
    assert got != cfg["topics"]["odom_ground_truth"]


def test_the_XML_TAG_is_the_id_the_SOURCE_registers(cfg, source, body):
    # The third copy of the same string: config.yaml names it, the tree
    # writes it as a tag, and BT_REGISTER_NODES is where it becomes real.
    node = cfg["bt_direction"]["node_id"]
    assert 'registerNodeType<m5v3_bt::DirectionStablePath>("{}")'.format(
        node) in source
    assert "<{}".format(node) in body


# ----------------------------------------------------------------------
# the two behaviours in the C++ that cannot be seen from a parameter file
# ----------------------------------------------------------------------

def test_the_source_FAILS_OPEN_when_no_odometry_has_arrived(source):
    # A decorator that held plans on no evidence would be a navigator
    # that cannot start: before the first odometry message there is no
    # reason to believe the truck is moving, so every plan is accepted -
    # and it says so once rather than silently.
    guard = re.search(r"if \(!have_odom_\) \{(.*?)\n    \}", source,
                      re.DOTALL)
    assert guard, "the fail-open odometry guard is gone from the source"
    assert "warned_no_odom_" in guard.group(1)
    # G5-T6: every acceptance goes through accept(), which is also what
    # ends a hold streak - see test_ONE_PLACE_ACCEPTS_and_it_ends_the_streak.
    assert "return accept(fresh)" in guard.group(1)
    # and it is reached BEFORE any hold can be taken
    assert source.index("if (!have_odom_)") < source.index('setOutput("path"')


def test_the_source_RESETS_ITS_HELD_STATE_on_halt(source):
    # haltAllActions() reaches this node at the end of every
    # navigate_to_pose and on every retry of the top-level RecoveryNode.
    # A new goal that inherited a held path would be steered by a plan
    # computed for a goal nobody asked for any more.
    halt = re.search(r"void halt\(\) override\s*\{(.*?)\n  \}", source,
                     re.DOTALL)
    assert halt, "the source no longer overrides halt()"
    assert "have_prev_ = false" in halt.group(1)
    assert "BT::DecoratorNode::halt()" in halt.group(1)
    # G5-T6: and the HOLD STREAK with it. A new goal that inherited a
    # streak clock which had already run would take its first fresh plan
    # on "hold expired" - an expiry that describes the PREVIOUS goal.
    assert "streak_ = false" in halt.group(1)


def test_the_hold_is_only_ever_a_path_the_PLANNER_produced(source):
    # The one line that writes the blackboard, and the only value it can
    # write. A decorator that could synthesise a path would be a second
    # planner with no costmap.
    writes = re.findall(r'setOutput\("path",\s*([A-Za-z_]+)\)', source)
    assert writes == ["prev_"]


def test_child_FAILURE_and_child_RUNNING_pass_through_untouched(source):
    assert ("if (child_state != BT::NodeStatus::SUCCESS) {\n"
            "      return child_state;") in source


def test_the_ACCEPTED_plan_is_read_where_the_truck_STANDS_on_it(source):
    # THE ONE READING THAT COST A PAIR OF SMOKE TRIALS, 2026-09-01. Read
    # at the accepted plan's FIRST segment, this node holds through the
    # TERMINAL CUSP of a plan it had already agreed to - the planner and
    # the accepted plan want the same thing and the decorator refuses
    # both - and two runs that arrive became two START_OCCUPIED aborts.
    # Read at the segment the truck is standing on, a cusp the accepted
    # plan itself contains is not a flip and is not refused.
    #   The truck's position is the FRESH plan's first pose: Smac plans
    # FROM the current pose, so no tf and no second opinion are involved.
    #   G5-T6 gave that pose a NAME because three rungs of the accept
    # ladder now ask about it. It is the same reading.
    assert ("const geometry_msgs::msg::Point & robot = "
            "fresh.poses[0].pose.position;") in source
    assert "current_segment_direction(prev_, robot)" in source
    assert "const int fresh_dir = segment_direction(fresh, 0);" in source
    # and the nearest pose being the LAST one is a consumed plan, which
    # segment_direction() answers 0 for and the caller accepts on
    assert re.search(r"return segment_direction\(path, nearest\);", source)


# ----------------------------------------------------------------------
# G5-T6: the accept ladder, the two modes, and the bounds on the latch
# ----------------------------------------------------------------------

def accepts(source):
    """Every early return that TAKES the fresh plan, in source order.

    The node is written as a ladder of named acceptances followed by one
    hold, rather than as a single boolean: each rung is a reason a reader
    can name and a log line an operator can grep, which is this track's
    rule for a decision made inside a running process."""
    body = source[source.index("BT::NodeStatus tick() override"):]
    return [m.start() for m in re.finditer(r"return accept\(fresh\);", body)]


def test_ONE_PLACE_ACCEPTS_and_it_ends_the_streak(source):
    # accept() is the only place a fresh plan becomes the accepted one,
    # so a plan cannot be taken without the hold streak that was running
    # being ended with it - which is what stops an expiry clock from
    # surviving the acceptance it caused.
    fn = re.search(r"BT::NodeStatus accept\(const nav_msgs::msg::Path & fresh\)"
                   r"\s*\{(.*?)\n  \}", source, re.DOTALL)
    assert fn, "accept() is gone from the source"
    for want in ("prev_ = fresh", "have_prev_ = true", "streak_ = false"):
        assert want in fn.group(1), want
    assert len(re.findall(r"prev_ = fresh", source)) == 1


def test_the_ladder_accepts_on_every_condition_the_task_named(source):
    # no odometry at all / stale odometry / no accepted plan or a changed
    # goal / slow / consumed / not a swap in direction-only mode / hold
    # expired. Seven rungs, and the hold is what is left when none fires.
    assert len(accepts(source)) >= 7, "an accept rung has been removed"


def test_SLOW_ACCEPTS_and_it_is_the_cusp_and_the_stop_and_the_terminus(source):
    # In commit mode this is the only thing that lets a fresh plan in
    # while the accepted plan is still long: a cusp passes through zero
    # speed by construction, so the manoeuvre the accepted plan itself
    # contains is exactly where the next plan is taken.
    assert re.search(
        r"if \(speed_ <= hold_speed_\) \{\s*\n\s*return accept\(fresh\);",
        source)


def test_a_CONSUMED_plan_is_never_held(source):
    # remaining_length() measures from the segment the truck STANDS on,
    # not from the plan's start - the same reading
    # current_segment_direction() makes, and for the same reason.
    assert "static double remaining_length(" in source
    assert "nearest_index(path, robot)" in source
    at = source.find("if (left < consume_floor_m_)")
    assert at > 0, "the consume floor no longer gates the hold"
    assert "consumed" in source[at:at + 600]


def test_hold_all_IS_THE_WHOLE_DIFFERENCE_BETWEEN_THE_TWO_ARMS(source):
    # hold_all=false refuses ONE thing and accepts everything else;
    # hold_all=true refuses every replacement the other rungs let past.
    # A single `if` is the entire mode switch, which is what makes the
    # campaign's A/B a comparison of one variable.
    assert re.search(
        r"if \(!hold_all_ && !swap\) \{\s*\n\s*return accept\(fresh\);",
        source)
    assert len(re.findall(r"hold_all_", source)) >= 3


def test_the_SWAP_is_still_the_same_three_part_test(source):
    swap = re.search(r"const bool swap = \((.*?)\);", source, re.DOTALL)
    assert swap, "the direction-swap test has been rewritten"
    for want in ("fresh_dir != 0", "prev_dir != 0", "fresh_dir != prev_dir"):
        assert want in swap.group(1), want


def test_the_LATCH_IS_BOUNDED_and_the_expiry_is_named_in_the_log(source):
    # Commit mode held for a whole drive would BE the F1 pilot - one
    # plan, no correction, terminal overshoot - so an unbroken streak
    # older than hold_max_s takes the fresh plan and says so.
    assert "const double held = (now - holding_since_).seconds();" in source
    expiry = re.search(r"if \(streak_ && held > hold_max_s_\) \{(.*?)\n    \}",
                       source, re.DOTALL)
    assert expiry, "the hold_max_s bound is gone from the source"
    assert "hold expired" in expiry.group(1), (
        "the expiry has no NAMED log line, so a campaign cannot count it")
    assert "return accept(fresh)" in expiry.group(1)
    assert re.search(r"if \(!streak_\) \{\s*\n?\s*streak_ = true;"
                     r"\s*\n?\s*holding_since_ = now;", source)


def test_a_DEAD_ESTIMATOR_CANNOT_LATCH_THE_HOLD(source):
    # THE HOLE G5-T6 CLOSES BY NAME. speed_ is the last speed the
    # estimator ever published; if it stops publishing while that number
    # is above hold_speed, every condition this node tests stays true for
    # ever and the truck drives a plan nobody is allowed to replace.
    assert "odom_seen_ = node_->now()" in source, (
        "the odometry callback no longer stamps its arrival")
    stale = re.search(r"if \(odom_age > kOdomStaleS\) \{(.*?)\n    \}",
                      source, re.DOTALL)
    assert stale, "the stale-odometry fail-open is gone from the source"
    assert "odom stale" in stale.group(1)
    assert "return accept(fresh)" in stale.group(1)
    assert source.index("if (odom_age > kOdomStaleS)") < source.index(
        'setOutput("path"')
    # one second is FIFTY missed messages on this 50 Hz estimator, so it
    # is a stopped publisher and not a slow one
    assert re.search(r"kOdomStaleS = 1\.0", source)


def test_the_node_SAYS_WHICH_ARM_IT_IS_RUNNING_at_startup(source):
    # The campaign switches arms by an XML attribute. An xml sha says
    # what was on DISK; this says what the running process LOADED, which
    # is the only thing a measured result can be attributed to.
    init = source[source.index("void initialize()"):
                  source.index("BT::NodeStatus tick()")]
    for want in ("hold_all", "hold_max_s", "consume_floor_m"):
        assert 'getInput("{}"'.format(want) in init, want
    assert "RCLCPP_INFO" in init
    assert "COMMIT" in init and "DIRECTION-ONLY" in init


def test_the_three_new_ports_are_DECLARED(source):
    ports = source[source.index("providedPorts()"):source.index("void halt()")]
    assert 'BT::InputPort<bool>(\n        "hold_all"' in ports
    assert 'BT::InputPort<double>(\n        "hold_max_s"' in ports
    assert 'BT::InputPort<double>(\n        "consume_floor_m"' in ports


# ----------------------------------------------------------------------
# G5-T6: the three new values, pinned config.yaml <-> tree XML
# ----------------------------------------------------------------------

def test_hold_all_IS_config_yamls_ARM_and_the_XML_repeats_it(cfg, body):
    # THE ARM SELECTOR. config.yaml owns which mode ships; the tree
    # repeats it because a BT port takes a literal. The campaign switched
    # arms by editing BOTH, and this is what stops a half-switched pair
    # from ever being measured.
    want = cfg["nav"]["direction_hold"]["hold_all"]
    assert want in ("true", "false")
    assert attribute(body, cfg["bt_direction"]["node_id"], "hold_all") == want


def test_hold_max_s_IS_config_yamls_number(cfg, body):
    want = float(cfg["nav"]["direction_hold"]["hold_max_s"])
    assert want > 0.0
    assert float(attribute(body, cfg["bt_direction"]["node_id"],
                           "hold_max_s")) == want


def test_consume_floor_m_IS_config_yamls_number(cfg, body):
    want = float(cfg["nav"]["direction_hold"]["consume_floor_m"])
    assert want > 0.0
    assert float(attribute(body, cfg["bt_direction"]["node_id"],
                           "consume_floor_m")) == want


def test_the_direction_hold_block_has_NOTHING_ELSE_in_it(cfg):
    # Four values and no fifth. A knob that is not measured is a knob
    # nobody can defend, and this task's ruling is that there is no third
    # variant - so the block is closed.
    assert set(cfg["nav"]["direction_hold"]) == {
        "hold_speed_mps", "hold_all", "hold_max_s", "consume_floor_m"}


# ----------------------------------------------------------------------
# the stack can actually find the library
# ----------------------------------------------------------------------

def test_the_installer_exists_and_config_yaml_agrees_with_it(cfg):
    script = read("tools", "install_bt_direction.sh")
    assert "bt_direction.workspace" in script
    assert "--packages-select" in script and "--paths" in script
    # THE BUILD TREE IS THE USER's AND NOT THE REPOSITORY's, which is
    # tools/install_rf2o.sh's ruling: under m5_ver3/ it would be object
    # files one stray `git add` from being committed.
    assert cfg["bt_direction"]["workspace"].startswith("~/")


def test_m5v3_puts_the_library_on_bt_navigators_LOADER_PATH():
    # BT::SharedLibrary is a plain dlopen: no ament index, no pluginlib.
    # So this one child - and no other - is spawned through `env`.
    script = read("m5v3.sh")
    assert "btdir_paths" in script and "btdir_env" in script
    assert 'env "LD_LIBRARY_PATH=$BTDIR_LD_LIBRARY_PATH"' in script
    common = read("tools", "_common.sh")
    assert "BTDIR_SO=" in common and "BTDIR_LD_LIBRARY_PATH=" in common


def test_a_bringup_without_the_library_is_REFUSED_BY_NAME():
    # A plugin_lib_names entry with no file behind it does not degrade:
    # bt_navigator throws out of registerFromPlugin during on_configure
    # and dies, and the lifecycle manager then waits on a server that is
    # gone. Measured 2026-09-01 - "Could not load library:
    # libm5v3_direction_stable_bt_node.so", then a segfault.
    script = read("m5v3.sh")
    assert '[ -f "$BTDIR_SO" ] || refuse' in script
    assert "install_bt_direction.sh" in script
