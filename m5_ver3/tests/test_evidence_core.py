#!/usr/bin/env python3
"""test_evidence_core.py - the arithmetic behind every figure in
EVIDENCE_SENSORS.md, checked without a simulator.

    python -m pytest m5_ver3/tests/ -q

WHY THESE TESTS EXIST AND NOT ONLY THE RIG RUNS. Every number in the
evidence file is produced by tools/evidence_core.py from a CSV, and a
sign error in the frame transform or an anchored drift score would
produce numbers that look entirely plausible - a drift of 0.3 m instead
of 0.6 m is not a value anybody can spot by reading it. The rig proves
the plant; these prove the ruler.

THE ONE THAT MATTERS MOST IS THE FRAME TRANSFORM. The ground truth on
this track is in WORLD coordinates and the estimate is in an odom frame
that starts at the spawn pose (nodes/wheel_odom_core.py reset()'s
docstring carries the measurement). Scoring one against the other needs
the spawn pose subtracted AND the spawn yaw rotated out, and the spawn
yaw here is pi - the one value where a sign error changes nothing about
the magnitudes and everything about the direction. So the pi case is
tested explicitly, beside a quarter turn where the sign is visible.

NO ROS AND NO GAZEBO IS REACHED FROM THIS FILE, which is what lets the
owner run it on the Windows python. conftest.py puts tools/ on the path.
"""
import math
import os

import pytest

import evidence_core


# ----------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------

def test_the_stddev_is_the_sample_one_and_not_the_population_one():
    # [1..5]: mean 3, sum of squares 10. n-1 gives 2.5, n gives 2.0, and
    # the difference is 12 % on a five-sample noise figure.
    got = evidence_core.stddev([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(got - math.sqrt(2.5)) < 1e-12


def test_one_reading_has_no_spread_and_says_so():
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.stddev([5.0])
    assert "two" in str(exc.value)


def test_the_summary_carries_the_median_and_not_only_the_mean():
    s = evidence_core.summarise([1.0, 2.0, 3.0, 4.0, 100.0])
    assert s.n == 5
    assert s.median == 3.0
    assert s.minimum == 1.0 and s.maximum == 100.0


def test_the_white_noise_is_scored_after_the_run_mean_comes_off():
    # A per-run bias is a constant offset: it moves the mean and leaves
    # the spread alone. The evidence file scores the SPREAD against the
    # configured white sigma and reports the mean separately as the bias
    # - this is the arithmetic that keeps the two apart.
    noise = [-2.0, -1.0, 0.0, 1.0, 2.0]
    biased = [7.5 + v for v in noise]
    centred = evidence_core.remove_mean(biased)
    assert abs(evidence_core.mean(biased) - 7.5) < 1e-12
    assert abs(evidence_core.stddev(centred)
               - evidence_core.stddev(noise)) < 1e-12
    assert abs(evidence_core.mean(centred)) < 1e-12


# ----------------------------------------------------------------------
# angles
# ----------------------------------------------------------------------

def test_an_angle_folds_into_the_half_open_turn():
    assert abs(evidence_core.normalise_angle(3 * math.pi) - math.pi) < 1e-12
    assert abs(evidence_core.normalise_angle(-math.pi / 2)
               + math.pi / 2) < 1e-12


def test_unwrapping_removes_the_step_a_wrap_puts_in():
    # A heading that crosses pi wraps to -pi, and a consumer differencing
    # it sees a 2 pi jump that the vehicle did not perform.
    wrapped = [3.10, 3.14, -3.14, -3.10]
    out = evidence_core.unwrap(wrapped)
    assert out[0] == 3.10
    for a, b in zip(out, out[1:]):
        assert abs(b - a) < 0.5
    assert out[-1] > 3.14


# ----------------------------------------------------------------------
# the spawn frame - the transform every drift figure passes through
# ----------------------------------------------------------------------

def test_the_spawn_frame_of_the_spawn_pose_is_the_origin():
    frame = evidence_core.SpawnFrame(-17.0, 10.0, math.pi)
    x, y, yaw = frame.apply(-17.0, 10.0, math.pi)
    assert abs(x) < 1e-12 and abs(y) < 1e-12 and abs(yaw) < 1e-12


def test_at_spawn_yaw_pi_world_plus_x_is_spawn_frame_minus_x():
    # THE CLASSIC FAILURE. The truck spawns facing world +x with model
    # yaw pi, so 11.6 m of travel down the leg is +11.6 m of WORLD x and
    # -11.6 m in the frame the estimator reports in. A missing rotation
    # gives the right magnitude with the wrong sign and every drift
    # figure then reads as 23 m of error.
    frame = evidence_core.SpawnFrame(-17.0, 10.0, math.pi)
    x, y, _ = frame.apply(-5.3968, 10.0, math.pi)
    assert abs(x - (-11.6032)) < 1e-9
    assert abs(y) < 1e-9


def test_a_quarter_turn_of_spawn_yaw_puts_world_x_on_spawn_minus_y():
    # pi hides a sign because -1 is its own inverse here; pi/2 does not.
    frame = evidence_core.SpawnFrame(0.0, 0.0, math.pi / 2)
    x, y, _ = frame.apply(1.0, 0.0, 0.0)
    assert abs(x) < 1e-12
    assert abs(y - (-1.0)) < 1e-12


def test_the_spawn_yaw_is_subtracted_from_the_heading_and_not_added():
    frame = evidence_core.SpawnFrame(-17.0, 10.0, math.pi)
    _, _, yaw = frame.apply(-17.0, 10.0, math.pi + 0.1)
    assert abs(yaw - 0.1) < 1e-12


def test_the_spawn_frame_round_trips():
    frame = evidence_core.SpawnFrame(-17.0, 10.0, math.pi)
    x, y, yaw = frame.apply(-3.25, 12.5, 2.0)
    bx, by, byaw = frame.unapply(x, y, yaw)
    assert abs(bx - (-3.25)) < 1e-9
    assert abs(by - 12.5) < 1e-9
    assert abs(evidence_core.normalise_angle(byaw - 2.0)) < 1e-9


# ----------------------------------------------------------------------
# delivered rate, from timestamps
# ----------------------------------------------------------------------

def test_the_rate_of_a_clean_fifteen_hertz_stream_is_fifteen():
    stamps = [i / 15.0 for i in range(151)]
    rate = evidence_core.rate_from_stamps(stamps)
    assert rate.n == 151
    assert abs(rate.hz_mean - 15.0) < 1e-9
    assert abs(rate.hz_median - 15.0) < 1e-9


def test_a_dropped_frame_shows_in_the_worst_interval_and_not_in_the_median():
    stamps = [i / 15.0 for i in range(60)]
    stamps = stamps[:30] + [t + 3 / 15.0 for t in stamps[30:]]
    rate = evidence_core.rate_from_stamps(stamps)
    assert abs(rate.dt_median - 1 / 15.0) < 1e-9
    assert rate.dt_max > 3.9 / 15.0


def test_a_rate_needs_two_stamps():
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.rate_from_stamps([0.0])


# ----------------------------------------------------------------------
# resampling - the ground truth is 20 Hz and the estimate is 500 Hz
# ----------------------------------------------------------------------

def test_resampling_interpolates_between_the_two_bracketing_samples():
    got = evidence_core.resample([0.0, 1.0], [10.0, 20.0], [0.25], 1.0)
    assert abs(got[0] - 12.5) < 1e-12


def test_resampling_refuses_to_extrapolate_past_the_bound():
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.resample([0.0, 1.0], [10.0, 20.0], [5.0], 0.5)
    assert "5" in str(exc.value)


# ----------------------------------------------------------------------
# drift - absolute, never anchored
# ----------------------------------------------------------------------

def _still(t):
    """A truck that never moves: the ground truth sits at the spawn."""
    return [(v, -17.0, 10.0, math.pi) for v in t]


# score_drift's gap bound carries NO DEFAULT - it is the number that
# decides which recordings are scoreable at all, so evidence_core refuses
# to own one and every caller spells it. 1.0 s is deliberately generous
# against traces sampled every 0.05 s below: what these tests exercise is
# the SCORE, and the bound itself is tested against resample() above.
_GAP_S = 1.0


def test_a_perfect_estimate_of_a_stationary_truck_drifts_nothing():
    t = [i * 0.05 for i in range(21)]
    score = evidence_core.score_drift(
        _still(t), [(v, 0.0, 0.0, 0.0) for v in t],
        evidence_core.SpawnFrame(-17.0, 10.0, math.pi), _GAP_S)
    assert score.end_error_m < 1e-9
    assert score.rms_m < 1e-9


def test_the_score_is_absolute_and_is_not_anchored_to_the_first_sample():
    # An estimate that is 0.40 m out from its FIRST sample and stays
    # there has drifted 0.40 m, and a scorer that subtracted its own
    # starting error would report zero. Global constraint 5: scores are
    # ABSOLUTE, never per-run anchored.
    t = [i * 0.05 for i in range(21)]
    score = evidence_core.score_drift(
        _still(t), [(v, 0.40, 0.0, 0.0) for v in t],
        evidence_core.SpawnFrame(-17.0, 10.0, math.pi), _GAP_S)
    assert abs(score.end_error_m - 0.40) < 1e-9
    assert abs(score.rms_m - 0.40) < 1e-9
    assert abs(score.max_error_m - 0.40) < 1e-9


def test_the_end_error_is_the_estimate_minus_the_truth_in_the_spawn_frame():
    truth = [(0.0, -17.0, 10.0, math.pi), (1.0, -16.0, 10.0, math.pi)]
    # world +1 m of x is -1 m in the spawn frame; the estimate says -1.10
    est = [(0.0, 0.0, 0.0, 0.0), (1.0, -1.10, 0.0, 0.0)]
    score = evidence_core.score_drift(
        truth, est, evidence_core.SpawnFrame(-17.0, 10.0, math.pi),
        _GAP_S)
    assert abs(score.end_dx - (-0.10)) < 1e-9
    assert abs(score.end_error_m - 0.10) < 1e-9


def test_the_heading_error_folds_and_does_not_read_two_pi():
    truth = [(0.0, -17.0, 10.0, math.pi), (1.0, -17.0, 10.0, math.pi)]
    est = [(0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 2 * math.pi - 0.05)]
    score = evidence_core.score_drift(
        truth, est, evidence_core.SpawnFrame(-17.0, 10.0, math.pi),
        _GAP_S)
    assert abs(score.end_yaw_error_rad - (-0.05)) < 1e-9


def test_the_path_length_is_the_sum_of_the_steps_and_not_the_displacement():
    # Out and back: 2 m of path, 0 m of displacement. The aisle profile
    # is exactly this shape and a scorer that reported displacement would
    # call a 40 m round trip a 0 m run.
    truth = [(0.0, -17.0, 10.0, math.pi), (1.0, -16.0, 10.0, math.pi),
             (2.0, -17.0, 10.0, math.pi)]
    est = [(0.0, 0.0, 0.0, 0.0), (1.0, -1.0, 0.0, 0.0), (2.0, 0.0, 0.0, 0.0)]
    score = evidence_core.score_drift(
        truth, est, evidence_core.SpawnFrame(-17.0, 10.0, math.pi),
        _GAP_S)
    assert abs(score.truth_path_m - 2.0) < 1e-9
    assert abs(score.est_path_m - 2.0) < 1e-9


# ----------------------------------------------------------------------
# the steady-state window a corner is measured over
# ----------------------------------------------------------------------

def _corner_trace(n=400, dt=0.05, slew_s=2.0, target=-0.785398, speed=0.3):
    """A steer axis slewing into a corner and then holding it."""
    t, steer, spd = [], [], []
    for i in range(n):
        now = i * dt
        t.append(now)
        steer.append(target * min(1.0, now / slew_s))
        spd.append(speed if now > 0.5 else 0.0)
    return t, steer, spd


def test_the_steady_window_starts_after_the_settle_and_not_at_the_command():
    t, steer, speed = _corner_trace()
    w = evidence_core.steady_window(t, steer, speed, -0.785398,
                                    steer_tol_rad=0.01, speed_min_mps=0.05,
                                    settle_s=1.0, min_window_s=2.0)
    # The axis reaches the target at t = 2.0; the settle discards the
    # first second of the hold, so the window may not open before 3.0.
    assert w.t0 >= 3.0 - 1e-9
    assert w.t1 <= t[-1] + 1e-9
    assert w.t1 - w.t0 >= 2.0


def test_a_corner_the_axis_never_reached_is_a_refusal_naming_the_target():
    t, steer, speed = _corner_trace(target=-0.2)
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.steady_window(t, steer, speed, -0.785398,
                                    steer_tol_rad=0.01, speed_min_mps=0.05,
                                    settle_s=1.0, min_window_s=2.0)
    assert "0.785" in str(exc.value)


def test_a_touch_of_the_target_too_short_to_measure_is_not_a_window():
    t = [i * 0.05 for i in range(100)]
    steer = [-0.785398 if 10 <= i <= 20 else 0.0 for i in range(100)]
    speed = [0.3] * 100
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.steady_window(t, steer, speed, -0.785398,
                                    steer_tol_rad=0.01, speed_min_mps=0.05,
                                    settle_s=0.2, min_window_s=5.0)


def test_the_vehicle_must_be_moving_for_the_window_to_open():
    t = [i * 0.05 for i in range(200)]
    steer = [-0.785398] * 200
    speed = [0.0] * 200
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.steady_window(t, steer, speed, -0.785398,
                                    steer_tol_rad=0.01, speed_min_mps=0.05,
                                    settle_s=0.2, min_window_s=2.0)


# ----------------------------------------------------------------------
# corner fidelity - does the tricycle model hold at creep speed
# ----------------------------------------------------------------------

def test_an_ideal_tricycle_delivers_the_yaw_its_geometry_promises():
    fid = evidence_core.corner_fidelity(
        yaw_rate=0.3 * math.sin(0.785398) / 1.05,
        steer_rad=0.785398, wheelbase_m=1.05,
        commanded_tread_mps=0.3, measured_rear_mps=0.3 * math.cos(0.785398))
    assert abs(fid.ratio_commanded - 1.0) < 1e-12
    assert abs(fid.ratio_measured - 1.0) < 1e-12


def test_the_two_spellings_of_the_kinematic_yaw_rate_are_one_formula():
    # v_tread * sin(delta) / L  ==  v_rear * tan(delta) / L, because the
    # rear axle runs at v_rear = v_tread * cos(delta). config.yaml's
    # square: table is written in the first spelling and Task 4's brief
    # in the second; they are the same claim and this locks that down.
    delta = 0.6
    fid = evidence_core.corner_fidelity(
        yaw_rate=1.0, steer_rad=delta, wheelbase_m=1.05,
        commanded_tread_mps=0.3,
        measured_rear_mps=0.3 * math.cos(delta))
    assert abs(fid.kinematic_commanded - fid.kinematic_measured) < 1e-12


def test_a_vehicle_that_scrubs_delivers_a_fraction_and_it_is_reported():
    kin = 0.3 * math.sin(0.785398) / 1.05
    fid = evidence_core.corner_fidelity(
        yaw_rate=0.401 * kin, steer_rad=0.785398, wheelbase_m=1.05,
        commanded_tread_mps=0.3, measured_rear_mps=0.3 * math.cos(0.785398))
    assert abs(fid.ratio_commanded - 0.401) < 1e-9
    # The effective radius is DEFINED as the measured rear-axle ground
    # speed over the measured yaw rate - one measurement over another,
    # with no kinematics in it. 0.2121 / 0.08101 = 2.6185 m against the
    # 1.05 m the geometry promises.
    assert abs(fid.effective_radius_m - 2.6185) < 1e-3
    assert abs(fid.kinematic_radius_m - 1.05) < 1e-6


def test_the_sign_of_the_steer_does_not_change_the_fidelity():
    kin = 0.3 * math.sin(0.785398) / 1.05
    left = evidence_core.corner_fidelity(
        yaw_rate=-0.5 * kin, steer_rad=-0.785398, wheelbase_m=1.05,
        commanded_tread_mps=0.3, measured_rear_mps=0.3 * math.cos(0.785398))
    right = evidence_core.corner_fidelity(
        yaw_rate=0.5 * kin, steer_rad=0.785398, wheelbase_m=1.05,
        commanded_tread_mps=0.3, measured_rear_mps=0.3 * math.cos(0.785398))
    assert abs(left.ratio_commanded - right.ratio_commanded) < 1e-12


# ----------------------------------------------------------------------
# the CSV the recorder writes and the analyser reads
# ----------------------------------------------------------------------

def test_the_reader_reads_a_headered_csv(tmp_path):
    path = os.path.join(str(tmp_path), "imu.csv")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("t_sim,t_wall,gx\n0.0,100.0,0.5\n0.01,100.01,-0.5\n")
    table = evidence_core.read_csv(path)
    assert table.n == 2
    assert table.column("gx") == [0.5, -0.5]


def test_a_missing_column_is_refused_by_name(tmp_path):
    path = os.path.join(str(tmp_path), "imu.csv")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("t_sim,gx\n0.0,0.5\n0.01,-0.5\n")
    table = evidence_core.read_csv(path)
    with pytest.raises(evidence_core.EvidenceError) as exc:
        table.column("gy")
    assert "gy" in str(exc.value)
    assert "imu.csv" in str(exc.value)


def test_an_empty_csv_is_refused_rather_than_averaged(tmp_path):
    path = os.path.join(str(tmp_path), "scan_nav.csv")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("t_sim,t_wall,beam_0\n")
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.read_csv(path)


def test_a_beam_that_is_not_finite_in_every_frame_is_left_out(tmp_path):
    # A beam that is out of range in one frame and not the next is the
    # ROOM, not the noise, and averaging it would invent a reading.
    path = os.path.join(str(tmp_path), "scan_nav.csv")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("t_sim,t_wall,beam_0,beam_1\n")
        handle.write("0.0,0.0,3.6,inf\n")
        handle.write("0.1,0.1,3.61,4.0\n")
        handle.write("0.2,0.2,3.59,4.0\n")
    table = evidence_core.read_csv(path)
    series = evidence_core.finite_beam_series(table, "beam_")
    assert list(series) == ["beam_0"]


# ----------------------------------------------------------------------
# the SDF, which is the authority on every configured figure
# ----------------------------------------------------------------------

_SDF = """<?xml version="1.0"?>
<sdf version="1.8">
  <model name="truck">
    <link name="a">
      <sensor name="nav_lidar" type="gpu_lidar">
        <update_rate>15</update_rate>
        <topic>/scan</topic>
        <lidar>
          <scan><horizontal><samples>811</samples></horizontal></scan>
          <range><min>0.05</min><max>25.0</max></range>
          <noise>
            <type>gaussian</type>
            <mean>0.0</mean>
            <stddev>0.02</stddev>
            <bias_mean>0.0</bias_mean>
            <bias_stddev>0.02</bias_stddev>
          </noise>
        </lidar>
      </sensor>
      <sensor name="imu" type="imu">
        <update_rate>100</update_rate>
        <topic>/imu</topic>
        <imu>
          <angular_velocity>
            <x>
              <noise type="gaussian">
                <mean>0.0</mean>
                <stddev>0.001745</stddev>
                <bias_mean>0.002618</bias_mean>
                <bias_stddev>0.0</bias_stddev>
              </noise>
            </x>
          </angular_velocity>
        </imu>
      </sensor>
    </link>
  </model>
</sdf>
"""


def _sdf_file(tmp_path):
    path = os.path.join(str(tmp_path), "model.sdf")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(_SDF)
    return path


def test_the_configured_noise_is_read_from_the_model_and_not_from_config(
        tmp_path):
    spec = evidence_core.sdf_sensors(_sdf_file(tmp_path))["nav_lidar"]
    assert abs(spec["noise"]["range"]["stddev"] - 0.02) < 1e-12
    assert abs(spec["noise"]["range"]["bias_stddev"] - 0.02) < 1e-12
    assert abs(spec["update_rate"] - 15.0) < 1e-12
    assert spec["topic"] == "/scan"


def test_the_noise_type_is_carried_because_one_of_them_disables_the_noise():
    # gaussian_quantized produces NO noise at all on a gpu_lidar
    # (EVIDENCE_MODEL_V3.md 9.2, measured both ways). A configured column
    # that printed only the stddev would say 0.02 about a silent channel.
    assert "type" in evidence_core.NOISE_FIELDS


def test_the_imu_noise_is_read_per_axis(tmp_path):
    spec = evidence_core.sdf_sensors(_sdf_file(tmp_path))["imu"]
    axis = spec["noise"]["angular_velocity_x"]
    assert abs(axis["stddev"] - 0.001745) < 1e-12
    assert abs(axis["bias_mean"] - 0.002618) < 1e-12
    assert axis["bias_stddev"] == 0.0
    assert axis["type"] == "gaussian"


def test_a_sensor_the_model_does_not_carry_is_refused_by_name(tmp_path):
    sensors = evidence_core.sdf_sensors(_sdf_file(tmp_path))
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.sdf_sensor(sensors, "nav_lidar_3d")
    assert "nav_lidar_3d" in str(exc.value)
    assert "nav_lidar" in str(exc.value)


def test_a_beam_pinned_to_the_range_minimum_is_kept_apart_from_the_rest():
    # gz clamps a return closer than <range><min> to the minimum instead
    # of dropping it, and the back safety scanner sees this truck's own
    # counterweight. A clamped beam is not measuring the room, so its
    # spread is not a noise figure and must not be averaged into one.
    series = {"beam_0": [0.1, 0.1, 0.1], "beam_1": [3.5, 3.52, 3.48]}
    free, clamped = evidence_core.split_clamped(series, 0.1, 1e-6)
    assert list(free) == ["beam_1"]
    assert list(clamped) == ["beam_0"]


def test_the_worlds_gravity_is_read_and_not_assumed(tmp_path):
    # The accelerometer at rest reads gravity plus its bias, so the bias
    # is only checkable against the model if the gravity under it is the
    # world's own. warehouse_ver3 declares 9.8; the vehicle's own mass
    # derivation uses 9.80665. The difference is a third of the bias.
    path = os.path.join(str(tmp_path), "world.sdf")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('<sdf version="1.8"><world name="w">'
                     '<gravity>0 0 -9.8</gravity></world></sdf>')
    assert abs(evidence_core.sdf_gravity(path) - 9.8) < 1e-12


def test_a_world_with_no_gravity_element_is_refused_rather_than_guessed(
        tmp_path):
    path = os.path.join(str(tmp_path), "world.sdf")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('<sdf version="1.8"><world name="w"/></sdf>')
    with pytest.raises(evidence_core.EvidenceError) as exc:
        evidence_core.sdf_gravity(path)
    assert "default" in str(exc.value)


def test_the_gravity_is_read_from_a_world_a_strict_parser_will_not_open(
        tmp_path):
    # m6/gazebo/warehouse_ver3.sdf draws its floor plan in a header
    # comment with rules made of hyphens, and `--` inside an XML comment
    # is illegal: ElementTree refuses the file, gz accepts it, and m6/ is
    # not this track's to correct.
    path = os.path.join(str(tmp_path), "world.sdf")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('<sdf version="1.8"><!-- ----- a rule ----- -->'
                     '<world name="w"><gravity>0 0 -9.8</gravity>'
                     '</world></sdf>')
    assert abs(evidence_core.sdf_gravity(path) - 9.8) < 1e-12


def test_a_gravity_drawn_inside_a_comment_is_not_the_worlds(tmp_path):
    path = os.path.join(str(tmp_path), "world.sdf")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('<sdf version="1.8"><world name="w">'
                     '<!-- <gravity>0 0 -1.62</gravity> the moon -->'
                     '<gravity>0 0 -9.8</gravity></world></sdf>')
    assert abs(evidence_core.sdf_gravity(path) - 9.8) < 1e-12


def test_the_rear_axle_is_behind_base_link_along_the_model_x_axis():
    # config.yaml records the axle at x = -0.50 IN base_link, so at yaw 0
    # the axle stands 0.50 m in the -x direction of the world.
    xs, ys = evidence_core.rear_axle_track([0.0], [0.0], [0.0], -0.50)
    assert abs(xs[0] + 0.50) < 1e-12 and abs(ys[0]) < 1e-12


def test_the_rear_axle_swings_with_the_heading():
    xs, ys = evidence_core.rear_axle_track([0.0], [0.0], [math.pi / 2], -0.50)
    assert abs(xs[0]) < 1e-12
    assert abs(ys[0] + 0.50) < 1e-12


def test_in_a_turn_base_link_moves_faster_than_the_axle_it_pivots_on():
    # base_link carries a lateral term d*yawrate that the rear axle does
    # not, so a turning radius computed from base_link's speed is too
    # large. Half a turn of a 2 m circle, sampled: the axle path is
    # shorter than base_link's.
    n = 200
    yaws = [math.pi * i / n for i in range(n + 1)]
    # THE AXLE is what traces the circle - it is the point whose velocity
    # is purely longitudinal - and base_link rides 0.50 m ahead of it
    # along the heading, on a circle of radius sqrt(R^2 + d^2).
    axle_x = [2.0 * math.sin(a) for a in yaws]
    axle_y = [2.0 * (1.0 - math.cos(a)) for a in yaws]
    xs = [x + 0.50 * math.cos(a) for x, a in zip(axle_x, yaws)]
    ys = [y + 0.50 * math.sin(a) for y, a in zip(axle_y, yaws)]
    ax, ay = evidence_core.rear_axle_track(xs, ys, yaws, -0.50)
    assert abs(ax[-1] - axle_x[-1]) < 1e-9 and abs(ay[-1] - axle_y[-1]) < 1e-9
    assert (evidence_core.path_length(ax, ay)
            < evidence_core.path_length(xs, ys) - 0.1)


# ----------------------------------------------------------------------
# every held corner of a run, not only the longest one
# ----------------------------------------------------------------------

def _four_corner_trace(hold_s=9.14, straight_s=3.33, slew_s=1.0, dt=0.05,
                       target=-1.25, speed=0.3):
    """A square: four corners, each slewed into and held, with straights
    between them. The shape config.yaml's square: profile drives."""
    t, steer, spd = [], [], []
    now = 0.0

    def push(seconds, value):
        nonlocal now
        for _ in range(int(round(seconds / dt))):
            t.append(now)
            steer.append(value)
            spd.append(speed)
            now += dt

    push(2.0, 0.0)
    for _ in range(4):
        push(straight_s, 0.0)
        # the axis slews in over slew_s, then holds
        steps = int(round(slew_s / dt))
        for i in range(steps):
            t.append(now)
            steer.append(target * (i + 1) / steps)
            spd.append(speed)
            now += dt
        push(hold_s - slew_s, target)
    push(2.0, 0.0)
    return t, steer, spd


def test_every_held_corner_is_found_and_not_only_the_longest():
    # The square turns four corners at ONE steer angle, and the delivered
    # yaw differs between them - so a reduction that returns only the
    # longest run cannot produce the per-corner table at all.
    t, steer, speed = _four_corner_trace()
    runs = evidence_core.steady_runs(
        t, steer, speed, -1.25, steer_tol_rad=0.02, speed_min_mps=0.05,
        trim_start_s=1.0, trim_end_s=0.3, min_window_s=6.0)
    assert runs.found == 4
    assert len(runs.windows) == 4


def test_each_corner_is_trimmed_at_both_ends():
    # The axis slews INTO a corner and back OUT of it, and neither is a
    # steady state. corner_creep discards a settle at the start only,
    # because it has one long corner and no exit inside the window; a
    # square's corners are short enough that the exit is inside.
    t, steer, speed = _four_corner_trace()
    runs = evidence_core.steady_runs(
        t, steer, speed, -1.25, steer_tol_rad=0.02, speed_min_mps=0.05,
        trim_start_s=1.0, trim_end_s=0.3, min_window_s=6.0)
    first = runs.windows[0]
    # the hold begins at 2.0 + 3.33 + 1.0 (slew) and runs hold_s - slew_s
    held_start = 2.0 + 3.33 + 1.0
    held_end = 2.0 + 3.33 + 9.14
    assert first.t0 >= held_start + 1.0 - 1e-9
    assert first.t1 <= held_end - 0.3 + 1e-9
    assert first.t1 - first.t0 >= 6.0


def test_a_corner_too_short_after_trimming_is_dropped_and_the_count_says_so():
    t, steer, speed = _four_corner_trace()
    runs = evidence_core.steady_runs(
        t, steer, speed, -1.25, steer_tol_rad=0.02, speed_min_mps=0.05,
        trim_start_s=1.0, trim_end_s=0.3, min_window_s=30.0)
    assert runs.found == 4
    assert runs.windows == []


def test_the_single_window_reduction_is_one_of_the_runs():
    # steady_window() and steady_runs() must not be two opinions about
    # what "held" means: the first is the longest of the second, under
    # the same criterion.
    t, steer, speed = _corner_trace()
    one = evidence_core.steady_window(
        t, steer, speed, -0.785398, steer_tol_rad=0.01, speed_min_mps=0.05,
        settle_s=1.0, min_window_s=2.0)
    runs = evidence_core.steady_runs(
        t, steer, speed, -0.785398, steer_tol_rad=0.01, speed_min_mps=0.05,
        trim_start_s=1.0, trim_end_s=0.0, min_window_s=2.0)
    assert runs.found == 1
    assert runs.windows[0] == one


# ----------------------------------------------------------------------
# where a corner's missing yaw actually went
# ----------------------------------------------------------------------

def _arc(u_mps, steer_rad, wheelbase_m=1.05, seconds=6.0, dt=0.05,
         side_slip_mps=0.0, extra_yaw_rate=0.0):
    """A rear axle driven at a constant body velocity and a constant yaw
    rate, integrated in CLOSED FORM so the trace carries no integrator
    error of its own.

    THE TRACK IS ALL THE REDUCTION GETS. scrub_split() sees positions and
    headings and has to recover the two slip velocities from them, which
    is exactly its job on a real CSV - so the generator writes the motion
    and never the answer.

    With no side slip and no extra yaw rate the motion is the tricycle's
    own: yaw rate u*tan(delta)/L, both slip terms zero.
    """
    omega = u_mps * math.tan(steer_rad) / wheelbase_m + extra_yaw_rate
    t, xs, ys, yaws, steer = [], [], [], [], []
    n = int(round(seconds / dt))
    for i in range(n + 1):
        now = i * dt
        yaw = omega * now
        if omega:
            x = (u_mps / omega) * math.sin(yaw) + (
                side_slip_mps / omega) * (math.cos(yaw) - 1.0)
            y = (u_mps / omega) * (1.0 - math.cos(yaw)) + (
                side_slip_mps / omega) * math.sin(yaw)
        else:
            x, y = u_mps * now, side_slip_mps * now
        t.append(now)
        xs.append(x)
        ys.append(y)
        yaws.append(yaw)
        steer.append(steer_rad)
    return t, xs, ys, yaws, steer


def test_a_corner_that_obeys_the_kinematics_charges_nothing_to_either_wheel():
    # An arc whose radius IS L/tan(delta), driven with no lateral slip at
    # the axle: both slip terms must come out at zero and the delivered
    # yaw must equal the kinematic one.
    delta = -0.785398
    t, xs, ys, yaws, steer = _arc(0.2114, delta)
    split = evidence_core.scrub_split(t, xs, ys, yaws, steer,
                                      wheelbase_m=1.05, tread_mps=0.3)
    assert abs(split.rear_lat_mps) < 1e-6
    assert abs(split.front_lat_mps) < 1e-6
    assert abs(split.deficit / split.kinematic) < 1e-5


def test_a_rear_axle_that_slides_is_charged_to_the_rear_and_not_the_front():
    # THE SAME ARC, with the axle crabbing sideways. The rear term has to
    # pick that up: a plant whose rear axle slides is a different repair
    # from one whose steered wheel does, and a split that could not tell
    # them apart would send the tuning to the wrong wheel.
    delta = -0.785398
    t, xs, ys, yaws, steer = _arc(0.2114, delta, side_slip_mps=0.03)
    split = evidence_core.scrub_split(t, xs, ys, yaws, steer,
                                      wheelbase_m=1.05, tread_mps=0.3)
    assert abs(split.rear_lat_mps - 0.03) < 1e-6
    assert abs(split.rear_term + 0.03 / 1.05) < 1e-6


def test_the_yaw_budget_is_an_identity_and_closes_on_any_trace():
    # kinematic + front + rear - delivered is algebra, not a fit, so it
    # closes on a trace that obeys no model at all. This is the check the
    # printed block quotes as `residual`.
    delta = -0.9
    t, xs, ys, yaws, steer = _arc(0.25, delta, side_slip_mps=-0.05,
                                  extra_yaw_rate=0.04)
    split = evidence_core.scrub_split(t, xs, ys, yaws, steer,
                                      wheelbase_m=1.05, tread_mps=0.3)
    assert abs(split.residual) < 1e-12
    assert abs((split.kinematic + split.front_term + split.rear_term)
               - split.yaw_rate) < 1e-12


def test_the_split_reproduces_the_untuned_plants_measured_deficit():
    # THE NUMBERS ARE THE RIG'S, not invented: EVIDENCE_LATERAL_TUNE.md 2.2
    # measures the untuned plant at u = -0.209242 m/s, w = +0.000673 m/s
    # and psidot = +0.083067 rad/s at a held -0.788531 rad. Fed those, the
    # reduction has to return the steered wheel's 99.5 % share.
    delta = -0.788531
    u, w, omega = -0.209242, 0.000673, 0.083067
    dt = 0.05
    t, xs, ys, yaws, steer = [], [], [], [], []
    x = y = yaw = 0.0
    for i in range(200):
        t.append(i * dt)
        xs.append(x)
        ys.append(y)
        yaws.append(yaw)
        steer.append(delta)
        x += (u * math.cos(yaw) - w * math.sin(yaw)) * dt
        y += (u * math.sin(yaw) + w * math.cos(yaw)) * dt
        yaw += omega * dt
    split = evidence_core.scrub_split(t, xs, ys, yaws, steer,
                                      wheelbase_m=1.05, tread_mps=-0.300)
    assert abs(split.front_share - 0.995) < 0.005
    assert abs(split.rear_share - 0.005) < 0.005
    assert abs(split.deficit / split.kinematic - 0.586) < 0.005
    # and the corner's longitudinal slip at the driven contact, which is
    # 0.96 % on a straight and thirty times that here.
    assert abs(split.tread_slip - 0.3006) < 0.002


def test_a_scrub_split_refuses_a_trace_it_cannot_difference():
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.scrub_split([0.0, 0.1], [0.0, 0.1], [0.0, 0.0],
                                  [0.0, 0.0], [0.0, 0.0], 1.05, 0.3)
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.scrub_split([0.0, 0.1, 0.2], [0.0, 0.1, 0.2],
                                  [0.0, 0.0, 0.0], [0.0, 0.0, 0.0],
                                  [0.0, 0.0, 0.0], 1.05, 0.0)


# ----------------------------------------------------------------------
# closure: what the profile's own table was worth
# ----------------------------------------------------------------------

def test_a_closed_loop_closes_and_an_open_one_does_not():
    square = ([0.0, 1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0, 0.0])
    assert evidence_core.closure(*square) < 1e-12
    assert abs(evidence_core.closure([0.0, 3.0], [0.0, 4.0]) - 5.0) < 1e-12


def test_closure_is_not_path_length_and_an_out_and_back_shows_it():
    xs = [0.0, 5.0, 0.1]
    ys = [0.0, 0.0, 0.0]
    assert abs(evidence_core.path_length(xs, ys) - 9.9) < 1e-12
    assert abs(evidence_core.closure(xs, ys) - 0.1) < 1e-12


def test_a_closure_needs_a_start_and_an_end():
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.closure([1.0], [1.0])
    with pytest.raises(evidence_core.EvidenceError):
        evidence_core.closure([1.0, 2.0], [1.0])
