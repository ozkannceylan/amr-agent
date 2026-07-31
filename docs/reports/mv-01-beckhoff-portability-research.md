# Report mv-01 — Beckhoff/TwinCAT portability: research and architecture design

```
brief:               docs/briefs/mv-01-beckhoff-portability-research.md
status:              done
files_changed:       [docs/reports/mv-01-beckhoff-portability-research.md]
invariants_touched:  none changed. One new ADR is REQUIRED before implementation
                     (§F.7): it records tool-derived TwinCAT contract constraints
                     (the ADR 0006 analogue) and the startup controller-selection
                     ruling. No invariant needs to change (§F.6).
open_questions:      the owner decisions in §G — gate placement, directory
                     variant, mirror scope, endpoint-liveness guard
next_suggested:      issue the §F.5 stage-0 probe brief (owner tool session)
                     before any other Beckhoff work; every browse path and URI
                     in this report is a design value until that probe runs
```

Two owner scope corrections landed during this research and are incorporated
throughout: **(1)** the two controllers never run at the same time — the system
must be *capable* of either, one active per session; **(2)** the controller is
selected **at system startup and does not change while the system runs** — no
hot switch, ever. §F.3 designs the startup selection; the mid-run switch is
recorded as out of scope in one paragraph there and analysed nowhere.

Verification dates: all external sources were checked **2026-07-31** unless
stated. Two verification grades are used, per this project's standing rule that
a figure appearing in no tool output does not enter a document:

- **[fetched]** — the page was retrieved and the statement quoted from it.
- **[snippet]** — the statement comes from a search-result excerpt of the named
  page and was not re-read in full context. Snippet-grade claims are restated
  in §A/§C as items the stage-0 probe re-verifies in the installed tool.

---

## Verdict on the thesis, first

**The brief's framing is confirmed, and the research strengthens it.**

"Identical tags and addresses on both PLCs" is false in its literal form — and
not merely because the addressing models differ, but because **neither
implementation uses addresses at all**. The Siemens build uses optimized DBs
(no absolute offsets; `plc/demo-cell/SPEC.md` §4.2) with a server interface
mapping symbols to nodes; the TwinCAT build would use GVL symbols exposed over
ADS to the TwinCAT OPC UA Server. There is no address on either side for a
diff to compare.

The honest claim is the brief's stronger one, sharpened by the owner's
corrections:

> The **contract** is identical below the interface node — the same relative
> browse paths, the same BrowseNames, the same data types, the same access
> rights, the same start values, the same handshake and watchdog semantics —
> and portability is **demonstrated**, not asserted: the same byte-identical
> bridge and HMI, with nothing changed but a configuration file pair selected
> at startup, run the same scenario procedures against the Siemens controller
> in one session and the Beckhoff controller in another, and both evidence
> sets are kept.

What can **not** be identical, exactly (details §C, §D):

1. **The two namespace URIs.** Siemens derives `http://<interface name>` and a
   Siemens-owned folder namespace (ADR 0006). TwinCAT derives its PLC
   namespace URI from the host name and the data-access device name
   (`urn:<Hostname>:BeckhoffAutomation:Ua:PLC1` form — [snippet], §C.2). Both
   are tool-derived; neither can be made to equal the other.
2. **The browse path from `Objects` down to the interface node.** Siemens:
   `Objects/ServerInterfaces/DemoCell`. TwinCAT: `Objects/<device node>/…`
   with no `ServerInterfaces` folder. The parent path is vendor topology.
3. **The safety layer.** It cannot be mirrored without hardware today (§B).
   The Siemens side has vendor-documented F-simulation (verdict still pending
   in `plc/forklift-safety/FIO-FEASIBILITY.md`); the Beckhoff side has no
   generally released software-only TwinSAFE runtime — TE9100 is announced,
   not shipped. The honest scope is **standard-program-only portability**,
   with the safety layer named Siemens-only and the `Forklift/Safety/` mirror
   group absent on the Beckhoff server (which the HMI already tolerates by
   design, `hmi/config.yaml` `OPTIONAL_READ_FOLDERS`).

Both vendor-specific residues in items 1–2 are **already configuration, not
code**, in both clients: `bridge/config/bridge.yaml` and `hmi/config.yaml`
carry the endpoint, both namespace URIs and the `interface_path` element list
as data. That is why the client stack can be byte-identical across vendors
(§F.3).

---

## A. TwinCAT 3 without Beckhoff hardware

### A.1 Can a full TwinCAT 3 PLC project run on an ordinary Windows PC?

**Yes, with one load-bearing qualification about which runtime form.**

TwinCAT 3 splits into XAE (engineering, a Visual Studio-shell IDE) and XAR
(runtime). Both install on an ordinary PC; the local runtime is the normal
development target and needs no Beckhoff hardware and no EtherCAT device.
There are, as of TwinCAT 3.1 Build 4026, **two runtime forms**, selected at
installation as `XarMode` [snippet, infosys "Runtime Configuration",
https://infosys.beckhoff.com/content/1033/tc3_installation/20830884491.html]:

| XarMode | What it is | Real time | Relevance here |
|---|---|---|---|
| `KM` | classic kernel-mode real-time runtime | yes | **will not start on the owner's machine** (§A.3) |
| `UM` | user-mode runtime, from Build 4026.21, offered "as a replacement for the real time Runtime, because more and more XAE installations on Windows do not meet the Hyper-V requirements due to IT security requirements" [snippet, same page] | **no** — minimum cycle 1 ms [snippet, same page] | **the path for this project** |
| `KMWithUM` | both installed | — | possible, KM stays unusable while Hyper-V is on |

The user-mode runtime executes "the same program code of the customer project
… but without meeting the real-time requirements" [fetched, infosys usermode
runtime overview,
https://infosys.beckhoff.com/content/1033/tc170x_tc3_usermode_runtime/11319881355.html].
A 1 ms minimum cycle is far inside this project's needs: the ported program
runs at a 20 ms task cycle mirroring OB30, and the HMI/bridge cadences are
100 ms / 50 ms.

**What happens to I/O with no terminals behind it: nothing, because this
project's PLC programs have none.** This is the decisive simplification and it
is inherited from the Siemens design, not invented here: every contracted
value is a **DB tag written or read over OPC UA** — the bridge writes the
input image into `Input/` nodes, the PLC forms outputs in `Output/` nodes
(`opcua-nodes.md` §9.1). No `%I`, `%Q` or process image is used on the Siemens
side, and the TwinCAT mirror uses no `AT %I*` variable and configures **no
fieldbus, no EtherCAT master and no simulated device**. The whole
"Simulation Manager / simulated I/O / free-running with unmapped variables"
question of the brief is therefore moot for this project: there is nothing to
map. (Beckhoff's TE1111 EtherCAT Simulation exists for projects that do need
simulated EtherCAT devices; it is not needed here and is deliberately not
proposed.) The residual claim — "a PLC project with zero I/O devices runs in
the user-mode runtime and serves symbols over ADS" — is the expected default
behaviour and is **settled by the stage-0 probe's first build**, not asserted
as fact before then.

### A.2 Concrete steps (what a person would do)

Design values until executed; the stage-0 probe brief (§F.5) turns them into
a record with dates, per the FIO-FEASIBILITY pattern.

1. Install TwinCAT 3.1 Build **4026** via the TwinCAT Package Manager:
   workload XAE plus runtime with `XarMode = UM` (or `KMWithUM`). Record the
   exact build number the installer reports.
2. Install the **TwinCAT OPC UA Server** (TF6100 family; in 4026 it is a
   package, historically also shipped as the standalone TS6100/TcOpcUaServer).
   Record the package name and version actually installed.
3. In XAE: new PLC project; create the GVLs and FB mirroring
   `docs/interfaces/opcua-nodes.md` (§C.4 naming candidates); enable symbol
   exposure per tag with `{attribute 'OPC.UA.DA' := '1'}` and read-only tags
   with the access pragma (§C.3); set the task cycle to 20 ms; activate the
   configuration onto the local user-mode runtime.
4. When prompted for licences, generate **7-day trial licences** in XAE for
   the runtime functions the activation demands (expected: TC1200 "TC3 PLC"
   and the TF6100 OPC UA Server licence; the tool's own demand list is the
   authority — record what it actually asks for).
5. Browse the server with a client that is **not** the bridge (UaExpert or the
   project's `asyncua` probe), read the NamespaceArray and every contracted
   node at its start value, and record strings verbatim — the phase-0
   analogue of `opcua-nodes.md` §9.10.

### A.3 Licensing, precisely, as the vendor states it

All from Beckhoff Information System / beckhoff.com, 2026-07-31:

- "TwinCAT 3 test licenses can be activated as often as required in the
  TwinCAT 3 development environment (XAE) for a period of 7 days." …
  "An internet connection is not required." [fetched,
  https://infosys.beckhoff.com/content/1033/tc3_licensing/921947147.html]
- Trial licenses **cannot** be generated on a runtime-only (XAR) system and
  cannot be created for TwinCAT 3 license dongles — only for the local target
  (IPC or engineering computer) from within XAE. [fetched, same page]
- "The licenses marked in the Manage Licenses tab are activated as trial
  licenses for 7 days." [fetched,
  https://infosys.beckhoff.com/content/1033/tc3_licensing/3510308491.html]
- "The 7-day trial license for TwinCAT 3 products, which can be renewed over
  and over again, enables TwinCAT functionalities to be used in a
  straightforward and cost-effective manner in the lab." [snippet,
  https://www.beckhoff.com/en-us/products/automation/twincat/twincat-3-licensing/]
- The user-mode runtime's **engineering mode (TC1700) is "free of license
  costs"**; TC1701/TC1702 are its licensed production modes. [fetched,
  https://infosys.beckhoff.com/content/1033/tc170x_tc3_usermode_runtime/11319881355.html]
- The OPC UA Server is a separately licensed function (TF6100,
  https://www.beckhoff.com/en-us/products/automation/twincat/tfxxxx-twincat-3-functions/tf6xxx-connectivity/tf6100.html);
  it participates in the trial mechanism above like other TF functions.
  Which licence IDs the activation actually demands on the installed build is
  recorded at stage 0, not assumed here.

**What may honestly be claimed in a public portfolio:** the project runs on
renewable 7-day trial licences generated in XAE, which the vendor's own
licensing pages describe as the intended lab/testing mechanism, renewable "as
often as required". **What must not be claimed:** that TwinCAT or TF6100 is
"free". The engineering-mode user-mode runtime is stated free of licence
costs; the PLC and OPC UA runtime functions are commercial products used here
under trial terms. No sentence restricting trial licences to non-commercial
use was found on the cited pages — and the README wording should say "used
under Beckhoff's 7-day renewable trial licensing" rather than asserting the
absence of any restriction. (The full licence text shipped with the installer
is the authority; stage 0 records where it lives.)

### A.4 Platform: one Windows machine, TIA Portal, PLCSIM Advanced, WSL2

Downgraded to a **workflow finding** per the owner's first correction (the
controllers never run concurrently), but the facts still shape the workflow:

- **The owner's machine already runs a hypervisor, permanently.** The Gazebo
  side of every M3/M4 run lives in WSL2 (report m3-07, LESSONS 2026-07-27),
  and WSL2 runs on the Windows hypervisor platform. PLCSIM Advanced V7 with
  its virtual adapter demonstrably coexists with that arrangement — the
  entire M3/M4 evidence base was produced on it (`opcua-nodes.md` §9.10).
- **The TwinCAT kernel-mode real-time runtime will not start there.**
  Beckhoff: "The real-time runtime environment cannot be started within a
  Hyper-V environment. … As soon as a component of the computer uses Hyper-V,
  only the engineering environment (XAE) can be used on this computer, but
  not the real-time runtime environment." Device Guard, Credential Guard and
  Virtualization-based Security are named as activators. [fetched, infosys
  System requirements,
  https://infosys.beckhoff.com/content/1033/tc3_overview/6162419083.html]
- **The user-mode runtime exists precisely for this situation** (from Build
  4026.21, §A.1), so no boot-time or install-time choice is forced: TIA
  Portal + PLCSIM Advanced + WSL2 + XAE + user-mode XAR can be installed
  side by side, and sessions select a controller without rebooting.
  *Install-level* co-residency (two large toolchains, no shared driver, no
  NIC binding needed since the user-mode runtime and a local OPC UA server
  need no RT-Ethernet driver) has no documented conflict, but it is
  **unverified** — settled the day both are installed, at stage 0.
- **If the owner ever wants kernel real time** (not needed for any current
  gate criterion): dual boot with Hyper-V/WSL2 disabled in that boot entry, a
  second machine, or a Beckhoff C60xx-class IPC / TwinCAT/BSD box are the
  options. A VM cannot provide it — the same vendor page rules the RT runtime
  out inside Hyper-V. None of these is proposed for the simulation-only
  gates.

**Honest consequence for evidence:** latency and timing figures measured
against the TwinCAT user-mode runtime are figures about a non-real-time
execution environment on Windows, exactly as the PLCSIM Advanced figures are
figures about a soft PLC. The project already qualifies every measurement by
the environment that produced it (LESSONS 2026-07-27); the TwinCAT evidence
files inherit that rule and additionally state "user-mode runtime, no real
time" in their environment records.

---

## B. The safety layer

### B.1 The Beckhoff safety architecture, briefly

The Siemens stack under mirror is: F-CPU, F-runtime group, F-FBD networks,
F-I/O over PROFIsafe (`plc/forklift-safety/SPEC.md`). The Beckhoff
equivalents:

- **TwinSAFE logic runs in dedicated safety hardware**, not in the Windows
  runtime: TwinSAFE Logic terminals (EL6910 family, EK1960, …) programmed
  from the **TwinCAT 3 Safety Editor (TE9000)** inside XAE
  [https://www.beckhoff.com/en-us/products/automation/twinsafe/twinsafe-software/te9000.html].
- The safety fieldbus is **FSoE (Safety over EtherCAT)** between safety I/O
  and the logic terminal — the PROFIsafe analogue — which presupposes an
  EtherCAT segment with physical safety terminals.
- Coupling to the standard PLC is via mapped (non-safe) data, the analogue of
  the standard program reading F-DB flags.

### B.2 Can any of it run without hardware? — the finding

**No released software-only TwinSAFE runtime was found.**

- Beckhoff's TwinSAFE software page describes "an extension for the TwinCAT 3
  EtherCAT simulation environment [that] facilitates testing of safety
  applications without using actual hardware or with only limited use of
  hardware" [fetched,
  https://www.beckhoff.com/en-us/products/automation/twinsafe/twinsafe-software/].
- That extension is **TE9100 "TwinSAFE Logic Simulator"**, which extends
  TE1111 (TwinCAT 3 EtherCAT Simulation) "via aspects of safety technology"
  so that "safety applications based on the TwinCAT 3 Safety Editor [can be
  commissioned] without the presence of real hardware". Its product page
  states, verified 2026-07-31: **"product announcement | estimated market
  release on request."** [fetched,
  https://www.beckhoff.com/en-us/products/automation/twinsafe/twinsafe-software/te9100.html]

A product at announcement status is not a plannable basis for a gate. Until
TE9100 ships (and its licence and capability are read from its own
documentation, not inferred), the honest statement is:

> **The safety layer cannot be mirrored on Beckhoff without hardware.** The
> Siemens side has vendor-documented F-simulation in PLCSIM Advanced —
> version-gated, with this project's own feasibility verdict still blank
> (`FIO-FEASIBILITY.md` §7) — and has already executed an F-runtime group in
> simulation (ADR 0009 context, 2026-07-29). The Beckhoff side today has an
> editor and an announced simulator, and no released execution path.

The brief's caution was warranted: the Beckhoff side is not easier; it is
currently harder than the still-unresolved Siemens case.

### B.3 The scoped alternative, as the brief asks

**Standard-program-only portability, with the safety layer named
Siemens-only.** Concretely:

1. The TwinCAT mirror implements `plc/forklift/SPEC.md` (and optionally
   `plc/demo-cell/SPEC.md`) — the standard program, all process interlocks,
   both watchdogs, the monitored reset. Nothing of
   `plc/forklift-safety/SPEC.md` is implemented.
2. There is **no** honest TwinCAT equivalent of `forklift-safety/SPEC.md` to
   write today. What can honestly exist is a **one-page mapping note** inside
   the TwinCAT layer's README: which SRS functions the Siemens F-program
   carries, what their TwinSAFE realisation would be (EL6910-class logic,
   FSoE I/O, Safety Editor project), and why it is not built (TE9100
   unreleased; no hardware; no claim). Not a SPEC — a spec for an
   unbuildable layer would be exactly the "design value authored without the
   tool" this project has already paid for.
3. The four `Forklift/Safety/` mirror nodes (`opcua-nodes.md` §11) are
   **absent** from the Beckhoff server. This is already a tolerated server
   state: the HMI declares the group optional and "greys the group rather
   than guessing a value" (`hmi/README.md`, `hmi/config.yaml`). No client
   change is needed; the §13 safety-coupling delta of `plc/forklift/SPEC.md`
   is simply not applied in the TwinCAT program (its own §13.7 fallback
   wording — omit part 0 and the `#safetyDemandClear` conjunct — is the exact
   recipe, already written).
4. Every showcase, README and evidence file states the asymmetry: *"the
   F-safety layer exists on the Siemens controller only; the Beckhoff mirror
   is the standard program."* If TE9100 ships, re-opening the question is its
   own brief with its own feasibility probe, TE9100's documentation quoted —
   the FIO-FEASIBILITY pattern on the other vendor.

---

## C. The OPC UA server and the contract

### C.1 How the TwinCAT OPC UA Server builds its address space

Mechanism, from the TF6100 documentation [fetched,
https://infosys.beckhoff.com/content/1033/tf6100_tc3_opcua_server/15620470667.html
and the TF6100 manual/quick-start pages]:

- The server is a **separate process** (TcOpcUaServer) beside the runtime; it
  reads the PLC's **symbol file (TMC)** and talks **ADS** to the runtime. "The
  OPC UA Server automatically imports the first PLC runtime into its
  namespace"; that runtime appears as a **data-access device**, by default
  named **`PLC1`**, as a node under `Objects` [snippet, TF6100 docs/manual].
  Additional ADS devices are configured with Name, AmsNetId, AdsPort and
  SymbolFile [snippet, TF6100 configurator docs].
- **Exposure is opt-in per symbol**: `{attribute 'OPC.UA.DA' := '1'}` on a
  variable, array or struct publishes it; "the pragma for enabling a symbol
  is automatically inherited to all child symbols" [fetched, PLC page above].
  Further pragmas set **access control and read-only flags** per symbol
  [fetched, same page] — the enforcement analogue of TIA's per-tag *Writable
  from HMI/OPC UA* column (`opcua-nodes.md` §10.3).
- BrowseNames follow the PLC symbol names; a struct instance browses as a
  node with its members as children. (Exact BrowseName strings — member name
  vs qualified name — are a stage-0 read-back item, §C.4.)

A welcome asymmetry: because exposure is pragma-opt-in, the Beckhoff server
has **no analogue of the S7-1500's auto-published `DataBlocksGlobal` second
path** (`opcua-nodes.md` §9.8's open hardening item). The contracted nodes
can be the only published symbols. To be confirmed at the stage-0 browse, not
assumed — the server ships with default namespaces (Server diagnostics etc.)
that the probe should inventory.

### C.2 The namespace URI — the ADR 0006 analogue

ADR 0006's Siemens finding: the URI is derived (`http://<interface name>`),
not editable, one namespace per interface. The Beckhoff constraints found:

- The PLC device namespace URI is **tool-derived** and — in the documented
  examples — **embeds the host name**: the TF6100 manual shows
  `urn://SVENG-NB04/BeckhoffAutomation/Ua/PLC1` ("the OPC UA Server ensures
  that the URI always remains the same, even after a restart") and
  configuration references show the form
  `urn:<Hostname>:BeckhoffAutomation:Ua:PLC1` with an `<AllowRenameUri>`
  server-configuration parameter (default `false`) and a `<ComAlias>` prefix
  setting. [snippet — TF6100 manual mirrors and configuration references;
  current manual: TF6100_TC3_OPC_UA_Server_EN v1.4.0, 2025-09-16,
  https://download.beckhoff.com/download/document/automation/twincat3/TF6100_TC3_OPC_UA_Server_EN.pdf]

Consequences, stated now so they cannot surprise later:

1. **A host-name-coupled URI is a stronger version of ADR 0006's lesson**: on
   Siemens, renaming the *interface* breaks every browse; on Beckhoff (if the
   documented form holds on the installed version), **renaming the Windows
   computer** may change the namespace URI and break every browse. The
   machine name becomes contract the way the interface name did. This goes in
   the vendor ADR verbatim once read back from the tool.
2. **Whether the URI can be pinned to a chosen string** (`AllowRenameUri`,
   device rename, `ComAlias`) on the currently shipping server is
   **unverified**. What settles it: stage 0 reads the `NamespaceArray` from
   the installed server and, if a rename knob exists, records whether the
   renamed URI survives restart and re-activation. Until then the design
   assumes the *worst documented case* — a derived, host-coupled URI — which
   the client stack already absorbs (URIs are config values, resolved by
   browse at session establishment, never hardcoded; ADR 0006 D4's mechanism
   is vendor-neutral and stands).

### C.3 The decisive question: same browse paths and BrowseNames?

**Below the interface node: yes, by construction. Above it: no, and the
contract already absorbs the difference.**

- **Identical (contract):** the relative paths and BrowseNames of every
  contracted node — `Input/ConveyorBeltPosition`,
  `Forklift/Hmi/HmiTractionRequest`, all 15 §9 + 18 §10 names — the data
  types, the access rights (client view), the start values, the handshake and
  watchdog semantics. TwinCAT symbol naming (PascalCase GVL/struct members)
  reproduces the BrowseNames exactly; nothing in the naming convention of
  CLAUDE.md §9 is Siemens-specific.
- **Vendor-specific (config, per client, already so today):**
  - the endpoint URL;
  - the **path from `Objects` to the interface node** — Siemens
    `ServerInterfaces` (in `http://www.siemens.com/simatic-s7-opcua`) then
    `DemoCell`; TwinCAT the data-access device node (default `PLC1`, name
    configurable) with **no** `ServerInterfaces` analogue;
  - the **two namespace URI values** for those path elements.

  Both clients hold exactly these as data: `namespace_uris` (two keys) and
  `interface_path` (a list of `namespace-key: BrowseName` elements) in
  `bridge/config/bridge.yaml` and `hmi/config.yaml`. The list length is not
  fixed in the config format, so a shallower or deeper TwinCAT path is a
  config edit. Residual code-level checks to verify at implementation: the
  loaders' namespace-key sets are the fixed pair
  `server_interfaces`/`interface` (`bridge/amr_bridge/config.py`
  `NAMESPACE_KEYS`) — semantically Siemens-flavoured names, functionally
  arbitrary labels. If the TwinCAT path needs only one namespace, the config
  can carry the same URI under both keys or the loader gains a one-line
  generalisation; either way it is not vendor *logic* (§F.3).
- **Where exact matching is impossible**, the quirk stays out of the client
  by the same rule ADR 0006 D4 set: clients browse by URI and by configured
  path, never by index and never by assumption. No vendor string appears in
  client code.

### C.4 Two candidate symbol layouts, and the probe that picks one

Both reproduce the contracted names below the interface node; they differ in
what the interface node *is*. The stage-0 probe builds both in a throwaway
project, browses, and records which yields the cleaner tree:

| Candidate | PLC-side construction | Expected browse path |
|---|---|---|
| **m1 — device-as-interface** | data-access device renamed `DemoCell`; GVLs named `Input`, `Output`, `Status`, `Link`, `Forklift` (the last holding struct instances `Hmi`, `Input`, `Output`, `Status`, `Link`) | `Objects/DemoCell/Input/ConveyorBeltPosition` |
| **m2 — GVL-as-interface** | device stays `PLC1`; one GVL `DemoCell` containing struct instances `Input`, `Output`, … | `Objects/PLC1/DemoCell/Input/ConveyorBeltPosition` |

Open items the probe settles (all tool-derived identifiers, ADR 0006
discipline): the exact BrowseName strings of struct-member nodes; whether the
device node can be renamed and what that does to the namespace URI; whether
GVL names appear as their own nodes; the OPC UA types the server reports for
`BOOL/INT/UINT/REAL/STRING(16)` (expected `Boolean/Int16/UInt16/Float/String`,
matching the contract's OPC UA column — expected, not asserted); and whether
the server's write handling accepts the clients' `ua.DataValue` write form
(the m4f-07c shape, which is generic OPC UA and *should* be
vendor-indifferent — verified only by running the conformance harness).

---

## D. Addressing and symbols, compared honestly

| Aspect | Siemens S7-1500 (as built here) | TwinCAT 3 (as proposed) |
|---|---|---|
| Data home | Global DBs, **optimized access** — no absolute offsets exist (`plc/demo-cell/SPEC.md` §4.2) | GVL variables / struct instances — symbolic, ADS-addressed by name |
| Process image | Unused: no `%I`/`%Q` in any contracted program | Unused: no `AT %I*`, no fieldbus configured |
| Server mapping | TIA server interface: DB tags dragged into folders; BrowseName = tag name | Pragma-exposed symbols; BrowseName = symbol name |
| Second exposure path | `DataBlocksGlobal` auto-published (open hardening item §9.8) | none expected — exposure is opt-in (§C.1, verify) |
| Namespace | `http://<interface name>`, derived, not editable (ADR 0006) | `urn:<Hostname>:…:<device name>` form, derived; configurability unverified (§C.2) |
| Access rights | per-tag *Writable from HMI/OPC UA* checkbox | per-symbol access pragma |
| "Address" | none | none |

**What a reader should understand by "the same addresses on both": nothing —
the sentence has no referent.** The strongest true statement is:

> One document, `docs/interfaces/opcua-nodes.md`, owns every name, type,
> access right, start value and meaning. Both controllers realise that
> document symbol-for-symbol below their interface node, each through its own
> vendor mechanism, and the same client stack proves the two realisations
> equivalent by browsing, reading, writing and running the same scenarios
> against each.

## E. Language portability — the corpus, measured

Corpus: `plc/forklift/SPEC.md` §7 (the authoritative fence: 131 statement
lines as built 2026-07-30, per its own count note) and `plc/demo-cell/SPEC.md`
§7 (same idiom). The corpus is SCL in a deliberately portable subset: no
`GRAPH`, no `CASE` in the forklift FB (the demo cell has a `CASE` step
machine), no RS/SR *blocks* (all latches are IF-set booleans), no indirect
addressing, no vendor library calls except as noted.

**Ports unchanged (semantics identical, IEC 61131-3 ST):**
`IF/ELSIF/ELSE/END_IF`, `CASE`, boolean/comparison expressions, `:=`,
`AND/OR/NOT`, `ABS`, the entire latch/edge/permissive structure, TON
semantics (`IN`, `PT`, `Q`) including the release-outside-the-branch and
never-read-ET-on-falling-edge lessons — those are IEC timer semantics, not
Siemens ones, and every LESSONS rule about them transfers verbatim.

**Mechanical, token-level edits (systematic, scriptable, no redesign):**

| Siemens form | TwinCAT form |
|---|---|
| `"ForkliftHmi".HmiTractionRequest` (quoted DB access) | `ForkliftHmi.HmiTractionRequest` (GVL access — quotes are TIA syntax) |
| `#localVar` | `localVar` (`#` is TIA notation) |
| `IEC_TIMER` / `TON_TIME` static instance | `TON` instance (Tc2_Standard) |
| `Bool, Int, UInt, Real, String[16]` | `BOOL, INT, UINT, REAL, STRING(16)` |
| FB constant block | `VAR CONSTANT` section |
| Temp identifiers | `VAR_TEMP` section |
| `LIMIT(MN := …, IN := …, MX := …)` | `LIMIT(min, in, max)` positional (IEC operator; named actuals are not portable) |
| OB30, 20 ms cyclic interrupt | PLC task, 20 ms cycle, calling `MAIN` → the FB instance |
| DB start values | initial values in GVL declarations (`:= TRUE` for `ForkliftObstacleInStopZone`, per §10.9) |

**No equivalent / genuinely different:**

- `IS_VALID` (S7-1500 SCL) does not exist in TwinCAT ST. **No impact**: both
  specs already rule it redundant because every plausibility test is the
  affirmative two-comparison AND, with NaN falling to the fault branch on
  IEEE semantics alone (`forklift/SPEC.md` §6.2; LESSONS 2026-07-27). The
  comment lines that mention it are edited, no logic moves.
- **Retentivity model**: S7 per-tag retain vs TwinCAT `VAR RETAIN`/
  `PERSISTENT` (needing NOVRAM or persistent-data handling). **No impact on
  the corpus** — every static is deliberately non-retain with an explicit
  start value — but the domain rule "never use an edge to represent state
  that must survive a restart" is what made that true, and the TwinCAT SPEC
  restates it so nobody adds a retained latch on the new platform.
- **Download/initialisation semantics differ**: TIA's
  download-without-reinitialisation preserving stale in-force values (LESSONS
  2026-07-28, the `T#1M_40S` incident) maps to TwinCAT's online-change
  (values kept) vs full download / cold reset (initial values applied). The
  discipline transfers — read in-force values online, never trust declared
  defaults — the click-paths do not, and the TwinCAT SPEC's commissioning
  section is authored fresh (§F.5 stage 2).
- **The RS/SR behaviour the brief names**: relied on only by the *safety*
  spec's F-FBD networks, which are not ported (§B). Out of corpus.

**Quantified, honestly:** by construct classes, every one of the 131
statement lines of the forklift fence falls in the first two categories —
none requires redesign; the edits are renames, declaration-section moves and
one call-style change. Stated as an assessment of the fence as written, not a
compiler-verified figure: no TwinCAT compiler has run on it, and the number
that matters — the translated FB compiles and its double-checked behaviour
matches `plc/forklift/double/` — is produced at stage 2, where the existing
executable logic-double procedure (LESSONS 2026-07-29: build the double
before the owner types anything into the tool) is reused as the acceptance
instrument for the *translation*: same stimuli, same expected transitions,
two implementations.

What does **not** port and is re-authored per vendor, deliberately: the TIA
click paths, the watch tables (→ TwinCAT online view/watch), the
PLCSIM-specific procedures, and every tool-derived identifier.

---

## F. The architecture proposal

### F.1 Directory shape

Proposed (additive; the alternative and its cost are in §G item 2):

```
plc/
  README.md                  gains a vendor table: which subtree is which
                             vendor, and the Siemens-only status of safety
  demo-cell/                 Siemens/TIA implementation (unchanged, as built)
  forklift/                  Siemens/TIA implementation (unchanged, as built)
  forklift-safety/           Siemens/TIA F-program — SIEMENS-ONLY (§B)
  twincat/
    README.md                opens with "This layer must not access", per
                             CLAUDE.md §4; states: no safety claim, no
                             fieldbus, mirrors the node model only
    forklift/
      SPEC.md                the ST mirror of plc/forklift/SPEC.md: GVL
                             tables, FB, task, pragmas, XAE click path,
                             T5-equivalent procedure
      double/                reuses plc/forklift/double/ stimuli against the
                             translated logic (the translation instrument)
    demo-cell/               only if the owner scopes the M3 cell in (§G)
```

`plc/twincat/README.md`'s forbidden list = the existing `plc/README.md` list
plus two vendor items: no TwinSAFE/FSoE claim (nothing safety-rated exists on
this side), and no fieldbus/EtherCAT configuration (the plant reaches this
PLC only as OPC UA writes from the bridge, invariant 11 unchanged). The
existing three Siemens directories are not renamed: a `git mv` would sweep
hundreds of cross-references through evidence files whose paths are quoted in
committed records, for a purely cosmetic symmetry (LESSONS 2026-07-29 on
sweep costs). Instead `plc/README.md` states plainly that the three existing
subtrees are the Siemens implementation.

### F.2 Single source of truth, and the drift check (invariant 10)

**Owner of every tag's name, type, access, start value and meaning:
`docs/interfaces/opcua-nodes.md`, unchanged.** Both vendor SPECs are derived
documents that cite it; neither may introduce, rename or retype a node. The
two implementations are kept from drifting from it — and from each other — by
a **mechanism, not an intention**, in two layers:

1. **Live conformance, the strong check.** The existing connect-conformance
   instrument (`bridge/tools/check_connect_conformance.py`, evidence
   `connect-conformance-*.csv`) already proves, against a running server:
   namespace resolution by URI, the browse path, node resolution, and type
   verification for the configured set. **The same unmodified tool, pointed
   at the TwinCAT server by its config file, is the drift check**: run
   against both servers, two CSVs, any node missing, mistyped, misnamed or
   wrongly writable fails the run. It runs in this repository today (asyncua
   + config; the TwinCAT endpoint is reachable from WSL exactly as PLCSIM's
   is). Extend it in one place: also assert *rejected* writes on read-only
   nodes, which turns the access-rights column into checked behaviour on
   both vendors.
2. **Document-level, the cheap check.** A small repo tool parses the
   markdown tag tables of `opcua-nodes.md` and of each vendor SPEC and diffs
   name/type/access/start-value columns. Pure text, runs anywhere, catches
   drift at review time before any server exists. (The project already
   parses its own specs for the logic double; this is the same move on
   tables.)

Neither check invents a second owner: both read the node model as the
reference and fail toward it.

### F.3 What the clients must not learn — and the startup selection

**Vendor knowledge in client code: none, and none is needed.** The research
found no point at which the bridge or HMI must branch on vendor: browse paths,
URIs and endpoints are already configuration (§C.3); the write form
(`ua.DataValue`) is generic OPC UA; session-parameter handling already treats
every requested value as a request and times against the grant
(`opcua-nodes.md` §2), which absorbs whatever the TwinCAT server revises.
**The single unavoidable configuration surface is one config file pair per
vendor**: `bridge/config/bridge.<controller>.yaml` and
`hmi/config.<controller>.yaml`, differing only in endpoint, the two namespace
URI values and the `interface_path` elements. Justified: every one of those is
an address, which is exactly the class of value the config files were built to
hold ("an address, a cadence, housekeeping" — their own header rule). One
candidate cosmetic code touch, flagged not required: the loader's fixed
namespace-key labels (`server_interfaces`) read Siemens-specific; renaming the
*labels* is optional and touches no behaviour.

**Startup selection (owner ruling: chosen at startup, immutable for the
session).**

- **The selection datum and its single owner.** The selection is the
  `--controller <siemens|twincat>` argument of `stack.sh start` — one datum,
  owned by the **launcher invocation**, written by the operator, consumed by
  nobody else at run time. `stack.sh` resolves it to the config file pair,
  passes each client its file exactly as it does today, refuses any other
  value, and prints the selection in its start banner and status output. No
  new data path exists: the bridge and the HMI still learn nothing but the
  contents of their own config file, and no process reads another's choice.
- **Which controller actually runs** stays what it is today: row 1 of the
  stack — PLCSIM Advanced or the TwinCAT runtime on Windows — is started by
  the owner before `stack.sh start`, and the selection argument must match
  what the owner started. The launcher can and should check it cheaply:
  before starting clients, probe the *selected* endpoint for TCP reachability
  (fail fast with a named error instead of a reconnect loop), and — offered
  as an option for the owner to accept or decline (§G item 4) — probe the
  *other* vendor's endpoint too and **refuse to start if both answer**,
  since one-controller-at-a-time is now a ruled property of the system.
- **Mismatch by manual start** (a bridge pointed at one vendor, an HMI at
  another, bypassing the launcher): with one controller running this is not
  dangerous — the mismatched client finds no server and sits visibly in its
  reconnect loop — but it must be *diagnosable*. Each client already logs its
  endpoint at connect; add one read: the server's standard
  `Server/ServerStatus/BuildInfo` (`ManufacturerName`, `ProductName` — ns=0,
  standard nodes, no vendor knowledge required to read them), logged at every
  session establishment. The run's evidence then records which vendor served
  it, from the server's own mouth.
- **The HMI shows which controller is active, unmistakably, all session.** A
  persistent banner on the operator page: the `ManufacturerName` /
  `ProductName` read from `BuildInfo` at connect, plus the endpoint — i.e.
  the *server-reported* identity, never a config label. Ownership is clean
  under invariant 10: the identity is the server's datum; the HMI displays
  it and configures nothing. The banner is part of every screenshot and
  showcase recording, so a viewer of the Siemens session and the Beckhoff
  session can tell them apart at a glance. (`config-*` doubles display
  whatever the double reports, keeping the rule "every recorded number states
  which server produced it".)
- **Mid-run switching is out of scope by owner ruling** (2026-07-31), and the
  ruling is the sound reading: a controller switch would be a controller
  restart, the newly selected controller starts from its own state — latches,
  edge memories, heartbeat one-shots, monitored-reset arming — and CLAUDE.md
  §9 already forbids resuming from stale sequence state and forbids automatic
  resume after a stop. No switching flow, state carry-over or in-flight
  hand-off is designed, now or later, without a new owner ruling.

**"From the GUI", reconciled with "at startup":** the GUI *displays and
confirms* the selection (the banner above); it does not carry it to other
processes. Making the HMI page itself the selection surface would require the
HMI to launch or configure the bridge — a new inter-client path that ADR 0005
/ ADR 0008 deliberately do not have, for a datum the launcher already owns.
If the owner wants a literal pre-start chooser, the shape that stays inside
the boundaries is a trivial launcher front-end (a `stack.sh` prompt or a
static chooser page that invokes the launcher), not an HMI feature; noted as
a cosmetic option, not designed here.

### F.4 How portability is demonstrated

The claim is demonstrated by **runs, not diffs** — and the owner's rulings
make it sharper: one session per vendor, same everything else.

| Element | Siemens session | Beckhoff session |
|---|---|---|
| bridge, HMI | byte-identical code | byte-identical code |
| configs | `*.siemens.yaml` pair | `*.twincat.yaml` pair |
| conformance | `check_connect_conformance` CSV | same tool, same assertions, own CSV |
| scenarios | `plc/forklift/SPEC.md` §11 **T5.1–T5.6** (the five M4 criteria + bridge-loss) as run for M4 | the same procedures, from the TwinCAT SPEC's mirrored section |
| latency | existing instrumentation CSVs | same instrumentation, own CSVs, environment-qualified ("user-mode runtime, no real time") |
| evidence | kept | kept **beside** it, neither replacing the other (LESSONS 2026-07-27 on evidence per environment) |

If the demo cell is scoped in, T1/T2/T4 of `plc/demo-cell/SPEC.md` §11 are
re-run the same way. The safety scenarios (T6, AT-*) are **not** run against
Beckhoff and the evidence says why (§B).

**The honest README claim afterwards**, verbatim proposal:

> The cell's OPC UA contract is vendor-portable: the same unmodified bridge
> and commissioning HMI, and the same scenario procedures, pass against a
> Siemens S7-1500 (PLCSIM Advanced) and a Beckhoff TwinCAT 3 runtime
> (user-mode, no real-time claim), with the controller selected at startup
> and fixed for the session. The safety layer is Siemens-only: TwinSAFE
> requires safety hardware (its logic simulator, TE9100, is announced but
> not released), so the Beckhoff mirror carries the standard program only.

### F.5 Implementation stages, sized, and gate-placement options

Stages (a brief ≈ one deliverable, this project's unit of work):

| Stage | Content | Size |
|---|---|---|
| 0 | **Probe, owner-in-tool**: install 4026 + TF6100 (UM runtime), trial licences as demanded, build both §C.4 layout candidates in a throwaway project, browse, record NamespaceArray/BrowseNames/types verbatim; confirm install co-residency with TIA/PLCSIM/WSL2 | 1 brief (probe procedure, FIO-FEASIBILITY-shaped) + 1 owner session |
| 1 | **Vendor ADR**: the TwinCAT contract constraints as read back (URI form, root path, layout choice), the standard-program-only safety scope, the startup-selection ruling | 1 brief |
| 2 | **`plc/twincat/forklift/SPEC.md`** + ST translation validated against the existing logic double | 1–2 briefs (+1 if demo cell in scope) |
| 3 | **Clients**: config pairs, `stack.sh --controller`, endpoint fail-fast (and the optional both-alive refusal), the `BuildInfo` read + HMI banner | 2 briefs (infra/bridge, hmi) |
| 4 | **Runs**: conformance both vendors, T5.1–T5.6 on TwinCAT, evidence, README claim; drift-check tool of §F.2 | 1–2 briefs + 2 owner sessions |

Total ≈ **6–9 briefs and 3–4 owner tool sessions** for the forklift-cell
mirror; +2 briefs and more owner time with the demo cell included.

**Gate-placement options — the decision is the owner's; none is chosen
here:**

- **Option A — inside M5.** Fold the mirror into the current gate.
  *Buys:* one commissioning period; TIA-side knowledge freshest. *Costs:* M5
  is already the project's heaviest gate (F-layer feasibility unresolved,
  SLAM/Nav2, HMI v2, showcase); +6–9 briefs of cross-cutting work raises its
  risk and muddies its showcase, and the vendor mirror has no dependency on
  anything M5 adds. The mirror would also immediately trail M5's own node
  additions (`Forklift/Safety/` lands there — which the mirror must then
  *not* serve, §B.3).
- **Option B — its own gate between M5 and M6** ("multi-vendor gate"). Closes
  on: both conformance runs green, T5.1–T5.6 recorded on TwinCAT with the
  banner visible, both evidence sets committed, README claim landed.
  *Buys:* a crisp, self-contained, observable-behaviour gate; catches the
  contract at its most stable point (M4 node set frozen, M6 fleet interface
  not yet started); the M6 fleet-facing interface can then be *specified*
  vendor-neutrally from day one. *Costs:* delays M6 by the gate's length;
  one more gate in the roadmap (ADR round per LESSONS 2026-07-30 — roadmap.md
  is the single source for gate numbering).
- **Option C — parallel track, landing after M6/M7.** The mirror proceeds in
  low-priority briefs beside the main line and closes late, as a portfolio
  addendum. *Buys:* zero delay to the main line; the LLM/fleet story
  completes first. *Costs:* the contract keeps moving underneath it (M6 adds
  the fleet-facing interface and station handshakes; every addition widens
  the mirror's catch-up), so the §F.2 drift check stops being a safeguard
  and becomes load-bearing; owner tool time contends with M6/M7
  commissioning; the portability claim is absent from the intermediate
  showcases.

### F.6 The thirteen invariants, walked

| # | Invariant | Verdict |
|---|---|---|
| 1 | Safety never traverses the network | **Untouched.** The Beckhoff side carries no safety function at all (§B); its OPC UA nodes are process data; the `Forklift/Safety/` mirrors are absent there, not re-routed. |
| 2 | Loss of network is degraded mode | **Untouched.** Both watchdogs, both stale windows and the controlled-stop `ELSE` discipline port as logic (§E); the semantics are vendor-free. |
| 3 | Fleet contract is VDA 5050 | **Untouched.** No fleet-layer involvement; nothing here touches MQTT. |
| 4 | The PLC is the OPC UA server, never inverted | **Untouched in direction and in force.** Honest note for the vendor ADR: on Beckhoff the endpoint is served by TcOpcUaServer, a separate service coupled to the runtime by ADS on the same host — the server side of the same boundary, a vendor implementation detail of "the PLC", not a topology change. Both clients remain clients; nothing in this proposal listens. |
| 5 | The PLC does not manage the fleet | **Untouched.** The mirror carries the same node set; no fleet datum lands on either controller. |
| 6 | The fleet manager never commands actuators | **Untouched.** The request/setpoint split and the read-only `Output/` group port unchanged, enforced on Beckhoff by access pragmas (§C.1). |
| 7 | Standard and safety programs independent | **Untouched — trivially on Beckhoff (no safety program exists there), materially on Siemens (nothing changes).** The asymmetry is disclosed wherever the twin is described (§B.3). |
| 8 | Tailscale is engineering access only | **Untouched.** No new transport; the TwinCAT endpoint sits where PLCSIM's does. |
| 9 | Hard real time stays out of Python | **Untouched.** The TwinCAT user-mode runtime is non-real-time, but the invariant is satisfied the way the project already reads it for PLCSIM: deterministic-*class* logic lives in the PLC layer, and no gate criterion claims hard real time (`plc/demo-cell/SPEC.md` §4.1). Evidence carries the "user-mode, no real time" qualifier (§A.4). |
| 10 | Single source of truth per data item | **Untouched, and actively defended**: the node model stays sole owner of the contract (§F.2 mechanism); the selection datum has one owner (the launcher invocation, §F.3); the displayed controller identity is the server's own datum, displayed not configured. |
| 11 | Layers talk only to adjacent layers | **Untouched.** No new edge: the selection deliberately does not create an HMI→bridge path (§F.3). If the owner wants the §3 topology to *depict* the vendor-selectable controller, that is a drawing change taken in an ADR round (LESSONS 2026-07-30), not required by this design. |
| 12 | Simulation is Gazebo | **Untouched.** TwinCAT XAR is controller simulation standing exactly where PLCSIM Advanced stands; the world stays Gazebo; MuJoCo appears nowhere. |
| 13 | No secrets in the repository | **Untouched.** TwinCAT licence files and any future certificates stay outside the repo, referenced by absolute path like the existing security config keys. |

**No invariant needs to change. One new ADR is required regardless** (§F.7) —
required by the project's own discipline, not by an invariant conflict.

### F.7 The ADR this needs (proposal-needed item, per the brief's forbidden list)

A single new ADR — the ADR 0006 analogue for the second vendor — authored at
stage 1, **after** the stage-0 probe and **before** any client config or
vendor SPEC is written (a config authored before the tool has spoken would
repeat the `urn:amr-agent:cell:plc` failure verbatim). It records:

1. the TwinCAT namespace URI as read from the installed server, its
   derivation and its host-name coupling (and, consequently, that the
   Windows computer name joins the contract-change discipline);
2. the chosen symbol layout (§C.4 m1 or m2) and the resulting interface-node
   path;
3. the standard-program-only scope: safety is Siemens-only, with the TE9100
   status quoted and dated;
4. the startup-selection ruling (owner, 2026-07-31): controller chosen at
   startup via the launcher, immutable per session, no hot switch — recorded
   so it binds future work the way ADR 0008 D2.7 parks the remote operator.

It supersedes nothing: ADR 0006 remains true of the Siemens interface and
stands beside it.

---

## G. Owner decisions required (listed as decisions, not resolved)

1. **Gate placement** — Option A, B or C of §F.5.
2. **Directory shape variant** — additive `plc/twincat/` (proposed, §F.1) or
   symmetric rename to `plc/siemens/` + `plc/twincat/` (cost: a whole-repo
   reference sweep through committed evidence).
3. **Mirror scope** — forklift cell only, or demo cell too (+2 briefs, more
   owner tool time; buys the M3 loop demonstrated on both vendors).
4. **The both-endpoints-alive guard** — should `stack.sh` refuse to start
   when both vendors' endpoints answer (§F.3), or only warn.
5. **TE9100 watch** — whether to re-probe the safety question if/when
   Beckhoff releases the TwinSAFE Logic Simulator (its own brief, its own
   feasibility procedure).

*(Removed from this list by owner ruling 2026-07-31: switching semantics —
mid-run switching is out of scope; see §F.3.)*

---

## Sources

Beckhoff Information System and beckhoff.com (all verified 2026-07-31;
grades per the header):

- TwinCAT 3 test licenses [fetched] — https://infosys.beckhoff.com/content/1033/tc3_licensing/921947147.html
- Creating trial licenses manually [fetched] — https://infosys.beckhoff.com/content/1033/tc3_licensing/3510308491.html
- TwinCAT 3 licensing overview [snippet] — https://www.beckhoff.com/en-us/products/automation/twincat/twincat-3-licensing/
- System requirements (Hyper-V/VBS vs XAR; XarMode from 4026.21) [fetched] — https://infosys.beckhoff.com/content/1033/tc3_overview/6162419083.html
- Runtime Configuration (XarMode KM/UM/KMWithUM; UM min. 1 ms cycle; UM offered as RT replacement where Hyper-V requirements unmet) [snippet] — https://infosys.beckhoff.com/content/1033/tc3_installation/20830884491.html
- TwinCAT 3 Usermode Runtime overview (from 4026; same code, no real time; TC1700 engineering mode free of license costs) [fetched] — https://infosys.beckhoff.com/content/1033/tc170x_tc3_usermode_runtime/11319881355.html
- TF6100 product page — https://www.beckhoff.com/en-us/products/automation/twincat/tfxxxx-twincat-3-functions/tf6xxx-connectivity/tf6100.html
- TF6100 server, PLC symbols and pragmas (`OPC.UA.DA`, inheritance, access/read-only pragmas) [fetched] — https://infosys.beckhoff.com/content/1033/tf6100_tc3_opcua_server/15620470667.html
- TF6100 manual (namespace URI examples incl. hostname; NamespaceArray; `PLC1` device; `AllowRenameUri`/`ComAlias` configuration references) [snippet] — https://download.beckhoff.com/download/document/automation/twincat3/TF6100_TC3_OPC_UA_Server_EN.pdf (v1.4.0, 2025-09-16)
- TwinSAFE software overview (simulation extension wording) [fetched] — https://www.beckhoff.com/en-us/products/automation/twinsafe/twinsafe-software/
- TE9100 TwinSAFE Logic Simulator — "product announcement | estimated market release on request" [fetched] — https://www.beckhoff.com/en-us/products/automation/twinsafe/twinsafe-software/te9100.html
- TE1111 EtherCAT Simulation licensing [snippet] — https://infosys.beckhoff.com/content/1033/te1111_ethercat_simulation/576854027.html
- TE9000 Safety Editor — https://www.beckhoff.com/en-us/products/automation/twinsafe/twinsafe-software/te9000.html

Repository sources: `docs/interfaces/opcua-nodes.md`, `docs/interfaces/handshake-tables.md`,
`docs/adr/0006-tia-derived-namespace-uri.md`, `plc/demo-cell/SPEC.md`,
`plc/forklift/SPEC.md`, `plc/forklift-safety/SPEC.md` + `FIO-FEASIBILITY.md`,
`bridge/README.md` + `config/bridge.yaml` + `amr_bridge/config.py`,
`hmi/README.md` + `config.yaml` + `EVIDENCE_HMI.md` §F, `stack.sh`,
`docs/roadmap.md`, `docs/LESSONS.md`.
