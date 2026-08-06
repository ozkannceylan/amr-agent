# m5-65 — correct the validation document and harden two procedure steps

    brief:               docs/briefs/m5-65-validation-doc-corrections.md
    status:              done
    invariants_touched:  none

## The one-line answer

**The three corrections are in, and none of them moved a measured figure.**
`docs/VALIDATION-M5.md` now publishes the band as **≈ 2 … 50 mm/s** with a
correction note that states in one line that the band is **wider** than first
reported; `plc/forklift-safety/SPEC.md` §11.1b now records the three
vehicle-side constants the 25 mm/s floor rests on, with what breaks if each
moves; and step 38 of the fix procedure now resolves a whitespace artefact
instead of stalling on it.

---

## 1. The band — corrected, and the direction of the correction is stated

`docs/VALIDATION-M5.md` §3 carried the mechanism as *1.4 … 30.8 mm/s* and §7
finding 5 repeated it. Both are replaced by **≈ 2 … 50 mm/s**, and both carry
the direction explicitly.

| Edge | Was published | In force / measured | Why the old figure was wrong |
|---|---|---|---|
| Upper | 30.8 mm/s | **50 mm/s** | `SPEED_STANDSTILL_MAX` = `50` is the constant that bounds the near-zero test. 30.784 mm/s is `SPEED_DISCREPANCY_MAX`, a different constant answering a different question; it never bounded this band |
| Lower | 1.4 mm/s | **≈ 2.0 mm/s** of body speed | 0.0014 m/s is `motion_threshold_mps`, a per-ray range **rate**, not a speed. At the worst measured rate-to-body ratio (0.715) it is ≈ 2.0 mm/s of body speed, and that conversion is an extrapolation below 0.05 m/s |

**The direction is on the page, twice.** §3's correction note says the band
"is *wider* than first reported, not narrower — it opens lower and closes
higher", and §7 finding 5 carries the same in a parenthetical so a reader who
lands on the findings table without reading §3 still sees which way it went.

**No measured figure moved.** The 15–26 mm/s encoder readings, the timings in
the two-row table, the 0.025 m/s smoother floor, the 7 fail-safe trips and
every figure elsewhere in the document are untouched. Only the two threshold
values changed, and the note says so in those words.

**Two things I added beyond the swap, both to stop the narration going wrong
in the other direction.** §3 now states that the replacement window is `15` /
`-15` mm/s per §11.1b and that **the change is not in this run** — it moves the
F-collective signature, so a narrator reading §3 cannot come away thinking the
band has already been closed on the CPU. §7 finding 5's owner column now reads
*answered* rather than open, pointing at §11.1b. Finding 4 was left as written:
m5-59 answers it too, but the brief scoped this deliverable to the threshold
numbers and I did not widen it.

The document's own signature-`50573CD9` caveat and its re-run pointer to
`plc/forklift/TIA-FIX-PROCEDURE.md` are now stated in §3 rather than only in
the procedure, because §3 is the section that will be read aloud.

## 2. The three constants, recorded as load-bearing

`plc/forklift-safety/SPEC.md` §11.1b — the section that carries the window —
gains a fifth not-covered row and a table beneath it. The row says plainly that
the 25 mm/s floor is **not a property of this spec**: it is a numeric
coincidence in three vehicle-side constants the F-program cannot see, nothing
here detects a change to them, and the exclusion simply stops holding.

The equality is stated first, because it is what makes the floor *flat*:
`a_v·dt` = 0.50 × 0.05 = 0.025 m/s and `a_w·dt·L` = 0.4762 × 0.05 × 1.05 =
0.025 m/s. Break it and the floor becomes whichever branch is smaller, at the
steer angle where that branch bites.

| Constant | Where it lives | What moving it does |
|---|---|---|
| `max_accel` `[0.50, 0.0, 0.4762]` | `agv/forklift/nav2.yaml`, `velocity_smoother:` | Lowers one branch each; either drives the floor toward the `W ≤ 18.0` mm/s exclusion bound, below which **no admissible `W` exists at all** |
| `smoothing_frequency` `20.0` (dt = 0.05 s) | `agv/forklift/nav2.yaml`, `velocity_smoother:` | Multiplies **both** branches — 40 Hz halves the floor to 12.5 mm/s, below `W` = 15, and every from-rest mission latches again |
| `wheelbase_m` `1.05` | `agv/forklift/config.yaml`, `kinematics:` (mirrors `model.sdf`) | Scales the curvature-limited branch only; a shorter wheelbase turns the flat floor into a dip at large steer, where the exclusion is weakest |

A closing paragraph names the re-derivation trigger and says that these three
plus `motion_threshold_mps` (m5-59 OQ3, the lower edge) are the **complete**
set of vehicle-side values `SPEED_STANDSTILL_MAX` depends on.

**Nothing was re-derived.** The judge reproduced every number independently and
this section records rather than re-opens; the arithmetic above is quoted from
`agv/forklift/nav2.yaml` lines 729/784 and `agv/forklift/config.yaml` line 52
as committed.

## 3. Step 38 can no longer stall

The step kept its "exactly three hunks" expectation and gained the fallback
command and a four-row reading table:

| First command | `--ignore-cr-at-eol -w` | Ruling |
|---|---|---|
| three hunks | not needed | Go to step 39 |
| many hunks | three hunks | Copy-out artefact, not drift — SCL is not whitespace-sensitive and step 39 replaces the whole body. Go to step 39, record that the first count was an artefact |
| many hunks | more than three | **Real drift. Stop.** |
| three hunks, but not *these* three | — | **Stop.** A right count of wrong hunks is drift that happens to be the same size |

The fourth row is not in the judge's finding; it closes the same hole from the
other side, since the original wording could be satisfied by a count alone. The
step also now states *why* the fallback exists — `git diff --no-index` compares
raw bytes, so one editor-side normalisation reads as a total rewrite — so the
owner is not applying a rule he cannot see the reason for. The record table row
for step 38 asks for both counts when the first is a wall.

## files_changed

| File | What |
|---|---|
| `docs/VALIDATION-M5.md` | §3: band corrected to ≈ 2 … 50 mm/s, a correction note stating the band is **wider** and that no measured figure moves, and a forward pointer to the pending `15`/`-15` change and the spent run identity. §7 finding 5: same numbers, direction stated, marked answered |
| `plc/forklift-safety/SPEC.md` | §11.1b: not-covered row 5, the three-constant table with locations and consequences, and the re-derivation trigger |
| `plc/forklift/TIA-FIX-PROCEDURE.md` | Step 38's fallback command and four-row reading table; the record table row asks for both counts |
| `docs/reports/m5-65-validation-doc-corrections.md` | This report |

**Nothing was committed, no branch was created, no dependency added.** No TIA
project was opened, nothing was compiled or downloaded, and no process was
started. `agv/forklift/nav2.yaml` and `agv/forklift/config.yaml` were read and
never written.

## Requests — work outside this scope

| # | Request | Owner | Blocking? |
|---|---|---|---|
| 1 | Mirror §11.1b's three-constant row **beside the constants themselves** — a comment at `nav2.yaml`'s `velocity_smoother:` and at `config.yaml`'s `wheelbase_m` saying an F-side safety window depends on them and pointing at `plc/forklift-safety/SPEC.md` §11.1b. The spec row is where the derivation lives; the person who retunes a smoother will never open it | `agv/` | No, but it is the half of finding 5 that would actually be seen by the person who breaks it |
| 2 | m5-64 finding 1's redaction in `agv/forklift/evidence/m5-61-writer-session-nocycle.log` line 11, and the `hmi/tools/capture_v2b_real_screens.mjs:76` literal | `agv/`, `hmi/` | **Before any push or public visibility.** Outside my scope and untouched here |
| 3 | m5-64 finding 8 — TODO.md and PLAN.md against the full report directory | orchestrator | Before gate advance or narration drafting |

## open_questions

1. **§7 finding 4 is still worded as an open design question** ("whether teleop
   should also be reduced"). m5-59 §3 answers it and the procedure implements
   the answer, but the brief scoped me to the threshold numbers so I left the
   wording alone. It wants one line in the same pass that rewrites the document
   after the signature changes.
2. **The §3 correction note will outlive its usefulness.** Once the document is
   re-run against the new signature the note is describing an issue nobody has
   seen. It should be kept through the re-validation rewrite and dropped only
   when the band's numbers are re-measured, not before — a reader who saw the
   1.4 … 30.8 figure needs the trail.

## next_suggested

Run `plc/forklift/TIA-FIX-PROCEDURE.md` front to back; then the acceptance run
against its re-run table, which is what replaces §3's corrected-but-superseded
band with a measured one.
