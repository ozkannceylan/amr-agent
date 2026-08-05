# Report — m5-29 HMI v2a review: can M5 continue, and can M5 finish?

    brief:               docs/briefs/m5-29-hmi-v2a-review.md
    status:              done
    files_changed:
      - docs/reports/m5-29-hmi-v2a-review.md   (this report; nothing else touched)
    invariants_touched:  none
    open_questions:      none beyond the owner's standing OQ1/OQ2 (m5-27)
    next_suggested:      one hmi brief executing fixes F1+F2+F4 below before the
                         end-to-end run; F3 tracked in TODO under plc + sim.

## Verdicts, first

**Q1 — sound enough to build the rest of M5 on? YES, with one blocking fix.**
The backend's shape (OPC UA client + loopback HTTP, allowlist in code, no
verdict over any process value), the node contract (exactly the §12.2 rows,
nothing invented, M2 enforced at config load), and the double arrangement are
sound, and nothing in them makes m5-13, v2b, the bridge extension or the
end-to-end run harder. One defect blocks continuing as-is: **the standing-control
state model lets a second, stale page release an engaged process stop and
command mode transitions** (finding 1). It is a page-side state-model defect,
small to fix, and it must land before the end-to-end run puts a live vehicle
behind this screen.

**Q2 — can M5 be finished with it? YES.** Criterion (e) checked clause by
clause below: two clauses met, one ("real-time map with live obstacles") not
yet attempted — it is v2b, inside M5 by the owner ruling of 2026-08-05 — and
**no clause has been made unreachable** by anything v2a built. The owner's §3
v3 wishes are likewise not foreclosed (last section).

## What was verified, and how (read-only; probes named)

- Read `hmi/hmi_server.py` (all 1483 lines), `hmi/static/index.html` (all),
  `hmi/config.yaml`, `hmi/config-logic-double.yaml` header, `V2A-DESIGN.md`,
  `EVIDENCE_HMI.md` §I, both m5-27/m5-28 reports, roadmap M5 row, m5-23 Part B,
  SPEC §14.4 X-rules, `opcua-nodes.md` §12.8/§12.2/§12.3, ADR 0010 D6(b),
  ADR 0011 D4.
- Re-counted the capture log's checks case-sensitively:
  `hmi/evidence/capture-v2a-2026-08-05-run2.log` carries **exactly 41 `CHECK
  PASS`, 0 `CHECK FAIL`** — the report's "41/41" is the log's, not agent
  arithmetic. (A case-insensitive count reads 42 because the summary line
  "every check passed" matches; the extra is that line, not a 42nd check.)
- Opened screenshots 05 and 07 and read the log's quoted-DOM lines for 05, 06,
  14, 15, 23. No simulator, no PLC, no server was run.
- Swept `hmi/` for attribution phrases: clean.

## Findings, ranked

### 1. BLOCKING — a stale second page can release an engaged process stop

The design's PS-D says: *"On load, the page renders the control from
`GET /state` (engaged/released as the backend holds it) and changes it only on
operator action."* The build does the **load** half and then departs from the
**renders** half: after a one-time adoption (`index.html`,
`if (!adopted && …) { standing.… ; adopted = true; }`), the page renders the
stop and the selector from its **local** `standing` copy forever, never
re-syncing from the backend — and `post()` includes
`body.process_stop = standing.process_stop; body.drive_mode =
standing.drive_mode` in **every** post once adopted, including the 50 ms dirty
loop, every deadman post, and the blur/pagehide/visibilitychange `releaseAll`
posts.

Walked as the brief asked:

- **Reload, one tab: sound.** The fresh page posts before adoption with the
  standing keys omitted (backend treats absent as unchanged), then adopts. The
  boot-ENGAGED and first-FALSE-is-an-operator's-release properties hold. The
  capture evidence (images 00–04, 23; checks 4, 5, 39, 40) is genuine.
- **Second tab / two operators: broken, in both directions.** Tab A and B both
  adopt ENGAGED at load. Operator releases the stop in A and drives. The moment
  B is backgrounded, its `visibilitychange` handler fires `releaseAll(true)` →
  a post carrying `process_stop: true` → a phantom stop engagement and, once
  the PLC latches, a reset nobody owes. The reverse is the serious one:
  operator **engages** the stop in A mid-run; tab B (holding a stale
  `process_stop: false` from before) posts on any blur, joystick touch or
  dirty-loop tick → the backend's standing value flips to `FALSE` → the wire
  now carries a **released** stop. The PLC's latch stands (PS1 — no motion
  resumes), but PS3's live-world term "stop released" is now TRUE without any
  operator having released it, so the next reset clears the latch **while tab
  A still renders PROCESS STOP — ENGAGED** from its own local copy. A standing
  control was released by a browser event, and the operator's screen says
  otherwise. The same mechanism replays for the selector: a stale
  `drive_mode` post is a fresh `#modeSelectRise` at the PLC (SPEC §14.4
  `LastModeRequest`), so a background tab can fire X3 (a mode exit no operator
  made) or X2 — **autonomous motion enabled by a stale tab**, since X2 is the
  affirmative enable.

This is exactly the class the brief said to hunt: something that releases a
standing control which should not be released. It is reachable on the single
loopback machine (two tabs of one browser), needs no second operator, and the
end-to-end run (m5-23 Part B step 9) is where it would bite. The capture
instrument never opens a second page, so no existing check covers it.

**Fix F1** (one hmi brief, no design decision left open — PS-D as written is
the design; the build diverged from it):

1. `index.html`: render the stop's engaged/released look and the selector's
   `sel` highlight from `s.controls` (the backend's published standing state)
   on **every** poll, not from the local `standing` copy. Delete the one-time
   adoption latch as the source of rendering; keep `adopted` only as "a
   /state response has been seen" gate for the click handlers.
2. `index.html`: send `process_stop` / `drive_mode` **only in the post
   triggered by the click that changed it** (a one-shot: set the key on the
   click's post, never in the periodic dirty-loop, deadman, blur or beacon
   posts). The click computes its absolute target from the last-rendered
   backend value: stop → `!rendered_engaged`; selector → the clicked position.
   With delta-posting, a stale tab's periodic and deadman posts carry no
   standing key and can change nothing.
3. `hmi_server.py`: in `do_POST`, after `set_process_stop` / `set_drive_mode`,
   refresh the published section: `published.update(controls=
   controls.standing())` — today `controls` is only refreshed inside the write
   cycle, so `/state` serves stale standing values whenever the session is
   down, and a page loading in that window adopts them.
4. `capture_v2a_screens.mjs`: add three checks — (a) a second page opened
   mid-scenario renders the backend's current standing values, not §12.8 boot
   values; (b) with two pages open, backgrounding the non-acting one changes
   neither standing value on the wire (read `requests` from `/state`); (c) a
   blur-triggered post carries no standing key (assert via the backend's
   evidence CSV columns `HmiDriveModeRequest`/`HmiProcessStopRequest`
   unchanged across the blur).

Display latency note so the implementer does not reinvent an optimistic-UI
layer: after a click, the rendered state catches up on the next 200 ms poll;
that lag is acceptable and no local override is to be added.

### 2. Non-blocking, fix in the same brief — `config.yaml`'s designed connect failure is illegible at runtime

The header of `hmi/config.yaml` states honestly that the file fails at connect
until the owner's TIA session lands §12. But the runtime symptom is a bare
retry loop: `_connect` resolves `Mode/HmiDriveModeRequest` with
`objects.get_child`, which raises `BadNoMatch` naming **no browse path**, so
the operator sees `connect failed: BadNoMatch … (retry in 1.0 s)` forever and
the page shows RECONNECTING with that reason. To anyone who has not read the
config header — including the owner mid-TIA-session verifying a partial
download — it looks like a defect, the concern brief §2 item 2 names.

**Fix F2:** in `_connect`, wrap each `get_child` so the raised
`ConnectionError` names the node and its full browse path, and when the
unresolved path's folder is one of `Mode/Envelope/Vehicle/ProcessStop`
(§12 groups), append one sentence: *"the commissioned CPU does not carry the
§12 nodes until the owner's TIA session lands them — see the header of
hmi/config.yaml."* String change plus one try/except; no behaviour change.

### 3. Non-blocking for continuing, must be tracked — the broken M4 harness path has a fifth consumer nobody named

m5-28's judgement 1 is correctly reasoned as far as it goes: the eight-node
write set is required, the three M4 configs refuse to start, the four
`hmi/tools/` harnesses cannot run, and the restoration is the
`plc/forklift/double/` §14+§12 extension already requested in m5-27 **and**
m5-28 (twice now, unactioned). What the report and the superseded headers do
**not** name: `sim/scenarios/run_forklift_rehearsal.py` line 90 hardcodes
`HMI_CONFIG = "hmi/config-logic-double.yaml"`, and
`sim/scenarios/forklift_commissioning.md` (lines 59, 95, 576, 718) instructs
both that config and `config.yaml`. The committed procedure for re-running the
M4 T5 scenarios — which M8 criterion (b) requires running byte-identically
against TwinCAT — is dead until the double extension lands and those files are
repointed. Neither is an hmi/ file, so this needs a TODO entry under **plc**
(the double extension, third request) and **sim** (repoint rehearsal launcher
and procedure once it lands), or the breakage vanishes the way LESSONS
2026-07-30 (84) describes. Acceptable as-is for M5's next steps; not
acceptable as a permanent state, and not currently written down anywhere
outside two report bodies.

### 4. Minor — three small departures from the design (brief item 6)

- **The page invents two numbers the design says it must not.** `index.html`
  hardcodes `since_last_good_write_ms < 2000` (the write-health half of
  UNAVAILABLE) and a `stale_after_ms || 1000` fallback in the backend-gone
  render path. V2A-DESIGN §8 and m5-28's judgement 2 both state the backend
  publishes every window so "the page invents no number". Fix: serve both from
  `/state` (`write` section gains `stale_after_ms: 2000`; the catch-path
  fallback reads the last-seen published value), values unchanged, named
  constants beside a citation in `hmi_server.py`.
- **§8's per-selector caption is missing.** The design: on link-down "the mode
  selector renders its position but adds *'not reaching the PLC'*". The build
  shows only the global degraded banner. One caption element.
- **The Changing/Adopting chips use the `warn` (amber) chip class.** §5.2 says
  "neutral colour, never an alarm". Amber-outlined is attention, not alarm,
  and the evidence checks confirm the chip never says fault — cosmetic; fold
  into the same edit or leave, owner's taste.

These are one small brief together with F1/F2; none blocks anything alone.

## Brief §2 items not already covered above

- **Item 3 (standing control)** — finding 1. The boot-ENGAGED decision itself
  is right and evidenced (images 00–01, checks 4–7); the defect is the
  re-assertion of stale copies, not the boot polarity.
- **Item 4 (adopt-window evidence)** — genuine. The log's quoted DOM for image
  05 shows `machineMode "NONE"`, `selected [1]`, `requests.mode "1"` — the
  sample is inside stage 1, not at its edge (350 ms of 1200 ms, the script's
  own annotation printed at capture time); image 06's DOM shows
  `machineMode "TELEOP"`, `vehicleMode "NONE"`, `vehicleDiff true` — inside
  stage 2. Image 07 (opened) shows all three agreeing with the caption
  "Selected, in force and applied agree" — the rendering **clears**, which is
  the half the 2026-07-31 lesson exists for. The two never-resolving shapes
  (13, 14) and the PLC's own declaration (15, `resetreq ASSERTED` in the
  quoted DOM with the chip still neutral) are also in the log.
- **Item 5 (three UNAVAILABLE causes)** — independent in code, not one
  condition in three coats: `pstopAvailable = writeHealthy && !readStale &&
  linkOk === true`, where `writeHealthy` is the backend's session state plus
  its own last-good-write age (catches a hung write the session state alone
  would miss — `_write` carries no timeout inside the cycle, so a hang
  surfaces only through this term), `readStale` is the backend's read-poll
  bookkeeping, and `linkOk` is the PLC's verdict. Evidence drove them
  separately: image 16 (`HmiLinkOk` FALSE, session UP), 18 (session down), 19
  (backend gone), with checks 29–33.
- **A note, not a finding:** the selector stays clickable while UNAVAILABLE
  (the stop deliberately does not). A selection made link-down is carried when
  the link returns — but the PLC latches on link loss (P5) and X1/X2 require
  `#modeEntryAdmitted`, so the queued selection meets a standing latch and is
  consumed as X5, refused. Covered by the PLC by design; no HMI change needed.

## Q2 — criterion (e), word for word

Roadmap M5 row, clause by clause:

| Clause | Status |
|---|---|
| "the HMI, inherited from M4 and visually reduced" | **Met.** v1's every behaviour retained (write set grew by exactly two; raw dump demoted to the drawer, not deleted); reduction is the design's verdict-not-number rule, visible in the screenshots |
| "selects the drive mode (teleop / autonomous)" | **Met in the build**, exercised against the scenario double through both in-flight windows, a refusal and a non-adopting vehicle. Live-CPU demonstration is correctly still ahead (m5-23 Part B step 5's TIA session, then step 9) — pending, not unreachable |
| "shows a real-time map with live obstacles" | **Not yet attempted — correctly.** v2b (m5-13, ADR 0011 D4), inside M5 by owner ruling of 2026-08-05. Not made unreachable: see foreclosure check below |
| "carries an emergency button that issues a process stop and displays F-layer state — never a safety function over the network (invariant 1, ADR 0010 D6(b))" | **Met**, and unusually well: the D6(b) reading is implemented exactly (write of `HmiProcessStopRequest` + the four §11.2 mirrors, nothing more), the control is denied every visual signifier of a real e-stop, red exists only in zone D, the PSU6 limitation caption is verbatim on the page, and UNAVAILABLE rendering makes the invariant-1 honesty visible. Finding 1 dents the request path's integrity, not the clause's reachability |

The clause-level narration duty ("naming which reactions are F-CPU safety
functions and which are process behaviour") belongs to the showcase, and the
page's own fixed texts (zone C's "standard program, process logic" heading,
zone D's mirror banner) already carry the distinction the narrator will speak.

**Nothing in v2a makes any (e) clause — or any other M5 clause — unreachable.**

## Q1 detail — what comes next, against v2a's structure

- **m5-13 monitoring service:** no coupling. v2a reads only the PLC and holds
  no assumption of being the only data source (V2A-DESIGN §11, and the code
  matches: `/state` is additive, the page is one file that ignores unknown
  keys).
- **HMI v2b live map:** the layout genuinely reserves a third column (the CSS
  comment at `index.html` lines 101–105 and the one-column-pair grid are
  real, not aspirational); map data arrives from the monitoring plane, a
  second source beside `/state`, which nothing in the page's polling design
  prevents. One sentence will need restating when v2b lands: the page
  header's "no external request of any kind" was written against CDNs, and a
  local monitoring-plane fetch is not what it forbids — say so in the v2b
  design rather than silently widening it.
- **Bridge extension:** no interaction with hmi/.
- **First end-to-end run:** runs this exact screen against the real chain —
  which is why finding 1 blocks and finding 2 is worth the one-line fix first.

## Brief §3 — does v2a foreclose the owner's v3 wishes?

**No, none of the four.** Joystick-only-in-teleop is a rendering change on a
zone that already greys by mode (the write stream continuing in every mode is
an H1 contract fact, independent of what is shown). An RViz-grade map and live
cameras are new panes fed by the monitoring plane; the grid grows a column,
`/state` stays untouched, and video rides its own stream (MJPEG/WebRTC from
the monitoring service), not the 200 ms JSON poll — the poll was never asked
to carry it. All-vehicle-data-on-one-page is the drawer pattern scaled.
The state model holds no one-panel assumption; the only structural sentence
v3 must revisit is the same "no external request" framing named above, and
that is a documentation edit, not an undo.

## Fix order

| # | Fix | Blocks M5 continuing? | Agent |
|---|---|---|---|
| 1 | F1 — standing-control state model (render from backend, delta-post on click, publish controls from POST, three new capture checks) | **Yes** — lands before the end-to-end run and before v2b builds on this page | hmi |
| 2 | F2 — legible §12 connect failure in `_connect` | No, but same brief, trivially cheap | hmi |
| 3 | F4 — the two page-invented constants, the missing selector caption, (optionally) chip tone | No — same brief | hmi |
| 4 | F3 — plc double §14+§12 extension (third request), then repoint `run_forklift_rehearsal.py` + `forklift_commissioning.md` | No — but enters TODO now under plc and sim, or it is lost | plc, sim |

F1+F2+F4 are one brief, one deliverable (the v2a page/backend correction),
with the capture instrument re-run as its evidence. F3 is two existing
agents' queues and an orchestrator TODO edit, not a new design.
