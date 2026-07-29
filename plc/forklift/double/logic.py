#!/usr/bin/env python3
"""FB_ForkliftTeleop, transliterated statement-for-statement from
plc/forklift/SPEC.md section 7.

THIS IS A REHEARSAL STAND-IN. The TIA Portal build is the plant. Where this file
and SPEC.md section 7 ever disagree, SPEC.md is right and this file is wrong.

Transliteration rules held to here, because the point of the artifact is spec
conformance and not working software:

  * Same identifiers. SCL `#hmiLinkOk` is `hmiLinkOk`; `"ForkliftHmi".X` is
    `db.ForkliftHmi.X`; `#HMI_STALE_TIME` is `K.HMI_STALE_TIME`.
  * Same order. The seven numbered parts appear in the order section 7 has them
    and every statement inside a part keeps its position. Nothing is hoisted,
    merged, short-circuited or reordered for efficiency.
  * Same constants, to the digit, from SPEC.md section 3.3.
  * No improvement. Where a statement looks redundant it is transliterated
    anyway; where it looks wrong it is transliterated anyway and reported.

No OPC UA in this file. It takes a plain image in, mutates statics, and writes a
plain image out, so it can be read side by side with section 7 without server
noise in the way.
"""

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Constants -- SPEC.md section 3.3. Times in seconds; SCL's T#600ms is 0.600.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Constants:
    HMI_STALE_TIME: float = 0.600               # T#600ms
    TRACTION_SPEED_MAX: float = 1.00            # m/s
    TRACTION_SPEED_CAP_RAISED: float = 0.30     # m/s
    FORK_HEIGHT_SLOW_THRESHOLD: float = 0.50    # m
    FORK_SPEED_MAX: float = 0.15                # m/s
    STEER_ANGLE_MAX: float = 1.31               # rad
    FORK_TRAVEL_MIN: float = 0.05               # m
    FORK_TRAVEL_MAX: float = 1.55               # m
    FORK_HEIGHT_MIN: float = -0.05              # m
    FORK_HEIGHT_MAX: float = 1.70               # m
    LINEAR_SPEED_MIN: float = -2.00             # m/s
    LINEAR_SPEED_MAX: float = 2.00              # m/s
    OBSTACLE_DISTANCE_MIN: float = 0.05         # m
    OBSTACLE_DISTANCE_MAX: float = 8.10         # m
    TRACTION_REQUEST_MIN: float = -1.05
    TRACTION_REQUEST_MAX: float = 1.05
    FORK_REQUEST_MIN: float = -1.05
    FORK_REQUEST_MAX: float = 1.05
    STEER_REQUEST_MIN: float = -1.35            # rad
    STEER_REQUEST_MAX: float = 1.35             # rad
    TRACTION_REQUEST_CLAMP: float = 1.00
    FORK_REQUEST_CLAMP: float = 1.00
    PLANT_FAULT_DELAY: float = 0.300            # T#300ms
    LIDAR_FAULT_DELAY: float = 0.300            # T#300ms
    REQUEST_FAULT_DELAY: float = 0.600          # T#600ms


K = Constants()

# The one constant that is NOT section 3.3's. It belongs to FB_DemoCellControl
# (plc/demo-cell/SPEC.md section 3.3) and is used only by the companion fragment
# at the bottom of this file, which is not part of section 7.
HEARTBEAT_STALE_TIME = 0.500                    # T#500ms, demo-cell


# --------------------------------------------------------------------------
# IEC TON
# --------------------------------------------------------------------------


class Ton:
    """IEC 61131-3 TON.

    IN false            -> Q false, ET 0.
    IN false->true      -> ET 0, Q false on that very call (a real TON does not
                           credit the call in which IN rises).
    IN held true        -> ET accumulates, Q true once ET >= PT, ET holds at PT.

    ET is accumulated from the measured scan period rather than from a nominal
    20 ms, which is what an S7 TON does: it times against the CPU clock, not
    against an assumed cycle.
    """

    def __init__(self) -> None:
        self.ET = 0.0
        self.Q = False
        self._running = False

    def __call__(self, IN: bool, PT: float, dt: float) -> "Ton":
        if not IN:
            self.ET = 0.0
            self.Q = False
            self._running = False
        else:
            if not self._running:
                self._running = True
                self.ET = 0.0
            else:
                self.ET = min(self.ET + dt, PT)
            self.Q = self.ET >= PT
        return self


def LIMIT(MN: float, IN: float, MX: float) -> float:
    """SCL LIMIT(MN := , IN := , MX := ), same argument order and names."""
    if IN < MN:
        return MN
    if IN > MX:
        return MX
    return IN


# --------------------------------------------------------------------------
# Statics -- SPEC.md section 3.2, with its start values.
# The instance DB "ForkliftControl_DB". No tag here is Retain.
# --------------------------------------------------------------------------


@dataclass
class Statics:
    LastHmiHeartbeat: int = 0
    HmiStaleTimer: Ton = field(default_factory=Ton)
    HmiSeenAlive: bool = False
    TeleopEnableEdgeMemory: bool = True         # start value TRUE
    ResetEdgeMemory: bool = True                # start value TRUE
    ResetDeviceFault: bool = True               # start value TRUE
    ObstacleStopLatch: bool = False
    HmiLinkLostLatch: bool = False
    BridgeLinkLostLatch: bool = False
    PlantInputFaultLatch: bool = False
    RequestFaultLatch: bool = False
    PlantInvalidTimer: Ton = field(default_factory=Ton)
    LidarInvalidTimer: Ton = field(default_factory=Ton)
    RequestInvalidTimer: Ton = field(default_factory=Ton)


# --------------------------------------------------------------------------
# The global DBs -- SPEC.md section 3.1, with its start values.
# --------------------------------------------------------------------------


@dataclass
class ForkliftHmi:
    HmiTractionRequest: float = 0.0
    HmiSteerRequest: float = 0.0
    HmiForkRequest: float = 0.0
    HmiTeleopRequest: bool = False
    HmiResetRequest: bool = False


@dataclass
class ForkliftInput:
    ForkliftForkHeight: float = 0.0
    ForkliftLinearSpeed: float = 0.0
    ForkliftObstacleInStopZone: bool = True     # the one non-zero start value
    ForkliftObstacleMinDistance: float = 0.0


@dataclass
class ForkliftOutput:
    ForkliftTractionSpeedRef: float = 0.0
    ForkliftSteerAngleRef: float = 0.0
    ForkliftForkSpeedRef: float = 0.0


@dataclass
class ForkliftStatus:
    ForkliftTeleopActive: bool = False
    ForkliftObstacleStopActive: bool = False
    ForkliftSpeedLimitActive: bool = False
    ForkliftResetRequired: bool = False


@dataclass
class ForkliftLink:
    HmiHeartbeat: int = 0
    HmiLinkOk: bool = False


@dataclass
class DemoCellLink:
    """The M3 cell's Link DB. Owned by FB_DemoCellControl, not by this block.

    BridgeLinkOk is CONSUMED by section 7 and never written by it. The companion
    fragment below stands in for the M3 block that owns it.
    """
    BridgeHeartbeat: int = 0
    BridgeLinkOk: bool = False


@dataclass
class Db:
    ForkliftHmi: ForkliftHmi = field(default_factory=ForkliftHmi)
    ForkliftInput: ForkliftInput = field(default_factory=ForkliftInput)
    ForkliftOutput: ForkliftOutput = field(default_factory=ForkliftOutput)
    ForkliftStatus: ForkliftStatus = field(default_factory=ForkliftStatus)
    ForkliftLink: ForkliftLink = field(default_factory=ForkliftLink)
    DemoCellLink: DemoCellLink = field(default_factory=DemoCellLink)


@dataclass
class DemoCellStatics:
    """Statics of the companion fragment only. Not section 3.2."""
    LastBridgeHeartbeat: int = 0
    HeartbeatStaleTimer: Ton = field(default_factory=Ton)
    HeartbeatSeenAlive: bool = False


# --------------------------------------------------------------------------
# FB_ForkliftTeleop -- SPEC.md section 7, transliterated.
# Called from OB30 (20 ms), once, AFTER FB_DemoCellControl. Nowhere else,
# and never a second instance.
# --------------------------------------------------------------------------


def FB_ForkliftTeleop(db: Db, st: Statics, dt: float) -> None:
    # ---- 1. Link supervision (before anything that reads an input) ------------
    # HMI heartbeat: this FB owns HmiLinkOk.
    hmiHbChanged = (db.ForkliftLink.HmiHeartbeat != st.LastHmiHeartbeat)
    st.HmiStaleTimer(IN=not hmiHbChanged, PT=K.HMI_STALE_TIME, dt=dt)
    st.LastHmiHeartbeat = db.ForkliftLink.HmiHeartbeat   # inequality only, never subtract
    if hmiHbChanged:
        st.HmiSeenAlive = True   # one-shot, start value FALSE, non-retain
    # BOTH terms. NOT staleTimer.Q alone reads "not YET proven stale", which is TRUE
    # for the first HMI_STALE_TIME of every CPU run, before any operator input has
    # arrived. NEVER write HmiLinkOk := NOT #HmiStaleTimer.Q.
    db.ForkliftLink.HmiLinkOk = st.HmiSeenAlive and not st.HmiStaleTimer.Q
    hmiLinkOk = db.ForkliftLink.HmiLinkOk

    # Bridge heartbeat: owned by FB_DemoCellControl, CONSUMED here. One session,
    # one heartbeat, one verdict (invariant 10). NEVER assign to this tag.
    bridgeLinkOk = db.DemoCellLink.BridgeLinkOk

    if not hmiLinkOk:
        st.HmiLinkLostLatch = True        # degraded mode, not a safety event
    if not bridgeLinkOk:
        st.BridgeLinkLostLatch = True     # separate latch: the watch table names the link

    # ---- 2. Plausibility: all six Reals, affirmative, link-qualified ----------
    # Affirmative AND of two window comparisons per value; the fault is the ELSE of
    # this. NaN and inf make BOTH comparisons false, so they land in the fault
    # branch. NEVER invert into NOT(x < MIN OR x > MAX): that form returns TRUE for
    # NaN and passes a dead transducer downstream as a measurement.

    # 2a. Plant state (bridge-written).
    heightValid = (bridgeLinkOk
                   and (K.FORK_HEIGHT_MIN < db.ForkliftInput.ForkliftForkHeight)
                   and (db.ForkliftInput.ForkliftForkHeight < K.FORK_HEIGHT_MAX))
    speedValid = (bridgeLinkOk
                  and (K.LINEAR_SPEED_MIN < db.ForkliftInput.ForkliftLinearSpeed)
                  and (db.ForkliftInput.ForkliftLinearSpeed < K.LINEAR_SPEED_MAX))
    plantInputsValid = heightValid and speedValid

    st.PlantInvalidTimer(IN=bridgeLinkOk and not plantInputsValid,
                         PT=K.PLANT_FAULT_DELAY, dt=dt)
    if st.PlantInvalidTimer.Q:
        st.PlantInputFaultLatch = True

    # 2b. Lidar diagnostic distance. This is a statement about the TRANSDUCER.
    # The vehicle layer's no-data sentinel 0.0 lies outside the window on purpose.
    # There is NO comparison of this value against a stop distance anywhere in this
    # program: the field verdict belongs to the device (invariant 10).
    distanceValid = (bridgeLinkOk
                     and (K.OBSTACLE_DISTANCE_MIN < db.ForkliftInput.ForkliftObstacleMinDistance)
                     and (db.ForkliftInput.ForkliftObstacleMinDistance < K.OBSTACLE_DISTANCE_MAX))

    st.LidarInvalidTimer(IN=bridgeLinkOk and not distanceValid,
                         PT=K.LIDAR_FAULT_DELAY, dt=dt)

    # 2c. Operator requests (HMI-written). An out-of-window request is a BROKEN
    # CLIENT, not a demand. Clamping it silently would hide exactly that.
    requestsValid = (hmiLinkOk
                     and (K.TRACTION_REQUEST_MIN < db.ForkliftHmi.HmiTractionRequest)
                     and (db.ForkliftHmi.HmiTractionRequest < K.TRACTION_REQUEST_MAX)
                     and (K.STEER_REQUEST_MIN < db.ForkliftHmi.HmiSteerRequest)
                     and (db.ForkliftHmi.HmiSteerRequest < K.STEER_REQUEST_MAX)
                     and (K.FORK_REQUEST_MIN < db.ForkliftHmi.HmiForkRequest)
                     and (db.ForkliftHmi.HmiForkRequest < K.FORK_REQUEST_MAX))

    st.RequestInvalidTimer(IN=hmiLinkOk and not requestsValid,
                           PT=K.REQUEST_FAULT_DELAY, dt=dt)
    if st.RequestInvalidTimer.Q:
        st.RequestFaultLatch = True

    # ---- 3. Obstacle latch (PROCESS stop; not SF-03, not any SRS function) ----
    # Level, no delay, no debounce on the field bit. The bridgeLinkOk conjunct is
    # what keeps this out of the boot window: the node's START VALUE IS TRUE, so
    # without it a cold-started CPU would latch a stop no lidar ever reported.
    if bridgeLinkOk and (db.ForkliftInput.ForkliftObstacleInStopZone
                         or st.LidarInvalidTimer.Q):
        st.ObstacleStopLatch = True
    db.ForkliftStatus.ForkliftObstacleStopActive = st.ObstacleStopLatch

    # ---- 4. World / permissive / cause-gone (kept distinct on purpose) -------
    worldOk = (bridgeLinkOk                                                  # C1
               and hmiLinkOk                                                 # C2
               and not db.ForkliftInput.ForkliftObstacleInStopZone           # C3
               and plantInputsValid                                          # C4
               and distanceValid                                             # C5
               and requestsValid)                                            # C6

    latchPending = (st.ObstacleStopLatch or st.HmiLinkLostLatch
                    or st.BridgeLinkLostLatch or st.PlantInputFaultLatch
                    or st.RequestFaultLatch)
    db.ForkliftStatus.ForkliftResetRequired = latchPending

    motionPermissive = worldOk and not latchPending   # may the machine MOVE
    causeGone = worldOk                               # may a RESET clear latches
    # Latches are absent from causeGone on purpose: a latch must not be its own
    # precondition for clearing. The fork soft limits are absent from BOTH: a
    # blanket limit permissive would strand a carriage sitting on a limit, since
    # leaving one requires moving. They abort fork motion in the offending
    # direction only, in part 6 below.

    # ---- 5. Monitored reset, then a SEPARATE enable edge (order matters) -----
    # latchPending was computed ONCE, above, so an enable edge in the SAME call as
    # a reset still sees the latch and is refused.
    resetRise = db.ForkliftHmi.HmiResetRequest and not st.ResetEdgeMemory
    teleopRise = (hmiLinkOk and db.ForkliftHmi.HmiTeleopRequest
                  and not st.TeleopEnableEdgeMemory)
    st.ResetEdgeMemory = db.ForkliftHmi.HmiResetRequest          # start value TRUE
    st.TeleopEnableEdgeMemory = db.ForkliftHmi.HmiTeleopRequest  # start value TRUE

    # The guard is a LEVEL verdict about the CURRENT HMI link session, re-armed at
    # every link loss -- not a once-per-run latch. Cleared only by seeing the request
    # FALSE with the link up AFTER the last outage, so a reset asserted across a CPU
    # restart or an HMI restart cannot clear a latch at link-up (P6). The HMI writes
    # all six of its nodes EVERY cycle, so at a normal link-up the node already
    # carries a real FALSE and this clears within one OB call.
    if not hmiLinkOk:
        st.ResetDeviceFault = True    # re-arm; start value is TRUE for the same reason
    elif not db.ForkliftHmi.HmiResetRequest:
        st.ResetDeviceFault = False   # seen FALSE, in THIS link session

    if resetRise and not st.ResetDeviceFault and latchPending and causeGone:
        st.ObstacleStopLatch = False
        st.HmiLinkLostLatch = False
        st.BridgeLinkLostLatch = False
        st.PlantInputFaultLatch = False
        st.RequestFaultLatch = False
        # Reset clears latches. It energizes NOTHING: no enable, no setpoint.
        # Enabling the machine is a SEPARATE, deliberate operator action, below.

    if teleopRise and not latchPending and motionPermissive:
        db.ForkliftStatus.ForkliftTeleopActive = True

    # Dropped by ANY interlock, any latch, or the operator withdrawing the enable --
    # immediately, in the same OB call. motionPermissive already carries both link
    # verdicts and latchPending, so this one test covers every drop condition.
    if not (motionPermissive and db.ForkliftHmi.HmiTeleopRequest):
        db.ForkliftStatus.ForkliftTeleopActive = False

    # ---- 6. Caps, clamps and the direction-scoped fork limits ----------------
    # (NOT heightValid) OR ... is the load-bearing half: written as a bare
    # comparison, a NaN height reads as NOT raised and hands the machine the FULL
    # speed cap -- the permissive direction on a fault.
    forkRaised = ((not heightValid)
                  or (db.ForkliftInput.ForkliftForkHeight > K.FORK_HEIGHT_SLOW_THRESHOLD))

    if forkRaised:
        speedCap = K.TRACTION_SPEED_CAP_RAISED
    else:
        speedCap = K.TRACTION_SPEED_MAX
    # "The cap is IN FORCE", not "the cap is biting": stable on a display and in a
    # recording, and it does not flicker with the operator's control (section 6.5).
    db.ForkliftStatus.ForkliftSpeedLimitActive = (
        db.ForkliftStatus.ForkliftTeleopActive and forkRaised)

    # Clamp to the ENGINEERING RANGE. A value inside the plausibility window but
    # outside this range is a legitimate +/-1.0 that narrowed upward through
    # float64 -> Real. A value outside the WINDOW is a fault and was caught in
    # part 2c -- the window and the clamp are two different decisions.
    tractionDemand = LIMIT(MN=-K.TRACTION_REQUEST_CLAMP,
                           IN=db.ForkliftHmi.HmiTractionRequest,
                           MX=K.TRACTION_REQUEST_CLAMP)
    forkDemand = LIMIT(MN=-K.FORK_REQUEST_CLAMP,
                       IN=db.ForkliftHmi.HmiForkRequest,
                       MX=K.FORK_REQUEST_CLAMP)

    # Direction-scoped aborts. NEVER a blanket "inside the limits" permissive: a
    # carriage on a limit can only leave it by moving, and a permissive would
    # strand it there. An implausible height blocks BOTH directions.
    raiseBlocked = ((not heightValid)
                    or (db.ForkliftInput.ForkliftForkHeight >= K.FORK_TRAVEL_MAX))
    lowerBlocked = ((not heightValid)
                    or (db.ForkliftInput.ForkliftForkHeight <= K.FORK_TRAVEL_MIN))
    forkDemandAllowed = (((forkDemand > 0.0) and not raiseBlocked)
                         or ((forkDemand < 0.0) and not lowerBlocked))
    # forkDemand = 0.0 is not "allowed" and falls to the ELSE below: same 0.0,
    # one branch.

    # ---- 7. THE ONLY assignments to the three actuator setpoints ------------
    # Gating an analogue value = driving it to zero. Not a coil. Each ELSE is
    # mandatory: without it the Real keeps its last value, the bridge keeps
    # republishing it, and the machine keeps moving after the stop.
    if db.ForkliftStatus.ForkliftTeleopActive and motionPermissive:
        db.ForkliftOutput.ForkliftTractionSpeedRef = tractionDemand * speedCap
    else:
        db.ForkliftOutput.ForkliftTractionSpeedRef = 0.0

    # Steering returns to CENTRE on every stop. RULED: opcua-nodes.md section 10.6
    # and P5 require all three setpoints, the steer angle included, to take 0.0 in
    # the interlock-failed ELSE; the earlier exemption for steering is withdrawn.
    # All three assignments run in the same call, so the wheel is re-aimed on a
    # machine whose traction setpoint has already gone to 0.0.
    if db.ForkliftStatus.ForkliftTeleopActive and motionPermissive:
        db.ForkliftOutput.ForkliftSteerAngleRef = LIMIT(
            MN=-K.STEER_ANGLE_MAX,
            IN=db.ForkliftHmi.HmiSteerRequest,
            MX=K.STEER_ANGLE_MAX)
    else:
        db.ForkliftOutput.ForkliftSteerAngleRef = 0.0

    # 0.0 means HOLD: the plant holds the carriage against gravity.
    if (db.ForkliftStatus.ForkliftTeleopActive and motionPermissive
            and forkDemandAllowed):
        db.ForkliftOutput.ForkliftForkSpeedRef = forkDemand * K.FORK_SPEED_MAX
    else:
        db.ForkliftOutput.ForkliftForkSpeedRef = 0.0


# --------------------------------------------------------------------------
# COMPANION FRAGMENT -- NOT part of SPEC.md section 7.
#
# Section 7 consumes "DemoCellLink".BridgeLinkOk and never writes it: the tag is
# owned by FB_DemoCellControl, which this double does not implement. Something
# has to produce it, or a real bridge would advance BridgeHeartbeat forever with
# BridgeLinkOk stuck FALSE and no teleop loop could be rehearsed at all.
#
# So this is the heartbeat half of plc/demo-cell/SPEC.md section 7 part 1,
# transliterated from THAT document with ITS constant (HEARTBEAT_STALE_TIME =
# T#500ms, demo-cell section 3.3). It carries the heartbeat, the seen-alive
# one-shot and the verdict, and NOTHING else of the M3 cell -- no LinkLostLatch,
# no conveyor, no panel, no sequence.
#
# It runs BEFORE FB_ForkliftTeleop in the scan, which is the OB30 call order
# SPEC.md section 4.1 fixes.
# --------------------------------------------------------------------------


def FB_DemoCellControl_link_fragment(db: Db, st: DemoCellStatics, dt: float) -> None:
    hbChanged = (db.DemoCellLink.BridgeHeartbeat != st.LastBridgeHeartbeat)
    st.HeartbeatStaleTimer(IN=not hbChanged, PT=HEARTBEAT_STALE_TIME, dt=dt)
    st.LastBridgeHeartbeat = db.DemoCellLink.BridgeHeartbeat   # never subtract
    if hbChanged:
        st.HeartbeatSeenAlive = True
    db.DemoCellLink.BridgeLinkOk = (st.HeartbeatSeenAlive
                                    and not st.HeartbeatStaleTimer.Q)
