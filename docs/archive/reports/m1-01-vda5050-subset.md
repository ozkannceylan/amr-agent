brief:               docs/briefs/m1-01-vda5050-subset.md
status:              done
files_changed:       [docs/interfaces/vda5050-subset.md]
invariants_touched:  none
open_questions:
  - The official repo's main branch is already VDA 5050 version 3.0.0
    (released 2026). The brief specified v2, so the document pins 2.1.0
    (git tag 2.1.0, commit 511d01d), the latest v2.x release. If the owner
    prefers to target 3.0.0 before M4 implementation starts, this document
    should be revised now rather than after client code exists.
  - Concrete factsheet values (speeds, dimensions, protocol limits for the
    RB-KAIROS) are declared as owned by the agv layer per invariant 10;
    a later brief must produce them.
next_suggested:      Brief m1-02 (OPC UA node model) so M1 review can cover both contracts together.
