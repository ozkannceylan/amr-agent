# Report m4r2-01 — ADR 0008, forklift commissioning gate and HMI layer

brief:               docs/briefs/m4r2-01-adr-0008-forklift-gate.md
status:              done
files_changed:       docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md (new), docs/reports/m4r2-01-adr-0008-forklift-gate.md (this file). Nothing else touched — roadmap.md, PLAN.md, TODO.md, CLAUDE.md, ADR 0002 and ADR 0007 are unchanged, per the brief's forbidden list. Committed as one pathspec-scoped commit of exactly these two files, per the brief's Git section, with repo-local `user.name`/`user.email` set to the owner identity read from existing commits.
invariants_touched:  none. Gate order is ADR 0004's and ADR 0007's, not a CLAUDE.md §2 invariant, so inserting a gate is not an invariant change. Invariant 4 is preserved explicitly (the HMI is a client of the PLC server, never the inverse); invariant 2's pattern is applied at the new HMI boundary rather than excepted; invariants 1, 6, 7, 10 and 11 are unaffected in substance. The ADR adds a layer to the CLAUDE.md §3 topology on the ADR 0005 precedent — that is a topology change requiring the owner's edit to CLAUDE.md, not an invariant change, and it is requested rather than made.

## What the ADR decides

Five decisions, all owner-approved 2026-07-28, status accepted with that date.

**D1 — New gate M4, forklift commissioning cell.** A tricycle forklift plant in
Gazebo, teleoperated from a local commissioning HMI, every command travelling
HMI → PLC standard program → bridge → simulation and every state report
returning simulation → bridge → PLC. ADR 0007's M4–M11 shift to M5–M12; Hermes
stays parked and last. ADR 0007 §2's per-SF landing points and §3's three
showcases move with their gates (safety M5, fleet M9, demonstration M10). The
ADR states the shift and explicitly leaves the renumbering mechanics to m4r2-02.

**D2 — Operator/HMI layer, local case.** Seven sub-decisions: the HMI is an OPC
UA *client* of the PLC (invariant 4 restated, not bent); it streams setpoints,
an enable, an edge-triggered reset request and a `UInt16` heartbeat as
*requests*; heartbeat loss zeroes every motion setpoint in a mandatory `ELSE`
(the SPEC §6.4 gating discipline, and the invariant-2 degraded-mode pattern at a
new boundary); the pattern is a continuous setpoint stream and is explicitly
*not* the Hermes-style token handshake of m4-00 §5; per-client write scoping is
recorded as policy rather than enforcement; the HMI is a new top-level `hmi/` on
the ADR 0005 precedent.

D2.7 is the amendment the brief required: ADR 0007's operator-layer prohibition
is amended **only** for the local commissioning HMI — same machine, same cell
network, no remote transport — and continues to hold unchanged for every remote
or assistant-originated path. m4-00 decision 3 is ruled for the local case and
for no other; decision 2 was closed by ADR 0007; decisions 1, 4, 5, 6, 7, 8, 9
and 10 stay unruled and the invariant-8 reading stays open.

**D3 — Teleop logic is process logic.** Teleop routing, fork-height speed cap,
fork soft travel limits and the lidar obstacle stop are process interlocks in a
second FB beside `FB_DemoCellControl`. The non-claims name exact ids: not SF-02,
not SF-03, not SF-04, not SF-07, not SF-09. Invariants 1, 2 and 7 untouched by
construction; no F-CPU is involved and its PLCSIM feasibility remains the open
owner item on the safety gate, now M5.

**D4 — Model sourcing.** Original in-house SDF driven by `gz-sim` built-in
systems, no `ros2_control`, no new dependency. `cangozpi/ROS2-Forklift-Simulation`
and the owner's fork are reference-only, no file may enter the repository. Every
external claim sits in one table headed with the pinned commit
`ba74f767111c6c8a7a907c10d0d962c899a8b1c1` and the verification date 2026-07-28:
license NONE (API field null, no LICENSE in the recursive tree, three
`package.xml` carrying `TODO: License declaration`), differential-with-caster
kinematics rather than tricycle, no robot meshes, Gazebo Classic 11 / Humble
against this project's Harmonic / Jazzy. The fork travel figures are recorded as
citable prior art, being measurements of a published model rather than content.

**D5 — ADR 0002 not superseded.** It rejected a custom reach truck *as the
navigation platform*; this plant carries no navigation claim. The vehicle gate,
M6 after the shift, keeps RB-KAIROS. Plant and vehicle never merge into one
model.

## open_questions

1. **The three tracking files now disagree with this ADR, by design of the brief
   split — and the disagreement is in the live pointer, not only in the table.**
   `docs/roadmap.md` reads "Current gate: M4 — Safety layer on the fixed cell",
   which under ADR 0008 is M5; the table still carries M4 = safety and M11 =
   Hermes, and `docs/PLAN.md` and `docs/TODO.md` carry the same numbering.
   Editing them was forbidden here and belongs to m4r2-02. Until that lands the
   disagreement is real and this ADR is the newer statement — it should not be
   left open across a verifier run, since "never let PLAN, TODO and roadmap
   disagree" is a standing rule and ADR 0007's own renumbering already produced
   one such gap.
2. **CLAUDE.md needs three edits and they are the owner's**, requested here on
   the ADR 0005 precedent: §3's topology gains an operator/HMI box, §4's layout
   gains `hmi/`, §5's roster gains an agent owning it with write access to
   `hmi/`. Until then the locked topology diagram has no box for a layer this
   ADR admits. Also note CLAUDE.md §6's gate table still carries the original
   numbering, as it has since ADR 0004.
3. **The HMI-writable node group is undecided and is the interface agent's.**
   Two findings it must resolve: `docs/interfaces/opcua-nodes.md` §9.8 records a
   client-writable command node as *deliberately absent* — true today and void
   at the new M4 — and if the group lands on a **new** server interface rather
   than `DemoCell`, that interface's *name* is a contract decision because ADR
   0006 derives the namespace URI from it. Both are the same class of item as
   the M6 fleet-facing interface name already carried in TODO.
4. **Two writing clients make the enforcement gap wider.** Per-tag writability
   is CPU-enforced; per-client scoping is not, because the commissioned CPU runs
   with access control disabled and security `None`. Recorded in D2.5, not
   closed. Whoever briefs the HMI should decide whether this gate is where
   access control finally gets configured.
5. **The second FB is a change to a spec that says "one FB, one instance".**
   `plc/demo-cell/SPEC.md` §4.1 chose one FB in OB30 partly to guarantee one
   writer per tag. Two FBs in the same OB keep that guarantee only if it is
   restated across both — the plc agent's item, together with the OB30 budget at
   20 ms.
6. **Where the forklift plant lives in `sim/` is not decided** — a new world, or
   the existing cell world extended. The sim agent's call; the ADR deliberately
   says nothing about it.
7. **The ADR 0007 status line is again not edited**, same resolution as m4r-01:
   CLAUDE.md §8's never-edit rule wins over its `superseded by NNNN` vocabulary,
   and in any case ADR 0007 is not superseded here — only its gate numbers shift
   and one consequence bullet is scoped. The forward pointer lives in ADR 0008's
   status block and belongs in roadmap.md.

next_suggested:      m4r2-02 (arch-docs) — roadmap.md to the M0..M12 order with the new M4 row written from ADR 0008 D1, PLAN.md's current-gate block, and TODO.md reconciled by the orchestrator in the same commit, with the stale gate references re-verified by independent search rather than from ADR 0007's list.
