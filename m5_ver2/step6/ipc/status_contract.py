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
import os
from types import MappingProxyType

# ----------------------------- CONFIG -----------------------------
# ----------------------------- VEHICLES ----------------------------
# The one table every per-vehicle difference lives in (M6.1 spec). WSL
# nodes read their vehicle id from env VEHICLE, stamped by step6.sh on
# every spawn; the Windows writer sets the same variable from
# --vehicle before importing this module. The 5100/5101 family is left
# to step5 on purpose: an accidentally concurrent step5 stack collides
# with nothing here and is caught by its own port guard.
VEHICLES = {
    "f1": {"plc_port": 5110, "sensor_port": 5111,
           "spawn": {"x": "-3.00", "y": "-5.50", "z": "0.05", "yaw": "0.0"}},
    "f2": {"plc_port": 5120, "sensor_port": 5121,
           "spawn": {"x": "3.00", "y": "-5.50", "z": "0.05",
                     "yaw": "3.14159"}},
}
# f1 keeps step5's proven spawn. f2 faces it from the other end of the
# 6.50 m main aisle. Task 4 (the RTF spike) validates both live; if a
# scanner reads PROTECTIVE at spawn the pose moves THERE, in this table.

_HERE = os.path.dirname(os.path.abspath(__file__))


def vehicle_id():
    """Env VEHICLE, refused loudly when absent or unknown."""
    vid = os.environ.get("VEHICLE", "")
    if vid not in VEHICLES:
        raise SystemExit(
            "status_contract: env VEHICLE must be one of {}, got {!r}"
            .format(sorted(VEHICLES), vid))
    return vid


def contract(vid):
    """Every per-vehicle name and number, as pure data.

    The launch file serves BOTH vehicles from one process, so it calls
    this per vid instead of reading the env-bound module constants.
    """
    if vid not in VEHICLES:
        raise SystemExit(
            "status_contract: unknown vehicle {!r}, valid: {}"
            .format(vid, sorted(VEHICLES)))
    v = VEHICLES[vid]
    return {
        "status_topic": "/{}/plc/status".format(vid),
        "fields_topic": "/{}/safety/fields".format(vid),
        "encoders_topic": "/{}/safety/encoders".format(vid),
        "scan_topic": "/" + vid + "/gz/safety_scanner_{}/measurement",
        "hmi_cmd_topic": "/{}/hmi/cmd_vel".format(vid),
        "vehicle_cmd_topic": "/{}/vehicle/cmd_vel".format(vid),
        "auto_cmd_topic": "/{}/auto/cmd_vel".format(vid),
        "auto_goal_topic": "/{}/auto/goal".format(vid),
        "auto_state_topic": "/{}/auto/state".format(vid),
        "mode_topic": "/{}/hmi/mode".format(vid),
        "plc_port": v["plc_port"],
        "sensor_port": v["sensor_port"],
        "config_path": os.path.normpath(os.path.join(
            _HERE, "..", "vehicles", vid, "config.yaml")),
        "spawn": v["spawn"],
    }


# ------------------- THE ENV VEHICLE'S OWN NAMES -------------------
# Every reason each name below lives in this file is unchanged by M6.1
# - only the VALUES became vehicle-scoped, and they are now read from
# contract() rather than spelled out, so the namespacing cannot drift
# from the table above.
#
# STATUS_TOPIC is one of only two ROS topic names this project allows
# outside config.yaml (m5_ver2/CLAUDE.md), so it gets exactly one home.
#
# THE OTHER SAFETY TOPIC NAMES, HERE FOR THE SAME REASON STATUS_TOPIC
# IS. m5_ver2/CLAUDE.md allows two literals outside config.yaml; by
# Step 3 there were six, three of them spelled out in two files each,
# and the gz drive-speed pair was worst - config.yaml OWNS those keys
# (topics.gz_drive_speed_read_a/b), the launch file read them from
# there, and encoder_link hard-coded them. One name, two sources, in
# one step: rename the config key and the bridge and the subscriber
# break differently, with a silently red encoder lamp as the symptom.
#
# The drive-speed channels are DELIBERATELY ABSENT. config.yaml owns
# topics.gz_drive_speed_read_a/b, so encoder_link reads them from there
# and this file must not become a second source for a name that
# already has one. This is the one home for every topic name
# config.yaml has never heard of.
#
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
#
# WHAT EACH NAME ROUTES, kept from the literals it replaces:
#   VEHICLE_CMD_TOPIC  cmd_mux -> cmd_gate, the one seam
#   AUTO_CMD_TOPIC     nav_node -> cmd_mux
#   AUTO_GOAL_TOPIC    HMI -> nav_node, station id or ""
#   AUTO_STATE_TOPIC   nav_node -> HMI, JSON
#   MODE_TOPIC         HMI -> mux & nav, latched
#
# WHY THE BINDING IS GUARDED. The LAUNCH FILE imports this module
# env-free - it serves both vehicles through contract(vid) and must not
# die at import. A NODE missing the env must still get a loud, naming
# refusal, which the PEP 562 module __getattr__ in the else branch
# provides.
if os.environ.get("VEHICLE"):
    VID = vehicle_id()
    _C = contract(VID)
    PLC_PORT = _C["plc_port"]
    SENSOR_PORT = _C["sensor_port"]
    CONFIG_PATH = _C["config_path"]
    STATUS_TOPIC = _C["status_topic"]
    FIELDS_TOPIC = _C["fields_topic"]
    ENCODERS_TOPIC = _C["encoders_topic"]
    SCAN_TOPIC = _C["scan_topic"]
    HMI_CMD_TOPIC = _C["hmi_cmd_topic"]
    VEHICLE_CMD_TOPIC = _C["vehicle_cmd_topic"]
    AUTO_CMD_TOPIC = _C["auto_cmd_topic"]
    AUTO_GOAL_TOPIC = _C["auto_goal_topic"]
    AUTO_STATE_TOPIC = _C["auto_state_topic"]
    MODE_TOPIC = _C["mode_topic"]
else:
    # The launch file imports this module with no VEHICLE - it reads
    # only VEHICLES and contract(vid), which exist above. Anything
    # else reaching for a per-vehicle constant without the env gets
    # the refusal by name, not an ImportError shrug.
    def __getattr__(name):
        raise SystemExit(
            "status_contract: env VEHICLE is not set, so the "
            "per-vehicle constant {!r} does not exist. step6.sh stamps "
            "VEHICLE on every node; the writer's --vehicle sets it; "
            "env-free callers use contract(vid).".format(name))


# The mode words are the same in every cab, so they stay unguarded.
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

#: The keys of the wire format step6.py sends. `issubset` and not
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
