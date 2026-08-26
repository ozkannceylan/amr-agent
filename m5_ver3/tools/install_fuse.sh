#!/usr/bin/env bash
# install_fuse.sh - the `fuse` factor-graph estimator, from the Jazzy
# archive, into the user's own $HOME, without root.
#
#     bash m5_ver3/tools/install_fuse.sh
#
# WHAT IT INSTALLS AND WHY IT IS NOT A SOURCE BUILD. Every package this
# arm needs IS in the ROS 2 Jazzy archive this rig is already configured
# for - `apt-cache policy ros-jazzy-fuse-core` names a candidate - so
# unlike tools/install_rf2o.sh there is a binary to fetch and nothing to
# compile. What there is NOT is permission to install it: F2's global
# constraint 14 is that this rig has no sudo, verified, so `apt-get
# install` is not available and neither is anything that writes under
# /opt or /usr. m6/tools/install_broker.sh is this repository's
# precedent for the way out - `apt-get download` fetches a .deb as an
# ordinary user, `dpkg-deb -x` unpacks it wherever it is told, and
# neither touches the dpkg database - and this script is that shape with
# tools/install_rf2o.sh's discipline: every constant from config.yaml, a
# refusal by name for every way it can fail, idempotent through a
# BEHAVIOURAL probe rather than a file test, and a manifest beside the
# tree recording exactly what was fetched.
#
# THE VERSIONS ARE PINNED AND THE PIN IS CHECKED AFTER THE FETCH.
# config.yaml's fuse.packages carries `name=version` for all nine, and
# `apt-get download name=version` will fetch that version or fail. The
# version is read back off each downloaded file with `dpkg-deb -f`
# anyway, because an archive that has moved on is exactly the state a
# figure quoted against "fuse 1.1.5" must not be measured in silently.
#
# WHAT IT VENDORS IS ONLY WHAT THIS RIG IS MISSING, AND THAT IS CHECKED
# PER PACKAGE. `apt-cache depends --recurse` over the seven fuse packages
# names 654 distinct packages because it follows every ALTERNATIVE of
# every Depends line - six versions of flang, five of gcc, three DDS
# implementations nothing here uses. The nine in config.yaml are what
# `dpkg-query -W` said was actually absent on this rig; this script asks
# that question again on whatever rig it is run on, skips what is already
# installed system-wide, and records both answers in the manifest.
#   AND THE REAL CHECK IS `ldd`, NOT A DEPENDENCY GRAPH. `dpkg-deb -x`
#   performs no dependency resolution at all, so the honest test of
#   "did we vendor enough" is whether the dynamic loader can resolve the
#   binary. It is run below and it refuses by name, listing the objects
#   it could not find, because THAT is the message that tells the next
#   operator what to add to fuse.packages.
#
# HOW A dpkg-x'd ROS PACKAGE IS MADE FINDABLE, WHICH IS THE ONE PIECE OF
# PLUMBING HERE. A ROS deb's payload is rooted at /opt/ros/jazzy, so the
# unpacked tree is $prefix/opt/ros/jazzy/{lib,share,include} and TWO
# search paths have to name it:
#   LD_LIBRARY_PATH   for libfuse_core.so and the eight beside it. The
#                     executable is linked against them by SONAME with
#                     no RPATH that reaches outside /opt/ros/jazzy.
#   AMENT_PREFIX_PATH for everything pluginlib does. fuse loads its
#                     motion models, sensor models and publishers as
#                     pluginlib classes, and pluginlib finds them through
#                     the ament index: it asks ament_index_cpp for the
#                     `fuse_core__pluginlib__plugin` resource, reads the
#                     named package's package.xml out of <prefix>/share,
#                     and only then dlopen()s the library. Without this
#                     the node starts and fails to load a single plugin.
# Both are computed in tools/_common.sh's fuse_paths()/fuse_env(), which
# is where m5v3.sh reads them from too - the path arithmetic and the two
# exports are a MECHANISM, and a second copy of it in the launcher would
# drift the way _common.sh's own header says two copies of a list did.
#   NO PYTHONPATH, DELIBERATELY. fuse_msgs ships python bindings and
#   nothing on this track imports them: the estimator is C++ and every
#   instrument here reads nav_msgs/Odometry, which is the system's. A
#   search path exported for a thing nobody imports is a claim this
#   install does not make.
#
# IT IS NOT A STACK CHILD AND IT IS NOT RUN BY m5v3.sh. An operator runs
# it once; `m5v3.sh start --fuse` then refuses by name if the executable
# it produces is not there, which is the same shape as every other
# missing-file refusal on this track.
set -euo pipefail

TOOL=install_fuse
# shellcheck source=_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

REQUIRED_KEYS=(
    fuse.packages fuse.prefix fuse.deb_prefix fuse.package fuse.executable
    fuse.node_name
)
load_config "${REQUIRED_KEYS[@]}"
# THE PATHS, FROM _common.sh, AND NOT SPELLED AGAIN HERE. fuse_paths()
# sets FUSE_PREFIX, FUSE_ROS_PREFIX, FUSE_BIN and FUSE_MANIFEST off
# config.yaml's fuse.prefix / fuse.deb_prefix / fuse.package /
# fuse.executable, and m5v3.sh calls the same function.
fuse_paths

DEBS="$FUSE_PREFIX/debs"

# THE INSTALL TEST IS "IT LOADS ITS PLUGINS", NOT "THE FILE IS THERE".
# install_broker.sh's rule, and here it has to reach further than a
# `--version` would: this executable is present the moment the first deb
# is unpacked, and every way this install can be HALF done - a missing
# shared object, a share/ tree the ament index cannot see, one deb
# fetched and the next one not - leaves a binary that starts and then
# cannot load fuse_models. So the probe runs a self-contained parameter
# file whose ignition sensor and publisher are BOTH fuse_models plugins,
# and reads back the one line that only exists on the far side of
# pluginlib having resolved them, dlopen()ed them and run their onInit:
#
#   [INFO] [...] [<node>]: Received a set_pose request (stamp: ...)
#
# emitted by fuse_models::Unicycle2DIgnition when publish_on_startup
# fires. A binary that cannot find its libraries never reaches it, and
# neither does one whose AMENT_PREFIX_PATH is wrong.
#   THE PROBE IS NOT ALLOWED TO TOUCH A LIVE STACK, and it takes three
#   precautions rather than trusting one:
#     A NODE NAME OF ITS OWN, not config.yaml's fuse.node_name. Two nodes
#     of the same name on one domain is a graph nobody can reason about,
#     and this script is run by people checking whether they need to run
#     it - which is a thing done with the stack up.
#     publish_tf FALSE. Odometry2DPublisher defaults to broadcasting
#     odom -> base_link. That edge has exactly one owner at a time on
#     this stack and a HEALTH CHECK is not it (ver2 invariant 10).
#     A topic nothing subscribes to, and use_sim_time false so it does
#     not wait for a clock it has no business reading.
#   THE PARAMETER FILE IS THE PROBE'S OWN AND NOT config.yaml's
#   fuse.params_file. The shipped file's sensors take a REQUIRED `topic`
#   that m5v3.sh supplies on the command line, so loading it here would
#   test this script's ability to spell those topics rather than the
#   install. It is written under the prefix, not in /tmp, so a refusal
#   leaves it where it can be read.
probe() {
    local out="$FUSE_PREFIX/probe.yaml" node="${CFG_FUSE_NODE_NAME}_install_probe"
    [ -x "$FUSE_BIN" ] || return 0
    cat > "$out" <<EOF
$node:
  ros__parameters:
    motion_models:
      probe_motion_model:
        type: fuse_models::Unicycle2D
    probe_motion_model:
      process_noise_diagonal: [0.05, 0.05, 0.06, 0.025, 0.025, 0.02, 0.01, 0.01]
    sensor_models:
      probe_ignition:
        type: fuse_models::Unicycle2DIgnition
        motion_models: [probe_motion_model]
        ignition: true
    probe_ignition:
      publish_on_startup: true
      topic: "${node}/set_pose"
      set_pose_service: "${node}/set_pose"
      set_pose_deprecated_service: "${node}/set_pose_deprecated"
    publishers:
      probe_publisher:
        type: fuse_models::Odometry2DPublisher
    probe_publisher:
      publish_tf: false
EOF
    { AMENT_PREFIX_PATH="$FUSE_AMENT_PREFIX_PATH" \
      LD_LIBRARY_PATH="$FUSE_LD_LIBRARY_PATH" \
      ROS_DOMAIN_ID="$ROS_DOMAIN_ID" \
      timeout 20 "$FUSE_BIN" --ros-args -r __node:="$node" \
        --params-file "$out" \
        -p use_sim_time:=false \
        -p probe_publisher.topic:="/${node}/odometry" \
        2>&1 || true; } \
        | sed -n '/Received a set_pose request/{s/.*\]: //;p;q;}'
}

report() {
    echo "  binary:   $FUSE_BIN"
    echo "  manifest: $FUSE_MANIFEST"
    if [ -f "$FUSE_MANIFEST" ]; then
        sed 's/^/    /' "$FUSE_MANIFEST"
    else
        echo "    (no manifest - this tree was not written by this script)"
    fi
    echo "  m5v3.sh start --fuse runs it INSTEAD of ekf_node; without the"
    echo "  flag nothing here is started, fuse.yaml is never named, and the"
    echo "  stack is the one EVIDENCE_FUSION.md 9.3 measured."
}

for tool in apt-get dpkg-deb dpkg-query ldd; do
    command -v "$tool" >/dev/null 2>&1 || refuse \
        "$tool is installed" "$0 (the toolchain this vendoring needs)" \
        "the packages are fetched with apt-get download, unpacked with" \
        "dpkg-deb -x and checked with ldd - all three as an ordinary" \
        "user. On a rig without $tool this cannot proceed and must not" \
        "pretend to."
done

source_ros
# THE TWO SEARCH PATHS, AFTER source_ros AND NOT BEFORE IT. They are
# built by PREPENDING to what /opt/ros/jazzy/setup.bash exports, so a
# copy taken before that line would name a prefix path with the whole of
# ROS missing from it.
fuse_env

# IDEMPOTENT, AND THE SECOND RUN IS THE COMMON ONE - install_rf2o.sh's
# note. This script is quoted in the evidence file and in m5v3.sh's own
# refusal, so it is run by people checking whether they need to run it.
mkdir -p "$FUSE_PREFIX" || refuse "the prefix directory is writable" \
    "$CONFIG (fuse.prefix)" "it resolves to $FUSE_PREFIX"
ver="$(probe)"
if [ -n "$ver" ]; then
    echo "already installed: fuse ($CFG_FUSE_PACKAGE)"
    echo "  $ver"
    report
    exit 0
fi

echo "vendoring fuse into $FUSE_PREFIX"
echo "  from:   the ROS 2 Jazzy archive this rig is configured for"
echo "  pinned: $CONFIG (fuse.packages)"

mkdir -p "$DEBS" || refuse "the download directory is writable" \
    "$CONFIG (fuse.prefix)" "it resolves to $DEBS"

# WHAT IS ALREADY HERE IS NOT FETCHED, and the question is asked per
# package on THIS rig rather than assumed from config.yaml's list. A
# package installed system-wide is already on every search path the
# loader and the ament index use, and vendoring a second copy of it into
# a prefix that comes FIRST on both would be quietly overriding the
# rig's version with the pin - which is a thing to do on purpose or not
# at all.
present=""
fetched=""
for spec in $CFG_FUSE_PACKAGES; do
    name="${spec%%=*}"
    want="${spec#*=}"
    [ "$name" != "$spec" ] || refuse \
        "every entry of fuse.packages is name=version" "$CONFIG (fuse.packages)" \
        "this one has no '=' in it: $spec" \
        "the pin is what makes EVIDENCE_FUSION.md 11 reproducible."
    have="$(dpkg-query -W -f='${Status}|${Version}' "$name" 2>/dev/null || true)"
    case "$have" in
        *"install ok installed"*)
            present="$present${present:+ }$name=${have#*|}"
            continue ;;
    esac
    ( cd "$DEBS" && apt-get download "$name=$want" >/dev/null 2>&1 ) || refuse \
        "the archive still carries the pinned version of $name" \
        "$CONFIG (fuse.packages)" \
        "apt-get download $name=$want failed. Either this rig is off the" \
        "network, or the archive has moved past that version - ROS's" \
        "noble repository keeps ONE build per package and drops the" \
        "previous one, so a pin can expire." \
        "what it offers now:" \
        "$(apt-cache policy "$name" 2>/dev/null | sed -n 2,3p)" \
        "NOTHING WAS INSTALLED. Re-pinning is a decision with a" \
        "measurement attached: every figure in EVIDENCE_FUSION.md 11 is" \
        "the pinned versions', so a new pin is a re-run and not an edit."
    deb="$(ls -1 "$DEBS/${name}_"*.deb 2>/dev/null | tail -n 1)"
    [ -n "$deb" ] || refuse "apt-get download left a file behind" "$DEBS" \
        "it reported success and there is no ${name}_*.deb here."
    # THE PIN IS CHECKED OFF THE FILE AND NOT ASSUMED FROM THE EXIT
    # STATUS - install_rf2o.sh's rule about `git checkout` accepting a
    # branch name, in this file's currency.
    got="$(dpkg-deb -f "$deb" Version)"
    [ "$got" = "$want" ] || refuse \
        "the downloaded $name IS the pinned version" "$CONFIG (fuse.packages)" \
        "config.yaml pins $want" \
        "the file is    $got" \
        "$deb"
    dpkg-deb -x "$deb" "$FUSE_PREFIX" || refuse \
        "$name unpacked into the prefix" "$deb" \
        "dpkg-deb -x failed. It writes no dpkg state and needs no root," \
        "so the usual answer is a full disk or a read-only \$HOME."
    fetched="$fetched${fetched:+ }$name=$got"
    echo "  fetched $name=$got"
done

[ -n "$fetched" ] \
    || echo "  (nothing to fetch - every pinned package was installed)"

[ -x "$FUSE_BIN" ] || refuse \
    "the prefix now carries $CFG_FUSE_EXECUTABLE" \
    "$CONFIG (fuse.package, fuse.executable, fuse.deb_prefix)" \
    "every deb unpacked and there is no executable at $FUSE_BIN" \
    "the usual cause is fuse.deb_prefix not matching the archive's" \
    "layout: a ROS deb's payload is rooted at /opt/ros/<distro>, so the" \
    "path under the prefix is that, without the leading slash." \
    "what IS under the prefix:" \
    "$(find "$FUSE_PREFIX" -maxdepth 5 -type d -name lib 2>/dev/null | sed -n 1,5p)"

# THE LOADER IS THE DEPENDENCY CHECK, because dpkg-deb -x ran none.
# `ldd` resolves against LD_LIBRARY_PATH, so it is asked with exactly the
# environment m5v3.sh will hand the child - a check made under a
# different loader path is a check about a different program.
missing="$(LD_LIBRARY_PATH="$FUSE_LD_LIBRARY_PATH" ldd "$FUSE_BIN" 2>/dev/null \
    | sed -n 's/^[[:space:]]*\(.*\) => not found$/\1/p')"
[ -z "$missing" ] || refuse \
    "the dynamic loader can resolve every object $CFG_FUSE_EXECUTABLE needs" \
    "$CONFIG (fuse.packages) and $FUSE_BIN" \
    "dpkg-deb -x runs NO dependency resolution, so this is the check" \
    "that says whether enough was vendored. Not found:" \
    "$(printf '%s\n' "$missing" | sed 's/^/  /')" \
    "find the package that owns each - 'apt-file search <soname>', or" \
    "'apt-cache depends ros-jazzy-fuse-core' - and add it to" \
    "config.yaml's fuse.packages with its exact version. Do NOT install" \
    "it: there is no sudo on this rig (F2 constraint 14)."

{ echo "prefix=$FUSE_PREFIX"
  echo "ros_prefix=$FUSE_ROS_PREFIX"
  echo "binary=$FUSE_BIN"
  echo "node_name=$CFG_FUSE_NODE_NAME"
  echo "ros_setup=$ROS_SETUP"
  echo "ros_distro=${ROS_DISTRO:-unknown}"
  # THE TWO LISTS ARE KEPT APART BECAUSE THEY ANSWER DIFFERENT
  # QUESTIONS. `vendored` is what this prefix CONTAINS and therefore
  # what a figure taken on it depends on; `already_installed` is what
  # this rig supplied, which is the row that will differ on the next
  # machine and the first thing to read when it behaves differently.
  echo "vendored=${fetched:-none}"
  echo "already_installed=${present:-none}"
  echo "debs=$DEBS"
  echo "dpkg_deb=$(dpkg-deb --version | sed -n 1p)"
  echo "installed=$(date -Is)"
  echo "installed_by=$0"; } > "$FUSE_MANIFEST"

ver="$(probe)"
[ -n "$ver" ] || refuse \
    "the vendored node loads its fuse_models plugins" "$FUSE_BIN" \
    "every deb unpacked, the loader resolves every object, and the node" \
    "did not reach its ignition sensor. What it says:" \
    "$( { AMENT_PREFIX_PATH="$FUSE_AMENT_PREFIX_PATH" \
          LD_LIBRARY_PATH="$FUSE_LD_LIBRARY_PATH" \
          ROS_DOMAIN_ID="$ROS_DOMAIN_ID" \
          timeout 20 "$FUSE_BIN" --ros-args \
            -r __node:="${CFG_FUSE_NODE_NAME}_install_probe" \
            --params-file "$FUSE_PREFIX/probe.yaml" \
            -p use_sim_time:=false 2>&1 || true; } | sed -n 1,6p)" \
    "a plugin that will not load is almost always AMENT_PREFIX_PATH:" \
    "pluginlib finds a class through the ament index and not through" \
    "the loader. Check that $FUSE_ROS_PREFIX/share/ament_index exists."

echo ""
echo "installed: fuse ($CFG_FUSE_PACKAGE)"
echo "  $ver"
report
