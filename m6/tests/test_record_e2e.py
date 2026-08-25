"""record_e2e's pure half: the sentences the film tells.

The wire pane is the one part of the E2E film a viewer actually READS,
so what each message renders as - and what stays silent - is pinned
here without a broker, a camera or ROS. main() owns all three.
"""
import os
import sys

import pytest

pytest.importorskip("paho.mqtt.client")

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in ("tools", "fleet"):
    sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", _sub)))

import record_e2e as e2e                            # noqa: E402


def test_an_order_reads_as_one_line_with_its_base_and_its_action():
    body = {"orderId": "ft-ab12cd34", "orderUpdateId": 0,
            "nodes": [{"released": True, "actions": []},
                      {"released": True, "actions": []},
                      {"released": False,
                       "actions": [{"actionId": "x", "actionType": "pick",
                                    "blockingType": "HARD"}]}],
            "edges": []}
    line = e2e.wire_line("uagv/v2/amragent/f1/order", body, "10:00:00")
    assert ">> f1" in line
    assert "ORDER ft-ab12cd34" in line
    assert "3 nodes (2 base)" in line
    assert "+pick" in line


def test_an_extension_says_extend_not_order():
    body = {"orderId": "ft-ab12cd34", "orderUpdateId": 2,
            "nodes": [{"released": True, "actions": []}], "edges": []}
    line = e2e.wire_line("uagv/v2/amragent/f2/order", body)
    assert "EXTEND upd 2" in line


def test_a_task_submission_names_the_operator():
    line = e2e.wire_line("fleet/task/submit",
                         {"taskId": "demo-1", "from": "S1", "to": "S8"},
                         "10:00:01")
    assert "TASK demo-1" in line and "S1 -> S8" in line
    assert "operator" in line


def test_a_plain_state_is_silence_and_a_change_is_a_line():
    """Four trucks at 2 s periods would be forty lines a minute of
    'still driving'; the tap speaks only on the edges a viewer can
    follow - arrival, and the fork cycle's phases."""
    tap = e2e.StateTap("f1")
    driving = {"orderId": "ft-1", "nodeStates": [{"nodeId": "S1"}],
               "actionStates": [{"actionId": "ft-1:pick",
                                 "actionType": "pick",
                                 "actionStatus": "WAITING"}]}
    first = tap.lines(driving, "t")
    assert any("pick WAITING" in ln for ln in first)
    assert tap.lines(driving, "t") == []          # nothing changed
    arrived = {"orderId": "ft-1", "nodeStates": [],
               "actionStates": [{"actionId": "ft-1:pick",
                                 "actionType": "pick",
                                 "actionStatus": "RUNNING"}]}
    lines = tap.lines(arrived, "t")
    assert any("arrived" in ln for ln in lines)
    assert any("pick RUNNING" in ln for ln in lines)
    done = {"orderId": "ft-1", "nodeStates": [],
            "actionStates": [{"actionId": "ft-1:pick",
                              "actionType": "pick",
                              "actionStatus": "FINISHED"}]}
    lines = tap.lines(done, "t")
    assert lines == ["t << f1  pick FINISHED"]


def test_an_error_is_always_worth_a_line():
    tap = e2e.StateTap("f3")
    body = {"orderId": "ft-9", "nodeStates": [{"nodeId": "x"}],
            "errors": [{"errorType": "pathBlocked",
                        "errorDescription": "a body in the path"}]}
    lines = tap.lines(body)
    assert any("! pathBlocked" in ln for ln in lines)


def test_a_connection_state_reads_plainly():
    line = e2e.wire_line("uagv/v2/amragent/f4/connection",
                         {"connectionState": "ONLINE"}, "c")
    assert line == "c << f4  ONLINE"
