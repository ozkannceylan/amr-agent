# Report m5-02 — CLAUDE.md §3 topology gains the monitoring plane

```
brief:               docs/briefs/m5-02-topology-monitoring-plane.md
status:              done
files_changed:       [CLAUDE.md (section 3 only)]
invariants_touched:  none. Invariants 1-13 are byte-identical; the diagram
                     invariant 11 refers to gained one node and two edges,
                     under the authority of ADR 0011 D4 (accepted 2026-07-30).
open_questions:      three, below
next_suggested:      the first monitoring brief rules the service's directory
                     against the ADR 0005 D1 test and shows "no write endpoint,
                     no publisher" as a build property.
```

## What changed

One node and two edges added to the §3 diagram, and the legend rewritten from
one prose line into four bullets, one per link style.

- Node `MON` — "Monitoring service / subscribes to the vehicle ROS 2 graph /
  no write endpoint, no publisher". Deliberately **no directory in the label**:
  ADR 0011 D4 recommends `agv/` but explicitly does not rule it.
- `NAV --o|subscribe: map, pose, obstacles| MON`
- `MON --o|read-only map view, no command| HMI`

Both monitoring edges are one-way, neither touches `PLC`, and no pre-existing
edge, label or node was altered — the HMI to PLC process edge included.

## The third arrow style, and why

**Circle-ended arrow, mermaid `--o`.**

The diagram already spent two of mermaid's obvious styles: `==>` on the safety
path and `-.->` on PROFIsafe. The monitoring plane therefore needed a *fourth*
distinguishable style, not a third.

The deciding property is what mermaid actually emits. Rendering the section 3
diagram and reading the SVG shows that `-->`, `==>` and `-.->` all terminate in
the **same** `pointEnd` marker and differ only in stroke class
(`edge-thickness-thick`, `edge-pattern-dotted`). `--o` is the one form that
changes the **terminator glyph** itself, to `circleEnd`:

```
g1-L_SAFE_NAV_0   marker-end=...-pointEnd    class=edge-thickness-thick
g1-L_FCPU_PLC_0   marker-end=...-pointEnd    class=edge-pattern-dotted
g1-L_HMI_PLC_0    marker-end=...-pointEnd    class=edge-thickness-normal
g1-L_NAV_MON_0    marker-end=...-circleEnd   marker-start=none
g1-L_MON_HMI_0    marker-end=...-circleEnd   marker-start=none
```

So the monitoring plane is the only plane that is distinguishable by shape
rather than by stroke weight or dash pattern. That survives a greyscale print,
a low-resolution screenshot and a slide, which stroke-weight differences do
not — and this diagram exists to be read at a glance in a portfolio review.

Two further reasons. A circle terminator reads as a **tap or probe** rather than
as a delivery, which is exactly the semantics of an edge that carries no
command. And it needs **no `linkStyle` index arithmetic**: an index-based style
statement in the owner's contract file would silently mis-style itself the day
anyone inserts an edge above it, which is the class of silent breakage LESSONS
keeps recording.

`--x` (cross terminator) was the alternative and was rejected on meaning: a
cross reads as a blocked or terminated path, not as an observation.

## Verification

Rendered, not merely parsed, with mermaid **11.16.0** under jsdom, against the
diagram text **extracted programmatically from CLAUDE.md** rather than retyped:

- `mermaid.parse` returns `diagramType: flowchart-v2`.
- `mermaid.render` resolves all **nine** edges, which requires every node id to
  exist.
- `SAFE ==> NAV` still carries `edge-thickness-thick`; `FCPU -.-> PLC` still
  carries `edge-pattern-dotted`; both VDA 5050 edges keep their bidirectional
  `pointStart`. Nothing regressed.
- Both monitoring edges report `marker-start=none`, which is the one-way
  property checked mechanically rather than asserted.

CLAUDE.md is 0 non-ASCII bytes and 0 CRLF. `git status` shows `CLAUDE.md` as the
only path modified by this brief. Nothing committed; the tree is left dirty for
the orchestrator.

## Open questions

1. **`bridge/` is absent from the §3 topology, and this is now more visible.**
   ADR 0005 D1 made the bridge a top-level layer, and ADR 0011 D4's own diagram
   draws the command path as `HMI -> PLC -> BR -> VEH`. Section 3 has no bridge
   node at all: its only PLC-to-vehicle path runs `PLC -> FM -> MQ -> CL`. Since
   invariant 11 is enforced against this diagram, the layer that actually
   carries the M4/M5 command path is currently unenforceable by it. Out of scope
   here (this brief adds the monitoring edge and forbids altering others) — it
   needs its own owner-approved amendment, and arch-docs should say whether the
   ADR 0011 D4 process chain is the intended §3 shape.
2. **ADR 0011 D4's illustrative diagram draws the monitoring edges dotted
   (`-.->`).** That is unambiguous in its own `graph LR` snippet, which has no
   PROFIsafe edge, but it cannot be transplanted into §3 where dotted is already
   the safety fieldbus. §3 therefore uses `--o` while the ADR shows `-.->`. This
   satisfies D4's binding text ("a third style distinct from both the safety
   path and the process path") and no accepted ADR may be edited, so this is
   recorded rather than reconciled. A reader diffing the two will see different
   glyphs for the same plane.
3. **The `MON` node names no directory**, per D4. Every document that gains a
   monitoring reference before the directory is ruled should follow the same
   restraint, or the recommendation will harden into a decision by repetition.
