# m5-74 — a bench panel for the stand-in writer

    brief:               docs/briefs/m5-74-writer-bench-panel.md
    status:              done, with one leg of the demonstration not reproducible
                         in this session and named below
    invariants_touched:  none. No API, no OPC UA, no socket, no port, no service,
                         no second writer, and nothing in hmi/

## The one-line answer

**The panel is an input device for the writer's existing operator channel and a
display of the writer's existing log, and it is nothing else.** It appends one
command line to the writer's `-CommandFile` and follows the writer's session
log; it holds no PLCSIM API session, opens no socket and listens on no port, so
it adds no seam and no authority the terminal did not already have. It was
driven against the live `safecell3` CPU and against an independent OPC UA
witness.

## How it reaches the writer, and why that way

`bench_panel.ps1` runs **beside** the writer, not inside it: the writer's
single-threaded loop is load-bearing (design §1), and a message pump sharing it
could stall the heartbeat, which the F-program converts into a latched demand
within 1 s. The two things it touches are two files on the same host — the
command file it appends to, and the log it tails. The writer executes a panel
line through the **same `Invoke-Command2`** the console feeds, so the grammar,
the refusals and the log lines are the ones that already existed (§4.1).

**Every state on the panel is read out of the writer's log, never inferred from
the button that was pressed.** That is what makes a dead control visibly dead.

## The brief's constraints, and how each is met

| Constraint | How |
|---|---|
| nothing in `hmi/` | no file outside `bridge/` was written except `RUNBOOK.md`, under the owner's scope grant. The HMI's sentence about its F-layer pane stays true |
| no network path, port or service | two file handles on the writer's own host. `netstat` after teardown shows 45015 and 45016 free, and the panel never opened either |
| no control over a link-driven channel | the panel emits no such command and has no code path that could; the speed readings, the motion observation and the warning field are **displays**, in a column headed *READ-ONLY — arrives from a link*, over the sentence *setting one by hand would be inventing a measurement* |
| the zone belongs to the field while a link is up | the zone buttons are **disabled and labelled** *NOT IN FORCE HERE: a field link is up and owns this channel*, and become live again when the writer hands the channel back. Both directions were observed |
| no one-click reset | `reset press` on **mouse-down**, `reset release` on **mouse-up**, the elapsed hold shown live in ms against a drawn 200–3000 ms band. The panel judges nothing and never releases a hold for you |
| no PL, Category, SIL or PFH claim | the writer's banner is the second thing on the window, above every control, in its own strip |
| keep the log | unchanged in content. A panel press logs `OPERATOR \| command file: estop close` and then the identical `OPERATOR \| estop close -> EStopCircuitClosed := True` |

The panel also refuses to look usable when it is not: it compares the command
file the running writer **named** at start with the one it appends to, and goes
red with the reason when they differ, when the writer has no command file, or
when no `CYCLE` line has arrived for 1 s.

## Demonstrated against the live CPU

Instance `safecell3`, `OperatingState = Run`, with an **independent OPC UA
witness** on the CPU's own server — a different protocol stack from the API the
writer uses, and one that cannot see `SafetyInputStandIn` at all, only the
`ForkliftSafetyMirror` consequence.

| Leg | Result |
|---|---|
| **e-stop closed from the panel** | one press, `EStopCircuitClosed := True` in the writer's log at 13:00:05.633Z |
| **the boot state made obvious** | the panel shows **E-STOP CIRCUIT OPEN** at writer start, with the note that nothing closes it until a human does |
| **the read-only channels moving on their own** | with the vehicle stack up, both freshness sequences advanced every cycle and the speeds changed; with it down they showed *frozen — the F-program reads this as MISSING* |
| **the zone control not in force under a link** | field link up at 12:59:00.174Z → zone control disabled and labelled; link down at 13:04:43.900Z → ownership returned to the operator and the control went live |
| **a zone tripped and cleared from the panel** | `zone close` / `zone open` / `zone close` accepted and logged once the link was down |
| **a hold shown as it runs** | screenshot at **2 013 ms**, marker inside the drawn band, lamp reading *PRESSED — held at the CPU* |
| **the F-program judging the hold — measured** | three holds longer than the window: `SafetyResetFault` rose in the witness **while the button was still down**, at **3.171 / 3.225 / 3.159 s** after the press, and cleared 0.12–0.14 s after each release |

That last row is the monitored-reset mechanism being demonstrated rather than
assumed: it is the **program**, not the panel, that refuses a long hold, and
the 3000 ms edge the panel draws is the edge in force. **n = 3, one operator,
one machine — an observed range, not a bound.**

### The leg that was not achieved

**An accepted reset — one that clears the latched demands — was not reproduced
in this session.** Two attempts were correctly refused with a cause standing:
one with the zone circuit open (the field evaluation was reporting `ZONE 0`),
one with both circuits closed but **no speed source**, where both freshness
sequences were frozen and a missing reading is itself a standing demand. The
owner took the vehicle stack down mid-run and brings it up themselves, so the
clearing conditions could not be met from `bridge/`. Nothing on the panel's
side is untested by this: the press edge, the measured hold, the release edge
and the program's judgement of the hold were all observed end to end.

## One defect found and fixed by observation

After the writer died, the panel went on showing *field link up — it owns the
zone channel*, read from a line written **before** the death. That is a
statement about the cell that was no longer true. Fixed: when no `CYCLE` line
has arrived for 1 s, every read-only row reads *no report — the writer is not
writing* and the three lamps are greyed and marked *(last reported)*. History
is shown as history.

## Teardown — verified, not intended

Every item below was checked after the run, not assumed:

- `quit` was sent through the panel's own mechanism; the writer's log carries
  **`TERMINAL`** (three circuits FALSE, warning FALSE, motion TRUE/invalid,
  both speed sequences deliberately left frozen) and then
  **`EXIT reason=quit cycles=7516 overruns=4 write-failures=0`**;
- **no writer and no panel process**: `Get-CimInstance Win32_Process` matched on
  `standin_writer.ps1|bench_panel.ps1` returns nothing;
- **both ports free**: `netstat` finds no `:45015` and no `:45016`;
- **the mutex is free**: `Global\amr-standin-writer` was acquired by the check
  and released again;
- **PLCSIM Advanced is left running**, as `RUNBOOK.md` §6 says it should be
  between takes. Nothing in TIA Portal was opened, and no download was made.

Two witness processes in WSL both ran to completion; no python or WSL process
of mine survives.

## files_changed

| File | Change |
|---|---|
| `bridge/standin_writer/bench_panel.ps1` | **new** — the panel |
| `bridge/STANDIN-WRITER-DESIGN.md` | **new §10**, dated 2026-08-07: the naming ruling, the mechanism, the three things it cannot do, the in-force check, the log, how to run it, and what it must never become |
| `bridge/.gitignore` | ignore `standin_writer/commands/` — per-session command files are run artefacts |
| `bridge/standin_writer/evidence/m5-74/` | **new** — four panel screenshots against the live CPU, the two witness logs, the writer-log excerpt, and `m5-74-notes.md` describing them with the measured figures |
| `RUNBOOK.md` | **owner-granted scope.** §1b now starts the writer *and* the panel in one command and says what "it is working" looks like; §3 leads with the three facts that cost a live session; §5 and §6 name the panel. +24 lines net, prose cut to pay for the steps |

`standin_writer.ps1` was **not changed**. The panel needed nothing from it: the
command file and the log were already there.

## invariants_touched

None. The panel writes no tag, holds no session, listens on nothing and
computes no verdict. Invariant 10 in particular is untouched: there is still
exactly one writer of the eleven `SafetyInputStandIn` members.

## open_questions

1. **The accepted reset is owed a run.** It needs the vehicle stack up, because
   a frozen speed sequence is a standing demand. It should be the first thing
   observed after the owner's next `./demo.sh up`, and it costs one press.
2. **The 3.16–3.23 s press-to-fault figure is n = 3.** It is one operator on one
   machine and includes the panel → file → 50 ms writer cycle → F-cycle path. It
   is quoted as observed, and the split between the F-program's PT and the path
   was not separated.
3. **The panel is not DPI-aware.** At the owner's 125 % scaling Windows
   bitmap-scales it, which is legible but soft; it fits 2048×1152 with room. On
   a smaller screen it would want scrolling.

## Requests — work this brief could not do

| # | Request | Owner |
|---|---|---|
| 1 | **`demo.sh up`'s "you forgot the writer" message still prints the bare `standin_writer.ps1` command.** It should print the `bench_panel.ps1` line instead, so the panel comes up on presentation morning without anyone remembering it exists | infra |
| 2 | **`demo.sh down` should say the panel is a window to close**, beside the line it already prints about the writer and its ports | infra |
| 3 | **`RUNBOOK.md` §3's reset table now says "about 2 s".** m5-72 OQ2 recorded an 800 ms hold accepted where the RUNBOOK said 2000; this brief measured the **upper** end (≈3.2 s to a fault, n = 3) but not the lower. The accepted band deserves one characterisation run so the RUNBOOK and the machine agree at both ends | plc, one short brief |

## next_suggested

Take request 1 — one line in `demo.sh` — before the next `up`, so the panel is
part of the start rather than something to remember.
