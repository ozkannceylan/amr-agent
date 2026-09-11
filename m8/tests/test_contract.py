"""Proposal dataclass, monotone rules, TTL. No ROS."""
import math

import pytest

from m8_core.contract import (
    ABORT_REASONS,
    ContractError,
    Evidence,
    KIND_ANOMALY,
    KIND_DOCK_ABORT,
    KIND_DOCK_TARGET_REFINE,
    KIND_LOAD_ID,
    KIND_SLOT_STATE,
    KIND_SPEED_REDUCE,
    LoadEntry,
    PoseDelta,
    SENSOR_PALLET_CAM,
    SLOT_STATES,
    SlotRow,
    is_expired,
    is_monotone,
    make_proposal,
    monotone_violations,
    remaining_ttl_ms,
    validate_proposal,
)


def _ev(stamp=10.0, frame="frame-1"):
    return Evidence(frame_id=frame, sim_stamp=stamp,
                    sensor_name=SENSOR_PALLET_CAM)


def _refine(dx=0.04, dy=0.02, dtheta=0.01, stamp=10.0, ttl=200, conf=0.9):
    return make_proposal(
        KIND_DOCK_TARGET_REFINE, PoseDelta(dx, dy, dtheta),
        conf, _ev(stamp), ttl)


def _abort(reason="pallet_absent", stamp=10.0, ttl=200):
    return make_proposal(KIND_DOCK_ABORT, reason, 0.95, _ev(stamp), ttl)


def _speed(ceiling=0.4, leg="leg-1", stamp=10.0, ttl=200):
    return make_proposal(
        KIND_SPEED_REDUCE, ceiling, 0.8, _ev(stamp), ttl, leg_id=leg)


def test_a_well_formed_refine_validates():
    p = _refine()
    validate_proposal(p)
    assert p.pose_delta().hypot_xy() == pytest.approx(math.hypot(0.04, 0.02))
    assert p.evidence.sensor_name == "pallet_cam"


def test_confidence_is_a_unit_interval():
    with pytest.raises(ContractError, match="confidence"):
        make_proposal(KIND_DOCK_ABORT, "pallet_absent", 1.1, _ev(), 200)
    with pytest.raises(ContractError, match="confidence"):
        make_proposal(KIND_DOCK_ABORT, "pallet_absent", -0.01, _ev(), 200)


def test_ttl_must_be_positive():
    with pytest.raises(ContractError, match="ttl_ms"):
        make_proposal(KIND_DOCK_ABORT, "pallet_absent", 0.5, _ev(), 0)


def test_unknown_kind_is_refused():
    with pytest.raises(ContractError, match="unknown kind"):
        make_proposal("PROCEED", "go", 0.5, _ev(), 200)


def test_proceed_is_never_an_output():
    # C2: proceed is never an M8 output. A reason-code sneak is the
    # same refusal as a kind named PROCEED.
    with pytest.raises(ContractError, match="proceed"):
        make_proposal(KIND_ANOMALY, "proceed", 0.5, _ev(), 200)


def test_sensor_name_is_pallet_cam_only_r2():
    ev = Evidence(frame_id="f", sim_stamp=1.0, sensor_name="os0")
    with pytest.raises(ContractError, match="pallet_cam"):
        make_proposal(KIND_DOCK_ABORT, "pallet_absent", 0.5, ev, 200)


def test_frame_id_is_required():
    ev = Evidence(frame_id="  ", sim_stamp=1.0)
    with pytest.raises(ContractError, match="frame_id"):
        make_proposal(KIND_DOCK_ABORT, "pallet_absent", 0.5, ev, 200)


def test_every_c2_abort_reason_is_accepted_and_no_others():
    for reason in ABORT_REASONS:
        make_proposal(KIND_DOCK_ABORT, reason, 0.5, _ev(), 200)
    with pytest.raises(ContractError, match="unknown abort reason"):
        make_proposal(KIND_DOCK_ABORT, "not_a_reason", 0.5, _ev(), 200)


def test_slot_table_rows_and_states():
    rows = tuple(SlotRow("S5-{}".format(i), s)
                 for i, s in enumerate(SLOT_STATES))
    p = make_proposal(KIND_SLOT_STATE, rows, 0.7, _ev(), 500)
    assert [r.state for r in p.slot_table()] == list(SLOT_STATES)
    with pytest.raises(ContractError, match="duplicate"):
        make_proposal(
            KIND_SLOT_STATE,
            (SlotRow("A", "empty"), SlotRow("A", "occupied")),
            0.7, _ev(), 500)
    with pytest.raises(ContractError, match="unknown slot state"):
        make_proposal(
            KIND_SLOT_STATE, (SlotRow("A", "full"),), 0.7, _ev(), 500)


def test_speed_reduce_requires_a_leg_and_a_positive_ceiling_r5():
    with pytest.raises(ContractError, match="leg_id"):
        make_proposal(KIND_SPEED_REDUCE, 0.4, 0.5, _ev(), 200)
    with pytest.raises(ContractError, match="zero is a stop"):
        make_proposal(KIND_SPEED_REDUCE, 0.0, 0.5, _ev(), 200, leg_id="L")
    with pytest.raises(ContractError, match="zero is a stop"):
        make_proposal(KIND_SPEED_REDUCE, -0.1, 0.5, _ev(), 200, leg_id="L")
    with pytest.raises(ContractError, match="leg_id is only valid"):
        make_proposal(
            KIND_DOCK_ABORT, "pallet_absent", 0.5, _ev(), 200, leg_id="L")


def test_load_id_and_anomaly_payloads():
    make_proposal(KIND_LOAD_ID, LoadEntry("P-1", "EUR"), 0.6, _ev(), 200)
    make_proposal(KIND_ANOMALY, "aisle_blocked", 0.6, _ev(), 200)
    with pytest.raises(ContractError, match="load_id"):
        make_proposal(KIND_LOAD_ID, LoadEntry(""), 0.6, _ev(), 200)
    with pytest.raises(ContractError, match="class name"):
        make_proposal(KIND_ANOMALY, "  ", 0.6, _ev(), 200)


def test_ttl_expires_at_the_boundary_and_never_goes_negative():
    p = _refine(stamp=10.0, ttl=200)
    assert p.expiry_stamp() == pytest.approx(10.2)
    assert is_expired(p, 10.199) is False
    assert remaining_ttl_ms(p, 10.199) >= 1
    # Equality is expired: the last instant is already stale.
    assert is_expired(p, 10.2) is True
    assert remaining_ttl_ms(p, 10.2) == 0
    assert is_expired(p, 11.0) is True
    assert remaining_ttl_ms(p, 11.0) == 0


def test_a_first_proposal_is_monotone():
    assert is_monotone(None, _refine()) is True
    assert is_monotone(None, _abort()) is True
    assert is_monotone(None, _speed()) is True


def test_a_smaller_refine_is_monotone_a_larger_one_is_not():
    first = _refine(dx=0.05, dy=0.00, dtheta=0.10)
    tighter = _refine(dx=0.02, dy=0.00, dtheta=0.05)
    looser_xy = _refine(dx=0.08, dy=0.00, dtheta=0.05)
    looser_yaw = _refine(dx=0.02, dy=0.00, dtheta=0.20)
    assert is_monotone(first, tighter) is True
    assert is_monotone(first, looser_xy) is False
    assert is_monotone(first, looser_yaw) is False
    assert monotone_violations(first, looser_xy) == ("refine_delta_grew",)


def test_a_lower_ceiling_is_monotone_a_raise_is_not():
    first = _speed(0.50, "leg-1")
    lower = _speed(0.30, "leg-1")
    raise_it = _speed(0.60, "leg-1")
    other_leg = _speed(0.90, "leg-2")
    assert is_monotone(first, lower) is True
    assert is_monotone(first, raise_it) is False
    assert monotone_violations(first, raise_it) == ("ceiling_raised",)
    # A different leg is a different proposal, not a raise of this one.
    assert is_monotone(first, other_leg) is True


def test_an_abort_is_always_a_tightening_and_is_terminal():
    refine = _refine()
    abort = _abort()
    assert is_monotone(refine, abort) is True
    assert is_monotone(abort, _refine()) is False
    assert monotone_violations(abort, _refine()) == ("abort_is_terminal",)


def test_reporting_kinds_do_not_loosen_motion():
    slots = make_proposal(
        KIND_SLOT_STATE, (SlotRow("A", "empty"),), 0.5, _ev(), 200)
    assert is_monotone(_refine(), slots) is True
    assert is_monotone(slots, _refine()) is True
