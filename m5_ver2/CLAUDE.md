# m5_ver2

## Global Constraints

Every task's requirements implicitly include this section.

- **Single-writer rule.** Exactly one process — `step1.py` on Windows — opens the PLCSIM Advanced API. No ROS node, no test, no helper script may open it.
- **Fail-safe direction.** On any exception, timeout or shutdown, boolean PLC inputs are written `False` and the vehicle command is zeroed.
- **The PLC program is ground truth.** Never change PLC logic, tags or addresses. Never invent a tag name. Tag names are case-sensitive and may contain hyphens (`E-Stop`).
- **PLCSIM instance name is `PLC_2`.** API DLL directory is `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0`. API error `-4` (`DoesNotExist`) means the instance is not running or the name mismatches — report it, never work around it.
- **The bridge must hold `PF_OSSD=True`, `WF_Clear=True`, `ENC_A=0`, `ENC_B=0` every cycle**, or `Motor` can never energise.
- **Nothing is copied from the existing tree.** `sim/worlds/warehouse.sdf`, `agv/forklift/model.sdf`, `agv/forklift/config.yaml`, `agv/forklift/scripts/forklift_io.py` and `agv/forklift/scripts/sto_contactor.py` are used where they are, unmodified.
- **No topic name is a literal.** Every ROS and gz topic name is read from `agv/forklift/config.yaml` under `topics:`. The two exceptions, which that file does not own, are `/plc/status` and `/hmi/cmd_vel`.
- **Target < 150 lines per file.** Plain Python run with `python3`. No colcon package, no classes without need.
- **Every shell that runs `gz` must source `/opt/ros/jazzy/setup.bash` first.** There is no `/usr/bin/gz` on this machine.
- **Repo root in WSL:** `/mnt/c/Users/ozkan/projects/amr-agent`. On Windows: `C:\Users\ozkan\projects\amr-agent`.
- **Do not begin Step 2.** When Task 8 is done, print the validation checklist and stop.

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
| PF_OSSD     | %I0.1   | Bool | True = protective field clear (OSSD high)         |
| WF_Clear    | %I0.2   | Bool | True = warning field clear                        |
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
- ESTOP1 semantics: **a demand latches.** The input returning to healthy does
  *not* re-enable; a rising edge on `Acknowledge` is required. `ACK_NEC=true`
  also means one `Acknowledge` is required after PLC startup before `Motor` can
  ever be True.
- For `Motor` to be True, all of these must hold: `E-Stop=True`, `PF_OSSD=True`,
  encoder channels plausible (equal, < 2800), and an `Acknowledge` edge after
  the last demand. **Therefore the Step 1 bridge must constantly hold
  `PF_OSSD=True`, `WF_Clear=True`, `ENC_A=0`, `ENC_B=0`, or `Motor` can never
  energise.**
- Case bits binary-encode monitoring case 1..3 (01/10/11); pattern 00 is
  deliberately invalid. `V_Limit` is 1500 when `WF_Clear` else 300. Both are
  irrelevant to Step 1 and are consumed in later steps.

## Port map

| Port | Direction | Payload | Step |
|---|---|---|---|
| 5100 | Windows -> WSL | PLC state JSON {"estop_healthy","motor","ts"} @ 20 Hz | Step 1 |
| 5101 | WSL -> Windows | simulated sensors (distance, speed) | later |
