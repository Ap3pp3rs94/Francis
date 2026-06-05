from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

from francis.managed_copies import (
    MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
    MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE,
    MANAGED_COPIES_ROGUE_RECOVERY_WRITE_SCOPE,
    MANAGED_COPIES_RUNTIME_EVIDENCE_WRITE_SCOPE,
    MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE,
    MANAGED_COPIES_SLA_WRITE_SCOPE,
    managed_copies_status_snapshot,
    managed_copy_completion_review_snapshot,
    managed_copy_creation_contract_snapshot,
    managed_copy_creation_request_blocked_snapshot,
    managed_copy_decommission_contract_snapshot,
    managed_copy_isolation_rules_contract_snapshot,
    managed_copy_isolation_verification_blocked_snapshot,
    managed_copy_rogue_recovery_contract_snapshot,
    managed_copy_rogue_recovery_review_blocked_snapshot,
    managed_copy_runtime_evidence_contract_snapshot,
    managed_copy_runtime_evidence_readback_blocked_snapshot,
    managed_copy_runtime_evidence_readbacks_snapshot,
    managed_copy_safe_delta_model_contract_snapshot,
    managed_copy_safe_delta_review_blocked_snapshot,
    managed_copy_sla_commitment_review_blocked_snapshot,
    managed_copy_sla_framework_contract_snapshot,
    managed_copy_roles_contract_snapshot,
)

router = APIRouter()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _managed_copy_write_actor(payload: dict[str, Any]) -> str:
    return (
        _safe_str(payload.get("request_actor")).strip()
        or _safe_str(payload.get("api_actor")).strip()
        or _safe_str(payload.get("actor")).strip()
    )


def _write_permission(actor: Any, *, required_scope: str, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[required_scope],
        route=route,
        method=method,
    )


def _permission_denied(
    decision: ApiPermissionDecision,
    *,
    required_scope: str,
    next_step: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "required_scope": required_scope,
        "copy_creation_enabled": False,
        "isolation_enforcement_enabled": False,
        "isolation_verification_enabled": False,
        "runtime_evidence_recording_enabled": False,
        "rogue_recovery_review_enabled": False,
        "rogue_recovery_ready": False,
        "halt_enabled": False,
        "quarantine_enabled": False,
        "replacement_enabled": False,
        "restore_enabled": False,
        "safe_delta_review_enabled": False,
        "safe_delta_flow_active": False,
        "sla_framework_ready": False,
        "sla_review_enabled": False,
        "sla_commitments_active": False,
        "monitoring_enabled": False,
        "paging_enabled": False,
        "support_tiers_enabled": False,
        "billing_entitlements_enabled": False,
        "creates_service_commitment": False,
        "pages_support": False,
        "opens_incident": False,
        "records_sla_receipt": False,
        "grants_support_authority": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": next_step,
            "required_scope": required_scope,
            "evidence": decision.evidence,
            "copy_creation_enabled": False,
            "isolation_enforcement_enabled": False,
            "isolation_verification_enabled": False,
            "runtime_evidence_recording_enabled": False,
            "rogue_recovery_review_enabled": False,
            "rogue_recovery_ready": False,
            "halt_enabled": False,
            "quarantine_enabled": False,
            "replacement_enabled": False,
            "restore_enabled": False,
            "safe_delta_review_enabled": False,
            "safe_delta_flow_active": False,
            "sla_framework_ready": False,
            "sla_review_enabled": False,
            "sla_commitments_active": False,
            "monitoring_enabled": False,
            "paging_enabled": False,
            "support_tiers_enabled": False,
            "billing_entitlements_enabled": False,
            "creates_service_commitment": False,
            "pages_support": False,
            "opens_incident": False,
            "records_sla_receipt": False,
            "grants_support_authority": False,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return managed_copies_status_snapshot()


@router.get("/copy-creation-contract")
def copy_creation_contract() -> dict[str, Any]:
    return managed_copy_creation_contract_snapshot()


@router.post("/copy-creation-request")
def copy_creation_request(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    actor = _managed_copy_write_actor(payload)
    decision = _write_permission(
        actor,
        required_scope=MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
            next_step="configure_actor_scope_before_requesting_managed_copy_creation",
        )
    return managed_copy_creation_request_blocked_snapshot(payload, actor=actor)


@router.get("/isolation-rules-contract")
def isolation_rules_contract() -> dict[str, Any]:
    return managed_copy_isolation_rules_contract_snapshot()


@router.post("/isolation-verification")
def isolation_verification(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    actor = _managed_copy_write_actor(payload)
    decision = _write_permission(
        actor,
        required_scope=MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE,
            next_step="configure_actor_scope_before_verifying_managed_copy_isolation",
        )
    return managed_copy_isolation_verification_blocked_snapshot(payload, actor=actor)


@router.get("/safe-delta-model-contract")
def safe_delta_model_contract() -> dict[str, Any]:
    return managed_copy_safe_delta_model_contract_snapshot()


@router.post("/safe-delta-review")
def safe_delta_review(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    actor = _managed_copy_write_actor(payload)
    decision = _write_permission(
        actor,
        required_scope=MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE,
            next_step="configure_actor_scope_before_reviewing_managed_copy_safe_delta",
        )
    return managed_copy_safe_delta_review_blocked_snapshot(payload, actor=actor)


@router.get("/rogue-recovery-contract")
def rogue_recovery_contract() -> dict[str, Any]:
    return managed_copy_rogue_recovery_contract_snapshot()


@router.post("/rogue-recovery-review")
def rogue_recovery_review(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    actor = _managed_copy_write_actor(payload)
    decision = _write_permission(
        actor,
        required_scope=MANAGED_COPIES_ROGUE_RECOVERY_WRITE_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=MANAGED_COPIES_ROGUE_RECOVERY_WRITE_SCOPE,
            next_step="configure_actor_scope_before_reviewing_managed_copy_rogue_recovery",
        )
    return managed_copy_rogue_recovery_review_blocked_snapshot(payload, actor=actor)


@router.get("/sla-framework-contract")
def sla_framework_contract() -> dict[str, Any]:
    return managed_copy_sla_framework_contract_snapshot()


@router.post("/sla-commitment-review")
def sla_commitment_review(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    actor = _managed_copy_write_actor(payload)
    decision = _write_permission(
        actor,
        required_scope=MANAGED_COPIES_SLA_WRITE_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=MANAGED_COPIES_SLA_WRITE_SCOPE,
            next_step="configure_actor_scope_before_reviewing_managed_copy_sla_commitment",
        )
    return managed_copy_sla_commitment_review_blocked_snapshot(payload, actor=actor)


@router.get("/roles-contract")
def roles_contract() -> dict[str, Any]:
    return managed_copy_roles_contract_snapshot()


@router.get("/decommission-contract")
def decommission_contract() -> dict[str, Any]:
    return managed_copy_decommission_contract_snapshot()


@router.get("/completion-review")
def completion_review() -> dict[str, Any]:
    return managed_copy_completion_review_snapshot()


@router.get("/runtime-evidence-contract")
def runtime_evidence_contract() -> dict[str, Any]:
    return managed_copy_runtime_evidence_contract_snapshot()


@router.get("/runtime-evidence-readbacks")
def runtime_evidence_readbacks(limit: int = 100) -> dict[str, Any]:
    return managed_copy_runtime_evidence_readbacks_snapshot(limit=limit)


@router.post("/runtime-evidence-readback")
def runtime_evidence_readback(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    actor = _managed_copy_write_actor(payload)
    decision = _write_permission(
        actor,
        required_scope=MANAGED_COPIES_RUNTIME_EVIDENCE_WRITE_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not decision.allowed:
        return _permission_denied(
            decision,
            required_scope=MANAGED_COPIES_RUNTIME_EVIDENCE_WRITE_SCOPE,
            next_step="configure_actor_scope_before_recording_managed_copy_runtime_evidence",
        )
    return managed_copy_runtime_evidence_readback_blocked_snapshot(payload, actor=actor)
