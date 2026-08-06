#!/usr/bin/env python3
"""vehicle_link.py - one vehicle, watched.

WHAT ONE LINK IS. One VDA 5050 serial number, the DDS domain that serial is
allocated in `allocation.yaml`, one zero-endpoint node inside that domain, one
executor thread, one refcounted subscription manager, and a store of the latest
value of each watched datum with the age of that value. n links, one process,
no republishing anywhere - the ADR 0016 D3(c) mechanism as viz/DESIGN.md
section 3 rules it.

WHAT IT FORWARDS AND WHAT IT MAY NOT DERIVE (invariant 10, DESIGN section 6).
Forwarded, each with its single owner elsewhere: the map (the vehicle's map
server), the pose (the vehicle's localization, as published), the obstacles
(the navigation lidar, as published), and the vehicle's own published TF, used
for one thing only - to express the scan's points in the map frame, which is a
frame change of a vehicle-owned datum through the vehicle's own transform and
not a new datum. Originated here, and nothing else: the ARRIVAL AGE of each
datum, which watches only this process.

Forbidden here and on the page: any localization-quality verdict, any obstacle
classification in the sense of danger or severity, any stop / mode / fault /
"vehicle alive" verdict, any fusion of monitoring-plane pose with PLC state,
and any safety statement of any kind.

THE THREE SENSOR CLASSES ARE NOT A VERDICT. Turning a LaserScan into a list of
coordinates requires reading each return the way the device means it, and
`agv/forklift/README.md` states that reading as the consumer rule for this
topic: an `inf` or a range at or beyond `range_max` is the sensor reporting no
echo inside its window - a measurement of a clear path, not missing data; a
finite range inside the window is a distance; `NaN`, `-inf` or a range below
`range_min` is invalid. Only the distance class becomes a point. The three
counts are served beside the points so the page can render what the sensor
said without recomputing anything, and no return is ever called dangerous,
near, relevant or a fault by this layer.

STALENESS RUNS ON THE STEADY CLOCK, ALWAYS. Every age below is measured with
`time.monotonic()` at message arrival. This process never subscribes `/clock`
and never runs a timeout on a message-carried stamp: the simulation clock
arrives over the very graph being watched, and a watchdog must not run on a
clock supplied by the thing it watches (docs/LESSONS.md 2026-08-06). A stalled
vehicle therefore renders as a growing age and never as last-value-as-live.
"""

import math
import os
import sys
import threading
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan
from tf2_msgs.msg import TFMessage

from subscribe_only import LATCHED, LIVE, SubscribeOnlyNode


#: The vehicle-domain topic set of DESIGN section 3. Every name is the vehicle
#: README contract's, quoted and not invented here. A name that changes there
#: changes here and nowhere else in this layer.
TOPIC_MAP = '/map'
TOPIC_POSE = '/amcl_pose'
TOPIC_SCAN = '/forklift/scan'
TOPIC_TF = '/tf'
TOPIC_TF_STATIC = '/tf_static'

#: The frame the map, and therefore every served coordinate, is expressed in.
MAP_FRAME = 'map'


def _yaw_from_quaternion(q):
    """Yaw about z. A representation of the orientation that arrived, not a
    second opinion about it."""
    siny = 2.0 * (q.w * q.z + q.x * q.y)
    cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny, cosy)


class _Timed(object):
    """A value and the steady-clock instant it arrived. Nothing else."""

    __slots__ = ('value', 'at')

    def __init__(self, value, at):
        self.value = value
        self.at = at


class SubscriptionManager(object):
    """Refcounted subscription lifecycle, keyed by topic.

    THIS IS THE CAMERA MECHANISM, BUILT NOW AND USED AT V3 (DESIGN section 7).
    The permanent subscriptions - map, pose, scan, tf - are simply entries
    whose refcount the service takes once at start and never releases. A camera
    view is an entry whose refcount is taken on first viewer and released on
    last, so "selecting a camera" is create/destroy of an operator-side DDS
    subscription and nothing else: no service call, no parameter write, no
    publisher, no vehicle-side toggle. Nothing enters a vehicle domain when a
    view opens or closes, which is also why the mechanism is indifferent to
    whatever enforcement ruling ever supersedes DESIGN section 2.
    """

    def __init__(self, node):
        self._node = node
        self._lock = threading.Lock()
        self._counts = {}

    def acquire(self, topic, msg_type, callback, qos=None):
        """First taker creates the subscription; later takers just count."""
        with self._lock:
            count = self._counts.get(topic, 0)
            if count == 0:
                self._node.subscribe(topic, msg_type, callback, qos)
            self._counts[topic] = count + 1
            return self._counts[topic]

    def release(self, topic):
        """Last releaser destroys the subscription; earlier ones just count."""
        with self._lock:
            count = self._counts.get(topic, 0)
            if count <= 0:
                return 0
            count -= 1
            if count == 0:
                self._counts.pop(topic, None)
                self._node.unsubscribe(topic)
            else:
                self._counts[topic] = count
            return count

    def census(self):
        with self._lock:
            return dict(self._counts)


class _Transforms(object):
    """The minimum tf2 this layer needs, and no more.

    Two edges are looked up and composed: `map -> forklift/odom` (published by
    the vehicle's AMCL) and `forklift/odom -> forklift/base_link` (published by
    the vehicle's EKF), plus the latched static edge from `base_link` to the
    scan's own frame. The composition is planar because everything served here
    is planar; a frame this layer cannot reach yields no points rather than an
    assumed identity.

    Every transform in it came from the vehicle. This class originates none.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._edges = {}      # child frame -> (parent, x, y, yaw)

    @staticmethod
    def _strip(frame):
        return frame[1:] if frame.startswith('/') else frame

    def ingest(self, msg):
        with self._lock:
            for tr in msg.transforms:
                child = self._strip(tr.child_frame_id)
                parent = self._strip(tr.header.frame_id)
                t = tr.transform.translation
                self._edges[child] = (parent, t.x, t.y,
                                      _yaw_from_quaternion(tr.transform.rotation))

    def to_map(self, frame):
        """Compose `frame -> map` as (x, y, yaw), or None if unreachable."""
        frame = self._strip(frame)
        x, y, yaw = 0.0, 0.0, 0.0
        with self._lock:
            for _ in range(16):          # the tree is four deep; 16 is a fuse
                if frame == MAP_FRAME:
                    return (x, y, yaw)
                edge = self._edges.get(frame)
                if edge is None:
                    return None
                parent, px, py, pyaw = edge
                cos_p, sin_p = math.cos(pyaw), math.sin(pyaw)
                x, y = (px + cos_p * x - sin_p * y,
                        py + sin_p * x + cos_p * y)
                yaw += pyaw
                frame = parent
        return None

    def known_frames(self):
        with self._lock:
            return sorted(self._edges)


class VehicleLink(object):
    """One watched vehicle. Constructs no entity itself - it asks the factory."""

    def __init__(self, serial, domain_id, node_name=None):
        self.serial = str(serial)
        self.domain_id = int(domain_id)
        self.node = SubscribeOnlyNode(
            node_name or 'viz_monitor_{}'.format(self.serial.lower()),
            self.domain_id)
        self.subscriptions = SubscriptionManager(self.node)

        self._lock = threading.Lock()
        self._pose = None            # _Timed(dict)
        self._scan = None            # _Timed(dict)
        self._map = None             # _Timed(dict)
        self._map_version = 0
        self._map_cells = b''
        self._tf = _Transforms()
        self._counts = {'map': 0, 'pose': 0, 'scan': 0, 'tf': 0}
        self.started_at = time.monotonic()

    # -- the permanent subscription set -------------------------------------

    def start(self):
        """Take the permanent refcounts and spin. Creates no other entity."""
        self.node.assert_zero_endpoints()
        self.subscriptions.acquire(TOPIC_MAP, OccupancyGrid,
                                   self.cb_map, LATCHED)
        self.subscriptions.acquire(TOPIC_POSE, PoseWithCovarianceStamped,
                                   self.cb_pose, LIVE)
        self.subscriptions.acquire(TOPIC_SCAN, LaserScan, self.cb_scan, LIVE)
        self.subscriptions.acquire(TOPIC_TF, TFMessage, self.cb_tf, LIVE)
        self.subscriptions.acquire(TOPIC_TF_STATIC, TFMessage,
                                   self.cb_tf, LATCHED)
        self.node.assert_zero_endpoints()
        self.node.spin_in_thread()
        return self

    def shutdown(self):
        self.node.shutdown()

    # -- callbacks. cb_* per docs/LESSONS.md 2026-07-27 ----------------------

    def cb_tf(self, msg):
        self._tf.ingest(msg)
        with self._lock:
            self._counts['tf'] += 1

    def cb_map(self, msg):
        # THE CELLS, VERBATIM. `int8[]` arrives as an `array.array('b')` (or a
        # numpy array); both expose the underlying buffer, so the bytes served
        # are the bytes received, one per cell, in row-major order. The
        # element-wise path is the fallback for a build that hands back a plain
        # list, and it produces the identical bytes.
        raw = msg.data
        if hasattr(raw, 'tobytes'):
            cells = raw.tobytes()
        else:
            cells = bytes(bytearray((int(c) & 0xFF) for c in raw))
        meta = {
            'resolution_m': float(msg.info.resolution),
            'width': int(msg.info.width),
            'height': int(msg.info.height),
            'origin': {
                'x_m': float(msg.info.origin.position.x),
                'y_m': float(msg.info.origin.position.y),
                'yaw_rad': _yaw_from_quaternion(msg.info.origin.orientation),
            },
            'frame': msg.header.frame_id or MAP_FRAME,
        }
        with self._lock:
            self._map_version += 1
            self._map_cells = cells
            self._map = _Timed(meta, time.monotonic())
            self._counts['map'] += 1

    def cb_pose(self, msg):
        p = msg.pose.pose
        value = {
            'x_m': float(p.position.x),
            'y_m': float(p.position.y),
            'yaw_rad': _yaw_from_quaternion(p.orientation),
            'frame': msg.header.frame_id or MAP_FRAME,
        }
        with self._lock:
            self._pose = _Timed(value, time.monotonic())
            self._counts['pose'] += 1

    def cb_scan(self, msg):
        """Turn one scan into map-frame points, by the vehicle's own reading rule."""
        frame = msg.header.frame_id
        placement = self._tf.to_map(frame)

        clear = distance = invalid = 0
        points = []
        angle = msg.angle_min
        r_min, r_max = float(msg.range_min), float(msg.range_max)
        for rng in msg.ranges:
            a = angle
            angle += msg.angle_increment
            if math.isinf(rng) and rng > 0.0:
                clear += 1
                continue
            if math.isnan(rng) or rng < r_min or (math.isinf(rng) and rng < 0):
                invalid += 1
                continue
            if rng >= r_max:
                clear += 1
                continue
            distance += 1
            if placement is not None:
                px, py = rng * math.cos(a), rng * math.sin(a)
                ox, oy, oyaw = placement
                cos_o, sin_o = math.cos(oyaw), math.sin(oyaw)
                points.append([round(ox + cos_o * px - sin_o * py, 4),
                               round(oy + sin_o * px + cos_o * py, 4)])

        value = {
            'frame': MAP_FRAME if placement is not None else None,
            'source_frame': frame,
            'placed': placement is not None,
            'points': points,
            'returns': {'distance': distance, 'clear_beyond_range': clear,
                        'invalid': invalid, 'total': len(msg.ranges)},
        }
        with self._lock:
            self._scan = _Timed(value, time.monotonic())
            self._counts['scan'] += 1

    # -- what the HTTP face serves ------------------------------------------

    @staticmethod
    def _age_ms(entry, now):
        return None if entry is None else round((now - entry.at) * 1000.0, 1)

    def state(self):
        """The values-only payload of DESIGN section 5. Never a raster."""
        now = time.monotonic()
        with self._lock:
            pose, scan, mapmeta = self._pose, self._scan, self._map
            version, cell_count = self._map_version, len(self._map_cells)
            counts = dict(self._counts)
        return {
            'serial': self.serial,
            'domain_id': self.domain_id,
            'node': self.node.node_name,
            'pose': None if pose is None else pose.value,
            'pose_age_ms': self._age_ms(pose, now),
            'obstacles': None if scan is None else scan.value,
            'obstacles_age_ms': self._age_ms(scan, now),
            'map_version': version,
            'map_meta': None if mapmeta is None else mapmeta.value,
            'map_age_ms': self._age_ms(mapmeta, now),
            'map_cells': cell_count,          # a COUNT, not the cells
            'messages_received': counts,
            'tf_frames': self._tf.known_frames(),
            'watching_for_s': round(now - self.started_at, 1),
            'subscriptions': self.subscriptions.census(),
        }

    def map_bytes(self):
        """The WHOLE grid, full extent, never a crop, with its version."""
        with self._lock:
            return self._map_version, self._map_cells, (
                None if self._map is None else dict(self._map.value))
