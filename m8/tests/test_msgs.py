"""The ROS .msg files exist and name the A0 contract. They are not built."""
from pathlib import Path

_MSGS = Path(__file__).resolve().parents[1] / "m8_msgs"


def test_the_three_planned_msg_files_are_present():
    for name in ("Proposal.msg", "Verdict.msg", "SlotState.msg"):
        path = _MSGS / name
        assert path.is_file(), path


def test_proposal_msg_names_every_kind_and_the_r2_sensor():
    text = (_MSGS / "Proposal.msg").read_text(encoding="utf-8")
    for kind in ("DOCK_TARGET_REFINE", "DOCK_ABORT", "SLOT_STATE",
                 "LOAD_ID", "ANOMALY", "SPEED_REDUCE"):
        assert kind in text, kind
    assert "pallet_cam" in text
    assert "ttl_ms" in text
    assert "leg_id" in text
    assert "proceed" in text.lower()  # the prohibition is written down


def test_verdict_msg_is_accept_or_refuse():
    text = (_MSGS / "Verdict.msg").read_text(encoding="utf-8")
    assert "bool accepted" in text
    assert "string reason" in text
