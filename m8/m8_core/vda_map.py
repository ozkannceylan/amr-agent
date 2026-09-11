"""Proposal/Verdict → VDA 5050 2.1.0 state fragments.

Field names are the spec's, as recorded in
`docs/interfaces/vda5050-subset.md` §5 and §9:

* errors[]: errorType, errorLevel (WARNING|FATAL), errorDescription,
  errorHint, errorReferences[{referenceKey, referenceValue}]
* information[]: infoType, infoLevel (INFO|DEBUG), infoDescription,
  infoReferences[{referenceKey, referenceValue}]

Project error names are camelCase (subset amendment 2026-08-21 (e)).
ARCHITECTURE.md §5 names the two M8 types: `m8.dockAbort` (errors[],
WARNING) and `m8.slotState` (information[]). information[] is a debug
channel — the spec forbids using it for control logic; the vehicle does
not act on a slot mismatch (fleet-level finding only).

This module builds fragments. It does not publish MQTT, does not touch
the PLC, and does not carry frames.
"""
from __future__ import annotations

from typing import Any, List, Mapping, Optional

from .contract import (
    KIND_ANOMALY,
    KIND_DOCK_ABORT,
    KIND_DOCK_TARGET_REFINE,
    KIND_LOAD_ID,
    KIND_SLOT_STATE,
    KIND_SPEED_REDUCE,
    Proposal,
    proposal_log_fields,
)
from .gate import Verdict

# Documented extension names (ARCHITECTURE.md §5). Dotted prefix keeps
# them out of the VDA-predefined set (orderError, pathBlocked, …).
ERROR_TYPE_DOCK_ABORT = "m8.dockAbort"
INFO_TYPE_SLOT_STATE = "m8.slotState"

ERROR_LEVEL_WARNING = "WARNING"
INFO_LEVEL_INFO = "INFO"

# Subset §5 produced errorLevel set is {WARNING, FATAL}. Abort is not a
# safety event (R4): the F-PLC never hears it. WARNING is the level.
# FATAL would mean "not in running condition" — M8 does not claim that.


def _ref(key: str, value: Any) -> dict:
    return {"referenceKey": str(key), "referenceValue": str(value)}


def _evidence_refs(proposal: Proposal) -> List[dict]:
    ev = proposal.evidence
    refs = [
        _ref("frameId", ev.frame_id),
        _ref("simStamp", ev.sim_stamp),
        _ref("sensorName", ev.sensor_name),
        _ref("kind", proposal.kind),
    ]
    if proposal.leg_id:
        refs.append(_ref("legId", proposal.leg_id))
    return refs


def dock_abort_error(proposal: Proposal,
                     verdict: Optional[Verdict] = None) -> dict:
    """One errors[] item. errorType m8.dockAbort, errorLevel WARNING."""
    if proposal.kind != KIND_DOCK_ABORT:
        raise ValueError("dock_abort_error needs a DOCK_ABORT proposal")
    reason = proposal.abort_reason()
    refs = _evidence_refs(proposal)
    refs.append(_ref("reasonCode", reason))
    if verdict is not None:
        refs.append(_ref("verdict", "accepted" if verdict.accepted else "refused"))
        refs.append(_ref("verdictReason", verdict.reason))
    return {
        "errorType": ERROR_TYPE_DOCK_ABORT,
        "errorLevel": ERROR_LEVEL_WARNING,
        "errorDescription": "M8 dock abort: {}".format(reason),
        "errorHint": "cycle ends at staging; fleet may cancelOrder",
        "errorReferences": refs,
    }


def slot_state_info(proposal: Proposal,
                    verdict: Optional[Verdict] = None) -> dict:
    """One information[] item. infoType m8.slotState, infoLevel INFO."""
    if proposal.kind != KIND_SLOT_STATE:
        raise ValueError("slot_state_info needs a SLOT_STATE proposal")
    rows = proposal.slot_table()
    refs = _evidence_refs(proposal)
    for row in rows:
        refs.append(_ref("slot:{}".format(row.slot_id), row.state))
    if verdict is not None:
        refs.append(_ref("verdict", "accepted" if verdict.accepted else "refused"))
        refs.append(_ref("verdictReason", verdict.reason))
    return {
        "infoType": INFO_TYPE_SLOT_STATE,
        "infoLevel": INFO_LEVEL_INFO,
        "infoDescription": "M8 shelf-slot table ({} rows)".format(len(rows)),
        "infoReferences": refs,
    }


def _generic_info(info_type: str,
                  proposal: Proposal,
                  verdict: Optional[Verdict],
                  description: str) -> dict:
    refs = _evidence_refs(proposal)
    fields = proposal_log_fields(proposal)
    payload = fields["payload"]
    if isinstance(payload, dict):
        for key, value in payload.items():
            refs.append(_ref(key, value))
    else:
        refs.append(_ref("payload", payload))
    if verdict is not None:
        refs.append(_ref("verdict", "accepted" if verdict.accepted else "refused"))
    return {
        "infoType": info_type,
        "infoLevel": INFO_LEVEL_INFO,
        "infoDescription": description,
        "infoReferences": refs,
    }


def to_vda(proposal: Proposal,
           verdict: Optional[Verdict] = None) -> Mapping[str, List[dict]]:
    """Map one Proposal (and optional Verdict) to VDA state fragments.

    Returns {"errors": [...], "information": [...]}. Empty arrays are
    valid VDA (subset §5: empty errors[] = none). Phase A verdicts are
    refused; the fragments are still produced so shadow logs and later
    publishers share one mapper.
    """
    errors: List[dict] = []
    information: List[dict] = []

    if proposal.kind == KIND_DOCK_ABORT:
        errors.append(dock_abort_error(proposal, verdict))
    elif proposal.kind == KIND_SLOT_STATE:
        information.append(slot_state_info(proposal, verdict))
    elif proposal.kind == KIND_DOCK_TARGET_REFINE:
        information.append(_generic_info(
            "m8.dockTargetRefine", proposal, verdict,
            "M8 dock-target refine (information only)"))
    elif proposal.kind == KIND_SPEED_REDUCE:
        information.append(_generic_info(
            "m8.speedReduce", proposal, verdict,
            "M8 speed-ceiling proposal (information only)"))
    elif proposal.kind == KIND_LOAD_ID:
        information.append(_generic_info(
            "m8.loadId", proposal, verdict,
            "M8 load identity (information only; loads[] is C4)"))
    elif proposal.kind == KIND_ANOMALY:
        information.append(_generic_info(
            "m8.anomaly", proposal, verdict,
            "M8 aisle anomaly (information only)"))
    return {"errors": errors, "information": information}


# Keys a VDA 2.1.0 errors[] / information[] item may carry. Used by
# tests to refuse invented fields (subset §9: no top-level extras).
ERROR_ITEM_KEYS = frozenset({
    "errorType", "errorLevel", "errorDescription", "errorHint",
    "errorReferences",
})
INFO_ITEM_KEYS = frozenset({
    "infoType", "infoLevel", "infoDescription", "infoReferences",
})
REFERENCE_KEYS = frozenset({"referenceKey", "referenceValue"})
ERROR_LEVELS = frozenset({"WARNING", "FATAL"})
INFO_LEVELS = frozenset({"INFO", "DEBUG"})
