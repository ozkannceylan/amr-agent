"""virtual_fplc.py's model semantics. Nothing here needs PLCSIM or Tk.

Every behaviour asserted below is measured live (m5_ver2/CLAUDE.md
section 3.2, the step PROOFs) or an owner ruling recorded in
docs/superpowers/specs/2026-08-20-virtual-fplc-design.md. The cycle
boundary is a ReadBool("Motor") call, so the helpers read Motor to
advance the model exactly as m6.py's 20 ms loop does.
"""
import pytest

from virtual_fplc import VirtualFPLC

SCANNERS = ("PF_OSSD", "PF_OSSD_right", "PF_OSSD_left")
WARNINGS = ("WF_Clear", "WF_Clear_right", "WF_Clear_left")


def write_healthy(plc, enc=(0, 0)):
    """One cycle's input picture, everything healthy, ack released."""
    for tag in SCANNERS + WARNINGS:
        plc.WriteBool(tag, True)
    plc.WriteInt16("ENC_A", enc[0])
    plc.WriteInt16("ENC_B", enc[1])
    plc.WriteBool("E-Stop", True)
    plc.WriteBool("Acknowledge", False)


def ack(plc):
    """An Acknowledge rising edge with a cycle boundary inside it."""
    plc.WriteBool("Acknowledge", True)
    plc.ReadBool("Motor")
    plc.WriteBool("Acknowledge", False)


def enabled_plc():
    plc = VirtualFPLC()
    write_healthy(plc)
    ack(plc)
    assert plc.ReadBool("Motor") is True
    return plc


def test_startup_needs_one_ack_before_motor():
    plc = VirtualFPLC()
    write_healthy(plc)
    assert plc.ReadBool("Motor") is False    # ACK_NEC
    ack(plc)
    assert plc.ReadBool("Motor") is True


@pytest.mark.parametrize("tag", ("E-Stop",) + SCANNERS)
def test_each_demand_latches_and_healing_does_not_reenable(tag):
    plc = enabled_plc()
    plc.WriteBool(tag, False)
    assert plc.ReadBool("Motor") is False
    plc.WriteBool(tag, True)
    assert plc.ReadBool("Motor") is False    # latched
    ack(plc)
    assert plc.ReadBool("Motor") is True


def test_one_ack_clears_every_healthy_latch():
    plc = enabled_plc()
    plc.WriteBool("E-Stop", False)
    for tag in SCANNERS:
        plc.WriteBool(tag, False)
    assert plc.ReadBool("Motor") is False
    write_healthy(plc)
    ack(plc)
    assert plc.ReadBool("Motor") is True


def test_ack_skips_a_latch_whose_input_is_still_unhealthy():
    plc = enabled_plc()
    plc.WriteBool("PF_OSSD_left", False)
    ack(plc)                                 # consumed while unhealthy
    assert plc.ReadBool("Motor") is False
    plc.WriteBool("PF_OSSD_left", True)
    assert plc.ReadBool("Motor") is False
    ack(plc)
    assert plc.ReadBool("Motor") is True


def test_holding_acknowledge_is_one_edge_not_many():
    plc = enabled_plc()
    plc.WriteBool("Acknowledge", True)
    plc.ReadBool("Motor")                    # edge consumed here
    plc.WriteBool("PF_OSSD", False)
    plc.ReadBool("Motor")                    # demand latches
    plc.WriteBool("PF_OSSD", True)
    assert plc.ReadBool("Motor") is False    # still held: no new edge


def test_cross_check_trips_above_50():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 100)
    plc.WriteInt16("ENC_B", 160)
    assert plc.ReadBool("Motor") is False


def test_disagreement_of_exactly_50_is_allowed():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 100)
    plc.WriteInt16("ENC_B", 150)
    assert plc.ReadBool("Motor") is True


def test_half_written_encoder_pair_does_not_trip():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 500)             # B still 0: no read, no scan
    plc.WriteInt16("ENC_B", 500)
    assert plc.ReadBool("Motor") is True


def test_ceiling_2800_by_magnitude_either_direction():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", -2850)
    plc.WriteInt16("ENC_B", -2850)
    assert plc.ReadBool("Motor") is False


def test_speed_above_v_limit_trips_when_any_wf_violated():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 500)
    plc.WriteInt16("ENC_B", 500)
    assert plc.ReadBool("Motor") is True     # 500 < 1500
    plc.WriteBool("WF_Clear_left", False)    # any-WF ruling: limit 300
    assert plc.ReadBool("Motor") is False


def test_dead_link_picture_0_3000_trips():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 0)
    plc.WriteInt16("ENC_B", 3000)
    assert plc.ReadBool("Motor") is False


def test_the_speed_instance_latches_and_one_ack_re_enables():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 100)
    plc.WriteInt16("ENC_B", 400)             # 300 apart: cross-check fault
    assert plc.ReadBool("Motor") is False
    plc.WriteInt16("ENC_B", 100)             # the channels agree again
    assert plc.ReadBool("Motor") is False    # latched, like every instance
    ack(plc)
    assert plc.ReadBool("Motor") is True


@pytest.mark.parametrize("wf", WARNINGS)
def test_v_limit_is_300_when_any_single_wf_is_violated(wf):
    plc = VirtualFPLC()
    write_healthy(plc)
    assert plc.ReadInt16("V_Limit") == 1500
    plc.WriteBool(wf, False)
    assert plc.ReadInt16("V_Limit") == 300


def test_v_limit_heals_with_the_warning_field_and_never_latches():
    # V_Limit is computed in the standard OB1, not in the safety program:
    # it follows the warning fields both ways. Only the ESTOP1 instance
    # the limit tripped stays latched, and that is Motor's business.
    plc = VirtualFPLC()
    write_healthy(plc)
    assert plc.ReadInt16("V_Limit") == 1500
    plc.WriteBool("WF_Clear_right", False)
    assert plc.ReadInt16("V_Limit") == 300
    plc.WriteBool("WF_Clear_right", True)
    assert plc.ReadInt16("V_Limit") == 1500


def test_case_bits_are_pinned_at_case_1():
    plc = VirtualFPLC()
    assert plc.ReadBool("CASE_B0") is True
    assert plc.ReadBool("CASE_B1") is False


def test_input_readback_returns_the_process_image():
    plc = VirtualFPLC()
    plc.WriteBool("E-Stop", True)
    assert plc.ReadBool("E-Stop") is True
    plc.WriteBool("E-Stop", False)
    assert plc.ReadBool("E-Stop") is False


def test_unknown_tags_raise_keyerror():
    plc = VirtualFPLC()
    with pytest.raises(KeyError):
        plc.WriteBool("NoSuchTag", True)
    with pytest.raises(KeyError):
        plc.ReadBool("NoSuchTag")
