# RUNBOOK — the first M5 build (the Claude-supervised stack)

This is the runbook for **M5 ver1**: the layered stack (`agv/`, `sim/`,
`bridge/`, `hmi/`, `fleet/`, `viz/`, `plc/`) as it was built under Claude
supervision and recorded on video in August 2026. It has two ways to run:

- **The virtual path (2026-08-21, works today).** The PLCSIM Advanced trial
  has expired, so the CPU seat is filled by
  [`virtual_plc/virtual_plc.py`](virtual_plc/virtual_plc.py) — a software
  stand-in serving the same address space, the same boot signature and the
  same writer surface. **It is not a PLC and carries no safety integrity.**
  Everything below except §H is this path.
- **The recorded path (historical).** PLCSIM Advanced + TIA Portal +
  `bridge/standin_writer/standin_writer.ps1`, exactly as the videos were
  made. Kept in §H for the record; it needs a licensed PLCSIM Advanced.

The WSL half is identical in both paths. The archived entry script
[`.archive/demo.sh`](../../.archive/demo.sh) is frozen as recorded; the
virtual path uses [`demo.sh`](demo.sh) in this folder — the archived script
with five marked changes (its header lists them).

---

## 1. Prerequisites

- **WSL** with ROS 2 Jazzy (`/opt/ros/jazzy/setup.bash`), Gazebo (via the
  ROS overlay), and the two venvs: `~/amr-bridge-venv`, `~/amr-hmi-venv`.
- **Windows:** Python 3.12+ with `asyncua` (`pip install asyncua`) for the
  virtual PLC. No Siemens software needed in this path.
- Nothing else may hold the writer's mutex or ports: no second
  `virtual_plc.py`, no `standin_writer.ps1`, nothing listening on 45015,
  45016 or 4841.

## 2. Up

**Windows side first.** Open a terminal in the repo and leave it open — it
is the operator keyboard for e-stop, zone and reset:

```powershell
python m5\m5_ver1\virtual_plc\virtual_plc.py --command-file C:\Temp\m5v1_cmds
```

(Create `C:\Temp\m5v1_cmds` empty first if it does not exist. Without
`--command-file`, only the console takes commands. `--no-console` disables
the console, e.g. for scripted runs.)

**WSL side:**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent/m5/m5_ver1
bash demo.sh check     # the Windows-side pre-flight only
bash demo.sh up        # add --headless when no display is wanted
```

`check`/`up` probe the Windows side, never assume it: the virtual PLC is
accepted where PLCSIM's runtime process used to be (its OPC UA listener on
4841), plus the writer's own definition of itself — the named mutex
`Global\amr-standin-writer` and the listeners on 45015/45016. The proof that
a CPU is actually answering is unchanged: the bridge establishing its
session.

Unless `AMR_BRIDGE_CONFIG` / `AMR_HMI_CONFIG` are set, `up` generates both
configs into the runtime dir (`/tmp/amr-agent-demo/`) from the committed
ones, substituting the endpoint for the Windows host address read back from
the WSL default route, port 4841. No committed file is edited.

`up` reports READY with the controller's own boot table read over OPC UA.
Expect: **TorqueOffDemand TRUE, EStopDemand TRUE, ZoneStopDemand TRUE,
SafetyResetRequired TRUE** — the recorded boot signature. The vehicle is
torque-off until the monitored reset. That is intended, not a fault.

## 3. The monitored reset (both hands, or it is refused)

1. Writer window (or command file): `estop close`
2. HMI page: release **PROCESS STOP**
3. Together: `reset pulse 2000` at the writer **and** hold the HMI **RESET**
   button across the same two seconds

Refusals are the F-program's, reproduced by the model: a press shorter than
200 ms never arms; longer than 3 s is a fault; a press the CPU never saw
open is a fault; and a reset while any cause stands clears nothing. If
`WarningFieldOccupied` reads True, clear the warning field first.

Headless equivalent (what [EVIDENCE.md](EVIDENCE.md) §4 ran):

```bash
python /mnt/c/Users/ozkan/projects/amr-agent/m5/m5_ver1/drive_demo.py \
    --command-file C:\Temp\m5v1_cmds        # from Windows; drives reset + a 0.3 m/s move
```

## 4. Drive

Operator page: <http://127.0.0.1:8088/> — select **TELEOP**, hold the
deadman, drive. The command path is HMI → (virtual) PLC → bridge → Gazebo;
the safety chain is onboard and appears in no launch file. The HMI section
of [`README.md`](README.md) explains the page.

The writer's console (or command file) takes the field devices' side:
`estop open|close`, `zone open|close` (refused while the field-evaluation
link owns the channel), `reset press|release`, `reset pulse <ms>`,
`status`, `quit`.

## 5. Down

```bash
bash demo.sh down
```

Stops the WSL components in reverse order, sweeps survivors by this run's
`GZ_PARTITION`, stops the ros2 daemon, sweeps `/dev/shm`, then stops the
virtual PLC on the Windows side (matched by command line, like the writer
before it) and verifies the mutex is free and both writer ports are closed.
`down --keep-writer` leaves the virtual PLC running for a second take.

If the vehicle stopped nose-to-rack and cannot reverse out of its own
field: `bash demo.sh home` teleports the model to spawn. It clears no
latch — the monitored reset is still the only way back to motion.

---

## H. The recorded path (historical — needs PLCSIM Advanced)

How the videos were made, frozen for the record:

1. **Windows:** PLCSIM Advanced instance running, TIA project downloaded,
   CPU in RUN. Then the stand-in writer, in its own PowerShell window:
   `powershell -ExecutionPolicy Bypass -File bridge\standin_writer\standin_writer.ps1 -Instance <name>`
   (the instance name is tool-derived — read it from the PLCSIM Advanced
   control panel; `safecell3` was this era's).
2. **WSL:** `./.archive/demo.sh up` — the frozen script. Its pre-flight
   requires the PLCSIM runtime process *and* the writer's mutex and
   listeners.
3. Drive as §3–§4. Down: `./.archive/demo.sh down`.

Everything the frozen script expects still exists except a licensed PLCSIM
Advanced. That is the only difference the virtual path repairs.

## Files in this folder

| File | What it is |
|---|---|
| [`demo.sh`](demo.sh) | The archived demo script + five marked virtual-PLC-era changes |
| [`drive_demo.py`](drive_demo.py) | The headless replay of the demo's first two minutes |
| [`virtual_plc/`](virtual_plc/) | The software CPU: models, server, tests, smoke test |
| [`EVIDENCE.md`](EVIDENCE.md) | The 2026-08-21 runs, transcribed |
| [`PLC-PROGRAM.md`](PLC-PROGRAM.md) | Why this controller could not be used, and ver2's motivation |
| [`assets/`](assets/) | The recorded videos, GIFs and HMI stills |
