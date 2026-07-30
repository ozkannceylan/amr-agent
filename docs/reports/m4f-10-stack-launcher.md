# Report m4f-10 — one-command start/stop for the Linux-side M4 stack

```
brief:               docs/briefs/m4f-10-stack-launcher.md
status:              done
files_changed:       [stack.sh (new, mode 100755), README.md (new "Run it" section)]
invariants_touched:  none
open_questions:      see below (five, one of which is a doc/brief disagreement)
next_suggested:      have the owner run ./stack.sh start on WSL against PLCSIM once, and record which readiness waits fired and how long each took
```

## What was built

`stack.sh` at the repo root, executable, LF, pure ASCII, with `start`, `stop`,
`status` and `--help`. It owns rows 2-5 of the start order in
`sim/scenarios/forklift_commissioning.md` §1 — bridge, sim bringup, the two
vehicle scripts, the HMI — and deliberately does not own row 1, PLCSIM on the
owner's Windows machine. The start lines are the documents' own, not
reconstructed: each one is quoted from §1's table and cross-checked against
`bridge/README.md`, `hmi/README.md`, `agv/forklift/README.md` and the argument
parsers of the five scripts themselves.

Design points that are load-bearing rather than decorative:

- **One PID file per process** under `${AMR_STACK_RUN_DIR:-/tmp/amr-agent-stack}`,
  plus one log per process and a recorded `partition` / `domain`.
- **Each component leads its own process group** (`setsid`), and the leader
  writes its *own* pid into the PID file rather than the parent recording `$!`.
  `setsid` execs in place or forks depending on whether its caller is already a
  process group leader, so `$!` is not reliably the leader. Every component
  command ends in `exec`, so the pid written survives into the process that does
  the work.
- **`stop` signals exactly those groups**: SIGTERM, a bounded wait
  (`AMR_TERM_GRACE`, default 10 s), then SIGKILL, then a survivor sweep for what
  `ros2 launch` leaves behind — matched by `pgrep` **and** by this run's
  `GZ_PARTITION` in `/proc/<pid>/environ`. There is no blanket `pkill`: a process
  is signalled only if it is in a PID file this script wrote or it carries this
  run's partition. If no partition was recorded, the sweep is skipped rather than
  falling back to matching by name alone.
- **A second `start` refuses** (exit 2) before any environment probe or spawn.
- **Readiness is observed, not assumed**, and every wait has a deadline:
  `session established` in the bridge log, `/forklift/scan` on the wire,
  `startup rule R3 satisfied` in the bridge log for the plant, and for the HMI a
  session in `CONNECTED` **with metrics present** — a panel whose metrics are
  blank is not a boot reading (§3, "an absent value is not a zero").
- **GUI by default** (`gui:=true`), `--headless` passes `gui:=false`, which is
  the flag `forklift_bringup.launch.py` already declares. No new launch argument
  was invented.

## Testing — what was exercised here, and what was not

This container has **no ROS 2, no Gazebo and no venvs** (`/opt/ros` absent, `gz`
absent, neither venv present), so a real bringup is impossible in it. Evidence is
qualified by the environment that produced it, so:

**Exercised, in this container, 2026-07-30:**

- `bash -n` clean. `shellcheck` is not installed here, so the script has not been
  linted.
- The full PID-file lifecycle, against stand-in processes with the real code
  path (`spawn`, `is_running`, `pid_alive`, `stop_group`, `survivors`,
  `cmd_start`, `cmd_stop`, `cmd_status`): **23 checks, 23 passed**, including
  the recorded pid being its own process group leader, a grandchild dying with
  the group, SIGTERM-then-SIGKILL escalation against a process that ignores
  SIGTERM, a second `start` refusing with exit 2 and spawning nothing, stale and
  recycled PID files reading as down, `stop` being idempotent, and the survivor
  sweep listing nothing for a partition that is not this run's.
- The real CLI: `status` with nothing up (exit 1), `status` with a component up
  (`up` + pid), `start` failing the environment guard and naming all four missing
  things without spawning anything (exit 1), `start` refusing while a component
  is live (exit 2), `stop` on an empty stack (exit 0), an unknown subcommand
  (exit 1), and `--help`.
- HTTP port parsed out of the HMI config rather than hardcoded: `hmi/config.yaml`
  -> 8088, `hmi/config-logic-double.yaml` -> 8090.
- `.gitattributes` already carries `*.sh text eol=lf` (line 18); nothing was
  added. Confirmed effective for the new file with
  `git check-attr text eol -- stack.sh` -> `text: set`, `eol: lf`. File mode is
  100755 in the working tree; the file is ASCII-only with no CR bytes.

**Not exercised anywhere:** the actual bringup. No component was ever started,
no readiness predicate has ever seen its real signal, no timeout value has been
calibrated against a real start, and the survivor sweep has never run against a
real `gz sim` / `parameter_bridge` pair. `./stack.sh start` has not been run to
completion on any machine. The first real run belongs on the owner's WSL.

Two defects were found by testing and fixed, both worth recording:

1. `spawn` reported success for a process that died immediately, sending the
   operator to the wrong log. It now settles, re-checks, prints the tail of the
   component's log and fails; `start` stops at that point rather than continuing
   through an order that no longer means anything.
2. `kill -0` succeeds on an **unreaped zombie**, and a component leader is a
   child of this script. `stop` would therefore have escalated to SIGKILL against
   a corpse and then reported that the corpse survived SIGKILL. Liveness is now
   read from the state field of `/proc/<pid>/stat`, and `Z` counts as dead. This
   was observed directly in this container, where PID 1 does not reap promptly.

## Disagreements between the documents and the tree

Reported rather than resolved, as the brief instructs.

1. **The bridge configuration (brief vs. `forklift_commissioning.md` §1).** The
   brief says the script uses "the live `bridge.yaml` as configured". It does —
   `bridge/config/bridge.yaml`, unmodified. But that file is committed carrying
   `groups: ["cell"]`, so a stack started with it reads and writes **no
   `Forklift/` node at all**, and §1's prerequisite 1 says in terms that neither
   `bridge.yaml` nor `rehearsal-forklift.yaml` is the gate configuration and that
   the gate run cannot start until a forklift-group config against the
   commissioned endpoint exists. The script keeps the brief's default, warns at
   start when the chosen config does not name the forklift group, and accepts
   `AMR_BRIDGE_CONFIG`. It does not choose a file and does not edit one. **The
   missing forklift-group config is still an open request on `bridge/`**, exactly
   as §1 records it.
2. **The bridge venv path (brief vs. `bridge/README.md`).** The brief names
   `/opt/amr-bridge-venv`. `bridge/README.md` gives that as the *container's*
   path and `~/amr-bridge-venv` as the owner's WSL path, because `/opt` is not
   writable there — and `run_forklift_rehearsal.py` hardcodes
   `/home/ozkan/amr-bridge-venv`. Since this script runs on the owner's WSL, it
   searches `/opt/amr-bridge-venv` then `$HOME/amr-bridge-venv` and honours
   `AMR_BRIDGE_VENV` over both, rather than hardcoding one machine's path.
3. **The HMI port.** §1 step 5 and §10 quote `8090`, and §1's shutdown snippet
   greps for it. That is the *rehearsal* config's port
   (`hmi/config-logic-double.yaml`); the owner's `hmi/config.yaml` binds **8088**.
   The script reads the port out of whichever config it was given, so it is right
   either way, but the `8090` in §1 will mislead a reader running the owner
   config. `sim/` owns that document and is held by a parallel brief, so it was
   not touched.
4. **`agv/forklift/launch/vehicle.launch.py`.** Consistent with the brief's note:
   it is a standalone rig that brings its own server, spawn and transport bridge,
   so composing it here would start a second world. The two scripts are run
   directly, which is what §1 row 4 and `sim/README.md` both say.
5. **Runtime directory location.** `/tmp/amr-agent-stack`, outside the
   repository, so a gate run cannot dirty `git status` while other agents are
   committing by pathspec, and so log writes do not land on DrvFs. A repo-local
   directory would need a `.gitignore` line; if the owner would rather have logs
   beside the checkout, that one line is the whole change.

## Not done, deliberately

- **No PLC test double orchestration.** The brief forbids deciding it. A later
  `--double` flag that starts `plc/forklift/double/server.py` first and swaps to
  a rehearsal config is the obvious shape, but it is a rehearsal-versus-gate
  distinction and belongs in its own brief; `run_forklift_rehearsal.py` already
  covers the rehearsal case end to end.
- **No config, launch file or `sim/README.md` edits.** Nothing under `bridge/`,
  `hmi/`, `sim/` or `agv/` was modified. No dependency was added: the script uses
  bash, coreutils, `pgrep`, `setsid`, `awk` and the `python3` already required by
  the vehicle nodes.
- **Nothing was committed.** `README.md` is modified and `stack.sh` is untracked
  in the working tree, with its executable bit already set.

## Open questions

1. Which bridge configuration is the gate run's? Until the forklift-group config
   against the commissioned endpoint exists, `./stack.sh start` will warn on
   every run. (Owned by `bridge/`; already an outstanding §1 prerequisite.)
2. Should `start` abort and tear down when the bridge never connects, rather than
   warning and carrying on? It currently carries on, because §1 says the bridge
   can be started early and left to wait, and because tearing down destroys the
   logs that explain why. Exit code 4 marks the run.
3. Are the default timeouts right on the owner's machine? 60 s bridge, 120 s
   arena, 90 s R3, 60 s HMI are guesses scaled from the rehearsal's reported
   bringup times, not measurements on WSL. All four are environment-overridable.
4. Should `stop` archive the run's logs somewhere dated instead of the next
   `start` truncating them? Related to the one-CSV-per-session rule, though the
   bridge's own evidence path is untouched here and already suffixes per session.
5. `8090` in `forklift_commissioning.md` §1/§10 against `hmi/config.yaml`'s 8088
   (item 3 above) — a `sim/`-owned correction if the orchestrator wants it.
