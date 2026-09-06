# m8_msgs/Verdict.msg
# Gate output: every proposal produces one. Phase A: accepted is always false.

bool accepted
string reason
string kind
string frame_id
float64 now_s
string checks_json
