from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from francis.lens import (
    deny_lens_host_activation_execution,
    deny_lens_host_supervision_authority_grant,
    deny_lens_resident_runtime_activation_execution,
    deny_lens_resident_runtime_execution_authority_grant,
    lens_host_activation_denial_receipts,
    lens_host_activation_execution_preflight,
    lens_host_activation_execution_plan,
    lens_host_activation_readback,
    lens_host_launch_manifest,
    lens_host_status,
    lens_host_supervision_authority_denial_receipts,
    lens_host_supervision_authority_preflight,
    lens_host_supervision_authority_readiness_audit,
    lens_host_supervision_gate,
    lens_overlay_enablement_gate,
    lens_preflight,
    lens_resident_runtime_authority_grant_denial_receipts,
    lens_resident_runtime_authority_grant_readiness_audit,
    lens_resident_runtime_activation_preflight,
    lens_resident_runtime_activation_plan,
    lens_resident_runtime_execution_policy_contract,
    lens_resident_surface_activation_boundary,
    lens_status,
    lens_summon_enablement_gate,
    lens_tray_enablement_gate,
    request_lens_host_activation,
)

router = APIRouter()


class LensHostActivationRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens host foreground activation"
    mode: str = Field(default="foreground_status_session")


class LensHostActivationExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens host foreground activation"


class LensResidentRuntimeExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens resident runtime activation"


class LensResidentRuntimeAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens resident runtime execution authority grant"


class LensHostSupervisionAuthorityGrantIn(BaseModel):
    actor: str | None = None
    reason: str = "attempt Lens host supervision authority grant"


@router.get("/status")
@router.get("/hud")
def status(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_status(limit=limit)


@router.get("/preflight")
def preflight() -> dict[str, Any]:
    return lens_preflight()


@router.get("/summon")
def summon() -> dict[str, Any]:
    return lens_summon_enablement_gate()


@router.get("/tray")
def tray() -> dict[str, Any]:
    return lens_tray_enablement_gate()


@router.get("/overlay")
def overlay() -> dict[str, Any]:
    return lens_overlay_enablement_gate()


@router.get("/host")
def host(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_host_status(limit=limit)


@router.get("/host/manifest")
def host_manifest() -> dict[str, Any]:
    return lens_host_launch_manifest()


@router.get("/host/supervision")
def host_supervision() -> dict[str, Any]:
    return lens_host_supervision_gate()


@router.get("/host/supervision/authority")
def host_supervision_authority() -> dict[str, Any]:
    return lens_host_supervision_authority_preflight()


@router.get("/host/supervision/authority/readiness")
def host_supervision_authority_readiness(
    limit: int = Query(5, ge=1, le=50),
    actor: str = "",
) -> dict[str, Any]:
    return lens_host_supervision_authority_readiness_audit(actor=actor, limit=limit)


@router.get("/host/supervision/authority/denials")
def host_supervision_authority_denials(
    limit: int = Query(5, ge=1, le=50),
    status: str = "",
) -> dict[str, Any]:
    return lens_host_supervision_authority_denial_receipts(limit=limit, status=status)


@router.post("/host/supervision/authority")
def host_supervision_authority_grant(
    request: Request,
    payload: LensHostSupervisionAuthorityGrantIn,
) -> dict[str, Any]:
    return deny_lens_host_supervision_authority_grant(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
    )


@router.get("/host/activation")
def host_activation(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_host_activation_readback(limit=limit)


@router.get("/host/activation/denials")
def host_activation_denials(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_host_activation_denial_receipts(limit=limit, approval_id=approval_id, status=status)


@router.get("/host/activation/preflight")
def host_activation_preflight(approval_id: str = "", actor: str = "") -> dict[str, Any]:
    return lens_host_activation_execution_preflight(approval_id=approval_id, actor=actor)


@router.get("/host/activation/plan")
def host_activation_plan(approval_id: str = "", actor: str = "") -> dict[str, Any]:
    return lens_host_activation_execution_plan(approval_id=approval_id, actor=actor)


@router.get("/resident-runtime/preflight")
def resident_runtime_preflight(approval_id: str = "", actor: str = "") -> dict[str, Any]:
    return lens_resident_runtime_activation_preflight(approval_id=approval_id, actor=actor)


@router.get("/resident-runtime/policy")
def resident_runtime_policy(approval_id: str = "", actor: str = "") -> dict[str, Any]:
    return lens_resident_runtime_execution_policy_contract(approval_id=approval_id, actor=actor)


@router.get("/resident-runtime/plan")
def resident_runtime_plan(approval_id: str = "", actor: str = "") -> dict[str, Any]:
    return lens_resident_runtime_activation_plan(approval_id=approval_id, actor=actor)


@router.get("/resident-runtime/authority-grant/denials")
def resident_runtime_authority_grant_denials(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_resident_runtime_authority_grant_denial_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
    )


@router.get("/resident-runtime/authority-grant/readiness")
def resident_runtime_authority_grant_readiness(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    actor: str = "",
) -> dict[str, Any]:
    return lens_resident_runtime_authority_grant_readiness_audit(
        approval_id=approval_id,
        actor=actor,
        limit=limit,
    )


@router.post("/resident-runtime/authority-grant")
def resident_runtime_authority_grant(
    request: Request,
    payload: LensResidentRuntimeAuthorityGrantIn,
) -> dict[str, Any]:
    return deny_lens_resident_runtime_execution_authority_grant(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
    )


@router.post("/resident-runtime/execute")
def resident_runtime_execute(request: Request, payload: LensResidentRuntimeExecuteIn) -> dict[str, Any]:
    return deny_lens_resident_runtime_activation_execution(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.get("/resident-surface/activation")
def resident_surface_activation(
    approval_id: str = "",
    actor: str = "",
    limit: int = Query(5, ge=1, le=50),
) -> dict[str, Any]:
    return lens_resident_surface_activation_boundary(approval_id=approval_id, actor=actor, limit=limit)


@router.post("/host/activation/execute")
def host_activation_execute(request: Request, payload: LensHostActivationExecuteIn) -> dict[str, Any]:
    return deny_lens_host_activation_execution(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
    )


@router.post("/host/activation/request")
def host_activation_request(request: Request, payload: LensHostActivationRequestIn) -> dict[str, Any]:
    return request_lens_host_activation(
        actor=payload.actor,
        reason=payload.reason,
        mode=payload.mode,
        route=request.url.path,
        method=request.method,
    )
