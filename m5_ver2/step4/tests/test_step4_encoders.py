"""step4.py's encoder fault injection."""
import step4


def test_ok_passes_both_channels_through():
    assert step4.apply_encoder_fault(400, 402, "ok", 0) == (400, 402)


def test_fa_freezes_channel_a_at_its_last_value():
    # Trips the cross-check as soon as the vehicle moves away from the
    # frozen value, and not before - which is the point of the mode.
    assert step4.apply_encoder_fault(400, 402, "fa", 0) == (0, 402)
    assert step4.apply_encoder_fault(900, 902, "fa", 400) == (400, 902)


def test_oa_offsets_channel_a_past_the_cross_check():
    a, b = step4.apply_encoder_fault(100, 102, "oa", 0)
    assert a == 100 + step4.ENC_OFFSET_MM_S
    assert abs(a - b) > 50      # the F-program's limit


def test_an_unknown_mode_passes_through_rather_than_inventing_a_fault():
    assert step4.apply_encoder_fault(400, 402, "wat", 0) == (400, 402)


def test_the_stale_values_fail_both_f_program_checks():
    # 0/0 would read as "stopped and healthy" - the dangerous lie. These
    # must fail the 50 mm/s cross-check AND the 2800 mm/s ceiling.
    assert abs(step4.ENC_STALE_A - step4.ENC_STALE_B) > 50
    assert max(step4.ENC_STALE_A, step4.ENC_STALE_B) > 2800


def test_parse_sensor_requires_integer_encoder_fields():
    import json

    def packet(**enc):
        msg = {key: True for key, _tag in step4.SENSOR_TAGS}
        msg.update({"enc_a": 10, "enc_b": 12, "ts": 1.0})
        msg.update(enc)
        return json.dumps(msg).encode()

    assert step4.parse_sensor(packet())["enc_a"] == 10
    assert step4.parse_sensor(packet(enc_a="10")) is None
    assert step4.parse_sensor(packet(enc_a=True)) is None
    bad = json.loads(packet().decode())
    del bad["enc_a"]
    assert step4.parse_sensor(json.dumps(bad).encode()) is None
