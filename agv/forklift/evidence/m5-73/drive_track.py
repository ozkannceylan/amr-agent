#!/usr/bin/env python3
"""m5-73 drive-and-track: drive the forklift forward while sampling the
viz stream's world_pose against the simulator's own model pose.
Run inside WSL with ROS sourced, GZ_PARTITION=m573stack ROS_DOMAIN_ID=73."""
import json
import subprocess
import time

EV = "/tmp/m573/ev"


def sh(cmd, timeout=15):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=timeout).stdout


def model_pose():
    out = sh("gz model -m Forklift -p 2>/dev/null")
    lines = [l.strip() for l in out.splitlines()]
    for i, l in enumerate(lines):
        if l.startswith("- Pose"):
            xyz = lines[i + 1].strip("[] ").split()
            rpy = lines[i + 2].strip("[] ").split()
            return float(xyz[0]), float(xyz[1]), float(rpy[2])
    raise RuntimeError("no model pose:\n" + out)


def viz_front_pose():
    out = sh("timeout 5 gz topic -e -n 1 --json-output "
             "-t /forklift/gz/viz/safety_scanner_front")
    m = json.loads(out)
    wp = m["worldPose"]
    p = wp.get("position", {})
    o = wp.get("orientation", {})
    return (p.get("x", 0.0), p.get("y", 0.0),
            o.get("z", 0.0), o.get("w", 1.0))


def pub(topic, value, repeats=2):
    for _ in range(repeats):
        sh("ros2 topic pub --once {} std_msgs/msg/Float64 "
           "'{{data: {}}}' >/dev/null".format(topic, value), timeout=20)


def main():
    rows = []
    pub("/forklift/cmd/steer_angle", 0.0)
    pub("/forklift/cmd/traction_speed", 0.5)
    t0 = time.time()
    for _ in range(14):
        mx, my, myaw = model_pose()
        vx, vy, qz, qw = viz_front_pose()
        rows.append((time.time() - t0, mx, my, myaw, vx, vy, qz, qw))
        print("t=%6.2f model=(%.3f,%.3f yaw %.4f) viz_front=(%.3f,%.3f)"
              % (rows[-1][0], mx, my, myaw, vx, vy), flush=True)
    pub("/forklift/cmd/traction_speed", 0.0)
    time.sleep(2.0)
    mx, my, myaw = model_pose()
    print("final model pose: (%.3f, %.3f, yaw %.4f)" % (mx, my, myaw))
    with open(EV + "/drive-track.csv", "w") as f:
        f.write("t_s,model_x,model_y,model_yaw,viz_front_x,viz_front_y,"
                "viz_front_qz,viz_front_qw\n")
        for r in rows:
            f.write(",".join("%.6f" % v for v in r) + "\n")
    print("wrote", EV + "/drive-track.csv")


if __name__ == "__main__":
    main()
