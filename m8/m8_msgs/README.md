# m8_msgs

ROS 2 message contract for M8. Not built in Phase A0 — H0 is pure
Python (`m8_core`) and does not require colcon or rclpy.

| File | Role |
|---|---|
| `Proposal.msg` | the one proposal type (ARCHITECTURE.md §4) |
| `Verdict.msg` | gate accept/refuse + reason |
| `SlotState.msg` | one row of a `SLOT_STATE` table |

Python dataclasses in `m8_core/contract.py` and `m8_core/gate.py` are
the executable form of these files. A later phase that adds an
`m8_nodes` publisher must keep the two in lockstep.
