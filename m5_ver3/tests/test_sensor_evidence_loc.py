"""The absolute-layer label, as pure logic - F3 Task 2.

WHY THERE IS A THIRD LABEL AND A THIRD TEST FILE. `traction` says which
PLANT a run was taken on, `arm` says which ESTIMATOR of the vehicle's own
motion was on it, and `loc` says whether anything at all knew where that
vehicle WAS - and against which map. The three are independent, every
combination is a legitimate run, and a set of sessions has to be uniform
in all three before it may be read out into one document.

IT IS THE HARDEST OF THE THREE TO SEE MIXED. A slippery run in a dry
table at least reads oddly, and a wheel+imu run in an rf2o table reads as
the arm making no difference; a localised run beside an unlocalised one
produces tables that are simply MISSING a block for half the set, which
reads as a recording that went wrong rather than as two different
experiments in one document.

AND IT CARRIES THE MAP's md5 FOR A REASON THE OTHER TWO DO NOT HAVE.
Every absolute figure is a map pose carried into the building by ONE
grid's registration, and a rebuilt map has its own rotation from the
building (F3 constraint 16). A label that named only the localiser would
let two grids' scores into one table with nothing in the numbers to say
so.

NO ROS AND NO GAZEBO: sensor_evidence.py keeps its rclpy import inside
record()'s own body, so importing it here reaches the reductions and
nothing else.
"""
import pytest

import sensor_evidence


# ----------------------------------------------------------------------
# what a session says its absolute layer was
# ----------------------------------------------------------------------

def test_a_localised_session_reads_back_with_its_map():
    assert sensor_evidence.loc_of({"loc": "amcl@735cdbc6"}) \
        == "amcl@735cdbc6"


def test_an_unlocalised_session_reads_back_as_none_and_that_is_a_value():
    assert sensor_evidence.loc_of({"loc": "none"}) == "none"


def test_a_session_with_NO_loc_line_is_not_read_as_unlocalised():
    # Every session recorded before F3 Task 2 had no localiser on it -
    # --localize did not exist - and this must STILL not say `none`. The
    # label is worth something only because it was read off the running
    # stack; inferring it from an absence is the habit the whole chain
    # guards against, and it is the traction and arm labels' own rule.
    label = sensor_evidence.loc_of({"kind": "drive", "profile": "straight",
                                    "traction": "nominal",
                                    "arm": "wheel+imu"})
    assert label == sensor_evidence.UNLABELLED_LOC
    assert "none" not in label


def test_an_unlabelled_session_and_an_unlocalised_one_are_DIFFERENT():
    assert sensor_evidence.loc_of({}) != sensor_evidence.loc_of(
        {"loc": "none"})


def test_two_maps_are_two_labels_even_on_the_same_localiser():
    # THE WHOLE POINT OF THE md5 HALF. A rebuild is a new artifact with
    # its own rotation from the building; two runs against two grids are
    # two measurements and may not share a table.
    assert sensor_evidence.loc_of({"loc": "amcl@735cdbc6"}) \
        != sensor_evidence.loc_of({"loc": "amcl@0badc0de"})


def test_the_loc_is_read_from_its_OWN_key_and_not_from_the_arm_one():
    session = {"traction": "slippery", "slip_compliance_lateral": "0.5",
               "slip_compliance_longitudinal": "0.5",
               "arm": "wheel+imu+rf2o", "loc": "amcl@735cdbc6"}
    assert sensor_evidence.loc_of(session) == "amcl@735cdbc6"
    assert sensor_evidence.arm_of(session) == "wheel+imu+rf2o"
    assert sensor_evidence.traction_of(session).startswith("slippery")


# ----------------------------------------------------------------------
# the grammar the recorder parses the label with
# ----------------------------------------------------------------------

def test_the_localiser_half_is_what_decides_the_subscriptions():
    assert sensor_evidence.localizer_of("amcl@735cdbc6") == "amcl"


def test_none_names_no_localiser_and_neither_does_an_empty_label():
    # The recorder subscribes the two localisation topics only when this
    # is non-empty, because on the default stack nothing publishes on
    # either and a subscription would hold an empty writer open forever.
    assert sensor_evidence.localizer_of("none") == ""
    assert sensor_evidence.localizer_of("") == ""


def test_the_map_half_is_the_part_after_the_at_sign():
    assert sensor_evidence.map_md5_of("amcl@735cdbc6") == "735cdbc6"
    assert sensor_evidence.map_md5_of("none") == ""


def test_a_future_localiser_parses_without_this_file_being_edited():
    # F3 Task 3 puts slam_toolbox's localization mode on the same flag
    # family. The label is PARSED and not looked up, for
    # evidence_core.fused_topic_key()'s reason: a table keyed by whole
    # labels would stop working the first time a map is rebuilt.
    assert sensor_evidence.localizer_of("slamloc@735cdbc6") == "slamloc"
    assert sensor_evidence.map_md5_of("slamloc@735cdbc6") == "735cdbc6"


# ----------------------------------------------------------------------
# one analyse, one absolute layer
# ----------------------------------------------------------------------

class _Cfg(object):
    """Enough of _common.Config for the grouping check, and its refuse()
    raises instead of exiting so a test can catch it."""

    class Refused(Exception):
        pass

    def __init__(self):
        self.lines = []

    def s(self, dotted):
        return {"evidence.dir": "m5_ver3/logs/evidence"}[dotted]

    def refuse(self, check, owner, *lines):
        self.lines = [check, owner] + list(lines)
        raise _Cfg.Refused(check)


_BASE = {"traction": "nominal", "slip_compliance_lateral": "7.0",
         "slip_compliance_longitudinal": "7.0", "arm": "wheel+imu"}
_LOCALIZED = dict(_BASE, loc="amcl@735cdbc6")
_PLAIN = dict(_BASE, loc="none")
_REBUILT = dict(_BASE, loc="amcl@0badc0de")


def test_a_set_that_is_all_localised_is_not_refused():
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_loc(
        cfg, ["a", "b", "c"], [_LOCALIZED, _LOCALIZED, _LOCALIZED])
    assert cfg.lines == []


def test_one_session_is_never_a_mixed_set():
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_loc(cfg, ["a"], [_LOCALIZED])
    assert cfg.lines == []


def test_a_localised_run_beside_an_unlocalised_one_is_REFUSED():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_loc(
            cfg, ["a", "b"], [_LOCALIZED, _PLAIN])
    assert "absolute layer" in cfg.lines[0]


def test_two_DIFFERENT_MAPS_are_refused_even_on_the_same_localiser():
    # F3 constraint 16 reaching the analysis and not only the bringup.
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_loc(
            cfg, ["a", "b"], [_LOCALIZED, _REBUILT])
    assert any("0badc0de" in line for line in cfg.lines)
    assert any("735cdbc6" in line for line in cfg.lines)


def test_the_refusal_names_EVERY_session_on_BOTH_sides():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_loc(
            cfg, ["/e/one", "/e/two", "/e/three"],
            [_LOCALIZED, _PLAIN, _LOCALIZED])
    text = "\n".join(cfg.lines)
    for name in ("one", "two", "three"):
        assert name in text


def test_an_UNLABELLED_session_beside_a_labelled_one_is_also_refused():
    # A session from before this label existed is not an unlocalised
    # session - it is a session that cannot say - and the two may not be
    # tabled together on the strength of an assumption.
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_loc(cfg, ["a", "b"], [_BASE, _PLAIN])


def test_a_set_uniform_in_TRACTION_and_ARM_can_still_be_mixed_in_LOC():
    # THE THREE QUESTIONS ARE INDEPENDENT AND THERE ARE THREE REFUSALS.
    # This set is all-nominal and all-wheel+imu; nothing but the third
    # check can see what is wrong with it.
    cfg = _Cfg()
    paths, sessions = ["a", "b"], [_LOCALIZED, _PLAIN]
    sensor_evidence.refuse_mixed_traction(cfg, paths, sessions)
    sensor_evidence.refuse_mixed_arm(cfg, paths, sessions)
    assert cfg.lines == []
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_loc(cfg, paths, sessions)


def test_the_refusal_prints_a_command_per_group():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_loc(
            cfg, ["/e/one", "/e/two"], [_LOCALIZED, _PLAIN])
    text = "\n".join(cfg.lines)
    assert text.count("sensor_evidence.py analyse") == 2
