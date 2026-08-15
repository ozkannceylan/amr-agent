"""The glue, end to end and pure - including the AT-09 shape (SC-12, SF-09):
broker lost mid-order -> controlled stop, order kept; broker back -> resume
with no operator reset anywhere in the transcript."""
import actions_core
import client_core
import protocol
from stations import STATIONS

CFG = {"map_id": "warehouse", "state_interval_s": 30.0,
       "battery_charge_pct": 100.0,
       "factsheet": {
           "series_name": "amr-forklift", "kinematic": "THREEWHEEL",
           "agv_class": "FORKLIFT", "max_load_mass_kg": 1500,
           "physical": {"speed_min_mps": 0.0, "speed_max_mps": 1.5,
                        "accel_max_mps2": 0.5, "decel_max_mps2": 0.8,
                        "height_m": 2.0, "width_m": 1.0, "length_m": 2.4},
           "min_order_interval_s": 0.5, "min_state_interval_s": 0.5}}


def client():
    c = client_core.Client(protocol.identity("amragent", "FL1"),
                           STATIONS, CFG)
    c.on_broker(True, 0.0)
    c.on_mode("auto", 0.0)
    return c


def order(node_ids=("S7",), order_id="TO-1", update_id=0):
    return {"manufacturer": "amragent", "serialNumber": "FL1",
            "orderId": order_id, "orderUpdateId": update_id, "edges": [],
            "nodes": [{"nodeId": n, "sequenceId": 2 * i, "released": True,
                       "actions": []} for i, n in enumerate(node_ids)]}


def actions(*pairs):
    return {"manufacturer": "amragent", "serialNumber": "FL1",
            "actions": [{"actionId": a, "actionType": t,
                         "blockingType": "HARD"} for a, t in pairs]}


def goals(effects):
    return [e[1] for e in effects if e[0] == "goal"]


def published(effects, sub):
    return [e[2] for e in effects if e[0] == "publish" and e[1] == sub]


def test_connect_publishes_online_factsheet_and_state():
    c = client_core.Client(protocol.identity("amragent", "FL1"),
                           STATIONS, CFG)
    out = c.on_broker(True, 0.0)
    assert published(out, "connection")[0]["connectionState"] == "ONLINE"
    fact = published(out, "factsheet")[0]
    assert [a["actionType"] for a in
            fact["protocolFeatures"]["agvActions"]] \
        == list(actions_core.SUPPORTED)
    assert published(out, "state")


def test_an_order_becomes_a_goal_and_arrival_walks_the_order():
    c = client()
    out = c.on_order(order(("S7", "S3")), 1.0)
    assert goals(out) == ["S7"]
    out = c.on_nav_state({"state": "ARRIVED", "goal": "S7"}, 2.0)
    assert goals(out) == ["S3"]
    assert published(out, "state")[0]["lastNodeId"] == "S7"
    out = c.on_nav_state({"state": "ARRIVED", "goal": "S3"}, 3.0)
    assert goals(out) == [""]          # order complete: nothing to drive
    assert not c.book.active()


def test_order_for_another_vehicle_is_dropped_silently():
    c = client()
    msg = dict(order(), serialNumber="FL2")
    assert c.on_order(msg, 1.0) == []
    assert c.book.order_id == ""


def test_at09_broker_lost_controlled_stop_order_kept_resume_without_reset():
    c = client()
    c.on_order(order(("S7",)), 1.0)
    out = c.on_broker(False, 2.0)      # the outage begins
    assert goals(out) == [""]          # controlled stop through /auto/goal
    assert c.book.target() == "S7"     # THE ORDER IS KEPT
    assert c.book.order_id == "TO-1"
    # during the outage nothing else is asked of the vehicle
    assert c.tick(10.0) == []
    out = c.on_broker(True, 20.0)      # supervision returns
    assert goals(out) == ["S7"]        # resume: same order, no reset step
    assert published(out, "connection")[0]["connectionState"] == "ONLINE"


def test_pause_parks_and_resume_reissues_the_goal():
    c = client()
    c.on_order(order(("S7",)), 1.0)
    out = c.on_instant_actions(actions(("a1", "startPause")), 2.0)
    assert goals(out) == [""]
    assert published(out, "state")[0]["paused"] is True
    out = c.on_instant_actions(actions(("a2", "stopPause")), 3.0)
    assert goals(out) == ["S7"]
    assert published(out, "state")[0]["paused"] is False


def test_cancel_order_stops_and_clears_pending_nodes():
    c = client()
    c.on_order(order(("S7",)), 1.0)
    out = c.on_instant_actions(actions(("a1", "cancelOrder")), 2.0)
    assert goals(out) == [""]
    assert published(out, "state")[0]["nodeStates"] == []


def test_mode_teleop_holds_the_goal_and_mode_auto_releases_it():
    c = client_core.Client(protocol.identity("amragent", "FL1"),
                           STATIONS, CFG)
    c.on_broker(True, 0.0)
    c.on_mode("teleop", 0.0)
    out = c.on_order(order(("S7",)), 1.0)
    assert goals(out) == []            # accepted, held: MANUAL vehicles wait
    assert c.book.target() == "S7"
    out = c.on_mode("auto", 2.0)
    assert goals(out) == ["S7"]


def test_state_request_and_factsheet_request_publish_now():
    c = client()
    out = c.on_instant_actions(actions(("a1", "stateRequest")), 1.0)
    assert published(out, "state")
    out = c.on_instant_actions(actions(("a2", "factsheetRequest")), 2.0)
    assert published(out, "factsheet") and published(out, "state")


def test_tick_republishes_state_on_the_interval_floor():
    c = client()
    assert c.tick(1.0) == []           # connect already published at 0.0
    out = c.tick(31.0)
    assert published(out, "state")
    assert c.tick(32.0) == []


def test_shutdown_says_offline_and_zeroes_the_goal():
    c = client()
    c.on_order(order(("S7",)), 1.0)
    out = c.shutdown(2.0)
    assert goals(out) == [""]
    assert published(out, "connection")[0]["connectionState"] == "OFFLINE"


def test_charging_actions_reach_the_battery_state():
    c = client()
    out = c.on_instant_actions(actions(("a1", "startCharging")), 1.0)
    assert published(out, "state")[0]["batteryState"]["charging"] is True
