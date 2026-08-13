# Report — m5-28 build HMI v2a

    brief:               docs/briefs/m5-28-hmi-v2a-build.md
    status:              done
    files_changed:
      - hmi/hmi_server.py                     (modified — the write set becomes eight)
      - hmi/static/index.html                 (rewritten — the v2a operator page)
      - hmi/config.yaml                       (modified — eight writes, the §12 reads)
      - hmi/config-v2a-double.yaml            (new)
      - hmi/config-double.yaml                (modified — superseded-by-v2a header only)
      - hmi/config-logic-double.yaml          (modified — superseded-by-v2a header only)
      - hmi/config-safety-mirror-double.yaml  (modified — superseded-by-v2a header only)
      - hmi/tools/v2a_scenario_double.py      (new — the interim scenario double)
      - hmi/tools/capture_v2a_screens.mjs     (new — the screenshot instrument)
      - hmi/README.md                         (modified)
      - hmi/EVIDENCE_HMI.md                   (modified — new section I)
      - hmi/evidence/capture-v2a-2026-08-05-run2.log (new — the run log)
      - docs/reports/m5-28-hmi-v2a-build.md
      - (hmi/evidence/screenshots/ — 24 PNGs + a manifest, GITIGNORED by owner
         ruling, listed row by row in EVIDENCE_HMI.md §I.3)
    invariants_touched:  none. Invariant 1 is what the design exists to respect
                         and §I.5's checks are how the build proves it did.
    open_questions:      see below
    next_suggested:      owner reviews EVIDENCE_HMI.md §I.3 against the local
                         screenshots; that feedback is the review pass.

## What was built

HMI v2a, to `hmi/V2A-DESIGN.md`. Nothing in the design proved unbuildable and
nothing in it was substituted; the two places where the build had to decide
something the design does not legislate are named under **Judgements** below.

- **Write set eight.** `HMI_WRITABLE_PATHS` grew by exactly
  `Mode/HmiDriveModeRequest` and `ProcessStop/HmiProcessStopRequest` and by
  nothing else. The one write helper is unchanged in mechanism; **no node was
  invented** and every node written or read is a §10/§11/§12 row that already
  existed. All eight are written every cycle, heartbeat last.
- **Two standing controls.** The mode selector and the process stop are
  excluded from the H6 deadman rest set and are not re-armed per page session
  (PS-B, PS-C, §5.1). The stop **boots ENGAGED** to match §12.8 (PS-A), and the
  page **adopts backend state on load** rather than asserting its own defaults
  (PS-D) — the `/control` payload treats those two keys as *unchanged when
  absent*, so a page that has not yet adopted cannot release a stop or command
  a mode exit.
- **The process stop, as ADR 0010 D6(b) reads it.** Amber, rectangular, labelled
  PROCESS STOP; the words *emergency*, *e-stop*, *not-aus* and *protective*
  appear nowhere on or near the control **as a name for it**. They appear
  exactly twice on the page and both are the design's own required text: the
  PSU6 limitation caption, verbatim (*"on real equipment the emergency stop is
  the hardwired device at the machine, never a screen"*), and the zone D lamp
  named `e-stop demand`, which is §7's mirror of the only thing in this cell
  that carries the word. Red is used for the two F-demand lamps and nothing
  else.
- **It never looks armed when its effect could not arrive.** Session down, write
  cycle failing, or `HmiLinkOk` false/stale renders it UNAVAILABLE — hatched,
  greyed, `disabled`, with the invariant-2 sentence. Captured in three separate
  causes (images 16, 18, 19) and asserted by five checks.
- **Zero HMI verdicts about mode.** No timer, no debounce, no latch. Every mode
  rendering is a pure function of one poll's values; the only fault display is
  the PLC's `ForkliftResetRequired`.
- **The interim double.** `hmi/tools/v2a_scenario_double.py` serves §9.7's two
  `DemoCell/Link/` tags, §10's eighteen nodes, §12's nine at their §12.8 start
  values with §12.2's access rights (`Envelope/*` and every PLC verdict refuse a
  client write), and §11's four mirrors optionally. It **replays** §14 as
  straight-line scripts — wait for a value the HMI wrote, sleep a scripted
  delay, assign a recorded answer — and computes no verdict; a refusal is a
  different script, not a branch.

## The adopt window was tested, not asserted

Driven with a **1.2 s adopt delay per stage**, in two stages, and the page was
sampled *inside* both: image 05 at 350 ms of stage 1 ("selection not in force",
machine mode still NONE), image 06 at 400 ms of stage 2 ("vehicle adopting",
TELEOP vs NONE shown side by side). Image 07 proves the rendering **clears**.
Two different never-resolving disagreements were driven — a consumed refusal
(13) and a vehicle that never adopts (14) — and both render neutrally with no
HMI clock; the PLC's own declaration arrives later as `ForkliftResetRequired`
(15). Detail and quoted DOM in `EVIDENCE_HMI.md` §I.4.

## Evidence

24 screenshots, one per state, in `hmi/evidence/screenshots/` (gitignored), each
listed with what it shows in **`hmi/EVIDENCE_HMI.md` §I.3** — the only part of
the capture that travels with the repository. The capture instrument also
**asserts** against the rendered DOM at each step: **41 checks, 41 passed, 0
failed**, tabulated in §I.5. Run log:
`hmi/evidence/capture-v2a-2026-08-05-run2.log`.

The instrument presses the page's own DOM handlers with real input events
dispatched into Chrome, closing the §C residual (handlers passing an endpoint
test while unexercised). It speaks the Chrome DevTools Protocol over Node 22's
built-in WebSocket and **adds no dependency** — Playwright is absent on the
Windows showcase machine and installing it to take a picture was not worth the
environment change.

**No PLC was contacted** and no §12 node on the running CPU was touched: it
carries none. Nothing here closes a gate criterion.

## Judgements the design does not legislate, declared

1. **The eight-node write set is required, not optional**, so the M4-era
   configurations (`config-double.yaml`, `config-logic-double.yaml`,
   `config-safety-mirror-double.yaml`) no longer start: they name six. Rather
   than invent an optional-write mode nobody designed, each carries a header
   saying it is superseded and why, and the four M4 harnesses in `hmi/tools/`
   are **not runnable against the v2a backend** until a double serves §12.
   That is precisely the `plc/forklift/double/` extension the m5-27 report
   already requested; it is not fixable inside `hmi/`. `hmi/config.yaml` was
   updated to the eight and will fail at connect against today's CPU, by
   design, until the owner's TIA session lands §12.
2. **The read-poll staleness window** that flips read-derived states to unknown
   is five read-poll periods, published by the backend so the page invents no
   number. It watches this process's own poll — its own channel — which is the
   class §8 admits; it is not a window over any plant value or PLC verdict.

Also added, as the code side of §12.3 **M2**: a configuration that names either
written §12 node in its *read* table is refused at start, with the M2 sentence
in the error.

## Requests

1. **plc agent (restated from m5-27, now with a second consumer):** extend
   `plc/forklift/double/` with §14 and the §12 address space. It would restore
   the four M4 harnesses under the v2a backend and give divergence a place to
   resolve toward.
2. Nothing from the interface agent — no §12 gap was found in the build either.

## Open questions

- The design's **OQ1** (per-cause latch display) and **OQ2** (a published
  vehicle-liveness verdict) are the owner's and were **not answered**. v2a
  implements the conservative side of both: `ForkliftResetRequired` alone, and
  the raw `ForkliftVehicleHeartbeat` counter in the drawer with no verdict
  derived from it.
- Whether the M4 harnesses should be ported to the v2a write set once a §12
  double exists, or left as the record of the M4 runs. Not decided here.

## Not done, deliberately

No map, no monitoring plane, nothing needing m5-13 (that is v2b); no goal
command or display; no write beyond the eight; nothing toward the F-layer; no
second stop control and no autonomous-only enable; no HMI-computed verdict,
staleness window over a process value, debounce or fault delay.

**Not committed.** The tree is left dirty; the paths are the `files_changed`
list above.
