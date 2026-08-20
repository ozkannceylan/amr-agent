# M6.1 Two-Vehicle Foundation (step6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `m5_ver2/step6/` runs two forklifts (`f1`, `f2`) in one Gazebo world, each with its own full step5-grade stack and its own virtual F-PLC, with the known step5 debt closed.

**Architecture:** step6 is a copy of step5 (the owner's step-copy ruling), then parameterized: every per-vehicle difference lives in one `VEHICLES` table in step6's `ipc/status_contract.py`; per-vehicle model/config are derived build products of a small instantiation tool; per-vehicle writer processes on Windows. Spec: `docs/superpowers/specs/2026-08-20-m6-1-two-vehicle-foundation-design.md` — read it before starting.

**Tech Stack:** Plain Python 3 (no package), bash, ROS 2 Jazzy in WSL, Gazebo (gz-sim 8), pytest. Windows writers are Tk + pure Python (`--virtual`).

## Global Constraints

- Sources are used in place, unmodified: `agv/forklift/model.sdf`, `agv/forklift/config.yaml`, `agv/forklift/scripts/forklift_io.py`, `agv/forklift/scripts/sto_contactor.py`. (Note: step5's plant model is `step5/gazebo/forklift_ver2/model.sdf` — step6's own copy of THAT file is the instantiation source, and the copy inside step6 may not be edited either: derivation only.)
- Steps 1–5 stay frozen: nothing outside `m5_ver2/step6/`, `docs/`, and the repo `.gitignore` may change. step5 must remain runnable as-is.
- Isolation: `GZ_PARTITION=step6`, `ROS_DOMAIN_ID=96`. Port families: f1 = 5110/5111, f2 = 5120/5121; the 5100/5101 family is left to step5.
- Vehicle ids are exactly `f1` and `f2`. WSL nodes read env `VEHICLE`; the Windows writer takes `--vehicle`.
- Never rename or invent a PLC tag; `E-Stop` keeps its hyphen.
- No MQTT, no VDA 5050, no fleet or traffic logic, no third vehicle, no headless writer.
- Commit messages: lowercase `step6: ...` style, no attribution lines, no Claude mention.
- Test evidence before claims. WSL suite runs need `source /opt/ros/jazzy/setup.bash`. Windows has no rclpy: rclpy-importing tests collect only in WSL.
- Repo root in WSL: `/mnt/c/Users/ozkan/projects/amr-agent`. On Windows: `C:\Users\ozkan\projects\amr-agent`.

## Facts about the step5 tree you will rely on (verified 2026-08-20)

- `step5/gazebo/forklift_ver2/model.sdf` contains exactly **35** occurrences of the string `/forklift/`; `agv/forklift/config.yaml` contains **61**. Every gz topic is explicit and absolute — that is why two spawns of one file would share topics.
- The launch file spawns with `-name forklift` (a deliberate literal); gz topic names do not depend on the entity name.
- Ports live in exactly two node files: `ipc/plc_link.py` (`UDP_PORT = 5100`) and `ipc/sensor_link.py` (`UDP_PORT = 5101`). The Windows writer has its own `UDP_PORT = 5100` / `SENSOR_PORT = 5101` constants.
- `ipc/status_contract.py` is the one home for every ROS name config.yaml has never heard of (`STATUS_TOPIC`, `FIELDS_TOPIC`, `ENCODERS_TOPIC`, `SCAN_TOPIC`, `HMI_CMD_TOPIC`, `VEHICLE_CMD_TOPIC`, `AUTO_*`, `MODE_*`).
- Config-reading nodes and their mechanism: `plc_link.py`, `cmd_gate.py`, `encoder_link.py`, `nav_node.py`, `hmi/hmi_node.py` each build `CONFIG_YAML` with an `os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml")` walk. `field_eval.py`, `cmd_mux.py`, `follower.py`, `route.py`, `stations.py` read no config.
- `tests/conftest.py` puts `ipc/`, `hmi/`, `windows/` on `sys.path` relative to itself — it survives the tree copy unchanged.
- `step5.sh` mechanics you must preserve in the copy: `PATTERNS` nominate, `ours()` (GZ_PARTITION in `/proc/pid/environ`) decides; `recorded()` greps `m5_ver2/step5` in cmdline; the UDP :5100 pre-flight is pipe-free on purpose; `spawn()` writes leader pids via setsid; deploy() freezes `ipc/` + config with a sha256 MANIFEST; stop sweeps gz first.
- step5's whole WSL suite: **220 passed**. That is your regression baseline for the copied tree (step6's copy will run the same tests under new file names).

---

### Task 1: The step6 copy

**Files:**
- Create: `m5_ver2/step6/` (copy of `m5_ver2/step5/`), with renames:
  `step5.sh`→`step6.sh`, `windows/step5.py`→`windows/step6.py`,
  `gazebo/step5_world.launch.py`→`gazebo/step6_world.launch.py`,
  `README_step5.md`→`README_step6.md`,
  `tests/test_step5.py`→`tests/test_step6.py`,
  `tests/test_step5_encoders.py`→`tests/test_step6_encoders.py`,
  `tests/test_step5_virtual_loop.py`→`tests/test_step6_virtual_loop.py`

**Interfaces:**
- Produces: a step6 tree that is step5 under new names — single vehicle, ports 5100/5101 still, tests green. Every later task edits THIS tree.

- [ ] **Step 1: Copy and clean**

```bash
cd /c/Users/ozkan/projects/amr-agent/m5_ver2
cp -r step5 step6
cd step6
rm -rf logs deploy .step5_pids ipc/__pycache__ hmi/__pycache__ windows/__pycache__ tests/__pycache__ gazebo/__pycache__ 2>/dev/null
mv step5.sh step6.sh
mv windows/step5.py windows/step6.py
mv gazebo/step5_world.launch.py gazebo/step6_world.launch.py
mv README_step5.md README_step6.md
mv tests/test_step5.py tests/test_step6.py
mv tests/test_step5_encoders.py tests/test_step6_encoders.py
mv tests/test_step5_virtual_loop.py tests/test_step6_virtual_loop.py
```

- [ ] **Step 2: Token sweep — code files only**

Inside `m5_ver2/step6/` only, on `*.py`, `*.sh` and the launch file (NOT on `*.md` — CONTEXT.md's references to real step5 paths are true statements about where the inherited proofs live):

```bash
cd /c/Users/ozkan/projects/amr-agent/m5_ver2/step6
grep -rl "step5" --include="*.py" --include="*.sh" . | xargs sed -i 's/step5/step6/g'
sed -i 's/ROS_DOMAIN_ID:-95/ROS_DOMAIN_ID:-96/' step6.sh
```

The blanket lowercase sed is safe on code files: it hits exactly the path tokens (`m5_ver2/step5`, `step5_world.launch.py`, `import step5`, `.step5_pids`, `GZ_PARTITION:-step5`, `step5.py`, `m5_ver2\\step5`) and lowercase `step5` appears in no other role there. `Step 5` (capital S, prose) is untouched by design.

Then the two targeted prose-debt fixes the spec names, in `step6.sh` and `gazebo/step6_world.launch.py` (they are comments, so the sed above did not fix their content): delete or correct the stale statements "Port 5101 arrives in a later step" (if present after the sweep) and any "All four recorded command lines" style count claim — the honest count is nine. Read the surrounding comment and correct the sentence, do not delete whole explanatory blocks.

- [ ] **Step 3: Reset the inherited claims**

Replace `m5_ver2/step6/PROOF.md` entirely with:

```markdown
# Step 6 — proof ledger

Nothing is proven here yet. The inherited system's evidence lives in
`m5_ver2/step5/PROOF.md` and is step5's, not step6's. This file fills as
step6's own gates run (see the M6.1 spec's proof gates).
```

Leave `CONTEXT.md` as copied — it documents inherited ground truth; Task 9 adds the step6 header.

- [ ] **Step 4: Port-guard note check**

`step6.sh`'s UDP pre-flight still checks :5100 after the sweep (the literal `5100` was not touched). That is WRONG for step6 and RIGHT for step5 — Task 7 rewrites the guard for 5110/5120. For now just confirm the file still parses: `bash -n step6.sh`.

- [ ] **Step 5: Verify the copied suite**

```bash
wsl -e bash -lc "source /opt/ros/jazzy/setup.bash && cd /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6 && python3 -m pytest tests/ -q"
```
Expected: 220 passed (same count as step5's suite — same tests, new tree). Also:
```bash
grep -rn "step5" m5_ver2/step6 --include="*.py" --include="*.sh"
```
Expected: no hits. And `wsl -e bash -lc "cd /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step5 && source /opt/ros/jazzy/setup.bash && python3 -m pytest tests/ -q"` still 220 passed (step5 untouched).

- [ ] **Step 6: Commit**

```bash
git add -A m5_ver2/step6
git commit -m "step6: the copy - step5 under new names, claims reset"
```

---

### Task 2: Vehicle-aware status_contract

**Files:**
- Modify: `m5_ver2/step6/ipc/status_contract.py` (the CONFIG section)
- Modify: `m5_ver2/step6/tests/conftest.py` (default VEHICLE)
- Test: `m5_ver2/step6/tests/test_vehicles_table.py` (new)

**Interfaces:**
- Produces (later tasks rely on these exact names):
  - `VEHICLES: dict` — `{"f1": {"plc_port": 5110, "sensor_port": 5111, "spawn": {...}}, "f2": {...}}`
  - `contract(vid) -> dict` — pure; keys `status_topic`, `fields_topic`, `encoders_topic`, `scan_topic` (with `{}` side placeholder), `hmi_cmd_topic`, `vehicle_cmd_topic`, `auto_cmd_topic`, `auto_goal_topic`, `auto_state_topic`, `mode_topic`, `plc_port`, `sensor_port`, `config_path`, `spawn`
  - `vehicle_id() -> str` — env `VEHICLE`, SystemExit naming valid ids if unset/unknown
  - Module constants `VID`, `PLC_PORT`, `SENSOR_PORT`, `CONFIG_PATH` and the existing topic constant names, now vehicle-namespaced — every existing `from status_contract import STATUS_TOPIC` keeps working unchanged.

- [ ] **Step 1: Write the failing test**

`m5_ver2/step6/tests/test_vehicles_table.py`:

```python
"""The VEHICLES table and the per-vehicle contract."""
import pytest

import status_contract as sc


def test_table_has_exactly_the_two_vehicles_with_disjoint_ports():
    assert set(sc.VEHICLES) == {"f1", "f2"}
    ports = [v[k] for v in sc.VEHICLES.values()
             for k in ("plc_port", "sensor_port")]
    assert len(ports) == len(set(ports))
    assert 5100 not in ports and 5101 not in ports   # step5's family


def test_contract_namespaces_every_ros_name():
    c = sc.contract("f2")
    assert c["status_topic"] == "/f2/plc/status"
    assert c["fields_topic"] == "/f2/safety/fields"
    assert c["encoders_topic"] == "/f2/safety/encoders"
    assert c["scan_topic"].format("back") == \
        "/f2/gz/safety_scanner_back/measurement"
    assert c["vehicle_cmd_topic"] == "/f2/vehicle/cmd_vel"
    assert c["hmi_cmd_topic"] == "/f2/hmi/cmd_vel"
    assert c["plc_port"] == 5120 and c["sensor_port"] == 5121


def test_module_constants_follow_the_env_vehicle():
    # conftest sets VEHICLE=f1 for the whole suite.
    assert sc.VID == "f1"
    assert sc.STATUS_TOPIC == "/f1/plc/status"
    assert sc.PLC_PORT == 5110 and sc.SENSOR_PORT == 5111
    assert sc.CONFIG_PATH.replace("\\", "/").endswith(
        "step6/vehicles/f1/config.yaml")


def test_unknown_vehicle_refused():
    with pytest.raises(SystemExit):
        sc.contract("f9")
```

- [ ] **Step 2: Run it to verify it fails**

Run (WSL or Windows): `python -m pytest m5_ver2/step6/tests/test_vehicles_table.py -q`
Expected: FAIL/collection error (no `VEHICLES`, and `VEHICLE` env unset kills import if you implement env-checking first — that is why conftest changes in this task).

- [ ] **Step 3: Implement**

In `m5_ver2/step6/tests/conftest.py`, after the imports, add:

```python
# The suite runs as one vehicle; per-vehicle behaviour is tested through
# contract(vid), which is pure. f1 is arbitrary.
os.environ.setdefault("VEHICLE", "f1")
```

In `m5_ver2/step6/ipc/status_contract.py`, add `import os` to the imports, and at the top of the CONFIG section (before the topic constants) insert:

```python
# ----------------------------- VEHICLES ----------------------------
# The one table every per-vehicle difference lives in (M6.1 spec). WSL
# nodes read their vehicle id from env VEHICLE, stamped by step6.sh on
# every spawn; the Windows writer sets the same variable from
# --vehicle before importing this module. The 5100/5101 family is left
# to step5 on purpose: an accidentally concurrent step5 stack collides
# with nothing here and is caught by its own port guard.
VEHICLES = {
    "f1": {"plc_port": 5110, "sensor_port": 5111,
           "spawn": {"x": "-3.00", "y": "-5.50", "z": "0.05", "yaw": "0.0"}},
    "f2": {"plc_port": 5120, "sensor_port": 5121,
           "spawn": {"x": "3.00", "y": "-5.50", "z": "0.05",
                     "yaw": "3.14159"}},
}
# f1 keeps step5's proven spawn. f2 faces it from the other end of the
# 6.50 m main aisle. Task 4 (the RTF spike) validates both live; if a
# scanner reads PROTECTIVE at spawn the pose moves THERE, in this table.

_HERE = os.path.dirname(os.path.abspath(__file__))


def vehicle_id():
    """Env VEHICLE, refused loudly when absent or unknown."""
    vid = os.environ.get("VEHICLE", "")
    if vid not in VEHICLES:
        raise SystemExit(
            "status_contract: env VEHICLE must be one of {}, got {!r}"
            .format(sorted(VEHICLES), vid))
    return vid


def contract(vid):
    """Every per-vehicle name and number, as pure data.

    The launch file serves BOTH vehicles from one process, so it calls
    this per vid instead of reading the env-bound module constants.
    """
    if vid not in VEHICLES:
        raise SystemExit(
            "status_contract: unknown vehicle {!r}, valid: {}"
            .format(vid, sorted(VEHICLES)))
    v = VEHICLES[vid]
    return {
        "status_topic": "/{}/plc/status".format(vid),
        "fields_topic": "/{}/safety/fields".format(vid),
        "encoders_topic": "/{}/safety/encoders".format(vid),
        "scan_topic": "/" + vid + "/gz/safety_scanner_{}/measurement",
        "hmi_cmd_topic": "/{}/hmi/cmd_vel".format(vid),
        "vehicle_cmd_topic": "/{}/vehicle/cmd_vel".format(vid),
        "auto_cmd_topic": "/{}/auto/cmd_vel".format(vid),
        "auto_goal_topic": "/{}/auto/goal".format(vid),
        "auto_state_topic": "/{}/auto/state".format(vid),
        "mode_topic": "/{}/hmi/mode".format(vid),
        "plc_port": v["plc_port"],
        "sensor_port": v["sensor_port"],
        "config_path": os.path.normpath(os.path.join(
            _HERE, "..", "vehicles", vid, "config.yaml")),
        "spawn": v["spawn"],
    }


```

Then REPLACE the literal topic constants with an env-guarded binding block, keeping the existing comment blocks in place above it (the reasoning still holds; only the values become vehicle-scoped). The guard exists because the LAUNCH FILE imports this module env-free — it serves both vehicles through `contract(vid)` and must not die at import; a NODE missing the env must still get a loud, naming refusal, which the PEP 562 module `__getattr__` provides:

```python
if os.environ.get("VEHICLE"):
    VID = vehicle_id()
    _C = contract(VID)
    PLC_PORT = _C["plc_port"]
    SENSOR_PORT = _C["sensor_port"]
    CONFIG_PATH = _C["config_path"]
    STATUS_TOPIC = _C["status_topic"]
    FIELDS_TOPIC = _C["fields_topic"]
    ENCODERS_TOPIC = _C["encoders_topic"]
    SCAN_TOPIC = _C["scan_topic"]
    HMI_CMD_TOPIC = _C["hmi_cmd_topic"]
    VEHICLE_CMD_TOPIC = _C["vehicle_cmd_topic"]
    AUTO_CMD_TOPIC = _C["auto_cmd_topic"]
    AUTO_GOAL_TOPIC = _C["auto_goal_topic"]
    AUTO_STATE_TOPIC = _C["auto_state_topic"]
    MODE_TOPIC = _C["mode_topic"]
else:
    # The launch file imports this module with no VEHICLE - it reads
    # only VEHICLES and contract(vid), which exist above. Anything
    # else reaching for a per-vehicle constant without the env gets
    # the refusal by name, not an ImportError shrug.
    def __getattr__(name):
        raise SystemExit(
            "status_contract: env VEHICLE is not set, so the "
            "per-vehicle constant {!r} does not exist. step6.sh stamps "
            "VEHICLE on every node; the writer's --vehicle sets it; "
            "env-free callers use contract(vid).".format(name))
```

`MODE_TELEOP`, `MODE_AUTO`, `STATUS_STALE_S`, `V_LIMIT_*`, `FAILSAFE`, and the three functions are untouched.

- [ ] **Step 4: Run the tests**

`python -m pytest m5_ver2/step6/tests/test_vehicles_table.py -q` → 4 passed.
Then the whole step6 suite in WSL → expected 224 passed (220 + these 4). If a copied test hard-codes an old literal like `/plc/status`, fix THAT test to import the constant instead — the contract is the source of truth. Name every such fix in your report.

- [ ] **Step 5: Commit**

```bash
git add m5_ver2/step6/ipc/status_contract.py m5_ver2/step6/tests/conftest.py m5_ver2/step6/tests/test_vehicles_table.py
git commit -m "step6: the VEHICLES table - every per-vehicle difference in one place"
```

---

### Task 3: The instantiation tool

**Files:**
- Create: `m5_ver2/step6/tools/instantiate_vehicle.py`
- Test: `m5_ver2/step6/tests/test_instantiate_vehicle.py`
- Modify: repo `.gitignore` (add `m5_ver2/step6/vehicles/`)

**Interfaces:**
- Consumes: `status_contract.VEHICLES` (Task 2).
- Produces: `instantiate(vid, force=False) -> pathlib-free str dir path` writing `m5_ver2/step6/vehicles/<vid>/model.sdf` and `config.yaml`; CLI `python3 tools/instantiate_vehicle.py --all` (or one vid). Task 7's `step6.sh deploy` calls the CLI; Task 6's launch reads the derived files.

- [ ] **Step 1: Write the failing test**

`m5_ver2/step6/tests/test_instantiate_vehicle.py`:

```python
"""The derivation is mechanical, counted, and refuses the unknown."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "tools")))

import instantiate_vehicle as iv


def test_derives_both_files_with_full_prefix_rewrite(tmp_path):
    out = iv.instantiate("f1", out_root=str(tmp_path))
    model = open(os.path.join(out, "model.sdf"), encoding="utf-8").read()
    config = open(os.path.join(out, "config.yaml"), encoding="utf-8").read()
    assert "/forklift/" not in model and "/forklift/" not in config
    assert model.count("/f1/") == iv.count_prefix(iv.SRC_MODEL)
    assert config.count("/f1/") == iv.count_prefix(iv.SRC_CONFIG)


def test_rewrite_touches_only_the_prefix(tmp_path):
    out = iv.instantiate("f2", out_root=str(tmp_path))
    src = open(iv.SRC_MODEL, encoding="utf-8").read()
    derived = open(os.path.join(out, "model.sdf"), encoding="utf-8").read()
    assert derived == src.replace("/forklift/", "/f2/")


def test_idempotent(tmp_path):
    first = iv.instantiate("f1", out_root=str(tmp_path))
    body1 = open(os.path.join(first, "model.sdf"), encoding="utf-8").read()
    second = iv.instantiate("f1", out_root=str(tmp_path))
    body2 = open(os.path.join(second, "model.sdf"), encoding="utf-8").read()
    assert first == second and body1 == body2


def test_unknown_vehicle_refused(tmp_path):
    with pytest.raises(SystemExit):
        iv.instantiate("f9", out_root=str(tmp_path))
```

- [ ] **Step 2: Run to verify it fails**

`python -m pytest m5_ver2/step6/tests/test_instantiate_vehicle.py -q`
Expected: `ModuleNotFoundError: No module named 'instantiate_vehicle'`.

- [ ] **Step 3: Implement**

`m5_ver2/step6/tools/instantiate_vehicle.py`:

```python
"""instantiate_vehicle.py - derive one vehicle's model.sdf and config.yaml.

The sources write every gz topic explicitly and absolutely under
/forklift/, so two spawns of one file would SHARE topics. This tool is
the only thing that may vary them: a counted, mechanical prefix rewrite
/forklift/ -> /<vid>/ into step6/vehicles/<vid>/. The sources are never
edited - agv/forklift/config.yaml belongs to three stacks, and
step6/gazebo/forklift_ver2/model.sdf is the inherited plant.

The count assertion is the safety of the mechanism: a source edit that
spells a topic any other way would silently escape the rewrite, so the
derived file must contain exactly as many /<vid>/ as the source has
/forklift/, or this tool refuses.

Usage:
  python3 m5_ver2/step6/tools/instantiate_vehicle.py --all
  python3 m5_ver2/step6/tools/instantiate_vehicle.py f1
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_STEP6 = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_STEP6, "..", ".."))
sys.path.insert(0, os.path.join(_STEP6, "ipc"))

PREFIX = "/forklift/"
SRC_MODEL = os.path.join(_STEP6, "gazebo", "forklift_ver2", "model.sdf")
SRC_CONFIG = os.path.join(_REPO, "agv", "forklift", "config.yaml")
OUT_ROOT = os.path.join(_STEP6, "vehicles")


def count_prefix(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read().count(PREFIX)


def _derive(src, dst, vid):
    with open(src, encoding="utf-8") as handle:
        body = handle.read()
    want = body.count(PREFIX)
    derived = body.replace(PREFIX, "/{}/".format(vid))
    got = derived.count("/{}/".format(vid))
    if got != want or PREFIX in derived:
        raise SystemExit(
            "instantiate_vehicle: rewrite miscount on {} ({} -> {})"
            .format(src, want, got))
    with open(dst, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(derived)


def instantiate(vid, out_root=OUT_ROOT):
    """Write <out_root>/<vid>/{model.sdf,config.yaml}; return the dir."""
    from status_contract import VEHICLES
    if vid not in VEHICLES:
        raise SystemExit(
            "instantiate_vehicle: unknown vehicle {!r}, valid: {}"
            .format(vid, sorted(VEHICLES)))
    out_dir = os.path.join(out_root, vid)
    os.makedirs(out_dir, exist_ok=True)
    _derive(SRC_MODEL, os.path.join(out_dir, "model.sdf"), vid)
    _derive(SRC_CONFIG, os.path.join(out_dir, "config.yaml"), vid)
    return out_dir


def main():
    from status_contract import VEHICLES
    parser = argparse.ArgumentParser()
    parser.add_argument("vehicle", nargs="?", help="one vehicle id")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    vids = sorted(VEHICLES) if args.all else [args.vehicle]
    if vids == [None]:
        parser.error("name a vehicle or pass --all")
    for vid in vids:
        print("instantiated", instantiate(vid))


if __name__ == "__main__":
    main()
```

Note: `status_contract` is imported lazily inside the functions so importing the tool never requires env `VEHICLE` (the table and `contract()` are env-free; only the module constants bind to the env).

Deliberate deviation from the spec, record it in your report: the spec has this tool also rename the SDF entity `Forklift` → `Forklift_<vid>`; the entity name is instead set at spawn time (`-name forklift_<vid>`, Task 7), which is the pattern step5 already uses (`-name forklift`, a deliberate literal) and gz topic names are name-independent by design. The spec's intent — distinct entity names per vehicle — is preserved; the mechanism moved to where step5 already does it.

Append to the repo `.gitignore` (both are build products — the derived vehicle files and step6's regenerated deploy tree; step5's committed deploy stays as the historical deliverable it was):

```
m5_ver2/step6/vehicles/
m5_ver2/step6/deploy/
```

- [ ] **Step 4: Run the tests, then generate for real**

`python -m pytest m5_ver2/step6/tests/test_instantiate_vehicle.py -q` → 4 passed.
Then: `python m5_ver2/step6/tools/instantiate_vehicle.py --all` → prints two dirs; `git status --short` shows NO new tracked files (vehicles/ ignored). Run the whole step6 WSL suite → 228 passed.

- [ ] **Step 5: Commit**

```bash
git add m5_ver2/step6/tools/instantiate_vehicle.py m5_ver2/step6/tests/test_instantiate_vehicle.py .gitignore
git commit -m "step6: instantiate_vehicle - counted prefix rewrite, sources untouched"
```

---

### Task 4: The RTF spike — GATE

**Files:**
- Create: `m5_ver2/step6/tools/rtf_spike.sh`
- Modify: `m5_ver2/step6/PROOF.md` (record the measurement)

**Interfaces:**
- Consumes: derived models from Task 3.
- Produces: a recorded RTF number, and a GO/STOP verdict. **If mean RTF (headless) < 0.90 with both models spawned: STOP — report BLOCKED with the numbers. Do not proceed to Task 5.** (Spec proof gate 1: the levers beyond this point need an owner ruling.)

- [ ] **Step 1: Write the spike script**

`m5_ver2/step6/tools/rtf_spike.sh`:

```bash
#!/usr/bin/env bash
# rtf_spike.sh - spec gate 1: can this machine's Gazebo carry two
# forklifts? Server-only, no ROS stack, no writers: the world plus both
# derived models, RTF sampled off gz stats for 60 s. Run inside WSL.
set -euo pipefail
STEP6="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GZ_PARTITION=step6-rtf-spike
source /opt/ros/jazzy/setup.bash
for f in "$STEP6/vehicles/f1/model.sdf" "$STEP6/vehicles/f2/model.sdf"; do
    [ -f "$f" ] || { echo "missing $f - run tools/instantiate_vehicle.py --all"; exit 1; }
done
gz sim -s -r --headless-rendering -v 1 "$STEP6/gazebo/warehouse_ver2.sdf" &
SIM=$!
trap 'kill $SIM 2>/dev/null; wait $SIM 2>/dev/null' EXIT
sleep 8
spawn() {  # spawn <vid> <x> <y> <yaw>
    gz service -s /world/warehouse/create --reqtype gz.msgs.EntityFactory \
        --reptype gz.msgs.Boolean --timeout 5000 \
        --req "sdf_filename: \"$STEP6/vehicles/$1/model.sdf\", name: \"forklift_$1\", pose: {position: {x: $2, y: $3, z: 0.05}, orientation: {w: $(awk "BEGIN{printf \"%.6f\", cos($4/2)}"), z: $(awk "BEGIN{printf \"%.6f\", sin($4/2)}")}}" \
        | grep -q "data: true" || { echo "spawn $1 refused"; exit 1; }
}
spawn f1 -3.00 -5.50 0.0
spawn f2  3.00 -5.50 3.14159
sleep 5
echo "sampling gz stats for 60 s..."
timeout 60 gz stats > /tmp/step6_rtf.log || true
# gz stats lines: "Factor[0.99] SimTime[...] RealTime[...] Iterations[...]"
awk -F'[][]' '/Factor/ {sum+=$2; n++} END {
    if (n==0) {print "NO SAMPLES"; exit 1}
    printf "samples %d  mean RTF %.3f\n", n, sum/n }' /tmp/step6_rtf.log
```

Note on the spawn poses: they mirror the VEHICLES table (Task 2). If a pose lands a model inside racking geometry (`create` succeeds but the model collides), pick a visibly free pose from `gazebo/warehouse_ver2.sdf`'s open aisle, update BOTH this script and the VEHICLES table `spawn` entries, and say so in your report.

- [ ] **Step 2: Run it**

```bash
wsl -e bash -lc "bash /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6/tools/rtf_spike.sh"
```
Expected: `samples N  mean RTF X.XXX`. Baseline: step5 measured single-vehicle headless mean 0.998.

- [ ] **Step 3: Record the verdict**

Append to `m5_ver2/step6/PROOF.md` a `## Gate 1 — RTF with two vehicles` section: the command, the sample count, the mean, the machine (WSL, llvmpipe), the date, and the verdict line `GO (>= 0.90)` or `STOP`. **If STOP: commit the measurement, then report BLOCKED — do not start Task 5.**

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/tools/rtf_spike.sh m5_ver2/step6/PROOF.md
git commit -m "step6: gate 1 - two-vehicle RTF measured"
```

---

### Task 5: Node plumbing — ports and config through the contract

**Files:**
- Modify: `m5_ver2/step6/ipc/plc_link.py`, `ipc/sensor_link.py`, `ipc/encoder_link.py`, `ipc/cmd_gate.py`, `ipc/nav_node.py`, `hmi/hmi_node.py`

**Interfaces:**
- Consumes: `PLC_PORT`, `SENSOR_PORT`, `CONFIG_PATH` from Task 2's status_contract.
- Produces: no node carries its own port number or config path; everything flows from env `VEHICLE` through the contract.

- [ ] **Step 1: The six edits**

Each is the same two-line pattern; apply per file:

1. `ipc/plc_link.py`: delete `UDP_PORT = 5100` from CONFIG; import `PLC_PORT` from status_contract (extend the existing `from status_contract import (...)`) and use `PLC_PORT` at the bind and in the log line. Delete the `CONFIG_YAML` walk (`_HERE`/`CONFIG_YAML` block) and change `load_topics(path=CONFIG_YAML)` to import `CONFIG_PATH` from status_contract and use `load_topics(path=CONFIG_PATH)`. Update the docstring's ":5100" to "its vehicle's PLC port (VEHICLES table)".
2. `ipc/sensor_link.py`: `UDP_PORT = 5101` → import `SENSOR_PORT` from status_contract, use it at the sendto/log sites (it already does `import status_contract`, so `status_contract.SENSOR_PORT` is fine and smaller). Docstring "5101" reference updated the same way.
3. `ipc/encoder_link.py`: replace the `CONFIG_YAML` walk with `status_contract.CONFIG_PATH` (it already imports status_contract).
4. `ipc/cmd_gate.py`: same `CONFIG_YAML` → `CONFIG_PATH` replacement (extend its existing status_contract import list).
5. `ipc/nav_node.py`: same replacement.
6. `hmi/hmi_node.py`: same replacement (keep its existing import mechanics for reaching the ipc dir). Additionally (spec: per-vehicle HMI windows): find the Tk window title call (`root.title(...)` or `self.title(...)`) and append the vehicle id to the existing string using `status_contract.VID` — e.g. `existing_title + " - " + VID` — so two open HMIs are tellable apart.

Do NOT touch the comments explaining why STALE_S budgets differ — only the port/path lines and the specific numbers named here.

- [ ] **Step 2: Adjust any test that asserted the old literals**

Run the step6 WSL suite. Any copied test that asserted `5100`/`5101` or the old config walk now fails — fix those tests to import the contract values. Name each fixed test in your report. Expected end state: 228 passed.

- [ ] **Step 3: Spot-check the derived config actually resolves**

```bash
wsl -e bash -lc "cd /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6 && python3 tools/instantiate_vehicle.py --all && VEHICLE=f2 python3 -c \"import sys; sys.path.insert(0,'ipc'); import status_contract as sc, yaml; t=yaml.safe_load(open(sc.CONFIG_PATH))['topics']; print(sc.PLC_PORT, t['gz_odom'])\""
```
Expected: `5120 /f2/gz/odom`.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/ipc m5_ver2/step6/hmi m5_ver2/step6/tests
git commit -m "step6: ports and config paths flow from the contract, not from nodes"
```

---

### Task 6: The gate's fail-open debt

**Files:**
- Modify: `m5_ver2/step6/ipc/cmd_gate.py`
- Test: extend `m5_ver2/step6/tests/test_cmd_gate.py`

**Interfaces:**
- Produces: `command_or_zeros(cmd, last_rx_s, now_s, stale_s=CMD_STALE_S) -> (float, float)`; `CMD_STALE_S = 0.25`.

- [ ] **Step 1: Write the failing tests**

Append to `m5_ver2/step6/tests/test_cmd_gate.py`:

```python
def test_command_never_received_is_zeros():
    assert cmd_gate.command_or_zeros((0.8, 0.2), None, 100.0) == (0.0, 0.0)


def test_fresh_command_passes():
    assert cmd_gate.command_or_zeros((0.8, 0.2), 99.9, 100.0) == (0.8, 0.2)


def test_stale_command_is_zeros_while_enabled():
    # THE step4 14.8 m CLASS: mux dead, Motor True, last setpoint held.
    # At CMD_STALE_S the gate stops repeating the corpse's command.
    stale_at = 100.0 + cmd_gate.CMD_STALE_S
    assert cmd_gate.command_or_zeros((0.8, 0.2), 100.0, stale_at) == (0.0, 0.0)
```

(Match the file's existing import style — it imports the module under test as `cmd_gate`; if it uses `from cmd_gate import ...` instead, follow that.)

- [ ] **Step 2: Run to verify they fail**

`python -m pytest m5_ver2/step6/tests/test_cmd_gate.py -q` → the three new tests fail with AttributeError.

- [ ] **Step 3: Implement**

In `m5_ver2/step6/ipc/cmd_gate.py` CONFIG section:

```python
# THE COMMAND INPUT'S OWN TIMEOUT - the one silence path that failed
# OPEN in steps 4-5: cb_cmd repeats on receipt, tick published only
# while inhibited, so a dead cmd_mux with Motor True left the plant
# holding its last setpoint (measured class: 14.8 m). Same value class
# as STATUS_STALE_S, same shape as the mux's own auto-source rule:
# enabled and silent -> zeros.
CMD_STALE_S = 0.25
```

New pure function next to `gated_command`:

```python
def command_or_zeros(cmd, last_rx_s, now_s, stale_s=CMD_STALE_S):
    """The command to obey: the mux's, unless the mux has gone silent.

    is_stale already reads never-received as stale, so a gate that has
    heard Motor True but no command yet commands zeros, not garbage.
    """
    if is_stale(last_rx_s, now_s, stale_s):
        return (0.0, 0.0)
    return cmd
```

Wire it in `CmdGate`: in `__init__` add `self.last_cmd_rx = None`; in `cb_cmd` set `self.last_cmd_rx = time.monotonic()` before storing; in `publish()` replace `self.cmd[0], self.cmd[1]` with

```python
        cmd = command_or_zeros(self.cmd, self.last_cmd_rx, time.monotonic())
        traction, steer = gated_command(
            cmd[0], cmd[1], self.enabled(),
            limit, self.steer_max)
```

and in `tick()` change the final publish condition so the zeros actually flow while enabled-and-silent:

```python
        if not live or is_stale(self.last_cmd_rx, time.monotonic(),
                                CMD_STALE_S):
            self.publish()
```

- [ ] **Step 4: Run the tests**

`python -m pytest m5_ver2/step6/tests/test_cmd_gate.py -q` → all pass. Whole step6 WSL suite → 231 passed.

- [ ] **Step 5: Commit**

```bash
git add m5_ver2/step6/ipc/cmd_gate.py m5_ver2/step6/tests/test_cmd_gate.py
git commit -m "step6: the gate's command input times out - the 14.8 m class is closed"
```

---

### Task 7: Two vehicles in the launch and in step6.sh

**Files:**
- Modify: `m5_ver2/step6/gazebo/step6_world.launch.py`
- Modify: `m5_ver2/step6/step6.sh`

**Interfaces:**
- Consumes: `status_contract.VEHICLES`, `contract(vid)` (Task 2); derived `vehicles/<vid>/{model.sdf,config.yaml}` (Task 3).
- Produces: `step6.sh start|stop|home|deploy` managing the doubled stack; the launch spawning `forklift_f1`/`forklift_f2`.

- [ ] **Step 1: Launch file — loop the per-vehicle pieces**

In `step6_world.launch.py` (which already `sys.path.insert`s the ipc dir and imports `status_contract`):

- Replace `_MODEL` and its existence check with per-vehicle paths:

```python
_VEHICLE_MODELS = {
    vid: os.path.join(_HERE, "..", "vehicles", vid, "model.sdf")
    for vid in sorted(status_contract.VEHICLES)
}
for _vid, _path in _VEHICLE_MODELS.items():
    if not os.path.isfile(_path):
        raise FileNotFoundError(
            "step6_world.launch.py: no derived model for {}: {} "
            "(run tools/instantiate_vehicle.py --all)".format(_vid, _path))
```

- Replace the single `_CONFIG` read and `_BRIDGE_ARGS` build with a per-vehicle loop. The bridge stays ONE process; its argument list carries both vehicles:

```python
_BRIDGE_ARGS = []
_VEHICLE_TOPICS = {}
for _vid in sorted(status_contract.VEHICLES):
    _vcfg = os.path.join(_HERE, "..", "vehicles", _vid, "config.yaml")
    with open(_vcfg, "r", encoding="utf-8") as _handle:
        _T = yaml.safe_load(_handle)["topics"]
    _VEHICLE_TOPICS[_vid] = _T
    _c = status_contract.contract(_vid)
    _scans = tuple(_c["scan_topic"].format(n)
                   for n in ("back", "left", "right"))
    _BRIDGE_ARGS += [
        "{}@std_msgs/msg/Float64]gz.msgs.Double".format(
            _T["gz_actuator_steer_cmd"]),
        "{}@std_msgs/msg/Float64]gz.msgs.Double".format(
            _T["gz_actuator_traction_cmd"]),
        "{}@nav_msgs/msg/Odometry[gz.msgs.Odometry".format(_T["gz_odom"]),
        "{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan".format(
            _T["gz_scan_nav"]),
        "{}@sensor_msgs/msg/JointState[gz.msgs.Model".format(
            _T["gz_drive_speed_read_a"]),
        "{}@sensor_msgs/msg/JointState[gz.msgs.Model".format(
            _T["gz_drive_speed_read_b"]),
    ] + ["{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan".format(t)
         for t in _scans]
_BRIDGE_ARGS.insert(0, "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock")
```

(`/clock` is world-level and bridged once — it has no `/forklift/` prefix and the derived configs all carry the same value; assert that if you like, in the loop.)

- Replace the single spawn Node and the two ExecuteProcess vehicle nodes with a loop over `sorted(status_contract.VEHICLES)` inside `generate_launch_description()`:

```python
    for vid in sorted(status_contract.VEHICLES):
        c = status_contract.contract(vid)
        vcfg = os.path.join(_HERE, "..", "vehicles", vid, "config.yaml")
        ld.add_action(Node(
            package="ros_gz_sim", executable="create",
            name="spawn_forklift_{}".format(vid), output="screen",
            arguments=[
                "-world", _WORLD_NAME,
                "-file", _VEHICLE_MODELS[vid],
                "-name", "forklift_{}".format(vid),
                "-x", c["spawn"]["x"], "-y", c["spawn"]["y"],
                "-z", c["spawn"]["z"], "-Y", c["spawn"]["yaw"],
                "-allow_renaming", "false",
            ]))
        ld.add_action(ExecuteProcess(
            cmd=[sys.executable, _STO_SCRIPT, "--config", vcfg,
                 "--ros-args", "-p", "use_sim_time:=true",
                 "-r", "__node:=sto_contactor_{}".format(vid)],
            name="sto_contactor_{}".format(vid), output="screen"))
        ld.add_action(ExecuteProcess(
            cmd=[sys.executable, _IO_SCRIPT, "--config", vcfg,
                 "--ros-args", "-r", "__node:=forklift_io_{}".format(vid)],
            name="forklift_io_{}".format(vid), output="screen"))
```

(The `__node` remap gives each instance a distinct node name so `ros2 node list` is honest; the scripts pass unknown `--ros-args` through to rclpy — verify with a quick `--help` if in doubt, and report if a script rejects the remap: fallback is accepting duplicate node names, which rclpy allows with a warning.)

- The GUI gate waits on the back scanner topic: change its `_SCAN_TOPICS[0]` reference to f1's back scanner via `status_contract.contract("f1")["scan_topic"].format("back")`.
- Update the module docstring's process count sentence to the honest new count.

- [ ] **Step 2: step6.sh — the doubled stack**

Edits, keeping every existing mechanism (`ours()`, `recorded()`, pipe-free guard, setsid spawn, sweep order):

1. Port guard: check BOTH 5110 and 5120 (two `case` checks on the same `ss` capture, one per family; message names the vehicle whose port is held).
2. `deploy()`: before the copy, run the instantiation so the freeze ships current derived configs:
   ```bash
   ( cd "$STEP6" && python3 tools/instantiate_vehicle.py --all ) || return 1
   cp -r "$STEP6/vehicles" "$DEPLOY/m5_ver2/step6/vehicles"
   ```
   (The deployed ipc's `CONFIG_PATH` walk — `ipc/../vehicles/<vid>/config.yaml` — then resolves inside the deploy tree, exactly as the source tree resolves. Keep the existing agv config copy line; forklift_io/sto_contactor still take their `--config` from the launch, which reads the SOURCE vehicles dir.)
   Also extend `stale_check`'s path mapping with a `./m5_ver2/step6/vehicles/*` case mapping back to `$STEP6/vehicles/`.
3. `spawn()` gains env stamping: change its `setsid bash -c` line to accept a leading VEHICLE value:
   ```bash
   spawn() {  # spawn <name> <vid-or-"-"> <cmd...>
       local name="$1" vid="$2" pid="" want=$(( $(wc -l < "$PIDFILE") + 1 )); shift 2
       setsid bash -c 'echo $$ >> "$1"; shift; exec "$@"' _ "$PIDFILE" \
           env ${vid:+VEHICLE=$vid} "$@" \
           > "$LOGDIR/$name.log" 2>&1 &
       for _ in {1..50}; do pid="$(sed -n "${want}p" "$PIDFILE")"
           [ -n "$pid" ] && break; sleep 0.1; done
       echo "  $name pid ${pid:-UNKNOWN, see $LOGDIR/$name.log}"
   }
   ```
   with `-` meaning no VEHICLE (the world). Guard: `${vid:+...}` must expand to nothing for `-`; set `vid=""` when `$2` is `-`.
4. The start sequence becomes world + per-vehicle sets:
   ```bash
   spawn world - ros2 launch "$STEP6/gazebo/step6_world.launch.py" "gui:=$GUI"
   sleep 5
   local IPC="$DEPLOY/m5_ver2/step6/ipc"
   local vid
   for vid in f1 f2; do
       spawn "plc_link_$vid"     "$vid" python3 "$IPC/plc_link.py"
       spawn "cmd_gate_$vid"     "$vid" python3 "$IPC/cmd_gate.py"
       spawn "cmd_mux_$vid"      "$vid" python3 "$IPC/cmd_mux.py"
       spawn "field_eval_$vid"   "$vid" python3 "$IPC/field_eval.py"
       spawn "encoder_link_$vid" "$vid" python3 "$IPC/encoder_link.py"
       spawn "sensor_link_$vid"  "$vid" python3 "$IPC/sensor_link.py"
       spawn "nav_node_$vid"     "$vid" python3 "$IPC/nav_node.py"
       spawn "hmi_$vid"          "$vid" python3 "$STEP6/hmi/hmi_node.py"
   done
   ```
   and the startup `names=(...)` check list becomes `(world plc_link_f1 cmd_gate_f1 ... hmi_f1 plc_link_f2 ... hmi_f2)` in exact spawn order (17 entries).
5. `home()` loops both vehicles: read each spawn pose from the table instead of sed-ing the launch file:
   ```bash
   for vid in f1 f2; do
       read -r x y z yaw < <(python3 -c "
   import sys; sys.path.insert(0, '$STEP6/ipc')
   from status_contract import contract
   s = contract('$vid')['spawn']
   print(s['x'], s['y'], s['z'], s['yaw'])")
       ...gz service set_pose with name \"forklift_$vid\"...
   done
   ```
   (keep the quaternion awk; the service call's `name:` becomes `forklift_$vid`).
6. Final echo names both writers:
   ```
   echo "up. On Windows, one writer per vehicle:"
   echo "  python m5_ver2\\step6\\windows\\step6.py --vehicle f1 --virtual"
   echo "  python m5_ver2\\step6\\windows\\step6.py --vehicle f2 --virtual"
   ```
7. `PATTERNS` needs no new entries (same script basenames; each pattern nominates both instances and `ours()` decides), but update its maintenance comment to say so.

- [ ] **Step 3: Static verification**

`bash -n m5_ver2/step6/step6.sh`. Then a launch dry-run inside WSL:
```bash
wsl -e bash -lc "source /opt/ros/jazzy/setup.bash && cd /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6 && python3 tools/instantiate_vehicle.py --all && python3 -c \"import sys; sys.path.insert(0,'gazebo'); import step6_world_launch\" 2>/dev/null; ros2 launch gazebo/step6_world.launch.py --print 2>&1 | head -40"
```
Expected: `--print` renders the description — two spawns, one bridge whose args contain `/f1/` and `/f2/` and no `/forklift/`, four vehicle ExecuteProcess entries. Whole step6 WSL suite still 231 passed.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/gazebo/step6_world.launch.py m5_ver2/step6/step6.sh
git commit -m "step6: one world, two vehicles - launch and lifecycle doubled"
```

---

### Task 8: The per-vehicle writer

**Files:**
- Modify: `m5_ver2/step6/windows/step6.py`
- Modify: `m5_ver2/step6/tests/test_step6_virtual_loop.py`

**Interfaces:**
- Consumes: `status_contract.PLC_PORT/SENSOR_PORT` (env-bound), Task 2.
- Produces: `step6.py --vehicle {f1|f2} [--virtual]`.

- [ ] **Step 1: The writer edits**

In `m5_ver2/step6/windows/step6.py`:

1. Argument handling at the very top of the module, BEFORE the CONFIG constants (the module docstring explains the panel; add the vehicle sentence to its usage lines):
   ```python
   import argparse
   _parser = argparse.ArgumentParser(add_help=False)
   # NOT required=True: pytest imports this module with its own argv, and
   # a hard requirement here would kill collection. The flag sets the env;
   # status_contract's import below is what refuses, loudly and by name,
   # when neither the flag nor the env named a vehicle.
   _parser.add_argument("--vehicle", choices=("f1", "f2"))
   _parser.add_argument("--virtual", action="store_true")
   _ARGS, _ = _parser.parse_known_args()
   if _ARGS.vehicle:
       os.environ["VEHICLE"] = _ARGS.vehicle
   sys.path.insert(0, os.path.normpath(os.path.join(
       os.path.dirname(os.path.abspath(__file__)), "..", "ipc")))
   from status_contract import PLC_PORT, SENSOR_PORT, VID  # noqa: E402
   ```
   (add `import os` to the imports if the sweep left it absent; `VIRTUAL = "--virtual" in sys.argv` becomes `VIRTUAL = _ARGS.virtual`.)
2. Replace the two port constants: `UDP_PORT = 5100` → `UDP_PORT = PLC_PORT`; `SENSOR_PORT = 5101` → delete the literal, the imported name IS `SENSOR_PORT` (keep every use site's spelling).
3. Panel title: `"Forklift 1 PLC Control Panel"` → `"Forklift {} PLC Control Panel".format(VID)` (the `- VIRTUAL F-PLC (model)` suffix logic stays).
4. Docstring usage lines gain `--vehicle f1`.
5. `PLC_INSTANCE = "PLC_2"` gains a per-vehicle shape for the non-virtual future: `PLC_INSTANCE = {"f1": "PLC_2", "f2": "PLC_3"}[VID]` with a one-line comment that PLC_3 is reserved, unused until a license returns, and PLCSIM has never run as f2.

- [ ] **Step 2: Parameterize the loop test**

In `m5_ver2/step6/tests/test_step6_virtual_loop.py` (it already imports `step6` — conftest set `VEHICLE=f1` before import, so import works): parameterize its tests over both port pairs by monkeypatching the module's port globals per case, e.g. a fixture:

```python
@pytest.fixture(params=["f1", "f2"])
def vehicle_ports(request, monkeypatch):
    from status_contract import contract
    c = contract(request.param)
    monkeypatch.setattr(step6, "UDP_PORT", c["plc_port"])
    monkeypatch.setattr(step6, "SENSOR_PORT", c["sensor_port"])
    return request.param
```

and thread it through the existing socket-setup helper so the listener binds `c["plc_port"]` and the feeder targets the rx socket as before (the rx socket already binds an ephemeral port — only the 5100-family listener constant changes). Each existing test function takes the fixture, so the three scenarios run per vehicle (6 runs).

- [ ] **Step 3: Run the tests + smoke**

`python -m pytest m5_ver2/step6/tests/test_step6_virtual_loop.py m5_ver2/step6/tests/test_step6.py -q` on Windows → all pass (loop tests now 6).
Headless smoke, both vehicles, Windows:
```bash
python -c "import sys; sys.argv += ['--vehicle', 'f2', '--virtual']; sys.path.insert(0, 'm5_ver2/step6/windows'); import step6; plc = step6.connect_plc(); print(step6.VID, step6.UDP_PORT, step6.SENSOR_PORT, type(plc).__name__)"
```
Expected: `f2 5120 5121 VirtualFPLC` after the VIRTUAL print. Whole step6 WSL suite → 234 passed (231 + 3 extra loop parameterizations).

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/windows/step6.py m5_ver2/step6/tests/test_step6_virtual_loop.py
git commit -m "step6: the writer takes --vehicle - one process, one PLC, per truck"
```

---

### Task 9: Live WSL-side proofs, PROOF.md, README

**Files:**
- Modify: `m5_ver2/step6/PROOF.md`, `m5_ver2/step6/CONTEXT.md`, `m5_ver2/step6/README_step6.md`

**Interfaces:**
- Consumes: everything above.
- Produces: recorded evidence for the agent-runnable subset of the spec's proof gates; an honest ledger of what remains owner-run.

- [ ] **Step 1: Bring the doubled stack up, headless, and record**

```bash
wsl -e bash -lc "cd /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6 && ./step6.sh deploy && ./step6.sh start --headless"
```
Record in PROOF.md: all 17 pids up (none "exited during startup"). Then:
```bash
wsl -e bash -lc "source /opt/ros/jazzy/setup.bash && export ROS_DOMAIN_ID=96 && ros2 topic list | grep -E '^/(f1|f2)/' | sort"
```
Record: both vehicles' namespaces present, `/forklift/...` absent. Check per-vehicle binds in the logs: `grep bound m5_ver2/step6/logs/plc_link_f*.log` → 5110 and 5120.

- [ ] **Step 2: Fail-safe state without writers — per vehicle**

With no Windows writer running, both vehicles must sit inhibited:
```bash
wsl -e bash -lc "source /opt/ros/jazzy/setup.bash && export ROS_DOMAIN_ID=96 && timeout 3 ros2 topic echo /f1/plc/status std_msgs/msg/String --once && timeout 3 ros2 topic echo /f2/plc/status std_msgs/msg/String --once"
```
Record: both FAILSAFE payloads (`motor: false`, `case: 3`, `v_limit: 300`). This is spec gate 4's silence half, per vehicle.

- [ ] **Step 3: Lifecycle, twice**

`./step6.sh stop` → records every swept pid; `ss -uln` shows 5110/5120 free; `start --headless` again clean; `stop` again. Record both cycles (spec gate 5).

- [ ] **Step 4: The honest ledger**

- `PROOF.md`: sections per spec gate. Gates 1 (RTF, from Task 4), and the subset of 4/5 above: measured, with output. Gates 2 (cross-isolation under live writers), 3 (simultaneous autonomy), 6 (mux-kill under Motor True), and gate 4's driving half: `NOT RUN — needs the two Windows writers; owner's runbook below`, each with its exact run recipe (commands, what to click, what number to record where).
- `CONTEXT.md`: add a `# Step 6 context` header section at the top stating what step6 is (two vehicles, the VEHICLES table, derived vehicles/, per-vehicle writers), that the loop-level and WSL-side evidence is in PROOF.md, and that inherited step5 references below it describe the ancestor.
- `README_step6.md`: rewrite the launch table for step6 — deploy, start, the two writer command lines, per-vehicle panels and HMIs, `--headless` note, and the vehicles/ regeneration note.

- [ ] **Step 5: Full suite one last time**

Whole step6 WSL suite → 234 passed; step5 suite untouched → 220 passed.

- [ ] **Step 6: Commit**

```bash
git add m5_ver2/step6/PROOF.md m5_ver2/step6/CONTEXT.md m5_ver2/step6/README_step6.md
git commit -m "step6: WSL-side gates measured, the rest handed to the owner's runbook"
```
