from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_display_value
from francis.kernel.paths import data_dir


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        text = _safe_str(value).strip()
        if text:
            return text
    return ""


def _safe_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    result = _as_dict(task.get("result"))
    return _as_dict(result.get("data"))


def _task_inputs(task: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(task.get("inputs"))


def _approval_task_match(task: dict[str, Any], approval_id: str) -> bool:
    if not approval_id:
        return False
    inputs = _task_inputs(task)
    input_meta = _as_dict(inputs.get("meta"))
    payload = _task_payload(task)
    candidates = (
        inputs.get("approval_id"),
        input_meta.get("approval_id"),
        payload.get("approval_id"),
    )
    return any(_safe_str(candidate).strip() == approval_id for candidate in candidates)


def _task_handle_from_metadata(task: dict[str, Any], *keys: str) -> str:
    task_meta = _as_dict(task.get("meta"))
    inputs = _task_inputs(task)
    input_meta = _as_dict(inputs.get("meta"))
    for source in (task_meta, input_meta):
        for key in keys:
            value = _safe_str(source.get(key)).strip()
            if value:
                return value
    return ""


def approval_task_record(
    approval_id: str,
    *,
    task_root: Path | None = None,
    max_records: int = 5000,
) -> dict[str, Any]:
    resolved_id = _safe_str(approval_id).strip()
    if not resolved_id:
        return {}

    tasks_base = task_root if task_root is not None else data_dir() / "tasks"
    if not tasks_base.exists():
        return {}

    candidates: list[tuple[float, Path]] = []
    try:
        paths = tasks_base.glob("*/record.json")
        for path in paths:
            try:
                candidates.append((path.stat().st_mtime, path))
            except Exception:
                candidates.append((0.0, path))
    except Exception:
        return {}

    bounded = max(1, min(int(max_records), 50_000))
    for _, path in sorted(candidates, key=lambda item: item[0], reverse=True)[:bounded]:
        record = _read_json(path)
        if record and _approval_task_match(record, resolved_id):
            return record
    return {}


def _task_operation_status(task: dict[str, Any], result_status: str) -> str:
    raw_status = _safe_str(task.get("status")).strip().lower()
    if result_status in {"blocked", "denied"}:
        return "blocked"
    if result_status in {"pending", "needs_approval"}:
        return "queued"
    if raw_status in {"pending", "accepted"}:
        return "queued"
    if raw_status == "running":
        return "running"
    if raw_status in {"complete", "completed"}:
        return "succeeded"
    if raw_status == "failed":
        return "failed"
    if raw_status in {"canceled", "cancelled"}:
        return "canceled"
    return raw_status or ""


def _task_operation_plane(task: dict[str, Any], result_status: str, governance: dict[str, Any]) -> str:
    task_meta = _as_dict(task.get("meta"))
    inputs = _task_inputs(task)
    input_meta = _as_dict(inputs.get("meta"))
    explicit_plane = _first_text(
        task_meta.get("orb_plane"),
        task_meta.get("operation_plane"),
        input_meta.get("orb_plane"),
        input_meta.get("operation_plane"),
    )
    if explicit_plane:
        return explicit_plane

    raw_status = _safe_str(task.get("status")).strip().lower()
    if governance or result_status in {"pending", "needs_approval", "blocked", "denied"}:
        return "P3_GOVERNANCE"
    if raw_status in {"pending", "accepted", "running"}:
        return "P7_EXECUTION"
    if raw_status:
        return "P9_OBSERVABILITY"
    return ""


def _task_advance_action(task: dict[str, Any]) -> str:
    task_meta = _as_dict(task.get("meta"))
    inputs = _task_inputs(task)
    input_meta = _as_dict(inputs.get("meta"))
    return _first_text(
        task_meta.get("advance_action"),
        task_meta.get("current_task_advance_action"),
        task_meta.get("last_advance_action"),
        input_meta.get("advance_action"),
        input_meta.get("current_task_advance_action"),
        input_meta.get("last_advance_action"),
    )


def _task_plan_summary(task: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    task_meta = _as_dict(task.get("meta"))
    inputs = _task_inputs(task)
    input_meta = _as_dict(inputs.get("meta"))
    payload_meta = _as_dict(payload.get("meta"))
    sources = (payload, payload_meta, task_meta, input_meta)

    out: dict[str, Any] = {}
    for key in ("plan_status", "plan_current_step_id", "plan_current_step_title"):
        value = _first_text(*(source.get(key) for source in sources))
        if value:
            out[key] = value

    for key in ("plan_step_count", "plan_checkpoint_count"):
        for source in sources:
            value = _safe_nonnegative_int(source.get(key))
            if value is not None:
                out[key] = value
                break

    return out


def approval_task_projection(approval_id: str, *, task_root: Path | None = None) -> dict[str, Any]:
    task = approval_task_record(approval_id, task_root=task_root)
    if not task:
        return {}

    inputs = _task_inputs(task)
    input_meta = _as_dict(inputs.get("meta"))
    payload = _task_payload(task)
    governance = _as_dict(payload.get("governance"))
    receipt = _as_dict(payload.get("receipt"))
    sandbox = _as_dict(payload.get("sandbox"))
    audit = _as_dict(receipt.get("audit_event"))
    sandbox_audit = _as_dict(sandbox.get("audit_event"))

    result_status = _safe_str(payload.get("status")).strip().lower()
    out: dict[str, Any] = {}

    operation_id = _safe_str(task.get("task_id")).strip()
    if operation_id:
        out["operation_id"] = operation_id

    operation_name = _safe_str(task.get("capability")).strip()
    if operation_name:
        out["operation_name"] = operation_name

    mission_id = _first_text(inputs.get("mission_id"), input_meta.get("mission_id"))
    if mission_id:
        out["mission_id"] = mission_id

    operation_status = _task_operation_status(task, result_status)
    if operation_status:
        out["operation_status"] = operation_status
    if result_status:
        out["operation_result_status"] = result_status

    gate = _safe_str(governance.get("gate")).strip()
    if gate:
        out["gate"] = gate

    operation_plane = _task_operation_plane(task, result_status, governance)
    if operation_plane:
        out["operation_plane"] = operation_plane

    advance_action = _task_advance_action(task)
    if advance_action:
        out["advance_action"] = advance_action

    next_step = redact_governed_display_value(governance.get("next_step"))
    next_step_text = _safe_str(next_step).strip()
    if next_step_text:
        out["next_step"] = next_step_text

    trace_id = _first_text(
        payload.get("trace_id"),
        payload.get("traceId"),
        receipt.get("trace_id"),
        sandbox.get("trace_id"),
        audit.get("trace_id"),
        sandbox_audit.get("trace_id"),
        _task_handle_from_metadata(task, "trace_id", "traceId"),
    )
    if trace_id:
        out["trace_id"] = trace_id

    run_id = _first_text(
        payload.get("run_id"),
        payload.get("runId"),
        receipt.get("run_id"),
        sandbox.get("run_id"),
        audit.get("run_id"),
        sandbox_audit.get("run_id"),
        _task_handle_from_metadata(task, "run_id", "runId"),
    )
    if run_id:
        out["run_id"] = run_id

    artifact_dir = _first_text(
        payload.get("artifact_dir"),
        payload.get("artifact_path"),
        receipt.get("artifact_dir"),
        receipt.get("artifact_path"),
        sandbox.get("artifact_dir"),
        sandbox.get("artifact_path"),
        audit.get("artifact_dir"),
        sandbox_audit.get("artifact_dir"),
        _task_handle_from_metadata(task, "artifact_dir", "artifact_path"),
    )
    if artifact_dir:
        out["artifact_dir"] = artifact_dir

    out.update(_task_plan_summary(task, payload))

    return out


def approval_payload_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    display_payload = redact_governed_display_value(payload)
    payload_root = display_payload if isinstance(display_payload, dict) else payload
    payload_obj = payload_root.get("payload") if isinstance(payload_root.get("payload"), dict) else {}
    summary_payload = payload_obj if payload_obj else payload_root

    input_obj = summary_payload.get("input") if isinstance(summary_payload.get("input"), dict) else {}
    meta_obj = summary_payload.get("meta") if isinstance(summary_payload.get("meta"), dict) else {}

    summary: dict[str, Any] = {}

    requested_action = _safe_str(summary_payload.get("action")).strip() or _safe_str(payload.get("action")).strip()
    if requested_action:
        summary["requested_action"] = requested_action

    plugin_id = _safe_str(summary_payload.get("plugin_id")).strip() or _safe_str(payload.get("plugin_id")).strip()
    if plugin_id:
        summary["plugin_id"] = plugin_id

    scope_id = _safe_str(summary_payload.get("scope_id")).strip() or _safe_str(payload.get("scope_id")).strip()
    if scope_id:
        summary["scope_id"] = scope_id

    provider = _safe_str(summary_payload.get("provider")).strip() or _safe_str(payload.get("provider")).strip()
    if provider:
        summary["provider"] = provider

    credential_type = _safe_str(summary_payload.get("type")).strip() or _safe_str(payload.get("type")).strip()
    if credential_type:
        summary["credential_type"] = credential_type

    label = _safe_str(summary_payload.get("label")).strip() or _safe_str(payload.get("label")).strip()
    if label:
        summary["label"] = label

    credential_id = (
        _safe_str(summary_payload.get("credential_id")).strip()
        or _safe_str(summary_payload.get("id")).strip()
        or _safe_str(payload.get("credential_id")).strip()
        or _safe_str(payload.get("id")).strip()
    )
    if credential_id:
        summary["credential_id"] = credential_id

    target_kind = _safe_str(summary_payload.get("target_kind")).strip()
    if target_kind:
        summary["target_kind"] = target_kind

    target_id = _safe_str(summary_payload.get("target_id")).strip()
    if target_id:
        summary["target_id"] = target_id

    twin_id = _safe_str(summary_payload.get("twin_id")).strip()
    if twin_id:
        summary["twin_id"] = twin_id

    url = _safe_str(summary_payload.get("url")).strip()
    if url:
        summary["url"] = url

    domain = _safe_str(summary_payload.get("domain")).strip()
    if domain:
        summary["domain"] = domain

    actor = _safe_str(summary_payload.get("actor")).strip()
    if actor:
        summary["actor"] = actor

    risk = _safe_str(summary_payload.get("risk")).strip().lower()
    if risk:
        summary["risk"] = risk

    enabled = summary_payload.get("enabled")
    if isinstance(enabled, bool):
        summary["enabled"] = enabled

    dry_run = summary_payload.get("dry_run")
    if isinstance(dry_run, bool):
        summary["dry_run"] = dry_run

    risk_tier = (
        _safe_str(summary_payload.get("risk_tier")).strip().lower()
        or _safe_str(payload.get("risk_tier")).strip().lower()
    )
    if risk_tier:
        summary["risk_tier"] = risk_tier

    required_trust_raw = summary_payload.get("required_trust")
    if required_trust_raw is None:
        required_trust_raw = payload.get("required_trust")
    if isinstance(required_trust_raw, bool):
        summary["required_trust"] = int(required_trust_raw)
    elif isinstance(required_trust_raw, int):
        summary["required_trust"] = required_trust_raw
    elif isinstance(required_trust_raw, float):
        summary["required_trust"] = int(required_trust_raw)
    elif isinstance(required_trust_raw, str):
        text = required_trust_raw.strip()
        if text:
            try:
                summary["required_trust"] = int(float(text))
            except Exception:
                pass

    payload_keys = sorted(_safe_str(key).strip() for key in summary_payload.keys() if _safe_str(key).strip())
    if payload_keys:
        summary["payload_keys"] = payload_keys[:8]

    input_keys = sorted(_safe_str(key).strip() for key in input_obj.keys() if _safe_str(key).strip())
    if input_keys:
        summary["input_keys"] = input_keys[:8]

    meta_keys = sorted(_safe_str(key).strip() for key in meta_obj.keys() if _safe_str(key).strip())
    if meta_keys:
        summary["meta_keys"] = meta_keys[:8]

    params_obj = summary_payload.get("params") if isinstance(summary_payload.get("params"), dict) else {}
    params_keys = sorted(_safe_str(key).strip() for key in params_obj.keys() if _safe_str(key).strip())
    if params_keys:
        summary["params_keys"] = params_keys[:8]

    return summary


def approval_artifact_request(approval_id: str, *, artifact_root: Path | None = None) -> dict[str, Any]:
    resolved_id = _safe_str(approval_id).strip()
    if not resolved_id:
        return {}

    artifact_base = artifact_root if artifact_root is not None else data_dir() / "artifacts"
    candidates = [
        artifact_base / "credentials" / "approvals" / resolved_id / "request.json",
        artifact_base / "plugins" / "approvals" / resolved_id / "request.json",
        artifact_base / "web_learning" / "approvals" / resolved_id / "request.json",
        artifact_base / "industrial" / "approvals" / resolved_id / "request.json",
        artifact_base / "git_push" / resolved_id / "request.json",
        artifact_base / "supervised_exec" / resolved_id / "request.json",
    ]
    for path in candidates:
        record = _read_json(path)
        if record:
            return record
    return {}


def approval_artifact_mismatch(approval_id: str, *, artifact_root: Path | None = None) -> dict[str, Any]:
    resolved_id = _safe_str(approval_id).strip()
    if not resolved_id:
        return {}

    artifact_base = artifact_root if artifact_root is not None else data_dir() / "artifacts"
    candidates = [
        artifact_base / "credentials" / "approvals" / resolved_id / "mismatch.json",
        artifact_base / "plugins" / "approvals" / resolved_id / "mismatch.json",
        artifact_base / "web_learning" / "approvals" / resolved_id / "mismatch.json",
        artifact_base / "industrial" / "approvals" / resolved_id / "mismatch.json",
        artifact_base / "git_push" / resolved_id / "mismatch.json",
        artifact_base / "supervised_exec" / resolved_id / "mismatch.json",
    ]
    for path in candidates:
        record = _read_json(path)
        if record:
            return record
    return {}


def _changed_payload_keys(expected: Any, previous: Any) -> list[str]:
    if not isinstance(expected, dict) or not isinstance(previous, dict):
        return []

    changed: list[str] = []
    for key in sorted(set(expected.keys()) | set(previous.keys())):
        left = expected.get(key)
        right = previous.get(key)
        if json.dumps(left, sort_keys=True, default=str) != json.dumps(right, sort_keys=True, default=str):
            text = _safe_str(key).strip()
            if text:
                changed.append(text)
    return changed[:8]


def _payload_keys(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    return sorted(_safe_str(key).strip() for key in payload.keys() if _safe_str(key).strip())[:8]


def approval_projection_fields(
    record: dict[str, Any],
    *,
    artifact_root: Path | None = None,
    task_root: Path | None = None,
) -> dict[str, Any]:
    item = dict(record) if isinstance(record, dict) else {}
    approval_id = _safe_str(item.get("id")).strip()

    artifact_request = approval_artifact_request(approval_id, artifact_root=artifact_root)
    artifact_mismatch = approval_artifact_mismatch(approval_id, artifact_root=artifact_root)
    payload_summary = approval_payload_summary(item.get("payload"))
    artifact_payload = artifact_request.get("request")
    if isinstance(artifact_payload, dict):
        credential_id = _safe_str(artifact_payload.get("credential_id")).strip()
        if credential_id and "credential_id" not in payload_summary:
            payload_summary["credential_id"] = credential_id

    out: dict[str, Any] = {"payload_summary": payload_summary}

    request_kind = _safe_str(artifact_request.get("kind")).strip()
    if request_kind:
        out["request_kind"] = request_kind

    previous_approval_id = _safe_str(artifact_request.get("previous_approval_id")).strip()
    if previous_approval_id:
        out["previous_approval_id"] = previous_approval_id

    previous_status = _safe_str(artifact_request.get("previous_status")).strip()
    if previous_status:
        out["previous_approval_status"] = previous_status

    mismatch_kind = _safe_str(artifact_mismatch.get("kind")).strip()
    if mismatch_kind:
        out["replacement_kind"] = mismatch_kind
        out["replacement_reason"] = (
            "approval_payload_mismatch" if mismatch_kind.endswith(".mismatch") else mismatch_kind
        )

    expected_payload = artifact_mismatch.get("expected_payload")
    if not isinstance(expected_payload, dict) and isinstance(artifact_mismatch.get("request"), dict):
        expected_payload = artifact_mismatch.get("request")
    approval_record = (
        artifact_mismatch.get("approval_record") if isinstance(artifact_mismatch.get("approval_record"), dict) else {}
    )
    previous_payload = approval_record.get("payload") if isinstance(approval_record, dict) else {}
    expected_payload_keys = _payload_keys(expected_payload)
    previous_payload_keys = _payload_keys(previous_payload)
    if expected_payload_keys:
        out["replacement_expected_payload_keys"] = expected_payload_keys
    if previous_payload_keys:
        out["replacement_previous_payload_keys"] = previous_payload_keys
    changed_keys = _changed_payload_keys(expected_payload, previous_payload)
    if changed_keys:
        out["replacement_changed_keys"] = changed_keys

    out.update(approval_task_projection(approval_id, task_root=task_root))

    return out
