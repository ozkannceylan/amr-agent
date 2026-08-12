"""The shared /plc/status contract. No ROS graph is started."""
import pytest

import status_contract


def test_parse_status_reads_a_good_packet():
    msg = status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": 2, "ts": 3.0}')
    assert msg == {"estop_healthy": True, "motor": True, "case": 2, "ts": 3.0}


def test_parse_status_rejects_malformed_json():
    assert status_contract.parse_status(b'{not json') is None


def test_parse_status_rejects_a_packet_missing_a_required_key():
    # A truncated or future-format packet must not be read as healthy.
    assert status_contract.parse_status(b'{"estop_healthy": true}') is None


def test_parse_status_rejects_a_non_boolean_motor():
    # JSON 1 and "off" are both TRUTHY, so `not motor` would publish demand
    # False and release the STO contactor on a packet the wire contract
    # calls invalid. isinstance(1, bool) is False, which is the direction
    # needed; isinstance(True, int) also being True does not weaken it,
    # because the test is against bool and not against int.
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": 1, "case": 3, "ts": 0.0}') is None
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": "off", "case": 3, "ts": 0.0}') is None


def test_parse_status_rejects_a_non_boolean_estop_healthy():
    assert status_contract.parse_status(
        b'{"estop_healthy": 1, "motor": true, "case": 3, "ts": 0.0}') is None


def test_failsafe_is_tripped_in_both_fields():
    assert status_contract.FAILSAFE["estop_healthy"] is False
    assert status_contract.FAILSAFE["motor"] is False


def test_failsafe_cannot_be_rewritten_by_a_consumer():
    # hmi_node binds FAILSAFE BY REFERENCE, so while it was a plain dict
    # one item assignment anywhere in the process rewrote the fail-safe
    # state for every consumer at once - and plc_link's dict(FAILSAFE)
    # copies would then have copied the corrupted value. The read-only
    # view makes that a loud TypeError instead of a silent enable.
    with pytest.raises(TypeError):
        status_contract.FAILSAFE["motor"] = True
    assert status_contract.FAILSAFE["motor"] is False
    # and it is still copyable, which is how plc_link takes a working one
    assert dict(status_contract.FAILSAFE) == {
        "estop_healthy": False, "motor": False, "case": 3, "ts": 0.0}


def test_is_stale_is_false_inside_the_window():
    assert status_contract.is_stale(10.0, 10.4, 0.5) is False


def test_is_stale_is_true_at_the_window():
    assert status_contract.is_stale(10.0, 10.5, 0.5) is True


def test_is_stale_is_true_before_the_first_packet():
    # last_rx of None means nothing has ever arrived.
    assert status_contract.is_stale(None, 10.0, 0.5) is True


def test_parse_status_rejects_a_packet_with_no_case():
    # `case` joined the contract in Step 2. A Step 1 sender is not a Step 2
    # one, and field_eval would otherwise get no field pair at all.
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "ts": 1.0}') is None


def test_parse_status_rejects_a_non_integer_case():
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": "2", "ts": 1.0}') is None


def test_parse_status_rejects_a_boolean_case():
    # isinstance(True, int) is True in Python, so `true` would sneak through
    # a bare int check and be read as case 1.
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": true, "ts": 1.0}') is None


def test_failsafe_carries_the_largest_field_case():
    # Not knowing the case means assuming the most demanding one.
    assert status_contract.FAILSAFE["case"] == 3
