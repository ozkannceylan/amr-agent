"""Every §4 transition, TTL expiry, and duplicate idempotency key.

Phase 1a: no broker. The machine is pure.
"""
import pytest
from jsonschema import Draft202012Validator

from gate.audit import AuditLog
from gate.policy import load_policy
from gate.proposal import (
    APPROVED,
    DUPLICATE,
    EXPIRED,
    FORWARD_FAILED,
    FORWARDED,
    PENDING,
    RECEIVED,
    REJECTED_HUMAN,
    REJECTED_POLICY,
    REJECTED_SCHEMA,
    TRANSITIONS,
    Gate,
    Proposal,
    build_submit_body,
    load_schema,
)


def _gate(tmp_path, now=1000.0):
    clock = {"t": now}

    def now_fn():
        return clock["t"]

    gate = Gate(
        policy=load_policy(),
        audit=AuditLog(path=tmp_path / "audit.jsonl"),
        clock=now_fn,
    )
    gate._clock_state = clock
    return gate


def _fresh(gate, **kwargs):
    defaults = dict(
        from_station="S1",
        to_station="S4",
        reason="move a pallet",
        idempotency_key="k-1",
        client_id="console-a",
        status_ts=gate.now(),
    )
    defaults.update(kwargs)
    return gate.propose(**defaults)


def test_submit_body_matches_fleet_cli_shape_and_schema():
    body = build_submit_body("S1", "S4")
    assert set(body) == {"taskId", "from", "to"}
    assert (body["from"], body["to"]) == ("S1", "S4")
    assert body["taskId"].startswith("ft-") and len(body["taskId"]) == 11
    Draft202012Validator(load_schema("submit.schema.json")).validate(body)


def test_named_task_id_is_passed_through_like_fleet_cli():
    body = build_submit_body("S1", "S4", "night-shift-7")
    assert body["taskId"] == "night-shift-7"
    Draft202012Validator(load_schema("submit.schema.json")).validate(body)


def test_illegal_transition_is_refused(tmp_path):
    proposal = Proposal(
        proposal_id="pr-dead", client_id="c", from_station="S1",
        to_station="S4", reason="", idempotency_key="k", created_ts=0.0,
    )
    with pytest.raises(ValueError, match="illegal transition"):
        proposal.transition(FORWARDED)
    proposal.transition(PENDING)
    with pytest.raises(ValueError, match="illegal transition"):
        proposal.transition(RECEIVED)


def test_received_to_pending(tmp_path):
    gate = _gate(tmp_path)
    result = _fresh(gate)
    assert result.verdict == PENDING
    assert result.proposal.state == PENDING
    assert result.proposal.history == ["RECEIVED->PENDING"]


def test_received_to_rejected_schema_missing_from(tmp_path):
    gate = _gate(tmp_path)
    result = _fresh(gate, from_station="", to_station="S4",
                    idempotency_key="k-schema")
    assert result.verdict == REJECTED_SCHEMA
    assert result.proposal.history == ["RECEIVED->REJECTED_SCHEMA"]


def test_received_to_rejected_schema_non_string_station(tmp_path):
    gate = _gate(tmp_path)
    result = _fresh(gate, from_station=1, to_station="S4",
                    idempotency_key="k-type")
    assert result.verdict == REJECTED_SCHEMA


def test_received_to_rejected_policy_unknown_station(tmp_path):
    gate = _gate(tmp_path)
    result = _fresh(gate, from_station="S99", idempotency_key="k-pol")
    assert result.verdict == REJECTED_POLICY
    assert result.proposal.history == ["RECEIVED->REJECTED_POLICY"]


def test_pending_to_expired_at_ttl(tmp_path):
    gate = _gate(tmp_path, now=0.0)
    result = _fresh(gate, status_ts=0.0)
    assert result.verdict == PENDING
    gate._clock_state["t"] = gate.policy.proposal_ttl_s
    expired = gate.expire_due()
    assert [p.proposal_id for p in expired] == [result.proposal.proposal_id]
    assert result.proposal.state == EXPIRED
    assert result.proposal.history[-1] == "PENDING->EXPIRED"


def test_pending_does_not_expire_before_ttl(tmp_path):
    gate = _gate(tmp_path, now=0.0)
    result = _fresh(gate, status_ts=0.0)
    gate._clock_state["t"] = gate.policy.proposal_ttl_s - 0.001
    assert gate.expire_due() == []
    assert result.proposal.state == PENDING


def test_pending_to_approved_and_rejected_human(tmp_path):
    gate = _gate(tmp_path)
    approved = _fresh(gate, idempotency_key="k-ok")
    rejected = _fresh(gate, idempotency_key="k-no")
    a = gate.apply_decision(approved.proposal.proposal_id, "approve",
                            "m7-approve")
    r = gate.apply_decision(rejected.proposal.proposal_id, "reject",
                            "m7-approve")
    assert a.verdict == APPROVED
    assert r.verdict == REJECTED_HUMAN
    assert approved.proposal.history[-1] == "PENDING->APPROVED"
    assert rejected.proposal.history[-1] == "PENDING->REJECTED_HUMAN"


def test_approved_to_forwarded_and_forward_failed(tmp_path):
    gate = _gate(tmp_path)
    ok = _fresh(gate, idempotency_key="k-fwd")
    bad = _fresh(gate, idempotency_key="k-fail")
    gate.apply_decision(ok.proposal.proposal_id, "approve", "m7-approve")
    gate.apply_decision(bad.proposal.proposal_id, "approve", "m7-approve")
    f = gate.complete_forward(ok.proposal.proposal_id, True, forward_rc=0)
    x = gate.complete_forward(bad.proposal.proposal_id, False,
                              forward_rc="stale_status")
    assert f.verdict == FORWARDED
    assert x.verdict == FORWARD_FAILED
    assert ok.proposal.history[-1] == "APPROVED->FORWARDED"
    assert bad.proposal.history[-1] == "APPROVED->FORWARD_FAILED"


def test_every_named_transition_exists_on_the_machine():
    expected = {
        (RECEIVED, REJECTED_SCHEMA),
        (RECEIVED, REJECTED_POLICY),
        (RECEIVED, PENDING),
        (PENDING, EXPIRED),
        (PENDING, REJECTED_HUMAN),
        (PENDING, APPROVED),
        (APPROVED, FORWARDED),
        (APPROVED, FORWARD_FAILED),
    }
    got = {(src, dst) for src, dests in TRANSITIONS.items() for dst in dests}
    assert got == expected


def test_duplicate_idempotency_key_returns_the_existing_proposal(tmp_path):
    gate = _gate(tmp_path)
    first = _fresh(gate, idempotency_key="same")
    second = _fresh(gate, from_station="S2", to_station="S5",
                    idempotency_key="same", reason="retry")
    assert second.duplicate is True
    assert second.verdict == DUPLICATE
    assert second.proposal.proposal_id == first.proposal.proposal_id
    assert second.proposal.state == PENDING
    assert len(gate.all()) == 1


def test_duplicate_key_does_not_open_a_second_transition(tmp_path):
    gate = _gate(tmp_path)
    first = _fresh(gate, idempotency_key="same")
    _fresh(gate, idempotency_key="same")
    rows = gate.audit.rows()
    assert [row["verdict"] for row in rows] == [PENDING]
    assert rows[0]["proposal_id"] == first.proposal.proposal_id


def test_proposal_record_matches_proposal_schema(tmp_path):
    gate = _gate(tmp_path)
    result = _fresh(gate)
    Draft202012Validator(load_schema("proposal.schema.json")).validate(
        result.proposal.to_record())
