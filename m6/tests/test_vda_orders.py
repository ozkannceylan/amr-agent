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


def pick(action_id="o1:pick", kind="pick"):
    return {"actionId": action_id, "actionType": kind,
            "blockingType": "HARD", "actionParameters": []}


def test_a_pick_on_the_final_node_validates():
    """Item 3: the fork cycle rides the order as a standard node action
    on the station node - the last released node - and nowhere else."""
    msg = order()
    msg["nodes"][-1]["actions"] = [pick()]
    assert vo.validate_order(msg) == ""


def test_a_drop_on_the_final_node_validates():
    msg = order()
    msg["nodes"][-1]["actions"] = [pick("o1:drop", "drop")]
    assert vo.validate_order(msg) == ""


def test_an_action_on_an_intermediate_node_is_refused():
    """A waypoint is a place the pursuit may legitimately cut past
    outside its own radius (vda_orders' own skip rule) - an action
    there could be skipped with it. Stations are final nodes on this
    fleet, so the door only opens where arrival is decided."""
    bad = order()
    bad["nodes"][0]["actions"] = [pick()]
    assert "final" in vo.validate_order(bad)


def test_an_unknown_node_action_type_is_refused_at_the_door():
    bad = order()
    bad["nodes"][-1]["actions"] = [pick(kind="detectObject")]
    assert "detectObject" in vo.validate_order(bad)


def test_a_second_action_on_one_node_is_refused():
    bad = order()
    bad["nodes"][-1]["actions"] = [pick(), pick("o1:drop", "drop")]
    assert "one action" in vo.validate_order(bad)


def test_a_node_action_missing_its_id_is_refused():
    bad = order()
    bad["nodes"][-1]["actions"] = [{"actionType": "pick",
                                    "blockingType": "HARD"}]
    assert "actionId" in vo.validate_order(bad)


def test_an_edge_action_is_refused():
    bad = order()
    bad["edges"][0]["actions"] = [pick()]
    assert "edge" in vo.validate_order(bad)


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


def test_a_digit_storm_is_rejected_not_raised():
    """A 400-digit integer is legal JSON and a fine Python int, but no
    float holds it - math.isfinite raises on it. The door must answer,
    not crash."""
    bad = order()
    bad["nodes"][1]["nodePosition"]["x"] = 10 ** 400
    reason = vo.validate_order(bad)
    assert reason and "node 1" in reason and "x" in reason


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
    assert vo.accept_order(ok, None, False, "AUTOMATIC")[0] == "accept"
    assert vo.accept_order(ok, None, False, "MANUAL")[0] == "reject"
    assert vo.accept_order(
        ok, order(orderId="other"), True, "AUTOMATIC")[0] == "reject"
    assert vo.accept_order(ok, order(), True, "AUTOMATIC")[0] == "ignore"
    upd = order(orderUpdateId=1)
    assert vo.accept_order(upd, None, False, "AUTOMATIC")[0] == "reject"


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


# ---- base extension: VDA 5050 s.6.6, the M6.4 stitch ----


def chain(released, total=5, update_id=0, order_id="o1"):
    """A straight run of `total` nodes 2 m apart; the first `released`
    are base, the rest horizon - and their edges with them."""
    nodes, edges = [], []
    for i in range(total):
        nodes.append({"nodeId": "n{}".format(i), "sequenceId": 2 * i,
                      "released": i < released, "actions": [],
                      "nodePosition": {"x": 2.0 * i, "y": 0.0,
                                       "mapId": "warehouse"}})
        if i:
            edges.append({"edgeId": "e{}".format(i - 1),
                          "sequenceId": 2 * i - 1, "released": i < released,
                          "startNodeId": "n{}".format(i - 1),
                          "endNodeId": "n{}".format(i), "actions": []})
    return {"orderId": order_id, "orderUpdateId": update_id,
            "nodes": nodes, "edges": edges}


@pytest.mark.parametrize("released,total", [(1, 1), (2, 5), (5, 5)])
def test_the_chain_helper_builds_valid_orders(released, total):
    """The stitching tests are only worth something if what they feed
    the door would otherwise be accepted."""
    assert vo.validate_order(chain(released, total=total)) == ""


def test_a_base_may_grow_at_the_far_end():
    assert vo.accept_order(chain(3, update_id=1), chain(2),
                           True, "AUTOMATIC") == ("extend", "")


def test_a_horizon_node_may_be_released_and_more_appended():
    """n3 was horizon and is now base; n4 and n5 are new. Nothing the
    truck has already been told to drive moved."""
    assert vo.accept_order(chain(6, total=6, update_id=1),
                           chain(3, total=4),
                           True, "AUTOMATIC") == ("extend", "")


def test_only_the_very_next_update_id_extends():
    verdict, reason = vo.accept_order(chain(3, update_id=2), chain(2),
                                      True, "AUTOMATIC")
    assert verdict == "reject"
    assert "orderUpdateId" in reason and "1" in reason


def test_a_released_node_that_moved_is_refused():
    upd = chain(3, update_id=1)
    upd["nodes"][1]["nodePosition"]["x"] = 99.0
    verdict, reason = vo.accept_order(upd, chain(2), True, "AUTOMATIC")
    assert verdict == "reject" and "already driven" in reason


def test_a_released_node_that_was_renamed_is_refused():
    upd = chain(3, update_id=1)
    upd["nodes"][1]["nodeId"] = "elsewhere"
    upd["edges"][0]["endNodeId"] = "elsewhere"
    upd["edges"][1]["startNodeId"] = "elsewhere"
    assert vo.validate_order(upd) == ""      # the door itself is happy
    verdict, reason = vo.accept_order(upd, chain(2), True, "AUTOMATIC")
    assert verdict == "reject" and "already driven" in reason


def test_a_released_node_may_not_become_horizon():
    verdict, reason = vo.accept_order(chain(1, update_id=1), chain(2),
                                      True, "AUTOMATIC")
    assert verdict == "reject" and "already driven" in reason


def test_a_released_node_may_not_vanish():
    verdict, reason = vo.accept_order(chain(1, total=1, update_id=1),
                                      chain(2), True, "AUTOMATIC")
    assert verdict == "reject" and "already driven" in reason


def test_there_is_nothing_to_extend_when_nothing_executes():
    """The order is held after a broker bounce but the truck is standing:
    a longer base is not something to stitch onto a drive that is not
    running."""
    verdict, reason = vo.accept_order(chain(3, update_id=1), chain(2),
                                      False, "AUTOMATIC")
    assert verdict == "reject" and "executing" in reason


def test_an_update_to_an_order_we_never_had_is_refused():
    verdict, reason = vo.accept_order(chain(3, update_id=1), None,
                                      False, "AUTOMATIC")
    assert verdict == "reject" and reason


def test_an_extension_to_a_manual_vehicle_is_refused():
    """Dropping to teleop does not make the update legal - the mode is
    the vehicle's answer to every order, stitch or not."""
    verdict, reason = vo.accept_order(chain(3, update_id=1), chain(2),
                                      True, "MANUAL")
    assert verdict == "reject" and "AUTOMATIC" in reason


def test_the_same_update_delivered_twice_is_silence():
    cur = chain(3, update_id=1)
    again = chain(3, update_id=1)
    assert vo.accept_order(again, cur, True, "AUTOMATIC") == (
        "ignore", "duplicate delivery")
