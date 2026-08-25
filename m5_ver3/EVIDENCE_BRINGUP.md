# EVIDENCE — m5-ver3 bringup (Task 1)

Every number below was measured on this rig on **2026-08-25**, and the
instrument that produced it is named beside it. Nothing here is quoted
from another tree's evidence file; where an m6 figure is mentioned it is
labelled as m6's and is there for comparison only.

**The rig.** WSL2 on Windows 11 · Ubuntu 24.04.4 LTS · kernel
`5.15.167.4-microsoft-standard-WSL2` · 13th Gen Intel Core i9-13900H,
20 threads · NVIDIA GeForce RTX 4050 Laptop GPU · gz-sim **8.11.0** ·
ROS 2 **Jazzy** · python3 3.12.3. Repository at
`/mnt/c/Users/ozkan/projects/amr-agent`.

**What was run.** `./m5_ver3/m5v3.sh start --headless`, `status`,
`tools/rtf_probe.sh`, `ros2 topic hz`, `stop` — and separately
`./m5_ver3/m5v3.sh start` with the window, against a decoy stack in
another partition. Nothing else was up on the machine during the
measurements; that was checked with `pgrep -af "gz sim|parameter_bridge"`
before each one.

---

## 1. The GPU preflight, and what it refuses

**Instrument:** `glxinfo -B`, run by `m5v3.sh`'s `gpu_preflight` before
anything is started. The whole reply is kept in
`m5_ver3/logs/gpu_preflight.log`.

| Environment | `OpenGL vendor string` | `OpenGL renderer string` |
|---|---|---|
| bare shell | `Mesa` | `llvmpipe (LLVM 20.1.2, 256 bits)` |
| `GALLIUM_DRIVER=d3d12`, `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` | `Microsoft Corporation` | **`D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`** |

So the two exports are not decoration: without them this WSL renders in
software and says so.

**The refusal was measured, not assumed.** `config.yaml`'s
`gpu.required_renderer` was temporarily set to `NoSuchGPU` and
`start --headless` run:

```
m5v3: REFUSED at check 'the renderer names NoSuchGPU'
      owned by: .../m5_ver3/config.yaml (gpu.required_renderer)
      renderer is: D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)
      ...
      NOTHING WAS STARTED. Do not work around this by rendering
      on the CPU: llvmpipe measures a different machine.
```

Exit status **1**, and `pgrep -af "gz sim|parameter_bridge"` immediately
afterwards returned nothing — the refusal happens before the first child.
The key was restored to `NVIDIA`.

---

## 2. What the simulator actually rendered on

`glxinfo` answers about the **GLX** path. gz renders its sensors through
OGRE-Next on **EGL**, so it is a different question, and `logs/world.log`
carries two lines that look like the wrong answer to it:

```
libEGL warning: egl: failed to create dri2 screen
libEGL warning: NEEDS EXTENSION: falling back to kms_swrast
```

**Instrument:** `~/.gz/rendering/ogre2.log` — OGRE-Next's own startup
report, which names the device it initialised. Read immediately after a
solo `start --headless` (19:01:44):

```
GL_VERSION  = 4.6 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2
GL_VENDOR   = Microsoft Corporation
GL_RENDERER = D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)
Device Name : D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)
```

The same four lines were measured on a probe server started **without**
`--headless-rendering` (18:45:33). Both paths land on the GPU; the two
`libEGL` lines are a first probe failing and being superseded, not the
path taken. They appear in `world.log` either way and are **expected
noise**.

This log is deliberately *not* an automated gate: it is one shared file
under `$HOME` that every gz process on the machine truncates and
rewrites, so with a concurrent m6 stack up it would answer about somebody
else's renderer. It is read by hand, here, beside a start with nothing
else running.

---

## 3. The truck is where the table put it

**Instrument:** `gz model -m forklift_ver3 --pose`, in partition `m5v3`,
sampled twice 20 s apart on the headless stack.

Spawn request: `(-17.00, 10.00, 0.05)` yaw `3.14159` — `config.yaml`'s
`vehicle.spawn`, which is `m6/ipc/status_contract.py` `VEHICLES["f1"]`.

```
- Pose [ XYZ (m) ] [ RPY (rad) ]:
  [-17.000000 10.000000 -0.000001]
  [0.000000 0.000000 3.141590]        <- t + ~15 s

- Pose [ XYZ (m) ] [ RPY (rad) ]:
  [-17.000000 10.000000 -0.000001]
  [0.000000 0.000000 3.141590]        <- t + ~35 s, unchanged
```

Against the **m6 Gate 1 criterion** — exact coordinates, zero roll and
pitch — this **passes**: x and y are the table's to six decimals, z is
1 µm below the floor after a 0.05 m drop, roll and pitch are zero, and
yaw is the requested heading. It is also *stationary*, which the second
sample is there to say.

**The nav lidar at rest.** Instrument: `gz topic -e -n 1 -t
/forklift/gz/scan_nav`. 211 of 360 rays return inside the 8.0 m
`range_max`; closest **1.287 m**, farthest **7.951 m**. The closest
return is the truck's own mast, by construction and not by luck: the nav
lidar sits at model `(0.55, -0.40, 1.80)` and the mast spans
`x ∈ [-0.83, -0.73]`, `|y| ≤ 0.36` up to `z = 2.05`, which is 1.33 m
away in the scan plane. **This is not a protective verdict** and must not
be read as one — a raw minimum over a rendered depth image is not a field
evaluation.

---

## 4. Real-time factor, headless

**Instrument:** `m5_ver3/tools/rtf_probe.sh` — 30 s of
`gz.msgs.WorldStatistics` off `/world/warehouse/stats` in partition
`m5v3`, sampled with `stdbuf -oL gz topic -e`. (`gz stats` is Gazebo
*classic*'s verb and does not exist on gz-tools for Harmonic; a probe
built on it would report nothing on a healthy sim.)

Measured against the stack `start --headless` brings up — server, one
truck, and the bridge **subscribed to the nav lidar, so that sensor is
being rendered**. That matters: gz renders a `gpu_lidar` only while
something is subscribed to its topic, and an RTF taken with nothing
listening is a physics-only number.

| Run | samples | mean | median | floor | ceiling |
|---|---|---|---|---|---|
| 1 | 296 | 0.9985 | 0.9999 | 0.9429 | 1.0399 |
| 2 | 296 | **0.9996** | **0.9999** | **0.9408** | 1.0706 |

Run 2 is the clean one and the figure to quote: run 1 was taken while a
stray `ros2 topic pub` from an earlier discovery check was still
publishing at 5 Hz on domain 97. The two agree to within the spread, so
that stray cost nothing measurable — it is disclosed because a figure
whose conditions were not exactly what they claim is not a figure.

296 samples over 30 s is **9.9 Hz** against the topic's nominal 10 Hz;
that rate sags with the RTF, so the sample count is itself a reading and
is printed with every mean.

**The window was not measured.** Every figure here is headless. m6
measured its own GUI cost on llvmpipe (mean 0.806 with the window against
0.998 without, floor 0.127 against 0.926) and that number is **m6's, on
software rendering** — it says nothing about this stack on the GPU, and
this file does not borrow it. If a windowed run is ever timed, it needs
its own probe.

---

## 5. Bridged topic rates

**Instrument:** `ros2 topic hz`, `ROS_DOMAIN_ID=97`, against the headless
stack, ~20 s per topic.

| Topic | Nominal | Measured | min / max interval | std dev | window |
|---|---|---|---|---|---|
| `/clock` | 500 Hz | **500.003** | 0.001 / 0.003 s | 0.00008 s | 5507 |
| `/forklift/gz/odom` | 20 Hz | **19.967** | 0.049 / 0.083 s | 0.00166 s | 411 |
| `/forklift/gz/scan_nav` | 10 Hz | **9.985** | 0.095 / 0.132 s | 0.00253 s | 208 |

All three carry their nominal rate: the odometry publisher is configured
at 20 Hz in the model, the nav lidar at 10 Hz, and the world steps at
500 Hz. `ros2 topic list` on domain 97 shows exactly these three plus
`/parameter_events` and `/rosout` — nothing else is bridged yet, and
nothing else should be until something consumes it.

`/forklift/gz/odom` is **ground truth and a measurement reference only**.
See CONTEXT.md; F1 removes it.

---

## 6. `stop` kills this partition and nothing else

**Instrument:** a **decoy** gz server, started by hand with
`GZ_PARTITION=m6 ROS_DOMAIN_ID=96` on m6's world. It stands in for a live
m6 stack — m6 was **not** running during these measurements, and starting
it was not this task's to do. What the decoy can prove is exactly what
matters: the sweep's patterns nominate it and `ours()` spares it.

```
decoy pid 23921, GZ_PARTITION=m6

$ ./m5_ver3/m5v3.sh start          # the GUI default
gpu: D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)
starting the m5-ver3 plant (partition m5v3, domain 97, gui true)
  world pid 24086
  spawning forklift_ver3 at (-17.00, 10.00, 0.05) yaw 3.14159
  bridge pid 24164
  gui pid 24172

$ ./m5_ver3/m5v3.sh status
  world    ALIVE   pid 24086   .../logs/world.log
  bridge   ALIVE   pid 24164   .../logs/bridge.log
  gui      ALIVE   pid 24172   .../logs/gui.log
3 alive, 0 dead.                                    (exit 0)

$ pgrep -af "gz sim"
23921 gz sim -s -r --headless-rendering -v 1 m6/gazebo/warehouse_ver3.sdf
24086 gz sim -s -r -v 2 .../m6/gazebo/warehouse_ver3.sdf
24172 gz sim -g -v 2

$ ./m5_ver3/m5v3.sh stop
  swept 24086 (gz sim)
  swept 24172 (gz sim)
  swept 24164 (parameter_bridge)
  swept 24177 (parameter_bridge)
  killed 24086 (world)
  killed 24172 (gui)
  swept 24086 (gz sim)
down.

DECOY SURVIVED (pid 23921) - the m6 partition was not touched
```

Both m5v3 gz processes were nominated by the pattern `gz sim`; so was the
decoy, and only the decoy came back. `24177` is the real
`parameter_bridge` under the `ros2 run` wrapper at `24164` — two
processes, both carrying the partition, both swept.

After `stop`: the pid file is **removed**, `status` reports `not running
(no pid file)` with exit 1, and `pgrep` finds nothing of ours. The GUI
run also confirms the client gate works: `gui` reached `exec gz sim -g`
only after the back scanner's topic was advertised, which is what keeps
the lidar fans from anchoring at the world origin.

**Log inventory after a run** — one file per child, by name, as
`status` reports them:

```
logs/gpu_preflight.log   logs/spawn.log   logs/world.log
logs/bridge.log          logs/gui.log
```

---

## 7. The spawn pose the plan quoted puts the forks inside a rack

This is the one thing Task 1 did not take on trust, and the finding is
worth more than the bringup.

The plan asked for f1's pose "from `m6/ipc/status_contract.py` VEHICLES"
and quoted `(-3.00, -5.50, 0.05)` yaw `0.0`. **That table does not hold
those values.** It holds `(-17.00, 10.00, 0.05)` yaw `3.14159`. The
quoted pair is real but belongs to an earlier floor: it is
`sim/launch/warehouse_bringup.launch.py`'s `_SPAWN_X`/`_SPAWN_Y`, what
step5 and M6.1 spawned at on **`warehouse_ver2`**, and M6.6's relayout put
a rack column across it.

### The arithmetic

**Instrument:** the collision geometry of
`m5_ver3/gazebo/forklift_ver3/model.sdf` and of `warehouse_ver3.sdf`,
read out of the files.

| | x | y | z |
|---|---|---|---|
| `fork_left` / `fork_right` collision, model frame | **-1.875 … -0.825** | ±(0.220…0.340) | 0.050 … 0.100 |
| `RackSW3`, world frame | **-4.500 … -4.000** | -6.000 … -2.500 | 0.000 … 4.000 |

At `(-3.00, -5.50)` with yaw 0 the fork tips land at world
`x = -3.00 + (-1.875) = -4.875`. The rack's east face is at `-4.000`.
**The truck is spawned with 0.875 m of fork inside a rack leg**, and the
forks sit at z 0.05–0.10, well inside the rack's 0–4.0 m.

`data: true` from the entity factory says the request was *accepted*,
never that the truck is clear of geometry.

### The measurement

**Instrument:** `gz model --pose` after a full `m5v3.sh start --headless`
at the quoted pose. The truck slid east and came to rest at

```
[-2.125000 -5.500000 -0.000000]   [0.000000 0.000000 0.000012]
```

`-2.125 + (-1.875) = -4.000` — **the fork tips end flush on the rack
face, having undone exactly the 0.875 m of penetration.** The arithmetic
and the measurement agree to the micrometre. While being ejected the
truck rode at a fixed `z = 0.018278`, pitch `-0.036406 rad`, on its fork
tips against the rack.

### The A/B that ruled out everything else

**Instrument:** server-only gz runs, 30 s each, one variable at a time.
Resting pose after 30 s:

| World | Model | Lidar subscribed | Spawn z | Resting pose |
|---|---|---|---|---|
| ver3 | forklift_ver3 | no | 0.05 | `-2.622670  -5.500000  0.018278` / pitch `-0.036406` |
| **ver2** | forklift_ver3 | no | 0.05 | **`-3.000000  -5.500000  -0.000001` / `0 0 0`** |
| ver3 | **m6's forklift_ver2** | no | 0.05 | `-2.623660  -5.500000  0.018278` / pitch `-0.036406` |
| ver3 | forklift_ver3 | **yes** | 0.05 | `-2.627990  -5.500000  0.018278` / pitch `-0.036406` |
| ver3, Floor `<pose>` removed | forklift_ver3 | no | 0.05 | `-2.623930  -5.500000  0.018278` |
| ver2, Floor `<pose>` added | forklift_ver3 | no | 0.05 | `-3.000000  -5.500000  -0.000001` |
| ver3 | forklift_ver3 | no | **0.00** | `-2.675000  -5.500000  0.018278` |
| ver3 | forklift_ver3 | no | **0.01** | `-2.652840  -5.500000  0.018278` |

So it is **not** this track's fork of the model (m6's own model does the
same), **not** the bridge or the lidar subscriber, **not** the drop from
`z = 0.05`, and **not** the ver3 floor plane's offset pose. It is the
rack, and only the rack. The ver2 row reproduces m6's own Gate 1 figure
for f1 exactly — `(-3.000000, -5.500000, -0.000001)`, zero roll and pitch
— which is how that pose earned its place, on a floor that no longer
exists.

### What was done about it

`config.yaml` was set to the pose the table **actually holds**,
`(-17.00, 10.00, 0.05)` yaw `3.14159` — the north ring leg, an 8.00 m
clear cruise corridor whose nearest racks end at `y = +6.00`. Section 3
is its measurement: exact coordinates, zero roll and pitch, stationary.

The rule this leaves behind, for any pose this track picks later: **check
a candidate against the fork reach (`x = -1.875` in the model frame), not
against the look of the floor plan.** It is written into `config.yaml`
beside the pose, where the next person will be standing.
