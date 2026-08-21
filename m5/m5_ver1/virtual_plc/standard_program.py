#!/usr/bin/env python3
"""The first build's standard program, as the recorded M5 demo ran it.

FB_ForkliftTeleop — plc/forklift/SPEC.md section 7 (transliterated before in
plc/forklift/double/logic.py) AS AMENDED by:
  - section 14.8  (the M5 delta: mode arbiter, vehicle heartbeat, process stop,
                   envelope outputs; parts 2d, 3b, 5a, 8 new; parts 4, 5, 7 modified)
  - section 14.16 (the warning-field ceiling on the envelope, m5-49)
  - section 14.17 (the same ceiling in teleop, m5-59 F4)
  - the safety coupling of plc/forklift-safety/SPEC.md section 6.1 as extended
    by section 11.8 (six F-Bools read; one permissive conjunct; six mirrors
    written every cycle, unconditionally — S5)

plus the DemoCell link fragment of plc/demo-cell/SPEC.md section 7 part 1
(BridgeLinkOk's owner — the M3 cell itself was never in this project, owner
decision 2026-07-30).

Called from OB30's equivalent: a 20 ms cyclic scan. Where this file and the
SPECs disagree, the SPECs are right and this file is wrong. Nothing here is a
safety function (ADR 0008 D3); the F-program's model lives in f_program.py.
"""

from dataclasses import dataclass, field

from f_program import FStatics
from plc_logic_ref import K, Ton, LIMIT, HEARTBEAT_STALE_TIME

# ---------------------------------------------------------------------------
# New constants — SPEC section 14.3, to the digit.
# ---------------------------------------------------------------------------

MODE_NONE = 0
MODE_TELEOP = 1
MODE_AUTONOMOUS = 2
VEHICLE_STALE_TIME = 0.500          # T#500ms — its own constant, never shared
MODE_DISAGREE_DELAY = 2.0           # T#2s
AUTONOMOUS_SPEED_CEILING = 0.60     # m/s — 60 % of TRACTION_SPEED_MAX
STANDSTILL_SPEED = 0.05             # m/s
STANDSTILL_TIME = 0.500             # T#500ms
WARNING_SPEED_CEILING = 0.20        # m/s — section 14.16's derivation


# ---------------------------------------------------------------------------
# The global DBs — the OPC UA node's image. Start values are opcua-nodes.md
# section 10.9, section 12.8 and section 13: every start value is the
# non-permissive one.
# ---------------------------------------------------------------------------


@dataclass
class ForkliftHmi:                  # section 10.4 — the operator's requests
    HmiTractionRequest: float = 0.0
    HmiSteerRequest: float = 0.0
    HmiForkRequest: float = 0.0
    HmiTeleopRequest: bool = False
    HmiResetRequest: bool = False


@dataclass
class ForkliftMode:                 # section 12.3
    HmiDriveModeRequest: int = 0        # writable
    ForkliftDriveModeActive: int = 0    # the PLC's answer, read-only


@dataclass
class ForkliftInput:                # section 10.5 — plant state, bridge-written
    ForkliftForkHeight: float = 0.0
    ForkliftLinearSpeed: float = 0.0
    ForkliftObstacleInStopZone: bool = True   # the one non-zero start value
    ForkliftObstacleMinDistance: float = 0.0


@dataclass
class ForkliftVehicle:              # section 12.6 — the vehicle's report
    ForkliftVehicleModeApplied: int = 0
    ForkliftVehicleHeartbeat: int = 0


@dataclass
class ForkliftProcessStop:          # section 12.7 — both start TRUE
    HmiProcessStopRequest: bool = True
    ForkliftProcessStopActive: bool = True


@dataclass
class ForkliftWarning:              # section 13 — starts TRUE (occupied)
    ForkliftWarningFieldOccupied: bool = True


@dataclass
class ForkliftEnvelope:             # section 12.4 — the three envelope elements,
    ForkliftMotionEnable: bool = False      # read-only to every client: a
    ForkliftSpeedCeiling: float = 0.0       # permission is not a command
    ForkliftEquipmentPermit: bool = False


@dataclass
class ForkliftOutput:               # section 10.6 — the three setpoints
    ForkliftTractionSpeedRef: float = 0.0
    ForkliftSteerAngleRef: float = 0.0
    ForkliftForkSpeedRef: float = 0.0


@dataclass
class ForkliftStatus:               # section 10.7 — the PLC's verdicts
    ForkliftTeleopActive: bool = False
    ForkliftObstacleStopActive: bool = False
    ForkliftSpeedLimitActive: bool = False
    ForkliftResetRequired: bool = False


@dataclass
class ForkliftLink:                 # section 10.8 — the HMI's watchdog
    HmiHeartbeat: int = 0
    HmiLinkOk: bool = False


@dataclass
class DemoCellLink:                 # the M3 cell's link surface (bridge's heartbeat)
    BridgeHeartbeat: int = 0
    BridgeLinkOk: bool = False


@dataclass
class ForkliftSafetyMirror:         # section 11.8 / opcua-nodes.md section 11 —
    EStopDemand: bool = True            # six F-verdicts mirrored every cycle,
    ZoneStopDemand: bool = True         # read-only to every client. Start values
    SafetyResetRequired: bool = True    # are the sources' boot truth (section 11.6):
    SafetyResetFault: bool = False      # both demands boot latched, so the SS1
    SpeedMonitorDemand: bool = False    # second stage stands within 1 s of boot,
    TorqueOffDemand: bool = True        # and the speed monitor cannot be armed yet.


@dataclass
class Db:
    ForkliftHmi: ForkliftHmi = field(default_factory=ForkliftHmi)
    ForkliftMode: ForkliftMode = field(default_factory=ForkliftMode)
    ForkliftInput: ForkliftInput = field(default_factory=ForkliftInput)
    ForkliftVehicle: ForkliftVehicle = field(default_factory=ForkliftVehicle)
    ForkliftProcessStop: ForkliftProcessStop = field(default_factory=ForkliftProcessStop)
    ForkliftWarning: ForkliftWarning = field(default_factory=ForkliftWarning)
    ForkliftEnvelope: ForkliftEnvelope = field(default_factory=ForkliftEnvelope)
    ForkliftOutput: ForkliftOutput = field(default_factory=ForkliftOutput)
    ForkliftStatus: ForkliftStatus = field(default_factory=ForkliftStatus)
    ForkliftLink: ForkliftLink = field(default_factory=ForkliftLink)
    DemoCellLink: DemoCellLink = field(default_factory=DemoCellLink)
    ForkliftSafetyMirror: ForkliftSafetyMirror = field(default_factory=ForkliftSafetyMirror)


# ---------------------------------------------------------------------------
# Statics — ForkliftControl_DB: section 3.2's thirteen plus section 14.3's ten.
# ---------------------------------------------------------------------------


@dataclass
class Statics:
    # section 3.2
    LastHmiHeartbeat: int = 0
    HmiStaleTimer: Ton = field(default_factory=Ton)
    HmiSeenAlive: bool = False
    TeleopEnableEdgeMemory: bool = True      # start value TRUE
    ResetEdgeMemory: bool = True             # start value TRUE
    ResetDeviceFault: bool = True            # start value TRUE
    ObstacleStopLatch: bool = False
    HmiLinkLostLatch: bool = False
    BridgeLinkLostLatch: bool = False
    PlantInputFaultLatch: bool = False
    RequestFaultLatch: bool = False
    PlantInvalidTimer: Ton = field(default_factory=Ton)
    LidarInvalidTimer: Ton = field(default_factory=Ton)
    RequestInvalidTimer: Ton = field(default_factory=Ton)
    # section 14.3
    DriveModeInForce: int = 0                # MODE_NONE — the arbiter's state
    LastModeRequest: int = 0
    AutonomousArmed: bool = False
    LastVehicleHeartbeat: int = 0
    VehicleSeenAlive: bool = False
    VehicleStaleTimer: Ton = field(default_factory=Ton)
    ModeDisagreeTimer: Ton = field(default_factory=Ton)
    ModeDisagreeLatch: bool = False
    ProcessStopLatch: bool = True            # start value TRUE (section 12.7)
    StandstillTimer: Ton = field(default_factory=Ton)


@dataclass
class DemoCellStatics:
    """Statics of the companion fragment only (demo-cell section 3.2's link half)."""
    LastBridgeHeartbeat: int = 0
    HeartbeatStaleTimer: Ton = field(default_factory=Ton)
    HeartbeatSeenAlive: bool = False


# ---------------------------------------------------------------------------
# The scan — OB30's equivalent, 20 ms nominal. Part order is section 7's as
# amended by section 14.8: 1, 2a-2d, 3, 3b, 4, 5a, 5, 6, 7, 8.
# ---------------------------------------------------------------------------


def scan(db: Db, st: Statics, dc: DemoCellStatics, f: FStatics, dt: float) -> None:
    # ---- 1. Link supervision ------------------------------------------------
    # The DemoCell companion fragment runs FIRST (the OB30 call order of
    # section 4.1): it owns BridgeLinkOk, which part 2 consumes.
    hbChanged = db.DemoCellLink.BridgeHeartbeat != dc.LastBridgeHeartbeat
    dc.HeartbeatStaleTimer(IN=not hbChanged, PT=HEARTBEAT_STALE_TIME, dt=dt)
    dc.LastBridgeHeartbeat = db.DemoCellLink.BridgeHeartbeat
    if hbChanged:
        dc.HeartbeatSeenAlive = True
    db.DemoCellLink.BridgeLinkOk = dc.HeartbeatSeenAlive and not dc.HeartbeatStaleTimer.Q
    bridgeLinkOk = db.DemoCellLink.BridgeLinkOk

    hmiHbChanged = db.ForkliftLink.HmiHeartbeat != st.LastHmiHeartbeat
    st.HmiStaleTimer(IN=not hmiHbChanged, PT=K.HMI_STALE_TIME, dt=dt)
    st.LastHmiHeartbeat = db.ForkliftLink.HmiHeartbeat
    if hmiHbChanged:
        st.HmiSeenAlive = True
    db.ForkliftLink.HmiLinkOk = st.HmiSeenAlive and not st.HmiStaleTimer.Q
    hmiLinkOk = db.ForkliftLink.HmiLinkOk

    if not hmiLinkOk:
        st.HmiLinkLostLatch = True
    if not bridgeLinkOk:
        st.BridgeLinkLostLatch = True

    # ---- 2a/2b/2c. Plausibility — affirmative, link-qualified (section 7) ---
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

    distanceValid = (bridgeLinkOk
                     and (K.OBSTACLE_DISTANCE_MIN < db.ForkliftInput.ForkliftObstacleMinDistance)
                     and (db.ForkliftInput.ForkliftObstacleMinDistance < K.OBSTACLE_DISTANCE_MAX))
    st.LidarInvalidTimer(IN=bridgeLinkOk and not distanceValid,
                         PT=K.LIDAR_FAULT_DELAY, dt=dt)

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

    # ---- 2d. The mode request, the vehicle's report, and standstill (14.8) --
    modeRequest = db.ForkliftMode.HmiDriveModeRequest
    modeRequestValid = (hmiLinkOk
                        and (modeRequest in (MODE_NONE, MODE_TELEOP, MODE_AUTONOMOUS)))

    vehicleHbChanged = db.ForkliftVehicle.ForkliftVehicleHeartbeat != st.LastVehicleHeartbeat
    st.VehicleStaleTimer(IN=not vehicleHbChanged, PT=VEHICLE_STALE_TIME, dt=dt)
    st.LastVehicleHeartbeat = db.ForkliftVehicle.ForkliftVehicleHeartbeat
    if vehicleHbChanged:
        st.VehicleSeenAlive = True
    vehicleAlive = bridgeLinkOk and st.VehicleSeenAlive and not st.VehicleStaleTimer.Q

    vehicleModeValid = db.ForkliftVehicle.ForkliftVehicleModeApplied in (
        MODE_NONE, MODE_TELEOP, MODE_AUTONOMOUS)
    modeDisagreeRaw = (vehicleAlive
                       and not (vehicleModeValid
                                and db.ForkliftVehicle.ForkliftVehicleModeApplied
                                == st.DriveModeInForce))
    st.ModeDisagreeTimer(IN=modeDisagreeRaw, PT=MODE_DISAGREE_DELAY, dt=dt)
    if st.ModeDisagreeTimer.Q:
        st.ModeDisagreeLatch = True

    atStandstill = speedValid and abs(db.ForkliftInput.ForkliftLinearSpeed) < STANDSTILL_SPEED
    st.StandstillTimer(IN=atStandstill, PT=STANDSTILL_TIME, dt=dt)

    # ---- 3. The obstacle latch (section 7 part 3) ---------------------------
    if bridgeLinkOk and (db.ForkliftInput.ForkliftObstacleInStopZone
                         or st.LidarInvalidTimer.Q):
        st.ObstacleStopLatch = True
    db.ForkliftStatus.ForkliftObstacleStopActive = st.ObstacleStopLatch

    # ---- 3b. The operator's process stop (14.8) ------------------------------
    if hmiLinkOk and db.ForkliftProcessStop.HmiProcessStopRequest:
        st.ProcessStopLatch = True
    db.ForkliftProcessStop.ForkliftProcessStopActive = st.ProcessStopLatch

    # ---- 4. World / permissive / cause-gone (14.8's modified statements) -----
    worldOk = (bridgeLinkOk                                                  # C1
               and hmiLinkOk                                                 # C2
               and not db.ForkliftInput.ForkliftObstacleInStopZone           # C3
               and plantInputsValid                                          # C4
               and distanceValid                                             # C5
               and requestsValid                                             # C6
               and not db.ForkliftProcessStop.HmiProcessStopRequest          # C7
               and not st.ModeDisagreeTimer.Q)                               # C8

    latchPending = (st.ObstacleStopLatch or st.HmiLinkLostLatch
                    or st.BridgeLinkLostLatch or st.PlantInputFaultLatch
                    or st.RequestFaultLatch
                    or st.ProcessStopLatch or st.ModeDisagreeLatch)
    db.ForkliftStatus.ForkliftResetRequired = latchPending

    # The safety coupling (forklift-safety SPEC section 6.1 + section 11.8):
    # six F-Bools read, one conjunct added. TorqueOffDemand is deliberately NOT
    # a permissive term — its consumer is the vehicle's inhibit.
    safetyDemandClear = (not f.EStopDemand and not f.ZoneStopDemand
                         and not f.SpeedMonitorDemand)

    motionPermissive = worldOk and not latchPending and safetyDemandClear
    causeGone = worldOk

    # ---- 5a. The mode arbiter (14.8) — ONE decision per call -----------------
    modeSelectRise = modeRequestValid and (modeRequest != st.LastModeRequest)
    modeEntryAdmitted = st.StandstillTimer.Q and motionPermissive

    if not modeRequestValid:
        st.DriveModeInForce = MODE_NONE                                    # X4
    elif modeRequest != st.DriveModeInForce:
        st.DriveModeInForce = MODE_NONE                                    # X3

    if (st.DriveModeInForce == MODE_NONE) and modeSelectRise and modeEntryAdmitted:
        if modeRequest == MODE_TELEOP:
            st.DriveModeInForce = MODE_TELEOP                              # X1
        elif modeRequest == MODE_AUTONOMOUS and vehicleAlive:
            st.DriveModeInForce = MODE_AUTONOMOUS                          # X2
            st.AutonomousArmed = True

    st.LastModeRequest = modeRequest

    if not ((st.DriveModeInForce == MODE_AUTONOMOUS)
            and motionPermissive and vehicleAlive):
        st.AutonomousArmed = False

    # ---- 5. Monitored reset, then a SEPARATE enable edge (7 + 14.8) ----------
    resetRise = db.ForkliftHmi.HmiResetRequest and not st.ResetEdgeMemory
    teleopRise = (hmiLinkOk and db.ForkliftHmi.HmiTeleopRequest
                  and not st.TeleopEnableEdgeMemory)
    st.ResetEdgeMemory = db.ForkliftHmi.HmiResetRequest
    st.TeleopEnableEdgeMemory = db.ForkliftHmi.HmiTeleopRequest

    if not hmiLinkOk:
        st.ResetDeviceFault = True
    elif not db.ForkliftHmi.HmiResetRequest:
        st.ResetDeviceFault = False

    if resetRise and not st.ResetDeviceFault and latchPending and causeGone:
        st.ObstacleStopLatch = False
        st.HmiLinkLostLatch = False
        st.BridgeLinkLostLatch = False
        st.PlantInputFaultLatch = False
        st.RequestFaultLatch = False
        st.ProcessStopLatch = False
        st.ModeDisagreeLatch = False
        # Reset clears latches. It energizes NOTHING.

    if (teleopRise and not latchPending and motionPermissive
            and st.DriveModeInForce == MODE_TELEOP):
        db.ForkliftStatus.ForkliftTeleopActive = True

    if not (motionPermissive and db.ForkliftHmi.HmiTeleopRequest
            and st.DriveModeInForce == MODE_TELEOP):
        db.ForkliftStatus.ForkliftTeleopActive = False

    # ---- 6. Caps, clamps and the direction-scoped fork limits (7 + 14.17) ----
    forkRaised = ((not heightValid)
                  or (db.ForkliftInput.ForkliftForkHeight > K.FORK_HEIGHT_SLOW_THRESHOLD))
    if forkRaised:
        speedCap = K.TRACTION_SPEED_CAP_RAISED
    else:
        speedCap = K.TRACTION_SPEED_MAX
    db.ForkliftStatus.ForkliftSpeedLimitActive = (
        db.ForkliftStatus.ForkliftTeleopActive and forkRaised)

    # The warning verdict, stale-safe (14.16): a dark transport cannot report
    # a clear field. TRUE = occupied.
    warningFieldOccupied = (db.ForkliftWarning.ForkliftWarningFieldOccupied
                            or not bridgeLinkOk)

    # 14.17: the warning ceiling reaches the teleop scale too — the F-monitor
    # cannot read the drive mode, so a mode left unclamped is a mode that
    # latches SpeedMonitorDemand.
    if warningFieldOccupied:
        teleopSpeedCap = min(speedCap, WARNING_SPEED_CEILING)
    else:
        teleopSpeedCap = speedCap

    tractionDemand = LIMIT(MN=-K.TRACTION_REQUEST_CLAMP,
                           IN=db.ForkliftHmi.HmiTractionRequest,
                           MX=K.TRACTION_REQUEST_CLAMP)
    forkDemand = LIMIT(MN=-K.FORK_REQUEST_CLAMP,
                       IN=db.ForkliftHmi.HmiForkRequest,
                       MX=K.FORK_REQUEST_CLAMP)

    raiseBlocked = ((not heightValid)
                    or (db.ForkliftInput.ForkliftForkHeight >= K.FORK_TRAVEL_MAX))
    lowerBlocked = ((not heightValid)
                    or (db.ForkliftInput.ForkliftForkHeight <= K.FORK_TRAVEL_MIN))
    forkDemandAllowed = (((forkDemand > 0.0) and not raiseBlocked)
                         or ((forkDemand < 0.0) and not lowerBlocked))

    # ---- 7. THE ONLY assignments to the three actuator setpoints -------------
    if db.ForkliftStatus.ForkliftTeleopActive and motionPermissive:
        db.ForkliftOutput.ForkliftTractionSpeedRef = tractionDemand * teleopSpeedCap
    else:
        db.ForkliftOutput.ForkliftTractionSpeedRef = 0.0

    if db.ForkliftStatus.ForkliftTeleopActive and motionPermissive:
        db.ForkliftOutput.ForkliftSteerAngleRef = LIMIT(
            MN=-K.STEER_ANGLE_MAX,
            IN=db.ForkliftHmi.HmiSteerRequest,
            MX=K.STEER_ANGLE_MAX)
    else:
        db.ForkliftOutput.ForkliftSteerAngleRef = 0.0

    if (db.ForkliftStatus.ForkliftTeleopActive and motionPermissive
            and forkDemandAllowed):
        db.ForkliftOutput.ForkliftForkSpeedRef = forkDemand * K.FORK_SPEED_MAX
    else:
        db.ForkliftOutput.ForkliftForkSpeedRef = 0.0

    # ---- 8. The mode node, the envelope, and the safety mirrors (14.8 + S5) --
    db.ForkliftMode.ForkliftDriveModeActive = st.DriveModeInForce

    autonomousMotionPermitted = ((st.DriveModeInForce == MODE_AUTONOMOUS)
                                 and st.AutonomousArmed
                                 and motionPermissive
                                 and vehicleAlive)
    db.ForkliftEnvelope.ForkliftMotionEnable = autonomousMotionPermitted

    if autonomousMotionPermitted:
        if warningFieldOccupied:
            speedCeiling = min(min(AUTONOMOUS_SPEED_CEILING, speedCap),
                               WARNING_SPEED_CEILING)
        else:
            speedCeiling = min(AUTONOMOUS_SPEED_CEILING, speedCap)
    else:
        speedCeiling = 0.0
    db.ForkliftEnvelope.ForkliftSpeedCeiling = speedCeiling

    equipmentPermit = bridgeLinkOk and not st.ProcessStopLatch           # EQ1, EQ2
    db.ForkliftEnvelope.ForkliftEquipmentPermit = equipmentPermit

    # S5: the six mirrors, written unconditionally, every cycle, from the
    # F-program's own operands — never recomputed here (S3).
    db.ForkliftSafetyMirror.EStopDemand = f.EStopDemand
    db.ForkliftSafetyMirror.ZoneStopDemand = f.ZoneStopDemand
    db.ForkliftSafetyMirror.SafetyResetRequired = f.SafetyResetRequired
    db.ForkliftSafetyMirror.SafetyResetFault = f.SafetyResetFault
    db.ForkliftSafetyMirror.SpeedMonitorDemand = f.SpeedMonitorDemand
    db.ForkliftSafetyMirror.TorqueOffDemand = f.TorqueOffDemand
