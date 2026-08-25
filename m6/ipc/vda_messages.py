"""vda_messages.py - the VDA 5050 wire builders, pure. No ROS, no MQTT.

Every field below is traceable to docs/interfaces/vda5050-subset.md
(M1); nothing is invented. The factsheet declares only the implemented
actions - the machine-readable statement must not advertise what would
FAIL (spec, recorded deviation from the M1 table's eight).

batteryState is an honest stub: the sim has no battery, the schema
requires the object, so it reports full-and-not-charging rather than a
number that pretends to drain.
"""
import time

MANUFACTURER = "amragent"
VERSION = "2.1.0"


def topic(vid, name):
    return "uagv/v2/{}/{}/{}".format(MANUFACTURER, vid, name)


def _stamp(now=None):
    t = time.time() if now is None else now
    ms = int((t - int(t)) * 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) \
        + ".{:03d}Z".format(ms)


class Counters:
    """headerId is a per-topic counter, +1 per sent message (M1 s.3)."""

    def __init__(self):
        self._n = {}

    def header(self, topic_name, vid, now=None):
        self._n[topic_name] = self._n.get(topic_name, 0) + 1
        return {"headerId": self._n[topic_name], "timestamp": _stamp(now),
                "version": VERSION, "manufacturer": MANUFACTURER,
                "serialNumber": vid}


def errors_and_safety(motor, estop_healthy, pf_violated):
    """M1 s.5: errors[] + safetyState, from what the PLC already did.

    Reporting only - by the time this runs the F-model has long since
    dropped Motor. eStop=MANUAL means an acknowledge is pending, which
    is what a latched demand or an unhealthy chain both mean here.
    """
    errors = []
    if not motor:
        errors.append({
            "errorType": "safetyStop", "errorLevel": "FATAL",
            "errorDescription": "drive enable is down - latched safety "
                                "demand or startup acknowledge pending",
            "errorReferences": []})
    safety = {"eStop": "NONE" if (motor and estop_healthy) else "MANUAL",
              "fieldViolation": bool(pf_violated)}
    return errors, safety


def any_pf_false(obj):
    """True when any 'pf' key anywhere in the parsed report is False."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "pf" and value is False:
                return True
            if any_pf_false(value):
                return True
    elif isinstance(obj, list):
        return any(any_pf_false(v) for v in obj)
    return False


def build_state(header, order_ctx, pose, driving, operating_mode,
                errors, safety, action_states):
    state = dict(header)
    state.update({
        "orderId": order_ctx.get("orderId", ""),
        "orderUpdateId": order_ctx.get("orderUpdateId", 0),
        "lastNodeId": order_ctx.get("lastNodeId", ""),
        "lastNodeSequenceId": order_ctx.get("lastNodeSequenceId", 0),
        "nodeStates": order_ctx.get("nodeStates", []),
        "edgeStates": order_ctx.get("edgeStates", []),
        "driving": bool(driving),
        "paused": False,
        "newBaseRequest": bool(order_ctx.get("newBaseRequest", False)),
        "agvPosition": {"x": pose[0], "y": pose[1], "theta": pose[2],
                        "mapId": "warehouse",
                        "positionInitialized": True},
        "batteryState": {"batteryCharge": 100.0, "charging": False},
        "operatingMode": operating_mode,
        "errors": errors,
        "actionStates": action_states,
        "safetyState": safety})
    return state


def build_factsheet(header, cfg):
    """Truthful for THIS vehicle: speed from config.yaml, size measured
    off model.sdf, labeled sim stubs only where neither file knows."""
    limits = cfg.get("limits", {})
    fs = dict(header)
    fs.update({
        "typeSpecification": {
            "seriesName": "forklift_ver2",
            "agvKinematic": "THREEWHEEL",
            "agvClass": "FORKLIFT",
            "maxLoadMass": 1000.0,          # sim stub, no load model
            "localizationTypes": ["NATURAL"],
            "navigationTypes": ["AUTONOMOUS"]},
        "physicalParameters": {
            "speedMin": 0.0,
            "speedMax": float(limits.get("traction_speed_max_mps", 1.5)),
            "accelerationMax": 1.0,          # sim stub
            "decelerationMax": 1.0,          # sim stub
            # Size is measured, not guessed: model.sdf owns the
            # geometry (config.yaml says so in its own header).
            #   width  0.90 = chassis box y, model.sdf:240 - the widest
            #          link on the truck (counterweight 0.80, mast 0.72).
            #   length 2.735 = counterweight front face 0.74 + 0.24/2
            #          (model.sdf:256-257) back to the fork tip at
            #          -1.35 - 1.05/2 (model.sdf:913, 922).
            #   heightMax 2.20 = carriage top 0.35 + 0.50/2
            #          (model.sdf:895, 904) lifted by mast_joint's full
            #          travel, config.yaml fork_travel_max_m 1.6. The
            #          static mast is lower, 2.05, so the raised
            #          carriage is what a doorway has to clear.
            "heightMax": 2.20, "width": 0.90, "length": 2.735},
        "protocolLimits": {
            "maxStringLens": {}, "maxArrayLens": {},
            "timing": {"minOrderInterval": 1.0, "minStateInterval": 0.5}},
        "protocolFeatures": {
            "optionalParameters": [
                {"parameter": "order.edge.maxSpeed",
                 "support": "NOT_SUPPORTED"}],
            "agvActions": [
                {"actionType": name, "actionScopes": ["INSTANT"]}
                for name in ("cancelOrder", "stateRequest",
                             "factsheetRequest")]
            + [{"actionType": name, "actionScopes": ["NODE"]}
               for name in ("pick", "drop")]},
        "agvGeometry": {},
        "loadSpecification": {"loadSets": []}})
    return fs


def connection_payload(header, state):
    payload = dict(header)
    payload["connectionState"] = state
    return payload
