"""plc_link.py's pure functions. No ROS graph is started."""
import plc_link


def test_parse_status_reads_a_good_packet():
    msg = plc_link.parse_status(b'{"estop_healthy": true, "motor": true, "ts": 3.0}')
    assert msg == {"estop_healthy": True, "motor": True, "ts": 3.0}


def test_parse_status_rejects_malformed_json():
    assert plc_link.parse_status(b'{not json') is None


def test_parse_status_rejects_a_packet_missing_a_required_key():
    # A truncated or future-format packet must not be read as healthy.
    assert plc_link.parse_status(b'{"estop_healthy": true}') is None


def test_parse_status_rejects_a_non_boolean_motor():
    # JSON 1 and "off" are both TRUTHY, so `not motor` would publish demand
    # False and release the STO contactor on a packet the wire contract
    # calls invalid. isinstance(1, bool) is False, which is the direction
    # needed; isinstance(True, int) also being True does not weaken it,
    # because the test is against bool and not against int.
    assert plc_link.parse_status(b'{"estop_healthy": true, "motor": 1, "ts": 0.0}') is None
    assert plc_link.parse_status(b'{"estop_healthy": true, "motor": "off", "ts": 0.0}') is None


def test_parse_status_rejects_a_non_boolean_estop_healthy():
    assert plc_link.parse_status(b'{"estop_healthy": 1, "motor": true, "ts": 0.0}') is None


def test_failsafe_is_tripped_in_both_fields():
    assert plc_link.FAILSAFE["estop_healthy"] is False
    assert plc_link.FAILSAFE["motor"] is False


def test_is_stale_is_false_inside_the_window():
    assert plc_link.is_stale(10.0, 10.4, 0.5) is False


def test_is_stale_is_true_at_the_window():
    assert plc_link.is_stale(10.0, 10.5, 0.5) is True


def test_is_stale_is_true_before_the_first_packet():
    # last_rx of None means nothing has ever arrived.
    assert plc_link.is_stale(None, 10.0, 0.5) is True


def test_is_stale_default_window_is_the_configured_constant():
    # Called with TWO arguments, so these pin STALE_S itself. Every test
    # above passes the window explicitly and would stay green if the
    # constant were edited to a wrong value; the node uses the default.
    assert plc_link.is_stale(10.0, 10.3) is True
    assert plc_link.is_stale(10.0, 10.29) is False
