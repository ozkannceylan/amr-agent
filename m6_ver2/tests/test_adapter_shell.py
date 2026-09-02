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

import follower                                            # noqa: E402
import instantiate_truck as itk                            # noqa: E402
import nav2_adapter_node as shell                          # noqa: E402
import nav2_envelope                                       # noqa: E402
import nav2_legs                                           # noqa: E402
import nav2_pose                                           # noqa: E402
import nav2_seed                                           # noqa: E402
import nav2_state                                          # noqa: E402
import scan_mask_node                                      # noqa: E402
from stations import STATIONS                              # noqa: E402
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
    """geometry_msgs' float fields, AS STRICT AS THE REAL ONES.

    A permissive fake is an inaccurate fake, and this is the exact spot
    where that cost a live gate. rosidl's generated converter runs
    `assert PyFloat_Check(field)` in C: an int, a None or a numpy scalar
    does not raise a Python exception, it ABORTS THE PROCESS -
    `geometry_msgs__msg__vector3__convert_from_py: Assertion
    'PyFloat_Check(field)' failed` - so a shell that assigned None here
    was killed by its own first command while 366 green tests said the
    wiring was fine (measured 2026-09-02, first live bringup).

    Refusing it here rather than in one test is deliberate: the check
    then rides EVERY test that publishes a command, which is where a
    regression of this class would actually appear.
    """

    __slots__ = ("x", "y", "z", "w")

    def __init__(self):
        object.__setattr__(self, "x", 0.0)
        object.__setattr__(self, "y", 0.0)
        object.__setattr__(self, "z", 0.0)
        object.__setattr__(self, "w", 1.0)

    def __setattr__(self, name, value):
        # bool is an int and an int is not a float, exactly as
        # PyFloat_Check reads it.
        if type(value) is not float:
            raise TypeError(
                "rosidl would ABORT here: geometry_msgs float field {!r} "
                "was given {!r} ({}), and PyFloat_Check accepts a float "
                "and nothing else".format(name, value,
                                          type(value).__name__))
        object.__setattr__(self, name, value)


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

#: TWO TRANSIT LEGS, split at a junction turn and ending nowhere in
#: particular. It is the OTHER shape, and it has to be a second route
#: rather than a second reading of the first: TO_S1 ends in a BAY, so
#: its leg switch changes the behaviour tree and nav2 refuses to preempt
#: across it (see _advance_to). True preemption - the thing
#: PREEMPT_AT_M was measured for - only ever happens between legs that
#: SHARE A TREE, and since SPEC_ADAPTER.md AMENDMENTS 4 that is every
#: pair except the last one into a bay.
TWO_TRANSITS = [(-17.0, 10.0), (-13.0, 10.0), (-13.0, -10.0)]


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


@pytest.fixture
def transiting(rig):
    """The same truck on TWO_TRANSITS - one class, so one tree."""
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.status()
    rig.tick()
    rig.route(TWO_TRANSITS)
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
    """Two legs, transit then station spur, and the classes pick trees.

    The transit leg's tree is the RPP one since AMENDMENTS 4; the bay's
    is the RPP tree with the 0.25 m checker named. Two different files,
    which is what makes the boundary below a cancel and not a preempt.
    """
    legs = driving.adapter.legs
    assert [leg.klass for leg in legs] == [nav2_legs.TRANSIT,
                                           nav2_legs.STATION_SPUR]
    assert len(driving.action.goals) == 1
    goal = driving.action.goals[0]
    assert goal["frame_id"] == driving.cfg.s("frames.map")
    assert goal["behavior_tree"].endswith(
        os.path.basename(driving.cfg.s("nav.bt_xml_rpp")))
    # THE GOAL IS IN THE MAP FRAME, and the leg end is in m6's world -
    # so the registration has to have been applied. Round-tripping it is
    # the cheapest check that it was applied the right way round: at
    # -179.813 deg a rotation is very nearly its own inverse.
    back = nav2_pose.to_world(driving.adapter.frame, goal["map_pose"][0],
                              goal["map_pose"][1], goal["map_pose"][2])
    assert back[0] == pytest.approx(-13.0, abs=1e-6)
    assert back[1] == pytest.approx(10.0, abs=1e-6)


def test_the_next_leg_is_decided_at_the_preempt_distance(driving):
    """P = 1.5 m, and it is nav2_legs' number rather than this shell's."""
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M - 0.5, 10.0)
    driving.tick()
    assert len(driving.action.goals) == 1
    assert driving.adapter.pending_leg is None
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    driving.tick()
    # THE DECISION IS TAKEN AT P. What it does with it depends on
    # whether the tree changes, which for TO_S1 it does - see the test
    # below for why nav2 will not take that as a preemption.
    assert driving.adapter.pending_leg == 1


def test_a_tree_change_is_a_cancel_and_then_a_send(driving):
    """nav2 REFUSES a preemption that changes the behaviour tree.

    MEASURED LIVE, 2026-09-02, and quoted from bt_navigator's own log:
    "Preemption request was rejected since the requested BT XML file is
    not the same as the one that the current goal is executing ...
    Cancel the current goal and send a new action request if you want to
    use a different BT XML file. For now, continuing to track the last
    goal until completion." The rejected goal comes back ABORTED with an
    EMPTY result - error_code 0 - so the adapter read it as a nav2
    failure and latched BLOCKED 1.49 m short of the spur foot, which is
    where EVERY route ends. The order died there.

    So the transition is nav2's own: cancel, and send when the server
    says the old goal is off it - never on a timer.
    """
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    driving.tick()
    # 1. cancelled, and NOTHING new sent yet.
    assert driving.action.cancels == 1
    assert driving.action.handles[0].cancelled is True
    assert len(driving.action.goals) == 1
    assert driving.adapter.pending_leg == 1
    # 2. more ticks change nothing: a leg already waiting is not
    #    cancelled a second time.
    driving.tick()
    driving.tick()
    assert driving.action.cancels == 1
    assert len(driving.action.goals) == 1
    # 3. the server reports the old goal finished, and only then.
    driving.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.CANCELED,
        result=types.SimpleNamespace(error_code=0)))
    assert len(driving.action.goals) == 2
    assert driving.adapter.pending_leg is None
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    # THE STATION TREE, because leg 2 is the spur into the bay:
    # nav2_legs.CLASS_TREE names the key and this shell only looks it
    # up in the config.
    assert driving.action.goals[1]["behavior_tree"].endswith(
        os.path.basename(driving.cfg.s("nav.bt_xml_station")))


def test_the_rejected_preemptions_own_abort_is_not_a_failure(driving):
    """The same switch, when nav2 answers the cancel with ABORTED.

    A cancelled NavigateToPose does not always come back CANCELED - a
    BT that was already failing terminates ABORTED with whatever code it
    had. Either way the goal is OFF the server, which is the only fact
    the pending leg is waiting for.
    """
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    driving.tick()
    driving.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.ABORTED,
        result=types.SimpleNamespace(error_code=0)))
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert len(driving.action.goals) == 2


def test_true_preemption_still_runs_between_legs_of_one_class(transiting):
    """P = 1.5 m with NO cancel in it, which is what it was measured for.

    Two transit legs share nav.bt_xml_rpp, so bt_navigator takes the
    second goal as a real preemption and displaces the first itself -
    the truck never stops, and `executing` never flickers.
    """
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M - 0.5, 10.0)
    transiting.tick()
    assert len(transiting.action.goals) == 1
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    transiting.tick()
    assert len(transiting.action.goals) == 2
    assert transiting.action.cancels == 0
    assert transiting.adapter.pending_leg is None
    assert transiting.action.goals[1]["behavior_tree"].endswith(
        os.path.basename(transiting.cfg.s("nav.bt_xml_rpp")))


def test_a_cancel_takes_the_waiting_leg_with_it(driving):
    """A pending leg that outlived the route would be a goal nobody
    asked for, sent after the door that asked for it had closed."""
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    driving.tick()
    assert driving.adapter.pending_leg == 1
    driving.send("auto/goal", types.SimpleNamespace(data=""))
    assert driving.adapter.pending_leg is None
    driving.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.CANCELED,
        result=types.SimpleNamespace(error_code=0)))
    assert len(driving.action.goals) == 1
    assert driving.adapter.state.state == nav2_state.IDLE


def test_a_preempted_legs_abort_is_not_a_failure(transiting):
    """THE GENERATION COUNTER, and it is the whole of Decision 2's tail.

    nav2 displaces a running goal itself, so the leg that was preempted
    comes back ABORTED - every single time. Read as a failure it would
    latch BLOCKED on a truck that is driving perfectly, and vda_agent
    would report pathBlocked on a corridor that is clear.
    """
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    transiting.tick()
    assert len(transiting.action.handles) == 2
    transiting.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.ABORTED,
        result=types.SimpleNamespace(error_code=106)))
    assert transiting.adapter.state.state == nav2_state.EN_ROUTE


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
        "speed_limit": 0.3, "percentage": False}


def _on_the_station_spur(driving):
    """Drive the fixture route to its FINAL leg and hand back the handle.

    The station spur is the only leg allowed to run to completion, so it
    is the only one whose SUCCEEDED reaches the arrival verdict at all.
    """
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    driving.tick()
    driving.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.CANCELED, result=types.SimpleNamespace(error_code=0)))
    assert driving.adapter.legs[driving.adapter.leg_i].final
    return driving.action.handles[1]


def test_a_boundary_arrival_is_an_arrival_and_not_a_block(driving):
    """D6, run4 - nav2 SUCCEEDED half a millimetre outside arrive_m.

    The adapter's `arrive_m` and nav2's `station_goal_checker` are the
    same 0.25 m read off two beliefs sampled at two instants: nav2
    checks AMCL's map pose, the adapter checks the composed estimate
    through the committed registration. Three arrivals at S1 in one run
    measured 0.2453, 0.2482 and 0.2502 m, and the third one BLOCKED the
    task and put it back on the fleet's queue.
    """
    handle = _on_the_station_spur(driving)
    driving.tf_at(-13.0, 4.25 + 0.2502)
    driving.tick()
    assert driving.adapter.state.state != nav2_state.ARRIVED,         "the fixture must stand OUTSIDE arrive_m or it proves nothing"
    handle.result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED, result=types.SimpleNamespace(error_code=0)))
    assert driving.adapter.state.state == nav2_state.ARRIVED
    driving.tick()
    assert driving.state["state"] == nav2_state.ARRIVED
    assert "arrived short" not in (driving.state.get("note") or "")


def test_an_arrival_a_metre_out_is_still_a_named_miss(driving):
    # m5v3's S7 orbit - a stable 0.643-0.742 m ring round a station the
    # truck can never reach - is what this note exists for, and it is a
    # long way outside the registration's own residual.
    handle = _on_the_station_spur(driving)
    driving.tf_at(-13.0, 4.25 + 1.0)
    driving.tick()
    handle.result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED, result=types.SimpleNamespace(error_code=0)))
    assert driving.adapter.state.state == nav2_state.BLOCKED
    driving.tick()
    assert "arrived short" in driving.state["note"]


def test_the_arrival_margin_is_the_registrations_own_residual(rig):
    """ONE HOME: the committed transform states what it is worth."""
    assert rig.adapter.arrival_margin_m == nav2_pose.floor_margin_m(
        rig.adapter.frame)
    assert 0.0 < rig.adapter.arrival_margin_m < 0.25


def test_no_published_speed_limit_ever_widens_the_envelope(rig):
    """D4, run3, 2026-09-02 - measured, and this is the guard.

    `setSpeedLimit` REPLACES a controller's configured maximum rather
    than intersecting with it. The adapter published the unrestricted
    permission ABSOLUTE - V_Limit 1500 mm/s as `speed_limit 1.5` - onto
    a controller whose envelope is 0.300, and the next /f1/cmd_vel row
    carried -1.5. A permission is a permission to go SLOWER.
    """
    envelope = rig.adapter.envelope_max_mps
    assert envelope == 0.300
    for v_limit in (300, 1500, 700, 99999, -1, 300):
        rig.status(v_limit=v_limit)
    sent = rig.node.pubs[rig.cfg.s("topics.speed_limit")].sent
    assert sent, "the permission was never published at all"
    for row in sent:
        assert row["speed_limit"] <= envelope + 1e-12, row
        assert row["percentage"] is False


def test_the_envelope_is_read_from_nav2s_own_params_file(rig):
    """ONE HOME. The number is nav2.yaml's; config.yaml does not repeat it."""
    path = os.path.join(_REPO, rig.cfg.s("nav.params_file"))
    assert rig.adapter.envelope_max_mps == nav2_envelope.envelope_max_mps_of(
        path)
    assert rig.adapter.limits.envelope_max_mps == rig.adapter.envelope_max_mps


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


# ----------------------------------------------------------------------
# "HOLD THE STEER AXIS" is a number on this wire (live, 2026-09-02)
# ----------------------------------------------------------------------
def test_a_sub_creep_twist_holds_the_steer_angle_it_last_sent(driving):
    """nav2_cmd answers None for "hold"; the wire has no way to say it.

    THE STANDING START IS THE CASE. nav2's controller ramps from rest
    through the creep deadband, so the first twists of the first leg are
    exactly the ones cmd_vel_tricycle_core answers `steer_rad=None` to -
    "Traction zero, steer HELD". Published straight through, that None
    aborts the process inside rosidl and the truck never moves; centred
    to 0.0 instead, the wheel is commanded to swing back to straight at
    every crawl, which inside a station spur is a motion into the rack.
    """
    import nav2_cmd
    limits = driving.adapter.limits

    # 1. a real cornering twist, well over the deadband: a real angle.
    driving.smoothed(-0.30, 0.20)
    driving.tick()
    linear, angular = driving.cmd
    assert type(angular) is float and angular != 0.0
    cornering = angular

    # 2. the same corner, now crawling under the creep deadband. The
    #    donor declines to answer a steer angle at all ...
    crawl = 0.5 * limits.creep_speed_mps
    assert nav2_cmd.translate(-crawl, 0.20, limits).angular_z is None
    #    ... and the wire still carries the angle the wheel is at.
    driving.smoothed(-crawl, 0.20)
    driving.tick()
    linear, angular = driving.cmd
    assert type(linear) is float and type(angular) is float
    assert linear == 0.0
    assert angular == pytest.approx(cornering)


def test_leaving_en_route_centres_the_wheel_and_the_hold_follows(driving):
    """Outside EN-ROUTE the contract is zeros on BOTH fields, so the
    held angle is zero too - the attribute is the last angle SENT."""
    driving.smoothed(-0.30, 0.20)
    driving.tick()
    assert driving.cmd[1] != 0.0
    driving.status(motor=False)            # SAFETY-STOP: zeros flow
    driving.tick()
    assert driving.cmd == (0.0, 0.0)
    assert driving.adapter.held_steer_rad == 0.0


# ----------------------------------------------------------------------
# 9. DEFECT D7: the current yaw reaches every door that builds a goal.
#
# nav2_legs decides the heading (SPEC_ADAPTER.md AMENDMENTS 3) and this
# shell only carries the truck's yaw to it - but it has to carry it at
# the moment the goal is BUILT, and there are THREE moments: the first
# leg of a route, the leg the preempt sends, and the leg a SAFETY-STOP
# re-sends when Motor comes back. A yaw read at the wrong instant is a
# heading for a pose the truck has already left, which is D7 wearing a
# different hat.
# ----------------------------------------------------------------------

#: A route that LEAVES a bay: spur exit then transit. Since
#: AMENDMENTS 4 both are RPP on ONE tree, so nav2 would allow a true
#: preemption here - and defect D10 (runs 8 and 9) is what happened
#: when it got one, and again when the adapter used the cancel door
#: instead. The spur exit is DRIVEN TO ITS GOAL now, and the transit
#: after it starts on nav2's SUCCEEDED, from a stop. That second leg
#: is a TRANSIT, which is the only class whose heading D7 touches.
OUT_OF_S1 = [(-13.0, 4.25), (-13.0, 10.0), (0.0, 10.0)]


def _goal_yaw(rig, index):
    """The world-frame heading of goal `index`, off the wire it went out
    on - through the registration, the same way round the adapter put it
    there."""
    goal = rig.action.goals[index]
    return nav2_pose.to_world(rig.adapter.frame, goal["map_pose"][0],
                              goal["map_pose"][1], goal["map_pose"][2])[2]


def _turn(goal_yaw, current_yaw):
    return abs(follower.norm_ang(goal_yaw - current_yaw))


def _at_s1(rig, yaw):
    """A truck standing in S1, in auto, with a live PLC."""
    rig.mode()
    rig.tf_at(-13.0, 4.25, yaw)
    rig.status()
    rig.tick()
    return rig


def test_the_first_goal_of_a_route_carries_the_trucks_own_yaw(rig):
    """DOOR 1 - the initial dispatch.

    TO_S1's first leg runs east and the truck is standing on pi, forks
    east. The travel direction (0.0) would turn it round in the ring
    band; the flip is what it is already doing.
    """
    rig.mode()
    rig.tf_at(-17.0, 10.0, math.pi)
    rig.status()
    rig.tick()
    rig.route(TO_S1)
    assert rig.adapter.legs[0].klass == nav2_legs.TRANSIT
    assert _turn(_goal_yaw(rig, 0), math.pi) < 1e-6


def test_the_first_goal_follows_the_yaw_and_is_not_a_constant(rig):
    """The same door, the same route, a truck pointing the other way -
    and the goal moves with it. A fixed answer would pass the test
    above and still be D7."""
    rig.mode()
    rig.tf_at(-17.0, 10.0, 0.2)
    rig.status()
    rig.tick()
    rig.route(TO_S1)
    assert _turn(_goal_yaw(rig, 0), 0.2) == pytest.approx(0.2, abs=1e-6)
    assert abs(follower.norm_ang(_goal_yaw(rig, 0))) < 1e-6


def test_the_preempted_leg_is_built_on_the_yaw_at_the_preempt(transiting):
    """DOOR 2 - true preemption, between two legs of one class.

    TWO_TRANSITS turns south at (-13.0, 10.0). A truck arriving on -0.4
    is clear of the tie band on the travel direction's side and keeps
    it; one arriving on +0.2 is on the flip's, and takes that. Same leg,
    same geometry, two answers - so the yaw is being read.
    """
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0, -0.4)
    transiting.tick()
    assert len(transiting.action.goals) == 2
    assert transiting.action.cancels == 0
    south = _goal_yaw(transiting, 1)
    assert _turn(south, -0.4) <= math.pi / 2.0
    assert abs(follower.norm_ang(south + math.pi / 2.0)) < 1e-6


def test_the_preempted_leg_takes_the_flip_when_the_yaw_asks_for_it(
        transiting):
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0, 0.2)
    transiting.tick()
    north = _goal_yaw(transiting, 1)
    assert _turn(north, 0.2) <= math.pi / 2.0
    assert abs(follower.norm_ang(north - math.pi / 2.0)) < 1e-6


def test_the_leg_after_a_bay_mouth_is_built_on_the_yaw_at_the_SEND(rig):
    """DOOR 3 by another name - defect D10's door, which is nav2's
    SUCCEEDED rather than a cancel.

    Inside P the spur exit is NOT handed over: no cancel, no pending
    leg, no second goal. It runs to its own goal, RPP decelerates into
    it, and the next leg starts when nav2 says the old one finished.
    The truck is still rolling through that (a tricycle takes 0.208 m
    to stop), so the goal is built on the yaw at the SEND: here it
    swings from -1.3 to -1.9 in between, which crosses the quarter turn
    and changes the answer from 0.0 to pi.
    """
    _at_s1(rig, float(STATIONS["S1"]["yaw"]))
    rig.route(OUT_OF_S1)
    # THREE LEGS SINCE D12: the 13 m ring leg is opened by its own
    # alignment leg, which is collinear with it and therefore takes the
    # same goal heading - so the yaw this test is about is unchanged.
    assert [leg.klass for leg in rig.adapter.legs] == [
        nav2_legs.SPUR_EXIT, nav2_legs.ALIGN, nav2_legs.TRANSIT]
    # ONE TREE, SO NAV2 WOULD ALLOW THE PREEMPTION. The refusal is ours.
    assert rig.adapter.legs[0].tree_key == rig.adapter.legs[1].tree_key
    rig.tf_at(-13.0, 10.0 - nav2_legs.PREEMPT_AT_M + 0.1, -1.3)
    rig.tick()
    rig.tf_at(-13.0, 10.0 - 0.2, -1.3)
    rig.tick()
    assert rig.adapter.pending_leg is None
    assert rig.action.cancels == 0
    assert len(rig.action.goals) == 1
    # the truck rolls to a stop while nav2 finishes with the goal
    rig.tf_at(-13.0, 10.0, -1.9)
    rig.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED,
        result=types.SimpleNamespace(error_code=0)))
    assert len(rig.action.goals) == 2
    east = _goal_yaw(rig, 1)
    assert abs(follower.norm_ang(east - math.pi)) < 1e-6
    assert _turn(east, -1.9) <= math.pi / 2.0


def test_the_same_leg_keeps_the_travel_direction_from_the_other_side(rig):
    _at_s1(rig, float(STATIONS["S1"]["yaw"]))
    rig.route(OUT_OF_S1)
    rig.tf_at(-13.0, 10.0 - nav2_legs.PREEMPT_AT_M + 0.1, -1.9)
    rig.tick()
    rig.tf_at(-13.0, 10.0, -1.3)
    rig.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED,
        result=types.SimpleNamespace(error_code=0)))
    assert len(rig.action.goals) == 2
    assert abs(follower.norm_ang(_goal_yaw(rig, 1))) < 1e-6


def test_the_last_leg_into_a_bay_cancels_for_the_tree_and_not_the_mouth(
        rig):
    """DOOR 3 on the OTHER boundary, and for the other reason.

    The bay's tree names the 0.25 m checker, so it is a different file
    and nav2 itself refuses to preempt across it: the adapter cancels,
    waits for the server's own result, and only then sends. The truck
    KEEPS MOVING through that wait, so the goal has to be built on the
    pose it is standing at when the send happens and not the one it was
    at when the decision was taken (D7).
      A STATION LEG'S HEADING IS THE BAY'S and does not move with the
    truck, so the yaw cannot be read off the goal here - it is read off
    the adapter's own leg line, which is the seam the field run quotes.
    """
    lines = []
    rig.node.get_logger = lambda: types.SimpleNamespace(
        info=lines.append, warn=lines.append)
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.status()
    rig.tick()
    rig.route(TO_S1)
    assert [leg.klass for leg in rig.adapter.legs] == [
        nav2_legs.TRANSIT, nav2_legs.STATION_SPUR]
    rig.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0, -1.3)
    rig.tick()
    assert rig.adapter.pending_leg == 1
    assert rig.action.cancels == 1
    assert len(rig.action.goals) == 1
    # the truck turns into the bay while the cancelled goal is still on
    # the server
    rig.tf_at(-13.0, 9.0, -1.9)
    rig.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.CANCELED, result=types.SimpleNamespace(error_code=0)))
    assert len(rig.action.goals) == 2
    assert _goal_yaw(rig, 1) == pytest.approx(float(STATIONS["S1"]["yaw"]),
                                              abs=1e-6)
    leg2 = [line for line in lines if "leg 2/2" in line]
    assert len(leg2) == 1
    assert "truck_yaw=-1.900" in leg2[0]
    assert "truck_yaw=-1.300" not in leg2[0]


def test_a_resume_re_goals_on_where_the_truck_is_now(driving):
    """DOOR 4 - SAFETY-STOP holds the route and Motor True re-sends it.

    The truck does not always stand still through a stop: the plant
    decelerates it, and a tricycle that is still rolling with the wheel
    over ends up somewhere else. The re-sent goal is built on the yaw at
    the RESUME, which is the only one that is true.
    """
    assert len(driving.action.goals) == 1
    driving.status(motor=False)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.SAFETY_STOP
    driving.tf_at(-17.0, 10.0, 0.1)
    driving.status(motor=True)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert len(driving.action.goals) == 2
    assert abs(follower.norm_ang(_goal_yaw(driving, 1))) < 1e-6
    assert _turn(_goal_yaw(driving, 1), 0.1) <= math.pi / 2.0


def test_a_resume_with_no_belief_waits_instead_of_guessing(driving):
    """AND IT WAITS FOR ONE. A goal built without a heading is a heading
    invented, which is the defect itself; the route is already HELD, so
    the honest answer is to stay stopped until the picture is back."""
    driving.status(motor=False)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.SAFETY_STOP
    # nothing fresh for longer than nav2_pose.SENSOR_STALE_S
    driving.holder["t"] += 5.0
    driving.status(motor=True)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.SAFETY_STOP
    assert len(driving.action.goals) == 1
    # the belief comes back, and so does the truck
    driving.tf_at(-17.0, 10.0, math.pi)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert len(driving.action.goals) == 2


def test_every_goal_this_shell_builds_names_its_leg_in_the_log(rig):
    """THE OBSERVABLE SEAM. A field run has to be able to quote the leg
    table - class, tree and goal yaw against the yaw the truck was on -
    and nothing else on this rig can reconstruct it: the goal that
    leaves is in map coordinates and the class is not on any wire."""
    lines = []
    rig.node.get_logger = lambda: types.SimpleNamespace(
        info=lines.append, warn=lines.append)
    _at_s1(rig, float(STATIONS["S1"]["yaw"]))
    rig.route(OUT_OF_S1)
    assert len(lines) == 1
    assert "leg 1/3" in lines[0]
    assert nav2_legs.SPUR_EXIT in lines[0]
    assert "nav.bt_xml_rpp" in lines[0]
    assert "-1.571" in lines[0]


# ----------------------------------------------------------------------
# 10. DEFECT D9: a non-final leg nav2 calls DONE moves the queue on.
#
# Run 6, measured: bt_navigator answered a leg pair with "Goal
# succeeded" 19 ms after it began navigating, 4 m short of the goal it
# named - the displaced leg had been inside the 0.60 m checker before it
# was sent. The adapter read SUCCEEDED for a NON-FINAL leg, had no
# branch for it, and stood on the spot until its own ClosingWatch called
# a stall that was really a lost goal: "blocked: no progress - best
# 4.00 m, 30 s without closing", twice.
#
# nav2_legs no longer builds a leg that can be displaced in the tick it
# is sent (D9's other half), so this is the belt over those braces: a
# server that says a leg is finished is a server with nothing on it, and
# the only honest answer is the next leg.
# ----------------------------------------------------------------------
def test_a_non_final_leg_that_nav2_calls_done_sends_the_next_one(
        transiting):
    assert len(transiting.action.goals) == 1
    transiting.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED,
        result=types.SimpleNamespace(error_code=0)))
    assert len(transiting.action.goals) == 2
    assert transiting.adapter.leg_i == 1
    assert transiting.adapter.state.state == nav2_state.EN_ROUTE


def test_the_last_leg_finishing_is_still_an_arrival_and_not_a_send(
        driving):
    """The final leg's SUCCEEDED is the arrival verdict and always was;
    D9 must not turn it into a goal nobody asked for."""
    driving.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    driving.tick()
    driving.action.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.CANCELED, result=types.SimpleNamespace(error_code=0)))
    assert len(driving.action.goals) == 2
    driving.tf_at(-13.0, 4.25)
    driving.action.handles[1].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED,
        result=types.SimpleNamespace(error_code=0)))
    assert driving.adapter.state.state == nav2_state.ARRIVED
    assert len(driving.action.goals) == 2
