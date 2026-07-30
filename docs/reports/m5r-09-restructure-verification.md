# Report m5r-09 — verification of the ADR 0010 restructure round

```
brief:               docs/briefs/m5r-09-restructure-verification.md
status:              done
files_changed:       docs/reports/m5r-09-restructure-verification.md (this file, only)
invariants_touched:  none. Read-only run. Invariants 1-13 were checked against
                     the new roadmap rows and none is amended by them.
open_questions:      none of the verifier's own; eight findings below
next_suggested:      one orchestrator commit reconciling PLAN.md and TODO.md
                     against the full report directory (findings 1-5), then
                     one plc or safety-spec line for finding 6
```

**Verdict: fail — bounded to check 6.**

Checks 1, 2 and 3 pass outright. Checks 4 and 5 pass with findings. Check 6, the
tracking-file reconciliation against the full report directory, fails: PLAN.md
predates six of the round's reports, an open item was deleted rather than closed,
and two reports' open questions entered no queue. The restructure's substance —
the ADR, the roadmap, the four sweeps, the contract and public tables — is sound
and none of it needs revisiting. What fails is the round's closure, and it closes
on one tracking-file commit.

Every sweep below is my own, whitespace-normalised, over all git-tracked files
excluding `docs/adr/`, `docs/briefs/`, `docs/reports/` and `docs/LESSONS.md`.
The m5r reports' self-verdicts are cited only where I confirmed or refuted them.
Two accepted deviations were treated as accepted and are not findings:
`assets/CREDITS.md`'s dependency-fixed sentence (m5r-04) and
`plc/demo-cell/SPEC.md`'s two-gate safety row (m5r-06).

---

## Check 1 — no live document carries a pre-ADR-0010 gate reference

**pass.**

Artifacts: independent sweep script over 100% of tracked non-binary files
outside the four excluded paths, matching on a whitespace-collapsed copy of each
file and separately on adjacent-line pairs so a phrase broken across a line break
still matches (LESSONS 2026-07-27, #45).

- `\bM(8|9|10|11|12)\b` — **9 hits, all legitimate.** Eight sit inside
  `docs/roadmap.md`'s renumbering-history paragraph, which describes the ADR 0007
  and ADR 0008 rounds by name and must keep their numbers. The ninth is
  `CLAUDE.md` §9's PLC-tag example, "`ZoneAOccupied`, not `M12`".
- Per-directory re-verification of the four sweep agents' closing claims:
  `sim/` **0**, `docs/interfaces/` **0**, `plc/` **0** M7–M12 tokens.
  `docs/safety/` has **1**, `PL-SCENARIOS.md` §0's "the end-to-end demonstration
  is folded into **M7**" — a correct forward reference to the new gate.
  All four agents' "zero remaining" claims are confirmed.
- Old gate names swept as prose, not numbers: *vehicle gate*, *navigation gate*,
  *safety gate*, *fleet gate*, *demonstration gate*, *PLC integration*,
  *arm integration*, *arm gate*, *simulated vehicle*, *Hermes*, *RB-KAIROS* /
  *rbkairos*. Every surviving occurrence either states the retirement or removal
  with an ADR 0010 citation, or is a historical citation of what an earlier ADR
  said. `sim/README.md` line 189's heading is byte-identical to the text
  `docs/interfaces/bridge-design.md` item 15 quotes — verified by extracting both.
- `git diff 2a62d77 HEAD -- sim | grep "^-" | grep -w M4` is empty: m5r-07's
  "no M4 reference removed" claim is confirmed.

Not a failure of this check, recorded for completeness:
`docs/interfaces/vda5050-subset.md` lines 261-263 still define
`typeSpecification.seriesName` as RB-KAIROS per ADR 0002 with `agvClass` =
`CARRIER`. That is a retired *platform*, not a gate reference, it is correctly
outside m5r-08's forbidden list, and `docs/TODO.md` carries it as M6-briefing
work (commit 9ce38f1). Correctly handled.

## Check 2 — roadmap, PLAN, TODO, CLAUDE.md §6 and README agree with ADR 0010

**pass.**

Artifacts: `docs/roadmap.md`, `docs/PLAN.md`, `docs/TODO.md`, `CLAUDE.md` §6
(lines 172-186), `README.md` "Milestones" (lines 107-142), read in full against
ADR 0010 D2/D3/D4/D5/D6/D7.

| | roadmap | PLAN | TODO | CLAUDE §6 | README |
|---|---|---|---|---|---|
| gate set | M0–M7 | M0–M7 | M5/M6/M7 by name | M0–M7 | M0–M7 |
| M5 name | Sensored autonomous forklift | same | same | same | same |
| M6 name | VDA 5050 fleet at scale | same | same | same | same |
| M7 name | LLM operations layer and final demonstration | same | same | LLM operations layer | LLM operations layer + final demonstration |
| M4 status | closing | closing | open, in closing | deferred to roadmap | closing |
| arm | out of scope | removed | — | no row | out of scope |
| Hermes | absorbed into M7 | — | Pre-M7 decisions | no row | absorbed into M7 |

No disagreement. `CLAUDE.md` §6's M7 title omits "+ final demonstration"; its own
"closes when" cell supplies it ("closes with the recorded end-to-end
demonstration"), so the substance matches. `CLAUDE.md` §6 carries no M4 status
marker — a deliberate choice disclosed in m5r-03 open question 1, and the correct
one: the same section's kept-verbatim sentence says the current gate is tracked
in `docs/roadmap.md`, so a marker in the contract would be a second source of
truth for gate status.

Invariant check on the new rows: M5 (e) states the HMI emergency button as a
process stop plus F-layer display, "never a safety function over the network
(invariant 1, ADR 0010 D6(b))"; M5's map view defers its data path rather than
drawing a shortcut edge (invariant 11); M7 confines the LLM to the fleet layer
with no actuator writes (invariants 6, 11) and requires normal operation with it
unreachable (invariant 2). None of the three rows amends an invariant.

One cross-document disagreement was found and is **finding 6**, in `plc/` rather
than in these five files.

## Check 3 — the four D6 open decisions are recorded as open, none resolved

**pass.**

Artifacts: `docs/roadmap.md` lines 80-91 and the M5 row; `docs/PLAN.md` lines
21-24; `docs/TODO.md` lines 60-68; independent sweep for `D6`, *map view* /
*map-view*, *emergency button*, *attachment point*, *one gate or staged*.

- **(a) HMI map-view data path** — open in roadmap ("decided by its own ADR at M5
  briefing"), PLAN, and TODO with a definition of done. No document anywhere
  names a data path; `hmi/` contains no map-view design and `hmi/README.md`'s
  boundary section still forbids ROS 2 and `gz` transport in any form.
- **(b) HMI emergency button** — recorded as the reading it is, in the roadmap's
  D6 paragraph and again inside the M5 criterion. Correctly absent from TODO:
  ADR 0010 marks it "not scheduled", so a work item would misrepresent it.
- **(c) LLM attachment point** — open in roadmap, PLAN, and TODO ("Pre-M7").
- **(d) M6 one gate or staged** — open in roadmap, PLAN, and TODO
  ("done when its findings are owner-ruled (ADR 0010 D6d)").

No m5r deliverable resolves any of them. `git diff --name-only 2a62d77 HEAD --
docs/adr/` returns exactly one path, the new ADR 0010: no accepted ADR was
edited, so CLAUDE.md §8 holds.

## Check 4 — M0–M4 criteria unchanged; `Forklift M4 gate` survives

**pass-with-findings.**

Artifact: `git show 517b0a4^:docs/roadmap.md` against `git show
HEAD:docs/roadmap.md`. The M0–M4 table rows are **byte-identical** — both extract
to md5 `6bfc4e788bd7c4ded50fed6991a0d45e`, and a direct `diff` of the two
extractions is empty. `docs/roadmap.md` was touched exactly once in the round
(517b0a4), so that comparison spans the whole round. The only M0–M4 change is the
M4 status line, which the m5r-02 brief explicitly permitted.

`Forklift M4 gate`, the TIA watch-table name: pre-round (2a62d77) it appeared in
six files; at HEAD it appears in `plc/README.md` (1), `plc/forklift-safety/SPEC.md`
(2), `plc/forklift/SPEC.md` (1), `sim/scenarios/forklift_commissioning.md` (4) and
`docs/reports/m4f-04-plc-forklift-spec.md` (1) — **unchanged, no rename anywhere**,
including in the plc sweep that edited two of those files. One occurrence is gone:
`docs/TODO.md`'s, deleted with its whole item in d3ed03b. That is a queue
deletion, not a rename, and it is **finding 1**.

## Check 5 — write scope, pathspec cleanliness, conventional commits, attribution

**pass-with-findings.**

Artifact: `git show --name-status` for all 17 commits from c72dce7 to 40f9af4,
plus `git log --format='%an|%ae|%cn|%ce'` over the same range.

**Write scope.** Every agent stayed inside its area plus its report:
safety-spec → `docs/safety/` (3 files); plc → `plc/` (3 SPECs); sim → `sim/`
(12 files); interface → `docs/interfaces/` (2 files); arch-docs → `docs/adr/` and
`docs/roadmap.md`. The infra agent's `CLAUDE.md`, `README.md` and
`assets/CREDITS.md` edits are all named in their briefs' `deliverable` fields, so
`assets/CREDITS.md` is in scope, not a stray. No agent wrote outside.

**Pathspec cleanliness.** Every commit's file set equals its brief's deliverable
plus its report. Nothing unrelated was swept in — checked commit by commit, which
matters here because seven agents ran concurrently and LESSONS 2026-07-27 (#36)
records a bare `git commit` sweeping an agent's staged file into an unrelated
message. Deliverable and report land together in every case except m5r-01, split
across 166ffb3 and 3793861; both are one logical change each.

**Conventional commits.** All 17 use `type(scope): imperative`, and every scope
(`infra`, `adr`, `interfaces`, `sim`, `plc`, `safety`) is in CLAUDE.md §7's
closed area list.

**Attribution.** Author *and* committer on all 17 are `Ozkan Ceylan
<ozkannceylan@gmail.com>`. A case-insensitive scan of every message body in the
range for `co-authored`, `generated with`, `claude`, `anthropic`, `assistant`,
`copilot`, `chatgpt` returns nothing. `.claude/settings.json` still reads
`{ "attribution": { "commit": "", "pr": "" } }`. Repository content carries no
tooling attribution: the only `claude` hits outside `CLAUDE.md` and `.claude/`
are brief and report *filenames* of the form `*-claudemd-*`, which name the
contract file. `docs/LESSONS.md` is +2/-0, append-only.

Two findings against this check: **finding 7** (branch name) and **finding 8**
(three owner commits inside the stated window).

Incidental checks on the round's edits to executable files, since a sweep that
touches code can break it: `bash -n` passes on `sim/setup/install.sh` and
`stack.sh`; `py_compile` passes on both edited launch files; the edited
`nav2_params.yaml` still parses as YAML; `git ls-files --eol` reports `i/lf w/lf`
on every file the round touched, with `text eol=lf` in force on the two shell
scripts.

## Check 6 — TODO and PLAN reconcile against the full report directory

**fail.**

Artifact: `git log -1 -- docs/PLAN.md` → d3ed03b, 2026-07-30 19:07:16.
`git log --since=19:07:20 --name-status -- docs/reports/` → six reports landed
**after** PLAN's last write: m5r-02 (19:07:59), m5r-05 (19:09:57), m5r-06
(19:10:23), m5r-07 (19:13:04), m5r-08 (19:19:15), m4f-10 (19:26:20).

PLAN.md therefore still records only "m5r-01 … closed 166ffb3" and describes
m5r-02…-08 as work that "ran in parallel" and "follows m5r-07". This is the
failure mode LESSONS 2026-07-27 (#44) exists to prevent, restated verbatim in
CLAUDE.md §11: *reconcile TODO and PLAN against the full report directory before
the verifier runs, not against the last report read.* TODO.md's own orchestrator
row states the sequence — "reconcile PLAN/TODO against the full report directory,
then run m5r-09" — and this verification was dispatched with that step
incomplete. Findings 1, 2, 3, 4 and 5 are the consequences.

---

## Findings

**1. An open item was deleted rather than closed (checks 4 and 6).**
Commit d3ed03b removed `docs/TODO.md`'s "Build FB_ForkliftTeleop in TIA…" item
whole. That item carried a second, independent sub-item: *"At that download also
check m3-37 finding 7: the built program declares `ResetEdgeMemory_1` where SPEC
§3.2 says `ResetEdgeMemory` — align one of them."* The build half is genuinely
closed — TODO's "build COMPLETE on the CPU (2026-07-30 TIA handover,
live-verified)" section records it. The `ResetEdgeMemory_1` half is not:
`git grep ResetEdgeMemory_1` over the whole tree returns exactly one hit,
`docs/reports/m3-37-gate-verification.md:394`, and `plc/forklift/SPEC.md` still
names `.ResetEdgeMemory` at lines 243, 864, 878, 1109, 1112 and 1337 with no
as-built note. CLAUDE.md §11 says closed items are deleted; this one was not
closed. It is also precisely the hazard LESSONS 2026-07-30 (#81) names — TIA's
silent `_1` collision suffixes, swept for after every download. Restore it as a
plc or owner item.

**2. PLAN.md does not reflect the report directory (check 6).**
Six reports post-date PLAN's last write (evidence under check 6). `m4f-10`
appears in neither PLAN nor TODO at all. Rewrite the m5r section to record
m5r-02…-08 closed, with their commits, and add m4f-10.

**3. TODO's orchestrator row is stale against its own sequence (check 6).**
`docs/TODO.md` lines 55-58 still read "dispatch m5r-08 after m5r-07, reconcile
PLAN/TODO against the full report directory, then run m5r-09". m5r-08 closed at
19:19 in e864e5b. The row's remaining work is the reconciliation itself.

**4. m4f-10's open questions are untracked (check 6).**
`docs/reports/m4f-10-stack-launcher.md` declares five open questions, "one of
which is a doc/brief disagreement", and a `next_suggested` owner run on WSL
against PLCSIM. None of it reached TODO.md. Separately, `stack.sh` is a new
repo-root file that CLAUDE.md §4's layout does not list and that no layer
README's "This layer must not access" section covers — worth one line somewhere
before it becomes precedent. (m4f-10's substance is outside this brief; only its
tracking is in scope.)

**5. m5r-07's open question 5 raised a reproducible defect that entered no queue
(check 6).** I reproduced it independently: `xml.etree.ElementTree.parse` fails
on all three worlds — `sim/worlds/warehouse.sdf` line 16 col 20,
`sim/worlds/forklift_arena.sdf` line 326 col 49, `sim/worlds/cell.sdf` line 15
col 8 — from `--` inside XML comments. LESSONS 2026-07-27 (#25) already records
this exact mechanism for `cell.sdf`, so the project has now met it twice. It is
pre-existing and correctly outside m5r-07's scope, but a report open question is
not a queue. Related: CLAUDE.md §11 obliges a LESSONS append whenever a report
carries a correction; d0c6d44 added two entries, neither covering the m5r-04
CREDITS deviation, the m5r-06 two-gate deviation, or the m5r-07 M3-label
corrections.

**6. `plc/forklift-safety/SPEC.md` and `docs/safety/SRS.md` disagree on SF-08's
landing gate (check 2).** The SPEC now reads *"`opcua-nodes.md` §4 defines
`Safety/SafetyResetRequired` for the **fixed cell** (SF-08, M6)"*. SRS §4's
traceability row reads *"SF-08 | Monitored reset | … | AT-08 | **M5** (cell and
vehicle instances, one gate)"*, and the SRS's gate-references paragraph puts "the
cell instance of SF-08" at M5. ADR 0010 D7 lists SF-08's cell instance **and**
vehicle instance at M5, and sends only SF-05 and SF-06 to M6; `docs/roadmap.md`'s
M6 row likewise names only SF-05/SF-06 as the fixed-equipment F-I/O landing with
the stations. **No document authorises an SF-08 instance at M6.** The m5r-06
brief itself directed this mapping ("1024 (fixed-cell SF-08 'M9' → M6)"), so the
plc agent complied with its brief; the inconsistency originates in the brief.
One of the two statements needs a one-line correction — and if M6 is the intended
reading, it needs the roadmap and SRS to say so, not just the plc SPEC. This is
**distinct** from the accepted `plc/demo-cell/SPEC.md` two-gate deviation.

**7. The branch name reintroduces a `claude/*` ref (check 5).**
All 17 round commits sit on `claude/forklift-sim-architecture-plan-zjdeq4`,
present locally and at `origin`. CLAUDE.md §7 fixes the template to
`feat|fix|docs/<area>-<slug>` over a closed area list, and forbids tooling names
in branch names. `docs/reports/pub-01-public-readiness-audit.md:123` recorded
"All 8 refs conform to the branch template. No `claude/*` ref exists in any…" —
that statement is now false. Precedent is LESSONS 2026-07-26 (#7) and
`m0-04-verify.md` finding 2: platform-provisioned, surfaced rather than silently
renamed, and the owner's to resolve. Commit messages, author fields and committer
fields are all clean; this is the only attribution surface that is not. Note also
that `main` holds only three commits (03afa60, 4419818, 0f17f07) while this
branch is 67 ahead — the project's whole history lives on a non-conforming ref.

**8. Three 2026-07-30 owner commits are non-conventional (check 5).**
46caa95 and 0007b16 ("Revise project milestones in README") and 2a62d77 ("Refine
project description in README.md"), authored
`114666033+ozkannceylan@users.noreply.github.com` with committer `GitHub`. Not
agent work and not attribution leaks, but they fall inside check 5's stated
window and they are the hand-edits ADR 0010's context and LESSONS 2026-07-30
(#82) were written to correct. Recorded so the window's ruling is complete; no
action implied beyond the rule already appended.

---

## Minor observations, not findings

- **Term drift, disclosed and reconciled.**
  `sim/scenarios/forklift_commissioning.md` §12 keeps the heading "T6 (M5,
  early)" while `plc/` and `docs/interfaces/` adopted "M5 opening wave". Lines
  778-782 reconcile the heading explicitly against ADR 0010, so it reads
  correctly; only the heading string differs. m5r-06 open question 4 predicted
  exactly this and m5r-08 answered it — the coordination worked.
- **CLAUDE.md §5's roster still has no `infra` row**, though m5r-03 and m5r-04
  were issued to that agent. Long-standing ad-hoc precedent (LESSONS 2026-07-26,
  #6) and correctly outside m5r-03's forbidden list, but roster and practice have
  now disagreed across three rounds.
- **Every layer README's "This layer must not access" section is intact**, and
  the round's one layer-README edit (`sim/README.md`) does not touch it —
  confirmed by diffing that section across 2a62d77..HEAD.
- **No secret-shaped addition** in the round's diff. The one match,
  `declare -A COMPONENT_TOKEN` in `stack.sh`, is a table of `pgrep` match strings.
- **The working tree is clean** and nothing was staged or committed by this run.
