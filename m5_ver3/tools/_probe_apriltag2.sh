#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
set -u
echo "=== policy ==="
apt-cache policy ros-jazzy-apriltag ros-jazzy-apriltag-ros ros-jazzy-apriltag-msgs libapriltag3t64
echo "=== depends apriltag-ros ==="
apt-cache depends ros-jazzy-apriltag-ros
echo "=== rtf sample_s ==="
python3 - <<'PY'
import yaml
p="/mnt/c/Users/ozkan/projects/amr-agent/m5_ver3/config.yaml"
# naive: just grep via open
text=open(p,encoding="utf-8").read()
for line in text.splitlines():
    if "sample_s" in line and "rtf" in line.lower() or line.strip().startswith("sample_s:"):
        print(line)
PY
echo DONE
