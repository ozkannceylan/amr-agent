"""The pins on the three rclpy shells - SPEC_ADAPTER.md A-T2/A-T4/A-T9.

NO ROS IS REACHED FROM HERE, AND THAT IS A PROPERTY OF THE SHELLS
RATHER THAN A TRICK OF THIS FILE. Every ROS import in
nav2_adapter_node.py, nav2_seed.py and scan_mask_node.py is INSIDE a
function (m5_ver3/tools/drive_goal.py's idiom), and the adapter TAKES a
node instead of being one - so the whole ordering the shell is
responsible for can be driven with plain python objects, on the owner's
Windows machine, where `import rclpy` fails.

WHAT THAT BUYS. The failures this file catches are the ones a fake can
see and a simulator cannot make happen on demand: a preempted leg's
ABORTED read as a failure, a cancel that did not reach the action
server, a SAFETY-STOP that dropped the route it was supposed to hold, a
namespace that stopped agreeing with status_contract. m6's own suite
draws the line in the same place (`pytest.importorskip("rclpy")` in
test_vda_agent_mqtt.py, nowhere else).

THE DERIVED TREE IS A BUILD PRODUCT and this suite makes it the way an
operator does - by running the tool - rather than skipping when it is
absent. m6_ver2/vehicles/ is gitignored, so a fresh checkout has none of
it and a suite that skipped there would be a suite that passed by
having nothing to say.
"""
import math
import os
import sys
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_M6V2, ".."))
for _sub in (os.path.join(_M6V2, "tools"),):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

import instantiate_truck as itk                            # noqa: E402
import nav2_adapter_node as shell                          # noqa: E402
import nav2_legs                                           # noqa: E402
import nav2_pose                                           # noqa: E402
import nav2_seed                                           # noqa: E402
import nav2_state                                          # noqa: E402
import scan_mask_node                                      # noqa: E402
from status_contract import MODE_AUTO, VEHICLES, contract  # noqa: E402

VID = "f1"


@pytest.fixture(scope="module", autouse=True)
def derived():
    """m6_ver2/vehicles/<vid>/, made if it is not there."""
    for vid in sorted(VEHICLES):
        if not os.path.isfile(os.path.join(itk.OUT_ROOT, vid,
                                           "config.yaml")):
            itk.instantiate(vid)
    return itk.OUT_ROOT


# ----------------------------------------------------------------------
# THE FAKE GRAPH. Nothing below imports ROS; every object is the
# smallest thing the shell actually touches, and `Messages` mirrors the
# real assembler's signatures exactly - including result_of's, because
# reading the wrong field off an action result is one of the failures
# this file exists to catch.
# ----------------------------------------------------------------------
class Vec(object):
    def __init__(self):
        self.x = self.y = self.z = 0.0
        self.w = 1.0


class Twist(object):
    def __init__(self):
        self.linear = Vec()
        self.angular = Vec()


class Immediate(object):
    def __init__(self, value):
        self.value = value

    def add_done_callback(self, callback):
        callback(self)

    def result(self):
        return self.value


class Deferred(object):
    """A future the test fires by hand, which is what an action result is."""

    def __init__(self):
        self.callback = None
        self.value = None

    def add_done_callback(self, callback):
        self.callback = callback

    def result(self):
        return self.value

    def fire(self, value):
        self.value = value
        self.callback(self)


class Handle(object):
    def __init__(self, action, accepted=True):
        self.accepted = accepted
        self.action = action
        self.result_future = Deferred()
        self.cancelled = False

    def get_result_async(self):
        return self.result_future

    def cancel_goal_async(self):
        self.cancelled = True
        self.action.cancels += 1
        return Immediate(None)


class Action(object):
    def __init__(self, name):
        self.name = name
        self.goals = []
        self.handles = []
        self.cancels = 0
        self.accept = True

    def send_goal_async(self, goal):
        self.goals.append(goal)
        handle = Handle(self, accepted=self.accept)
        self.handles.append(handle)
        return Immediate(handle)


class Publisher(object):
    def __init__(self, address):
        self.address = address
        self.sent = []

    def publish(self, message):
        self.sent.append(message)


class Clock(object):
    def __init__(self, holder):
        self.holder = holder

    def now(self):
        seconds = self.holder["t"]
        return types.SimpleNamespace(
            nanoseconds=int(seconds * 1e9),
            to_msg=lambda: types.SimpleNamespace(
                sec=int(seconds), nanosec=0))


class Node(object):
    def __init__(self, holder):
        self.pubs = {}
        self.subs = {}
        self.timers = []
        self._clock = Clock(holder)

    def create_publisher(self, kind, address, qos):
        self.pubs[address] = Publisher(address)
        return self.pubs[address]

    def create_subscription(self, kind, address, callback, qos):
        self.subs[address] = callback
        return object()

    def create_timer(self, period, callback):
        self.timers.append((period, callback))

    def get_clock(self):
        return self._clock

    def get_logger(self):
        return types.SimpleNamespace(info=lambda *a: None,
                                     warn=lambda *a: None)


class Messages(object):
    SUCCEEDED, CANCELED, ABORTED = 4, 5, 6

    def __init__(self):
        self.action = None

    def type_of(self, name):
        return name

    def qos(self, depth, latched):
        return (depth, latched)

    def action_client(self, node, kind, name):
        self.action = Action(name)
        return self.action

    def tf_sample(self, transform):
        return transform.sample

    def string(self, data):
        return types.SimpleNamespace(data=data)

    def twist(self):
        return Twist()

    def odometry(self, rows):
        return rows

    def speed_limit(self, row):
        return row

    def nav_goal(self, frame_id, stamp, map_pose, behavior_tree):
        return {"frame_id": frame_id, "map_pose": map_pose,
                "behavior_tree": behavior_tree}

    def result_of(self, result):
        # The real assembler's line, character for character.
        code = getattr(result.result, "error_code", -1)
        return result.status, code


def status_json(motor=True, v_limit=300):
    return ('{{"estop_healthy": true, "motor": {}, "case": 1, '
            '"v_limit": {}, "ts": 1.0}}').format(
                "true" if motor else "false", v_limit)


class Rig(object):
    """One adapter on a fake graph, with a clock the test steps."""

    def __init__(self):
        self.holder = {"t": 1000.0}
        self.node = Node(self.holder)
        self.msgs = Messages()
        self.cfg = shell.vehicle_config(VID)
        self.adapter = shell.Adapter(
            self.node, self.msgs, self.cfg, VID,
            world_frame="{}/forklift/odom".format(VID),
            clock_s=lambda: self.holder["t"])
        self.adapter.build(shell.wiring(self.cfg, VID))

    # ------------------------------ inputs ------------------------------

    def send(self, address, message):
        self.node.subs[address](message)

    def mode(self, value=MODE_AUTO):
        self.send("hmi/mode", types.SimpleNamespace(data=value))

    def status(self, motor=True, v_limit=300):
        self.send("plc/status", types.SimpleNamespace(data=status_json(
            motor, v_limit)))

    def tf_at(self, x, y, yaw=math.pi):
        """Put the belief at a WORLD pose, through the real registration."""
        map_pose = self.adapter.frame.to_map(x, y, yaw)
        stamp = self.holder["t"]
        rows = [
            types.SimpleNamespace(
                header=types.SimpleNamespace(frame_id="map"),
                child_frame_id="{}/odom".format(VID),
                sample=nav2_pose.TfSample(stamp, 0.0, 0.0, 0.0)),
            types.SimpleNamespace(
                header=types.SimpleNamespace(
                    frame_id="{}/odom".format(VID)),
                child_frame_id="{}/base_link".format(VID),
                sample=nav2_pose.TfSample(stamp, *map_pose)),
        ]
        self.send("tf", types.SimpleNamespace(transforms=rows))

    def smoothed(self, v, w):
        twist = Twist()
        twist.linear.x = v
        twist.angular.z = w
        self.send("cmd_vel_smoothed", twist)

    def route(self, points, label="ORD-1", arrive_m=None):
        payload = {"points": [list(p) for p in points], "label": label}
        if arrive_m is not None:
            payload["arrive_m"] = arrive_m
        import json
        self.send("auto/route", types.SimpleNamespace(
            data=json.dumps(payload)))

    def tick(self, step=1.0 / shell.TICK_HZ):
        self.holder["t"] += step
        self.adapter.tick()

    # ------------------------------ outputs -----------------------------

    @property
    def state(self):
        import json
        sent = self.node.pubs["auto/state"].sent
        return json.loads(sent[-1].data) if sent else None

    @property
    def cmd(self):
        sent = self.node.pubs["auto/cmd_vel"].sent
        return (sent[-1].linear.x, sent[-1].angular.z) if sent else None

    @property
    def action(self):
        return self.msgs.action


#: A released polyline that ends on station S1 - so the split is a
#: TRANSIT leg and then a STATION SPUR, which is the pair the leg runner
#: exists for.
TO_S1 = [(-17.0, 10.0), (-13.0, 10.0), (-13.0, 4.25)]


@pytest.fixture
def rig():
    return Rig()


@pytest.fixture
def driving(rig):
    """A truck in auto, with a pose, a live PLC and a route accepted."""
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.status()
    rig.tick()
    rig.route(TO_S1)
    return rig


# ----------------------------------------------------------------------
# 1. The shells import, and they import WITHOUT ROS.
# ----------------------------------------------------------------------
def test_no_shell_drags_in_rclpy():
    """The property the whole suite stands on, asserted rather than assumed."""
    assert "rclpy" not in sys.modules


def test_own_args_hands_the_ros_block_to_rclpy():
    """argparse must never see `-r __ns:=/f1`; rclpy must always see it."""
    argv = ["--vid", "f1", "--ros-args", "-r", "__ns:=/f1", "-r", "tf:=/tf"]
    assert shell.own_args(argv) == ["--vid", "f1"]
    assert shell.own_args(["--selftest"]) == ["--selftest"]
    # Every shell splits it the same way, because they all get the block.
    assert scan_mask_node.main.__module__ != shell.__name__
    assert nav2_seed.own_args is shell.own_args


@pytest.mark.parametrize("main,argv", [
    (shell.main, ["--selftest"]),
    (nav2_seed.main, ["--vid", VID, "--selftest"]),
    (scan_mask_node.main, ["--selftest"]),
])
def test_every_shell_selftests_without_a_graph(main, argv, capsys):
    assert main(argv) == 0
    assert "problems" in capsys.readouterr().out


# ----------------------------------------------------------------------
# 2. The wiring table IS the namespacing decision.
# ----------------------------------------------------------------------
@pytest.mark.parametrize("vid", sorted(VEHICLES))
def test_the_relative_names_resolve_to_the_fleet_contract(vid, derived):
    """What the adapter asks for, under /<vid>, is what m6 reads.

    A namespace that stopped being applied, or a contract that was
    re-spelled, shows up here as a diff - and nowhere else until a truck
    silently stops answering its orders.
    """
    cfg = shell.vehicle_config(vid)
    rows = dict((row.label, row.address) for row in shell.wiring(cfg, vid)
                if row.kind in ("sub", "pub"))
    names = contract(vid)
    for label, key in (("route", "auto_route_topic"),
                       ("goal", "auto_goal_topic"),
                       ("mode", "mode_topic"),
                       ("status", "status_topic"),
                       ("cmd", "auto_cmd_topic"),
                       ("state", "auto_state_topic")):
        assert not rows[label].startswith("/"), label
        assert "/{}/{}".format(vid, rows[label]) == names[key], label


def test_the_shared_tree_is_reached_relatively():
    """`tf` relative + truck.sh's `-r tf:=/tf`, never `/tf` outright.

    An absolute `/tf` here would work - and it would be the one place in
    the stack that did not obey the rule every other child obeys, so the
    day somebody moved the tree it would be the one that kept working
    and reported nothing.
    """
    cfg = shell.vehicle_config(VID)
    rows = dict((row.label, row.address) for row in shell.wiring(cfg, VID))
    assert rows["tf"] == "tf"
    assert ("tf", "/tf") in shell.NS_REMAPS


def test_the_estimate_and_the_limit_are_where_the_stack_expects_them():
    cfg = shell.vehicle_config(VID)
    rows = dict((row.label, row.address) for row in shell.wiring(cfg, VID))
    assert rows["est"] == "est/odom"
    assert rows["speed_limit"] == cfg.s("topics.speed_limit")
    # THE FIREWALL: ground truth is subscribed by nothing here.
    assert cfg.s("topics.odom_ground_truth") not in rows.values()


def test_every_subscription_has_a_callback():
    cfg = shell.vehicle_config(VID)
    for row in shell.wiring(cfg, VID):
        if row.kind == "sub":
            assert hasattr(shell.Adapter, "cb_" + row.label), row.label


# ----------------------------------------------------------------------
# 3. The boot posture, and the stream that never stops.
# ----------------------------------------------------------------------
def test_boot_is_idle_with_the_localiser_note(rig):
    rig.tick()
    rig.tick()
    assert rig.state["state"] == nav2_state.IDLE
    assert rig.state["note"] == nav2_state.NOTE_LOCALISER_NOT_READY
    assert rig.state["pose"] == [None, None, None]
    assert rig.cmd == (0.0, 0.0)


def test_zeros_flow_rather_than_silence(rig):
    """cmd_gate reads silence as a demand; a zero is a different message."""
    for _ in range(6):
        rig.tick()
    assert len(rig.node.pubs["auto/cmd_vel"].sent) == 6
    assert len(rig.node.pubs["auto/state"].sent) == 3     # 20 Hz / 10 Hz


def test_a_route_is_refused_without_a_pose(rig):
    rig.mode()
    rig.route(TO_S1)
    rig.tick()
    rig.tick()
    assert rig.state["state"] == nav2_state.IDLE
    assert rig.state["note"] == nav2_state.ROUTE_REFUSED_NO_POSE
    assert rig.action.goals == []


def test_an_unreadable_route_is_refused_by_name(rig):
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.tick()
    rig.send("auto/route", types.SimpleNamespace(data="{not json"))
    assert rig.adapter.state.note == nav2_state.ROUTE_REFUSED_UNREADABLE


# ----------------------------------------------------------------------
# 4. The leg runner.
# ----------------------------------------------------------------------
def test_acceptance_sets_en_route_synchronously(driving):
    """vda_agent measures NAV_SETTLE_S from the moment it published.

    A state tick inside that 0.3 s window that still said IDLE is read
    as "nav is not driving this order", and the agent drops `executing`
    on a truck that is about to move.
    """
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert driving.adapter.state.goal == "ORD-1"


def test_the_first_leg_goes_out_with_its_own_tree(driving):
    """Two legs, transit then station spur, and the classes pick trees."""
    legs = driving.adapter.legs
    assert [leg.klass for leg in legs] == [nav2_legs.TRANSIT,
                                           nav2_legs.STATION_SPUR]
    assert len(driving.action.goals) == 1
    goal = driving.action.goals[0]
    assert goal["frame_id"] == driving.cfg.s("frames.map")
    assert goal["behavior_tree"].endswith(
        os.path.basename(driving.cfg.s("nav.bt_xml")))
    # THE GOAL IS IN THE MAP FRAME, and the leg end is in m6's world -
    # so the registration has to have been applied. Round-tripping it is
    # the cheapest check that it was applied the right way round: at
    # -179.813 deg a rotation is very nearly its own inverse.
    back = nav2_pose.to_world(driving.adapter.frame, goal["map_pose"][0],
                              goal["map_pose"][1], goal["map_pose"][2])
    assert back[0] == pytest.approx(-13.0, abs=1e-6)
    assert back[1] == pytest.approx(10.0, abs=1e-6)


def test_the_next_leg_is_sent_at_the_preempt_distance(driving):
    """P = 1.5 m, and it is nav2_legs' number rather than this shell's."""
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M - 0.5, 10.0)
    driving.tick()
    assert len(driving.action.goals) == 1
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    driving.tick()
    assert len(driving.action.goals) == 2
    assert driving.action.goals[1]["behavior_tree"].endswith(
        os.path.basename(driving.cfg.s("nav.bt_xml_rpp")))


def test_a_preempted_legs_abort_is_not_a_failure(driving):
    """THE GENERATION COUNTER, and it is the whole of Decision 2's tail.

    nav2 displaces a running goal itself, so the leg that was preempted
    comes back ABORTED - every single time. Read as a failure it would
    latch BLOCKED on a truck that is driving perfectly, and vda_agent
    would report pathBlocked on a corridor that is clear.
    """
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    driving.tick()
    assert len(driving.action.handles) == 2
    driving.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.ABORTED,
        result=types.SimpleNamespace(error_code=106)))
    assert driving.adapter.state.state == nav2_state.EN_ROUTE


def test_a_live_abort_is_blocked_with_the_named_note(driving):
    driving.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.ABORTED,
        result=types.SimpleNamespace(error_code=205)))
    assert driving.adapter.state.state == nav2_state.BLOCKED
    assert driving.adapter.state.note == (
        "blocked: planner refused (error_code 205)")


def test_a_refused_goal_is_blocked_and_not_silent(rig):
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.status()
    rig.tick()
    rig.msgs.action.accept = False
    rig.route(TO_S1)
    assert rig.adapter.state.state == nav2_state.BLOCKED
    assert "error_code -1" in rig.adapter.state.note


def test_arrival_latches_on_the_estimate(driving):
    driving.tf_at(-13.0, 4.25)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.ARRIVED
    assert driving.action.handles[-1].cancelled
    driving.tick()
    assert driving.state["state"] == nav2_state.ARRIVED
    assert driving.cmd == (0.0, 0.0)


# ----------------------------------------------------------------------
# 5. The doors: cancel, mode, and the PLC.
# ----------------------------------------------------------------------
def test_an_empty_goal_cancels_inside_one_tick(driving):
    """vda_agent's 5 s pump confirms on IDLE + no goal."""
    driving.send("auto/goal", types.SimpleNamespace(data=""))
    driving.tick()
    assert driving.state["state"] == nav2_state.IDLE
    assert driving.state["note"] == nav2_state.NOTE_CANCELLED
    assert driving.state["goal"] is None
    assert driving.action.handles[-1].cancelled
    assert driving.adapter.legs == []


def test_leaving_auto_cancels_by_name(driving):
    driving.mode("teleop")
    driving.tick()
    assert driving.state["state"] == nav2_state.IDLE
    assert driving.state["note"] == nav2_state.NOTE_MODE_LEFT_AUTO
    assert driving.action.handles[-1].cancelled


def test_motor_false_cancels_and_HOLDS_the_route(driving):
    """SAFETY-STOP holds the route; Motor returning re-sends the leg."""
    driving.status(motor=False)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.SAFETY_STOP
    assert driving.adapter.state.route is not None
    assert driving.adapter.state.goal == "ORD-1"
    assert driving.action.handles[-1].cancelled
    assert driving.cmd == (0.0, 0.0)
    sent = len(driving.action.goals)
    driving.status(motor=True)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert len(driving.action.goals) == sent + 1


def test_a_silent_plc_is_a_demand(driving):
    """status_contract.STATUS_STALE_S, the same rule cmd_gate obeys."""
    driving.holder["t"] += 5.0
    driving.tick()
    assert driving.adapter.state.state == nav2_state.SAFETY_STOP


def test_the_speed_limit_is_republished_on_change(rig):
    rig.status(v_limit=300)
    assert rig.node.pubs[rig.cfg.s("topics.speed_limit")].sent == [
        {"speed_limit": 0.3, "percentage": False}]
    rig.status(v_limit=300)
    assert len(rig.node.pubs[rig.cfg.s("topics.speed_limit")].sent) == 1
    rig.status(v_limit=1500)
    assert rig.node.pubs[rig.cfg.s("topics.speed_limit")].sent[-1] == {
        "speed_limit": 1.5, "percentage": False}


# ----------------------------------------------------------------------
# 6. The command translation and the estimate.
# ----------------------------------------------------------------------
def test_a_smoothed_twist_becomes_a_tricycle_command(driving):
    """The sign audit, end to end through the shell.

    Nav2's ordinary reverse leg commands a NEGATIVE linear.x and the
    traction sign passes through unchanged; what changes TYPE is
    angular.z - yaw rate in, STEER ANGLE out - and getting it wrong
    steers at the rack.
    """
    driving.smoothed(-0.30, 0.10)
    driving.tick()
    linear, angular = driving.cmd
    assert linear < 0.0
    expected = nav2_cmd_translate(driving, -0.30, 0.10)
    assert linear == pytest.approx(expected.linear_x)
    assert angular == pytest.approx(expected.angular_z)
    assert driving.state["reversing"] is False


def nav2_cmd_translate(rig, v, w):
    import nav2_cmd
    return nav2_cmd.translate(
        v, w, rig.adapter.limits,
        nav2_cmd.limit_mps_from_v_limit(rig.adapter.v_limit))


def test_a_stale_smoothed_twist_becomes_zeros(driving):
    driving.smoothed(-0.30, 0.0)
    driving.tick()
    assert driving.cmd[0] < 0.0
    driving.holder["t"] += 5.0
    driving.status()                       # keep the PLC alive
    driving.tick()
    assert driving.cmd == (0.0, 0.0)


def test_the_estimate_goes_out_at_20_hz_in_the_world_frame(driving):
    driving.tick()
    rows = driving.node.pubs["est/odom"].sent[-1]
    assert rows["header"]["frame_id"] == "{}/forklift/odom".format(VID)
    assert rows["child_frame_id"] == driving.cfg.s("frames.base_link")
    assert rows["pose"]["position"]["x"] == pytest.approx(-17.0, abs=1e-6)
    assert rows["pose"]["position"]["y"] == pytest.approx(10.0, abs=1e-6)


def test_a_stale_pose_holds_and_says_which_silence_it_is(driving):
    driving.holder["t"] += 5.0
    driving.status()
    driving.tick()
    driving.tick()
    assert driving.state["state"] == nav2_state.HOLD
    assert driving.state["note"] == nav2_state.NOTE_POSE_STALE
    assert driving.state["route"], "the route is HELD, not dropped"


# ----------------------------------------------------------------------
# 7. The seed, without a graph.
# ----------------------------------------------------------------------
@pytest.mark.parametrize("vid", sorted(VEHICLES))
def test_the_seed_is_the_pose_the_world_spawned_the_truck_at(vid, derived):
    cfg = shell.vehicle_config(vid, nav2_seed.TOOL, nav2_seed.REQUIRED_KEYS)
    frame, seed = nav2_seed.seed_in_map(cfg, vid)
    spawn = VEHICLES[vid]["spawn"]
    back = nav2_pose.to_world(frame, seed[0], seed[1], seed[2])
    assert back[0] == pytest.approx(float(spawn["x"]), abs=1e-6)
    assert back[1] == pytest.approx(float(spawn["y"]), abs=1e-6)
    # AND THE DERIVED CONFIG AGREES WITH THE TABLE. The world launch
    # spawns from VEHICLES and the config carries the same quad; a
    # truck seeded at a pose it was not spawned at answers 7.00 m out,
    # which is the spacing of the spawn row.
    assert cfg.s("vehicle.spawn.x") == spawn["x"]
    assert cfg.s("vehicle.spawn.y") == spawn["y"]


def test_four_seeds_are_four_places(derived):
    seeds = set()
    for vid in sorted(VEHICLES):
        cfg = shell.vehicle_config(vid, nav2_seed.TOOL,
                                   nav2_seed.REQUIRED_KEYS)
        seeds.add(nav2_seed.seed_in_map(cfg, vid)[1][:2])
    assert len(seeds) == len(VEHICLES)


@pytest.mark.parametrize("vid", sorted(VEHICLES))
def test_each_truck_seeds_on_its_own_topic(vid, derived):
    cfg = shell.vehicle_config(vid, nav2_seed.TOOL, nav2_seed.REQUIRED_KEYS)
    assert cfg.s("topics.initialpose") == "/{}/initialpose".format(vid)
    assert cfg.s("topics.amcl_pose") == "/{}/amcl_pose".format(vid)
    # THE SEED'S FRAME IS THE SHARED ONE. nav2_amcl ignores a pose in
    # any frame but its own global_frame_id, with one warning line and
    # no other effect - which looks exactly like a seed never sent.
    assert cfg.s("frames.map") == "map"


# ----------------------------------------------------------------------
# 8. The scan mask shell.
# ----------------------------------------------------------------------
def test_the_mask_shell_refuses_a_defaulted_address(capsys):
    with pytest.raises(SystemExit) as raised:
        scan_mask_node.main(["--in-topic", "/f1/gz/scan_nav"])
    assert raised.value.code == 2
    assert "second spelling" in capsys.readouterr().err


def test_the_masked_address_has_exactly_one_home(derived):
    """The mask node's output, the costmaps' file literal, one string."""
    masked = itk.masked_scan_topic(VID)
    body = itk.read_text(os.path.join(itk.OUT_ROOT, VID, "nav2.yaml"))
    assert body.count("topic: " + masked) == 2
    cfg = shell.vehicle_config(VID)
    assert masked != cfg.s("topics.scan_nav")
    # And the adapter's own guard reads the RAW scan, because
    # follower.sector_min applies the contour itself.
    rows = dict((row.label, row.address) for row in shell.wiring(cfg, VID))
    assert rows["scan"] == cfg.s("topics.scan_nav")
