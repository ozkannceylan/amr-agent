"""On-vehicle topic names. Single source for nodes, launch and tests.

R3: these stay on the vehicle ROS graph. Only /m8/proposal and
/m8/verdict (numbers and enums as JSON) are candidates for a later
VDA adapter. No image topic is listed as a publish.
"""

# Camera on the truck (m5_ver3/config.yaml topics.*). Subscribe only.
CAM_DEPTH = "/forklift/gz/cam/depth_image"
CAM_INFO = "/forklift/gz/cam/camera_info"
CAM_IMAGE = "/forklift/gz/cam/image"

# The vehicle telling M8 where its OWN forks are. Subscribe only, and it
# is a joint position in metres - not a command, not a frame, not a pose.
# forklift_ver3/model.sdf publishes steer_joint, drive_wheel_joint and
# mast_joint here; `m8_core.selfmask` reads the third and nothing else.
JOINT_STATE = "/forklift/gz/joint_state"
MAST_JOINT = "mast_joint"

# M8 wire. JSON text matching m8_msgs/*.msg field names. m8_msgs is
# not built in A1; std_msgs/String carries the same fields.
PROPOSAL = "/m8/proposal"
VERDICT = "/m8/verdict"
HEALTH = "/m8/health"
LOG = "/m8/log"

# Names a consumer (Phase B+) would use. A1 must not publish them.
CONSUMER_DOCK = "/m8/consumer/dock_target"
CONSUMER_ABORT = "/m8/consumer/abort"
CONSUMER_SPEED = "/m8/consumer/speed_ceiling"

# Frames the shadow nodes LOOK UP. m5_ver3/config.yaml frames.* and
# apriltag.tag_frame; M8 broadcasts none of them and must not - the
# transform tree has its owners already (F2's EKF, AMCL, apriltag_node).
FRAME_BASE = "base_link"
FRAME_CAM_OPTICAL = "pallet_cam_optical"
FRAME_TAG = "tag36h11_0"

PUBLISH_TOPICS = (PROPOSAL, VERDICT, HEALTH, LOG)
SUBSCRIBE_CAMERA = (CAM_DEPTH, CAM_INFO)
SUBSCRIBE_VEHICLE = (JOINT_STATE,)
LOOKUP_FRAMES = (FRAME_BASE, FRAME_CAM_OPTICAL, FRAME_TAG)
A1_NODE_FILES = (
    "pocket_pose_node.py",
    "abort_node.py",
    "slot_state_node.py",
    "veto_gate_node.py",
    "m8_health.py",
)
