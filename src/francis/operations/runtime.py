from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.agent import delegation as delegation_store
from francis.agent import executor as agent_executor
from francis.agent.delegation import DelegationRequest
from francis.chat.continuity.ledger import append as append_continuity_ledger
from francis.governance import approvals
from francis.governance.operation_redaction import (
    redact_operation_metadata,
    redact_operation_optional_text,
    redact_operation_task,
    redact_operation_text,
    redact_operation_value,
)
from francis.kernel.paths import data_dir
from francis.memory.mission_receipts import operation_memory_receipts
from francis.missions import store as mission_store

logger = logging.getLogger(__name__)

_TASK_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{6,128}$")
_TERMINAL_STATUSES = {"complete", "completed", "failed", "canceled", "cancelled"}
_RETRYABLE_GOVERNANCE_STATUSES = {"pending", "needs_approval", "blocked", "denied"}

_ACTION_TO_CAPABILITY: dict[str, str] = {
    "chat.summarize": "chat.summarize",
    "plan.create": "plan.create",
    "plan.revise": "plan.revise",
    "git.push": "git.push",
    "operations.git.push": "git.push",
    "codex.supervised_exec": "codex.supervised_exec",
    "supervised_exec": "codex.supervised_exec",
    "operations.supervised_exec": "codex.supervised_exec",
    "plugin.list": "plugin.list",
    "plugins.list": "plugin.list",
    "plugin.get": "plugin.get",
    "plugins.get": "plugin.get",
    "plugin.enable": "plugin.enable",
    "plugins.enable": "plugin.enable",
    "plugin.disable": "plugin.disable",
    "plugins.disable": "plugin.disable",
    "plugin.install": "plugin.install",
    "plugins.install": "plugin.install",
    "plugin.uninstall": "plugin.uninstall",
    "plugins.uninstall": "plugin.uninstall",
    "plugin.run": "plugin.run",
    "plugins.run": "plugin.run",
    "plugin.reload": "plugin.reload",
    "plugins.reload": "plugin.reload",
    "tool.run": "plugin.tool.run",
    "plugin.tool.run": "plugin.tool.run",
    "plugins.tools.run": "plugin.tool.run",
}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _parse_iso_to_unix(value: Any) -> int:
    text = _safe_str(value).strip()
    if not text:
        return 0
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp())
    except Exception:
        return 0


def _normalize_internal_status(status: Any) -> str:
    raw = _safe_str(status).strip().lower()
    if not raw:
        return "pending"
    if raw == "complete":
        return "completed"
    if raw == "canceled":
        return "cancelled"
    return raw


def _to_operation_status(status: Any) -> str:
    normalized = _normalize_internal_status(status)
    if normalized in {"pending", "accepted"}:
        return "queued"
    if normalized == "running":
        return "running"
    if normalized == "completed":
        return "succeeded"
    if normalized == "failed":
        return "failed"
    if normalized == "cancelled":
        return "canceled"
    return "unknown"


def _task_root_dir() -> Path:
    return data_dir() / "tasks"


def _record_path(task_id: str) -> Path:
    return _task_root_dir() / task_id / "record.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        text = data.decode("utf-16", errors="replace")
    elif data.startswith(b"\xef\xbb\xbf"):
        text = data.decode("utf-8-sig", errors="replace")
    elif b"\x00" in data[:200]:
        try:
            text = data.decode("utf-16", errors="replace")
        except Exception:
            text = data.decode("utf-8", errors="replace")
    else:
        text = data.decode("utf-8", errors="replace")
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError(f"record is not a dict: {path.as_posix()}")
    return obj


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def _load_task(task_id: str) -> dict[str, Any] | None:
    path = _record_path(task_id)
    if not path.exists():
        return None
    try:
        return _read_json(path)
    except Exception as exc:
        logger.error("Failed to read task record %s: %s", task_id, exc)
        return None


def _result_payload(task: dict[str, Any]) -> dict[str, Any]:
    result = task.get("result")
    if not isinstance(result, dict):
        return {}
    payload = result.get("data")
    return payload if isinstance(payload, dict) else {}


def _result_status(task: dict[str, Any]) -> str:
    payload = _result_payload(task)
    return _safe_str(payload.get("status")).strip().lower()


def _result_governance(task: dict[str, Any]) -> dict[str, Any]:
    payload = _result_payload(task)
    governance = payload.get("governance")
    return governance if isinstance(governance, dict) else {}


def _result_approval_id(task: dict[str, Any]) -> str:
    payload = _result_payload(task)
    return _safe_str(payload.get("approval_id")).strip()


def _input_approval_id(task: dict[str, Any]) -> str:
    inputs = task.get("inputs") if isinstance(task.get("inputs"), dict) else {}
    approval_id = _safe_str(inputs.get("approval_id")).strip()
    if approval_id:
        return approval_id
    meta = inputs.get("meta") if isinstance(inputs.get("meta"), dict) else {}
    return _safe_str(meta.get("approval_id")).strip()


def _operation_approval_id(task: dict[str, Any]) -> str:
    return _result_approval_id(task) or _input_approval_id(task)


def _result_previous_approval_id(task: dict[str, Any]) -> str:
    payload = _result_payload(task)
    return _safe_str(payload.get("previous_approval_id")).strip()


def _task_mission_id(task: dict[str, Any]) -> str:
    inputs = task.get("inputs")
    if not isinstance(inputs, dict):
        return ""
    mission_id = _safe_str(inputs.get("mission_id")).strip()
    if mission_id:
        return mission_id
    meta = inputs.get("meta")
    if isinstance(meta, dict):
        return _safe_str(meta.get("mission_id")).strip()
    return ""


def _task_handle_from_metadata(task: dict[str, Any], *keys: str) -> str:
    task_meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    inputs = task.get("inputs") if isinstance(task.get("inputs"), dict) else {}
    input_meta = inputs.get("meta") if isinstance(inputs.get("meta"), dict) else {}
    for source in (task_meta, input_meta):
        for key in keys:
            value = _safe_str(source.get(key)).strip()
            if value:
                return value
    return ""


def _approval_status(approval_id: str) -> str:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return ""
    for status, folder in (
        ("pending", approvals.pending_dir()),
        ("approved", approvals.approved_dir()),
        ("rejected", approvals.rejected_dir()),
        ("emergency", approvals.emergency_dir()),
    ):
        if (folder / f"{cleaned}.json").exists():
            return status
    return ""


def _operation_status_for_task(task: dict[str, Any], raw_status: str) -> str:
    result_status = _result_status(task)
    if result_status in {"blocked", "denied"}:
        return "blocked"
    if result_status in {"pending", "needs_approval"}:
        return "queued"
    return _to_operation_status(raw_status)


def _operation_plane(raw_status: str, result_status: str, governance: dict[str, Any]) -> str:
    if governance or result_status in _RETRYABLE_GOVERNANCE_STATUSES:
        return "P3_GOVERNANCE"
    if raw_status in {"pending", "accepted", "running"}:
        return "P7_EXECUTION"
    return "P9_OBSERVABILITY"


def _operation_request_ok(status: Any) -> bool:
    normalized = _safe_str(status).strip().lower()
    return normalized not in {"", "failed", "unknown"}


def _hold_retryable_governance_task(task_id: str, task: dict[str, Any]) -> dict[str, Any]:
    result_status = _result_status(task)
    if result_status not in _RETRYABLE_GOVERNANCE_STATUSES:
        return task

    updated = dict(task)
    updated["status"] = "accepted"
    updated["updated_at"] = _now_iso()
    payload = _result_payload(task)
    updated["status_reason"] = redact_operation_optional_text(
        _safe_str(payload.get("error")).strip()
        or _safe_str(payload.get("message")).strip()
        or result_status
        or _safe_str(task.get("status_reason")).strip()
    )

    inputs = dict(updated.get("inputs") or {}) if isinstance(updated.get("inputs"), dict) else {}
    input_meta = dict(inputs.get("meta") or {}) if isinstance(inputs.get("meta"), dict) else {}
    approval_id = _operation_approval_id(task)

    if result_status in {"pending", "needs_approval"} and approval_id:
        inputs["approval_id"] = approval_id
        input_meta["approval_id"] = approval_id
    elif result_status == "denied":
        inputs.pop("approval_id", None)
        input_meta.pop("approval_id", None)

    if input_meta:
        inputs["meta"] = input_meta
    else:
        inputs.pop("meta", None)
    updated["inputs"] = inputs

    _write_json(_record_path(task_id), updated)

    governance = _result_governance(task)
    previous_approval_id = _result_previous_approval_id(task)
    append = getattr(delegation_store, "_append_audit", None)
    if callable(append):
        append(
            task_id,
            "governance_hold",
            {
                "status": result_status,
                "approval_id": approval_id or None,
                "gate": _safe_str(governance.get("gate")).strip() or None,
                "next_step": redact_operation_optional_text(governance.get("next_step")),
                "reason": updated.get("status_reason"),
            },
        )
    mission_id = _task_mission_id(updated)
    if mission_id:
        mission_store.record_linked_task_transition(
            mission_id,
            task_id,
            task_status=_safe_str(updated.get("status")).strip(),
            result_status=result_status,
            status_reason=_safe_str(updated.get("status_reason")).strip(),
            governance=governance,
            approval_id=approval_id,
            previous_approval_id=previous_approval_id,
            task_updated_at=_safe_str(updated.get("updated_at")).strip(),
            actor="operations.runtime",
            note="governance_hold",
        )
    return updated


def _task_to_operation(task: dict[str, Any]) -> dict[str, Any]:
    task_id = _safe_str(task.get("task_id")).strip()
    raw_status = _normalize_internal_status(task.get("status"))
    op_status = _operation_status_for_task(task, raw_status)
    created_at = _safe_str(task.get("created_at"))
    updated_at = _safe_str(task.get("updated_at"))
    ts = _parse_iso_to_unix(updated_at) or _parse_iso_to_unix(created_at) or int(datetime.now(UTC).timestamp())

    result_obj = task.get("result") if isinstance(task.get("result"), dict) else {}
    output = redact_operation_value(result_obj.get("data"))
    output_trace = output if isinstance(output, dict) else {}
    output_receipt = output_trace.get("receipt") if isinstance(output_trace.get("receipt"), dict) else {}
    output_sandbox = (
        output_trace.get("sandbox")
        if isinstance(output_trace.get("sandbox"), dict)
        else output_receipt.get("sandbox")
        if isinstance(output_receipt.get("sandbox"), dict)
        else {}
    )
    output_audit = output_receipt.get("audit_event") if isinstance(output_receipt.get("audit_event"), dict) else {}
    output_sandbox_audit = (
        output_sandbox.get("audit_event") if isinstance(output_sandbox.get("audit_event"), dict) else {}
    )
    trace_id = (
        _safe_str(output_trace.get("trace_id")).strip()
        or _safe_str(output_trace.get("traceId")).strip()
        or _safe_str(output_receipt.get("trace_id")).strip()
        or _safe_str(output_sandbox.get("trace_id")).strip()
        or _safe_str(output_audit.get("trace_id")).strip()
        or _safe_str(output_sandbox_audit.get("trace_id")).strip()
        or _task_handle_from_metadata(task, "trace_id", "traceId")
    )
    run_id = (
        _safe_str(output_trace.get("run_id")).strip()
        or _safe_str(output_trace.get("runId")).strip()
        or _safe_str(output_receipt.get("run_id")).strip()
        or _safe_str(output_sandbox.get("run_id")).strip()
        or _safe_str(output_audit.get("run_id")).strip()
        or _safe_str(output_sandbox_audit.get("run_id")).strip()
        or _task_handle_from_metadata(task, "run_id", "runId")
    )
    artifact_dir = (
        _safe_str(output_trace.get("artifact_dir")).strip()
        or _safe_str(output_trace.get("artifact_path")).strip()
        or _safe_str(output_receipt.get("artifact_dir")).strip()
        or _safe_str(output_receipt.get("artifact_path")).strip()
        or _safe_str(output_sandbox.get("artifact_dir")).strip()
        or _safe_str(output_sandbox.get("artifact_path")).strip()
        or _safe_str(output_audit.get("artifact_dir")).strip()
        or _safe_str(output_sandbox_audit.get("artifact_dir")).strip()
        or _task_handle_from_metadata(task, "artifact_dir", "artifact_path")
    )
    result_status = _result_status(task)
    governance = _result_governance(task)
    approval_id = _operation_approval_id(task)
    error = redact_operation_optional_text(task.get("status_reason"))
    if not error:
        error = redact_operation_optional_text(
            (result_obj.get("data") or {}).get("error") if isinstance(result_obj.get("data"), dict) else ""
        )
    result_message = redact_operation_text(
        (result_obj.get("data") or {}).get("message") if isinstance(result_obj.get("data"), dict) else ""
    )
    orb_plane = _operation_plane(raw_status, result_status, governance)
    mission_id = _task_mission_id(task)

    return {
        "id": task_id,
        "ts": ts,
        "kind": "delegated_task",
        "name": _safe_str(task.get("capability")).strip() or None,
        "status": op_status,
        "level": "error" if op_status in {"failed", "blocked"} else "warning" if governance else "info",
        "actor": _safe_str(task.get("requester_id")).strip() or "unknown",
        "trace_id": trace_id or None,
        "run_id": run_id or None,
        "artifact_dir": artifact_dir or None,
        "duration_ms": None,
        "input": redact_operation_value(task.get("inputs")),
        "output": output,
        "error": error,
        "tags": task.get("tags") if isinstance(task.get("tags"), list) else None,
        "meta": {
            "raw_status": raw_status,
            "objective": redact_operation_optional_text(task.get("objective")),
            "priority": task.get("priority"),
            "ttl_sec": task.get("ttl_sec"),
            "assigned_to": task.get("assigned_to"),
            "attempts": task.get("attempts"),
            "created_at": created_at,
            "updated_at": updated_at,
            "result_status": result_status or None,
            "result_message": result_message or None,
            "approval_id": approval_id or None,
            "trace_id": trace_id or None,
            "run_id": run_id or None,
            "artifact_dir": artifact_dir or None,
            "mission_id": mission_id or None,
            "governance": redact_operation_value(governance) if governance else None,
            "orb_plane": orb_plane,
        },
    }


def _memory_receipt_projection(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
    references: dict[str, str] = {}
    for key in ("mission_id", "operation_id", "trace_id", "approval_id", "run_id", "artifact_dir"):
        value = _safe_str(meta.get(key)).strip()
        if value:
            references[key] = value
    projection: dict[str, Any] = {
        "source": "continuity.ledger",
        "kind": "ledger_append",
        "ts": entry.get("ts"),
        "role": _safe_str(entry.get("role")).strip() or None,
        "message": redact_operation_optional_text(entry.get("content")),
    }
    if references:
        projection["references"] = references
    for key in (
        "active_stage",
        "scope",
        "operation_status",
        "approval_status",
        "capability",
        "subsystem",
        "operation_error",
        "result_message",
        "recovery_next_step",
        "handoff_stage",
        "handoff_action",
        "handoff_gate",
        "handoff_operation_id",
        "handoff_trace_id",
        "handoff_run_id",
        "handoff_artifact_dir",
        "handoff_next_step",
        "current_task_source",
        "current_task_operation_id",
        "current_task_gate",
        "current_task_trace_id",
        "current_task_run_id",
        "current_task_artifact_dir",
        "current_task_next_step",
    ):
        value = _safe_str(meta.get(key)).strip()
        if value:
            projection[key] = value
    for key in ("plan_status", "plan_current_step_id", "plan_current_step_title"):
        value = _safe_str(meta.get(key)).strip()
        if value:
            projection[key] = value
    for key in ("memory_receipt_count", "plan_step_count", "plan_checkpoint_count"):
        value = meta.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            projection[key] = value
    return projection


def _safe_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _operation_plan_receipt_meta(operation: dict[str, Any]) -> dict[str, Any]:
    output = operation.get("output") if isinstance(operation.get("output"), dict) else {}
    if not output:
        return {}

    field_names = (
        "plan_status",
        "plan_current_step_id",
        "plan_current_step_title",
        "plan_step_count",
        "plan_checkpoint_count",
    )
    kind = _safe_str(output.get("kind")).strip()
    if kind != "plan.create.result" and not any(name in output for name in field_names):
        return {}

    summary: dict[str, Any] = {}
    for key in ("plan_status", "plan_current_step_id", "plan_current_step_title"):
        value = _safe_str(output.get(key)).strip()
        if value:
            summary[key] = value
    for key in ("plan_step_count", "plan_checkpoint_count"):
        value = _safe_nonnegative_int(output.get(key))
        if value is not None:
            summary[key] = value
    return summary


def _append_terminal_mission_operation_receipt(
    task: dict[str, Any], operation: dict[str, Any]
) -> dict[str, Any] | None:
    mission_id = _task_mission_id(task)
    operation_id = _safe_str(operation.get("id")).strip() or _safe_str(task.get("task_id")).strip()
    operation_status = _safe_str(operation.get("status")).strip().lower()
    if not mission_id or not operation_id or operation_status not in {"succeeded", "failed"}:
        return None

    trace_id = _safe_str(operation.get("trace_id")).strip()
    run_id = _safe_str(operation.get("run_id")).strip()
    artifact_dir = _safe_str(operation.get("artifact_dir")).strip()
    capability = _safe_str(operation.get("name")).strip()
    operation_meta = operation.get("meta") if isinstance(operation.get("meta"), dict) else {}
    approval_id = _safe_str(operation_meta.get("approval_id")).strip() or _operation_approval_id(task)
    approval_status = _approval_status(approval_id)
    operation_error = redact_operation_optional_text(operation.get("error"))
    result_message = redact_operation_optional_text(operation_meta.get("result_message"))
    recovery_next_step = "review_operation_detail" if operation_status == "failed" else ""
    meta = {
        "domain": "operations",
        "scope": "mission.loop",
        "mission_id": mission_id,
        "operation_id": operation_id,
        "trace_id": trace_id or None,
        "approval_id": approval_id or None,
        "approval_status": approval_status or None,
        "handoff_approval_id": approval_id or None,
        "handoff_approval_status": approval_status or None,
        "current_task_approval_id": approval_id or None,
        "current_task_approval_status": approval_status or None,
        "run_id": run_id or None,
        "artifact_dir": artifact_dir or None,
        "operation_status": operation_status,
        "operation_error": operation_error or None,
        "result_message": result_message or None,
        "recovery_next_step": recovery_next_step or None,
        "capability": capability or None,
        "subsystem": "operations.runtime",
    }
    if operation_status == "succeeded":
        meta.update(
            {
                "active_stage": "interface",
                "handoff_stage": "interface",
                "handoff_action": "review_result",
                "handoff_gate": "operator_review",
                "handoff_operation_id": operation_id,
                "handoff_trace_id": trace_id or None,
                "handoff_run_id": run_id or None,
                "handoff_artifact_dir": artifact_dir or None,
                "handoff_next_step": "review_completed_mission",
                "current_task_source": "terminal_operation_receipt",
                "current_task_operation_id": operation_id,
                "current_task_gate": "operator_review",
                "current_task_trace_id": trace_id or None,
                "current_task_run_id": run_id or None,
                "current_task_artifact_dir": artifact_dir or None,
                "current_task_next_step": "review_completed_mission",
                "memory_receipt_count": 1,
            }
        )
    elif operation_status == "failed":
        meta.update(
            {
                "active_stage": "deadletter",
                "handoff_stage": "deadletter",
                "handoff_action": "retry_or_deadletter",
                "handoff_operation_id": operation_id,
                "handoff_trace_id": trace_id or None,
                "handoff_run_id": run_id or None,
                "handoff_artifact_dir": artifact_dir or None,
                "handoff_next_step": recovery_next_step or "review_operation_detail",
                "current_task_source": "terminal_operation_receipt",
                "current_task_operation_id": operation_id,
                "current_task_trace_id": trace_id or None,
                "current_task_run_id": run_id or None,
                "current_task_artifact_dir": artifact_dir or None,
                "current_task_next_step": recovery_next_step or "review_operation_detail",
                "memory_receipt_count": 1,
            }
        )
    meta.update(_operation_plan_receipt_meta(operation))
    outcome = "completed" if operation_status == "succeeded" else "failed"
    entry = append_continuity_ledger(
        "system",
        f"Mission operation {outcome}: mission={mission_id} operation={operation_id} status={operation_status}",
        {key: value for key, value in meta.items() if value is not None},
    )
    return _memory_receipt_projection(entry)


def operation_memory_receipt_summary(
    task: dict[str, Any],
    operation: dict[str, Any] | None = None,
    *,
    per_operation_limit: int = 5,
) -> dict[str, Any]:
    operation_payload = operation if isinstance(operation, dict) else {}
    operation_id = _safe_str(operation_payload.get("id")).strip() or _safe_str(task.get("task_id")).strip()
    mission_id = _task_mission_id(task)
    receipts = operation_memory_receipts(
        operation_id,
        mission_id=mission_id,
        per_operation_limit=per_operation_limit,
    )
    return {
        "memory_receipts": receipts,
        "memory_receipt_count": len(receipts),
        "latest_memory_receipt": dict(receipts[0]) if receipts else {},
    }


def attach_operation_memory_receipt_summary(
    operation: dict[str, Any],
    receipt_summary: dict[str, Any],
) -> dict[str, Any]:
    if int(receipt_summary.get("memory_receipt_count") or 0) <= 0:
        return operation
    updated = dict(operation)
    meta = dict(updated.get("meta") or {}) if isinstance(updated.get("meta"), dict) else {}
    meta["memory_receipt_count"] = int(receipt_summary.get("memory_receipt_count") or 0)
    latest = receipt_summary.get("latest_memory_receipt")
    if isinstance(latest, dict) and latest:
        meta["latest_memory_receipt"] = dict(latest)
    updated["meta"] = meta
    return updated


def _event_to_operation(task_id: str, idx: int, event: dict[str, Any]) -> dict[str, Any]:
    ts = _parse_iso_to_unix(event.get("ts")) or int(datetime.now(UTC).timestamp())
    event_name = _safe_str(event.get("event")).strip() or "event"
    raw_details = event.get("details") if isinstance(event.get("details"), dict) else {}
    details = redact_operation_value(raw_details)
    details = details if isinstance(details, dict) else {}
    status = "unknown"
    level = "info"
    if event_name == "created":
        status = _to_operation_status(details.get("status"))
    elif event_name == "status_updated":
        status = _to_operation_status(details.get("to"))
        if status in {"failed", "blocked"}:
            level = "error"
    elif event_name == "governance_hold":
        held_status = _safe_str(details.get("status")).strip().lower()
        status = "blocked" if held_status in {"blocked", "denied"} else "queued"
        level = "warning"
    trace_id = _safe_str(details.get("trace_id")).strip()
    run_id = _safe_str(details.get("run_id")).strip()
    artifact_dir = _safe_str(details.get("artifact_dir")).strip()
    return {
        "id": f"{task_id}:evt:{idx}",
        "ts": ts,
        "kind": "audit_event",
        "name": event_name,
        "status": status,
        "level": level,
        "actor": "system",
        "trace_id": trace_id or None,
        "run_id": run_id or None,
        "artifact_dir": artifact_dir or None,
        "output": details or event.get("details"),
        "meta": {
            "task_id": task_id,
            "reason": redact_operation_optional_text(details.get("reason")),
            "gate": details.get("gate"),
            "next_step": redact_operation_optional_text(details.get("next_step")),
            "trace_id": trace_id or None,
            "run_id": run_id or None,
            "artifact_dir": artifact_dir or None,
            "orb_plane": "P3_GOVERNANCE" if event_name == "governance_hold" else None,
        },
    }


def operation_logs(operation_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
    op_id = _safe_str(operation_id).strip()
    if not _validate_operation_id(op_id):
        return []
    events = delegation_store.read_audit(op_id, limit=limit)
    out: list[dict[str, Any]] = []
    for idx, event in enumerate(events):
        if isinstance(event, dict):
            out.append(_event_to_operation(op_id, idx, event))
    return out


def get_operation_detail(
    operation_id: str,
    *,
    include_logs: bool = True,
    log_limit: int = 200,
) -> dict[str, object]:
    op_id = _safe_str(operation_id).strip()
    if not _validate_operation_id(op_id):
        return {"ok": False, "error": "invalid_operation_id"}

    task = _load_task(op_id)
    if not isinstance(task, dict):
        return {"ok": False, "error": "not_found"}

    operation = _task_to_operation(task)
    receipt_summary = operation_memory_receipt_summary(task, operation)
    operation = attach_operation_memory_receipt_summary(operation, receipt_summary)
    payload: dict[str, object] = {
        "ok": True,
        "operation": operation,
        "meta": {"task": redact_operation_task(task)},
        **receipt_summary,
    }
    payload["logs"] = operation_logs(op_id, limit=log_limit) if include_logs else []
    return payload


def _validate_operation_id(operation_id: str) -> bool:
    if not operation_id:
        return False
    if operation_id.startswith("tsk_"):
        return True
    return bool(_TASK_ID_RE.match(operation_id))


def _allowed_capabilities() -> list[str]:
    try:
        agent_executor._register_capabilities()
    except Exception:
        return sorted(set(_ACTION_TO_CAPABILITY.values()))
    if not isinstance(agent_executor.CAPABILITY_ALLOWLIST, dict):
        return sorted(set(_ACTION_TO_CAPABILITY.values()))
    return sorted(str(key) for key in agent_executor.CAPABILITY_ALLOWLIST.keys())


def _resolve_capability(action: str, explicit: str | None) -> str:
    allowed = set(_allowed_capabilities())
    if explicit and explicit.strip():
        candidate = explicit.strip()
        if candidate in allowed:
            return candidate
        return ""

    raw_action = action.strip()
    if not raw_action:
        return ""
    if raw_action in allowed:
        return raw_action
    mapped = _ACTION_TO_CAPABILITY.get(raw_action)
    if mapped and mapped in allowed:
        return mapped
    return ""


def create_operation(
    *,
    action: str,
    reason: str = "requested",
    domain: str | None = None,
    actor: str | None = None,
    mission_id: str | None = None,
    idempotency_key: str | None = None,
    input: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    capability: str | None = None,
    objective: str | None = None,
    priority: int = 5,
    ttl_sec: int = 3600,
) -> dict[str, object]:
    capability_name = _resolve_capability(action, capability)
    if not capability_name:
        return {
            "ok": False,
            "error": "unsupported_action",
            "message": "Action could not be mapped to an allowed capability.",
            "supported_actions": _allowed_capabilities(),
        }

    requester_id = _safe_str(actor).strip() or "api"
    effective_objective = redact_operation_text(objective or reason or action)
    mission_ref = _safe_str(mission_id).strip()

    if mission_ref:
        linked_mission, mission_err = mission_store.read_mission(mission_ref)
        if not linked_mission:
            return {"ok": False, "error": mission_err or "invalid_mission_id"}

    inputs = dict(input or {})
    if domain and "domain" not in inputs:
        inputs["domain"] = domain
    if idempotency_key and "idempotency_key" not in inputs:
        inputs["idempotency_key"] = idempotency_key
    existing_meta = inputs.get("meta")
    merged_meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    if meta:
        merged_meta.update(redact_operation_metadata(meta))
    if mission_ref:
        inputs["mission_id"] = mission_ref
        merged_meta["mission_id"] = mission_ref
    if merged_meta:
        inputs["meta"] = merged_meta
    else:
        inputs.pop("meta", None)

    record, err = delegation_store.create_delegation(
        DelegationRequest(
            requester_id=requester_id,
            capability=capability_name,
            objective=effective_objective,
            inputs=inputs,
            priority=max(1, min(int(priority), 9)),
            ttl_sec=max(1, min(int(ttl_sec), 7 * 24 * 3600)),
        )
    )
    if not record:
        return {"ok": False, "error": err or "create_failed"}

    mission_linked = True
    mission_link_error = ""
    if mission_ref:
        _, mission_link_err = mission_store.link_task(
            mission_ref,
            record.task_id,
            actor=requester_id,
            note="operation_created",
        )
        if mission_link_err:
            mission_linked = False
            mission_link_error = mission_link_err

    operation = _task_to_operation(record.to_json_dict())
    return {
        "ok": mission_linked,
        "operation_id": record.task_id,
        "status": operation.get("status", "queued"),
        "operation": operation,
        "message": "created" if mission_linked else "created_with_mission_link_error",
        "mission_id": mission_ref or None,
        "mission_linked": mission_linked,
        "mission_link_error": mission_link_error or None,
    }


def run_operation(operation_id: str, *, worker_id: str = "api.operations") -> dict[str, object]:
    op_id = _safe_str(operation_id).strip()
    if not _validate_operation_id(op_id):
        return {"ok": False, "error": "invalid_operation_id"}

    task = _load_task(op_id)
    if not isinstance(task, dict):
        return {"ok": False, "error": "not_found"}
    if (
        _normalize_internal_status(task.get("status")) in _TERMINAL_STATUSES
        and _result_status(task) not in _RETRYABLE_GOVERNANCE_STATUSES
    ):
        operation = _task_to_operation(task)
        return {
            "ok": _operation_request_ok(operation.get("status")),
            "status": operation.get("status", "unknown"),
            "operation": operation,
            "message": "already_terminal",
        }
    if _normalize_internal_status(task.get("status")) in _TERMINAL_STATUSES:
        task = _hold_retryable_governance_task(op_id, task)

    assigned_worker_id = _safe_str(worker_id).strip() or "api.operations"
    if not agent_executor._try_acquire_lock(op_id, assigned_worker_id):
        return {"ok": False, "error": "locked", "status": "running"}
    try:
        updated = agent_executor.execute_task(task_id=op_id, worker_id=assigned_worker_id)
    finally:
        agent_executor._release_lock(op_id)

    if isinstance(updated, dict):
        updated = _hold_retryable_governance_task(op_id, updated)
    operation = _task_to_operation(updated)
    memory_receipt = None
    if isinstance(updated, dict):
        memory_receipt = _append_terminal_mission_operation_receipt(updated, operation)
    response: dict[str, object] = {
        "ok": _operation_request_ok(operation.get("status")),
        "status": operation.get("status", "unknown"),
        "operation": operation,
    }
    if memory_receipt:
        receipt_summary = operation_memory_receipt_summary(updated, operation, per_operation_limit=1)
        if int(receipt_summary.get("memory_receipt_count") or 0) <= 0:
            receipt_summary = {
                "memory_receipts": [memory_receipt],
                "memory_receipt_count": 1,
                "latest_memory_receipt": memory_receipt,
            }
        operation = attach_operation_memory_receipt_summary(
            operation,
            receipt_summary,
        )
        response["operation"] = operation
        response["memory_receipt"] = memory_receipt
    return response
