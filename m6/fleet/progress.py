"""progress.py - has this truck advanced, and for how long has it not.

PURE ARITHMETIC ON POSITIONS THE FLEET ALREADY HAS. Every vehicle
publishes its pose in every state message and the manager has stored it
since M6.3; until M6.7 nothing ever asked whether it CHANGED. Measured
2026-08-23: f2 and f3 showed ASSIGNED_LEG2 for 245 s at a standstill and
the status document listed them as ordinary trucks executing orders,
because that is exactly what the fleet believed.

NO OPINION ABOUT WHY. This file will call a truck not-advancing whether
it is jammed, parked, out of fuel or waiting politely for floor that
belongs to somebody else. Deciding which of those is a FAULT belongs to
fleet_manager, which is the only thing that knows what the ledger is
doing - and its first rule is that a truck the floor is holding is
behaving perfectly and is never called stalled.

AN ANCHOR, NOT A TRAIL. What is kept per vehicle is one position and the
time it was reached: the last place the truck actually got to. A truck
that shuffles half a metre back and forth for a minute never leaves its
anchor and is correctly called stalled, which a "distance travelled
since" measure would miss entirely - and shuffling is exactly what a
truck sawing at a guard band does.
"""
import math

# More than odometry noise, less than any real move. At the creep
# ceiling (0.30 m/s) a truck covers this in 1.7 s.
PROGRESS_M = 0.50
# A truck that has not made half a metre in thirty seconds is not
# driving. A leg on this floor is up to 60.65 m; nothing legitimate is
# this slow.
PROGRESS_S = 30.0
# Three windows before the task is taken away. A stall is usually
# somebody else's truck moving, and this is how long it is given to.
STALL_GIVE_UP_S = 90.0


class Progress:
    """Where each truck last got to, and when."""

    def __init__(self, progress_m=PROGRESS_M, window_s=PROGRESS_S):
        self._progress_m = float(progress_m)
        self._window_s = float(window_s)
        self._anchor = {}          # serial -> ((x, y), t)

    def note(self, serial, xy, now):
        """Record a position. The anchor moves only on real progress."""
        point = (float(xy[0]), float(xy[1]))
        anchor = self._anchor.get(serial)
        if anchor is None or math.dist(anchor[0], point) >= self._progress_m:
            self._anchor[serial] = (point, float(now))

    def stalled_for(self, serial, now):
        """Seconds since this truck last advanced, or None.

        None means BOTH "it is moving" and "we have never heard of it",
        and the caller wants the same thing in both cases: leave it
        alone. A vehicle with no anchor has published no position, and a
        fleet that acted on that would be acting on silence.
        """
        anchor = self._anchor.get(serial)
        if anchor is None:
            return None
        held = float(now) - anchor[1]
        return held if held >= self._window_s else None

    def forget(self, serial):
        """Drop a truck's anchor, so its next position starts it clean.

        Called when a truck stops being the watchdog's business - it lost
        its task, or the FLOOR is holding it. Without this a truck that
        waited two minutes for a corridor would be given up on the
        instant the corridor drained, which is the opposite of what the
        wait was for.
        """
        self._anchor.pop(serial, None)
