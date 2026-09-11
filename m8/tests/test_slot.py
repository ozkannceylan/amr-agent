"""Classical C3 slot table on synthetic depth. No ROS."""
from m8_core.contract import KIND_SLOT_STATE, SLOT_STATES, validate_proposal
from m8_core.pocket import DepthFrame, make_plane_depth
from m8_core.slot import DEFAULT_SLOT_IDS, propose


def test_three_default_slots_are_always_proposed():
    frame = make_plane_depth(48, 36, 1.20)
    proposal = propose(frame)
    validate_proposal(proposal)
    assert proposal.kind == KIND_SLOT_STATE
    rows = proposal.slot_table()
    assert tuple(r.slot_id for r in rows) == DEFAULT_SLOT_IDS
    assert all(r.state in SLOT_STATES for r in rows)


def test_far_near_and_mid_columns_map_to_empty_occupied_blocked():
    # Paint three vertical thirds: far / near / mid.
    w, h = 48, 36
    depths = []
    for _v in range(h):
        for u in range(w):
            if u < 16:
                depths.append(2.6)
            elif u < 32:
                depths.append(1.2)
            else:
                depths.append(2.0)
    frame = DepthFrame(w, h, tuple(depths), frame_id="x", sim_stamp=1.0)
    states = [r.state for r in propose(frame).slot_table()]
    assert states == ["empty", "occupied", "blocked"]
