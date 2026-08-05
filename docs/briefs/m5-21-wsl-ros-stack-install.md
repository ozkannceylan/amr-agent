# m5-21 — install the ROS 2 autonomy stack properly on the WSL machine

    gate:                M5 (supporting; not a gate criterion)
    agent:               infra   (owner-approved scope, 2026-08-04)
    goal:                Nav2 and robot_localization are installed as real packages on the WSL machine, the user-prefix .deb overlay is retired, and the M5 vehicle stack is shown to still come up on the installed stack.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-11-envelope-gate-node.md (§"Files outside agv/", item 2 — the overlay it had to build)
      - agv/forklift/EVIDENCE_ENVELOPE.md §0 (the overlay's package list and versions)
      - sim/setup/WSL_ENVIRONMENT.md
      - sim/setup/install.sh
      - agv/forklift/EVIDENCE_NAV2.md, agv/forklift/EVIDENCE_LOCALIZATION.md (how the stack is brought up)
      - docs/LESSONS.md
    deliverable:         a working apt-installed Nav2 + robot_localization on the WSL machine, sim/setup/WSL_ENVIRONMENT.md rewritten to match, and sim/setup/install.sh updated if it is the right home for the step
    done_when:           `ros2 pkg prefix nav2_bringup` and `ros2 pkg prefix robot_localization` both resolve to a system path with no overlay sourced, the exact installed versions are recorded, and one m5-11 measurement is re-run on the installed stack and agrees with the committed figure — or is reported as disagreeing.
    forbidden:
      - writing outside sim/ except the report (request anything else in the report)
      - leaving the machine in a state where the m5-10 / m5-11 stack no longer comes up; if that happens, restore and report BLOCKED
      - adding a repository dependency to the project without proposing it in the report first
      - re-deriving or restating the measured numbers in docs/TODO.md §"Measured numbers a later session should not re-derive"
      - handling, requesting or storing any password or credential

---

## 1. Why this exists

m5-11 needed Nav2 and `robot_localization` and this machine has neither. Rather
than install, it fetched `.deb` files and extracted them into a user prefix at
`~/ros-overlay/prefix` — 12 + 42 packages, ~40 MB — dragging in `fastcdr`,
`fastrtps`, `libompl.so.18` and GraphicsMagick because **the system ROS install
is about 345 packages behind the archive**. That was the right call under a
brief that forbade adding dependencies, and it is the wrong thing to leave in
place: every figure in `EVIDENCE_ENVELOPE.md` is currently qualified by an
overlay that no one else can reproduce.

The owner has asked for the real thing.

## 2. Privilege — settled, do not go hunting

`sudo` on this machine **requires a password, and you must never ask for one or
handle one**. Use `wsl.exe -u root -e bash -lc '<command>'`, which is already
verified to work without a password on this machine. The ROS 2 apt source is
already configured (`/etc/apt/sources.list.d/ros2.list`, `packages.ros.org/ros2/ubuntu noble main`).

## 3. The real risk, and the order that contains it

The system install being ~345 packages behind the archive means
`apt install ros-jazzy-navigation2` may pull a large upgrade across the whole
ROS tree. **That can break a stack the project depends on**, and the owner is
away. So:

1. **Snapshot first.** Record `dpkg --get-selections`, the `ros-jazzy-*` package
   list with versions, and `/var/log/apt/history.log`'s tail, into the evidence
   BEFORE touching anything. This is the rollback record.
2. **Simulate before executing.** `apt-get -s install ...` and record the full
   plan — how many packages upgrade, how many install, whether anything is
   REMOVED. A removal of a package the current stack uses is a stop-and-report,
   not something to accept because apt offered it.
3. **Then install**, and record what actually happened, not what step 2
   predicted.
4. **Then verify** (§4). If verification fails, restore what you can, report
   **BLOCKED**, and say precisely what broke.

Prefer the narrowest package set that satisfies the need. `navigation2` /
`nav2_bringup` and `robot_localization` are the targets; do not install a
desktop metapackage to get them.

## 4. Verification — this is the deliverable, not the apt run

1. `ros2 pkg prefix nav2_bringup` and `ros2 pkg prefix robot_localization`
   resolve to a **system** path, with the overlay **not** sourced. Show the
   command and its output.
2. The overlay is retired: `~/ros-overlay/prefix` is no longer sourced by any
   launch, script or shell rc the project uses. Grep for it. If anything still
   references it, that reference is yours to fix inside `sim/` or to report.
3. **The stack still comes up.** Bring up the M5 vehicle stack the way
   `EVIDENCE_NAV2.md` / `EVIDENCE_LOCALIZATION.md` describe and show it running:
   nodes present, no fatal errors. A launch that dies is a failure of this
   brief.
4. **One m5-11 measurement is re-run on the installed stack.** Choose the
   cheapest decisive one — the §3.2 gate-release comparison, or observation 5's
   pass-through fidelity. Report the new figure beside the committed one. **If
   they disagree, say so plainly**; a disagreement is a finding about the
   overlay, not a failure of this brief. Do not tune anything to make them
   agree.
5. Record the exact installed versions of every package that matters, so the
   environment is reproducible from the document alone.

## 5. The document

Rewrite `sim/setup/WSL_ENVIRONMENT.md` so it describes the machine as it now is,
including: what was missing, what was installed and at which versions, that the
overlay existed and is retired, and the `wsl -u root` privilege route (as a fact
about this machine, with no credential anywhere near it). If
`sim/setup/install.sh` is the right home for the install step, update it; if it
is not, say why in the report.

Note for the document: `EVIDENCE_ENVELOPE.md`'s figures were produced under the
overlay. That qualifier belongs in the record (LESSONS 2026-07-27, evidence is
qualified by the environment that produced it). You may not edit that file —
request the edit in your report.

## 6. Working discipline

- **Write results into the evidence as they land**, not at the end. The snapshot
  goes in before the install, the apt plan goes in before you execute it.
- Beware line endings: this repo is checked out on Windows and executed in WSL.
  `*.sh` needs `eol=lf` (LESSONS 2026-07-27); check `git ls-files --eol` before
  concluding a script failure is a content problem.
- **Do not commit.** The orchestrator commits by pathspec.
- Write `docs/reports/m5-21-wsl-ros-stack-install.md` in the CLAUDE.md §5 report
  format.
- Read `docs/LESSONS.md` first.
