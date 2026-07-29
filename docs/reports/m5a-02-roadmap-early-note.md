brief:               docs/briefs/m5a-02-roadmap-early-note.md
status:              done
files_changed:       docs/roadmap.md (two-sentence note added directly under
                     the current-gate line, before the existing "M5, the
                     safety layer..." paragraph; no table row touched, no
                     renumbering); docs/reports/m5a-02-roadmap-early-note.md
                     (this file). Left uncommitted in the working tree — see
                     note below. bridge/config/bridge-double-forklift.yaml is
                     a concurrent agent's unrelated modification, confirmed
                     present but untouched by this brief.
invariants_touched:  none
open_questions:
  1. The paragraph immediately after the new note ("M5, the safety layer,
     keeps the entry condition ADR 0007 set for it: its first brief settles
     F-CPU-on-PLCSIM feasibility in the tool before any safety logic is
     written.") is now stale beside it: ADR 0009's context section records
     that as of 2026-07-29 the F-runtime compiled, downloaded, reached RUN
     and executed F-logic end to end in the tool, so "before any safety
     logic is written" no longer holds. Rewriting that paragraph is prose
     revision beyond this brief's deliverable (one note, no table change),
     so it is reported rather than touched.
  2. m5a-01's report open question 3 flagged PLAN.md's M5 block as carrying
     the superseded feasibility-trigger wording. Re-read during this brief,
     PLAN.md's M5 section already states the narrowed trigger ("the
     abort-to-fallback trigger has narrowed to the formal acceptance
     procedure") — that item reads as resolved by a concurrent edit.
     TODO.md's "owner — URGENT first" block, however, still phrases the
     F-layer checkpoint as pending ("Safety Advanced V21 licence present; an
     empty F-project compiles; the F-runtime group reaches RUN" as items yet
     to happen) rather than as observed and closed per ADR 0009. TODO.md is
     outside arch-docs's write scope entirely (CLAUDE.md §5 roster table),
     so this is reported, not edited.
  3. This brief's own git instruction — "pathspec-scoped commit of exactly
     roadmap.md plus your report" — conflicts with this agent's standing
     hard rule for the session: "Do not commit. Leave changes in the
     working tree; the orchestrator commits by pathspec." No brief or
     dispatch message can authorize overriding that rule, so the commit was
     not performed; see next_suggested for the exact command.
next_suggested:      Commit is outstanding — run (repo-local identity is
                     already Ozkan Ceylan / ozkannceylan@gmail.com, confirmed
                     this session): git commit -- docs/roadmap.md
                     docs/reports/m5a-02-roadmap-early-note.md -m
                     "docs(infra): note the early cell-scope safety opening"
                     (pathspec-scoped, not bare — bridge/config/bridge-double-forklift.yaml
                     is a concurrent agent's unstaged change and must stay
                     out of this commit). Separately: a small follow-up note
                     to reconcile the now-stale "before any safety logic is
                     written" roadmap paragraph against ADR 0009, and a
                     reconciliation of TODO.md's URGENT F-layer-checkpoint
                     wording against the same ADR (TODO.md is outside this
                     agent's write scope).
