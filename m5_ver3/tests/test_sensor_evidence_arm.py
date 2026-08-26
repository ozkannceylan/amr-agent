"""The estimator-arm label, as pure logic - F2 Task 3.

WHY THIS FILE EXISTS AND WHY IT IS NOT test_sensor_evidence_traction.py.
The two labels answer two independent questions about one run - which
PLANT it was taken on, and which ESTIMATOR was on that plant - and all
four combinations are legitimate runs that EVIDENCE_FUSION.md 10 uses
three of. Reading them out into one document requires the set to be
uniform in BOTH, so there are two labels, two refusals over one shared
mechanism, and two test files.

IT IS TESTED FOR ITS NEIGHBOUR'S REASON, ONE TURN WORSE.
`m5v3.sh start --rf2o` brings up a truck whose FUSED estimate has a third
sensor in it, on the same floor, from the same model file, driving the
same profiles, publishing on the SAME topic, writing CSVs of the same
shape into a directory of the same name. Nothing downstream of
`session.txt` can tell one from the other. And where a slippery run in a
dry table at least reads oddly, a wheel+imu run in an rf2o table reads as
*the arm making no difference* - which is one of the answers the A/B
could honestly have reached, and there would be nothing in the numbers to
say it was not the one measured.

NO ROS AND NO GAZEBO: sensor_evidence.py keeps its rclpy import inside
record()'s own body, so importing it here reaches the reductions and
nothing else.
"""
import pytest

import sensor_evidence


# ----------------------------------------------------------------------
# what a session says its estimator was
# ----------------------------------------------------------------------

def test_the_default_arm_reads_back_as_the_default_arm():
    assert sensor_evidence.arm_of({"arm": "wheel+imu"}) == "wheel+imu"


def test_the_rf2o_arm_reads_back_as_the_rf2o_arm_and_not_as_the_default():
    label = sensor_evidence.arm_of({"arm": "wheel+imu+rf2o"})
    assert label == "wheel+imu+rf2o"
    assert label != "wheel+imu"


def test_a_session_with_NO_arm_is_not_read_as_the_default_arm():
    # Every session recorded before F2 Task 3 was in fact wheel+imu -
    # --rf2o did not exist - and this must STILL not say so. The label is
    # worth something only because it was read off the running stack;
    # inferring it from an absence is exactly the habit it guards
    # against, and it is the traction label's own rule.
    label = sensor_evidence.arm_of({"kind": "drive", "profile": "straight",
                                    "traction": "nominal"})
    assert label == sensor_evidence.UNLABELLED_ARM
    assert "wheel+imu" not in label


def test_an_unlabelled_session_and_a_default_arm_one_are_DIFFERENT():
    old = sensor_evidence.arm_of({})
    new = sensor_evidence.arm_of({"arm": "wheel+imu"})
    assert old != new


def test_the_arm_is_read_from_its_OWN_key_and_not_from_the_traction_one():
    # The two labels live in one file and are written by one function.
    # A reader that fell through to the wrong key would produce a label
    # that looked plausible on every run of the default stack.
    session = {"traction": "slippery", "arm": "wheel+imu+rf2o"}
    assert sensor_evidence.arm_of(session) == "wheel+imu+rf2o"
    assert sensor_evidence.traction_of(session).startswith("slippery")


# ----------------------------------------------------------------------
# one analyse, one estimator
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


_PLAIN = {"traction": "nominal", "slip_compliance_lateral": "7.0",
          "slip_compliance_longitudinal": "7.0", "arm": "wheel+imu"}
_RF2O = {"traction": "nominal", "slip_compliance_lateral": "7.0",
         "slip_compliance_longitudinal": "7.0", "arm": "wheel+imu+rf2o"}


def test_a_set_that_is_all_one_arm_is_not_refused():
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_arm(
        cfg, ["a", "b", "c"], [_RF2O, _RF2O, _RF2O])
    assert cfg.lines == []


def test_one_session_is_never_a_mixed_set():
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_arm(cfg, ["a"], [_RF2O])
    assert cfg.lines == []


def test_a_set_mixing_the_two_arms_is_REFUSED():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_arm(
            cfg, ["plain-1", "rf2o-1"], [_PLAIN, _RF2O])


def test_the_refusal_names_EVERY_session_on_BOTH_sides():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_arm(
            cfg, ["plain-1", "rf2o-1", "plain-2"], [_PLAIN, _RF2O, _PLAIN])
    text = "\n".join(str(line) for line in cfg.lines)
    for name in ("plain-1", "plain-2", "rf2o-1"):
        assert name in text
    assert "wheel+imu" in text and "wheel+imu+rf2o" in text


def test_an_UNLABELLED_session_beside_a_labelled_one_is_also_refused():
    # The dangerous direction: EVIDENCE_FUSION.md 9.3's own eight
    # sessions carry no arm= line at all, and they are the baseline the
    # rf2o arm is measured against. Reading one of each out by one
    # command is exactly how a baseline row would end up in the new
    # table looking like a result.
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_arm(cfg, ["old", "rf2o"], [{}, _RF2O])


def test_a_set_uniform_in_TRACTION_can_still_be_mixed_in_ARM():
    # The two axes are independent, which is the whole reason there are
    # two refusals: this set passes the traction check and must not pass
    # this one.
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_traction(cfg, ["a", "b"], [_PLAIN, _RF2O])
    assert cfg.lines == []
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_arm(cfg, ["a", "b"], [_PLAIN, _RF2O])


def test_a_set_uniform_in_ARM_can_still_be_mixed_in_TRACTION():
    # And the other way round, so neither check can be deleted on the
    # grounds that the other one covers it.
    wet = dict(_RF2O)
    wet["traction"] = "slippery"
    wet["slip_compliance_lateral"] = "16.0"
    wet["slip_compliance_longitudinal"] = "16.0"
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_arm(cfg, ["a", "b"], [_RF2O, wet])
    assert cfg.lines == []
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_traction(cfg, ["a", "b"], [_RF2O, wet])


def test_the_refusal_prints_a_command_per_group():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_arm(
            cfg, ["plain-1", "rf2o-1"], [_PLAIN, _RF2O])
    text = "\n".join(str(line) for line in cfg.lines)
    # An operator who is refused needs the two commands that would have
    # worked, not just the news that they were wrong.
    assert text.count("sensor_evidence.py analyse") == 2
