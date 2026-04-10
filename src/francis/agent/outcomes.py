from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Outcome", "OutcomeRecord", "OutcomeLog", "record_outcome", "process_outcomes"]

_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


@dataclass(frozen=True, slots=True)
class Outcome:
    id: str
    timestamp: float = field(default_factory=lambda: float(time.time()))
    result: Any = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": float(self.timestamp),
            "result": self.result,
            "error": self.error,
            "meta": dict(self.meta or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Outcome":
        if not isinstance(data, dict):
            raise TypeError("Outcome.from_dict: data must be a dict")
        rid = data.get("id")
        if not isinstance(rid, str) or not rid.strip():
            raise ValueError("Outcome.from_dict: 'id' must be a non-empty string")
        ts = data.get("timestamp", time.time())
        try:
            ts_f = float(ts)
        except Exception as exc:
            raise ValueError("Outcome.from_dict: 'timestamp' must be numeric") from exc
        err = data.get("error")
        if err is not None and not isinstance(err, str):
            err = str(err)
        meta = data.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {"_coerced_meta": str(meta)}
        return cls(id=rid, timestamp=ts_f, result=data.get("result"), error=err, meta=meta)


OutcomeRecord = Outcome


@dataclass(frozen=True)
class OutcomeLog:
    task_id: str
    outcome: Outcome


def _validate_task_id(task_id: str) -> str:
    if not isinstance(task_id, str):
        raise TypeError("task_id must be a string")
    tid = task_id.strip()
    if not tid:
        raise ValueError("task_id must be non-empty")
    if not _TASK_ID_RE.match(tid):
        raise ValueError("task_id contains invalid characters")
    return tid


def _validate_outcome(outcome: Outcome) -> None:
    if not isinstance(outcome, Outcome):
        raise TypeError("outcome must be an Outcome")
    _validate_task_id(outcome.id)
    if not isinstance(outcome.timestamp, (int, float)):
        raise ValueError("Outcome.timestamp must be numeric")
    if outcome.error is not None and not isinstance(outcome.error, str):
        raise ValueError("Outcome.error must be a string or None")
    if outcome.meta is not None and not isinstance(outcome.meta, dict):
        raise ValueError("Outcome.meta must be a dict")


def _normalize_outcome(outcome: Outcome) -> Outcome:
    out = replace(outcome, id=outcome.id.strip(), timestamp=float(outcome.timestamp))
    if out.error is not None:
        out = replace(out, error=out.error.strip())
    if out.meta is None:
        out = replace(out, meta={})
    return out


def _task_root_dir() -> Path:
    env = (os.getenv("FRANCIS_TASK_DATA_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / "data" / "tasks").resolve()


def _task_dir(task_id: str) -> Path:
    return _task_root_dir() / task_id


def _record_path(task_id: str) -> Path:
    return _task_dir(task_id) / "record.json"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", errors="replace")
    os.replace(str(tmp), str(path))


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        raise ValueError(f"Empty JSON file: {path}")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return obj


def record_outcome(task_id: str, outcome: Outcome) -> None:
    tid = _validate_task_id(task_id)
    _validate_outcome(outcome)
    rec = _normalize_outcome(outcome).to_dict()
    text = json.dumps(rec, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    path = _record_path(tid)
    try:
        _atomic_write_text(path, text)
        logger.info("Outcome recorded: task_id=%s path=%s", tid, path)
    except Exception:
        logger.exception("Failed to record outcome: task_id=%s path=%s", tid, path)
        raise


def process_outcomes(task_id: str) -> Outcome:
    tid = _validate_task_id(task_id)
    path = _record_path(tid)
    try:
        data = _safe_read_json(path)
    except Exception:
        logger.exception("Failed to read outcome record: task_id=%s path=%s", tid, path)
        raise

    try:
        outcome = Outcome.from_dict(data)
    except Exception as exc:
        logger.exception("Invalid outcome record: task_id=%s path=%s", tid, path)
        raise ValueError(f"Invalid outcome record for task {tid}") from exc

    return _normalize_outcome(outcome)
