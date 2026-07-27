gate:                M3
agent:               interface
goal:                Correct the three known defects in the bridge design document so it agrees with ADR 0005 and with the measured latency evidence.
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md, docs/adr/0005-bridge-layer.md, bridge/EVIDENCE_LATENCY.md, fleet/README.md, bridge/README.md]
deliverable:         docs/interfaces/bridge-design.md (corrected in place)
done_when:           No path in the document names fleet/bridge/; §9.2's L1 is defined as the slot-take hold time; the fleet/README.md exception request is marked resolved by ADR 0005; and no other content has changed.
forbidden:           [rewriting or restructuring sections beyond the three corrections, editing fleet/README.md or any file outside docs/interfaces/, adding new design decisions, changing any measured number, writing code]

## The three corrections, precisely

### 1. Stale component paths

The bridge was originally designed to live at `fleet/bridge/`. ADR 0005 moved
it to a top-level `bridge/` because `fleet/README.md` forbids ROS 2 access —
correctly, for the fleet manager — so hosting the bridge there would have
required writing an exception into another layer's boundary statement.

The document still says `fleet/bridge/` in **§1, §9.4, §10 and §12** (verify
this list; correct every occurrence you find, including any not listed).
Replace with `bridge/`. Check prose, tables, code fences and diagrams alike.

### 2. §9.2, the L1 definition

L1 is currently defined incorrectly. The correct definition is **the slot-take
hold time**. Amend the definition so it matches what
`bridge/EVIDENCE_LATENCY.md` actually measured.

Read the evidence document before writing the amended definition — the wording
must describe the quantity that was measured, not a plausible-sounding
restatement. **Do not change any measured number.** If you find that the
evidence document and the corrected definition still disagree, stop, leave
§9.2 untouched, and report it as a blocking open question rather than
inventing a reconciliation.

### 3. The fleet/README exception request

The document contains a request for an exception to be written into
`fleet/README.md`. That request is obsolete: ADR 0005 resolved it by making
`bridge/` its own layer, so no exception is needed. Mark it resolved by
ADR 0005 in place. **Do not edit `fleet/README.md`** — it is outside your
write access, and per LESSONS the correct move is to request it in your report
if you believe it still needs a change.

## Discipline

LESSONS, 2026-07-26: *when a revision resolves another document's request,
update the requesting document in the same commit*. Applied here that means:
if correcting this document leaves any other document contradicting it, name
that document and the contradiction in your report. Do not fix it yourself and
do not leave it unmentioned.

Keep the diff minimal and reviewable. This is a correction brief, not a
revision brief. A large diff is a failed deliverable.

## Reporting

Write `docs/reports/m3-03c-bridge-design-corrections.md` in the CLAUDE.md
report shape. End with a `lessons_candidates` section (may be "none") in the
`date | what was attempted | what went wrong | the rule now` format. Do not
edit `docs/LESSONS.md` yourself.
