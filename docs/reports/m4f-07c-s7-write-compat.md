brief:               docs/briefs/m4f-07c-s7-write-compat.md
status:              done
files_changed:
  - hmi/hmi_server.py — `HmiClient._write`, the single write helper every one of
    the six HMI-writable nodes passes through, now builds `ua.DataValue(ua.Variant(
    value, variant_type))` per node before calling `client.write_values(nodes,
    datavalues)`, in place of handing `write_values` a bare `ua.Variant` per node.
    Nothing else in the file changed (confirmed by `git diff --stat`: one method
    body plus its docstring).
  - hmi/EVIDENCE_HMI.md — new section F: the live failure quoted verbatim, the
    defect isolated at the wire-encoding-byte level (not just re-asserted), the
    fix, and both kernel harnesses re-run green against fresh own-port doubles.
    The file's intro paragraph now lists this brief alongside the two it already
    named.
  - docs/reports/m4f-07c-s7-write-compat.md — this report.
invariants_touched:  none
open_questions:
  - The brief's done_when states the DataValue should carry "no StatusCode".
    `ua.DataValue`'s `StatusCode` field defaults to `StatusCode()` (Good) via a
    dataclass `default_factory`, not to `None`, so passing only a `Variant` to
    `DataValue(...)` — this fix, and the bridge's identical pattern it mirrors —
    still asserts `StatusCode` present on the wire (confirmed by serialising both
    forms with `asyncua.ua.ua_binary.struct_to_binary`: mask `0x03`, bit 0 Value
    + bit 1 StatusCode; only bits 2/3, SourceTimestamp/ServerTimestamp, are
    actually absent). I mirrored the bridge's exact, already-proven construction
    rather than a stricter all-`None` form (`StatusCode=None` too, mask `0x01`)
    that a literal reading of "no StatusCode" implies, because that stricter
    form has never been written to the real CPU and this brief forbids
    contacting it to find out. `bridge/amr_bridge/opcua_side.py`'s identical
    construction has written to the commissioned CPU since M3 carrying that same
    Good StatusCode, which is why I read the live failure's "value, status and
    timestamps" wording as the OPC UA spec's fixed text for `BadWriteNotSupported`
    rather than proof that StatusCode-Good is itself refused. Recorded in full in
    `hmi/EVIDENCE_HMI.md` §F.3. If the orchestrator's live check still refuses,
    the next, one-line step is `StatusCode=None` explicit in the same helper.
  - `bridge/config/bridge-double-forklift.yaml` showed as modified in
    `git status` before and throughout this task. I did not create, edit, stage,
    inspect the diff of, or revert it — it is outside `hmi/`, and CLAUDE.md's
    per-agent write scoping means it belongs to whoever is already changing it.
    Flagging only so it is not mistaken for part of this deliverable and is not
    lost track of if it belongs to a concurrently running agent.
  - This run produced four new raw evidence files under hmi/evidence/ (two
    harness logs, two per-cycle CSVs, named m4f07c-passA/passB) that back the
    figures quoted in EVIDENCE_HMI.md §F. The brief's git instruction names only
    the two hmi/ files above plus this report, so these four sit untracked in
    the working tree rather than staged. They can be added to the historical
    record the way the original m4f-07/m4f-07b raw files were, or left as scratch
    — advisory only, not acted on here.
next_suggested:      After the orchestrator's live verification against the
  commissioned CPU, append its result to hmi/EVIDENCE_HMI.md (§F or a new §G) —
  that is the one figure this report cannot supply, since this brief forbids
  contacting that endpoint from here.
