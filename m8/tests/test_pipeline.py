"""Shadow pipeline: proposers → Phase A gate → refuse all, log all."""
from m8_core.gate import REASON_PHASE_A_SHADOW, Gate, healthy
from m8_core.pipeline import all_refused, propose_all, shadow_tick
from m8_core.pocket import make_plane_depth
from m8_core.topics import A1_NODE_FILES, PUBLISH_TOPICS
from m8_core.wire import dumps_proposal, loads_proposal


def _clean():
    return make_plane_depth(
        48, 36, 1.20,
        pockets=((10, 16, 10, 26, 1.55),
                 (32, 38, 10, 26, 1.55)))


def test_shadow_tick_refuses_every_proposal_and_logs_each():
    gate = Gate(phase="A")
    verdicts = shadow_tick(_clean(), gate, healthy(), now_s=1.05)
    assert verdicts
    assert all_refused(verdicts)
    assert all(v.reason == REASON_PHASE_A_SHADOW for v in verdicts)
    assert len(gate.log) == len(verdicts)
    kinds = {v.proposal.kind for v in verdicts}
    assert "DOCK_TARGET_REFINE" in kinds
    assert "SLOT_STATE" in kinds
    # A clean face must not invent an abort.
    assert "DOCK_ABORT" not in kinds


def test_a_faulted_frame_still_only_logs_refusals():
    from m8_core.pocket import DepthFrame
    empty = DepthFrame(16, 12, tuple([float("nan")] * 192),
                       frame_id="x", sim_stamp=1.0)
    gate = Gate(phase="A")
    verdicts = shadow_tick(empty, gate, healthy(), now_s=1.05)
    assert all_refused(verdicts)
    assert any(v.proposal.kind == "DOCK_ABORT" for v in verdicts)
    assert all(row["accepted"] is False for row in gate.log)


def test_propose_all_round_trips_through_the_json_wire():
    for proposal in propose_all(_clean()):
        again = loads_proposal(dumps_proposal(proposal))
        assert again.kind == proposal.kind
        assert again.evidence.frame_id == proposal.evidence.frame_id


def test_a1_publish_topics_are_m8_numbers_not_images():
    for topic in PUBLISH_TOPICS:
        assert topic.startswith("/m8/")
        assert "image" not in topic
        assert "cam" not in topic
    assert set(A1_NODE_FILES) == {
        "pocket_pose_node.py", "abort_node.py", "slot_state_node.py",
        "veto_gate_node.py", "m8_health.py"}
