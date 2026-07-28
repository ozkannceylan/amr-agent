# Report m3-31 — §11 pass claims count what actually exists

brief:               docs/briefs/m3-31-pass-string-accounting.md
status:              done
files_changed:       [plc/demo-cell/SPEC.md, docs/reports/m3-31-pass-string-accounting.md]  (nothing committed)
invariants_touched:  none
open_questions:
  - Both new caveats end at the same place: **F1, the presence verdict that never
    asserts, has no fix.** T1.4 is recorded failed and T2.2–T2.4 unreachable
    because of it, so exit items (a) and (b) cannot be claimed until it is
    diagnosed — and §B.13 F1 says the watch table is the only instrument that
    can distinguish its three candidate causes. m3-29 fixed F2; F1 is still open
    and is not the subject of any brief.
  - The new §11 preamble points at `bridge/EVIDENCE_LATENCY.md` §B.7 / §B.12 /
    §B.13 by number. If Section B is ever restructured those three pointers need
    a sweep; they are correct against HEAD (`eb3ebd4`) and against what m3-32's
    report says it changed.
next_suggested:      A brief that attacks F1 — owner TIA session running T1 with §9 Group 4 in the watch table, to separate a filter-timer fault from a hysteresis fault from a verdict that is never written.

---

## What the counts actually are

Counted from the tables themselves rather than from the numbers the brief
quoted, per the enumerated-list rule (LESSONS 2026-07-27):

| Scenario | Rows in its table | Line before | Line now |
|---|---|---|---|
| T1 | **6** — 1.1, 1.1b, 1.2, 1.3, 1.4, 1.5 | "Pass: all six" | "Pass: all six steps of the table above" + a caveat for 1.4 |
| T2 | **8** — 2.1…2.8 | "Pass: all eight" | "Pass: all eight steps of the table above" + a caveat for 2.2–2.4 |
| T3 | **no numbered table** | prose criterion, no count | same criterion, now stating explicitly that it carries no count |
| T4 | **13** — 4.1…4.5, 4.6, 4.6b, 4.7, 4.8, 4.9, 4.9b, 4.10, 4.11 | "Pass: all thirteen" (m3-29) | "Pass: all thirteen steps of the table above" + the as-run reconciliation |

**The "Pass: all twelve" the brief expected no longer exists.** m3-29 had already
raised T4 to thirteen and added the denominator caveat when it added 4.6b, so the
T4 work here was reconciliation against the as-run record, not a count fix. Both
numbers the brief named were verified by machine count of the table rows, not by
reading the prose.

## The three rules, hoisted

A new subsection **"How the Pass lines below are counted"** sits between the §11
preconditions and T1, and states once what m3-29 had stated only for T4:

1. A count is the number of rows in that scenario's own step table. Sub-lettered
   steps (1.1b, 4.6b, 4.9b) are steps. A scenario with no numbered table carries
   no count.
2. A count here is the **specified denominator**, never a claim about a run. A
   step added after a run grows this count and gives the evidence an outstanding
   row; the denominator of a run that already happened never grows.
3. A step recorded as failed, not run or not executable is **not** a pass by
   default. The as-run record is named — §B.7, §B.12, §B.13 — and a pass claim
   names the build it was taken against.

Rule 1 deliberately does **not** repeat the counts centrally. They live on the
four **Pass** lines and nowhere else, so there is one place to change when a
table changes (invariant 10). The three rules are referenced by number from each
caveat rather than restated.

## The three caveats, and what each is derived from

- **T1** — the run observed the first half of 1.4 (range falls to the
  beam-blocked value and holds well past `PRESENCE_FILTER`) and *not* the second
  (`ProductPresentAtSensor` never changed state for the whole run), §B.13 F1.
  Six of six therefore needs 1.4 re-run against a build that answers F1.
- **T2** — 2.2–2.4 sit downstream of the same verdict and have never been
  reached, §B.12 item 8. The note also records the one part of T2 that did run
  repeatedly, the re-home branch of 2.1, and that it ran only from the positive
  side of home (§B.13 F1).
- **T4** — the recorded run covered the twelve steps the list then held: seven
  ran, one of those failed (the then-4.6, F2), one was attempted and found not
  executable (the then-4.7), and four did not run (4.5, 4.8, 4.9b, 4.11). Since
  that run 4.6b was added and 4.6/4.7 were re-specified, so no case-D step has a
  valid as-run result.

No figure was copied out of the evidence except where a name was needed; the
caveats point at the sections rather than reproducing their numbers, so nothing
here can drift out of step with a measurement.

## Scope discipline

- **No scenario step and no detection logic was touched.** The diff is
  confined to the four **Pass** lines, three new blockquotes and one new
  preamble subsection; every step row of T1, T2 and T4 is byte-identical to
  HEAD.
- The brief named T1 only. T2 was swept and needed the same treatment, since the
  goal line forbids counting *any* step recorded as failed or outstanding
  (LESSONS 2026-07-27: a rule applied only to the input that taught it is half a
  fix). T3 was checked and needed a statement that it has no count at all.
- `bridge/EVIDENCE_LATENCY.md` was read **only at HEAD** (`git show HEAD:`,
  HEAD = `eb3ebd4`), never from the working tree, since m3-32 is editing it.
  The result is consistent with what m3-32's report says it wrote: the evidence
  keeps **twelve** as its as-run denominator and reconciles thirteen in prose;
  this document keeps **thirteen** as its specified list and reconciles twelve
  in prose. Neither grew a denominator.
- The §8 case A/C phrases "the six inputs" / "refreshed all six inputs" were
  found by the sweep and deliberately left: m3-12's report records them as
  verbatim quotations of the in-container measurement, which predates the reset
  node. They are history, not a pass claim, and not §11.
- Line endings verified: `git ls-files --eol` reads `i/lf w/lf`, and
  `git diff --numstat` equals `git diff --ignore-cr-at-eol --numstat`
  (57 / 13), so every changed line is real content.
- Nothing committed.

## Closed by this brief

`EVIDENCE_LATENCY.md` §B.7 ended with a request to `plc/` for this accounting
("requested here, not made here"). It is made here, in the same working tree as
m3-32's revision of that paragraph, so the requesting document and the
responding one land together (LESSONS 2026-07-26).
