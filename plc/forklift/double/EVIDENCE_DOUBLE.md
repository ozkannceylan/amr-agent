# Evidence — forklift PLC logic double

What this file records: that the transliteration of `plc/forklift/SPEC.md` §7 in
`logic.py` executes, that the address space it serves matches
`docs/interfaces/opcua-nodes.md` §10.3 including the namespace derivation of
ADR 0006, and that the four T5 kernels the brief names behave as the
specification says they should.

**This is evidence about a rehearsal stand-in, not about the plant.** No PLCSIM
Advanced instance and no TIA Portal build was involved, contacted or started. A
kernel passing here says the specification is self-consistent and executable; it
says nothing whatever about the TIA build, which is verified by the owner's own
run of §11 against the CPU.

## Environment

| Item | Value |
|---|---|
| Date | 2026-07-29 |
| Host | WSL2 (Ubuntu, kernel 6.6), repo at `/mnt/c/Users/ozkan/projects/amr-agent` |
| Python | 3.12.3 |
| `asyncua` | **2.0.1**, from `/home/ozkan/amr-bridge-venv` — the bridge's venv, pinned to it per the brief (`bridge/requirements.txt` carries `asyncua==2.0.1`) |
| Server | `plc/forklift/double/server.py`, endpoint `opc.tcp://0.0.0.0:4850/`, security `None`, anonymous |
| Client | `plc/forklift/double/check_kernels.py` — a direct `asyncua` client. **No bridge code, no HMI code and nothing from another layer is imported** |
| Ports | 4850 only. 4840 (PLCSIM Advanced) and 4842–4846 (the bridge's own doubles) were never bound; `server.py` refuses to start on any of them |
| Scan loop | nominal 20 ms; **measured mean 20.6 ms, max 22.3 ms over 1000 scans** |

The session was ended by observation, not assumption: the process was killed and
`ss -ltn` then showed 4850 free.

**Reproduced.** After the transcript below was captured, one cosmetic rename was
made in `check_kernels.py` (a local poll-timeout variable), so the whole run was
repeated from a fresh server against the committed script: **48 checks, 0
failures, exit 0**, with `HmiLinkOk` falling **643 ms** after the last heartbeat
(642 ms in the transcript) and the scan loop at mean 20.7 ms, max 22.5 ms. The
transcript below is verbatim from the first of the two runs; the second differs
only in those third-digit timings, which is scheduler noise on a Python loop and
not a property of the logic.

## Address space, read back rather than asserted

The namespace array as the server actually advertised it, and the browse path as
the client actually resolved it — both read out of the running server, neither
typed from the design:

```
server namespace array: ['http://opcfoundation.org/UA/',
                         'urn:freeopcua:python:server',
                         'http://www.siemens.com/simatic-s7-opcua',
                         'http://DemoCell']
resolved index 2 -> http://www.siemens.com/simatic-s7-opcua
resolved index 3 -> http://DemoCell
browse path: 0:Root -> 0:Objects -> 2:ServerInterfaces -> 3:DemoCell
             -> 3:Forklift -> 3:Hmi -> 3:HmiTractionRequest
```

Four things this confirms, each of which is a rule from the interface document
rather than a convenience of the double:

- **Both namespaces resolve by URI**, and the client hardcodes neither index
  (ADR 0006 D4, `opcua-nodes.md` §2.1). The indices happen to be 2 and 3 here and
  will differ on the CPU; nothing depends on them.
- **`ServerInterfaces` is in the Siemens namespace, not the interface's own** —
  index 2 in the path above, while everything from `DemoCell` down is index 3.
  Reusing one index for both fails to browse, which is the trap §2.1 names.
- **The interface node is named `DemoCell`**, which is what derives
  `http://DemoCell`. On the CPU the field is not editable; here it is chosen to
  match, so a client written against the CPU browses the double unchanged.
- **`Forklift/` sits beside the M3 folders**, not on a second interface (§10.2).

20 nodes resolved: the 18 of §10 plus `DemoCell/Link/BridgeHeartbeat` and
`DemoCell/Link/BridgeLinkOk`, which is the shared link surface the bridge needs
and the one tag §7 consumes. Access rights were tested by attempting a write, not
by reading a flag: `Forklift/Output/` and `Forklift/Status/` both refused with
**`BadUserAccessDenied`**, which is §10.3's *Writable from HMI/OPC UA* ✘ enforced
by the server rather than by convention.

## Kernel transcript

Run of 2026-07-29, from a freshly started server (so K1 reads a true boot state).
Verbatim.

```
==============================================================================
Forklift PLC logic double -- kernel checks
endpoint: opc.tcp://127.0.0.1:4850/
==============================================================================

[K0] namespace table and browse path, resolved BY URI
    server namespace array: ['http://opcfoundation.org/UA/', 'urn:freeopcua:python:server', 'http://www.siemens.com/simatic-s7-opcua', 'http://DemoCell']
    resolved index 2 -> http://www.siemens.com/simatic-s7-opcua
    resolved index 3 -> http://DemoCell
    PASS   both namespaces resolve by URI, neither index hardcoded
    browse path: 0:Root -> 0:Objects -> 2:ServerInterfaces -> 3:DemoCell -> 3:Forklift -> 3:Hmi -> 3:HmiTractionRequest
    PASS   ServerInterfaces is NOT a child of Objects' own namespace
    PASS   interface node is named DemoCell (the URI is derived from it)
    PASS   Forklift subtree sits beside the M3 folders
    PASS   18 forklift nodes + 2 shared link nodes resolved  -- resolved 20
    PASS   Output/ is read-only for clients  -- BadUserAccessDenied
    PASS   Status/ is read-only for clients

[K1] boot polarity -- HmiLinkOk FALSE until the heartbeat has moved
    at boot, before any heartbeat: HmiLinkOk=False BridgeLinkOk=False ResetRequired=True ObstacleStopActive=False
    PASS   HmiLinkOk FALSE from the first scan
    PASS   BridgeLinkOk FALSE from the first scan
    PASS   ResetRequired TRUE from power-up (both link latches formed)
    PASS   ObstacleStopActive FALSE despite the field bit's TRUE start value  -- no sensor is accused of something no sensor reported
    PASS   ...and the field bit really did start TRUE
    after the heartbeats advance: HmiLinkOk=True BridgeLinkOk=True
    PASS   HmiLinkOk TRUE once the heartbeat has been seen to change
    PASS   BridgeLinkOk TRUE likewise
    PASS   teleop still NOT active -- a link coming up energizes nothing

[bring-up] TeleopActive=True ResetRequired=False
    PASS   machine enabled after reset + a separate enable edge

[K2] T5.3 -- traction capped while the fork is raised
    fork 0.20 m (below 0.50), demand 1.0 -> TractionSpeedRef=1.000 SpeedLimitActive=False
    PASS   uncapped setpoint is demand x TRACTION_SPEED_MAX = 1.00
    PASS   SpeedLimitActive FALSE below the threshold
    fork 0.80 m (above 0.50), demand UNCHANGED at 1.0 -> TractionSpeedRef=0.300 SpeedLimitActive=True
    PASS   capped setpoint is demand x TRACTION_SPEED_CAP_RAISED = 0.30  -- the operator touched nothing; the PLC reduced it
    PASS   SpeedLimitActive TRUE above the threshold
    fork still raised, demand 0.2 -> TractionSpeedRef=0.060 SpeedLimitActive=True
    PASS   the cap LIMITS, it does not command (0.2 x 0.30 = 0.06)
    PASS   SpeedLimitActive stays TRUE -- 'in force', not 'biting'

[K3] T5.2 -- fork soft travel limits, direction-scoped
    fork 0.02 m (below FORK_TRAVEL_MIN 0.05), lower demand -1.0 -> ForkSpeedRef=0.000
    PASS   lowering blocked at the bottom limit
    PASS   no latch: a soft-limit abort is a refusal, not a fault
    same height, raise demand +1.0 -> ForkSpeedRef=0.150
    PASS   raising still permitted at the bottom limit -- NOT stranded
    fork 1.58 m (above FORK_TRAVEL_MAX 1.55), raise demand STILL +1.0 -> ForkSpeedRef=0.000
    PASS   raising blocked at the top limit with the control still held
    same height, lower demand -1.0 -> ForkSpeedRef=-0.150
    PASS   lowering permitted at the top limit -- the abort is direction-scoped
    PASS   still no latch anywhere in K3

[K4] T5.4 -- obstacle latch, override, refusal, monitored reset
    driving: TractionSpeedRef=1.000 TeleopActive=True
    PASS   driving before the obstacle
    obstacle in zone, traction demand STILL 1.0 -> TractionSpeedRef=0.000 SteerAngleRef=0.000 ForkSpeedRef=0.000 TeleopActive=False ObstacleStopActive=True ResetRequired=True
    PASS   all three setpoints zeroed -- the latch overrides a LIVE command
    PASS   teleop dropped
    PASS   ObstacleStopActive latched
    PASS   ResetRequired TRUE
    reset asserted WHILE occupied (and now held) -> ObstacleStopActive=True ResetRequired=True
    PASS   reset REFUSED while the zone reads occupied (causeGone false on C3)
    zone cleared with the reset STILL HELD, 1.2 s -> ObstacleStopActive=True ResetRequired=True
    PASS   the field clearing does NOT release the latch
    PASS   a HELD reset clears nothing -- the edge happened before the cause went, and no elapsed time makes a new one
    released, then a FRESH rising edge -> ObstacleStopActive=False ResetRequired=False TeleopActive=False TractionSpeedRef=0.000
    PASS   the fresh edge clears the latches
    PASS   the reset ENERGIZES NOTHING: teleop still off, setpoints still 0.0  -- traction demand is still 1.0 and the machine does not move
    PASS   enable held across the reset produces NO edge -- no auto-resume
    enable released and re-asserted -> TeleopActive=True TractionSpeedRef=1.000
    PASS   teleop returns only on a fresh enable edge

[K5] T5.5 -- HMI heartbeat stale zeros all three setpoints
    driving with all three moving: Traction=1.000 Steer=0.500 Fork=0.150
    PASS   all three setpoints non-zero before the outage
    last heartbeat -> HmiLinkOk FALSE: 642 ms
    last heartbeat -> all three refs 0.0: 642 ms
    after the outage: TeleopActive=False ResetRequired=True
    PASS   HmiLinkOk goes FALSE within HMI_STALE_TIME + one scan (600+20 ms)  -- 642 ms
    PASS   all three setpoints reach 0.0 in the same window  -- 642 ms
    PASS   teleop dropped
    PASS   the loss LATCHES: ResetRequired TRUE
    HMI restarted, heartbeat advancing again, nothing else done -> HmiLinkOk=True TeleopActive=False ResetRequired=True Traction=0.000
    PASS   link returns
    PASS   teleop does NOT return -- a returning heartbeat restores nothing
    PASS   ResetRequired still TRUE

==============================================================================
all kernel checks passed
```

## What each kernel actually establishes

| Kernel | SPEC | Established |
|---|---|---|
| K0 | §4.3, `opcua-nodes.md` §2.1, §10.2, §10.3 | The browse path and both namespace URIs, **read back from the running server**. Read-only enforcement on `Output/` and `Status/` proven by a refused write |
| K1 | §6.1, `opcua-nodes.md` §10.8 P2 | `HmiLinkOk` and `BridgeLinkOk` are **`FALSE` from the first scan**, not merely "not yet proven stale". Both link latches form at boot, so `ForkliftResetRequired` reads `TRUE` from power-up. **`ForkliftObstacleStopActive` reads `FALSE` even though the field bit's start value really is `TRUE`** — the `bridgeLinkOk` conjunct in part 3 keeps a cold-started CPU from accusing a sensor. A link coming up energizes nothing |
| K2 | §6.5 | The cap engages at `FORK_HEIGHT_SLOW_THRESHOLD` **with the operator's control untouched**: 1.00 → 0.30 m/s on the fork crossing 0.50 m. At a 0.2 demand the setpoint is 0.060, so the cap **scales** the request rather than clamping the full-scale product, and `ForkliftSpeedLimitActive` stays `TRUE` — "in force", not "biting". **The label carried in the transcript above reads "the cap LIMITS, it does not command", which is the clamp reading `SPEC.md` §6.5 and §11 5.3.4 were corrected away from on 2026-07-29; the assertion under it always tested `0.06` and always passed.** Relabelled and re-run rather than edited in place — see the re-run at the end of this file |
| K3 | §6.6 | Both soft limits abort **in the offending direction only**. At 0.02 m lowering is refused and raising still gives −/+0.15 m/s; at 1.58 m raising is refused with the control held and lowering still works. **Nothing latches**, so no reset is needed to leave a limit — the carriage is never stranded |
| K4 | §6.7 | The latch **overrides a live command**: all three setpoints go to `0.0` while the traction request still stands at 1.0. A reset is refused while the zone reads occupied; the field clearing does not release the latch; a **held** control supplies no edge and clears nothing; a fresh edge clears the latches and **energizes nothing**; teleop returns only on a fresh enable edge |
| K5 | §6.4, §8 case H1, `opcua-nodes.md` §10.8 P5 | All three setpoints reach `0.0` **642 ms** after the last advancing heartbeat, inside `HMI_STALE_TIME` + one scan. The loss latches, and a returning heartbeat restores nothing |

The 642 ms is the bound this run measured, not a specification value: it is
`HMI_STALE_TIME` (600 ms) plus the TON's first-call convention plus one scan plus
the client's own 5 ms poll. The specification's claim is "within the watchdog
period", and this is inside it.

## Finding: SPEC §11 steps 5.4.4–5.4.7 cannot demonstrate the stuck reset

**Found by transliteration, reported rather than fixed, and it is a defect in the
procedure, not in the logic.** The first run of K4 followed §11's step order
literally and **failed**: the latch cleared where step 5.4.7 says it never can.

The mechanism, and why the program is right and the procedure is wrong:

- **5.4.4** attempts a reset while the zone is occupied and says to *"assert **and
  release** the reset control"*. The control therefore ends released and
  `ResetEdgeMemory` ends `FALSE`.
- **5.4.6** clears the zone, so `causeGone` becomes `TRUE`.
- **5.4.7** then says to *"assert the reset control and leave it asserted"* and
  expects *"the latch **never** clears"*.

But an assertion after a release **is a fresh rising edge**, and by 5.4.7 the
cause is gone, so `resetRise AND NOT ResetDeviceFault AND latchPending AND
causeGone` is satisfied and the program correctly clears the latch. **Step 5.4.7
as written measures nothing**, and 5.4.8 is then left with nothing to clear.

The property §6.7 actually claims — *"a reset held down across a later stop
cannot clear that stop's latch either, because the edge happened before the latch
did"* — needs the control **held continuously across the moment the cause
clears**, with no intervening release. K4 is ordered that way instead: assert
while occupied, hold, clear the zone **with the control still held**, and confirm
after 1.2 s that nothing cleared. That passes, and it tests both properties at
once — the field clearing does not release the latch, and a held control supplies
no edge.

**Why this matters more than a wording nit.** An owner running §11 T5.4 against
the CPU as written would watch the latch clear at 5.4.7, conclude the
edge-triggered reset was broken, and go hunting for a defect in a program that
does not have one. `SPEC.md` was not edited — the brief forbids it and requires
the finding be reported — so the correction is requested in
`docs/reports/m4f-04c-plc-logic-double.md`.

## What was NOT demonstrated, and why

| Not covered | Why |
|---|---|
| The plausibility latches (`PlantInputFaultLatch`, `RequestFaultLatch`, `ObstacleStopLatch` via `LidarInvalidTimer`) | Reachable here — a client *can* write an out-of-window value, unlike the real plant — but they are not among the four kernels the brief names, and the double is not the place to close `SPEC.md` §12 item 6, which asks for injection at the **bridge**. Their absence from this file is not a pass |
| T5.1 and T5.6 | Not among the four kernels briefed. T5.6 needs a bridge session to lose, which is the rehearsal run's business, not the double's |
| Anything about the TIA build | Nothing here executed on a CPU. The double's agreement with the specification is not evidence about the plant |
| Timing on a real CPU | The 642 ms and the 20.6 ms mean scan are this Python loop's numbers. The CPU's OB30 and its TONs are the owner's to measure |

---

## Re-run of 2026-07-29 — K2's label states the scale

**Why.** `SPEC.md` §6.5 and §11 step 5.3.4 were corrected on 2026-07-29
(`docs/reports/m4f-04e-t5-pass-line-corrections.md`): the raised-carriage cap is
a **scale** — §7 assigns the traction setpoint once as
`#tractionDemand * #speedCap` — so a 0.2 demand under the raised carriage is
`0.2 × 0.30 = 0.060` m/s, not a clamp of the full-scale product to `0.20`. K2's
check label was the last statement of the clamp reading left inside `plc/`, and
it sat over an assertion that had always tested the scale's number and always
passed.

**What changed, and what did not.** Exactly one string in `check_kernels.py`:

```
-    check("the cap LIMITS, it does not command (0.2 x 0.30 = 0.06)",
+    check("the cap SCALES the request, it does not clamp the full-scale product "
+          "(0.2 x 0.30 = 0.060, not 0.20)",
           abs(s["ForkliftTractionSpeedRef"] - 0.06) < 1e-6)
```

The **assertion is untouched** — same tolerance, same `0.06`, same reading of the
same node. `logic.py` and `server.py` are byte-identical, so the behaviour under
test did not move and this run is not a re-measurement of anything. **The
transcript above was not edited**: a transcript is quoted as the harness printed
it, and a corrected label is proven by re-running, not by rewriting the record of
a run that used the old one.

**Environment, as the table at the top of this file, with two deltas.**

| Item | Value |
|---|---|
| Date | 2026-07-29 |
| Port | **4851**, not 4850. A concurrent agent may hold a double on 4850; 4851 was confirmed free before start and free again after. 4840 (PLCSIM Advanced) and 4842–4846 (the bridge's doubles) were never bound, and `server.py` refuses them |
| Python / `asyncua` / kernel | 3.12.3 / **2.0.1** (`/home/ozkan/amr-bridge-venv`) / WSL2 5.15.167.4 |
| Scan loop | `scan 500, mean 20.6 ms, max 22.5 ms`, from the server's own log |
| Server | freshly started for this run, so K1 reads a true boot state |

**PLCSIM was never contacted.** One endpoint was named, `opc.tcp://127.0.0.1:4851/`.

### Transcript, verbatim

Standard output of `check_kernels.py`, exactly as printed:

```
==============================================================================
Forklift PLC logic double -- kernel checks
endpoint: opc.tcp://127.0.0.1:4851/
==============================================================================

[K0] namespace table and browse path, resolved BY URI
    server namespace array: ['http://opcfoundation.org/UA/', 'urn:freeopcua:python:server', 'http://www.siemens.com/simatic-s7-opcua', 'http://DemoCell']
    resolved index 2 -> http://www.siemens.com/simatic-s7-opcua
    resolved index 3 -> http://DemoCell
    PASS   both namespaces resolve by URI, neither index hardcoded
    browse path: 0:Root -> 0:Objects -> 2:ServerInterfaces -> 3:DemoCell -> 3:Forklift -> 3:Hmi -> 3:HmiTractionRequest
    PASS   ServerInterfaces is NOT a child of Objects' own namespace
    PASS   interface node is named DemoCell (the URI is derived from it)
    PASS   Forklift subtree sits beside the M3 folders
    PASS   18 forklift nodes + 2 shared link nodes resolved  -- resolved 20
    PASS   Output/ is read-only for clients  -- BadUserAccessDenied
    PASS   Status/ is read-only for clients

[K1] boot polarity -- HmiLinkOk FALSE until the heartbeat has moved
    at boot, before any heartbeat: HmiLinkOk=False BridgeLinkOk=False ResetRequired=True ObstacleStopActive=False
    PASS   HmiLinkOk FALSE from the first scan
    PASS   BridgeLinkOk FALSE from the first scan
    PASS   ResetRequired TRUE from power-up (both link latches formed)
    PASS   ObstacleStopActive FALSE despite the field bit's TRUE start value  -- no sensor is accused of something no sensor reported
    PASS   ...and the field bit really did start TRUE
    after the heartbeats advance: HmiLinkOk=True BridgeLinkOk=True
    PASS   HmiLinkOk TRUE once the heartbeat has been seen to change
    PASS   BridgeLinkOk TRUE likewise
    PASS   teleop still NOT active -- a link coming up energizes nothing

[bring-up] TeleopActive=True ResetRequired=False
    PASS   machine enabled after reset + a separate enable edge

[K2] T5.3 -- traction capped while the fork is raised
    fork 0.20 m (below 0.50), demand 1.0 -> TractionSpeedRef=1.000 SpeedLimitActive=False
    PASS   uncapped setpoint is demand x TRACTION_SPEED_MAX = 1.00
    PASS   SpeedLimitActive FALSE below the threshold
    fork 0.80 m (above 0.50), demand UNCHANGED at 1.0 -> TractionSpeedRef=0.300 SpeedLimitActive=True
    PASS   capped setpoint is demand x TRACTION_SPEED_CAP_RAISED = 0.30  -- the operator touched nothing; the PLC reduced it
    PASS   SpeedLimitActive TRUE above the threshold
    fork still raised, demand 0.2 -> TractionSpeedRef=0.060 SpeedLimitActive=True
    PASS   the cap SCALES the request, it does not clamp the full-scale product (0.2 x 0.30 = 0.060, not 0.20)
    PASS   SpeedLimitActive stays TRUE -- 'in force', not 'biting'

[K3] T5.2 -- fork soft travel limits, direction-scoped
    fork 0.02 m (below FORK_TRAVEL_MIN 0.05), lower demand -1.0 -> ForkSpeedRef=0.000
    PASS   lowering blocked at the bottom limit
    PASS   no latch: a soft-limit abort is a refusal, not a fault
    same height, raise demand +1.0 -> ForkSpeedRef=0.150
    PASS   raising still permitted at the bottom limit -- NOT stranded
    fork 1.58 m (above FORK_TRAVEL_MAX 1.55), raise demand STILL +1.0 -> ForkSpeedRef=0.000
    PASS   raising blocked at the top limit with the control still held
    same height, lower demand -1.0 -> ForkSpeedRef=-0.150
    PASS   lowering permitted at the top limit -- the abort is direction-scoped
    PASS   still no latch anywhere in K3

[K4] T5.4 -- obstacle latch, override, refusal, monitored reset
    driving: TractionSpeedRef=1.000 TeleopActive=True
    PASS   driving before the obstacle
    obstacle in zone, traction demand STILL 1.0 -> TractionSpeedRef=0.000 SteerAngleRef=0.000 ForkSpeedRef=0.000 TeleopActive=False ObstacleStopActive=True ResetRequired=True
    PASS   all three setpoints zeroed -- the latch overrides a LIVE command
    PASS   teleop dropped
    PASS   ObstacleStopActive latched
    PASS   ResetRequired TRUE
    reset asserted WHILE occupied (and now held) -> ObstacleStopActive=True ResetRequired=True
    PASS   reset REFUSED while the zone reads occupied (causeGone false on C3)
    zone cleared with the reset STILL HELD, 1.2 s -> ObstacleStopActive=True ResetRequired=True
    PASS   the field clearing does NOT release the latch
    PASS   a HELD reset clears nothing -- the edge happened before the cause went, and no elapsed time makes a new one
    released, then a FRESH rising edge -> ObstacleStopActive=False ResetRequired=False TeleopActive=False TractionSpeedRef=0.000
    PASS   the fresh edge clears the latches
    PASS   the reset ENERGIZES NOTHING: teleop still off, setpoints still 0.0  -- traction demand is still 1.0 and the machine does not move
    PASS   enable held across the reset produces NO edge -- no auto-resume
    enable released and re-asserted -> TeleopActive=True TractionSpeedRef=1.000
    PASS   teleop returns only on a fresh enable edge

[K5] T5.5 -- HMI heartbeat stale zeros all three setpoints
    driving with all three moving: Traction=1.000 Steer=0.500 Fork=0.150
    PASS   all three setpoints non-zero before the outage
    last heartbeat -> HmiLinkOk FALSE: 643 ms
    last heartbeat -> all three refs 0.0: 643 ms
    after the outage: TeleopActive=False ResetRequired=True
    PASS   HmiLinkOk goes FALSE within HMI_STALE_TIME + one scan (600+20 ms)  -- 643 ms
    PASS   all three setpoints reach 0.0 in the same window  -- 643 ms
    PASS   teleop dropped
    PASS   the loss LATCHES: ResetRequired TRUE
    HMI restarted, heartbeat advancing again, nothing else done -> HmiLinkOk=True TeleopActive=False ResetRequired=True Traction=0.000
    PASS   link returns
    PASS   teleop does NOT return -- a returning heartbeat restores nothing
    PASS   ResetRequired still TRUE

==============================================================================
all kernel checks passed
```

**Standard error carried exactly one line**, and it is the `asyncua` client's own
log rather than anything the harness prints:

```
Requested session timeout to be 3600000ms, got 600000ms instead
```

It is quoted here because it was in the capture, and it is the familiar
`granted = min(request, cap)` shape: the client asked for an hour and this server
granted ten minutes. It bears on no kernel — nothing here runs long enough to
renew a session — and it is a property of the double's `asyncua` server, not a
figure the CPU will reproduce.

### What this run establishes, and what it does not

- **Exit 0**, and `all kernel checks passed` as the harness printed it. The
  harness prints **no count of its own**, so: counting `PASS` lines in the
  transcript above gives **48**, with no `FAIL` line. That 48 is a count of this
  transcript, not a figure any tool reported.
- **K2 now reads the scale in its label as well as in its arithmetic**, which was
  the whole point of the re-run. Its three printed values — `1.000`, `0.300`,
  `0.060` — are identical to the run above it, because only the label moved.
- **K5 measured 643 ms** here against 642 ms and 643 ms in the two runs recorded
  above. Third-digit scheduler noise on a Python loop, and inside the same
  `HMI_STALE_TIME` + one scan window; it is not a new claim about the program.
- **The session was ended by observation, not assumption**: the server was killed,
  `ss -ltn` then showed 4851 free, and no process from the venv survived.
- **Nothing here is evidence about the plant.** The double is a transliteration of
  `SPEC.md` §7; agreement between them says the specification is self-consistent
  and executable and says nothing about the TIA build, which the owner verifies by
  running §11 against the CPU.
