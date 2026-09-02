"""nav2_envelope.py - the one number nav2 is CONFIGURED to drive at.

WHY THIS FILE EXISTS, MEASURED. m6_ver2/logs/run3-speed-limit-latch:
the adapter published `SpeedLimit 1.5` (V_Limit 1500 mm/s, absolute) on
a controller whose configured ceiling was 0.300 m/s. `setSpeedLimit`
REPLACES a controller's maximum rather than intersecting with it, so the
message WIDENED nav2 by a factor of five and the next `/f1/cmd_vel` row
carried -1.5. A permission is a permission to go SLOWER; it may narrow
the envelope and it may never widen it, and the only way to write that
down is to know what the envelope IS.

THE ENVELOPE HAS ONE HOME AND IT IS nav2's OWN PARAMS FILE. The number
is not repeated in config.yaml, because a ceiling spelled in two files
is two ceilings and the first one edited is the one that is right.
"""
import os

import pytest

import _donors

import nav2_envelope


F1_PARAMS = os.path.join(_donors.REPO, "m6_ver2", "vehicles", "f1",
                         "nav2.yaml")


def params(**controllers):
    """A minimal nav2 params document, wrapped under a vid like the real one."""
    block = {"controller_plugins": sorted(controllers)}
    block.update(controllers)
    return {"f1": {"controller_server": {"ros__parameters": block}}}


# ----------------------------------------------------------------------
# the derived file, read as it stands
# ----------------------------------------------------------------------
def test_the_envelope_is_the_derived_nav2_yamls_own_number():
    assert nav2_envelope.envelope_max_mps_of(F1_PARAMS) == 0.300


def test_every_configured_controller_is_named_beside_its_ceiling():
    # NAMED, because a single float is unarguable and undebuggable: when
    # the envelope moves, the operator has to be able to see WHICH
    # controller moved it.
    ceilings = nav2_envelope.controller_ceilings(
        nav2_envelope.read_params(F1_PARAMS))
    assert ceilings == {"FollowPath": 0.300, "FollowPathRPP": 0.300}


def test_the_two_controllers_spell_the_same_ceiling_two_ways():
    # MPPI carries `vx_max`; RPP carries one magnitude in
    # `desired_linear_vel` and applies the sign afterwards. Both are the
    # same statement about the vehicle.
    doc = nav2_envelope.read_params(F1_PARAMS)
    block = nav2_envelope.controller_params(doc)
    assert block["FollowPath"]["vx_max"] == 0.300
    assert block["FollowPathRPP"]["desired_linear_vel"] == 0.300


# ----------------------------------------------------------------------
# the rule: the LOWEST ceiling wins
# ----------------------------------------------------------------------
def test_the_lowest_controller_ceiling_is_the_envelope():
    # A SpeedLimit REPLACES the ceiling of whichever controller is
    # active, so a message sized for the fastest one would widen the
    # slowest one the moment the tree switched. The min is the only
    # figure that narrows both.
    doc = params(FollowPath={"vx_max": 0.300},
                 FollowPathRPP={"desired_linear_vel": 0.100})
    assert nav2_envelope.envelope_max_mps(doc) == 0.100
    assert nav2_envelope.controller_ceilings(doc) == {
        "FollowPath": 0.300, "FollowPathRPP": 0.100}


def test_vx_min_is_not_the_envelope():
    # An ASYMMETRIC envelope's reverse end is a planner permission, not
    # a ceiling on the forward one; shrinking the whole truck to a creep
    # astern would be a limit nobody chose.
    doc = params(FollowPath={"vx_max": 0.300, "vx_min": -0.050})
    assert nav2_envelope.envelope_max_mps(doc) == 0.300


def test_a_ceiling_is_a_magnitude():
    doc = params(FollowPathRPP={"desired_linear_vel": -0.250})
    assert nav2_envelope.envelope_max_mps(doc) == 0.250


# ----------------------------------------------------------------------
# what it refuses, and it refuses BY NAME
# ----------------------------------------------------------------------
def test_a_controller_with_no_envelope_key_is_refused_by_name():
    doc = params(FollowPath={"vx_max": 0.300}, FollowPathDWB={"foo": 1})
    with pytest.raises(nav2_envelope.Nav2EnvelopeError) as caught:
        nav2_envelope.envelope_max_mps(doc)
    assert "FollowPathDWB" in str(caught.value)
    assert "vx_max" in str(caught.value)


def test_a_controller_named_in_the_plugin_list_but_absent_is_refused():
    doc = {"f1": {"controller_server": {"ros__parameters": {
        "controller_plugins": ["FollowPath"]}}}}
    with pytest.raises(nav2_envelope.Nav2EnvelopeError) as caught:
        nav2_envelope.envelope_max_mps(doc)
    assert "FollowPath" in str(caught.value)


def test_a_params_file_with_no_controller_server_is_refused():
    with pytest.raises(nav2_envelope.Nav2EnvelopeError) as caught:
        nav2_envelope.envelope_max_mps({"f1": {"planner_server": {}}})
    assert "controller_server" in str(caught.value)


def test_an_empty_plugin_list_is_refused():
    doc = {"f1": {"controller_server": {"ros__parameters": {
        "controller_plugins": []}}}}
    with pytest.raises(nav2_envelope.Nav2EnvelopeError) as caught:
        nav2_envelope.envelope_max_mps(doc)
    assert "controller_plugins" in str(caught.value)


def test_a_missing_params_file_is_refused_by_path():
    path = os.path.join(_donors.REPO, "m6_ver2", "vehicles", "f1",
                        "no-such-nav2.yaml")
    with pytest.raises(nav2_envelope.Nav2EnvelopeError) as caught:
        nav2_envelope.read_params(path)
    assert "no-such-nav2.yaml" in str(caught.value)
    assert "instantiate_truck" in str(caught.value)


# ----------------------------------------------------------------------
# the read is done once
# ----------------------------------------------------------------------
def test_the_file_is_parsed_once_per_process():
    # 136 kB of commented YAML per Adapter() would be paid by every
    # test in the shell suite and by nothing at run time: the file is a
    # gitignored BUILD PRODUCT that cannot change under a live node.
    first = nav2_envelope.read_params(F1_PARAMS)
    assert nav2_envelope.read_params(F1_PARAMS) is first


def test_the_selftest_is_green():
    assert nav2_envelope._selftest() == 0
