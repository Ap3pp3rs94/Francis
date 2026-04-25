from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from typing import Any

from francis.kernel.paths import data_dir

REDACTED_SECRET = "[REDACTED:secret]"
SEALED_SECRET_KIND = "sealed_secret"

_DEFAULT_CONTROL_KEYS = frozenset({"approval_id", "force"})
_SENSITIVE_META_KEY_RE = re.compile(
    r"(api[_-]?key|apikey|access[_-]?key|auth[_-]?token|bearer|client[_-]?secret|password|private[_-]?key|"
    r"refresh[_-]?token|secret)",
    re.IGNORECASE,
)
_SECRET_TEXT_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s\"']{6,})"
    r"|\bsk-[A-Za-z0-9]{20,}\b"
    r"|\bghp_[A-Za-z0-9]{30,}\b"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"
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


def _redaction_key() -> bytes:
    env_key = _safe_str(os.getenv("FRANCIS_REDACTION_HMAC_KEY")).strip()
    if env_key:
        return env_key.encode("utf-8")

    path = data_dir() / "governance" / "redaction_hmac.key"
    try:
        if path.exists():
            existing = path.read_text(encoding="utf-8", errors="replace").strip()
            if existing:
                return existing.encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_hex(32)
        path.write_text(generated, encoding="utf-8")
        return generated.encode("utf-8")
    except OSError:
        return b"francis-redaction-hmac-fallback"


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        return _safe_str(value)


def _is_sealed_secret(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        _safe_str(value.get("kind")).strip() == SEALED_SECRET_KIND
        and _safe_str(value.get("redacted")).strip() == REDACTED_SECRET
        and _safe_str(value.get("digest")).startswith("hmac-sha256:")
    )


def _sealed_secret(value: Any, *, key: str, redacted: str = REDACTED_SECRET) -> dict[str, str]:
    canonical = _canonical_json(value)
    digest_input = f"{key.strip().lower()}\0{canonical}".encode("utf-8", errors="replace")
    digest = hmac.new(_redaction_key(), digest_input, hashlib.sha256).hexdigest()
    return {"kind": SEALED_SECRET_KIND, "redacted": redacted, "digest": f"hmac-sha256:{digest}"}


def seal_governed_approval_value(value: Any, *, key: str = "") -> Any:
    if _is_sealed_secret(value):
        return value
    normalized_key = key.strip().lower()
    if normalized_key == "meta" and isinstance(value, dict):
        return redact_governed_metadata(value, drop_control_keys=True)
    if normalized_key == "token" or _SENSITIVE_META_KEY_RE.search(key):
        return _sealed_secret(value, key=key)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        redacted = redact_secret_text(value)
        if redacted != value or _SECRET_TEXT_RE.search(value):
            return _sealed_secret(value, key=key, redacted=redacted)
        return value
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key in sorted(value, key=lambda item: _safe_str(item).strip().lower()):
            normalized_key = _safe_str(raw_key).strip()
            if not normalized_key:
                continue
            normalized[normalized_key] = seal_governed_approval_value(value.get(raw_key), key=normalized_key)
        return normalized
    if isinstance(value, (list, tuple)):
        return [seal_governed_approval_value(item, key=key) for item in value]
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
    except Exception:
        text = _safe_str(value)
        redacted = redact_secret_text(text)
        if redacted != text:
            return _sealed_secret(text, key=key, redacted=redacted)
        return text


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
