# m3-03d — bridge design residuals

brief:               docs/briefs/m3-03d-bridge-design-residuals.md
status:              done
files_changed:       [docs/interfaces/bridge-design.md, docs/reports/m3-03d-bridge-design-residuals.md]
invariants_touched:  none
open_questions:
  1. §11 ("Dependencies (require owner approval — see the report)") is stale in the
     same family as the two defects this brief closed. It records `asyncua` as
     **absent** and **"NEW — needs owner approval"**, and gives an install path
     "subject to approval: `pip install asyncua==<pinned version>`". The dependency
     has since been approved, pinned and installed: `bridge/requirements.txt` line 8
     is `asyncua==2.0.1` and `bridge/EVIDENCE_LATENCY.md` line 5 records `asyncua`
     2.0.1 in the run environment. LESSONS entry 12 further records that the real
     install path is a venv at `/opt/amr-bridge-venv` created with
     `--system-site-packages`, not the bare `pip install` §11 describes. Reported,
     not fixed — outside this brief's two corrections, exactly as m3-03c handled
     the two below.
next_suggested:      Fold §11's dependency status and install path into whichever brief next revises bridge-design.md.

---

## The two corrections

Diff is **2 changed lines in one file** (`git diff --stat`: 2 insertions, 2
deletions). No section restructured, no neighbouring prose reworded, no measured
number altered, no m3-03c correction revisited.

### 1. §9.4, raw evidence filename — corrected

| | Text |
|---|---|
| Before | `` `bridge/evidence/latency-<YYYY-MM-DD>.csv` `` \| Raw per-event rows behind the table |
| After | `` `bridge/evidence/latency-<YYYY-MM-DD>.csv.gz` `` \| Raw per-event rows behind the table |

Extension only. The date placeholder form was kept, per the brief.

Confirmed against the filesystem rather than against the brief: the only file in
`bridge/evidence/` is `latency-2026-07-27.csv.gz` (1 179 999 bytes). It is also
the artefact `bridge/EVIDENCE_LATENCY.md` line 6 names —
`evidence/latency-2026-07-27.csv.gz`, 76 191 rows. The `.csv` spelling appears
nowhere else in the document; §9.3's "appended to CSV in memory and flushed
periodically" is a format statement, not a filename, and was left alone.

### 2. §12, open item 7 — closed, and §A.4 supports it

**§A.4 does support the closure.** Its final paragraph states, unprompted:

> The 20 Hz expectation of `opcua-nodes.md` §9.2 is met (open item 7 of the
> design closes without a revision): the median period is 50.003 ms and there
> were **0 cycle overruns**.

Both figures are corroborated inside the same section: the `R1 | cycle period`
row of the statistics table gives median **50.003** ms over 3999 intervals, and
the run counters give `cycle_overruns (> 50 ms)` = **0**. The evidence names the
item by number and states the disposition itself, so the closure is the evidence
document's own verdict rather than an inference drawn to satisfy the brief.

| | Status column |
|---|---|
| Before | An expectation from §9.2, not logic. m3-04 measures what is achieved and may revise it **with evidence**; a revision updates §9.2 and this section together |
| After | **Closed** by m3-04's measurement, `bridge/EVIDENCE_LATENCY.md` §A.4: the expectation is met — median cycle period 50.003 ms, 0 cycle overruns — so the item closes without a revision and §9.2 stands unchanged |

The two figures cited match §A.4 character for character. The old text's
conditional ("may revise it with evidence; a revision updates §9.2 and this
section together") is replaced by the outcome that condition resolved to: no
revision, so §9.2 is untouched. The Item column was not changed.

One wording note. The old Status said "an expectation from §9.2" and §A.4 says
"the 20 Hz expectation of `opcua-nodes.md` §9.2". These are the same reference —
this document's §12 cites §9.2 of the node model throughout — so the new text
says "the expectation" and cites the evidence section, avoiding a §9.2 that
could be misread as this document's own §9.2 (Clock rules).

## Contradictions with other documents

None introduced, and none found outstanding:

- `bridge/EVIDENCE_LATENCY.md` — now agreed with on both points; it was the
  source for both.
- `bridge/requirements.txt` — agrees with nothing in the document either way,
  except §11, which is open question 1 above.
- No other document in the repo names the raw evidence file with a `.csv`
  extension.

lessons_candidates:

2026-07-27 | m3-03c reported two staleness defects it was right to leave out of
scope, and they were fixed one brief later | Nothing went wrong — the defects
were carried in a report, not lost, and the follow-up brief closed both with a
2-line diff | An out-of-scope defect found mid-brief is reported in
`open_questions`, never fixed opportunistically; the orchestrator turns the
report entry into the next brief
