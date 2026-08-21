# The first build's PLC program — what it was, and why it could not be used

This is the post-mortem of the M5 ver1 controller: the one the recorded
demonstration ran on, designed entirely under Claude supervision. It is kept
here because it *worked on camera* and was still **unusable as an engineering
artefact**. Both halves of that sentence matter; the second is why
[`m5_ver2/`](../../m5_ver2/) exists.

## 1. What the CPU carried

One simulated CPU (S7-1516F, PLCSIM Advanced), two programs:

| Program | Source of truth | Size of that source |
|---|---|---|
| `FB_ForkliftTeleop` — the standard program: teleop setpoints, mode arbiter, autonomy envelope, link supervision, latches | [`plc/forklift/SPEC.md`](../../plc/forklift/SPEC.md) | **254 KB, 2 673 lines** of prose |
| `F_Forklift_Safety` — the F-program: e-stop, protective-field stop, monitored reset, speed monitor, SS1 | [`plc/forklift-safety/SPEC.md`](../../plc/forklift-safety/SPEC.md) | **227 KB, 2 387 lines** of prose |

Plus the procedures that turned prose into a TIA project:

- [`plc/forklift/TIA-BUILD-PROCEDURE.md`](../../plc/forklift/TIA-BUILD-PROCEDURE.md)
  — **177 KB, 2 568 lines** of click-by-click instructions for entering the
  standard program by hand.
- [`plc/forklift/TIA-FIX-PROCEDURE.md`](../../plc/forklift/TIA-FIX-PROCEDURE.md)
  — **40 KB, 495 lines** of *fixes*, after the first entry attempt drifted
  from the spec.

**481 KB of English was the source of truth for one CPU.** Not model-based
code generation, not a library — prose, transcribed into TIA Portal by a
human clicking, across days, with a second document to repair what the first
transcription got wrong.

## 2. The shape of the standard program

`FB_ForkliftTeleop` (SPEC §7) was honestly engineered: heartbeat-supervised
links, affirmative plausibility checks, latching faults, a monitored reset,
direction-scoped fork limits, exactly one assignment site per actuator
setpoint. The M5 delta (§14) added the drive-mode arbiter, the vehicle
heartbeat, the operator's process stop and the autonomy envelope; §14.16/17
added the warning-field speed ceiling in both modes.

You can read it today as Python: [`virtual_plc/standard_program.py`](virtual_plc/standard_program.py)
is a statement-for-statement transliteration, and
[`plc/forklift/double/logic.py`](../../plc/forklift/double/logic.py) was the
M4-era original. The logic was never the problem.

## 3. The shape of the F-program

49 networks in the post-delta order: the S015 validity check (V1–V7), the
speed-monitor terms (SL1–SL20), the monitored reset with its 200 ms–3 s hold
window and its stuck-button fault, three set-dominant demand latches, and the
SS1 sequencer (Q1–Q4). Transcribed for the virtual PLC in
[`virtual_plc/f_program.py`](virtual_plc/f_program.py), with every constant
cited to its SPEC row.

Its behaviours were subtle and *correct as designed*: demands latch and need
a monitored reset; a dead input source reads as a demand, never as a clear
world; the warning field gates the speed ceiling, not the enable — a fact
that was **discovered by measurement** (`step2/PROOF.md`, `step3/PROOF.md`
record `Motor=True` while `WF=False`), not read out of the program, because
nobody could hold 49 networks of cross-latching SCL in their head.

## 4. Why it was disastrous in practice

**It was specified faster than it could be verified.** Two 250 KB
specifications were written *before* a line of SCL existed, in a single
design pass, integrating every idea at once: three scanners, dual encoders,
a speed monitor with four independent demand causes, an SS1 sequencer, a
two-handed monitored reset, a mode arbiter, an autonomy envelope. Each idea
is defensible. Composed unverified, they produced a controller whose own
boot state needed a runbook paragraph to explain (TorqueOffDemand boots TRUE;
the vehicle will not move until a monitored reset; that is intended).

**The transcription gap was unbridgeable.** The SPEC was not the program;
the program was what the owner typed into TIA Portal following a 2 568-line
procedure. The FIX procedure exists because the first transcription drifted.
Every subsequent behavioural question ("is `WF_Clear` a `Motor` condition?")
could only be answered by running the cell and measuring — the opposite of
why you write a safety program down.

**The safety PLC was safety-themed.** The F-CPU's inputs did not come from
F-I/O. They came from `bridge/standin_writer/standin_writer.ps1` — a
PowerShell script poking a standard DB through the PLCSIM API, fed over two
TCP sockets from Python scripts in WSL. The F-program's logic was real, but
with simulated inputs there is no PL/SIL claim, no discrepancy behaviour, no
F-runtime semantics worth the name. The writer's own design document said
so. The demo could *show* the safety chain acting; it could never *be* a
safety chain.

**The reset protocol was unusable at the bench.** The monitored reset
required: e-stop circuit closed (writer console), process stop released
(HMI), then a `reset pulse 2000` typed at the writer *and* the HMI RESET
button held across the same two seconds — refused if the warning field was
occupied and the vehicle above 300 mm/s, refused if the press was shorter
than 200 ms, faulted if longer than 3 s. The recorded videos show this dance.
It is correct. It is also the kind of correct that makes a demonstrator
fragile and a reviewer suspicious.

**Integration debt compounded.** The full layered stack (`agv/`, `sim/`,
`bridge/`, `hmi/`, `fleet/`, `viz/`, `plc/`) was integrated all at once.
When the vehicle would not move, the cause could be in any of seven
processes on two operating systems. `m5-plc-debug/` exists because the
owner eventually stopped debugging the composition and started debugging
the safety loop in isolation.

## 5. The m5_ver2 motivation

The verdict after the first build: the architecture was proven (the videos
are real), but the controller was unmaintainable and its safety claims were
theatre. The rebuild rules, written into [`m5_ver2/CLAUDE.md`](../../m5_ver2/CLAUDE.md),
are the negation of every failure above:

- **The PLC program is ground truth** — not a 481 KB prose surrogate. Small,
  standard safety instructions (`ESTOP1`), no invented tags, behaviour read
  from the program and confirmed live.
- **Steps, each frozen with a PROOF.** Step 1 drives one e-stop bit and
  proves it. Step 2 adds the scanner. Step 3 adds the encoders. Nothing is
  integrated before its predecessor's evidence exists.
- **Single-writer rule, fail-safe direction** — one process owns the PLCSIM
  API; on any fault every input goes to the demand direction.
- **No safety claim without safety hardware semantics.** ver2's F-program is
  a professional F-program because its inputs, outputs and instructions are
  what a real F-CPU would run — not because the demo looks safe.

ver2 also answered the expired-trial problem first: since 2026-08-20 its
final step runs without PLCSIM as `step5.py --virtual`
(`m5_ver2/step5/windows/virtual_fplc.py`, an in-process behavioural model of
the *validated* F-program, with its own design spec and tests). The virtual
PLC in this folder follows that precedent — with the difference that this
build's clients speak OPC UA, so its model has to sit on the network.

The first build remains in the repo as the reference for the *layered
architecture* — and, through [`virtual_plc/`](virtual_plc/), as a runnable
artefact again. Study it, run it, learn from it. Do not build a safety PLC
this way.

## 6. Where the evidence lives

- The recorded demonstration: [`assets/`](assets/) — `demo_m5.mp4` and the
  HMI stills under `assets/hmi/`. (The inherited older media have their own
  homes: the cell captures in [`../../m3/assets/`](../../m3/), the pre-safety
  teleop showcase in [`../../m4/assets/`](../../m4/).)
- Validation against F-collective signature `29FD2C52`:
  [`docs/VALIDATION-M5.md`](../../docs/VALIDATION-M5.md).
- The owner's hand-debug chapter: [`m5-plc-debug/`](../../m5-plc-debug/).
- The rebuild: [`m5_ver2/`](../../m5_ver2/), whose final step is the repo's
  current system.
