#!/usr/bin/env bash
# install_broker.sh - mosquitto without root. `apt-get download` fetches
# the Ubuntu packages into a temp dir and `dpkg-deb -x` unpacks them into
# the user's home; no sudo at any point, nothing system-wide, and the
# binary is NOT committed - this script is how it reproduces.
# mosquitto 2.x run with no config listens on localhost only and allows
# anonymous local clients, which is exactly the M6.2 posture (the broker
# moves to the fleet side in M6.3).
#
# WHY FIVE PACKAGES AND NOT ONE. Measured on Ubuntu noble against
# 2.0.18-1build3: the extracted binary would not start, and `ldd` named
# libwrap.so.0, libdlt.so.2 and libwebsockets.so.19 "not found". All
# three are NEEDED entries in the ELF, so the loader demands them whether
# or not a config-less broker uses tcp-wrappers, DLT logging or
# websockets - libwrap0, libdlt2 and libwebsockets19t64 are those three.
# Everything else the binary links (libssl3, libcrypto3, libsystemd,
# libcap...) is already on the system and was left there. libmosquitto1
# is the CLIENT library, taken along so anything that links a mosquitto
# client here links the same version as the broker it talks to.
#
# THE VENDORED LIBS ARE NOT ON THE LOADER'S PATH, and putting them there
# is exactly the root this script does not have. Whoever runs the binary
# sets LD_LIBRARY_PATH to the lib dir printed at the end; m6.sh does
# it on the broker's spawn line, for that one child. Without it the exec
# fails with status 127 and no broker.
set -euo pipefail
DEST="$HOME/.local/mosquitto-vendored"
BIN="$DEST/usr/sbin/mosquitto"
# Ubuntu's amd64 multiarch dir - where these .debs put their libraries.
# MAINTENANCE OBLIGATION: m6.sh spells the same path in BROKER_LIB,
# because a shell script cannot ask this one where it put things.
LIB="$DEST/usr/lib/x86_64-linux-gnu"
PKGS=(mosquitto libmosquitto1 libwrap0 libdlt2 libwebsockets19t64)

# THE INSTALL TEST IS "IT RUNS", NOT "THE FILE IS THERE". A run
# interrupted between two dpkg-deb calls leaves an executable binary that
# cannot start, and "already installed" over that is the one answer that
# helps nobody. So the probe prints the broker's own version line and
# prints NOTHING when the binary is missing or unable to load its libs.
#   `mosquitto -h` EXITS 3 - measured - so its status is swallowed here
#   rather than ending the script under `set -e`.
#   `sed -n 1p` and not `head -1`, because head exits at the first line
#   and leaves the writer in the SIGPIPE race that `pipefail` would then
#   report as a failed install (the same trap as m6.sh's port guard).
#   2>/dev/null so the loader's "error while loading shared libraries"
#   is not mistaken for a version line.
probe() {
    [ -x "$BIN" ] || return 0
    { LD_LIBRARY_PATH="$LIB" "$BIN" -h 2>/dev/null || true; } | sed -n 1p
}

ver="$(probe)"
if [ -n "$ver" ]; then
    echo "already installed: $BIN"
    echo "  $ver"
    echo "  libs: $LIB"
    exit 0
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
( cd "$TMP" && apt-get download "${PKGS[@]}" )
mkdir -p "$DEST"
for deb in "$TMP"/*.deb; do dpkg-deb -x "$deb" "$DEST"; done
ver="$(probe)"
if [ -z "$ver" ]; then
    echo "extract failed - $BIN is not there or cannot load its libraries."
    echo "  LD_LIBRARY_PATH=$LIB ldd $BIN"
    echo "names what is missing; add its package to PKGS above and rerun."
    exit 1
fi
echo "installed: $BIN"
echo "  $ver"
echo "  libs: $LIB  (export LD_LIBRARY_PATH to run it by hand)"
