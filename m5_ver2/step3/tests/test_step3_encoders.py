"""step3.py's encoder fault injection."""
import step3


def test_ok_passes_both_channels_through():
    assert step3.apply_encoder_fault(400, 402, "ok", 0) == (400, 402)


def test_fa_freezes_channel_a_at_its_last_value():
    # Trips the cross-check as soon as the vehicle moves away from the
    # frozen value, and not before - which is the point of the mode.
    assert step3.apply_encoder_fault(400, 402, "fa", 0) == (0, 402)
    assert step3.apply_encoder_fault(900, 902, "fa", 400) == (400, 902)


def test_oa_offsets_channel_a_past_the_cross_check():
    a, b = step3.apply_encoder_fault(100, 102, "oa", 0)
    assert a == 100 + step3.ENC_OFFSET_MM_S
    assert abs(a - b) > 50      # the F-program's limit


def test_an_unknown_mode_passes_through_rather_than_inventing_a_fault():
    assert step3.apply_encoder_fault(400, 402, "wat", 0) == (400, 402)


def test_the_stale_values_fail_both_f_program_checks():
    # 0/0 would read as "stopped and healthy" - the dangerous lie. These
    # must fail the 50 mm/s cross-check AND the 2800 mm/s ceiling.
    assert abs(step3.ENC_STALE_A - step3.ENC_STALE_B) > 50
    assert max(step3.ENC_STALE_A, step3.ENC_STALE_B) > 2800


def test_parse_sensor_requires_integer_encoder_fields():
    good = b'{"pf": true, "wf": true, "enc_a": 10, "enc_b": 12, "ts": 1.0}'
    assert step3.parse_sensor(good)["enc_a"] == 10
    for bad in (b'{"pf": true, "wf": true, "enc_a": "10", "enc_b": 12, "ts": 1.0}',
                b'{"pf": true, "wf": true, "enc_a": true, "enc_b": 12, "ts": 1.0}',
                b'{"pf": true, "wf": true, "enc_b": 12, "ts": 1.0}'):
        assert step3.parse_sensor(bad) is None
