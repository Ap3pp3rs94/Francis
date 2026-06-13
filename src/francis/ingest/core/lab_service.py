# mypy: disable-error-code=attr-defined
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from francis.governance import approvals

from ..lab.lab import current_lab_boundary
from ..lab.lab_runtime import (
    EXECUTION_MODE_REAL,
    LabExecutionRunReceipt,
    SandboxPlan,
    candidate_lab_safety,
    decide_promotion,
    detect_docker,
    validate_run,
)
from ..shared.models import (
    CapabilityCandidate,
    LabApprovalConsumptionHandoff,
    LabApprovalConsumptionPreflight,
    LabApprovalConsumptionRecord,
    LabApprovalRequestRecord,
    LabExecutionReceiptPrewriteBinding,
    LabExecutionReceiptSinkReservation,
    LabExecutionReceiptWriterPreflight,
    LabExecutionReceiptWriteReadiness,
    LabExecutionPreflight,
    LabExecutionRefusal,
    LabNoopRunnerEnvelope,
    LabNoopRunnerIdentityBinding,
    LabNoopRunnerTranscript,
    LabPermissionRequirement,
    LabPlan,
    LabRunBoundaryPreflight,
    LabRunnerBindingPreflight,
    LabRunnerCommandAllowlistBinding,
    LabRunnerCommandAllowlistDeclaration,
    LabRunnerCommandAllowlistEnforcementPreflight,
    LabRunnerContract,
    LabRunnerEnforcementPreflight,
    LabRunnerReadiness,
    LabRunnerSandboxReadiness,
    LabSandboxProviderBindingPreflight,
    LabSandboxProviderContract,
    LabSandboxProviderRuntimeProbeApprovalConsumption,
    LabSandboxProviderRuntimeProbeApprovalRequest,
    LabSandboxProviderRuntimeProbeExecutionBoundary,
    LabSandboxProviderRuntimeProbeHarnessPreflight,
    LabSandboxProviderRuntimeProbeInvocationBoundary,
    LabSandboxProviderRuntimeProbeRefusal,
    LabSandboxProviderRuntimeProbeRunnerBindingPreflight,
    LabSandboxProviderRuntimeProbeRunnerControlBinding,
    LabSandboxProviderRuntimeProbeRunnerEnforcementPreflight,
    LabSandboxProviderRuntimeProbeRunnerPreExecutionBoundary,
    LabSandboxProviderRuntimeProbeRunnerReadiness,
    LabSandboxProviderRuntimeProbePreflight,
    LabSandboxProviderSelectionPreflight,
    LabSandboxProviderVerifierPreflight,
    LabSandboxedRebuildRunTestApprovalConsumption,
    LabSandboxedRebuildRunTestApprovalRequest,
    LabSandboxedRebuildRunTestBoundary,
    LabSandboxedRebuildRunTestRunnerBindingPreflight,
    LabSandboxedRebuildRunTestSandboxPolicyPreflight,
    LabSourceMountContract,
    LabSourceMountReadiness,
    LabSyntheticExecutionReceipt,
    LabWorkspaceRecord,
    SourceRecord,
)
from .registry import ingest_artifact_root, lab_workspace_root, utc_now, write_ingest_record_artifact
from .service_base import _as_dict, _display_payload, _load_ingest_record_payload, _read_json, _safe_list, _safe_str

_PROVIDER_POLICY_MANIFEST_MAX_BYTES = 128 * 1024
_PROVIDER_REFERENCE_FILE_HASH_MAX_BYTES = 64 * 1024 * 1024
_PROVIDER_REFERENCE_DIRECTORY_MAX_ENTRIES = 256
_PROVIDER_REFERENCE_HASH_CHUNK_BYTES = 1024 * 1024


def _sha256_file(path: Path, *, max_bytes: int) -> tuple[str, int, str]:
    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        return "", 0, str(exc)
    if size_bytes > max_bytes:
        return "", size_bytes, f"file_too_large_to_hash:{size_bytes}>{max_bytes}"
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(_PROVIDER_REFERENCE_HASH_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        return "", size_bytes, str(exc)
    return "sha256:" + digest.hexdigest(), size_bytes, ""


def _safe_manifest_token(value: Any) -> str:
    clean = _safe_str(value).strip()
    if not clean or len(clean) > 80:
        return ""
    if not all(ch.isalnum() or ch in {"_", "-", ".", ":"} for ch in clean):
        return ""
    return clean


def _manifest_bool_false(payload: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = payload.get(key)
        if value is False:
            return True
    return False


def _looks_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        token in lowered for token in ("secret", "token", "password", "credential", "private", "apikey", "api_key")
    )


def _provider_reference_static_evidence(provider_reference: str) -> dict[str, Any]:
    clean = _safe_str(provider_reference).strip()
    metadata = _lab_provider_reference_metadata(clean)
    evidence: dict[str, Any] = {
        **metadata,
        "verification_mode": "static_reference_fingerprint_no_execution",
        "fingerprint": "",
        "fingerprint_algorithm": "sha256",
        "fingerprint_captured": False,
        "directory_entry_count": 0,
        "directory_fingerprint_truncated": False,
        "contents_persisted": False,
        "executed": False,
        "service_query_performed": False,
        "process_launched": False,
        "container_launched": False,
    }
    if not metadata.get("reference_verified"):
        return evidence
    path = Path(_safe_str(metadata.get("reference")))
    if metadata.get("is_file"):
        fingerprint, size_bytes, error = _sha256_file(path, max_bytes=_PROVIDER_REFERENCE_FILE_HASH_MAX_BYTES)
        evidence["size_bytes"] = size_bytes
        evidence["fingerprint"] = fingerprint
        evidence["fingerprint_captured"] = bool(fingerprint)
        evidence["contents_read_for_hash_only"] = bool(fingerprint)
        if error:
            evidence["error"] = error
        return evidence
    if metadata.get("is_dir"):
        digest = hashlib.sha256()
        entry_count = 0
        truncated = False
        try:
            for child in sorted(path.rglob("*"), key=lambda item: str(item).lower()):
                if entry_count >= _PROVIDER_REFERENCE_DIRECTORY_MAX_ENTRIES:
                    truncated = True
                    break
                try:
                    if not child.is_file():
                        continue
                    rel = child.relative_to(path).as_posix()
                    if any(_looks_sensitive_key(part) for part in rel.split("/")):
                        continue
                    stat = child.stat()
                except OSError:
                    continue
                digest.update(f"{rel}|{stat.st_size}\n".encode("utf-8", errors="replace"))
                entry_count += 1
        except OSError as exc:
            evidence["error"] = str(exc)
            return evidence
        evidence["directory_entry_count"] = entry_count
        evidence["directory_fingerprint_truncated"] = truncated
        evidence["fingerprint"] = "sha256:" + digest.hexdigest() if entry_count else ""
        evidence["fingerprint_captured"] = bool(entry_count)
    return evidence


def _provider_policy_manifest_static_evidence(provider_policy_manifest: str) -> dict[str, Any]:
    metadata = _lab_provider_policy_manifest_metadata(provider_policy_manifest)
    evidence: dict[str, Any] = {
        **metadata,
        "verification_mode": "static_policy_manifest_summary_no_secret_values",
        "manifest_hash": "",
        "manifest_hash_captured": False,
        "manifest_json_parsed": False,
        "manifest_keys": [],
        "sensitive_key_count": 0,
        "declared_provider_kind": "",
        "declared_provider_name": "",
        "declared_provider_version": "",
        "network_disabled_by_manifest": False,
        "direct_execution_disabled_by_manifest": False,
        "contents_persisted": False,
    }
    if not metadata.get("bound"):
        return evidence
    path = Path(_safe_str(metadata.get("path")))
    size_bytes = int(metadata.get("size_bytes") or 0)
    if size_bytes > _PROVIDER_POLICY_MANIFEST_MAX_BYTES:
        evidence["error"] = f"manifest_too_large_to_parse:{size_bytes}>{_PROVIDER_POLICY_MANIFEST_MAX_BYTES}"
        return evidence
    try:
        raw_bytes = path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    except Exception as exc:
        evidence["error"] = str(exc)
        return evidence
    if not isinstance(payload, dict):
        evidence["error"] = "manifest_root_not_object"
        return evidence
    evidence["manifest_hash"] = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    evidence["manifest_hash_captured"] = True
    evidence["manifest_json_parsed"] = True
    keys = [_safe_str(key).strip() for key in payload if _safe_str(key).strip()]
    safe_keys = [key for key in keys if not _looks_sensitive_key(key)]
    evidence["manifest_keys"] = sorted(safe_keys)[:50]
    evidence["sensitive_key_count"] = len(keys) - len(safe_keys)
    provider = _as_dict(payload.get("provider"))
    evidence["declared_provider_kind"] = _normalize_lab_sandbox_provider_kind(
        _safe_manifest_token(payload.get("provider_kind") or provider.get("kind"))
    )
    if evidence["declared_provider_kind"] == "unselected":
        evidence["declared_provider_kind"] = ""
    evidence["declared_provider_name"] = _safe_manifest_token(payload.get("provider_name") or provider.get("name"))
    evidence["declared_provider_version"] = _safe_manifest_token(
        payload.get("provider_version") or payload.get("version") or provider.get("version")
    )
    evidence["network_disabled_by_manifest"] = _manifest_bool_false(payload, "network", "network_enabled")
    evidence["direct_execution_disabled_by_manifest"] = _manifest_bool_false(payload, "execution", "execution_enabled")
    return evidence


def _lab_sandbox_provider_static_verification_payload(
    *,
    provider_selection: LabSandboxProviderSelectionPreflight,
    actor: str,
) -> dict[str, Any]:
    reference_evidence = _provider_reference_static_evidence(provider_selection.provider_reference)
    policy_evidence = _provider_policy_manifest_static_evidence(provider_selection.provider_policy_manifest_path)
    version = _safe_str(policy_evidence.get("declared_provider_version")).strip()
    provider_identity_material = {
        "provider_kind": provider_selection.selected_provider_kind,
        "provider_reference_kind": reference_evidence.get("reference_kind"),
        "provider_reference_fingerprint": reference_evidence.get("fingerprint"),
        "provider_policy_manifest_hash": policy_evidence.get("manifest_hash"),
        "provider_version": version,
    }
    provider_identity_fingerprint = (
        _stable_payload_hash(provider_identity_material)
        if reference_evidence.get("fingerprint_captured") and policy_evidence.get("manifest_hash_captured")
        else ""
    )
    verifier_identity = {
        "verifier_kind": "francis.lab.static_sandbox_provider_verifier",
        "verifier_version": "1",
        "verifier_mode": "static_identity_policy_verification_no_execution",
        "actor": _safe_str(actor).strip() or "francis/system",
        "receipt_operation": "lab.sandbox.provider_verifier.preflight",
        "executes_provider": False,
        "queries_provider_service": False,
        "launches_container": False,
        "runs_repository_code": False,
    }
    return {
        "verification_kind": "francis.lab.sandbox_provider_static_verification",
        "schema_version": 1,
        "verification_mode": "static_identity_policy_verification_no_execution",
        "verifier_identity": verifier_identity,
        "provider_identity": {
            **provider_identity_material,
            "provider_identity_fingerprint": provider_identity_fingerprint,
            "provider_identity_fingerprint_captured": bool(provider_identity_fingerprint),
            "static_identity_verification_performed": bool(provider_identity_fingerprint),
        },
        "provider_policy_manifest": policy_evidence,
        "provider_runtime_probe": {
            "status": "not_performed",
            "reason": "provider_runtime_probe_requires_future_governed_provider_runner",
            "provider_runtime_probe_performed": False,
            "service_query_performed": False,
            "process_launched": False,
            "container_launched": False,
        },
        "reference_evidence": reference_evidence,
        "verifier_implementation_bound": True,
        "verifier_identity_bound": True,
        "verifier_policy_bound": bool(policy_evidence.get("manifest_hash_captured")),
        "verifier_receipt_contract_bound": True,
        "provider_reference_fingerprint_captured": bool(reference_evidence.get("fingerprint_captured")),
        "provider_policy_manifest_hash_captured": bool(policy_evidence.get("manifest_hash_captured")),
        "provider_binary_or_service_verified": bool(provider_identity_fingerprint),
        "provider_runtime_probe_performed": False,
        "provider_version_captured": bool(version),
        "provider_identity_fingerprint_captured": bool(provider_identity_fingerprint),
        "service_query_performed": False,
        "process_launched": False,
        "container_launched": False,
        "network_accessed": False,
        "executed": False,
        "repo_code_executed": False,
        "wrote_to_repo": False,
    }


def _append_unique(items: list[str], *values: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in [*items, *values]:
        cleaned = _safe_str(item).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _lab_plan_id(source_id: str, candidate_id: str) -> str:
    digest = hashlib.sha256(f"{source_id}:{candidate_id}:francis_lab_plan_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_plan_{digest}"


def _lab_refusal_id(plan_id: str) -> str:
    return f"lab_refusal_{plan_id}_{uuid.uuid4().hex[:8]}"


def _lab_workspace_id(plan_id: str) -> str:
    digest = hashlib.sha256(f"{plan_id}:workspace_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_workspace_{digest}"


def _lab_preflight_id(plan_id: str, workspace_id: str) -> str:
    digest = hashlib.sha256(f"{plan_id}:{workspace_id}:preflight_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_preflight_{digest}"


def _lab_approval_request_id(preflight_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(f"{preflight_id}:{approval_id}:approval_request_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_approval_request_{digest}"


def _lab_runner_contract_id(preflight_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(f"{preflight_id}:{approval_id}:runner_contract_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_runner_contract_{digest}"


def _lab_approval_consumption_preflight_id(preflight_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(f"{preflight_id}:{approval_id}:approval_consumption_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_approval_consumption_{digest}"


def _lab_runner_readiness_id(preflight_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(f"{preflight_id}:{approval_id}:runner_readiness_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_runner_readiness_{digest}"


def _lab_runner_binding_preflight_id(readiness_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(f"{readiness_id}:{approval_id}:runner_binding_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_runner_binding_{digest}"


def _lab_runner_enforcement_preflight_id(binding_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(f"{binding_id}:{approval_id}:runner_enforcement_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_runner_enforcement_{digest}"


def _lab_approval_consumption_handoff_id(enforcement_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{enforcement_id}:{approval_id}:approval_consumption_handoff_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_approval_handoff_{digest}"


def _lab_execution_receipt_sink_reservation_id(handoff_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{handoff_id}:{approval_id}:execution_receipt_sink_reservation_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_receipt_sink_reservation_{digest}"


def _reserved_lab_execution_receipt_id(reservation_id: str) -> str:
    digest = hashlib.sha256(f"{reservation_id}:reserved_execution_receipt_v0".encode("utf-8")).hexdigest()[:16]
    return f"lab_execution_receipt_{digest}"


def _lab_runner_command_allowlist_binding_id(reservation_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{reservation_id}:{approval_id}:runner_command_allowlist_binding_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runner_command_allowlist_{digest}"


def _lab_runner_command_allowlist_declaration_id(command_allowlist_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{command_allowlist_id}:{approval_id}:runner_command_allowlist_declaration_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runner_command_allowlist_declaration_{digest}"


def _lab_runner_command_allowlist_enforcement_preflight_id(declaration_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{declaration_id}:{approval_id}:runner_command_allowlist_enforcement_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_cmd_allowlist_enforce_{digest}"


def _lab_runner_sandbox_readiness_id(allowlist_enforcement_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{allowlist_enforcement_id}:{approval_id}:runner_sandbox_readiness_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_sandbox_readiness_{digest}"


def _lab_sandbox_provider_contract_id(sandbox_readiness_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{sandbox_readiness_id}:{approval_id}:sandbox_provider_contract_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_sandbox_provider_contract_{digest}"


def _lab_sandbox_provider_binding_id(provider_contract_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{provider_contract_id}:{approval_id}:sandbox_provider_binding_preflight_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_sandbox_provider_binding_{digest}"


def _lab_sandbox_provider_selection_id(
    provider_binding_id: str,
    approval_id: str,
    provider_kind: str,
    provider_reference: str,
    provider_policy_manifest: str,
) -> str:
    digest = hashlib.sha256(
        (
            f"{provider_binding_id}:{approval_id}:{provider_kind}:"
            f"{provider_reference}:{provider_policy_manifest}:sandbox_provider_selection_preflight_v0"
        ).encode("utf-8", errors="replace")
    ).hexdigest()[:16]
    return f"lab_sandbox_provider_selection_{digest}"


def _lab_sandbox_provider_verifier_id(provider_selection_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{provider_selection_id}:{approval_id}:sandbox_provider_verifier_preflight_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_sandbox_provider_verifier_{digest}"


def _lab_sandbox_provider_runtime_probe_id(provider_verifier_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{provider_verifier_id}:{approval_id}:sandbox_provider_runtime_probe_preflight_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_sandbox_provider_runtime_probe_{digest}"


def _lab_sandbox_provider_runtime_probe_harness_id(runtime_probe_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{runtime_probe_id}:{approval_id}:sandbox_provider_runtime_probe_harness_preflight_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_sandbox_provider_runtime_probe_harness_{digest}"


def _lab_sandbox_provider_runtime_probe_runner_readiness_id(harness_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{harness_id}:{approval_id}:sandbox_provider_runtime_probe_runner_readiness_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_runner_ready_{digest}"


def _lab_sandbox_provider_runtime_probe_runner_binding_id(readiness_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{readiness_id}:{approval_id}:sandbox_provider_runtime_probe_runner_binding_preflight_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_runner_binding_{digest}"


def _lab_sandbox_provider_runtime_probe_runner_enforcement_id(binding_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{binding_id}:{approval_id}:sandbox_provider_runtime_probe_runner_enforcement_preflight_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_runner_enforcement_{digest}"


def _lab_execution_receipt_write_readiness_id(sandbox_readiness_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{sandbox_readiness_id}:{approval_id}:execution_receipt_write_readiness_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_receipt_write_ready_{digest}"


def _lab_execution_receipt_prewrite_binding_id(write_readiness_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{write_readiness_id}:{approval_id}:execution_receipt_prewrite_binding_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_receipt_prewrite_binding_{digest}"


def _lab_execution_receipt_writer_preflight_id(prewrite_binding_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{prewrite_binding_id}:{approval_id}:execution_receipt_writer_preflight_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_receipt_writer_preflight_{digest}"


def _lab_approval_consumption_record_id(approval_id: str, execution_receipt_id: str) -> str:
    digest = hashlib.sha256(
        f"{approval_id}:{execution_receipt_id}:approval_consumption_record_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_approval_consumed_{digest}"


def _lab_noop_runner_envelope_id(approval_consumption_id: str, source_id: str, candidate_id: str) -> str:
    digest = hashlib.sha256(
        f"{approval_consumption_id}:{source_id}:{candidate_id}:noop_runner_envelope_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_noop_runner_envelope_{digest}"


def _lab_noop_runner_transcript_id(noop_runner_envelope_id: str, source_id: str, candidate_id: str) -> str:
    digest = hashlib.sha256(
        f"{noop_runner_envelope_id}:{source_id}:{candidate_id}:noop_runner_transcript_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_noop_runner_transcript_{digest}"


def _lab_noop_runner_identity_binding_id(noop_runner_transcript_id: str, source_id: str, candidate_id: str) -> str:
    digest = hashlib.sha256(
        f"{noop_runner_transcript_id}:{source_id}:{candidate_id}:noop_runner_identity_binding_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_noop_runner_identity_{digest}"


def _lab_source_mount_readiness_id(
    identity_binding_id: str,
    workspace_id: str,
    source_id: str,
    candidate_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{identity_binding_id}:{workspace_id}:{source_id}:{candidate_id}:source_mount_readiness_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_source_mount_readiness_{digest}"


def _lab_source_mount_contract_id(source_mount_readiness_id: str, source_id: str, candidate_id: str) -> str:
    digest = hashlib.sha256(
        f"{source_mount_readiness_id}:{source_id}:{candidate_id}:source_mount_contract_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_source_mount_contract_{digest}"


def _lab_run_boundary_preflight_id(source_mount_contract_id: str, writer_preflight_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{source_mount_contract_id}:{writer_preflight_id}:{approval_id}:run_boundary_preflight_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_run_boundary_{digest}"


def _lab_sandbox_provider_runtime_probe_execution_boundary_id(run_boundary_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{run_boundary_id}:{approval_id}:sandbox_provider_runtime_probe_execution_boundary_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_execution_boundary_{digest}"


def _lab_sandbox_provider_runtime_probe_refusal_id(execution_boundary_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{execution_boundary_id}:{approval_id}:sandbox_provider_runtime_probe_refusal_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_refusal_{digest}"


def _lab_sandbox_provider_runtime_probe_approval_request_id(
    execution_boundary_id: str,
    approval_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{execution_boundary_id}:{approval_id}:sandbox_provider_runtime_probe_approval_request_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_approval_request_{digest}"


def _lab_sandbox_provider_runtime_probe_approval_consumption_id(
    approval_id: str,
    approval_request_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{approval_id}:{approval_request_id}:sandbox_provider_runtime_probe_approval_consumption_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_approval_consumed_{digest}"


def _lab_sandbox_provider_runtime_probe_invocation_boundary_id(
    approval_consumption_id: str,
    execution_boundary_id: str,
) -> str:
    digest = hashlib.sha256(
        (
            f"{approval_consumption_id}:{execution_boundary_id}:sandbox_provider_runtime_probe_invocation_boundary_v0"
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_invocation_boundary_{digest}"


def _lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_id(
    invocation_boundary_id: str,
    approval_id: str,
) -> str:
    digest = hashlib.sha256(
        (
            f"{invocation_boundary_id}:{approval_id}:sandbox_provider_runtime_probe_runner_pre_execution_boundary_v0"
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_runtime_probe_preexec_boundary_{digest}"


def _lab_sandbox_provider_runtime_probe_runner_control_binding_id(
    pre_execution_boundary_id: str,
    approval_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{pre_execution_boundary_id}:{approval_id}:sandbox_provider_runtime_probe_runner_control_binding_v0".encode(
            "utf-8"
        )
    ).hexdigest()[:16]
    return f"lab_runtime_probe_ctrl_binding_{digest}"


def _lab_sandboxed_rebuild_run_test_boundary_id(control_binding_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{control_binding_id}:{approval_id}:sandboxed_rebuild_run_test_boundary_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_sandboxed_run_boundary_{digest}"


def _lab_sandboxed_rebuild_run_test_approval_request_id(boundary_id: str, approval_id: str) -> str:
    digest = hashlib.sha256(
        f"{boundary_id}:{approval_id}:sandboxed_rebuild_run_test_approval_request_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_sandboxed_run_approval_request_{digest}"


def _lab_sandboxed_rebuild_run_test_approval_consumption_id(approval_id: str, approval_request_id: str) -> str:
    digest = hashlib.sha256(
        f"{approval_id}:{approval_request_id}:sandboxed_rebuild_run_test_approval_consumption_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_srt_approval_used_{digest}"


def _lab_sandboxed_rebuild_run_test_runner_binding_id(
    approval_consumption_id: str,
    provider_kind: str,
    provider_reference: str,
    provider_policy_manifest: str,
) -> str:
    digest = hashlib.sha256(
        (
            f"{approval_consumption_id}:{provider_kind}:{provider_reference}:"
            f"{provider_policy_manifest}:sandboxed_rebuild_run_test_runner_binding_v0"
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_srt_runner_bind_{digest}"


def _lab_sandboxed_rebuild_run_test_sandbox_policy_id(runner_binding_id: str, action_hash: str) -> str:
    digest = hashlib.sha256(
        f"{runner_binding_id}:{action_hash}:sandboxed_rebuild_run_test_sandbox_policy_v0".encode("utf-8")
    ).hexdigest()[:16]
    return f"lab_srt_sandbox_policy_{digest}"


def _stable_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8", errors="replace"
    )
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _lab_exact_action_payload(
    *,
    source: SourceRecord,
    plan: LabPlan,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "action": "francis.lab.execute",
        "source_id": source.id,
        "source_type": source.type,
        "source_fingerprint": source.fingerprint,
        "candidate_id": plan.candidate_id,
        "candidate_name": plan.candidate_name,
        "plan_id": plan.id,
        "workspace_id": workspace.id,
        "workspace_path": workspace.path,
        "suggested_commands": list(plan.suggested_commands),
        "permissions_required": plan.permissions_required.to_dict(),
        "network_blocked_by_default": plan.permissions_required.network_blocked_by_default,
        "approval_scope": plan.permissions_required.approval_scope,
        "source_reference_mode": workspace.source_reference.get("mode"),
        "source_copied": workspace.source_copied,
    }


def _read_lab_approval_record(approval_id: str) -> tuple[str, dict[str, Any], Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return "invalid", {}, None
    for status, folder in (
        ("approved", approvals.approved_dir()),
        ("pending", approvals.pending_dir()),
        ("rejected", approvals.rejected_dir()),
        ("emergency", approvals.emergency_dir()),
    ):
        path = folder / f"{cleaned}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return "corrupt", {}, path
        return status, payload if isinstance(payload, dict) else {}, path
    return "missing", {}, None


def _find_lab_approval_consumption(approval_id: str) -> tuple[LabApprovalConsumptionRecord | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_approval_consumptions"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabApprovalConsumptionRecord.from_dict(_as_dict(_read_json(path).get("approval_consumption_record")))
        if record is None:
            continue
        if record.approval_id == cleaned and record.status == "consumed" and record.approval_consumed:
            return record, path
    return None, None


def _find_lab_sandbox_provider_runtime_probe_approval_request(
    approval_id: str,
) -> tuple[LabSandboxProviderRuntimeProbeApprovalRequest | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_runtime_probe_approval_requests"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxProviderRuntimeProbeApprovalRequest.from_dict(
            _as_dict(_read_json(path).get("sandbox_provider_runtime_probe_approval_request"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned:
            return record, path
    return None, None


def _find_lab_sandbox_provider_runtime_probe_approval_consumption(
    approval_id: str,
) -> tuple[LabSandboxProviderRuntimeProbeApprovalConsumption | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_runtime_probe_approval_consumptions"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxProviderRuntimeProbeApprovalConsumption.from_dict(
            _as_dict(_read_json(path).get("sandbox_provider_runtime_probe_approval_consumption"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned and record.status == "consumed" and record.approval_consumed:
            return record, path
    return None, None


def _find_lab_sandbox_provider_runtime_probe_execution_boundary(
    execution_boundary_id: str,
) -> tuple[LabSandboxProviderRuntimeProbeExecutionBoundary | None, Path | None]:
    cleaned = _safe_str(execution_boundary_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_runtime_probe_execution_boundaries"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxProviderRuntimeProbeExecutionBoundary.from_dict(
            _as_dict(_read_json(path).get("sandbox_provider_runtime_probe_execution_boundary"))
        )
        if record is None:
            continue
        if record.id == cleaned:
            return record, path
    return None, None


def _find_lab_sandbox_provider_runtime_probe_invocation_boundary(
    approval_id: str,
) -> tuple[LabSandboxProviderRuntimeProbeInvocationBoundary | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_runtime_probe_invocation_boundaries"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxProviderRuntimeProbeInvocationBoundary.from_dict(
            _as_dict(_read_json(path).get("sandbox_provider_runtime_probe_invocation_boundary"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned:
            return record, path
    return None, None


def _find_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
    approval_id: str,
) -> tuple[LabSandboxProviderRuntimeProbeRunnerPreExecutionBoundary | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_runtime_probe_preexec_boundaries"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxProviderRuntimeProbeRunnerPreExecutionBoundary.from_dict(
            _as_dict(_read_json(path).get("sandbox_provider_runtime_probe_runner_pre_execution_boundary"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned:
            return record, path
    return None, None


def _find_lab_sandbox_provider_runtime_probe_runner_control_binding(
    approval_id: str,
) -> tuple[LabSandboxProviderRuntimeProbeRunnerControlBinding | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_runtime_probe_control_bindings"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxProviderRuntimeProbeRunnerControlBinding.from_dict(
            _as_dict(_read_json(path).get("sandbox_provider_runtime_probe_runner_control_binding"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned:
            return record, path
    return None, None


def _find_lab_sandboxed_rebuild_run_test_boundary(
    approval_id: str,
) -> tuple[LabSandboxedRebuildRunTestBoundary | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_sandboxed_rebuild_run_test_boundaries"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxedRebuildRunTestBoundary.from_dict(
            _as_dict(_read_json(path).get("sandboxed_rebuild_run_test_boundary"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned:
            return record, path
    return None, None


def _find_lab_sandboxed_rebuild_run_test_boundary_by_id(
    boundary_id: str,
) -> tuple[LabSandboxedRebuildRunTestBoundary | None, Path | None]:
    cleaned = _safe_str(boundary_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_sandboxed_rebuild_run_test_boundaries"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxedRebuildRunTestBoundary.from_dict(
            _as_dict(_read_json(path).get("sandboxed_rebuild_run_test_boundary"))
        )
        if record is None:
            continue
        if record.id == cleaned:
            return record, path
    return None, None


def _find_lab_sandboxed_rebuild_run_test_approval_request(
    approval_id: str,
) -> tuple[LabSandboxedRebuildRunTestApprovalRequest | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_sandboxed_rebuild_run_test_approval_requests"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxedRebuildRunTestApprovalRequest.from_dict(
            _as_dict(_read_json(path).get("sandboxed_rebuild_run_test_approval_request"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned:
            return record, path
    return None, None


def _find_lab_sandboxed_rebuild_run_test_approval_consumption(
    approval_id: str,
) -> tuple[LabSandboxedRebuildRunTestApprovalConsumption | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_sandboxed_rebuild_run_test_approval_consumptions"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxedRebuildRunTestApprovalConsumption.from_dict(
            _as_dict(_read_json(path).get("sandboxed_rebuild_run_test_approval_consumption"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned and record.status == "consumed" and record.approval_consumed:
            return record, path
    return None, None


def _find_lab_sandboxed_rebuild_run_test_runner_binding(
    approval_id: str,
) -> tuple[LabSandboxedRebuildRunTestRunnerBindingPreflight | None, Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_sandboxed_rebuild_run_test_runner_bindings"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabSandboxedRebuildRunTestRunnerBindingPreflight.from_dict(
            _as_dict(_read_json(path).get("sandboxed_rebuild_run_test_runner_binding"))
        )
        if record is None:
            continue
        if record.approval_id == cleaned:
            return record, path
    return None, None


def _find_lab_noop_runner_envelope(
    approval_consumption_record_id: str,
) -> tuple[LabNoopRunnerEnvelope | None, Path | None]:
    cleaned = _safe_str(approval_consumption_record_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_noop_runner_envelopes"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabNoopRunnerEnvelope.from_dict(_as_dict(_read_json(path).get("noop_runner_envelope")))
        if record is None:
            continue
        if record.approval_consumption_record_id == cleaned and record.status == "completed":
            return record, path
    return None, None


def _find_lab_noop_runner_transcript(
    noop_runner_envelope_id: str,
) -> tuple[LabNoopRunnerTranscript | None, Path | None]:
    cleaned = _safe_str(noop_runner_envelope_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_noop_runner_transcripts"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabNoopRunnerTranscript.from_dict(_as_dict(_read_json(path).get("noop_runner_transcript")))
        if record is None:
            continue
        if record.noop_runner_envelope_id == cleaned and record.status == "completed":
            return record, path
    return None, None


def _find_lab_noop_runner_identity_binding(
    noop_runner_transcript_id: str,
) -> tuple[LabNoopRunnerIdentityBinding | None, Path | None]:
    cleaned = _safe_str(noop_runner_transcript_id).strip()
    if not cleaned:
        return None, None
    artifact_root = ingest_artifact_root() / "lab_noop_runner_identity_bindings"
    if not artifact_root.exists():
        return None, None
    for path in sorted(artifact_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = LabNoopRunnerIdentityBinding.from_dict(_as_dict(_read_json(path).get("noop_runner_identity_binding")))
        if record is None:
            continue
        if record.noop_runner_transcript_id == cleaned and record.status == "completed":
            return record, path
    return None, None


def _lab_noop_runner_envelope_required_checks() -> list[str]:
    return [
        "approval_consumption_record_found",
        "approval_consumed",
        "single_use_enforced",
        "noop_runner_envelope_not_already_completed",
        "source_identity_matches_consumption",
        "candidate_identity_matches_consumption",
        "action_hash_present",
        "synthetic_execution_receipt_present",
        "synthetic_execution_receipt_finalized",
        "synthetic_execution_receipt_noop",
        "synthetic_execution_receipt_no_repo_execution",
        "builtin_noop_runner_only",
        "commands_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_authority_absent",
    ]


def _lab_noop_runner_envelope_current_checks(
    *,
    source: SourceRecord,
    candidate: CapabilityCandidate,
    approval_id: str,
    consumption: LabApprovalConsumptionRecord | None,
    synthetic: LabSyntheticExecutionReceipt | None,
    envelope_path: Path,
) -> dict[str, Any]:
    prior_envelope, prior_path = _find_lab_noop_runner_envelope(
        consumption.id if consumption is not None else "",
    )
    source_matches = bool(consumption is not None and consumption.source_id == source.id)
    candidate_matches = bool(
        consumption is not None
        and consumption.candidate_id == candidate.id
        and consumption.candidate_name == candidate.name
    )
    no_repo_execution = bool(
        synthetic is not None
        and not synthetic.executed
        and not synthetic.repo_code_executed
        and not synthetic.ran_repo_scripts
        and not synthetic.ran_install
        and not synthetic.ran_build
        and not synthetic.ran_tests
        and not synthetic.network_accessed
        and not synthetic.wrote_to_repo
    )
    return {
        "approval_id": approval_id,
        "approval_consumption_record_found": consumption is not None,
        "approval_consumption_record_id": consumption.id if consumption is not None else "",
        "approval_consumed": bool(consumption and consumption.approval_consumed),
        "single_use_enforced": bool(consumption and consumption.single_use_enforced),
        "noop_runner_envelope_not_already_completed": prior_envelope is None,
        "prior_noop_runner_envelope_path": str(prior_path) if prior_path is not None else "",
        "source_identity_matches_consumption": source_matches,
        "candidate_identity_matches_consumption": candidate_matches,
        "action_hash_present": bool(consumption and consumption.action_hash),
        "synthetic_execution_receipt_present": synthetic is not None,
        "synthetic_execution_receipt_id": synthetic.id if synthetic is not None else "",
        "synthetic_execution_receipt_finalized": bool(synthetic and synthetic.finalized),
        "synthetic_execution_receipt_noop": bool(synthetic and synthetic.synthetic and synthetic.noop),
        "synthetic_execution_receipt_no_repo_execution": no_repo_execution,
        "builtin_noop_runner_only": True,
        "commands_not_executed": True,
        "network_not_accessed": True,
        "repo_write_not_performed": True,
        "execution_authority_absent": True,
        "envelope_path": str(envelope_path),
        "envelope_artifact_kind": "francis.lab.noop_runner_envelope",
        "executed": False,
        "execution_authority": False,
        "repo_code_executed": False,
        "network_accessed": False,
        "wrote_to_repo": False,
    }


def _noop_output_stream(stream: str) -> dict[str, Any]:
    return {
        "stream": stream,
        "source": "builtin_noop_no_process",
        "bytes": 0,
        "line_count": 0,
        "sha256": "sha256:" + hashlib.sha256(b"").hexdigest(),
        "content_stored": False,
        "truncated": False,
        "redacted": False,
    }


def _noop_combined_output_hash(stdout: dict[str, Any], stderr: dict[str, Any]) -> str:
    return _stable_payload_hash(
        {
            "stdout_sha256": _safe_str(stdout.get("sha256")).strip(),
            "stderr_sha256": _safe_str(stderr.get("sha256")).strip(),
            "capture_mode": "builtin_noop_empty_output",
        }
    )


def _lab_noop_runner_transcript_required_checks() -> list[str]:
    return [
        "noop_runner_envelope_found",
        "noop_runner_envelope_completed",
        "noop_runner_envelope_builtin_noop",
        "noop_runner_envelope_not_repo_execution",
        "noop_runner_transcript_not_already_completed",
        "source_identity_matches_envelope",
        "candidate_identity_matches_envelope",
        "stdout_empty_declared",
        "stderr_empty_declared",
        "output_content_not_stored",
        "real_process_output_not_claimed",
        "commands_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_authority_absent",
    ]


def _lab_noop_runner_transcript_current_checks(
    *,
    source: SourceRecord,
    candidate: CapabilityCandidate,
    envelope: LabNoopRunnerEnvelope | None,
    transcript_path: Path,
    stdout: dict[str, Any],
    stderr: dict[str, Any],
) -> dict[str, Any]:
    prior_transcript, prior_path = _find_lab_noop_runner_transcript(envelope.id if envelope is not None else "")
    source_matches = bool(envelope is not None and envelope.source_id == source.id)
    candidate_matches = bool(
        envelope is not None and envelope.candidate_id == candidate.id and envelope.candidate_name == candidate.name
    )
    envelope_no_repo_execution = bool(
        envelope is not None
        and not envelope.executed
        and not envelope.commands_executed
        and not envelope.repo_code_executed
        and not envelope.ran_repo_scripts
        and not envelope.ran_install
        and not envelope.ran_build
        and not envelope.ran_tests
        and not envelope.network_accessed
        and not envelope.wrote_to_repo
    )
    stdout_empty = stdout.get("bytes") == 0 and stdout.get("content_stored") is False
    stderr_empty = stderr.get("bytes") == 0 and stderr.get("content_stored") is False
    return {
        "noop_runner_envelope_found": envelope is not None,
        "noop_runner_envelope_id": envelope.id if envelope is not None else "",
        "noop_runner_envelope_completed": bool(envelope and envelope.status == "completed"),
        "noop_runner_envelope_builtin_noop": bool(
            envelope and envelope.runner_mode == "builtin_noop_only" and envelope.noop_performed
        ),
        "noop_runner_envelope_not_repo_execution": envelope_no_repo_execution,
        "noop_runner_transcript_not_already_completed": prior_transcript is None,
        "prior_noop_runner_transcript_path": str(prior_path) if prior_path is not None else "",
        "source_identity_matches_envelope": source_matches,
        "candidate_identity_matches_envelope": candidate_matches,
        "stdout_empty_declared": stdout_empty,
        "stderr_empty_declared": stderr_empty,
        "output_content_not_stored": not bool(stdout.get("content_stored")) and not bool(stderr.get("content_stored")),
        "real_process_output_not_claimed": True,
        "commands_not_executed": True,
        "network_not_accessed": True,
        "repo_write_not_performed": True,
        "execution_authority_absent": True,
        "transcript_path": str(transcript_path),
        "transcript_artifact_kind": "francis.lab.noop_runner_transcript",
        "stdout_sha256": _safe_str(stdout.get("sha256")).strip(),
        "stderr_sha256": _safe_str(stderr.get("sha256")).strip(),
        "executed": False,
        "execution_authority": False,
        "repo_code_executed": False,
        "network_accessed": False,
        "wrote_to_repo": False,
    }


def _noop_runner_identity_payload() -> dict[str, Any]:
    return {
        "runner_id": "francis.lab.runner.builtin_noop.v0",
        "runner_kind": "francis.lab.noop_runner",
        "runner_mode": "builtin_noop_only",
        "runner_version": "v0",
        "allowed_operations": [
            "complete_builtin_noop_envelope",
            "record_empty_builtin_noop_transcript",
            "bind_builtin_noop_runner_identity",
        ],
        "denied_operations": [
            "execute_repository_command",
            "run_repository_script",
            "install_dependencies",
            "build_repository",
            "run_repository_tests",
            "capture_real_process_output",
            "access_network",
            "write_source_repository",
            "validate_capability",
            "promote_capability",
        ],
        "execution_authority": False,
        "live_runner_bound": False,
        "sandbox_runner_bound": False,
    }


def _lab_noop_runner_identity_binding_required_checks() -> list[str]:
    return [
        "noop_runner_transcript_found",
        "noop_runner_transcript_completed",
        "noop_runner_transcript_builtin_noop",
        "noop_runner_transcript_no_real_output",
        "noop_runner_transcript_not_repo_execution",
        "noop_runner_envelope_found",
        "noop_runner_envelope_completed",
        "noop_runner_identity_not_already_completed",
        "source_identity_matches_transcript",
        "candidate_identity_matches_transcript",
        "runner_identity_builtin_noop",
        "runner_identity_denies_repo_execution",
        "live_runner_not_bound",
        "sandbox_runner_not_bound",
        "commands_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_authority_absent",
    ]


def _lab_noop_runner_identity_binding_current_checks(
    *,
    source: SourceRecord,
    candidate: CapabilityCandidate,
    transcript: LabNoopRunnerTranscript | None,
    envelope: LabNoopRunnerEnvelope | None,
    binding_path: Path,
    runner_identity: dict[str, Any],
) -> dict[str, Any]:
    prior_binding, prior_path = _find_lab_noop_runner_identity_binding(transcript.id if transcript is not None else "")
    source_matches = bool(transcript is not None and transcript.source_id == source.id)
    candidate_matches = bool(
        transcript is not None
        and transcript.candidate_id == candidate.id
        and transcript.candidate_name == candidate.name
    )
    transcript_no_repo_execution = bool(
        transcript is not None
        and not transcript.executed
        and not transcript.commands_executed
        and not transcript.repo_code_executed
        and not transcript.ran_repo_scripts
        and not transcript.ran_install
        and not transcript.ran_build
        and not transcript.ran_tests
        and not transcript.network_accessed
        and not transcript.wrote_to_repo
    )
    raw_denied_operations = runner_identity.get("denied_operations")
    denied_operations = {
        _safe_str(item).strip() for item in (raw_denied_operations if isinstance(raw_denied_operations, list) else [])
    }
    return {
        "noop_runner_transcript_found": transcript is not None,
        "noop_runner_transcript_id": transcript.id if transcript is not None else "",
        "noop_runner_transcript_completed": bool(transcript and transcript.status == "completed"),
        "noop_runner_transcript_builtin_noop": bool(
            transcript and transcript.capture_mode == "builtin_noop_empty_output" and transcript.noop_performed
        ),
        "noop_runner_transcript_no_real_output": bool(
            transcript and not transcript.real_process_output_captured and not transcript.output_content_stored
        ),
        "noop_runner_transcript_not_repo_execution": transcript_no_repo_execution,
        "noop_runner_envelope_found": envelope is not None,
        "noop_runner_envelope_id": envelope.id if envelope is not None else "",
        "noop_runner_envelope_completed": bool(envelope and envelope.status == "completed"),
        "noop_runner_identity_not_already_completed": prior_binding is None,
        "prior_noop_runner_identity_binding_path": str(prior_path) if prior_path is not None else "",
        "source_identity_matches_transcript": source_matches,
        "candidate_identity_matches_transcript": candidate_matches,
        "runner_identity_builtin_noop": runner_identity.get("runner_id") == "francis.lab.runner.builtin_noop.v0",
        "runner_identity_denies_repo_execution": "execute_repository_command" in denied_operations,
        "live_runner_not_bound": not bool(runner_identity.get("live_runner_bound")),
        "sandbox_runner_not_bound": not bool(runner_identity.get("sandbox_runner_bound")),
        "commands_not_executed": True,
        "network_not_accessed": True,
        "repo_write_not_performed": True,
        "execution_authority_absent": not bool(runner_identity.get("execution_authority")),
        "identity_binding_path": str(binding_path),
        "identity_binding_artifact_kind": "francis.lab.noop_runner_identity_binding",
        "executed": False,
        "execution_authority": False,
        "repo_code_executed": False,
        "network_accessed": False,
        "wrote_to_repo": False,
    }


def _lab_source_mount_readiness_required_checks() -> list[str]:
    return [
        "source_path_found",
        "workspace_record_found",
        "workspace_manifest_path_present",
        "workspace_source_reference_present",
        "source_reference_identity_matches_source",
        "source_reference_mode_read_only",
        "workspace_source_not_copied",
        "workspace_source_write_not_allowed",
        "noop_runner_identity_binding_found",
        "noop_runner_identity_binding_completed",
        "identity_binding_source_matches_source",
        "identity_binding_candidate_matches_candidate",
        "noop_runner_identity_builtin_noop",
        "noop_runner_identity_no_live_runner",
        "noop_runner_identity_no_sandbox_runner",
        "noop_runner_identity_no_repo_execution",
        "read_only_mount_not_bound",
        "source_mount_enforcement_not_claimed",
        "source_write_not_allowed",
        "commands_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_authority_absent",
    ]


def _lab_source_mount_readiness_current_checks(
    *,
    source: SourceRecord,
    candidate: CapabilityCandidate,
    workspace: LabWorkspaceRecord,
    identity: LabNoopRunnerIdentityBinding | None,
) -> dict[str, Any]:
    source_reference = _as_dict(workspace.source_reference)
    workspace_policy = _as_dict(workspace.workspace_policy)
    canonical_source = _safe_str(source.canonical_path).strip()
    manifest_path = _safe_str(workspace.manifest_path).strip()
    identity_no_repo_execution = bool(
        identity is not None
        and not identity.executed
        and not identity.commands_executed
        and not identity.repo_code_executed
        and not identity.ran_repo_scripts
        and not identity.ran_install
        and not identity.ran_build
        and not identity.ran_tests
        and not identity.network_accessed
        and not identity.wrote_to_repo
    )
    source_write_allowed = bool(source.permissions.write or workspace_policy.get("source_write_allowed"))
    return {
        "source_path_found": bool(canonical_source and Path(canonical_source).exists()),
        "workspace_record_found": True,
        "workspace_id": workspace.id,
        "workspace_path": workspace.path,
        "workspace_manifest_path_present": bool(manifest_path and Path(manifest_path).exists()),
        "workspace_source_reference_present": bool(source_reference),
        "source_reference_identity_matches_source": _safe_str(source_reference.get("source_id")).strip() == source.id,
        "source_reference_mode_read_only": _safe_str(source_reference.get("mode")).strip()
        == "reference_only_read_only",
        "workspace_source_not_copied": not bool(workspace.source_copied)
        and not bool(source_reference.get("contents_copied")),
        "workspace_source_write_not_allowed": not bool(workspace_policy.get("source_write_allowed")),
        "noop_runner_identity_binding_found": identity is not None,
        "noop_runner_identity_binding_id": identity.id if identity is not None else "",
        "noop_runner_identity_binding_completed": bool(identity and identity.status == "completed"),
        "identity_binding_source_matches_source": bool(identity and identity.source_id == source.id),
        "identity_binding_candidate_matches_candidate": bool(
            identity is not None and identity.candidate_id == candidate.id and identity.candidate_name == candidate.name
        ),
        "noop_runner_identity_builtin_noop": bool(
            identity
            and identity.runner_id == "francis.lab.runner.builtin_noop.v0"
            and identity.builtin_noop_only
            and identity.runner_identity_bound
        ),
        "noop_runner_identity_no_live_runner": bool(identity and not identity.live_runner_bound),
        "noop_runner_identity_no_sandbox_runner": bool(identity and not identity.sandbox_runner_bound),
        "noop_runner_identity_no_repo_execution": identity_no_repo_execution,
        "read_only_mount_not_bound": True,
        "source_mount_enforcement_not_claimed": True,
        "source_write_not_allowed": not source_write_allowed,
        "commands_not_executed": True,
        "network_not_accessed": True,
        "repo_write_not_performed": True,
        "execution_authority_absent": bool(identity is None or not identity.execution_authority),
        "read_only_mount_bound": False,
        "source_mount_enforced": False,
        "source_copied": False,
        "source_write_allowed": source_write_allowed,
        "executed": False,
        "execution_authority": False,
        "repo_code_executed": False,
        "network_accessed": False,
        "wrote_to_repo": False,
    }


def _lab_source_mount_contract_required_checks() -> list[str]:
    return [
        "source_mount_readiness_found",
        "source_mount_readiness_ready",
        "source_mount_readiness_source_matches_source",
        "source_mount_readiness_candidate_matches_candidate",
        "workspace_manifest_path_present",
        "source_reference_present",
        "source_reference_identity_matches_source",
        "source_reference_fingerprint_matches_source",
        "source_reference_mode_read_only",
        "contract_kind_declared",
        "contract_mode_declared_no_live_mount",
        "mount_mode_declared_future_read_only",
        "allowed_read_root_declared",
        "denied_write_root_declared",
        "workspace_write_root_declared",
        "read_only_mount_not_bound",
        "source_mount_enforcement_not_claimed",
        "source_copy_not_performed",
        "source_write_not_allowed",
        "live_runner_not_bound",
        "sandbox_runner_not_bound",
        "commands_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_authority_absent",
    ]


def _lab_source_mount_contract_payload(
    *,
    source: SourceRecord,
    candidate: CapabilityCandidate,
    workspace: LabWorkspaceRecord,
    readiness: LabSourceMountReadiness,
) -> dict[str, Any]:
    workspace_policy = _as_dict(workspace.workspace_policy)
    source_reference = _as_dict(workspace.source_reference)
    allowed_write_subdirs = [
        _safe_str(item).strip()
        for item in (workspace_policy.get("allowed_write_subdirs") or [])
        if _safe_str(item).strip()
    ]
    return {
        "contract_kind": "francis.lab.source_mount_contract",
        "schema_version": 1,
        "mode": "contract_only_no_live_mount",
        "mount_mode": "future_read_only_source_mount",
        "source_id": source.id,
        "source_type": source.type,
        "source_fingerprint": source.fingerprint,
        "canonical_source_path": source.canonical_path,
        "candidate_id": candidate.id,
        "candidate_name": candidate.name,
        "workspace_id": workspace.id,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "source_mount_readiness_id": readiness.id,
        "source_reference": source_reference,
        "allowed_read_roots": [source.canonical_path],
        "denied_write_roots": [source.canonical_path],
        "workspace_write_root": _safe_str(workspace_policy.get("workspace_write_root")).strip() or workspace.path,
        "allowed_workspace_write_subdirs": allowed_write_subdirs,
        "requires": [
            "os_readonly_mount_or_equivalent",
            "path_escape_prevention",
            "source_write_denial",
            "symlink_escape_denial",
            "sensitive_value_redaction",
            "mount_lifetime_bound_to_lab_run",
            "audit_receipts",
            "network_blocked_by_default",
        ],
        "live_mount_bound": False,
        "mount_enforced": False,
        "read_only_mount_bound": False,
        "source_copied": False,
        "source_write_allowed": False,
        "live_runner_bound": False,
        "sandbox_runner_bound": False,
        "execution_authority": False,
        "executed": False,
        "commands_executed": False,
        "repo_code_executed": False,
        "network_accessed": False,
        "wrote_to_repo": False,
        "candidate_validated": False,
        "capability_promoted": False,
        "store_file_contents": False,
        "store_sensitive_values": False,
    }


def _lab_source_mount_contract_current_checks(
    *,
    source: SourceRecord,
    candidate: CapabilityCandidate,
    workspace: LabWorkspaceRecord,
    readiness: LabSourceMountReadiness,
    contract_payload: dict[str, Any],
) -> dict[str, Any]:
    source_reference = _as_dict(workspace.source_reference)
    workspace_policy = _as_dict(workspace.workspace_policy)
    canonical_source = _safe_str(source.canonical_path).strip()
    manifest_path = _safe_str(workspace.manifest_path).strip()
    allowed_read_roots = [
        _safe_str(item).strip()
        for item in _safe_list(contract_payload.get("allowed_read_roots"))
        if _safe_str(item).strip()
    ]
    denied_write_roots = [
        _safe_str(item).strip()
        for item in _safe_list(contract_payload.get("denied_write_roots"))
        if _safe_str(item).strip()
    ]
    return {
        "source_mount_readiness_found": bool(readiness.id),
        "source_mount_readiness_id": readiness.id,
        "source_mount_readiness_ready": readiness.status == "ready",
        "source_mount_readiness_source_matches_source": readiness.source_id == source.id,
        "source_mount_readiness_candidate_matches_candidate": readiness.candidate_id == candidate.id,
        "workspace_manifest_path_present": bool(manifest_path and Path(manifest_path).exists()),
        "source_reference_present": bool(source_reference),
        "source_reference_identity_matches_source": _safe_str(source_reference.get("source_id")).strip() == source.id,
        "source_reference_fingerprint_matches_source": _safe_str(source_reference.get("fingerprint")).strip()
        == source.fingerprint,
        "source_reference_mode_read_only": _safe_str(source_reference.get("mode")).strip()
        == "reference_only_read_only",
        "contract_kind_declared": _safe_str(contract_payload.get("contract_kind")).strip()
        == "francis.lab.source_mount_contract",
        "contract_mode_declared_no_live_mount": _safe_str(contract_payload.get("mode")).strip()
        == "contract_only_no_live_mount",
        "mount_mode_declared_future_read_only": _safe_str(contract_payload.get("mount_mode")).strip()
        == "future_read_only_source_mount",
        "allowed_read_root_declared": bool(canonical_source and canonical_source in allowed_read_roots),
        "denied_write_root_declared": bool(canonical_source and canonical_source in denied_write_roots),
        "workspace_write_root_declared": bool(_safe_str(contract_payload.get("workspace_write_root")).strip()),
        "read_only_mount_not_bound": not bool(contract_payload.get("read_only_mount_bound")),
        "source_mount_enforcement_not_claimed": not bool(contract_payload.get("mount_enforced")),
        "source_copy_not_performed": not bool(contract_payload.get("source_copied"))
        and not bool(source_reference.get("contents_copied"))
        and not bool(workspace.source_copied)
        and not bool(readiness.source_copied),
        "source_write_not_allowed": not bool(contract_payload.get("source_write_allowed"))
        and not bool(workspace_policy.get("source_write_allowed"))
        and not bool(source.permissions.write)
        and not bool(readiness.source_write_allowed),
        "live_runner_not_bound": not bool(contract_payload.get("live_runner_bound"))
        and not bool(readiness.live_runner_bound),
        "sandbox_runner_not_bound": not bool(contract_payload.get("sandbox_runner_bound"))
        and not bool(readiness.sandbox_runner_bound),
        "commands_not_executed": not bool(contract_payload.get("commands_executed"))
        and not readiness.commands_executed,
        "network_not_accessed": not bool(contract_payload.get("network_accessed")) and not readiness.network_accessed,
        "repo_write_not_performed": not bool(contract_payload.get("wrote_to_repo")) and not readiness.wrote_to_repo,
        "execution_authority_absent": not bool(contract_payload.get("execution_authority"))
        and not readiness.execution_authority,
        "live_mount_bound": False,
        "mount_enforced": False,
        "source_copied": False,
        "source_write_allowed": False,
        "executed": False,
        "execution_authority": False,
        "repo_code_executed": False,
        "network_accessed": False,
        "wrote_to_repo": False,
    }


def _lab_run_boundary_required_checks() -> list[str]:
    return [
        "source_mount_contract_present",
        "source_mount_contract_ready",
        "source_mount_contract_declared",
        "read_only_mount_bound",
        "read_only_source_mount_enforced",
        "source_not_copied",
        "source_write_denied",
        "path_escape_prevention_bound",
        "symlink_escape_denial_bound",
        "sandbox_provider_contract_present",
        "sandbox_provider_contract_ready",
        "sandbox_provider_contract_declared",
        "sandbox_provider_binding_present",
        "sandbox_provider_binding_ready",
        "sandbox_provider_selection_present",
        "sandbox_provider_selection_ready",
        "provider_kind_selected",
        "provider_reference_verified",
        "sandbox_provider_verifier_present",
        "sandbox_provider_verifier_ready",
        "verifier_contract_declared",
        "verifier_implementation_bound",
        "verifier_identity_bound",
        "provider_binary_or_service_verified",
        "sandbox_provider_runtime_probe_present",
        "sandbox_provider_runtime_probe_ready",
        "runtime_probe_contract_declared",
        "runtime_probe_authorization_required",
        "runtime_probe_network_blocked_by_contract",
        "runtime_probe_receipt_contract_declared",
        "runtime_probe_repo_execution_separated",
        "provider_runtime_probe_performed",
        "sandbox_provider_runtime_probe_harness_present",
        "sandbox_provider_runtime_probe_harness_ready",
        "runtime_probe_harness_contract_declared",
        "sandbox_provider_runtime_probe_runner_enforcement_present",
        "sandbox_provider_runtime_probe_runner_enforcement_ready",
        "runtime_probe_runner_enforcement_contract_declared",
        "runtime_probe_runner_enforcement_bound",
        "runtime_probe_runner_bound",
        "runtime_probe_sandbox_bound",
        "runtime_probe_service_query_guard_bound",
        "runtime_probe_output_capture_bound",
        "runtime_probe_kill_switch_bound",
        "provider_policy_manifest_bound",
        "runner_sandbox_readiness_present",
        "runner_sandbox_readiness_ready",
        "sandbox_provider_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "workspace_isolated",
        "workspace_write_policy_bound",
        "network_blocked_or_policy_bound",
        "resource_limits_bound",
        "timeout_policy_bound",
        "stdout_stderr_capture_bound",
        "kill_switch_bound",
        "command_allowlist_enforcement_present",
        "command_allowlist_enforced",
        "execution_receipt_writer_preflight_present",
        "writer_implementation_bound",
        "receipt_prewrite_bound",
        "receipt_final_write_bound",
        "approval_consumption_handoff_present",
        "approval_consumption_ready",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "candidate_not_validated",
        "capability_not_promoted",
    ]


def _lab_run_boundary_contract_payload(
    *,
    source: SourceRecord,
    preflight: LabExecutionPreflight,
    workspace: LabWorkspaceRecord,
    source_mount_contract: LabSourceMountContract,
    writer_preflight: LabExecutionReceiptWriterPreflight,
    sandbox_readiness: LabRunnerSandboxReadiness,
    sandbox_provider_contract: LabSandboxProviderContract,
    sandbox_provider_binding: LabSandboxProviderBindingPreflight,
    sandbox_provider_selection: LabSandboxProviderSelectionPreflight,
    sandbox_provider_verifier: LabSandboxProviderVerifierPreflight,
    sandbox_provider_runtime_probe: LabSandboxProviderRuntimeProbePreflight,
    sandbox_provider_runtime_probe_harness: LabSandboxProviderRuntimeProbeHarnessPreflight,
    sandbox_provider_runtime_probe_runner_enforcement: LabSandboxProviderRuntimeProbeRunnerEnforcementPreflight,
    allowlist_enforcement: LabRunnerCommandAllowlistEnforcementPreflight,
    approval_handoff: LabApprovalConsumptionHandoff,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.run_boundary_preflight",
        "schema_version": 1,
        "mode": "preflight_only_no_execution",
        "run_mode": "future_sandboxed_rebuild_run_test",
        "action": writer_preflight.action,
        "action_hash": writer_preflight.action_hash,
        "source_id": source.id,
        "source_type": source.type,
        "source_fingerprint": source.fingerprint,
        "candidate_id": preflight.candidate_id,
        "candidate_name": preflight.candidate_name,
        "approval_id": approval_handoff.approval_id,
        "workspace_id": workspace.id,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "depends_on": {
            "source_mount_contract_id": source_mount_contract.id,
            "source_mount_readiness_id": source_mount_contract.source_mount_readiness_id,
            "execution_receipt_writer_preflight_id": writer_preflight.id,
            "receipt_prewrite_binding_id": writer_preflight.receipt_prewrite_binding_id,
            "receipt_write_readiness_id": writer_preflight.receipt_write_readiness_id,
            "sandbox_readiness_id": sandbox_readiness.id,
            "sandbox_provider_contract_id": sandbox_provider_contract.id,
            "sandbox_provider_binding_id": sandbox_provider_binding.id,
            "sandbox_provider_selection_id": sandbox_provider_selection.id,
            "sandbox_provider_verifier_id": sandbox_provider_verifier.id,
            "sandbox_provider_runtime_probe_id": sandbox_provider_runtime_probe.id,
            "sandbox_provider_runtime_probe_harness_id": sandbox_provider_runtime_probe_harness.id,
            "sandbox_provider_runtime_probe_runner_enforcement_id": (
                sandbox_provider_runtime_probe_runner_enforcement.id
            ),
            "command_allowlist_enforcement_id": allowlist_enforcement.id,
            "approval_handoff_id": approval_handoff.id,
        },
        "required_controls": _lab_run_boundary_required_checks(),
        "boundary_ready": False,
        "live_runner_bound": False,
        "sandbox_provider_contract_declared": sandbox_provider_contract.provider_contract_declared,
        "sandbox_provider_binding_ready": sandbox_provider_binding.status == "ready",
        "sandbox_provider_selection_ready": sandbox_provider_selection.status == "ready",
        "sandbox_provider_verifier_ready": sandbox_provider_verifier.status == "ready",
        "sandbox_provider_runtime_probe_ready": sandbox_provider_runtime_probe.status == "ready",
        "sandbox_provider_runtime_probe_harness_ready": sandbox_provider_runtime_probe_harness.status == "ready",
        "sandbox_provider_runtime_probe_runner_enforcement_ready": (
            sandbox_provider_runtime_probe_runner_enforcement.status == "ready"
        ),
        "selected_provider_kind": sandbox_provider_selection.selected_provider_kind,
        "verifier_contract_declared": sandbox_provider_verifier.verifier_contract_declared,
        "verifier_implementation_bound": sandbox_provider_verifier.verifier_implementation_bound,
        "verifier_identity_bound": sandbox_provider_verifier.verifier_identity_bound,
        "provider_reference_verified": sandbox_provider_selection.provider_reference_verified,
        "provider_binary_or_service_verified": sandbox_provider_verifier.provider_binary_or_service_verified,
        "runtime_probe_contract_declared": sandbox_provider_runtime_probe.runtime_probe_contract_declared,
        "runtime_probe_authorization_required": sandbox_provider_runtime_probe.runtime_probe_authorization_required,
        "runtime_probe_network_blocked_by_contract": (
            sandbox_provider_runtime_probe.runtime_probe_network_blocked_by_contract
        ),
        "runtime_probe_receipt_contract_declared": sandbox_provider_runtime_probe.runtime_probe_receipt_contract_declared,
        "runtime_probe_repo_execution_separated": sandbox_provider_runtime_probe.runtime_probe_repo_execution_separated,
        "provider_runtime_probe_performed": sandbox_provider_runtime_probe.provider_runtime_probe_performed,
        "runtime_probe_harness_contract_declared": (
            sandbox_provider_runtime_probe_harness.runtime_probe_runner_contract_declared
            and sandbox_provider_runtime_probe_harness.runtime_probe_sandbox_contract_declared
            and sandbox_provider_runtime_probe_harness.runtime_probe_service_query_guard_declared
            and sandbox_provider_runtime_probe_harness.runtime_probe_output_capture_declared
            and sandbox_provider_runtime_probe_harness.runtime_probe_kill_switch_declared
        ),
        "runtime_probe_runner_bound": sandbox_provider_runtime_probe_runner_enforcement.probe_runner_bound,
        "runtime_probe_sandbox_bound": sandbox_provider_runtime_probe_harness.runtime_probe_sandbox_bound,
        "runtime_probe_service_query_guard_bound": (
            sandbox_provider_runtime_probe_harness.runtime_probe_service_query_guard_bound
        ),
        "runtime_probe_output_capture_bound": (
            sandbox_provider_runtime_probe_harness.runtime_probe_output_capture_bound
        ),
        "runtime_probe_kill_switch_bound": sandbox_provider_runtime_probe_harness.runtime_probe_kill_switch_bound,
        "runtime_probe_runner_enforcement_contract_declared": (
            sandbox_provider_runtime_probe_runner_enforcement.probe_runner_enforcement_contract_declared
        ),
        "runtime_probe_runner_enforcement_bound": (
            sandbox_provider_runtime_probe_runner_enforcement.probe_runner_enforcement_bound
        ),
        "provider_policy_manifest_bound": sandbox_provider_selection.provider_policy_manifest_bound,
        "sandbox_provider_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "read_only_mount_bound": False,
        "source_mount_enforced": False,
        "command_allowlist_enforced": False,
        "execution_receipt_writer_bound": False,
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
        "repo_code_executed": False,
        "network_accessed": False,
        "wrote_to_repo": False,
        "candidate_validated": False,
        "capability_promoted": False,
    }


def _lab_run_boundary_current_checks(
    *,
    source_mount_contract: LabSourceMountContract,
    writer_preflight: LabExecutionReceiptWriterPreflight,
    sandbox_readiness: LabRunnerSandboxReadiness,
    sandbox_provider_contract: LabSandboxProviderContract,
    sandbox_provider_binding: LabSandboxProviderBindingPreflight,
    sandbox_provider_selection: LabSandboxProviderSelectionPreflight,
    sandbox_provider_verifier: LabSandboxProviderVerifierPreflight,
    sandbox_provider_runtime_probe: LabSandboxProviderRuntimeProbePreflight,
    sandbox_provider_runtime_probe_harness: LabSandboxProviderRuntimeProbeHarnessPreflight,
    sandbox_provider_runtime_probe_runner_enforcement: LabSandboxProviderRuntimeProbeRunnerEnforcementPreflight,
    allowlist_enforcement: LabRunnerCommandAllowlistEnforcementPreflight,
    approval_handoff: LabApprovalConsumptionHandoff,
) -> dict[str, Any]:
    provider_checks = _as_dict(sandbox_provider_contract.current_checks)
    binding_checks = _as_dict(sandbox_provider_binding.current_checks)
    selection_checks = _as_dict(sandbox_provider_selection.current_checks)
    verifier_checks = _as_dict(sandbox_provider_verifier.current_checks)
    runtime_probe_checks = _as_dict(sandbox_provider_runtime_probe.current_checks)
    runtime_probe_runner_enforcement_checks = _as_dict(sandbox_provider_runtime_probe_runner_enforcement.current_checks)
    return {
        "source_mount_contract_present": bool(source_mount_contract.id),
        "source_mount_contract_ready": source_mount_contract.status == "ready",
        "source_mount_contract_declared": bool(source_mount_contract.contract_declared),
        "read_only_mount_bound": bool(source_mount_contract.read_only_mount_bound),
        "read_only_source_mount_enforced": bool(source_mount_contract.mount_enforced),
        "source_not_copied": not bool(source_mount_contract.source_copied),
        "source_write_denied": not bool(source_mount_contract.source_write_allowed),
        "path_escape_prevention_bound": False,
        "symlink_escape_denial_bound": False,
        "sandbox_provider_contract_present": bool(sandbox_provider_contract.id),
        "sandbox_provider_contract_ready": sandbox_provider_contract.status == "ready",
        "sandbox_provider_contract_declared": bool(sandbox_provider_contract.provider_contract_declared),
        "sandbox_provider_binding_present": bool(sandbox_provider_binding.id),
        "sandbox_provider_binding_ready": sandbox_provider_binding.status == "ready",
        "sandbox_provider_selection_present": bool(sandbox_provider_selection.id),
        "sandbox_provider_selection_ready": sandbox_provider_selection.status == "ready",
        "provider_kind_selected": bool(sandbox_provider_selection.provider_kind_selected),
        "provider_reference_verified": bool(sandbox_provider_selection.provider_reference_verified),
        "provider_policy_manifest_bound": bool(sandbox_provider_selection.provider_policy_manifest_bound),
        "sandbox_provider_verifier_present": bool(sandbox_provider_verifier.id),
        "sandbox_provider_verifier_ready": sandbox_provider_verifier.status == "ready",
        "verifier_contract_declared": bool(sandbox_provider_verifier.verifier_contract_declared),
        "verifier_implementation_bound": bool(sandbox_provider_verifier.verifier_implementation_bound),
        "verifier_identity_bound": bool(sandbox_provider_verifier.verifier_identity_bound),
        "provider_binary_or_service_verified": bool(sandbox_provider_verifier.provider_binary_or_service_verified),
        "sandbox_provider_runtime_probe_present": bool(sandbox_provider_runtime_probe.id),
        "sandbox_provider_runtime_probe_ready": sandbox_provider_runtime_probe.status == "ready",
        "runtime_probe_contract_declared": bool(sandbox_provider_runtime_probe.runtime_probe_contract_declared),
        "runtime_probe_authorization_required": bool(
            sandbox_provider_runtime_probe.runtime_probe_authorization_required
        ),
        "runtime_probe_network_blocked_by_contract": bool(
            sandbox_provider_runtime_probe.runtime_probe_network_blocked_by_contract
        ),
        "runtime_probe_receipt_contract_declared": bool(
            sandbox_provider_runtime_probe.runtime_probe_receipt_contract_declared
        ),
        "runtime_probe_repo_execution_separated": bool(
            sandbox_provider_runtime_probe.runtime_probe_repo_execution_separated
        ),
        "provider_runtime_probe_performed": bool(sandbox_provider_runtime_probe.provider_runtime_probe_performed),
        "sandbox_provider_runtime_probe_harness_present": bool(sandbox_provider_runtime_probe_harness.id),
        "sandbox_provider_runtime_probe_harness_ready": sandbox_provider_runtime_probe_harness.status == "ready",
        "sandbox_provider_runtime_probe_runner_enforcement_present": bool(
            sandbox_provider_runtime_probe_runner_enforcement.id
        ),
        "sandbox_provider_runtime_probe_runner_enforcement_ready": (
            sandbox_provider_runtime_probe_runner_enforcement.status == "ready"
        ),
        "runtime_probe_harness_contract_declared": bool(
            sandbox_provider_runtime_probe_harness.runtime_probe_runner_contract_declared
            and sandbox_provider_runtime_probe_harness.runtime_probe_sandbox_contract_declared
            and sandbox_provider_runtime_probe_harness.runtime_probe_service_query_guard_declared
            and sandbox_provider_runtime_probe_harness.runtime_probe_output_capture_declared
            and sandbox_provider_runtime_probe_harness.runtime_probe_kill_switch_declared
        ),
        "runtime_probe_runner_enforcement_contract_declared": bool(
            sandbox_provider_runtime_probe_runner_enforcement.probe_runner_enforcement_contract_declared
        ),
        "runtime_probe_runner_enforcement_bound": bool(
            sandbox_provider_runtime_probe_runner_enforcement.probe_runner_enforcement_bound
        ),
        "runtime_probe_runner_bound": bool(sandbox_provider_runtime_probe_runner_enforcement.probe_runner_bound),
        "runtime_probe_sandbox_bound": bool(sandbox_provider_runtime_probe_harness.runtime_probe_sandbox_bound),
        "runtime_probe_service_query_guard_bound": bool(
            sandbox_provider_runtime_probe_harness.runtime_probe_service_query_guard_bound
        ),
        "runtime_probe_output_capture_bound": bool(
            sandbox_provider_runtime_probe_harness.runtime_probe_output_capture_bound
        ),
        "runtime_probe_kill_switch_bound": bool(sandbox_provider_runtime_probe_harness.runtime_probe_kill_switch_bound),
        "runner_sandbox_readiness_present": bool(sandbox_readiness.id),
        "runner_sandbox_readiness_ready": sandbox_readiness.status == "ready",
        "sandbox_provider_bound": bool(runtime_probe_checks.get("sandbox_provider_bound"))
        and bool(verifier_checks.get("sandbox_provider_bound"))
        and bool(runtime_probe_runner_enforcement_checks.get("sandbox_provider_bound")),
        "sandbox_bound": bool(sandbox_readiness.sandbox_bound),
        "sandbox_enforced": bool(sandbox_readiness.sandbox_enforced),
        "workspace_isolated": bool(verifier_checks.get("workspace_isolation_bound")),
        "workspace_write_policy_bound": bool(verifier_checks.get("filesystem_write_policy_bound")),
        "network_blocked_or_policy_bound": bool(provider_checks.get("network_blocked_or_policy_bound"))
        and bool(binding_checks.get("network_blocked_or_policy_bound"))
        and bool(selection_checks.get("network_blocked_or_policy_bound"))
        and bool(verifier_checks.get("network_blocked_or_policy_bound")),
        "resource_limits_bound": bool(verifier_checks.get("resource_limits_bound")),
        "timeout_policy_bound": bool(verifier_checks.get("timeout_policy_bound")),
        "stdout_stderr_capture_bound": bool(verifier_checks.get("stdout_stderr_capture_bound")),
        "kill_switch_bound": bool(verifier_checks.get("kill_switch_bound")),
        "command_allowlist_enforcement_present": bool(allowlist_enforcement.id),
        "command_allowlist_enforced": bool(allowlist_enforcement.allowlist_enforced),
        "execution_receipt_writer_preflight_present": bool(writer_preflight.id),
        "writer_implementation_bound": bool(writer_preflight.writer_implementation_bound),
        "receipt_prewrite_bound": bool(writer_preflight.prewrite_writer_bound),
        "receipt_final_write_bound": bool(writer_preflight.final_write_writer_bound),
        "approval_consumption_handoff_present": bool(approval_handoff.id),
        "approval_consumption_ready": approval_handoff.status == "ready",
        "approval_not_consumed": not bool(approval_handoff.approval_consumed),
        "execution_authority_absent": not bool(writer_preflight.execution_authority)
        and not bool(sandbox_readiness.execution_authority)
        and not bool(sandbox_provider_verifier.execution_authority)
        and not bool(sandbox_provider_runtime_probe.execution_authority)
        and not bool(sandbox_provider_runtime_probe_harness.execution_authority)
        and not bool(sandbox_provider_runtime_probe_runner_enforcement.execution_authority)
        and not bool(allowlist_enforcement.execution_authority)
        and not bool(approval_handoff.execution_authority),
        "commands_not_executed": not bool(writer_preflight.executed)
        and not bool(sandbox_readiness.executed)
        and not bool(sandbox_provider_verifier.executed)
        and not bool(sandbox_provider_runtime_probe.executed)
        and not bool(sandbox_provider_runtime_probe_harness.executed)
        and not bool(sandbox_provider_runtime_probe_runner_enforcement.executed)
        and not bool(allowlist_enforcement.executed),
        "repo_code_not_executed": True,
        "network_not_accessed": not bool(writer_preflight.network_accessed)
        and not bool(sandbox_readiness.network_accessed)
        and not bool(sandbox_provider_verifier.network_accessed)
        and not bool(sandbox_provider_runtime_probe.network_accessed)
        and not bool(sandbox_provider_runtime_probe_harness.network_accessed)
        and not bool(sandbox_provider_runtime_probe_runner_enforcement.network_accessed)
        and not bool(allowlist_enforcement.network_accessed),
        "repo_write_not_performed": not bool(writer_preflight.wrote_to_repo)
        and not bool(sandbox_readiness.wrote_to_repo)
        and not bool(sandbox_provider_verifier.wrote_to_repo)
        and not bool(sandbox_provider_runtime_probe.wrote_to_repo)
        and not bool(sandbox_provider_runtime_probe_harness.wrote_to_repo)
        and not bool(sandbox_provider_runtime_probe_runner_enforcement.wrote_to_repo)
        and not bool(allowlist_enforcement.wrote_to_repo),
        "candidate_not_validated": True,
        "capability_not_promoted": True,
        "source_write_allowed": bool(source_mount_contract.source_write_allowed),
        "source_copied": bool(source_mount_contract.source_copied),
        "approval_consumed": bool(approval_handoff.approval_consumed),
        "execution_authority": bool(writer_preflight.execution_authority)
        or bool(sandbox_readiness.execution_authority)
        or bool(sandbox_provider_verifier.execution_authority)
        or bool(sandbox_provider_runtime_probe.execution_authority)
        or bool(sandbox_provider_runtime_probe_harness.execution_authority)
        or bool(sandbox_provider_runtime_probe_runner_enforcement.execution_authority)
        or bool(allowlist_enforcement.execution_authority)
        or bool(approval_handoff.execution_authority),
        "commands_executed": bool(writer_preflight.executed)
        or bool(sandbox_readiness.executed)
        or bool(sandbox_provider_verifier.executed)
        or bool(sandbox_provider_runtime_probe.executed)
        or bool(sandbox_provider_runtime_probe_harness.executed)
        or bool(sandbox_provider_runtime_probe_runner_enforcement.executed)
        or bool(allowlist_enforcement.executed),
        "repo_code_executed": False,
        "network_accessed": bool(writer_preflight.network_accessed)
        or bool(sandbox_readiness.network_accessed)
        or bool(sandbox_provider_verifier.network_accessed)
        or bool(sandbox_provider_runtime_probe.network_accessed)
        or bool(sandbox_provider_runtime_probe_harness.network_accessed)
        or bool(sandbox_provider_runtime_probe_runner_enforcement.network_accessed)
        or bool(allowlist_enforcement.network_accessed),
        "wrote_to_repo": bool(writer_preflight.wrote_to_repo)
        or bool(sandbox_readiness.wrote_to_repo)
        or bool(sandbox_provider_verifier.wrote_to_repo)
        or bool(sandbox_provider_runtime_probe.wrote_to_repo)
        or bool(sandbox_provider_runtime_probe_harness.wrote_to_repo)
        or bool(sandbox_provider_runtime_probe_runner_enforcement.wrote_to_repo)
        or bool(allowlist_enforcement.wrote_to_repo),
        "candidate_validated": False,
        "capability_promoted": False,
    }


def _lab_sandbox_provider_runtime_probe_execution_boundary_required_checks() -> list[str]:
    return [
        "run_boundary_present",
        "run_boundary_ready",
        "runtime_probe_runner_enforcement_present",
        "runtime_probe_runner_enforcement_ready",
        "runtime_probe_runner_enforcement_bound",
        "runtime_probe_runner_bound",
        "runtime_probe_bound",
        "provider_probe_execution_boundary_declared",
        "provider_probe_execution_boundary_bound",
        "provider_runtime_probe_performed",
        "execution_receipt_writer_bound",
        "receipt_prewrite_bound",
        "receipt_final_write_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "network_blocked_or_policy_bound",
        "workspace_isolated",
        "timeout_policy_bound",
        "kill_switch_bound",
        "output_capture_bound",
        "approval_not_consumed",
        "execution_authority_absent",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "process_not_launched",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_receipt_not_written",
    ]


def _lab_sandbox_provider_runtime_probe_execution_boundary_contract_payload(
    *,
    run_boundary: LabRunBoundaryPreflight,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_execution_boundary",
        "schema_version": 1,
        "mode": "execution_boundary_preflight_only_no_provider_execution",
        "probe_mode": "future_sandbox_provider_runtime_probe",
        "run_boundary_preflight_id": run_boundary.id,
        "approval_id": run_boundary.approval_id,
        "preflight_id": run_boundary.preflight_id,
        "workspace_id": run_boundary.workspace_id,
        "source_id": run_boundary.source_id,
        "candidate_id": run_boundary.candidate_id,
        "candidate_name": run_boundary.candidate_name,
        "action": run_boundary.action,
        "action_hash": run_boundary.action_hash,
        "depends_on": {
            "run_boundary_preflight_id": run_boundary.id,
            "source_mount_contract_id": run_boundary.source_mount_contract_id,
            "execution_receipt_writer_preflight_id": run_boundary.execution_receipt_writer_preflight_id,
            "sandbox_provider_runtime_probe_runner_enforcement_id": (
                run_boundary.sandbox_provider_runtime_probe_runner_enforcement_id
            ),
            "sandbox_provider_runtime_probe_harness_id": run_boundary.sandbox_provider_runtime_probe_harness_id,
            "sandbox_provider_runtime_probe_id": run_boundary.sandbox_provider_runtime_probe_id,
        },
        "required_controls": _lab_sandbox_provider_runtime_probe_execution_boundary_required_checks(),
        "future_execution_allowed_only_if": {
            "run_boundary_ready": True,
            "runtime_probe_runner_enforcement_bound": True,
            "runtime_probe_bound": True,
            "provider_probe_execution_boundary_bound": True,
            "sandbox_bound": True,
            "sandbox_enforced": True,
            "network_blocked_or_policy_bound": True,
            "workspace_isolated": True,
            "timeout_policy_bound": True,
            "kill_switch_bound": True,
            "output_capture_bound": True,
            "execution_receipt_writer_bound": True,
        },
        "prohibited_during_preflight": {
            "provider_runtime_probe": True,
            "provider_binary_execution": True,
            "provider_service_query": True,
            "process_launch": True,
            "container_launch": True,
            "repository_code_execution": True,
            "network_access": True,
            "repository_write": True,
            "approval_consumption": True,
            "execution_receipt_write": True,
        },
        "provider_probe_execution_boundary_declared": True,
        "provider_probe_execution_boundary_bound": False,
        "provider_runtime_probe_performed": False,
        "execution_receipt_write_allowed": False,
        "approval_consumption_allowed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_sandbox_provider_runtime_probe_execution_boundary_current_checks(
    *,
    run_boundary: LabRunBoundaryPreflight,
    execution_boundary_contract: dict[str, Any],
) -> dict[str, Any]:
    run_checks = _as_dict(run_boundary.current_checks)
    runner_enforcement = _as_dict(run_boundary.sandbox_provider_runtime_probe_runner_enforcement)
    return {
        "run_boundary_present": bool(run_boundary.id),
        "run_boundary_ready": run_boundary.status == "ready",
        "runtime_probe_runner_enforcement_present": bool(
            run_boundary.sandbox_provider_runtime_probe_runner_enforcement_id
        ),
        "runtime_probe_runner_enforcement_ready": bool(
            run_boundary.sandbox_provider_runtime_probe_runner_enforcement_ready
        ),
        "runtime_probe_runner_enforcement_bound": bool(run_boundary.runtime_probe_runner_enforcement_bound),
        "runtime_probe_runner_bound": bool(run_boundary.runtime_probe_runner_bound),
        "runtime_probe_bound": bool(runner_enforcement.get("runtime_probe_bound"))
        or bool(run_checks.get("runtime_probe_bound")),
        "provider_probe_execution_boundary_declared": bool(
            execution_boundary_contract.get("provider_probe_execution_boundary_declared")
        ),
        "provider_probe_execution_boundary_bound": False,
        "provider_runtime_probe_performed": False,
        "execution_receipt_writer_bound": bool(run_boundary.writer_implementation_bound),
        "receipt_prewrite_bound": bool(run_boundary.receipt_prewrite_bound),
        "receipt_final_write_bound": bool(run_boundary.receipt_final_write_bound),
        "sandbox_bound": bool(run_boundary.sandbox_bound),
        "sandbox_enforced": bool(run_boundary.sandbox_enforced),
        "network_blocked_or_policy_bound": bool(run_checks.get("network_blocked_or_policy_bound")),
        "workspace_isolated": bool(run_checks.get("workspace_isolated")),
        "timeout_policy_bound": bool(run_checks.get("timeout_policy_bound")),
        "kill_switch_bound": bool(run_checks.get("kill_switch_bound")),
        "output_capture_bound": bool(run_checks.get("stdout_stderr_capture_bound"))
        or bool(run_checks.get("runtime_probe_output_capture_bound")),
        "approval_not_consumed": not bool(run_boundary.approval_consumed),
        "execution_authority_absent": not bool(run_boundary.execution_authority),
        "provider_binary_not_executed": not bool(runner_enforcement.get("executed")),
        "service_query_not_performed": not bool(runner_enforcement.get("service_query_performed")),
        "process_not_launched": not bool(runner_enforcement.get("process_launched")),
        "container_not_launched": not bool(runner_enforcement.get("container_launched")),
        "repo_code_not_executed": not bool(run_boundary.repo_code_executed),
        "network_not_accessed": not bool(run_boundary.network_accessed),
        "repo_write_not_performed": not bool(run_boundary.wrote_to_repo),
        "execution_receipt_not_written": True,
        "approval_consumed": bool(run_boundary.approval_consumed),
        "execution_authority": bool(run_boundary.execution_authority),
        "executed": bool(run_boundary.executed),
        "service_query_performed": bool(runner_enforcement.get("service_query_performed")),
        "process_launched": bool(runner_enforcement.get("process_launched")),
        "container_launched": bool(runner_enforcement.get("container_launched")),
        "repo_code_executed": bool(run_boundary.repo_code_executed),
        "network_accessed": bool(run_boundary.network_accessed),
        "wrote_to_repo": bool(run_boundary.wrote_to_repo),
        "execution_receipt_written": False,
    }


def _lab_sandbox_provider_runtime_probe_invocation_boundary_required_checks() -> list[str]:
    return [
        "approval_consumption_found",
        "approval_consumed",
        "single_use_enforced",
        "exact_action_binding_verified",
        "execution_boundary_present",
        "execution_boundary_recorded",
        "execution_boundary_ready",
        "provider_probe_execution_boundary_bound",
        "probe_runner_bound",
        "probe_runner_policy_bound",
        "probe_runner_sandbox_bound",
        "probe_runner_network_blocked",
        "probe_runner_workspace_isolated",
        "probe_runner_timeout_bound",
        "probe_runner_output_capture_bound",
        "probe_runner_kill_switch_bound",
        "probe_runner_receipt_writer_bound",
        "execution_authority_absent",
        "provider_runtime_probe_not_performed",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "process_not_launched",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_receipt_not_written",
    ]


def _lab_sandbox_provider_runtime_probe_invocation_boundary_contract_payload(
    *,
    approval_consumption: LabSandboxProviderRuntimeProbeApprovalConsumption,
    execution_boundary: LabSandboxProviderRuntimeProbeExecutionBoundary | None,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_invocation_boundary",
        "schema_version": 1,
        "mode": "invocation_boundary_preflight_only_no_provider_execution",
        "invocation_mode": "future_sandbox_provider_runtime_probe_invocation",
        "approval_id": approval_consumption.approval_id,
        "approval_consumption_id": approval_consumption.id,
        "approval_request_id": approval_consumption.approval_request_id,
        "execution_boundary_id": approval_consumption.execution_boundary_id,
        "run_boundary_preflight_id": approval_consumption.run_boundary_preflight_id,
        "source_id": approval_consumption.source_id,
        "candidate_id": approval_consumption.candidate_id,
        "candidate_name": approval_consumption.candidate_name,
        "action": approval_consumption.action,
        "action_hash": approval_consumption.action_hash,
        "depends_on": {
            "approval_consumption_id": approval_consumption.id,
            "approval_request_id": approval_consumption.approval_request_id,
            "execution_boundary_id": approval_consumption.execution_boundary_id,
            "run_boundary_preflight_id": approval_consumption.run_boundary_preflight_id,
        },
        "required_controls": _lab_sandbox_provider_runtime_probe_invocation_boundary_required_checks(),
        "future_invocation_allowed_only_if": {
            "execution_boundary_ready": True,
            "provider_probe_execution_boundary_bound": True,
            "probe_runner_bound": True,
            "probe_runner_policy_bound": True,
            "probe_runner_sandbox_bound": True,
            "probe_runner_network_blocked": True,
            "probe_runner_workspace_isolated": True,
            "probe_runner_timeout_bound": True,
            "probe_runner_output_capture_bound": True,
            "probe_runner_kill_switch_bound": True,
            "probe_runner_receipt_writer_bound": True,
        },
        "prohibited_during_boundary_write": {
            "provider_runtime_probe": True,
            "provider_binary_execution": True,
            "provider_service_query": True,
            "process_launch": True,
            "container_launch": True,
            "repository_code_execution": True,
            "network_access": True,
            "repository_write": True,
            "execution_receipt_write": True,
        },
        "approval_consumed": approval_consumption.approval_consumed,
        "single_use_enforced": approval_consumption.single_use_enforced,
        "execution_boundary_recorded": execution_boundary is not None,
        "execution_authority": False,
        "executed": False,
    }


def _lab_sandbox_provider_runtime_probe_invocation_boundary_current_checks(
    *,
    approval_consumption: LabSandboxProviderRuntimeProbeApprovalConsumption,
    execution_boundary: LabSandboxProviderRuntimeProbeExecutionBoundary | None,
) -> dict[str, Any]:
    approval_binding = _as_dict(approval_consumption.approval_binding)
    boundary_checks = _as_dict(execution_boundary.current_checks) if execution_boundary is not None else {}
    return {
        "approval_consumption_found": bool(approval_consumption.id),
        "approval_consumed": bool(approval_consumption.approval_consumed),
        "single_use_enforced": bool(approval_consumption.single_use_enforced),
        "exact_action_binding_verified": bool(approval_binding.get("exact_match")),
        "execution_boundary_present": execution_boundary is not None,
        "execution_boundary_recorded": execution_boundary is not None and bool(execution_boundary.id),
        "execution_boundary_ready": execution_boundary is not None and execution_boundary.status == "ready",
        "provider_probe_execution_boundary_bound": bool(
            execution_boundary.provider_probe_execution_boundary_bound if execution_boundary is not None else False
        ),
        "probe_runner_bound": bool(boundary_checks.get("runtime_probe_runner_bound")),
        "probe_runner_policy_bound": bool(boundary_checks.get("runtime_probe_runner_enforcement_bound")),
        "probe_runner_sandbox_bound": bool(boundary_checks.get("sandbox_bound"))
        and bool(boundary_checks.get("sandbox_enforced")),
        "probe_runner_network_blocked": bool(boundary_checks.get("network_blocked_or_policy_bound")),
        "probe_runner_workspace_isolated": bool(boundary_checks.get("workspace_isolated")),
        "probe_runner_timeout_bound": bool(boundary_checks.get("timeout_policy_bound")),
        "probe_runner_output_capture_bound": bool(boundary_checks.get("output_capture_bound")),
        "probe_runner_kill_switch_bound": bool(boundary_checks.get("kill_switch_bound")),
        "probe_runner_receipt_writer_bound": bool(boundary_checks.get("execution_receipt_writer_bound"))
        and bool(boundary_checks.get("receipt_prewrite_bound"))
        and bool(boundary_checks.get("receipt_final_write_bound")),
        "execution_authority_absent": not bool(approval_consumption.execution_authority)
        and (execution_boundary is None or not bool(execution_boundary.execution_authority)),
        "provider_runtime_probe_not_performed": not bool(approval_consumption.provider_runtime_probe_performed)
        and (execution_boundary is None or not bool(execution_boundary.provider_runtime_probe_performed)),
        "provider_binary_not_executed": not bool(approval_consumption.provider_binary_executed),
        "service_query_not_performed": not bool(approval_consumption.service_query_performed)
        and (execution_boundary is None or not bool(execution_boundary.service_query_performed)),
        "process_not_launched": not bool(approval_consumption.process_launched)
        and (execution_boundary is None or not bool(execution_boundary.process_launched)),
        "container_not_launched": not bool(approval_consumption.container_launched)
        and (execution_boundary is None or not bool(execution_boundary.container_launched)),
        "repo_code_not_executed": not bool(approval_consumption.repo_code_executed)
        and (execution_boundary is None or not bool(execution_boundary.repo_code_executed)),
        "network_not_accessed": not bool(approval_consumption.network_accessed)
        and (execution_boundary is None or not bool(execution_boundary.network_accessed)),
        "repo_write_not_performed": not bool(approval_consumption.wrote_to_repo)
        and (execution_boundary is None or not bool(execution_boundary.wrote_to_repo)),
        "execution_receipt_not_written": not bool(approval_consumption.execution_receipt_written)
        and (execution_boundary is None or not bool(execution_boundary.execution_receipt_written)),
        "upstream_approval_consumed": bool(approval_consumption.upstream_approval_consumed),
        "execution_authority": bool(approval_consumption.execution_authority)
        or (execution_boundary is not None and bool(execution_boundary.execution_authority)),
        "executed": bool(approval_consumption.executed)
        or (execution_boundary is not None and bool(execution_boundary.executed)),
        "provider_runtime_probe_performed": bool(approval_consumption.provider_runtime_probe_performed)
        or (execution_boundary is not None and bool(execution_boundary.provider_runtime_probe_performed)),
        "provider_binary_executed": bool(approval_consumption.provider_binary_executed),
        "service_query_performed": bool(approval_consumption.service_query_performed)
        or (execution_boundary is not None and bool(execution_boundary.service_query_performed)),
        "process_launched": bool(approval_consumption.process_launched)
        or (execution_boundary is not None and bool(execution_boundary.process_launched)),
        "container_launched": bool(approval_consumption.container_launched)
        or (execution_boundary is not None and bool(execution_boundary.container_launched)),
        "repo_code_executed": bool(approval_consumption.repo_code_executed)
        or (execution_boundary is not None and bool(execution_boundary.repo_code_executed)),
        "network_accessed": bool(approval_consumption.network_accessed)
        or (execution_boundary is not None and bool(execution_boundary.network_accessed)),
        "wrote_to_repo": bool(approval_consumption.wrote_to_repo)
        or (execution_boundary is not None and bool(execution_boundary.wrote_to_repo)),
        "execution_receipt_written": bool(approval_consumption.execution_receipt_written)
        or (execution_boundary is not None and bool(execution_boundary.execution_receipt_written)),
    }


def _lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_required_checks() -> list[str]:
    return [
        "invocation_boundary_found",
        "invocation_boundary_recorded",
        "invocation_boundary_ready",
        "approval_consumed",
        "single_use_consumption_found",
        "single_use_enforced",
        "exact_action_binding_verified",
        "runner_identity_declared",
        "runner_identity_bound",
        "runner_policy_declared",
        "runner_policy_bound",
        "sandbox_policy_declared",
        "sandbox_policy_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "network_block_declared",
        "network_block_bound",
        "timeout_policy_declared",
        "timeout_policy_bound",
        "output_capture_declared",
        "output_capture_bound",
        "kill_switch_declared",
        "kill_switch_bound",
        "execution_receipt_writer_declared",
        "execution_receipt_writer_bound",
        "execution_authority_absent",
        "provider_runtime_probe_not_performed",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "process_not_launched",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_receipt_not_written",
    ]


def _lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_contract_payload(
    *,
    invocation_boundary: LabSandboxProviderRuntimeProbeInvocationBoundary,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary",
        "schema_version": 1,
        "mode": "runner_pre_execution_boundary_no_provider_execution",
        "pre_execution_mode": "future_sandbox_provider_runtime_probe_runner_pre_execution",
        "approval_id": invocation_boundary.approval_id,
        "approval_consumption_id": invocation_boundary.approval_consumption_id,
        "approval_request_id": invocation_boundary.approval_request_id,
        "invocation_boundary_id": invocation_boundary.id,
        "execution_boundary_id": invocation_boundary.execution_boundary_id,
        "run_boundary_preflight_id": invocation_boundary.run_boundary_preflight_id,
        "source_id": invocation_boundary.source_id,
        "candidate_id": invocation_boundary.candidate_id,
        "candidate_name": invocation_boundary.candidate_name,
        "action": invocation_boundary.action,
        "action_hash": invocation_boundary.action_hash,
        "depends_on": {
            "invocation_boundary_id": invocation_boundary.id,
            "approval_consumption_id": invocation_boundary.approval_consumption_id,
            "approval_request_id": invocation_boundary.approval_request_id,
            "execution_boundary_id": invocation_boundary.execution_boundary_id,
            "run_boundary_preflight_id": invocation_boundary.run_boundary_preflight_id,
        },
        "declared_controls": {
            "runner_identity": True,
            "runner_policy": True,
            "sandbox_policy": True,
            "network_block": True,
            "timeout_policy": True,
            "output_capture": True,
            "kill_switch": True,
            "execution_receipt_writer": True,
        },
        "required_controls": _lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_required_checks(),
        "future_probe_allowed_only_if": {
            "invocation_boundary_ready": True,
            "runner_identity_bound": True,
            "runner_policy_bound": True,
            "sandbox_policy_bound": True,
            "sandbox_bound": True,
            "sandbox_enforced": True,
            "network_block_bound": True,
            "timeout_policy_bound": True,
            "output_capture_bound": True,
            "kill_switch_bound": True,
            "execution_receipt_writer_bound": True,
        },
        "prohibited_during_boundary_write": {
            "provider_runtime_probe": True,
            "provider_binary_execution": True,
            "provider_service_query": True,
            "process_launch": True,
            "container_launch": True,
            "repository_code_execution": True,
            "network_access": True,
            "repository_write": True,
            "execution_receipt_write": True,
        },
        "approval_consumed": invocation_boundary.approval_consumed,
        "single_use_enforced": invocation_boundary.single_use_enforced,
        "invocation_boundary_ready": invocation_boundary.status == "ready",
        "execution_authority": False,
        "executed": False,
    }


def _lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_current_checks(
    *,
    invocation_boundary: LabSandboxProviderRuntimeProbeInvocationBoundary,
) -> dict[str, Any]:
    return {
        "invocation_boundary_found": bool(invocation_boundary.id),
        "invocation_boundary_recorded": bool(invocation_boundary.id),
        "invocation_boundary_ready": invocation_boundary.status == "ready",
        "approval_consumed": bool(invocation_boundary.approval_consumed),
        "single_use_consumption_found": bool(invocation_boundary.single_use_consumption_found),
        "single_use_enforced": bool(invocation_boundary.single_use_enforced),
        "exact_action_binding_verified": bool(invocation_boundary.exact_action_binding_verified),
        "runner_identity_declared": True,
        "runner_identity_bound": False,
        "runner_policy_declared": True,
        "runner_policy_bound": False,
        "sandbox_policy_declared": True,
        "sandbox_policy_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "network_block_declared": True,
        "network_block_bound": False,
        "timeout_policy_declared": True,
        "timeout_policy_bound": False,
        "output_capture_declared": True,
        "output_capture_bound": False,
        "kill_switch_declared": True,
        "kill_switch_bound": False,
        "execution_receipt_writer_declared": True,
        "execution_receipt_writer_bound": False,
        "execution_authority_absent": not bool(invocation_boundary.execution_authority),
        "provider_runtime_probe_not_performed": not bool(invocation_boundary.provider_runtime_probe_performed),
        "provider_binary_not_executed": not bool(invocation_boundary.provider_binary_executed),
        "service_query_not_performed": not bool(invocation_boundary.service_query_performed),
        "process_not_launched": not bool(invocation_boundary.process_launched),
        "container_not_launched": not bool(invocation_boundary.container_launched),
        "repo_code_not_executed": not bool(invocation_boundary.repo_code_executed),
        "network_not_accessed": not bool(invocation_boundary.network_accessed),
        "repo_write_not_performed": not bool(invocation_boundary.wrote_to_repo),
        "execution_receipt_not_written": not bool(invocation_boundary.execution_receipt_written),
        "execution_authority": bool(invocation_boundary.execution_authority),
        "executed": bool(invocation_boundary.executed),
        "provider_runtime_probe_performed": bool(invocation_boundary.provider_runtime_probe_performed),
        "provider_binary_executed": bool(invocation_boundary.provider_binary_executed),
        "service_query_performed": bool(invocation_boundary.service_query_performed),
        "process_launched": bool(invocation_boundary.process_launched),
        "container_launched": bool(invocation_boundary.container_launched),
        "repo_code_executed": bool(invocation_boundary.repo_code_executed),
        "network_accessed": bool(invocation_boundary.network_accessed),
        "wrote_to_repo": bool(invocation_boundary.wrote_to_repo),
        "execution_receipt_written": bool(invocation_boundary.execution_receipt_written),
    }


def _lab_sandbox_provider_runtime_probe_runner_control_binding_required_checks() -> list[str]:
    return [
        "pre_execution_boundary_found",
        "pre_execution_boundary_recorded",
        "pre_execution_boundary_ready",
        "invocation_boundary_found",
        "invocation_boundary_recorded",
        "approval_consumed",
        "single_use_consumption_found",
        "single_use_enforced",
        "exact_action_binding_verified",
        "control_binding_recorded",
        "runner_identity_declared",
        "runner_identity_binding_recorded",
        "runner_identity_bound",
        "runner_policy_declared",
        "runner_policy_binding_recorded",
        "runner_policy_bound",
        "sandbox_policy_declared",
        "sandbox_policy_binding_recorded",
        "sandbox_policy_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "network_block_declared",
        "network_block_binding_recorded",
        "network_block_bound",
        "timeout_policy_declared",
        "timeout_policy_binding_recorded",
        "timeout_policy_bound",
        "output_capture_declared",
        "output_capture_binding_recorded",
        "output_capture_bound",
        "kill_switch_declared",
        "kill_switch_binding_recorded",
        "kill_switch_bound",
        "execution_receipt_writer_declared",
        "execution_receipt_writer_binding_recorded",
        "execution_receipt_writer_bound",
        "execution_authority_absent",
        "provider_runtime_probe_not_performed",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "process_not_launched",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_receipt_not_written",
    ]


def _lab_sandbox_provider_runtime_probe_runner_control_binding_contract_payload(
    *,
    pre_execution_boundary: LabSandboxProviderRuntimeProbeRunnerPreExecutionBoundary,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_runner_control_binding",
        "schema_version": 1,
        "mode": "control_binding_preflight_only_no_provider_execution",
        "control_binding_mode": "future_sandbox_provider_runtime_probe_runner_control_binding",
        "approval_id": pre_execution_boundary.approval_id,
        "approval_consumption_id": pre_execution_boundary.approval_consumption_id,
        "approval_request_id": pre_execution_boundary.approval_request_id,
        "invocation_boundary_id": pre_execution_boundary.invocation_boundary_id,
        "pre_execution_boundary_id": pre_execution_boundary.id,
        "execution_boundary_id": pre_execution_boundary.execution_boundary_id,
        "run_boundary_preflight_id": pre_execution_boundary.run_boundary_preflight_id,
        "source_id": pre_execution_boundary.source_id,
        "candidate_id": pre_execution_boundary.candidate_id,
        "candidate_name": pre_execution_boundary.candidate_name,
        "action": pre_execution_boundary.action,
        "action_hash": pre_execution_boundary.action_hash,
        "depends_on": {
            "pre_execution_boundary_id": pre_execution_boundary.id,
            "invocation_boundary_id": pre_execution_boundary.invocation_boundary_id,
            "approval_consumption_id": pre_execution_boundary.approval_consumption_id,
            "approval_request_id": pre_execution_boundary.approval_request_id,
            "execution_boundary_id": pre_execution_boundary.execution_boundary_id,
            "run_boundary_preflight_id": pre_execution_boundary.run_boundary_preflight_id,
        },
        "control_binding_records": {
            "runner_identity": True,
            "runner_policy": True,
            "sandbox_policy": True,
            "network_block": True,
            "timeout_policy": True,
            "output_capture": True,
            "kill_switch": True,
            "execution_receipt_writer": True,
        },
        "required_controls": _lab_sandbox_provider_runtime_probe_runner_control_binding_required_checks(),
        "future_probe_allowed_only_if": {
            "pre_execution_boundary_ready": True,
            "runner_identity_bound": True,
            "runner_policy_bound": True,
            "sandbox_policy_bound": True,
            "sandbox_bound": True,
            "sandbox_enforced": True,
            "network_block_bound": True,
            "timeout_policy_bound": True,
            "output_capture_bound": True,
            "kill_switch_bound": True,
            "execution_receipt_writer_bound": True,
        },
        "prohibited_during_binding_write": {
            "provider_runtime_probe": True,
            "provider_binary_execution": True,
            "provider_service_query": True,
            "process_launch": True,
            "container_launch": True,
            "repository_code_execution": True,
            "network_access": True,
            "repository_write": True,
            "execution_receipt_write": True,
        },
        "approval_consumed": pre_execution_boundary.approval_consumed,
        "single_use_enforced": pre_execution_boundary.single_use_enforced,
        "execution_authority": False,
        "executed": False,
    }


def _lab_sandbox_provider_runtime_probe_runner_control_binding_current_checks(
    *,
    pre_execution_boundary: LabSandboxProviderRuntimeProbeRunnerPreExecutionBoundary,
) -> dict[str, Any]:
    return {
        "pre_execution_boundary_found": bool(pre_execution_boundary.id),
        "pre_execution_boundary_recorded": bool(pre_execution_boundary.id),
        "pre_execution_boundary_ready": pre_execution_boundary.status == "ready",
        "invocation_boundary_found": bool(pre_execution_boundary.invocation_boundary_id),
        "invocation_boundary_recorded": bool(pre_execution_boundary.invocation_boundary_recorded),
        "invocation_boundary_ready": bool(pre_execution_boundary.invocation_boundary_ready),
        "approval_consumed": bool(pre_execution_boundary.approval_consumed),
        "single_use_consumption_found": bool(pre_execution_boundary.single_use_consumption_found),
        "single_use_enforced": bool(pre_execution_boundary.single_use_enforced),
        "exact_action_binding_verified": bool(pre_execution_boundary.exact_action_binding_verified),
        "control_binding_recorded": True,
        "runner_identity_declared": bool(pre_execution_boundary.runner_identity_declared),
        "runner_identity_binding_recorded": True,
        "runner_identity_bound": False,
        "runner_policy_declared": bool(pre_execution_boundary.runner_policy_declared),
        "runner_policy_binding_recorded": True,
        "runner_policy_bound": False,
        "sandbox_policy_declared": bool(pre_execution_boundary.sandbox_policy_declared),
        "sandbox_policy_binding_recorded": True,
        "sandbox_policy_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "network_block_declared": bool(pre_execution_boundary.network_block_declared),
        "network_block_binding_recorded": True,
        "network_block_bound": False,
        "timeout_policy_declared": bool(pre_execution_boundary.timeout_policy_declared),
        "timeout_policy_binding_recorded": True,
        "timeout_policy_bound": False,
        "output_capture_declared": bool(pre_execution_boundary.output_capture_declared),
        "output_capture_binding_recorded": True,
        "output_capture_bound": False,
        "kill_switch_declared": bool(pre_execution_boundary.kill_switch_declared),
        "kill_switch_binding_recorded": True,
        "kill_switch_bound": False,
        "execution_receipt_writer_declared": bool(pre_execution_boundary.execution_receipt_writer_declared),
        "execution_receipt_writer_binding_recorded": True,
        "execution_receipt_writer_bound": False,
        "execution_authority_absent": not bool(pre_execution_boundary.execution_authority),
        "provider_runtime_probe_not_performed": not bool(pre_execution_boundary.provider_runtime_probe_performed),
        "provider_binary_not_executed": not bool(pre_execution_boundary.provider_binary_executed),
        "service_query_not_performed": not bool(pre_execution_boundary.service_query_performed),
        "process_not_launched": not bool(pre_execution_boundary.process_launched),
        "container_not_launched": not bool(pre_execution_boundary.container_launched),
        "repo_code_not_executed": not bool(pre_execution_boundary.repo_code_executed),
        "network_not_accessed": not bool(pre_execution_boundary.network_accessed),
        "repo_write_not_performed": not bool(pre_execution_boundary.wrote_to_repo),
        "execution_receipt_not_written": not bool(pre_execution_boundary.execution_receipt_written),
        "execution_authority": bool(pre_execution_boundary.execution_authority),
        "executed": bool(pre_execution_boundary.executed),
        "provider_runtime_probe_performed": bool(pre_execution_boundary.provider_runtime_probe_performed),
        "provider_binary_executed": bool(pre_execution_boundary.provider_binary_executed),
        "service_query_performed": bool(pre_execution_boundary.service_query_performed),
        "process_launched": bool(pre_execution_boundary.process_launched),
        "container_launched": bool(pre_execution_boundary.container_launched),
        "repo_code_executed": bool(pre_execution_boundary.repo_code_executed),
        "network_accessed": bool(pre_execution_boundary.network_accessed),
        "wrote_to_repo": bool(pre_execution_boundary.wrote_to_repo),
        "execution_receipt_written": bool(pre_execution_boundary.execution_receipt_written),
    }


def _lab_sandboxed_rebuild_run_test_boundary_required_checks() -> list[str]:
    return [
        "control_binding_found",
        "control_binding_recorded",
        "control_binding_ready",
        "provider_probe_approval_consumed",
        "single_use_consumption_found",
        "single_use_enforced",
        "exact_action_binding_verified",
        "execution_approval_required",
        "execution_approval_consumed",
        "runner_identity_bound",
        "runner_policy_bound",
        "sandbox_policy_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "network_block_bound",
        "timeout_policy_bound",
        "output_capture_bound",
        "kill_switch_bound",
        "execution_receipt_writer_bound",
        "execution_authority_absent",
        "process_not_launched",
        "container_not_launched",
        "commands_not_executed",
        "repo_code_not_executed",
        "install_not_run",
        "build_not_run",
        "tests_not_run",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_receipt_not_written",
        "candidate_not_validated",
        "capability_not_promoted",
    ]


def _lab_sandboxed_rebuild_run_test_boundary_contract_payload(
    *,
    control_binding: LabSandboxProviderRuntimeProbeRunnerControlBinding,
    action_hash: str,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandboxed_rebuild_run_test_boundary",
        "schema_version": 1,
        "mode": "sandboxed_rebuild_run_test_boundary_no_execution",
        "run_mode": "future_sandboxed_rebuild_run_test",
        "approval_id": control_binding.approval_id,
        "approval_consumption_id": control_binding.approval_consumption_id,
        "approval_request_id": control_binding.approval_request_id,
        "invocation_boundary_id": control_binding.invocation_boundary_id,
        "pre_execution_boundary_id": control_binding.pre_execution_boundary_id,
        "control_binding_id": control_binding.id,
        "execution_boundary_id": control_binding.execution_boundary_id,
        "run_boundary_preflight_id": control_binding.run_boundary_preflight_id,
        "source_id": control_binding.source_id,
        "candidate_id": control_binding.candidate_id,
        "candidate_name": control_binding.candidate_name,
        "action": "francis.lab.execute",
        "action_hash": action_hash,
        "depends_on": {
            "control_binding_id": control_binding.id,
            "pre_execution_boundary_id": control_binding.pre_execution_boundary_id,
            "invocation_boundary_id": control_binding.invocation_boundary_id,
            "approval_consumption_id": control_binding.approval_consumption_id,
            "execution_boundary_id": control_binding.execution_boundary_id,
            "run_boundary_preflight_id": control_binding.run_boundary_preflight_id,
        },
        "future_execution_allowed_only_if": {
            "separate_execution_approval_consumed": True,
            "control_binding_ready": True,
            "runner_identity_bound": True,
            "runner_policy_bound": True,
            "sandbox_policy_bound": True,
            "sandbox_bound": True,
            "sandbox_enforced": True,
            "network_block_bound": True,
            "timeout_policy_bound": True,
            "output_capture_bound": True,
            "kill_switch_bound": True,
            "execution_receipt_writer_bound": True,
            "command_allowlist_enforced": True,
            "read_only_source_mount_enforced": True,
        },
        "declared_future_actions": {
            "install": True,
            "build": True,
            "run": True,
            "test": True,
            "validate": True,
        },
        "prohibited_during_boundary_write": {
            "process_launch": True,
            "container_launch": True,
            "command_execution": True,
            "repository_code_execution": True,
            "network_access": True,
            "repository_write": True,
            "execution_receipt_write": True,
            "candidate_validation": True,
            "capability_promotion": True,
        },
        "provider_probe_approval_consumed": control_binding.approval_consumed,
        "execution_approval_required": True,
        "execution_approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_sandboxed_rebuild_run_test_boundary_current_checks(
    *,
    control_binding: LabSandboxProviderRuntimeProbeRunnerControlBinding,
) -> dict[str, Any]:
    return {
        "control_binding_found": bool(control_binding.id),
        "control_binding_recorded": bool(control_binding.control_binding_recorded),
        "control_binding_ready": control_binding.status == "ready",
        "provider_probe_approval_consumed": bool(control_binding.approval_consumed),
        "single_use_consumption_found": bool(control_binding.single_use_consumption_found),
        "single_use_enforced": bool(control_binding.single_use_enforced),
        "exact_action_binding_verified": bool(control_binding.exact_action_binding_verified),
        "execution_approval_required": True,
        "execution_approval_consumed": False,
        "runner_identity_bound": bool(control_binding.runner_identity_bound),
        "runner_policy_bound": bool(control_binding.runner_policy_bound),
        "sandbox_policy_bound": bool(control_binding.sandbox_policy_bound),
        "sandbox_bound": bool(control_binding.sandbox_bound),
        "sandbox_enforced": bool(control_binding.sandbox_enforced),
        "network_block_bound": bool(control_binding.network_block_bound),
        "timeout_policy_bound": bool(control_binding.timeout_policy_bound),
        "output_capture_bound": bool(control_binding.output_capture_bound),
        "kill_switch_bound": bool(control_binding.kill_switch_bound),
        "execution_receipt_writer_bound": bool(control_binding.execution_receipt_writer_bound),
        "rebuild_declared": True,
        "run_declared": True,
        "test_declared": True,
        "execution_authority_absent": not bool(control_binding.execution_authority),
        "process_not_launched": not bool(control_binding.process_launched),
        "container_not_launched": not bool(control_binding.container_launched),
        "commands_not_executed": True,
        "repo_code_not_executed": not bool(control_binding.repo_code_executed),
        "install_not_run": True,
        "build_not_run": True,
        "tests_not_run": True,
        "network_not_accessed": not bool(control_binding.network_accessed),
        "repo_write_not_performed": not bool(control_binding.wrote_to_repo),
        "execution_receipt_not_written": not bool(control_binding.execution_receipt_written),
        "candidate_not_validated": True,
        "capability_not_promoted": True,
        "execution_authority": bool(control_binding.execution_authority),
        "executed": bool(control_binding.executed),
        "process_launched": bool(control_binding.process_launched),
        "container_launched": bool(control_binding.container_launched),
        "commands_executed": False,
        "repo_code_executed": bool(control_binding.repo_code_executed),
        "ran_install": False,
        "ran_build": False,
        "ran_tests": False,
        "network_accessed": bool(control_binding.network_accessed),
        "wrote_to_repo": bool(control_binding.wrote_to_repo),
        "execution_receipt_written": bool(control_binding.execution_receipt_written),
        "candidate_validated": False,
        "capability_promoted": False,
    }


def _lab_sandboxed_rebuild_run_test_runner_binding_required_checks() -> list[str]:
    return [
        "approval_consumption_present",
        "approval_consumed",
        "single_use_enforced",
        "provider_kind_selected",
        "provider_reference_checked",
        "provider_reference_verified",
        "provider_policy_manifest_bound",
        "static_provider_reference_bound",
        "runner_binding_declared",
        "live_runner_bound",
        "sandbox_runner_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "network_block_bound",
        "timeout_policy_bound",
        "output_capture_bound",
        "kill_switch_bound",
        "command_allowlist_bound",
        "source_mount_bound",
        "execution_receipt_writer_bound",
        "provider_binary_not_executed",
        "provider_service_not_queried",
        "execution_authority_absent",
        "process_not_launched",
        "container_not_launched",
        "commands_not_executed",
        "repo_code_not_executed",
        "install_not_run",
        "build_not_run",
        "tests_not_run",
        "network_not_accessed",
        "repo_write_not_performed",
        "execution_receipt_not_written",
        "candidate_not_validated",
        "capability_not_promoted",
    ]


def _lab_sandboxed_rebuild_run_test_runner_binding_contract_payload(
    *,
    consumption: LabSandboxedRebuildRunTestApprovalConsumption,
    provider_kind: str,
    provider_reference: dict[str, Any],
    provider_policy_manifest: dict[str, Any],
    action_hash: str,
) -> dict[str, Any]:
    selected_provider_kind = provider_kind if provider_kind in _lab_sandbox_provider_kind_tokens() else "unselected"
    return {
        "contract_kind": "francis.lab.sandboxed_rebuild_run_test_runner_binding",
        "schema_version": 1,
        "mode": "static_provider_reference_only_no_live_runner",
        "approval_id": consumption.approval_id,
        "approval_consumption_id": consumption.id,
        "approval_request_id": consumption.approval_request_id,
        "sandboxed_boundary_id": consumption.sandboxed_boundary_id,
        "control_binding_id": consumption.control_binding_id,
        "source_id": consumption.source_id,
        "candidate_id": consumption.candidate_id,
        "candidate_name": consumption.candidate_name,
        "action": consumption.action,
        "action_hash": action_hash,
        "allowed_provider_kinds": _lab_sandbox_provider_kind_tokens(),
        "requested_provider_kind": provider_kind,
        "selected_provider_kind": selected_provider_kind,
        "provider_reference": provider_reference,
        "provider_policy_manifest": provider_policy_manifest,
        "runner_binding_declared": True,
        "static_provider_reference_only": True,
        "requires_explicit_provider_kind": True,
        "requires_local_provider_reference": True,
        "requires_provider_policy_manifest": True,
        "requires_future_live_runner_binding": True,
        "requires_future_sandbox_enforcement": True,
        "requires_future_execution_receipt_writer": True,
        "live_runner_bound": False,
        "sandbox_runner_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "provider_binary_execution_allowed": False,
        "provider_service_query_allowed": False,
        "repository_command_execution_allowed": False,
        "execution_receipt_write_allowed": False,
        "requires": _lab_sandboxed_rebuild_run_test_runner_binding_required_checks(),
    }


def _lab_sandboxed_rebuild_run_test_runner_binding_current_checks(
    *,
    consumption: LabSandboxedRebuildRunTestApprovalConsumption,
    provider_kind: str,
    provider_reference: dict[str, Any],
    provider_policy_manifest: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    selected_provider_kind = _safe_str(contract.get("selected_provider_kind")).strip()
    provider_kind_selected = bool(selected_provider_kind and selected_provider_kind != "unselected")
    provider_reference_verified = bool(provider_reference.get("reference_verified"))
    provider_policy_manifest_bound = bool(provider_policy_manifest.get("bound"))
    static_provider_reference_bound = bool(
        provider_kind_selected and provider_reference_verified and provider_policy_manifest_bound
    )
    return {
        "approval_consumption_present": bool(consumption.id),
        "approval_consumed": bool(consumption.approval_consumed),
        "single_use_enforced": bool(consumption.single_use_enforced),
        "provider_kind_selected": provider_kind_selected,
        "provider_kind_allowed": provider_kind in _lab_sandbox_provider_kind_tokens(),
        "provider_reference_checked": bool(provider_reference.get("metadata_checked")),
        "provider_reference_present": bool(provider_reference.get("reference_present")),
        "provider_reference_verified": provider_reference_verified,
        "provider_policy_manifest_present": bool(provider_policy_manifest.get("present")),
        "provider_policy_manifest_bound": provider_policy_manifest_bound,
        "static_provider_reference_bound": static_provider_reference_bound,
        "runner_binding_declared": bool(contract.get("runner_binding_declared")),
        "live_runner_bound": False,
        "sandbox_runner_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "network_block_bound": False,
        "timeout_policy_bound": False,
        "output_capture_bound": False,
        "kill_switch_bound": False,
        "command_allowlist_bound": False,
        "source_mount_bound": False,
        "execution_receipt_writer_bound": False,
        "provider_binary_not_executed": True,
        "provider_service_not_queried": True,
        "execution_authority_absent": not bool(consumption.execution_authority),
        "process_not_launched": not bool(consumption.process_launched),
        "container_not_launched": not bool(consumption.container_launched),
        "commands_not_executed": not bool(consumption.commands_executed),
        "repo_code_not_executed": not bool(consumption.repo_code_executed),
        "install_not_run": not bool(consumption.ran_install),
        "build_not_run": not bool(consumption.ran_build),
        "tests_not_run": not bool(consumption.ran_tests),
        "network_not_accessed": not bool(consumption.network_accessed),
        "repo_write_not_performed": not bool(consumption.wrote_to_repo),
        "execution_receipt_not_written": not bool(consumption.execution_receipt_written),
        "candidate_not_validated": not bool(consumption.candidate_validated),
        "capability_not_promoted": not bool(consumption.capability_promoted),
        "provider_binary_executed": False,
        "provider_service_queried": False,
        "execution_authority": bool(consumption.execution_authority),
        "executed": bool(consumption.executed),
        "process_launched": bool(consumption.process_launched),
        "container_launched": bool(consumption.container_launched),
        "commands_executed": bool(consumption.commands_executed),
        "repo_code_executed": bool(consumption.repo_code_executed),
        "network_accessed": bool(consumption.network_accessed),
        "wrote_to_repo": bool(consumption.wrote_to_repo),
        "execution_receipt_written": bool(consumption.execution_receipt_written),
        "candidate_validated": bool(consumption.candidate_validated),
        "capability_promoted": bool(consumption.capability_promoted),
    }


def _lab_sandboxed_rebuild_run_test_sandbox_policy_required_checks() -> list[str]:
    return [
        "approval_consumption_present",
        "approval_consumed",
        "single_use_enforced",
        "runner_binding_present",
        "static_provider_reference_bound",
        "provider_kind_selected",
        "sandbox_policy_declared",
        "network_default_deny",
        "filesystem_read_only",
        "repo_write_disallowed",
        "destructive_disallowed",
        "secret_storage_disallowed",
        "process_launch_disallowed",
        "container_launch_disallowed",
        "provider_execution_disallowed",
        "provider_service_query_disallowed",
        "command_execution_disabled",
        "env_passthrough_disallowed",
        "no_execution_authority",
        "no_repo_execution",
        "no_network_access",
        "no_repo_write",
        "no_execution_receipt_written",
        "command_allowlist_bound",
        "execution_receipt_writer_bound",
        "live_sandbox_bound",
        "sandbox_enforced",
        "timeout_policy_bound",
        "output_capture_bound",
        "kill_switch_bound",
    ]


def _lab_sandboxed_rebuild_run_test_sandbox_policy_payload(
    *,
    consumption: LabSandboxedRebuildRunTestApprovalConsumption,
    runner_binding: LabSandboxedRebuildRunTestRunnerBindingPreflight,
    action_hash: str,
) -> dict[str, Any]:
    return {
        "policy_kind": "francis.lab.sandboxed_rebuild_run_test_sandbox_policy",
        "schema_version": 1,
        "mode": "policy_preflight_no_live_sandbox",
        "approval_id": consumption.approval_id,
        "approval_consumption_id": consumption.id,
        "runner_binding_id": runner_binding.id,
        "approval_request_id": consumption.approval_request_id,
        "sandboxed_boundary_id": consumption.sandboxed_boundary_id,
        "control_binding_id": consumption.control_binding_id,
        "source_id": consumption.source_id,
        "candidate_id": consumption.candidate_id,
        "candidate_name": consumption.candidate_name,
        "action": consumption.action,
        "action_hash": action_hash,
        "network_policy": {
            "default": "deny",
            "network": False,
            "egress_allowed": False,
            "provider_service_query_allowed": False,
        },
        "filesystem_policy": {
            "source_mount": "read_only_reference",
            "repo_write_allowed": False,
            "write": False,
            "destructive": False,
        },
        "process_policy": {
            "process_launch_allowed": False,
            "container_launch_allowed": False,
            "provider_binary_execution_allowed": False,
            "repository_command_execution_allowed": False,
        },
        "secret_policy": {
            "store_file_contents": False,
            "store_sensitive_values": False,
            "env_passthrough_allowed": False,
        },
        "command_policy": {
            "command_execution_enabled": False,
            "command_allowlist_required": True,
            "command_allowlist_bound": False,
        },
        "receipt_policy": {
            "execution_receipt_writer_required": True,
            "execution_receipt_writer_bound": False,
            "execution_receipt_write_allowed": False,
        },
        "resource_policy": {
            "timeout_required": True,
            "timeout_policy_bound": False,
            "output_capture_bound": False,
            "kill_switch_bound": False,
        },
        "requires_future_live_sandbox": True,
        "requires_future_sandbox_enforcement": True,
        "requires_future_command_allowlist_binding": True,
        "requires_future_execution_receipt_writer": True,
        "requires": _lab_sandboxed_rebuild_run_test_sandbox_policy_required_checks(),
    }


def _lab_sandboxed_rebuild_run_test_sandbox_policy_current_checks(
    *,
    consumption: LabSandboxedRebuildRunTestApprovalConsumption,
    runner_binding: LabSandboxedRebuildRunTestRunnerBindingPreflight,
    sandbox_policy: dict[str, Any],
) -> dict[str, Any]:
    network_policy = _as_dict(sandbox_policy.get("network_policy"))
    filesystem_policy = _as_dict(sandbox_policy.get("filesystem_policy"))
    process_policy = _as_dict(sandbox_policy.get("process_policy"))
    secret_policy = _as_dict(sandbox_policy.get("secret_policy"))
    command_policy = _as_dict(sandbox_policy.get("command_policy"))
    receipt_policy = _as_dict(sandbox_policy.get("receipt_policy"))
    resource_policy = _as_dict(sandbox_policy.get("resource_policy"))
    provider_kind_selected = bool(
        runner_binding.selected_provider_kind and runner_binding.selected_provider_kind != "unselected"
    )
    return {
        "approval_consumption_present": bool(consumption.id),
        "approval_consumed": bool(consumption.approval_consumed),
        "single_use_enforced": bool(consumption.single_use_enforced),
        "runner_binding_present": bool(runner_binding.id),
        "static_provider_reference_bound": bool(runner_binding.static_provider_reference_bound),
        "provider_kind_selected": provider_kind_selected,
        "sandbox_policy_declared": bool(sandbox_policy),
        "network_default_deny": network_policy.get("default") == "deny"
        and network_policy.get("network") is False
        and network_policy.get("egress_allowed") is False,
        "filesystem_read_only": filesystem_policy.get("source_mount") == "read_only_reference",
        "repo_write_disallowed": filesystem_policy.get("repo_write_allowed") is False
        and filesystem_policy.get("write") is False,
        "destructive_disallowed": filesystem_policy.get("destructive") is False,
        "secret_storage_disallowed": secret_policy.get("store_file_contents") is False
        and secret_policy.get("store_sensitive_values") is False,
        "process_launch_disallowed": process_policy.get("process_launch_allowed") is False,
        "container_launch_disallowed": process_policy.get("container_launch_allowed") is False,
        "provider_execution_disallowed": process_policy.get("provider_binary_execution_allowed") is False,
        "provider_service_query_disallowed": network_policy.get("provider_service_query_allowed") is False,
        "command_execution_disabled": command_policy.get("command_execution_enabled") is False,
        "env_passthrough_disallowed": secret_policy.get("env_passthrough_allowed") is False,
        "no_execution_authority": not bool(consumption.execution_authority or runner_binding.execution_authority),
        "no_repo_execution": not bool(consumption.repo_code_executed or runner_binding.repo_code_executed),
        "no_network_access": not bool(consumption.network_accessed or runner_binding.network_accessed),
        "no_repo_write": not bool(consumption.wrote_to_repo or runner_binding.wrote_to_repo),
        "no_execution_receipt_written": not bool(
            consumption.execution_receipt_written or runner_binding.execution_receipt_written
        ),
        "command_allowlist_bound": bool(command_policy.get("command_allowlist_bound")),
        "execution_receipt_writer_bound": bool(receipt_policy.get("execution_receipt_writer_bound")),
        "live_sandbox_bound": False,
        "sandbox_enforced": False,
        "timeout_policy_bound": bool(resource_policy.get("timeout_policy_bound")),
        "output_capture_bound": bool(resource_policy.get("output_capture_bound")),
        "kill_switch_bound": bool(resource_policy.get("kill_switch_bound")),
        "execution_authority": bool(consumption.execution_authority or runner_binding.execution_authority),
        "executed": bool(consumption.executed or runner_binding.executed),
        "process_launched": bool(consumption.process_launched or runner_binding.process_launched),
        "container_launched": bool(consumption.container_launched or runner_binding.container_launched),
        "commands_executed": bool(consumption.commands_executed or runner_binding.commands_executed),
        "repo_code_executed": bool(consumption.repo_code_executed or runner_binding.repo_code_executed),
        "network_accessed": bool(consumption.network_accessed or runner_binding.network_accessed),
        "wrote_to_repo": bool(consumption.wrote_to_repo or runner_binding.wrote_to_repo),
        "execution_receipt_written": bool(
            consumption.execution_receipt_written or runner_binding.execution_receipt_written
        ),
    }


def _lab_approval_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    if not record:
        return {}
    payload = _as_dict(record.get("payload"))
    return {
        "id": _safe_str(record.get("id")).strip(),
        "status": _safe_str(record.get("status")).strip(),
        "action": _safe_str(record.get("action")).strip(),
        "reason": _safe_str(record.get("reason")).strip(),
        "ts": record.get("ts"),
        "decision": _safe_str(record.get("decision")).strip(),
        "decision_actor": _safe_str(record.get("decision_actor")).strip(),
        "decided_ts": record.get("decided_ts"),
        "payload": payload,
    }


def _lab_approval_binding(
    *,
    preflight: LabExecutionPreflight,
    approval_id: str,
    approval_status: str,
    approval_record: dict[str, Any],
    approval_path: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    payload = _as_dict(approval_record.get("payload"))
    expected = {
        "action": "francis.lab.execute",
        "action_hash": preflight.action_hash,
        "preflight_id": preflight.id,
        "plan_id": preflight.plan_id,
        "workspace_id": preflight.workspace_id,
        "source_id": preflight.source_id,
        "candidate_id": preflight.candidate_id,
        "candidate_name": preflight.candidate_name,
    }
    actual = {
        "action": _safe_str(approval_record.get("action")).strip(),
        "payload_action": _safe_str(payload.get("action")).strip(),
        "action_hash": _safe_str(payload.get("action_hash")).strip(),
        "preflight_id": _safe_str(payload.get("preflight_id")).strip(),
        "plan_id": _safe_str(payload.get("plan_id")).strip(),
        "workspace_id": _safe_str(payload.get("workspace_id")).strip(),
        "source_id": _safe_str(payload.get("source_id")).strip(),
        "candidate_id": _safe_str(payload.get("candidate_id")).strip(),
        "candidate_name": _safe_str(payload.get("candidate_name")).strip(),
    }

    blockers: list[str] = []
    mismatch_fields: list[str] = []
    approval_record_found = approval_status in {"approved", "pending", "rejected", "emergency"} and bool(
        approval_record
    )
    if not approval_record_found:
        blockers.append(f"approval_record_{approval_status}")
    elif approval_status == "pending":
        blockers.append("approval_not_approved")
    elif approval_status == "rejected":
        blockers.append("approval_rejected")
    elif approval_status == "emergency":
        blockers.append("approval_emergency_not_consumable")
    elif approval_status != "approved":
        blockers.append("approval_not_approved")

    top_action_matches = actual["action"] == expected["action"]
    payload_action_matches = actual["payload_action"] in {"", expected["action"]}
    if approval_record_found and not top_action_matches:
        blockers.append("approval_action_mismatch")
        mismatch_fields.append("action")
    if approval_record_found and not payload_action_matches:
        blockers.append("approval_payload_action_mismatch")
        mismatch_fields.append("payload_action")

    field_matches: dict[str, bool] = {}
    for field in (
        "action_hash",
        "preflight_id",
        "plan_id",
        "workspace_id",
        "source_id",
        "candidate_id",
        "candidate_name",
    ):
        matches = actual[field] == expected[field]
        field_matches[field] = matches
        if approval_record_found and not matches:
            blockers.append(f"approval_{field}_mismatch")
            mismatch_fields.append(field)

    exact_match = (
        approval_record_found and top_action_matches and payload_action_matches and all(field_matches.values())
    )
    if approval_record_found and not exact_match:
        blockers.append("approval_exact_action_binding_mismatch")
    if approval_record_found and (
        not field_matches.get("action_hash", False) or not field_matches.get("preflight_id", False)
    ):
        blockers.append("approval_stale_or_wrong_preflight")

    consumption_record, consumption_path = _find_lab_approval_consumption(approval_id)
    approval_consumed = consumption_record is not None
    if approval_consumed:
        blockers.append("approval_already_consumed")

    refused = (
        approval_status in {"invalid", "missing", "corrupt", "rejected", "emergency"}
        or (approval_record_found and not exact_match)
        or approval_consumed
    )
    binding = {
        "approval_id": approval_id,
        "approval_status": approval_status,
        "approval_path": str(approval_path) if approval_path is not None else "",
        "approval_consumption_record_id": consumption_record.id if consumption_record is not None else "",
        "approval_consumption_record_path": str(consumption_path) if consumption_path is not None else "",
        "approval_record_found": approval_record_found,
        "approval_approved": approval_status == "approved",
        "expected": expected,
        "actual": actual,
        "field_matches": field_matches,
        "action_matches": top_action_matches and payload_action_matches,
        "exact_match": exact_match,
        "mismatch_fields": mismatch_fields,
        "refused": refused,
        "approval_consumed": approval_consumed,
        "execution_authority": False,
    }
    return binding, _append_unique([], *blockers)


def _lab_sandbox_provider_runtime_probe_approval_binding(
    *,
    approval_request: LabSandboxProviderRuntimeProbeApprovalRequest | None,
    approval_id: str,
    approval_status: str,
    approval_record: dict[str, Any],
    approval_path: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    payload = _as_dict(approval_record.get("payload"))
    expected = {
        "action": "francis.lab.sandbox_provider_runtime_probe",
        "approval_id": approval_request.approval_id if approval_request is not None else approval_id,
        "action_hash": approval_request.action_hash if approval_request is not None else "",
        "approval_request_id": approval_request.id if approval_request is not None else "",
        "upstream_approval_id": approval_request.upstream_approval_id if approval_request is not None else "",
        "execution_boundary_id": approval_request.execution_boundary_id if approval_request is not None else "",
        "run_boundary_preflight_id": (
            approval_request.run_boundary_preflight_id if approval_request is not None else ""
        ),
        "source_id": approval_request.source_id if approval_request is not None else "",
        "candidate_id": approval_request.candidate_id if approval_request is not None else "",
        "candidate_name": approval_request.candidate_name if approval_request is not None else "",
    }
    actual = {
        "action": _safe_str(approval_record.get("action")).strip(),
        "payload_action": _safe_str(payload.get("action")).strip(),
        "approval_id": approval_id,
        "action_hash": _safe_str(payload.get("action_hash")).strip(),
        "upstream_approval_id": _safe_str(payload.get("upstream_approval_id")).strip(),
        "execution_boundary_id": _safe_str(payload.get("execution_boundary_id")).strip(),
        "run_boundary_preflight_id": _safe_str(payload.get("run_boundary_preflight_id")).strip(),
        "source_id": _safe_str(payload.get("source_id")).strip(),
        "candidate_id": _safe_str(payload.get("candidate_id")).strip(),
        "candidate_name": _safe_str(payload.get("candidate_name")).strip(),
    }

    blockers: list[str] = []
    mismatch_fields: list[str] = []
    approval_record_found = approval_status in {"approved", "pending", "rejected", "emergency"} and bool(
        approval_record
    )
    if approval_request is None:
        blockers.append("provider_runtime_probe_approval_request_missing")
    if not approval_record_found:
        blockers.append(f"approval_record_{approval_status}")
    elif approval_status == "pending":
        blockers.append("approval_not_approved")
    elif approval_status == "rejected":
        blockers.append("approval_rejected")
    elif approval_status == "emergency":
        blockers.append("approval_emergency_not_consumable")
    elif approval_status != "approved":
        blockers.append("approval_not_approved")

    top_action_matches = actual["action"] == expected["action"]
    payload_action_matches = actual["payload_action"] in {"", expected["action"]}
    if approval_record_found and not top_action_matches:
        blockers.append("approval_action_mismatch")
        mismatch_fields.append("action")
    if approval_record_found and not payload_action_matches:
        blockers.append("approval_payload_action_mismatch")
        mismatch_fields.append("payload_action")

    field_matches: dict[str, bool] = {}
    for field in (
        "action_hash",
        "upstream_approval_id",
        "execution_boundary_id",
        "run_boundary_preflight_id",
        "source_id",
        "candidate_id",
        "candidate_name",
    ):
        matches = bool(expected[field]) and actual[field] == expected[field]
        field_matches[field] = matches
        if approval_record_found and not matches:
            blockers.append(f"approval_{field}_mismatch")
            mismatch_fields.append(field)

    approval_id_matches = approval_id == expected["approval_id"]
    field_matches["approval_id"] = approval_id_matches
    if not approval_id_matches:
        blockers.append("approval_id_mismatch")
        mismatch_fields.append("approval_id")

    exact_match = (
        approval_request is not None
        and approval_record_found
        and top_action_matches
        and payload_action_matches
        and all(field_matches.values())
    )
    if approval_record_found and not exact_match:
        blockers.append("approval_exact_action_binding_mismatch")
    if approval_record_found and (
        not field_matches.get("action_hash", False)
        or not field_matches.get("execution_boundary_id", False)
        or not field_matches.get("source_id", False)
        or not field_matches.get("candidate_id", False)
    ):
        blockers.append("approval_stale_or_wrong_provider_probe_request")

    provider_consumption_record, provider_consumption_path = (
        _find_lab_sandbox_provider_runtime_probe_approval_consumption(approval_id)
    )
    generic_consumption_record, generic_consumption_path = _find_lab_approval_consumption(approval_id)
    approval_consumed = provider_consumption_record is not None or generic_consumption_record is not None
    if provider_consumption_record is not None:
        blockers.append("provider_runtime_probe_approval_already_consumed")
    if generic_consumption_record is not None:
        blockers.append("approval_already_consumed_by_lab_execution")

    refused = (
        approval_status in {"invalid", "missing", "corrupt", "rejected", "emergency"}
        or (approval_record_found and not exact_match)
        or approval_consumed
        or approval_request is None
    )
    binding = {
        "approval_id": approval_id,
        "approval_status": approval_status,
        "approval_path": str(approval_path) if approval_path is not None else "",
        "provider_runtime_probe_approval_request_id": expected["approval_request_id"],
        "provider_runtime_probe_approval_consumption_record_id": (
            provider_consumption_record.id if provider_consumption_record is not None else ""
        ),
        "provider_runtime_probe_approval_consumption_record_path": (
            str(provider_consumption_path) if provider_consumption_path is not None else ""
        ),
        "generic_approval_consumption_record_id": (
            generic_consumption_record.id if generic_consumption_record is not None else ""
        ),
        "generic_approval_consumption_record_path": (
            str(generic_consumption_path) if generic_consumption_path is not None else ""
        ),
        "approval_record_found": approval_record_found,
        "approval_approved": approval_status == "approved",
        "expected": expected,
        "actual": actual,
        "field_matches": field_matches,
        "action_matches": top_action_matches and payload_action_matches,
        "exact_match": exact_match,
        "mismatch_fields": mismatch_fields,
        "refused": refused,
        "approval_consumed": approval_consumed,
        "provider_runtime_probe_performed": False,
        "execution_authority": False,
    }
    return binding, _append_unique([], *blockers)


def _lab_sandboxed_rebuild_run_test_approval_binding(
    *,
    approval_request: LabSandboxedRebuildRunTestApprovalRequest | None,
    approval_id: str,
    approval_status: str,
    approval_record: dict[str, Any],
    approval_path: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    payload = _as_dict(approval_record.get("payload"))
    expected = {
        "action": "francis.lab.sandboxed_rebuild_run_test",
        "approval_id": approval_request.approval_id if approval_request is not None else approval_id,
        "action_hash": approval_request.action_hash if approval_request is not None else "",
        "approval_request_id": approval_request.id if approval_request is not None else "",
        "upstream_approval_id": approval_request.upstream_approval_id if approval_request is not None else "",
        "sandboxed_boundary_id": approval_request.sandboxed_boundary_id if approval_request is not None else "",
        "control_binding_id": approval_request.control_binding_id if approval_request is not None else "",
        "source_id": approval_request.source_id if approval_request is not None else "",
        "candidate_id": approval_request.candidate_id if approval_request is not None else "",
        "candidate_name": approval_request.candidate_name if approval_request is not None else "",
    }
    actual = {
        "action": _safe_str(approval_record.get("action")).strip(),
        "payload_action": _safe_str(payload.get("action")).strip(),
        "approval_id": approval_id,
        "action_hash": _safe_str(payload.get("action_hash")).strip(),
        "upstream_approval_id": _safe_str(payload.get("upstream_approval_id")).strip(),
        "sandboxed_boundary_id": _safe_str(payload.get("sandboxed_boundary_id")).strip(),
        "control_binding_id": _safe_str(payload.get("control_binding_id")).strip(),
        "source_id": _safe_str(payload.get("source_id")).strip(),
        "candidate_id": _safe_str(payload.get("candidate_id")).strip(),
        "candidate_name": _safe_str(payload.get("candidate_name")).strip(),
    }

    blockers: list[str] = []
    mismatch_fields: list[str] = []
    approval_record_found = approval_status in {"approved", "pending", "rejected", "emergency"} and bool(
        approval_record
    )
    if approval_request is None:
        blockers.append("sandboxed_rebuild_run_test_approval_request_missing")
    if not approval_record_found:
        blockers.append(f"approval_record_{approval_status}")
    elif approval_status == "pending":
        blockers.append("approval_not_approved")
    elif approval_status == "rejected":
        blockers.append("approval_rejected")
    elif approval_status == "emergency":
        blockers.append("approval_emergency_not_consumable")
    elif approval_status != "approved":
        blockers.append("approval_not_approved")

    top_action_matches = actual["action"] == expected["action"]
    payload_action_matches = actual["payload_action"] in {"", expected["action"]}
    if approval_record_found and not top_action_matches:
        blockers.append("approval_action_mismatch")
        mismatch_fields.append("action")
    if approval_record_found and not payload_action_matches:
        blockers.append("approval_payload_action_mismatch")
        mismatch_fields.append("payload_action")

    field_matches: dict[str, bool] = {}
    for field in (
        "action_hash",
        "upstream_approval_id",
        "sandboxed_boundary_id",
        "control_binding_id",
        "source_id",
        "candidate_id",
        "candidate_name",
    ):
        matches = bool(expected[field]) and actual[field] == expected[field]
        field_matches[field] = matches
        if approval_record_found and not matches:
            blockers.append(f"approval_{field}_mismatch")
            mismatch_fields.append(field)

    approval_id_matches = approval_id == expected["approval_id"]
    field_matches["approval_id"] = approval_id_matches
    if not approval_id_matches:
        blockers.append("approval_id_mismatch")
        mismatch_fields.append("approval_id")

    exact_match = (
        approval_request is not None
        and approval_record_found
        and top_action_matches
        and payload_action_matches
        and all(field_matches.values())
    )
    if approval_record_found and not exact_match:
        blockers.append("approval_exact_action_binding_mismatch")
    if approval_record_found and (
        not field_matches.get("action_hash", False)
        or not field_matches.get("sandboxed_boundary_id", False)
        or not field_matches.get("source_id", False)
        or not field_matches.get("candidate_id", False)
    ):
        blockers.append("approval_stale_or_wrong_sandboxed_rebuild_run_test_request")

    sandboxed_consumption_record, sandboxed_consumption_path = (
        _find_lab_sandboxed_rebuild_run_test_approval_consumption(approval_id)
    )
    generic_consumption_record, generic_consumption_path = _find_lab_approval_consumption(approval_id)
    approval_consumed = sandboxed_consumption_record is not None or generic_consumption_record is not None
    if sandboxed_consumption_record is not None:
        blockers.append("sandboxed_rebuild_run_test_approval_already_consumed")
    if generic_consumption_record is not None:
        blockers.append("approval_already_consumed_by_lab_execution")

    refused = (
        approval_status in {"invalid", "missing", "corrupt", "rejected", "emergency"}
        or (approval_record_found and not exact_match)
        or approval_consumed
        or approval_request is None
    )
    binding = {
        "approval_id": approval_id,
        "approval_status": approval_status,
        "approval_path": str(approval_path) if approval_path is not None else "",
        "sandboxed_rebuild_run_test_approval_request_id": expected["approval_request_id"],
        "sandboxed_rebuild_run_test_approval_consumption_record_id": (
            sandboxed_consumption_record.id if sandboxed_consumption_record is not None else ""
        ),
        "sandboxed_rebuild_run_test_approval_consumption_record_path": (
            str(sandboxed_consumption_path) if sandboxed_consumption_path is not None else ""
        ),
        "generic_approval_consumption_record_id": (
            generic_consumption_record.id if generic_consumption_record is not None else ""
        ),
        "generic_approval_consumption_record_path": (
            str(generic_consumption_path) if generic_consumption_path is not None else ""
        ),
        "approval_record_found": approval_record_found,
        "approval_approved": approval_status == "approved",
        "expected": expected,
        "actual": actual,
        "field_matches": field_matches,
        "action_matches": top_action_matches and payload_action_matches,
        "exact_match": exact_match,
        "mismatch_fields": mismatch_fields,
        "refused": refused,
        "approval_consumed": approval_consumed,
        "commands_executed": False,
        "execution_authority": False,
    }
    return binding, _append_unique([], *blockers)


def _lab_runner_required_controls() -> list[str]:
    return [
        "approved_exact_action_record",
        "approval_action_hash_matches_preflight",
        "source_candidate_workspace_identity_matches",
        "approval_not_stale_or_reused",
        "governed_runner_bound",
        "sandboxed_workspace",
        "source_copy_or_mount_policy",
        "network_isolation_enforced",
        "filesystem_write_boundary_enforced",
        "resource_limits_enforced",
        "execution_receipt_sink_bound",
    ]


def _lab_runner_readiness_required_controls() -> list[str]:
    return [
        "approved_exact_action_record",
        "approval_not_stale_or_reused",
        "workspace_manifest_present",
        "workspace_subdirs_present",
        "source_reference_read_only",
        "source_not_copied",
        "source_write_blocked",
        "governed_runner_bound",
        "command_allowlist_declared",
        "environment_scrubbing_policy_declared",
        "network_isolation_enforced",
        "filesystem_write_boundary_enforced",
        "resource_limits_enforced",
        "timeout_policy_enforced",
        "stdout_stderr_capture_bound",
        "execution_receipt_sink_bound",
    ]


def _lab_runner_readiness_current_controls(
    *,
    workspace: LabWorkspaceRecord,
    preflight: LabExecutionPreflight,
    binding: dict[str, Any],
) -> dict[str, Any]:
    workspace_path = _safe_str(workspace.path).strip()
    workspace_root = Path(workspace_path) if workspace_path else None
    manifest_path = _safe_str(workspace.manifest_path).strip()
    manifest = Path(manifest_path) if manifest_path else None
    allowed_write_subdirs = [
        _safe_str(item).strip() for item in (workspace.workspace_policy.get("allowed_write_subdirs") or [])
    ]
    workspace_subdirs_present = False
    if workspace_root is not None:
        workspace_subdirs_present = all(
            (workspace_root / child).is_dir() for child in ("work", "artifacts", "logs", "tmp")
        )
    source_reference_read_only = _safe_str(workspace.source_reference.get("mode")).strip() == "reference_only_read_only"
    source_write_blocked = not bool(workspace.workspace_policy.get("source_write_allowed"))
    exact_approval = bool(binding.get("approval_approved")) and bool(binding.get("exact_match"))
    approval_not_stale = exact_approval and not bool(binding.get("refused"))
    return {
        "approved_exact_action_record": exact_approval,
        "approval_not_stale_or_reused": approval_not_stale,
        "workspace_manifest_present": bool(manifest and manifest.exists()),
        "workspace_subdirs_present": workspace_subdirs_present,
        "source_reference_read_only": source_reference_read_only,
        "source_not_copied": not workspace.source_copied,
        "source_write_blocked": source_write_blocked,
        "governed_runner_bound": False,
        "command_allowlist_declared": False,
        "environment_scrubbing_policy_declared": False,
        "network_isolation_enforced": bool(workspace.workspace_policy.get("network_isolation_enforced")),
        "filesystem_write_boundary_enforced": False,
        "resource_limits_enforced": False,
        "timeout_policy_enforced": False,
        "stdout_stderr_capture_bound": False,
        "execution_receipt_sink_bound": False,
        "workspace_path": workspace_path,
        "manifest_path": manifest_path,
        "allowed_write_subdirs": allowed_write_subdirs,
        "preflight_status": preflight.status,
        "preflight_execution_ready": bool(preflight.readiness.get("execution_ready")),
        "approval_status": _safe_str(binding.get("approval_status")).strip(),
        "approval_exact_match": bool(binding.get("exact_match")),
        "approval_consumed": bool(binding.get("approval_consumed")),
        "execution_authority": False,
    }


def _lab_runner_binding_required_controls() -> list[str]:
    return [
        "approved_exact_action_record",
        "approval_not_stale_or_reused",
        "runner_readiness_ready",
        "governed_runner_bound",
        "runner_identity_verified",
        "runner_contract_loaded",
        "command_allowlist_bound",
        "environment_scrubbing_bound",
        "network_policy_bound",
        "filesystem_policy_bound",
        "resource_policy_bound",
        "timeout_policy_bound",
        "stdout_stderr_capture_bound",
        "execution_receipt_sink_bound",
        "execution_receipt_schema_bound",
        "execution_receipt_prewrite_bound",
        "execution_receipt_final_write_bound",
        "approval_consumption_ready",
    ]


def _lab_runner_binding_contract(
    *,
    readiness: LabRunnerReadiness,
    preflight: LabExecutionPreflight,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "runner_kind": readiness.runner_kind or "francis.lab.runner",
        "binding_mode": "preflight_contract_only",
        "runner_id": "",
        "runner_binary_path": "",
        "runner_version": "",
        "runner_bound": False,
        "runner_identity_verified": False,
        "runner_contract_loaded": False,
        "execution_enabled": False,
        "workspace_id": workspace.id,
        "workspace_path": workspace.path,
        "preflight_id": preflight.id,
        "action_hash": preflight.action_hash,
        "command_allowlist_bound": False,
        "environment_scrubbing_bound": False,
        "network_policy_bound": False,
        "filesystem_policy_bound": False,
        "resource_policy_bound": False,
        "timeout_policy_bound": False,
        "stdout_stderr_capture_bound": False,
        "approval_consumption_required": True,
        "approval_consumed": False,
    }


def _lab_execution_receipt_sink_contract() -> dict[str, Any]:
    return {
        "sink_kind": "francis.lab.execution_receipts",
        "binding_mode": "preflight_contract_only",
        "schema_version": 1,
        "sink_id": "",
        "bound": False,
        "artifact_root": str(ingest_artifact_root() / "lab_execution_receipts"),
        "required_receipt_operation": "lab.execution.run",
        "prewrite_bound": False,
        "final_write_bound": False,
        "captures_exit_code": False,
        "captures_stdout_stderr_refs": False,
        "captures_artifact_refs": False,
        "captures_network_summary": False,
        "captures_filesystem_write_summary": False,
        "sensitive_values_redacted": True,
    }


def _lab_runner_binding_current_controls(
    *,
    readiness: LabRunnerReadiness,
    runner_binding: dict[str, Any],
    execution_receipt_sink: dict[str, Any],
) -> dict[str, Any]:
    readiness_controls = readiness.current_controls
    return {
        "approved_exact_action_record": bool(readiness_controls.get("approved_exact_action_record")),
        "approval_not_stale_or_reused": bool(readiness_controls.get("approval_not_stale_or_reused")),
        "runner_readiness_ready": readiness.status == "ready",
        "governed_runner_bound": bool(runner_binding.get("runner_bound")),
        "runner_identity_verified": bool(runner_binding.get("runner_identity_verified")),
        "runner_contract_loaded": bool(runner_binding.get("runner_contract_loaded")),
        "command_allowlist_bound": bool(runner_binding.get("command_allowlist_bound")),
        "environment_scrubbing_bound": bool(runner_binding.get("environment_scrubbing_bound")),
        "network_policy_bound": bool(runner_binding.get("network_policy_bound")),
        "filesystem_policy_bound": bool(runner_binding.get("filesystem_policy_bound")),
        "resource_policy_bound": bool(runner_binding.get("resource_policy_bound")),
        "timeout_policy_bound": bool(runner_binding.get("timeout_policy_bound")),
        "stdout_stderr_capture_bound": bool(runner_binding.get("stdout_stderr_capture_bound")),
        "execution_receipt_sink_bound": bool(execution_receipt_sink.get("bound")),
        "execution_receipt_schema_bound": bool(execution_receipt_sink.get("schema_version"))
        and bool(execution_receipt_sink.get("bound")),
        "execution_receipt_prewrite_bound": bool(execution_receipt_sink.get("prewrite_bound")),
        "execution_receipt_final_write_bound": bool(execution_receipt_sink.get("final_write_bound")),
        "approval_consumption_ready": False,
        "approval_consumed": False,
        "runner_bound": False,
        "receipt_sink_bound": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_runner_enforcement_required_checks() -> list[str]:
    return [
        "runner_binding_record_present",
        "runner_binding_status_ready",
        "runner_readiness_status_ready",
        "workspace_matches_binding",
        "action_hash_matches_binding",
        "runner_bound",
        "runner_identity_verified",
        "runner_binary_declared",
        "runner_contract_loaded",
        "command_allowlist_bound",
        "environment_scrubbing_bound",
        "network_policy_bound",
        "filesystem_policy_bound",
        "resource_policy_bound",
        "timeout_policy_bound",
        "stdout_stderr_capture_bound",
        "execution_receipt_sink_bound",
        "execution_receipt_schema_bound",
        "execution_receipt_prewrite_bound",
        "execution_receipt_final_write_bound",
        "receipt_sink_sensitive_redaction_declared",
        "approval_consumption_ready",
        "approval_consumed",
    ]


def _lab_runner_enforcement_interface(
    *,
    binding_preflight: LabRunnerBindingPreflight,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "interface_kind": "francis.lab.runner.enforcement",
        "schema_version": 1,
        "mode": "preflight_only_no_execution",
        "execution_enabled": False,
        "runner_binding_id": binding_preflight.id,
        "workspace_id": workspace.id,
        "workspace_path": workspace.path,
        "requires": [
            "verified_runner_identity",
            "declared_runner_binary",
            "loaded_runner_contract",
            "bound_command_allowlist",
            "bound_environment_scrubbing",
            "bound_network_policy",
            "bound_filesystem_policy",
            "bound_resource_policy",
            "bound_timeout_policy",
            "bound_stdout_stderr_capture",
            "bound_execution_receipt_sink",
            "execution_receipt_prewrite",
            "execution_receipt_final_write",
            "approval_consumption",
        ],
    }


def _lab_runner_enforcement_current_checks(
    *,
    binding_preflight: LabRunnerBindingPreflight,
    readiness: LabRunnerReadiness,
    preflight: LabExecutionPreflight,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    runner_binding = binding_preflight.runner_binding
    receipt_sink = binding_preflight.execution_receipt_sink
    workspace_matches = _safe_str(runner_binding.get("workspace_id")).strip() == workspace.id
    action_hash_matches = _safe_str(runner_binding.get("action_hash")).strip() == preflight.action_hash
    return {
        "runner_binding_record_present": True,
        "runner_binding_status_ready": binding_preflight.status == "ready",
        "runner_readiness_status_ready": readiness.status == "ready",
        "workspace_matches_binding": workspace_matches,
        "action_hash_matches_binding": action_hash_matches,
        "runner_bound": bool(runner_binding.get("runner_bound")),
        "runner_identity_verified": bool(runner_binding.get("runner_identity_verified")),
        "runner_binary_declared": bool(_safe_str(runner_binding.get("runner_binary_path")).strip()),
        "runner_contract_loaded": bool(runner_binding.get("runner_contract_loaded")),
        "command_allowlist_bound": bool(runner_binding.get("command_allowlist_bound")),
        "environment_scrubbing_bound": bool(runner_binding.get("environment_scrubbing_bound")),
        "network_policy_bound": bool(runner_binding.get("network_policy_bound")),
        "filesystem_policy_bound": bool(runner_binding.get("filesystem_policy_bound")),
        "resource_policy_bound": bool(runner_binding.get("resource_policy_bound")),
        "timeout_policy_bound": bool(runner_binding.get("timeout_policy_bound")),
        "stdout_stderr_capture_bound": bool(runner_binding.get("stdout_stderr_capture_bound")),
        "execution_receipt_sink_bound": bool(receipt_sink.get("bound")),
        "execution_receipt_schema_bound": bool(receipt_sink.get("schema_version")) and bool(receipt_sink.get("bound")),
        "execution_receipt_prewrite_bound": bool(receipt_sink.get("prewrite_bound")),
        "execution_receipt_final_write_bound": bool(receipt_sink.get("final_write_bound")),
        "receipt_sink_sensitive_redaction_declared": bool(receipt_sink.get("sensitive_values_redacted")),
        "approval_consumption_ready": bool(binding_preflight.current_controls.get("approval_consumption_ready")),
        "approval_consumed": bool(binding_preflight.approval_consumed),
        "execution_authority": False,
        "executed": False,
    }


def _lab_approval_consumption_handoff_required_checks() -> list[str]:
    return [
        "approval_id_provided",
        "approval_record_found",
        "approval_approved",
        "approval_exact_action_binding",
        "approval_not_stale_or_reused",
        "approval_not_consumed",
        "runner_enforcement_ready",
        "runner_binding_ready",
        "runner_readiness_ready",
        "runner_bound",
        "receipt_sink_bound",
        "execution_receipt_prewrite_bound",
        "execution_receipt_final_write_bound",
        "approval_consumption_not_disabled",
    ]


def _lab_approval_consumption_handoff_contract(
    *,
    enforcement: LabRunnerEnforcementPreflight,
    approval_id: str,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.approval_consumption_handoff",
        "schema_version": 1,
        "mode": "preflight_only_no_consumption",
        "approval_id": approval_id,
        "runner_enforcement_id": enforcement.id,
        "runner_binding_id": enforcement.runner_binding_id,
        "runner_readiness_id": enforcement.runner_readiness_id,
        "preflight_id": enforcement.preflight_id,
        "action": enforcement.action,
        "action_hash": enforcement.action_hash,
        "single_use_approval_required": True,
        "approval_consumption_enabled": False,
        "execution_enabled": False,
        "future_consumption_operation": "lab.execution.approval.consume",
        "requires": _lab_approval_consumption_handoff_required_checks(),
    }


def _lab_approval_consumption_handoff_current_checks(
    *,
    approval_id: str,
    approval_status: str,
    approval_binding: dict[str, Any],
    enforcement: LabRunnerEnforcementPreflight,
    binding_preflight: LabRunnerBindingPreflight,
    readiness: LabRunnerReadiness,
) -> dict[str, Any]:
    exact_approval = bool(approval_binding.get("approval_approved")) and bool(approval_binding.get("exact_match"))
    not_consumed = not bool(approval_binding.get("approval_consumed")) and not bool(enforcement.approval_consumed)
    return {
        "approval_id_provided": bool(approval_id),
        "approval_record_found": bool(approval_binding.get("approval_record_found")),
        "approval_approved": bool(approval_binding.get("approval_approved")),
        "approval_exact_action_binding": bool(approval_binding.get("exact_match")),
        "approval_not_stale_or_reused": exact_approval and not bool(approval_binding.get("refused")),
        "approval_not_consumed": not_consumed,
        "runner_enforcement_ready": enforcement.status == "ready",
        "runner_binding_ready": binding_preflight.status == "ready",
        "runner_readiness_ready": readiness.status == "ready",
        "runner_bound": bool(enforcement.runner_bound) or bool(enforcement.current_checks.get("runner_bound")),
        "receipt_sink_bound": bool(enforcement.receipt_sink_bound)
        or bool(enforcement.current_checks.get("execution_receipt_sink_bound")),
        "execution_receipt_prewrite_bound": bool(enforcement.current_checks.get("execution_receipt_prewrite_bound")),
        "execution_receipt_final_write_bound": bool(
            enforcement.current_checks.get("execution_receipt_final_write_bound")
        ),
        "approval_consumption_not_disabled": False,
        "approval_status": approval_status,
        "runner_enforcement_status": enforcement.status,
        "runner_binding_status": binding_preflight.status,
        "runner_readiness_status": readiness.status,
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_execution_receipt_sink_reservation_required_checks() -> list[str]:
    return [
        "approval_handoff_present",
        "approval_handoff_ready",
        "approval_approved",
        "approval_not_consumed",
        "approval_consumption_ready",
        "runner_enforcement_ready",
        "runner_binding_ready",
        "runner_readiness_ready",
        "receipt_sink_declared",
        "receipt_sink_bound",
        "receipt_sink_schema_bound",
        "receipt_sink_sensitive_redaction_declared",
        "execution_receipt_prewrite_bound",
        "execution_receipt_final_write_bound",
        "reserved_receipt_id_created",
        "reserved_receipt_path_scoped",
        "execution_receipt_not_written",
    ]


def _lab_execution_receipt_sink_reservation_contract(
    *,
    handoff: LabApprovalConsumptionHandoff,
    reserved_receipt: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.execution_receipt_sink_reservation",
        "schema_version": 1,
        "mode": "prewrite_reservation_only_no_execution",
        "approval_handoff_id": handoff.id,
        "runner_enforcement_id": handoff.runner_enforcement_id,
        "preflight_id": handoff.preflight_id,
        "action": handoff.action,
        "action_hash": handoff.action_hash,
        "reserved_execution_receipt_id": _safe_str(reserved_receipt.get("id")).strip(),
        "reserved_execution_receipt_path": _safe_str(reserved_receipt.get("path")).strip(),
        "writes_execution_receipt": False,
        "prewrite_enabled": False,
        "final_write_enabled": False,
        "execution_enabled": False,
        "requires": _lab_execution_receipt_sink_reservation_required_checks(),
    }


def _reserved_lab_execution_receipt(
    *,
    reservation_id: str,
    handoff: LabApprovalConsumptionHandoff,
    source: SourceRecord,
) -> dict[str, Any]:
    receipt_id = _reserved_lab_execution_receipt_id(reservation_id)
    path = ingest_artifact_root() / "lab_execution_receipts" / f"{receipt_id}.json"
    return {
        "id": receipt_id,
        "path": str(path),
        "operation": "lab.execution.run",
        "reservation_id": reservation_id,
        "source_id": source.id,
        "candidate_id": handoff.candidate_id,
        "candidate_name": handoff.candidate_name,
        "action_hash": handoff.action_hash,
        "reserved": True,
        "written": False,
        "prewrite_bound": False,
        "final_write_bound": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_execution_receipt_sink_reservation_current_checks(
    *,
    handoff: LabApprovalConsumptionHandoff,
    enforcement: LabRunnerEnforcementPreflight,
    binding_preflight: LabRunnerBindingPreflight,
    readiness: LabRunnerReadiness,
    reserved_receipt: dict[str, Any],
) -> dict[str, Any]:
    receipt_sink = enforcement.execution_receipt_sink
    reserved_path = _safe_str(reserved_receipt.get("path")).strip()
    sink_root = str(ingest_artifact_root() / "lab_execution_receipts")
    return {
        "approval_handoff_present": True,
        "approval_handoff_ready": handoff.status == "ready",
        "approval_approved": bool(handoff.current_checks.get("approval_approved")),
        "approval_not_consumed": not bool(handoff.approval_consumed),
        "approval_consumption_ready": bool(enforcement.current_checks.get("approval_consumption_ready")),
        "runner_enforcement_ready": enforcement.status == "ready",
        "runner_binding_ready": binding_preflight.status == "ready",
        "runner_readiness_ready": readiness.status == "ready",
        "receipt_sink_declared": _safe_str(receipt_sink.get("sink_kind")).strip() == "francis.lab.execution_receipts",
        "receipt_sink_bound": bool(enforcement.current_checks.get("execution_receipt_sink_bound")),
        "receipt_sink_schema_bound": bool(enforcement.current_checks.get("execution_receipt_schema_bound")),
        "receipt_sink_sensitive_redaction_declared": bool(
            enforcement.current_checks.get("receipt_sink_sensitive_redaction_declared")
        ),
        "execution_receipt_prewrite_bound": bool(enforcement.current_checks.get("execution_receipt_prewrite_bound")),
        "execution_receipt_final_write_bound": bool(
            enforcement.current_checks.get("execution_receipt_final_write_bound")
        ),
        "reserved_receipt_id_created": bool(_safe_str(reserved_receipt.get("id")).strip()),
        "reserved_receipt_path_scoped": bool(reserved_path) and reserved_path.startswith(sink_root),
        "execution_receipt_not_written": not bool(reserved_receipt.get("written")),
        "reserved_receipt_path": reserved_path,
        "receipt_sink_root": sink_root,
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_runner_command_allowlist_required_checks() -> list[str]:
    return [
        "receipt_sink_reservation_present",
        "receipt_sink_reservation_ready",
        "reserved_execution_receipt_id_created",
        "execution_receipt_not_written",
        "approval_not_consumed",
        "runner_enforcement_ready",
        "runner_binding_ready",
        "runner_readiness_ready",
        "command_plan_present",
        "commands_from_exact_action",
        "command_allowlist_declared",
        "command_allowlist_bound",
        "every_command_has_allowlist_entry",
        "no_command_execution_enabled",
        "receipt_sink_prewrite_bound",
        "receipt_sink_final_write_bound",
    ]


def _lab_runner_command_plan(
    *,
    preflight: LabExecutionPreflight,
) -> dict[str, Any]:
    raw_commands = [
        _safe_str(item).strip()
        for item in (preflight.exact_action.get("suggested_commands") or [])
        if _safe_str(item).strip()
    ]
    commands = [
        {
            "id": f"planned_command_{index}",
            "command": command,
            "source": "lab_execution_preflight.exact_action.suggested_commands",
            "requires_execution": True,
            "allowlist_entry_id": "",
            "allowlisted": False,
            "bound": False,
            "executed": False,
        }
        for index, command in enumerate(raw_commands, start=1)
    ]
    return {
        "plan_id": preflight.plan_id,
        "preflight_id": preflight.id,
        "candidate_id": preflight.candidate_id,
        "candidate_name": preflight.candidate_name,
        "commands": commands,
        "command_count": len(commands),
        "source": "exact_action",
        "allowlist_binding_mode": "preflight_contract_only",
        "shell_expansion_allowed": False,
        "execution_enabled": False,
        "executed": False,
    }


def _lab_runner_command_allowlist_contract(
    *,
    reservation: LabExecutionReceiptSinkReservation,
    command_plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.runner.command_allowlist_binding",
        "schema_version": 1,
        "mode": "allowlist_binding_preflight_only_no_execution",
        "receipt_sink_reservation_id": reservation.id,
        "approval_handoff_id": reservation.approval_handoff_id,
        "runner_enforcement_id": reservation.runner_enforcement_id,
        "preflight_id": reservation.preflight_id,
        "action": reservation.action,
        "action_hash": reservation.action_hash,
        "command_count": int(command_plan.get("command_count") or 0),
        "allowlist_declared": False,
        "allowlist_bound": False,
        "command_execution_enabled": False,
        "execution_enabled": False,
        "requires": _lab_runner_command_allowlist_required_checks(),
    }


def _lab_runner_command_allowlist_current_checks(
    *,
    reservation: LabExecutionReceiptSinkReservation,
    enforcement: LabRunnerEnforcementPreflight,
    binding_preflight: LabRunnerBindingPreflight,
    readiness: LabRunnerReadiness,
    command_plan: dict[str, Any],
) -> dict[str, Any]:
    raw_commands = command_plan.get("commands")
    commands = raw_commands if isinstance(raw_commands, list) else []
    command_count = len(commands)
    return {
        "receipt_sink_reservation_present": True,
        "receipt_sink_reservation_ready": reservation.status == "ready",
        "reserved_execution_receipt_id_created": bool(
            _safe_str(reservation.reserved_execution_receipt.get("id")).strip()
        ),
        "execution_receipt_not_written": not bool(reservation.execution_receipt_written),
        "approval_not_consumed": not bool(reservation.approval_consumed),
        "runner_enforcement_ready": enforcement.status == "ready",
        "runner_binding_ready": binding_preflight.status == "ready",
        "runner_readiness_ready": readiness.status == "ready",
        "command_plan_present": command_count > 0,
        "commands_from_exact_action": command_count > 0
        and _safe_str(command_plan.get("source")).strip() == "exact_action",
        "command_allowlist_declared": False,
        "command_allowlist_bound": False,
        "every_command_has_allowlist_entry": False,
        "no_command_execution_enabled": not bool(command_plan.get("execution_enabled")),
        "receipt_sink_prewrite_bound": bool(reservation.prewrite_bound),
        "receipt_sink_final_write_bound": bool(reservation.final_write_bound),
        "command_count": command_count,
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_runner_command_allowlist_declaration_required_checks() -> list[str]:
    return [
        "command_allowlist_binding_present",
        "runner_command_allowlist_binding_ready",
        "command_plan_present",
        "commands_from_exact_action",
        "declaration_created",
        "command_allowlist_declared",
        "every_command_has_declaration",
        "every_declaration_source_is_exact_action",
        "command_allowlist_bound",
        "command_execution_disabled",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
        "receipt_sink_prewrite_bound",
        "receipt_sink_final_write_bound",
    ]


def _lab_runner_command_allowlist_declaration_entries(
    *,
    declaration_id: str,
    command_plan: dict[str, Any],
) -> dict[str, Any]:
    raw_commands = command_plan.get("commands")
    commands = raw_commands if isinstance(raw_commands, list) else []
    entries: list[dict[str, Any]] = []
    for index, raw_command in enumerate(commands, start=1):
        command_record = _as_dict(raw_command)
        command = _safe_str(command_record.get("command")).strip()
        if not command:
            continue
        command_id = _safe_str(command_record.get("id")).strip() or f"planned_command_{index}"
        command_hash = hashlib.sha256(command.encode("utf-8", errors="replace")).hexdigest()
        entry_digest = hashlib.sha256(f"{declaration_id}:{command_id}:{command_hash}".encode("utf-8")).hexdigest()[:16]
        entries.append(
            {
                "id": f"allowlist_entry_{entry_digest}",
                "command_id": command_id,
                "command": command,
                "command_hash": f"sha256:{command_hash}",
                "source": "exact_action_command_plan",
                "requires_execution": True,
                "declared": True,
                "bound": False,
                "executed": False,
                "shell_expansion_allowed": False,
                "network_allowed": False,
                "write_allowed": False,
                "destructive_allowed": False,
            }
        )
    return {
        "schema_version": 1,
        "mode": "allowlist_declaration_preflight_only_no_binding",
        "source": "exact_action",
        "entries": entries,
        "entry_count": len(entries),
        "allowlist_declared": bool(entries),
        "allowlist_bound": False,
        "command_execution_enabled": False,
        "executed": False,
    }


def _lab_runner_command_allowlist_declaration_contract(
    *,
    command_allowlist: LabRunnerCommandAllowlistBinding,
    allowlist_declaration: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.runner.command_allowlist_declaration",
        "schema_version": 1,
        "mode": "allowlist_declaration_preflight_only_no_binding",
        "command_allowlist_binding_id": command_allowlist.id,
        "receipt_sink_reservation_id": command_allowlist.receipt_sink_reservation_id,
        "preflight_id": command_allowlist.preflight_id,
        "action": command_allowlist.action,
        "action_hash": command_allowlist.action_hash,
        "entry_count": int(allowlist_declaration.get("entry_count") or 0),
        "allowlist_declared": bool(allowlist_declaration.get("allowlist_declared")),
        "allowlist_bound": False,
        "command_execution_enabled": False,
        "requires": _lab_runner_command_allowlist_declaration_required_checks(),
    }


def _lab_runner_command_allowlist_declaration_current_checks(
    *,
    command_allowlist: LabRunnerCommandAllowlistBinding,
    allowlist_declaration: dict[str, Any],
) -> dict[str, Any]:
    raw_entries = allowlist_declaration.get("entries")
    entries = raw_entries if isinstance(raw_entries, list) else []
    raw_commands = command_allowlist.command_plan.get("commands")
    commands = raw_commands if isinstance(raw_commands, list) else []
    entry_count = len(entries)
    command_count = len(commands)
    command_plan_source = _safe_str(command_allowlist.command_plan.get("source")).strip()
    return {
        "command_allowlist_binding_present": True,
        "runner_command_allowlist_binding_ready": command_allowlist.status == "ready",
        "command_plan_present": command_count > 0,
        "commands_from_exact_action": command_count > 0 and command_plan_source == "exact_action",
        "declaration_created": bool(allowlist_declaration),
        "command_allowlist_declared": bool(allowlist_declaration.get("allowlist_declared")),
        "every_command_has_declaration": command_count > 0 and entry_count == command_count,
        "every_declaration_source_is_exact_action": entry_count > 0
        and all(_safe_str(_as_dict(entry).get("source")).strip() == "exact_action_command_plan" for entry in entries),
        "command_allowlist_bound": False,
        "command_execution_disabled": not bool(allowlist_declaration.get("command_execution_enabled")),
        "approval_not_consumed": not bool(command_allowlist.approval_consumed),
        "execution_authority_absent": not bool(command_allowlist.execution_authority),
        "commands_not_executed": all(not bool(_as_dict(entry).get("executed")) for entry in entries)
        and all(not bool(_as_dict(command).get("executed")) for command in commands),
        "receipt_sink_prewrite_bound": bool(command_allowlist.current_checks.get("receipt_sink_prewrite_bound")),
        "receipt_sink_final_write_bound": bool(command_allowlist.current_checks.get("receipt_sink_final_write_bound")),
        "command_count": command_count,
        "entry_count": entry_count,
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_runner_command_allowlist_enforcement_required_checks() -> list[str]:
    return [
        "command_allowlist_declaration_present",
        "runner_command_allowlist_declaration_ready",
        "allowlist_entries_declared",
        "every_entry_has_command_hash",
        "every_entry_from_exact_action",
        "runner_enforcement_ready",
        "runner_bound",
        "runner_identity_verified",
        "command_allowlist_bound",
        "command_allowlist_enforced",
        "command_execution_disabled",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
        "receipt_sink_prewrite_bound",
        "receipt_sink_final_write_bound",
    ]


def _lab_runner_command_allowlist_enforcement_projection(
    *,
    declaration: LabRunnerCommandAllowlistDeclaration,
    runner_enforcement: LabRunnerEnforcementPreflight,
) -> dict[str, Any]:
    raw_entries = declaration.allowlist_declaration.get("entries")
    entries = raw_entries if isinstance(raw_entries, list) else []
    projected_entries: list[dict[str, Any]] = []
    for raw_entry in entries:
        entry = _as_dict(raw_entry)
        projected_entries.append(
            {
                "entry_id": _safe_str(entry.get("id")).strip(),
                "command_id": _safe_str(entry.get("command_id")).strip(),
                "command_hash": _safe_str(entry.get("command_hash")).strip(),
                "source": _safe_str(entry.get("source")).strip(),
                "declared": bool(entry.get("declared")),
                "bound": False,
                "enforced": False,
                "executed": False,
                "enforcement_blockers": [
                    "live_runner_not_bound",
                    "runner_identity_not_verified",
                    "command_allowlist_not_bound",
                    "execution_receipt_prewrite_not_bound",
                    "execution_receipt_final_write_not_bound",
                ],
            }
        )
    return {
        "schema_version": 1,
        "mode": "allowlist_enforcement_preflight_only_no_execution",
        "runner_enforcement_id": runner_enforcement.id,
        "command_allowlist_declaration_id": declaration.id,
        "entry_count": len(projected_entries),
        "entries": projected_entries,
        "allowlist_declared": declaration.allowlist_declared,
        "allowlist_bound": False,
        "allowlist_enforced": False,
        "command_execution_enabled": False,
        "executed": False,
    }


def _lab_runner_command_allowlist_enforcement_contract(
    *,
    declaration: LabRunnerCommandAllowlistDeclaration,
    enforcement_projection: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.runner.command_allowlist_enforcement_preflight",
        "schema_version": 1,
        "mode": "allowlist_enforcement_preflight_only_no_execution",
        "command_allowlist_declaration_id": declaration.id,
        "command_allowlist_binding_id": declaration.command_allowlist_binding_id,
        "runner_enforcement_id": declaration.runner_enforcement_id,
        "preflight_id": declaration.preflight_id,
        "action": declaration.action,
        "action_hash": declaration.action_hash,
        "entry_count": int(enforcement_projection.get("entry_count") or 0),
        "allowlist_bound": False,
        "allowlist_enforced": False,
        "command_execution_enabled": False,
        "requires": _lab_runner_command_allowlist_enforcement_required_checks(),
    }


def _lab_runner_command_allowlist_enforcement_current_checks(
    *,
    declaration: LabRunnerCommandAllowlistDeclaration,
    runner_enforcement: LabRunnerEnforcementPreflight,
    enforcement_projection: dict[str, Any],
) -> dict[str, Any]:
    raw_entries = enforcement_projection.get("entries")
    entries = raw_entries if isinstance(raw_entries, list) else []
    entry_count = len(entries)
    return {
        "command_allowlist_declaration_present": True,
        "runner_command_allowlist_declaration_ready": declaration.status == "ready",
        "allowlist_entries_declared": declaration.allowlist_declared and entry_count > 0,
        "every_entry_has_command_hash": entry_count > 0
        and all(_safe_str(_as_dict(entry).get("command_hash")).strip().startswith("sha256:") for entry in entries),
        "every_entry_from_exact_action": entry_count > 0
        and all(_safe_str(_as_dict(entry).get("source")).strip() == "exact_action_command_plan" for entry in entries),
        "runner_enforcement_ready": runner_enforcement.status == "ready",
        "runner_bound": bool(runner_enforcement.current_checks.get("runner_bound")),
        "runner_identity_verified": bool(runner_enforcement.current_checks.get("runner_identity_verified")),
        "command_allowlist_bound": False,
        "command_allowlist_enforced": False,
        "command_execution_disabled": not bool(enforcement_projection.get("command_execution_enabled")),
        "approval_not_consumed": not bool(declaration.approval_consumed),
        "execution_authority_absent": not bool(declaration.execution_authority),
        "commands_not_executed": all(not bool(_as_dict(entry).get("executed")) for entry in entries),
        "receipt_sink_prewrite_bound": bool(declaration.current_checks.get("receipt_sink_prewrite_bound")),
        "receipt_sink_final_write_bound": bool(declaration.current_checks.get("receipt_sink_final_write_bound")),
        "entry_count": entry_count,
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_runner_sandbox_required_checks() -> list[str]:
    return [
        "command_allowlist_enforcement_present",
        "runner_command_allowlist_enforcement_ready",
        "workspace_manifest_present",
        "workspace_subdirs_present",
        "workspace_owned_by_francis",
        "source_reference_read_only",
        "source_not_copied",
        "source_write_blocked",
        "runner_bound",
        "runner_identity_verified",
        "sandbox_provider_bound",
        "sandbox_workspace_isolated",
        "source_mounted_readonly",
        "working_directory_is_lab_owned",
        "environment_scrubbed",
        "network_blocked_or_policy_bound",
        "filesystem_write_policy_bound",
        "resource_limits_bound",
        "timeout_policy_bound",
        "stdout_stderr_capture_bound",
        "kill_switch_bound",
        "command_allowlist_enforced",
        "receipt_sink_prewrite_bound",
        "receipt_sink_final_write_bound",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
    ]


def _lab_runner_sandbox_profile(
    *,
    workspace: LabWorkspaceRecord,
    allowlist_enforcement: LabRunnerCommandAllowlistEnforcementPreflight,
) -> dict[str, Any]:
    workspace_path = _safe_str(workspace.path).strip()
    workspace_root = Path(workspace_path) if workspace_path else None
    manifest_path = _safe_str(workspace.manifest_path).strip()
    manifest = Path(manifest_path) if manifest_path else None
    workspace_subdirs_present = False
    if workspace_root is not None:
        workspace_subdirs_present = all(
            (workspace_root / child).is_dir() for child in ("work", "artifacts", "logs", "tmp")
        )
    source_reference_read_only = _safe_str(workspace.source_reference.get("mode")).strip() == "reference_only_read_only"
    return {
        "schema_version": 1,
        "mode": "sandbox_readiness_preflight_only_no_execution",
        "workspace_id": workspace.id,
        "workspace_path": workspace_path,
        "manifest_path": manifest_path,
        "manifest_present": bool(manifest and manifest.exists()),
        "workspace_subdirs_present": workspace_subdirs_present,
        "workspace_owned_by_francis": workspace_path.startswith(str(ingest_artifact_root() / "lab_workspaces")),
        "source_reference_read_only": source_reference_read_only,
        "source_not_copied": not workspace.source_copied,
        "source_write_blocked": not bool(workspace.workspace_policy.get("source_write_allowed")),
        "source_mount_mode": "reference_only_no_mount",
        "allowed_write_subdirs": [
            _safe_str(item).strip() for item in (workspace.workspace_policy.get("allowed_write_subdirs") or [])
        ],
        "command_allowlist_enforcement_id": allowlist_enforcement.id,
        "allowlist_enforced": allowlist_enforcement.allowlist_enforced,
        "command_execution_enabled": allowlist_enforcement.command_execution_enabled,
        "executed": False,
    }


def _lab_runner_sandbox_contract(
    *,
    allowlist_enforcement: LabRunnerCommandAllowlistEnforcementPreflight,
    sandbox_profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.runner.sandbox_readiness",
        "schema_version": 1,
        "mode": "sandbox_readiness_preflight_only_no_execution",
        "command_allowlist_enforcement_id": allowlist_enforcement.id,
        "runner_enforcement_id": allowlist_enforcement.runner_enforcement_id,
        "preflight_id": allowlist_enforcement.preflight_id,
        "workspace_id": allowlist_enforcement.workspace_id,
        "action": allowlist_enforcement.action,
        "action_hash": allowlist_enforcement.action_hash,
        "workspace_path": _safe_str(sandbox_profile.get("workspace_path")).strip(),
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "runner_bound": False,
        "command_execution_enabled": False,
        "requires": _lab_runner_sandbox_required_checks(),
    }


def _lab_runner_sandbox_current_checks(
    *,
    workspace: LabWorkspaceRecord,
    allowlist_enforcement: LabRunnerCommandAllowlistEnforcementPreflight,
    sandbox_profile: dict[str, Any],
) -> dict[str, Any]:
    workspace_path = _safe_str(sandbox_profile.get("workspace_path")).strip()
    return {
        "command_allowlist_enforcement_present": True,
        "runner_command_allowlist_enforcement_ready": allowlist_enforcement.status == "ready",
        "workspace_manifest_present": bool(sandbox_profile.get("manifest_present")),
        "workspace_subdirs_present": bool(sandbox_profile.get("workspace_subdirs_present")),
        "workspace_owned_by_francis": bool(sandbox_profile.get("workspace_owned_by_francis")),
        "source_reference_read_only": bool(sandbox_profile.get("source_reference_read_only")),
        "source_not_copied": bool(sandbox_profile.get("source_not_copied")),
        "source_write_blocked": bool(sandbox_profile.get("source_write_blocked")),
        "runner_bound": bool(allowlist_enforcement.current_checks.get("runner_bound")),
        "runner_identity_verified": bool(allowlist_enforcement.current_checks.get("runner_identity_verified")),
        "sandbox_provider_bound": False,
        "sandbox_workspace_isolated": False,
        "source_mounted_readonly": False,
        "working_directory_is_lab_owned": bool(workspace_path) and not workspace.source_copied,
        "environment_scrubbed": False,
        "network_blocked_or_policy_bound": bool(workspace.workspace_policy.get("network_enabled")) is False,
        "filesystem_write_policy_bound": False,
        "resource_limits_bound": False,
        "timeout_policy_bound": False,
        "stdout_stderr_capture_bound": False,
        "kill_switch_bound": False,
        "command_allowlist_enforced": bool(allowlist_enforcement.allowlist_enforced),
        "receipt_sink_prewrite_bound": bool(allowlist_enforcement.current_checks.get("receipt_sink_prewrite_bound")),
        "receipt_sink_final_write_bound": bool(
            allowlist_enforcement.current_checks.get("receipt_sink_final_write_bound")
        ),
        "approval_not_consumed": not bool(allowlist_enforcement.approval_consumed),
        "execution_authority_absent": not bool(allowlist_enforcement.execution_authority),
        "commands_not_executed": not bool(allowlist_enforcement.executed),
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_sandbox_provider_contract_required_checks() -> list[str]:
    return [
        "runner_sandbox_readiness_present",
        "runner_sandbox_readiness_ready",
        "provider_contract_declared",
        "sandbox_provider_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "workspace_isolation_bound",
        "filesystem_write_policy_bound",
        "network_blocked_or_policy_bound",
        "resource_limits_bound",
        "timeout_policy_bound",
        "stdout_stderr_capture_bound",
        "kill_switch_bound",
        "command_allowlist_enforced",
        "receipt_prewrite_bound",
        "receipt_final_write_bound",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_contract_payload(
    *,
    sandbox_readiness: LabRunnerSandboxReadiness,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_contract",
        "schema_version": 1,
        "mode": "provider_contract_preflight_only_no_execution",
        "provider_kind": "unbound",
        "sandbox_readiness_id": sandbox_readiness.id,
        "command_allowlist_enforcement_id": sandbox_readiness.command_allowlist_enforcement_id,
        "preflight_id": sandbox_readiness.preflight_id,
        "workspace_id": sandbox_readiness.workspace_id,
        "source_id": sandbox_readiness.source_id,
        "candidate_id": sandbox_readiness.candidate_id,
        "candidate_name": sandbox_readiness.candidate_name,
        "action": sandbox_readiness.action,
        "action_hash": sandbox_readiness.action_hash,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "provider_contract_declared": True,
        "live_provider_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "execution_authority": False,
        "executed": False,
        "repo_code_executed": False,
        "requires": _lab_sandbox_provider_contract_required_checks(),
    }


def _lab_sandbox_provider_contract_current_checks(
    *,
    sandbox_readiness: LabRunnerSandboxReadiness,
    provider_contract: dict[str, Any],
) -> dict[str, Any]:
    sandbox_checks = _as_dict(sandbox_readiness.current_checks)
    return {
        "runner_sandbox_readiness_present": bool(sandbox_readiness.id),
        "runner_sandbox_readiness_ready": sandbox_readiness.status == "ready",
        "provider_contract_declared": bool(provider_contract.get("provider_contract_declared")),
        "sandbox_provider_bound": bool(sandbox_checks.get("sandbox_provider_bound")),
        "sandbox_bound": bool(sandbox_readiness.sandbox_bound),
        "sandbox_enforced": bool(sandbox_readiness.sandbox_enforced),
        "workspace_isolation_bound": bool(sandbox_checks.get("sandbox_workspace_isolated")),
        "filesystem_write_policy_bound": bool(sandbox_checks.get("filesystem_write_policy_bound")),
        "network_blocked_or_policy_bound": bool(sandbox_checks.get("network_blocked_or_policy_bound")),
        "resource_limits_bound": bool(sandbox_checks.get("resource_limits_bound")),
        "timeout_policy_bound": bool(sandbox_checks.get("timeout_policy_bound")),
        "stdout_stderr_capture_bound": bool(sandbox_checks.get("stdout_stderr_capture_bound")),
        "kill_switch_bound": bool(sandbox_checks.get("kill_switch_bound")),
        "command_allowlist_enforced": bool(sandbox_readiness.allowlist_enforced),
        "receipt_prewrite_bound": bool(sandbox_readiness.receipt_prewrite_bound),
        "receipt_final_write_bound": bool(sandbox_readiness.receipt_final_write_bound),
        "approval_not_consumed": not bool(sandbox_readiness.approval_consumed),
        "execution_authority_absent": not bool(sandbox_readiness.execution_authority),
        "commands_not_executed": not bool(sandbox_readiness.executed),
        "repo_code_not_executed": True,
        "network_not_accessed": not bool(sandbox_readiness.network_accessed),
        "repo_write_not_performed": not bool(sandbox_readiness.wrote_to_repo),
        "approval_consumed": bool(sandbox_readiness.approval_consumed),
        "execution_authority": bool(sandbox_readiness.execution_authority),
        "commands_executed": bool(sandbox_readiness.executed),
        "repo_code_executed": False,
        "network_accessed": bool(sandbox_readiness.network_accessed),
        "wrote_to_repo": bool(sandbox_readiness.wrote_to_repo),
    }


def _lab_sandbox_provider_binding_required_checks() -> list[str]:
    return [
        "provider_contract_present",
        "provider_contract_ready",
        "provider_contract_declared",
        "provider_binding_contract_declared",
        "provider_kind_selected",
        "provider_binary_or_service_verified",
        "provider_policy_manifest_bound",
        "sandbox_provider_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "workspace_isolation_bound",
        "filesystem_write_policy_bound",
        "network_blocked_or_policy_bound",
        "resource_limits_bound",
        "timeout_policy_bound",
        "stdout_stderr_capture_bound",
        "kill_switch_bound",
        "command_allowlist_enforced",
        "receipt_prewrite_bound",
        "receipt_final_write_bound",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_binding_contract_payload(
    *,
    provider_contract: LabSandboxProviderContract,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_binding_preflight",
        "schema_version": 1,
        "mode": "binding_preflight_only_no_execution",
        "provider_kind": "unbound",
        "sandbox_provider_contract_id": provider_contract.id,
        "sandbox_readiness_id": provider_contract.sandbox_readiness_id,
        "preflight_id": provider_contract.preflight_id,
        "workspace_id": provider_contract.workspace_id,
        "source_id": provider_contract.source_id,
        "candidate_id": provider_contract.candidate_id,
        "candidate_name": provider_contract.candidate_name,
        "action": provider_contract.action,
        "action_hash": provider_contract.action_hash,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "provider_binding_contract_declared": True,
        "provider_kind_selected": False,
        "provider_binary_or_service_verified": False,
        "provider_policy_manifest_bound": False,
        "sandbox_provider_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "execution_authority": False,
        "executed": False,
        "repo_code_executed": False,
        "requires": _lab_sandbox_provider_binding_required_checks(),
    }


def _lab_sandbox_provider_binding_current_checks(
    *,
    provider_contract: LabSandboxProviderContract,
    binding_contract: dict[str, Any],
) -> dict[str, Any]:
    provider_checks = _as_dict(provider_contract.current_checks)
    return {
        "provider_contract_present": bool(provider_contract.id),
        "provider_contract_ready": provider_contract.status == "ready",
        "provider_contract_declared": bool(provider_contract.provider_contract_declared),
        "provider_binding_contract_declared": bool(binding_contract.get("provider_binding_contract_declared")),
        "provider_kind_selected": False,
        "provider_binary_or_service_verified": False,
        "provider_policy_manifest_bound": False,
        "sandbox_provider_bound": bool(provider_checks.get("sandbox_provider_bound")),
        "sandbox_bound": bool(provider_contract.sandbox_bound),
        "sandbox_enforced": bool(provider_contract.sandbox_enforced),
        "workspace_isolation_bound": bool(provider_contract.workspace_isolation_bound),
        "filesystem_write_policy_bound": bool(provider_contract.filesystem_write_policy_bound),
        "network_blocked_or_policy_bound": bool(provider_checks.get("network_blocked_or_policy_bound")),
        "resource_limits_bound": bool(provider_contract.resource_limits_bound),
        "timeout_policy_bound": bool(provider_contract.timeout_policy_bound),
        "stdout_stderr_capture_bound": bool(provider_contract.stdout_stderr_capture_bound),
        "kill_switch_bound": bool(provider_contract.kill_switch_bound),
        "command_allowlist_enforced": bool(provider_contract.command_allowlist_enforced),
        "receipt_prewrite_bound": bool(provider_contract.receipt_prewrite_bound),
        "receipt_final_write_bound": bool(provider_contract.receipt_final_write_bound),
        "approval_not_consumed": not bool(provider_contract.approval_consumed),
        "execution_authority_absent": not bool(provider_contract.execution_authority),
        "commands_not_executed": not bool(provider_contract.executed),
        "repo_code_not_executed": not bool(provider_contract.repo_code_executed),
        "network_not_accessed": not bool(provider_contract.network_accessed),
        "repo_write_not_performed": not bool(provider_contract.wrote_to_repo),
        "approval_consumed": bool(provider_contract.approval_consumed),
        "execution_authority": bool(provider_contract.execution_authority),
        "commands_executed": bool(provider_contract.executed),
        "repo_code_executed": bool(provider_contract.repo_code_executed),
        "network_accessed": bool(provider_contract.network_accessed),
        "wrote_to_repo": bool(provider_contract.wrote_to_repo),
    }


def _lab_sandbox_provider_selection_required_checks() -> list[str]:
    return [
        "provider_binding_present",
        "provider_binding_ready",
        "provider_selection_policy_declared",
        "provider_kind_allowed_by_policy",
        "provider_kind_selected",
        "provider_reference_checked",
        "provider_reference_verified",
        "provider_binary_or_service_verified",
        "provider_policy_manifest_bound",
        "sandbox_provider_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "workspace_isolation_bound",
        "filesystem_write_policy_bound",
        "network_blocked_or_policy_bound",
        "resource_limits_bound",
        "timeout_policy_bound",
        "stdout_stderr_capture_bound",
        "kill_switch_bound",
        "command_allowlist_enforced",
        "receipt_prewrite_bound",
        "receipt_final_write_bound",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_kind_tokens() -> list[str]:
    return [
        "container_runtime",
        "local_process_sandbox",
        "microvm_sandbox",
        "windows_job_object",
        "wsl_sandbox",
    ]


def _normalize_lab_sandbox_provider_kind(value: str) -> str:
    clean = _safe_str(value).strip().lower().replace("-", "_").replace(" ", "_")
    clean = "".join(ch for ch in clean if ch.isalnum() or ch in {"_", "."})
    return clean or "unselected"


def _lab_provider_reference_metadata(provider_reference: str) -> dict[str, Any]:
    clean = _safe_str(provider_reference).strip()
    if not clean:
        return {
            "reference": "",
            "reference_kind": "none",
            "reference_present": False,
            "metadata_checked": False,
            "reference_verified": False,
            "contents_read": False,
            "executed": False,
        }
    path_like = any(token in clean for token in ("\\", "/", ":")) or Path(clean).exists()
    if not path_like:
        return {
            "reference": clean,
            "reference_kind": "service_or_name",
            "reference_present": True,
            "metadata_checked": True,
            "reference_verified": False,
            "contents_read": False,
            "executed": False,
            "warning": "service_or_name_reference_not_locally_verified_in_v0",
        }
    try:
        path = Path(clean).expanduser()
        resolved = path.resolve(strict=False)
        exists = path.exists()
        is_file = path.is_file() if exists else False
        is_dir = path.is_dir() if exists else False
        size_bytes = path.stat().st_size if exists and is_file else None
        error = ""
    except OSError as exc:
        resolved = Path(clean)
        exists = False
        is_file = False
        is_dir = False
        size_bytes = None
        error = str(exc)
    metadata: dict[str, Any] = {
        "reference": str(resolved),
        "reference_kind": "path",
        "reference_present": exists,
        "metadata_checked": True,
        "exists": exists,
        "is_file": is_file,
        "is_dir": is_dir,
        "size_bytes": size_bytes,
        "reference_verified": bool(exists and (is_file or is_dir)),
        "contents_read": False,
        "executed": False,
    }
    if error:
        metadata["error"] = error
    return metadata


def _lab_provider_policy_manifest_metadata(provider_policy_manifest: str) -> dict[str, Any]:
    clean = _safe_str(provider_policy_manifest).strip()
    if not clean:
        return {
            "path": "",
            "present": False,
            "metadata_checked": False,
            "bound": False,
            "contents_read": False,
        }
    try:
        path = Path(clean).expanduser()
        resolved = path.resolve(strict=False)
        exists = path.exists()
        is_file = path.is_file() if exists else False
        size_bytes = path.stat().st_size if exists and is_file else None
        error = ""
    except OSError as exc:
        resolved = Path(clean)
        exists = False
        is_file = False
        size_bytes = None
        error = str(exc)
    metadata: dict[str, Any] = {
        "path": str(resolved),
        "present": exists,
        "metadata_checked": True,
        "is_file": is_file,
        "size_bytes": size_bytes,
        "bound": bool(exists and is_file),
        "contents_read": False,
    }
    if error:
        metadata["error"] = error
    return metadata


def _lab_sandbox_provider_selection_policy_payload(
    *,
    provider_binding: LabSandboxProviderBindingPreflight,
    requested_provider_kind: str,
    provider_reference: str,
    provider_policy_manifest: str,
) -> dict[str, Any]:
    selected_provider_kind = _normalize_lab_sandbox_provider_kind(requested_provider_kind)
    allowed_provider_kinds = _lab_sandbox_provider_kind_tokens()
    return {
        "policy_kind": "francis.lab.sandbox_provider_selection_policy",
        "schema_version": 1,
        "mode": "selection_policy_preflight_only_no_execution",
        "sandbox_provider_binding_id": provider_binding.id,
        "sandbox_provider_contract_id": provider_binding.sandbox_provider_contract_id,
        "source_id": provider_binding.source_id,
        "candidate_id": provider_binding.candidate_id,
        "candidate_name": provider_binding.candidate_name,
        "action": provider_binding.action,
        "action_hash": provider_binding.action_hash,
        "allowed_provider_kinds": allowed_provider_kinds,
        "requested_provider_kind": selected_provider_kind,
        "selected_provider_kind": selected_provider_kind
        if selected_provider_kind in allowed_provider_kinds
        else "unselected",
        "provider_selection_policy_declared": True,
        "provider_reference": _safe_str(provider_reference).strip(),
        "provider_policy_manifest_path": _safe_str(provider_policy_manifest).strip(),
        "requires_explicit_provider_kind": True,
        "requires_local_provider_reference": True,
        "requires_provider_policy_manifest": True,
        "requires_future_provider_binary_or_service_verifier": True,
        "sandbox_provider_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "execution_authority": False,
        "executed": False,
        "repo_code_executed": False,
        "requires": _lab_sandbox_provider_selection_required_checks(),
    }


def _lab_sandbox_provider_selection_current_checks(
    *,
    provider_binding: LabSandboxProviderBindingPreflight,
    provider_selection_policy: dict[str, Any],
    provider_verification: dict[str, Any],
) -> dict[str, Any]:
    binding_checks = _as_dict(provider_binding.current_checks)
    requested_kind = _safe_str(provider_selection_policy.get("requested_provider_kind")).strip()
    selected_kind = _safe_str(provider_selection_policy.get("selected_provider_kind")).strip()
    policy_manifest = _as_dict(provider_verification.get("provider_policy_manifest"))
    provider_reference = _as_dict(provider_verification.get("provider_reference"))
    return {
        "provider_binding_present": bool(provider_binding.id),
        "provider_binding_ready": provider_binding.status == "ready",
        "provider_selection_policy_declared": bool(provider_selection_policy.get("provider_selection_policy_declared")),
        "provider_kind_allowed_by_policy": bool(selected_kind and selected_kind == requested_kind),
        "provider_kind_selected": bool(selected_kind and selected_kind != "unselected"),
        "provider_reference_checked": bool(provider_reference.get("metadata_checked")),
        "provider_reference_present": bool(provider_reference.get("reference_present")),
        "provider_reference_verified": bool(provider_reference.get("reference_verified")),
        "provider_binary_or_service_verified": False,
        "provider_policy_manifest_present": bool(policy_manifest.get("present")),
        "provider_policy_manifest_bound": bool(policy_manifest.get("bound")),
        "sandbox_provider_bound": bool(binding_checks.get("sandbox_provider_bound")),
        "sandbox_bound": bool(provider_binding.sandbox_bound),
        "sandbox_enforced": bool(provider_binding.sandbox_enforced),
        "workspace_isolation_bound": bool(provider_binding.workspace_isolation_bound),
        "filesystem_write_policy_bound": bool(provider_binding.filesystem_write_policy_bound),
        "network_blocked_or_policy_bound": bool(binding_checks.get("network_blocked_or_policy_bound")),
        "resource_limits_bound": bool(provider_binding.resource_limits_bound),
        "timeout_policy_bound": bool(provider_binding.timeout_policy_bound),
        "stdout_stderr_capture_bound": bool(provider_binding.stdout_stderr_capture_bound),
        "kill_switch_bound": bool(provider_binding.kill_switch_bound),
        "command_allowlist_enforced": bool(provider_binding.command_allowlist_enforced),
        "receipt_prewrite_bound": bool(provider_binding.receipt_prewrite_bound),
        "receipt_final_write_bound": bool(provider_binding.receipt_final_write_bound),
        "approval_not_consumed": not bool(provider_binding.approval_consumed),
        "execution_authority_absent": not bool(provider_binding.execution_authority),
        "commands_not_executed": not bool(provider_binding.executed),
        "repo_code_not_executed": not bool(provider_binding.repo_code_executed),
        "network_not_accessed": not bool(provider_binding.network_accessed),
        "repo_write_not_performed": not bool(provider_binding.wrote_to_repo),
        "approval_consumed": bool(provider_binding.approval_consumed),
        "execution_authority": bool(provider_binding.execution_authority),
        "commands_executed": bool(provider_binding.executed),
        "repo_code_executed": bool(provider_binding.repo_code_executed),
        "network_accessed": bool(provider_binding.network_accessed),
        "wrote_to_repo": bool(provider_binding.wrote_to_repo),
    }


def _lab_sandbox_provider_verifier_required_checks() -> list[str]:
    return [
        "provider_selection_present",
        "provider_selection_ready",
        "provider_kind_selected",
        "provider_reference_verified",
        "provider_policy_manifest_bound",
        "verifier_contract_declared",
        "verifier_implementation_bound",
        "verifier_identity_bound",
        "verifier_policy_bound",
        "verifier_receipt_contract_bound",
        "static_identity_verification_performed",
        "provider_reference_fingerprint_captured",
        "provider_policy_manifest_hash_captured",
        "provider_binary_or_service_verified",
        "provider_runtime_probe_performed",
        "provider_version_captured",
        "provider_identity_fingerprint_captured",
        "sandbox_provider_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "workspace_isolation_bound",
        "filesystem_write_policy_bound",
        "network_blocked_or_policy_bound",
        "resource_limits_bound",
        "timeout_policy_bound",
        "stdout_stderr_capture_bound",
        "kill_switch_bound",
        "command_allowlist_enforced",
        "receipt_prewrite_bound",
        "receipt_final_write_bound",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_verifier_contract_payload(
    *,
    provider_selection: LabSandboxProviderSelectionPreflight,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_verifier_contract",
        "schema_version": 1,
        "mode": "static_identity_policy_verification_no_execution",
        "sandbox_provider_selection_id": provider_selection.id,
        "sandbox_provider_binding_id": provider_selection.sandbox_provider_binding_id,
        "sandbox_provider_contract_id": provider_selection.sandbox_provider_contract_id,
        "sandbox_readiness_id": provider_selection.sandbox_readiness_id,
        "preflight_id": provider_selection.preflight_id,
        "workspace_id": provider_selection.workspace_id,
        "source_id": provider_selection.source_id,
        "candidate_id": provider_selection.candidate_id,
        "candidate_name": provider_selection.candidate_name,
        "action": provider_selection.action,
        "action_hash": provider_selection.action_hash,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "provider_kind": provider_selection.selected_provider_kind,
        "provider_reference": provider_selection.provider_reference,
        "provider_policy_manifest_path": provider_selection.provider_policy_manifest_path,
        "verifier_contract_declared": True,
        "verifier_implementation_bound": True,
        "verifier_identity_bound": True,
        "verifier_policy_bound": False,
        "verifier_receipt_contract_bound": True,
        "allowed_verification_mode": "static_identity_policy_verification_no_execution",
        "provider_binary_or_service_verified": False,
        "provider_binary_or_service_verification_source": "static_identity_fingerprint",
        "provider_runtime_probe_performed": False,
        "provider_version_captured": False,
        "provider_version_source": "policy_manifest",
        "provider_identity_fingerprint_captured": False,
        "provider_identity_fingerprint_source": "reference_and_policy_hashes",
        "service_query_performed": False,
        "process_launched": False,
        "container_launched": False,
        "sandbox_provider_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "execution_authority": False,
        "executed": False,
        "repo_code_executed": False,
        "forbidden_in_v0": [
            "execute_provider_binary",
            "query_provider_service",
            "launch_container",
            "bind_sandbox_provider",
            "run_repository_code",
        ],
        "requires": _lab_sandbox_provider_verifier_required_checks(),
    }


def _lab_sandbox_provider_verifier_current_checks(
    *,
    provider_selection: LabSandboxProviderSelectionPreflight,
    verifier_contract: dict[str, Any],
    static_verification: dict[str, Any],
) -> dict[str, Any]:
    selection_checks = _as_dict(provider_selection.current_checks)
    provider_identity = _as_dict(static_verification.get("provider_identity"))
    return {
        "provider_selection_present": bool(provider_selection.id),
        "provider_selection_ready": provider_selection.status == "ready",
        "provider_kind_selected": bool(provider_selection.provider_kind_selected),
        "provider_reference_verified": bool(provider_selection.provider_reference_verified),
        "provider_policy_manifest_bound": bool(provider_selection.provider_policy_manifest_bound),
        "verifier_contract_declared": bool(verifier_contract.get("verifier_contract_declared")),
        "verifier_implementation_bound": bool(static_verification.get("verifier_implementation_bound")),
        "verifier_identity_bound": bool(static_verification.get("verifier_identity_bound")),
        "verifier_policy_bound": bool(static_verification.get("verifier_policy_bound")),
        "verifier_receipt_contract_bound": bool(static_verification.get("verifier_receipt_contract_bound")),
        "static_identity_verification_performed": bool(provider_identity.get("static_identity_verification_performed")),
        "provider_reference_fingerprint_captured": bool(
            static_verification.get("provider_reference_fingerprint_captured")
        ),
        "provider_policy_manifest_hash_captured": bool(
            static_verification.get("provider_policy_manifest_hash_captured")
        ),
        "provider_binary_or_service_verified": bool(static_verification.get("provider_binary_or_service_verified")),
        "provider_runtime_probe_performed": bool(static_verification.get("provider_runtime_probe_performed")),
        "provider_version_captured": bool(static_verification.get("provider_version_captured")),
        "provider_identity_fingerprint_captured": bool(
            static_verification.get("provider_identity_fingerprint_captured")
        ),
        "service_query_performed": bool(static_verification.get("service_query_performed")),
        "process_launched": bool(static_verification.get("process_launched")),
        "container_launched": bool(static_verification.get("container_launched")),
        "sandbox_provider_bound": bool(selection_checks.get("sandbox_provider_bound")),
        "sandbox_bound": bool(provider_selection.sandbox_bound),
        "sandbox_enforced": bool(provider_selection.sandbox_enforced),
        "workspace_isolation_bound": bool(provider_selection.workspace_isolation_bound),
        "filesystem_write_policy_bound": bool(provider_selection.filesystem_write_policy_bound),
        "network_blocked_or_policy_bound": bool(selection_checks.get("network_blocked_or_policy_bound")),
        "resource_limits_bound": bool(provider_selection.resource_limits_bound),
        "timeout_policy_bound": bool(provider_selection.timeout_policy_bound),
        "stdout_stderr_capture_bound": bool(provider_selection.stdout_stderr_capture_bound),
        "kill_switch_bound": bool(provider_selection.kill_switch_bound),
        "command_allowlist_enforced": bool(provider_selection.command_allowlist_enforced),
        "receipt_prewrite_bound": bool(provider_selection.receipt_prewrite_bound),
        "receipt_final_write_bound": bool(provider_selection.receipt_final_write_bound),
        "approval_not_consumed": not bool(provider_selection.approval_consumed),
        "execution_authority_absent": not bool(provider_selection.execution_authority),
        "commands_not_executed": not bool(provider_selection.executed),
        "repo_code_not_executed": not bool(provider_selection.repo_code_executed),
        "network_not_accessed": not bool(provider_selection.network_accessed),
        "repo_write_not_performed": not bool(provider_selection.wrote_to_repo),
        "approval_consumed": bool(provider_selection.approval_consumed),
        "execution_authority": bool(provider_selection.execution_authority),
        "commands_executed": bool(provider_selection.executed),
        "repo_code_executed": bool(provider_selection.repo_code_executed),
        "network_accessed": bool(provider_selection.network_accessed),
        "wrote_to_repo": bool(provider_selection.wrote_to_repo),
    }


def _lab_sandbox_provider_runtime_probe_required_checks() -> list[str]:
    return [
        "sandbox_provider_verifier_present",
        "verifier_static_identity_ready",
        "provider_identity_fingerprint_captured",
        "provider_binary_or_service_verified",
        "runtime_probe_contract_declared",
        "runtime_probe_authorization_required",
        "runtime_probe_policy_bound",
        "runtime_probe_timeout_policy_declared",
        "runtime_probe_network_blocked_by_contract",
        "runtime_probe_workspace_isolation_required",
        "runtime_probe_receipt_contract_declared",
        "runtime_probe_repo_execution_separated",
        "runtime_probe_runner_bound",
        "runtime_probe_sandbox_bound",
        "runtime_probe_service_query_guard_bound",
        "runtime_probe_output_capture_bound",
        "runtime_probe_kill_switch_bound",
        "provider_runtime_probe_performed",
        "sandbox_provider_bound",
        "sandbox_bound",
        "sandbox_enforced",
        "approval_not_consumed",
        "execution_authority_absent",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_runtime_probe_contract_payload(
    *,
    provider_verifier: LabSandboxProviderVerifierPreflight,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_contract",
        "schema_version": 1,
        "mode": "runtime_probe_contract_preflight_only_no_provider_execution",
        "sandbox_provider_verifier_id": provider_verifier.id,
        "sandbox_provider_selection_id": provider_verifier.sandbox_provider_selection_id,
        "sandbox_provider_binding_id": provider_verifier.sandbox_provider_binding_id,
        "sandbox_provider_contract_id": provider_verifier.sandbox_provider_contract_id,
        "sandbox_readiness_id": provider_verifier.sandbox_readiness_id,
        "preflight_id": provider_verifier.preflight_id,
        "workspace_id": provider_verifier.workspace_id,
        "source_id": provider_verifier.source_id,
        "candidate_id": provider_verifier.candidate_id,
        "candidate_name": provider_verifier.candidate_name,
        "action": provider_verifier.action,
        "action_hash": provider_verifier.action_hash,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "provider_kind": provider_verifier.provider_kind,
        "provider_reference": provider_verifier.provider_reference,
        "provider_identity": provider_verifier.provider_identity,
        "provider_policy_manifest": provider_verifier.provider_policy_manifest,
        "runtime_probe_contract_declared": True,
        "runtime_probe_authorization_required": True,
        "runtime_probe_policy_bound": bool(provider_verifier.verifier_policy_bound),
        "runtime_probe_timeout_policy_declared": True,
        "runtime_probe_timeout_seconds": 10,
        "runtime_probe_network_blocked_by_contract": True,
        "runtime_probe_workspace_isolation_required": True,
        "runtime_probe_receipt_contract_declared": True,
        "runtime_probe_repo_execution_separated": True,
        "allowed_probe_mode": "future_governed_provider_health_probe_no_repository_code",
        "forbidden_in_v0": [
            "execute_provider_binary",
            "query_provider_service",
            "launch_container",
            "bind_sandbox_provider",
            "run_repository_code",
            "consume_repository_execution_approval",
            "write_execution_receipt",
        ],
        "requires": _lab_sandbox_provider_runtime_probe_required_checks(),
    }


def _lab_sandbox_provider_runtime_probe_current_checks(
    *,
    provider_verifier: LabSandboxProviderVerifierPreflight,
    runtime_probe_contract: dict[str, Any],
) -> dict[str, Any]:
    verifier_static_identity_ready = bool(
        provider_verifier.verifier_implementation_bound
        and provider_verifier.verifier_identity_bound
        and provider_verifier.provider_identity_fingerprint_captured
        and provider_verifier.provider_binary_or_service_verified
    )
    return {
        "sandbox_provider_verifier_present": bool(provider_verifier.id),
        "sandbox_provider_verifier_ready": provider_verifier.status == "ready",
        "verifier_static_identity_ready": verifier_static_identity_ready,
        "provider_identity_fingerprint_captured": bool(provider_verifier.provider_identity_fingerprint_captured),
        "provider_binary_or_service_verified": bool(provider_verifier.provider_binary_or_service_verified),
        "runtime_probe_contract_declared": bool(runtime_probe_contract.get("runtime_probe_contract_declared")),
        "runtime_probe_authorization_required": bool(
            runtime_probe_contract.get("runtime_probe_authorization_required")
        ),
        "runtime_probe_policy_bound": bool(runtime_probe_contract.get("runtime_probe_policy_bound")),
        "runtime_probe_timeout_policy_declared": bool(
            runtime_probe_contract.get("runtime_probe_timeout_policy_declared")
        ),
        "runtime_probe_network_blocked_by_contract": bool(
            runtime_probe_contract.get("runtime_probe_network_blocked_by_contract")
        ),
        "runtime_probe_workspace_isolation_required": bool(
            runtime_probe_contract.get("runtime_probe_workspace_isolation_required")
        ),
        "runtime_probe_receipt_contract_declared": bool(
            runtime_probe_contract.get("runtime_probe_receipt_contract_declared")
        ),
        "runtime_probe_repo_execution_separated": bool(
            runtime_probe_contract.get("runtime_probe_repo_execution_separated")
        ),
        "runtime_probe_runner_bound": False,
        "runtime_probe_sandbox_bound": False,
        "runtime_probe_service_query_guard_bound": False,
        "runtime_probe_output_capture_bound": False,
        "runtime_probe_kill_switch_bound": False,
        "provider_runtime_probe_performed": False,
        "service_query_performed": False,
        "process_launched": False,
        "container_launched": False,
        "sandbox_provider_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "approval_not_consumed": not bool(provider_verifier.approval_consumed),
        "execution_authority_absent": not bool(provider_verifier.execution_authority),
        "provider_binary_not_executed": not bool(provider_verifier.executed),
        "service_query_not_performed": not bool(provider_verifier.service_query_performed),
        "container_not_launched": not bool(provider_verifier.container_launched),
        "repo_code_not_executed": not bool(provider_verifier.repo_code_executed),
        "network_not_accessed": not bool(provider_verifier.network_accessed),
        "repo_write_not_performed": not bool(provider_verifier.wrote_to_repo),
        "approval_consumed": bool(provider_verifier.approval_consumed),
        "execution_authority": bool(provider_verifier.execution_authority),
        "commands_executed": bool(provider_verifier.executed),
        "repo_code_executed": bool(provider_verifier.repo_code_executed),
        "network_accessed": bool(provider_verifier.network_accessed),
        "wrote_to_repo": bool(provider_verifier.wrote_to_repo),
    }


def _lab_sandbox_provider_runtime_probe_harness_required_checks() -> list[str]:
    return [
        "runtime_probe_preflight_present",
        "runtime_probe_contract_declared",
        "runtime_probe_authorization_required",
        "runtime_probe_network_blocked_by_contract",
        "runtime_probe_workspace_isolation_required",
        "runtime_probe_receipt_contract_declared",
        "runtime_probe_repo_execution_separated",
        "runtime_probe_runner_contract_declared",
        "runtime_probe_runner_bound",
        "runtime_probe_sandbox_contract_declared",
        "runtime_probe_sandbox_bound",
        "runtime_probe_service_query_guard_declared",
        "runtime_probe_service_query_guard_bound",
        "runtime_probe_output_capture_declared",
        "runtime_probe_output_capture_bound",
        "runtime_probe_kill_switch_declared",
        "runtime_probe_kill_switch_bound",
        "provider_runtime_probe_performed",
        "approval_not_consumed",
        "execution_authority_absent",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "process_not_launched",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_runtime_probe_harness_contract_payload(
    *,
    runtime_probe: LabSandboxProviderRuntimeProbePreflight,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_harness_contract",
        "schema_version": 1,
        "mode": "runtime_probe_harness_preflight_only_no_provider_execution",
        "sandbox_provider_runtime_probe_id": runtime_probe.id,
        "sandbox_provider_verifier_id": runtime_probe.sandbox_provider_verifier_id,
        "sandbox_provider_selection_id": runtime_probe.sandbox_provider_selection_id,
        "sandbox_provider_binding_id": runtime_probe.sandbox_provider_binding_id,
        "sandbox_provider_contract_id": runtime_probe.sandbox_provider_contract_id,
        "sandbox_readiness_id": runtime_probe.sandbox_readiness_id,
        "preflight_id": runtime_probe.preflight_id,
        "workspace_id": runtime_probe.workspace_id,
        "source_id": runtime_probe.source_id,
        "candidate_id": runtime_probe.candidate_id,
        "candidate_name": runtime_probe.candidate_name,
        "action": runtime_probe.action,
        "action_hash": runtime_probe.action_hash,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "provider_kind": runtime_probe.provider_kind,
        "provider_reference": runtime_probe.provider_reference,
        "provider_identity": runtime_probe.provider_identity,
        "runtime_probe_contract": runtime_probe.runtime_probe_contract,
        "runtime_probe_runner_contract_declared": True,
        "runtime_probe_runner_binding_mode": "future_governed_probe_runner",
        "runtime_probe_sandbox_contract_declared": True,
        "runtime_probe_sandbox_mode": "future_network_blocked_workspace_isolated_probe",
        "runtime_probe_service_query_guard_declared": True,
        "runtime_probe_output_capture_declared": True,
        "runtime_probe_kill_switch_declared": True,
        "provider_binary_execution_allowed": False,
        "provider_service_query_allowed": False,
        "container_launch_allowed": False,
        "repository_code_execution_allowed": False,
        "approval_consumption_allowed": False,
        "execution_receipt_write_allowed": False,
        "forbidden_in_v0": [
            "execute_provider_binary",
            "query_provider_service",
            "launch_container",
            "bind_live_sandbox_provider",
            "consume_repository_execution_approval",
            "run_repository_code",
            "write_execution_receipt",
        ],
        "requires": _lab_sandbox_provider_runtime_probe_harness_required_checks(),
    }


def _lab_sandbox_provider_runtime_probe_harness_current_checks(
    *,
    runtime_probe: LabSandboxProviderRuntimeProbePreflight,
    runtime_probe_harness_contract: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_probe_preflight_present": bool(runtime_probe.id),
        "runtime_probe_contract_declared": bool(runtime_probe.runtime_probe_contract_declared),
        "runtime_probe_authorization_required": bool(runtime_probe.runtime_probe_authorization_required),
        "runtime_probe_network_blocked_by_contract": bool(runtime_probe.runtime_probe_network_blocked_by_contract),
        "runtime_probe_workspace_isolation_required": bool(runtime_probe.runtime_probe_workspace_isolation_required),
        "runtime_probe_receipt_contract_declared": bool(runtime_probe.runtime_probe_receipt_contract_declared),
        "runtime_probe_repo_execution_separated": bool(runtime_probe.runtime_probe_repo_execution_separated),
        "runtime_probe_runner_contract_declared": bool(
            runtime_probe_harness_contract.get("runtime_probe_runner_contract_declared")
        ),
        "runtime_probe_runner_bound": False,
        "runtime_probe_sandbox_contract_declared": bool(
            runtime_probe_harness_contract.get("runtime_probe_sandbox_contract_declared")
        ),
        "runtime_probe_sandbox_bound": False,
        "runtime_probe_service_query_guard_declared": bool(
            runtime_probe_harness_contract.get("runtime_probe_service_query_guard_declared")
        ),
        "runtime_probe_service_query_guard_bound": False,
        "runtime_probe_output_capture_declared": bool(
            runtime_probe_harness_contract.get("runtime_probe_output_capture_declared")
        ),
        "runtime_probe_output_capture_bound": False,
        "runtime_probe_kill_switch_declared": bool(
            runtime_probe_harness_contract.get("runtime_probe_kill_switch_declared")
        ),
        "runtime_probe_kill_switch_bound": False,
        "provider_runtime_probe_performed": False,
        "service_query_performed": False,
        "process_launched": False,
        "container_launched": False,
        "sandbox_provider_bound": False,
        "sandbox_bound": False,
        "sandbox_enforced": False,
        "approval_not_consumed": not bool(runtime_probe.approval_consumed),
        "execution_authority_absent": not bool(runtime_probe.execution_authority),
        "provider_binary_not_executed": not bool(runtime_probe.executed),
        "service_query_not_performed": not bool(runtime_probe.service_query_performed),
        "process_not_launched": not bool(runtime_probe.process_launched),
        "container_not_launched": not bool(runtime_probe.container_launched),
        "repo_code_not_executed": not bool(runtime_probe.repo_code_executed),
        "network_not_accessed": not bool(runtime_probe.network_accessed),
        "repo_write_not_performed": not bool(runtime_probe.wrote_to_repo),
        "approval_consumed": bool(runtime_probe.approval_consumed),
        "execution_authority": bool(runtime_probe.execution_authority),
        "commands_executed": bool(runtime_probe.executed),
        "repo_code_executed": bool(runtime_probe.repo_code_executed),
        "network_accessed": bool(runtime_probe.network_accessed),
        "wrote_to_repo": bool(runtime_probe.wrote_to_repo),
    }


def _lab_sandbox_provider_runtime_probe_runner_readiness_required_checks() -> list[str]:
    return [
        "runtime_probe_harness_present",
        "runtime_probe_harness_contract_declared",
        "runtime_probe_runner_contract_declared",
        "runtime_probe_sandbox_contract_declared",
        "runtime_probe_service_query_guard_declared",
        "runtime_probe_output_capture_declared",
        "runtime_probe_kill_switch_declared",
        "probe_runner_interface_declared",
        "probe_runner_implementation_bound",
        "probe_runner_identity_bound",
        "probe_runner_policy_bound",
        "probe_runner_sandbox_bound",
        "probe_runner_network_blocked",
        "probe_runner_workspace_isolated",
        "probe_runner_timeout_bound",
        "probe_runner_output_capture_bound",
        "probe_runner_kill_switch_bound",
        "probe_runner_receipt_contract_bound",
        "provider_runtime_probe_performed",
        "approval_not_consumed",
        "execution_authority_absent",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "process_not_launched",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_runtime_probe_runner_interface_payload(
    *,
    harness: LabSandboxProviderRuntimeProbeHarnessPreflight,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_runner_readiness",
        "schema_version": 1,
        "mode": "probe_runner_interface_readiness_only_no_provider_execution",
        "sandbox_provider_runtime_probe_harness_id": harness.id,
        "sandbox_provider_runtime_probe_id": harness.sandbox_provider_runtime_probe_id,
        "sandbox_provider_verifier_id": harness.sandbox_provider_verifier_id,
        "sandbox_provider_selection_id": harness.sandbox_provider_selection_id,
        "sandbox_provider_binding_id": harness.sandbox_provider_binding_id,
        "sandbox_provider_contract_id": harness.sandbox_provider_contract_id,
        "sandbox_readiness_id": harness.sandbox_readiness_id,
        "command_allowlist_enforcement_id": harness.command_allowlist_enforcement_id,
        "preflight_id": harness.preflight_id,
        "workspace_id": harness.workspace_id,
        "source_id": harness.source_id,
        "candidate_id": harness.candidate_id,
        "candidate_name": harness.candidate_name,
        "action": harness.action,
        "action_hash": harness.action_hash,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "provider_kind": harness.provider_kind,
        "provider_reference": harness.provider_reference,
        "provider_identity": harness.provider_identity,
        "input_contract": {
            "provider_identity_required": True,
            "provider_reference_required": bool(harness.provider_reference),
            "workspace_reference_required": True,
            "network_must_be_blocked": True,
            "repository_code_execution_allowed": False,
            "provider_binary_execution_allowed": False,
            "service_query_allowed": False,
        },
        "output_contract": {
            "stdout_stderr_capture_required": True,
            "receipt_contract_required": True,
            "secret_redaction_required": True,
            "no_raw_secret_storage": True,
        },
        "control_contract": {
            "implementation_binding_required": True,
            "runner_identity_required": True,
            "policy_binding_required": True,
            "sandbox_binding_required": True,
            "workspace_isolation_required": True,
            "timeout_required": True,
            "kill_switch_required": True,
        },
        "probe_runner_interface_declared": True,
        "probe_runner_implementation_bound": False,
        "probe_runner_identity_bound": False,
        "probe_runner_policy_bound": False,
        "probe_runner_sandbox_bound": False,
        "probe_runner_network_blocked": False,
        "probe_runner_workspace_isolated": False,
        "probe_runner_timeout_bound": False,
        "probe_runner_output_capture_bound": False,
        "probe_runner_kill_switch_bound": False,
        "probe_runner_receipt_contract_bound": False,
        "provider_runtime_probe_performed": False,
        "provider_binary_execution_allowed": False,
        "provider_service_query_allowed": False,
        "container_launch_allowed": False,
        "repository_code_execution_allowed": False,
        "approval_consumption_allowed": False,
        "execution_receipt_write_allowed": False,
        "requires": _lab_sandbox_provider_runtime_probe_runner_readiness_required_checks(),
    }


def _lab_sandbox_provider_runtime_probe_runner_readiness_current_checks(
    *,
    harness: LabSandboxProviderRuntimeProbeHarnessPreflight,
    probe_runner_interface: dict[str, Any],
) -> dict[str, Any]:
    harness_contract_declared = (
        harness.runtime_probe_runner_contract_declared
        and harness.runtime_probe_sandbox_contract_declared
        and harness.runtime_probe_service_query_guard_declared
        and harness.runtime_probe_output_capture_declared
        and harness.runtime_probe_kill_switch_declared
    )
    return {
        "runtime_probe_harness_present": bool(harness.id),
        "runtime_probe_harness_contract_declared": bool(harness_contract_declared),
        "runtime_probe_runner_contract_declared": bool(harness.runtime_probe_runner_contract_declared),
        "runtime_probe_sandbox_contract_declared": bool(harness.runtime_probe_sandbox_contract_declared),
        "runtime_probe_service_query_guard_declared": bool(harness.runtime_probe_service_query_guard_declared),
        "runtime_probe_output_capture_declared": bool(harness.runtime_probe_output_capture_declared),
        "runtime_probe_kill_switch_declared": bool(harness.runtime_probe_kill_switch_declared),
        "probe_runner_interface_declared": bool(probe_runner_interface.get("probe_runner_interface_declared")),
        "probe_runner_implementation_bound": False,
        "probe_runner_identity_bound": False,
        "probe_runner_policy_bound": False,
        "probe_runner_sandbox_bound": False,
        "probe_runner_network_blocked": False,
        "probe_runner_workspace_isolated": False,
        "probe_runner_timeout_bound": False,
        "probe_runner_output_capture_bound": False,
        "probe_runner_kill_switch_bound": False,
        "probe_runner_receipt_contract_bound": False,
        "provider_runtime_probe_performed": False,
        "approval_not_consumed": not bool(harness.approval_consumed),
        "execution_authority_absent": not bool(harness.execution_authority),
        "provider_binary_not_executed": not bool(harness.executed),
        "service_query_not_performed": not bool(harness.service_query_performed),
        "process_not_launched": not bool(harness.process_launched),
        "container_not_launched": not bool(harness.container_launched),
        "repo_code_not_executed": not bool(harness.repo_code_executed),
        "network_not_accessed": not bool(harness.network_accessed),
        "repo_write_not_performed": not bool(harness.wrote_to_repo),
        "approval_consumed": bool(harness.approval_consumed),
        "execution_authority": bool(harness.execution_authority),
        "commands_executed": bool(harness.executed),
        "repo_code_executed": bool(harness.repo_code_executed),
        "network_accessed": bool(harness.network_accessed),
        "wrote_to_repo": bool(harness.wrote_to_repo),
    }


def _lab_sandbox_provider_runtime_probe_runner_binding_required_checks() -> list[str]:
    return [
        "runner_readiness_present",
        "probe_runner_interface_declared",
        "probe_runner_readiness_ready",
        "probe_runner_binding_contract_declared",
        "probe_runner_implementation_bound",
        "probe_runner_identity_bound",
        "probe_runner_policy_bound",
        "probe_runner_sandbox_bound",
        "probe_runner_network_blocked",
        "probe_runner_workspace_isolated",
        "probe_runner_timeout_bound",
        "probe_runner_output_capture_bound",
        "probe_runner_kill_switch_bound",
        "probe_runner_receipt_contract_bound",
        "probe_runner_bound",
        "runtime_probe_bound",
        "provider_runtime_probe_performed",
        "approval_not_consumed",
        "execution_authority_absent",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "process_not_launched",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_runtime_probe_runner_binding_contract_payload(
    *,
    readiness: LabSandboxProviderRuntimeProbeRunnerReadiness,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_runner_binding_preflight",
        "schema_version": 1,
        "mode": "probe_runner_binding_preflight_no_provider_execution",
        "sandbox_provider_runtime_probe_runner_readiness_id": readiness.id,
        "sandbox_provider_runtime_probe_harness_id": readiness.sandbox_provider_runtime_probe_harness_id,
        "sandbox_provider_runtime_probe_id": readiness.sandbox_provider_runtime_probe_id,
        "sandbox_provider_verifier_id": readiness.sandbox_provider_verifier_id,
        "sandbox_provider_selection_id": readiness.sandbox_provider_selection_id,
        "sandbox_provider_binding_id": readiness.sandbox_provider_binding_id,
        "sandbox_provider_contract_id": readiness.sandbox_provider_contract_id,
        "sandbox_readiness_id": readiness.sandbox_readiness_id,
        "command_allowlist_enforcement_id": readiness.command_allowlist_enforcement_id,
        "preflight_id": readiness.preflight_id,
        "workspace_id": readiness.workspace_id,
        "source_id": readiness.source_id,
        "candidate_id": readiness.candidate_id,
        "candidate_name": readiness.candidate_name,
        "action": readiness.action,
        "action_hash": readiness.action_hash,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "provider_kind": readiness.provider_kind,
        "provider_reference": readiness.provider_reference,
        "provider_identity": readiness.provider_identity,
        "readiness_contract": {
            "readiness_status_required": "ready",
            "current_readiness_status": readiness.status,
            "readiness_missing_checks": list(readiness.missing_checks),
            "readiness_must_have_no_blockers": True,
        },
        "binding_contract": {
            "implementation_binding_required": True,
            "runner_identity_binding_required": True,
            "policy_binding_required": True,
            "sandbox_binding_required": True,
            "network_block_required": True,
            "workspace_isolation_required": True,
            "timeout_required": True,
            "output_capture_required": True,
            "kill_switch_required": True,
            "receipt_contract_required": True,
            "runtime_probe_binding_required": True,
        },
        "prohibited_during_preflight": {
            "provider_runtime_probe": True,
            "provider_binary_execution": True,
            "provider_service_query": True,
            "process_launch": True,
            "container_launch": True,
            "repository_code_execution": True,
            "approval_consumption": True,
            "execution_receipt_write": True,
        },
        "probe_runner_binding_contract_declared": True,
        "probe_runner_bound": False,
        "runtime_probe_bound": False,
        "provider_runtime_probe_performed": False,
        "provider_binary_execution_allowed": False,
        "provider_service_query_allowed": False,
        "process_launch_allowed": False,
        "container_launch_allowed": False,
        "repository_code_execution_allowed": False,
        "approval_consumption_allowed": False,
        "execution_receipt_write_allowed": False,
        "requires": _lab_sandbox_provider_runtime_probe_runner_binding_required_checks(),
    }


def _lab_sandbox_provider_runtime_probe_runner_binding_current_checks(
    *,
    readiness: LabSandboxProviderRuntimeProbeRunnerReadiness,
    binding_contract: dict[str, Any],
) -> dict[str, Any]:
    readiness_ready = (
        readiness.status == "ready"
        and not readiness.missing_checks
        and readiness.probe_runner_interface_declared
        and readiness.probe_runner_implementation_bound
        and readiness.probe_runner_identity_bound
        and readiness.probe_runner_policy_bound
        and readiness.probe_runner_sandbox_bound
        and readiness.probe_runner_network_blocked
        and readiness.probe_runner_workspace_isolated
        and readiness.probe_runner_timeout_bound
        and readiness.probe_runner_output_capture_bound
        and readiness.probe_runner_kill_switch_bound
        and readiness.probe_runner_receipt_contract_bound
    )
    return {
        "runner_readiness_present": bool(readiness.id),
        "probe_runner_interface_declared": bool(readiness.probe_runner_interface_declared),
        "probe_runner_readiness_ready": bool(readiness_ready),
        "probe_runner_binding_contract_declared": bool(binding_contract.get("probe_runner_binding_contract_declared")),
        "probe_runner_implementation_bound": bool(readiness.probe_runner_implementation_bound),
        "probe_runner_identity_bound": bool(readiness.probe_runner_identity_bound),
        "probe_runner_policy_bound": bool(readiness.probe_runner_policy_bound),
        "probe_runner_sandbox_bound": bool(readiness.probe_runner_sandbox_bound),
        "probe_runner_network_blocked": bool(readiness.probe_runner_network_blocked),
        "probe_runner_workspace_isolated": bool(readiness.probe_runner_workspace_isolated),
        "probe_runner_timeout_bound": bool(readiness.probe_runner_timeout_bound),
        "probe_runner_output_capture_bound": bool(readiness.probe_runner_output_capture_bound),
        "probe_runner_kill_switch_bound": bool(readiness.probe_runner_kill_switch_bound),
        "probe_runner_receipt_contract_bound": bool(readiness.probe_runner_receipt_contract_bound),
        "probe_runner_bound": False,
        "runtime_probe_bound": False,
        "provider_runtime_probe_performed": False,
        "approval_not_consumed": not bool(readiness.approval_consumed),
        "execution_authority_absent": not bool(readiness.execution_authority),
        "provider_binary_not_executed": not bool(readiness.executed),
        "service_query_not_performed": not bool(readiness.service_query_performed),
        "process_not_launched": not bool(readiness.process_launched),
        "container_not_launched": not bool(readiness.container_launched),
        "repo_code_not_executed": not bool(readiness.repo_code_executed),
        "network_not_accessed": not bool(readiness.network_accessed),
        "repo_write_not_performed": not bool(readiness.wrote_to_repo),
        "approval_consumed": bool(readiness.approval_consumed),
        "execution_authority": bool(readiness.execution_authority),
        "commands_executed": bool(readiness.executed),
        "repo_code_executed": bool(readiness.repo_code_executed),
        "network_accessed": bool(readiness.network_accessed),
        "wrote_to_repo": bool(readiness.wrote_to_repo),
        "service_query_performed": bool(readiness.service_query_performed),
        "process_launched": bool(readiness.process_launched),
        "container_launched": bool(readiness.container_launched),
        "sandbox_provider_bound": bool(readiness.sandbox_provider_bound),
        "sandbox_bound": bool(readiness.sandbox_bound),
        "sandbox_enforced": bool(readiness.sandbox_enforced),
    }


def _lab_sandbox_provider_runtime_probe_runner_enforcement_required_checks() -> list[str]:
    return [
        "runner_binding_present",
        "probe_runner_binding_contract_declared",
        "probe_runner_binding_ready",
        "probe_runner_enforcement_contract_declared",
        "probe_runner_enforcement_bound",
        "probe_runner_bound",
        "runtime_probe_bound",
        "probe_runner_identity_bound",
        "probe_runner_policy_bound",
        "probe_runner_sandbox_bound",
        "probe_runner_network_blocked",
        "probe_runner_workspace_isolated",
        "probe_runner_timeout_bound",
        "probe_runner_output_capture_bound",
        "probe_runner_kill_switch_bound",
        "probe_runner_receipt_contract_bound",
        "provider_runtime_probe_performed",
        "approval_not_consumed",
        "execution_authority_absent",
        "provider_binary_not_executed",
        "service_query_not_performed",
        "process_not_launched",
        "container_not_launched",
        "repo_code_not_executed",
        "network_not_accessed",
        "repo_write_not_performed",
    ]


def _lab_sandbox_provider_runtime_probe_runner_enforcement_contract_payload(
    *,
    binding: LabSandboxProviderRuntimeProbeRunnerBindingPreflight,
    workspace: LabWorkspaceRecord,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.sandbox_provider_runtime_probe_runner_enforcement_preflight",
        "schema_version": 1,
        "mode": "probe_runner_enforcement_preflight_no_provider_execution",
        "sandbox_provider_runtime_probe_runner_binding_id": binding.id,
        "sandbox_provider_runtime_probe_runner_readiness_id": binding.sandbox_provider_runtime_probe_runner_readiness_id,
        "sandbox_provider_runtime_probe_harness_id": binding.sandbox_provider_runtime_probe_harness_id,
        "sandbox_provider_runtime_probe_id": binding.sandbox_provider_runtime_probe_id,
        "sandbox_provider_verifier_id": binding.sandbox_provider_verifier_id,
        "sandbox_provider_selection_id": binding.sandbox_provider_selection_id,
        "sandbox_provider_binding_id": binding.sandbox_provider_binding_id,
        "sandbox_provider_contract_id": binding.sandbox_provider_contract_id,
        "sandbox_readiness_id": binding.sandbox_readiness_id,
        "command_allowlist_enforcement_id": binding.command_allowlist_enforcement_id,
        "preflight_id": binding.preflight_id,
        "workspace_id": binding.workspace_id,
        "source_id": binding.source_id,
        "candidate_id": binding.candidate_id,
        "candidate_name": binding.candidate_name,
        "action": binding.action,
        "action_hash": binding.action_hash,
        "workspace_path": workspace.path,
        "workspace_manifest_path": workspace.manifest_path,
        "provider_kind": binding.provider_kind,
        "provider_reference": binding.provider_reference,
        "provider_identity": binding.provider_identity,
        "binding_contract": {
            "binding_status_required": "ready",
            "current_binding_status": binding.status,
            "binding_missing_checks": list(binding.missing_checks),
            "binding_must_have_no_blockers": True,
        },
        "enforcement_contract": {
            "live_probe_runner_binding_required": True,
            "live_runtime_probe_binding_required": True,
            "runner_identity_enforcement_required": True,
            "policy_enforcement_required": True,
            "sandbox_enforcement_required": True,
            "network_block_enforcement_required": True,
            "workspace_isolation_enforcement_required": True,
            "timeout_enforcement_required": True,
            "output_capture_enforcement_required": True,
            "kill_switch_enforcement_required": True,
            "receipt_contract_enforcement_required": True,
        },
        "prohibited_during_preflight": {
            "provider_runtime_probe": True,
            "provider_binary_execution": True,
            "provider_service_query": True,
            "process_launch": True,
            "container_launch": True,
            "repository_code_execution": True,
            "approval_consumption": True,
            "execution_receipt_write": True,
        },
        "probe_runner_enforcement_contract_declared": True,
        "probe_runner_enforcement_bound": False,
        "probe_runner_bound": False,
        "runtime_probe_bound": False,
        "provider_runtime_probe_performed": False,
        "provider_binary_execution_allowed": False,
        "provider_service_query_allowed": False,
        "process_launch_allowed": False,
        "container_launch_allowed": False,
        "repository_code_execution_allowed": False,
        "approval_consumption_allowed": False,
        "execution_receipt_write_allowed": False,
        "requires": _lab_sandbox_provider_runtime_probe_runner_enforcement_required_checks(),
    }


def _lab_sandbox_provider_runtime_probe_runner_enforcement_current_checks(
    *,
    binding: LabSandboxProviderRuntimeProbeRunnerBindingPreflight,
    enforcement_contract: dict[str, Any],
) -> dict[str, Any]:
    binding_ready = (
        binding.status == "ready"
        and not binding.missing_checks
        and binding.probe_runner_binding_contract_declared
        and binding.probe_runner_bound
        and binding.runtime_probe_bound
        and binding.probe_runner_identity_bound
        and binding.probe_runner_policy_bound
        and binding.probe_runner_sandbox_bound
        and binding.probe_runner_network_blocked
        and binding.probe_runner_workspace_isolated
        and binding.probe_runner_timeout_bound
        and binding.probe_runner_output_capture_bound
        and binding.probe_runner_kill_switch_bound
        and binding.probe_runner_receipt_contract_bound
    )
    return {
        "runner_binding_present": bool(binding.id),
        "probe_runner_binding_contract_declared": bool(binding.probe_runner_binding_contract_declared),
        "probe_runner_binding_ready": bool(binding_ready),
        "probe_runner_enforcement_contract_declared": bool(
            enforcement_contract.get("probe_runner_enforcement_contract_declared")
        ),
        "probe_runner_enforcement_bound": False,
        "probe_runner_bound": bool(binding.probe_runner_bound),
        "runtime_probe_bound": bool(binding.runtime_probe_bound),
        "probe_runner_identity_bound": bool(binding.probe_runner_identity_bound),
        "probe_runner_policy_bound": bool(binding.probe_runner_policy_bound),
        "probe_runner_sandbox_bound": bool(binding.probe_runner_sandbox_bound),
        "probe_runner_network_blocked": bool(binding.probe_runner_network_blocked),
        "probe_runner_workspace_isolated": bool(binding.probe_runner_workspace_isolated),
        "probe_runner_timeout_bound": bool(binding.probe_runner_timeout_bound),
        "probe_runner_output_capture_bound": bool(binding.probe_runner_output_capture_bound),
        "probe_runner_kill_switch_bound": bool(binding.probe_runner_kill_switch_bound),
        "probe_runner_receipt_contract_bound": bool(binding.probe_runner_receipt_contract_bound),
        "provider_runtime_probe_performed": False,
        "approval_not_consumed": not bool(binding.approval_consumed),
        "execution_authority_absent": not bool(binding.execution_authority),
        "provider_binary_not_executed": not bool(binding.executed),
        "service_query_not_performed": not bool(binding.service_query_performed),
        "process_not_launched": not bool(binding.process_launched),
        "container_not_launched": not bool(binding.container_launched),
        "repo_code_not_executed": not bool(binding.repo_code_executed),
        "network_not_accessed": not bool(binding.network_accessed),
        "repo_write_not_performed": not bool(binding.wrote_to_repo),
        "approval_consumed": bool(binding.approval_consumed),
        "execution_authority": bool(binding.execution_authority),
        "commands_executed": bool(binding.executed),
        "repo_code_executed": bool(binding.repo_code_executed),
        "network_accessed": bool(binding.network_accessed),
        "wrote_to_repo": bool(binding.wrote_to_repo),
        "service_query_performed": bool(binding.service_query_performed),
        "process_launched": bool(binding.process_launched),
        "container_launched": bool(binding.container_launched),
        "sandbox_provider_bound": bool(binding.sandbox_provider_bound),
        "sandbox_bound": bool(binding.sandbox_bound),
        "sandbox_enforced": bool(binding.sandbox_enforced),
    }


def _lab_execution_receipt_write_required_checks() -> list[str]:
    return [
        "sandbox_readiness_present",
        "runner_sandbox_readiness_ready",
        "receipt_sink_reservation_present",
        "reserved_execution_receipt_id_present",
        "reserved_execution_receipt_path_present",
        "reserved_execution_receipt_not_written",
        "receipt_schema_bound",
        "receipt_prewrite_writer_bound",
        "receipt_final_writer_bound",
        "prewrite_before_execution_required",
        "final_write_after_execution_required",
        "sandbox_bound",
        "runner_bound",
        "command_allowlist_enforced",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
    ]


def _lab_execution_receipt_write_contract(
    *,
    sandbox_readiness: LabRunnerSandboxReadiness,
    reservation: LabExecutionReceiptSinkReservation,
) -> dict[str, Any]:
    reserved = reservation.reserved_execution_receipt
    return {
        "contract_kind": "francis.lab.execution_receipt_write_readiness",
        "schema_version": 1,
        "mode": "receipt_write_readiness_preflight_only_no_execution_receipt_write",
        "sandbox_readiness_id": sandbox_readiness.id,
        "receipt_sink_reservation_id": reservation.id,
        "preflight_id": sandbox_readiness.preflight_id,
        "workspace_id": sandbox_readiness.workspace_id,
        "action": sandbox_readiness.action,
        "action_hash": sandbox_readiness.action_hash,
        "reserved_execution_receipt_id": _safe_str(reserved.get("id")).strip(),
        "reserved_execution_receipt_path": _safe_str(reserved.get("path")).strip(),
        "operation": "lab.execution.run",
        "prewrite_bound": False,
        "final_write_bound": False,
        "execution_receipt_prewritten": False,
        "execution_receipt_finalized": False,
        "requires": _lab_execution_receipt_write_required_checks(),
    }


def _lab_execution_receipt_write_current_checks(
    *,
    sandbox_readiness: LabRunnerSandboxReadiness,
    reservation: LabExecutionReceiptSinkReservation,
) -> dict[str, Any]:
    reserved = reservation.reserved_execution_receipt
    reserved_id = _safe_str(reserved.get("id")).strip()
    reserved_path = _safe_str(reserved.get("path")).strip()
    reserved_file = Path(reserved_path) if reserved_path else None
    return {
        "sandbox_readiness_present": True,
        "runner_sandbox_readiness_ready": sandbox_readiness.status == "ready",
        "receipt_sink_reservation_present": True,
        "reserved_execution_receipt_id_present": bool(reserved_id),
        "reserved_execution_receipt_path_present": bool(reserved_path),
        "reserved_execution_receipt_not_written": bool(reserved_file is None or not reserved_file.exists()),
        "receipt_schema_bound": False,
        "receipt_prewrite_writer_bound": False,
        "receipt_final_writer_bound": False,
        "prewrite_before_execution_required": True,
        "final_write_after_execution_required": True,
        "sandbox_bound": bool(sandbox_readiness.sandbox_bound),
        "runner_bound": bool(sandbox_readiness.runner_bound),
        "command_allowlist_enforced": bool(sandbox_readiness.allowlist_enforced),
        "approval_not_consumed": not bool(sandbox_readiness.approval_consumed),
        "execution_authority_absent": not bool(sandbox_readiness.execution_authority),
        "commands_not_executed": not bool(sandbox_readiness.executed),
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_execution_receipt_schema_contract(
    *,
    write_readiness: LabExecutionReceiptWriteReadiness,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.execution_receipt_schema",
        "schema_version": 1,
        "operation": "lab.execution.run",
        "mode": "schema_contract_only_no_execution_receipt_write",
        "source_id": write_readiness.source_id,
        "candidate_id": write_readiness.candidate_id,
        "preflight_id": write_readiness.preflight_id,
        "workspace_id": write_readiness.workspace_id,
        "action": write_readiness.action,
        "action_hash": write_readiness.action_hash,
        "required_top_level_fields": [
            "id",
            "timestamp",
            "operation",
            "source_id",
            "actor",
            "input_paths",
            "input_hashes",
            "result_status",
            "warnings",
            "errors",
            "generated_artifact_paths",
            "validation_performed",
            "execution",
            "governance",
        ],
        "required_execution_fields": [
            "executed",
            "execution_authority",
            "ran_repo_scripts",
            "ran_install",
            "ran_build",
            "ran_tests",
            "network_accessed",
            "wrote_to_repo",
            "approval_consumed",
            "reserved_execution_receipt_id",
            "reserved_execution_receipt_path",
        ],
        "sensitive_value_policy": {
            "store_file_contents": False,
            "store_sensitive_values": False,
            "record_sensitive_file_presence_only": True,
            "redaction_required": True,
        },
        "status_lifecycle": ["prewritten", "running", "finalized", "failed", "refused", "blocked"],
    }


def _lab_execution_receipt_prewrite_contract(
    *,
    write_readiness: LabExecutionReceiptWriteReadiness,
    schema_hash: str,
) -> dict[str, Any]:
    reserved = write_readiness.reserved_execution_receipt
    return {
        "contract_kind": "francis.lab.execution_receipt_prewrite",
        "schema_version": 1,
        "mode": "prewrite_contract_bound_no_execution_receipt_write",
        "operation": "lab.execution.run",
        "receipt_write_readiness_id": write_readiness.id,
        "receipt_sink_reservation_id": write_readiness.receipt_sink_reservation_id,
        "preflight_id": write_readiness.preflight_id,
        "workspace_id": write_readiness.workspace_id,
        "source_id": write_readiness.source_id,
        "candidate_id": write_readiness.candidate_id,
        "action": write_readiness.action,
        "action_hash": write_readiness.action_hash,
        "schema_hash": schema_hash,
        "reserved_execution_receipt_id": _safe_str(reserved.get("id")).strip(),
        "reserved_execution_receipt_path": _safe_str(reserved.get("path")).strip(),
        "must_prewrite_before": [
            "approval_consumption",
            "execution_authority_grant",
            "runner_start",
            "command_execution",
        ],
        "initial_result_status": "prewritten",
        "writes_reserved_execution_receipt": False,
        "execution_authority": False,
        "approval_consumed": False,
        "executed": False,
    }


def _lab_execution_receipt_final_write_contract(
    *,
    write_readiness: LabExecutionReceiptWriteReadiness,
    schema_hash: str,
    prewrite_contract_hash: str,
) -> dict[str, Any]:
    reserved = write_readiness.reserved_execution_receipt
    return {
        "contract_kind": "francis.lab.execution_receipt_final_write",
        "schema_version": 1,
        "mode": "final_write_contract_bound_no_execution_receipt_write",
        "operation": "lab.execution.run",
        "receipt_write_readiness_id": write_readiness.id,
        "receipt_sink_reservation_id": write_readiness.receipt_sink_reservation_id,
        "preflight_id": write_readiness.preflight_id,
        "workspace_id": write_readiness.workspace_id,
        "source_id": write_readiness.source_id,
        "candidate_id": write_readiness.candidate_id,
        "action": write_readiness.action,
        "action_hash": write_readiness.action_hash,
        "schema_hash": schema_hash,
        "prewrite_contract_hash": prewrite_contract_hash,
        "reserved_execution_receipt_id": _safe_str(reserved.get("id")).strip(),
        "reserved_execution_receipt_path": _safe_str(reserved.get("path")).strip(),
        "must_finalize_after": [
            "runner_exit",
            "timeout",
            "refusal",
            "failure",
            "operator_abort",
        ],
        "terminal_result_statuses": ["validated", "failed", "refused", "blocked"],
        "writes_reserved_execution_receipt": False,
        "execution_authority": False,
        "approval_consumed": False,
        "executed": False,
    }


def _lab_execution_receipt_prewrite_binding_contract(
    *,
    write_readiness: LabExecutionReceiptWriteReadiness,
    schema_hash: str,
    prewrite_contract_hash: str,
    final_write_contract_hash: str,
) -> dict[str, Any]:
    return {
        "contract_kind": "francis.lab.execution_receipt_prewrite_binding",
        "schema_version": 1,
        "mode": "contract_binding_only_no_execution_receipt_write",
        "operation": "lab.execution.run",
        "receipt_write_readiness_id": write_readiness.id,
        "receipt_sink_reservation_id": write_readiness.receipt_sink_reservation_id,
        "sandbox_readiness_id": write_readiness.sandbox_readiness_id,
        "command_allowlist_enforcement_id": write_readiness.command_allowlist_enforcement_id,
        "preflight_id": write_readiness.preflight_id,
        "workspace_id": write_readiness.workspace_id,
        "source_id": write_readiness.source_id,
        "candidate_id": write_readiness.candidate_id,
        "action_hash": write_readiness.action_hash,
        "schema_hash": schema_hash,
        "prewrite_contract_hash": prewrite_contract_hash,
        "final_write_contract_hash": final_write_contract_hash,
        "receipt_schema_bound": True,
        "prewrite_contract_bound": True,
        "final_write_contract_bound": True,
        "prewrite_writer_bound": False,
        "final_write_writer_bound": False,
        "execution_receipt_prewritten": False,
        "execution_receipt_finalized": False,
        "execution_authority": False,
        "approval_consumed": False,
        "executed": False,
    }


def _lab_execution_receipt_prewrite_binding_required_checks() -> list[str]:
    return [
        "receipt_write_readiness_present",
        "receipt_sink_reservation_present",
        "reserved_execution_receipt_id_present",
        "reserved_execution_receipt_path_present",
        "reserved_execution_receipt_not_written",
        "schema_contract_bound",
        "schema_hash_present",
        "prewrite_contract_bound",
        "prewrite_contract_hash_present",
        "final_write_contract_bound",
        "final_write_contract_hash_present",
        "prewrite_before_execution_required",
        "final_write_after_execution_required",
        "prewrite_writer_bound",
        "final_writer_bound",
        "sandbox_bound",
        "runner_bound",
        "command_allowlist_enforced",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
    ]


def _lab_execution_receipt_prewrite_binding_current_checks(
    *,
    write_readiness: LabExecutionReceiptWriteReadiness,
    schema_hash: str,
    prewrite_contract_hash: str,
    final_write_contract_hash: str,
) -> dict[str, Any]:
    reserved = write_readiness.reserved_execution_receipt
    reserved_id = _safe_str(reserved.get("id")).strip()
    reserved_path = _safe_str(reserved.get("path")).strip()
    reserved_file = Path(reserved_path) if reserved_path else None
    return {
        "receipt_write_readiness_present": True,
        "receipt_sink_reservation_present": bool(write_readiness.receipt_sink_reservation_id),
        "reserved_execution_receipt_id_present": bool(reserved_id),
        "reserved_execution_receipt_path_present": bool(reserved_path),
        "reserved_execution_receipt_not_written": bool(reserved_file is None or not reserved_file.exists()),
        "schema_contract_bound": bool(schema_hash),
        "schema_hash_present": bool(schema_hash),
        "prewrite_contract_bound": bool(prewrite_contract_hash),
        "prewrite_contract_hash_present": bool(prewrite_contract_hash),
        "final_write_contract_bound": bool(final_write_contract_hash),
        "final_write_contract_hash_present": bool(final_write_contract_hash),
        "prewrite_before_execution_required": True,
        "final_write_after_execution_required": True,
        "prewrite_writer_bound": False,
        "final_writer_bound": False,
        "sandbox_bound": bool(write_readiness.current_checks.get("sandbox_bound")),
        "runner_bound": bool(write_readiness.current_checks.get("runner_bound")),
        "command_allowlist_enforced": bool(write_readiness.current_checks.get("command_allowlist_enforced")),
        "approval_not_consumed": not bool(write_readiness.approval_consumed),
        "execution_authority_absent": not bool(write_readiness.execution_authority),
        "commands_not_executed": not bool(write_readiness.executed),
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _path_is_within(parent: Path, child: Path) -> bool:
    try:
        parent_resolved = parent.resolve(strict=False)
        child_resolved = child.resolve(strict=False)
    except OSError:
        return False
    return child_resolved == parent_resolved or child_resolved.is_relative_to(parent_resolved)


def _lab_execution_receipt_writer_boundary(
    *,
    prewrite_binding: LabExecutionReceiptPrewriteBinding,
) -> dict[str, Any]:
    artifact_root = ingest_artifact_root() / "lab_execution_receipts"
    reserved = prewrite_binding.reserved_execution_receipt
    reserved_path = _safe_str(reserved.get("path")).strip()
    reserved_file = Path(reserved_path) if reserved_path else None
    temp_path = str(reserved_file.with_suffix(reserved_file.suffix + ".tmp")) if reserved_file else ""
    return {
        "boundary_kind": "francis.lab.execution_receipt_writer_boundary",
        "schema_version": 1,
        "mode": "writer_preflight_only_no_execution_receipt_write",
        "artifact_root": str(artifact_root),
        "reserved_execution_receipt_id": _safe_str(reserved.get("id")).strip(),
        "reserved_execution_receipt_path": reserved_path,
        "reserved_execution_receipt_temp_path": temp_path,
        "reserved_path_within_sink": bool(reserved_file and _path_is_within(artifact_root, reserved_file)),
        "reserved_path_exists": bool(reserved_file and reserved_file.exists()),
        "reserved_receipt_not_written": bool(reserved_file is None or not reserved_file.exists()),
        "allowed_operations": ["prewrite", "finalize"],
        "atomic_write_strategy": "write_tmp_then_replace",
        "temp_suffix": ".tmp",
        "redaction_required": True,
        "store_file_contents": False,
        "store_sensitive_values": False,
        "writes_reserved_execution_receipt": False,
    }


def _lab_execution_receipt_writer_contract(
    *,
    prewrite_binding: LabExecutionReceiptPrewriteBinding,
    writer_boundary: dict[str, Any],
) -> dict[str, Any]:
    binding = prewrite_binding.contract_binding
    return {
        "contract_kind": "francis.lab.execution_receipt_writer_preflight",
        "schema_version": 1,
        "mode": "writer_preflight_only_no_execution_receipt_write",
        "operation": "lab.execution.run",
        "receipt_prewrite_binding_id": prewrite_binding.id,
        "receipt_write_readiness_id": prewrite_binding.receipt_write_readiness_id,
        "receipt_sink_reservation_id": prewrite_binding.receipt_sink_reservation_id,
        "preflight_id": prewrite_binding.preflight_id,
        "workspace_id": prewrite_binding.workspace_id,
        "source_id": prewrite_binding.source_id,
        "candidate_id": prewrite_binding.candidate_id,
        "action": prewrite_binding.action,
        "action_hash": prewrite_binding.action_hash,
        "schema_hash": _safe_str(binding.get("schema_hash")).strip(),
        "prewrite_contract_hash": _safe_str(binding.get("prewrite_contract_hash")).strip(),
        "final_write_contract_hash": _safe_str(binding.get("final_write_contract_hash")).strip(),
        "reserved_execution_receipt_id": _safe_str(writer_boundary.get("reserved_execution_receipt_id")).strip(),
        "reserved_execution_receipt_path": _safe_str(writer_boundary.get("reserved_execution_receipt_path")).strip(),
        "reserved_execution_receipt_temp_path": _safe_str(
            writer_boundary.get("reserved_execution_receipt_temp_path")
        ).strip(),
        "atomic_write_strategy": "write_tmp_then_replace",
        "temp_suffix": ".tmp",
        "redaction_required": True,
        "store_file_contents": False,
        "store_sensitive_values": False,
        "writer_interface_declared": True,
        "writer_implementation_bound": False,
        "prewrite_writer_bound": False,
        "final_write_writer_bound": False,
        "writes_reserved_execution_receipt": False,
        "execution_receipt_prewritten": False,
        "execution_receipt_finalized": False,
        "execution_authority": False,
        "approval_consumed": False,
        "executed": False,
    }


def _lab_execution_receipt_writer_prewrite_operation(
    *,
    prewrite_binding: LabExecutionReceiptPrewriteBinding,
    writer_contract_hash: str,
) -> dict[str, Any]:
    reserved = prewrite_binding.reserved_execution_receipt
    reserved_path = _safe_str(reserved.get("path")).strip()
    reserved_file = Path(reserved_path) if reserved_path else None
    return {
        "operation": "lab.execution.run",
        "phase": "prewrite",
        "enabled": False,
        "performed": False,
        "would_write_path": reserved_path,
        "would_use_temp_path": str(reserved_file.with_suffix(reserved_file.suffix + ".tmp")) if reserved_file else "",
        "writer_contract_hash": writer_contract_hash,
        "result_status": "prewritten",
        "writes_reserved_execution_receipt": False,
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_execution_receipt_writer_final_write_operation(
    *,
    prewrite_binding: LabExecutionReceiptPrewriteBinding,
    writer_contract_hash: str,
) -> dict[str, Any]:
    reserved = prewrite_binding.reserved_execution_receipt
    reserved_path = _safe_str(reserved.get("path")).strip()
    reserved_file = Path(reserved_path) if reserved_path else None
    return {
        "operation": "lab.execution.run",
        "phase": "finalize",
        "enabled": False,
        "performed": False,
        "would_write_path": reserved_path,
        "would_use_temp_path": str(reserved_file.with_suffix(reserved_file.suffix + ".tmp")) if reserved_file else "",
        "writer_contract_hash": writer_contract_hash,
        "terminal_result_statuses": ["validated", "failed", "refused", "blocked"],
        "writes_reserved_execution_receipt": False,
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_execution_receipt_writer_required_checks() -> list[str]:
    return [
        "prewrite_binding_present",
        "prewrite_binding_contract_bound",
        "receipt_schema_bound",
        "prewrite_contract_bound",
        "final_write_contract_bound",
        "reserved_execution_receipt_id_present",
        "reserved_execution_receipt_path_present",
        "reserved_execution_receipt_path_within_sink",
        "reserved_execution_receipt_not_written",
        "writer_boundary_declared",
        "writer_contract_hash_present",
        "atomic_write_plan_declared",
        "redaction_policy_bound",
        "prewrite_operation_declared",
        "final_write_operation_declared",
        "writer_implementation_bound",
        "prewrite_writer_bound",
        "final_writer_bound",
        "approval_not_consumed",
        "execution_authority_absent",
        "commands_not_executed",
    ]


def _lab_execution_receipt_writer_current_checks(
    *,
    prewrite_binding: LabExecutionReceiptPrewriteBinding,
    writer_boundary: dict[str, Any],
    writer_contract_hash: str,
    prewrite_operation: dict[str, Any],
    final_write_operation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "prewrite_binding_present": True,
        "prewrite_binding_contract_bound": bool(prewrite_binding.contract_binding),
        "receipt_schema_bound": bool(prewrite_binding.receipt_schema_bound),
        "prewrite_contract_bound": bool(prewrite_binding.prewrite_contract_bound),
        "final_write_contract_bound": bool(prewrite_binding.final_write_contract_bound),
        "reserved_execution_receipt_id_present": bool(
            _safe_str(writer_boundary.get("reserved_execution_receipt_id")).strip()
        ),
        "reserved_execution_receipt_path_present": bool(
            _safe_str(writer_boundary.get("reserved_execution_receipt_path")).strip()
        ),
        "reserved_execution_receipt_path_within_sink": bool(writer_boundary.get("reserved_path_within_sink")),
        "reserved_execution_receipt_not_written": bool(writer_boundary.get("reserved_receipt_not_written")),
        "writer_boundary_declared": True,
        "writer_contract_hash_present": bool(writer_contract_hash),
        "atomic_write_plan_declared": writer_boundary.get("atomic_write_strategy") == "write_tmp_then_replace",
        "redaction_policy_bound": bool(writer_boundary.get("redaction_required"))
        and not bool(writer_boundary.get("store_sensitive_values")),
        "prewrite_operation_declared": bool(prewrite_operation) and prewrite_operation.get("phase") == "prewrite",
        "final_write_operation_declared": bool(final_write_operation)
        and final_write_operation.get("phase") == "finalize",
        "writer_implementation_bound": False,
        "prewrite_writer_bound": False,
        "final_writer_bound": False,
        "approval_not_consumed": not bool(prewrite_binding.approval_consumed),
        "execution_authority_absent": not bool(prewrite_binding.execution_authority),
        "commands_not_executed": not bool(prewrite_binding.executed),
        "approval_consumed": False,
        "execution_authority": False,
        "executed": False,
    }


def _lab_synthetic_execution_receipt_approval_blockers(
    writer_preflight: LabExecutionReceiptWriterPreflight,
) -> list[str]:
    blockers = set(writer_preflight.blockers) | set(writer_preflight.upstream_blockers)
    approval_blockers = [
        blocker
        for blocker in blockers
        if blocker.startswith("approval_record_")
        or blocker
        in {
            "approval_not_approved",
            "approval_rejected",
            "approval_emergency_path_not_supported",
            "approval_action_mismatch",
            "approval_exact_action_mismatch",
            "approval_already_consumed",
        }
    ]
    return sorted(approval_blockers)


def _lab_synthetic_execution_receipt(
    *,
    writer_preflight: LabExecutionReceiptWriterPreflight,
    prewrite_binding: LabExecutionReceiptPrewriteBinding,
    actor: str,
    phase: str,
    status: str,
    result_status: str,
    created_at: str,
    updated_at: str,
    finalized_at: str,
    warnings: list[str],
    validation_performed: list[str],
) -> LabSyntheticExecutionReceipt:
    reserved = writer_preflight.reserved_execution_receipt
    return LabSyntheticExecutionReceipt(
        id=_safe_str(reserved.get("id")).strip(),
        operation="lab.execution.run",
        schema_version=1,
        mode="synthetic_noop_execution_receipt",
        phase=phase,
        status=status,
        result_status=result_status,
        created_at=created_at,
        updated_at=updated_at,
        approval_id=writer_preflight.approval_id,
        writer_preflight_id=writer_preflight.id,
        receipt_prewrite_binding_id=prewrite_binding.id,
        receipt_write_readiness_id=writer_preflight.receipt_write_readiness_id,
        receipt_sink_reservation_id=writer_preflight.receipt_sink_reservation_id,
        preflight_id=writer_preflight.preflight_id,
        plan_id=writer_preflight.plan_id,
        workspace_id=writer_preflight.workspace_id,
        source_id=writer_preflight.source_id,
        candidate_id=writer_preflight.candidate_id,
        candidate_name=writer_preflight.candidate_name,
        actor=_safe_str(actor).strip() or "francis/system",
        action=writer_preflight.action,
        action_hash=writer_preflight.action_hash,
        finalized_at=finalized_at,
        reserved_execution_receipt=reserved,
        writer_boundary=writer_preflight.writer_boundary,
        writer_contract=writer_preflight.writer_contract,
        synthetic=True,
        noop=True,
        prewritten=True,
        finalized=bool(finalized_at),
        approval_consumed=False,
        execution_authority=False,
        executed=False,
        ran_repo_scripts=False,
        ran_install=False,
        ran_build=False,
        ran_tests=False,
        network_accessed=False,
        wrote_to_repo=False,
        repo_code_executed=False,
        store_file_contents=False,
        store_sensitive_values=False,
        warnings=warnings,
        errors=[],
        validation_performed=validation_performed,
        receipts=[],
    )


def _write_lab_execution_receipt_artifact(execution_receipt: LabSyntheticExecutionReceipt) -> Path:
    return write_ingest_record_artifact(
        "lab_execution_receipts",
        execution_receipt.id,
        {"execution_receipt": execution_receipt.to_dict()},
    )


def _lab_plan_blockers(permission: LabPermissionRequirement, boundary: Any) -> list[str]:
    blockers: list[str] = []
    if permission.execute or permission.write or permission.network or permission.destructive:
        blockers.extend(
            [
                "explicit_operator_permission_not_granted",
                "francis_lab_runner_not_implemented",
                "execution_receipt_runner_binding_missing",
            ]
        )
    if permission.sandbox_required:
        blockers.append("sandboxed_workspace_not_available")
    if permission.execute and not bool(getattr(boundary, "supports_unknown_repo_execution", False)):
        blockers.append("unknown_repo_execution_not_supported")
    if (permission.execute or permission.network) and not bool(getattr(boundary, "supports_network_isolation", False)):
        blockers.append("network_isolation_not_available")
    if (permission.write or permission.destructive) and not bool(
        getattr(boundary, "supports_filesystem_write_isolation", False)
    ):
        blockers.append("filesystem_write_boundary_not_available")
    if permission.destructive:
        blockers.append("destructive_action_blocked")
    return _append_unique([], *blockers)


def _no_lab_execution_payload(*, reason: str = "plan_only_boundary") -> dict[str, Any]:
    return {
        "executed": False,
        "execution_authority": False,
        "ran_repo_scripts": False,
        "ran_install": False,
        "ran_build": False,
        "ran_tests": False,
        "network_accessed": False,
        "wrote_to_repo": False,
        "reason": reason,
        "lab_boundary": current_lab_boundary().to_dict(),
    }


def _lab_noop_runner_execution_payload(*, noop_performed: bool, reason: str) -> dict[str, Any]:
    payload = _no_lab_execution_payload(reason=reason)
    payload.update(
        {
            "builtin_noop_runner_envelope": True,
            "builtin_noop_performed": bool(noop_performed),
            "commands_executed": False,
            "repo_code_executed": False,
            "store_file_contents": False,
            "store_sensitive_values": False,
        }
    )
    return payload


def _lab_noop_runner_transcript_execution_payload(*, transcript_captured: bool, reason: str) -> dict[str, Any]:
    payload = _lab_noop_runner_execution_payload(noop_performed=transcript_captured, reason=reason)
    payload.update(
        {
            "builtin_noop_runner_transcript": True,
            "builtin_noop_output_captured": bool(transcript_captured),
            "real_process_output_captured": False,
            "stdout_content_stored": False,
            "stderr_content_stored": False,
            "output_content_stored": False,
        }
    )
    return payload


def _lab_noop_runner_identity_binding_execution_payload(*, identity_bound: bool, reason: str) -> dict[str, Any]:
    payload = _lab_noop_runner_transcript_execution_payload(transcript_captured=identity_bound, reason=reason)
    payload.update(
        {
            "builtin_noop_runner_identity_binding": True,
            "builtin_noop_runner_identity_bound": bool(identity_bound),
            "live_runner_bound": False,
            "sandbox_runner_bound": False,
            "candidate_validated": False,
            "capability_promoted": False,
        }
    )
    return payload


def _lab_source_mount_readiness_execution_payload(
    *,
    recorded: bool,
    identity_bound: bool,
    source_reference_ready: bool,
    ready: bool,
    reason: str,
) -> dict[str, Any]:
    payload = _lab_noop_runner_identity_binding_execution_payload(
        identity_bound=identity_bound,
        reason=reason,
    )
    payload.update(
        {
            "source_mount_readiness_recorded": bool(recorded),
            "source_mount_ready": bool(ready),
            "source_reference_ready": bool(source_reference_ready),
            "source_mount_mode": "reference_only_read_only",
            "read_only_mount_bound": False,
            "source_mount_enforced": False,
            "source_copied": False,
            "source_write_allowed": False,
            "candidate_validated": False,
            "capability_promoted": False,
        }
    )
    return payload


def _lab_source_mount_contract_execution_payload(
    *,
    recorded: bool,
    identity_bound: bool,
    source_reference_ready: bool,
    readiness_ready: bool,
    contract_declared: bool,
    reason: str,
) -> dict[str, Any]:
    payload = _lab_source_mount_readiness_execution_payload(
        recorded=readiness_ready,
        identity_bound=identity_bound,
        source_reference_ready=source_reference_ready,
        ready=readiness_ready,
        reason=reason,
    )
    payload.update(
        {
            "source_mount_contract_recorded": bool(recorded),
            "source_mount_contract_declared": bool(contract_declared),
            "source_mount_contract_mode": "contract_only_no_live_mount",
            "future_mount_mode": "future_read_only_source_mount",
            "live_mount_bound": False,
            "mount_enforced": False,
            "read_only_mount_bound": False,
            "source_mount_enforced": False,
            "source_copied": False,
            "source_write_allowed": False,
            "executed": False,
            "execution_authority": False,
            "repo_code_executed": False,
            "commands_executed": False,
            "network_accessed": False,
            "wrote_to_repo": False,
            "candidate_validated": False,
            "capability_promoted": False,
        }
    )
    return payload


def _lab_run_boundary_execution_payload(*, recorded: bool, ready: bool, reason: str) -> dict[str, Any]:
    payload = _no_lab_execution_payload(reason=reason)
    payload.update(
        {
            "run_boundary_preflight_recorded": bool(recorded),
            "run_boundary_ready": bool(ready),
            "run_mode": "future_sandboxed_rebuild_run_test",
            "source_mount_contract_required": True,
            "read_only_mount_bound": False,
            "source_mount_enforced": False,
            "sandbox_bound": False,
            "sandbox_enforced": False,
            "runner_bound": False,
            "command_allowlist_enforced": False,
            "execution_receipt_writer_bound": False,
            "approval_consumed": False,
            "executed": False,
            "commands_executed": False,
            "repo_code_executed": False,
            "candidate_validated": False,
            "capability_promoted": False,
        }
    )
    return payload


def _lab_sandboxed_rebuild_run_test_execution_payload(*, recorded: bool, ready: bool, reason: str) -> dict[str, Any]:
    payload = _lab_run_boundary_execution_payload(recorded=recorded, ready=ready, reason=reason)
    payload.update(
        {
            "sandboxed_rebuild_run_test_boundary_recorded": bool(recorded),
            "sandboxed_rebuild_run_test_boundary_ready": bool(ready),
            "run_mode": "future_sandboxed_rebuild_run_test",
            "provider_runtime_probe_runner_control_binding_required": True,
            "provider_runtime_probe_runner_control_binding_recorded": bool(recorded),
            "provider_runtime_probe_runner_control_binding_ready": False,
            "execution_approval_required": True,
            "execution_approval_consumed": False,
            "process_launched": False,
            "container_launched": False,
            "commands_executed": False,
            "repo_code_executed": False,
            "ran_install": False,
            "ran_build": False,
            "ran_tests": False,
            "network_accessed": False,
            "wrote_to_repo": False,
            "execution_receipt_written": False,
            "candidate_validated": False,
            "capability_promoted": False,
        }
    )
    return payload


def _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
    *,
    recorded: bool,
    ready: bool,
    reason: str,
) -> dict[str, Any]:
    payload = _no_lab_execution_payload(reason=reason)
    payload.update(
        {
            "provider_runtime_probe_execution_boundary_recorded": bool(recorded),
            "provider_runtime_probe_execution_boundary_ready": bool(ready),
            "provider_runtime_probe_performed": False,
            "provider_binary_executed": False,
            "provider_service_queried": False,
            "process_launched": False,
            "container_launched": False,
            "sandbox_provider_bound": False,
            "sandbox_bound": False,
            "sandbox_enforced": False,
            "execution_receipt_written": False,
            "approval_consumed": False,
            "execution_authority": False,
            "executed": False,
            "commands_executed": False,
            "repo_code_executed": False,
            "network_accessed": False,
            "wrote_to_repo": False,
            "candidate_validated": False,
            "capability_promoted": False,
        }
    )
    return payload


class LabIngestService:
    def plan_lab(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        record = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(record, candidate_ref, actor=actor)
        if candidate is None:
            receipt, receipt_path = self.receipts.write(
                operation="lab.plan",
                source_id=record.id,
                actor=actor,
                input_paths=[record.canonical_path],
                input_hashes=[record.fingerprint],
                result_status="failed",
                errors=["capability_candidate_not_found"],
                validation_performed=["candidate_registry_lookup_no_execution"],
            )
            updated = replace(record, receipts=_append_unique(record.receipts, str(receipt_path)))
            self.sources.upsert(updated)
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_not_found",
                    "source": updated.to_dict(),
                    "receipt": receipt.to_dict(),
                    "receipt_path": str(receipt_path),
                    "execution": _no_lab_execution_payload(),
                }
            )

        permission = LabPermissionRequirement.from_candidate_permissions(candidate.permissions_required)
        boundary = current_lab_boundary()
        blockers = _lab_plan_blockers(permission, boundary)
        status = "blocked" if blockers else "planned"
        now = utc_now()
        plan = LabPlan(
            id=_lab_plan_id(record.id, candidate.id),
            source_id=record.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            permissions_required=permission,
            suggested_commands=list(candidate.suggested_validation),
            blockers=blockers,
            workspace={
                "created": False,
                "path": "",
                "mode": "plan_only",
                "source_copied": False,
                "writes_allowed": False,
            },
            boundary=boundary.to_dict(),
            execution_authority=False,
            executed=False,
            promotion_requirements=[
                "operator_review",
                "sandboxed_workspace",
                "network_blocking_policy",
                "filesystem_write_boundary",
                "execution_receipt_binding",
            ],
        )
        artifact_path = write_ingest_record_artifact("lab_plans", plan.id, {"plan": plan.to_dict()})
        receipt, receipt_path = self.receipts.write(
            operation="lab.plan",
            source_id=record.id,
            actor=actor,
            input_paths=[record.canonical_path],
            input_hashes=[record.fingerprint],
            result_status=status,
            errors=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "candidate_registry_lookup_no_execution",
                "permission_requirement_projection",
                "lab_boundary_preflight_no_execution",
            ],
        )
        plan = replace(plan, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact("lab_plans", plan.id, {"plan": plan.to_dict()})
        candidate_receipts = _append_unique(candidate.receipts, str(receipt_path))
        self._replace_candidate(record.id, candidate.id, replace(candidate, receipts=candidate_receipts))
        metadata = {
            **record.metadata,
            "last_lab_plan_path": str(artifact_path),
            "last_lab_plan_receipt_path": str(receipt_path),
            "last_lab_plan_status": status,
            "last_lab_plan_candidate_id": candidate.id,
            "last_lab_plan_candidate_name": candidate.name,
        }
        updated = replace(
            record,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(record.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(record.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "candidate": replace(candidate, receipts=candidate_receipts).to_dict(),
                "plan": plan.to_dict(),
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(),
            }
        )

    def prepare_lab_workspace(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        plan_result = self.plan_lab(source_or_path, candidate_ref, actor=actor)
        plan = LabPlan.from_dict(plan_result.get("plan"))
        source = SourceRecord.from_dict(plan_result.get("source"))
        if plan is None or source is None:
            return _display_payload(
                {
                    **plan_result,
                    "status": "failed",
                    "error": "lab_plan_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_plan_unavailable"),
                }
            )

        workspace_id = _lab_workspace_id(plan.id)
        workspace_root = lab_workspace_root(workspace_id)
        workspace_root.mkdir(parents=True, exist_ok=True)
        for child in ("work", "artifacts", "logs", "tmp"):
            (workspace_root / child).mkdir(exist_ok=True)

        blocker_list = _append_unique(
            plan.blockers,
            "lab_runner_not_bound",
            "approval_consumption_not_implemented",
            "source_copy_not_performed",
        )
        now = utc_now()
        workspace = LabWorkspaceRecord(
            id=workspace_id,
            plan_id=plan.id,
            source_id=source.id,
            candidate_id=plan.candidate_id,
            candidate_name=plan.candidate_name,
            status="prepared",
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            path=str(workspace_root),
            manifest_path=str(workspace_root / "workspace_manifest.json"),
            source_reference={
                "source_id": source.id,
                "canonical_path": source.canonical_path,
                "fingerprint": source.fingerprint,
                "mode": "reference_only_read_only",
                "contents_copied": False,
            },
            workspace_policy={
                "execution_enabled": False,
                "runner_bound": False,
                "network_enabled": False,
                "network_isolation_enforced": False,
                "source_copy_allowed": False,
                "source_write_allowed": False,
                "workspace_write_root": str(workspace_root),
                "allowed_write_subdirs": ["artifacts", "logs", "tmp", "work"],
            },
            preflight={
                "plan_status": plan.status,
                "read_only_workspace_ready": True,
                "execution_ready": False,
                "approval_required": plan.permissions_required.explicit_operator_permission,
                "approval_scope": plan.permissions_required.approval_scope,
                "blockers": blocker_list,
            },
            source_copied=False,
            execution_authority=False,
            executed=False,
        )
        manifest_payload = {"workspace": workspace.to_dict()}
        Path(workspace.manifest_path).write_text(
            json.dumps(_display_payload(manifest_payload), indent=2, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        artifact_path = write_ingest_record_artifact("lab_workspaces", workspace.id, manifest_payload)
        receipt, receipt_path = self.receipts.write(
            operation="lab.workspace.prepare",
            source_id=source.id,
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[source.fingerprint],
            result_status="prepared",
            warnings=blocker_list,
            generated_artifact_paths=[str(artifact_path), workspace.manifest_path],
            validation_performed=[
                "lab_plan_readback_no_execution",
                "empty_workspace_directory_created",
                "source_reference_recorded_no_copy",
                "runner_binding_absent_execution_blocked",
            ],
        )
        workspace = replace(workspace, receipts=[str(receipt_path)])
        manifest_payload = {"workspace": workspace.to_dict()}
        Path(workspace.manifest_path).write_text(
            json.dumps(_display_payload(manifest_payload), indent=2, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        artifact_path = write_ingest_record_artifact("lab_workspaces", workspace.id, manifest_payload)
        metadata = {
            **source.metadata,
            "last_lab_workspace_path": str(workspace_root),
            "last_lab_workspace_manifest_path": workspace.manifest_path,
            "last_lab_workspace_artifact_path": str(artifact_path),
            "last_lab_workspace_receipt_path": str(receipt_path),
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path), workspace.manifest_path),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": "prepared",
                "source": updated.to_dict(),
                "plan": plan.to_dict(),
                "workspace": workspace.to_dict(),
                "artifact_path": str(artifact_path),
                "manifest_path": workspace.manifest_path,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="workspace_prepared_without_runner"),
            }
        )

    def preflight_lab_execution(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        workspace_result = self.prepare_lab_workspace(source_or_path, candidate_ref, actor=actor)
        plan = LabPlan.from_dict(workspace_result.get("plan"))
        workspace = LabWorkspaceRecord.from_dict(workspace_result.get("workspace"))
        source = SourceRecord.from_dict(workspace_result.get("source"))
        if plan is None or workspace is None or source is None:
            return _display_payload(
                {
                    **workspace_result,
                    "status": "failed",
                    "error": "lab_workspace_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_workspace_unavailable"),
                }
            )

        exact_action = _lab_exact_action_payload(source=source, plan=plan, workspace=workspace)
        action_hash = _stable_payload_hash(exact_action)
        blockers = _append_unique(
            plan.blockers,
            *workspace.preflight.get("blockers", []),
            "approval_artifact_not_created",
            "approval_consumption_not_implemented",
            "runner_binding_absent",
        )
        status = (
            "blocked"
            if blockers
            else "needs_approval"
            if plan.permissions_required.explicit_operator_permission
            else "ready"
        )
        now = utc_now()
        preflight = LabExecutionPreflight(
            id=_lab_preflight_id(plan.id, workspace.id),
            plan_id=plan.id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=plan.candidate_id,
            candidate_name=plan.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            approval={
                "required": plan.permissions_required.explicit_operator_permission,
                "gate": "approvals_gate" if plan.permissions_required.explicit_operator_permission else "not_required",
                "scope": plan.permissions_required.approval_scope,
                "action": "francis.lab.execute",
                "action_hash": action_hash,
                "approval_id": "",
                "approval_created": False,
                "approval_consumed": False,
                "next_step": "build_governed_lab_runner_and_exact_action_approval_request",
            },
            exact_action=exact_action,
            action_hash=action_hash,
            readiness={
                "execution_ready": False,
                "workspace_ready": True,
                "source_copied": workspace.source_copied,
                "runner_bound": bool(workspace.workspace_policy.get("runner_bound")),
                "network_isolation_enforced": bool(workspace.workspace_policy.get("network_isolation_enforced")),
                "filesystem_write_boundary_enforced": False,
                "resource_limits_enforced": False,
                "approval_consumption_ready": False,
                "result": "blocked",
            },
            blockers=blockers,
            execution_authority=False,
            executed=False,
        )
        artifact_path = write_ingest_record_artifact("lab_preflights", preflight.id, {"preflight": preflight.to_dict()})
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[source.fingerprint, action_hash],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "lab_workspace_readback_no_execution",
                "exact_action_hash_created",
                "approval_requirement_projected_no_approval_created",
                "runner_absence_blocks_execution",
            ],
        )
        preflight = replace(preflight, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact("lab_preflights", preflight.id, {"preflight": preflight.to_dict()})
        metadata = {
            **source.metadata,
            "last_lab_execution_preflight_path": str(artifact_path),
            "last_lab_execution_preflight_receipt_path": str(receipt_path),
            "last_lab_execution_preflight_status": status,
            "last_lab_execution_action_hash": action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "plan": plan.to_dict(),
                "workspace": workspace.to_dict(),
                "preflight": preflight.to_dict(),
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="preflight_blocked_no_runner"),
            }
        )

    def request_lab_execution_approval(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        actor: str = "francis/system",
        reason: str = "francis_lab_execution_requested",
    ) -> dict[str, Any]:
        preflight_result = self.preflight_lab_execution(source_or_path, candidate_ref, actor=actor)
        preflight = LabExecutionPreflight.from_dict(preflight_result.get("preflight"))
        source = SourceRecord.from_dict(preflight_result.get("source"))
        if preflight is None or source is None:
            return _display_payload(
                {
                    **preflight_result,
                    "status": "failed",
                    "error": "lab_preflight_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_preflight_unavailable"),
                }
            )

        approval_payload = _display_payload(
            {
                "action": "francis.lab.execute",
                "action_hash": preflight.action_hash,
                "exact_action": preflight.exact_action,
                "preflight_id": preflight.id,
                "plan_id": preflight.plan_id,
                "workspace_id": preflight.workspace_id,
                "source_id": preflight.source_id,
                "candidate_id": preflight.candidate_id,
                "candidate_name": preflight.candidate_name,
                "readiness": {
                    "execution_ready": False,
                    "preflight_status": preflight.status,
                    "blockers": preflight.blockers,
                },
                "governance": {
                    "approval_scope": _safe_str(preflight.approval.get("scope")).strip(),
                    "approval_consumed": False,
                    "execution_authority": False,
                    "runner_bound": False,
                },
            }
        )
        approval = approvals.request(
            action="francis.lab.execute",
            reason=reason.strip() or "francis_lab_execution_requested",
            payload=approval_payload,
        )
        approval_id = _safe_str(approval.get("id")).strip()
        approval_path = approvals.pending_dir() / f"{approval_id}.json" if approval_id else Path("")
        now = utc_now()
        request_record = LabApprovalRequestRecord(
            id=_lab_approval_request_id(preflight.id, approval_id),
            approval_id=approval_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=preflight.workspace_id,
            source_id=preflight.source_id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status="needs_approval",
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            approval_path=str(approval_path) if approval_id else "",
            approval_payload=approval_payload,
            approval_created=bool(approval_id),
            approval_consumed=False,
            execution_authority=False,
            executed=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_approval_requests", request_record.id, {"approval_request": request_record.to_dict()}
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.approval_request",
            source_id=source.id,
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status="needs_approval",
            warnings=preflight.blockers,
            generated_artifact_paths=[str(artifact_path), str(approval_path) if approval_id else ""],
            validation_performed=[
                "lab_execution_preflight_readback_no_execution",
                "exact_action_approval_request_created",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        request_record = replace(request_record, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_approval_requests", request_record.id, {"approval_request": request_record.to_dict()}
        )
        metadata = {
            **source.metadata,
            "last_lab_approval_request_path": str(artifact_path),
            "last_lab_approval_request_receipt_path": str(receipt_path),
            "last_lab_approval_id": approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": "needs_approval",
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "approval_request": request_record.to_dict(),
                "approval": approval,
                "approval_path": str(approval_path) if approval_id else "",
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="approval_requested_no_execution"),
            }
        )

    def preflight_lab_runner_readiness(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        approval_id: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        preflight_result = self.preflight_lab_execution(source_or_path, candidate_ref, actor=actor)
        preflight = LabExecutionPreflight.from_dict(preflight_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(preflight_result.get("workspace"))
        source = SourceRecord.from_dict(preflight_result.get("source"))
        if preflight is None or workspace is None or source is None:
            return _display_payload(
                {
                    **preflight_result,
                    "status": "failed",
                    "error": "lab_preflight_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_preflight_unavailable"),
                }
            )

        approval_status = "not_provided"
        approval_record: dict[str, Any] = {}
        approval_path: Path | None = None
        if clean_approval_id:
            approval_status, approval_record, approval_path = _read_lab_approval_record(clean_approval_id)
            binding, approval_blockers = _lab_approval_binding(
                preflight=preflight,
                approval_id=clean_approval_id,
                approval_status=approval_status,
                approval_record=approval_record,
                approval_path=approval_path,
            )
        else:
            binding = {
                "approval_id": "",
                "approval_status": approval_status,
                "approval_path": "",
                "approval_record_found": False,
                "approval_approved": False,
                "exact_match": False,
                "refused": False,
                "approval_consumed": False,
                "execution_authority": False,
            }
            approval_blockers = ["approval_id_not_provided"]

        required_controls = _lab_runner_readiness_required_controls()
        current_controls = _lab_runner_readiness_current_controls(
            workspace=workspace,
            preflight=preflight,
            binding=binding,
        )
        missing_controls = [control for control in required_controls if not bool(current_controls.get(control))]
        blockers = _append_unique(
            preflight.blockers,
            *approval_blockers,
            *missing_controls,
            "runner_readiness_blocked",
        )
        status = "ready" if not blockers else "blocked"
        now = utc_now()
        readiness = LabRunnerReadiness(
            id=_lab_runner_readiness_id(preflight.id, clean_approval_id),
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            approval_id=clean_approval_id,
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            runner_kind="francis.lab.runner",
            sandbox={
                "workspace_path": workspace.path,
                "manifest_path": workspace.manifest_path,
                "source_reference_mode": _safe_str(workspace.source_reference.get("mode")).strip(),
                "source_copied": workspace.source_copied,
                "execution_enabled": bool(workspace.workspace_policy.get("execution_enabled")),
                "runner_bound": bool(workspace.workspace_policy.get("runner_bound")),
                "network_enabled": bool(workspace.workspace_policy.get("network_enabled")),
                "allowed_write_subdirs": list(workspace.workspace_policy.get("allowed_write_subdirs") or []),
            },
            required_controls=required_controls,
            current_controls=current_controls,
            missing_controls=missing_controls,
            blockers=blockers,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runner_readiness",
            readiness.id,
            {"runner_readiness": readiness.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.readiness.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [source.canonical_path, workspace.manifest_path],
                str(approval_path) if approval_path is not None else "",
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "lab_execution_preflight_readback_no_execution",
                "workspace_manifest_readback_no_source_copy",
                "approval_record_readback_no_consumption",
                "runner_sandbox_control_projection",
                "execution_authority_not_granted",
            ],
        )
        readiness = replace(readiness, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runner_readiness",
            readiness.id,
            {"runner_readiness": readiness.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runner_readiness_path": str(artifact_path),
            "last_lab_runner_readiness_receipt_path": str(receipt_path),
            "last_lab_runner_readiness_status": status,
            "last_lab_runner_missing_controls": missing_controls,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": _lab_approval_snapshot(approval_record),
                "approval_path": str(approval_path) if approval_path is not None else "",
                "approval_binding": binding,
                "runner_readiness": readiness.to_dict(),
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="runner_readiness_preflight_no_execution"),
            }
        )

    def preflight_lab_runner_binding(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        approval_id: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        readiness_result = self.preflight_lab_runner_readiness(
            source_or_path,
            candidate_ref,
            approval_id=clean_approval_id,
            actor=actor,
        )
        readiness = LabRunnerReadiness.from_dict(readiness_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(readiness_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(readiness_result.get("workspace"))
        source = SourceRecord.from_dict(readiness_result.get("source"))
        if readiness is None or preflight is None or workspace is None or source is None:
            return _display_payload(
                {
                    **readiness_result,
                    "status": "failed",
                    "error": "lab_runner_readiness_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_runner_readiness_unavailable"),
                }
            )

        runner_binding = _lab_runner_binding_contract(
            readiness=readiness,
            preflight=preflight,
            workspace=workspace,
        )
        execution_receipt_sink = _lab_execution_receipt_sink_contract()
        required_controls = _lab_runner_binding_required_controls()
        current_controls = _lab_runner_binding_current_controls(
            readiness=readiness,
            runner_binding=runner_binding,
            execution_receipt_sink=execution_receipt_sink,
        )
        missing_controls = [control for control in required_controls if not bool(current_controls.get(control))]
        blockers = _append_unique(
            readiness.blockers,
            *missing_controls,
            "runner_binding_preflight_blocked",
        )
        status = "ready" if not blockers else "blocked"
        now = utc_now()
        binding_preflight = LabRunnerBindingPreflight(
            id=_lab_runner_binding_preflight_id(readiness.id, clean_approval_id),
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            approval_id=clean_approval_id,
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            runner_binding=runner_binding,
            execution_receipt_sink=execution_receipt_sink,
            required_controls=required_controls,
            current_controls=current_controls,
            missing_controls=missing_controls,
            blockers=blockers,
            approval_consumed=False,
            runner_bound=False,
            receipt_sink_bound=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runner_bindings",
            binding_preflight.id,
            {"runner_binding": binding_preflight.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.binding.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(readiness_result.get("artifact_path")).strip(),
                ],
                _safe_str(readiness_result.get("approval_path")).strip(),
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "runner_readiness_readback_no_execution",
                "runner_binding_contract_projected_no_execution",
                "execution_receipt_sink_contract_projected_no_execution",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        binding_preflight = replace(binding_preflight, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runner_bindings",
            binding_preflight.id,
            {"runner_binding": binding_preflight.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runner_binding_path": str(artifact_path),
            "last_lab_runner_binding_receipt_path": str(receipt_path),
            "last_lab_runner_binding_status": status,
            "last_lab_runner_binding_missing_controls": missing_controls,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": readiness_result.get("approval") or {},
                "approval_path": _safe_str(readiness_result.get("approval_path")).strip(),
                "approval_binding": readiness_result.get("approval_binding") or {},
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "artifact_path": str(artifact_path),
                "runner_binding_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="runner_binding_preflight_no_execution"),
            }
        )

    def preflight_lab_runner_enforcement(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        approval_id: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        binding_result = self.preflight_lab_runner_binding(
            source_or_path,
            candidate_ref,
            approval_id=clean_approval_id,
            actor=actor,
        )
        binding_preflight = LabRunnerBindingPreflight.from_dict(binding_result.get("runner_binding"))
        readiness = LabRunnerReadiness.from_dict(binding_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(binding_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(binding_result.get("workspace"))
        source = SourceRecord.from_dict(binding_result.get("source"))
        if binding_preflight is None or readiness is None or preflight is None or workspace is None or source is None:
            return _display_payload(
                {
                    **binding_result,
                    "status": "failed",
                    "error": "lab_runner_binding_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_runner_binding_unavailable"),
                }
            )

        enforcement_interface = _lab_runner_enforcement_interface(
            binding_preflight=binding_preflight,
            workspace=workspace,
        )
        required_checks = _lab_runner_enforcement_required_checks()
        current_checks = _lab_runner_enforcement_current_checks(
            binding_preflight=binding_preflight,
            readiness=readiness,
            preflight=preflight,
            workspace=workspace,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(
            binding_preflight.blockers,
            *missing_checks,
            "runner_enforcement_preflight_blocked",
        )
        status = "ready" if not blockers else "blocked"
        now = utc_now()
        enforcement = LabRunnerEnforcementPreflight(
            id=_lab_runner_enforcement_preflight_id(binding_preflight.id, clean_approval_id),
            runner_binding_id=binding_preflight.id,
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            approval_id=clean_approval_id,
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            enforcement_interface=enforcement_interface,
            runner_binding=binding_preflight.runner_binding,
            execution_receipt_sink=binding_preflight.execution_receipt_sink,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            approval_consumed=False,
            runner_bound=False,
            receipt_sink_bound=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runner_enforcement_preflights",
            enforcement.id,
            {"runner_enforcement": enforcement.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.enforcement.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(binding_result.get("runner_binding_path")).strip(),
                ],
                _safe_str(binding_result.get("approval_path")).strip(),
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "runner_binding_readback_no_execution",
                "runner_enforcement_interface_projected_no_execution",
                "runner_identity_not_verified",
                "runner_policies_not_enforced",
                "execution_receipt_sink_not_bound",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        enforcement = replace(enforcement, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runner_enforcement_preflights",
            enforcement.id,
            {"runner_enforcement": enforcement.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runner_enforcement_path": str(artifact_path),
            "last_lab_runner_enforcement_receipt_path": str(receipt_path),
            "last_lab_runner_enforcement_status": status,
            "last_lab_runner_enforcement_missing_checks": missing_checks,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": binding_result.get("approval") or {},
                "approval_path": _safe_str(binding_result.get("approval_path")).strip(),
                "approval_binding": binding_result.get("approval_binding") or {},
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "runner_enforcement": enforcement.to_dict(),
                "artifact_path": str(artifact_path),
                "runner_enforcement_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="runner_enforcement_preflight_no_execution"),
            }
        )

    def preflight_lab_approval_consumption_handoff(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        enforcement_result = self.preflight_lab_runner_enforcement(
            source_or_path,
            candidate_ref,
            approval_id=clean_approval_id,
            actor=actor,
        )
        enforcement = LabRunnerEnforcementPreflight.from_dict(enforcement_result.get("runner_enforcement"))
        binding_preflight = LabRunnerBindingPreflight.from_dict(enforcement_result.get("runner_binding"))
        readiness = LabRunnerReadiness.from_dict(enforcement_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(enforcement_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(enforcement_result.get("workspace"))
        source = SourceRecord.from_dict(enforcement_result.get("source"))
        if (
            enforcement is None
            or binding_preflight is None
            or readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **enforcement_result,
                    "status": "failed",
                    "error": "lab_runner_enforcement_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_runner_enforcement_unavailable"),
                }
            )

        approval_status, approval_record, approval_path = _read_lab_approval_record(clean_approval_id)
        approval_binding, approval_blockers = _lab_approval_binding(
            preflight=preflight,
            approval_id=clean_approval_id,
            approval_status=approval_status,
            approval_record=approval_record,
            approval_path=approval_path,
        )
        required_checks = _lab_approval_consumption_handoff_required_checks()
        current_checks = _lab_approval_consumption_handoff_current_checks(
            approval_id=clean_approval_id,
            approval_status=approval_status,
            approval_binding=approval_binding,
            enforcement=enforcement,
            binding_preflight=binding_preflight,
            readiness=readiness,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = bool(approval_binding.get("refused"))
        blockers = _append_unique(
            approval_blockers,
            *missing_checks,
            "approval_consumption_handoff_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        handoff = LabApprovalConsumptionHandoff(
            id=_lab_approval_consumption_handoff_id(enforcement.id, clean_approval_id),
            approval_id=clean_approval_id,
            runner_enforcement_id=enforcement.id,
            runner_binding_id=binding_preflight.id,
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            approval_status=approval_status,
            approval_path=str(approval_path) if approval_path is not None else "",
            approval_snapshot=_lab_approval_snapshot(approval_record),
            approval_binding=approval_binding,
            handoff_contract=_lab_approval_consumption_handoff_contract(
                enforcement=enforcement,
                approval_id=clean_approval_id,
            ),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_approval_consumption_handoffs",
            handoff.id,
            {"approval_handoff": handoff.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.approval_consumption_handoff",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(enforcement_result.get("runner_enforcement_path")).strip(),
                ],
                str(approval_path) if approval_path is not None else "",
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "runner_enforcement_readback_no_execution",
                "approval_record_readback_no_mutation",
                "exact_action_hash_binding_check",
                "approval_consumption_disabled_until_governed_consumer",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        handoff = replace(handoff, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_approval_consumption_handoffs",
            handoff.id,
            {"approval_handoff": handoff.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_approval_consumption_handoff_path": str(artifact_path),
            "last_lab_approval_consumption_handoff_receipt_path": str(receipt_path),
            "last_lab_approval_consumption_handoff_status": status,
            "last_lab_approval_consumption_handoff_missing_checks": missing_checks,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": _lab_approval_snapshot(approval_record),
                "approval_path": str(approval_path) if approval_path is not None else "",
                "approval_binding": approval_binding,
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "runner_enforcement": enforcement.to_dict(),
                "approval_consumption_handoff": handoff.to_dict(),
                "artifact_path": str(artifact_path),
                "approval_consumption_handoff_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="approval_consumption_handoff_preflight_no_execution"),
            }
        )

    def preflight_lab_execution_receipt_sink_reservation(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        handoff_result = self.preflight_lab_approval_consumption_handoff(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        handoff = LabApprovalConsumptionHandoff.from_dict(handoff_result.get("approval_consumption_handoff"))
        enforcement = LabRunnerEnforcementPreflight.from_dict(handoff_result.get("runner_enforcement"))
        binding_preflight = LabRunnerBindingPreflight.from_dict(handoff_result.get("runner_binding"))
        readiness = LabRunnerReadiness.from_dict(handoff_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(handoff_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(handoff_result.get("workspace"))
        source = SourceRecord.from_dict(handoff_result.get("source"))
        if (
            handoff is None
            or enforcement is None
            or binding_preflight is None
            or readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **handoff_result,
                    "status": "failed",
                    "error": "lab_approval_consumption_handoff_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_approval_consumption_handoff_unavailable"),
                }
            )

        reservation_id = _lab_execution_receipt_sink_reservation_id(handoff.id, clean_approval_id)
        reserved_receipt = _reserved_lab_execution_receipt(
            reservation_id=reservation_id,
            handoff=handoff,
            source=source,
        )
        required_checks = _lab_execution_receipt_sink_reservation_required_checks()
        current_checks = _lab_execution_receipt_sink_reservation_current_checks(
            handoff=handoff,
            enforcement=enforcement,
            binding_preflight=binding_preflight,
            readiness=readiness,
            reserved_receipt=reserved_receipt,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = handoff.status == "refused" or bool(handoff.approval_binding.get("refused"))
        blockers = _append_unique(
            handoff.blockers,
            *missing_checks,
            "execution_receipt_sink_reservation_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        reservation = LabExecutionReceiptSinkReservation(
            id=reservation_id,
            approval_id=clean_approval_id,
            approval_handoff_id=handoff.id,
            runner_enforcement_id=enforcement.id,
            runner_binding_id=binding_preflight.id,
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            receipt_sink=enforcement.execution_receipt_sink,
            reservation_contract=_lab_execution_receipt_sink_reservation_contract(
                handoff=handoff,
                reserved_receipt=reserved_receipt,
            ),
            reserved_execution_receipt=reserved_receipt,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            reservation_created=True,
            prewrite_bound=False,
            final_write_bound=False,
            execution_receipt_written=False,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_execution_receipt_sink_reservations",
            reservation.id,
            {"receipt_sink_reservation": reservation.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.receipt_sink_reservation",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(handoff_result.get("approval_consumption_handoff_path")).strip(),
                ],
                handoff.approval_path,
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "approval_consumption_handoff_readback_no_execution",
                "execution_receipt_id_reserved_without_write",
                "execution_receipt_sink_not_bound",
                "execution_receipt_prewrite_not_bound",
                "execution_receipt_final_write_not_bound",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        reservation = replace(reservation, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_execution_receipt_sink_reservations",
            reservation.id,
            {"receipt_sink_reservation": reservation.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_execution_receipt_sink_reservation_path": str(artifact_path),
            "last_lab_execution_receipt_sink_reservation_receipt_path": str(receipt_path),
            "last_lab_execution_receipt_sink_reservation_status": status,
            "last_lab_execution_receipt_sink_reservation_missing_checks": missing_checks,
            "last_lab_reserved_execution_receipt_id": reserved_receipt.get("id"),
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": handoff.approval_snapshot,
                "approval_path": handoff.approval_path,
                "approval_binding": handoff.approval_binding,
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "runner_enforcement": enforcement.to_dict(),
                "approval_consumption_handoff": handoff.to_dict(),
                "execution_receipt_sink_reservation": reservation.to_dict(),
                "artifact_path": str(artifact_path),
                "execution_receipt_sink_reservation_path": str(artifact_path),
                "reserved_execution_receipt": reserved_receipt,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="execution_receipt_sink_reservation_no_execution"),
            }
        )

    def preflight_lab_runner_command_allowlist_binding(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        reservation_result = self.preflight_lab_execution_receipt_sink_reservation(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        reservation = LabExecutionReceiptSinkReservation.from_dict(
            reservation_result.get("execution_receipt_sink_reservation")
        )
        handoff = LabApprovalConsumptionHandoff.from_dict(reservation_result.get("approval_consumption_handoff"))
        enforcement = LabRunnerEnforcementPreflight.from_dict(reservation_result.get("runner_enforcement"))
        binding_preflight = LabRunnerBindingPreflight.from_dict(reservation_result.get("runner_binding"))
        readiness = LabRunnerReadiness.from_dict(reservation_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(reservation_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(reservation_result.get("workspace"))
        source = SourceRecord.from_dict(reservation_result.get("source"))
        if (
            reservation is None
            or handoff is None
            or enforcement is None
            or binding_preflight is None
            or readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **reservation_result,
                    "status": "failed",
                    "error": "lab_execution_receipt_sink_reservation_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_execution_receipt_sink_reservation_unavailable"),
                }
            )

        command_plan = _lab_runner_command_plan(preflight=preflight)
        required_checks = _lab_runner_command_allowlist_required_checks()
        current_checks = _lab_runner_command_allowlist_current_checks(
            reservation=reservation,
            enforcement=enforcement,
            binding_preflight=binding_preflight,
            readiness=readiness,
            command_plan=command_plan,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = reservation.status == "refused" or handoff.status == "refused"
        blockers = _append_unique(
            reservation.blockers,
            *missing_checks,
            "runner_command_allowlist_binding_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        command_allowlist = LabRunnerCommandAllowlistBinding(
            id=_lab_runner_command_allowlist_binding_id(reservation.id, clean_approval_id),
            approval_id=clean_approval_id,
            receipt_sink_reservation_id=reservation.id,
            approval_handoff_id=handoff.id,
            runner_enforcement_id=enforcement.id,
            runner_binding_id=binding_preflight.id,
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            command_plan=command_plan,
            allowlist_contract=_lab_runner_command_allowlist_contract(
                reservation=reservation,
                command_plan=command_plan,
            ),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            allowlist_declared=False,
            allowlist_bound=False,
            command_execution_enabled=False,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runner_command_allowlists",
            command_allowlist.id,
            {"runner_command_allowlist": command_allowlist.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.command_allowlist.binding",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(reservation_result.get("execution_receipt_sink_reservation_path")).strip(),
                ],
                handoff.approval_path,
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "execution_receipt_sink_reservation_readback_no_execution",
                "exact_action_command_plan_projected_no_execution",
                "command_allowlist_not_declared",
                "command_allowlist_not_bound",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        command_allowlist = replace(command_allowlist, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runner_command_allowlists",
            command_allowlist.id,
            {"runner_command_allowlist": command_allowlist.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runner_command_allowlist_path": str(artifact_path),
            "last_lab_runner_command_allowlist_receipt_path": str(receipt_path),
            "last_lab_runner_command_allowlist_status": status,
            "last_lab_runner_command_allowlist_missing_checks": missing_checks,
            "last_lab_runner_command_count": command_plan.get("command_count"),
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": handoff.approval_snapshot,
                "approval_path": handoff.approval_path,
                "approval_binding": handoff.approval_binding,
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "runner_enforcement": enforcement.to_dict(),
                "approval_consumption_handoff": handoff.to_dict(),
                "execution_receipt_sink_reservation": reservation.to_dict(),
                "runner_command_allowlist": command_allowlist.to_dict(),
                "artifact_path": str(artifact_path),
                "runner_command_allowlist_path": str(artifact_path),
                "reserved_execution_receipt": reservation.reserved_execution_receipt,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="runner_command_allowlist_binding_no_execution"),
            }
        )

    def preflight_lab_runner_command_allowlist_declaration(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        command_allowlist_result = self.preflight_lab_runner_command_allowlist_binding(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        command_allowlist = LabRunnerCommandAllowlistBinding.from_dict(
            command_allowlist_result.get("runner_command_allowlist")
        )
        reservation = LabExecutionReceiptSinkReservation.from_dict(
            command_allowlist_result.get("execution_receipt_sink_reservation")
        )
        handoff = LabApprovalConsumptionHandoff.from_dict(command_allowlist_result.get("approval_consumption_handoff"))
        enforcement = LabRunnerEnforcementPreflight.from_dict(command_allowlist_result.get("runner_enforcement"))
        binding_preflight = LabRunnerBindingPreflight.from_dict(command_allowlist_result.get("runner_binding"))
        readiness = LabRunnerReadiness.from_dict(command_allowlist_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(command_allowlist_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(command_allowlist_result.get("workspace"))
        source = SourceRecord.from_dict(command_allowlist_result.get("source"))
        if (
            command_allowlist is None
            or reservation is None
            or handoff is None
            or enforcement is None
            or binding_preflight is None
            or readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **command_allowlist_result,
                    "status": "failed",
                    "error": "lab_runner_command_allowlist_binding_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_runner_command_allowlist_binding_unavailable"),
                }
            )

        declaration_id = _lab_runner_command_allowlist_declaration_id(command_allowlist.id, clean_approval_id)
        allowlist_declaration = _lab_runner_command_allowlist_declaration_entries(
            declaration_id=declaration_id,
            command_plan=command_allowlist.command_plan,
        )
        required_checks = _lab_runner_command_allowlist_declaration_required_checks()
        current_checks = _lab_runner_command_allowlist_declaration_current_checks(
            command_allowlist=command_allowlist,
            allowlist_declaration=allowlist_declaration,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        closed_by_declaration = {"command_allowlist_declared", "every_command_has_allowlist_entry"}
        upstream_blockers = [blocker for blocker in command_allowlist.blockers if blocker not in closed_by_declaration]
        refused = (
            command_allowlist.status == "refused" or reservation.status == "refused" or handoff.status == "refused"
        )
        blockers = _append_unique(
            upstream_blockers,
            *missing_checks,
            "runner_command_allowlist_declaration_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        declaration = LabRunnerCommandAllowlistDeclaration(
            id=declaration_id,
            approval_id=clean_approval_id,
            command_allowlist_binding_id=command_allowlist.id,
            receipt_sink_reservation_id=reservation.id,
            approval_handoff_id=handoff.id,
            runner_enforcement_id=enforcement.id,
            runner_binding_id=binding_preflight.id,
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            command_plan=command_allowlist.command_plan,
            allowlist_declaration=allowlist_declaration,
            declaration_contract=_lab_runner_command_allowlist_declaration_contract(
                command_allowlist=command_allowlist,
                allowlist_declaration=allowlist_declaration,
            ),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            declaration_created=True,
            allowlist_declared=bool(allowlist_declaration.get("allowlist_declared")),
            allowlist_bound=False,
            command_execution_enabled=False,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runner_command_allowlist_declarations",
            declaration.id,
            {"runner_command_allowlist_declaration": declaration.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.command_allowlist.declaration",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(command_allowlist_result.get("runner_command_allowlist_path")).strip(),
                ],
                handoff.approval_path,
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "runner_command_allowlist_binding_readback_no_execution",
                "exact_action_command_plan_declaration_created",
                "command_allowlist_not_bound",
                "commands_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        declaration = replace(declaration, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runner_command_allowlist_declarations",
            declaration.id,
            {"runner_command_allowlist_declaration": declaration.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runner_command_allowlist_declaration_path": str(artifact_path),
            "last_lab_runner_command_allowlist_declaration_receipt_path": str(receipt_path),
            "last_lab_runner_command_allowlist_declaration_status": status,
            "last_lab_runner_command_allowlist_declaration_missing_checks": missing_checks,
            "last_lab_runner_command_allowlist_entry_count": allowlist_declaration.get("entry_count"),
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": handoff.approval_snapshot,
                "approval_path": handoff.approval_path,
                "approval_binding": handoff.approval_binding,
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "runner_enforcement": enforcement.to_dict(),
                "approval_consumption_handoff": handoff.to_dict(),
                "execution_receipt_sink_reservation": reservation.to_dict(),
                "runner_command_allowlist": command_allowlist.to_dict(),
                "runner_command_allowlist_declaration": declaration.to_dict(),
                "artifact_path": str(artifact_path),
                "runner_command_allowlist_declaration_path": str(artifact_path),
                "reserved_execution_receipt": reservation.reserved_execution_receipt,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="runner_command_allowlist_declaration_no_execution"),
            }
        )

    def preflight_lab_runner_command_allowlist_enforcement(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        declaration_result = self.preflight_lab_runner_command_allowlist_declaration(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        declaration = LabRunnerCommandAllowlistDeclaration.from_dict(
            declaration_result.get("runner_command_allowlist_declaration")
        )
        command_allowlist = LabRunnerCommandAllowlistBinding.from_dict(
            declaration_result.get("runner_command_allowlist")
        )
        reservation = LabExecutionReceiptSinkReservation.from_dict(
            declaration_result.get("execution_receipt_sink_reservation")
        )
        handoff = LabApprovalConsumptionHandoff.from_dict(declaration_result.get("approval_consumption_handoff"))
        runner_enforcement = LabRunnerEnforcementPreflight.from_dict(declaration_result.get("runner_enforcement"))
        binding_preflight = LabRunnerBindingPreflight.from_dict(declaration_result.get("runner_binding"))
        readiness = LabRunnerReadiness.from_dict(declaration_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(declaration_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(declaration_result.get("workspace"))
        source = SourceRecord.from_dict(declaration_result.get("source"))
        if (
            declaration is None
            or command_allowlist is None
            or reservation is None
            or handoff is None
            or runner_enforcement is None
            or binding_preflight is None
            or readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **declaration_result,
                    "status": "failed",
                    "error": "lab_runner_command_allowlist_declaration_unavailable",
                    "execution": _no_lab_execution_payload(
                        reason="lab_runner_command_allowlist_declaration_unavailable"
                    ),
                }
            )

        enforcement_projection = _lab_runner_command_allowlist_enforcement_projection(
            declaration=declaration,
            runner_enforcement=runner_enforcement,
        )
        required_checks = _lab_runner_command_allowlist_enforcement_required_checks()
        current_checks = _lab_runner_command_allowlist_enforcement_current_checks(
            declaration=declaration,
            runner_enforcement=runner_enforcement,
            enforcement_projection=enforcement_projection,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = declaration.status == "refused" or reservation.status == "refused" or handoff.status == "refused"
        blockers = _append_unique(
            declaration.blockers,
            *missing_checks,
            "runner_command_allowlist_enforcement_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        enforcement_preflight = LabRunnerCommandAllowlistEnforcementPreflight(
            id=_lab_runner_command_allowlist_enforcement_preflight_id(declaration.id, clean_approval_id),
            approval_id=clean_approval_id,
            command_allowlist_declaration_id=declaration.id,
            command_allowlist_binding_id=command_allowlist.id,
            receipt_sink_reservation_id=reservation.id,
            approval_handoff_id=handoff.id,
            runner_enforcement_id=runner_enforcement.id,
            runner_binding_id=binding_preflight.id,
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            allowlist_declaration=declaration.allowlist_declaration,
            enforcement_projection=enforcement_projection,
            enforcement_contract=_lab_runner_command_allowlist_enforcement_contract(
                declaration=declaration,
                enforcement_projection=enforcement_projection,
            ),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            allowlist_declared=declaration.allowlist_declared,
            allowlist_bound=False,
            allowlist_enforced=False,
            command_execution_enabled=False,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_cmd_allowlist_enforcements",
            enforcement_preflight.id,
            {"runner_command_allowlist_enforcement": enforcement_preflight.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.command_allowlist.enforcement_preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(declaration_result.get("runner_command_allowlist_declaration_path")).strip(),
                ],
                handoff.approval_path,
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "runner_command_allowlist_declaration_readback_no_execution",
                "declared_command_hashes_checked",
                "live_allowlist_not_bound",
                "command_allowlist_not_enforced",
                "commands_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        enforcement_preflight = replace(enforcement_preflight, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_cmd_allowlist_enforcements",
            enforcement_preflight.id,
            {"runner_command_allowlist_enforcement": enforcement_preflight.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runner_command_allowlist_enforcement_path": str(artifact_path),
            "last_lab_runner_command_allowlist_enforcement_receipt_path": str(receipt_path),
            "last_lab_runner_command_allowlist_enforcement_status": status,
            "last_lab_runner_command_allowlist_enforcement_missing_checks": missing_checks,
            "last_lab_runner_command_allowlist_entry_count": enforcement_projection.get("entry_count"),
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": handoff.approval_snapshot,
                "approval_path": handoff.approval_path,
                "approval_binding": handoff.approval_binding,
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "runner_enforcement": runner_enforcement.to_dict(),
                "approval_consumption_handoff": handoff.to_dict(),
                "execution_receipt_sink_reservation": reservation.to_dict(),
                "runner_command_allowlist": command_allowlist.to_dict(),
                "runner_command_allowlist_declaration": declaration.to_dict(),
                "runner_command_allowlist_enforcement": enforcement_preflight.to_dict(),
                "artifact_path": str(artifact_path),
                "runner_command_allowlist_enforcement_path": str(artifact_path),
                "reserved_execution_receipt": reservation.reserved_execution_receipt,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="runner_command_allowlist_enforcement_no_execution"),
            }
        )

    def preflight_lab_runner_sandbox_readiness(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        enforcement_result = self.preflight_lab_runner_command_allowlist_enforcement(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        allowlist_enforcement = LabRunnerCommandAllowlistEnforcementPreflight.from_dict(
            enforcement_result.get("runner_command_allowlist_enforcement")
        )
        declaration = LabRunnerCommandAllowlistDeclaration.from_dict(
            enforcement_result.get("runner_command_allowlist_declaration")
        )
        command_allowlist = LabRunnerCommandAllowlistBinding.from_dict(
            enforcement_result.get("runner_command_allowlist")
        )
        reservation = LabExecutionReceiptSinkReservation.from_dict(
            enforcement_result.get("execution_receipt_sink_reservation")
        )
        handoff = LabApprovalConsumptionHandoff.from_dict(enforcement_result.get("approval_consumption_handoff"))
        runner_enforcement = LabRunnerEnforcementPreflight.from_dict(enforcement_result.get("runner_enforcement"))
        binding_preflight = LabRunnerBindingPreflight.from_dict(enforcement_result.get("runner_binding"))
        readiness = LabRunnerReadiness.from_dict(enforcement_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(enforcement_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(enforcement_result.get("workspace"))
        source = SourceRecord.from_dict(enforcement_result.get("source"))
        if (
            allowlist_enforcement is None
            or declaration is None
            or command_allowlist is None
            or reservation is None
            or handoff is None
            or runner_enforcement is None
            or binding_preflight is None
            or readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **enforcement_result,
                    "status": "failed",
                    "error": "lab_runner_command_allowlist_enforcement_unavailable",
                    "execution": _no_lab_execution_payload(
                        reason="lab_runner_command_allowlist_enforcement_unavailable"
                    ),
                }
            )

        sandbox_profile = _lab_runner_sandbox_profile(
            workspace=workspace,
            allowlist_enforcement=allowlist_enforcement,
        )
        required_checks = _lab_runner_sandbox_required_checks()
        current_checks = _lab_runner_sandbox_current_checks(
            workspace=workspace,
            allowlist_enforcement=allowlist_enforcement,
            sandbox_profile=sandbox_profile,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = (
            allowlist_enforcement.status == "refused"
            or declaration.status == "refused"
            or reservation.status == "refused"
            or handoff.status == "refused"
        )
        blockers = _append_unique(
            allowlist_enforcement.blockers,
            *missing_checks,
            "runner_sandbox_readiness_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        sandbox_readiness = LabRunnerSandboxReadiness(
            id=_lab_runner_sandbox_readiness_id(allowlist_enforcement.id, clean_approval_id),
            approval_id=clean_approval_id,
            command_allowlist_enforcement_id=allowlist_enforcement.id,
            command_allowlist_declaration_id=declaration.id,
            command_allowlist_binding_id=command_allowlist.id,
            receipt_sink_reservation_id=reservation.id,
            approval_handoff_id=handoff.id,
            runner_enforcement_id=runner_enforcement.id,
            runner_binding_id=binding_preflight.id,
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            sandbox_profile=sandbox_profile,
            sandbox_contract=_lab_runner_sandbox_contract(
                allowlist_enforcement=allowlist_enforcement,
                sandbox_profile=sandbox_profile,
            ),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            sandbox_bound=False,
            sandbox_enforced=False,
            runner_bound=False,
            runner_identity_verified=False,
            allowlist_enforced=False,
            receipt_prewrite_bound=False,
            receipt_final_write_bound=False,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_readiness",
            sandbox_readiness.id,
            {"runner_sandbox_readiness": sandbox_readiness.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.sandbox_readiness.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(enforcement_result.get("runner_command_allowlist_enforcement_path")).strip(),
                ],
                handoff.approval_path,
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "runner_command_allowlist_enforcement_readback_no_execution",
                "workspace_manifest_checked",
                "source_reference_checked_no_copy",
                "sandbox_not_bound",
                "runner_not_bound",
                "command_allowlist_not_enforced",
                "execution_receipt_prewrite_not_bound",
                "execution_receipt_final_write_not_bound",
                "commands_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        sandbox_readiness = replace(sandbox_readiness, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_readiness",
            sandbox_readiness.id,
            {"runner_sandbox_readiness": sandbox_readiness.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runner_sandbox_readiness_path": str(artifact_path),
            "last_lab_runner_sandbox_readiness_receipt_path": str(receipt_path),
            "last_lab_runner_sandbox_readiness_status": status,
            "last_lab_runner_sandbox_readiness_missing_checks": missing_checks,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": handoff.approval_snapshot,
                "approval_path": handoff.approval_path,
                "approval_binding": handoff.approval_binding,
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "runner_enforcement": runner_enforcement.to_dict(),
                "approval_consumption_handoff": handoff.to_dict(),
                "execution_receipt_sink_reservation": reservation.to_dict(),
                "runner_command_allowlist": command_allowlist.to_dict(),
                "runner_command_allowlist_declaration": declaration.to_dict(),
                "runner_command_allowlist_enforcement": allowlist_enforcement.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "artifact_path": str(artifact_path),
                "runner_sandbox_readiness_path": str(artifact_path),
                "reserved_execution_receipt": reservation.reserved_execution_receipt,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="runner_sandbox_readiness_no_execution"),
            }
        )

    def preflight_lab_sandbox_provider_contract(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        sandbox_result = self.preflight_lab_runner_sandbox_readiness(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(sandbox_result.get("runner_sandbox_readiness"))
        preflight = LabExecutionPreflight.from_dict(sandbox_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(sandbox_result.get("workspace"))
        source = SourceRecord.from_dict(sandbox_result.get("source"))
        if sandbox_readiness is None or preflight is None or workspace is None or source is None:
            return _display_payload(
                {
                    **sandbox_result,
                    "status": "failed",
                    "error": "lab_runner_sandbox_readiness_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_runner_sandbox_readiness_unavailable"),
                }
            )

        provider_contract = _lab_sandbox_provider_contract_payload(
            sandbox_readiness=sandbox_readiness,
            workspace=workspace,
        )
        required_checks = _lab_sandbox_provider_contract_required_checks()
        current_checks = _lab_sandbox_provider_contract_current_checks(
            sandbox_readiness=sandbox_readiness,
            provider_contract=provider_contract,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
            )
        )
        blockers = _append_unique(
            sandbox_readiness.blockers,
            *missing_checks,
            "sandbox_provider_contract_blocked",
        )
        status = (
            "refused"
            if unsafe_state or sandbox_readiness.status == "refused"
            else "ready"
            if not blockers
            else "blocked"
        )
        now = utc_now()
        contract = LabSandboxProviderContract(
            id=_lab_sandbox_provider_contract_id(sandbox_readiness.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_readiness_id=sandbox_readiness.id,
            command_allowlist_enforcement_id=sandbox_readiness.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=sandbox_readiness.action,
            action_hash=sandbox_readiness.action_hash,
            contract_kind="francis.lab.sandbox_provider_contract",
            contract_mode="provider_contract_preflight_only_no_execution",
            provider_kind="unbound",
            provider_contract=provider_contract,
            runner_sandbox_readiness=sandbox_readiness.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            provider_contract_declared=bool(current_checks.get("provider_contract_declared")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            workspace_isolation_bound=bool(current_checks.get("workspace_isolation_bound")),
            filesystem_write_policy_bound=bool(current_checks.get("filesystem_write_policy_bound")),
            network_policy_bound=bool(current_checks.get("network_blocked_or_policy_bound")),
            resource_limits_bound=bool(current_checks.get("resource_limits_bound")),
            timeout_policy_bound=bool(current_checks.get("timeout_policy_bound")),
            stdout_stderr_capture_bound=bool(current_checks.get("stdout_stderr_capture_bound")),
            kill_switch_bound=bool(current_checks.get("kill_switch_bound")),
            command_allowlist_enforced=bool(current_checks.get("command_allowlist_enforced")),
            receipt_prewrite_bound=bool(current_checks.get("receipt_prewrite_bound")),
            receipt_final_write_bound=bool(current_checks.get("receipt_final_write_bound")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_contract_preflight_only",
                    "sandbox_provider_not_bound",
                    "sandbox_not_enforced",
                    "commands_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "runner_sandbox_readiness_readback",
                "provider_contract_declared",
                "sandbox_provider_binding_checked",
                "sandbox_enforcement_checked",
                "workspace_isolation_checked",
                "filesystem_write_policy_checked",
                "network_policy_checked",
                "resource_limits_checked",
                "timeout_policy_checked",
                "stdout_stderr_capture_checked",
                "kill_switch_checked",
                "commands_not_executed",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_contracts",
            contract.id,
            {"sandbox_provider_contract": contract.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_contract.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(sandbox_result.get("runner_sandbox_readiness_path")).strip(),
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(provider_contract),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=contract.warnings,
            errors=contract.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=contract.validation_performed,
        )
        contract = replace(contract, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_contracts",
            contract.id,
            {"sandbox_provider_contract": contract.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_contract_path": str(artifact_path),
            "last_lab_sandbox_provider_contract_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_contract_status": status,
            "last_lab_sandbox_provider_contract_missing_checks": missing_checks,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": contract.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "sandbox_provider_contract": contract.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_contract_path": str(artifact_path),
                "reserved_execution_receipt": sandbox_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="sandbox_provider_contract_no_execution"),
            }
        )

    def preflight_lab_sandbox_provider_binding(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        contract_result = self.preflight_lab_sandbox_provider_contract(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        provider_contract = LabSandboxProviderContract.from_dict(contract_result.get("sandbox_provider_contract"))
        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(contract_result.get("runner_sandbox_readiness"))
        preflight = LabExecutionPreflight.from_dict(contract_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(contract_result.get("workspace"))
        source = SourceRecord.from_dict(contract_result.get("source"))
        if (
            provider_contract is None
            or sandbox_readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **contract_result,
                    "status": "failed",
                    "error": "lab_sandbox_provider_contract_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_sandbox_provider_contract_unavailable"),
                }
            )

        binding_contract = _lab_sandbox_provider_binding_contract_payload(
            provider_contract=provider_contract,
            workspace=workspace,
        )
        required_checks = _lab_sandbox_provider_binding_required_checks()
        current_checks = _lab_sandbox_provider_binding_current_checks(
            provider_contract=provider_contract,
            binding_contract=binding_contract,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
            )
        )
        blockers = _append_unique(
            provider_contract.blockers,
            *missing_checks,
            "sandbox_provider_binding_preflight_blocked",
        )
        status = (
            "refused"
            if unsafe_state or provider_contract.status == "refused"
            else "ready"
            if not blockers
            else "blocked"
        )
        now = utc_now()
        binding = LabSandboxProviderBindingPreflight(
            id=_lab_sandbox_provider_binding_id(provider_contract.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_provider_contract_id=provider_contract.id,
            sandbox_readiness_id=provider_contract.sandbox_readiness_id,
            command_allowlist_enforcement_id=provider_contract.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=provider_contract.action,
            action_hash=provider_contract.action_hash,
            binding_kind="francis.lab.sandbox_provider_binding_preflight",
            binding_mode="binding_preflight_only_no_execution",
            provider_kind="unbound",
            provider_contract=provider_contract.provider_contract,
            provider_binding_contract=binding_contract,
            sandbox_provider_contract=provider_contract.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            provider_contract_present=bool(current_checks.get("provider_contract_present")),
            provider_contract_ready=bool(current_checks.get("provider_contract_ready")),
            provider_contract_declared=bool(current_checks.get("provider_contract_declared")),
            provider_kind_selected=bool(current_checks.get("provider_kind_selected")),
            provider_binary_or_service_verified=bool(current_checks.get("provider_binary_or_service_verified")),
            provider_policy_manifest_bound=bool(current_checks.get("provider_policy_manifest_bound")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            workspace_isolation_bound=bool(current_checks.get("workspace_isolation_bound")),
            filesystem_write_policy_bound=bool(current_checks.get("filesystem_write_policy_bound")),
            network_policy_bound=bool(current_checks.get("network_blocked_or_policy_bound")),
            resource_limits_bound=bool(current_checks.get("resource_limits_bound")),
            timeout_policy_bound=bool(current_checks.get("timeout_policy_bound")),
            stdout_stderr_capture_bound=bool(current_checks.get("stdout_stderr_capture_bound")),
            kill_switch_bound=bool(current_checks.get("kill_switch_bound")),
            command_allowlist_enforced=bool(current_checks.get("command_allowlist_enforced")),
            receipt_prewrite_bound=bool(current_checks.get("receipt_prewrite_bound")),
            receipt_final_write_bound=bool(current_checks.get("receipt_final_write_bound")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_binding_preflight_only",
                    "sandbox_provider_not_selected",
                    "sandbox_provider_not_bound",
                    "sandbox_not_enforced",
                    "commands_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "sandbox_provider_contract_readback",
                "provider_binding_contract_declared",
                "provider_kind_selection_checked",
                "provider_binary_or_service_checked",
                "provider_policy_manifest_checked",
                "sandbox_provider_binding_checked",
                "sandbox_enforcement_checked",
                "commands_not_executed",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_bindings",
            binding.id,
            {"sandbox_provider_binding": binding.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_binding.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(contract_result.get("sandbox_provider_contract_path")).strip(),
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(binding_contract),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=binding.warnings,
            errors=binding.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=binding.validation_performed,
        )
        binding = replace(binding, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_bindings",
            binding.id,
            {"sandbox_provider_binding": binding.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_binding_path": str(artifact_path),
            "last_lab_sandbox_provider_binding_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_binding_status": status,
            "last_lab_sandbox_provider_binding_missing_checks": missing_checks,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": binding.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "sandbox_provider_contract": provider_contract.to_dict(),
                "sandbox_provider_binding": binding.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_binding_path": str(artifact_path),
                "reserved_execution_receipt": contract_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="sandbox_provider_binding_no_execution"),
            }
        )

    def preflight_lab_sandbox_provider_selection(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        provider_kind: str = "",
        provider_reference: str = "",
        provider_policy_manifest: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        requested_provider_kind = _normalize_lab_sandbox_provider_kind(provider_kind)
        clean_provider_reference = _safe_str(provider_reference).strip()
        clean_provider_policy_manifest = _safe_str(provider_policy_manifest).strip()
        binding_result = self.preflight_lab_sandbox_provider_binding(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        provider_binding = LabSandboxProviderBindingPreflight.from_dict(binding_result.get("sandbox_provider_binding"))
        provider_contract = LabSandboxProviderContract.from_dict(binding_result.get("sandbox_provider_contract"))
        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(binding_result.get("runner_sandbox_readiness"))
        preflight = LabExecutionPreflight.from_dict(binding_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(binding_result.get("workspace"))
        source = SourceRecord.from_dict(binding_result.get("source"))
        if (
            provider_binding is None
            or provider_contract is None
            or sandbox_readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **binding_result,
                    "status": "failed",
                    "error": "lab_sandbox_provider_binding_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_sandbox_provider_binding_unavailable"),
                }
            )

        provider_selection_policy = _lab_sandbox_provider_selection_policy_payload(
            provider_binding=provider_binding,
            requested_provider_kind=requested_provider_kind,
            provider_reference=clean_provider_reference,
            provider_policy_manifest=clean_provider_policy_manifest,
        )
        provider_verification = {
            "verification_kind": "francis.lab.sandbox_provider_local_reference_verification",
            "schema_version": 1,
            "mode": "local_metadata_only_no_execution",
            "provider_reference": _lab_provider_reference_metadata(clean_provider_reference),
            "provider_policy_manifest": _lab_provider_policy_manifest_metadata(clean_provider_policy_manifest),
            "provider_binary_or_service_verified": False,
            "verification_limited_to_metadata": True,
            "service_queries_performed": False,
            "processes_launched": False,
            "containers_launched": False,
            "network_accessed": False,
            "repo_code_executed": False,
            "wrote_to_repo": False,
        }
        required_checks = _lab_sandbox_provider_selection_required_checks()
        current_checks = _lab_sandbox_provider_selection_current_checks(
            provider_binding=provider_binding,
            provider_selection_policy=provider_selection_policy,
            provider_verification=provider_verification,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
            )
        )
        blockers = _append_unique(
            provider_binding.blockers,
            *missing_checks,
            "sandbox_provider_selection_preflight_blocked",
        )
        status = (
            "refused"
            if unsafe_state or provider_binding.status == "refused"
            else "ready"
            if not blockers
            else "blocked"
        )
        now = utc_now()
        selection = LabSandboxProviderSelectionPreflight(
            id=_lab_sandbox_provider_selection_id(
                provider_binding.id,
                clean_approval_id,
                requested_provider_kind,
                clean_provider_reference,
                clean_provider_policy_manifest,
            ),
            approval_id=clean_approval_id,
            sandbox_provider_binding_id=provider_binding.id,
            sandbox_provider_contract_id=provider_binding.sandbox_provider_contract_id,
            sandbox_readiness_id=provider_binding.sandbox_readiness_id,
            command_allowlist_enforcement_id=provider_binding.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=provider_binding.action,
            action_hash=provider_binding.action_hash,
            selection_kind="francis.lab.sandbox_provider_selection_preflight",
            selection_mode="selection_verification_preflight_only_no_execution",
            requested_provider_kind=requested_provider_kind,
            selected_provider_kind=_safe_str(provider_selection_policy.get("selected_provider_kind")).strip()
            or "unselected",
            provider_reference=_safe_str(
                _as_dict(provider_verification.get("provider_reference")).get("reference")
            ).strip(),
            provider_reference_kind=_safe_str(
                _as_dict(provider_verification.get("provider_reference")).get("reference_kind")
            ).strip()
            or "none",
            provider_policy_manifest_path=_safe_str(
                _as_dict(provider_verification.get("provider_policy_manifest")).get("path")
            ).strip(),
            provider_selection_policy=provider_selection_policy,
            provider_verification=provider_verification,
            sandbox_provider_binding=provider_binding.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            provider_binding_present=bool(current_checks.get("provider_binding_present")),
            provider_binding_ready=bool(current_checks.get("provider_binding_ready")),
            provider_selection_policy_declared=bool(current_checks.get("provider_selection_policy_declared")),
            provider_kind_allowed_by_policy=bool(current_checks.get("provider_kind_allowed_by_policy")),
            provider_kind_selected=bool(current_checks.get("provider_kind_selected")),
            provider_reference_checked=bool(current_checks.get("provider_reference_checked")),
            provider_reference_present=bool(current_checks.get("provider_reference_present")),
            provider_reference_verified=bool(current_checks.get("provider_reference_verified")),
            provider_binary_or_service_verified=bool(current_checks.get("provider_binary_or_service_verified")),
            provider_policy_manifest_present=bool(current_checks.get("provider_policy_manifest_present")),
            provider_policy_manifest_bound=bool(current_checks.get("provider_policy_manifest_bound")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            workspace_isolation_bound=bool(current_checks.get("workspace_isolation_bound")),
            filesystem_write_policy_bound=bool(current_checks.get("filesystem_write_policy_bound")),
            network_policy_bound=bool(current_checks.get("network_blocked_or_policy_bound")),
            resource_limits_bound=bool(current_checks.get("resource_limits_bound")),
            timeout_policy_bound=bool(current_checks.get("timeout_policy_bound")),
            stdout_stderr_capture_bound=bool(current_checks.get("stdout_stderr_capture_bound")),
            kill_switch_bound=bool(current_checks.get("kill_switch_bound")),
            command_allowlist_enforced=bool(current_checks.get("command_allowlist_enforced")),
            receipt_prewrite_bound=bool(current_checks.get("receipt_prewrite_bound")),
            receipt_final_write_bound=bool(current_checks.get("receipt_final_write_bound")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_selection_preflight_only",
                    "local_provider_reference_metadata_only",
                    "provider_binary_or_service_not_verified",
                    "sandbox_provider_not_bound",
                    "sandbox_not_enforced",
                    "commands_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "sandbox_provider_binding_readback",
                "provider_selection_policy_declared",
                "provider_kind_policy_checked",
                "provider_reference_metadata_checked_without_execution",
                "provider_policy_manifest_metadata_checked_without_contents",
                "provider_binary_or_service_not_executed",
                "provider_binary_or_service_not_verified",
                "sandbox_provider_binding_checked",
                "sandbox_enforcement_checked",
                "commands_not_executed",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_selections",
            selection.id,
            {"sandbox_provider_selection": selection.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_selection.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(binding_result.get("sandbox_provider_binding_path")).strip(),
                    selection.provider_reference,
                    selection.provider_policy_manifest_path,
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(provider_selection_policy),
                _stable_payload_hash(provider_verification),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=selection.warnings,
            errors=selection.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=selection.validation_performed,
        )
        selection = replace(selection, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_selections",
            selection.id,
            {"sandbox_provider_selection": selection.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_selection_path": str(artifact_path),
            "last_lab_sandbox_provider_selection_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_selection_status": status,
            "last_lab_sandbox_provider_selection_missing_checks": missing_checks,
            "last_lab_sandbox_provider_selected_kind": selection.selected_provider_kind,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": selection.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "sandbox_provider_contract": provider_contract.to_dict(),
                "sandbox_provider_binding": provider_binding.to_dict(),
                "sandbox_provider_selection": selection.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_selection_path": str(artifact_path),
                "reserved_execution_receipt": binding_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="sandbox_provider_selection_no_execution"),
            }
        )

    def preflight_lab_sandbox_provider_verifier(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        provider_kind: str = "",
        provider_reference: str = "",
        provider_policy_manifest: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        selection_result = self.preflight_lab_sandbox_provider_selection(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            provider_kind=provider_kind,
            provider_reference=provider_reference,
            provider_policy_manifest=provider_policy_manifest,
            actor=actor,
        )
        provider_selection = LabSandboxProviderSelectionPreflight.from_dict(
            selection_result.get("sandbox_provider_selection")
        )
        provider_binding = LabSandboxProviderBindingPreflight.from_dict(
            selection_result.get("sandbox_provider_binding")
        )
        provider_contract = LabSandboxProviderContract.from_dict(selection_result.get("sandbox_provider_contract"))
        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(selection_result.get("runner_sandbox_readiness"))
        preflight = LabExecutionPreflight.from_dict(selection_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(selection_result.get("workspace"))
        source = SourceRecord.from_dict(selection_result.get("source"))
        if (
            provider_selection is None
            or provider_binding is None
            or provider_contract is None
            or sandbox_readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **selection_result,
                    "status": "failed",
                    "error": "lab_sandbox_provider_selection_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_sandbox_provider_selection_unavailable"),
                }
            )

        verifier_contract = _lab_sandbox_provider_verifier_contract_payload(
            provider_selection=provider_selection,
            workspace=workspace,
        )
        static_verification = _lab_sandbox_provider_static_verification_payload(
            provider_selection=provider_selection,
            actor=actor,
        )
        required_checks = _lab_sandbox_provider_verifier_required_checks()
        current_checks = _lab_sandbox_provider_verifier_current_checks(
            provider_selection=provider_selection,
            verifier_contract=verifier_contract,
            static_verification=static_verification,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "service_query_performed",
                "process_launched",
                "container_launched",
            )
        )
        upstream_blockers = [
            blocker
            for blocker in provider_selection.blockers
            if not bool(current_checks.get(_safe_str(blocker).strip()))
        ]
        blockers = _append_unique(
            upstream_blockers,
            *missing_checks,
            "sandbox_provider_verifier_preflight_blocked",
        )
        status = (
            "refused"
            if unsafe_state or provider_selection.status == "refused"
            else "ready"
            if not blockers
            else "blocked"
        )
        now = utc_now()
        verifier = LabSandboxProviderVerifierPreflight(
            id=_lab_sandbox_provider_verifier_id(provider_selection.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_provider_selection_id=provider_selection.id,
            sandbox_provider_binding_id=provider_selection.sandbox_provider_binding_id,
            sandbox_provider_contract_id=provider_selection.sandbox_provider_contract_id,
            sandbox_readiness_id=provider_selection.sandbox_readiness_id,
            command_allowlist_enforcement_id=provider_selection.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=provider_selection.action,
            action_hash=provider_selection.action_hash,
            verifier_kind="francis.lab.sandbox_provider_verifier_preflight",
            verifier_mode="static_identity_policy_verification_no_execution",
            provider_kind=provider_selection.selected_provider_kind,
            provider_reference=provider_selection.provider_reference,
            provider_policy_manifest_path=provider_selection.provider_policy_manifest_path,
            verifier_identity=_as_dict(static_verification.get("verifier_identity")),
            provider_identity=_as_dict(static_verification.get("provider_identity")),
            provider_policy_manifest=_as_dict(static_verification.get("provider_policy_manifest")),
            provider_runtime_probe=_as_dict(static_verification.get("provider_runtime_probe")),
            verifier_contract=verifier_contract,
            verifier_boundary={
                "mode": "static_identity_policy_verification_no_provider_execution",
                "verification_refused_until_runtime_probe_bound": True,
                "provider_binary_or_service_verified": bool(current_checks.get("provider_binary_or_service_verified")),
                "provider_runtime_probe_performed": False,
                "service_query_performed": False,
                "process_launched": False,
                "container_launched": False,
                "sandbox_provider_bound": False,
                "execution_authority": False,
            },
            sandbox_provider_selection=provider_selection.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            provider_selection_present=bool(current_checks.get("provider_selection_present")),
            provider_selection_ready=bool(current_checks.get("provider_selection_ready")),
            provider_kind_selected=bool(current_checks.get("provider_kind_selected")),
            provider_reference_verified=bool(current_checks.get("provider_reference_verified")),
            provider_policy_manifest_bound=bool(current_checks.get("provider_policy_manifest_bound")),
            verifier_contract_declared=bool(current_checks.get("verifier_contract_declared")),
            verifier_implementation_bound=bool(current_checks.get("verifier_implementation_bound")),
            verifier_identity_bound=bool(current_checks.get("verifier_identity_bound")),
            verifier_policy_bound=bool(current_checks.get("verifier_policy_bound")),
            verifier_receipt_contract_bound=bool(current_checks.get("verifier_receipt_contract_bound")),
            static_identity_verification_performed=bool(current_checks.get("static_identity_verification_performed")),
            provider_reference_fingerprint_captured=bool(current_checks.get("provider_reference_fingerprint_captured")),
            provider_policy_manifest_hash_captured=bool(current_checks.get("provider_policy_manifest_hash_captured")),
            provider_binary_or_service_verified=bool(current_checks.get("provider_binary_or_service_verified")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            provider_version_captured=bool(current_checks.get("provider_version_captured")),
            provider_identity_fingerprint_captured=bool(current_checks.get("provider_identity_fingerprint_captured")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            workspace_isolation_bound=bool(current_checks.get("workspace_isolation_bound")),
            filesystem_write_policy_bound=bool(current_checks.get("filesystem_write_policy_bound")),
            network_policy_bound=bool(current_checks.get("network_blocked_or_policy_bound")),
            resource_limits_bound=bool(current_checks.get("resource_limits_bound")),
            timeout_policy_bound=bool(current_checks.get("timeout_policy_bound")),
            stdout_stderr_capture_bound=bool(current_checks.get("stdout_stderr_capture_bound")),
            kill_switch_bound=bool(current_checks.get("kill_switch_bound")),
            command_allowlist_enforced=bool(current_checks.get("command_allowlist_enforced")),
            receipt_prewrite_bound=bool(current_checks.get("receipt_prewrite_bound")),
            receipt_final_write_bound=bool(current_checks.get("receipt_final_write_bound")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_verifier_static_identity_only",
                    "provider_runtime_probe_not_performed",
                    "provider_binary_not_executed",
                    "provider_service_not_queried",
                    "container_not_launched",
                    "sandbox_provider_not_bound",
                    "sandbox_not_enforced",
                    "commands_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *(
                    []
                    if current_checks.get("provider_binary_or_service_verified")
                    else ["provider_binary_or_service_not_verified"]
                ),
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "sandbox_provider_selection_readback",
                "verifier_contract_declared",
                "verifier_static_identity_bound",
                "verifier_receipt_contract_bound",
                "provider_reference_fingerprint_checked",
                "provider_policy_manifest_hash_checked",
                "provider_identity_fingerprint_checked",
                "provider_binary_or_service_not_executed",
                "provider_runtime_probe_not_performed",
                "provider_service_not_queried",
                "container_not_launched",
                "sandbox_provider_binding_checked",
                "sandbox_enforcement_checked",
                "commands_not_executed",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_verifier_preflights",
            verifier.id,
            {"sandbox_provider_verifier": verifier.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_verifier.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(selection_result.get("sandbox_provider_selection_path")).strip(),
                    verifier.provider_reference,
                    verifier.provider_policy_manifest_path,
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(verifier_contract),
                _stable_payload_hash(static_verification),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=verifier.warnings,
            errors=verifier.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=verifier.validation_performed,
        )
        verifier = replace(verifier, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_verifier_preflights",
            verifier.id,
            {"sandbox_provider_verifier": verifier.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_verifier_path": str(artifact_path),
            "last_lab_sandbox_provider_verifier_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_verifier_status": status,
            "last_lab_sandbox_provider_verifier_missing_checks": missing_checks,
            "last_lab_sandbox_provider_verifier_mode": verifier.verifier_mode,
            "last_lab_sandbox_provider_identity_fingerprint": _safe_str(
                verifier.provider_identity.get("provider_identity_fingerprint")
            ).strip(),
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": verifier.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "sandbox_provider_contract": provider_contract.to_dict(),
                "sandbox_provider_binding": provider_binding.to_dict(),
                "sandbox_provider_selection": provider_selection.to_dict(),
                "sandbox_provider_verifier": verifier.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_verifier_path": str(artifact_path),
                "reserved_execution_receipt": selection_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="sandbox_provider_verifier_no_execution"),
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        provider_kind: str = "",
        provider_reference: str = "",
        provider_policy_manifest: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        verifier_result = self.preflight_lab_sandbox_provider_verifier(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            provider_kind=provider_kind,
            provider_reference=provider_reference,
            provider_policy_manifest=provider_policy_manifest,
            actor=actor,
        )
        provider_verifier = LabSandboxProviderVerifierPreflight.from_dict(
            verifier_result.get("sandbox_provider_verifier")
        )
        provider_selection = LabSandboxProviderSelectionPreflight.from_dict(
            verifier_result.get("sandbox_provider_selection")
        )
        provider_binding = LabSandboxProviderBindingPreflight.from_dict(verifier_result.get("sandbox_provider_binding"))
        provider_contract = LabSandboxProviderContract.from_dict(verifier_result.get("sandbox_provider_contract"))
        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(verifier_result.get("runner_sandbox_readiness"))
        preflight = LabExecutionPreflight.from_dict(verifier_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(verifier_result.get("workspace"))
        source = SourceRecord.from_dict(verifier_result.get("source"))
        if (
            provider_verifier is None
            or provider_selection is None
            or provider_binding is None
            or provider_contract is None
            or sandbox_readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **verifier_result,
                    "status": "failed",
                    "error": "lab_sandbox_provider_verifier_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_sandbox_provider_verifier_unavailable"),
                }
            )

        runtime_probe_contract = _lab_sandbox_provider_runtime_probe_contract_payload(
            provider_verifier=provider_verifier,
            workspace=workspace,
        )
        required_checks = _lab_sandbox_provider_runtime_probe_required_checks()
        current_checks = _lab_sandbox_provider_runtime_probe_current_checks(
            provider_verifier=provider_verifier,
            runtime_probe_contract=runtime_probe_contract,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "service_query_performed",
                "process_launched",
                "container_launched",
            )
        )
        blockers = _append_unique([], *missing_checks, "sandbox_provider_runtime_probe_preflight_blocked")
        status = "refused" if unsafe_state else "ready" if not blockers else "blocked"
        now = utc_now()
        runtime_probe = LabSandboxProviderRuntimeProbePreflight(
            id=_lab_sandbox_provider_runtime_probe_id(provider_verifier.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_provider_verifier_id=provider_verifier.id,
            sandbox_provider_selection_id=provider_verifier.sandbox_provider_selection_id,
            sandbox_provider_binding_id=provider_verifier.sandbox_provider_binding_id,
            sandbox_provider_contract_id=provider_verifier.sandbox_provider_contract_id,
            sandbox_readiness_id=provider_verifier.sandbox_readiness_id,
            command_allowlist_enforcement_id=provider_verifier.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=provider_verifier.action,
            action_hash=provider_verifier.action_hash,
            probe_kind="francis.lab.sandbox_provider_runtime_probe_preflight",
            probe_mode="runtime_probe_contract_preflight_only_no_provider_execution",
            provider_kind=provider_verifier.provider_kind,
            provider_reference=provider_verifier.provider_reference,
            provider_policy_manifest_path=provider_verifier.provider_policy_manifest_path,
            provider_identity=provider_verifier.provider_identity,
            provider_policy_manifest=provider_verifier.provider_policy_manifest,
            runtime_probe_contract=runtime_probe_contract,
            runtime_probe_boundary={
                "mode": "future_governed_provider_probe_contract_no_execution",
                "provider_runtime_probe_performed": False,
                "provider_binary_executed": False,
                "service_query_performed": False,
                "process_launched": False,
                "container_launched": False,
                "sandbox_provider_bound": False,
                "execution_authority": False,
                "repo_code_executed": False,
            },
            sandbox_provider_verifier=provider_verifier.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            verifier_present=bool(current_checks.get("sandbox_provider_verifier_present")),
            verifier_static_identity_ready=bool(current_checks.get("verifier_static_identity_ready")),
            provider_identity_fingerprint_captured=bool(current_checks.get("provider_identity_fingerprint_captured")),
            provider_binary_or_service_verified=bool(current_checks.get("provider_binary_or_service_verified")),
            runtime_probe_contract_declared=bool(current_checks.get("runtime_probe_contract_declared")),
            runtime_probe_authorization_required=bool(current_checks.get("runtime_probe_authorization_required")),
            runtime_probe_policy_bound=bool(current_checks.get("runtime_probe_policy_bound")),
            runtime_probe_timeout_policy_declared=bool(current_checks.get("runtime_probe_timeout_policy_declared")),
            runtime_probe_network_blocked_by_contract=bool(
                current_checks.get("runtime_probe_network_blocked_by_contract")
            ),
            runtime_probe_workspace_isolation_required=bool(
                current_checks.get("runtime_probe_workspace_isolation_required")
            ),
            runtime_probe_receipt_contract_declared=bool(current_checks.get("runtime_probe_receipt_contract_declared")),
            runtime_probe_repo_execution_separated=bool(current_checks.get("runtime_probe_repo_execution_separated")),
            runtime_probe_runner_bound=bool(current_checks.get("runtime_probe_runner_bound")),
            runtime_probe_sandbox_bound=bool(current_checks.get("runtime_probe_sandbox_bound")),
            runtime_probe_service_query_guard_bound=bool(current_checks.get("runtime_probe_service_query_guard_bound")),
            runtime_probe_output_capture_bound=bool(current_checks.get("runtime_probe_output_capture_bound")),
            runtime_probe_kill_switch_bound=bool(current_checks.get("runtime_probe_kill_switch_bound")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_runtime_probe_preflight_only",
                    "provider_runtime_probe_not_performed",
                    "provider_binary_not_executed",
                    "provider_service_not_queried",
                    "container_not_launched",
                    "sandbox_provider_not_bound",
                    "repository_code_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "sandbox_provider_verifier_readback",
                "runtime_probe_contract_declared",
                "runtime_probe_authorization_requirement_declared",
                "runtime_probe_timeout_policy_declared",
                "runtime_probe_network_blocked_by_contract",
                "runtime_probe_receipt_contract_declared",
                "runtime_probe_repository_execution_separated",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "container_not_launched",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_runtime_probe_preflights",
            runtime_probe.id,
            {"sandbox_provider_runtime_probe": runtime_probe.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(verifier_result.get("sandbox_provider_verifier_path")).strip(),
                    runtime_probe.provider_reference,
                    runtime_probe.provider_policy_manifest_path,
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(runtime_probe_contract),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=runtime_probe.warnings,
            errors=runtime_probe.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=runtime_probe.validation_performed,
        )
        runtime_probe = replace(runtime_probe, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandbox_provider_runtime_probe_preflights",
            runtime_probe.id,
            {"sandbox_provider_runtime_probe": runtime_probe.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_runtime_probe_path": str(artifact_path),
            "last_lab_sandbox_provider_runtime_probe_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_runtime_probe_status": status,
            "last_lab_sandbox_provider_runtime_probe_missing_checks": missing_checks,
            "last_lab_sandbox_provider_runtime_probe_mode": runtime_probe.probe_mode,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": runtime_probe.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "sandbox_provider_contract": provider_contract.to_dict(),
                "sandbox_provider_binding": provider_binding.to_dict(),
                "sandbox_provider_selection": provider_selection.to_dict(),
                "sandbox_provider_verifier": provider_verifier.to_dict(),
                "sandbox_provider_runtime_probe": runtime_probe.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_path": str(artifact_path),
                "reserved_execution_receipt": verifier_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="sandbox_provider_runtime_probe_no_execution"),
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe_harness(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        provider_kind: str = "",
        provider_reference: str = "",
        provider_policy_manifest: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        runtime_probe_result = self.preflight_lab_sandbox_provider_runtime_probe(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            provider_kind=provider_kind,
            provider_reference=provider_reference,
            provider_policy_manifest=provider_policy_manifest,
            actor=actor,
        )
        runtime_probe = LabSandboxProviderRuntimeProbePreflight.from_dict(
            runtime_probe_result.get("sandbox_provider_runtime_probe")
        )
        provider_verifier = LabSandboxProviderVerifierPreflight.from_dict(
            runtime_probe_result.get("sandbox_provider_verifier")
        )
        provider_selection = LabSandboxProviderSelectionPreflight.from_dict(
            runtime_probe_result.get("sandbox_provider_selection")
        )
        provider_binding = LabSandboxProviderBindingPreflight.from_dict(
            runtime_probe_result.get("sandbox_provider_binding")
        )
        provider_contract = LabSandboxProviderContract.from_dict(runtime_probe_result.get("sandbox_provider_contract"))
        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(runtime_probe_result.get("runner_sandbox_readiness"))
        preflight = LabExecutionPreflight.from_dict(runtime_probe_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(runtime_probe_result.get("workspace"))
        source = SourceRecord.from_dict(runtime_probe_result.get("source"))
        if (
            runtime_probe is None
            or provider_verifier is None
            or provider_selection is None
            or provider_binding is None
            or provider_contract is None
            or sandbox_readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **runtime_probe_result,
                    "status": "failed",
                    "error": "lab_sandbox_provider_runtime_probe_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_sandbox_provider_runtime_probe_unavailable"),
                }
            )

        harness_contract = _lab_sandbox_provider_runtime_probe_harness_contract_payload(
            runtime_probe=runtime_probe,
            workspace=workspace,
        )
        required_checks = _lab_sandbox_provider_runtime_probe_harness_required_checks()
        current_checks = _lab_sandbox_provider_runtime_probe_harness_current_checks(
            runtime_probe=runtime_probe,
            runtime_probe_harness_contract=harness_contract,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "service_query_performed",
                "process_launched",
                "container_launched",
            )
        )
        blockers = _append_unique(
            runtime_probe.blockers,
            *missing_checks,
            "sandbox_provider_runtime_probe_harness_preflight_blocked",
        )
        status = "refused" if unsafe_state else "ready" if not blockers else "blocked"
        now = utc_now()
        harness = LabSandboxProviderRuntimeProbeHarnessPreflight(
            id=_lab_sandbox_provider_runtime_probe_harness_id(runtime_probe.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_provider_runtime_probe_id=runtime_probe.id,
            sandbox_provider_verifier_id=runtime_probe.sandbox_provider_verifier_id,
            sandbox_provider_selection_id=runtime_probe.sandbox_provider_selection_id,
            sandbox_provider_binding_id=runtime_probe.sandbox_provider_binding_id,
            sandbox_provider_contract_id=runtime_probe.sandbox_provider_contract_id,
            sandbox_readiness_id=runtime_probe.sandbox_readiness_id,
            command_allowlist_enforcement_id=runtime_probe.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=runtime_probe.action,
            action_hash=runtime_probe.action_hash,
            harness_kind="francis.lab.sandbox_provider_runtime_probe_harness_preflight",
            harness_mode="runtime_probe_harness_preflight_only_no_provider_execution",
            provider_kind=runtime_probe.provider_kind,
            provider_reference=runtime_probe.provider_reference,
            provider_identity=runtime_probe.provider_identity,
            runtime_probe_contract=runtime_probe.runtime_probe_contract,
            runtime_probe_harness_contract=harness_contract,
            sandbox_provider_runtime_probe=runtime_probe.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            runtime_probe_preflight_present=bool(current_checks.get("runtime_probe_preflight_present")),
            runtime_probe_contract_declared=bool(current_checks.get("runtime_probe_contract_declared")),
            runtime_probe_authorization_required=bool(current_checks.get("runtime_probe_authorization_required")),
            runtime_probe_network_blocked_by_contract=bool(
                current_checks.get("runtime_probe_network_blocked_by_contract")
            ),
            runtime_probe_workspace_isolation_required=bool(
                current_checks.get("runtime_probe_workspace_isolation_required")
            ),
            runtime_probe_receipt_contract_declared=bool(current_checks.get("runtime_probe_receipt_contract_declared")),
            runtime_probe_repo_execution_separated=bool(current_checks.get("runtime_probe_repo_execution_separated")),
            runtime_probe_runner_contract_declared=bool(current_checks.get("runtime_probe_runner_contract_declared")),
            runtime_probe_runner_bound=bool(current_checks.get("runtime_probe_runner_bound")),
            runtime_probe_sandbox_contract_declared=bool(current_checks.get("runtime_probe_sandbox_contract_declared")),
            runtime_probe_sandbox_bound=bool(current_checks.get("runtime_probe_sandbox_bound")),
            runtime_probe_service_query_guard_declared=bool(
                current_checks.get("runtime_probe_service_query_guard_declared")
            ),
            runtime_probe_service_query_guard_bound=bool(current_checks.get("runtime_probe_service_query_guard_bound")),
            runtime_probe_output_capture_declared=bool(current_checks.get("runtime_probe_output_capture_declared")),
            runtime_probe_output_capture_bound=bool(current_checks.get("runtime_probe_output_capture_bound")),
            runtime_probe_kill_switch_declared=bool(current_checks.get("runtime_probe_kill_switch_declared")),
            runtime_probe_kill_switch_bound=bool(current_checks.get("runtime_probe_kill_switch_bound")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_runtime_probe_harness_preflight_only",
                    "runtime_probe_runner_not_bound",
                    "runtime_probe_sandbox_not_bound",
                    "provider_runtime_probe_not_performed",
                    "provider_binary_not_executed",
                    "provider_service_not_queried",
                    "container_not_launched",
                    "repository_code_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "sandbox_provider_runtime_probe_readback",
                "runtime_probe_harness_contract_declared",
                "runtime_probe_runner_contract_declared",
                "runtime_probe_sandbox_contract_declared",
                "runtime_probe_service_query_guard_declared",
                "runtime_probe_output_capture_declared",
                "runtime_probe_kill_switch_declared",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "container_not_launched",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_harness_preflights",
            harness.id,
            {"sandbox_provider_runtime_probe_harness": harness.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe_harness.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(runtime_probe_result.get("sandbox_provider_runtime_probe_path")).strip(),
                    harness.provider_reference,
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(harness_contract),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=harness.warnings,
            errors=harness.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=harness.validation_performed,
        )
        harness = replace(harness, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_harness_preflights",
            harness.id,
            {"sandbox_provider_runtime_probe_harness": harness.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_runtime_probe_harness_path": str(artifact_path),
            "last_lab_sandbox_provider_runtime_probe_harness_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_runtime_probe_harness_status": status,
            "last_lab_sandbox_provider_runtime_probe_harness_missing_checks": missing_checks,
            "last_lab_sandbox_provider_runtime_probe_harness_mode": harness.harness_mode,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": harness.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "sandbox_provider_contract": provider_contract.to_dict(),
                "sandbox_provider_binding": provider_binding.to_dict(),
                "sandbox_provider_selection": provider_selection.to_dict(),
                "sandbox_provider_verifier": provider_verifier.to_dict(),
                "sandbox_provider_runtime_probe": runtime_probe.to_dict(),
                "sandbox_provider_runtime_probe_harness": harness.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_harness_path": str(artifact_path),
                "reserved_execution_receipt": runtime_probe_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="sandbox_provider_runtime_probe_harness_no_execution"),
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe_runner_readiness(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        provider_kind: str = "",
        provider_reference: str = "",
        provider_policy_manifest: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        harness_result = self.preflight_lab_sandbox_provider_runtime_probe_harness(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            provider_kind=provider_kind,
            provider_reference=provider_reference,
            provider_policy_manifest=provider_policy_manifest,
            actor=actor,
        )
        harness = LabSandboxProviderRuntimeProbeHarnessPreflight.from_dict(
            harness_result.get("sandbox_provider_runtime_probe_harness")
        )
        runtime_probe = LabSandboxProviderRuntimeProbePreflight.from_dict(
            harness_result.get("sandbox_provider_runtime_probe")
        )
        preflight = LabExecutionPreflight.from_dict(harness_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(harness_result.get("workspace"))
        source = SourceRecord.from_dict(harness_result.get("source"))
        if harness is None or runtime_probe is None or preflight is None or workspace is None or source is None:
            return _display_payload(
                {
                    **harness_result,
                    "status": "failed",
                    "error": "lab_sandbox_provider_runtime_probe_harness_unavailable",
                    "execution": _no_lab_execution_payload(
                        reason="lab_sandbox_provider_runtime_probe_harness_unavailable"
                    ),
                }
            )

        probe_runner_interface = _lab_sandbox_provider_runtime_probe_runner_interface_payload(
            harness=harness,
            workspace=workspace,
        )
        required_checks = _lab_sandbox_provider_runtime_probe_runner_readiness_required_checks()
        current_checks = _lab_sandbox_provider_runtime_probe_runner_readiness_current_checks(
            harness=harness,
            probe_runner_interface=probe_runner_interface,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "service_query_performed",
                "process_launched",
                "container_launched",
            )
        )
        blockers = _append_unique(
            harness.blockers,
            *missing_checks,
            "sandbox_provider_runtime_probe_runner_readiness_blocked",
        )
        status = "refused" if unsafe_state else "ready" if not blockers else "blocked"
        now = utc_now()
        readiness = LabSandboxProviderRuntimeProbeRunnerReadiness(
            id=_lab_sandbox_provider_runtime_probe_runner_readiness_id(harness.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_provider_runtime_probe_harness_id=harness.id,
            sandbox_provider_runtime_probe_id=harness.sandbox_provider_runtime_probe_id,
            sandbox_provider_verifier_id=harness.sandbox_provider_verifier_id,
            sandbox_provider_selection_id=harness.sandbox_provider_selection_id,
            sandbox_provider_binding_id=harness.sandbox_provider_binding_id,
            sandbox_provider_contract_id=harness.sandbox_provider_contract_id,
            sandbox_readiness_id=harness.sandbox_readiness_id,
            command_allowlist_enforcement_id=harness.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=harness.action,
            action_hash=harness.action_hash,
            runner_kind="francis.lab.sandbox_provider_runtime_probe_runner_readiness",
            runner_mode="probe_runner_interface_readiness_only_no_provider_execution",
            provider_kind=harness.provider_kind,
            provider_reference=harness.provider_reference,
            provider_identity=harness.provider_identity,
            probe_runner_interface=probe_runner_interface,
            probe_runner_boundary={
                "mode": "future_sandboxed_probe_runner_interface_no_execution",
                "probe_runner_implementation_bound": False,
                "probe_runner_identity_bound": False,
                "probe_runner_sandbox_bound": False,
                "provider_runtime_probe_performed": False,
                "service_query_performed": False,
                "process_launched": False,
                "container_launched": False,
                "repo_code_executed": False,
            },
            sandbox_provider_runtime_probe_harness=harness.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            runtime_probe_harness_present=bool(current_checks.get("runtime_probe_harness_present")),
            runtime_probe_harness_contract_declared=bool(current_checks.get("runtime_probe_harness_contract_declared")),
            probe_runner_interface_declared=bool(current_checks.get("probe_runner_interface_declared")),
            probe_runner_implementation_bound=bool(current_checks.get("probe_runner_implementation_bound")),
            probe_runner_identity_bound=bool(current_checks.get("probe_runner_identity_bound")),
            probe_runner_policy_bound=bool(current_checks.get("probe_runner_policy_bound")),
            probe_runner_sandbox_bound=bool(current_checks.get("probe_runner_sandbox_bound")),
            probe_runner_network_blocked=bool(current_checks.get("probe_runner_network_blocked")),
            probe_runner_workspace_isolated=bool(current_checks.get("probe_runner_workspace_isolated")),
            probe_runner_timeout_bound=bool(current_checks.get("probe_runner_timeout_bound")),
            probe_runner_output_capture_bound=bool(current_checks.get("probe_runner_output_capture_bound")),
            probe_runner_kill_switch_bound=bool(current_checks.get("probe_runner_kill_switch_bound")),
            probe_runner_receipt_contract_bound=bool(current_checks.get("probe_runner_receipt_contract_bound")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_runtime_probe_runner_readiness_only",
                    "probe_runner_implementation_not_bound",
                    "probe_runner_identity_not_bound",
                    "probe_runner_sandbox_not_bound",
                    "provider_runtime_probe_not_performed",
                    "provider_binary_not_executed",
                    "provider_service_not_queried",
                    "container_not_launched",
                    "repository_code_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "sandbox_provider_runtime_probe_harness_readback",
                "probe_runner_interface_declared",
                "probe_runner_required_controls_declared",
                "probe_runner_implementation_not_bound",
                "probe_runner_identity_not_bound",
                "probe_runner_sandbox_not_bound",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "container_not_launched",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_runner_readiness",
            readiness.id,
            {"sandbox_provider_runtime_probe_runner_readiness": readiness.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe_runner.readiness",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(harness_result.get("sandbox_provider_runtime_probe_path")).strip(),
                    _safe_str(harness_result.get("sandbox_provider_runtime_probe_harness_path")).strip(),
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(probe_runner_interface),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=readiness.warnings,
            errors=readiness.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=readiness.validation_performed,
        )
        readiness = replace(readiness, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_runner_readiness",
            readiness.id,
            {"sandbox_provider_runtime_probe_runner_readiness": readiness.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_runtime_probe_runner_readiness_path": str(artifact_path),
            "last_lab_sandbox_provider_runtime_probe_runner_readiness_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_runtime_probe_runner_readiness_status": status,
            "last_lab_sandbox_provider_runtime_probe_runner_readiness_missing_checks": missing_checks,
            "last_lab_sandbox_provider_runtime_probe_runner_readiness_mode": readiness.runner_mode,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": readiness.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "sandbox_provider_runtime_probe": runtime_probe.to_dict(),
                "sandbox_provider_runtime_probe_harness": harness.to_dict(),
                "sandbox_provider_runtime_probe_runner_readiness": readiness.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_runner_readiness_path": str(artifact_path),
                "reserved_execution_receipt": harness_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(
                    reason="sandbox_provider_runtime_probe_runner_readiness_no_execution"
                ),
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe_runner_binding(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        provider_kind: str = "",
        provider_reference: str = "",
        provider_policy_manifest: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        readiness_result = self.preflight_lab_sandbox_provider_runtime_probe_runner_readiness(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            provider_kind=provider_kind,
            provider_reference=provider_reference,
            provider_policy_manifest=provider_policy_manifest,
            actor=actor,
        )
        readiness = LabSandboxProviderRuntimeProbeRunnerReadiness.from_dict(
            readiness_result.get("sandbox_provider_runtime_probe_runner_readiness")
        )
        harness = LabSandboxProviderRuntimeProbeHarnessPreflight.from_dict(
            readiness_result.get("sandbox_provider_runtime_probe_harness")
        )
        runtime_probe = LabSandboxProviderRuntimeProbePreflight.from_dict(
            readiness_result.get("sandbox_provider_runtime_probe")
        )
        preflight = LabExecutionPreflight.from_dict(readiness_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(readiness_result.get("workspace"))
        source = SourceRecord.from_dict(readiness_result.get("source"))
        if (
            readiness is None
            or harness is None
            or runtime_probe is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **readiness_result,
                    "status": "failed",
                    "error": "lab_sandbox_provider_runtime_probe_runner_readiness_unavailable",
                    "execution": _no_lab_execution_payload(
                        reason="lab_sandbox_provider_runtime_probe_runner_readiness_unavailable"
                    ),
                }
            )

        binding_contract = _lab_sandbox_provider_runtime_probe_runner_binding_contract_payload(
            readiness=readiness,
            workspace=workspace,
        )
        required_checks = _lab_sandbox_provider_runtime_probe_runner_binding_required_checks()
        current_checks = _lab_sandbox_provider_runtime_probe_runner_binding_current_checks(
            readiness=readiness,
            binding_contract=binding_contract,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "service_query_performed",
                "process_launched",
                "container_launched",
            )
        )
        blockers = _append_unique(
            readiness.blockers,
            *missing_checks,
            "sandbox_provider_runtime_probe_runner_binding_preflight_blocked",
        )
        status = "refused" if unsafe_state else "ready" if not blockers else "blocked"
        now = utc_now()
        binding = LabSandboxProviderRuntimeProbeRunnerBindingPreflight(
            id=_lab_sandbox_provider_runtime_probe_runner_binding_id(readiness.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_provider_runtime_probe_runner_readiness_id=readiness.id,
            sandbox_provider_runtime_probe_harness_id=readiness.sandbox_provider_runtime_probe_harness_id,
            sandbox_provider_runtime_probe_id=readiness.sandbox_provider_runtime_probe_id,
            sandbox_provider_verifier_id=readiness.sandbox_provider_verifier_id,
            sandbox_provider_selection_id=readiness.sandbox_provider_selection_id,
            sandbox_provider_binding_id=readiness.sandbox_provider_binding_id,
            sandbox_provider_contract_id=readiness.sandbox_provider_contract_id,
            sandbox_readiness_id=readiness.sandbox_readiness_id,
            command_allowlist_enforcement_id=readiness.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=readiness.action,
            action_hash=readiness.action_hash,
            runner_kind="francis.lab.sandbox_provider_runtime_probe_runner_binding_preflight",
            binding_mode="probe_runner_binding_preflight_no_provider_execution",
            provider_kind=readiness.provider_kind,
            provider_reference=readiness.provider_reference,
            provider_identity=readiness.provider_identity,
            probe_runner_binding_contract=binding_contract,
            sandbox_provider_runtime_probe_runner_readiness=readiness.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            runner_readiness_present=bool(current_checks.get("runner_readiness_present")),
            probe_runner_interface_declared=bool(current_checks.get("probe_runner_interface_declared")),
            probe_runner_readiness_ready=bool(current_checks.get("probe_runner_readiness_ready")),
            probe_runner_binding_contract_declared=bool(current_checks.get("probe_runner_binding_contract_declared")),
            probe_runner_implementation_bound=bool(current_checks.get("probe_runner_implementation_bound")),
            probe_runner_identity_bound=bool(current_checks.get("probe_runner_identity_bound")),
            probe_runner_policy_bound=bool(current_checks.get("probe_runner_policy_bound")),
            probe_runner_sandbox_bound=bool(current_checks.get("probe_runner_sandbox_bound")),
            probe_runner_network_blocked=bool(current_checks.get("probe_runner_network_blocked")),
            probe_runner_workspace_isolated=bool(current_checks.get("probe_runner_workspace_isolated")),
            probe_runner_timeout_bound=bool(current_checks.get("probe_runner_timeout_bound")),
            probe_runner_output_capture_bound=bool(current_checks.get("probe_runner_output_capture_bound")),
            probe_runner_kill_switch_bound=bool(current_checks.get("probe_runner_kill_switch_bound")),
            probe_runner_receipt_contract_bound=bool(current_checks.get("probe_runner_receipt_contract_bound")),
            probe_runner_bound=bool(current_checks.get("probe_runner_bound")),
            runtime_probe_bound=bool(current_checks.get("runtime_probe_bound")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_runtime_probe_runner_binding_preflight_only",
                    "probe_runner_readiness_not_ready",
                    "probe_runner_binding_not_live",
                    "runtime_probe_not_bound",
                    "provider_runtime_probe_not_performed",
                    "provider_binary_not_executed",
                    "provider_service_not_queried",
                    "process_not_launched",
                    "container_not_launched",
                    "repository_code_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "sandbox_provider_runtime_probe_runner_readiness_readback",
                "probe_runner_binding_contract_declared",
                "probe_runner_binding_not_live",
                "runtime_probe_not_bound",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_runner_bindings",
            binding.id,
            {"sandbox_provider_runtime_probe_runner_binding": binding.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe_runner.binding_preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(readiness_result.get("sandbox_provider_runtime_probe_runner_readiness_path")).strip(),
                    _safe_str(readiness_result.get("sandbox_provider_runtime_probe_harness_path")).strip(),
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(binding_contract),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=binding.warnings,
            errors=binding.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=binding.validation_performed,
        )
        binding = replace(binding, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_runner_bindings",
            binding.id,
            {"sandbox_provider_runtime_probe_runner_binding": binding.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_runtime_probe_runner_binding_path": str(artifact_path),
            "last_lab_sandbox_provider_runtime_probe_runner_binding_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_runtime_probe_runner_binding_status": status,
            "last_lab_sandbox_provider_runtime_probe_runner_binding_missing_checks": missing_checks,
            "last_lab_sandbox_provider_runtime_probe_runner_binding_mode": binding.binding_mode,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": binding.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "sandbox_provider_runtime_probe": runtime_probe.to_dict(),
                "sandbox_provider_runtime_probe_harness": harness.to_dict(),
                "sandbox_provider_runtime_probe_runner_readiness": readiness.to_dict(),
                "sandbox_provider_runtime_probe_runner_binding": binding.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_runner_binding_path": str(artifact_path),
                "reserved_execution_receipt": readiness_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(
                    reason="sandbox_provider_runtime_probe_runner_binding_preflight_no_execution"
                ),
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe_runner_enforcement(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        provider_kind: str = "",
        provider_reference: str = "",
        provider_policy_manifest: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        binding_result = self.preflight_lab_sandbox_provider_runtime_probe_runner_binding(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            provider_kind=provider_kind,
            provider_reference=provider_reference,
            provider_policy_manifest=provider_policy_manifest,
            actor=actor,
        )
        binding = LabSandboxProviderRuntimeProbeRunnerBindingPreflight.from_dict(
            binding_result.get("sandbox_provider_runtime_probe_runner_binding")
        )
        readiness = LabSandboxProviderRuntimeProbeRunnerReadiness.from_dict(
            binding_result.get("sandbox_provider_runtime_probe_runner_readiness")
        )
        harness = LabSandboxProviderRuntimeProbeHarnessPreflight.from_dict(
            binding_result.get("sandbox_provider_runtime_probe_harness")
        )
        runtime_probe = LabSandboxProviderRuntimeProbePreflight.from_dict(
            binding_result.get("sandbox_provider_runtime_probe")
        )
        preflight = LabExecutionPreflight.from_dict(binding_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(binding_result.get("workspace"))
        source = SourceRecord.from_dict(binding_result.get("source"))
        if (
            binding is None
            or readiness is None
            or harness is None
            or runtime_probe is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **binding_result,
                    "status": "failed",
                    "error": "lab_sandbox_provider_runtime_probe_runner_binding_unavailable",
                    "execution": _no_lab_execution_payload(
                        reason="lab_sandbox_provider_runtime_probe_runner_binding_unavailable"
                    ),
                }
            )

        enforcement_contract = _lab_sandbox_provider_runtime_probe_runner_enforcement_contract_payload(
            binding=binding,
            workspace=workspace,
        )
        required_checks = _lab_sandbox_provider_runtime_probe_runner_enforcement_required_checks()
        current_checks = _lab_sandbox_provider_runtime_probe_runner_enforcement_current_checks(
            binding=binding,
            enforcement_contract=enforcement_contract,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "service_query_performed",
                "process_launched",
                "container_launched",
            )
        )
        blockers = _append_unique(
            binding.blockers,
            *missing_checks,
            "sandbox_provider_runtime_probe_runner_enforcement_preflight_blocked",
        )
        status = "refused" if unsafe_state else "ready" if not blockers else "blocked"
        now = utc_now()
        enforcement = LabSandboxProviderRuntimeProbeRunnerEnforcementPreflight(
            id=_lab_sandbox_provider_runtime_probe_runner_enforcement_id(binding.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_provider_runtime_probe_runner_binding_id=binding.id,
            sandbox_provider_runtime_probe_runner_readiness_id=binding.sandbox_provider_runtime_probe_runner_readiness_id,
            sandbox_provider_runtime_probe_harness_id=binding.sandbox_provider_runtime_probe_harness_id,
            sandbox_provider_runtime_probe_id=binding.sandbox_provider_runtime_probe_id,
            sandbox_provider_verifier_id=binding.sandbox_provider_verifier_id,
            sandbox_provider_selection_id=binding.sandbox_provider_selection_id,
            sandbox_provider_binding_id=binding.sandbox_provider_binding_id,
            sandbox_provider_contract_id=binding.sandbox_provider_contract_id,
            sandbox_readiness_id=binding.sandbox_readiness_id,
            command_allowlist_enforcement_id=binding.command_allowlist_enforcement_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=binding.action,
            action_hash=binding.action_hash,
            runner_kind="francis.lab.sandbox_provider_runtime_probe_runner_enforcement_preflight",
            enforcement_mode="probe_runner_enforcement_preflight_no_provider_execution",
            provider_kind=binding.provider_kind,
            provider_reference=binding.provider_reference,
            provider_identity=binding.provider_identity,
            probe_runner_enforcement_contract=enforcement_contract,
            sandbox_provider_runtime_probe_runner_binding=binding.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            runner_binding_present=bool(current_checks.get("runner_binding_present")),
            probe_runner_binding_contract_declared=bool(current_checks.get("probe_runner_binding_contract_declared")),
            probe_runner_binding_ready=bool(current_checks.get("probe_runner_binding_ready")),
            probe_runner_enforcement_contract_declared=bool(
                current_checks.get("probe_runner_enforcement_contract_declared")
            ),
            probe_runner_enforcement_bound=bool(current_checks.get("probe_runner_enforcement_bound")),
            probe_runner_bound=bool(current_checks.get("probe_runner_bound")),
            runtime_probe_bound=bool(current_checks.get("runtime_probe_bound")),
            probe_runner_identity_bound=bool(current_checks.get("probe_runner_identity_bound")),
            probe_runner_policy_bound=bool(current_checks.get("probe_runner_policy_bound")),
            probe_runner_sandbox_bound=bool(current_checks.get("probe_runner_sandbox_bound")),
            probe_runner_network_blocked=bool(current_checks.get("probe_runner_network_blocked")),
            probe_runner_workspace_isolated=bool(current_checks.get("probe_runner_workspace_isolated")),
            probe_runner_timeout_bound=bool(current_checks.get("probe_runner_timeout_bound")),
            probe_runner_output_capture_bound=bool(current_checks.get("probe_runner_output_capture_bound")),
            probe_runner_kill_switch_bound=bool(current_checks.get("probe_runner_kill_switch_bound")),
            probe_runner_receipt_contract_bound=bool(current_checks.get("probe_runner_receipt_contract_bound")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            warnings=_append_unique(
                [
                    "sandbox_provider_runtime_probe_runner_enforcement_preflight_only",
                    "probe_runner_binding_not_ready",
                    "probe_runner_enforcement_not_live",
                    "probe_runner_binding_not_live",
                    "runtime_probe_not_bound",
                    "provider_runtime_probe_not_performed",
                    "provider_binary_not_executed",
                    "provider_service_not_queried",
                    "process_not_launched",
                    "container_not_launched",
                    "repository_code_not_executed",
                    "approval_not_consumed",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "sandbox_provider_runtime_probe_runner_binding_readback",
                "probe_runner_enforcement_contract_declared",
                "probe_runner_enforcement_not_live",
                "probe_runner_binding_not_live",
                "runtime_probe_not_bound",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_runner_enforcements",
            enforcement.id,
            {"sandbox_provider_runtime_probe_runner_enforcement": enforcement.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe_runner.enforcement_preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(binding_result.get("sandbox_provider_runtime_probe_runner_binding_path")).strip(),
                    _safe_str(binding_result.get("sandbox_provider_runtime_probe_runner_readiness_path")).strip(),
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(enforcement_contract),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=enforcement.warnings,
            errors=enforcement.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=enforcement.validation_performed,
        )
        enforcement = replace(enforcement, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_runner_enforcements",
            enforcement.id,
            {"sandbox_provider_runtime_probe_runner_enforcement": enforcement.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandbox_provider_runtime_probe_runner_enforcement_path": str(artifact_path),
            "last_lab_sandbox_provider_runtime_probe_runner_enforcement_receipt_path": str(receipt_path),
            "last_lab_sandbox_provider_runtime_probe_runner_enforcement_status": status,
            "last_lab_sandbox_provider_runtime_probe_runner_enforcement_missing_checks": missing_checks,
            "last_lab_sandbox_provider_runtime_probe_runner_enforcement_mode": enforcement.enforcement_mode,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": enforcement.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "sandbox_provider_runtime_probe": runtime_probe.to_dict(),
                "sandbox_provider_runtime_probe_harness": harness.to_dict(),
                "sandbox_provider_runtime_probe_runner_readiness": readiness.to_dict(),
                "sandbox_provider_runtime_probe_runner_binding": binding.to_dict(),
                "sandbox_provider_runtime_probe_runner_enforcement": enforcement.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_runner_enforcement_path": str(artifact_path),
                "reserved_execution_receipt": binding_result.get("reserved_execution_receipt"),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(
                    reason="sandbox_provider_runtime_probe_runner_enforcement_preflight_no_execution"
                ),
            }
        )

    def preflight_lab_execution_receipt_write_readiness(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        sandbox_result = self.preflight_lab_runner_sandbox_readiness(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(sandbox_result.get("runner_sandbox_readiness"))
        allowlist_enforcement = LabRunnerCommandAllowlistEnforcementPreflight.from_dict(
            sandbox_result.get("runner_command_allowlist_enforcement")
        )
        reservation = LabExecutionReceiptSinkReservation.from_dict(
            sandbox_result.get("execution_receipt_sink_reservation")
        )
        handoff = LabApprovalConsumptionHandoff.from_dict(sandbox_result.get("approval_consumption_handoff"))
        runner_enforcement = LabRunnerEnforcementPreflight.from_dict(sandbox_result.get("runner_enforcement"))
        binding_preflight = LabRunnerBindingPreflight.from_dict(sandbox_result.get("runner_binding"))
        readiness = LabRunnerReadiness.from_dict(sandbox_result.get("runner_readiness"))
        preflight = LabExecutionPreflight.from_dict(sandbox_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(sandbox_result.get("workspace"))
        source = SourceRecord.from_dict(sandbox_result.get("source"))
        if (
            sandbox_readiness is None
            or allowlist_enforcement is None
            or reservation is None
            or handoff is None
            or runner_enforcement is None
            or binding_preflight is None
            or readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **sandbox_result,
                    "status": "failed",
                    "error": "lab_runner_sandbox_readiness_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_runner_sandbox_readiness_unavailable"),
                }
            )

        required_checks = _lab_execution_receipt_write_required_checks()
        current_checks = _lab_execution_receipt_write_current_checks(
            sandbox_readiness=sandbox_readiness,
            reservation=reservation,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = (
            sandbox_readiness.status == "refused"
            or allowlist_enforcement.status == "refused"
            or reservation.status == "refused"
            or handoff.status == "refused"
        )
        blockers = _append_unique(
            sandbox_readiness.blockers,
            *missing_checks,
            "execution_receipt_write_readiness_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        receipt_write_readiness = LabExecutionReceiptWriteReadiness(
            id=_lab_execution_receipt_write_readiness_id(sandbox_readiness.id, clean_approval_id),
            approval_id=clean_approval_id,
            sandbox_readiness_id=sandbox_readiness.id,
            command_allowlist_enforcement_id=allowlist_enforcement.id,
            receipt_sink_reservation_id=reservation.id,
            approval_handoff_id=handoff.id,
            runner_enforcement_id=runner_enforcement.id,
            runner_binding_id=binding_preflight.id,
            runner_readiness_id=readiness.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            reserved_execution_receipt=reservation.reserved_execution_receipt,
            receipt_write_contract=_lab_execution_receipt_write_contract(
                sandbox_readiness=sandbox_readiness,
                reservation=reservation,
            ),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            receipt_schema_bound=False,
            prewrite_bound=False,
            final_write_bound=False,
            execution_receipt_prewritten=False,
            execution_receipt_finalized=False,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_receipt_write_readiness",
            receipt_write_readiness.id,
            {"execution_receipt_write_readiness": receipt_write_readiness.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.receipt_write_readiness.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(sandbox_result.get("runner_sandbox_readiness_path")).strip(),
                ],
                handoff.approval_path,
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "runner_sandbox_readiness_readback_no_execution",
                "reserved_execution_receipt_path_checked_without_write",
                "execution_receipt_schema_not_bound",
                "execution_receipt_prewrite_not_bound",
                "execution_receipt_final_write_not_bound",
                "execution_receipt_not_prewritten",
                "execution_receipt_not_finalized",
                "commands_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        receipt_write_readiness = replace(receipt_write_readiness, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_receipt_write_readiness",
            receipt_write_readiness.id,
            {"execution_receipt_write_readiness": receipt_write_readiness.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_execution_receipt_write_readiness_path": str(artifact_path),
            "last_lab_execution_receipt_write_readiness_receipt_path": str(receipt_path),
            "last_lab_execution_receipt_write_readiness_status": status,
            "last_lab_execution_receipt_write_readiness_missing_checks": missing_checks,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "approval": handoff.approval_snapshot,
                "approval_path": handoff.approval_path,
                "approval_binding": handoff.approval_binding,
                "runner_readiness": readiness.to_dict(),
                "runner_binding": binding_preflight.to_dict(),
                "runner_enforcement": runner_enforcement.to_dict(),
                "approval_consumption_handoff": handoff.to_dict(),
                "execution_receipt_sink_reservation": reservation.to_dict(),
                "runner_command_allowlist_enforcement": allowlist_enforcement.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "execution_receipt_write_readiness": receipt_write_readiness.to_dict(),
                "artifact_path": str(artifact_path),
                "execution_receipt_write_readiness_path": str(artifact_path),
                "reserved_execution_receipt": reservation.reserved_execution_receipt,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="execution_receipt_write_readiness_no_execution"),
            }
        )

    def preflight_lab_execution_receipt_prewrite_binding(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        readiness_result = self.preflight_lab_execution_receipt_write_readiness(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        write_readiness = LabExecutionReceiptWriteReadiness.from_dict(
            readiness_result.get("execution_receipt_write_readiness")
        )
        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(readiness_result.get("runner_sandbox_readiness"))
        preflight = LabExecutionPreflight.from_dict(readiness_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(readiness_result.get("workspace"))
        source = SourceRecord.from_dict(readiness_result.get("source"))
        if (
            write_readiness is None
            or sandbox_readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **readiness_result,
                    "status": "failed",
                    "error": "lab_execution_receipt_write_readiness_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_execution_receipt_write_readiness_unavailable"),
                }
            )

        schema = _lab_execution_receipt_schema_contract(write_readiness=write_readiness)
        schema_hash = _stable_payload_hash(schema)
        prewrite_contract = _lab_execution_receipt_prewrite_contract(
            write_readiness=write_readiness,
            schema_hash=schema_hash,
        )
        prewrite_contract_hash = _stable_payload_hash(prewrite_contract)
        final_write_contract = _lab_execution_receipt_final_write_contract(
            write_readiness=write_readiness,
            schema_hash=schema_hash,
            prewrite_contract_hash=prewrite_contract_hash,
        )
        final_write_contract_hash = _stable_payload_hash(final_write_contract)
        contract_binding = _lab_execution_receipt_prewrite_binding_contract(
            write_readiness=write_readiness,
            schema_hash=schema_hash,
            prewrite_contract_hash=prewrite_contract_hash,
            final_write_contract_hash=final_write_contract_hash,
        )
        required_checks = _lab_execution_receipt_prewrite_binding_required_checks()
        current_checks = _lab_execution_receipt_prewrite_binding_current_checks(
            write_readiness=write_readiness,
            schema_hash=schema_hash,
            prewrite_contract_hash=prewrite_contract_hash,
            final_write_contract_hash=final_write_contract_hash,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = write_readiness.status == "refused"
        blockers = _append_unique(
            missing_checks,
            "execution_receipt_prewrite_binding_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        prewrite_binding = LabExecutionReceiptPrewriteBinding(
            id=_lab_execution_receipt_prewrite_binding_id(write_readiness.id, clean_approval_id),
            approval_id=clean_approval_id,
            receipt_write_readiness_id=write_readiness.id,
            sandbox_readiness_id=write_readiness.sandbox_readiness_id,
            command_allowlist_enforcement_id=write_readiness.command_allowlist_enforcement_id,
            receipt_sink_reservation_id=write_readiness.receipt_sink_reservation_id,
            preflight_id=write_readiness.preflight_id,
            plan_id=write_readiness.plan_id,
            workspace_id=write_readiness.workspace_id,
            source_id=write_readiness.source_id,
            candidate_id=write_readiness.candidate_id,
            candidate_name=write_readiness.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action=write_readiness.action,
            action_hash=write_readiness.action_hash,
            reserved_execution_receipt=write_readiness.reserved_execution_receipt,
            execution_receipt_schema=schema,
            prewrite_contract=prewrite_contract,
            final_write_contract=final_write_contract,
            contract_binding=contract_binding,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            upstream_blockers=write_readiness.blockers,
            receipt_schema_bound=True,
            prewrite_contract_bound=True,
            final_write_contract_bound=True,
            prewrite_writer_bound=False,
            final_write_writer_bound=False,
            execution_receipt_prewritten=False,
            execution_receipt_finalized=False,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_receipt_prewrite_bindings",
            prewrite_binding.id,
            {"execution_receipt_prewrite_binding": prewrite_binding.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.receipt_prewrite_binding.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(readiness_result.get("execution_receipt_write_readiness_path")).strip(),
                ],
                _safe_str(write_readiness.reserved_execution_receipt.get("path")).strip(),
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                schema_hash,
                prewrite_contract_hash,
                final_write_contract_hash,
            ],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "execution_receipt_write_readiness_readback_no_execution",
                "execution_receipt_schema_contract_bound",
                "execution_receipt_prewrite_contract_bound",
                "execution_receipt_final_write_contract_bound",
                "reserved_execution_receipt_not_written",
                "execution_receipt_writer_not_bound",
                "execution_receipt_not_prewritten",
                "execution_receipt_not_finalized",
                "commands_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        prewrite_binding = replace(prewrite_binding, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_receipt_prewrite_bindings",
            prewrite_binding.id,
            {"execution_receipt_prewrite_binding": prewrite_binding.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_execution_receipt_prewrite_binding_path": str(artifact_path),
            "last_lab_execution_receipt_prewrite_binding_receipt_path": str(receipt_path),
            "last_lab_execution_receipt_prewrite_binding_status": status,
            "last_lab_execution_receipt_prewrite_binding_missing_checks": missing_checks,
            "last_lab_execution_receipt_schema_hash": schema_hash,
            "last_lab_execution_receipt_prewrite_contract_hash": prewrite_contract_hash,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "execution_receipt_write_readiness": write_readiness.to_dict(),
                "execution_receipt_prewrite_binding": prewrite_binding.to_dict(),
                "artifact_path": str(artifact_path),
                "execution_receipt_prewrite_binding_path": str(artifact_path),
                "reserved_execution_receipt": write_readiness.reserved_execution_receipt,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="execution_receipt_prewrite_binding_no_execution"),
            }
        )

    def preflight_lab_execution_receipt_writer(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        binding_result = self.preflight_lab_execution_receipt_prewrite_binding(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        prewrite_binding = LabExecutionReceiptPrewriteBinding.from_dict(
            binding_result.get("execution_receipt_prewrite_binding")
        )
        write_readiness = LabExecutionReceiptWriteReadiness.from_dict(
            binding_result.get("execution_receipt_write_readiness")
        )
        preflight = LabExecutionPreflight.from_dict(binding_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(binding_result.get("workspace"))
        source = SourceRecord.from_dict(binding_result.get("source"))
        if (
            prewrite_binding is None
            or write_readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    **binding_result,
                    "status": "failed",
                    "error": "lab_execution_receipt_prewrite_binding_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_execution_receipt_prewrite_binding_unavailable"),
                }
            )

        writer_boundary = _lab_execution_receipt_writer_boundary(prewrite_binding=prewrite_binding)
        writer_contract = _lab_execution_receipt_writer_contract(
            prewrite_binding=prewrite_binding,
            writer_boundary=writer_boundary,
        )
        writer_contract_hash = _stable_payload_hash(writer_contract)
        prewrite_operation = _lab_execution_receipt_writer_prewrite_operation(
            prewrite_binding=prewrite_binding,
            writer_contract_hash=writer_contract_hash,
        )
        final_write_operation = _lab_execution_receipt_writer_final_write_operation(
            prewrite_binding=prewrite_binding,
            writer_contract_hash=writer_contract_hash,
        )
        required_checks = _lab_execution_receipt_writer_required_checks()
        current_checks = _lab_execution_receipt_writer_current_checks(
            prewrite_binding=prewrite_binding,
            writer_boundary=writer_boundary,
            writer_contract_hash=writer_contract_hash,
            prewrite_operation=prewrite_operation,
            final_write_operation=final_write_operation,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = prewrite_binding.status == "refused"
        blockers = _append_unique(
            missing_checks,
            "execution_receipt_writer_preflight_blocked",
        )
        status = "refused" if refused else "ready" if not blockers else "blocked"
        now = utc_now()
        writer_preflight = LabExecutionReceiptWriterPreflight(
            id=_lab_execution_receipt_writer_preflight_id(prewrite_binding.id, clean_approval_id),
            approval_id=clean_approval_id,
            receipt_prewrite_binding_id=prewrite_binding.id,
            receipt_write_readiness_id=prewrite_binding.receipt_write_readiness_id,
            sandbox_readiness_id=prewrite_binding.sandbox_readiness_id,
            command_allowlist_enforcement_id=prewrite_binding.command_allowlist_enforcement_id,
            receipt_sink_reservation_id=prewrite_binding.receipt_sink_reservation_id,
            preflight_id=prewrite_binding.preflight_id,
            plan_id=prewrite_binding.plan_id,
            workspace_id=prewrite_binding.workspace_id,
            source_id=prewrite_binding.source_id,
            candidate_id=prewrite_binding.candidate_id,
            candidate_name=prewrite_binding.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=prewrite_binding.action,
            action_hash=prewrite_binding.action_hash,
            reserved_execution_receipt=prewrite_binding.reserved_execution_receipt,
            writer_contract=writer_contract,
            prewrite_operation=prewrite_operation,
            final_write_operation=final_write_operation,
            writer_boundary=writer_boundary,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            upstream_blockers=prewrite_binding.blockers,
            writer_interface_declared=True,
            writer_implementation_bound=False,
            writer_path_within_sink=bool(current_checks.get("reserved_execution_receipt_path_within_sink")),
            atomic_write_plan_declared=True,
            redaction_policy_bound=True,
            prewrite_writer_bound=False,
            final_write_writer_bound=False,
            execution_receipt_prewritten=False,
            execution_receipt_finalized=False,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_receipt_writer_preflights",
            writer_preflight.id,
            {"execution_receipt_writer_preflight": writer_preflight.to_dict()},
        )
        reserved_path = _safe_str(prewrite_binding.reserved_execution_receipt.get("path")).strip()
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.receipt_writer.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(binding_result.get("execution_receipt_prewrite_binding_path")).strip(),
                ],
                reserved_path,
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                writer_contract_hash,
            ],
            result_status=status,
            warnings=blockers,
            errors=blockers if refused else [],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "execution_receipt_prewrite_binding_readback_no_execution",
                "execution_receipt_writer_boundary_declared",
                "execution_receipt_writer_atomic_write_plan_declared",
                "execution_receipt_writer_redaction_policy_bound",
                "reserved_execution_receipt_path_within_sink_checked",
                "reserved_execution_receipt_not_written",
                "execution_receipt_writer_not_implemented",
                "execution_receipt_not_prewritten",
                "execution_receipt_not_finalized",
                "commands_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        writer_preflight = replace(writer_preflight, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_receipt_writer_preflights",
            writer_preflight.id,
            {"execution_receipt_writer_preflight": writer_preflight.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_execution_receipt_writer_preflight_path": str(artifact_path),
            "last_lab_execution_receipt_writer_preflight_receipt_path": str(receipt_path),
            "last_lab_execution_receipt_writer_preflight_status": status,
            "last_lab_execution_receipt_writer_preflight_missing_checks": missing_checks,
            "last_lab_execution_receipt_writer_contract_hash": writer_contract_hash,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "execution_receipt_write_readiness": write_readiness.to_dict(),
                "execution_receipt_prewrite_binding": prewrite_binding.to_dict(),
                "execution_receipt_writer_preflight": writer_preflight.to_dict(),
                "artifact_path": str(artifact_path),
                "execution_receipt_writer_preflight_path": str(artifact_path),
                "reserved_execution_receipt": prewrite_binding.reserved_execution_receipt,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="execution_receipt_writer_preflight_no_execution"),
            }
        )

    def prewrite_lab_synthetic_execution_receipt(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        writer_result = self.preflight_lab_execution_receipt_writer(
            source_or_path,
            candidate_ref,
            approval_id,
            actor=actor,
        )
        writer_preflight = LabExecutionReceiptWriterPreflight.from_dict(
            writer_result.get("execution_receipt_writer_preflight")
        )
        prewrite_binding = LabExecutionReceiptPrewriteBinding.from_dict(
            writer_result.get("execution_receipt_prewrite_binding")
        )
        source = SourceRecord.from_dict(writer_result.get("source"))
        if writer_preflight is None or prewrite_binding is None or source is None:
            return _display_payload(
                {
                    **writer_result,
                    "ok": False,
                    "status": "failed",
                    "error": "lab_execution_receipt_writer_preflight_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_execution_receipt_writer_preflight_unavailable"),
                }
            )

        reserved = writer_preflight.reserved_execution_receipt
        reserved_path = _safe_str(reserved.get("path")).strip()
        reserved_file = Path(reserved_path) if reserved_path else None
        approval_blockers = _lab_synthetic_execution_receipt_approval_blockers(writer_preflight)
        blockers = _append_unique(
            [],
            *approval_blockers,
            *(
                []
                if bool(writer_preflight.current_checks.get("reserved_execution_receipt_path_within_sink"))
                else ["reserved_execution_receipt_path_outside_sink"]
            ),
            *(
                []
                if reserved_file is not None and not reserved_file.exists()
                else ["reserved_execution_receipt_already_written"]
            ),
        )
        if blockers:
            return _display_payload(
                {
                    **writer_result,
                    "ok": False,
                    "status": "blocked",
                    "error": "synthetic_execution_receipt_prewrite_blocked",
                    "blockers": blockers,
                    "execution": _no_lab_execution_payload(reason="synthetic_execution_receipt_prewrite_blocked"),
                }
            )

        now = utc_now()
        execution_receipt = _lab_synthetic_execution_receipt(
            writer_preflight=writer_preflight,
            prewrite_binding=prewrite_binding,
            actor=actor,
            phase="prewrite",
            status="prewritten",
            result_status="prewritten",
            created_at=now,
            updated_at=now,
            finalized_at="",
            warnings=[
                "synthetic_noop_execution_receipt_only",
                "repository_code_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
                "live_runner_not_bound",
            ],
            validation_performed=[
                "execution_receipt_writer_preflight_readback",
                "reserved_execution_receipt_path_within_sink",
                "synthetic_noop_receipt_prewritten",
                "commands_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = _write_lab_execution_receipt_artifact(execution_receipt)
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.receipt.synthetic_prewrite",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    _safe_str(writer_result.get("execution_receipt_writer_preflight_path")).strip(),
                ],
                reserved_path,
            ),
            input_hashes=[
                source.fingerprint,
                prewrite_binding.action_hash,
                _stable_payload_hash(writer_preflight.writer_contract),
            ],
            result_status=execution_receipt.status,
            warnings=execution_receipt.warnings,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=execution_receipt.validation_performed,
        )
        execution_receipt = replace(execution_receipt, receipts=[str(receipt_path)])
        artifact_path = _write_lab_execution_receipt_artifact(execution_receipt)
        updated = self._record_lab_execution_receipt_artifact(
            source=source,
            artifact_path=artifact_path,
            receipt_path=receipt_path,
            execution_receipt=execution_receipt,
        )
        return _display_payload(
            {
                "ok": True,
                "status": execution_receipt.status,
                "source": updated.to_dict(),
                "execution_receipt_writer_preflight": writer_preflight.to_dict(),
                "execution_receipt_prewrite_binding": prewrite_binding.to_dict(),
                "execution_receipt": execution_receipt.to_dict(),
                "artifact_path": str(artifact_path),
                "execution_receipt_path": str(artifact_path),
                "reserved_execution_receipt": reserved,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="synthetic_execution_receipt_prewrite_no_execution"),
            }
        )

    def finalize_lab_synthetic_execution_receipt(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        writer_result = self.preflight_lab_execution_receipt_writer(
            source_or_path,
            candidate_ref,
            approval_id,
            actor=actor,
        )
        writer_preflight = LabExecutionReceiptWriterPreflight.from_dict(
            writer_result.get("execution_receipt_writer_preflight")
        )
        prewrite_binding = LabExecutionReceiptPrewriteBinding.from_dict(
            writer_result.get("execution_receipt_prewrite_binding")
        )
        source = SourceRecord.from_dict(writer_result.get("source"))
        if writer_preflight is None or prewrite_binding is None or source is None:
            return _display_payload(
                {
                    **writer_result,
                    "ok": False,
                    "status": "failed",
                    "error": "lab_execution_receipt_writer_preflight_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_execution_receipt_writer_preflight_unavailable"),
                }
            )

        reserved = writer_preflight.reserved_execution_receipt
        reserved_path = _safe_str(reserved.get("path")).strip()
        existing_payload = _as_dict(_read_json(reserved_path).get("execution_receipt")) if reserved_path else {}
        existing = LabSyntheticExecutionReceipt.from_dict(existing_payload)
        approval_blockers = _lab_synthetic_execution_receipt_approval_blockers(writer_preflight)
        blockers = _append_unique(
            [],
            *approval_blockers,
            *(
                []
                if bool(writer_preflight.current_checks.get("reserved_execution_receipt_path_within_sink"))
                else ["reserved_execution_receipt_path_outside_sink"]
            ),
            *([] if existing is not None else ["synthetic_execution_receipt_prewrite_missing"]),
            *(
                []
                if existing is None or existing.id == _safe_str(reserved.get("id")).strip()
                else ["synthetic_execution_receipt_id_mismatch"]
            ),
            *(
                []
                if existing is None or (existing.synthetic and existing.noop)
                else ["execution_receipt_not_synthetic"]
            ),
            *([] if existing is None or not existing.executed else ["execution_receipt_claims_execution"]),
        )
        if blockers:
            return _display_payload(
                {
                    **writer_result,
                    "ok": False,
                    "status": "blocked",
                    "error": "synthetic_execution_receipt_finalize_blocked",
                    "blockers": blockers,
                    "execution": _no_lab_execution_payload(reason="synthetic_execution_receipt_finalize_blocked"),
                }
            )

        assert existing is not None
        now = utc_now()
        execution_receipt = replace(
            existing,
            phase="finalize",
            status="blocked",
            result_status="blocked",
            updated_at=now,
            finalized_at=now,
            finalized=True,
            prewritten=True,
            warnings=_append_unique(
                existing.warnings,
                "synthetic_noop_execution_receipt_finalized",
                "repository_code_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
                "live_runner_not_bound",
            ),
            validation_performed=_append_unique(
                existing.validation_performed,
                "synthetic_noop_receipt_finalized",
                "commands_not_executed",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ),
            approval_consumed=False,
            execution_authority=False,
            executed=False,
            ran_repo_scripts=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            repo_code_executed=False,
        )
        artifact_path = _write_lab_execution_receipt_artifact(execution_receipt)
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.receipt.synthetic_finalize",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    _safe_str(writer_result.get("execution_receipt_writer_preflight_path")).strip(),
                ],
                reserved_path,
            ),
            input_hashes=[
                source.fingerprint,
                prewrite_binding.action_hash,
                _stable_payload_hash(existing.to_dict()),
            ],
            result_status=execution_receipt.status,
            warnings=execution_receipt.warnings,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=execution_receipt.validation_performed,
        )
        execution_receipt = replace(
            execution_receipt,
            receipts=_append_unique(execution_receipt.receipts, str(receipt_path)),
        )
        artifact_path = _write_lab_execution_receipt_artifact(execution_receipt)
        updated = self._record_lab_execution_receipt_artifact(
            source=source,
            artifact_path=artifact_path,
            receipt_path=receipt_path,
            execution_receipt=execution_receipt,
        )
        return _display_payload(
            {
                "ok": True,
                "status": execution_receipt.status,
                "source": updated.to_dict(),
                "execution_receipt_writer_preflight": writer_preflight.to_dict(),
                "execution_receipt_prewrite_binding": prewrite_binding.to_dict(),
                "execution_receipt": execution_receipt.to_dict(),
                "artifact_path": str(artifact_path),
                "execution_receipt_path": str(artifact_path),
                "reserved_execution_receipt": reserved,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="synthetic_execution_receipt_finalize_no_execution"),
            }
        )

    def consume_lab_approval_for_synthetic_execution_receipt(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        writer_result = self.preflight_lab_execution_receipt_writer(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        writer_preflight = LabExecutionReceiptWriterPreflight.from_dict(
            writer_result.get("execution_receipt_writer_preflight")
        )
        prewrite_binding = LabExecutionReceiptPrewriteBinding.from_dict(
            writer_result.get("execution_receipt_prewrite_binding")
        )
        preflight = LabExecutionPreflight.from_dict(writer_result.get("preflight"))
        source = SourceRecord.from_dict(writer_result.get("source"))
        if writer_preflight is None or prewrite_binding is None or preflight is None or source is None:
            return _display_payload(
                {
                    **writer_result,
                    "ok": False,
                    "status": "failed",
                    "error": "lab_execution_receipt_writer_preflight_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_execution_receipt_writer_preflight_unavailable"),
                }
            )

        approval_status, approval_record, approval_path = _read_lab_approval_record(clean_approval_id)
        binding, approval_blockers = _lab_approval_binding(
            preflight=preflight,
            approval_id=clean_approval_id,
            approval_status=approval_status,
            approval_record=approval_record,
            approval_path=approval_path,
        )
        existing_consumption, existing_consumption_path = _find_lab_approval_consumption(clean_approval_id)
        reserved = writer_preflight.reserved_execution_receipt
        reserved_path = _safe_str(reserved.get("path")).strip()
        existing_payload = _as_dict(_read_json(reserved_path).get("execution_receipt")) if reserved_path else {}
        existing = LabSyntheticExecutionReceipt.from_dict(existing_payload)
        blockers = _append_unique(
            [],
            *approval_blockers,
            *(
                []
                if bool(writer_preflight.current_checks.get("reserved_execution_receipt_path_within_sink"))
                else ["reserved_execution_receipt_path_outside_sink"]
            ),
            *([] if existing is not None else ["synthetic_execution_receipt_finalize_missing"]),
            *(
                []
                if existing is None or existing.id == _safe_str(reserved.get("id")).strip()
                else ["synthetic_execution_receipt_id_mismatch"]
            ),
            *(
                []
                if existing is None or (existing.synthetic and existing.noop)
                else ["execution_receipt_not_synthetic"]
            ),
            *([] if existing is None or existing.finalized else ["synthetic_execution_receipt_not_finalized"]),
            *([] if existing is None or not existing.executed else ["execution_receipt_claims_execution"]),
            *([] if existing_consumption is None else ["approval_already_consumed"]),
        )
        refused = bool(binding.get("refused"))
        if blockers:
            return _display_payload(
                {
                    **writer_result,
                    "ok": False,
                    "status": "refused" if refused else "blocked",
                    "error": "lab_approval_consumption_blocked",
                    "blockers": blockers,
                    "existing_approval_consumption_path": (
                        str(existing_consumption_path) if existing_consumption_path is not None else ""
                    ),
                    "approval_binding": binding,
                    "execution": _no_lab_execution_payload(reason="lab_approval_consumption_blocked"),
                }
            )

        assert existing is not None
        now = utc_now()
        consumption = LabApprovalConsumptionRecord(
            id=_lab_approval_consumption_record_id(clean_approval_id, existing.id),
            approval_id=clean_approval_id,
            synthetic_execution_receipt_id=existing.id,
            writer_preflight_id=writer_preflight.id,
            receipt_prewrite_binding_id=writer_preflight.receipt_prewrite_binding_id,
            receipt_write_readiness_id=writer_preflight.receipt_write_readiness_id,
            receipt_sink_reservation_id=writer_preflight.receipt_sink_reservation_id,
            preflight_id=writer_preflight.preflight_id,
            plan_id=writer_preflight.plan_id,
            workspace_id=writer_preflight.workspace_id,
            source_id=writer_preflight.source_id,
            candidate_id=writer_preflight.candidate_id,
            candidate_name=writer_preflight.candidate_name,
            status="consumed",
            created_at=now,
            updated_at=now,
            consumed_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=writer_preflight.action,
            action_hash=writer_preflight.action_hash,
            approval_status=approval_status,
            approval_path=str(approval_path) if approval_path is not None else "",
            approval_snapshot=_lab_approval_snapshot(approval_record),
            approval_binding=binding,
            synthetic_execution_receipt=existing.to_dict(),
            approval_consumed=True,
            single_use_enforced=True,
            execution_authority=False,
            executed=False,
            ran_repo_scripts=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            repo_code_executed=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=[
                "approval_consumed_for_synthetic_noop_receipt_only",
                "repository_code_not_executed",
                "execution_authority_not_granted",
                "approval_reuse_blocked_by_consumption_record",
            ],
            validation_performed=[
                "approved_exact_action_binding_checked",
                "synthetic_noop_execution_receipt_finalized",
                "approval_consumption_record_written",
                "single_use_consumption_record_declared",
                "commands_not_executed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_approval_consumptions",
            consumption.id,
            {"approval_consumption_record": consumption.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.approval.consume_synthetic_noop",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    _safe_str(writer_result.get("execution_receipt_writer_preflight_path")).strip(),
                    existing.reserved_execution_receipt.get("path", ""),
                    str(approval_path) if approval_path is not None else "",
                ],
            ),
            input_hashes=[
                source.fingerprint,
                writer_preflight.action_hash,
                _stable_payload_hash(existing.to_dict()),
                _stable_payload_hash(binding),
            ],
            result_status=consumption.status,
            warnings=consumption.warnings,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=consumption.validation_performed,
        )
        consumption = replace(consumption, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_approval_consumptions",
            consumption.id,
            {"approval_consumption_record": consumption.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_approval_consumption_record_path": str(artifact_path),
            "last_lab_approval_consumption_record_receipt_path": str(receipt_path),
            "last_lab_approval_consumption_record_status": consumption.status,
            "last_lab_approval_consumed": consumption.approval_consumed,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": writer_preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": consumption.status,
                "source": updated.to_dict(),
                "approval_consumption_record": consumption.to_dict(),
                "approval_binding": binding,
                "execution_receipt_writer_preflight": writer_preflight.to_dict(),
                "execution_receipt": existing.to_dict(),
                "artifact_path": str(artifact_path),
                "approval_consumption_record_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="approval_consumed_for_synthetic_noop_no_execution"),
            }
        )

    def run_lab_noop_runner_envelope(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _no_lab_execution_payload(reason="capability_candidate_unavailable"),
                }
            )

        consumption, consumption_path = _find_lab_approval_consumption(clean_approval_id)
        consumption_payload = consumption.to_dict() if consumption is not None else {}
        synthetic_snapshot = LabSyntheticExecutionReceipt.from_dict(
            _as_dict(consumption_payload.get("synthetic_execution_receipt"))
        )
        synthetic_path = ""
        if synthetic_snapshot is not None:
            synthetic_path = _safe_str(synthetic_snapshot.reserved_execution_receipt.get("path")).strip()
        synthetic_current = (
            LabSyntheticExecutionReceipt.from_dict(_as_dict(_read_json(synthetic_path).get("execution_receipt")))
            if synthetic_path
            else None
        )
        synthetic = synthetic_current or synthetic_snapshot
        envelope_id = _lab_noop_runner_envelope_id(
            consumption.id if consumption is not None else clean_approval_id,
            source.id,
            candidate.id,
        )
        envelope_path = ingest_artifact_root() / "lab_noop_runner_envelopes" / f"{envelope_id}.json"
        required_checks = _lab_noop_runner_envelope_required_checks()
        current_checks = _lab_noop_runner_envelope_current_checks(
            source=source,
            candidate=candidate,
            approval_id=clean_approval_id,
            consumption=consumption,
            synthetic=synthetic,
            envelope_path=envelope_path,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(missing_checks, *(["lab_noop_runner_envelope_blocked"] if missing_checks else []))
        prior_envelope_path = _safe_str(current_checks.get("prior_noop_runner_envelope_path")).strip()
        if "noop_runner_envelope_not_already_completed" in missing_checks and prior_envelope_path:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "lab_noop_runner_envelope_already_completed",
                    "source": source.to_dict(),
                    "blockers": blockers,
                    "prior_noop_runner_envelope_path": prior_envelope_path,
                    "execution": _lab_noop_runner_execution_payload(
                        noop_performed=False,
                        reason="lab_noop_runner_envelope_already_completed_without_repo_execution",
                    ),
                }
            )
        refused = any(
            check in missing_checks
            for check in (
                "approval_consumption_record_found",
                "source_identity_matches_consumption",
                "candidate_identity_matches_consumption",
                "synthetic_execution_receipt_present",
                "synthetic_execution_receipt_noop",
                "synthetic_execution_receipt_no_repo_execution",
            )
        )
        status = "completed" if not blockers else "refused" if refused else "blocked"
        noop_performed = status == "completed"
        now = utc_now()
        envelope = LabNoopRunnerEnvelope(
            id=envelope_id,
            approval_id=clean_approval_id,
            approval_consumption_record_id=consumption.id if consumption is not None else "",
            synthetic_execution_receipt_id=synthetic.id if synthetic is not None else "",
            preflight_id=consumption.preflight_id if consumption is not None else "",
            plan_id=consumption.plan_id if consumption is not None else "",
            workspace_id=consumption.workspace_id if consumption is not None else "",
            source_id=source.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=consumption.action if consumption is not None else "francis.lab.execute",
            action_hash=consumption.action_hash if consumption is not None else "",
            approval_consumption_record_path=str(consumption_path) if consumption_path is not None else "",
            synthetic_execution_receipt_path=synthetic_path,
            approval_consumption_record=consumption_payload,
            synthetic_execution_receipt=synthetic.to_dict() if synthetic is not None else {},
            required_checks=required_checks,
            current_checks=current_checks,
            blockers=blockers,
            noop_performed=noop_performed,
            approval_consumed=bool(consumption and consumption.approval_consumed),
            single_use_enforced=bool(consumption and consumption.single_use_enforced),
            execution_authority=False,
            executed=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_repo_scripts=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=[
                "builtin_noop_runner_envelope_only",
                "repository_code_not_executed",
                "commands_not_executed",
                "execution_authority_not_granted",
            ],
            errors=blockers if status != "completed" else [],
            validation_performed=[
                "approval_consumption_record_readback",
                "synthetic_noop_execution_receipt_readback",
                "source_candidate_identity_checked",
                "builtin_noop_runner_envelope_completed" if noop_performed else "builtin_noop_runner_envelope_blocked",
                "commands_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_noop_runner_envelopes",
            envelope.id,
            {"noop_runner_envelope": envelope.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.noop_envelope",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(consumption_path) if consumption_path is not None else "",
                    synthetic_path,
                ],
            ),
            input_hashes=[
                source.fingerprint,
                envelope.action_hash,
                _stable_payload_hash(consumption_payload),
                _stable_payload_hash(synthetic.to_dict() if synthetic is not None else {}),
            ],
            result_status=status,
            warnings=envelope.warnings,
            errors=envelope.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=envelope.validation_performed,
        )
        envelope = replace(envelope, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_noop_runner_envelopes",
            envelope.id,
            {"noop_runner_envelope": envelope.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_noop_runner_envelope_path": str(artifact_path),
            "last_lab_noop_runner_envelope_receipt_path": str(receipt_path),
            "last_lab_noop_runner_envelope_status": status,
            "last_lab_noop_runner_envelope_noop_performed": noop_performed,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": envelope.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": status == "completed",
                "status": status,
                "source": updated.to_dict(),
                "noop_runner_envelope": envelope.to_dict(),
                "approval_consumption_record": consumption_payload,
                "execution_receipt": synthetic.to_dict() if synthetic is not None else {},
                "artifact_path": str(artifact_path),
                "noop_runner_envelope_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _lab_noop_runner_execution_payload(
                    noop_performed=noop_performed,
                    reason=(
                        "lab_noop_runner_envelope_completed_without_repo_execution"
                        if noop_performed
                        else "lab_noop_runner_envelope_blocked_without_repo_execution"
                    ),
                ),
            }
        )

    def capture_lab_noop_runner_transcript(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _no_lab_execution_payload(reason="capability_candidate_unavailable"),
                }
            )

        consumption, _consumption_path = _find_lab_approval_consumption(clean_approval_id)
        envelope, envelope_path = _find_lab_noop_runner_envelope(consumption.id if consumption is not None else "")
        envelope_payload = envelope.to_dict() if envelope is not None else {}
        transcript_id = _lab_noop_runner_transcript_id(
            envelope.id if envelope is not None else clean_approval_id,
            source.id,
            candidate.id,
        )
        transcript_path = ingest_artifact_root() / "lab_noop_runner_transcripts" / f"{transcript_id}.json"
        stdout = _noop_output_stream("stdout")
        stderr = _noop_output_stream("stderr")
        combined_output_hash = _noop_combined_output_hash(stdout, stderr)
        required_checks = _lab_noop_runner_transcript_required_checks()
        current_checks = _lab_noop_runner_transcript_current_checks(
            source=source,
            candidate=candidate,
            envelope=envelope,
            transcript_path=transcript_path,
            stdout=stdout,
            stderr=stderr,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(missing_checks, *(["lab_noop_runner_transcript_blocked"] if missing_checks else []))
        prior_transcript_path = _safe_str(current_checks.get("prior_noop_runner_transcript_path")).strip()
        if "noop_runner_transcript_not_already_completed" in missing_checks and prior_transcript_path:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "lab_noop_runner_transcript_already_completed",
                    "source": source.to_dict(),
                    "blockers": blockers,
                    "prior_noop_runner_transcript_path": prior_transcript_path,
                    "execution": _lab_noop_runner_transcript_execution_payload(
                        transcript_captured=False,
                        reason="lab_noop_runner_transcript_already_completed_without_repo_execution",
                    ),
                }
            )
        refused = any(
            check in missing_checks
            for check in (
                "source_identity_matches_envelope",
                "candidate_identity_matches_envelope",
                "noop_runner_envelope_not_repo_execution",
                "output_content_not_stored",
                "real_process_output_not_claimed",
            )
        )
        status = "completed" if not blockers else "refused" if refused else "blocked"
        transcript_captured = status == "completed"
        now = utc_now()
        transcript = LabNoopRunnerTranscript(
            id=transcript_id,
            noop_runner_envelope_id=envelope.id if envelope is not None else "",
            approval_id=clean_approval_id,
            approval_consumption_record_id=envelope.approval_consumption_record_id if envelope is not None else "",
            synthetic_execution_receipt_id=envelope.synthetic_execution_receipt_id if envelope is not None else "",
            source_id=source.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=envelope.action if envelope is not None else "francis.lab.execute",
            action_hash=envelope.action_hash if envelope is not None else "",
            noop_runner_envelope_path=str(envelope_path) if envelope_path is not None else "",
            noop_runner_envelope=envelope_payload,
            stdout=stdout,
            stderr=stderr,
            combined_output_hash=combined_output_hash,
            required_checks=required_checks,
            current_checks=current_checks,
            blockers=blockers,
            noop_performed=bool(envelope and envelope.noop_performed),
            builtin_noop_output_captured=transcript_captured,
            real_process_output_captured=False,
            stdout_content_stored=False,
            stderr_content_stored=False,
            output_content_stored=False,
            execution_authority=False,
            executed=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_repo_scripts=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=[
                "builtin_noop_transcript_only",
                "stdout_empty_no_process_output",
                "stderr_empty_no_process_output",
                "output_content_not_stored",
                "repository_code_not_executed",
                "commands_not_executed",
                "execution_authority_not_granted",
            ],
            errors=blockers if status != "completed" else [],
            validation_performed=[
                "noop_runner_envelope_readback",
                "builtin_noop_output_streams_declared_empty",
                "output_hashes_recorded",
                "output_content_not_stored",
                "commands_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_noop_runner_transcripts",
            transcript.id,
            {"noop_runner_transcript": transcript.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.noop_transcript",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(envelope_path) if envelope_path is not None else "",
                ],
            ),
            input_hashes=[
                source.fingerprint,
                transcript.action_hash,
                _stable_payload_hash(envelope_payload),
                combined_output_hash,
            ],
            result_status=status,
            warnings=transcript.warnings,
            errors=transcript.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=transcript.validation_performed,
        )
        transcript = replace(transcript, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_noop_runner_transcripts",
            transcript.id,
            {"noop_runner_transcript": transcript.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_noop_runner_transcript_path": str(artifact_path),
            "last_lab_noop_runner_transcript_receipt_path": str(receipt_path),
            "last_lab_noop_runner_transcript_status": status,
            "last_lab_noop_runner_transcript_captured": transcript_captured,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": transcript.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": status == "completed",
                "status": status,
                "source": updated.to_dict(),
                "noop_runner_transcript": transcript.to_dict(),
                "noop_runner_envelope": envelope_payload,
                "artifact_path": str(artifact_path),
                "noop_runner_transcript_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _lab_noop_runner_transcript_execution_payload(
                    transcript_captured=transcript_captured,
                    reason=(
                        "lab_noop_runner_transcript_completed_without_repo_execution"
                        if transcript_captured
                        else "lab_noop_runner_transcript_blocked_without_repo_execution"
                    ),
                ),
            }
        )

    def bind_lab_noop_runner_identity(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _no_lab_execution_payload(reason="capability_candidate_unavailable"),
                }
            )

        consumption, _consumption_path = _find_lab_approval_consumption(clean_approval_id)
        envelope, envelope_path = _find_lab_noop_runner_envelope(consumption.id if consumption is not None else "")
        transcript, transcript_path = _find_lab_noop_runner_transcript(envelope.id if envelope is not None else "")
        transcript_payload = transcript.to_dict() if transcript is not None else {}
        envelope_payload = envelope.to_dict() if envelope is not None else {}
        runner_identity = _noop_runner_identity_payload()
        binding_id = _lab_noop_runner_identity_binding_id(
            transcript.id if transcript is not None else clean_approval_id,
            source.id,
            candidate.id,
        )
        binding_path = ingest_artifact_root() / "lab_noop_runner_identity_bindings" / f"{binding_id}.json"
        required_checks = _lab_noop_runner_identity_binding_required_checks()
        current_checks = _lab_noop_runner_identity_binding_current_checks(
            source=source,
            candidate=candidate,
            transcript=transcript,
            envelope=envelope,
            binding_path=binding_path,
            runner_identity=runner_identity,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(
            missing_checks,
            *(["lab_noop_runner_identity_binding_blocked"] if missing_checks else []),
        )
        prior_binding_path = _safe_str(current_checks.get("prior_noop_runner_identity_binding_path")).strip()
        if "noop_runner_identity_not_already_completed" in missing_checks and prior_binding_path:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "lab_noop_runner_identity_binding_already_completed",
                    "source": source.to_dict(),
                    "blockers": blockers,
                    "prior_noop_runner_identity_binding_path": prior_binding_path,
                    "execution": _lab_noop_runner_identity_binding_execution_payload(
                        identity_bound=False,
                        reason="lab_noop_runner_identity_binding_already_completed_without_repo_execution",
                    ),
                }
            )
        refused = any(
            check in missing_checks
            for check in (
                "source_identity_matches_transcript",
                "candidate_identity_matches_transcript",
                "noop_runner_transcript_not_repo_execution",
                "runner_identity_builtin_noop",
                "runner_identity_denies_repo_execution",
                "live_runner_not_bound",
                "sandbox_runner_not_bound",
            )
        )
        status = "completed" if not blockers else "refused" if refused else "blocked"
        identity_bound = status == "completed"
        now = utc_now()
        binding = LabNoopRunnerIdentityBinding(
            id=binding_id,
            noop_runner_transcript_id=transcript.id if transcript is not None else "",
            noop_runner_envelope_id=envelope.id if envelope is not None else "",
            approval_id=clean_approval_id,
            approval_consumption_record_id=envelope.approval_consumption_record_id if envelope is not None else "",
            synthetic_execution_receipt_id=envelope.synthetic_execution_receipt_id if envelope is not None else "",
            source_id=source.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=transcript.action if transcript is not None else "francis.lab.execute",
            action_hash=transcript.action_hash if transcript is not None else "",
            noop_runner_transcript_path=str(transcript_path) if transcript_path is not None else "",
            noop_runner_envelope_path=str(envelope_path) if envelope_path is not None else "",
            noop_runner_transcript=transcript_payload,
            noop_runner_envelope=envelope_payload,
            runner_identity=runner_identity,
            required_checks=required_checks,
            current_checks=current_checks,
            blockers=blockers,
            runner_identity_bound=identity_bound,
            builtin_noop_only=True,
            live_runner_bound=False,
            sandbox_runner_bound=False,
            execution_authority=False,
            executed=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_repo_scripts=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            real_process_output_captured=False,
            candidate_validated=False,
            capability_promoted=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=[
                "builtin_noop_runner_identity_only",
                "live_runner_not_bound",
                "sandbox_runner_not_bound",
                "repository_code_not_executed",
                "commands_not_executed",
                "execution_authority_not_granted",
                "candidate_not_validated",
                "capability_not_promoted",
            ],
            errors=blockers if status != "completed" else [],
            validation_performed=[
                "noop_runner_transcript_readback",
                "noop_runner_envelope_readback",
                "builtin_noop_runner_identity_bound" if identity_bound else "builtin_noop_runner_identity_blocked",
                "live_runner_not_bound",
                "sandbox_runner_not_bound",
                "commands_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_authority_not_granted",
                "candidate_not_validated",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_noop_runner_identity_bindings",
            binding.id,
            {"noop_runner_identity_binding": binding.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.runner.noop_identity_bind",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(transcript_path) if transcript_path is not None else "",
                    str(envelope_path) if envelope_path is not None else "",
                ],
            ),
            input_hashes=[
                source.fingerprint,
                binding.action_hash,
                _stable_payload_hash(transcript_payload),
                _stable_payload_hash(envelope_payload),
                _stable_payload_hash(runner_identity),
            ],
            result_status=status,
            warnings=binding.warnings,
            errors=binding.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=binding.validation_performed,
        )
        binding = replace(binding, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_noop_runner_identity_bindings",
            binding.id,
            {"noop_runner_identity_binding": binding.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_noop_runner_identity_binding_path": str(artifact_path),
            "last_lab_noop_runner_identity_binding_receipt_path": str(receipt_path),
            "last_lab_noop_runner_identity_binding_status": status,
            "last_lab_noop_runner_identity_bound": identity_bound,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": binding.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": status == "completed",
                "status": status,
                "source": updated.to_dict(),
                "noop_runner_identity_binding": binding.to_dict(),
                "noop_runner_transcript": transcript_payload,
                "noop_runner_envelope": envelope_payload,
                "artifact_path": str(artifact_path),
                "noop_runner_identity_binding_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _lab_noop_runner_identity_binding_execution_payload(
                    identity_bound=identity_bound,
                    reason=(
                        "lab_noop_runner_identity_binding_completed_without_repo_execution"
                        if identity_bound
                        else "lab_noop_runner_identity_binding_blocked_without_repo_execution"
                    ),
                ),
            }
        )

    def preflight_lab_source_mount_readiness(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        workspace_result = self.prepare_lab_workspace(source_or_path, candidate_ref, actor=actor)
        workspace = LabWorkspaceRecord.from_dict(workspace_result.get("workspace"))
        source = SourceRecord.from_dict(workspace_result.get("source"))
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor) if source is not None else None
        if workspace is None or source is None or candidate is None:
            return _display_payload(
                {
                    **workspace_result,
                    "status": "failed",
                    "error": "lab_workspace_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_workspace_unavailable"),
                }
            )

        consumption, _consumption_path = _find_lab_approval_consumption(clean_approval_id)
        envelope, _envelope_path = _find_lab_noop_runner_envelope(consumption.id if consumption is not None else "")
        transcript, _transcript_path = _find_lab_noop_runner_transcript(envelope.id if envelope is not None else "")
        identity, identity_path = _find_lab_noop_runner_identity_binding(
            transcript.id if transcript is not None else ""
        )
        identity_payload = identity.to_dict() if identity is not None else {}
        readiness_id = _lab_source_mount_readiness_id(
            identity.id if identity is not None else clean_approval_id,
            workspace.id,
            source.id,
            candidate.id,
        )
        required_checks = _lab_source_mount_readiness_required_checks()
        current_checks = _lab_source_mount_readiness_current_checks(
            source=source,
            candidate=candidate,
            workspace=workspace,
            identity=identity,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = any(
            check in missing_checks
            for check in (
                "source_reference_identity_matches_source",
                "identity_binding_source_matches_source",
                "identity_binding_candidate_matches_candidate",
                "noop_runner_identity_builtin_noop",
                "noop_runner_identity_no_repo_execution",
                "source_write_not_allowed",
                "execution_authority_absent",
            )
        )
        blockers = _append_unique(
            missing_checks,
            *(["source_mount_readiness_blocked"] if missing_checks else []),
        )
        status = "ready" if not blockers else "refused" if refused else "blocked"
        source_reference = _as_dict(workspace.source_reference)
        now = utc_now()
        readiness = LabSourceMountReadiness(
            id=readiness_id,
            noop_runner_identity_binding_id=identity.id if identity is not None else "",
            noop_runner_transcript_id=identity.noop_runner_transcript_id if identity is not None else "",
            noop_runner_envelope_id=identity.noop_runner_envelope_id if identity is not None else "",
            approval_id=clean_approval_id,
            approval_consumption_record_id=identity.approval_consumption_record_id if identity is not None else "",
            synthetic_execution_receipt_id=identity.synthetic_execution_receipt_id if identity is not None else "",
            workspace_id=workspace.id,
            plan_id=workspace.plan_id,
            source_id=source.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=identity.action if identity is not None else "francis.lab.execute",
            action_hash=identity.action_hash if identity is not None else "",
            source_mount_mode="reference_only_read_only",
            mount_kind="source_reference_readiness",
            workspace_path=workspace.path,
            workspace_manifest_path=workspace.manifest_path,
            noop_runner_identity_binding_path=str(identity_path) if identity_path is not None else "",
            workspace=workspace.to_dict(),
            source_reference=source_reference,
            noop_runner_identity_binding=identity_payload,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            source_reference_ready=bool(current_checks.get("workspace_source_reference_present")),
            read_only_reference_confirmed=bool(current_checks.get("source_reference_mode_read_only")),
            read_only_mount_bound=False,
            source_mount_enforced=False,
            source_copied=False,
            source_write_allowed=False,
            runner_identity_verified=bool(current_checks.get("noop_runner_identity_binding_completed")),
            builtin_noop_only=True,
            live_runner_bound=False,
            sandbox_runner_bound=False,
            execution_authority=False,
            executed=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_repo_scripts=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            candidate_validated=False,
            capability_promoted=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=_append_unique(
                [
                    "source_mount_readiness_only",
                    "read_only_mount_not_bound",
                    "source_mount_enforcement_not_claimed",
                    "live_runner_not_bound",
                    "sandbox_runner_not_bound",
                    "repository_code_not_executed",
                    "commands_not_executed",
                    "execution_authority_not_granted",
                    "candidate_not_validated",
                    "capability_not_promoted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "workspace_source_reference_readback",
                "source_reference_mode_read_only_checked",
                "source_not_copied_checked",
                "source_write_not_allowed_checked",
                "noop_runner_identity_binding_readback",
                "read_only_mount_not_bound",
                "source_mount_enforcement_not_claimed",
                "live_runner_not_bound",
                "sandbox_runner_not_bound",
                "commands_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_authority_not_granted",
                "candidate_not_validated",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_source_mount_readiness",
            readiness.id,
            {"source_mount_readiness": readiness.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.source_mount.readiness",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    str(identity_path) if identity_path is not None else "",
                ],
            ),
            input_hashes=[
                source.fingerprint,
                readiness.action_hash,
                _stable_payload_hash(source_reference),
                _stable_payload_hash(identity_payload),
            ],
            result_status=status,
            warnings=readiness.warnings,
            errors=readiness.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=readiness.validation_performed,
        )
        readiness = replace(readiness, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_source_mount_readiness",
            readiness.id,
            {"source_mount_readiness": readiness.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_source_mount_readiness_path": str(artifact_path),
            "last_lab_source_mount_readiness_receipt_path": str(receipt_path),
            "last_lab_source_mount_readiness_status": status,
            "last_lab_source_mount_readiness_missing_checks": missing_checks,
            "last_lab_source_mount_readiness_mount_mode": readiness.source_mount_mode,
            "last_lab_source_mount_enforced": False,
            "last_lab_read_only_mount_bound": False,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": readiness.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "workspace": workspace.to_dict(),
                "source_mount_readiness": readiness.to_dict(),
                "noop_runner_identity_binding": identity_payload,
                "artifact_path": str(artifact_path),
                "source_mount_readiness_path": str(artifact_path),
                "noop_runner_identity_binding_path": str(identity_path) if identity_path is not None else "",
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _lab_source_mount_readiness_execution_payload(
                    recorded=True,
                    identity_bound=identity is not None and identity.status == "completed",
                    source_reference_ready=bool(current_checks.get("workspace_source_reference_present"))
                    and bool(current_checks.get("source_reference_mode_read_only")),
                    ready=status == "ready",
                    reason=(
                        "lab_source_mount_readiness_ready_without_mount_or_repo_execution"
                        if status == "ready"
                        else "lab_source_mount_readiness_blocked_without_mount_or_repo_execution"
                    ),
                ),
            }
        )

    def preflight_lab_source_mount_contract(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        readiness_result = self.preflight_lab_source_mount_readiness(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        readiness = LabSourceMountReadiness.from_dict(readiness_result.get("source_mount_readiness"))
        workspace = LabWorkspaceRecord.from_dict(readiness_result.get("workspace"))
        source = SourceRecord.from_dict(readiness_result.get("source"))
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor) if source is not None else None
        readiness_path = _safe_str(readiness_result.get("source_mount_readiness_path")).strip()
        if readiness is None or workspace is None or source is None or candidate is None:
            return _display_payload(
                {
                    **readiness_result,
                    "status": "failed",
                    "error": "lab_source_mount_readiness_unavailable",
                    "execution": _lab_source_mount_contract_execution_payload(
                        recorded=False,
                        identity_bound=False,
                        source_reference_ready=False,
                        readiness_ready=False,
                        contract_declared=False,
                        reason="lab_source_mount_readiness_unavailable",
                    ),
                }
            )

        contract_id = _lab_source_mount_contract_id(readiness.id, source.id, candidate.id)
        contract_payload = _lab_source_mount_contract_payload(
            source=source,
            candidate=candidate,
            workspace=workspace,
            readiness=readiness,
        )
        required_checks = _lab_source_mount_contract_required_checks()
        current_checks = _lab_source_mount_contract_current_checks(
            source=source,
            candidate=candidate,
            workspace=workspace,
            readiness=readiness,
            contract_payload=contract_payload,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        refused = any(
            check in missing_checks
            for check in (
                "source_reference_identity_matches_source",
                "source_reference_mode_read_only",
                "source_reference_fingerprint_matches_source",
                "read_only_mount_not_bound",
                "source_mount_enforcement_not_claimed",
                "source_copy_not_performed",
                "source_write_not_allowed",
                "live_runner_not_bound",
                "sandbox_runner_not_bound",
                "commands_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_authority_absent",
            )
        )
        blockers = _append_unique(
            missing_checks,
            *(["source_mount_contract_blocked"] if missing_checks else []),
        )
        status = "ready" if not blockers else "refused" if refused else "blocked"
        now = utc_now()
        contract = LabSourceMountContract(
            id=contract_id,
            source_mount_readiness_id=readiness.id,
            noop_runner_identity_binding_id=readiness.noop_runner_identity_binding_id,
            approval_id=clean_approval_id,
            workspace_id=workspace.id,
            plan_id=workspace.plan_id,
            source_id=source.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=readiness.action,
            action_hash=readiness.action_hash,
            contract_kind="francis.lab.source_mount_contract",
            contract_version=1,
            contract_mode="contract_only_no_live_mount",
            mount_mode="future_read_only_source_mount",
            workspace_path=workspace.path,
            workspace_manifest_path=workspace.manifest_path,
            source_mount_readiness_path=readiness_path,
            source_mount_contract=contract_payload,
            source_mount_readiness=readiness.to_dict(),
            source_reference=_as_dict(workspace.source_reference),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            contract_declared=status == "ready",
            source_reference_ready=bool(current_checks.get("source_mount_readiness_ready")),
            read_only_reference_confirmed=bool(current_checks.get("source_reference_mode_read_only")),
            live_mount_bound=False,
            mount_enforced=False,
            read_only_mount_bound=False,
            source_copied=False,
            source_write_allowed=False,
            live_runner_bound=False,
            sandbox_runner_bound=False,
            execution_authority=False,
            executed=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_repo_scripts=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            candidate_validated=False,
            capability_promoted=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=_append_unique(
                [
                    "source_mount_contract_only",
                    "live_source_mount_not_bound",
                    "source_mount_enforcement_not_claimed",
                    "source_copy_not_performed",
                    "source_write_not_allowed",
                    "live_runner_not_bound",
                    "sandbox_runner_not_bound",
                    "repository_code_not_executed",
                    "commands_not_executed",
                    "execution_authority_not_granted",
                    "candidate_not_validated",
                    "capability_not_promoted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "source_mount_readiness_readback",
                "source_mount_readiness_status_checked",
                "source_reference_identity_checked",
                "source_reference_fingerprint_checked",
                "source_reference_mode_read_only_checked",
                "workspace_manifest_path_checked",
                "contract_payload_declared",
                "live_source_mount_not_bound",
                "source_mount_enforcement_not_claimed",
                "source_copy_not_performed",
                "source_write_not_allowed_checked",
                "live_runner_not_bound",
                "sandbox_runner_not_bound",
                "commands_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_authority_not_granted",
                "candidate_not_validated",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_source_mount_contracts",
            contract.id,
            {"source_mount_contract": contract.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.source_mount.contract",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    readiness_path,
                ],
            ),
            input_hashes=[
                source.fingerprint,
                readiness.action_hash,
                _stable_payload_hash(_as_dict(workspace.source_reference)),
                _stable_payload_hash(contract_payload),
            ],
            result_status=status,
            warnings=contract.warnings,
            errors=contract.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=contract.validation_performed,
        )
        contract = replace(contract, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_source_mount_contracts",
            contract.id,
            {"source_mount_contract": contract.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_source_mount_contract_path": str(artifact_path),
            "last_lab_source_mount_contract_receipt_path": str(receipt_path),
            "last_lab_source_mount_contract_status": status,
            "last_lab_source_mount_contract_missing_checks": missing_checks,
            "last_lab_source_mount_contract_mode": contract.contract_mode,
            "last_lab_source_mount_contract_mount_mode": contract.mount_mode,
            "last_lab_source_mount_contract_declared": contract.contract_declared,
            "last_lab_source_mount_enforced": False,
            "last_lab_read_only_mount_bound": False,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": contract.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "workspace": workspace.to_dict(),
                "source_mount_contract": contract.to_dict(),
                "source_mount_readiness": readiness.to_dict(),
                "artifact_path": str(artifact_path),
                "source_mount_contract_path": str(artifact_path),
                "source_mount_readiness_path": readiness_path,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _lab_source_mount_contract_execution_payload(
                    recorded=True,
                    identity_bound=bool(readiness.runner_identity_verified),
                    source_reference_ready=bool(current_checks.get("source_reference_mode_read_only")),
                    readiness_ready=readiness.status == "ready",
                    contract_declared=status == "ready",
                    reason=(
                        "lab_source_mount_contract_ready_without_live_mount_or_repo_execution"
                        if status == "ready"
                        else "lab_source_mount_contract_blocked_without_live_mount_or_repo_execution"
                    ),
                ),
            }
        )

    def preflight_lab_run_boundary(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source_contract_result = self.preflight_lab_source_mount_contract(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        writer_result = self.preflight_lab_execution_receipt_writer(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        provider_runtime_probe_runner_enforcement_result = (
            self.preflight_lab_sandbox_provider_runtime_probe_runner_enforcement(
                source_or_path,
                candidate_ref,
                clean_approval_id,
                actor=actor,
            )
        )
        provider_runtime_probe_runner_enforcement = LabSandboxProviderRuntimeProbeRunnerEnforcementPreflight.from_dict(
            provider_runtime_probe_runner_enforcement_result.get("sandbox_provider_runtime_probe_runner_enforcement")
        )
        source_contract = LabSourceMountContract.from_dict(source_contract_result.get("source_mount_contract"))
        writer_preflight = LabExecutionReceiptWriterPreflight.from_dict(
            writer_result.get("execution_receipt_writer_preflight")
        )
        provider_contract_payload = (
            _load_ingest_record_payload(
                "lab_sandbox_provider_contracts",
                "sandbox_provider_contract",
                provider_runtime_probe_runner_enforcement.sandbox_provider_contract_id,
            )
            if provider_runtime_probe_runner_enforcement is not None
            else {}
        )
        provider_binding_payload = (
            _load_ingest_record_payload(
                "lab_sandbox_provider_bindings",
                "sandbox_provider_binding",
                provider_runtime_probe_runner_enforcement.sandbox_provider_binding_id,
            )
            if provider_runtime_probe_runner_enforcement is not None
            else {}
        )
        provider_selection_payload = (
            _load_ingest_record_payload(
                "lab_sandbox_provider_selections",
                "sandbox_provider_selection",
                provider_runtime_probe_runner_enforcement.sandbox_provider_selection_id,
            )
            if provider_runtime_probe_runner_enforcement is not None
            else {}
        )
        provider_verifier_payload = (
            _load_ingest_record_payload(
                "lab_sandbox_provider_verifier_preflights",
                "sandbox_provider_verifier",
                provider_runtime_probe_runner_enforcement.sandbox_provider_verifier_id,
            )
            if provider_runtime_probe_runner_enforcement is not None
            else {}
        )
        provider_runtime_probe_payload = (
            _load_ingest_record_payload(
                "lab_sandbox_provider_runtime_probe_preflights",
                "sandbox_provider_runtime_probe",
                provider_runtime_probe_runner_enforcement.sandbox_provider_runtime_probe_id,
            )
            if provider_runtime_probe_runner_enforcement is not None
            else {}
        )
        provider_runtime_probe_harness_payload = (
            _load_ingest_record_payload(
                "lab_runtime_probe_harness_preflights",
                "sandbox_provider_runtime_probe_harness",
                provider_runtime_probe_runner_enforcement.sandbox_provider_runtime_probe_harness_id,
            )
            if provider_runtime_probe_runner_enforcement is not None
            else {}
        )
        provider_contract = LabSandboxProviderContract.from_dict(provider_contract_payload)
        provider_binding = LabSandboxProviderBindingPreflight.from_dict(provider_binding_payload)
        provider_selection = LabSandboxProviderSelectionPreflight.from_dict(provider_selection_payload)
        provider_verifier = LabSandboxProviderVerifierPreflight.from_dict(provider_verifier_payload)
        provider_runtime_probe = LabSandboxProviderRuntimeProbePreflight.from_dict(provider_runtime_probe_payload)
        provider_runtime_probe_harness = LabSandboxProviderRuntimeProbeHarnessPreflight.from_dict(
            provider_runtime_probe_harness_payload
        )
        prewrite_binding = LabExecutionReceiptPrewriteBinding.from_dict(
            writer_result.get("execution_receipt_prewrite_binding")
        )
        write_readiness = LabExecutionReceiptWriteReadiness.from_dict(
            writer_result.get("execution_receipt_write_readiness")
        )
        preflight = LabExecutionPreflight.from_dict(writer_result.get("preflight"))
        workspace = LabWorkspaceRecord.from_dict(writer_result.get("workspace"))
        source = SourceRecord.from_dict(writer_result.get("source"))
        if (
            source_contract is None
            or writer_preflight is None
            or provider_contract is None
            or provider_binding is None
            or provider_selection is None
            or provider_verifier is None
            or provider_runtime_probe is None
            or provider_runtime_probe_harness is None
            or provider_runtime_probe_runner_enforcement is None
            or prewrite_binding is None
            or write_readiness is None
            or preflight is None
            or workspace is None
            or source is None
        ):
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "lab_run_boundary_upstream_preflight_unavailable",
                    "source_mount_contract_result": source_contract_result,
                    "execution_receipt_writer_result": writer_result,
                    "sandbox_provider_runtime_probe_runner_enforcement_result": (
                        provider_runtime_probe_runner_enforcement_result
                    ),
                    "execution": _lab_run_boundary_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="lab_run_boundary_upstream_preflight_unavailable",
                    ),
                }
            )

        sandbox_readiness = LabRunnerSandboxReadiness.from_dict(
            _load_ingest_record_payload(
                "lab_sandbox_readiness",
                "runner_sandbox_readiness",
                write_readiness.sandbox_readiness_id,
            )
        )
        allowlist_enforcement = LabRunnerCommandAllowlistEnforcementPreflight.from_dict(
            _load_ingest_record_payload(
                "lab_cmd_allowlist_enforcements",
                "runner_command_allowlist_enforcement",
                write_readiness.command_allowlist_enforcement_id,
            )
        )
        approval_handoff = LabApprovalConsumptionHandoff.from_dict(
            _load_ingest_record_payload(
                "lab_approval_consumption_handoffs",
                "approval_handoff",
                write_readiness.approval_handoff_id,
            )
        )
        if sandbox_readiness is None or allowlist_enforcement is None or approval_handoff is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "lab_run_boundary_artifact_readback_unavailable",
                    "source_mount_contract": source_contract.to_dict(),
                    "execution_receipt_writer_preflight": writer_preflight.to_dict(),
                    "execution": _lab_run_boundary_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="lab_run_boundary_artifact_readback_unavailable",
                    ),
                }
            )

        contract_payload = _lab_run_boundary_contract_payload(
            source=source,
            preflight=preflight,
            workspace=workspace,
            source_mount_contract=source_contract,
            writer_preflight=writer_preflight,
            sandbox_readiness=sandbox_readiness,
            sandbox_provider_contract=provider_contract,
            sandbox_provider_binding=provider_binding,
            sandbox_provider_selection=provider_selection,
            sandbox_provider_verifier=provider_verifier,
            sandbox_provider_runtime_probe=provider_runtime_probe,
            sandbox_provider_runtime_probe_harness=provider_runtime_probe_harness,
            sandbox_provider_runtime_probe_runner_enforcement=provider_runtime_probe_runner_enforcement,
            allowlist_enforcement=allowlist_enforcement,
            approval_handoff=approval_handoff,
        )
        required_checks = _lab_run_boundary_required_checks()
        current_checks = _lab_run_boundary_current_checks(
            source_mount_contract=source_contract,
            writer_preflight=writer_preflight,
            sandbox_readiness=sandbox_readiness,
            sandbox_provider_contract=provider_contract,
            sandbox_provider_binding=provider_binding,
            sandbox_provider_selection=provider_selection,
            sandbox_provider_verifier=provider_verifier,
            sandbox_provider_runtime_probe=provider_runtime_probe,
            sandbox_provider_runtime_probe_harness=provider_runtime_probe_harness,
            sandbox_provider_runtime_probe_runner_enforcement=provider_runtime_probe_runner_enforcement,
            allowlist_enforcement=allowlist_enforcement,
            approval_handoff=approval_handoff,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "source_write_allowed",
                "approval_consumed",
                "execution_authority",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "candidate_validated",
                "capability_promoted",
            )
        )
        blockers = _append_unique(
            source_contract.blockers,
            *writer_preflight.blockers,
            *sandbox_readiness.blockers,
            *provider_contract.blockers,
            *provider_binding.blockers,
            *provider_selection.blockers,
            *provider_verifier.blockers,
            *provider_runtime_probe.blockers,
            *provider_runtime_probe_harness.blockers,
            *provider_runtime_probe_runner_enforcement.blockers,
            *allowlist_enforcement.blockers,
            *approval_handoff.blockers,
            *missing_checks,
            "lab_run_boundary_preflight_blocked",
        )
        status = "refused" if unsafe_state else "ready" if not blockers else "blocked"
        now = utc_now()
        boundary = LabRunBoundaryPreflight(
            id=_lab_run_boundary_preflight_id(source_contract.id, writer_preflight.id, clean_approval_id),
            approval_id=clean_approval_id,
            source_mount_contract_id=source_contract.id,
            source_mount_readiness_id=source_contract.source_mount_readiness_id,
            execution_receipt_writer_preflight_id=writer_preflight.id,
            receipt_prewrite_binding_id=writer_preflight.receipt_prewrite_binding_id,
            receipt_write_readiness_id=writer_preflight.receipt_write_readiness_id,
            sandbox_readiness_id=sandbox_readiness.id,
            sandbox_provider_contract_id=provider_contract.id,
            sandbox_provider_binding_id=provider_binding.id,
            sandbox_provider_selection_id=provider_selection.id,
            sandbox_provider_verifier_id=provider_verifier.id,
            sandbox_provider_runtime_probe_id=provider_runtime_probe.id,
            sandbox_provider_runtime_probe_harness_id=provider_runtime_probe_harness.id,
            sandbox_provider_runtime_probe_runner_enforcement_id=provider_runtime_probe_runner_enforcement.id,
            command_allowlist_enforcement_id=allowlist_enforcement.id,
            approval_handoff_id=approval_handoff.id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=workspace.id,
            source_id=source.id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=writer_preflight.action,
            action_hash=writer_preflight.action_hash,
            boundary_kind="francis.lab.run_boundary_preflight",
            boundary_mode="preflight_only_no_execution",
            run_mode="future_sandboxed_rebuild_run_test",
            run_boundary_contract=contract_payload,
            source_mount_contract=source_contract.to_dict(),
            execution_receipt_writer_preflight=writer_preflight.to_dict(),
            runner_sandbox_readiness=sandbox_readiness.to_dict(),
            sandbox_provider_contract=provider_contract.to_dict(),
            sandbox_provider_binding=provider_binding.to_dict(),
            sandbox_provider_selection=provider_selection.to_dict(),
            sandbox_provider_verifier=provider_verifier.to_dict(),
            sandbox_provider_runtime_probe=provider_runtime_probe.to_dict(),
            sandbox_provider_runtime_probe_harness=provider_runtime_probe_harness.to_dict(),
            sandbox_provider_runtime_probe_runner_enforcement=provider_runtime_probe_runner_enforcement.to_dict(),
            runner_command_allowlist_enforcement=allowlist_enforcement.to_dict(),
            approval_consumption_handoff=approval_handoff.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            source_mount_contract_declared=bool(current_checks.get("source_mount_contract_declared")),
            read_only_mount_bound=bool(current_checks.get("read_only_mount_bound")),
            mount_enforced=bool(current_checks.get("read_only_source_mount_enforced")),
            source_copied=bool(current_checks.get("source_copied")),
            source_write_allowed=bool(current_checks.get("source_write_allowed")),
            sandbox_provider_contract_declared=bool(current_checks.get("sandbox_provider_contract_declared")),
            sandbox_provider_binding_ready=bool(current_checks.get("sandbox_provider_binding_ready")),
            sandbox_provider_selection_ready=bool(current_checks.get("sandbox_provider_selection_ready")),
            sandbox_provider_verifier_ready=bool(current_checks.get("sandbox_provider_verifier_ready")),
            sandbox_provider_runtime_probe_ready=bool(current_checks.get("sandbox_provider_runtime_probe_ready")),
            sandbox_provider_runtime_probe_harness_ready=bool(
                current_checks.get("sandbox_provider_runtime_probe_harness_ready")
            ),
            sandbox_provider_runtime_probe_runner_enforcement_ready=bool(
                current_checks.get("sandbox_provider_runtime_probe_runner_enforcement_ready")
            ),
            runtime_probe_harness_contract_declared=bool(current_checks.get("runtime_probe_harness_contract_declared")),
            runtime_probe_runner_enforcement_contract_declared=bool(
                current_checks.get("runtime_probe_runner_enforcement_contract_declared")
            ),
            runtime_probe_runner_enforcement_bound=bool(current_checks.get("runtime_probe_runner_enforcement_bound")),
            runtime_probe_runner_bound=bool(current_checks.get("runtime_probe_runner_bound")),
            runtime_probe_sandbox_bound=bool(current_checks.get("runtime_probe_sandbox_bound")),
            runtime_probe_service_query_guard_bound=bool(current_checks.get("runtime_probe_service_query_guard_bound")),
            runtime_probe_output_capture_bound=bool(current_checks.get("runtime_probe_output_capture_bound")),
            runtime_probe_kill_switch_bound=bool(current_checks.get("runtime_probe_kill_switch_bound")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            sandbox_provider_bound=bool(current_checks.get("sandbox_provider_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            runner_bound=bool(current_checks.get("runner_bound")),
            runner_identity_verified=bool(current_checks.get("runner_identity_verified")),
            command_allowlist_enforced=bool(current_checks.get("command_allowlist_enforced")),
            writer_implementation_bound=bool(current_checks.get("writer_implementation_bound")),
            receipt_prewrite_bound=bool(current_checks.get("receipt_prewrite_bound")),
            receipt_final_write_bound=bool(current_checks.get("receipt_final_write_bound")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("commands_executed")),
            commands_executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            ran_repo_scripts=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            candidate_validated=bool(current_checks.get("candidate_validated")),
            capability_promoted=bool(current_checks.get("capability_promoted")),
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=_append_unique(
                [
                    "lab_run_boundary_preflight_only",
                    "sandboxed_run_not_available",
                    "repository_code_not_executed",
                    "commands_not_executed",
                    "approval_not_consumed_for_repo_execution",
                    "execution_authority_not_granted",
                    "candidate_not_validated",
                    "capability_not_promoted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "source_mount_contract_readback",
                "execution_receipt_writer_preflight_readback",
                "runner_sandbox_readiness_readback",
                "sandbox_provider_selection_readback",
                "sandbox_provider_verifier_readback",
                "sandbox_provider_runtime_probe_readback",
                "sandbox_provider_runtime_probe_harness_readback",
                "sandbox_provider_runtime_probe_runner_enforcement_readback",
                "runner_command_allowlist_enforcement_readback",
                "approval_consumption_handoff_readback",
                "read_only_mount_enforcement_checked",
                "sandbox_binding_checked",
                "runtime_probe_runner_enforcement_checked",
                "workspace_write_boundary_checked",
                "network_policy_checked",
                "command_allowlist_enforcement_checked",
                "receipt_writer_binding_checked",
                "approval_consumption_checked",
                "commands_not_executed",
                "repo_code_not_executed",
                "execution_authority_not_granted",
                "candidate_not_validated",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_run_boundary_preflights",
            boundary.id,
            {"run_boundary_preflight": boundary.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.run_boundary.preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    workspace.manifest_path,
                    _safe_str(source_contract_result.get("source_mount_contract_path")).strip(),
                    _safe_str(writer_result.get("execution_receipt_writer_preflight_path")).strip(),
                    _safe_str(
                        provider_runtime_probe_runner_enforcement_result.get(
                            "sandbox_provider_runtime_probe_runner_enforcement_path"
                        )
                    ).strip(),
                ],
            ),
            input_hashes=[
                source.fingerprint,
                preflight.action_hash,
                _stable_payload_hash(contract_payload),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=boundary.warnings,
            errors=boundary.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=boundary.validation_performed,
        )
        boundary = replace(boundary, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_run_boundary_preflights",
            boundary.id,
            {"run_boundary_preflight": boundary.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_run_boundary_preflight_path": str(artifact_path),
            "last_lab_run_boundary_preflight_receipt_path": str(receipt_path),
            "last_lab_run_boundary_preflight_status": status,
            "last_lab_run_boundary_preflight_missing_checks": missing_checks,
            "last_lab_run_boundary_mode": boundary.boundary_mode,
            "last_lab_run_boundary_run_mode": boundary.run_mode,
            "last_lab_execution_action_hash": boundary.action_hash,
            "last_lab_approval_id": clean_approval_id,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "workspace": workspace.to_dict(),
                "source_mount_contract": source_contract.to_dict(),
                "execution_receipt_writer_preflight": writer_preflight.to_dict(),
                "runner_sandbox_readiness": sandbox_readiness.to_dict(),
                "sandbox_provider_contract": provider_contract.to_dict(),
                "sandbox_provider_binding": provider_binding.to_dict(),
                "sandbox_provider_selection": provider_selection.to_dict(),
                "sandbox_provider_verifier": provider_verifier.to_dict(),
                "sandbox_provider_runtime_probe": provider_runtime_probe.to_dict(),
                "sandbox_provider_runtime_probe_harness": provider_runtime_probe_harness.to_dict(),
                "sandbox_provider_runtime_probe_runner_enforcement": provider_runtime_probe_runner_enforcement.to_dict(),
                "runner_command_allowlist_enforcement": allowlist_enforcement.to_dict(),
                "approval_consumption_handoff": approval_handoff.to_dict(),
                "run_boundary_preflight": boundary.to_dict(),
                "artifact_path": str(artifact_path),
                "run_boundary_preflight_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _lab_run_boundary_execution_payload(
                    recorded=True,
                    ready=status == "ready",
                    reason=(
                        "lab_run_boundary_ready_for_future_guarded_runner"
                        if status == "ready"
                        else "lab_run_boundary_blocked_without_repo_execution"
                    ),
                ),
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe_execution_boundary(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        run_boundary_result = self.preflight_lab_run_boundary(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        run_boundary = LabRunBoundaryPreflight.from_dict(run_boundary_result.get("run_boundary_preflight"))
        source = SourceRecord.from_dict(run_boundary_result.get("source"))
        if run_boundary is None or source is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "lab_runtime_probe_execution_boundary_run_boundary_unavailable",
                    "run_boundary_result": run_boundary_result,
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="lab_runtime_probe_execution_boundary_run_boundary_unavailable",
                    ),
                }
            )

        contract_payload = _lab_sandbox_provider_runtime_probe_execution_boundary_contract_payload(
            run_boundary=run_boundary
        )
        required_checks = _lab_sandbox_provider_runtime_probe_execution_boundary_required_checks()
        current_checks = _lab_sandbox_provider_runtime_probe_execution_boundary_current_checks(
            run_boundary=run_boundary,
            execution_boundary_contract=contract_payload,
        )
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "approval_consumed",
                "execution_authority",
                "executed",
                "service_query_performed",
                "process_launched",
                "container_launched",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "execution_receipt_written",
            )
        )
        blockers = _append_unique(
            run_boundary.blockers,
            *missing_checks,
            "sandbox_provider_runtime_probe_execution_boundary_blocked",
        )
        status = "refused" if unsafe_state else "ready" if not blockers else "blocked"
        now = utc_now()
        boundary = LabSandboxProviderRuntimeProbeExecutionBoundary(
            id=_lab_sandbox_provider_runtime_probe_execution_boundary_id(run_boundary.id, clean_approval_id),
            approval_id=clean_approval_id,
            run_boundary_preflight_id=run_boundary.id,
            source_mount_contract_id=run_boundary.source_mount_contract_id,
            execution_receipt_writer_preflight_id=run_boundary.execution_receipt_writer_preflight_id,
            sandbox_provider_runtime_probe_runner_enforcement_id=(
                run_boundary.sandbox_provider_runtime_probe_runner_enforcement_id
            ),
            sandbox_provider_runtime_probe_harness_id=run_boundary.sandbox_provider_runtime_probe_harness_id,
            sandbox_provider_runtime_probe_id=run_boundary.sandbox_provider_runtime_probe_id,
            preflight_id=run_boundary.preflight_id,
            plan_id=run_boundary.plan_id,
            workspace_id=run_boundary.workspace_id,
            source_id=run_boundary.source_id,
            candidate_id=run_boundary.candidate_id,
            candidate_name=run_boundary.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=run_boundary.action,
            action_hash=run_boundary.action_hash,
            boundary_kind="francis.lab.sandbox_provider_runtime_probe_execution_boundary",
            boundary_mode="execution_boundary_preflight_only_no_provider_execution",
            probe_mode="future_sandbox_provider_runtime_probe",
            execution_boundary_contract=contract_payload,
            run_boundary_preflight=run_boundary.to_dict(),
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            run_boundary_present=bool(current_checks.get("run_boundary_present")),
            run_boundary_ready=bool(current_checks.get("run_boundary_ready")),
            runtime_probe_runner_enforcement_present=bool(
                current_checks.get("runtime_probe_runner_enforcement_present")
            ),
            runtime_probe_runner_enforcement_ready=bool(current_checks.get("runtime_probe_runner_enforcement_ready")),
            runtime_probe_runner_enforcement_bound=bool(current_checks.get("runtime_probe_runner_enforcement_bound")),
            runtime_probe_runner_bound=bool(current_checks.get("runtime_probe_runner_bound")),
            runtime_probe_bound=bool(current_checks.get("runtime_probe_bound")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            provider_probe_execution_boundary_declared=bool(
                current_checks.get("provider_probe_execution_boundary_declared")
            ),
            provider_probe_execution_boundary_bound=bool(current_checks.get("provider_probe_execution_boundary_bound")),
            execution_receipt_writer_bound=bool(current_checks.get("execution_receipt_writer_bound")),
            receipt_prewrite_bound=bool(current_checks.get("receipt_prewrite_bound")),
            receipt_final_write_bound=bool(current_checks.get("receipt_final_write_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            network_blocked_or_policy_bound=bool(current_checks.get("network_blocked_or_policy_bound")),
            workspace_isolated=bool(current_checks.get("workspace_isolated")),
            timeout_policy_bound=bool(current_checks.get("timeout_policy_bound")),
            kill_switch_bound=bool(current_checks.get("kill_switch_bound")),
            output_capture_bound=bool(current_checks.get("output_capture_bound")),
            approval_not_consumed=bool(current_checks.get("approval_not_consumed")),
            execution_authority_absent=bool(current_checks.get("execution_authority_absent")),
            provider_binary_not_executed=bool(current_checks.get("provider_binary_not_executed")),
            service_query_not_performed=bool(current_checks.get("service_query_not_performed")),
            process_not_launched=bool(current_checks.get("process_not_launched")),
            container_not_launched=bool(current_checks.get("container_not_launched")),
            repo_code_not_executed=bool(current_checks.get("repo_code_not_executed")),
            network_not_accessed=bool(current_checks.get("network_not_accessed")),
            repo_write_not_performed=bool(current_checks.get("repo_write_not_performed")),
            execution_receipt_not_written=bool(current_checks.get("execution_receipt_not_written")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("executed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            execution_receipt_written=bool(current_checks.get("execution_receipt_written")),
            warnings=_append_unique(
                [
                    "sandbox_provider_runtime_probe_execution_boundary_preflight_only",
                    "provider_runtime_probe_not_performed",
                    "provider_binary_not_executed",
                    "provider_service_not_queried",
                    "process_not_launched",
                    "container_not_launched",
                    "repo_code_not_executed",
                    "execution_receipt_not_written",
                    "approval_not_consumed_for_provider_probe",
                    "execution_authority_not_granted",
                ],
                *blockers,
            ),
            errors=blockers if status == "refused" else [],
            validation_performed=[
                "run_boundary_preflight_readback",
                "runtime_probe_runner_enforcement_readback",
                "runtime_probe_execution_boundary_contract_declared",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_execution_boundaries",
            boundary.id,
            {"sandbox_provider_runtime_probe_execution_boundary": boundary.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe.execution_boundary",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    _safe_str(run_boundary_result.get("run_boundary_preflight_path")).strip(),
                ],
            ),
            input_hashes=[
                source.fingerprint,
                run_boundary.action_hash,
                _stable_payload_hash(contract_payload),
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=boundary.warnings,
            errors=boundary.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=boundary.validation_performed,
        )
        boundary = replace(boundary, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_execution_boundaries",
            boundary.id,
            {"sandbox_provider_runtime_probe_execution_boundary": boundary.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runtime_probe_execution_boundary_path": str(artifact_path),
            "last_lab_runtime_probe_execution_boundary_receipt_path": str(receipt_path),
            "last_lab_runtime_probe_execution_boundary_status": status,
            "last_lab_runtime_probe_execution_boundary_missing_checks": missing_checks,
            "last_lab_runtime_probe_execution_boundary_mode": boundary.boundary_mode,
            "last_lab_execution_action_hash": boundary.action_hash,
            "last_lab_approval_id": clean_approval_id,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "run_boundary_preflight": run_boundary.to_dict(),
                "sandbox_provider_runtime_probe_execution_boundary": boundary.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_execution_boundary_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                    recorded=True,
                    ready=status == "ready",
                    reason=(
                        "sandbox_provider_runtime_probe_execution_boundary_ready_for_future_guarded_probe"
                        if status == "ready"
                        else "sandbox_provider_runtime_probe_execution_boundary_blocked_without_execution"
                    ),
                ),
            }
        )

    def refuse_lab_sandbox_provider_runtime_probe(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
        reason: str = "sandbox_provider_runtime_probe_not_available",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        boundary_result = self.preflight_lab_sandbox_provider_runtime_probe_execution_boundary(
            source_or_path,
            candidate_ref,
            clean_approval_id,
            actor=actor,
        )
        boundary = LabSandboxProviderRuntimeProbeExecutionBoundary.from_dict(
            boundary_result.get("sandbox_provider_runtime_probe_execution_boundary")
        )
        source = SourceRecord.from_dict(boundary_result.get("source"))
        if boundary is None or source is None:
            return _display_payload(
                {
                    **boundary_result,
                    "status": "blocked",
                    "error": "lab_runtime_probe_execution_boundary_unavailable",
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="lab_runtime_probe_execution_boundary_unavailable",
                    ),
                }
            )

        clean_reason = _safe_str(reason).strip() or "sandbox_provider_runtime_probe_not_available"
        blockers = _append_unique(
            boundary.blockers,
            *boundary.missing_checks,
            "sandbox_provider_runtime_probe_refused_in_v0",
            "no_governed_provider_probe_runner_bound",
            "provider_runtime_probe_execution_not_authorized",
        )
        status = "refused" if boundary.status == "refused" else "blocked"
        refusal = LabSandboxProviderRuntimeProbeRefusal(
            id=_lab_sandbox_provider_runtime_probe_refusal_id(boundary.id, clean_approval_id),
            approval_id=clean_approval_id,
            execution_boundary_id=boundary.id,
            run_boundary_preflight_id=boundary.run_boundary_preflight_id,
            source_id=boundary.source_id,
            candidate_id=boundary.candidate_id,
            candidate_name=boundary.candidate_name,
            timestamp=utc_now(),
            actor=_safe_str(actor).strip() or "francis/system",
            status=status,
            reason=clean_reason,
            blockers=blockers,
            execution_boundary=boundary.to_dict(),
            execution_authority=False,
            executed=False,
            provider_runtime_probe_performed=False,
            provider_binary_executed=False,
            service_query_performed=False,
            process_launched=False,
            container_launched=False,
            repo_code_executed=False,
            network_accessed=False,
            wrote_to_repo=False,
            execution_receipt_written=False,
            approval_consumed=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_refusals",
            refusal.id,
            {"sandbox_provider_runtime_probe_refusal": refusal.to_dict()},
        )
        boundary_path = _safe_str(boundary_result.get("sandbox_provider_runtime_probe_execution_boundary_path")).strip()
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe.refuse",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique([source.canonical_path], boundary_path),
            input_hashes=[
                source.fingerprint,
                boundary.action_hash,
                boundary.id,
                _stable_payload_hash(boundary.current_checks),
            ],
            result_status=status,
            warnings=[
                "sandbox_provider_runtime_probe_refusal_recorded",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "execution_receipt_not_written",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
            errors=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "runtime_probe_execution_boundary_readback_no_provider_execution",
                "provider_runtime_probe_refusal_recorded",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        refusal = replace(refusal, receipt_path=str(receipt_path))
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_refusals",
            refusal.id,
            {"sandbox_provider_runtime_probe_refusal": refusal.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runtime_probe_refusal_path": str(artifact_path),
            "last_lab_runtime_probe_refusal_receipt_path": str(receipt_path),
            "last_lab_runtime_probe_refusal_status": status,
            "last_lab_runtime_probe_refusal_reason": refusal.reason,
            "last_lab_runtime_probe_refusal_boundary_id": boundary.id,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": boundary.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == boundary.candidate_id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "sandbox_provider_runtime_probe_execution_boundary": boundary.to_dict(),
                "sandbox_provider_runtime_probe_refusal": refusal.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_refusal_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                    recorded=True,
                    ready=False,
                    reason=refusal.reason,
                ),
            }
        )

    def request_lab_sandbox_provider_runtime_probe_approval(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
        reason: str = "sandbox_provider_runtime_probe_requested",
    ) -> dict[str, Any]:
        clean_upstream_approval_id = _safe_str(approval_id).strip()
        boundary_result = self.preflight_lab_sandbox_provider_runtime_probe_execution_boundary(
            source_or_path,
            candidate_ref,
            clean_upstream_approval_id,
            actor=actor,
        )
        boundary = LabSandboxProviderRuntimeProbeExecutionBoundary.from_dict(
            boundary_result.get("sandbox_provider_runtime_probe_execution_boundary")
        )
        source = SourceRecord.from_dict(boundary_result.get("source"))
        if boundary is None or source is None:
            return _display_payload(
                {
                    **boundary_result,
                    "status": "failed",
                    "error": "lab_runtime_probe_execution_boundary_unavailable",
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="lab_runtime_probe_execution_boundary_unavailable",
                    ),
                }
            )

        blockers = _append_unique(
            boundary.blockers,
            *boundary.missing_checks,
            "sandbox_provider_runtime_probe_requires_operator_approval",
            "sandbox_provider_runtime_probe_still_blocked_after_request",
        )
        action_payload = {
            "action": "francis.lab.sandbox_provider_runtime_probe",
            "upstream_approval_id": clean_upstream_approval_id,
            "execution_boundary_id": boundary.id,
            "run_boundary_preflight_id": boundary.run_boundary_preflight_id,
            "source_id": boundary.source_id,
            "candidate_id": boundary.candidate_id,
            "candidate_name": boundary.candidate_name,
            "boundary_status": boundary.status,
            "boundary_missing_checks": boundary.missing_checks,
            "required_controls": boundary.required_checks,
        }
        action_hash = _stable_payload_hash(action_payload)
        approval_payload = _display_payload(
            {
                **action_payload,
                "action_hash": action_hash,
                "readiness": {
                    "provider_runtime_probe_ready": False,
                    "execution_boundary_status": boundary.status,
                    "blockers": blockers,
                },
                "governance": {
                    "approval_scope": "ingest.lab.sandbox.provider_runtime_probe.execute",
                    "approval_consumed": False,
                    "upstream_approval_consumed": False,
                    "execution_authority": False,
                    "provider_runtime_probe_performed": False,
                    "provider_binary_executed": False,
                    "service_query_performed": False,
                    "process_launched": False,
                    "container_launched": False,
                },
            }
        )
        approval = approvals.request(
            action="francis.lab.sandbox_provider_runtime_probe",
            reason=_safe_str(reason).strip() or "sandbox_provider_runtime_probe_requested",
            payload=approval_payload,
        )
        provider_probe_approval_id = _safe_str(approval.get("id")).strip()
        approval_path = (
            approvals.pending_dir() / f"{provider_probe_approval_id}.json" if provider_probe_approval_id else Path("")
        )
        now = utc_now()
        request_record = LabSandboxProviderRuntimeProbeApprovalRequest(
            id=_lab_sandbox_provider_runtime_probe_approval_request_id(boundary.id, provider_probe_approval_id),
            approval_id=provider_probe_approval_id,
            upstream_approval_id=clean_upstream_approval_id,
            execution_boundary_id=boundary.id,
            run_boundary_preflight_id=boundary.run_boundary_preflight_id,
            source_id=boundary.source_id,
            candidate_id=boundary.candidate_id,
            candidate_name=boundary.candidate_name,
            status="needs_approval",
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action="francis.lab.sandbox_provider_runtime_probe",
            action_hash=action_hash,
            approval_path=str(approval_path) if provider_probe_approval_id else "",
            approval_payload=approval_payload,
            execution_boundary=boundary.to_dict(),
            blockers=blockers,
            approval_created=bool(provider_probe_approval_id),
            approval_consumed=False,
            upstream_approval_consumed=False,
            execution_authority=False,
            executed=False,
            provider_runtime_probe_performed=False,
            provider_binary_executed=False,
            service_query_performed=False,
            process_launched=False,
            container_launched=False,
            repo_code_executed=False,
            network_accessed=False,
            wrote_to_repo=False,
            execution_receipt_written=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_approval_requests",
            request_record.id,
            {"sandbox_provider_runtime_probe_approval_request": request_record.to_dict()},
        )
        boundary_path = _safe_str(boundary_result.get("sandbox_provider_runtime_probe_execution_boundary_path")).strip()
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe.approval_request",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique([source.canonical_path], boundary_path),
            input_hashes=[source.fingerprint, boundary.action_hash, action_hash, boundary.id],
            result_status="needs_approval",
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path), str(approval_path) if provider_probe_approval_id else ""],
            validation_performed=[
                "runtime_probe_execution_boundary_readback_no_provider_execution",
                "provider_runtime_probe_approval_request_created",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        request_record = replace(request_record, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_approval_requests",
            request_record.id,
            {"sandbox_provider_runtime_probe_approval_request": request_record.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runtime_probe_approval_request_path": str(artifact_path),
            "last_lab_runtime_probe_approval_request_receipt_path": str(receipt_path),
            "last_lab_runtime_probe_approval_id": provider_probe_approval_id,
            "last_lab_runtime_probe_approval_action_hash": action_hash,
            "last_lab_runtime_probe_approval_boundary_id": boundary.id,
            "last_lab_approval_id": clean_upstream_approval_id,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": "needs_approval",
                "source": updated.to_dict(),
                "sandbox_provider_runtime_probe_execution_boundary": boundary.to_dict(),
                "sandbox_provider_runtime_probe_approval_request": request_record.to_dict(),
                "approval": approval,
                "approval_path": str(approval_path) if provider_probe_approval_id else "",
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_approval_request_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": {
                    **_lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=True,
                        ready=False,
                        reason="sandbox_provider_runtime_probe_approval_requested_no_execution",
                    ),
                    "approval_request_created": bool(provider_probe_approval_id),
                    "provider_runtime_probe_approval_id": provider_probe_approval_id,
                },
            }
        )

    def consume_lab_sandbox_provider_runtime_probe_approval(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        approval_request, approval_request_path = _find_lab_sandbox_provider_runtime_probe_approval_request(
            clean_approval_id
        )
        approval_status, approval_record, approval_path = _read_lab_approval_record(clean_approval_id)
        binding, approval_blockers = _lab_sandbox_provider_runtime_probe_approval_binding(
            approval_request=approval_request,
            approval_id=clean_approval_id,
            approval_status=approval_status,
            approval_record=approval_record,
            approval_path=approval_path,
        )
        existing_consumption, existing_consumption_path = _find_lab_sandbox_provider_runtime_probe_approval_consumption(
            clean_approval_id
        )
        blockers = _append_unique(
            [],
            *approval_blockers,
            *([] if approval_request is not None else ["provider_runtime_probe_approval_request_missing"]),
            *(
                []
                if approval_request is None or approval_request.source_id == source.id
                else ["source_identity_mismatch"]
            ),
            *(
                []
                if approval_request is None
                or (approval_request.candidate_id == candidate.id and approval_request.candidate_name == candidate.name)
                else ["candidate_identity_mismatch"]
            ),
            *(
                []
                if approval_request is None or approval_request.status == "needs_approval"
                else ["approval_request_status_not_needs_approval"]
            ),
            *(
                []
                if approval_request is None or approval_request.approval_created
                else ["approval_request_missing_created_approval"]
            ),
            *(
                []
                if approval_request is None or not approval_request.approval_consumed
                else ["approval_request_already_marks_consumed"]
            ),
            *(
                []
                if approval_request is None or not approval_request.execution_authority
                else ["approval_request_claims_execution_authority"]
            ),
            *(
                []
                if approval_request is None or not approval_request.executed
                else ["approval_request_claims_execution"]
            ),
            *(
                []
                if approval_request is None or not approval_request.provider_runtime_probe_performed
                else ["approval_request_claims_provider_probe"]
            ),
            *(
                []
                if approval_request is None or not approval_request.provider_binary_executed
                else ["approval_request_claims_provider_binary_execution"]
            ),
            *(
                []
                if approval_request is None or not approval_request.service_query_performed
                else ["approval_request_claims_provider_service_query"]
            ),
            *(
                []
                if approval_request is None or not approval_request.process_launched
                else ["approval_request_claims_process_launch"]
            ),
            *(
                []
                if approval_request is None or not approval_request.container_launched
                else ["approval_request_claims_container_launch"]
            ),
            *(
                []
                if approval_request is None or not approval_request.repo_code_executed
                else ["approval_request_claims_repo_execution"]
            ),
            *(
                []
                if approval_request is None or not approval_request.network_accessed
                else ["approval_request_claims_network_access"]
            ),
            *(
                []
                if approval_request is None or not approval_request.wrote_to_repo
                else ["approval_request_claims_repo_write"]
            ),
            *(
                []
                if approval_request is None or not approval_request.execution_receipt_written
                else ["approval_request_claims_execution_receipt"]
            ),
            *([] if existing_consumption is None else ["provider_runtime_probe_approval_already_consumed"]),
        )
        refused = bool(binding.get("refused"))
        if blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "refused" if refused else "blocked",
                    "error": "provider_runtime_probe_approval_consumption_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_binding": binding,
                    "blockers": blockers,
                    "provider_runtime_probe_approval_request_path": (
                        str(approval_request_path) if approval_request_path is not None else ""
                    ),
                    "existing_provider_runtime_probe_approval_consumption_path": (
                        str(existing_consumption_path) if existing_consumption_path is not None else ""
                    ),
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=approval_request is not None,
                        ready=False,
                        reason="provider_runtime_probe_approval_consumption_blocked",
                    ),
                }
            )

        assert approval_request is not None
        now = utc_now()
        consumption = LabSandboxProviderRuntimeProbeApprovalConsumption(
            id=_lab_sandbox_provider_runtime_probe_approval_consumption_id(
                clean_approval_id,
                approval_request.id,
            ),
            approval_id=clean_approval_id,
            approval_request_id=approval_request.id,
            upstream_approval_id=approval_request.upstream_approval_id,
            execution_boundary_id=approval_request.execution_boundary_id,
            run_boundary_preflight_id=approval_request.run_boundary_preflight_id,
            source_id=approval_request.source_id,
            candidate_id=approval_request.candidate_id,
            candidate_name=approval_request.candidate_name,
            status="consumed",
            created_at=now,
            updated_at=now,
            consumed_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=approval_request.action,
            action_hash=approval_request.action_hash,
            approval_status=approval_status,
            approval_path=str(approval_path) if approval_path is not None else "",
            approval_snapshot=_lab_approval_snapshot(approval_record),
            approval_binding=binding,
            approval_request=approval_request.to_dict(),
            approval_consumed=True,
            single_use_enforced=True,
            upstream_approval_consumed=False,
            execution_authority=False,
            executed=False,
            provider_runtime_probe_performed=False,
            provider_binary_executed=False,
            service_query_performed=False,
            process_launched=False,
            container_launched=False,
            repo_code_executed=False,
            network_accessed=False,
            wrote_to_repo=False,
            execution_receipt_written=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=[
                "provider_runtime_probe_approval_consumed_for_future_probe_only",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repository_code_not_executed",
                "execution_authority_not_granted",
                "approval_reuse_blocked_by_consumption_record",
            ],
            validation_performed=[
                "provider_runtime_probe_approval_request_found",
                "approved_exact_action_binding_checked",
                "provider_runtime_probe_approval_consumption_record_written",
                "single_use_consumption_record_declared",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_approval_consumptions",
            consumption.id,
            {"sandbox_provider_runtime_probe_approval_consumption": consumption.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe.approval.consume",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(approval_request_path) if approval_request_path is not None else "",
                    str(approval_path) if approval_path is not None else "",
                ],
            ),
            input_hashes=[
                source.fingerprint,
                approval_request.action_hash,
                approval_request.id,
                _stable_payload_hash(binding),
            ],
            result_status=consumption.status,
            warnings=consumption.warnings,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=consumption.validation_performed,
        )
        consumption = replace(consumption, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_approval_consumptions",
            consumption.id,
            {"sandbox_provider_runtime_probe_approval_consumption": consumption.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runtime_probe_approval_consumption_path": str(artifact_path),
            "last_lab_runtime_probe_approval_consumption_receipt_path": str(receipt_path),
            "last_lab_runtime_probe_approval_consumption_status": consumption.status,
            "last_lab_runtime_probe_approval_consumed": consumption.approval_consumed,
            "last_lab_runtime_probe_approval_id": clean_approval_id,
            "last_lab_runtime_probe_approval_request_id": approval_request.id,
            "last_lab_runtime_probe_approval_action_hash": approval_request.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == approval_request.candidate_id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        execution = _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
            recorded=True,
            ready=False,
            reason="provider_runtime_probe_approval_consumed_no_execution",
        )
        execution.update(
            {
                "approval_consumed": True,
                "provider_runtime_probe_approval_consumed": True,
                "provider_runtime_probe_approval_id": clean_approval_id,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": consumption.status,
                "source": updated.to_dict(),
                "sandbox_provider_runtime_probe_approval_request": approval_request.to_dict(),
                "sandbox_provider_runtime_probe_approval_consumption": consumption.to_dict(),
                "approval_binding": binding,
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_approval_consumption_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        consumption, consumption_path = _find_lab_sandbox_provider_runtime_probe_approval_consumption(clean_approval_id)
        if consumption is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "provider_runtime_probe_approval_consumption_missing",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_id": clean_approval_id,
                    "blockers": ["provider_runtime_probe_approval_consumption_missing"],
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="provider_runtime_probe_approval_consumption_missing",
                    ),
                }
            )

        identity_blockers = _append_unique(
            [],
            *([] if consumption.source_id == source.id else ["source_identity_mismatch"]),
            *(
                []
                if consumption.candidate_id == candidate.id and consumption.candidate_name == candidate.name
                else ["candidate_identity_mismatch"]
            ),
            *([] if consumption.status == "consumed" else ["approval_consumption_status_not_consumed"]),
            *([] if consumption.approval_consumed else ["provider_runtime_probe_approval_not_consumed"]),
            *([] if consumption.single_use_enforced else ["single_use_consumption_not_enforced"]),
            *([] if not consumption.execution_authority else ["approval_consumption_claims_execution_authority"]),
            *([] if not consumption.executed else ["approval_consumption_claims_execution"]),
            *(
                []
                if not consumption.provider_runtime_probe_performed
                else ["approval_consumption_claims_provider_probe"]
            ),
            *([] if not consumption.process_launched else ["approval_consumption_claims_process_launch"]),
            *([] if not consumption.container_launched else ["approval_consumption_claims_container_launch"]),
            *([] if not consumption.repo_code_executed else ["approval_consumption_claims_repo_execution"]),
            *([] if not consumption.network_accessed else ["approval_consumption_claims_network_access"]),
            *([] if not consumption.wrote_to_repo else ["approval_consumption_claims_repo_write"]),
            *([] if not consumption.execution_receipt_written else ["approval_consumption_claims_execution_receipt"]),
        )
        if identity_blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "provider_runtime_probe_invocation_boundary_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "sandbox_provider_runtime_probe_approval_consumption": consumption.to_dict(),
                    "blockers": identity_blockers,
                    "provider_runtime_probe_approval_consumption_path": (
                        str(consumption_path) if consumption_path is not None else ""
                    ),
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="provider_runtime_probe_invocation_boundary_blocked",
                    ),
                }
            )

        execution_boundary, execution_boundary_path = _find_lab_sandbox_provider_runtime_probe_execution_boundary(
            consumption.execution_boundary_id
        )
        now = utc_now()
        invocation_contract = _lab_sandbox_provider_runtime_probe_invocation_boundary_contract_payload(
            approval_consumption=consumption,
            execution_boundary=execution_boundary,
        )
        current_checks = _lab_sandbox_provider_runtime_probe_invocation_boundary_current_checks(
            approval_consumption=consumption,
            execution_boundary=execution_boundary,
        )
        required_checks = _lab_sandbox_provider_runtime_probe_invocation_boundary_required_checks()
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(
            missing_checks,
            "provider_runtime_probe_invocation_blocked_until_governed_runner_bound",
            "provider_runtime_probe_not_performed",
            "provider_binary_not_executed",
            "provider_service_not_queried",
            "process_not_launched",
            "container_not_launched",
            "repo_code_not_executed",
            "network_not_accessed",
            "repo_write_not_performed",
            "execution_receipt_not_written",
        )
        status = "ready" if not missing_checks else "blocked"
        boundary = LabSandboxProviderRuntimeProbeInvocationBoundary(
            id=_lab_sandbox_provider_runtime_probe_invocation_boundary_id(
                consumption.id,
                consumption.execution_boundary_id,
            ),
            approval_id=clean_approval_id,
            approval_consumption_id=consumption.id,
            approval_request_id=consumption.approval_request_id,
            execution_boundary_id=consumption.execution_boundary_id,
            run_boundary_preflight_id=consumption.run_boundary_preflight_id,
            source_id=consumption.source_id,
            candidate_id=consumption.candidate_id,
            candidate_name=consumption.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=consumption.action,
            action_hash=consumption.action_hash,
            approval_consumption=consumption.to_dict(),
            execution_boundary=execution_boundary.to_dict() if execution_boundary is not None else {},
            invocation_contract=invocation_contract,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            approval_consumed=bool(current_checks.get("approval_consumed")),
            single_use_consumption_found=bool(current_checks.get("approval_consumption_found")),
            single_use_enforced=bool(current_checks.get("single_use_enforced")),
            exact_action_binding_verified=bool(current_checks.get("exact_action_binding_verified")),
            upstream_approval_consumed=bool(current_checks.get("upstream_approval_consumed")),
            execution_boundary_present=bool(current_checks.get("execution_boundary_present")),
            execution_boundary_recorded=bool(current_checks.get("execution_boundary_recorded")),
            execution_boundary_ready=bool(current_checks.get("execution_boundary_ready")),
            provider_probe_execution_boundary_bound=bool(current_checks.get("provider_probe_execution_boundary_bound")),
            probe_runner_bound=bool(current_checks.get("probe_runner_bound")),
            probe_runner_policy_bound=bool(current_checks.get("probe_runner_policy_bound")),
            probe_runner_sandbox_bound=bool(current_checks.get("probe_runner_sandbox_bound")),
            probe_runner_network_blocked=bool(current_checks.get("probe_runner_network_blocked")),
            probe_runner_workspace_isolated=bool(current_checks.get("probe_runner_workspace_isolated")),
            probe_runner_timeout_bound=bool(current_checks.get("probe_runner_timeout_bound")),
            probe_runner_output_capture_bound=bool(current_checks.get("probe_runner_output_capture_bound")),
            probe_runner_kill_switch_bound=bool(current_checks.get("probe_runner_kill_switch_bound")),
            probe_runner_receipt_writer_bound=bool(current_checks.get("probe_runner_receipt_writer_bound")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("executed")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            provider_binary_executed=bool(current_checks.get("provider_binary_executed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            execution_receipt_written=bool(current_checks.get("execution_receipt_written")),
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=blockers,
            validation_performed=[
                "provider_runtime_probe_approval_consumption_found",
                "single_use_approval_consumption_readback_checked",
                "execution_boundary_readback_checked",
                "future_probe_runner_controls_checked",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_invocation_boundaries",
            boundary.id,
            {"sandbox_provider_runtime_probe_invocation_boundary": boundary.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe.invocation_boundary",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(consumption_path) if consumption_path is not None else "",
                    str(execution_boundary_path) if execution_boundary_path is not None else "",
                ]
            ),
            input_hashes=[
                source.fingerprint,
                consumption.action_hash,
                consumption.id,
                consumption.execution_boundary_id,
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=boundary.validation_performed,
        )
        boundary = replace(boundary, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_invocation_boundaries",
            boundary.id,
            {"sandbox_provider_runtime_probe_invocation_boundary": boundary.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runtime_probe_invocation_boundary_path": str(artifact_path),
            "last_lab_runtime_probe_invocation_boundary_receipt_path": str(receipt_path),
            "last_lab_runtime_probe_invocation_boundary_status": boundary.status,
            "last_lab_runtime_probe_approval_id": clean_approval_id,
            "last_lab_runtime_probe_approval_consumption_id": consumption.id,
            "last_lab_runtime_probe_invocation_action_hash": consumption.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == candidate.id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        execution = _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
            recorded=execution_boundary is not None,
            ready=False,
            reason="provider_runtime_probe_invocation_boundary_no_execution",
        )
        execution.update(
            {
                "provider_runtime_probe_invocation_boundary_recorded": True,
                "provider_runtime_probe_invocation_boundary_ready": boundary.status == "ready",
                "provider_runtime_probe_approval_consumed": True,
                "approval_consumed": True,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": boundary.status,
                "source": updated.to_dict(),
                "candidate": candidate.to_dict(),
                "sandbox_provider_runtime_probe_approval_consumption": consumption.to_dict(),
                "sandbox_provider_runtime_probe_execution_boundary": (
                    execution_boundary.to_dict() if execution_boundary is not None else {}
                ),
                "sandbox_provider_runtime_probe_invocation_boundary": boundary.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_invocation_boundary_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        invocation_boundary, invocation_boundary_path = _find_lab_sandbox_provider_runtime_probe_invocation_boundary(
            clean_approval_id
        )
        if invocation_boundary is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "provider_runtime_probe_invocation_boundary_missing",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_id": clean_approval_id,
                    "blockers": ["provider_runtime_probe_invocation_boundary_missing"],
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="provider_runtime_probe_invocation_boundary_missing",
                    ),
                }
            )

        identity_blockers = _append_unique(
            [],
            *([] if invocation_boundary.source_id == source.id else ["source_identity_mismatch"]),
            *(
                []
                if invocation_boundary.candidate_id == candidate.id
                and invocation_boundary.candidate_name == candidate.name
                else ["candidate_identity_mismatch"]
            ),
            *([] if invocation_boundary.approval_id == clean_approval_id else ["approval_identity_mismatch"]),
            *([] if invocation_boundary.approval_consumed else ["provider_runtime_probe_approval_not_consumed"]),
            *([] if invocation_boundary.single_use_enforced else ["single_use_consumption_not_enforced"]),
            *([] if invocation_boundary.exact_action_binding_verified else ["exact_action_binding_not_verified"]),
            *(
                []
                if not invocation_boundary.execution_authority
                else ["invocation_boundary_claims_execution_authority"]
            ),
            *([] if not invocation_boundary.executed else ["invocation_boundary_claims_execution"]),
            *(
                []
                if not invocation_boundary.provider_runtime_probe_performed
                else ["invocation_boundary_claims_provider_probe"]
            ),
            *(
                []
                if not invocation_boundary.provider_binary_executed
                else ["invocation_boundary_claims_provider_binary"]
            ),
            *([] if not invocation_boundary.service_query_performed else ["invocation_boundary_claims_service_query"]),
            *([] if not invocation_boundary.process_launched else ["invocation_boundary_claims_process_launch"]),
            *([] if not invocation_boundary.container_launched else ["invocation_boundary_claims_container_launch"]),
            *([] if not invocation_boundary.repo_code_executed else ["invocation_boundary_claims_repo_execution"]),
            *([] if not invocation_boundary.network_accessed else ["invocation_boundary_claims_network_access"]),
            *([] if not invocation_boundary.wrote_to_repo else ["invocation_boundary_claims_repo_write"]),
            *(
                []
                if not invocation_boundary.execution_receipt_written
                else ["invocation_boundary_claims_execution_receipt"]
            ),
        )
        if identity_blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "provider_runtime_probe_runner_pre_execution_boundary_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "sandbox_provider_runtime_probe_invocation_boundary": invocation_boundary.to_dict(),
                    "blockers": identity_blockers,
                    "sandbox_provider_runtime_probe_invocation_boundary_path": (
                        str(invocation_boundary_path) if invocation_boundary_path is not None else ""
                    ),
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="provider_runtime_probe_runner_pre_execution_boundary_blocked",
                    ),
                }
            )

        consumption, consumption_path = _find_lab_sandbox_provider_runtime_probe_approval_consumption(clean_approval_id)
        execution_boundary, execution_boundary_path = _find_lab_sandbox_provider_runtime_probe_execution_boundary(
            invocation_boundary.execution_boundary_id
        )
        now = utc_now()
        pre_execution_contract = _lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_contract_payload(
            invocation_boundary=invocation_boundary,
        )
        current_checks = _lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_current_checks(
            invocation_boundary=invocation_boundary,
        )
        required_checks = _lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_required_checks()
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(
            missing_checks,
            "provider_runtime_probe_runner_pre_execution_boundary_blocked_until_live_runner_controls_bound",
            "provider_runtime_probe_not_performed",
            "provider_binary_not_executed",
            "provider_service_not_queried",
            "process_not_launched",
            "container_not_launched",
            "repo_code_not_executed",
            "network_not_accessed",
            "repo_write_not_performed",
            "execution_receipt_not_written",
        )
        status = "ready" if not missing_checks else "blocked"
        boundary = LabSandboxProviderRuntimeProbeRunnerPreExecutionBoundary(
            id=_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_id(
                invocation_boundary.id,
                clean_approval_id,
            ),
            approval_id=clean_approval_id,
            approval_consumption_id=invocation_boundary.approval_consumption_id,
            invocation_boundary_id=invocation_boundary.id,
            approval_request_id=invocation_boundary.approval_request_id,
            execution_boundary_id=invocation_boundary.execution_boundary_id,
            run_boundary_preflight_id=invocation_boundary.run_boundary_preflight_id,
            source_id=invocation_boundary.source_id,
            candidate_id=invocation_boundary.candidate_id,
            candidate_name=invocation_boundary.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=invocation_boundary.action,
            action_hash=invocation_boundary.action_hash,
            approval_consumption=consumption.to_dict() if consumption is not None else {},
            invocation_boundary=invocation_boundary.to_dict(),
            execution_boundary=execution_boundary.to_dict() if execution_boundary is not None else {},
            pre_execution_contract=pre_execution_contract,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            invocation_boundary_found=bool(current_checks.get("invocation_boundary_found")),
            invocation_boundary_recorded=bool(current_checks.get("invocation_boundary_recorded")),
            invocation_boundary_ready=bool(current_checks.get("invocation_boundary_ready")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            single_use_consumption_found=bool(current_checks.get("single_use_consumption_found")),
            single_use_enforced=bool(current_checks.get("single_use_enforced")),
            exact_action_binding_verified=bool(current_checks.get("exact_action_binding_verified")),
            runner_identity_declared=bool(current_checks.get("runner_identity_declared")),
            runner_identity_bound=bool(current_checks.get("runner_identity_bound")),
            runner_policy_declared=bool(current_checks.get("runner_policy_declared")),
            runner_policy_bound=bool(current_checks.get("runner_policy_bound")),
            sandbox_policy_declared=bool(current_checks.get("sandbox_policy_declared")),
            sandbox_policy_bound=bool(current_checks.get("sandbox_policy_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            network_block_declared=bool(current_checks.get("network_block_declared")),
            network_block_bound=bool(current_checks.get("network_block_bound")),
            timeout_policy_declared=bool(current_checks.get("timeout_policy_declared")),
            timeout_policy_bound=bool(current_checks.get("timeout_policy_bound")),
            output_capture_declared=bool(current_checks.get("output_capture_declared")),
            output_capture_bound=bool(current_checks.get("output_capture_bound")),
            kill_switch_declared=bool(current_checks.get("kill_switch_declared")),
            kill_switch_bound=bool(current_checks.get("kill_switch_bound")),
            execution_receipt_writer_declared=bool(current_checks.get("execution_receipt_writer_declared")),
            execution_receipt_writer_bound=bool(current_checks.get("execution_receipt_writer_bound")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("executed")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            provider_binary_executed=bool(current_checks.get("provider_binary_executed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            execution_receipt_written=bool(current_checks.get("execution_receipt_written")),
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=blockers,
            validation_performed=[
                "provider_runtime_probe_invocation_boundary_found",
                "provider_runtime_probe_approval_consumption_readback_checked",
                "runner_pre_execution_control_requirements_recorded",
                "runner_identity_binding_not_present",
                "runner_policy_binding_not_present",
                "sandbox_policy_binding_not_present",
                "network_block_binding_not_present",
                "timeout_policy_binding_not_present",
                "output_capture_binding_not_present",
                "kill_switch_binding_not_present",
                "execution_receipt_writer_binding_not_present",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_preexec_boundaries",
            boundary.id,
            {"sandbox_provider_runtime_probe_runner_pre_execution_boundary": boundary.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(invocation_boundary_path) if invocation_boundary_path is not None else "",
                    str(consumption_path) if consumption_path is not None else "",
                    str(execution_boundary_path) if execution_boundary_path is not None else "",
                ]
            ),
            input_hashes=[
                source.fingerprint,
                invocation_boundary.action_hash,
                invocation_boundary.id,
                invocation_boundary.approval_consumption_id,
                invocation_boundary.execution_boundary_id,
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=boundary.validation_performed,
        )
        boundary = replace(boundary, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_preexec_boundaries",
            boundary.id,
            {"sandbox_provider_runtime_probe_runner_pre_execution_boundary": boundary.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runtime_probe_runner_pre_execution_boundary_path": str(artifact_path),
            "last_lab_runtime_probe_runner_pre_execution_boundary_receipt_path": str(receipt_path),
            "last_lab_runtime_probe_runner_pre_execution_boundary_status": boundary.status,
            "last_lab_runtime_probe_invocation_boundary_id": invocation_boundary.id,
            "last_lab_runtime_probe_approval_id": clean_approval_id,
            "last_lab_runtime_probe_approval_consumption_id": invocation_boundary.approval_consumption_id,
            "last_lab_runtime_probe_runner_pre_execution_action_hash": invocation_boundary.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == candidate.id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        execution = _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
            recorded=execution_boundary is not None,
            ready=False,
            reason="provider_runtime_probe_runner_pre_execution_boundary_no_execution",
        )
        execution.update(
            {
                "provider_runtime_probe_invocation_boundary_recorded": True,
                "provider_runtime_probe_runner_pre_execution_boundary_recorded": True,
                "provider_runtime_probe_runner_pre_execution_boundary_ready": boundary.status == "ready",
                "provider_runtime_probe_approval_consumed": True,
                "approval_consumed": True,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": boundary.status,
                "source": updated.to_dict(),
                "candidate": candidate.to_dict(),
                "sandbox_provider_runtime_probe_approval_consumption": consumption.to_dict() if consumption else {},
                "sandbox_provider_runtime_probe_execution_boundary": (
                    execution_boundary.to_dict() if execution_boundary is not None else {}
                ),
                "sandbox_provider_runtime_probe_invocation_boundary": invocation_boundary.to_dict(),
                "sandbox_provider_runtime_probe_runner_pre_execution_boundary": boundary.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_runner_pre_execution_boundary_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        pre_execution_boundary, pre_execution_boundary_path = (
            _find_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(clean_approval_id)
        )
        if pre_execution_boundary is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "provider_runtime_probe_runner_pre_execution_boundary_missing",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_id": clean_approval_id,
                    "blockers": ["provider_runtime_probe_runner_pre_execution_boundary_missing"],
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="provider_runtime_probe_runner_pre_execution_boundary_missing",
                    ),
                }
            )

        identity_blockers = _append_unique(
            [],
            *([] if pre_execution_boundary.source_id == source.id else ["source_identity_mismatch"]),
            *(
                []
                if pre_execution_boundary.candidate_id == candidate.id
                and pre_execution_boundary.candidate_name == candidate.name
                else ["candidate_identity_mismatch"]
            ),
            *([] if pre_execution_boundary.approval_id == clean_approval_id else ["approval_identity_mismatch"]),
            *([] if pre_execution_boundary.approval_consumed else ["provider_runtime_probe_approval_not_consumed"]),
            *([] if pre_execution_boundary.single_use_enforced else ["single_use_consumption_not_enforced"]),
            *([] if pre_execution_boundary.exact_action_binding_verified else ["exact_action_binding_not_verified"]),
            *(
                []
                if not pre_execution_boundary.execution_authority
                else ["pre_execution_boundary_claims_execution_authority"]
            ),
            *([] if not pre_execution_boundary.executed else ["pre_execution_boundary_claims_execution"]),
            *(
                []
                if not pre_execution_boundary.provider_runtime_probe_performed
                else ["pre_execution_boundary_claims_provider_probe"]
            ),
            *(
                []
                if not pre_execution_boundary.provider_binary_executed
                else ["pre_execution_boundary_claims_provider_binary"]
            ),
            *(
                []
                if not pre_execution_boundary.service_query_performed
                else ["pre_execution_boundary_claims_service_query"]
            ),
            *([] if not pre_execution_boundary.process_launched else ["pre_execution_boundary_claims_process_launch"]),
            *(
                []
                if not pre_execution_boundary.container_launched
                else ["pre_execution_boundary_claims_container_launch"]
            ),
            *(
                []
                if not pre_execution_boundary.repo_code_executed
                else ["pre_execution_boundary_claims_repo_execution"]
            ),
            *([] if not pre_execution_boundary.network_accessed else ["pre_execution_boundary_claims_network_access"]),
            *([] if not pre_execution_boundary.wrote_to_repo else ["pre_execution_boundary_claims_repo_write"]),
            *(
                []
                if not pre_execution_boundary.execution_receipt_written
                else ["pre_execution_boundary_claims_execution_receipt"]
            ),
        )
        if identity_blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "provider_runtime_probe_runner_control_binding_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "sandbox_provider_runtime_probe_runner_pre_execution_boundary": pre_execution_boundary.to_dict(),
                    "blockers": identity_blockers,
                    "sandbox_provider_runtime_probe_runner_pre_execution_boundary_path": (
                        str(pre_execution_boundary_path) if pre_execution_boundary_path is not None else ""
                    ),
                    "execution": _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
                        recorded=False,
                        ready=False,
                        reason="provider_runtime_probe_runner_control_binding_blocked",
                    ),
                }
            )

        consumption, consumption_path = _find_lab_sandbox_provider_runtime_probe_approval_consumption(clean_approval_id)
        invocation_boundary, invocation_boundary_path = _find_lab_sandbox_provider_runtime_probe_invocation_boundary(
            clean_approval_id
        )
        execution_boundary, execution_boundary_path = _find_lab_sandbox_provider_runtime_probe_execution_boundary(
            pre_execution_boundary.execution_boundary_id
        )
        now = utc_now()
        control_binding_contract = _lab_sandbox_provider_runtime_probe_runner_control_binding_contract_payload(
            pre_execution_boundary=pre_execution_boundary,
        )
        current_checks = _lab_sandbox_provider_runtime_probe_runner_control_binding_current_checks(
            pre_execution_boundary=pre_execution_boundary,
        )
        required_checks = _lab_sandbox_provider_runtime_probe_runner_control_binding_required_checks()
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(
            missing_checks,
            "provider_runtime_probe_runner_control_binding_blocked_until_live_runner_enforced",
            "provider_runtime_probe_not_performed",
            "provider_binary_not_executed",
            "provider_service_not_queried",
            "process_not_launched",
            "container_not_launched",
            "repo_code_not_executed",
            "network_not_accessed",
            "repo_write_not_performed",
            "execution_receipt_not_written",
        )
        status = "ready" if not missing_checks else "blocked"
        boundary = LabSandboxProviderRuntimeProbeRunnerControlBinding(
            id=_lab_sandbox_provider_runtime_probe_runner_control_binding_id(
                pre_execution_boundary.id,
                clean_approval_id,
            ),
            approval_id=clean_approval_id,
            approval_consumption_id=pre_execution_boundary.approval_consumption_id,
            invocation_boundary_id=pre_execution_boundary.invocation_boundary_id,
            pre_execution_boundary_id=pre_execution_boundary.id,
            approval_request_id=pre_execution_boundary.approval_request_id,
            execution_boundary_id=pre_execution_boundary.execution_boundary_id,
            run_boundary_preflight_id=pre_execution_boundary.run_boundary_preflight_id,
            source_id=pre_execution_boundary.source_id,
            candidate_id=pre_execution_boundary.candidate_id,
            candidate_name=pre_execution_boundary.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=pre_execution_boundary.action,
            action_hash=pre_execution_boundary.action_hash,
            approval_consumption=consumption.to_dict() if consumption is not None else {},
            invocation_boundary=invocation_boundary.to_dict() if invocation_boundary is not None else {},
            pre_execution_boundary=pre_execution_boundary.to_dict(),
            execution_boundary=execution_boundary.to_dict() if execution_boundary is not None else {},
            control_binding_contract=control_binding_contract,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            pre_execution_boundary_found=bool(current_checks.get("pre_execution_boundary_found")),
            pre_execution_boundary_recorded=bool(current_checks.get("pre_execution_boundary_recorded")),
            pre_execution_boundary_ready=bool(current_checks.get("pre_execution_boundary_ready")),
            invocation_boundary_found=bool(current_checks.get("invocation_boundary_found")),
            invocation_boundary_recorded=bool(current_checks.get("invocation_boundary_recorded")),
            invocation_boundary_ready=bool(current_checks.get("invocation_boundary_ready")),
            approval_consumed=bool(current_checks.get("approval_consumed")),
            single_use_consumption_found=bool(current_checks.get("single_use_consumption_found")),
            single_use_enforced=bool(current_checks.get("single_use_enforced")),
            exact_action_binding_verified=bool(current_checks.get("exact_action_binding_verified")),
            control_binding_recorded=bool(current_checks.get("control_binding_recorded")),
            runner_identity_declared=bool(current_checks.get("runner_identity_declared")),
            runner_identity_binding_recorded=bool(current_checks.get("runner_identity_binding_recorded")),
            runner_identity_bound=bool(current_checks.get("runner_identity_bound")),
            runner_policy_declared=bool(current_checks.get("runner_policy_declared")),
            runner_policy_binding_recorded=bool(current_checks.get("runner_policy_binding_recorded")),
            runner_policy_bound=bool(current_checks.get("runner_policy_bound")),
            sandbox_policy_declared=bool(current_checks.get("sandbox_policy_declared")),
            sandbox_policy_binding_recorded=bool(current_checks.get("sandbox_policy_binding_recorded")),
            sandbox_policy_bound=bool(current_checks.get("sandbox_policy_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            network_block_declared=bool(current_checks.get("network_block_declared")),
            network_block_binding_recorded=bool(current_checks.get("network_block_binding_recorded")),
            network_block_bound=bool(current_checks.get("network_block_bound")),
            timeout_policy_declared=bool(current_checks.get("timeout_policy_declared")),
            timeout_policy_binding_recorded=bool(current_checks.get("timeout_policy_binding_recorded")),
            timeout_policy_bound=bool(current_checks.get("timeout_policy_bound")),
            output_capture_declared=bool(current_checks.get("output_capture_declared")),
            output_capture_binding_recorded=bool(current_checks.get("output_capture_binding_recorded")),
            output_capture_bound=bool(current_checks.get("output_capture_bound")),
            kill_switch_declared=bool(current_checks.get("kill_switch_declared")),
            kill_switch_binding_recorded=bool(current_checks.get("kill_switch_binding_recorded")),
            kill_switch_bound=bool(current_checks.get("kill_switch_bound")),
            execution_receipt_writer_declared=bool(current_checks.get("execution_receipt_writer_declared")),
            execution_receipt_writer_binding_recorded=bool(
                current_checks.get("execution_receipt_writer_binding_recorded")
            ),
            execution_receipt_writer_bound=bool(current_checks.get("execution_receipt_writer_bound")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("executed")),
            provider_runtime_probe_performed=bool(current_checks.get("provider_runtime_probe_performed")),
            provider_binary_executed=bool(current_checks.get("provider_binary_executed")),
            service_query_performed=bool(current_checks.get("service_query_performed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            execution_receipt_written=bool(current_checks.get("execution_receipt_written")),
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=blockers,
            validation_performed=[
                "provider_runtime_probe_runner_pre_execution_boundary_found",
                "runner_control_binding_requirements_recorded",
                "runner_identity_binding_recorded_without_live_runner",
                "runner_policy_binding_recorded_without_live_runner",
                "sandbox_policy_binding_recorded_without_live_sandbox",
                "network_block_binding_recorded_without_live_enforcement",
                "timeout_policy_binding_recorded_without_live_runner",
                "output_capture_binding_recorded_without_live_runner",
                "kill_switch_binding_recorded_without_live_runner",
                "execution_receipt_writer_binding_recorded_without_live_writer",
                "provider_runtime_probe_not_performed",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "repo_code_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "execution_authority_not_granted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_control_bindings",
            boundary.id,
            {"sandbox_provider_runtime_probe_runner_control_binding": boundary.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandbox.provider_runtime_probe.runner_control_binding",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(pre_execution_boundary_path) if pre_execution_boundary_path is not None else "",
                    str(invocation_boundary_path) if invocation_boundary_path is not None else "",
                    str(consumption_path) if consumption_path is not None else "",
                    str(execution_boundary_path) if execution_boundary_path is not None else "",
                ]
            ),
            input_hashes=[
                source.fingerprint,
                pre_execution_boundary.action_hash,
                pre_execution_boundary.id,
                pre_execution_boundary.invocation_boundary_id,
                pre_execution_boundary.approval_consumption_id,
                pre_execution_boundary.execution_boundary_id,
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=boundary.validation_performed,
        )
        boundary = replace(boundary, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_runtime_probe_control_bindings",
            boundary.id,
            {"sandbox_provider_runtime_probe_runner_control_binding": boundary.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_runtime_probe_runner_control_binding_path": str(artifact_path),
            "last_lab_runtime_probe_runner_control_binding_receipt_path": str(receipt_path),
            "last_lab_runtime_probe_runner_control_binding_status": boundary.status,
            "last_lab_runtime_probe_runner_pre_execution_boundary_id": pre_execution_boundary.id,
            "last_lab_runtime_probe_invocation_boundary_id": pre_execution_boundary.invocation_boundary_id,
            "last_lab_runtime_probe_approval_id": clean_approval_id,
            "last_lab_runtime_probe_runner_control_binding_action_hash": pre_execution_boundary.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == candidate.id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        execution = _lab_sandbox_provider_runtime_probe_execution_boundary_payload(
            recorded=execution_boundary is not None,
            ready=False,
            reason="provider_runtime_probe_runner_control_binding_no_execution",
        )
        execution.update(
            {
                "provider_runtime_probe_invocation_boundary_recorded": True,
                "provider_runtime_probe_runner_pre_execution_boundary_recorded": True,
                "provider_runtime_probe_runner_control_binding_recorded": True,
                "provider_runtime_probe_runner_control_binding_ready": boundary.status == "ready",
                "provider_runtime_probe_approval_consumed": True,
                "approval_consumed": True,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": boundary.status,
                "source": updated.to_dict(),
                "candidate": candidate.to_dict(),
                "sandbox_provider_runtime_probe_approval_consumption": consumption.to_dict() if consumption else {},
                "sandbox_provider_runtime_probe_execution_boundary": (
                    execution_boundary.to_dict() if execution_boundary is not None else {}
                ),
                "sandbox_provider_runtime_probe_invocation_boundary": (
                    invocation_boundary.to_dict() if invocation_boundary is not None else {}
                ),
                "sandbox_provider_runtime_probe_runner_pre_execution_boundary": pre_execution_boundary.to_dict(),
                "sandbox_provider_runtime_probe_runner_control_binding": boundary.to_dict(),
                "artifact_path": str(artifact_path),
                "sandbox_provider_runtime_probe_runner_control_binding_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def preflight_lab_sandboxed_rebuild_run_test_boundary(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        control_binding, control_binding_path = _find_lab_sandbox_provider_runtime_probe_runner_control_binding(
            clean_approval_id
        )
        if control_binding is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "provider_runtime_probe_runner_control_binding_missing",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_id": clean_approval_id,
                    "blockers": ["provider_runtime_probe_runner_control_binding_missing"],
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="provider_runtime_probe_runner_control_binding_missing",
                    ),
                }
            )

        identity_blockers = _append_unique(
            [],
            *([] if control_binding.source_id == source.id else ["source_identity_mismatch"]),
            *(
                []
                if control_binding.candidate_id == candidate.id and control_binding.candidate_name == candidate.name
                else ["candidate_identity_mismatch"]
            ),
            *([] if control_binding.approval_id == clean_approval_id else ["approval_identity_mismatch"]),
            *([] if control_binding.approval_consumed else ["provider_runtime_probe_approval_not_consumed"]),
            *([] if control_binding.single_use_enforced else ["single_use_consumption_not_enforced"]),
            *([] if control_binding.exact_action_binding_verified else ["exact_action_binding_not_verified"]),
            *([] if control_binding.control_binding_recorded else ["control_binding_not_recorded"]),
            *([] if not control_binding.execution_authority else ["control_binding_claims_execution_authority"]),
            *([] if not control_binding.executed else ["control_binding_claims_execution"]),
            *(
                []
                if not control_binding.provider_runtime_probe_performed
                else ["control_binding_claims_provider_probe"]
            ),
            *([] if not control_binding.provider_binary_executed else ["control_binding_claims_provider_binary"]),
            *([] if not control_binding.service_query_performed else ["control_binding_claims_service_query"]),
            *([] if not control_binding.process_launched else ["control_binding_claims_process_launch"]),
            *([] if not control_binding.container_launched else ["control_binding_claims_container_launch"]),
            *([] if not control_binding.repo_code_executed else ["control_binding_claims_repo_execution"]),
            *([] if not control_binding.network_accessed else ["control_binding_claims_network_access"]),
            *([] if not control_binding.wrote_to_repo else ["control_binding_claims_repo_write"]),
            *([] if not control_binding.execution_receipt_written else ["control_binding_claims_execution_receipt"]),
        )
        if identity_blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "sandboxed_rebuild_run_test_boundary_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "sandbox_provider_runtime_probe_runner_control_binding": control_binding.to_dict(),
                    "sandbox_provider_runtime_probe_runner_control_binding_path": (
                        str(control_binding_path) if control_binding_path is not None else ""
                    ),
                    "blockers": identity_blockers,
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="sandboxed_rebuild_run_test_boundary_blocked",
                    ),
                }
            )

        consumption, consumption_path = _find_lab_sandbox_provider_runtime_probe_approval_consumption(clean_approval_id)
        invocation_boundary, invocation_boundary_path = _find_lab_sandbox_provider_runtime_probe_invocation_boundary(
            clean_approval_id
        )
        pre_execution_boundary, pre_execution_boundary_path = (
            _find_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(clean_approval_id)
        )
        execution_boundary, execution_boundary_path = _find_lab_sandbox_provider_runtime_probe_execution_boundary(
            control_binding.execution_boundary_id
        )
        now = utc_now()
        action_payload = {
            "action": "francis.lab.execute",
            "mode": "future_sandboxed_rebuild_run_test",
            "approval_id": clean_approval_id,
            "control_binding_id": control_binding.id,
            "source_id": source.id,
            "candidate_id": candidate.id,
            "candidate_name": candidate.name,
        }
        action_hash = _stable_payload_hash(action_payload)
        execution_contract = _lab_sandboxed_rebuild_run_test_boundary_contract_payload(
            control_binding=control_binding,
            action_hash=action_hash,
        )
        current_checks = _lab_sandboxed_rebuild_run_test_boundary_current_checks(control_binding=control_binding)
        required_checks = _lab_sandboxed_rebuild_run_test_boundary_required_checks()
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(
            missing_checks,
            "sandboxed_rebuild_run_test_boundary_blocked_until_live_runner_enforced",
            "execution_approval_not_consumed",
            "sandboxed_execution_not_performed",
            "process_not_launched",
            "container_not_launched",
            "commands_not_executed",
            "repo_code_not_executed",
            "install_not_run",
            "build_not_run",
            "tests_not_run",
            "network_not_accessed",
            "repo_write_not_performed",
            "execution_receipt_not_written",
            "candidate_not_validated",
            "capability_not_promoted",
        )
        status = "ready" if not missing_checks else "blocked"
        boundary = LabSandboxedRebuildRunTestBoundary(
            id=_lab_sandboxed_rebuild_run_test_boundary_id(control_binding.id, clean_approval_id),
            approval_id=clean_approval_id,
            approval_consumption_id=control_binding.approval_consumption_id,
            invocation_boundary_id=control_binding.invocation_boundary_id,
            pre_execution_boundary_id=control_binding.pre_execution_boundary_id,
            control_binding_id=control_binding.id,
            approval_request_id=control_binding.approval_request_id,
            execution_boundary_id=control_binding.execution_boundary_id,
            run_boundary_preflight_id=control_binding.run_boundary_preflight_id,
            source_id=control_binding.source_id,
            candidate_id=control_binding.candidate_id,
            candidate_name=control_binding.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=action_hash,
            control_binding=control_binding.to_dict(),
            pre_execution_boundary=pre_execution_boundary.to_dict() if pre_execution_boundary is not None else {},
            invocation_boundary=invocation_boundary.to_dict() if invocation_boundary is not None else {},
            execution_boundary=execution_boundary.to_dict() if execution_boundary is not None else {},
            approval_consumption=consumption.to_dict() if consumption is not None else {},
            sandboxed_execution_contract=execution_contract,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            control_binding_found=bool(current_checks.get("control_binding_found")),
            control_binding_recorded=bool(current_checks.get("control_binding_recorded")),
            control_binding_ready=bool(current_checks.get("control_binding_ready")),
            approval_consumed=bool(current_checks.get("provider_probe_approval_consumed")),
            single_use_consumption_found=bool(current_checks.get("single_use_consumption_found")),
            single_use_enforced=bool(current_checks.get("single_use_enforced")),
            exact_action_binding_verified=bool(current_checks.get("exact_action_binding_verified")),
            execution_approval_required=bool(current_checks.get("execution_approval_required")),
            execution_approval_consumed=bool(current_checks.get("execution_approval_consumed")),
            runner_identity_bound=bool(current_checks.get("runner_identity_bound")),
            runner_policy_bound=bool(current_checks.get("runner_policy_bound")),
            sandbox_policy_bound=bool(current_checks.get("sandbox_policy_bound")),
            sandbox_bound=bool(current_checks.get("sandbox_bound")),
            sandbox_enforced=bool(current_checks.get("sandbox_enforced")),
            network_block_bound=bool(current_checks.get("network_block_bound")),
            timeout_policy_bound=bool(current_checks.get("timeout_policy_bound")),
            output_capture_bound=bool(current_checks.get("output_capture_bound")),
            kill_switch_bound=bool(current_checks.get("kill_switch_bound")),
            execution_receipt_writer_bound=bool(current_checks.get("execution_receipt_writer_bound")),
            rebuild_declared=bool(current_checks.get("rebuild_declared")),
            run_declared=bool(current_checks.get("run_declared")),
            test_declared=bool(current_checks.get("test_declared")),
            execution_authority=bool(current_checks.get("execution_authority")),
            executed=bool(current_checks.get("executed")),
            process_launched=bool(current_checks.get("process_launched")),
            container_launched=bool(current_checks.get("container_launched")),
            commands_executed=bool(current_checks.get("commands_executed")),
            repo_code_executed=bool(current_checks.get("repo_code_executed")),
            ran_install=bool(current_checks.get("ran_install")),
            ran_build=bool(current_checks.get("ran_build")),
            ran_tests=bool(current_checks.get("ran_tests")),
            network_accessed=bool(current_checks.get("network_accessed")),
            wrote_to_repo=bool(current_checks.get("wrote_to_repo")),
            execution_receipt_written=bool(current_checks.get("execution_receipt_written")),
            candidate_validated=bool(current_checks.get("candidate_validated")),
            capability_promoted=bool(current_checks.get("capability_promoted")),
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=blockers,
            validation_performed=[
                "provider_runtime_probe_runner_control_binding_found",
                "sandboxed_rebuild_run_test_boundary_recorded",
                "execution_approval_required_but_not_consumed",
                "live_runner_not_bound",
                "live_sandbox_not_enforced",
                "network_block_not_bound",
                "timeout_policy_not_bound",
                "output_capture_not_bound",
                "kill_switch_not_bound",
                "execution_receipt_writer_not_bound",
                "process_not_launched",
                "container_not_launched",
                "commands_not_executed",
                "repo_code_not_executed",
                "install_not_run",
                "build_not_run",
                "tests_not_run",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "candidate_not_validated",
                "capability_not_promoted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_boundaries",
            boundary.id,
            {"sandboxed_rebuild_run_test_boundary": boundary.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandboxed_rebuild_run_test.boundary",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(control_binding_path) if control_binding_path is not None else "",
                    str(pre_execution_boundary_path) if pre_execution_boundary_path is not None else "",
                    str(invocation_boundary_path) if invocation_boundary_path is not None else "",
                    str(consumption_path) if consumption_path is not None else "",
                    str(execution_boundary_path) if execution_boundary_path is not None else "",
                ]
            ),
            input_hashes=[
                source.fingerprint,
                action_hash,
                control_binding.id,
                control_binding.action_hash,
                control_binding.approval_consumption_id,
                control_binding.execution_boundary_id,
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=boundary.validation_performed,
        )
        boundary = replace(boundary, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_boundaries",
            boundary.id,
            {"sandboxed_rebuild_run_test_boundary": boundary.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandboxed_rebuild_run_test_boundary_path": str(artifact_path),
            "last_lab_sandboxed_rebuild_run_test_boundary_receipt_path": str(receipt_path),
            "last_lab_sandboxed_rebuild_run_test_boundary_status": boundary.status,
            "last_lab_runtime_probe_runner_control_binding_id": control_binding.id,
            "last_lab_runtime_probe_runner_pre_execution_boundary_id": control_binding.pre_execution_boundary_id,
            "last_lab_runtime_probe_approval_id": clean_approval_id,
            "last_lab_sandboxed_rebuild_run_test_action_hash": action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == candidate.id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        execution = _lab_sandboxed_rebuild_run_test_execution_payload(
            recorded=True,
            ready=boundary.status == "ready",
            reason="sandboxed_rebuild_run_test_boundary_no_execution",
        )
        execution.update(
            {
                "provider_runtime_probe_runner_control_binding_recorded": True,
                "provider_runtime_probe_runner_control_binding_ready": control_binding.status == "ready",
                "sandboxed_rebuild_run_test_boundary_recorded": True,
                "sandboxed_rebuild_run_test_boundary_ready": boundary.status == "ready",
                "provider_probe_approval_consumed": bool(control_binding.approval_consumed),
                "execution_approval_required": True,
                "execution_approval_consumed": False,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": boundary.status,
                "source": updated.to_dict(),
                "candidate": candidate.to_dict(),
                "sandbox_provider_runtime_probe_runner_control_binding": control_binding.to_dict(),
                "sandboxed_rebuild_run_test_boundary": boundary.to_dict(),
                "artifact_path": str(artifact_path),
                "sandboxed_rebuild_run_test_boundary_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def request_lab_sandboxed_rebuild_run_test_approval(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
        reason: str = "sandboxed_rebuild_run_test_requested",
    ) -> dict[str, Any]:
        clean_upstream_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        boundary, boundary_path = _find_lab_sandboxed_rebuild_run_test_boundary(clean_upstream_approval_id)
        if boundary is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "sandboxed_rebuild_run_test_boundary_missing",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_id": clean_upstream_approval_id,
                    "blockers": ["sandboxed_rebuild_run_test_boundary_missing"],
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="sandboxed_rebuild_run_test_boundary_missing",
                    ),
                }
            )

        identity_blockers = _append_unique(
            [],
            *([] if boundary.source_id == source.id else ["source_identity_mismatch"]),
            *(
                []
                if boundary.candidate_id == candidate.id and boundary.candidate_name == candidate.name
                else ["candidate_identity_mismatch"]
            ),
            *([] if boundary.approval_id == clean_upstream_approval_id else ["approval_identity_mismatch"]),
            *([] if boundary.control_binding_recorded else ["control_binding_not_recorded"]),
            *([] if boundary.execution_approval_required else ["execution_approval_not_required_by_boundary"]),
            *(
                []
                if not boundary.execution_approval_consumed
                else ["boundary_already_marks_execution_approval_consumed"]
            ),
            *([] if not boundary.execution_authority else ["boundary_claims_execution_authority"]),
            *([] if not boundary.executed else ["boundary_claims_execution"]),
            *([] if not boundary.process_launched else ["boundary_claims_process_launch"]),
            *([] if not boundary.container_launched else ["boundary_claims_container_launch"]),
            *([] if not boundary.commands_executed else ["boundary_claims_command_execution"]),
            *([] if not boundary.repo_code_executed else ["boundary_claims_repo_execution"]),
            *([] if not boundary.ran_install else ["boundary_claims_install_run"]),
            *([] if not boundary.ran_build else ["boundary_claims_build_run"]),
            *([] if not boundary.ran_tests else ["boundary_claims_tests_run"]),
            *([] if not boundary.network_accessed else ["boundary_claims_network_access"]),
            *([] if not boundary.wrote_to_repo else ["boundary_claims_repo_write"]),
            *([] if not boundary.execution_receipt_written else ["boundary_claims_execution_receipt"]),
            *([] if not boundary.candidate_validated else ["boundary_claims_candidate_validation"]),
            *([] if not boundary.capability_promoted else ["boundary_claims_capability_promotion"]),
        )
        if identity_blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "sandboxed_rebuild_run_test_approval_request_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "sandboxed_rebuild_run_test_boundary": boundary.to_dict(),
                    "sandboxed_rebuild_run_test_boundary_path": str(boundary_path) if boundary_path is not None else "",
                    "blockers": identity_blockers,
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="sandboxed_rebuild_run_test_approval_request_blocked",
                    ),
                }
            )

        blockers = _append_unique(
            boundary.blockers,
            *boundary.missing_checks,
            "sandboxed_rebuild_run_test_requires_operator_execution_approval",
            "sandboxed_rebuild_run_test_still_blocked_after_request",
        )
        action_payload = {
            "action": "francis.lab.sandboxed_rebuild_run_test",
            "upstream_approval_id": clean_upstream_approval_id,
            "sandboxed_boundary_id": boundary.id,
            "control_binding_id": boundary.control_binding_id,
            "source_id": boundary.source_id,
            "candidate_id": boundary.candidate_id,
            "candidate_name": boundary.candidate_name,
            "boundary_status": boundary.status,
            "boundary_missing_checks": boundary.missing_checks,
            "required_controls": boundary.required_checks,
        }
        action_hash = _stable_payload_hash(action_payload)
        approval_payload = _display_payload(
            {
                **action_payload,
                "action_hash": action_hash,
                "readiness": {
                    "sandboxed_rebuild_run_test_ready": False,
                    "boundary_status": boundary.status,
                    "blockers": blockers,
                },
                "governance": {
                    "approval_scope": "ingest.lab.sandboxed_rebuild_run_test.execute",
                    "approval_consumed": False,
                    "upstream_approval_consumed": False,
                    "execution_authority": False,
                    "process_launched": False,
                    "container_launched": False,
                    "commands_executed": False,
                    "repo_code_executed": False,
                    "ran_install": False,
                    "ran_build": False,
                    "ran_tests": False,
                    "network_accessed": False,
                    "wrote_to_repo": False,
                    "execution_receipt_written": False,
                    "candidate_validated": False,
                    "capability_promoted": False,
                },
            }
        )
        approval = approvals.request(
            action="francis.lab.sandboxed_rebuild_run_test",
            reason=_safe_str(reason).strip() or "sandboxed_rebuild_run_test_requested",
            payload=approval_payload,
        )
        sandboxed_approval_id = _safe_str(approval.get("id")).strip()
        approval_path = approvals.pending_dir() / f"{sandboxed_approval_id}.json" if sandboxed_approval_id else Path("")
        now = utc_now()
        request_record = LabSandboxedRebuildRunTestApprovalRequest(
            id=_lab_sandboxed_rebuild_run_test_approval_request_id(boundary.id, sandboxed_approval_id),
            approval_id=sandboxed_approval_id,
            upstream_approval_id=clean_upstream_approval_id,
            sandboxed_boundary_id=boundary.id,
            control_binding_id=boundary.control_binding_id,
            pre_execution_boundary_id=boundary.pre_execution_boundary_id,
            invocation_boundary_id=boundary.invocation_boundary_id,
            approval_consumption_id=boundary.approval_consumption_id,
            approval_request_id=boundary.approval_request_id,
            execution_boundary_id=boundary.execution_boundary_id,
            run_boundary_preflight_id=boundary.run_boundary_preflight_id,
            source_id=boundary.source_id,
            candidate_id=boundary.candidate_id,
            candidate_name=boundary.candidate_name,
            status="needs_approval",
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action="francis.lab.sandboxed_rebuild_run_test",
            action_hash=action_hash,
            approval_path=str(approval_path) if sandboxed_approval_id else "",
            approval_payload=approval_payload,
            sandboxed_boundary=boundary.to_dict(),
            blockers=blockers,
            approval_created=bool(sandboxed_approval_id),
            approval_consumed=False,
            upstream_approval_consumed=False,
            boundary_recorded=True,
            boundary_ready=boundary.status == "ready",
            execution_authority=False,
            executed=False,
            process_launched=False,
            container_launched=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            execution_receipt_written=False,
            candidate_validated=False,
            capability_promoted=False,
            store_file_contents=False,
            store_sensitive_values=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_approval_requests",
            request_record.id,
            {"sandboxed_rebuild_run_test_approval_request": request_record.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandboxed_rebuild_run_test.approval_request",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(boundary_path) if boundary_path is not None else "",
                ]
            ),
            input_hashes=[source.fingerprint, boundary.action_hash, action_hash, boundary.id],
            result_status="needs_approval",
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path), str(approval_path) if sandboxed_approval_id else ""],
            validation_performed=[
                "sandboxed_rebuild_run_test_boundary_readback_no_execution",
                "sandboxed_rebuild_run_test_approval_request_created",
                "approval_not_consumed",
                "execution_authority_not_granted",
                "process_not_launched",
                "container_not_launched",
                "commands_not_executed",
                "repo_code_not_executed",
                "install_not_run",
                "build_not_run",
                "tests_not_run",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "candidate_not_validated",
                "capability_not_promoted",
            ],
        )
        request_record = replace(request_record, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_approval_requests",
            request_record.id,
            {"sandboxed_rebuild_run_test_approval_request": request_record.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandboxed_rebuild_run_test_approval_request_path": str(artifact_path),
            "last_lab_sandboxed_rebuild_run_test_approval_request_receipt_path": str(receipt_path),
            "last_lab_sandboxed_rebuild_run_test_approval_id": sandboxed_approval_id,
            "last_lab_sandboxed_rebuild_run_test_approval_action_hash": action_hash,
            "last_lab_sandboxed_rebuild_run_test_boundary_id": boundary.id,
            "last_lab_runtime_probe_approval_id": clean_upstream_approval_id,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        execution = _lab_sandboxed_rebuild_run_test_execution_payload(
            recorded=True,
            ready=False,
            reason="sandboxed_rebuild_run_test_approval_requested_no_execution",
        )
        execution.update(
            {
                "approval_request_created": bool(sandboxed_approval_id),
                "sandboxed_rebuild_run_test_approval_id": sandboxed_approval_id,
                "sandboxed_rebuild_run_test_approval_consumed": False,
                "execution_approval_required": True,
                "execution_approval_consumed": False,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": "needs_approval",
                "source": updated.to_dict(),
                "candidate": candidate.to_dict(),
                "sandboxed_rebuild_run_test_boundary": boundary.to_dict(),
                "sandboxed_rebuild_run_test_approval_request": request_record.to_dict(),
                "approval": approval,
                "approval_path": str(approval_path) if sandboxed_approval_id else "",
                "artifact_path": str(artifact_path),
                "sandboxed_rebuild_run_test_approval_request_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def consume_lab_sandboxed_rebuild_run_test_approval(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        approval_request, approval_request_path = _find_lab_sandboxed_rebuild_run_test_approval_request(
            clean_approval_id
        )
        approval_status, approval_record, approval_path = _read_lab_approval_record(clean_approval_id)
        binding, approval_blockers = _lab_sandboxed_rebuild_run_test_approval_binding(
            approval_request=approval_request,
            approval_id=clean_approval_id,
            approval_status=approval_status,
            approval_record=approval_record,
            approval_path=approval_path,
        )
        existing_consumption, existing_consumption_path = _find_lab_sandboxed_rebuild_run_test_approval_consumption(
            clean_approval_id
        )
        boundary, boundary_path = (
            _find_lab_sandboxed_rebuild_run_test_boundary_by_id(approval_request.sandboxed_boundary_id)
            if approval_request is not None
            else (None, None)
        )
        blockers = _append_unique(
            [],
            *approval_blockers,
            *([] if approval_request is not None else ["sandboxed_rebuild_run_test_approval_request_missing"]),
            *([] if boundary is not None else ["sandboxed_rebuild_run_test_boundary_missing"]),
            *(
                []
                if approval_request is None or approval_request.source_id == source.id
                else ["source_identity_mismatch"]
            ),
            *(
                []
                if approval_request is None
                or (approval_request.candidate_id == candidate.id and approval_request.candidate_name == candidate.name)
                else ["candidate_identity_mismatch"]
            ),
            *(
                []
                if approval_request is None or approval_request.status == "needs_approval"
                else ["approval_request_status_not_needs_approval"]
            ),
            *(
                []
                if approval_request is None or approval_request.approval_created
                else ["approval_request_missing_created_approval"]
            ),
            *(
                []
                if approval_request is None or not approval_request.approval_consumed
                else ["approval_request_already_marks_consumed"]
            ),
            *(
                []
                if approval_request is None or approval_request.boundary_recorded
                else ["approval_request_missing_boundary_record"]
            ),
            *(
                []
                if approval_request is None or not approval_request.execution_authority
                else ["approval_request_claims_execution_authority"]
            ),
            *(
                []
                if approval_request is None or not approval_request.executed
                else ["approval_request_claims_execution"]
            ),
            *(
                []
                if approval_request is None or not approval_request.process_launched
                else ["approval_request_claims_process_launch"]
            ),
            *(
                []
                if approval_request is None or not approval_request.container_launched
                else ["approval_request_claims_container_launch"]
            ),
            *(
                []
                if approval_request is None or not approval_request.commands_executed
                else ["approval_request_claims_command_execution"]
            ),
            *(
                []
                if approval_request is None or not approval_request.repo_code_executed
                else ["approval_request_claims_repo_execution"]
            ),
            *(
                []
                if approval_request is None or not approval_request.ran_install
                else ["approval_request_claims_install_run"]
            ),
            *(
                []
                if approval_request is None or not approval_request.ran_build
                else ["approval_request_claims_build_run"]
            ),
            *(
                []
                if approval_request is None or not approval_request.ran_tests
                else ["approval_request_claims_tests_run"]
            ),
            *(
                []
                if approval_request is None or not approval_request.network_accessed
                else ["approval_request_claims_network_access"]
            ),
            *(
                []
                if approval_request is None or not approval_request.wrote_to_repo
                else ["approval_request_claims_repo_write"]
            ),
            *(
                []
                if approval_request is None or not approval_request.execution_receipt_written
                else ["approval_request_claims_execution_receipt"]
            ),
            *(
                []
                if approval_request is None or not approval_request.candidate_validated
                else ["approval_request_claims_candidate_validation"]
            ),
            *(
                []
                if approval_request is None or not approval_request.capability_promoted
                else ["approval_request_claims_capability_promotion"]
            ),
            *([] if existing_consumption is None else ["sandboxed_rebuild_run_test_approval_already_consumed"]),
        )
        refused = bool(binding.get("refused"))
        if blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "refused" if refused else "blocked",
                    "error": "sandboxed_rebuild_run_test_approval_consumption_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_binding": binding,
                    "blockers": blockers,
                    "sandboxed_rebuild_run_test_approval_request_path": (
                        str(approval_request_path) if approval_request_path is not None else ""
                    ),
                    "sandboxed_rebuild_run_test_boundary_path": (
                        str(boundary_path) if boundary_path is not None else ""
                    ),
                    "existing_sandboxed_rebuild_run_test_approval_consumption_path": (
                        str(existing_consumption_path) if existing_consumption_path is not None else ""
                    ),
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=approval_request is not None,
                        ready=False,
                        reason="sandboxed_rebuild_run_test_approval_consumption_blocked",
                    ),
                }
            )

        assert approval_request is not None
        now = utc_now()
        consumption = LabSandboxedRebuildRunTestApprovalConsumption(
            id=_lab_sandboxed_rebuild_run_test_approval_consumption_id(
                clean_approval_id,
                approval_request.id,
            ),
            approval_id=clean_approval_id,
            approval_request_id=approval_request.id,
            upstream_approval_id=approval_request.upstream_approval_id,
            upstream_approval_consumption_id=approval_request.approval_consumption_id,
            sandboxed_boundary_id=approval_request.sandboxed_boundary_id,
            control_binding_id=approval_request.control_binding_id,
            pre_execution_boundary_id=approval_request.pre_execution_boundary_id,
            invocation_boundary_id=approval_request.invocation_boundary_id,
            upstream_approval_request_id=approval_request.approval_request_id,
            execution_boundary_id=approval_request.execution_boundary_id,
            run_boundary_preflight_id=approval_request.run_boundary_preflight_id,
            source_id=approval_request.source_id,
            candidate_id=approval_request.candidate_id,
            candidate_name=approval_request.candidate_name,
            status="consumed",
            created_at=now,
            updated_at=now,
            consumed_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=approval_request.action,
            action_hash=approval_request.action_hash,
            approval_status=approval_status,
            approval_path=str(approval_path) if approval_path is not None else "",
            approval_snapshot=_lab_approval_snapshot(approval_record),
            approval_binding=binding,
            approval_request=approval_request.to_dict(),
            sandboxed_boundary=boundary.to_dict() if boundary is not None else approval_request.sandboxed_boundary,
            approval_consumed=True,
            single_use_enforced=True,
            upstream_approval_consumed=False,
            boundary_recorded=True,
            boundary_ready=approval_request.boundary_ready,
            execution_authority=False,
            executed=False,
            process_launched=False,
            container_launched=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            execution_receipt_written=False,
            candidate_validated=False,
            capability_promoted=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=[
                "sandboxed_rebuild_run_test_approval_consumed_for_future_execution_only",
                "execution_authority_not_granted",
                "process_not_launched",
                "container_not_launched",
                "repository_commands_not_executed",
                "install_not_run",
                "build_not_run",
                "tests_not_run",
                "repository_code_not_executed",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "candidate_not_validated",
                "capability_not_promoted",
                "approval_reuse_blocked_by_consumption_record",
            ],
            validation_performed=[
                "sandboxed_rebuild_run_test_approval_request_found",
                "approved_exact_action_binding_checked",
                "sandboxed_rebuild_run_test_approval_consumption_record_written",
                "single_use_consumption_record_declared",
                "execution_authority_not_granted",
                "process_not_launched",
                "container_not_launched",
                "commands_not_executed",
                "repo_code_not_executed",
                "install_not_run",
                "build_not_run",
                "tests_not_run",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "candidate_not_validated",
                "capability_not_promoted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_approval_consumptions",
            consumption.id,
            {"sandboxed_rebuild_run_test_approval_consumption": consumption.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandboxed_rebuild_run_test.approval.consume",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(approval_request_path) if approval_request_path is not None else "",
                    str(boundary_path) if boundary_path is not None else "",
                    str(approval_path) if approval_path is not None else "",
                ],
            ),
            input_hashes=[
                source.fingerprint,
                approval_request.action_hash,
                approval_request.id,
                approval_request.sandboxed_boundary_id,
                _stable_payload_hash(binding),
            ],
            result_status=consumption.status,
            warnings=consumption.warnings,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=consumption.validation_performed,
        )
        consumption = replace(consumption, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_approval_consumptions",
            consumption.id,
            {"sandboxed_rebuild_run_test_approval_consumption": consumption.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandboxed_rebuild_run_test_approval_consumption_path": str(artifact_path),
            "last_lab_sandboxed_rebuild_run_test_approval_consumption_receipt_path": str(receipt_path),
            "last_lab_sandboxed_rebuild_run_test_approval_consumption_status": consumption.status,
            "last_lab_sandboxed_rebuild_run_test_approval_consumed": consumption.approval_consumed,
            "last_lab_sandboxed_rebuild_run_test_approval_id": clean_approval_id,
            "last_lab_sandboxed_rebuild_run_test_approval_request_id": approval_request.id,
            "last_lab_sandboxed_rebuild_run_test_approval_action_hash": approval_request.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == approval_request.candidate_id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        execution = _lab_sandboxed_rebuild_run_test_execution_payload(
            recorded=True,
            ready=False,
            reason="sandboxed_rebuild_run_test_approval_consumed_no_execution",
        )
        execution.update(
            {
                "approval_consumed": True,
                "sandboxed_rebuild_run_test_approval_consumed": True,
                "sandboxed_rebuild_run_test_approval_id": clean_approval_id,
                "execution_approval_consumed": True,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": consumption.status,
                "source": updated.to_dict(),
                "candidate": candidate.to_dict(),
                "sandboxed_rebuild_run_test_boundary": boundary.to_dict() if boundary is not None else {},
                "sandboxed_rebuild_run_test_approval_request": approval_request.to_dict(),
                "sandboxed_rebuild_run_test_approval_consumption": consumption.to_dict(),
                "approval_binding": binding,
                "artifact_path": str(artifact_path),
                "sandboxed_rebuild_run_test_approval_consumption_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def preflight_lab_sandboxed_rebuild_run_test_runner_binding(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        provider_kind: str = "local_process_sandbox",
        provider_reference: str = "",
        provider_policy_manifest: str = "",
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        consumption, consumption_path = _find_lab_sandboxed_rebuild_run_test_approval_consumption(clean_approval_id)
        boundary, boundary_path = (
            _find_lab_sandboxed_rebuild_run_test_boundary_by_id(consumption.sandboxed_boundary_id)
            if consumption is not None
            else (None, None)
        )
        identity_blockers = _append_unique(
            [],
            *([] if consumption is not None else ["sandboxed_rebuild_run_test_approval_consumption_missing"]),
            *([] if boundary is not None else ["sandboxed_rebuild_run_test_boundary_missing"]),
            *([] if consumption is None or consumption.source_id == source.id else ["source_identity_mismatch"]),
            *(
                []
                if consumption is None
                or (consumption.candidate_id == candidate.id and consumption.candidate_name == candidate.name)
                else ["candidate_identity_mismatch"]
            ),
            *(
                []
                if consumption is None or consumption.approval_id == clean_approval_id
                else ["approval_identity_mismatch"]
            ),
            *([] if consumption is None or consumption.approval_consumed else ["sandboxed_approval_not_consumed"]),
            *(
                []
                if consumption is None or consumption.single_use_enforced
                else ["single_use_consumption_not_enforced"]
            ),
            *(
                []
                if consumption is None or not consumption.execution_authority
                else ["consumption_claims_execution_authority"]
            ),
            *([] if consumption is None or not consumption.executed else ["consumption_claims_execution"]),
            *([] if consumption is None or not consumption.process_launched else ["consumption_claims_process_launch"]),
            *(
                []
                if consumption is None or not consumption.container_launched
                else ["consumption_claims_container_launch"]
            ),
            *(
                []
                if consumption is None or not consumption.commands_executed
                else ["consumption_claims_command_execution"]
            ),
            *(
                []
                if consumption is None or not consumption.repo_code_executed
                else ["consumption_claims_repo_execution"]
            ),
            *([] if consumption is None or not consumption.ran_install else ["consumption_claims_install_run"]),
            *([] if consumption is None or not consumption.ran_build else ["consumption_claims_build_run"]),
            *([] if consumption is None or not consumption.ran_tests else ["consumption_claims_tests_run"]),
            *([] if consumption is None or not consumption.network_accessed else ["consumption_claims_network_access"]),
            *([] if consumption is None or not consumption.wrote_to_repo else ["consumption_claims_repo_write"]),
            *(
                []
                if consumption is None or not consumption.execution_receipt_written
                else ["consumption_claims_execution_receipt"]
            ),
            *(
                []
                if consumption is None or not consumption.candidate_validated
                else ["consumption_claims_candidate_validation"]
            ),
            *(
                []
                if consumption is None or not consumption.capability_promoted
                else ["consumption_claims_capability_promotion"]
            ),
        )
        if identity_blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "sandboxed_rebuild_run_test_runner_binding_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_id": clean_approval_id,
                    "blockers": identity_blockers,
                    "sandboxed_rebuild_run_test_approval_consumption": (
                        consumption.to_dict() if consumption is not None else {}
                    ),
                    "sandboxed_rebuild_run_test_approval_consumption_path": (
                        str(consumption_path) if consumption_path is not None else ""
                    ),
                    "sandboxed_rebuild_run_test_boundary_path": str(boundary_path) if boundary_path is not None else "",
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=consumption is not None,
                        ready=False,
                        reason="sandboxed_rebuild_run_test_runner_binding_blocked",
                    ),
                }
            )

        assert consumption is not None
        clean_provider_kind = _normalize_lab_sandbox_provider_kind(provider_kind)
        provider_reference_metadata = _lab_provider_reference_metadata(provider_reference)
        provider_policy_manifest_metadata = _lab_provider_policy_manifest_metadata(provider_policy_manifest)
        action_payload = {
            "action": "francis.lab.sandboxed_rebuild_run_test",
            "approval_id": clean_approval_id,
            "approval_consumption_id": consumption.id,
            "source_id": source.id,
            "candidate_id": candidate.id,
            "candidate_name": candidate.name,
            "provider_kind": clean_provider_kind,
            "provider_reference": _safe_str(provider_reference_metadata.get("reference")).strip(),
            "provider_policy_manifest": _safe_str(provider_policy_manifest_metadata.get("path")).strip(),
        }
        action_hash = _stable_payload_hash(action_payload)
        contract = _lab_sandboxed_rebuild_run_test_runner_binding_contract_payload(
            consumption=consumption,
            provider_kind=clean_provider_kind,
            provider_reference=provider_reference_metadata,
            provider_policy_manifest=provider_policy_manifest_metadata,
            action_hash=action_hash,
        )
        current_checks = _lab_sandboxed_rebuild_run_test_runner_binding_current_checks(
            consumption=consumption,
            provider_kind=clean_provider_kind,
            provider_reference=provider_reference_metadata,
            provider_policy_manifest=provider_policy_manifest_metadata,
            contract=contract,
        )
        required_checks = _lab_sandboxed_rebuild_run_test_runner_binding_required_checks()
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(
            missing_checks,
            "sandboxed_rebuild_run_test_runner_binding_preflight_only",
            "live_sandbox_runner_not_bound",
            "sandbox_not_enforced",
            "commands_not_executed",
            "repo_code_not_executed",
            "install_not_run",
            "build_not_run",
            "tests_not_run",
            "execution_receipt_not_written",
            "candidate_not_validated",
            "capability_not_promoted",
        )
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "provider_binary_executed",
                "provider_service_queried",
                "execution_authority",
                "executed",
                "process_launched",
                "container_launched",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "execution_receipt_written",
                "candidate_validated",
                "capability_promoted",
            )
        )
        status = "refused" if unsafe_state else "ready" if not missing_checks else "blocked"
        now = utc_now()
        binding = LabSandboxedRebuildRunTestRunnerBindingPreflight(
            id=_lab_sandboxed_rebuild_run_test_runner_binding_id(
                consumption.id,
                clean_provider_kind,
                _safe_str(provider_reference_metadata.get("reference")).strip(),
                _safe_str(provider_policy_manifest_metadata.get("path")).strip(),
            ),
            approval_id=clean_approval_id,
            approval_consumption_id=consumption.id,
            approval_request_id=consumption.approval_request_id,
            sandboxed_boundary_id=consumption.sandboxed_boundary_id,
            control_binding_id=consumption.control_binding_id,
            source_id=source.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=consumption.action,
            action_hash=action_hash,
            provider_kind=clean_provider_kind,
            selected_provider_kind=_safe_str(contract.get("selected_provider_kind")).strip(),
            approval_consumption=consumption.to_dict(),
            sandboxed_boundary=boundary.to_dict() if boundary is not None else consumption.sandboxed_boundary,
            provider_reference=provider_reference_metadata,
            provider_policy_manifest=provider_policy_manifest_metadata,
            runner_binding_contract=contract,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            approval_consumed=bool(current_checks.get("approval_consumed")),
            single_use_enforced=bool(current_checks.get("single_use_enforced")),
            static_provider_reference_bound=bool(current_checks.get("static_provider_reference_bound")),
            provider_reference_checked=bool(current_checks.get("provider_reference_checked")),
            provider_reference_present=bool(current_checks.get("provider_reference_present")),
            provider_reference_verified=bool(current_checks.get("provider_reference_verified")),
            provider_policy_manifest_present=bool(current_checks.get("provider_policy_manifest_present")),
            provider_policy_manifest_bound=bool(current_checks.get("provider_policy_manifest_bound")),
            runner_binding_declared=bool(current_checks.get("runner_binding_declared")),
            live_runner_bound=False,
            sandbox_runner_bound=False,
            sandbox_bound=False,
            sandbox_enforced=False,
            network_block_bound=False,
            timeout_policy_bound=False,
            output_capture_bound=False,
            kill_switch_bound=False,
            command_allowlist_bound=False,
            source_mount_bound=False,
            execution_receipt_writer_bound=False,
            provider_binary_executed=False,
            provider_service_queried=False,
            execution_authority=False,
            executed=False,
            process_launched=False,
            container_launched=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            execution_receipt_written=False,
            candidate_validated=False,
            capability_promoted=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=blockers,
            validation_performed=[
                "sandboxed_rebuild_run_test_approval_consumption_found",
                "static_provider_reference_metadata_checked",
                "provider_policy_manifest_metadata_checked_without_contents",
                "sandboxed_rebuild_run_test_runner_binding_preflight_recorded",
                "live_runner_not_bound",
                "sandbox_runner_not_bound",
                "sandbox_not_enforced",
                "provider_binary_not_executed",
                "provider_service_not_queried",
                "process_not_launched",
                "container_not_launched",
                "commands_not_executed",
                "repo_code_not_executed",
                "install_not_run",
                "build_not_run",
                "tests_not_run",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "candidate_not_validated",
                "capability_not_promoted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_runner_bindings",
            binding.id,
            {"sandboxed_rebuild_run_test_runner_binding": binding.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandboxed_rebuild_run_test.runner_binding",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(consumption_path) if consumption_path is not None else "",
                    str(boundary_path) if boundary_path is not None else "",
                    _safe_str(provider_reference_metadata.get("reference")).strip(),
                    _safe_str(provider_policy_manifest_metadata.get("path")).strip(),
                ],
            ),
            input_hashes=[
                source.fingerprint,
                consumption.action_hash,
                consumption.id,
                action_hash,
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=binding.warnings,
            errors=binding.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=binding.validation_performed,
        )
        binding = replace(binding, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_runner_bindings",
            binding.id,
            {"sandboxed_rebuild_run_test_runner_binding": binding.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandboxed_rebuild_run_test_runner_binding_path": str(artifact_path),
            "last_lab_sandboxed_rebuild_run_test_runner_binding_receipt_path": str(receipt_path),
            "last_lab_sandboxed_rebuild_run_test_runner_binding_status": status,
            "last_lab_sandboxed_rebuild_run_test_runner_binding_id": binding.id,
            "last_lab_sandboxed_rebuild_run_test_provider_kind": binding.selected_provider_kind,
            "last_lab_sandboxed_rebuild_run_test_approval_id": clean_approval_id,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == candidate.id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        execution = _lab_sandboxed_rebuild_run_test_execution_payload(
            recorded=True,
            ready=False,
            reason="sandboxed_rebuild_run_test_runner_binding_preflight_no_execution",
        )
        execution.update(
            {
                "sandboxed_rebuild_run_test_approval_consumed": True,
                "sandboxed_rebuild_run_test_runner_binding_recorded": True,
                "static_provider_reference_bound": binding.static_provider_reference_bound,
                "live_runner_bound": False,
                "sandbox_runner_bound": False,
                "sandbox_enforced": False,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "candidate": candidate.to_dict(),
                "sandboxed_rebuild_run_test_approval_consumption": consumption.to_dict(),
                "sandboxed_rebuild_run_test_boundary": boundary.to_dict() if boundary is not None else {},
                "sandboxed_rebuild_run_test_runner_binding": binding.to_dict(),
                "artifact_path": str(artifact_path),
                "sandboxed_rebuild_run_test_runner_binding_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def preflight_lab_sandboxed_rebuild_run_test_sandbox_policy(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=False,
                        ready=False,
                        reason="capability_candidate_unavailable",
                    ),
                }
            )

        consumption, consumption_path = _find_lab_sandboxed_rebuild_run_test_approval_consumption(clean_approval_id)
        runner_binding, runner_binding_path = _find_lab_sandboxed_rebuild_run_test_runner_binding(clean_approval_id)
        identity_blockers = _append_unique(
            [],
            *([] if consumption is not None else ["sandboxed_rebuild_run_test_approval_consumption_missing"]),
            *([] if runner_binding is not None else ["sandboxed_rebuild_run_test_runner_binding_missing"]),
            *([] if consumption is None or consumption.source_id == source.id else ["source_identity_mismatch"]),
            *(
                []
                if consumption is None
                or (consumption.candidate_id == candidate.id and consumption.candidate_name == candidate.name)
                else ["candidate_identity_mismatch"]
            ),
            *(
                []
                if runner_binding is None or runner_binding.source_id == source.id
                else ["runner_binding_source_identity_mismatch"]
            ),
            *(
                []
                if runner_binding is None
                or (runner_binding.candidate_id == candidate.id and runner_binding.candidate_name == candidate.name)
                else ["runner_binding_candidate_identity_mismatch"]
            ),
            *(
                []
                if consumption is None or consumption.approval_id == clean_approval_id
                else ["approval_identity_mismatch"]
            ),
            *(
                []
                if runner_binding is None or runner_binding.approval_id == clean_approval_id
                else ["runner_binding_approval_identity_mismatch"]
            ),
            *(
                []
                if consumption is None
                or runner_binding is None
                or runner_binding.approval_consumption_id == consumption.id
                else ["runner_binding_consumption_identity_mismatch"]
            ),
            *([] if consumption is None or consumption.approval_consumed else ["sandboxed_approval_not_consumed"]),
            *(
                []
                if consumption is None or consumption.single_use_enforced
                else ["single_use_consumption_not_enforced"]
            ),
            *(
                []
                if runner_binding is None or runner_binding.static_provider_reference_bound
                else ["static_provider_reference_not_bound"]
            ),
            *(
                []
                if runner_binding is None
                or (
                    bool(runner_binding.selected_provider_kind)
                    and runner_binding.selected_provider_kind != "unselected"
                )
                else ["sandbox_provider_kind_not_selected"]
            ),
            *(
                []
                if consumption is None or not consumption.execution_authority
                else ["consumption_claims_execution_authority"]
            ),
            *([] if consumption is None or not consumption.executed else ["consumption_claims_execution"]),
            *([] if consumption is None or not consumption.process_launched else ["consumption_claims_process_launch"]),
            *(
                []
                if consumption is None or not consumption.container_launched
                else ["consumption_claims_container_launch"]
            ),
            *(
                []
                if consumption is None or not consumption.commands_executed
                else ["consumption_claims_command_execution"]
            ),
            *(
                []
                if consumption is None or not consumption.repo_code_executed
                else ["consumption_claims_repo_execution"]
            ),
            *([] if consumption is None or not consumption.network_accessed else ["consumption_claims_network_access"]),
            *([] if consumption is None or not consumption.wrote_to_repo else ["consumption_claims_repo_write"]),
            *(
                []
                if consumption is None or not consumption.execution_receipt_written
                else ["consumption_claims_execution_receipt"]
            ),
            *(
                []
                if runner_binding is None or not runner_binding.execution_authority
                else ["runner_binding_claims_execution_authority"]
            ),
            *([] if runner_binding is None or not runner_binding.executed else ["runner_binding_claims_execution"]),
            *(
                []
                if runner_binding is None or not runner_binding.process_launched
                else ["runner_binding_claims_process_launch"]
            ),
            *(
                []
                if runner_binding is None or not runner_binding.container_launched
                else ["runner_binding_claims_container_launch"]
            ),
            *(
                []
                if runner_binding is None or not runner_binding.commands_executed
                else ["runner_binding_claims_command_execution"]
            ),
            *(
                []
                if runner_binding is None or not runner_binding.repo_code_executed
                else ["runner_binding_claims_repo_execution"]
            ),
            *(
                []
                if runner_binding is None or not runner_binding.network_accessed
                else ["runner_binding_claims_network_access"]
            ),
            *(
                []
                if runner_binding is None or not runner_binding.wrote_to_repo
                else ["runner_binding_claims_repo_write"]
            ),
            *(
                []
                if runner_binding is None or not runner_binding.execution_receipt_written
                else ["runner_binding_claims_execution_receipt"]
            ),
        )
        if identity_blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "sandboxed_rebuild_run_test_sandbox_policy_blocked",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "approval_id": clean_approval_id,
                    "blockers": identity_blockers,
                    "sandboxed_rebuild_run_test_approval_consumption": (
                        consumption.to_dict() if consumption is not None else {}
                    ),
                    "sandboxed_rebuild_run_test_approval_consumption_path": (
                        str(consumption_path) if consumption_path is not None else ""
                    ),
                    "sandboxed_rebuild_run_test_runner_binding": (
                        runner_binding.to_dict() if runner_binding is not None else {}
                    ),
                    "sandboxed_rebuild_run_test_runner_binding_path": (
                        str(runner_binding_path) if runner_binding_path is not None else ""
                    ),
                    "execution": _lab_sandboxed_rebuild_run_test_execution_payload(
                        recorded=consumption is not None and runner_binding is not None,
                        ready=False,
                        reason="sandboxed_rebuild_run_test_sandbox_policy_blocked",
                    ),
                }
            )

        assert consumption is not None
        assert runner_binding is not None
        action_payload = {
            "action": "francis.lab.sandboxed_rebuild_run_test",
            "approval_id": clean_approval_id,
            "approval_consumption_id": consumption.id,
            "runner_binding_id": runner_binding.id,
            "source_id": source.id,
            "candidate_id": candidate.id,
            "candidate_name": candidate.name,
            "policy_mode": "policy_preflight_no_live_sandbox",
        }
        action_hash = _stable_payload_hash(action_payload)
        sandbox_policy = _lab_sandboxed_rebuild_run_test_sandbox_policy_payload(
            consumption=consumption,
            runner_binding=runner_binding,
            action_hash=action_hash,
        )
        current_checks = _lab_sandboxed_rebuild_run_test_sandbox_policy_current_checks(
            consumption=consumption,
            runner_binding=runner_binding,
            sandbox_policy=sandbox_policy,
        )
        required_checks = _lab_sandboxed_rebuild_run_test_sandbox_policy_required_checks()
        missing_checks = [check for check in required_checks if not bool(current_checks.get(check))]
        blockers = _append_unique(
            missing_checks,
            "sandboxed_rebuild_run_test_sandbox_policy_preflight_only",
            "live_sandbox_not_bound",
            "sandbox_not_enforced",
            "command_allowlist_not_bound",
            "execution_receipt_writer_not_bound",
            "commands_not_executed",
            "repo_code_not_executed",
            "install_not_run",
            "build_not_run",
            "tests_not_run",
            "candidate_not_validated",
            "capability_not_promoted",
        )
        unsafe_state = any(
            bool(current_checks.get(check))
            for check in (
                "execution_authority",
                "executed",
                "process_launched",
                "container_launched",
                "commands_executed",
                "repo_code_executed",
                "network_accessed",
                "wrote_to_repo",
                "execution_receipt_written",
            )
        )
        status = "refused" if unsafe_state else "ready" if not missing_checks else "blocked"
        now = utc_now()
        policy = LabSandboxedRebuildRunTestSandboxPolicyPreflight(
            id=_lab_sandboxed_rebuild_run_test_sandbox_policy_id(runner_binding.id, action_hash),
            approval_id=clean_approval_id,
            approval_consumption_id=consumption.id,
            runner_binding_id=runner_binding.id,
            approval_request_id=consumption.approval_request_id,
            sandboxed_boundary_id=consumption.sandboxed_boundary_id,
            control_binding_id=consumption.control_binding_id,
            source_id=source.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=_safe_str(actor).strip() or "francis/system",
            action=consumption.action,
            action_hash=action_hash,
            approval_consumption=consumption.to_dict(),
            runner_binding=runner_binding.to_dict(),
            provider_reference=runner_binding.provider_reference,
            provider_policy_manifest=runner_binding.provider_policy_manifest,
            sandbox_policy=sandbox_policy,
            required_checks=required_checks,
            current_checks=current_checks,
            missing_checks=missing_checks,
            blockers=blockers,
            approval_consumed=bool(current_checks.get("approval_consumed")),
            single_use_enforced=bool(current_checks.get("single_use_enforced")),
            runner_binding_present=bool(current_checks.get("runner_binding_present")),
            static_provider_reference_bound=bool(current_checks.get("static_provider_reference_bound")),
            provider_kind_selected=bool(current_checks.get("provider_kind_selected")),
            sandbox_policy_declared=bool(current_checks.get("sandbox_policy_declared")),
            network_default_deny=bool(current_checks.get("network_default_deny")),
            network_allowed=False,
            repo_write_allowed=False,
            destructive_allowed=False,
            secret_storage_allowed=False,
            command_execution_enabled=False,
            command_allowlist_bound=False,
            execution_receipt_writer_bound=False,
            live_sandbox_bound=False,
            sandbox_enforced=False,
            source_read_only_reference=bool(current_checks.get("filesystem_read_only")),
            process_launch_allowed=False,
            container_launch_allowed=False,
            provider_binary_execution_allowed=False,
            provider_service_query_allowed=False,
            timeout_policy_bound=False,
            output_capture_bound=False,
            kill_switch_bound=False,
            env_passthrough_allowed=False,
            execution_authority=False,
            executed=False,
            process_launched=False,
            container_launched=False,
            commands_executed=False,
            repo_code_executed=False,
            ran_install=False,
            ran_build=False,
            ran_tests=False,
            network_accessed=False,
            wrote_to_repo=False,
            execution_receipt_written=False,
            candidate_validated=False,
            capability_promoted=False,
            store_file_contents=False,
            store_sensitive_values=False,
            warnings=blockers,
            validation_performed=[
                "sandboxed_rebuild_run_test_approval_consumption_found",
                "sandboxed_rebuild_run_test_runner_binding_found",
                "sandbox_policy_declared_no_live_sandbox",
                "network_default_deny_recorded",
                "source_reference_read_only_policy_recorded",
                "repo_write_disallowed",
                "destructive_action_disallowed",
                "secret_storage_disallowed",
                "command_execution_disabled",
                "command_allowlist_not_bound",
                "execution_receipt_writer_not_bound",
                "live_sandbox_not_bound",
                "sandbox_not_enforced",
                "process_not_launched",
                "container_not_launched",
                "commands_not_executed",
                "repo_code_not_executed",
                "install_not_run",
                "build_not_run",
                "tests_not_run",
                "network_not_accessed",
                "repo_write_not_performed",
                "execution_receipt_not_written",
                "candidate_not_validated",
                "capability_not_promoted",
            ],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_sandbox_policies",
            policy.id,
            {"sandboxed_rebuild_run_test_sandbox_policy": policy.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.sandboxed_rebuild_run_test.sandbox_policy",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [
                    source.canonical_path,
                    str(consumption_path) if consumption_path is not None else "",
                    str(runner_binding_path) if runner_binding_path is not None else "",
                ],
            ),
            input_hashes=[
                source.fingerprint,
                consumption.action_hash,
                runner_binding.action_hash,
                runner_binding.id,
                action_hash,
                _stable_payload_hash(current_checks),
            ],
            result_status=status,
            warnings=policy.warnings,
            errors=policy.errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=policy.validation_performed,
        )
        policy = replace(policy, receipts=[str(receipt_path)])
        artifact_path = write_ingest_record_artifact(
            "lab_sandboxed_rebuild_run_test_sandbox_policies",
            policy.id,
            {"sandboxed_rebuild_run_test_sandbox_policy": policy.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_sandboxed_rebuild_run_test_sandbox_policy_path": str(artifact_path),
            "last_lab_sandboxed_rebuild_run_test_sandbox_policy_receipt_path": str(receipt_path),
            "last_lab_sandboxed_rebuild_run_test_sandbox_policy_status": status,
            "last_lab_sandboxed_rebuild_run_test_sandbox_policy_id": policy.id,
            "last_lab_sandboxed_rebuild_run_test_approval_id": clean_approval_id,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        for item in self.capabilities.list_for_source(source.id):
            if item.id == candidate.id:
                self._replace_candidate(
                    source.id,
                    item.id,
                    replace(item, receipts=_append_unique(item.receipts, str(receipt_path))),
                )
                break
        execution = _lab_sandboxed_rebuild_run_test_execution_payload(
            recorded=True,
            ready=False,
            reason="sandboxed_rebuild_run_test_sandbox_policy_preflight_no_execution",
        )
        execution.update(
            {
                "sandboxed_rebuild_run_test_approval_consumed": True,
                "sandboxed_rebuild_run_test_runner_binding_recorded": True,
                "sandboxed_rebuild_run_test_sandbox_policy_recorded": True,
                "sandbox_policy_declared": True,
                "network_default_deny": True,
                "repo_write_allowed": False,
                "destructive_allowed": False,
                "command_execution_enabled": False,
                "command_allowlist_bound": False,
                "execution_receipt_writer_bound": False,
                "live_sandbox_bound": False,
                "sandbox_enforced": False,
            }
        )
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "candidate": candidate.to_dict(),
                "sandboxed_rebuild_run_test_approval_consumption": consumption.to_dict(),
                "sandboxed_rebuild_run_test_runner_binding": runner_binding.to_dict(),
                "sandboxed_rebuild_run_test_sandbox_policy": policy.to_dict(),
                "artifact_path": str(artifact_path),
                "sandboxed_rebuild_run_test_sandbox_policy_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": execution,
            }
        )

    def preflight_lab_approval_consumption(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_approval_id = _safe_str(approval_id).strip()
        preflight_result = self.preflight_lab_execution(source_or_path, candidate_ref, actor=actor)
        preflight = LabExecutionPreflight.from_dict(preflight_result.get("preflight"))
        source = SourceRecord.from_dict(preflight_result.get("source"))
        if preflight is None or source is None:
            return _display_payload(
                {
                    **preflight_result,
                    "status": "failed",
                    "error": "lab_preflight_unavailable",
                    "execution": _no_lab_execution_payload(reason="lab_preflight_unavailable"),
                }
            )

        approval_status, approval_record, approval_path = _read_lab_approval_record(clean_approval_id)
        binding, approval_blockers = _lab_approval_binding(
            preflight=preflight,
            approval_id=clean_approval_id,
            approval_status=approval_status,
            approval_record=approval_record,
            approval_path=approval_path,
        )
        runner_blockers = _append_unique(
            approval_blockers,
            "approval_consumption_disabled_in_v0",
            "governed_lab_runner_not_bound",
            "execution_receipt_runner_binding_missing",
        )
        refused = bool(binding.get("refused"))
        status = "refused" if refused else "blocked"
        now = utc_now()
        runner_contract = LabRunnerContract(
            id=_lab_runner_contract_id(preflight.id, clean_approval_id),
            preflight_id=preflight.id,
            workspace_id=preflight.workspace_id,
            source_id=preflight.source_id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status="blocked",
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            approval_id=clean_approval_id,
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            runner_kind="francis.lab.runner",
            runner_bound=False,
            execution_enabled=False,
            required_controls=_lab_runner_required_controls(),
            current_controls={
                "approval_record_found": bool(binding.get("approval_record_found")),
                "approval_status": approval_status,
                "approval_approved": bool(binding.get("approval_approved")),
                "approval_exact_match": bool(binding.get("exact_match")),
                "approval_consumption_ready": False,
                "workspace_ready": bool(preflight.readiness.get("workspace_ready")),
                "source_copied": bool(preflight.readiness.get("source_copied")),
                "runner_bound": False,
                "network_isolation_enforced": False,
                "filesystem_write_boundary_enforced": False,
                "resource_limits_enforced": False,
                "execution_receipt_sink_bound": False,
            },
            blockers=runner_blockers,
            execution_authority=False,
            executed=False,
        )
        runner_contract_path = write_ingest_record_artifact(
            "lab_runner_contracts",
            runner_contract.id,
            {"runner_contract": runner_contract.to_dict()},
        )
        consumption_preflight = LabApprovalConsumptionPreflight(
            id=_lab_approval_consumption_preflight_id(preflight.id, clean_approval_id),
            approval_id=clean_approval_id,
            preflight_id=preflight.id,
            plan_id=preflight.plan_id,
            workspace_id=preflight.workspace_id,
            source_id=preflight.source_id,
            candidate_id=preflight.candidate_id,
            candidate_name=preflight.candidate_name,
            status=status,
            created_at=now,
            updated_at=now,
            actor=actor.strip() or "francis/system",
            action="francis.lab.execute",
            action_hash=preflight.action_hash,
            approval_status=approval_status,
            approval_path=str(approval_path) if approval_path is not None else "",
            approval_snapshot=_lab_approval_snapshot(approval_record),
            binding=binding,
            runner_contract_id=runner_contract.id,
            runner_contract=runner_contract.to_dict(),
            blockers=runner_blockers,
            approval_consumed=False,
            execution_authority=False,
            executed=False,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_approval_consumption_preflights",
            consumption_preflight.id,
            {"approval_consumption": consumption_preflight.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.approval_consumption_preflight",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [source.canonical_path],
                str(approval_path) if approval_path is not None else "",
            ),
            input_hashes=[source.fingerprint, preflight.action_hash],
            result_status=status,
            warnings=runner_blockers,
            errors=runner_blockers if refused else [],
            generated_artifact_paths=[str(artifact_path), str(runner_contract_path)],
            validation_performed=[
                "approval_record_readback_no_mutation",
                "exact_action_hash_binding_check",
                "source_candidate_workspace_identity_binding_check",
                "runner_contract_projected_no_execution",
                "approval_not_consumed",
                "execution_authority_not_granted",
            ],
        )
        runner_contract = replace(runner_contract, receipts=[str(receipt_path)])
        runner_contract_path = write_ingest_record_artifact(
            "lab_runner_contracts",
            runner_contract.id,
            {"runner_contract": runner_contract.to_dict()},
        )
        consumption_preflight = replace(
            consumption_preflight,
            runner_contract=runner_contract.to_dict(),
            receipts=[str(receipt_path)],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_approval_consumption_preflights",
            consumption_preflight.id,
            {"approval_consumption": consumption_preflight.to_dict()},
        )
        metadata = {
            **source.metadata,
            "last_lab_approval_consumption_preflight_path": str(artifact_path),
            "last_lab_approval_consumption_preflight_receipt_path": str(receipt_path),
            "last_lab_runner_contract_path": str(runner_contract_path),
            "last_lab_approval_consumption_status": status,
            "last_lab_approval_id": clean_approval_id,
            "last_lab_execution_action_hash": preflight.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path), str(runner_contract_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": status,
                "source": updated.to_dict(),
                "preflight": preflight.to_dict(),
                "approval_consumption": consumption_preflight.to_dict(),
                "runner_contract": runner_contract.to_dict(),
                "approval": _lab_approval_snapshot(approval_record),
                "approval_path": str(approval_path) if approval_path is not None else "",
                "artifact_path": str(artifact_path),
                "runner_contract_path": str(runner_contract_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="approval_consumption_preflight_no_execution"),
            }
        )

    def refuse_lab_execution(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        actor: str = "francis/system",
        reason: str = "francis_lab_execution_not_available",
    ) -> dict[str, Any]:
        plan_result = self.plan_lab(source_or_path, candidate_ref, actor=actor)
        plan = LabPlan.from_dict(plan_result.get("plan"))
        source = SourceRecord.from_dict(plan_result.get("source"))
        if plan is None or source is None:
            return _display_payload(
                {
                    **plan_result,
                    "status": "blocked",
                    "execution": _no_lab_execution_payload(reason="lab_plan_unavailable"),
                }
            )

        blockers = _append_unique(plan.blockers, "lab_execution_disabled_in_v0", "no_governed_runner_bound")
        refusal = LabExecutionRefusal(
            id=_lab_refusal_id(plan.id),
            plan_id=plan.id,
            source_id=plan.source_id,
            candidate_id=plan.candidate_id,
            candidate_name=plan.candidate_name,
            timestamp=utc_now(),
            actor=actor.strip() or "francis/system",
            reason=reason.strip() or "francis_lab_execution_not_available",
            blockers=blockers,
            permission_scope=plan.permissions_required.approval_scope,
            execution_authority=False,
            executed=False,
            network_accessed=False,
            wrote_to_repo=False,
        )
        artifact_path = write_ingest_record_artifact("lab_refusals", refusal.id, {"refusal": refusal.to_dict()})
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.refuse",
            source_id=source.id,
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[source.fingerprint],
            result_status="blocked",
            errors=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "lab_plan_readback_no_execution",
                "execution_authority_denial",
                "refusal_receipt_created",
            ],
        )
        refusal = replace(refusal, receipt_path=str(receipt_path))
        artifact_path = write_ingest_record_artifact("lab_refusals", refusal.id, {"refusal": refusal.to_dict()})
        metadata = {
            **source.metadata,
            "last_lab_execution_refusal_path": str(artifact_path),
            "last_lab_execution_refusal_receipt_path": str(receipt_path),
            "last_lab_execution_refusal_reason": refusal.reason,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        candidate = self.capabilities.list_for_source(source.id)
        for item in candidate:
            if item.id == plan.candidate_id:
                self._replace_candidate(
                    source.id, item.id, replace(item, receipts=_append_unique(item.receipts, str(receipt_path)))
                )
                break
        return _display_payload(
            {
                "ok": True,
                "status": "blocked",
                "source": updated.to_dict(),
                "plan": plan.to_dict(),
                "refusal": refusal.to_dict(),
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason=refusal.reason),
            }
        )

    def run_lab_capability(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        approval_id: str,
        *,
        opt_in: bool = False,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        """Francis Lab v0: attempt a safe, sandboxed rebuild/run of a capability.

        Real execution happens ONLY when all of these hold: a consumed exact-action
        approval exists upstream, the candidate is safe + non-destructive, the
        operator passed ``opt_in=True``, and a live Docker daemon is reachable.
        Otherwise the run is SIMULATED (a Francis-owned no-op) and can never reach
        the ``validated`` promotion state. Every attempt writes a receipt.
        """

        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            refusal = self._emit_lab_run_refusal_receipt(
                refusal_code="capability_candidate_unavailable",
                actor=actor,
                approval_id=clean_approval_id,
                source=source,
                candidate_ref=candidate_ref,
                blockers=["capability_candidate_unavailable"],
            )
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    **refusal,
                    "execution": _no_lab_execution_payload(reason="capability_candidate_unavailable"),
                }
            )

        repo_map = self._load_repo_map(source)
        if repo_map is None:
            refusal = self._emit_lab_run_refusal_receipt(
                refusal_code="repo_map_unavailable",
                actor=actor,
                approval_id=clean_approval_id,
                source=source,
                candidate=candidate,
                blockers=["repo_map_unavailable"],
            )
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "repo_map_unavailable",
                    "source": source.to_dict(),
                    **refusal,
                    "execution": _no_lab_execution_payload(reason="repo_map_unavailable"),
                }
            )

        # Authority evidence: a consumed exact-action approval for THIS candidate.
        consumption, consumption_path = _find_lab_sandboxed_rebuild_run_test_approval_consumption(clean_approval_id)
        authority_blockers: list[str] = []
        if consumption is None:
            authority_blockers.append("sandboxed_rebuild_run_test_approval_not_consumed")
        else:
            if consumption.source_id != source.id:
                authority_blockers.append("approval_source_identity_mismatch")
            if consumption.candidate_id != candidate.id:
                authority_blockers.append("approval_candidate_identity_mismatch")
            if not consumption.approval_consumed or consumption.status != "consumed":
                authority_blockers.append("approval_consumption_not_finalized")

        # Safety gate: only safe, non-destructive candidates may enter the Lab.
        safety = candidate_lab_safety(candidate, repo_map)

        if authority_blockers or not safety.safe:
            blockers = _append_unique([], *authority_blockers, *safety.blockers)
            refusal = self._emit_lab_run_refusal_receipt(
                refusal_code="lab_run_refused",
                actor=actor,
                approval_id=clean_approval_id,
                source=source,
                candidate=candidate,
                blockers=blockers,
            )
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "lab_run_refused",
                    "blockers": blockers,
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "safety": safety.to_dict(),
                    **refusal,
                    "execution": _no_lab_execution_payload(reason="lab_run_refused"),
                }
            )

        # Decide real vs simulated.
        docker = detect_docker(self._lab_command_runner)
        sim_reasons: list[str] = []
        if not opt_in:
            sim_reasons.append("opt_in_not_provided")
        if not docker.available:
            sim_reasons.append(f"docker_unavailable:{docker.reason or 'unknown'}")
        allow_real = not sim_reasons

        rebuild_plan = self.rebuilder.plan(candidate, repo_map)
        run_id = f"lab_run_{utc_now().replace(':', '').replace('-', '')}_{uuid.uuid4().hex[:8]}"
        container_name = run_id.replace(".", "_")
        image = os.environ.get("FRANCIS_LAB_IMAGE", "francis-lab-base:pinned").strip() or "francis-lab-base:pinned"
        sandbox_plan = SandboxPlan(
            image=image,
            container_name=container_name,
            source_path=source.canonical_path,
            script=rebuild_plan.container_script,
        )

        if allow_real:
            outcome = self.sandbox.run_real(sandbox_plan, detected_commands=rebuild_plan.detected_commands)
        else:
            outcome = self.sandbox.simulate(sandbox_plan, reason=";".join(sim_reasons) or "simulated")

        validation_status = validate_run(outcome)
        promotion = decide_promotion(candidate.status, outcome, validation_status)

        warnings = _append_unique(
            [],
            *(
                []
                if outcome.execution_mode == EXECUTION_MODE_REAL
                else ["simulated_run_no_repository_command_executed", "validation_cannot_reach_valid_on_simulated"]
            ),
            *([] if not outcome.failure_reason else [f"failure:{outcome.failure_reason}"]),
        )

        now = utc_now()
        run_receipt = LabExecutionRunReceipt(
            lab_run_id=run_id,
            operation="lab.execution.run",
            source_id=source.id,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            approval_id=clean_approval_id,
            sandbox_id=outcome.sandbox_id,
            execution_mode=outcome.execution_mode,
            image=image,
            commands_run=outcome.commands_run,
            container_argv=outcome.argv,
            exit_code=outcome.exit_code,
            stdout_summary=outcome.stdout_summary,
            stderr_summary=outcome.stderr_summary,
            timed_out=outcome.timed_out,
            duration_ms=outcome.duration_ms,
            validation_status=validation_status,
            promotion_from=promotion.from_status,
            promotion_to=promotion.to_status,
            promoted=promotion.promoted,
            failure_reason=outcome.failure_reason,
            created_at=now,
            actor=actor,
            executed=outcome.execution_mode == EXECUTION_MODE_REAL,
            repo_code_executed=outcome.repo_code_executed,
            network_accessed=outcome.network_accessed,
            wrote_to_repo=outcome.wrote_to_repo,
            execution_authority=outcome.execution_mode == EXECUTION_MODE_REAL,
            approval_consumed=consumption is not None,
            opt_in=opt_in,
            warnings=warnings,
        )

        artifact_path = write_ingest_record_artifact(
            "lab_execution_runs", run_id, {"lab_execution_run": run_receipt.to_dict()}
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.run",
            source_id=source.id,
            actor=actor,
            input_paths=_append_unique(
                [source.canonical_path],
                str(consumption_path) if consumption_path else "",
            ),
            input_hashes=[source.fingerprint, consumption.action_hash if consumption else ""],
            result_status=validation_status,
            warnings=warnings,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                f"execution_mode:{outcome.execution_mode}",
                f"validation_status:{validation_status}",
                f"promotion:{promotion.from_status}->{promotion.to_status}",
                "approval_consumption_verified",
                "safety_gate_passed",
            ],
        )
        run_receipt = replace(
            run_receipt,
            receipts=[str(receipt_path)],
            artifacts_generated=[str(artifact_path)],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_execution_runs", run_id, {"lab_execution_run": run_receipt.to_dict()}
        )

        # Promote the candidate (one rung at most; never validated on simulated).
        if promotion.promoted and promotion.to_status != candidate.status:
            updated_candidate = replace(
                candidate,
                status=promotion.to_status,
                receipts=_append_unique(candidate.receipts, str(receipt_path)),
            )
            self._replace_candidate(source.id, candidate.id, updated_candidate)
        else:
            updated_candidate = candidate

        return _display_payload(
            {
                "ok": True,
                "status": validation_status,
                "execution_mode": outcome.execution_mode,
                "source": source.to_dict(),
                "candidate": updated_candidate.to_dict(),
                "safety": safety.to_dict(),
                "docker": docker.to_dict(),
                "simulated_reasons": sim_reasons,
                "rebuild_plan": rebuild_plan.to_dict(),
                "lab_execution_run": run_receipt.to_dict(),
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "promotion": promotion.to_dict(),
                "execution": {
                    "executed": outcome.execution_mode == EXECUTION_MODE_REAL,
                    "execution_mode": outcome.execution_mode,
                    "repo_code_executed": outcome.repo_code_executed,
                    "network_accessed": outcome.network_accessed,
                    "validation_status": validation_status,
                },
            }
        )

    def _emit_lab_run_refusal_receipt(
        self,
        *,
        refusal_code: str,
        actor: str,
        approval_id: str = "",
        source: SourceRecord | None = None,
        candidate: CapabilityCandidate | None = None,
        candidate_ref: str = "",
        blockers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Write a refusal `lab.execution.run` receipt for a blocked/early-return run.

        Mirrors the success-path receipt shape but asserts only negatives: no
        execution, no sandbox run, no validation, no promotion, no authority. Used
        so that every governed `run_lab_capability` path is auditable.
        """

        now = utc_now()
        run_id = f"lab_run_{now.replace(':', '').replace('-', '')}_{uuid.uuid4().hex[:8]}"
        source_id = source.id if source is not None else ""
        candidate_status = candidate.status if candidate is not None else ""
        block_list = _append_unique([], *(blockers or []))
        warnings = _append_unique(
            [
                "lab_run_refused",
                "no_sandbox_run",
                "repository_code_not_executed",
                "no_validation_performed",
                "no_promotion",
            ],
            *[f"blocker:{item}" for item in block_list],
        )
        run_receipt = LabExecutionRunReceipt(
            lab_run_id=run_id,
            operation="lab.execution.run",
            source_id=source_id,
            candidate_id=candidate.id if candidate is not None else "",
            candidate_name=(candidate.name if candidate is not None else _safe_str(candidate_ref).strip()),
            approval_id=_safe_str(approval_id).strip(),
            sandbox_id="",
            execution_mode="refused",
            image="",
            commands_run=[],
            container_argv=[],
            exit_code=None,
            stdout_summary="",
            stderr_summary="",
            timed_out=False,
            duration_ms=0,
            validation_status="REFUSED",
            promotion_from=candidate_status,
            promotion_to=candidate_status,
            promoted=False,
            failure_reason=refusal_code,
            created_at=now,
            actor=actor,
            executed=False,
            repo_code_executed=False,
            network_accessed=False,
            wrote_to_repo=False,
            execution_authority=False,
            approval_consumed=False,
            opt_in=False,
            warnings=warnings,
        )
        artifact_path = write_ingest_record_artifact(
            "lab_execution_runs", run_id, {"lab_execution_run": run_receipt.to_dict()}
        )
        receipt, receipt_path = self.receipts.write(
            operation="lab.execution.run",
            source_id=source_id,
            actor=actor,
            input_paths=[source.canonical_path] if source is not None else [],
            input_hashes=[source.fingerprint] if source is not None else [],
            result_status="refused",
            warnings=warnings,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=_append_unique(
                [
                    f"refusal_code:{refusal_code}",
                    "no_execution",
                    "no_sandbox_run",
                    "no_validation",
                    "no_promotion",
                ],
                *[f"blocker:{item}" for item in block_list],
            ),
        )
        run_receipt = replace(
            run_receipt,
            receipts=[str(receipt_path)],
            artifacts_generated=[str(artifact_path)],
        )
        artifact_path = write_ingest_record_artifact(
            "lab_execution_runs", run_id, {"lab_execution_run": run_receipt.to_dict()}
        )
        return {
            "lab_execution_run": run_receipt.to_dict(),
            "artifact_path": str(artifact_path),
            "receipt": receipt.to_dict(),
            "receipt_path": str(receipt_path),
        }

    def _record_lab_execution_receipt_artifact(
        self,
        *,
        source: SourceRecord,
        artifact_path: Path,
        receipt_path: Path,
        execution_receipt: LabSyntheticExecutionReceipt,
    ) -> SourceRecord:
        metadata = {
            **source.metadata,
            "last_lab_execution_receipt_path": str(artifact_path),
            "last_lab_execution_receipt_receipt_path": str(receipt_path),
            "last_lab_execution_receipt_status": execution_receipt.status,
            "last_lab_execution_receipt_synthetic": execution_receipt.synthetic,
            "last_lab_execution_receipt_finalized": execution_receipt.finalized,
            "last_lab_approval_id": execution_receipt.approval_id,
            "last_lab_execution_action_hash": execution_receipt.action_hash,
        }
        updated = replace(
            source,
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(source.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(source.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return updated
