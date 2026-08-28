#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
set -u
echo "=== find_library ==="
python3 - <<'PY'
import ctypes.util
print(repr(ctypes.util.find_library("apriltag")))
PY
echo "=== dpkg ==="
dpkg -l | grep -i april || true
echo "=== apt-cache ros-jazzy-april ==="
apt-cache search ros-jazzy-april || true
echo "=== apt-cache libapril ==="
apt-cache search libapril || true
echo "=== which gz ==="
command -v gz || true
echo PKG_DONE
