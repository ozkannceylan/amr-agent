#!/usr/bin/env python3
"""FB_DemoCellControl — the M3 demonstration cell's standard program.

A statement-for-statement transliteration of plc/demo-cell/SPEC.md section 7
(the SCL sketch), parts 2-8, with section 3.2's statics and section 3.3's
constants to the digit. Called from the same 20 ms cyclic cadence as OB30.

Part 1 (the bridge-heartbeat half that owns `DemoCell/Link/BridgeLinkOk`)
is NOT here: in this two-era CPU it keeps the home it already had — the
companion fragment at the head of standard_program.py's scan, which runs
first and whose verdict this scan consumes as `linkOk`, exactly as part 2
of the sketch consumes part 1's. One tag, one writer.

Where this file and the SPEC disagree, the SPEC is right and this file is
wrong. Nothing here is a safety function: the cell's stops are process
behaviour (SPEC section 2's boundary statement).
"""

from dataclasses import dataclass, field

from plc_logic_ref import Ton

# ---------------------------------------------------------------------------
# Constants — SPEC section 3.3, to the digit. Commissioning values, not
# measurements; the node model and the bridge design refused to make them.
# ---------------------------------------------------------------------------

PRESENT_THRESHOLD = 1.00        # m — midway between 1.440 clear and 0.540 blocked
PRESENT_CLEAR = 1.10            # m — 0.10 m hysteresis against a jittering beam
PRESENCE_FILTER = 0.100         # T#100ms, both directions
RANGE_MIN = 0.05                # m — the photo-eye's physical window
RANGE_MAX = 3.00
BELT_POSITION_MIN = -2.60       # m — the encoder's physical window (stops at ±2.50)
BELT_POSITION_MAX = 2.60
BELT_SPEED_MIN = -1.00          # m/s — the drive's physical window
BELT_SPEED_MAX = 1.00
RANGE_FAULT_DELAY = 0.200       # T#200ms — tolerates one dropped sample
BELT_FAULT_DELAY = 0.200        # its own constant: a different transducer
TRANSPORT_SPEED = 0.15          # m/s — ≈9 s from the product's start to the beam
RETURN_SPEED = -0.15            # m/s — negative = towards -x
HOME_WINDOW = 0.05              # m
SOFT_LIMIT = 2.40               # m — 0.10 m inside the mechanical stops
DWELL_TIME = 2.0                # T#2s — the stand-in transfer at the station
STEP_TIMEOUT = 60.0             # T#60s — watchdog on any moving step
SPEED_TOLERANCE = 0.02          # m/s — 13 % of transport speed
DRIVE_FAULT_DELAY = 1.0         # T#1s — covers start transients and the reversal
POSITION_WINDOW_TIME = 1.0      # T#1s — one freeze window (section 6.6)
POSITION_FREEZE_BAND = 0.005    # m — detects a freeze, never second-guesses a speed


# ---------------------------------------------------------------------------
# The image — SPEC section 3.1's server-visible tags, start values as tabled.
# The Link folder (BridgeHeartbeat, BridgeLinkOk) lives in standard_program's
# Db: the fragment's home since the M5 project.
# ---------------------------------------------------------------------------


@dataclass
class CellDb:
    # DemoCellInput — written by the bridge from the cell's devices
    ConveyorBeltPosition: float = 0.0
    ConveyorBeltSpeed: float = 0.0
    ProductSensorRange: float = 0.0
    PanelStartPressed: bool = False
    PanelResetPressed: bool = False
    PanelStopCircuitClosed: bool = False
    PanelProcessStopCircuitClosed: bool = False
    # DemoCellOutput — written by this program only
    ConveyorSpeedCommand: float = 0.0
    # DemoCellStatus — written by this program only
    CellCycleRunning: bool = False
    CellProcessStopActive: bool = False
    CellResetRequired: bool = False
    ProductPresentAtSensor: bool = False
    ConveyorDriveFault: bool = False


@dataclass
class CellStatics:
    """SPEC section 3.2, minus the link half (the companion fragment's)."""
    StartEdgeMemory: bool = True        # start value TRUE: a stuck start cannot start
    ResetEdgeMemory: bool = True        # start value TRUE: a held reset yields no edge
    ResetDeviceFault: bool = True       # start value TRUE: not seen open this session
    SeqStep: int = 0                    # 0 Idle, 10 Transport, 20 Dwell, 30 Return, 40 Complete
    DwellTimer: Ton = field(default_factory=Ton)
    StepTimer: Ton = field(default_factory=Ton)
    PresenceOnTimer: Ton = field(default_factory=Ton)
    PresenceOffTimer: Ton = field(default_factory=Ton)
    RangeInvalidTimer: Ton = field(default_factory=Ton)
    BeltFeedbackInvalidTimer: Ton = field(default_factory=Ton)
    DriveFaultTimer: Ton = field(default_factory=Ton)
    PositionRef: float = 0.0
    PositionWindowTimer: Ton = field(default_factory=Ton)
    PosWindowArmed: bool = False
    PositionFrozen: bool = False
    ProcessStopLatch: bool = False
    LinkLostLatch: bool = False
    SensorFaultLatch: bool = False
    BeltFeedbackFaultLatch: bool = False
    SequenceFaultLatch: bool = False
    SpeedRequest: float = 0.0


# ---------------------------------------------------------------------------
# The scan — section 7's part order: 2, 2b, 3, 4, 5, 6, 7, 8. Part 1's one
# cell-side consequence (LinkLostLatch) stands where the sketch has it.
# ---------------------------------------------------------------------------


def scan(cell: CellDb, cs: CellStatics, linkOk: bool, dt: float) -> None:
    # ---- 1 (cell side). The link loss latch — a degraded mode, not a safety
    # event. linkOk itself is the companion fragment's verdict, this cycle's.
    if not linkOk:
        cs.LinkLostLatch = True

    # ---- 2. Photo-eye validity and presence -------------------------------
    # Affirmative AND of two window comparisons: NaN and inf make BOTH false
    # and land in the fault branch. Never invert this form (section 6.2).
    rangeValid = (linkOk
                  and (cell.ProductSensorRange >= RANGE_MIN)
                  and (cell.ProductSensorRange <= RANGE_MAX))

    cs.RangeInvalidTimer(IN=linkOk and not rangeValid, PT=RANGE_FAULT_DELAY, dt=dt)
    if cs.RangeInvalidTimer.Q:
        cs.SensorFaultLatch = True

    if rangeValid:
        cs.PresenceOnTimer(IN=cell.ProductSensorRange < PRESENT_THRESHOLD,
                           PT=PRESENCE_FILTER, dt=dt)
        cs.PresenceOffTimer(IN=cell.ProductSensorRange > PRESENT_CLEAR,
                            PT=PRESENCE_FILTER, dt=dt)
        if cs.PresenceOnTimer.Q:
            cell.ProductPresentAtSensor = True
        elif cs.PresenceOffTimer.Q:
            cell.ProductPresentAtSensor = False
        # between thresholds: hold
    else:
        cell.ProductPresentAtSensor = False     # not attributable

    # ---- 2b. Belt feedback plausibility (same form, same gating) ----------
    beltFeedbackValid = (linkOk
                         and (cell.ConveyorBeltPosition >= BELT_POSITION_MIN)
                         and (cell.ConveyorBeltPosition <= BELT_POSITION_MAX)
                         and (cell.ConveyorBeltSpeed >= BELT_SPEED_MIN)
                         and (cell.ConveyorBeltSpeed <= BELT_SPEED_MAX))

    cs.BeltFeedbackInvalidTimer(IN=linkOk and not beltFeedbackValid,
                                PT=BELT_FAULT_DELAY, dt=dt)
    if cs.BeltFeedbackInvalidTimer.Q:
        cs.BeltFeedbackFaultLatch = True
    # No last-known-good substitution anywhere.

    # ---- 3. Drive fault, incl. signal-loss case D --------------------------
    cmdMoving = abs(cell.ConveyorSpeedCommand) > SPEED_TOLERANCE
    beltMoving = (beltFeedbackValid
                  and (abs(cell.ConveyorBeltSpeed) > SPEED_TOLERANCE))

    # The freeze window RE-ARMS for as long as motion is claimed (6.6.1).
    windowRunning = linkOk and beltMoving and cs.PosWindowArmed
    cs.PositionWindowTimer(IN=windowRunning, PT=POSITION_WINDOW_TIME, dt=dt)
    windowExpired = windowRunning and cs.PositionWindowTimer.Q

    if windowExpired:                           # one verdict per window
        cs.PositionFrozen = (abs(cell.ConveyorBeltPosition - cs.PositionRef)
                             < POSITION_FREEZE_BAND)

    if linkOk and beltMoving:
        if not cs.PosWindowArmed:
            # Arm, or RE-arm on the release call: the reference is the
            # position NOW, never the position at the start of the stroke.
            cs.PositionRef = cell.ConveyorBeltPosition
            cs.PosWindowArmed = True
        elif windowExpired:
            cs.PosWindowArmed = False           # release the TON for one call
    else:
        cs.PosWindowArmed = False
        cs.PositionFrozen = False               # a LEVEL verdict: it clears too

    d1 = beltFeedbackValid and cmdMoving and not beltMoving   # stalled / case D at rest
    d2 = beltMoving and cs.PositionFrozen                     # case D mid-motion

    cs.DriveFaultTimer(IN=linkOk and (d1 or d2), PT=DRIVE_FAULT_DELAY, dt=dt)
    if cs.DriveFaultTimer.Q:
        cell.ConveyorDriveFault = True

    # ---- 4. Stops (wire NC, program NO: plain NO contacts) -----------------
    if linkOk and (not cell.PanelStopCircuitClosed
                   or not cell.PanelProcessStopCircuitClosed):
        cs.ProcessStopLatch = True              # PROCESS stop. Not a safety function.
    cell.CellProcessStopActive = cs.ProcessStopLatch

    # ---- 5. World / permissive / cause-gone (kept distinct on purpose) -----
    worldOk = (cell.PanelStopCircuitClosed                    # C1
               and cell.PanelProcessStopCircuitClosed         # C2
               and linkOk                                     # C3
               and rangeValid                                 # C4
               and beltFeedbackValid)                         # C5

    runPermissive = (worldOk
                     and not cell.ConveyorDriveFault          # the DELAYED verdict...
                     and not cs.SensorFaultLatch
                     and not cs.BeltFeedbackFaultLatch
                     and not cs.SequenceFaultLatch)
    # ...not d1/d2: D1 is momentarily true at every start of motion.

    causeGone = worldOk and not (d1 or d2)      # may a RESET clear latches
    # Latches are absent from causeGone on purpose.

    latchPending = (cs.ProcessStopLatch or cs.LinkLostLatch or cs.SensorFaultLatch
                    or cs.BeltFeedbackFaultLatch
                    or cs.SequenceFaultLatch or cell.ConveyorDriveFault)
    cell.CellResetRequired = latchPending

    # ---- 6. Monitored reset, then a SEPARATE start (order matters) ---------
    resetRise = cell.PanelResetPressed and not cs.ResetEdgeMemory
    startRise = cell.PanelStartPressed and not cs.StartEdgeMemory
    cs.ResetEdgeMemory = cell.PanelResetPressed     # start value TRUE
    cs.StartEdgeMemory = cell.PanelStartPressed     # start value TRUE

    if not linkOk:
        cs.ResetDeviceFault = True              # re-arm at every link loss
    elif not cell.PanelResetPressed:
        cs.ResetDeviceFault = False             # contact seen open, THIS session

    if resetRise and not cs.ResetDeviceFault and latchPending and causeGone:
        cs.ProcessStopLatch = False
        cs.LinkLostLatch = False
        cs.SensorFaultLatch = False
        cs.SequenceFaultLatch = False
        cs.BeltFeedbackFaultLatch = False
        cell.ConveyorDriveFault = False
        # Reset clears latches. It energizes NOTHING.

    if startRise and not latchPending and runPermissive and cs.SeqStep == 0:
        cell.CellCycleRunning = True
        # Re-read where the belt IS; never resume from stale sequence state.
        if abs(cell.ConveyorBeltPosition) <= HOME_WINDOW:
            cs.SeqStep = 10                     # at home: transport
        else:
            cs.SeqStep = 30                     # elsewhere: re-home first

    if not runPermissive:                       # any interlock, any time
        cell.CellCycleRunning = False
        cs.SeqStep = 0

    # ---- 7. Sequence: sets SpeedRequest ONLY --------------------------------
    if cs.SeqStep == 0:
        cs.SpeedRequest = 0.0
    elif cs.SeqStep == 10:
        cs.SpeedRequest = TRANSPORT_SPEED
        if cell.ProductPresentAtSensor:
            cs.SeqStep = 20
        if cell.ConveyorBeltPosition >= SOFT_LIMIT:
            cs.SequenceFaultLatch = True
    elif cs.SeqStep == 20:
        cs.SpeedRequest = 0.0
        if cs.DwellTimer.Q:
            cs.SeqStep = 30
    elif cs.SeqStep == 30:
        cs.SpeedRequest = RETURN_SPEED
        if abs(cell.ConveyorBeltPosition) <= HOME_WINDOW:
            cs.SeqStep = 40
        if cell.ConveyorBeltPosition <= -SOFT_LIMIT:
            cs.SequenceFaultLatch = True
    elif cs.SeqStep == 40:
        cs.SpeedRequest = 0.0
        cell.CellCycleRunning = False
        cs.SeqStep = 0
    else:
        cs.SeqStep = 0
        cs.SpeedRequest = 0.0

    # Step timers: called UNCONDITIONALLY, outside the step branches (6.5).
    cs.DwellTimer(IN=(cs.SeqStep == 20), PT=DWELL_TIME, dt=dt)
    cs.StepTimer(IN=(cs.SeqStep == 10) or (cs.SeqStep == 30), PT=STEP_TIMEOUT, dt=dt)
    if cs.StepTimer.Q:
        cs.SequenceFaultLatch = True

    # ---- 8. THE ONLY assignment to the actuator setpoint --------------------
    if cell.CellCycleRunning and runPermissive:
        cell.ConveyorSpeedCommand = cs.SpeedRequest
    else:
        cell.ConveyorSpeedCommand = 0.0
