from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_value
from francis.kernel.paths import data_dir
from francis.telemetry.tracing import current_context


def _audit_path() -> Path:
    return data_dir() / "logs" / "audit" / "audit.jsonl"


def _coerce_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _coerce_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce_jsonable(item) for item in value]
    return str(value)


def _redact_jsonable(value: Any, *, key: str = "") -> Any:
    return _coerce_jsonable(redact_governed_value(_coerce_jsonable(value), key=key))


def _append_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


@dataclass(frozen=True, slots=True)
class AuditRecord:
    ts: float
    event: str
    status: str
    fields: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "event": self.event, "status": self.status, **self.fields}


def record(event: str, *, status: str = "ok", **fields: Any) -> dict[str, Any]:
    context = current_context().as_dict()
    payload = AuditRecord(
        ts=time.time(),
        event=event.strip() or "unknown",
        status=status.strip() or "ok",
        fields={
            **{key: _redact_jsonable(value, key=key) for key, value in context.items()},
            **{key: _redact_jsonable(value, key=key) for key, value in fields.items()},
        },
    ).to_dict()
    _append_line(_audit_path(), payload)
    return payload


def append_event(event: str, **fields: Any) -> dict[str, Any]:
    return record(event, **fields)


def read_events(*, limit: int = 100, event: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    path = _audit_path()
    if not path.exists():
        return []

    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if event and str(payload.get("event", "")).strip().lower() != event.strip().lower():
            continue
        if status and str(payload.get("status", "")).strip().lower() != status.strip().lower():
            continue
        items.append(payload)
    if limit <= 0:
        return items
    return items[-limit:]
