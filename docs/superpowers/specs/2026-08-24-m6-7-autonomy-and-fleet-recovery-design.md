# M6.7 — a truck that can get itself out, and a fleet that notices when it cannot

    date:     2026-08-24
    scope:    m6/ only.
    owner:    approved 2026-08-23 (local avoidance + recovery; watchdog +
              honest latch accounting)
    follows:  M6.6, PROOF.md's M6.6 section

---

## 1. Why, and every reason is a measurement

The M6.6 run drove 404.4 m in 630 s with four trucks and finished four
transports. Three things it did are the whole of this spec.

**A truck that stops has no way back.** `nav_core.step` sets `HOLD` when
`follower.target_speed` returns zero and returns `(0.0, 0.0)`. There is
no next state. Measured 2026-08-23:

    f3  state HOLD  guard_min 1.4722 m  reversing True
    f2  state HOLD  guard_min 1.4846 m  reversing True

Motor was TRUE, every field was clear, and both trucks stood at their
station indefinitely. Nothing was broken — `GUARD_HOLD_M` is 1.500 and
the autopilot did exactly what it says. But its only move was to wait
for the world to change, and the world was a wall.

**The lidar's 360 rays become one number.** `follower.sector_min`
reduces the whole scan to the minimum range in a ±35° cone about the
direction of travel. The truck therefore knows *how close* something is
and nothing at all about *where*, so it cannot go round anything, ever.

**The fleet cannot tell a driving truck from a dead one.** f2 and f3
showed `ASSIGNED_LEG2` for 245 s at zero speed. The status document
listed them as ordinary trucks executing orders. The fleet receives
their position at 2 Hz throughout and never looks at whether it changes.

And one accounting defect that makes the rest hard to judge: the run
logged **15 auto-RESET recoveries**, and most of them are a scan that
arrived 28 ms late (worst gap 0.528 s against `field_eval`'s 0.500 s
rule), not a truck that hit anything. Counting those together makes the
number useless.

---

## 2. What is NOT in this

Nav2, AMCL/SLAM, RViz, and sharing blocked floor between vehicles
(`PROOF.md` residual 11). **Localisation stays on ground-truth
odometry.** One variable moves at a time or the next run's numbers
cannot be attributed to anything.

---

## 3. The vehicle

### 3.1 `m6/ipc/avoid.py` — new, pure, no ROS

Turns one `LaserScan`'s ranges into a **polar obstacle histogram** and
answers two questions. Nothing else. It has no memory, no map and no
clock: one scan in, one answer out, which is what makes it testable
against hand-written range arrays.

    buckets(ranges, angle_min, angle_inc, range_lo, range_hi, self_mask)
        -> tuple of (bearing_rad, nearest_m), BUCKET_RAD wide, over the
           whole 360 degrees. Invalid returns and SELF_MASK returns are
           dropped exactly as follower.sector_min drops them - the mask
           is imported from follower rather than restated.

    free_heading(buckets, want_rad, reach_m=FREE_M) -> float | None
        The bearing NEAREST `want_rad` whose vehicle-width window is
        clear to `reach_m`, or None when there is no such bearing within
        MAX_SWING_RAD.

**The window is the vehicle, not a constant.** A heading is only free if
everything the truck's width would sweep is free, so the half-width
checked at range `r` is `atan2(HALF_ENVELOPE_M + WINDOW_MARGIN_M, r)`.
At the reach below that is about 18 degrees each side; at 5 m it is
about 8. A fixed angular window would be too wide near and too narrow
far, and being too narrow far is how a truck steers into a gap it does
not fit through.

    BUCKET_RAD       = 0.0873   # 5 deg. The nav lidar is 360 samples
                                # over 360 deg, so a bucket is 5 rays.
    HALF_ENVELOPE_M  = 0.52     # the plan envelope is 1.04 m wide
                                # (warehouse_ver3.sdf's header)
    WINDOW_MARGIN_M  = 0.15
    FREE_M           = 2.00     # GUARD_HOLD_M 1.50 + 0.50. A heading
                                # that clears by less than the hold band
                                # is a heading the guard stops on
                                # anyway, so offering it is a lie.
    MAX_SWING_RAD    = 1.047    # 60 deg off the pursuit's own heading.
                                # Further than that is not an avoidance,
                                # it is a re-route, and re-routing is
                                # the fleet's job and not this file's.

### 3.2 `nav_core` — HOLD stops being terminal

`HOLD` becomes the first of four states rather than the only one. Any of
them ends the moment the guard reads clear again; that check comes
first, so a truck never nudges its way out of a jam that had already
dissolved.

| state | what it does | leaves when |
|---|---|---|
| `HOLD` | full zero, exactly as today | guard clears, or `HOLD_PATIENCE_S` |
| `AVOID` | steers to `free_heading` at `GUARD_SLOW_MPS`, bounded by `MAX_SWING_RAD` | guard clears, or no free heading |
| `NUDGE` | reverses `NUDGE_M` along the route, steer zero | the move completes |
| `BLOCKED` | full zero, and the note names the bearing and range | guard clears, or a new goal |

    HOLD_PATIENCE_S = 5.0   # a truck at the creep ceiling covers 1.5 m
                            # in this, so an obstacle that is another
                            # vehicle has passed. Waiting is the right
                            # first move and it costs nothing.
    NUDGE_M         = 0.40  # most of one envelope half-width: enough to
                            # change the geometry, short enough to stay
                            # on the corridor. 1.6 s at REVERSE_MPS.
    NUDGE_MAX       = 2     # then BLOCKED. A truck that has backed off
                            # twice and still cannot see a way out is
                            # not going to find one on the third.

**AVOID and NUDGE are not the same mechanism and both are needed.**
Tonight's stall had no obstacle to go round — the truck was reversing
out of a gap and the wall *was* the gap. `free_heading` returns None
there and always will. What clears it is changing the geometry: pull
forward, re-align, try again. Equally, a pallet dropped in an aisle is
something to go round and no amount of nudging helps. The two failures
are different and the escalation covers both in the cheap-first order.

**HOW TIME ENTERS A FILE THAT HAD NO CLOCK.** `nav_core` has never
known what time it is; it is called at 10 Hz and that was enough.
`HOLD_PATIENCE_S` and the nudge need a duration, so `step()` takes
`now=None` and `nav_node` passes `time.monotonic()`. With `now` absent
the escalation is disabled entirely and `HOLD` behaves as it does today
— which is what keeps every existing test meaningful without rewriting
it. A tick COUNT was the alternative and is worse: it silently means
something different the moment the node's rate changes, and this rig's
rate is exactly the thing that moves.

**`step()` grows two defaulted arguments** — `buckets=None` and
`now=None` — and with both absent the file behaves exactly as it does
today. That is the same
convention `field_min_m=math.inf` already set, and it is what keeps
every existing caller and every existing test honest.

**No `follower` constant moves.** `GUARD_HOLD_M`, `GUARD_SLOW_M`,
`FIELD_SLOW_M`, `CRUISE_MPS` and the bands are measured numbers; this
work adds a behaviour on top of them and changes none of them.

### 3.3 `nav_node` — wiring only

`cb_scan` already holds the raw ranges long enough to compute two sector
minima. It computes the buckets in the same callback and hands them to
`step()`. One extra pass over 360 numbers at 10 Hz.

---

## 4. The fleet

### 4.1 `m6/fleet/progress.py` — new, pure

    Progress(progress_m=PROGRESS_M, window_s=PROGRESS_S)
      .note(serial, xy, now)          record where a truck is
      .stalled_for(serial, now)       seconds since it last advanced,
                                      or None if it has

A vehicle has *advanced* when it has moved `PROGRESS_M` from the last
position that counted. Everything else is arithmetic on that.

    PROGRESS_M      = 0.50   # more than odometry noise, less than any
                             # real move. At the creep ceiling a truck
                             # covers this in 1.7 s.
    PROGRESS_S      = 30.0   # a truck that has not made half a metre in
                             # thirty seconds is not driving.
    STALL_GIVE_UP_S = 90.0   # three windows before the task is taken
                             # away. A stall is usually somebody else's
                             # truck moving; give it time to.

### 4.2 What the manager does with it

**A TRUCK HELD BY THE LEDGER IS NOT STALLED.** This is the rule the
whole thing turns on. A vehicle parked at the end of its released base
because the floor ahead belongs to somebody else is behaving perfectly,
and calling that a stall would put a name on the screen every time
traffic worked. So `floor.waiting_on(serial)` being set excludes a
vehicle from the watchdog entirely, as does having no executing order.

What is left is a truck the fleet believes is driving, that the floor is
not holding, and that is not moving. For that truck:

1. **It goes on the screen by name**, in the status document's traffic
   block beside `blocked` and `aside`, with how long it has been still
   and what its nav state was. This alone is the 245 s that nobody saw.
2. **At `STALL_GIVE_UP_S` its order is cancelled and its task requeued**
   — through `_abandon_order` and `requeue_to_head`, the same path the
   step-aside already uses, so the truck becomes eligible again and the
   transport is not lost.
3. **The give-up is counted per vehicle.** A truck that has been given
   up on twice stops being assigned until it reports a clean idle, which
   is the existing `not_eligible` mechanism and needs no new flag.

### 4.3 Latch accounting

`m6/windows/m6.py` already computes the three protective inputs every
cycle. It publishes one more derived number beside `fields_clear`: how
many of them were false. `scripted_writer` reads it at the moment Motor
drops and labels the press:

* **all three false → `recover(starvation)`.** No single body is in
  three fields at once from three different mount points; that is
  `field_eval` failing safe on scans that did not arrive.
* **one or two false → `recover(body)`.** A real protective demand.

The acceptance criterion counts `body` only. `starvation` is still
logged, still in PROOF, and still a rig problem rather than a floor one.

---

## 5. Files

**New**

    m6/ipc/avoid.py                     the histogram and the free heading
    m6/fleet/progress.py                the stall arithmetic
    m6/tests/test_avoid.py
    m6/tests/test_progress.py

**Changed**

    m6/ipc/nav_core.py                  the four-state escalation
    m6/ipc/nav_node.py                  compute buckets, pass them in
    m6/fleet/fleet_manager.py           watchdog wiring, status section
    m6/windows/m6.py                    the violated-PF count
    m6/tools/scripted_writer.py         classify the press
    m6/tools/score_run.py               report stalls beside distance
    m6/README_m6.md, m6/PROOF.md

`floor.py` is NOT in that list on purpose: `Floor.waiting_on` is
already public and the watchdog reads it as it stands.

**Untouched, and checked by `git status`:** `m6/ipc/follower.py`,
`m6/fleet/floor.py`,
`m6/ipc/field_eval.py`, `m6/gazebo/**`, `m6/ipc/stations.py`,
`m6/ipc/route.py`, and everything outside `m6/`.

---

## 6. Testing

The suite is 515 today and must be green with 0 skips at the end.

**`test_avoid.py`** — hand-written range arrays, no ROS:
* a clear scan offers the wanted heading itself
* a wall dead ahead and a gap 30 degrees left offers the gap
* a gap NARROWER than the vehicle window at that range is not offered
* nothing within `MAX_SWING_RAD` returns None
* `SELF_MASK` returns are dropped, so the truck's own mast is not a wall
* the answer is the same answer for the same input, every time

**`test_nav_core.py`** — the escalation as a table:
* guard clear at every state returns to `EN-ROUTE` immediately
* `HOLD` for less than `HOLD_PATIENCE_S` stays `HOLD` and commands zero
* a free heading at patience gives `AVOID` at the creep ceiling, and the
  steer is inside `MAX_SWING_RAD`
* no free heading gives `NUDGE`, reversing, `NUDGE_M` long
* `NUDGE_MAX` nudges without progress gives `BLOCKED`, and the note
  carries the bearing and the range
* `step()` with `buckets=None` and `now=None` is byte-identical to
  today's behaviour, which is what the existing test_nav_node cases
  assert without being touched

**`test_progress.py`** — pure arithmetic:
* a truck that moves `PROGRESS_M` resets the clock
* one that moves less does not
* `stalled_for` is None until `PROGRESS_S` has passed

**`test_fleet_manager_stub.py`** — three additions:
* a truck the FLOOR is holding is never called stalled, however long it
  stands
* a truck with no executing order is never called stalled
* a stalled truck is named in the document, and at `STALL_GIVE_UP_S` its
  order is cancelled and its task is at the head of the queue

---

## 7. Acceptance

A 600 s four-truck run, `--seed 7`, measured the way M6.6's was:

1. **No truck stands still for more than `STALL_GIVE_UP_S` without the
   fleet naming it.** Read off the status document.
2. **Every stall ends** — self-cleared, or requeued with the truck
   eligible again. No transport is lost to one.
3. **`recover(body)` and `recover(starvation)` are reported separately**,
   and `body` is the number the gate reads.
4. **More than four transports complete.** M6.6's run did four; this is
   the floor to beat and it is deliberately low, because the rig is the
   binding constraint and this work does not change it.
5. **515+ tests pass, 0 skipped.**

Where a criterion fails it is written down as measured and the gate is
not ticked, which is this file's own convention and M6.6's.
