from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir


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


# Backward-compatible constants (computed at import time).
PENDING = pending_dir()
APPROVED = approved_dir()
REJECTED = rejected_dir()
EMERGENCY = emergency_dir()
BUILDER_APPROVAL_ACTOR = "codex.builder"

_BUILDER_ALLOWED_ENV_PROFILES = {"dev", "workstation"}
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


def _read_pending_request(approval_id: str) -> tuple[str, dict[str, Any]]:
    src = pending_dir() / f"{approval_id}.json"
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


def _builder_self_approval_evaluation(record: dict[str, Any], decision_status: str) -> dict[str, Any]:
    profile = _safe_str(os.getenv("FRANCIS_ENV_PROFILE")).strip().lower()
    if profile not in _BUILDER_ALLOWED_ENV_PROFILES:
        return {"allowed": False, "reason": "env_profile_not_allowed", "env_profile": profile}

    if decision_status == "emergency":
        return {"allowed": False, "reason": "builder_emergency_decisions_forbidden", "env_profile": profile}

    approval_action = _safe_str(record.get("action")).strip()
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
