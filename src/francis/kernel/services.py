from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.feature_flags import get_flag
from francis.kernel.paths import repo_root
from francis.telemetry.audit import record as audit_record
from francis.telemetry.logging import log as telemetry_log

_KNOWN_SERVICES: tuple[str, ...] = ("api", "daemon", "workers", "chat_ui", "plugins")
_SERVICE_FLAG_KEYS: dict[str, str | None] = {
    "api": None,
    "daemon": "daemon.enabled",
    "workers": "workers.enabled",
    "chat_ui": None,
    "plugins": None,
}
_SERVICE_PATHS: dict[str, tuple[str, ...]] = {
    "api": ("src", "francis", "api", "app.py"),
    "daemon": ("src", "francis", "daemon", "runner.py"),
    "workers": ("src", "francis", "workers", "runner.py"),
    "chat_ui": ("apps", "chat_ui"),
    "plugins": ("plugins",),
}
_ALLOWED_ACTIONS = {"status", "probe", "start", "stop", "restart", "reload"}


def _redact_free_text(value: Any) -> str:
    try:
        return redact_secret_text(str(value or "").strip())
    except Exception:
        return ""


def _service_path(name: str) -> Path:
    rel = _SERVICE_PATHS.get(name, (name,))
    return repo_root().joinpath(*rel)


def _service_enabled(name: str) -> bool:
    flag_key = _SERVICE_FLAG_KEYS.get(name)
    if not flag_key:
        return True
    item = get_flag(flag_key)
    if not isinstance(item, dict):
        return True
    return bool(item.get("enabled"))


def _service_record(name: str) -> dict[str, Any]:
    path = _service_path(name)
    enabled = _service_enabled(name)
    exists = path.exists()
    if not exists:
        status = "missing"
    elif not enabled:
        status = "disabled"
    else:
        status = "ready"
    return {
        "name": name,
        "status": status,
        "enabled": enabled,
        "path": str(path),
        "exists": exists,
    }


def services_status() -> dict[str, object]:
    """Report local service surfaces without starting or stopping processes."""

    items = [_service_record(name) for name in _KNOWN_SERVICES]
    missing = len([item for item in items if item["status"] == "missing"])
    degraded = len([item for item in items if item["status"] == "disabled"])
    status = "ready" if missing == 0 and degraded == 0 else "degraded"
    return {
        "status": status,
        "generated_at": time.time(),
        "services": items,
        "counts": {
            "total": len(items),
            "ready": len([item for item in items if item["status"] == "ready"]),
            "disabled": degraded,
            "missing": missing,
        },
    }


def services_action(action: str, services: list[str] | None = None) -> dict[str, object]:
    """Simulate an operator action without mutating host processes.

    This is intentionally receipts-first and local-only. It acknowledges what
    would be targeted and logs the request, but it does not start/stop services.
    """

    normalized_action = (action or "").strip().lower()
    if normalized_action not in _ALLOWED_ACTIONS:
        return {
            "ok": False,
            "status": "invalid_action",
            "error": f"unsupported_action:{normalized_action or 'unknown'}",
            "allowed_actions": sorted(_ALLOWED_ACTIONS),
        }

    selected = services or list(_KNOWN_SERVICES)
    targets: list[dict[str, Any]] = []
    unknown: list[str] = []
    for name in selected:
        normalized_name = (name or "").strip()
        if normalized_name not in _KNOWN_SERVICES:
            unknown.append(_redact_free_text(normalized_name))
            continue
        item = _service_record(normalized_name)
        item["requested_action"] = normalized_action
        item["accepted"] = item["status"] != "missing"
        targets.append(item)

    audit_record(
        "services.action.requested",
        action=normalized_action,
        services=[item["name"] for item in targets],
        unknown=unknown,
    )
    telemetry_log(
        "services.action.requested",
        action=normalized_action,
        services=[item["name"] for item in targets],
        unknown=unknown,
    )

    return {
        "ok": len(unknown) == 0,
        "status": "accepted" if len(unknown) == 0 else "partial",
        "simulated": True,
        "action": normalized_action,
        "services": targets,
        "unknown_services": unknown,
    }
