"""Where the truck's own forks are in its own camera, and when to believe it.

WHY THIS FILE EXISTS. `EVIDENCE_M8_C1C2_FIX.md` finding 2: at a camera
range of 1.0 m the truck's forks and the pallet are ONE surface to this
camera. About 730 coarse cells with the same signature sit 0.5-1.0 m
away at 0.1 m above the floor at every pose, and at 1.0 m they abut the
pallet with no range discontinuity at all (adjacent-cell steps p50
0.0103, p90 0.0355, p99 0.0546, max 0.0721 m, and no step at the
junction), so depth-aware connectivity cannot split them either. The
merged blob leaves the face at 23-25 % of the candidates and C1 refuses.
That file named the fix and did not apply it:

    "Separating them needs a self-mask from the mast/fork joint state,
     which `m8_core` does not have."

This is that self-mask. It is GEOMETRY the vehicle already knows about
itself, not a detector: nothing here looks at the depth frame to decide
what the forks are.

WHERE THE NUMBERS COME FROM. `m5_ver3/gazebo/forklift_ver3/model.sdf`
and `m5_ver3/config.yaml`, in base_link metres:

    fork_left   pose (-1.350, +0.280, 0.075), box 1.05 x 0.12 x 0.05
    fork_right  pose (-1.350, -0.280, 0.075), same box
    both are FIXED to `carriage`, which rides `mast_joint`, a prismatic
    joint on +Z with limits 0.0 .. 1.6 m
    pallet cam  mount (-0.900, +0.400, 1.100), yaw pi, pitch 0.5236 down

The camera looks along base -X with no roll, so in the optical frame
(REP-103: +X right, +Y down, +Z forward):

    horizontal distance from the camera  d = -0.900 - x_base
    lateral                            lat = y_base - 0.400
    height above the floor               h = z_base

which puts the tine tips at d = 0.975 m, the tine roots behind the
camera at d = -0.075 m, the two tines at lat -0.74..-0.62 and
-0.18..-0.06, and the tine top at 0.050 + 0.050 + q = 0.100 + q above
the floor, where q is `mast_joint`. Those are the only numbers in this
module and each is a dimension of a part, not a fitted constant.

The pallet's own pockets are at lat -0.76..-0.60 and -0.20..-0.04 when
the pallet is staged on the centreline, so the tines sit INSIDE the
pockets in lateral - which is the point of a fork - and the only thing
that separates them from the pallet is DISTANCE. That is why the reach
pad below is small and argued, and why widening it is not a free action:
at the 1.0 m pose the tips are 25 mm short of the pallet face.

WHEN NOT TO BELIEVE IT. The mask is placed by `mast_joint`, so a mask
whose joint reading is stale is a mask in the wrong place, and a mask in
the wrong place at this range deletes part of the pallet. `is_stale`
answers that question and `m8_core.abort` acts on it by saying nothing:
a classifier that cannot tell its own forks from the scene has no word
worth publishing. Silence is not `proceed`.

Ground truth is not an input here and this module claims no plant
number: E3 does.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

# --- the vehicle, in its own camera's frame -------------------------------
# forklift_ver3/model.sdf fork_left / fork_right against config.yaml
# vehicle.cam_mount. Derived once, above, and not fitted to anything.
TINE_LATERAL_M: Tuple[Tuple[float, float], ...] = ((-0.74, -0.62),
                                                   (-0.18, -0.06))
TINE_REACH_M = 0.975          # tine tips, horizontal, from the camera
TINE_TOP_M = 0.100            # tine top above the floor at mast_joint = 0

# --- the pads, and why they are this small --------------------------------
# LATERAL. The tine is 0.12 m wide and the depth noise on this camera is
# 0.008 m (model.sdf). 0.02 m each way covers the noise and the coarse
# grid's own quantisation without reaching the 0.04 m of clear pocket
# either side of a centred tine.
LATERAL_PAD_M = 0.02
# HEIGHT. The mask is a prism from the floor to the tine top, so only the
# top edge needs a pad, and it is bounded by what it must not eat: the
# pallet face starts at the floor and the pocket mouth is 0.122 m tall.
HEIGHT_PAD_M = 0.02
# REACH. At the 1.0 m pose the tips are 0.025 m short of the pallet face.
# A pad of 0.01 m covers the depth noise and leaves 0.015 m of clearance;
# anything larger starts deleting the face the mask exists to reveal.
# THIS IS THE TIGHT ONE. Widening it is not free and is not a tuning
# knob - it trades a refusal for a wrong pose.
REACH_PAD_M = 0.01

# A JOINT READING OLDER THAN THIS IS NO JOINT READING. `mast_joint` is
# published once per physics step (about 493 Hz in a 500 Hz world) on
# /forklift/gz/joint_state, so 0.3 s of silence is a dead publisher and
# not a late one. This is config.yaml's own `steer_stale_s` argument on
# the same channel, and the number is the same 0.3 s for the same reason.
STALE_S = 0.3


@dataclass(frozen=True)
class SelfMask:
    """The volume the truck's own forks occupy in its own camera's frame.

    A prism: the tines' lateral footprint, from the floor up to the tine
    top, out to the tine tips. Everything under a tine is either the tine
    or hidden behind it, so the whole column goes - a mask with a hole in
    it is worse than none, because the survivors are a thin ragged blob
    that still merges with the pallet.

    `stamp` is the sim time of the joint reading the mask was built from.
    It is not the frame's stamp and the two are compared, never mixed.
    """

    lift_m: float = 0.0
    stamp: Optional[float] = None
    tines: Tuple[Tuple[float, float], ...] = TINE_LATERAL_M
    reach_m: float = TINE_REACH_M
    top_m: float = TINE_TOP_M
    stale_s: float = STALE_S

    @property
    def top_above_floor_m(self) -> float:
        return self.top_m + self.lift_m

    def is_stale(self, now: Optional[float]) -> bool:
        """True when this mask must not be trusted to be where it says.

        A mask with no stamp is stale: an unstamped reading is a reading
        of unknown age, and the whole point of the test is age. A `now`
        the caller could not supply is stale for the same reason. A
        stamp from the FUTURE is stale too - clocks that disagree by more
        than the window are not one clock, and guessing which is right is
        how a mask ends up in the wrong place silently.
        """
        if self.stamp is None or now is None:
            return True
        return abs(float(now) - float(self.stamp)) > self.stale_s

    def covers(self, lateral: float, height: float, d_h: float) -> bool:
        """Is this point inside the truck itself.

        `lateral` and `d_h` are optical-frame metres (right, and
        horizontal distance from the camera); `height` is metres above
        the FLOOR PLANE the frame itself supplied. Heights are never
        taken from the mount - a mask that assumed the camera height
        would be wrong on a ramp and would not say so.
        """
        if d_h < 0.0 or d_h > self.reach_m + REACH_PAD_M:
            return False
        if height > self.top_above_floor_m + HEIGHT_PAD_M:
            return False
        for lo, hi in self.tines:
            if lo - LATERAL_PAD_M <= lateral <= hi + LATERAL_PAD_M:
                return True
        return False


def from_mast_joint(position_m: float, stamp: Optional[float] = None,
                    tines: Sequence[Tuple[float, float]] = TINE_LATERAL_M
                    ) -> SelfMask:
    """Build the mask from a `mast_joint` position and its own stamp.

    `position_m` is the prismatic joint's position, which is how far the
    carriage - and with it both tines, which are fixed to it - has risen
    above its bottom stop. model.sdf limits it to 0.0 .. 1.6 m.
    """
    return SelfMask(lift_m=float(position_m), stamp=stamp,
                    tines=tuple(tines))
