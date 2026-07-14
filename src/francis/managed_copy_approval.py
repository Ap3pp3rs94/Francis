from __future__ import annotations

import hashlib
import json
from typing import Any

from francis.governance import approvals as approval_store
from francis.governance.redaction import redact_secret_text
from francis.telemetry.audit import record as audit_record

MANAGED_COPY_APPROVAL_REQUEST_CONTRACT = "stage18_managed_copy_creation_approval_request_v1"
MANAGED_COPY_APPROVAL_REQUEST_KIND = "francis.stage18.managed_copies.copy_creation_approval_request"
MANAGED_COPY_APPROVAL_REQUESTS_KIND = "francis.stage18.managed_copies.copy_creation_approval_requests"
MANAGED_COPY_PROVISION_ACTION = "managed_copies.provision_copy"

_APPROVAL_STATUSES = ("pending", "approved", "rejected", "emergency")


def managed_copy_creation_approval_request_plan(
    payload: dict[str, Any],
    *,
    actor: str,
    plan_receipt: dict[str, Any],
) -> dict[str, Any]:
    safe_actor = _redacted_text(actor)[:240]
    provided_plan_receipt_id = _safe_text(payload.get("plan_receipt_id"))
    expected_plan_receipt_id = _safe_text(plan_receipt.get("receipt_id"))
    plan_fingerprint = _safe_text(plan_receipt.get("plan_fingerprint"))
    raw_plan_steps = plan_receipt.get("plan_steps")
    plan_steps = raw_plan_steps if isinstance(raw_plan_steps, list) else []
    plan_step_ids = [
        _safe_text(step.get("id")) for step in plan_steps if isinstance(step, dict) and _safe_text(step.get("id"))
    ]

    blockers: list[str] = []
    if not plan_receipt:
        blockers.append("copy_creation_plan_receipt_missing")
    if not safe_actor:
        blockers.append("copy_approval_request_actor_missing")
    if not provided_plan_receipt_id:
        blockers.append("copy_creation_plan_receipt_id_missing")
    elif expected_plan_receipt_id and provided_plan_receipt_id != expected_plan_receipt_id:
        blockers.append("copy_creation_plan_receipt_id_mismatch")
    if plan_receipt and not _plan_receipt_lineage_ready(plan_receipt, plan_step_ids):
        blockers.append("copy_creation_plan_lineage_invalid")

    exact_action = {
        "kind": "francis.stage18.managed_copies.copy_creation_exact_action",
        "contract": MANAGED_COPY_APPROVAL_REQUEST_CONTRACT,
        "requested_action": MANAGED_COPY_PROVISION_ACTION,
        "requested_transition": "planned_to_provisioning",
        "request_actor": safe_actor,
        "tenant_key": _safe_text(plan_receipt.get("tenant_key")),
        "plan_receipt_id": expected_plan_receipt_id,
        "plan_fingerprint": plan_fingerprint,
        "request_receipt_id": _safe_text(plan_receipt.get("request_receipt_id")),
        "request_fingerprint": _safe_text(plan_receipt.get("request_fingerprint")),
        "preflight_receipt_id": _safe_text(plan_receipt.get("preflight_receipt_id")),
        "preflight_fingerprint": _safe_text(plan_receipt.get("preflight_fingerprint")),
        "stage17_closure_receipt_id": _safe_text(plan_receipt.get("stage17_closure_receipt_id")),
        "plan_step_ids": plan_step_ids,
        "future_effects": {
            "creates_isolated_copy_state": True,
            "writes_tenant_state": True,
            "writes_registry": True,
            "writes_provisioning_receipt": True,
            "starts_runtime": False,
        },
    }
    approval_action_fingerprint = _fingerprint(exact_action) if not blockers else ""
    return {
        "ok": not blockers,
        "kind": "francis.stage18.managed_copies.copy_creation_approval_request_plan",
        "contract": MANAGED_COPY_APPROVAL_REQUEST_CONTRACT,
        "status": "approval_request_ready" if not blockers else "blocked",
        "actor": safe_actor,
        "plan_receipt_id": expected_plan_receipt_id,
        "provided_plan_receipt_id": provided_plan_receipt_id,
        "plan_fingerprint": plan_fingerprint,
        "plan_receipt_aligned": bool(
            plan_receipt and expected_plan_receipt_id and provided_plan_receipt_id == expected_plan_receipt_id
        ),
        "exact_action": exact_action,
        "approval_action_fingerprint": approval_action_fingerprint,
        "approval_request_contract_ready": not blockers,
        "blockers": blockers,
        "dry_run_confirmation": {
            "required_for_request": True,
            "fingerprint": approval_action_fingerprint,
            "fingerprint_contract": MANAGED_COPY_APPROVAL_REQUEST_CONTRACT,
        },
        "contains_raw_tenant_payload": False,
        "writes_approval_request": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "creates_copy": False,
        "starts_runtime": False,
        "consumes_approval": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def record_managed_copy_creation_approval_request(
    plan: dict[str, Any],
    *,
    provided_fingerprint: str,
    confirm_approval_request: bool,
) -> dict[str, Any]:
    expected_fingerprint = _safe_text(plan.get("approval_action_fingerprint"))
    if not plan.get("approval_request_contract_ready"):
        return _blocked("blocked_copy_approval_request_contract", "copy_approval_request_contract_not_ready", plan)
    if not confirm_approval_request:
        return _blocked(
            "blocked_copy_approval_request_confirmation",
            "copy_approval_request_confirmation_required",
            plan,
        )
    if not expected_fingerprint or _safe_text(provided_fingerprint) != expected_fingerprint:
        return _blocked(
            "blocked_copy_approval_request_dry_run_confirmation",
            "copy_approval_request_fingerprint_mismatch",
            plan,
        )

    plan_receipt_id = _safe_text(plan.get("plan_receipt_id"))
    existing = latest_managed_copy_creation_approval_for_plan(
        plan_receipt_id,
        plan_fingerprint=_safe_text(plan.get("plan_fingerprint")),
        approval_action_fingerprint=expected_fingerprint,
    )
    if existing:
        return {
            "ok": True,
            "status": "already_requested",
            "error": "",
            "approval": existing,
            "approval_id": _safe_text(existing.get("id")),
            "approval_status": _safe_text(existing.get("status")),
            "copy_approval_request_recorded": True,
            "writes_approval_request": False,
            "writes_receipt": False,
            "writes_tenant_state": False,
            "creates_copy": False,
            "starts_runtime": False,
            "consumes_approval": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }

    request_payload = {
        "kind": MANAGED_COPY_APPROVAL_REQUEST_KIND,
        "contract": MANAGED_COPY_APPROVAL_REQUEST_CONTRACT,
        "approval_action_fingerprint": expected_fingerprint,
        "exact_action": dict(plan.get("exact_action") or {}),
        "governance": {
            "exact_action_hash_bound": True,
            "copy_creation_plan_receipt_required": True,
            "operator_decision_required": True,
            "approval_request_only": True,
            "contains_raw_tenant_payload": False,
            "does_not_consume_approval": True,
            "does_not_provision_copy": True,
            "does_not_write_tenant_state": True,
            "does_not_start_runtime": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    approval = approval_store.request(
        MANAGED_COPY_PROVISION_ACTION,
        "Stage 18 managed-copy provisioning requires exact-action operator approval.",
        request_payload,
    )
    approval_id = _safe_text(approval.get("id"))
    audit_record(
        "managed_copies.copy_creation_approval_requested",
        actor=_safe_text(plan.get("actor")),
        approval_id=approval_id,
        plan_receipt_id=plan_receipt_id,
        approval_action_fingerprint=expected_fingerprint,
    )
    return {
        "ok": True,
        "status": "approval_pending",
        "error": "",
        "approval": approval,
        "approval_id": approval_id,
        "approval_status": "pending",
        "copy_approval_request_recorded": True,
        "writes_approval_request": True,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "creates_copy": False,
        "starts_runtime": False,
        "consumes_approval": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def managed_copy_creation_approval_requests_readback(*, limit: int = 20) -> dict[str, Any]:
    items = _approval_records(limit=max(limit, 1))
    valid_items = [item for item in items if _valid_approval_record(item)]
    latest = items[0] if items else {}
    latest_valid = valid_items[0] if valid_items else {}
    latest_status = _safe_text(latest_valid.get("status"))
    return {
        "ok": True,
        "kind": MANAGED_COPY_APPROVAL_REQUESTS_KIND,
        "status": "ready" if valid_items else "empty",
        "items": items[: _safe_limit(limit)],
        "count": len(items),
        "valid_count": len(valid_items),
        "latest_approval": latest,
        "latest_approval_id": _safe_text(latest.get("id")),
        "latest_approval_valid": _valid_approval_record(latest),
        "latest_valid_approval": latest_valid,
        "latest_valid_approval_id": _safe_text(latest_valid.get("id")),
        "latest_valid_approval_status": latest_status,
        "reads_approval_requests": True,
        "writes_approval_requests": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "creates_copy": False,
        "starts_runtime": False,
        "consumes_approval": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "next_smallest_truthful_gap": _next_gap(latest_status),
    }


def latest_managed_copy_creation_approval_for_plan(
    plan_receipt_id: str,
    *,
    plan_fingerprint: str = "",
    approval_action_fingerprint: str = "",
) -> dict[str, Any]:
    expected_plan_receipt_id = _safe_text(plan_receipt_id)
    if not expected_plan_receipt_id:
        return {}
    expected_plan_fingerprint = _safe_text(plan_fingerprint)
    expected_action_fingerprint = _safe_text(approval_action_fingerprint)
    for item in _approval_records(limit=500):
        exact_action = _exact_action(item)
        if (
            _safe_text(exact_action.get("plan_receipt_id")) == expected_plan_receipt_id
            and (
                not expected_plan_fingerprint
                or _safe_text(exact_action.get("plan_fingerprint")) == expected_plan_fingerprint
            )
            and (not expected_action_fingerprint or _approval_action_fingerprint(item) == expected_action_fingerprint)
            and _valid_approval_record(item)
        ):
            return item
    return {}


def _blocked(status: str, error: str, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": error,
        "approval": None,
        "approval_id": "",
        "approval_status": "",
        "copy_approval_request_recorded": False,
        "writes_approval_request": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "creates_copy": False,
        "starts_runtime": False,
        "consumes_approval": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "plan": plan,
    }


def _approval_records(*, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for status in _APPROVAL_STATUSES:
        for raw in approval_store.list_requests(status=status, limit=limit):
            if isinstance(raw, dict) and _safe_text(raw.get("action")) == MANAGED_COPY_PROVISION_ACTION:
                item = dict(raw)
                item["status"] = status
                items.append(item)
    return sorted(items, key=lambda item: _safe_float(item.get("ts")), reverse=True)


def _valid_approval_record(item: dict[str, Any]) -> bool:
    payload = item.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    governance = payload.get("governance")
    governance = governance if isinstance(governance, dict) else {}
    exact_action = _exact_action(item)
    action_fingerprint = _approval_action_fingerprint(item)
    future_effects = exact_action.get("future_effects")
    future_effects = future_effects if isinstance(future_effects, dict) else {}
    plan_step_ids = exact_action.get("plan_step_ids")
    return (
        bool(_safe_text(item.get("id")))
        and _safe_text(item.get("action")) == MANAGED_COPY_PROVISION_ACTION
        and _safe_text(item.get("status")) in _APPROVAL_STATUSES
        and _safe_text(payload.get("kind")) == MANAGED_COPY_APPROVAL_REQUEST_KIND
        and _safe_text(payload.get("contract")) == MANAGED_COPY_APPROVAL_REQUEST_CONTRACT
        and _is_sha256(action_fingerprint)
        and action_fingerprint == _fingerprint(exact_action)
        and _safe_text(exact_action.get("kind")) == "francis.stage18.managed_copies.copy_creation_exact_action"
        and _safe_text(exact_action.get("contract")) == MANAGED_COPY_APPROVAL_REQUEST_CONTRACT
        and _safe_text(exact_action.get("requested_action")) == MANAGED_COPY_PROVISION_ACTION
        and _safe_text(exact_action.get("requested_transition")) == "planned_to_provisioning"
        and bool(_safe_text(exact_action.get("request_actor")))
        and _is_sha256(exact_action.get("tenant_key"))
        and _safe_text(exact_action.get("plan_receipt_id")).startswith("managed_copy_creation_plan_")
        and _is_sha256(exact_action.get("plan_fingerprint"))
        and _safe_text(exact_action.get("request_receipt_id")).startswith("managed_copy_request_")
        and _is_sha256(exact_action.get("request_fingerprint"))
        and _safe_text(exact_action.get("preflight_receipt_id")).startswith("managed_copy_preflight_")
        and _is_sha256(exact_action.get("preflight_fingerprint"))
        and _safe_text(exact_action.get("stage17_closure_receipt_id")).startswith("stage17_capability_economy_closure_")
        and isinstance(plan_step_ids, list)
        and bool(plan_step_ids)
        and all(bool(_safe_text(step_id)) for step_id in plan_step_ids)
        and bool(future_effects.get("creates_isolated_copy_state"))
        and bool(future_effects.get("writes_tenant_state"))
        and bool(future_effects.get("writes_registry"))
        and bool(future_effects.get("writes_provisioning_receipt"))
        and not bool(future_effects.get("starts_runtime"))
        and bool(governance.get("exact_action_hash_bound"))
        and bool(governance.get("copy_creation_plan_receipt_required"))
        and bool(governance.get("operator_decision_required"))
        and bool(governance.get("approval_request_only"))
        and not bool(governance.get("contains_raw_tenant_payload"))
        and bool(governance.get("does_not_consume_approval"))
        and bool(governance.get("does_not_provision_copy"))
        and bool(governance.get("does_not_write_tenant_state"))
        and bool(governance.get("does_not_start_runtime"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _plan_receipt_lineage_ready(plan_receipt: dict[str, Any], plan_step_ids: list[str]) -> bool:
    return (
        _safe_text(plan_receipt.get("receipt_id")).startswith("managed_copy_creation_plan_")
        and _is_sha256(plan_receipt.get("tenant_key"))
        and _is_sha256(plan_receipt.get("plan_fingerprint"))
        and _safe_text(plan_receipt.get("request_receipt_id")).startswith("managed_copy_request_")
        and _is_sha256(plan_receipt.get("request_fingerprint"))
        and _safe_text(plan_receipt.get("preflight_receipt_id")).startswith("managed_copy_preflight_")
        and _is_sha256(plan_receipt.get("preflight_fingerprint"))
        and _safe_text(plan_receipt.get("stage17_closure_receipt_id")).startswith("stage17_capability_economy_closure_")
        and bool(plan_step_ids)
    )


def _exact_action(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    exact_action = payload.get("exact_action")
    return exact_action if isinstance(exact_action, dict) else {}


def _approval_action_fingerprint(item: dict[str, Any]) -> str:
    payload = item.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    return _safe_text(payload.get("approval_action_fingerprint"))


def _next_gap(status: str) -> str:
    return {
        "pending": "stage18_copy_creation_approval_decision",
        "approved": "stage18_copy_creation_provision",
        "rejected": "stage18_copy_creation_plan_revision",
        "emergency": "stage18_copy_creation_approval_emergency_review",
    }.get(status, "stage18_copy_creation_approval_request")


def _safe_limit(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 20
    return min(max(parsed, 1), 500)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_sha256(value: Any) -> bool:
    text = _safe_text(value)
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text.casefold())


def _fingerprint(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))
