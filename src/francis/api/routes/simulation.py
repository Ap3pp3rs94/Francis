from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Request

from francis.compute_substrate import (
    MAX_VIRTUAL_WORKFIELD_NODES,
    MAX_VIRTUAL_WORKFIELD_RUNTIME_MS,
    MAX_VIRTUAL_WORKFIELD_UNITS,
    VirtualWorkfieldBudget,
    create_virtual_workfield_plan,
)
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

router = APIRouter()

_VIRTUAL_WORKFIELD_READ_SCOPE = "simulation:virtual-workfield:read"
_SAFE_PLAN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "ok": True,
        "route": "simulation",
        "status": "partial",
        "ready": False,
        "implemented_operations": [
            "status_readback",
            "virtual_workfield_contract_readback",
        ],
        "blockers": ["simulation_execution_adapter_not_implemented"],
        "governance": {
            "read_only": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


@router.get("/virtual-workfield")
def virtual_workfield(
    request: Request,
    actor: str = "",
    plan_id: str = "",
    workload: str = "francis_vr_compute_concept",
    work_units: int = 2400,
    virtual_node_count: int = 8,
    max_runtime_ms: int = 250,
    max_memory_mb: int = 128,
    cpu_weight: int = 25,
    approval_required: bool = False,
) -> dict[str, Any]:
    permission = _route_permission(
        actor=actor,
        required_scope=_VIRTUAL_WORKFIELD_READ_SCOPE,
        route=request.url.path,
        method=request.method,
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            required_scope=_VIRTUAL_WORKFIELD_READ_SCOPE,
            next_step="configure_actor_scope_before_virtual_workfield_readback",
        )

    clean_plan_id = _safe_plan_id(plan_id) if plan_id else ""
    if plan_id and not clean_plan_id:
        return _malformed_request("invalid_plan_id")

    try:
        budget = VirtualWorkfieldBudget(
            work_units=work_units,
            virtual_node_count=virtual_node_count,
            max_runtime_ms=max_runtime_ms,
            max_memory_mb=max_memory_mb,
            cpu_weight=cpu_weight,
            approval_required=approval_required,
        )
        plan = create_virtual_workfield_plan(
            plan_id=clean_plan_id or None,
            workload=workload,
            budget=budget,
        ).to_dict()
    except ValueError:
        return _malformed_request(
            _budget_denial_reason(
                work_units=work_units,
                virtual_node_count=virtual_node_count,
                max_runtime_ms=max_runtime_ms,
                max_memory_mb=max_memory_mb,
                cpu_weight=cpu_weight,
            )
        )

    return {
        "ok": True,
        "status": plan["status"],
        "error": "",
        "plan_id": plan["plan_id"],
        "plan": plan,
        "governance": _route_governance(
            extra={
                "virtual_workfield_readback_only": True,
                "phase_plane": "P6_SIMULATION",
                "compute_substrate_adapter_contract": True,
                "grants_execution_authority": False,
                "does_not_trigger_execution": True,
                "does_not_submit_compute_tasks": True,
                "does_not_consume_approval": True,
                "does_not_create_real_compute": True,
            },
        ),
    }


def _route_permission(
    *,
    actor: Any,
    required_scope: str,
    route: str,
    method: str,
) -> ApiPermissionDecision:
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
        "denial_reason": decision.reason,
        "governance": _route_governance(
            extra={
                "reason": decision.reason,
                "required_scope": required_scope,
                "next_step": next_step,
                "evidence": decision.evidence,
                "permission_gate": True,
                "uses_compute_substrate_service": False,
            },
        ),
    }


def _malformed_request(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "denied",
        "error": "malformed_request",
        "denial_reason": reason,
        "governance": _route_governance(
            extra={
                "reason": reason,
                "grants_execution_authority": False,
            },
        ),
    }


def _budget_denial_reason(
    *,
    work_units: int,
    virtual_node_count: int,
    max_runtime_ms: int,
    max_memory_mb: int,
    cpu_weight: int,
) -> str:
    if not 1 <= work_units <= MAX_VIRTUAL_WORKFIELD_UNITS:
        return "work_units_out_of_range"
    if not 1 <= virtual_node_count <= MAX_VIRTUAL_WORKFIELD_NODES:
        return "virtual_node_count_out_of_range"
    if not 1 <= max_runtime_ms <= MAX_VIRTUAL_WORKFIELD_RUNTIME_MS:
        return "max_runtime_ms_out_of_range"
    if not 1 <= max_memory_mb <= 1024:
        return "max_memory_mb_out_of_range"
    if not 1 <= cpu_weight <= 100:
        return "cpu_weight_out_of_range"
    return "invalid_virtual_workfield_budget"


def _route_governance(*, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    governance: dict[str, Any] = {
        "api_permission_gate": True,
        "internal_local_dev_only": True,
        "uses_compute_substrate_service": False,
        "calls_backend_directly": False,
        "calls_governor_directly": False,
        "mutates_receipts_directly": False,
        "mutates_approvals_directly": False,
        "mutates_status_directly": False,
        "stores_payload": False,
        "stores_output": False,
        "returns_raw_execution_output": False,
        "writes_memory": False,
        "long_term_memory_persistence": False,
        "live_learning_persistence": False,
        "model_training": False,
        "async_execution": False,
        "background_execution": False,
        "task_recovery": False,
        "task_resumability": False,
        "shell": False,
        "subprocess": False,
        "network_client": False,
        "gpu_execution": False,
        "daemon": False,
        "os_level_cpu_memory_enforcement": False,
    }
    if extra:
        governance.update(extra)
    return governance


def _safe_plan_id(value: Any) -> str:
    text = _safe_text(value, limit=160)
    return text if _SAFE_PLAN_ID_RE.fullmatch(text) else ""


def _safe_text(value: Any, *, limit: int = 240) -> str:
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    return text[:limit]
