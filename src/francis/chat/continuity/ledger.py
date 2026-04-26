from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir

logger = logging.getLogger(__name__)


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


def tail(limit: int = 200) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or limit <= 0:
        logger.warning("tail: limit must be a positive int")
        return []
    ledger_path = _ledger_path()
    if not ledger_path.exists():
        return []
    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        logger.error("Failed to read ledger: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
