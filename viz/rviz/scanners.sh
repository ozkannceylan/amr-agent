#!/usr/bin/env bash
# See what the vehicle's scanners see, drawn on the vehicle.
#
# Usage:  ./viz/rviz/scanners.sh            # the vehicle demo.sh started
#         AMR_VEHICLE_SERIAL=F002 ./viz/rviz/scanners.sh
#
# The DDS domain is read from agv/forklift/vehicles/allocation.yaml, which is
# the single owner of the serial -> domain mapping (invariant 10). This script
# does not default one and does not accept a disagreeing environment: a viewer
# on the wrong domain shows an empty screen and looks like a broken sensor,
# which is exactly the confusion this file exists to end.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
SERIAL="${AMR_VEHICLE_SERIAL:-F001}"
CONFIG="$REPO/viz/rviz/forklift_scanners.rviz"
ROS_SETUP="${AMR_ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

[ -r "$ROS_SETUP" ] || { echo "no ROS 2 setup at $ROS_SETUP (set AMR_ROS_SETUP)" >&2; exit 1; }
[ -r "$CONFIG" ]    || { echo "missing $CONFIG" >&2; exit 1; }

domain="$(cd "$REPO" && python3 -c "
import sys
sys.path.insert(0, 'agv/forklift/scripts')
import vehicle_identity as vi
print(vi.load_identity('$SERIAL').domain_id)
")" || { echo "could not read $SERIAL's domain from the allocation table" >&2; exit 1; }

if [ -n "${ROS_DOMAIN_ID:-}" ] && [ "$ROS_DOMAIN_ID" != "$domain" ]; then
    echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID is set, but the allocation table gives" >&2
    echo "$SERIAL domain $domain. Run 'unset ROS_DOMAIN_ID' and try again." >&2
    exit 1
fi

# set -u is relaxed across this source: the ROS setup scripts read variables
# they have not set yet, so sourcing them under -u aborts on AMENT_TRACE_SETUP_FILES.
set +u
# shellcheck disable=SC1090
source "$ROS_SETUP"
set -u
export ROS_DOMAIN_ID="$domain"

echo "  vehicle $SERIAL on DDS domain $domain"
echo "  red = front safety scanner, orange = rear safety scanner."
echo "  The navigation lidar is a MEASUREMENT channel and starts switched off;"
echo "  tick it in the Displays panel if you want it."
echo "  Nothing drawn here is a safety verdict -- these are raw returns."
echo

exec rviz2 -d "$CONFIG"
