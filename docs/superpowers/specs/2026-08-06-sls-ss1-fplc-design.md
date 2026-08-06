# SLS and SS1 in the F-PLC — design

**Date:** 2026-08-06
**Gate:** M5
**Status:** approved by the owner, 2026-08-06. Standards basis **not yet
verified** — see §7.

---

## 1. Why this exists

The owner's framing settles it: **M5 is one vehicle's control, completed exactly
as wanted and compliant with the standards. M6 clones that vehicle into a fleet.**

A review had recommended deferring SLS (safely limited speed) and SS1
(controlled stop then torque removal) to M6, because nothing at M5 implemented
them and so nothing could test them. The owner rejected that reasoning: a
standards-compliant single vehicle **has** those functions, so the work is to
build them, not to move the test. They also ruled the placement — **SLS and the
controlled stop are the F-PLC's, not the standard program's.**

## 2. The five decisions

| # | Question | Ruling |
|---|---|---|
| 1 | What "standards-compliant" means here | **Architectural fidelity plus a simulated safe-measurement structure** — two channels, cross-compared, demand on discrepancy. Not certification: this project claims PLr targets only (ADR 0011 D5) |
| 2 | Where the two speed channels come from | **Two encoder channels on one shaft, independent noise** — what a real safe encoder is, rather than two convenient different measurements |
| 3 | What STO means in simulation | **Joint controller disabled plus a holding brake.** Implementation **deferred**: planned here, built after the vehicle is seen working |
| 4 | What "a vehicle working" means | **The full loop without the map first**, validated, then the map |
| 5 | Whether SLS limits or monitors | **Monitors.** The standard program limits; the F-program verifies and demands |

## 3. Speed measurement

Two encoder channels on the drive shaft, each carrying **independent noise**.
The F-program cross-compares them and raises a demand when they disagree for
longer than a discrepancy time.

This is chosen because it is **what a real safe encoder is** — one shaft, two
reading channels — rather than an engineered pair of different measurements. It
also makes the cross-comparison mean something specific: the channels observe
the same physical quantity, so a divergence is a channel fault and not an
ambiguity between two estimates.

**The shared-shaft hole, closed deliberately.** Two channels on one shaft can
lie together if the shaft itself fails. The design therefore adds a separate
**motion-present check**: the F-program corroborates a claimed zero speed
against another observation of the vehicle before trusting it.

**The honest limit.** Speed reaches the F-program as **standard data** over the
bridge. So this carries the same three consequences as the scanner channel: the
S015 disclosure check written visibly in the F-code, the path labelled a
stand-in wherever it appears, and **no integrity claim of any kind** — no PL, no
Category, no SIL, no PFH.

## 4. SLS — the standard program limits, the F-program verifies

- **The standard program** lowers the **envelope speed ceiling** when the
  warning field trips. This is what actually slows the vehicle, and the ceiling
  keeps its single owner (invariant 10).
- **The F-program** independently measures the real speed from the two channels
  and checks it against the SLS limit. On violation it **demands a stop**.

Three properties follow, and they are the reason for the split:

1. the speed ceiling still has exactly one owner;
2. **no speed value leaves the F-program** — only a demand — so ADR 0014 holds;
3. the safety layer catches the case where **the slowdown itself fails**, which
   is the reason a safety function exists at all.

## 5. SS1 — two stages, the second deferred

On demand: a **controlled stop** using the existing chain's ramp, then, once
standstill is confirmed or a timeout expires, **STO**.

**STO is the joint controller disabled plus a holding brake.** The observable
that makes SS1 testable rather than nominal: **after STO the vehicle is deaf to
commands**, and stays deaf even if the envelope reopens. Only the safety reset
restores it. Without this, SS1's two stages collapse into the stop the vehicle
already has and no test can tell them apart.

**Deferred by owner ruling, 2026-08-06.** It requires a `model.sdf` change, and
the owner wants the vehicle seen working first. Planned here; built in phase 4.

## 6. Sequencing

| Phase | What | Depends on |
|---|---|---|
| **1** | **The full loop, no map**: HMI → PLC → bridge → vehicle → Gazebo, autonomous, a field intrusion stopping it, the monitored reset recovering it | the bridge forklift repoint |
| **2** | The map page (HMI v2b) on the monitoring service | phase 1, `viz/` (built) |
| **3** | **SLS monitoring**: the dual channel, the F-program's check, the demand. **No model change** | phase 1 |
| **4** | **SS1 and STO**: the model's brake and controller disable | phase 3 |

**Open, and the owner's to rule:** whether phases 3 and 4 gate M5's closure or
land immediately after phase 2. Both are defensible — the first is more faithful
to "one vehicle finished to standard", the second shows a working vehicle
sooner.

## 7. What is not yet verified

The owner believes the F-PLC placement of SLS and the controlled stop is an ISO
requirement, and the recollection here is that **IEC 61800-5-2** defines STO,
SS1 and SLS while **ISO 3691-4** governs driverless industrial trucks. **None of
that has been checked**, and this project's rule is that an external source is
cited with a verification date and, where possible, a pinned reference.

A research round (m5-45) verifies it before phase 3 is briefed, and its findings
may change §3 and §4. Until then no document may cite a clause number from this
spec.

## 8. What this design does not claim

No PL, Category, SIL or PFH is claimed anywhere. The measured path is a standard
DB throughout, the safe measurement is a **simulated structure** rather than a
safe one, and every artefact says so. ADR 0011 D5's claim boundary is untouched.
