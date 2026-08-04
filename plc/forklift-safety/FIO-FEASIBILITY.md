# F-I/O feasibility procedure — does a configured F-DI reach the F-program on this instance?

**This is a procedure, not a specification.** It builds nothing that survives it
and it decides nothing. It exists to settle, **in TIA Portal and PLCSIM
Advanced**, the one question ADR 0011 D2 rests on:

> Can the simulated safety scanner reach the F-program through **real configured
> F-I/O**, whose channel values are driven by the **S7-PLCSIM Advanced API by tag
> name** — the simulation's equivalent of wiring?

**What it blocks.** The PLC half of M5 and nothing else. The vehicle-side waves —
the scanner and navigation-lidar models, SLAM, Nav2, HMI v2, the monitoring plane
— proceed on their own briefs regardless of how this comes out, because none of
them depends on which side of the CPU boundary the scanner signal enters. What
depends on the verdict is the **input path** of `plc/forklift-safety/SPEC.md`,
and only that: §7, plus three pins at §4.2 step 8.

**Status: nothing below has been executed by this document's author**, who has
neither tool installed. Every menu path, dialog name, tag name and API call name
here is **what to look for so it can be recognised**, never a value to type or to
quote. **Every value this procedure produces is a design value until the tool
prints it**, and it becomes a fact only when it is written into a *Record* table
below with its date (ADR 0006; LESSONS 2026-07-27). **No gate criterion may rest
on any of it before then.**

**The verdict section is deliberately empty.** Nobody but the owner, sitting in
front of the tool, may fill it in.

## Authority

| Document | What it fixes | Relation to this one |
|---|---|---|
| `docs/adr/0011-sensored-autonomy-architecture.md` **D2** and facts **F1–F7** | That the scanner reaches the F-program through configured F-I/O driven by the API; the feasibility condition, its trigger, and its named fallback | **Binding.** This procedure is D2's feasibility condition, executed |
| `docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md` **D4** | The feasibility-checkpoint and inert-fallback pattern | **Pattern.** §0.1 below is what makes the fallback inert here |
| `plc/forklift-safety/SPEC.md` **§2.1**, **§7**, **§10 open item 1** | The present ruling that no usable F-I/O channel exists, the standard-DB stand-in stimulus, and the open item this procedure closes | **The document under test.** §2.1 is a *design assessment* that explicitly asks to be falsified; this is the falsification attempt |
| `docs/LESSONS.md` | The six standing rules restated in §0.2 | **Binding** |
| `CLAUDE.md` §2 invariants, §9 conventions | Wire NC / program NO, and that safety never traverses the network | **Binding.** Nothing here changes either |

---

## 0. Before you start

### 0.1 The copy rule — what makes the fallback inert

ADR 0011 D2 says the fallback "requires building nothing and removing nothing".
That is true of the *fallback* and not of this *procedure*: adding a PROFINET IO
system and an F-DI to a running F-CPU configuration is a hardware change to the
build that currently compiles, downloads, reaches RUN and executes the F-runtime
group (ADR 0009 context, 2026-07-29).

**So the probe runs on a copy.**

1. **Archive the working project** (*Project → Archive*, or *Save as* to a new
   name). Record the archive file name and its date in the table below.
2. Do every step of this procedure **in the copy**.
3. On any abort, **delete the copy**. The working build was never touched, and
   the fallback costs one file deletion rather than an undo history.
4. On a yes verdict, the copy is still not the build: the design change it
   licenses is a separate brief against `SPEC.md` §7 and §4.2 step 8.

| Record | Value | Date |
|---|---|---|
| Working project archived as | `safe_amr` left untouched; the probe was taken as *Save as* rather than as an archive file | 2026-08-04 |
| Probe copy project name | `safe_amr_FIOPROBE` | 2026-08-04 |
| PLCSIM Advanced instance used for the probe | `FIOPROBE` (fresh name, TCP/IP single adapter, 192.168.53.1) | 2026-08-04 |

> A **fresh PLCSIM instance name** is the reliable reset for PLCSIM network
> configuration — an existing name remembers its old IP configuration and locks
> the fields (LESSONS 2026-07-27). If the probe needs its own instance, give it
> its own name rather than reconfiguring the commissioned one.

### 0.2 Standing discipline, every step

Each of these has already cost this project a session. They apply to every step
below without being repeated in it.

1. **Read values from the watch table's in-force values**, never from an
   interface default, a properties dialog's proposal or a start value. A default
   governs nothing once the instance data exists (LESSONS 2026-07-28).
2. **After every download, check the block diff circles are solid green** before
   reading anything. A stale build shows as monitoring-error icons and in-force
   values that contradict the code, and it will make this procedure produce a
   false no (LESSONS 2026-07-28). On the F-side there is a stronger instrument:
   compare the **F-collective signature online against offline** (`SPEC.md` §2).
3. **After any *Change device*** — and treat a CPU firmware-version change or a
   safety-system-version change as one — **re-verify the `DemoCell` server
   interface, its access control and the OPC UA runtime licence, then
   re-download** (LESSONS 2026-07-27). A *Change device* silently deletes the
   server interface and resets security.
4. **Sweep the new names for TIA's silent `_1` collision suffixes** after every
   download. Adding a station and an F-DI creates PLC tags and an F-I/O data
   block, and TIA appends `_1` without asking, in DB statics and interface rows
   both (LESSONS 2026-07-30). A browse name that gained a suffix cuts a client
   with no error dialog.
5. **A tool-derived identifier is a design value until it has been read back.**
   Every module name, order number, F-I/O DB name, member name, tag name and API
   call name in this document is a **thing to look for**. Write the one the tool
   actually shows into the *Record* table, and mark it **owner-verified-in-tool**
   with its date.
6. **State an expectation as the rule, not as the single value one observation
   produced** (LESSONS 2026-07-28). Where a step below predicts a reading, the
   prediction is the mechanism; if the number differs, record the number and
   check the mechanism, do not adjust the rule to fit one sample.

### 0.3 What this procedure never does

- **It adds no safety logic.** No network is added to `F_Forklift_Safety`, no pin
  on the call in `Main_Safety_RTG1` is rewired, and no field evaluation of any
  kind is designed here. The channel is observed **at the process image and in
  the F-I/O data block**, which is exactly where an F-program operand takes its
  value from, and that observation needs no code.
- **It designs no scanner.** Field sets, monitoring cases, discrepancy time,
  input delay, the 1oo2 arrangement and the module's parameterisation values are
  design questions ADR 0011 explicitly leaves open. This procedure needs **one
  readable channel**, not a parameterised device.
- **It produces no gate evidence and claims nothing.** Anything measured on a
  simulated F-I/O path is evidence about the tool, never about device behaviour
  (F5), and the claim boundary of ADR 0011 D5 applies to every sentence written
  about it.

---

## 1. Step 1 — the two version numbers, read from the tool

**The question.** Does this installation support F-I/O simulation *at all*? ADR
0011 **F1** records that simulating a project with fail-safe modules requires
safety system version **V1.6, V2.0, V2.1, V2.2, V2.3, V2.4 or V2.5** and does not
work correctly with an older one (PLCSIM Advanced **V5.0** manual). **F2** records
that the **V4.0** manual names only V1.6 and V2.0. **F4** records that the
supported list for **V6.0 and later is unverified**.

**Do.**

1. **Read the installed PLCSIM Advanced version.** The PLCSIM Advanced control
   panel states it (the panel's *About* / version field), and Windows'
   installed-programs list states it independently. Read **both** and record the
   exact string each prints, including the update level. Do not round it, do not
   translate "V5" into "V5.0", and do not write a version number the tool did not
   print.
2. **Read the project's safety system version.** *Safety Administration →
   Settings*, the **safety system version** entry. Record the exact string.
3. **Read the CPU's firmware version** from the device view, and the **TIA Portal
   version and update** from *Help → Installed software*. Both constrain which
   safety system versions the project may take, so both belong beside the other
   two.

**Record.**

| Item | What the tool printed | Where it printed it | Date |
|---|---|---|---|
| PLCSIM Advanced version (control panel) | not read — **the V7.0 control panel carries no About / version field**; its title bar reads `S7-PLCSIM Advanced V7.0` | PLCSIM Advanced control panel | 2026-08-04 |
| PLCSIM Advanced version (installed programs) | `SIMATIC S7-PLCSIM Advanced V7.0` (DisplayVersion `V7.0`); beside it `PLCSIM Advanced Single SetupPackage V7.0` = `07.00.0000`, `SIMATIC PLCSIM Advanced SimRT` = `07.00.0000` | Windows installed-programs registry | 2026-08-04 |
| Project safety system version | `V2.8` | Safety Administration → Settings | 2026-08-04 |
| CPU firmware version | `CPU 1513F-1 PN`, `6ES7 513-1FM03-0AB0`, `V3.1` | Device view → CPU properties | 2026-08-04 |
| TIA Portal version + update | `V21` | Help → Installed software | 2026-08-04 |

**Reading:** PLCSIM Advanced **V7.0** falls under **F4** — no verified supported
list exists for V6.0 or later, so the ADR's table cannot answer question (i) in
either direction, and the project's safety system version **V2.8** is outside
F1's V5.0-era list for the same reason: that list stops at V2.5 and predates both
this tool version and this safety system version. Per the F4 row this is **not an
abort**; steps 2, 3 and 4 settled it empirically, and no safety-system-version
change was attempted (the remedy table below is therefore not applicable).

**What the reading means.**

| Reading | Meaning |
|---|---|
| PLCSIM Advanced **V5.0**, safety system version **in F1's list** | The supported combination named by a pinned manual. Continue at step 2 with the version question answered **yes on the document**; steps 2–4 then answer it **in the observable** |
| PLCSIM Advanced **V5.0**, safety system version **outside F1's list** | This is **F3's probable cause** of `SPEC.md` §2.1's "no usable F-I/O channel" finding — probable, not established. **Do not abort yet.** Go to the remedy below |
| PLCSIM Advanced **V4.0** | F2's list is narrower (V1.6, V2.0 only). Same remedy path, against the narrower list |
| PLCSIM Advanced **V6.0 or later** | **F4: the supported list is unverified**, so the ADR's table cannot answer the question in either direction. **This is not an abort.** Record the version, record that no verified list exists for it, and let **steps 2, 3 and 4 settle it empirically** — an observable channel that reintegrates and accepts an API write outranks an absent table |

**The remedy, when the safety system version is outside the list.** Look in
*Safety Administration* for a safety-system-version change, and record whether it
is offered at all. Before touching it:

- The change **invalidates the F-collective signature** and requires a full
  safety recompile and re-download. That is precisely why §0.1 puts this on a
  copy.
- The tool may **refuse**, for a reason that is itself the finding: CPU firmware
  too new, the installed TIA version not offering the older version, or the
  existing F-blocks not being convertible. **Record the refusal text verbatim.**
- If it accepts, re-run `SPEC.md` §2's F0–F6 checkpoint on the copy before
  reading anything else. A copy whose F-runtime group no longer reaches RUN
  answers a different question than the one asked here.

| Record | Value | Date |
|---|---|---|
| Safety-system-version change offered? | not attempted — under F4 the version question was left to steps 2–4 | 2026-08-04 |
| Versions offered by the dialog | not read | 2026-08-04 |
| Version selected, or refusal text verbatim | not read | 2026-08-04 |
| F0–F6 re-run on the copy after the change | not applicable, no change made | 2026-08-04 |

**Abort condition → fallback.** The safety system version is outside the
supported list **and** the tool refuses every change into it, **or** the change
succeeds and the F-runtime group no longer reaches RUN. This is **ADR 0011 D2's
first named trigger** — question (i) answering no. Delete the copy and take the
fallback of §6.

---

## 2. Step 2 — configure an ET 200SP F-DI, compile, download, RUN

**The question.** Can the module be configured at all on this CPU, and does the
project still compile, download and run with it present? A configuration that
cannot be downloaded answers question (i) in the observable, whatever the version
table says.

**Do.**

1. In the copy's network view, give the CPU a **PROFINET IO system** and add an
   **ET 200SP station**: head module (IM 155-6 PN family), a **BaseUnit** for the
   F-DI, the **F-DI** itself from the catalogue, and the **server module** if the
   station calls for one — a station may complain about a missing server module
   only at compile rather than at placement, so place it now and record what the
   tool asked for.
2. Take **whatever F-DI the catalogue offers** — this procedure needs one
   readable channel, not a chosen device. **Record the order number and firmware
   version of the module you actually placed**; ADR 0011 explicitly leaves the
   exact order number undecided, so nothing downstream depends on which one it is.
3. **Leave the parameterisation at the tool's proposal** except where a value
   blocks the download. Discrepancy time, input delay and the 1oo2 arrangement
   are design questions and are not settled here (§0.3).
4. **Enable *value status*** in the module's properties if it is offered — step 3
   reads it, and it costs input address space, so it is easier to have it from
   the start than to re-address later.
5. **Read back, before compiling**: the module's **I/O address range**, the
   **PROFIsafe F-destination address** (`F_dest_add`) and **F-source address**,
   the **F-monitoring time** for the F-I/O, and the **name of the F-I/O data
   block** TIA generated for the module.
6. **Compile the whole project — hardware and software.** Record every error, and
   record the warnings; a safety program is expected to be reported on, and the
   count matters more than any single line.
7. **Download to the PLCSIM Advanced instance.** Expect TIA to require the CPU in
   STOP for a safety-program download. Then apply §0.2 rules 2 and 4: **solid
   green diff circles**, **F-collective signature online = offline**, and a
   **sweep of the new names for `_1` suffixes**.
8. **Read the CPU's operating state and the F-runtime group's state.** RUN is not
   enough on its own: the group must be **executing**, and *Safety
   Administration* online must read **safety mode activated**.

**Record.**

| Item | What the tool printed | Date |
|---|---|---|
| Head module placed (name, order number, FW) | `IO device_1 [IM 155-6 PN ST]`, `6ES7 155-6AU02-0BN0`; FW not read. Assigned to `PROFINET IO-System_1` | 2026-08-04 |
| F-DI placed (name, order number, FW) | `F-DI 8x24VDC HF_1`, `6ES7 136-6BA01-0CA0`, `V2.0` | 2026-08-04 |
| F-DI input address range | inputs `I0.0 … I6.7`; outputs `Q0.0 … Q4.7`; **process image `---` (not assigned)** | 2026-08-04 |
| Value status enabled, and its address bits | **not offered** — this module's *Module parameters → General* page carries only *Startup: comparison preset to actual module*; no value-status checkbox exists to enable | 2026-08-04 |
| `F_dest_add` / F-source address | `F-destination address 65534` / `F-source address 1`; PROFIsafe **V2 mode**, expanded protocol (XP); F-parameter signature (with addresses) `65255` | 2026-08-04 |
| F-I/O F-monitoring time | `150 ms` (manual assignment unchecked) | 2026-08-04 |
| **F-I/O data block name, exactly as generated** | `F00000_F-DI8x24VDCHF_1`, DB number `30011` | 2026-08-04 |
| Channel tag names in the PLC tag table, exactly | none generated by TIA. One tag was created for the probe: `ProbeFdiCh0` = `%I0.0`. **The *IO tags* tab is read-only while online** — the name could only be entered after going offline | 2026-08-04 |
| `_1` suffix sweep result | TIA appended `_1` unasked to **three** names: the placed module `F-DI 8x24VDC HF_1`, the server module `SRVM BC_1`, and the generated F-I/O DB `F00000_F-DI8x24VDCHF_1`. The hand-entered `ProbeFdiCh0` survived compile and download unsuffixed | 2026-08-04 |
| Compile: errors / warnings | `errors: 0; warnings: 2`. The safety-side line is *"The F-module 'F-DI 8x24VDC HF_1' was not interconnected in the fail-safe program"* — expected, since §0.3 forbids adding logic. Second warning is the pre-existing OPC UA "no security" note | 2026-08-04 |
| Download: diff circles solid green? | yes, solid green after the download and again after the tag-name download | 2026-08-04 |
| F-collective signature online / offline | `5DC99AD0` / `5DC99AD0`, version comparison green; offline and online safety programs both reported consistent | 2026-08-04 |
| CPU operating state | `RUN` | 2026-08-04 |
| Safety mode | *"Safety mode is activated."* Fast Commissioning not activated | 2026-08-04 |
| F-runtime group executing? | yes — `FOB_RTG1` (OB123) present and the safety program consistent online; no F-runtime-group fault in the diagnostic buffer | 2026-08-04 |

**What the reading means.**

| Reading | Meaning |
|---|---|
| Compiles, downloads, CPU **RUN**, safety mode **activated**, F-runtime group **executing** | The configuration is viable in the tool. The remaining questions are behavioural — steps 3, 4 and 5 |
| Compiles and downloads, but the CPU will not leave STOP, or the F-runtime group is not executing | Read the **CPU diagnostic buffer** before concluding anything, and record the entries verbatim. A failure whose mechanism is unread is not a finding (LESSONS 2026-07-27) |
| The hardware **compile** fails on the F-DI or the station | Record the message verbatim. Distinguish a **configuration** complaint that a correction fixes (missing server module, address overlap, F-address collision) from a **support** complaint that names the safety system version or the simulation — only the second is the abort |
| The CPU enters **STOP with an F-runtime-group or F-I/O fault** | Record the buffer entry. This is the reading that turns `SPEC.md` §2.1's design assessment into an observation, whichever way it falls |

**Abort condition → fallback.** The F-DI cannot be configured, or the project
cannot be compiled or downloaded with it present, or the CPU will not reach RUN
with the F-runtime group executing. This answers question (i) **in the
observable**, which is the stronger of the two answers. Delete the copy and take
the fallback of §6.

> **A variation is a design change, not a workaround.** If the ET 200SP path
> fails and a **centrally plugged** F-DI, or a different F-I/O family, looks like
> it would succeed, that is worth **recording and reporting** — ADR 0011 D2 names
> the ET 200SP F-DI specifically, so adopting a different arrangement is an
> architecture decision for the owner, not a substitution to make quietly at the
> keyboard.

---

## 3. Step 3 — reintegration, and what QBAD / PASS_OUT / value status actually show

**The question.** Does the configured F-I/O become and stay usable, or does it sit
passivated with fail-safe zeros substituted into the channel? This is the exact
mechanism `SPEC.md` §2.1 points 2–4 predicts, and it is the difference between a
channel and a permanently tripped input.

**What the manual says, so that the reading can be compared to it.** ADR 0011
**F5** (SIMATIC Safety programming manual §10.7.4, §12.1): S7-PLCSIM does **not**
fully behave like a real F-CPU; **F-I/O startup behaviour cannot be simulated
exactly**; **automatic reintegration occurs from the second cycle of the
F-runtime group**; channel values initialise to **0** and value status to **1** on
STOP→RUN; and **simulated value status does not drive QBAD / PASS_OUT as real
F-I/O does**. That last clause is why this step reads three things and not one:
on real F-I/O they move together, and here they may not.

**Do.**

1. Build a watch table — call it something that cannot be confused with `Forklift
   F gate` (`SPEC.md` §8), because that table is the demonstration's and this one
   is a probe's. Put in it, **symbolically**:
   - every **channel tag** of the F-DI, from the PLC tag table;
   - the **value status** bits, if enabled;
   - the F-I/O data block's status members. **Read the member list out of the
     generated block rather than typing names from memory** — the ones to look
     for are `PASS_ON`, `PASS_OUT`, `QBAD`, the per-channel `QBAD_I_*`,
     `ACK_NEC`, `ACK_REI`, `IPAR_EN`, `IPAR_OK` and `DIAG`, and their exact
     spelling and presence are version-dependent.
2. Open the table in **Monitor**, with safety mode **activated**. Record the
   **in-force values**, never the start values (§0.2 rule 1).
3. **Cycle the CPU STOP → RUN** and read the same rows again, at rest.
4. Read the **diagnostic buffer** and the module's **online diagnostics** page,
   and record what each says about the module's state.
5. If `ACK_REI` / `ACK_NEC` indicate that an acknowledgement is required, record
   that fact and **stop there** — do not build an acknowledgement mechanism. A
   reintegration acknowledgement is an additional device and an additional SF-08
   consideration (`SPEC.md` §10), which is design work this procedure does not do.

**Record.**

Generated block members, read out of `F00000_F-DI8x24VDCHF_1` rather than typed
from memory — In: `PASS_ON`, `ACK_NEC`, `ACK_REI`, `IPAR_EN`, `DISABLE`; Out:
`PASS_OUT`, `QBAD`, **`ACK_REQ`** (not `ACK_REI` on the output side), `IPAR_OK`,
`DIAG`, `DISABLED`, `BASEID_ACTIVE`. **No per-channel `QBAD_I_*` members exist**
in this version of the block.

| Row | Immediately after STOP→RUN | At rest, no stimulus | Date |
|---|---|---|---|
| Channel value(s) | `ProbeFdiCh0` = FALSE | FALSE, unchanged over minutes | 2026-08-04 |
| Value status bit(s) | not applicable — value status is not offered by this module | — | 2026-08-04 |
| `PASS_OUT` | TRUE | TRUE, unchanged | 2026-08-04 |
| `QBAD` | TRUE | TRUE, unchanged | 2026-08-04 |
| `QBAD_I_*` (per channel) | member does not exist in the generated block | — | 2026-08-04 |
| `ACK_NEC` / `ACK_REI` | `ACK_NEC` = TRUE (start value TRUE) / `ACK_REI` = FALSE. `ACK_REQ` = **FALSE**, i.e. the block never raised an acknowledgement request | unchanged | 2026-08-04 |
| `DIAG` | `16#00` | `16#00` | 2026-08-04 |
| Diagnostic buffer entries, verbatim | 15 entries, **none naming PROFINET, the IO device, the F-I/O or the F-runtime group**. The newest are OPC UA server state changes on download, `Communication initiated request: WARM RESTART - CPU changes from STARTUP to RUN mode`, `ES/HMI communication: Transition from provisioning mode to secure mode`, `CPU access protection configuration changed`, `Retentive data warning: Retentive data lost`, `Technology package MC Base loaded: Version: V9.0.1`, `Boot up - CPU changes from OFF to STOP (initialization) mode` | — | 2026-08-04 |
| Module online diagnostics | head module and F-DI both read **"Module exists. OK"** — no channel fault is being reported while the block reports `QBAD` = 1 | — | 2026-08-04 |
| Acknowledgement attempt | **refused by the tool.** Writing `ACK_REI` from the watch table returns, verbatim: *"Debugging of fail-safe tags is not allowed in permanent safety mode. (2206:000002)"*. The reintegration acknowledgement is therefore not reachable from the engineering connection without deactivating safety mode, which §7.1 of `SPEC.md` and step 4's refusal row both rule out | — | 2026-08-04 |

> **You cannot see "the second cycle" in a watch table**, and this step does not
> ask you to. What is observable is the **outcome** F5 predicts: whether
> passivation clears **by itself**, without any acknowledgement, shortly after
> RUN. Record the outcome; do not report a cycle count the tool did not print.

**What the reading means.**

| Reading | Meaning |
|---|---|
| `PASS_OUT` / `QBAD` go to **0 without any acknowledgement** shortly after RUN | Automatic reintegration as F5 describes. The channel is live and step 4 is the next question |
| `PASS_OUT` / `QBAD` stay **1** indefinitely | The module is **passivated with no partner**, which is `SPEC.md` §2.1 points 2–4 **observed rather than assessed**. Under wire-NC / program-NO the channel then reads permanently tripped, a demand would latch at power-up, and no reset could ever succeed because the cause never clears. **This is the abort** |
| Value status reads **1** while `QBAD` / `PASS_OUT` disagree with it | Exactly the F5 divergence: **simulated value status does not drive QBAD / PASS_OUT**. Record both. It does **not** by itself abort the procedure — it means **any future evidence on this path must state which of the two it was read from**, and must never present a value-status reading as a passivation reading |
| Reintegration requires an **explicit acknowledgement** | Not an abort, and not something to solve here. Record it as a finding: it adds a device and an SF-08 consideration to the design that the ADR 0011 D2 path would inherit |

**Abort condition → fallback.** The module remains passivated with fail-safe
values substituted into the channel, with no reintegration and no acknowledgement
that clears it. Record the readings — they close `SPEC.md` §10 open item 1 as
**confirmed by observation** rather than as an assessment — then delete the copy
and take the fallback of §6.

---

## 4. Step 4 — can the PLCSIM Advanced API write the channel **by tag name**?

**The question.** ADR 0011 D2's **second named trigger**: whether the Gazebo
scanner model can drive those channel values through the S7-PLCSIM Advanced API
**by tag name** (F7), and **what the F-program reads when it does**.

**Why by tag name and never by address.** F7 is explicit: the API is to be
accessed by tag name rather than by address areas, and it warns against writing
bytes that belong to other applications or that contain internal data **such as
qualifier bits for fail-safe modules**. An address-area write into an F-I/O range
can land on a PROFIsafe qualifier. **A by-address write is not a fallback for a
failed by-name write — it is the thing the manual forbids**, and if by-name
writing does not work, the answer to this step is no.

**Do.**

1. **Use the smallest harness that answers the question.** Look first for the API
   form the installation already provides — the PLCSIM Advanced installation
   directory carries the API's own files and documentation, and if a .NET
   assembly is among them, Windows PowerShell can load it with `Add-Type -Path`
   and introduce **no new project dependency**. **Record the API form and file
   you actually used.** Anything that would add a dependency — a Python bridge to
   .NET, a new package — is **proposed in a report and waited on** (CLAUDE.md
   §10), not adopted at the keyboard mid-probe.
2. **Find the instance and open an interface to it.** The calls to look for are
   the runtime manager's registered-instance list and its create-interface call;
   **record the names your installed API version actually exposes**, from its
   object browser or its documentation, rather than the shapes named here.
3. **Update the tag list, then enumerate it.** This is the decisive read-back of
   the whole step. The tag list is populated from the downloaded project, so it
   must be refreshed **after** step 2's download. Enumerate it and answer, from
   the enumeration and not from expectation:
   - **Does the F-DI's channel appear in the tag list at all?**
   - **Under exactly what name** — the PLC tag-table symbol, a qualified form,
     something else? Record the string verbatim, character for character. This is
     a tool-derived identifier in the strictest sense: it is the string the
     scanner-side harness would have to use forever.
   - Does the **F-I/O data block** appear, and are its members reachable?
4. **Write the channel by name**, with the CPU in RUN and safety mode activated,
   and **read it back three ways**:
   - through the **API** (the by-name read);
   - in the **TIA watch table**, in-force value;
   - together with `QBAD` / `PASS_OUT` / value status from step 3, **in the same
     observation**, because the interesting failure is a write that appears to
     land and is then overwritten.
5. **Hold the write and watch it for at least several seconds.** A value that
   reads back once and reverts is the F-driver substituting fail-safe values
   (`SPEC.md` §2.1 point 4), and a single read cannot tell that apart from a
   write that stands.

**Record.**

| Item | What the tool printed | Date |
|---|---|---|
| API assembly path and version | `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll`; `SimulationRuntimeManager.Version` printed `458752`. Loaded from Windows PowerShell 5.1 with `Add-Type -Path` — **no new project dependency** | 2026-08-04 |
| Runtime-manager / interface calls actually used | `SimulationRuntimeManager.RegisteredInstanceInfo`, `SimulationRuntimeManager.CreateInterface(name)`, `IInstance.OperatingState`, `IInstance.ReadBool/WriteBool/ReadInt32/ReadFloat` | 2026-08-04 |
| Tag-list update call and its options | `IInstance.UpdateTagList()` with no arguments, called after the step 2 download; `IInstance.TagInfos` enumerated **166** tags | 2026-08-04 |
| **F-DI channel present in the tag list?** | **yes** — `area=Input`, data type `Bool` | 2026-08-04 |
| **Exact tag string, verbatim** | `ProbeFdiCh0` — i.e. the PLC tag-table symbol, unqualified, exactly as typed in the *IO tags* tab | 2026-08-04 |
| F-I/O data block present in the tag list? | **yes**, and every member is reachable: `F00000_F-DI8x24VDCHF_1` plus `.PASS_ON .ACK_NEC .ACK_REI .IPAR_EN .DISABLE .PASS_OUT .QBAD .ACK_REQ .IPAR_OK .DIAG .DISABLED .BASEID_ACTIVE` | 2026-08-04 |
| Write call used, and its return / error | `WriteBool('ProbeFdiCh0', $true)` — **returned without error**, with the CPU in RUN and safety mode activated. No refusal, unlike the watch table's `2206:000002` | 2026-08-04 |
| API read-back value | `True`, on every sample of a 10 s run and of a 60 s run | 2026-08-04 |
| Watch-table in-force value, same moment | **`FALSE`** — read inside the 60 s hold window, screenshot `evidence/m5-03-watch-false-while-api-holds-true.png` | 2026-08-04 |
| `QBAD` / `PASS_OUT` / value status, same moment | `QBAD` = TRUE, `PASS_OUT` = TRUE throughout; value status not applicable on this module | 2026-08-04 |
| Value after holding several seconds | API side held `True` for the full 60 s without reverting; the watch table never left `FALSE` in that window | 2026-08-04 |

**Which abort row this is.** The third and fourth rows of the meaning table
above describe two different failures, and this observation is the **second**:
*the write returns success, the API reads it back, but the watch table shows the
fail-safe value.* The API is writing a process image the safety layer does not
honour — the F-driver substitutes the fail-safe value into the operand the
F-program would read, exactly as `SPEC.md` §2.1 point 4 predicted. The value does
not oscillate or revert; the two views simply never agree, for as long as the
module is passivated, which step 3 established it permanently is on this
installation.

**What the reading means.**

| Reading | Meaning |
|---|---|
| The channel appears by name, the write returns success, and **both** the API read-back **and the watch table** show the written value, **and it holds** | The path exists. This is the reading ADR 0011 D2 is conditioned on. It still does not make the demand real — what an F-program operand does with it is design work for a later brief |
| The write returns success, the **API** reads it back, but the **watch table** shows the fail-safe value | The F-driver is overwriting the channel in the same F-cycle — `SPEC.md` §2.1 point 4, observed. The API is writing a process image the safety layer does not honour. **Abort** |
| The value lands and then **reverts** while held | Same mechanism, seen in time rather than in one sample. **Abort** |
| The channel does **not appear in the tag list** | Question (ii) answered **no** as ADR 0011 D2 words it: the API cannot write the channel values **by tag name**. Do **not** reach for an address-area write — F7 forbids it, and it would put the write on the qualifier bits. **Abort** |
| The write is **refused** because safety mode is activated | Record the refusal verbatim. A path that requires deactivating safety mode is not a path: it would conduct the demonstration in the one CPU state where the safety program's protections are lifted, which `SPEC.md` §7.1 already rules out for the standard-DB stimulus and which is no more acceptable here. **Abort** |

**Abort condition → fallback.** Any row above marked abort. This is **ADR 0011
D2's second named trigger** — question (ii) answering no. Delete the copy and take
the fallback of §6.

---

## 5. Step 5 — does SYNC_PI / SYNC_PO on PIP 1 change the picture?

**The question.** F7 records that deterministic coupling to the F-runtime group
is supported via **PIP 1** with **`SYNC_PI` / `SYNC_PO` registered as pre- and
post-processing of that group**. Two readings are wanted from this step, and they
are different: whether it **rescues** a marginal result from step 4, and whether
it **changes** a good one.

**Run this step only if step 4 produced either a clean yes or a
timing-shaped no** — a value that lands sometimes, or lands and reverts
intermittently. If step 4's no was structural (no tag, refusal under safety mode,
consistent overwrite by the F-driver), **this step cannot rescue it** and the
abort of step 4 stands. Determinism does not create a channel that is not there.

**Do.**

1. Assign the F-DI's I/O addresses to **PIP 1** in the module's properties, in
   place of the automatic process image. Record what the dialog offers and what
   you selected.
2. Register **`SYNC_PI`** as the F-runtime group's **pre-processing** and
   **`SYNC_PO`** as its **post-processing**, in *Safety Administration*'s
   F-runtime-group settings. **Confirm from the dialog which block type it asks
   for and record it**; if it asks for standard blocks, as the pre-/post-
   processing entries are expected to, then nothing here adds a network to
   `F_Forklift_Safety` and nothing here is safety logic (§0.3). Keep each block
   to the single call it needs. **If the tool instead requires an F-block, stop:
   that is a change to the safety program and belongs to a brief, not to a
   probe** — record the requirement and report it.
3. Compile, download, and re-apply §0.2 rules 2 and 4 — **green diff circles**,
   **signature online = offline**, **`_1` sweep**.
4. **Repeat step 4's write-and-read-back three ways**, unchanged, so the two
   observations are comparable. Then **delete the pre- and post-processing probe
   blocks** and record that you deleted them; they are a probe, not a design.

**Record.**

**NOT RUN**, by this section's own gate. Step 4's no was **structural**, not
timing-shaped: the module is passivated with no reintegration reachable, the
watch table never agrees with the API for a single sample, and the divergence is
constant rather than intermittent. This section says in that case the step
"cannot rescue it and the abort of step 4 stands". Determinism does not create a
channel that is not there.

Read for the record while step 5's page was open: the F-runtime group's
**Pre processing** and **Post processing** entries both read `(None)`, so nothing
was registered and nothing had to be deleted.

| Item | Before PIP 1 / SYNC | After PIP 1 / SYNC | Date |
|---|---|---|---|
| Process image assignment of the F-DI | `---` (no process image assigned) | not run | 2026-08-04 |
| Pre-/post-processing blocks registered | `(None)` / `(None)` | not run | 2026-08-04 |
| API read-back | `True` | not run | 2026-08-04 |
| Watch-table in-force value | `FALSE` | not run | 2026-08-04 |
| `QBAD` / `PASS_OUT` / value status | TRUE / TRUE / not applicable | not run | 2026-08-04 |
| Holds under sustained write? | API side yes, watch table never followed | not run | 2026-08-04 |
| Probe blocks deleted | — | none were ever registered | 2026-08-04 |

**What the reading means.**

| Reading | Meaning |
|---|---|
| Step 4 was already a clean yes, and this changes nothing observable | Record it. The coupling is then a **design option for a later brief**, not a condition of feasibility, and this procedure's verdict does not depend on it |
| Step 4 was intermittent, and this makes the write land and hold consistently | The deterministic coupling is **part of the path**, and any later design that omits it inherits the intermittency. Record it as a **required element**, not as a nicety |
| Step 4 was intermittent, and this changes nothing | The path is not reliable by the supported mechanism. **Abort** |
| Registering the blocks breaks the compile, the download or RUN | Record the message verbatim, delete the probe blocks, and re-verify that the step 2 state is restored before drawing any conclusion from step 4 |

**Abort condition → fallback.** Step 4 was marginal and the supported
deterministic coupling does not make it reliable. Delete the copy and take the
fallback of §6.

---

## 6. The fallback, and its consequence — stated once

**The trigger** is any abort above: step 1's version question answering no,
step 2's configuration or download failing, step 3's module staying passivated,
step 4's API not writing the channel by tag name or the write not standing, or
step 5's coupling not rescuing a marginal step 4.

**The fallback is ADR 0011 D2's named one**: the **present standard-DB stand-in**
of `plc/forklift-safety/SPEC.md` §7 — the three Bools of `SafetyInputStandIn`,
driven by *Modify* from the watch table over the engineering connection.

**It is inert by construction.** It is the path the project already runs. Taking
it requires building nothing and removing nothing: delete the probe copy of §0.1,
and the working build is untouched. `SPEC.md` §2.1's ruling stands, its §10 open
item 1 closes as **confirmed by observation** rather than as a design assessment,
and no network, tag, watch-table row or T6 step moves.

**Its consequence, which is not cosmetic.** ADR 0011 **F6**: only fail-safe data
from F-I/O and other safety programs may be processed in a safety program,
because **standard tags are unsafe**; TIA's warning **S015** requires
process-specific validity checks per F-runtime group; and TIA's mechanism is
**disclosure** — the standard tags a safety program reads are listed in the
safety summary — **not protection**. So under the fallback:

1. The stand-in path is **labelled a stand-in wherever it appears**, in every
   document, caption, watch-table screenshot and spoken line. The DB's own name
   already carries the word, which is why it was named that way (`SPEC.md` §7.1).
2. The **S015 validity check is carried visibly in the F-code**, per F-runtime
   group, rather than acknowledged in a compile log and forgotten.
3. Nothing about **D1 reopens**. Which controller the F-program *is* — the
   vehicle's own onboard safety controller — does not depend on how its inputs
   are stimulated. Only the input path is a stand-in.

**And the fallback does not touch the vehicle-side waves.** They were never
conditioned on this verdict (see the header).

---

## 7. Verdict — **for the owner, after running the procedure**

*Filled on 2026-08-04 by the owner, at the tool, from the record tables above.
Every value here is quoted from a Record row of this document; none is inferred.*

| # | Question | Verdict | Evidence (step, record row) | Date |
|---|---|---|---|---|
| Q1 | ADR 0011 D2 question (i) — does this installation's PLCSIM Advanced version and this project's safety system version support F-I/O simulation? | **Undecidable on the document, decided in the observable** — PLCSIM Advanced V7.0 is F4 territory (no verified list) and safety system V2.8 postdates F1's list. Steps 2–4 answered it instead | §1 record table; §1 reading note | 2026-08-04 |
| Q2 | Can an ET 200SP F-DI be configured, compiled, downloaded, with the CPU in RUN and the F-runtime group executing? | **YES** — 0 errors, 2 warnings, green diff circles, F-collective signature `5DC99AD0` online = offline, CPU RUN, safety mode activated | §2 record table | 2026-08-04 |
| Q3 | Does the F-I/O reintegrate without an acknowledgement, and what do QBAD / PASS_OUT / value status actually show? | **NO — the module stays passivated indefinitely.** `PASS_OUT` = `QBAD` = 1 at rest and after STOP→RUN, `ACK_NEC` = 1 with `ACK_REQ` never rising, `DIAG` = `16#00`, and both modules read *"Module exists. OK"* online. Value status is not offered by the module at all. The acknowledgement path is closed from the engineering side: *"Debugging of fail-safe tags is not allowed in permanent safety mode. (2206:000002)"* | §3 record table | 2026-08-04 |
| Q4 | ADR 0011 D2 question (ii) — can the PLCSIM Advanced API write that F-DI's channel values **by tag name**, and does the value stand? | **Split, and the split is the answer.** The channel **is** in the tag list by name (`ProbeFdiCh0`, area Input), `WriteBool` returns without error under activated safety mode, and the API reads `True` back for 60 s. **But the TIA watch table reads `FALSE` in the same window** — the F-driver substitutes the fail-safe value into the operand an F-program would read. This is the *write lands in the API's view only* abort row | §4 record table; `evidence/m5-03-watch-false-while-api-holds-true.png`; `evidence/m5-03-api-tag-write-log.txt` | 2026-08-04 |
| Q5 | Does PIP 1 with SYNC_PI / SYNC_PO change the picture? | **NOT RUN** — step 4's no is structural, not timing-shaped, and §5's own gate forbids running it in that case | §5 | 2026-08-04 |

**Overall verdict** (`ADR 0011 D2 primary path` / `ADR 0011 D2 fallback`):
**`ADR 0011 D2 fallback`** — decided on `2026-08-04` by `Ozkan Ceylan`, at the
tool.

**Consequence recorded here, in one sentence, by the owner:** the scanner's
simulated signal cannot reach the F-program through configured F-I/O on this
installation, so the standard-DB stand-in of `SPEC.md` §7 remains the input path,
`SPEC.md` §10 open item 1 closes as **confirmed by observation**, and §6's three
consequences — the stand-in labelled everywhere, the S015 validity check carried
visibly in the F-code, and D1 untouched — become binding on the m5-15 F-program
spec.

**Two facts this run adds that the procedure did not anticipate**, recorded so a
later reader does not re-derive them:

1. **The passivation is not a startup transient that an acknowledgement would
   clear.** `ACK_REQ` never rose, so there was nothing to acknowledge, while both
   modules reported *"Module exists. OK"* and the diagnostic buffer logged no
   PROFINET, F-I/O or F-runtime-group event at all. The F-driver holds the
   channel fail-safe without ever declaring a fault — which is why the
   `SPEC.md` §2.1 assessment could not have been falsified by reading diagnostics
   alone.
2. **The engineering connection cannot modify fail-safe tags at all** in
   permanent safety mode (`2206:000002`). This closes a path the procedure left
   open in step 3 — "record it as a finding" — and it applies to any future
   design that hoped to stimulate F-data by *Modify*, not only to this probe.

**Housekeeping still owed** (§0.1 rule 3): the probe copy `safe_amr_FIOPROBE` was
closed but **not yet deleted** at the end of the 2026-08-04 session. The working
project `safe_amr` was never modified by this procedure.

**What follows from a yes** (stated so the verdict does not have to invent it):
`SPEC.md` §7 is the only section that changes, three pins move at `SPEC.md` §4.2
step 8, and the AT-07 and AT-01 (c) consequences of `SPEC.md` §2.1 are re-read at
the same time — **each of those is its own brief, not a keystroke made while the
verdict is being written.**

**What follows from a no:** §6 above, unchanged, and `SPEC.md` §10 open item 1
closes as confirmed by observation.
