# Beckhoff runbook — the m5_ver2 safety chain on TwinCAT

The TIA / PLCSIM Advanced trial is gone; from here the PLC substrate is
**TwinCAT 3.1 Build 4026, user mode runtime**, on the same Windows + WSL2
machine. The WSL vehicle side — Gazebo, the nine step5 processes, the HMI —
runs **unchanged**: the Windows writer keeps the identical UDP wire, so
`plc_link.py` and `sensor_link.py` cannot tell the vendors apart.

**The safety chain is authored in the TE9000 Safety Editor** as a real
TwinSAFE safety project — certified function blocks, the editor's own
verification, the documented offline simulation — from the specification
in [`plc/safety/SAFETY-APP.md`](plc/safety/SAFETY-APP.md). Because the
safety *runtime* for a hardware-less machine (TE9100) is still at
product-announcement status, the live loop is executed meanwhile by an ST
**stand-in** generated from the same spec ([`plc/`](plc/)), and the two are
pinned to each other by a parity check (part 5). Claims discipline: the
stand-in "models the F-behaviour — no safety integrity, no PL/SIL"; the
safety project is the authentic artifact. Facts, sources and the decision:
**[RESEARCH.md](RESEARCH.md)**.

## Part 1 — install TwinCAT (once)

| # | Do this | Expect |
|---|---|---|
| 1.1 | Create a free account at beckhoff.com, download the **TwinCAT Package Manager** (TcPkg) from the TwinCAT 3.1 Build 4026 download area. | An installer, no license key asked. |
| 1.2 | Run TcPkg. Select the proposed feed, install the **TwinCAT Standard** workload (XAE engineering + XAR runtime). | TcXaeShell appears in the Start menu. |
| 1.3 | In TcPkg install the **TwinCAT Safety** engineering package — the TE9000 Safety Editor. **Not optional: the chain is built with it** (part 3). | "Safety project" templates appear in XAE. |
| 1.4 | In TcPkg → **Settings → Runtime**, set the runtime to **User mode (UM)**. This machine runs WSL2, WSL2 rides Hyper-V, and the real-time runtime will not start beside it — UM exists for exactly this profile (RESEARCH F2/F3). Do **not** switch off WSL2 to force real time. | TcPkg reports user mode; packages adjust. |
| 1.5 | Windows Python (the same 64-bit Python that ran `step5.py`): `pip install pyads`. | `python -c "import pyads"` says nothing. |

## Part 2 — the standard PLC project (once, ~15 minutes)

The standard half plays the same role TIA's standard program played: it
owns the ADS seam (`GVL_IO`), computes `V_Limit` and the case bits for the
vehicle's wire — and, until the safety runtime lands, hosts the stand-in
executor of the chain.

| # | Do this |
|---|---|
| 2.1 | TcXaeShell → File → New → Project → **TwinCAT XAE Project**, name `amr_tc`, target `<Local>`. |
| 2.2 | Right-click **PLC → Add New Item → Standard PLC Project**, name `forklift`. |
| 2.3 | **GVLs → Add → Global Variable List**, name **`GVL_IO`**, paste [`plc/GVL_IO.st`](plc/GVL_IO.st). |
| 2.4 | **POUs → Add → POU**, Function Block, **Structured Text**, name **`FB_ESTOP1`**, paste [`plc/FB_ESTOP1.st`](plc/FB_ESTOP1.st) — declaration into the upper pane, body into the lower. |
| 2.5 | Open **`MAIN`**, paste [`plc/MAIN.st`](plc/MAIN.st). Confirm `MAIN` runs under the default **PlcTask** (10 ms). |
| 2.6 | Build (F7). Zero errors expected. |
| 2.7 | **Activate Configuration** → the license dialog → **generate the 7-day trial license**, type the security code. Renewal repeats this dialog weekly — the officially unlimited evaluation path (RESEARCH F4). |
| 2.8 | Runtime in **Run** (tray icon green). **Login** and watch `MAIN` online: `Motor` FALSE, `V_Limit` 300 — the born-latched cold state, exactly like a fresh `PLC_2`. |

## Part 3 — the TE9000 safety project: the chain itself (once, ~1–2 hours)

Build to the spec in [`plc/safety/SAFETY-APP.md`](plc/safety/SAFETY-APP.md);
this table is the tour, the spec is the law.

| # | Do this |
|---|---|
| 3.1 | Right-click the `amr_tc` project → **Add New Item → Safety project**, template **with ErrAck and Run mappings**, name `forklift_safety`. |
| 3.2 | **Target system: EL6910.** For hardware-less work select the target as a **simulated external device** (Target System dialog → External Device, default AMS Net Id). Do not pick EL6900 — its debug never activates without hardware (RESEARCH F8). |
| 3.3 | Add **alias devices** per the spec's table: EL1904-class channels for e-stop, the three OSSD pairs and the three warning fields; analog inputs for `ENC_A`/`ENC_B`; one EL2904-class output for the enable. Link the non-safe **Restart/ErrAck** signals to the standard PLC (`GVL_IO.Acknowledge`). |
| 3.4 | Draw the networks: four `safeEstop` instances (e-stop + three protective fields, shared Restart), the N5 speed monitor from the EL6910 analog block set (cross-check 50, ceiling 2800, case limit 1500/300 derived from the safe WF inputs), and the N6 AND into `AQ_MotorEnable`. The WF inputs feed **only** the limit derivation — never the enable AND (the measured F-CPU law). |
| 3.5 | **Verify** the safety project — the editor's own verification pass must be clean; fix what it names. |
| 3.6 | Exercise it in the **offline simulation / debug mode** (official editor capability, RESEARCH F8/F11): manipulate the input values online in the FBD view and watch the block states. Run the S1–S6 stimulus table of part 5 and record the verdicts. |
| 3.7 | Commit the safety project directory into `beckhoff/plc/safety/` beside the spec once 3.5–3.6 pass. |

## Part 4 — daily run order

The shape of the m5_ver2 step5 run order, rows 1 and 5 swapped to TwinCAT.
The PLC goes first; the vehicle cannot be enabled without it.

| # | Where | Do this |
|---|---|---|
| 1 | Windows | Open `amr_tc` in TcXaeShell → **Activate Configuration** → Run. (Trial expired? The dialog offers renewal — type the code, ~15 s.) |
| 2 | WSL | `cd /mnt/c/Users/ozkan/projects/amr-agent` |
| 3 | WSL | `./m5_ver2/step5/step5.sh deploy` *(first run or after edits)* |
| 4 | WSL | `./m5_ver2/step5/step5.sh start` — nine pid lines, Gazebo + HMI appear, exactly as before. |
| 5 | Windows | `cd C:\Users\ozkan\projects\amr-agent` then `python beckhoff\windows\step5_tc.py` — the grey panel opens; console prints `streaming PLC state to <wsl-ip>:5100` and `listening for the scanners on 0.0.0.0:5101`. |
| 6 | Panel | **RESET** once. `Motor` True, `MOTOR ENABLED`, HMI reads `Drive enable: ON`. |
| 7 | HMI | Teleop or Auto exactly as the step5 README describes — nothing on this side knows the vendor changed. |
| 8 | Done | Close the panel **first** (it writes the trip values on the way out), then `./m5_ver2/step5/step5.sh stop`. The runtime can stay in Run. |

Everything in the step5 README's **Not a bug** table still applies —
including "one RESET after every stack bounce" and "the e-stop is the
brake, `stop` is not".

## Part 5 — validation: the live chain, and parity with the safety app

**Live rows (V1–V9)** — the m5_ver2 acceptance moments, run against the
stand-in executor; transcripts go to `beckhoff/PROOF.md`. The three
labelled port choices (conservative WF AND, pinned case 1, +50 mm/s
margin) are what the diff column exists to catch.

| # | Stimulus | Must observe |
|---|---|---|
| V1 | Cold start, nothing pressed | `Motor` False until one RESET (ACK_NEC). |
| V2 | PUSH then RELEASE e-stop, no reset | Lamp neutral but `Motor` still False — the latch made visible. RESET restores motion. |
| V3 | Drive at a wall; back protective field trips | Truck stops; clearing the field does **not** re-enable; RESET does. |
| V4 | ENCODER → **OFFSET A** while driving | Cross-check demand ≤ one panel cycle; latch; RESET after **OK** clears. |
| V5 | ENCODER → **FREEZE A**, then drive | Trips once the truck moves. |
| V6 | Drive near racking (warning field occupied) | `V_Limit` 300 on the wire; the truck creeps; no latch while it obeys. |
| V7 | Close `step5_tc.py` mid-drive | Vehicle stops ≤ 0.45 s (the step-1 budget); HMI red ≤ ~0.3 s. |
| V8 | Bounce the WSL stack, panel running | Fields go False on 5101 silence → demand; one RESET re-arms. |
| V9 | `python3 -m pytest m5_ver2/step5/tests/ -q` in WSL | Still `195 passed` — the vehicle side provably untouched. |

**Parity rows (S1–S6)** — the same stimuli given to the **safety project in
the editor's simulation** (part 3.6) and to the stand-in (panel buttons);
the two must show the same enable verdict and the same latch/clear
behaviour. A divergence is a defect in one of them and blocks trusting
either.

| # | Stimulus | Verdict both must show |
|---|---|---|
| S1 | All inputs healthy, no restart yet | enable FALSE (born latched) |
| S2 | Restart edge, all healthy | enable TRUE |
| S3 | E-stop demand, then healthy again, no restart | enable FALSE throughout (latch) |
| S4 | ENC 700/300 (cross-check) | demand; latch survives equal channels; restart clears |
| S5 | WF back occupied, ENC 400/400 | demand at limit 300 (+50 margin); with ENC 200/200 no demand |
| S6 | One PF pair low, restart held high before it clears | no clear on level — restart must be an **edge** after healthy |

## Part 6 — the execution upgrade path (from stand-in to safety runtime)

1. **Ask Beckhoff sales for TE9100** (TwinSAFE Logic Simulator) availability
   — the product page still says *"product announcement, market release on
   request"* (quoted 2026-08-15). When it ships: license it, bind the
   part-3 safety project to the simulated logic device, and the stand-in's
   `MAIN` networks reduce to mirroring `AQ_MotorEnable` into
   `GVL_IO.Motor`. |
2. Or **TwinSAFE hardware** on a spare EtherCAT port: EK1100 + EL1918 +
   EL2904 + EL6910-class logic — the paid path; the same safety project
   downloads to it unchanged (alias devices re-pointed from simulated to
   real, which is what alias devices are for).
3. Either way the claims change **only then**: "certified safety logic
   executing on a safety runtime" replaces "models the F-behaviour". The
   Siemens-era F-CPU evidence remains the record of real F-logic execution
   until that day (ADR 0013 D2 asymmetry, stated and dated).

## Part 7 — troubleshooting

| Symptom | Meaning / fix |
|---|---|
| Panel exits: *target port not found* / ADS timeout | Runtime not in Run. Activate Configuration; tray icon must be green. |
| Panel exits: *symbol not found* | The running project is not the one with `GVL_IO`, or activation was skipped after an edit. Re-activate. |
| Activate Configuration fails on licensing | Trial expired: the dialog offers **7 days trial license** — type the code. Unlimited renewals are the documented path. |
| Runtime refuses to start / real-time or core errors | Runtime set to real-time mode. TcPkg → Settings → Runtime → **User mode** (part 1.4). |
| Safety project's debug button never activates | Target is EL6900 or a real (non-simulated) device is selected. Target **EL6910**, external/simulated device (part 3.2). |
| Safety verification fails | Read what it names — the verifier is the authority. Fix the FBD, never the verdict. |
| `import pyads` fails on TcAdsDll | pyads needs the TwinCAT ADS router; install order was reversed. Reinstall pyads after TwinCAT, or reboot. |
| Panel runs, HMI stays red | Same as m5_ver2: WSL stack down, or the WSL IP moved — it moves on every WSL restart, and the panel rediscovers it at launch. Restart the panel after restarting WSL. |
| `Motor` never True after RESET | Panel status line: any `F` in `PF b/r/l` = a field verdict missing (5101 silent or real intrusion); encoders `0/3000` = the dead-link picture. |

## What did not change

The single-writer rule (one process opens ADS toward the inputs), the
fail-safe direction, the UDP port map, every WSL-side constant and test,
the deploy discipline, and the HMI. `m5_ver2/CLAUDE.md` remains ground
truth for the *behaviour*; `plc/safety/SAFETY-APP.md` is ground truth for
the *safety application*; this directory is ground truth for the substrate
that executes them.
