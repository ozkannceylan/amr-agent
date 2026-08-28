#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
set -u
echo "=== dpkg-query depends ==="
for p in ros-jazzy-apriltag ros-jazzy-apriltag-msgs ros-jazzy-apriltag-ros \
         ros-jazzy-camera-ros ros-jazzy-cv-bridge ros-jazzy-image-proc \
         ros-jazzy-image-transport ros-jazzy-image-transport-plugins \
         ros-jazzy-tf2-ros ros-jazzy-sensor-msgs libopencv-core406t64 \
         libopencv-calib3d406t64 libconsole-bridge1.0; do
  if dpkg-query -W "$p" >/dev/null 2>&1; then
    echo "HAVE $p $(dpkg-query -W -f='${Version}' "$p")"
  else
    echo "MISS $p"
  fi
done
echo DONE
