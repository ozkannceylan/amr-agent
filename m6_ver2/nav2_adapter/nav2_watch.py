#!/usr/bin/env python3
"""nav2_watch.py - is this leg still getting closer, and if not, what
does the operator get told?

    python3 m6_ver2/nav2_adapter/nav2_watch.py --selftest

NO ROS IN THIS FILE. It is a rule, a ruler and a table; the shell feeds
it the believed POSE on every tick and hands the resulting note to
nav2_state.block().

THE RULE IS ONE AND THE RULER IS PER LEG (defect D16). "Still getting
closer" is one question, but what CLOSER means is not the same on every
class this adapter drives: a manoeuvre is a goal in front of the truck
and a ring chain is forty metres of corridor that turns away from its
own end before it comes back. Feeding the second one the first one's
ruler cancelled four consecutive orders in run18-c8-session-c while the
truck drove them correctly at 0.30 m/s. So a leg is dispatched with a
`ClosingMetric` and the watch carries it - and because a distance on the
wire that does not say what it is a distance OF is not a WHY, the note
names the ruler whenever it is not the ordinary one.

THE QUESTION nav2's OWN PROGRESS CHECKER CANNOT ASK.
`nav2_controller::SimpleProgressChecker` is satisfied by
`required_movement_radius` of MOVEMENT inside `movement_time_allowance`,
and a vehicle that has driven past its goal and is orbiting it satisfies
that completely - it moves 0.30 m every second. The failure m5v3's F4
Task 2 measured is 130.199 m driven and 459 plans published for a goal
2.910 m away, and no amount of tightening a movement test reaches it,
because the vehicle was moving the whole time. This asks about the GOAL.

This is a PORT of drive_goal.ClosingWatch, not a re-derivation: the two
answer identically over the same samples and
tests/test_nav2_adapter_watch.py pins that against the original. What is
new here is only the second half of the file - the notes.

THE NOTE IS THE WIRE'S ONLY WHY. `/auto/state.note` is the single field
that says what stopped the truck, and vda_agent quotes it verbatim into
a VDA `pathBlocked` errorDescription that a dispatcher reads. So each
note NAMES ITS INSTRUMENT: the watchdog says it was the watchdog and
what its numbers were; a nav2 abort says which SERVER refused and prints
the code, because the code is the only thing that distinguishes "the
planner will not start from here" from "the controller ran out of
patience", and those are different jobs for whoever goes and looks.

THE WIRE NOTE AND THE LOG LINE ARE DIFFERENT THINGS ON PURPOSE. The
note is contract - its bytes are pinned - so it carries the number and
not a name that upstream nav2 could re-spell. `describe_error` is for
the adapter's own per-child log, where an operator wants the word.
"""
import argparse
import collections
import math
import sys

import _donors                                            # noqa: F401

import nav2_path


class Nav2WatchError(ValueError):
    """A sample or an error code this file will not guess at."""


#: Where a leg stopped closing on its goal, and what the distance was
#: there. `t` is the plant's clock; `distance` is straight-line metres
#: from the BELIEVED pose to the goal - the pose the goal checker sees,
#: not the ground truth, because a watchdog that fired on a truth the
#: stack cannot see would be reporting the localiser instead.
#: The field names are drive_goal.Stalled's, pinned by test.
Stalled = collections.namedtuple("Stalled", "t distance mark since_s")

#: nav2's own error-code numbering, as this repository states it.
#: `ComputePathToPose` numbers from 200 and `FollowPath` from 100, so a
#: 2xx is the PLANNER and never the controller (drive_goal prints
#: exactly this legend when a plan is refused).
PLANNER_CODES = range(200, 300)
CONTROLLER_CODES = range(100, 200)

#: The names this repository has written down beside these numbers - the
#: 2xx in drive_goal's operator legend, the 1xx in SPEC_ADAPTER.md's
#: BLOCKED table. Nothing here is remembered from upstream: a code whose
#: name is not in one of those two files is printed as a bare number.
ERROR_CODE_NAMES = {
    203: "START_OUTSIDE_MAP",
    205: "START_OCCUPIED",
    206: "GOAL_OCCUPIED",
    208: "NO_VALID_PATH",
    101: "INVALID_CONTROLLER",
    102: "TF_ERROR",
    103: "INVALID_PATH",
    104: "PATIENCE_EXCEEDED",
    105: "FAILED_TO_MAKE_PROGRESS",
    106: "NO_VALID_CONTROL",
    107: "CONTROLLER_TIMED_OUT",
}

#: THE NOTE FOR A CHAIN THIS ADAPTER COULD NOT BUILD A PATH FOR
#: (SPEC_ADAPTER.md AMENDMENTS 9). It is a BLOCKED and not a warning
#: because the two things that produce it are permanent: a corner too
#: tight to round at the truck's own turning radius, and a reversal in
#: the middle of a granted polyline. Re-sending the same route would
#: refuse the same way for ever, so the fleet is told once and gets to
#: requeue the order somewhere else.
#:   THE ARITHMETIC IS IN THE LOG AND NOT ON THE WIRE, which is this
#: file's own rule: `/auto/state.note` is one sentence an operator reads
#: at a glance and the numbers that produced it are on the adapter's own
#: line at the same instant (nav2_adapter_node._send_chain).
CHAIN_REFUSED_NOTE = ("blocked: the granted polyline cannot be driven as "
                      "a path - see the adapter log for which corner")


#: ONE WAY OF ASKING "HOW FAR IS THIS LEG FROM DONE", with its name on
#: it. `of` takes an (x, y) BELIEF and returns metres; `name` is what
#: the adapter's log calls the number and what METRIC_PHRASE looks up
#: when the note has to say which ruler produced it.
ClosingMetric = collections.namedtuple("ClosingMetric", "name of")

#: WHAT EACH RULER IS CALLED IN A NOTE, AND WHY ONE OF THEM IS SILENT.
#: `/auto/state.note` is byte-pinned contract quoted verbatim into a VDA
#: pathBlocked errorDescription, so the ordinary case - a straight line
#: to a goal - keeps the sentence it has always had. A chain's number is
#: measured along forty metres of path and means something else
#: entirely, so it says so. A ruler this table does not know cannot
#: produce a note at all: an operator reading a distance has to know
#: what it is a distance OF.
METRIC_PHRASE = {"dist": "", "remain": " along the chain"}


def straight_metric(end_xy):
    """The ruler every NavigateToPose leg closes on: the line to its end.

    IT IS THE LEG'S END AND NOT ITS GOAL (D13). The message aims
    ARRIVE_BIAS_M past the station point; the leg still ENDS on the
    point, and every distance the adapter and the fleet measure is to
    that.
    """
    end = (float(end_xy[0]), float(end_xy[1]))
    return ClosingMetric(name="dist", of=lambda xy: math.dist(xy, end))


def chain_metric(poses):
    """The ruler a RING_CHAIN closes on: what is LEFT of its own path.

    DEFECT D16, MEASURED (run18-c8-session-c, 2026-09-02). A chain
    turns away from its own end by construction - the S1 -> S4 grant
    leaves the bay NORTHWARD up the spur while S4's spur foot is fifteen
    metres SOUTH - so the straight line to that end grew from 15.69 m to
    20.93 m over the first third of a leg the truck was driving
    perfectly at 0.30 m/s, with the fleet's own node counter advancing
    10 -> 9 -> 8 underneath. The watchdog called it a stall and
    cancelled four consecutive orders.
      The rule was never wrong. It was handed a ruler that does not
    measure this shape of leg, so the leg now carries its own: project
    the belief onto the path that was sent and read the arclength to the
    end of it. On the same thirty seconds this falls 43.90 -> 36.63 m
    without one step the wrong way.

    THE TABLE IS PREPARED ONCE, HERE. The shell asks this twenty times a
    second against four hundred poses and the cumulative arclength does
    not change while the leg runs.
    """
    tail = nav2_path.cumulative_from_end(poses)
    if len(tail) < 2:
        raise nav2_path.Nav2PathError(
            "a chain of {} pose(s) is not a path, and a leg cannot be "
            "watched for closing along one".format(len(tail)))
    return ClosingMetric(
        name="remain",
        of=lambda xy: nav2_path.remaining_along(xy, poses, tail_m=tail))


class ClosingWatch(object):
    """Is this leg still getting CLOSER to its goal?

    THE RULE IS A FAILURE TO IMPROVE RATHER THAN A SPEED. A MARK is
    kept: the smallest distance the leg has earned. Whenever the vehicle
    beats the mark by at least `required_closing_m` the mark moves and
    the clock restarts. If `allowance_s` passes without the mark moving,
    the leg has stopped closing and `step` returns the verdict.

    WHY THE MARGIN AND NOT ANY IMPROVEMENT AT ALL. A vehicle creeping in
    at a millimetre a second improves on its mark for ever, and a rule
    that reset on that would never fire on the one case it exists for.

    AND WHY A LOCALISATION JUMP CANNOT PROVOKE IT. A `map` -> `odom`
    correction that moves the belief AWAY from the goal is not an
    improvement, so it neither moves the mark nor counts as progress;
    one that moves the belief TOWARD it makes the rule more lenient.
    Either way a jump can only DELAY this guard.

    IT COMMANDS NOTHING AND IT IS NOT A SAFETY FUNCTION. What it
    produces is a verdict; cancelling the goal and latching BLOCKED is
    the caller's, and the PLC keeps the last word on all of it.

    BOTH NUMBERS COME FROM CONFIG AND NEITHER HAS A DEFAULT HERE. They
    are a property of the floor and the vehicle (m5v3 runs 0.50 m in
    30 s), and a default in a library is a number that gets used by
    accident and then measured as if it had been chosen.

    THE RULE IS ONE AND THE RULER IS PER LEG (D16). `step` is the rule
    and it is a port of drive_goal's, pinned sample for sample against
    it; `metric` is the thing that turns a believed POSE into the
    number `step` is fed, and a chain's is not a manoeuvre's. It is
    optional so that the rule stays constructible from two numbers -
    which is what the port test needs - and `measure` refuses BY NAME
    rather than guessing when a shell forgets to hand one over.
    """

    def __init__(self, required_closing_m, allowance_s, metric=None):
        self.required_closing_m = float(required_closing_m)
        self.allowance_s = float(allowance_s)
        self.metric = metric
        if not (math.isfinite(self.required_closing_m)
                and self.required_closing_m > 0.0):
            raise Nav2WatchError(
                "required_closing_m must be a positive distance, got "
                "{!r}: a margin of zero makes the rule fire on a "
                "millimetre and never on an orbit"
                .format(required_closing_m))
        if not (math.isfinite(self.allowance_s) and self.allowance_s > 0.0):
            raise Nav2WatchError(
                "allowance_s must be a positive time, got {!r}"
                .format(allowance_s))
        self.mark = None
        self.t_mark = None

    def measure(self, xy):
        """This leg's own ruler, read at a believed position."""
        if self.metric is None:
            raise Nav2WatchError(
                "this watch has no ruler: a leg is dispatched with the "
                "metric it closes on (nav2_watch.straight_metric for a "
                "manoeuvre, nav2_watch.chain_metric for a ring chain) "
                "and measuring without one would be a verdict about a "
                "number nobody chose")
        return float(self.metric.of(xy))

    def observe(self, t, xy):
        """`(distance, verdict)` - the ruler read and the rule stepped.

        ONE DOOR FOR THE SHELL, so the number the watchdog judged is the
        same number the adapter's log prints on the same tick. Two calls
        would be two readings of a belief that moves between them.
        """
        distance = self.measure(xy)
        return distance, self.step(t, distance)

    def step(self, t, distance):
        """None while it is still closing; a `Stalled` when it is not."""
        try:
            t = float(t)
            distance = float(distance)
        except (TypeError, ValueError):
            raise Nav2WatchError(
                "the watchdog was stepped with t={!r}, distance={!r}"
                .format(t, distance))
        if not (math.isfinite(t) and math.isfinite(distance)):
            raise Nav2WatchError(
                "the watchdog was stepped with a non-finite sample "
                "(t={!r}, distance={!r}): a verdict about progress "
                "measured off a broken belief is worse than no verdict"
                .format(t, distance))
        beaten = (self.mark is None
                  or distance <= self.mark - self.required_closing_m)
        if beaten:
            self.mark = distance
            self.t_mark = t
            return None
        since = t - self.t_mark
        if since > self.allowance_s:
            return Stalled(t=t, distance=distance, mark=self.mark,
                           since_s=since)
        return None


def no_progress_at(samples, required_closing_m, allowance_s):
    """`ClosingWatch` run over a whole recording, or None.

    ONE IMPLEMENTATION AND TWO ENTRY POINTS - the shell steps the watch
    live off the composed pose, and this runs it over a session already
    on disk. Two copies of a rule drift exactly the way two copies of a
    value do.
    """
    watch = ClosingWatch(required_closing_m, allowance_s)
    for t, distance in samples:
        verdict = watch.step(t, distance)
        if verdict is not None:
            return verdict
    return None


# ------------------------------ the notes ------------------------------

def blocked_note_no_progress(stalled, metric=None):
    """The adapter's own watchdog fired. It names itself and its numbers.

    AND SINCE D16 IT NAMES THE RULER TOO, when the ruler is not the
    ordinary one. "best 36.64 m" measured along a forty-metre chain and
    "best 36.64 m" measured across a room are different facts about a
    truck, and the note is the only place a dispatcher ever sees either.
    A straight line is the ordinary case and its bytes do not move.
    """
    if metric is None:
        phrase = METRIC_PHRASE["dist"]
    elif metric.name in METRIC_PHRASE:
        phrase = METRIC_PHRASE[metric.name]
    else:
        raise Nav2WatchError(
            "the watchdog was measuring with a {!r} ruler, which this "
            "file has no sentence for. A distance on the wire that does "
            "not say what it is a distance OF is not a WHY"
            .format(metric.name))
    return ("blocked: no progress - best {:.2f} m{}, {:.0f} s without "
            "closing".format(stalled.mark, phrase, stalled.since_s))


def blocked_note_for_error(error_code):
    """A nav2 ABORTED, as the sentence an operator reads.

    THREE ROWS, AND THE THIRD IS NOT A FALLBACK SO MUCH AS AN ADMISSION.
    A note is the wire's only WHY, so a code from a family this table
    does not know - a behaviour server's, a smoother's, or a -1 from a
    result that carried none - may not produce an EMPTY note. It gets
    the number, which is the thing that can be looked up.
    """
    try:
        code = int(error_code)
    except (TypeError, ValueError):
        raise Nav2WatchError(
            "the action result's error_code is {!r}, which is not a "
            "number. nav2 numbers these per server (FollowPath from "
            "100, ComputePathToPose from 200) and the adapter has "
            "nothing to tell the operator without one."
            .format(error_code))
    if code in PLANNER_CODES:
        return "blocked: planner refused (error_code {})".format(code)
    if code in CONTROLLER_CODES:
        return "blocked: controller gave up (error_code {})".format(code)
    return "blocked: nav2 refused (error_code {})".format(code)


def arrival_is_short(distance_m, arrive_m, margin_m):
    """Is nav2's SUCCEEDED a MISS, or two beliefs at one boundary?

    D6, MEASURED (run4, 2026-09-02). nav2's `station_goal_checker` and
    the adapter's `arrive_m` are THE SAME NUMBER - 0.25 m - read off two
    different beliefs at two different instants: nav2 checks AMCL's map
    pose inside the controller loop, the adapter checks the composed
    estimate through the committed registration on its own 20 Hz tick.
    Three arrivals at S1 in one run came in at 0.2453, 0.2482 and
    0.2502 m, and the third - five tenths of a millimetre outside - made
    a completed pick an "arrived short", BLOCKED the task and put it
    back on the fleet's queue.

    THE MARGIN IS NOT A FUDGE AND IT IS NOT A NEW NUMBER. It is the
    committed registration's own residual against the building, which
    the transform states and every boot prints ("registration residual
    rms 0.0291 m, MAX 0.1179 m"): two beliefs of one truck cannot be
    asked to agree closer than the transform between their frames is
    known. A registration that states no residual buys no margin.

    AND THE VERDICT THIS EXISTS FOR IS UNTOUCHED. m5v3's S7 orbit is a
    stable 0.643-0.742 m ring round a station the truck can never reach,
    which is 1.7 times the widest this rule will ever accept.
    """
    try:
        margin = abs(float(margin_m))
    except (TypeError, ValueError):
        raise Nav2WatchError(
            "the arrival margin is {!r}, which is not a number. It is "
            "the committed registration's own residual and there is no "
            "default for it: a margin nobody measured is a tolerance "
            "nobody chose".format(margin_m))
    return float(distance_m) > float(arrive_m) + margin


def arrived_short_note(distance_m, arrive_m):
    """Nav2 said SUCCEEDED and the belief never entered `arrive_m`.

    DO NOT RE-SEND, AND THAT IS WHAT THIS NOTE IS FOR. A 0.4 m goal is
    inside this vehicle's own turning circle, and m5v3 measured what
    re-sending one produces: the S7 orbit, a stable 0.643-0.742 m ring
    round a station the truck can never reach. So the adapter reports
    the miss and stops, rather than driving a circle that looks like
    progress.
    """
    return "arrived short: {:.2f} m against arrive_m {:.2f}".format(
        float(distance_m), float(arrive_m))


def error_code_name(error_code):
    """The word this repository writes beside a code, or None."""
    try:
        return ERROR_CODE_NAMES.get(int(error_code))
    except (TypeError, ValueError):
        raise Nav2WatchError(
            "{!r} is not an error code".format(error_code))


def describe_error(error_code):
    """"205 START_OCCUPIED", for the adapter's own log line.

    NOT THE WIRE. The note is contract and carries the number alone; a
    name that upstream nav2 re-spells one release later would break a
    byte-pinned string. The log is where the operator wants the word.
    """
    code = int(error_code)
    name = ERROR_CODE_NAMES.get(code)
    return "{} {}".format(code, name) if name else str(code)


def _selftest():
    """Checks that need no simulator, no ROS and no network.

    tests/test_nav2_adapter_watch.py is the real suite - it runs this
    rule and drive_goal's side by side over the same samples, which this
    cannot do without an import - and this is the version an operator
    can run on the rig without pytest.
    """
    fails = []
    ran = []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    watch = ClosingWatch(0.50, 30.0)
    check("a leg that keeps closing is never stalled",
          all(watch.step(t * 5.0, d) is None
              for t, d in enumerate([20.0, 15.0, 10.0, 5.0, 1.0])))

    orbit = [(float(t), 2.910 + 0.05 * math.sin(t)) for t in range(0, 60)]
    verdict = no_progress_at(orbit, 0.50, 30.0)
    check("the 2.910 m orbit IS caught (best {:.2f} m, {:.0f} s)".format(
              verdict.mark, verdict.since_s) if verdict else
          "the 2.910 m orbit IS caught", verdict is not None)

    creep = [(float(t), 5.0 - 0.001 * t) for t in range(0, 60)]
    check("a millimetre a second does not reset the clock",
          no_progress_at(creep, 0.50, 30.0) is not None)

    jump = ClosingWatch(0.50, 10.0)
    jump.step(0.0, 10.0)
    check("a localisation jump AWAY from the goal cannot provoke it",
          jump.step(1.0, 40.0) is None and jump.step(2.0, 9.0) is None
          and jump.mark == 9.0)

    check("the no-progress note names the instrument and the numbers",
          blocked_note_no_progress(
              Stalled(41.0, 2.93, 2.91, 30.4))
          == "blocked: no progress - best 2.91 m, 30 s without closing")

    # D16: ONE RULE, TWO RULERS, AND THE TRUCK IS DRIVING PERFECTLY.
    # This corridor is run-18's chain in miniature: it leaves NORTH for
    # an end that lies SOUTH, and the walk is forty seconds at the
    # vehicle's own 0.30 m/s envelope, on the corridor the whole way.
    away = [(0.0, 0.0), (0.0, 20.0), (20.0, 20.0), (20.0, -20.0)]
    straight = straight_metric((20.0, -20.0))
    along = chain_metric(away)
    walk = [(float(t), (0.0, 0.30 * t)) for t in range(0, 41)]
    check("the straight ruler KILLS a leg driven correctly at 0.30 m/s",
          no_progress_at([(t, straight.of(xy)) for t, xy in walk],
                         0.50, 30.0) is not None)
    check("and the chain's own ruler does not",
          no_progress_at([(t, along.of(xy)) for t, xy in walk],
                         0.50, 30.0) is None)
    check("the chain ruler reads the whole path at its head and nothing "
          "at its end",
          abs(along.of((0.0, 0.0)) - 80.0) < 1e-9
          and abs(along.of((20.0, -20.0))) < 1e-9)
    check("a watch measures and steps in one call",
          ClosingWatch(0.50, 30.0,
                       metric=straight_metric((0.0, 0.0))).observe(
              0.0, (3.0, 4.0)) == (5.0, None))
    check("the note says WHICH ruler when it is not the ordinary one",
          blocked_note_no_progress(Stalled(41.0, 36.70, 36.64, 30.4),
                                   along)
          == "blocked: no progress - best 36.64 m along the chain, "
             "30 s without closing"
          and blocked_note_no_progress(Stalled(41.0, 2.93, 2.91, 30.4),
                                       straight)
          == "blocked: no progress - best 2.91 m, 30 s without closing")
    check("a 2xx is the PLANNER, and 205 is the costmap under the "
          "footprint",
          blocked_note_for_error(205)
          == "blocked: planner refused (error_code 205)")
    check("a 1xx is the CONTROLLER",
          blocked_note_for_error(106)
          == "blocked: controller gave up (error_code 106)")
    check("a code from neither family still gets a WHY",
          "701" in blocked_note_for_error(701))
    check("arrived-short states both radii",
          arrived_short_note(0.41, 0.25)
          == "arrived short: 0.41 m against arrive_m 0.25")
    check("the log line carries the word and the wire does not",
          describe_error(205) == "205 START_OCCUPIED"
          and describe_error(999) == "999"
          and "START_OCCUPIED" not in blocked_note_for_error(205))

    for bad, what in ((lambda: ClosingWatch(0.50, 30.0).step(0.0, math.nan),
                       "a non-finite distance"),
                      (lambda: blocked_note_for_error("ABORTED"),
                       "an error code that is not a number"),
                      (lambda: ClosingWatch(0.0, 30.0),
                       "a zero closing margin")):
        try:
            bad()
            check("{} is refused by name".format(what), False)
        except Nav2WatchError:
            check("{} is refused by name".format(what), True)

    check("two beliefs half a millimetre apart at one 0.25 m boundary "
          "are not a miss (D6)",
          not arrival_is_short(0.2502, 0.25, 0.1179)
          and not arrival_is_short(0.3679, 0.25, 0.1179))
    check("and m5v3's 0.643 m S7 orbit still is",
          arrival_is_short(0.643, 0.25, 0.1179)
          and arrival_is_short(float("inf"), 0.25, 0.1179))
    check("a registration that states no residual buys no margin",
          arrival_is_short(0.2502, 0.25, 0.0))

    for name in ran:
        print("{}  {}".format("FAIL" if name in fails else "pass", name))
    print("{}/{} checks passed".format(len(ran) - len(fails), len(ran)))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="the no-progress watchdog and the BLOCKED notes for "
                    "m6_ver2's nav2 adapter. The node that uses it is "
                    "nav2_adapter_node.py.")
    parser.add_argument("--selftest", action="store_true",
                        help="run the no-ROS, no-simulator checks and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("this file is a library; --selftest is the only thing "
                 "it does on its own")


if __name__ == "__main__":
    sys.exit(main())
