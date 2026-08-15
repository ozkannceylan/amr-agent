"""protocol.py - VDA 5050 wire basics: identity, topics, headers, time.

The subset contract is docs/interfaces/vda5050-subset.md; every string and
rule here is that document's section 2 and 3 made executable. This is the
ONE home for VDA topic strings - no other file spells one out - so the
scheme cannot fork the way a hand-copied prefix would.

The clock is an argument everywhere. These functions never call time.time():
the shell owns the clock, the tests own a fake one, and a timestamp that
appears in a message is always the caller's now, not a second opinion.
"""
import json
import re
from datetime import datetime, timezone

VERSION = "2.1.0"          # full protocol version, header field `version`
INTERFACE = "uagv"         # topic level `interfaceName`
MAJOR = "v2"               # topic level `majorVersion`

TOPICS = ("order", "instantActions", "state", "connection", "factsheet")

# connection.connectionState values (subset section 7)
ONLINE, OFFLINE, BROKEN = "ONLINE", "OFFLINE", "CONNECTIONBROKEN"

# Topic levels allow A-Z a-z 0-9 _ . : - and nothing else (spec 6.3);
# in particular no `/` (it would fork the topic tree) and no `$`.
_NAME_RE = re.compile(r"^[A-Za-z0-9_.:\-]+$")


def valid_name(name):
    return isinstance(name, str) and bool(_NAME_RE.match(name))


def identity(manufacturer, serial):
    """The vehicle's wire identity, validated once at the door.

    Everything downstream trusts these strings, so a bad one must fail
    here - loudly, at startup - and not as a malformed topic later.
    """
    if not valid_name(manufacturer):
        raise ValueError("bad manufacturer: {!r}".format(manufacturer))
    if not valid_name(serial):
        raise ValueError("bad serialNumber: {!r}".format(serial))
    return {"manufacturer": manufacturer, "serialNumber": serial}


def topic(ident, sub):
    if sub not in TOPICS:
        raise ValueError("not a VDA topic: {!r}".format(sub))
    return "/".join((INTERFACE, MAJOR, ident["manufacturer"],
                     ident["serialNumber"], sub))


def stamp(now_s):
    """ISO 8601 UTC, `YYYY-MM-DDTHH:mm:ss.ffZ` (spec 6.1.2)."""
    dt = datetime.fromtimestamp(now_s, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + \
        "{:02d}Z".format(dt.microsecond // 10000)


class Headers:
    """Per-topic headerId counters: +1 per sent message, per topic.

    One instance per publisher. Keyed by the full topic string, so a
    dispatcher counting toward several vehicles cannot cross its streams.
    """

    def __init__(self):
        self._next = {}

    def take(self, key):
        n = self._next.get(key, 0)
        self._next[key] = n + 1
        return n


def header(ident, headers, sub, now_s):
    """The five common header fields (subset section 3)."""
    return {"headerId": headers.take(topic(ident, sub)),
            "timestamp": stamp(now_s),
            "version": VERSION,
            "manufacturer": ident["manufacturer"],
            "serialNumber": ident["serialNumber"]}


def connection_payload(ident, headers, state, now_s):
    if state not in (ONLINE, OFFLINE, BROKEN):
        raise ValueError("bad connectionState: {!r}".format(state))
    msg = header(ident, headers, "connection", now_s)
    msg["connectionState"] = state
    return msg


def parse(payload):
    """Decode one inbound MQTT payload, or None if it is not a JSON object.

    None, not an exception: a broken payload on a QoS-0 topic is dropped,
    exactly as the parser in status_contract.py drops a bad datagram.
    """
    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode()
        except UnicodeDecodeError:
            return None
    try:
        msg = json.loads(payload)
    except ValueError:
        return None
    return msg if isinstance(msg, dict) else None


def addressed_to(msg, ident):
    """True when the message header names this vehicle.

    The topic already routed it here; this is the belt to that brace. A
    dispatcher bug that publishes FL2's order on FL1's topic is dropped
    instead of driven.
    """
    return (msg.get("manufacturer") == ident["manufacturer"]
            and msg.get("serialNumber") == ident["serialNumber"])
