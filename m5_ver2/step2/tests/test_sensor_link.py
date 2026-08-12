"""sensor_link.py's wire format. No socket is opened."""
import json

import sensor_link


def _fields(pf, wf):
    return json.dumps({"case": 3,
                       "back": {"pf": pf, "wf": wf, "level": "SAFE"},
                       "left": {}, "right": {}, "ts": 1.0})


def test_back_payload_carries_exactly_the_three_wire_keys():
    msg = json.loads(sensor_link.back_payload(_fields(True, False)).decode())
    assert set(msg) == {"pf", "wf", "ts"}
    assert msg["pf"] is True and msg["wf"] is False


def test_only_the_back_sensor_reaches_the_wire():
    # The F-PLC has one sensor input configured. Left and right are HMI-only.
    msg = json.loads(sensor_link.back_payload(_fields(True, True)).decode())
    assert "left" not in msg and "right" not in msg


def test_a_report_without_back_sends_nothing():
    assert sensor_link.back_payload(
        json.dumps({"left": {}, "ts": 1.0})) is None


def test_unparseable_input_sends_nothing():
    assert sensor_link.back_payload("{garbage") is None


def test_a_non_boolean_verdict_sends_nothing():
    # Sending nothing is safe: step2.py's own timeout then trips within
    # SENSOR_STALE_S. Sending a truthy non-bool would enable the plant.
    bad = json.dumps({"back": {"pf": 1, "wf": False}, "ts": 1.0})
    assert sensor_link.back_payload(bad) is None
    bad = json.dumps({"back": {"pf": True, "wf": "clear"}, "ts": 1.0})
    assert sensor_link.back_payload(bad) is None
