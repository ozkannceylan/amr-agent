#!/usr/bin/env bash
# install_rf2o.sh - rf2o_laser_odometry, from source, without root.
#
#     bash m5_ver3/tools/install_rf2o.sh
#
# WHAT IT BUILDS AND WHY IT IS NOT AN apt PACKAGE. `rf2o_laser_odometry`
# is not in the Jazzy archive at all - there is no binary to fetch, for
# any distribution - so m6/tools/install_broker.sh's shape (apt-get
# download, dpkg-deb -x into $HOME) has nothing to download. What it has
# that this script keeps is its DISCIPLINE: no sudo at any point, nothing
# system-wide, nothing committed to this repository, idempotent, and a
# refusal by name for every way it can fail. The build tree lives under
# the user's own $HOME, this file is how it reproduces, and F2's global
# constraint 14 is why it is a file and not a paragraph in a report.
#
# THE COMMIT IS PINNED AND THE PIN IS CHECKED AFTER THE FETCH. `ros2` is
# a moving branch; a figure measured against "the ros2 branch" is a claim
# about whatever that branch was on the day. RF2O_COMMIT below is the
# revision every number in EVIDENCE_FUSION.md 10 was taken on, the clone
# is detached onto exactly it, and the manifest this script writes beside
# the workspace records what was fetched so a later reader can tell a
# rebuild from a re-point.
#
# NO SUDO WAS NEEDED, AND THAT IS A MEASUREMENT AND NOT AN ASSUMPTION.
# Everything this package needs to compile was already on the rig:
# ament_cmake and eigen3_cmake_module under /opt/ros/jazzy, Eigen's
# headers at /usr/include/eigen3, Boost's headers, colcon, cmake and g++.
# Nothing had to be vendored, so this script vendors nothing - if a
# future rig is missing one of them, install_broker.sh's apt-get download
# route is the precedent to copy and the refusal below will name what
# CMake could not find.
#
# IT IS NOT A STACK CHILD AND IT IS NOT RUN BY m5v3.sh. An operator runs
# it once; `m5v3.sh start --rf2o` then refuses by name if the executable
# it produces is not there, which is the same shape as every other
# missing-file refusal on this track.
set -euo pipefail

# refuse(), the config.yaml reader and the ROS source are the track's,
# and this script uses all three: the workspace path and the pin are
# config.yaml's like every other constant here, and the build needs ROS
# sourced exactly as the stack's children do.
TOOL=install_rf2o
# shellcheck source=_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

REQUIRED_KEYS=(
    rf2o.repo rf2o.commit rf2o.workspace rf2o.package rf2o.executable
    rf2o.build_type
)
load_config "${REQUIRED_KEYS[@]}"

# THE ONE PATH THIS TRACK SPELLS AGAINST $HOME AND NOT AGAINST $REPO.
# The build tree is the USER's, not the repository's: it must not land
# under m5_ver3/ where a stray `git add` would commit a hundred megabytes
# of object files, and it must not need root. config.yaml writes it with
# a leading ~/ and the two readers - this script and m5v3.sh - expand it
# the same way.
WS="${CFG_RF2O_WORKSPACE/#\~/$HOME}"
SRC="$WS/src/$CFG_RF2O_PACKAGE"
BIN="$WS/install/$CFG_RF2O_PACKAGE/lib/$CFG_RF2O_PACKAGE/$CFG_RF2O_EXECUTABLE"
MANIFEST="$WS/m5v3_rf2o.manifest"

# THE INSTALL TEST IS "IT RUNS", NOT "THE FILE IS THERE" - and not "the
# file is there and the manifest agrees", either. That is
# install_broker.sh's rule and it is here for its reason: a run
# interrupted between the clone and the link leaves an executable that
# cannot start, and "already installed" over that is the one answer that
# helps nobody.
#   THE BINARY HAS NO --help AND NO --version. It is a plain rclcpp
#   executable whose main() spins for ever, so the only way to ask it
#   whether it runs is to START it and read its first line: it prints
#   "Initializing RF2O node..." before it has subscribed to anything.
#   Pointed at a topic nothing publishes it then does nothing at all,
#   which is why the read is bounded by `timeout` and the status is
#   swallowed - a killed process exits non-zero and that is the SUCCESS
#   case here.
#   init_pose_from_topic IS SET EMPTY EVEN IN THE PROBE, because its
#   default is /base_pose_ground_truth and a probe that subscribed to a
#   ground-truth topic - on any graph, for any length of time - would be
#   this track's one unbreakable rule broken by a health check (F2
#   constraint 13). It is spelled as YAML's empty string because rcl
#   cannot parse a bare `-p key:=`.
#   THE PROBE RUNS ON ITS OWN DOMAIN, the isolation one, so a probe on a
#   machine where the m5-ver3 stack happens to be up cannot reach it.
probe() {
    [ -x "$BIN" ] || return 0
    { ROS_DOMAIN_ID="$ROS_DOMAIN_ID" timeout 10 "$BIN" --ros-args \
        -p laser_scan_topic:=/m5v3_install_probe_no_such_topic \
        -p 'init_pose_from_topic:=""' \
        -p publish_tf:=false 2>&1 || true; } \
        | sed -n '/Initializing RF2O node/{s/.*\]: //;p;q;}'
}

report() {
    echo "  binary:   $BIN"
    echo "  manifest: $MANIFEST"
    if [ -f "$MANIFEST" ]; then
        sed 's/^/    /' "$MANIFEST"
    else
        echo "    (no manifest - this tree was not built by this script)"
    fi
    echo "  m5v3.sh start --rf2o runs it; without the flag nothing here"
    echo "  is started and the stack is the one EVIDENCE_FUSION.md 9.3"
    echo "  measured."
}

for tool in git colcon cmake g++; do
    command -v "$tool" >/dev/null 2>&1 || refuse \
        "$tool is installed" "$0 (the toolchain this build needs)" \
        "rf2o_laser_odometry is an ament_cmake package built from source;" \
        "there is no binary of it in the Jazzy archive for any distro." \
        "on a rig without $tool this cannot proceed and must not pretend to."
done

source_ros

# IDEMPOTENT, AND THE SECOND RUN IS THE COMMON ONE. This script is
# quoted in the evidence file and in m5v3.sh's own refusal, so it is run
# by people checking whether they need to run it.
ver="$(probe)"
if [ -n "$ver" ]; then
    echo "already installed: $CFG_RF2O_PACKAGE"
    echo "  $ver"
    report
    exit 0
fi

echo "building $CFG_RF2O_PACKAGE from source"
echo "  repo:   $CFG_RF2O_REPO"
echo "  commit: $CFG_RF2O_COMMIT   (pinned in $CONFIG)"
echo "  into:   $WS"

mkdir -p "$WS/src" || refuse "the workspace directory is writable" \
    "$CONFIG (rf2o.workspace)" "it resolves to $WS"

# A FRESH CLONE EVERY TIME THE PROBE SAID NO, and the old tree is
# removed rather than fetched into. A half-built or re-pointed source
# tree is exactly the state this script exists to make impossible to be
# in silently, and the clone is four megabytes.
rm -rf "$SRC"
git clone --quiet "$CFG_RF2O_REPO" "$SRC" || refuse \
    "the source could be cloned" "$CONFIG (rf2o.repo)" \
    "git clone $CFG_RF2O_REPO failed - is this rig on the network?"
git -C "$SRC" checkout --quiet --detach "$CFG_RF2O_COMMIT" 2>/dev/null || refuse \
    "the pinned commit exists in that repository" "$CONFIG (rf2o.commit)" \
    "git checkout $CFG_RF2O_COMMIT failed in $SRC" \
    "the branch has moved or the sha is mistyped; NOTHING was built."
# THE PIN IS CHECKED AFTER THE CHECKOUT AND NOT ASSUMED FROM ITS EXIT
# STATUS. `git checkout` accepts an abbreviated sha, a tag and a branch
# name alike, so the only proof that the tree is the pinned revision is
# reading the revision back off the tree.
got="$(git -C "$SRC" rev-parse HEAD)"
[ "$got" = "$CFG_RF2O_COMMIT" ] || refuse \
    "the checked-out tree IS the pinned commit" "$CONFIG (rf2o.commit)" \
    "config.yaml pins $CFG_RF2O_COMMIT" \
    "the tree is at   $got" \
    "every figure in EVIDENCE_FUSION.md 10 is that revision's."

# THE .git DIRECTORY GOES. colcon does not need it, and a source tree
# that can still be `git pull`ed is a source tree whose revision the
# manifest below stops describing the moment somebody does.
rm -rf "$SRC/.git"

( cd "$WS" && colcon build --packages-select "$CFG_RF2O_PACKAGE" \
    --cmake-args "-DCMAKE_BUILD_TYPE=$CFG_RF2O_BUILD_TYPE" ) || refuse \
    "colcon built $CFG_RF2O_PACKAGE" \
    "$WS/log/latest_build/$CFG_RF2O_PACKAGE/stdout_stderr.log" \
    "the build log is named above and CMake names what it could not find." \
    "a MISSING DEPENDENCY is the usual answer and there is no sudo here:" \
    "m6/tools/install_broker.sh is this repository's precedent for" \
    "vendoring a -dev package into \$HOME with apt-get download and" \
    "dpkg-deb -x, and CMake is pointed at the extracted include path."

{ echo "repo=$CFG_RF2O_REPO"
  echo "commit=$got"
  echo "package=$CFG_RF2O_PACKAGE"
  echo "executable=$CFG_RF2O_EXECUTABLE"
  echo "build_type=$CFG_RF2O_BUILD_TYPE"
  echo "ros_setup=$ROS_SETUP"
  echo "ros_distro=${ROS_DISTRO:-unknown}"
  echo "cmake=$(cmake --version | sed -n 1p)"
  echo "compiler=$(g++ --version | sed -n 1p)"
  # NOT `colcon version-check`, which was here first and was wrong twice:
  # it reaches the NETWORK to compare against PyPI, and it writes a
  # `log/` tree into whatever directory the script was invoked from -
  # which for the documented invocation is the repository root. A build
  # script that leaves untracked directories in the repository it was run
  # from is a build script somebody will commit by accident.
  echo "colcon=$(dpkg-query -W -f='${Version}' python3-colcon-core 2>/dev/null || echo unknown)"
  echo "built=$(date -Is)"
  echo "built_by=$0"; } > "$MANIFEST"

ver="$(probe)"
[ -n "$ver" ] || refuse \
    "the built executable starts" "$BIN" \
    "colcon reported success and the binary does not run. What it says:" \
    "$( { timeout 10 "$BIN" --ros-args -p 'init_pose_from_topic:=""' 2>&1 || true; } | sed -n 1,5p)" \
    "check its shared libraries: ldd $BIN"

echo ""
echo "installed: $CFG_RF2O_PACKAGE"
echo "  $ver"
report
