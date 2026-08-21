# m5_ver2

The Milestone-6 system (two vehicles, VDA 5050, fleet manager) lives at
`/m6` — it grew out of this tree as `m5_ver2/step6` and moved out on
2026-08-21. This file remains ground truth for steps 1-5 and the PLC.

If `HANDOVER.local.md` exists at the repo root, read it before any work.
It is gitignored. Cursor and Claude Code coordinate there so they do not
build two M6s. Do not commit it.

## Global Constraints

Every task's requirements implicitly include this section.

- **Single-writer rule.** Exactly one process — the current step's `stepN.py` on Windows — opens the PLCSIM Advanced API. No ROS node, no test, no helper script may open it, and two steps' writers must never run together.
- **Fail-safe direction.** On any exception, timeout or shutdown, boolean PLC inputs are written `False` and the vehicle command is zeroed.
- **The PLC program is ground truth.** Never change PLC logic, tags or addresses. Never invent a tag name. Tag names are case-sensitive and may contain hyphens (`E-Stop`).
- **PLCSIM instance name is `PLC_2`.** API DLL directory is `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0`. API error `-4` (`DoesNotExist`) means the instance is not running or the name mismatches — report it, never work around it.
- **STEP 1 ONLY: the bridge held `PF_OSSD=True`, `WF_Clear=True`, `ENC_A=0`, `ENC_B=0` every cycle**, because they were a precondition for `Motor` and not the subject. **Step 2 drives PF_OSSD and WF_Clear from the back scanner and Step 3 drives ENC_A and ENC_B from the drive shaft. Do not re-pin them: doing so silently disables both chains.**
- **Nothing is copied from the existing tree.** `sim/worlds/warehouse.sdf`, `agv/forklift/model.sdf`, `agv/forklift/config.yaml`, `agv/forklift/scripts/forklift_io.py` and `agv/forklift/scripts/sto_contactor.py` are used where they are, unmodified.
- **No topic name is a literal.** Every ROS and gz topic name is read from `agv/forklift/config.yaml` under `topics:`. The two exceptions, which that file does not own, are `/plc/status` and `/hmi/cmd_vel`.
- **Target < 150 lines per file.** Plain Python run with `python3`. No colcon package, no classes without need.
- **Every shell that runs `gz` must source `/opt/ros/jazzy/setup.bash` first.** There is no `/usr/bin/gz` on this machine.
- **Repo root in WSL:** `/mnt/c/Users/ozkan/projects/amr-agent`. On Windows: `C:\Users\ozkan\projects\amr-agent`.

## 3. PLC ground truth

Platform: TIA Portal, CPU 1516F-3 PN/DP, simulated in S7-PLCSIM Advanced.
The instance is started from the PLCSIM Advanced Control Panel by the owner.

**Instance name: `PLC_2`.** Confirmed by the owner on 2026-08-11. Three stale
names exist in the tree and none of them is the F-PLC under test:
`plcsim_api.py` says `v20`, `demo.sh`/`RUNBOOK.md` assume `safecell3`, and the
Step 1 brief said `PLC_1`. `m5-plc-debug/plc_bridge.py` is the file that agrees,
and its tag set matches the table below exactly.

If the API throws error `-4` (`DoesNotExist`), the instance is not running or
the name mismatches. Report it; do not work around it.

Access is through the PLCSIM Advanced Runtime API via pythonnet, 64-bit Python
on Windows. Known-good boilerplate:

```python
import sys, clr
sys.path.append(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0")
clr.AddReference("Siemens.Simatic.Simulation.Runtime.Api.x64")
from Siemens.Simatic.Simulation.Runtime import SimulationRuntimeManager, ETagListDetails
plc = SimulationRuntimeManager.CreateInterface("PLC_2")
plc.UpdateTagList(ETagListDetails.IOM)
plc.WriteBool("E-Stop", True); plc.ReadBool("Motor"); plc.WriteInt16("ENC_A", 0)
```

Facts about this simulation that are not obvious:

- API writes to inputs **persist across PLC cycles** — the API plays the role of
  the field devices. TIA watch and force tables cannot drive inputs; the API is
  the only way. Reading an input back returns the process image, which is valid.
- Fail-safe 1oo2 channel pairs collapse to a single process-image bit in
  simulation. F-DI discrepancy behaviour is not simulated.
- Tag names are case-sensitive and may contain hyphens (`E-Stop`).

### 3.1 Tag table (addresses fixed, never rename)

| Tag         | Addr    | Type | Meaning                                           |
|-------------|---------|------|---------------------------------------------------|
| E-Stop      | %I0.0   | Bool | True = healthy (NC chain closed), False = pressed |
| PF_OSSD     | %I0.1   | Bool | True = protective field clear (OSSD high), BACK scanner |
| WF_Clear    | %I0.2   | Bool | True = warning field clear, BACK scanner          |
| PF_OSSD_right | %I0.3 | Bool | True = RIGHT protective field clear (added 2026-08-12) |
| WF_Clear_right | %I0.4 | Bool | True = RIGHT warning field clear (added 2026-08-12) |
| PF_OSSD_left | %I0.5  | Bool | True = LEFT protective field clear (added 2026-08-12) |
| WF_Clear_left | %I0.6  | Bool | True = LEFT warning field clear (added 2026-08-12) |
| Acknowledge | %I15.0  | Bool | Reset button, rising edge required                |
| ENC_A       | %IW100  | Int  | Encoder channel A, mm/s                           |
| ENC_B       | %IW102  | Int  | Encoder channel B, mm/s                           |
| Motor       | %Q9.0   | Bool | Drive enable from the safety program (the output) |
| CASE_B0     | %Q9.1   | Bool | Monitoring-case bit 0                             |
| CASE_B1     | %Q9.2   | Bool | Monitoring-case bit 1                             |
| V_Limit     | %MW100  | Int  | Speed ceiling mm/s, computed in standard OB1      |

### 3.2 Safety program behaviour (already implemented and validated in TIA)

- Three ESTOP1 instances: e-stop button, protective field, speed/encoder
  monitor (cross-check `|ENC_A - ENC_B| > 50` → fault; ceiling 2800 mm/s).
  `Motor` is the AND of all three enables.
- **2026-08-12: the owner added ESTOP1 instances for the right and left
  scanners** (`PF_OSSD_right` → `#pf_right`, `PF_OSSD_left` → `#pf_left`)
  and configured `WF_Clear_right`/`WF_Clear_left` on the F-DI. How they
  compose into `Motor` and `V_Limit` is TIA-side and not yet verified from
  a live run. In the owner's screenshot both new instances show `ACK`
  wired to a literal `false` (Instance_1 uses `"Acknowledge"`), which with
  `ACK_NEC=true` would keep their Q False forever.
- ESTOP1 semantics: **a demand latches.** The input returning to healthy does
  *not* re-enable; a rising edge on `Acknowledge` is required. `ACK_NEC=true`
  also means one `Acknowledge` is required after PLC startup before `Motor` can
  ever be True.
- For `Motor` to be True, all of these must hold: `E-Stop=True`, `PF_OSSD=True`,
  encoder channels plausible (equal, < 2800), and an `Acknowledge` edge after
  the last demand. **`WF_Clear` is NOT among them.** Measured, not assumed:
  `step2/PROOF.md` and `step3/PROOF.md` both record `Motor=True` while
  `WF=False`. It gates `V_Limit`, and through it the speed monitor — not the
  enable directly.
- Case bits binary-encode monitoring case 1..3 (01/10/11); pattern 00 is
  deliberately invalid and decodes to 0, which the vehicle maps to case 3,
  the largest field. **`V_Limit` is 1500 when `WF_Clear` else 300, and that
  path is LIVE:** `step3/PROOF.md` records the vehicle stopped 0.68 s after
  enable, at 0.5 m/s commanded with racks 1.75 m away, because `WF_Clear`
  went False and the speed monitor demanded a stop above 300 mm/s. Anything
  commanding speed near racking meets this.

## Port map

| Port | Direction | Payload | Step |
|---|---|---|---|
| 5100 | Windows -> WSL | {"estop_healthy","motor","case","ts"} | Step 1, `case` added in Step 2 |
| 5101 | WSL -> Windows | {"pf","wf","pf_right","wf_right","pf_left","wf_left","enc_a","enc_b","ts"} | Step 2, encoders added in Step 3, right/left scanners added 2026-08-12 |
