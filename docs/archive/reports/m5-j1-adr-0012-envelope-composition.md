# Report m5-j1 — ADR 0012: envelope composition, and the D1 disclosures

```
brief:               docs/briefs/m5-j1-adr-0012-envelope-composition.md
status:              done
files_changed:       [docs/adr/0012-envelope-composition.md (new),
                      docs/roadmap.md (two sentences added),
                      docs/PLAN.md (two sentences added),
                      docs/reports/m5-j1-adr-0012-envelope-composition.md]
invariants_touched:  none. ADR 0012 changes no invariant; it exists to keep
                     invariants 5 and 10 intact by removing from the PLC a datum
                     the fleet manager owns at M6. Invariants 4, 6 and 9 are
                     named in the ADR as unaffected, not amended
open_questions:      five, below
next_suggested:      carry the D1 ruling into the m5-17 brief (the envelope's
                     third node is a station permit and may not be named for a
                     zone) and into m5-16's formation logic, before either is
                     written
```

## What was written

`docs/adr/0012-envelope-composition.md`, accepted 2026-07-31, in the CLAUDE.md §8
format (Status, Context, Decision, Consequences, Alternatives) and the ADR 0011 /
0008 house style.

**It refines ADR 0011 D3; it supersedes nothing.** The preamble states this before
anything else and names the replaced clause exactly: in D3's opening paragraph the
envelope reads *"a motion enable, a speed ceiling and a zone permit"*, and the
words **"and a zone permit"** — that term and nothing else — are replaced. The ADR
also lists, item by item, what is *not* replaced: the enable, the ceiling, the
onboard closure of the loop, D3's rationale against PLC-in-the-loop velocity, the
mode-scoped M4 phrasing (M4 stays closed and unchanged), and the velocity-smoother
consequence. It further records that D3's *"supervision at order and zone level"*
rationale sentence is **not** a second replaced clause — zone-level supervision
leaves the PLC, not the system, and becomes the fleet manager's at M6.

**D1** rules the third element as a **fixed-equipment / station permit** (door
open, conveyor ready, charging bay clear, station handshake satisfied), with the
M6 consequence recorded as ruling text: a vehicle's motion is bounded by **both** a
PLC station permit **and** a fleet-manager zone reservation — different data,
different owners, tabulated by the question each answers (*is my equipment ready
for you?* versus *may you be here?*) — and no document, node name, message field
or caption may conflate them. The node name itself stays `opcua-nodes.md`'s under
invariant 10; the only constraint imposed on m5-17 is negative (the name may not
be a zone name).

**D2** lands the ADR 0011 D1 disclosures: the artifact sentence in both tracking
files (D2.1); the shared-execution-substrate consequence stated as a consequence
and not a claim, with B4 explicitly **not** weakened — it stands as the roadmap
words it, and the M7 brief inherits a disclosure it must speak when the run is
narrated (D2.2); and **F13** and **F14** recorded **UNVERIFIED** in ADR 0011's F4
pattern, continuing its numbering, each with what would settle it — F13 the
F-runtime-groups-per-F-CPU bound (SIMATIC Safety manual edition plus the
6ES7 513-1FM03-0AB0 technical data, read back in TIA per ADR 0006), F14 the PLCSIM
Advanced instance budget (the manual edition this project actually runs, plus the
licence read back in the tool). D1's *"It scales"* is quoted with both unknowns
until they are pinned; the ADR names M6's existing deep-research entry condition
as the place to settle them and changes no criterion to say so.

Four rejected alternatives are recorded — the brief's three (leave "zone permit"
and separate owners at M6; drop the third element; edit ADR 0011 in place) plus the
collision's other branch named in the review (let the fleet manager write the PLC's
zone permit, rejected against invariant 4's direction of authority) — and a fifth
on the evidence discipline (record "it scales" as settled and pin F13/F14 later).

The ADR makes **no PL, Category, SIL or PFH claim**, states ADR 0011 D5 as
untouched and binding, and explicitly leaves the F-I/O / criterion-(a) question
(the review's finding 1) **open pending m5-03**, whose §7 verdict is still empty.

## Exact sentences added to the tracking files

**`docs/roadmap.md`** — appended to the ADR 0011 paragraph (after *"…for as long
as the project is hardware-free."*):

> The single 1513F-1 PN hosting that onboard safety controller is a **simulation
> artifact**, disclosed as one wherever the twin is described and never an
> architectural claim that one F-CPU guards a fleet: one simulated CPU carries what
> the architecture calls per-vehicle safety, so the cell and vehicle chains share an
> execution substrate in simulation — the M7 statement B4 holds architecturally but
> not at that execution layer (ADR 0011 D1, ADR 0012 D2).

and, as a new one-sentence paragraph immediately after it:

> ADR 0012 (docs/adr/0012-envelope-composition.md, accepted 2026-07-31) refines
> ADR 0011 D3 in one clause and supersedes nothing: the envelope's third element is
> a **fixed-equipment / station permit** — the PLC's statement that the equipment it
> owns is ready for the vehicle to act on it — and not a zone permit, because zone
> reservation belongs to the fleet manager under invariant 5 and one datum has one
> owner under invariant 10.

**`docs/PLAN.md`** — appended to the "Architecture settled with the owner
2026-07-31" paragraph (after *"…never an achieved PL, SIL or PFH."*):

> The single 1513F-1 PN hosting that onboard safety controller is a **simulation
> artifact**, never a claim that one F-CPU guards a fleet, and because one simulated
> CPU carries what the architecture calls per-vehicle safety the cell and vehicle
> chains share an execution substrate in simulation (ADR 0011 D1, ADR 0012 D2).
> Refined 2026-07-31 by ADR 0012 D1: the envelope's third element is a
> **fixed-equipment / station permit**, not a zone permit, since zone reservation is
> the fleet manager's under invariant 5 and one datum has one owner under
> invariant 10.

Nothing else in either file was touched. The second sentence in each is not part
of the brief's `done_when` list but is the minimum needed to stop PLAN:22 and
roadmap:43 — both of which say "zone permit" in their own words — from
contradicting an accepted ADR the moment ADR 0012 lands.

Nothing was committed; both files and the two new files are left modified /
untracked for the orchestrator. `git config user.name` reads **Ozkan Ceylan**
(`user.email` ozkannceylan@gmail.com), verified before writing.

## Open questions

1. **The ruling date versus the review date.** The brief and the `done_when`
   require status *accepted 2026-07-31*, and the ADR carries that date. The review
   the rulings were taken on states it was *commissioned 2026-07-31*
   (`docs/reports/m5-judge-architecture-review.md:5`) against tree `b8713ff`. The
   ADR is written as approved on 2026-07-31 as instructed; if the owner in fact
   ruled on 2026-07-31, the status line and the two roadmap/PLAN sentences are the
   three places to correct, and this is worth settling before the verifier reads
   the dates against each other.
2. **`docs/TODO.md` items I cannot create** (outside write scope, and forbidden by
   the brief). Three are needed: (a) m5-17 — the envelope's third node is a station
   permit and may not be named for a zone; (b) m5-16 — the station permit's
   granularity and formation logic are undecided and must be ruled at that brief;
   (c) the M6 deep-research entry brief must answer F13 and F14 before D1's
   *"it scales"* is quoted as settled.
3. **The review's finding 4(b) and 4(c) are unruled and remain open.** The
   enforcement-locus wording (*the PLC owns the envelope; the vehicle's gate node
   enforces it; the F-layer's SLS backstops the ceiling*) and the public
   `README.md` motion-setpoint sentences are named in ADR 0012 as *not decided
   here*. They need their own owner ruling and their own brief; `README.md` is
   outside every current agent's write scope.
4. **`docs/interfaces/opcua-nodes.md` has not been swept** for the retired term.
   The whitespace-normalised search I ran found "zone permit" only in ADR 0011, the
   roadmap, PLAN, the m5-01 brief and report and the judge report — the last three
   being historical records that correctly state what was decided in their round
   and should not be edited. No interface document yet uses the term, which is why
   the fix is cheap today; that stops being true the moment m5-17 runs.
5. **F13/F14 are recorded, not researched.** No vendor document was opened for
   either (the brief forbids nothing here, but pinning them is a research task with
   its own brief, and the ADR would rather carry two honest absences than two
   unpinned assertions).
