# Report m4f-07b — H6 liveness and the holdable reset

```
brief:               docs/briefs/m4f-07b-h6-and-holdable-reset.md
status:              done
files_changed:       hmi/hmi_server.py                             (H6, held reset)
                     hmi/static/index.html                         (hold, beacon,
                                                                    drop notice)
                     hmi/tools/check_hmi_h6_and_reset.py           (new harness)
                     hmi/tools/check_hmi_writes.py                 (check E, beacon)
                     hmi/tools/check_hmi_teleop_loop.py            (beacon)
                     hmi/EVIDENCE_HMI.md                           (section E, and
                                                                    A.5, C and D
                                                                    amended)
                     hmi/README.md                                 (H6, the level
                                                                    reset, the
                                                                    timer line)
                     hmi/evidence/harness-2026-07-29-m4f07b-h6reset.log
                     hmi/evidence/harness-2026-07-29-m4f07b-passA.log
                     hmi/evidence/harness-2026-07-29-m4f07b-passB.log
                     hmi/evidence/hmi-2026-07-29-m4f07b-h6reset.log
                     hmi/evidence/hmi-cycles-2026-07-29-m4f07b-h6reset-*.csv
                     docs/reports/m4f-07b-h6-and-holdable-reset.md (this file)
invariants_touched:  none
open_questions:      four, below — one for hmi/ itself, one for docs/interfaces/,
                     one for sim/, one recorded and not owed to anyone
next_suggested:      close `opcua-nodes.md` §10.12 item 8 and refresh
                     `sim/scenarios/forklift_commissioning.md`'s five statements
                     that the reset cannot be held from the page.
```

## What was delivered

**H6, as ruled.** The page's `GET /state` is the liveness beacon: one timestamp
in `PageLiveness`, refreshed by **every** request the page makes on the loopback
endpoint (both request methods, before the path is examined, so a 404 counts).
`UI_POLL_STALE_TIME` is `5.0 * UI_POLL_PERIOD_S` in code beside its derivation —
the multiple is the rule, not the millisecond — and deliberately not a config
key. Once a cycle the write loop measures the age; on expiry it fires the same
deadman as H5's fault path and **nothing else**: five requests to rest, the enable
included, the write cycle and the heartbeat continuing, no latch, nothing demanded
of the operator. Recovery is a release: the three Reals are carried on the page's
next post, each Bool only once that page has been seen to send **that** Bool low.
The transition is logged and rendered in `/state` (`page.state`, `age_ms`,
`drops`, `last_drop_utc`, `teleop_armed`, `reset_armed`), and the page renders it,
returns its own controls to rest when it learns it was dropped, and shows the drop
count afterwards.

**The reset is a level and it is held.** `HmiResetRequest` is now `TRUE` in every
write cycle for as long as the button is down and `FALSE` from the cycle after
release, which is what `opcua-nodes.md` §10.4 and `hmi/README.md` already said it
was. The page's RESET uses the same press-and-hold shape as the fork jog buttons,
with keyboard down/up as well, because a `click` carries no hold. One sticky flag,
cleared by the cycle that carried it, keeps a tap shorter than one write cycle
landing exactly one `TRUE` cycle — an operator press no cycle carried is a press
the PLC never had the chance to refuse. No timer, and nothing waits for a value to
be stable.

**Both demonstrated against `plc/forklift/double/` on 4850**, transcripts quoted
as printed in `hmi/EVIDENCE_HMI.md` section E:
`hmi/tools/check_hmi_h6_and_reset.py`, **34 checks, no failures**. K1 kills the
page's poll with the backend alive — all five requests at rest 1063 ms later
against a 1000 ms window, `hb_value` incrementing straight through the drop in the
per-cycle CSV, `HmiLinkOk` still `TRUE`, `ForkliftResetRequired` still `FALSE` —
then recovers per the release rule, with a page that thaws holding both Bools
asserted and gets neither carried. K2 runs SPEC §11 T5.4 steps 5.4.1–5.4.9 from
the operator's endpoint, both ten-second holds at full length: the reset reads
`TRUE` in 20 of 20 server samples while held, is refused with the zone occupied,
stands unbroken across the zone clearing, never clears while held, and clears only
on the fresh edge after a real release — with teleop still `FALSE` afterwards
because the enable never fell. That closes `m4f-08` finding 3.

## The consequence nobody asked for, and it is the interesting one

**Every instrument that plays the operator must now poll like the operator's
page.** H6's window is over the page's *requests*, so a harness that posts a
control and then reads OPC UA for three seconds is a crashed browser, and is
correctly treated as one. Both existing harnesses gained a `PageBeacon` standing
in for the browser's 5 Hz `GET /state`; without it they would have failed, and
failed *correctly*. Anything outside `hmi/` that drives `/control` — notably
`sim/scenarios/forklift_stimulus.py` — needs the same, or it must expect its
requests to be dropped after one second of silence.

Both existing passes were re-run after the change: pass A **42 checks, no
failures** (was 40; check `E` was re-specified from "momentary" to "a held level,
plus a tap that still lands"), pass B **33 checks, no failures**, unchanged.

## Open questions

1. **The browser pass was not re-run** (`hmi/`). `EVIDENCE_HMI.md` section C
   exercised the *momentary* RESET in a real browser engine; the page's markup and
   handlers have changed since and no browser was drivable from this session. E.4
   demonstrates the whole of T5.4 through the endpoint the page posts to, and the
   new handlers copy the fork buttons' proven shape, but the DOM events themselves
   are unexercised since the change. Recorded in section D as not shown.
2. **`opcua-nodes.md` §10.12 item 8 is now covered** (`docs/interfaces/`). It was
   written as a request against `hmi/` — a timestamp refreshed by every request,
   the constant with its derivation, the existing deadman fired with the cycle and
   heartbeat left running, the two Bools re-armed on being seen low, the
   transition logged and rendered. All five are implemented and evidenced. §10.8's
   prose and item 8 both cite "`EVIDENCE_HMI.md` §D carries it as 'a browser that
   crashes with the joystick held'"; that row now reads as closed and points at
   section E, so the two documents disagree until item 8 is closed.
3. **`sim/scenarios/forklift_commissioning.md` has five statements that go stale
   with this commit** (`sim/`): lines 447, 459, 507, 653 and 720 say the reset can
   be held "only by re-posting to `/control` above the write rate" and that a
   hold-capable control is "open, in flight". Line 720 already names this brief and
   its own closing condition. The `hold` helper is still needed for T5.5.5's
   pre-link-up reset, which the page cannot produce; only the T5.4 claim changes.
   One new interaction belongs in the same edit: **H6 applies to that helper too**.
   `hold` re-posts continuously and is therefore safe by construction, but any
   step that posts once and then waits more than a second will have its requests
   returned to rest, and any Bool it re-asserts after that gap is carried only
   once it has been posted low first. T5.5.5's "write `HmiResetRequest` `TRUE`
   from its very first cycle" is unaffected as long as the first post lands within
   one window of HMI start, which is what the helper already does.
4. **What H6 does not close, stated rather than covered.** The poll proves the
   *page* is alive, not that a person is in front of it: an operator who walks away
   from a live browser leaves the poll ticking, and no timer this layer can run
   would notice. Carried in section D beside the case-D limitation the bridge
   records for its own heartbeat.

## Scope notes

- Nothing outside `hmi/` and this report was written. `plc/forklift/SPEC.md`,
  `plc/forklift/double/`, `docs/interfaces/opcua-nodes.md` and the `m4f-08` report
  were read as contracts; the double was **run** as the test target and not
  edited. H5's two paths are untouched — the fault path zeroes and does not disarm,
  the clean path still writes no farewell value — and both were re-verified by the
  pass A re-run (checks `G`, `I`, `H`).
- **No dependency was added and no node was added.** `asyncua` and the standard
  library, and the six writable nodes are still the six.
- The runs were WSL2 Ubuntu 24.04 on the `/mnt/c` checkout, `~/amr-hmi-venv`,
  Python 3.12.3, `asyncua 2.0.1`, against loopback 4847 and 4850. **PLCSIM was
  never contacted**; all three harnesses refuse a non-loopback endpoint. Every
  process had stopped and no listener remained on 4847/4850/8089/8090 before the
  files were read.
- Nothing implemented here is a safety device. The page going quiet is a degraded
  mode with a controlled stop the PLC owns, never a safety event (invariants 1, 2;
  ADR 0008 D3), and no reaction in this layer is named a safety function.
