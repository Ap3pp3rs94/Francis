from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, cast

from francis.chat.continuity.ledger import tail as continuity_tail

_TERMINAL_OPERATION_STATUSES = {"succeeded", "failed"}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _first_text(*values: Any) -> str:
    for value in values:
        text = _safe_str(value).strip()
        if text:
            return text
    return ""


def _parse_ts(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.timestamp()
        except Exception:
            return 0.0
    return 0.0


def _safe_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _safe_dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _reference_handles(meta: dict[str, Any]) -> dict[str, str]:
    references = {
        "mission_id": _first_text(
            meta.get("mission_id"), meta.get("current_task_mission_id"), meta.get("handoff_mission_id")
        ),
        "operation_id": _first_text(
            meta.get("operation_id"),
            meta.get("task_id"),
            meta.get("current_task_operation_id"),
            meta.get("handoff_operation_id"),
        ),
        "trace_id": _first_text(meta.get("trace_id"), meta.get("current_task_trace_id"), meta.get("handoff_trace_id")),
        "approval_id": _first_text(
            meta.get("approval_id"), meta.get("current_task_approval_id"), meta.get("handoff_approval_id")
        ),
        "run_id": _first_text(meta.get("run_id"), meta.get("current_task_run_id"), meta.get("handoff_run_id")),
        "artifact_dir": _first_text(
            meta.get("artifact_dir"), meta.get("current_task_artifact_dir"), meta.get("handoff_artifact_dir")
        ),
    }
    return {key: value for key, value in references.items() if value}


def _operation_receipts_from_continuity(
    *,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    try:
        entries = continuity_tail(limit=max(1, min(int(limit), 10_000)))
    except Exception:
        return []

    receipts: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        meta = _safe_dict(item.get("meta"))
        if _safe_str(meta.get("subsystem")).strip() != "operations.runtime":
            continue
        if _safe_str(meta.get("domain")).strip() != "operations":
            continue
        if _safe_str(meta.get("scope")).strip() != "mission.loop":
            continue
        operation_status = _safe_str(meta.get("operation_status")).strip().lower()
        if operation_status == "completed":
            operation_status = "succeeded"
        if operation_status not in _TERMINAL_OPERATION_STATUSES:
            continue

        references = _reference_handles(meta)
        mission_id = references.get("mission_id", "")
        operation_id = references.get("operation_id", "")
        if not mission_id or not operation_id:
            continue

        role = _safe_str(item.get("role")).strip() or "unknown"
        content = _safe_str(item.get("content")).strip()
        ts_raw = item.get("ts")
        digest = hashlib.sha1(f"{ts_raw}:{role}:{content}".encode("utf-8", errors="ignore")).hexdigest()[:12]
        receipt: dict[str, Any] = {
            "id": f"ledger_{digest}",
            "source": "continuity.ledger",
            "ts": _parse_ts(ts_raw),
            "mission_id": mission_id,
            "operation_id": operation_id,
            "trace_id": references.get("trace_id", ""),
            "approval_id": references.get("approval_id", ""),
            "run_id": references.get("run_id", ""),
            "artifact_dir": references.get("artifact_dir", ""),
            "operation_status": operation_status,
            "operation_error": _safe_str(meta.get("operation_error")).strip(),
            "result_message": _safe_str(meta.get("result_message")).strip(),
            "recovery_next_step": _safe_str(meta.get("recovery_next_step")).strip(),
            "approval_status": _first_text(
                meta.get("approval_status"),
                meta.get("current_task_approval_status"),
                meta.get("handoff_approval_status"),
            ).lower(),
            "capability": _safe_str(meta.get("capability")).strip(),
            "domain": "operations",
            "scope": "mission.loop",
            "references": references,
        }
        for key in (
            "active_stage",
            "handoff_stage",
            "handoff_action",
            "handoff_gate",
            "handoff_approval_id",
            "handoff_approval_status",
            "handoff_operation_id",
            "handoff_trace_id",
            "handoff_run_id",
            "handoff_artifact_dir",
            "handoff_next_step",
            "current_task_source",
            "current_task_approval_id",
            "current_task_approval_status",
            "current_task_previous_approval_id",
            "current_task_previous_approval_status",
            "current_task_operation_id",
            "current_task_operation_name",
            "current_task_operation_plane",
            "current_task_advance_action",
            "current_task_gate",
            "current_task_trace_id",
            "current_task_run_id",
            "current_task_artifact_dir",
            "current_task_next_step",
            "plan_status",
            "plan_current_step_id",
            "plan_current_step_title",
        ):
            value = _safe_str(meta.get(key)).strip()
            if value:
                receipt[key] = value
        for key in ("memory_receipt_count", "plan_step_count", "plan_checkpoint_count"):
            numeric_value = _safe_nonnegative_int(meta.get(key))
            if numeric_value is not None:
                receipt[key] = numeric_value
        receipts.append({key: value for key, value in receipt.items() if value != "" and value != {}})

    receipts.sort(key=lambda value: (float(value.get("ts") or 0.0), _safe_str(value.get("id"))), reverse=True)
    return receipts


def mission_operation_receipt_index(
    *,
    limit: int = 1000,
    per_mission_limit: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    receipts: dict[str, list[dict[str, Any]]] = {}
    for receipt in _operation_receipts_from_continuity(limit=limit):
        mission_id = _safe_str(receipt.get("mission_id")).strip()
        if mission_id:
            receipts.setdefault(mission_id, []).append(receipt)

    safe_per_mission_limit = max(1, min(int(per_mission_limit), 100))
    for mission_id, items in list(receipts.items()):
        receipts[mission_id] = items[:safe_per_mission_limit]
    return receipts


def mission_operation_receipts(
    mission_id: Any,
    *,
    limit: int = 1000,
    per_mission_limit: int = 5,
) -> list[dict[str, Any]]:
    cleaned = _safe_str(mission_id).strip()
    if not cleaned:
        return []
    return [
        dict(receipt)
        for receipt in mission_operation_receipt_index(
            limit=limit,
            per_mission_limit=per_mission_limit,
        ).get(cleaned, [])
        if isinstance(receipt, dict)
    ]


def operation_memory_receipts(
    operation_id: Any,
    *,
    mission_id: Any = "",
    limit: int = 1000,
    per_operation_limit: int = 5,
) -> list[dict[str, Any]]:
    cleaned_operation = _safe_str(operation_id).strip()
    cleaned_mission = _safe_str(mission_id).strip()
    if not cleaned_operation:
        return []

    receipts: list[dict[str, Any]] = []
    for receipt in _operation_receipts_from_continuity(limit=limit):
        if _safe_str(receipt.get("operation_id")).strip() != cleaned_operation:
            continue
        if cleaned_mission and _safe_str(receipt.get("mission_id")).strip() != cleaned_mission:
            continue
        receipts.append(dict(receipt))

    safe_per_operation_limit = max(1, min(int(per_operation_limit), 100))
    return receipts[:safe_per_operation_limit]
