# Report m4r2-10 — README milestone curation and the architecture diagram

```
brief:               docs/briefs/m4r2-10-readme-milestones-diagram.md
status:              done
files_changed:       [README.md,
                      docs/reports/m4r2-10-readme-milestones-diagram.md]
invariants_touched:  none
open_questions:      three, all wording or scope, listed below
next_suggested:      the post-demo ADR reconciles docs/roadmap.md with the
                     README's archived M5/M6 rows
```

---

## What changed in README.md

Four hunks, 40 insertions and 6 deletions, nothing else in the file.

1. **Milestone table.** `M5 — Safety layer on the fixed cell (F-CPU)` and
   `M6 — Simulated vehicle` read `archived` instead of `planned`. No other row,
   heading, GIF, caption or link changed.
2. **One line under the table** stating the path forward: the archived rows moved
   onto the forklift twin, the VDA 5050 client builds on that twin rather than on
   a separate vehicle, and fleet management follows with multiple forklifts.
3. **A mermaid flowchart** after the Architecture paragraph, with a one-sentence
   italic annotation under it.
4. **One clause in the Architecture paragraph** — see open question 2.

## The diagram, and how it was checked

`flowchart LR`, six nodes, eight edges, one `subgraph` for the CPU. Browser HMI →
HMI backend → OPC UA → the 1513F-1 PN, holding the standard program
`FB_ForkliftTeleop` and the F-program `F_Forklift_Safety`, → OPC UA → bridge →
ROS 2 topics → the Gazebo forklift; and the return path lidar and joint state →
bridge → PLC → HMI state.

Checked by parsing and rendering the fence with mermaid itself, not by reading it:

| Check | Result |
|---|---|
| `mermaid.parse()` on the block extracted from `README.md` | OK, `diagramType=flowchart-v2` |
| `mermaid.render()` to SVG | OK; 6 nodes, 8 edges, 1 cluster, all six load-bearing labels present in the SVG |
| Version used | mermaid **11.16.0**, under Node 22.14.0 and jsdom |

Qualification, per the standing rule that evidence is qualified by the environment
that produced it: jsdom has no text metrics, so the harness stubbed `getBBox`. That
makes the render a **syntax and layout-execution** check only — the SVG's geometry
is the stub's, not real, and no claim about the rendered size rests on it. "One
screen" rests on the structural facts above, not on measured pixels. GitHub renders
mermaid 11.x, so the version is representative; the harness lives outside the repo
under the session scratchpad and nothing from it was committed.

## Wording discipline

Against `docs/adr/0009-*.md` D5 and `docs/safety/TWIN-DEMO-MAP.md` §5.3:

- The F box reads **"the safety demand forms here"**. No SF number, no Category, no
  PL, no "certified", "validated", "safety-rated" or "SIL" anywhere in the addition.
- The annotation is the ADR 0009 D3 claim in one sentence: the network carries
  process data and read-only safety mirrors only; the demand forms inside the CPU
  and never leaves it.
- The lidar appears only as a device on the plant. Nothing in the diagram names an
  obstacle stop, so the standard-program obstacle latch and the F-side zone demand
  are not merged and share no label (TWIN-DEMO-MAP R4).
- No deadline is mentioned. The existing "No achieved performance level is claimed"
  line is untouched.

## Open questions

1. **`archived` is plain, not bold.** The brief wrote `**archived**` inside a
   plain-text field. In this table bold marks completion — `**done**` ×4, with
   `next`, `planned` and `parked` plain — so bolding `archived` would give the two
   de-emphasised rows the same weight as the finished ones, which is the opposite of
   what archiving means. Rendered plain for that reason. One edit flips it if the
   owner wants the literal.
2. **One clause outside the brief's enumeration, inside its file.** The Architecture
   paragraph said the safety functions are *"specified in `docs/safety/` and
   implemented at M5"*. Archiving the M5 row would have left the public README
   pointing live implementation work at an archived gate — a self-contradiction on
   the page the brief calls the public face. Replaced with ADR 0009 D2.4's own
   accurate wording: their cell-scope core is being built early on the forklift twin,
   linked to ADR 0009. This is a consequence of the archiving, not new scope, and it
   is inside README.md; flagged because the brief enumerated the table, the line and
   the diagram only.
3. **`docs/roadmap.md` and the README now disagree by design.** M5 and M6 are live
   gates in the roadmap and archived rows in the README. That is the owner ruling of
   2026-07-30 recorded outside the repo, and `docs/roadmap.md` was not touched, as
   the brief forbids. It is a standing divergence until the post-demo ADR closes it,
   and it is the one thing here that a verifier will otherwise read as a tracking-file
   inconsistency.

## Not touched

`docs/roadmap.md`, `docs/PLAN.md`, `docs/TODO.md`, any asset, any caption, any
existing link, and every file outside `README.md` and this report. No dependency was
added to the repository.
