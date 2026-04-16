from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis.governance.approvals import decide as decide_request, list_requests, request as create_request
from francis.kernel.paths import data_dir

router = APIRouter()
_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_LOCAL_HOST_ALIASES = {"localhost", "testclient"}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _to_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _remote_decisions_allowed() -> bool:
    return _to_bool(os.getenv("FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS"), default=False)


def _is_local_client(host: str) -> bool:
    normalized = host.strip().lower()
    if not normalized:
        return False
    if normalized in _LOCAL_HOST_ALIASES:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _approval_payload_summary(payload: Any) -> dict[str, Any]:
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

    risk_tier = _safe_str(summary_payload.get("risk_tier")).strip().lower() or _safe_str(payload.get("risk_tier")).strip().lower()
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


def _approval_artifact_request(approval_id: str) -> dict[str, Any]:
    resolved_id = _safe_str(approval_id).strip()
    if not resolved_id:
        return {}

    artifact_root = data_dir() / "artifacts"
    candidates = [
        artifact_root / "credentials" / "approvals" / resolved_id / "request.json",
        artifact_root / "plugins" / "approvals" / resolved_id / "request.json",
        artifact_root / "web_learning" / "approvals" / resolved_id / "request.json",
        artifact_root / "industrial" / "approvals" / resolved_id / "request.json",
        artifact_root / "git_push" / resolved_id / "request.json",
        artifact_root / "supervised_exec" / resolved_id / "request.json",
    ]
    for path in candidates:
        record = _read_json(path)
        if record:
            return record
    return {}


def _approval_item(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record) if isinstance(record, dict) else {}
    approval_id = _safe_str(item.get("id")).strip()

    artifact_request = _approval_artifact_request(approval_id)
    payload_summary = _approval_payload_summary(item.get("payload"))
    artifact_payload = artifact_request.get("request")
    if isinstance(artifact_payload, dict):
        credential_id = _safe_str(artifact_payload.get("credential_id")).strip()
        if credential_id and "credential_id" not in payload_summary:
            payload_summary["credential_id"] = credential_id

    out = dict(item)
    out["payload_summary"] = payload_summary

    request_kind = _safe_str(artifact_request.get("kind")).strip()
    if request_kind:
        out["request_kind"] = request_kind

    previous_approval_id = _safe_str(artifact_request.get("previous_approval_id")).strip()
    if previous_approval_id:
        out["previous_approval_id"] = previous_approval_id

    previous_status = _safe_str(artifact_request.get("previous_status")).strip()
    if previous_status:
        out["previous_approval_status"] = previous_status

    return out


class ApprovalIn(BaseModel):
    action: str
    reason: str = "requested"
    payload: dict[str, object] = Field(default_factory=dict)


class ApprovalDecisionIn(BaseModel):
    id: str
    action: str
    comment: str | None = None


@router.post("/request")
def request_approval(payload: ApprovalIn) -> dict[str, object]:
    try:
        return create_request(payload.action, payload.reason, payload.payload)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/list")
def list_approvals(status: str = "pending", limit: int = 100) -> dict[str, object]:
    try:
        return {"items": [_approval_item(item) for item in list_requests(status=status, limit=limit)]}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


@router.post("/decision")
def decide_approval(request: Request, payload: ApprovalDecisionIn) -> dict[str, object]:
    try:
        client_host = request.client.host if request.client is not None else ""
        if not _remote_decisions_allowed() and not _is_local_client(client_host):
            raise HTTPException(status_code=403, detail="approval decisions require a local caller")
        return decide_request(payload.id, payload.action, payload.comment)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        return {"ok": False, "error": str(exc)}
