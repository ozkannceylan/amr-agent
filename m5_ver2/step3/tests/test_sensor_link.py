"""sensor_link.py's wire format. No socket is opened."""
import json

import sensor_link


def _fields(pf, wf):
    return json.dumps({"case": 3,
                       "back": {"pf": pf, "wf": wf, "level": "SAFE"},
                       "left": {}, "right": {}, "ts": 1.0})


def _enc(a=400, b=402):
    return json.dumps({"a": a, "b": b, "healthy": True, "ts": 1.0})


def test_payload_carries_exactly_the_five_wire_keys():
    msg = json.loads(sensor_link.payload(_fields(True, False), _enc()).decode())
    assert set(msg) == {"pf", "wf", "enc_a", "enc_b", "ts"}
    assert msg["pf"] is True and msg["wf"] is False
    assert msg["enc_a"] == 400 and msg["enc_b"] == 402


def test_only_the_back_sensor_reaches_the_wire():
    # The F-PLC has one sensor input configured. Left and right are HMI-only.
    msg = json.loads(sensor_link.payload(_fields(True, True), _enc()).decode())
    assert "left" not in msg and "right" not in msg


def test_a_report_without_back_sends_nothing():
    assert sensor_link.payload(
        json.dumps({"left": {}, "ts": 1.0}), _enc()) is None


def test_unparseable_fields_send_nothing():
    assert sensor_link.payload("{garbage", _enc()) is None


def test_unparseable_encoders_send_nothing():
    assert sensor_link.payload(_fields(True, True), "{garbage") is None


def test_a_non_boolean_verdict_sends_nothing():
    # Sending nothing is safe: step3.py's own timeout then trips within
    # SENSOR_STALE_S. Sending a truthy non-bool would enable the plant.
    bad = json.dumps({"back": {"pf": 1, "wf": False}, "ts": 1.0})
    assert sensor_link.payload(bad, _enc()) is None
    bad = json.dumps({"back": {"pf": True, "wf": "clear"}, "ts": 1.0})
    assert sensor_link.payload(bad, _enc()) is None


def test_an_absent_encoder_channel_sends_nothing():
    # encoder_link reports a stale channel as null rather than as zero.
    # Zero would say "stopped" about a vehicle that may be moving, so the
    # whole datagram is withheld and step3.py's timeout trips instead.
    assert sensor_link.payload(
        _fields(True, True),
        json.dumps({"a": None, "b": 402, "ts": 1.0})) is None


def test_a_boolean_encoder_value_sends_nothing():
    # isinstance(True, int) is True in Python; a JSON `true` must not be
    # written to the PLC as 1 mm/s.
    assert sensor_link.payload(
        _fields(True, True),
        json.dumps({"a": True, "b": 402, "ts": 1.0})) is None


def test_negative_speeds_survive():
    msg = json.loads(
        sensor_link.payload(_fields(True, True), _enc(-400, -398)).decode())
    assert msg["enc_a"] == -400 and msg["enc_b"] == -398
