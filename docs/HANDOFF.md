# Handoff — local session, 2026-07-27

State at handoff: `main` at commit `71d04c1`. Gates M0, M1, M2 closed and
verified. M3 (fixed equipment I/O loop) is partly delivered: the cell, the
node model, the bridge design and the bridge implementation are done and
evidenced in-container against an OPC UA test double. What remains of M3 is
the PLC side, which is owner work, plus two documentation corrections and
the gate verification.

## What is proven, and where the evidence is

| Artifact | Evidence |
|---|---|
| Fixed-equipment cell in Gazebo Harmonic, headless, RTF ~1.0 | `sim/worlds/CELL_EVIDENCE.md` |
| Bridge: cell to PLC and PLC to cell, 4000 cycles at 19.99 Hz, 0 overruns | `bridge/EVIDENCE_LATENCY.md` |
| Signal loss cases A-D exercised | `bridge/EVIDENCE_SIGNAL_LOSS.md` |
| Raw per-event samples, 76 191 rows | `bridge/evidence/latency-2026-07-27.csv.gz` |

Nothing in the above proves the PLC program. The test double has no scan
cycle and no program; `DemoCell/Status/*` and `BridgeLinkOk` were False in
every run because nothing computes them yet.

## Environment the work was verified in

- Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic, python3.12.
- Robotnik jazzy-devel workspace at `/opt/m3-feasibility/ws` (M5 work only).
- asyncua 2.0.1 in `/opt/amr-bridge-venv`, created with
  `--system-site-packages` so the same interpreter imports rclpy. pip refuses
  a system-wide install because Debian owns `cryptography`.
- Reproducible setup: `sim/setup/install.sh`.

The local session runs WSL, so every one of these has to be re-established
and re-verified there before anything is trusted.

## Open points that are the owner's, not an agent's

1. **PLC.** Implement the TIA Portal program, run PLCSIM Advanced, capture
   the watch-table evidence for gate items (a) and (b) and fill Section B of
   `bridge/EVIDENCE_LATENCY.md`.
2. **Hermes.** Undefined in the repository. Which component, which repo, how
   Telegram reaches it, what it is allowed to write. M4 cannot be briefed
   until this exists.

## Remaining agent work, already queued in docs/TODO.md

- `m3-03c` interface: correct the stale `fleet/bridge/` paths in
  `docs/interfaces/bridge-design.md` and amend the L1 definition in §9.2.
- `m3-05` plc: write `plc/demo-cell/SPEC.md`, the TIA implementation
  specification the owner builds from.
- `m3-06` verifier: re-run the container-side loop from committed
  instructions and state precisely what remains owner-executed.

## How to work in this repository

Read `CLAUDE.md` in full first. It is the contract, not a summary. The
orchestrator delegates and reads reports; it does not read source files.
One brief, one deliverable, one report. The verifier runs before any gate
advances. Tracking files are `docs/PLAN.md`, `docs/TODO.md`,
`docs/LESSONS.md` — read LESSONS before the first delegation of a session.
