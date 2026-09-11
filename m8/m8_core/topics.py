"""On-vehicle topic names. Single source for nodes, launch and tests.

R3: these stay on the vehicle ROS graph. Only /m8/proposal and
/m8/verdict (numbers and enums as JSON) are candidates for a later
VDA adapter. No image topic is listed as a publish.
"""

# Camera on the truck (m5_ver3/config.yaml topics.*). Subscribe only.
CAM_DEPTH = "/forklift/gz/cam/depth_image"
CAM_INFO = "/forklift/gz/cam/camera_info"
CAM_IMAGE = "/forklift/gz/cam/image"

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

PUBLISH_TOPICS = (PROPOSAL, VERDICT, HEALTH, LOG)
SUBSCRIBE_CAMERA = (CAM_DEPTH, CAM_INFO)
A1_NODE_FILES = (
    "pocket_pose_node.py",
    "abort_node.py",
    "slot_state_node.py",
    "veto_gate_node.py",
    "m8_health.py",
)
