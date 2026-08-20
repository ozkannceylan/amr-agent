"""plc_link.py's own constant. No ROS graph is started.

The parser, the staleness rule and FAILSAFE moved to status_contract.py
and are tested there. What is left here is what belongs to this NODE:
STALE_S, the UDP receive timeout, which is a different constant from the
contract's STATUS_STALE_S and is on a different clock.
"""
import plc_link
from status_contract import is_stale


def test_the_udp_window_is_the_configured_constant():
    # Passes plc_link.STALE_S explicitly, exactly as the node's tick()
    # does, so these pin the CONSTANT. Every is_stale test in
    # test_status_contract.py passes a window of its own and would stay
    # green if this constant were edited to a wrong value.
    #
    # The base is 0.0 so the subtraction is EXACT. From a base of 10.0 it
    # is not: 10.28 - 10.0 is 0.27999999999999936, just under the window,
    # so that assertion would pin the opposite answer for a reason that
    # has nothing to do with this node.
    assert is_stale(0.0, 0.28, plc_link.STALE_S) is True
    assert is_stale(0.0, 0.27, plc_link.STALE_S) is False


def test_the_udp_window_trips_on_the_sixth_tick_and_not_the_fifth():
    # What the timing budget actually rests on. The node compares two TICK
    # timestamps, so the elapsed value tested is a multiple of the 0.05 s
    # period: 5 ticks must not trip and 6 ticks must, with margin at both
    # ends rather than on a boundary. This is what a return to an exact
    # multiple of the tick (0.25 or 0.30) would break - and 0.25 is
    # exactly the value STATUS_STALE_S carries, so merging the two
    # constants breaks it too.
    assert is_stale(0.0, 0.25, plc_link.STALE_S) is False
    assert is_stale(0.0, 0.30, plc_link.STALE_S) is True
