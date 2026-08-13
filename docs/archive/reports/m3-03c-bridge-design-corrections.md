# m3-03c — bridge design corrections

brief:               docs/briefs/m3-03c-bridge-design-corrections.md
status:              done
files_changed:       [docs/interfaces/bridge-design.md, docs/reports/m3-03c-bridge-design-corrections.md]
invariants_touched:  none
open_questions:
  1. §9.4 names the raw evidence file `bridge/evidence/latency-<YYYY-MM-DD>.csv`;
     the delivered file is `bridge/evidence/latency-2026-07-27.csv.gz`. Compression
     of the same artefact, not a different file — left as written because changing
     it is outside this brief's three corrections. Worth folding into whichever
     brief next revises §9.4.
  2. §12 open item 7 ("20 Hz cycle period ... m3-04 measures what is achieved and
     may revise it with evidence") still reads as open. `bridge/EVIDENCE_LATENCY.md`
     §A.4 states the expectation was met (median period 50.003 ms, 0 overruns) and
     that the item "closes without a revision". Pre-existing staleness, not caused
     by these corrections, and outside the three corrections — not touched.
next_suggested:      Confirm m3-03c has landed, then release m3-05 (its §4 gates on this).

---

## What was changed

### 1. Stale component paths — 7 occurrences, all corrected

The brief listed §1, §9.4, §10 and §12. Verified independently with a repo-wide
search; the real list is seven occurrences in six locations, including one the
brief did not name (§11, the install path):

| Location | Before | After |
|---|---|---|
| Header line 4 | specification `fleet/bridge/` (m3-04) is implemented against | `bridge/` |
| §1, "It is not" row | m3-04 places the bridge under `fleet/bridge/` | its own top-level layer `bridge/` (ADR 0005) |
| §9.4, evidence table | `fleet/bridge/EVIDENCE_LATENCY.md` | `bridge/EVIDENCE_LATENCY.md` |
| §9.4, evidence table | `fleet/bridge/evidence/latency-<YYYY-MM-DD>.csv` | `bridge/evidence/...` |
| §10, "Location" row | `fleet/bridge/` (m3-04's scope) | `bridge/` |
| §11, install path | requirements file under `fleet/bridge/` | under `bridge/` |
| §12, open item 1 | two mentions | rewritten, see correction 3 |

The §1 row needed one clause reworded, not only the path: it read "the two are
separate processes ... **even though** m3-04 places the bridge under
`fleet/bridge/`". The concessive "even though" existed only because of the
provisional location. With `bridge/` a top-level layer the tension is gone, so
the clause is now "and m3-04 places the bridge in its own top-level layer
`bridge/` (ADR 0005; see §12, open item 1)". No other wording on that line moved.

Zero occurrences of `fleet/bridge/` remain in the document.

### 2. §9.2, the L1 definition

The End column changed from "start of the cycle that writes it" to
**"the cycle takes that sample out of its slot"**, and the What-it-contains
column now opens with "Slot hold time" and carries a one-sentence justification:
callbacks run on their own thread, so a sample can arrive after the cycle start
and still be the one written, which would make a cycle-start-referenced interval
negative.

Evidence backing, `bridge/EVIDENCE_LATENCY.md` §A.5, "A measurement-definition
correction (reported, not silently applied)": the measured `L1` "ends when the
cycle takes the sample out of its slot — the true hold time, never negative",
while `L1cs` (raw CSV only) implements the literal old §9.2 wording and "is
negative for 30–50 % of belt samples". That section explicitly states that §9.2
should be amended to the slot-take wording and that the amendment is this
document's to make. The amended definition therefore describes the quantity the
§A.4 table reports.

No measured number was read into the document, altered, or restated. §9.2's
"Expected ~uniform 0–50 ms" is a pre-measurement expectation, not a measurement,
and was left untouched. L2, L3 and the `L3 = L1 + L2` identity are unaffected:
L2 starts at the write, which follows the slot take in the same cycle, and §A.5
confirms L3 was measured end to end rather than by adding statistics.

No disagreement remained between the corrected definition and the evidence
document, so §9.2 was amended rather than reported as blocked.

### 3. The `fleet/README.md` exception request

§12 open item 1 asked for a one-line exception in `fleet/README.md`. It is now
marked **Resolved by ADR 0005**: the bridge is its own top-level layer, not part
of `fleet/`, so no exception is needed and the earlier request is withdrawn.
The item text was reworded from an assertion ("m3-04 places the bridge under
`fleet/bridge/`") to the question it actually was, so that the Status column can
resolve it.

`fleet/README.md` was **not** edited and needs no edit. ADR 0005's Consequences
section is explicit that it "stays absolute. No exception line is added". Its
current content was read and confirmed consistent: line 6's ban on ROS 2
internals is unqualified, which is now correct rather than a conflict.

## Contradictions with other documents

None introduced, and none found outstanding after the change:

- `fleet/README.md` — consistent, and correctly requires no change (above).
- `docs/adr/0005-bridge-layer-and-opcua-client.md` — its Consequences list of
  paths to correct is now fully satisfied by this document.
- `docs/briefs/m3-05-plc-program-spec.md` §4 — already says the component
  directory is `bridge/`, never `fleet/bridge/`. No conflict.
- `bridge/README.md` and `bridge/EVIDENCE_LATENCY.md` — already use `bridge/`
  paths and the slot-take L1. They agree with the corrected document.
- Remaining repo-wide `fleet/bridge/` strings are in `docs/LESSONS.md`,
  `docs/adr/0005`, `docs/briefs/m3-03c`, `docs/reports/m3-03`, `m3-03b`, `m3-04`
  — all historical records of the provisional location or of its rejection.
  Correcting those would be falsifying a record, so they are deliberately left.

## Discipline

Diff is 8 changed lines in one file. No section was restructured, no design
decision added, no measured number touched, no file outside
`docs/interfaces/` and `docs/reports/` written, and nothing committed.

---

lessons_candidates:

none
