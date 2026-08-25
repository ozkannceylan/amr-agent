#!/usr/bin/env python3
"""evidence_core.py - the arithmetic behind every figure in
EVIDENCE_SENSORS.md, and nothing else.

    python3 m5_ver3/tools/evidence_core.py --selftest

NO ROS, NO GAZEBO AND NO FILESYSTEM OPINIONS IN THIS FILE. It takes lists
of numbers and CSV paths and returns statistics; tools/sensor_evidence.py
is the shell that subscribes the plant, writes those CSVs and prints the
tables. Everything that could be WRONG about a published figure is here,
where tests/test_evidence_core.py can reach it without a simulator -
nodes/wheel_odom_core.py against nodes/wheel_odometry.py is the same split
and for the same reason.

THE ONE THING THIS FILE EXISTS TO GET RIGHT IS THE FRAME. The ground truth
on this track is the model's OdometryPublisher, and it publishes the WORLD
pose: at rest it reads (-17.00000000000007, 10.0) yaw pi, which is the
spawn pose in world coordinates (measured 2026-08-25, Task 3 3.4). The
estimate is in an odom frame that starts at the vehicle, at the origin,
yaw zero. SCORING ONE AGAINST THE OTHER IS THEREFORE NOT A SUBTRACTION:
the spawn pose has to come off the world pose AND the spawn yaw has to be
rotated out of the remainder. SpawnFrame is that transform and it is the
only place on this track where it is spelled.
  WHY IT IS THE CLASSIC FAILURE. This vehicle's spawn yaw is pi, and at pi
  the rotation is its own inverse - so a sign error in the rotation leaves
  every magnitude EXACTLY right and puts the whole trajectory on the wrong
  side of the origin, which reads as a plausible 23 m of drift on an 11 m
  run. The suite tests pi and a quarter turn together for that reason.

EVERY SCORE IS ABSOLUTE. Nothing here subtracts an initial error, a
per-run offset or a first sample from a drift figure. An estimate that is
0.4 m out at its first sample and stays there has drifted 0.4 m, and a
score anchored to its own start would report zero - which is global
constraint 5, and the suite locks it.

THE ONE PLACE A MEAN IS REMOVED IS THE NOISE, AND IT IS LABELLED. gz draws
a per-run bias once per sensor at load and adds it to every reading for
the life of the run (EVIDENCE_MODEL_V3.md 5.3 measures three draws). It is
a constant offset: it moves the MEAN and leaves the SPREAD alone. So a
white-noise figure is the spread about each reading's own mean, the bias
is reported separately as that mean, and the evidence file says which is
which rather than adding them together and calling the total noise.
"""
import argparse
import collections
import csv as _csv
import math
import os
import sys


class EvidenceError(Exception):
    """A measurement that cannot honestly be made.

    RAISED HERE AND REFUSED BY THE CALLER. This file is pure arithmetic
    and has no voice of its own - tools/sensor_evidence.py catches these
    and turns each into _common.refuse(), which names the check and the
    file that owns the answer in the one format logs/ already carries.
    The message is written as the CHECK THAT FAILED for that reason.
    """


#: Everything a set of readings has to say about itself. `sd` is the
#: SAMPLE standard deviation - see stddev() for why that matters here.
Stats = collections.namedtuple("Stats", "n mean sd median minimum maximum")

#: A delivered rate, from timestamps. hz_mean is the honest headline (the
#: whole span over the whole count); the interval statistics beside it are
#: what tell a dropped frame from a slow one.
Rate = collections.namedtuple(
    "Rate", "n span_s hz_mean hz_median dt_mean dt_median dt_min dt_max "
            "n_nonpositive")

#: The stretch of a run a steady-state figure was taken over.
Window = collections.namedtuple("Window", "t0 t1 i0 i1 n")

#: Every held corner of a run: the windows that survived the trimming,
#: and how many were FOUND before it. The second number is not
#: decoration - a corner that was driven and then dropped for being too
#: short is a fact about the run, and it may not go missing in the gap
#: between "four corners" and "three rows".
Runs = collections.namedtuple("Runs", "windows found")

#: What a drive profile did to the estimate. Every length is metres in the
#: SPAWN FRAME and every one of them is absolute.
Drift = collections.namedtuple(
    "Drift", "n t0 t1 end_dx end_dy end_error_m end_yaw_error_rad "
             "rms_m max_error_m truth_path_m est_path_m "
             "truth_turned_rad est_turned_rad")

#: A corner, against the kinematics it was supposed to obey.
Fidelity = collections.namedtuple(
    "Fidelity", "yaw_rate steer_rad kinematic_commanded kinematic_measured "
                "ratio_commanded ratio_measured effective_radius_m "
                "kinematic_radius_m")


# ----------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------

def mean(values):
    values = list(values)
    if not values:
        raise EvidenceError("a mean needs at least one reading, got none")
    return math.fsum(values) / len(values)


def stddev(values):
    """The SAMPLE standard deviation, n-1 in the denominator.

    n-1 AND NOT n, and on this track it is not a formality. The noise
    figures here are compared against a configured sigma to two
    significant figures off samples of 40 to 900 frames; at n = 40 the
    population form is 1.3 % low, which is inside the number being
    checked. The estimator being unbiased is what lets the comparison in
    EVIDENCE_SENSORS.md be read as a comparison.
    """
    values = list(values)
    if len(values) < 2:
        raise EvidenceError(
            "a spread needs at least two readings, got {}".format(
                len(values)))
    m = mean(values)
    return math.sqrt(math.fsum((v - m) ** 2 for v in values)
                     / (len(values) - 1))


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise EvidenceError("a median needs at least one reading, got none")
    if n % 2:
        return ordered[n // 2]
    return 0.5 * (ordered[n // 2 - 1] + ordered[n // 2])


def summarise(values):
    values = list(values)
    return Stats(n=len(values), mean=mean(values),
                 sd=stddev(values) if len(values) > 1 else 0.0,
                 median=median(values),
                 minimum=min(values), maximum=max(values))


def remove_mean(values):
    """The readings about their own mean.

    THIS IS WHAT SEPARATES THE NOISE FROM THE BIAS and it is the only
    mean-removal in this file. gz's bias is drawn once per run and added
    to every reading, so it lives entirely in the mean; what is left is
    the white noise the SDF configures. The caller reports both.
    """
    values = list(values)
    m = mean(values)
    return [v - m for v in values]


def path_length(xs, ys):
    """The distance TRAVELLED, which is not the distance moved.

    The aisle profile drives 20 m out and 20 m back: 40 m of path and
    about 0 m of displacement. A figure that reported displacement would
    call that run a standstill.
    """
    total = 0.0
    for i in range(1, len(xs)):
        total += math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1])
    return total


# ----------------------------------------------------------------------
# angles
# ----------------------------------------------------------------------

def rear_axle_track(xs, ys, yaws, rear_axle_offset_m):
    """A base_link trajectory, moved onto the rear axle.

    THE KINEMATICS IS THE REAR AXLE'S AND THE GROUND TRUTH IS
    base_link's, so one of them has to move before a turning radius means
    anything. The rear axle midpoint is the only point of a tricycle
    whose velocity is purely longitudinal - nodes/wheel_odom_core.py
    integrates there for the same reason - and base_link stands 0.50 m
    forward of it, so in a turn base_link carries a lateral component
    d*yawrate that the rear axle does not.

    IT IS NOT A ROUNDING ERROR AT CREEP SPEED. Measured on corner_creep:
    base_link runs at 0.2150 m/s where the rear axle runs at 0.2114, a
    1.7 % difference on a ratio quoted to three figures.

    rear_axle_offset_m is the axle's x IN base_link, which config.yaml
    records as -0.50 - so the sign is already right and is not flipped
    here.
    """
    out_x, out_y = [], []
    for x, y, yaw in zip(xs, ys, yaws):
        out_x.append(x + rear_axle_offset_m * math.cos(yaw))
        out_y.append(y + rear_axle_offset_m * math.sin(yaw))
    return out_x, out_y


def normalise_angle(rad):
    """Fold an angle into (-pi, pi]."""
    return math.atan2(math.sin(rad), math.cos(rad))


def unwrap(values):
    """Remove the 2 pi steps a wrapped heading puts into a difference.

    A heading that crosses pi comes back as -pi, and anything
    differencing it then sees a full turn the vehicle did not perform.
    The square profile crosses pi twice, so this is not hypothetical.
    """
    out = []
    previous = None
    offset = 0.0
    for value in values:
        value = float(value)
        if previous is not None:
            step = value + offset - previous
            while step > math.pi:
                offset -= 2.0 * math.pi
                step -= 2.0 * math.pi
            while step < -math.pi:
                offset += 2.0 * math.pi
                step += 2.0 * math.pi
        previous = value + offset
        out.append(previous)
    return out


# ----------------------------------------------------------------------
# the spawn frame
# ----------------------------------------------------------------------

class SpawnFrame(object):
    """World coordinates in, the estimator's own frame out.

    THE ESTIMATE'S FRAME IS THE VEHICLE AT SPAWN. nodes/wheel_odom_core.py
    reset()s to the origin with yaw zero, so its odom frame is the body
    frame the truck had at the instant it started - x along the model's
    own +x, which at spawn yaw pi points at world -x.

        p' = R(-yaw0) . (p - p0)
        yaw' = yaw - yaw0

    and NOT p' = R(yaw0).(p - p0), which is the same arithmetic with the
    rotation applied the wrong way round and, at yaw0 = pi, gives an
    answer of exactly the right size pointing exactly backwards.
    """

    def __init__(self, x0, y0, yaw0):
        self.x0 = float(x0)
        self.y0 = float(y0)
        self.yaw0 = float(yaw0)
        self._c = math.cos(self.yaw0)
        self._s = math.sin(self.yaw0)

    def apply(self, x, y, yaw):
        dx = float(x) - self.x0
        dy = float(y) - self.y0
        return (self._c * dx + self._s * dy,
                -self._s * dx + self._c * dy,
                normalise_angle(float(yaw) - self.yaw0))

    def unapply(self, x, y, yaw):
        """Back to world coordinates. Exists so the transform can be
        round-tripped in a test rather than only read."""
        x = float(x)
        y = float(y)
        return (self.x0 + self._c * x - self._s * y,
                self.y0 + self._s * x + self._c * y,
                normalise_angle(float(yaw) + self.yaw0))


# ----------------------------------------------------------------------
# delivered rate
# ----------------------------------------------------------------------

def rate_from_stamps(stamps):
    """A delivered rate from a stream's own timestamps.

    SCORED ON SIM-TIME STAMPS WHEREVER A RATE IS PUBLISHED. The plant
    stamps every message from its own clock, so a rate computed from
    those stamps is what the SENSOR delivered; a rate computed from
    arrival times is that number multiplied by the day's real-time
    factor. The caller records both and the evidence file says which
    column is which.

    hz_mean is the span over the count and not the mean of the
    reciprocals: one stalled interval biases the second form upwards
    (the reciprocal of a small number is large) and the first not at all.
    """
    stamps = [float(s) for s in stamps]
    if len(stamps) < 2:
        raise EvidenceError(
            "a rate needs at least two stamps, got {}".format(len(stamps)))
    span = stamps[-1] - stamps[0]
    if span <= 0.0:
        raise EvidenceError(
            "a rate needs the stamps to advance; the first and last read "
            "{:.9f} and {:.9f}".format(stamps[0], stamps[-1]))
    dts = [b - a for a, b in zip(stamps, stamps[1:])]
    positive = [d for d in dts if d > 0.0]
    dt_med = median(positive) if positive else 0.0
    return Rate(n=len(stamps), span_s=span,
                hz_mean=(len(stamps) - 1) / span,
                hz_median=(1.0 / dt_med) if dt_med > 0.0 else float("inf"),
                dt_mean=span / (len(stamps) - 1),
                dt_median=dt_med, dt_min=min(dts), dt_max=max(dts),
                n_nonpositive=len(dts) - len(positive))


def resample(source_t, source_v, at_t, max_gap_s):
    """One series read at another's timestamps, by linear interpolation.

    THE DENSER SERIES IS THE ONE THAT MOVES. The ground truth arrives at
    20 Hz and the estimate at ~500 Hz, so the estimate is interpolated
    onto the truth's stamps: interpolating the dense one costs almost
    nothing, and pairing by nearest-neighbour instead would carry up to
    25 ms of the vehicle's motion into the error - 17 mm at cruise, which
    is a tenth of the drift being measured.

    IT WILL NOT EXTRAPOLATE. A query outside the source's own span by
    more than max_gap_s is a refusal, because the honest answer there is
    that nothing was recorded.
    """
    source_t = [float(t) for t in source_t]
    source_v = [float(v) for v in source_v]
    if len(source_t) < 2:
        raise EvidenceError(
            "resampling needs at least two source samples, got {}".format(
                len(source_t)))
    if len(source_t) != len(source_v):
        raise EvidenceError(
            "resampling needs one value per stamp, got {} stamps and "
            "{} values".format(len(source_t), len(source_v)))
    out = []
    for query in at_t:
        query = float(query)
        if query < source_t[0] - max_gap_s or query > source_t[-1] + max_gap_s:
            raise EvidenceError(
                "the stamp {:.6f} lies inside the recorded span "
                "[{:.6f}, {:.6f}] to within {:g}s".format(
                    query, source_t[0], source_t[-1], max_gap_s))
        if query <= source_t[0]:
            out.append(source_v[0])
            continue
        if query >= source_t[-1]:
            out.append(source_v[-1])
            continue
        lo, hi = 0, len(source_t) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if source_t[mid] <= query:
                lo = mid
            else:
                hi = mid
        dt = source_t[hi] - source_t[lo]
        if dt <= 0.0:
            out.append(source_v[lo])
            continue
        frac = (query - source_t[lo]) / dt
        out.append(source_v[lo] + frac * (source_v[hi] - source_v[lo]))
    return out


# ----------------------------------------------------------------------
# drift
# ----------------------------------------------------------------------

def score_drift(truth_rows, est_rows, frame, max_gap_s=1.0):
    """The estimate against the ground truth, over a whole drive.

    Both arguments are sequences of (t, x, y, yaw): the truth in WORLD
    coordinates as the plant publishes it, the estimate in its own odom
    frame as the node publishes it. The frame is what makes them
    comparable and nothing else here touches coordinates.

    THE SCORE IS ABSOLUTE. The error at every sample is the estimate
    minus the transformed truth, full stop - no initial offset is
    removed, no per-run constant is fitted. If the estimate starts 0.4 m
    out it has drifted 0.4 m at its first sample and this says so.

    THE COMMON TIMELINE IS THE TRUTH's, for the reason resample() gives.
    Truth samples outside the estimate's own span are dropped rather than
    extrapolated onto, which is what makes a recording that started late
    a shorter score instead of a wrong one.
    """
    if len(truth_rows) < 2:
        raise EvidenceError(
            "the ground truth recorded at least two samples, got "
            "{}".format(len(truth_rows)))
    if len(est_rows) < 2:
        raise EvidenceError(
            "the estimate recorded at least two samples, got {}".format(
                len(est_rows)))

    tt, tx, ty, tyaw_raw = [], [], [], []
    for row in truth_rows:
        x, y, yaw = frame.apply(row[1], row[2], row[3])
        tt.append(float(row[0]))
        tx.append(x)
        ty.append(y)
        tyaw_raw.append(yaw)
    tyaw = unwrap(tyaw_raw)

    et = [float(r[0]) for r in est_rows]
    ex = [float(r[1]) for r in est_rows]
    ey = [float(r[2]) for r in est_rows]
    eyaw = unwrap([float(r[3]) for r in est_rows])

    keep = [i for i, t in enumerate(tt) if et[0] <= t <= et[-1]]
    if len(keep) < 2:
        raise EvidenceError(
            "the two recordings overlap in time: the truth spans "
            "[{:.3f}, {:.3f}] and the estimate [{:.3f}, {:.3f}]".format(
                tt[0], tt[-1], et[0], et[-1]))
    at = [tt[i] for i in keep]
    rx = resample(et, ex, at, max_gap_s)
    ry = resample(et, ey, at, max_gap_s)
    ryaw = resample(et, eyaw, at, max_gap_s)

    errors = []
    for k, i in enumerate(keep):
        errors.append(math.hypot(rx[k] - tx[i], ry[k] - ty[i]))
    last = keep[-1]
    return Drift(
        n=len(keep), t0=at[0], t1=at[-1],
        end_dx=rx[-1] - tx[last], end_dy=ry[-1] - ty[last],
        end_error_m=errors[-1],
        end_yaw_error_rad=normalise_angle(ryaw[-1] - tyaw[last]),
        rms_m=math.sqrt(math.fsum(e * e for e in errors) / len(errors)),
        max_error_m=max(errors),
        truth_path_m=path_length([tx[i] for i in keep],
                                 [ty[i] for i in keep]),
        est_path_m=path_length(rx, ry),
        truth_turned_rad=tyaw[last] - tyaw[keep[0]],
        est_turned_rad=ryaw[-1] - ryaw[0])


# ----------------------------------------------------------------------
# the steady-state window a corner is measured over
# ----------------------------------------------------------------------

def _held_runs(t, steer, speed, target_steer_rad, steer_tol_rad,
               speed_min_mps):
    """Every contiguous stretch where the axis is AT the angle and the
    vehicle is MOVING, as [first, last] index pairs.

    ONE CRITERION, ONE IMPLEMENTATION. steady_window() takes the longest
    of these and steady_runs() takes all of them, and they must never
    become two opinions about what "held" means - the per-corner table
    and the single-corner headline are read side by side in
    EVIDENCE_SENSORS.md 4, so a difference between them has to be the
    VEHICLE and never the reduction.
    """
    if not (len(t) == len(steer) == len(speed)):
        raise EvidenceError(
            "the corner trace has one steer and one speed per stamp: "
            "{} stamps, {} steer, {} speed".format(
                len(t), len(steer), len(speed)))
    if len(t) < 2:
        raise EvidenceError(
            "the corner trace has at least two samples, got {}".format(
                len(t)))
    runs = []
    run = None
    for i in range(len(t)):
        at_target = (abs(float(steer[i]) - float(target_steer_rad))
                     <= steer_tol_rad
                     and abs(float(speed[i])) >= speed_min_mps)
        if at_target:
            run = [i, i] if run is None else [run[0], i]
        else:
            if run is not None:
                runs.append(run)
            run = None
    if run is not None:
        runs.append(run)
    return runs


def _trim(t, run, trim_start_s, trim_end_s, min_window_s):
    """One held run with its slew-in and its exit taken off, or None.

    NEITHER END OF A CORNER IS A STEADY STATE. The axis has to slew INTO
    the angle, and on a short corner it is already slewing back OUT
    before the table's hold time is up - the tread command changes at the
    same instant, so the last fraction of a second carries a yaw rate at
    a falling speed. Both ends come off by a stated amount, and a run
    with nothing left in the middle is dropped rather than shrunk.
    """
    t0 = t[run[0]] + trim_start_s
    t1 = t[run[1]] - trim_end_s
    i0 = None
    for i in range(run[0], run[1] + 1):
        if t[i] >= t0:
            i0 = i
            break
    i1 = None
    for i in range(run[1], run[0] - 1, -1):
        if t[i] <= t1:
            i1 = i
            break
    if i0 is None or i1 is None or i1 <= i0:
        return None
    if t[i1] - t[i0] < min_window_s:
        return None
    return Window(t0=t[i0], t1=t[i1], i0=i0, i1=i1, n=i1 - i0 + 1)


def steady_runs(t, steer, speed, target_steer_rad, steer_tol_rad,
                speed_min_mps, trim_start_s, trim_end_s, min_window_s):
    """EVERY held corner of a run, each trimmed at both ends.

    THIS IS WHAT A REPEATED-CORNER PROFILE NEEDS AND THE LONGEST WINDOW
    CANNOT GIVE. `square` turns four corners at ONE steer angle and ONE
    speed, and they do not deliver the same yaw rate as each other - the
    delivered fraction depends on the vehicle's HEADING
    (EVIDENCE_SENSORS.md 4.2). A reduction that returned only the longest
    run would average that away, or worse, report whichever corner
    happened to last a sample longer as though it were the profile's.

    `found` is how many held runs the criterion saw and `windows` is how
    many survived the trimming and the minimum, because a corner that was
    driven and then dropped is a fact about the run and must not go
    missing between the two numbers.
    """
    runs = _held_runs(t, steer, speed, target_steer_rad, steer_tol_rad,
                      speed_min_mps)
    windows = []
    for run in runs:
        window = _trim(t, run, trim_start_s, trim_end_s, min_window_s)
        if window is not None:
            windows.append(window)
    return Runs(windows=windows, found=len(runs))


def steady_window(t, steer, speed, target_steer_rad, steer_tol_rad,
                  speed_min_mps, settle_s, min_window_s):
    """The single stretch of a run where the corner had established.

    FOUND IN THE DATA AND NOT COUNTED OFF THE SCHEDULE. The steer axis
    has to SLEW into a corner - config.yaml's square: block says every
    corner loses the yaw of its own first fraction of a second for
    exactly this reason - and how long that takes is a property of the
    plant, not of the table. So the window is the LONGEST stretch where
    the steer READING is at the target and the vehicle is moving, with
    the first settle_s of it discarded.

    NO EXIT IS TRIMMED HERE, and that is the difference between this
    reduction and steady_runs(). This one is for ONE long sustained
    corner, where the criterion's own end IS the corner's end - measured
    on corner_creep, the axis leaves tolerance 1.0 s after the segment
    ends and the vehicle is still at full creep speed inside every
    sub-bin of the window.

    A window that is never reached, or is too short to average, is a
    refusal naming the angle that was asked for. Reporting a yaw rate
    off two samples of a slewing axis would produce a number that looks
    exactly like a measurement.
    """
    runs = _held_runs(t, steer, speed, target_steer_rad, steer_tol_rad,
                      speed_min_mps)
    if not runs:
        raise EvidenceError(
            "the steer axis reached {:+.6f} rad (within {:g}) while the "
            "vehicle was moving; it never did".format(
                float(target_steer_rad), steer_tol_rad))
    best = max(runs, key=lambda run: run[1] - run[0])
    window = _trim(t, best, settle_s, 0.0, min_window_s)
    if window is None:
        held = t[best[1]] - t[best[0]]
        raise EvidenceError(
            "the corner at {:+.6f} rad held for {:g}s after a {:g}s settle, "
            "which is the {:g}s a steady-state yaw rate is averaged over; "
            "it held {:.3f}s in all".format(
                float(target_steer_rad), min_window_s, settle_s,
                min_window_s, held))
    return window


def corner_fidelity(yaw_rate, steer_rad, wheelbase_m, commanded_tread_mps,
                    measured_rear_mps):
    """Did the vehicle take the yaw its steer angle promised?

    TWO PREDICTIONS AND THEY ARE ONE FORMULA. A tricycle whose tyres do
    not slide sideways turns at

        psidot = v_tread * sin(delta) / L        (the drive wheel's speed)
               = v_rear  * tan(delta) / L        (the rear axle's speed)

    and the two are identical because v_rear = v_tread * cos(delta).
    config.yaml's square: table is written in the first spelling and this
    task's brief in the second, so both are computed and reported:

      ratio_commanded  scores the delivered yaw against what the COMMAND
                       promised. It carries longitudinal slip AND lateral
                       scrub together, and it is the number config.yaml's
                       drive_route: table is built from (0.401 at
                       0.785 rad, 0.634 at 1.25 rad).
      ratio_measured   scores it against what the vehicle ACTUALLY
                       travelled. Longitudinal slip is already inside the
                       measured speed, so what is left is the lateral
                       scrub alone - which is the question the corner
                       profile was added to answer.

    The effective radius is measured over measured: rear-axle ground
    speed divided by delivered yaw rate, with no kinematics in it at all.
    """
    wheelbase_m = float(wheelbase_m)
    if wheelbase_m <= 0.0:
        raise EvidenceError(
            "the wheelbase is positive, got {!r}".format(wheelbase_m))
    delta = abs(float(steer_rad))
    if delta <= 0.0:
        raise EvidenceError(
            "a corner has a steer angle; this one reads {!r} rad".format(
                steer_rad))
    rate = abs(float(yaw_rate))
    kin_cmd = abs(float(commanded_tread_mps)) * math.sin(delta) / wheelbase_m
    kin_meas = abs(float(measured_rear_mps)) * math.tan(delta) / wheelbase_m
    return Fidelity(
        yaw_rate=float(yaw_rate), steer_rad=float(steer_rad),
        kinematic_commanded=kin_cmd, kinematic_measured=kin_meas,
        ratio_commanded=(rate / kin_cmd) if kin_cmd > 0.0 else float("inf"),
        ratio_measured=(rate / kin_meas) if kin_meas > 0.0 else float("inf"),
        effective_radius_m=(abs(float(measured_rear_mps)) / rate
                            if rate > 0.0 else float("inf")),
        kinematic_radius_m=wheelbase_m / math.tan(delta))


# ----------------------------------------------------------------------
# the CSVs the recorder writes
# ----------------------------------------------------------------------

class Table(object):
    """One recorded stream: a header row and its columns.

    NUMBERS ARE PARSED ONCE, AT READ. "inf" and "nan" are kept as the
    floats they are rather than dropped, because a lidar beam that went
    out of range is a reading about the room and the analyser has to be
    able to see it in order to leave it out (finite_beam_series).
    """

    def __init__(self, path, names, columns, n):
        self.path = path
        self.names = list(names)
        self._columns = columns
        self.n = n

    def has(self, name):
        return name in self._columns

    def column(self, name):
        if name not in self._columns:
            raise EvidenceError(
                "{} carries a column named {!r}; it carries {}".format(
                    self.path, name,
                    ", ".join(repr(c) for c in self.names)))
        return self._columns[name]

    def rows(self, *names):
        cols = [self.column(name) for name in names]
        return list(zip(*cols))


def read_csv(path):
    """One headered CSV, as columns.

    AN EMPTY CAPTURE IS A REFUSAL AND NOT AN EMPTY TABLE. A stream that
    delivered a header and no rows would otherwise reach a statistic and
    come back as a plausible-looking zero.
    """
    if not os.path.isfile(path):
        raise EvidenceError("the capture {} exists".format(path))
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = _csv.reader(handle)
        try:
            names = next(reader)
        except StopIteration:
            raise EvidenceError(
                "the capture {} carries a header row; the file is "
                "empty".format(path))
        columns = collections.OrderedDict((name, []) for name in names)
        n = 0
        for row in reader:
            if not row:
                continue
            if len(row) != len(names):
                raise EvidenceError(
                    "every row of {} has {} fields like its header; row {} "
                    "has {}".format(path, len(names), n + 1, len(row)))
            for name, cell in zip(names, row):
                try:
                    columns[name].append(float(cell))
                except ValueError:
                    columns[name].append(cell)
            n += 1
    if n == 0:
        raise EvidenceError(
            "the capture {} recorded at least one sample; it has a header "
            "and no rows".format(path))
    return Table(path, names, columns, n)


def finite_beam_series(table, prefix):
    """The columns under `prefix` that carried a finite reading EVERY
    frame, in index order.

    A beam that is out of range in one frame and not the next is the
    ROOM, not the noise - the truck is at rest but the renderer's own
    accuracy at shallow incidence moves a marginal return across the
    range limit - and averaging it in would invent a reading.
    tools/noise_probe.sh makes the same exclusion and says so.
    """
    def index_of(name):
        tail = name[len(prefix):]
        try:
            return (0, int(tail))
        except ValueError:
            return (1, tail)

    out = collections.OrderedDict()
    for name in sorted((n for n in table.names if n.startswith(prefix)),
                       key=index_of):
        series = table.column(name)
        if all(isinstance(v, float) and math.isfinite(v) for v in series):
            out[name] = series
    return out


# ----------------------------------------------------------------------
# the model, which is the authority on every CONFIGURED figure
# ----------------------------------------------------------------------

#: The five things a gz noise element can say. `type` is in the list and
#: it is not decoration: a gpu_lidar declared `gaussian_quantized`
#: produces NO NOISE AT ALL on this version (EVIDENCE_MODEL_V3.md 9.2,
#: measured both ways), so a configured column that printed only the
#: stddev would say 0.02 about a channel that is silent.
NOISE_FIELDS = ("type", "mean", "stddev", "bias_mean", "bias_stddev")


def _noise_element(element):
    """One <noise> block as a dict.

    The type is spelled TWO WAYS in one file and both are legal SDF: a
    lidar and a camera carry <type>gaussian</type> as a child, an IMU
    axis carries type="gaussian" as an attribute. Both are read.
    """
    out = {"type": element.get("type")}
    for field in NOISE_FIELDS:
        if field == "type":
            continue
        text = element.findtext(field)
        out[field] = None if text is None else float(text)
    if out["type"] is None:
        out["type"] = element.findtext("type")
    return out


def sdf_sensors(path):
    """Every <sensor> in a model file, with its rate, topic and noise.

    THE SDF IS THE AUTHORITY AND THIS IS HOW A PYTHON PROGRAM OBEYS IT.
    config.yaml's sensors: block repeats the update rates because a SHELL
    cannot read XML and says so in its own header - "it may hold NOTHING
    the SDF does not already decide". That exception does not extend to
    this file: everything EVIDENCE_SENSORS.md prints in its CONFIGURED
    column is read here, out of the model the plant was built from, so
    the column cannot drift away from the plant it describes.

    Noise is keyed by the CHANNEL it belongs to - "range" for a lidar,
    "depth" for a camera, "angular_velocity_x" and its five siblings for
    an IMU - because a sensor can carry more than one.
    """
    from xml.etree import ElementTree

    if not os.path.isfile(path):
        raise EvidenceError("the model {} exists".format(path))
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise EvidenceError(
            "the model {} is well-formed XML: {}".format(path, exc))
    out = collections.OrderedDict()
    for sensor in root.iter("sensor"):
        name = sensor.get("name")
        rate = sensor.findtext("update_rate")
        entry = {
            "name": name,
            "type": sensor.get("type"),
            "topic": sensor.findtext("topic"),
            "update_rate": None if rate is None else float(rate),
            "noise": collections.OrderedDict(),
        }
        for tag, channel in (("lidar", "range"), ("camera", "depth")):
            block = sensor.find(tag)
            if block is None:
                continue
            noise = block.find("noise")
            if noise is not None:
                entry["noise"][channel] = _noise_element(noise)
            samples = block.findtext("./scan/horizontal/samples")
            if samples is not None:
                entry["samples"] = int(samples)
            for edge in ("min", "max"):
                text = block.findtext("./range/" + edge)
                if text is not None:
                    entry["range_" + edge] = float(text)
        imu = sensor.find("imu")
        if imu is not None:
            for group in ("angular_velocity", "linear_acceleration"):
                block = imu.find(group)
                if block is None:
                    continue
                for axis in ("x", "y", "z"):
                    axis_block = block.find(axis)
                    if axis_block is None:
                        continue
                    noise = axis_block.find("noise")
                    if noise is not None:
                        entry["noise"]["{}_{}".format(group, axis)] = \
                            _noise_element(noise)
            entry["enable_orientation"] = imu.findtext("enable_orientation")
        out[name] = entry
    if not out:
        raise EvidenceError(
            "the model {} declares at least one sensor; it declares "
            "none".format(path))
    return out


def sdf_gravity(path):
    """The magnitude of a world's own gravity vector.

    IT IS READ AND NOT ASSUMED, and this is not pedantry: the accelerometer
    at rest reads gravity plus its bias, so the bias can only be checked
    against the model if the gravity underneath it is the world's own
    number. warehouse_ver3.sdf declares 9.8 while forklift_ver3's mass
    derivation uses standard gravity 9.80665 - the two differ by 0.0067,
    which is a THIRD of the accelerometer bias being measured against
    them. Assuming 9.80665 here would have turned a bias that matches the
    model into one that misses it by 34 %.

    IT SCANS FOR THE ELEMENT RATHER THAN PARSING THE DOCUMENT, and that
    is measured rather than lazy: m6/gazebo/warehouse_ver3.sdf IS NOT
    WELL-FORMED XML. Its header comment draws the floor plan with rules
    made of hyphens, and `--` inside an XML comment is illegal - python's
    ElementTree refuses the file at line 18 while gz's own parser accepts
    it without a word. The file belongs to m6 and is used BY REFERENCE
    (CONTEXT.md); it is not this track's to correct. So comments are
    stripped and the one element is found by scan, which is the right
    tool for a document a strict parser will not open.
    """
    import re

    if not os.path.isfile(path):
        raise EvidenceError("the world {} exists".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    # Comments first, so a <gravity> drawn inside one is not read as the
    # world's. Non-greedy, so each comment ends at its own `-->`.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    match = re.search(r"<gravity>([^<]*)</gravity>", text)
    if match is None:
        raise EvidenceError(
            "the world {} declares a <gravity>; it does not, so the "
            "engine's default is in force and this file cannot say what "
            "it is".format(path))
    parts = [float(value) for value in match.group(1).split()]
    return math.sqrt(math.fsum(value * value for value in parts))


def sdf_sensor(sensors, name):
    """One sensor by the name the model gives it, or a refusal listing
    the names it does give."""
    if name not in sensors:
        raise EvidenceError(
            "the model declares a sensor named {!r}; it declares {}".format(
                name, ", ".join(repr(n) for n in sensors)))
    return sensors[name]


def split_clamped(series, range_min, tol):
    """The readings that are pinned to the sensor's range minimum, apart
    from the ones that are not.

    A gz lidar return closer than <range><min> comes back CLAMPED TO THE
    MINIMUM rather than as a no-reading (EVIDENCE_MODEL_V3.md 8, where
    562 readings of one sweep are exactly 0.300). A clamped beam is not
    measuring the room, so its temporal spread is not a noise figure -
    and on the back safety scanner, which sees the vehicle's own
    counterweight, there are enough of them to drag a mean noise figure
    down by a third. They are SEPARATED and both counts are reported,
    never averaged together and never silently dropped.
    """
    free = collections.OrderedDict()
    clamped = collections.OrderedDict()
    for name, values in series.items():
        if abs(mean(values) - float(range_min)) <= tol:
            clamped[name] = values
        else:
            free[name] = values
    return free, clamped


def temporal_spread(series):
    """How much each reading moved about its own mean, over the frames.

    WHY TEMPORAL AND NOT SPATIAL, in tools/noise_probe.sh's words: a
    stationary scan's spread ACROSS beams is the room and says nothing.
    What a noise block adds is spread across TIME at a fixed beam, on a
    vehicle that is not moving. This returns the summary of those
    per-reading spreads, plus how many of them did not move at all -
    which is the reading that caught `gaussian_quantized` producing no
    noise whatsoever (EVIDENCE_MODEL_V3.md 9.2).
    """
    if not series:
        raise EvidenceError(
            "at least one reading was finite in every frame; none was")
    sds = []
    means = []
    for values in series.values():
        sds.append(stddev(values))
        means.append(mean(values))
    return summarise(sds), summarise(means), sum(1 for s in sds if s == 0.0)


# ----------------------------------------------------------------------
# the operator's own check
# ----------------------------------------------------------------------

def _selftest():
    """Synthetic CSVs in, arithmetic nobody has to trust out.

    tests/test_evidence_core.py is the real suite; this is the version an
    operator can run on the rig, in the shell they are already in,
    without pytest - and it is the one that proves the file can read a
    CSV of the shape sensor_evidence.py writes, which the unit tests do
    only in a tmp_path.
    """
    import tempfile

    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    check("the sample spread of 1..5 is sqrt(2.5)",
          abs(stddev([1.0, 2.0, 3.0, 4.0, 5.0]) - math.sqrt(2.5)) < 1e-12)
    check("a bias moves the mean and leaves the spread alone",
          abs(stddev(remove_mean([7.5, 8.5, 9.5]))
              - stddev([0.0, 1.0, 2.0])) < 1e-12)

    frame = SpawnFrame(-17.0, 10.0, math.pi)
    x, y, yaw = frame.apply(-17.0, 10.0, math.pi)
    check("the spawn pose is the origin of the spawn frame",
          abs(x) < 1e-12 and abs(y) < 1e-12 and abs(yaw) < 1e-12)
    x, _, _ = frame.apply(-5.3968, 10.0, math.pi)
    check("11.6 m of world +x is -11.6 m in the spawn frame",
          abs(x + 11.6032) < 1e-9)
    x, y, _ = SpawnFrame(0.0, 0.0, math.pi / 2).apply(1.0, 0.0, 0.0)
    check("a quarter-turn spawn puts world +x on spawn -y",
          abs(x) < 1e-12 and abs(y + 1.0) < 1e-12)

    rate = rate_from_stamps([i / 15.0 for i in range(151)])
    check("150 intervals of 1/15 s read 15 Hz",
          abs(rate.hz_mean - 15.0) < 1e-9)

    still = [(i * 0.05, -17.0, 10.0, math.pi) for i in range(21)]
    score = score_drift(still, [(i * 0.05, 0.40, 0.0, 0.0)
                                for i in range(21)], frame)
    check("a 0.40 m offset that never grows still scores 0.40 m",
          abs(score.end_error_m - 0.40) < 1e-9
          and abs(score.rms_m - 0.40) < 1e-9)

    kin = 0.3 * math.sin(0.785398) / 1.05
    fid = corner_fidelity(yaw_rate=kin, steer_rad=0.785398, wheelbase_m=1.05,
                          commanded_tread_mps=0.3,
                          measured_rear_mps=0.3 * math.cos(0.785398))
    check("an ideal tricycle scores a fidelity of 1 both ways",
          abs(fid.ratio_commanded - 1.0) < 1e-12
          and abs(fid.ratio_measured - 1.0) < 1e-12)

    # A CSV of the shape the recorder writes, read back and measured.
    handle, path = tempfile.mkstemp(suffix="_scan_nav.csv", text=True)
    os.close(handle)
    try:
        with open(path, "w", encoding="utf-8") as out:
            out.write("t_sim,t_wall,beam_0,beam_1\n")
            for i, (a, b) in enumerate([(3.60, float("inf")),
                                        (3.62, 4.0), (3.58, 4.0),
                                        (3.60, 4.0), (3.60, 4.0)]):
                out.write("{:.9f},{:.6f},{:.6f},{}\n".format(
                    i / 15.0, 1000.0 + i / 15.0, a, b))
        table = read_csv(path)
        check("the reader reads five frames", table.n == 5)
        series = finite_beam_series(table, "beam_")
        check("a beam that went out of range in one frame is left out",
              list(series) == ["beam_0"])
        spread, _, zeros = temporal_spread(series)
        check("the surviving beam's temporal spread is its own stddev",
              abs(spread.mean - stddev([3.60, 3.62, 3.58, 3.60, 3.60]))
              < 1e-12 and zeros == 0)
        rate = rate_from_stamps(table.column("t_sim"))
        check("the capture's own stamps read 15 Hz",
              abs(rate.hz_mean - 15.0) < 1e-6)
    finally:
        os.remove(path)

    try:
        stddev([1.0])
    except EvidenceError:
        check("one reading is refused rather than given a spread of zero",
              True)
    else:
        check("one reading is refused rather than given a spread of zero",
              False)

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    # The denominator is derived from the checks that ran and never typed
    # beside them (LESSONS 2026-07-28).
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the arithmetic behind EVIDENCE_SENSORS.md. The tool "
                    "that uses it is tools/sensor_evidence.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-Gazebo checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
