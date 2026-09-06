"""Veto gate — delta box, freshness, health; Phase A refuses all.

ARCHITECTURE.md §5. Every proposal is checked; every proposal and every
verdict is a log row. Phase A (shadow) accepts nothing: the classical
stack keeps driving on the tag alone. Later phases flip individual
kinds live (B: abort only; C: refine inside the box). This module
already computes the checks those phases will honour, so the log is
scorable from day one.

NO ROS. Health is a flag the caller supplies — the node that will
measure latency and RTF does not exist in A0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from .contract import (
    KIND_DOCK_ABORT,
    KIND_DOCK_TARGET_REFINE,
    KIND_SPEED_REDUCE,
    Proposal,
    is_expired,
    is_monotone,
    monotone_violations,
    proposal_log_fields,
    remaining_ttl_ms,
    validate_proposal,
    ContractError,
)

# Phase letters match PLAN.md. A0 ships Phase A behaviour only.
PHASE_A = "A"
PHASE_B = "B"
PHASE_C = "C"

# Reasons that appear in Verdict.reason and the log. Named so a bench
# can count them without parsing prose.
REASON_PHASE_A_SHADOW = "phase_a_shadow"
REASON_INVALID = "invalid"
REASON_EXPIRED = "expired"
REASON_STALE_FRAME = "stale_frame"
REASON_UNHEALTHY = "unhealthy"
REASON_NOT_MONOTONE = "not_monotone"
REASON_OUTSIDE_DELTA_BOX = "outside_delta_box"
REASON_ACCEPTED = "accepted"

# Health budgets are placeholders until E5 names the real ones. They
# exist so the check has a shape; they are not a measured claim.
DEFAULT_MAX_FRAME_AGE_MS = 200.0
DEFAULT_MAX_INFER_P95_MS = 50.0
DEFAULT_MAX_RTF_COST = 0.15


@dataclass(frozen=True)
class DeltaBox:
    """Accept a refine only when the pose delta sits inside this box.

    Phase C fixes the numbers from E1. Phase A/B never accept a refine
    regardless of the box; the check is still run and logged.
    """

    max_dx: float
    max_dy: float
    max_dtheta: float

    def contains(self, proposal: Proposal) -> bool:
        if proposal.kind != KIND_DOCK_TARGET_REFINE:
            return True
        delta = proposal.pose_delta()
        return (abs(delta.dx) <= self.max_dx
                and abs(delta.dy) <= self.max_dy
                and abs(delta.dtheta) <= self.max_dtheta)


@dataclass(frozen=True)
class Health:
    """Caller-supplied snapshot. Any failure → refuse rather than limp."""

    model_loaded: bool = False
    model_warm: bool = False
    inference_latency_p95_ms: float = float("inf")
    frame_age_ms: float = float("inf")
    rtf_cost: float = float("inf")

    def ok(self,
           max_infer_p95_ms: float = DEFAULT_MAX_INFER_P95_MS,
           max_frame_age_ms: float = DEFAULT_MAX_FRAME_AGE_MS,
           max_rtf_cost: float = DEFAULT_MAX_RTF_COST) -> bool:
        return (
            bool(self.model_loaded)
            and bool(self.model_warm)
            and self.inference_latency_p95_ms <= max_infer_p95_ms
            and self.frame_age_ms <= max_frame_age_ms
            and self.rtf_cost <= max_rtf_cost
        )

    def failures(self,
                 max_infer_p95_ms: float = DEFAULT_MAX_INFER_P95_MS,
                 max_frame_age_ms: float = DEFAULT_MAX_FRAME_AGE_MS,
                 max_rtf_cost: float = DEFAULT_MAX_RTF_COST) -> List[str]:
        names = []
        if not self.model_loaded:
            names.append("model_not_loaded")
        if not self.model_warm:
            names.append("model_not_warm")
        if self.inference_latency_p95_ms > max_infer_p95_ms:
            names.append("inference_latency")
        if self.frame_age_ms > max_frame_age_ms:
            names.append("frame_age")
        if self.rtf_cost > max_rtf_cost:
            names.append("rtf_cost")
        return names


def healthy(**kwargs: Any) -> Health:
    """A passing health snapshot for tests and for later phases."""
    defaults = dict(
        model_loaded=True,
        model_warm=True,
        inference_latency_p95_ms=1.0,
        frame_age_ms=10.0,
        rtf_cost=0.0)
    defaults.update(kwargs)
    return Health(**defaults)


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str
    checks: dict
    proposal: Proposal
    now_s: float

    def log_row(self) -> dict:
        row = {
            "accepted": self.accepted,
            "reason": self.reason,
            "now_s": self.now_s,
            "checks": dict(self.checks),
            "remaining_ttl_ms": remaining_ttl_ms(self.proposal, self.now_s),
        }
        row.update(proposal_log_fields(self.proposal))
        return row


@dataclass
class Gate:
    """Deterministic consumer of Proposal. Phase A: refuse all, log all."""

    phase: str = PHASE_A
    delta_box: Optional[DeltaBox] = None
    max_frame_age_ms: float = DEFAULT_MAX_FRAME_AGE_MS
    max_infer_p95_ms: float = DEFAULT_MAX_INFER_P95_MS
    max_rtf_cost: float = DEFAULT_MAX_RTF_COST
    log: List[dict] = field(default_factory=list)
    _last_motion: Optional[Proposal] = field(default=None, init=False, repr=False)

    def evaluate(self,
                 proposal: Proposal,
                 now_s: float,
                 health: Optional[Health] = None,
                 previous: Optional[Proposal] = None) -> Verdict:
        """Check, refuse or (later phases) accept, and always append a row."""
        checks: dict = {
            "phase": self.phase,
            "valid": False,
            "fresh": False,
            "healthy": False,
            "monotone": False,
            "inside_delta_box": False,
        }
        reason = REASON_INVALID
        accepted = False

        try:
            validate_proposal(proposal)
            checks["valid"] = True
        except ContractError as exc:
            checks["invalid_why"] = str(exc)
            return self._record(proposal, now_s, False, REASON_INVALID, checks)

        expired = is_expired(proposal, now_s)
        frame_age_ms = (float(now_s) - float(proposal.evidence.sim_stamp)) * 1000.0
        stale_frame = frame_age_ms > self.max_frame_age_ms
        checks["expired"] = expired
        checks["frame_age_ms"] = frame_age_ms
        checks["stale_frame"] = stale_frame
        checks["fresh"] = (not expired) and (not stale_frame)

        snap = health if health is not None else Health()
        checks["health_failures"] = snap.failures(
            self.max_infer_p95_ms, self.max_frame_age_ms, self.max_rtf_cost)
        checks["healthy"] = snap.ok(
            self.max_infer_p95_ms, self.max_frame_age_ms, self.max_rtf_cost)

        prior = previous if previous is not None else self._last_motion
        checks["monotone"] = is_monotone(prior, proposal)
        checks["monotone_violations"] = list(monotone_violations(prior, proposal))

        if self.delta_box is None:
            checks["inside_delta_box"] = proposal.kind != KIND_DOCK_TARGET_REFINE
            checks["delta_box"] = None
        else:
            checks["inside_delta_box"] = self.delta_box.contains(proposal)
            checks["delta_box"] = {
                "max_dx": self.delta_box.max_dx,
                "max_dy": self.delta_box.max_dy,
                "max_dtheta": self.delta_box.max_dtheta,
            }

        if not checks["fresh"]:
            reason = REASON_EXPIRED if expired else REASON_STALE_FRAME
        elif not checks["healthy"]:
            reason = REASON_UNHEALTHY
        elif not checks["monotone"]:
            reason = REASON_NOT_MONOTONE
        elif proposal.kind == KIND_DOCK_TARGET_REFINE and not checks["inside_delta_box"]:
            reason = REASON_OUTSIDE_DELTA_BOX
        elif self.phase == PHASE_A:
            reason = REASON_PHASE_A_SHADOW
        else:
            # Later phases live here. A0 never takes this branch in
            # production; tests may construct a non-A gate to pin the
            # check order without shipping a consumer.
            reason = REASON_ACCEPTED
            accepted = True

        if self.phase == PHASE_A:
            accepted = False
            if reason == REASON_ACCEPTED:
                reason = REASON_PHASE_A_SHADOW

        if accepted and proposal.kind in (
                KIND_DOCK_TARGET_REFINE, KIND_DOCK_ABORT, KIND_SPEED_REDUCE):
            self._last_motion = proposal

        return self._record(proposal, now_s, accepted, reason, checks)

    def _record(self,
                proposal: Proposal,
                now_s: float,
                accepted: bool,
                reason: str,
                checks: dict) -> Verdict:
        verdict = Verdict(
            accepted=accepted,
            reason=reason,
            checks=checks,
            proposal=proposal,
            now_s=float(now_s))
        self.log.append(verdict.log_row())
        return verdict
