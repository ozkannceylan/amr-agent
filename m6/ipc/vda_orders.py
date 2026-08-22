"""vda_orders.py - VDA 5050 order rules, pure. No ROS, no MQTT.

The M1 subset's section 4 as executable checks. Validation names what
is wrong instead of repairing it; acceptance is a three-way verdict so
a duplicate delivery is silence, not an error; progress is monotone and
skip-tolerant, because the pursuit cuts corners and the polyline's
ARRIVED (nav-side) is what finally closes an order, not this counter.

Numbers are checked, not merely present: an order that lies about a
coordinate is rejected at the door, because the alternative is a crash
in the callback that drives - or worse, a drive that crashes mid-motion.

M6.4 STITCHES (VDA 5050 s.6.6): an update to the order the vehicle is
already driving is a fourth verdict, 'extend', not a new order. It is
allowed exactly when nothing the truck has already been told to drive
changes - same orderId, orderUpdateId one higher, and every released
node still there, at its index, at its coordinates, still released.
Everything past that may grow: a horizon node may be released and new
released nodes may be appended. Node actions stay rejected (M6.5).
"""
import math

DEFAULT_DEV_M = 0.8   # intermediate waypoint pass radius; the pursuit
                      # cuts corners, and ARRIVED closes what this misses


def _real(v):
    """True for a real, finite number. Booleans are not numbers here -
    the same strictness orderUpdateId already gets. A 400-digit integer
    is legal JSON and an int Python holds happily, but no float can:
    isfinite() raises on it, so the answer is asked for, not assumed."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:        # int too large to convert to float
        return False


def validate_order(msg):
    """'' when valid, else the reason - which names the missing thing."""
    if not isinstance(msg, dict):
        return "not an object"
    for key in ("orderId", "orderUpdateId", "nodes", "edges"):
        if key not in msg:
            return "missing {}".format(key)
    if not isinstance(msg["orderId"], str) or not msg["orderId"]:
        return "orderId must be a non-empty string"
    upd = msg["orderUpdateId"]
    if not isinstance(upd, int) or isinstance(upd, bool) or upd < 0:
        return "orderUpdateId must be an integer >= 0"
    nodes, edges = msg["nodes"], msg["edges"]
    if not isinstance(nodes, list) or not nodes:
        return "nodes must be a non-empty array"
    if not isinstance(edges, list) or len(edges) != len(nodes) - 1:
        return "edges must join the nodes (len(nodes)-1 of them)"
    for i, n in enumerate(nodes):
        for key in ("nodeId", "sequenceId", "released", "actions"):
            if key not in n:
                return "node {} missing {}".format(i, key)
        if n["sequenceId"] != 2 * i:
            return "node {} sequenceId must be {} (interleaved rule)".format(
                i, 2 * i)
        pos = n.get("nodePosition")
        if not isinstance(pos, dict) or not {"x", "y", "mapId"} <= set(pos):
            return "node {} missing nodePosition (mandatory for us)".format(i)
        for axis in ("x", "y"):
            if not _real(pos[axis]):
                return ("node {} nodePosition {} must be a finite number, "
                        "not {!r}".format(i, axis, pos[axis]))
        dev = pos.get("allowedDeviationXY")
        if dev is not None and not _real(dev):
            return ("node {} allowedDeviationXY must be a finite number, "
                    "not {!r}".format(i, dev))
        if n["actions"]:
            return "node {} actions unsupported until M6.3".format(i)
    for i, e in enumerate(edges):
        for key in ("edgeId", "sequenceId", "released",
                    "startNodeId", "endNodeId", "actions"):
            if key not in e:
                return "edge {} missing {}".format(i, key)
        if e["sequenceId"] != 2 * i + 1:
            return "edge {} sequenceId must be {} (interleaved rule)".format(
                i, 2 * i + 1)
        if (e["startNodeId"] != nodes[i]["nodeId"]
                or e["endNodeId"] != nodes[i + 1]["nodeId"]):
            return "edge {} does not join its neighbour nodes".format(i)
    if not nodes[0]["released"]:
        return "no released base - the first node is horizon"
    seen_horizon = False
    for n in nodes:
        if seen_horizon and n["released"]:
            return "released node after a horizon node"
        seen_horizon = seen_horizon or not n["released"]
    for e, end in zip(edges, nodes[1:]):
        if bool(e["released"]) != bool(end["released"]):
            return "edge released must match its end node"
    return ""


BASE_CHANGED = "an update may not change the part already driven"


def _base_kept(current, msg):
    """'' when msg preserves every released node of the current order.

    The already-driven part is not a suggestion: a released node must
    still be there, at the same index, with the same id and sequenceId,
    at the same x/y, and still released. Where the current order goes
    horizon the update may do as it likes - that is the whole point of
    a horizon - so the walk stops at the first unreleased node.
    """
    new = msg["nodes"]
    for i, old in enumerate(current.get("nodes", [])):
        if not old.get("released"):
            return ""
        if i >= len(new):
            return BASE_CHANGED          # a released node simply vanished
        n, pos = new[i], new[i]["nodePosition"]
        was = old.get("nodePosition") or {}
        if (not n["released"]
                or n["nodeId"] != old.get("nodeId")
                or n["sequenceId"] != old.get("sequenceId")
                or pos["x"] != was.get("x") or pos["y"] != was.get("y")):
            return BASE_CHANGED
    return ""


def accept_order(msg, current_order, executing, operating_mode):
    """('accept'|'extend'|'ignore'|'reject', reason).

    `current_order` is the order the vehicle holds (the whole message,
    because an extension is judged against its nodes) or None.
    """
    reason = validate_order(msg)
    if reason:
        return ("reject", reason)
    cur_id = current_order["orderId"] if current_order else ""
    cur_upd = current_order["orderUpdateId"] if current_order else 0
    if msg["orderId"] == cur_id and msg["orderUpdateId"] == cur_upd:
        return ("ignore", "duplicate delivery")
    # THE MODE ANSWERS FIRST, stitch or not: an update that reaches a
    # truck someone has just taken to teleop is still an order this
    # vehicle cannot drive.
    if operating_mode != "AUTOMATIC":
        return ("reject", "vehicle not in AUTOMATIC")
    if current_order and msg["orderId"] == cur_id:
        if msg["orderUpdateId"] != cur_upd + 1:
            return ("reject",
                    "orderUpdateId must be {} - exactly one more than the "
                    "executing order".format(cur_upd + 1))
        if not executing:
            return ("reject",
                    "no order is executing - nothing to extend")
        reason = _base_kept(current_order, msg)
        return ("reject", reason) if reason else ("extend", "")
    if msg["orderUpdateId"] != 0:
        return ("reject",
                "an update to an order this vehicle is not driving - "
                "send a new order with orderUpdateId 0")
    if executing:
        return ("reject", "an order is executing - cancelOrder first")
    return ("accept", "")


def released_route(msg):
    """(points, arrive_m, released_nodes, horizon_nodes).

    Call it on a validated order only: it reads nodePosition and the last
    released node without re-checking either. Callers hand nav
    [current pose] + these points, so a single released node is still a
    drivable two-point polyline because of that prepend.
    """
    released = [n for n in msg["nodes"] if n["released"]]
    horizon = [n for n in msg["nodes"] if not n["released"]]
    points = [(float(n["nodePosition"]["x"]), float(n["nodePosition"]["y"]))
              for n in released]
    last = released[-1]["nodePosition"]
    # Only a positive radius is a radius: nav_core.on_route refuses
    # anything <= 0, so a zero or negative deviation takes the default
    # rather than costing the order its route.
    raw = last.get("allowedDeviationXY")
    arrive_m = float(raw) if isinstance(raw, (int, float)) \
        and not isinstance(raw, bool) and raw > 0 else 0.25
    return points, arrive_m, released, horizon


class Progress:
    """Which released nodes the truck has passed. Monotone, skips."""

    def __init__(self, released_nodes):
        self.nodes = released_nodes
        self.reached = 0

    def update(self, xy):
        """Mark the furthest node whose deviation circle contains xy,
        and everything before it. True when the count advanced."""
        before = self.reached
        for j in range(len(self.nodes) - 1, self.reached - 1, -1):
            pos = self.nodes[j]["nodePosition"]
            dev = float(pos.get("allowedDeviationXY", DEFAULT_DEV_M))
            if math.hypot(xy[0] - pos["x"], xy[1] - pos["y"]) <= dev:
                self.reached = j + 1
                break
        return self.reached != before

    def complete(self):
        self.reached = len(self.nodes)

    def last_node(self):
        if self.reached == 0:
            return ("", 0)
        node = self.nodes[self.reached - 1]
        return (node["nodeId"], node["sequenceId"])
