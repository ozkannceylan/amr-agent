"""Every §4 transition writes exactly one audit row.

100 % coverage of transitions (HAND_OFF task 5 / G2). Append-only:
a second write adds a line, it does not rewrite the first.
"""
from jsonschema import Draft202012Validator

from gate.audit import AuditLog, load_audit_schema
from gate.policy import load_policy
from gate.proposal import (
    APPROVED,
    EXPIRED,
    FORWARD_FAILED,
    FORWARDED,
    PENDING,
    REJECTED_HUMAN,
    REJECTED_POLICY,
    REJECTED_SCHEMA,
    Gate,
)


def _gate(tmp_path, now=1000.0):
    clock = {"t": now}

    def now_fn():
        return clock["t"]

    path = tmp_path / "audit.jsonl"
    gate = Gate(
        policy=load_policy(),
        audit=AuditLog(path=path),
        clock=now_fn,
    )
    gate._clock_state = clock
    gate._audit_path = path
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


def _drive(gate, dest):
    """Drive one named edge and return the proposal."""
    if dest == REJECTED_SCHEMA:
        return _propose(gate, "schema-" + dest, from_station="").proposal
    if dest == REJECTED_POLICY:
        return _propose(gate, "policy-" + dest, from_station="S99").proposal
    if dest == PENDING:
        return _propose(gate, "pend-" + dest).proposal
    if dest == EXPIRED:
        proposal = _propose(gate, "ttl").proposal
        gate._clock_state["t"] = proposal.created_ts + gate.policy.proposal_ttl_s
        gate.expire_due()
        return proposal
    if dest == APPROVED:
        proposal = _propose(gate, "appr").proposal
        gate.apply_decision(proposal.proposal_id, "approve", "m7-approve")
        return proposal
    if dest == REJECTED_HUMAN:
        proposal = _propose(gate, "rej").proposal
        gate.apply_decision(proposal.proposal_id, "reject", "m7-approve")
        return proposal
    if dest == FORWARDED:
        proposal = _propose(gate, "fwd").proposal
        gate.apply_decision(proposal.proposal_id, "approve", "m7-approve")
        gate.complete_forward(proposal.proposal_id, True, forward_rc=0)
        return proposal
    if dest == FORWARD_FAILED:
        proposal = _propose(gate, "fail").proposal
        gate.apply_decision(proposal.proposal_id, "approve", "m7-approve")
        gate.complete_forward(proposal.proposal_id, False,
                              forward_rc="stale_status")
        return proposal
    raise AssertionError(dest)


def test_each_transition_writes_one_row_with_that_verdict(tmp_path):
    schema = load_audit_schema()
    validator = Draft202012Validator(schema)
    edges = (
        REJECTED_SCHEMA, REJECTED_POLICY, PENDING, EXPIRED,
        REJECTED_HUMAN, APPROVED, FORWARDED, FORWARD_FAILED,
    )
    seen = []
    for dest in edges:
        gate = _gate(tmp_path / dest)
        proposal = _drive(gate, dest)
        rows = gate.audit.rows()
        matching = [row for row in rows if row["verdict"] == dest]
        assert matching, (dest, [row["verdict"] for row in rows])
        assert matching[-1]["proposal_id"] == proposal.proposal_id
        for row in rows:
            validator.validate(row)
        seen.append(dest)
    assert set(seen) == set(edges)


def test_append_only_never_rewrites_a_line(tmp_path):
    gate = _gate(tmp_path)
    first = _propose(gate, "one")
    second = _propose(gate, "two")
    text = gate._audit_path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln]
    assert len(lines) == 2
    assert first.proposal.proposal_id in lines[0]
    assert second.proposal.proposal_id in lines[1]
    assert first.proposal.proposal_id not in lines[1]


def test_date_rotation_opens_a_new_file_not_an_edit(tmp_path):
    audit = AuditLog(audit_dir=tmp_path)
    row = {
        "ts": 0.0,
        "proposal_id": "pr-a",
        "client_id": "c",
        "tool": "propose_transport",
        "arguments": {},
        "schema_version": "1",
        "verdict": PENDING,
    }
    audit.append(row)
    later = dict(row, ts=86_400.0, proposal_id="pr-b")
    audit.append(later)
    files = sorted(p.name for p in tmp_path.glob("m7-*.jsonl"))
    assert files == ["m7-1970-01-01.jsonl", "m7-1970-01-02.jsonl"]
    assert audit.rows()[0]["proposal_id"] == "pr-a"
    assert audit.rows()[1]["proposal_id"] == "pr-b"
