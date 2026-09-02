"""The pins on tools/nav_plan_health.py - the per-truck plan gate.

NO ROS AND NO SIMULATOR IS REACHED FROM HERE, which is the same split
the tool itself is built on: the seed, the goal arithmetic and the
action name are decided before rclpy is imported, so everything that
could be WRONG about WHICH truck is being asked and WHERE the goal is
can be tested on the owner's Windows python. What cannot be tested here
is the only thing the tool exists for - whether a planner answered with
a path - and the tool's own selftest says so out loud rather than
printing a pass it never ran.
"""
import math
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6V2 = os.path.normpath(os.path.join(_HERE, os.pardir))
_TOOLS = os.path.join(_M6V2, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import nav_plan_health as gate                            # noqa: E402
import nav2_seed                                          # noqa: E402
from status_contract import VEHICLES                      # noqa: E402

VIDS = sorted(VEHICLES)
SOURCE = open(os.path.join(_TOOLS, "nav_plan_health.py"),
              encoding="utf-8").read()


# ----------------------------------------------------------------------
# WHICH TRUCK IS BEING ASKED
# ----------------------------------------------------------------------

def test_the_action_carries_the_truck():
    """Four planner servers advertise this action under four namespaces.

    Composed ABSOLUTELY rather than left relative under `-r __ns:=/fN`:
    both work on a correctly namespaced child, and only one of them
    still asks the right truck when a spawn line loses its remap - which
    is the silent-breakage class this whole branch's suites exist for.
    """
    for vid in VIDS:
        assert gate.plan_action(vid) == "/{}/compute_path_to_pose".format(vid)
    assert len({gate.plan_action(vid) for vid in VIDS}) == len(VIDS)
    assert gate.PLAN_ACTION == "compute_path_to_pose"


def test_a_stranger_vid_is_refused_by_name():
    with pytest.raises(SystemExit) as caught:
        gate.plan_action("forklift")
    assert "forklift" in str(caught.value)


# ----------------------------------------------------------------------
# WHERE THE GOAL IS
# ----------------------------------------------------------------------

def test_the_goal_is_along_the_heading_and_not_along_x():
    """THE FAILURE THIS ARITHMETIC AVOIDS IS A PASSING GATE.

    warehouse_v3's registration is about a half turn from the building,
    so `x + 2` in the map frame is two metres BEHIND every truck at
    spawn - which a Reeds-Shepp planner solves with a cusp and a three
    point turn, returns a long path for, and the gate would pass having
    proved something else.
    """
    seed = (1.0, 2.0, math.pi)
    ahead = gate.goal_ahead(seed, 2.0)
    assert ahead[2] == seed[2]
    assert math.isclose(ahead[0], -1.0, abs_tol=1e-9)
    assert math.isclose(ahead[1], 2.0, abs_tol=1e-9)
    # the same distance, in a direction that is not +x
    assert math.isclose(math.dist(seed[:2], ahead[:2]), 2.0, abs_tol=1e-9)


@pytest.mark.parametrize("vid", VIDS)
def test_the_goal_is_ahead_of_this_trucks_own_seed(vid):
    from nav2_adapter_node import vehicle_config
    cfg = vehicle_config(vid, "test_nav_plan_health", gate.REQUIRED_KEYS)
    _frame, seed = nav2_seed.seed_in_map(cfg, vid)
    ahead_m = cfg.f("nav.health.goal_ahead_m")
    ahead = gate.goal_ahead(seed, ahead_m)
    forward = ((ahead[0] - seed[0]) * math.cos(seed[2])
               + (ahead[1] - seed[1]) * math.sin(seed[2]))
    assert math.isclose(forward, ahead_m, abs_tol=1e-9)
    # 2.00 m down an 8.00 m ring leg: short enough to be trivial, long
    # enough that an empty costmap cannot answer it.
    assert ahead_m == 2.0


def test_the_seed_is_the_one_the_localiser_was_gated_on():
    """ONE PIECE OF ARITHMETIC, NOT TWO.

    nav2_seed.seed_in_map carries VEHICLES[vid].spawn into the map frame
    through the committed registration, and it is what seeded AMCL. A
    gate that derived its own start pose would be planning from a place
    the localiser was never told about.
    """
    assert "nav2_seed.seed_in_map" in SOURCE
    assert gate.__dict__["nav2_seed"].seed_in_map is nav2_seed.seed_in_map
    # and the start is the SEED, not tf: `use_start` is what says so
    assert "goal.use_start = True" in SOURCE
    assert "lookup_transform" not in SOURCE


# ----------------------------------------------------------------------
# WHAT IT PROMISES NOT TO DO
# ----------------------------------------------------------------------

def test_it_commands_no_motion():
    """compute_path_to_pose is the PLANNER's action.

    It never reaches the controller, so nothing is published on this
    truck's command path. A gate that could move a truck at bringup is
    a gate nobody would run with a load on the forks.
    """
    assert "NavigateToPose" not in SOURCE
    assert "create_publisher" not in SOURCE
    assert "cmd_vel" not in SOURCE
    assert "Twist" not in SOURCE
    assert "NOTHING WAS COMMANDED" in SOURCE


def test_the_lifecycle_wait_is_not_ported_twice():
    """truck.sh's nav_can_answer already waits on all six nodes.

    m5_ver3/tools/nav_health.py does both halves because it is the whole
    gate there. Here the first half exists in the runner, with its own
    refusal naming the costmap blocking rule, so asking again would be a
    second answer to a question already asked.
    """
    assert "get_state" not in SOURCE
    assert "GetState" not in SOURCE
    assert "lifecycle_msgs" not in SOURCE
    # it names the runner's gate rather than repeating it
    assert "nav_can_answer" in SOURCE


def test_every_required_key_is_read_and_every_read_key_is_required():
    """THE MAINTENANCE OBLIGATION, both directions.

    A key read below the list is a key that reaches its first use
    unchecked; a key in the list that nothing reads is a config
    constraint nobody asked for. The map/registration triple is read
    THROUGH the cfg this file hands nav2_seed, so it counts as read.
    """
    read = set(re.findall(r'cfg\.[sfi]\("([^"]+)"\)', SOURCE))
    through_seed = {"map.dir", "map.name", "map.registration.file"}
    assert read - through_seed <= set(gate.REQUIRED_KEYS)
    assert set(gate.REQUIRED_KEYS) - through_seed <= read


@pytest.mark.parametrize("vid", VIDS)
def test_the_selftest_passes_offline_for_every_truck(vid, capsys):
    assert gate.main(["--vid", vid, "--selftest"]) == 0
    out = capsys.readouterr().out
    assert gate.plan_action(vid) in out
    assert "NOT CHECKED HERE" in out
    assert "0 problems" in out


def test_the_selftest_survives_the_ros_argument_block(capsys):
    """truck.sh appends `--ros-args -r __ns:=/fN ...` to every child.

    argparse has never heard of `-r __ns:=/f1` and its answer is exit 2
    before a line of this program runs, so the split has to happen
    first - and it is own_args(), the same one the adapter and the seed
    gate use.
    """
    argv = ["--vid", "f1", "--selftest", "--ros-args", "-r", "__ns:=/f1",
            "-r", "__node:=nav_plan_health"]
    assert gate.main(argv) == 0
    assert "0 problems" in capsys.readouterr().out
