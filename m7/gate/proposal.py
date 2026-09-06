"""proposal.py — the gate state machine, purely.

Bound by the fleet/ invariants (no ROS here; the only path to a vehicle
is VDA 5050, and this file is not on that path; losing the fleet
degrades, never endangers) and by ADR 0001 invariants 1, 2, 3, 11.
M7 is not a safety function.

THE MACHINE IS THE ONE IN ARCHITECTURE.md §4. Same input, same verdict,
and the verdict never depends on model output. The model's text is
stored as `reason` and is never parsed here.

RECEIVED is entered and left in the same propose() call. Duplicate
idempotency keys return the existing proposal rather than opening a
new one. There is no auto-approve in Phase 1.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

from gate.audit import AuditLog
from gate.policy import (
    Policy,
    RULE_STALE_STATUS,
    evaluate,
    is_authorised_decider,
    load_policy,
)

RECEIVED = "RECEIVED"
REJECTED_SCHEMA = "REJECTED_SCHEMA"
REJECTED_POLICY = "REJECTED_POLICY"
PENDING = "PENDING"
EXPIRED = "EXPIRED"
REJECTED_HUMAN = "REJECTED_HUMAN"
APPROVED = "APPROVED"
FORWARDED = "FORWARDED"
FORWARD_FAILED = "FORWARD_FAILED"
DUPLICATE = "DUPLICATE"
IGNORED_UNAUTHORISED = "IGNORED_UNAUTHORISED"

STATES = frozenset({
    RECEIVED, REJECTED_SCHEMA, REJECTED_POLICY, PENDING, EXPIRED,
    REJECTED_HUMAN, APPROVED, FORWARDED, FORWARD_FAILED,
})

TRANSITIONS = {
    RECEIVED: frozenset({REJECTED_SCHEMA, REJECTED_POLICY, PENDING}),
    PENDING: frozenset({EXPIRED, REJECTED_HUMAN, APPROVED}),
    APPROVED: frozenset({FORWARDED, FORWARD_FAILED}),
}

TERMINAL = frozenset({
    REJECTED_SCHEMA, REJECTED_POLICY, EXPIRED, REJECTED_HUMAN,
    FORWARDED, FORWARD_FAILED,
})

_SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
_RATE_WINDOW_S = 60.0


def new_task_id() -> str:
    """`ft-<hex8>`, the same mark fleet_cli.build_submission uses."""
    return "ft-{}".format(uuid.uuid4().hex[:8])


def new_proposal_id() -> str:
    return "pr-{}".format(uuid.uuid4().hex[:8])


def build_submit_body(from_station, to_station, task_id=None) -> dict:
    """The body shape `fleet_cli.build_submission` produces.

    Station and from!=to checks live in policy, not here: this function
    only shapes the payload the manager will read.
    """
    return {
        "taskId": task_id or new_task_id(),
        "from": from_station,
        "to": to_station,
    }


def load_schema(name: str) -> dict:
    return json.loads((_SCHEMAS / name).read_text(encoding="utf-8"))


def submit_validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema("submit.schema.json"))


@dataclass
class Proposal:
    proposal_id: str
    client_id: str
    from_station: object
    to_station: object
    reason: str
    idempotency_key: str
    created_ts: float
    state: str = RECEIVED
    task_id: str | None = None
    policy_rule: str | None = None
    decided_by: str | None = None
    forward_rc: str | int | None = None
    history: list[str] = field(default_factory=list)

    def to_record(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "client_id": self.client_id,
            "from": self.from_station,
            "to": self.to_station,
            "reason": self.reason,
            "idempotency_key": self.idempotency_key,
            "state": self.state,
            "created_ts": self.created_ts,
            "task_id": self.task_id,
            "policy_rule": self.policy_rule,
            "decided_by": self.decided_by,
            "forward_rc": self.forward_rc,
        }

    def transition(self, new_state: str) -> str:
        allowed = TRANSITIONS.get(self.state, frozenset())
        if new_state not in allowed:
            raise ValueError(
                "illegal transition {} -> {}".format(self.state, new_state))
        self.history.append("{}->{}".format(self.state, new_state))
        self.state = new_state
        return new_state


@dataclass(frozen=True)
class GateResult:
    proposal: Proposal | None
    verdict: str
    duplicate: bool = False
    policy_rule: str | None = None
    ignored: bool = False


class Gate:
    """Schema → policy → hold. MQTT and MCP stay out of this file."""

    def __init__(self, policy: Policy | None = None,
                 audit: AuditLog | None = None,
                 clock=None):
        self.policy = policy if policy is not None else load_policy()
        self.audit = audit if audit is not None else AuditLog()
        self._clock = clock or time.time
        self._by_id: dict[str, Proposal] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self._rate: dict[str, list[float]] = {}
        self._submit = submit_validator()

    def now(self) -> float:
        return float(self._clock())

    def get(self, proposal_id: str) -> Proposal | None:
        return self._by_id.get(proposal_id)

    def all(self) -> list[Proposal]:
        return list(self._by_id.values())

    def pending(self) -> list[Proposal]:
        return [p for p in self._by_id.values() if p.state == PENDING]

    def pending_count(self, client_id: str) -> int:
        return sum(1 for p in self._by_id.values()
                   if p.client_id == client_id and p.state == PENDING)

    def recent_count(self, client_id: str, now: float | None = None) -> int:
        when = self.now() if now is None else now
        stamps = [t for t in self._rate.get(client_id, [])
                  if when - t < _RATE_WINDOW_S]
        self._rate[client_id] = stamps
        return len(stamps)

    def propose(
        self,
        *,
        from_station,
        to_station,
        reason,
        idempotency_key,
        client_id: str,
        status_ts=None,
        now: float | None = None,
    ) -> GateResult:
        when = self.now() if now is None else now
        key = str(idempotency_key) if isinstance(idempotency_key, str) else ""
        if key:
            existing_id = self._by_key.get((client_id, key))
            if existing_id is not None:
                existing = self._by_id[existing_id]
                return GateResult(existing, DUPLICATE, duplicate=True)

        proposal = Proposal(
            proposal_id=new_proposal_id(),
            client_id=client_id,
            from_station=from_station,
            to_station=to_station,
            reason="" if reason is None else str(reason),
            idempotency_key=key,
            created_ts=when,
        )
        self._by_id[proposal.proposal_id] = proposal
        if key:
            self._by_key[(client_id, key)] = proposal.proposal_id
        self._rate.setdefault(client_id, []).append(when)

        body = build_submit_body(from_station, to_station)
        proposal.task_id = body.get("taskId") if isinstance(
            body.get("taskId"), str) else None
        schema_errors = sorted(
            self._submit.iter_errors(body), key=lambda e: list(e.path))
        )
        if not key or schema_errors:
            return self._close(
                proposal, REJECTED_SCHEMA, when,
                tool="propose_transport",
                arguments=_args(from_station, to_station, reason,
                                idempotency_key),
            )

        policy = evaluate(
            self.policy,
            from_station=from_station,
            to_station=to_station,
            now=when,
            status_ts=status_ts,
            pending_count=self.pending_count(client_id),
            recent_count=self.recent_count(client_id, when) - 1,
        )
        if not policy.ok:
            proposal.policy_rule = policy.rule
            return self._close(
                proposal, REJECTED_POLICY, when,
                tool="propose_transport",
                arguments=_args(from_station, to_station, reason,
                                idempotency_key),
                policy_rule=policy.rule,
            )

        return self._close(
            proposal, PENDING, when,
            tool="propose_transport",
            arguments=_args(from_station, to_station, reason,
                            idempotency_key),
        )

    def expire_due(self, now: float | None = None) -> list[Proposal]:
        when = self.now() if now is None else now
        expired = []
        for proposal in list(self._by_id.values()):
            if proposal.state != PENDING:
                continue
            if when - proposal.created_ts < self.policy.proposal_ttl_s:
                continue
            self._close(
                proposal, EXPIRED, when,
                tool="expire",
                arguments={"proposal_id": proposal.proposal_id},
            )
            expired.append(proposal)
        return expired

    def apply_decision(
        self,
        proposal_id: str,
        decision: str,
        decided_by: str,
        now: float | None = None,
    ) -> GateResult:
        when = self.now() if now is None else now
        if not is_authorised_decider(self.policy, decided_by):
            self.audit.append({
                "ts": when,
                "proposal_id": proposal_id,
                "client_id": decided_by,
                "tool": "decision",
                "arguments": {
                    "proposal_id": proposal_id,
                    "decision": decision,
                    "decided_by": decided_by,
                },
                "schema_version": self.policy.schema_version,
                "verdict": IGNORED_UNAUTHORISED,
                "decided_by": decided_by,
            })
            return GateResult(
                self.get(proposal_id), IGNORED_UNAUTHORISED, ignored=True)

        proposal = self._by_id.get(proposal_id)
        if proposal is None or proposal.state != PENDING:
            raise ValueError(
                "proposal {!r} is not PENDING".format(proposal_id))
        if decision == "approve":
            target = APPROVED
        elif decision == "reject":
            target = REJECTED_HUMAN
        else:
            raise ValueError("decision must be approve or reject")
        proposal.decided_by = decided_by
        return self._close(
            proposal, target, when,
            tool="decision",
            arguments={
                "proposal_id": proposal_id,
                "decision": decision,
                "decided_by": decided_by,
            },
            decided_by=decided_by,
        )

    def complete_forward(
        self,
        proposal_id: str,
        ok: bool,
        forward_rc=None,
        now: float | None = None,
    ) -> GateResult:
        when = self.now() if now is None else now
        proposal = self._by_id.get(proposal_id)
        if proposal is None or proposal.state != APPROVED:
            raise ValueError(
                "proposal {!r} is not APPROVED".format(proposal_id))
        proposal.forward_rc = forward_rc
        target = FORWARDED if ok else FORWARD_FAILED
        return self._close(
            proposal, target, when,
            tool="forward",
            arguments={"proposal_id": proposal_id},
            forward_rc=forward_rc,
        )

    def _close(self, proposal: Proposal, new_state: str, now: float, *,
               tool: str, arguments: dict,
               policy_rule: str | None = None,
               decided_by: str | None = None,
               forward_rc=None) -> GateResult:
        proposal.transition(new_state)
        row = {
            "ts": now,
            "proposal_id": proposal.proposal_id,
            "client_id": proposal.client_id,
            "tool": tool,
            "arguments": arguments,
            "schema_version": self.policy.schema_version,
            "verdict": new_state,
            "task_id": proposal.task_id,
        }
        rule = policy_rule if policy_rule is not None else proposal.policy_rule
        if rule is not None:
            row["policy_rule"] = rule
        who = decided_by if decided_by is not None else proposal.decided_by
        if who is not None:
            row["decided_by"] = who
        rc = forward_rc if forward_rc is not None else proposal.forward_rc
        if rc is not None:
            row["forward_rc"] = rc
        self.audit.append(row)
        return GateResult(proposal, new_state, policy_rule=rule)


def _args(from_station, to_station, reason, idempotency_key) -> dict:
    return {
        "from": from_station,
        "to": to_station,
        "reason": reason,
        "idempotency_key": idempotency_key,
    }


# Re-export for tests that name the stale rule next to a verdict.
STALE_STATUS = RULE_STALE_STATUS
