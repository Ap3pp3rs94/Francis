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
from francis.kernel.paths import data_dir
from francis.missions import store as mission_store

logger = logging.getLogger(__name__)

_TASK_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{6,128}$")
_TERMINAL_STATUSES = {"complete", "completed", "failed", "canceled", "cancelled"}
_RETRYABLE_GOVERNANCE_STATUSES = {"pending", "needs_approval", "blocked", "denied"}

_ACTION_TO_CAPABILITY: dict[str, str] = {
    "chat.summarize": "chat.summarize",
    "plan.create": "plan.create",
    "plan.revise": "plan.revise",
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
    updated["status_reason"] = (
        _safe_str(payload.get("error")).strip()
        or _safe_str(payload.get("message")).strip()
        or result_status
        or _safe_str(task.get("status_reason")).strip()
        or None
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
                "next_step": _safe_str(governance.get("next_step")).strip() or None,
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
    output = result_obj.get("data")
    result_status = _result_status(task)
    governance = _result_governance(task)
    approval_id = _result_approval_id(task)
    error = _safe_str(task.get("status_reason")).strip() or None
    if not error:
        error = _safe_str((result_obj.get("data") or {}).get("error") if isinstance(result_obj.get("data"), dict) else "")
        error = error or None
    result_message = _safe_str((result_obj.get("data") or {}).get("message") if isinstance(result_obj.get("data"), dict) else "")
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
        "duration_ms": None,
        "input": task.get("inputs"),
        "output": output,
        "error": error,
        "tags": task.get("tags") if isinstance(task.get("tags"), list) else None,
        "meta": {
            "raw_status": raw_status,
            "objective": task.get("objective"),
            "priority": task.get("priority"),
            "ttl_sec": task.get("ttl_sec"),
            "assigned_to": task.get("assigned_to"),
            "attempts": task.get("attempts"),
            "created_at": created_at,
            "updated_at": updated_at,
            "result_status": result_status or None,
            "result_message": result_message or None,
            "approval_id": approval_id or None,
            "mission_id": mission_id or None,
            "governance": governance or None,
            "orb_plane": orb_plane,
        },
    }


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
    effective_objective = _safe_str(objective).strip() or _safe_str(reason).strip() or action.strip()
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
        merged_meta.update(meta)
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
    if _normalize_internal_status(task.get("status")) in _TERMINAL_STATUSES and _result_status(task) not in _RETRYABLE_GOVERNANCE_STATUSES:
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
    return {
        "ok": _operation_request_ok(operation.get("status")),
        "status": operation.get("status", "unknown"),
        "operation": operation,
    }
