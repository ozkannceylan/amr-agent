"""policy.py — Phase 1 gate rules, purely.

Bound by the fleet/ invariants (no ROS here; the only path to a vehicle
is VDA 5050, and this file is not on that path; losing the fleet
degrades, never endangers) and by ADR 0001 invariants 1, 2, 3, 11.
M7 is not a safety function.

THE RULES ARE DATA. Every check reads `policy.yaml` and the arguments
it was given. Nothing here parses a model `reason`, and nothing here
reads a vehicle. Same input, same verdict.

Phase 1 contents (ARCHITECTURE.md §4): station allowlist, from != to,
max pending per client, max proposals per minute, refuse when
fleet/status is older than its staleness bound.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

POLICY_PATH = Path(__file__).resolve().with_name("policy.yaml")

RULE_STALE_STATUS = "stale_status"
RULE_STATION_ALLOWLIST = "station_allowlist"
RULE_FROM_NEQ_TO = "from_neq_to"
RULE_PENDING_CAP = "pending_cap"
RULE_RATE_CAP = "rate_cap"


@dataclass(frozen=True)
class Policy:
    schema_version: str
    stations: dict[str, str]
    status_period_s: float
    stale_after_s: float
    proposal_ttl_s: float
    max_pending_per_client: int
    max_proposals_per_minute: int
    authorised_deciders: frozenset[str]


@dataclass(frozen=True)
class PolicyResult:
    ok: bool
    rule: str | None = None
    detail: str = ""


def load_policy(path: Path | None = None) -> Policy:
    raw = yaml.safe_load((path or POLICY_PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("policy.yaml must be a mapping")
    stations = raw.get("stations")
    if not isinstance(stations, dict) or not stations:
        raise ValueError("policy.yaml stations must be a non-empty mapping")
    deciders = raw.get("authorised_deciders") or []
    if not isinstance(deciders, list):
        raise ValueError("policy.yaml authorised_deciders must be a list")
    return Policy(
        schema_version=str(raw.get("schema_version", "1")),
        stations={str(k): str(v) for k, v in stations.items()},
        status_period_s=float(raw["status_period_s"]),
        stale_after_s=float(raw["stale_after_s"]),
        proposal_ttl_s=float(raw["proposal_ttl_s"]),
        max_pending_per_client=int(raw["max_pending_per_client"]),
        max_proposals_per_minute=int(raw["max_proposals_per_minute"]),
        authorised_deciders=frozenset(str(d) for d in deciders),
    )


def evaluate(
    policy: Policy,
    *,
    from_station,
    to_station,
    now: float,
    status_ts,
    pending_count: int,
    recent_count: int,
) -> PolicyResult:
    """First failing rule, or ok. Order is the refuse-early path:

    stale status (no manager) → allowlist → from!=to → pending cap →
    per-minute cap. Duplicate idempotency is not a policy refusal; the
    book returns the existing proposal instead.
    """
    if status_ts is None or not isinstance(status_ts, (int, float)) \
            or isinstance(status_ts, bool):
        return PolicyResult(False, RULE_STALE_STATUS,
                            "fleet/status carries no timestamp")
    age = now - float(status_ts)
    if age > policy.stale_after_s:
        return PolicyResult(
            False, RULE_STALE_STATUS,
            "fleet/status is {:.1f} s old (bound {:.1f} s)".format(
                age, policy.stale_after_s))

    for role, station in (("FROM", from_station), ("TO", to_station)):
        if station not in policy.stations:
            return PolicyResult(
                False, RULE_STATION_ALLOWLIST,
                "unknown {} station {!r}".format(role, station))

    if from_station == to_station:
        return PolicyResult(
            False, RULE_FROM_NEQ_TO,
            "FROM and TO are the same station ({})".format(from_station))

    if pending_count >= policy.max_pending_per_client:
        return PolicyResult(
            False, RULE_PENDING_CAP,
            "client already has {} pending (cap {})".format(
                pending_count, policy.max_pending_per_client))

    if recent_count >= policy.max_proposals_per_minute:
        return PolicyResult(
            False, RULE_RATE_CAP,
            "client already sent {} proposals in the last minute (cap {})"
            .format(recent_count, policy.max_proposals_per_minute))

    return PolicyResult(True)


def is_authorised_decider(policy: Policy, decided_by: str) -> bool:
    return decided_by in policy.authorised_deciders
