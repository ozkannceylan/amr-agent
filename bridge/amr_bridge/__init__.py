"""amr-agent bridge — Gazebo cell <-> S7-1500 OPC UA server.

One OS process that is an OPC UA *client* (invariant 4) and a ROS 2 node, and
nothing else. It carries each signal of docs/interfaces/opcua-nodes.md §9.9
from one side to the other unchanged, and writes its own heartbeat.

THE NO-LOGIC RULE (docs/interfaces/bridge-design.md §1.1) is the binding
statement for every module in this package:

    The bridge applies no process decision to any signal. It moves values. The
    only numeric operation permitted anywhere in the bridge is unit-preserving
    type conversion (ROS float64 -> S7 Real, i.e. IEEE-754 double -> single
    narrowing). No scaling, no offset, no clamping, no rounding, no unit
    change.

There is therefore no threshold, no interlock, no sequencer, no latch, no
meaning-changing debounce and no timer that gates a signal anywhere in this
package. Every such decision belongs to the PLC.
"""

__all__ = [
    "config",
    "slots",
    "instrumentation",
    "ros_side",
    "opcua_side",
]
