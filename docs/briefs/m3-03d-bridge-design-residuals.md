gate:                M3
agent:               interface
goal:                Remove the two residual staleness defects m3-03c found in the bridge design document but correctly left out of its scope.
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md, bridge/EVIDENCE_LATENCY.md, docs/reports/m3-03c-bridge-design-corrections.md]
deliverable:         docs/interfaces/bridge-design.md (corrected in place)
done_when:           §9.4 names the artefact that was actually delivered, §12 open item 7 reflects the measured outcome recorded in EVIDENCE_LATENCY.md §A.4, and no other content has changed.
forbidden:           [rewriting or restructuring sections, changing any measured number, editing files outside docs/interfaces/ and the report, adding design decisions, writing code, re-opening the m3-03c corrections]

## The two corrections

### 1. §9.4, raw evidence filename

§9.4 names the raw evidence file `bridge/evidence/latency-<YYYY-MM-DD>.csv`.
The delivered artefact is `bridge/evidence/latency-2026-07-27.csv.gz` — the
same artefact, compressed. Correct the extension so the document names what
exists. Keep the date placeholder form if that is how the surrounding text
reads; the defect is the extension, not the date.

### 2. §12, open item 7

Open item 7 concerns the 20 Hz cycle period and reads as still open, with
wording to the effect that m3-04 measures what is achieved and may revise it
with evidence. `bridge/EVIDENCE_LATENCY.md` §A.4 records the expectation met:
median period 50.003 ms, 0 overruns, and states the item closes without a
revision. Mark it closed, citing the evidence section.

Read §A.4 before writing. **Do not restate or alter any measured figure** — if
you cite a number, it must match the evidence document exactly. If §A.4 does
not in fact support closing the item, leave it open and report that instead;
do not force the closure.

## Discipline

This is a correction brief. Minimal diff. m3-03c's changes are settled and are
not to be revisited. If you find a third defect, report it rather than fixing
it — that is what m3-03c did with these two, and it is why they are being
handled cleanly now.

## Reporting

`docs/reports/m3-03d-bridge-design-residuals.md` in the CLAUDE.md report shape,
then a `lessons_candidates` section (may be "none").
