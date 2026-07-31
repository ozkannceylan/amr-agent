# Brief m5-07 — ROS 2 / Gazebo / autonomy toolchain in the session container

```
gate:                M5
agent:               sim
goal:                this container can run the M5 stack — ROS 2 Jazzy,
                     Gazebo Harmonic, ros_gz, Nav2 and slam_toolbox — so M5
                     modules are verified by running them, not by review.
invariants_touched:  none
inputs:              [sim/setup/install.sh, sim/setup/WSL_ENVIRONMENT.md,
                      agv/forklift/model.sdf, sim/worlds/forklift_arena.sdf,
                      docs/LESSONS.md (the WSL, llvmpipe and gz-isolation
                      entries)]
deliverable:         a working toolchain in this container, sim/setup/
                     install.sh updated where it disagrees with what actually
                     worked, and an evidence file recording versions and the
                     verification run
done_when:           ROS 2 Jazzy, Gazebo Harmonic (gz sim 8), ros_gz,
                     navigation2 and slam_toolbox are installed with their
                     exact versions recorded; `gz sim -s -r` runs the existing
                     forklift arena headless and the existing scan topic
                     carries data through ros_gz_bridge into ROS 2, shown by a
                     captured `ros2 topic echo` sample; GL_RENDERER is read
                     from the ogre2 log and reported (LESSONS 2026-07-27 — the
                     presence of a DRI node proves nothing); install.sh
                     reflects what actually worked; and the evidence file
                     states plainly that this is CONTAINER evidence and that
                     the owner's WSL remains a separate environment to be
                     re-verified, keeping both sets rather than replacing one.
forbidden:           [editing agv/, plc/, hmi/, bridge/ or docs/ outside your
                      report; changing the model's sensor definitions (m5-04
                      owns those, in flight — if the model changes under you,
                      re-run against the new one rather than editing it);
                      raising sensor sample counts; committing (the
                      orchestrator commits); reporting a version number that
                      no command printed]
```

## Notes

Environment facts already established, do not re-derive: the target is ROS 2
**Jazzy** and Gazebo **Harmonic / gz sim 8** via `ros-jazzy-gz-sim-vendor`;
`ros-jazzy-ros-gz` is the bridge; `gz` reaches PATH only after sourcing ROS;
rendering is expected to fall back to **llvmpipe** software rendering, which
is fine and is what the owner's machine does too. `navigation2`,
`nav2-bringup` and `slam_toolbox` are listed in install.sh but were absent on
the verified WSL host — this brief is where their real package names and
versions get pinned.

Outbound HTTPS goes through a configured proxy; if apt or a key fetch fails
TLS or returns 403/405/407, read /root/.ccr/README.md and
`curl -sS "$HTTPS_PROXY/__agentproxy/status"` rather than disabling
verification.

Disk is finite (about 30 GB free at briefing). Prefer `ros-jazzy-ros-base`
plus the specific packages needed over `desktop-full`, and record the
installed footprint. If a package genuinely cannot be installed, say so and
what blocked it — a blocked report is a result, an invented version number is
not.

Two isolation rules from LESSONS, because other agents may run Gazebo
concurrently: `ROS_DOMAIN_ID` does not isolate gz transport — set
`GZ_PARTITION` as well — and match any pkill against observed `pgrep -af`
output rather than an assumed argument order.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-07-autonomy-toolchain.md.
