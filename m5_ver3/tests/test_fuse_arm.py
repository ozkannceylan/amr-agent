"""The factor-graph arm, as pure logic - F2 Task 4.

WHAT IS TESTED HERE AND WHY IT IS NOT IN test_sensor_evidence_arm.py.
That file is about whether a SET of sessions may be read out into one
document. This one is about the thing F2 Task 4 added underneath it: the
two arms publish their fused estimate on DIFFERENT TOPICS, so every
instrument that reads a fused estimate has to be told which arm is up
before it can subscribe to anything - the bringup gate
(tools/ekf_health.py) and the recorder (tools/sensor_evidence.py) alike.

THE FAILURE IT EXISTS TO PREVENT IS A SILENT ZERO, NOT A CRASH. Point the
gate at the wrong arm's topic and nothing is published on it at all - so
the gate times out and refuses a healthy stack, which is loud. Point the
RECORDER at the wrong one and it refuses by stream name, which is also
loud. But the day somebody makes either of them FALL BACK to the default
topic when it cannot tell, both failures become quiet: the gate passes
because a topic nobody publishes on cannot diverge, and a session records
an empty fused stream under a label saying which estimator produced it.
So the mapping refuses an arm it does not recognise rather than
defaulting, and that refusal is what most of this file tests.

THE LABEL IS A GRAMMAR AND NOT A TABLE, and that is the design being
locked here. `[<estimator>:]<channels>` - the part before the colon names
the ESTIMATOR and its absence means robot_localization, the part after
names the CHANNELS. `wheel+imu` and `wheel+imu+rf2o` are two channel sets
on one estimator; `fuse:wheel+imu` is one channel set on another. A table
keyed by whole labels would have mapped a future `fuse:wheel+imu+rf2o`
onto the EKF's topic, silently, on its first bringup.

NO ROS AND NO GAZEBO: evidence_core.py is pure arithmetic and this file
also reads two committed text files off disk, which needs neither.
"""
import os

import pytest

import evidence_core as core


M5V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


# ----------------------------------------------------------------------
# which estimator a label names
# ----------------------------------------------------------------------

def test_a_label_with_no_colon_names_the_shipping_estimator():
    assert core.estimator_of("wheel+imu") == ""


def test_the_rf2o_label_still_names_the_shipping_estimator():
    # --rf2o adds a SENSOR to robot_localization's filter; it does not
    # change the estimator, and the label's grammar has to agree or the
    # eight sessions of EVIDENCE_FUSION.md 10 would be re-pointed at a
    # topic that did not exist when they were recorded.
    assert core.estimator_of("wheel+imu+rf2o") == ""


def test_the_fuse_label_names_fuse():
    assert core.estimator_of("fuse:wheel+imu") == "fuse"


def test_the_estimator_is_the_part_before_the_FIRST_colon():
    assert core.estimator_of("fuse:wheel+imu:extra") == "fuse"


def test_surrounding_whitespace_is_not_part_of_the_label():
    # The label arrives off a `key=value` line read out of a file, and a
    # trailing space there is a truncated write's cousin, not a new arm.
    assert core.estimator_of("  fuse:wheel+imu \n") == "fuse"


# ----------------------------------------------------------------------
# which topic that estimator publishes on
# ----------------------------------------------------------------------

def test_the_default_arm_reads_the_shipping_topic():
    assert core.fused_topic_key("wheel+imu") == "topics.odometry_filtered"


def test_the_rf2o_arm_reads_the_SAME_topic_as_the_default_arm():
    # It must, and this is the whole reason the rf2o arm needed no change
    # to the recorder: it is the same filter with one more sensor, on one
    # address. EVIDENCE_FUSION.md 10.3.
    assert core.fused_topic_key("wheel+imu+rf2o") == "topics.odometry_filtered"


def test_the_fuse_arm_reads_its_own_topic():
    assert core.fused_topic_key("fuse:wheel+imu") == "topics.fuse_odometry_filtered"


def test_a_future_fuse_arm_with_more_channels_still_reads_the_fuse_topic():
    # The grammar's payoff. A table keyed by whole labels would have sent
    # this one to the EKF's topic and the failure would have been an
    # empty stream, not an error.
    assert core.fused_topic_key("fuse:wheel+imu+rf2o") == \
        "topics.fuse_odometry_filtered"


# ----------------------------------------------------------------------
# and what it does when it cannot tell
# ----------------------------------------------------------------------

def test_an_empty_arm_is_refused_and_not_defaulted():
    with pytest.raises(core.EvidenceError):
        core.fused_topic_key("")


def test_a_whitespace_only_arm_is_refused():
    with pytest.raises(core.EvidenceError):
        core.fused_topic_key("   ")


def test_an_unknown_estimator_is_refused_BY_NAME_and_not_defaulted():
    # The one that matters. A stack brought up by a future arm this
    # mapping has never heard of must stop the instrument, not hand it
    # the shipping filter's address - which is exactly what a
    # dict.get(arm, DEFAULT) would have done.
    with pytest.raises(core.EvidenceError) as excinfo:
        core.fused_topic_key("ukf:wheel+imu")
    assert "ukf" in str(excinfo.value)


def test_a_label_with_a_colon_and_no_channels_is_refused():
    with pytest.raises(core.EvidenceError):
        core.fused_topic_key("fuse:")


def test_a_label_that_is_only_a_colon_is_refused():
    with pytest.raises(core.EvidenceError):
        core.fused_topic_key(":")


def test_the_refusal_names_the_estimators_it_does_know():
    # An operator who is refused needs the list, or the refusal is a
    # riddle. tools/_common.sh's rule, in this file's currency.
    with pytest.raises(core.EvidenceError) as excinfo:
        core.fused_topic_key("ukf:wheel+imu")
    assert "fuse" in str(excinfo.value)


# ----------------------------------------------------------------------
# the state file both instruments read the label out of
# ----------------------------------------------------------------------

def test_a_state_file_parses_to_its_key_value_pairs():
    text = "traction=nominal\narm=fuse:wheel+imu\npartition=m5v3\n"
    fields = core.parse_state_file(text)
    assert fields["traction"] == "nominal"
    assert fields["arm"] == "fuse:wheel+imu"


def test_a_value_containing_an_equals_sign_survives_the_parse():
    # arm_source= carries a whole command line with `--params-file x=y`
    # shapes in it; splitting on every `=` would truncate it.
    text = "arm_source=m5v3.sh --fuse, a=b, c=d\n"
    assert core.parse_state_file(text)["arm_source"] == \
        "m5v3.sh --fuse, a=b, c=d"


def test_blank_lines_and_lines_without_an_equals_are_ignored():
    text = "\ntraction=nominal\nthis line is not a pair\n\narm=wheel+imu\n"
    fields = core.parse_state_file(text)
    assert set(fields) == {"traction", "arm"}


def test_a_later_line_wins_over_an_earlier_one_of_the_same_key():
    # m5v3.sh writes the file whole, so this cannot happen from that
    # side; it is pinned because the alternative - first-wins - would
    # make a partially rewritten file report the OLD arm, which is the
    # one direction that is dangerous.
    assert core.parse_state_file("arm=wheel+imu\narm=fuse:wheel+imu\n")["arm"] \
        == "fuse:wheel+imu"


# ----------------------------------------------------------------------
# the committed parameter file, checked the way m5v3.sh checks it
# ----------------------------------------------------------------------
#
# WHY A TEST FILE READS A YAML FILE. m5v3.sh's check_fuse_params() is the
# gate that runs on the rig, and it is a grep in a shell script that
# nothing else executes on the owner's Windows python. These four are the
# same invariants asserted where `pytest` can see them, so that an edit to
# fuse.yaml that would be refused at the next bringup is refused at the
# next test run instead - which is hours earlier and costs no GPU.

def _fuse_yaml():
    with open(os.path.join(M5V3, "fuse.yaml"), "r", encoding="utf-8") as handle:
        return handle.read()


def test_fuse_yaml_is_addressed_to_the_node_config_yaml_names():
    import yaml
    with open(os.path.join(M5V3, "config.yaml"), "r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    assert "\n{}:".format(cfg["fuse"]["node_name"]) in "\n" + _fuse_yaml()


@pytest.mark.parametrize("key", ["position_dimensions",
                                 "orientation_dimensions",
                                 "linear_acceleration_dimensions"])
def test_the_refused_dimension_lists_are_absent_from_fuse_yaml(key):
    # On this node a refusal IS an absence: fuse takes lists of dimension
    # names, an empty YAML list will not load at all (rclcpp cannot infer
    # its type), and so the key being PRESENT is the channel being fused.
    # The pose is refused by F2 global constraint 13 and the acceleration
    # by F2 Task 2's measured reversal (EVIDENCE_FUSION.md 9).
    for line in _fuse_yaml().splitlines():
        assert not line.strip().startswith(key + ":"), line


def test_fuse_yaml_carries_no_topic_and_no_frame():
    # ekf.yaml's rule, and this file lives under it: config.yaml owns
    # every name and m5v3.sh passes them as `-p` overrides, so no name
    # appears in two places. The `/` is the tell - a ROS topic here would
    # be an absolute name and a frame would be quoted beside one.
    for line in _fuse_yaml().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "/m5v3/" not in stripped, line


def test_the_process_noise_is_robot_localizations_default_projected_to_2d():
    # THE A/B's ONE CONTROLLED KNOB. ekf.yaml leaves
    # process_noise_covariance at robot_localization's shipped default on
    # purpose; fuse has no default and will not start without one, so the
    # only honest value is that same diagonal's 2D subset. If somebody
    # tunes this for the fuse arm, EVIDENCE_FUSION.md 11 stops being a
    # comparison of two estimators and becomes a comparison of one
    # estimator against one tuning effort - so it is pinned here with the
    # source's own numbers written out.
    import yaml
    with open(os.path.join(M5V3, "fuse.yaml"), "r", encoding="utf-8") as handle:
        params = yaml.safe_load(handle)["m5v3_fuse"]["ros__parameters"]
    # robot_localization's default diagonal, ordered x y z roll pitch yaw
    # vx vy vz vroll vpitch vyaw ax ay az, read off this rig's own
    # /opt/ros/jazzy/share/robot_localization/params/ekf.yaml.
    rl_default = [0.05, 0.05, 0.06, 0.03, 0.03, 0.06, 0.025, 0.025, 0.04,
                  0.01, 0.01, 0.02, 0.01, 0.01, 0.015]
    # Unicycle2D's state, ordered x y yaw vx vy vyaw ax ay.
    want = [rl_default[i] for i in (0, 1, 5, 6, 7, 11, 12, 13)]
    assert params["unicycle_motion_model"]["process_noise_diagonal"] == want
