# Beckhoff runbook — the m5_ver2 safety chain on TwinCAT

The TIA / PLCSIM Advanced trial is gone; from here the PLC substrate is
**TwinCAT 3.1 Build 4026, user mode runtime**, on the same Windows + WSL2
machine. The WSL vehicle side — Gazebo, the nine step5 processes, the HMI —
runs **unchanged**: the Windows writer keeps the identical UDP wire, so
`plc_link.py` and `sensor_link.py` cannot tell the vendors apart.

Why user mode and not real time, why the trial licensing is sustainable,
and why the safety story has two tracks: **[RESEARCH.md](RESEARCH.md)**
(graded facts, sources, decisions). Read its D3 before quoting any safety
claim: **Track A below is a standard program modelling the F-behaviour —
no safety integrity, no PL/SIL.** Track B (part 5) is the authentic
TwinSAFE artifact.

## Part 1 — install TwinCAT (once)

| # | Do this | Expect |
|---|---|---|
| 1.1 | Create a free account at beckhoff.com, download the **TwinCAT Package Manager** (TcPkg) from the TwinCAT 3.1 Build 4026 download area. | An installer, no license key asked. |
| 1.2 | Run TcPkg. In its first-run dialog select the feed it proposes, then install the **TwinCAT Standard** workload (XAE engineering + XAR runtime). | XAE Shell (or Visual Studio integration) appears in the Start menu. |
| 1.3 | In TcPkg → **Settings → Runtime**, set the runtime to **User mode (UM)**. This machine runs WSL2, WSL2 rides Hyper-V, and the real-time runtime will not start beside it — UM exists for exactly this profile (RESEARCH F2/F3). Do **not** switch off WSL2 to force real time; nothing in this project needs it. | TcPkg reports the runtime configuration as user mode; packages adjust. |
| 1.4 | Windows Python (the same 64-bit Python that ran `step5.py`): `pip install pyads`. | `python -c "import pyads"` says nothing. |
| 1.5 | *(Track B, optional now)* In TcPkg also install the **TwinCAT Safety** engineering package (TE9000 Safety Editor). | "Safety" project templates appear in XAE. |

## Part 2 — create and run the PLC project (once, ~20 minutes)

| # | Do this |
|---|---|
| 2.1 | Open **TcXaeShell** → File → New → Project → **TwinCAT XAE Project**. Name it `amr_tc`. Keep the target `<Local>`. |
| 2.2 | Right-click **PLC → Add New Item → Standard PLC Project**, name `forklift`. |
| 2.3 | Under `forklift Project` → **GVLs → Add → Global Variable List**, name **`GVL_IO`**, and paste the contents of [`plc/GVL_IO.st`](plc/GVL_IO.st) (replace the generated skeleton entirely). |
| 2.4 | Under **POUs → Add → POU**, Function Block, language **Structured Text**, name **`FB_ESTOP1`**, paste [`plc/FB_ESTOP1.st`](plc/FB_ESTOP1.st) — declaration part into the upper pane, body (below the last `END_VAR`) into the lower pane. |
| 2.5 | Open the generated **`MAIN`** and paste [`plc/MAIN.st`](plc/MAIN.st) the same way. Confirm `MAIN` is referenced by the default **PlcTask** (10 ms) under SYSTEM → Tasks. |
| 2.6 | Build (F7). Zero errors expected. |
| 2.7 | **Activate Configuration** (toolbar). The license dialog appears: click through to **generate the 7-day trial license**, type the security code it shows. This is the officially unlimited-renewal evaluation path (RESEARCH F4) — when it expires in 7 days, re-activating repeats this dialog and everything else stays as it was. |
| 2.8 | Confirm the runtime goes to **Run mode** (the TwinCAT icon turns green). **Login** (the PLC login toolbar button) to watch `MAIN` online: `GVL_IO.Motor` FALSE, `V_Limit` 300 — the born-latched, fields-violated cold state, exactly like a fresh `PLC_2`. |

The project is saved once and reopened forever; only 2.7's trial renewal
recurs weekly.

## Part 3 — daily run order

The shape of the m5_ver2 step5 run order, with rows 1 and 7 swapped to
TwinCAT. The PLC goes first; the vehicle cannot be enabled without it.

| # | Where | Do this |
|---|---|---|
| 1 | Windows | Open `amr_tc` in TcXaeShell → **Activate Configuration** → Run mode. (Trial expired? The dialog offers the renewal — type the code, ~15 s.) |
| 2 | WSL | `cd /mnt/c/Users/ozkan/projects/amr-agent` |
| 3 | WSL | `./m5_ver2/step5/step5.sh deploy` *(first run or after edits)* |
| 4 | WSL | `./m5_ver2/step5/step5.sh start` — nine pid lines, Gazebo + HMI appear, exactly as before. |
| 5 | Windows | `cd C:\Users\ozkan\projects\amr-agent` then `python beckhoff\windows\step5_tc.py` — the same grey panel opens; console prints `streaming PLC state to <wsl-ip>:5100` and `listening for the scanners on 0.0.0.0:5101`. |
| 6 | Panel | **RESET** once. `Motor` goes True, `MOTOR ENABLED`, the HMI line reads `Drive enable: ON`. |
| 7 | HMI | Teleop or Auto exactly as the step5 README describes — nothing on this side knows the vendor changed. |
| 8 | Done | Close the panel window **first** (it writes the trip values on the way out), then `./m5_ver2/step5/step5.sh stop`. The runtime can stay in Run. |

Everything in the step5 README's **Not a bug** table still applies —
including "one RESET after every stack bounce" (silence on 5101 writes the
fields False; a demand latches) and "the e-stop is the brake, `stop` is
not".

## Part 4 — validation: prove the port before trusting it

Re-run the m5_ver2 acceptance moments and write the transcripts to
`beckhoff/PROOF.md`. The port is not the system until this table is
earned; the three **labelled port choices** (conservative WF AND, pinned
case 1, +50 mm/s case-ceiling margin — see `plc/MAIN.st`) are what the
diff column exists to catch.

| # | Stimulus | Must observe |
|---|---|---|
| V1 | Cold start, nothing pressed | `Motor` False until one RESET (ACK_NEC). |
| V2 | PUSH then RELEASE e-stop, no reset | Lamp neutral but `Motor` still False — the latch made visible. RESET restores motion on the next message. |
| V3 | Drive at a wall; back protective field trips | Truck stops; clearing the field does **not** re-enable; RESET does. |
| V4 | ENCODER → **OFFSET A** while driving | Cross-check demand ≤ one panel cycle; latch; RESET after **OK** clears. |
| V5 | ENCODER → **FREEZE A**, then drive | Trips once the truck moves. |
| V6 | Drive near racking (warning field occupied) | `V_Limit` 300 on the wire; the truck creeps; no latch while it obeys. |
| V7 | Close `step5_tc.py` mid-drive | Vehicle stops ≤ 0.45 s (the step-1 budget); HMI red ≤ ~0.3 s. |
| V8 | Bounce the WSL stack, panel running | Fields go False on 5101 silence → demand; one RESET re-arms. |
| V9 | `python3 -m pytest m5_ver2/step5/tests/ -q` in WSL | Still `195 passed` — the vehicle side is provably untouched. |

## Part 5 — Track B: the TwinSAFE safety project (authentic safety logic)

The standard-runtime port above keeps the system alive; this track rebuilds
the chain as a **real safety application** in the TE9000 Safety Editor, the
artifact a Beckhoff commissioning engineer would recognise. Stage it after
V1–V9 pass; nothing in daily operation waits on it.

1. In `amr_tc`: right-click the project → **Add New Item → Safety project**
   (template *with* ErrAck and Run mappings). **Target system: EL6910** —
   the editor's hardware-less debug explicitly does not work for the older
   EL6900 target (RESEARCH F8).
2. Recreate the chain in FBD with the certified blocks: `safeEstop` for the
   e-stop and the three protective-field OSSD pairs, the analog comparison
   blocks of the EL6910 set for the encoder cross-check, `safeMon`/restart
   blocks for the monitored reset. Alias devices: EL1904-class inputs,
   EL2904-class output for the enable.
3. **Verify** the safety project (the editor's own verification pass), then
   exercise it in **debug mode** against a simulated external device,
   manipulating the input values online (RESEARCH F8).
4. For *execution* as a safety runtime, one of, in order of preference:
   **TE9100 TwinSAFE Logic Simulator** — ask Beckhoff sales for
   availability; the product page still says *"product announcement,
   market release on request"* (RESEARCH F6, quoted 2026-08-15) — or real
   TwinSAFE hardware (EK1100 + EL1918 + EL2904 + EL6910 class) on a spare
   EtherCAT port.
5. Claims discipline, unchanged from ADR 0011 D5 / ADR 0013 D2: until the
   safety project runs on a safety runtime, the live system's words are
   "models the F-behaviour"; the Siemens-era F-CPU evidence stays in the
   tree as the record of real F-logic execution, and the asymmetry is
   stated wherever the port is described.

## Part 6 — troubleshooting

| Symptom | Meaning / fix |
|---|---|
| Panel exits: *target port not found* / ADS timeout | Runtime not in Run. Activate Configuration in XAE; check the TwinCAT tray icon is green. |
| Panel exits: *symbol not found* | The running project is not the one with `GVL_IO` (or activation was skipped after an edit). Re-activate. |
| Activate Configuration fails on licensing | Trial expired: the same dialog offers **7 days trial license** — type the code. Unlimited renewals are the documented evaluation path. |
| Runtime refuses to start / real-time errors mentioning cores or Hyper-V | The runtime is set to real-time mode. TcPkg → Settings → Runtime → **User mode** (part 1.3). |
| `pip install pyads` succeeds but `import pyads` fails on TcAdsDll | pyads needs the TwinCAT ADS router, which the XAE install provides; install order was reversed. Reinstall pyads after TwinCAT, or reboot. |
| Panel runs, HMI stays red | Same as m5_ver2: check the WSL stack is up and the panel console shows the discovered WSL IP; the IP moves on every WSL restart — the panel rediscovers it at launch, so restart the panel after restarting WSL. |
| `Motor` never True after RESET | Read the panel's status line: any `F` in `PF b/r/l` means a field verdict is missing — 5101 silent (stack down) or a real intrusion. Encoders `0/3000` = the dead-link picture, same cause. |

## What did not change

The single-writer rule (one process opens ADS toward the inputs), the
fail-safe direction, the UDP port map, every WSL-side constant and test,
the deploy discipline, and the HMI. `m5_ver2/CLAUDE.md` remains ground
truth for the *behaviour*; this directory is ground truth for the
*substrate* that now executes it.
