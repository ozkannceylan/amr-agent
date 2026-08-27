"""nav2.yaml recomputed, and the behaviour tree read - F4 Task 2.

WHAT THIS FILE IS FOR, AND IT IS tests/test_smoother_params.py's
ARGUMENT ONE LAYER UP. `m5v3.sh`'s check_nav_params() runs before
anything is started and asks the questions a SHELL can ask: is the file
addressed to each of the six nodes, and do the three addresses it has to
repeat still agree with config.yaml. This file loads the YAML and asks
the questions that need a parser and some arithmetic:

  - is the FOOTPRINT still the model's? It is not typed in - it is the
    convex hull of every collision and visual primitive in
    gazebo/forklift_ver3/model.sdf, computed by
    evidence_core.sdf_footprint(), and a model whose forks moved would
    otherwise leave a polygon here describing a truck that no longer
    exists.
  - do the numbers that are DERIVED still follow from the ones they were
    derived from? `model_dt` is 1/controller_frequency, `wz_max` is
    vx_min/min_turning_r, `az_max` is ax_max/min_turning_r, the
    acceleration is config.yaml's own navcmd.accel_mps2 and the two
    speed limits are two rows of config.yaml's drive_route table.
  - does the arm that was written for a REVERSE-TRAVELLING vehicle still
    have every one of the four parameters section (D) names pointing the
    right way?
  - are the three GOALS still nodes of m6/ipc/route.py's road graph? The
    graph is read-only to this track and the poses are copied into
    config.yaml as values, so this is the copy saying when it has gone
    stale.
  - and does the behaviour tree still have no Spin and no BackUp in it?

NO ROS AND NO GAZEBO: three files off disk, one XML parse and some
arithmetic, on the Windows python the suite runs under.
"""
import math
import os
import re

import pytest

yaml = pytest.importorskip("yaml")

import evidence_core as core                          # noqa: E402

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
_REPO = os.path.normpath(os.path.join(_M5V3, os.pardir))

#: THE FLOOR THE PLANT ACTUALLY DELIVERS, in metres of REAR-AXLE radius,
#: measured on four corners at four headings and taken as the WORST of
#: them: EVIDENCE_NAV_V3.md 2.1, and F4 Task 1's handover. It is here as
#: a literal because it is a MEASUREMENT and lives in an evidence file
#: rather than in a config; what this file checks is that nav2.yaml's
#: radius still leaves room above it.
DELIVERED_MIN_REAR_RADIUS_M = 0.4154

#: THE ERROR BUDGET F3 HANDED OVER (EVIDENCE_LOCALIZATION_V3.md 6.1, 8
#: and 13.10), dry, on the shipping `amcl` arm. Same reason as above.
WORST_ABSOLUTE_ERROR_M = 0.5321
WORST_CROSS_TRACK_M = 0.1044
WORST_MAP_ODOM_STEP_M = 0.2591
WORST_END_ERROR_M = 0.1954

#: The pick aisle: the only 5.00 m corridor on this floor, rack faces at
#: y = +-2.50 (m6/gazebo/warehouse_ver3.sdf, and EVIDENCE_MAP_V3.md 2.1).
PICK_AISLE_HALF_WIDTH_M = 2.50

#: The station-class arrival tolerance this floor's twelve stations are
#: specified to (m6/ipc/stations.py).
STATION_TOLERANCE_M = 0.25


def read(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load(read("config.yaml"))


@pytest.fixture(scope="module")
def nav(cfg):
    return yaml.safe_load(read(cfg["nav"]["params_file"].split("/", 1)[1]))


@pytest.fixture(scope="module")
def planner(nav):
    return nav["planner_server"]["ros__parameters"]["GridBased"]


@pytest.fixture(scope="module")
def controller(nav):
    return nav["controller_server"]["ros__parameters"]["FollowPath"]


@pytest.fixture(scope="module")
def costmaps(nav):
    return {name: nav[name][name]["ros__parameters"]
            for name in ("local_costmap", "global_costmap")}


def polygon(text):
    """nav2's footprint string as a list of (x, y)."""
    return [(float(a), float(b)) for a, b in
            re.findall(r"\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", text)]


def pad(poly, padding):
    """nav2_costmap_2d::padFootprint - per vertex, per axis, by sign."""
    def sign0(value):
        return 0.0 if value == 0.0 else math.copysign(1.0, value)
    return [(x + sign0(x) * padding, y + sign0(y) * padding)
            for x, y in poly]


# ----------------------------------------------------------------------
# the file is addressed to the six nodes m5v3.sh starts and constructs
# ----------------------------------------------------------------------

def test_every_section_config_yaml_names_is_a_top_level_key(cfg, nav):
    # The same claim m5v3.sh's check_nav_params() makes with a grep,
    # made here with a parser - so a section that is present but nested
    # one level too deep fails here even though the grep would pass.
    wanted = [cfg["nav"][part]["node_name"]
              for part in ("planner", "controller", "behavior", "bt",
                           "lifecycle")]
    wanted += cfg["nav"]["costmap_sections"].split()
    for name in wanted:
        assert name in nav, "nav2.yaml has no top-level {!r}".format(name)


def test_every_section_declares_use_sim_time(nav):
    # It is in this file rather than on four command lines because two of
    # the six sections address SUB-NODES that have no command line - the
    # file's own header argues it. What that buys is only real if every
    # section carries it: a costmap on the wall clock rejects every
    # transform as impossibly old.
    for name, section in nav.items():
        params = section.get("ros__parameters")
        if params is None:              # the two costmaps are nested
            params = section[name]["ros__parameters"]
        assert params.get("use_sim_time") is True, name


# ----------------------------------------------------------------------
# the footprint, recomputed off the model
# ----------------------------------------------------------------------

#: THE MARGIN THE POLYGON CARRIES, per axis, and the whole of section
#: (C)'s argument in two numbers. On this vehicle the body x axis IS the
#: direction of travel and y IS across it, so F3's measured anisotropy
#: lands on the polygon's own axes: +0.54 m of along-track error and
#: +0.11 m of cross-track. `footprint_padding` cannot express that -
#: nav2's padFootprint moves both axes by one number - so the POLYGON
#: carries it and the padding is 0.0.
MARGIN_X_M = 0.54
MARGIN_Y_M = 0.11


def grow(poly, mx, my):
    """The model's hull, grown per axis, which is nav2's padFootprint
    with two numbers instead of one."""
    def sign0(value):
        return 0.0 if value == 0.0 else math.copysign(1.0, value)
    return [(x + sign0(x) * mx, y + sign0(y) * my) for x, y in poly]


def test_the_footprint_is_the_MODEL_and_not_a_number_somebody_typed(
        cfg, costmaps):
    model = os.path.join(_REPO, cfg["vehicle"]["model"])
    want = grow(core.sdf_footprint(model), MARGIN_X_M, MARGIN_Y_M)
    for name, params in costmaps.items():
        got = polygon(params["footprint"])
        assert len(got) == len(want), name
        for (gx, gy), (wx, wy) in zip(got, want):
            assert abs(gx - wx) < 1e-6 and abs(gy - wy) < 1e-6, (
                "{}: nav2.yaml has ({:+.6f}, {:+.6f}) where {} grown by "
                "({:g}, {:g}) computes ({:+.6f}, {:+.6f}). The polygon "
                "is the convex hull of every collision and visual in the "
                "model plus the measured margin; if the model moved, "
                "this file has to move with it.".format(
                    name, gx, gy, cfg["vehicle"]["model"], MARGIN_X_M,
                    MARGIN_Y_M, wx, wy))


def test_the_margin_is_ANISOTROPIC_because_the_measured_error_is(cfg,
                                                                  costmaps):
    # THE ARGUMENT, AS ARITHMETIC. The along-track margin has to cover
    # F3's worst absolute error and the cross-track one its worst
    # cross-track error, and those are five times apart
    # (EVIDENCE_LOCALIZATION_V3.md 9). An isotropic padding sized on the
    # larger doubled the polygon's INSCRIBED radius, which is what put
    # the inflation layer below it and cost two runs.
    assert MARGIN_X_M >= WORST_ABSOLUTE_ERROR_M
    assert MARGIN_X_M < WORST_ABSOLUTE_ERROR_M + 0.01
    assert MARGIN_Y_M >= WORST_CROSS_TRACK_M
    assert MARGIN_Y_M < WORST_CROSS_TRACK_M + 0.01
    assert MARGIN_X_M > 4.0 * MARGIN_Y_M
    for name, params in costmaps.items():
        assert float(params["footprint_padding"]) == 0.0, (
            "{}: the margin is in the POLYGON. nav2's padFootprint moves "
            "both axes by one number and would put {:g} m on the "
            "cross-track axis, where the measurement asks for {:g}"
            .format(name, MARGIN_X_M, MARGIN_Y_M))


def test_the_two_costmaps_carry_the_SAME_polygon_and_the_SAME_padding(
        costmaps):
    # Two footprints would be two vehicles: the planner would refuse a
    # path the controller thinks it can drive, or worse the other way.
    local, glob = costmaps["local_costmap"], costmaps["global_costmap"]
    assert polygon(local["footprint"]) == polygon(glob["footprint"])
    assert local["footprint_padding"] == glob["footprint_padding"]


def test_the_footprint_reaches_the_FORK_TIPS_and_the_COUNTERWEIGHT(
        costmaps):
    # A hull computed off collisions ALONE loses both tines - they are
    # visuals on this model - and a footprint 1.0 m short at the fork end
    # looks exactly like a correct one.
    poly = polygon(costmaps["global_costmap"]["footprint"])
    assert min(x for x, _ in poly) == pytest.approx(
        -1.875 - MARGIN_X_M, abs=1e-6)
    assert max(x for x, _ in poly) == pytest.approx(
        0.860 + MARGIN_X_M, abs=1e-6)


def test_the_grown_footprint_still_fits_the_PICK_AISLE(costmaps):
    # The tightest corridor on this floor is 5.00 m and the grown
    # half-width has to leave a centreline in it - with room for the
    # inflation layer above.
    params = costmaps["global_costmap"]
    poly = pad(polygon(params["footprint"]), params["footprint_padding"])
    half = max(abs(y) for _, y in poly)
    assert half < PICK_AISLE_HALF_WIDTH_M, (
        "the grown half-width is {:.4f} m against rack faces at "
        "{:.2f} m".format(half, PICK_AISLE_HALF_WIDTH_M))
    slack = PICK_AISLE_HALF_WIDTH_M - half
    assert slack > 1.5, (
        "only {:.4f} m of lateral slack in the pick aisle".format(slack))


# ----------------------------------------------------------------------
# the turning radius, derived
# ----------------------------------------------------------------------

def test_the_planner_and_the_controller_share_ONE_turning_radius(
        planner, controller):
    assert planner["minimum_turning_radius"] == \
        controller["AckermannConstraints"]["min_turning_r"]


def test_the_planned_arc_is_one_the_PLANT_HAS_DELIVERED(cfg, planner):
    # THE FRAME IS THE FINDING. The planner's radius is base_link's; the
    # arc turns about a centre on the REAR AXLE, and the rear axle
    # midpoint is |rear_axle_offset_m| from base_link - so the radius the
    # PLANT is asked for on a planned arc is sqrt(R^2 - d^2), and THAT is
    # the number that has to clear the measured floor.
    radius = float(planner["minimum_turning_radius"])
    d = abs(float(cfg["vehicle"]["rear_axle_offset_m"]))
    assert radius > d, "a base_link radius under the offset is not an arc"
    rear = math.sqrt(radius * radius - d * d)
    assert rear > DELIVERED_MIN_REAR_RADIUS_M, (
        "a planned {:.4f} m base_link arc asks the rear axle for "
        "{:.4f} m, and the worst corner this plant delivered was "
        "{:.4f} m".format(radius, rear, DELIVERED_MIN_REAR_RADIUS_M))
    reserve = (1.0 / DELIVERED_MIN_REAR_RADIUS_M) / (1.0 / rear)
    assert reserve > 2.0, (
        "curvature reserve is only {:.2f}x - a planner must leave the "
        "controller room to tighten with".format(reserve))


def test_the_steer_angle_the_arc_asks_for_is_inside_the_COMMANDED_ceiling(
        cfg, controller):
    # The controller's min_turning_r bounds |vx|/|wz|, and
    # cmd_vel_tricycle_core reads exactly that ratio as
    # atan(L * w / v). So this is the steer angle MPPI is allowed to
    # demand, against the ceiling the converter clamps at.
    radius = float(controller["AckermannConstraints"]["min_turning_r"])
    wheelbase = float(cfg["vehicle"]["wheelbase_m"])
    steer = math.atan(wheelbase / radius)
    assert steer < float(cfg["navcmd"]["steer_command_limit_rad"])
    assert steer < float(cfg["vehicle"]["steer_limit_rad"])


# ----------------------------------------------------------------------
# the numbers that are derived from other numbers
# ----------------------------------------------------------------------

def test_model_dt_is_one_over_the_controller_frequency(nav, controller):
    rate = float(nav["controller_server"]["ros__parameters"]
                 ["controller_frequency"])
    assert float(controller["model_dt"]) * rate == pytest.approx(1.0)


def test_one_rate_runs_the_whole_command_line(cfg, nav):
    # The controller, the smoother and the converter all at 20 Hz. A
    # controller faster than the smoother has commands coalesced; slower,
    # and the smoother ramps between them on its own.
    smoother = yaml.safe_load(read(
        cfg["smoother"]["params_file"].split("/", 1)[1]))
    rate = float(nav["controller_server"]["ros__parameters"]
                 ["controller_frequency"])
    assert rate == float(cfg["navcmd"]["rate_hz"])
    assert rate == float(smoother[cfg["smoother"]["node_name"]]
                         ["ros__parameters"]["smoothing_frequency"])


def test_wz_max_is_the_transit_ceiling_on_the_tightest_permitted_arc(
        controller):
    radius = float(controller["AckermannConstraints"]["min_turning_r"])
    assert float(controller["wz_max"]) == pytest.approx(
        abs(float(controller["vx_min"])) / radius, abs=1e-6)


def test_az_max_holds_the_SAME_RATIO_as_the_linear_acceleration(
        controller):
    radius = float(controller["AckermannConstraints"]["min_turning_r"])
    assert float(controller["az_max"]) == pytest.approx(
        float(controller["ax_max"]) / radius, abs=1e-6)


def test_the_acceleration_is_the_PLANTs_own_ramp(cfg, controller):
    accel = float(cfg["navcmd"]["accel_mps2"])
    assert float(controller["ax_max"]) == pytest.approx(accel)
    assert float(controller["ax_min"]) == pytest.approx(-accel)


def test_the_two_speed_limits_are_TWO_ROWS_OF_config_yaml(cfg, controller):
    # vx_min is the FORKS-FIRST transit ceiling, which is
    # drive_route.profiles.straight's cruise and the converter's own
    # traction ceiling. vx_max is COUNTERWEIGHT-FIRST and is capped at
    # corner_creep's creep speed, because that direction leads with the
    # nav lidar's blind sector.
    profiles = cfg["drive_route"]["profiles"]
    cruise = max(abs(float(row["tread_mps"]))
                 for row in profiles["straight"])
    creep = max(abs(float(row["tread_mps"]))
                for row in profiles["corner_creep"])
    assert float(controller["vx_min"]) == pytest.approx(-cruise)
    assert float(controller["vx_min"]) == pytest.approx(
        -float(cfg["navcmd"]["speed_max_mps"]))
    assert float(controller["vx_max"]) == pytest.approx(creep)
    assert abs(float(controller["vx_min"])) > float(controller["vx_max"]), (
        "the envelope is asymmetric ON PURPOSE and this vehicle's "
        "TRANSIT direction is the negative one")


def test_the_horizon_fits_inside_the_pruned_path(controller):
    horizon = (float(controller["time_steps"]) * float(controller["model_dt"])
               * abs(float(controller["vx_min"])))
    assert float(controller["prune_distance"]) >= horizon, (
        "the critics score {:.2f} m of trajectory against a path pruned "
        "to {:.2f} m".format(horizon, float(controller["prune_distance"])))


def test_the_local_costmap_contains_the_padded_truck_AND_the_horizon(
        costmaps, controller):
    params = costmaps["local_costmap"]
    poly = pad(polygon(params["footprint"]), params["footprint_padding"])
    reach = max(abs(x) for x, _ in poly)
    horizon = (float(controller["time_steps"]) * float(controller["model_dt"])
               * abs(float(controller["vx_min"])))
    half = float(params["width"]) / 2.0
    assert half == float(params["height"]) / 2.0
    assert half > reach + horizon, (
        "a {:g} x {:g} m rolling window holds {:.3f} m either side, and "
        "the padded footprint reaches {:.3f} m with {:.3f} m of horizon "
        "beyond it".format(params["width"], params["height"], half, reach,
                           horizon))


# ----------------------------------------------------------------------
# the inflation, argued from F3's PEAKS in one direction and from the
# floor in the other
# ----------------------------------------------------------------------

def inscribed(poly):
    """The largest circle about the origin inside a convex polygon."""
    best = float("inf")
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        length = math.hypot(ex, ey)
        if length:
            best = min(best, abs(ex * ay - ax * ey) / length)
    return best


def test_the_inflation_is_a_GRADIENT_and_not_a_HARD_BAND(costmaps):
    # THE FIGURE TWO ABORTED RUNS BOUGHT. nav2 marks every cell within
    # the footprint's INSCRIBED radius of an obstacle as
    # INSCRIBED_INFLATED_OBSTACLE. If the inflation radius is below that,
    # EVERY inflated cell carries that one cost and the layer is a hard
    # band with no slope in it - so the planner has no reason at all to
    # stand off a rack corner, and a vehicle a third of a metre off a
    # plan that hugs one is a vehicle in collision.
    for name, params in costmaps.items():
        radius = float(params["inflation_layer"]["inflation_radius"])
        inner = inscribed(polygon(params["footprint"]))
        assert radius > inner, (
            "{}: inflation {:.2f} m is inside the grown footprint's own "
            "inscribed radius {:.4f} m, so every inflated cell is "
            "INSCRIBED_INFLATED_OBSTACLE and there is no gradient at "
            "all".format(name, radius, inner))


def test_the_inflation_covers_the_LATERAL_surprise(costmaps):
    lateral = WORST_CROSS_TRACK_M + WORST_MAP_ODOM_STEP_M
    for name, params in costmaps.items():
        radius = float(params["inflation_layer"]["inflation_radius"])
        assert radius > lateral, (
            "{}: {:.2f} m of inflation against a worst cross-track error "
            "of {:.4f} m plus a worst single map->odom step of {:.4f} m, "
            "which arrives in one tick and can be entirely "
            "lateral".format(name, radius, WORST_CROSS_TRACK_M,
                             WORST_MAP_ODOM_STEP_M))


def test_the_inflation_leaves_a_CORRIDOR_down_the_pick_aisle(costmaps):
    params = costmaps["global_costmap"]
    radius = float(params["inflation_layer"]["inflation_radius"])
    poly = pad(polygon(params["footprint"]), params["footprint_padding"])
    width = 2.0 * max(abs(y) for _, y in poly)
    free = 2.0 * (PICK_AISLE_HALF_WIDTH_M - radius)
    assert free > width, (
        "inflation at {:.2f} m leaves {:.2f} m of uninflated aisle for a "
        "padded footprint {:.2f} m wide".format(radius, free, width))


def test_both_costmaps_inflate_by_the_SAME_radius(costmaps):
    radii = {name: params["inflation_layer"]["inflation_radius"]
             for name, params in costmaps.items()}
    assert len(set(radii.values())) == 1, radii


# ----------------------------------------------------------------------
# the goal checker, argued against the station class AND F3's END error
# ----------------------------------------------------------------------

def test_the_goal_tolerance_is_the_STATION_CLASS_and_that_is_what_binds(
        nav):
    checker = nav["controller_server"]["ros__parameters"][
        "general_goal_checker"]
    assert float(checker["xy_goal_tolerance"]) == STATION_TOLERANCE_M
    # AND THE COMPARISON THAT SAYS WHICH ONE BINDS. The localiser's own
    # worst END error, at rest, is TIGHTER than the class the floor asks
    # for - so the floor binds. Had it gone the other way the honest
    # answer would have been the localiser's number.
    assert WORST_END_ERROR_M < STATION_TOLERANCE_M


def test_the_goal_checker_LATCHES_because_this_vehicle_cannot_pirouette(
        nav):
    checker = nav["controller_server"]["ros__parameters"][
        "general_goal_checker"]
    assert checker["stateful"] is True


# ----------------------------------------------------------------------
# NAV2's FORWARD IS THIS TRUCK's REVERSE - the four parameters
# ----------------------------------------------------------------------

def test_the_planner_can_REVERSE_at_all(planner):
    assert planner["motion_model_for_search"] == "REEDS_SHEPP", (
        "DUBIN is forward-only, and on this vehicle nav2-forward is "
        "counterweight-first")


def test_reverse_is_NOT_penalised_because_reverse_is_the_ordinary_direction(
        planner):
    assert float(planner["reverse_penalty"]) == 1.0, (
        "nav2's default is 2.0 and the research says raise it; here that "
        "would make the planner prefer COUNTERWEIGHT-FIRST legs, with "
        "the nav lidar's 90 deg blind sector leading")


def test_PreferForwardCritic_is_disabled_by_name(controller):
    assert "PreferForwardCritic" not in controller["critics"]
    assert controller["PreferForwardCritic"]["enabled"] is False, (
        "it is kept in the file with enabled: false so a reader finds "
        "the argument where they would go looking for the parameter")


def test_PathAngleCritic_does_not_use_FORWARD_PREFERENCE(controller):
    # mode 0 = FORWARD_PREFERENCE penalises any trajectory whose heading
    # is far from the bearing to the path - which on this vehicle is
    # every ordinary leg. docs/reports/m5v3-02 2 names mode 1 or 2 for
    # Reeds-Shepp paths.
    assert int(controller["PathAngleCritic"]["mode"]) in (1, 2)


def test_the_motion_model_is_Ackermann_and_the_constraint_exists(
        controller):
    assert controller["motion_model"] == "Ackermann"
    assert "min_turning_r" in controller["AckermannConstraints"]


# ----------------------------------------------------------------------
# the message type, which is silently incompatible if it is wrong
# ----------------------------------------------------------------------

def test_the_controller_publishes_the_type_the_SMOOTHER_SUBSCRIBES(
        cfg, nav):
    smoother = yaml.safe_load(read(
        cfg["smoother"]["params_file"].split("/", 1)[1]))
    want = smoother[cfg["smoother"]["node_name"]]["ros__parameters"][
        "enable_stamped_cmd_vel"]
    for section in ("controller_server", "behavior_server"):
        assert nav[section]["ros__parameters"]["enable_stamped_cmd_vel"] \
            is want, (
            "{}: a subscriber of the wrong type simply never receives "
            "anything, and the truck sits still through a perfectly "
            "healthy goal".format(section))


# ----------------------------------------------------------------------
# unknown space
# ----------------------------------------------------------------------

def test_unknown_space_is_not_traversable_and_is_TRACKED(planner, costmaps):
    assert planner["allow_unknown"] is False
    assert costmaps["global_costmap"]["track_unknown_space"] is True, (
        "with this false every never-observed cell reads as FREE and "
        "allow_unknown: false means nothing at all")


def test_the_global_costmap_has_NO_obstacle_layer(costmaps):
    # Marking live returns into a MAP-frame costmap smears every rack
    # face by the localisation error the file is dimensioned against,
    # and the smear does not clear.
    assert costmaps["global_costmap"]["plugins"] == [
        "static_layer", "inflation_layer"]


def test_the_cost_critic_and_the_costmap_AGREE_about_the_robots_shape(
        controller):
    # nav2 prints "Inconsistent configuration in collision checking" the
    # moment a polygon costmap meets a point-scoring cost critic, and it
    # is right: the centre of this truck is 2.415 m from the front of
    # it. Measured on this stack before it was turned on.
    assert controller["CostCritic"]["consider_footprint"] is True


def test_the_local_costmap_obstacle_layer_CLEARS_ITS_OWN_FOOTPRINT(
        costmaps):
    # THE ONE THING THAT MAKES THE OBSTACLE LAYER SURVIVABLE HERE. This
    # scanner sees the truck's own 3D lidar housing and both mast rails,
    # and all three land inside the footprint polygon.
    layer = costmaps["local_costmap"]["obstacle_layer"]
    assert layer["footprint_clearing_enabled"] is True


def test_the_self_returns_really_are_INSIDE_the_footprint(cfg, costmaps):
    # The claim the line above rests on, checked against the model
    # rather than asserted: the nav lidar stands at nav_lidar_mount and
    # the three pieces of this truck that reach its scan plane are at
    # base_link (0,0) and (-0.78, +-0.30). Every one has to be inside
    # the UNPADDED polygon, because that is what the layer clears.
    poly = polygon(costmaps["local_costmap"]["footprint"])

    def inside(px, py):
        # Ray casting; the polygon is convex and counter-clockwise.
        n = len(poly)
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            if (bx - ax) * (py - ay) - (by - ay) * (px - ax) < 0.0:
                return False
        return True

    for point in ((0.0, 0.0), (-0.78, 0.30), (-0.78, -0.30)):
        assert inside(*point), (
            "{} is a piece of this truck that the nav lidar can see at "
            "z = 1.80 m, and it is OUTSIDE the footprint the obstacle "
            "layer clears - so it would be marked as an obstacle 0.6 to "
            "1.5 m ahead of travel, permanently".format(point,))


# ----------------------------------------------------------------------
# the lifecycle manager
# ----------------------------------------------------------------------

def test_the_manager_drives_exactly_the_four_servers(cfg, nav):
    params = nav[cfg["nav"]["lifecycle"]["node_name"]]["ros__parameters"]
    assert params["node_names"] == [
        cfg["nav"][part]["node_name"]
        for part in ("controller", "planner", "behavior", "bt")]
    assert params["autostart"] is True


def test_the_manager_does_NOT_own_the_velocity_smoother(cfg, nav):
    # The smoother is part of the COMMAND PATH and not of this arm: it
    # goes up on every bringup and self-transitions off its own
    # autostart_node. A manager that owned it would own a node that
    # exists on arms the manager does not.
    params = nav[cfg["nav"]["lifecycle"]["node_name"]]["ros__parameters"]
    assert cfg["smoother"]["node_name"] not in params["node_names"]


def test_the_BOND_is_switched_off_which_is_the_whole_reason_this_is_allowed(
        cfg, nav):
    # localize_lifecycle() drives amcl and map_server by hand because a
    # manager's bond starves at simulation real-time factors. That
    # argument is about the BOND; switching it off is what lets the
    # manager back in.
    params = nav[cfg["nav"]["lifecycle"]["node_name"]]["ros__parameters"]
    assert float(params["bond_timeout"]) == 0.0


# ----------------------------------------------------------------------
# the addresses config.yaml owns and this file has to repeat
# ----------------------------------------------------------------------

def test_the_static_layer_subscribes_config_yamls_own_map_topic(
        cfg, costmaps):
    assert costmaps["global_costmap"]["static_layer"]["map_topic"] == \
        cfg["topics"]["map"]
    assert costmaps["global_costmap"]["static_layer"][
        "map_subscribe_transient_local"] is True, (
        "the grid is published ONCE, latched: without transient-local "
        "durability this layer waits for a message that has already been "
        "sent")


def test_the_obstacle_layer_subscribes_config_yamls_own_scan_topic(
        cfg, costmaps):
    layer = costmaps["local_costmap"]["obstacle_layer"]
    source = layer[layer["observation_sources"]]
    assert source["topic"] == cfg["topics"]["scan_nav"]


def test_every_frame_in_the_file_is_one_config_yaml_names(cfg, nav,
                                                          costmaps):
    frames = cfg["frames"]
    assert costmaps["global_costmap"]["global_frame"] == frames["map"]
    assert costmaps["local_costmap"]["global_frame"] == frames["odom"]
    for name, params in costmaps.items():
        assert params["robot_base_frame"] == frames["base_link"], name
    bt = nav["bt_navigator"]["ros__parameters"]
    assert bt["global_frame"] == frames["map"]
    assert bt["robot_base_frame"] == frames["base_link"]
    behave = nav["behavior_server"]["ros__parameters"]
    assert behave["global_frame"] == frames["map"]
    assert behave["local_frame"] == frames["odom"]
    assert behave["robot_base_frame"] == frames["base_link"]


# ----------------------------------------------------------------------
# the goals, against the road graph they were taken from
# ----------------------------------------------------------------------

def road_graph():
    """m6/ipc/route.py's graph, imported READ-ONLY."""
    import sys
    ipc = os.path.join(_REPO, "m6", "ipc")
    if ipc not in sys.path:
        sys.path.insert(0, ipc)
    import route
    return route.build_graph()


def test_every_goal_is_a_NODE_of_the_road_graph(cfg):
    graph = road_graph()
    for name, goal in cfg["nav"]["goals"].items():
        node = (float(goal["x"]), float(goal["y"]))
        assert node in graph, (
            "nav.goals.{} is {} and m6/ipc/route.py's graph has no such "
            "node. The graph is read-only to this track and these poses "
            "are a COPY of it; this is the copy saying it has gone "
            "stale.".format(name, node))


def test_the_default_goal_is_one_of_them_and_is_the_repeated_one(cfg):
    goals = cfg["nav"]["goals"]
    default = cfg["nav"]["default_goal"]
    assert default in goals
    assert int(goals[default]["repeat"]) > 1, (
        "the headline goal is the one the repeatability claim is made "
        "on, so it is the one that is repeated")
    for name, goal in goals.items():
        if name != default:
            assert int(goal["repeat"]) == 1


def test_no_two_goals_are_the_same_pose(cfg):
    seen = {(g["x"], g["y"], g["travel_yaw_rad"])
            for g in cfg["nav"]["goals"].values()}
    assert len(seen) == len(cfg["nav"]["goals"])


def test_the_goals_are_written_as_TRAVEL_headings(cfg):
    # The one place this table could silently lie. A pose yaw of 0 means
    # the COUNTERWEIGHT points at world +x, so the truck travels at -x.
    # Every entry here is the direction of TRAVEL and drive_goal.py adds
    # the pi; a table written the obvious way would arrive
    # counterweight-first and still look like a successful goal.
    import drive_goal
    for goal in cfg["nav"]["goals"].values():
        travel = float(goal["travel_yaw_rad"])
        pose = drive_goal.pose_yaw(travel)
        assert abs(abs(core.normalise_angle(pose - travel)) - math.pi) < 1e-9


# ----------------------------------------------------------------------
# the behaviour tree
# ----------------------------------------------------------------------

def test_the_tree_has_NO_Spin_and_NO_BackUp_and_no_DriveOnHeading(cfg):
    tree = read(cfg["nav"]["bt_xml"].split("/", 1)[1])
    body = re.sub(r"<!--.*?-->", "", tree, flags=re.DOTALL)
    for node in ("Spin", "BackUp", "DriveOnHeading", "AssistedTeleop"):
        assert "<{}".format(node) not in body, (
            "{} is in the tree. This vehicle cannot rotate in place and "
            "cmd_vel_tricycle_core REFUSES a yaw rate at a standstill by "
            "name, so a Spin would stand still for the whole behaviour "
            "and then report SUCCESS.".format(node))


def test_the_tree_still_replans_and_still_clears_costmaps(cfg):
    body = read(cfg["nav"]["bt_xml"].split("/", 1)[1])
    assert "<ComputePathToPose" in body and "<FollowPath" in body
    assert body.count("<ClearEntireCostmap") >= 3
    assert "<Wait" in body


def test_the_behaviour_server_runs_only_wait(cfg, nav):
    params = nav["behavior_server"]["ros__parameters"]
    assert params["behavior_plugins"] == ["wait"]
    assert params["wait"]["plugin"] == "nav2_behaviors::Wait"


def test_the_tree_file_config_yaml_names_actually_exists(cfg):
    assert os.path.isfile(os.path.join(_REPO, cfg["nav"]["bt_xml"]))


def test_only_ONE_navigator_is_declared(nav):
    assert nav["bt_navigator"]["ros__parameters"]["navigators"] == [
        "navigate_to_pose"], (
        "navigate_through_poses is a pose SEQUENCE, which is an ORDER, "
        "and orders are VDA 5050's at m6")
