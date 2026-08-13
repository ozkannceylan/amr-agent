gate:                M3
agent:               infra (ad-hoc, owner-approved this session)
goal:                Rebuild the M3 toolchain inside WSL Ubuntu from the committed setup script and record every WSL-specific deviation, so the container-verified work can be re-verified locally.
invariants_touched:  none
inputs:              [sim/setup/install.sh, sim/README.md, bridge/README.md, docs/LESSONS.md]
deliverable:         sim/setup/WSL_ENVIRONMENT.md
done_when:           A reader with a clean WSL Ubuntu can follow the document and reach a state where ROS 2 Jazzy, Gazebo Harmonic and asyncua 2.0.1 all import in one interpreter; every command in the document has been executed by the author and its real output quoted; every point where WSL behaved differently from Ubuntu 24.04 in a container is named with the observed symptom.
forbidden:           [running the bridge or the cell end-to-end loop (that is brief m3-08), editing bridge/ or docs/, changing sim/setup/install.sh logic beyond what is required to make it run and recording that change as a finding, adding dependencies not already named in install.sh, writing any PLC artifact]

## Context the agent must not re-derive

The M3 bridge work was built and evidenced inside an Ubuntu 24.04 container:
ROS 2 Jazzy, Gazebo Harmonic, python3.12, asyncua 2.0.1 in a venv at
`/opt/amr-bridge-venv` created with `--system-site-packages` (pip refuses a
system-wide install because Debian owns `cryptography`). Evidence lives in
`sim/worlds/CELL_EVIDENCE.md`, `bridge/EVIDENCE_LATENCY.md` and
`bridge/EVIDENCE_SIGNAL_LOSS.md`. None of it has been reproduced on this
machine. Nothing is trusted until it runs here.

## Environment already probed by the orchestrator

Do not spend turns re-discovering these:

- Distro: WSL2 `Ubuntu`, default distro, kernel `5.15.167.4-microsoft-standard-WSL2`.
- ROS 2: `/opt/ros/jazzy` exists.
- Gazebo: `gz` is NOT on PATH. Harmonic is very likely not installed.
- Python: 3.12.3. No `/opt/amr-bridge-venv`.
- Repo is visible from WSL at `/mnt/c/Users/ozkan/projects/amr-agent` (a 9p
  DrvFs mount, not native ext4).
- 20 CPUs, 15.8 GB RAM, `/dev/shm` is 7.8 GB.

## Required investigations, each answered with observed evidence

1. **Gazebo Harmonic install.** Install it the way `sim/setup/install.sh`
   specifies. Record the actual version string from `gz sim --version`.
2. **Interpreter unification.** Create the venv with `--system-site-packages`
   and prove in one command that `rclpy`, `asyncua` and the Gazebo Python
   bindings (if the project uses them) all import in that interpreter. Quote
   the output. Record the resolved asyncua version — the target is 2.0.1.
3. **DDS discovery under WSL2.** WSL2 uses a NAT'd virtual adapter and
   multicast behaves differently from a container's bridge network. Determine
   empirically whether default DDS discovery works between two terminals in
   the same distro, and whether `ROS_LOCALHOST_ONLY` / a custom
   `ROS_DOMAIN_ID` / an XML profile is needed. State what you actually
   observed, not what is generally true of WSL.
4. **/dev/shm.** Fast RTPS uses shared memory transport. Confirm `/dev/shm`
   is writable and sized, and note whether any shm segment cleanup is needed
   between runs.
5. **Clock source.** WSL2 clock can drift from the Windows host across
   suspend. This matters because the latency evidence is timestamp-derived.
   Record the clock source, whether `CLOCK_MONOTONIC` is sane, and any drift
   observed. This finding directly gates whether m3-08's latency numbers are
   trustworthy.
6. **Filesystem.** Determine whether working from the `/mnt/c` DrvFs mount is
   acceptable for this workload or whether the run must happen from a native
   ext4 path. Measure, do not assume. If a native path is required, say so
   explicitly and state the exact mechanism you recommend — this is a finding
   for the orchestrator, not a change you make to the repo layout.
7. **Graphics.** The cell must run headless. Confirm headless Gazebo works
   without WSLg and record what happens if WSLg is present.

## Output shape

`sim/setup/WSL_ENVIRONMENT.md`, with these sections in this order:

1. Purpose and scope — one paragraph, states this documents WSL only and does
   not supersede the container path.
2. Verified environment table — component, expected version, observed version.
3. Step-by-step setup, each step with the command and its real quoted output
   (trim to the meaningful lines; do not paste hundreds of apt lines).
4. WSL-specific findings — one subsection per investigation above, each
   stating the symptom observed and the resolution applied.
5. Known-unresolved — anything you could not settle, stated plainly.

Prefer a short document. Quote real output; never invent or paraphrase a
command result.

## Reporting

Write `docs/reports/m3-07-wsl-environment.md` in the CLAUDE.md report shape.
Additionally, end the report with a section titled `lessons_candidates`
listing any entry you believe belongs in `docs/LESSONS.md`, in the file's
`date | attempted | went wrong | rule now` format. Do NOT edit
`docs/LESSONS.md` yourself — the orchestrator appends it.
