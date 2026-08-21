"""The wire builders - M1 sections 3, 5, 7, 8 as assertions."""
import re

import vda_messages as vm


def test_topic_root_is_the_m1_shape():
    assert vm.topic("f1", "order") == "uagv/v2/amragent/f1/order"


def test_headers_count_per_topic_and_stamp_utc_z():
    c = vm.Counters()
    h1 = c.header("state", "f2")
    h2 = c.header("state", "f2")
    h3 = c.header("connection", "f2")
    assert (h1["headerId"], h2["headerId"], h3["headerId"]) == (1, 2, 1)
    assert h1["version"] == "2.1.0"
    assert h1["manufacturer"] == "amragent"
    assert h1["serialNumber"] == "f2"
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", h1["timestamp"])


def test_errors_and_safety_mapping():
    errors, safety = vm.errors_and_safety(True, True, False)
    assert errors == [] and safety == {"eStop": "NONE",
                                       "fieldViolation": False}
    errors, safety = vm.errors_and_safety(False, True, True)
    assert errors[0]["errorLevel"] == "FATAL"
    assert safety["eStop"] == "MANUAL" and safety["fieldViolation"] is True


def test_any_pf_false_walks_nested_reports():
    report = {"ts": 1.0,
              "back": {"pf": True, "wf": False},
              "left": {"pf": False, "wf": True}}
    assert vm.any_pf_false(report) is True
    report["left"]["pf"] = True
    assert vm.any_pf_false(report) is False


def test_state_carries_every_required_field():
    c = vm.Counters()
    ctx = {"orderId": "o1", "orderUpdateId": 0,
           "lastNodeId": "wp0", "lastNodeSequenceId": 0,
           "nodeStates": [{"nodeId": "S4", "sequenceId": 2,
                           "released": True}],
           "edgeStates": [], "newBaseRequest": False}
    state = vm.build_state(
        c.header("state", "f1"), ctx, (1.0, 2.0, 0.5), True, "AUTOMATIC",
        [], {"eStop": "NONE", "fieldViolation": False}, [])
    for key in ("headerId", "timestamp", "version", "manufacturer",
                "serialNumber", "orderId", "orderUpdateId", "lastNodeId",
                "lastNodeSequenceId", "nodeStates", "edgeStates", "driving",
                "paused", "newBaseRequest", "agvPosition", "batteryState",
                "operatingMode", "errors", "actionStates", "safetyState"):
        assert key in state, key
    assert state["agvPosition"] == {
        "x": 1.0, "y": 2.0, "theta": 0.5, "mapId": "warehouse",
        "positionInitialized": True}
    assert state["batteryState"] == {"batteryCharge": 100.0,
                                     "charging": False}


def test_factsheet_is_truthful_and_minimal():
    c = vm.Counters()
    cfg = {"limits": {"traction_speed_max_mps": 1.5},
           "model": {"steer_limit_rad": 1.31}}
    fs = vm.build_factsheet(c.header("factsheet", "f1"), cfg)
    ts = fs["typeSpecification"]
    assert ts["agvClass"] == "FORKLIFT"
    assert ts["agvKinematic"] == "THREEWHEEL"
    assert ts["navigationTypes"] == ["AUTONOMOUS"]
    phys = fs["physicalParameters"]
    assert phys["speedMax"] == 1.5
    # The truck's real size, off model.sdf - not a round number that
    # would have a fleet planner refuse aisles this vehicle fits.
    assert (phys["width"], phys["length"], phys["heightMax"]) == (
        0.90, 2.735, 2.20)
    acts = {a["actionType"] for a in fs["protocolFeatures"]["agvActions"]}
    assert acts == {"cancelOrder", "stateRequest", "factsheetRequest"}


def test_connection_payload():
    c = vm.Counters()
    p = vm.connection_payload(c.header("connection", "f1"), "ONLINE")
    assert p["connectionState"] == "ONLINE"
