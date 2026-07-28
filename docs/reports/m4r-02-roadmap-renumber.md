# Report m4r-02 — roadmap and plan onto the ADR 0007 order

brief:               docs/briefs/m4r-02-roadmap-renumber.md
status:              done

files_changed:
- docs/roadmap.md — gate order citation moved from ADR 0004 to ADR 0007 with the
  forward pointer kept; table rows M4 to M11 replaced by ADR 0007 §1's rows
  (M4 safety layer on the fixed cell, M5–M8 unchanged in number with ADR 0007's
  added acceptance-test and showcase content, M9 demonstration, M10 arm, M11
  Hermes parked with its m4-00 entry condition); three closing notes added — the
  showcase rule (M4/M8/M9, from ADR 0007 §3), the "not safety layer complete"
  statement naming SF-01/07/08 at M4 against SF-05/06 at M8 and the vehicle chain
  at M5/M6, and the four-row renumbering map with the filename-retention rule.
  M0, M1, M2 and M3 rows and the three closed-gate lines are untouched.
- docs/PLAN.md — the gate-order line now cites ADR 0007 and states what moved;
  the filename note gained the m4-00-hermes-survey → M11 mapping; a "Next gate:
  M4" section was added stating the gate is not open, pointing at the roadmap row
  for the criterion, recording ADR 0007's requirement that the first M4 brief
  settles F-CPU-on-PLCSIM feasibility in the tool before any safety logic, and
  repeating that M4 is cell-scope only. M3's scope, status, exit criterion and
  brief list are untouched.

invariants_touched:  none

open_questions:
- Deliverable label for M8: the previous roadmap row read "PLC/fleet
  integration"; ADR 0007 §1 prints "PLC integration", which is also CLAUDE.md
  §6's label. The ADR was taken as the authority and the roadmap now reads "PLC
  integration". Flagged because it is the one row where matching the ADR changed
  text the ADR itself calls unchanged.
- Path formatting deviates from ADR 0007 in the M4 and M11 rows only: the ADR
  backticks `docs/safety/SRS.md` and `docs/reports/m4-00-hermes-survey.md`, the
  roadmap writes them plain, matching its own existing style for
  docs/reports/m0-04-verify.md. Content is byte-identical otherwise (verified by
  comparing both tables' M4–M11 rows with backticks stripped: all eight match
  exactly, including `Safety/`, SF-20…29 and the embedded showcase emphasis).
- Stale ADR 0004 gate references remain outside this brief's write scope, exactly
  as ADR 0007's consequences list them: docs/safety/SRS.md, docs/safety/PL-SCENARIOS.md
  lines 28–32, plc/demo-cell/SPEC.md line 1450, sim/README.md line 237, and
  docs/TODO.md lines 32 and 39. docs/TODO.md is the orchestrator's; the other
  four need their owning agents. Until they are done, roadmap.md and PLAN.md
  agree with ADR 0007 while TODO.md line 32's unissued m2-04 done_when still
  quotes the old numbers — a tracking-file disagreement I cannot close from here.
- Not verified: whether the roadmap should also record ADR 0007 §2's per-function
  SF table. The brief limited the carry-over to criterion lines, so the M4/M5/M6/
  M8/M10 rows carry their AT and SF references and the roadmap points at the ADR
  for the rest.

next_suggested:      Issue the docs/safety/, plc/ and sim/ staleness sweeps and the
TODO.md line 32/39 correction so no document outside CLAUDE.md §6 still carries
ADR 0004 gate numbers.
