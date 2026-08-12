"""step4.py's pure functions. Nothing here opens the PLCSIM API."""
import json

import pytest

import step4


def test_status_payload_has_exactly_the_five_wire_keys():
    raw = step4.status_payload(True, False, 2, 1500, 12.5)
    msg = json.loads(raw.decode())
    assert set(msg) == {"estop_healthy", "motor", "case", "v_limit", "ts"}
    assert msg["estop_healthy"] is True
    assert msg["motor"] is False
    assert msg["ts"] == 12.5


def test_status_payload_emits_real_json_booleans_not_strings():
    msg = json.loads(step4.status_payload(False, True, 3, 300, 0.0).decode())
    assert isinstance(msg["estop_healthy"], bool)
    assert isinstance(msg["motor"], bool)


def _sensor_msg(**overrides):
    msg = {"pf": True, "wf": True, "pf_right": True, "wf_right": True,
           "pf_left": True, "wf_left": False, "enc_a": 400, "enc_b": 402,
           "ts": 1.0}
    msg.update(overrides)
    return json.dumps(msg).encode()


def test_parse_sensor_accepts_the_nine_key_packet():
    msg = step4.parse_sensor(_sensor_msg())
    assert msg["pf_right"] is True and msg["wf_left"] is False


def test_parse_sensor_rejects_a_packet_missing_a_side_verdict():
    # The old five-key wire format must not pass: a sender that predates
    # the right/left inputs would leave them at whatever this loop held.
    old = {"pf": True, "wf": True, "enc_a": 400, "enc_b": 402, "ts": 1.0}
    assert step4.parse_sensor(json.dumps(old).encode()) is None


def test_parse_sensor_rejects_a_non_boolean_side_verdict():
    assert step4.parse_sensor(_sensor_msg(pf_left=1)) is None
    assert step4.parse_sensor(_sensor_msg(wf_right="clear")) is None


def test_resolve_udp_target_honours_an_explicit_string():
    assert step4.resolve_udp_target("10.0.0.5") == "10.0.0.5"


def test_resolve_udp_target_takes_the_first_token_of_the_wsl_reply():
    # `wsl.exe hostname -I` answers with the eth0 address first and may
    # append the docker bridge. Only the first is reachable from Windows.
    assert step4._first_token("172.19.180.72 172.17.0.1 \n") == "172.19.180.72"


def test_first_token_rejects_empty_output():
    with pytest.raises(RuntimeError):
        step4._first_token("   \n")
