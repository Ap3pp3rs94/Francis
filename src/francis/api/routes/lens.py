from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from francis.lens import (
    deny_lens_host_activation_execution,
    deny_lens_host_persistent_supervision_enablement,
    deny_lens_host_persistent_supervision_enablement_execution,
    deny_lens_resident_runtime_activation_execution,
    deny_lens_resident_runtime_execution_authority_grant,
    grant_lens_host_persistent_supervision_enablement_execution_authority,
    grant_lens_host_persistent_supervision_enablement_authority,
    grant_lens_host_supervision_authority,
    lens_host_activation_denial_receipts,
    lens_host_activation_execution_preflight,
    lens_host_activation_execution_plan,
    lens_host_activation_readback,
    lens_host_launch_manifest,
    lens_host_persistent_supervision_enablement_execution_authority_grant_receipts,
    lens_host_persistent_supervision_enablement_execution_readiness_audit,
    lens_host_persistent_supervision_enablement_execution_request_readback,
    lens_host_persistent_supervision_enablement_authority_readiness_audit,
    lens_host_persistent_supervision_enablement_authority_grant_receipts,
    lens_host_persistent_supervision_enablement_authority_request_readback,
    lens_host_persistent_supervision_enablement_preflight,
    lens_host_persistent_supervision_plan,
    lens_host_status,
    lens_host_supervision_authority_denial_receipts,
    lens_host_supervision_authority_grant_receipts,
    lens_host_supervision_authority_request_readback,
    lens_host_supervision_authority_preflight,
    lens_host_supervision_authority_readiness_audit,
    lens_host_supervision_gate,
    lens_overlay_enablement_gate,
    lens_resident_runtime_activation_denial_receipts,
    lens_preflight,
    lens_resident_runtime_authority_grant_denial_receipts,
    lens_resident_runtime_authority_grant_readiness_audit,
    lens_resident_runtime_execution_authority_request_readback,
    lens_resident_runtime_activation_preflight,
    lens_resident_runtime_activation_plan,
    lens_resident_runtime_execution_policy_contract,
    lens_resident_surface_activation_boundary,
    lens_resident_surface_readback,
    lens_status,
    lens_summon_enablement_gate,
    lens_tray_enablement_gate,
    request_lens_host_activation,
    request_lens_host_persistent_supervision_enablement_execution_authority,
    request_lens_host_persistent_supervision_enablement_authority,
    request_lens_host_supervision_authority,
    request_lens_resident_runtime_execution_authority,
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


class LensResidentRuntimeAuthorityRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens resident runtime execution authority review"


class LensHostSupervisionAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens host supervision authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


class LensHostSupervisionAuthorityRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens host supervision authority review"


class LensHostPersistentSupervisionEnablementIn(BaseModel):
    actor: str | None = None
    reason: str = "attempt Lens persistent supervision enablement"


class LensHostPersistentSupervisionEnablementAuthorityRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens persistent supervision enablement authority review"


class LensHostPersistentSupervisionEnablementAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens persistent supervision enablement authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


class LensHostPersistentSupervisionEnablementExecutionRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens persistent supervision execution authority review"


class LensHostPersistentSupervisionEnablementExecutionIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens persistent supervision execution enablement"


class LensHostPersistentSupervisionEnablementExecutionAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens persistent supervision execution authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


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


@router.get("/host/persistent-supervision")
def host_persistent_supervision() -> dict[str, Any]:
    return lens_host_persistent_supervision_plan()


@router.get("/host/persistent-supervision/enablement")
def host_persistent_supervision_enablement() -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_preflight()


@router.post("/host/persistent-supervision/enablement")
def host_persistent_supervision_enablement_denial(
    request: Request,
    payload: LensHostPersistentSupervisionEnablementIn,
) -> dict[str, Any]:
    return deny_lens_host_persistent_supervision_enablement(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.get("/host/persistent-supervision/enablement/authority/requests")
def host_persistent_supervision_enablement_authority_requests(
    limit: int = Query(5, ge=1, le=50),
) -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_authority_request_readback(limit=limit)


@router.get("/host/persistent-supervision/enablement/authority/grants")
def host_persistent_supervision_enablement_authority_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


@router.get("/host/persistent-supervision/enablement/authority/readiness")
def host_persistent_supervision_enablement_authority_readiness(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    actor: str = "",
) -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_authority_readiness_audit(
        approval_id=approval_id,
        actor=actor,
        limit=limit,
    )


@router.post("/host/persistent-supervision/enablement/authority")
def host_persistent_supervision_enablement_authority_grant(
    request: Request,
    payload: LensHostPersistentSupervisionEnablementAuthorityGrantIn,
) -> dict[str, Any]:
    return grant_lens_host_persistent_supervision_enablement_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
    )


@router.post("/host/persistent-supervision/enablement/authority/request")
def host_persistent_supervision_enablement_authority_request(
    request: Request,
    payload: LensHostPersistentSupervisionEnablementAuthorityRequestIn,
) -> dict[str, Any]:
    return request_lens_host_persistent_supervision_enablement_authority(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.get("/host/persistent-supervision/enablement/execution")
def host_persistent_supervision_enablement_execution(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    actor: str = "",
) -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_execution_readiness_audit(
        approval_id=approval_id,
        actor=actor,
        limit=limit,
    )


@router.post("/host/persistent-supervision/enablement/execution")
def host_persistent_supervision_enablement_execution_denial(
    request: Request,
    payload: LensHostPersistentSupervisionEnablementExecutionIn,
) -> dict[str, Any]:
    return deny_lens_host_persistent_supervision_enablement_execution(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.get("/host/persistent-supervision/enablement/execution/authority/grants")
def host_persistent_supervision_enablement_execution_authority_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_execution_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


@router.post("/host/persistent-supervision/enablement/execution/authority")
def host_persistent_supervision_enablement_execution_authority_grant(
    request: Request,
    payload: LensHostPersistentSupervisionEnablementExecutionAuthorityGrantIn,
) -> dict[str, Any]:
    return grant_lens_host_persistent_supervision_enablement_execution_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
    )


@router.get("/host/persistent-supervision/enablement/execution/requests")
def host_persistent_supervision_enablement_execution_requests(
    limit: int = Query(5, ge=1, le=50),
) -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_execution_request_readback(limit=limit)


@router.get("/host/persistent-supervision/enablement/execution/readiness")
def host_persistent_supervision_enablement_execution_readiness(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    actor: str = "",
) -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_execution_readiness_audit(
        approval_id=approval_id,
        actor=actor,
        limit=limit,
    )


@router.post("/host/persistent-supervision/enablement/execution/request")
def host_persistent_supervision_enablement_execution_request(
    request: Request,
    payload: LensHostPersistentSupervisionEnablementExecutionRequestIn,
) -> dict[str, Any]:
    return request_lens_host_persistent_supervision_enablement_execution_authority(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.get("/host/supervision/authority")
def host_supervision_authority() -> dict[str, Any]:
    return lens_host_supervision_authority_preflight()


@router.get("/host/supervision/authority/readiness")
def host_supervision_authority_readiness(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    actor: str = "",
) -> dict[str, Any]:
    return lens_host_supervision_authority_readiness_audit(approval_id=approval_id, actor=actor, limit=limit)


@router.get("/host/supervision/authority/requests")
def host_supervision_authority_requests(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_host_supervision_authority_request_readback(limit=limit)


@router.get("/host/supervision/authority/denials")
def host_supervision_authority_denials(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_host_supervision_authority_denial_receipts(limit=limit, approval_id=approval_id, status=status)


@router.get("/host/supervision/authority/grants")
def host_supervision_authority_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_host_supervision_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


@router.post("/host/supervision/authority/request")
def host_supervision_authority_request(
    request: Request,
    payload: LensHostSupervisionAuthorityRequestIn,
) -> dict[str, Any]:
    return request_lens_host_supervision_authority(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.post("/host/supervision/authority")
def host_supervision_authority_grant(
    request: Request,
    payload: LensHostSupervisionAuthorityGrantIn,
) -> dict[str, Any]:
    return grant_lens_host_supervision_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
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


@router.get("/resident-runtime/denials")
def resident_runtime_denials(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_resident_runtime_activation_denial_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
    )


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


@router.get("/resident-runtime/authority-grant/requests")
def resident_runtime_authority_grant_requests(
    limit: int = Query(5, ge=1, le=50),
) -> dict[str, Any]:
    return lens_resident_runtime_execution_authority_request_readback(limit=limit)


@router.post("/resident-runtime/authority-grant/request")
def resident_runtime_authority_grant_request(
    request: Request,
    payload: LensResidentRuntimeAuthorityRequestIn,
) -> dict[str, Any]:
    return request_lens_resident_runtime_execution_authority(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
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
        record_receipt=True,
    )


@router.get("/resident-surface")
def resident_surface(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_resident_surface_readback(limit=limit)


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
