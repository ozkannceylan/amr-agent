#!/usr/bin/env python3
"""F_Forklift_Safety [FB2] — a behavioural model of the first build's F-program.

Transcribed network-for-network from plc/forklift-safety/SPEC.md: the fourteen
core networks (section 5.1, as built 2026-07-30), the S015 validity check
(section 5.4, V1-V7) and the SLS/SS1 delta (section 11.5, SL1-SL20, D1, Q1-Q4,
M2-M4) — 49 networks in the post-delta order of section 11.5's block table.
Constants are section 3.3 and section 11.3, to the digit.

THIS IS NOT THE F-PROGRAM. It is the virtual PLC's answer to the expired
PLCSIM Advanced trial: the same demands latch, the same monitored reset is
required, the same boot signature reads back — so the first build's stack
runs as if the CPU existed. It claims no safety integrity, exactly as the
stand-in writer it replaces claimed none (SPEC section 7.8).

No OPC UA in this file: it takes the SafetyInputStandIn image in, mutates
statics, and the six outputs sit on the statics for the standard program to
read (the coupling contract of section 6, extended by section 11.8).
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants — SPEC section 3.3 and section 11.3. Times in seconds; T#200ms is
# 0.200. Every derivation is on the SPEC row named in the comment.
# ---------------------------------------------------------------------------

STANDIN_STALE_MAX = 1.0        # T#1s     — section 3.3 (ten F-cycles + twenty writer cycles)
RESET_HOLD_MIN = 0.200         # T#200ms  — SF-08's monitored window, SRS section 3
RESET_HOLD_MAX = 3.0           # T#3s     — same row
SPEED_DISCREPANCY_MAX = 31     # mm/s     — section 11.1 (4 sigma measured, rounded up)
SPEED_DISCREPANCY_TIME = 0.200 # T#200ms  — section 11.1 (two-cycle floor)
SPEED_STALE_MAX = 0.500        # T#500ms  — section 11.3 (five F-OB cycles)
SPEED_PLAUSIBLE_MAX = 4000     # mm/s     — section 11.3 (1.0 m/s at the 1.31 rad steer stop, rounded away)
SPEED_LIMIT_MAX = 300          # mm/s     — SRS SF-10 / SC-13 creep cap, quoted
SPEED_LIMIT_ONSET_MAX = 2.300  # T#2s300ms — section 11.3, revised m5-59 F4 (teleop ramp 1.00 -> 0.20)
SPEED_OVERLIMIT_TIME = 0.200   # T#200ms  — section 11.3
SPEED_STANDSTILL_MAX = 15      # mm/s     — section 11.1b (revised m5-59 F2; was 50)
SHAFT_DOUBT_TIME = 1.0         # T#1s     — section 11.3 (ten F-cycles)
SS1_TIME_MAX = 1.0             # T#1s     — SRS SF-03 reaction row, quoted


class Ton:
    """IEC 61131-3 TON, the same semantics the M4 logic double documented:
    the rising call gets no credit, ET accumulates the MEASURED scan period,
    Q holds at PT. A loop that overruns stretches its timers honestly."""

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


# ---------------------------------------------------------------------------
# The SafetyInputStandIn image — SPEC section 3.1 + section 11.3 (SD2).
# A STANDARD DB the writer role writes and the F-program reads; its eleven
# members and their start values are the contract. On real hardware this DB
# does not exist (section 6.3 item 4).
# ---------------------------------------------------------------------------


@dataclass
class StandInImage:
    EStopCircuitClosed: bool = False       # boots OPEN — the demand direction
    ZoneDeviceCircuitClosed: bool = False  # boots OPEN
    ResetButtonPressed: bool = False       # boots unpressed
    StandInHeartbeat: int = 0
    SpeedReadingA: int = 0                 # mm/s, signed tread speed
    SpeedReadingB: int = 0
    SpeedSeqA: int = 0                     # advances only on a fresh reading
    SpeedSeqB: int = 0
    MotionPresent: bool = True             # start TRUE: uncertainty resolves to moving
    MotionObservationValid: bool = False   # diagnosis only — read by no network
    WarningFieldClear: bool = False        # start FALSE: limit selected until a live WARN 1


# ---------------------------------------------------------------------------
# Statics — InstF_Forklift_Safety [DB3]. Section 3.3's eighteen plus section
# 11.3's twenty-five. Every timer a multi-instance TON. Nothing is Retain.
# ---------------------------------------------------------------------------


@dataclass
class FStatics:
    # --- core (section 3.3) ---
    ResetSeenOpen: bool = False            # one-shot: the device seen unpressed at least once
    ResetPressArmed: bool = False          # SR, reset-dominant
    ResetHoldMinTimer: Ton = field(default_factory=Ton)   # N6: the armed press's hold
    ResetHoldMaxTimer: Ton = field(default_factory=Ton)   # N7: the press's hold
    ResetHoldValid: bool = False           # SR, reset-dominant
    SafetyResetFault: bool = False         # SR, reset-dominant
    ResetMemory: bool = False              # one F-cycle of state for the two edges
    EStopDemand: bool = False              # RS, set-dominant — the SF-01 demand
    ZoneStopDemand: bool = False           # RS, set-dominant — the SF-07-pattern demand
    SafetyResetRequired: bool = False      # OR of the demand latches
    # --- S015 validity (section 5.4) ---
    HeartbeatMemory: int = 0
    HeartbeatChanged: bool = False
    HeartbeatSeen: bool = False            # one-shot, never cleared
    StandInStaleTimer: Ton = field(default_factory=Ton)
    StandInValid: bool = False
    EStopClosedValid: bool = False
    ZoneClosedValid: bool = False
    ResetValid: bool = False
    # --- speed monitor and SS1 (section 11.3) ---
    SpeedSeqAMemory: int = 0
    SpeedSeqBMemory: int = 0
    SpeedSeqAChanged: bool = False
    SpeedSeqBChanged: bool = False
    SpeedChainSeen: bool = False           # the arming one-shot
    SpeedAStaleTimer: Ton = field(default_factory=Ton)
    SpeedBStaleTimer: Ton = field(default_factory=Ton)
    SpeedAValid: bool = False
    SpeedBValid: bool = False
    SpeedStaleNow: bool = False
    WarningFieldClearValid: bool = False
    SpeedDiff: int = 0
    SpeedDiscrepantNow: bool = False
    SpeedDiscrepancyTimer: Ton = field(default_factory=Ton)
    SpeedNearZero: bool = False
    MotionPresentValid: bool = False
    ShaftDoubtNow: bool = False
    ShaftDoubtTimer: Ton = field(default_factory=Ton)
    SpeedLimitOnsetTimer: Ton = field(default_factory=Ton)
    SpeedOverLimitNow: bool = False
    SpeedOverLimitTimer: Ton = field(default_factory=Ton)
    SpeedCauseGone: bool = False
    SpeedMonitorDemand: bool = False       # D1 — RS, set-dominant
    Ss1Demand: bool = False                # Q1 — recomputed every cycle, no latch
    Ss1Timer: Ton = field(default_factory=Ton)
    VehicleStandstillNow: bool = False
    TorqueOffDemand: bool = False          # Q4 — RS, R = NOT Ss1Demand


# ---------------------------------------------------------------------------
# The 49 networks, in the post-delta order of section 11.5's block table:
#   1-7   V1-V7        the S015 validity check
#   8-27  SL1-SL20     the speed validity and monitor terms
#   28    CauseGone    core network 1, re-pointed (+SpeedCauseGone)
#   29-39 core 2-12    the monitored reset, then the two demand latches
#   40    D1           SpeedMonitorDemand
#   41    SafetyResetRequired, re-pointed (+SpeedMonitorDemand)
#   42-45 Q1-Q4        the SS1 sequencer
#   46-49 ResetMemory, HeartbeatMemory, SpeedSeqAMemory, SpeedSeqBMemory
# ---------------------------------------------------------------------------


def scan(img: StandInImage, st: FStatics, dt: float) -> None:
    """One F-cycle. dt is the MEASURED period (nominal 100 ms, OB123)."""

    # ---- V1-V7: the S015 validity check (before everything that reads a channel)
    st.HeartbeatChanged = img.StandInHeartbeat != st.HeartbeatMemory
    if st.HeartbeatChanged:
        st.HeartbeatSeen = True                      # V2: one-shot, never cleared
    st.StandInStaleTimer(IN=not st.HeartbeatChanged, PT=STANDIN_STALE_MAX, dt=dt)
    st.StandInValid = st.HeartbeatSeen and not st.StandInStaleTimer.Q
    # V5-V7: a dead writer reads as open / open / unpressed — never as a clear world
    st.EStopClosedValid = img.EStopCircuitClosed and st.StandInValid
    st.ZoneClosedValid = img.ZoneDeviceCircuitClosed and st.StandInValid
    st.ResetValid = img.ResetButtonPressed and st.StandInValid

    # ---- SL1-SL20: the speed world ----------------------------------------
    st.SpeedSeqAChanged = img.SpeedSeqA != st.SpeedSeqAMemory
    st.SpeedSeqBChanged = img.SpeedSeqB != st.SpeedSeqBMemory
    if st.SpeedSeqAChanged or st.SpeedSeqBChanged:
        st.SpeedChainSeen = True                     # SL3: arms once, never cleared
    st.SpeedAStaleTimer(IN=not st.SpeedSeqAChanged, PT=SPEED_STALE_MAX, dt=dt)
    st.SpeedBStaleTimer(IN=not st.SpeedSeqBChanged, PT=SPEED_STALE_MAX, dt=dt)
    st.SpeedAValid = (st.StandInValid and st.SpeedChainSeen
                      and not st.SpeedAStaleTimer.Q
                      and -SPEED_PLAUSIBLE_MAX < img.SpeedReadingA < SPEED_PLAUSIBLE_MAX)
    st.SpeedBValid = (st.StandInValid and st.SpeedChainSeen
                      and not st.SpeedBStaleTimer.Q
                      and -SPEED_PLAUSIBLE_MAX < img.SpeedReadingB < SPEED_PLAUSIBLE_MAX)
    st.SpeedStaleNow = st.SpeedChainSeen and not (st.SpeedAValid and st.SpeedBValid)
    st.WarningFieldClearValid = img.WarningFieldClear and st.StandInValid
    st.SpeedDiff = img.SpeedReadingA - img.SpeedReadingB
    st.SpeedDiscrepantNow = (st.SpeedAValid and st.SpeedBValid
                             and (st.SpeedDiff > SPEED_DISCREPANCY_MAX
                                  or st.SpeedDiff < -SPEED_DISCREPANCY_MAX))
    st.SpeedDiscrepancyTimer(IN=st.SpeedDiscrepantNow, PT=SPEED_DISCREPANCY_TIME, dt=dt)
    st.SpeedNearZero = (st.SpeedAValid and st.SpeedBValid
                        and abs(img.SpeedReadingA) < SPEED_STANDSTILL_MAX
                        and abs(img.SpeedReadingB) < SPEED_STANDSTILL_MAX)
    # SL14: the one validated channel whose fail direction is TRUE
    st.MotionPresentValid = img.MotionPresent or not st.StandInValid
    st.ShaftDoubtNow = st.SpeedNearZero and st.MotionPresentValid
    st.ShaftDoubtTimer(IN=st.ShaftDoubtNow, PT=SHAFT_DOUBT_TIME, dt=dt)
    st.SpeedLimitOnsetTimer(IN=not st.WarningFieldClearValid,
                            PT=SPEED_LIMIT_ONSET_MAX, dt=dt)
    st.SpeedOverLimitNow = (st.SpeedLimitOnsetTimer.Q
                            and ((st.SpeedAValid and abs(img.SpeedReadingA) > SPEED_LIMIT_MAX)
                                 or (st.SpeedBValid and abs(img.SpeedReadingB) > SPEED_LIMIT_MAX)))
    st.SpeedOverLimitTimer(IN=st.SpeedOverLimitNow, PT=SPEED_OVERLIMIT_TIME, dt=dt)
    # SL20: no latch in here — the live world only, or a reset could never fire
    st.SpeedCauseGone = not (st.SpeedStaleNow or st.SpeedDiscrepantNow
                             or st.ShaftDoubtNow or st.SpeedOverLimitNow)

    # ---- 28: CauseGone — core network 1, re-pointed ------------------------
    causeGone = st.EStopClosedValid and st.ZoneClosedValid and st.SpeedCauseGone

    # ---- 29-37: the monitored reset (core networks 2-10) -------------------
    if not st.ResetValid:
        st.ResetSeenOpen = True                      # one-shot, never cleared
    resetRise = st.ResetValid and not st.ResetMemory
    resetFall = (not st.ResetValid) and st.ResetMemory

    # N5 ResetPressArmed — SR, reset-dominant: the release and any returning
    # cause both outrank the arming.
    if (not st.ResetValid) or (not causeGone):
        st.ResetPressArmed = False
    elif resetRise and causeGone and st.ResetSeenOpen:
        st.ResetPressArmed = True

    # N6/N7: the two hold timers. N6 times the ARMED press; N7 times the press.
    st.ResetHoldMinTimer(IN=st.ResetPressArmed and st.ResetValid, PT=RESET_HOLD_MIN, dt=dt)
    st.ResetHoldMaxTimer(IN=st.ResetValid, PT=RESET_HOLD_MAX, dt=dt)
    holdMinQ = st.ResetHoldMinTimer.Q
    holdMaxQ = st.ResetHoldMaxTimer.Q

    # N8 SafetyResetFault — SR, reset-dominant: set by a stuck/bridged device,
    # cleared by the device returning to 0.
    if not st.ResetValid:
        st.SafetyResetFault = False
    elif holdMaxQ or (st.ResetValid and not st.ResetSeenOpen):
        st.SafetyResetFault = True

    # N9 ResetHoldValid — SR, reset-dominant: set at the monitored minimum,
    # cleared by the next rising edge, an over-long hold, or any cause returning.
    if resetRise or holdMaxQ or (not causeGone):
        st.ResetHoldValid = False
    elif holdMinQ:
        st.ResetHoldValid = True

    # N10 ResetPulse — one F-cycle, on the release of an armed, validly held
    # press with the whole live world clear.
    resetPulse = resetFall and st.ResetHoldValid and causeGone

    # ---- 38/39: the two demand latches — RS, SET-dominant ------------------
    # A cause standing in the same cycle as the reset pulse wins.
    for name, closedValid in (("EStopDemand", st.EStopClosedValid),
                              ("ZoneStopDemand", st.ZoneClosedValid)):
        if not closedValid:
            setattr(st, name, True)
        elif resetPulse:
            setattr(st, name, False)

    # ---- 40: D1 SpeedMonitorDemand — RS, set-dominant -----------------------
    if (st.SpeedStaleNow or st.SpeedDiscrepancyTimer.Q
            or st.ShaftDoubtTimer.Q or st.SpeedOverLimitTimer.Q):
        st.SpeedMonitorDemand = True
    elif resetPulse:
        st.SpeedMonitorDemand = False

    # ---- 41: SafetyResetRequired — re-pointed OR of three -------------------
    st.SafetyResetRequired = (st.EStopDemand or st.ZoneStopDemand
                              or st.SpeedMonitorDemand)

    # ---- 42-45: Q1-Q4, the SS1 sequencer ------------------------------------
    st.Ss1Demand = st.ZoneStopDemand or st.SpeedMonitorDemand
    st.Ss1Timer(IN=st.Ss1Demand, PT=SS1_TIME_MAX, dt=dt)
    st.VehicleStandstillNow = st.SpeedNearZero and not st.MotionPresentValid
    # Q4: set-dominant; R = NOT Ss1Demand, so the flag's life is the demand's life.
    if not st.Ss1Demand:
        st.TorqueOffDemand = False
    elif st.VehicleStandstillNow or st.Ss1Timer.Q:
        st.TorqueOffDemand = True

    # ---- 46-49: the four memory copies, last --------------------------------
    st.ResetMemory = st.ResetValid
    st.HeartbeatMemory = img.StandInHeartbeat
    st.SpeedSeqAMemory = img.SpeedSeqA
    st.SpeedSeqBMemory = img.SpeedSeqB
