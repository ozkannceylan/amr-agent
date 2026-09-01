"""pallet_cycle.py's plan - F5 Task 3's remaining Nav2 cycle.

NO ROS AND NO GAZEBO. The live loop is scored by drive_goal / dock_bench
/ pallet_bench; this file pins that the plan names every leg the F5
plan asked for and does not teleport, edit the world, or call the
UndockRobot action that T2 named 905.
"""
import os

import pytest

import pallet_bench as pb                             # noqa: E402
import pallet_cycle as cy                             # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def test_plan_names_every_leg_the_plan_asked_for():
    assert [step["leg"] for step in cy.plan_cycle()] == list(pb.CYCLE)


def test_transit_is_nav2_along_the_ring():
    step = cy.plan_cycle()[0]
    assert step["tool"] == "drive_goal.py"
    assert step["argv"] == ["record", "--goal", "spine_north"]


# ----------------------------------------------------------------------
# WHICH TRANSIT GOAL, AND IT IS CHOSEN BY WHERE THE TRUCK IS - G5 TASK 9
#
# The transit leg is the same ERRAND every cycle and it is not the same
# DRIVE. Cycle 1 leaves the spawn down an open 8.00 m corridor; every
# cycle after it leaves the S5 bay through a Reeds-Shepp cusp, and the
# two geometries measured OPPOSITE ways on the two controllers
# (config.yaml nav.goals.spine_north carries the campaign). A goal row
# holds one controller, so the split is two rows and the cycle picks
# between them by origin.
#   THE LEG NAME DOES NOT MOVE. config.yaml film.shots is one row per
# plan_cycle leg and tests/test_film_core.py locks the two together; a
# film that had to know which cycle it was filming would be a film that
# noticed. Only the `--goal` argument differs.
# ----------------------------------------------------------------------

def test_the_FIRST_transit_of_a_run_leaves_the_SPAWN():
    step = cy.plan_cycle(cy.transit_origin(1))[0]
    assert step["leg"] == "transit"
    assert step["tool"] == "drive_goal.py"
    assert step["argv"] == ["record", "--goal", "spine_north"]


@pytest.mark.parametrize("cycle", [2, 3, 4, 10])
def test_EVERY_LATER_transit_leaves_the_S5_BAY(cycle):
    step = cy.plan_cycle(cy.transit_origin(cycle))[0]
    assert step["leg"] == "transit"
    assert step["tool"] == "drive_goal.py"
    assert step["argv"] == ["record", "--goal", "spine_north_from_bay"]


def test_transit_origin_is_the_spawn_ONCE_and_the_bay_ever_after():
    assert cy.transit_origin(1) == "spawn"
    assert all(cy.transit_origin(n) == "bay" for n in range(2, 12))


def test_the_default_origin_is_the_SPAWN_one():
    # Every caller that does not care - the film's shot lock, the leg
    # list, `describe` - gets cycle 1's plan, which is the plan this
    # file pinned before the split existed.
    assert cy.plan_cycle() == cy.plan_cycle(cy.transit_origin(1))


def test_BOTH_origins_name_a_goal_row_that_config_yaml_HOLDS():
    import yaml
    with open(os.path.join(_M5V3, "config.yaml"), encoding="utf-8") as fh:
        goals = yaml.safe_load(fh)["nav"]["goals"]
    assert set(cy.TRANSIT_GOAL) == {"spawn", "bay"}
    for origin, goal in cy.TRANSIT_GOAL.items():
        assert goal in goals, origin


def test_ONLY_the_transit_ARGV_differs_between_the_two_origins():
    """THE FILM MUST NOT NOTICE. Same legs, same order, same tools.

    config.yaml film.shots is one row per leg of plan_cycle() and
    tests/test_film_core.py holds them equal; if the origin could move
    a leg name the cut would refuse a perfect take on cycle 2.
    """
    spawn = cy.plan_cycle("spawn")
    bay = cy.plan_cycle("bay")
    assert [s["leg"] for s in spawn] == [s["leg"] for s in bay]
    assert [s["tool"] for s in spawn] == [s["tool"] for s in bay]
    differ = [i for i, (a, b) in enumerate(zip(spawn, bay))
              if a["argv"] != b["argv"]]
    assert differ == [0]


def test_an_ORIGIN_THAT_IS_NOT_A_POSE_ON_THIS_FLOOR_is_refused_by_name():
    # A typo must not silently fall back on a controller. There are two
    # origins because there are two geometries, and a third is a bug.
    with pytest.raises(ValueError) as excinfo:
        cy.plan_cycle("aisle")
    assert "spawn" in str(excinfo.value) and "bay" in str(excinfo.value)


def test_run_asks_for_the_origin_of_the_CYCLE_IT_IS_ON():
    # The seam, pinned against the source: `run` loops cycles and must
    # plan each one from its own origin. A run that planned once and
    # reused it would send the spawn goal out of the bay - which is the
    # exact leg G5 Task 7 measured failing 2 of 2.
    src = open(cy.__file__, encoding="utf-8").read()
    assert "plan_cycle(transit_origin(n))" in src


def test_empty_stage_is_nav2_stage_s5():
    stages = [s for s in cy.plan_cycle() if s["leg"] == "stage"]
    assert len(stages) == 2
    assert stages[0]["tool"] == "drive_goal.py"
    assert stages[0]["argv"] == ["record", "--case", "stage_s5"]


def test_laden_return_stage_is_cmd_vel_not_nav2():
    """010800: Nav2 stage_s5 after carry drove north to y=12.6.

    AMCL was still at the docked pose; the pallet is also a scan
    obstacle (laden footprint not switched). Return is body -x.
    """
    stages = [s for s in cy.plan_cycle() if s["leg"] == "stage"]
    assert stages[1]["tool"] == "burst"
    assert "return" in stages[1]["argv"]


def test_pickup_dock_is_plugin_from_staging():
    docks = [s for s in cy.plan_cycle() if s["leg"] == "dock"]
    assert len(docks) == 2
    assert docks[0]["tool"] == "dock_bench.py"
    assert docks[0]["argv"] == ["record", "--from-staging"]


def test_laden_return_dock_is_cmd_vel_not_plugin():
    """set_pose does not carry an attached child (EVIDENCE §4.2).

    Plugin dock also yaws off attach_ok. Drop is the reverse of
    the undock burst, heading kept from the aisle cmd_vel.
    """
    docks = [s for s in cy.plan_cycle() if s["leg"] == "dock"]
    assert docks[1]["tool"] == "burst"
    assert "return-dock" in docks[1]["argv"]


def test_run_seeds_heading_before_plugin_dock():
    src = open(cy.__file__, encoding="utf-8").read()
    assert "heading seed" in src
    assert 'step["tool"] == "dock_bench.py"' in src
    assert "set_pose" not in src


def test_run_restores_docked_pose_before_attach():
    src = open(cy.__file__, encoding="utf-8").read()
    assert "docked pose restore" in src
    assert "pallet_bench.py" in src


def test_run_reseeds_amcl_after_cmd_vel_carry():
    src = open(cy.__file__, encoding="utf-8").read()
    assert "live seed" in src


def test_run_rejects_a_nav2_abort():
    src = open(cy.__file__, encoding="utf-8").read()
    assert "action_status=4" in src


def test_run_recovers_an_empty_nav2_miss_to_staging():
    """spine_north from spawn is the named ring_corner miss class.

    An empty Nav2 miss must not abort the pallet cycle: dock_bench
    stage is T2's measured heading-aligned staging, and set_pose
    is legal while the pallet is not attached.
    """
    src = open(cy.__file__, encoding="utf-8").read()
    assert "nav2 miss recovered" in src
    assert "dock_bench.py" in src


def test_pallet_legs_are_the_existing_bench():
    want = {
        "attach": ["attach"], "lift": ["lift"],
        "lower": ["lower"], "detach": ["detach"],
    }
    for step in cy.plan_cycle():
        if step["leg"] in want:
            assert step["tool"] == "pallet_bench.py"
            assert step["argv"] == want[step["leg"]]


def test_carry_is_cmd_vel_up_the_aisle():
    carries = [s for s in cy.plan_cycle() if s["leg"] == "carry"]
    assert len(carries) == 1
    assert carries[0]["tool"] == "burst"


def test_undock_is_cmd_vel_burst_not_undock_robot():
    undocks = [s for s in cy.plan_cycle() if s["leg"] == "undock"]
    assert len(undocks) == 2
    for step in undocks:
        assert step["tool"] == "burst"
        assert "undock" not in step["argv"]


def test_cycle_never_edits_the_world_or_teleports():
    src = open(cy.__file__, encoding="utf-8").read()
    assert "warehouse_ver3" not in src
    assert "set_pose" not in src
    assert "UndockRobot" not in src
    assert "topics.cmd_vel" in src
    assert os.path.isfile(os.path.join(_M5V3, "tools", "pallet_cycle.py"))


def test_default_repeat_is_three():
    assert cy.DEFAULT_REPEAT == 3


def test_burst_speed_is_the_dock_minimum_not_the_deadband():
    src = open(cy.__file__, encoding="utf-8").read()
    assert "dock.v_linear_min" in src
    assert "creep_speed_mps" not in src
