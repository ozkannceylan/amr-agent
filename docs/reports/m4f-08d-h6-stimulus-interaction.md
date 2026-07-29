# Report m4f-08d — the scenario doc learns H6

```
brief:               docs/briefs/m4f-08d-h6-stimulus-interaction.md
status:              done
files_changed:       sim/scenarios/forklift_commissioning.md  (six hunks;
                                                               git diff
                                                               --numstat 48 14)
                     docs/reports/m4f-08d-h6-stimulus-interaction.md (this file)
invariants_touched:  none
open_questions:      none
next_suggested:      nothing blocking; four of the five rehearsal findings are
                     now closed against their commits and the fifth is the
                     owner's own queued step.
```

## What changed

Six hunks in three places. `git diff --numstat` reads **`48 14`**; the net
growth is the new §9 note. **No figure and no rehearsal transcript line was
added, removed or altered** — verified by diffing for transcript-shaped lines
and finding none on either side.

**§6, the held-reset block** (was "The held reset, and why a browser click
cannot produce it"). Now titled "The held reset, produced from the page" and
instructs the operator to **press and hold the page's RESET button**:
`HmiResetRequest` `TRUE` in every write cycle while the button is down, `FALSE`
from the cycle after release, keyboard down/up accepted, and a tap shorter than
one write cycle still landing exactly one `TRUE` cycle — so 5.1.3's single reset
is unaffected. The Group 1 confirmation and the §11 rule 3 "not run" fallback
are kept. The helper is presented as the terminal equivalent and as what T5.5.5
still needs, because that step's reset must stand before the page exists.

**§9, the `hold` row.** No longer "the only way to produce the held reset of
5.4.4". It now says T5.4's held reset comes from the page's own press-and-hold
RESET, and that `hold` remains the only route for T5.5.5.

**§11, finding 3.** **Closed by `7675960`**, naming what shipped and the
consequence that matters — T5.4 now runs entirely from the operator's screen —
and pointing at §9 for the liveness interaction the same commit introduced.

## The new interaction note

New subsection in §9, where the stimulus tool is introduced, because that is
where an operator meets it. It records H6 as shipped: every request the page
makes on the loopback endpoint refreshes one timestamp, and after
`UI_POLL_STALE_TIME` — 1.0 s, five poll periods — the backend returns all five
requests to rest while the write cycle and the heartbeat keep running, nothing
latches and nothing is demanded of the operator. It is named as a degraded mode
the PLC owns, not a safety reaction. Three consequences are stated:

- **`hold` is safe by construction** — it re-posts continuously, so the beacon
  never goes stale while it runs, and nothing about the subcommands changes.
- **A step that posts once and then waits longer than a second loses its
  requests**, exactly as if the operator had let go — which from the page's
  point of view is what happened. Hold for the duration of a step instead.
- **Recovery is a release, not a resume** — the three Reals are carried on the
  next post, but each Bool only once the poster has been seen to send *that*
  Bool low, so an enable or a reset re-asserted after a gap needs one `false`
  post before the one that asserts it. `watch` also refreshes the beacon, so a
  `watch` running alongside keeps the page alive when nothing is held.

## The transcript line, and why it was not edited

The m4f-07b report lists line 507 among the five. It is inside a fenced
REHEARSAL EVIDENCE block — `24.866 ok HmiResetRequest reads TRUE and stays TRUE
(held by re-posting above the HMI write rate)` — and it is what the harness
printed. This brief forbids rehearsal-transcript changes and the line is not
wrong: that run genuinely used the helper, because it predates `7675960`.
Editing printed evidence to match a later build is the one thing an evidence
block must never do. Handled instead by one sentence in §6 recording that the
rehearsal predates the holdable button, so its transcript names the helper, and
that both routes present the same level to the program — the difference is only
which process re-posts it.

## The sweep

Subject sweep over `reset` and `stimulus`, every hit read rather than counted.
**No surviving statement asserts the momentary-only reset.** Two step-table
lines still say "click RESET once" (5.1.3) and "click it again" (5.4.8): both
are correct and were deliberately left, because those steps want a momentary
press and a tap still lands exactly one `TRUE` cycle. 5.4.4 already read "assert
RESET and hold it", which is route-agnostic and needed no change.

T5.5.5's block in §7 was re-read against H6 and needs no edit: the helper posts
at 50 Hz continuously, so the beacon never goes stale, and the m4f-07b report
states directly that the step is unaffected as long as the first post lands
within one window of HMI start, which is what the helper already does.

## Scope notes

- Nothing outside the scenario doc and this report was written. `7675960`'s
  commit message and `docs/reports/m4f-07b-h6-and-holdable-reset.md` were read
  for what shipped; `hmi/` was not opened for editing.
- The five statements were located by their content, not by the line numbers in
  the m4f-07b report. They happened to match, because that report was written
  after `1ed9b80`; the sweep was still run independently.
- No dependency, no new subcommand and no change to `forklift_stimulus.py`:
  `hold` already satisfies H6 by re-posting, so the tool needed documenting
  rather than changing.
- No commit was made — see the note returned with this report.
