# m5-ver3 — what this build is

The **sensor-fusion showcase vehicle**. One forklift, real instrument
profiles, an estimate that is scored against ground truth rather than
handed it. Owner decision **AMR-DEC-003** (vault, 2026-08-25); branch
`m5-ver3`; phase ledger `tasks/TODO.md` § *m5-ver3*; the research it is
built on is `docs/reports/m5v3-01..04.md` (SLAM/localisation SOTA, Nav2
for a tricycle, simulation realism and cameras, fusion architecture).

It is **not** a fleet. M6 is the fleet and stays the fleet: four trucks,
VDA 5050, a manager, a floor, a PLC. This track takes M6's plant back
down to ONE truck so that everything the vehicle *perceives* can be made
honest — and whether any of it ever rejoins the fleet is a separate
decision, not an assumption in this tree.

---

## What it inherits, and how

| Thing | Where it comes from | How |
|---|---|---|
| The floor | `m6/gazebo/warehouse_ver3.sdf` | **By reference.** Never copied, never edited. |
| The vehicle | `m6/gazebo/forklift_ver2/model.sdf` | **Forked** into `gazebo/forklift_ver3/model.sdf` — byte-identical but for the model name and a provenance header. |
| The spawn pose | `m6/ipc/status_contract.py` `VEHICLES["f1"]` | Copied into `config.yaml` as a value, with the floor check that validates it (see below). |

**Why the floor is referenced and the vehicle is forked.** Two files that
start identical and then drift are two files, and a figure measured on
one of them is a claim about neither. The floor will not drift — this
track has no reason to move a rack — so it is read where it lives. The
vehicle *will* drift, and hard: phase F1 replaces its ideal sensors with
instrument profiles and takes the ground-truth odometry away. m6's
published figures are measured on `forklift_ver2`, so that file is not
this track's to touch.

**Nothing outside `m5_ver3/` is modified by this track.** Not `m6/`, not
`m5_ver2/`, not `m5/`, `agv/`, `sim/`, `plc/`, `hmi/`, `fleet/`,
`bridge/` or `docs/adr/`. Reading them is expected; writing to them is
not.

---

## The two rules the scripts enforce

### 1. Isolation — this stack cannot join, or be joined by, another

| | m5-ver3 | m6 | step5 |
|---|---|---|---|
| `GZ_PARTITION` | **`m5v3`** | `m6` | `m5demo` |
| `ROS_DOMAIN_ID` | **`97`** | `96` | — |

Both are set on every child. `GZ_PARTITION` is the one that scopes
**Gazebo** — gz transport is not DDS, so `ROS_DOMAIN_ID` isolates only the
ROS side — and it is also what decides **what `stop` may kill**:
`m5v3.sh`'s `ours()` reads a candidate process's own environment and the
sweep skips anything that does not carry `GZ_PARTITION=m5v3`. Measured
(EVIDENCE_BRINGUP.md 6): a gz server running in partition `m6` is
nominated by the same command-line pattern and survives an `m5v3.sh stop`
untouched.

Neither value is overridable from the environment. They live in
`config.yaml` and are read by `start`, `stop` and `status` alike, so the
three cannot disagree about which graph this is.

### 2. The GPU is mandatory, and the refusal is the point

Every launch exports

```
GALLIUM_DRIVER=d3d12
MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
```

and then **refuses to start anything at all** unless `glxinfo -B` reports
a renderer naming NVIDIA. Measured on this rig: without the exports the
renderer is `llvmpipe (LLVM 20.1.2, 256 bits)`; with them it is
`D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`.

There is no CPU fallback and there must never be one. Software
rasterisation does not fail — it measures a *different machine*, and
every figure taken under it wears this rig's name while describing
something else. A render problem is diagnosed, never downgraded.

---

## The tree

```
m5_ver3/
├── CONTEXT.md            this file
├── EVIDENCE_BRINGUP.md   Task 1's measured numbers, instrument by instrument
├── config.yaml           every constant the scripts obey - the one home
├── m5v3.sh               start [--headless] | stop | status
├── gazebo/
│   └── forklift_ver3/
│       └── model.sdf     the forked vehicle
├── logs/                 one file per child, by name (git-ignored)
└── tools/
    ├── _common.sh        sourced: refuse(), the config reader, source_ros()
    └── rtf_probe.sh      real-time factor of the RUNNING world
```

**`config.yaml` is the one home for every constant.** No behavioural
number is written inline in a script on this track. A partition, a pose,
a topic or a timing budget that has to move moves there, once, and both
scripts move with it.

**`m5v3.sh` orchestrates processes and holds no logic of its own.** Every
child writes its own log under `logs/`, named for the child, and `status`
reports the same children back by name with ALIVE or DEAD. Every refusal
names the check that failed and the file that owns the answer it tested
against — including a child that died on its way up, which is a refusal
with a non-zero exit and not a warning printed above the word "up."

**`tools/_common.sh` is sourced, never executed.** It is the three things
both scripts do before they can do anything of their own: `refuse()` in
one voice, one reader of `config.yaml` that checks required keys by their
dotted names, and `source_ros()`. Two copies of a mechanism drift exactly
the way two copies of a value do.

---

## Running it

The rig is **WSL Ubuntu 24.04**, ROS 2 Jazzy at `/opt/ros/jazzy`,
gz-sim 8.11.0. The repository is visible inside WSL at
`/mnt/c/Users/ozkan/projects/amr-agent`. From Windows:

```bash
wsl -e bash -lc 'cd /mnt/c/Users/ozkan/projects/amr-agent && ./m5_ver3/m5v3.sh start'
```

| Command | What it does |
|---|---|
| `m5v3.sh start` | GPU preflight, then the world, one `forklift_ver3`, the bridge and a Gazebo **window**. |
| `m5v3.sh start --headless` | The same without the window. **Use this for anything being measured** — every figure in `EVIDENCE_BRINGUP.md` was taken this way. |
| `m5v3.sh status` | Each child by name, ALIVE or DEAD, with its log. Exit 0 only if every one is alive. |
| `m5v3.sh stop` | Ends this partition's stack, and nothing else. |
| `tools/rtf_probe.sh` | 30 s real-time-factor sample of the world that is already running. |

`start` exits **non-zero** if any child died during startup, naming the
child and its log; what survived is left running, because the operator's
next command is `stop`.

Three processes at Task 1: the gz server, the `ros_gz_bridge`, and the
GUI client when there is one. **No broker, no fleet manager, no HMI, no
PLC link** — that absence is the phase, not an omission. Nothing here
touches PLCSIM Advanced or anything on the Windows side.

### What is bridged, and one word about odometry

| Topic | Direction | Rate |
|---|---|---|
| `/clock` | gz → ROS | 500 Hz |
| `/forklift/gz/odom` | gz → ROS | 20 Hz |
| `/forklift/gz/scan_nav` | gz → ROS | 10 Hz |

`/forklift/gz/odom` is the model's `OdometryPublisher` — **ground truth,
and a measurement reference ONLY**. No wheel slip, no encoder
quantisation, no drift. On this track it is an *instrument*, never an
input: phase F1 deletes it from the model and replaces it with wheel
odometry through an EKF, and until then anything that *navigates* on it is
measuring its own answer. The bridge line in `m5v3.sh` says so where it
is opened.

---

## Two things worth knowing before the next phase

**A spawn pose has to be checked against the floor, not against the map.**
Task 1 was handed the pose `(-3.00, -5.50)` and measured it spawning the
truck's forks 0.875 m inside a rack leg: that pose belongs to
`warehouse_ver2`, and M6.6's relayout put `RackSW3` across it. The model's
forks reach `x = -1.875` in its own frame, and *that* number — not the
look of the floor plan — is what a candidate pose has to clear.
`EVIDENCE_BRINGUP.md` 5 carries the whole measurement.

**DDS discovery on this rig has failed before.** Mid-session on
2026-08-25 the WSL multicast path died and FastDDS discovery went with it;
m6 works around it with a unicast profile at `m6/tools/fastdds_loopback.xml`
(exported as `FASTRTPS_DEFAULT_PROFILES_FILE`). This track does **not**
carry one — a bare `ros2 topic pub` / `echo` pair was verified working on
domain 97 before Task 1's measurements, and three participants is a long
way from the ~40 that made m6's default initial-peer range too small. If
bridged topics start going missing at boot, that file is the first thing
to try, not a mystery.
