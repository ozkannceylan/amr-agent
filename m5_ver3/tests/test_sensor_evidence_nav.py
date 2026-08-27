"""The nav-arm label, as pure logic - F4 Task 2.

WHY THERE IS A FOURTH LABEL AND A FOURTH TEST FILE. `traction` says
which PLANT a run was taken on, `arm` which ESTIMATOR of the vehicle's
own motion was on it, `loc` whether anything at all knew where that
vehicle WAS - and this one says whether anything was DECIDING WHERE IT
WENT. The four are independent, every combination is a legitimate run,
and a set of sessions has to be uniform in all four before it may be
read out into one document.

IT IS THE ONE THAT CHANGES WHAT THE RUN *IS* RATHER THAN WHAT IT IS
MEASURED WITH. A `nav=off` session was driven by a table in config.yaml
with nothing on the stack reading a pose. A `nav=on@...` session was
driven by a CONTROLLER CLOSING A LOOP on the localiser's own output - so
every figure about the estimate has a feedback path through the quantity
being reported. The topics are the same, the CSV columns are the same,
and there is nothing else anywhere that says which.

AND IT CARRIES nav2.yaml's md5 FOR THE MAP LABEL's REASON. That file
decides every planned arc and every followed one; two runs against two
versions of it are two experiments, and eight characters is what refuses
to table them together.

NO ROS AND NO GAZEBO: sensor_evidence.py keeps its rclpy import inside
record()'s own body, so importing it here reaches the reductions and
nothing else.
"""
import pytest

import sensor_evidence


# ----------------------------------------------------------------------
# what a session says about the planner that drove it
# ----------------------------------------------------------------------

def test_a_planned_session_reads_back_with_its_params_md5():
    assert sensor_evidence.nav_of({"nav": "on@1f2e3d4c"}) == "on@1f2e3d4c"


def test_an_unplanned_session_reads_back_as_off_and_that_is_a_value():
    assert sensor_evidence.nav_of({"nav": "off"}) == "off"


def test_a_session_with_NO_nav_line_is_not_read_as_unplanned():
    # Every session recorded before F4 Task 2 had no planner on it -
    # --nav did not exist - and this must STILL not say `off`. The label
    # is worth something only because it was read off the running stack;
    # inferring it from an absence is the habit the whole chain guards
    # against, and it is the other three labels' own rule.
    label = sensor_evidence.nav_of({"kind": "drive", "profile": "straight",
                                    "traction": "nominal",
                                    "arm": "wheel+imu",
                                    "loc": "amcl@735cdbc6"})
    assert label == sensor_evidence.UNLABELLED_NAV
    assert "off" not in label


def test_an_unlabelled_session_and_an_unplanned_one_are_DIFFERENT():
    assert sensor_evidence.nav_of({}) != sensor_evidence.nav_of({"nav": "off"})


def test_two_nav2_yamls_are_two_labels():
    # THE POINT OF THE md5 HALF. nav2.yaml is where the turning radius,
    # the footprint padding, the inflation and every critic weight are
    # decided; two runs against two versions of it are two measurements
    # and may not share a table.
    assert sensor_evidence.nav_of({"nav": "on@1f2e3d4c"}) \
        != sensor_evidence.nav_of({"nav": "on@0badc0de"})


def test_the_nav_is_read_from_its_OWN_key_and_not_from_the_loc_one():
    session = {"traction": "slippery", "slip_compliance_lateral": "0.5",
               "slip_compliance_longitudinal": "0.5",
               "arm": "wheel+imu+rf2o", "loc": "amcl@735cdbc6",
               "nav": "on@1f2e3d4c"}
    assert sensor_evidence.nav_of(session) == "on@1f2e3d4c"
    assert sensor_evidence.loc_of(session) == "amcl@735cdbc6"
    assert sensor_evidence.arm_of(session) == "wheel+imu+rf2o"
    assert sensor_evidence.traction_of(session).startswith("slippery")


# ----------------------------------------------------------------------
# one analyse, one nav arm
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
         "slip_compliance_longitudinal": "7.0", "arm": "wheel+imu",
         "loc": "amcl@735cdbc6"}
_PLANNED = dict(_BASE, nav="on@1f2e3d4c")
_TABLED = dict(_BASE, nav="off")
_RETUNED = dict(_BASE, nav="on@0badc0de")


def test_a_set_that_is_all_planned_is_not_refused():
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_nav(
        cfg, ["a", "b", "c"], [_PLANNED, _PLANNED, _PLANNED])
    assert cfg.lines == []


def test_one_session_is_never_a_mixed_set():
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_nav(cfg, ["a"], [_PLANNED])
    assert cfg.lines == []


def test_a_planned_run_beside_a_table_driven_one_is_REFUSED():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_nav(cfg, ["a", "b"],
                                         [_PLANNED, _TABLED])
    assert "nav arm" in cfg.lines[0]


def test_two_DIFFERENT_nav2_yamls_are_refused_even_though_both_are_on():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_nav(cfg, ["a", "b"],
                                         [_PLANNED, _RETUNED])
    assert any("0badc0de" in line for line in cfg.lines)
    assert any("1f2e3d4c" in line for line in cfg.lines)


def test_the_refusal_names_EVERY_session_on_BOTH_sides():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_nav(
            cfg, ["/e/one", "/e/two", "/e/three"],
            [_PLANNED, _TABLED, _PLANNED])
    text = "\n".join(cfg.lines)
    for name in ("one", "two", "three"):
        assert name in text


def test_an_UNLABELLED_session_beside_a_labelled_one_is_also_refused():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_nav(cfg, ["a", "b"], [_BASE, _TABLED])


def test_a_set_uniform_in_the_OTHER_THREE_can_still_be_mixed_in_NAV():
    # THE FOUR QUESTIONS ARE INDEPENDENT AND THERE ARE FOUR REFUSALS.
    # This set is all-nominal, all wheel+imu and all localised against
    # ONE grid; nothing but the fourth check can see what is wrong with
    # it - and what is wrong with it is that half of it was driven by a
    # controller closing a loop on that grid.
    cfg = _Cfg()
    paths, sessions = ["a", "b"], [_PLANNED, _TABLED]
    sensor_evidence.refuse_mixed_traction(cfg, paths, sessions)
    sensor_evidence.refuse_mixed_arm(cfg, paths, sessions)
    sensor_evidence.refuse_mixed_loc(cfg, paths, sessions)
    assert cfg.lines == []
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_nav(cfg, paths, sessions)


def test_the_refusal_prints_a_command_per_group():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_nav(cfg, ["/e/one", "/e/two"],
                                         [_PLANNED, _TABLED])
    text = "\n".join(cfg.lines)
    assert text.count("sensor_evidence.py analyse") == 2


# ----------------------------------------------------------------------
# and the OTHER direction: the label reaches the recorder's own refusal
# ----------------------------------------------------------------------

def test_the_recorder_REFUSES_a_state_file_with_no_nav_line():
    # BOTH DIRECTIONS, WHICH IS THE HALF THAT ROTS. The tests above
    # prove `analyse` refuses a mixed set; this proves `record` refuses
    # to write a session that could BECOME one. read_traction() is the
    # only place that can still say nothing has been recorded.
    class _RecCfg(_Cfg):
        def s(self, dotted):
            return {"paths.traction_file": "m5_ver3/.m5v3_traction"}[dotted]

    import os

    import _common

    state = ("traction=nominal\nslip_compliance_lateral=7.0\n"
             "slip_compliance_longitudinal=7.0\nwheels=a b c\n"
             "arm=wheel+imu\nloc=amcl@735cdbc6\n")
    path = os.path.join(_common.REPO, "m5_ver3", ".m5v3_traction_navtest")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(state)
    try:
        class _P(_RecCfg):
            def s(self, dotted):
                return {"paths.traction_file":
                        os.path.relpath(path, _common.REPO)}[dotted]

        cfg = _P()
        with pytest.raises(_Cfg.Refused):
            sensor_evidence.read_traction(cfg)
        assert "nav" in "\n".join(cfg.lines)
    finally:
        os.remove(path)


def test_the_recorder_ACCEPTS_a_state_file_that_carries_every_label():
    import os

    import _common

    state = ("traction=nominal\nslip_compliance_lateral=7.0\n"
             "slip_compliance_longitudinal=7.0\nwheels=a b c\n"
             "arm=wheel+imu\nloc=amcl@735cdbc6\nnav=on@1f2e3d4c\n")
    path = os.path.join(_common.REPO, "m5_ver3", ".m5v3_traction_navtest2")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(state)
    try:
        class _P(_Cfg):
            def s(self, dotted):
                return {"paths.traction_file":
                        os.path.relpath(path, _common.REPO)}[dotted]

        cfg = _P()
        fields = sensor_evidence.read_traction(cfg)
        assert fields["nav"] == "on@1f2e3d4c"
        assert cfg.lines == []
    finally:
        os.remove(path)
