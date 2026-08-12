"""status_contract.py - what every /plc/status consumer has to agree on.

The wire contract for the PLC status link lives here and nowhere else:
the topic name, the parser, the staleness rule, the fail-safe state and
the ROS-side timeout. plc_link.py publishes it; cmd_gate.py and
hmi_node.py read it.

WHY IT IS A MODULE, AND WHAT IT IS FOR LATER
  Every consumer of /plc/status makes the same three decisions - what a
  trustworthy packet is, when silence becomes a demand, and what to
  believe when neither is available - and a second implementation of any
  of them is a second opinion about whether the truck may move. Before
  this module the answers lived in plc_link.py, so two nodes imported a
  NODE to borrow a contract, and the timeout existed as two constants a
  test had to hold equal by hand. Later steps add consumers; they import
  this and inherit the answers rather than restating them.

WHY FAILSAFE IS A READ-ONLY VIEW AND NOT A dict
  It was a plain dict that hmi_node bound BY REFERENCE
  (`self.status = plc_link.FAILSAFE`), so one item assignment anywhere in
  the process would have rewritten the fail-safe state for every consumer
  at once - including plc_link's `dict(FAILSAFE)` copies, which would
  then have copied the corrupted value. A MappingProxyType leaves every
  existing read and every `dict(FAILSAFE)` copy working unchanged and
  turns that assignment into a loud TypeError instead of a silent enable.
  A frozen dataclass was rejected because `status` is sometimes a parsed
  packet (a real dict) and sometimes this, and the two have to index the
  same way. A failsafe() factory was rejected because it hands out copies
  that LOOK shared, which is the same trap facing the other way.

WHAT MUST NOT DRIFT
  STALE_S in plc_link.py is a DIFFERENT constant: that node's own UDP
  receive timeout, on a different clock with a different budget.
  STATUS_STALE_S below is the ROS-side timeout on /plc/status. They are
  not interchangeable and must not be merged. is_stale therefore takes
  its window as a REQUIRED argument: a default here would quietly be one
  of the two budgets for a caller that meant the other.
"""

import json
from types import MappingProxyType

# ----------------------------- CONFIG -----------------------------
# One of only two ROS topic names this project allows outside
# config.yaml (m5_ver2/CLAUDE.md), so it gets exactly one home.
STATUS_TOPIC = "/plc/status"

# THE OTHER SAFETY TOPIC NAMES, HERE FOR THE SAME REASON STATUS_TOPIC
# IS. m5_ver2/CLAUDE.md allows two literals outside config.yaml; by
# Step 3 there were six, three of them spelled out in two files each,
# and the gz drive-speed pair was worst - config.yaml OWNS those keys
# (topics.gz_drive_speed_read_a/b), the launch file read them from
# there, and encoder_link hard-coded them. One name, two sources, in
# one step: rename the config key and the bridge and the subscriber
# break differently, with a silently red encoder lamp as the symptom.
FIELDS_TOPIC = "/forklift/safety/fields"
ENCODERS_TOPIC = "/forklift/safety/encoders"
SCAN_TOPIC = "/forklift/gz/safety_scanner_{}/measurement"
#
# The drive-speed channels are DELIBERATELY ABSENT. config.yaml owns
# topics.gz_drive_speed_read_a/b, so encoder_link reads them from there
# and this file must not become a second source for a name that
# already has one. This is the one home for every topic name
# config.yaml has never heard of.

# STEP 5'S NAMES, HERE FOR THE SAME REASON. /hmi/cmd_vel moves in from
# cmd_gate.py and hmi_node.py so the mux does not become a third
# spelling. Every name below is one config.yaml has never heard of: the
# mux seam and the autonomy channels are this step's own inventions and
# have no other home.
#
# THE TWO GZ SOURCE NAMES ARE NOT HERE, AND THAT IS THE POINT. They were,
# briefly, on the reasoning that model.sdf's <odom_topic> and the nav
# lidar's <topic> are model.sdf's own and config.yaml had never heard of
# them. It HAS: topics.gz_odom and topics.gz_scan_nav
# (agv/forklift/config.yaml), spelled exactly as model.sdf spells them.
# Owner ruling 2026-08-12, applying m5_ver2/CLAUDE.md's house rule - every
# gz and ROS topic name config.yaml owns is READ from config.yaml. A
# second home would have been the drive-speed trap again: rename the key
# and the bridge and the subscriber break differently.
HMI_CMD_TOPIC = "/hmi/cmd_vel"
VEHICLE_CMD_TOPIC = "/vehicle/cmd_vel"   # cmd_mux -> cmd_gate, the one seam
AUTO_CMD_TOPIC = "/auto/cmd_vel"         # nav_node -> cmd_mux
AUTO_GOAL_TOPIC = "/auto/goal"           # HMI -> nav_node, station id or ""
AUTO_STATE_TOPIC = "/auto/state"         # nav_node -> HMI, JSON
MODE_TOPIC = "/hmi/mode"                 # HMI -> mux & nav, latched
MODE_TELEOP = "teleop"
MODE_AUTO = "auto"

# The ROS-side timeout on /plc/status: how long a consumer keeps
# believing the last thing the PLC said. ONE constant, because the
# screen and the vehicle must stop trusting a silent /plc/status at the
# same instant - whichever went first would be lying. Both consumers'
# derivations are kept: the same number has to satisfy both, and each
# rules out a different family of wrong values.
#
# THE GATE (cmd_gate.py, ZERO_HZ = 10). The gate's OWN timeout on
# /plc/status. Five missed publishes at plc_link's 20 Hz, so ordinary
# scheduling jitter cannot trip it, and deliberately NOT a multiple of
# 1/ZERO_HZ: 2.5 ticks, clear of the tick boundary that cost Task 3 two
# rounds on STALE_S.
#
# THE DISPLAY (hmi_node.py, PUBLISH_HZ = 20). IT IS AN EXACT MULTIPLE OF
# THE TICK IT IS COMPARED ON, AND THAT IS ACCEPTED. display_state is
# reached only from the 1/PUBLISH_HZ timer, so the elapsed values tested
# walk in 50 ms steps and 0.25 s is 5 of them: depending on where the
# last packet fell inside a tick, the lamp turns red anywhere in 0.25 to
# 0.30 s, which is the band measured (0.301 s). The ambiguity is one tick
# of DISPLAY trip time and nothing else - the vehicle is cmd_gate's, and
# it times out on this same constant - so holding the two equal is worth
# more than shaving a tick off a lamp.
STATUS_STALE_S = 0.25

# V_Limit (%MW100) is the PLC standard program's speed permission in
# mm/s: 1500 with the warning field clear, 300 with it occupied
# (m5_ver2/CLAUDE.md section 3.2). These two are the only values the
# F-program computes, so anything else on the wire is a fault.
#
# AN UNREADABLE V_Limit BECOMES THE CREEP CEILING, not the full one.
# Same rule as an unreadable monitoring case selecting the largest
# field: not knowing means assuming the most demanding permission,
# and here the most demanding is the slowest.
V_LIMIT_FULL_MM_S = 1500
V_LIMIT_CREEP_MM_S = 300
V_LIMIT_MAX_PLAUSIBLE_MM_S = 3000
# ------------------------------------------------------------------

#: The keys of the wire format step5.py sends. `issubset` and not
#: equality: a later sender adding a field must still pass this parser.
#: `case` joined in Step 2 - field_eval picks its (PF, WF) pair from it,
#: and Step 1 left CASE_B0/CASE_B1 deliberately unconsumed.
_REQUIRED_KEYS = {"estop_healthy", "motor", "case", "v_limit", "ts"}

#: What the vehicle is told when the link is stale or has never spoken.
#: Read-only on purpose - see the module docstring. Copy it with
#: dict(FAILSAFE) before handing it anywhere that mutates.
#: case 3 is the LARGEST field: not knowing which case applies means
#: assuming the most demanding one (microscan3.py:16). v_limit is the
#: creep ceiling for the same reason - the slowest known permission.
FAILSAFE = MappingProxyType(
    {"estop_healthy": False, "motor": False, "case": 3,
     "v_limit": V_LIMIT_CREEP_MM_S, "ts": 0.0})


def parse_status(data):
    """Decode one datagram, or None if it is not a packet we trust.

    A packet missing a key is rejected rather than defaulted: defaulting
    `motor` would be inventing an enable. The booleans must also BE
    booleans - `not motor` on a truthy non-bool (1, or "off") would
    publish demand False and release the contactor on an invalid packet.
    """
    try:
        msg = json.loads(data.decode())
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict) or not _REQUIRED_KEYS.issubset(msg):
        return None
    for key in ("motor", "estop_healthy"):
        if not isinstance(msg[key], bool):
            return None
    # isinstance(True, int) is True in Python, so bool must be excluded or
    # a JSON `true` would pass as a monitoring case.
    if not isinstance(msg["case"], int) or isinstance(msg["case"], bool):
        return None
    v = msg["v_limit"]
    if not isinstance(v, int) or isinstance(v, bool):
        return None
    return msg


def speed_limit_mm_s(v_limit):
    """The permission to obey, in mm/s.

    Anything outside the plausible range becomes the creep ceiling. A
    negative or absurd V_Limit is a fault in the reading, and a fault
    must not widen a permission - so it narrows it to the slowest
    value the F-program ever computes.
    """
    if not isinstance(v_limit, int) or isinstance(v_limit, bool):
        return V_LIMIT_CREEP_MM_S
    if v_limit <= 0 or v_limit > V_LIMIT_MAX_PLAUSIBLE_MM_S:
        return V_LIMIT_CREEP_MM_S
    return v_limit


def is_stale(last_rx_s, now_s, stale_s):
    """True when nothing has arrived within the window, or ever.

    `stale_s` is required: this rule is shared but the budgets are not.
    """
    if last_rx_s is None:
        return True
    return (now_s - last_rx_s) >= stale_s
