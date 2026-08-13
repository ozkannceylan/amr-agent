# Brief pub-02 — public README and media

gate:                none (repository publication, owner-directed)
agent:               infra (ad-hoc, owner-approved; write scope exactly: README.md at the repo root, assets/ at the repo root)
goal:                a visual-first, low-text public README that shows the running system, the deliberately minimal cell, the chosen AMR, and the current milestone state
invariants_touched:  none
inputs:              [docs/roadmap.md, docs/adr/0007-*.md, docs/adr/0002-*.md (platform choice), CLAUDE.md §1-§3, sim/README.md (cell signal table), bridge/EVIDENCE_LATENCY.md and EVIDENCE_CONNECT.md (headline numbers only), the media sources below]
deliverable:         README.md and assets/ (media referenced by it)
done_when:           the README renders on GitHub with the hero GIF and images working, text is minimal (the owner's requirement — show, don't lecture), the equipment table states plainly that the cell visuals are deliberately simple because the subject is the control architecture, the milestone table matches docs/roadmap.md exactly with M0-M2 done / M3 closing / M4 next, and no claim in it outruns the evidence
forbidden:           [editing anything outside README.md and assets/, editing docs/ or any layer directory, inventing figures, using vendor marketing images or any asset whose license is not verifiably permissive, mentioning AI assistance anywhere]

## Media sources

Copy into `assets/` (rename sensibly):
- `plc-drives-cell.gif` from the session scratchpad — 28 s, T1→T4, the
  S7-1500 program driving the Gazebo belt live. Hero.
- `cell.png` from the same scratchpad — the cell, three-quarter view.
- Optionally one watch-table capture from `plc/demo-cell/evidence/watch-table/`
  (reference in place, do not duplicate) to show the PLC side.

**The AMR visual:** the chosen platform is recorded in ADR 0002 — read it for
the vendor/model and its pinned source. Attempt, time-boxed (~20 min): fetch
the vendor's open-source description package at the pinned ref into the
scratchpad (never into the repo), verify its license is permissive, render
the model in Gazebo under WSL (llvmpipe works; GZ_PARTITION isolate;
Windows-side CopyFromScreen is the proven capture path — a grab script
pattern exists in the scratchpad), screenshot to assets/. If any step fails
or the license is unclear, DO NOT substitute a vendor photo — ship the README
with a text row ("platform: <name>, arrives at M5") and say so in the report.

## Content shape (keep it tight)

1. Hero GIF + one-sentence pitch: a PLC-supervised AMR fleet, built
   simulation-first with production-grade layer discipline.
2. A small mermaid architecture diagram (adapt CLAUDE.md §3, simplified).
3. "The demonstration cell" — image + the equipment table: each visual
   object → the control equipment it stands for → its signals (Conveyor →
   drive + encoder → ConveyorSpeedCommand/BeltPosition/BeltSpeed;
   through-beam sensor → analogue range input; panel → NC/NO contacts,
   wire-NC/program-NO note; e-stop deliberately a PROCESS stop until the
   F-CPU gate). One line above it: visuals are deliberately minimal — the
   work is the control architecture, not the art.
4. Headline measured numbers, three or four max, from committed evidence
   (20 Hz / 0 overruns; case-D freeze-to-reaction 2.301 s; closed-loop L7
   median 46.8 ms; CPU cycle ~1 ms on a 20 ms OB30) with file pointers.
5. Milestone table from docs/roadmap.md with status column.
6. A short "how it is built" note: docs/adr/ decision records, evidence
   discipline (every figure reproduces from a committed artifact), links to
   the key documents. No tutorial, no installation promises beyond what
   sim/setup and bridge/README already state.

Language: English (public portfolio). Tone: engineering, no hype.
