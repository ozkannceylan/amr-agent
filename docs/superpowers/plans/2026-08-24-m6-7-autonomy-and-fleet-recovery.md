# M6.7 — Autonomy Recovery and Fleet Watchdog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-08-24-m6-7-autonomy-and-fleet-recovery-design.md`

**Goal:** Give a stopped truck a way out of its own stop, and give the
fleet the arithmetic to notice a truck that has not got one.

**Architecture:** Two pure modules and four wiring edits. `ipc/avoid.py`
turns one scan into a polar histogram and answers where the free floor
is; `nav_core` grows a four-state escalation on top of the `HOLD` it
already had; `fleet/progress.py` measures whether a truck is advancing
and `fleet_manager` acts on it. `follower.py` is not edited — its bands
are measured numbers and this work adds behaviour on top of them.

**Tech Stack:** Python 3.12 (plain files, no package), ROS 2 Jazzy,
pytest. Runs under WSL2.

## Global Constraints

- **Scope is `m6/` only.** Verify with `git status --short` before every
  commit; nothing outside `m6/` may appear except the two doc files.
- **No `follower.py` constant may change**, and `follower.py` is not in
  any file list. If the escalation appears to need `GUARD_HOLD_M`,
  `GUARD_SLOW_M`, `CRUISE_MPS` or a band edge moved, stop and report.
- **`m6/ipc/stations.py`, `m6/ipc/route.py` and `m6/gazebo/**` are not
  edited.** The floor is settled; this is about what the truck does on
  it.
- **Localisation stays on ground-truth odometry.** No AMCL, no SLAM, no
  Nav2, no costmap.
- **Backwards compatibility is the test strategy.** Both new arguments
  to `nav_core.step()` default to `None`, and with both absent the file
  must behave exactly as it does today — that is what lets the existing
  `test_nav_node.py` and `test_m6.py` cases stand unedited and still
  mean something.
- **Test command, and the `source` is not optional:**
  ```bash
  cd /mnt/c/Users/ozkan/projects/amr-agent
  source /opt/ros/jazzy/setup.bash
  python3 -m pytest m6/tests/ -q
  ```
- **A skip is a failure.** Baseline is `515 passed, 0 skipped`. If the
  suite reports skips, something is still running: `m6/m6.sh stop` on
  the WSL side and stop the Windows `python` writers. Twelve skips with
  the stack up is not a result.
- **Rig preconditions for Task 7 only:** `wsl --shutdown` first, then
  `export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`.
- **Commit after every task.** Working branch is `grok-m6`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `m6/ipc/avoid.py` (new) | one scan → polar histogram → the nearest free heading the vehicle's width fits through | 1 |
| `m6/tests/test_avoid.py` (new) | the histogram and the window rule, against hand-written scans | 1 |
| `m6/ipc/nav_core.py` | the `HOLD → AVOID → NUDGE → BLOCKED` escalation | 2 |
| `m6/tests/test_nav_core_escalation.py` (new) | the escalation as a table, and the scan-sign pin | 2 |
| `m6/ipc/nav_node.py` | compute buckets in `cb_scan`, pass buckets and a clock to `step()` | 3 |
| `m6/fleet/progress.py` (new) | has this truck advanced, and for how long has it not | 4 |
| `m6/tests/test_progress.py` (new) | the arithmetic | 4 |
| `m6/fleet/fleet_manager.py` | note positions, run the stall pass, put it on the screen, give up | 5 |
| `m6/fleet/fleet_cli.py` | render the STALLED section | 5 |
| `m6/windows/m6.py` | publish how many protective inputs were false | 6 |
| `m6/tools/scripted_writer.py` | latch the count at the Motor falling edge, label the press | 6 |
| `m6/tools/score_run.py` | report stalls beside distance | 7 |
| `m6/README_m6.md`, `m6/PROOF.md` | the measured run | 7 |

---

## Task 1: `avoid.py` — where the free floor is

**Files:**
- Create: `m6/ipc/avoid.py`
- Test: `m6/tests/test_avoid.py`

**Interfaces:**
- Consumes: `follower.SELF_MASK`, `follower.norm_ang`,
  `follower._self_return` (all in `m6/ipc/follower.py`).
- Produces: `avoid.buckets(ranges, angle_min, angle_inc, range_lo,
  range_hi, self_mask=follower.SELF_MASK) -> tuple[(float, float), ...]`
  and `avoid.free_heading(bkts, want_rad, reach_m=FREE_M) -> float |
  None`, plus the constants `BUCKET_RAD`, `HALF_ENVELOPE_M`,
  `WINDOW_MARGIN_M`, `FREE_M`, `MAX_SWING_RAD`. Task 2 calls both.

- [ ] **Step 1: Write the failing test**

Create `m6/tests/test_avoid.py`:

```python
"""avoid - where the free floor is, from one scan. Pure geometry.

THE SCANS BELOW ARE BUILT, NOT CAPTURED, and every one of them is a
shape with a name: a clear room, a wall with a gap on one side, a gap
too narrow for the truck, a wall with no gap at all. A capture would
prove that this file agreed with one afternoon; a shape proves the rule.
"""
import math

import avoid
import follower

N = 360
ANGLE_MIN = -math.pi
ANGLE_INC = 2.0 * math.pi / N


def scan(default=8.0, blocked=(), value=1.0):
    """A 360-ray scan at `default`, with each (lo_deg, hi_deg) span in
    `blocked` set to `value`. Ray i is at ANGLE_MIN + i * ANGLE_INC."""
    out = [default] * N
    for lo, hi in blocked:
        for i in range(N):
            deg = math.degrees(follower.norm_ang(ANGLE_MIN + i * ANGLE_INC))
            if lo <= deg <= hi:
                out[i] = value
    return out


def bkts(ranges):
    return avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)


def test_the_histogram_covers_the_whole_circle_once():
    b = bkts(scan())
    assert len(b) == int(round(2.0 * math.pi / avoid.BUCKET_RAD))
    bearings = [x for x, _r in b]
    assert len(set(bearings)) == len(bearings), "two buckets, one bearing"
    for bearing, _r in b:
        assert -math.pi <= bearing <= math.pi


def test_a_clear_room_offers_the_heading_that_was_asked_for():
    free = avoid.free_heading(bkts(scan()), 0.0)
    assert free is not None
    assert abs(free) <= avoid.BUCKET_RAD, free


def test_a_wall_with_a_gap_on_one_side_offers_the_gap():
    # Everything from -60 to +25 degrees is a wall at 1.0 m. The only
    # free floor inside MAX_SWING is to the LEFT of it, and the answer
    # has to clear the wall edge by the vehicle's own half-window.
    b = bkts(scan(blocked=((-60.0, 25.0),)))
    free = avoid.free_heading(b, 0.0)
    assert free is not None
    assert free > 0.0, "steered into the wall rather than round it"
    assert math.degrees(free) >= 43.0, math.degrees(free)
    assert abs(free) <= avoid.MAX_SWING_RAD


def test_a_gap_narrower_than_the_truck_is_not_offered():
    # A wall with a 10-degree slot in it. The window the vehicle needs
    # at FREE_M is about 37 degrees wide, so the slot is not floor.
    b = bkts(scan(blocked=((-90.0, -5.0), (5.0, 90.0))))
    assert avoid.free_heading(b, 0.0) is None


def test_a_wall_with_no_gap_at_all_answers_None():
    assert avoid.free_heading(bkts(scan(blocked=((-180.0, 180.0),))), 0.0) \
        is None


def test_free_floor_beyond_the_swing_bound_is_not_offered():
    # Blocked everywhere except behind: the free floor is real and it is
    # 180 degrees away, which is a re-route and not an avoidance.
    b = bkts(scan(blocked=((-100.0, 100.0),)))
    assert avoid.free_heading(b, 0.0) is None


def test_the_trucks_own_mast_is_not_a_wall():
    # SELF_MASK's near upright: -3 to -6 degrees off the fork end, under
    # 1.6 m. In the scan frame the fork end is pi, so those rays sit
    # near +-pi. Unmasked they would block the reverse heading.
    ranges = [8.0] * N
    for i in range(N):
        off = math.degrees(follower.norm_ang(
            ANGLE_MIN + i * ANGLE_INC - math.pi))
        if -6.0 <= off <= -3.0:
            ranges[i] = 1.29
    b = avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)
    assert avoid.free_heading(b, math.pi) is not None, \
        "the truck's own mast was read as a wall"
    raw = avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0,
                        self_mask=())
    assert avoid.free_heading(raw, math.pi) is None, \
        "the staging put nothing where the mask is - this proves nothing"


def test_invalid_returns_are_dropped_not_counted_as_close():
    ranges = [float("inf")] * N
    ranges[0] = float("nan")
    ranges[1] = 0.01           # below range_lo
    ranges[2] = 99.0           # above range_hi
    b = avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)
    assert all(r == math.inf for _x, r in b)
    assert avoid.free_heading(b, 0.0) is not None


def test_the_same_scan_gives_the_same_answer():
    ranges = scan(blocked=((-60.0, 25.0),))
    first = avoid.free_heading(bkts(ranges), 0.0)
    for _ in range(5):
        assert avoid.free_heading(bkts(ranges), 0.0) == first
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m6/tests/test_avoid.py -q
```

Expected: `ModuleNotFoundError: No module named 'avoid'`.

- [ ] **Step 3: Write `m6/ipc/avoid.py`**

```python
"""avoid.py - where the free floor is, from one scan. Pure, no ROS.

follower.sector_min ANSWERS "HOW CLOSE". THIS ONE ANSWERS "WHERE", and
until M6.7 nothing did. The nav lidar is 360 rays over the whole circle
and the autopilot reduced them to one number per direction of travel -
so a truck knew an obstacle was 1.47 m away and had no idea whether
there was three metres of clear floor beside it. Measured 2026-08-23,
that is exactly the state f2 and f3 stood in indefinitely.

WHAT THIS FILE IS NOT. It has no memory, no map, no clock and no
opinion about routes. One scan in, one heading out. It cannot know that
the gap it just offered is a dead end, and it is not asked to - going
round a body is an avoidance and finding another way to the station is
a re-route, which is the fleet's job and route.py's.

THE WINDOW IS THE VEHICLE, NOT A CONSTANT. A heading is free only if
everything the truck's WIDTH would sweep is free, so the half-width
tested at range r is atan2(HALF_ENVELOPE_M + WINDOW_MARGIN_M, r): about
18 degrees each side at 2.00 m, about 8 at 5.00. A fixed angular window
is too wide near and too narrow far, and too narrow far is how a truck
steers confidently into a gap it does not fit through.

THE MASK IS FOLLOWER'S, IMPORTED AND NOT RESTATED. follower.SELF_MASK is
the measured list of bearings where this vehicle sees its own mast
(probed live 2026-08-13). A second copy here would be a second thing to
keep true, and the first time they disagreed a truck would treat its own
upright as a wall - or worse, treat a wall as its own upright.
"""
import math

import follower

# 5 degrees. The nav lidar is 360 samples over 360 degrees, so a bucket
# is exactly five rays and no bucket is ever empty for want of rays.
BUCKET_RAD = 0.0873
HALF_ENVELOPE_M = 0.52      # the plan envelope is 1.04 m wide
WINDOW_MARGIN_M = 0.15
# A HEADING THAT CLEARS BY LESS THAN THE HOLD BAND IS NOT A HEADING.
# follower.GUARD_HOLD_M is 1.50: offer 1.60 m of free floor and the
# guard stops the truck on it anyway, which is worse than saying no -
# it spends the escalation and gets nowhere.
FREE_M = 2.00
# 60 degrees off the pursuit's own heading. Further than that is not an
# avoidance, it is a re-route.
MAX_SWING_RAD = 1.047


def buckets(ranges, angle_min, angle_inc, range_lo, range_hi,
            self_mask=follower.SELF_MASK):
    """((bearing, nearest), ...) over the whole circle, BUCKET_RAD wide.

    `nearest` is inf for a bucket with no valid return, which reads as
    "nothing there" - and that is the right direction here because this
    file only ever GRANTS floor. The safety layer is what treats silence
    as an obstacle, and it does that independently of this.
    """
    count = int(round(2.0 * math.pi / BUCKET_RAD))
    nearest = [math.inf] * count
    for index, value in enumerate(ranges):
        if not (range_lo <= value <= range_hi):   # False for nan and inf
            continue
        angle = follower.norm_ang(angle_min + index * angle_inc)
        # The mask's windows are offsets from the fork end, exactly as
        # follower.sector_min reads them.
        if follower._self_return(
                math.degrees(follower.norm_ang(angle - math.pi)),
                value, self_mask):
            continue
        slot = int((angle + math.pi) / BUCKET_RAD) % count
        if value < nearest[slot]:
            nearest[slot] = value
    return tuple(
        (follower.norm_ang(-math.pi + (slot + 0.5) * BUCKET_RAD),
         nearest[slot])
        for slot in range(count))


def _window_clear(bkts, centre, half_rad, reach_m):
    """True when every bucket within half_rad of centre is clear."""
    for bearing, nearest in bkts:
        if abs(follower.norm_ang(bearing - centre)) <= half_rad:
            if nearest < reach_m:
                return False
    return True


def free_heading(bkts, want_rad, reach_m=FREE_M):
    """The bearing NEAREST want_rad whose window is clear, or None.

    NEAREST AND NOT WIDEST. The widest gap in the room is often behind
    the truck; what is wanted is the smallest deviation from the route
    that gets past the thing in the way, because every degree of
    deviation is floor the pursuit then has to win back.

    Ties go to the lower bearing, so the answer is the same answer every
    time - a fleet log that reads differently on two identical scans is
    a log nobody can use.
    """
    half_rad = math.atan2(HALF_ENVELOPE_M + WINDOW_MARGIN_M, reach_m)
    best = None
    for bearing, _nearest in bkts:
        swing = abs(follower.norm_ang(bearing - want_rad))
        if swing > MAX_SWING_RAD:
            continue
        if not _window_clear(bkts, bearing, half_rad, reach_m):
            continue
        rank = (swing, bearing)
        if best is None or rank < best:
            best = rank
    return None if best is None else best[1]
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
python3 -m pytest m6/tests/test_avoid.py -q
```

Expected: `9 passed`. If
`test_a_wall_with_a_gap_on_one_side_offers_the_gap` fails on the 43-degree
bound, print `math.degrees(free)` and check it against
`25 + math.degrees(math.atan2(0.67, 2.0))` = 43.5 — the bound is that
sum rounded down to a bucket edge, not a guess.

- [ ] **Step 5: Commit**

```bash
git add m6/ipc/avoid.py m6/tests/test_avoid.py
git commit -m "m6.7: the lidar's 360 rays stop being one number"
```

---

## Task 2: the escalation in `nav_core`

**Files:**
- Modify: `m6/ipc/nav_core.py`
- Test: `m6/tests/test_nav_core_escalation.py` (create)

**Interfaces:**
- Consumes: `avoid.buckets`, `avoid.free_heading`, `avoid.FREE_M`,
  `avoid.MAX_SWING_RAD` (Task 1); `follower.steer`, `follower.norm_ang`,
  `follower.travel_yaw`, `follower.GUARD_SLOW_MPS`,
  `follower.REVERSE_MPS`.
- Produces: `nav_core.AVOID`, `nav_core.NUDGE`, `nav_core.BLOCKED`
  (state strings `"AVOID"`, `"NUDGE"`, `"BLOCKED"`), the constants
  `HOLD_PATIENCE_S`, `NUDGE_M`, `NUDGE_MAX`, `SCAN_SIGN`, and
  `NavCore.step(pose, fwd_guard_m, rev_guard_m, motor_ok, v_limit_mm_s,
  field_min_m=math.inf, buckets=None, now=None)`. Task 3 passes the two
  new arguments.

**THE ONE THING IN THIS PLAN THAT IS NOT DERIVABLE FROM THE SOURCE.**
`avoid` answers in the SCAN frame; `follower.steer` wants a target point
in the WORLD. Whether a positive scan bearing is a positive or negative
offset from the travel heading is a property of how the lidar is mounted
in `forklift_ver2/model.sdf`, and reading it off is exactly the kind of
thing that is wrong half the time. So it is a named constant, `SCAN_SIGN`,
and **step 1 below writes the test that pins it before anything else.**
If the sign is wrong the truck steers *away* from the gap, which is worse
than not moving, and that test is what catches it.

- [ ] **Step 1: Write the failing test**

Create `m6/tests/test_nav_core_escalation.py`:

```python
"""HOLD stops being terminal. The escalation, as a table.

WHAT THIS FILE IS REALLY FOR is the first test in it. Everything else
here is bookkeeping that a careful reader could check by eye; the sign
of the scan frame against the world frame cannot be checked by eye, it
is wrong half the time by construction, and when it is wrong the truck
steers AWAY from the only free floor in the room.
"""
import math

import avoid
import follower
import nav_core
from status_contract import MODE_AUTO

CLEAR = 9.9            # a guard reading that stops nothing
BLOCKED_M = 1.0        # inside follower.GUARD_HOLD_M (1.50)
N = 360
ANGLE_MIN = -math.pi
ANGLE_INC = 2.0 * math.pi / N


def core(route=None):
    c = nav_core.NavCore()
    c.mode = MODE_AUTO
    c.on_route(route or [[0.0, 0.0], [10.0, 0.0]], 0.25, "t-1")
    return c


def scan_with_gap_to_port():
    """A wall ahead of a truck travelling +x, clear floor to its left.

    The truck's forks lead at model yaw + pi, and the scan's fork end is
    at angle pi. So 'ahead' is pi and the wall is put there.
    """
    ranges = [8.0] * N
    for i in range(N):
        off = math.degrees(follower.norm_ang(
            ANGLE_MIN + i * ANGLE_INC - math.pi))
        if -25.0 <= off <= 60.0:
            ranges[i] = BLOCKED_M
    return avoid.buckets(ranges, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)


def test_the_scan_sign_puts_the_steer_toward_the_gap():
    """THE PIN. A wall ahead and floor on ONE side: the steer must have
    the sign that turns toward the floor, whatever the mounting is."""
    c = core()
    pose = (0.0, 0.0, math.pi)          # travel heading +x
    bkts = scan_with_gap_to_port()
    free = avoid.free_heading(bkts, math.pi)
    assert free is not None, "the staging left no gap - this proves nothing"
    off = follower.norm_ang(free - math.pi)
    assert off != 0.0
    now = 100.0
    c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=bkts, now=now)
    linear, steer = c.step(pose, BLOCKED_M, CLEAR, True, 1500,
                           buckets=bkts, now=now + nav_core.HOLD_PATIENCE_S)
    assert c.state == nav_core.AVOID, c.state
    assert linear != 0.0
    # follower.steer's sign convention: a target clockwise of the travel
    # heading (negative alpha) needs POSITIVE steer. So the steer must
    # be the opposite sign to the offset the gap sits at.
    assert (steer > 0.0) == (off * nav_core.SCAN_SIGN < 0.0), (
        "the truck steered away from the only free floor in the room "
        "- SCAN_SIGN is inverted")


def test_a_clear_guard_never_enters_the_escalation():
    c = core()
    linear, _steer = c.step((0.0, 0.0, math.pi), CLEAR, CLEAR, True, 1500,
                            buckets=scan_with_gap_to_port(), now=100.0)
    assert c.state == nav_core.EN_ROUTE
    assert linear != 0.0


def test_hold_waits_out_its_patience_before_anything_else():
    c = core()
    bkts = scan_with_gap_to_port()
    for dt in (0.0, 1.0, nav_core.HOLD_PATIENCE_S - 0.1):
        out = c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
                     buckets=bkts, now=100.0 + dt)
        assert c.state == nav_core.HOLD, dt
        assert out == (0.0, 0.0)


def test_a_free_heading_at_patience_gives_avoid_at_the_creep_ceiling():
    c = core()
    bkts = scan_with_gap_to_port()
    c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
           buckets=bkts, now=100.0)
    linear, steer = c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True,
                           1500, buckets=bkts,
                           now=100.0 + nav_core.HOLD_PATIENCE_S)
    assert c.state == nav_core.AVOID
    assert abs(linear) == follower.GUARD_SLOW_MPS
    assert abs(steer) <= 1.31, "past the steer stop cmd_gate declares"


def test_no_free_heading_gives_a_nudge_and_it_reverses():
    c = core()
    walled = avoid.buckets([BLOCKED_M] * N, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)
    c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
           buckets=walled, now=100.0)
    linear, steer = c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True,
                           1500, buckets=walled,
                           now=100.0 + nav_core.HOLD_PATIENCE_S)
    assert c.state == nav_core.NUDGE
    assert steer == 0.0, "a nudge is straight - an arc is what it avoids"
    assert linear > 0.0, "the forward sign is negative; a nudge reverses"


def test_a_nudge_that_has_run_its_distance_ends():
    c = core()
    walled = avoid.buckets([BLOCKED_M] * N, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)
    now = 100.0
    c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
           buckets=walled, now=now)
    c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
           buckets=walled, now=now + nav_core.HOLD_PATIENCE_S)
    assert c.state == nav_core.NUDGE
    # ...and once the truck has moved NUDGE_M the nudge is over.
    moved = (nav_core.NUDGE_M + 0.05, 0.0, math.pi)
    c.step(moved, BLOCKED_M, CLEAR, True, 1500, buckets=walled,
           now=now + nav_core.HOLD_PATIENCE_S + 2.0)
    assert c.state != nav_core.NUDGE


def test_nudging_without_getting_anywhere_ends_in_blocked():
    c = core()
    walled = avoid.buckets([BLOCKED_M] * N, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)
    pose, now = (0.0, 0.0, math.pi), 100.0
    for cycle in range(nav_core.NUDGE_MAX + 1):
        c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=walled, now=now)
        now += nav_core.HOLD_PATIENCE_S
        c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=walled, now=now)
        # the truck never actually moves: each nudge is spent
        pose = (pose[0] + nav_core.NUDGE_M + 0.05, 0.0, math.pi)
        now += 2.0
        c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=walled, now=now)
    out = c.step(pose, BLOCKED_M, CLEAR, True, 1500, buckets=walled,
                 now=now + nav_core.HOLD_PATIENCE_S + 1.0)
    assert c.state == nav_core.BLOCKED
    assert out == (0.0, 0.0)
    assert "m" in c.note and "deg" in c.note, (
        "BLOCKED must name the bearing and the range: {!r}".format(c.note))


def test_the_guard_clearing_ends_any_state_at_once():
    c = core()
    walled = avoid.buckets([BLOCKED_M] * N, ANGLE_MIN, ANGLE_INC, 0.10, 8.0)
    now = 100.0
    for _ in range(3):
        c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500,
               buckets=walled, now=now)
        now += nav_core.HOLD_PATIENCE_S + 1.0
    assert c.state in (nav_core.NUDGE, nav_core.BLOCKED)
    linear, _ = c.step((0.0, 0.0, math.pi), CLEAR, CLEAR, True, 1500,
                       buckets=walled, now=now + 1.0)
    assert c.state == nav_core.EN_ROUTE
    assert linear != 0.0


def test_without_a_clock_or_buckets_the_file_behaves_as_it_did():
    """The compatibility contract. Every caller written before M6.7 -
    including test_nav_node.py's - passes neither, and must still see
    the HOLD it was written against."""
    c = core()
    out = c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500)
    assert c.state == nav_core.HOLD
    assert out == (0.0, 0.0)
    for _ in range(50):
        c.step((0.0, 0.0, math.pi), BLOCKED_M, CLEAR, True, 1500)
    assert c.state == nav_core.HOLD, "the escalation ran with no clock"
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_nav_core_escalation.py -q
```

Expected: `AttributeError: module 'nav_core' has no attribute 'AVOID'`.

- [ ] **Step 3: Add the escalation to `m6/ipc/nav_core.py`**

Add `import avoid` beside the existing `import follower`, then the
states and constants beside `IDLE, EN_ROUTE, HOLD`:

```python
IDLE, EN_ROUTE, HOLD = "IDLE", "EN-ROUTE", "HOLD"
SAFETY_STOP, ARRIVED = "SAFETY-STOP", "ARRIVED"
# M6.7: HOLD IS NO LONGER WHERE A TRUCK GOES TO STAY. Measured
# 2026-08-23, f2 and f3 stood at their stations indefinitely with
# guard_min 1.4846 and 1.4722 m against a 1.500 m hold band, Motor TRUE
# and every field clear. Nothing was broken; the autopilot's only move
# was to wait for the world to change and the world was a wall.
AVOID, NUDGE, BLOCKED = "AVOID", "NUDGE", "BLOCKED"

# WAIT FIRST, AND IT IS THE CHEAPEST MOVE THERE IS. At the creep ceiling
# a truck covers 1.5 m in this, so an obstacle that was another vehicle
# has gone. Trying to drive round a truck that is about to leave is how
# a floor gets two vehicles in the same aisle facing each other.
HOLD_PATIENCE_S = 5.0
# Most of one envelope half-width: enough to change the geometry, short
# enough to stay on the corridor. 1.6 s at follower.REVERSE_MPS.
NUDGE_M = 0.40
NUDGE_MAX = 2
# WHICH WAY A POSITIVE SCAN BEARING TURNS THE TRUCK. avoid answers in
# the scan frame and follower.steer wants a world target, and whether
# the two agree is a property of how the lidar is mounted rather than
# anything either file says. It is a constant with a test on it
# (test_nav_core_escalation.test_the_scan_sign_puts_the_steer_toward_
# the_gap): get it wrong and the truck steers AWAY from the only free
# floor in the room, which is worse than not moving at all.
SCAN_SIGN = 1.0
```

In `NavCore.__init__`, after `self.reversing = False`:

```python
        # The escalation's own memory. All three are cleared by any tick
        # that actually drives, so a truck that got going never carries
        # a stale nudge count into its next stop.
        self._stop_since = None
        self._nudges = 0
        self._nudge_from = None
```

Add to `_cancel`, beside `self.reversing = False`:

```python
        self._clear_escalation()
```

Then the three new methods, after `_cancel`:

```python
    def _clear_escalation(self):
        self._stop_since = None
        self._nudges = 0
        self._nudge_from = None

    def _want_bearing(self):
        """Where the route wants to go, in the SCAN frame.

        The scan's fork end is angle pi and its counterweight end is 0,
        which is the same convention follower.sector_min centres on. A
        truck driving forwards therefore wants pi and a reversing one
        wants 0; the pursuit's own bearing error is added on top, with
        SCAN_SIGN carrying whether the two frames agree about which way
        is positive.
        """
        return 0.0 if self.reversing else math.pi

    def _escalate(self, pose, xy, alpha, bkts, now):
        """A stop that has a way out of itself, or an honest BLOCKED.

        Returns (linear, angular). The guard is already known to be
        stopping the truck; what is decided here is what to do about it.
        """
        if now is None or bkts is None:
            # THE COMPATIBILITY PATH, and it is deliberately first. A
            # caller from before M6.7 - or a test written against the
            # old behaviour - gets the HOLD it expects and nothing else.
            self.state = HOLD
            return (0.0, 0.0)
        if self._stop_since is None:
            self._stop_since = now
        if now - self._stop_since < HOLD_PATIENCE_S:
            self.state = HOLD
            return (0.0, 0.0)
        if self._nudge_from is not None:
            if math.dist(xy, self._nudge_from) < NUDGE_M:
                self.state = NUDGE
                return (follower.REVERSE_MPS, 0.0)
            # The move is spent. Start the cycle again from the top:
            # the geometry has changed and the cheap answers deserve
            # another look before the expensive one.
            self._nudge_from = None
            self._stop_since = now
            self.state = HOLD
            return (0.0, 0.0)
        want = self._want_bearing()
        free = avoid.free_heading(bkts, want)
        if free is not None:
            self.state = AVOID
            off = SCAN_SIGN * follower.norm_ang(free - want)
            travel = follower.travel_yaw(pose[2])
            reach = avoid.FREE_M
            target = (pose[0] + reach * math.cos(travel + off),
                      pose[1] + reach * math.sin(travel + off))
            steer = follower.steer(pose, target)
            speed = follower.GUARD_SLOW_MPS
            return ((speed if self.reversing else -speed), steer)
        if self._nudges < NUDGE_MAX:
            self._nudges += 1
            self._nudge_from = xy
            self.state = NUDGE
            return (follower.REVERSE_MPS, 0.0)
        self.state = BLOCKED
        near = min((r for _b, r in bkts), default=float("inf"))
        bearing = min(bkts, key=lambda br: br[1])[0] if bkts else 0.0
        self.note = ("blocked: nearest {:.2f} m at {:.0f} deg, no free "
                     "heading and {} nudges spent"
                     .format(near, math.degrees(bearing), self._nudges))
        return (0.0, 0.0)
```

Finally, change `step`'s signature and its zero-speed branch:

```python
    def step(self, pose, fwd_guard_m, rev_guard_m, motor_ok, v_limit_mm_s,
             field_min_m=math.inf, buckets=None, now=None):
```

and replace the `if speed == 0.0:` block with:

```python
        if speed == 0.0:
            return self._escalate(pose, xy, alpha, buckets, now)
        self._clear_escalation()
        self.state = EN_ROUTE
```

(the `self.state = EN_ROUTE` line already exists; add `_clear_escalation`
immediately before it).

- [ ] **Step 4: Run the tests and watch them pass**

```bash
python3 -m pytest m6/tests/test_nav_core_escalation.py m6/tests/test_nav_node.py -q
```

Expected: all pass. **If `test_the_scan_sign_puts_the_steer_toward_the_gap`
fails, change `SCAN_SIGN` to `-1.0` and re-run — that is what the
constant is for, and a failure there is the test doing its job rather
than a defect in the escalation.**

- [ ] **Step 5: Commit**

```bash
git add m6/ipc/nav_core.py m6/tests/test_nav_core_escalation.py
git commit -m "m6.7: HOLD is no longer where a truck goes to stay"
```

---

## Task 3: wire the scan into the escalation

**Files:**
- Modify: `m6/ipc/nav_node.py` (`cb_scan` and `tick`)

**Interfaces:**
- Consumes: `avoid.buckets` (Task 1), the new `step()` signature (Task 2).
- Produces: nothing new. This is wiring.

- [ ] **Step 1: Add the buckets to `cb_scan`**

Add `import avoid` beside `import follower`, then at the end of
`cb_scan`, after the two `sector_min` calls:

```python
        # THE SAME SCAN, KEPT AS A SHAPE AND NOT ONLY AS A NUMBER. The
        # two lines above answer "how close in the direction of travel";
        # this one answers "where is there floor", which is what the
        # escalation needs when the first answer is "too close". One
        # extra pass over 360 numbers at 10 Hz.
        self.buckets = avoid.buckets(
            msg.ranges, msg.angle_min, msg.angle_increment, lo, hi)
```

and initialise it in `__init__` beside the guard fields:

```python
        self.buckets = None
```

- [ ] **Step 2: Pass them, and a clock, to `step`**

In `tick`, replace the `step` call:

```python
        linear, steer = self.core.step(
            self.pose, fwd, rev, motor, self.v_limit, field,
            # A DEAD SCAN OFFERS NO FLOOR. `dead` already zeroes both
            # guards above; passing the last good buckets with it would
            # let the escalation drive on a picture of the world that
            # has stopped arriving.
            buckets=None if dead else self.buckets, now=now)
```

- [ ] **Step 3: Run the node's tests**

```bash
python3 -m pytest m6/tests/test_nav_node.py m6/tests/test_nav_core_escalation.py -q
```

Expected: all pass.

- [ ] **Step 4: Prove it on the real stack**

```bash
# Windows: wsl --shutdown
export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
cd /mnt/c/Users/ozkan/projects/amr-agent/m6
./m6.sh deploy && ./m6.sh start --headless
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=96
timeout 10 ros2 topic echo /f1/auto/state --once
```

Expected: a state document as before. The escalation is not exercised
here; what this proves is that the extra work in `cb_scan` did not break
the node or its rate. Then `./m6.sh stop`.

- [ ] **Step 5: Commit**

```bash
git add m6/ipc/nav_node.py
git commit -m "m6.7: the scan reaches the escalation as a shape"
```

---

## Task 4: `progress.py` — has this truck advanced

**Files:**
- Create: `m6/fleet/progress.py`
- Test: `m6/tests/test_progress.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `progress.Progress(progress_m=PROGRESS_M,
  window_s=PROGRESS_S)` with `.note(serial, xy, now)`,
  `.stalled_for(serial, now) -> float | None`, `.forget(serial)`, and
  the constants `PROGRESS_M`, `PROGRESS_S`, `STALL_GIVE_UP_S`. Task 5
  uses all of it.

- [ ] **Step 1: Write the failing test**

Create `m6/tests/test_progress.py`:

```python
"""progress - has this truck advanced, and for how long has it not.

Pure arithmetic on positions the fleet already receives. No clock of its
own, no wire, no opinion about WHY a truck is not moving - that judgement
is fleet_manager's, and it is the one that knows a truck the ledger is
holding is behaving perfectly.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import progress                                      # noqa: E402


def test_an_unknown_truck_is_not_stalled():
    p = progress.Progress()
    assert p.stalled_for("f1", 100.0) is None


def test_a_truck_that_advances_resets_the_clock():
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    p.note("f1", (progress.PROGRESS_M + 0.1, 0.0),
           100.0 + progress.PROGRESS_S + 5.0)
    assert p.stalled_for("f1", 100.0 + progress.PROGRESS_S + 5.0) is None


def test_a_truck_that_shuffles_does_not_reset_it():
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    for i in range(20):
        # half the threshold, back and forth: movement, not progress
        p.note("f1", ((progress.PROGRESS_M / 2.0) * (i % 2), 0.0),
               100.0 + i)
    held = p.stalled_for("f1", 100.0 + progress.PROGRESS_S + 1.0)
    assert held is not None and held > progress.PROGRESS_S


def test_nothing_is_stalled_before_the_window_has_passed():
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    assert p.stalled_for("f1", 100.0 + progress.PROGRESS_S - 0.1) is None
    assert p.stalled_for("f1", 100.0 + progress.PROGRESS_S) is not None


def test_forgetting_a_truck_starts_it_again_from_clean():
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    assert p.stalled_for("f1", 200.0) is not None
    p.forget("f1")
    assert p.stalled_for("f1", 200.0) is None


def test_two_trucks_do_not_share_a_clock():
    p = progress.Progress()
    p.note("f1", (0.0, 0.0), 100.0)
    p.note("f2", (5.0, 0.0), 100.0)
    p.note("f2", (5.0 + progress.PROGRESS_M + 0.1, 0.0), 150.0)
    assert p.stalled_for("f1", 200.0) is not None
    assert p.stalled_for("f2", 200.0) is not None
    assert p.stalled_for("f1", 200.0) > p.stalled_for("f2", 200.0)


def test_the_give_up_bound_is_longer_than_the_window():
    # Otherwise a task is taken away the instant a stall is noticed,
    # with no chance for the floor ahead to drain on its own.
    assert progress.STALL_GIVE_UP_S > progress.PROGRESS_S
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_progress.py -q
```

Expected: `ModuleNotFoundError: No module named 'progress'`.

- [ ] **Step 3: Write `m6/fleet/progress.py`**

```python
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
since" measure would miss entirely.
"""
import math

# More than odometry noise, less than any real move. At the creep
# ceiling (0.30 m/s) a truck covers this in 1.7 s.
PROGRESS_M = 0.50
# A truck that has not made half a metre in thirty seconds is not
# driving. A leg on this floor is 60 m; nothing legitimate is this slow.
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
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
python3 -m pytest m6/tests/test_progress.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add m6/fleet/progress.py m6/tests/test_progress.py
git commit -m "m6.7: the arithmetic that says a truck is not moving"
```

---

## Task 5: the fleet acts on it

**Files:**
- Modify: `m6/fleet/fleet_manager.py`
- Modify: `m6/fleet/fleet_cli.py`
- Test: `m6/tests/test_fleet_manager_stub.py` (append)

**Interfaces:**
- Consumes: `progress.Progress` (Task 4), the existing
  `FleetManager._abandon_order`, `fleet_core.requeue_to_head`,
  `Floor.waiting_on`, `FleetManager._task_of`.
- Produces: `FleetManager.progress` (a `Progress`),
  `FleetManager.stalled` (`{serial: seconds}`), `_stall_pass(now)`, and
  a `"stalled"` key in the retained status document.

- [ ] **Step 1: Write the failing test**

Append to `m6/tests/test_fleet_manager_stub.py`:

```python
# =====================================================================
# M6.7 - the fleet notices a truck that is not moving
# =====================================================================
def test_a_truck_the_floor_is_holding_is_never_called_stalled(floor):
    """THE RULE THE WHOLE WATCHDOG TURNS ON. A vehicle parked at the end
    of its released base because the floor ahead is somebody else's is
    behaving perfectly. Calling that a stall would put a name on the
    operator's screen every single time traffic worked."""
    manager, stub = floor
    now = time.monotonic()
    f1, f2 = head_on(manager, stub, now)
    assert manager.floor.waiting_on("f2") is not None, \
        "the staging did not produce a waiting truck"
    for step in range(10):
        later = now + fl_progress.STALL_GIVE_UP_S * (step + 1)
        for truck in (f1, f2):
            truck.take().state(later)
        manager._stall_pass(later)
    assert "f2" not in manager.stalled
    assert manager.tasks[0]["state"] != "QUEUED" or \
        manager.tasks[0]["assignee"] is not None


def test_a_truck_with_no_task_is_never_called_stalled(floor):
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", WEST)
    for step in range(10):
        later = now + fl_progress.STALL_GIVE_UP_S * (step + 1)
        f1.state(later)
        manager._stall_pass(later)
    assert manager.stalled == {}


def test_a_truck_that_stops_driving_is_named_on_the_screen(floor):
    """The 245 seconds nobody saw. f1 takes a leg, drives none of it,
    and the document says so by name."""
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", WEST)
    submit(manager, "t-1", "S1", "S2")
    turn(manager, (f1,), now)
    assert manager.tasks[0]["assignee"] == "f1"

    later = now + fl_progress.PROGRESS_S + 1.0
    f1.state(later)                       # same position, new state
    manager._stall_pass(later)

    assert "f1" in manager.stalled
    assert manager.stalled["f1"] >= fl_progress.PROGRESS_S
    doc = manager._status(later)
    assert "f1" in doc["stalled"]


def test_a_stall_that_runs_long_gives_the_task_back(floor):
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", WEST)
    submit(manager, "t-1", "S1", "S2")
    turn(manager, (f1,), now)
    order_id = manager.tasks[0]["order_id"]

    later = now + fl_progress.STALL_GIVE_UP_S + 1.0
    f1.state(later)
    manager._stall_pass(later)

    assert manager.tasks[0]["task_id"] == "t-1"
    assert manager.tasks[0]["state"] == "QUEUED"
    assert manager.tasks[0]["assignee"] is None
    assert manager.cancelled["f1"]["order_id"] == order_id
    assert any("not moving" in r["why"] for r in manager.refused)


def test_a_truck_that_gets_going_again_is_forgiven(floor):
    manager, stub = floor
    now = time.monotonic()
    f1 = Truck(manager, stub, "f1", WEST)
    submit(manager, "t-1", "S1", "S2")
    turn(manager, (f1,), now)

    later = now + fl_progress.PROGRESS_S + 1.0
    f1.state(later)
    manager._stall_pass(later)
    assert "f1" in manager.stalled

    f1.xy = (f1.xy[0], f1.xy[1] + fl_progress.PROGRESS_M + 0.1)
    f1.state(later + 1.0)
    manager._stall_pass(later + 1.0)
    assert "f1" not in manager.stalled
```

Add the import at the top of the file, beside the existing `import
floor as fl`:

```python
import progress as fl_progress                       # noqa: E402
```

- [ ] **Step 2: Run the tests and watch them fail**

```bash
python3 -m pytest m6/tests/test_fleet_manager_stub.py -q -k stall
```

Expected: `AttributeError: 'FleetManager' object has no attribute
'_stall_pass'`.

- [ ] **Step 3: Wire it into `fleet_manager.py`**

Add the import beside the others at the top:

```python
import progress as pg
```

In `FleetManager.__init__`, beside `self.tasks = []`:

```python
        # M6.7: WHETHER A TRUCK IS ACTUALLY MOVING. The registry has
        # carried `position` since M6.3 and nothing ever asked whether
        # it changed - which is how f2 and f3 spent 245 s at a
        # standstill on 2026-08-23 listed as ordinary trucks executing
        # orders.
        self.progress = pg.Progress()
        self.stalled = {}          # serial -> seconds since it advanced
```

In `_on_state`, immediately after the vehicle's position is stored, add:

```python
        pos = veh.get("position")
        if pos is not None:
            self.progress.note(serial, pos, now)
```

In `drain()`, after `self.floor.traffic_pass(now)` and before
`self._assign(now)`:

```python
        # BEFORE THE ASSIGNMENT AND AFTER THE FLOOR. A truck given up on
        # here has its task requeued and becomes eligible again in the
        # same pass, which is what makes a stall cost one transport's
        # delay rather than one transport.
        self._stall_pass(now)
```

Then the method itself, beside `_expire_dwells`:

```python
    def _stall_pass(self, now):
        """Name the trucks that are not moving, and give up on the ones
        that have not moved for long enough.

        A TRUCK THE FLOOR IS HOLDING IS NOT STALLED, and that is the
        rule this whole method turns on. A vehicle parked at the end of
        its released base because the floor ahead belongs to somebody
        else is behaving exactly as M6.4 designed it to; naming it would
        put a word on the operator's screen every time traffic worked,
        and a screen that cries wolf is a screen nobody reads. So the
        watchdog looks at trucks the fleet BELIEVES are driving: with a
        task, with no ledger wait, and not moving.

        forget() rather than skip: a truck released from a two-minute
        wait must start its clock clean, or it is given up on the
        instant the corridor drains - the opposite of what the wait was
        for.
        """
        for serial in sorted(self.vehicles):
            task = self._task_of(serial)
            if task is None or self.floor.waiting_on(serial) is not None:
                self.progress.forget(serial)
                self.stalled.pop(serial, None)
                continue
            held = self.progress.stalled_for(serial, now)
            if held is None:
                self.stalled.pop(serial, None)
                continue
            self.stalled[serial] = round(held, 1)
            if held < pg.STALL_GIVE_UP_S:
                continue
            why = ("{} has not moved {:.2f} m in {:.0f} s while executing "
                   "{} - the task is given back and the truck stands "
                   "down until its own state says it is idle"
                   .format(serial, pg.PROGRESS_M, held, task["task_id"]))
            self.log.warning("%s", why)
            self._note_refusal(task["task_id"], why)
            order_id = task.get("order_id")
            self._requeue(task["task_id"], why)
            if order_id:
                self._abandon_order(serial, order_id, why)
            self.progress.forget(serial)
            self.stalled.pop(serial, None)
```

In `_status`, add the key beside `"refused"`:

```python
                "stalled": dict(self.stalled),
```

- [ ] **Step 4: Render it in `fleet_cli.py`**

`render` builds a list called `lines` and returns `"
".join(lines)`.
Insert this immediately after `lines += traffic_lines(doc)` and before
the `if refused:` block, so the screen reads floor, then trucks that are
not on it, then refusals:

```python
    stalled = _dict(doc, "stalled")
    if stalled:
        lines += ["", "NOT MOVING ({} - has a task, and the floor is "
                  "not holding it)".format(len(stalled))]
        for serial in sorted(stalled):
            lines.append("  {}  still for {} s".format(
                _cell(serial, 8), stalled[serial]))
```

`_dict` and `_cell` are already defined in the file (they are what the
vehicle and task tables are built from), so nothing new is imported.

- [ ] **Step 5: Run the tests and watch them pass**

```bash
python3 -m pytest m6/tests/test_fleet_manager_stub.py m6/tests/test_fleet_cli.py -q
```

Expected: all pass. If
`test_a_truck_the_floor_is_holding_is_never_called_stalled` fails,
`head_on` is not producing a waiting truck — check `waiting_on("f2")`
directly before assuming the watchdog is wrong.

- [ ] **Step 6: Commit**

```bash
git add m6/fleet/fleet_manager.py m6/fleet/fleet_cli.py \
        m6/tests/test_fleet_manager_stub.py
git commit -m "m6.7: the fleet can tell a driving truck from a dead one"
```

---

## Task 6: an honest latch count

**Files:**
- Modify: `m6/windows/m6.py`
- Modify: `m6/tools/scripted_writer.py`
- Test: `m6/tests/test_scripted_writer.py` (append)

**Interfaces:**
- Consumes: the existing `live` dict and `fields` dict in
  `m6.control_loop`.
- Produces: `live["pf_violated"]` (int 0-3), and
  `scripted_writer.classify(pf_at_drop) -> "starvation" | "body"`.

- [ ] **Step 1: Write the failing test**

Append to `m6/tests/test_scripted_writer.py`:

```python
def test_all_three_protective_fields_false_is_scan_starvation():
    """No single body is in three fields at once from three different
    mount points. All three false is field_eval failing safe on scans
    that did not arrive - measured 2026-08-23, worst gap 0.528 s against
    a 0.500 s rule, and it accounted for most of a run's 15 recoveries."""
    assert sw.classify(3) == "starvation"


def test_one_or_two_protective_fields_false_is_a_real_body():
    assert sw.classify(1) == "body"
    assert sw.classify(2) == "body"


def test_an_unknown_count_is_called_a_body():
    """The direction to be wrong in. An unlabelled latch counted as a
    body is a run that looks worse than it was; counted as starvation it
    is a run that hid a collision."""
    assert sw.classify(None) == "body"
    assert sw.classify(0) == "body"
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
python3 -m pytest m6/tests/test_scripted_writer.py -q -k protective
```

Expected: `AttributeError: module ... has no attribute 'classify'`.

- [ ] **Step 3: Publish the count in `m6/windows/m6.py`**

Beside the existing `live["fields_clear"] = ...`:

```python
            # HOW MANY OF THE THREE WERE FALSE, for the recording's
            # latch accounting. All three at once is not a body - no
            # single object is inside three fields evaluated at three
            # different mount points - it is field_eval failing safe on
            # scans that did not arrive. tools/scripted_writer.classify
            # is the only reader.
            live["pf_violated"] = sum(
                1 for key in ("pf", "pf_right", "pf_left")
                if not fields[key])
```

- [ ] **Step 4: Classify the press in `scripted_writer.py`**

Add beside `latch_watch`:

```python
def classify(pf_at_drop):
    """What kind of stop this was, from the protective inputs at the
    moment Motor fell.

    Read at the FALLING EDGE and not at the press: by the time the
    watchdog is allowed to press, the fields have re-cleared by
    definition, and every latch would look identical.
    """
    return "starvation" if pf_at_drop == 3 else "body"
```

In `serve`, track the edge. After `resets = [0, 0] if resets is None
else resets`:

```python
    was_motor = True
    pf_at_drop = None
```

and at the top of the loop, before the print block:

```python
        motor_now = bool(live.get("motor"))
        if was_motor and not motor_now:
            pf_at_drop = live.get("pf_violated")
        was_motor = motor_now
```

Then in the press branch, replace the `kind` line:

```python
                kind = ("recover({})".format(classify(pf_at_drop))
                        if enabled_once[0] else "enable")
```

- [ ] **Step 5: Run the tests and watch them pass**

```bash
python3 -m pytest m6/tests/test_scripted_writer.py m6/tests/test_m6.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add m6/windows/m6.py m6/tools/scripted_writer.py \
        m6/tests/test_scripted_writer.py
git commit -m "m6.7: a late scan is not a collision, and the count says so"
```

---

## Task 7: the measured run

**Files:**
- Modify: `m6/tools/score_run.py`
- Modify: `m6/PROOF.md`, `m6/README_m6.md`
- Create: `assets/m6-fleet/m6-fleet-06-recovery-2026-08-XX.mp4`

- [ ] **Step 1: Report stalls beside distance in `score_run.py`**

In `report()`, after the per-window table, add:

```python
    print("\nLONGEST STILL SPELL PER TRUCK (seconds between samples "
          "{:.2f} m apart)".format(JUMP_M))
    for vid in VEHICLES:
        rows_v = [r for r in rows if r["v"] == vid]
        longest, anchor = 0.0, None
        for r in rows_v:
            xy = (r["x"], r["y"])
            if anchor is None or math.dist(anchor[0], xy) >= 0.50:
                anchor = (xy, r["t"])
            longest = max(longest, r["t"] - anchor[1])
        print("  {}  {:8.1f} s".format(vid, longest))
```

- [ ] **Step 2: Run the whole suite green**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m6/tests/ -q
```

Expected: **all pass, 0 skipped.** The count will be about 540 (this
plan adds roughly 25 tests). If there are skips, the stack or the
Windows writers are still up.

- [ ] **Step 3: Record a 600 s run**

```bash
# Windows: wsl --shutdown
export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
cd /mnt/c/Users/ozkan/projects/amr-agent/m6
./m6.sh deploy && ./m6.sh start --headless
```

Then, from PowerShell, four writers with `--auto-reset` on ports
5910/5920/5930/5940, and the take driven by `wsl.exe` as a detached
process (a `nohup` inside `wsl -e bash -lc` dies with its session). Hold
a `/fN/hmi/mode` publisher for the whole run — `hmi_node` latches
`teleop` once at startup, and a transient publisher that exits leaves
that on the wire.

- [ ] **Step 4: Score it against the spec's five criteria**

1. No truck stands still longer than `STALL_GIVE_UP_S` without the fleet
   naming it — read `stalled` out of the status document and the
   longest-still-spell table against each other.
2. Every stall ends: self-cleared, or requeued with the truck eligible.
3. `recover(body)` and `recover(starvation)` reported separately.
4. More than four transports complete.
5. Suite green, 0 skipped.

Write every number down as measured, pass or fail. **A failed criterion
is reported and the gate is not ticked** — that is this repo's own
convention and M6.6's.

- [ ] **Step 5: Write it up and commit**

Append an M6.7 section to `m6/PROOF.md` carrying the five criteria with
their measured values, the auto-RESET split, the escalation counts
(`AVOID`, `NUDGE`, `BLOCKED` from the nav logs) and the seed. Remove
nothing. Update `README_m6.md` with the escalation states and the
watchdog.

```bash
git add -A m6/ assets/m6-fleet/
git status --short          # nothing outside m6/ and assets/
git commit -m "m6.7: a truck that gets itself out, measured"
```

---

## Self-Review Notes

Spec coverage, section by section: §3.1 → Task 1; §3.2 → Task 2; §3.3 →
Task 3; §4.1 → Task 4; §4.2 → Task 5; §4.3 → Task 6; §5's file list is
the File Structure table; §6's test list is distributed across Tasks
1-6 verbatim; §7's five criteria → Task 7 Step 4.

Names defined once and used consistently: `avoid.buckets`,
`avoid.free_heading`, `avoid.FREE_M`, `avoid.MAX_SWING_RAD`,
`avoid.BUCKET_RAD` (Task 1); `nav_core.AVOID/NUDGE/BLOCKED`,
`HOLD_PATIENCE_S`, `NUDGE_M`, `NUDGE_MAX`, `SCAN_SIGN`,
`NavCore._escalate`, `NavCore._clear_escalation` (Task 2);
`progress.Progress.note/stalled_for/forget`, `PROGRESS_M`, `PROGRESS_S`,
`STALL_GIVE_UP_S` (Task 4); `FleetManager.progress`,
`FleetManager.stalled`, `FleetManager._stall_pass`, the document's
`"stalled"` key (Task 5); `scripted_writer.classify`,
`live["pf_violated"]` (Task 6).

The one risk this plan cannot resolve on paper is `SCAN_SIGN`, and Task
2 Step 1 writes the test that pins it before the implementation exists.
