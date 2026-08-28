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
             "truth_turned_rad est_turned_rad truth_end_yaw_rad "
             "truth_nose_forward_m")

#: ONE POSITION ERROR, SPLIT ALONG THE DIRECTION THE TRUCK WAS FACING.
#: `along` is the estimate running LONG (+) or SHORT (-) of where the
#: vehicle actually got to; `cross` is it sitting to the LEFT (+) or the
#: RIGHT (-) of the path. See track_error() for why the split is taken in
#: the ground truth's frame and not the estimate's.
TrackError = collections.namedtuple("TrackError", "along cross")

#: ONE FIGURE OF ONE ESTIMATE AGAINST THE SAME FIGURE OF ANOTHER.
#: `before` and `after` are kept as they were measured, SIGNS AND ALL -
#: a heading error says which way the estimate was wrong and that is not
#: information a comparison may throw away. `removed` and `fraction` are
#: about MAGNITUDES, because an error of -1.73 rad becoming +0.02 rad is
#: an improvement of 1.71 and not of 1.75.
Removed = collections.namedtuple("Removed", "before after removed fraction")

#: What fusing bought, over one run, on the four figures the drift table
#: publishes - plus how far apart the two scores' windows were, which is
#: not decoration. See compare_drift().
Comparison = collections.namedtuple(
    "Comparison", "end_error end_yaw along cross rms max_error "
                  "span_gap_start_s span_gap_end_s")

#: WHAT AN ABSOLUTE LOCALISER COSTS THE THING THAT READS IT. F3's
#: `map` -> `odom` is re-broadcast on every scan and CHANGES only when
#: the filter corrects, so a run's worth of that edge is a few dozen
#: steps buried in a few thousand repeats. `n` counts the steps, `dpos`
#: and `dyaw` are their sizes, and `samples` is what they were found in -
#: because "four corrections" means nothing without "in 372 broadcasts
#: over 24.6 s". See tf_jumps().
Jumps = collections.namedtuple(
    "Jumps", "n samples span_s dpos dyaw max_dpos_m max_dyaw_rad per_s")

#: A corner, against the kinematics it was supposed to obey.
Fidelity = collections.namedtuple(
    "Fidelity", "yaw_rate steer_rad kinematic_commanded kinematic_measured "
                "ratio_commanded ratio_measured effective_radius_m "
                "kinematic_radius_m")

#: WHERE the missing yaw of a corner went: the steered wheel sliding
#: sideways, the rear axle sliding sideways, or both. Every field is a
#: mean over the window. See scrub_split() for the identity that ties
#: them together and for what `residual` is worth.
ScrubSplit = collections.namedtuple(
    "ScrubSplit", "n u_mps rear_lat_mps front_lat_mps front_along_mps "
                  "front_slip_mps front_slip_off_plane_rad tread_slip "
                  "yaw_rate kinematic front_term rear_term deficit "
                  "front_share rear_share front_slip_angle_rad "
                  "rear_slip_angle_rad residual")


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


def correlation(xs, ys):
    """Pearson's r of two equal-length series, or None where it has none.

    NONE AND NOT ZERO WHEN EITHER SERIES IS FLAT. r is a covariance
    divided by two spreads, and a series with no spread has no
    correlation with anything - reporting 0.0 there would read as "these
    two are unrelated", which is a claim, where the truth is that the
    question was not asked. tools/drive_goal.py's curvature_following
    prints it beside a regression slope and the pair is only readable if
    a missing r looks missing.
    """
    xs = [float(v) for v in xs]
    ys = [float(v) for v in ys]
    if len(xs) != len(ys):
        raise EvidenceError(
            "correlation: {} against {} - these are two readings of the "
            "SAME samples".format(len(xs), len(ys)))
    if len(xs) < 2:
        return None
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    syy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sxx < 1e-12 or syy < 1e-12:
        return None
    return sxy / (sxx * syy)


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

def closure(xs, ys):
    """How far from its own start a trajectory finished.

    THE CLASSIC OPEN-LOOP READING, and it is a fact about the PLANT when
    it is taken over the ground truth: a profile written to come back to
    where it started either does or does not, and the gap is what the
    table's corner times were worth. It is NOT a drift figure and must
    not be read as one - EVIDENCE_SENSORS.md 3.1(b) measures an
    out-and-back profile whose ESTIMATE closes to 0.04 m while being
    1.23 m out at the far end - so this returns the closure of whichever
    trajectory it is handed and the caller says which one that was.
    """
    if len(xs) != len(ys):
        raise EvidenceError(
            "a trajectory has one y per x, got {} and {}".format(
                len(xs), len(ys)))
    if len(xs) < 2:
        raise EvidenceError(
            "a closure needs a start and an end, got {} sample(s)".format(
                len(xs)))
    return math.hypot(float(xs[-1]) - float(xs[0]),
                      float(ys[-1]) - float(ys[0]))


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


def world_frame():
    """The frame that does nothing, for a score taken in WORLD metres.

    WHY AN ABSOLUTE SCORE NEEDS ONE AT ALL. score_drift() transforms the
    TRUTH and compares it against an estimate already in the target
    frame, because F1 and F2 scored an estimate born in the odom frame -
    the vehicle at spawn - and the truth had to be brought to it. F3's
    estimate is born in the MAP frame and is carried into the BUILDING
    by the committed registration (rows_to_world), so by the time it
    reaches the scorer both sides are already in world metres and the
    truth must be left exactly as the plant published it.

    IT IS A SpawnFrame AT THE ORIGIN AND NOT A SECOND CLASS. The
    arithmetic of "subtract nothing and rotate by nothing" is the
    arithmetic tests/test_evidence_core.py already locks; a second
    implementation of the identity would be a second thing that could
    stop being one.

    AND THE SCORE IS THE SAME SIZE EITHER WAY, which is worth saying
    because it looks like a choice that could move a number. Every
    figure score_drift() returns is either a distance, an angle, or a
    projection of one onto the other, and a rigid transform applied to
    BOTH sides changes none of them. What the world frame buys is that
    the printed dx/dy are metres east and north in the building, which
    is what a reader of an absolute figure is entitled to.
    """
    return SpawnFrame(0.0, 0.0, 0.0)


# ----------------------------------------------------------------------
# the map frame
# ----------------------------------------------------------------------

class MapFrame(object):
    """The committed registration, as a transform anything may apply.

        p_map = R(theta) . p_world + t
        yaw_map = yaw_world + theta

    and `to_world` is that inverted. It is the ONE spelling of the
    world <-> map transform on this track: tools/map_core.py's
    world_to_map() and map_to_world() delegate here rather than carrying
    a second copy, because two copies of a MECHANISM drift the way two
    copies of a VALUE do and the copy that gets fixed is the one that was
    already right (tools/_common.sh's own argument).

    WHY IT LIVES IN THIS FILE AND NOT IN map_core. map_core imports this
    module - MapError is an EvidenceError - so the dependency can only
    run one way, and the transform is needed on THIS side: F3's absolute
    score carries a map-frame pose into the building, and that score is
    evidence arithmetic. What stays in map_core is what the transform is
    DERIVED from: grids, wall fits and the world's own rectangles.

    THE HALF TURN IS WHY THIS IS TESTED AT TWO ANGLES. warehouse_v3's
    theta is -179.813 deg, and at a half turn a rotation is very nearly
    its own inverse - so applying the wrong one leaves every magnitude
    EXACTLY right and puts the answer on the other side of the map. That
    is SpawnFrame's trap, one frame further out, and the suite runs every
    case here at a quarter turn as well.

    THE INSTRUMENT FLOOR TRAVELS WITH IT. `residual_rms_m` and
    `residual_max_m` are the registration's own residual against the
    building (EVIDENCE_MAP_V3.md 6.4) and no absolute figure derived
    through this transform may be printed without them. They are carried
    here so that the print site has them in hand rather than looking them
    up again; a frame built from three bare numbers has None, because
    "no floor stated" is a different thing from "a floor of zero".
    """

    #: The three the transform cannot exist without. A registration that
    #: is missing one is refused by the NAME of the missing key - it is
    #: either not a registration this track wrote or it is a truncated
    #: one, and both are things the operator has to go and look at.
    REQUIRED = ("theta_rad", "t_x_m", "t_y_m")

    def __init__(self, theta_rad, t_x_m, t_y_m,
                 residual_rms_m=None, residual_max_m=None):
        self.theta_rad = float(theta_rad)
        self.t_x_m = float(t_x_m)
        self.t_y_m = float(t_y_m)
        self.residual_rms_m = (None if residual_rms_m is None
                               else float(residual_rms_m))
        self.residual_max_m = (None if residual_max_m is None
                               else float(residual_max_m))
        self._c = math.cos(self.theta_rad)
        self._s = math.sin(self.theta_rad)

    @classmethod
    def from_registration(cls, record):
        """A MapFrame out of what map_register.load_registration() read.

        The record is a plain dict of the committed file's scalars. What
        binds it to a GRID is not this function - it is
        load_registration(), which refuses a registration whose .pgm has
        changed underneath it (F3 constraint 16). This only refuses a
        record that is not a registration at all.
        """
        for key in cls.REQUIRED:
            if key not in record:
                raise EvidenceError(
                    "the registration carries {}: it is not a "
                    "registration this track wrote, or it is a truncated "
                    "one. What it does carry: {}".format(
                        key, ", ".join(sorted(record)) or "(nothing)"))
        return cls(record["theta_rad"], record["t_x_m"], record["t_y_m"],
                   record.get("residual_rms_m"),
                   record.get("residual_max_m"))

    def to_map(self, x, y, yaw=None):
        mx = self._c * float(x) - self._s * float(y) + self.t_x_m
        my = self._s * float(x) + self._c * float(y) + self.t_y_m
        if yaw is None:
            return (mx, my)
        return (mx, my, normalise_angle(float(yaw) + self.theta_rad))

    def to_world(self, x, y, yaw=None):
        dx = float(x) - self.t_x_m
        dy = float(y) - self.t_y_m
        wx = self._c * dx + self._s * dy
        wy = -self._s * dx + self._c * dy
        if yaw is None:
            return (wx, wy)
        return (wx, wy, normalise_angle(float(yaw) - self.theta_rad))

    def floor(self):
        """The one sentence every absolute figure has to be read with."""
        if self.residual_max_m is None:
            return "no registration residual was stated with this transform"
        rms = (float("nan") if self.residual_rms_m is None
               else self.residual_rms_m)
        return ("registration residual rms {:.4f} m, MAX {:.4f} m - no "
                "figure at or below the MAX is a measurement of the "
                "localiser".format(rms, self.residual_max_m))


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

def diverged_at(xs, ys, limit_m):
    """The index of the first sample that has left the building, or None.

    A FILTER THAT HAS BLOWN UP IS NOT A FILTER WITH A LARGE ERROR, and
    this is the only place on this track that draws that line. Every
    other score here is ABSOLUTE and unbounded on purpose: a
    dead-reckoned pose is ALLOWED to drift without limit and saying so
    is the whole of §5. What it is not allowed to do is leave the
    warehouse. The floor is 48 m x 32 m, so an odom-frame estimate a
    hundred metres from where the vehicle switched on has not drifted -
    it has broken - and the two must not share a table.

    WHY IT EXISTS, MEASURED. `robot_localization` 3.8.3 diverges at
    startup on most bringups of this stack: its covariance reaches 1e84
    in a single cycle and its pose 1e48 m, and it logs NOTHING. `status`
    reads ALIVE, the topic is at its configured rate, and the recorder's
    stream arrives - so every instrument this track already had would
    call that a healthy run (EVIDENCE_FUSION.md §2.6 named three such
    failures; §8.6 is the fourth). Without this check the drift table is
    printed with 1e48 in it and the reader is the guard.

    NON-FINITE IS DIVERGED WHATEVER THE BOUND, because a comparison
    against nan is false in both directions and would pass a bound test
    written the obvious way round.
    """
    limit = float(limit_m)
    for i, (x, y) in enumerate(zip(xs, ys)):
        x = float(x)
        y = float(y)
        if not (math.isfinite(x) and math.isfinite(y)):
            return i
        if math.hypot(x, y) > limit:
            return i
    return None


def require_not_diverged(xs, ys, limit_m, what):
    """diverged_at(), as the refusal the caller has to answer."""
    i = diverged_at(xs, ys, limit_m)
    if i is None:
        return
    raise EvidenceError(
        "{} stayed inside {:g} m of where it started, and it did not: "
        "sample {} of {} reads ({:g}, {:g}). That is not drift, it is a "
        "filter that has diverged - see EVIDENCE_FUSION.md 8.6".format(
            what, float(limit_m), i, len(list(xs)), float(list(xs)[i]),
            float(list(ys)[i])))


def echo_is_undiscovered(text):
    """True when `ros2 topic echo --once` exited without matching a publisher.

    MEASURED on this rig, and ekf_health.py's own comment already names
    it: that invocation returns IMMEDIATELY with

        WARNING: topic [...] does not appear to be published yet
        Could not determine the type for the passed topic

    rather than waiting for discovery. config.yaml's
    ekf.startup_check.timeout_s is a claim about waiting; without this
    test the gate treats the immediate miss as a message, raises
    EvidenceError on the missing covariance, and refuses a stack that
    is in fact healthy. The retry lives in ekf_health.read_once; this
    is the classification a test can reach without ROS.
    """
    body = str(text)
    return ("does not appear to be published yet" in body
            or "Could not determine the type" in body)


def worst_covariance(text):
    """The largest MAGNITUDE in a covariance printed by `ros2 topic echo`.

    WHY A SHELL CANNOT DO THIS AND WHY IT IS NOT IN THE SHELL ANYWAY.
    m5v3.sh's startup gate reads one message off the filter's output
    topic and has to decide whether the thing that published it is a
    filter or a wreck. That decision is a parse and a comparison, both of
    which are logic, and this track keeps logic where a test can reach it
    without a simulator - so the shell runs `ros2 topic echo`, and this
    reads what came back. tools/ekf_health.py is the two-line shell
    around it.

    THE LARGEST MAGNITUDE AND NOT THE FIRST ENTRY. A diverged filter on
    this stack publishes 5.74e87 on the xx diagonal and -5.08e91 off it,
    so a gate reading covariance[0] would be reading the SMALLER of the
    two by four orders of magnitude. It is also the reason the sign is
    dropped: an off-diagonal is allowed to be negative and a magnitude is
    what a ceiling can be compared against. Nothing here checks that the
    matrix is a valid covariance - a diverged one is not, and finding out
    which way it is invalid is not what a bringup gate is for.

    BOTH SPELLINGS, because `ros2 topic echo` prints a float array as a
    YAML block sequence and `--field` prints it as an inline list, and a
    gate that only understood one of them would fail the day somebody
    made the call more specific.

    AN EMPTY OR COVARIANCE-FREE READ IS A REFUSAL AND NEVER A ZERO. A
    topic nobody publishes echoes nothing at all, and "no numbers, so
    the worst is 0, so the filter is healthy" is the gate failing OPEN on
    exactly the case it was written for.
    """
    body = text[text.index("covariance"):] if "covariance" in text else ""
    if not body:
        raise EvidenceError(
            "the message carries a covariance: no 'covariance' appears in "
            "{} character(s) of output. An empty read is a topic nobody "
            "published on, not a healthy filter.".format(len(text)))
    # Everything from the first `covariance` to the next key that is not
    # part of one: a block sequence item starts with `-`, an inline list
    # is on the `covariance:` line itself.
    values = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("covariance"):
            stripped = stripped.split(":", 1)[-1]
        elif stripped.startswith("- "):
            stripped = stripped[2:]
        elif stripped == "-":
            continue
        else:
            if values:
                break
            continue
        for token in stripped.replace("[", " ").replace("]", " ").replace(
                ",", " ").split():
            try:
                values.append(abs(float(token)))
            except ValueError:
                continue
    if not values:
        raise EvidenceError(
            "the message's covariance carries numbers: 'covariance' "
            "appears but no value follows it.")
    return max(values)


def covariance_is_absent(text):
    """Did the estimator publish a covariance, or 36 zeros?

    A ZERO MATRIX IS ABSENT AND NOT CERTAIN, and this track has now met
    the distinction twice. `rf2o_laser_odometry` never assigns its twist
    covariance and ships 36 zeros (EVIDENCE_FUSION.md 10.1b);
    `fuse_models::Odometry2DPublisher` 1.1.5 does the same with the pose
    AND the twist of everything it publishes on this stack, measured with
    and without predict_to_current_time and with no warning in its log
    (EVIDENCE_FUSION.md 11.2). Read as a covariance, that says the
    estimate is EXACTLY right, which no estimator has ever meant.

    WHY THE BRINGUP GATE NEEDS TO ASK. require_covariance_under() is
    this stack's answer to a filter that diverges silently, and against
    an all-zero matrix it cannot fail: 0.0 is under every ceiling. A
    gate that cannot fail is worse than no gate, because it is READ as
    an answer. So tools/ekf_health.py asks this first and, on an arm
    that publishes nothing, says so and gates on the POSE instead.

    NOT A COVARIANCE AT ALL IS STILL A REFUSAL. This delegates the parse
    to worst_covariance(), so an empty read - a topic nobody published on
    - raises there rather than returning True and quietly sending the
    gate down its fallback path.
    """
    return worst_covariance(text) == 0.0


def covariance_absent_in(values):
    """covariance_is_absent(), for a covariance already IN HAND.

    THE SECOND GATE HOLDS A MESSAGE, which is require_worst_under()'s
    reason word for word: tools/ekf_health.py shells out to `ros2 topic
    echo` and parses text, tools/localization_health.py subscribes and
    holds the 36 floats. The question is the same one and the answer is
    read the same way - an all-zero matrix is ABSENT and not CERTAIN,
    and a ceiling cannot fail against it, so a gate that did not ask
    would report a pass it never tested.
      AN EMPTY MATRIX RAISES HERE TOO, through worst_of().
    """
    return worst_of(values) == 0.0


def position_of(text):
    """(x, y) out of the POSE of a nav_msgs/Odometry printed by
    `ros2 topic echo`.

    THE FIRST `position:` BLOCK AND NOTHING ELSE. That message carries
    two `x:`/`y:` pairs at the same indentation - pose.pose.position and
    twist.twist.linear - and a parse that took the last one would gate on
    a VELOCITY, which at bringup is near zero on a healthy stack AND on a
    wreck whose pose is 1e48 m from the origin.

    A VALUE THAT IS NOT A NUMBER IS A REFUSAL. `ros2 topic echo` prints a
    NaN as `.nan`, which float() will not read, and skipping it would
    hand the caller the next number down - which is `z`, and is always
    0.0 on this plant.
    """
    where = text.find("position:")
    if where < 0:
        raise EvidenceError(
            "the message carries a pose: no 'position:' appears in {} "
            "character(s) of output.".format(len(text)))
    found = {}
    for line in text[where:].splitlines()[1:]:
        stripped = line.strip()
        for axis in ("x", "y"):
            if axis in found or not stripped.startswith(axis + ":"):
                continue
            token = stripped.split(":", 1)[1].strip()
            try:
                found[axis] = float(token)
            except ValueError:
                raise EvidenceError(
                    "the pose's {} is a number, and it reads {!r}. A "
                    "non-finite pose is what a diverged estimator "
                    "publishes.".format(axis, token))
        if len(found) == 2:
            return found["x"], found["y"]
    raise EvidenceError(
        "the message's pose carries an x and a y: 'position:' appears "
        "and {} of the two follow it.".format(len(found)))


def require_covariance_under(text, ceiling, what):
    """worst_covariance(), as the refusal a bringup gate has to answer.

    Returns the figure when it passes, so the caller can print what it
    checked rather than only that it checked.
    """
    return require_worst_under(worst_covariance(text), ceiling, what)


def require_worst_under(worst, ceiling, what):
    """One covariance figure against one ceiling, as a refusal.

    IT TAKES A NUMBER BECAUSE THE SECOND GATE HAS ONE. The F2 bringup
    gate shells out to `ros2 topic echo` and parses text
    (worst_covariance above); F3's localisation gate holds a MESSAGE,
    because it has to publish an initial pose before it can read one and
    a subprocess cannot be made to do both in the right order. The
    comparison and the sentence it refuses in are the same either way,
    and this is where they are, once.
    """
    worst = float(worst)
    if worst > float(ceiling):
        raise EvidenceError(
            "{} published a covariance inside {:g}, and it did not: the "
            "largest entry is {:g}. That is not an uncertain estimate, it "
            "is a filter that has diverged - see EVIDENCE_FUSION.md 8.6 "
            "and 9.".format(what, float(ceiling), worst))
    return worst


def worst_of(values):
    """The largest MAGNITUDE in a covariance already in hand.

    THE LARGEST AND NOT THE FIRST, for worst_covariance()'s reason: a
    diverged filter on this stack publishes 5.74e87 on the xx diagonal
    and -5.08e91 off it, so a gate reading entry 0 would read the
    smaller of the two by four orders of magnitude. The sign is dropped
    because an off-diagonal is allowed to be negative and a ceiling is a
    comparison against a magnitude.

    AN EMPTY MATRIX IS A REFUSAL AND NEVER A ZERO, exactly as an empty
    read is: "no numbers, so the worst is 0, so it is healthy" is the
    gate failing OPEN on the case it was written for.
    """
    values = [abs(float(v)) for v in values]
    if not values:
        raise EvidenceError(
            "the message carries a covariance: it has no entries at all. "
            "An empty matrix is not a certain estimate.")
    if not all(math.isfinite(v) for v in values):
        raise EvidenceError(
            "the covariance is finite, and it is not: it carries "
            "{}. A non-finite entry is what a filter that has blown up "
            "publishes.".format(
                ", ".join(repr(v) for v in values
                          if not math.isfinite(v))[:120]))
    return max(values)


def require_pose_near(x, y, ref_x, ref_y, tolerance_m, what):
    """One pose against the pose it was SUPPOSED to be at, as a refusal.

    WHY A LOCALISER NEEDS THIS AND A FILTER DOES NOT. F2's bringup gate
    asks whether the estimator's covariance is sane, because an estimator
    that has diverged says so in its covariance. A LOCALISER that never
    received its initial pose does not diverge - it reports a perfectly
    ordinary pose, with a perfectly ordinary covariance, from wherever
    its own default prior put it. The covariance ceiling cannot see that
    at all: nav2_amcl's untouched prior carries the same 0.25 m2 the
    bringup's seed does.

    SO THE CHECK IS AGAINST THE SEED AND NOT AGAINST ZERO. The bringup
    told the localiser where it was; this asks whether the answer that
    came back is anywhere near what it was told, with the truck standing
    where it was spawned and nothing having commanded it. It is the only
    check on this stack that can tell a localiser which HEARD the
    bringup from one which did not.

    Returns the distance when it passes, so the caller can print what it
    measured rather than only that it checked.
    """
    off = math.hypot(float(x) - float(ref_x), float(y) - float(ref_y))
    if not math.isfinite(off):
        raise EvidenceError(
            "{} published a finite pose, and it read ({!r}, {!r})".format(
                what, x, y))
    if off > float(tolerance_m):
        raise EvidenceError(
            "{} answered within {:g} m of the pose it was seeded with, "
            "and it did not: it reports ({:.4f}, {:.4f}) against a seed "
            "of ({:.4f}, {:.4f}), which is {:.4f} m away. With the truck "
            "standing where it was spawned that is not a correction - it "
            "is a localiser that never received the seed and is "
            "answering from its own prior.".format(
                what, float(tolerance_m), float(x), float(y),
                float(ref_x), float(ref_y), off))
    return off


# WHICH ESTIMATOR PUBLISHES WHERE, AS A GRAMMAR OVER THE ARM LABEL.
#
# F2 Task 4 put a SECOND estimator on this track and the two do not
# publish on the same address: robot_localization's ekf_node writes
# topics.odometry_filtered and fuse's fixed-lag smoother writes
# topics.fuse_odometry_filtered (config.yaml argues why it is not one
# address wearing two meanings). So every instrument that reads a FUSED
# estimate has to know which arm is up before it can subscribe: the
# bringup gate tools/ekf_health.py and the recorder in
# tools/sensor_evidence.py both do, and this is the one place either of
# them asks.
#
# THE LABEL IS PARSED AND NOT LOOKED UP. `m5v3.sh` writes
# `[<estimator>:]<channels>` - `wheel+imu`, `wheel+imu+rf2o`,
# `fuse:wheel+imu` - where the part before the colon names the ESTIMATOR
# and its absence means robot_localization, and the part after names the
# CHANNELS. A table keyed by whole labels would map a future
# `fuse:wheel+imu+rf2o` onto the EKF's topic on its first bringup,
# silently, and the symptom would be a recorded session with an empty
# fused stream under a label naming the estimator that did not fill it.
#
# AND AN ESTIMATOR IT HAS NEVER HEARD OF IS A REFUSAL, NOT A DEFAULT.
# The whole of this track's labelling chain exists because an unlabelled
# run does not look like a failure - it looks like a row - and a `.get()`
# with a fallback here would put that failure back one layer down, where
# no refusal can see it. tests/test_fuse_arm.py locks it.
_FUSED_TOPIC_KEYS = {
    # no colon: robot_localization's ekf_node, with or without the rf2o
    # arm's third sensor. Both are the SAME filter on the same address,
    # which is why EVIDENCE_FUSION.md 10 needed no change here.
    "": "topics.odometry_filtered",
    "fuse": "topics.fuse_odometry_filtered",
}


def estimator_of(arm):
    """The estimator half of an arm label: the part before the first
    colon, or "" when there is none.
    """
    arm = str(arm).strip()
    if ":" not in arm:
        return ""
    return arm.split(":", 1)[0].strip()


def fused_topic_key(arm):
    """The dotted config.yaml key naming the topic THIS arm's fused
    estimate comes out on.

    Returns a key rather than a topic because this file reads no
    config.yaml - the caller has the loaded config and this has the
    mapping, which is the same split every other function here is under.
    """
    text = str(arm).strip()
    if not text:
        raise EvidenceError(
            "the running stack says which ESTIMATOR ARM it is on, and it "
            "said nothing. m5v3.sh writes an `arm=` line on every bringup; "
            "an empty one is a truncated write, and this mapping will not "
            "guess a topic from it - a fused stream read off the wrong "
            "arm's address is EMPTY, not wrong, and an empty stream under "
            "a label is the failure the whole arm chain exists to "
            "prevent.")
    estimator = estimator_of(text)
    if ":" in text and not text.split(":", 1)[1].strip():
        raise EvidenceError(
            "the arm label {!r} names its channels as well as its "
            "estimator, and it does not. The grammar is "
            "[<estimator>:]<channels>.".format(text))
    if estimator not in _FUSED_TOPIC_KEYS:
        known = ", ".join(
            repr(name) if name else "'' (robot_localization)"
            for name in sorted(_FUSED_TOPIC_KEYS))
        raise EvidenceError(
            "the estimator named by this arm label publishes somewhere "
            "this file knows about: {!r} names estimator {!r}, and the "
            "ones with an address here are {}. An arm added to m5v3.sh "
            "is an entry added here - defaulting to the shipping "
            "filter's topic would subscribe to a topic that arm does not "
            "publish on and read an empty stream.".format(
                text, estimator, known))
    return _FUSED_TOPIC_KEYS[estimator]


# ----------------------------------------------------------------------
# WHICH LOCALISER, AS A GRAMMAR OVER THE `loc=` LABEL
# ----------------------------------------------------------------------
#
# F3 TASK 3 PUT A SECOND LOCALISER ON THIS TRACK AND IT IS
# fused_topic_key()'s PROBLEM ONE LAYER UP. `m5v3.sh` writes
# `<localiser>@<md5>` or the word `none`, and the two arms differ in two
# things a downstream instrument cannot guess:
#
#   WHERE EACH ONE PUBLISHES ITS OWN POSE. nav2_amcl advertises
#   `amcl_pose`; slam_toolbox's localisation node advertises `pose`. A
#   recorder that subscribed to the other arm's address would not fail -
#   it would record an EMPTY stream under a label naming a localiser that
#   was publishing all along.
#
#   WHICH ARTIFACT THE md5 IN THE LABEL NAMES. AMCL localises in the
#   GRID, whose md5 the committed registration carries; slam_toolbox
#   localises in the POSE GRAPH, whose md5 is in the build manifest
#   beside it. They are two files out of one build, and the label binds
#   each arm to the one it actually opened (F3 constraint 16).
#
# AND A LOCALISER THIS FILE HAS NEVER HEARD OF IS A REFUSAL RATHER THAN A
# DEFAULT, for fused_topic_key()'s reason exactly: a `.get()` with a
# fallback here would put the failure one layer down, where no refusal
# can see it. An arm added to m5v3.sh is an entry added to both tables.
_LOC_POSE_TOPIC_KEYS = {
    "amcl": "topics.amcl_pose",
    "slam": "topics.slam_pose",
}
#: Which frozen artifact the md5 half of each arm's label is taken from.
#: `grid` is the .pgm, hashed by the committed registration's `map_md5`;
#: `posegraph` is the .posegraph, hashed by build.txt's own line. The
#: VALUES are names this file owns and the CALLER turns into a file - the
#: same split every other function here is under: no path lives in this
#: module.
_LOC_MD5_ARTIFACTS = {
    "amcl": "grid",
    "slam": "posegraph",
}
#: HOW EACH ARM IS TOLD WHERE IT STARTS, and it is a third table for the
#: same reason the two above are tables: it is a property of the
#: LOCALISER, the bringup gate has to know it, and getting it wrong is
#: silent both ways.
#:   `message`  nav2_amcl. It publishes on its pose topic when the
#:              particle filter resamples OR when a publication is
#:              FORCED, and what forces one is an initial pose - so with
#:              the truck standing at spawn there is exactly one message
#:              per seed, and the gate must subscribe BEFORE it seeds or
#:              it will wait for a second that never comes.
#:   `parameter` slam_toolbox's localisation node. `map_start_pose` is
#:              read on the configure transition, before the gate exists.
#:              That node DOES subscribe to the same initial-pose topic -
#:              it is how a running localiser is re-placed - and THAT IS
#:              EXACTLY WHY THE GATE MUST NOT PUBLISH ONE HERE: seeding
#:              it would move the localiser to the pose the gate already
#:              believes, and the gate's own pose-against-seed check
#:              would then be a check on the gate. On this arm the check
#:              is whether `map_start_pose` arrived at all.
_LOC_SEED_MECHANISMS = {
    "amcl": "message",
    "slam": "parameter",
}
#: WHAT THE BRINGUP GATE CAN ACTUALLY READ ON EACH ARM, WITH THE TRUCK
#: STANDING AT ITS SPAWN POSE - and this one is a MEASUREMENT rather than
#: a preference (EVIDENCE_LOCALIZATION_V3.md 13.2).
#:   `pose`  nav2_amcl. It publishes on its pose topic when the filter
#:           resamples or when a publication is forced, and the seed
#:           forces one - so there is exactly one message to read, it
#:           carries a covariance, and BOTH checks can run on it.
#:   `edge`  slam_toolbox's localisation node. Its pose topic is
#:           TRAVEL-GATED: `minimum_travel_distance` is 0.25 m and
#:           nothing has commanded the vehicle, so it publishes NOTHING
#:           at rest - measured on this rig, 30 s of subscription with
#:           the node ACTIVE, the graph deserialised and the sensor
#:           registered. What it does publish from the moment it
#:           activates is `map` -> `odom`, on a 50 Hz timer. So the gate
#:           reads THE EDGE there: composed onto the estimator's
#:           `odom` -> `base_link`, that is map -> base_link, which is
#:           what a consumer of this stack reads anyway.
#:           THE COST IS THE COVARIANCE CHECK, and it is stated rather
#:           than papered over: a transform carries no covariance, so on
#:           that arm only the pose-against-seed bound runs and the gate
#:           SAYS SO. (That node's pose topic does carry a real
#:           covariance once the truck moves - 0.033 m2 on the diagonal,
#:           measured - which is why this is about WHEN it publishes and
#:           not about what it publishes.)
_LOC_GATE_SOURCES = {
    "amcl": "pose",
    "slam": "edge",
}


def localizer_of(label):
    """The localiser half of a `loc=` label: the part before the `@`.

    The grammar is `<localiser>@<artifact md5>` or the word `none`, and
    it is PARSED rather than looked up so that a rebuilt map - which
    changes the md5 and nothing else - does not need a table entry.
    An empty string means "no absolute layer", which is a value.
    """
    text = str(label).strip()
    if not text or text == "none":
        return ""
    return text.split("@", 1)[0].strip()


def loc_md5_of(label):
    """The artifact-md5 half of a `loc=` label: after the `@`, or ""."""
    text = str(label).strip()
    if "@" not in text:
        return ""
    return text.split("@", 1)[1].strip()


def _loc_lookup(table, localizer, what):
    name = str(localizer).strip()
    if not name:
        raise EvidenceError(
            "the session or the running stack says which LOCALISER it is "
            "on, and it said nothing. m5v3.sh writes a `loc=` line on "
            "every bringup - `none` or `<localiser>@<md5>` - and this "
            "mapping will not guess {} from an empty one.".format(what))
    if name not in table:
        raise EvidenceError(
            "the localiser named by this loc= label has {} this file "
            "knows about: {!r} is not one of {}. An arm added to m5v3.sh "
            "is an entry added here - defaulting to the other arm's "
            "answer would read an empty stream, or score a session "
            "against an artifact it never opened.".format(
                what, name, ", ".join(repr(k) for k in sorted(table))))
    return table[name]


def loc_pose_topic_key(localizer):
    """The dotted config.yaml key naming the topic THIS localiser
    publishes its own pose on.

    Returns a KEY rather than a topic because this file reads no
    config.yaml - the caller has the loaded config and this has the
    mapping, which is fused_topic_key()'s split exactly.
    """
    return _loc_lookup(_LOC_POSE_TOPIC_KEYS, localizer, "a pose topic")


def loc_md5_artifact(localizer):
    """Which frozen artifact the md5 in THIS localiser's label is of:
    `grid` (the .pgm, hashed by the registration) or `posegraph` (hashed
    by the build manifest).
    """
    return _loc_lookup(_LOC_MD5_ARTIFACTS, localizer, "an artifact")


def loc_seed_mechanism(localizer):
    """How THIS localiser is told where it starts: `message` (published
    on topics.initialpose by the bringup gate) or `parameter` (read off
    its own command line on the configure transition).
    """
    return _loc_lookup(_LOC_SEED_MECHANISMS, localizer, "a seed mechanism")


def loc_gate_source(localizer):
    """What the bringup gate reads on THIS arm with the truck at rest:
    `pose` (the localiser's own pose topic, covariance included) or
    `edge` (`map` -> `odom` off /tf, composed onto the estimator's
    `odom` -> `base_link`).
    """
    return _loc_lookup(_LOC_GATE_SOURCES, localizer, "a gate source")


def stack_log_dir(state, fallback):
    """Where the RUNNING stack's per-child logs are, off its state file.

    F4's CLOSING WAVE, AND IT EXISTS SO THAT A REFUSAL CAN NAME A FILE
    THAT IS STILL THERE. Every bringup used to truncate the previous
    one's logs; since the wave each gets `<log_dir>/run-<stamp>/` and
    `m5v3.sh` records the path in its state file. A tool that printed
    the ROOT would send a reader to a file the next bringup had already
    replaced - which is exactly what happened to the two `error_code
    205` runs EVIDENCE_NAV_V3.md 17.3 and 17.4 had to decode from
    streams instead of quoting.

    `state` is `parse_state_file`'s dict. A state file written before
    the wave carries no `log_dir=` line and this answers `fallback`,
    which is where that stack's logs really are - `loc=none`'s rule
    again: a missing line is an older script and not a value.
    """
    return state.get("log_dir") or fallback


def parse_state_file(text):
    """m5v3.sh's `key=value` state file, as a dict.

    THE SAME GRAMMAR TWO INSTRUMENTS ALREADY READ BY HAND. `m5v3.sh
    start` writes paths.traction_file whole on every bringup - the
    traction, the arm, the partition, the timestamp - and `status`,
    tools/sensor_evidence.py's `record` and tools/ekf_health.py all read
    it. It is here so the PARSE is one thing that a test can reach; the
    REFUSALS stay with each caller, because what a missing key means
    differs: a recorder without an arm may not record, and a gate without
    one may not gate.
      A VALUE MAY CONTAIN '=' AND arm_source DOES. The split is on the
      first one only.
    """
    fields = collections.OrderedDict()
    for line in str(text).splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key] = value
    return fields


def travel_projection(xs, ys, yaws):
    """How far the vehicle went NOSE-FIRST: metres, and the sign is the
    reading.

    THE FORKLIFT DRIVES BACKWARDS AND THAT IS NOT A FIGURE OF SPEECH.
    `forklift_ver3` travels forks-trailing: model yaw 0 points the forks
    at world -x, the travel heading is yaw + pi, and every profile in
    config.yaml's `drive_route:` is driven at a NEGATIVE tread speed
    (m6/ipc/follower.py carries the same convention for the fleet). So on
    this vehicle the HEADING and the COURSE are a half-turn apart, and an
    along-track error split on the heading comes out with its sign
    reversed - an estimate that ran 0.48 m long reads -0.48 and the
    reader is told it ran short.

    IT IS MEASURED AND NOT ASSUMED. Nothing here knows about forklifts:
    each step of the path is projected onto the heading the vehicle
    HAD when it took that step, and the projections are summed. A run
    driven nose-first returns a positive number close to its path
    length; this truck's runs return the path length NEGATED. A vehicle
    that never moved returns exactly zero and track_error_of() then falls
    back on the nose, because the split of a stationary truck's error is
    arbitrary whichever way it is taken.

    THE PROJECTION IS PER STEP AND NOT ON THE NET DISPLACEMENT, which is
    the whole reason it works on `square`: that profile ends where it
    started, so its net displacement is nothing at all while every one of
    its four sides was driven forks-trailing.
    """
    xs = [float(v) for v in xs]
    ys = [float(v) for v in ys]
    yaws = [float(v) for v in yaws]
    if not (len(xs) == len(ys) == len(yaws)):
        raise EvidenceError(
            "the path and the headings are the same length, got "
            "{}, {} and {}".format(len(xs), len(ys), len(yaws)))
    total = 0.0
    for i in range(1, len(xs)):
        total += ((xs[i] - xs[i - 1]) * math.cos(yaws[i - 1])
                  + (ys[i] - ys[i - 1]) * math.sin(yaws[i - 1]))
    return total


def track_error(dx, dy, heading_rad):
    """A position error split into ALONG-track and CROSS-track.

    WHY A MAGNITUDE IS NOT ENOUGH, AND F2 TASK 2 IS WHY IT IS HERE. An
    end error of 0.60 m says nothing about WHICH of the two things went
    wrong, and under slip the two go wrong for different reasons and
    have different cures: the wheel odometry lies about DISTANCE (the
    tyre creeps, so a revolution buys less ground than the estimator
    believes) and it lies about HEADING (the corner scrubs). Projected
    onto the direction the vehicle was actually facing they come apart:

        along = +e . u(psi)      the estimate ran LONG (+) or SHORT (-)
        cross = +e . u(psi+pi/2) the estimate is LEFT (+) or RIGHT (-)

    THE HEADING IS THE GROUND TRUTH's AND NEVER THE ESTIMATE's. The
    question is where the estimate is relative to where the truck REALLY
    went, so the frame has to be the truck's; taking it from the estimate
    would rotate the split by exactly the heading error being measured
    and mix the two components back together - which is the failure this
    function exists to avoid.

    IT IS A ROTATION AND NOTHING ELSE, so hypot(along, cross) is the same
    end error the caller already has. Nothing is normalised, clamped or
    fitted here.
    """
    dx = float(dx)
    dy = float(dy)
    c = math.cos(float(heading_rad))
    s = math.sin(float(heading_rad))
    return TrackError(along=c * dx + s * dy, cross=-s * dx + c * dy)


def track_error_of(drift):
    """One Drift's end error, split along the direction the vehicle was
    actually TRAVELLING at the end of the window.

    THE COURSE AND NOT THE HEADING. travel_projection() says which way
    this run was driven relative to the nose; on `forklift_ver3` that is
    forks-trailing on every profile, so the axis the error is split along
    is the heading turned by pi. It is ONE function because two callers
    ask - the printed per-estimate line and compare_drift's two columns -
    and a track split that disagreed with itself between the two would be
    the worst kind of duplicate: both halves plausible, one of them
    backwards.
    """
    heading = float(drift.truth_end_yaw_rad)
    if float(drift.truth_nose_forward_m) < 0.0:
        heading += math.pi
    return track_error(drift.end_dx, drift.end_dy, heading)


def score_drift(truth_rows, est_rows, frame, max_gap_s):
    """The estimate against the ground truth, over a whole drive.

    Both arguments are sequences of (t, x, y, yaw): the truth in WORLD
    coordinates as the plant publishes it, the estimate in its own odom
    frame as the node publishes it. The frame is what makes them
    comparable and nothing else here touches coordinates.

    max_gap_s HAS NO DEFAULT, and that is the point of it. It is
    resample()'s bound - how far the estimate may be reached across
    before a gap in it is a refusal rather than a straight line - so it
    decides which recordings are scoreable at all, and a caller that
    took a default would be scoring against a number written in this
    file instead of the one in config.yaml (evidence.analyse.
    max_pair_gap_s, 0.5 s, which is 250 estimate samples on this rig).
    resample() below already requires it; this function used to carry a
    1.0 that silently disagreed with the only caller that mattered.

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
        est_turned_rad=ryaw[-1] - ryaw[0],
        # THE DIRECTION THE TRUCK WAS ACTUALLY FACING WHEN THE WINDOW
        # CLOSED, carried so the end error can be split along it without
        # a second pass over the CSVs. It is the TRUTH's heading and it
        # is the unwrapped one - cos and sin do not care, and a wrapped
        # copy would be one more number to keep in step with tyaw.
        truth_end_yaw_rad=tyaw[last],
        # AND WHICH WAY THE TRUCK WAS FACING RELATIVE TO WHERE IT WENT,
        # over the same paired window and off the TRUTH alone. See
        # travel_projection(): on this vehicle it comes out NEGATIVE, and
        # an along-track error split without it reads backwards.
        truth_nose_forward_m=travel_projection(
            [tx[i] for i in keep], [ty[i] for i in keep],
            [tyaw[i] for i in keep]))


def _removed(before, after):
    """One figure, before against after.

    THE FRACTION IS NOT CLAMPED AND MUST NEVER BE. An estimate that is
    WORSE than the one it was built from is a result - it is the result
    F2's evidence file most needs to be able to state - and a fraction
    floored at zero would publish it as "no improvement", which is a
    different and flattering claim about the same measurement.

    A `before` of exactly zero has NO fraction, and nan is the honest
    answer rather than a division. There is no percentage of nothing:
    the absolute `removed` still says everything there is to say.
    """
    before = float(before)
    after = float(after)
    removed = abs(before) - abs(after)
    if abs(before) == 0.0:
        fraction = float("nan")
    else:
        fraction = removed / abs(before)
    return Removed(before=before, after=after, removed=removed,
                   fraction=fraction)


def compare_drift(raw, fused):
    """Two Drifts of the SAME RUN against the SAME TRUTH, subtracted.

    F2 Task 1's addition, and the question it exists for: the evidence
    file's headline is not how far out the filter is, it is HOW MUCH OF
    THE RAW ESTIMATE'S ERROR THE FILTER REMOVED - the corner yaw error
    above all, because that is the error a gyro observes and dead
    reckoning cannot. Both arguments come from score_drift(), so both are
    already absolute and already in the spawn frame; this only subtracts.

    THE TWO SCORES ARE NOT OVER THE SAME SAMPLES AND CANNOT BE. Each one
    clips the ground truth to its own estimate's span, and the two
    estimates do not start together: on this stack the wheel odometry
    publishes as soon as the joint channels do, and the EKF waits for a
    clock and for its first measurement of each sensor. So the two window
    edges are REPORTED - span_gap_start_s and span_gap_end_s, both
    magnitudes - rather than assumed to be small. An end error over a
    window that closed half a second early is an end error at a different
    place, and an rms over a shorter window is an rms over a different
    run; a reader who is shown the gaps can see whether either matters.

    NOTHING HERE PAIRS, RESAMPLES OR RE-SCORES. If the two Drifts came
    from different truths or different runs, this function will happily
    subtract them - it is arithmetic and has no way to know. The caller
    (tools/sensor_evidence.py) reads both out of ONE session directory,
    which is where that guarantee lives.
    """
    raw_track = track_error_of(raw)
    fused_track = track_error_of(fused)
    return Comparison(
        end_error=_removed(raw.end_error_m, fused.end_error_m),
        end_yaw=_removed(raw.end_yaw_error_rad, fused.end_yaw_error_rad),
        # F2 TASK 2's TWO COLUMNS, and each score is split along ITS OWN
        # window's truth heading rather than a shared one. The two
        # windows close at different sim times (see below), so the truck
        # is not pointing exactly the same way at the end of each, and
        # borrowing one heading for both would charge that difference to
        # the filter. On a straight profile the two headings agree to
        # milliradians and it makes no difference; on a corner it would.
        along=_removed(raw_track.along, fused_track.along),
        cross=_removed(raw_track.cross, fused_track.cross),
        rms=_removed(raw.rms_m, fused.rms_m),
        max_error=_removed(raw.max_error_m, fused.max_error_m),
        span_gap_start_s=abs(float(fused.t0) - float(raw.t0)),
        span_gap_end_s=abs(float(fused.t1) - float(raw.t1)))


# ----------------------------------------------------------------------
# the absolute pose: two transforms, composed, and carried to the world
# ----------------------------------------------------------------------

def compose_se2(parent, child):
    """`child` expressed in `parent`'s own parent frame.

    Both are (x, y, yaw). On this stack the call that matters is

        map -> base_link  =  (map -> odom)  o  (odom -> base_link)

    and the failure it exists to prevent is the one that LOOKS RIGHT:
    adding the two translations and adding the two yaws. That is this
    composition with the rotation left out, and it is EXACT whenever the
    parent's yaw is zero - which is what `map` -> `odom` is at bringup,
    on a stack whose odom frame has not drifted yet. So the wrong
    arithmetic agrees with the right one for the first few seconds of
    every run and then quietly stops.

    THE YAW IS WRAPPED, because these are composed thousands of times
    down a run and an unwrapped sum walks off the circle. Nothing here
    unwraps FOR the caller: a series that has to be differenced is
    unwrapped by the caller with unwrap(), which is where that decision
    already lives.
    """
    px, py, pyaw = (float(v) for v in parent)
    cx, cy, cyaw = (float(v) for v in child)
    c = math.cos(pyaw)
    s = math.sin(pyaw)
    return (px + c * cx - s * cy,
            py + s * cx + c * cy,
            normalise_angle(pyaw + cyaw))


def invert_se2(pose):
    """The transform that undoes `pose`. Exists so a composition can be
    round-tripped in a test rather than only read - SpawnFrame.unapply()
    is here for the same reason."""
    x, y, yaw = (float(v) for v in pose)
    c = math.cos(yaw)
    s = math.sin(yaw)
    return (-(c * x + s * y), -(-s * x + c * y), normalise_angle(-yaw))


def compose_rows(parent_rows, child_rows, max_gap_s):
    """Two stamped transform streams, composed on the CHILD's timeline.

    Both arguments are sequences of (t, x, y, yaw). On this stack the
    parent is `map` -> `odom` as the localiser broadcasts it - once per
    scan, 15 Hz - and the child is `odom` -> `base_link` as the filter
    publishes it, at 50 Hz. What comes out is `map` -> `base_link`: the
    answer a tf2 listener would have got, at the rate the vehicle's own
    motion is carried at.

    THE PARENT IS INTERPOLATED AND THAT IS NOT AN APPROXIMATION OF tf2 -
    IT IS WHAT tf2 DOES. A listener asking for a transform between two
    stamped messages gets a linear interpolation of the two, whatever
    the transform means; a zero-order hold would be a DIFFERENT answer
    from the one any consumer of this stack would receive, and the
    jitter figures this file is asked for are figures about what a
    consumer receives. tf_jumps() is where the STEPS are counted, on the
    parent's own samples, before any interpolation touches them.

    THE YAW IS UNWRAPPED BEFORE IT IS RESAMPLED. `map` -> `odom` on this
    vehicle passes through pi during a `square`, and interpolating a
    wrapped series between +3.13 and -3.13 sweeps the estimate the whole
    way round the circle over one 67 ms step.

    max_gap_s HAS NO DEFAULT, for score_drift()'s reason: it is
    resample()'s bound and it decides which recordings are scoreable at
    all. On this pair the gap that matters is the localiser's, and a
    localiser that stopped broadcasting for longer than that did not
    slow down - it stopped.

    CHILD SAMPLES OUTSIDE THE PARENT'S SPAN ARE DROPPED. map_server has a
    1712 x 1196 grid to read before the localiser can say anything, so
    the first stretch of every session has an odom pose and no map pose.
    Those samples are not scoreable and dropping them makes the run
    SHORTER rather than WRONG, which is score_drift()'s own rule one
    layer up.
    """
    parent_rows = list(parent_rows)
    child_rows = list(child_rows)
    if len(parent_rows) < 2:
        raise EvidenceError(
            "the localiser broadcast at least two transforms, got "
            "{}".format(len(parent_rows)))
    if len(child_rows) < 1:
        raise EvidenceError(
            "the filter published at least one pose, got 0")
    pt = [float(r[0]) for r in parent_rows]
    px = [float(r[1]) for r in parent_rows]
    py = [float(r[2]) for r in parent_rows]
    pyaw = unwrap([float(r[3]) for r in parent_rows])

    keep = [row for row in child_rows if pt[0] <= float(row[0]) <= pt[-1]]
    if not keep:
        raise EvidenceError(
            "the two transform streams overlap in time: the localiser "
            "spans [{:.3f}, {:.3f}] and the filter [{:.3f}, {:.3f}]".format(
                pt[0], pt[-1], float(child_rows[0][0]),
                float(child_rows[-1][0])))
    at = [float(row[0]) for row in keep]
    # A HOLE IN THE PARENT IS A REFUSAL AND resample() WILL NOT CATCH IT.
    # That function refuses a query outside the source's whole SPAN,
    # which is the right rule for a dense stream with ragged ends; it
    # says nothing about a hole in the middle, and a localiser that
    # stopped broadcasting for five seconds has one. Interpolated
    # across, that hole becomes a smooth ramp between two corrections -
    # a straight line drawn through the exact stretch of run where
    # nothing was known - and every jitter figure taken over it would be
    # a figure about this function.
    for lo, hi in zip(pt, pt[1:]):
        if hi - lo <= max_gap_s or hi < at[0] or lo > at[-1]:
            continue
        raise EvidenceError(
            "the localiser broadcast without a gap wider than {:g}s, and "
            "it did not: nothing between {:.3f} and {:.3f} ({:.3f}s). "
            "Interpolating that would draw a straight line through the "
            "stretch of the run where the absolute pose was "
            "unknown.".format(max_gap_s, lo, hi, hi - lo))
    rx = resample(pt, px, at, max_gap_s)
    ry = resample(pt, py, at, max_gap_s)
    ryaw = resample(pt, pyaw, at, max_gap_s)
    out = []
    for i, row in enumerate(keep):
        x, y, yaw = compose_se2((rx[i], ry[i], ryaw[i]),
                                (float(row[1]), float(row[2]),
                                 float(row[3])))
        out.append((at[i], x, y, yaw))
    return out


def rows_to_world(rows, frame):
    """A map-frame trajectory, carried into the BUILDING's own frame.

    THIS IS THE STEP THAT MAKES AN ABSOLUTE SCORE POSSIBLE AND IT IS THE
    ONE THAT CAN BE SILENTLY WRONG. The localiser reports where the
    vehicle is in a GRID; the ground truth says where it is in a
    BUILDING; the committed registration is the only thing that relates
    the two, and it was DERIVED (EVIDENCE_MAP_V3.md 6) rather than
    asserted. Nothing here is anchored, fitted or offset: the transform
    is the frozen one and the score that follows is the difference
    between two poses in one frame.

    AND WHAT THE TRANSFORM CANNOT DO IS THE POINT. It is RIGID. A grid
    whose metres are not the building's - warehouse_v3 has 0.265 deg of
    internal shear - cannot be made to fit by any rotation and
    translation, so a localiser that is PERFECT in that grid is wrong in
    the building by whatever the grid is wrong by. That error lands in
    the FIGURE, which is why the registration residual is stated beside
    every figure as the floor (MapFrame.floor()).
    """
    return [(float(row[0]),) + frame.to_world(row[1], row[2], row[3])
            for row in rows]


def point_to_segment(px, py, ax, ay, bx, by):
    """Distance from a point to a SEGMENT, not to its infinite line.

    THE DIFFERENCE IS THE WHOLE OF WHAT MAKES A PATH DEVIATION HONEST.
    A global path is a chain of short segments; measured against the
    LINES they lie on, a vehicle standing at the end of the path is
    zero from the line of every one of them and its deviation reads as
    nothing at all. The clamp to [0, 1] is what stops that.
    """
    ex, ey = float(bx) - float(ax), float(by) - float(ay)
    length2 = ex * ex + ey * ey
    if length2 <= 0.0:
        return math.hypot(float(px) - float(ax), float(py) - float(ay))
    t = ((float(px) - float(ax)) * ex + (float(py) - float(ay)) * ey) / length2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(float(px) - (float(ax) + t * ex),
                      float(py) - (float(ay) + t * ey))


def point_to_polyline(px, py, poly):
    """The shortest distance from a point to a polyline, in its units.

    WHAT IT IS FOR. It is the DEVIATION of where the vehicle actually
    went from the path a planner drew - the figure nav2 issue #5714
    reports Ackermann robots losing in turns, and the one an evidence
    file has to be able to state rather than describe.

    IT IS UNSIGNED, DELIBERATELY. A signed cross-track error needs a
    direction of travel to be signed AGAINST, and on a path with cusps
    in it that direction reverses - so the sign would flip in the middle
    of a reverse segment and a mean would cancel to nothing. What a
    corridor is sized on is a magnitude.

    AN EMPTY POLYLINE IS A REFUSAL AND NOT AN INFINITE DISTANCE. A path
    with no poses in it is a planner that returned nothing, which is a
    different fact from a vehicle that is far from its path.
    """
    points = [(float(x), float(y)) for x, y in poly]
    if not points:
        raise EvidenceError(
            "the path has at least one pose in it, and this one is "
            "empty. A planner that returned nothing is not a vehicle "
            "that is far from its path.")
    if len(points) == 1:
        return math.hypot(float(px) - points[0][0],
                          float(py) - points[0][1])
    return min(point_to_segment(px, py, a[0], a[1], b[0], b[1])
               for a, b in zip(points, points[1:]))


def polyline_length(poly):
    """The length of a polyline. Zero for fewer than two points."""
    points = [(float(x), float(y)) for x, y in poly]
    return math.fsum(math.hypot(b[0] - a[0], b[1] - a[1])
                     for a, b in zip(points, points[1:]))


def sign_changes(values, deadband=0.0):
    """How many times a series changes sign, ignoring a deadband.

    WHAT IT COUNTS ON THIS TRACK IS CUSPS. A Reeds-Shepp path reverses
    direction at a cusp, and the commanded linear velocity crosses zero
    with it. The deadband is what keeps the crossing itself from being
    counted several times: every ramp through zero passes through a
    dozen samples whose sign is arithmetic rather than intent, and
    config.yaml's navcmd.creep_speed_mps is the value below which the
    converter itself stops reading a command as a direction.
    """
    last = 0
    count = 0
    for value in values:
        current = 0
        if float(value) > abs(deadband):
            current = 1
        elif float(value) < -abs(deadband):
            current = -1
        if current == 0:
            continue
        if last != 0 and current != last:
            count += 1
        last = current
    return count


def tf_jumps(rows, tolerance=0.0):
    """Every CHANGE in a re-broadcast transform, as the correction it is.

    THE QUESTION THIS ANSWERS IS NOT "HOW ACCURATE" BUT "HOW SMOOTH", and
    it is the number a later phase's architecture decision turns on: an
    absolute localiser pays its debt in DISCONTINUITIES, because a
    particle filter's answer moves in steps and `map` -> `odom` moves
    with it. A controller reading map -> base_link sees those steps as
    the vehicle teleporting.

    A REPEAT IS NOT A CORRECTION. nav2_amcl re-sends `map` -> `odom` on
    EVERY scan whether or not the filter updated (laserReceived's
    latest_tf_valid_ branch), and it updates only after
    `update_min_d` of travel - so a 25 s run carries some 370 broadcasts
    and a few dozen actual corrections. Counting broadcasts would report
    a correction rate of 15 Hz and a mean correction of zero, which is
    the smoothest possible localiser and a complete fiction.

    `tolerance` IS 0.0 BY DEFAULT AND THAT IS THE HONEST SETTING. The
    recorder writes six decimals, so a genuine re-broadcast is EXACTLY
    equal and needs no epsilon; a tolerance above zero would be a
    threshold below which a jump is called a repeat, and that is a
    choice a reader has to be told about rather than a default.

    AN EMPTY STREAM IS A REFUSAL AND NEVER "NO JUMPS". A localiser that
    never broadcast at all is not a localiser that never corrected, and
    reporting the second about the first is the failure this whole file
    is written against. One sample is not a refusal - it is a stream
    with no PAIR in it - and it returns n = 0 with no statistics, which
    says the same thing without inventing a spread.
    """
    rows = list(rows)
    if not rows:
        raise EvidenceError(
            "the localiser broadcast at least one transform, and the "
            "stream is empty. A localiser that never broadcast is not a "
            "localiser that never corrected.")
    span = float(rows[-1][0]) - float(rows[0][0])
    if len(rows) < 2:
        return Jumps(n=0, samples=len(rows), span_s=span, dpos=None,
                     dyaw=None, max_dpos_m=None, max_dyaw_rad=None,
                     per_s=None)
    dpos = []
    dyaw = []
    for before, after in zip(rows, rows[1:]):
        step = math.hypot(float(after[1]) - float(before[1]),
                          float(after[2]) - float(before[2]))
        turn = abs(normalise_angle(float(after[3]) - float(before[3])))
        if step <= tolerance and turn <= tolerance:
            continue
        dpos.append(step)
        dyaw.append(turn)
    if not dpos:
        return Jumps(n=0, samples=len(rows), span_s=span, dpos=None,
                     dyaw=None, max_dpos_m=0.0, max_dyaw_rad=0.0,
                     per_s=0.0 if span > 0.0 else None)
    return Jumps(n=len(dpos), samples=len(rows), span_s=span,
                 dpos=summarise(dpos), dyaw=summarise(dyaw),
                 max_dpos_m=max(dpos), max_dyaw_rad=max(dyaw),
                 per_s=(len(dpos) / span) if span > 0.0 else None)


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


def scrub_split(t, x_rear, y_rear, yaw, steer, wheelbase_m, tread_mps):
    r"""A corner's missing yaw, charged to the contact patch that lost it.

    corner_fidelity() says HOW MUCH yaw went missing. This says WHERE,
    and the two candidates are not the same repair: a steered wheel that
    slides sideways is a tyre parameter on THAT wheel, a rear axle that
    slides sideways is a tyre parameter on the other two, and a plant
    that does both is neither on its own.

    THE IDENTITY IS EXACT AND IT IS NOT A FIT. Take the rear-axle
    midpoint P, body x forward, and write its ground velocity in body
    axes as (u, w) with yaw rate psidot. The steered contact stands L
    ahead of P, so its ground velocity is (u, w + psidot*L), and
    resolving that across the wheel plane at steer angle d gives the two
    slip velocities the tyres actually see:

        s_f = -u*sin(d) + (w + psidot*L)*cos(d)   across the steered wheel
        s_r = w                                    across the rear axle

    Rearranging for psidot - no assumption, just algebra -

        psidot = u*tan(d)/L  +  s_f/(L*cos(d))  -  s_r/L
                 \_________/    \____________/     \_____/
                  kinematic      front term         rear term

    so the deficit (kinematic - delivered) is exactly -front_term minus
    rear_term, and `front_share` and `rear_share` are those two as
    fractions of it. A plant whose rear axle holds reports a rear share
    near zero and a front share near one.

    `residual` is the identity's own closure - kinematic + front + rear
    minus the measured yaw rate - and it is reported rather than assumed.
    It is arithmetic, so it should be at the rounding of the inputs; a
    residual that is not is a bug in the reduction and not a finding
    about the vehicle.

    TWO SLIPS AT THE STEERED WHEEL, AND THE SECOND ONE IS NOT LATERAL.
    `front_along_mps` is the contact's speed ALONG its own wheel plane,
    which the tread speed is supposed to equal; `tread_slip` scores one
    against the other, and it is the corner's longitudinal slip at the
    driven contact - the same quantity tools/slip_bench.sh measures on a
    straight, measured where the wheel is steered. `front_slip_mps` is
    the magnitude of the two together and `front_slip_off_plane_rad` how
    far that slide sits off the wheel plane - zero is a patch sliding
    purely along its own tread, a quarter turn is one sliding purely
    sideways - because a contact patch does not know which of a
    reduction's axes it is sliding along.

    Every argument is a series on ONE clock, the ground truth's, with the
    steer reading already resampled onto it. x_rear and y_rear are the
    REAR AXLE's track (rear_axle_track() moves base_link onto it) because
    the identity above is written at P and nowhere else.
    """
    n = len(t)
    if not (n == len(x_rear) == len(y_rear) == len(yaw) == len(steer)):
        raise EvidenceError(
            "the corner trace has one position, one heading and one steer "
            "reading per stamp: {} stamps, {} x, {} y, {} yaw, {} steer"
            .format(n, len(x_rear), len(y_rear), len(yaw), len(steer)))
    if n < 3:
        raise EvidenceError(
            "a scrub split differences the track, so it needs at least "
            "three samples; got {}".format(n))
    wheelbase_m = float(wheelbase_m)
    if wheelbase_m <= 0.0:
        raise EvidenceError(
            "the wheelbase is positive, got {!r}".format(wheelbase_m))
    tread_mps = float(tread_mps)
    if tread_mps == 0.0:
        raise EvidenceError(
            "the longitudinal slip is scored against the commanded tread "
            "speed, which is zero on this window")

    us, ws, oms, sfs, alongs, kins, fronts, rears, deltas = (
        [], [], [], [], [], [], [], [], [])
    for i in range(1, n):
        dt = float(t[i]) - float(t[i - 1])
        if dt <= 0.0:
            raise EvidenceError(
                "the ground truth's stamps increase; sample {} is {:.6f}s "
                "after {:.6f}s".format(i, float(t[i]), float(t[i - 1])))
        vx = (float(x_rear[i]) - float(x_rear[i - 1])) / dt
        vy = (float(y_rear[i]) - float(y_rear[i - 1])) / dt
        om = (float(yaw[i]) - float(yaw[i - 1])) / dt
        psi = 0.5 * (float(yaw[i]) + float(yaw[i - 1]))
        delta = 0.5 * (float(steer[i]) + float(steer[i - 1]))
        if abs(math.cos(delta)) < 1e-9:
            raise EvidenceError(
                "the steer angle is inside a quarter turn; this window "
                "reads {:.6f} rad".format(delta))
        u = vx * math.cos(psi) + vy * math.sin(psi)
        w = -vx * math.sin(psi) + vy * math.cos(psi)
        s_f = -u * math.sin(delta) + (w + om * wheelbase_m) * math.cos(delta)
        along = u * math.cos(delta) + (w + om * wheelbase_m) * math.sin(delta)
        us.append(u)
        ws.append(w)
        oms.append(om)
        sfs.append(s_f)
        alongs.append(along)
        deltas.append(delta)
        kins.append(u * math.tan(delta) / wheelbase_m)
        fronts.append(s_f / (wheelbase_m * math.cos(delta)))
        rears.append(-w / wheelbase_m)

    u_m, w_m, om_m = mean(us), mean(ws), mean(oms)
    sf_m, along_m = mean(sfs), mean(alongs)
    kin_m, front_m, rear_m = mean(kins), mean(fronts), mean(rears)
    deficit = kin_m - om_m
    speed_m = math.hypot(u_m, w_m)
    return ScrubSplit(
        n=len(us), u_mps=u_m, rear_lat_mps=w_m, front_lat_mps=sf_m,
        front_along_mps=along_m,
        front_slip_mps=math.hypot(sf_m, tread_mps - along_m),
        front_slip_off_plane_rad=math.atan2(abs(sf_m),
                                            abs(tread_mps - along_m)),
        tread_slip=(tread_mps - along_m) / tread_mps,
        yaw_rate=om_m, kinematic=kin_m, front_term=front_m, rear_term=rear_m,
        deficit=deficit,
        front_share=(-front_m / deficit) if deficit else float("nan"),
        rear_share=(-rear_m / deficit) if deficit else float("nan"),
        front_slip_angle_rad=math.atan2(sf_m, abs(along_m)),
        rear_slip_angle_rad=(math.atan2(w_m, abs(u_m)) if speed_m > 0.0
                             else 0.0),
        residual=(kin_m + front_m + rear_m) - om_m)


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


def read_csv(path, allow_empty=False):
    """One headered CSV, as columns.

    AN EMPTY CAPTURE IS A REFUSAL AND NOT AN EMPTY TABLE. A stream that
    delivered a header and no rows would otherwise reach a statistic and
    come back as a plausible-looking zero.

    `allow_empty` IS FOR THE ONE CASE WHERE THE EMPTINESS IS THE
    MEASUREMENT, and it has exactly one caller. F4 Task 2.5's fail-fast
    is demonstrated on a goal inside a rack: the planner refuses it, so
    the controller publishes NOTHING and four of tools/drive_goal.py's
    nine streams are empty for the reason being demonstrated. That
    caller passes True for those four streams only, still requires the
    POSE streams (which come from the plant and the estimator and run
    whether or not anything is commanded), and then prints the run as a
    vehicle that never moved rather than as a table of zeros.
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
    if n == 0 and not allow_empty:
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
            # THE APERTURE, AND IT IS READ RATHER THAN ASSUMED FOR THE
            # SAME REASON THE SAMPLE COUNT IS. F3 Task 2 has to place
            # every beam of a recorded scan on the map, and the bearing
            # of beam i is angle_min + i * (max - min)/(samples - 1). On
            # THIS vehicle the window is not symmetric about the sensor's
            # own +x - a TiM571 is blind over 90 deg and the mount points
            # that blind sector ASTERN, so min_angle is +0.785 and
            # max_angle is +5.498 (model.sdf carries the whole argument).
            # A reader that assumed -half..+half would put every beam of
            # every scan a half turn from where it was taken.
            for edge in ("min", "max"):
                text = block.findtext("./scan/horizontal/{}_angle".format(
                    edge))
                if text is not None:
                    entry["angle_" + edge] = float(text)
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


def sdf_link_pose(path, name):
    """One <link>'s <pose> in its model frame, as six floats.

    WHY A LINK POSE IS A CONFIGURED FIGURE LIKE ANY OTHER. F2's stack has
    to publish base_link -> imu_link on /tf before robot_localization
    will fuse a single IMU sample, and a SHELL cannot read XML - so
    config.yaml carries a copy of imu_link's pose under
    vehicle.imu_mount, exactly as its sensors: block carries a copy of
    the update rates and for the same stated reason. This is what lets
    `analyse` diff the copy against the file that decides it, so the copy
    says when it has gone stale instead of quietly describing a mount
    that moved.

    A LINK WITH NO <pose> IS AT THE MODEL ORIGIN, which is SDF's own
    default and not a guess this function makes - forklift_ver3's
    base_link carries none for that reason. A pose that is present but is
    not six numbers is refused: SDF allows a shorter pose in some
    contexts and padding one here would invent a rotation.
    """
    from xml.etree import ElementTree

    if not os.path.isfile(path):
        raise EvidenceError("the model {} exists".format(path))
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise EvidenceError(
            "the model {} is well-formed XML: {}".format(path, exc))
    names = []
    for link in root.iter("link"):
        names.append(link.get("name"))
        if link.get("name") != name:
            continue
        text = link.findtext("pose")
        if text is None:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        parts = text.split()
        if len(parts) != 6:
            raise EvidenceError(
                "link {!r} in {} carries a six-number <pose>; it carries "
                "{} ({!r})".format(name, path, len(parts), text.strip()))
        return tuple(float(value) for value in parts)
    raise EvidenceError(
        "the model {} declares a link named {!r}; it declares {}".format(
            path, name, ", ".join(repr(n) for n in names)))


#: How many points a CYLINDER's rim is sampled at when its silhouette is
#: projected onto the floor. A box projects EXACTLY - eight corners, and
#: the hull of their projections IS the projection of the box - and a
#: cylinder does not, so its two rims are sampled. 64 points put the
#: worst chord error at r*(1 - cos(pi/64)) = 0.14 mm on this model's
#: largest cylinder (r = 0.12 m), which is a 350th of one 5 cm costmap
#: cell: below anything a costmap can represent.
CYLINDER_RIM_POINTS = 64


def _rotation(roll, pitch, yaw):
    """SDF's own Z-Y-X extrinsic rotation, as three rows.

    IT IS THE FULL 3x3 AND NOT A YAW, and that is not generality for its
    own sake: forklift_ver3's pallet camera is mounted `0 0.5235988
    3.1415927` - pitched 30 degrees down and turned end for end - and the
    FOOTPRINT of its housing is a different rectangle from the one a
    yaw-only reading would produce.
    """
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def _apply(rotation, translation, point):
    x, y, z = point
    return tuple(
        translation[i] + rotation[i][0] * x + rotation[i][1] * y
        + rotation[i][2] * z for i in range(3))


def _pose6(text, where):
    """A <pose> as six floats.

    Absent is SDF's own default of all zeros; a pose that is PRESENT and
    is not six numbers is REFUSED rather than padded, because padding one
    would invent a rotation. sdf_link_pose() above makes the same
    distinction for the same reason.
    """
    if text is None:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    parts = text.split()
    if len(parts) != 6:
        raise EvidenceError(
            "the <pose> on {} is six numbers; it is {} ({!r})".format(
                where, len(parts), text.strip()))
    return tuple(float(value) for value in parts)


def _primitive_points(geometry, where):
    """One <geometry>'s corner or rim points, in its own frame.

    A GEOMETRY THIS FUNCTION HAS NEVER HEARD OF IS A REFUSAL AND NOT A
    SKIP. Silently ignoring a <mesh> would return a footprint SMALLER
    than the vehicle, and a footprint that is too small looks exactly
    like a correct one from every angle a test or a costmap has - which
    is the one failure a collision polygon may not have.
    """
    box = geometry.find("box")
    if box is not None:
        size = box.findtext("size")
        parts = (size or "").split()
        if len(parts) != 3:
            raise EvidenceError(
                "the <box> on {} carries a three-number <size>; it "
                "carries {!r}".format(where, size))
        hx, hy, hz = (float(value) / 2.0 for value in parts)
        return [(sx * hx, sy * hy, sz * hz)
                for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)
                for sz in (-1.0, 1.0)]
    cylinder = geometry.find("cylinder")
    if cylinder is not None:
        radius = float(cylinder.findtext("radius"))
        half = float(cylinder.findtext("length")) / 2.0
        points = []
        for index in range(CYLINDER_RIM_POINTS):
            angle = 2.0 * math.pi * index / CYLINDER_RIM_POINTS
            cx, cy = radius * math.cos(angle), radius * math.sin(angle)
            points.append((cx, cy, -half))
            points.append((cx, cy, half))
        return points
    kinds = [child.tag for child in geometry]
    raise EvidenceError(
        "the <geometry> on {} is a <box> or a <cylinder>; it is {}. A "
        "geometry this function cannot project would have to be SKIPPED, "
        "and a footprint smaller than the vehicle looks exactly like a "
        "correct one".format(where, ", ".join(kinds) or "empty"))


def convex_hull(points):
    """The convex hull of a set of (x, y), counter-clockwise.

    Andrew's monotone chain, which is nine lines and no dependency. It is
    here rather than borrowed because a costmap footprint on this track
    is EVIDENCE: the polygon written into m5_ver3/nav2.yaml is checked
    against what this returns, off the model, by a test - so the hull has
    to be reachable from the Windows python the suite runs under.

    COLLINEAR POINTS ARE DROPPED (`<= 0.0` rather than `< 0.0`), because
    a footprint with three points on one edge is the same polygon written
    at greater length, and nav2 walks every vertex of it on every
    collision check.
    """
    pts = sorted(set((round(float(x), 9), round(float(y), 9))
                     for x, y in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return ((a[0] - o[0]) * (b[1] - o[1])
                - (a[1] - o[1]) * (b[0] - o[0]))

    lower = []
    for point in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def sdf_footprint(path, model=None):
    """THE VEHICLE'S OUTLINE ON THE FLOOR, COMPUTED OFF THE MODEL.

    Every <collision> and every <visual> of every <link>, carried through
    that link's own pose and its own, projected onto z = 0 and hulled.
    Returns the hull counter-clockwise as (x, y) in the MODEL's frame -
    which for forklift_ver3 is base_link's, because that link carries no
    <pose> at all.

    WHY THE VISUALS TOO, AND NOT THE COLLISIONS ALONE. A costmap
    footprint is not a physics body: it is the answer to "what floor does
    this machine occupy". forklift_ver3 models its mast RAILS, its four
    overhead-guard posts, the pallet camera's bracket and both fork tines
    as visuals where the physics only needs one box - and a rack face
    does not care which element of an SDF a piece of steel was written
    in. The collisions alone lose the camera bracket and the tines.

    WHY IT IS A POLYGON AND NOT A RADIUS. This vehicle's circumscribed
    circle is wider than half the 5.00 m pick aisle, so a radius model
    refuses that corridor outright; nav2's own footprint guide says the
    same thing for the same reason (docs/reports/m5v3-02 section 5).

    IT IS THE UNLADEN OUTLINE AND SAYS SO. A pallet on the tines is wider
    than the tines; nav2 documents republishing a LARGER footprint on
    ~/footprint when laden, and this track carries no load and makes no
    such claim.
    """
    from xml.etree import ElementTree

    if not os.path.isfile(path):
        raise EvidenceError("the model {} exists".format(path))
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise EvidenceError(
            "the model {} is well-formed XML: {}".format(path, exc))
    models = list(root.iter("model"))
    if not models:
        raise EvidenceError("the model {} declares a <model>".format(path))
    chosen = models[0]
    if model is not None:
        matching = [node for node in models if node.get("name") == model]
        if not matching:
            raise EvidenceError(
                "the model {} declares a <model> named {!r}; it declares "
                "{}".format(path, model,
                            ", ".join(repr(n.get("name")) for n in models)))
        chosen = matching[0]
    points = []
    for link in chosen.findall("link"):
        name = link.get("name")
        link_pose = _pose6(link.findtext("pose"), "link {!r}".format(name))
        link_rotation = _rotation(*link_pose[3:])
        for element in (list(link.findall("collision"))
                        + list(link.findall("visual"))):
            geometry = element.find("geometry")
            if geometry is None:
                continue
            where = "{}/{} {!r}".format(name, element.tag,
                                        element.get("name"))
            pose = _pose6(element.findtext("pose"), where)
            rotation = _rotation(*pose[3:])
            for point in _primitive_points(geometry, where):
                local = _apply(rotation, pose[:3], point)
                whole = _apply(link_rotation, link_pose[:3], local)
                points.append((whole[0], whole[1]))
    if not points:
        raise EvidenceError(
            "the model {} carries a <collision> or a <visual> with a "
            "<geometry>; it carries none".format(path))
    return convex_hull(points)


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
    # The gap bound is spelled here rather than defaulted, because the
    # function has no default - see score_drift's own docstring. 1.0 s is
    # generous against a synthetic trace sampled every 0.05 s: it is the
    # scorer being exercised, not the bound.
    score = score_drift(still, [(i * 0.05, 0.40, 0.0, 0.0)
                                for i in range(21)], frame, 1.0)
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

    # THE SAME IDEAL TRICYCLE, THROUGH THE SPLIT. A rear axle driven at
    # exactly u*tan(delta)/L slides nowhere, so both slip terms are zero
    # and the deficit is nothing to charge to either wheel.
    u, delta = 0.2114, -0.785398
    omega = u * math.tan(delta) / 1.05
    t, tx, ty, tyaw, tsteer = [], [], [], [], []
    for i in range(121):
        now, yaw = i * 0.05, omega * i * 0.05
        t.append(now)
        tx.append((u / omega) * math.sin(yaw))
        ty.append((u / omega) * (1.0 - math.cos(yaw)))
        tyaw.append(yaw)
        tsteer.append(delta)
    split = scrub_split(t, tx, ty, tyaw, tsteer, 1.05, 0.3)
    check("a kinematic corner charges nothing to either contact patch",
          abs(split.front_lat_mps) < 1e-6 and abs(split.rear_lat_mps) < 1e-6
          and abs(split.residual) < 1e-12)
    # AND THE CRABBING ONE, where the axle slides and the split has to
    # say so - it is the reading that decides which wheel gets tuned.
    tx = [x + (0.03 / omega) * (math.cos(a) - 1.0)
          for x, a in zip(tx, tyaw)]
    ty = [y + (0.03 / omega) * math.sin(a) for y, a in zip(ty, tyaw)]
    crab = scrub_split(t, tx, ty, tyaw, tsteer, 1.05, 0.3)
    check("an axle that crabs is charged to the rear and not the front",
          abs(crab.rear_lat_mps - 0.03) < 1e-6)

    check("a square that closes reads zero and an open leg reads its gap",
          closure([0.0, 1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0, 0.0])
          < 1e-12
          and abs(closure([0.0, 3.0], [0.0, 4.0]) - 5.0) < 1e-12)

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

    # F2's third stream: one estimate against another. The two checks are
    # the two ways a comparison can flatter a filter - clamping a
    # negative improvement to zero, and comparing a signed heading error
    # by its value rather than by its magnitude.
    def _d(end, yaw, rms_v, worst, t0=0.0, t1=40.0, dx=0.0, dy=0.0,
           truth_yaw=0.0, nose=10.0):
        return Drift(n=100, t0=t0, t1=t1, end_dx=dx, end_dy=dy,
                     end_error_m=end, end_yaw_error_rad=yaw, rms_m=rms_v,
                     max_error_m=worst, truth_path_m=10.0, est_path_m=10.0,
                     truth_turned_rad=1.0, est_turned_rad=1.0,
                     truth_end_yaw_rad=truth_yaw, truth_nose_forward_m=nose)

    worse = compare_drift(_d(0.20, 0.1, 0.1, 0.3),
                          _d(0.50, 0.1, 0.1, 0.3))
    check("a filter that made the error worse reads a NEGATIVE fraction",
          worse.end_error.removed < 0.0
          and abs(worse.end_error.fraction + 1.5) < 1e-12)
    flipped = compare_drift(_d(1.0, -1.7326, 0.9, 1.8),
                            _d(1.0, +0.0156, 0.9, 1.8))
    check("a heading error is compared by magnitude and keeps its sign",
          flipped.end_yaw.before < 0.0 and flipped.end_yaw.after > 0.0
          and abs(flipped.end_yaw.removed - (1.7326 - 0.0156)) < 1e-12)
    late = compare_drift(_d(1.0, 0.1, 0.9, 1.8, t0=10.0, t1=50.0),
                         _d(1.0, 0.1, 0.9, 1.8, t0=10.6, t1=49.5))
    check("the two scores report how far apart their windows were",
          abs(late.span_gap_start_s - 0.6) < 1e-12
          and abs(late.span_gap_end_s - 0.5) < 1e-12)

    # F2 TASK 2's SPLIT. The slip scenario's whole claim is that the two
    # halves of one end error move for different reasons, so the two
    # checks here are the two ways the split can be got wrong: taking it
    # in the wrong frame, and letting the along-track column report an
    # improvement the filter did not make.
    split = track_error(0.60, 0.0, math.pi)
    check("the end error is split in the TRUTH's frame, so +x at yaw pi "
          "runs SHORT",
          abs(split.along + 0.60) < 1e-12 and abs(split.cross) < 1e-12)
    # AND THE ONE THAT COST A RE-CUT. This truck drives forks-trailing,
    # so the axis is the COURSE and not the nose - split on the nose the
    # sign of every along-track figure in EVIDENCE_FUSION.md 8 is wrong.
    # AND THE GUARD THAT EXISTS BECAUSE THE FILTER BLOWS UP SILENTLY.
    check("a broken filter is told apart from a drifting one by the bound "
          "and not by the reader",
          diverged_at([0.0, 1.0, -12.0], [0.0, 0.5, 3.0], 100.0) is None
          and diverged_at([0.0, -3.6e47], [0.0, 2.0e44], 100.0) == 1
          and diverged_at([0.0, float("nan")], [0.0, 0.0], 1e300) == 1)
    check("a forks-trailing run is split on its COURSE and not its nose",
          travel_projection([0.0, -1.0, -2.0], [0.0, 0.0, 0.0],
                            [0.0, 0.0, 0.0]) < 0.0
          and abs(track_error_of(
              _d(0.2, 0.0, 0.1, 0.2, dx=-0.2, nose=-2.0)).along - 0.2)
          < 1e-12)
    heading_only = compare_drift(
        _d(1.24, 0.30, 0.9, 1.8, dx=1.20, dy=0.30),
        _d(1.20, 0.02, 0.9, 1.8, dx=1.20, dy=0.05))
    check("a filter that fixes only the heading removes NOTHING "
          "along-track",
          abs(heading_only.along.removed) < 1e-12
          and abs(heading_only.cross.removed - 0.25) < 1e-12)

    # AND WHICH ESTIMATOR PUBLISHES WHERE - F2 Task 4. It is in the
    # OPERATOR's selftest and not only in pytest because the two callers
    # are a bringup gate and a recorder, both run on the rig, and the way
    # this can be wrong is that an instrument subscribes to a topic
    # nobody publishes on and reads an EMPTY stream.
    check("the rf2o arm reads the same fused topic as the default arm",
          fused_topic_key("wheel+imu")
          == fused_topic_key("wheel+imu+rf2o")
          == "topics.odometry_filtered")
    check("the fuse arm reads its own fused topic",
          fused_topic_key("fuse:wheel+imu")
          == "topics.fuse_odometry_filtered")
    try:
        fused_topic_key("ukf:wheel+imu")
    except EvidenceError as exc:
        check("an estimator with no address here is REFUSED, not "
              "defaulted to the shipping filter's topic",
              "ukf" in str(exc))
    else:
        check("an estimator with no address here is REFUSED, not "
              "defaulted to the shipping filter's topic", False)
    check("a state file's value may contain '=' and is not truncated",
          parse_state_file("arm=fuse:wheel+imu\nsource=a=b\n")["source"]
          == "a=b")

    # F3 TASK 2's THREE TRANSFORMS, AND THE HALF TURN THAT HIDES A SIGN
    # ERROR IN ALL OF THEM. warehouse_v3's registration is -179.813 deg
    # and this vehicle spawns at yaw pi, so a rotation applied the wrong
    # way round leaves every magnitude EXACTLY right and puts the answer
    # on the other side of the map. It is in the OPERATOR's selftest
    # because it is the one thing an absolute figure cannot survive.
    warehouse_v3 = MapFrame(-3.138328398, -17.111857467, 9.798692466,
                            0.029052, 0.117891)
    spawn_in_map = warehouse_v3.to_map(-17.0, 10.0, math.pi)
    check("the committed registration carries the spawn pose onto the "
          "map origin, which is what says it is not nonsense",
          math.hypot(spawn_in_map[0], spawn_in_map[1]) < 0.30
          and abs(normalise_angle(spawn_in_map[2])) < 0.01)
    back = warehouse_v3.to_world(*spawn_in_map)
    check("the map transform round-trips at the half turn AND at a "
          "quarter, where a reversed rotation is visible",
          abs(back[0] + 17.0) < 1e-9 and abs(back[1] - 10.0) < 1e-9
          and MapFrame(math.pi / 2.0, 3.0, -4.0).to_map(2.0, 0.0)
          == (3.0, -2.0))
    check("map -> base_link is the PRODUCT of the two transforms and not "
          "the sum: a quarter-turn parent turns the child's translation",
          compose_se2((0.0, 0.0, math.pi / 2.0), (2.0, 0.0, 0.0))[1]
          == 2.0)
    # AND THE ONE THE JITTER FIGURE DEPENDS ON. amcl re-sends map -> odom
    # on every scan whether or not it corrected; counting the repeats
    # would report a 15 Hz correction rate and a mean jump of zero.
    repeats = [(0.1 * i, 1.0, 2.0, 0.3) for i in range(30)]
    check("a re-broadcast transform is not a correction",
          tf_jumps(repeats).n == 0 and tf_jumps(repeats).samples == 30)
    check("a correction is measured at its own size, the short way round "
          "the circle",
          abs(tf_jumps([(0.0, 0.0, 0.0, math.pi - 0.05),
                        (0.1, 0.0, 0.0, -math.pi + 0.05)]).max_dyaw_rad
              - 0.1) < 1e-9)

    # And the model's link poses, which is how config.yaml's copy of the
    # IMU mount is checked against the file that decides it.
    handle, path = tempfile.mkstemp(suffix="_link.sdf", text=True)
    os.close(handle)
    try:
        with open(path, "w", encoding="utf-8") as out:
            out.write('<sdf version="1.9"><model name="m">'
                      '<link name="base_link"/>'
                      '<link name="imu_link"><pose>-0.50 0 0.25 0 0 0</pose>'
                      '</link></model></sdf>')
        check("a link pose is read as six numbers out of the model",
              sdf_link_pose(path, "imu_link") == (-0.5, 0.0, 0.25,
                                                  0.0, 0.0, 0.0))
        check("a link with no pose sits at the model origin, per SDF",
              sdf_link_pose(path, "base_link") == (0.0,) * 6)
        try:
            sdf_link_pose(path, "no_such_link")
        except EvidenceError as exc:
            check("a link the model does not carry is refused by name",
                  "imu_link" in str(exc))
        else:
            check("a link the model does not carry is refused by name",
                  False)
    finally:
        os.remove(path)

    # ---- F3 TASK 3's FOUR LOCALISER TABLES, ON THE RIG ----
    #
    # tests/test_localizer_arms.py is the real suite; these are the
    # checks an operator standing in front of a stack that will not come
    # up needs, and they are the ones a wrong answer is silent about: a
    # recorder that subscribed to the other arm's pose topic writes an
    # EMPTY stream under a label naming a localiser that was publishing
    # all along, and a gate that seeded the wrong arm would be checking
    # itself.
    check("the two localisers do not publish their pose at one address",
          loc_pose_topic_key("amcl") == "topics.amcl_pose"
          and loc_pose_topic_key("slam") == "topics.slam_pose")
    check("each arm's label md5 names the artifact THAT arm opens",
          loc_md5_artifact("amcl") == "grid"
          and loc_md5_artifact("slam") == "posegraph")
    check("only the arm seeded by MESSAGE may be sent one",
          loc_seed_mechanism("amcl") == "message"
          and loc_seed_mechanism("slam") == "parameter")
    check("the arm seeded by parameter is gated on the EDGE, not a pose",
          loc_gate_source("slam") == "edge"
          and loc_gate_source("amcl") == "pose")
    for _table in (loc_pose_topic_key, loc_md5_artifact, loc_seed_mechanism,
                   loc_gate_source):
        try:
            _table("cartographer")
        except EvidenceError:
            check("a localiser this file has never heard of is REFUSED "
                  "by {}".format(_table.__name__), True)
        else:
            check("a localiser this file has never heard of is REFUSED "
                  "by {}".format(_table.__name__), False)
    check("36 zeros are an ABSENT covariance and not a certain one",
          covariance_absent_in([0.0] * 36) is True
          and covariance_absent_in([0.0] * 35 + [0.5]) is False)

    # F4 TASK 2's FOUR, AND EACH IS IN THE OPERATOR's SELFTEST BECAUSE
    # THE THING THAT CONSUMES IT RUNS ON THE RIG.
    #   THE FOOTPRINT IS THE COSTMAP's COLLISION POLYGON, and a hull
    #   computed off collisions alone loses both fork tines - they are
    #   VISUALS on this model - which is a footprint 1.0 m short at the
    #   fork end that looks exactly like a correct one from every angle.
    _model = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "gazebo", "forklift_ver3", "model.sdf")
    if os.path.isfile(_model):
        _hull = sdf_footprint(_model)
        check("the footprint reaches the FORK TIPS at x = -1.875, which "
              "are VISUALS and would be lost by a collision-only hull",
              abs(min(x for x, _ in _hull) + 1.875) < 1e-9)
        check("the footprint reaches the COUNTERWEIGHT at x = +0.860 and "
              "the scanner corners at y = +-0.559",
              abs(max(x for x, _ in _hull) - 0.860) < 1e-9
              and abs(max(y for _, y in _hull) - 0.558994949) < 1e-6)
        check("the hull is CONVEX and has no collinear filler in it",
              len(_hull) == 8)
    #   THE DEVIATION FROM A PLAN IS TO THE SEGMENTS AND NOT TO THEIR
    #   LINES. A vehicle standing at the end of a path is zero from the
    #   LINE of every segment, so a line distance would report a
    #   perfectly tracked path for a truck that stopped a metre early.
    check("a path deviation is measured to the SEGMENT and not to the "
          "line it lies on",
          point_to_polyline(3.0, 0.0, [(0.0, 0.0), (1.0, 0.0)]) == 2.0)
    check("r is +1 on a series against itself",
          abs(correlation([1.0, 2.0, 5.0], [1.0, 2.0, 5.0]) - 1.0) < 1e-12)
    check("r is -1 on a series against its own negative",
          abs(correlation([1.0, 2.0, 5.0], [-1.0, -2.0, -5.0]) + 1.0) < 1e-12)
    check("a FLAT series has no correlation rather than a zero one",
          correlation([2.0, 2.0, 2.0], [1.0, 2.0, 3.0]) is None)
    check("one sample is not a correlation",
          correlation([1.0], [1.0]) is None)
    check("a cusp is a SIGN CHANGE above the creep deadband, and a ramp "
          "through zero is not several of them",
          sign_changes([-0.7, -0.3, -0.001, 0.0, 0.002, 0.3, 0.7],
                       0.005) == 1)

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
