#!/usr/bin/env bash
# scan_viz_repeater.sh - build-if-stale wrapper for scan_viz_repeater.cc.
#
# This directory ships plain sources on purpose (no colcon package, no
# build system), and the repeater is the one tool here that cannot be
# Python: publishing a gz message with a corrected world_pose needs
# gz-transport, whose Python bindings do not ship with ROS Jazzy's vendor
# packages (measured m5-73; gz.msgs10 ships, gz.transport13 does not). So
# the wrapper compiles the single .cc on first use, recompiles when the
# source is newer than the binary, and execs the result with the caller's
# arguments unchanged. The binary lands in a build/ sibling that is not
# committed.
#
# Needs the sourced ROS Jazzy environment, both to compile (vendor
# headers) and to run (vendor libraries via LD_LIBRARY_PATH). Every
# caller of vehicle.launch.py has it by construction. Fails loudly when
# it is absent rather than producing a binary that cannot load.

set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/scan_viz_repeater.cc"
BIN_DIR="$HERE/build"
BIN="$BIN_DIR/scan_viz_repeater"
OPT="${AMR_GZ_VENDOR_OPT:-/opt/ros/jazzy/opt}"

for d in gz_transport_vendor gz_msgs_vendor gz_utils_vendor gz_math_vendor; do
    if [ ! -d "$OPT/$d" ]; then
        echo "[scan_viz_repeater.sh] $OPT/$d not found - is the ROS Jazzy" \
             "environment installed? (set AMR_GZ_VENDOR_OPT to override)" >&2
        exit 3
    fi
done

if [ ! -x "$BIN" ] || [ "$SRC" -nt "$BIN" ]; then
    echo "[scan_viz_repeater.sh] building $BIN" >&2
    mkdir -p "$BIN_DIR"
    g++ -std=c++17 -O2 -o "$BIN" "$SRC" \
        -I"$OPT/gz_transport_vendor/include/gz/transport13" \
        -I"$OPT/gz_msgs_vendor/include/gz/msgs10" \
        -I"$OPT/gz_utils_vendor/include/gz/utils2" \
        -I"$OPT/gz_math_vendor/include/gz/math7" \
        -L"$OPT/gz_transport_vendor/lib" \
        -L"$OPT/gz_msgs_vendor/lib" \
        -L"$OPT/gz_utils_vendor/lib" \
        -lgz-transport13 -lgz-msgs10 -lgz-utils2 -lprotobuf
fi

exec "$BIN" "$@"
