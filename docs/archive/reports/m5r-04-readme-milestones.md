# Report m5r-04 — public README milestone table and narrative per ADR 0010

```
brief:               docs/briefs/m5r-04-readme-milestones.md
status:              done
files_changed:       [README.md (Milestones section only: lead line, table,
                      archived-rows paragraph, gate-order paragraph),
                      assets/CREDITS.md (closing paragraph, one gate reference)]
invariants_touched:  none
open_questions:      see below
next_suggested:      verifier sweeps every gate number above M4 by subject across
                     docs/ and the layer READMEs, not only the four files this
                     round names.
```

## What changed

**README.md, Milestones section only.** The table now carries seven rows, M0–M7,
matching ADR 0010 D7: M0–M3 **done**; M4 **closing** — showcase recording and gate
verification pending (D7 corrects the owner's "done" mark); M5 *Sensored autonomous
forklift*, M6 *VDA 5050 fleet at scale*, M7 *LLM operations layer + final
demonstration*, all planned. The two rows the 2026-07-30 hand-edit deleted are
accounted for in prose rather than restored as rows: the arm is out of scope (D5)
and the Hermes command path is unparked into M7 as an evaluation candidate (D4), so
neither has a row of its own.

The lead line read "Next gate: M4" above a table marking M4 done; it now reads
"Current gate: M4", which agrees with the table's *closing* status and with
docs/roadmap.md.

The archived-rows paragraph now states what ADR 0010 rules rather than the
hand-edit's partial account: safety and autonomy both land on the forklift built at
M4, which is the vehicle platform from M5 onward (D1, D2); the VDA 5050 client, the
fleet manager and PLC integration merge into one fleet gate — four forklifts, ten
PLC-owned stations, the counts as D3 fixes them (5 loading + 5 unloading); the LLM
layer closes the program and absorbs the end-to-end demonstration as its exit
criterion (D4); the arm is out of scope with its SRS functions marked, not deleted
(D5).

The gate-order paragraph now cites ADR 0010 as the order in force, names ADR 0008
and ADR 0007 as the orders it supersedes above M3, and states that M0–M4 keep their
numbers and criteria. It closes on the embedded-recordings principle (D7): each of
the last three gates closes on its own recording.

Untouched, as the brief requires: the video lead and its caption, the Architecture
section and its diagram, the "How it started — the M3 fixed-cell loop" section with
its media and figures, and "Where things are". No showcase media was removed or
reordered. No deadline appears anywhere.

**assets/CREDITS.md**, closing paragraph — see the deviation below.

## Deviation from the brief's literal wording, disclosed

The brief instructs that CREDITS.md's line "the vehicle enters the demonstration at
M6" reads **M5**. Written that way the sentence is false under ADR 0010 D1: the
RB-Kairos is *retired* as the vehicle platform, so it enters no gate at all, and the
mechanical M6→M5 swap would have converted a stale gate number into a wrong claim
about the current program. This is LESSONS 2026-07-27 (#47) — when a value is
corrected, sweep for statements that *depend on its scope*, not only occurrences of
the string.

The edit made instead stays inside the same three lines and carries the renumber
while correcting the dependency:

    The RB-Kairos render carries no claim about this project's own progress. It was
    the platform selected for the vehicle gate, now M5; ADR 0010 retired it in favour
    of the in-house forklift, and nothing in it was ever integrated.

Revert to a bare "M5" only if the orchestrator wants the literal wording; the claim
would then need a different owner.

## open_questions

1. **The RB-Kairos render's place in the repository.** With the platform retired,
   `assets/rb-kairos-gazebo.png` illustrates nothing the program still contains, and
   its provenance table row plus the reproduced BSD-3-Clause notice exist to license
   an image no document now needs. Removing the image, its row and its notice is a
   separate decision (and a separate brief); this brief's scope was one line.
2. **docs/roadmap.md still carries the old M5–M12 order** at the time of writing, so
   the README's table and the roadmap it links to disagree until m5r-02 lands. The
   README was repaired against ADR 0010 directly, as briefed, not against the
   roadmap's current text.
3. **The Architecture section's ADR 0009 sentence** ("their cell-scope core is being
   built early on the forklift twin") reads as an exception under ADR 0010 D2, which
   makes that content the M5 gate's own subject matter. Correct today while M4 is the
   current gate; it needs re-wording when M5 opens. Out of this brief's scope.
