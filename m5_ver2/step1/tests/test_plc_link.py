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
