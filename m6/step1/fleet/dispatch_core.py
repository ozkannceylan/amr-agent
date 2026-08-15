"""dispatch_core.py - master control's order building and bookkeeping. Pure.

Step 1's dispatcher is deliberately minimal: ONE vehicle, orders built from
station ids, no traffic. It exists to exercise the vehicle's client from the
real fleet side of the wire - step 3 grows it into assignment and traffic,
and everything it will say then is already said through these builders.

nodePosition comes from stations.py - THE one home for station truth - with
the station's own arrive_m as allowedDeviationXY, so the dispatcher and the
autopilot cannot disagree about what "arrived" means. sequenceIds run across
nodes and edges (0, 2, 4... nodes; 1, 3... edges) per the subset's order
table.
"""
import protocol


def transport_order(order_id, update_id, stations_tbl, station_ids, map_id):
    """An order dict (headerless) walking the given stations in sequence."""
    if not station_ids:
        raise ValueError("an order needs at least one station")
    for sid in station_ids:
        if sid not in stations_tbl:
            raise ValueError("unknown station: {}".format(sid))
    nodes, edges = [], []
    for i, sid in enumerate(station_ids):
        st = stations_tbl[sid]
        nodes.append({
            "nodeId": sid, "sequenceId": 2 * i, "released": True,
            "nodePosition": {"x": st["x"], "y": st["y"], "theta": st["yaw"],
                             "allowedDeviationXY": st["arrive_m"],
                             "mapId": map_id},
            "actions": []})
        if i:
            edges.append({
                "edgeId": "{}-{}".format(station_ids[i - 1], sid),
                "sequenceId": 2 * i - 1, "released": True,
                "startNodeId": station_ids[i - 1], "endNodeId": sid,
                "actions": []})
    return {"orderId": order_id, "orderUpdateId": update_id,
            "nodes": nodes, "edges": edges}


def instant_action(action_type, action_id, blocking="HARD", params=None):
    act = {"actionType": action_type, "actionId": action_id,
           "blockingType": blocking}
    if params:
        act["actionParameters"] = [{"key": k, "value": v}
                                   for k, v in params.items()]
    return {"actions": [act]}


class Dispatcher:
    """Header minting and per-vehicle bookkeeping for the fleet side."""

    def __init__(self, manufacturer):
        self.manufacturer = manufacturer
        self.headers = protocol.Headers()
        self.vehicles = {}              # serial -> {state, connection}
        self._order_n = 0

    def _ident(self, serial):
        return protocol.identity(self.manufacturer, serial)

    def next_order_id(self):
        self._order_n += 1
        return "TO-{:04d}".format(self._order_n)

    def order_message(self, serial, order, now_s):
        msg = protocol.header(self._ident(serial), self.headers,
                              "order", now_s)
        msg.update(order)
        return protocol.topic(self._ident(serial), "order"), msg

    def action_message(self, serial, actions, now_s):
        msg = protocol.header(self._ident(serial), self.headers,
                              "instantActions", now_s)
        msg.update(actions)
        return protocol.topic(self._ident(serial), "instantActions"), msg

    def on_state(self, msg):
        serial = msg.get("serialNumber")
        if serial:
            self.vehicles.setdefault(serial, {})["state"] = msg

    def on_connection(self, msg):
        serial = msg.get("serialNumber")
        if serial:
            self.vehicles.setdefault(serial, {})["connection"] = \
                msg.get("connectionState")

    def assignable(self, serial):
        """ONLINE, AUTOMATIC, and no pending nodes: may receive an order.

        The dispatcher's half of the mode contract - the HMI owns the
        mode, and a MANUAL vehicle is a vehicle someone is driving."""
        v = self.vehicles.get(serial, {})
        state = v.get("state")
        return (v.get("connection") == protocol.ONLINE
                and state is not None
                and state.get("operatingMode") == "AUTOMATIC"
                and not state.get("nodeStates"))
