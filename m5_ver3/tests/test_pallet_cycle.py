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
