"""instantActions: effects out, actionStates kept, the unsupported refused."""
import actions_core


def msg(*actions):
    return {"actions": [
        {"actionId": aid, "actionType": atype, "blockingType": "HARD"}
        for aid, atype in actions]}


def test_pause_and_resume_return_their_effects():
    b = actions_core.ActionBook()
    assert b.receive(msg(("a1", "startPause"))) == [("pause", True)]
    assert b.receive(msg(("a2", "stopPause"))) == [("pause", False)]
    assert [s["actionStatus"] for s in b.action_states()] == \
        ["FINISHED", "FINISHED"]


def test_cancel_and_requests_map_to_their_effects():
    b = actions_core.ActionBook()
    effects = b.receive(msg(("a1", "cancelOrder"), ("a2", "stateRequest"),
                            ("a3", "factsheetRequest")))
    assert effects == [("cancel", None), ("state", None),
                       ("factsheet", None)]


def test_charging_actions_drive_the_modeled_battery_flag():
    b = actions_core.ActionBook()
    assert b.receive(msg(("a1", "startCharging"))) == [("charging", True)]
    assert b.receive(msg(("a2", "stopCharging"))) == [("charging", False)]


def test_unsupported_action_fails_and_names_the_factsheet():
    b = actions_core.ActionBook()
    assert b.receive(msg(("a1", "pick"))) == []
    state = b.action_states()[0]
    assert state["actionStatus"] == "FAILED"
    assert "factsheet" in state["resultDescription"]


def test_init_position_is_a_named_noop():
    b = actions_core.ActionBook()
    assert b.receive(msg(("a1", "initPosition"))) == []
    state = b.action_states()[0]
    assert state["actionStatus"] == "FINISHED"
    assert "ground truth" in state["resultDescription"]


def test_duplicate_action_id_is_processed_once():
    b = actions_core.ActionBook()
    assert b.receive(msg(("a1", "startPause"))) == [("pause", True)]
    assert b.receive(msg(("a1", "startPause"))) == []
    assert len(b.action_states()) == 1


def test_malformed_entries_are_dropped_without_state():
    b = actions_core.ActionBook()
    assert b.receive({"actions": ["nope", {"actionType": "startPause"}]}) == []
    assert b.receive({"actions": "nope"}) == []
    assert b.action_states() == []
