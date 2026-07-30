#!/usr/bin/env bash
# install.sh - reproducible setup for the amr-agent simulation layer.
#
# Target: Ubuntu 24.04 (noble), amd64, behind an HTTPS proxy that blocks
# api.github.com but allows raw.githubusercontent.com and git clone.
#
# Idempotent: every step checks before doing. Safe to re-run.
#
# What it installs by default (steps 0-3):
#   1. python3 -> python3.12 via update-alternatives (container quirk)
#   2. ROS 2 Jazzy apt source (proxy-safe key and http package host)
#   3. ROS 2 Jazzy + Gazebo Harmonic + ros_gz + Nav2 + slam_toolbox
#
# Steps 4-6 are the RB-KAIROS path (Robotnik jazzy-devel workspace, the
# closed-source controller debs and the colcon build). That platform was
# retired by ADR 0010 D1 and the steps are kept only as the record of the
# parked navigation scenario (sim/scenarios/DEFERRED.md). They are OPT-IN
# and OFF by default: nothing the project builds now needs them, and running
# them costs a multi-repository clone plus a colcon build. Enable with
#
#   ROBOTNIK=1 ./install.sh
#
# M5 note. Which packages the autonomy gate needs is no longer an open
# question: the set in ROS_PKGS below was installed and exercised in the
# session container on 2026-07-30 and every version is recorded in
# sim/setup/CONTAINER_TOOLCHAIN.md. That file is CONTAINER evidence; the
# owner's WSL host is a separate environment recorded in
# sim/setup/WSL_ENVIRONMENT.md and re-verified there on its own terms.
#
# Run as root (or with sudo).

set -euo pipefail

ROBOTNIK="${ROBOTNIK:-0}"
ROBOTNIK_WS="${ROBOTNIK_WS:-/opt/m3-feasibility/ws}"
ROS_DISTRO=jazzy

log() { echo "[install.sh] $*"; }

# --- 0. Preconditions -------------------------------------------------------
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi
. /etc/os-release
if [[ "${VERSION_CODENAME:-}" != "noble" ]]; then
  echo "Expected Ubuntu 24.04 (noble), got ${VERSION_CODENAME:-unknown}." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# --- 1. python3 -> 3.12 (container quirk) -----------------------------------
# This container ships python3.11 as the default python3 alternative, but
# ROS 2 Jazzy on noble is built against python3.12. Register and select 3.12.
if ! command -v python3.12 >/dev/null; then
  apt-get update
  apt-get install -y python3.12 python3.12-venv
fi
if [[ "$(readlink -f /usr/bin/python3)" != *python3.12 ]]; then
  log "switching python3 alternative to python3.12"
  update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 || true
  update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 2
  update-alternatives --set python3 /usr/bin/python3.12
else
  log "python3 already points to python3.12"
fi

# The alternative governs /usr/bin/python3 only. A python3 earlier on PATH
# shadows it, and the session container of 2026-07-30 had exactly that:
# /usr/local/bin/python3 -> /usr/bin/python3.11. ROS 2 itself is unaffected,
# because every console script it installs carries an absolute
# "#!/usr/bin/python3" shebang, but a bare "python3 -c 'import rclpy'" in an
# interactive shell then fails with a misleading missing-C-extension error.
# Warn rather than repoint: /usr/local/bin is not this project's to own.
SHADOW="$(command -v python3 || true)"
if [[ -n "$SHADOW" && "$SHADOW" != "/usr/bin/python3" ]] \
   && [[ "$(readlink -f "$SHADOW")" != *python3.12 ]]; then
  log "WARNING: $SHADOW shadows /usr/bin/python3 and resolves to" \
      "$(readlink -f "$SHADOW")."
  log "         ros2 and its launch files are unaffected (absolute shebang)."
  log "         For interactive ROS Python work use /usr/bin/python3 explicitly."
fi

# --- 2. ROS 2 Jazzy apt source ----------------------------------------------
# Proxy-safe: the key comes from raw.githubusercontent.com (allowed), the
# packages from packages.ros.org over plain http. Do NOT use the
# api.github.com release-asset method for ros-apt-source; api.github.com is
# blocked by the proxy. Both hops were re-verified in the session container
# on 2026-07-30: the key fetch returned HTTP/2 200 through the CONNECT proxy
# and the plain-http package host returned 200 directly.
ROS_KEYRING=/usr/share/keyrings/ros-archive-keyring.gpg
ROS_LIST=/etc/apt/sources.list.d/ros2.list
if [[ ! -f "$ROS_KEYRING" ]]; then
  log "fetching ROS apt key"
  apt-get update
  apt-get install -y curl gnupg lsb-release
  curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o "$ROS_KEYRING"
fi
if ! grep -rqs "packages.ros.org/ros2/ubuntu" /etc/apt/sources.list.d/; then
  log "adding ROS 2 apt source"
  echo "deb [arch=amd64 signed-by=$ROS_KEYRING] http://packages.ros.org/ros2/ubuntu noble main" \
    > "$ROS_LIST"
  apt-get update
fi

# --- 3. ROS 2 + Gazebo Harmonic + ros_gz + Nav2 + slam_toolbox --------------
# This is the verified M5 set. Every package here was installed in the
# session container on 2026-07-30 and exercised: the arena ran headless, all
# three scan topics reached ROS 2 through ros_gz_bridge, and the Nav2 and
# slam_toolbox nodes were started. Versions: sim/setup/CONTAINER_TOOLCHAIN.md.
#
# ros-jazzy-ros-base, not desktop-full: no GUI tool is needed for a headless
# run and the base metapackage keeps the footprint at the recorded size.
ROS_PKGS=(
  ros-jazzy-ros-base
  ros-jazzy-xacro
  ros-jazzy-robot-state-publisher
  ros-jazzy-joint-state-publisher
  # Gazebo Harmonic + ROS integration (invariant 12: Gazebo, not MuJoCo).
  # gz-sim-vendor is what puts gz sim 8 on the box; the gz binary itself only
  # reaches PATH after sourcing /opt/ros/jazzy/setup.bash.
  ros-jazzy-gz-sim-vendor
  ros-jazzy-ros-gz
  # M5 autonomy: Nav2 and lidar SLAM on the in-house forklift (ADR 0010 D1/D2)
  ros-jazzy-navigation2
  ros-jazzy-nav2-bringup
  ros-jazzy-slam-toolbox
  # workspace build tools
  python3-colcon-common-extensions
  python3-rosdep
  python3-vcstool
  git
)

# ros2_control was in this list for the RB-KAIROS vendor mecanum drive only.
# The forklift drives through gz joint-controller plugins and a vehicle node,
# not through ros2_control, and the verified container does not have these
# packages installed. They move with the rest of the retired platform behind
# ROBOTNIK=1. If a later gate needs ros2_control for the forklift, add it to
# ROS_PKGS above and re-verify rather than switching this flag on.
ROBOTNIK_PKGS=(
  ros-jazzy-ros2-control
  ros-jazzy-gz-ros2-control
  ros-jazzy-controller-manager
  ros-jazzy-joint-state-broadcaster
  ros-jazzy-joint-trajectory-controller
)
if [[ "$ROBOTNIK" == "1" ]]; then
  ROS_PKGS+=("${ROBOTNIK_PKGS[@]}")
fi

MISSING=()
for p in "${ROS_PKGS[@]}"; do
  dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p")
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
  log "installing: ${MISSING[*]}"
  apt-get update
  apt-get install -y "${MISSING[@]}"
else
  log "ROS packages already installed"
fi

if [[ "$ROBOTNIK" != "1" ]]; then
  log "done (ROS 2 Jazzy, Gazebo Harmonic, ros_gz, Nav2, slam_toolbox)."
  log "  source /opt/ros/jazzy/setup.bash"
  log "  gz sim --versions        # gz only reaches PATH after sourcing ROS"
  log "Isolate BOTH transports when another simulation may be running:"
  log "  export GZ_PARTITION=<run> ROS_DOMAIN_ID=<n>   # gz transport is not DDS"
  log "Steps 4-6 (retired RB-KAIROS platform, ADR 0010 D1) skipped."
  log "  Re-run with ROBOTNIK=1 to install them."
  exit 0
fi

# --- 4. Robotnik jazzy-devel workspace (opt-in, ROBOTNIK=1) -----------------
# Retired platform, kept as the record of the parked navigation scenario.
# Clone over https (git clone through the proxy works; api.github.com is not
# needed for plain clones).
mkdir -p "$ROBOTNIK_WS/src"
clone_if_absent() {
  local url=$1 dir=$2
  if [[ -d "$dir/.git" ]]; then
    log "already cloned: $dir"
  else
    git clone --branch jazzy-devel --depth 1 "$url" "$dir"
  fi
}
clone_if_absent https://github.com/RobotnikAutomation/robotnik_description.git "$ROBOTNIK_WS/src/robotnik_description"
clone_if_absent https://github.com/RobotnikAutomation/robotnik_simulation.git  "$ROBOTNIK_WS/src/robotnik_simulation"
clone_if_absent https://github.com/RobotnikAutomation/robotnik_sensors.git     "$ROBOTNIK_WS/src/robotnik_sensors"
clone_if_absent https://github.com/RobotnikAutomation/robotnik_common.git      "$ROBOTNIK_WS/src/robotnik_common"
clone_if_absent https://github.com/RobotnikAutomation/teleop_panel.git         "$ROBOTNIK_WS/src/teleop_panel"

# --- 5. Robotnik controller debs (opt-in, shipped inside robotnik_simulation)
# The rbkairos ros2_control profile references
# robotnik_controllers/RBKairosController. That controller is closed-source
# and distributed as .deb files in robotnik_simulation/debs/. Without them
# the controller spawner fails and the base never accepts cmd_vel.
DEBS_DIR="$ROBOTNIK_WS/src/robotnik_simulation/debs"
if ! dpkg -s ros-jazzy-robotnik-controllers >/dev/null 2>&1; then
  log "installing Robotnik controller debs from $DEBS_DIR"
  apt-get install -y \
    "$DEBS_DIR"/ros-jazzy-robotnik-common-msgs_*.deb \
    "$DEBS_DIR"/ros-jazzy-robotnik-controllers-msgs_*.deb \
    "$DEBS_DIR"/ros-jazzy-robotnik-controllers_*.deb
else
  log "robotnik_controllers already installed"
fi

# --- 6. Build the workspace (opt-in) ----------------------------------------
if [[ -f "$ROBOTNIK_WS/install/setup.bash" ]]; then
  log "workspace already built: $ROBOTNIK_WS/install"
else
  log "building workspace (colcon)"
  ( cd "$ROBOTNIK_WS" \
    && . /opt/ros/jazzy/setup.sh \
    && colcon build --symlink-install )
fi

log "done. To use:"
log "  source /opt/ros/jazzy/setup.bash"
log "  source $ROBOTNIK_WS/install/setup.bash"
log "  ros2 launch <repo>/sim/launch/warehouse_bringup.launch.py"
