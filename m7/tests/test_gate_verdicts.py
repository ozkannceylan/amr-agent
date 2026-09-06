"""G2 — every proposal is gated and audited.

A bad schema, a bad station, a stale status, and a duplicate key each
produce the named verdict, and every transition has an audit row.
Architecture hygiene, not a safety function: M7 is not one.
"""
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
    pending = _propose(gate, "ok")
    other = _propose(gate, "ok2")
    human = _propose(gate, "ok3")
    fail = _propose(gate, "ok4")
    gate.apply_decision(pending.proposal.proposal_id, "approve", "m7-approve")
    gate.complete_forward(pending.proposal.proposal_id, True, forward_rc=0)
    gate.apply_decision(human.proposal.proposal_id, "reject", "m7-approve")
    gate.apply_decision(fail.proposal.proposal_id, "approve", "m7-approve")
    gate.complete_forward(fail.proposal.proposal_id, False, forward_rc="no_ack")
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
