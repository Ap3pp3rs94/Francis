from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def approval_payload_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    payload_obj = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    summary_payload = payload_obj if payload_obj else payload

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


def approval_projection_fields(record: dict[str, Any], *, artifact_root: Path | None = None) -> dict[str, Any]:
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
    approval_record = (
        artifact_mismatch.get("approval_record") if isinstance(artifact_mismatch.get("approval_record"), dict) else {}
    )
    previous_payload = approval_record.get("payload") if isinstance(approval_record, dict) else {}
    changed_keys = _changed_payload_keys(expected_payload, previous_payload)
    if changed_keys:
        out["replacement_changed_keys"] = changed_keys

    return out
