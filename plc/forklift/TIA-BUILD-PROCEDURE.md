# TIA build procedure — the M5 standard-program delta, one step at a time

**Who this is for.** One session at TIA Portal, driven by
`docs/TIA-SESSION-PROMPT.md`: the owner is at the tool, the session gives
**exactly one step per message** and waits. Every step below is one physical
action with one observable result, so the session always has something to ask
about and the owner never has to hold two instructions at once.

**What this builds, and it is exactly four things:**

1. **The `opcua-nodes.md` §12 node set** — four global DBs, four interface
   folders, nine nodes — verified from **outside** TIA before anything else is
   built on it.
2. **The `plc/forklift/SPEC.md` §14 standard-program delta** — the mode
   arbiter, the autonomy envelope and the operator's process stop.
3. **The m5-03b stand-in stimulus proof, repeated on the working project
   `safe_amr`**, plus the deletion of the probe copy `safe_amr_FIOPROBE` and
   the `Tag_1` loose end.
4. **The `plc/forklift-safety/SPEC.md` §4.5 F-delta** — the stand-in
   heartbeat, the eight S015 validity networks of §5.4, the thirteen-pin
   re-point, and the download-with-reinitialisation that makes them run.
   **Chunks J–O**, added once §4.5 existed to build from.

**What this does NOT build, and must not be made to.**

> **The stand-in writer is not built here, and no step may be added that builds
> it.** `plc/forklift-safety/SPEC.md` §7 specifies the writer completely — one
> Windows-host process, all four members every 50 ms, level republish, two
> sources — but **its implementation home is an owner ruling that has not been
> made** (SPEC §10 open item 8). No implementation exists in this repository
> and none may be written at the keyboard during a build session. Chunk O
> observes everything the F-delta does **without** a writer, which is the
> fail-safe direction and is worth observing; chunk P lists what stays
> unproven until the ruling lands.

Chunk H runs F-relevant **evidence** on the F-program as it stands before the
delta: it writes standard DB tags with the PLCSIM Advanced API and watches the
F-blocks react. It **changes no F-block, no F-runtime group and no F-I/O**, and
it types no value into a fail-safe tag — TIA refuses that outright in permanent
safety mode (`2206:000002`, LESSONS 2026-08-04), which is precisely why that
path exists.

> **Chunk H must run before chunk J, and cannot be re-run after it.** The
> repeat script writes the three Bool channels and **no heartbeat**. After the
> S015 delta a frozen heartbeat means `StandInValid` `FALSE`, which forces all
> three validated channels to open/unpressed — so the script would drive a
> program that has correctly stopped believing it. §2 F3 is closed **before**
> the delta or not at all.

**Every name, type, value and browse path below is quoted from
`plc/forklift/SPEC.md` §14, `docs/interfaces/opcua-nodes.md` §12 or
`plc/forklift-safety/SPEC.md` §3–§5.** Nothing here was invented. Where a value
is one TIA *derives* rather than accepts — the namespace URI above all — the
step says **read it back** and never *type it*.

---

## Progress — the session updates this section

Rewrite the three fields below whenever a step completes, and always before the
session ends. Resuming then costs nothing: read this section, give the next
step.

    chunk:               COMPLETE — chunks 0 and A–O all done in the session of
                         2026-08-05 (step 49 = A, step 125 = A). Step 189 stands
                         BLOCKED as written: no writer was improvised.
    last completed step: 189
    STEP 189 IS NOW STALE, and this is the first thing the next session should
                         act on. Step 189 rests on "no writer implementation
                         exists". One does: commit 640e71e built the stand-in
                         writer in `bridge/`, on the owner's ruling recorded in
                         440666d, and it is blocked on exactly one thing — the
                         `StandInHeartbeat` tag not existing in the controller,
                         which threw a does-not-exist on 122 consecutive cycles.
                         **That tag was created and downloaded in this session
                         (step 127).** So the writer is unblocked: run it, watch
                         `HeartbeatSeen` and `StandInValid` go TRUE, then stop it
                         and watch validity drop and both demands latch. That is
                         SPEC §4.5 step 13 and the whole of T6, and it is the
                         only part of this build that stayed unproven today.
    step 164 caught one: the network 15 `R1` re-point had NOT taken, although it
                         had been reported done at step 160 — the search found
                         it still reading `"SafetyInputStandIn".ResetButtonPressed`.
                         Re-applied, and the search then returned 0. This is the
                         step existing for exactly its stated reason.
    chunks N and O:      the safety program compiled 0/0, downloaded WITH
                         re-initialisation of DB3, circles solid green, and the
                         collective F-signature changed. The four call pins are
                         wired, the four output pins are still empty, no name
                         carries a `_1`, and the `Forklift F gate` table (which
                         already existed with 21 rows) now carries Group 1's
                         heartbeat row and Group 3's eight validity rows —
                         30 rows, monitoring with no error icon.
    EVIDENCE GAP:        of the ~14 screenshots this procedure asks for, only
                         `m5-25-before-interface.png` and
                         `m5-25-cold-start-signature.png` are on disk. Every
                         other one was reported saved but is not in
                         plc/forklift/evidence/ or plc/forklift-safety/evidence/.
                         The tool-produced artefacts — five logs and
                         safety_summary.pdf — ARE present, and they carry the
                         load-bearing values; the missing files are the visual
                         record. They WERE taken: they sit unrenamed in
                         `C:\Users\ozkan\OneDrive\Pictures\Screenshots` as
                         `Screenshot 2026-08-05 HHMMSS.png`, from 16:47 onward.
                         They were deliberately NOT auto-mapped into evidence
                         names, because that mapping would be inferred from
                         timestamps and a mislabelled evidence file is worse than
                         a missing one. Rename them with the owner, who knows
                         which is which, before any gate cites them.
    note for step 164:   V1 and V5–V7 were built on the FB's INTERFACE
                         PARAMETERS (`#StandInHeartbeat`,
                         `#EStopCircuitClosed`, `#ZoneDeviceCircuitClosed`,
                         `#ResetButtonPressed`) exactly as steps 144 and 148–150
                         write them. The pre-delta core networks, by contrast,
                         read `"SafetyInputStandIn".<channel>` GLOBALLY. So once
                         chunk M's re-point is done, a text search for
                         `SafetyInputStandIn` inside FB2 will return **zero**
                         hits, not the four step 164 predicts — the four reads
                         live at FB1's call pins instead, which is what the
                         step 178 cross-reference row actually asks for.
    verified so far:     project safe_amr on CPU 1513F-1 PN (6ES7 513-1FM03-0AB0,
                         fw V3.1); PLCSIM instance safecell3 at 192.168.53.1;
                         DemoCell interface URI reads http://DemoCell; Forklift
                         has six subfolders (Input, Output, Status, Hmi, Link,
                         Safety) with the four Safety mirrors present.
                         Chunk A: four new global DBs created with all nine
                         members, types, start values (both ProcessStop members
                         TRUE) and access rights per §14.2; Retain clear on all
                         nine; no existing DB opened or edited.
                         Chunk B: Forklift now has ten subfolders; the nine §12
                         nodes are in place with no _1 suffix, and the three
                         Envelope leaves read access level RD only.
                         Chunk C: compiled 0/0, downloaded, diff circles solid
                         green; the nine nodes read back from outside TIA with
                         asyncua 2.0.1 on the Windows host, and the write on
                         Forklift/Envelope/ForkliftMotionEnable was REFUSED with
                         BadNotWritable. The `Forklift M4 gate` table monitors
                         with no error icon on any row.
                         Chunk D answered A, with one owner-added verification
                         run between C and E: HMI v2a was pointed at the live
                         CPU with hmi/config.yaml and CONNECTED — 8 writable and
                         23 read-only nodes resolved, §12 and the four Safety
                         mirrors included, zero browse failures. Its writes land:
                         Mode/HmiDriveModeRequest went 0 -> 1, and
                         ProcessStop/HmiProcessStopRequest was driven TRUE ->
                         False -> TRUE from the operator page.
                         ForkliftProcessStopActive stayed TRUE throughout, which
                         is correct — no program writes it until §14 part 3b.
                         The HMI was stopped again before chunk E.
                         CORRECTION to this document: chunk D's text says the
                         cell "goes inert until HMI v2a exists". v2a exists (it
                         was built in ea4d63d) and has now been exercised against
                         the real CPU; what chunk D's consequence actually turns
                         on is v2a being RUNNING, not v2a being built.
                         Chunk E: eight constants, ten statics and eleven temps
                         declared in FB_ForkliftTeleop (FB3, instance
                         ForkliftControl_DB / DB10); the timer type read back
                         off HmiStaleTimer is TON_TIME. ProcessStopLatch reads
                         default `true`. Neither the FB nor its instance DB was
                         renamed.
                         Chunk F: parts 2d, 3b, 5a and 8 inserted and the five
                         statements modified; compiles 0 errors / 0 warnings.
                         At the owner's request steps 74–79 were applied as ONE
                         paste of the whole FB body rather than five in-place
                         edits, and that body is now committed to the repository
                         as `plc/forklift/scl/FB_ForkliftTeleop.scl`,
                         byte-identical to what was pasted, so a future TIA
                         export can be diffed against it.
                         Chunk G: downloaded, circles solid green, no `_1` in
                         the new statics, watch table `Forklift M5 delta` built
                         with all 22 rows and monitoring cleanly. The §14.9
                         cold-start signature was observed in full after a
                         STOP -> RUN, and the node set was re-read from outside
                         TIA with the nine values now PROGRAM-PUBLISHED and the
                         envelope write still refused
                         (`m5-25-node-verify-2026-08-05-post-delta.log`).
    open check:          two timer PTs read `T#0MS` in force. This is NOT the
                         LESSONS 2026-07-28 stale-PT trap: all three statics
                         were created by this very download, so their content
                         starts at zero, the only writer of `PT` is the call
                         site, and the one timer whose `IN` is TRUE
                         (`VehicleStaleTimer`, heartbeat frozen) reads exactly
                         its specified `T#500MS`. `ModeDisagreeTimer` and
                         `StandstillTimer` have `IN` FALSE — `#modeDisagreeRaw`
                         needs `#vehicleAlive`, `#atStandstill` needs
                         `#speedValid`, and both need the bridge. Re-read all
                         three PTs with the bridge running before any test that
                         depends on the 2 s or 500 ms delay. A reinitialisation
                         would not have helped and was deliberately not done.
                         Chunk H: the m5-03b criterion (a) proof now stands on
                         the working project — see the record table row. Both
                         runs were executed from the session's own shells rather
                         than the owner's consoles, so step 107's side-by-side
                         console screenshot was NOT taken; the two dated logs in
                         plc/forklift-safety/evidence/ are the evidence, and they
                         are stronger than the screenshot would have been. The
                         run established no safety integrity claim: the path is a
                         standard DB and ADR 0011 D5's claim boundary is
                         untouched.
    notes:               FIOPROBE instance still listed in the PLCSIM panel,
                         switched off — chunk I business, not touched.
                         Step 12: ForkliftDriveModeActive was first typed as
                         "ForkliftMode" and corrected before proceeding.
                         Step 25 had to be redone: the two TRUE start values did
                         not commit the first time, and after they were retyped
                         and downloaded the server still read False — the DBs
                         already existed on the CPU, so the download preserved
                         their actual values (LESSONS 2026-07-28). A PLCSIM
                         STOP -> RUN took the start values, nothing being Retain.
                         Note for step 45's script: it prints the §14.2 start
                         value beside the live value but does NOT fail on a
                         mismatch — it reported PASS while both ProcessStop
                         nodes read False. Compare that column by eye.

**Record table.** These are values only the tool can produce. Fill each in when
the step that produces it passes, with its date. Until a row is filled, the
value is a design value and no gate criterion may rest on it (ADR 0006,
LESSONS 2026-07-27).

| Record | Value | Date |
|---|---|---|
| Server interface namespace URI, read back (step 6) | `http://DemoCell` | 2026-08-05 |
| PLCSIM Advanced instance name, read back (step 3) | `safecell3` | 2026-08-05 |
| PLCSIM Advanced instance IP, read back (step 4) | `192.168.53.1` | 2026-08-05 |
| Nine §12 browse paths confirmed (step 45) | all nine, values match §14.2; ten subfolders; 44 browse names, no `_1` | 2026-08-05 |
| Status code of the refused `Envelope/` write (step 45) | `BadNotWritable` — "The access level does not allow writing to the Node." | 2026-08-05 |
| Ten new statics in force match §14.3 (step 90) | all ten agree; `ProcessStopLatch` reads TRUE in force | 2026-08-05 |
| Three new timer `PT` values in force (step 91) | `VehicleStaleTimer.PT` = `T#500MS`; the other two read `T#0MS` **because their `IN` is FALSE** — see the note below, not a stale build | 2026-08-05 |
| Cold-start signature of §14.9 observed (step 94) | all seven: mode `0`, enable FALSE, ceiling `0.0`, permit FALSE, `ForkliftProcessStopActive` TRUE, `ForkliftResetRequired` TRUE, `VehicleSeenAlive` FALSE with `VehicleStaleTimer.ET` at `T#500MS` | 2026-08-05 |
| OB30 cycle time and CPU maximum, re-measured (step 97) | CPU cycle shortest 1.002 ms, last 1.006 ms, longest 1.701 ms; configured maximum 150 ms. OB30's own execution time was not read — this panel is the CPU cycle | 2026-08-05 |
| m5-03b repeat on `safe_amr` (steps 102–106) | PASS on all four phases — (a) 48.8 ms consumer-view latency, (b) closing both circuits cleared no demand, (c) `SafetyResetRequired` cleared 38.3 ms **after** release, (d) E-stop re-asserted 84.8 ms with `ZoneStopDemand` clear; restored bit string identical to the PHASE0 baseline. The independent OPC UA witness agrees on every transition **and every non-transition**. Logs: `m5-25-standin-repeat-2026-08-05.log`, `m5-25-opcua-witness-2026-08-05.log` | 2026-08-05 |
| `safe_amr_FIOPROBE` deleted (step 113) | deleted, together with `safe_amr_FIOPROBE.backup`. The PLCSIM Advanced **instance** named FIOPROBE is still listed in the control panel, switched off | 2026-08-05 |
| F-collective signature **before** the F-delta (step 119) | `AA735E2A`, offline = online. Unchanged from the 2026-08-04 read, so the day's standard-program downloads touched no F-block. F-SW `AA735E29`, F-HW `00000001` | 2026-08-05 |
| F-OB number and cycle time in force (step 120) | `FOB_RTG1` = **OB123**, cyclic interrupt, cycle time 100000 µs = **100 ms**, priority 12, warn 110 ms, maximum 120 ms | 2026-08-05 |
| §2 F7 — Int `<>` and `MOVE` offered? (steps 122–123) | **Both offered.** `CMP <>` ("Not equal") under Comparator operations, and `MOVE` under Move operations V2.0. No design change: the heartbeat stays `Int` | 2026-08-05 |
| FB2 interface counts after the delta, 4 / 4 / 18 / 3 (step 141) | read back **4 / 4 / 19 / 3**. The static count is 19, not 18, because the pre-delta block already carried **11** statics and not 10: the eleventh is TIA's auto-generated `F_IEC_Timer_Instance` (TON), which SPEC §3.3's table does not count. Same build, different counting rule — step 130's 3 / 4 / 10 / 2 should read 3 / 4 / 11 / 2 | 2026-08-05 |
| S015 disclosure warning, the tags it names (step 172) | TIA raised **no compile warning**; the disclosure appears in **Safety Administration → Generate safety summary**, section *"Data from the standard user program"*. It names exactly the four `SafetyInputStandIn` members — `ZoneDeviceCircuitClosed`, `ResetButtonPressed`, `EStopCircuitClosed`, `StandInHeartbeat` — all at `Main_Safety_RTG1 [FB1]` network 1, RTG1, **and nothing else**. Summary saved as `plc/forklift/evidence/safety_summary.pdf` | 2026-08-05 |
| F-collective signature **after** the F-delta (step 176) | `2BC94038`, offline = online, different from step 119's `AA735E2A`. F-SW `2BC94037`; F-HW unchanged at `00000001` | 2026-08-05 |
| `SafetyInputStandIn` cross-reference: 4 reads, 0 writes (step 178) | exactly four accesses, one per member, **all `Read`**, all at `Main_Safety_RTG1` %FB1 NW1. **No write access from any block on the CPU** | 2026-08-05 |
| F-side absence check `RESULT:` line (step 179) | `RESULT: PASS` — positive control read all four `Forklift/Safety/` mirrors first, then 328 browse names swept: `SafetyInputStandIn`, `StandInHeartbeat`, `InstF_Forklift_Safety`, `F_Forklift_Safety`, `Main_Safety_RTG1` all **absent**; `DataBlocksGlobal` **not published at all**; no `_1`. Log `m5-25b-f-absence-2026-08-05.log` | 2026-08-05 |
| Three F timer `PT` values in force (step 186) | `StandInStaleTimer.PT` = `T#1S`, `ResetHoldMinTimer.PT` = `T#200MS`, `ResetHoldMaxTimer.PT` = `T#3S` — all three as specified | 2026-08-05 |
| Invalid-boot signature of §5.4 observed (step 187) | **all ten readings as written**: `StandInValid` FALSE, `HeartbeatSeen` FALSE, `StandInStaleTimer.ET` at `T#1S` and not climbing, the three validated channels FALSE, `EStopDemand` / `ZoneStopDemand` / `SafetyResetRequired` TRUE, `SafetyResetFault` FALSE. Neither defect signature present | 2026-08-05 |

---

## Before step 1 — what must be true

| # | Precondition | How to know |
|---|---|---|
| 1 | The working project is **`safe_amr`**. The probe copy `safe_amr_FIOPROBE` is **not** the project being edited | Step 1 reads the title bar |
| 2 | **The bridge is not running and the HMI is not running.** A download drops the CPU's OPC UA sessions mid-read, and this project has already lost an evidence run to that (LESSONS 2026-07-28) | Step 41 checks it, chunk H's log prints both link one-shots, and the same holds for the F-side download at step 174 |
| 3 | Nothing else is writing this CPU — no test double on the same endpoint, no leftover API session | |
| 4 | The four `Forklift/Safety/` mirrors and the M4 subtree already exist on the `DemoCell` interface | Step 7 reads the folder list back; step 179 uses the four mirrors as its positive control |
| 5 | **For chunks J–O only:** the F-program is the **as-built 2026-07-30** build — D1–D7 applied, fourteen networks in FB2, interface 3 / 4 / 10 / 2 | Step 130 reads the four counts back, and stops if they differ |

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

## Chunk J — the F-session's ground truth, and one decision

*Ends with: the licence, safety mode, the pre-delta signature, the F-OB cycle
and the S015 instruction set all read back, and one answer.*

**Everything from here to chunk O is the F-delta**, `plc/forklift-safety/SPEC.md`
§4.5. It can be run in the same sitting as chunks 0–I or in its own session; the
only chunk it depends on is **H**, and it depends on H having run **first**
(see the callout at the top of this document — the repeat script writes no
heartbeat, so §2 F3 cannot be closed after the delta).

**Nothing in chunks J–O touches the standard program.** The one new object on
the standard side is a member added to a standard DB that no standard block
reads or writes.

**117.** Open **Safety Administration** for the CPU.
*You should see:* the F-runtime group `RTG1` with `FOB_RTG1` and
`Main_Safety_RTG1` under it, and a licence state.
*Tell me:* the **Safety Advanced licence state** as it reads.
*Why:* SPEC §2 **F0**. It was answered 2026-07-29; this confirms it still holds
on this project, with today's date.

**118.** In the same view, read the **safety mode**.
*Tell me:* the exact wording.
*Expected:* **activated** (permanent safety mode).
**Trap.** Everything below assumes it stays activated. If a step ever seems to
need it deactivated, that step is wrong — say so instead of deactivating. And
no step below plans to *Modify* a fail-safe tag, because TIA refuses that
outright in this mode (`2206:000002`, LESSONS 2026-08-04).

**119.** Read the **F-collective signature**, online and offline.
*Tell me:* both values, and whether they are equal.
*Context, not an expectation:* `AA735E2A` was read on 2026-08-04, before this
delta. **Record what you read** — it is the *before* value, and step 176 must
show a **different** one. A collective signature that has not changed after a
download is the F-side's version of a stale build (SPEC §2 F6).

**120.** Open the F-OB's properties and read the **OB number and its cycle
time** in force.
*Tell me:* both, as the tool states them.
*Context:* `FOB_RTG1` = OB123, cyclic 100 ms, read back 2026-08-04. It is what
`STANDIN_STALE_MAX` = `T#1s` was derived against (ten F-cycles, SPEC §3.3).
**Open item, not yours to fix at the keyboard:** at 100 ms, `RESET_HOLD_MIN` =
200 ms spans two F-cycles where SPEC §4.3 requires five. That deviation is
**open and belongs to a safety-spec ruling** (SPEC §10 open item 2). Both
constants stay exactly as the SRS states them, and every evidence record from
this build carries one line naming the deviation.

**121.** Confirm chunk H has run **on this build**: find the log
`plc/forklift-safety/evidence/m5-25-standin-repeat-<date>.log`.
*Tell me:* the file name and its date.
**Stop if it does not exist** and run chunk H first. This is SPEC §4.5 step 1's
F3 half, and it is the last moment it can be closed: after the S015 delta the
repeat script drives a program that has correctly stopped believing a frozen
stand-in, so a re-run would measure the S015 check rather than the stimulus.

**122.** Open **`F_Forklift_Safety [FB2]`**. In the *Instructions* task card,
find the **comparator** operations available **inside the safety program**, and
look for `<>` usable with an **Int**.
*Tell me:* whether it is offered, and what the instruction is called.
*Why this is asked before anything is built:* SPEC §2 **F7**, and it is a
genuine unknown. This safety instruction set already turned out to omit
`R_TRIG` and `F_TRIG`, which is why the existing block forms both edges by hand.

**123.** In the same instruction list, look for **`MOVE`** usable with an Int.
*Tell me:* whether it is offered.
**Stop if either `<>` or `MOVE` is missing.** The heartbeat's type then becomes
a **design change** — SPEC §2 F7 names the fallback shape, a Bool toggle with a
period of at least three writer cycles so the F-OB cannot alias it — and that is
a specification change, **not a substitution to make at the keyboard**. Report
it and stop; the fourteen existing networks are unaffected either way.

**124.** Screenshot the safety instruction list showing both, saved as
`plc/forklift-safety/evidence/m5-25b-f7-instruction-set.png`.
*Tell me:* saved.
*Why a screenshot of an instruction list:* F7 is recorded as a tool read-back
with its date, like every other tool-derived value in this project.

**125. DECISION.** One consequence has to be decided before the delta, not
discovered after.

**What happens the moment the S015 delta is downloaded:** `StandInValid` boots
`FALSE` and stays `FALSE` until the heartbeat has been **seen to change**
(SPEC §5.4 V2 — the boot polarity). No process advances that heartbeat, because
**the stand-in writer does not exist**: SPEC §7 specifies it completely, and its
implementation home is an **owner ruling that has not been made** (SPEC §10
open item 8). So all three validated channels read open/unpressed, **both
demands stay latched and no reset can be accepted, indefinitely.**

That is **by design, not a defect**, and it is the fail-safe direction: a writer
that never started reads as a demand, never as a clear world. But it means the
F-program is **inert** after this delta until the writer exists.

*What depends on your answer:*

- **Proceed (A).** Chunks K–O go in now. The delta is built, downloaded and
  verified, and chunk O observes the whole invalid-boot signature — which is
  §7.3 rows 1 and 6 observed for real. **T6 cannot run** until the writer
  exists. The `Forklift M4 gate` behaviour is unaffected either way, because
  the standard program does not yet read F-data.
- **Stop here (B).** The F-program stays as built on 2026-07-30, chunk H's F3
  proof stands, and the delta waits for the writer ruling so that build and
  stimulus land together. Nothing done in chunks 0–I has to be undone.

*Tell me:* **A or B.**

---

## Chunk K — the heartbeat member and FB2's interface (SPEC §4.5 steps 2–3)

*Ends with: `SafetyInputStandIn` carrying four members and still reachable by
no client, and FB2's interface reading 4 / 4 / 18 / 3.*

**126.** In Program blocks, open the standard DB **`SafetyInputStandIn`**.
*You should see:* three Bools — `EStopCircuitClosed`,
`ZoneDeviceCircuitClosed`, `ResetButtonPressed` — all start value `FALSE`.
*Tell me:* the three rows as they read.
**Trap.** This is a **standard** DB and it stays one. Do not move it into the
safety program and do not mark it as an F-DB: F-data cannot be stimulated from
outside the safety program at all in permanent safety mode, which would destroy
the stimulus (SPEC §4.2 step 2).

**127.** Add a fourth member **`StandInHeartbeat`**, data type **`Int`**, start
value **`0`**.
*Tell me:* the row as it reads.
*What it is:* not a device and not a wire — the writer's liveness counter, so
the S015 check can tell a live stand-in from a frozen one (SPEC §3.1).

**128.** Confirm **no member of this DB is Retain**.
*Tell me:* that the Retain column is clear on all four.

**129.** Open the DB's **properties** and read *Accessible from HMI/OPC UA*
back.
*You should see:* **✘**, unticked.
*Tell me:* what the box reads.
**Trap, and this is why it is read rather than assumed.** An edit is an
occasion for a property to revert, and with this box ticked the S7-1500
auto-publishes the DB under `Objects/DataBlocksGlobal` in its own namespace,
where the commissioned access settings do **not** write-protect it — any OPC UA
client could then clear a safety latch (SPEC §4.2 step 3). Step 179 turns this
read-back into a fact from outside the tool.

**130.** Open **`F_Forklift_Safety [FB2]`**'s interface table and read the
**counts** back.
*Tell me:* how many Inputs, Outputs, Statics and Constants it has.
*Expected, as built 2026-07-30:* **3 / 4 / 10 / 2**.
**Stop if it differs** — this delta is written against that build, and a
different starting point is a different delta.

**131.** Add an **Input** named **`StandInHeartbeat`**, type **`Int`**.
*Tell me:* the row, and that it is the fourth Input.
*Why an interface parameter and not a global read:* the same reason the three
channels are — if a usable F-I/O channel ever exists, the swap is pins at one
call and nothing inside this block moves (SPEC §2.1).

Steps 132–139 add the **eight statics** of SPEC §3.3's second table. Each is
one row: name, type, start value. All Static, all non-Retain.

**132.** `HeartbeatChanged` — **`Bool`**, start **`FALSE`**.
**133.** `HeartbeatSeen` — **`Bool`**, start **`FALSE`**.
*After 133, tell me:* the start value of `HeartbeatSeen` as it reads.
**Trap.** `FALSE` is load-bearing. This static is the boot polarity: a verdict
built only on "not yet proven stale" boots `TRUE` for the whole first stale
window, and every guard riding on it inherits that (LESSONS 2026-07-28,
`BridgeLinkOk`). Life must be **seen** before it is believed.
**134.** `StandInStaleTimer` — the **same timer type** the existing
`ResetHoldMinTimer` uses: open that static, read its declared type back, and
give this one the same.
*Tell me:* the type you read off `ResetHoldMinTimer`, and that you used it.
**Trap:** when TIA offers the call-options dialog, choose **multi-instance**.
*Single instance* creates an extra data block and moves the statics out of
`DB3`, so SPEC §8's watch table and §6's contract stop matching the build
(SPEC §4.2 step 7).
**135.** `StandInValid` — **`Bool`**, start **`FALSE`**.
**136.** `EStopClosedValid` — **`Bool`**, start **`FALSE`**.
**137.** `ZoneClosedValid` — **`Bool`**, start **`FALSE`**.
**138.** `ResetPressedValid` — **`Bool`**, start **`FALSE`**.
**139.** `HeartbeatMemory` — **`Int`**, start **`0`**.
*Tell me:* the eight static rows are present.

**140.** Add the constant **`STANDIN_STALE_MAX`** = **`T#1s`** in the block's
*Constant* section — **if the F-block offers one**.
*Tell me:* whether it offers a Constant section, and the row if it does.
**If it does not**, say so and we enter `T#1s` as a **literal at V3's `PT` pin**
at step 146. Either way the `PT` is **explicit at the call site**: a `PT` left
to an interface default is the defect this project once hunted for a session
while the value in force was `T#1M_40S` (LESSONS 2026-07-28).

**141.** Read the interface **counts** back again.
*Tell me:* the four counts as the interface table shows them.
*Expected:* **4 / 4 / 18 / 3** — or 4 / 4 / 18 / 2 if step 140 found no
Constant section.
**Read them off the table.** A count you assumed is not a count.

**142.** Screenshot the interface table showing the new Input, the eight statics
and the constant, saved as
`plc/forklift-safety/evidence/m5-25b-f-declarations.png`.
*Tell me:* saved.

> **Chunk K done.** The block has the vocabulary of §5.4. Nothing uses it yet
> and the compiled program has not changed behaviour.

---

## Chunk L — the seven validity networks (SPEC §5.4 V1–V7)

*Ends with: seven new networks ahead of the existing fourteen, each ending in
one written operand.*

**The position rule is load-bearing.** V1–V7 run **before** network 1, so every
consumer reads a validated value computed earlier in the **same** F-cycle. Built
after the latches instead, a dying writer would get one cycle of stale trust.
After this chunk, TIA numbers V1–V7 as networks 1–7 and the core fourteen as
8–21.

Each step below builds **one** network. The element/pin/operand tables are in
`plc/forklift-safety/SPEC.md` §5.4 — open it beside TIA and build from there,
reading each network's notes: the notes carry the traps.

**143.** In FB2, insert a **new empty network above the existing network 1**
(`CauseGone`).
*Tell me:* the empty network is first, and what the network below it is titled.
*Expected below it:* `CauseGone`.

**144.** Build **V1 — `HeartbeatChanged`**: a `CMP <>` box (Int) with
in 1 = `#StandInHeartbeat`, in 2 = `#HeartbeatMemory`, driving an `=` coil on
`#HeartbeatChanged`.
*Tell me:* the coil's operand and the two comparator inputs as they read.
**Trap:** `#HeartbeatMemory` is written by the **last** network of the block, so
this comparison reads the **previous** cycle's value. That apparent forward
reference is the design (SPEC §5.0 note 6) — do not "repair" it.

**145.** Build **V2 — `HeartbeatSeen`**: an `S` (set output) coil with operand
`#HeartbeatSeen`, driven by `#HeartbeatChanged`.
*Tell me:* the coil type and its operand.
*Why a set coil and not an assignment:* one-shot, never cleared while the
F-runtime group runs — the same shape as `ResetSeenOpen`.

**146.** Build **V3 — `StandInStaleTimer`**: a `TON` box, multi-instance
`#StandInStaleTimer`, with `IN` = `#HeartbeatChanged` **(negated)** and `PT` =
`#STANDIN_STALE_MAX` — or the literal `T#1s` at the pin if step 140 found no
Constant section.
*Tell me:* the `PT` operand as it reads at the pin, and that the `IN` pin shows
the negation circle.
**Trap:** the box is called **unconditionally, every cycle**, outside any
branch. A timer that must be released by an event is called with `IN` as the
event's own test — a timer called inside a state that stops executing can only
ever be released by code that runs in the same scan as the exit (LESSONS
2026-07-27).

**147.** Build **V4 — `StandInValid`**: an `AND` box, in 1 = `#HeartbeatSeen`,
in 2 = `#StandInStaleTimer.Q` **(negated)**, driving `=` on `#StandInValid`.
*Tell me:* the two inputs and which one carries the negation circle.
*Why this shape:* validity is asserted **affirmatively from evidence of life**,
so boot, stale, frozen and never-started all fall through to invalid without
being enumerated (LESSONS 2026-07-27, applied to liveness).

**148.** Build **V5 — `EStopClosedValid`**: `AND` of `#EStopCircuitClosed` and
`#StandInValid`, driving `=` on `#EStopClosedValid`.
*Tell me:* the coil operand.

**149.** Build **V6 — `ZoneClosedValid`**: the same shape with
`#ZoneDeviceCircuitClosed`.
*Tell me:* the coil operand.

**150.** Build **V7 — `ResetPressedValid`**: the same shape with
`#ResetButtonPressed`.
*Tell me:* the coil operand.
*What V5–V7 buy:* every failure direction is the stopping one. Invalid makes
both circuits read **open** and the reset read **unpressed** — no edge, no
arming, no pulse.

**151.** Read the **first eight networks** back in order and tell me each one's
**written operand**.
*Expected, in this order:* `HeartbeatChanged`, `HeartbeatSeen`,
`StandInStaleTimer`, `StandInValid`, `EStopClosedValid`, `ZoneClosedValid`,
`ResetPressedValid`, then `CauseGone` as network 8.
*Tell me:* the eight operands, and stop if the order differs.

**152.** Screenshot networks 1–7, saved as
`plc/forklift-safety/evidence/m5-25b-f-validity-networks.png`.
*Tell me:* saved.

> **Chunk L done.** The validity verdict exists. Nothing consumes it yet — the
> core fourteen still read the raw channels, which chunk M fixes.

---

## Chunk M — the re-point, and the last network (SPEC §5.4)

*Ends with: no logic network reading a raw channel, and `HeartbeatMemory`
written by the final network of the block.*

The re-point table in SPEC §5.4 is **exhaustive**: ten networks, thirteen pins,
and nothing else in any core network moves. Steps 153–163 walk it in network
order, using TIA's **new** numbering (the core fourteen are now 8–21).

**153.** Network **8 `CauseGone`** — re-point the `AND` box: in 1 from
`"SafetyInputStandIn".EStopCircuitClosed` to **`#EStopClosedValid`**, in 2 from
`.ZoneDeviceCircuitClosed` to **`#ZoneClosedValid`**.
*Tell me:* the two inputs as they now read.

**154.** Network **9 `ResetSeenOpen`** — this one is **more than a
substitution**. Replace the negated `ResetButtonPressed` on the `S` coil's input
with an **`AND` box**: `#StandInValid` AND `#ResetPressedValid` *(negated)*.
*Tell me:* the network as it now reads, and which pin carries the negation.
*Why the extra conjunct:* "seen open" must mean *observed not pressed **while
the stand-in was alive***. Without it, the invalid boot window — during which
`ResetPressedValid` is forced `FALSE` — would count as having seen the device
open, and a device genuinely stuck from before start-up would slip the power-up
rejection the moment validity arrived.

**155.** Network **10 `ResetRise`** — `AND` in 1 from `ResetButtonPressed` to
**`#ResetPressedValid`**.
*Tell me:* the input as it now reads.

**156.** Network **11 `ResetFall`** — `AND` in 1 *(negated)* to
**`#ResetPressedValid`**.
*Tell me:* the input, and that the negation circle survived the edit.

**157.** Network **12 `ResetPressArmed`** — `OR` in 1 *(negated)* to
**`#ResetPressedValid`**.
*Tell me:* the input and its negation.

**158.** Network **13 `ResetHoldMinTimer`** — `AND` in 1 to
**`#ResetPressedValid`**.
*Tell me:* the input.
**Do not touch this network's `PT`.** It stays `RESET_HOLD_MIN` = `T#200ms`
exactly as the SRS states it; the sampling deviation of step 120 is a
safety-spec ruling, not a keystroke here.

**159.** Network **14 `ResetHoldMaxTimer`** — `TON` `IN` to
**`#ResetPressedValid`**.
*Tell me:* the `IN` pin.
**Its `PT` also stays** `T#3s`.

**160.** Network **15 `SafetyResetFault`** — **two** pins: `AND` in 1, and the
`R1` pin *(negated)*, both from `ResetButtonPressed` to
**`#ResetPressedValid`**.
*Tell me:* both pins as they now read.

**161.** Network **18 `EStopDemand`** — `S1` *(negated)* from
`"SafetyInputStandIn".EStopCircuitClosed` to **`#EStopClosedValid`**.
*Tell me:* the pin.
**Trap:** this is the `RS` box, **set-dominant**. Do not swap it for an `SR`
while you are in here — in TIA the trailing `1` marks the dominant input, and a
demand arriving in the same cycle as a reset must win (SPEC §5.0 note 2).

**162.** Network **19 `ZoneStopDemand`** — `S1` *(negated)* to
**`#ZoneClosedValid`**.
*Tell me:* the pin.

**163.** Network **21 `ResetMemory`** — the coil's driver from
`"SafetyInputStandIn".ResetButtonPressed` to **`#ResetPressedValid`**.
*Tell me:* the driver as it now reads.

**164.** Search FB2 for **`SafetyInputStandIn`** and list every hit.
*You should see:* hits **only** in networks 1 (the heartbeat) and 5, 6, 7 (the
three channels) — four in total, in the validity networks and nowhere else.
*Tell me:* the hit list.
**This is the verification of the whole re-point, and it is a search rather
than a re-read for a reason:** thirteen pins is exactly the size of list where
one gets missed, and the missed one reads a raw channel that a dead writer has
frozen in the permissive direction.

**165.** Build **M2 — `HeartbeatMemory`** as the **last network of the block**,
after network 21 (`ResetMemory`): a `MOVE` box, `IN` = `#StandInHeartbeat`,
`OUT1` = `#HeartbeatMemory`.
*Tell me:* it is in, and what network number it has.
**Trap:** last, and unconditional. Moved earlier, V1 compares the heartbeat
against itself, `HeartbeatChanged` is never `TRUE`, the stale timer runs from
the first cycle and `StandInValid` dies — **a failure that looks exactly like a
dead writer and is not.**

**166.** Read the **network count** back, and the titles of the last two
networks.
*Tell me:* the count and the two titles.
*Expected:* **22**, ending `ResetMemory` then `HeartbeatMemory` — the two memory
copies closing the block in that order.

**167.** Screenshot the last three networks, saved as
`plc/forklift-safety/evidence/m5-25b-f-repoint-and-m2.png`.
*Tell me:* saved.

> **Chunk M done.** The block is written. It is not on the CPU yet, and the call
> in `Main_Safety_RTG1` is still inconsistent — chunk N repairs it.

---

## Chunk N — call, compile, download, and the checks a script can run

*Ends with: the delta in the CPU with a changed collective signature, four read
accesses and zero writes on the stand-in, and the F-side absence proven from
outside TIA.*

**168.** Open **`Main_Safety_RTG1 [FB1]`**, right-click the
`F_Forklift_Safety` call box and choose **Update**.
*Tell me:* whether the call box still shows an inconsistency marker.

**169.** Wire the **fourth input pin** to
**`"SafetyInputStandIn".StandInHeartbeat`**.
*Tell me:* all four input pins as they read.
*Expected:* the three Bool channels unchanged plus the heartbeat.

**170.** Confirm **all four output pins are still empty**.
*Tell me:* that they are.
**Trap.** An unassigned FB output pin is legal and is the point: the values live
in `DB3` and the standard program reads them **there**. A wired output pin here
would put the F-program back to writing a standard DB — the dual-writer defect
D4 exists to remove (SPEC §3.4).

**171.** **Compile the safety program.**
*Tell me:* the error and warning counts.
**Stop on any error** — give me the message text.

**172.** Open the compile/safety summary and find the **standard-data
disclosure** (the S015 territory warning).
*Tell me:* every tag it names.
*Expected:* **four members of `SafetyInputStandIn` and nothing else.**
**A warning naming any other DB means a re-point was missed** — go back to step
164's search. And note what this warning is: TIA's mechanism here is
**disclosure, not protection**, which is exactly why §5.4's validity check is
built as networks the owner types rather than acknowledged in a log and
forgotten.

**173.** Screenshot the compile summary showing that warning, saved as
`plc/forklift-safety/evidence/m5-25b-f-compile-s015.png`.
*Tell me:* saved.

**174.** **Download the safety program, with re-initialisation of
`InstF_Forklift_Safety [DB3]`.** Expect TIA to want the CPU in STOP.
*Tell me:* the dialog wording, and whether you were offered and took the
re-initialisation option. If you do not see it, **stop and tell me what the
dialog offers**.
**Trap.** The interface change moved the DB layout. A download that preserves
the old instance values leaves stale values ruling — the live tells are
monitoring-error icons on exactly the rows whose offsets moved and an in-force
`PT` that contradicts the call site (LESSONS 2026-07-28). Nothing here is
Retain, so a re-initialisation costs nothing.

**175.** Check the **diff circles** are **solid green** on every block.
*Tell me:* what they show.
**Read nothing until they are.** "I downloaded" is not "the CPU runs the new
build", and this project has read it that way twice.

**176.** Read the **F-collective signature** online and offline again.
*Tell me:* both values, and whether they are equal to each other and different
from step 119's.
*Expected:* equal to each other, **different** from step 119.
**A changed collective signature is the expected evidence of this delta, not an
error.** Unchanged means the CPU is not running what you are reading — and this
is the F-side's strongest stale-build instrument, because it answers "is the CPU
running the program I am reading?" in one value rather than by inference.

**177.** Open `InstF_Forklift_Safety [DB3]` and read the **new static names**
back, and the new member name in `SafetyInputStandIn`.
*Tell me:* any name ending in `_1` or another digit suffix.
**Trap:** TIA appends collision suffixes without asking, in DB statics as well
as interface rows, and a suffixed name cuts a client with no error dialog
(LESSONS 2026-07-30). Step 179 sweeps the browse names by machine; these
statics are swept here, by eye.

**178.** Right-click **`SafetyInputStandIn`** → **Cross-references**.
*You should see:* exactly **four read accesses**, all at the call in
`Main_Safety_RTG1`, and **no write access from any block on the CPU**.
*Tell me:* the access count and where each one is.
*Why zero writes is the interesting half:* the only writer of this DB is the
stand-in writer, outside the CPU. A write access from a block on the CPU means
something in the program is fabricating its own stimulus.

**179.** Run the F-side absence check from a shell **outside TIA**:

    python plc/forklift-safety/evidence/m5-25b-f-absence-verify.py opc.tcp://<instance IP>:4840

using the IP read back at step 4. It needs `asyncua`; use the same environment
the bridge's client runs in. **It writes nothing** — the claim is that the datum
is unreachable, and a script that tried to write it would be asserting the
reachability it exists to deny.
*You should see:* the namespace array, a **positive control** reading the four
`Forklift/Safety/` mirrors, then the absence sweep, the `DataBlocksGlobal`
listing, a collision-suffix sweep, and a final `RESULT:` line.
*Tell me:* the `RESULT:` line, and what `DataBlocksGlobal` was reported to hold.
**Stop if the result is FAIL** — the script names what is reachable.
*Why the control runs first and the script aborts if it fails:* **an absence
proven by a browse that never reached the server is not an absence.** The
mirrors are the proof that this client sees the CPU at all.

**180.** Save that output to
`plc/forklift-safety/evidence/m5-25b-f-absence-<today's date>.log`.
*Tell me:* the file name you used.
**Trap:** one log per run, unique name per run (LESSONS 2026-07-28).

> **Chunk N done.** The S015 check is running in the CPU, its signature is
> recorded, and "no client can reach the F-side" is a read-back from a different
> protocol stack rather than a setting.

---

## Chunk O — in force, and what the delta does with no writer

*Ends with: three `PT`s read in force, and the invalid-boot signature of §5.4
observed — which is the only part of §4.5 step 13 that can be run today.*

**181.** In **Watch and force tables**, look for a table named
**`Forklift F gate`**.
*Tell me:* whether it exists. If it does, tell me roughly how many rows it has.
*Context:* SPEC §8 specifies it in four groups. Whether the 2026-07-30 build
created it is not recorded anywhere, which is why this is a question and not an
instruction.

**182.** Make sure **SPEC §8 Group 1**'s four rows are in that table (creating
the table if step 181 found none): the three `"SafetyInputStandIn"` channels,
and **`"SafetyInputStandIn".StandInHeartbeat`** in **Dec**.
*Tell me:* four rows present.
**No row of this table is ever modified.** It is a **reading** instrument: the
stimulus is the writer, fail-safe rows could not be modified anyway with safety
mode activated (`2206:000002`), and a fabricated latch demonstrates nothing.

**183.** Add **SPEC §8 Group 3**'s eight new validity rows:
`"InstF_Forklift_Safety".StandInValid`, `.HeartbeatSeen`,
`.StandInStaleTimer.ET`, `.StandInStaleTimer.PT`, `.EStopClosedValid`,
`.ZoneClosedValid`, `.ResetPressedValid`, `.HeartbeatMemory` (Dec).
*Tell me:* eight rows added.

**184.** Confirm **Group 2**'s four rows are present:
`"InstF_Forklift_Safety".EStopDemand`, `.ZoneStopDemand`,
`.SafetyResetRequired`, `.SafetyResetFault`.
*Tell me:* four rows present.

**185.** Put the table in **Monitor**.
*Tell me:* whether any row shows a monitoring-error icon.
**Trap:** an error icon on exactly the rows whose offsets moved is the live tell
of a download that did not re-initialise `DB3` (step 174).

**186.** Read the **three timer `PT` values in force**.
*Expected:* `StandInStaleTimer.PT` = `T#1s`, `ResetHoldMinTimer.PT` =
`T#200ms`, `ResetHoldMaxTimer.PT` = `T#3s`.
*Tell me:* the three values as the watch table shows them.
**Trap, and this is why they are read here and not off the interface.** An
interface *Default value* governs **nothing** once the instance DB exists. A
disagreement here is a stale build or a download without re-initialisation — not
a typo — and the repair is step 174 again, not an edit.

**187.** Read the **invalid-boot signature** off the table, all in one reading:

    StandInValid                FALSE
    HeartbeatSeen               FALSE
    StandInStaleTimer.ET        at PT (T#1s), not climbing
    EStopClosedValid            FALSE
    ZoneClosedValid             FALSE
    ResetPressedValid           FALSE
    EStopDemand                 TRUE
    ZoneStopDemand              TRUE
    SafetyResetRequired         TRUE
    SafetyResetFault            FALSE

*Tell me:* each of those ten readings.
**This is the delta working, not the delta failing.** With no writer, the
heartbeat never advances, so life is never seen, so the logic refuses to
believe a frozen world and holds both demands. It is SPEC §7.3 rows 1 and 6
observed — *wire NC, program NO*, rebuilt for a software wire.
**Two readings would be the defect signature of this whole delta:**
`StandInValid` **`TRUE`** with the heartbeat frozen (V2's boot polarity is
wrong, or V4 is reading the timer un-negated), or `EStopClosedValid` **`TRUE`**
while `StandInValid` is `FALSE` (V5 is not conjoined with validity). If you see
either, **stop**.
*Also worth reading, and it is not a fault:* Group 1's raw channel rows read
`FALSE` too, so they and the validated rows agree right now. **They differ
exactly when `StandInValid` is `FALSE` and a channel is closed** — and that
difference on screen is the S015 check doing its work. It cannot be seen until
a writer exists.

**188.** Screenshot the watch table showing that signature, saved as
`plc/forklift-safety/evidence/m5-25b-f-invalid-boot-signature.png`.
*Tell me:* saved.

**189. BLOCKED, and it is recorded rather than worked around.** SPEC §4.5 step
13 — start the stand-in writer, watch `HeartbeatSeen` and `StandInValid` go
`TRUE`, then stop it and watch validity drop and both demands latch — **cannot
be run in this session.** No writer implementation exists: SPEC §7 is the
contract, and its **implementation home is an owner ruling that has not been
made** (SPEC §10 open item 8). Until it lands, no implementation may be written,
here or at the keyboard.

*What is proven without it, and it is not nothing:* the delta compiles, downloads
with a changed collective signature, is reachable by no client, reads four
standard tags and writes none, holds its three `PT`s in force, and **fails in
the stopping direction with the stand-in dead** (step 187). That is the failure
row the check exists for.

*What stays unproven until the writer exists:* that validity ever becomes
`TRUE`; every T6 step; the re-arming of the stale timer; and the whole reset
path on this build. **No gate criterion may cite them.**
*Tell me:* that you have read this and are not going to improvise a writer.

**190.** Record the **F-session read-backs** in one go, for the record table:
safety mode (step 118), the new collective signature (step 176), the F-OB and
its cycle (step 120), and the three `PT`s (step 186).
*Tell me:* the four lines, each with today's date.
*Why they are collected rather than trusted from earlier in the session:* SPEC
§4.5 step 14 asks for them together, at the end, against the build that is
actually running.

**191.** Fill in every remaining row of the **record table** at the top of this
document with its date, and rewrite the **progress block**.
*Tell me:* done.

> **Chunk O done.** The S015 validity check runs in the F-CPU, and the F-program
> is deliberately inert until the stand-in writer exists. It establishes **no
> safety integrity claim**: the stand-in stays a standard DB, standard tags stay
> unsafe, and what the check adds is honesty about liveness (SPEC §5.4, §7.8).

---

## Chunk P — what is still not built, and who owns it

**No step above builds any of the following, and none may be added that does.**
Each is somebody's specified work, and where a step in this document would have
depended on one, it is marked BLOCKED in place rather than filled with an
invented value.

| What is missing | Whose it is | What it blocks here |
|---|---|---|
| **The stand-in writer's implementation home** — an **owner ruling**, not made. SPEC §7.1–§7.3 is the complete contract; no implementation exists and none may be written until the ruling lands | **Owner** (SPEC §10 open item 8) | Step 189, and with it every T6 step, every criterion-(a) run, and any observation of `StandInValid` `TRUE` |
| **The field evaluation's wall-clock transition log** — §7.6's four-way correlated record is the only instrument that distinguishes a field-originated write from a scripted one | **m5-12**, not started (SPEC §10 open item 9) | The zone channel's criterion-(a) form. Without it a zone transition is an operator command whatever the narration says |
| **`sim/scenarios/forklift_commissioning.md` §13** still stimulates by watch-table *Modify*, which ADR 0015 retired | **sim agent** (SPEC §10 open item 10) | Nothing in this document, but it will contradict SPEC §9.1 for anyone reading both |
| **The `RESET_HOLD_MIN` sampling deviation** — 200 ms against a 100 ms F-OB is two cycles where §4.3 requires five | **safety-spec**, with AT-08 re-read beside it (SPEC §10 open item 2) | Nothing is tuned here; step 120 names it and every evidence record from this build carries one line naming it |
| **AT-08 (b)'s scope** — the timed stimulus `reset pulse <ms>` now exists; whether the sub-window rejection test is in scope is a ruling, shadowed by the one above | **safety-spec** (SPEC §10 open item 3) | Nothing here; the program behaves identically either way |
| **HMI v2a** (m5-14a) — without it the standard cell is inert after chunk D | **hmi agent** | Teleop drive and any showcase re-take, per chunk D |
| **The bridge's forklift-group repoint and the §12.10 slot tables** | **bridge agent** | The vehicle-side half of the §14 envelope |
| **The stand-in writer's speed extension** — the 45016 listener, the seven new members, `WARN` on the field link (`plc/forklift-safety/SPEC.md` §11.2) | **bridge agent** (m5-49 report request) | Chunk Q's T7 rehearsal (its step Q17 second half). The F-delta itself types and shows its no-source signature without it |
| **The WSL-side `SPD`/`MOT`/`PING` client** beside `safe_speed_channels.py` | **agv agent** (m5-49 report request) | Same rehearsal |
| **The warning node `Forklift/Warning/ForkliftWarningFieldOccupied` and its bridge slot** (`plc/forklift/SPEC.md` §14.16) | **interface + bridge agents** (m5-49 report request) | Chunk Q's standard-side half — the ceiling delta compiles against the DB either way, but nothing drives the node until the slot exists |

---

## Chunk Q — the m5-49 SLS/SS1 and warning-ceiling delta: specified, not yet expanded

**Nothing below is a numbered step, and the honest count for this chunk today
is zero.** The m5-49 brief produced the specification and its click-paths; the
expansion into one-action-one-observable numbered steps is a **later brief**,
which starts from these two sources and adds nothing of its own judgement:

| Half | Click-path in force | What it builds |
|---|---|---|
| **F-side** | `plc/forklift-safety/SPEC.md` **§11.9** (steps Q1–Q17), with the network tables in §11.5 and the counts in §11.3 | Seven stand-in members (SD2), FB2 at 10 / 6 / 43 / 17, twenty-seven new networks for 49 in all, two re-pointed pins, watch Group 5, the no-source signature |
| **Standard side** | `plc/forklift/SPEC.md` **§14.16** | One new DB `ForkliftWarning` and its requested node, one constant `WARNING_SPEED_CEILING`, one temp, the modified part-8 ceiling statement, two watch rows |

**Ordering constraints the expansion must carry.** The F-side half depends on
chunk O's build (the 22-network, S015 program in the CPU) and on nothing else
— it is typeable **before** the writer's speed extension exists, and §11.9
step Q16's no-source signature is exactly the with-nothing-attached proof, the
way chunk O's step 187 was. The standard-side half depends on the interface
agent's ruling on the warning node; typing it against an unruled path is how
two documents start disagreeing, so it **waits for the ruling**, and the
F-side half does not wait for it. The T7 rehearsal (Q17, second half) waits on
the two implementation requests in chunk P's table.

**When the expansion lands it takes step numbers 192 onward**, updates the
step index, and re-derives every count from the spec tables at that moment —
never from this stub.

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
| J — F ground truth and decision | 117–125 | licence, safety mode, pre-delta signature, F-OB cycle, F7 |
| K — heartbeat and FB2 interface | 126–142 | four DB members, interface 4 / 4 / 18 / 3 |
| L — the validity networks | 143–152 | V1–V7 ahead of `CauseGone` |
| M — re-point and last network | 153–167 | thirteen pins re-pointed, 22 networks, M2 last |
| N — call, compile, download | 168–180 | changed signature, 4 reads / 0 writes, absence proven |
| O — in force, no writer | 181–191 | three `PT`s in force, the invalid-boot signature |
| P — not built here | — | the writer, the field log, two safety-spec rulings |
| Q — m5-49 delta, not yet expanded | — (192+ when its brief lands) | the click-paths in force: `forklift-safety/SPEC.md` §11.9, `forklift/SPEC.md` §14.16 |

**191 steps.** If a step turns out to contain two actions, split it and say the
total has changed.

**Steps 1–116 are the standard-program side and steps 117–191 are the F-side.**
They are two sittings for most people, and the only ordering constraint between
them is that **chunk H runs before chunk J**.
