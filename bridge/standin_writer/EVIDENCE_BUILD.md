# Stand-in writer — build verification evidence (m5-37)

**ENGINEERING STAND-IN.** Everything recorded here concerns a process that
stands in for the *wiring* of three safety-rated devices that do not exist in
this project. It carries no Category, no Performance Level, no SIL, no PFH, no
channel count and no diagnostic coverage, and nothing in this file claims
otherwise (`plc/forklift-safety/SPEC.md` §1.2 N2–N4).

**These are build checks, not T6 evidence.** They are the `STANDIN-WRITER-DESIGN.md`
§8 acceptance list, run to prove the script works. Nothing here closes a gate
criterion, an acceptance test or an SRS item (SPEC §8 N5).

---

## §0 Environment — read back, not assumed

| Item | Read-back value | How it was read |
|---|---|---|
| Host | Windows 11, Windows PowerShell 5.1 | the shell the script runs in |
| PLCSIM Advanced API DLL | `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll` | `Test-Path` → `True` |
| API version | `0x70000` = 7.0 | `SimulationRuntimeManager::Version` |
| Registered instances | id 0 `FIOPROBE`, id 1 `safecell3` | `SimulationRuntimeManager::RegisteredInstanceInfo` |
| **Instance used** | **`safecell3`** — the working project's instance, **not** the probe's `FIOPROBE` | read back from the registered-instance list and confirmed by its tag set (`ForkliftControl_DB`, `ForkliftSafetyMirror`, `InstF_Forklift_Safety` all present) |
| `OperatingState` | `Run` | `IInstance.OperatingState` |
| Live tag count | 185 | `UpdateTagList()` + `TagInfos` |
| Int16 write call | `void WriteInt16(string in_Tag, int16 in_Value)` | `$inst \| Get-Member Write*` — the 16-bit **signed** call the design requires; the DB member's type was not changed to fit the API |
| `Global\` mutex creation | permitted (session is elevated) | probe mutex created and released |

### §0.1 Build state at the start of this task — the S015 delta had NOT landed

Read from the live tag list at 2026-08-05, before any writer run:

```
SafetyInputStandIn                               DB
SafetyInputStandIn.EStopCircuitClosed          Bool
SafetyInputStandIn.ZoneDeviceCircuitClosed     Bool
SafetyInputStandIn.ResetButtonPressed          Bool
```

`SafetyInputStandIn.StandInHeartbeat` was **absent**, and
`InstF_Forklift_Safety` carried the fourteen-network statics only —
no `HeartbeatChanged`, `HeartbeatSeen`, `StandInValid` or `HeartbeatMemory`.
The owner was landing the delta in TIA Portal while this build ran. Every
check below records which build it ran against.

---

## §1 Run A — 2026-08-05T17:31:51Z — against the PRE-delta build

Log: `logs/standin-writer-20260805T173151Z-pid5928.log` (per-session, unique
per start, `CreateNew`). Instance `safecell3`, `OperatingState = Run`.

Everything in this run that does **not** need `StandInHeartbeat` is proven
here; everything that does is deferred to run B, after the delta.

### A1 — double start refused (design §8 check 1)

A second invocation while the first held the mutex:

```
exit code 3
STAND-IN WRITER refused to start: the mutex Global\amr-standin-writer is already held,
so a stand-in writer is already running on this host. ... Nothing was touched: no log
file, no API contact.
```

The `logs/` directory still held exactly one file afterwards, and the refused
process reached neither `Add-Type` nor `CreateInterface` — the mutex is
acquired before both.

### A2 — the API-failure path, unfaked (design §5.1, §8 check 5's mechanism)

`SafetyInputStandIn.StandInHeartbeat` did not exist in this build, so the
heartbeat write threw on the first cycle. This is a *real* API failure, not a
simulated one, and the writer took the designed path exactly:

```
17:31:51.730Z | API | write failed: MethodInvocationException: Exception calling
               "WriteInt16" with "2" argument(s): "Error Code: -4, DoesNotExist"
17:31:51.734Z | API | session dropped (write failure); no writes are issued and the
               heartbeat does not advance while disconnected -- at the CPU this is
               writer death, which is the safe direction
17:31:52.738Z | API | reconnect attempt
17:31:52.740Z | API | connected to instance 'safecell3', OperatingState = Run
```

Observed for 2 min 13 s: `cycles=0`, `write-failures=122`, `final heartbeat=0`.
**The heartbeat never advanced past 0** — the counter advances only on a fully
successful write cycle, and one failed member is enough to withhold it. The
reconnect ran once per second and each attempt was logged.

### A3 — the operator console, driven per key from outside (design §4)

Commands were typed into the writer's own console input buffer by
`testing/console_feed.ps1` (`AttachConsole` + `WriteConsoleInput`, addressed by
process id — no focus-dependent input, no GUI automation):

```
17:33:09.824Z | OPERATOR | status -- levels: estop=OPEN zone=OPEN reset=released |
               heartbeat=0 | field link down (operator owns the zone channel) |
               API DISCONNECTED | cycles=0 overruns=1 write-failures=72
17:33:10.402Z | OPERATOR | estop close -> EStopCircuitClosed := True
17:33:10.859Z | REFUSED  | 'reset pulse x': the pulse width must be an integer number
               of milliseconds
17:33:11.243Z | REFUSED  | 'wibble': unrecognised command. ...
```

`status` reads nothing from the CPU and writes nothing. Both refusals are
logged, never silent (design §8 check 8's `REFUSED` half).

### A4 — the field link, whole (design §3; SPEC §7.2)

Fed by `testing/field_feed.ps1`, a throwaway line feeder — **not** the field
evaluation, and satisfying nothing in criterion (a)'s intrusion chain:

```
17:33:30.193Z | LINK    | up: field-evaluation client 127.0.0.1:50828 connected; the
                zone channel now belongs to the field and is held FALSE until its
                first ZONE line -- a link with no verdict yet is not a clear field
17:33:30.750Z | FIELD   | ZONE 1 -> ZoneDeviceCircuitClosed := True  (field clear)
17:33:31.749Z | LINK    | refused a second connection: one field-evaluation client
                at a time
17:33:32.791Z | REFUSED | 'zone close': the field-evaluation link is up and owns the
                zone channel; one channel, one source at any moment
17:33:33.191Z | FIELD   | ZONE 0 -> ZoneDeviceCircuitClosed := False (intrusion)
17:33:34.188Z | FIELD   | ZONE 1 -> ZoneDeviceCircuitClosed := True
17:33:35.246Z | REFUSED | field link: malformed line 'GARBAGE LINE' -- it refreshes
                nothing; bytes are not proof of a live verdict
17:33:36.350Z | LINK    | down (stale: no well-formed line for 1000 ms);
                ZoneDeviceCircuitClosed driven FALSE (open) and ownership of the zone
                channel returns to the operator
```

Six design rules observed in one capture: the held-FALSE-until-first-verdict
rule, the `ZONE` digit = circuit level encoding, the single-client rule, the
operator refusal while the link is up, garbage refreshing no clock, and the
1000 ms staleness driving the channel **open**.

### A5 — the terminal write, in its failure form (design §5.4)

`quit` was issued while the writer happened to be inside a disconnected
window (the DoesNotExist cycle), so the terminal write could not be issued and
said so rather than pretending:

```
17:34:04.447Z | OPERATOR | quit
17:34:04.449Z | TERMINAL | FAILED: no API session at exit, so the terminal write could
                not be issued. Death-by-staleness covers it: ...
17:34:04.451Z | EXIT     | reason=quit cycles=0 overruns=1 write-failures=122
                final heartbeat=0
```

The success form is run B check 7.

### A6 — the CPU left as found

Read back after the run: `EStopCircuitClosed` had been left `True` by the last
partially-successful cycle (the three Bools land before the heartbeat call
throws). It was restored to `False` by a one-shot read-back-and-restore, and
the three channels read `False, False, False` afterwards — the as-found state.
Both demands and `SafetyResetRequired` stood latched throughout, which is
correct for a build with both circuits open.

---

## §2 Two findings from the environment, recorded because they cost time

### F1 — the second witness is live and is on a different stack

`plc/forklift-safety/evidence/m5-03b-opcua-witness.py` was run read-only from
the WSL venv (`asyncua 2.0.1`) against `opc.tcp://192.168.53.1:4840`:

```
# OPC UA witness on opc.tcp://192.168.53.1:4840
# columns: EStopDemand, ZoneStopDemand, SafetyResetRequired, SafetyResetFault, ForkliftResetRequired
19:44:10.801  11101  baseline
# 6691 polls over 5 s, final 11101
```

Both demands and `SafetyResetRequired` stand, `SafetyResetFault` clear — the
correct reading of a build whose stand-in circuits are open. This witness
**cannot see `SafetyInputStandIn`**, so nothing it reports can be an echo of
the writer's process image; it is available for run B.

### F2 — `CreateInterface` / `Dispose` churn faults the API assembly

A polling harness that created and disposed an `IInstance` once every 20 s
died with:

```
System.AccessViolationException: Attempted to read or write protected memory.
   at Siemens.Simatic.Simulation.Runtime.CInstanceNet.!CInstanceNet()
   at ...CInstanceNet.Dispose()
```

The fault is in the API assembly's own finalizer, not in caller code, and it
is a **harness** observation: the writer creates one interface and holds it,
and disposes only on a write failure. Run A survived 122 such
disconnect/reconnect rounds without it. It is recorded because any future
tool that polls this API in a create/dispose loop will hit it — hold one
interface instead.

---

## §3 Run B — DEFERRED: the S015 delta had not landed when this build ended

`SafetyInputStandIn.StandInHeartbeat` was still absent from the live tag list
after 45 minutes of polling at 20 s intervals (`state=Run`, `tags=185`
unchanged throughout). Everything in `STANDIN-WRITER-DESIGN.md` §8 that reads
`StandInHeartbeat`, `HeartbeatSeen` or `StandInValid` therefore **has not been
observed** and is stated as unproven rather than assumed:

| §8 check | Status |
|---|---|
| 1 double start refused | **proven**, run A §1 A1 |
| 2 belief: heartbeat advances, `StandInValid` → TRUE | **not run** — the tag does not exist |
| 3 the cell starts: `estop close`/`zone close`/reset → demands clear | **not run** — needs `StandInValid` TRUE |
| 4 typing does not starve the heartbeat | **not run** — needs the heartbeat |
| 5 death converts to a demand | **not run** — needs `StandInValid` |
| 6 rebirth restores belief, not motion | **not run** — needs `StandInValid` |
| 7 terminal write, success form | **not run**; the *failure* form is proven, run A §1 A5 |
| 8 zone/refusal shapes | **proven**, run A §1 A3 and A4 |

The mechanism each unrun check exercises is nevertheless exercised in run A by
a different route: the counter-withholding rule and the reconnect path by A2,
the console non-blocking read by A3 (four commands accepted while the loop
kept cycling), the terminal write by A5.

**What run B is, when the delta lands.** Start the writer, run the eight
checks with `testing/observe_consumer.ps1` reading the consumer's view and the
OPC UA witness of F1 running beside it, and append the capture here as §3.

---

## §4 Cadence under real API write cost — measured, not reasoned

The one heartbeat-critical property that could be measured without
`StandInHeartbeat` is whether a 50 ms deadline-scheduled loop holds while
issuing real API writes. Probe: the writer's exact scheduler, republishing the
three channels that exist in this build at their as-found `FALSE`, 400 cycles
(20 s), instance `safecell3`, `OperatingState = Run`. It left the DB exactly
as found.

```
cycles=400  overruns=0
3-write cost ms : median 1.40  p95 1.92  max 10.41
achieved period ms: median 47.02  p95 62.94  max 64.21  min 44.88
```

Reading it: three writes cost **1.40 ms median**, so the fourth (`WriteInt16`,
one more call of the same class) leaves the write phase around 2 ms of a 50 ms
budget. **No cycle missed its deadline in 400.** The period spread — 44.9 to
64.2 ms around a 50 ms anchor — is Windows `Thread.Sleep` granularity
(~15.6 ms), which the deadline anchor absorbs without drift rather than
compensating for; `STANDIN_STALE_MAX` = 1 s is twenty cycles of headroom, so
the widest observed period is 6 % of the window the F-program allows.

This is a **timing sample from one 20 s run on one machine**, not a bound
(LESSONS 2026-08-04, 2026-08-05): the design property it demonstrates — the
write phase is small against the cycle and the anchor does not drift — will
reproduce; the individual millisecond figures are one draw.

---

## §5 How to start it — the whole procedure

From **Windows PowerShell 5.1** on the host running PLCSIM Advanced, in its
own console window (the operator console is read per key, so it needs one):

```
powershell -ExecutionPolicy Bypass -File bridge\standin_writer\standin_writer.ps1 -Instance safecell3
```

`-Instance` is mandatory and is a **tool-derived** value: `safecell3` is what
this project's instance read back as on 2026-08-05, and it is read from the
PLCSIM Advanced control panel rather than taken from this file. Start order
against the CPU, the WSL bridge and the HMI is irrelevant — the level
republish repairs any ordering.

Getting the cell moving (SPEC §9.1 T6.0.1–T6.0.4, the operator form):

```
estop close
zone close
reset press          ... wait about a second ...
reset release        -> both demands clear, SafetyResetRequired -> FALSE
```

then enable and drive from the HMI as in M4. `quit` (or Ctrl+C) writes all
three channels FALSE and only then falls silent.

**Watch out for one thing.** Until `SafetyInputStandIn.StandInHeartbeat`
exists in the downloaded build, every cycle will log

```
API | write failed: ... "Error Code: -4, DoesNotExist"
```

once per second and the heartbeat will stay at 0. That is not a writer
defect: it is the S015 delta not being in the CPU. The three channel levels
still land, so the T6.0 sequence above will still clear the demands on a
pre-delta build — but nothing is validating the stand-in's liveness, which is
the whole point of the delta.

## §6 State the CPU was left in

Read back after the last run, instance `safecell3`, `OperatingState = Run`:

```
SafetyInputStandIn.EStopCircuitClosed         False
SafetyInputStandIn.ZoneDeviceCircuitClosed    False
SafetyInputStandIn.ResetButtonPressed         False
InstF_Forklift_Safety.EStopDemand             True
InstF_Forklift_Safety.ZoneStopDemand          True
InstF_Forklift_Safety.SafetyResetRequired     True
InstF_Forklift_Safety.SafetyResetFault        False
```

The as-found state: three channels open/unpressed, both demands correctly
latched, no reset fault. No writer process was left running and nothing was
listening on port 45015. Nothing was downloaded, no program was changed and
no project was touched at any point in this build.

The delta poll ran from 19:35 to 20:37 local (about 62 minutes, 15–20 s
interval) and reported `state=Run tags=185 hb=False` unchanged throughout.
