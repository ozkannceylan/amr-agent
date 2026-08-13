# Report — m5-27 HMI v2a design

    brief:               docs/briefs/m5-27-hmi-v2a-design.md
    status:              done
    files_changed:
      - hmi/V2A-DESIGN.md            (new — the design document)
      - docs/reports/m5-27-hmi-v2a-design.md
    invariants_touched:  none. The §2 ambiguity is resolved WITHIN invariant 1:
                         ADR 0010 D6(b) is satisfiable without weakening it,
                         and the design says so explicitly (V2A-DESIGN §1).
    open_questions:      see below
    next_suggested:      m5-28 (the build) can start against the hmi-owned
                         scenario double immediately; the plc double extension
                         request below should be briefed in parallel.

## The ambiguity, resolved

The emergency button is designed as ADR 0010 D6(b) reads it and nothing more:
a **process-stop request** (`HmiProcessStopRequest`) plus a **read-only
display** of the four `Forklift/Safety/` mirrors. The design makes the
distinction unmissable by construction (V2A-DESIGN §4): label "PROCESS STOP",
rectangular, amber — never round, never red-on-yellow, never the words
emergency/e-stop; red is reserved for the two F-demand lamps, the only things
on the page named e-stop (§11.2's ruling). A permanent caption states the
network path and the honest limitation, and the control renders UNAVAILABLE
(never armed-looking) whenever the session is down or `HmiLinkOk` is
FALSE/stale, with the invariant-2 sentence that the PLC's watchdog has already
stopped the machine.

## Node check against §12 — nothing invented

Writes (8, all existing): the five §10.4 requests, `Link/HmiHeartbeat`,
`Mode/HmiDriveModeRequest`, `ProcessStop/HmiProcessStopRequest` — exactly the
§12.1 "every-cycle write set becomes eight". Reads (all existing): §10.5/10.6
(diagnostics drawer), §10.7 all four, `Link/HmiLinkOk`, §11.2 all four
mirrors, and §12's `ForkliftDriveModeActive`, three `Envelope/` nodes, two
`Vehicle/` nodes, `ForkliftProcessStopActive` — each an admitted HMI read in
§12.2's reader table. **No node the design needs is missing from §12; no
request to the interface agent is required.**

## The adopt window (LESSONS 2026-07-31)

The HMI runs no timer and no verdict over any mode value. The in-flight
renderings — "selection not in force" (request ≠ in force, incl. an
X5-consumed refusal, with the away-and-back re-selection stated as
instruction) and "vehicle adopting" (in force ≠ applied) — are pure per-poll
functions of read values, neutral in tone, never alarms. The only fault
display is the PLC's own `ForkliftResetRequired`. (V2A-DESIGN §5.)

## Cold start

Specified step by step against SPEC §14.9's cold-start signature (V2A-DESIGN
§9): backend boots the stop control ENGAGED and the selector at None
(deliberate — a connecting HMI must not clear a non-permissive boot value);
then release stop → reset (clears latch, energizes nothing) → select mode,
with the F-side preconditions named as outside the HMI. Two further design
decisions recorded: the stop and the mode selector are standing controls
excluded from the H6 deadman rest set (a page loss neither releases an
engaged stop nor commands a mode exit), and the stop needs no per-session
re-arming because it has no dangerous edge.

## Buildable before the CPU has the nodes

V2A-DESIGN §10 specifies the double: the §10 set + the nine §12 nodes with
§12.2 access rights and §12.8 start values + the §14 arbiter/latch/envelope
behaviour + the §11 mirrors (and a run mode without them). The §14 logic
belongs in `plc/forklift/double/` (the SPEC transliteration); interim, an
hmi-owned scripted scenario double on the `safety_mirror_double.py` precedent
keeps the build unblocked without a second §14 implementation in hmi/.

## Requests

1. **plc agent:** extend `plc/forklift/double/` with the §14 delta and the
   §12 address space (arbiter X1–X6, PS1–PS6 coupling, envelope formation,
   per-tag writability incl. the Envelope write refusal). Same
   executable-double step that caught the 2026-07-31 defect, worth doing
   before the owner's TIA session.
2. **interface agent:** none — no §12 gap found.

## Open questions (owner's)

- OQ1: per-cause latch display — the operator sees `ForkliftResetRequired`
  without which of the seven latches stands; exposing more touches §10.11's
  refusal of latch internals and moves node counts.
- OQ2: whether a published vehicle-liveness verdict node is ever wanted for
  display; v2a shows the raw `ForkliftVehicleHeartbeat` counter only and
  derives no verdict from it.

## What v2a does not do

No map/monitoring plane (v2b), no goal command or display (§12.13 item 4
open), no write beyond the eight, nothing toward the F-layer, no HMI-computed
verdict or staleness window over a process value, no second stop control, no
autonomous-only enable (§12.13 item 5 stays as ruled). V2A-DESIGN §11 carries
the full table and the v2b non-foreclosure statement.
