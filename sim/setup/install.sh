#!/usr/bin/env bash
# install.sh - reproducible setup for the amr-agent simulation layer.
#
# Target: Ubuntu 24.04 (noble), amd64, behind an HTTPS proxy that blocks
# api.github.com but allows raw.githubusercontent.com and git clone.
#
# Idempotent: every step checks before doing. Safe to re-run.
#
# What it installs:
#   1. python3 -> python3.12 via update-alternatives (container quirk)
#   2. ROS 2 Jazzy apt source + packages (Gazebo Harmonic via gz-sim-vendor)
#   3. Robotnik jazzy-devel workspace at $ROBOTNIK_WS (default
#      /opt/m3-feasibility/ws), built with colcon
#   4. Robotnik controller debs shipped inside robotnik_simulation
#      (robotnik_controllers provides the RB-KAIROS mecanum controller;
#      it is NOT built from the workspace sources)
#
# Steps 3 and 4 are the RB-KAIROS path, retired as the vehicle platform by
# ADR 0010 D1 and kept here as the record of the parked navigation scenario
# (sim/scenarios/DEFERRED.md). Neither the M3 cell nor the M4 forklift arena
# needs them. Navigation work resumes at M5 on the in-house forklift; what
# that gate needs installed is decided at M5 briefing, not by this script.
#
# Run as root (or with sudo).

set -euo pipefail

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

# --- 2. ROS 2 Jazzy apt source ----------------------------------------------
# Proxy-safe: the key comes from raw.githubusercontent.com (allowed), the
# packages from packages.ros.org over plain http. Do NOT use the
# api.github.com release-asset method for ros-apt-source; api.github.com is
# blocked by the proxy.
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

# --- 3. ROS 2 + Gazebo Harmonic + Nav2 + build tools ------------------------
ROS_PKGS=(
  ros-jazzy-ros-base
  ros-jazzy-xacro
  ros-jazzy-robot-state-publisher
  ros-jazzy-joint-state-publisher
  # Gazebo Harmonic + ROS integration (invariant 12: Gazebo, not MuJoCo)
  ros-jazzy-gz-sim-vendor
  ros-jazzy-ros-gz
  # ros2_control stack used by the vendor mecanum drive
  ros-jazzy-ros2-control
  ros-jazzy-gz-ros2-control
  ros-jazzy-controller-manager
  ros-jazzy-joint-state-broadcaster
  ros-jazzy-joint-trajectory-controller
  # Nav2 (used from M3 navigation bringup onward)
  ros-jazzy-navigation2
  ros-jazzy-nav2-bringup
  # workspace build tools
  python3-colcon-common-extensions
  python3-rosdep
  python3-vcstool
  git
)
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

# --- 4. Robotnik jazzy-devel workspace --------------------------------------
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

# --- 5. Robotnik controller debs (shipped inside robotnik_simulation) -------
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

# --- 6. Build the workspace -------------------------------------------------
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
