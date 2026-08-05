# m5-36 — the stand-in writer: design

    brief:               docs/briefs/m5-36-standin-writer-design.md
    status:              done
    files_changed:
      - bridge/STANDIN-WRITER-DESIGN.md            (new — the deliverable)
      - bridge/README.md                           (boundary statement rewritten for two processes)
      - docs/interfaces/bridge-design.md           (scope note only; see open question 2)
      - docs/reports/m5-36-standin-writer-design.md
    invariants_touched:  none
    open_questions:      see below
    next_suggested:      dispatch the coding brief against STANDIN-WRITER-DESIGN.md tonight; its §8 acceptance list is the done_when

---

## What the design settles

- **Realisation**: one Windows PowerShell 5.1 script,
  `bridge/standin_writer/standin_writer.ps1`, built from the proven m5-03b /
  m5-25 kernel (Add-Type on the API 7.0 DLL, writes by tag name). No new
  dependency. `-Instance` is mandatory and tool-derived — the probe's
  `FIOPROBE` is not the working project's instance; the working project read
  back `safecell3` on 2026-08-05 (m5-25 log).
- **Heartbeat first**: single-threaded, one 50 ms deadline-scheduled loop;
  console read per-key non-blocking (never `ReadLine`, which would stall the
  loop mid-command and latch the demands); heartbeat `WriteInt16`, +1 per
  successful write cycle, wrap 30000→0; all four members republished every
  cycle. Acceptance check 4 observes that typing cannot starve the heartbeat.
- **The absent field evaluation is not a special mode**: SPEC §7.2 already
  binds the zone channel to the operator console while no field link is up.
  The writer never waits for or requires the link; the zone boots FALSE
  (open, the wire-NC fail-safe direction) and the operator gets the cell
  moving with exactly T6.0.2–T6.0.4. The 45015 listener is still built
  tonight; the `ZONE` digit is fixed as the circuit level (1 = clear/closed).
- **Failure realisation**: API failure → no writes, no heartbeat advance
  (indistinguishable from death at the CPU, the safe direction), 1 Hz logged
  reconnect; CPU STOP/RUN handled entirely by the level republish; double
  start refused by a named mutex before any API contact; deliberate exit
  writes the terminal values (all channels open) before falling silent.
- **Layer boundary written out**: bridge/README.md now states the two
  processes, scopes the never-listens rule to the translator, and carries the
  writer's own must-not-access block (four-tag allowlist, no OPC UA, no
  process decision, no safety claim); bridge-design.md carries a scope note
  that every statement in it binds the translator alone.

## Open questions

1. **SPEC §10 open item 8 can now close** — the writer's home is ruled
   (bridge/) and designed. That is a `plc/` edit and the owner is working
   there; requested, not made.
2. **bridge-design.md lives in `docs/interfaces/`**, the interface agent's
   scope, not this agent's. The brief explicitly granted it ("they are
   yours"), so the scope note was written; flagged for the verifier so the
   grant is on record rather than looking like drift.
3. **The `ZONE 0/1` encoding is fixed by this design** (digit = circuit
   level), consistent with FIELD-EVALUATION §8 rule 1. The m5-12 build brief
   must adopt it — an `agv/` obligation, requested here.
4. **`bridge/.gitignore` needs one line** (`standin_writer/logs/`) — inside
   this layer, specified in the design, to land with tonight's code.
