"""test_map_core.py - the arithmetic behind the map, on geometry whose
answer is known before the test runs.

NO SIMULATOR, NO ROS, NO GRID FROM DISK. Every fixture here is built in
the test: a PGM is a bytes object, a world is an SDF string, a wall is a
list of points on a line somebody chose. That is tests/'s rule and it is
what lets the fit be trusted on a real grid - a test that needed
warehouse_v3.pgm to exist could not have been written before the map was.

THE SHAPE OF THE FIT IS THE THING UNDER TEST, and the case that matters
is CONTAMINATION. The m5_ver1 lineage measured what a least-squares seed
does to a wall with racking in front of it (sim/maps/warehouse/
register_map.py, and docs/LESSONS.md 93): it converges onto the
contaminating surface and reports a TIGHT residual against the wrong
thing, which is the worst failure available here because it looks like
success. So the contaminated-wall case below asserts the recovered angle
and not only the residual.
"""
import math
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.normpath(os.path.join(_HERE, os.pardir, "tools"))
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import map_core as mc                                 # noqa: E402


# ----------------------------------------------------------------------
# fixtures built by hand
# ----------------------------------------------------------------------

def pgm(width, height, pixels, maxval=255):
    """A binary P5 PGM as bytes, exactly as nav2's map_saver writes one."""
    head = "P5\n{} {}\n{}\n".format(width, height, maxval).encode("ascii")
    return head + bytes(bytearray(pixels))


def grid_meta(**over):
    meta = {"image": "m.pgm", "resolution": 0.05, "origin": (0.0, 0.0, 0.0),
            "negate": 0.0, "occupied_thresh": 0.65, "free_thresh": 0.196,
            "mode": "trinary"}
    meta.update(over)
    return meta


def line_points(normal, offset, tangent_from, tangent_to, step,
                angle_rad=0.0, jitter=None):
    """Points on a line, optionally rotated by angle_rad about the origin.

    `normal` names which axis the line is perpendicular to, so a north
    wall is (0, 1) and the points run along x.
    """
    out = []
    n = tangent_from
    i = 0
    while n <= tangent_to + 1e-9:
        if abs(normal[0]) > 0.5:
            x, y = offset * normal[0], n
        else:
            x, y = n, offset * normal[1]
        if jitter is not None:
            d = jitter[i % len(jitter)]
            x += d * normal[0]
            y += d * normal[1]
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        out.append((x * c - y * s, x * s + y * c))
        n += step
        i += 1
    return out


WORLD = """<?xml version="1.0" ?>
<sdf version="1.8">
  <world name="w">
    <model name="Floor">
      <static>true</static>
      <pose>0 -2 0 0 0 0</pose>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>48 32</size></plane>
          </geometry>
        </collision>
      </link>
    </model>
    <model name="WallNorth">
      <static>true</static>
      <link name="link">
        <collision name="c">
          <pose>0.000 14.100 2.000 0 0 0</pose>
          <geometry><box><size>48.600 0.200 4.000</size></box></geometry>
        </collision>
      </link>
    </model>
    <model name="WallEast">
      <static>true</static>
      <link name="link">
        <collision name="c">
          <pose>24.100 -2.000 2.000 0 0 0</pose>
          <geometry><box><size>0.200 32.000 4.000</size></box></geometry>
        </collision>
      </link>
    </model>
    <model name="RackNW1">
      <static>true</static>
      <pose>-15.750 4.250 2.000 0 0 0</pose>
      <link name="link">
        <collision name="c">
          <geometry><box><size>0.500 3.500 4.000</size></box></geometry>
        </collision>
      </link>
    </model>
    <model name="StationPaint">
      <static>true</static>
      <pose>-13.000 4.250 0 0 0 -1.570796</pose>
      <link name="link">
        <visual name="disc">
          <geometry><cylinder><radius>0.40</radius><length>0.006</length>
          </cylinder></geometry>
        </visual>
      </link>
    </model>
  </world>
</sdf>
"""


# ----------------------------------------------------------------------
# the PGM and the yaml
# ----------------------------------------------------------------------

class TestPgm(object):

    def test_reads_a_p5_grid(self):
        g = mc.parse_pgm(pgm(3, 2, [0, 128, 255, 10, 20, 30]))
        assert (g.width, g.height, g.maxval) == (3, 2, 255)
        assert list(g.pixels) == [0, 128, 255, 10, 20, 30]

    def test_skips_comments_between_the_header_fields(self):
        raw = b"P5\n# made by map_saver\n4 1\n# and another\n255\n"
        raw += bytes(bytearray([1, 2, 3, 4]))
        g = mc.parse_pgm(raw)
        assert (g.width, g.height) == (4, 1)
        assert list(g.pixels) == [1, 2, 3, 4]

    def test_refuses_anything_that_is_not_p5(self):
        with pytest.raises(mc.MapError):
            mc.parse_pgm(b"P2\n2 2\n255\n1 2 3 4\n")

    def test_refuses_a_short_read_rather_than_padding_it(self):
        with pytest.raises(mc.MapError):
            mc.parse_pgm(pgm(4, 4, [0] * 9))

    def test_takes_exactly_one_whitespace_byte_after_maxval(self):
        # a payload whose first byte is itself whitespace must survive
        g = mc.parse_pgm(pgm(2, 1, [0x20, 0x0A]))
        assert list(g.pixels) == [0x20, 0x0A]


class TestMapYaml(object):

    TEXT = ("image: warehouse_v3.pgm\n"
            "mode: trinary\n"
            "resolution: 0.05\n"
            "origin: [-30.1, -25.2, 0]\n"
            "negate: 0\n"
            "occupied_thresh: 0.65\n"
            "free_thresh: 0.25\n")

    def test_reads_the_six_keys_nav2_writes(self):
        meta = mc.parse_map_yaml(self.TEXT)
        assert meta["image"] == "warehouse_v3.pgm"
        assert meta["resolution"] == pytest.approx(0.05)
        assert meta["origin"] == pytest.approx((-30.1, -25.2, 0.0))
        assert meta["occupied_thresh"] == pytest.approx(0.65)
        assert meta["free_thresh"] == pytest.approx(0.25)
        assert meta["negate"] == pytest.approx(0.0)

    def test_refuses_a_file_with_no_origin(self):
        with pytest.raises(mc.MapError):
            mc.parse_map_yaml("image: a.pgm\nresolution: 0.05\n")

    def test_refuses_a_file_with_no_resolution(self):
        with pytest.raises(mc.MapError):
            mc.parse_map_yaml("image: a.pgm\norigin: [0, 0, 0]\n")


class TestOccupancy(object):

    def test_dark_pixels_are_occupied_at_the_files_own_threshold(self):
        g = mc.parse_pgm(pgm(4, 1, [0, 60, 200, 254]))
        mask = mc.occupied_mask(g, grid_meta())
        # shade = (255 - value)/255 ; occupied when shade > 0.65
        assert mask == [True, True, False, False]

    def test_negate_flips_which_end_is_occupied(self):
        g = mc.parse_pgm(pgm(4, 1, [0, 60, 200, 254]))
        mask = mc.occupied_mask(g, grid_meta(negate=1.0))
        # shade = value/255 now, so the BRIGHT end is the occupied one
        assert mask == [False, False, True, True]

    def test_the_threshold_comes_from_the_meta_and_is_not_hard_coded(self):
        g = mc.parse_pgm(pgm(3, 1, [100, 150, 200]))
        loose = mc.occupied_mask(g, grid_meta(occupied_thresh=0.20))
        tight = mc.occupied_mask(g, grid_meta(occupied_thresh=0.90))
        assert loose == [True, True, True]
        assert tight == [False, False, False]


class TestCellCentre(object):

    def test_row_zero_is_the_TOP_of_the_image(self):
        meta = grid_meta(origin=(-1.0, -2.0, 0.0), resolution=0.5)
        # height 4: row 0 is the top row, so it is the LARGEST y
        top = mc.cell_centre(meta, 4, 0, 0)
        bottom = mc.cell_centre(meta, 4, 0, 3)
        assert top[1] > bottom[1]
        assert bottom == pytest.approx((-1.0 + 0.25, -2.0 + 0.25))
        assert top == pytest.approx((-1.0 + 0.25, -2.0 + 3.5 * 0.5))

    def test_columns_run_left_to_right_from_the_origin(self):
        meta = grid_meta(origin=(10.0, 0.0, 0.0), resolution=0.1)
        assert mc.cell_centre(meta, 2, 0, 0)[0] == pytest.approx(10.05)
        assert mc.cell_centre(meta, 2, 5, 0)[0] == pytest.approx(10.55)


# ----------------------------------------------------------------------
# wall candidates
# ----------------------------------------------------------------------

class TestExtractExtremes(object):
    """One candidate per grid line, the OUTERMOST occupied cell, unfiltered."""

    #   . . . .
    #   . # . #      row 1
    #   # . . .      row 2
    #   . . . .
    PIX = [255, 255, 255, 255,
           255, 0, 255, 0,
           0, 255, 255, 255,
           255, 255, 255, 255]

    def grid(self):
        return mc.parse_pgm(pgm(4, 4, self.PIX))

    def test_north_takes_the_topmost_occupied_cell_of_each_column(self):
        g = self.grid()
        meta = grid_meta(resolution=1.0, origin=(0.0, 0.0, 0.0))
        pts = mc.extract_extremes(mc.occupied_mask(g, meta), g.width,
                                  g.height, meta, (0.0, 1.0))
        # columns 0, 1 and 3 have occupied cells; column 2 has none
        assert len(pts) == 3
        by_x = {round(p[0], 3): round(p[1], 3) for p in pts}
        assert by_x == {0.5: 1.5, 1.5: 2.5, 3.5: 2.5}

    def test_south_takes_the_bottommost(self):
        g = self.grid()
        meta = grid_meta(resolution=1.0, origin=(0.0, 0.0, 0.0))
        pts = mc.extract_extremes(mc.occupied_mask(g, meta), g.width,
                                  g.height, meta, (0.0, -1.0))
        by_x = {round(p[0], 3): round(p[1], 3) for p in pts}
        assert by_x == {0.5: 1.5, 1.5: 2.5, 3.5: 2.5}

    def test_east_takes_the_rightmost_occupied_cell_of_each_row(self):
        g = self.grid()
        meta = grid_meta(resolution=1.0, origin=(0.0, 0.0, 0.0))
        pts = mc.extract_extremes(mc.occupied_mask(g, meta), g.width,
                                  g.height, meta, (1.0, 0.0))
        by_y = {round(p[1], 3): round(p[0], 3) for p in pts}
        assert by_y == {2.5: 3.5, 1.5: 0.5}

    def test_west_takes_the_leftmost(self):
        g = self.grid()
        meta = grid_meta(resolution=1.0, origin=(0.0, 0.0, 0.0))
        pts = mc.extract_extremes(mc.occupied_mask(g, meta), g.width,
                                  g.height, meta, (-1.0, 0.0))
        by_y = {round(p[1], 3): round(p[0], 3) for p in pts}
        assert by_y == {2.5: 1.5, 1.5: 0.5}

    def test_nothing_is_filtered_out_by_this_function(self):
        """A candidate 5 m off the wall is still a candidate here."""
        pix = [255] * 25
        pix[0 * 5 + 0] = 0        # top-left, far from the rest
        for col in range(1, 5):
            pix[4 * 5 + col] = 0  # bottom row
        g = mc.parse_pgm(pgm(5, 5, pix))
        meta = grid_meta(resolution=1.0, origin=(0.0, 0.0, 0.0))
        pts = mc.extract_extremes(mc.occupied_mask(g, meta), g.width,
                                  g.height, meta, (0.0, 1.0))
        assert len(pts) == 5
        assert max(p[1] for p in pts) == pytest.approx(4.5)

    def test_a_tangent_window_selects_which_grid_lines_are_scanned(self):
        g = self.grid()
        meta = grid_meta(resolution=1.0, origin=(0.0, 0.0, 0.0))
        pts = mc.extract_extremes(mc.occupied_mask(g, meta), g.width,
                                  g.height, meta, (0.0, 1.0),
                                  windows=[(1.0, 2.0)])
        assert len(pts) == 1
        assert pts[0] == pytest.approx((1.5, 2.5))


# ----------------------------------------------------------------------
# fitting one wall
# ----------------------------------------------------------------------

class TestRotate(object):
    """The grid is not in the world's frame, so a scan direction is not
    a world normal. See map_core.rotate's own header."""

    def test_a_quarter_turn(self):
        assert mc.rotate((1.0, 0.0), math.pi / 2) == pytest.approx(
            (0.0, 1.0), abs=1e-9)

    def test_a_half_turn_reverses_it(self):
        assert mc.rotate((0.0, 1.0), math.pi) == pytest.approx(
            (0.0, -1.0), abs=1e-9)

    def test_the_worlds_north_wall_is_the_grids_SOUTH_side_at_yaw_pi(self):
        """The failure this exists to prevent, made concrete.

        A grid built with the map frame half a turn from the world has
        the world's north wall along its BOTTOM row. Scanning for the
        outermost occupied cell in +y would find the world's SOUTH side
        and fit it beautifully, which is the failure that looks like
        success one level up from the trimming rule's.
        """
        #  world north wall at y = +2, world south wall at y = -2,
        #  pushed through a half turn: north lands at map y = -2.
        pix = [255] * 25
        for col in range(5):
            pix[0 * 5 + col] = 0      # top row of the image
            pix[4 * 5 + col] = 0      # bottom row
        g = mc.parse_pgm(pgm(5, 5, pix))
        meta = grid_meta(resolution=1.0, origin=(0.0, 0.0, 0.0))
        mask = mc.occupied_mask(g, meta)
        world_normal = (0.0, 1.0)
        naive = mc.extract_extremes(mask, 5, 5, meta, world_normal)
        turned = mc.extract_extremes(mask, 5, 5, meta,
                                     mc.rotate(world_normal, math.pi))
        assert max(p[1] for p in naive) == pytest.approx(4.5)
        assert max(p[1] for p in turned) == pytest.approx(0.5)
        assert naive != turned


class TestFitLine(object):

    def test_a_clean_horizontal_wall_comes_back_exactly(self):
        pts = line_points((0.0, 1.0), 14.0, -20.0, 20.0, 0.05)
        normal, offset, rms = mc.fit_line(pts, (0.0, 1.0))
        assert normal == pytest.approx((0.0, 1.0), abs=1e-9)
        assert offset == pytest.approx(14.0)
        assert rms == pytest.approx(0.0, abs=1e-9)

    def test_a_rotated_wall_returns_its_rotation(self):
        theta = math.radians(1.5)
        pts = line_points((0.0, 1.0), 14.0, -20.0, 20.0, 0.05,
                          angle_rad=theta)
        normal, offset, rms = mc.fit_line(pts, (0.0, 1.0))
        assert math.atan2(normal[0], normal[1]) == pytest.approx(-theta,
                                                                 abs=1e-6)
        assert offset == pytest.approx(14.0, abs=1e-6)
        assert rms == pytest.approx(0.0, abs=1e-9)

    def test_the_returned_normal_agrees_with_the_one_it_was_given(self):
        """A wall's outward direction is the WORLD's to say, not the fit's."""
        pts = line_points((0.0, -1.0), 18.0, -20.0, 20.0, 0.05)
        normal, offset, _ = mc.fit_line(pts, (0.0, -1.0))
        assert normal[1] < 0
        assert offset == pytest.approx(18.0)

    def test_it_is_total_least_squares_and_not_y_on_x(self):
        """A vertical wall has infinite y-on-x slope and must still fit."""
        pts = line_points((1.0, 0.0), 24.0, -16.0, 14.0, 0.05)
        normal, offset, rms = mc.fit_line(pts, (1.0, 0.0))
        assert offset == pytest.approx(24.0)
        assert rms == pytest.approx(0.0, abs=1e-9)

    def test_rms_is_the_perpendicular_scatter(self):
        pts = line_points((0.0, 1.0), 14.0, -5.0, 5.0, 0.05,
                          jitter=[+0.02, -0.02])
        _, offset, rms = mc.fit_line(pts, (0.0, 1.0))
        assert offset == pytest.approx(14.0, abs=1e-3)
        assert rms == pytest.approx(0.02, abs=1e-3)


class TestQuantisationFloor(object):
    """What the BEST possible fit to a 0.05 m grid can be.

    A wall in an occupancy grid is a row of cell CENTRES, so the normal
    coordinate of every candidate is rounded to the nearest cell before
    any fit sees it. That rounding is uniform over one cell, and the rms
    of a uniform distribution of width w is w/sqrt(12) - so no line fit
    to a 0.05 m grid can report a residual below 0.0144 m, however
    perfect the map is. It is the FIRST term of the instrument floor
    EVIDENCE_MAP_V3.md quotes, and it is asserted here rather than
    claimed there.
    """

    def test_a_perfect_wall_on_a_grid_still_scatters_by_a_cell(self):
        res = 0.05
        angle = math.radians(1.3)
        pts = []
        for i in range(1200):
            t = -30.0 + i * res
            d = 14.0 + t * math.tan(angle)
            # snap to the cell centre, which is what extract_extremes
            # returns for every candidate
            pts.append((t, math.floor(d / res) * res + res / 2.0))
        _, offset, rms = mc.fit_line(pts, (0.0, 1.0))
        assert rms == pytest.approx(res / math.sqrt(12.0), abs=0.002)
        assert offset == pytest.approx(14.0, abs=res)


class TestRepeatedMedianSeed(object):

    def test_it_survives_contamination_a_least_squares_seed_does_not(self):
        """40 % of the points on a surface 0.50 m in front of the wall."""
        wall = line_points((0.0, 1.0), 14.0, -20.0, 8.0, 0.05,
                           angle_rad=math.radians(1.5))
        rack = line_points((0.0, 1.0), 13.5, 8.05, 20.0, 0.05,
                           angle_rad=math.radians(1.5))
        pts = wall + rack
        slope, intercept = mc.repeated_median_line(pts, (0.0, 1.0))
        assert intercept == pytest.approx(14.0, abs=0.05)
        # the wall's own frame runs t = -x for a north wall (the tangent
        # is the normal turned a quarter left), so a wall rotated +1.5 deg
        # in the world has slope -tan(1.5 deg) in it
        assert slope == pytest.approx(-math.tan(math.radians(1.5)), abs=0.01)

    def test_the_least_squares_seed_is_dragged_and_that_is_the_point(self):
        wall = line_points((0.0, 1.0), 14.0, -20.0, 8.0, 0.05)
        rack = line_points((0.0, 1.0), 13.5, 8.05, 20.0, 0.05)
        _, offset, _ = mc.fit_line(wall + rack, (0.0, 1.0))
        assert offset < 13.9          # dragged off the wall, by construction


class TestFitLineRobust(object):

    def test_it_trims_the_contamination_and_keeps_the_wall(self):
        wall = line_points((0.0, 1.0), 14.0, -20.0, 8.0, 0.05,
                           angle_rad=math.radians(1.5))
        rack = line_points((0.0, 1.0), 13.5, 8.05, 20.0, 0.05,
                           angle_rad=math.radians(1.5))
        fit = mc.fit_line_robust(wall + rack, (0.0, 1.0), 0.05,
                                 min_points=50, tolerance_cells=3.0)
        assert fit.dropped == len(rack)
        assert len(fit.kept) == len(wall)
        assert fit.offset == pytest.approx(14.0, abs=1e-3)
        assert fit.rms < 1e-6

    def test_the_answer_does_not_move_across_the_usable_trim_window(self):
        wall = line_points((0.0, 1.0), 14.0, -20.0, 8.0, 0.05,
                           angle_rad=math.radians(1.5),
                           jitter=[+0.02, -0.01, 0.0, -0.02, +0.01])
        rack = line_points((0.0, 1.0), 13.5, 8.05, 20.0, 0.05,
                           angle_rad=math.radians(1.5))
        angles = []
        for cells in (2.0, 3.0, 4.0, 6.0):
            fit = mc.fit_line_robust(wall + rack, (0.0, 1.0), 0.05,
                                     min_points=50, tolerance_cells=cells)
            angles.append(math.degrees(math.atan2(fit.normal[0],
                                                  fit.normal[1])))
        assert max(angles) - min(angles) < 0.01

    def test_it_refuses_too_few_points_rather_than_fitting_them(self):
        pts = line_points((0.0, 1.0), 14.0, 0.0, 0.30, 0.05)
        with pytest.raises(mc.MapError):
            mc.fit_line_robust(pts, (0.0, 1.0), 0.05, min_points=100,
                               tolerance_cells=3.0)

    def test_it_refuses_when_the_trim_eats_the_wall(self):
        """A tolerance below the scatter leaves a remnant, not a wall."""
        wall = line_points((0.0, 1.0), 14.0, -20.0, 20.0, 0.05,
                           jitter=[+1.0, -1.0])
        # 801 candidates, 401 of them on one of the two surfaces: at a
        # 0.05 m tolerance the trim can only ever keep those 401, so a
        # floor above that has to be a refusal and not a fit.
        with pytest.raises(mc.MapError):
            mc.fit_line_robust(wall, (0.0, 1.0), 0.05, min_points=500,
                               tolerance_cells=1.0)
        survived = mc.fit_line_robust(wall, (0.0, 1.0), 0.05,
                                      min_points=400, tolerance_cells=1.0)
        assert survived.dropped == 400


# ----------------------------------------------------------------------
# the rigid registration
# ----------------------------------------------------------------------

def synthetic_walls(theta, tx, ty, sides=("N", "E", "W"), noise=None):
    """Grid wall points made by pushing TRUE walls through a known SE(2).

    p_map = R(theta) p_world + t, which is the transform derive_transform
    has to recover.
    """
    truth = {"N": ((0.0, 1.0), 14.0, (-24.0, 24.0)),
             "S": ((0.0, -1.0), 18.0, (-24.0, 24.0)),
             "E": ((1.0, 0.0), 24.0, (-18.0, 14.0)),
             "W": ((-1.0, 0.0), 24.0, (-18.0, 14.0))}
    c, s = math.cos(theta), math.sin(theta)
    walls = []
    for name in sides:
        normal, offset, (lo, hi) = truth[name]
        world = line_points(normal, offset, lo, hi, 0.10)
        pts = []
        for i, (x, y) in enumerate(world):
            mx = c * x - s * y + tx
            my = s * x + c * y + ty
            if noise:
                mx += noise[(2 * i) % len(noise)]
                my += noise[(2 * i + 1) % len(noise)]
            pts.append((mx, my))
        walls.append((name, normal, offset, pts))
    return walls


class TestDeriveTransform(object):

    def test_it_recovers_a_transform_it_was_given(self):
        theta, tx, ty = math.radians(-0.45), 6.03, 5.54
        walls = synthetic_walls(theta, tx, ty)
        reg = mc.derive_transform(walls)
        assert reg["theta_rad"] == pytest.approx(theta, abs=1e-6)
        assert reg["t_x_m"] == pytest.approx(tx, abs=1e-5)
        assert reg["t_y_m"] == pytest.approx(ty, abs=1e-5)
        assert reg["residual_rms_m"] == pytest.approx(0.0, abs=1e-6)
        assert reg["residual_max_m"] == pytest.approx(0.0, abs=1e-6)

    def test_it_recovers_a_positive_rotation_too(self):
        theta, tx, ty = math.radians(1.83), -2.5, 11.25
        reg = mc.derive_transform(synthetic_walls(theta, tx, ty))
        assert reg["theta_rad"] == pytest.approx(theta, abs=1e-6)
        assert reg["t_x_m"] == pytest.approx(tx, abs=1e-5)
        assert reg["t_y_m"] == pytest.approx(ty, abs=1e-5)

    def test_it_recovers_a_HALF_TURN_when_it_is_pointed_at_one(self):
        """The case this track actually has.

        slam_toolbox's map frame is the odom frame and this stack's odom
        frame is the vehicle at spawn, which stands at yaw pi - so the
        transform from the world onto the grid is a half turn plus a
        fraction of a degree, and a search centred on zero would find its
        best value at its own edge and be refused. The hint is what makes
        it findable; the refusal is what stops it being guessed.
        """
        theta = mc.core.normalise_angle(-math.pi + math.radians(0.31))
        walls = synthetic_walls(theta, -4.2, 11.9)
        reg = mc.derive_transform(walls, hint=-math.pi)
        assert reg["theta_rad"] == pytest.approx(theta, abs=1e-6)
        assert reg["t_x_m"] == pytest.approx(-4.2, abs=1e-5)
        assert reg["t_y_m"] == pytest.approx(11.9, abs=1e-5)
        with pytest.raises(mc.MapError):
            mc.derive_transform(walls, hint=0.0)

    def test_three_walls_in_two_directions_are_enough(self):
        """North + east + west spans both axes, which is what det needs."""
        reg = mc.derive_transform(synthetic_walls(0.01, 1.0, 2.0,
                                                  sides=("N", "E", "W")))
        assert reg["t_x_m"] == pytest.approx(1.0, abs=1e-5)
        assert reg["t_y_m"] == pytest.approx(2.0, abs=1e-5)

    def test_walls_that_span_one_direction_only_are_refused(self):
        with pytest.raises(mc.MapError):
            mc.derive_transform(synthetic_walls(0.0, 1.0, 2.0,
                                                sides=("E", "W")))

    def test_the_residual_is_the_scatter_a_rigid_fit_cannot_absorb(self):
        walls = synthetic_walls(0.0, 0.0, 0.0,
                                noise=[+0.03, -0.03, +0.01, -0.01])
        reg = mc.derive_transform(walls)
        assert reg["residual_rms_m"] > 0.005
        assert reg["residual_max_m"] >= reg["residual_rms_m"]

    def test_it_reports_every_wall_it_used(self):
        reg = mc.derive_transform(synthetic_walls(0.0, 0.0, 0.0))
        assert [w["name"] for w in reg["walls"]] == ["N", "E", "W"]
        assert reg["n_wall_points"] == sum(w["points"] for w in reg["walls"])

    def test_a_transform_outside_the_scan_span_is_refused_not_clipped(self):
        walls = synthetic_walls(math.radians(20.0), 0.0, 0.0)
        with pytest.raises(mc.MapError):
            mc.derive_transform(walls, span_rad=math.radians(8.0))


class TestWorldToMap(object):

    def test_it_is_the_transform_derive_solved_for(self):
        theta, tx, ty = math.radians(-0.45), 6.03, 5.54
        reg = {"theta_rad": theta, "t_x_m": tx, "t_y_m": ty}
        x, y = mc.world_to_map(reg, 3.0, -7.0)
        c, s = math.cos(theta), math.sin(theta)
        assert x == pytest.approx(c * 3.0 - s * -7.0 + tx)
        assert y == pytest.approx(s * 3.0 + c * -7.0 + ty)

    def test_map_to_world_undoes_it(self):
        reg = {"theta_rad": math.radians(1.2), "t_x_m": -4.0, "t_y_m": 9.5}
        x, y = mc.world_to_map(reg, -11.0, 3.25)
        back = mc.map_to_world(reg, x, y)
        assert back == pytest.approx((-11.0, 3.25))

    def test_a_heading_rotates_and_wraps(self):
        reg = {"theta_rad": math.radians(179.0), "t_x_m": 0.0, "t_y_m": 0.0}
        _, _, yaw = mc.world_to_map(reg, 0.0, 0.0, math.radians(179.0))
        assert -math.pi <= yaw <= math.pi
        assert yaw == pytest.approx(math.radians(-2.0), abs=1e-9)


# ----------------------------------------------------------------------
# the world's own geometry
# ----------------------------------------------------------------------

class TestSdfGeometry(object):

    def test_a_collision_pose_composes_with_the_models(self):
        box = mc.sdf_box(WORLD, "WallNorth")
        assert box.x0 == pytest.approx(-24.3)
        assert box.x1 == pytest.approx(24.3)
        assert box.y0 == pytest.approx(14.0)
        assert box.y1 == pytest.approx(14.2)

    def test_a_model_pose_with_no_collision_pose_is_used_alone(self):
        box = mc.sdf_box(WORLD, "RackNW1")
        assert box.x0 == pytest.approx(-16.0)
        assert box.x1 == pytest.approx(-15.5)
        assert box.y0 == pytest.approx(2.5)
        assert box.y1 == pytest.approx(6.0)

    def test_a_model_that_is_not_there_is_refused_not_skipped(self):
        with pytest.raises(mc.MapError):
            mc.sdf_box(WORLD, "WallSouth")

    def test_the_inner_face_is_the_side_the_normal_points_away_from(self):
        north = mc.sdf_box(WORLD, "WallNorth")
        east = mc.sdf_box(WORLD, "WallEast")
        assert mc.inner_face(north, (0.0, 1.0)) == pytest.approx(14.0)
        assert mc.inner_face(east, (1.0, 0.0)) == pytest.approx(24.0)

    def test_the_outer_face_is_the_far_side_of_the_same_box(self):
        north = mc.sdf_box(WORLD, "WallNorth")
        assert mc.inner_face(north, (0.0, 1.0)) == pytest.approx(14.0)
        assert mc.outer_face(north, (0.0, 1.0)) == pytest.approx(14.2)

    def test_the_inner_face_does_not_assume_the_hall_is_centred(self):
        """warehouse_ver3's floor is centred on y = -2, not on the origin."""
        text = WORLD.replace("<pose>0.000 14.100 2.000 0 0 0</pose>",
                             "<pose>0.000 -18.100 2.000 0 0 0</pose>")
        box = mc.sdf_box(text, "WallNorth")
        assert mc.inner_face(box, (0.0, -1.0)) == pytest.approx(18.0)

    def test_obstacles_are_the_models_with_a_box_collision_and_no_others(self):
        names = [b.name for b in mc.sdf_obstacles(WORLD)]
        assert "WallNorth" in names
        assert "WallEast" in names
        assert "RackNW1" in names
        # a plane collision is the floor and is not an obstacle
        assert "Floor" not in names
        # paint has a visual and no collision at all
        assert "StationPaint" not in names

    def test_a_rotated_box_collision_is_refused_rather_than_projected(self):
        text = WORLD.replace(
            "<pose>-15.750 4.250 2.000 0 0 0</pose>",
            "<pose>-15.750 4.250 2.000 0 0 0.7</pose>")
        with pytest.raises(mc.MapError):
            mc.sdf_obstacles(text)


# ----------------------------------------------------------------------
# does the drive fit the floor
# ----------------------------------------------------------------------

BOX = mc.Box("R", -1.0, 1.0, -1.0, 1.0) if hasattr(mc, "Box") else None


class TestClearance(object):

    def box(self):
        return mc.Box("R", -1.0, 1.0, -1.0, 1.0)

    def test_a_point_outside_measures_to_the_nearest_face(self):
        assert mc.rect_distance(3.0, 0.0, self.box()) == pytest.approx(2.0)
        assert mc.rect_distance(0.0, -4.0, self.box()) == pytest.approx(3.0)

    def test_a_point_off_a_corner_measures_to_the_corner(self):
        assert mc.rect_distance(4.0, 5.0, self.box()) == pytest.approx(5.0)

    def test_a_point_inside_is_zero(self):
        assert mc.rect_distance(0.5, -0.5, self.box()) == pytest.approx(0.0)

    def test_the_truck_outline_is_placed_by_its_base_link_pose(self):
        poly = mc.truck_polygon(0.0, 0.0, 0.0, fore=1.875, aft=0.90,
                                half_width=0.60)
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        # travel is model -x, so `fore` reaches towards -x
        assert min(xs) == pytest.approx(-1.875)
        assert max(xs) == pytest.approx(0.90)
        assert min(ys) == pytest.approx(-0.60)
        assert max(ys) == pytest.approx(0.60)

    def test_the_outline_turns_with_the_yaw(self):
        poly = mc.truck_polygon(0.0, 0.0, math.pi / 2, fore=1.875, aft=0.90,
                                half_width=0.60)
        ys = [p[1] for p in poly]
        assert min(ys) == pytest.approx(-1.875)
        assert max(ys) == pytest.approx(0.90)

    def test_polygon_distance_is_zero_when_they_overlap(self):
        a = mc.truck_polygon(0.0, 0.0, 0.0, 1.875, 0.90, 0.60)
        assert mc.polygon_distance(a, mc.box_polygon(self.box())) == 0.0

    def test_polygon_distance_is_the_gap_when_they_do_not(self):
        a = mc.truck_polygon(5.0, 0.0, 0.0, 1.0, 1.0, 0.5)
        # the truck spans x 4.0..6.0; the box ends at x = 1.0
        assert mc.polygon_distance(
            a, mc.box_polygon(self.box())) == pytest.approx(3.0)

    def test_path_clearance_finds_the_worst_point_and_names_the_obstacle(self):
        boxes = [mc.Box("far", 40.0, 41.0, 40.0, 41.0),
                 mc.Box("near", 0.0, 1.0, 3.0, 4.0)]
        xs = [-10.0, 0.0, 10.0]
        ys = [0.0, 0.0, 0.0]
        yaws = [0.0, 0.0, 0.0]
        worst = mc.path_clearance(xs, ys, yaws, boxes,
                                  fore=1.0, aft=1.0, half_width=0.5)
        assert worst["obstacle"] == "near"
        assert worst["index"] == 1
        assert worst["clearance_m"] == pytest.approx(2.5)

    def test_a_strike_reports_zero_rather_than_a_negative_number(self):
        boxes = [mc.Box("hit", -0.2, 0.2, -0.2, 0.2)]
        worst = mc.path_clearance([0.0], [0.0], [0.0], boxes,
                                  fore=1.0, aft=1.0, half_width=0.5)
        assert worst["clearance_m"] == 0.0
        assert worst["obstacle"] == "hit"


# ----------------------------------------------------------------------
# does the map cover the floor
# ----------------------------------------------------------------------

class TestHallRectangle(object):

    FACES = [((-1.0, 0.0), 24.0), ((1.0, 0.0), 24.0),
             ((0.0, -1.0), 18.0), ((0.0, 1.0), 14.0)]

    def test_four_faces_make_the_buildings_inner_rectangle(self):
        hall = mc.hall_rectangle(self.FACES)
        assert (hall.x0, hall.x1) == pytest.approx((-24.0, 24.0))
        assert (hall.y0, hall.y1) == pytest.approx((-18.0, 14.0))

    def test_it_does_not_assume_the_hall_is_centred_on_the_origin(self):
        hall = mc.hall_rectangle(self.FACES)
        assert (hall.y0 + hall.y1) / 2.0 == pytest.approx(-2.0)

    def test_three_faces_are_refused(self):
        with pytest.raises(mc.MapError):
            mc.hall_rectangle(self.FACES[:3])

    def test_a_diagonal_face_is_refused_rather_than_projected(self):
        bad = self.FACES[:3] + [((0.7071, 0.7071), 10.0)]
        with pytest.raises(mc.MapError):
            mc.hall_rectangle(bad)


class TestOpenFloor(object):

    def test_overlapping_rectangles_share_their_intersection(self):
        a = mc.Box("a", 0.0, 10.0, 0.0, 10.0)
        b = mc.Box("b", 8.0, 20.0, -5.0, 4.0)
        assert mc.overlap_area(a, b) == pytest.approx(2.0 * 4.0)

    def test_disjoint_rectangles_share_nothing(self):
        a = mc.Box("a", 0.0, 1.0, 0.0, 1.0)
        b = mc.Box("b", 5.0, 6.0, 5.0, 6.0)
        assert mc.overlap_area(a, b) == 0.0

    def test_the_open_floor_is_the_hall_less_what_stands_in_it(self):
        hall = mc.Box("hall", 0.0, 10.0, 0.0, 10.0)
        boxes = [mc.Box("in", 1.0, 3.0, 1.0, 3.0),
                 mc.Box("out", 20.0, 21.0, 20.0, 21.0)]
        assert mc.open_floor_area(hall, boxes) == pytest.approx(100.0 - 4.0)

    def test_an_obstacle_that_straddles_the_wall_counts_only_its_inside(self):
        hall = mc.Box("hall", 0.0, 10.0, 0.0, 10.0)
        boxes = [mc.Box("straddle", 9.0, 12.0, 0.0, 10.0)]
        assert mc.open_floor_area(hall, boxes) == pytest.approx(100.0 - 10.0)


class TestGridCensus(object):
    """Cells classified once, and asked whether they are in the building."""

    def grid(self):
        #   row0:  occupied  free      unknown  free
        #   row1:  free      unknown   free     occupied
        return mc.parse_pgm(pgm(4, 2, [0, 254, 205, 254,
                                       254, 205, 254, 0]))

    def meta(self):
        return grid_meta(resolution=1.0, origin=(0.0, 0.0, 0.0),
                         free_thresh=0.196)

    IDENTITY = {"theta_rad": 0.0, "t_x_m": 0.0, "t_y_m": 0.0}
    BIG = mc.Box("big", -100.0, 100.0, -100.0, 100.0)

    def test_it_counts_the_three_classes(self):
        c = mc.grid_census(self.grid(), self.meta(), self.IDENTITY,
                           self.BIG, self.BIG, mc.map_to_world)
        assert c["occupied_hall"] == 2
        assert c["free_hall"] == 4
        assert c["unknown"] == 2
        assert c["cells"] == 8

    def test_a_cell_beyond_the_building_is_counted_as_such(self):
        # cell centres sit at x = 0.5, 1.5, 2.5, 3.5, so a hall and a
        # building that both stop at 2.0 put columns 2 and 3 outside:
        # row 0 loses one free cell there, row 1 one free and one
        # occupied.
        small = mc.Box("h", -100.0, 2.0, -100.0, 100.0)
        c = mc.grid_census(self.grid(), self.meta(), self.IDENTITY,
                           small, small, mc.map_to_world)
        assert c["occupied_outside"] == 1
        assert c["free_outside"] == 2
        assert c["occupied_hall"] == 1
        assert c["free_hall"] == 2

    def test_the_wall_fabric_is_its_own_zone_and_not_outside(self):
        """A wall cell sits ON the inner face; two centimetres proud of
        it is a wall and not a finding."""
        hall = mc.Box("hall", -100.0, 2.0, -100.0, 100.0)
        building = mc.Box("b", -100.0, 3.0, -100.0, 100.0)
        c = mc.grid_census(self.grid(), self.meta(), self.IDENTITY,
                           hall, building, mc.map_to_world)
        # column 2 (x = 2.5) is now fabric; column 3 (x = 3.5) is outside
        assert c["free_fabric"] == 1
        assert c["occupied_fabric"] == 0
        assert c["occupied_outside"] == 1
        assert c["free_outside"] == 1

    def test_unknown_cells_are_never_asked_where_they_are(self):
        """They carry no claim, so putting them anywhere invents one."""
        far = mc.Box("hall", 1e9, 1e9 + 1.0, 1e9, 1e9 + 1.0)
        c = mc.grid_census(self.grid(), self.meta(), self.IDENTITY, far,
                           far, mc.map_to_world)
        assert c["unknown"] == 2
        assert c["occupied_hall"] + c["free_hall"] == 0

    def test_the_cell_area_comes_from_the_resolution(self):
        c = mc.grid_census(self.grid(), grid_meta(resolution=0.05),
                           self.IDENTITY, self.BIG, self.BIG,
                           mc.map_to_world)
        assert c["cell_area_m2"] == pytest.approx(0.0025)

    def test_it_reads_the_census_through_the_transform_it_is_given(self):
        """A half turn puts the grid's right-hand cells on the left."""
        half = {"theta_rad": math.pi, "t_x_m": 0.0, "t_y_m": 0.0}
        hall = mc.Box("hall", -2.0, 100.0, -100.0, 100.0)
        c = mc.grid_census(self.grid(), self.meta(), half, hall, hall,
                           mc.map_to_world)
        # map x 0.5..3.5 becomes world x -0.5..-3.5, so the far columns
        # fall outside a hall that stops at -2.0
        assert c["occupied_outside"] + c["free_outside"] > 0


# ----------------------------------------------------------------------
# the absolute score
# ----------------------------------------------------------------------

class TestSpan(object):

    def test_two_opposite_walls_give_the_distance_between_them(self):
        east = mc.LineFit((1.0, 0.0), 24.02, 0.0, [], 0)
        west = mc.LineFit((-1.0, 0.0), 23.99, 0.0, [], 0)
        assert mc.span_between(east, west) == pytest.approx(48.01)

    def test_a_span_is_refused_when_the_two_normals_are_not_opposed(self):
        north = mc.LineFit((0.0, 1.0), 14.0, 0.0, [], 0)
        east = mc.LineFit((1.0, 0.0), 24.0, 0.0, [], 0)
        with pytest.raises(mc.MapError):
            mc.span_between(north, east)

    def test_a_span_uses_the_fitted_normals_and_not_the_nominal_ones(self):
        """Two walls tilted the same way still measure their true gap."""
        t = math.radians(1.0)
        east = mc.LineFit((math.cos(t), math.sin(t)), 24.0, 0.0, [], 0)
        west = mc.LineFit((-math.cos(t), -math.sin(t)), 24.0, 0.0, [], 0)
        assert mc.span_between(east, west) == pytest.approx(48.0)

    def test_wall_rotation_is_measured_against_the_world_normal(self):
        t = math.radians(-0.45)
        fit = mc.LineFit((math.sin(-t), math.cos(t)), 14.0, 0.0, [], 0)
        assert mc.wall_rotation(fit, (0.0, 1.0)) == pytest.approx(t, abs=1e-6)

    def test_shear_is_the_spread_of_the_walls_own_rotations(self):
        fits = [((0.0, 1.0), (0.0, 1.0)),
                ((math.sin(0.01), math.cos(0.01)), (0.0, 1.0))]
        rots = [mc.wall_rotation(mc.LineFit(f, 0.0, 0.0, [], 0), n)
                for f, n in fits]
        assert max(rots) - min(rots) == pytest.approx(-0.01, abs=1e-6) or \
            max(rots) - min(rots) == pytest.approx(0.01, abs=1e-6)


class TestSelftest(object):

    def test_the_module_can_check_itself_without_pytest(self):
        assert mc._selftest() == 0
