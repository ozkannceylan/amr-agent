# RUNBOOK — start to finish

Two systems run from this repo. **The fleet cell (M6)** — four
forklifts under a VDA 5050 fleet manager — is the current one and comes
first. **The single M5 vehicle** with the real TIA/PLCSIM safety PLC
follows, unchanged. Two machines share the work either way: **Windows**
runs the PLC side (real or virtual) and the one process allowed to
write to it; **WSL2** runs Gazebo, ROS 2 and the vehicle stack.

---

## The fleet cell (M6) — quickstart

No PLCSIM needed here: each truck gets a **virtual F-PLC** on the
Windows side — the same chain, the same verdicts. Every WSL shell
below wants `source /opt/ros/jazzy/setup.bash` and
`export ROS_DOMAIN_ID=96` first (`m6.sh` exports the domain — and the
FastDDS loopback profile, see the note at the end — for its own
children on its own).

**Once:**

```bash
bash m6/tools/install_broker.sh     # vendors mosquitto into ~/.local (this WSL has no sudo)
bash m6/m6.sh deploy                # freeze the vehicle image the trucks run from
```

Re-run `deploy` after **any** change under `m6/ipc/` or `m6/windows/`.
The trucks run the frozen image, not the source: a stale image refuses
new work in ways that look exactly like fleet bugs (measured 2026-08-25
— four fresh doors rejected every order carrying the new pick action,
and the fleet re-offered the task in a 2 s loop for as long as anyone
watched).

**Every run:**

```bash
# 1 · WSL — the world, four vehicle stacks, broker and fleet manager
export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA   # GPU lidars; without these, four trucks fall to ~0.2 RTF
bash m6/m6.sh start --headless        # drop --headless for the Gazebo window

# 2 · WSL — is this boot actually delivering? (~30 s, parallel probes)
bash m6/tools/preflight.sh            # must end "preflight: OK";
                                      # if not: m6.sh stop, start again —
                                      # never time, tape or gate on a failed boot

# 3 · Windows — one writer per truck (ctl ports 5910/5920/5930/5940 for f1..f4)
python m6\windows\m6.py --vehicle f1 --virtual                                       # the owner's panel, or:
python m6\tools\scripted_writer.py --vehicle f1 --virtual --ctl-port 5910 --auto-reset   # the scripted stand-in (recordings)
# panel: click RESET once per truck; --auto-reset presses it for you

# 4 · WSL — every cab to AUTOMATIC (or click Auto on each HMI window)
python3 m6/tools/all_auto.py

# 5 · Work
python3 m6/fleet/fleet_cli.py submit S1 S8            # one transport
python3 m6/fleet/fleet_cli.py demo --duration 600 --in-flight 4 --seed 7   # a whole shift
python3 m6/fleet/fleet_cli.py status --watch          # the operator's screen

# 6 · Film it (optional): floor + operator screen + the VDA 5050 wire, one file
python3 m6/tools/record_e2e.py --out run.mp4 --seconds 500 --fps 10   # fps 10 = true plant speed

# 7 · Down
bash m6/m6.sh stop
```

The deep runbook — every step with its reasons and its measured
failure modes — is [`m6/README_m6.md`](m6/README_m6.md); the evidence
ledger is [`m6/PROOF.md`](m6/PROOF.md).

**DDS note.** `m6.sh` pins FastDDS to loopback-unicast discovery
([`m6/tools/fastdds_loopback.xml`](m6/tools/fastdds_loopback.xml)):
this rig's WSL multicast path has died mid-session before and took
arbitrary topics with it. Under unicast discovery a *fresh* CLI
participant needs 10–20 s to walk the ~40-node mesh — `preflight.sh`
and `all_auto.py` already wait that long; your own one-off `ros2 topic`
probes should too.

---

## The single vehicle (M5), start to finish

The original system, unchanged — TIA Portal, S7-PLCSIM Advanced and
one truck. Deeper reference:
[`m5_ver2/step5/README_step5.md`](m5_ver2/step5/README_step5.md)
(run order, field contract, "Not a bug" table, CONFIG). Evidence:
[`m5_ver2/step5/PROOF.md`](m5_ver2/step5/PROOF.md).

---

## 0. Prerequisites (once)

**Windows**
- TIA Portal V20 with STEP 7 Safety V20. The TIA project itself ships in
  this repo — restore
  [`plc/forklift-safety/amr-agent-fplc-v20.zap20`](plc/forklift-safety/amr-agent-fplc-v20.zap20)
  (Project → Retrieve in TIA Portal).
  [`safety_summary.pdf`](safety_summary.pdf) is a Safety Administration
  printout of that program's lineage. The tag table below is the
  contract; the collective F-signature changes whenever the F-program is
  edited (the last one recorded in this repo's evidence is `29FD2C52`,
  [docs/VALIDATION-M5.md](docs/VALIDATION-M5.md), 2026-08-10 — before
  the right/left scanner ESTOP1 instances were added).
- S7-PLCSIM Advanced 6.0 (API DLLs under
  `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0`).
- 64-bit Python 3 with `pythonnet` (`pip install pythonnet`).

**WSL2 (Ubuntu 24.04)**
- ROS 2 Jazzy with the Gazebo vendor packages and `ros_gz`.
- This repo at `/mnt/c/Users/<you>/projects/amr-agent`.

## 1. The PLC half (Windows, by hand)

1. Start a PLCSIM Advanced instance named **`PLC_2`** from the Control
   Panel. The name matters: API error `-4 (DoesNotExist)` means the
   instance is not running or is named something else.
2. From TIA Portal, download the standard and safety program and put the
   CPU in **RUN**.

Tag names and addresses are the contract and never change:

| Tag | Addr | Meaning |
|---|---|---|
| `E-Stop` | %I0.0 | True = chain healthy, False = pressed |
| `PF_OSSD` / `_right` / `_left` | %I0.1 / .3 / .5 | protective field clear, per scanner |
| `WF_Clear` / `_right` / `_left` | %I0.2 / .4 / .6 | warning field clear, per scanner |
| `Acknowledge` | %I15.0 | reset, rising edge required |
| `ENC_A` / `ENC_B` | %IW100 / %IW102 | encoder channels, mm/s |
| `Motor` | %Q9.0 | the drive enable — the F-program's verdict |
| `CASE_B0` / `CASE_B1` | %Q9.1 / .2 | monitoring case, binary |
| `V_Limit` | %MW100 | speed ceiling mm/s (1500 fields clear, 300 warned) |

## 2. The vehicle half (WSL)

```bash
cd /mnt/c/Users/<you>/projects/amr-agent
./m5_ver2/step5/step5.sh deploy    # freeze the vehicle software + manifest
./m5_ver2/step5/step5.sh start     # warehouse + forklift + HMI (~7 s)
```

Nine pid lines print; a `WARNING: <name> exited during startup` sends you
to that log under `m5_ver2/step5/logs/`. Two windows appear: **Gazebo**
(warehouse, ten painted stations, the forklift in the dock aisle) and the
**HMI** (joystick left, warehouse sketch right). `start --headless`
skips the Gazebo window.

If `start` prints a STALE banner, the source has changed since the last
deploy — the vehicle honestly runs the old frozen copy until you rerun
`deploy`. That is the deploy exercise working, not a fault.

## 3. The panel (Windows)

```powershell
cd C:\Users\<you>\projects\amr-agent
python m5_ver2\step5\windows\step5.py
```

A control panel opens — PUSH/RELEASE EMERGENCY STOP, RESET, encoder
fault buttons, a live status line. Press **RESET once**: the ESTOP1
blocks demand one acknowledge after every startup (`ACK_NEC`), and every
stack restart trips the latch again (the sensor link goes silent during
the bounce, which the fail-safe direction reads as a demand). The lamp
turns **MOTOR ENABLED**.

## 4. Drive

**Teleop** — mode selector on *Teleop* (the default): drag the joystick.
Forks lead. Steering stays live through a safety stop on purpose — it is
how you tell a stop from a dead HMI.

**Autonomous** — mode selector on *Auto* (the knob greys out), click a
station on the sketch, press **GO**. The route draws, the truck drives
it — reverse-out first when it is parked nose-in at a rack. **STOP**
cancels; switching back to *Teleop* mid-drive cancels too, instantly.
Arrivals are within 0.25 m at open stations, 0.80 m at the six
short-spur rack faces — the truck's own turning circle sets that limit,
and [`PROOF.md`](m5_ver2/step5/PROOF.md) carries the measured runs.

Near racks the PLC drops `V_Limit` to 300 mm/s and the truck creeps:
that is the warning field working. A protective-field trip stops it
outright and holds until the cause clears **and** RESET is pressed.

## 5. Down

```bash
./m5_ver2/step5/step5.sh stop      # sweeps only this stack's processes
```

Close the panel window (its exit writes the trip values — the next
session starts latched, as intended). PLCSIM is yours: only you stop the
PLC, from its Control Panel.

Useful extras:

```bash
./m5_ver2/step5/step5.sh home      # teleport the truck to spawn (plant only;
                                   # PLC latches stay latched - RESET clears)
# the test suite (WSL):
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step5/tests/ -q     # 195 passed, 0 skipped
```

## When something looks wrong

Read the **Not a bug** table in
[`m5_ver2/step5/README_step5.md`](m5_ver2/step5/README_step5.md) before
debugging — the red HMI at startup, the latch surviving an e-stop
release, the creep near racking and the STALE banner are all the system
telling the truth.
