# m5-03 — F-I/O feasibility probe, executed

brief:               plc/forklift-safety/FIO-FEASIBILITY.md (the procedure itself; no separate brief file)
status:              done
files_changed:
  - plc/forklift-safety/FIO-FEASIBILITY.md (record tables and §7 verdict filled)
  - plc/forklift-safety/evidence/m5-03-fio-addresses.png
  - plc/forklift-safety/evidence/m5-03-fio-fparameters.png
  - plc/forklift-safety/evidence/m5-03-fio-db-members.png
  - plc/forklift-safety/evidence/m5-03-probe-safety-mode-signature.png
  - plc/forklift-safety/evidence/m5-03-watch-passivated-at-rest.png
  - plc/forklift-safety/evidence/m5-03-diagnostic-buffer.png
  - plc/forklift-safety/evidence/m5-03-modify-refused-permanent-safety-mode.png
  - plc/forklift-safety/evidence/m5-03-watch-false-while-api-holds-true.png
  - plc/forklift-safety/evidence/m5-03-api-tag-write-log.txt
  - plc/forklift-safety/evidence/m4-f-collective-signature-2026-08-04.png
  - plc/forklift-safety/evidence/m4-f-runtime-group-1.png
  - plc/forklift/evidence/m4-ob30-cyclic-time.png
  - plc/forklift/evidence/m4-cpu-cycle-time.png
  - plc/forklift/evidence/m4-safety-access-protection.png
  - plc/forklift/evidence/m4-cold-start-bridge-down.png
  - docs/reports/m5-03-fio-probe-run.md
invariants_touched:  none
open_questions:      see the list at the end
next_suggested:      m5-15 (F-program spec) may now be briefed against the standard-DB stand-in path, carrying §6's three consequences; the roadmap criterion (a) blocker deferred in docs/TODO.md is now live and needs an owner ruling

---

## FIO-PROBE VERDICT — 2026-08-04

**Ortam / environment:** TIA Portal **V21**; S7-PLCSIM Advanced **V7.0**
(installed-programs `V7.0` / `07.00.0000`; the V7.0 control panel has no About or
version field, so the panel could not corroborate it); CPU **1513F-1 PN**,
`6ES7 513-1FM03-0AB0`, firmware **V3.1**; project safety system version **V2.8**.

**Adım 1 (versions against the supported list): PASS, in the sense F4 defines.**
PLCSIM Advanced V7.0 has no verified supported list (ADR 0011 F4), and safety
system V2.8 postdates F1's V1.6–V2.5 list, which belongs to the V5.0 manual. Per
F4's row this is explicitly not an abort and not a yes either — the question was
handed to steps 2–4 and answered there. No safety-system-version change was
attempted, so no refusal text exists to quote.

**Adım 2 (F-DI configured, compiled, downloaded, RUN, safety mode active):
PASS.**
Address range: inputs `I0.0 … I6.7`, outputs `Q0.0 … Q4.7`, **process image not
assigned** (`---`). PROFIsafe: `F-source address 1`, `F-destination address
65534`, V2 mode, expanded protocol (XP), F-parameter signature (with addresses)
`65255`. **F-monitoring time 150 ms** (manual assignment unchecked). **F-I/O DB
generated as `F00000_F-DI8x24VDCHF_1`, DB 30011.** Station: `IO device_1
[IM 155-6 PN ST]` `6ES7 155-6AU02-0BN0` on `PROFINET IO-System_1`, F-DI `F-DI
8x24VDC HF_1` `6ES7 136-6BA01-0CA0` V2.0, server module `SRVM BC_1`
`6ES7 193-6PA20-0AA0` V1.2. Compile `errors: 0; warnings: 2`, the safety-side one
being *"The F-module 'F-DI 8x24VDC HF_1' was not interconnected in the fail-safe
program"* — expected, since the probe adds no logic. Download clean, diff circles
solid green, F-collective signature `5DC99AD0` online = offline, CPU **RUN**,
*"Safety mode is activated."*

**Adım 3 (startup / passivation): the module never leaves passivation.**
Channel value `FALSE`; **value status does not exist on this module** — no
checkbox is offered, so the F5 divergence between value status and QBAD could not
be observed here at all. `PASS_OUT` = **TRUE**, `QBAD` = **TRUE**, unchanged after
STOP→RUN and unchanged over minutes at rest. `ACK_NEC` = TRUE, `ACK_REI` = FALSE,
**`ACK_REQ` = FALSE** — the block never raised an acknowledgement request, so
there was nothing to acknowledge. `DIAG` = `16#00`. Generated block members are
`PASS_ON ACK_NEC ACK_REI IPAR_EN DISABLE` / `PASS_OUT QBAD ACK_REQ IPAR_OK DIAG
DISABLED BASEID_ACTIVE`; **there are no per-channel `QBAD_I_*` members**.
Diagnostic buffer: 15 entries, **none** naming PROFINET, the IO device, the F-I/O
or the F-runtime group. Online diagnostics of both head module and F-DI read
**"Module exists. OK"** while the block reported `QBAD` = 1. Unacknowledged
reintegration was therefore **not** observed, and the acknowledgement path is
closed from the engineering side — see the finding below.

**Adım 4 (does the API write BY TAG NAME): the channel is writable by name, and
the F-program still would not see it. FAIL for the primary path.**
- Tag path: **`ProbeFdiCh0`** — the PLC tag-table symbol, unqualified, area
  `Input`, type `Bool`. Present in `IInstance.TagInfos` (166 tags) after
  `UpdateTagList()`. The F-I/O DB and all twelve of its members are reachable by
  name too.
- API used: `Siemens.Simatic.Simulation.Runtime.Api.x64.dll` from the
  installation's own `API\7.0` directory, loaded into Windows PowerShell 5.1 with
  `Add-Type -Path`. **No new project dependency.** `SimulationRuntimeManager`
  version printed `458752`.
- Write: `WriteBool('ProbeFdiCh0', $true)` **returned without error**, with the
  CPU in RUN and safety mode activated. No refusal.
- **Read back through the API:** `True`, on every sample of a 10 s run and of a
  60 s run.
- **Read back in the TIA watch table, inside the hold window:** **`FALSE`.**
- `QBAD` / `PASS_OUT` at the same moment: **TRUE / TRUE**. Value status: not
  applicable.
- Hold: the divergence is constant for the full 60 s. The value does not land and
  revert; the two views simply never agree.

This is the procedure's abort row *"the write returns success, the API reads it
back, but the watch table shows the fail-safe value"* — the API writes a process
image the safety layer does not honour, which is `plc/forklift-safety/SPEC.md`
§2.1 point 4 **observed rather than assessed**. No by-address write was attempted;
F7 forbids it.

**Adım 5 (PIP 1 + SYNC_PI/SYNC_PO): KOŞULMADI / NOT RUN.** §5's own gate: step 4's
no is structural, not timing-shaped, so the step cannot rescue it. Read for the
record: the F-runtime group's pre- and post-processing entries both read
`(None)`, so nothing was registered and nothing had to be deleted.

**GENEL / OVERALL: GERİ DÜŞÜŞ GEREKLİ — ADR 0011 D2 fallback.** The standard-DB
stand-in of `SPEC.md` §7 remains the input path. Nothing was built and nothing was
removed; the working project `safe_amr` was never modified, the probe ran entirely
on the copy `safe_amr_FIOPROBE`.

### Faz 2 okumaları — the six M4 handover items

1. **F-collective signature:** `AA735E2A`, **online = offline**, version
   comparison green, read 2026-08-04 on the working project; offline and online
   safety programs both reported consistent; *"Safety mode is activated."*
   (Collective F-SW `AA735E29`, F-HW `00000001`, F-communication address
   signature `none`.)
2. **F-runtime monitoring and F-OB cycle:** `FOB_RTG1` = **OB123**, cyclic
   interrupt, **cycle time 100 ms**, phase shift 0, priority 12; warn cycle time
   of the F-runtime group **110 ms**, maximum **120 ms**; information DB
   `RTG1SysInfo`; main safety block `Main_Safety_RTG1 [FB1]` with I-DB
   `Main_Safety_RTG1_DB [DB1]`.
3. **RESET_HOLD_MIN against five F-OB cycles: DOES NOT COVER IT.** Five F-OB
   cycles are 5 × 100 ms = **500 ms**; `RESET_HOLD_MIN` is **200 ms**, which is
   two cycles. This is recorded as an **open SRS-window deviation**, not tuned.
   Raising it is a change to the monitored-reset window that the SRS states, and
   it belongs to a safety-spec brief with the acceptance test re-read beside it —
   not to a keystroke made while reading handover items.
4. **OB30 and CPU cycle times:** OB30 cyclic time **20 ms** (20000 µs), phase
   offset 0. CPU: minimum cycle time 1 ms, **cycle monitoring time 150 ms**;
   measured shortest **1.002 ms**, current **1.004 ms**, longest **1.655 ms**.
5. **Safety access protection:** no password is set for modifying safety-related
   project data, and none is set on the F-CPU online page. **Owner ruling,
   2026-08-04: out of scope** for this portfolio simulation — recorded here as
   the explicit line the handover item asks for, rather than left implicit.
6. **`HmiStaleTimer.PT`:** watch row reads **`T#600MS`**, and the in-force value
   read through the API is **600 ms**. (`BridgeStaleTimer.PT` = 500 ms, read
   beside it.)

### Faz 3 sonuçları — the three M4 closing items

1. **m3-37 finding 7 (`ResetEdgeMemory_1` vs SPEC §3.2): no mismatch exists.**
   The downloaded program's tag list carries **`ForkliftControl_DB.ResetEdgeMemory`**
   with no suffix, matching `plc/forklift/SPEC.md` §3.2. Neither side needed
   aligning; the finding closes as **not reproduced**. The `_1` sweep over the
   whole instance tag list found exactly one `_1` name, the stand-alone tag
   `Tag_1`, which is unrelated to the reset path — noted as a separate loose end
   below.
2. **Cold-start capture: taken** (`plc/forklift/evidence/m4-cold-start-bridge-down.png`).
   CPU cold start, bridge down, HMI down. `ForkliftHmi` requests all `0.0` /
   `FALSE`; `ForkliftInput` `ForkliftForkHeight` `0.0`, `ForkliftLinearSpeed`
   `0.0`, `ForkliftObstacleInStopZone` `FALSE`, `ForkliftObstacleMinDistance`
   `0.0` (the no-data sentinel); all three `ForkliftOutput` refs `0.0`;
   `ForkliftTeleopActive` `FALSE`, `ForkliftResetRequired` **TRUE**;
   `HmiLinkOk` `FALSE`, `HmiLinkLostLatch` **TRUE**, `BridgeLinkLostLatch`
   **TRUE**, `ResetDeviceFault` **TRUE**; `HmiStaleTimer.PT` `T#600MS`. This one
   screen closes m3-37 findings **1, 2, 8 and 9** together, and carries §11 4.8's
   cold-start half and 4.9b form (b).
   **The running-cell Group 1 + Group 2 capture was deferred by the owner to a
   separate run** — it is the one item of this session's scope that is not
   delivered, and it is listed in the open questions below.
3. **`bridge/config/bridge.yaml` repointing: NOT DONE in this session.** The TODO
   item conditions it on the TIA read-back being finished, which it now is, but
   the edit belongs to the bridge layer and to the same run as the running-cell
   capture that would verify it. Left for that run rather than committed blind.

### Beklenmedik olan — what was not anticipated

1. **Fail-safe tags cannot be modified from the engineering connection at all**
   in permanent safety mode. The tool refuses verbatim: *"Debugging of fail-safe
   tags is not allowed in permanent safety mode. (2206:000002)"*. This closes the
   acknowledgement experiment step 3 leaves open, and it constrains any future
   design that hoped to stimulate F-data by *Modify* — not just this probe.
2. **The passivation declares no fault.** `ACK_REQ` never rose, the diagnostic
   buffer logged nothing about PROFINET or the F-I/O, and both modules read
   *"Module exists. OK"* — while the F-I/O DB reported `QBAD` = `PASS_OUT` = 1
   throughout. A reader checking diagnostics alone would conclude the station is
   healthy. The `SPEC.md` §2.1 assessment could not have been falsified that way.
3. **This F-DI offers no value status parameter**, so the F5 divergence between
   simulated value status and QBAD / PASS_OUT could not be observed. The
   procedure assumed the checkbox would be there to enable.
4. **TIA's `_1` suffixing hit three names in one placement** — the module, the
   server module and the generated F-I/O DB — while the hand-typed tag survived
   two downloads unsuffixed. The suffix comes with tool-generated names, not with
   authored ones.
5. **The *IO tags* tab is read-only while online.** A channel tag can only be
   named offline, which matters for any procedure that expects to name a tag
   while watching it.
6. **The PLCSIM Advanced V7.0 control panel prints no version anywhere** — the
   installed-programs registry is the only source, so §0.2 rule 5's "read it back
   from the tool" had to be satisfied from Windows rather than from the tool.

## Open questions

1. **Roadmap criterion (a) is now live.** The judge review recorded that a NO
   verdict on this probe puts criterion (a) of the M5 row in question; the owner
   deferred that blocker until the verdict was in. It is in. This needs an owner
   ruling before m5-19, and it is an arch-docs / safety-spec question, not a PLC
   one.
2. **`RESET_HOLD_MIN` is 200 ms against a 500 ms five-cycle window.** Recorded as
   an SRS-window deviation. Whether the window is widened or the requirement
   restated is a safety-spec decision.
3. **The running-cell Group 1 + Group 2 capture** and **the `bridge.yaml`
   repointing** are deferred to their own run, together.
4. **`Tag_1`** exists in the downloaded program as a stand-alone Bool with no
   documented owner. Trivial, but it is an undocumented tag in a program whose
   naming convention is explicit (CLAUDE.md §9).
5. **The probe copy `safe_amr_FIOPROBE` has not been deleted yet.** §0.1 rule 3
   asks for it on any abort; the working project was never touched, so this is
   housekeeping rather than risk.
