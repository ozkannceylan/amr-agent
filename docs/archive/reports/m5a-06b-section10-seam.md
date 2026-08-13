# Report m5a-06b — the §10.11 seam and the §11 cross-references

```
brief:               docs/briefs/m5a-06b-section10-seam.md
status:              done
files_changed:       [docs/interfaces/opcua-nodes.md, docs/reports/m5a-06b-section10-seam.md]
invariants_touched:  none
open_questions:
  - §9.6's "SF-01 is unaffected" row still closes with "The demonstration cell has no F-CPU."
    ADR 0009 put one physical/simulated CPU behind the whole DemoCell interface, F-runtime group
    included, so the literal sentence is now imprecise; it likely still holds in the sense it was
    written (the M3 equipment itself carries no F-input and implements no SRS function), but §11.8
    did not name it as a requested cross-reference and it sits outside this brief's section-10
    sweep and its "nothing else changes" bound, so it was left untouched. Worth an owner or
    verifier look.
  - §11.8's own open item 1 (the item this brief answers) still reads as open in the document: it
    names the interface agent's own next brief as owner, and marking it closed would mean editing
    section 11, which this brief forbids. A follow-up brief, or the verifier, can add a closure
    annotation in the style §10.12 and §11.8 already use elsewhere ("Closed by ..., 2026-07-29").
  - The working tree also carries unrelated, in-progress changes from other concurrent agents
    (plc/forklift/SPEC.md modified; four new untracked files under hmi/evidence/). None of that
    belongs to this brief; the pathspec-scoped commit of this work must name only
    docs/interfaces/opcua-nodes.md and this report, never a bare commit.
next_suggested:      A short follow-up brief can mark §11.8 open item 1 closed and re-check §9.6's F-CPU sentence against the shared-CPU fact ADR 0009 records.
```

## What changed, and why

Five edits, all inside `docs/interfaces/opcua-nodes.md`, none inside section 11:

1. **§10.11's row** (the one item this brief was written to fix). Left cell reframed from an
   unqualified "no such node" list — which §11 had already falsified by adding four safety mirrors
   under `DemoCell/Forklift/Safety/` — to "any safety node **other than the read-only mirrors of
   §11**". The right cell keeps the invariant-1 claim ("no node in this subtree is a safety path,
   carries a demand, or can affect one") unchanged as the row's real content, replaces the expired
   premise ("this plant has no F-CPU") with the ADR 0009 fact (a 1513F-1 PN now instantiates SF-01,
   SF-08 and the SF-07 pattern), keeps the still-true half of the old premise (no safety-rated
   device — simulated stand-ins only, ADR 0009 D5), states the exception is bounded to the four
   read-only mirrors, and keeps the unrelated closing sentence about the obstacle stop verbatim in
   substance.
2. **§10.3's folder tree** gains a sixth line, `Safety/`, pointing at §11 and labelled "M5 early" so
   it reads as a later addition rather than part of the M4 delta the tree otherwise describes.
3. **§10.3's "Five new global DBs" paragraph** gains one sentence stating the sixth subfolder is a
   later, separate addition with its own DB (`ForkliftSafetyMirror`, §11.3), so "five" stays true of
   what that paragraph actually delta'd.
4. **§10.3's "18 nodes" paragraph** gains one sentence stating the count is silent about
   `Forklift/Safety/`'s four nodes and restating the 15+18+4=37 total §11.8 already gives, so the two
   sections read as one arithmetic rather than two.
5. **§9.6's "No mirror either" row** (the optional fourth cross-reference §11.8 item 1 names) now
   scopes "the only informational mirror of SF-01" to the fixed cell explicitly and points at the
   twin's separate mirror, `Forklift/Safety/EStopDemand` (§11), on a different machine.

**Subject sweep.** Grepped `safety` (case-insensitive) and `F-CPU` across the whole document, then
read every hit that falls inside section 10 (lines 453–1036) for dependency on the retired premise.
Ten occurrences fall in that range; nine were already independent of "this plant has no F-CPU" (the
§10.1 "not a safety path" row, which disclaims specific SRS numbers ADR 0009 itself re-confirms; the
lidar fail-safe language in §10.5; the §10.8 H6 "process behaviour, not a safety function" line; the
"no safety-rated stop" and "safety-rated on real equipment... does not exist on this plant" lines in
§10.8, both still true post-ADR-0009 since no rated device exists even now) and needed no change; the
tenth was the target row itself. `F-CPU` as a literal string appears in section 10 only at that same
row, confirming no second statement was built on its absence.

**Section 11 was not touched.** No ruling, node row or open-item annotation in §11 was edited,
per the brief's forbidden list — including §11.8's own open item 1, which this work answers but
which still names the interface agent's *next* brief as its owner; closing it was left to that
follow-up rather than self-certified here.
