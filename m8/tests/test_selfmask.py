"""The truck's own forks, and the rule for when not to believe the mask.

`EVIDENCE_M8_C1C2_FIX.md` open item 1: C1 sees nothing at 1.0 m on the
plant because the tines and the pallet are one surface to this camera.
Open item 4: `stringer_in_path` cannot widen its search past the
pallet's own footprint until the tines can be told apart from the scene.
Both were named and left open with the fix named too - "a self-mask from
the mast/fork joint state, which `m8_core` does not have".

These tests hold the mask itself (geometry, off the model) and the two
things it must never do: be trusted when its joint reading is stale, and
eat the pallet it exists to reveal.

Rendered depth, no plant. E3 is the score.
"""
import pytest
import scenes

from m8_core import selfmask
from m8_core.abort import classify
from m8_core.pocket import observe, segment


def _fresh(lift_m=0.0, stamp=1.0):
    return selfmask.from_mast_joint(lift_m, stamp=stamp)


# ------------------------------------------------- the geometry is a part
def test_the_mask_is_the_model_and_not_a_fitted_constant():
    """Every number traces to forklift_ver3/model.sdf and config.yaml.

    fork_left/right at base x = -1.350 with a 1.05 m box reach to
    x = -1.875; the camera is mounted at x = -0.900, so the tips are
    0.975 m away along the optical axis. The tines sit at base
    y = +-0.28 +- 0.06 and the camera at y = +0.400, so their lateral
    spans are -0.74..-0.62 and -0.18..-0.06. The tine top is 0.050 m of
    box centred on z = 0.075, so 0.100 m above the floor at mast zero.
    """
    assert selfmask.TINE_REACH_M == pytest.approx(-0.900 + 1.875)
    assert selfmask.TINE_TOP_M == pytest.approx(0.075 + 0.025)
    assert selfmask.TINE_LATERAL_M == ((-0.74, -0.62), (-0.18, -0.06))
    for lo, hi in selfmask.TINE_LATERAL_M:
        assert hi - lo == pytest.approx(0.12, abs=1e-9)   # the box width


def test_the_mast_lifts_the_mask_with_the_forks():
    """The tines are FIXED to the carriage, which rides mast_joint."""
    assert _fresh(0.0).top_above_floor_m == pytest.approx(0.100)
    assert _fresh(0.9).top_above_floor_m == pytest.approx(1.000)


def test_the_reach_pad_cannot_reach_the_pallet_at_the_closest_pose():
    """At the 1.0 m pose the tips are 25 mm short of the pallet face.

    That is the whole clearance the mask has, so the pad is checked
    against it here rather than trusted: a pad that grew past it would
    start deleting the face the mask exists to reveal, and would do it
    silently.
    """
    clearance = scenes.CLOSE_M - selfmask.TINE_REACH_M
    assert clearance == pytest.approx(0.025, abs=1e-9)
    assert selfmask.REACH_PAD_M < clearance


def test_the_mask_covers_a_tine_and_not_the_pallet_beside_it():
    mask = _fresh()
    # On a tine, under its top, inside its reach.
    assert mask.covers(-0.68, 0.08, 0.90)
    # Same place, but beyond the tips - that is where the pallet is.
    assert not mask.covers(-0.68, 0.08, 1.00)
    # Same place and range, but above the tine: the pallet deck.
    assert not mask.covers(-0.68, 0.40, 0.90)
    # Between the tines, which is where the pallet's centre stringer is.
    assert not mask.covers(-0.40, 0.08, 0.90)
    # Behind the camera.
    assert not mask.covers(-0.68, 0.08, -0.20)


# ---------------------------------------------------------- staleness
def test_an_unstamped_or_unclocked_mask_is_stale():
    """A reading of unknown age is exactly what the test is about."""
    assert selfmask.from_mast_joint(0.0).is_stale(1.0)
    assert _fresh(stamp=1.0).is_stale(None)


def test_a_reading_from_the_future_is_stale_too():
    """Two clocks that disagree by more than the window are not one clock.

    Guessing which of them is right is how a mask ends up in the wrong
    place without anyone being told.
    """
    mask = _fresh(stamp=10.0)
    assert not mask.is_stale(10.0 + 0.5 * selfmask.STALE_S)
    assert mask.is_stale(10.0 - 2.0 * selfmask.STALE_S)
    assert mask.is_stale(10.0 + 2.0 * selfmask.STALE_S)


def test_a_stale_mask_silences_the_classifier_rather_than_guessing():
    """A mask in the wrong place at 1.0 m deletes part of the pallet.

    The classifier says nothing instead of publishing a word it derived
    from a frame it may have cut a hole in. Silence is not `proceed`.
    """
    frame, _scene = scenes.forks(scenes.CLOSE_M)
    assert classify(frame, self_mask=selfmask.from_mast_joint(0.0)) is None
    stale = selfmask.from_mast_joint(0.0, stamp=frame.sim_stamp - 5.0)
    assert classify(frame, self_mask=stale) is None


def test_no_mask_is_not_a_stale_mask():
    """A caller that never opted in gets exactly the old classifier."""
    frame, _scene = scenes.rotated(0.25)
    assert classify(frame) == "pallet_rotated"
    assert classify(frame, self_mask=None) == "pallet_rotated"


# --------------------------------------------- what the mask buys, measured
def test_the_mask_gives_c1_back_the_last_metre():
    """Open item 1, offline: refused at 1.0 m, observed with the mask."""
    frame, scene = scenes.forks(scenes.CLOSE_M)
    assert segment(frame) is None
    seg = segment(frame, self_mask=_fresh())
    assert seg is not None

    obs = observe(frame, self_mask=_fresh())
    assert obs is not None
    truth = scene.pocket_centre()
    lateral = (obs.pocket_u - frame.cx) / frame.fx * obs.face_z
    # The tag chain at staging, which is the only bar E1 states.
    assert abs(lateral - truth[0]) < scenes.TAG_BAR_M
    assert abs(obs.face_z - truth[2]) < scenes.TAG_BAR_M
    assert abs(obs.face_yaw) < 0.01


@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M])
def test_the_mask_changes_nothing_where_the_forks_were_never_the_problem(
        distance):
    """At 1.5 m and staging there is clean floor between them already."""
    frame, _scene = scenes.forks(distance)
    assert segment(frame) is not None
    assert classify(frame, self_mask=_fresh()) is None


@pytest.mark.parametrize("distance", [scenes.STAGING_M, scenes.APPROACH_M,
                                      scenes.CLOSE_M])
def test_the_mask_does_not_buy_its_result_with_the_empty_bay(distance):
    frame, _scene = scenes.forks_empty_bay(distance)
    assert classify(frame, self_mask=_fresh()) == "pallet_absent"


def test_the_mask_does_not_swallow_a_real_obstruction():
    """A bar in the fork path is still in the fork path.

    The truck's own tines travel in the fork band by definition, so they
    are excluded from it; a staged bar is not the truck and is not.
    """
    frame, _scene = scenes.stringer(scenes.CLOSE_M)
    assert classify(frame, self_mask=_fresh()) == "stringer_in_path"


def test_a_lifted_mast_does_not_mask_the_floor_it_left_behind():
    """With the forks up, the volume under them is scene again.

    A mask that stayed at the bottom stop would keep deleting a band the
    forks are no longer in, and the pallet face starts at the floor.
    """
    high = _fresh(lift_m=1.2)
    assert high.covers(-0.68, 1.10, 0.90)
    assert high.covers(-0.68, 0.08, 0.90)          # still under the forks
    low = _fresh(lift_m=0.0)
    assert not low.covers(-0.68, 1.10, 0.90)
