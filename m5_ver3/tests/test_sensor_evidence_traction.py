"""The traction label, as pure logic - F2 Task 2.

WHY THIS FILE EXISTS AND WHY IT IS NOT IN test_evidence_core.py. The
arithmetic of this track lives in tools/evidence_core.py and is tested
next door; this is the small amount of LOGIC that had to live in
tools/sensor_evidence.py because it is about a SESSION rather than about
numbers - which plant a recording was taken on, and whether two
recordings may be read out into one document.

IT IS TESTED FOR ONE REASON. `m5v3.sh start --slippery` brings up a truck
whose wheel odometry is wrong in a completely different way, on the same
floor, from the same model file, driving the same profiles, writing CSVs
of the same shape into a directory of the same name. Nothing downstream
of `session.txt` can tell one from the other. So the two functions that
read that file are the whole guard, and the failure they exist to prevent
- a slippery run sitting in the no-slip tables looking like one of them -
is silent, permanent and unfalsifiable after the fact.

NO ROS AND NO GAZEBO, exactly like the rest of this suite:
sensor_evidence.py keeps its rclpy import inside record()'s own body, so
importing it here reaches the reductions and nothing else.
"""
import pytest

import sensor_evidence


# ----------------------------------------------------------------------
# what a session says it was taken on
# ----------------------------------------------------------------------

def test_a_nominal_session_reads_as_nominal_with_its_compliances():
    label = sensor_evidence.traction_of({
        "traction": "nominal",
        "slip_compliance_lateral": "7.0",
        "slip_compliance_longitudinal": "7.0"})
    assert label == "nominal (slip compliance 7.0 / 7.0)"


def test_a_slippery_session_reads_as_slippery_and_not_as_nominal():
    label = sensor_evidence.traction_of({
        "traction": "slippery",
        "slip_compliance_lateral": "16.0",
        "slip_compliance_longitudinal": "16.0"})
    assert label.startswith("slippery")
    assert "16.0 / 16.0" in label


def test_the_COMPLIANCES_are_part_of_the_label_and_not_decoration():
    # Two slippery runs at different compliances are two different
    # plants. A label that said only "slippery" would let them into one
    # table, and the whole point of §8.2's ladder is that 12.0 and 16.0
    # are 3.19 % and 6.18 % of slip - not the same floor.
    a = sensor_evidence.traction_of({"traction": "slippery",
                                     "slip_compliance_lateral": "12.0",
                                     "slip_compliance_longitudinal": "12.0"})
    b = sensor_evidence.traction_of({"traction": "slippery",
                                     "slip_compliance_lateral": "16.0",
                                     "slip_compliance_longitudinal": "16.0"})
    assert a != b


def test_a_session_with_NO_label_is_not_read_as_nominal():
    # Every session recorded before F2 Task 2 was in fact nominal -
    # --slippery did not exist - and this must STILL not say so. The
    # label is worth something only because it was read off the plant;
    # inferring it from an absence is exactly the habit it guards
    # against.
    label = sensor_evidence.traction_of({"kind": "drive",
                                         "profile": "straight"})
    assert label == sensor_evidence.UNLABELLED
    assert "nominal" not in label


def test_an_unlabelled_session_and_a_nominal_one_are_DIFFERENT_plants():
    old = sensor_evidence.traction_of({})
    new = sensor_evidence.traction_of({"traction": "nominal",
                                       "slip_compliance_lateral": "7.0",
                                       "slip_compliance_longitudinal": "7.0"})
    assert old != new


# ----------------------------------------------------------------------
# one analyse, one plant
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


_NOMINAL = {"traction": "nominal", "slip_compliance_lateral": "7.0",
            "slip_compliance_longitudinal": "7.0"}
_SLIPPERY = {"traction": "slippery", "slip_compliance_lateral": "16.0",
             "slip_compliance_longitudinal": "16.0"}


def test_a_set_that_is_all_one_plant_is_not_refused():
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_traction(
        cfg, ["a", "b", "c"], [_NOMINAL, _NOMINAL, _NOMINAL])
    assert cfg.lines == []


def test_one_session_is_never_a_mixed_set():
    cfg = _Cfg()
    sensor_evidence.refuse_mixed_traction(cfg, ["a"], [_SLIPPERY])
    assert cfg.lines == []


def test_a_set_mixing_the_two_plants_is_REFUSED():
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_traction(
            cfg, ["dry-1", "wet-1"], [_NOMINAL, _SLIPPERY])


def test_the_refusal_names_EVERY_session_on_BOTH_sides():
    # A refusal that said only "these are mixed" would leave the operator
    # to sort forty session directories by hand.
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_traction(
            cfg, ["dry-1", "wet-1", "dry-2"],
            [_NOMINAL, _SLIPPERY, _NOMINAL])
    text = "\n".join(str(line) for line in cfg.lines)
    for name in ("dry-1", "dry-2", "wet-1"):
        assert name in text
    assert "nominal" in text and "slippery" in text


def test_an_UNLABELLED_session_beside_a_labelled_one_is_also_refused():
    # The dangerous direction: a pre-F2-Task-2 session read into the same
    # document as a slippery one. It is not nominal-by-assumption and it
    # does not get to be quietly grouped with anything.
    cfg = _Cfg()
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_traction(
            cfg, ["old", "wet"], [{}, _SLIPPERY])


def test_two_slippery_sets_at_DIFFERENT_compliances_are_refused():
    cfg = _Cfg()
    other = dict(_SLIPPERY)
    other["slip_compliance_lateral"] = "20.0"
    other["slip_compliance_longitudinal"] = "20.0"
    with pytest.raises(_Cfg.Refused):
        sensor_evidence.refuse_mixed_traction(
            cfg, ["wet-16", "wet-20"], [_SLIPPERY, other])
