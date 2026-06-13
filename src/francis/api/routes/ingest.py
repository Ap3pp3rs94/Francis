from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from francis.api.errors import api_error_message
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.ingest import IngestService

router = APIRouter()

_LAB_READBACK_SCOPE = "ingest.lab.readback"
_LAB_EXECUTE_RUN_SCOPE = "ingest.lab.execute.run"
_LAB_RECEIPT_WRITE_SCOPE = "ingest.lab.receipt.write"
_LAB_APPROVAL_CONSUME_SCOPE = "ingest.lab.approval.consume"
_LAB_NOOP_RUNNER_SCOPE = "ingest.lab.runner.noop"
_LAB_NOOP_RUNNER_TRANSCRIPT_SCOPE = "ingest.lab.runner.noop.transcript"
_LAB_NOOP_RUNNER_IDENTITY_SCOPE = "ingest.lab.runner.noop.identity"
_LAB_SOURCE_MOUNT_READINESS_SCOPE = "ingest.lab.source_mount.readiness"
_LAB_SOURCE_MOUNT_CONTRACT_SCOPE = "ingest.lab.source_mount.contract"
_LAB_SANDBOX_PROVIDER_CONTRACT_SCOPE = "ingest.lab.sandbox.provider_contract"
_LAB_SANDBOX_PROVIDER_BINDING_SCOPE = "ingest.lab.sandbox.provider_binding"
_LAB_SANDBOX_PROVIDER_SELECTION_SCOPE = "ingest.lab.sandbox.provider_selection"
_LAB_SANDBOX_PROVIDER_VERIFIER_SCOPE = "ingest.lab.sandbox.provider_verifier"
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_SCOPE = "ingest.lab.sandbox.provider_runtime_probe"
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_HARNESS_SCOPE = "ingest.lab.sandbox.provider_runtime_probe_harness"
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_READINESS_SCOPE = (
    "ingest.lab.sandbox.provider_runtime_probe_runner_readiness"
)
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_BINDING_SCOPE = "ingest.lab.sandbox.provider_runtime_probe_runner_binding"
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_ENFORCEMENT_SCOPE = (
    "ingest.lab.sandbox.provider_runtime_probe_runner_enforcement"
)
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_EXECUTION_BOUNDARY_SCOPE = (
    "ingest.lab.sandbox.provider_runtime_probe_execution_boundary"
)
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_REFUSAL_SCOPE = "ingest.lab.sandbox.provider_runtime_probe.refuse"
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_REQUEST_SCOPE = (
    "ingest.lab.sandbox.provider_runtime_probe.request_approval"
)
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_CONSUME_SCOPE = (
    "ingest.lab.sandbox.provider_runtime_probe.consume_approval"
)
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_INVOCATION_BOUNDARY_SCOPE = (
    "ingest.lab.sandbox.provider_runtime_probe.invocation_boundary"
)
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_PRE_EXECUTION_BOUNDARY_SCOPE = (
    "ingest.lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary"
)
_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_CONTROL_BINDING_SCOPE = (
    "ingest.lab.sandbox.provider_runtime_probe.runner_control_binding"
)
_LAB_SANDBOXED_REBUILD_RUN_TEST_BOUNDARY_SCOPE = "ingest.lab.sandboxed_rebuild_run_test.boundary"
_LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_REQUEST_SCOPE = "ingest.lab.sandboxed_rebuild_run_test.request_approval"
_LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_CONSUME_SCOPE = "ingest.lab.sandboxed_rebuild_run_test.consume_approval"
_LAB_SANDBOXED_REBUILD_RUN_TEST_RUNNER_BINDING_SCOPE = "ingest.lab.sandboxed_rebuild_run_test.runner_binding"
_LAB_SANDBOXED_REBUILD_RUN_TEST_SANDBOX_POLICY_SCOPE = "ingest.lab.sandboxed_rebuild_run_test.sandbox_policy"
_LAB_RUN_BOUNDARY_PREFLIGHT_SCOPE = "ingest.lab.run_boundary.preflight"


class LabApprovalConsumptionPreflightIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunnerReadinessIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunnerBindingIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunnerEnforcementIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabApprovalConsumptionHandoffIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabExecutionReceiptSinkReservationIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunnerCommandAllowlistBindingIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunnerCommandAllowlistDeclarationIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunnerCommandAllowlistEnforcementIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunnerSandboxReadinessIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderContractIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderBindingIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderSelectionIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    provider_kind: str | None = None
    provider_reference: str | None = None
    provider_policy_manifest: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderVerifierIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    provider_kind: str | None = None
    provider_reference: str | None = None
    provider_policy_manifest: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderRuntimeProbeIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    provider_kind: str | None = None
    provider_reference: str | None = None
    provider_policy_manifest: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderRuntimeProbeHarnessIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    provider_kind: str | None = None
    provider_reference: str | None = None
    provider_policy_manifest: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderRuntimeProbeRunnerReadinessIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    provider_kind: str | None = None
    provider_reference: str | None = None
    provider_policy_manifest: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderRuntimeProbeRunnerBindingIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    provider_kind: str | None = None
    provider_reference: str | None = None
    provider_policy_manifest: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderRuntimeProbeRunnerEnforcementIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    provider_kind: str | None = None
    provider_reference: str | None = None
    provider_policy_manifest: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabExecutionReceiptWriteReadinessIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabExecutionReceiptPrewriteBindingIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabExecutionReceiptWriterPreflightIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSyntheticExecutionReceiptIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabApprovalConsumeIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabNoopRunnerEnvelopeIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabNoopRunnerTranscriptIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabNoopRunnerIdentityBindingIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSourceMountReadinessIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSourceMountContractIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunBoundaryPreflightIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderRuntimeProbeExecutionBoundaryIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderRuntimeProbeRefusalIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    reason: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxProviderRuntimeProbeApprovalRequestIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    reason: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxedRebuildRunTestRunnerBindingIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    provider_kind: str | None = None
    provider_reference: str | None = None
    provider_policy_manifest: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxedRebuildRunTestSandboxPolicyIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabSandboxedRebuildRunTestApprovalRequestIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    reason: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class LabRunIn(BaseModel):
    source_or_path: str
    candidate: str
    approval_id: str
    opt_in: bool = False
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


def _permission_denied(
    decision: ApiPermissionDecision,
    *,
    kind: str = "francis.ingest.lab.approval_consumption_preflight",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_lab_readback",
            "evidence": decision.evidence,
        },
        "execution": {
            "executed": False,
            "execution_authority": False,
            "ran_repo_scripts": False,
            "network_accessed": False,
        },
    }


@router.get("/readback")
def readback(actor: str = "", source_id: str = "", limit: int = 100) -> dict[str, Any]:
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/readback",
        method="GET",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.readback")

    try:
        return IngestService().readback(source_id=source_id, limit=limit)
    except Exception as exc:
        return {
            "kind": "francis.ingest.readback",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/run")
def lab_run(payload: LabRunIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_EXECUTE_RUN_SCOPE],
        route="/ingest/lab/run",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.run")

    try:
        result = IngestService().run_lab_capability(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            opt_in=bool(payload.opt_in),
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.run", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.run",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/runner-command-allowlist-binding")
def lab_runner_command_allowlist_binding(payload: LabRunnerCommandAllowlistBindingIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/runner-command-allowlist-binding",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.runner_command_allowlist_binding")

    try:
        result = IngestService().preflight_lab_runner_command_allowlist_binding(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.runner_command_allowlist_binding", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.runner_command_allowlist_binding",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/runner-command-allowlist-declaration")
def lab_runner_command_allowlist_declaration(payload: LabRunnerCommandAllowlistDeclarationIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/runner-command-allowlist-declaration",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.runner_command_allowlist_declaration")

    try:
        result = IngestService().preflight_lab_runner_command_allowlist_declaration(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.runner_command_allowlist_declaration", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.runner_command_allowlist_declaration",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/runner-command-allowlist-enforcement")
def lab_runner_command_allowlist_enforcement(payload: LabRunnerCommandAllowlistEnforcementIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/runner-command-allowlist-enforcement",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.runner_command_allowlist_enforcement")

    try:
        result = IngestService().preflight_lab_runner_command_allowlist_enforcement(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.runner_command_allowlist_enforcement", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.runner_command_allowlist_enforcement",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/runner-sandbox-readiness")
def lab_runner_sandbox_readiness(payload: LabRunnerSandboxReadinessIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/runner-sandbox-readiness",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.runner_sandbox_readiness")

    try:
        result = IngestService().preflight_lab_runner_sandbox_readiness(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.runner_sandbox_readiness", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.runner_sandbox_readiness",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-contract")
def lab_sandbox_provider_contract(payload: LabSandboxProviderContractIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_CONTRACT_SCOPE],
        route="/ingest/lab/sandbox-provider-contract",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.sandbox_provider_contract")

    try:
        result = IngestService().preflight_lab_sandbox_provider_contract(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_contract", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_contract",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-binding")
def lab_sandbox_provider_binding(payload: LabSandboxProviderBindingIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_BINDING_SCOPE],
        route="/ingest/lab/sandbox-provider-binding",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.sandbox_provider_binding")

    try:
        result = IngestService().preflight_lab_sandbox_provider_binding(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_binding", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_binding",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-selection")
def lab_sandbox_provider_selection(payload: LabSandboxProviderSelectionIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_SELECTION_SCOPE],
        route="/ingest/lab/sandbox-provider-selection",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.sandbox_provider_selection")

    try:
        result = IngestService().preflight_lab_sandbox_provider_selection(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            provider_kind=payload.provider_kind or "",
            provider_reference=payload.provider_reference or "",
            provider_policy_manifest=payload.provider_policy_manifest or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_selection", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_selection",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-verifier")
def lab_sandbox_provider_verifier(payload: LabSandboxProviderVerifierIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_VERIFIER_SCOPE],
        route="/ingest/lab/sandbox-provider-verifier",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.sandbox_provider_verifier")

    try:
        result = IngestService().preflight_lab_sandbox_provider_verifier(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            provider_kind=payload.provider_kind or "",
            provider_reference=payload.provider_reference or "",
            provider_policy_manifest=payload.provider_policy_manifest or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_verifier", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_verifier",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe")
def lab_sandbox_provider_runtime_probe(payload: LabSandboxProviderRuntimeProbeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.sandbox_provider_runtime_probe")

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            provider_kind=payload.provider_kind or "",
            provider_reference=payload.provider_reference or "",
            provider_policy_manifest=payload.provider_policy_manifest or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-harness")
def lab_sandbox_provider_runtime_probe_harness(payload: LabSandboxProviderRuntimeProbeHarnessIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_HARNESS_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-harness",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.sandbox_provider_runtime_probe_harness")

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_harness(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            provider_kind=payload.provider_kind or "",
            provider_reference=payload.provider_reference or "",
            provider_policy_manifest=payload.provider_policy_manifest or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_harness", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_harness",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-runner-readiness")
def lab_sandbox_provider_runtime_probe_runner_readiness(
    payload: LabSandboxProviderRuntimeProbeRunnerReadinessIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_READINESS_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-runner-readiness",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_runner_readiness",
        )

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_readiness(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            provider_kind=payload.provider_kind or "",
            provider_reference=payload.provider_reference or "",
            provider_policy_manifest=payload.provider_policy_manifest or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_readiness", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_readiness",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-runner-binding")
def lab_sandbox_provider_runtime_probe_runner_binding(
    payload: LabSandboxProviderRuntimeProbeRunnerBindingIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_BINDING_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-runner-binding",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_runner_binding",
        )

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_binding(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            provider_kind=payload.provider_kind or "",
            provider_reference=payload.provider_reference or "",
            provider_policy_manifest=payload.provider_policy_manifest or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_binding", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_binding",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-runner-enforcement")
def lab_sandbox_provider_runtime_probe_runner_enforcement(
    payload: LabSandboxProviderRuntimeProbeRunnerEnforcementIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_ENFORCEMENT_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-runner-enforcement",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_runner_enforcement",
        )

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_enforcement(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            provider_kind=payload.provider_kind or "",
            provider_reference=payload.provider_reference or "",
            provider_policy_manifest=payload.provider_policy_manifest or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_enforcement", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_enforcement",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/execution-receipt-write-readiness")
def lab_execution_receipt_write_readiness(payload: LabExecutionReceiptWriteReadinessIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/execution-receipt-write-readiness",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.execution_receipt_write_readiness")

    try:
        result = IngestService().preflight_lab_execution_receipt_write_readiness(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.execution_receipt_write_readiness", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.execution_receipt_write_readiness",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/execution-receipt-prewrite-binding")
def lab_execution_receipt_prewrite_binding(payload: LabExecutionReceiptPrewriteBindingIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/execution-receipt-prewrite-binding",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.execution_receipt_prewrite_binding")

    try:
        result = IngestService().preflight_lab_execution_receipt_prewrite_binding(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.execution_receipt_prewrite_binding", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.execution_receipt_prewrite_binding",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/execution-receipt-writer-preflight")
def lab_execution_receipt_writer_preflight(payload: LabExecutionReceiptWriterPreflightIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/execution-receipt-writer-preflight",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.execution_receipt_writer_preflight")

    try:
        result = IngestService().preflight_lab_execution_receipt_writer(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.execution_receipt_writer_preflight", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.execution_receipt_writer_preflight",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/synthetic-execution-receipt-prewrite")
def lab_synthetic_execution_receipt_prewrite(payload: LabSyntheticExecutionReceiptIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_RECEIPT_WRITE_SCOPE],
        route="/ingest/lab/synthetic-execution-receipt-prewrite",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.synthetic_execution_receipt_prewrite")

    try:
        result = IngestService().prewrite_lab_synthetic_execution_receipt(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.synthetic_execution_receipt_prewrite", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.synthetic_execution_receipt_prewrite",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/synthetic-execution-receipt-finalize")
def lab_synthetic_execution_receipt_finalize(payload: LabSyntheticExecutionReceiptIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_RECEIPT_WRITE_SCOPE],
        route="/ingest/lab/synthetic-execution-receipt-finalize",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.synthetic_execution_receipt_finalize")

    try:
        result = IngestService().finalize_lab_synthetic_execution_receipt(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.synthetic_execution_receipt_finalize", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.synthetic_execution_receipt_finalize",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/approval-consume-synthetic-noop")
def lab_approval_consume_synthetic_noop(payload: LabApprovalConsumeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_APPROVAL_CONSUME_SCOPE],
        route="/ingest/lab/approval-consume-synthetic-noop",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.approval_consume_synthetic_noop")

    try:
        result = IngestService().consume_lab_approval_for_synthetic_execution_receipt(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.approval_consume_synthetic_noop", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.approval_consume_synthetic_noop",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/noop-runner-envelope")
def lab_noop_runner_envelope(payload: LabNoopRunnerEnvelopeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_NOOP_RUNNER_SCOPE],
        route="/ingest/lab/noop-runner-envelope",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.noop_runner_envelope")

    try:
        result = IngestService().run_lab_noop_runner_envelope(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.noop_runner_envelope", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.noop_runner_envelope",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/noop-runner-transcript")
def lab_noop_runner_transcript(payload: LabNoopRunnerTranscriptIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_NOOP_RUNNER_TRANSCRIPT_SCOPE],
        route="/ingest/lab/noop-runner-transcript",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.noop_runner_transcript")

    try:
        result = IngestService().capture_lab_noop_runner_transcript(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.noop_runner_transcript", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.noop_runner_transcript",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/noop-runner-identity-binding")
def lab_noop_runner_identity_binding(payload: LabNoopRunnerIdentityBindingIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_NOOP_RUNNER_IDENTITY_SCOPE],
        route="/ingest/lab/noop-runner-identity-binding",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.noop_runner_identity_binding")

    try:
        result = IngestService().bind_lab_noop_runner_identity(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.noop_runner_identity_binding", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.noop_runner_identity_binding",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/source-mount-readiness")
def lab_source_mount_readiness(payload: LabSourceMountReadinessIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SOURCE_MOUNT_READINESS_SCOPE],
        route="/ingest/lab/source-mount-readiness",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.source_mount_readiness")

    try:
        result = IngestService().preflight_lab_source_mount_readiness(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.source_mount_readiness", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.source_mount_readiness",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/source-mount-contract")
def lab_source_mount_contract(payload: LabSourceMountContractIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SOURCE_MOUNT_CONTRACT_SCOPE],
        route="/ingest/lab/source-mount-contract",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.source_mount_contract")

    try:
        result = IngestService().preflight_lab_source_mount_contract(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.source_mount_contract", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.source_mount_contract",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/run-boundary-preflight")
def lab_run_boundary_preflight(payload: LabRunBoundaryPreflightIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_RUN_BOUNDARY_PREFLIGHT_SCOPE],
        route="/ingest/lab/run-boundary-preflight",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.run_boundary_preflight")

    try:
        result = IngestService().preflight_lab_run_boundary(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.run_boundary_preflight", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.run_boundary_preflight",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-execution-boundary")
def lab_sandbox_provider_runtime_probe_execution_boundary(
    payload: LabSandboxProviderRuntimeProbeExecutionBoundaryIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_EXECUTION_BOUNDARY_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-execution-boundary",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_execution_boundary",
        )

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_execution_boundary(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_execution_boundary", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_execution_boundary",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-refuse")
def lab_sandbox_provider_runtime_probe_refuse(
    payload: LabSandboxProviderRuntimeProbeRefusalIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_REFUSAL_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-refuse",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_refusal",
        )

    try:
        result = IngestService().refuse_lab_sandbox_provider_runtime_probe(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
            reason=payload.reason or "sandbox_provider_runtime_probe_not_available",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_refusal", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_refusal",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-request-approval")
def lab_sandbox_provider_runtime_probe_request_approval(
    payload: LabSandboxProviderRuntimeProbeApprovalRequestIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_REQUEST_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-request-approval",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_approval_request",
        )

    try:
        result = IngestService().request_lab_sandbox_provider_runtime_probe_approval(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
            reason=payload.reason or "sandbox_provider_runtime_probe_requested",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_approval_request", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_approval_request",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-consume-approval")
def lab_sandbox_provider_runtime_probe_consume_approval(payload: LabApprovalConsumeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_CONSUME_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-consume-approval",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_approval_consume",
        )

    try:
        result = IngestService().consume_lab_sandbox_provider_runtime_probe_approval(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_approval_consume", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_approval_consume",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-invocation-boundary")
def lab_sandbox_provider_runtime_probe_invocation_boundary(payload: LabApprovalConsumeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_INVOCATION_BOUNDARY_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-invocation-boundary",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_invocation_boundary",
        )

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_invocation_boundary", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_invocation_boundary",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-runner-pre-execution-boundary")
def lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(payload: LabApprovalConsumeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_PRE_EXECUTION_BOUNDARY_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-runner-pre-execution-boundary",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary",
        )

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandbox-provider-runtime-probe-runner-control-binding")
def lab_sandbox_provider_runtime_probe_runner_control_binding(payload: LabApprovalConsumeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_CONTROL_BINDING_SCOPE],
        route="/ingest/lab/sandbox-provider-runtime-probe-runner-control-binding",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandbox_provider_runtime_probe_runner_control_binding",
        )

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_control_binding", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandbox_provider_runtime_probe_runner_control_binding",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandboxed-rebuild-run-test-boundary")
def lab_sandboxed_rebuild_run_test_boundary(payload: LabApprovalConsumeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOXED_REBUILD_RUN_TEST_BOUNDARY_SCOPE],
        route="/ingest/lab/sandboxed-rebuild-run-test-boundary",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandboxed_rebuild_run_test_boundary",
        )

    try:
        result = IngestService().preflight_lab_sandboxed_rebuild_run_test_boundary(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandboxed_rebuild_run_test_boundary", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandboxed_rebuild_run_test_boundary",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandboxed-rebuild-run-test-request-approval")
def lab_sandboxed_rebuild_run_test_request_approval(
    payload: LabSandboxedRebuildRunTestApprovalRequestIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_REQUEST_SCOPE],
        route="/ingest/lab/sandboxed-rebuild-run-test-request-approval",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandboxed_rebuild_run_test_approval_request",
        )

    try:
        result = IngestService().request_lab_sandboxed_rebuild_run_test_approval(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
            reason=payload.reason or "sandboxed_rebuild_run_test_requested",
        )
        return {"kind": "francis.ingest.lab.sandboxed_rebuild_run_test_approval_request", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandboxed_rebuild_run_test_approval_request",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandboxed-rebuild-run-test-consume-approval")
def lab_sandboxed_rebuild_run_test_consume_approval(payload: LabApprovalConsumeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_CONSUME_SCOPE],
        route="/ingest/lab/sandboxed-rebuild-run-test-consume-approval",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandboxed_rebuild_run_test_approval_consume",
        )

    try:
        result = IngestService().consume_lab_sandboxed_rebuild_run_test_approval(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandboxed_rebuild_run_test_approval_consume", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandboxed_rebuild_run_test_approval_consume",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandboxed-rebuild-run-test-runner-binding")
def lab_sandboxed_rebuild_run_test_runner_binding(
    payload: LabSandboxedRebuildRunTestRunnerBindingIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOXED_REBUILD_RUN_TEST_RUNNER_BINDING_SCOPE],
        route="/ingest/lab/sandboxed-rebuild-run-test-runner-binding",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandboxed_rebuild_run_test_runner_binding",
        )

    try:
        result = IngestService().preflight_lab_sandboxed_rebuild_run_test_runner_binding(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            provider_kind=payload.provider_kind or "local_process_sandbox",
            provider_reference=payload.provider_reference or "",
            provider_policy_manifest=payload.provider_policy_manifest or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandboxed_rebuild_run_test_runner_binding", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandboxed_rebuild_run_test_runner_binding",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/sandboxed-rebuild-run-test-sandbox-policy")
def lab_sandboxed_rebuild_run_test_sandbox_policy(
    payload: LabSandboxedRebuildRunTestSandboxPolicyIn,
) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_SANDBOXED_REBUILD_RUN_TEST_SANDBOX_POLICY_SCOPE],
        route="/ingest/lab/sandboxed-rebuild-run-test-sandbox-policy",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(
            permission,
            kind="francis.ingest.lab.sandboxed_rebuild_run_test_sandbox_policy",
        )

    try:
        result = IngestService().preflight_lab_sandboxed_rebuild_run_test_sandbox_policy(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.sandboxed_rebuild_run_test_sandbox_policy", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.sandboxed_rebuild_run_test_sandbox_policy",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/approval-consumption-preflight")
def lab_approval_consumption_preflight(payload: LabApprovalConsumptionPreflightIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/approval-consumption-preflight",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission)

    try:
        result = IngestService().preflight_lab_approval_consumption(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.approval_consumption_preflight", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.approval_consumption_preflight",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/runner-readiness")
def lab_runner_readiness(payload: LabRunnerReadinessIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/runner-readiness",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.runner_readiness")

    try:
        result = IngestService().preflight_lab_runner_readiness(
            payload.source_or_path,
            payload.candidate,
            approval_id=payload.approval_id or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.runner_readiness", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.runner_readiness",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/runner-binding")
def lab_runner_binding(payload: LabRunnerBindingIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/runner-binding",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.runner_binding")

    try:
        result = IngestService().preflight_lab_runner_binding(
            payload.source_or_path,
            payload.candidate,
            approval_id=payload.approval_id or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.runner_binding", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.runner_binding",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/runner-enforcement")
def lab_runner_enforcement(payload: LabRunnerEnforcementIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/runner-enforcement",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.runner_enforcement")

    try:
        result = IngestService().preflight_lab_runner_enforcement(
            payload.source_or_path,
            payload.candidate,
            approval_id=payload.approval_id or "",
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.runner_enforcement", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.runner_enforcement",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/approval-consumption-handoff")
def lab_approval_consumption_handoff(payload: LabApprovalConsumptionHandoffIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/approval-consumption-handoff",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.approval_consumption_handoff")

    try:
        result = IngestService().preflight_lab_approval_consumption_handoff(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.approval_consumption_handoff", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.approval_consumption_handoff",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


@router.post("/lab/execution-receipt-sink-reservation")
def lab_execution_receipt_sink_reservation(payload: LabExecutionReceiptSinkReservationIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_LAB_READBACK_SCOPE],
        route="/ingest/lab/execution-receipt-sink-reservation",
        method="POST",
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.lab.execution_receipt_sink_reservation")

    try:
        result = IngestService().preflight_lab_execution_receipt_sink_reservation(
            payload.source_or_path,
            payload.candidate,
            payload.approval_id,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.lab.execution_receipt_sink_reservation", **result}
    except Exception as exc:
        return {
            "kind": "francis.ingest.lab.execution_receipt_sink_reservation",
            "ok": False,
            "status": "failed",
            "error": api_error_message(exc),
            "execution": {
                "executed": False,
                "execution_authority": False,
                "ran_repo_scripts": False,
                "network_accessed": False,
            },
        }


# --------------------------------------------------------------------------- #
# Forge synthesis + acquisition corridor (governed, non-applying)
# --------------------------------------------------------------------------- #
_FORGE_SYNTHESIZE_SCOPE = "ingest.forge.synthesize"
_FORGE_REVIEW_SCOPE = "ingest.forge.review"
_FORGE_APPLY_SCOPE = "ingest.forge.apply.execute"
_FORGE_BIND_SCOPE = "ingest.forge.bind"
_ACQUIRE_SCOPE = "ingest.acquire"

_FORGE_NO_EXEC = {
    "executed": False,
    "execution_authority": False,
    "ran_repo_scripts": False,
    "network_accessed": False,
    "patch_applied": False,
    "wrote_to_repo": False,
}


class ForgeSynthesizeIn(BaseModel):
    source_or_path: str
    candidate: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class ForgeRunIn(BaseModel):
    run_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class ForgeReviewIn(BaseModel):
    source_or_path: str
    builder_run_id: str
    proposal_text: str = ""
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class ForgeDryrunIn(BaseModel):
    source_or_path: str
    builder_run_id: str
    approval_id: str
    proposal_text: str = ""
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class ForgeBindIn(BaseModel):
    source_or_path: str
    builder_run_id: str
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


class AcquireStartIn(BaseModel):
    source_or_path: str
    candidate: str | None = None
    opt_in: bool = False
    lab_image: str | None = None
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


def _forge_failed(kind: str, exc: Exception) -> dict[str, Any]:
    return {"kind": kind, "ok": False, "status": "failed", "error": api_error_message(exc), "execution": _FORGE_NO_EXEC}


@router.post("/forge/synthesize")
def forge_synthesize(payload: ForgeSynthesizeIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor, required_scopes=[_FORGE_SYNTHESIZE_SCOPE], route="/ingest/forge/synthesize", method="POST"
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.forge.synthesize")
    try:
        result = IngestService().synthesize_capability(
            payload.source_or_path, payload.candidate or "", actor=actor or "francis/system"
        )
        return {"kind": "francis.ingest.forge.synthesize", **result}
    except Exception as exc:
        return _forge_failed("francis.ingest.forge.synthesize", exc)


@router.post("/forge/continue")
def forge_continue(payload: ForgeRunIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor, required_scopes=[_FORGE_SYNTHESIZE_SCOPE], route="/ingest/forge/continue", method="POST"
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.forge.continue")
    try:
        result = IngestService().continue_synthesis_after_approval(payload.run_id, actor=actor or "francis/system")
        return {"kind": "francis.ingest.forge.continue", **result}
    except Exception as exc:
        return _forge_failed("francis.ingest.forge.continue", exc)


@router.post("/forge/review")
def forge_review(payload: ForgeReviewIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor, required_scopes=[_FORGE_REVIEW_SCOPE], route="/ingest/forge/review", method="POST"
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.forge.review")
    try:
        result = IngestService().review_builder_proposal(
            payload.source_or_path, payload.builder_run_id, payload.proposal_text, actor=actor or "francis/system"
        )
        return {"kind": "francis.ingest.forge.review", **result}
    except Exception as exc:
        return _forge_failed("francis.ingest.forge.review", exc)


@router.post("/forge/dryrun")
def forge_dryrun(payload: ForgeDryrunIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor, required_scopes=[_FORGE_APPLY_SCOPE], route="/ingest/forge/dryrun", method="POST"
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.forge.dryrun")
    try:
        result = IngestService().dryrun_forge_apply(
            payload.source_or_path,
            payload.builder_run_id,
            payload.approval_id,
            payload.proposal_text,
            actor=actor or "francis/system",
        )
        return {"kind": "francis.ingest.forge.dryrun", **result}
    except Exception as exc:
        return _forge_failed("francis.ingest.forge.dryrun", exc)


@router.post("/forge/bind")
def forge_bind(payload: ForgeBindIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor, required_scopes=[_FORGE_BIND_SCOPE], route="/ingest/forge/bind", method="POST"
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.forge.bind")
    try:
        result = IngestService().bind_synthesized_source(
            payload.source_or_path, payload.builder_run_id, actor=actor or "francis/system"
        )
        return {"kind": "francis.ingest.forge.bind", **result}
    except Exception as exc:
        return _forge_failed("francis.ingest.forge.bind", exc)


@router.post("/acquire/start")
def acquire_start(payload: AcquireStartIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor, required_scopes=[_ACQUIRE_SCOPE], route="/ingest/acquire/start", method="POST"
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.acquire.start")
    try:
        result = IngestService().acquire_source_candidate(
            payload.source_or_path,
            payload.candidate or "",
            opt_in=bool(payload.opt_in),
            actor=actor or "francis/system",
            lab_image=payload.lab_image or "",
        )
        return {"kind": "francis.ingest.acquire.start", **result}
    except Exception as exc:
        return _forge_failed("francis.ingest.acquire.start", exc)


@router.post("/acquire/continue")
def acquire_continue(payload: ForgeRunIn) -> dict[str, Any]:
    actor = payload.request_actor or payload.api_actor or payload.actor
    permission = ApiPermissionGate.from_env().check(
        actor_id=actor, required_scopes=[_ACQUIRE_SCOPE], route="/ingest/acquire/continue", method="POST"
    )
    if not permission.allowed:
        return _permission_denied(permission, kind="francis.ingest.acquire.continue")
    try:
        result = IngestService().continue_acquisition_after_approval(payload.run_id, actor=actor or "francis/system")
        return {"kind": "francis.ingest.acquire.continue", **result}
    except Exception as exc:
        return _forge_failed("francis.ingest.acquire.continue", exc)
