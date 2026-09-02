#!/usr/bin/env python3
"""nav2_watch.py - is this leg still getting closer, and if not, what
does the operator get told?

    python3 m6_ver2/nav2_adapter/nav2_watch.py --selftest

NO ROS IN THIS FILE. It is a rule and a table; the shell feeds it the
believed distance on every tick and hands the resulting note to
nav2_state.block().

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
    104: "PATIENCE_EXCEEDED",
    105: "FAILED_TO_MAKE_PROGRESS",
    106: "NO_VALID_CONTROL",
}


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
    """

    def __init__(self, required_closing_m, allowance_s):
        self.required_closing_m = float(required_closing_m)
        self.allowance_s = float(allowance_s)
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

def blocked_note_no_progress(stalled):
    """The adapter's own watchdog fired. It names itself and its numbers."""
    return ("blocked: no progress - best {:.2f} m, {:.0f} s without "
            "closing".format(stalled.mark, stalled.since_s))


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
