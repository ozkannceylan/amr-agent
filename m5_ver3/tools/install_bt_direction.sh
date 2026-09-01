#!/usr/bin/env bash
# install_bt_direction.sh - the DirectionStablePath behaviour-tree
# decorator, built from this repository's own source, without root.
#
#     bash m5_ver3/tools/install_bt_direction.sh
#
# WHAT IT BUILDS. m5_ver3/bt_direction_stable/ is the only C++ package on
# this track. It produces one shared library,
# lib<bt_direction.library>.so, which bt_navigator dlopen()s because
# nav2.yaml names it in `plugin_lib_names`. G5 Task 5, AMR-DEC-004.
#
# IT IS install_rf2o.sh's SHAPE AND install_rf2o.sh's DISCIPLINE: no sudo
# at any point, nothing system-wide, nothing committed to this
# repository, idempotent, and a refusal by name for every way it can
# fail. The build tree lives under the user's own $HOME because under
# m5_ver3/ it would be object files one stray `git add` from being
# committed.
#
# WHERE IT DIFFERS FROM install_rf2o.sh, AND IT IS ONE THING. rf2o is
# FETCHED from a moving branch, so a commit pin is the only way to say
# which revision a figure was measured on. This source is IN this
# repository: `git rev-parse HEAD` already says that, and the manifest
# beside the workspace records it - together with the sha256 of the one
# source file, so a build made over UNCOMMITTED edits says so too.
#
# IT REBUILDS ON EVERY RUN, WHICH IS ALSO NOT install_rf2o.sh's RULE.
# That script's "already installed" shortcut is right for a pinned
# external tree and wrong for source that this repository edits: colcon
# is incremental, an unchanged tree costs a few seconds, and the failure
# it prevents - a stale .so answering for source that has moved - is
# exactly the one nobody would notice.
#
# IT IS NOT A STACK CHILD AND IT IS NOT RUN BY m5v3.sh. An operator runs
# it once; `m5v3.sh start --nav` then refuses by name if the library it
# produces is not there, which is the same shape as every other
# missing-file refusal on this track.
set -euo pipefail

TOOL=install_bt_direction
# shellcheck source=_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

REQUIRED_KEYS=(
    bt_direction.source_dir bt_direction.workspace bt_direction.package
    bt_direction.library bt_direction.build_type bt_direction.node_id
)
load_config "${REQUIRED_KEYS[@]}"
btdir_paths

for tool in colcon cmake g++; do
    command -v "$tool" >/dev/null 2>&1 || refuse \
        "$tool is installed" "$0 (the toolchain this build needs)" \
        "bt_direction_stable is an ament_cmake package built from the" \
        "source in this repository; there is nothing to download and" \
        "nothing to fetch, and on a rig without $tool this cannot" \
        "proceed and must not pretend to."
done

[ -f "$BTDIR_SRC/package.xml" ] || refuse \
    "the package source is where config.yaml says" \
    "$CONFIG (bt_direction.source_dir)" \
    "it resolves to $BTDIR_SRC and there is no package.xml there"

source_ros
btdir_env

# THE PROBE IS "IT LOADS", NOT "THE FILE IS THERE". install_rf2o.sh's
# rule, applied to a thing that is not an executable: this library has no
# main() and cannot be started, so the honest question is the one
# bt_navigator will ask - can the loader open it with every symbol
# resolved, and does it export the entry point BT.CPP calls?
#   RTLD_NOW IS THE POINT AND ctypes ALWAYS SETS IT (_ctypes ORs it into
#   every dlopen it makes). With lazy binding a library missing an
#   rclcpp symbol opens cleanly here and aborts inside bt_navigator's
#   on_configure - several minutes and one dead lifecycle manager
#   further from the cause.
probe() {
    [ -f "$BTDIR_SO" ] || return 0
    LD_LIBRARY_PATH="$BTDIR_LD_LIBRARY_PATH" python3 -c '
import ctypes, sys
lib = ctypes.CDLL(sys.argv[1])
getattr(lib, "BT_RegisterNodesFromPlugin")
print("BT_RegisterNodesFromPlugin resolved")
' "$BTDIR_SO" 2>/dev/null || true
}

echo "building $CFG_BT_DIRECTION_PACKAGE from this repository's source"
echo "  source: $BTDIR_SRC"
echo "  into:   $BTDIR_WS"

mkdir -p "$BTDIR_WS" || refuse "the workspace directory is writable" \
    "$CONFIG (bt_direction.workspace)" "it resolves to $BTDIR_WS"

# THE SOURCE IS NOT COPIED INTO THE WORKSPACE. colcon is pointed at the
# repository tree with --paths, so there is exactly one copy of this code
# on the machine and a build can never be of a stale duplicate. Only
# build/, install/ and log/ land under $HOME.
#   THE `cd` IS install_rf2o.sh's AND FOR ITS REASON: colcon writes a
#   log/ tree into the directory it was invoked from, and a build script
#   that leaves untracked directories in the repository it was run from
#   is a build script somebody will commit by accident.
( cd "$BTDIR_WS" && colcon build \
    --paths "$BTDIR_SRC" \
    --packages-select "$CFG_BT_DIRECTION_PACKAGE" \
    --cmake-args "-DCMAKE_BUILD_TYPE=$CFG_BT_DIRECTION_BUILD_TYPE" ) || refuse \
    "colcon built $CFG_BT_DIRECTION_PACKAGE" \
    "$BTDIR_WS/log/latest_build/$CFG_BT_DIRECTION_PACKAGE/stdout_stderr.log" \
    "the build log is named above and CMake names what it could not find." \
    "the three it needs - behaviortree_cpp, nav_msgs and rclcpp - are all" \
    "in the Jazzy archive and all already on this rig for nav2's sake," \
    "so a missing one is a ROS installation this stack could not run at" \
    "all."

[ -f "$BTDIR_SO" ] || refuse \
    "the build produced the library nav2.yaml names" \
    "$CONFIG (bt_direction.library) and $BTDIR_SRC/CMakeLists.txt" \
    "colcon reported success and there is no file at $BTDIR_SO" \
    "the CMake target name IS the plugin name; if one was renamed the" \
    "other has to move with it, and nav2.yaml's plugin_lib_names is the" \
    "third copy."

{ echo "package=$CFG_BT_DIRECTION_PACKAGE"
  echo "library=$CFG_BT_DIRECTION_LIBRARY"
  echo "node_id=$CFG_BT_DIRECTION_NODE_ID"
  echo "source=$BTDIR_SRC"
  # THE REVISION AND THE FILE, BOTH, because they answer different
  # questions. The sha says what was compiled; the git revision says
  # where that came from, and `dirty` says the two need not agree.
  echo "git_revision=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "git_uncommitted_files=$(git -C "$REPO" status --porcelain -- "$CFG_BT_DIRECTION_SOURCE_DIR" 2>/dev/null | wc -l)"
  echo "source_sha256=$(sha256sum "$BTDIR_SRC/src/direction_stable_path.cpp" | cut -d' ' -f1)"
  echo "build_type=$CFG_BT_DIRECTION_BUILD_TYPE"
  echo "ros_setup=$ROS_SETUP"
  echo "ros_distro=${ROS_DISTRO:-unknown}"
  echo "nav2_bt_navigator=$(dpkg-query -W -f='${Version}' ros-jazzy-nav2-bt-navigator 2>/dev/null || echo unknown)"
  echo "cmake=$(cmake --version | sed -n 1p)"
  echo "compiler=$(g++ --version | sed -n 1p)"
  echo "colcon=$(dpkg-query -W -f='${Version}' python3-colcon-core 2>/dev/null || echo unknown)"
  echo "built=$(date -Is)"
  echo "built_by=$0"; } > "$BTDIR_MANIFEST"

loaded="$(probe)"
[ -n "$loaded" ] || refuse \
    "the built library LOADS and exports BT.CPP's entry point" \
    "$BTDIR_SO" \
    "colcon reported success and the loader will not open it." \
    "what it says:" \
    "$(LD_LIBRARY_PATH="$BTDIR_LD_LIBRARY_PATH" python3 -c '
import ctypes, sys
ctypes.CDLL(sys.argv[1])
' "$BTDIR_SO" 2>&1 | sed -n 1,5p)" \
    "check its shared libraries: ldd $BTDIR_SO"

echo ""
echo "installed: $CFG_BT_DIRECTION_PACKAGE"
echo "  $loaded"
echo "  library:  $BTDIR_SO"
echo "  manifest: $BTDIR_MANIFEST"
sed 's/^/    /' "$BTDIR_MANIFEST"
echo "  m5v3.sh start --nav puts $BTDIR_LIB_DIR on bt_navigator's"
echo "  LD_LIBRARY_PATH and nav2.yaml's plugin_lib_names names the"
echo "  library; without this build that bringup is REFUSED by name."
