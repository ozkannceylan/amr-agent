# m5-ver3 operator runbook

This is the file you run from. Branch `cursor/m5ver3`. One truck, one
warehouse, Nav2 + dock + pallet. Isolation: `GZ_PARTITION=m5v3`,
`ROS_DOMAIN_ID=97`.

**Not in this stack (do not start them for this test):** PLCSIM
Advanced / `PLC_2`, the m5_ver2 HMI sketch, the m6 fleet. m5-ver3 never
opens the F-PLC. `/speed_limit` is the empty envelope slot; `--monitor`
is a software guard at 1.80 m, not a safety PLC.

---

## 1. Start (the product)

Gazebo window + AMCL + Nav2 (Smac Hybrid / MPPI / tricycle BT) + S5
dock + pallet. About **90 s**. From Windows PowerShell:

```powershell
wsl -e bash -lc "cd /mnt/c/Users/ozkan/projects/amr-agent && ./m5_ver3/m5v3.sh start --localize amcl --nav --dock"
```

Already in WSL:

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
./m5_ver3/m5v3.sh start --localize amcl --nav --dock
```

First time only, if `start --dock` refuses a missing detector:

```bash
bash m5_ver3/tools/install_apriltag.sh
```

Wait until the script prints `up.` and `Pallet attach:`. The first
`ekf_health: REFUSED` line is a DDS race; the next line should be
`ekf: healthy`. Do not stop and restart for that alone.

Optional software guard (not an F-PLC; sees nothing below 1.80 m):

```bash
./m5_ver3/m5v3.sh start --localize amcl --nav --dock --monitor
```

Headless (no window; same autonomy): add `--headless` before the other
flags.

---

## 2. Confirm it is the Nav2 stack

```bash
./m5_ver3/m5v3.sh status
```

You want: `22 alive, 0 dead` without `--monitor`, **or** 23 with it.
Lines that must say on:

| line | meaning |
|---|---|
| `loc amcl@…` | map → odom is AMCL |
| `nav on@…` | planner + MPPI + tricycle BT |
| `dock on@…` `docking on@…` | AprilTag + `opennav_docking` on `/cmd_vel` |

If `nav=off` you started without `--nav`. Stop and start again with the
command in §1.

---

## 3. Tests (pick one)

Every test below is a **new WSL shell**. Source ROS and isolation first:

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
export ROS_DOMAIN_ID=97 GZ_PARTITION=m5v3 PYTHONUNBUFFERED=1
set +u; source /opt/ros/jazzy/setup.bash; set -u
```

From Windows, wrap the python line in `wsl -e bash -lc 'cd /mnt/c/Users/ozkan/projects/amr-agent && …'` after those exports.

### A. Nav2 drive — ~1 min

Spawn → north ring junction. Success is `status 4` `error_code 0`.

```bash
python3 m5_ver3/tools/drive_goal.py record --goal spine_north
```

A `NO PROGRESS` here is the named `ring_corner` miss. Stop, start §1,
try once more. Do not force the truck with `set_pose` and call it Nav2.

### B. Nav2 into S5 staging — ~1 min

```bash
python3 m5_ver3/tools/drive_goal.py record --case stage_s5
```

Arrival is a 0.60 m **position** box. Heading at rest is often not
camera-on-tag. That is why dock uses `dock_bench.py stage` first.

### C. Plugin dock from staging — ~1 min

```bash
python3 m5_ver3/tools/dock_bench.py stage
python3 m5_ver3/tools/dock_bench.py record --from-staging
```

Success prints `success True` `error 0`.

### D. Pallet pick / lift / drop (seated) — ~1 min

Plugin heading is not `attach_ok`. Pickup is from the docked pose:

```bash
python3 m5_ver3/tools/pallet_bench.py seat
python3 m5_ver3/tools/pallet_bench.py attach
python3 m5_ver3/tools/pallet_bench.py lift
python3 m5_ver3/tools/pallet_bench.py lower
python3 m5_ver3/tools/pallet_bench.py detach
```

### E. Full dry cycle ×3 — ~13 min

Nav2 empty legs; laden motion is `/cmd_vel`. Empty Nav2 `no_progress`
is recovered to staging.

```bash
python3 m5_ver3/tools/pallet_cycle.py run
```

Done looks like: `done      3 cycles -> …/pallet-cycle-…`

### F. The film — one cycle, four cameras — ~8 min

**Run it on a `--headless` stack.** The Gazebo window client costs
two-thirds of the real-time factor on this rig (RTF 0.9995 headless
against 0.15–0.5 windowed, measured 2026-08-30/31), and the cycle's
`/cmd_vel` bursts are timed on the WALL clock — at RTF 0.3 the truck
moves a third of the commanded distance and the cycle geometry falls
apart. The film cameras render server-side; the window adds nothing.

```bash
python3 m5_ver3/tools/film_run.py record
python3 m5_ver3/tools/film_run.py cut
```

`record` places the cameras, starts one recorder per camera plus the
truck's own, then **holds twice `film.lead_s` of wall time before the
cycle** so the establishing shot is footage rather than luck — the
cameras run on the sim clock, and twice the wall is at least the lead
at any real-time factor this rig has shown. `cut` writes
`m5_ver3/logs/film/film-<stamp>/m5v3-film.mp4`: the wide establishing
shot — `film.lead_s` of it, or as much as the wide recording holds,
and the printed `lead` line says which — every leg on the camera the
shot table names, and the truck's own camera inset over the approach
— the AprilTag growing in frame is the proof the dock is tag-driven.

---

## 4. Stop

```bash
./m5_ver3/m5v3.sh stop
```

Kills only partition `m5v3`. A Gazebo in `m6` survives this on purpose.

---

## 5. What you are looking at

| You asked for | What this start actually is |
|---|---|
| Autonomous driving | Nav2: SmacPlannerHybrid + MPPI Ackermann + tricycle BT (no Spin, no BackUp). Nav2 forward is this truck's reverse (forks at model −x). |
| HMI / sim view | Gazebo client (`gz sim -g`) when you omit `--headless`. There is no operator panel in `m5_ver3/`. |
| Virtual F-PLC | **Not here.** Do not start PLCSIM. Envelope topic `/speed_limit` is wired and idle until something publishes. Collision monitor (`--monitor`) is not a safety PLC. |
| Dock + pallet | `--dock`: marker + pallet spawned, AprilTag, `DockRobot` on `/cmd_vel`. |

Offline tests (no Gazebo): `python -m pytest m5_ver3/tests -q` on Windows
or WSL. Suite was **1021 passed** at F5 close.

---

## 6. If start refuses

| print | fix |
|---|---|
| GPU / renderer | NVIDIA must be the GLX renderer. Close other gz worlds. |
| `apriltag_ros is vendored` | `bash m5_ver3/tools/install_apriltag.sh` |
| `--dock was given with --nav` | you omitted `--nav` |
| `--nav` without `--localize` | add `--localize amcl` |
| children DEAD after `up.` | `./m5_ver3/m5v3.sh status` then `stop` and start §1 again |
