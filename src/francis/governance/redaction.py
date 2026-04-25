from __future__ import annotations

import json
import re
from typing import Any

REDACTED_SECRET = "[REDACTED:secret]"

_DEFAULT_CONTROL_KEYS = frozenset({"approval_id", "force"})
_SENSITIVE_META_KEY_RE = re.compile(
    r"(api[_-]?key|apikey|access[_-]?key|auth[_-]?token|bearer|client[_-]?secret|password|private[_-]?key|"
    r"refresh[_-]?token|secret)",
    re.IGNORECASE,
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def redact_secret_text(value: str) -> str:
    out = re.sub(
        r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s\"']{6,})",
        lambda match: f"{match.group(1)}={REDACTED_SECRET}",
        value,
    )
    out = re.sub(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", REDACTED_SECRET, out, flags=re.I)
    out = re.sub(r"\bsk-[A-Za-z0-9]{20,}\b", REDACTED_SECRET, out)
    out = re.sub(r"\bghp_[A-Za-z0-9]{30,}\b", REDACTED_SECRET, out)
    out = re.sub(r"\bAKIA[0-9A-Z]{16}\b", REDACTED_SECRET, out)
    out = re.sub(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b", REDACTED_SECRET, out)
    return out


def redact_governed_value(value: Any, *, key: str = "") -> Any:
    if key.strip().lower() == "token" or _SENSITIVE_META_KEY_RE.search(key):
        return REDACTED_SECRET
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key in sorted(value, key=lambda item: _safe_str(item).strip().lower()):
            normalized_key = _safe_str(raw_key).strip()
            if not normalized_key:
                continue
            normalized[normalized_key] = redact_governed_value(value.get(raw_key), key=normalized_key)
        return normalized
    if isinstance(value, (list, tuple)):
        return [redact_governed_value(item, key=key) for item in value]
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
    except Exception:
        return redact_secret_text(_safe_str(value))


def redact_governed_metadata(meta: Any, *, drop_control_keys: bool = False) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    normalized: dict[str, Any] = {}
    for raw_key in sorted(meta, key=lambda item: _safe_str(item).strip().lower()):
        key = _safe_str(raw_key).strip()
        if not key:
            continue
        if drop_control_keys and key in _DEFAULT_CONTROL_KEYS:
            continue
        normalized[key] = redact_governed_value(meta.get(raw_key), key=key)
    return normalized
