gate:                M3
agate_note:          audit brief; the deliverable is the document confirmed current, not a feature
agent:               interface
goal:                One full pass over the bridge design document against the delivered bridge/ artefacts, so the next reader can trust every section instead of discovering staleness one brief at a time.
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md, bridge/README.md, bridge/requirements.txt, bridge/EVIDENCE_LATENCY.md, bridge/EVIDENCE_SIGNAL_LOSS.md, docs/reports/m3-11-panel-reset-node.md, docs/reports/m3-10-panel-reset-contact.md, docs/LESSONS.md]
deliverable:         docs/interfaces/bridge-design.md, audited and corrected in place
done_when:           Every section has been checked against the delivered artefacts and either corrected or explicitly confirmed current; the report lists both sets section by section; and no measured number differs from the evidence documents.
forbidden:           [changing any measured number, adding design decisions, restructuring sections, editing files outside docs/interfaces/ and the report, re-opening items m3-03c and m3-03d already settled]

## Why an audit rather than another correction

Three consecutive briefs (m3-03c, m3-03d, m3-11) each found this document
describing a pre-delivery state. The document was written before the bridge
existed and has been drifting since. Single corrections are how the fourth
defect reaches the verifier; this brief ends that pattern with one full pass.

## Known-stale going in (verify, do not trust)

1. **§11, asyncua.** Recorded as absent, "NEW — needs owner approval", with a
   bare `pip install asyncua==<pinned version>` path. Reality: approved,
   pinned `asyncua==2.0.1` in `bridge/requirements.txt`, installed into a
   `--system-site-packages` venv (LESSONS #12). On the venv path, note it is
   `/opt/amr-bridge-venv` in the container and `/home/<user>/amr-bridge-venv`
   on WSL where /opt needs root — state the mechanism, not one machine's path.
2. **Reset contact, from m3-11's report:** six inputs become seven in five
   places it names; the signal map needs a `/cell/panel/reset` →
   `DemoCell/Input/PanelResetPressed` row; and the reset's pre-first-publish
   default must be documented FALSE, because a default of true clears a latch
   at startup — the auto-resume CLAUDE.md §9 forbids.

LESSONS' rule applies: enumerated lists are a starting point. Sweep every
section, not just these.

## Method

Section by section. For each: check against the delivered artefact it
describes, then either correct it (minimal diff) or record it as confirmed.
The report's section-by-section list is as much the deliverable as the edits —
"confirmed current" claims with nothing behind them are how this document got
here.

## Reporting

`docs/reports/m3-03e-bridge-design-staleness-sweep.md` in the CLAUDE.md report
shape, then `lessons_candidates` (may be "none"). The report carries the full
section-by-section table: section, verdict (corrected | confirmed), and for
corrections, what changed in one line.
