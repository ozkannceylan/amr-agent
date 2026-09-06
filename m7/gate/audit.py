"""audit.py — append-only JSONL, one row per gate transition.

Bound by the fleet/ invariants (no ROS here; the only path to a vehicle
is VDA 5050, and this file is not on that path; losing the fleet
degrades, never endangers) and by ADR 0001 invariants 1, 2, 3, 11.
M7 is not a safety function.

THE FILE IS NEVER REWRITTEN. A row that is already on disk stays. Rotation
is by date (one file per UTC day under m7/audit/), which is a new file,
not an edit of yesterday's. This is also the raw material for the
conformance suite (ARCHITECTURE.md §5).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "audit.schema.json"
)
AUDIT_DIR = Path(__file__).resolve().parents[1] / "audit"

OPTIONAL = ("policy_rule", "decided_by", "task_id", "forward_rc")


def load_audit_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class AuditLog:
    """Append-only JSONL. `path` pins a file for tests; production
    rotates under `audit_dir` by UTC date."""

    def __init__(self, path: Path | None = None,
                 audit_dir: Path | None = None):
        self._fixed = path
        self._dir = audit_dir or AUDIT_DIR
        self._schema = load_audit_schema()
        self._validator = Draft202012Validator(self._schema)
        if self._fixed is not None:
            self._fixed.parent.mkdir(parents=True, exist_ok=True)
        else:
            self._dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, ts: float) -> Path:
        if self._fixed is not None:
            return self._fixed
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        return self._dir / ("m7-{}.jsonl".format(day))

    def append(self, row: dict) -> dict:
        payload = _normalise(row)
        errors = sorted(
            self._validator.iter_errors(payload),
            key=lambda e: list(e.path),
        )
        if errors:
            raise ValueError("audit row fails schema: {}".format(
                "; ".join(e.message for e in errors)))
        target = self.path_for(payload["ts"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, separators=(",", ":"),
                                ensure_ascii=False))
            fh.write("\n")
        return payload

    def rows(self, path: Path | None = None) -> list[dict]:
        target = path or self._fixed
        if target is None:
            if not self._dir.exists():
                return []
            paths = sorted(self._dir.glob("m7-*.jsonl"))
            out: list[dict] = []
            for item in paths:
                out.extend(_read_jsonl(item))
            return out
        if not target.exists():
            return []
        return _read_jsonl(target)


def _normalise(row: dict) -> dict:
    payload = {
        "ts": row["ts"],
        "proposal_id": row["proposal_id"],
        "client_id": row["client_id"],
        "tool": row["tool"],
        "arguments": dict(row.get("arguments") or {}),
        "schema_version": row["schema_version"],
        "verdict": row["verdict"],
    }
    for key in OPTIONAL:
        if key in row:
            payload[key] = row[key]
    return payload


def _read_jsonl(path: Path) -> list[dict]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        lines.append(json.loads(raw))
    return lines
