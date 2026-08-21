"""state_core.py - one VDA 5050 state message from the vehicle's snapshots.

Pure assembly: every value comes in as an argument and the caller owns every
clock. The snapshots are the step 5 wire formats, read as-is:

    nav    - the /auto/state JSON (state, goal, pose, ...), or None
    plc    - the /plc/status JSON (estop_healthy, motor, case, v_limit), or
             None - and None means FAILSAFE, exactly as every step 5
             consumer reads a silent status
    fields - the /forklift/safety/fields JSON report, or None

THE SAFETY STATE IS A REPORT, NOT A CHANNEL (subset section 5): it says what
the onboard chain already did. eStop=MANUAL whenever Motor is False, because
every latched demand on this vehicle - e-stop, field, encoder - clears only
through the panel's monitored reset; the dispatcher cannot tell WHICH demand
latched from here and does not need to: it stops assigning and alerts.

THE BATTERY IS MODELED and the factsheet says so. There is no battery in the
simulation; charge is a config constant and `charging` follows the modeled
start/stopCharging actions. It exists because batteryState is a required
object, and inventing a discharge curve would be decoration pretending to be
measurement.
"""

AUTOMATIC, MANUAL = "AUTOMATIC", "MANUAL"
E_STOP_NONE, E_STOP_MANUAL = "NONE", "MANUAL"

DRIVING_STATES = ("EN-ROUTE",)          # nav_core states that mean motion


def operating_mode(hmi_mode):
    """auto -> AUTOMATIC, everything else - teleop, unknown, silence -
    MANUAL. The dispatcher only assigns to AUTOMATIC (subset section 5)."""
    return AUTOMATIC if hmi_mode == "auto" else MANUAL


def field_violation(fields):
    """True when any scanner's protective field reads violated.

    The report's scanner entries are the dict values that carry a `pf`
    key; a missing or empty report is True - a chain that has said
    nothing must not be reported clear (the step 5 failsafe rule)."""
    if not isinstance(fields, dict):
        return True
    verdicts = [v.get("pf") for v in fields.values()
                if isinstance(v, dict) and "pf" in v]
    if not verdicts:
        return True
    return any(v is not True for v in verdicts)


def safety_state(plc, fields):
    motor = bool(plc and plc.get("motor") is True)
    return {"eStop": E_STOP_NONE if motor else E_STOP_MANUAL,
            "fieldViolation": field_violation(fields)}


def agv_position(nav, map_id):
    pose = (nav or {}).get("pose")
    if not (isinstance(pose, (list, tuple)) and len(pose) == 3):
        return {"x": 0.0, "y": 0.0, "theta": 0.0, "mapId": map_id,
                "positionInitialized": False}
    return {"x": float(pose[0]), "y": float(pose[1]),
            "theta": float(pose[2]), "mapId": map_id,
            "positionInitialized": True}


def build_state(header, book, actions, nav, plc, fields,
                hmi_mode, paused, battery, map_id):
    """The state topic payload (subset section 5). `header` comes from
    protocol.header(); `book` is the OrderBook, `actions` the ActionBook."""
    nav_state = (nav or {}).get("state")
    msg = dict(header)
    msg.update({
        "orderId": book.order_id,
        "orderUpdateId": book.update_id,
        "lastNodeId": book.last_node_id,
        "lastNodeSequenceId": book.last_seq,
        "nodeStates": book.node_states(),
        "edgeStates": book.edge_states(),
        "driving": nav_state in DRIVING_STATES,
        "paused": bool(paused),
        "newBaseRequest": book.new_base_request(),
        "agvPosition": agv_position(nav, map_id),
        "batteryState": {"batteryCharge": float(battery["charge_pct"]),
                         "charging": bool(battery["charging"])},
        "operatingMode": operating_mode(hmi_mode),
        "errors": list(book.errors),
        "actionStates": actions.action_states(),
        "safetyState": safety_state(plc, fields),
    })
    return msg
