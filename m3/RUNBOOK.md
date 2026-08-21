# M3 runbook — the fixed-equipment I/O loop, runnable today

This is the 2026-07-28 gate, re-runnable **without PLCSIM Advanced** (the
trial expired). The CPU seat is filled by the virtual PLC —
`m5/m5_ver1/virtual_plc/`, which since 2026-08-21 also runs
`FB_DemoCellControl` (`demo_cell_program.py`, transliterated from
`plc/demo-cell/SPEC.md` §7) and serves the §9 subtree. Everything else is
the tree as the gate ran it: `sim/launch/cell_bringup.launch.py`,
`bridge/` with the cell group, `bridge/tools/cell_stimulus.py`.

> **Historical note.** In 2026-07 the cell's CPU was a CPU 1513-1 PN named
> `PLC_1` serving **only** the `DemoCell` subtree. The virtual PLC serves
> both eras' subtrees from one process (the M3 cell program and the M5
> vehicle project); which era a run meets is decided by which subtree its
> clients configure. The cell program's link half (`BridgeLinkOk`) keeps the
> home it had in the M5 project — the companion fragment at the head of
> `standard_program.py`'s scan — so one tag still has exactly one writer.

## What you need

- **Windows side**: Python 3 with `asyncua` (the virtual PLC's only
  dependency beyond the stdlib).
- **WSL side**: ROS 2 Jazzy, the bridge venv (`~/amr-bridge-venv`, the one
  `bridge/README.md` pins — it must import both `rclpy` and `asyncua`), and
  Gazebo (Harmonic) as every sim run needs.

## 1. Start the CPU (Windows)

```powershell
python m5\m5_ver1\virtual_plc\virtual_plc.py
```

A **fresh** start matters if you want the boot signature in the exercise
(the link-loss latch that stands from CPU start until the first monitored
reset). A warm CPU skips those two lines — the exercise says so and tells
you why. Leave the process running; it is yours to stop, as PLCSIM was.

## 2. Bring up the Linux side (WSL)

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
./m3/run_cell.sh start
```

This probes for the virtual PLC (reading the Windows host address from the
default route, never assuming it), renders `m3/bridge.cell.virtual.yaml`
into `m3/runtime/` with that endpoint, and starts:

1. the cell world (headless Gazebo + the `ros_gz_bridge` for the cell's
   seven signals),
2. the bridge with the **cell** group (the group never left the code —
   `amr_bridge/config.py`'s `CELL_GROUP`; the committed live config simply
   stopped carrying it when the forklift group arrived),
3. the panel at rest (`cell_stimulus.py`'s default script — both stop
   circuits closed, both buttons released, republished at 1 Hz, so the
   bridge's startup rule R3 can close).

`start` returns when it reads **R3 satisfied** in the bridge log — the same
proof the 2026-07 runbook waited for. `./m3/run_cell.sh status` shows what
is up.

## 3. Run the gate exercise (WSL)

```bash
source /opt/ros/jazzy/setup.bash
~/amr-bridge-venv/bin/python m3/verify_cell.py
```

The script takes the panel over from the resting stimulus and drives the
gate, end to end, in about 40 seconds:

- the boot signature: `CellResetRequired` TRUE (the boot link-loss latch),
  `CellProcessStopActive` FALSE — no process stop from DB start values
  (SPEC §6.1's corrected polarity);
- the monitored reset clears the latch;
- one full cycle: start edge → transport at +0.15 m/s → the product
  observed at the beam (`ProductPresentAtSensor`, with
  `/cell/product_box/pose` ground truth ≥ 1 m of travel) → 2 s dwell →
  return at −0.15 m/s → home within the 0.05 m window → cycle complete;
- a process stop mid-transport: the latch, the zeroed command, the dead
  cycle;
- healing the contact resumes **nothing**; the monitored reset clears the
  latch; the cycle stays down — no automatic resume.

Every line is a PASS/FAIL verdict; the run also writes a time-series CSV to
`m3/evidence/`. Exit code 0 means every counted line passed. On a warm CPU
the two boot lines print SKIP (the fresh-CPU run and the unit tests pin
them), and if the belt sits away from home the exercise first drives the
SPEC §5 re-home branch and reports it.

If you would rather drive the panel by hand: leave `verify_cell.py` aside
and script `bridge/tools/cell_stimulus.py` yourself — its docstring shows
the vocabulary. The PLC-side watch table is `bridge/tools/observe_plc.py`
pointed at the same endpoint.

## 4. Tear down

```bash
./m3/run_cell.sh stop
```

Then stop the virtual PLC on Windows (Ctrl+C in its console, or close the
window). `m3/runtime/` holds the logs and the rendered config; nothing
outside `m3/` is written except the bridge's evidence CSV (which lands in
`m3/evidence/` by the config's own relative-path rule).

## What this runbook does NOT reproduce

- **The 46.163 ms latency figure** is a 2026-07-28 measurement against
  PLCSIM Advanced's virtual NIC (`plc/demo-cell/evidence/`,
  `bridge/EVIDENCE_LATENCY.md`). Tonight's path is WSL→localhost Python;
  the number will differ and means nothing about the recorded one. The
  bridge still writes its per-session latency CSV (`m3/evidence/`), so the
  loop's timing is observable — it is just not the M3 figure.
- **The four signal-loss cases** of `EVIDENCE_SIGNAL_LOSS.md` were bridge
  and CPU kills against PLCSIM. The program logic they exercised is pinned
  by `m5/m5_ver1/virtual_plc/test_demo_cell.py` (14 unit tests) and the
  boot/stop/reset lines of the gate exercise; the network-failure timing is
  not re-measured here.
