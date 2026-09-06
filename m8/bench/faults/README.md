# Staged fault set (E3)

Named faults from ARCHITECTURE.md §3 C2. The plant injects these; the
classifier names them. `proceed` is not a fault and not an output.

| id | meaning |
|---|---|
| `pallet_absent` | no pallet in the last two metres |
| `pallet_rotated` | pallet yaw off the tag-derived heading |
| `pallet_shifted` | lateral offset of the pocket pair |
| `pocket_blocked` | pockets not open (load or debris) |
| `stringer_in_path` | a ridge in the fork path |

Unit fixtures for these names live in `m8/tests/test_abort.py` (synthetic
depth, no Gazebo). Plant injection scripts are not in A1 — they need
`warehouse_ver3` and the live camera.
