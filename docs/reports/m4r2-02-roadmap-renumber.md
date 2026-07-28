# Report m4r2-02 — roadmap renumber per ADR 0008

brief:               docs/briefs/m4r2-02-roadmap-renumber.md
status:              done
files_changed:       docs/roadmap.md, docs/reports/m4r2-02-roadmap-renumber.md (this file)
invariants_touched:  none
open_questions:      four, listed in §3 — one of them is a correction to the brief
next_suggested:      one brief to renumber the tracking files (PLAN.md, TODO.md) onto the ADR 0008 order, since roadmap.md and PLAN.md now disagree

---

## 1. What changed

`docs/roadmap.md` now carries the ADR 0008 order.

- **Current-gate line** reads `Current gate: M4 — Forklift commissioning cell (ADR 0008).`
  It previously read `M4 — Safety layer on the fixed cell (F-CPU)`, which
  contradicted the accepted ADR. That contradiction is resolved.
- **New M4 row inserted**, byte-identical to the brief's row text (verified by
  string comparison against `docs/briefs/m4r2-02-roadmap-renumber.md`).
- **Old M4–M11 shifted to M5–M12.** Verified mechanically: every shifted row's
  deliverable and criterion text is byte-identical to its pre-edit version, and
  M0–M3 are untouched. No shifted criterion contained a gate-number
  cross-reference, so no in-criterion renumbering was required — the brief's
  allowance for that was not needed.
- **Gate-order paragraph** now names ADR 0008 as the live order, states that it
  inserts a gate rather than superseding ADR 0007, and keeps the ADR 0007 →
  ADR 0004 supersession chain intact.
- **Recordings paragraph** is now four recordings: commissioning showcase at M4,
  cell + safety showcase at M5, fleet showcase at M9, end-to-end demonstration at
  M10; M10 remains a gate in its own right rather than a compilation of the
  earlier three.
- **Safety-completeness paragraph** renumbered: cell-scope functions at M5,
  SF-05/SF-06 at M9, the vehicle chain at M6 and M7, ADR 0007 §2 still holding the
  per-function split one gate number higher.
- **Renumbering note** now carries both rounds — the ADR 0004 → ADR 0007 round
  kept verbatim in substance, the ADR 0008 round added — plus the filename note
  (`m4-00-hermes-survey.*` → M12, `m4r-*` → the ADR 0007 round, `m4r2-*`/`m4f-*`
  → the new M4, the older `m3-*` sim files → M6).
- **ADR 0007's entry condition for the safety gate is preserved**, attached to
  M5 rather than deleted, as a renumbered prose cross-reference. Deleting it
  would have dropped live state that `docs/PLAN.md` and `docs/TODO.md` both
  still carry.

Nothing else in the file changed. No ADR, no PLAN.md, no TODO.md, no CLAUDE.md.

## 2. One brief instruction not applied, and why

The brief's "Renumbering and prose edits" section instructs:

> M3 closure line: "M3 closed 2026-07-28 by owner ruling; evidence in
> docs/reports/m3-26/m3-33/m3-35/m3-36; the gate-verifier run is deferred and
> carried in TODO with the two outstanding T4.11 items."

**This was not applied.** It is stale, and applying it would have written a false
statement into the live order:

- The gate-verifier run is **not** deferred. It ran and ruled
  **pass-with-findings** — `docs/reports/m3-37-gate-verification.md`, twelve
  findings, none unmeeting an exit item.
- The line on disk, `M3 closed 2026-07-28, verified in
  docs/reports/m3-37-gate-verification.md (pass-with-findings).`, was written by
  commit `8fe89cd` ("close M3 on the verifier's pass-with-findings and reset the
  queue"), which post-dates the state the brief's text describes.
- `docs/PLAN.md` opens with "Verified in `docs/reports/m3-37-gate-verification.md`,
  **pass-with-findings**". Applying the brief's text would have made roadmap.md
  and PLAN.md disagree on whether M3 was verified at all — the one thing
  CLAUDE.md §11 forbids outright.
- The brief's own `done_when` does not list the M3 closure line among its
  criteria, and ends with "nothing else changes", which reads the same way.

The existing M3 closure line is therefore kept verbatim. This is the LESSONS rule
of 2026-07-27 applied to a brief rather than to a document: an enumerated
instruction is a starting point to be verified by independent search, and this one
did not survive the check.

## 3. Open questions

1. **`docs/PLAN.md` now disagrees with `docs/roadmap.md`.** PLAN's whole
   "M4 — Safety layer on the fixed cell (F-CPU): NOT OPENED" section is the gate
   now numbered M5, and its closing note places `m4-00-hermes-survey.*` at M11 and
   the older `m3-*` sim files at M5. PLAN.md is inside this agent's write scope but
   the brief's `forbidden` list bars editing it, so the disagreement is reported,
   not fixed. It needs a brief.
2. **`docs/TODO.md` carries six stale gate references** and one stale ADR
   reference (line 30's m2-04 `done_when` says the SRS must match "the **ADR 0007**
   order", which is now the ADR 0008 order). Also forbidden to this brief.
3. **The M12 Hermes row's entry condition was left verbatim**, per the brief's bar
   on altering a shifted row's criterion beyond gate numbers. It reads "the ten
   owner decisions … are ruled, including the operator/HMI layer ADR that the §3
   topology needs". ADR 0008 D2.7 rules decision 3 **for the local case only** and
   records that decision 2 was closed by ADR 0007, leaving eight unruled. The row
   is not wrong — the entry condition still stands — but it no longer describes
   what remains. A later brief should decide whether the row states the residue.
4. **Stale gate references outside this agent's write scope**, found by
   independent search on 2026-07-28 (`\bM(4|5|6|7|8|9|10|11|12)\b` across all
   tracked `*.md`). ADR 0008's consequences asked m4r2-02 to verify ADR 0007's list
   rather than inherit it; the verified list is below. ADR 0007's items are marked
   †, and every one of them is still unfixed, so those are now stale by two rounds.

   | File | Where | Reads | Should read |
   |---|---|---|---|
   | `README.md` (public) | 130–137 | gate table M4–M11 | new M4 inserted, M5–M12 |
   | `README.md` | 120 | "Next gate: **M4**" | M4, but relabelled Forklift commissioning cell |
   | `README.md` | 74 | e-stop chain "arrives at M4" | M5 |
   | `README.md` | 112 | "out of scope until M10", "joins the demonstration at **M5**" | M11, M6 |
   | `docs/safety/SRS.md` † | 6–7 | F-CPU at M7, vehicle at M3/M4 | M5, M6 |
   | `docs/safety/SRS.md` † | §1.3 heading + body (3 refs) | arm at M9 | M11 |
   | `docs/safety/SRS.md` † | AT-06/07/08 tags | M7, coupled at M8 | M9 (AT-06), M5 with coupled at M9 (AT-07), M5 (AT-08) |
   | `docs/safety/SRS.md` † | AT-09 tag | M4 | M7 |
   | `docs/safety/SRS.md` † | §4 "Verified at gate" column | M7/M3/M4/M9 | M5/M6/M7/M9/M11 per ADR 0007 §2 shifted |
   | `docs/safety/PL-SCENARIOS.md` † | 30–31 | safety M9, vehicle M5/M6, demonstration M10 | M5, M6/M7, M10 |
   | `plc/demo-cell/SPEC.md` † | 1683 | safety "gate M9" | M5 |
   | `plc/demo-cell/SPEC.md` † | 1684 | target-cell logic "Gate M8" | M9 |
   | `sim/README.md` † | 22, 164, 248 | warehouse world / navigation scenario / vehicle work at M5 | M6 |
   | `sim/README.md` † | 237 | handshakes at "later gates (M6/M7)" | M9 |
   | `docs/TODO.md` † | 6–8, 24, 30, 40, 41, 42, 43 | M4, M6, ADR 0007, M6, M7, M5, M8/M9 | M5, M7, ADR 0008, M7, M8, M6, M9/M10 |
   | `docs/PLAN.md` | 25–43, 60–61 | M4 section, M11, M5 | M5 section, M12, M6 |
   | `sim/setup/WSL_ENVIRONMENT.md` | 15, 33, 34, 146 | "deferred M5 vehicle work" | M6 |
   | `assets/CREDITS.md` | 58 | "vehicle enters the demonstration at M5" | M6 |
   | `sim/scenarios/DEFERRED.md` | 13, 15 | "the gate now numbered M5", cites ADR 0004 | M6, ADR 0008 |
   | `docs/interfaces/bridge-design.md` | 567 | quotes the `sim/README.md` heading "(M5, deferred)" | M6, in step with sim/README |
   | `CLAUDE.md` §6 | 169–177 | the original M0–M8 numbering | owner-owned; ADR 0008 requests the follow-up, and `docs/briefs/m4r2-03-claudemd-hmi-layer.md` exists for the topology, layout and roster additions |

   Two files are deliberately **not** on the fix list. `docs/LESSONS.md` line 48
   names "the M6 fleet-facing interface name" but is append-only and is a
   historical record. `docs/adr/0004`, `0006` and `0007` are accepted ADRs and are
   never edited; `docs/roadmap.md` remains the live order, which is what ADR 0008
   §"The shift" and ADR 0007's own consequence both say. Brief and report files in
   `docs/briefs/` and `docs/reports/` keep the numbers they were written under, per
   the ADR 0004, 0007 and 0008 precedent, and are not stale references.

   `HANDOVER.local.md` also carries two, but it is gitignored owner-local material,
   not repository content.

## 4. Verification performed

- New M4 row compared byte-for-byte against the brief's row: identical.
- All twelve pre-edit rows parsed and compared against their post-edit
  counterparts under the shift map: M0–M3 identical, M4→M5 … M11→M12 identical in
  both deliverable and criterion.
- Stale-reference list built by independent search across all tracked `*.md`,
  not inherited from ADR 0007's list; ADR 0007's list was then checked against it
  and every item confirmed still present.
- Working tree line endings confirmed LF (`git ls-files --eol`) before writing, so
  the diff is content only.
