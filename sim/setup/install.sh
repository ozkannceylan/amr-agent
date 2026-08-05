#!/usr/bin/env bash
# install.sh - reproducible setup for the amr-agent simulation layer.
#
# Target: Ubuntu 24.04 (noble), amd64, behind an HTTPS proxy that blocks
# api.github.com but allows raw.githubusercontent.com and git clone.
#
# Idempotent: every step checks before doing. Safe to re-run.
#
# What it installs (steps 0-3, all of them):
#   1. python3 -> python3.12 via update-alternatives (container quirk)
#   2. ROS 2 Jazzy apt source (proxy-safe key and http package host)
#   3. ROS 2 Jazzy + Gazebo Harmonic + ros_gz + Nav2 + slam_toolbox
#
# This script had three further steps that provisioned the vendor workspace
# of the vehicle platform retired by ADR 0010 D1 (a multi-repository clone,
# closed-source controller debs and a colcon build). m5-07 put them behind
# an opt-in flag; m5-09 removed them entirely. A retired platform does not
# get an installation path: the flag was executable content that cloned
# vendor repositories and installed closed-source packages for a vehicle
# this project does not have. Nothing here provisions it any more, and the
# parked navigation scenario it served is recorded, not runnable
# (sim/scenarios/DEFERRED.md).
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
  # The vehicle's state estimator (agv/forklift/ekf.yaml). PINNED HERE ON
  # PURPOSE, 2026-07-31: it was already on the box, but only as an AUTOMATIC
  # dependency of ros-jazzy-nav2-waypoint-follower, so `apt autoremove` would
  # take it the moment Nav2 left and the vehicle would lose the sole
  # publisher of odom -> base_link with no other symptom. Named as a direct
  # dependency it survives that. Requested by
  # docs/reports/m5-07c-realistic-odometry.md open question 1.
  ros-jazzy-robot-localization
  # workspace build tools
  python3-colcon-common-extensions
  python3-rosdep
  python3-vcstool
  git
)

# Five ros2_control packages (ros2-control, gz-ros2-control,
# controller-manager, joint-state-broadcaster, joint-trajectory-controller)
# were in this list for the retired platform's vendor mecanum drive only.
# The forklift drives through gz joint-controller plugins and a vehicle node,
# not through ros2_control, and the verified container does not have these
# packages installed. They went with the rest of the retired platform
# (m5-09, ADR 0010 D1). If a later gate needs ros2_control for the forklift,
# add it to ROS_PKGS above and re-verify.

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

# Fast-CDR / Fast-DDS COHERENCE. Measured on the owner's WSL machine
# 2026-08-05 (sim/setup/WSL_ENVIRONMENT.md section 12), and a no-op on a box
# whose whole ROS tree came from one archive snapshot.
#
# The failure it prevents: installing today's Nav2 onto a ROS tree that is
# months behind the archive puts a nav2_msgs typesupport library built
# against a NEWER Fast-CDR beside an OLDER libfastcdr, and nav2_amcl and
# controller_server then die at startup with exit code 127 and
#   undefined symbol: _ZN8eprosima7fastcdr3Cdr9serializeEj
# ldd reports nothing missing, because the fault is a symbol and not a file.
#
# Why the four are named TOGETHER and never one at a time: Fast-CDR 2.2.5 ->
# 2.2.7 is not a drop-in despite an unchanged soname (libfastcdr.so.2).
# Upgrading fastcdr alone left every ROS 2 process on that machine aborting
# at startup - the Gazebo bridge and the EKF included, not only Nav2.
# fastrtps and both rmw_fastrtps packages have to move with it.
#
# --only-upgrade, so this can never pull a package in that was not already
# there, and it does nothing at all when they are already current.
DDS_PKGS=(
  ros-jazzy-fastcdr
  ros-jazzy-fastrtps
  ros-jazzy-rmw-fastrtps-cpp
  ros-jazzy-rmw-fastrtps-shared-cpp
)
# Unconditional on purpose (m5-21b decision 2, finding 1). Guarding this on
# MISSING skipped it in exactly the case that caused the original outage: a
# machine where every ROS_PKGS entry is already present and someone later
# hand-installs a new ROS package against a stale Fast-DDS set. On an
# already-current machine --only-upgrade is a no-op, so the guard bought
# nothing and cost that hole.
log "aligning the Fast-DDS stack with the archive: ${DDS_PKGS[*]}"
apt-get install --only-upgrade -y "${DDS_PKGS[@]}"

log "done (ROS 2 Jazzy, Gazebo Harmonic, ros_gz, Nav2, slam_toolbox)."
log "  source /opt/ros/jazzy/setup.bash"
log "  gz sim --versions        # gz only reaches PATH after sourcing ROS"
log "Isolate BOTH transports when another simulation may be running:"
log "  export GZ_PARTITION=<run> ROS_DOMAIN_ID=<n>   # gz transport is not DDS"
