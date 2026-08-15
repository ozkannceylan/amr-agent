"""The wire basics: topics, headers, timestamps, identity charset."""
import re

import pytest

import protocol


IDENT = protocol.identity("amragent", "FL1")


def test_topic_structure_matches_the_subset_doc():
    assert protocol.topic(IDENT, "order") == "uagv/v2/amragent/FL1/order"


def test_unknown_subtopic_is_refused():
    with pytest.raises(ValueError):
        protocol.topic(IDENT, "visualization")   # deliberately unused


@pytest.mark.parametrize("bad", ["a/b", "a$b", "", "türk", "a b"])
def test_identity_charset_is_enforced(bad):
    with pytest.raises(ValueError):
        protocol.identity("amragent", bad)
    with pytest.raises(ValueError):
        protocol.identity(bad, "FL1")


def test_header_ids_count_per_topic_independently():
    h = protocol.Headers()
    assert [protocol.header(IDENT, h, "state", 0.0)["headerId"]
            for _ in range(3)] == [0, 1, 2]
    # a second topic starts its own count, unmoved by the first
    assert protocol.header(IDENT, h, "connection", 0.0)["headerId"] == 0


def test_header_carries_identity_and_version():
    h = protocol.Headers()
    msg = protocol.header(IDENT, h, "state", 1723622400.0)
    assert msg["version"] == "2.1.0"
    assert msg["manufacturer"] == "amragent"
    assert msg["serialNumber"] == "FL1"


def test_timestamp_is_iso8601_utc_with_two_digit_fraction():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{2}Z",
                        protocol.stamp(1723622400.5))


def test_connection_payload_states():
    h = protocol.Headers()
    msg = protocol.connection_payload(IDENT, h, protocol.ONLINE, 0.0)
    assert msg["connectionState"] == "ONLINE"
    with pytest.raises(ValueError):
        protocol.connection_payload(IDENT, h, "UP", 0.0)


def test_parse_drops_what_is_not_a_json_object():
    assert protocol.parse(b"not json") is None
    assert protocol.parse(b"[1,2]") is None
    assert protocol.parse(b'{"a": 1}') == {"a": 1}
    assert protocol.parse(b"\xff\xfe") is None


def test_addressed_to_checks_both_identity_fields():
    msg = {"manufacturer": "amragent", "serialNumber": "FL1"}
    assert protocol.addressed_to(msg, IDENT)
    assert not protocol.addressed_to(dict(msg, serialNumber="FL2"), IDENT)
    assert not protocol.addressed_to(dict(msg, manufacturer="other"), IDENT)
