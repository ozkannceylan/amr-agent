# m5-59 — triage the validation findings, and write the owner's TIA procedure

    brief:               docs/briefs/m5-59-validation-fix-triage.md
    status:              done
    invariants_touched:  none

## The one-line answer

**Three of the four findings need the CPU and all three fit in one sitting; the
fourth needs no TIA at all.** The procedure is
`plc/forklift/TIA-FIX-PROCEDURE.md` — 63 steps, six changes, one F-signature
change. Two things the brief did not ask for came out of reading the code:
**F2's published band is wrong in both directions and is wider than reported**,
and **F1 must not land without F3, or the 1.000 m/s teleop clip dies.**

---

## 1. The triage — which side each finding lives on

| # | Finding | TIA half | Agent half | Why the split falls there |
|---|---|---|---|---|
| **F1** | SLS/SS1 demands do not reach the vehicle | **Yes.** Two `ForkliftSafetyMirror` members; two copy statements and a third permissive conjunct in `FB_ForkliftTeleop`; two leaves on the `DemoCell` server interface | **Yes.** `interface`: two rows in `opcua-nodes.md` §11.2. `bridge`: a read slot for `Forklift/Safety/TorqueOffDemand` and a publisher on `/forklift/safety/torque_off_demand` | The permissive and the mirror copies are standard-program logic and the leaves are configured in TIA. The node **model** and the ROS publisher are not. **The F-program is not touched by F1 at all** — `SpeedMonitorDemand` and `TorqueOffDemand` already exist as FB2 outputs and DB3 statics, so F1 alone would not have changed the F-signature |
| **F2** | The shaft-doubt band | **Yes, and only TIA.** `SPEED_STANDSTILL_MAX` / `_NEG` `50`/`-50` → **`15`/`-15`** in FB2's Constant section | **No.** The vehicle's `motion_threshold_mps` **does not move** | Read both. The near-zero threshold is an **F-program constant** (build step 258). The motion threshold is `agv/forklift/config.yaml` `safe_speed.motion_threshold_mps` = 0.0014 — and it is derived, 98× above its measured rest floor and 64× below its slowest sustained-motion sample. Raising it would blind the only mechanism covering a frozen channel below 0.0308 m/s of tread speed. **The band closes entirely on the F-side** |
| **F3** | Nothing sends `WARN` | **No** | **Yes, `agv/` only.** `field_evaluation.py` implements `ZONE` and not `WARN`; the grammar is fixed in `plc/forklift-safety/SPEC.md` §11.2 | The sender is a vehicle-side script on a TCP link to the writer. No PLC object is involved |
| **F4** | Warning ceiling is autonomous-mode only | **Yes.** One temp, one new statement and one modified statement in `FB_ForkliftTeleop`; **and** `SPEED_LIMIT_ONSET_MAX` `T#1s500ms` → **`T#2s300ms`** in FB2 | Optional: an `hmi/` lamp on the warning node | Both halves are program constants and program logic. The onset budget is the half that would have been discovered **after** the session if F4 had been treated as an SCL-only change |

**Carried debts, both `plc/`, both documents, neither needing TIA:**

| Item | Ruling | Owner of the edit |
|---|---|---|
| `FIELD_LINK_STALE_MAX` = 1 s against a 1 Hz keepalive, reaped 10 ms early | **Keep the 1 s window; raise the source's keepalive.** The rule is *window ≥ 3 × ping period + one writer cycle*. At 5 Hz that is 0.65 s against a 1 s window; the field evaluation's present 2 Hz gives 1.55 s and does **not** satisfy it. Widening the window instead would degrade detection of a dead field source, which is the thing the window exists for | `plc/` §7.2 states the rule; `agv/` sets the ping rate to 5 Hz |
| `plc/forklift-safety/SPEC.md` §11 should state 0.40 s | Confirmed: the carrier's own 0.15 s window plus the writer's `MOTION_SILENCE_MAX` 250 ms. **Documentation only** — the writer constant does not change | `plc/`, one row in §11.2 |

**Neither of those is in this deliverable.** They are a `plc/` document brief and
I did not take it; the derivations above are complete enough to make it
mechanical.

---

## 2. F2 — the derivation, and the two numbers that were wrong

**The published band is wrong at both ends, and it is wider than reported.**

| | `docs/VALIDATION-M5.md` says | In force / measured | Where |
|---|---|---|---|
| Upper edge | 30.8 mm/s | **50 mm/s** | `SPEED_STANDSTILL_MAX` = `50`, build step 258, spec §11.3. 30.784 mm/s is `SPEED_DISCREPANCY_MAX`, a different constant answering a different question |
| Lower edge | 1.4 mm/s | **≈ 2.0 mm/s of body speed** | 0.0014 m/s is a **rate** — q95 of the per-ray range change — not a speed. At the worst measured rate-to-body ratio (0.715) it is a body speed of 2.0 mm/s, and that conversion is an extrapolation below 0.05 m/s |

**What each threshold must distinguish, and from what noise.** The motion
observation separates *the world is moving* from the observation's floor at rest
(0.0000143 m/s over 5 644 sustained-rest samples). The near-zero window separates
*this reading is a stopped shaft* from the reading heads' jitter at rest —
**σ = 5.47 mm/s per channel**, measured in the 0.00–0.02 m/s band, with
consecutive F-samples independent (lag-1 −0.0105). The two questions are
different and neither threshold is wrong alone. What nobody derived is the
window.

**Derived over the ten F-cycles the demand actually needs.** `ShaftDoubtNow` must
hold continuously for `SHAFT_DOUBT_TIME` = 1 s, and SL13 requires **both**
channels inside the window in every cycle, so a demand forms with probability
`p_in(v,W)^20`:

| Bound | Requirement | Gives |
|---|---|---|
| Detection — a stopped shaft under a rolling vehicle must demand | `p_demand(0,W) ≥ 0.5` per window | `W ≥ 11.6` mm/s |
| Exclusion — the measured teleop creep at ≈ 20 mm/s must not | `p_demand(20,W) ≤ 1e-9` | `W ≤ 18.0` mm/s |

**`W` = 15 mm/s**, the round value nearest the centre. Reading back: a stopped
shaft demands with **p = 0.885** in the first second (≈ 1.1 s expected, the `TON`
re-arming continuously); the measured creep at 20 mm/s gives 1.3e-15; Nav2's
from-rest tread speed gives 3.7e-30.

**And the healthy vehicle is excluded by construction, not by a gap.** Nav2's
closed-loop smoother cannot exceed `max_accel × dt` from rest, so
`v = min(0.025, 0.02381/κ)`; the F-program measures **tread** speed, `v / cos δ`.
That is `0.025 / cos δ ≥ 0.025` in the acceleration-limited regime and
`0.025 / sin δ ≥ 0.0259` in the curvature-limited one — **minimum 25 mm/s at
every steer angle**, 1.83 σ above the new window. The 0.025 m/s in the report is
not a coincidence; it is that floor.

**What the new value does not cover, stated on the row** (spec §11.1b, table of
four): a teleop operator **sustaining** below ≈ 15 mm/s of tread can still
produce a false demand — irreducible, because the jitter is the same order as the
speeds being separated; a decoupled shaft below ≈ 2 mm/s of body speed is below
the motion observation's own floor; and detection in the first second is now
probabilistic (0.885) where 50 mm/s made it near-certain. **None of it buys
integrity: no PL, Category, SIL or PFH is claimed or implied.**

---

## 3. F4 — answered as a design question, and the answer is forced

**Recommendation: the warning ceiling applies in teleop, and the procedure
implements it.** Not because "slow first, then stop" reads better:

> **The F-program cannot read the drive mode** (safety SPEC §6.3 — it reads no
> teleop state, no HMI request, no standard-program status bit). `SPEED_LIMIT_MAX`
> is therefore enforced on the measured tread speed **in both modes** whenever the
> warning field is occupied. A mode the standard program leaves unclamped is not a
> mode that goes fast; it is a mode that **latches `SpeedMonitorDemand`**. The
> choice was never between two behaviours — it was between slowing and stopping
> hard.

The counter-argument — a commissioning operator who cannot see why the vehicle is
sluggish — is answered by a lamp on a node that already exists, not by a faster
vehicle; and the alternative he would otherwise meet is a hard stop and a
monitored reset, which is strictly more confusing.

**The half that would have cost a second session.** `SPEED_LIMIT_ONSET_MAX` was
derived from the **autonomous** ceiling: 0.35 s + (0.60 − 0.20)/0.50 = 1.15 s,
plus 0.35 s margin, = 1.50 s. Clamping teleop asks the plant to ramp from
`TRACTION_SPEED_MAX`: 0.35 + (1.00 − 0.20)/0.50 = **1.95 s**, plus the same
margin = **2.30 s = 23 F-cycles**. Without that constant the teleop clamp would
comply 0.45 s too late and latch the demand it exists to prevent — and it is an
**F-program** constant, so discovering it after the session costs the second one.
Cost stated: a genuinely failed slow-down is discovered 0.80 s later, with SF-03's
protective field independent throughout.

**Not covered, and carried rather than fixed:** the limit is on tread speed, so a
compliant 0.20 m/s body speed reads as 300 mm/s of tread at 48° of steer and
776 mm/s at the 75° stop. An operator holding full lock inside a warning field
still latches. A steer-dependent clamp is new logic with its own failure modes
and the consequence here is a correct demand, not a hazard — it belongs in the
operator's briefing.

---

## 4. Two things the brief did not ask about, and one of them changes the plan

**(a) F1 must not land without F3.** With no `WARN` sender, `WarningFieldClear`
is permanently `FALSE`, so the 300 mm/s limit is permanently enforced — which is
already measured: `SpeedMonitorDemand` latched at 496 mm/s in `at11r1`, and
m5-57 records that no monitored reset can be accepted while the vehicle is over
the limit. Today that latch reaches nothing. **The moment the permissive conjunct
lands, it reaches everything**: any drive above 0.30 m/s refuses motion until a
reset. The 1.000 m/s drive-at-a-wall clip — the strongest result in the
validation set — cannot be re-recorded until F3 is in. Step 8 of the procedure is
that gate, and it does not block the session; it decides what the next run may
expect.

**(b) Nothing in the session proves a behaviour, and the procedure says so.**
With no writer running both F-demands stand for reasons predating the session, so
a watch-table reading cannot isolate the new conjunct. Step 60 says that rather
than writing a step whose expected value sits in an unreachable branch — the
2026-08-06 lesson, applied to my own document.

**No finding turned out not to be a defect.** F4 was carried as "a question, not
a defect"; on inspection it is a defect, and §3 above is the evidence.

---

## 5. What must be re-run once the signature changes

`50573CD9` signs every figure in `docs/VALIDATION-M5.md`. Changes 1–3 change it,
and the standard-side change alters the teleop reaction path, so **the document's
run identity is spent**. The procedure carries the full table; in short: §0, §1.1,
§1.2/§5, §2, §3 (both halves — the reproduction must now **fail** to reproduce),
§4 (first result), §6.1 and §6.2 all re-run. §1.3's control case is cheap to
re-observe. **No figure may be carried across the signature change.**

---

## files_changed

| File | What |
|---|---|
| `plc/forklift/TIA-FIX-PROCEDURE.md` | **The deliverable.** 63 steps in seven chunks, `TIA-BUILD-PROCEDURE.md`'s format exactly: one action, one observable, `Tell me:` on every step; starting state, both gates, the F-signature before and after with a place to record each, an 18-row record table, the re-run table, and a seven-row stop point |
| `plc/forklift/scl/FB_ForkliftTeleop.scl` | The F1 and F4 body deltas — two mirror copies, the third permissive conjunct, the `#teleopSpeedCap` block, and part 7's traction statement. Edited **here first** so the session's step 39 is one paste of a committed file (LESSONS 2026-08-06) |
| `plc/forklift-safety/SPEC.md` | New **§11.1b**, the standstill-window derivation with its four not-covered rows; §11.3's two constant rows revised with their derivations; SL13 gains a pointer |
| `plc/forklift/SPEC.md` | New **§14.17**, the teleop warning clamp with its reasoning, its delta and its two not-covered rows; §14.16 open item 10 closed against it |
| `docs/reports/m5-59-validation-fix-triage.md` | This report |

**Nothing was downloaded, compiled or changed in TIA. No project was opened.**
Nothing committed, no branch, no dependency added. `agv/`, `bridge/`, `hmi/`,
`docs/interfaces/` and `docs/VALIDATION-M5.md` were read and never written.

## Requests — the agent-side work, in the order it matters

| # | Request | Owner | Blocking? |
|---|---|---|---|
| 1 | Two rows in `opcua-nodes.md` §11.2 — `SpeedMonitorDemand` (start `FALSE`) and `TorqueOffDemand` (start **`TRUE`**), leaf = tag name exactly, *Accessible* ✔ / *Writable* ✘. §11.7's "deliberately absent" table needs no change: neither is writable, neither is an aggregate | `interface` | **Yes — blocks chunk AE.** Wanted before the session opens |
| 2 | `field_evaluation.py` sends `WARN 0` / `WARN 1` on 45015, and pings at **5 Hz** | `agv/` | Not for the session; **blocks re-recording anything above 0.30 m/s afterwards** |
| 3 | Bridge reads `Forklift/Safety/TorqueOffDemand` and publishes `/forklift/safety/torque_off_demand`. `opcua-nodes.md` §11.8 item 4 makes this a `bridge-design.md` change, not an assumption | `bridge` + `interface` | Not for the session; blocks AT-11 |
| 4 | `docs/VALIDATION-M5.md` §3 and finding 5: the band is **≈ 2 … 50 mm/s**, not 1.4 … 30.8, and 0.0014 m/s is a rate rather than a speed. §7's finding 4 is now answered, not open | whoever owns that document | No, but it is a wrong number in the narration document |
| 5 | A `plc/` document brief for the two carried debts of §1 | `plc/`, next brief | No |
| 6 | A lamp on `Forklift/Warning/ForkliftWarningFieldOccupied` | `hmi/` | No |

## open_questions

1. **Does the standard program's teleop clamp want a display?** §14.17 recommends
   the lamp and does not take it; without one the operator sees a sluggish
   vehicle and no reason.
2. **The steer-angle residual of §3** — 0.20 m/s of body speed is over the
   monitored tread limit beyond 48° of steer, in both modes. Carried, not fixed,
   and it will look like a fault on stage if an operator turns hard inside a
   warning field.
3. **`agv/` should record that `motion_threshold_mps` is now load-bearing against
   the F-side window.** It does not change, and that is a decision — a future
   raise of it re-opens the band from the other side.

## next_suggested

Land request 1 tonight so chunk AE is not blocked, and run the session
front to back tomorrow; then one acceptance run with the whole stack up, against
the re-run table, which is what turns six changed values into four closed
findings.
