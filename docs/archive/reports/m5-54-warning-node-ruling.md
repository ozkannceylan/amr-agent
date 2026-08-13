# Report m5-54 — the warning-field node ruling

    brief:               m5-54 (issued in-session; no file in docs/briefs/)
    status:              done
    files_changed:
      - docs/interfaces/opcua-nodes.md    (new §13 — the ruling; §12.13 pointer
                                           rows landed and items 1–3 statused;
                                           §12.2/§10.3/§11.8 totals re-derived
                                           to 47; §10.1 as-built single-FB row
                                           per m4f-04j with the browse-path
                                           read-back note; §10.1/§10.5/§10.7/
                                           §10.8 H1/§10.11 pointer edits; §11.8
                                           open item 1 closure mark; §9.7
                                           no-timer sentence rescoped)
      - docs/interfaces/bridge-design.md  (new §4.11 — the envelope group as a
                                           THIRD group, ruled, with the §13
                                           warning slot as row 23 and its
                                           silence-⇒-TRUE rule; §2.1 group set
                                           + observed configuration counts from
                                           m5-44; §4 preamble, §4.6 and §4.10
                                           scoped; §7.2 no-timer sentence
                                           rescoped; §10 double marked as not
                                           serving the group; §12 items 11
                                           superseded-note, 16 and 17 added)
      - docs/reports/m5-54-warning-node-ruling.md (this file)
    invariants_touched:  none. Checked deliberately: invariant 4 (PLC stays
                         server, bridge stays client), invariant 10 (one
                         producer — the field evaluation — two consumers over
                         two transports, neither recomputing), invariant 11
                         (the vehicle layer still sees only ROS topics), and
                         invariant 1 (the node is process data; every failure
                         of its path is more restrictive, never less, and the
                         F-side's independent copy rides the writer path that
                         never touches this server).
    open_questions:
      - The bridge slot (opcua-nodes §13 item 1 / bridge-design §12 item 16) is
        ruled but not built — the bridge agent's own brief. TIA procedure step
        358's second half waits on it; the stale direction is observable
        without it.
      - The bridge's test double does not serve §12 or §13 (bridge-design §12
        item 17) — same brief, naturally.
      - Every §13 value is a design value until the owner reads it back out of
        the tool at chunk X steps 349–360 (§13.3 item 3).
      - Whether the HMI displays the node is hmi/'s (§13 item 2).
      - NOT taken, stated so nobody rediscovers it as drift: §12.13 item 3's
        remaining half (the nine §12 start values read back with a date) is
        still the owner's; the m5-44 read-back covered types, folders and
        suffixes only.
    next_suggested:      the bridge agent's warning-slot brief (items 16+17
                         together) — it is the only remaining gap between
                         chunk X's step 358 and a fully live warning chain.

## The ruling, one line

**The node exists as `plc/forklift/SPEC.md` §14.16 requests it, unchanged:
`DemoCell/Forklift/Warning/ForkliftWarningFieldOccupied`, Bool/Boolean, in a
new one-member global DB `ForkliftWarning` under a new `Warning/` subfolder,
*Accessible* ✔ / *Writable* ✔, written by the bridge, value owned by the field
evaluation, start value `TRUE` = occupied — `opcua-nodes.md` §13, so chunk X
runs against the shape it was written for and needs no correction.**

## Why §12.12's refusal does not catch it (§13.1)

Both adjacent refusals were tested rather than waved past. It is not an SLS or
safe-speed node: it carries no speed, no limit and no setpoint, and the
SLS-pattern limit lives in the F-program and reaches no node. It is not the
safety scanner's channel: the safe copy rides the stand-in writer path
(`SafetyInputStandIn.WarningFieldClear`, safety SPEC §11.2), below any client
interface. E1 passes (a level with a producer-side 2 s clear-hold), and the
name discipline holds — the leaf names a field state, and no name contains
Safe, SLS, Speed, Ref or Cmd.

## The stale rule across the seam (§13.2 W1–W5)

An OPC UA node is a held value, so the seam is by construction the
republishing layer the producer's 20 Hz absence-visible rule exists to defeat.
The model preserves the guarantee by making every holder an asserter: the
bridge converts topic silence into an **explicit `TRUE` write** inside its own
named window (W1), so a `FALSE` on the node is always a fresh claim by a live
bridge; bridge death — the one failure that freezes the node — is caught by
the consumer's `OR NOT #bridgeLinkOk` term, whose verdict is formed outside
the frozen value (W2); the start value and the restart rewrite land at `TRUE`,
the fail direction (W3). The honest residual is stated, not hidden (W5): a
frozen `FALSE` can stand for at most the heartbeat stale window, and the
independent backstop for exactly that window is the F-side monitor on the
writer path. The seam itself cannot carry silence, and §13 says so plainly.

## The folded carried items, all landed

1. §10.1's shared-project two-FB description → as-built single FB forming both
   link verdicts (m4f-04j), heartbeat browse-path read-back note added, and
   the same phrasing swept by subject to §10.11's row.
2. The flat "no timer … in the bridge" sentence rescoped in **both** places
   (§9.7 and bridge-design §7.2) to §10.1's own-cycle/own-channel scope.
3. §11.8 open item 1 marked closed (the m5a-06b pointers verified present in
   §10.11, §10.3 tree and §10.3 count before marking).
4. The envelope group's placement ruled: **third group**, confirming m5-44's
   proposal — bridge-design §4.11 now carries the full signal map, QoS,
   writable-set and UInt16 record, with m5-44's observed counts, closing
   opcua-nodes §12.13 item 1; the §12.13 pointer rows (item 2) landed in the
   same round, with the interface total re-derived to 47 in all three places.
