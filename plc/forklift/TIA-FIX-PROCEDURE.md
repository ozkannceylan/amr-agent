# TIA fix procedure — the m5-59 validation fixes, one step at a time

**Who this is for.** One session at TIA Portal, in exactly the shape of
`plc/forklift/TIA-BUILD-PROCEDURE.md`, whose 360 steps are already walked: the
owner is at the tool, one step per message, one physical action and one
observable each. **This document's steps are numbered from 1 and the build
procedure's 360 are untouched.**

**Why there is a fix procedure at all.** `docs/VALIDATION-M5.md` ran the whole
chain against the finished program and found four things. Three of them need the
CPU. This is those three, and **only** those three, gathered into one sitting so
there is no second one.

## What this session changes, and it is exactly six things

| # | Change | Side | Finding |
|---|---|---|---|
| 1 | `SPEED_STANDSTILL_MAX` `50` → **`15`** | F-program | F2 |
| 2 | `SPEED_STANDSTILL_NEG` `-50` → **`-15`** | F-program | F2 |
| 3 | `SPEED_LIMIT_ONSET_MAX` `T#1s500ms` → **`T#2s300ms`** | F-program | F4 |
| 4 | `ForkliftSafetyMirror` gains **two Bools**, and the FB body gains two mirror copies and a third permissive conjunct | standard | F1 |
| 5 | The warning ceiling reaches the **teleop** setpoint: one temp, one new statement, one modified statement | standard | F4 |
| 6 | `Forklift/Safety/` gains **two leaves**, four → six | server interface | F1 |

Changes 1–3 are **one value each in a Constant row**. Nothing in the F-program's
logic moves: no network is added, no pin is re-pointed, no interface row is
created. Changes 4–6 are the standard side and the address space.

## What this session does NOT do, and no step may be added that does it

> **No acceptance testing.** The writer stays down, the bridge stays down, the
> HMI stays down, Gazebo stays down. Every figure this session produces is a
> value read out of the tool. The runs that prove behaviour are listed under
> *What must be re-run* below and belong to a later sitting with the stack up.

> **No `WARN` sender, no bridge slot, no node-model edit.** Those are the
> agent-side halves of the same findings (`docs/reports/m5-59-validation-fix-triage.md`).
> Nothing here is improvised at the keyboard to stand in for one.

> **No new threshold is decided at the tool.** Every number above is derived in
> `plc/forklift-safety/SPEC.md` §11.1b and §11.3 and in `plc/forklift/SPEC.md`
> §14.17. If a value in front of you disagrees with this document, stop and say
> so; do not reconcile it by typing.

## The F-signature changes, and what that costs

The build in front of you is signed **`50573CD9`**, and **every figure in
`docs/VALIDATION-M5.md` was measured against it.** Changes 1–3 change it. That
is expected and is the delta's own evidence — but it means the validation
document's run identity is spent.

**What must be re-run before any of these numbers is quoted again:**

| `docs/VALIDATION-M5.md` | Why it must be re-run | What is expected to change |
|---|---|---|
| §0 boot state | Two mirror nodes are new; `TorqueOffDemand` boots `TRUE` | Two more rows in the table |
| §1.1 scanner stops (V1) | Standard-side permissive gained a conjunct | Nothing — but it is a different program |
| §1.2 / §5 scanner slows (V5) | **This is the run F4 exists for.** With the `WARN` sender in place the teleop vehicle must now slow to 0.20 m/s at the warning trip and stop at the protective boundary | The 1.000 m/s row becomes a 0.20 m/s row |
| §2 e-stop (V2) | Same program change; latency figures are chain figures | Re-measure, do not carry over |
| §3 the shaft-doubt band | **The reproduction must now fail to reproduce.** Same 0.02 m/s creep, encoders 15–26 mm/s, and no `ShaftDoubtNow` | The demand does not form |
| §3 autonomous mission (V3) | The band was what stopped it in its first metre | A mission that leaves rest |
| §4 safety in autonomous (V4) | Never run; unblocked by the above | First result |
| §6.1 AT-10 / SS1 | The onset budget moved by 0.80 s and the standstill window narrowed | Enforcement starts later; SS1 stage two unchanged |
| §6.2 the demand reaches the plant | **This is the run F1 exists for** | Publisher count 1, six leaves, motion refused under a standing demand |

**The claim boundary is unchanged and applies to every reading below.** This
project claims **PLr targets only**. **No Performance Level, Category, SIL or PFH
is claimed, achieved or implied** by anything in this procedure. The whole
safety input path is a labelled stand-in: standard data, written by an
engineering process, over a TCP link.

---

## Progress — the session updates this section

Rewrite these three fields whenever a step completes, and always before the
session ends. Resuming then costs nothing.

    chunk:               AA–AG done
    steps done:          63 of 63
    open:                nothing in TIA. The re-run table at the top of this
                         document is owed, with the stack up, against
                         F-signature 29FD2C52

---

## Record table

These are values only the tool can produce. Fill each in when the step that
produces it passes, with its date. **Until a row is filled, the value is a
design value and no gate criterion may rest on it** (ADR 0006).

| Record | Value | Date |
|---|---|---|
| Project and instance read back (steps 1–2) | Project `safe_amr`; PLCSIM Advanced instance `safecell3` | 2026-08-07 |
| F-collective signature **before** (step 3) — expected `50573CD9` | `50573CD9` offline = `50573CD9` online, version comparison green. Collective F-SW `50573CD8`, F-HW `00000001`, F-communication address signature `none` | 2026-08-07 |
| Safety mode state before (step 4) | safety mode activated | 2026-08-07 |
| Machine quiet: writer, bridge, HMI (steps 5–6) | Windows process sweep by command line: no stand-in writer, no PLCSIM Advanced API client. Only PLCSIM Advanced itself (Runtime Manager PID 22324, instance PID 14420) and two unrelated PostgreSQL `bgwriter`/`wal_writer` children the `writer` pattern matched. WSL: no bridge, no HMI, no OPC UA process | 2026-08-07 |
| Interface ruling for the two new mirror leaves (step 7) | **Ruled, gate open.** `docs/interfaces/opcua-nodes.md` §11 is six nodes (m5-60). `SpeedMonitorDemand` Bool/`Boolean`, accessible ✔, writable ✘, start `FALSE`; `TorqueOffDemand` Bool/`Boolean`, accessible ✔, writable ✘, start `TRUE`. Ruled names agree character for character with the names requested below, so chunks AD–AF are unchanged and chunk AE is not blocked | 2026-08-07 |
| `WARN` sender present? (step 8) | **Yes** — `docs/reports/m5-61-warn-sender.md`, status `done`. `field_evaluation.py` sends `WARN` on the 45015 link; `WarningFieldClear` read `True` for the first time, reaching `WarningFieldClearValid` 17 ms later; n = 4 intrusions / 4 member changes, n = 5 controls / 0 verdicts. After the step-52 download: full teleop speed with a clear field, 0.20 m/s while occupied, no latch | 2026-08-07 |
| Constant count after the three edits (step 14) — expected **17**, unchanged | **17**, unchanged (rows 69–85). `SPEED_STANDSTILL_MAX` `15`, `SPEED_STANDSTILL_NEG` `-15`, `SPEED_LIMIT_ONSET_MAX` `T#2s300ms`. SL13's four comparator pins all symbolic — `#SPEED_STANDSTILL_MAX` / `#SPEED_STANDSTILL_NEG`, one pair per channel, no literal, resolving to 15 / −15 at the pin (step 15). SL17's `PT` symbolic `#SPEED_LIMIT_ONSET_MAX`, resolving to `T#2s300ms`, `IN` the negation of `#WarningFieldClearValid` (step 16) | 2026-08-07 |
| Safety compile result (step 17) | **0 errors, 0 warnings.** Downloaded in the same action: CPU taken to STOP for the safety download, then RUN (steps 18–20) | 2026-08-07 |
| F-collective signature **after** (step 22) — must differ from `50573CD9`, offline = online | **`29FD2C52`** offline = `29FD2C52` online, version comparison green. Collective F-SW `29FD2C51`; F-HW `00000001` **unchanged**, correctly — no hardware or F-communication change was made, only three constant values. This is the run identity every re-run in the table above must be measured against | 2026-08-07 |
| `SpeedLimitOnsetTimer.PT` in force **with its `IN`** (step 24) | `PT` = **`T#2S_300MS`** with `IN` = **`TRUE`** — the timer is running, so the `PT` read is the value and not the instrument. `IN` is `TRUE` because no field source is running, `WarningFieldClearValid` is `FALSE` and this timer's `IN` is its negation. Safety mode read back **activated** after the download (step 23) | 2026-08-07 |
| No-source signature re-read (step 26) | **All thirteen as the build's step 333 recorded them.** `SpeedChainSeen` `FALSE`; `SpeedAValid` `FALSE`, `SpeedBValid` `FALSE`; `SpeedStaleNow` `FALSE`, `SpeedDiscrepantNow` `FALSE`, `ShaftDoubtNow` `FALSE`, `SpeedOverLimitNow` `FALSE`; `SpeedCauseGone` **`TRUE`**; `SpeedMonitorDemand` `FALSE`; `WarningFieldClearValid` `FALSE`; `SpeedLimitOnsetTimer.ET` `T#2S_300MS` — **at `PT` and not climbing**, the new budget; `Ss1Demand` **`TRUE`**, tracking the boot-latched zone demand; `TorqueOffDemand` **`TRUE`**. Neither defect signature present. Read alongside: `SpeedDiff` `0`, `VehicleStandstillNow` `FALSE`, `Ss1Timer.ET` `T#1S` at `PT` (expired), `SpeedAStaleTimer.PT` / `SpeedBStaleTimer.PT` `T#500MS`, `SpeedDiscrepancyTimer.PT` `T#200MS`, `ShaftDoubtTimer.PT` `T#1S`, `SpeedOverLimitTimer.PT` `T#200MS`, `ShaftDoubtTimer.IN` `FALSE` (step 25) | 2026-08-07 |
| Body diff before the paste (step 38) — expected exactly three hunks; if a wall of hunks, the `--ignore-cr-at-eol -w` count too | Body captured from TIA (440 lines) as `plc/forklift/evidence/m5-59-fb-body-before.scl`; committed file 465 lines. **Raw `git diff --no-index`: 27 hunks. With `--ignore-cr-at-eol -w`: 5.** The three expected deltas are all present and are hunks 1, 4 and 5 — (1) the two mirror assignments **and** the third `#safetyDemandClear` conjunct, together in one hunk as the procedure predicted; (4) the `#teleopSpeedCap` `IF … ELSE` block; (5) `#tractionDemand * #speedCap` → `* #teleopSpeedCap`. **Hunks 2 and 3 are not drift**: `#HmiStaleTimer(…)` and `#BridgeStaleTimer(…)` are one line in the committed file and two lines in the CPU body — identical tokens, identical arguments, a line wrap only, which `-w` cannot fold because it is a newline and not whitespace within a line. No substantive difference outside the three deltas; step 39 replaces the whole body regardless | 2026-08-07 |
| Search for `#tractionDemand * #speedCap` (step 43) — expected **zero** hits | **0 hits**, searched in TIA over the pasted body. Read back from the same body: part 0 carries **six** unconditional mirror assignments (step 40); `#safetyDemandClear` carries **three** conjuncts, all from `"InstF_Forklift_Safety"` and none from a mirror, with `TorqueOffDemand` deliberately absent (step 41); part 7's traction statement is `#tractionDemand * #teleopSpeedCap` inside the same `IF … ELSE` whose `ELSE` still assigns `0.0` (step 42) | 2026-08-07 |
| Standard compile result (step 44) | Compiled with **no error** — reported by the owner and corroborated by a successful download and solid green diff circles on every block; warning count not read off. **Downloaded in the same action, ahead of chunk AE**, and TIA offered **re-initialisation of `ForkliftSafetyMirror`, which was accepted** — the DB layout had moved, so this is step 52's requirement met early and the two new members took their start values rather than an old image. Safety mode read back **activated**; offline and online safety programs both consistent; collective F-signature still **`29FD2C52`** offline = online, **correctly unmoved** — a standard-program change does not touch it. Chunk AE therefore runs against a CPU that already carries the six mirrors, and the step-52 download becomes an interface-only download | 2026-08-07 |
| Six leaves under `Forklift/Safety/`, no `_1` (step 49) | **6**, read character for character: `TorqueOffDemand`, `SpeedMonitorDemand`, `EStopDemand`, `ZoneStopDemand`, `SafetyResetRequired`, `SafetyResetFault` — **no `_1` on either new name**. All six `BOOL`, all six access level **`RD`**, read-only: no client may write any of them (step 48). Each points at its `"ForkliftSafetyMirror"` member of the same name. The two new leaves sit at the top of the folder rather than the bottom, which is display order only and is not part of any browse path | 2026-08-07 |
| Browse-name count after the download (step 56) — expected **48** | **48**, as expected — 46 plus two leaves and **no new folder** (`Forklift` still has its eleven subfolders). The collision-suffix sweep found **none**. The nine §12 nodes all read back with their types and values; the envelope write probe was still refused `BadNotWritable`. `RESULT: PASS`. The script was **not edited** and knows nothing about the two new nodes. Run from a Windows shell outside TIA against `opc.tcp://192.168.53.1:4840`; saved as `plc/forklift/evidence/m5-59-node-verify-2026-08-07.log` (step 57) | 2026-08-07 |
| Write refused on a new mirror leaf, with its status code (step 59) | **`BadNotWritable`** — word for word: *"The access level does not allow writing to the Node.(BadNotWritable)"*. The probe wrote back the value the node already held, so nothing could have changed had it been accepted. Read first from the same shell (step 58): `Forklift/Safety/SpeedMonitorDemand` `Boolean` **`False`**, `Forklift/Safety/TorqueOffDemand` `Boolean` **`True`**, both `access={CurrentRead}` — read-only at the server, not by convention. Evidence: `plc/forklift/evidence/m5-59-safety-leaf-probe-2026-08-07.log` and the script beside it | 2026-08-07 |
| Four-row mirror/F-data comparison (step 60) | `"ForkliftSafetyMirror".SpeedMonitorDemand` `FALSE`; `"ForkliftSafetyMirror".TorqueOffDemand` **`TRUE`**; `"ForkliftStatus".ForkliftTeleopActive` `FALSE`; `"ForkliftOutput".ForkliftTractionSpeedRef` `0.0`. **No monitoring-error icon on any row.** **This is not evidence of the new conjunct**: with no writer running both F-demands stand for reasons that predate this session, so `TeleopActive` is `FALSE` and the setpoint `0.0` several times over. The conjunct is proven only by an acceptance run with the stack up — the re-run table at the top of this document | 2026-08-07 |
| Mirror vs F-data, compared by eye (step 55) | **Both pairs equal.** `"ForkliftSafetyMirror".SpeedMonitorDemand` `FALSE` = `"InstF_Forklift_Safety".SpeedMonitorDemand` `FALSE`; `"ForkliftSafetyMirror".TorqueOffDemand` **`TRUE`** = `"InstF_Forklift_Safety".TorqueOffDemand` **`TRUE`**. Read after the STOP → RUN of step 54, so the mirrors are the running copy and not a stale image. `SpeedLimitOnsetTimer.PT` still `T#2S_300MS` with `IN` `TRUE` across the restart | 2026-08-07 |

---

## Before step 1 — what must be true

| # | Precondition | How to know |
|---|---|---|
| 1 | The working project is **`safe_amr`** | Step 1 reads the title bar |
| 2 | The CPU is the as-built 2026-08-06 program: FB2 at **49 networks**, interface **10 / 6 / 44 / 17**, collective signature **`50573CD9`** | Step 3 reads the signature and stops if it differs |
| 3 | **Nothing is holding the CPU** — no stand-in writer, no bridge, no HMI, no leftover PLCSIM API session | Steps 5–6, **by process identity on every transport**. The writer is **not** an OPC UA client and opens no socket on 4840, so `netstat` on that port proves nothing (LESSONS 2026-08-06) |
| 4 | `docs/interfaces/opcua-nodes.md` §11.2 carries rows for `SpeedMonitorDemand` and `TorqueOffDemand` | Step 7 is the gate. **Without it, chunks AA–AD run and chunk AE does not** |
| 5 | The committed `plc/forklift/scl/FB_ForkliftTeleop.scl` carries the F1 and F4 deltas | Step 38 diffs it against what is actually in the CPU before anything is pasted |

**If reality does not match a step, stop and say so.** A wrong keystroke in a
safety project costs more than a question, and this document was written by an
author who cannot run TIA Portal: menu wording and dialog placement move between
versions, so the steps name **what to look for**, not a verified click path.

---

## Chunk AA — ground truth, and the two gates

*Ends with: the signature before, a quiet machine, and a yes/no on each gate.*

**1.** Read the **title bar**.
*Tell me:* the project name.
*Expected:* `safe_amr`.

**2.** Read the **PLCSIM Advanced control panel** instance name.
*Tell me:* the name.
*Expected:* `safecell3`.

**3.** Go online and read the **collective F-signature**, offline and online.
*Tell me:* both values.
*Expected:* `50573CD9` = `50573CD9`.
**If they differ from each other, or from `50573CD9`, stop.** Something has
changed the F-program since the validation run, and every figure in
`docs/VALIDATION-M5.md` is against that build. Say what you see and we re-plan.

**4.** Read the **safety mode** state.
*Tell me:* what it says.
*Expected:* safety mode activated.

**5.** On the **Windows host**, list running processes whose command line names
the stand-in writer or a PLCSIM Advanced API client.
*Tell me:* what the list contains.
*Expected:* nothing.
**Trap, and this project has paid for it twice.** The writer holds a **PLCSIM
Advanced API session**, not an OPC UA one — it opens no socket on 4840, so a
`netstat` on that port is a weaker claim than it looks (LESSONS 2026-08-06). And
**exclude the sweep from itself**: a pattern of `bridge|hmi` matches its own
command line.

**6.** In **WSL**, check that the bridge and the HMI are not running.
*Tell me:* both confirmed.
**Why it matters:** a download drops the CPU's OPC UA sessions mid-read, and
this project has already lost an evidence run and killed a bridge on an
unhandled in-flight exception that way (LESSONS 2026-07-28).

**7. GATE — the interface ruling.** Open `docs/interfaces/opcua-nodes.md` §11.2
and look for rows named `SpeedMonitorDemand` and `TorqueOffDemand`.
*Tell me:* whether both are there, and if they are, the **exact leaf names,
per-tag rights and start values** the document rules.
**If they are not there, chunk AE is BLOCKED and chunks AA–AD stand on their
own.** The leaf name is the diff key between the node model, the TIA export and
`plc/forklift-safety/SPEC.md` §6.1, and typing a browse path against an unruled
name is how two documents start disagreeing (LESSONS 2026-07-30; step 338 of the
build procedure is the same gate one node earlier). **Every name below is the
requested one. Where the ruling differs, the ruling wins and you tell me before
typing it.**

**8. GATE — the `WARN` sender.** Ask whether `agv/forklift/scripts/field_evaluation.py`
now sends the `WARN` line on the 45015 field link.
*Tell me:* yes or no.
**This does not block the session** — it decides what the next run may expect:

| Answer | What it means for the vehicle after this download |
|---|---|
| **Yes** | The warning field selects the F-side limit only while it is occupied. Full teleop speed with a clear field; 0.20 m/s while occupied; no latch |
| **No** | `WarningFieldClear` is permanently `FALSE`, so the 300 mm/s limit is permanently enforced. After the step-52 download the coupling is live, so **any drive above 0.30 m/s latches `SpeedMonitorDemand` and refuses motion until a monitored reset** — correct behaviour, and it ends the 1.000 m/s teleop clip |

**9.** Write today's date and the answers to steps 1–8 into the **record table**
above.
*Tell me:* done.

> **Chunk AA done.** Nothing has been changed. We know which build is in the
> CPU, that no client is holding it, and which of the two chunks ahead is gated.

---

## Chunk AB — the three F-constants (`plc/forklift-safety/SPEC.md` §11.3)

*Ends with: three values changed in FB2's Constant section and a clean safety
compile. No network is touched.*

**10.** Open **`F_Forklift_Safety [FB2]`** and scroll to the **Constant**
section. Read the current value of **`SPEED_STANDSTILL_MAX`**.
*Tell me:* the value.
*Expected:* `50`.

**11.** Change **`SPEED_STANDSTILL_MAX`** to **`15`**.
*Tell me:* the row as it now reads.
*Why 15 and not 50:* §11.1b. `50` was 9 σ of the reading heads' jitter wide and
swallowed every speed the vehicle actually executes — the 0.02 m/s teleop creep
that read 15–26 mm/s, and Nav2's 25 mm/s from rest. `15` sits inside the
admissible window 11.6 … 18.0 mm/s that the detection and exclusion bounds leave
open, and the derivation is on the row.

**12.** Change **`SPEED_STANDSTILL_NEG`** to **`-15`**.
*Tell me:* the row, and that the negative value was accepted.

**13.** Change **`SPEED_LIMIT_ONSET_MAX`** to **`T#2s300ms`**.
*Tell me:* the value exactly as it reads **back** — TIA normalises the literal,
so `T#2S300MS` is the same value and is what you should expect to see.
*Why 2.30 s:* §11.3. The old 1.50 s ramped from the autonomous ceiling, which
was silently a statement that the vehicle is never in teleop when the field
trips. It is: 0.35 s of verdict-to-ceiling plus (1.00 − 0.20) / 0.50 = 1.60 s of
ramp = 1.95 s worst compliance, plus the same 0.35 s transport margin. 23
F-cycles.

**14.** Read the **Constant count** back.
*Tell me:* the number.
*Expected:* **17**, unchanged.
**Trap.** A value change must not add a row. If it reads 18, a new constant was
created beside the old one and the old one is still what the pins read.

**15.** Open **network 20**, `SpeedNearZero` (SL13), and read its **four
comparator pins**.
*Tell me:* the four operands.
*Expected:* `#SPEED_STANDSTILL_MAX` and `#SPEED_STANDSTILL_NEG`, symbolic, twice
each — one pair per channel.
**Why this step exists.** If any pin carries a **literal** `50`, the constant
edit above reaches nothing and the band is still open. A constant is only in
force where it is named.

**16.** Open **network 24**, `SpeedLimitOnsetTimer` (SL17), and read its `PT`
pin.
*Tell me:* the operand.
*Expected:* `#SPEED_LIMIT_ONSET_MAX`, symbolic — not a literal time.

**17.** **Compile the safety program.**
*Tell me:* the error and warning counts.
**Stop on any error.**

> **Chunk AB done.** The three values are changed in the project. They are not
> in the CPU yet, and the signature has not moved.

---

## Chunk AC — the F download, and the signature that proves it

*Ends with: a new collective F-signature, recorded, and the three timers read
back in force.*

**18.** Put the CPU in **STOP**, as the safety download requires.
*Tell me:* the state.

**19.** **Download to device.** Let it finish.
*Tell me:* that it completed, and what the dialog reported — including whether
it offered **re-initialisation**.
**Note, and it is the opposite of the build's step 312.** Only constant *values*
changed, and constants compile into code rather than into `DB3`, so **no DB
layout moved and re-initialisation is not required here.** If TIA offers it
anyway, accepting is harmless — nothing in `DB3` is Retain — and it clears
`SpeedChainSeen`, which the STOP → RUN below does regardless.

**20.** Put the CPU in **RUN**.
*Tell me:* the state.

**21.** Check the **diff circles** are **solid green** on every block.
*Tell me:* what they show.
**Test nothing until they are.** A stale build shows as silent refusals,
monitoring-error icons and an in-force value that contradicts the call site
(LESSONS 2026-07-28).

**22.** Read the **collective F-signature**, offline and online.
*Tell me:* both values.
*Expected:* **a new value, offline = online, different from `50573CD9`.**
**If it still reads `50573CD9`, the download did not take** and everything below
is being read off the old program. Record the new value in the record table with
today's date.

**23.** Read the **safety mode** state back.
*Tell me:* what it says.
*Expected:* activated.

**24.** In the watch table, read `"InstF_Forklift_Safety".SpeedLimitOnsetTimer.PT`
**together with its `.IN` state**.
*Tell me:* both.
*Expected:* `T#2S300MS`, with `IN` **`TRUE`** — no field source is running, so
`WarningFieldClearValid` is `FALSE` and this timer's `IN` is its negation.
**Trap, and it cuts both ways.** An IEC timer reports `PT` as `T#0MS` while it is
not running, so a `PT` read with `IN` `FALSE` is the instrument and not the value
(LESSONS 2026-08-05). This one runs, so it can be read honestly.

**25.** Read `"InstF_Forklift_Safety".ShaftDoubtTimer.PT` with its `.IN`.
*Tell me:* both.
*Expected:* `T#1000MS` with `IN` `FALSE` — unchanged by this session, and the
`PT` persists because the timer has run on this block before.

**26.** Put the **Group 5** rows of `plc/forklift-safety/SPEC.md` §11.8 in
**Monitor** and read the no-source signature.
*Tell me:* the thirteen values.
*Expected, exactly as the build's step 333 recorded them:* `SpeedChainSeen`
`FALSE`, both valids `FALSE`, `SpeedStaleNow` `FALSE`, `SpeedDiscrepantNow`
`FALSE`, `ShaftDoubtNow` `FALSE`, `SpeedOverLimitNow` `FALSE`, `SpeedCauseGone`
**`TRUE`**, `SpeedMonitorDemand` `FALSE`, `WarningFieldClearValid` `FALSE`,
`SpeedLimitOnsetTimer.ET` at `PT` and not climbing, `Ss1Demand` tracking the zone
latch, `TorqueOffDemand` `TRUE`.
**Two readings would be a defect signature:** `SpeedChainSeen` `TRUE` with no
source ever started, or `SpeedCauseGone` `FALSE` blocking a reset in a run with
no speed chain.

**27.** Screenshot the Group 5 rows and the Constant section, saved as
`plc/forklift-safety/evidence/m5-59-f-constants-in-force.png`.
*Tell me:* saved.

> **Chunk AC done.** The F-program's standstill window and onset budget are in
> the CPU, the signature has moved and is recorded, and the monitor is still
> silent because it has still never met its measurement.

---

## Chunk AD — the standard side: two DB members, one temp, one paste

*Ends with: the FB body carrying the F1 and F4 deltas and compiling clean.*

**28.** Open the **`ForkliftSafetyMirror`** DB and read the **member count**.
*Tell me:* the number.
*Expected:* **4**.

**29.** Add the member **`SpeedMonitorDemand`**, type **`Bool`**, start value
**`FALSE`**.
*Tell me:* the row and the start value as it reads.

**30.** Add the member **`TorqueOffDemand`**, type **`Bool`**, start value
**`TRUE`**.
*Tell me:* the row and the start value as it reads.
**`TRUE` is not a typo and it is not the fail direction — it is the source's
own start-state truth.** `ZoneStopDemand` boots latched, so `Ss1Demand` stands
from the first believed F-cycle and `Ss1Timer` expires within a second of every
boot: `TorqueOffDemand` really does read `TRUE` at a cold start. A mirror's start
value is its source's (`plc/forklift-safety/SPEC.md` §11.8, §6.4).

**31.** Set both new members: *Accessible from HMI/OPC UA* **✔**, *Writable from
HMI/OPC UA* **✘**.
*Tell me:* the four checkbox states.
**Nothing a client writes may reach the F-layer** — that is this group's defining
property, not a restriction on it (invariant 1).

**32.** Confirm neither new member is marked **Retain**.
*Tell me:* the Retain column for both.

**33.** Read the whole member list back and look for a trailing **`_1`** on
either new name.
*Tell me:* the six names, character for character.
**TIA appends `_1` without asking, in DB statics and interface rows both, and a
silent one once cut the bridge with no error dialog** (LESSONS 2026-07-30).

**34.** Open **`FB_ForkliftTeleop`** and read the current **Temp count**.
*Tell me:* the number.

**35.** Add the Temp **`teleopSpeedCap`**, type **`Real`**.
*Tell me:* the row.

**36.** Read the Temp count back.
*Tell me:* the number.
*Expected:* **exactly one more than step 34.**

**37.** Select the **entire FB body** in TIA, copy it, and save it to
`plc/forklift/evidence/m5-59-fb-body-before.scl`.
*Tell me:* the file name and its line count.

**38.** At a shell, compare that file with the committed body:

    git diff --no-index plc/forklift/evidence/m5-59-fb-body-before.scl plc/forklift/scl/FB_ForkliftTeleop.scl

*Tell me:* how many hunks it reports, and what each one is.
*Expected:* **exactly three** — the two mirror assignments plus the third
conjunct, the `#teleopSpeedCap` block, and the traction statement.

**If you get a wall of hunks instead — most or every line differing — do not
conclude drift yet. Re-run the same compare ignoring line endings and
whitespace:**

    git diff --no-index --ignore-cr-at-eol -w plc/forklift/evidence/m5-59-fb-body-before.scl plc/forklift/scl/FB_ForkliftTeleop.scl

*Tell me:* the hunk count from **both** commands. Then read the result this way:

| First command | Second command | What it means, and what to do |
|---|---|---|
| three hunks | not needed | The bodies agree outside the three deltas. **Go to step 39.** |
| many hunks | **three hunks** | An artefact of the copy-out, not drift: TIA's editor re-indented or re-cased the body, or it came out LF against this CRLF working tree. SCL is not whitespace-sensitive and step 39 replaces the whole body anyway, so nothing is lost. **Go to step 39**, and record in the table that the first count was a whitespace artefact |
| many hunks | **more than three** | **Real drift. Stop and tell me what the extra hunks are.** The CPU's body and the committed file differ in substance, and the paste in step 39 would silently revert whatever drifted |
| three hunks, but not *these* three | — | **Stop and tell me.** A right count of wrong hunks is drift that happens to be the same size |

**Why the fallback and not the stop rule alone.** `git diff --no-index`
compares raw bytes, so a single editor-side normalisation makes a clean body
read as a total rewrite — a defect that does not exist, discovered alone at
the keyboard. The second command answers that question in one line; only when
it still disagrees is there something to stop for.

**39.** Select the **whole** FB body in TIA and paste
`plc/forklift/scl/FB_ForkliftTeleop.scl` over it, **in one paste**.
*Tell me:* that it is in.
**This is the standing method, not a preference.** A multi-line SCL statement
typed by hand at a named insertion point once landed **inside** another statement
and split it in two, which compiles as neither (LESSONS 2026-08-06). The file is
edited in the repository first so the file and the CPU agree by construction.

**40.** Read **part 0** back.
*Tell me:* how many mirror assignments it contains.
*Expected:* **six**, each one unconditional and each from one F-flag of the same
name.

**41.** Read the **`#safetyDemandClear`** statement back.
*Tell me:* its conjuncts.
*Expected:* three — `NOT EStopDemand`, `NOT ZoneStopDemand`, `NOT
SpeedMonitorDemand`, all read from `"InstF_Forklift_Safety"` and **none** from a
mirror.
**`TorqueOffDemand` is deliberately not a conjunct here.** It is a strict
consequence of causes already in this term, and its consumer is the vehicle's
inhibit, not the cell's permissive.

**42.** Read **part 7**'s traction statement back.
*Tell me:* the statement.
*Expected:* `#tractionDemand * #teleopSpeedCap`, inside the same `IF … ELSE`
whose `ELSE` still assigns `0.0`.
**The mandatory `ELSE` is the gate.** A `Real` left unwritten holds its last
value and the bridge keeps republishing it, and the machine keeps moving after
the stop (LESSONS 2026-07-27).

**43.** Search the whole body for **`#tractionDemand * #speedCap`**.
*Tell me:* the hit count.
*Expected:* **zero**.
**Verify a re-point by searching for what must no longer be there**, never by
re-reading what should now be there: a search returns zero or it does not
(LESSONS 2026-08-05).

**44.** **Compile the standard program** — *Software (only changes)*.
*Tell me:* the error and warning counts.
**Stop on any error.**

> **Chunk AD done.** The standard program mirrors six flags and refuses motion
> on the speed monitor's demand, and the warning ceiling reaches the teleop
> setpoint. None of it is in the CPU yet.

---

## Chunk AE — the two mirror leaves (**gated on step 7**)

*Ends with: six leaves under `Forklift/Safety/`, read back by name.*

**45.** Open the **`DemoCell`** server interface, folder `Forklift` →
`Safety`. Read the **leaf count**.
*Tell me:* the number.
*Expected:* **4**.

**46.** Drag `ForkliftSafetyMirror`'s **`SpeedMonitorDemand`** into `Safety`, and
read the leaf name back.
*Tell me:* the leaf name character for character.
**Rename nothing, and look hard for a trailing `_1`. Do not rename the interface
itself, ever** — the interface name **is** the namespace URI (ADR 0006), and a
rename silently breaks every browse-by-URI at connect.

**47.** Drag **`TorqueOffDemand`** into `Safety`, and read the leaf name back.
*Tell me:* the leaf name character for character.

**48.** Read the **access level** of both new leaves.
*Tell me:* what each says.
*Expected:* read-only. No client may write either.

**49.** Read the **leaf count** back.
*Tell me:* the number and the six names.
*Expected:* **6**.

**50.** **Compile** — *Software (only changes)*.
*Tell me:* the error and warning counts.

> **Chunk AE done.** The two demands have an address. Nothing reads them yet —
> the bridge's slot is an agent-side change and is not made here.

---

## Chunk AF — download, and prove it from outside TIA

*Ends with: the address space grown by exactly two leaves, proven by a client
that is not TIA.*

**51.** Confirm again that the writer, the bridge and the HMI are still not
running.
*Tell me:* all three confirmed.

**52.** **Download to device.** Let it finish.
*Tell me:* that it completed, what the dialog reported, and whether it offered
**re-initialisation of `ForkliftSafetyMirror`**.
**This one is the opposite of step 19.** Two members were added, so the DB layout
moved and TIA should ask. **Accept it** — nothing in that DB is Retain, and
without it the two new members keep whatever the old image held rather than
taking their start values (LESSONS 2026-08-05).

**53.** Check the **diff circles** are **solid green** on every block.
*Tell me:* what they show.

**54.** If step 52 did **not** re-initialise, take the PLCSIM instance
**STOP → RUN**.
*Tell me:* which of the two happened.
**A start value governs a DB that does not exist yet.** Once the DB is on the
CPU, only a restart or an explicit re-initialisation applies one — this project
typed two `TRUE`s twice before finding that out (LESSONS 2026-08-05).

**55.** In the watch table, read the two new **mirror** members beside their two
**F-data** sources.
*Tell me:* the four values.
*Expected:* each mirror equal to its source, `TorqueOffDemand` `TRUE`.
**Compare the two columns by eye.** A checker that prints two values without
comparing them is a display, not a check, and this project has a `PASS` line in
its history that stood over a mismatch (LESSONS 2026-08-05).

**56.** Run the node check from a shell **outside** TIA:

    python plc/forklift/evidence/m5-25-node-verify.py opc.tcp://192.168.53.1:4840

*Tell me:* the browse-name count, whether the sweep found any `_1`, and the
`RESULT:` line.
*Expected:* **48** browse names — 46 plus two leaves and **no new folder** — no
suffix, the nine §12 nodes still reading back, and the envelope write still
`BadNotWritable`.
**This script knows nothing about the two new nodes and is not edited to.**

**57.** Save that output to
`plc/forklift/evidence/m5-59-node-verify-<today's date>.log`.
*Tell me:* the file name you used.

**58.** From the same shell, **read** `Forklift/Safety/SpeedMonitorDemand` and
`Forklift/Safety/TorqueOffDemand`.
*Tell me:* both values.

**59.** From the same shell, **attempt a write** to
`Forklift/Safety/SpeedMonitorDemand`.
*Tell me:* the status code, word for word.
*Expected:* a refusal — `BadNotWritable` or the server's equivalent.
**This is the group's defining property under test, not a formality.** Nothing a
client writes may reach the F-layer.

> **Chunk AF done.** The F-program's speed monitor and its SS1 sequencer now
> reach the standard program's permissive and the address space. Whether they
> reach the **vehicle** depends on the bridge slot, which is an agent-side change
> and is not in this session.

---

## Chunk AG — the record, and the stop point

**60.** In the watch table, put these four rows in Monitor together:
`"ForkliftSafetyMirror".SpeedMonitorDemand`, `.TorqueOffDemand`,
`"ForkliftStatus".ForkliftTeleopActive`, `"ForkliftOutput".ForkliftTractionSpeedRef`.
*Tell me:* the four values, and whether any row shows a monitoring-error icon.
**Do not read this as proof of the new conjunct.** With no writer running, both
F-demands stand for reasons that predate this session, so `TeleopActive` is
`FALSE` and the setpoint is `0.0` several times over. **The new conjunct is
proven by an acceptance run with the stack up**, in the re-run table at the top
of this document — a step that expects a value inside a branch its own
preconditions make unreachable is a defective step, and this project wrote a
lesson for it (LESSONS 2026-08-06).

**61.** Fill in every remaining row of the **record table** with its date.
*Tell me:* done.

**62.** Rewrite the **progress block**.
*Tell me:* done.

**63.** Save the project.
*Tell me:* saved.

---

## The stop point — what "done" looks like

The session is finished when **all seven** of these are true, and not before:

| # | Done means |
|---|---|
| 1 | The collective F-signature has **changed from `50573CD9`**, offline = online, and the new value is in the record table with today's date |
| 2 | `SpeedLimitOnsetTimer.PT` reads **`T#2S300MS` in force with its `IN` `TRUE`**, and SL13's four pins are symbolic |
| 3 | Safety mode reads **activated** after the download |
| 4 | The FB body's part 0 has **six** mirror assignments, `#safetyDemandClear` has **three** conjuncts, and the search for `#tractionDemand * #speedCap` returns **zero** |
| 5 | `Forklift/Safety/` has **six** leaves, none with a `_1`, and a client write to one is **refused with a status code you have written down** |
| 6 | Both new mirror members equal their F-data sources in the watch table, compared by eye |
| 7 | The record table has **no empty row**, and the progress block says so |

**And one thing that is deliberately not on that list.** Nothing in this session
proves a behaviour. Six values changed and an address space grew; the four
findings are closed when the runs in the re-run table have been made with the
stack up and `docs/VALIDATION-M5.md` carries a new run identity. **No PL,
Category, SIL or PFH is claimed by any of it.**

---

## Step index

| Chunk | Steps | Ends with |
|---|---|---|
| AA — ground truth and gates | 1–9 | signature before, quiet machine, both gates answered |
| AB — the three F-constants | 10–17 | three values changed, clean safety compile, 17 constants |
| AC — F download | 18–27 | **new F-signature**, three timers in force, no-source signature re-read |
| AD — standard side | 28–44 | six mirrors, three conjuncts, one temp, clean compile |
| AE — the two mirror leaves | 45–50 | six leaves — **gated on step 7** |
| AF — download and prove | 51–59 | 48 browse names, write refused |
| AG — record and stop | 60–63 | record table full, project saved |

**63 steps.** If a step turns out to contain two actions, split it and say the
total has changed.

**The ordering constraints are exactly two:** chunk AC finishes before chunk AD
begins, so the F-signature change is attributable to the three constants and to
nothing else; and **chunk AE does not start until step 7's ruling exists.**
