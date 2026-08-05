# m5-37 — the stand-in writer: build

    brief:               m5-37 (issued in-session; no file in docs/briefs/)
    status:              blocked
    files_changed:
      - bridge/standin_writer/standin_writer.ps1              (new — the deliverable)
      - bridge/standin_writer/EVIDENCE_BUILD.md               (new — build evidence, written as it landed)
      - bridge/standin_writer/testing/observe_consumer.ps1    (new — TEST SCAFFOLDING, read-only consumer's-view observer)
      - bridge/standin_writer/testing/console_feed.ps1        (new — TEST SCAFFOLDING, types into the writer's own console)
      - bridge/standin_writer/testing/field_feed.ps1          (new — TEST SCAFFOLDING, throwaway field-link line feeder)
      - bridge/.gitignore                                     (one line: standin_writer/logs/)
      - docs/reports/m5-37-standin-writer-build.md
    invariants_touched:  none
    open_questions:      see below
    next_suggested:      run §8 checks 2–7 (evidence §3 table) the moment SafetyInputStandIn.StandInHeartbeat exists; nothing else is outstanding

---

## Status: blocked, and on exactly one thing

**The script is built, complete and proven on every path that does not require
`SafetyInputStandIn.StandInHeartbeat`. That tag does not exist yet.** The S015
delta had not landed in `safecell3` when this build ran, and did not land
during ~55 minutes of polling at 15–20 s intervals (`state=Run`, `tags=185`,
unchanged throughout). Nothing about the writer is waiting on anything else:
the moment the delta lands, `powershell -ExecutionPolicy Bypass -File
bridge\standin_writer\standin_writer.ps1 -Instance safecell3` is the whole
start procedure.

The blocked status is honest rather than cautious: **`StandInValid` going TRUE
has not been observed**, because there is no `StandInValid` in this build to
observe. Everything the design offers as the belief chain — heartbeat
advancing, `HeartbeatSeen`, `StandInValid`, a demand clearing through the
monitored reset with the writer driving the channels — is unproven and is
written up as unproven in `bridge/standin_writer/EVIDENCE_BUILD.md` §3, check
by check.

## What is proven, live, against the running CPU

Instance **`safecell3`** — read back from `RegisteredInstanceInfo` and
confirmed by its tag set, **not** the probe's `FIOPROBE` (which is `Off`).
API 7.0, `OperatingState = Run` throughout. Nothing was downloaded, no program
was changed, no project was touched; the writer writes tag values through the
API and reads them back through a separate process.

- **Double start refused** (§8 check 1): exit 3 on the named mutex, no log
  file created, no API contact — the mutex is acquired before `Add-Type`.
- **The API-failure path, unfaked** (§5.1): the missing heartbeat tag threw a
  real `DoesNotExist` on every cycle for 2 min 13 s. The writer logged it,
  disposed, marked disconnected, and retried once per second, each attempt
  logged — and **the heartbeat never advanced past 0** across 122 failures.
  The counter-advances-only-on-a-fully-successful-write-cycle rule is
  therefore observed, not asserted.
- **The operator console** (§4): commands typed into the writer's own console
  input buffer from another process; `estop close`, `status`, and both refusal
  forms (`reset pulse x`, an unrecognised line) accepted and logged while the
  loop kept cycling.
- **The field link, whole** (§3): held FALSE until the first verdict, the
  `ZONE 1` = circuit-closed encoding, a second connection refused, an operator
  `zone` command refused while the link is up, garbage refreshing no clock,
  and the 1000 ms staleness driving the channel **open** and returning
  ownership to the operator. Six design rules in one capture.
- **The terminal write in its failure form** (§5.4): `quit` inside a
  disconnected window reported `TERMINAL | FAILED` and named death-by-
  staleness as the cover, rather than pretending the write happened.
- **Cadence under real API write cost**: 400 cycles, **0 overruns**, three
  writes costing 1.40 ms median of a 50 ms budget. One 20 s draw on one
  machine, stated as a sample and not as a bound.
- **The second witness is live**: the OPC UA witness runs from the WSL venv
  against the CPU's own server and cannot see `SafetyInputStandIn`, so it is
  ready to serve run B as the witness that cannot echo the writer.

Every observation above was made in a **separate process** from the writer.
The writer has no read-back to consult by construction — it reads nothing from
the CPU but `OperatingState`.

## Deviations from the design, both stated rather than hidden

1. **A headless guard on the console.** If `[Console]::KeyAvailable` throws
   (input redirected, or no console at all), the writer disables the console
   for that session, logs a `REFUSED` line naming the consequence — no
   operator command can be entered — and **keeps cycling**. The design assumes
   a console; without the guard a headless start would die on its first
   iteration, which is the one outcome the design forbids. It adds no
   behaviour when a console exists.
2. **`testing/` exists.** The design says one file, no module, no second file
   — that binds the *writer*, and the writer is one file. The three scripts in
   `testing/` are build scaffolding, labelled as such in their own headers,
   and the design itself contemplates a "throwaway `ncat` line-feeder" for the
   field link. They are separable from the deliverable if the verifier would
   rather they were not committed.

## Not done, and why — the two failure paths the brief named that were not run

- **A controller stop and restart repaired by the republish.** Stopping the
  CPU is a change to the machine the owner was working in TIA on, and the
  brief's own instruction is to wait rather than force anything. Deferred with
  the reason, not attempted. The design's §8 acceptance list does not contain
  it either.
- **Checks 2–7**, all of which read `StandInHeartbeat`, `HeartbeatSeen` or
  `StandInValid`. Blocked on the delta.

## Open questions

1. **The delta.** `SafetyInputStandIn.StandInHeartbeat` and the V1–V7 statics
   in `InstF_Forklift_Safety` are the only things standing between this script
   and a startable cell. Nothing in `bridge/` changes when they land.
2. **A partially successful write cycle leaves levels written and the
   heartbeat withheld.** Observed in run A: the three Bools land, then the
   heartbeat call throws. That is the safe direction and matches §5.1's
   intent, but the design does not state it explicitly and the sentence "no
   writes are issued" reads, strictly, as if it also covered the failing cycle
   itself. Worth one clarifying line in `STANDIN-WRITER-DESIGN.md` §5.1 — a
   `bridge/` edit, but the design document is the authority and should not be
   amended from the build without the orchestrator's say-so.
3. **`CreateInterface`/`Dispose` churn faults the API assembly** with an
   `AccessViolationException` inside `CInstanceNet`'s finalizer. It bit a
   polling harness, not the writer (which holds one interface). Recorded in
   the evidence so the next tool that polls this API does not rediscover it.
4. **`plc/forklift-safety/SPEC.md` §10 open item 8** (the writer's home) can
   now close on built code rather than on a design — a `plc/` edit, requested
   and not made.
