from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

_MAX_TITLE_CHARS = 180
_MAX_RECEIPTS = 5


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _redact_text(value: str) -> dict[str, Any]:
    digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return {"redacted": True, "length": len(value), "sha256_16": digest}


def _safe_title(value: str) -> str:
    return " ".join(value.split())[:_MAX_TITLE_CHARS]


def _windows_active_window_title() -> dict[str, Any]:
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"supported": True, "available": False, "reason": "no_foreground_window"}

        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return {"supported": True, "available": False, "reason": "empty_title"}

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = _safe_title(buffer.value)
        if not title:
            return {"supported": True, "available": False, "reason": "empty_title"}

        if _truthy(os.environ.get("FRANCIS_SCREEN_READBACK_REDACT_TITLES")):
            return {"supported": True, "available": True, "title": _redact_text(title)}

        return {"supported": True, "available": True, "title": title}
    except Exception as exc:  # pragma: no cover - host-specific fallback
        return {"supported": False, "available": False, "reason": type(exc).__name__}


def _active_window_readback() -> dict[str, Any]:
    system = platform.system()
    if system == "Windows":
        return {
            "platform": system,
            "capture": "not_performed",
            "pixels": False,
            "screenshot": False,
            **_windows_active_window_title(),
        }

    return {
        "platform": system,
        "supported": False,
        "available": False,
        "capture": "not_performed",
        "pixels": False,
        "screenshot": False,
        "reason": "active_window_title_unsupported_on_platform",
    }


def _state_root(env_name: str, default_parts: tuple[str, ...]) -> Path:
    override = os.environ.get(env_name)
    return Path(override) if override else repo_root().joinpath(*default_parts)


def _receipt_root(env_name: str, default_parts: tuple[str, ...]) -> Path:
    return _state_root(env_name, default_parts) / "receipts"


def _receipt_ids(root: Path) -> list[str]:
    if not root.exists():
        return []
    receipts = sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:_MAX_RECEIPTS]
    return [path.stem for path in receipts]


def _last_receipt_summary() -> dict[str, Any]:
    mcp_root = _receipt_root("FRANCIS_MCP_GATEWAY_STATE_DIR", (".francis", "mcp_gateway"))
    input_root = _receipt_root("FRANCIS_INPUT_ACTUATOR_STATE_DIR", (".francis", "input_actuator"))
    takeover_root = _receipt_root("FRANCIS_TAKEOVER_SESSION_STATE_DIR", (".francis", "takeover_session"))
    return {
        "mcp_gateway_receipts": _receipt_ids(mcp_root),
        "input_actuator_receipts": _receipt_ids(input_root),
        "takeover_session_receipts": _receipt_ids(takeover_root),
        "content_included": False,
    }


def _takeover_status() -> dict[str, Any]:
    try:
        from francis.takeover_session.tools import takeover_status_snapshot

        result = takeover_status_snapshot(limit=5)
        if isinstance(result, dict):
            return result
    except Exception as exc:  # pragma: no cover - defensive readback fallback
        return {
            "ok": False,
            "status": "unavailable",
            "error": type(exc).__name__,
            "control_transfer_active": False,
            "active_session_id": "",
        }
    return {"ok": False, "status": "unavailable", "control_transfer_active": False, "active_session_id": ""}


def screen_readback_status() -> dict[str, Any]:
    """Return the safe screen/session readback contract status."""

    system = platform.system()
    takeover = _takeover_status()
    return {
        "ok": True,
        "status": "ready",
        "surface": "screen_readback_v0",
        "created_at": _utc_now(),
        "capabilities": {
            "active_window_title": system == "Windows",
            "session_state": True,
            "takeover_session_state": True,
            "last_receipt_ids": True,
            "screen_capture": False,
            "pixel_access": False,
            "ocr": False,
            "input_execution": False,
        },
        "governance": {
            "read_only": True,
            "raw_shell": False,
            "raw_input": False,
            "screenshots": False,
            "pixels": False,
            "authority": "readback",
        },
        "env": {
            "title_redaction_enabled": _truthy(os.environ.get("FRANCIS_SCREEN_READBACK_REDACT_TITLES")),
            "real_input_enabled": _truthy(os.environ.get("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL")),
            "takeover_active": bool(takeover.get("control_transfer_active")),
            "takeover_session_id": str(takeover.get("active_session_id") or ""),
        },
    }


def session_readback(_args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return bounded desktop/session context without pixels or control."""

    takeover = _takeover_status()
    return {
        "ok": True,
        "status": "ready",
        "surface": "screen_readback_v0",
        "created_at": _utc_now(),
        "session": {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "repo_root": str(repo_root()),
        },
        "takeover": {
            "active": bool(takeover.get("control_transfer_active")),
            "session_id": str(takeover.get("active_session_id") or ""),
            "mode": str(takeover.get("mode") or "read_only"),
            "status": str(takeover.get("status") or "unknown"),
            "panic_stop_ready": bool(takeover.get("panic_stop_ready")),
            "handback_required": bool(takeover.get("handback_required")),
        },
        "input_actuator": {
            "real_input_enabled": _truthy(os.environ.get("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL")),
            "requires_takeover": True,
        },
        "active_window": _active_window_readback(),
        "available_action_surface": [
            "francis.health",
            "francis.repo.status",
            "francis.screen.status",
            "francis.screen.session",
            "francis.takeover.status",
            "francis.takeover.propose",
            "francis.takeover.start_approved",
            "francis.takeover.end",
            "francis.input.status",
            "francis.input.propose",
            "francis.input.execute_approved",
            "francis.input.receipts",
        ],
        "last_receipts": _last_receipt_summary(),
        "safety": {
            "read_only": True,
            "screen_capture": False,
            "pixel_access": False,
            "raw_input": False,
            "secrets_read": False,
        },
    }


def main() -> int:
    print(json.dumps(session_readback({}), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
