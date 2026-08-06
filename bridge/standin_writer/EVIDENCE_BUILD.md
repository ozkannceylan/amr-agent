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

## §3 Run B — RUN on 2026-08-05T23:10Z, against the POST-delta build (m5-41)

> Written as each observation landed, not at the end. The §3 table that
> follows the capture is the run-A deferral list, updated in place.

### B0.0 — the captures, all of them

Every file named in §3 lives in `bridge/standin_writer/evidence/`. The writer's
own session logs are per-session run artefacts under `logs/` (gitignored); the
three from this run are copied out under dated names, the short one in full and
the two long ones with their `CYCLE` lines stripped.

| File | What it is |
|---|---|
| `m5-41-B1-consumer.log` / `-witness.log` | B1 belief + B2 start sequence + B3 re-assert |
| `m5-41-B4-consumer.log` / `-witness.log` | B4 unplanned writer death |
| `m5-41-B5-rebirth-consumer.log` | B5 restart |
| `m5-41-B6-consumer.log` / `-witness.log` | B6 second start sequence, slow typing, commanded kill |
| `m5-41-B7-consumer.log` | B7 terminal write |
| `m5-41-timers-ForkliftControl_DB.log`, `m5-41-timers-InstF_Forklift_Safety.log` | §3.2, all four members of every timer |
| `m5-41-writer-session-2026-08-05-pid37312.log` | the B7 writer session, complete |
| `…-pid34844-events.log`, `…-pid5340-events.log` | the B1–B6 writer sessions, `CYCLE` lines stripped |
| `m5-41-B*-witness.err` | the asyncua session-timeout grant line, kept because the grant is `min(request, cap)` and is read back, never assumed |

New read-only scaffolding built for this run, both in `testing/`:
`opcua_witness.py` (§B0.1) and `read_timers.ps1` (§3.2). Neither writes
anything. `observe_consumer.ps1` gained four columns — `StandInStaleTimer.Q`
and the three validated channels — so B4 onward carry 21 bits where B1–B3 carry
17; each capture prints its own column list.

### B0 — the build the run ran against, read back

`SafetyInputStandIn.StandInHeartbeat` **exists**. Live tag list, instance
`safecell3`, `OperatingState = Run`, **199 tags** (185 before the delta):

```
SafetyInputStandIn.EStopCircuitClosed          Bool
SafetyInputStandIn.ZoneDeviceCircuitClosed     Bool
SafetyInputStandIn.ResetButtonPressed          Bool
SafetyInputStandIn.StandInHeartbeat            Int      <-- the S015 delta
InstF_Forklift_Safety.HeartbeatChanged         Bool
InstF_Forklift_Safety.HeartbeatSeen            Bool
InstF_Forklift_Safety.StandInValid             Bool
InstF_Forklift_Safety.HeartbeatMemory          Int
InstF_Forklift_Safety.StandInStaleTimer.{IN,PT,Q,ET}
InstF_Forklift_Safety.EStopClosedValid         Bool
InstF_Forklift_Safety.ZoneClosedValid          Bool
InstF_Forklift_Safety.ResetPressedValid        Bool
```

### B0.1 — the witness, re-established before anything was trusted

The run-A witness (`m5-03b-opcua-witness.py`) addresses the mirror as
`ns=3;s="ForkliftSafetyMirror"."EStopDemand"` — a NodeId in the CPU's own
auto-published namespace, whose `DataBlocksGlobal` folder this server
**no longer publishes at all** (`m5-25b-f-absence-2026-08-05.log`). So the
witness path was re-established from scratch rather than assumed:

| Question | Answer, read back |
|---|---|
| Does the browse path of `opcua-nodes.md` §11.2 serve the mirror? | **Yes.** `Objects/ServerInterfaces/DemoCell/Forklift/Safety/{EStopDemand, ZoneStopDemand, SafetyResetRequired, SafetyResetFault}` browses and reads. This is the witness used below (`testing/opcua_witness.py`, new) |
| Does the old `ns=3` NodeId form still resolve, with `DataBlocksGlobal` unbrowsable? | **Yes** — `ns=3;s="ForkliftSafetyMirror"."EStopDemand"` → `True`, `ns=3;s="ForkliftStatus"."ForkliftResetRequired"` → `True`. **Unbrowsable is not unaddressable** for a string NodeId; the run-A witness would still have worked. Recorded because the opposite was the working assumption |
| Is the absence of the F-side and the stand-in DB an absence of *browse*, or of the address space? | **Of the address space.** Read by direct NodeId, `SafetyInputStandIn.EStopCircuitClosed`, `.StandInHeartbeat`, `InstF_Forklift_Safety.StandInValid`, `.HeartbeatSeen` and `.EStopDemand` all return **`BadNodeIdUnknown`** — "does not exist in the server address space" — not `BadNotReadable`. The m5-25b claim is stronger than its browse sweep proved |

**What no witness can see, stated rather than papered over.**
`HeartbeatSeen` and `StandInValid` are members of `InstF_Forklift_Safety`,
which is on **no** client's address space (above). There is therefore **no
OPC UA witness for them and none was invented.** They are read where the brief
directs: from the F-block's own instance data, by
`testing/observe_consumer.ps1`, **a separate process** — a different memory
location from the four `SafetyInputStandIn` members the writer writes, and
never the writer's own read-back (the writer has none, by construction).
The OPC UA witness runs beside it on the consequence — the four
`ForkliftSafetyMirror` values — and cannot echo anything written.

### B1 — belief: the single observation everything was waiting on (design §8 check 2)

Observer started first, writer started 4 s into its window. Columns as the
observer prints them; only the ones that move are named here.

```
        t_ms  .................   hb        note
        33.3  00000000011101110   0 0       baseline
     4,385.5  00000011111101110   3 3       CHANGE
     5,075.1  00000011111101110   17 15     tick
    40,133.2  00000011111101110   718 718   tick
```

Reading the CHANGE, bit by bit:

| Bit | Tag | baseline | after |
|---|---|---|---|
| 6 | `InstF_Forklift_Safety.HeartbeatChanged` | 0 | **1** |
| 7 | `InstF_Forklift_Safety.HeartbeatSeen` | 0 | **1** |
| 8 | `InstF_Forklift_Safety.StandInValid` | 0 | **1** |
| 9,10,11 | `EStopDemand`, `ZoneStopDemand`, `SafetyResetRequired` | 1,1,1 | **1,1,1 — unchanged** |

**`HeartbeatSeen` and `StandInValid` are TRUE, observed, in the consumer's
view.** The heartbeat advances (`hb` 3 → 718 over 40 s; `HeartbeatMemory`
tracks it one cycle behind), and **both demands stay latched** — belief is not
motion, which is design §8 check 2 in full.

The transition is 385 ms after the `Start-Process` call that launched the
writer, and that interval contains PowerShell start-up, `Add-Type`,
`CreateInterface` and `UpdateTagList` as well as the F-program's own
recognition. **It is a single draw and is not a latency figure for anything**
(LESSONS 2026-08-05); the design's "≈150 ms of the first republish" is neither
confirmed nor refuted by it, because the first republish was not separately
timed.

Command that produced it:

```
powershell -ExecutionPolicy Bypass -File bridge\standin_writer\standin_writer.ps1 -Instance safecell3
powershell -ExecutionPolicy Bypass -File bridge\standin_writer\testing\observe_consumer.ps1 -Instance safecell3 -Duration 75 -TickSeconds 5
python bridge\standin_writer\testing\opcua_witness.py 70
```

Captures: `evidence/m5-41-B1-consumer.log`, `evidence/m5-41-B1-witness.log`.

### B2 — the cell starts: circuits close, nothing clears; the reset clears on release (design §8 check 3)

Same observer window, commands fed into the writer's own console by
`testing/console_feed.ps1` (`WriteConsoleInput`, addressed by process id).

```
    44,720.4  10000011111101110   810 808   CHANGE   estop close  -> SafetyInputStandIn.EStopCircuitClosed
    44,785.3  10010011111101110   811 811   CHANGE                   InstF_...EStopCircuitClosed follows      (+64.9 ms)
    46,223.7  11010011111101110   840 839   CHANGE   zone close   -> SafetyInputStandIn.ZoneDeviceCircuitClosed
    46,318.3  11011011111101110   842 842   CHANGE                   InstF_...ZoneDeviceCircuitClosed follows (+94.6 ms)
    48,740.6  11111011111101110   890 889   CHANGE   reset press  -> SafetyInputStandIn.ResetButtonPressed
    48,784.0  11111111111101110   891 891   CHANGE                   InstF_...ResetButtonPressed follows      (+43.4 ms)
    49,897.3  11011111111101110   914 912   CHANGE   reset release-> ResetButtonPressed FALSE (held 1,156.7 ms)
    49,923.1  11011011100001110   914 914   CHANGE   EStopDemand, ZoneStopDemand, SafetyResetRequired ALL -> 0 (+25.8 ms)
    49,945.2  11011011100000000   914 914   CHANGE   the four ForkliftSafetyMirror bits follow                (+22.1 ms)
```

Three things are observed here and each is separately load-bearing:

1. **Closing both circuits cleared no demand.** Bits 9/10/11 stay `1,1,1`
   from 44.7 s to 49.9 s with both circuits closed. A stop is not undone by
   its cause going away (CLAUDE.md §9 restart behaviour).
2. **The press cleared nothing either** — bits 9/10/11 still `1,1,1` for the
   whole 1,156.7 ms hold.
3. **Both demands cleared on the RELEASE**, 25.8 ms after it. The monitored,
   edge-triggered reset runs on this build.

Independent witness, same events, different protocol stack:

```
23:10:23.716  1110  baseline      EStopDemand, ZoneStopDemand, SafetyResetRequired set
23:11:13.845  0000  CHANGE        all clear
```

### B3 — a circuit reopening re-asserts, and only its own demand

```
    60,776.0  11001011110100000  1131 1130 CHANGE   estop open -> EStopDemand 1, SafetyResetRequired 1,
                                                    ZoneStopDemand stays 0
    60,809.1  01001011110101010  1132 1130 CHANGE   the mirror follows                        (+33.1 ms)
    63,854.3  11001011110101010  1193 1191 CHANGE   estop close -> circuit closed again
    63,909.7  11011011110101010  1194 1193 CHANGE   InstF_...EStopCircuitClosed follows       (+55.4 ms)
                                                    demands stay 1,0,1 -- closing does not clear
```

Witness: `23:11:24.690  1010  CHANGE` — `EStopDemand` set, `ZoneStopDemand`
still clear, `SafetyResetRequired` set. **Reopening one circuit re-asserts
that circuit's demand and not the other's**, and closing it again does not
clear the latch.

**One honest note on the 60,776.0 row.** The observer's sample is 17 `ReadBool`
calls plus two `ReadInt16`, **not atomic**, so a line that spans a transition
can read torn: this one shows `SafetyInputStandIn.EStopCircuitClosed` still `1`
while the F-side copy already reads `0`. The next line, 33 ms later, is
consistent. Only the sequence across lines is evidence; no single line is.

### B4 — the fail-safe direction: the heartbeat freezes and both demands latch (design §8 check 5)

**How this one arose, stated plainly because it matters.** The writer process
**terminated abruptly at 21:13:35.953Z** — its log ends mid-`CYCLE` at
`hb=3757` with **no `TERMINAL` and no `EXIT` line**, so it was killed rather
than exited, and the commanded kill in the same script had not yet run. The
cause is not established (§3.3 F3). It is recorded as what it is: an
**unplanned writer death**, which is exactly SPEC §7.3 row 1's case, and the
F-program's response was captured in full because the observer was already
running.

Observer columns changed for this run: `StandInStaleTimer.Q` and the three
**validated** channels were added, because they are the whole point of S015.

```
        t_ms  .....................   hb        note
        31.0  110110111011010101010   3704 3703 baseline   writer alive, both circuits closed
     2,783.9  110110011011010101010   3757 3757 CHANGE     HeartbeatChanged -> FALSE, hb frozen at 3757
     3,808.6  110110010100011101010   3757 3757 CHANGE     StandInValid -> FALSE, StandInStaleTimer.Q -> TRUE,
                                                           EStopClosedValid -> FALSE, ZoneClosedValid -> FALSE,
                                                           ZoneStopDemand -> TRUE
     3,835.4  110110010100011101110   3757 3757 CHANGE     the mirror follows                      (+26.8 ms)
    25,119.4  110110010100011101110   3757 3757 tick       held for the remaining 21 s
```

- **Heartbeat frozen → validity lost.** `HeartbeatChanged` FALSE at 2,783.9 ms,
  `StandInValid` FALSE at 3,808.6 ms: **1,024.7 ms**, against
  `StandInStaleTimer.PT` = `T#1S` read in force plus one 100 ms F-OB. One draw,
  not a bound.
- **Both demands latch.** `EStopDemand` and `SafetyResetRequired` were already
  set from B3; `ZoneStopDemand` joins them at the same instant. All three then
  stand for the rest of the window.
- **This is the S015 check visibly doing its work.** Bits 0/1 (the raw
  channels, frozen at the writer's last write) read `1,1` — closed — while
  bits 10/11 (the validated channels) read `0,0`. The raw and the validated
  rows **differ exactly when `StandInValid` is FALSE and a channel is closed**,
  which is what `plc/forklift/TIA-BUILD-PROCEDURE.md` step 187 says cannot be
  seen until a writer exists.

Independent witness, different protocol stack, same event:

```
23:13:33.150  1010  baseline
23:13:37.130  1110  CHANGE      ZoneStopDemand joins the latch
```

Capture: `evidence/m5-41-B4-consumer.log`, `evidence/m5-41-B4-witness.log`.

### B5 — rebirth restores belief, not motion (design §8 check 6)

The writer was restarted (fresh log name `standin-writer-20260805T211547Z-pid5340.log`,
`CreateNew`, so the earlier session's file is intact).

```
        t_ms  .....................   hb        note
        28.5  110110010100011101110   3757 3757 baseline  dead-writer state: raw 1,1 / validated 0,0
     4,260.5  000110010100011101110      1 3757 CHANGE    the writer's boot republish drives all three
                                                          channels open; heartbeat restarts at 1
     4,334.2  000000111000011101110      3    2 CHANGE    HeartbeatChanged, HeartbeatSeen, StandInValid
                                                          -> TRUE; demands stay 1,1,1
    30,018.5  000000111000011101110    516  515 final
```

**Belief comes back; the latches do not.** `StandInValid` TRUE again with
`EStopDemand`, `ZoneStopDemand` and `SafetyResetRequired` all still set — they
are cleared only by a fresh monitored reset. The boot republish drives the
three channels **open**, so the restored cell asks for a deliberate operator
action rather than resuming from the state the dead writer left behind.

Note `HeartbeatSeen` read TRUE throughout the dead window (baseline bit 7),
while `StandInValid` read FALSE: `HeartbeatSeen` is the latched "life has been
seen at least once" memory and `StandInValid` is the live verdict. They are
different questions and the build answers them differently.

Capture: `evidence/m5-41-B5-rebirth-consumer.log`.

### B6 — the whole shape again on a second writer instance, then a *commanded* kill (design §8 checks 3, 4, 5)

One 34 s window, one writer session (pid 5340), everything in order. This is a
**second independent instance** of the start-and-reset sequence, run because a
criterion-relevant observation made once is one draw (LESSONS 2026-08-05).

```
        t_ms  .....................   hb        note
        34.5  000000111000011101110   1948 1946 baseline  channels open, StandInValid TRUE, demands 1,1,1
     3,234.9  100000111000011101110   2012 2010 CHANGE    estop close -> raw channel
     3,292.0  100100111010011101110   2013 2012 CHANGE    F copy AND EStopClosedValid follow    (+57.1 ms)
     4,406.4  110100111010011101110   2035 2033 CHANGE    zone close -> raw channel
     4,427.7  110110111011011101110   2036 2035 CHANGE    F copy AND ZoneClosedValid follow     (+21.3 ms)
     5,912.8  111110111011011101110   2065 2064 CHANGE    reset press -> raw channel
     5,982.2  111111111011111101110   2067 2066 CHANGE    F copy AND ResetPressedValid follow   (+69.4 ms)
                                                          demands still 1,1,1 through all of the above
     7,110.4  110110111011000001110   2089 2089 CHANGE    reset release (held 1,197.6 ms):
                                                          EStopDemand, ZoneStopDemand, SafetyResetRequired -> 0
     7,134.2  110110111011000000000   2090 2089 CHANGE    the mirror follows                    (+23.8 ms)
    -- slow typing: six keys at one per second, 6.1 s from first key to Enter --
    10,077.9  110110111011000000000   2148 2147 tick
    15,090.1  110110111011000000000   2249 2248 tick
    16,349.3  110110011011000000000   2270 2270 CHANGE    Stop-Process -Force: HeartbeatChanged -> FALSE
    17,359.5  110110010100011100000   2270 2270 CHANGE    StandInValid -> FALSE, StaleTimer.Q -> TRUE,
                                                          EStopClosedValid / ZoneClosedValid -> FALSE,
                                                          all three demands -> TRUE
    17,379.9  110110010100011101110   2270 2270 CHANGE    the mirror follows                    (+20.4 ms)
    30,136.0  110110010100011101110   2270 2270 tick      held
```

Witness, independently:

```
23:17:25.477  1110  baseline
23:17:32.771  0000  CHANGE     the reset clears both demands
23:17:43.019  1110  CHANGE     the commanded kill latches them again
# 75608 polls over 32 s, final 1110
```

What this window closes:

- **Check 3, second instance.** Both circuits closed and the reset held for
  1,197.6 ms cleared nothing until the **release**, and the validated channels
  track the raw ones one F-cycle behind *while* `StandInValid` is TRUE — the
  positive half of S015, where B4 showed the negative half.
- **Check 4 — typing does not starve the heartbeat.** Six keys at one per
  second, **6.1 s** from first key to Enter, entirely inside the 7.1 s → 16.3 s
  span: **no CHANGE line in it**, `StandInValid` stayed TRUE, and the heartbeat
  advanced ~101 counts per 5 s tick, i.e. the full 20 Hz. The non-blocking
  per-key read is observed, not asserted.
- **Check 5 — a commanded kill converts to a demand.** `Stop-Process -Force`,
  not `quit`. `HeartbeatChanged` FALSE at 16,349.3 ms, `StandInValid` FALSE at
  17,359.5 ms: **1,010.2 ms**, a second draw beside B4's 1,024.7 ms against
  `StandInStaleTimer.PT` = `T#1S`. Both demands latch, and the raw channels
  read `1,1` closed while the validated channels read `0,0` — the S015
  signature again.

Capture: `evidence/m5-41-B6-consumer.log`, `evidence/m5-41-B6-witness.log`.

### B7 — the terminal write, success form (design §8 check 7, §5.4)

Third writer session (pid 37312). Both circuits were closed first, so the
terminal write had something to drive.

```
        t_ms  .....................   hb        note
        40.0  110110010100011101110   2270 2270 baseline  dead-writer state from B6
     3,382.7  010110010100011101110      1 2270 CHANGE    boot republish; heartbeat restarts at 1
     3,416.8  000000111000011101110      2    2 CHANGE    StandInValid -> TRUE (third instance)
     6,774.3  100000111000011101110     69   67 CHANGE    estop close
     6,842.9  100100111010011101110     71   70 CHANGE    F copy + EStopClosedValid              (+68.6 ms)
     7,968.1  100100111011011101110     93   92 CHANGE    ZoneClosedValid
     8,001.4  110110111011011101110     94   92 CHANGE    zone channel fully closed
     9,971.1  000110111011011101110    132  132 CHANGE    QUIT: all three channels written FALSE,
                                                          heartbeat still 132 and the writer still alive
    10,051.6  000110011000011101110    132  132 CHANGE    HeartbeatChanged FALSE; EStopClosedValid and
                                                          ZoneClosedValid FALSE -- while StandInValid is
                                                          STILL TRUE, because the channels are genuinely open
    10,081.8  000000011000011101110    132  132 CHANGE    the F copies follow the open channels
    11,082.0  000000010100011101110    132  132 CHANGE    StandInValid -> FALSE, StaleTimer.Q -> TRUE
                                                          (+1,030.4 ms after the heartbeat froze)
    25,133.3  000000010100011101110    132  132 tick      held
```

Writer log, the last three lines of the session:

```
21:19:09.422Z | OPERATOR | quit
21:19:09.432Z | TERMINAL | all three channels written FALSE (open, unpressed, the demand direction)
                           before falling silent; the heartbeat now freezes and both demands latch
                           on channels already open
21:19:09.441Z | EXIT     | reason=quit cycles=132 overruns=2 write-failures=0 final heartbeat=132
```

**The terminal write happens first and the silence second, and the order is
visible in the consumer's view**: the channels go open at 9,971.1 ms with the
writer still alive and `StandInValid` still TRUE, and only 1,030.4 ms later
does validity fall. Both demands therefore latch **on channels already open** —
there is no ambiguity about why the cell stopped, which is the whole point of
§5.4. `write-failures=0` across the session; 132 cycles in ≈6.6 s is the 20 Hz
cadence, with 2 overruns.

Capture: `evidence/m5-41-B7-consumer.log`; log
`logs/standin-writer-20260805T211902Z-pid37312.log`.

---

## §3.1 Run B — the run-A deferral list, closed or still open

The run-A table listed six of the eight `STANDIN-WRITER-DESIGN.md` §8 checks as
**not run**, each blocked on `SafetyInputStandIn.StandInHeartbeat` not existing.
It exists (B0). Every row is now settled, and each names the capture that
settles it:

| §8 check | Status after run B |
|---|---|
| 1 double start refused | **proven**, run A §1 A1. Not re-run; the mechanism did not change |
| 2 belief: heartbeat advances, `StandInValid` → TRUE | **RUN — proven**, B1, and again at B5 and B7. Three instances |
| 3 the cell starts: `estop close`/`zone close`/reset → demands clear | **RUN — proven**, B2 and again B6. Two instances, both confirmed by the OPC UA witness |
| 4 typing does not starve the heartbeat | **RUN — proven**, B6: 6.1 s from first key to Enter, no CHANGE line in the span, heartbeat at 20 Hz throughout |
| 5 death converts to a demand | **RUN — proven twice**: B4 (unplanned death) and B6 (`Stop-Process -Force`). Freeze-to-invalid 1,024.7 ms and 1,010.2 ms |
| 6 rebirth restores belief, not motion | **RUN — proven**, B5: `StandInValid` TRUE again, all three latches standing |
| 7 terminal write, success form | **RUN — proven**, B7: channels open *while the writer still lives*, validity falls 1,030.4 ms later |
| 8 zone/refusal shapes | **proven**, run A §1 A3 and A4. Not re-run — no field link exists to re-exercise (SPEC §10 open item 9) |

**Still not run, and named rather than glossed:** a CPU stop and restart
repaired by the republish (the design's §8 list does not contain it either; it
would stop a controller the owner has just finished building), and the
field-link *acceptance* path against the real m5-12 evaluation, which does not
exist. Neither is a T6 step.

---

## §3.2 The two `ForkliftControl_DB` timer `PT`s — the open check, answered

`plc/forklift/TIA-BUILD-PROCEDURE.md`'s progress block leaves this open:
`ModeDisagreeTimer.PT` and `StandstillTimer.PT` read `T#0MS` in force while
`VehicleStaleTimer.PT` read its specified `T#500MS`, and the hypothesis was
that the difference is `IN`.

**`IN` was NOT made TRUE for either timer, and the reason is structural, not a
matter of effort.** Both need the bridge writing the forklift group to the live
CPU:

- `StandstillTimer.IN` = `#atStandstill` = `#speedValid AND |speed| < STANDSTILL_SPEED`,
  and `#speedValid` requires `#bridgeLinkOk`, which requires
  **`"ForkliftLink".BridgeHeartbeat`** to be changing.
- `ModeDisagreeTimer.IN` additionally requires `#vehicleAlive`, i.e.
  **`"ForkliftVehicle".ForkliftVehicleHeartbeat`** changing.

`ForkliftLink` is a **different DB** from the M3 cell's `Link` folder, verified
in the live tag list. The committed `bridge/config/bridge.yaml` is cell-only by
its own statement and maps `BridgeHeartbeat` to `["Link","BridgeHeartbeat"]`,
so running it would advance the *cell's* heartbeat and not this one; and
`config/rehearsal-forklift.yaml`, which does carry the forklift group, points at
the PLC logic double on `127.0.0.1:4850` and is labelled "gate evidence does not
run on this file". **No committed configuration maps the forklift group to the
live CPU** — that is exactly the bridge deliverable chunk P lists as missing.
Nothing was improvised to fill it.

**What was done instead, and it settles the question more strongly than one
read with `IN` TRUE would have.** All four members — `IN`, `PT`, `ET`, `Q` — of
**every** timer instance in both DBs were read together
(`testing/read_timers.ps1`, read-only):

```
ForkliftControl_DB                          InstF_Forklift_Safety
timer                IN     PT       ET     timer                IN     PT       ET
BridgeStaleTimer     True   T#500MS  T#500MS   F_IEC_Timer_Instance False  T#0MS    T#0MS
HmiStaleTimer        True   T#600MS  T#600MS   ResetHoldMaxTimer    False  T#3000MS T#0MS
LidarInvalidTimer    False  T#0MS    T#0MS     ResetHoldMinTimer    False  T#200MS  T#0MS
ModeDisagreeTimer    False  T#0MS    T#0MS     StandInStaleTimer    True   T#1000MS T#1000MS
PlantInvalidTimer    False  T#0MS    T#0MS
RequestInvalidTimer  False  T#0MS    T#0MS
StandstillTimer      False  T#0MS    T#0MS
VehicleStaleTimer    True   T#500MS  T#500MS
```

Three things follow, and the third is the one that closes it:

1. **The split is exactly on `IN`, across the whole DB.** All three
   `ForkliftControl_DB` timers with `IN` TRUE hold their specified `PT`; all
   **five** with `IN` FALSE read `T#0MS` — not the two the procedure named.
   A defect confined to two call sites would not paint five.
2. **`PT` is not zeroed by `IN` going FALSE.** `ResetHoldMinTimer` reads
   `T#200MS` and `ResetHoldMaxTimer` reads `T#3000MS` **with `IN` FALSE** —
   because those two timers *have* run, during the reset presses of B2 and B6,
   and the instance kept the `PT` its call site last wrote.
3. Therefore **`T#0MS` means "this timer has never yet run on this build", not
   "a stale `PT` governs".** It is the opposite of the LESSONS 2026-07-28 trap,
   where a *non-zero wrong* value was in force and ruled; here nothing is in
   force because nothing has run, and the call site's value lands the moment it
   does. That the call site's value does land was observed twice in this
   session: `StandInStaleTimer.PT` = `T#1S` produced measured freeze-to-invalid
   intervals of 1,024.7 ms (B4) and 1,010.2 ms (B6).

**What this does not establish.** It does not read `T#2S` or `T#500MS` off
`ModeDisagreeTimer` / `StandstillTimer` — those values remain **design values**
until the timers run. The open check should stay open in that narrow form and
close on the first forklift run with the bridge writing `ForkliftLink`.

Captures: `evidence/m5-41-timers-ForkliftControl_DB.log`,
`evidence/m5-41-timers-InstF_Forklift_Safety.log`.

---

## §3.3 F3 — one writer process died without logging its exit, cause not established

At **21:13:35.953Z** the writer of pid 34844 stopped mid-`CYCLE` at `hb=3757`.
Its log has **no `TERMINAL` and no `EXIT` line**, no `API` line, and the
Windows Application log shows nothing in the window; the commanded
`Stop-Process` in the same script had not yet run and the process was gone
before the next `console_feed` command reached it. The session's other three
writer instances (pid 5340, pid 37312, and 5340 again through five
`console_feed` invocations) were unaffected, so it is **not reproducible from
this session's evidence** and no mechanism is claimed.

It is recorded for two reasons. It cost the planned shape of one test — B4 was
supposed to be a commanded kill and became an observation of an unplanned one,
which is why B6 re-ran it commanded. And it is itself an instance of the
failure the design is built around: an abrupt writer death **converted to a
latched demand within 1,024.7 ms with no operator action**, which is the
correct direction, and the F-program did not need to know why the writer died.

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

**Watch out for one thing — no longer in force, kept for the diagnosis.**
`SafetyInputStandIn.StandInHeartbeat` **exists** in the build as of
2026-08-05 (§B0), so what follows describes a pre-delta controller. Until the
tag exists in the downloaded build, every cycle will log

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

### §6.1 State the CPU was left in after run B (m5-41)

Read back after B7's `quit`, instance `safecell3`, `OperatingState = Run`:

```
SafetyInputStandIn.EStopCircuitClosed         False
SafetyInputStandIn.ZoneDeviceCircuitClosed    False
SafetyInputStandIn.ResetButtonPressed         False
SafetyInputStandIn.StandInHeartbeat             132   (frozen: no writer running)
InstF_Forklift_Safety.StandInValid            False
InstF_Forklift_Safety.HeartbeatSeen            True
InstF_Forklift_Safety.EStopDemand              True
InstF_Forklift_Safety.ZoneStopDemand           True
InstF_Forklift_Safety.SafetyResetRequired      True
InstF_Forklift_Safety.SafetyResetFault        False
ForkliftSafetyMirror.{EStop,ZoneStop,SafetyResetRequired,SafetyResetFault}
                                               True, True, True, False
```

No writer process is running (the `Global\amr-standin-writer` mutex was
acquired and released to prove it), nothing is listening on port 45015.
**Nothing was downloaded, no block was compiled, no program was changed, no
project was opened and no `plc/` file was edited.** Every write in run B went
through the writer's four-tag allowlist; nothing else on the CPU was written by
anything.

**Two differences from the pre-run state, and both are recorded rather than
tidied away:**

1. `SafetyInputStandIn.StandInHeartbeat` reads **132** instead of 0. It is a
   free-running counter left at the last value the writer wrote; frozen is the
   only property that means anything, and it is frozen.
2. `InstF_Forklift_Safety.HeartbeatSeen` reads **TRUE** where the owner's
   invalid-boot signature (procedure step 187) had it FALSE. This is
   **unavoidable and correct**: it is the one-shot "life has been seen at least
   once" latch of SPEC §5.4 V2, and observing it go TRUE was the point of this
   run. Only a CPU STOP → RUN clears it, and stopping the controller was not in
   scope. A reader who repeats step 187 on this CPU will therefore see nine of
   its ten readings and `HeartbeatSeen` TRUE; the tenth returns after a cold
   start.

---

## §7 Runs C–J — the §11.2 speed link (m5-57), 2026-08-06

**Same standing as everything above.** These are build checks of the writer's
§11.2 extension. Nothing here closes a gate criterion, an acceptance test or
an SRS item, and nothing here carries a Category, Performance Level, SIL or
PFH — for the writer or for anything downstream of it. The readings reach the
safety program as **standard data over a stand-in path**.

Written as each observation landed.

### §7.0 The build the runs ran against, read back

Instance `safecell3`, `OperatingState = Run`, **269 tags** (199 at m5-41).
Read from the live tag list before any run — and the writer asks the same
question itself at every connect (`MEMBERS` log class) rather than assuming:

```
SafetyInputStandIn.EStopCircuitClosed          Bool
SafetyInputStandIn.ZoneDeviceCircuitClosed     Bool
SafetyInputStandIn.ResetButtonPressed          Bool
SafetyInputStandIn.StandInHeartbeat            Int
SafetyInputStandIn.SpeedReadingA               Int      <- new, §11.3
SafetyInputStandIn.SpeedReadingB               Int      <- new
SafetyInputStandIn.SpeedSeqA                   Int      <- new
SafetyInputStandIn.SpeedSeqB                   Int      <- new
SafetyInputStandIn.MotionPresent               Bool     <- new
SafetyInputStandIn.MotionObservationValid      Bool     <- new
SafetyInputStandIn.WarningFieldClear           Bool     <- new
```

All eleven present. The F-side statics and both new outputs
(`SpeedMonitorDemand`, `TorqueOffDemand`) were present too, so every run below
could be read **in the consumer's view** rather than in the writer's own.

> Runs C–G ran while the owner was still building. The safety program reached
> 360/360 with collective signature `50573CD9` **after** run G and **before**
> run J1. **Run J1 is the only run below that ran against the finished
> program, and it is the one the link claim rests on.**

### §7.1 What each run was, and where it is

| Run | Writer session | Consumer capture | What it establishes |
|---|---|---|---|
| C1 | pid32084 | — | double start still refused (design §8 check 1) |
| C3 | pid32084 | `m5-57-C3-consumer.log` | the freshness sequences, a channel going silent, the motion silence rule, the three refusal shapes |
| C4 | pid32084 | `m5-57-C4-terminal-consumer.log` | the terminal write, extended form |
| D | pid44496 | `m5-57-D-consumer.log` | `WARN` on the 45015 link, both refusals, the link hang-up |
| E | pid44496 | `m5-57-E-consumer.log` | source reconnect after a hang-up; discrepancy and over-limit terms live |
| F | pid44496 | `m5-57-F-consumer.log` | one monitored reset clearing three latches; the demand re-forming from a fresh discrepancy |
| G | pid44496 | `m5-57-G-terminal-consumer.log` | terminal write, and the `status` line for the new members |
| **J1** | **pid14288** | **`m5-57-J1-consumer.log`** | **the joint run: the real vehicle-side client, the real writer, the finished safety program** |
| R1, R2 | pid14288 | `m5-57-R1/R2-reset-refusal-consumer.log` | two observations of a reset **refused** while the speed world was not clear (§7.8) |
| Z | pid14288 | `m5-57-Z-shutdown-consumer.log` | the shutdown that left the machine as §7.9 records it |

Writer session logs, `CYCLE` lines stripped:
`m5-57-writer-session-2026-08-06-pid{32084,44496,14288}-events.log`.
The first 400 reading-carrying cycles of J1 are kept whole in
`m5-57-J1-writer-cycles-first400.log`, because the per-cycle
`spdA=<value>@<seq>` field is the record of the property this section exists
to prove.

### §7.2 J1 — the joint run, the one that matters

**Both halves real.** The vehicle side is `agv/`'s committed carrier
`safe_speed_link.py` (m5-56) driven by its producer `safe_speed_channels.py`
and the rig's `plant` stimulus, in WSL. The PLC side is this writer on the
Windows host. Nothing was modelled at either end of the seam: the client
dialled the writer's own listener and the writer wrote the CPU's own DB.

The client read the Windows address back from its own default route and
logged it — never taken from a document (ADR 0006):

```
LINK: writer address 172.19.176.1:45016 read back from WSL default route
LINK: up: connected to the stand-in writer at 172.19.176.1:45016 (attempt 1, connection 1)
```

The writer, same seam, same instant:

```
17:36:20.431Z | SPEEDLINK | up: speed-source client 172.19.180.72:50546 connected.
17:36:20.513Z | SPEED | MOT 1 1 -> MotionPresent := True, MotionObservationValid := True
17:36:20.542Z | SPEED | channel A alive: first reading written, SpeedReadingA = 299 mm/s, SpeedSeqA = 1
17:36:20.555Z | SPEED | channel B alive: first reading written, SpeedReadingB = 299 mm/s, SpeedSeqB = 1
```

**The readings reached the F-program's own instance data.** Consumer capture,
`InstF_Forklift_Safety` columns, while the source ran:

```
     t_ms  chainSeen Aval Bval stale  | SI seq     F reading   F SpeedDiff
 18,311.1      1      0    0     1    | 1022/1015   120/200       -80    <- before the source
 21,075.7      1      0    0     1    |    2/2      308/301        +7    <- first readings land
 21,153.5      1      1    1     0    |    3/3      308/301        +7    <- both channels VALID
 30,113.8      1      1    1     0    |  183/183    300/300         0
 54,102.5      1      1    1     0    |  663/663    303/295        +8
```

- **`SpeedAValid` and `SpeedBValid` were TRUE within one F-cycle of the second
  reading**, and `SpeedStaleNow` fell in the same step.
- Over the 686 writer cycles that carried a fresh reading the wire values ran
  **288 … 315 mm/s**, and the F-program's own `SpeedDiff` stayed within
  **±22 mm/s** — inside `SPEED_DISCREPANCY_MAX` = 31 without ever reaching it.
  No discrepancy formed, which is the correct outcome for two healthy channels
  and is the negative half of the discrepancy evidence.
- The two sides' own counts agree: the client reports `sent SPD A 688,
  SPD B 688, MOT 688, PING 33; refused non-finite 0, out-of-range 0`, the
  writer reports `speed cycles A=686 B=686`. The two-line difference is the
  pair in flight when each side stopped.

**And the source going silent reached the CPU as a demand, not as a zero.**
The client shut down at the end of its window and said so:

```
LINK: down (node shutting down). Both freshness sequences stop advancing at
the writer within one of its cycles, and the F-program reads both channels as
missing - a demand, not a zero
```

The writer noticed the hang-up in the same 50 ms cycle
(`17:36:54.844Z | SPEEDLINK | down (the source closed the connection)`),
stopped advancing both sequences, and drove `MotionPresent := TRUE` with
`MotionObservationValid := FALSE`. **`SpeedReadingA` and `SpeedReadingB` were
not written at all** — they still read 300 and 300 in the CPU at the end of
the session, and that is exactly the point: *the value is not the signal, the
sequence is.* `SpeedAValid` and `SpeedBValid` fell and `SpeedStaleNow` rose.

### §7.3 The per-channel freshness rule, isolated (run C3)

A feeder held channel B alive and took channel A silent for 5 s:

```
     t_ms  SeqAChg SeqBChg Aval Bval stale AstaleQ causeGone SPDdemand | SI seq
 16,373.6     1       1     1    1     0      0        1         0     | 215/217
 18,186.2     0       1     0    1     1      1        0         1     | 234/247  <- A alone
 22,406.0     0       1     0    1     1      1        0         1     | 234/313
 22,748.5     1       1     1    1     0      0        1         1     | 238/319  <- A returns
```

- `SpeedSeqA` **froze at 234** while `SpeedSeqB` advanced 247 → 313. One
  channel's silence is one channel's problem; nothing was smoothed.
- `SpeedMonitorDemand` went **0 → 1** on the missing reading and **stayed 1
  after the reading returned** — a latch, cleared only by the monitored reset.
- Later in the same run the source closed entirely: both sequences froze at
  630/708, both channels invalid, and the readings still read 250/250 in the
  DB while meaning nothing to the monitor.

The motion rule, same run:

```
17:10:58.929Z | SPEED | motion observation unavailable (no MOT line for 250 ms)
              -> MotionPresent := TRUE, MotionObservationValid := FALSE
```

and the three refusals, none of which advanced anything:

```
17:11:06.773Z | REFUSED | speed link: 'SPD A 99999' is outside the Int the DB member is
17:11:07.732Z | REFUSED | speed link: malformed line 'SPD A notanumber'
17:11:08.725Z | REFUSED | speed link: malformed line 'HELLO WORLD'
```

> The out-of-Int refusal agrees with `agv/`'s independent decision (m5-56 open
> question 3): a reading that will not fit the S7 `Int` is **refused at both
> ends** rather than clamped or wrapped, so it arrives as *missing*. Neither
> end applies a plausibility window — that is the F-program's, at SL6/SL7.

### §7.4 `WARN` on the field link (run D)

`m5-57-D-consumer.log`, tracking the verdict from the wire to the F-block:

| t_ms | line fed | `SafetyInputStandIn.WarningFieldClear` | `InstF….WarningFieldClear` | `WarningFieldClearValid` |
|---|---|---|---|---|
| 2,133 | `ZONE 1` | 0 | 0 | 0 |
| 3,096 | `WARN 1` | 1 | 1 | 1 |
| 8,142 | `WARN 0` | 0 | 0 | 0 |
| 12,183 | `WARN 1` | 1 | 1 | 1 |
| 22,143 | *link closed* | 0 | 0 | 0 |

`WARN 2` and `WARNING` were both refused as malformed and refreshed nothing.
On the hang-up the writer drove **both** the zone channel open **and**
`WarningFieldClear := FALSE` in one step, and said so in one log line.

### §7.5 Two defects these runs found, and what happened to each

**D1 — the writer never noticed a peer hanging up (found and fixed here).**
`NetworkStream.DataAvailable` is FALSE at end of stream, so a read loop
guarded by it never runs and never sees the zero-length read. Measured: a
source that closed cleanly at 17:11:18.75 left the client object held, and the
**next** connection — as it happens, a connectivity probe from the concurrent
m5-56 session at 17:11:19.93 — was refused as a "second connection". The data
path was never wrong (silence is silence), but **the link could never be
re-established**, which would have made the joint run impossible. Fixed with
`Test-PeerClosed` (`Poll(SelectRead)` with `Available == 0`), applied to both
links; the field link had been getting away with it only because its 1 s
staleness reaper eventually freed the object. Re-proven in run E — two source
sessions back to back on 45016, the second **accepted** — and again in J1.

**D2 — a 1 Hz keepalive against a 1 s stale window has no margin (NOT fixed;
it is SPEC §7.2's value, not the writer's).** The first attempt at run D had
its field link reaped as stale after three keepalives, **10 ms before the
fourth arrived**: the sender's interval drifts a few ms past 1.000 s and the
writer's test is `> 1000 ms`. The failure direction is safe — the link reads
as intrusion *and* warning-occupied — so this is a nuisance trip, not a
hazard. It matters more than it did, because the same link now carries the
warning verdict and a spurious drop selects the limit. **The writer implements
the spec's value unchanged**; the test feeder gained a `-PingHz` knob so that
a check of the `ZONE`/`WARN` vocabulary is not silently a check of that
margin. Raised to `plc/` in the m5-57 report.

### §7.6 The proven properties, re-run

The three m5-41 properties this extension could have broken:

| Property | Re-run | Result |
|---|---|---|
| Double start refused | C1 | exit code **3**, the mutex message, **no new log file** (8 before, 8 after), no API contact |
| Terminal write before falling silent | C4, G | `TERMINAL` then `EXIT`; the three circuits FALSE, `WarningFieldClear` FALSE, `MotionPresent` TRUE with `MotionObservationValid` FALSE — and **both speed sequences deliberately left unwritten and frozen**, because a terminal zero would be a speed the writer invented |
| Republish repairs a controller restart | **not re-run** | The level republish is unchanged and now covers eight members; it ran continuously (10 962 cycles in the J1 session, 0 write failures). **The CPU-restart form was not reproduced** — stopping the controller was out of scope. It is owed a run |

Run F additionally showed **console commands entered while the loop kept
cycling** — `estop close`, `zone close`, `reset pulse 1500` typed into the
writer's own console from another process — with the heartbeat advancing
throughout and no gap in the `CYCLE` lines. In the same run one monitored
reset cleared `SpeedMonitorDemand`, `Ss1Demand` and `TorqueOffDemand`
together, and a fresh 80 mm/s discrepancy fed afterwards re-formed the demand
and ran the sequencer to torque-off about a second later. **That was a
by-product of proving the writer, not a T7 rehearsal**: T7 belongs to m5-58.

### §7.7 Cadence with eleven tags instead of four — measured

From the `CYCLE` timestamps of the two long sessions and the writer's own
`EXIT` counters:

| Session | cycles | overruns | write failures | period median | p95 | max |
|---|---|---|---|---|---|---|
| pid44496 (D–G) | 7 342 | 11 (0.15 %) | 0 | 48.0 ms | 65.0 ms | 113.0 ms |
| pid14288 (J1) | 10 962 | 8 (0.07 %) | 0 | 48.0 ms | 65.0 ms | 111.0 ms |

The 50 ms anchor holds with eleven writes as it held with four, and the write
phase failed **zero times in 18 304 cycles**. **These are timing samples from
two sessions on one machine, not bounds** (LESSONS 2026-08-04, 2026-08-05):
the design property — the write phase is small against the cycle, and the
deadline anchor does not drift — will reproduce; the millisecond figures are
two draws. The spread is Windows `Thread.Sleep` granularity, which
`STANDIN_STALE_MAX` = 1 s absorbs twenty times over.

### §7.8 An operating note that cost a run, recorded because it will cost another

**With no field-evaluation source running, `WarningFieldClear` is FALSE, so
the reduced limit is in force.** A vehicle fed at 300 mm/s is then legitimately
over it: `SpeedOverLimitNow` chattered as the noisy readings crossed the
selected limit, `SpeedCauseGone` followed it, and **no monitored reset could
ever be accepted** (`m5-57-R2-reset-refusal-consumer.log`). That is the
program behaving exactly as §11.2 specifies — loss of the field source selects
the limit — and it is not a defect at either end.

It does mean that **any procedure needing the latches to clear must either run
a field source saying `WARN 1`, or drive below the limit in force.** Run R1 is
the simpler form of the same observation: with no speed source at all, a reset
was refused twice with `SpeedCauseGone` FALSE throughout.

### §7.9 State the machine was left in (m5-57)

Read back after the last `quit`, instance `safecell3`, `OperatingState = Run`,
269 tags:

```
SafetyInputStandIn.EStopCircuitClosed        False
SafetyInputStandIn.ZoneDeviceCircuitClosed   False
SafetyInputStandIn.ResetButtonPressed        False
SafetyInputStandIn.WarningFieldClear         False
SafetyInputStandIn.MotionPresent              True
SafetyInputStandIn.MotionObservationValid    False
SafetyInputStandIn.StandInHeartbeat          10962   (frozen: no writer running)
SafetyInputStandIn.SpeedReadingA               300   (stale by construction)
SafetyInputStandIn.SpeedReadingB               300
SafetyInputStandIn.SpeedSeqA                  1715   (frozen == missing)
SafetyInputStandIn.SpeedSeqB                  1715
InstF_Forklift_Safety.StandInValid           False
InstF_Forklift_Safety.SpeedChainSeen          True
InstF_Forklift_Safety.EStopDemand             True
InstF_Forklift_Safety.ZoneStopDemand          True
InstF_Forklift_Safety.SpeedMonitorDemand      True
InstF_Forklift_Safety.Ss1Demand               True
InstF_Forklift_Safety.TorqueOffDemand         True
InstF_Forklift_Safety.SafetyResetRequired     True
InstF_Forklift_Safety.SafetyResetFault       False
```

**No writer process is running** (the `Global\amr-standin-writer` mutex was
acquired fresh and released to prove it), **nothing is listening on 45015 or
45016**, and no vehicle-side process survives in WSL. **Nothing was
downloaded, no block was compiled, no program was changed, no project was
opened and no `plc/` file was edited.** Every write went through the writer's
eleven-tag allowlist.

Two members read a value rather than a start value, and neither is tidied
away: `SpeedReadingA`/`B` hold 300/300 while their sequences are **frozen**,
which is precisely what makes them meaningless to the monitor.
`SpeedChainSeen` is TRUE and only a CPU STOP → RUN clears it — the same
one-shot property m5-41 recorded for `HeartbeatSeen`.
