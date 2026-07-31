#!/usr/bin/env python3
"""sensor_tf.py - static TF for the forklift's three sensor frames.

WHAT THIS NODE IS
  One publisher of /tf_static carrying one transform per scanner:

      forklift/base_link -> safety_scanner_front_link
                         -> safety_scanner_rear_link
                         -> nav_lidar_link

  Every number it publishes is READ FROM model.sdf at start-up. Nothing
  is typed into this file, into config.yaml or into a launch file, so
  moving a sensor in the model moves its transform on the next run and
  there is no second copy to age. model.sdf is the authority for the
  geometry; this node is a translator of it (CLAUDE.md invariant 10).

WHY ONE SDF-READING NODE RATHER THAN A URDF, OR THREE static_transform_publishers
  A URDF plus robot_state_publisher is the usual answer and is the wrong
  one here: it would be a SECOND geometric description of a vehicle that
  already has one, and the two would have to be kept equal by hand. Three
  static_transform_publishers are worse in the same direction - the poses
  would be typed into a launch file, three processes would publish what
  one message carries, and the launch file would silently disagree with
  the model the moment either changed. A URDF becomes the right answer
  when the vehicle needs TF for its MOVING joints (steer, drive wheel,
  mast) - that is a Nav2/SLAM decision for a later brief, and when it is
  taken this node is deleted rather than kept beside it.

WHAT IT REFUSES TO DO
  It validates the model before publishing anything, because a transform
  that quietly disagrees with the scan it belongs to is worse than no
  transform at all. Each sensor link must be attached to base_link by a
  FIXED joint, its <gz_frame_id> must name its own link, its <sensor>
  pose must be identity, and its link pose must be expressed in the model
  frame with no relative_to. If any of that fails the node reports which
  check failed and exits non-zero instead of publishing.

  The parent frame is not this node's choice either: it is the
  <robot_base_frame> model.sdf's OdometryPublisher already declares, so
  the sensor frames land on the same tree the odometry does.

WHAT IT IS NOT
  It is not a localisation solution and it publishes no dynamic
  transform. odom -> base_link is not published here and is owed by the
  brief that brings up SLAM.

Usage (after sourcing /opt/ros/jazzy/setup.bash; use /usr/bin/python3 in
the session container, per sim/setup/CONTAINER_TOOLCHAIN.md section 3.3):

  python3 agv/forklift/scripts/sensor_tf.py [--model PATH] [--ros-args ...]
  python3 agv/forklift/scripts/sensor_tf.py --print   # no ROS, no publish
"""

import argparse
import math
import os
import sys
import xml.etree.ElementTree as ET

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MODEL = os.path.normpath(os.path.join(_THIS_DIR, '..', 'model.sdf'))

#: Link every sensor frame must hang off, and the only parent this node
#: will publish. A sensor on a moving link is not a static transform.
_BASE_LINK = 'base_link'


class ModelError(Exception):
    """The model does not support a static sensor transform being published."""


class SensorFrame(object):
    """One base_link -> sensor_link transform, as read from the SDF."""

    def __init__(self, link, sensor, topic, xyz, rpy):
        self.link = link          # SDF link name == <gz_frame_id> == TF child
        self.sensor = sensor      # SDF sensor name, for the log line only
        self.topic = topic        # the channel this frame's samples arrive on
        self.xyz = xyz            # (x, y, z) in the base_link frame [m]
        self.rpy = rpy            # (roll, pitch, yaw) in the base_link frame

    @property
    def quaternion(self):
        """(x, y, z, w) for the SDF's roll-pitch-yaw, ZYX order."""
        roll, pitch, yaw = self.rpy
        cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
        cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
        cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
        return (sr * cp * cy - cr * sp * sy,
                cr * sp * cy + sr * cp * sy,
                cr * cp * sy - sr * sp * cy,
                cr * cp * cy + sr * sp * sy)


def _pose_of(elem):
    """Read an SDF <pose> child as six floats. Absent means identity."""
    pose = elem.find('pose')
    if pose is None:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), None
    values = [float(v) for v in (pose.text or '').split()]
    if len(values) != 6:
        raise ModelError(
            'pose "{}" does not carry six values'.format(pose.text))
    frame = pose.get('relative_to') or pose.get('frame')
    return tuple(values[0:3]), tuple(values[3:6]), frame


def _is_identity(xyz, rpy, tol=1e-12):
    return all(abs(v) <= tol for v in tuple(xyz) + tuple(rpy))


def read_model(path):
    """Parse model.sdf and return (base_frame, [SensorFrame, ...]).

    Raises ModelError with the failing check named, rather than
    publishing a transform the model does not justify.
    """
    model = ET.parse(path).getroot().find('model')
    if model is None:
        raise ModelError('{}: no <model> element'.format(path))

    links = {}
    for link in model.findall('link'):
        name = link.get('name')
        if name is None:
            raise ModelError('a <link> has no name attribute')
        links[name] = link

    if _BASE_LINK not in links:
        raise ModelError('no link named "{}"'.format(_BASE_LINK))

    # base_link must BE the model frame, because every other link's pose is
    # written relative to the model frame. If base_link is displaced, every
    # transform below is off by that displacement and nothing says so.
    base_xyz, base_rpy, base_rel = _pose_of(links[_BASE_LINK])
    if base_rel is not None or not _is_identity(base_xyz, base_rpy):
        raise ModelError(
            '{} is not at the model origin ({} {} relative_to={}); sensor '
            'poses are written in the model frame and would be wrong'.format(
                _BASE_LINK, base_xyz, base_rpy, base_rel))

    # Fixed joints onto base_link. A sensor link reached any other way is
    # not a static transform and this node will not pretend otherwise.
    fixed_children = set()
    joint_of = {}
    for joint in model.findall('joint'):
        parent = (joint.findtext('parent') or '').strip()
        child = (joint.findtext('child') or '').strip()
        joint_of[child] = joint.get('name')
        if joint.get('type') == 'fixed' and parent == _BASE_LINK:
            fixed_children.add(child)

    frames = []
    for name, link in sorted(links.items()):
        for sensor in link.findall('sensor'):
            frame_id = (sensor.findtext('gz_frame_id') or '').strip()
            if not frame_id:
                raise ModelError(
                    'sensor "{}" on link "{}" has no <gz_frame_id>; its '
                    'messages would carry a scoped frame no TF lookup '
                    'resolves'.format(sensor.get('name'), name))
            if frame_id != name:
                raise ModelError(
                    'sensor "{}" declares gz_frame_id "{}" but sits on link '
                    '"{}"; the frame its samples name would not be the frame '
                    'published here'.format(sensor.get('name'), frame_id, name))
            s_xyz, s_rpy, s_rel = _pose_of(sensor)
            if s_rel is not None or not _is_identity(s_xyz, s_rpy):
                raise ModelError(
                    'sensor "{}" has a non-identity pose inside its link; the '
                    'frame its angles are measured in would differ from the '
                    'frame published here by exactly that pose'.format(
                        sensor.get('name')))
            if name not in fixed_children:
                raise ModelError(
                    'link "{}" carries a sensor but is not a fixed child of '
                    '{} (joint: {}); its transform is not static'.format(
                        name, _BASE_LINK, joint_of.get(name, 'none')))
            l_xyz, l_rpy, l_rel = _pose_of(link)
            if l_rel is not None:
                raise ModelError(
                    'link "{}" has pose relative_to="{}"; this node resolves '
                    'model-frame poses only'.format(name, l_rel))
            frames.append(SensorFrame(
                link=name,
                sensor=sensor.get('name'),
                topic=(sensor.findtext('topic') or '').strip(),
                xyz=l_xyz,
                rpy=l_rpy))

    if not frames:
        raise ModelError('{}: no sensor carries a gz_frame_id'.format(path))

    # The parent frame is the one the odometry already declares, so the
    # sensor frames land on the same tree rather than beside it.
    base_frame = None
    for plugin in model.findall('plugin'):
        declared = plugin.findtext('robot_base_frame')
        if declared:
            base_frame = declared.strip()
    if not base_frame:
        raise ModelError(
            'no plugin declares <robot_base_frame>; the parent frame would '
            'be this node\'s invention rather than the model\'s statement')

    return base_frame, frames


def format_table(base_frame, frames):
    """One line per transform, in metres and degrees, for a log or a check."""
    lines = ['{:<28} {:<28} {:>8} {:>8} {:>8} {:>9} {:>9} {:>9}'.format(
        'parent', 'child', 'x [m]', 'y [m]', 'z [m]',
        'roll [d]', 'pitch [d]', 'yaw [d]')]
    for frame in frames:
        lines.append('{:<28} {:<28} {:8.4f} {:8.4f} {:8.4f} {:9.4f} {:9.4f} '
                     '{:9.4f}'.format(base_frame, frame.link,
                                      frame.xyz[0], frame.xyz[1], frame.xyz[2],
                                      math.degrees(frame.rpy[0]),
                                      math.degrees(frame.rpy[1]),
                                      math.degrees(frame.rpy[2])))
    return '\n'.join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Publish /tf_static for the forklift sensor frames.')
    parser.add_argument('--model', default=_DEFAULT_MODEL,
                        help='model SDF to read (default: %(default)s)')
    parser.add_argument('--print', dest='print_only', action='store_true',
                        help='print the transforms and exit; imports no ROS')
    args, ros_argv = parser.parse_known_args(argv)

    try:
        base_frame, frames = read_model(args.model)
    except (ModelError, ET.ParseError) as exc:
        sys.stderr.write('sensor_tf: {}\n'.format(exc))
        return 2

    if args.print_only:
        print(format_table(base_frame, frames))
        return 0

    # Imported here so --print runs on a machine with no ROS at all.
    import rclpy
    from geometry_msgs.msg import TransformStamped
    from rclpy.node import Node
    from tf2_ros import StaticTransformBroadcaster

    class SensorTf(Node):
        """Publishes the three transforms once, latched, and then idles."""

        def __init__(self, base, sensor_frames, model_path):
            super().__init__('sensor_tf')
            self.broadcaster = StaticTransformBroadcaster(self)

            stamped = []
            for frame in sensor_frames:
                tf = TransformStamped()
                tf.header.stamp = self.get_clock().now().to_msg()
                tf.header.frame_id = base
                tf.child_frame_id = frame.link
                tf.transform.translation.x = float(frame.xyz[0])
                tf.transform.translation.y = float(frame.xyz[1])
                tf.transform.translation.z = float(frame.xyz[2])
                qx, qy, qz, qw = frame.quaternion
                tf.transform.rotation.x = qx
                tf.transform.rotation.y = qy
                tf.transform.rotation.z = qz
                tf.transform.rotation.w = qw
                stamped.append(tf)

            # One message carrying all three, so a late subscriber that
            # reads the latched /tf_static gets a complete set or none.
            self.broadcaster.sendTransform(stamped)

            self.get_logger().info(
                'sensor_tf up: {} static transform(s) from {}\n{}'.format(
                    len(stamped), model_path,
                    format_table(base, sensor_frames)))

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    node = SensorTf(base_frame, frames, args.model)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
