from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

from .repo_tools import DeveloperBridgeError

_KIND = "developer_bridge.francis_capability_grants"
_STATE_KIND = "developer_bridge.francis_capability_grants_state"
_SCHEMA_VERSION = "developer_bridge_francis_capability_grants_v1"
_SURFACE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_REASON_CHARS = 500
_MAX_RECEIPTS = 200
_KNOWN_SURFACES = (
    "collaboration",
    "memory",
    "governance",
    "action_intake",
    "execution",
    "orb_planes",
    "orb_lens_hud_shell",
    "mcp",
    "capability_economy",
    "model_tuning",
)
_LOW_RISK_ACCESS_MODES = ("observe", "read", "request", "propose_plan")
_DECISIONS = ("grant", "deny", "revoke")


def known_capability_surfaces() -> tuple[str, ...]:
    """Return the bounded Francis body surfaces that can receive explicit grants."""

    return _KNOWN_SURFACES


def allowed_capability_access_modes() -> tuple[str, ...]:
    """Return low-risk access modes allowed by the capability-grant receipt lane."""

    return _LOW_RISK_ACCESS_MODES


def read_francis_capability_grants(*, surface_id: str = "") -> dict[str, object]:
    """Read operator capability-grant decisions without granting execution authority."""

    clean_surface = _optional_surface_id(surface_id)
    state = _load_state()
    decisions = _state_decisions(state)
    surfaces = [clean_surface] if clean_surface else list(_KNOWN_SURFACES)
    items = [_grant_record(surface, _decision_state(decisions, surface)) for surface in surfaces]
    granted = [item for item in items if bool(item.get("capability_granted"))]
    denied = [item for item in items if item.get("grant_state") in {"denied", "revoked"}]
    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "readback_and_operator_receipts",
        "surface": "developer_bridge.francis_capability_grants",
        "state_path": _display_path(_state_path()),
        "known_surfaces": list(_KNOWN_SURFACES),
        "allowed_decisions": list(_DECISIONS),
        "allowed_access_modes": list(_LOW_RISK_ACCESS_MODES),
        "items": items,
        "count": len(items),
        "summary": {
            "surface_count": len(items),
            "granted_count": len(granted),
            "denied_or_revoked_count": len(denied),
            "active_grants_present": bool(granted),
            "deny_after_grant_supported": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
        "receipts": _list(state.get("receipts"))[-10:],
        "filters": {"surface_id": clean_surface},
        "definitions": {
            "grant": "Permit a named low-risk Francis body surface to be exposed as local-model capability context.",
            "deny": "Keep or place the surface outside local-model capability use.",
            "revoke": "Remove a prior grant while retaining the bounded decision receipt for tuning review.",
        },
        "governance": _governance(write=False, decision="read"),
    }


def active_capability_grant(surface_id: str) -> dict[str, object]:
    """Return the current grant state for one body-map surface."""

    clean_surface = _surface_id(surface_id)
    state = _load_state()
    return _grant_record(clean_surface, _decision_state(_state_decisions(state), clean_surface))


def set_francis_capability_grant(
    surface_id: str,
    decision: str,
    *,
    requested_access_mode: str = "read",
    actor: str = "",
    reason: str = "",
    source_review_item_id: str = "",
) -> dict[str, object]:
    """Record an operator grant, deny, or revoke decision for one known surface."""

    clean_surface = _surface_id(surface_id)
    clean_decision = _decision(decision)
    clean_mode = _access_mode(requested_access_mode)
    clean_actor = _bounded_text(actor, max_chars=96) or "operator"
    clean_reason = _bounded_text(reason, max_chars=_MAX_REASON_CHARS)
    clean_source_review = _bounded_text(source_review_item_id, max_chars=180)
    if clean_decision == "grant" and not clean_reason:
        raise DeveloperBridgeError("capability_grant_reason_required", "grant decisions require a bounded reason")

    state = _load_state()
    decisions = _state_decisions(state)
    previous = _grant_record(clean_surface, _decision_state(decisions, clean_surface))
    now = _utc_now()
    grant_state = _grant_state_for(clean_decision)
    current: dict[str, object] = {
        "surface_id": clean_surface,
        "grant_state": grant_state,
        "decision": clean_decision,
        "requested_access_mode": clean_mode,
        "granted_access_mode": clean_mode if clean_decision == "grant" else "observe",
        "actor": redact_secret_text(clean_actor),
        "reason": redact_secret_text(clean_reason),
        "source_review_item_id": redact_secret_text(clean_source_review),
        "updated_at": now,
    }
    decisions[clean_surface] = current
    state["decisions"] = decisions
    governance = _governance(write=True, decision=clean_decision)
    current_record = _grant_record(clean_surface, current)
    receipt = {
        "kind": "developer_bridge.francis_capability_grant_receipt",
        "schema_version": _SCHEMA_VERSION,
        "receipt_id": f"francis-capability-grant-{uuid4().hex[:16]}",
        "created_at": now,
        "surface_id": clean_surface,
        "decision": clean_decision,
        "grant_state": grant_state,
        "requested_access_mode": clean_mode,
        "granted_access_mode": current_record["granted_access_mode"],
        "actor": redact_secret_text(clean_actor),
        "reason": redact_secret_text(clean_reason),
        "source_review_item_id": redact_secret_text(clean_source_review),
        "previous_grant_state": previous["grant_state"],
        "current_grant_state": current_record["grant_state"],
        "capability_granted": current_record["capability_granted"],
        "connected_to_local_model": current_record["connected_to_local_model"],
        "operator_grant_proof": _operator_grant_proof(
            actor=clean_actor,
            reason=clean_reason,
            previous=previous,
            current=current_record,
            governance=governance,
        ),
        "governance": governance,
    }
    receipts = _list(state.get("receipts"))
    receipts.append(receipt)
    state["receipts"] = receipts[-_MAX_RECEIPTS:]
    _save_state(state)
    return {
        "kind": "developer_bridge.francis_capability_grant_decision",
        "ok": True,
        "surface_id": clean_surface,
        "decision": clean_decision,
        "grant": current_record,
        "receipt": receipt,
        "status": read_francis_capability_grants(surface_id=clean_surface),
        "governance": governance,
    }


def _grant_record(surface_id: str, state: dict[str, object]) -> dict[str, object]:
    grant_state = _bounded_text(state.get("grant_state"), max_chars=40) or "not_granted"
    granted = grant_state == "granted"
    requested_access_mode = _access_mode_or_default(state.get("requested_access_mode"), default="observe")
    granted_access_mode = _access_mode_or_default(
        state.get("granted_access_mode"),
        default=requested_access_mode if granted else "observe",
    )
    return {
        "kind": "developer_bridge.francis_capability_grant",
        "schema_version": _SCHEMA_VERSION,
        "surface_id": surface_id,
        "grant_state": grant_state,
        "capability_granted": granted,
        "connected_to_local_model": granted,
        "safe_for_capability_use": granted,
        "capability_use_status": f"granted_{granted_access_mode}" if granted else "not_exposed",
        "requested_access_mode": requested_access_mode,
        "granted_access_mode": granted_access_mode if granted else "observe",
        "grantable_after_trust": True,
        "grant_requires": [
            "trust_ladder_decision",
            "codex_or_operator_review",
            "governed_capability_receipt",
        ],
        "deny_after_grant_supported": True,
        "revocation_state": "revocable_for_tuning",
        "can_deny_after_fact_for_tuning": True,
        "source_review_item_id": _bounded_text(state.get("source_review_item_id"), max_chars=180),
        "updated_at": _bounded_text(state.get("updated_at"), max_chars=80),
        "updated_by": _bounded_text(state.get("actor"), max_chars=96),
        "reason": _bounded_text(state.get("reason"), max_chars=_MAX_REASON_CHARS),
        "grants_capability_authority": granted,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _operator_grant_proof(
    *,
    actor: str,
    reason: str,
    previous: dict[str, object],
    current: dict[str, object],
    governance: dict[str, object],
) -> dict[str, object]:
    return {
        "kind": "developer_bridge.francis_capability_grant_proof",
        "proof_status": "operator_grant_recorded",
        "actor_recorded": bool(actor),
        "reason_recorded": bool(reason),
        "previous_state_observed": True,
        "current_state_observed": True,
        "previous_grant_state": previous["grant_state"],
        "current_grant_state": current["grant_state"],
        "state_changed": previous["grant_state"] != current["grant_state"],
        "deny_after_grant_supported": True,
        "can_deny_after_fact_for_tuning": True,
        "client_can_be_operator_console": bool(governance["client_can_be_operator_console"]),
        "client_is_automatic_execution_authority": bool(governance["client_is_automatic_execution_authority"]),
        "grants_capability_authority": bool(current["capability_granted"]),
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "capability_grants" / "state.json"


def _load_state() -> dict[str, object]:
    path = _state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(data, dict) or data.get("kind") != _STATE_KIND:
        return _empty_state()
    data.setdefault("decisions", {})
    data.setdefault("receipts", [])
    return data


def _empty_state() -> dict[str, object]:
    now = _utc_now()
    return {
        "kind": _STATE_KIND,
        "schema_version": _SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
        "decisions": {},
        "receipts": [],
        "governance": _governance(write=True, decision="bootstrap"),
    }


def _save_state(state: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now()
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{uuid4().hex[:12]}.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _state_decisions(state: dict[str, object]) -> dict[str, object]:
    decisions = state.get("decisions")
    return decisions if isinstance(decisions, dict) else {}


def _decision_state(decisions: dict[str, object], surface_id: str) -> dict[str, object]:
    value = decisions.get(surface_id)
    return dict(value) if isinstance(value, dict) else {}


def _surface_id(value: str) -> str:
    text = str(value or "").strip().lower()
    if not _SURFACE_RE.fullmatch(text):
        raise DeveloperBridgeError("capability_surface_denied", "surface id must be a known Francis body surface")
    if text not in _KNOWN_SURFACES:
        raise DeveloperBridgeError(
            "unknown_capability_surface", f"surface must be one of: {', '.join(_KNOWN_SURFACES)}"
        )
    return text


def _optional_surface_id(value: str) -> str:
    if not str(value or "").strip():
        return ""
    return _surface_id(value)


def _decision(value: str) -> str:
    text = str(value or "").strip().lower()
    if text not in _DECISIONS:
        raise DeveloperBridgeError("capability_grant_decision_denied", "decision must be grant, deny, or revoke")
    return text


def _grant_state_for(decision: str) -> str:
    if decision == "grant":
        return "granted"
    if decision == "deny":
        return "denied"
    return "revoked"


def _access_mode(value: object) -> str:
    text = _access_mode_or_default(value, default="")
    if text not in _LOW_RISK_ACCESS_MODES:
        raise DeveloperBridgeError(
            "capability_access_mode_denied",
            "capability grants here are limited to observe, read, request, or propose_plan",
        )
    return text


def _access_mode_or_default(value: object, *, default: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if not text:
        return default
    return text if text in _LOW_RISK_ACCESS_MODES else default


def _bounded_text(value: object, *, max_chars: int) -> str:
    text = redact_secret_text(str(value or "")).replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()[:max_chars]


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(data_dir()).as_posix()
    except ValueError:
        return path.as_posix()


def _governance(*, write: bool, decision: str) -> dict[str, object]:
    grants_capability = write and decision == "grant"
    return {
        "surface": "developer_bridge.francis_capability_grants",
        "read_only": not write,
        "writes_capability_grant_state": write,
        "writes_bounded_receipt": write,
        "executes_prompt": False,
        "calls_model": False,
        "trains_model": False,
        "client_can_be_operator_console": True,
        "client_is_automatic_execution_authority": False,
        "requires_operator_review": True,
        "allowed_access_modes": list(_LOW_RISK_ACCESS_MODES),
        "grants_capability_authority": grants_capability,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }
