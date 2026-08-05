# Report — m5-29b, the v2a review fixes

    brief:               docs/briefs/m5-29b-hmi-v2a-fixes.md
    status:              done
    files_changed:
      - hmi/static/index.html                 (F1 page half, F4)
      - hmi/hmi_server.py                     (F1 backend half, F2, F4)
      - hmi/tools/capture_v2a_screens.mjs     (second-tab pass, --passes, 10 new checks)
      - hmi/README.md                         (one paragraph: who holds the standing controls)
      - hmi/EVIDENCE_HMI.md                   (§I.1, §I.3, §I.5 re-counted; new §I.7, §I.8)
      - hmi/evidence/capture-v2a-2026-08-05-run3.log                     (new)
      - hmi/evidence/capture-v2a-2026-08-05-f1-defect-before-fix.log     (new)
      - hmi/evidence/f2-connect-failure-2026-08-05.log                   (new)
      - hmi/evidence/hmi-cycles-2026-08-05-secondtab-20260805T115515Z-pid12676.csv (new, BEFORE the fix)
      - hmi/evidence/hmi-cycles-2026-08-05-secondtab-20260805T120629Z-pid656.csv   (new, AFTER)
      - hmi/evidence/screenshots/  26 images + MANIFEST-2026-08-05.txt, all re-captured (gitignored)
      - docs/reports/m5-29b-hmi-v2a-fixes.md  (this report)
    invariants_touched:  none
    open_questions:      three, below. The design's OQ1/OQ2 stay unanswered.
    next_suggested:      the end-to-end run (m5-23 Part B) can now put a live
                         vehicle behind this screen; F3 is still plc + sim.

Nothing outside `hmi/` and this report was written. `plc/` was **read** (the
TIA build procedure, and `plc/forklift/double/server.py` was run as the §12-less
server that F2's evidence needed) and not modified. Nothing is committed.

## F1 — the blocking one: reproduced, then fixed, then walked again

**The defect was reproduced before it was fixed**, with the same instrument that
now proves it gone. `capture_v2a_screens.mjs` gained `passSecondTab`: it opens a
**real second browser target** on the same backend, has the operator release,
reset and select TELEOP in tab A, opens tab B, has the operator **engage the
stop in A**, then backgrounds B and fires B's own `visibilitychange` and `blur`
handlers into it — the exact path the review named.

Against the superseded page (`capture-v2a-2026-08-05-f1-defect-before-fix.log`),
four checks failed and the DOM quotes read:

```
A after the other tab was backgrounded  pstop.label "PROCESS STOP — ENGAGED"
                                        requests.pstop "false"
CHECK FAIL  F1(c)   cycles=20 stop-flips=20 mode-flips=0
```

The operator's own screen said ENGAGED while the wire said released, and all 20
write cycles that followed carried the release. That is the finding, on this
machine, in a real browser.

Built exactly as the review specified, no design decision left open:

1. `index.html` renders both standing controls from `s.controls` on **every**
   poll. The adoption latch is gone; `seenState` survives only as the "a
   `/state` has been seen" gate for the click handlers.
2. A standing key travels in **one** post — the click's own. `pending` is a
   one-shot consumed by the next post; the 50 ms dirty loop, every deadman post,
   `blur`, `pagehide` and the unload beacon carry no standing key, and a missing
   key already meant UNCHANGED at the backend. The click computes an absolute
   target from the last **rendered** backend value.
3. `hmi_server.py`'s `do_POST` republishes `controls=controls.standing()`
   whenever either key is present, so `/state` cannot serve a stale position
   while the OPC UA session is down.
4. Three new checks, plus five supporting ones, in the new pass.

After the fix the same pass passes all eight: the second tab **follows the
backend** (renders ENGAGED because the backend holds ENGAGED), backgrounding it
moves nothing on the wire, and the backend's own per-cycle CSV shows 23/23
cycles after the background still carrying `HmiProcessStopRequest True` and
`HmiDriveModeRequest 1`. H6 is untouched: the backgrounded page's five deadman
requests still went to rest.

There is **no optimistic local override** — a click's effect appears on the next
200 ms poll, as the review directed. One consequence worth naming: if a click's
post fails, the staged value dies with it and the control visibly does not move,
so the operator presses again. That is deliberate; the alternative is a
background retry re-asserting a standing value, which is the defect itself.

## F2 — the designed connect failure, made legible

`_connect`'s required browses now go through one `_resolve` helper that raises a
`ConnectionError` naming the node, its full path under the resolved browse
prefix, and — when the unresolved folder is one of `Mode/Envelope/Vehicle/
ProcessStop` — that this is the **expected** failure against today's CPU,
pointing at `plc/forklift/TIA-BUILD-PROCEDURE.md`, at `hmi/config.yaml`'s header
and at `config-v2a-double.yaml` as what to run meanwhile. The optional-group
path (`Forklift/Safety/`) is untouched and still degrades gracefully.

Exercised, not asserted: run against `plc/forklift/double/server.py`, a server
carrying §10 and no §12 node — the shape of the commissioned CPU today. The
transcript is `hmi/evidence/f2-connect-failure-2026-08-05.log`. The same string
is `/state`'s `session.reason`, so the page's banner says it too.

## F4 — the three minor departures, closed

- **The two page-invented numbers are gone.** `WRITE_HEALTH_STALE_TIME = 2.0`
  is a named constant beside its citation in `hmi_server.py` and is published as
  `write.stale_after_ms`; the page reads both windows from `/state` and the
  backend-gone render path reuses the **last published** values rather than a
  literal. `grep` for `2000` or `1000` in `index.html` now returns nothing.
- **The §8 selector caption exists**: `#modelink` renders *not reaching the PLC*
  whenever the link is down, with two new checks — present link-down, absent
  link-up — so it can neither vanish nor stick.
- **The chip tone is neutral**, not amber: a new `.chip.neutral` class carries
  SELECTION NOT IN FORCE and VEHICLE ADOPTING (§5.2, "never an alarm").

## Where the design was silent and the build had to choose

Reported here rather than backfilled into `V2A-DESIGN.md`:

1. **A selector position with no backend to read it from.** §8 says the selector
   "renders its position" when the link is down. That covers a down OPC UA
   session — the backend still publishes the position and the page draws it with
   the caption. It does not cover the **backend itself being gone**, where there
   is no published position at all. The build shows **none**, with a caption
   saying so, on the page's own rule that a stale display never keeps its last
   live look. A remembered position is not a position.
2. **A failed click's post.** PS-D says the page changes a control "only on
   operator action" and is silent on a post that does not arrive. The build lets
   it fail visibly rather than retrying, per the reasoning above.
3. **Display lag after a click.** The review directed it; the design does not
   mention it. One poll period, ~200 ms, no local override.

## Evidence

Every image was re-captured, so no row describes a page that no longer exists.
`hmi/evidence/screenshots/` holds 26 images (00–25; 24 and 25 are new) and
`MANIFEST-2026-08-05.txt` written as the run landed. The run log is
`capture-v2a-2026-08-05-run3.log`: **51 checks, 51 passed, 0 failed** as the log
prints them (41 from m5-28, 8 from the second-tab pass, 2 on the §8 caption).
`EVIDENCE_HMI.md` §I.1, §I.3 and §I.5 are updated and §I.7 (the second tab,
before and after) and §I.8 (the connect refusal) are new.

Environment: the **Windows showcase machine**, Python 3.13.2 / `asyncua` 2.0.1,
`Chrome/151.0.7922.75` headless over CDP, against `v2a_scenario_double.py` on
loopback. **No PLC was contacted**; nothing here closes a gate criterion.

## Open questions

1. `hmi/V2A-DESIGN.md` PS-D now understates what the build does — the page holds
   no copy at all, rather than adopting one on load. The design is the interface
   agent's/owner's to revise, not mine; flagged rather than edited.
2. The three silences above may be worth writing into the design when it is next
   revised.
3. F3 is untouched and still unowned in `hmi/`: `config-logic-double.yaml`,
   `config-double.yaml` and `config-safety-mirror-double.yaml` still refuse to
   start, and the four `hmi/tools/` M4 harnesses with them, until
   `plc/forklift/double/` gains §14+§12. Third request, unchanged.
