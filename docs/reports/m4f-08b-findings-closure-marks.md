# Report m4f-08b — scenario-doc findings closed by their commits

```
brief:               docs/briefs/m4f-08b-findings-closure-marks.md
status:              done
files_changed:       sim/scenarios/forklift_commissioning.md  (section 11
                                                               findings table
                                                               only, 7 lines)
                     docs/reports/m4f-08b-findings-closure-marks.md (this file)
invariants_touched:  none
open_questions:      one — the scenario-3 FINDING block still reads as open
next_suggested:      one line into section 5's FINDING block pointing at
                     bc6a570, so a reader who stops at scenario 3 is not left
                     with a ruling described as untaken.
```

## What changed

Section 11's findings table gained a **Status** column; the five findings rows
are the only lines touched. `git diff --numstat` reads `7 7` — the header, the
separator and the five rows. No procedure step, no operator step, no observable,
no rehearsal figure and no evidence text was edited.

| # | Status written |
|---|---|
| 1 | **Closed by `bc6a570`** — the scale form was ruled correct, §11 5.3.4's Pass line now reads `≈+0.060 m/s`, §6.5 states the cap as a scale rather than a ceiling, and §9's Group 3 row says so beside it. Recorded plainly: the rehearsal reading was the specification's and the Pass line was the defect |
| 2 | **Closed by `bc6a570`** — §11 5.1.1 now states that both readings pass, names the race that decides which appears, and replaces the single-value check with a pair check (field bit and distance read before the verdict is judged; the latch must *hold* rather than take a value) |
| 3 | **Open, in flight** — names `docs/briefs/m4f-07b-h6-and-holdable-reset.md` as the resolution path, and says what it does: RESET becomes press-and-hold capable, `TRUE` every cycle while held, `FALSE` on release. Until it lands, `forklift_stimulus.py hold --reset` is the way to produce the hold |
| 4 | **Open, queued to the owner** — points at `docs/TODO.md`, *owner — M4 queue*, the "after the TIA read-back: point `bridge/config/bridge.yaml` at the `Forklift` groups" step, with the reason it is deliberately not made earlier |
| 5 | **Closed by `aa593ed`** — sim's own, recorded in §6 with its arithmetic and in `sim/README.md` with the arena |

Finding 3 was checked against the log rather than assumed: `git log aa593ed..HEAD`
carries no `feat(hmi)` commit, and `hmi/` is dirty in the working tree, so
m4f-07b is in flight and the row is marked open rather than closed.

## Open question

**Section 5's `FINDING` block still reads as open.** It ends "which form is
intended is a `plc/` ruling, and it is not one this file may take", which was
true when written and is now stale — `bc6a570` took it. The same applies more
mildly to §3's start-order note, which describes a §11 revision as *requested*.
Both sit inside procedure sections that this brief's `forbidden` list puts out
of bounds ("editing any scenario step or rehearsal figure"; "no procedure step,
figure or evidence text changes"), so neither was touched.

Raising it rather than half-fixing it: a reader who stops at scenario 3 sees a
ruling described as untaken while §11 says it is closed, and that is exactly the
two-documents-disagreeing shape the verifier has failed a gate on before. One
sentence in each of the two blocks, changing no figure and no step, would close
it — but it needs a brief that permits the edit.

## Scope notes

- Nothing outside the scenario doc and this report was written. `bc6a570`'s
  `plc/forklift/SPEC.md` diff, `docs/TODO.md` and
  `docs/briefs/m4f-07b-h6-and-holdable-reset.md` were read to state the
  closures accurately, and none was edited.
- No commit was made — see the note returned with this report. The tree was
  verified clean of m4f-08 work first: `aa593ed` carries all five files of the
  previous brief, and the only dirty paths belong to the `hmi/` agent.
