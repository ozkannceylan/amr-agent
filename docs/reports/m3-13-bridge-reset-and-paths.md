brief:               docs/briefs/m3-13-bridge-reset-and-paths.md
status:              done
files_changed:
  - bridge/config/bridge.yaml            (PanelResetPressed node path; panel_reset topic; machine-neutral csv_path)
  - bridge/amr_bridge/config.py          (INPUT_KEYS/BOOL_INPUT_KEYS seven-node set; Config.evidence_csv_path)
  - bridge/amr_bridge/ros_side.py        (subscription on /cell/panel/reset; QoS startup report)
  - bridge/amr_bridge/opcua_side.py      (counts in log/exception text; no cycle change needed)
  - bridge/amr_bridge/main.py            (uses the resolved evidence path)
  - bridge/amr_bridge/slots.py           (comment: "six input slots" -> per-node)
  - bridge/test_double/plc_test_double.py (PanelResetPressed node, start value FALSE)
  - bridge/test_double/README.md         (start-value note; venv path -> $VENV)
  - bridge/tools/cell_stimulus.py        (fourth contact; default script; unknown-contact guard)
  - bridge/tools/check_write_allowlist.py (counts; venv path -> $VENV)
  - bridge/README.md                     (venv mechanism + two worked examples; $REPO/$VENV; reset bullet)
  - bridge/requirements.txt              (install lines show the mechanism, container and WSL)
  - bridge/run_bridge.py                 (venv path -> $VENV)
  - bridge/EVIDENCE_LATENCY.md           (scope note on Section A; new Section C, dated WSL run)
  - bridge/EVIDENCE_SIGNAL_LOSS.md       (scope note only; no number touched, no case re-run)
invariants_touched:  none
open_questions:
  - "docs/interfaces/bridge-design.md now disagrees with the code it specifies. It says 'the six
     DemoCell/Input/ nodes' in §3, §4 intro, §5 (contacts row), §6.1 R3/R4, the §6.2 guarantee box
     and §7 (reconnect row); its §4.1 signal map has no reset row and its §6.3 start-value table has
     no PanelResetPressed. The implementation follows opcua-nodes.md §9.3, which is the contract.
     Already queued by m3-11; outside this agent's write access."
  - "plc/demo-cell/SPEC.md is unchanged and still implements the monitored reset on
     PanelStartPressed with a 14-node table (m3-12, plc agent). The bridge now delivers the
     dedicated contact, so the conflation has a device to move to."
  - "sim/setup/WSL_ENVIRONMENT.md §5 'Known-unresolved' items 1 and 2 are now stale. Item 2
     (csv_path is a container path) is fixed here. Item 1 recommends recreating the venv at
     /opt 'so bridge/README.md stays literally true'; the README no longer names one machine, so
     the WSL venv at /home/ozkan/amr-bridge-venv is now a documented example rather than a
     deviation. sim/ is outside this agent's write access."
  - "The committed default evidence file, bridge/evidence/latency-latest.csv, lands inside the
     repository and is untracked. The run made here was deleted afterwards. A one-line .gitignore
     entry would keep the tree clean; the repo root is outside this agent's write access. m3-08
     passes --evidence-csv with its own dated name regardless."
next_suggested:      m3-12 plc — consume PanelResetPressed and retire the start/reset conflation in SPEC §5-§7.

---

## 1. The reset — how pre-first-publish works, and that it matches

**The existing three contacts have no pre-first-publish default, and neither does
the reset. That is the whole mechanism.** `bridge-design.md` §6.1 R1 — "the
bridge writes no `DemoCell/Input/` node until it has received a real sample" —
is implemented as three lines in `opcua_side._input_path`: the slot is read,
`if sample is None: continue`, and the write is skipped. A `Slot` starts with
`_sample = None` and only a subscriber callback can fill it. There is no
initialiser, no placeholder and no config key that could put a value there.

So before the first message on `/cell/panel/reset`, the bridge does not write
FALSE — it writes **nothing**, and the node keeps the value the server started
with, which is FALSE both in the test double and, per `opcua-nodes.md` §3.1, in
the PLC's data block. The bridge cannot contradict it because it never
addresses the node. `PanelResetPressed` is handled by exactly the same code path
as `PanelStartPressed`: it was added to `INPUT_KEYS` and `BOOL_INPUT_KEYS` and
nothing else in the cycle changed.

The second half of the guarantee is the heartbeat. R3 withholds
`BridgeHeartbeat` until every input has been written from a real sample, so the
PLC's §6.2 predicate now covers seven nodes: while the heartbeat advances, the
reset level is attributable to the cell; while it does not, the PLC is looking
at its own start values and knows it.

**No logic was added.** No edge, no hold timer, no latch, no interlock, no
threshold, no debounce, no "one-shot" — the reset is carried as a momentary
level, on change, refreshed on reconnect, exactly like the other three contacts.
The rising edge and the hold time are PLC program content and stayed there.
Nothing outside `DemoCell/Input/` is written; the write allowlist grew by one
input node and was re-checked against a running server (§3).

## 2. evidence.csv_path

`--evidence-csv` already existed, so no knob was added; the committed **default**
was made sane instead, as the brief asked. `evidence.csv_path` is now
`evidence/latency-latest.csv`, resolved by `Config.evidence_csv_path`:
`~` and `$VARS` are expanded, an absolute path is used as written, and a path
still relative is joined to the **bridge directory** — the same anchor
`main._parse_args` already uses to find the default config file. No new config
key, no new dependency, and nothing about a transported value depends on it.

## 3. README venv

The README now documents the mechanism — a venv created with
`--system-site-packages` (so `rclpy` still imports) anywhere the account can
write, plus `/opt/ros/jazzy/setup.bash` sourced in every shell — and gives the
container (`/opt/amr-bridge-venv`, root, `/home/user/amr-agent`) and WSL
(`/home/ozkan/amr-bridge-venv`, no sudo, `/mnt/c/...`) as the two worked
examples. Every command in `bridge/` now reads `"$VENV/bin/python"` and
`"$REPO/..."`, so no machine's home directory is left in the layer:
`grep -rn "/home/user" bridge/` returns nothing.

## 4. Verified live, against the running cell and the test double

WSL2 Ubuntu 24.04, `ROS_DOMAIN_ID=88` and `GZ_PARTITION=m313bridge` (both, per
LESSONS — gz transport is not DDS), nothing else running before or after; every
process was driven to completion in the foreground. Headless cell via
`sim/launch/cell_bringup.launch.py`, the test double, the bridge for 45 s, and
`tools/cell_stimulus.py` with a script that **deliberately withholds the reset
for the first 15 s**. Full capture: `bridge/EVIDENCE_LATENCY.md` Section C.

| Claim | How it was checked |
|---|---|
| The mapping resolves against a live server | `namespace ... resolved to index 2`, `all node DataTypes match opcua-nodes.md §9` — `DemoCell/Input/PanelResetPressed` browsed and type-verified as `Boolean` |
| Pre-first-publish the node reads FALSE | 14.0 s with a live session and no reset publish: `heartbeat withheld: no real sample yet for PanelResetPressed`. The double's own 5 Hz observation log has 84 samples in that window; the distinct set of `PanelResetPressed` values while `BridgeHeartbeat == 0` is exactly `{False}` |
| That FALSE is the server's, not the bridge's | The bridge's evidence CSV contains **no** write row for the node before `t_start_ns = 9316826185902`, which is the first publish |
| The press traverses | Server side `ResetPressed=True` at monotonic 9321.920, back to `False` at 9323.967 — the 20 s / 22 s script points |
| It is written on change, not cyclically | `R3` decimation `PanelResetPressed 32/3`: 32 samples received (the stimulus republishes the held level at 1 Hz), 3 writes — one per real change |
| The heartbeat waits for seven | `startup rule satisfied: all 7 DemoCell/Input nodes carry a real cell sample`, 2.0 ms after the node's first write, same cycle. `heartbeat_suppressed_cycles = 290` of `cycles = 900` |
| Nothing else broke | `write_errors = 0`, `read_errors = 0`, `reconnects = 0`, `cycle_overruns = 0`, `publishes = 900`; the other three contacts `43/1` as before |
| The write allowlist still holds | `tools/check_write_allowlist.py` against a fresh double: 8 keys, all five forbidden nodes refused client-side (`WriteNotPermitted`) and server-side (`BadUserAccessDenied`), `RESULT: PASS` |
| The committed default csv path resolves | Second short run with **no** `--evidence-csv`: `evidence written to /mnt/c/Users/ozkan/projects/amr-agent/bridge/evidence/latency-latest.csv`, file created with the header row. Deleted afterwards |
| The stimulus drives the reset like the others | It is the fourth entry in `CONTACTS`, published and republished by the same code; the run above is the proof |
| Everything still imports and compiles | `py_compile` over all of `bridge/`, and `config.load()` on the committed YAML |

### Not verified, and why

- **Nothing was run against PLCSIM Advanced or hardware.** The server here is
  the test double, which has no program: it holds `PanelResetPressed` and forms
  no edge, no hold and no latch from it. Nothing above is evidence for
  `plc/demo-cell/SPEC.md`, and the M3 gate still closes on Section B.
- **The four signal-loss cases were not re-run** for the seventh node. A scope
  note was added to `EVIDENCE_SIGNAL_LOSS.md`; no number in it was touched.
- **No measured-latency claim is made.** Section C is a behaviour capture, not a
  statistics run; `§A.4` was not re-measured and m3-08 remains outstanding.
- **The container was not used.** All of this is WSL evidence, recorded as its
  own dated section rather than replacing the container capture.
- **Wall-clock timestamps in Section C are from the WSL guest**, whose clock
  still steps ~2.73 s / 30 s (`WSL_ENVIRONMENT.md` §4.5). Every interval quoted
  is `CLOCK_MONOTONIC`, so no figure depends on that defect.

---

## lessons_candidates

2026-07-27 | Added a seventh input node to a bridge whose heartbeat waits for every input | The startup rule silently became stricter: nothing in the cell publishes a panel contact on its own, so an unattended run that never touched the new topic would have had a permanently stopped heartbeat and looked like a link fault | When a signal joins a set that an all-of predicate quantifies over, check what publishes it before shipping the change, and update the default stimulus in the same commit as the mapping

2026-07-27 | Asked "what does the bridge write for a contact before its first publish" | The right answer was "it never addresses the node", not "it writes a safe default": the fail-safe value is the PLC's DB start value, so the bridge's correct contribution is silence | A layer that carries values proves a startup property by showing it wrote nothing, not by showing it wrote the right thing; the evidence is an absent row, so make the absence observable (a withheld heartbeat, a named node in the log)

2026-07-27 | Ran WSL commands as `wsl.exe -- bash -lc '<command with $VAR>'` from the agent's shell | The `$VAR` references were consumed before reaching WSL, so the command ran with empty variables and failed with a bare exit code and no output | Put multi-line or variable-using WSL work in a script file and run the file; and never put `set -u` above `source /opt/ros/jazzy/setup.bash`, which exits the shell silently on an unbound ROS variable
