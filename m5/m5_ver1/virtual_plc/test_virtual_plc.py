#!/usr/bin/env python3
"""The virtual PLC's proof, without PLCSIM.

Every test pins a documented behaviour of the F-networks, the standard
program or the writer role to the SPEC row it came from. Run on Windows:

    python -m pytest m5\\m5_ver1\\virtual_plc\\test_virtual_plc.py -q
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import f_program as fp
import standard_program as std
from virtual_plc import WriterRole


DT_F = 0.100
DT_S = 0.020


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_f():
    return fp.StandInImage(), fp.FStatics()


def f_cycles(img, st, n, dt=DT_F):
    for _ in range(n):
        fp.scan(img, st, dt)


def f_cycles_live(img, st, n):
    """Cycles with the writer's heartbeat advancing — a press does not stop
    the writer."""
    for _ in range(n):
        img.StandInHeartbeat += 1
        fp.scan(img, st, DT_F)


def live_writer(img, st, cycles=12):
    """The recorded boot: the writer alive with both circuits OPEN (the demand
    direction), so the demands latch; then the world closes."""
    for _ in range(3):
        img.StandInHeartbeat += 1
        fp.scan(img, st, DT_F)
    assert st.EStopDemand is True and st.ZoneStopDemand is True
    for _ in range(cycles):
        img.StandInHeartbeat += 1
        img.EStopCircuitClosed = True
        img.ZoneDeviceCircuitClosed = True
        fp.scan(img, st, DT_F)


def valid_reset_pulse(img, st, hold_cycles=3):
    """A monitored reset done by the book: press, hold >= 200 ms, release —
    the writer's heartbeat advancing throughout."""
    img.ResetButtonPressed = True
    f_cycles_live(img, st, hold_cycles)
    img.ResetButtonPressed = False
    f_cycles_live(img, st, 1)


class NullLog:
    path = os.devnull

    def file_only(self, *a):
        pass

    def say(self, *a):
        pass


def make_writer():
    img, _st = make_f()
    return WriterRole(img, NullLog(), command_file="", console_ok=False), img


# ---------------------------------------------------------------------------
# The boot signature — the recorded demo's first seconds.
# ---------------------------------------------------------------------------


def test_boot_signature():
    """SPEC 3.3 + 11.6: both circuits boot OPEN, the demands latch, the SS1
    second stage stands within 1 s, the speed monitor is NOT armed."""
    img, st = make_f()
    f_cycles(img, st, 12)                       # 1.2 s of a dead writer
    assert st.EStopDemand is True
    assert st.ZoneStopDemand is True
    assert st.SafetyResetRequired is True
    assert st.TorqueOffDemand is True           # Ss1Timer expired at 1.0 s
    assert st.SpeedMonitorDemand is False       # SpeedChainSeen never armed
    assert st.SafetyResetFault is False


def test_dead_writer_reads_as_open_world():
    """V5-V7: a dead writer can never read as a clear world."""
    img, st = make_f()
    img.EStopCircuitClosed = True               # the bit is set...
    img.ZoneDeviceCircuitClosed = True          # ...but the heartbeat is dead
    f_cycles(img, st, 12)
    assert st.StandInValid is False
    assert st.EStopClosedValid is False
    assert st.ZoneClosedValid is False
    assert st.EStopDemand is True and st.ZoneStopDemand is True


# ---------------------------------------------------------------------------
# The monitored reset — SF-08's window.
# ---------------------------------------------------------------------------


def test_reset_clears_the_demands():
    img, st = make_f()
    live_writer(img, st)
    assert st.EStopDemand is True               # latched at boot, world now clear
    valid_reset_pulse(img, st)
    assert st.EStopDemand is False
    assert st.ZoneStopDemand is False
    assert st.SafetyResetRequired is False
    f_cycles_live(img, st, 12)
    assert st.TorqueOffDemand is False          # the SS1 demand is gone


def test_short_press_is_no_reset():
    """A press shorter than T#200ms never arms the hold."""
    img, st = make_f()
    live_writer(img, st)
    img.ResetButtonPressed = True
    f_cycles_live(img, st, 1)                   # 100 ms < 200 ms
    img.ResetButtonPressed = False
    f_cycles_live(img, st, 2)
    assert st.EStopDemand is True               # nothing was cleared


def test_overlong_hold_is_a_fault_not_a_reset():
    """Held past T#3s: SafetyResetFault, and the release clears nothing."""
    img, st = make_f()
    live_writer(img, st)
    img.ResetButtonPressed = True
    f_cycles_live(img, st, 32)                  # 3.2 s, the writer alive throughout
    assert st.SafetyResetFault is True
    img.ResetButtonPressed = False
    f_cycles_live(img, st, 2)
    assert st.EStopDemand is True
    assert st.SafetyResetFault is False         # cleared by the device returning to 0


def test_boot_press_is_a_fault():
    """A device already pressed at boot was never seen open: fault, no reset."""
    img, st = make_f()
    img.ResetButtonPressed = True
    for _ in range(3):                          # boot: circuits open, demands latch
        img.StandInHeartbeat += 1
        fp.scan(img, st, DT_F)
    assert st.EStopDemand is True
    for _ in range(12):                         # the world closes, the press still held
        img.StandInHeartbeat += 1
        img.EStopCircuitClosed = True
        img.ZoneDeviceCircuitClosed = True
        fp.scan(img, st, DT_F)
    assert st.SafetyResetFault is True
    img.ResetButtonPressed = False
    f_cycles_live(img, st, 2)
    assert st.EStopDemand is True               # the fault press reset nothing


def test_reset_while_cause_standing_clears_nothing():
    """The e-stop still open: the reset pulse loses to the standing cause."""
    img, st = make_f()
    live_writer(img, st)
    img.EStopCircuitClosed = False              # the demand returns
    f_cycles(img, st, 2)
    valid_reset_pulse(img, st)
    assert st.EStopDemand is True


# ---------------------------------------------------------------------------
# The speed monitor — SF-10's four causes.
# ---------------------------------------------------------------------------


def speed_live(img, st, a=0, b=0):
    """A live speed chain at a standstill."""
    img.SpeedReadingA = a
    img.SpeedReadingB = b
    img.SpeedSeqA += 1
    img.SpeedSeqB += 1


def test_speed_discrepancy_latches():
    """|A-B| > 31 mm/s for 200 ms -> SpeedMonitorDemand (SL10-SL12, D1)."""
    img, st = make_f()
    live_writer(img, st)
    valid_reset_pulse(img, st)
    for _ in range(10):
        img.StandInHeartbeat += 1
        speed_live(img, st, a=100, b=200)       # 100 mm/s apart
        fp.scan(img, st, DT_F)
    assert st.SpeedMonitorDemand is True
    assert st.SafetyResetRequired is True


def test_frozen_sequences_latch():
    """The source goes quiet: the sequences freeze, 500 ms later a demand."""
    img, st = make_f()
    live_writer(img, st)
    for _ in range(5):
        img.StandInHeartbeat += 1
        speed_live(img, st)
        fp.scan(img, st, DT_F)
    for _ in range(8):                          # 800 ms of silence
        img.StandInHeartbeat += 1
        fp.scan(img, st, DT_F)
    assert st.SpeedMonitorDemand is True


def test_over_limit_only_after_the_onset():
    """Warning field occupied: the 300 mm/s cap applies after T#2s300ms
    (SL17-SL19). The onset timer runs from the occupation, not from boot."""
    img, st = make_f()
    img.WarningFieldClear = True                # clear field: no limit in force
    live_writer(img, st)
    valid_reset_pulse(img, st)
    img.WarningFieldClear = False               # the field is occupied NOW
    for _ in range(20):                         # 2.0 s at 500 mm/s: still inside the onset
        img.StandInHeartbeat += 1
        speed_live(img, st, a=500, b=500)
        fp.scan(img, st, DT_F)
    assert st.SpeedMonitorDemand is False
    for _ in range(8):                          # past 2.3 s + the 200 ms over-limit timer
        img.StandInHeartbeat += 1
        speed_live(img, st, a=500, b=500)
        fp.scan(img, st, DT_F)
    assert st.SpeedMonitorDemand is True


def test_shaft_doubt():
    """Encoders say standstill, the observer says moving, for 1 s: demand."""
    img, st = make_f()
    live_writer(img, st)
    valid_reset_pulse(img, st)
    img.MotionPresent = True                    # the observer sees motion
    for _ in range(12):
        img.StandInHeartbeat += 1
        speed_live(img, st, a=0, b=0)           # the shaft says stopped
        fp.scan(img, st, DT_F)
    assert st.SpeedMonitorDemand is True


# ---------------------------------------------------------------------------
# The SS1 sequencer.
# ---------------------------------------------------------------------------


def test_ss1_torque_off_at_standstill():
    """Zone demand with a proven standstill: torque off without the 1 s wait."""
    img, st = make_f()
    live_writer(img, st)
    valid_reset_pulse(img, st)
    img.MotionPresent = False                   # corroborated standstill
    img.ZoneDeviceCircuitClosed = False         # the intrusion
    for _ in range(3):
        img.StandInHeartbeat += 1
        speed_live(img, st, a=0, b=0)
        fp.scan(img, st, DT_F)
    assert st.ZoneStopDemand is True
    assert st.TorqueOffDemand is True           # before any 1 s wait


def test_ss1_torque_off_by_timer_when_motion_uncertain():
    """MotionPresent stuck TRUE (its fail direction): the 1 s timer decides."""
    img, st = make_f()
    live_writer(img, st)
    valid_reset_pulse(img, st)
    img.MotionPresent = True
    img.ZoneDeviceCircuitClosed = False
    for _ in range(3):
        img.StandInHeartbeat += 1
        speed_live(img, st, a=0, b=0)
        fp.scan(img, st, DT_F)
    assert st.TorqueOffDemand is False          # standstill not corroborated
    for _ in range(9):                          # 1.2 s of demand total
        img.StandInHeartbeat += 1
        speed_live(img, st, a=0, b=0)
        fp.scan(img, st, DT_F)
    assert st.TorqueOffDemand is True


# ---------------------------------------------------------------------------
# The standard program and the safety coupling.
# ---------------------------------------------------------------------------


def make_std():
    return std.Db(), std.Statics(), std.DemoCellStatics(), fp.FStatics()


def std_cycles(db, st, dc, fst, n, dt=DT_S):
    for _ in range(n):
        std.scan(db, st, dc, fst, dt)


def links_alive(db, dc_heartbeat=1, hmi_heartbeat=1):
    db.DemoCellLink.BridgeHeartbeat = dc_heartbeat
    db.ForkliftLink.HmiHeartbeat = hmi_heartbeat


def test_teleop_blocked_by_a_standing_safety_demand():
    """The coupling conjunct: EStopDemand TRUE, teleop can never energize."""
    db, st, dc, fst = make_std()
    fst.EStopDemand = True                      # as it boots
    db.ForkliftInput.ForkliftObstacleInStopZone = False
    db.ForkliftInput.ForkliftForkHeight = 0.1
    db.ForkliftInput.ForkliftObstacleMinDistance = 2.0
    db.ForkliftProcessStop.HmiProcessStopRequest = False
    db.ForkliftMode.HmiDriveModeRequest = std.MODE_TELEOP
    db.ForkliftHmi.HmiTeleopRequest = True
    db.ForkliftHmi.HmiTractionRequest = 0.5
    for i in range(1, 60):                      # links alive, standstill proven
        links_alive(db, i, i)
        std_cycles(db, st, dc, fst, 1)
    assert db.ForkliftStatus.ForkliftTeleopActive is False
    assert db.ForkliftOutput.ForkliftTractionSpeedRef == 0.0


def test_mirrors_follow_the_f_statics():
    """S5: the six mirrors are the F-program's operands, every cycle."""
    db, st, dc, fst = make_std()
    fst.EStopDemand = True
    fst.TorqueOffDemand = True
    fst.SpeedMonitorDemand = True
    std_cycles(db, st, dc, fst, 2)
    m = db.ForkliftSafetyMirror
    assert (m.EStopDemand, m.ZoneStopDemand, m.SafetyResetRequired,
            m.SafetyResetFault, m.SpeedMonitorDemand, m.TorqueOffDemand) == \
        (True, False, False, False, True, True)


def clear_world(db):
    db.ForkliftInput.ForkliftObstacleInStopZone = False
    db.ForkliftInput.ForkliftForkHeight = 0.1
    db.ForkliftInput.ForkliftObstacleMinDistance = 2.0
    db.ForkliftProcessStop.HmiProcessStopRequest = False


def boot_to_mode_none(db, st, dc, fst):
    """The demo's first minute: links come alive, the boot latches stand
    (ProcessStopLatch starts TRUE), the operator's standard-program reset
    clears them. Returns with the world clear and the mode still NONE."""
    clear_world(db)
    for i in range(1, 40):                      # 800 ms: links ok, standstill proven
        links_alive(db, i, i)
        db.ForkliftHmi.HmiResetRequest = (i == 10)   # one rising edge, device seen open
        std_cycles(db, st, dc, fst, 1)
    db.ForkliftHmi.HmiResetRequest = False
    assert db.ForkliftStatus.ForkliftResetRequired is False


def test_teleop_runs_when_the_world_is_clear():
    """The happy path the demo recorded: reset, mode entered, teleop edge,
    the request scaled by the cap."""
    db, st, dc, fst = make_std()
    boot_to_mode_none(db, st, dc, fst)
    db.ForkliftWarning.ForkliftWarningFieldOccupied = False
    db.ForkliftMode.HmiDriveModeRequest = std.MODE_TELEOP   # the selector's edge
    links_alive(db, 41, 41)
    std_cycles(db, st, dc, fst, 1)
    assert db.ForkliftMode.ForkliftDriveModeActive == std.MODE_TELEOP
    db.ForkliftHmi.HmiTeleopRequest = True      # the enable edge
    db.ForkliftHmi.HmiTractionRequest = 0.5
    for i in range(42, 52):
        links_alive(db, i, i)
        std_cycles(db, st, dc, fst, 1)
    assert db.ForkliftStatus.ForkliftTeleopActive is True
    assert db.ForkliftOutput.ForkliftTractionSpeedRef == pytest.approx(0.5 * 1.0)


def test_warning_ceiling_in_teleop():
    """14.17: warning field occupied -> the teleop scale drops to 0.20 m/s."""
    db, st, dc, fst = make_std()
    boot_to_mode_none(db, st, dc, fst)
    db.ForkliftWarning.ForkliftWarningFieldOccupied = True
    db.ForkliftMode.HmiDriveModeRequest = std.MODE_TELEOP
    links_alive(db, 41, 41)
    std_cycles(db, st, dc, fst, 1)
    db.ForkliftHmi.HmiTeleopRequest = True
    db.ForkliftHmi.HmiTractionRequest = 0.5
    for i in range(42, 52):
        links_alive(db, i, i)
        std_cycles(db, st, dc, fst, 1)
    assert db.ForkliftStatus.ForkliftTeleopActive is True
    assert db.ForkliftOutput.ForkliftTractionSpeedRef == pytest.approx(0.5 * 0.20)


# ---------------------------------------------------------------------------
# The writer role.
# ---------------------------------------------------------------------------


def test_writer_commands_and_refusals():
    w, img = make_writer()
    w.command("estop close")
    assert img.EStopCircuitClosed is True
    w.command("estop open")
    assert img.EStopCircuitClosed is False
    w.command("zone close")
    assert img.ZoneDeviceCircuitClosed is True
    w.command("reset press")
    assert img.ResetButtonPressed is True
    w.command("reset pulse 300")                # refused: already held
    assert w._pulse_end is None
    w.command("reset release")
    w.command("reset pulse 0")                  # refused: below the window
    assert w._pulse_end is None
    w.command("reset pulse 300")
    assert img.ResetButtonPressed is True
    assert w._pulse_end is not None
    w.command("definitely not a command")       # refused, logged, survived


def test_writer_zone_ownership():
    """While the field link is up the operator's 'zone close' is refused."""
    w, img = make_writer()
    w.field_client = object()                   # a link is up
    w.command("zone close")
    assert img.ZoneDeviceCircuitClosed is False


def test_writer_field_link_and_stale_reaper():
    w, img = make_writer()
    w.field_client = object()
    w.field_line("ZONE 1")
    assert img.ZoneDeviceCircuitClosed is True
    w.field_line("WARN 1")
    assert img.WarningFieldClear is True
    w.field_line("PING")
    w.field_line("garbage")                     # refused, refreshes nothing
    w.field_last = time.monotonic() - 2.0       # 2 s of silence
    import asyncio
    asyncio.run(w.cycle())
    assert img.ZoneDeviceCircuitClosed is False  # the reaper: intrusion + occupied
    assert img.WarningFieldClear is False
    assert w.field_client is None


def test_writer_speed_link():
    w, img = make_writer()
    w.speed_client = object()
    w.speed_line("SPD A 512")
    w.speed_line("SPD B -3")
    assert (img.SpeedReadingA, img.SpeedReadingB) == (512, -3)
    assert (img.SpeedSeqA, img.SpeedSeqB) == (1, 1)
    w.speed_line("MOT 1 1")
    assert img.MotionPresent is True and img.MotionObservationValid is True
    w.speed_line("SPD A 99999")                 # out of Int16 range: refused
    assert img.SpeedReadingA == 512


def test_writer_pulse_deadline():
    w, img = make_writer()
    import asyncio
    w.command("reset pulse 50")
    assert img.ResetButtonPressed is True
    time.sleep(0.08)
    asyncio.run(w.cycle())
    assert img.ResetButtonPressed is False
