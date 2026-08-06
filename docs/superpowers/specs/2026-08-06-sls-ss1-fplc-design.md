# SLS and SS1 in the F-PLC — design

**Date:** 2026-08-06
**Gate:** M5
**Status:** approved by the owner, 2026-08-06. Standards basis **verified the
same day** by m5-45 (`docs/safety/SLS-STANDARDS-BASIS.md`): all five decisions
survive, none contradicted, two wording amendments applied below. Phases 3 and 4
**gate M5's closure** — owner ruling, 2026-08-06.

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
| 1 | What "standards-compliant" means here | **Architectural fidelity plus a simulated safe-measurement structure** — two readings cross-compared, demand on discrepancy. Not certification: this project claims PLr targets only (ADR 0011 D5) |
| 2 | Where the speed readings come from | **Two reading channels on one shaft, independent noise** — what a real safe encoder is, rather than two convenient different measurements. Its honest name is a **single-channel tested system**; see §3 |
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

**Its honest name (m5-45 amendment 1).** This arrangement is a **single-channel
tested system**, not a two-channel one. One shaft, one measurement, two readings
of it, cross-compared — which is what real safe encoders do
(HEIDENHAIN TI 596632: two internally generated position values cross-compared
by the safe control). Calling it two-channel would overstate it, and the
documents say single-channel tested wherever they describe it.

**The shared-shaft hole, closed deliberately.** Two readings of one shaft lie
together if the shaft itself fails. The design therefore adds a separate
**motion-present check**: the F-program corroborates a claimed zero speed
against another observation of the vehicle before trusting it.

**(m5-45 amendment 2)** That check is a **stand-in**, and is labelled one. Real
systems close this hole with a **mechanical fault exclusion** on the shaft
coupling — an argument about construction, not a monitored signal. This project
has no such argument available, so it substitutes an observation and says so.

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

**RULED 2026-08-06: phases 3 and 4 gate M5's closure.** The reasoning is not
only fidelity: the SRS traceability already commits SF-10 and SF-11 to M5, and
**SF-03's R3 residual is carried by SF-10** — so removing them would not merely
defer two tests, it would puncture a safety argument that is already written.
The contrary ruling was defensible but would have required a written SRS
restatement round rather than a silent deferral.

## 7. The standards basis — verified 2026-08-06 (m5-45)

Full record with graded sources: `docs/safety/SLS-STANDARDS-BASIS.md`.

**The split in §4 is the certified pattern, not our invention.** A drive
manufacturer's safety manual places the speed-setpoint limiting in its
**standard functions** column while the safety side monitors actual speed and
executes the safe stop, and declares that split conformant with the drive-safety
definition of SLS.

**The owner's instinct is confirmed in effect and sharpened in mechanism.**
Nothing reachable states a rule that these functions must live in a safety
controller. What puts them there is that the function — measurement, monitoring
and reaction — must meet its **required performance level**, while the limiting
earns **no safety credit at all**. That is a stronger reason than a placement
rule, and it is the one to give when the architecture is questioned.

**Still unreached, and marked so.** The normative texts stayed behind their
paywall. Five items (U1–U5 in the basis document) record what would settle each.
**No clause number appears in this spec**, and none may be quoted from it — only
from a reachable source that cites one.

**Process warning from that round.** Two automated document summaries returned
**fabricated quotations**. Every quotation in the basis document was re-verified
against locally extracted source text, and nothing here may be quoted from a
summariser.

## 8. What this design does not claim

No PL, Category, SIL or PFH is claimed anywhere. The measured path is a standard
DB throughout, the safe measurement is a **simulated structure** rather than a
safe one, and every artefact says so. ADR 0011 D5's claim boundary is untouched.
