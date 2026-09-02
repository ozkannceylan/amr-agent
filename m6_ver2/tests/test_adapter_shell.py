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
import nav2_path                                           # noqa: E402
import nav2_pose                                           # noqa: E402
import nav2_seed                                           # noqa: E402
import nav2_state                                          # noqa: E402
import nav2_watch                                          # noqa: E402
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
    #: A SHARED SEQUENCE ACROSS BOTH SERVERS (AMENDMENTS 9). There are
    #: two goal servers now - navigate_to_pose and follow_path - and a
    #: test that asks "was the RUNNING goal cancelled" means whichever
    #: of them the adapter last sent to. One counter answers that
    #: without either fake having to know about the other.
    seq = 0

    def __init__(self, name):
        self.name = name
        self.goals = []
        self.handles = []
        self.cancels = 0
        self.accept = True
        self.last_seq = -1

    def send_goal_async(self, goal):
        Action.seq += 1
        self.last_seq = Action.seq
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
        # THE TWO GOAL SERVERS, KEYED BY THEIR ADDRESS (AMENDMENTS 9).
        # `action` stays as the NavigateToPose one so that every test
        # written before the chain existed still reads the server it
        # meant, and `follow` is the new one.
        self.actions = {}
        self.action = None
        self.follow = None

    def type_of(self, name):
        return name

    def qos(self, depth, latched):
        return (depth, latched)

    def action_client(self, node, kind, name):
        client = Action(name)
        self.actions[name] = client
        if name == "follow_path":
            self.follow = client
        else:
            self.action = client
        return client

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

    def chain_goal(self, frame_id, stamp, map_poses, controller_id,
                   goal_checker_id, progress_checker_id):
        return {"frame_id": frame_id, "map_poses": list(map_poses),
                "controller_id": controller_id,
                "goal_checker_id": goal_checker_id,
                "progress_checker_id": progress_checker_id}

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

    def filtered(self, v, w=0.0):
        """The EKF's own body twist - what the leg table quotes as `v`."""
        body = types.SimpleNamespace(
            linear=types.SimpleNamespace(x=v),
            angular=types.SimpleNamespace(z=w))
        self.send(self.cfg.s("topics.odometry_filtered"),
                  types.SimpleNamespace(
                      twist=types.SimpleNamespace(twist=body)))

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
        """The server the adapter last sent a goal to.

        TWO SERVERS SINCE AMENDMENTS 9. A ring chain goes out on
        follow_path and a manoeuvre on navigate_to_pose, and almost
        every test below is asking about THE RUNNING GOAL rather than
        about a particular server - so this follows the goal.
        """
        live = [client for client in self.msgs.actions.values()
                if client.goals]
        if not live:
            return self.msgs.action
        return max(live, key=lambda client: client.last_seq)

    @property
    def navigate(self):
        """The NavigateToPose server: the two manoeuvre classes."""
        return self.msgs.action

    @property
    def follow(self):
        """The FollowPath server: the ring chain, and nothing else."""
        return self.msgs.follow

    def override_legs(self, legs, current_yaw=math.pi):
        """Install a hand-built leg queue and dispatch its first leg.

        NO ROUTE ON THIS FLOOR PRODUCES TWO NavigateToPose LEGS ANY MORE
        (AMENDMENTS 9: the ring is one chain, and both manoeuvre classes
        are driven to their own goals). The preemption machinery is
        still the contract - PREEMPT_AT_M, should_preempt and both doors
        of _advance_to - so the tests that pin it drive it here,
        directly, instead of pretending a route can still build one.
        """
        self.adapter.legs = list(legs)
        self.adapter._send_leg(0, current_yaw)


#: A released polyline that ends on station S1 - so the split is a
#: TRANSIT leg and then a STATION SPUR, which is the pair the leg runner
#: exists for.
TO_S1 = [(-17.0, 10.0), (-13.0, 10.0), (-13.0, 4.25)]

#: THE SAME RING RUN, WHICH IS NOW ONE CHAIN. It is kept as a route so
#: that the state machine, the watchdog and the arrival have something
#: real underneath the hand-built queues below.
TWO_TRANSITS = [(-17.0, 10.0), (-13.0, 10.0), (-13.0, -10.0)]


def _leg(klass, points, final=False):
    """One leg of one class, built by hand.

    NO ROUTE ON THIS FLOOR PRODUCES A TRANSIT ANY MORE (AMENDMENTS 9:
    the ring collapses into a chain), so the preemption machinery -
    which is still the contract, and still what a class that earns a
    hand-over at P would be built on - is driven off queues made here.
    """
    controller, tree_key = nav2_legs.controller_for(klass)
    points = [tuple(p) for p in points]
    return nav2_legs.Leg(points=points, start=points[0], end=points[-1],
                         goal=nav2_legs.goal_point(points[-1], klass),
                         klass=klass, controller=controller,
                         tree_key=tree_key, final=final)


def _two_transits():
    """TWO_TRANSITS as it used to split: two legs, one tree."""
    return [_leg(nav2_legs.TRANSIT, [(-17.0, 10.0), (-13.0, 10.0)]),
            _leg(nav2_legs.TRANSIT, [(-13.0, 10.0), (-13.0, -10.0)],
                 final=True)]


def _transit_then_bay():
    """TO_S1 as it used to split: a transit and a bay, TWO trees."""
    return [_leg(nav2_legs.TRANSIT, [(-17.0, 10.0), (-13.0, 10.0)]),
            _leg(nav2_legs.STATION_SPUR, [(-13.0, 10.0), (-13.0, 4.25)],
                 final=True)]


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
    """The same truck on TWO hand-built transit legs - one class, one tree.

    THE ROUTE IS REAL AND THE QUEUE IS NOT (AMENDMENTS 9). The state
    machine, the watchdog and the arrival all need a route underneath
    them; what no route can still build is two NavigateToPose legs in a
    row, and that is the shape the preemption tests are about.
    """
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.status()
    rig.tick()
    rig.route(TWO_TRANSITS)
    rig.override_legs(_two_transits())
    return rig


@pytest.fixture
def two_trees(rig):
    """The truck on a hand-built transit -> station-spur queue.

    The one boundary nav2 itself refuses to preempt across, which is the
    reason _advance_to has two doors at all.
    """
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.status()
    rig.tick()
    rig.route(TO_S1)
    rig.override_legs(_transit_then_bay())
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


def test_the_first_leg_of_a_route_is_a_chain_on_follow_path(driving):
    """AMENDMENTS 9, at the wire. The ring run is not a pose at all.

    TO_S1 is a ring run and a bay, so the queue is a CHAIN and a station
    spur - and the chain goes out on the OTHER action server, carrying
    the path this adapter built off the granted polyline. No planner is
    asked anything about it.
    """
    legs = driving.adapter.legs
    assert [leg.klass for leg in legs] == [nav2_legs.RING_CHAIN,
                                           nav2_legs.STATION_SPUR]
    assert len(driving.navigate.goals) == 0
    assert len(driving.follow.goals) == 1
    goal = driving.follow.goals[0]
    assert goal["frame_id"] == driving.cfg.s("frames.map")
    # ALL THREE IDS ARE NAMED - AMENDMENTS 2's lesson, paid once
    # already: nav2_controller falls back on an empty id only when
    # exactly one plugin is loaded, and this stack loads two checkers.
    assert goal["controller_id"] == nav2_legs.CHAIN_CONTROLLER_ID
    assert goal["goal_checker_id"] == nav2_legs.CHAIN_GOAL_CHECKER_ID
    assert goal["progress_checker_id"] == nav2_legs.CHAIN_PROGRESS_CHECKER_ID
    # THE PATH IS IN THE MAP FRAME, and the polyline is in m6's world -
    # so the registration has to have been applied to every pose. Round-
    # tripping the two ends is the cheapest check that it was applied
    # the right way round: at -179.813 deg a rotation is very nearly its
    # own inverse.
    poses = goal["map_poses"]
    assert len(poses) > 30
    first = nav2_pose.to_world(driving.adapter.frame, *poses[0])
    last = nav2_pose.to_world(driving.adapter.frame, *poses[-1])
    assert first[0] == pytest.approx(-17.0, abs=1e-6)
    assert first[1] == pytest.approx(10.0, abs=1e-6)
    assert last[0] == pytest.approx(-13.0, abs=1e-6)
    assert last[1] == pytest.approx(10.0, abs=1e-6)
    # AND THE PATH IS STILL CUSP-FREE ON THE OTHER SIDE OF THE
    # REGISTRATION. The transform is a rotation and a translation, so it
    # cannot introduce one - but the path RPP reads is the transformed
    # one, and it is the transformed one that has to be checked.
    assert nav2_path.cusp_at(poses) is None


def test_a_ring_chain_is_never_preempted_at_p(driving):
    """It is a goal on ANOTHER SERVER, so P has nothing to do here.

    Before AMENDMENTS 9 this same route decided the next leg 1.5 m short
    of the spur foot and cancelled for the tree change. The chain runs
    to its own end against the 0.60 m general checker, and the bay goes
    out on its RESULT (D9's door).
    """
    for offset in (nav2_legs.PREEMPT_AT_M + 0.5,
                   nav2_legs.PREEMPT_AT_M - 0.1, 0.05):
        driving.tf_at(-13.0 - offset, 10.0)
        driving.tick()
        assert driving.adapter.pending_leg is None, offset
        assert len(driving.follow.goals) == 1, offset
        assert len(driving.navigate.goals) == 0, offset
        assert driving.follow.cancels == 0, offset


def test_the_chain_finishing_sends_the_bay_through_the_result_door(driving):
    """The chain SUCCEEDS at the spur foot; the station leg follows."""
    driving.tf_at(-13.0, 10.0, -1.9)
    driving.tick()
    driving.follow.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED,
        result=types.SimpleNamespace(error_code=0)))
    assert len(driving.navigate.goals) == 1
    assert driving.adapter.legs[driving.adapter.leg_i].final
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert driving.navigate.goals[0]["behavior_tree"].endswith(
        os.path.basename(driving.cfg.s("nav.bt_xml_station")))


def test_a_polyline_the_builder_refuses_is_a_named_block(rig):
    """A corner too tight to round is not a silent stop.

    It cannot be built out of route.py's own floor - the suite asserts
    that over every station pair - so it is reached here the only way it
    could ever be reached in the field: a polyline that is not this
    floor's. Re-sending it would refuse the same way for ever, so the
    fleet is told once and gets to requeue.
    """
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.status()
    rig.tick()
    rig.route([(-17.0, 10.0), (-13.0, 10.0), (-13.0, 10.5), (-17.0, 10.5)])
    assert rig.adapter.state.state == nav2_state.BLOCKED
    assert rig.adapter.state.note == nav2_watch.CHAIN_REFUSED_NOTE
    assert len(rig.follow.goals) == 0


def test_the_next_leg_is_decided_at_the_preempt_distance(two_trees):
    """P = 1.5 m, and it is nav2_legs' number rather than this shell's."""
    two_trees.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M - 0.5, 10.0)
    two_trees.tick()
    assert len(two_trees.navigate.goals) == 1
    assert two_trees.adapter.pending_leg is None
    two_trees.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    two_trees.tick()
    # THE DECISION IS TAKEN AT P. What it does with it depends on
    # whether the tree changes, which for this queue it does - see the
    # test below for why nav2 will not take that as a preemption.
    assert two_trees.adapter.pending_leg == 1


def test_a_tree_change_is_a_cancel_and_then_a_send(two_trees):
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
    two_trees.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    two_trees.tick()
    # 1. cancelled, and NOTHING new sent yet.
    assert two_trees.navigate.cancels == 1
    assert two_trees.navigate.handles[0].cancelled is True
    assert len(two_trees.navigate.goals) == 1
    assert two_trees.adapter.pending_leg == 1
    # 2. more ticks change nothing: a leg already waiting is not
    #    cancelled a second time.
    two_trees.tick()
    two_trees.tick()
    assert two_trees.navigate.cancels == 1
    assert len(two_trees.navigate.goals) == 1
    # 3. the server reports the old goal finished, and only then.
    two_trees.navigate.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.CANCELED,
        result=types.SimpleNamespace(error_code=0)))
    assert len(two_trees.navigate.goals) == 2
    assert two_trees.adapter.pending_leg is None
    assert two_trees.adapter.state.state == nav2_state.EN_ROUTE
    # THE STATION TREE, because leg 2 is the spur into the bay:
    # nav2_legs.CLASS_TREE names the key and this shell only looks it
    # up in the config.
    assert two_trees.navigate.goals[1]["behavior_tree"].endswith(
        os.path.basename(two_trees.cfg.s("nav.bt_xml_station")))


def test_the_rejected_preemptions_own_abort_is_not_a_failure(two_trees):
    """The same switch, when nav2 answers the cancel with ABORTED.

    A cancelled NavigateToPose does not always come back CANCELED - a
    BT that was already failing terminates ABORTED with whatever code it
    had. Either way the goal is OFF the server, which is the only fact
    the pending leg is waiting for.
    """
    two_trees.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    two_trees.tick()
    two_trees.navigate.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.ABORTED,
        result=types.SimpleNamespace(error_code=0)))
    assert two_trees.adapter.state.state == nav2_state.EN_ROUTE
    assert len(two_trees.navigate.goals) == 2


def test_true_preemption_still_runs_between_legs_of_one_class(transiting):
    """P = 1.5 m with NO cancel in it, which is what it was measured for.

    Two transit legs share nav.bt_xml_rpp, so bt_navigator takes the
    second goal as a real preemption and displaces the first itself -
    the truck never stops, and `executing` never flickers.
    """
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M - 0.5, 10.0)
    transiting.tick()
    assert len(transiting.navigate.goals) == 1
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    transiting.tick()
    assert len(transiting.navigate.goals) == 2
    assert transiting.navigate.cancels == 0
    assert transiting.adapter.pending_leg is None
    assert transiting.navigate.goals[1]["behavior_tree"].endswith(
        os.path.basename(transiting.cfg.s("nav.bt_xml_rpp")))


def test_a_cancel_takes_the_waiting_leg_with_it(two_trees):
    """A pending leg that outlived the route would be a goal nobody
    asked for, sent after the door that asked for it had closed."""
    two_trees.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    two_trees.tick()
    assert two_trees.adapter.pending_leg == 1
    two_trees.send("auto/goal", types.SimpleNamespace(data=""))
    assert two_trees.adapter.pending_leg is None
    two_trees.navigate.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.CANCELED,
        result=types.SimpleNamespace(error_code=0)))
    assert len(two_trees.navigate.goals) == 1
    assert two_trees.adapter.state.state == nav2_state.IDLE


def test_a_preempted_legs_abort_is_not_a_failure(transiting):
    """THE GENERATION COUNTER, and it is the whole of Decision 2's tail.

    nav2 displaces a running goal itself, so the leg that was preempted
    comes back ABORTED - every single time. Read as a failure it would
    latch BLOCKED on a truck that is driving perfectly, and vda_agent
    would report pathBlocked on a corridor that is clear.
    """
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0)
    transiting.tick()
    assert len(transiting.navigate.handles) == 2
    transiting.navigate.handles[0].result_future.fire(types.SimpleNamespace(
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
    # THE CHAIN'S SERVER, because that is the one a route reaches first
    # since AMENDMENTS 9.
    rig.follow.accept = False
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

    The station spur is the last of TWO objects since AMENDMENTS 9: the
    chain runs to the spur foot on follow_path, and the bay goes out on
    navigate_to_pose when the chain's own result lands (D9's door).
    """
    driving.tf_at(-13.0, 10.0)
    driving.tick()
    driving.follow.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED,
        result=types.SimpleNamespace(error_code=0)))
    assert driving.adapter.legs[driving.adapter.leg_i].final
    return driving.navigate.handles[0]


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
    goal = rig.navigate.goals[index]
    return nav2_pose.to_world(rig.adapter.frame, goal["map_pose"][0],
                              goal["map_pose"][1], goal["map_pose"][2])[2]


def _chain_yaw(rig, index=0, pose=0):
    """The world-frame orientation of one pose of chain goal `index`."""
    goal = rig.follow.goals[index]
    return nav2_pose.to_world(rig.adapter.frame, *goal["map_poses"][pose])[2]


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
    assert rig.adapter.legs[0].klass == nav2_legs.RING_CHAIN
    # THE CHAIN CARRIES THE ANSWER ON EVERY POSE (AMENDMENTS 9) - the
    # same D7 comparison, resolved once at dispatch and then spent.
    assert _turn(_chain_yaw(rig), math.pi) < 1e-6
    assert _turn(_chain_yaw(rig, pose=-1), math.pi) < 1e-6


def test_the_first_goal_follows_the_yaw_and_is_not_a_constant(rig):
    """The same door, the same route, a truck pointing the other way -
    and the path's orientations move with it. A fixed answer would pass
    the test above and still be D7."""
    rig.mode()
    rig.tf_at(-17.0, 10.0, 0.2)
    rig.status()
    rig.tick()
    rig.route(TO_S1)
    assert _turn(_chain_yaw(rig), 0.2) == pytest.approx(0.2, abs=1e-6)
    assert abs(follower.norm_ang(_chain_yaw(rig))) < 1e-6


def test_the_preempted_leg_is_built_on_the_yaw_at_the_preempt(transiting):
    """DOOR 2 - true preemption, between two legs of one class.

    TWO_TRANSITS turns south at (-13.0, 10.0). A truck arriving on -0.4
    is clear of the tie band on the travel direction's side and keeps
    it; one arriving on +0.2 is on the flip's, and takes that. Same leg,
    same geometry, two answers - so the yaw is being read.
    """
    transiting.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0, -0.4)
    transiting.tick()
    assert len(transiting.navigate.goals) == 2
    assert transiting.navigate.cancels == 0
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


def test_the_chain_out_of_a_bay_starts_in_the_bay(rig):
    """DEFECT D15, ON THE SHELL. There is no goal at the mouth at all.

    The first cut of AMENDMENTS 9 stopped the truck at the mouth on the
    bay's heading and then handed it a chain running east - a carrot
    across its own body axis, a curvature demand of 2.1 to 2.9 1/m
    against a 1.25 m minimum radius, and an orbit at the steer stop
    (run 17). The chain now starts IN THE BAY: one goal, one path, the
    mouth rounded inside it, and the truck leaving dead astern along its
    own axis.
    """
    _at_s1(rig, float(STATIONS["S1"]["yaw"]))
    rig.route(OUT_OF_S1)
    assert [leg.klass for leg in rig.adapter.legs] == [nav2_legs.RING_CHAIN]
    assert len(rig.navigate.goals) == 0
    assert len(rig.follow.goals) == 1
    poses = rig.follow.goals[0]["map_poses"]
    head = nav2_pose.to_world(rig.adapter.frame, *poses[0])
    assert head[0] == pytest.approx(-13.0, abs=1e-6)
    assert head[1] == pytest.approx(4.25, abs=1e-6)
    # DEAD ASTERN: the sense is the one the truck is already standing
    # in, so nothing is asked of a standing truck (D5, D7, D15).
    assert _turn(_chain_yaw(rig), float(STATIONS["S1"]["yaw"])) < 1e-6
    # ... and the mouth is a rounded corner in the middle of it, not an
    # end: no pose sits ON the vertex, and none is more than the arc's
    # sagitta off the granted line.
    world = [nav2_pose.to_world(rig.adapter.frame, *p)[:2] for p in poses]
    assert min(math.dist(p, (-13.0, 10.0)) for p in world) > 0.4
    worst = max(nav2_path.offset_from_polyline(p, OUT_OF_S1) for p in world)
    assert worst < 0.50, worst


def test_the_ring_run_off_a_mouth_is_one_goal_and_never_a_second(rig):
    """WHAT AMENDMENTS 9 AND D15 REPLACED THE ALIGNMENT LEG WITH.

    Out of S1 the queue used to be a spur exit, an alignment leg and a
    13 m transit: three goals, two boundaries, and run 16 lost three of
    eight alignment legs to the two-sense tie at the mouth. It is ONE
    path. Driving the whole route produces no further dispatch of any
    kind - which is the property the tie needed to survive and no longer
    has anywhere to live.
    """
    _at_s1(rig, float(STATIONS["S1"]["yaw"]))
    rig.filtered(-0.30)
    rig.route(OUT_OF_S1)
    assert [leg.klass for leg in rig.adapter.legs] == [nav2_legs.RING_CHAIN]
    assert len(rig.follow.goals) == 1
    assert rig.adapter.legs[rig.adapter.leg_i].klass == nav2_legs.RING_CHAIN
    # ... and the whole 13 m ring run costs nothing more. No preempt, no
    # cancel, no second path, and one decision in the entire leg.
    # SHORT OF THE ARRIVAL RADIUS, deliberately: this test is about what
    # happens WHILE the chain is driven, and the arrival is its own
    # door (it cancels, run 14).
    for step in ((-13.0, 8.0), (-13.0, 10.0), (-11.5, 10.0), (-8.0, 10.0),
                 (-4.0, 10.0), (-1.4, 10.0), (-0.4, 10.0)):
        rig.tf_at(step[0], step[1], math.pi)
        rig.status()                      # the PLC keeps talking, too
        rig.tick()
    assert len(rig.follow.goals) == 1
    assert len(rig.navigate.goals) == 0
    assert rig.follow.cancels == 0
    assert rig.adapter.pending_leg is None


def test_the_leg_table_quotes_the_speed_the_handover_happened_at(rig):
    """THE SEAM AMENDMENTS 8 HAS TO BE READ THROUGH.

    "It hands over in motion" is a claim about a number no other line
    on this rig carries: the leg table is written at the dispatch and
    the truck's speed is only on /est/odom, sampled elsewhere. So the
    dispatch line carries it, signed, from the EKF's own body twist -
    forks-first is negative on this model (Decision 1's sign audit).
    """
    lines = []
    rig.node.get_logger = lambda: types.SimpleNamespace(
        info=lines.append, warn=lines.append)
    _at_s1(rig, float(STATIONS["S1"]["yaw"]))
    rig.filtered(0.0)
    rig.route(OUT_OF_S1)
    assert "v=+0.000" in lines[0], lines[0]
    # THE SAME SEAM ON A RE-SEND: the truck is rolling when a SAFETY-STOP
    # resume re-dispatches the chain, and the line has to say so.
    rig.filtered(-0.301)
    rig.status(motor=False)
    rig.tick()
    rig.tf_at(-13.0, 8.0, -1.571)
    rig.status(motor=True)
    rig.tick()
    dispatch = [line for line in lines if line.startswith("leg 1/1")]
    assert len(dispatch) == 2, lines
    assert "v=-0.301" in dispatch[1], dispatch[1]
    # AND THE CHAIN TABLE CARRIES ITS OWN NUMBERS (AMENDMENTS 9): a path
    # has four hundred poses and none of them is the decision, so the
    # line quotes what the decision WAS.
    assert "ring chain follow_path" in dispatch[1], dispatch[1]
    for field in ("head=", "len=", "poses=", "corners=", "dropped=",
                  "sense="):
        assert field in dispatch[1], dispatch[1]


def test_the_same_chain_keeps_the_travel_direction_from_the_other_side(rig):
    """The truck standing in its bay POINTING OUT of it, which is the
    other way a forklift can park: the sense follows, and it is the one
    that asks it for no turn (D7)."""
    _at_s1(rig, math.pi / 2.0)
    rig.route(OUT_OF_S1)
    assert len(rig.follow.goals) == 1
    assert abs(follower.norm_ang(
        _chain_yaw(rig) - math.pi / 2.0)) < 1e-6


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
        nav2_legs.RING_CHAIN, nav2_legs.STATION_SPUR]
    rig.tf_at(-13.0 - nav2_legs.PREEMPT_AT_M + 0.1, 10.0, -1.3)
    rig.tick()
    # THE CHAIN IS NOT PREEMPTED AT P AT ALL SINCE AMENDMENTS 9 - it is
    # on another server. What is unchanged is the SEAM: the bay goal is
    # built when it is SENT and not when the boundary was reached.
    assert rig.adapter.pending_leg is None
    assert len(rig.navigate.goals) == 0
    # the truck turns into the bay while the chain is still running
    rig.tf_at(-13.0, 9.0, -1.9)
    rig.follow.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED, result=types.SimpleNamespace(error_code=0)))
    assert len(rig.navigate.goals) == 1
    assert _goal_yaw(rig, 0) == pytest.approx(float(STATIONS["S1"]["yaw"]),
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
    assert len(driving.follow.goals) == 1
    driving.status(motor=False)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.SAFETY_STOP
    driving.tf_at(-17.0, 10.0, 0.1)
    driving.status(motor=True)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert len(driving.follow.goals) == 2
    assert abs(follower.norm_ang(_chain_yaw(driving, index=1))) < 1e-6
    assert _turn(_chain_yaw(driving, index=1), 0.1) <= math.pi / 2.0


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
    assert len(driving.follow.goals) == 1
    # the belief comes back, and so does the truck
    driving.tf_at(-17.0, 10.0, math.pi)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert len(driving.follow.goals) == 2


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
    assert "leg 1/1" in lines[0]
    assert nav2_legs.RING_CHAIN in lines[0]
    assert "follow_path" in lines[0]
    assert "truck_yaw=-1.571" in lines[0]
    # AND THE OTHER SHAPE, WHICH IS THE ONE WITH A TREE ON IT: the bay
    # at the far end is still a NavigateToPose and still names its tree.
    other = []
    rig.node.get_logger = lambda: types.SimpleNamespace(
        info=other.append, warn=other.append)
    rig.route(TO_S1)
    rig.tf_at(-13.0, 10.0, -1.3)
    rig.tick()
    rig.follow.handles[-1].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED, result=types.SimpleNamespace(error_code=0)))
    bay = [line for line in other if nav2_legs.STATION_SPUR in line]
    assert len(bay) == 1, other
    assert "nav.bt_xml_station" in bay[0]


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
    handle = _on_the_station_spur(driving)
    assert len(driving.navigate.goals) == 1
    driving.tf_at(-13.0, 4.25)
    handle.result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED,
        result=types.SimpleNamespace(error_code=0)))
    assert driving.adapter.state.state == nav2_state.ARRIVED
    assert len(driving.navigate.goals) == 1
    assert len(driving.follow.goals) == 1


# ----------------------------------------------------------------------
# DEFECT D13: THE GOAL THAT LEAVES AIMS PAST THE POINT (AMENDMENTS 6)
#
# nav2's station checker and the fleet's arrival radius are one 0.25 m
# number with no margin, sampled off two beliefs; run 13 measured nav2
# SUCCEEDING at 0.2473 m on the estimate with the truck 0.3121 m out,
# and fourteen re-issued orders that could not move a truck already
# inside the checker. The LEG still ends on the station - every distance
# this shell and the fleet measure is to that point - and only the
# NavigateToPose message carries the deeper one.
# ----------------------------------------------------------------------

def test_the_bay_goal_that_leaves_is_the_point_advanced(driving):
    """The message is read off the action and put back through the map."""
    _on_the_station_spur(driving)
    goal = driving.navigate.goals[-1]
    assert goal["behavior_tree"].endswith(
        os.path.basename(driving.cfg.s("nav.bt_xml_station")))
    back = nav2_pose.to_world(driving.adapter.frame, goal["map_pose"][0],
                              goal["map_pose"][1], goal["map_pose"][2])
    bay = driving.adapter.legs[-1]
    assert bay.klass == nav2_legs.STATION_SPUR
    assert bay.end == (-13.0, 4.25)
    assert back[0] == pytest.approx(-13.0, abs=1e-6)
    assert back[1] == pytest.approx(4.25 - nav2_legs.ARRIVE_BIAS_M, abs=1e-6)
    # THE HEADING IS UNTOUCHED: the bay's own approach heading, which is
    # also the axis the point was advanced along.
    assert back[2] == pytest.approx(float(STATIONS["S1"]["yaw"]), abs=1e-6)


def test_a_chain_still_ends_on_its_own_end(driving):
    """Only the bay aims past itself. The granted corridor is not moved.

    A chain has no goal to advance at all - what would be advanced is
    the last pose of a path, and moving it would move the corridor. So
    the last pose IS the spur foot the ledger granted, to the micron.
    """
    goal = driving.follow.goals[0]
    back = nav2_pose.to_world(driving.adapter.frame, *goal["map_poses"][-1])
    assert driving.adapter.legs[0].klass == nav2_legs.RING_CHAIN
    assert back[0] == pytest.approx(-13.0, abs=1e-6)
    assert back[1] == pytest.approx(10.0, abs=1e-6)


def test_the_leg_table_says_where_the_goal_went(rig):
    """The leg table is the only record of what left, so it carries both.

    D7 was found in this line and D13 is unreadable without it: the end
    and the goal are two different points now, and a table printing one
    of them cannot tell a run that aimed past from a run that did not.
    """
    lines = []
    rig.node.get_logger = lambda: types.SimpleNamespace(
        info=lines.append, warn=lines.append)
    rig.mode()
    rig.tf_at(-17.0, 10.0)
    rig.status()
    rig.tick()
    rig.route(TO_S1)
    rig.tf_at(-13.0, 10.0, -1.3)
    rig.tick()
    rig.follow.handles[0].result_future.fire(types.SimpleNamespace(
        status=Messages.SUCCEEDED, result=types.SimpleNamespace(error_code=0)))
    legs = [line for line in lines if line.startswith("leg ")]
    assert len(legs) == 2, legs
    # THE CHAIN LINE IS A DIFFERENT SHAPE AND SAYS SO (AMENDMENTS 9): it
    # names the server, its own end, and the four numbers that are the
    # decision - there is no single goal pose to print.
    assert "ring chain follow_path end=(-13.00, 10.00)" in legs[0], legs[0]
    assert "len=4.00 poses=41 corners=0 dropped=0" in legs[0], legs[0]
    assert "sense=" in legs[0], legs[0]
    assert "end=(-13.00, 4.25) goal=(-13.00, 4.15)" in legs[1], legs[1]



# ----------------------------------------------------------------------
# THE LATCH AND THE CANCEL ARE ONE ACTION, AND RUN 14 IS WHY
#
# D13 aims the bay's goal ARRIVE_BIAS_M past the station point so that
# nav2's own checker fires with margin. The adapter's 20 Hz latch fires
# at arrive_m of the POINT - 0.10 m earlier on the same axis - and it
# cancels, so the aim-past goal never gets driven. The obvious fix was
# to let the bay's goal outlive the latch. It was built, and the floor
# refused it (run 14, 2026-09-03):
#
#   * IT MOVES NOTHING. Decision 3 publishes ZEROS on /auto/cmd_vel
#     outside EN-ROUTE, so the truck is commanded to stop the instant
#     the arrival latches whatever nav2 still believes. Measured, with
#     the goal deliberately left running: v 0.1159 -> 0.0000 in one
#     0.2 s sample at estimate 0.2480 m, against run 13's cancelled
#     0.2462 m. The same stop, to two millimetres.
#   * AND IT KILLS THE NEXT ORDER. Three seconds later the fleet's leg 2
#     went out, the spur exit was sent on the RPP tree while the station
#     tree was still on the server, nav2 refused the preemption, and the
#     order died 200 ms after it was issued: "blocked: nav2 refused
#     (error_code 0)". Fourteen re-dispatches followed.
#
# So the cancel stays where it is, and these tests pin it there.
# ----------------------------------------------------------------------

def test_the_arrival_takes_the_goal_off_the_server(driving):
    """Every arrival cancels, bay or not - run 14's own conclusion."""
    _on_the_station_spur(driving)
    cancels = driving.action.cancels
    driving.tf_at(-13.0, 4.25 + 0.24)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.ARRIVED
    assert driving.action.cancels == cancels + 1
    assert driving.adapter.handle is None
    driving.tick()
    assert driving.state["state"] == nav2_state.ARRIVED


def test_no_goal_outlives_the_route_that_asked_for_it(driving):
    """The property run 14 broke, stated so it cannot break again.

    A goal still on the server when the next route arrives is a goal
    nav2 will be asked to preempt across a tree boundary - the one
    boundary it refuses (_advance_to's own quotation) - and the answer
    is an aborted NEW goal with error_code 0 and a BLOCKED order.
    """
    _on_the_station_spur(driving)
    driving.tf_at(-13.0, 4.25 + 0.24)
    driving.tick()
    assert driving.adapter.handle is None
    assert driving.adapter.pending_leg is None
    driving.route([(-13.0, 4.25), (-13.0, 10.0), (-10.0, 10.0)])
    assert driving.adapter.state.state == nav2_state.EN_ROUTE
    assert driving.state.get("note") in (None, "")


def test_a_late_abort_cannot_un_arrive_a_latched_arrival(driving):
    """The result of the cancelled goal lands after the fleet was told.

    Once ARRIVED is latched the route is over and the fleet has been
    told. A nav2 error code landing afterwards is a report about a goal
    the adapter no longer needs, and reading it as a BLOCKED would take
    a completed pick off the truck.
    """
    handle = _on_the_station_spur(driving)
    driving.tf_at(-13.0, 4.25 + 0.24)
    driving.tick()
    assert driving.adapter.state.state == nav2_state.ARRIVED
    handle.result_future.fire(types.SimpleNamespace(
        status=Messages.ABORTED, result=types.SimpleNamespace(error_code=103)))
    assert driving.adapter.state.state == nav2_state.ARRIVED
    driving.tick()
    assert driving.state["state"] == nav2_state.ARRIVED
    assert not (driving.state.get("note") or "")
