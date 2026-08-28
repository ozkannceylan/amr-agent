#!/usr/bin/env bash
# install_apriltag.sh - libapriltag + apriltag_ros, from the Jazzy
# archive, into the user's own $HOME, without root.
#
#     bash m5_ver3/tools/install_apriltag.sh
#
# SAME SHAPE AS install_fuse.sh: apt-get download, dpkg-deb -x, no
# sudo, versions pinned, ldd is the real check. F5 Task 1's detector
# and tag_model.py's bitmap both come from this tree so a printed
# marker and a decoded marker cannot drift.
set -euo pipefail

TOOL=install_apriltag
# shellcheck source=_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

REQUIRED_KEYS=(
    apriltag.packages apriltag.prefix apriltag.deb_prefix
    apriltag.package apriltag.executable apriltag.lib
)
load_config "${REQUIRED_KEYS[@]}"
apriltag_paths

DEBS="$APRILTAG_PREFIX/debs"

for tool in apt-get dpkg-deb dpkg-query ldd; do
    command -v "$tool" >/dev/null 2>&1 || refuse \
        "$tool is installed" "$0 (the toolchain this vendoring needs)" \
        "the packages are fetched with apt-get download, unpacked with" \
        "dpkg-deb -x and checked with ldd - all three as an ordinary user."
done

source_ros
apriltag_env

if [ -x "$APRILTAG_BIN" ] && [ -f "$APRILTAG_LIB_SO" ] && [ -f "$APRILTAG_MANIFEST" ]; then
    missing="$(LD_LIBRARY_PATH="$APRILTAG_LD_LIBRARY_PATH" ldd "$APRILTAG_BIN" \
        2>/dev/null | sed -n 's/^[[:space:]]*\(.*\) => not found$/\1/p')"
    if [ -z "$missing" ]; then
        echo "already installed: apriltag_ros ($CFG_APRILTAG_PACKAGE)"
        echo "  binary: $APRILTAG_BIN"
        echo "  lib:    $APRILTAG_LIB_SO"
        [ -f "$APRILTAG_MANIFEST" ] && sed 's/^/    /' "$APRILTAG_MANIFEST"
        exit 0
    fi
fi

mkdir -p "$APRILTAG_PREFIX" "$DEBS" || refuse \
    "the prefix directory is writable" "$CONFIG (apriltag.prefix)" \
    "it resolves to $APRILTAG_PREFIX"

echo "vendoring apriltag into $APRILTAG_PREFIX"
present=""
fetched=""
for spec in $CFG_APRILTAG_PACKAGES; do
    name="${spec%%=*}"
    want="${spec#*=}"
    [ "$name" != "$spec" ] || refuse \
        "every entry of apriltag.packages is name=version" \
        "$CONFIG (apriltag.packages)" \
        "this one has no '=' in it: $spec"
    have="$(dpkg-query -W -f='${Status}|${Version}' "$name" 2>/dev/null || true)"
    case "$have" in
        *"install ok installed"*)
            present="$present${present:+ }$name=${have#*|}"
            continue ;;
    esac
    ( cd "$DEBS" && apt-get download "$name=$want" >/dev/null 2>&1 ) || refuse \
        "the archive still carries the pinned version of $name" \
        "$CONFIG (apriltag.packages)" \
        "apt-get download $name=$want failed." \
        "what it offers now:" \
        "$(apt-cache policy "$name" 2>/dev/null | sed -n 2,3p)" \
        "NOTHING WAS INSTALLED. Re-pinning is a new measurement."
    deb="$(ls -1 "$DEBS/${name}_"*.deb 2>/dev/null | tail -n 1)"
    [ -n "$deb" ] || refuse "apt-get download left a file behind" "$DEBS" \
        "it reported success and there is no ${name}_*.deb here."
    got="$(dpkg-deb -f "$deb" Version)"
    [ "$got" = "$want" ] || refuse \
        "the downloaded $name IS the pinned version" \
        "$CONFIG (apriltag.packages)" \
        "config.yaml pins $want" \
        "the file is    $got"
    dpkg-deb -x "$deb" "$APRILTAG_PREFIX" || refuse \
        "$name unpacked into the prefix" "$deb" \
        "dpkg-deb -x failed."
    fetched="$fetched${fetched:+ }$name=$got"
    echo "  fetched $name=$got"
done

[ -x "$APRILTAG_BIN" ] || refuse \
    "the prefix now carries $CFG_APRILTAG_EXECUTABLE" \
    "$CONFIG (apriltag.package, apriltag.executable, apriltag.deb_prefix)" \
    "every deb unpacked and there is no executable at $APRILTAG_BIN"

[ -f "$APRILTAG_LIB_SO" ] || refuse \
    "the prefix now carries libapriltag" \
    "$CONFIG (apriltag.lib)" \
    "tag_model.py write loads this .so through ctypes so the printed" \
    "marker and the detector are the same family. Missing: $APRILTAG_LIB_SO"

missing="$(LD_LIBRARY_PATH="$APRILTAG_LD_LIBRARY_PATH" ldd "$APRILTAG_BIN" \
    2>/dev/null | sed -n 's/^[[:space:]]*\(.*\) => not found$/\1/p')"
[ -z "$missing" ] || refuse \
    "the dynamic loader can resolve every object $CFG_APRILTAG_EXECUTABLE needs" \
    "$CONFIG (apriltag.packages) and $APRILTAG_BIN" \
    "Not found:" \
    "$(printf '%s\n' "$missing" | sed 's/^/  /')" \
    "add the owning package to config.yaml apriltag.packages."

{ echo "prefix=$APRILTAG_PREFIX"
  echo "ros_prefix=$APRILTAG_ROS_PREFIX"
  echo "binary=$APRILTAG_BIN"
  echo "lib=$APRILTAG_LIB_SO"
  echo "ros_setup=$ROS_SETUP"
  echo "vendored=${fetched:-none}"
  echo "already_installed=${present:-none}"
  echo "installed=$(date -Is)"
} > "$APRILTAG_MANIFEST" || refuse \
    "the manifest is writable" "$APRILTAG_MANIFEST"

echo "installed: apriltag_ros"
echo "  binary: $APRILTAG_BIN"
echo "  lib:    $APRILTAG_LIB_SO"
echo "  next:   python3 m5_ver3/tools/tag_model.py write"
echo "          then m5v3.sh start --headless --localize amcl --nav --dock"
