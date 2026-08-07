// scan_viz_repeater.cc - republish each gz LaserScan with a live world_pose,
// so the Gazebo GUI can draw the ray fan ON the vehicle instead of at the
// world origin.
//
// WHY THIS TOOL EXISTS, MEASURED 2026-08-07 (m5-73). On this stack
// (gz-sim 8.11.0 / gz-sensors 8.2.2) the `world_pose` field of every
// gz.msgs.LaserScan is NOT a world pose: it is the sensor's static SDF
// <pose> relative to its parent link, copied once at load and never
// composed with the vehicle's pose. Probe: a lidar whose SDF pose was
// (1.5, 2.5, 0.5, yaw 1.0) inside a model spawned at (4, -2, yaw 0.7)
// published world_pose (1.5, 2.5, 0.5, yaw 1.0) exactly, and kept
// publishing it byte-identical after the model was teleported. model.sdf
// deliberately writes each scanner's mount into the LINK pose and leaves
// the sensor pose identity (so the measurement frame and <gz_frame_id>
// agree), so all three scanners publish world_pose = identity, and the
// GUI's VisualizeLidar plugin - whose anchor is that field - draws every
// fan at the world origin. The m5-05 arena captures looked right only
// because that vehicle spawned AT the origin.
//
// WHAT IT DOES. Subscribes to /world/<world>/pose/info, composes the
// vehicle model's world pose with the named sensor link's model-relative
// pose (the sensor's own pose within its link is identity in model.sdf,
// which this tool relies on and does not re-add), and republishes each
// scan on a separate viz topic with ONLY world_pose replaced. Ranges,
// intensities, angles, frame and stamp are copied untouched.
//
// WHAT IT IS NOT. Visualization only. No node on the vehicle consumes the
// viz topics; the measurement channels are not written, renamed or
// re-timed - this tool only adds one more subscriber to each. It is not a
// safety function and not part of any measurement path: no Category, no
// Performance Level, no SIL, no PFH. If the pose stream is absent the
// tool publishes NOTHING on that channel (absence, not a wrong anchor)
// and says so on stderr.
//
// SINGLE-INSTANCE ASSUMPTION, STATED. Model and link entries in pose/info
// are matched BY NAME, which is unambiguous at one vehicle and is not at
// two (the same n=1 contract already recorded for the fixed gz topic
// names in PLANT-CHANGE-INVENTORY.md). A second vehicle needs per-model
// scoping of the viz topics and of this matching, in the same round that
// re-scopes the topic names themselves.
//
// Build: scripts/scan_viz_repeater.sh (g++ one-liner, no build system -
// this directory ships plain sources on purpose). Needs the sourced ROS
// Jazzy environment at run time for the gz vendor libraries, which every
// caller of vehicle.launch.py already has by construction.
//
// Usage:
//   scan_viz_repeater --model Forklift [--world warehouse] \
//     --chan <scan_topic>=<link_name>=<viz_topic>   (repeatable)

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <map>
#include <mutex>
#include <regex>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include <gz/transport.hh>
#include <gz/msgs/laserscan.pb.h>
#include <gz/msgs/pose_v.pb.h>

namespace {

// Minimal quaternion/pose algebra, kept local so the tool links against
// transport and msgs only.
struct Quat { double w{1}, x{0}, y{0}, z{0}; };
struct Vec3 { double x{0}, y{0}, z{0}; };
struct Pose { Vec3 p; Quat q; };

Quat qmul(const Quat &a, const Quat &b) {
  return Quat{
      a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
      a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
      a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
      a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w};
}

Vec3 qrot(const Quat &q, const Vec3 &v) {
  // v' = q * (0,v) * q^-1 for a unit quaternion.
  Quat p{0.0, v.x, v.y, v.z};
  Quat qi{q.w, -q.x, -q.y, -q.z};
  Quat r = qmul(qmul(q, p), qi);
  return Vec3{r.x, r.y, r.z};
}

// world_T_link = world_T_model * model_T_link
Pose compose(const Pose &a, const Pose &b) {
  Vec3 rp = qrot(a.q, b.p);
  return Pose{Vec3{a.p.x + rp.x, a.p.y + rp.y, a.p.z + rp.z}, qmul(a.q, b.q)};
}

struct Channel {
  std::string scan_topic;
  std::string link_name;
  std::string viz_topic;
  gz::transport::Node::Publisher pub;
  std::atomic<bool> announced{false};
  std::atomic<bool> waiting_logged{false};
};

struct Shared {
  std::mutex mtx;
  bool model_seen{false};
  Pose model_pose;                       // world_T_model
  std::map<std::string, Pose> link_pose; // model_T_link, by link name
  std::string model_name;
};

Shared g_shared;

void cb_pose_info(const gz::msgs::Pose_V &msg) {
  std::lock_guard<std::mutex> lock(g_shared.mtx);
  for (int i = 0; i < msg.pose_size(); ++i) {
    const auto &e = msg.pose(i);
    Pose p;
    p.p = Vec3{e.position().x(), e.position().y(), e.position().z()};
    p.q = Quat{e.orientation().w(), e.orientation().x(), e.orientation().y(),
               e.orientation().z()};
    if (e.name() == g_shared.model_name) {
      g_shared.model_pose = p;
      g_shared.model_seen = true;
    } else {
      g_shared.link_pose[e.name()] = p;
    }
  }
}

void cb_scan(const gz::msgs::LaserScan &msg, Channel &ch) {
  Pose world;
  {
    std::lock_guard<std::mutex> lock(g_shared.mtx);
    auto it = g_shared.link_pose.find(ch.link_name);
    if (!g_shared.model_seen || it == g_shared.link_pose.end()) {
      // No pose yet: publish nothing rather than a wrongly anchored fan.
      if (!ch.waiting_logged.exchange(true))
        std::fprintf(stderr,
                     "[scan_viz_repeater] %s: scan arriving but no pose for "
                     "model '%s' link '%s' yet - not publishing\n",
                     ch.scan_topic.c_str(), g_shared.model_name.c_str(),
                     ch.link_name.c_str());
      return;
    }
    world = compose(g_shared.model_pose, it->second);
  }
  gz::msgs::LaserScan out(msg); // everything copied; only world_pose replaced
  auto *wp = out.mutable_world_pose();
  wp->mutable_position()->set_x(world.p.x);
  wp->mutable_position()->set_y(world.p.y);
  wp->mutable_position()->set_z(world.p.z);
  wp->mutable_orientation()->set_w(world.q.w);
  wp->mutable_orientation()->set_x(world.q.x);
  wp->mutable_orientation()->set_y(world.q.y);
  wp->mutable_orientation()->set_z(world.q.z);
  ch.pub.Publish(out);
  if (!ch.announced.exchange(true))
    std::fprintf(stderr,
                 "[scan_viz_repeater] %s -> %s live, anchored to link '%s'\n",
                 ch.scan_topic.c_str(), ch.viz_topic.c_str(),
                 ch.link_name.c_str());
}

} // namespace

int main(int argc, char **argv) {
  std::string model, world;
  std::vector<std::unique_ptr<Channel>> channels;

  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto next = [&](const char *flag) -> std::string {
      if (i + 1 >= argc) {
        std::fprintf(stderr, "[scan_viz_repeater] %s needs a value\n", flag);
        std::exit(2);
      }
      return argv[++i];
    };
    if (a == "--model") {
      model = next("--model");
    } else if (a == "--world") {
      world = next("--world");
    } else if (a == "--chan") {
      std::string spec = next("--chan");
      auto p1 = spec.find('=');
      auto p2 = spec.find('=', p1 == std::string::npos ? p1 : p1 + 1);
      if (p1 == std::string::npos || p2 == std::string::npos) {
        std::fprintf(stderr,
                     "[scan_viz_repeater] --chan wants "
                     "<scan_topic>=<link_name>=<viz_topic>, got '%s'\n",
                     spec.c_str());
        return 2;
      }
      auto ch = std::make_unique<Channel>();
      ch->scan_topic = spec.substr(0, p1);
      ch->link_name = spec.substr(p1 + 1, p2 - p1 - 1);
      ch->viz_topic = spec.substr(p2 + 1);
      channels.push_back(std::move(ch));
    } else {
      std::fprintf(stderr, "[scan_viz_repeater] unknown argument '%s'\n",
                   a.c_str());
      return 2;
    }
  }
  if (model.empty() || channels.empty()) {
    std::fprintf(stderr,
                 "[scan_viz_repeater] usage: --model NAME [--world NAME] "
                 "--chan scan=link=viz [--chan ...]\n");
    return 2;
  }
  g_shared.model_name = model;

  gz::transport::Node node;

  // World discovery, when not named: poll the topic list for
  // /world/<name>/pose/info. One world proceeds; several is a refusal,
  // because guessing would anchor the fan in somebody else's world.
  if (world.empty()) {
    std::regex re("^/world/([^/]+)/pose/info$");
    for (int tries = 0; world.empty(); ++tries) {
      std::vector<std::string> topics;
      node.TopicList(topics);
      std::set<std::string> found;
      for (const auto &t : topics) {
        std::smatch m;
        if (std::regex_match(t, m, re))
          found.insert(m[1].str());
      }
      if (found.size() == 1) {
        world = *found.begin();
      } else if (found.size() > 1) {
        std::fprintf(stderr,
                     "[scan_viz_repeater] %zu worlds advertise pose/info - "
                     "pass --world explicitly\n",
                     found.size());
        return 3;
      } else {
        if (tries == 0)
          std::fprintf(stderr,
                       "[scan_viz_repeater] waiting for a "
                       "/world/*/pose/info topic...\n");
        if (tries >= 120) {
          std::fprintf(stderr,
                       "[scan_viz_repeater] no world after 120 s - giving "
                       "up loudly rather than idling silently\n");
          return 3;
        }
        std::this_thread::sleep_for(std::chrono::seconds(1));
      }
    }
    std::fprintf(stderr, "[scan_viz_repeater] discovered world '%s'\n",
                 world.c_str());
  }

  const std::string pose_topic = "/world/" + world + "/pose/info";
  if (!node.Subscribe(pose_topic, cb_pose_info)) {
    std::fprintf(stderr, "[scan_viz_repeater] cannot subscribe %s\n",
                 pose_topic.c_str());
    return 3;
  }

  for (auto &ch : channels) {
    ch->pub = node.Advertise<gz::msgs::LaserScan>(ch->viz_topic);
    if (!ch->pub) {
      std::fprintf(stderr, "[scan_viz_repeater] cannot advertise %s\n",
                   ch->viz_topic.c_str());
      return 3;
    }
    Channel *raw = ch.get();
    std::function<void(const gz::msgs::LaserScan &)> cb =
        [raw](const gz::msgs::LaserScan &m) { cb_scan(m, *raw); };
    if (!node.Subscribe<gz::msgs::LaserScan>(ch->scan_topic, cb)) {
      std::fprintf(stderr, "[scan_viz_repeater] cannot subscribe %s\n",
                   ch->scan_topic.c_str());
      return 3;
    }
  }

  gz::transport::waitForShutdown();
  return 0;
}
