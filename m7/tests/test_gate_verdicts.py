"""G2 — every proposal is gated and audited.

A bad schema, a bad station, a stale status, a duplicate key, and a
decision that arrives after the TTL each produce the named verdict, and
every transition has an audit row.
Architecture hygiene, not a safety function: M7 is not one.
"""
import pytest

from gate.audit import AuditLog
from gate.policy import (
    RULE_STALE_STATUS,
    RULE_STATION_ALLOWLIST,
    load_policy,
)
from gate.proposal import (
    APPROVED,
    DUPLICATE,
    EXPIRED,
    FORWARD_FAILED,
    FORWARDED,
    PENDING,
    REJECTED_HUMAN,
    REJECTED_POLICY,
    REJECTED_SCHEMA,
    TRANSITIONS,
    Gate,
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


def _propose(gate, key, **kwargs):
    defaults = dict(
        from_station="S1",
        to_station="S4",
        reason="move a pallet",
        idempotency_key=key,
        client_id="console-a",
        status_ts=gate.now(),
    )
    defaults.update(kwargs)
    return gate.propose(**defaults)


def test_g2_bad_schema_is_rejected_schema(tmp_path):
    gate = _gate(tmp_path)
    result = _propose(gate, "bad-schema", from_station="")
    assert result.verdict == REJECTED_SCHEMA
    rows = [row for row in gate.audit.rows()
            if row["proposal_id"] == result.proposal.proposal_id]
    assert [row["verdict"] for row in rows] == [REJECTED_SCHEMA]


def test_g2_bad_station_is_rejected_policy(tmp_path):
    gate = _gate(tmp_path)
    result = _propose(gate, "bad-station", from_station="S99")
    assert result.verdict == REJECTED_POLICY
    assert result.policy_rule == RULE_STATION_ALLOWLIST
    rows = gate.audit.rows()
    assert rows[-1]["verdict"] == REJECTED_POLICY
    assert rows[-1]["policy_rule"] == RULE_STATION_ALLOWLIST


def test_g2_stale_status_is_rejected_policy(tmp_path):
    gate = _gate(tmp_path)
    result = _propose(
        gate, "stale",
        status_ts=gate.now() - gate.policy.stale_after_s - 1,
    )
    assert result.verdict == REJECTED_POLICY
    assert result.policy_rule == RULE_STALE_STATUS
    assert gate.audit.rows()[-1]["policy_rule"] == RULE_STALE_STATUS


def test_g2_duplicate_key_is_the_named_verdict(tmp_path):
    gate = _gate(tmp_path)
    first = _propose(gate, "dup")
    second = _propose(gate, "dup", from_station="S2", to_station="S8")
    assert first.verdict == PENDING
    assert second.verdict == DUPLICATE
    assert second.duplicate is True
    assert second.proposal.proposal_id == first.proposal.proposal_id
    assert [row["verdict"] for row in gate.audit.rows()] == [PENDING]


def test_g2_every_transition_has_an_audit_row(tmp_path):
    gate = _gate(tmp_path)
    schema = _propose(gate, "s", from_station="")
    policy = _propose(gate, "p", from_station="S99")
    # Keep at most one PENDING at a time so the per-client cap (3)
    # cannot hide the later edges.
    pending = _propose(gate, "ok")
    gate.apply_decision(pending.proposal.proposal_id, "approve", "m7-approve")
    gate.complete_forward(pending.proposal.proposal_id, True, forward_rc=0)
    human = _propose(gate, "ok3")
    gate.apply_decision(human.proposal.proposal_id, "reject", "m7-approve")
    fail = _propose(gate, "ok4")
    gate.apply_decision(fail.proposal.proposal_id, "approve", "m7-approve")
    gate.complete_forward(fail.proposal.proposal_id, False, forward_rc="no_ack")
    other = _propose(gate, "ok2")
    gate._clock_state["t"] = other.proposal.created_ts + gate.policy.proposal_ttl_s
    gate.expire_due()

    by_verdict = {}
    for row in gate.audit.rows():
        by_verdict.setdefault(row["verdict"], []).append(row)

    expected = {
        REJECTED_SCHEMA, REJECTED_POLICY, PENDING, EXPIRED,
        REJECTED_HUMAN, APPROVED, FORWARDED, FORWARD_FAILED,
    }
    assert expected <= set(by_verdict)
    dests = {dst for dests in TRANSITIONS.values() for dst in dests}
    assert dests <= set(by_verdict)
    assert schema.proposal.proposal_id == by_verdict[REJECTED_SCHEMA][0]["proposal_id"]
    assert policy.proposal.proposal_id == by_verdict[REJECTED_POLICY][0]["proposal_id"]
    assert other.proposal.state == EXPIRED


def test_g2_decision_after_ttl_expires_instead_of_deciding(tmp_path):
    """The decision path is the one that moves a vehicle, so it checks
    the TTL itself rather than trusting a sweep to have run first."""
    gate = _gate(tmp_path)
    pending = _propose(gate, "ttl-approve")
    pid = pending.proposal.proposal_id
    gate._clock_state["t"] = (
        pending.proposal.created_ts + gate.policy.proposal_ttl_s)

    result = gate.apply_decision(pid, "approve", "m7-approve")

    assert result.verdict == EXPIRED
    assert gate.get(pid).state == EXPIRED
    assert gate.get(pid).history[-1] == "PENDING->EXPIRED"
    assert gate.get(pid).decided_by is None


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_g2_expired_decision_is_audited_with_who_tried(tmp_path, decision):
    gate = _gate(tmp_path)
    pending = _propose(gate, "ttl-audit-" + decision)
    pid = pending.proposal.proposal_id
    gate._clock_state["t"] = (
        pending.proposal.created_ts + gate.policy.proposal_ttl_s + 1.0)

    gate.apply_decision(pid, decision, "m7-approve")

    rows = [row for row in gate.audit.rows() if row["proposal_id"] == pid]
    assert [row["verdict"] for row in rows] == [PENDING, EXPIRED]
    expired_row = rows[-1]
    assert expired_row["tool"] == "decision"
    assert expired_row["decided_by"] == "m7-approve"
    assert expired_row["arguments"]["decision"] == decision


def test_g2_decision_just_inside_the_ttl_still_applies(tmp_path):
    gate = _gate(tmp_path)
    pending = _propose(gate, "ttl-edge")
    pid = pending.proposal.proposal_id
    gate._clock_state["t"] = (
        pending.proposal.created_ts + gate.policy.proposal_ttl_s - 0.001)

    result = gate.apply_decision(pid, "approve", "m7-approve")

    assert result.verdict == APPROVED
    assert gate.get(pid).decided_by == "m7-approve"


def test_g2_an_expired_proposal_cannot_be_decided_twice(tmp_path):
    gate = _gate(tmp_path)
    pending = _propose(gate, "ttl-twice")
    pid = pending.proposal.proposal_id
    gate._clock_state["t"] = (
        pending.proposal.created_ts + gate.policy.proposal_ttl_s)
    gate.apply_decision(pid, "approve", "m7-approve")
    before = len(gate.audit.rows())

    with pytest.raises(ValueError, match="not PENDING"):
        gate.apply_decision(pid, "approve", "m7-approve")

    assert len(gate.audit.rows()) == before


def test_g2_expiry_before_decide_runs_after_the_authorisation_check(tmp_path):
    """An unauthorised decider is still ignored, and still moves nothing:
    it does not get to trip the expiry edge either."""
    gate = _gate(tmp_path)
    pending = _propose(gate, "ttl-forged")
    pid = pending.proposal.proposal_id
    gate._clock_state["t"] = (
        pending.proposal.created_ts + gate.policy.proposal_ttl_s)

    result = gate.apply_decision(pid, "approve", "intruder")

    assert result.ignored is True
    assert gate.get(pid).state == PENDING
    assert gate.audit.rows()[-1]["verdict"] == "IGNORED_UNAUTHORISED"
