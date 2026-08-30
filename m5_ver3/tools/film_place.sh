#!/usr/bin/env bash
# Place the overhead film camera into a running m5v3 world and print the topic.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SDF="$ROOT/m5_ver3/gazebo/film_overhead.sdf"
WORLD=warehouse
REQ="sdf_filename: \"${SDF}\", name: \"film_overhead\", allow_renaming: false"
gz service -s "/world/${WORLD}/create" \
  --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
  --timeout 10000 --req "$REQ"
echo "placed film_overhead from $SDF"
gz topic -l | grep -F film || true
