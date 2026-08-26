"""The two localisers, as the four questions a downstream instrument has
to answer about a `loc=` label before it can do anything - F3 Task 3.

WHY THERE IS A FOURTH TABLE-SHAPED TEST FILE ON THIS TRACK. F2 Task 4 put
a second ESTIMATOR on the stack and `evidence_core.fused_topic_key()` is
what stopped a recorder subscribing to the wrong arm's address and writing
an EMPTY stream under a label naming the estimator that was publishing all
along (tests/test_fuse_arm.py). F3 Task 3 puts a second LOCALISER on it,
and the same failure has three more shapes:

  the POSE TOPIC. nav2_amcl advertises `amcl_pose`, slam_toolbox's
      localisation node advertises `pose`. Subscribe to the wrong one and
      nothing fails - the CSV is simply empty.
  the ARTIFACT the label's md5 is of. AMCL localises in the GRID, whose
      hash the committed registration carries; slam_toolbox deserialises
      the POSE GRAPH, whose hash is in the build manifest beside it.
      Check the wrong one and a session is bound to a file it never
      opened.
  the SEED MECHANISM. amcl is told where it is by a MESSAGE the bringup
      gate publishes; slam_toolbox by a PARAMETER on its own command
      line. Publish one to the second and the gate's own pose check
      becomes a check on the gate.
  what the GATE CAN READ AT REST, which is a MEASUREMENT
      (EVIDENCE_LOCALIZATION_V3.md 13.2): amcl publishes one pose per
      seed with the truck standing still, and slam_toolbox publishes
      none at all because its pose topic is travel-gated.

EVERY ONE OF THEM REFUSES AN ARM IT HAS NOT HEARD OF, and that is the
property these tests exist for: a `.get()` with a fallback would put each
of those four failures one layer down, where no refusal can see it.

NO ROS AND NO GAZEBO: this reaches evidence_core, which imports neither.
"""
import pytest

import evidence_core as core
import map_core
import map_register


ARMS = ("amcl", "slam")
TABLES = (core.loc_pose_topic_key, core.loc_md5_artifact,
          core.loc_seed_mechanism, core.loc_gate_source)


# ----------------------------------------------------------------------
# the grammar
# ----------------------------------------------------------------------

def test_the_localiser_half_is_the_part_before_the_at_sign():
    assert core.localizer_of("amcl@735cdbc6") == "amcl"
    assert core.localizer_of("slam@4bb88852") == "slam"


def test_none_and_empty_both_name_no_localiser():
    assert core.localizer_of("none") == ""
    assert core.localizer_of("") == ""
    assert core.localizer_of("  ") == ""


def test_the_md5_half_is_the_part_after_it():
    assert core.loc_md5_of("slam@4bb88852") == "4bb88852"
    assert core.loc_md5_of("none") == ""


def test_a_rebuilt_map_changes_the_md5_and_not_the_grammar():
    # The label is PARSED and never looked up, so a rebuild - which
    # changes eight characters and nothing else - needs no table entry.
    assert core.localizer_of("slam@0badc0de") == "slam"
    assert core.loc_md5_of("slam@0badc0de") == "0badc0de"


# ----------------------------------------------------------------------
# where each arm publishes its own pose
# ----------------------------------------------------------------------

def test_the_two_arms_do_not_publish_their_pose_at_the_same_address():
    assert core.loc_pose_topic_key("amcl") == "topics.amcl_pose"
    assert core.loc_pose_topic_key("slam") == "topics.slam_pose"
    assert core.loc_pose_topic_key("amcl") != core.loc_pose_topic_key("slam")


def test_it_returns_a_CONFIG_KEY_and_never_a_topic():
    # evidence_core reads no config.yaml. The caller has the loaded
    # config and this module has the mapping, which is the split every
    # other function here is under.
    for arm in ARMS:
        assert core.loc_pose_topic_key(arm).startswith("topics.")


# ----------------------------------------------------------------------
# which frozen artifact each arm's md5 belongs to
# ----------------------------------------------------------------------

def test_amcl_binds_to_the_grid_and_slam_to_the_pose_graph():
    assert core.loc_md5_artifact("amcl") == "grid"
    assert core.loc_md5_artifact("slam") == "posegraph"


def test_the_two_artifacts_are_different_files_out_of_one_build():
    # If these were the same, F3 constraint 16 would be enforced on the
    # slam arm by hashing a file that arm never opens.
    assert core.loc_md5_artifact("amcl") != core.loc_md5_artifact("slam")


def test_the_posegraph_name_is_the_file_suffix_the_manifest_uses():
    # tools/sensor_evidence.py builds `md5_<map.name>.<artifact>` out of
    # this value and looks it up in build.txt, so the string is not free.
    assert core.loc_md5_artifact("slam") == "posegraph"


# ----------------------------------------------------------------------
# how each arm is told where it starts
# ----------------------------------------------------------------------

def test_amcl_is_seeded_by_a_message_and_slam_by_a_parameter():
    assert core.loc_seed_mechanism("amcl") == "message"
    assert core.loc_seed_mechanism("slam") == "parameter"


def test_only_one_arm_may_be_sent_a_seed_by_the_gate():
    sent = [arm for arm in ARMS
            if core.loc_seed_mechanism(arm) == "message"]
    assert sent == ["amcl"]


# ----------------------------------------------------------------------
# what the bringup gate can read with the truck standing still
# ----------------------------------------------------------------------

def test_the_gate_reads_a_pose_on_one_arm_and_the_tf_edge_on_the_other():
    assert core.loc_gate_source("amcl") == "pose"
    assert core.loc_gate_source("slam") == "edge"


def test_an_arm_seeded_by_parameter_is_never_gated_on_a_seeded_pose():
    # The two properties are independent tables and this is the pairing
    # that would be a contradiction: a gate that read the pose topic on
    # an arm it may not seed would be waiting for a publication only a
    # seed can force.
    for arm in ARMS:
        if core.loc_seed_mechanism(arm) == "parameter":
            assert core.loc_gate_source(arm) == "edge"


# ----------------------------------------------------------------------
# and every one of them refuses rather than defaults
# ----------------------------------------------------------------------

@pytest.mark.parametrize("table", TABLES)
def test_an_unknown_localiser_is_REFUSED_by_every_table(table):
    with pytest.raises(core.EvidenceError):
        table("cartographer")


@pytest.mark.parametrize("table", TABLES)
def test_an_EMPTY_localiser_is_refused_and_not_treated_as_a_default(table):
    # `none` parses to "" through localizer_of(), and "" reaching one of
    # these is a caller that did not check whether the stack was
    # localised at all. Guessing here would answer a question nobody
    # asked.
    with pytest.raises(core.EvidenceError):
        table("")


@pytest.mark.parametrize("table", TABLES)
def test_the_refusal_names_the_arms_that_ARE_known(table):
    with pytest.raises(core.EvidenceError) as caught:
        table("cartographer")
    text = str(caught.value)
    for arm in ARMS:
        assert repr(arm) in text


@pytest.mark.parametrize("table", TABLES)
def test_the_label_is_stripped_before_it_is_looked_up(table):
    assert table(" slam ") == table("slam")


@pytest.mark.parametrize("table", TABLES)
def test_every_table_answers_for_every_arm(table):
    # THE MAINTENANCE OBLIGATION, AS A TEST. An arm added to m5v3.sh is
    # an entry added to all four tables; this is what fails when it is
    # added to three.
    for arm in ARMS:
        assert table(arm)


# ----------------------------------------------------------------------
# a covariance already in hand
# ----------------------------------------------------------------------

def test_thirty_six_zeros_are_ABSENT_and_not_certain():
    assert core.covariance_absent_in([0.0] * 36) is True


def test_a_real_covariance_is_not_absent():
    # The three entries slam_toolbox actually published on this rig.
    values = [0.0] * 36
    values[0], values[1] = 0.03288176843005891, 0.0068160327941534935
    values[7] = 0.005630846288377603
    assert core.covariance_absent_in(values) is False
    assert core.worst_of(values) == pytest.approx(0.03288176843005891)


def test_an_EMPTY_covariance_is_a_refusal_and_never_an_absent_one():
    # "no numbers, so the worst is 0, so there is nothing to check" is
    # the failure worst_of() exists to refuse, and this delegates to it
    # rather than answering True.
    with pytest.raises(core.EvidenceError):
        core.covariance_absent_in([])


# ----------------------------------------------------------------------
# the build manifest, which is where the slam arm's md5 is committed
# ----------------------------------------------------------------------
#
# THE REGISTRATION CANNOT CARRY IT AND THAT IS NOT AN OVERSIGHT.
# registration.yaml states the md5 of the .pgm it was FITTED to and of
# the .yaml a grid's consumer reads; the .posegraph and .data are neither,
# and nav2_amcl never opens them. build.txt is what tools/build_map.sh
# wrote when it saved all four artifacts out of one run, so it is the only
# file that says the graph the slam arm localises in and the grid the
# registration belongs to came from the same build.


def _manifest(tmp_path, text):
    path = tmp_path / "build.txt"
    path.write_text(text, encoding="utf-8")
    return str(path)


_GOOD = (
    "# built by tools/build_map.sh on 2026-08-26T18:20:34Z\n"
    "name: warehouse_v3\n"
    "session: m5_ver3/logs/evidence/drive-mapping-20260826-174815\n"
    "md5_warehouse_v3.pgm: 735cdbc68cfde4971e03f509347839d6\n"
    "md5_warehouse_v3.posegraph: 4bb88852b2f176ff90f812cbb9f2c176\n"
    "md5_warehouse_v3.data: e2d3c013b4a31d4158f1ed40f4565fd5\n")


def test_the_manifest_reads_back_as_key_and_value(tmp_path):
    got = map_register.load_build_manifest(_manifest(tmp_path, _GOOD))
    assert got["name"] == "warehouse_v3"
    assert got["md5_warehouse_v3.posegraph"].startswith("4bb88852")


def test_comments_and_blank_lines_are_not_entries(tmp_path):
    got = map_register.load_build_manifest(
        _manifest(tmp_path, "\n# a comment: with a colon in it\n"
                            "name: warehouse_v3\n\n"))
    assert list(got) == ["name"]


def test_the_key_the_slam_arm_looks_up_is_built_from_the_artifact_name(
        tmp_path):
    # tools/sensor_evidence.py spells it `md5_<map.name>.<artifact>` and
    # m5v3.sh greps the same line out of the same file, so the artifact
    # name in evidence_core is load-bearing on both sides.
    got = map_register.load_build_manifest(_manifest(tmp_path, _GOOD))
    key = "md5_{}.{}".format("warehouse_v3", core.loc_md5_artifact("slam"))
    assert key in got


def test_a_file_that_is_not_a_manifest_is_REFUSED_by_name(tmp_path):
    # A directory with a build.txt-shaped hole in it is not a map
    # artifact, and the slam arm reads NOTHING else that could catch it:
    # nav2_amcl localises in the grid, and this one never opens the grid.
    with pytest.raises(map_core.MapError):
        map_register.load_build_manifest(
            _manifest(tmp_path, "session: somewhere\nplay_rate: 0.5\n"))
