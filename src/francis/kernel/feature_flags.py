from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir

__all__ = ["get_flag", "list_flags", "set_flag"]

_FLAG_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _to_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _safe_str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def _utc_now_s() -> int:
    return int(time.time())


_DEFAULT_FLAGS_TS = _utc_now_s()


def _flags_path() -> Path:
    return data_dir() / "runtime" / "feature_flags.json"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _default_flags() -> dict[str, dict[str, Any]]:
    return {
        "workers.enabled": {
            "enabled": _to_bool(os.getenv("FRANCIS_WORKERS_ENABLED"), default=True),
            "source": "env",
            "description": "Enable worker execution loops.",
            "ts": _DEFAULT_FLAGS_TS,
            "meta": {},
        },
        "daemon.enabled": {
            "enabled": _to_bool(os.getenv("FRANCIS_DAEMON_ENABLED"), default=True),
            "source": "env",
            "description": "Enable daemon control loop.",
            "ts": _DEFAULT_FLAGS_TS,
            "meta": {},
        },
        "web_learning.enabled": {
            "enabled": _to_bool(os.getenv("FRANCIS_WEB_LEARNING_ENABLED"), default=True),
            "source": "env",
            "description": "Enable web-learning features.",
            "ts": _DEFAULT_FLAGS_TS,
            "meta": {},
        },
    }


def _validate_key(key: str) -> str:
    text = key.strip()
    if not text:
        raise ValueError("flag key is required")
    if not _FLAG_KEY_RE.match(text):
        raise ValueError("invalid flag key")
    return text


def _normalize_flag_record(key: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "enabled": _to_bool(record.get("enabled"), default=False),
        "source": _safe_str(record.get("source")).strip() or "runtime",
        "description": _safe_str(record.get("description")).strip() or "",
        "ts": int(record.get("ts") or _utc_now_s()),
        "meta": dict(record.get("meta") or {}) if isinstance(record.get("meta"), dict) else {},
    }


def _load_file_flags() -> dict[str, dict[str, Any]]:
    path = _flags_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    raw_flags = raw.get("flags")
    if not isinstance(raw_flags, dict):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for key, value in raw_flags.items():
        key_text = _safe_str(key).strip()
        if not key_text:
            continue
        if not isinstance(value, dict):
            continue
        try:
            normalized_key = _validate_key(key_text)
        except Exception:
            continue
        out[normalized_key] = _normalize_flag_record(normalized_key, value)
    return out


def _write_file_flags(flags: dict[str, dict[str, Any]]) -> None:
    serialized: dict[str, dict[str, Any]] = {}
    for key, value in flags.items():
        try:
            normalized_key = _validate_key(key)
        except Exception:
            continue
        serialized[normalized_key] = _normalize_flag_record(normalized_key, value)

    _atomic_write_json(
        _flags_path(),
        {
            "version": 1,
            "updated_at": _utc_now_s(),
            "flags": serialized,
        },
    )


def list_flags() -> list[dict[str, Any]]:
    merged = _default_flags()
    file_flags = _load_file_flags()
    for key, value in file_flags.items():
        merged[key] = value

    out: list[dict[str, Any]] = []
    for key in sorted(merged.keys()):
        item = _normalize_flag_record(key, merged[key])
        out.append(item)
    return out


def get_flag(key: str) -> dict[str, Any] | None:
    normalized_key = _validate_key(key)
    for item in list_flags():
        if _safe_str(item.get("key")) == normalized_key:
            return item
    return None


def set_flag(
    key: str,
    enabled: bool,
    *,
    source: str = "api",
    description: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_key = _validate_key(key)
    current = _load_file_flags()
    current[normalized_key] = {
        "enabled": bool(enabled),
        "source": _safe_str(source).strip() or "api",
        "description": _safe_str(description).strip(),
        "ts": _utc_now_s(),
        "meta": dict(meta or {}),
    }
    _write_file_flags(current)
    return _normalize_flag_record(normalized_key, current[normalized_key])
