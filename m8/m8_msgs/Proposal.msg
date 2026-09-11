# m8_msgs/Proposal.msg
# One ROS message type for every M8 proposal (ARCHITECTURE.md §4).
# A0 ships the .msg as the contract; nodes that publish it land in A1.
# Payload meaning is kind-specific. Unused fields stay at defaults.

# DOCK_TARGET_REFINE | DOCK_ABORT | SLOT_STATE | LOAD_ID | ANOMALY | SPEED_REDUCE
string kind

# 0..1
float32 confidence

# Evidence (R2: sensor_name is always "pallet_cam")
string frame_id
float64 sim_stamp
string sensor_name

# Expiry; never re-applied after ttl_ms from sim_stamp
uint32 ttl_ms

# Required for SPEED_REDUCE (R5: one leg). Empty otherwise.
string leg_id

# DOCK_TARGET_REFINE
float64 dx
float64 dy
float64 dtheta

# DOCK_ABORT — reason code from the C2 set. Never "proceed".
string reason_code

# SLOT_STATE
SlotState[] slots

# LOAD_ID
string load_id
string load_type

# ANOMALY
string anomaly_class

# SPEED_REDUCE — ceiling in m/s, must be > 0 (R5: zero is a stop)
float64 ceiling_mps
