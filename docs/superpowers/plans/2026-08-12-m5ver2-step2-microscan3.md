# m5_ver2 Step 2 — three microScan3 sensors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put three SICK microScan3 safety scanners on a `forklift_ver2` model, evaluate their protective and warning fields exactly as `m5-plc-debug/microscan3.py` does, show all three on the HMI, and drive the real F-PLC's `PF_OSSD` and `WF_Clear` from the Back sensor.

**Architecture:** `m5_ver2/step2/` is a complete copy of Step 1 plus two new ROS nodes. `field_eval.py` turns three `gpu_lidar` scans into three `(pf, wf)` verdicts using the debug script's thresholds, debounce and hysteresis, selecting its field set from the PLC's monitoring case. `sensor_link.py` sends the **Back** verdict to Windows over UDP 5101, where `step2.py` — still the only PLCSIM API writer — writes `PF_OSSD` and `WF_Clear`. What the e-stop button did in Step 1, a sensed obstacle does here.

**Tech Stack:** Python 3.12, rclpy on ROS 2 Jazzy, Gazebo Harmonic 8.11 `gpu_lidar`, pythonnet + PLCSIM Advanced Runtime API on Windows, tkinter, stdlib UDP, pytest 7.4.4.

**Spec:** `docs/superpowers/specs/2026-08-12-m5ver2-step2-microscan3-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **Single-writer rule.** Exactly one process — `step2.py` on Windows — opens the PLCSIM Advanced API. Never run `step1.py` and `step2.py` together.
- **`pf` and `wf` are TRUE when the field is CLEAR.** This matches the PLC tags `PF_OSSD` ("True = protective field clear, OSSD high") and `WF_Clear`. Inverting this inverts the safety function.
- **Fail-safe direction.** No scan, no 5101 datagram, no readable monitoring case, or any exception or shutdown → fields report violated and the PLC inputs are written `False`.
- **The PLC program is ground truth.** `PLC_2`, API dir `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0`. Never change PLC logic, tags or addresses. Tag names are case-sensitive and hyphenated (`E-Stop`).
- **`ENC_A = 0`, `ENC_B = 0` every cycle**, as in Step 1, or the encoder ESTOP1 instance never enables. `PF_OSSD` and `WF_Clear` are **no longer** held True — they come from the Back sensor.
- **Field values are `microscan3.py`'s, unchanged:** `{1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}` as `(PF, WF)` in metres. Debounce `N_SCAN = 3`. Hysteresis `+0.2 m` when re-clearing. Unknown case → 3.
- **Scanner range max is 8.0 m**, not the 5.5 m the old scanners used. Case 3's 6.0 m warning field cannot clear against a 5.5 m cap.
- **Step 2 copies Step 1; it does not reference it.** `m5_ver2/step1/` is never imported from and never modified. `agv/`, `sim/` and `plc/` are never modified — `forklift_ver2/model.sdf` is a *copy*.
- **No topic name is a literal** except `/plc/status`, `/hmi/cmd_vel` and `/forklift/safety/fields`, which `config.yaml` does not own.
- **Target < 150 lines per file.** Plain Python, `rclpy`, no colcon package.
- **Every shell that runs `gz` must source `/opt/ros/jazzy/setup.bash` first.** There is no `/usr/bin/gz`. Always `export GZ_PARTITION=step2 ROS_DOMAIN_ID=92` — note **step2/92**, so Step 1 and Step 2 can never join one graph.
- **Repo root in WSL:** `/mnt/c/Users/ozkan/projects/amr-agent`. On Windows: `C:\Users\ozkan\projects\amr-agent`.
- The working tree holds unrelated in-flight owner changes: an unstaged deletion of the root `CLAUDE.md`, and untracked `m5-plc-debug/` and `plcsim_api.py`. Never stage, commit, restore or delete them. Commit with `git commit -- <paths>`.

## File Structure

| File | Responsibility |
|---|---|
| `m5_ver2/step2/windows/step2.py` | The only PLC writer. Drives `PF_OSSD`/`WF_Clear` from 5101, reads the case bits, streams state on 5100. |
| `m5_ver2/step2/ros2/status_contract.py` | What the nodes agree on. Gains `case`. |
| `m5_ver2/step2/ros2/plc_link.py` | UDP 5100 → `/plc/status` + torque-off demand. |
| `m5_ver2/step2/ros2/field_eval.py` | **New.** Three scans → three `(pf, wf)` verdicts → `/forklift/safety/fields`. |
| `m5_ver2/step2/ros2/sensor_link.py` | **New.** Back verdict → UDP 5101. |
| `m5_ver2/step2/ros2/cmd_gate.py` | Unchanged copy. |
| `m5_ver2/step2/ros2/hmi_node.py` | Joystick, e-stop lamp, drive-enable line, **three sensor lamps**. |
| `m5_ver2/step2/gazebo/forklift_ver2/model.sdf` | Copy of `agv/forklift/model.sdf` with three scanners at 8.0 m. |
| `m5_ver2/step2/gazebo/step2_world.launch.py` | gz + spawn ver2 + bridge + `forklift_io` + `sto_contactor`. |
| `m5_ver2/step2/step2.sh` | `start` / `stop`, partition `step2`, domain 92. |
| `m5_ver2/step2/tests/` | `conftest.py` plus one test file per module. |
| `m5_ver2/step2/README_step2.md`, `PROOF.md` | Run procedure and the end-to-end evidence. |

## Reference values — established, do not re-derive

| Thing | Value | Source |
|---|---|---|
| Chassis box | `1.40 × 0.90 × 0.50` at `(0, 0, 0.45)`; x ∈ [−0.70, +0.70], y ∈ [−0.45, +0.45] | `agv/forklift/model.sdf:209-218` |
| Forks | x = −1.35 | `model.sdf:820-843` |
| Front = fork end = model **−x**; vehicle-left = model **−y** | | owner's drawing + commit `ab258b2` |
| Scan config | `gpu_lidar`, 10 Hz, 275 samples, `±2.3998277` rad, range `0.10`–**`8.0`**, res `0.01` | `model.sdf:356-396`, range changed |
| Housing visual | `0.14 0.14 0.11` box, pose `0 0 -0.075` | `model.sdf:351-355` |
| World name / spawn | `warehouse` / `x=-3.00 y=-5.50 z=0.05 yaw=0.0` | Step 1 plan |
| Windows host from WSL | `172.19.176.1` | measured |

### The three sensors

| Link | Pose `x y z r p yaw` | Points |
|---|---|---|
| `safety_scanner_back_link` | `0.72 0 0.15 0 0 0` | +x, blind sector into the vehicle |
| `safety_scanner_left_link` | `-0.68 -0.46 0.15 0 0 -2.3561945` | out along the −x/−y corner diagonal |
| `safety_scanner_right_link` | `-0.68 0.46 0.15 0 0 2.3561945` | out along the −x/+y corner diagonal |

Topics: `/forklift/gz/safety_scanner_back/measurement`, `.../safety_scanner_left/measurement`, `.../safety_scanner_right/measurement`.

---

### Task 1: `m5_ver2/step2/` — the copy, and its context file

**Files:**
- Create: `m5_ver2/step2/` tree (copy of `m5_ver2/step1/`)
- Create: `m5_ver2/step2/CONTEXT.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a `step2/` tree whose 55 inherited tests pass unchanged, and the context file later tasks read.

- [ ] **Step 1: Copy the tree**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
mkdir -p m5_ver2/step2
cp -r m5_ver2/step1/windows m5_ver2/step1/ros2 m5_ver2/step1/gazebo \
      m5_ver2/step1/tests m5_ver2/step2/
cp m5_ver2/step1/step1.sh m5_ver2/step2/step2.sh
cp m5_ver2/step1/README_step1.md m5_ver2/step2/README_step2.md
git mv --help >/dev/null   # no-op; the copy is deliberate, not a move
mv m5_ver2/step2/windows/step1.py m5_ver2/step2/windows/step2.py
mv m5_ver2/step2/gazebo/step1_world.launch.py m5_ver2/step2/gazebo/step2_world.launch.py
mv m5_ver2/step2/tests/test_step1.py m5_ver2/step2/tests/test_step2.py
rm -rf m5_ver2/step2/logs m5_ver2/step2/.step1_pids
```

Do **not** copy `PROOF.md` — Step 2 writes its own.

- [ ] **Step 2: Rewire the copies' own names**

Every internal reference to `step1` becomes `step2`:

- `step2.sh` — `STEP1`→`STEP2`, `.step1_pids`→`.step2_pids`, `step1_world.launch.py`→`step2_world.launch.py`, `plc_link.py`/`cmd_gate.py`/`hmi_node.py` paths, the `m5_ver2/step1` token in `recorded()` → `m5_ver2/step2`, `GZ_PARTITION` default `step1`→**`step2`**, `ROS_DOMAIN_ID` default `91`→**`92`**, and the printed instruction naming `step1.py` → `step2.py`.
- `step2_world.launch.py` — the docstring's `step1` references.
- `tests/test_step2.py` — `import step1` → `import step2`, and every `step1.` prefix.
- `windows/step2.py` — the docstring's usage line.

**The partition and domain change is not cosmetic.** With `step1` / 91 left in place, a Step 1 stack and a Step 2 stack would share one graph and put two publishers on the same command topics, and `step2.sh stop` would sweep Step 1's processes.

- [ ] **Step 3: Confirm the copy is green and independent**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step2/tests/ -q
grep -rn "step1" m5_ver2/step2/ || echo "NO step1 REFERENCES"
```

Expected: **55 passed**, and no `step1` reference anywhere under `step2/`. A surviving reference means Step 2 depends on Step 1, which the owner's ruling forbids.

- [ ] **Step 4: Write `m5_ver2/step2/CONTEXT.md`**

Three sections, nothing else:

1. **What Step 2 adds**, in four lines: three microScan3 scanners on `forklift_ver2`; field evaluation ported from `m5-plc-debug/microscan3.py`; three HMI lamps; the Back sensor drives `PF_OSSD` and `WF_Clear`.
2. **The field logic, verbatim** — the `FIELDS` dict, `N_SCAN`, the hysteresis, the three load-bearing properties from spec §4 (TRUE means clear; no measurement means violated; unknown case selects 3).
3. **The port map:**

```markdown
| Port | Direction | Payload |
|---|---|---|
| 5100 | Windows -> WSL | estop_healthy, motor, case, ts |
| 5101 | WSL -> Windows | back sensor pf, wf, ts |
```

Do not restate the PLC tag table — `m5_ver2/CLAUDE.md` owns it and is one directory up.

- [ ] **Step 5: Commit**

```bash
git add m5_ver2/step2
git commit -m "feat(step2): copy Step 1 as the base for the sensor work

Each step runs on its own, on the owner's ruling, so this is a copy rather
than an import. The partition and domain move to step2/92 so a Step 1 and a
Step 2 stack can never share a graph or sweep each other's processes.

55 inherited tests pass unchanged and no step1 reference survives."
```

---

### Task 2: `forklift_ver2/model.sdf` — three scanners

**Files:**
- Create: `m5_ver2/step2/gazebo/forklift_ver2/model.sdf`

**Interfaces:**
- Consumes: nothing.
- Produces: three `gpu_lidar` sensors publishing `/forklift/gz/safety_scanner_{back,left,right}/measurement`, which Task 3 bridges and Task 4 consumes.

- [ ] **Step 1: Copy the model**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
mkdir -p m5_ver2/step2/gazebo/forklift_ver2
cp agv/forklift/model.sdf m5_ver2/step2/gazebo/forklift_ver2/model.sdf
```

`agv/forklift/model.sdf` is never modified.

- [ ] **Step 2: Delete the two old scanner links**

Remove `<link name="safety_scanner_front_link">` … `</link>` and `<link name="safety_scanner_rear_link">` … `</link>` in full, including their comments.

They are deleted rather than kept because the model calls the **drive end** "front" while the owner calls the **fork end** "Front" — two conventions in one file eventually wires the wrong device to the PLC.

Also remove any `<joint>` that attaches them, and any reference to `safety_scanner_front_link` / `safety_scanner_rear_link` elsewhere in the file. Search for both names afterwards and confirm zero hits.

- [ ] **Step 3: Add the three new links**

Insert where the old pair was. `back` shown in full; `left` and `right` are identical except for the `<link name>`, the `<pose>`, the `<gz_frame_id>`, the `<sensor name>` and the `<topic>`.

```xml
    <link name="safety_scanner_back_link">
      <!-- BACK in the owner's frame: the drive/counterweight end, model +x,
           centred on the rear face. Yaw 0 points the sensor x axis straight
           out, so the 85 deg blind sector is centred on 180 deg, into the
           vehicle. The owner's Front is the FORK end, model -x. -->
      <pose>0.72 0 0.15 0 0 0</pose>
      <inertial>
        <mass>1.4</mass>
        <inertia>
          <ixx>0.004</ixx><ixy>0</ixy><ixz>0</ixz>
          <iyy>0.004</iyy><iyz>0</iyz><izz>0.004</izz>
        </inertia>
      </inertial>
      <!-- Housing top face sits 20 mm BELOW the scan plane, so the scanner
           cannot see its own mounting. Visual only. -->
      <visual name="housing">
        <pose>0 0 -0.075 0 0 0</pose>
        <geometry><box><size>0.14 0.14 0.11</size></box></geometry>
        <material><ambient>0.72 0.55 0.05 1</ambient><diffuse>0.72 0.55 0.05 1</diffuse></material>
      </visual>
      <sensor name="safety_scanner_back" type="gpu_lidar">
        <pose>0 0 0 0 0 0</pose>
        <gz_frame_id>safety_scanner_back_link</gz_frame_id>
        <always_on>1</always_on>
        <update_rate>10</update_rate>
        <visualize>true</visualize>
        <!-- NON-SAFE MEASUREMENT CHANNEL. The safe channel is not here and
             is not a topic: 1oo2 is the fail-safe input card's property, not
             the simulation's, and in PLCSIM the pair collapses to one
             process-image bit (m5_ver2/CLAUDE.md section 3).

             RANGE MAX IS 8.0, NOT THE 5.5 THE OLD SCANNERS USED. The debug
             script's case 3 warning field is 6.0 m. Capped at 5.5 the test
             `d > 6.0` can never pass, so the warning field would read as
             permanently violated in the very case the system falls into when
             the monitoring case is unreadable. -->
        <topic>/forklift/gz/safety_scanner_back/measurement</topic>
        <lidar>
          <scan>
            <horizontal>
              <samples>275</samples>
              <resolution>1</resolution>
              <min_angle>-2.3998277</min_angle>
              <max_angle>2.3998277</max_angle>
            </horizontal>
            <vertical>
              <samples>1</samples>
              <resolution>1</resolution>
              <min_angle>0.0</min_angle>
              <max_angle>0.0</max_angle>
            </vertical>
          </scan>
          <range>
            <min>0.10</min>
            <max>8.0</max>
            <resolution>0.01</resolution>
          </range>
        </lidar>
      </sensor>
    </link>
```

`left`: `<pose>-0.68 -0.46 0.15 0 0 -2.3561945</pose>`, names/topic `safety_scanner_left`. Comment: *"LEFT in the owner's frame is the model's −y, because the owner's frame is the model's rotated 180 deg about z. Mounted at the fork-end corner; yaw −135 deg points the sensor out along the corner diagonal."*

`right`: `<pose>-0.68 0.46 0.15 0 0 2.3561945</pose>`, names/topic `safety_scanner_right`. Comment mirrors `left` with +y and +135 deg.

- [ ] **Step 4: Verify the file structurally**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
grep -c "gpu_lidar" m5_ver2/step2/gazebo/forklift_ver2/model.sdf
grep -c "safety_scanner_front\|safety_scanner_rear" m5_ver2/step2/gazebo/forklift_ver2/model.sdf
grep -c "<max>8.0</max>" m5_ver2/step2/gazebo/forklift_ver2/model.sdf
grep -n "safety_scanner_back\|safety_scanner_left\|safety_scanner_right" m5_ver2/step2/gazebo/forklift_ver2/model.sdf | head -20
```

Expected: `gpu_lidar` count **4** (three safety scanners plus `nav_lidar`); front/rear count **0**; `<max>8.0</max>` count **4** (three scanners plus `nav_lidar`'s pre-existing 8.0); the three new names present.

`agv/forklift/model.sdf` is not strict-XML parseable — its header comment contains `--` sequences that XML forbids — so do **not** validate with `xml.etree`. libsdformat's TinyXML2 accepts it. Task 3's launch is the real parse test.

- [ ] **Step 5: Commit**

```bash
git add m5_ver2/step2/gazebo/forklift_ver2/model.sdf
git commit -m "feat(step2): forklift_ver2 with three microScan3 scanners

Back at the drive end centred, left and right at the fork-end corners, each
yawed so its 85 degree blind sector faces into the vehicle. Placement is from
the owner's reference drawing, in the owner's frame where Front is the fork
end and the model's -x.

The old front and rear scanners are deleted rather than kept: the model called
the drive end front and the owner calls the fork end Front, and two conventions
in one file eventually wires the wrong device to the PLC.

Range goes to 8.0 m so case 3's 6.0 m warning field can clear."
```

---

### Task 3: `step2_world.launch.py` — spawn ver2, bridge three scans, and the screenshot

**Files:**
- Modify: `m5_ver2/step2/gazebo/step2_world.launch.py`

**Interfaces:**
- Consumes: Task 2's model.
- Produces: the three `/forklift/gz/safety_scanner_*/measurement` ROS topics Task 4 subscribes to.

- [ ] **Step 1: Point the launch at `forklift_ver2` and bridge the scans**

Change `_MODEL` to the local copy:

```python
_MODEL = os.path.join(_HERE, "forklift_ver2", "model.sdf")
```

Add the three scan topics to `_BRIDGE_ARGS`, gz→ROS (`[`):

```python
# The three safety scanners, gz -> ROS. sensor_msgs/msg/LaserScan is the
# ROS side of gz.msgs.LaserScan; the topic keeps its gz name so a gz topic
# list and a ros2 topic list read as one namespace.
_SCAN_TOPICS = (
    "/forklift/gz/safety_scanner_back/measurement",
    "/forklift/gz/safety_scanner_left/measurement",
    "/forklift/gz/safety_scanner_right/measurement",
)
_BRIDGE_ARGS += [
    "{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan".format(t)
    for t in _SCAN_TOPICS
]
```

These three are **not** in `config.yaml` — they are `forklift_ver2`'s own, so `_SCAN_TOPICS` is their one home. Keep the `isfile` guard from Step 1 and add `_MODEL`'s new path to it.

- [ ] **Step 2: Launch it and confirm the scans are live**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=step2 ROS_DOMAIN_ID=92
ros2 launch m5_ver2/step2/gazebo/step2_world.launch.py gui:=true
```

In a second shell with the same exports:

```bash
ros2 topic list | grep safety_scanner
ros2 topic echo --once /forklift/gz/safety_scanner_back/measurement | head -20
ros2 topic hz /forklift/gz/safety_scanner_back/measurement
```

Expected: three topics; a `LaserScan` with `angle_min ≈ -2.3998`, `angle_max ≈ 2.3998`, `range_max = 8.0`, and 275 entries in `ranges`; ~10 Hz.

**Record what a clear horizon reads.** `gz` reports a no-return as `inf`. Note whether the array holds `inf` or `8.0` — Task 4 must handle whichever it is, and guessing here is what the spec's §4.1 warning is about.

- [ ] **Step 3: Enable the lidar rays in the GUI and screenshot**

In the Gazebo GUI, open the **Visualize Lidar** plugin and select the three `/measurement` topics. Do **not** add a repeater node — `agv/forklift/launch/vehicle.launch.py:429-445` measured that the plugin resolves its anchor from the sensor entity behind the topic, so real sensor topics track the vehicle while repeated `viz/*` topics draw at the world origin. The repeater was the old clutter, not the rays.

Take **a top-down screenshot** of the vehicle with the three fans visible, framed so the fork end, the chassis and all three sensor housings are in view. Save to `assets/m5-step2-sensors/step2-topdown-three-scanners-2026-08-12.png`.

This screenshot is the owner's Adım 1 acceptance and they are away from the machine — it is the deliverable they asked for by name. Frame it so the placement can be compared against their drawing without them having to rotate the camera.

- [ ] **Step 4: Measure the RTF with three scanners and the GUI up**

```bash
gz topic -e -t /world/warehouse/stats -n 30 | grep -A1 real_time_factor | head
```

Step 1 measured 0.806 mean with the GUI and one scanner pair. Three scanners at 8.0 m on llvmpipe will cost more. Report the number; if it falls below ~0.3 the sim is not usable for a live drive and the owner needs to know before Task 8.

- [ ] **Step 5: Tear down and commit**

```bash
pkill -f "gz sim" ; pkill -f parameter_bridge ; pkill -f "step2_world"
pgrep -af "gz sim|parameter_bridge" || echo "NO ORPHANS"
git add m5_ver2/step2/gazebo/step2_world.launch.py assets/m5-step2-sensors
git commit -m "feat(step2): spawn forklift_ver2 and bridge the three scanners

The bridge carries the three scan topics gz to ROS. They are not in
config.yaml because they are forklift_ver2's own, so the launch file is their
one home.

Screenshot is the owner's acceptance for sensor placement."
```

---

### Task 4: `field_eval.py` — the microScan3 model

**Files:**
- Create: `m5_ver2/step2/ros2/field_eval.py`
- Create: `m5_ver2/step2/tests/test_field_eval.py`

**Interfaces:**
- Consumes: the three `LaserScan` topics from Task 3; `/plc/status` for `case` (Task 5 adds the field — until then the evaluator falls back to case 3, which is correct behaviour, not a stub).
- Produces: `/forklift/safety/fields` (`std_msgs/String`, JSON) and the module-level pure functions `min_range(ranges, range_max)`, `field_step(d, clear, cnt, th)`, `level(pf, wf)`, `fields_for_case(case)`.

- [ ] **Step 1: Write the failing test**

`m5_ver2/step2/tests/test_field_eval.py`:

```python
"""field_eval.py's pure decisions. No ROS graph, no Gazebo."""
import math

import field_eval

MAXR = 8.0


def test_min_range_ignores_non_returns():
    # gz reports a no-return as inf. Naive min() on [inf, inf] gives inf,
    # which compares uselessly against a threshold; on a list holding nan it
    # gives nan, which compares False against everything. Both must become
    # the range maximum first.
    assert field_eval.min_range([math.inf, math.inf], MAXR) == MAXR
    assert field_eval.min_range([math.nan, 3.0], MAXR) == 3.0
    assert field_eval.min_range([math.inf, 2.0, math.nan], MAXR) == 2.0


def test_min_range_of_an_empty_scan_is_a_violation_not_a_clear_horizon():
    # No samples at all is a broken device, not an empty room.
    assert field_eval.min_range([], MAXR) == 0.0


def test_min_range_clamps_above_the_maximum():
    assert field_eval.min_range([99.0], MAXR) == MAXR


def test_fields_for_case_matches_the_debug_script():
    assert field_eval.fields_for_case(1) == (1.0, 2.5)
    assert field_eval.fields_for_case(2) == (2.2, 3.7)
    assert field_eval.fields_for_case(3) == (4.5, 6.0)


def test_an_unreadable_case_selects_the_largest_field():
    # microscan3.py:16 and :22 - unknown means assume the most demanding.
    for bad in (0, 4, None, "2", -1):
        assert field_eval.fields_for_case(bad) == (4.5, 6.0)


def test_a_clear_field_needs_no_debounce_to_stay_clear():
    clear, cnt = field_eval.field_step(5.0, True, 0, 2.5)
    assert (clear, cnt) is not None and clear is True and cnt == 0


def test_an_intrusion_takes_three_consecutive_scans():
    clear, cnt = True, 0
    for expected_cnt in (1, 2):
        clear, cnt = field_eval.field_step(1.0, clear, cnt, 2.5)
        assert clear is True and cnt == expected_cnt
    clear, cnt = field_eval.field_step(1.0, clear, cnt, 2.5)
    assert clear is False and cnt == 0


def test_a_single_bad_scan_does_not_trip_the_field():
    clear, cnt = field_eval.field_step(1.0, True, 0, 2.5)
    assert clear is True and cnt == 1
    clear, cnt = field_eval.field_step(5.0, clear, cnt, 2.5)
    assert clear is True and cnt == 0


def test_re_clearing_needs_the_extra_hysteresis_margin():
    # Violated at 2.5; 2.6 is past the threshold but inside the +0.2 band,
    # so it must NOT re-clear.
    clear, cnt = False, 0
    for _ in range(5):
        clear, cnt = field_eval.field_step(2.6, clear, cnt, 2.5)
    assert clear is False
    for _ in range(3):
        clear, cnt = field_eval.field_step(2.8, clear, cnt, 2.5)
    assert clear is True


def test_level_ranks_protective_above_warning():
    assert field_eval.level(True, True) == "SAFE"
    assert field_eval.level(True, False) == "WARNING"
    assert field_eval.level(False, True) == "PROTECTIVE"
    assert field_eval.level(False, False) == "PROTECTIVE"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step2/tests/test_field_eval.py -v
```

Expected: a collection error, `ModuleNotFoundError: No module named 'field_eval'`. Not a skip — this project does not use `importorskip` on the module under test, because a skip reports success with zero assertions run.

- [ ] **Step 3: Write `ros2/field_eval.py`**

```python
"""field_eval.py - what a safety laser scanner does inside its own housing.

Three gpu_lidar scans in, three (pf, wf) verdicts out. The arithmetic is
m5-plc-debug/microscan3.py's, which the owner validated against the PLC;
this file ports it to ROS and does not change a threshold.

    FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   case: (PF, WF)
    N_SCAN = 3 consecutive scans, +0.20 m hysteresis when re-clearing

pf AND wf ARE TRUE WHEN THE FIELD IS CLEAR, matching the PLC tags PF_OSSD
("True = protective field clear, OSSD high") and WF_Clear. Inverting this
inverts the safety function.

THREE FAIL-SAFE DIRECTIONS, ALL OF THEM "VIOLATED"
  No scan within SCAN_STALE_S: violated. Silence is not clear.
  An empty ranges array: violated. A broken device is not an empty room.
  An unreadable monitoring case: case 3, the largest field. Not knowing
  which case applies means assuming the most demanding one.

WHAT THIS IS NOT
  Not a safety function. One software process, one scan source per device,
  no redundancy, no test pulses. No Category, no Performance Level, no SIL,
  no PFH is claimed. 1oo2 is the fail-safe input card's property and in
  PLCSIM the pair collapses to one process-image bit.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step2/ros2/field_eval.py
"""

import json
import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

import status_contract

# ----------------------------- CONFIG -----------------------------
FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   # case: (PF, WF) [m]
N_SCAN = 3                  # consecutive scans before a state change
HYSTERESIS_M = 0.20         # extra margin required to RE-CLEAR
RANGE_MAX_M = 8.0           # must match model.sdf's <max>
SCAN_STALE_S = 0.5          # five missed scans at 10 Hz
PUBLISH_HZ = 10.0
FIELDS_TOPIC = "/forklift/safety/fields"
SENSORS = ("back", "left", "right")
SCAN_TOPIC = "/forklift/gz/safety_scanner_{}/measurement"
# ------------------------------------------------------------------


def fields_for_case(case):
    """(PF, WF) thresholds. Anything unreadable selects the largest field."""
    return FIELDS.get(case if case in FIELDS else 3)


def min_range(ranges, range_max=RANGE_MAX_M):
    """Nearest real return, with non-returns treated as the horizon.

    gz reports a no-return as inf and can report nan. A naive min() over
    [inf, inf] gives inf and over a list holding nan gives nan, and neither
    compares usefully against a threshold. Both become range_max first.

    An EMPTY array is a broken device, not an empty room, so it returns 0.0
    - the violated end of the scale.
    """
    if not len(ranges):
        return 0.0
    finite = [r for r in ranges if math.isfinite(r)]
    if not finite:
        return range_max
    return min(range_max, min(finite))


def field_step(d, clear, cnt, th):
    """One scan against one threshold. Returns (clear, count).

    Verbatim from microscan3.py: the threshold is th while clear and
    th + HYSTERESIS_M while violated, so re-clearing needs the extra margin
    and a target sitting exactly on the contour cannot chatter.
    """
    raw = d > (th if clear else th + HYSTERESIS_M)
    cnt = cnt + 1 if raw != clear else 0
    return (raw, 0) if cnt >= N_SCAN else (clear, cnt)


def level(pf, wf):
    """Display level. Protective outranks warning."""
    if not pf:
        return "PROTECTIVE"
    return "SAFE" if wf else "WARNING"


class Device:
    """One scanner's latched field state."""

    def __init__(self):
        self.pf = self.wf = False      # starts violated, like a cold OSSD
        self.pfc = self.wfc = 0
        self.last_scan = None

    def update(self, d, pf_th, wf_th, now):
        self.pf, self.pfc = field_step(d, self.pf, self.pfc, pf_th)
        self.wf, self.wfc = field_step(d, self.wf, self.wfc, wf_th)
        self.last_scan = now

    def go_violated(self):
        self.pf = self.wf = False
        self.pfc = self.wfc = 0


class FieldEval(Node):

    def __init__(self):
        super().__init__("field_eval")
        self.devices = {name: Device() for name in SENSORS}
        self.ranges = {name: None for name in SENSORS}
        self.case = 3
        self.pub = self.create_publisher(String, FIELDS_TOPIC, 10)
        for name in SENSORS:
            self.create_subscription(
                LaserScan, SCAN_TOPIC.format(name),
                lambda msg, n=name: self.cb_scan(n, msg), 10)
        self.create_subscription(
            String, status_contract.STATUS_TOPIC, self.cb_status, 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)
        self.get_logger().info(
            "fields {} | debounce {} scans | hysteresis {:.2f} m".format(
                FIELDS, N_SCAN, HYSTERESIS_M))

    def cb_scan(self, name, msg):
        self.ranges[name] = msg.ranges

    def cb_status(self, msg):
        parsed = status_contract.parse_status(msg.data.encode())
        self.case = parsed.get("case") if parsed else None

    def tick(self):
        now = time.monotonic()
        pf_th, wf_th = fields_for_case(self.case)
        report = {"case": self.case if self.case in FIELDS else 3,
                  "pf_th": pf_th, "wf_th": wf_th, "ts": now}
        for name in SENSORS:
            dev = self.devices[name]
            raw = self.ranges[name]
            if raw is None or status_contract.is_stale(
                    dev.last_scan, now, SCAN_STALE_S):
                dev.go_violated()
                d = 0.0
            else:
                d = min_range(raw)
                dev.update(d, pf_th, wf_th, now)
            report[name] = {"pf": dev.pf, "wf": dev.wf, "d": round(d, 3),
                            "level": level(dev.pf, dev.wf)}
            self.ranges[name] = None
        self.pub.publish(String(data=json.dumps(report)))


def main():
    rclpy.init()
    node = FieldEval()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step2/tests/test_field_eval.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Prove it against the live sim**

Bring up Task 3's launch, then:

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=step2 ROS_DOMAIN_ID=92
python3 m5_ver2/step2/ros2/field_eval.py &
timeout 3 ros2 topic echo /forklift/safety/fields
```

Expected on a clear spawn: `back`, `left`, `right` all `"level": "SAFE"` once the debounce has passed, `"case": 3` (no `/plc/status` publisher yet, which is the correct fallback), `d` near 8.0 where nothing is in range.

Then drive the forklift toward a rack and watch a level go `SAFE → WARNING → PROTECTIVE`. Paste the transition.

- [ ] **Step 6: Commit**

```bash
git add m5_ver2/step2/ros2/field_eval.py m5_ver2/step2/tests/test_field_eval.py
git commit -m "feat(step2): field_eval.py, the microScan3 model

The debug script's arithmetic ported to ROS with no threshold changed: three
field pairs by monitoring case, three-scan debounce, 0.20 m hysteresis on
re-clearing.

Three fail-safe directions all resolve to violated - a stale scan, an empty
ranges array, and an unreadable case. A no-return ray is inf and becomes the
horizon before any minimum is taken; the naive min() would have made a clear
horizon read as an intrusion."
```

---

### Task 5: the monitoring case reaches the vehicle

**Files:**
- Modify: `m5_ver2/step2/ros2/status_contract.py`
- Modify: `m5_ver2/step2/ros2/plc_link.py`
- Modify: `m5_ver2/step2/windows/step2.py`
- Modify: `m5_ver2/step2/tests/test_status_contract.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `/plc/status` carrying `case` (int 1–3), which Task 4's `field_eval` already reads and Task 6's HMI may display.

- [ ] **Step 1: Write the failing test**

Add to `m5_ver2/step2/tests/test_status_contract.py`:

```python
def test_parse_status_accepts_the_case_field():
    msg = status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": 2, "ts": 1.0}')
    assert msg["case"] == 2


def test_parse_status_rejects_a_packet_with_no_case():
    # case joined the contract in Step 2; a Step 1 sender is not a Step 2 one.
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "ts": 1.0}') is None


def test_parse_status_rejects_a_non_integer_case():
    assert status_contract.parse_status(
        b'{"estop_healthy": true, "motor": true, "case": "2", "ts": 1.0}') is None


def test_failsafe_carries_the_largest_field_case():
    # Not knowing the case means assuming the most demanding one.
    assert status_contract.FAILSAFE["case"] == 3
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python3 -m pytest m5_ver2/step2/tests/test_status_contract.py -v
```
Expected: the four new tests fail — `KeyError: 'case'` on the first, and the second passes trivially only if `_REQUIRED_KEYS` already rejects it, which it does not.

- [ ] **Step 3: Add `case` to the contract**

In `status_contract.py`: add `"case"` to `_REQUIRED_KEYS`; add `"case": 3` to `FAILSAFE`; and in `parse_status`, after the existing bool checks, add

```python
    if not isinstance(msg["case"], int) or isinstance(msg["case"], bool):
        return None
```

`isinstance(True, int)` is True in Python, so the `bool` exclusion is required or a JSON `true` would pass as a case.

In `plc_link.py`: nothing changes — it republishes the parsed dict as received, so `case` flows through automatically. Confirm that by reading the publish path rather than assuming it.

In `windows/step2.py`: read the two case bits every cycle and put the decoded value on the wire.

```python
    case = ((1 if plc.ReadBool("CASE_B0") else 0)
            + (2 if plc.ReadBool("CASE_B1") else 0))
```

`CASE_B0` is bit 0 and `CASE_B1` is bit 1, so the pattern `01` is case 1, `10` is case 2 and `11` is case 3. Pattern `00` is deliberately invalid in the F-program (`m5_ver2/CLAUDE.md` §3.2) and decodes here to `0`, which `fields_for_case` maps to case 3 — the correct fallback, and it must not be "corrected" to 1.

Add `case` to `status_payload`.

- [ ] **Step 4: Run the whole suite**

```bash
python3 -m pytest m5_ver2/step2/tests/ -q
```
Expected: all green. The Step 1 tests that assert on `parse_status` rejecting packets will still pass; any that construct a three-key packet and expect acceptance must gain a `case` field — fix those tests, do not relax `_REQUIRED_KEYS`.

- [ ] **Step 5: Commit**

```bash
git add m5_ver2/step2/ros2/status_contract.py m5_ver2/step2/windows/step2.py m5_ver2/step2/tests/test_status_contract.py
git commit -m "feat(step2): carry the PLC's monitoring case to the vehicle

Step 1 left CASE_B0 and CASE_B1 deliberately unconsumed. field_eval needs
them to pick a field pair, so they join the 5100 contract.

The invalid 00 pattern decodes to 0 and falls through to case 3, the largest
field. That is the fail-safe direction and is not a bug to correct."
```

---

### Task 6: three sensor lamps on the HMI

**Files:**
- Modify: `m5_ver2/step2/ros2/hmi_node.py`
- Modify: `m5_ver2/step2/tests/test_hmi_node.py`

**Interfaces:**
- Consumes: `/forklift/safety/fields` from Task 4.
- Produces: the module-level pure function `sensor_lamp(name, level)` returning `(colour, text)`.

- [ ] **Step 1: Write the failing test**

```python
def test_sensor_lamp_texts_and_colours():
    assert hmi_node.sensor_lamp("Back", "SAFE") == (
        hmi_node.LAMP_GREEN, "Back Sensor : Safe")
    assert hmi_node.sensor_lamp("Back", "WARNING") == (
        hmi_node.LAMP_ORANGE, "Back Sensor : Warning Field")
    assert hmi_node.sensor_lamp("Back", "PROTECTIVE") == (
        hmi_node.LAMP_RED, "Back Sensor : Protective Field")


def test_an_unknown_level_shows_the_safe_display():
    # A display that has lost its source must not show a comfortable state.
    colour, text = hmi_node.sensor_lamp("Left", None)
    assert colour == hmi_node.LAMP_RED
    assert text == "Left Sensor : Protective Field"


def test_every_sensor_gets_its_own_name_in_the_text():
    for name in ("Back", "Left", "Right"):
        _, text = hmi_node.sensor_lamp(name, "SAFE")
        assert text.startswith(name + " Sensor")
```

- [ ] **Step 2: Run it to verify it fails**

Expected: `AttributeError: module 'hmi_node' has no attribute 'sensor_lamp'`.

- [ ] **Step 3: Implement**

Add the colours beside the existing `LAMP_RED` / `LAMP_NEUTRAL`:

```python
LAMP_GREEN = "#2e7d32"
LAMP_ORANGE = "#ef6c00"
```

and the pure function:

```python
_LEVEL_LAMP = {
    "SAFE": (LAMP_GREEN, "Safe"),
    "WARNING": (LAMP_ORANGE, "Warning Field"),
    "PROTECTIVE": (LAMP_RED, "Protective Field"),
}


def sensor_lamp(name, level):
    """(colour, text) for one sensor lamp.

    An unknown level - no message yet, a stale topic, a level this build does
    not know - shows PROTECTIVE. A display that has lost its source must not
    show a comfortable state.
    """
    colour, word = _LEVEL_LAMP.get(level, _LEVEL_LAMP["PROTECTIVE"])
    return (colour, "{} Sensor : {}".format(name, word))
```

Wire three `tk.Label` widgets under the existing enable line, one per sensor, and a subscription:

```python
        self.fields = {}
        self.create_subscription(
            String, "/forklift/safety/fields", self.cb_fields, 10)
```

```python
    def cb_fields(self, msg):
        try:
            self.fields = json.loads(msg.data)
        except ValueError:
            self.fields = {}
```

and in the existing `refresh()`, after the two Step 1 indicators:

```python
        for key, widget in self.sensor_lamps.items():
            entry = self.fields.get(key.lower())
            lvl = entry.get("level") if isinstance(entry, dict) else None
            colour, text = sensor_lamp(key, lvl)
            widget.configure(bg=colour, fg="white", text=text)
```

`self.fields` is cleared to `{}` on a stale `/forklift/safety/fields` by the same staleness rule that already governs `/plc/status`, so a dead `field_eval` shows three red lamps rather than three frozen ones.

- [ ] **Step 4: Run the tests**

```bash
python3 -m pytest m5_ver2/step2/tests/test_hmi_node.py -v
```
Expected: all green, the three new ones included.

- [ ] **Step 5: See it**

Bring up the launch and `field_eval`, start the HMI, and confirm five indicators: the e-stop lamp, the drive-enable line, and three sensor lamps reading `Safe`. Drive toward a rack and screenshot each of `Warning Field` and `Protective Field`. Save under `assets/m5-step2-sensors/`.

- [ ] **Step 6: Commit**

```bash
git add m5_ver2/step2/ros2/hmi_node.py m5_ver2/step2/tests/test_hmi_node.py assets/m5-step2-sensors
git commit -m "feat(step2): three sensor lamps on the HMI

Safe green, Warning Field orange, Protective Field red, one lamp per scanner.
An unknown level shows protective: a display that has lost its source must not
show a comfortable state, which is the rule Step 1 arrived at the hard way."
```

---

### Task 7: `sensor_link.py` and the PLC path

**Files:**
- Create: `m5_ver2/step2/ros2/sensor_link.py`
- Create: `m5_ver2/step2/tests/test_sensor_link.py`
- Modify: `m5_ver2/step2/windows/step2.py`

**Interfaces:**
- Consumes: `/forklift/safety/fields` from Task 4.
- Produces: UDP 5101 datagrams `{"pf": bool, "wf": bool, "ts": float}` that `step2.py` consumes; and `back_payload(fields_json)` returning `bytes | None`.

- [ ] **Step 1: Write the failing test**

```python
"""sensor_link.py's wire format. No socket is opened."""
import json

import sensor_link


def _fields(pf, wf):
    return json.dumps({"case": 3, "back": {"pf": pf, "wf": wf, "level": "SAFE"},
                       "left": {}, "right": {}, "ts": 1.0})


def test_back_payload_carries_exactly_the_three_wire_keys():
    msg = json.loads(sensor_link.back_payload(_fields(True, False)).decode())
    assert set(msg) == {"pf", "wf", "ts"}
    assert msg["pf"] is True and msg["wf"] is False


def test_only_the_back_sensor_reaches_the_wire():
    # The F-PLC has one sensor input configured. Left and right are HMI-only.
    msg = json.loads(sensor_link.back_payload(_fields(True, True)).decode())
    assert "left" not in msg and "right" not in msg


def test_a_report_without_back_sends_nothing():
    assert sensor_link.back_payload(json.dumps({"left": {}, "ts": 1.0})) is None


def test_unparseable_input_sends_nothing():
    assert sensor_link.back_payload("{garbage") is None


def test_a_non_boolean_verdict_sends_nothing():
    bad = json.dumps({"back": {"pf": 1, "wf": False}, "ts": 1.0})
    assert sensor_link.back_payload(bad) is None
```

Sending nothing is safe: `step2.py`'s own timeout then trips within `SENSOR_STALE_S`.

- [ ] **Step 2: Run it to verify it fails**

Expected: `ModuleNotFoundError: No module named 'sensor_link'`.

- [ ] **Step 3: Write `ros2/sensor_link.py`**

```python
"""sensor_link.py - the Back scanner's verdict, to the PLC writer.

Subscribes /forklift/safety/fields and sends the BACK device's (pf, wf) to
Windows over UDP 5101, where step2.py writes PF_OSSD and WF_Clear.

ONLY THE BACK SENSOR. The F-PLC has one sensor input configured, so left and
right are HMI-only in this step. That is the owner's constraint, not a
simplification, and this file is where it is enforced.

SENDING NOTHING IS THE SAFE FAILURE. An unparseable report, a missing back
entry or a non-boolean verdict all send no datagram, and step2.py's own
timeout then writes both inputs False. This file never invents a verdict.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step2/ros2/sensor_link.py
"""

import json
import socket
import subprocess
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# ----------------------------- CONFIG -----------------------------
UDP_TARGET = None       # None -> the WSL default gateway, i.e. the Windows host
UDP_PORT = 5101
FIELDS_TOPIC = "/forklift/safety/fields"
# ------------------------------------------------------------------


def resolve_udp_target(configured=UDP_TARGET):
    """The Windows host, discovered rather than hard-coded.

    From WSL, Windows is the default route's gateway. It is 172.19.176.1
    today and it moves when the WSL network is rebuilt, so discovering it
    each run is the difference between a script that works and one that
    breaks silently later.
    """
    if configured:
        return configured
    out = subprocess.check_output(
        ["ip", "route", "show", "default"], text=True, timeout=10)
    parts = out.split()
    if "via" not in parts:
        raise RuntimeError("no default route: cannot find the Windows host")
    return parts[parts.index("via") + 1]


def back_payload(fields_json):
    """The 5101 wire format, or None if the report cannot be trusted."""
    try:
        report = json.loads(fields_json)
    except (ValueError, TypeError):
        return None
    back = report.get("back") if isinstance(report, dict) else None
    if not isinstance(back, dict):
        return None
    if not isinstance(back.get("pf"), bool) or not isinstance(back.get("wf"), bool):
        return None
    return json.dumps({"pf": back["pf"], "wf": back["wf"],
                       "ts": time.monotonic()}).encode()


class SensorLink(Node):

    def __init__(self):
        super().__init__("sensor_link")
        self.target = resolve_udp_target()
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.create_subscription(String, FIELDS_TOPIC, self.cb_fields, 10)
        self.get_logger().info(
            "back scanner -> {}:{}".format(self.target, UDP_PORT))

    def cb_fields(self, msg):
        payload = back_payload(msg.data)
        if payload is not None:
            self.tx.sendto(payload, (self.target, UDP_PORT))


def main():
    rclpy.init()
    node = SensorLink()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.tx.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Teach `step2.py` to receive 5101**

Add to its CONFIG:

```python
SENSOR_PORT = 5101
SENSOR_STALE_S = 0.40     # four missed sends at the 10 Hz evaluation rate
```

Bind a non-blocking UDP socket on `0.0.0.0:5101` at startup, drain it each cycle keeping the newest trusted datagram, and replace Step 1's unconditional writes:

```python
            # STEP 1 WROTE THESE TRUE UNCONDITIONALLY, BECAUSE THEY WERE A
            # PRECONDITION AND NOT THE SUBJECT. HERE THEY ARE THE SUBJECT.
            plc.WriteBool("PF_OSSD", sensor_pf)
            plc.WriteBool("WF_Clear", sensor_wf)
```

The staleness rule is not optional:

```python
            if now - last_sensor_rx >= SENSOR_STALE_S:
                sensor_pf = sensor_wf = False
```

with `last_sensor_rx` starting at `-inf` so nothing is enabled before the first datagram. A dead `sensor_link`, a dead `field_eval` or a dead Gazebo must all drop `PF_OSSD`; holding the last value would leave the vehicle enabled with nothing watching the field.

`ENC_A`, `ENC_B` and the `E-Stop`/`Acknowledge` handling are unchanged. The `finally` gains nothing — it already writes `PF_OSSD` and `WF_Clear` False.

Print the sensor state on the status line so the operator can see it: `E-Stop=… Motor=… PF=… WF=…`.

- [ ] **Step 5: Run the tests and prove the link**

```bash
python3 -m pytest m5_ver2/step2/tests/ -q
```

Then, with the PLC in RUN and the stack up, watch `step2.py`'s status line while driving toward a rack: `PF` must go False as the level reaches `PROTECTIVE`, and `Motor` must drop. Kill `sensor_link` while clear and confirm `PF` goes False within ~0.42 s.

- [ ] **Step 6: Commit**

```bash
git add m5_ver2/step2/ros2/sensor_link.py m5_ver2/step2/tests/test_sensor_link.py m5_ver2/step2/windows/step2.py
git commit -m "feat(step2): the Back scanner drives PF_OSSD and WF_Clear

Step 1 wrote both inputs True unconditionally because they were a
precondition and not the subject. Here they are the subject: an obstacle in
the protective field stops the vehicle through the same chain the e-stop
button used, and the stop originates in Gazebo.

step2.py owns a timeout on 5101 rather than trusting the sender. That is the
hole Step 1's review found in cmd_gate - a consumer trusting a topic because
the producer was designed never to fall silent."
```

---

### Task 8: `step2.sh`, `README_step2.md`, and the end-to-end proof

**Files:**
- Modify: `m5_ver2/step2/step2.sh`, `m5_ver2/step2/README_step2.md`
- Create: `m5_ver2/step2/PROOF.md`

**Interfaces:**
- Consumes: everything.
- Produces: the owner's evidence.

- [ ] **Step 1: Add the two new nodes to `step2.sh`**

`spawn field_eval` and `spawn sensor_link` after `plc_link`, and add `field_eval.py` and `sensor_link.py` to `PATTERNS` — the script's own comment says anything added to the stack must be added there or `stop` orphans it and still prints "down."

Order matters: `field_eval` before `sensor_link`, so the link never sends a verdict from a device that has not yet been evaluated.

- [ ] **Step 2: Test start/stop with the new nodes**

```bash
./m5_ver2/step2/step2.sh start
pgrep -af "field_eval.py|sensor_link.py"
./m5_ver2/step2/step2.sh stop
pgrep -af "gz sim|parameter_bridge|forklift_io|sto_contactor|plc_link|cmd_gate|hmi_node|field_eval|sensor_link" || echo "NO ORPHANS"
```

- [ ] **Step 3: Update `README_step2.md`**

Change from Step 1's: the run order gains nothing (the script starts the new nodes), but add

- the three sensor lamps and what each colour means;
- the field table by monitoring case;
- that the scanners reach 8.0 m and why;
- a new **not a bug** row: with `field_eval` running but Gazebo not yet publishing, all three lamps read `Protective Field` — that is the fail-safe display, not a fault;
- a second: `Motor` will not energise while an obstacle sits in the Back protective field, no matter how many times `a` is typed. That is the safety program working.

- [ ] **Step 4: Run the owner's five acceptance steps and write `PROOF.md`**

Same shape as Step 1's `PROOF.md` — a table, step / input / expected / measured, no prose. The owner asked for "few words, much work".

| # | Step | Evidence required |
|---|---|---|
| 1 | Three sensors placed | top-down screenshot against the drawing |
| 2 | Datasheet-faithful scans | `angle_min/max`, `range_max`, sample count, rate, from a live echo |
| 3 | Rays visible and clean | screenshot, plus the RTF cost |
| 4 | Lamps transition in a live drive | screenshot per level, with the measured `d` |
| 5 | Back sensor drives the PLC | `Motor` drops on a protective intrusion, timed |

**Assert the stop the way Step 1 did:** never from stillness alone. Each stop needs the terminal `/forklift/gz/actuator/traction_cmd` at 0.0, `/forklift/safety/torque_off_applied` true with `sto_contactor` confirmed alive, and a pose sampled before and after.

Every number measured in that run. Do not carry a figure over from Step 1 or from an earlier task's report.

- [ ] **Step 5: Commit and stop**

```bash
git add m5_ver2/step2/step2.sh m5_ver2/step2/README_step2.md m5_ver2/step2/PROOF.md
git commit -m "test(step2): prove the sensor chain end to end through the real PLC"
```

Print the five acceptance rows and stop. **Do not begin Step 3.**

---

## Self-Review

**Spec coverage.** §3 verified transport → Task 7's 5101 use; §4 field logic → Task 4; §4.1 non-finite ranges and staleness → Task 4 Steps 1 and 3; §4.2 1oo2 → Task 2's sensor comment and Task 4's docstring, with no code claiming redundancy; §4.3 range 8.0 → Task 2; §5.1 old scanners deleted → Task 2 Step 2; §5.2 geometry → Task 2 Step 3; §6 architecture → Tasks 3–7; §6.1 the behavioural change → Task 7 Step 4; §6.2 `step2.py`'s timeout → Task 7 Step 4; §7 components → the File Structure table; §7.1 copy → Task 1; §8 GUI → Task 6; §9 ray visualisation → Task 3 Step 3; §10 port map → Tasks 5 and 7; §11 out of scope → nothing implements it; §12 acceptance → Task 8.

**Type consistency.** `min_range(ranges, range_max)` → float. `field_step(d, clear, cnt, th)` → `(bool, int)`, same order everywhere. `level(pf, wf)` → one of `"SAFE"`, `"WARNING"`, `"PROTECTIVE"`, and Task 6 consumes exactly those three strings. `fields_for_case(case)` → `(pf_th, wf_th)`. `back_payload(fields_json)` → `bytes | None`. `sensor_lamp(name, level)` → `(colour, text)`.

**The one cross-task coupling, stated.** Task 4 imports `status_contract` for `parse_status`, `is_stale` and `STATUS_TOPIC`, exactly as `cmd_gate` and `hmi_node` already do. Task 5 adds `case` to that module, so Task 4's `cb_status` gets the field without a change — but Task 4 is written and tested *before* Task 5 lands, and its fallback to case 3 is what makes that ordering safe rather than broken.

**Known gap, deliberate.** No test covers `field_eval`'s ROS wiring — the subscriptions, the timer, the per-device latch across ticks. The pure functions are covered and the live check in Task 4 Step 5 exercises the rest. If a fix round has budget, a stub-driven wiring test in the shape of Step 1's `test_hmi_node.py` wiring guards is the thing to add.
