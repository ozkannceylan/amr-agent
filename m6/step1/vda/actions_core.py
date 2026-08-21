"""actions_core.py - instantActions in, effects out. No ROS in the room.

Eight standard actions (subset section 6), no custom names. Every received
action gets an actionState entry keyed by actionId - FINISHED or FAILED -
and the supported ones return an EFFECT for the shell's glue to execute:

    ("pause", True/False)      startPause / stopPause
    ("cancel", None)           cancelOrder
    ("charging", True/False)   startCharging / stopCharging (modeled battery)
    ("state", None)            stateRequest - publish state now
    ("factsheet", None)        factsheetRequest - publish factsheet now

THE ACTIONS ARE PROCESS COMMANDS. cancelOrder and startPause stop the truck
through the same /auto/goal seam a human uses; none of them is a stop
function in the safety sense (invariant 1), and none of them can touch the
Motor bit, the fields or the latch.

initPosition is accepted and does nothing, and SAYS SO: this vehicle's pose
is ground truth from the simulator (owner ruling at step 5 - the nav lidar
guards, it does not localise), so there is nothing to initialise. FINISHED
with a resultDescription naming the no-op, because a FAILED would tell the
dispatcher the vehicle is lost, which is the opposite of the truth.
"""

FINISHED, FAILED = "FINISHED", "FAILED"

_EFFECTS = {"startPause": ("pause", True),
            "stopPause": ("pause", False),
            "cancelOrder": ("cancel", None),
            "startCharging": ("charging", True),
            "stopCharging": ("charging", False),
            "stateRequest": ("state", None),
            "factsheetRequest": ("factsheet", None),
            "initPosition": None}

SUPPORTED = tuple(_EFFECTS)


class ActionBook:
    """actionStates for the state topic: one entry per received action."""

    def __init__(self):
        self._states = {}
        self._seen = []                 # actionIds in arrival order

    def receive(self, msg):
        """One inbound instantActions message. Returns the effect list."""
        effects = []
        actions = msg.get("actions")
        if not isinstance(actions, list):
            return effects
        for act in actions:
            if not isinstance(act, dict):
                continue
            aid, atype = act.get("actionId"), act.get("actionType")
            if not isinstance(aid, str) or not aid \
                    or not isinstance(atype, str):
                continue                # unaddressable: no state to key
            if aid in self._states:
                continue                # duplicate delivery, first one stands
            if atype not in _EFFECTS:
                self._set(aid, atype, FAILED,
                          "unsupported action (factsheet lists the eight)")
                continue
            if atype == "initPosition":
                self._set(aid, atype, FINISHED,
                          "no-op: pose is simulator ground truth")
                continue
            self._set(aid, atype, FINISHED, "")
            effects.append(_EFFECTS[atype])
        return effects

    def _set(self, aid, atype, status, result):
        entry = {"actionId": aid, "actionType": atype,
                 "actionStatus": status}
        if result:
            entry["resultDescription"] = result
        self._states[aid] = entry
        self._seen.append(aid)

    def action_states(self):
        return [dict(self._states[aid]) for aid in self._seen]
