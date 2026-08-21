# virtual_plc/ — the first build's CPU, answered in software

The PLCSIM Advanced trial expired. This process stands where PLCSIM Advanced
stood, so the first build's stack runs **as if the CPU existed**:

- it serves the commissioned 49-variable OPC UA address space
  (`docs/interfaces/opcua-nodes.md` §9–§13, the same tables the bridge's test
  double serves);
- it runs a statement-for-statement behavioural model of the standard
  program (`standard_program.py` — `plc/forklift/SPEC.md` §7 as amended by
  §14, §14.16/17, plus the safety coupling) at the 20 ms cyclic cadence;
- it runs a network-for-network behavioural model of the F-program
  (`f_program.py` — `plc/forklift-safety/SPEC.md`'s 49 networks, every
  constant cited to its row) at the 100 ms F-cadence;
- it plays the stand-in writer's role (`bridge/standin_writer/standin_writer.ps1`)
  toward the same surfaces: the named mutex `Global\amr-standin-writer`, the
  field link on **45015** (`ZONE 0|1` / `WARN 0|1` / `PING`), the speed link
  on **45016** (`SPD A|B <int>` / `MOT <p> <v>` / `PING`), and the operator's
  commands (`estop open|close`, `zone open|close`, `reset press|release`,
  `reset pulse <ms>`, `status`, `quit`) on the console and a command file.

**IT IS NOT A PLC AND CARRIES NO SAFETY INTEGRITY.** The F-side model
reproduces the documented *behaviour* of the F-networks; it is nobody's
F-runtime group, its inputs are software, and its scheduler is CPython. The
writer it replaces said the same sentence about itself
(`bridge/standin_writer/STANDIN-WRITER-DESIGN.md`). The one deliberate
surface difference: the OPC UA port is **4841**, not 4840 — the host's OPC
UA Local Discovery Server owns 4840, and the commissioned `192.168.53.1:4840`
was PLCSIM Advanced's virtual NIC.

**The precedent is ver2's.** `m5_ver2/step5/windows/virtual_fplc.py`
(2026-08-20, design: `docs/superpowers/specs/2026-08-20-virtual-fplc-design.md`)
was the first behavioural CPU model in the repo — `step5.py --virtual` swaps
the PLCSIM API object for it in-process. It could not be reused here: ver2's
model duck-types the five PLCSIM API methods its writer calls, while this
build's clients (the bridge, the HMI) speak **OPC UA** and its WSL side
speaks the writer's **TCP link protocol** — so the ver1 model had to be a
server on the network, not an API shim in a process. Same honesty rule,
different wire.

## Run

```powershell
python virtual_plc.py --command-file C:\Temp\m5v1_cmds
```

Options: `--endpoint`, `--field-port`, `--speed-port`, `--no-mutex`
(tests/non-Windows), `--no-console`. One session log per start under
`logs/`, never truncated — the writer's rule. A second instance refuses to
start on the mutex, exactly as the writer did.

Then the WSL half: [`../demo.sh`](../demo.sh) `check` / `up` — see
[`../RUNBOOK.md`](../RUNBOOK.md).

## Prove

```powershell
python -m pytest test_virtual_plc.py -q          # 22 behavioural pins
python smoke_test.py --command-file C:\Temp\m5v1_cmds   # 9 end-to-end checks over the wire
```

Both are transcribed in [`../EVIDENCE.md`](../EVIDENCE.md).

## Files

| File | What it is |
|---|---|
| `f_program.py` | The F-program model: the stand-in image, the statics, the 49 networks |
| `standard_program.py` | The standard program model: §7 + the M5 deltas + the safety coupling |
| `plc_logic_ref.py` | The §7 constants and IEC primitives, imported from `plc/forklift/double/logic.py` — one transliteration, one home |
| `virtual_plc.py` | The server, the three cyclic tasks, the writer role, the mutex |
| `test_virtual_plc.py` | The 22 behavioural pins |
| `smoke_test.py` | The 9 end-to-end checks against a running instance |
| `logs/` | One session log per start |

Where these files and the SPECs disagree, **the SPECs are right and these
files are wrong** — the same rule the logic double lived under.
