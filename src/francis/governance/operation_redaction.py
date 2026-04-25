from __future__ import annotations

from typing import Any

from francis.governance.redaction import redact_governed_metadata, redact_governed_value, redact_secret_text


def redact_operation_text(value: Any) -> str:
    try:
        return redact_secret_text(str(value or "").strip())
    except Exception:
        return ""


def redact_operation_optional_text(value: Any) -> str | None:
    text = redact_operation_text(value)
    return text or None


def redact_operation_value(value: Any) -> Any:
    return redact_governed_value(value)


def redact_operation_metadata(value: Any) -> dict[str, Any]:
    return redact_governed_metadata(value)


def redact_operation_task(task: Any) -> dict[str, Any]:
    redacted = redact_operation_value(task)
    return redacted if isinstance(redacted, dict) else {}
