# Report m4f-08c — two stale ruling sentences in the scenario doc

```
brief:               docs/briefs/m4f-08c-stale-ruling-sentences.md
status:              done
files_changed:       sim/scenarios/forklift_commissioning.md  (two sentences;
                                                               git diff
                                                               --numstat 10 7)
                     docs/reports/m4f-08c-stale-ruling-sentences.md (this file)
invariants_touched:  none
open_questions:      one, advisory — two past-tense residues inside the same
                     section 5 block, both outside this brief's sweep subject
next_suggested:      nothing blocking; the scenario doc is now consistent with
                     bc6a570 on both settled findings.
```

## What changed

Two hunks, both named by the brief. `git diff --numstat` reads **`10 7`**. No
figure, step, observable or findings-table row was touched.

**§5, the FINDING block's closing sentence.** Was "**Which form is intended is a
`plc/` ruling**, and it is not one this file may take … Requested in the report
for this file. Until it is ruled, record the observed value …". Now records that
the ruling was taken in `bc6a570`, that the **scale** form is the specified one,
that §11 5.3.4's Pass line reads `≈+0.060 m/s`, that the Pass line was the defect
rather than the program, and that §6.5 and §9's Group 3 row now say so beside it.

**§3, the start-order note's request sentence.** Was "A `SPEC.md` §11 revision to
state both outcomes is requested in the report for this file." Now states that
§11 5.1.1 **was revised in `bc6a570`** to state both outcomes, and carries the
shape of the revision: both readings pass, and the check is the pair — field bit
and distance read before the verdict is judged, the latch required to *hold*
rather than take a particular value.

## The sweep

Subject sweep over `ruling`, `ruled`, `requested`, `intended`, plus `may take`
and `until it is`, over the whole file. Seven hits after the edit, each read for
what it describes:

| Line | Text | Verdict |
|---|---|---|
| 92 | "Requested of `bridge/` in the report for this file" | **Correct as written.** Finding 4 is open — the `bridge.yaml` flip is queued to the owner behind the TIA read-back |
| 389–390 | the edited §5 sentence | the fix |
| 428 | "where a clear path was intended" | the crate stimulus, not a ruling |
| 458 | "Requested of `hmi/`: a hold-capable RESET control" | **Correct as written.** Finding 3 is open and in flight as `m4f-07b`; no `feat(hmi)` commit exists |
| 718, 719 | findings-table rows 1 and 2 | see below |

**No third sentence describes the settled question as open.** The two open
requests that survive are genuinely open, and they are the two the findings table
also marks open.

**Rows 1 and 2 were left alone deliberately.** Row 2's finding text still ends "a
revision stating both is requested", which reads oddly next to a Status of
"Closed by `bc6a570`" — but that is the shape of a findings register: the finding
column records what was raised, the Status column records what became of it, and
the two sit side by side on one line. Editing them is also forbidden by this
brief ("no … findings-table row changes"), so the question was not reopened by
rewording it.

## Open question, advisory

Two statements inside the §5 block are now past-tense facts written in the
present tense. Neither contains any of the sweep's subject words, so both are
outside what this brief was scoped to touch, and neither misleads a reader who
finishes the block:

1. the heading, "step 5.3.4's Pass line and §§7/9 predict different numbers" —
   a finding's title, of the kind that normally keeps its original wording;
2. the block's opening, "`SPEC.md` §11 step 5.3.4 says a demand of ≈0.2 … gives
   `≈+0.20 m/s`" — true when written, and now what §11 *said* rather than what it
   says. The new closing sentence resolves it three sentences later.

The block reads coherently as narrative — what it said, what was observed, how it
was ruled — so this is a judgement call rather than a defect. If the preference
is for the block to be true sentence by sentence rather than paragraph by
paragraph, it is one brief and two verbs.

## Scope notes

- Nothing outside the scenario doc and this report was written. `bc6a570`'s
  `plc/forklift/SPEC.md` diff was read to state the two closures accurately and
  was not edited.
- The tree was checked before starting: `1ed9b80` carries the m4f-08b work, and
  the other dirty paths belong to the `hmi/`, `plc/` and `interface` agents.
- No commit was made — see the note returned with this report.
