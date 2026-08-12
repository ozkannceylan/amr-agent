"""step3.py's pure functions. Nothing here opens the PLCSIM API."""
import json

import pytest

import step3


def test_status_payload_has_exactly_the_three_wire_keys():
    raw = step3.status_payload(True, False, 2, 12.5)
    msg = json.loads(raw.decode())
    assert set(msg) == {"estop_healthy", "motor", "case", "ts"}
    assert msg["estop_healthy"] is True
    assert msg["motor"] is False
    assert msg["ts"] == 12.5


def test_status_payload_emits_real_json_booleans_not_strings():
    msg = json.loads(step3.status_payload(False, True, 3, 0.0).decode())
    assert isinstance(msg["estop_healthy"], bool)
    assert isinstance(msg["motor"], bool)


def test_resolve_udp_target_honours_an_explicit_string():
    assert step3.resolve_udp_target("10.0.0.5") == "10.0.0.5"


def test_resolve_udp_target_takes_the_first_token_of_the_wsl_reply():
    # `wsl.exe hostname -I` answers with the eth0 address first and may
    # append the docker bridge. Only the first is reachable from Windows.
    assert step3._first_token("172.19.180.72 172.17.0.1 \n") == "172.19.180.72"


def test_first_token_rejects_empty_output():
    with pytest.raises(RuntimeError):
        step3._first_token("   \n")
