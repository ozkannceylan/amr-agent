"""Veto gate: delta box, freshness, health. Phase A refuses all and logs all."""
from m8_core.contract import (
    Evidence,
    KIND_DOCK_ABORT,
    KIND_DOCK_TARGET_REFINE,
    KIND_SLOT_STATE,
    KIND_SPEED_REDUCE,
    PoseDelta,
    SENSOR_PALLET_CAM,
    SlotRow,
    make_proposal,
)
from m8_core.gate import (
    PHASE_A,
    PHASE_C,
    REASON_EXPIRED,
    REASON_NOT_MONOTONE,
    REASON_OUTSIDE_DELTA_BOX,
    REASON_PHASE_A_SHADOW,
    REASON_STALE_FRAME,
    REASON_UNHEALTHY,
    DeltaBox,
    Gate,
    Health,
    healthy,
)


def _ev(stamp=10.0, frame="frame-1"):
    return Evidence(frame_id=frame, sim_stamp=stamp,
                    sensor_name=SENSOR_PALLET_CAM)


def _refine(dx=0.02, dy=0.01, dtheta=0.02, stamp=10.0, ttl=500):
    return make_proposal(
        KIND_DOCK_TARGET_REFINE, PoseDelta(dx, dy, dtheta),
        0.9, _ev(stamp), ttl)


def _abort(stamp=10.0, ttl=500):
    return make_proposal(
        KIND_DOCK_ABORT, "pocket_blocked", 0.95, _ev(stamp), ttl)


def _slots(stamp=10.0):
    return make_proposal(
        KIND_SLOT_STATE, (SlotRow("S5-A", "empty"),), 0.8, _ev(stamp), 500)


BOX = DeltaBox(max_dx=0.05, max_dy=0.05, max_dtheta=0.1)


def test_phase_a_refuses_a_perfect_refine_and_logs_it():
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    v = gate.evaluate(_refine(), now_s=10.05, health=healthy())
    assert v.accepted is False
    assert v.reason == REASON_PHASE_A_SHADOW
    assert v.checks["valid"] is True
    assert v.checks["fresh"] is True
    assert v.checks["healthy"] is True
    assert v.checks["monotone"] is True
    assert v.checks["inside_delta_box"] is True
    assert len(gate.log) == 1
    assert gate.log[0]["kind"] == KIND_DOCK_TARGET_REFINE
    assert gate.log[0]["evidence"]["frame_id"] == "frame-1"
    assert gate.log[0]["accepted"] is False


def test_phase_a_refuses_abort_and_slot_state_too():
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    abort = gate.evaluate(_abort(), now_s=10.05, health=healthy())
    slots = gate.evaluate(_slots(), now_s=10.06, health=healthy())
    assert abort.accepted is False and abort.reason == REASON_PHASE_A_SHADOW
    assert slots.accepted is False and slots.reason == REASON_PHASE_A_SHADOW
    assert len(gate.log) == 2


def test_every_evaluate_appends_exactly_one_log_row():
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    for i in range(5):
        gate.evaluate(_abort(stamp=10.0 + i * 0.01),
                      now_s=10.0 + i * 0.01 + 0.02,
                      health=healthy())
    assert len(gate.log) == 5
    frames = [row["evidence"]["frame_id"] for row in gate.log]
    assert frames == ["frame-1"] * 5


def test_expired_ttl_is_refused_before_the_phase_rule():
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    # ttl 200 ms from stamp 10.0 → expires at 10.2
    v = gate.evaluate(_refine(ttl=200, stamp=10.0),
                      now_s=10.25, health=healthy())
    assert v.accepted is False
    assert v.reason == REASON_EXPIRED
    assert v.checks["expired"] is True
    assert v.checks["fresh"] is False
    assert gate.log[0]["remaining_ttl_ms"] == 0


def test_a_stale_frame_is_refused_even_when_ttl_has_not_run_out():
    gate = Gate(phase=PHASE_A, delta_box=BOX, max_frame_age_ms=50.0)
    # 80 ms of age, TTL still 500 ms — the frame is the stale thing.
    v = gate.evaluate(_refine(ttl=500, stamp=10.0),
                      now_s=10.08, health=healthy(frame_age_ms=10.0))
    assert v.accepted is False
    assert v.reason == REASON_STALE_FRAME
    assert v.checks["stale_frame"] is True
    assert v.checks["expired"] is False


def test_unhealthy_is_refused_rather_than_limping():
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    cases = [
        Health(model_loaded=False, model_warm=True,
               inference_latency_p95_ms=1, frame_age_ms=1, rtf_cost=0),
        Health(model_loaded=True, model_warm=False,
               inference_latency_p95_ms=1, frame_age_ms=1, rtf_cost=0),
        healthy(inference_latency_p95_ms=999.0),
        healthy(rtf_cost=9.0),
    ]
    for snap in cases:
        v = gate.evaluate(_refine(), now_s=10.05, health=snap)
        assert v.accepted is False
        assert v.reason == REASON_UNHEALTHY
        assert v.checks["healthy"] is False
        assert v.checks["health_failures"]


def test_missing_health_is_unhealthy_not_a_pass():
    # Refuse rather than limp: a caller that forgot the snapshot does
    # not get a silent accept on a later phase.
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    v = gate.evaluate(_refine(), now_s=10.05, health=None)
    assert v.reason == REASON_UNHEALTHY
    assert "model_not_loaded" in v.checks["health_failures"]


def test_a_refine_outside_the_delta_box_is_named():
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    v = gate.evaluate(_refine(dx=0.20, dy=0.00, dtheta=0.00),
                      now_s=10.05, health=healthy())
    assert v.accepted is False
    assert v.reason == REASON_OUTSIDE_DELTA_BOX
    assert v.checks["inside_delta_box"] is False


def test_a_monotone_violation_is_named():
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    first = _refine(dx=0.02, dy=0.00, dtheta=0.02)
    grown = _refine(dx=0.04, dy=0.00, dtheta=0.02)
    v = gate.evaluate(grown, now_s=10.05, health=healthy(), previous=first)
    assert v.accepted is False
    assert v.reason == REASON_NOT_MONOTONE
    assert v.checks["monotone"] is False


def test_phase_c_would_accept_an_in_box_refine_but_a0_does_not_ship_that():
    # Pins the check order so Phase C can flip one flag. A0 production
    # gates stay on PHASE_A; this is a unit pin, not a consumer.
    later = Gate(phase=PHASE_C, delta_box=BOX)
    v = later.evaluate(_refine(), now_s=10.05, health=healthy())
    assert v.accepted is True
    assert v.reason == "accepted"

    still_a = Gate(phase=PHASE_A, delta_box=BOX)
    shadow = still_a.evaluate(_refine(), now_s=10.05, health=healthy())
    assert shadow.accepted is False
    assert shadow.reason == REASON_PHASE_A_SHADOW


def test_speed_reduce_and_abort_are_logged_in_phase_a():
    gate = Gate(phase=PHASE_A, delta_box=BOX)
    speed = make_proposal(
        KIND_SPEED_REDUCE, 0.4, 0.7, _ev(), 400, leg_id="edge-12")
    vs = gate.evaluate(speed, now_s=10.05, health=healthy())
    va = gate.evaluate(_abort(), now_s=10.06, health=healthy())
    assert vs.accepted is False and va.accepted is False
    kinds = [row["kind"] for row in gate.log]
    assert kinds == [KIND_SPEED_REDUCE, KIND_DOCK_ABORT]
    assert gate.log[0]["leg_id"] == "edge-12"
