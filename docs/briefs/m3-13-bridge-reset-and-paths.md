gate:                M3
agent:               bridge
goal:                Bridge the new reset contact and remove the two machine-specific paths, so m3-08's WSL evidence run can start from committed configuration alone.
invariants_touched:  none
inputs:              [bridge/config/bridge.yaml, bridge/tools/cell_stimulus.py, bridge/README.md, docs/interfaces/opcua-nodes.md §9.3, docs/reports/m3-10-panel-reset-contact.md, docs/reports/m3-11-panel-reset-node.md, sim/setup/WSL_ENVIRONMENT.md]
deliverable:         bridge/ updated: reset signal bridged and stimulable, no machine-specific path in config or README
done_when:           The bridge maps /cell/panel/reset to DemoCell/Input/PanelResetPressed with a pre-first-publish value of false; cell_stimulus.py can drive the reset like the other three contacts; evidence.csv_path no longer hardcodes a container home directory; the README's venv instruction produces a working venv for a non-root user on both the container and WSL; and whatever can be verified against the running cell and test double is verified, with what cannot be stated plainly.
forbidden:           [adding control logic to the bridge (no threshold, latch, timer, sequencing or interlock — invariants 5 and 6, the bridge translates signals only), writing to any Status or Output node, editing sim/ plc/ or docs/interfaces/, adding dependencies beyond requirements.txt, changing measured evidence files except to append a dated WSL section if a verification run produces one]

## The three items

### 1. Reset signal

`/cell/panel/reset` (std_msgs/Bool, delivered in adc9cd0) maps to
`DemoCell/Input/PanelResetPressed` (Bool, delivered in 79a7f1e). Follow the
exact pattern of the three existing panel contacts in `bridge.yaml` and in
`cell_stimulus.py`.

**The one property that matters: the pre-first-publish value is `false`.**
Before the first message arrives on the topic, whatever the bridge writes — or
refrains from writing — must leave the node reading FALSE. A startup default of
true asserts a reset the operator never pressed and clears a latch unbidden,
which is the auto-resume CLAUDE.md §9 forbids. State in your report how the
existing three contacts handle pre-first-publish, and that the reset matches.
The node's start value server-side is already FALSE (opcua-nodes.md §3.1 per
m3-11); your job is to never contradict it.

### 2. evidence.csv_path

`bridge.yaml` hardcodes `/home/user/amr-agent/...`, a container path that does
not exist on WSL (m3-07 finding). Make it machine-neutral — a path relative to
the repo root, an env-var expansion, or a CLI override, whichever the existing
config style supports most naturally. Do not invent a new configuration
mechanism if `--evidence-csv` already exists; prefer making the committed
default sane over adding knobs.

### 3. README venv path

`bridge/README.md` documents `/opt/amr-bridge-venv`. On WSL, /opt needs root
and the venv lands in `$HOME` (m3-07). Document the mechanism — a venv created
with `--system-site-packages` anywhere the user can write, with the container
and WSL locations as the two worked examples — rather than one machine's path.

## Verification

Gazebo Sim 8.11.0 is installed and headless works (`gz sim -s
--headless-rendering`, RTF ~1.0). The venv exists at
`/home/ozkan/amr-bridge-venv`. `sim/setup/WSL_ENVIRONMENT.md` documents every
WSL particular, including that `gz` requires sourcing
`/opt/ros/jazzy/setup.bash` first.

Verify what you can: the reset mapping against the running cell and the test
double, the stimulus tool driving it, the csv path resolving on this machine.
This is not m3-08 — do not run the full four-case measured loop or rewrite
evidence documents. If you append anything to an evidence file, it is a new
dated WSL section, never an edit to container numbers.

If a run is performed, isolate both transports if anything else is running
(check first): `ROS_DOMAIN_ID` and `GZ_PARTITION` — gz transport does not use
DDS, so the ROS variable alone does not isolate (LESSONS). Drive every run to
completion in the foreground; never end the turn with a process armed.

## Reporting

`docs/reports/m3-13-bridge-reset-and-paths.md` in the CLAUDE.md report shape,
then `lessons_candidates` (may be "none"). State explicitly: the
pre-first-publish behaviour, what was verified against a live cell versus
inspected only, and any file outside bridge/ you believe now disagrees.
