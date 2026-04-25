from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from francis.agent import delegation as delegation_store
from francis.agent import executor as agent_executor
from francis.api.routes._operator_posture import posture_write_guard
from francis.governance.operation_redaction import (
    redact_operation_metadata,
    redact_operation_optional_text,
    redact_operation_task,
    redact_operation_text,
    redact_operation_value,
)
from francis.kernel.paths import data_dir
from francis.missions import store as mission_store
from francis.operations import runtime as operations_runtime
from francis.workers.runner import run_workers

router = APIRouter()
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


class OperationCreateIn(BaseModel):
    action: str
    reason: str = "requested"
    domain: str | None = None
    actor: str | None = None
    mission_id: str | None = None
    idempotency_key: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)

    capability: str | None = None
    objective: str | None = None
    priority: int = 5
    ttl_sec: int = 3600


class OperationPatchIn(BaseModel):
    status: str | None = None
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None
    note: str | None = None


class OperationCancelIn(BaseModel):
    reason: str = "cancelled_by_operator"


class OperationDeleteIn(BaseModel):
    reason: str = "deleted_by_operator"


class OperationGetManyIn(BaseModel):
    ids: list[str] = Field(default_factory=list)


class OperationRunIn(BaseModel):
    worker_id: str = "api.operations"


class WorkerRunOnceIn(BaseModel):
    queue: str = "default"
    kind: str = "default"
    concurrency: int = 4
    heartbeat_s: float = 10.0
    profile: str = "dev"
    run_mode: str = "api"
    log_level: str = "INFO"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _execution_posture_guard(action_label: str) -> str:
    return posture_write_guard(
        action_label,
        verification_prefix="Execution is blocked until operator posture can be verified",
        observe_message="Observe mode keeps execution read-only.",
        writes_blocked_message="Current operator posture blocks writes.",
    )


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
    approval_id = _result_approval_id(task)

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
            actor="api.operations",
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
    )
    result_status = _result_status(task)
    governance = _result_governance(task)
    approval_id = _result_approval_id(task)
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
            "mission_id": mission_id or None,
            "governance": redact_operation_value(governance) if governance else None,
            "orb_plane": orb_plane,
        },
    }


def _event_to_operation(task_id: str, idx: int, event: dict[str, Any]) -> dict[str, Any]:
    ts = _parse_iso_to_unix(event.get("ts")) or int(datetime.now(UTC).timestamp())
    event_name = _safe_str(event.get("event")).strip() or "event"
    raw_details = event.get("details") if isinstance(event.get("details"), dict) else {}
    details = redact_operation_value(raw_details)
    details = details if isinstance(details, dict) else {}
    status = "unknown"
    level = "info"
    if event_name == "status_updated":
        status = _to_operation_status(details.get("to"))
        if status in {"failed", "blocked"}:
            level = "error"
    elif event_name == "governance_hold":
        held_status = _safe_str(details.get("status")).strip().lower()
        status = "blocked" if held_status in {"blocked", "denied"} else "queued"
        level = "warning"
    return {
        "id": f"{task_id}:evt:{idx}",
        "ts": ts,
        "kind": "audit_event",
        "name": event_name,
        "status": status,
        "level": level,
        "actor": "system",
        "output": details or event.get("details"),
        "meta": {
            "task_id": task_id,
            "reason": redact_operation_optional_text(details.get("reason")),
            "gate": details.get("gate"),
            "next_step": redact_operation_optional_text(details.get("next_step")),
            "orb_plane": "P3_GOVERNANCE" if event_name == "governance_hold" else None,
        },
    }


def _task_events(task_id: str, limit: int = 200) -> list[dict[str, Any]]:
    events = delegation_store.read_audit(task_id, limit=limit)
    out: list[dict[str, Any]] = []
    for idx, event in enumerate(events):
        if isinstance(event, dict):
            out.append(_event_to_operation(task_id, idx, event))
    return out


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


def _query_operations(
    *,
    limit: int,
    offset: int,
    status: str | None,
    kind: str | None,
    actor: str | None,
    search: str | None,
    start_ts: int | None,
    end_ts: int | None,
    capability: str | None,
) -> tuple[list[dict[str, Any]], int]:
    status_filter = _safe_str(status).strip().lower()
    kind_filter = _safe_str(kind).strip().lower()
    actor_filter = _safe_str(actor).strip().lower()
    search_filter = _safe_str(search).strip().lower()
    capability_filter = _safe_str(capability).strip().lower()

    items: list[dict[str, Any]] = []
    task_ids = delegation_store.list_tasks(limit=max(offset + limit + 200, 50_000))
    for task_id in task_ids:
        task = _load_task(task_id)
        if not isinstance(task, dict):
            continue
        op = _task_to_operation(task)

        if status_filter and _safe_str(op.get("status")).lower() != status_filter:
            if _normalize_internal_status((op.get("meta") or {}).get("raw_status")) != status_filter:
                continue
        if kind_filter and _safe_str(op.get("kind")).lower() != kind_filter:
            continue
        if actor_filter and _safe_str(op.get("actor")).lower() != actor_filter:
            continue
        if capability_filter and _safe_str(op.get("name")).lower() != capability_filter:
            continue

        ts = int(op.get("ts") or 0)
        if start_ts is not None and ts < start_ts:
            continue
        if end_ts is not None and ts > end_ts:
            continue

        if search_filter:
            haystack = " ".join(
                [
                    _safe_str(op.get("id")),
                    _safe_str(op.get("name")),
                    _safe_str((op.get("meta") or {}).get("objective")),
                    _safe_str(op.get("error")),
                    json.dumps(op.get("input"), ensure_ascii=False, default=str),
                    json.dumps(op.get("output"), ensure_ascii=False, default=str),
                ]
            ).lower()
            if search_filter not in haystack:
                continue

        items.append(op)

    items.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
    total = len(items)
    return items[offset : offset + limit], total


@router.get("/status")
def status() -> dict[str, object]:
    try:
        items, total = _query_operations(
            limit=10_000,
            offset=0,
            status=None,
            kind=None,
            actor=None,
            search=None,
            start_ts=None,
            end_ts=None,
            capability=None,
        )
        counts: dict[str, int] = {}
        for item in items:
            key = _safe_str(item.get("status")) or "unknown"
            counts[key] = counts.get(key, 0) + 1
        return {
            "ok": True,
            "route": "operations",
            "status": "ready",
            "total": total,
            "counts": counts,
            "capabilities": _allowed_capabilities(),
        }
    except Exception as exc:
        return {"ok": False, "route": "operations", "status": "error", "error": str(exc)}


@router.get("/list")
def list_operations(
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    kind: str | None = None,
    actor: str | None = None,
    search: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    capability: str | None = None,
) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(limit), 5000))
        safe_offset = max(0, int(offset))
        items, total = _query_operations(
            limit=safe_limit,
            offset=safe_offset,
            status=status,
            kind=kind,
            actor=actor,
            search=search,
            start_ts=start_ts,
            end_ts=end_ts,
            capability=capability,
        )
        return {"items": items, "total": total, "offset": safe_offset, "limit": safe_limit}
    except Exception as exc:
        return {"items": [], "total": 0, "offset": 0, "limit": 0, "error": str(exc)}


@router.post("/get_many")
def get_many_operations(payload: OperationGetManyIn) -> dict[str, object]:
    try:
        details: list[dict[str, Any]] = []
        for operation_id in payload.ids:
            op_id = _safe_str(operation_id).strip()
            if not _validate_operation_id(op_id):
                details.append(
                    {
                        "operation": {
                            "id": op_id or "unknown",
                            "ts": int(datetime.now(UTC).timestamp()),
                            "status": "unknown",
                            "kind": "delegated_task",
                        },
                        "meta": {"error": "invalid_operation_id"},
                    }
                )
                continue

            task = _load_task(op_id)
            if not isinstance(task, dict):
                details.append(
                    {
                        "operation": {
                            "id": op_id,
                            "ts": int(datetime.now(UTC).timestamp()),
                            "status": "unknown",
                            "kind": "delegated_task",
                        },
                        "meta": {"error": "not_found"},
                    }
                )
                continue

            details.append(
                {
                    "operation": _task_to_operation(task),
                    "logs": _task_events(op_id),
                    "meta": {"task": redact_operation_task(task)},
                }
            )

        return {"items": details}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


@router.post("/create")
def create_operation(payload: OperationCreateIn) -> dict[str, object]:
    blocked_reason = posture_write_guard("declaring an operation")
    if blocked_reason:
        return {"ok": False, "error": blocked_reason, "status": "blocked"}
    try:
        return operations_runtime.create_operation(
            action=payload.action,
            reason=payload.reason,
            domain=payload.domain,
            actor=payload.actor,
            mission_id=payload.mission_id,
            idempotency_key=payload.idempotency_key,
            input=dict(payload.input or {}),
            meta=dict(payload.meta or {}),
            capability=payload.capability,
            objective=payload.objective,
            priority=payload.priority,
            ttl_sec=payload.ttl_sec,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/run-once")
def run_workers_once(payload: WorkerRunOnceIn) -> dict[str, object]:
    blocked_reason = _execution_posture_guard("running a worker cycle")
    if blocked_reason:
        return {"ok": False, "exit_code": 1, "error": blocked_reason, "status": "blocked"}
    try:
        exit_code = int(
            run_workers(
                concurrency=max(1, min(int(payload.concurrency), 256)),
                queue=payload.queue.strip() or "default",
                kind=payload.kind.strip() or "default",
                heartbeat_s=max(0.1, float(payload.heartbeat_s)),
                run_once=True,
                env_profile=payload.profile.strip() or "dev",
                run_mode=payload.run_mode.strip() or "api",
                log_level=payload.log_level.strip() or "INFO",
            )
        )
        return {"ok": exit_code == 0, "exit_code": exit_code}
    except Exception as exc:
        return {"ok": False, "exit_code": 1, "error": str(exc)}


@router.get("/export")
def export_operations(
    format: str = "json",
    status: str | None = None,
    kind: str | None = None,
    actor: str | None = None,
    search: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    capability: str | None = None,
) -> PlainTextResponse:
    items, _ = _query_operations(
        limit=10_000,
        offset=0,
        status=status,
        kind=kind,
        actor=actor,
        search=search,
        start_ts=start_ts,
        end_ts=end_ts,
        capability=capability,
    )

    fmt = _safe_str(format).strip().lower() or "json"
    if fmt == "jsonl":
        content = "\n".join(json.dumps(item, ensure_ascii=False, default=str) for item in items)
        return PlainTextResponse(content=content, media_type="application/jsonl")

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["id", "ts", "status", "kind", "name", "actor", "duration_ms", "error"],
        )
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "id": item.get("id"),
                    "ts": item.get("ts"),
                    "status": item.get("status"),
                    "kind": item.get("kind"),
                    "name": item.get("name"),
                    "actor": item.get("actor"),
                    "duration_ms": item.get("duration_ms"),
                    "error": item.get("error"),
                }
            )
        return PlainTextResponse(content=output.getvalue(), media_type="text/csv")

    content = json.dumps({"items": items}, indent=2, ensure_ascii=False, default=str)
    return PlainTextResponse(content=content, media_type="application/json")


@router.get("/{operation_id}")
def get_operation(operation_id: str) -> dict[str, object]:
    try:
        op_id = _safe_str(operation_id).strip()
        if not _validate_operation_id(op_id):
            return {"ok": False, "error": "invalid_operation_id"}

        task = _load_task(op_id)
        if not isinstance(task, dict):
            return {"ok": False, "error": "not_found"}

        return {
            "operation": _task_to_operation(task),
            "logs": _task_events(op_id),
            "meta": {"task": redact_operation_task(task)},
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.patch("/{operation_id}")
def patch_operation(operation_id: str, payload: OperationPatchIn) -> dict[str, object]:
    try:
        op_id = _safe_str(operation_id).strip()
        if not _validate_operation_id(op_id):
            return {"ok": False, "error": "invalid_operation_id"}

        status_patch = _normalize_internal_status(payload.status) if payload.status else ""
        if status_patch == "cancelled":
            ok, err = delegation_store.cancel_delegation(op_id, reason=payload.note or "cancelled_by_patch")
            task = _load_task(op_id)
            operation = _task_to_operation(task) if isinstance(task, dict) else {"id": op_id, "status": "unknown"}
            return {
                "ok": ok,
                "operation": operation,
                "status": operation.get("status", "unknown"),
                "message": err if not ok else "cancelled",
            }
        if status_patch and status_patch not in {"pending", "accepted", "running", "completed", "failed"}:
            return {"ok": False, "error": "unsupported_status_patch"}

        path = _record_path(op_id)
        task = _load_task(op_id)
        if not isinstance(task, dict):
            return {"ok": False, "error": "not_found"}

        if payload.tags is not None:
            task["tags"] = [str(tag) for tag in payload.tags if _safe_str(tag).strip()]
        if payload.meta is not None:
            existing_meta = task.get("meta")
            if isinstance(existing_meta, dict):
                merged = dict(existing_meta)
                merged.update(payload.meta)
                task["meta"] = redact_operation_metadata(merged)
            else:
                task["meta"] = redact_operation_metadata(payload.meta)
        if payload.note:
            existing_meta = task.get("meta")
            if not isinstance(existing_meta, dict):
                existing_meta = {}
            existing_meta["note"] = redact_operation_text(payload.note)
            task["meta"] = redact_operation_metadata(existing_meta)

        task["updated_at"] = _now_iso()
        _write_json(path, task)
        operation = _task_to_operation(task)
        return {"ok": True, "operation": operation, "status": operation.get("status", "unknown")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/{operation_id}/cancel")
def cancel_operation(operation_id: str, payload: OperationCancelIn) -> dict[str, object]:
    try:
        op_id = _safe_str(operation_id).strip()
        if not _validate_operation_id(op_id):
            return {"ok": False, "error": "invalid_operation_id"}

        ok, err = delegation_store.cancel_delegation(op_id, reason=payload.reason)
        task = _load_task(op_id)
        operation = _task_to_operation(task) if isinstance(task, dict) else {"id": op_id, "status": "unknown"}
        return {
            "ok": ok,
            "status": operation.get("status", "unknown"),
            "operation": operation,
            "message": err if not ok else "cancelled",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/{operation_id}/run")
def run_operation(operation_id: str, payload: OperationRunIn) -> dict[str, object]:
    blocked_reason = _execution_posture_guard("running queued work")
    if blocked_reason:
        detail = operations_runtime.get_operation_detail(operation_id, include_logs=False)
        operation = (
            detail.get("operation") if isinstance(detail, dict) and isinstance(detail.get("operation"), dict) else None
        )
        status = _safe_str(operation.get("status") if isinstance(operation, dict) else "").strip() or "blocked"
        return {
            "ok": False,
            "status": status,
            "message": blocked_reason,
            "operation": operation,
        }
    try:
        return operations_runtime.run_operation(operation_id, worker_id=payload.worker_id)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.delete("/{operation_id}")
def delete_operation(operation_id: str, payload: OperationDeleteIn) -> dict[str, object]:
    try:
        op_id = _safe_str(operation_id).strip()
        if not _validate_operation_id(op_id):
            return {"ok": False, "error": "invalid_operation_id"}

        ok, err = delegation_store.cancel_delegation(op_id, reason=payload.reason)
        task = _load_task(op_id)
        operation = _task_to_operation(task) if isinstance(task, dict) else {"id": op_id, "status": "unknown"}
        return {
            "ok": ok,
            "status": operation.get("status", "unknown"),
            "operation": operation,
            "message": err if not ok else "deleted",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
