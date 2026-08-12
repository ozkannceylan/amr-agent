"""sensor_link.py's wire format. No socket is opened."""
import json

import sensor_link

_CLEAR = {"pf": True, "wf": True, "level": "SAFE"}


def _fields(pf, wf, right=None, left=None):
    return json.dumps({"case": 3,
                       "back": {"pf": pf, "wf": wf, "level": "SAFE"},
                       "right": dict(_CLEAR) if right is None else right,
                       "left": dict(_CLEAR) if left is None else left,
                       "ts": 1.0})


def _enc(a=400, b=402):
    return json.dumps({"a": a, "b": b, "healthy": True, "ts": 1.0})


def test_payload_carries_exactly_the_nine_wire_keys():
    msg = json.loads(sensor_link.payload(_fields(True, False), _enc()).decode())
    assert set(msg) == {"pf", "wf", "pf_right", "wf_right",
                       "pf_left", "wf_left", "enc_a", "enc_b", "ts"}
    assert msg["pf"] is True and msg["wf"] is False
    assert msg["enc_a"] == 400 and msg["enc_b"] == 402


def test_all_three_scanners_reach_the_wire():
    # Owner instruction 2026-08-12: PF_OSSD_right/left and WF_Clear_right/
    # left are configured on the F-DI, so right and left leave HMI-only.
    msg = json.loads(sensor_link.payload(
        _fields(True, True,
                right={"pf": False, "wf": True},
                left={"pf": True, "wf": False}), _enc()).decode())
    assert msg["pf_right"] is False and msg["wf_right"] is True
    assert msg["pf_left"] is True and msg["wf_left"] is False


def test_a_report_without_back_sends_nothing():
    assert sensor_link.payload(
        json.dumps({"left": dict(_CLEAR), "right": dict(_CLEAR),
                    "ts": 1.0}), _enc()) is None


def test_a_report_without_right_or_left_sends_nothing():
    # A missing device must not default to False on the wire: sending
    # nothing lets step5.py's one staleness rule trip ALL six inputs
    # together instead of pairing fresh back verdicts with invented ones.
    report = json.loads(_fields(True, True))
    del report["right"]
    assert sensor_link.payload(json.dumps(report), _enc()) is None
    report = json.loads(_fields(True, True))
    del report["left"]
    assert sensor_link.payload(json.dumps(report), _enc()) is None


def test_unparseable_fields_send_nothing():
    assert sensor_link.payload("{garbage", _enc()) is None


def test_unparseable_encoders_send_nothing():
    assert sensor_link.payload(_fields(True, True), "{garbage") is None


def test_a_non_boolean_verdict_sends_nothing():
    # Sending nothing is safe: step5.py's own timeout then trips within
    # SENSOR_STALE_S. Sending a truthy non-bool would enable the plant.
    bad = json.dumps({"back": {"pf": 1, "wf": False},
                      "right": dict(_CLEAR), "left": dict(_CLEAR), "ts": 1.0})
    assert sensor_link.payload(bad, _enc()) is None
    bad = json.dumps({"back": {"pf": True, "wf": "clear"},
                      "right": dict(_CLEAR), "left": dict(_CLEAR), "ts": 1.0})
    assert sensor_link.payload(bad, _enc()) is None


def test_a_non_boolean_side_verdict_sends_nothing():
    assert sensor_link.payload(
        _fields(True, True, right={"pf": 1, "wf": True}), _enc()) is None
    assert sensor_link.payload(
        _fields(True, True, left={"pf": True, "wf": "clear"}),
        _enc()) is None


def test_an_absent_encoder_channel_sends_nothing():
    # encoder_link reports a stale channel as null rather than as zero.
    # Zero would say "stopped" about a vehicle that may be moving, so the
    # whole datagram is withheld and step5.py's timeout trips instead.
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
