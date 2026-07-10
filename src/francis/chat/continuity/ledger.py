from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir

logger = logging.getLogger(__name__)

_TAIL_CHUNK_BYTES = 64 * 1024
_TAIL_MAX_BYTES = 32 * 1024 * 1024
_TAIL_CACHE_MAX_ENTRIES = 8
_TAIL_CACHE: dict[tuple[str, int, int, int], list[dict[str, Any]]] = {}


def _ledger_path() -> Path:
    return data_dir() / "conversations" / "ledger" / "ledger.jsonl"


def append(role: str, content: str, meta: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not isinstance(role, str) or not role.strip():
        logger.warning("append: role must be a non-empty string")
        return None
    if not isinstance(content, str):
        logger.warning("append: content must be a string")
        return None

    entry = {"ts": time.time(), "role": role.strip(), "content": content, "meta": meta or {}}
    try:
        ledger_path = _ledger_path()
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        return entry
    except Exception as exc:
        logger.error("Failed to append to ledger: %s", exc)
        return None


def _tail_lines(path: Path, *, limit: int) -> list[str]:
    pending = b""
    lines_reversed: list[bytes] = []
    bytes_read = 0

    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()

        while position > 0 and len(lines_reversed) < limit and bytes_read < _TAIL_MAX_BYTES:
            read_size = min(_TAIL_CHUNK_BYTES, position, _TAIL_MAX_BYTES - bytes_read)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size)
            bytes_read += len(chunk)
            parts = (chunk + pending).split(b"\n")
            pending = parts[0]
            completed = parts[1:]
            if completed and completed[-1] == b"":
                completed = completed[:-1]
            for line in reversed(completed):
                if line:
                    lines_reversed.append(line)
                    if len(lines_reversed) >= limit:
                        break

    if position == 0 and pending and len(lines_reversed) < limit:
        lines_reversed.append(pending)

    return [line.decode("utf-8", errors="replace") for line in reversed(lines_reversed[:limit])]


def tail(limit: int = 200) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or limit <= 0:
        logger.warning("tail: limit must be a positive int")
        return []
    ledger_path = _ledger_path()
    if not ledger_path.exists():
        return []
    try:
        stat = ledger_path.stat()
        cache_key = (str(ledger_path), int(limit), int(stat.st_size), int(stat.st_mtime_ns))
    except Exception:
        cache_key = None
    if cache_key is not None and cache_key in _TAIL_CACHE:
        return [dict(item) for item in _TAIL_CACHE[cache_key]]
    try:
        lines = _tail_lines(ledger_path, limit=limit)
    except Exception as exc:
        logger.error("Failed to read ledger: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    if cache_key is not None:
        _TAIL_CACHE[cache_key] = [dict(item) for item in out]
        while len(_TAIL_CACHE) > _TAIL_CACHE_MAX_ENTRIES:
            _TAIL_CACHE.pop(next(iter(_TAIL_CACHE)))
    return out
