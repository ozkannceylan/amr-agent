# M4 Runbook — the forklift commissioning cell, runnable today

This is the **today-working** path for the Milestone-4 gate: the forklift
arena in Gazebo, the I/O translator, the obstacle zone, the bridge and the
commissioning HMI, all against the **virtual PLC** — no PLCSIM Advanced,
no TIA Portal, no GUI. The five gate criteria of `README.md` are exercised
end-to-end and self-checked.

The historical path (`.archive/stack.sh` + PLCSIM Advanced + the T5
watch-table rehearsal) is preserved in `README.md` and
`sim/scenarios/forklift_commissioning.md`. This runbook replaces none of
that history; it makes the cell runnable after the PLCSIM trial expired.

## What you need

| Prerequisite | Check |
|---|---|
| Windows 11 + WSL2 with ROS 2 Jazzy and Gazebo | `wsl -e bash -c "source /opt/ros/jazzy/setup.bash && which gz sim"` |
| The bridge's Python venv in WSL | `ls ~/amr-bridge-venv/bin/python` |
| The HMI's Python venv in WSL | `ls ~/amr-hmi-venv/bin/python` |
| Python 3 on Windows with `asyncua` | `python -c "import asyncua"` |
| Repo at `C:\Users\ozkan\projects\amr-agent` | this file's grandparent |

## 1. Start the CPU (Windows)

```powershell
python m5\m5_ver1\virtual_plc\virtual_plc.py --no-console --command-file C:\Temp\m4_cmds
```

Leave it running. It serves OPC UA on port 4841 and takes the e-stop /
zone / reset devices from the command file — the same stand-in M3 and
M5 ver1 use, documented in `m5/m5_ver1/virtual_plc/README.md`.

**The CPU in force is the later build.** The M4 CPU ran the standard
program alone; the virtual PLC runs the M5-commissioned build, whose
section-7 core *is* the M4 program. What the operator notices: the boot
demands and their monitored reset, and the mode-entry handshake, are
F-program behavior M4 never had. The exercise names these as the M5-era
additions they are.

## 2. Bring up the cell (WSL)

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
./m4/run_commissioning.sh start
```

The script probes the Windows host for the virtual PLC, renders
`m4/bridge.forklift.virtual.yaml` and the HMI config into `m4/runtime/`,
then starts, in order: the headless arena with the forklift spawned,
`forklift_io.py`, `obstacle_zone.py`, a publisher holding the warning
field clear (the commissioned CPU reads it; the M4 CPU never had one),
the bridge, and the HMI on `http://127.0.0.1:8088`. It waits for the
bridge's startup rule R3 before declaring success.

`./m4/run_commissioning.sh status` shows what is up;
`./m4/run_commissioning.sh stop` tears the WSL side down (the virtual
PLC on Windows is yours to stop, as PLCSIM was).

## 3. Run the gate exercise (Windows)

```powershell
python m4\verify_commissioning.py --command-file C:\Temp\m4_cmds
```

Twelve checks, all through the operator's own surfaces:

1. **Boot signature** — the F-program's demands stand (the M5-era CPU's
   signature, named as such).
2. **The monitored reset** — e-stop and zone closed, process stop
   released, the reset edge through the command file: every demand and
   latch clears.
3. **Mode entry** — the arbiter takes TELEOP (section 14.8, the M5
   addition).
4. **(a) Teleop drive** — the vehicle moves under the PLC's setpoint.
5. **(b) The fork** rises on command to the soft travel limit, which
   zeroes the setpoint while the demand stands.
6. **(c) The speed cap** — fork above 0.50 m, traction capped at
   0.30 m/s, the limit lamp on; the cap lifts when the fork comes down.
7. **(d) The obstacle latch** — the T5.4 crate at the aisle home, a drive
   into the stop zone: latch, teleop override, zeroed setpoints; the
   reset is **refused while the cause stands**; crate clear plus a fresh
   edge clears everything with no auto-resume.
8. **(e) The HMI's heartbeat** — the HMI is killed mid-drive; the PLC's
   own link verdict drops and the setpoints die, read directly off the
   PLC over OPC UA (the watch table's role).

Expected tail:

```
COMMISSIONING PASS: 12/12 checks passed
```

A warm-CPU re-run (the virtual PLC outlived the stack) skips the boot
check by design; the reset prelude is idempotent. `m4/EVIDENCE.md`
records a fresh-CPU 12/12 run.

## 4. Teardown

```bash
./m4/run_commissioning.sh stop        # WSL side
```

then stop the virtual PLC on Windows (Ctrl-C or close the window).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `virtual PLC did not answer` | the CPU from step 1 is not running, or Windows Firewall is eating the WSL→Windows connection | start it; allow python.exe on port 4841 |
| `bridge startup rule R3` never satisfies | the arena or `forklift_io` died | `status`, then read `m4/runtime/*.log` |
| `(e)` fails with an OPC UA exception | the HMI was already dead, or the endpoint differs | the phase needs a live HMI at start; check `--plc-endpoint` |
| CRLF errors from `run_commissioning.sh` | the file was edited on Windows | `sed -i 's/\r$//' m4/run_commissioning.sh` |
| a stale `m4/runtime/*.pid` blocks start | a previous run crashed | `stop`, delete `m4/runtime/`, start again |
