"""The shared /plc/status contract. No ROS graph is started."""
import pytest

import status_contract


def test_parse_status_reads_a_good_packet():
    msg = status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": 2, "v_limit": 1500, "ts": 3.0}')
    assert msg == {"estop_healthy": True, "motor": True, "case": 2, "v_limit": 1500, "ts": 3.0}


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
        b'{"estop_healthy": true, "motor": 1, "case": 3, "v_limit": 1500, "ts": 0.0}') is None
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": "off", "case": 3, "v_limit": 1500, "ts": 0.0}') is None


def test_parse_status_rejects_a_non_boolean_estop_healthy():
    assert status_contract.parse_status(
        b'{"estop_healthy": 1, "motor": true, "case": 3, "v_limit": 1500, "ts": 0.0}') is None


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
        "estop_healthy": False, "motor": False, "case": 3,
        "v_limit": status_contract.V_LIMIT_CREEP_MM_S,
        "ts": 0.0}


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
        b'{"estop_healthy": true, "motor": true, "case": "2", "v_limit": 1500, "ts": 1.0}') is None


def test_parse_status_rejects_a_boolean_case():
    # isinstance(True, int) is True in Python, so `true` would sneak through
    # a bare int check and be read as case 1.
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": true, "v_limit": 1500, "ts": 1.0}') is None


def test_failsafe_carries_the_largest_field_case():
    # Not knowing the case means assuming the most demanding one.
    assert status_contract.FAILSAFE["case"] == 3


def test_parse_status_rejects_a_packet_with_no_v_limit():
    # v_limit joined the contract in Step 5. A Step 3 sender is not a
    # Step 5 one, and cmd_gate would otherwise have no permission to obey.
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": 1, "ts": 1.0}') is None


def test_parse_status_rejects_a_non_integer_v_limit():
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": 1,'
        b' "v_limit": "1500", "ts": 1.0}') is None


def test_failsafe_carries_the_creep_ceiling():
    # Not knowing the permission means assuming the slowest one.
    assert status_contract.FAILSAFE["v_limit"] == \
        status_contract.V_LIMIT_CREEP_MM_S


def test_speed_limit_passes_the_two_values_the_f_program_computes():
    assert status_contract.speed_limit_mm_s(1500) == 1500
    assert status_contract.speed_limit_mm_s(300) == 300


def test_an_implausible_speed_limit_narrows_to_creep():
    # A fault in the reading must never WIDEN a permission.
    for bad in (0, -1, -300, 3001, 32767, None, "1500", True):
        assert status_contract.speed_limit_mm_s(bad) == \
            status_contract.V_LIMIT_CREEP_MM_S


def test_step6_topic_names_are_absolute_and_distinct():
    names = (status_contract.HMI_CMD_TOPIC, status_contract.VEHICLE_CMD_TOPIC,
             status_contract.AUTO_CMD_TOPIC, status_contract.AUTO_GOAL_TOPIC,
             status_contract.AUTO_ROUTE_TOPIC,
             status_contract.AUTO_STATE_TOPIC, status_contract.MODE_TOPIC)
    assert all(n.startswith("/") for n in names)
    assert len(set(names)) == len(names)


def test_hmi_cmd_topic_is_the_historical_literal():
    # /hmi/cmd_vel predates this file; moving it here must not respell it.
    # M6.1 prefixes the vehicle id, so the historical spelling is now the
    # TAIL - and the constant must come from contract(), not from a second
    # literal here, which is the whole point of the table.
    assert status_contract.HMI_CMD_TOPIC.endswith("/hmi/cmd_vel")
    assert status_contract.HMI_CMD_TOPIC == \
        status_contract.contract(status_contract.VID)["hmi_cmd_topic"]


def test_mode_words_are_distinct_and_lowercase():
    assert status_contract.MODE_TELEOP == "teleop"
    assert status_contract.MODE_AUTO == "auto"
