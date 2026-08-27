"""collision_monitor.yaml, checked against the numbers it is derived from.

F4 TASK 3, AND IT IS tests/test_nav2_params.py's ARGUMENT ONE FILE OVER.
Every vertex in `collision_monitor.yaml` is a body edge plus a measured
stopping distance, and both live in `config.yaml monitor:`. A polygon
edited in one and not the other is two opinions about one zone, and on
this arm that zone is what decides whether the truck stops - so it is a
test failure here rather than a discovery in a log.

WHAT THIS FILE DOES NOT TEST. That the monitor is safe. It is not: nav2's
own words for the node are that it "does not provide hard real-time
safety certifications", it does not replace a safety-rated PLC, and no
assertion below is a safety argument. What is tested is that the file
says what the derivation says.
"""
import ast
import math
import os
import sys

import pytest
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if os.path.join(_ROOT, "m5_ver3", "tools") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "m5_ver3", "tools"))


def read(name):
    with open(os.path.join(_ROOT, "m5_ver3", name),
              encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load(read("config.yaml"))


@pytest.fixture(scope="module")
def mon(cfg):
    path = cfg["monitor"]["params_file"].split("/", 1)[1]
    return yaml.safe_load(read(path))["collision_monitor"]["ros__parameters"]


@pytest.fixture(scope="module")
def geom(cfg):
    m = cfg["monitor"]
    return {
        "fork_tip": float(m["geometry"]["fork_tip_x_m"]),
        "counterweight": float(m["geometry"]["counterweight_x_m"]),
        "half_width": (float(m["geometry"]["half_width_m"])
                       + float(m["geometry"]["lateral_margin_m"])),
    }


def points(text):
    """collision_monitor.yaml writes its polygons as a STRING, so does nav2."""
    return [tuple(p) for p in ast.literal_eval(text)]


def rectangle(near_x, depth, half_width, forward):
    far = near_x - depth if forward else near_x + depth
    return [(near_x, half_width), (far, half_width),
            (far, -half_width), (near_x, -half_width)]


# ---------------------------------------------------------------- shape

def test_the_file_is_addressed_to_the_node_m5v3_starts(cfg):
    # m5v3.sh's check_monitor_params() makes this claim with a grep
    # before anything starts; this is the same claim about the file on
    # disk. rclcpp applies NOTHING from a block addressed to a node that
    # is not running and says nothing about it.
    path = cfg["monitor"]["params_file"].split("/", 1)[1]
    tree = yaml.safe_load(read(path))
    assert cfg["monitor"]["node_name"] in tree
    assert "ros__parameters" in tree[cfg["monitor"]["node_name"]]


def test_both_polygon_sets_are_declared_and_defined(mon):
    assert set(mon["polygons"]) == {"MonitorStop", "MonitorSlowdown"}
    for name in mon["polygons"]:
        assert name in mon, name
        assert mon[name]["type"] == "velocity_polygon"


def test_the_two_sets_carry_the_two_actions(mon):
    assert mon["MonitorStop"]["action_type"] == "stop"
    assert mon["MonitorSlowdown"]["action_type"] == "slowdown"


def test_every_sub_polygon_named_in_the_list_exists(mon):
    # A velocity_polygons entry naming a block that is not there is a
    # nav2 warning and a node that comes up anyway - with a zone missing
    # and nothing downstream saying so.
    for name in ("MonitorStop", "MonitorSlowdown"):
        for sub in mon[name]["velocity_polygons"]:
            assert sub in mon[name], "{}.{}".format(name, sub)
            assert "points" in mon[name][sub]


# ----------------------------------------------------------- the shapes

@pytest.mark.parametrize("polygon,sub,depth_key,forward", [
    ("MonitorStop", "forks_transit", ("stop_m", "transit"), True),
    ("MonitorStop", "forks_cruise", ("stop_m", "cruise"), True),
    ("MonitorStop", "cw_transit", ("stop_m", "transit"), False),
    ("MonitorStop", "cw_cruise", ("stop_m", "cruise"), False),
    ("MonitorSlowdown", "forks_transit", ("slowdown_m", "transit"), True),
    ("MonitorSlowdown", "forks_cruise", ("slowdown_m", "cruise"), True),
    ("MonitorSlowdown", "cw_transit", ("slowdown_m", "transit"), False),
    ("MonitorSlowdown", "cw_cruise", ("slowdown_m", "cruise"), False),
])
def test_every_zone_is_its_derivation_recomputed(cfg, mon, geom, polygon,
                                                 sub, depth_key, forward):
    depth = float(cfg["monitor"][depth_key[0]][depth_key[1]])
    near = geom["fork_tip"] if forward else geom["counterweight"]
    want = rectangle(near, depth, geom["half_width"], forward)
    got = points(mon[polygon][sub]["points"])
    assert len(got) == len(want)
    for a, b in zip(got, want):
        assert a[0] == pytest.approx(b[0], abs=1e-9), sub
        assert a[1] == pytest.approx(b[1], abs=1e-9), sub


def test_the_fallback_is_the_FRONT_TRANSIT_zone_and_not_a_ring(mon, geom,
                                                              cfg):
    # nav2's own example wraps the robot at this rung. Here that polygon
    # would contain nav_lidar_3d's housing and both mast rails - 50 of
    # 811 rays, EVIDENCE_NAV_V3.md 14.4 - and would fire for ever. A
    # stopped vehicle has no direction of travel to guard and the honest
    # form of that is to guard the one it had.
    for polygon, key in (("MonitorStop", "stop_m"),
                         ("MonitorSlowdown", "slowdown_m")):
        depth = float(cfg["monitor"][key]["transit"])
        want = rectangle(geom["fork_tip"], depth, geom["half_width"], True)
        got = points(mon[polygon]["stopped"]["points"])
        assert len(got) == len(want), polygon
        for a, b in zip(got, want):
            assert a[0] == pytest.approx(b[0], abs=1e-9), polygon
            assert a[1] == pytest.approx(b[1], abs=1e-9), polygon


def test_NO_zone_contains_any_part_of_the_truck_the_scanner_can_see():
    # THE ONE ASSERTION THIS WHOLE DESIGN TURNS ON. The nav scanner
    # returns off three pieces of this vehicle (EVIDENCE_NAV_V3.md 14.4,
    # measured off one scan at the spawn) and this node has no
    # footprint-clearing mechanism at all. A zone containing any of them
    # is a monitor that stops the truck on itself, for ever, on every
    # cycle.
    seen = [(0.026, -0.019),      # nav_lidar_3d's housing, at base_link
            (-0.747, 0.285),      # mast_rail_left
            (-0.746, -0.302)]     # mast_rail_right
    cfg_ = yaml.safe_load(read("config.yaml"))
    path = cfg_["monitor"]["params_file"].split("/", 1)[1]
    mon_ = yaml.safe_load(read(path))["collision_monitor"]["ros__parameters"]
    for polygon in mon_["polygons"]:
        for sub in mon_[polygon]["velocity_polygons"]:
            poly = points(mon_[polygon][sub]["points"])
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            for x, y in seen:
                inside = (min(xs) <= x <= max(xs)
                          and min(ys) <= y <= max(ys))
                assert not inside, (
                    "{}.{} contains the self-return at ({}, {})".format(
                        polygon, sub, x, y))


def test_every_zone_starts_at_a_body_edge_and_points_OUTWARD(mon, geom):
    for polygon in ("MonitorStop", "MonitorSlowdown"):
        for sub in mon[polygon]["velocity_polygons"]:
            xs = [p[0] for p in points(mon[polygon][sub]["points"])]
            near = geom["fork_tip"] if "forks" in sub or sub == "stopped" \
                else geom["counterweight"]
            if near == geom["fork_tip"]:
                assert max(xs) == pytest.approx(near), sub
            else:
                assert min(xs) == pytest.approx(near), sub


def test_the_slowdown_zone_contains_the_stop_zone(cfg):
    # A slowdown that fired INSIDE the stop zone would never be seen: the
    # more restrictive action wins on the same cycle.
    m = cfg["monitor"]
    for band in ("transit", "cruise"):
        assert float(m["slowdown_m"][band]) > float(m["stop_m"][band]), band


# ------------------------------------------------------ the derivations

def test_the_stop_depths_clear_the_MEASURED_stopping_distances(cfg):
    # EVIDENCE_NAV_V3.md 8, and it is the measurement and not v^2/2a:
    # 1.019 m and 1.041 m from 0.700 m/s against the ramp's own 0.690 m
    # prediction, 0.208 m from 0.300 m/s. The zone has to be at least
    # the distance, or it is a zone the vehicle cannot stop inside.
    measured = {"transit": 0.208, "cruise": 1.041}
    for band, distance in measured.items():
        assert float(cfg["monitor"]["stop_m"][band]) >= distance, band


def test_the_cruise_slowdown_covers_the_run_down_to_the_transit_ceiling(cfg):
    # 1.05 (the stop zone) + 0.25 s of dead time at 0.700 m/s
    # + (0.700^2 - 0.300^2) / (2 x 0.35). The whole point of the
    # slowdown zone is that a vehicle warned at its edge is at the
    # transit ceiling by the time it reaches the stop zone.
    m = cfg["monitor"]
    stop = float(m["stop_m"]["cruise"])
    cruise = float(m["speeds"]["cruise_mps"])
    transit = float(m["speeds"]["transit_mps"])
    dead_time_s = 0.25
    accel = 0.35
    want = (stop + dead_time_s * cruise
            + (cruise ** 2 - transit ** 2) / (2.0 * accel))
    assert float(m["slowdown_m"]["cruise"]) >= want - 1e-9
    assert float(m["slowdown_m"]["cruise"]) < want + 0.05


def test_the_slowdown_ratio_IS_transit_over_cruise(cfg):
    m = cfg["monitor"]
    want = float(m["speeds"]["transit_mps"]) / float(m["speeds"]["cruise_mps"])
    assert float(m["slowdown_ratio"]) == pytest.approx(want, abs=1e-6)


def test_the_slowdown_ratio_in_the_yaml_is_the_one_in_config(cfg, mon):
    assert float(mon["MonitorSlowdown"]["slowdown_ratio"]) == pytest.approx(
        float(cfg["monitor"]["slowdown_ratio"]), abs=1e-9)


def test_the_transit_band_INCLUDES_nav2s_own_transit_ceiling(cfg, mon):
    # THE ONE OFF-BY-ONE THAT WOULD MATTER. nav2.yaml's vx_max is the
    # speed every driven goal on this track runs at; if the transit band
    # stopped short of it, every nav2-driven approach would be guarded
    # by the CRUISE zone - 1.05 m instead of 0.25 m - and a 4.00 m
    # station bay would be unenterable.
    nav = yaml.safe_load(read("nav2.yaml"))
    vx_max = float(nav["controller_server"]["ros__parameters"]["FollowPath"]
                   ["vx_max"])
    assert vx_max == pytest.approx(
        float(cfg["monitor"]["speeds"]["transit_mps"]), abs=1e-9)
    for polygon in ("MonitorStop", "MonitorSlowdown"):
        band = mon[polygon]["forks_transit"]
        assert float(band["linear_min"]) <= -vx_max
        assert float(band["linear_max"]) >= 0.0


def test_the_SMALL_bands_are_listed_FIRST(mon):
    # VelocityPolygon takes the FIRST sub-polygon whose band contains the
    # command and the bands share their endpoints (-0.300 is in both
    # forks_transit and forks_cruise). Listed the other way round, every
    # nav2-driven approach - which runs at exactly -0.300 - would get the
    # cruise rectangle.
    for polygon in ("MonitorStop", "MonitorSlowdown"):
        order = mon[polygon]["velocity_polygons"]
        assert order.index("forks_transit") < order.index("forks_cruise")
        assert order.index("cw_transit") < order.index("cw_cruise")
        assert order[-1] == "stopped", polygon


def test_the_bands_tile_everything_the_command_path_can_carry(mon):
    # A command outside every band falls to `stopped`, which nav2 asks to
    # cover the whole range - so the fallback is checked rather than
    # assumed.
    for polygon in ("MonitorStop", "MonitorSlowdown"):
        low = min(float(mon[polygon][s]["linear_min"])
                  for s in mon[polygon]["velocity_polygons"])
        high = max(float(mon[polygon][s]["linear_max"])
                   for s in mon[polygon]["velocity_polygons"])
        assert float(mon[polygon]["stopped"]["linear_min"]) <= low
        assert float(mon[polygon]["stopped"]["linear_max"]) >= high


def test_the_lateral_margin_is_the_SCANNER_and_not_the_localiser(cfg):
    # The costmaps in nav2.yaml grow the footprint by +0.54 m along and
    # +0.11 m across, and that growth is F3's LOCALISATION error. This
    # node has no map, no localiser and no pose - it tests points in
    # base_link - so a localisation margin here would be an error budget
    # applied in a frame where it does not exist. What IS added is 3
    # sigma of the nav lidar's own 0.02 m per-ray range noise.
    margin = float(cfg["monitor"]["geometry"]["lateral_margin_m"])
    assert margin == pytest.approx(0.061, abs=1e-9)
    assert margin >= 3.0 * 0.02
    assert margin < 0.11        # strictly under the costmap's cross margin


def test_the_body_edges_are_the_MODEL_hull_and_not_the_grown_polygon(cfg):
    # evidence_core.sdf_footprint over gazebo/forklift_ver3/model.sdf,
    # which is what EVIDENCE_NAV_V3.md 14.3 tabulates: x in
    # [-1.8750, +0.8600], y +-0.5590. The grown polygon in nav2.yaml
    # reaches -2.415 and +-0.669 and is a different claim.
    import evidence_core as core
    hull = core.sdf_footprint(os.path.join(
        _ROOT, "m5_ver3", "gazebo", "forklift_ver3", "model.sdf"))
    xs = [p[0] for p in hull]
    ys = [abs(p[1]) for p in hull]
    g = cfg["monitor"]["geometry"]
    assert float(g["fork_tip_x_m"]) == pytest.approx(min(xs), abs=1e-6)
    assert float(g["counterweight_x_m"]) == pytest.approx(max(xs), abs=1e-6)
    assert float(g["half_width_m"]) == pytest.approx(max(ys), abs=1e-3)


# --------------------------------------------------- the stack it is in

def test_the_monitor_is_wired_between_the_smoother_and_the_converter():
    # THE INSERTION IS A REMAP AND THE REMAP IS WHAT THIS CHECKS. m5v3.sh
    # spawns the monitor with cmd_vel_in = topics.cmd_vel_smoothed and
    # cmd_vel_out = topics.cmd_vel_monitored, and then spawns the
    # converter with its own subscription remapped onto the second. Get
    # either half wrong and the command path is cut.
    script = read("m5v3.sh")
    assert "-p cmd_vel_in_topic:=\"$CFG_TOPICS_CMD_VEL_SMOOTHED\"" in script
    assert "-p cmd_vel_out_topic:=\"$CFG_TOPICS_CMD_VEL_MONITORED\"" in script
    assert 'navcmd_in="$CFG_TOPICS_CMD_VEL_MONITORED"' in script
    assert ('-r "$CFG_TOPICS_CMD_VEL_SMOOTHED":="$navcmd_in"' in script)


def test_the_monitor_arm_starts_the_scanner_transform_it_cannot_work_without():
    # MEASURED 2026-08-27 and it cost a whole demonstration run: with no
    # base_link -> nav_lidar_link transform the node cannot place a scan
    # point and publishes NOTHING on its cmd_vel_out - which on this arm
    # is a CUT COMMAND PATH with every child ALIVE.
    script = read("m5v3.sh")
    assert ('if [ "$RF2O" = true ] || [ "$LOCALIZE" = true ] \\\n'
            '       || [ "$MONITOR" = true ]; then') in script


def test_the_disclaimer_is_verbatim_everywhere_it_appears():
    # F4 constraint 18 asks for it verbatim in the design prose. It is a
    # QUOTATION and a paraphrase is not one, so the exact string is
    # required in every file that makes the claim.
    words = "does not provide hard real-time safety certifications"
    for name in ("collision_monitor.yaml", "config.yaml", "m5v3.sh",
                 "tools/monitor_demo.py"):
        assert words in read(name), name


def test_the_scan_is_the_only_source_and_the_safety_scanners_are_NOT_in_it(
        mon):
    # The two safety scanners sit at z = 0.15 m in model.sdf and are not
    # bridged to ROS at all. Naming one here would be a claim that this
    # node watches the floor, which at z = 1.80 m it does not.
    assert mon["observation_sources"] == ["scan"]
    assert mon["scan"]["type"] == "scan"
    assert "safety" not in yaml.safe_dump(mon).lower()


def test_the_demo_obstacle_is_TALLER_than_the_scan_plane(cfg):
    # 1.80 m is where the nav lidar's plane is (model.sdf). A box shorter
    # than that is invisible to this node and the demonstration would
    # measure nothing at all while looking exactly like a run in which
    # the monitor never fired.
    assert float(cfg["monitor"]["obstacle"]["size_z_m"]) > 1.80


def test_the_demo_obstacle_stands_on_the_headline_route(cfg):
    # It has to be somewhere the truck drives at the commanded speed
    # with the forks leading: the north ring leg, y = +10.00, which is
    # the spawn's own leg and spine_north's route.
    box = cfg["monitor"]["obstacle"]
    assert float(box["y_m"]) == pytest.approx(float(cfg["vehicle"]["spawn"]["y"]))
    assert float(box["x_m"]) > float(cfg["vehicle"]["spawn"]["x"])
    # and far enough ahead that the vehicle is at speed before the
    # biggest zone reaches it
    tips = float(cfg["vehicle"]["spawn"]["x"]) + abs(
        float(cfg["monitor"]["geometry"]["fork_tip_x_m"]))
    face = float(box["x_m"]) - float(box["size_x_m"]) / 2.0
    assert face - tips > float(cfg["monitor"]["slowdown_m"]["cruise"]) + 2.0


def test_the_demo_drives_at_CRUISE_so_both_actions_are_observable(cfg):
    # At the transit ceiling the slowdown would take the command to
    # 0.129 m/s and the zones are 0.50/0.25 m; at cruise the slowdown
    # lands exactly on the transit ceiling and the zones are 1.80/1.05 m.
    m = cfg["monitor"]
    assert float(m["demo"]["speed_mps"]) == pytest.approx(
        float(m["speeds"]["cruise_mps"]))


def test_the_monitor_publishes_an_UNSTAMPED_twist_like_the_rest_of_the_chain(
        mon):
    # EVIDENCE_NAV_V3.md 6.1 fact 1 MEASURED this chain to be unstamped
    # end to end. A node inserted into it publishing TwistStamped would
    # be a publisher nothing subscribes to, on a topic that looks alive
    # from `ros2 topic list`.
    assert mon["enable_stamped_cmd_vel"] is False


def test_it_brings_itself_up_because_nothing_on_this_track_would(mon):
    # There is no nav2 lifecycle manager over this node. Left in
    # UNCONFIGURED it subscribes to nothing and publishes nothing, and on
    # this arm that is a cut command path rather than a missing guard.
    assert mon["autostart_node"] is True


def test_the_source_timeout_is_fifteen_scan_periods(cfg, mon):
    # The nav lidar is 15 Hz (config.yaml sensors.nav_lidar.rate_hz), and
    # 1.0 s is fifteen periods - localization.analyse.map_gap_s's own
    # argument, one sensor over.
    rate = float(cfg["sensors"]["nav_lidar"]["rate_hz"])
    assert float(mon["source_timeout"]) == pytest.approx(
        float(cfg["monitor"]["source_timeout_s"]))
    assert float(mon["source_timeout"]) * rate == pytest.approx(15.0, abs=0.5)


def test_min_points_is_above_noise_and_below_the_smallest_real_return(cfg,
                                                                     mon):
    # 811 rays over 270 deg is 0.0058178 rad apart. The demo box is
    # 0.60 m wide; at the far edge of the cruise slowdown zone (about
    # 3.7 m from base_link) it subtends 0.162 rad and about 28 rays.
    # Four is well under that and well over any single-ray excursion -
    # the range noise is 0.02 m and moves a ray ALONG its bearing.
    assert int(mon["MonitorStop"]["min_points"]) == int(
        cfg["monitor"]["min_points"])
    width = float(cfg["monitor"]["obstacle"]["size_y_m"])
    reach = (abs(float(cfg["monitor"]["geometry"]["fork_tip_x_m"]))
             + float(cfg["monitor"]["slowdown_m"]["cruise"]))
    rays = 2.0 * math.atan2(width / 2.0, reach) / 0.0058178
    assert 4 <= int(mon["MonitorStop"]["min_points"]) < rays / 4.0
