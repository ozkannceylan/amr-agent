# Step 4 context

The file the next step reads first. `m5_ver2/CLAUDE.md` holds the PLC tag
table and the working agreements; this page holds what Steps 1 to 3 added on
top and what a Step 4 implementer must not break.

## What each step added

| Step | Added | Proved, against the live `PLC_2` |
|---|---|---|
| 1 | E-Stop chain, HMI joystick, command gate | `step1/PROOF.md`, 8 of 8 |
| 2 | Three microScan3 scanners, field evaluation, the monitoring case | `step2/PROOF.md`, 5 of 5 |
| 3 | Two encoder reading channels, fault injection | `step4/PROOF.md`, 6 of 6 |

Each step is a **copy** of the one before. That is the owner's ruling so
every step runs on its own; the cost is that a fix must be made in the copy
being worked on, and earlier copies are left frozen.

**After `cp -r stepN stepN+1`, run `diff -r stepN stepN+1` and read every line
the rename touched.** The whole-branch review found the code never diverged
between copies — every constant identical, `git log` on the earlier copies
empty — but the *prose* did, because a `sed` turned four statements from
stale into confidently wrong. One of them was executable: a README telling
the operator the wrong `ROS_DOMAIN_ID`.

## The three chains that reach `Motor`

All three are ESTOP1 instances in the F-program and `Motor` is their AND. A
demand **latches**: clearing the cause does not re-enable, an `Acknowledge`
edge does.

```
E-Stop button      step4.py terminal: es0 / es1
Protective field   3 scanners -> field_eval -> sensor_link -> PF_OSSD
Speed / encoder    drive shaft -> encoder_link -> sensor_link -> ENC_A/ENC_B
```

## The field logic, unchanged from `m5-plc-debug/microscan3.py`

```python
FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   # case: (PF, WF) [m]
N_SCAN = 3          # consecutive scans before a state change
HYSTERESIS_M = 0.20 # extra margin required to RE-CLEAR
```

Three properties are load-bearing:

- **`pf` and `wf` are TRUE when the field is CLEAR**, matching `PF_OSSD` and
  `WF_Clear`. Inverting this inverts the safety function.
- **No measurement means violated.** Silence is not clear.
- **An unreadable monitoring case selects case 3**, the largest field — the
  value the system falls into when the case bits are unreadable, so it is
  the fail-safe path and must work.

## The encoders

`encoder_link` reads two `JointStatePublisher` systems on
`drive_wheel_joint` and converts each independently: `omega × 0.12 m × 1000`.

**A single-channel tested system, never a two-channel one.** One shaft, two
readings, both dying with the shaft they read. No Category, no Performance
Level, no SIL, no PFH is claimed anywhere in this tree.

The F-program faults on `|ENC_A − ENC_B| > 50` mm/s and on a 2800 mm/s
ceiling. `step4.py` injects the faults, because a broken encoder is a field
fault and the PLCSIM API is the wiring — the vehicle sends what the shaft
did and never lies.

## What will stop a Step 4 vehicle unexpectedly

**`V_Limit` is live and it is not on any acceptance list.** When `WF_Clear`
is False the standard program computes `V_Limit = 300` mm/s instead of 1500,
and the speed monitor demands a stop above it. Measured: driving at 0.5 m/s
commanded with racks 1.75 m from the back scanner, `Motor` dropped 0.68 s
after enable with the encoder channels agreeing. Anything commanding speed
near racking meets this, and the latch holds it stopped until an
`Acknowledge`.

## Ports

| Port | Direction | Payload |
|---|---|---|
| 5100 | Windows → WSL | `estop_healthy`, `motor`, `case`, `ts` |
| 5101 | WSL → Windows | `pf`, `wf`, `enc_a`, `enc_b`, `ts` |

The 5101 contract has two implementations that agree only by inspection:
`sensor_link.payload()` writes it, `step4.py parse_sensor()` validates it.
They are a pair. Changing one without the other is silent.

## Terminal commands on `step4.py`

`es0` · `es1` · `a` · `ok` · `fa` (freeze channel A) · `oa` (offset A
+400 mm/s) · `q`

## Isolation

`GZ_PARTITION=step4`, `ROS_DOMAIN_ID=94`. The next step takes `step5` / `95`, or
two stacks share one graph and `stop` sweeps the wrong processes.

## Known debt carried forward

The whole-branch review's register lives in this branch's history. The items
that survive into Step 4's tree:

- Five ROS topic names are literals and three are duplicated across files;
  `m5_ver2/CLAUDE.md` allows two. `/forklift/gz/drive_speed/read_{}` is the
  worst — `config.yaml:873-874` owns those keys and the launch file reads
  them from there while `encoder_link` hard-codes them. **Move them into
  `status_contract.py` before the copy, or pay it four times.**
- `gated_command`'s third parameter is still named `motor_ok` while every
  caller passes the composite `enabled()`. A future edit "correcting" it
  would reinstate a closed leak.
- `step4.sh`'s startup name list is positional and must be hand-synced with
  the spawn order; `stack.sh:191-203` teaches the per-component token fix.
- No committed test covers `step4.py`'s fail-direction path.
