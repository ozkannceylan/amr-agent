# Report m5-02b — roadmap records ADR 0011 and closes D6(a)

```
brief:               docs/briefs/m5-02b-roadmap-adr-0011-note.md
status:              done
files_changed:       [docs/roadmap.md]
invariants_touched:  none
```

## What changed, four edits plus one consistency touch

1. **Current-gate line (header).** Now reads M5 — Sensored autonomous forklift
   (ADR 0010 D2, architecture ruled by ADR 0011). M4 is carried as **closing**
   on the owner's recorded commissioning showcase and the m4f-09 gate
   verification, with its criteria and agent-side completion stated as before.
   This matches docs/PLAN.md, which already reads "M4 — CLOSING" plus "Current
   gate: M5"; the two files agreed before this edit only in PLAN.

2. **New ADR 0011 paragraph**, placed after the ADR 0009 paragraph where the
   roadmap records which ADRs govern. One paragraph, four settled rulings
   (D1 onboard safety controller; D2 configured F-DI stimulated by the PLCSIM
   Advanced API by tag name, with its feasibility condition and named
   standard-DB fallback stated; D3 motion envelope in autonomous mode with the
   M4 teleop phrasing unchanged; D4 read-only monitoring plane, no write
   endpoint, no publisher, process plane still the only command path) and the
   D5 claim boundary — PLr targets from the documented risk assessment, **no
   achieved PL, Category, SIL or PFH**, no acceptance test, no program
   signature, while the project is hardware-free.

3. **M5 row, last sentence only.** "The map-view data path is decided by its own
   ADR at M5 briefing (ADR 0010 D6(a))" is replaced by "The map-view data path
   is the read-only monitoring plane of ADR 0011 D4, which closes ADR 0010
   D6(a)." Criteria (a)–(e) are untouched, not restated and not reworded.

4. **D6 paragraph.** Opens "Of the four decisions ADR 0010 D6 recorded as open,
   one is closed and three remain open." (a) is rewritten as closed by ADR 0011
   D4, noting the one added topology edge in a third style and that invariant 11
   is unchanged. (b), (c) and (d) are carried word for word behind an explicit
   "Still open:" and are not resolved.

5. **Consistency touch, disclosed.** Line 28 read "built under its fallback rule
   **while M4 is still the current gate**", which the new header contradicts
   directly. Changed to "ahead of M4's closure" — meaning preserved, tense claim
   removed. The following clause, that ADR 0009's fallback rule retires once M4
   closes, is unchanged and still accurate: M4 has not closed. This is the only
   edit outside the brief's four; it was made because leaving it would have put
   a current-gate contradiction inside one file.

Nothing else in the file changed. No ADR, PLAN.md, TODO.md, CLAUDE.md or
README.md was touched. Nothing was committed.

## Verification performed

- Grep for "current gate / M4 remains / still M4" over the revised roadmap
  returns exactly one hit, the header line.
- ADR 0011's own preamble and D4 were read for the wording of the closure, so
  the roadmap cites the ADR rather than paraphrasing it loosely; the phrase
  "read-only by construction, not by configuration" is left in the ADR rather
  than duplicated here, since a paraphrase that drifts is worse than a citation.
- No PL, SIL, Category or PFH figure appears anywhere in the new text; the only
  claim wording is the D5 boundary, stated as a non-claim.
- docs/PLAN.md was read (not edited) to confirm it does not now disagree with
  the roadmap. It does not.

```
open_questions:
  - CLAUDE.md §3 does not yet carry ADR 0011 D4's monitoring-plane edge. The
    roadmap now states the edge exists, so until the separate owner-approved
    infra brief lands (m5-02 appears to be it), the contract's topology and the
    roadmap disagree by one edge. ADR 0011's preamble already rules that the ADR
    is the newer statement; flagged because it is outside this agent's write
    scope and the verifier will see both documents.
  - docs/TODO.md is outside this agent's write scope and was not read for queue
    state. If it still carries "D6(a) — map-view data path, open", that item is
    now closed by ADR 0011 D4 and needs deleting by whoever owns that file.
  - The README milestone table was not inspected (out of scope). Per the
    2026-07-30 lesson, roadmap.md is the single source and other tables follow
    it via a brief; if the README repeats the D6(a) deferral it needs its own.

next_suggested:      Verify m5-02 has landed the CLAUDE.md §3 monitoring edge,
                     then reconcile TODO.md's D6(a) item against this closure.
```
