#!/usr/bin/env python3
"""Behavioural pins for demo_cell_program.py — FB_DemoCellControl as specified
in plc/demo-cell/SPEC.md sections 5, 6 and 7.

Every test drives the scan directly (20 ms cycles) and reads the image.
The link half (BridgeLinkOk) is the companion fragment's; these tests pass
linkOk in as the fragment would have produced it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import demo_cell_program as dc  # noqa: E402

DT = 0.020  # OB30's 20 ms


def fresh():
    return dc.CellDb(), dc.CellStatics()


def cycles(cell, cs, n, link_ok=True):
    for _ in range(n):
        dc.scan(cell, cs, link_ok, DT)


def healthy(cell):
    """The world the permissive wants: circuits closed, beam clear, belt home."""
    cell.PanelStopCircuitClosed = True
    cell.PanelProcessStopCircuitClosed = True
    cell.ProductSensorRange = 1.440          # the cell's own beam-clear value
    cell.ConveyorBeltPosition = 0.0
    cell.ConveyorBeltSpeed = 0.0


def boot_link_down(cell, cs, n=5):
    """CPU start with no bridge: the boot window (SPEC 6.1)."""
    cycles(cell, cs, n, link_ok=False)


def link_up_healthy(cell, cs):
    """A link session with a healthy world, long enough for the filters."""
    healthy(cell)
    cycles(cell, cs, 10, link_ok=True)


def press(cell, cs, contact, hold_s=0.1):
    """A clean press-and-release of a panel contact, edges included."""
    setattr(cell, contact, True)
    cycles(cell, cs, max(1, int(hold_s / DT)))
    setattr(cell, contact, False)
    cycles(cell, cs, 2)


# ---------------------------------------------------------------------------
# Boot and link supervision
# ---------------------------------------------------------------------------

def test_boot_no_latches_from_start_values_except_link_lost():
    cell, cs = fresh()
    boot_link_down(cell, cs)
    # The corrected boot polarity (6.1): no process-stop latch from DB start
    # values; the link's absence is what stands.
    assert cs.ProcessStopLatch is False
    assert cs.LinkLostLatch is True
    assert cell.CellProcessStopActive is False
    assert cell.CellResetRequired is True       # LinkLostLatch is a latch
    assert cell.ConveyorSpeedCommand == 0.0


def test_reset_held_across_link_up_cannot_clear():
    # The inverted T4.7 / R3 case: reset held from before link-up is refused
    # (ResetDeviceFault), only a fresh rising edge clears.
    cell, cs = fresh()
    boot_link_down(cell, cs)
    cell.PanelResetPressed = True               # held through the outage
    link_up_healthy(cell, cs)
    cycles(cell, cs, 10)
    assert cs.LinkLostLatch is True             # still latched: no edge counted
    # The contact seen open, then a fresh press: now the reset acts.
    cell.PanelResetPressed = False
    cycles(cell, cs, 3)
    press(cell, cs, "PanelResetPressed")
    assert cs.LinkLostLatch is False
    assert cell.CellResetRequired is False


def test_link_loss_during_run_latches_and_zeroes():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    press(cell, cs, "PanelResetPressed")        # clear the boot LinkLostLatch
    press(cell, cs, "PanelStartPressed")
    assert cell.CellCycleRunning is True
    cell.ConveyorBeltSpeed = 0.15               # the plant answering
    cycles(cell, cs, 3)
    cycles(cell, cs, 3, link_ok=False)          # the bridge stops
    assert cs.LinkLostLatch is True
    assert cell.CellCycleRunning is False
    assert cs.SeqStep == 0
    assert cell.ConveyorSpeedCommand == 0.0     # the mandatory ELSE


# ---------------------------------------------------------------------------
# The sequence (SPEC section 5)
# ---------------------------------------------------------------------------

def run_full_cycle(cell, cs):
    """Drive one transport-dwell-return cycle, the plant answering as the cell
    does: position integrates the command, the beam breaks at 1.37 m."""
    press(cell, cs, "PanelResetPressed")        # boot LinkLostLatch away
    press(cell, cs, "PanelStartPressed")
    assert cell.CellCycleRunning is True
    assert cs.SeqStep == 10
    assert cell.ConveyorSpeedCommand == dc.TRANSPORT_SPEED

    pos = 0.0
    for _ in range(int(30 / DT)):               # 30 s of plant
        # the cell applies the command as given, no ramp (sim/README.md)
        cell.ConveyorBeltSpeed = cell.ConveyorSpeedCommand
        pos += cell.ConveyorSpeedCommand * DT
        cell.ConveyorBeltPosition = pos
        # the photo-eye: blocked by the product at the beam position 1.37 m
        cell.ProductSensorRange = 0.540 if pos >= 1.37 else 1.440
        dc.scan(cell, cs, True, DT)
        if cs.SeqStep == 0:
            break
    return pos


def test_full_cycle_transports_dwells_returns_home():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    pos = run_full_cycle(cell, cs)
    assert cs.SeqStep == 0                      # Complete -> Idle
    assert cell.CellCycleRunning is False
    assert abs(pos) <= dc.HOME_WINDOW + 0.01    # the belt came home
    assert cell.ConveyorSpeedCommand == 0.0


def test_start_refused_while_a_latch_stands():
    cell, cs = fresh()
    boot_link_down(cell, cs)                    # the real boot: LinkLostLatch stands
    link_up_healthy(cell, cs)
    # the boot latch is still standing: no reset pressed yet
    press(cell, cs, "PanelStartPressed")
    assert cell.CellCycleRunning is False
    assert cs.SeqStep == 0


def test_start_away_from_home_rehomes_first():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    cell.ConveyorBeltPosition = 1.20            # parked mid-travel
    cycles(cell, cs, 2)
    press(cell, cs, "PanelResetPressed")
    press(cell, cs, "PanelStartPressed")
    assert cs.SeqStep == 30                     # re-home, not transport
    assert cell.ConveyorSpeedCommand == 0.0 or cs.SpeedRequest == dc.RETURN_SPEED


def test_stuck_start_at_boot_produces_no_edge():
    cell, cs = fresh()
    healthy(cell)
    cell.PanelStartPressed = True               # already closed at the first scan
    cycles(cell, cs, 10)
    assert cell.CellCycleRunning is False       # StartEdgeMemory started TRUE


# ---------------------------------------------------------------------------
# Stops and latches
# ---------------------------------------------------------------------------

def test_process_stop_latches_and_overrides():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    press(cell, cs, "PanelResetPressed")
    press(cell, cs, "PanelStartPressed")
    assert cell.CellCycleRunning is True
    # the red button opens its contact
    cell.PanelProcessStopCircuitClosed = False
    cycles(cell, cs, 2)
    assert cell.CellProcessStopActive is True
    assert cell.CellCycleRunning is False
    assert cell.ConveyorSpeedCommand == 0.0
    # healing the contact does not un-stop (no auto-resume)
    cell.PanelProcessStopCircuitClosed = True
    cycles(cell, cs, 5)
    assert cell.CellProcessStopActive is True
    # the monitored reset clears it, and the cycle stays down
    press(cell, cs, "PanelResetPressed")
    assert cell.CellProcessStopActive is False
    assert cell.CellCycleRunning is False


def test_reset_refused_while_the_cause_stands():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    cell.PanelProcessStopCircuitClosed = False
    cycles(cell, cs, 2)
    assert cs.ProcessStopLatch is True
    press(cell, cs, "PanelResetPressed")        # cause still standing
    assert cs.ProcessStopLatch is True          # causeGone was False
    cell.PanelProcessStopCircuitClosed = True
    cycles(cell, cs, 2)
    press(cell, cs, "PanelResetPressed")
    assert cs.ProcessStopLatch is False


# ---------------------------------------------------------------------------
# Sensor and drive faults
# ---------------------------------------------------------------------------

def test_implausible_range_faults_after_the_delay():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    cell.ProductSensorRange = float("nan")      # a dead photo-eye
    cycles(cell, cs, 5)                         # 100 ms < 200 ms: tolerated
    assert cs.SensorFaultLatch is False
    cycles(cell, cs, 10)                        # past the delay
    assert cs.SensorFaultLatch is True
    assert cell.ProductPresentAtSensor is False  # not attributable


def test_implausible_belt_feedback_is_its_own_latch():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    cell.ConveyorBeltPosition = 9.99            # beyond the physical window
    cycles(cell, cs, 15)
    assert cs.BeltFeedbackFaultLatch is True
    assert cs.SensorFaultLatch is False         # the watch table names the failed one


def test_stalled_drive_faults_but_a_healthy_start_does_not():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    press(cell, cs, "PanelResetPressed")
    press(cell, cs, "PanelStartPressed")
    # D1 is momentarily true at every start of motion; the delay must absorb it.
    # The belt never answers: stalled.
    cycles(cell, cs, int(1.5 / DT))
    assert cell.ConveyorDriveFault is True
    assert cell.CellCycleRunning is False


def test_freeze_window_rearms_and_catches_mid_motion_freeze():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    pos = 0.0
    press(cell, cs, "PanelResetPressed")
    press(cell, cs, "PanelStartPressed")
    frozen_at = None
    for i in range(int(6 / DT)):
        # the belt answers for ~2.5 s, then freezes mid-transport (case D)
        if i < int(2.5 / DT):
            cell.ConveyorBeltSpeed = cell.ConveyorSpeedCommand
            pos += cell.ConveyorSpeedCommand * DT
        else:
            cell.ConveyorBeltSpeed = 0.0        # frozen: speed lies still...
        cell.ConveyorBeltPosition = pos         # ...and the position stops
        dc.scan(cell, cs, True, DT)
        if cell.ConveyorDriveFault and frozen_at is None:
            frozen_at = i * DT
            break
    assert frozen_at is not None
    # window 1.04 s + DRIVE_FAULT_DELAY 1.0 s after the freeze, not 26.3 s
    assert frozen_at < 2.5 + 1.04 + 1.0 + 0.3


def test_soft_limit_aborts_the_travelling_step():
    cell, cs = fresh()
    link_up_healthy(cell, cs)
    press(cell, cs, "PanelResetPressed")
    press(cell, cs, "PanelStartPressed")
    pos = 0.0
    for _ in range(int(25 / DT)):
        cell.ConveyorBeltSpeed = cell.ConveyorSpeedCommand
        pos += cell.ConveyorSpeedCommand * DT
        cell.ConveyorBeltPosition = pos
        cell.ProductSensorRange = 1.440         # the beam never breaks
        dc.scan(cell, cs, True, DT)
        if cs.SequenceFaultLatch:
            break
    assert cs.SequenceFaultLatch is True
    assert pos >= dc.SOFT_LIMIT
    # the latch trips in part 7, after part 5's permissive: the command takes
    # the mandatory ELSE on the NEXT scan — the sketch's own one-cycle lag.
    cycles(cell, cs, 2)
    assert cell.ConveyorSpeedCommand == 0.0
