"""Order validation, acceptance and progress - the M1 section-4 rules."""
import pytest

import vda_orders as vo


def order(nodes=None, edges=None, **over):
    """A minimal valid two-node order; override to break it."""
    if nodes is None:
        nodes = [
            {"nodeId": "wp0", "sequenceId": 0, "released": True,
             "actions": [],
             "nodePosition": {"x": 0.0, "y": 0.0, "mapId": "warehouse"}},
            {"nodeId": "S4", "sequenceId": 2, "released": True,
             "actions": [],
             "nodePosition": {"x": 6.0, "y": -8.0, "mapId": "warehouse",
                              "allowedDeviationXY": 0.25}},
        ]
    if edges is None:
        edges = [{"edgeId": "e0", "sequenceId": 1, "released": True,
                  "startNodeId": "wp0", "endNodeId": "S4", "actions": []}]
    msg = {"orderId": "o1", "orderUpdateId": 0,
           "nodes": nodes, "edges": edges}
    msg.update(over)
    return msg


def test_a_valid_order_validates():
    assert vo.validate_order(order()) == ""


@pytest.mark.parametrize("missing", ["orderId", "orderUpdateId",
                                     "nodes", "edges"])
def test_missing_top_level_fields_are_named(missing):
    msg = order()
    del msg[missing]
    assert missing in vo.validate_order(msg)


def test_edges_must_join_the_nodes():
    bad = order()
    bad["edges"][0]["endNodeId"] = "S5"
    assert "join" in vo.validate_order(bad)


def test_sequence_ids_are_the_interleaved_rule():
    bad = order()
    bad["nodes"][1]["sequenceId"] = 3
    assert "sequenceId" in vo.validate_order(bad)


def test_node_position_is_mandatory_for_us():
    bad = order()
    del bad["nodes"][1]["nodePosition"]
    assert "nodePosition" in vo.validate_order(bad)


def test_released_after_horizon_is_refused():
    n = order()["nodes"]
    n[0]["released"] = False
    assert "horizon" in vo.validate_order(order(nodes=n)) \
        or "base" in vo.validate_order(order(nodes=n))


def test_node_actions_are_not_supported_yet():
    bad = order()
    bad["nodes"][0]["actions"] = [{"actionType": "pick"}]
    assert "unsupported" in vo.validate_order(bad)


@pytest.mark.parametrize("axis", ["x", "y"])
@pytest.mark.parametrize("value", [None, "abc", "6.0", float("nan"),
                                   float("inf"), True])
def test_a_coordinate_that_is_not_a_number_is_rejected(axis, value):
    """Present is not enough. A null, a string - even a string that looks
    like a number - or a NaN would validate, then crash the agent's
    callback or, worse, drive and crash mid-motion in Progress."""
    bad = order()
    bad["nodes"][1]["nodePosition"][axis] = value
    reason = vo.validate_order(bad)
    assert "node 1" in reason and axis in reason


def test_a_deviation_that_is_not_a_number_is_rejected():
    bad = order()
    bad["nodes"][1]["nodePosition"]["allowedDeviationXY"] = "0.25"
    reason = vo.validate_order(bad)
    assert "node 1" in reason and "allowedDeviationXY" in reason


def test_a_non_positive_deviation_still_validates():
    """Zero is a number, so it passes the door; released_route floors it."""
    ok = order()
    ok["nodes"][1]["nodePosition"]["allowedDeviationXY"] = 0
    assert vo.validate_order(ok) == ""


def test_accept_matrix():
    ok = order()
    assert vo.accept_order(ok, "", 0, False, "AUTOMATIC")[0] == "accept"
    assert vo.accept_order(ok, "", 0, False, "MANUAL")[0] == "reject"
    assert vo.accept_order(ok, "other", 0, True, "AUTOMATIC")[0] == "reject"
    assert vo.accept_order(ok, "o1", 0, True, "AUTOMATIC")[0] == "ignore"
    upd = order(orderUpdateId=1)
    assert vo.accept_order(upd, "", 0, False, "AUTOMATIC")[0] == "reject"


def test_released_route_splits_base_and_horizon():
    n = order()["nodes"] + [
        {"nodeId": "S5", "sequenceId": 4, "released": False, "actions": [],
         "nodePosition": {"x": 8.0, "y": -8.0, "mapId": "warehouse"}}]
    e = order()["edges"] + [
        {"edgeId": "e1", "sequenceId": 3, "released": False,
         "startNodeId": "S4", "endNodeId": "S5", "actions": []}]
    pts, arrive, rel, hor = vo.released_route(order(nodes=n, edges=e))
    assert pts == [(0.0, 0.0), (6.0, -8.0)]
    assert arrive == 0.25
    assert [x["nodeId"] for x in rel] == ["wp0", "S4"]
    assert [x["nodeId"] for x in hor] == ["S5"]


def test_a_zero_deviation_falls_back_to_the_default():
    """nav_core.on_route refuses arrive_m <= 0, so a master that sends a
    zero radius must not cost us the route - it gets the default."""
    n = order()["nodes"]
    n[-1]["nodePosition"]["allowedDeviationXY"] = 0
    _, arrive, _, _ = vo.released_route(order(nodes=n))
    assert arrive == 0.25


def test_progress_is_monotone_and_skips():
    _, _, rel, _ = vo.released_route(order())
    p = vo.Progress(rel)
    assert p.last_node() == ("", 0)
    assert p.update((6.0, -8.0)) is True      # jumped to the last node
    assert p.reached == 2
    assert p.last_node() == ("S4", 2)
    assert p.update((0.0, 0.0)) is False      # never backwards


def test_progress_complete_marks_everything():
    _, _, rel, _ = vo.released_route(order())
    p = vo.Progress(rel)
    p.complete()
    assert p.reached == 2 and p.last_node() == ("S4", 2)
