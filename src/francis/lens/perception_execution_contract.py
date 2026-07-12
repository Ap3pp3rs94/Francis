"""Shared exact-approval contract for resident Lens perception execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis.governance.approvals import approved_dir

LENS_PERCEPTION_EXECUTION_ACTION = "lens.perception.desktop_capture_execution"
LENS_PERCEPTION_EXECUTION_REQUEST_KIND = "lens.perception.desktop_capture_execution.request"


def lens_perception_execution_approval_status(
    approval_id: str,
    authority_receipt_id: str,
) -> dict[str, Any]:
    cleaned_approval_id = str(approval_id or "").strip()
    cleaned_receipt_id = str(authority_receipt_id or "").strip()
    blockers: list[str] = []
    if not _safe_identifier(cleaned_approval_id):
        blockers.append("desktop_capture_execution_approval_invalid")
        record: dict[str, Any] = {}
    else:
        record = _read_json(approved_dir() / f"{cleaned_approval_id}.json")
    payload = _as_dict(record.get("payload"))
    if not record:
        blockers.append("desktop_capture_execution_approval_not_found")
    else:
        if str(record.get("id") or "") != cleaned_approval_id:
            blockers.append("desktop_capture_execution_approval_id_mismatch")
        if record.get("status") != "approved":
            blockers.append("desktop_capture_execution_approval_not_approved")
        if record.get("action") != LENS_PERCEPTION_EXECUTION_ACTION:
            blockers.append("desktop_capture_execution_approval_wrong_action")
        if payload.get("kind") != LENS_PERCEPTION_EXECUTION_REQUEST_KIND:
            blockers.append("desktop_capture_execution_approval_contract_invalid")
        if str(payload.get("authority_receipt_id") or "") != cleaned_receipt_id:
            blockers.append("desktop_capture_execution_authority_receipt_mismatch")
        if payload.get("source") != "desktop_ring_buffer" or payload.get("mode") != "resident":
            blockers.append("desktop_capture_execution_scope_invalid")
        if any(
            payload.get(field) is not False
            for field in (
                "camera_capture_authority",
                "microphone_capture_authority",
                "keyboard_capture_authority",
                "user_mouse_capture_authority",
                "input_execution_authority",
                "memory_write",
            )
        ):
            blockers.append("desktop_capture_execution_approval_overbroad")
    return {
        "status": "approved" if not blockers else "blocked",
        "active": not blockers,
        "approval_id": cleaned_approval_id,
        "action": LENS_PERCEPTION_EXECUTION_ACTION,
        "authority_receipt_id": cleaned_receipt_id,
        "blockers": _dedupe(blockers),
    }


def _safe_identifier(value: Any) -> bool:
    raw = str(value or "")
    cleaned = raw.strip()
    return bool(
        cleaned
        and raw == cleaned
        and "/" not in cleaned
        and "\\" not in cleaned
        and ".." not in cleaned
        and len(cleaned) <= 180
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "LENS_PERCEPTION_EXECUTION_ACTION",
    "LENS_PERCEPTION_EXECUTION_REQUEST_KIND",
    "lens_perception_execution_approval_status",
]
