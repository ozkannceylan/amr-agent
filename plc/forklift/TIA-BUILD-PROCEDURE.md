# TIA build procedure — the M5 standard-program delta, one step at a time

**Who this is for.** One session at TIA Portal, driven by
`docs/TIA-SESSION-PROMPT.md`: the owner is at the tool, the session gives
**exactly one step per message** and waits. Every step below is one physical
action with one observable result, so the session always has something to ask
about and the owner never has to hold two instructions at once.

**What this builds, and it is exactly three things:**

1. **The `opcua-nodes.md` §12 node set** — four global DBs, four interface
   folders, nine nodes — verified from **outside** TIA before anything else is
   built on it.
2. **The `plc/forklift/SPEC.md` §14 standard-program delta** — the mode
   arbiter, the autonomy envelope and the operator's process stop.
3. **The m5-03b stand-in stimulus proof, repeated on the working project
   `safe_amr`**, plus the deletion of the probe copy `safe_amr_FIOPROBE` and
   the `Tag_1` loose end.

**What this does NOT build, and must not be made to.**

> **The F-program half of M5 is pending brief m5-15 and appears nowhere in this
> document.** m5-15 is the F-program specification — the S015 validity check,
> the automated stand-in writer, its rate and failure behaviour, the
> WSL→Windows transport and the reset-origination path — and **it has not been
> written yet**. A procedure that told the owner to build fail-safe logic from
> an unwritten specification would produce a safety program nobody specified.
> **Chunk J** lists what the future F-session will need, so it can be seen
> coming. It contains no build steps, and none may be added to it here.

Chunk H does run F-relevant **evidence** on the existing F-program: it writes
standard DB tags with the PLCSIM Advanced API and watches the F-blocks react.
It **changes no F-block, no F-runtime group and no F-I/O**, and it types no
value into a fail-safe tag — TIA refuses that outright in permanent safety
mode (`2206:000002`, LESSONS 2026-08-04), which is precisely why that path
exists.

**Every name, type, value and browse path below is quoted from
`plc/forklift/SPEC.md` §14 or `docs/interfaces/opcua-nodes.md` §12.** Nothing
here was invented. Where a value is one TIA *derives* rather than accepts — the
namespace URI above all — the step says **read it back** and never *type it*.

---

## Progress — the session updates this section

Rewrite the three fields below whenever a step completes, and always before the
session ends. Resuming then costs nothing: read this section, give the next
step.

    chunk:               not started
    last completed step: none
    verified so far:     nothing yet
    notes:               —

**Record table.** These are values only the tool can produce. Fill each in when
the step that produces it passes, with its date. Until a row is filled, the
value is a design value and no gate criterion may rest on it (ADR 0006,
LESSONS 2026-07-27).

| Record | Value | Date |
|---|---|---|
| Server interface namespace URI, read back (step 6) | | |
| PLCSIM Advanced instance name, read back (step 3) | | |
| PLCSIM Advanced instance IP, read back (step 4) | | |
| Nine §12 browse paths confirmed (step 45) | | |
| Status code of the refused `Envelope/` write (step 45) | | |
| Ten new statics in force match §14.3 (step 90) | | |
| Three new timer `PT` values in force (step 91) | | |
| Cold-start signature of §14.9 observed (step 94) | | |
| OB30 cycle time and CPU maximum, re-measured (step 97) | | |
| m5-03b repeat on `safe_amr` (steps 102–106) | | |
| `safe_amr_FIOPROBE` deleted (step 113) | | |

---

## Before step 1 — what must be true

| # | Precondition | How to know |
|---|---|---|
| 1 | The working project is **`safe_amr`**. The probe copy `safe_amr_FIOPROBE` is **not** the project being edited | Step 1 reads the title bar |
| 2 | **The bridge is not running and the HMI is not running.** A download drops the CPU's OPC UA sessions mid-read, and this project has already lost an evidence run to that (LESSONS 2026-07-28) | Step 41 checks it, and chunk H's log prints both link one-shots |
| 3 | Nothing else is writing this CPU — no test double on the same endpoint, no leftover API session | |
| 4 | The four `Forklift/Safety/` mirrors and the M4 subtree already exist on the `DemoCell` interface | Step 7 reads the folder list back |

**If reality does not match a step, stop and say so.** A wrong keystroke in a
safety project costs more than a question, and this document was written by an
author who cannot run TIA Portal: menu wording and dialog placement move
between versions, so the steps name **what to look for**, not a click path
verified on this installation.

---

## Chunk 0 — ground truth before anything is changed

*Ends with: the project, the instance and the interface identified, all read
back from the tool.*

**1.** In TIA Portal, read the **title bar**.
*You should see:* the project name. It must be **`safe_amr`**.
*Tell me:* what the title bar says.
**Stop if it says `safe_amr_FIOPROBE`** — that is the probe copy, it is due for
deletion in chunk I, and nothing in this procedure is built in it.

**2.** In the **project tree**, expand the PLC device node.
*You should see:* one CPU with its device name and type.
*Tell me:* the device name and the CPU type shown beside it.

**3.** Switch to the **S7-PLCSIM Advanced control panel**. Look at the list of
local instances.
*You should see:* one instance in RUN, and possibly others switched off.
*Tell me:* the **name** of the running instance, character for character.
This name is a tool-derived value: chunk H passes it to a script, and it is
**not** `FIOPROBE` — that was the probe copy's instance.

**4.** In the same panel, read the **IP address** shown for that instance.
*Tell me:* the address.
*Expected, from `opcua-nodes.md` §9.10:* `192.168.53.1`. If it differs, the
verification script needs the endpoint you read, not the one in the document.

**5.** In the project tree, go to the CPU → **OPC UA communication** →
**Server interfaces** and double-click **`DemoCell`**.
*You should see:* the interface editor open, with a `Forklift` folder in it.
**Do not create a second interface and do not rename this one.**
*Tell me:* that it opened.

**6.** With the interface selected, open its **properties** and find the
**namespace URI** field. **Do not type anything into it.**
*You should see:* `http://DemoCell`, greyed or otherwise not editable.
*Tell me:* exactly what it reads.
**Trap.** TIA *derives* this field as `http://<interface name>` and the field
is not editable (ADR 0006). **The interface name IS the namespace URI**, which
is why renaming the interface is forbidden anywhere in this procedure: a rename
silently breaks every browse-by-URI at connect, for the bridge and the HMI
both. Repeat this read-back after any *Change device*, which deletes server
interfaces silently (LESSONS 2026-07-27).

**7.** In the interface tree, expand **`Forklift`** and read its subfolders.
*You should see:* six — `Hmi`, `Input`, `Output`, `Status`, `Link`, `Safety`.
*Tell me:* the list you see and how many there are.
(After chunk B there will be ten, per SPEC §14.2.)

**8.** Screenshot the interface tree as it is now and save it as
`plc/forklift/evidence/m5-25-before-interface.png`.
*Tell me:* saved.

> **Chunk 0 done.** Nothing has been changed. We now have the project, the
> instance name and IP, and the interface's own read-back of its URI.

---

## Chunk A — the four new global DBs

*Ends with: four DBs whose names, members, types, start values and access
rights match SPEC §14.2, and six untouched existing DBs.*

**Two traps govern this whole chunk.**

- **The DB names are contract identifiers. Write each one correctly the first
  time, and never rename one once the interface binds it.** A rename drags
  every interface local-data reference with it in one stroke, and the manual
  repair is what introduced a silent `BridgeHeartbeat_1` browse name that cut
  the bridge with no error dialog (LESSONS 2026-07-30).
- **These are NEW DBs. No existing DB gains a member.** Adding a member to
  `ForkliftHmi`, `ForkliftInput`, `ForkliftStatus`, `ForkliftLink` or
  `ForkliftSafetyMirror` moves the offsets of tags the M4 and §13 watch tables
  and evidence depend on; the live tell is a monitoring-error icon on exactly
  the rows whose offsets moved (LESSONS 2026-07-28).

**9.** Project tree → **Program blocks** → **Add new block** → **Data block**,
type **Global DB**, name it **`ForkliftMode`**. Create it.
*You should see:* `ForkliftMode [DB…]` in Program blocks, opened for editing.
*Tell me:* that it exists with that exact name.

**10.** In `ForkliftMode`, add a member named **`HmiDriveModeRequest`**, data
type **`UInt`**, start value **`0`**.
*Tell me:* the row as it reads.

**11.** Add a second member **`ForkliftDriveModeActive`**, type **`UInt`**,
start value **`0`**.
*Tell me:* the row as it reads.

**12.** In `ForkliftMode`'s declaration table, set the per-tag attributes:
*Accessible from HMI/OPC UA* **✔ on both**; *Writable from HMI/OPC UA*
**✔ on `HmiDriveModeRequest` only**, **✘ on `ForkliftDriveModeActive`**.
*Tell me:* the four checkbox states you set.
*Why:* the HMI writes the request; the program owns the verdict, and one node
has exactly one writer (invariant 10, §12.2).

**13.** Add a new Global DB named **`ForkliftEnvelope`**.
*Tell me:* that it exists with that exact name.

**14.** Add member **`ForkliftMotionEnable`**, type **`Bool`**, start value
**`FALSE`**.
*Tell me:* the row.

**15.** Add member **`ForkliftSpeedCeiling`**, type **`Real`**, start value
**`0.0`**.
*Tell me:* the row.

**16.** Add member **`ForkliftEquipmentPermit`**, type **`Bool`**, start value
**`FALSE`**.
*Tell me:* the row.

**17.** Set `ForkliftEnvelope`'s attributes: *Accessible* **✔ on all three**;
*Writable* **✘ on all three**.
*Tell me:* the six checkbox states.
*Why this one matters more than the others:* with the envelope not writable, a
defect in **either** client that tried to write the enable, the ceiling or the
permit is **refused by the CPU**. That is where "a permission is not a command"
stops being a convention and becomes a server refusal (§12.2, §14.2), and
step 45 proves it by attempting the write.

**18.** Add a new Global DB named **`ForkliftVehicle`**.
*Tell me:* that it exists.

**19.** Add member **`ForkliftVehicleModeApplied`**, type **`UInt`**, start
value **`0`**.
*Tell me:* the row.

**20.** Add member **`ForkliftVehicleHeartbeat`**, type **`UInt`**, start value
**`0`**.
*Tell me:* the row.

**21.** Set `ForkliftVehicle`'s attributes: *Accessible* **✔ on both**;
*Writable* **✔ on both** — the bridge writes these two.
*Tell me:* the four checkbox states.

**22.** Add a new Global DB named **`ForkliftProcessStop`**.
*Tell me:* that it exists.

**23.** Add member **`HmiProcessStopRequest`**, type **`Bool`**.
*Tell me:* the row (its start value is step 25's business).

**24.** Add member **`ForkliftProcessStopActive`**, type **`Bool`**.
*Tell me:* the row.

**25.** Set the start value of **both** `ForkliftProcessStop` members to
**`TRUE`**.
*Tell me:* both start values as they read.
**Trap.** These are the only two start values in this delta that are **not**
the type's zero, and both are deliberate (§12.7, §12.8, §14.2). `FALSE` on
either makes a freshly started server assert that nobody is asking the machine
to stop, before any client has connected. `TRUE` is the non-permissive value.

**26.** Set `ForkliftProcessStop`'s attributes: *Accessible* **✔ on both**;
*Writable* **✔ on `HmiProcessStopRequest` only**, **✘ on
`ForkliftProcessStopActive`**.
*Tell me:* the four checkbox states.

**27.** In all four new DBs, confirm **no member is marked Retain**.
*Tell me:* that the Retain column is clear on all nine members.
*Why:* §14.2 — a restart re-reads the world and decides where it is, and
nothing being retentive is also what makes a reinitialisation free at step 92.

**28.** Read the **Program blocks** list back and confirm the four new DB names
are spelled exactly `ForkliftMode`, `ForkliftEnvelope`, `ForkliftVehicle`,
`ForkliftProcessStop` — and that none of the six existing DBs was opened and
edited.
*Tell me:* the four names as the tree shows them.

**29.** Screenshot the four new DBs' declaration tables and save as
`plc/forklift/evidence/m5-25-four-dbs.png`.
*Tell me:* saved.

> **Chunk A done.** The CPU has four new data blocks. Nothing is on the server
> yet and no behaviour has changed.

---

## Chunk B — the four interface folders and the nine nodes

*Ends with: ten subfolders under `Forklift/` and nine new leaves whose names
are the BrowseNames of §12.3–§12.7, character for character.*

**30.** Open the **`DemoCell`** server interface editor again.
*Tell me:* it is open.

**31.** Under `Forklift`, add a folder named **`Mode`**, beside `Hmi`, `Input`,
`Output`, `Status`, `Link` and `Safety`.
*Tell me:* the folder appears with that name.

**32.** Add a folder **`Envelope`** in the same place.
*Tell me:* it appears.

**33.** Add a folder **`Vehicle`**.
*Tell me:* it appears.

**34.** Add a folder **`ProcessStop`**.
*Tell me:* it appears, and how many subfolders `Forklift` now has.
*Expected:* ten.

**35.** Drag `ForkliftMode`'s two tags into **`Mode`**.
*You should see:* `HmiDriveModeRequest` and `ForkliftDriveModeActive` as leaves
of `Mode`.
*Tell me:* the two leaf names as they read.
**Rename nothing.** Each leaf must stay the BrowseName of §12.3, because the
BrowseName is the diff key between `opcua-nodes.md` §12, the TIA export and
SPEC §14.2 (CLAUDE.md §9).

**36.** Drag `ForkliftEnvelope`'s three tags into **`Envelope`**.
*Tell me:* the three leaf names as they read.

**37.** Drag `ForkliftVehicle`'s two tags into **`Vehicle`**.
*Tell me:* the two leaf names.

**38.** Drag `ForkliftProcessStop`'s two tags into **`ProcessStop`**.
*Tell me:* the two leaf names.

**39.** Read all nine leaf names back once more and compare them against this
list, character for character:

    Mode/         HmiDriveModeRequest        ForkliftDriveModeActive
    Envelope/     ForkliftMotionEnable       ForkliftSpeedCeiling
                  ForkliftEquipmentPermit
    Vehicle/      ForkliftVehicleModeApplied ForkliftVehicleHeartbeat
    ProcessStop/  HmiProcessStopRequest      ForkliftProcessStopActive

*Tell me:* any name that differs by even one character — especially a trailing
`_1`.

**40.** Screenshot the interface tree with the four folders expanded, saved as
`plc/forklift/evidence/m5-25-interface-tree.png`.
*Tell me:* saved.

> **Chunk B done.** The address space is designed. It is still a design value
> until chunk C reads it back out of the running server.

---

## Chunk C — compile, download, and prove the node set from outside TIA

*Ends with: the nine nodes read back over OPC UA by a client that is not the
bridge and not the HMI, and one refused write recorded with its status code.*

**41.** Confirm the **bridge is not running and the HMI is not running**, and
that no test double holds the endpoint.
*Tell me:* both confirmed.
**Trap.** A download drops the CPU's OPC UA sessions mid-read. This project has
already had a bridge die on an unhandled exception in an in-flight request,
silently ending an evidence capture (LESSONS 2026-07-28). Downloads happen with
the clients down.

**42.** Right-click the CPU → **Compile** → **Software (only changes)**.
*Tell me:* the error and warning counts from the *Info → Compile* pane.
**Stop if there is any error.**

**43.** **Download to device.** Let it finish.
*Tell me:* that the download completed and what the dialog reported.

**44.** In the project tree, look at the **diff circles** beside the blocks.
*You should see:* **solid green** on every block.
*Tell me:* what they show.
**Trap, and this one has cost this project two sessions.** "I downloaded" is
not "the CPU runs the new build". A stale build shows as monitoring-error icons
on exactly the rows whose DB offsets moved and as an in-force timer value that
contradicts the call site (LESSONS 2026-07-28). **Do not test anything until
the circles are solid green.**

**45.** Run the verification script from a shell **outside TIA** — it is a
different protocol stack and it cannot echo anything TIA believes:

    python plc/forklift/evidence/m5-25-node-verify.py opc.tcp://<instance IP>:4840

using the IP read back at step 4. It needs `asyncua`; use the same environment
the bridge's client runs in.
*You should see:* the namespace array, a collision-suffix sweep, the ten
subfolders, the nine nodes with their types and values, a **REFUSED** write on
`Forklift/Envelope/ForkliftMotionEnable` with a status code, and a final
`RESULT:` line.
*Tell me:* the `RESULT:` line, and the status code of the refused write.
**Stop if the result is FAIL** — the script names the node that failed.
**Trap, swept automatically here so it cannot be forgotten:** TIA appends `_1`
collision suffixes without asking, in DB statics and interface rows both, and a
suffixed browse name cuts a client **with no error dialog** (LESSONS
2026-07-30). Check `[2]` in the output reads *none*.
**Trap:** if the write is **accepted** rather than refused, step 17's *Writable*
✘ did not take. Fix the attribute and download again — a read proves the nodes
exist, only the refusal proves the envelope is not a command channel.

**46.** Save that script output to
`plc/forklift/evidence/m5-25-node-verify-<today's date>.log`.
*Tell me:* the file name you used.
**Trap:** one log per run, unique name per run. A shared evidence file gets
truncated by the next run and the earlier data is gone (LESSONS 2026-07-28).

**47.** Open the existing watch table **`Forklift M4 gate`** and put it in
*Monitor*.
*You should see:* every M4 and §13 row monitoring with a value, and **no
monitoring-error icon** on any row.
*Tell me:* whether any row shows the error icon.
*Why, even though nothing should have moved:* no existing DB gained a member,
so no offset should have changed — and **"should not have moved" is not a
verification** (§12.11 step 5).

**48.** Screenshot the green diff circles beside the block list, saved as
`plc/forklift/evidence/m5-25-download-diff-green.png`.
*Tell me:* saved.

> **Chunk C done, and this is a safe place to stop for the day.** The §12 node
> set now exists on the CPU and has been read back from outside the tool, with
> the envelope's non-writability proven by a refusal. **No program behaviour has
> changed yet:** nothing writes these nodes, so they sit at their start values.

---

## Chunk D — one decision before the program delta

**49. DECISION.** The next chunks change what the program does. One consequence
has to be decided before, not discovered after.

**What happens the moment §14's part 3b and the C7 term are downloaded:**
`HmiProcessStopRequest`'s start value is **`TRUE`**, and HMI v1 writes only six
nodes — it does not write this one. So the node stays `TRUE` forever, term
**C7** holds `#worldOk` `FALSE` forever, and **every enable edge in both modes
is refused. The cell goes inert until HMI v2a exists** (SPEC §14.14 state C,
§14.12 precondition 1).

That is **by design, not a defect and not a compile failure**, and the watch
table says why in one row: `HmiProcessStopRequest` `TRUE` with
`ForkliftProcessStopActive` `TRUE` and every latch pending.

*What depends on your answer:*

- **Proceed (A).** Chunks E–G go in now. Teleop drive (T5.1–T5.6) and any
  showcase re-take **cannot run** until HMI v2a writes the two new request
  nodes. Everything else in M5 continues; HMI v2a is the next agent brief.
- **Stop here (B).** Chunks A–C stand on their own: the node set exists, HMI
  v2a can be developed against it, and the program delta waits. Nothing done so
  far has to be undone, and chunk H can still run today.

*Tell me:* **A or B.**
If B, jump to **chunk H** — the m5-03b repeat and the housekeeping do not
depend on the program delta.

---

## Chunk E — the FB declarations (SPEC §14.3)

*Ends with: eight new constants, ten new statics and eleven new Temps declared,
and the FB still named what it was named.*

**50.** Open **`FB_ForkliftTeleop`** from Program blocks.
*Tell me:* it is open, and what its instance DB is called in the tree.
*Expected:* `ForkliftControl_DB`.
**Trap.** **Do not rename the FB and do not rename the instance DB.** The FB
name is now a mild misnomer — it carries the autonomous-mode supervisor too —
and it is **deliberately not changed** (§14.15 open item 4). A rename with no
functional content is exactly the change this project has been bitten by, and
the interface binds these names (LESSONS 2026-07-30).

Steps 51–58 add the **constant** rows to the FB's constant block, beside
§3.3's. Each is one row: name, type, value.

**51.** `MODE_NONE` — type **`UInt`**, value **`0`**.
**52.** `MODE_TELEOP` — type **`UInt`**, value **`1`**.
**53.** `MODE_AUTONOMOUS` — type **`UInt`**, value **`2`**.
*After 53, tell me:* the three rows as they read.
*Why three constants for one encoding:* every comparison in §14.8 is against
these symbols, so the literal `2` appears in no statement of the program.

**54.** `VEHICLE_STALE_TIME` — type **`Time`**, value **`T#500ms`**.
*Tell me:* the row.
**Trap.** It is **its own** constant and is never shared with `HMI_STALE_TIME`
or `HEARTBEAT_STALE_TIME`, even though it happens to read the same as the
latter. Three parties are now watched across three transports; retuning one
must not silently retune another (§12.6 V3, §10.8 P4).

**55.** `MODE_DISAGREE_DELAY` — type **`Time`**, value **`T#2s`**.
*Tell me:* the row.

**56.** `AUTONOMOUS_SPEED_CEILING` — type **`Real`**, value **`0.60`** (m/s).
*Tell me:* the row.

**57.** `STANDSTILL_SPEED` — type **`Real`**, value **`0.05`** (m/s).
*Tell me:* the row.

**58.** `STANDSTILL_TIME` — type **`Time`**, value **`T#500ms`**.
*Tell me:* the row.

Steps 59–68 add the **statics** to the FB interface. Each is one row: name,
type, start value.

**59.** `DriveModeInForce` — **`UInt`**, start **`0`**.
**60.** `LastModeRequest` — **`UInt`**, start **`0`**.
**61.** `AutonomousArmed` — **`Bool`**, start **`FALSE`**.
**62.** `LastVehicleHeartbeat` — **`UInt`**, start **`0`**.
**63.** `VehicleSeenAlive` — **`Bool`**, start **`FALSE`**.
**64.** `VehicleStaleTimer` — the timer type **already used by the statics in
this FB** (`HmiStaleTimer` and the three fault timers, §3.2): open one of them,
read its declared type back, and give this static the same one. §14.3 names it
`IEC_TIMER` (TON); the type string TIA actually writes is the tool's, not the
document's.
*Tell me:* the type you read off the existing timer, and that you used it.
**65.** `ModeDisagreeTimer` — same timer type as step 64.
**66.** `ModeDisagreeLatch` — **`Bool`**, start **`FALSE`**.
**67.** `ProcessStopLatch` — **`Bool`**, start **`TRUE`**.
*Tell me after 67:* the start value of `ProcessStopLatch` as it reads.
**Trap.** `TRUE` is deliberate and is the one static whose start value is not
the type's zero: it is what stops the published node reading *clear* before the
program has decided anything (§14.3, §14.9). Step 90 reads it back **in force**,
because a start value in an interface governs nothing once the instance DB
exists.
**68.** `StandstillTimer` — same timer type as step 64.
*Tell me:* the ten static rows are present.

**69.** Add the eleven **Temp** rows to the FB's temp section:
`modeRequest`, `modeRequestValid`, `modeSelectRise`, `modeEntryAdmitted`,
`vehicleHbChanged`, `vehicleAlive`, `vehicleModeValid`, `modeDisagreeRaw`,
`atStandstill`, `autonomousMotionPermitted`, `equipmentPermit`.
Types follow their use in §14.8: `modeRequest` is **`UInt`**, all ten others are
**`Bool`**.
*Tell me:* the count of temp rows you added.

**70.** Screenshot the FB's declaration table showing the new constants and
statics, saved as `plc/forklift/evidence/m5-25-declarations.png`.
*Tell me:* saved.

> **Chunk E done.** The FB has the vocabulary of §14. It does not use it yet.

---

## Chunk F — the SCL body (SPEC §14.8)

*Ends with: three new parts inserted, five statements modified, and a clean
compile.*

Each step below inserts or replaces **one** block of code. The code is in
`plc/forklift/SPEC.md` §14.8 — open it beside TIA and copy each part from
there, including its comments: the comments carry the traps.

**71.** Insert **part 2d** ("The mode request, the vehicle's report, and
standstill") **after part 2c and before part 3**.
*Tell me:* it is in, and that the part above it is 2c.
**Trap, written into the code's own comments and repeated because it is the one
that made `Autonomous` unreachable in the model run:** never write
`#vehicleAlive := NOT #VehicleStaleTimer.Q` — that reads `TRUE` for the first
`VEHICLE_STALE_TIME` of every CPU run, before the vehicle layer has reported
anything. The verdict must carry `#VehicleSeenAlive`.
**Trap:** every timer states its `PT` **at the call site**, exactly as written.
That is what stops a stale instance-DB `PT` from ruling (LESSONS 2026-07-28).

**72.** Insert **part 3b** ("The operator's process stop") **after part 3 and
before part 4**.
*Tell me:* it is in.

**73.** Replace the `#worldOk` assignment in **part 4** with the *after* form of
§14.8 — the same six terms plus **C7** (`NOT
"ForkliftProcessStop".HmiProcessStopRequest`) and **C8** (`NOT
#ModeDisagreeTimer.Q`).
*Tell me:* the two new lines as they now read, with their `// C7` and `// C8`
comments.
**Trap:** C8 is the **debounced timer output**, never the live comparison.
Written the obvious way, `NOT #modeDisagreeRaw`, the term is `FALSE` for the
whole of the vehicle's normal adopt window, which disarms the mode one call
after it was selected and makes `Autonomous` permanently unreachable (§14.7,
LESSONS 2026-07-31).

**74.** Replace the `#latchPending` assignment in **part 4** with the
seven-latch form: the five existing latches plus `#ProcessStopLatch` and
`#ModeDisagreeLatch`.
*Tell me:* the statement as it now reads.
*Note:* `#motionPermissive` and `#causeGone` are **not edited** — both already
read `#worldOk` and `#latchPending`, so both inherit C7, C8 and the two latches
without a character changing.

**75.** Insert **part 5a** (the mode arbiter) **after part 4 and before
part 5's reset**.
*Tell me:* it is in, and what the part immediately below it starts with.
*Why the order matters:* the arbiter runs before the reset and the enable, and
`#latchPending` is computed once, in part 4, ahead of all three. A mode
selection, a reset and an enable edge arriving in the same 20 ms call are three
separate actions and cannot collapse into one.

**76.** In **part 5**, extend the reset statement so it clears **seven**
latches: the existing five plus `#ProcessStopLatch` and `#ModeDisagreeLatch`.
*Tell me:* the statement as it now reads.

**77.** In **part 5**, add the conjunct `AND (#DriveModeInForce =
#MODE_TELEOP)` to the statement that **sets** `ForkliftTeleopActive`.
*Tell me:* the statement as it now reads.

**78.** Add the same mode term to the statement that **clears**
`ForkliftTeleopActive`, per §14.8's *after* form.
*Tell me:* the statement as it now reads.
*What these two conjuncts buy:* teleop is the live command source **only** while
the mode in force says so — and that is the whole of the change to the teleop
path. The three setpoint assignments are byte-identical (§14.10).

**79.** Insert **part 8** — the only assignments to the mode node and the three
envelope nodes — **after part 7, as the last action of the FB**.
*Tell me:* it is in and it is last.
**Trap:** the ceiling's `ELSE` to `0.0` is **mandatory and unconditional**.
Without it the `Real` keeps its last value and the bridge keeps republishing a
permission the program has withdrawn (LESSONS 2026-07-27). A conditional write
is not a gate.
**Trap:** the equipment permit is never `:= TRUE`. It is the two-term register
`#bridgeLinkOk AND NOT #ProcessStopLatch` (EQ1, EQ2). A permit that cannot be
`FALSE` is a decoration.

**80.** Compile the software.
*Tell me:* the error and warning counts.
**Stop on any error** — tell me the message text and the line.

**81.** Screenshot the *Info → Compile* pane, saved as
`plc/forklift/evidence/m5-25-compile-clean.png`.
*Tell me:* saved.

> **Chunk F done.** The program is written. It is not on the CPU yet.

---

## Chunk G — download, and read the in-force values back

*Ends with: the delta running, its ten statics and three timer `PT`s read from
the watch table, and the §14.9 cold-start signature observed.*

**82.** **Download to device.**
*Tell me:* the dialog's report.

**83.** Check the **diff circles** are **solid green** on every block.
*Tell me:* what they show.
**Do not read a single value until they are.** The two live tells of a stale
build are a monitoring-error icon and an in-force timer `PT` that contradicts
the call site — and this chunk is entirely about reading in-force values.

**84.** Open `ForkliftControl_DB` and read the **new static names** back.
*Tell me:* any name ending in `_1` or another digit suffix.
**Trap:** TIA appends collision suffixes in **DB statics** as well as interface
rows, without asking (LESSONS 2026-07-30). The interface rows were swept
automatically at step 45; the statics are swept here, by eye.

**85.** Project tree → **Watch and force tables** → **Add new watch table**,
named **`Forklift M5 delta`**.
*Tell me:* it exists.

**86.** Add the nine **Group 6** rows (SPEC §14.11):

    "ForkliftMode".HmiDriveModeRequest              Decimal
    "ForkliftMode".ForkliftDriveModeActive          Decimal
    "ForkliftEnvelope".ForkliftMotionEnable         Bool
    "ForkliftEnvelope".ForkliftSpeedCeiling         Floating-point
    "ForkliftEnvelope".ForkliftEquipmentPermit      Bool
    "ForkliftVehicle".ForkliftVehicleModeApplied    Decimal
    "ForkliftVehicle".ForkliftVehicleHeartbeat      Decimal
    "ForkliftProcessStop".HmiProcessStopRequest     Bool
    "ForkliftProcessStop".ForkliftProcessStopActive Bool

*Tell me:* nine rows added.

**87.** Add the ten **Group 5** static rows:
`"ForkliftControl_DB".DriveModeInForce`, `.LastModeRequest`,
`.AutonomousArmed`, `.LastVehicleHeartbeat`, `.VehicleSeenAlive`,
`.VehicleStaleTimer.ET`, `.ModeDisagreeTimer.ET`, `.ModeDisagreeLatch`,
`.ProcessStopLatch`, `.StandstillTimer.ET`.
*Tell me:* ten rows added.

**88.** Add the three **`PT`** rows: `"ForkliftControl_DB".VehicleStaleTimer.PT`,
`.ModeDisagreeTimer.PT`, `.StandstillTimer.PT`.
*Tell me:* three rows added.

**89.** Put the watch table in **Monitor**.
*Tell me:* whether any row shows a monitoring-error icon.

**90.** Read the ten statics and compare against §14.3's start values —
**`ProcessStopLatch` first**.
*Tell me:* the value of `ProcessStopLatch`, and any static that disagrees with
§14.3.
**Trap, and this is why the values are read here and not from the FB
interface.** An interface *Default value* governs **nothing** once the instance
DB exists, and a download without reinitialisation preserves the DB's old
contents (LESSONS 2026-07-28). Ten statics were just added to a live
`ForkliftControl_DB` — that is exactly the situation. A stale `FALSE` on
`ProcessStopLatch` publishes a cleared process stop that nobody cleared.

**91.** Read the three timer **`PT`** values in force.
*Expected, from §14.3:* `VehicleStaleTimer.PT` = `T#500ms`,
`ModeDisagreeTimer.PT` = `T#2s`, `StandstillTimer.PT` = `T#500ms`.
*Tell me:* the three values as the watch table shows them.
**Trap:** an in-force `PT` that contradicts the call site is a stale build, not
a typo. This project once hunted a timer defect for a session while the value
in force was `T#1M_40S` and the interface read `T#100ms` (LESSONS 2026-07-28).

**92.** **Only if step 90 or 91 found a disagreement:** reinitialise
`ForkliftControl_DB` — download the block with the option that resets it to its
start values (the wording of that option differs by TIA version; if you do not
see it, stop and tell me what the dialog offers). Then repeat steps 90 and 91.
*Tell me:* whether this step was needed, and the values after it.
*Nothing is Retain, so a reinitialisation costs nothing.*

**93.** In the PLCSIM Advanced control panel, put the instance to **STOP** and
then back to **RUN**.
*Tell me:* the instance reads RUN again.
*Why:* the next step reads the cold-start signature, and non-retentive data
takes its start values at the STOP→RUN transition.

**94.** Read the watch table immediately and compare against §14.9's
**cold-start signature**: mode in force `0`, `ForkliftMotionEnable` `FALSE`,
`ForkliftSpeedCeiling` `0.0`, `ForkliftEquipmentPermit` `FALSE`,
`ForkliftProcessStopActive` **`TRUE`**, `ForkliftResetRequired` `TRUE`, and
`VehicleSeenAlive` `FALSE` with `VehicleStaleTimer.ET` running.
(`ForkliftResetRequired` is a §10 node in `ForkliftStatus` and is **not** one of
the Group 6 rows — read it from the `Forklift M4 gate` watch table.)
*Tell me:* each of those seven readings.
*What a mismatch means:* the reason the program gives for refusing everything in
this window must be the **link**, never a sensor and never a vehicle that has
not spoken yet.
**One reading is the defect signature of this whole delta:**
`ForkliftMotionEnable` and `ForkliftTeleopActive` **`TRUE` in the same
reading**. They are never both `TRUE`, in any state, including during a
transition (§12.3 M6). If you ever see it, stop.

**95.** Screenshot the watch table showing the cold-start signature, saved as
`plc/forklift/evidence/m5-25-cold-start-signature.png`.
*Tell me:* saved.

**96.** Re-run the verification script of step 45, same command.
*Tell me:* the `RESULT:` line and the nine values it prints.
*What is different this time:* the nine values are now **program-published**
rather than DB start values — the same numbers, arrived at by logic, and the
refused write must still be refused.

**97.** Online & diagnostics → **Cycle time**: read the **OB30 cycle time** and
the **CPU maximum cycle time**, and screenshot them as
`plc/forklift/evidence/m5-25-ob30-cycle-time.png`.
*Tell me:* both figures.
*Why:* OB30's one FB has grown and the F-OB shares the budget (§14.13 step 9).
If it is tight, the answer is a **longer OB30 period** — never a second standard
OB with a second time base.

> **Chunk G done.** The §14 delta is running. Read against
> `plc/forklift/evidence/m4-cold-start-bridge-down.png`, the new signature is
> the old one plus a mode, an envelope and a process stop.

---

## Chunk H — repeat the m5-03b stand-in proof on `safe_amr`

*Ends with: the criterion (a) stand-in proof standing on the working project
instead of on a probe copy that is about to be deleted.*

**Why this chunk exists.** m5-03b proved that an API write to the standard-DB
stand-in reaches the F-program and that F-logic executes on it — but it ran on
`safe_amr_FIOPROBE`. **Evidence is qualified by the environment that produced
it** (LESSONS 2026-07-27), so the gate cannot cite that run until the same
sequence runs here.

**It changes nothing.** It writes three standard DB tags, watches four layers
follow, and restores the CPU to its as-found state. **No fail-safe tag is
typed into from the engineering connection at any point** — TIA refuses that in
permanent safety mode (`2206:000002`).

**98.** Confirm the **bridge and the HMI are still not running**.
*Tell me:* confirmed.
*Why:* nothing must compete with the writes, and the script's first output line
records that as `BridgeSeenAlive` / `HmiSeenAlive`.

**99.** Confirm the instance name you read back at **step 3**.
*Tell me:* the name again. It is the `-Instance` argument of the next steps and
it is **not** `FIOPROBE`.

**100.** In the project tree, confirm the three block names the script
addresses exist in **`safe_amr`** with exactly these names: the standard DB
**`SafetyInputStandIn`**, the F-block instance **`InstF_Forklift_Safety`**, and
the standard DB **`ForkliftSafetyMirror`**.
*Tell me:* the three names as the tree shows them, and any that differs.
**Stop on any difference.** The script addresses tags by name through the
PLCSIM Advanced API; a name that differs by a character — including a `_1`
suffix — produces an API error, not a wrong reading, and the run must not be
retried against a guessed name.

**101.** In one console, start the independent OPC UA witness for 60 s:

    python plc/forklift-safety/evidence/m5-03b-opcua-witness.py 60

Edit its `EP` only if step 4's IP differed.
*You should see:* a baseline line printed.
*Tell me:* the baseline line.
*Why a second witness:* it is a different protocol on a different stack, and
`SafetyInputStandIn` is **not exposed on that server at all**, so nothing it
sees can be an echo of the writer's process image. The strongest witness is one
that cannot see the datum you wrote, only its consequence.

**102.** In a **second** console, immediately run:

    .\plc\forklift-safety\evidence\m5-25-standin-stimulus-repeat.ps1 `
        -Instance <the name from step 99> `
        | Tee-Object plc\forklift-safety\evidence\m5-25-standin-repeat-<date>.log

*Tell me:* the log file name and the last line of output.
**Trap:** a unique log name per run. `Tee-Object` truncates, so a shared name
wipes the earlier run (LESSONS 2026-07-28).

**103.** In that log, read the first three header lines.
*Tell me:* the operating state and the two `…SeenAlive` values.
*Expected:* `Run`, and both `False`.

**104.** In the log, check the four phase results:
(a) the consumer view followed the write within one F-OB cycle;
(b) with both circuits closed, the demands **did not** clear — closing a circuit
does not clear a demand;
(c) `SafetyResetRequired` cleared **after the reset was released**, not while it
was held;
(d) reopening the E-stop circuit re-asserted `EStopDemand`, with
`ZoneStopDemand` staying clear.
*Tell me:* pass or fail for each, with the numbers the log printed.
**If (c) failed**, before re-running anything read
`InstF_Forklift_Safety.ResetHoldMinTimer.PT` and `.ResetHoldMaxTimer.PT` **in
force** — monitoring fail-safe data is allowed, it is *Modify* that permanent
safety mode refuses (`2206:000002`), and the API reads them by name too: the
script holds the reset for 1000 ms, which is
only a valid hold if it falls between those two. The probe copy read 200 ms and
3000 ms; that is the probe's reading, not this project's.
**State each figure as the log prints it.** m5-03b measured 80.4 ms, 37.0 ms and
79.1 ms on a different project and a different instance; those are that run's
draws, not this run's expectations. What must reproduce is the **behaviour**.

**105.** Compare the witness console's transition list against the phase results.
*Tell me:* whether the two views agree on every transition **and every
non-transition**.
*Why this is the load-bearing comparison:* the m5-03 failure mode was the
writer's view and the consumer's view disagreeing while the writer read
success. Two independent consumers agreeing is what excludes it.

**106.** In the log, compare the final `RESTORED to as-found` row against the
`PHASE0 baseline` row.
*Tell me:* whether the two bit strings are identical.

**107.** Save the witness output as
`plc/forklift-safety/evidence/m5-25-opcua-witness-<date>.log`, and screenshot
the console showing both runs side by side as
`plc/forklift-safety/evidence/m5-25-standin-repeat-console.png`.
*Tell me:* both file names.

> **Chunk H done.** The criterion (a) stand-in proof now stands on the working
> project. It still establishes **no safety integrity claim** — the path is a
> standard DB, the stand-in stays labelled a stand-in, and ADR 0011 D5's claim
> boundary is untouched.

---

## Chunk I — housekeeping the judge review named

*Ends with: `Tag_1` resolved, the probe copy gone, and the project saved.*

**108.** In the project tree, open the CPU's **PLC tags** → *Show all tags* and
find **`Tag_1`**.
*Tell me:* whether it exists in `safe_amr`, and in which tag table.
*Context:* the m5-03 `_1` sweep found it as a stand-alone `Bool` with no
documented owner, in a program whose naming convention is explicit
(CLAUDE.md §9).

**109.** Right-click `Tag_1` → **Cross-references** (or *Information → Used by*).
*Tell me:* how many uses it has, and where.

**110. DECISION, and it depends on step 109.**
- **No uses:** delete it. *Tell me:* deleted.
- **Any use:** **stop.** Do not rename it here — a name under CLAUDE.md §9 must
  describe the physical thing plus its meaning, and nothing in this repository
  records what `Tag_1` is. Tell me where it is used and it becomes an owner
  decision, not a keystroke.

**111.** **Only if you deleted `Tag_1` at step 110:** compile the software,
download to device, and check the **diff circles are solid green**.
*Tell me:* whether this step was needed, and what the circles show.
*Why:* a tag deleted in the project is still in the CPU until a download, and
this project has twice read "I downloaded" as "the CPU runs the new build"
(LESSONS 2026-07-28).

**112.** Confirm the probe copy's evidence is already in the repository —
`plc/forklift-safety/evidence/m5-03-*.png`,
`m5-03b-standin-stimulus-proof.log`, `m5-03b-opcua-witness.log` — and that
`safe_amr_FIOPROBE` is **closed** in TIA.
*Tell me:* both confirmed.

**113.** Delete the project **`safe_amr_FIOPROBE`** (FIO-FEASIBILITY §0.1
rule 3: on any abort, the copy is deleted; the working build was never
touched).
*Tell me:* deleted, and today's date for the record table.
*Why now:* its evidence is load-bearing, and the longer the copy exists the
weaker "the working project was never modified" gets.

**114.** **Save** the `safe_amr` project.
*Tell me:* saved.

**115.** Leave TIA showing the **`Forklift M5 delta`** watch table in *Monitor*,
not the *Program info* tab.
*Tell me:* done.
*Why:* the last session left TIA on *Program info* and the next one had to
re-find its place.

**116.** Screenshot the project tree with the probe copy gone and the four new
DBs present, saved as `plc/forklift/evidence/m5-25-housekeeping.png`.
*Tell me:* saved.

> **Chunk I done.** Fill in every remaining row of the record table above, with
> dates, and update the progress block.

---

## Chunk J — what is NOT in this procedure, and what comes next

**No step in this document builds, edits or downloads any part of the safety
program.** The F-program specification is **brief m5-15** and it does not exist
yet. Building fail-safe logic from an unwritten specification would produce a
safety program nobody specified, and no amount of care in the tool would fix
that afterwards.

**What the future F-session will need, so it can be seen coming.** Each item is
m5-15's to *specify*; none may be attempted from this document:

| What | Where it comes from |
|---|---|
| The **S015 validity check** — TIA requires a process-specific validity check per F-runtime group for standard data entering it, and it is owed **visibly in the F-code** | m5-15, rewriting `plc/forklift-safety/SPEC.md` §7 and FIO-FEASIBILITY §6 |
| The **automated stand-in writer** — its design, its rate, its failure behaviour, and which layer owns it | m5-15 + an owner ruling on the writer's home (judge review F6: the path crosses `agv/`, `plc/` and the Windows host, and no roster agent obviously owns it) |
| The **WSL→Windows transport** for that writer | m5-15 |
| The **reset-origination path** — `SafetyInputStandIn.ResetButtonPressed` has no compliant stimulus today: watch-table *Modify* is retired, the field evaluation has no business pressing a reset, and a test script is fine for a proof but not for the showcase | m5-15 (judge review F3 soft spot 2) |
| The **protective/warning field evaluation** that produces the intrusion | m5-12, not started |

**And two things that are agent work, not TIA work, before the first true
end-to-end run:** HMI v2a (m5-14a — without it the cell is inert, chunk D) and
the bridge's forklift-group repoint plus the §12.10 slot tables.

---

## Step index

| Chunk | Steps | Ends with |
|---|---|---|
| 0 — ground truth | 1–8 | project, instance and namespace URI read back |
| A — four global DBs | 9–29 | four DBs, nine members, rights and start values |
| B — interface folders | 30–40 | ten subfolders, nine BrowseNames |
| C — download and prove | 41–48 | nine nodes read back from outside TIA, one refused write |
| D — decision | 49 | proceed to the program delta, or stop with the node set |
| E — declarations | 50–70 | eight constants, ten statics, eleven temps |
| F — SCL body | 71–81 | three new parts, five modified statements, clean compile |
| G — download and in force | 82–97 | in-force statics and `PT`s, cold-start signature, cycle time |
| H — m5-03b on `safe_amr` | 98–107 | the stand-in proof on the working project |
| I — housekeeping | 108–116 | `Tag_1` resolved, probe copy deleted, project saved |
| J — not built here | — | the F-program half, pending m5-15 |

**116 steps.** If a step turns out to contain two actions, split it and say the
total has changed.
