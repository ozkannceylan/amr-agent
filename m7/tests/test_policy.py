"""One test per Phase 1 policy rule (G2).

Architecture hygiene around the allowlist, caps and stale-status
refusal. M7 is not a safety function.
"""
from gate.policy import (
    RULE_FROM_NEQ_TO,
    RULE_PENDING_CAP,
    RULE_RATE_CAP,
    RULE_STALE_STATUS,
    RULE_STATION_ALLOWLIST,
    evaluate,
    is_authorised_decider,
    load_policy,
)


def _ok(policy, **kwargs):
    defaults = dict(
        from_station="S1",
        to_station="S4",
        now=100.0,
        status_ts=99.0,
        pending_count=0,
        recent_count=0,
    )
    defaults.update(kwargs)
    return evaluate(policy, **defaults)


def test_load_policy_has_the_fleet_station_table():
    policy = load_policy()
    assert policy.schema_version == "1"
    assert list(policy.stations) == [
        "S1", "S2", "S3", "S4", "S5", "S6",
        "S7", "S8", "S9", "S10", "S11", "S12",
    ]
    assert policy.stations["S1"] == "PICK-NW-1"
    assert policy.stations["S12"] == "CONVEYOR"
    assert policy.stale_after_s == 3 * policy.status_period_s
    assert policy.status_period_s == 2.0


def test_a_good_transport_passes():
    result = _ok(load_policy())
    assert result.ok is True
    assert result.rule is None


def test_unknown_station_is_station_allowlist():
    policy = load_policy()
    from_bad = _ok(policy, from_station="S99")
    to_bad = _ok(policy, to_station="sink")
    case = _ok(policy, from_station="s1")
    assert from_bad.ok is False and from_bad.rule == RULE_STATION_ALLOWLIST
    assert "FROM" in from_bad.detail
    assert to_bad.ok is False and to_bad.rule == RULE_STATION_ALLOWLIST
    assert "TO" in to_bad.detail
    assert case.rule == RULE_STATION_ALLOWLIST


def test_from_equals_to_is_refused():
    result = _ok(load_policy(), from_station="S4", to_station="S4")
    assert result.ok is False
    assert result.rule == RULE_FROM_NEQ_TO


def test_pending_cap_is_per_client_count():
    policy = load_policy()
    under = _ok(policy, pending_count=policy.max_pending_per_client - 1)
    at = _ok(policy, pending_count=policy.max_pending_per_client)
    assert under.ok is True
    assert at.ok is False and at.rule == RULE_PENDING_CAP


def test_per_minute_cap():
    policy = load_policy()
    under = _ok(policy, recent_count=policy.max_proposals_per_minute - 1)
    at = _ok(policy, recent_count=policy.max_proposals_per_minute)
    assert under.ok is True
    assert at.ok is False and at.rule == RULE_RATE_CAP


def test_stale_status_is_refused_after_three_periods():
    policy = load_policy()
    now = 1000.0
    fresh = _ok(policy, now=now, status_ts=now - policy.stale_after_s)
    stale = _ok(policy, now=now, status_ts=now - policy.stale_after_s - 0.001)
    missing = _ok(policy, status_ts=None)
    assert fresh.ok is True
    assert stale.ok is False and stale.rule == RULE_STALE_STATUS
    assert missing.ok is False and missing.rule == RULE_STALE_STATUS


def test_stale_status_is_asked_before_the_allowlist():
    result = _ok(load_policy(), from_station="S99", status_ts=None)
    assert result.rule == RULE_STALE_STATUS


def test_authorised_decider_is_the_approve_client():
    policy = load_policy()
    assert is_authorised_decider(policy, "m7-approve") is True
    assert is_authorised_decider(policy, "someone-else") is False
