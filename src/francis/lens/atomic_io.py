"""Bounded atomic file I/O for live Lens runtime state."""

from __future__ import annotations

import json
import os
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

_JSON_READ_ATTEMPTS = 5
_JSON_READ_RETRY_SECONDS = 0.02
_ATOMIC_REPLACE_ATTEMPTS = 20
_ATOMIC_REPLACE_RETRY_SECONDS = 0.025
_TRANSIENT_WINDOWS_REPLACE_ERRORS = {5, 32}


def read_json_object(path: Path) -> dict[str, Any]:
    """Read one JSON object, tolerating a short concurrent replacement window."""

    for attempt in range(_JSON_READ_ATTEMPTS):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except (OSError, json.JSONDecodeError):
            if attempt + 1 < _JSON_READ_ATTEMPTS:
                time.sleep(_JSON_READ_RETRY_SECONDS)
                continue
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Atomically replace a file with bounded Windows sharing-violation retries."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        temporary.write_bytes(payload)
        _replace_with_retry(temporary, path)
    finally:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_bytes(
        path,
        (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8"),
    )


def _replace_with_retry(source: Path, destination: Path) -> None:
    for attempt in range(_ATOMIC_REPLACE_ATTEMPTS):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            if not _is_transient_replace_error(exc) or attempt + 1 >= _ATOMIC_REPLACE_ATTEMPTS:
                raise
            time.sleep(_ATOMIC_REPLACE_RETRY_SECONDS)


def _is_transient_replace_error(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in _TRANSIENT_WINDOWS_REPLACE_ERRORS


__all__ = ["atomic_write_bytes", "atomic_write_json", "read_json_object"]
