from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from francis.lens import (
    deny_lens_os_binding_execution,
    deny_lens_host_persistent_supervision_enablement,
    deny_lens_host_persistent_supervision_enablement_execution,
    deny_lens_host_runtime_loop_execution,
    execute_lens_host_activation,
    execute_lens_host_persistent_supervision_enablement,
    execute_lens_host_supervision_once,
    execute_lens_resident_runtime_activation,
    execute_lens_os_binding,
    execute_lens_overlay_window,
    execute_lens_summon_action,
    execute_lens_tray_presence,
    grant_lens_os_binding_authority,
    grant_lens_overlay_authority,
    grant_lens_summon_authority,
    grant_lens_host_activation_authority,
    grant_lens_resident_runtime_execution_authority,
    grant_lens_host_persistent_supervision_enablement_execution_authority,
    grant_lens_host_persistent_supervision_enablement_authority,
    grant_lens_host_supervision_authority,
    grant_lens_tray_authority,
    lens_host_activation_denial_receipts,
    lens_host_activation_execution_receipts,
    lens_host_activation_authority_grant_receipts,
    lens_host_activation_execution_preflight,
    lens_host_activation_execution_plan,
    lens_host_activation_readback,
    lens_host_launch_manifest,
    lens_host_persistent_supervision_enablement_execution_authority_grant_receipts,
    lens_host_persistent_supervision_enablement_execution_receipts,
    lens_host_persistent_supervision_enablement_execution_readiness_audit,
    lens_host_persistent_supervision_enablement_execution_request_readback,
    lens_host_persistent_supervision_enablement_authority_readiness_audit,
    lens_host_persistent_supervision_enablement_authority_grant_receipts,
    lens_host_persistent_supervision_enablement_authority_request_readback,
    lens_host_persistent_supervision_enablement_preflight,
    lens_host_persistent_supervision_plan,
    lens_host_runtime_boundary,
    lens_host_runtime_implementation_plan,
    lens_host_runtime_loop_contract,
    lens_host_runtime_loop_denial_receipts,
    lens_host_runtime_loop_readiness_audit,
    lens_host_status,
    lens_host_supervision_authority_denial_receipts,
    lens_host_supervision_authority_grant_receipts,
    lens_host_supervision_authority_request_readback,
    lens_host_supervision_authority_preflight,
    lens_host_supervision_authority_readiness_audit,
    lens_host_supervision_execution_receipts,
    lens_host_supervision_gate,
    lens_os_binding_authority_grant_receipts,
    lens_os_binding_authority_request_contract,
    lens_os_binding_authority_request_readback,
    lens_os_binding_execution_denial_receipts,
    lens_os_binding_execution_receipts,
    lens_os_binding_execution_readiness_audit,
    lens_os_binding_implementation_plan,
    lens_os_binding_readiness,
    lens_overlay_authority_grant_receipts,
    lens_overlay_authority_request_readback,
    lens_overlay_enablement_gate,
    lens_overlay_window_execution_receipts,
    lens_resident_runtime_activation_denial_receipts,
    lens_resident_runtime_activation_execution_receipts,
    lens_preflight,
    lens_resident_runtime_authority_grant_denial_receipts,
    lens_resident_runtime_authority_grant_readiness_audit,
    lens_resident_runtime_execution_authority_grant_receipts,
    lens_resident_runtime_execution_authority_request_readback,
    lens_resident_runtime_activation_preflight,
    lens_resident_runtime_activation_plan,
    lens_resident_runtime_execution_policy_contract,
    lens_resident_surface_activation_boundary,
    lens_resident_surface_readback,
    lens_status,
    lens_summon_action_execution_receipts,
    lens_summon_authority_grant_receipts,
    lens_summon_authority_request_readback,
    lens_summon_enablement_gate,
    lens_tray_authority_grant_receipts,
    lens_tray_authority_request_contract,
    lens_tray_authority_request_readback,
    lens_tray_enablement_gate,
    lens_tray_presence_execution_receipts,
    request_lens_host_activation,
    request_lens_host_persistent_supervision_enablement_execution_authority,
    request_lens_host_persistent_supervision_enablement_authority,
    request_lens_host_supervision_authority,
    request_lens_os_binding_authority,
    request_lens_overlay_authority,
    request_lens_resident_runtime_execution_authority,
    request_lens_summon_authority,
    request_lens_tray_authority,
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
    run_seconds: int = Field(default=2, ge=1, le=10)


class LensHostActivationAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens host activation authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


class LensResidentRuntimeExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens resident runtime activation"
    run_seconds: int = Field(default=2, ge=1, le=10)


class LensHostRuntimeLoopExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens host runtime loop execution"


class LensResidentRuntimeAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens resident runtime execution authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


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


class LensHostSupervisionExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt bounded Lens resident host supervision"
    run_seconds: int = Field(default=2, ge=1, le=10)
    mode: str = Field(default="bounded_candidate")


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


class LensOsBindingAuthorityRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens OS-binding command palette authority review"


class LensOsBindingAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens OS-binding command palette authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


class LensOsBindingExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens OS-binding command palette execution"
    mode: str = Field(default="bind")
    run_seconds: int = Field(default=300, ge=0, le=3600)


class LensSummonAuthorityRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens summon action authority review"


class LensSummonAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens summon action authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


class LensSummonExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens summon action execution"
    mode: str = Field(default="launch")
    run_seconds: int = Field(default=5, ge=1, le=60)
    allow_launch: bool = False


class LensTrayAuthorityRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens tray presence authority review"


class LensTrayAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens tray presence authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


class LensTrayExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens tray presence execution"
    mode: str = Field(default="start")
    run_seconds: int = Field(default=300, ge=0, le=3600)


class LensOverlayAuthorityRequestIn(BaseModel):
    actor: str | None = None
    reason: str = "request Lens overlay window authority review"


class LensOverlayAuthorityGrantIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens overlay window authority grant"
    lease_seconds: int = Field(default=3600, ge=60, le=86400)


class LensOverlayExecuteIn(BaseModel):
    actor: str | None = None
    approval_id: str = ""
    reason: str = "attempt Lens overlay window execution"
    mode: str = Field(default="start")
    run_seconds: int = Field(default=300, ge=0, le=3600)


@router.get("/status")
@router.get("/hud")
def status(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_status(limit=limit)


@router.get("/preflight")
def preflight() -> dict[str, Any]:
    return lens_preflight()


@router.get("/os-binding/readiness")
def os_binding_readiness() -> dict[str, Any]:
    return lens_os_binding_readiness(
        authority_request_readback=lens_os_binding_authority_request_readback(),
    )


@router.get("/os-binding/plan")
def os_binding_plan() -> dict[str, Any]:
    return lens_os_binding_implementation_plan(
        authority_request_readback=lens_os_binding_authority_request_readback(),
    )


@router.get("/os-binding/authority")
def os_binding_authority() -> dict[str, Any]:
    return lens_os_binding_authority_request_contract()


@router.get("/os-binding/authority/requests")
def os_binding_authority_requests(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_os_binding_authority_request_readback(limit=limit)


@router.get("/os-binding/authority/grants")
def os_binding_authority_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_os_binding_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


@router.get("/os-binding/denials")
def os_binding_denials(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_os_binding_execution_denial_receipts(limit=limit, approval_id=approval_id, status=status)


@router.get("/os-binding/executions")
def os_binding_executions(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_os_binding_execution_receipts(limit=limit, approval_id=approval_id, status=status)


@router.get("/os-binding/execution/readiness")
def os_binding_execution_readiness(
    limit: int = Query(5, ge=1, le=50),
    actor: str = "",
) -> dict[str, Any]:
    return lens_os_binding_execution_readiness_audit(actor=actor, limit=limit)


@router.post("/os-binding/authority/request")
def os_binding_authority_request(
    request: Request,
    payload: LensOsBindingAuthorityRequestIn,
) -> dict[str, Any]:
    return request_lens_os_binding_authority(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.post("/os-binding/execute")
def os_binding_execute(
    request: Request,
    payload: LensOsBindingExecuteIn,
) -> dict[str, Any]:
    if not payload.approval_id:
        return deny_lens_os_binding_execution(
            actor=payload.actor,
            reason=payload.reason,
            route=request.url.path,
            method=request.method,
            record_receipt=True,
        )
    return execute_lens_os_binding(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        mode=payload.mode,
        run_seconds=payload.run_seconds,
    )


@router.post("/os-binding/authority")
def os_binding_authority_grant(
    request: Request,
    payload: LensOsBindingAuthorityGrantIn,
) -> dict[str, Any]:
    return grant_lens_os_binding_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
    )


@router.get("/summon/authority")
@router.get("/summon/authority/requests")
def summon_authority_requests(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_summon_authority_request_readback(limit=limit)


@router.get("/summon/authority/grants")
def summon_authority_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_summon_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


@router.get("/summon/executions")
def summon_executions(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_summon_action_execution_receipts(limit=limit, approval_id=approval_id, status=status)


@router.post("/summon/authority/request")
def summon_authority_request(
    request: Request,
    payload: LensSummonAuthorityRequestIn,
) -> dict[str, Any]:
    return request_lens_summon_authority(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.post("/summon/authority")
def summon_authority_grant(
    request: Request,
    payload: LensSummonAuthorityGrantIn,
) -> dict[str, Any]:
    return grant_lens_summon_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
    )


@router.post("/summon/execute")
def summon_execute(
    request: Request,
    payload: LensSummonExecuteIn,
) -> dict[str, Any]:
    return execute_lens_summon_action(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        mode=payload.mode,
        run_seconds=payload.run_seconds,
        allow_launch=payload.allow_launch,
    )


@router.get("/summon/readiness")
@router.get("/summon")
def summon() -> dict[str, Any]:
    return lens_summon_enablement_gate()


@router.get("/tray/readiness")
@router.get("/tray")
def tray() -> dict[str, Any]:
    return lens_tray_enablement_gate()


@router.get("/tray/authority")
def tray_authority() -> dict[str, Any]:
    return lens_tray_authority_request_contract()


@router.get("/tray/authority/requests")
def tray_authority_requests(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_tray_authority_request_readback(limit=limit)


@router.get("/tray/authority/grants")
def tray_authority_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_tray_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


@router.get("/tray/executions")
def tray_executions(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_tray_presence_execution_receipts(limit=limit, approval_id=approval_id, status=status)


@router.post("/tray/authority/request")
def tray_authority_request(
    request: Request,
    payload: LensTrayAuthorityRequestIn,
) -> dict[str, Any]:
    return request_lens_tray_authority(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.post("/tray/authority")
def tray_authority_grant(
    request: Request,
    payload: LensTrayAuthorityGrantIn,
) -> dict[str, Any]:
    return grant_lens_tray_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
    )


@router.post("/tray/execute")
def tray_execute(
    request: Request,
    payload: LensTrayExecuteIn,
) -> dict[str, Any]:
    return execute_lens_tray_presence(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        mode=payload.mode,
        run_seconds=payload.run_seconds,
    )


@router.get("/overlay/authority")
@router.get("/overlay/authority/requests")
def overlay_authority_requests(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_overlay_authority_request_readback(limit=limit)


@router.get("/overlay/authority/grants")
def overlay_authority_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_overlay_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


@router.get("/overlay/executions")
def overlay_executions(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_overlay_window_execution_receipts(limit=limit, approval_id=approval_id, status=status)


@router.post("/overlay/authority/request")
def overlay_authority_request(
    request: Request,
    payload: LensOverlayAuthorityRequestIn,
) -> dict[str, Any]:
    return request_lens_overlay_authority(
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
    )


@router.post("/overlay/authority")
def overlay_authority_grant(
    request: Request,
    payload: LensOverlayAuthorityGrantIn,
) -> dict[str, Any]:
    return grant_lens_overlay_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
    )


@router.post("/overlay/execute")
def overlay_execute(
    request: Request,
    payload: LensOverlayExecuteIn,
) -> dict[str, Any]:
    return execute_lens_overlay_window(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        mode=payload.mode,
        run_seconds=payload.run_seconds,
    )


@router.get("/overlay/readiness")
@router.get("/overlay")
def overlay() -> dict[str, Any]:
    return lens_overlay_enablement_gate()


@router.get("/host")
def host(limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    return lens_host_status(limit=limit)


@router.get("/host/manifest")
def host_manifest() -> dict[str, Any]:
    return lens_host_launch_manifest()


@router.get("/host/runtime-boundary")
def host_runtime_boundary() -> dict[str, Any]:
    return lens_host_runtime_boundary()


@router.get("/host/runtime-plan")
def host_runtime_plan() -> dict[str, Any]:
    return lens_host_runtime_implementation_plan()


@router.get("/host/runtime-loop")
def host_runtime_loop() -> dict[str, Any]:
    return lens_host_runtime_loop_contract()


@router.post("/host/runtime-loop/execute")
def host_runtime_loop_execute(request: Request, payload: LensHostRuntimeLoopExecuteIn) -> dict[str, Any]:
    return deny_lens_host_runtime_loop_execution(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
    )


@router.get("/host/runtime-loop/denials")
def host_runtime_loop_denials(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_host_runtime_loop_denial_receipts(limit=limit, approval_id=approval_id, status=status)


@router.get("/host/runtime-loop/readiness")
def host_runtime_loop_readiness(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    actor: str = "",
) -> dict[str, Any]:
    return lens_host_runtime_loop_readiness_audit(limit=limit, approval_id=approval_id, actor=actor)


@router.get("/host/supervision")
def host_supervision() -> dict[str, Any]:
    return lens_host_supervision_gate()


@router.post("/host/supervision/execute")
def host_supervision_execute(request: Request, payload: LensHostSupervisionExecuteIn) -> dict[str, Any]:
    return execute_lens_host_supervision_once(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        run_seconds=payload.run_seconds,
        mode=payload.mode,
    )


@router.get("/host/supervision/executions")
def host_supervision_executions(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_host_supervision_execution_receipts(limit=limit, approval_id=approval_id, status=status)


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


@router.post("/host/persistent-supervision/enablement/execution/apply")
def host_persistent_supervision_enablement_execution_apply(
    request: Request,
    payload: LensHostPersistentSupervisionEnablementExecutionIn,
) -> dict[str, Any]:
    return execute_lens_host_persistent_supervision_enablement(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
    )


@router.get("/host/persistent-supervision/enablement/executions")
def host_persistent_supervision_enablement_executions(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_host_persistent_supervision_enablement_execution_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
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


@router.get("/host/activation/executions")
def host_activation_executions(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_host_activation_execution_receipts(limit=limit, approval_id=approval_id, status=status)


@router.get("/host/activation/authority/grants")
def host_activation_authority_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_host_activation_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


@router.post("/host/activation/authority")
def host_activation_authority_grant(
    request: Request,
    payload: LensHostActivationAuthorityGrantIn,
) -> dict[str, Any]:
    return grant_lens_host_activation_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
    )


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


@router.get("/resident-runtime/executions")
def resident_runtime_executions(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
) -> dict[str, Any]:
    return lens_resident_runtime_activation_execution_receipts(
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


@router.get("/resident-runtime/authority-grant/grants")
def resident_runtime_authority_grant_grants(
    limit: int = Query(5, ge=1, le=50),
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> dict[str, Any]:
    return lens_resident_runtime_execution_authority_grant_receipts(
        limit=limit,
        approval_id=approval_id,
        status=status,
        active_only=active_only,
    )


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
    return grant_lens_resident_runtime_execution_authority(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        lease_seconds=payload.lease_seconds,
    )


@router.post("/resident-runtime/execute")
def resident_runtime_execute(request: Request, payload: LensResidentRuntimeExecuteIn) -> dict[str, Any]:
    return execute_lens_resident_runtime_activation(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        run_seconds=payload.run_seconds,
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
    return execute_lens_host_activation(
        approval_id=payload.approval_id,
        actor=payload.actor,
        reason=payload.reason,
        route=request.url.path,
        method=request.method,
        record_receipt=True,
        run_seconds=payload.run_seconds,
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
