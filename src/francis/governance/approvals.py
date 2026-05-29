from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir, repo_root


def approvals_dir() -> Path:
    return data_dir() / "approvals"


def pending_dir() -> Path:
    return approvals_dir() / "pending"


def approved_dir() -> Path:
    return approvals_dir() / "approved"


def rejected_dir() -> Path:
    return approvals_dir() / "rejected"


def emergency_dir() -> Path:
    return approvals_dir() / "emergency"


def builder_self_approval_receipts_dir() -> Path:
    return approvals_dir() / "builder_self_approval_receipts"


def operator_delegation_receipts_dir() -> Path:
    return approvals_dir() / "operator_delegation_receipts"


def delegated_operator_approval_receipts_dir() -> Path:
    return approvals_dir() / "delegated_operator_approval_receipts"


def delegated_operator_authority_grant_receipts_dir() -> Path:
    return approvals_dir() / "delegated_operator_authority_grant_receipts"


# Backward-compatible constants (computed at import time).
PENDING = pending_dir()
APPROVED = approved_dir()
REJECTED = rejected_dir()
EMERGENCY = emergency_dir()
BUILDER_APPROVAL_ACTOR = "codex.builder"
DELEGATED_OPERATOR_AUTHORITY = "delegated_operator"
OPERATOR_DELEGATION_KIND = "operator.delegation.receipt"
DELEGATED_OPERATOR_APPROVAL_RECEIPT_KIND = "francis.approval.delegated_operator_approval_receipt"
DELEGATED_OPERATOR_AUTHORITY_GRANT_RECEIPT_KIND = "operator.delegated_authority.grant_receipt"
STAGE6_LENS_AUTHORITY_SCOPES = (
    "lens.summon_authority",
    "lens.hotkey_registration_authority",
    "lens.overlay_control_authority",
    "lens.local_process_launch_authority",
    "stage6.lens_authority_request_approvals",
)

_BUILDER_ALLOWED_ENV_PROFILES = {"dev", "workstation"}
_DISALLOWED_OPERATOR_DELEGATION_ENV_PROFILES = {"prod", "production", "regulated"}
_BUILDER_APPROVABLE_ACTIONS = {
    "build.artifact",
    "build.phase",
    "build_artifact",
    "build_phase",
    "codex.supervised_exec",
    "supervised_exec",
}
_BUILDER_SUPERVISED_EXEC_ACTIONS = {"codex.supervised_exec", "supervised_exec"}
_BUILDER_FORBIDDEN_TRUE_FLAGS = {
    "hotkey_registration_authority",
    "local_process_launch_authority",
    "overlay_control_authority",
    "requires_explicit_enable",
    "summon_authority",
}
_BUILDER_DENIED_PLANE_VALUES = {
    "operator",
    "operations",
    "prod",
    "production",
    "regulated",
    "runtime",
}
_BUILDER_PLANE_KEYS = {"context", "domain", "env_profile", "environment", "plane", "profile", "scope"}
_BUILDER_TEST_MARKERS = (
    "pytest",
    "ruff",
    "mypy",
    "npm run test",
    "npm test",
    "test ",
    "tests/",
    "tests\\",
    "fixture",
    "scaffold",
)
_BUILDER_BUILD_MARKERS = ("npm run build", "python -m build", "uv build", "hatch build", " build")
_BUILDER_PROOF_MARKERS = ("-proof.ps1", " proof", "proof.ps1", "proof_script")
_STAGE6_LENS_DELEGATED_ACTION_SCOPES = {
    "lens.summon.action_authority": (
        "lens.summon_authority",
        "lens.local_process_launch_authority",
        "stage6.lens_authority_request_approvals",
    ),
    "lens.overlay.window_authority": (
        "lens.overlay_control_authority",
        "lens.local_process_launch_authority",
        "stage6.lens_authority_request_approvals",
    ),
    "lens.os_binding.command_palette_binding_authority": (
        "lens.hotkey_registration_authority",
        "lens.local_process_launch_authority",
        "stage6.lens_authority_request_approvals",
    ),
}
_STAGE6_LENS_CONFIG_AUTHORITY_FLAGS = (
    "summon_authority",
    "hotkey_registration_authority",
    "overlay_control_authority",
    "local_process_launch_authority",
)
_STAGE6_LENS_FLAG_SCOPES = {
    "summon_authority": "lens.summon_authority",
    "hotkey_registration_authority": "lens.hotkey_registration_authority",
    "overlay_control_authority": "lens.overlay_control_authority",
    "local_process_launch_authority": "lens.local_process_launch_authority",
}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value).strip())


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            cleaned = _safe_str(item).strip()
            if cleaned:
                out.append(cleaned)
        return out
    return []


def _now() -> float:
    return time.time()


def _read_pending_request(approval_id: str) -> tuple[str, dict[str, Any]]:
    src = pending_dir() / f"{approval_id}.json"
    if not src.exists():
        return "missing", {}
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        return "corrupt", {}
    return "ok", raw if isinstance(raw, dict) else {}


def _read_approved_request(approval_id: str) -> tuple[str, dict[str, Any]]:
    src = approved_dir() / f"{approval_id}.json"
    if not src.exists():
        return "missing", {}
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        return "corrupt", {}
    return "ok", raw if isinstance(raw, dict) else {}


def _redact_metadata(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return _redact_free_text(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = _redact_free_text(raw_key)
            if key:
                out[key] = _redact_metadata(raw_value)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact_metadata(item) for item in value]
    return _redact_free_text(value)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return bool(value)


def _contains_truthy_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        for raw_key, raw_value in value.items():
            key = _safe_str(raw_key).strip().lower()
            if key in keys and _truthy(raw_value):
                return True
            if _contains_truthy_key(raw_value, keys):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_truthy_key(item, keys) for item in value)
    return False


def _has_outside_build_plane(value: Any) -> bool:
    if isinstance(value, dict):
        for raw_key, raw_value in value.items():
            key = _safe_str(raw_key).strip().lower()
            if key in _BUILDER_PLANE_KEYS:
                text = _safe_str(raw_value).strip().lower()
                if text in _BUILDER_DENIED_PLANE_VALUES:
                    return True
            if _has_outside_build_plane(raw_value):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_has_outside_build_plane(item) for item in value)
    return False


def _bounded_text_blob(value: Any, *, max_parts: int = 80) -> str:
    parts: list[str] = []

    def walk(item: Any) -> None:
        if len(parts) >= max_parts:
            return
        if item is None:
            return
        if isinstance(item, (bool, int, float, str)):
            text = _safe_str(item).strip()
            if text:
                parts.append(text.lower())
            return
        if isinstance(item, dict):
            for key in sorted(item, key=lambda current: _safe_str(current).strip().lower()):
                if len(parts) >= max_parts:
                    return
                parts.append(_safe_str(key).strip().lower())
                walk(item.get(key))
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                walk(child)

    walk(value)
    return " ".join(parts)


def _builder_artifact_category(record: dict[str, Any]) -> str:
    text = _bounded_text_blob(record)
    if any(marker in text for marker in _BUILDER_PROOF_MARKERS):
        return "proof_script_execution"
    if any(marker in text for marker in _BUILDER_TEST_MARKERS):
        return "test_scaffolding_command"
    if any(marker in text for marker in _BUILDER_BUILD_MARKERS):
        return "build_artifact_generation"
    return ""


def _builder_policy_denial(reason: str, *, profile: str, status: str = "denied") -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": "builder_self_approval_denied",
        "governance": {
            "gate": "builder_self_approval_policy",
            "reason": reason,
            "actor": BUILDER_APPROVAL_ACTOR,
            "allowed_env_profiles": sorted(_BUILDER_ALLOWED_ENV_PROFILES),
            "env_profile": profile,
            "operator_decision_required": True,
            "authority_granted": False,
        },
    }


def _current_env_profile() -> str:
    return _safe_str(os.getenv("FRANCIS_ENV_PROFILE")).strip().lower()


def _operator_delegation_id(*, delegating_actor: str, receiving_actor: str, ts: float) -> str:
    seed = f"{delegating_actor}:{receiving_actor}:{ts}:{uuid.uuid4()}"
    return f"opdel_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex}"


def _operator_delegation_receipt_path(delegation_id: Any) -> Path | None:
    cleaned = _safe_str(delegation_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return operator_delegation_receipts_dir() / f"{cleaned}.json"


def _delegated_operator_approval_receipt_path(approval_id: str) -> Path:
    return delegated_operator_approval_receipts_dir() / f"{approval_id}.json"


def _delegated_operator_authority_grant_receipt_path(receipt_id: str) -> Path:
    return delegated_operator_authority_grant_receipts_dir() / f"{receipt_id}.json"


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_operator_delegation_receipt(
    *,
    delegating_actor: str,
    receiving_actor: str,
    granted_scope: list[str] | tuple[str, ...],
    reason: str,
    expiry_policy: str,
    expires_ts: float | None = None,
) -> dict[str, Any]:
    ts = _now()
    clean_delegating_actor = _redact_free_text(delegating_actor) or "operator"
    clean_receiving_actor = _redact_free_text(receiving_actor)
    scopes = [scope for scope in _string_list(granted_scope) if scope]
    delegation_id = _operator_delegation_id(
        delegating_actor=clean_delegating_actor,
        receiving_actor=clean_receiving_actor,
        ts=ts,
    )
    receipt = {
        "kind": OPERATOR_DELEGATION_KIND,
        "delegation_id": delegation_id,
        "delegating_actor": clean_delegating_actor,
        "receiving_actor": clean_receiving_actor,
        "granted_scope": scopes,
        "reason": _redact_free_text(reason),
        "timestamp": ts,
        "ts": ts,
        "expiry_policy": _redact_free_text(expiry_policy),
        "expires_ts": expires_ts,
        "status": "active",
        "revoked": False,
        "authority": DELEGATED_OPERATOR_AUTHORITY,
        "governance": {
            "operator_decision_record": True,
            "delegated_operator_authority": True,
            "receiving_actor": clean_receiving_actor,
            "allowed_env_profiles": sorted(_BUILDER_ALLOWED_ENV_PROFILES),
            "disallowed_env_profiles": sorted(_DISALLOWED_OPERATOR_DELEGATION_ENV_PROFILES),
            "scope_limited": True,
            "granted_scope": scopes,
            "subdelegation_allowed": False,
            "production_allowed": False,
            "regulated_profile_allowed": False,
            "memory_write": False,
        },
    }
    path = _operator_delegation_receipt_path(delegation_id)
    if path is None:
        raise ValueError("invalid delegation_id")
    _write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    _write_json(path, receipt)
    return receipt


def _read_operator_delegation_receipts() -> list[dict[str, Any]]:
    folder = operator_delegation_receipts_dir()
    if not folder.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json"), key=lambda current: current.stat().st_mtime, reverse=True):
        payload = _read_json_dict(path)
        if payload:
            items.append(payload)
    return items


def _operator_delegation_is_active(
    receipt: dict[str, Any],
    *,
    receiving_actor: str,
    required_scopes: list[str] | tuple[str, ...],
    profile: str,
) -> bool:
    if _safe_str(receipt.get("kind")).strip() != OPERATOR_DELEGATION_KIND:
        return False
    if _safe_str(receipt.get("status")).strip().lower() != "active":
        return False
    if _truthy(receipt.get("revoked")):
        return False
    if _safe_str(receipt.get("receiving_actor")).strip() != receiving_actor:
        return False
    if profile not in _BUILDER_ALLOWED_ENV_PROFILES:
        return False
    if profile in _DISALLOWED_OPERATOR_DELEGATION_ENV_PROFILES:
        return False
    expires_ts = receipt.get("expires_ts")
    if expires_ts is not None:
        try:
            if float(expires_ts) <= _now():
                return False
        except (TypeError, ValueError):
            return False
    scope = set(_string_list(receipt.get("granted_scope")))
    return set(required_scopes).issubset(scope)


def active_operator_delegation_for(
    *,
    receiving_actor: str,
    required_scopes: list[str] | tuple[str, ...],
    profile: str | None = None,
) -> dict[str, Any] | None:
    effective_profile = _current_env_profile() if profile is None else profile
    for receipt in _read_operator_delegation_receipts():
        if _operator_delegation_is_active(
            receipt,
            receiving_actor=receiving_actor,
            required_scopes=required_scopes,
            profile=effective_profile,
        ):
            return receipt
    return None


def list_operator_delegation_receipts(
    *,
    limit: int = 100,
    receiving_actor: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    safe_limit = min(max(int(limit), 1), 500)
    profile = _current_env_profile()
    items: list[dict[str, Any]] = []
    for receipt in _read_operator_delegation_receipts():
        if receiving_actor and _safe_str(receipt.get("receiving_actor")).strip() != receiving_actor:
            continue
        if active_only and not _operator_delegation_is_active(
            receipt,
            receiving_actor=_safe_str(receipt.get("receiving_actor")).strip(),
            required_scopes=[],
            profile=profile,
        ):
            continue
        items.append(receipt)
        if len(items) >= safe_limit:
            break
    return {
        "ok": True,
        "kind": "operator.delegation.receipts",
        "items": items,
        "total": len(items),
        "limit": safe_limit,
        "env_profile": profile,
    }


def _builder_delegated_operator_evaluation(record: dict[str, Any], decision_status: str) -> dict[str, Any]:
    profile = _current_env_profile()
    if profile not in _BUILDER_ALLOWED_ENV_PROFILES:
        return {"allowed": False, "reason": "env_profile_not_allowed", "env_profile": profile}
    if decision_status != "approved":
        return {"allowed": False, "reason": "delegated_operator_authority_approves_only", "env_profile": profile}

    approval_action = _safe_str(record.get("action")).strip()
    required_scopes = _STAGE6_LENS_DELEGATED_ACTION_SCOPES.get(approval_action)
    if not required_scopes:
        return {"allowed": False, "reason": "approval_action_outside_delegated_lens_authority", "env_profile": profile}
    if _has_outside_build_plane(record):
        return {"allowed": False, "reason": "request_outside_delegated_stage6_lens_plane", "env_profile": profile}

    delegation = active_operator_delegation_for(
        receiving_actor=BUILDER_APPROVAL_ACTOR,
        required_scopes=required_scopes,
        profile=profile,
    )
    if delegation is None:
        return {"allowed": False, "reason": "operator_delegation_missing_or_inactive", "env_profile": profile}

    return {
        "allowed": True,
        "reason": "delegated_operator_policy_satisfied",
        "env_profile": profile,
        "approval_action": approval_action,
        "decision_kind": "delegated_operator_approval",
        "required_scopes": list(required_scopes),
        "delegation": delegation,
    }


def _builder_self_approval_evaluation(record: dict[str, Any], decision_status: str) -> dict[str, Any]:
    approval_action = _safe_str(record.get("action")).strip()
    if approval_action in _STAGE6_LENS_DELEGATED_ACTION_SCOPES:
        return _builder_delegated_operator_evaluation(record, decision_status)

    profile = _current_env_profile()
    if profile not in _BUILDER_ALLOWED_ENV_PROFILES:
        return {"allowed": False, "reason": "env_profile_not_allowed", "env_profile": profile}

    if decision_status == "emergency":
        return {"allowed": False, "reason": "builder_emergency_decisions_forbidden", "env_profile": profile}

    if approval_action not in _BUILDER_APPROVABLE_ACTIONS:
        return {"allowed": False, "reason": "approval_action_outside_builder_plane", "env_profile": profile}

    payload = _as_dict(record.get("payload"))
    if _contains_truthy_key(record, _BUILDER_FORBIDDEN_TRUE_FLAGS):
        return {"allowed": False, "reason": "operator_authority_flag_present", "env_profile": profile}
    if _has_outside_build_plane(record):
        return {"allowed": False, "reason": "request_outside_build_dev_plane", "env_profile": profile}

    objective = _safe_str(payload.get("objective")).strip()
    if approval_action in _BUILDER_SUPERVISED_EXEC_ACTIONS and not objective.startswith("supervised_exec:"):
        return {"allowed": False, "reason": "supervised_exec_objective_prefix_missing", "env_profile": profile}

    category = _builder_artifact_category(record)
    if decision_status == "approved" and not category:
        return {"allowed": False, "reason": "builder_artifact_class_not_recognized", "env_profile": profile}
    if decision_status == "rejected" and not category:
        category = "dev_artifact_rejection_without_execution"

    return {
        "allowed": True,
        "reason": "builder_self_approval_policy_satisfied",
        "env_profile": profile,
        "category": category,
        "objective": objective,
        "approval_action": approval_action,
    }


def _builder_receipt_path(approval_id: str) -> Path:
    return builder_self_approval_receipts_dir() / f"{approval_id}.json"


def _write_builder_receipt(receipt: dict[str, Any]) -> Path:
    approval_id = _safe_str(receipt.get("approval_id")).strip()
    path = _builder_receipt_path(approval_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_delegated_operator_approval_receipt(receipt: dict[str, Any]) -> Path:
    approval_id = _safe_str(receipt.get("approval_id")).strip()
    path = _delegated_operator_approval_receipt_path(approval_id)
    _write_json(path, receipt)
    return path


def _write_delegated_operator_authority_grant_receipt(receipt: dict[str, Any]) -> Path:
    receipt_id = _safe_str(receipt.get("receipt_id")).strip()
    path = _delegated_operator_authority_grant_receipt_path(receipt_id)
    _write_json(path, receipt)
    return path


def request(action: str, reason: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "action": action,
        "reason": _redact_free_text(reason),
        "payload": payload,
        "status": "pending",
    }
    folder = pending_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{req['id']}.json").write_text(
        json.dumps(req, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return req


def list_requests(status: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
    folder = {
        "pending": pending_dir(),
        "approved": approved_dir(),
        "rejected": rejected_dir(),
        "emergency": emergency_dir(),
    }.get(status, pending_dir())
    if not folder.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(folder.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _decision_status(action: str) -> str:
    s = (action or "").strip().lower()
    if s in {"approve", "approved"}:
        return "approved"
    if s in {"reject", "rejected", "deny", "denied"}:
        return "rejected"
    if s in {"emergency", "escalate"}:
        return "emergency"
    return ""


def decide(
    approval_id: str,
    action: str,
    comment: str | None = None,
    actor: str | None = None,
    *,
    decision_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = _decision_status(action)
    if not status:
        return {"ok": False, "status": "invalid", "error": "Unsupported decision action."}

    src_status, req = _read_pending_request(approval_id)
    if src_status == "missing":
        return {"ok": False, "status": "missing", "error": "Approval not found in pending queue."}
    if src_status == "corrupt":
        return {"ok": False, "status": "corrupt", "error": "Approval record is unreadable."}

    req["status"] = status
    req["decision"] = action
    if comment:
        req["comment"] = _redact_free_text(comment)
    if actor:
        req["decision_actor"] = _redact_free_text(actor)
    req["decided_ts"] = time.time()
    if decision_metadata:
        metadata = _redact_metadata(decision_metadata)
        if isinstance(metadata, dict):
            req.update(metadata)

    dest = {
        "approved": approved_dir(),
        "rejected": rejected_dir(),
        "emergency": emergency_dir(),
    }[status]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{approval_id}.json").write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        src = pending_dir() / f"{approval_id}.json"
        src.unlink()
    except Exception:
        pass

    return {"ok": True, "status": status, "item": req}


def builder_self_decide(
    approval_id: str,
    action: str,
    *,
    reason: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    builder_actor = _safe_str(actor).strip()
    if builder_actor != BUILDER_APPROVAL_ACTOR:
        return _builder_policy_denial("actor_not_builder", profile=_safe_str(os.getenv("FRANCIS_ENV_PROFILE")))

    decision_status = _decision_status(action)
    if not decision_status:
        return {"ok": False, "status": "invalid", "error": "Unsupported decision action."}

    src_status, record = _read_pending_request(approval_id)
    profile = _safe_str(os.getenv("FRANCIS_ENV_PROFILE")).strip().lower()
    if src_status == "missing":
        return {"ok": False, "status": "missing", "error": "Approval not found in pending queue."}
    if src_status == "corrupt":
        return {"ok": False, "status": "corrupt", "error": "Approval record is unreadable."}

    evaluation = _builder_self_approval_evaluation(record, decision_status)
    if not evaluation.get("allowed"):
        return _builder_policy_denial(_safe_str(evaluation.get("reason")), profile=profile)

    decision_kind = _safe_str(evaluation.get("decision_kind")) or "builder_self_approval"
    if decision_kind == "delegated_operator_approval":
        delegation = _as_dict(evaluation.get("delegation"))
        delegation_id = _safe_str(delegation.get("delegation_id")).strip()
        required_scopes = _string_list(evaluation.get("required_scopes"))
        now = time.time()
        redacted_reason = _redact_free_text(reason or "delegated_operator_approval")
        receipt = {
            "id": str(uuid.uuid4()),
            "kind": DELEGATED_OPERATOR_APPROVAL_RECEIPT_KIND,
            "approval_id": _redact_free_text(approval_id),
            "approval_action": _redact_free_text(record.get("action")),
            "actor": BUILDER_APPROVAL_ACTOR,
            "decision": decision_status,
            "requested_decision": _redact_free_text(action),
            "reason": redacted_reason,
            "ts": now,
            "env_profile": profile,
            "decision_kind": "delegated_operator_approval",
            "authority": DELEGATED_OPERATOR_AUTHORITY,
            "delegated_operator_approval": True,
            "builder_self_approval": False,
            "operator_approval": False,
            "delegation_id": delegation_id,
            "delegating_actor": _redact_free_text(delegation.get("delegating_actor")),
            "receiving_actor": BUILDER_APPROVAL_ACTOR,
            "granted_scope": _string_list(delegation.get("granted_scope")),
            "required_scope": required_scopes,
            "policy": {
                "allowed_env_profiles": sorted(_BUILDER_ALLOWED_ENV_PROFILES),
                "env_profile": profile,
                "stage6_lens_authority_only": True,
                "delegation_required": True,
                "delegation_id": delegation_id,
                "operator_decision_recorded": True,
                "authority": DELEGATED_OPERATOR_AUTHORITY,
                "summon_authority": "lens.summon_authority" in required_scopes,
                "hotkey_registration_authority": "lens.hotkey_registration_authority" in required_scopes,
                "overlay_control_authority": "lens.overlay_control_authority" in required_scopes,
                "local_process_launch_authority": "lens.local_process_launch_authority" in required_scopes,
                "requires_explicit_enable": False,
                "production_allowed": False,
                "regulated_profile_allowed": False,
                "memory_write": False,
            },
        }
        receipt_path = _write_delegated_operator_approval_receipt(receipt)
        decision_metadata = {
            "builder_self_approval": False,
            "operator_approval": False,
            "delegated_operator_approval": True,
            "decision_kind": "delegated_operator_approval",
            "decision_reason": redacted_reason,
            "authority": DELEGATED_OPERATOR_AUTHORITY,
            "delegation_id": delegation_id,
            "delegating_actor": receipt["delegating_actor"],
            "delegated_operator_approval_receipt_id": receipt["id"],
            "delegated_operator_approval_receipt_path": str(receipt_path),
            "delegated_operator_approval_policy": receipt["policy"],
            "delegated_operator_required_scope": required_scopes,
        }
        result = decide(
            approval_id,
            action,
            comment=reason,
            actor=BUILDER_APPROVAL_ACTOR,
            decision_metadata=decision_metadata,
        )
        if not result.get("ok"):
            return result
        return result

    now = time.time()
    redacted_reason = _redact_free_text(reason or "builder_self_approval")
    receipt = {
        "id": str(uuid.uuid4()),
        "kind": "francis.approval.builder_self_approval_receipt",
        "approval_id": _redact_free_text(approval_id),
        "approval_action": _redact_free_text(record.get("action")),
        "actor": BUILDER_APPROVAL_ACTOR,
        "decision": decision_status,
        "requested_decision": _redact_free_text(action),
        "reason": redacted_reason,
        "ts": now,
        "env_profile": profile,
        "decision_kind": "builder_self_approval",
        "operator_approval": False,
        "builder_self_approval": True,
        "command_category": _safe_str(evaluation.get("category")),
        "objective": _redact_free_text(evaluation.get("objective")),
        "policy": {
            "allowed_env_profiles": sorted(_BUILDER_ALLOWED_ENV_PROFILES),
            "env_profile": profile,
            "build_dev_plane_only": True,
            "operator_authority_flags_denied": sorted(_BUILDER_FORBIDDEN_TRUE_FLAGS),
            "operator_decision_required_for_denied_requests": True,
            "summon_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "local_process_launch_authority": False,
            "requires_explicit_enable": False,
            "authority_granted": False,
        },
    }
    receipt_path = _write_builder_receipt(receipt)
    decision_metadata = {
        "builder_self_approval": True,
        "operator_approval": False,
        "decision_kind": "builder_self_approval",
        "decision_reason": redacted_reason,
        "builder_self_approval_receipt_id": receipt["id"],
        "builder_self_approval_receipt_path": str(receipt_path),
        "builder_self_approval_policy": receipt["policy"],
        "builder_self_approval_command_category": receipt["command_category"],
    }

    result = decide(
        approval_id,
        action,
        comment=reason,
        actor=BUILDER_APPROVAL_ACTOR,
        decision_metadata=decision_metadata,
    )
    if not result.get("ok"):
        return result
    return result


def _stage6_lens_summon_config_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    return repo_root() / "config" / "runtime" / "lens" / "summon.json"


def apply_stage6_lens_delegated_authority_grants(
    *,
    delegation_id: str,
    actor: str = BUILDER_APPROVAL_ACTOR,
    reason: str = "stage6_lens_delegated_authority_grant",
    summon_config_path: Path | None = None,
    approval_ids: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _current_env_profile()
    if actor != BUILDER_APPROVAL_ACTOR:
        return {"ok": False, "status": "denied", "error": "actor_not_builder"}
    delegation = active_operator_delegation_for(
        receiving_actor=actor,
        required_scopes=STAGE6_LENS_AUTHORITY_SCOPES,
        profile=profile,
    )
    if delegation is None or _safe_str(delegation.get("delegation_id")).strip() != _safe_str(delegation_id).strip():
        return {
            "ok": False,
            "status": "denied",
            "error": "operator_delegation_missing_or_inactive",
            "env_profile": profile,
        }

    path = _stage6_lens_summon_config_path(summon_config_path)
    config = _read_json_dict(path)
    if not config:
        return {"ok": False, "status": "missing", "error": "summon_config_missing_or_unreadable", "path": str(path)}

    approval_id_map = approval_ids or {}
    related_approvals_by_flag: dict[str, list[str]] = {}
    for flag in _STAGE6_LENS_CONFIG_AUTHORITY_FLAGS:
        authority_scope = _STAGE6_LENS_FLAG_SCOPES[flag]
        related_approval_ids = _string_list(approval_id_map.get(flag)) or _string_list(
            approval_id_map.get(authority_scope)
        )
        if not related_approval_ids:
            return {
                "ok": False,
                "status": "denied",
                "error": "delegated_authority_approval_missing",
                "missing_config_key": flag,
            }
        for approval_id in related_approval_ids:
            approval_status, approval = _read_approved_request(approval_id)
            if (
                approval_status != "ok"
                or _safe_str(approval.get("decision_kind")).strip() != "delegated_operator_approval"
                or _safe_str(approval.get("authority")).strip() != DELEGATED_OPERATOR_AUTHORITY
                or _safe_str(approval.get("delegation_id")).strip() != _safe_str(delegation_id).strip()
            ):
                return {
                    "ok": False,
                    "status": "denied",
                    "error": "delegated_authority_approval_unverified",
                    "approval_id": _redact_free_text(approval_id),
                    "config_key": flag,
                }
        related_approvals_by_flag[flag] = related_approval_ids

    before = {flag: bool(config.get(flag)) for flag in _STAGE6_LENS_CONFIG_AUTHORITY_FLAGS}
    for flag in _STAGE6_LENS_CONFIG_AUTHORITY_FLAGS:
        config[flag] = True
    _write_json(path, config)

    now = _now()
    receipt_paths: list[str] = []
    receipts: list[dict[str, Any]] = []
    for flag in _STAGE6_LENS_CONFIG_AUTHORITY_FLAGS:
        authority_scope = _STAGE6_LENS_FLAG_SCOPES[flag]
        receipt_id = f"dlag_{uuid.uuid4().hex[:12]}"
        receipt = {
            "kind": DELEGATED_OPERATOR_AUTHORITY_GRANT_RECEIPT_KIND,
            "receipt_id": receipt_id,
            "delegation_id": _safe_str(delegation_id).strip(),
            "actor": actor,
            "delegating_actor": _redact_free_text(delegation.get("delegating_actor")),
            "receiving_actor": actor,
            "authority": DELEGATED_OPERATOR_AUTHORITY,
            "decision": "approved",
            "reason": _redact_free_text(reason),
            "ts": now,
            "env_profile": profile,
            "status": "authority_granted",
            "config_path": str(path),
            "config_key": flag,
            "granted_authority": authority_scope,
            "before": before[flag],
            "after": True,
            "approval_ids": related_approvals_by_flag[flag],
            "governance": {
                "operator_delegation_required": True,
                "operator_decision_recorded": True,
                "delegation_id": _safe_str(delegation_id).strip(),
                "authority": DELEGATED_OPERATOR_AUTHORITY,
                "allowed_env_profiles": sorted(_BUILDER_ALLOWED_ENV_PROFILES),
                "env_profile": profile,
                "stage6_lens_authority_only": True,
                "requires_explicit_enable_changed": False,
                "production_allowed": False,
                "regulated_profile_allowed": False,
                "memory_write": False,
            },
        }
        receipt_path = _write_delegated_operator_authority_grant_receipt(receipt)
        receipt["receipt_path"] = str(receipt_path)
        _write_delegated_operator_authority_grant_receipt(receipt)
        receipts.append(receipt)
        receipt_paths.append(str(receipt_path))

    return {
        "ok": True,
        "status": "authority_granted",
        "kind": "operator.delegated_authority.stage6_lens_grants",
        "delegation_id": _safe_str(delegation_id).strip(),
        "actor": actor,
        "authority": DELEGATED_OPERATOR_AUTHORITY,
        "config_path": str(path),
        "before": before,
        "after": {flag: bool(config.get(flag)) for flag in _STAGE6_LENS_CONFIG_AUTHORITY_FLAGS},
        "receipts": receipts,
        "receipt_paths": receipt_paths,
        "stage6_closed": False,
    }
