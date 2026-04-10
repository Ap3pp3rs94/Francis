from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record
from francis.telemetry.tracing import current_context

logger = logging.getLogger(__name__)


def _log_dir() -> Path:
    return data_dir() / "logs" / "operations"


def _audit_dir() -> Path:
    return data_dir() / "logs" / "audit"


def _error_dir() -> Path:
    return data_dir() / "logs" / "errors"


def _json_enabled() -> bool:
    v = os.getenv("FRANCIS_LOG_JSON", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


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


def _write_line(path: Path, line: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception as exc:
        logger.error("Failed to write log line: %s", exc)


def log(event: str, level: str = "INFO", **fields: Any) -> None:
    payload: dict[str, Any] = {
        "ts": time.time(),
        "level": level,
        "event": event,
        **current_context().as_dict(),
        **{key: _coerce_jsonable(value) for key, value in fields.items()},
    }
    line = json.dumps(payload, ensure_ascii=True) if _json_enabled() else f"{level} {event} {fields}"
    _write_line(_log_dir() / "francis.jsonl", line)


def audit(event: str, **fields: Any) -> None:
    audit_record(event, **fields)


def error(event: str, **fields: Any) -> None:
    payload = {"ts": time.time(), "event": event, **current_context().as_dict(), **fields}
    _write_line(_error_dir() / "errors.jsonl", json.dumps(payload, ensure_ascii=True))
