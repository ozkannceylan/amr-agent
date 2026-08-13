# Report m4r2-04 — public README: gate order and finding-12 residue

brief:               docs/briefs/m4r2-04-readme-gate-order.md
status:              done
files_changed:       README.md, docs/reports/m4r2-04-readme-gate-order.md (this file)
invariants_touched:  none
open_questions:      three, listed in §4 — none blocks the deliverable
next_suggested:      one brief for the README's architecture diagram and layer table, which still predate the `hmi/` layer of ADR 0008 D2.6

---

## 1. What d717283 had already fixed, and what it had not

Diffed first, per the brief. `d717283` ("correct two README captions and mark M3
closed") touched three things, all of them finding-12 items or their
consequence:

| m3-37 finding 12 item | State before this brief |
|---|---|
| GIF captioned as "the four M3 exit scenarios T1–T4" | **fixed** by `d717283` — now "28 s of the first live PLCSIM loop run, ordered simplest-first" |
| `171656.png` captioned "live cell input values" | **fixed** by `d717283` — image replaced with `135105.png`, caption rewritten to name exit item (a) and the value's provenance |
| Closed-loop row cites `§B.6`; L7 is `§B.5` | **not fixed** — corrected here |
| PLAN line 118 over-claims the five re-runs | not a README item; out of this brief's scope and untouched |

`d717283` also flipped the M3 status cell to **done** and rewrote the milestone
lead-in, so neither was redone.

Verified against the source rather than inherited: `bridge/EVIDENCE_LATENCY.md`
§B.5 is "L7 — the closed loop, now that a real program answers (item 4)" and
carries the count 6 / median 46.8 ms table; §B.6 is "Startup rule against the
real DB start values (item 5)". The citation now reads §B.5. The row's
companion citation, "§B2.5 finds the same cluster on a later build", was checked
and is correct — §B2.5 is the part-2 L7 section and states the same 46.8 ms
cluster.

## 2. Gate order, renumbered against roadmap.md

`docs/roadmap.md` was taken as the authoritative order, not ADR 0008's shift
table and not the m4r2-02 report's summary. Every deliverable string in the
README's gate table now matches its roadmap row verbatim.

| README | Was | Now |
|---|---|---|
| table rows | M4 safety … M11 Hermes | **M4 Forklift commissioning cell** inserted; safety → M5, simulated vehicle → M6, VDA 5050 client → M7, fleet manager → M8, PLC integration → M9, demonstration → M10, arm → M11, Hermes → M12 (still `parked`) |
| line 120 | "Next gate: **M4**." | "Next gate: **M4 — Forklift commissioning cell**." |
| line 74 | e-stop chain "arrives at M4" | M5 |
| line 112 | arm "out of scope until M10", vehicle "joins the demonstration at **M5**" | M11, M6 |
| lines 139–141 | "Gate order follows ADR 0007: … then the safety layer on that same cell" | follows **ADR 0008**, which extends ADR 0007 rather than superseding it; the forklift step named between the signal loop and the safety layer |

The last row is not on m4r2-02 §3's list but is the same defect: the paragraph
states the gate *order*, and after the insertion it named the wrong ADR and
skipped a gate. It is a compression of `docs/roadmap.md`'s own gate-order
paragraph, not new prose — it adds one clause and one link.

M0–M3 are untouched, including the M3 closure line, which `8fe89cd` and
`d717283` already brought to the verified wording.

## 3. Verification performed

- **The stale-reference list was re-derived, not inherited.** `\bM([0-9]|1[0-2])\b`
  across README.md before and after. Before: eleven sites (74, 112, 118, 120,
  126–137). After: the same sites, every one either renumbered or correct as it
  stood (118 and 126–129 are M0–M3 and the M3 closure). No twelfth site existed,
  so m4r2-02 §3's four README rows were complete — recorded because the LESSONS
  rule of 2026-07-27 says an enumerated list is a starting point, not an
  inventory.
- **Every remaining caption re-checked against its artifact.** The GIF and
  watch-table captions are `d717283`'s and were not re-opened. `demo-cell.png`
  carries alt text only. The RB-KAIROS caption's provenance claim
  ("the manufacturer's own BSD-3-Clause ROS 2 description … not a marketing
  image") is confirmed by `assets/CREDITS.md`, which names both pinned upstream
  commits and reproduces the licence; only its two gate numbers were wrong.
- **The other three Measured rows were re-derived from their cited artifacts**,
  since one bad citation is reason to check the rest: 20.00 Hz / 14 244 cycles /
  1 overrun of 3.93 ms / 0 read or write errors is §B2.3's table verbatim;
  2.301 s inside [2.1, 3.2] s is `EVIDENCE_SIGNAL_LOSS.md` line 546 and its
  window statement; the CPU cycle-time triple was ruled digit-for-digit by
  m3-37. No §11 pass count is stated anywhere in the file, so the brief's bar on
  restating one had nothing to remove.
- **Both link targets checked to exist** before linking: `docs/adr/0007-…` and
  `docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md`.
- **Diff is content only.** `git diff --numstat` and
  `git diff --ignore-cr-at-eol --numstat` both report 19/15, and
  `git ls-files --eol README.md` reads `i/lf w/lf`. Git's
  "LF will be replaced by CRLF" warning is the checkout policy of the LESSONS
  entry of 2026-07-27, not a content change.
- Commit is pathspec-scoped to exactly two files. `agv/forklift/` is untracked
  work by a concurrent agent and was left alone.

## 4. Open questions

1. **The README's architecture diagram has no HMI box and its layer table has no
   `hmi/` row**, though `hmi/README.md` is tracked and CLAUDE.md §3/§4 gained
   both in `2e6bf48`. The gate table now names a commissioning cell whose
   command source the diagram does not draw. Left alone: the brief's `done_when`
   ends "nothing else changes", and this is a different deliverable. It needs a
   brief.
2. **The vehicle section may now read as the forklift.** ADR 0008 D5 is explicit
   that the forklift is *plant* and the RB-KAIROS is the *vehicle*, and that the
   two models are never merged; the README states neither, so a reader meeting
   "M4 Forklift commissioning cell" one screen below a photo of an RB-KAIROS has
   nothing distinguishing them. One clause would fix it, but it is new prose and
   this brief forbids that.
3. **The M12 row's deliverable text is the short form.** roadmap.md reads
   "Command path from Hermes — **parked, no priority**"; the README carries
   "Command path from Hermes" with `parked` in its status column, as it did
   before the shift. Recorded as a deliberate non-change rather than an
   oversight.
