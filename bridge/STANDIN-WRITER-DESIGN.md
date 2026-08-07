# The stand-in writer — implementation design

**ENGINEERING STAND-IN.** This process is the simulation's substitute for the
*wiring* of three safety-rated devices that do not exist in this project. It
carries no Category, no PL, no SIL, no PFH, no channel count and no diagnostic
coverage, and nothing in this document claims otherwise (SPEC §1.2 N2–N4,
FIO-FEASIBILITY §6 consequence 1). The word *stand-in* appears in its file
name, its console banner, its log header and every tag it writes.

**Authority.** `plc/forklift-safety/SPEC.md` §7 specifies this process
completely — the rate, the level republish, the members, the sources, the
command set, the failure behaviour, the log — and **§11.2 extends it** with
the speed-source link, the seven new members and the `WARN` vocabulary. This
document chooses **how** to realise them, never what they do. Where the two
disagree, the SPEC wins and this document is corrected. ADR 0015 D1 fixes the mechanism (API by tag name, no
hand at a watch table); the owner's 2026-08-05 ruling fixes the home:
**`bridge/`**, because bridge/ is already the simulation's stand-in for field
wiring and this is that role for the safety channel (SPEC §10 open item 8 is
thereby answered; closing the item in SPEC is plc's edit, requested in the
m5-36 report).

**Why it ships tonight.** With the S015 delta built, `StandInValid` boots
FALSE and stays FALSE until the heartbeat is **seen to change** (SPEC §5.4
V2). Nothing else in the system advances that heartbeat, so until this process
runs, both demands stay latched, no reset is accepted, and the cell —
including the M4 teleop demonstration — is inert. That is fail-safe and
correct; this process is what makes the cell startable again.

---

## 1. What is built — one file, one loop

| Item | Decision |
|---|---|
| File | `bridge/standin_writer/standin_writer.ps1` — one script, no module, no second file |
| Runtime | **Windows PowerShell 5.1** on the Windows host, beside PLCSIM Advanced. `Add-Type -Path` on `Siemens.Simatic.Simulation.Runtime.Api.x64.dll`, API **7.0** — exactly the proven kernel of `plc/forklift-safety/evidence/m5-03b-standin-stimulus-proof.ps1` and `m5-25-standin-stimulus-repeat.ps1`. **No new dependency** |
| Parameters | `-SpeedPort <n>` default `45016` (SPEC §11.2 design value). `-Instance <name>` **mandatory** (tool-derived; read from the PLCSIM Advanced control panel, never assumed — the probe ran on `FIOPROBE`, which is **not** the working project's instance; the working project read back **`safecell3`** on 2026-08-05, m5-25 log, and may change). `-Dll <path>` default `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll` (a read-back from the m5-03 record). `-Port <n>` default `45015` (SPEC §7.2 design value). **The cycle is not a parameter**: 50 ms is settled by §7.1 and a knob would invite drift |
| Concurrency | **Single-threaded, one loop.** No runspace, no job, no timer callback, no background thread. This is load-bearing, not simplicity: the heartbeat may only advance from the same loop iteration that services commands and writes levels, so anything that stalls the process stalls the heartbeat, and §5.4 converts that into a latched demand within `STANDIN_STALE_MAX` = 1 s. A second thread that kept the heartbeat alive past a wedged main loop would defeat SPEC §7.3 row 1 |
| Start | Manually, by the operator, from Windows PowerShell 5.1: `powershell -ExecutionPolicy Bypass -File bridge\standin_writer\standin_writer.ps1 -Instance <name>`. Start order against the CPU, the WSL bridge and the HMI is irrelevant — the republish repairs any ordering (§5) |
| Logs | `bridge/standin_writer/logs/standin-writer-<UTC yyyyMMddTHHmmssZ>-pid<pid>.log`, created with `CreateNew` (refuse a collision, never overwrite), `AutoFlush = $true`. One file per session, unique per start (LESSONS 2026-07-28). Add `standin_writer/logs/` to `bridge/.gitignore` |

### 1.1 The write set — exact and closed

The writer writes **exactly eleven tags** and nothing else, held as one literal
allowlist in one place in the script; every write goes through one helper that
takes the tag name from that list only:

| Tag | Call | Value | Group |
|---|---|---|---|
| `SafetyInputStandIn.EStopCircuitClosed` | `WriteBool` | operator-owned level | core |
| `SafetyInputStandIn.ZoneDeviceCircuitClosed` | `WriteBool` | field- or operator-owned level (§3) | core |
| `SafetyInputStandIn.ResetButtonPressed` | `WriteBool` | operator-owned level | core |
| `SafetyInputStandIn.StandInHeartbeat` | `WriteInt16` | counter, +1 per cycle, wraps `30000 → 0` | core |
| `SafetyInputStandIn.WarningFieldClear` | `WriteBool` | field-owned level; `FALSE` unless a live `WARN 1` says otherwise (§3) | warning |
| `SafetyInputStandIn.MotionPresent` | `WriteBool` | source-owned level, fail direction `TRUE` (§3.1) | motion |
| `SafetyInputStandIn.MotionObservationValid` | `WriteBool` | diagnosis only; `FALSE` whenever the observation is absent | motion |
| `SafetyInputStandIn.SpeedReadingA` / `…B` | `WriteInt16` | mm/s, signed. **Written only in a cycle that received a fresh line** | speed |
| `SafetyInputStandIn.SpeedSeqA` / `…B` | `WriteInt16` | freshness sequence, +1 in the same cycle, wraps `30000 → 0` | speed |

**Group gating, not per-member gating.** The seven §11.3 members may not exist
on a half-built controller. At every connect the writer reads the instance's
own tag list and marks each of the three groups present or absent, logging the
answer (`MEMBERS`); an absent group is **inert for the session and every
member of it is left untouched**. All four speed members or none: a reading
written without its sequence would hand the F-program a value with no way to
tell whether it is current, which is the failure §11.2 exists to prevent. The
probe is re-run at every reconnect, because a download changes the answer.

S7 `Int` is 16-bit signed; the write call is the API's signed-16-bit call. If
the installed assembly names it differently, discover the name from the
instance object (`$inst | Get-Member Write*`) and use the 16-bit signed call —
**never change the DB member's type to fit the API**. The wrap bound keeps the
counter inside positive Int16 range; V1's `<>` needs only that consecutive
cycles differ, and 30000 × 50 ms = 25 min between wraps.

The writer **reads** nothing from the CPU except `OperatingState`, logged at
start and at each reconnect. It never reads or writes `InstF_Forklift_Safety`
or any other DB: verification in the consumer's view (LESSONS 2026-08-04)
belongs to the §8 watch table and the m5-25 repeat script, **run while the
writer is stopped** — two processes writing one DB is the dual-writer failure
this project already refused once (§6).

---

## 2. The cycle — 50 ms, deadline-scheduled, level republish

Per §7.1: 50 ms, logged at start-up; **every LEVEL every cycle**, never
write-on-change (a CPU restart reverts the DB and only a republish repairs it,
LESSONS 2026-07-28; a level repair produces no edge). That is eight of the
eleven: the three circuits, the heartbeat, the warning verdict and the two
motion members.

**The two speed readings are the exception, and it is the whole point.** They
are **not** republished. A channel writes its value and advances its sequence
only in a cycle that received fresh source data; in every other cycle
**neither is written**, the sequence freezes where it stands, and the
F-program reads a frozen sequence as a **missing** reading — which is a
demand, never a zero and never the last value (SPEC §11.2, §11.5 SL1–SL8).
Republishing here would smooth exactly the gap the chain exists to see. Two
consequences, both deliberate:

- after a CPU restart the DB reverts both sequences to `0` while the writer's
  own counters stand at `N`; the next fresh write puts `N+1` there, the F-side
  `CMP <>` sees a change, and the channel comes back the moment a real reading
  does. In the one cycle where `N+1` would itself be `0` the F-side sees no
  change for one cycle — which fails toward *stale*, the safe direction;
- the terminal write (§5.4) writes neither reading and neither sequence.

Loop body, in order, every iteration:

1. **Console**: drain buffered keys with `[Console]::KeyAvailable` +
   `[Console]::ReadKey($true)` — per-key, non-blocking, echoed, accumulated
   into a line buffer; execute the command on Enter (§4). **Never
   `[Console]::ReadLine()`** — it blocks until Enter, the loop stalls while
   the operator types, the heartbeat freezes and the demands latch. Set
   `[Console]::TreatControlCAsInput = $true` at start so Ctrl+C arrives as a
   key and is handled as `quit` (§5.4), not as an abort that skips the
   terminal write.
2. **Field link** (§3): accept a pending connection if none is active
   (`TcpListener.Pending()`); read available bytes non-blocking
   (`DataAvailable`); parse complete lines; apply `ZONE`/`WARN`/`PING`; test
   whether the peer has hung up (`Test-PeerClosed`, §3.2); then test
   staleness: link up and no well-formed line for **1000 ms**
   (`FIELD_LINK_STALE_MAX`, §7.2) → link down.
2b. **Speed link** (§3.1): the same shape on `-SpeedPort`, applying
   `SPD`/`MOT`/`PING`, then the motion silence window.
3. **Pulse expiry**: if a `reset pulse` is active and its commanded duration
   has elapsed, drive `ResetButtonPressed := FALSE` and log the shaped
   release. This is the one writer-generated actuation §7.2 allows.
4. **Write**: the tags of §1.1 through the allowlist helper — every level,
   plus a fresh channel's reading and sequence — heartbeat incremented **only
   on a fully successful write cycle** (§5.1). Log one `CYCLE` line, whose
   `spdA=<value>@<seq>` field reads `-` in a cycle where that channel wrote
   nothing, so the log itself carries the silence. Then clear both freshness
   flags unconditionally, including on a failed or disconnected cycle: a
   reading whose write was lost must never advance a sequence later.
5. **Sleep** to the deadline: `t_next = t_start + n × 50 ms` from one
   `Stopwatch`; `Thread.Sleep(max(0, remaining))`. An overrun is logged and
   counted, **never compensated** — no catch-up burst, no skipped-cycle
   logic. Windows timer granularity (~15 ms) is jitter the design absorbs:
   `STANDIN_STALE_MAX` = 1 s is twenty cycles of headroom (SPEC §3.3).

**Timers, exhaustively.** The writer owns four timers and no fifth: its own
50 ms cycle, the staleness of its **own input channel** (the field link), the
silence of its **own other input channel** (`MOTION_SILENCE_MAX` = 250 ms on
the `MOT` line), and the operator-commanded pulse width. All four are fixed by
SPEC §7 and §11.2. **None watches the plant**: the motion timer asks "has my
source spoken", never "is the vehicle moving", which is the same question the
field-link timer asks about its own source. None debounces a signal, none
delays a value, and no threshold over a speed appears anywhere in the writer —
the speed limit, the discrepancy threshold and every persistence delay are the
F-program's, and a second copy here would be a process decision in the bridge.

The **speed link has no staleness timer at all**, deliberately: every
consequence of silence already runs in the demand direction, since a cycle
with no line freezes the sequence by construction. What it does have is
end-of-stream detection, which is socket state and not a timer (§3.2).

---

## 3. The zone channel with the field evaluation absent — tonight's state

**The field evaluation does not exist** — m5-12 (`agv/forklift/
FIELD-EVALUATION.md`) is a design, not a running node. This is not a special
mode the writer needs: it is §7.2's own rule, which already binds the zone
channel to the operator console **"only while no field link is up"**. So:

- **The writer starts, runs and serves the cell with no field link ever
  arriving.** It never waits for, probes for, or requires one. A writer that
  refused to run without a field evaluation would leave the cell inert, which
  is the situation being fixed.
- **In that state the zone channel reports what the operator last commanded,
  boot value `FALSE` (open).** Open is the safe choice: it is the wire-NC
  fail-safe direction — no source vouching for a clear zone reads as a demand,
  never as a clear field — and it matches the DB's own start value, so the
  writer's first republish changes nothing the CPU had not already assumed.
- **How the operator gets the cell moving tonight** — exactly T6.0.1–T6.0.4
  (SPEC §9.1): start the writer (`StandInValid` → TRUE within ≈150 ms; both
  demands correctly still latched); `estop close`; `zone close`;
  `reset press`, hold ≈1 s, `reset release` → both demands clear; enable and
  drive from the HMI as in M4. Zone plays are the operator form of §7.7 —
  `zone open` at the floor marking — which exercises every network of §5
  identically and is labelled as satisfying **nothing** in criterion (a)'s
  intrusion chain (§7.6). Criterion-(a) evidence waits for the field form.

**The listener is still built tonight** (it is ~30 lines and §7 specifies
it), so the day m5-12's node exists it dials in with no writer change:

| Rule | Statement |
|---|---|
| Transport | One TCP listener on `0.0.0.0:<Port>` (default 45015). The WSL client dials the Windows-side address from **its own** configuration — a host-derived read-back value, never taken from any document (§7.2, ADR 0006). One client at a time; a second connection is accepted, closed and logged as refused |
| Protocol | Newline-delimited ASCII: `ZONE 0`, `ZONE 1` at every verdict transition, `PING` at 1 Hz keepalive. **Encoding, fixed by this design because §7 left the digit unassigned: the digit is the circuit level** — `ZONE 1` = field clear → `ZoneDeviceCircuitClosed := TRUE`; `ZONE 0` = intrusion (or the evaluation's own fault verdict) → `FALSE`. This matches FIELD-EVALUATION §8 rule 1, which already sends `ZONE 0` for a dead scanner. The m5-12 build must adopt this encoding (requested in the m5-36 report) |
| Liveness | Only well-formed `ZONE`/`PING` lines refresh the link clock; garbage refreshes nothing and is logged as a refusal — bytes are not proof of a live *verdict* |
| Link up | Ownership of the zone channel passes to the field; operator `zone` commands are **refused with a logged refusal** (§7.2). Until the first `ZONE` line arrives the channel is held `FALSE` — a link with no verdict yet is not a clear field |
| Link down | On staleness (> 1000 ms), EOF, hang-up or socket error: drive `ZoneDeviceCircuitClosed := FALSE` **and `WarningFieldClear := FALSE`**, log the transition, close the socket, and return ownership of the zone to the operator — who must issue a deliberate `zone close` to re-close it. Loss of the field source reads as an intrusion **and** as warning-occupied, never as a clear field (§7.3 row 2, SPEC §11.2) |

**The warning verdict rides this same link** (SPEC §11.2), one vocabulary
entry, same polarity convention as `ZONE` — the digit is the channel level:

| Line | Effect |
|---|---|
| `WARN 1` | `WarningFieldClear := TRUE` — warning field clear |
| `WARN 0` | `WarningFieldClear := FALSE` — occupied; the limit is selected |

Before the first `WARN` line of a session the channel holds its start value
`FALSE`: the limit is in force until a source has said otherwise.
**There is deliberately no operator command for it**, unlike `zone`. An
operator typing "the warning field is clear" would be a human vouching for a
field verdict, which is exactly what the wire-NC discipline refuses; the same
reasoning bars an operator command for either speed reading or the motion
flag. The one consequence to know about is an operating one: with no field
source running, the reduced limit is in force for the whole session
(EVIDENCE_BUILD §7.8).

---

## 3.1 The speed-source link — port 45016

SPEC §11.2's second TCP listener, the same shape as §3's and with the same
"none is required" property: the writer starts, runs and serves the cell with
no speed source ever arriving.

| Line | Effect |
|---|---|
| `SPD A <int>` / `SPD B <int>` | signed drive-wheel tread speed, mm/s. Latest value wins within a cycle; the sequence advances **once** |
| `MOT <p> <v>` | `MotionPresent := p`, `MotionObservationValid := v`, both carried **unchanged** — `p` already folds the source's own fail direction, and the verdict has one owner |
| `PING` | keepalive, for the log only. **It refreshes no channel**: a PING is not a reading, and letting one hold a speed alive would be the repetition the whole design refuses |

Refused, logged, and advancing nothing: a malformed line; a `SPD` value
outside the S7 `Int` the DB member is. The second is **representability, not
plausibility** — the writer applies no physical window to a reading, because
that window is the F-program's (§11.5 SL6/SL7) and a second copy here would be
a process decision in the bridge. Its effect is the safe one: nothing written,
sequence frozen, channel reads as missing. `agv/`'s client reached the same
rule independently at its own end (m5-56).

**The motion channel fails toward moving.** If no `MOT` line has arrived for
`MOTION_SILENCE_MAX` = 250 ms, or the link is down, or none has ever arrived
this session, the writer drives `MotionPresent := TRUE` and
`MotionObservationValid := FALSE` and logs the transition. An unobservable
vehicle is *moving*; a false *still* is what would corroborate a lying
encoder. Note the vehicle-side carrier stops forwarding `MOT` after its own
0.15 s window, so the worst case from a dead observation to `MotionPresent`
TRUE is **0.40 s**, not 0.25 — bounded, on the safe transition, and raised to
`plc/` because §11 should state the number rather than inherit it.

## 3.2 End of stream — why both links ask the socket

`NetworkStream.DataAvailable` is FALSE at end of stream, so a read loop
guarded by it never runs and never sees the zero-length read. Measured on
2026-08-06: a source that closed cleanly left the client object held and the
next connection was refused as a "second connection" for ever. `Test-PeerClosed`
— `Socket.Poll(0, SelectRead)` with `Available == 0` — is the non-blocking
end-of-stream test, and it is **socket state, not a timer**. It runs on both
links, **after** the buffered lines are parsed so a verdict sent immediately
before the close is still applied. The field link had been surviving this only
because its 1 s staleness reaper eventually freed the object; the speed link
has no reaper by design, so it needed the real test.

---

## 4. The operator console — command grammar, exactly §7.2's

Commands are read per-key in the loop (§2 step 1) and executed on Enter.
**One command, one action** (§7.2): the writer never repeats, retries or
auto-releases a press beyond the pulse's own shaped release.

| Command | Effect |
|---|---|
| `estop open` / `estop close` | `EStopCircuitClosed := FALSE` / `TRUE` |
| `zone open` / `zone close` | `ZoneDeviceCircuitClosed`; **refused while the field link is up** |
| `reset press` / `reset release` | `ResetButtonPressed := TRUE` / `FALSE`, held until countermanded |
| `reset pulse <ms>` | `TRUE` now, `FALSE` after `<ms>`; `<ms>` validated as an integer 1–60000 (validation, not shaping — the F-program judges the hold, §7.4) |
| `status` | Print levels, heartbeat, link state, API state to the console. Reads nothing from the CPU, writes nothing |
| `quit` | Terminal write, then exit (§5.4) |

Refused with a logged `REFUSED` line, never silently: `zone` while the field
link is up; `reset pulse` while a press is already held (a second actuation
needs the first to end); a malformed `<ms>`; any unrecognised line. The
levels the commands set are the writer's internal state; the CPU sees them at
the next 50 ms republish.

### 4.1 The command file — the same operator, a second keyboard (m5-58)

`-CommandFile <path>` makes the writer poll a file once per cycle and execute
each newly appended line **through the same `Invoke-Command2`** the console
feeds. Same grammar, same refusals, same log lines; the only difference is
where the characters came from, and every executed line is logged as
`OPERATOR | command file: <line>` before it acts.

**Why it exists.** `[Console]::KeyAvailable` needs a real console, and a
writer started from a script has none — it logs `operator console =
UNAVAILABLE` and no command can be entered for the whole session. That would
have left `estop`, `zone` and `reset` undrivable in exactly the unattended
validation runs whose subject is those three channels (m5-58). It is the
operator's hands moved to a file, not a new capability.

**What it deliberately does not add.** No command for a speed reading, a
motion flag or the warning field: those arrive from a source on the two links
or they are missing, and a human typing one would be inventing a measurement.
The `default` arm of `Invoke-Command2` refuses them by the same sentence it
always did.

**How it behaves.** Polled inside the one loop, so it can never outrank the
heartbeat: only whole lines already on disk are consumed, a partial trailing
line is left for the next cycle, a file that shrinks is re-read from the top
rather than from the middle of a line, and any IO error is logged once as
`REFUSED` and swallowed. Empty (the default) opens no file. **Write the file
as UTF-8 without a BOM** — a BOM is a character, the writer offers it to the
grammar, and it is refused loudly as an unrecognised command, which is the
correct behaviour and a confusing first line.

---

## 5. Failure behaviour — how each §7.3 row is achieved

§7.3 specifies the behaviour; these are the realisation mechanisms.

### 5.1 Writer death, and the API session dropping

Death in any form — process kill, host down, wedge — stops the loop, the
heartbeat freezes at the CPU, and §5.4 latches both demands within
`STANDIN_STALE_MAX` + one F-cycle ≈ 1.1 s. The writer contributes exactly one
thing to this guarantee: **single-threadedness** (§1), so no surviving thread
can keep the heartbeat alive past a dead command path.

An **API failure** (any exception from a write or from `CreateInterface`) is
handled, not died on — but handled in the direction that is
indistinguishable from death at the CPU:

- catch, log `API` with the exception text, `Dispose()` the interface, mark
  disconnected;
- while disconnected: the loop keeps running (console and field link stay
  live, state still tracked), **no writes are issued and the heartbeat does
  not advance** — at the CPU this is writer death, demands latch, which is
  the safe direction;
- reconnect attempt once per second: `CreateInterface($Instance)` +
  `UpdateTagList()`, each attempt logged; on success log `OperatingState`,
  resume the republish — which repairs all four members within one cycle and,
  being a level repair, latches nothing and fires nothing.

### 5.2 CPU STOP and return

No special handling, by design: the republish **is** the handling. While the
CPU is stopped, writes either fail (→ §5.1 path) or land in a DB the restart
will re-initialise; either way, on return to RUN the DB reads start values
for at most one writer cycle, both demands latch (correctly — SPEC §3.1), the
next republish restores the levels, and the latches stand until one monitored
reset (§7.1 "After a CPU restart", T6.6). The writer does not poll
`OperatingState` in the cycle and takes no decision from CPU state.

### 5.3 Started twice

A named mutex, `Global\amr-standin-writer`, acquired before anything else —
before the log, before `Add-Type`, before any API contact. If it is already
held, print one refusal naming the mutex and the fact that a writer is
already running, and exit non-zero having touched nothing. Two writers on one
DB would be a second writer of every tag (invariant 10) and would keep the
heartbeat alive across the first writer's death — both disqualifying.

### 5.4 Deliberate exit — the terminal write

On `quit`, and on Ctrl+C (a key, per §2 step 1), and in a `finally` around
the loop as best effort: **write the terminal values first, then fall
silent** (LESSONS 2026-08-04 ×2: where a consumer holds levels, silence is
not an absence; a state whose purpose is to stop publishing publishes its
terminal value first). Terminal values: the three channels `FALSE` — open,
unpressed, the demand direction — `WarningFieldClear` `FALSE`, and
`MotionPresent` `TRUE` with `MotionObservationValid` `FALSE`; then log
`TERMINAL`, `Dispose()`, close the log.

**The two speed readings and both sequences are written by nothing here, on
purpose.** A terminal zero would be a speed the writer invented, and a
terminal repeat would be the last value outliving its source. Leaving both
sequences frozen is the honest terminal statement: from this instant the
readings are missing, and missing is a demand. The `TERMINAL` line records
where each sequence stopped, so the log says it rather than implying it.

The heartbeat then freezes, `StandInValid` falls within 1 s, and both
demands latch on **channels already open**, so no ambiguity about why. A
mid-press `quit` writes the reset `FALSE` in the terminal write; even if the
write is lost, §5.4's walkthrough refuses the dying edge in-cycle (SPEC §5.4).
If the API is unreachable at exit the terminal write fails, is logged as
failed, and death-by-staleness covers it.

---

## 6. Coexistence with the WSL bridge process — nothing is shared

`bridge/` now holds two processes. They share **nothing**: no code, no
config file, no log, no socket, no session, no tag.

| | ROS 2 ↔ OPC UA translator (existing) | Stand-in writer (this design) |
|---|---|---|
| Host | WSL (Ubuntu, venv) | Windows, beside PLCSIM Advanced |
| Reaches the CPU by | OPC UA client session (invariant 4) | PLCSIM Advanced API, by tag name — **below** any client interface |
| Touches | The configured `Input/`/`Output/` groups + `BridgeHeartbeat` | The eleven members of `SafetyInputStandIn`, which the OPC UA server does not expose at all (SPEC §4.2 step 14) |
| Listens | Never, on anything | Two TCP listeners: 45015 for the field evaluation, 45016 for the speed source. Nothing else, ever |
| Started by | `run_bridge.py` in a WSL shell | `standin_writer.ps1` in a Windows shell |
| Stimulates a demand | Never — carries process signals only | Yes — it is the stand-in for the safety-channel wiring |

The two write sets are disjoint by construction and *provably* so: the
stand-in DB is unreachable over OPC UA (verified by independent browse, SPEC
§4.2 step 14), and the writer holds no OPC UA stack. Start order is
irrelevant in every combination; both run together throughout M4 teleop and
T6. The m5-25 repeat script is the one process that must **not** run beside
the writer (§1.1).

---

## 7. The log — format, exactly

One line per event, `yyyy-MM-ddTHH:mm:ss.fffZ | CLASS | detail`, classes:

| Class | When |
|---|---|
| `START` | Once: stand-in banner, instance name, DLL path and API version, cycle = 50 ms (§7.1 requires the cycle logged at start-up), port, `OperatingState`, log file name |
| `CYCLE` | Every cycle: `hb=<n> estop= zone= reset= warn= mot=<p>/<v> spdA=<v>@<seq> spdB=<v>@<seq>` — the record of the writes issued (§7.2 "every API write issued"; the one line carries them all). A `-` in a `spd` field is a cycle in which that channel wrote **nothing**, so the log carries the silence as directly as it carries the readings |
| `OPERATOR` | Every console command accepted, with the value |
| `FIELD` | Every `ZONE` or `WARN` line applied, with the value |
| `SPEED` | Every speed-link event that changes state: each channel's first written reading, and every motion transition including the silence rule firing |
| `SPEEDLINK` | Every speed-link state change: up, down (EOF/hang-up/error), refused second connection |
| `MEMBERS` | Once per connect: which of the three SPEC §11.3 groups this CPU carries, and which are inert this session |
| `LINK` | Every field-link state change: up, down (stale/EOF/hang-up/error), refused second connection |
| `REFUSED` | Every refusal, with the reason (§4) |
| `API` | Write/connect failure, each reconnect attempt, reconnect success |
| `OVERRUN` | A cycle that missed its deadline, with the measured slip |
| `TERMINAL` | The terminal write of §5.4, or its failure |
| `EXIT` | Last line |

At 20 cycles/s the `CYCLE` lines cost ~5 MB/hour — accepted; §7.2 makes the
log load-bearing evidence (§7.6's correlated record), not a nicety, and the
file is per-session so no run can destroy an earlier one.

---

## 8. Acceptance — what the coding agent verifies tonight

Instrument: the §8 watch table `Forklift F gate`, Groups 1 and 3, in
*Monitor* mode — reading only. Safety mode activated throughout. These are
SPEC §4.5 step 13 and the T6.0/T6.7 shapes, run as build verification, **not**
as T6 evidence (N5 — nothing here closes anything).

1. **Double start refused**: second invocation exits with the mutex message,
   log untouched, no API contact.
2. **Belief**: start the writer → Group 1 heartbeat advances; `HeartbeatSeen`
   → TRUE, `StandInValid` → TRUE within ≈150 ms of the first republish; both
   demands still latched.
3. **The cell starts**: `estop close`, `zone close`, `reset press` ≈1 s,
   `reset release` → both demands clear, `SafetyResetRequired` → FALSE.
4. **Console does not starve the heartbeat**: type a command at one key per
   second, ≥ 5 s between first key and Enter — `StandInValid` stays TRUE
   throughout (the non-blocking-read requirement, §2 step 1, observed).
5. **Death converts to a demand**: kill the process (not `quit`) → within
   `STANDIN_STALE_MAX` + one F-cycle, `StandInValid` → FALSE, both demands
   latch (§7.3 row 1; T6.7.1 shape).
6. **Rebirth restores belief, not motion**: restart (fresh log name observed)
   → `StandInValid` TRUE, latches stand, cleared only by a fresh reset
   (T6.7.2 shape).
7. **Terminal write**: `quit` → log shows `TERMINAL` then `EXIT`; Group 1
   reads all three channels FALSE before the heartbeat freezes.
8. **Zone refusal shape**: with no field link (tonight's state), `zone close`
   is accepted; the `REFUSED` path is exercised with a malformed command
   (e.g. `reset pulse x`) and appears in the log. Field-link acceptance
   testing waits for m5-12 or a throwaway `ncat` line-feeder — either is a
   builder's smoke test, never criterion-(a) evidence (§7.6).

The §11.2 extension adds five, verified in EVIDENCE_BUILD §7:

9.  **A fresh reading reaches the F-program**: with a source on 45016, both
    `SpeedSeq` members advance in the consumer's view and `SpeedAValid` /
    `SpeedBValid` rise. The reading on the wire, in the `CYCLE` line and in the
    DB is the same integer, so the three can be diffed.
10. **A silent channel freezes its own sequence and nothing else's**: one
    channel taken silent while the other runs — the frozen one's sequence stops,
    its value is **not** rewritten, and the F-program latches the demand.
11. **The motion channel fails toward moving**: `MOT` stopped for longer than
    `MOTION_SILENCE_MAX`, and on a link drop, drives `MotionPresent` TRUE with
    `MotionObservationValid` FALSE.
12. **`WARN` reaches `WarningFieldClear` both ways**, and a field-link loss
    drives it FALSE together with the zone channel.
13. **A source that hangs up can dial back in**: two source sessions back to
    back on 45016, the second accepted rather than refused as a second client
    (the D1 defect of §7.5).

Every check is an observation in the **consumer's view or the watch table**,
never the writer's own read-back (LESSONS 2026-08-04) — the writer has no
read-back to consult by construction (§1.1).

---

## 9. What this process must never do

Restated from `bridge/README.md`'s boundary (which this design amends) so the
coding agent has it on the page they build from:

- No OPC UA, in any role. No ROS 2. No MQTT, no VDA 5050, no fleet, no HMI.
- No write outside the eleven-tag allowlist of §1.1; no read of any CPU datum
  but `OperatingState`. Never a tag of `InstF_Forklift_Safety`, never F-data,
  never a `Modify`, never another DB.
- No process decision: no threshold over plant state, no debounce of a
  channel, no verdict the PLC also computes, no auto-release of a press
  beyond the commanded pulse, no auto-reset, no auto-anything after a
  restart. The three timers of §2 are exhaustive.
- No second thread, no detached child, no state that survives the process.
- No claim: not a safety device, not a safety path, no PL, no Category, no
  SIL, no PFH — an engineering stand-in for wiring, labelled as such
  everywhere it appears.

---

## 10. The bench panel — 2026-08-07 (m5-74)

`bridge/standin_writer/bench_panel.ps1`. A small window that drives the
writer's operator channel by hand, so the three safety inputs no longer have
to be typed as commands into a console. It was built because typing them cost
a live session on 2026-08-07 (m5-72 §3).

### 10.1 What it is called, and why — the owner's ruling

**A bench panel, not a vehicle panel.** It imitates no real device and claims
none exists. Its face reads **"Safety input channels — engineering stand-in"**,
and it presents the *wiring* this process stands in for.

The owner considered calling it the vehicle's control panel and ruled against
it on 2026-08-07: the **vehicle e-stop is deferred to M6**, and `docs/safety/
SRS.md` B4 states the cell e-stop stops no vehicle. A panel labelled as the
vehicle's would imply a function this gate does not have. The writer's existing
banner — **NOT A SAFETY DEVICE**, no Category, no PL, no SIL, no PFH — is on
the panel at least as visibly as it is in the terminal: it is the second thing
on the window, in its own strip, above every control.

### 10.2 What it is mechanically — an input device and a display, and nothing else

It adds **no seam**: no network path, no port, no service, no second writer.

| | |
|---|---|
| Writes to the CPU | **Nothing.** It never loads the PLCSIM Advanced assembly, holds no API session, opens no OPC UA session and touches no tag. §1.1's allowlist still has exactly one writer |
| Reaches the writer by | **One line appended to the writer's `-CommandFile`** (§4.1). The writer executes it through the same `Invoke-Command2` the console feeds — same grammar, same refusals, same log lines |
| Learns the state by | **Following the writer's own session log**, tailed read-only. Every value on the panel is read out of a `CYCLE`, `LINK`, `SPEEDLINK`, `API` or `MEMBERS` line, never inferred from the button that was pressed |
| Listens on | **Nothing.** Two files on this host, both beside the writer |
| Process | Its own, beside the writer's. **Not inside it**: the writer's single-threaded loop is load-bearing (§1), and a message pump sharing it could stall the heartbeat — which §5.4 converts into a latched demand within 1 s |

That the panel shows the *writer's* view rather than its own intent is what
makes a dead control visibly dead. A button whose command was refused, or
never arrived, changes nothing on the panel.

### 10.3 Three things it cannot do, by construction

1. **It cannot drive a link-driven channel.** There is no control for either
   speed reading, for the motion observation or for the warning field. The
   panel emits no such command and has no code path that could; the writer's
   `default` arm would refuse one if it did. §3's sentence is the reason and it
   is printed on the panel: *a human setting one would be inventing a
   measurement.* They appear as **displays**, in their own column, under the
   heading `READ-ONLY — arrives from a link`.
2. **It cannot pretend to own the zone channel.** While a field link is up the
   zone belongs to the field (§3). The panel's zone buttons are then
   **disabled and labelled** — *"NOT IN FORCE HERE: a field link is up and owns
   this channel"* — rather than appearing to work and doing nothing.
3. **It cannot make the reset one click.** `reset press` is sent on
   **mouse-down** and `reset release` on **mouse-up**; the elapsed hold is
   shown live, in milliseconds and against a drawn 200–3000 ms band. The panel
   **judges nothing**: it never shortens a hold, never extends one and has no
   code path that releases one on its own. The monitored reset is a mechanism
   this project demonstrates rather than assumes, and a one-click button would
   hide all of it. The single exception is closing the window with the button
   still held, which sends `reset release` — the same command the operator
   would have sent, rather than leaving the level held at the CPU with nobody
   to release it.

**The band is a picture, not a threshold.** 200–3000 ms is drawn because the
F-program judges against it; the panel applies it to nothing and a hold outside
it is sent unchanged, to be refused by the program whose decision it is.

### 10.4 In force, or plainly not

The panel refuses to look usable when it is not connected to anything. It reads
the running writer's `START` block, compares the command file the writer
**named** with the one the panel **appends to**, and disables every control
with the reason in red when they differ, when the writer was started with no
command file at all, or when no `CYCLE` line has arrived for 1 s (the writer is
not writing, so its heartbeat is frozen at the CPU and both demands latch).
This is the same discipline as the zone control: a button that reaches nothing
is worse than no button.

**A writer that is not writing is not reporting either.** When no `CYCLE` line
has arrived for 1 s, every read-only row falls to *no report* and the three
lamps are greyed and marked *(last reported)*. Found by observation on
2026-08-07: after the writer died, the panel went on showing *field link up —
it owns the zone channel* from a line written before the death, which is a
statement about the cell that was no longer true. History is now shown as
history.

### 10.5 The log is unchanged, and it is still the evidence

The panel is an **input device, not a replacement**. A change made from it is
logged by the writer in the same words the typed command would have produced —
`OPERATOR | command file: estop close`, then the identical
`OPERATOR | estop close -> EStopCircuitClosed := True`. Committed figures have
been read out of these logs and they keep reading the same. The panel's own
lower-right pane shows the writer's latest `OPERATOR`, `REFUSED`, `FIELD`,
`SPEED`, `LINK` and `API` lines **verbatim**, so the operator sees the record
being written as they act.

The panel writes exactly one file of its own: its per-session command file,
`standin_writer/commands/bench-panel-<UTC>-pid<pid>.cmds`, unique per start for
the same reason the logs are (LESSONS 2026-07-28), UTF-8 without a BOM (§4.1),
and ignored by git.

### 10.6 Running it

```
# start the writer and the panel together (the writer keeps its own console,
# so the typed vocabulary stays available beside the panel)
powershell -ExecutionPolicy Bypass -File bridge\standin_writer\bench_panel.ps1 -Instance <name>

# or attach to a writer already started with -CommandFile <path>
powershell -ExecutionPolicy Bypass -File bridge\standin_writer\bench_panel.ps1 -CommandFile <path>
```

Windows PowerShell 5.1, WinForms out of the .NET Framework already on the host.
**No new dependency.** `-Instance` stays tool-derived: read it back from the
PLCSIM Advanced control panel, never assume it.

### 10.7 What the panel says that the terminal did not

Three facts cost the owner a live session and none of them was written where
they would look. Two are on the panel, permanently:

- **the e-stop circuit boots OPEN**, and nothing closes it until a human does —
  not the HMI, not a link, not a restart. The lamp says which it is, and the
  note says it boots open;
- **the HMI's RESET is the *process* reset** (`HmiResetRequest`) and cannot
  reach an F-latch. The F-side reset is the panel's hold button and nothing
  else (`plc/forklift-safety/SPEC.md` §1.3).

The third — a mode selection refused while a demand stands is **consumed, not
held** — is not this channel and belongs in `RUNBOOK.md` beside the other two;
it is requested in the m5-74 report. It is printed on the panel as well,
because it is the third step of the same recovery.

### 10.8 What the panel must never become

- A writer. It holds no API, no OPC UA and no tag, and adding one would make
  two writers of the same DB (invariant 10).
- A service. No port, no socket, no listener, no remote anything: it is a
  window on the host where the writer already runs.
- A place for logic. It contains no threshold, no interlock, no latch, no
  sequencing and no verdict — the reset band is drawn, not applied, and the
  freshness ages it prints are the age of a log line, not a decision about the
  plant. Every decision remains the F-program's.
- A second copy of the log. It displays the writer's lines; it never writes to
  the log, rewrites it or replaces it.
