"""Proposal/Verdict → VDA 2.1.0 errors[] / information[]. No ROS, no MQTT."""
import os
import re

from m8_core.contract import (
    Evidence,
    KIND_ANOMALY,
    KIND_DOCK_ABORT,
    KIND_DOCK_TARGET_REFINE,
    KIND_LOAD_ID,
    KIND_SLOT_STATE,
    KIND_SPEED_REDUCE,
    LoadEntry,
    PoseDelta,
    SENSOR_PALLET_CAM,
    SlotRow,
    make_proposal,
)
from m8_core.gate import PHASE_A, Gate, healthy
from m8_core.vda_map import (
    ERROR_ITEM_KEYS,
    ERROR_LEVEL_WARNING,
    ERROR_LEVELS,
    ERROR_TYPE_DOCK_ABORT,
    INFO_ITEM_KEYS,
    INFO_LEVEL_INFO,
    INFO_LEVELS,
    INFO_TYPE_SLOT_STATE,
    REFERENCE_KEYS,
    dock_abort_error,
    slot_state_info,
    to_vda,
)

_REPO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir))
_SUBSET = os.path.join(_REPO, "docs", "interfaces", "vda5050-subset.md")


def _ev(stamp=10.0):
    return Evidence(frame_id="cam-42", sim_stamp=stamp,
                    sensor_name=SENSOR_PALLET_CAM)


def _abort():
    return make_proposal(KIND_DOCK_ABORT, "stringer_in_path", 0.9, _ev(), 200)


def _slots():
    return make_proposal(
        KIND_SLOT_STATE,
        (SlotRow("R1-S5", "occupied"), SlotRow("R1-S6", "empty")),
        0.8, _ev(), 400)


def test_subset_file_is_where_the_field_names_live():
    text = open(_SUBSET, encoding="utf-8").read()
    # The mapper may only emit fields the subset already names.
    for name in ("errorType", "errorLevel", "errorDescription",
                 "errorHint", "errorReferences", "referenceKey",
                 "referenceValue", "WARNING", "FATAL"):
        assert name in text, name
    assert "information" in text
    assert "2.1.0" in text
    # information[] is an extension point, currently unused by M6.
    # M8 uses infoType / infoLevel — the spec names, not inventions.
    assert re.search(r"information\[\]", text)


def test_dock_abort_is_warning_m8_dock_abort():
    err = dock_abort_error(_abort())
    assert err["errorType"] == "m8.dockAbort"
    assert err["errorType"] == ERROR_TYPE_DOCK_ABORT
    assert err["errorLevel"] == "WARNING"
    assert err["errorLevel"] == ERROR_LEVEL_WARNING
    assert err["errorLevel"] in ERROR_LEVELS
    assert set(err) <= ERROR_ITEM_KEYS
    keys = {r["referenceKey"] for r in err["errorReferences"]}
    assert {"frameId", "reasonCode", "kind", "sensorName"} <= keys
    for ref in err["errorReferences"]:
        assert set(ref) == REFERENCE_KEYS
    reason = [r["referenceValue"] for r in err["errorReferences"]
              if r["referenceKey"] == "reasonCode"][0]
    assert reason == "stringer_in_path"
    # Not a safety event: FATAL would claim the vehicle is not in
    # running condition. R4: the F-PLC never hears this.
    assert err["errorLevel"] != "FATAL"


def test_slot_state_is_information_m8_slot_state():
    info = slot_state_info(_slots())
    assert info["infoType"] == "m8.slotState"
    assert info["infoType"] == INFO_TYPE_SLOT_STATE
    assert info["infoLevel"] == "INFO"
    assert info["infoLevel"] == INFO_LEVEL_INFO
    assert info["infoLevel"] in INFO_LEVELS
    assert set(info) <= INFO_ITEM_KEYS
    refs = {r["referenceKey"]: r["referenceValue"]
            for r in info["infoReferences"]}
    assert refs["slot:R1-S5"] == "occupied"
    assert refs["slot:R1-S6"] == "empty"
    assert refs["frameId"] == "cam-42"
    for ref in info["infoReferences"]:
        assert set(ref) == REFERENCE_KEYS


def test_to_vda_splits_abort_to_errors_and_slots_to_information():
    abort = to_vda(_abort())
    assert len(abort["errors"]) == 1
    assert abort["information"] == []
    assert abort["errors"][0]["errorType"] == "m8.dockAbort"

    slots = to_vda(_slots())
    assert slots["errors"] == []
    assert len(slots["information"]) == 1
    assert slots["information"][0]["infoType"] == "m8.slotState"


def test_phase_a_verdict_is_carried_as_a_reference_not_a_command():
    gate = Gate(phase=PHASE_A)
    proposal = _abort()
    verdict = gate.evaluate(proposal, now_s=10.05, health=healthy())
    assert verdict.accepted is False
    frag = to_vda(proposal, verdict)
    refs = {r["referenceKey"]: r["referenceValue"]
            for r in frag["errors"][0]["errorReferences"]}
    assert refs["verdict"] == "refused"
    assert refs["verdictReason"] == "phase_a_shadow"


def test_other_kinds_never_enter_errors():
    kinds = [
        make_proposal(KIND_DOCK_TARGET_REFINE, PoseDelta(0.01, 0.0, 0.0),
                      0.5, _ev(), 200),
        make_proposal(KIND_SPEED_REDUCE, 0.3, 0.5, _ev(), 200, leg_id="L1"),
        make_proposal(KIND_LOAD_ID, LoadEntry("P-9"), 0.5, _ev(), 200),
        make_proposal(KIND_ANOMALY, "aisle_blocked", 0.5, _ev(), 200),
    ]
    for proposal in kinds:
        frag = to_vda(proposal)
        assert frag["errors"] == [], proposal.kind
        assert frag["information"], proposal.kind
        assert all(item["infoType"].startswith("m8.")
                   for item in frag["information"])
        for item in frag["information"]:
            assert set(item) <= INFO_ITEM_KEYS
            # information[] is not a control channel: no errorLevel, no
            # FATAL, no cmd.
            assert "errorLevel" not in item
            assert "cmd" not in item


def test_fragments_carry_no_image_and_no_plc_fields():
    for proposal in (_abort(), _slots()):
        frag = to_vda(proposal)
        blob = str(frag).lower()
        for banned in ("image", "camera", "rgb", "depth", "opcua",
                       "forklift/", "cmd_vel", "torqueoff"):
            assert banned not in blob, banned
