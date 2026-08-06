# m5-65 — correct the validation document and harden two procedure steps

    gate:                M5
    agent:               plc
    scope grant:         plc/, plus docs/VALIDATION-M5.md by explicit owner-approved grant — no roster agent owns it and the corrections are yours
    goal:                Put the corrected threshold numbers into the document the owner narrates the showcase from, and remove the one procedure step that can stall tomorrow's session.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-64-fix-round-judge.md — findings 1 (request 4 never actioned), 3 (the F2 fragility), 6 (step 38)
      - docs/reports/m5-59-validation-fix-triage.md — your own derivation and the two corrections
      - docs/VALIDATION-M5.md
      - plc/forklift/TIA-FIX-PROCEDURE.md
      - agv/forklift/EVIDENCE_NAV2.md and agv/forklift/config.yaml — for the three constants below
    deliverable:         docs/VALIDATION-M5.md and plc/forklift/TIA-FIX-PROCEDURE.md, corrected
    done_when:           The document carries no superseded threshold figure, the three constants the F-window rests on are recorded as load-bearing, and step 38 cannot stall on a whitespace artefact.
    forbidden:
      - editing outside plc/ and docs/VALIDATION-M5.md
      - re-deriving the 15 mm/s window. The judge reproduced every number independently; this brief records, it does not re-open
      - changing any measured figure. Only the superseded threshold numbers move
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. The document still publishes numbers you proved wrong

`docs/VALIDATION-M5.md` still states the band as **1.4 … 30.8 mm/s**. Your own
triage established that both ends are wrong: the near-zero value in force is
**50 mm/s** (30.784 is `SPEED_DISCREPANCY_MAX`, a different constant), and
0.0014 m/s is a **lidar rate**, about **2.0 mm/s** of body speed. m5-59
requested the correction and it was never actioned.

This matters more than an ordinary stale figure: **`VALIDATION-M5.md` is the
document the owner narrates the recorded showcase from.** A wrong number there
is spoken aloud.

Correct it, and say in one line that the band was wider than first reported —
not narrower. A reader who saw the earlier figure must be able to tell which
direction the correction went.

## 2. Record what the F-window actually rests on

The judge confirmed your derivation reproduces independently, and confirmed the
"at every steer angle" claim is genuine — tread = min(0.025/cos δ, 0.025/sin δ)
≥ 0.025 up to the 1.31 rad stop.

It also found the fragility: **the 25 mm/s floor rests on `a_v · dt = a_w · dt ·
L` (0.025 = 0.02381 × 1.05), and none of those three constants is recorded
anywhere as load-bearing against the F-window.** Any of them could be retuned by
someone who has no idea a safety threshold depends on it.

One row, in the spec section that carries the window: name the three constants,
where they live, and what breaks if they move. That is the whole fix.

## 3. Step 38 can stall the session

Step 38 tells the owner to expect **"exactly three hunks"**. If TIA's copy-out
does not round-trip byte-identically, that becomes a wall of whitespace hunks
and the owner is stuck at the keyboard with no rule to apply.

Give the step its fallback: retry with `--ignore-cr-at-eol -w` **before**
concluding drift, and say what each outcome means. One line, and it is the
difference between a step that stalls and a step that resolves.

## 4. While you are in the procedure

The judge re-derived three expectations the owner will read back and they check
out — 48 = 46 + 2 against the m5-49 baseline, step 26's 13-value signature, and
step 24's IN-TRUE reachability. Nothing to do; recorded so you do not re-check
them.

## 5. Working discipline

- Read `docs/LESSONS.md` first.
- **Do not commit.** The orchestrator commits by pathspec.
