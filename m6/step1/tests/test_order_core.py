"""The order book: acceptance rules, the walk, updates, cancellation."""
import order_core
from stations import STATIONS


def book():
    return order_core.OrderBook(STATIONS)


def order(order_id="TO-1", update_id=0, node_ids=("S7",), released=None,
          edges="auto"):
    released = released or [True] * len(node_ids)
    nodes = [{"nodeId": nid, "sequenceId": 2 * i, "released": released[i],
              "actions": []} for i, nid in enumerate(node_ids)]
    if edges == "auto":
        edges = [{"edgeId": "e{}".format(i), "sequenceId": 2 * i - 1,
                  "released": released[i], "startNodeId": node_ids[i - 1],
                  "endNodeId": node_ids[i], "actions": []}
                 for i in range(1, len(node_ids))]
    return {"orderId": order_id, "orderUpdateId": update_id,
            "nodes": nodes, "edges": edges}


def test_single_node_order_is_accepted_and_becomes_the_target():
    b = book()
    assert b.receive(order(node_ids=("S7",))) == "accepted"
    assert b.target() == "S7"
    assert b.errors == []


def test_unknown_station_is_rejected_with_a_validation_error():
    b = book()
    assert b.receive(order(node_ids=("S99",))) == "rejected"
    assert b.errors[0]["errorType"] == order_core.VALIDATION_ERROR
    assert b.target() is None


def test_released_after_horizon_is_rejected():
    b = book()
    msg = order(node_ids=("S7", "S3"), released=[False, True])
    assert b.receive(msg) == "rejected"


def test_the_walk_updates_last_node_and_shrinks_node_states():
    b = book()
    b.receive(order(node_ids=("S7", "S3")))
    assert len(b.node_states()) == 2 and len(b.edge_states()) == 1
    assert b.arrived("S7")
    assert (b.last_node_id, b.last_seq) == ("S7", 0)
    assert b.target() == "S3"
    assert len(b.node_states()) == 1 and len(b.edge_states()) == 1
    assert b.arrived("S3")
    assert b.target() is None and not b.active()
    assert b.node_states() == [] and b.edge_states() == []


def test_arrival_at_the_wrong_station_changes_nothing():
    b = book()
    b.receive(order(node_ids=("S7",)))
    assert not b.arrived("S3")
    assert b.target() == "S7"


def test_duplicate_update_id_is_ignored_silently():
    b = book()
    b.receive(order(update_id=0))
    assert b.receive(order(update_id=0)) == "ignored"
    assert b.errors == []


def test_backward_update_id_is_rejected():
    b = book()
    b.receive(order(update_id=2))
    assert b.receive(order(update_id=1)) == "rejected"
    assert b.errors[0]["errorType"] == order_core.ORDER_UPDATE_ERROR


def test_new_order_id_while_active_is_rejected():
    b = book()
    b.receive(order(order_id="TO-1"))
    assert b.receive(order(order_id="TO-2", node_ids=("S3",))) == "rejected"
    assert b.target() == "S7"          # the active order is untouched


def test_new_order_id_after_completion_is_accepted():
    b = book()
    b.receive(order(order_id="TO-1"))
    b.arrived("S7")
    assert b.receive(order(order_id="TO-2", node_ids=("S3",))) == "accepted"
    assert b.target() == "S3"


def test_update_stitches_at_the_last_reached_node():
    b = book()
    b.receive(order(order_id="TO-1", update_id=0, node_ids=("S7",)))
    b.arrived("S7")
    up = order(order_id="TO-1", update_id=1, node_ids=("S7", "S3"))
    assert b.receive(up) == "accepted"
    assert b.target() == "S3"          # the repeated stitch node is not redriven


def test_update_that_does_not_stitch_is_rejected():
    b = book()
    b.receive(order(order_id="TO-1", update_id=0, node_ids=("S7",)))
    b.arrived("S7")
    up = order(order_id="TO-1", update_id=1, node_ids=("S3",))
    assert b.receive(up) == "rejected"
    assert b.errors[0]["errorType"] == order_core.ORDER_UPDATE_ERROR


def test_horizon_nodes_are_held_not_driven():
    b = book()
    b.receive(order(node_ids=("S7", "S3"), released=[True, False]))
    assert b.target() == "S7"
    b.arrived("S7")
    assert b.target() is None          # horizon: plan only, drive nothing
    assert b.new_base_request()        # and the dispatcher is asked to release


def test_cancel_drops_pending_nodes_but_keeps_identity():
    b = book()
    b.receive(order(order_id="TO-1", node_ids=("S7", "S3")))
    b.cancel()
    assert b.target() is None
    assert b.node_states() == [] and b.edge_states() == []
    assert b.order_id == "TO-1"        # state still reports which order died


def test_rejection_errors_clear_on_the_next_accepted_order():
    b = book()
    b.receive(order(node_ids=("S99",)))
    assert b.errors
    assert b.receive(order(node_ids=("S7",))) == "accepted"
    assert b.errors == []
