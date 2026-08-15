"""The dispatcher's builders and its half of the mode contract."""
import pytest

import dispatch_core
import order_core
import protocol
from stations import STATIONS


def test_transport_order_walks_the_subset_shape():
    order = dispatch_core.transport_order(
        "TO-1", 0, STATIONS, ["S7", "S3"], "warehouse")
    assert [n["sequenceId"] for n in order["nodes"]] == [0, 2]
    assert [e["sequenceId"] for e in order["edges"]] == [1]
    edge = order["edges"][0]
    assert (edge["startNodeId"], edge["endNodeId"]) == ("S7", "S3")
    pos = order["nodes"][0]["nodePosition"]
    assert pos["x"] == STATIONS["S7"]["x"]
    assert pos["allowedDeviationXY"] == STATIONS["S7"]["arrive_m"]
    assert pos["mapId"] == "warehouse"


def test_built_orders_are_accepted_by_the_vehicle_book():
    # the two ends of the wire agree, by construction and by this test
    book = order_core.OrderBook(STATIONS)
    order = dispatch_core.transport_order(
        "TO-1", 0, STATIONS, ["S7", "S3", "S1"], "warehouse")
    assert book.receive(order) == "accepted"
    assert book.target() == "S7"


def test_unknown_station_refused_at_the_dispatcher_already():
    with pytest.raises(ValueError):
        dispatch_core.transport_order("TO-1", 0, STATIONS, ["S99"], "m")
    with pytest.raises(ValueError):
        dispatch_core.transport_order("TO-1", 0, STATIONS, [], "m")


def test_order_message_carries_header_and_topic():
    d = dispatch_core.Dispatcher("amragent")
    order = dispatch_core.transport_order(
        d.next_order_id(), 0, STATIONS, ["S7"], "warehouse")
    topic, msg = d.order_message("FL1", order, 0.0)
    assert topic == "uagv/v2/amragent/FL1/order"
    assert msg["headerId"] == 0 and msg["serialNumber"] == "FL1"
    assert msg["orderId"] == "TO-0001"


def test_assignable_needs_online_automatic_and_an_empty_plate():
    d = dispatch_core.Dispatcher("amragent")
    assert not d.assignable("FL1")                     # never heard of it
    d.on_connection({"serialNumber": "FL1",
                     "connectionState": protocol.ONLINE})
    assert not d.assignable("FL1")                     # no state yet
    d.on_state({"serialNumber": "FL1", "operatingMode": "AUTOMATIC",
                "nodeStates": []})
    assert d.assignable("FL1")
    d.on_state({"serialNumber": "FL1", "operatingMode": "MANUAL",
                "nodeStates": []})
    assert not d.assignable("FL1")                     # someone is driving
    d.on_state({"serialNumber": "FL1", "operatingMode": "AUTOMATIC",
                "nodeStates": [{"nodeId": "S7"}]})
    assert not d.assignable("FL1")                     # an order is pending
    d.on_connection({"serialNumber": "FL1",
                     "connectionState": protocol.BROKEN})
    assert not d.assignable("FL1")
