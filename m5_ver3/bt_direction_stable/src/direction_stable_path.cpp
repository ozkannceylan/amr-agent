// direction_stable_path.cpp - the DirectionStablePath BT decorator.
// AMR-DEC-004. Built by tools/install_bt_direction.sh into the user's
// own $HOME; loaded by bt_navigator through nav2.yaml's
// `plugin_lib_names`; placed in the tree by
// behavior_trees/navigate_to_pose_tricycle_v3.xml.
//
// WHAT IT REFUSES. Smac replans at 1 Hz from the moving pose. At the
// adverse entry the fresh plan's FIRST-SEGMENT DRIVING DIRECTION flips -
// 13-15 times per run, measured - and MPPI's candidate cloud is anchored
// on the last command, so it cannot span the flip: every candidate
// points the wrong way, PathAlignCritic switches itself off
// (furthest_reached_path_point 0 < 12), the remaining critics balance at
// a 0.081 m/s wrong-direction creep, the footprint reaches lethal cost
// and Smac then answers START_OCCUPIED 205 with no retry left in the
// tree.
//
// IT HAS TWO MODES AND `hold_all` IS THE WHOLE DIFFERENCE, G5 TASK 6.
//   hold_all = false, DIRECTION-ONLY: refuse a fresh plan only when it
//     reverses the driving direction of the segment the truck is
//     standing on. This is what G5 Task 5 shipped and measured.
//   hold_all = true, COMMIT: refuse EVERY replacement while the truck is
//     moving, and take the next plan at the moments driving one makes
//     cheap - a cusp, a stop, a plan run out, or the expiry below.
// WHY A SECOND MODE EXISTS, AND IT IS A MEASUREMENT. Direction-only
// cleared the normal entry (29.5 s, one harmless hold) and did NOT clear
// the adverse one: 20 flips were held as designed, and about 92
// SAME-direction fresh plans were accepted underneath them. Their shape
// chatter - same sign, different geometry, every second - walked the
// truck 3.0 m off and put its footprint on lethal cost, which is the
// same 205 by a different road. Refusing the swap is not enough if the
// shape is free to change; commit mode is that hypothesis, and the
// campaign in EVIDENCE_STALL.md is what decides between them.
//
// AND THE CAMPAIGN SAID NEITHER. 24 trials, 2026-09-01, seed verified
// every one. Adverse entry: direction-only 2/8 arrivals, commit 0/8.
// Normal entry: direction-only 4/4 at 31 s, commit 2/4 - a regression.
// EVERY trial of BOTH arms carried a creep plateau, and the two arms'
// plateaus are the same number: 0.081-0.087 m/s against 0.080-0.084 m/s.
// Commit mode refused 92 % of the replans - 66 of 72 on one run, 61 of
// them SAME-DIRECTION, which is precisely the chatter the paragraph
// above blames - and the creep did not change. A cause you can delete
// without changing the effect is not the cause: THE CREEP IS NOT MADE BY
// PLAN REPLACEMENT, and no setting of hold_all fixes it. What this node
// does do is measured and it is narrow - it holds a direction swap, it
// says so, and it bounds itself - and the failure it was built for is an
// open architecture question for the owner, not a knob on this file.
//
// AND IT COMPARES AGAINST THE SEGMENT THE TRUCK IS ON. The accepted
// plan is read where the truck now stands on it, not where it set off:
// a plan with a cusp in it changes direction on its own, legitimately,
// and a decorator that refused that would refuse the terminal manoeuvre
// of a plan it had already agreed to. Measured, see
// current_segment_direction() below.
//
// THE REPLAN IS KEPT. Removing it (the F1 pilot) removed the flips, the
// creep and the 205 - and lost terminal overrun correction with it: four
// overshoot failures and a transformed plan frozen 0.66 m behind the
// truck. So the 1 Hz replan stays. Commit mode is deliberately NOT F1
// for exactly that reason: `hold_max_s` bounds every hold streak, so the
// planner still gets the truck back on a fresh plan on a fixed cadence.
//
// EVERY HOLD IS BOUNDED, AND THE BOUNDS ARE THE POINT.
//   hold_speed      below it the truck is not driving and a fresh plan
//                   costs nothing. A MEASURED threshold: every creep
//                   plateau this failure produced sits in 0.078-0.093
//                   m/s; a cusp and a stop pass through zero.
//   consume_floor_m an accepted plan with less than this left of it is
//                   a stub with no future in it and is never held.
//   hold_max_s      an unbroken streak of holds older than this takes
//                   the fresh plan anyway and says "hold expired".
//   stale odometry  if the estimator stops speaking, `speed_` freezes at
//                   the last number it published - which, above
//                   hold_speed, would latch the hold for ever. Aged and
//                   failed OPEN by name.
// config.yaml (nav.direction_hold.*) owns all four numbers, the tree's
// attributes repeat them because a BT port takes a literal, and
// tests/test_bt_direction.py pins every copy equal.
//
// IT HOLDS A PLAN; IT NEVER INVENTS ONE. The only path this node can
// write to the blackboard is a path the planner itself produced and this
// node already accepted. Child FAILURE and child RUNNING are passed
// through untouched, so no recovery this tree has is affected.
//
// IT IS NOT A SAFETY FUNCTION. Protective stop, e-stop and safe torque
// off are onboard and hardwired in the plant this models.
#include <cmath>
#include <limits>
#include <memory>
#include <string>

#include "behaviortree_cpp/bt_factory.h"
#include "behaviortree_cpp/decorator_node.h"
#include "geometry_msgs/msg/point.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "nav_msgs/msg/path.hpp"
#include "rclcpp/rclcpp.hpp"

namespace m5v3_bt
{

// HOW OLD THE LAST ODOMETRY READING MAY BE BEFORE THIS NODE STOPS
// BELIEVING IT, in seconds. It is NOT in config.yaml and that is
// deliberate: it is not a tuning knob, it is the difference between a
// live estimator and a dead one. The fused estimator on this arm
// publishes at config.yaml's ekf.frequency_hz = 50 Hz, so one second is
// FIFTY missed messages - nothing a loaded rig produces, and everything
// a stopped node does.
static constexpr double kOdomStaleS = 1.0;

class DirectionStablePath : public BT::DecoratorNode
{
public:
  DirectionStablePath(const std::string & name, const BT::NodeConfig & conf)
  : BT::DecoratorNode(name, conf) {}

  static BT::PortsList providedPorts()
  {
    return {
      BT::BidirectionalPort<nav_msgs::msg::Path>(
        "path", "the plan the child computed; written back when one is held"),
      BT::InputPort<std::string>(
        "odom_topic", "the FUSED estimator's address - config.yaml topics"),
      BT::InputPort<double>(
        "hold_speed", "m/s above which a fresh plan can be refused at all"),
      BT::InputPort<bool>(
        "hold_all",
        "false: refuse only a direction swap. true: commit to the accepted plan"),
      BT::InputPort<double>(
        "hold_max_s",
        "seconds after which an unbroken hold streak accepts the fresh plan anyway"),
      BT::InputPort<double>(
        "consume_floor_m",
        "metres of accepted plan left below which it is never held"),
    };
  }

  // A NEW NavigateToPose MUST NEVER INHERIT A HELD PATH. haltAllActions()
  // reaches this node at the end of every action and whenever the
  // top-level RecoveryNode retries, and both are exactly when the held
  // state stops describing anything. The STREAK CLOCK goes with it: a
  // new goal that inherited a streak which had already run would take
  // its first fresh plan on an expiry that describes the previous one.
  void halt() override
  {
    have_prev_ = false;
    streak_ = false;
    prev_ = nav_msgs::msg::Path();
    BT::DecoratorNode::halt();
  }

private:
  // The observer's convention (G5-T3): the sign of the segment leaving
  // pose `i`, projected on that pose's own heading. 0 means "no
  // direction here" - the index is the last pose, or the segment has no
  // length - and a 0 on either side skips the test.
  static int segment_direction(const nav_msgs::msg::Path & path, size_t i)
  {
    if (i + 1 >= path.poses.size()) {
      return 0;
    }
    const auto & q = path.poses[i].pose.orientation;
    const double yaw = std::atan2(
      2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z));
    const double dx = path.poses[i + 1].pose.position.x - path.poses[i].pose.position.x;
    const double dy = path.poses[i + 1].pose.position.y - path.poses[i].pose.position.y;
    if (std::hypot(dx, dy) < 1.0e-9) {
      return 0;
    }
    return (dx * std::cos(yaw) + dy * std::sin(yaw)) >= 0.0 ? 1 : -1;
  }

  // WHERE THE TRUCK STANDS ON A PLAN, and everything this node asks
  // about the accepted plan is asked from here rather than from its
  // start. One scan, two readers: the direction below and the remaining
  // length after it.
  static size_t nearest_index(
    const nav_msgs::msg::Path & path, const geometry_msgs::msg::Point & robot)
  {
    size_t nearest = 0;
    double best = std::numeric_limits<double>::infinity();
    for (size_t i = 0; i < path.poses.size(); ++i) {
      const auto & p = path.poses[i].pose.position;
      const double d = std::hypot(p.x - robot.x, p.y - robot.y);
      if (d < best) {
        best = d;
        nearest = i;
      }
    }
    return nearest;
  }

  // THE HELD PLAN IS COMPARED AT THE SEGMENT THE TRUCK IS ON AND NOT AT
  // THE ONE IT SET OFF ON, and that distinction is the whole difference
  // between refusing a flip and refusing a CUSP the accepted plan itself
  // contains. Measured 2026-09-01: reading the held plan's FIRST segment
  // made this node hold through the terminal cusp of a plan it had
  // already agreed to - four consecutive holds at 0.25-0.30 m/s - and
  // turned two arrivals into two START_OCCUPIED aborts.
  //   THE ROBOT'S POSITION IS THE FRESH PLAN'S FIRST POSE. Smac plans
  //   FROM the current pose, so that pose is where the truck is, already
  //   in the frame both paths are written in. No tf, no second opinion,
  //   and nothing to be stale.
  static int current_segment_direction(
    const nav_msgs::msg::Path & path, const geometry_msgs::msg::Point & robot)
  {
    if (path.poses.size() < 2) {
      return 0;
    }
    // nearest == last pose is a plan the truck has CONSUMED; there is no
    // segment left to compare and segment_direction() answers 0 for it.
    const size_t nearest = nearest_index(path, robot);
    return segment_direction(path, nearest);
  }

  // HOW MUCH OF THE ACCEPTED PLAN IS STILL IN FRONT OF THE TRUCK, in
  // metres along it, measured from the segment the truck stands on -
  // current_segment_direction()'s reading, and for its reason. A plan
  // the truck has all but finished has no future in it, and holding one
  // would steer the last centimetres of an approach by a stub.
  static double remaining_length(
    const nav_msgs::msg::Path & path, const geometry_msgs::msg::Point & robot)
  {
    if (path.poses.size() < 2) {
      return 0.0;
    }
    double total = 0.0;
    for (size_t i = nearest_index(path, robot); i + 1 < path.poses.size(); ++i) {
      const auto & a = path.poses[i].pose.position;
      const auto & b = path.poses[i + 1].pose.position;
      total += std::hypot(b.x - a.x, b.y - a.y);
    }
    return total;
  }

  // THE HELD PATH BELONGS TO A GOAL. Smac ends every plan on the goal
  // pose itself, so the last pose IS the goal identity; a preempted goal
  // therefore releases the hold instead of steering to the old one.
  static bool same_goal(const nav_msgs::msg::Path & a, const nav_msgs::msg::Path & b)
  {
    if (a.poses.empty() || b.poses.empty()) {
      return false;
    }
    const auto & pa = a.poses.back().pose.position;
    const auto & pb = b.poses.back().pose.position;
    return std::hypot(pa.x - pb.x, pa.y - pb.y) < 1.0e-3;
  }

  // ONE PLACE TAKES A FRESH PLAN, and it is the same place that ENDS the
  // hold streak. Written as a function rather than three lines repeated
  // seven times so that an expiry clock cannot survive the acceptance it
  // caused - which would be a node that expires every tick after the
  // first ten seconds.
  BT::NodeStatus accept(const nav_msgs::msg::Path & fresh)
  {
    prev_ = fresh;
    have_prev_ = true;
    streak_ = false;
    return BT::NodeStatus::SUCCESS;
  }

  void initialize()
  {
    node_ = config().blackboard->get<rclcpp::Node::SharedPtr>("node");
    getInput("odom_topic", odom_topic_);
    getInput("hold_speed", hold_speed_);
    getInput("hold_all", hold_all_);
    getInput("hold_max_s", hold_max_s_);
    getInput("consume_floor_m", consume_floor_m_);
    // BOTH CLOCKS ARE READ FROM THE NODE ONCE, HERE. rclcpp::Time
    // refuses to subtract two stamps taken from different time sources,
    // and a default-constructed Time is RCL_SYSTEM_TIME while
    // node_->now() on this stack is RCL_ROS_TIME.
    odom_seen_ = node_->now();
    holding_since_ = node_->now();
    // A callback group this node spins by hand, which is how every
    // subscribing nav2 BT node reaches a topic: the tree is ticked from
    // a thread that is not spinning bt_navigator's executor.
    callback_group_ = node_->create_callback_group(
      rclcpp::CallbackGroupType::MutuallyExclusive, false);
    executor_.add_callback_group(callback_group_, node_->get_node_base_interface());
    rclcpp::SubscriptionOptions options;
    options.callback_group = callback_group_;
    odom_sub_ = node_->create_subscription<nav_msgs::msg::Odometry>(
      odom_topic_, rclcpp::SystemDefaultsQoS(),
      [this](nav_msgs::msg::Odometry::SharedPtr msg) {
        speed_ = std::hypot(msg->twist.twist.linear.x, msg->twist.twist.linear.y);
        // WHEN IT ARRIVED, ON THIS NODE'S OWN CLOCK and not from the
        // message header: the question is "has the estimator spoken
        // lately", and a stalled publisher republishing an old stamp and
        // a stalled publisher saying nothing are the same failure.
        odom_seen_ = node_->now();
        have_odom_ = true;
      },
      options);
    // WHICH ARM THIS PROCESS IS ACTUALLY RUNNING, once, in the log. The
    // mode is an XML attribute, so a file on disk can say one thing and
    // a running bt_navigator another - an operator, and a campaign,
    // needs the process's own answer.
    RCLCPP_INFO(
      node_->get_logger(),
      "direction hold: mode %s | hold_speed %.3f m/s | hold_max_s %.1f s | "
      "consume_floor %.3f m | odom %s (stale above %.1f s)",
      hold_all_ ? "COMMIT (hold_all=true)" : "DIRECTION-ONLY (hold_all=false)",
      hold_speed_, hold_max_s_, consume_floor_m_, odom_topic_.c_str(),
      kOdomStaleS);
  }

  // THE LADDER. Seven named reasons to TAKE the fresh plan, and one hold
  // left over when none of them applies. It is written as a ladder and
  // not as one boolean because every rung is a thing an operator reads
  // in a log and asks about by name.
  BT::NodeStatus tick() override
  {
    if (!node_) {
      initialize();
    }
    setStatus(BT::NodeStatus::RUNNING);
    const BT::NodeStatus child_state = child_node_->executeTick();
    if (child_state != BT::NodeStatus::SUCCESS) {
      return child_state;
    }

    nav_msgs::msg::Path fresh;
    if (!getInput("path", fresh)) {
      return BT::NodeStatus::SUCCESS;
    }
    executor_.spin_some();

    // 1. FAIL OPEN. No odometry yet is no evidence that the truck is
    // moving, and a decorator that held plans on no evidence would be a
    // navigator that cannot start.
    if (!have_odom_) {
      if (!warned_no_odom_) {
        warned_no_odom_ = true;
        RCLCPP_INFO(
          node_->get_logger(),
          "direction hold: nothing received on %s yet - every plan is accepted "
          "until the estimator speaks", odom_topic_.c_str());
      }
      return accept(fresh);
    }

    // 2. FAIL OPEN AGAIN, AND THIS IS THE HOLE A DEAD ESTIMATOR OPENS.
    // `speed_` is the last speed the estimator ever published. If it
    // stops publishing while that number is above hold_speed, then every
    // condition below stays true for ever and the truck drives a plan
    // nobody is allowed to replace - a latch created by the failure of a
    // node this one only observes. Age the reading instead.
    const rclcpp::Time now = node_->now();
    const double odom_age = (now - odom_seen_).seconds();
    if (odom_age > kOdomStaleS) {
      RCLCPP_WARN(
        node_->get_logger(),
        "direction hold: odom stale - nothing on %s for %.1f s (limit %.1f s) - "
        "accepting the fresh plan", odom_topic_.c_str(), odom_age, kOdomStaleS);
      return accept(fresh);
    }

    // 3. NOTHING ACCEPTED YET, OR A GOAL NOBODY ASKED FOR ANY MORE.
    // same_goal() answers false on an empty path either side, which is
    // also what makes fresh.poses[0] below safe to read.
    if (fresh.poses.empty() || !have_prev_ || !same_goal(prev_, fresh)) {
      return accept(fresh);
    }
    const geometry_msgs::msg::Point & robot = fresh.poses[0].pose.position;

    // 4. SLOW, WHICH IS A CUSP, A STOP OR THE TERMINAL MANOEUVRE. In
    // commit mode this is the only rung that lets a fresh plan in while
    // the accepted one is still long, and that is by design: a
    // Reeds-Shepp cusp passes through zero speed by construction, so the
    // vehicle's own pauses are where the planner gets its turn.
    if (speed_ <= hold_speed_) {
      return accept(fresh);
    }

    // 5. A PLAN THE TRUCK HAS FINISHED IS NOT A PLAN.
    const double left = remaining_length(prev_, robot);
    if (left < consume_floor_m_) {
      RCLCPP_INFO(
        node_->get_logger(),
        "direction hold: the accepted plan is consumed - %.2f m of it left "
        "(consume_floor %.2f m) - accepting the fresh plan",
        left, consume_floor_m_);
      return accept(fresh);
    }

    // 6. WHAT THIS MODE REFUSES, AND IT IS THE ONLY LINE THE ARM CHANGES.
    const int fresh_dir = segment_direction(fresh, 0);
    const int prev_dir = current_segment_direction(prev_, robot);
    const bool swap = (fresh_dir != 0 && prev_dir != 0 && fresh_dir != prev_dir);
    if (!hold_all_ && !swap) {
      return accept(fresh);
    }

    // 7. THE LATCH IS BOUNDED. A commit that ran the whole drive would BE
    // the F1 pilot - one plan, no correction, terminal overshoot - so an
    // unbroken streak older than hold_max_s takes the fresh plan and says
    // so by name, which is also how a campaign counts it.
    const double held = (now - holding_since_).seconds();
    if (streak_ && held > hold_max_s_) {
      RCLCPP_INFO(
        node_->get_logger(),
        "direction hold: hold expired - held for %.1f s (hold_max_s %.1f s) - "
        "accepting the fresh plan", held, hold_max_s_);
      return accept(fresh);
    }

    if (!streak_) {
      streak_ = true;
      holding_since_ = now;
    }
    setOutput("path", prev_);
    RCLCPP_INFO(
      node_->get_logger(),
      "direction hold: %s at |v| = %.3f m/s (hold_speed %.3f), %+d -> %+d, "
      "%.2f m of the accepted plan left, held %.1f s - keeping the accepted plan",
      swap ? "fresh plan flips the driving direction"
           : "committed to the accepted plan",
      speed_, hold_speed_, prev_dir, fresh_dir, left,
      (now - holding_since_).seconds());
    return BT::NodeStatus::SUCCESS;
  }

  rclcpp::Node::SharedPtr node_;
  rclcpp::CallbackGroup::SharedPtr callback_group_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;

  std::string odom_topic_;
  double hold_speed_ {0.0};
  bool hold_all_ {false};
  double hold_max_s_ {0.0};
  double consume_floor_m_ {0.0};
  double speed_ {0.0};
  rclcpp::Time odom_seen_;
  rclcpp::Time holding_since_;
  bool have_odom_ {false};
  bool warned_no_odom_ {false};
  bool have_prev_ {false};
  bool streak_ {false};
  nav_msgs::msg::Path prev_;
};

}  // namespace m5v3_bt

BT_REGISTER_NODES(factory)
{
  factory.registerNodeType<m5v3_bt::DirectionStablePath>("DirectionStablePath");
}
