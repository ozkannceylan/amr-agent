"""encoder_link.py's pure decisions. No ROS graph, no Gazebo."""
import encoder_link

R = 0.12          # config.yaml model.wheel_radius_m


def test_omega_to_mm_s_is_tread_speed():
    # 1 rad/s on a 0.12 m wheel is 0.12 m/s is 120 mm/s.
    assert encoder_link.omega_to_mm_s(1.0, R) == 120
    assert encoder_link.omega_to_mm_s(0.0, R) == 0


def test_reverse_is_a_negative_reading():
    # The F-program's cross-check works on the difference either way, so
    # the sign has to survive rather than be taken as a magnitude.
    assert encoder_link.omega_to_mm_s(-1.0, R) == -120


def test_the_result_is_an_int_because_the_plc_tags_are_int():
    v = encoder_link.omega_to_mm_s(3.3333, R)
    assert isinstance(v, int) and v == 400


def test_matching_channels_are_healthy():
    assert encoder_link.healthy(400, 402) is True
    assert encoder_link.healthy(-400, -398) is True


def test_the_limit_is_the_f_programs_50_mm_s():
    assert encoder_link.healthy(0, 50) is True
    assert encoder_link.healthy(0, 51) is False


def test_a_missing_channel_is_a_fault_not_a_match():
    # No reading is not a matching pair.
    assert encoder_link.healthy(None, 400) is False
    assert encoder_link.healthy(400, None) is False
    assert encoder_link.healthy(None, None) is False
