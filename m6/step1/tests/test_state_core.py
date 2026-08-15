"""The state message: mappings from the step 5 snapshots, failsafe defaults."""
import actions_core
import order_core
import protocol
import state_core
from stations import STATIONS


IDENT = protocol.identity("amragent", "FL1")
BATTERY = {"charge_pct": 100.0, "charging": False}


def build(nav=None, plc=None, fields=None, mode="auto", paused=False,
          book=None):
    head = protocol.header(IDENT, protocol.Headers(), "state", 0.0)
    return state_core.build_state(
        head, book or order_core.OrderBook(STATIONS),
        actions_core.ActionBook(), nav, plc, fields, mode, paused,
        BATTERY, "warehouse")


def test_required_fields_are_all_present():
    msg = build()
    for key in ("orderId", "orderUpdateId", "lastNodeId",
                "lastNodeSequenceId", "nodeStates", "edgeStates", "driving",
                "batteryState", "operatingMode", "errors", "actionStates",
                "safetyState", "agvPosition", "paused", "newBaseRequest"):
        assert key in msg, key


def test_operating_mode_auto_is_automatic_everything_else_manual():
    assert state_core.operating_mode("auto") == "AUTOMATIC"
    assert state_core.operating_mode("teleop") == "MANUAL"
    assert state_core.operating_mode(None) == "MANUAL"


def test_driving_follows_en_route_only():
    assert build(nav={"state": "EN-ROUTE"})["driving"] is True
    for s in ("IDLE", "HOLD", "SAFETY-STOP", "ARRIVED", None):
        assert build(nav={"state": s})["driving"] is False


def test_silent_plc_reports_estop_manual_not_none():
    # None means FAILSAFE, exactly as every step 5 consumer reads silence
    assert build(plc=None)["safetyState"]["eStop"] == "MANUAL"
    assert build(plc={"motor": True})["safetyState"]["eStop"] == "NONE"
    assert build(plc={"motor": False})["safetyState"]["eStop"] == "MANUAL"


def test_field_violation_true_on_silence_and_on_any_pf():
    assert state_core.field_violation(None) is True
    assert state_core.field_violation({"case": 1}) is True   # no verdicts
    clear = {"case": 1, "back": {"pf": True, "wf": True}}
    assert state_core.field_violation(clear) is False
    tripped = {"case": 1, "back": {"pf": True}, "left": {"pf": False}}
    assert state_core.field_violation(tripped) is True


def test_position_uninitialized_until_a_pose_arrives():
    assert build()["agvPosition"]["positionInitialized"] is False
    msg = build(nav={"state": "IDLE", "pose": [1.0, 2.0, 0.5]})
    assert msg["agvPosition"] == {"x": 1.0, "y": 2.0, "theta": 0.5,
                                 "mapId": "warehouse",
                                 "positionInitialized": True}


def test_order_walk_is_reported():
    book = order_core.OrderBook(STATIONS)
    book.receive({"orderId": "TO-1", "orderUpdateId": 0, "edges": [],
                  "nodes": [{"nodeId": "S7", "sequenceId": 0,
                             "released": True, "actions": []}]})
    book.arrived("S7")
    msg = build(book=book)
    assert msg["orderId"] == "TO-1"
    assert msg["lastNodeId"] == "S7"
    assert msg["nodeStates"] == []
