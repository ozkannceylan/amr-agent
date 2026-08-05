# The stand-in writer — implementation design

**ENGINEERING STAND-IN.** This process is the simulation's substitute for the
*wiring* of three safety-rated devices that do not exist in this project. It
carries no Category, no PL, no SIL, no PFH, no channel count and no diagnostic
coverage, and nothing in this document claims otherwise (SPEC §1.2 N2–N4,
FIO-FEASIBILITY §6 consequence 1). The word *stand-in* appears in its file
name, its console banner, its log header and every tag it writes.

**Authority.** `plc/forklift-safety/SPEC.md` §7 specifies this process
completely — the rate, the level republish, the four members, the two sources,
the command set, the failure behaviour, the log. This document chooses **how**
to realise §7, never what it does. Where the two disagree, §7 wins and this
document is corrected. ADR 0015 D1 fixes the mechanism (API by tag name, no
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
| Parameters | `-Instance <name>` **mandatory** (tool-derived; read from the PLCSIM Advanced control panel, never assumed — the probe ran on `FIOPROBE`, which is **not** the working project's instance; the working project read back **`safecell3`** on 2026-08-05, m5-25 log, and may change). `-Dll <path>` default `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll` (a read-back from the m5-03 record). `-Port <n>` default `45015` (SPEC §7.2 design value). **The cycle is not a parameter**: 50 ms is settled by §7.1 and a knob would invite drift |
| Concurrency | **Single-threaded, one loop.** No runspace, no job, no timer callback, no background thread. This is load-bearing, not simplicity: the heartbeat may only advance from the same loop iteration that services commands and writes levels, so anything that stalls the process stalls the heartbeat, and §5.4 converts that into a latched demand within `STANDIN_STALE_MAX` = 1 s. A second thread that kept the heartbeat alive past a wedged main loop would defeat SPEC §7.3 row 1 |
| Start | Manually, by the operator, from Windows PowerShell 5.1: `powershell -ExecutionPolicy Bypass -File bridge\standin_writer\standin_writer.ps1 -Instance <name>`. Start order against the CPU, the WSL bridge and the HMI is irrelevant — the republish repairs any ordering (§5) |
| Logs | `bridge/standin_writer/logs/standin-writer-<UTC yyyyMMddTHHmmssZ>-pid<pid>.log`, created with `CreateNew` (refuse a collision, never overwrite), `AutoFlush = $true`. One file per session, unique per start (LESSONS 2026-07-28). Add `standin_writer/logs/` to `bridge/.gitignore` |

### 1.1 The write set — exact and closed

The writer writes **exactly four tags** and nothing else, held as one literal
allowlist in one place in the script; every write goes through one helper that
takes the tag name from that list only:

| Tag | Call | Value |
|---|---|---|
| `SafetyInputStandIn.EStopCircuitClosed` | `WriteBool` | operator-owned level |
| `SafetyInputStandIn.ZoneDeviceCircuitClosed` | `WriteBool` | field- or operator-owned level (§3) |
| `SafetyInputStandIn.ResetButtonPressed` | `WriteBool` | operator-owned level |
| `SafetyInputStandIn.StandInHeartbeat` | `WriteInt16` | counter, +1 per cycle, wraps `30000 → 0` |

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

Per §7.1: 50 ms, logged at start-up; **all four members every cycle**, never
write-on-change (a CPU restart reverts the DB and only a republish repairs it,
LESSONS 2026-07-28; a level repair produces no edge).

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
   (`DataAvailable`); parse complete lines; apply `ZONE`/`PING`; then test
   staleness: link up and no well-formed line for **1000 ms**
   (`FIELD_LINK_STALE_MAX`, §7.2) → link down.
3. **Pulse expiry**: if a `reset pulse` is active and its commanded duration
   has elapsed, drive `ResetButtonPressed := FALSE` and log the shaped
   release. This is the one writer-generated actuation §7.2 allows.
4. **Write**: the four tags of §1.1 through the allowlist helper, heartbeat
   incremented **only on a fully successful write cycle** (§5.1). Log one
   `CYCLE` line — the record of the four writes issued this cycle.
5. **Sleep** to the deadline: `t_next = t_start + n × 50 ms` from one
   `Stopwatch`; `Thread.Sleep(max(0, remaining))`. An overrun is logged and
   counted, **never compensated** — no catch-up burst, no skipped-cycle
   logic. Windows timer granularity (~15 ms) is jitter the design absorbs:
   `STANDIN_STALE_MAX` = 1 s is twenty cycles of headroom (SPEC §3.3).

**Timers, exhaustively.** The writer owns three timers and no fourth: its own
50 ms cycle, the staleness of its **own input channel** (the field link), and
the operator-commanded pulse width. All three are fixed by SPEC §7. None
watches the plant, none debounces a signal, none delays a value — a timer over
plant state would be a process decision, and those live in the PLC.

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
| Link down | On staleness (> 1000 ms), EOF or socket error: drive `ZoneDeviceCircuitClosed := FALSE`, log the transition, close the socket, and return ownership to the operator — who must issue a deliberate `zone close` to re-close it. Loss of the intrusion source reads as an intrusion, never as a clear field (§7.3 row 2) |

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
terminal value first). Terminal values: all three channels `FALSE` — open,
unpressed, the demand direction — then log `TERMINAL`, `Dispose()`, close the
log. The heartbeat then freezes, `StandInValid` falls within 1 s, and both
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
| Touches | The configured `Input/`/`Output/` groups + `BridgeHeartbeat` | The four members of `SafetyInputStandIn`, which the OPC UA server does not expose at all (SPEC §4.2 step 14) |
| Listens | Never, on anything | One TCP listener, port 45015, for the field evaluation only |
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
| `CYCLE` | Every cycle: `hb=<n> estop=<0/1> zone=<0/1> reset=<0/1>` — the record of the four writes issued (§7.2 "every API write issued"; the one line carries all four) |
| `OPERATOR` | Every console command accepted, with the value |
| `FIELD` | Every `ZONE` line applied, with the value |
| `LINK` | Every field-link state change: up, down (stale/EOF/error), refused second connection |
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

Every check is an observation in the **consumer's view or the watch table**,
never the writer's own read-back (LESSONS 2026-08-04) — the writer has no
read-back to consult by construction (§1.1).

---

## 9. What this process must never do

Restated from `bridge/README.md`'s boundary (which this design amends) so the
coding agent has it on the page they build from:

- No OPC UA, in any role. No ROS 2. No MQTT, no VDA 5050, no fleet, no HMI.
- No write outside the four-tag allowlist of §1.1; no read of any CPU datum
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
