# Beckhoff port research — the PLC substrate after the TIA trial

Date: 2026-08-15. Trigger: the owner's TIA Portal / S7-PLCSIM Advanced trial
has expired. The safety chain of m5_ver2 must run on Beckhoff TwinCAT, on
the same machine (Windows + WSL2), with the WSL vehicle side unchanged.
This is ADR 0013's M8 vendor-portability question arriving early, by
necessity rather than by schedule — and it now carries the whole live
system, not a second implementation beside a first.

## 1. Facts, graded as ADR 0014 grades them

**[fetched]** = page retrieved and read; **[snippet]** = statement from a
search excerpt of the named page. All verified 2026-08-15.

| # | Fact | Source | Grade |
|---|---|---|---|
| F1 | TwinCAT 3.1 **Build 4026** installs via the **TwinCAT Package Manager**; the XAE engineering environment is a free download (registration required) | infosys *Installation with the TwinCAT Package Manager* (15698617995) | [snippet] |
| F2 | As of **4026.21**, TwinCAT provides a **user mode runtime (UM)** "as a replacement for the real-time runtime, because more and more XAE installations on Windows do not meet the Hyper-V requirements". Three runtime modes exist — real-time (KM), user mode (UM), hybrid (KMWithUM) — selected in TcPkg → Settings → Runtime. UM has **no real-time behaviour**, minimum cycle time **1 ms** | infosys *Runtime configuration* (20830884491) | [fetched] |
| F3 | TwinCAT's **real-time runtime and Hyper-V do not coexist**; WSL2 uses Hyper-V even when the Hyper-V feature is "disabled", and community reports had to drop to WSL1 to run the RT runtime | alltwincat.com *TwinCAT & virtualization*; twincontrols.com *Running TwinCAT in Virtual Machine* | [snippet] |
| F4 | **7-day trial licenses** can be generated in XAE for most TwinCAT functions and runtime products, **repeated any number of times**, no internet or dongle needed, full functionality | infosys *TwinCAT 3 test licenses* (921947147); beckhoff.com *TwinCAT 3 licensing* | [snippet] |
| F5 | **TE9000 TwinCAT 3 Safety Editor**: graphical FBD safety programming integrated in TwinCAT 3, with **certified safety function blocks** (e.g. `safeEstop`, monitoring up to 4 two-channel e-stop circuits); targets are TwinSAFE logic devices (EL6910, EJ6910, EK1960, …) | beckhoff.com TE9000 product page; contactandcoil.com TwinSAFE tutorial | [snippet] |
| F6 | **TE9100 TwinSAFE Logic Simulator**: simulates safety applications built in the Safety Editor **without real hardware**, on top of TE1111 EtherCAT Simulation; hybrid (part real, part simulated) supported. Status on the worldwide product page: **"product announcement, estimated market release on request"** — not yet a shelf item | beckhoff.com TE9100 product page | [fetched] |
| F7 | **TE1111 EtherCAT Simulation** ships inside the TwinCAT installation since 3.1.4018 and is licensed per instantiated simulation device | infosys TE1111 *Installation/Licensing* (576854027) | [snippet] |
| F8 | A safety project targeting **EL6910** can be **debugged without hardware** in the editor: simulated "external device" target + alias devices (EL1904/EL2904), debug mode with online value manipulation. Community-documented; explicitly does **not** work for the older EL6900 target | twincontrols.com *Creating a TwinSAFE Simulation Project* | [fetched] |
| F9 | The 2017 **TwinCAT Safety PLC** (software safety runtime, SIL3/PL e capable) runs **only on Beckhoff IPCs** — not on a generic laptop | Beckhoff TcSafetyPLC manual 1.2.0 | [snippet] |
| F10 | **pyads** (Python ADS wrapper, TcAdsDll on Windows) reads/writes PLC symbols by name; the local runtime is AMS `127.0.0.1.1.1`, PLC port **851** (`pyads.PORT_TC3PLC1`); list reads/writes batch multiple symbols per call | pyads.readthedocs.io; pypi.org/project/pyads | [snippet] |

## 2. What this decides

### D1 — Runtime: TwinCAT 3.1 4026, **user mode runtime**, on the owner's machine

The Gazebo/ROS side lives in WSL2, WSL2 rides Hyper-V, and the RT runtime
will not start beside it (F3). The UM runtime exists for exactly this
machine profile (F2), and this project needs no hard real time from the
PLC substrate — PLCSIM Advanced was not hard real time under Windows
either, and the m5_ver2 timing budgets (0.28 s / 0.25 s / 0.40 s staleness
windows, 20 ms writer cycle) sit far above UM's 1 ms floor. Licensing is
the renewable 7-day trial (F4) — unlike the expired TIA trial, this is an
**officially unlimited** evaluation mechanism.

### D2 — The seam does not move: same wire, same single writer, WSL untouched

The Windows writer (`beckhoff/windows/step5_tc.py`, ported from
`m5_ver2/step5/windows/step5.py`) keeps the **identical UDP wire contract**
— 5100 out `{estop_healthy, motor, case, v_limit, ts}`, 5101 in the
six-field + encoder report — so `plc_link.py`, `sensor_link.py` and
everything below them run **unchanged**. Only the PLC API swaps: PLCSIM
Runtime API → **ADS by symbol name** over pyads (F10). The single-writer
rule carries over verbatim: one process opens ADS toward the PLC's inputs.

### D3 — The safety logic, two tracks with two different claims

**Track A — the standard-runtime port (day 1, unblocks everything).**
The F-program's *documented and measured* behaviour
(m5_ver2/CLAUDE.md §3.2) is ported to structured text in the standard
TwinCAT runtime: an `FB_ESTOP1` block with the real semantics (a demand
latches; healthy input does not re-enable; acknowledge is a rising edge;
`ACK_NEC` — one acknowledge required after startup), five instances
(e-stop, back/right/left protective fields, speed monitor), the encoder
cross-check (|A−B| > 50 → demand; 2800 mm/s ceiling), the V_Limit law
(1500 with the warning fields clear, else 300) and the case bits.
**Claim, stated wherever the port is described: this models the
F-behaviour in a standard program — no safety integrity, no PL, Category,
SIL or PFH.** It is the same claim discipline ADR 0011 D5/F6 applied to
the stand-in path, and the same asymmetry ADR 0013 D2 planned to state
for M8: the F-safety layer existed on the Siemens controller.

**Track B — the TwinSAFE artifact (authentic safety logic, staged).**
The same chain built in the **TE9000 Safety Editor** as a real safety
project (certified FBs, `safeEstop` et al., EL6910 target — F5), verified
by the editor's own verification step, and exercised in the editor's
hardware-less debug mode (F8). Execution as a *safety runtime* needs one
of: **TE9100** when it ships (F6 — status "product announcement", to be
asked of Beckhoff sales, quoted and dated per ADR 0013 D2), or real
TwinSAFE hardware (EK1100 + EL1918 + EL2904 + EL6910 class — the paid
path), or a Beckhoff IPC for the 2017 Safety PLC (F9 — out of scope).
Only Track B on a real safety runtime would earn the words "F-logic
executes"; until then those words are retired from the live-system claims.

### D4 — Port fidelity rules

- **Tag names**: ST identifiers cannot carry a hyphen, so `E-Stop` becomes
  `GVL_IO.EStop` **at the ADS seam only**; the UDP wire keys and every WSL
  name stay byte-identical. One mapping table, in the writer.
- **Unmapped TIA behaviours stay unmapped, conservatively.** The right/left
  warning-field composition into V_Limit was never mapped (step5 PROOF open
  item 4); the port takes the conservative AND (any warning field occupied
  → 300). The monitoring-case selection logic was never mapped; the port
  pins **case 1**, the value every live step5 run observed. Both choices
  are labelled in the ST source and fall to the validation diff.
- **The fail direction is unchanged**: writer exception or window close →
  `EStop` and all six field inputs written False; a dead 5101 link writes
  fields False and encoders 0/3000 (a demanded stop by two routes).

## 3. Alternatives rejected

- **Disable WSL2/Hyper-V to run the RT runtime** — kills the Gazebo/ROS
  half of the project to buy real time the project does not need (F3, D1).
- **TwinCAT/BSD or a second machine** as the runtime host — new toolchain
  and a network hop through the supervision seam, against ADR 0016's
  one-machine simulation substrate; nothing it buys is needed at UM's
  fidelity level.
- **Renew the Siemens path** (buy TIA + PLCSIM) — owner-cost decision, not
  ours to make; and M8 wanted the second vendor anyway. The Siemens
  artifacts (`plc/` exports, `safety_summary.pdf`, all measured evidence)
  remain in the tree as the F-CPU record.
- **Port to CODESYS SoftPLC instead** — a third vendor with its own trial
  mechanics, while the roadmap already names Beckhoff (ADR 0013) and
  TwinSAFE gives the safety story a real second act.

## 4. Sources

- infosys.beckhoff.com — Runtime configuration (4026): content/1033/tc3_installation/20830884491.html
- infosys.beckhoff.com — Package Manager installation: content/1033/tc3_installation/15698617995.html
- infosys.beckhoff.com — TwinCAT 3 test licenses: content/1033/tc3_licensing/921947147.html
- beckhoff.com — TwinCAT 3 licensing; TE9000; TE9100 product pages
- infosys.beckhoff.com — TE1111 Installation/Licensing: content/1033/te1111_ethercat_simulation/576854027.html
- twincontrols.com — Creating a TwinSAFE Simulation Project; Running TwinCAT in a VM
- alltwincat.com — TwinCAT & virtualization (2018), TwinCAT in user space (2022)
- Beckhoff TcSafetyPLC manual 1.2.0 (2017), download.beckhoff.com
- pyads.readthedocs.io — Quickstart; pypi.org/project/pyads
