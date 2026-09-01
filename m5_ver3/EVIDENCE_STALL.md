# EVIDENCE_STALL.md — the no-progress class, from a teleport to a cycle nobody touched (G5)

`EVIDENCE_FILM.md` §6 shipped a film of one autonomous pallet cycle. The
owner watched it, and at 1:40–2:24 he watched the truck **arrive at a
pose it had not driven to**. That was the pallet cycle's "recover empty
Nav2 miss to staging": a `set_pose` over a Nav2 leg that had failed.

> **kurtarma müdahaleleri hiç doğru değil; git kök nedeni bul, onu
> çöz.**
> — owner ruling 2026-09-01, [`AMR-DEC-004`]

**This file is the root cause and its removal.** It is the one failure
class this track never closed — first seen on 2026-08-27 as an
unexplained `START_OCCUPIED 205`, carried through F4 and F5 as a named
residual, and finally reproduced on demand, measured, attributed,
attacked with a seven-file parameter sweep and three structural
candidates that all failed, and then made structurally impossible on the
legs that met it.

Everything below was taken on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, gz-sim 8.11.0, RTX 4050) **headless**, `traction=nominal`,
`arm=wheel+imu`, `loc=amcl@735cdbc6`, on the full autonomous stack.
Every count in it was recomputed from the session archive under
`m5_ver3/logs/evidence/` by the method each table names — not copied
forward from a report.

---

## 0. The answer, before the working

| | |
|---|---|
| **what the owner refused** | a `set_pose` recovery inside a film of autonomy — [`AMR-DEC-004`], 2026-09-01 |
| **the class** | at an adverse entry heading MPPI's path critics lose authority, the softmax update collapses onto the optimiser's own prior, and the truck holds a **wrong-direction creep at ~0.081 m/s** until a watchdog or the planner gives up |
| **its fingerprint** | a plateau of ≥20 s inside 0.050–0.120 m/s. **29** of the **55** ordinary-service runs that ended on a named terminal carry one, and every one of the 29 sits at **0.0777–0.0901 m/s, mean 0.0840** — across 4 days, 12 different `nav2.yaml` fingerprints, 7 different goals and both terminals |
| **its terminals** | watchdog `no_progress` at 30 s / 0.50 m; `START_OCCUPIED` **205** once the crept footprint reaches lethal cost; historic **104** |
| **the reproducer** | one seeded pose — world **(−0.438, +9.736) yaw −2.7338 rad**, 0.4078 rad off the −π axis — driven **64 times**. Under MPPI: **3 arrivals in 49 trials over nine parameter files**; the first **18 failed 18 of 18** |
| **candidate causes removed, effect unchanged** | plan truncation, `change_penalty`, `vx_std`, the 1 Hz replan itself (F1), direction-swap refusal (DSP), and total plan commitment (DSP `hold_all`). **Commit mode refused 92 % of the replans and the creep did not move.** A cause you can delete without changing the effect is not the cause |
| **the fix, owner-ruled** | [`AMR-DEC-005`]: the reversal-heavy legs leave MPPI for **RegulatedPurePursuit with `allow_reversing`**. No sampler, no critics, no prior — the state the creep *is* is not reachable |
| **what it bought, measured** | `stage_s5` adverse **7/8** (MPPI on the same seed: 3 arrivals in 49), longest plateau **≤3.0 s**; `stage_s5` normal **4/4** at 29.8–31.7 s; bay-exit transit **6/6** at 26.8–29.0 s (was **0/2**, both crept) |
| **the mapping is per ORIGIN** | the 17.00 m spawn straight keeps **MPPI** (8/8; RPP 7/8) — `spine_north_from_bay` is the bay-exit row and it is RPP. One pose, two rows, pinned equal by `tests/test_nav2_params.py` |
| **acceptance** | **two full cycle pairs, 48 legs, every one `rc=0`**, four docks `success True error 0`, **ZERO** `nav2 miss recovered` lines, **ZERO** 205 |
| **suite** | **1218 passed** at `6b36f20`. This file changed no code and the suite was re-run to prove it |
| **still open, named** | the lateral-excursion class on the 17 m leg (both controllers, ~1/8, and it is **not** this class — it carries no plateau); `station_approach` still on MPPI; the cusp steer-ceiling clamp; a first dock that takes 123–129 s |

---

## 1. The class, and the four things it is not

### 1.1 The signature

The watchdog's own words are `no_progress`: `SimpleProgressChecker` at
`required_movement_radius` 0.50 m and `movement_time_allowance` 30 s
(`nav2.yaml`, `general_goal_checker` block). What it abandons is a truck
that is *moving* — just not usefully. `drive_goal.py record` writes
`outcome=no_progress`, `action_status=-1`, `error_code=-1`.

The second terminal is louder and it is the same disease. Once the truck
has crept far enough sideways that its **grown** footprint (x
[−2.4150, +1.4000], y [±0.6690]) sits on a lethal cell, the next
`ComputePathToPose` returns `START_OCCUPIED`. On this rig, from
`/opt/ros/jazzy/share/nav2_msgs/action/ComputePathToPose.action`:

```
uint16 UNKNOWN=200      uint16 START_OCCUPIED=205
uint16 TIMEOUT=207      uint16 NO_VALID_PATH=208
```

**205 is not in the tree's recovery set.** `navigate_to_pose_tricycle_v3.xml`
guards its `RoundRobin name="RecoveryActions"` behind
`WouldAPlannerRecoveryHelp`, and nav2 1.3.12's condition arms itself on
`{UNKNOWN, TIMEOUT, NO_VALID_PATH}` — 200, 207, 208. A planner that
answers 205 gets no clear-costmap, no wait, no retry; the tree simply
fails. This is upstream behaviour and it is recorded here as an upstream
question, not as something this file fixed.

### 1.2 The incidence, counted

**Method.** Every `kind=goal` session directory under
`m5_ver3/logs/evidence/` (272 of them). Sessions whose first
`ground_truth.csv` row is the seeded adverse pose of §2 are **excluded**
— those are experiments, not service. What is left is 208 sessions:
every goal and case this track has ever driven in ordinary conditions.

**And one definition, used identically everywhere below.** A *creep
plateau* is the longest unbroken run of `cmd_vel.csv` samples whose
commanded speed sits in **0.050 – 0.120 m/s**, reported as its wall
duration and as the mean speed inside it. The band is not chosen to
flatter: it is `nav.direction_hold.hold_speed_mps` 0.05 at the bottom
and a third of the 0.300 m/s transit ceiling at the top, and every arm
in this file is scored on it. Where a tighter band (0.070 – 0.095 m/s, the DSP header's
own measured creep window) is used, it says so.

| | sessions | arrived | `no_progress` | 205 | other |
|---|---|---|---|---|---|
| whole ordinary-service archive | **208** | 148 | 29 | 23 | 208 ×2, 104 ×1 |

Sixty non-arrivals in 208 attempts. Of the 55 that are `no_progress` or
a planner error code, **29 carry a creep plateau of 20 s or longer**,
and the speed of those 29 plateaus is the tightest number in this file:

| | value |
|---|---|
| plateau mean speed, min → max | **0.0777 → 0.0901 m/s** |
| plateau mean speed, mean of 29 | **0.0840 m/s** |
| plateau duration, min → max | 20.1 → 140.9 s |
| spread over days | 2026-08-27 (15), 08-28 (1), 08-29 (3), 09-01 (10) |
| spread over `nav2.yaml` fingerprints | 12 |
| spread over goals | `spine_north` 14, `stage_s5` 7, `ring_corner` 4, `ring_stress` 1, `aisle_end` 1, `ring_s5_junction` 1, `spine_cross` 1 |

Twelve parameter files, seven destinations, four days, both terminals —
**one speed**, to within 1.2 cm/s across the whole envelope. That is not
a tuning problem with several faces. It is one mechanism with one
operating point.

**On the file this track shipped at F5 close** (`nav_params_md5`
`3ed626ce`), ordinary service only:

| goal / case | sessions | arrived | `no_progress` | 205 |
|---|---|---|---|---|
| `spine_north` | 27 | 20 | **7** | 0 |
| `stage_s5` | 21 | 18 | 1 | **2** |
| `ring_s5_junction` | 5 | 1 | **2** | **2** |
| `station_s5_staging` | 5 | 5 | 0 | 0 |
| **total** | **58** | **44** | **10** | **4** |

Fourteen non-arrivals in fifty-eight. That is the number the film's
recovery existed to hide.

**On the file this file closes on** (`04aa49ee`), ordinary service only:

| goal / case | sessions | arrived | `no_progress` | 205 |
|---|---|---|---|---|
| `spine_north` | 32 | 29 | 3 | 0 |
| `stage_s5` | 11 | 11 | 0 | 0 |
| `spine_north_from_bay` | 3 | 3 | 0 | 0 |
| **total** | **46** | **43** | **3** | **0** |

And the three are named, individually, in §8. Two of them are the
bay-exit MPPI transits this file's fix moved off MPPI (§5); one is the
excursion class, which is a different animal (§8.1).

### 1.3 What it is not — four exonerations, each a measurement

**(a) It is not the plant.** The two bay-exit MPPI transits that made
[`AMR-DEC-005`]'s implementation note are the cleanest specimen in the
archive, because in them the creep is the *whole run*:

| session | span | max commanded speed | distance driven | plateau |
|---|---|---|---|---|
| `goal-spine_north-20260901-205935` | 29.9 s | **0.108 m/s** | **2.40 m** | 29.5 s @ 0.0799 |
| `goal-spine_north-20260901-211229` | 29.9 s | **0.101 m/s** | **2.40 m** | 28.8 s @ 0.0806 |

0.0803 m/s × 29.9 s = **2.40 m**. The truck delivered *exactly* what it
was told, for thirty seconds, and what it was told was a creep. Whatever
is broken is upstream of the wheels. `EVIDENCE_SENSORS.md`'s wheel-radius
identity and `EVIDENCE_LATERAL_TUNE.md`'s slip ladder have nothing to
answer here: `traction=nominal`, `slip_compliance_lateral=7.0`,
`slip_compliance_longitudinal=7.0`, `source=… (no override was applied)`
is written into **every** session in this file, arriving and failing
alike.

**(b) It is not the goal checker.** `PositionGoalChecker` at
`xy_goal_tolerance` 0.60 m cannot be blamed for a run that never came
near it. Ground-truth closest approach to the goal, adverse MPPI
failures:

| session | closest truth to goal |
|---|---|
| `case-stage_s5-20260901-164807` | 2.997 m |
| `case-stage_s5-20260901-171743` | 3.720 m |
| `case-stage_s5-20260901-172119` | 4.602 m |
| `case-stage_s5-20260901-181530` | 5.594 m |
| `case-stage_s5-20260901-180005` | 5.698 m |
| `goal-spine_north-20260901-205935` | 7.787 m |

Against arrivals at 0.504–0.649 m. The box was never in play; the
0.5 m/1.5 rad endgame argument of `nav2.yaml`'s goal-checker block is a
different finding and it is not this one.

**(c) It is not localisation.** Same reasoning as (a) from the other
end: the *command* was the creep, and a command is produced from a
belief. But the belief cannot be the discriminator either, because the
adverse seed is the **same pose to four decimal places** on all 64
trials (§2) and the same stack arrived on some of them. A localisation
error that fired on 46 of 49 identical starts and not on the other 3 is
not a localisation error, it is a bifurcation in the thing consuming the
pose.

**(d) It is not the rig's real-time factor.** The strongest form of this
is one bringup holding both outcomes. `run-20260901-170942` carries
`case-stage_s5-20260901-171204` (**arrived**, 123.8 s),
`case-stage_s5-20260901-173155` (**failed**, 101.0 s plateau) and the
four normal-entry arrivals of §4.4 — same Gazebo, same hour, same
children. And `run-20260901-213222` carries **all 22 trials** of the
controller A/B in §5.3, RPP and MPPI, bay exit and spawn, in one
unbroken session. A rig that was too slow would not have arrived 20
times inside it.

---

## 2. The reproducer, and the seed that had to be read back

A class that fires on 14 of 58 ordinary runs cannot be debugged. The
first thing G5 built was a way to make it fire every time.

**The adverse entry heading.** `stage_s5` is a station approach: the
truck stands on the ring's north leg and is asked for the S5 staging
pose at world (7.000, 6.575). Sent from the spawn with the forks
pointing along −x, it arrives. Sent from a pose whose heading is turned
**0.4078 rad off that axis**, it does not. The seed:

```
world (−0.438, +9.736)   yaw −2.7338 rad      (= −(π − 0.4078))
```

It is a *seeded* pose and not a driven one, and the archive proves it:
across all 64 adverse trials the first `ground_truth.csv` row is that
triple to four decimal places, every time. The normal-entry trials, by
contrast, scatter — (−0.515, +10.012) yaw +3.1290, (−0.535, +10.034)
yaw +3.1296, (−0.581, +10.026) yaw +3.0697, (−0.576, +10.019) yaw
+3.1252 — because the truck *drove* to them.

**What it does, under MPPI.**

| arm | trials | arrived | `no_progress` | 205 |
|---|---|---|---|---|
| MPPI (`navigate_to_pose_tricycle_v3.xml`), all parameter files | **49** | **3** | 28 | 18 |
| the first 18 of them, five parameter files, in order | **18** | **0** | 8 | 10 |

Eighteen consecutive failures over five different `nav2.yaml`
fingerprints before the first arrival. Three arrivals in forty-nine
across nine fingerprints. **That is a reproducer.**

### 2.1 The seed had to be verified, and the first attempt was not

The lesson this campaign paid for twice: **a pose published to
`/initialpose` is a request, not a fact.** A fire-and-forget publish
into a stack that has not finished coming up is dropped in silence by
DDS, and the trial then runs from wherever the truck actually was —
which produces a *void* trial that looks exactly like an arm that
worked. The trials counted anywhere in this file are the ones whose
start pose was **read back from `tf` and written into
`ground_truth.csv`** before the goal was sent; that read-back is what
the tables of §2 are filtered on, and it is why "64 adverse trials"
can be stated as a count rather than an intention.

This is the same failure mode `AMR-LES-020` (bridge starvation) and
`AMR-LES-023` (restart both arms) record from other angles: on this
stack, anything published once and not confirmed is a coin toss.

---

## 3. The mechanism, live

Three committed sources carry the mechanism, and they agree.

### 3.1 The plan flips under the moving truck

`bt_direction_stable/src/direction_stable_path.cpp`, the file header:

> Smac replans at 1 Hz from the moving pose. At the adverse entry the
> fresh plan's FIRST-SEGMENT DRIVING DIRECTION flips — **13-15 times per
> run, measured** — and MPPI's candidate cloud is anchored on the last
> command, so it cannot span the flip: every candidate points the wrong
> way […]

The vehicle is standing at a heading from which the Reeds-Shepp planner
can reach the goal two ways — nose-first through a cusp, or
counterweight-first through a different one — and their costs are close
enough that a metre of motion swaps the winner. At 1 Hz, that is a plan
whose *first segment* changes sign once a second under a truck that is
already moving.

### 3.2 MPPI cannot span the flip, and it says so in the source

The optimiser samples around the previous control sequence. Its
acceleration envelope is the plant's — `ax_max: 0.35`, `ax_min: -0.35`
m/s², which `nav2.yaml` derives from `config.yaml`'s `navcmd.accel_mps2`
and which the converter and smoother both enforce at 0.017500 m/s per
0.05 s tick. The spread around that anchor is `vx_std: 0.2`. The result
is a candidate cloud that is *centred on the direction the truck is
already going*, and when the plan's first segment points the other way,
**no candidate in the cloud scores well on it.**

The critic that would have noticed then switches itself off. From
`nav2.yaml`'s `PathAlignCritic` block, quoting nav2 1.3.12's
`path_align_critic.cpp` verbatim:

```cpp
// Don't apply when first getting bearing w.r.t. the path
utils::setPathFurthestPointIfNotSet(data);
const size_t path_segments_count = *data.furthest_reached_path_point;
if (path_segments_count < offset_from_furthest_) {
  return;
}
```

`offset_from_furthest: 12` on this file, derived from the vehicle's own
1.25 m minimum turning radius over the floor's measured 0.10 m plan
spacing. `furthest_reached_path_point` is **not a tunable** — it is the
prediction horizon measured in path points. A truck creeping at
0.081 m/s reaches path index **0**. Zero is less than twelve, so the
only critic in the file that penalises driving *parallel to* the path
returns without scoring, exactly as designed, exactly when it is needed
most.

`nav2.yaml`'s `FollowPathRPP` header states the whole chain in one
sentence:

> at an ADVERSE ENTRY HEADING the MPPI above loses its path critics —
> PathAlign self-gates at `furthest_reached_path_point` 0 and the Goal
> critics are out of range — and the softmax update then collapses onto
> its OWN PRIOR, holding a sustained WRONG-DIRECTION creep of about
> **0.081 m/s** until the footprint reaches lethal cost and the next
> plan comes back START_OCCUPIED 205.

The remaining critics are not zero — they balance. `GoalCritic` and
`PathFollowCritic` both carry `threshold_to_consider: 1.4` and the truck
is metres outside it — §1.3 (b) is the table of how many. What is left
is `ObstaclesCritic` and
`PreferForwardCritic` against the prior, and the equilibrium of that
sum is a number this archive has now measured 29 times: **0.084 m/s,
±0.006.**

### 3.3 And then the terminals

- **`no_progress`** if the creep is roughly straight: 0.50 m in 30 s is
  0.0167 m/s, and a 0.081 m/s creep *along* the goal direction would
  clear it — so the ones that trip the watchdog are the ones creeping
  sideways or backwards.
- **205** if the creep walks the grown footprint onto a lethal cell
  first. 18 of the 46 adverse MPPI failures took this exit, and it is
  the one with no recovery behind it (§1.1).
- **104** appears once in the archive (`spine_cross`, 2026-08-27) and is
  recorded for completeness.

---

## 4. The refutations — every candidate removed, the effect unchanged

Every arm below was run on the §2 seed, on this rig, and its sessions
are on disk. The parameter arms are identified by their `nav2.yaml`
fingerprint (`nav_params_md5` in each session), which is what the
sessions record; **the file diffs behind those fingerprints were working
edits and were not committed, so which fingerprint carried which knob is
not recoverable from this repository, and this file does not guess.**
What *is* on disk is what every one of them did, and it is the same
thing.

### 4.1 The parameter arms

`nav2.yaml`'s own line names the knobs that were tried and refused: the
class is *"invariant to path length, to `prune_distance`, to
`change_penalty`, to the plan replacement rate and to `vx_std`"*. On the
adverse seed:

| fingerprint | trials | arrived | 205 | `no_progress` | longest plateau (0.050–0.120 m/s) |
|---|---|---|---|---|---|
| `9487be02` (13:16) | 3 | 0 | 2 | 1 | 6.0 s @ 0.0808 |
| `334232d9` (13:24) | 4 | 0 | 3 | 1 | 4.8 s @ 0.0810 |
| `5b74af35` (13:34) | 3 | 0 | 0 | 3 | 7.7 s @ 0.0837 |
| `69038ebc` (13:41) | 4 | 0 | 3 | 1 | 0.3 s @ 0.0820 |
| `3ed626ce` (13:48, the shipped file) | 3 | 0 | 2 | 1 | 4.4 s @ 0.0849 |
| `69981ebd` (14:11) | 5 | **1** | 2 | 2 | 10.7 s @ 0.0822 |
| `879357e1` (14:48) | 5 | 0 | 0 | 5 | 0.9 s @ 0.0835 |

Twenty-seven trials, **one arrival**, and the creep speed constant to
four hundredths of a metre per second across every one of them. One arm
is visibly *worse* than the shipped file (`879357e1`, five for five,
every trial abandoned by the watchdog rather than the planner). One arm
made the runs *longer* without making them succeed (`69981ebd`, spans
of 86–102 s against the shipped file's 36–57 s, and 25.80 m driven on
the trial that did arrive). **No arm removed the plateau.**

### 4.2 F1 — remove the replan entirely

If the flip is the cause, a plan that never changes has no flip in it.
The F1 pilot ran a tree that computed one plan and drove it —
`f1_bt.xml` in six sessions, and the archive proves the intervention:
**`plan.csv` holds exactly ONE plan per run**, against 24–167 in every
other arm in this file.

| session | plans | outcome | span | driven |
|---|---|---|---|---|
| `case-stage_s5-20260901-151054` | **1** | `no_progress` | 65.0 s | 18.55 m |
| `case-stage_s5-20260901-151403` | **1** | `no_progress` | 62.7 s | 13.67 m |
| `case-stage_s5-20260901-151700` | **1** | arrived | 36.5 s | 10.35 m |
| `case-stage_s5-20260901-151900` | **1** | arrived | 35.6 s | 10.10 m |
| `case-stage_s5-20260901-152054` | **1** | arrived | 37.4 s | 10.47 m |

**3 of 5** — the best adverse result MPPI ever produced, and it is not
shippable. The DSP header records what it cost:

> Removing it (the F1 pilot) removed the flips, the creep and the 205 —
> and lost terminal overrun correction with them: **four overshoot
> failures and a transformed plan frozen 0.66 m behind the truck.**

A controller with no fresh plan cannot correct a terminal overrun,
because the only thing that would tell it to is a plan computed from
where it now is. F1 trades one class for another.

### 4.3 DSP direction-only — refuse the swap

`DirectionStablePath` (§6) with `hold_all: false` refuses a fresh plan
only when it reverses the driving direction of the segment the truck is
standing on. Eight adverse trials and four normal, in
`run-20260901-164557` and `run-20260901-170942`:

| session | outcome | plateau (0.050–0.120 m/s) |
|---|---|---|
| `164807` | 205 | 83.3 s @ 0.0861 |
| `165315` | **arrived** 29.4 s | 0.7 s |
| `171204` | **arrived** 123.8 s | 47.7 s @ 0.0823 |
| `171743` | 205 | 87.4 s @ 0.0862 |
| `172119` | `no_progress` | 47.5 s @ 0.0876 |
| `172428` | 205 | 57.3 s @ 0.0835 |
| `172804` | 205 | 70.9 s @ 0.0851 |
| `173155` | `no_progress` | 101.0 s @ 0.0829 |

**2 of 8 adverse**, four of them 205. Normal entry `174451` / `174814` /
`175140` / `175503`: **4 of 4**, 30.6–31.3 s, longest plateau **0.9 s**.

The holds fired as designed. `config.yaml`'s `nav.direction_hold` block
records what happened underneath them: *"20 flips were held as designed,
and about 92 SAME-direction fresh plans were accepted underneath them.
Their shape chatter — same sign, different geometry, every second —
walked the truck 3.0 m off and put its footprint on lethal cost, which
is the same 205 by a different road."*

### 4.4 DSP commit — refuse *every* replacement, and the decisive result

`hold_all: true` is that hypothesis as a knob: while the truck is
moving, every fresh plan is refused and the accepted one is driven,
until a cusp, a stop, a consumed plan, or `hold_max_s` 10.0 s. Eight
adverse and four normal, `run-20260901-175802`:

| session | outcome | plateau |
|---|---|---|
| `180005` | `no_progress` | 36.3 s @ 0.0837 |
| `180232` | `no_progress` | **28.6 s** @ 0.0819 |
| `180605` | `no_progress` | 32.8 s @ 0.0847 |
| `180826` | `no_progress` | 33.6 s @ 0.0796 |
| `181147` | `no_progress` | 36.5 s @ 0.0827 |
| `181530` | `no_progress` | 34.3 s @ 0.0843 |
| `181753` | `no_progress` | **39.3 s** @ 0.0809 |
| `182141` | `no_progress` | 38.5 s @ 0.0818 |

**0 of 8.** Normal entry: `182535` arrived 33.7 s, `182958`
`no_progress` (21.6 s plateau), `183414` arrived 31.1 s, `183819`
`no_progress` (20.1 s plateau) — **2 of 4, a regression on the one entry
the film uses.**

And this is the experiment that ended the search:

> Commit mode refused **92 % of the replans** — 66 of 72 on one run, 61
> of them SAME-DIRECTION, which is precisely the chatter the paragraph
> above blames — **and the creep did not change.** A cause you can delete
> without changing the effect is not the cause: THE CREEP IS NOT MADE BY
> PLAN REPLACEMENT, and no setting of `hold_all` fixes it.
> — `direction_stable_path.cpp`

The two arms' plateaus, side by side, recomputed here from
`cmd_vel.csv`: direction-only **47.5–101.0 s at 0.0823–0.0876 m/s**;
commit **28.6–39.3 s at 0.0796–0.0847 m/s**. Ninety-two per cent of the
input removed, and the output moved by less than a centimetre per
second. Both arms' ranges reproduce `config.yaml`'s published figures to
within 0.001 m/s.

**Neither arm cleared the bar, so `hold_all` was not "selected".** It is
left at `false` because `false` is the value that does not regress the
normal entry — and `config.yaml` says exactly that, in those words.

---

## 5. The fix — [`AMR-DEC-005`], and it is a controller, not a number

> the MPPI blind-inertia creep class […] is resolved by switching the
> **stage/approach Nav2 legs to RegulatedPurePursuit with
> `allow_reversing`** — deterministic tracking, no sampling, no critic
> gating: the class is structurally impossible there.
> — owner ruling 2026-09-01

### 5.1 Why it is structural

RPP's command is a closed-form function of one point on the path:
lookahead point → curvature → (v, ω). There is no sample set, no critic
sum and no prior, so *"the optimiser's own prior wins"* is not a state
the controller has.

The one mechanism the whole choice rests on is the cusp, and
`nav2.yaml` reads it out of the shipped binary's source rather than
assuming it —
`nav2_regulated_pure_pursuit_controller/src/regulated_pure_pursuit_controller.cpp`:

```cpp
192   // Check for reverse driving
193   if (params_->allow_reversing) {
194     // Cusp check
195     const double dist_to_cusp = findVelocitySignChange(...);
196
197     // if the lookahead distance is further than the cusp,
198     // use the cusp distance instead
199     if (dist_to_cusp < lookahead_dist) {
200       lookahead_dist = dist_to_cusp;
201     }
```

and `findVelocitySignChange` (:519) walks the transformed plan taking
the dot product of successive segments and returns the distance to the
first negative one (:536-541). **The carrot is never placed past a
cusp.** The travel direction is then read off that carrot and off
nothing else (:226-229). The vehicle drives *to* the cusp, the plan
behind it is pruned, the next carrot lands on the other side of
`base_link`, and the sign flips — with no optimisation anywhere in it.

`allow_reversing: true` is structural on this truck and not a
preference: the forks are at model −x, so this vehicle's ordinary travel
direction *is* nav2's reverse, and with the flag false `x_vel_sign` is
pinned at +1.0 and every command is counterweight-first.

### 5.2 What it measured on the approach leg

`case stage_s5` on `navigate_to_pose_tricycle_v3_rpp.xml`, eight adverse
trials in one bringup (`run-20260901-194955`) and four normal:

| adverse trial | outcome | span | plateau |
|---|---|---|---|
| `195834` | arrived | 90.7 s | 2.5 s |
| `200141` | arrived | 93.8 s | 3.0 s |
| `200458` | arrived | 76.3 s | 2.2 s |
| `200749` | arrived | 48.9 s | 0.5 s |
| `201008` | arrived | 50.0 s | 2.0 s |
| `201220` | `no_progress` | 38.9 s | 0.7 s |
| `201417` | arrived | 47.0 s | 0.2 s |
| `201629` | arrived | 50.3 s | 1.9 s |

**7 of 8.** `config.yaml`'s own `nav.cases.stage_s5` row records the
baseline it replaced as *"0 of 6 under MPPI"* from this entry; the
archive census of §2 puts the same claim at its widest — **3 arrivals in
49 MPPI trials** on this seed across nine parameter files. Either way it
is the same direction and the same size. Longest plateau anywhere in the
arm: **3.0 s** — against 47.5–101.0 s on the arm it replaced. On the
tighter 0.070–0.095 m/s creep band it falls to **0.6 s**. The one loss
carries the *shortest* plateau but one: it is not this class.

| normal trial | outcome | span | plateau |
|---|---|---|---|
| `202207` | arrived | 30.7 s | 0.0 s |
| `202558` | arrived | 30.5 s | 0.0 s |
| `202919` | arrived | 31.7 s | 0.2 s |
| `203240` | arrived | 29.8 s | 0.5 s |

**4 of 4 at 29.8–31.7 s**, which is the shape the pallet cycle actually
drives, unregressed.

### 5.3 The transit leg, and why the mapping is per ORIGIN

[`AMR-DEC-005`]'s implementation note named the leg the campaign had not
measured: both acceptance cycle pairs still carried exactly one
`nav2 miss recovered`, on the MPPI transit **leaving the S5 bay**. That
is `nav.cases.reverse_out`'s geometry and nav2 issue #5714's — a 3.815 m
truck with a 1.25 m turning radius at the mouth of a 4.00 m bay, forks
pointed south into it, whose only way out is counterweight-first through
a Reeds-Shepp cusp.

All twenty-two trials below ran in **one bringup**, `run-20260901-213222`.

| arm | from | n | arrived | span |
|---|---|---|---|---|
| **RPP** | S5 bay, post-undock (7.065, 6.435) yaw +1.5439 | 6 | **6** | 26.8 – 29.0 s |
| **MPPI** | the same pose (`run-…205023` / `…210414`) | 2 | **0** | both `no_progress` at 30.0 s, 2.40 m driven, 28.8/29.5 s plateau |
| **RPP** | spawn, the 17.00 m straight | 8 | **7** | six clean 55.6–56.0 s; one recovered 81.3 s; **one lost** `no_progress` 75.2 s |
| **MPPI** | the same 17.00 m straight | 8 | **8** | seven clean 56.5–57.2 s; one recovered 65.9 s |

**0 of 2 became 6 of 6 on the bay exit, and no creep appeared once.**
But on the spawn straight RPP *lost* a run MPPI would have recovered —
so a single `controller:` key on `nav.goals.spine_north` would have paid
for one entry with the other.

The decision (G5 Task 9) is a **second goal row**.
`nav.goals.spine_north_from_bay` is the same target pose under a second
name, and the name is the **origin it is driven from** rather than the
place it goes — the only row in that table of which that is true, and
true because the origin is the only thing that ever distinguished the
two drives. It carries `same_pose_as: "spine_north"`, and
`tests/test_nav2_params.py` holds the pair to one x, one y and one
travel heading in both directions: an *undeclared* duplicate pose is
refused as a typo, and a *declared* one that has drifted is refused as a
second destination wearing the first one's name.
`tools/pallet_cycle.plan_cycle` picks between them by where the truck is
standing when the transit starts.

So: the 17.00 m spawn straight keeps **MPPI**, the 7.91 m bay exit gets
**RPP**, and neither entry pays for the other.

### 5.4 What is given up, stated

- **No dynamic obstacle model.** RPP checks its one arc and refuses;
  MPPI steers around what it finds. On this floor nothing moves but this
  truck, and that is exactly why the transit legs keep MPPI.
- **No cross-track term.** RPP drives at a carrot. §8.1 is what that
  costs.
- **No kinematic model.** RPP emits `ω = v · curvature` and the
  feasibility of the pair is the converter's problem. §8.3.

---

## 6. The guard — `DirectionStablePath`, and its honest record

The decorator built in §4.3/§4.4 **did not cure the class** and it is
still in the tree. That is a decision and it is written down: it stays
as the seat belt on the MPPI legs, where the flip it refuses is real
even though it is not the cause of the creep.

**What it is.** `m5_ver3/bt_direction_stable/` — the only C++ package on
this track, one shared library, built by
`tools/install_bt_direction.sh` into the operator's own `$HOME` with no
sudo, `dlopen`ed by `bt_navigator` because `nav2.yaml` names it in
`plugin_lib_names`, and placed in the tree by
`behavior_trees/navigate_to_pose_tricycle_v3.xml`. `m5v3.sh start --nav`
refuses by name if the library is not there.

**What it refuses.** A fresh plan whose first-segment driving direction
reverses the direction of the segment the truck is *currently standing
on* — read where the truck now is, not where it set off, because a plan
with a cusp in it changes direction on its own, legitimately, and a
decorator that refused that would refuse the terminal manoeuvre of a
plan it had already agreed to.

**Every hold is bounded, and the bounds are the point.**

| bound | value | why, and what it did |
|---|---|---|
| `hold_speed_mps` | 0.05 | below it the truck is not driving and a fresh plan costs nothing. **Measured**: every creep plateau this failure produced sits in 0.078–0.093 m/s; a cusp and a stop pass through zero |
| `consume_floor_m` | 0.3 | an accepted plan with less than this left is a stub. **Never fired in 24 trials, and that is recorded rather than hidden** — the speed rung catches the terminal approach first, every time |
| `hold_max_s` | 10.0 | an unbroken hold streak older than this takes the fresh plan and logs `hold expired`. Chosen to sit *inside* the range the failure produces (streaks of 7 and 15 holds at 1 Hz). Fired 0–1 times a trial on direction-only, 4–9 on commit; **no trial's outcome turned on it** |
| stale odometry | 1.0 s (not a config key) | if the estimator stops speaking, `speed_` freezes at its last value, which above `hold_speed` would latch the hold for ever. Aged and **failed OPEN by name** |

**It holds a plan; it never invents one.** The only path it can write to
the blackboard is a path the planner produced and this node already
accepted. Child `FAILURE` and child `RUNNING` pass through untouched, so
no recovery the tree has is affected. **It is not a safety function** —
protective stop, e-stop and safe torque off are onboard and hardwired in
the plant this models.

**And the film enforces the other half of [`AMR-DEC-004`].** The ruling
has two consequences and the decorator is only one of them: *"a demo
film may not contain a `set_pose` intervention on the truck."*
`film_run.py` refuses a recovered cycle **by name** rather than cutting
around it — see `EVIDENCE_FILM.md`. A cycle that used the recovery has
no film in it.

---

## 7. Acceptance — two cycle pairs, 48 legs, nobody touched the truck

[`AMR-DEC-005`]'s bar: *"two full pallet cycles with zero
`nav2 miss recovered` lines"*, and the implementation note raised it to
two cycle pairs at **zero interventions**.

`nav_params_md5` `04aa49ee`, `nav_config_md5` `a5142b31`,
`nav_bt_md5` `ae988604`, on `run-20260901-224635` and
`run-20260901-225940`.

### 7.1 Pair A — `pallet-cycle-20260901-224803`

| leg | tool / tree | result |
|---|---|---|
| c1 transit `spine_north` (origin **spawn**) | `drive_goal record`, MPPI (`…_v3.xml`) | status **4**, error **0**, **57.19 s** |
| c1 stage `stage_s5` | `drive_goal record`, RPP (`…_v3_rpp.xml`) | status **4**, error **0**, **31.36 s** |
| c1 dock | `dock_bench record --from-staging` | `success True`, error **0**, retries 1 |
| c1 attach / lift / undock / carry / stage / dock / lower / detach / undock | `pallet_bench`, `/cmd_vel` bursts | `rc=0` each |
| c2 transit `spine_north_from_bay` (origin **bay**) | `drive_goal record`, **RPP** | status **4**, error **0**, **27.21 s** |
| c2 stage `stage_s5` | `drive_goal record`, RPP | status **4**, error **0**, **27.35 s** |
| c2 dock | `dock_bench record --from-staging` | `success True`, error **0**, retries **0** |
| c2 remainder | `pallet_bench`, bursts | `rc=0` each |

### 7.2 Pair B — `pallet-cycle-20260901-230108`

| leg | tool / tree | result |
|---|---|---|
| c1 transit `spine_north` (spawn) | MPPI | status **4**, error **0**, **57.24 s** |
| c1 stage `stage_s5` | RPP | status **4**, error **0**, **30.68 s** |
| c1 dock | plugin | `success True`, error **0**, retries 1 |
| c2 transit `spine_north_from_bay` (bay) | **RPP** | status **4**, error **0**, **26.31 s** |
| c2 stage `stage_s5` | RPP | status **4**, error **0**, **34.23 s** |
| c2 dock | plugin | `success True`, error **0**, retries **0** |
| all remaining legs | `pallet_bench`, bursts | `rc=0` each |

### 7.3 The three numbers that are the acceptance

| | |
|---|---|
| **legs** | `grep -c '^rc=0'` on each session file: **24 and 24** — every leg of every cycle, **48 of 48**, returned zero |
| **interventions** | `grep -c 'miss recovered'` on each session file: **0 and 0**. The recovery code is still in `pallet_cycle.py`, still armed, and it did not fire |
| **205** | across both run directories: **0**. The only `no progress` string in either is `controller_server`'s one-time startup WARN about the `current_progress_checker` parameter name |

The bay-exit transit — the leg that failed **2 of 2** under MPPI, that
fired the banned recovery both times, and that was the last intervention
left in a cycle — arrived at 27.21 s and 26.31 s.

---

## 8. What is still open, by name

### 8.1 The lateral-excursion class on the 17 m leg — and it is NOT this class

On the 17.00 m spawn straight, a small early heading error is sometimes
absorbed rather than corrected, and the truck rides several metres off
the y = +10.00 centreline. It fires under **both** controllers —
`config.yaml` records 2 of 8 on RPP (2.880 m and 2.859 m) and 1 of 8 on
MPPI (2.438 m). What differs is the endgame: MPPI's `PathAlignCritic`
scores a whole trajectory against the path and pulled its excursion back
at 2.44 m, arriving at 65.9 s; **RPP has no cross-track term at all**
and rode both of its excursions out, losing one (`no_progress` at
75.2 s, 21 collision throws, 5.19 m short).

**The measurement that separates it from this file's subject:**

| session | class | longest plateau |
|---|---|---|
| `goal-spine_north-20260901-214840` (RPP, lost) | excursion | **1.5 s** |
| `goal-spine_north-20260901-220056` (RPP, recovered) | excursion | **1.2 s** |
| `goal-spine_north-20260901-221056` (MPPI, recovered) | excursion | **0.8 s** |
| the 29 creep failures of §1.2 | creep | **20.1 – 140.9 s** |

There is no creep in an excursion. It is a second, smaller class on one
leg, it is why `spine_north` stayed on MPPI, and it is **not cleared**.
The sample is two against one and it will not carry more weight than
that.

### 8.2 `station_approach` is still on MPPI

It is the same class of leg as `stage_s5` — the same bay off the same
ring band — so an adverse entry heading is available to it too. It was
**not moved**, deliberately: it is a shipped-evidence case whose
approach figures in `EVIDENCE_NAV_V3.md` were measured behind MPPI, and
moving it would replace a recorded measurement with an unmeasured one.
G5's campaign drove `stage_s5` and the pallet cycle; it did not drive
this case. **The exposure that leaves is real and is named here.**

### 8.3 The cusp steer-ceiling clamp under RPP

RPP has nothing corresponding to MPPI's `AckermannConstraints`, and the
cusp clamp is applied *after* `getLookAheadDistance` and is not floored
by it — so approaching a cusp the carrot goes wherever the cusp is. Over
eight adverse trials and 13 354 commanded ticks the implied steer angle
`atan(L·ω/v)` passed the 1.25 rad commanded ceiling on **262 of them
(1.96 %)**, worst 1.5110 rad — past `model.sdf`'s 1.31 rad mechanical
stop. What happens is a **clamp, not a breach**: the converter truncates
the curvature, counts it on `/m5v3/navcmd/status`, and the truck
under-steers through the tightest tenth of a second of a cusp. Seven of
those eight arrived.

On the shape the pallet cycle actually drives — the four normal-entry
runs — it is **2 of 3362 ticks, 0.06 %**, and three of the four never
took the yaw rate above 0.2400 rad/s at all. There is **no parameter in
RPP that bounds the cusp clamp**; this is recorded so that a reader
sizing the steer axis knows which controller puts numbers on that
counter.

### 8.4 A first dock that takes 123–129 s, unexplained

In both acceptance pairs the **first** dock of the pair is five times
slower than the second, and the pattern is exact:

| pair | first dock | retries | second dock | retries |
|---|---|---|---|---|
| A | **129.0 s** | 1 | 18.3 s | 0 |
| B | **123.7 s** | 1 | 23.7 s | 0 |

(wall clock between the staging leg's record and the dock's record.)
Both succeeded, `error 0`. The retry is visible and the correlation is
perfect at n=2, but a single `opennav_docking` retry does not obviously
cost a hundred seconds, and **no mechanism is claimed here.** It is
written down as an observation with its four numbers so that whoever
looks next starts from evidence.

### 8.5 The arms this campaign never drove

`--fuse` and `--localize slam` were **not** measured with RPP in the
tree. The whole of this file is `arm=wheel+imu`, `loc=amcl`. A different
estimator changes the belief the carrot is computed from, and nothing
here says what that does. It is the same debt `EVIDENCE_NAV_V3.md`
recorded for MPPI, now owed twice.

### 8.6 Two questions worth reporting upstream

1. **`PathAlignCritic` self-gates hardest exactly when it is needed.**
   `offset_from_furthest` is compared against
   `furthest_reached_path_point`, which is the prediction horizon in
   path points — so a vehicle that has *slowed down* has a shorter
   horizon, reaches a lower index, and loses the only critic that
   penalises driving parallel to its path. The critic is disabled by the
   symptom it exists to correct. There is no parameter that separates
   "not yet oriented to the path" from "no longer moving along it".
2. **`START_OCCUPIED` (205) is absent from the planner recovery set.**
   `WouldAPlannerRecoveryHelp` arms on `{UNKNOWN 200, TIMEOUT 207,
   NO_VALID_PATH 208}`. A start pose that has become occupied is
   precisely the case a `ClearEntireCostmap` or a `BackUp` might fix,
   and it is the one code that gets neither.

### 8.7 What this file does not claim

- **It does not claim the class is gone.** It claims the class is
  structurally unreachable *on the legs that were moved*, and that the
  legs still on MPPI are named in §8.1 and §8.2 rather than quietly
  carried.
- **It does not identify which parameter arm was which.** §4.1 records
  what every fingerprint did; the edits behind the fingerprints were not
  committed and this file will not reconstruct them from memory.
- **It does not re-derive anything `nav2.yaml` already derives.** The
  RPP lookahead floor, the regulation radius, the `offset_from_furthest`
  gate and the budget are argued in that file and pinned by
  `tests/test_nav2_params.py`.
- **It re-ran the suite and changed no code.** `1218 passed` at
  `6b36f20`, which is the same number the fix wave closed on.

---

[`AMR-DEC-004`]: the owner ruling of 2026-09-01 — "set_pose recovery is
not autonomy; root-cause the Nav2 stall". Vault:
`projects/active/amr-agent/decisions/AMR-DEC-004.md`.

[`AMR-DEC-005`]: the owner ruling of 2026-09-01 — "RPP on the approach
legs". Vault: `projects/active/amr-agent/decisions/AMR-DEC-005.md`.
