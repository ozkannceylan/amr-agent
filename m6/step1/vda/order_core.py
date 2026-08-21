"""order_core.py - accept, hold and walk one VDA 5050 order. No ROS in the room.

The vehicle is AUTONOMOUS (factsheet navigationTypes): an order's nodes are
STATIONS from stations.py, addressed by nodeId, and the onboard router plans
the path between them - the order carries no trajectory and this file reads
no nodePosition. Validation is therefore membership: a nodeId the vehicle
does not know is a rejected order, not a guess.

REJECTION IS A REPORT, NOT AN EXCEPTION. A bad order leaves the current
order untouched and lands as an error entry (subset section 5, errors[])
that rides the state topic until the next accepted order clears it. The
dispatcher reads errors; the truck never sees the bad order at all.

Nothing here reacts to Motor, fields or the e-stop: nav_core's SAFETY-STOP
holds the route through a demand, and this book holds the order the same
way, one level further out.
"""
VALIDATION_ERROR = "validationError"
ORDER_UPDATE_ERROR = "orderUpdateError"


def _error(etype, desc, order_id):
    return {"errorType": etype, "errorLevel": "WARNING",
            "errorDescription": desc,
            "errorReferences": [{"referenceKey": "orderId",
                                 "referenceValue": order_id}]}


def _shape_ok(msg, stations):
    """Structural validity per the subset's order table, or a reason."""
    if not isinstance(msg.get("orderId"), str) or not msg["orderId"]:
        return "orderId missing"
    u = msg.get("orderUpdateId")
    if not isinstance(u, int) or isinstance(u, bool) or u < 0:
        return "orderUpdateId missing"
    nodes, edges = msg.get("nodes"), msg.get("edges")
    if not isinstance(nodes, list) or not nodes:
        return "nodes empty"
    if not isinstance(edges, list):
        return "edges missing"
    seen_horizon = False
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("nodeId"), str):
            return "malformed node"
        for key in ("sequenceId", "released", "actions"):
            if key not in n:
                return "node missing {}".format(key)
        if n["nodeId"] not in stations:
            return "unknown station {}".format(n["nodeId"])
        if n["released"]:
            if seen_horizon:            # base after horizon: no such order
                return "released node after a horizon node"
        else:
            seen_horizon = True
    return None


class OrderBook:
    """The one holder of order state: current order, walk position, errors."""

    def __init__(self, stations):
        self.stations = frozenset(stations)
        self.order_id, self.update_id = "", 0
        self.nodes, self.edges = [], []
        self.next_i = 0                 # index of the next unreached node
        self.last_node_id, self.last_seq = "", 0
        self.errors = []

    # ----- what the rest of the vehicle asks -----

    def target(self):
        """The station to drive now: next unreached RELEASED node, or None."""
        if self.next_i < len(self.nodes) and self.nodes[self.next_i]["released"]:
            return self.nodes[self.next_i]["nodeId"]
        return None

    def active(self):
        return self.target() is not None

    def node_states(self):
        return [{"nodeId": n["nodeId"], "sequenceId": n["sequenceId"],
                 "released": n["released"]} for n in self.nodes[self.next_i:]]

    def edge_states(self):
        if self.next_i >= len(self.nodes):   # done or cancelled: none remain
            return []
        return [{"edgeId": e["edgeId"], "sequenceId": e["sequenceId"],
                 "released": e["released"]} for e in self.edges
                if e["sequenceId"] > self.last_seq]

    def new_base_request(self):
        """True when only horizon remains: the dispatcher should release."""
        return (self.next_i < len(self.nodes)
                and not self.nodes[self.next_i]["released"])

    # ----- events -----

    def receive(self, msg):
        """One inbound order. Returns 'accepted' | 'ignored' | 'rejected'."""
        reason = _shape_ok(msg, self.stations)
        if reason:
            self.errors = [_error(VALIDATION_ERROR, reason,
                                  str(msg.get("orderId", "")))]
            return "rejected"
        if msg["orderId"] == self.order_id:
            if msg["orderUpdateId"] == self.update_id:
                return "ignored"        # duplicate delivery, spec says drop
            if msg["orderUpdateId"] < self.update_id:
                self.errors = [_error(ORDER_UPDATE_ERROR,
                                      "orderUpdateId ran backwards",
                                      self.order_id)]
                return "rejected"
            return self._adopt_update(msg)
        if self.active():
            self.errors = [_error(VALIDATION_ERROR,
                                  "an order is active; cancel it first",
                                  msg["orderId"])]
            return "rejected"
        self._adopt(msg, start_at=0)
        return "accepted"

    def _adopt_update(self, msg):
        """Same orderId, higher updateId: the update must repeat the last
        reached (or first base) node as its stitch node, per spec; anything
        else is a different route wearing the same orderId, and drives
        nothing."""
        first = msg["nodes"][0]["nodeId"]
        stitch = self.last_node_id or (self.nodes[0]["nodeId"]
                                       if self.nodes else "")
        if first != stitch:
            self.errors = [_error(ORDER_UPDATE_ERROR,
                                  "update does not stitch at {}".format(
                                      stitch or "the start"),
                                  self.order_id)]
            return "rejected"
        # The repeated stitch node is already reached when it names
        # last_node_id; the walk starts after it.
        self._adopt(msg, start_at=1 if self.last_node_id else 0)
        return "accepted"

    def _adopt(self, msg, start_at):
        self.order_id = msg["orderId"]
        self.update_id = msg["orderUpdateId"]
        self.nodes = list(msg["nodes"])
        self.edges = list(msg["edges"])
        self.next_i = start_at
        self.errors = []

    def arrived(self, station_id):
        """The autopilot reached a station. Returns True when it was ours."""
        if station_id != self.target():
            return False
        node = self.nodes[self.next_i]
        self.last_node_id, self.last_seq = node["nodeId"], node["sequenceId"]
        self.next_i += 1
        return True

    def cancel(self):
        """cancelOrder: drop every pending node; identity stays reported."""
        self.next_i = len(self.nodes)
        self.errors = []
