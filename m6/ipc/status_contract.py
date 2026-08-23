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
# nodes read their vehicle id from env VEHICLE, stamped by m6.sh on
# every spawn; the Windows writer sets the same variable from
# --vehicle before importing this module. The 5100/5101 family is left
# to step5 on purpose: an accidentally concurrent step5 stack collides
# with nothing here and is caught by its own port guard.
VEHICLES = {
    "f1": {"plc_port": 5110, "sensor_port": 5111,
           "spawn": {"x": "-17.00", "y": "10.00", "z": "0.05",
                     "yaw": "3.14159"}},
    "f2": {"plc_port": 5120, "sensor_port": 5121,
           "spawn": {"x": "-10.00", "y": "10.00", "z": "0.05",
                     "yaw": "3.14159"}},
    "f3": {"plc_port": 5130, "sensor_port": 5131,
           "spawn": {"x": "10.00", "y": "10.00", "z": "0.05",
                     "yaw": "3.14159"}},
    "f4": {"plc_port": 5140, "sensor_port": 5141,
           "spawn": {"x": "17.00", "y": "10.00", "z": "0.05",
                     "yaw": "3.14159"}},
}
# THE FOUR POSES ARE NOT A DIVISION OF THE FLOOR, AND THAT IS THE POINT.
# Until M6.6 they were: each truck stood nearest to the stations on its
# own quarter, no truck had to cross the hall, and the recording showed
# exactly that. The four now stand in a row on the NORTH RING LEG, which
# carries no station at all - so the first assignment sends every one of
# them somewhere, and after two transports the fleet is scattered by its
# own work rather than by this table (a truck finishes a transport at
# its DROPOFF station, not at a home pose).
#
# SPACING IS 7.00 m AT THE CLOSEST AND BOTH CONSTRAINTS ARE DERIVED.
#   A neighbour's body edge sits 7.00 - 0.46 - 0.52 = 6.02 m from a
#   scanner, outside the 2.70 m re-clear threshold, so four parked
#   trucks do not sit in each other's warning fields and none of them
#   starts under a reduced V_Limit.
#   Each pose IS A GRAPH NODE (route.LEG_X carries -17, -10, +10, +17,
#   which are the only x-positions on the north leg that are not a bay
#   spur foot - every station is entered off the ring since rev B).
#   nearest_node and floor._standing_from both snap a pose to the
#   nearest node, and four trucks whose nearest node is the same node
#   are four trucks the traffic ledger will hand one piece of floor to.
#
# yaw 3.14159 points the forks at world +x: model yaw 0 puts them at
# -x, so pi is the row facing east down the north leg.
#
# test_fleet_spawn_fairness.py holds all three of those, and it holds
# them as RULES: if a pose has to move, move it and let the assertions
# say whether the new one is honest.
#
# EVERY YAW IN THIS TABLE POINTS THE TRUCK AT THE FLOOR IT WILL BE SENT
# TO, and that is a rule, not an accident. Model yaw 0 points the FORKS
# at world -x, and the TRAVEL heading is the model heading flipped
# (follower.travel_yaw), so a truck at yaw 0 drives WEST when it is
# given work and one at yaw pi drives EAST. Where its first leg goes the
# other way the follower does not swing round - it REVERSES, straight,
# at REVERSE_MPS - and it stays in reverse until the next target is
# within REVERSE_EXIT_RAD of its travel heading. On a short spur that
# never happens: measured 2026-08-22, f4 at yaw pi was sent to S4, which
# is 4.50 m away and WEST, reversed straight down the dock aisle, passed
# the spur junction it should have turned at by 0.18 m, and stopped for
# good with nav's obstacle guard 1.477 m off PARKED f2 (GUARD_HOLD_M is
# 1.5). The truck could not reach its nearest station. So: f1 at yaw 0
# faces west, towards S3/S10/S2, its three nearest; f2 at yaw pi faces
# east, towards S4; f3 at yaw 0 faces west, towards the S6/S8 junction
# 5.00 m away; and f4 at yaw pi faces east, towards the S5/S7/S9
# junction, also 5.00 m away. No test can check this one - it is about
# where the WORK is, not about where the walls are - so it is written
# here instead.
#
# AND A PARKED TRUCK MUST HAVE ROOM TO TURN INTO THE STATIONS IT IS
# NEAREST TO, which is the third thing the route-usage table cannot see.
# (8.0, -5.5) is the quietest clear node on this floor - 6 of the 90
# routes - and it is 2.00 m from the S4 spur junction, so it wins every
# S4 transport and has two metres to set up a turn into a 2.5 m spur.
# Measured 2026-08-22 at both yaws: at yaw pi it reversed past the
# junction into f2's guard band; at yaw 0 it drove up at 0.70 m/s,
# decelerated into the corner and STALLED there - steer joint at
# -0.926 rad against the -2.5 rad/s traction command, drive wheel
# velocity 8e-5 rad/s, nav still EN-ROUTE with the guard clear at
# 2.975 m, for seven minutes. The same spur is reached routinely from
# the WEST, where the approach has 3.00 m of run-up (f2 did it in the
# M6.5 gate session, 19:14). So the parking node moved to the main aisle
# and S4 went back to f2, whose approach is the proven one. The lesson
# is the general one and it is why this paragraph is long: LEAST-USED
# FLOOR IS NOT THE ONLY RULE. A pose that no truck drives through is
# worth nothing if the truck standing on it cannot get out of it and
# into the stations the fleet will pick it for.
#
# WHERE A PARKED TRUCK MAY STAND IS A FLEET DECISION, NOT A SCENIC ONE,
# AND M6.5 GOT IT WRONG TWICE - once on the graph and once on the floor.
#
# THE FIRST WRONG ANSWER WAS THE GRAPH'S. f3 and f4 first went in at
# (-8.0, 5.65) and (8.0, 5.65) because those are open main-aisle floor.
# They are also the two SPUR JUNCTIONS floor.py names: (-8.0, 5.65) is the
# only way into both S6 and S8, and (8.0, 5.65) into S5, S7 and S9. What
# that costs is not theoretical, because an idle truck HOLDS the node
# under it (floor.py _hold_standing) and IDLE_HOLD_S hands it back after
# 30 s with the truck still standing there (_idle_floor, which says so in
# its own warning) - so those two poses put a parked truck first across
# the fleet's busiest junction and then invisible on it, leaving the
# scanners as the stop. Measured over the real planner, every one of the
# 90 station-to-station routes:
#
#     node            of 90 routes   nearest station   clear floor
#     (8.0, 5.65)          46           0.85 m  S7      3.25 m   <- was f4
#     (0.0, 5.65)          44           8.05 m  S6      4.35 m
#     (-3.0, -5.5)         42           0.00 m  S1      4.50 m   <- f1, = S1
#     (-8.0, 5.65)         34           0.85 m  S6      3.25 m   <- was f3
#     (3.0, 5.65)          36           5.07 m  S7      3.25 m   <- f4
#     (-3.0, 5.65)         20           5.07 m  S6      3.25 m   <- f3
#     (3.0, -5.5)          12           3.91 m  S4      4.50 m   <- f2
#     (-12.5, 5.65)        12           4.58 m  S6      2.50 m   <- was f3
#     (8.0, -5.5)           6           3.20 m  S4      4.45 m   <- see below
#     (12.0, -5.5)          6           6.50 m  S4      3.00 m   <- was f4
#     (12.0, 5.65)          6           0.40 m  S5      2.00 m
#
# NO NODE IN THIS GRAPH IS ROUTE-FREE - all 26 are on at least one of the
# 90 - so the choice is the least-used floor, not clean floor.
# (12.0, 5.65), the main aisle's east end, is rejected on the same table:
# 6 routes, but 0.40 m from S5's own station point, so a truck parked
# there stands ON the conveyor station while the ledger calls it a
# different node.
#
# THE SECOND WRONG ANSWER WAS THE FLOOR'S, AND IT COST THE FIRST
# ACCEPTANCE RUN. The two quietest nodes in the table are the END-AISLE
# ones, and the end aisles are 5.00 m wide. A fork-corner scanner sits at
# model (-0.68, +-0.46), so a truck parked 2.50 m off the west wall stands
# with that scanner 1.82 m from it - INSIDE its own 2.5 m warning field,
# which is V_Limit 300 from the F-program before the truck has moved a
# millimetre. Worse, its first turn swings the same scanner another half
# metre out: on 2026-08-22 f3 turned south out of (-12.5, 5.65), reached
# 0.971 m from that wall eight seconds into the acceptance run, latched
# PROTECTIVE and never moved again (PROOF, M6.5 Gate 4). f4's old pose at
# (12.0, -5.5) is the same fault at 2.32 m: it crawled from its first
# cycle. Neither the route-usage table nor the raw-closest-return check
# Task 4 used could see any of it, because the raw closest return is the
# truck's OWN forks on every truck.
#
# So the third rule is CLEAR FLOOR, and it is measured off the world SDF's
# own collision boxes at the safety scan plane, not off a list:
#
#     at rest   every scanner, at the pose's own yaw, further than
#               WF + hysteresis (2.70 m) from any solid - including the
#               other three parked trucks, whose contour is the vehicle
#               SDF's at that plane
#     leaving   the pose itself further than PF + hysteresis + the scanner
#               ring (0.821 m) + the pursuit's turning circle
#               (LOOKAHEAD_M / 2 = 0.60 m) from any solid: 2.62 m
#
#     truck  at-rest worst scanner            leaving
#     f1     4.04 m  left, south wall         4.50 m   (+1.88)
#     f2     3.99 m  right, the dock door post 4.50 m  (+1.88)
#     f3     2.84 m  right fork corner, rack A west run's end frame
#                                             3.25 m   (+0.63)
#     f4     2.84 m  right fork corner, rack B east run's end frame
#                                             3.25 m   (+0.63)
#
# Read back off the running world 2026-08-22, all four at rest,
# /fN/safety/fields: every device wf true and V_Limit 1500 on all four,
# which is what the old table could not say. The two main-aisle trucks
# measured 3.34 / 2.84 / 2.84 (back/left/right) against 2.84 computed -
# the arithmetic above and the scanners agree to the centimetre.
#
# tests/test_vehicles_table.py pins all three rules - no spur junction, no
# pose almost-but-not-quite on a station, and no truck parked inside a
# field it cannot clear or turn out of.
#
# WHAT f4'S POSE COSTS, NAMED. (8.0, -5.5)'s nearest graph neighbour is
# (6.0, -5.5), the S4 spur junction, 2.00 m west - the closest neighbour
# any parked truck has, against 3.00 m for the other three. Two truck
# centres 2.00 m apart are inside each other's protective fields, so a
# truck standing at that junction stops parked f4 until it leaves. It is
# a property of the dock aisle's node spacing (its tightest pair is the
# 1.40 m between (-7.4, -5.5) and (-6.0, -5.5)) and not of this pose, the
# window is the seconds between spawn and f4's first task, and the
# alternative is an end-aisle pose that cannot leave at all.
#
# EVERY POSE HERE HAS BEEN SPAWNED AND LOOKED AT, AND THE CHECK NOW READS
# field_eval AND NOT ONLY THE RAW RANGES. M6.1 validated f1's and f2's;
# M6.5's Gate 1 spike did the same for the first f3/f4 pair, and the pair
# above was measured the same way when they moved - resting pose read back
# off the running world, every safety lidar's closest return compared
# against f1's and f2's, AND /fN/safety/fields read at rest, where all
# three devices must show wf true, and again through the truck's first
# turn, where all three must stay pf true. A pose that rests tilted,
# sinks, reads unlike the others or cannot turn out of itself moves HERE,
# in this table, and nowhere else - the launch file, m6.sh's `home`, the
# spike and the fleet all read it.
#
# THE PORT FAMILIES CLIMB IN TENS AND THE SENSOR PORT IS ALWAYS +1, and
# they are still written out rather than computed: what a reader needs
# from this table is the number, not the rule that made it, and a fifth
# vehicle that has to sit outside the pattern would break a formula and
# not a list. The 5100/5101 family stays step5's (see above).

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
        "auto_route_topic": "/{}/auto/route".format(vid),
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
#   AUTO_ROUTE_TOPIC   agent -> nav_node, a finished route (M6.2)
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
    AUTO_ROUTE_TOPIC = _C["auto_route_topic"]
    AUTO_STATE_TOPIC = _C["auto_state_topic"]
    MODE_TOPIC = _C["mode_topic"]
else:
    # The launch file imports this module with no VEHICLE - it reads
    # only VEHICLES and contract(vid), which exist above. Anything
    # else reaching for a per-vehicle constant without the env gets
    # the refusal by name, not an ImportError shrug.
    #
    # DUNDERS ARE NOT PER-VEHICLE CONSTANTS. `from status_contract
    # import VEHICLES` makes the import machinery probe
    # hasattr(module, "__path__") to decide whether VEHICLES could be a
    # submodule; hasattr catches AttributeError and nothing else, so
    # answering that probe with SystemExit killed every env-free
    # from-import - including the launch file's and
    # tools/instantiate_vehicle.py's - before it could read the table
    # that is right there. Dunder lookups therefore get the ordinary
    # AttributeError the machinery expects; a real name still gets the
    # loud refusal.
    def __getattr__(name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        raise SystemExit(
            "status_contract: env VEHICLE is not set, so the "
            "per-vehicle constant {!r} does not exist. m6.sh stamps "
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

#: The keys of the wire format m6.py sends. `issubset` and not
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
