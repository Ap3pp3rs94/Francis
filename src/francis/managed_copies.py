from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis.economy.stage17_closure import (
    STAGE17_CLOSURE_DECISION_GAP,
    stage17_operator_stage_closure_decision_readback,
)
from francis.kernel.paths import data_dir
from francis.managed_copy_creation import (
    latest_managed_copy_creation_plan_receipt_for_preflight,
    latest_managed_copy_preflight_receipt_for_request,
    latest_managed_copy_request_receipt_for_stage17,
    managed_copy_creation_plan_dry_run,
    managed_copy_creation_plan_receipts_readback,
    managed_copy_preflight_plan,
    managed_copy_preflight_receipts_readback,
    managed_copy_request_plan,
    managed_copy_request_receipts_readback,
    record_managed_copy_creation_plan,
    record_managed_copy_preflight,
    record_managed_copy_request,
)
from francis.managed_copy_approval import (
    latest_managed_copy_creation_approval_for_plan,
    managed_copy_creation_approval_request_plan,
    managed_copy_creation_approval_requests_readback,
    record_managed_copy_creation_approval_request,
)
from francis.managed_copy_isolation import (
    latest_managed_copy_isolation_verification_for_provision,
    managed_copy_isolation_verification_plan,
    managed_copy_isolation_verification_receipts_readback,
    record_managed_copy_isolation_verification,
)
from francis.managed_copy_provisioning import (
    latest_managed_copy_provision_for_approval,
    managed_copy_provision_for_copy,
    managed_copy_provision_plan,
    managed_copy_provision_receipts_readback,
    record_managed_copy_provision,
)
from francis.managed_copy_safe_delta import (
    managed_copy_safe_delta_review_plan,
    managed_copy_safe_delta_review_receipts_readback,
    record_managed_copy_safe_delta_review,
)
from francis.managed_copy_safe_delta_approval import (
    managed_copy_safe_delta_decision_plan,
    managed_copy_safe_delta_decisions_readback,
    record_managed_copy_safe_delta_decision,
)
from francis.managed_copy_safe_delta_export import managed_copy_safe_delta_export_preflight
from francis.managed_copy_safe_delta_export_authorization import (
    managed_copy_safe_delta_export_authorization_request_plan,
    managed_copy_safe_delta_export_authorization_requests_readback,
    record_managed_copy_safe_delta_export_authorization_request,
)
from francis.managed_copy_safe_delta_export_authorization_decision import (
    managed_copy_safe_delta_export_authorization_decision_plan,
    managed_copy_safe_delta_export_authorization_decisions_readback,
    record_managed_copy_safe_delta_export_authorization_decision,
)
from francis.managed_copy_safe_delta_export_artifact_plan import managed_copy_safe_delta_export_artifact_plan
from francis.managed_copy_rogue_detection_assessment import (
    managed_copy_rogue_detection_assessment_plan,
    managed_copy_rogue_detection_assessments_readback,
    record_managed_copy_rogue_detection_assessment,
)
from francis.managed_copy_integrity_scan import managed_copy_integrity_scan
from francis.managed_copy_integrity_evidence import (
    managed_copy_integrity_evidence_plan,
    managed_copy_integrity_evidence_readback,
    record_managed_copy_integrity_evidence,
)
from francis.managed_copy_tenant_access import managed_copy_tenant_access_check

STAGE18_MANAGED_COPIES_STAGE = "Stage 18 / Managed Copies Platform"
MANAGED_COPIES_STATUS_KIND = "francis.stage18.managed_copies.status"
MANAGED_COPIES_COPY_CREATION_CONTRACT_KIND = "francis.stage18.managed_copies.copy_creation_contract"
MANAGED_COPIES_COPY_CREATION_REQUEST_KIND = "francis.stage18.managed_copies.copy_creation_request"
MANAGED_COPIES_COPY_CREATION_PREFLIGHT_KIND = "francis.stage18.managed_copies.copy_creation_preflight"
MANAGED_COPIES_COPY_CREATION_PLAN_KIND = "francis.stage18.managed_copies.copy_creation_plan"
MANAGED_COPIES_COPY_CREATION_APPROVAL_REQUEST_KIND = "francis.stage18.managed_copies.copy_creation_approval_request"
MANAGED_COPIES_COPY_CREATION_PROVISION_KIND = "francis.stage18.managed_copies.copy_creation_provision"
MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE = "managed_copies.copy_creation.write"
MANAGED_COPIES_ISOLATION_RULES_CONTRACT_KIND = "francis.stage18.managed_copies.isolation_rules_contract"
MANAGED_COPIES_ISOLATION_VERIFICATION_KIND = "francis.stage18.managed_copies.isolation_verification"
MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE = "managed_copies.isolation_verification.write"
MANAGED_COPIES_SAFE_DELTA_MODEL_CONTRACT_KIND = "francis.stage18.managed_copies.safe_delta_model_contract"
MANAGED_COPIES_SAFE_DELTA_REVIEW_KIND = "francis.stage18.managed_copies.safe_delta_review"
MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE = "managed_copies.safe_delta.write"
MANAGED_COPIES_SAFE_DELTA_APPROVAL_WRITE_SCOPE = "managed_copies.safe_delta.approval.write"
MANAGED_COPIES_SAFE_DELTA_EXPORT_PREFLIGHT_SCOPE = "managed_copies.safe_delta.export.preflight"
MANAGED_COPIES_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_SCOPE = "managed_copies.safe_delta.export.authorization.request"
MANAGED_COPIES_SAFE_DELTA_EXPORT_AUTHORIZATION_DECISION_SCOPE = "managed_copies.safe_delta.export.authorization.decide"
MANAGED_COPIES_SAFE_DELTA_EXPORT_ARTIFACT_PREFLIGHT_SCOPE = "managed_copies.safe_delta.export.artifact.preflight"
MANAGED_COPIES_ROGUE_RECOVERY_CONTRACT_KIND = "francis.stage18.managed_copies.rogue_recovery_contract"
MANAGED_COPIES_ROGUE_RECOVERY_REVIEW_KIND = "francis.stage18.managed_copies.rogue_recovery_review"
MANAGED_COPIES_ROGUE_RECOVERY_WRITE_SCOPE = "managed_copies.rogue_recovery.write"
MANAGED_COPIES_SLA_FRAMEWORK_CONTRACT_KIND = "francis.stage18.managed_copies.sla_framework_contract"
MANAGED_COPIES_SLA_COMMITMENT_REVIEW_KIND = "francis.stage18.managed_copies.sla_commitment_review"
MANAGED_COPIES_SLA_WRITE_SCOPE = "managed_copies.sla.write"
MANAGED_COPIES_ROLES_CONTRACT_KIND = "francis.stage18.managed_copies.roles_contract"
MANAGED_COPIES_ROLE_AUTHORITY_REVIEW_KIND = "francis.stage18.managed_copies.role_authority_review"
MANAGED_COPIES_ROLE_AUTHORITY_WRITE_SCOPE = "managed_copies.role_authority.write"
MANAGED_COPIES_DECOMMISSION_CONTRACT_KIND = "francis.stage18.managed_copies.decommission_contract"
MANAGED_COPIES_DECOMMISSION_REVIEW_KIND = "francis.stage18.managed_copies.decommission_review"
MANAGED_COPIES_DECOMMISSION_WRITE_SCOPE = "managed_copies.decommission.write"
MANAGED_COPIES_COMPLETION_REVIEW_KIND = "francis.stage18.managed_copies.completion_review"
MANAGED_COPIES_RUNTIME_EVIDENCE_CONTRACT_KIND = "francis.stage18.managed_copies.runtime_evidence_contract"
MANAGED_COPIES_RUNTIME_EVIDENCE_READBACKS_KIND = "francis.stage18.managed_copies.runtime_evidence_readbacks"
MANAGED_COPIES_RUNTIME_EVIDENCE_READBACK_KIND = "francis.stage18.managed_copies.runtime_evidence_readback"
MANAGED_COPIES_RUNTIME_EVIDENCE_WRITE_SCOPE = "managed_copies.runtime_evidence.write"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_limit(value: int, *, default: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, 1), 500)


def _runtime_evidence_path() -> Path:
    return data_dir() / "logs" / "managed_copies" / "runtime_evidence.jsonl"


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-_safe_limit(limit) :]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _deliverable(
    deliverable_id: str,
    title: str,
    *,
    ready: bool,
    status: str,
    next_gap: str,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": deliverable_id,
        "title": title,
        "ready": ready,
        "status": status,
        "next_gap": next_gap,
        "evidence": evidence or [],
    }


def _governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "projection_only": True,
        "copy_creation_enabled": False,
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "core_surrender_allowed": False,
        "privacy_weak_pooling_allowed": False,
        "uncontrolled_forks_allowed": False,
        "invisible_vendor_power_allowed": False,
    }


def _contract_requirement(
    requirement_id: str,
    title: str,
    *,
    ready: bool,
    required: bool = True,
    next_gap: str,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "title": title,
        "ready": ready,
        "required": required,
        "next_gap": next_gap,
        "evidence": evidence or [],
    }


def _contract_step(
    step_id: str,
    title: str,
    *,
    status: str,
    writes_tenant_state: bool = False,
    writes_registry: bool = False,
    writes_receipt: bool = False,
    requires_operator_approval: bool = True,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "status": status,
        "writes_tenant_state": writes_tenant_state,
        "writes_registry": writes_registry,
        "writes_receipt": writes_receipt,
        "requires_operator_approval": requires_operator_approval,
    }


def _isolation_domain(
    domain_id: str,
    title: str,
    *,
    isolated: bool,
    enforcement_status: str,
    verification_gap: str,
) -> dict[str, Any]:
    return {
        "id": domain_id,
        "title": title,
        "isolated": isolated,
        "enforcement_status": enforcement_status,
        "verification_gap": verification_gap,
    }


def _safe_delta_signal_class(
    signal_id: str,
    title: str,
    *,
    allowed: bool,
    status: str,
    redaction_required: bool = True,
) -> dict[str, Any]:
    return {
        "id": signal_id,
        "title": title,
        "allowed": allowed,
        "status": status,
        "redaction_required": redaction_required,
    }


def _rogue_recovery_signal(
    signal_id: str,
    title: str,
    *,
    status: str,
    severity: str,
    requires_evidence_preservation: bool = True,
) -> dict[str, Any]:
    return {
        "id": signal_id,
        "title": title,
        "status": status,
        "severity": severity,
        "requires_evidence_preservation": requires_evidence_preservation,
    }


def _rogue_recovery_step(
    step_id: str,
    title: str,
    *,
    status: str,
    writes_receipt: bool,
    mutates_copy_state: bool,
    requires_operator_approval: bool = True,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "status": status,
        "writes_receipt": writes_receipt,
        "mutates_copy_state": mutates_copy_state,
        "requires_operator_approval": requires_operator_approval,
    }


def _sla_commitment(
    commitment_id: str,
    title: str,
    *,
    status: str,
    active: bool,
    requires_receipt: bool = True,
) -> dict[str, Any]:
    return {
        "id": commitment_id,
        "title": title,
        "status": status,
        "active": active,
        "requires_receipt": requires_receipt,
    }


def _managed_copy_role(
    role_id: str,
    title: str,
    *,
    status: str,
    allowed_authority: list[str],
    denied_authority: list[str],
    requires_explicit_binding: bool = True,
    authority_active: bool = False,
) -> dict[str, Any]:
    return {
        "id": role_id,
        "title": title,
        "status": status,
        "allowed_authority": allowed_authority,
        "denied_authority": denied_authority,
        "requires_explicit_binding": requires_explicit_binding,
        "authority_active": authority_active,
    }


def _decommission_step(
    step_id: str,
    title: str,
    *,
    status: str,
    writes_receipt: bool,
    mutates_tenant_state: bool,
    requires_operator_approval: bool = True,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "status": status,
        "writes_receipt": writes_receipt,
        "mutates_tenant_state": mutates_tenant_state,
        "requires_operator_approval": requires_operator_approval,
    }


def _completion_check(
    check_id: str,
    title: str,
    *,
    readback_ready: bool,
    runtime_ready: bool,
    route: str,
    blocker: str,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "readback_ready": readback_ready,
        "runtime_ready": runtime_ready,
        "passed": readback_ready and runtime_ready,
        "status": "ready" if readback_ready and runtime_ready else "blocked",
        "route": route,
        "blocker": blocker,
    }


def _managed_copy_preflight_block(stage17_closed: bool) -> tuple[str, str]:
    if stage17_closed:
        return ("blocked_stage18_runtime_not_implemented", "stage18_runtime_not_implemented")
    return ("blocked_stage17_prerequisite", "stage17_prerequisite_not_closed")


def _copy_approval_next_gap(status: str) -> str:
    return {
        "pending": "stage18_copy_creation_approval_decision",
        "approved": "stage18_copy_creation_provision",
        "rejected": "stage18_copy_creation_plan_revision",
        "emergency": "stage18_copy_creation_approval_emergency_review",
    }.get(_safe_str(status).strip(), "stage18_copy_creation_approval_request")


def _copy_approval_state(status: str) -> str:
    return {
        "pending": "approval_pending",
        "approved": "approved",
        "rejected": "approval_rejected",
        "emergency": "approval_emergency",
    }.get(_safe_str(status).strip(), "planned")


def _runtime_evidence_requirement(
    requirement_id: str,
    title: str,
    *,
    source_contract_route: str,
    proof_kind: str,
    blocker: str,
    requires_receipt: bool = True,
    ready: bool = False,
    receipt_id: str = "",
) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "title": title,
        "status": "ready" if ready else "required_not_present",
        "ready": ready,
        "source_contract_route": source_contract_route,
        "proof_kind": proof_kind,
        "blocker": "" if ready else blocker,
        "requires_receipt": requires_receipt,
        "receipt_id": receipt_id if ready else "",
        "recording_enabled": False,
        "writes_receipt": False,
        "mutates_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _runtime_evidence_ready(item: dict[str, Any], requirement: dict[str, Any]) -> bool:
    raw_governance = item.get("governance")
    governance: dict[str, Any] = raw_governance if isinstance(raw_governance, dict) else {}
    return (
        _safe_str(item.get("requirement_id")).strip() == requirement["id"]
        and _safe_str(item.get("proof_kind")).strip() == requirement["proof_kind"]
        and _safe_str(item.get("receipt_id")).strip() != ""
        and _safe_str(item.get("trace_id")).strip() != ""
        and _safe_str(item.get("evidence_summary")).strip() != ""
        and bool(item.get("observed"))
        and _safe_str(item.get("status")).strip() == "observed"
        and bool(governance.get("runtime_evidence_receipt"))
        and bool(governance.get("trace_linked"))
        and bool(governance.get("redacted"))
        and not bool(governance.get("contains_raw_private_data"))
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _latest_runtime_evidence_by_requirement(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in items:
        requirement_id = _safe_str(item.get("requirement_id")).strip()
        if requirement_id:
            latest[requirement_id] = item
    return latest


def managed_copies_status_snapshot() -> dict[str, Any]:
    """Return the Stage 18 managed-copy substrate posture without creating state."""
    governance = _governance()
    stage17 = stage17_operator_stage_closure_decision_readback(limit=5)
    stage17_closed = bool(stage17["stage17_closed_by_receipt"])
    stage17_receipt_id = _safe_str(stage17.get("latest_receipt_id")).strip()
    stage17_blocker = "" if stage17_closed else STAGE17_CLOSURE_DECISION_GAP
    latest_aligned_request = latest_managed_copy_request_receipt_for_stage17(stage17_receipt_id)
    request_stage17_receipt_aligned = bool(stage17_closed and latest_aligned_request)
    copy_request_recorded = request_stage17_receipt_aligned
    copy_request_receipt_id = _safe_str(latest_aligned_request.get("receipt_id")).strip()
    latest_aligned_preflight = latest_managed_copy_preflight_receipt_for_request(
        copy_request_receipt_id,
        request_fingerprint=_safe_str(latest_aligned_request.get("request_fingerprint")).strip(),
        stage17_receipt_id=stage17_receipt_id,
    )
    preflight_request_receipt_aligned = bool(copy_request_recorded and latest_aligned_preflight)
    copy_preflight_recorded = preflight_request_receipt_aligned
    copy_preflight_receipt_id = _safe_str(latest_aligned_preflight.get("receipt_id")).strip()
    latest_aligned_plan = latest_managed_copy_creation_plan_receipt_for_preflight(
        copy_preflight_receipt_id,
        preflight_fingerprint=_safe_str(latest_aligned_preflight.get("preflight_fingerprint")).strip(),
        request_receipt_id=copy_request_receipt_id,
        request_fingerprint=_safe_str(latest_aligned_request.get("request_fingerprint")).strip(),
        stage17_receipt_id=stage17_receipt_id,
    )
    plan_preflight_receipt_aligned = bool(copy_preflight_recorded and latest_aligned_plan)
    copy_plan_recorded = plan_preflight_receipt_aligned
    copy_plan_receipt_id = _safe_str(latest_aligned_plan.get("receipt_id")).strip()
    latest_aligned_approval = latest_managed_copy_creation_approval_for_plan(
        copy_plan_receipt_id,
        plan_fingerprint=_safe_str(latest_aligned_plan.get("plan_fingerprint")).strip(),
    )
    copy_approval_request_recorded = bool(copy_plan_recorded and latest_aligned_approval)
    copy_approval_id = _safe_str(latest_aligned_approval.get("id")).strip()
    copy_approval_status = _safe_str(latest_aligned_approval.get("status")).strip()
    latest_aligned_provision = (
        latest_managed_copy_provision_for_approval(
            copy_approval_id,
            plan_receipt_id=copy_plan_receipt_id,
            plan_fingerprint=_safe_str(latest_aligned_plan.get("plan_fingerprint")).strip(),
            include_recovery=True,
        )
        if copy_approval_status == "approved"
        else {}
    )
    copy_provisioned = bool(latest_aligned_provision.get("provision_complete"))
    copy_provision_recovery_required = bool(latest_aligned_provision.get("recovery_required"))
    copy_provision_receipt_id = _safe_str(latest_aligned_provision.get("receipt_id")).strip()
    provisioned_copy_id = _safe_str(latest_aligned_provision.get("copy_id")).strip()
    latest_aligned_isolation = (
        latest_managed_copy_isolation_verification_for_provision(
            copy_provision_receipt_id,
            provision_fingerprint=_safe_str(latest_aligned_provision.get("provision_fingerprint")).strip(),
            copy_id=provisioned_copy_id,
        )
        if copy_provisioned
        else {}
    )
    copy_structural_isolation_verified = bool(latest_aligned_isolation.get("live_state_aligned"))
    copy_isolation_drift_detected = bool(latest_aligned_isolation.get("live_drift_detected"))
    copy_isolation_receipt_id = _safe_str(latest_aligned_isolation.get("receipt_id")).strip()
    integrity_evidence = managed_copy_integrity_evidence_readback(
        copy_id=provisioned_copy_id,
        provisioning_receipt_id=copy_provision_receipt_id,
        isolation_verification_receipt_id=copy_isolation_receipt_id,
    )
    copy_integrity_evidence_recorded = integrity_evidence.get("status") == "integrity_evidence_recorded"
    copy_integrity_incident_state = _safe_str(integrity_evidence.get("integrity_incident_state")).strip()
    copy_integrity_triage_required = integrity_evidence.get("triage_required") is True
    copy_integrity_evidence_receipt_id = _safe_str(integrity_evidence.get("latest_receipt_id")).strip()
    safe_delta_reviews = managed_copy_safe_delta_review_receipts_readback(
        copy_id=provisioned_copy_id,
        provisioning_receipt_id=copy_provision_receipt_id,
        isolation_verification_receipt_id=copy_isolation_receipt_id,
        limit=20,
    )
    latest_safe_delta_review = safe_delta_reviews.get("latest_valid_receipt")
    latest_safe_delta_review = latest_safe_delta_review if isinstance(latest_safe_delta_review, dict) else {}
    safe_delta_review_recorded = bool(
        copy_structural_isolation_verified
        and safe_delta_reviews.get("receipt_set_valid")
        and latest_safe_delta_review.get("live_source_boundary_aligned")
        and _safe_str(latest_safe_delta_review.get("copy_id")).strip() == provisioned_copy_id
    )
    safe_delta_review_receipt_id = (
        _safe_str(latest_safe_delta_review.get("receipt_id")).strip() if safe_delta_review_recorded else ""
    )
    safe_delta_decisions = (
        managed_copy_safe_delta_decisions_readback(
            copy_id=provisioned_copy_id,
            provisioning_receipt_id=copy_provision_receipt_id,
            isolation_verification_receipt_id=copy_isolation_receipt_id,
            review_fingerprint=_safe_str(latest_safe_delta_review.get("review_fingerprint")).strip(),
            limit=20,
        )
        if safe_delta_review_recorded
        else {}
    )
    safe_delta_approved = bool(safe_delta_decisions.get("safe_delta_approved"))
    safe_delta_rejected = bool(safe_delta_decisions.get("safe_delta_rejected"))
    safe_delta_decision_receipt_id = _safe_str(safe_delta_decisions.get("latest_valid_receipt_id")).strip()
    deliverables = [
        _deliverable(
            "stage17_ledger_closure_backstop",
            "Stage 17 closure backstop",
            ready=stage17_closed,
            status="ready" if stage17_closed else "blocked",
            next_gap=stage17_blocker,
            evidence=[
                f"Stage 17 closure receipt: {stage17_receipt_id}"
                if stage17_closed
                else "Stage 17 requires an explicit governed closure decision over the canonical six-criterion review.",
            ],
        ),
        _deliverable(
            "copy_creation_process",
            "Copy creation process",
            ready=False,
            status=(
                "provision_recovery_required"
                if copy_provision_recovery_required
                else "provisioned_structurally_verified"
                if copy_structural_isolation_verified
                else "provisioned_unverified"
                if copy_provisioned
                else f"approval_{copy_approval_status}"
                if copy_approval_request_recorded
                else "plan_recorded"
                if copy_plan_recorded
                else "preflight_recorded"
                if copy_preflight_recorded
                else "request_recorded"
                if copy_request_recorded
                else "request_recording_ready"
            ),
            next_gap=(
                "stage18_copy_provision_recovery"
                if copy_provision_recovery_required
                else "stage18_copy_isolation_runtime_access_boundary"
                if copy_structural_isolation_verified
                else "stage18_copy_isolation_reverification"
                if copy_isolation_drift_detected
                else "stage18_copy_isolation_verification"
                if copy_provisioned
                else _copy_approval_next_gap(copy_approval_status)
                if copy_approval_request_recorded
                else "stage18_copy_creation_approval_request"
                if copy_plan_recorded
                else "stage18_copy_creation_plan_process"
                if copy_preflight_recorded
                else "stage18_copy_creation_preflight_process"
                if copy_request_recorded
                else "stage18_copy_creation_request_recording"
            ),
            evidence=[
                (
                    f"Managed-copy request receipt: {copy_request_receipt_id}"
                    if copy_request_recorded
                    else "The governed request route is available after Stage 17 closure; no copy request is recorded."
                ),
                (
                    f"Managed-copy preflight receipt: {copy_preflight_receipt_id}"
                    if copy_preflight_recorded
                    else "No request-aligned managed-copy preflight receipt is recorded."
                ),
                (
                    f"Managed-copy creation plan receipt: {copy_plan_receipt_id}"
                    if copy_plan_recorded
                    else "No request/preflight-aligned managed-copy creation plan receipt is recorded."
                ),
                (
                    f"Managed-copy exact-action approval {copy_approval_status}: {copy_approval_id}"
                    if copy_approval_request_recorded
                    else "No plan-aligned managed-copy provisioning approval request is recorded."
                ),
                (
                    f"Managed-copy provisioning receipt requires recovery: {copy_provision_receipt_id}."
                    if copy_provision_recovery_required
                    else f"Managed-copy provisioning receipt: {copy_provision_receipt_id}; runtime remains stopped."
                    if copy_provisioned
                    else "No managed-copy tenant state or runtime has been created."
                ),
                (
                    f"Structural isolation receipt: {copy_isolation_receipt_id}; ACL and runtime boundaries remain open."
                    if copy_structural_isolation_verified
                    else f"Structural isolation receipt drifted from live tenant state: {copy_isolation_receipt_id}."
                    if copy_isolation_drift_detected
                    else "No live-aligned structural isolation receipt is recorded."
                ),
            ],
        ),
        _deliverable(
            "isolation_rules",
            "Isolation rules",
            ready=False,
            status=(
                "structural_verification_recorded"
                if copy_structural_isolation_verified
                else "structural_verification_drifted"
                if copy_isolation_drift_detected
                else "contract_readback_ready"
            ),
            next_gap=(
                "stage18_copy_isolation_runtime_access_boundary"
                if copy_structural_isolation_verified
                else "stage18_copy_isolation_reverification"
                if copy_isolation_drift_detected
                else "stage18_copy_isolation_rules"
            ),
            evidence=[
                (
                    f"Structural tenant isolation is live-aligned to receipt {copy_isolation_receipt_id}; ACL, runtime, and cross-tenant denial proof remain open."
                    if copy_structural_isolation_verified
                    else "GET /managed-copies/isolation-rules-contract exposes tenant boundary rules without claiming full enforcement."
                ),
            ],
        ),
        _deliverable(
            "safe_delta_model",
            "Safe delta model",
            ready=False,
            status=(
                "candidate_approved"
                if safe_delta_approved
                else "candidate_rejected"
                if safe_delta_rejected
                else "candidate_review_recorded"
                if safe_delta_review_recorded
                else "contract_readback_ready"
            ),
            next_gap=(
                "stage18_safe_delta_operator_approval" if safe_delta_review_recorded else "stage18_safe_delta_model"
            ),
            evidence=[
                (
                    f"Hash-only safe-delta review receipt: {safe_delta_review_receipt_id}; operator approval and export remain disabled."
                    if safe_delta_review_recorded
                    else "GET /managed-copies/safe-delta-model-contract exposes allowed signal classes without exporting data."
                ),
            ],
        ),
        _deliverable(
            "rogue_recovery",
            "Rogue kill/replace flows",
            ready=False,
            status=(
                "integrity_triage_required"
                if copy_integrity_triage_required
                else "integrity_evidence_recorded"
                if copy_integrity_evidence_recorded
                else "contract_readback_ready"
            ),
            next_gap=(
                "stage18_integrity_evidence_operator_triage"
                if copy_integrity_triage_required
                else "stage18_rogue_kill_replace_flows"
            ),
            evidence=[
                (
                    f"Live integrity triage requires operator review: {copy_integrity_evidence_receipt_id}."
                    if copy_integrity_triage_required
                    else f"Historical or changed integrity evidence: {copy_integrity_evidence_receipt_id}."
                    if copy_integrity_evidence_recorded
                    else "GET /managed-copies/rogue-recovery-contract exposes detect/halt/quarantine/replace gates without acting."
                ),
            ],
        ),
        _deliverable(
            "sla_framework",
            "SLA framework beginnings",
            ready=False,
            status="contract_readback_ready",
            next_gap="stage18_sla_framework",
            evidence=[
                "GET /managed-copies/sla-framework-contract exposes service commitments without activating them.",
            ],
        ),
        _deliverable(
            "managed_copy_roles",
            "Managed-copy role contract",
            ready=False,
            status="contract_readback_ready",
            next_gap="stage18_managed_copy_roles_contract",
            evidence=[
                "GET /managed-copies/roles-contract exposes managed-copy role boundaries without activating authority.",
            ],
        ),
        _deliverable(
            "exit_rights",
            "Decommission export and deletion contract",
            ready=False,
            status="contract_readback_ready",
            next_gap="stage18_decommission_export_delete_contract",
            evidence=[
                "GET /managed-copies/decommission-contract exposes export/delete/revocation proof gates without acting.",
            ],
        ),
    ]
    ready_count = sum(1 for deliverable in deliverables if deliverable["ready"])

    return {
        "ok": True,
        "kind": MANAGED_COPIES_STATUS_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "stage18_groundwork_open" if stage17_closed else "stage18_prerequisites_blocked",
        "status_readback_ready": True,
        "stage17_closed_by_receipt": stage17_closed,
        "stage17_closure_receipt_id": stage17_receipt_id,
        "stage17_closure_receipt_valid": bool(stage17.get("latest_receipt_valid")),
        "stage17_blocker": stage17_blocker,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "deliverables": deliverables,
        "safe_delta_decision_receipt_id": safe_delta_decision_receipt_id,
        "safe_delta_approved": safe_delta_approved,
        "safe_delta_rejected": safe_delta_rejected,
        "routes": {
            "status": "/managed-copies/status",
            "copy_creation_contract": "/managed-copies/copy-creation-contract",
            "copy_creation_request": "/managed-copies/copy-creation-request",
            "copy_creation_requests": "/managed-copies/copy-creation-requests",
            "copy_creation_preflight": "/managed-copies/copy-creation-preflight",
            "copy_creation_preflights": "/managed-copies/copy-creation-preflights",
            "copy_creation_plan": "/managed-copies/copy-creation-plan",
            "copy_creation_plans": "/managed-copies/copy-creation-plans",
            "copy_creation_approval_request": "/managed-copies/copy-creation-approval-request",
            "copy_creation_approval_requests": "/managed-copies/copy-creation-approval-requests",
            "copy_creation_provision": "/managed-copies/copy-creation-provision",
            "copy_creation_provisions": "/managed-copies/copy-creation-provisions",
            "isolation_rules_contract": "/managed-copies/isolation-rules-contract",
            "isolation_verification": "/managed-copies/isolation-verification",
            "isolation_verifications": "/managed-copies/isolation-verifications",
            "safe_delta_model_contract": "/managed-copies/safe-delta-model-contract",
            "safe_delta_review": "/managed-copies/safe-delta-review",
            "safe_delta_reviews": "/managed-copies/safe-delta-reviews",
            "safe_delta_decision": "/managed-copies/safe-delta-decision",
            "safe_delta_decisions": "/managed-copies/safe-delta-decisions",
            "safe_delta_export_preflight": "/managed-copies/safe-delta-export-preflight",
            "safe_delta_export_authorization_request": "/managed-copies/safe-delta-export-authorization-request",
            "safe_delta_export_authorization_requests": "/managed-copies/safe-delta-export-authorization-requests",
            "safe_delta_export_authorization_decision": "/managed-copies/safe-delta-export-authorization-decision",
            "safe_delta_export_authorization_decisions": "/managed-copies/safe-delta-export-authorization-decisions",
            "safe_delta_export_artifact_plan": "/managed-copies/safe-delta-export-artifact-plan",
            "rogue_recovery_contract": "/managed-copies/rogue-recovery-contract",
            "rogue_recovery_review": "/managed-copies/rogue-recovery-review",
            "rogue_detection_assessment": "/managed-copies/rogue-detection-assessment",
            "rogue_detection_assessments": "/managed-copies/rogue-detection-assessments",
            "integrity_scan": "/managed-copies/integrity-scan",
            "integrity_evidence": "/managed-copies/integrity-evidence",
            "integrity_evidence_readback": "/managed-copies/integrity-evidence-readback",
            "tenant_access_check": "/managed-copies/tenant-access-check",
            "sla_framework_contract": "/managed-copies/sla-framework-contract",
            "sla_commitment_review": "/managed-copies/sla-commitment-review",
            "roles_contract": "/managed-copies/roles-contract",
            "role_authority_review": "/managed-copies/role-authority-review",
            "decommission_contract": "/managed-copies/decommission-contract",
            "decommission_review": "/managed-copies/decommission-review",
            "runtime_evidence_contract": "/managed-copies/runtime-evidence-contract",
            "runtime_evidence_readbacks": "/managed-copies/runtime-evidence-readbacks",
            "runtime_evidence_readback": "/managed-copies/runtime-evidence-readback",
            "completion_review": "/managed-copies/completion-review",
            "stage17_closure_decisions": "/plugins/capabilities/stage17/stage-closure-decisions",
        },
        "managed_copy_roles_required": [
            "end_user",
            "tenant_admin",
            "support_operator",
            "automation_principal",
            "paired_node",
        ],
        "managed_copy_state_classes": [
            "managed_copy_configuration",
            "tenant_policy",
            "copy_identity",
            "capability_delta",
            "decommission_receipt",
        ],
        "failure_modes_blocked_by_contract": [
            "core_surrender",
            "privacy_weak_pooling",
            "uncontrolled_forks",
            "support_chaos",
            "invisible_vendor_power",
        ],
        "governance": governance,
        "copy_request_recording_enabled": stage17_closed,
        "copy_request_recorded": copy_request_recorded,
        "copy_request_receipt_id": copy_request_receipt_id,
        "copy_request_stage17_receipt_aligned": request_stage17_receipt_aligned,
        "copy_preflight_recording_enabled": copy_request_recorded,
        "copy_preflight_recorded": copy_preflight_recorded,
        "copy_preflight_receipt_id": copy_preflight_receipt_id,
        "copy_preflight_request_receipt_aligned": preflight_request_receipt_aligned,
        "copy_plan_recording_enabled": copy_preflight_recorded,
        "copy_plan_recorded": copy_plan_recorded,
        "copy_plan_receipt_id": copy_plan_receipt_id,
        "copy_plan_preflight_receipt_aligned": plan_preflight_receipt_aligned,
        "copy_approval_request_recording_enabled": copy_plan_recorded,
        "copy_approval_request_recorded": copy_approval_request_recorded,
        "copy_approval_id": copy_approval_id,
        "copy_approval_status": copy_approval_status,
        "copy_approval_plan_receipt_aligned": copy_approval_request_recorded,
        "copy_provisioning_enabled": copy_approval_status == "approved" and not copy_provisioned,
        "copy_provisioned": copy_provisioned,
        "copy_provision_recovery_required": copy_provision_recovery_required,
        "copy_provision_receipt_id": copy_provision_receipt_id,
        "provisioned_copy_id": provisioned_copy_id,
        "copy_provision_approval_aligned": bool(latest_aligned_provision),
        "copy_structural_isolation_verified": copy_structural_isolation_verified,
        "copy_isolation_drift_detected": copy_isolation_drift_detected,
        "copy_isolation_receipt_id": copy_isolation_receipt_id,
        "copy_full_customer_isolation_verified": False,
        "copy_integrity_evidence_recorded": copy_integrity_evidence_recorded,
        "copy_integrity_evidence_receipt_id": copy_integrity_evidence_receipt_id,
        "copy_integrity_incident_state": copy_integrity_incident_state,
        "copy_integrity_triage_required": copy_integrity_triage_required,
        "safe_delta_review_recorded": safe_delta_review_recorded,
        "safe_delta_review_receipt_id": safe_delta_review_receipt_id,
        "safe_delta_exported": False,
        "safe_delta_learning_written": False,
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "copy_creation_enabled": governance["copy_creation_enabled"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "next_smallest_truthful_gap": (
            "stage18_copy_provision_recovery"
            if stage17_closed and copy_provision_recovery_required
            else "stage18_copy_isolation_runtime_access_boundary"
            if stage17_closed and copy_structural_isolation_verified
            else "stage18_copy_isolation_reverification"
            if stage17_closed and copy_isolation_drift_detected
            else "stage18_copy_isolation_verification"
            if stage17_closed and copy_provisioned
            else _copy_approval_next_gap(copy_approval_status)
            if stage17_closed and copy_approval_request_recorded
            else "stage18_copy_creation_approval_request"
            if stage17_closed and copy_plan_recorded
            else "stage18_copy_creation_plan_process"
            if stage17_closed and copy_preflight_recorded
            else "stage18_copy_creation_preflight_process"
            if stage17_closed and copy_request_recorded
            else "stage18_copy_creation_request_recording"
            if stage17_closed
            else STAGE17_CLOSURE_DECISION_GAP
        ),
    }


def managed_copy_creation_contract_snapshot() -> dict[str, Any]:
    """Return the governed copy-creation process contract without creating copies."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    latest_request = latest_managed_copy_request_receipt_for_stage17(
        _safe_str(status.get("stage17_closure_receipt_id")).strip()
    )
    request_field_presence = latest_request.get("request_field_presence")
    request_field_presence = request_field_presence if isinstance(request_field_presence, dict) else {}
    copy_request_recorded = bool(status["copy_request_recorded"])
    copy_preflight_recorded = bool(status["copy_preflight_recorded"])
    copy_plan_recorded = bool(status["copy_plan_recorded"])
    copy_approval_request_recorded = bool(status["copy_approval_request_recorded"])
    copy_approval_status = _safe_str(status.get("copy_approval_status")).strip()
    copy_provisioned = bool(status["copy_provisioned"])
    copy_provision_recovery_required = bool(status["copy_provision_recovery_required"])
    copy_structural_isolation_verified = bool(status["copy_structural_isolation_verified"])
    copy_isolation_drift_detected = bool(status["copy_isolation_drift_detected"])

    def request_field_ready(field: str) -> bool:
        return copy_request_recorded and bool(request_field_presence.get(field))

    requirements = [
        _contract_requirement(
            "stage17_closed_by_receipt",
            "Stage 17 closure is backed by a governed canonical-criteria receipt",
            ready=bool(status["stage17_closed_by_receipt"]),
            next_gap=_safe_str(status["stage17_blocker"]),
            evidence=[
                f"Stage 17 closure receipt: {status['stage17_closure_receipt_id']}"
                if status["stage17_closed_by_receipt"]
                else "No valid Stage 17 operator closure receipt is present.",
            ],
        ),
        _contract_requirement(
            "tenant_identity_contract",
            "Tenant identity and administrator authority are declared before planning",
            ready=request_field_ready("tenant_identity"),
            next_gap="stage18_tenant_identity_contract",
        ),
        _contract_requirement(
            "tenant_policy_contract",
            "Tenant policy boundaries are explicit before provisioning",
            ready=request_field_ready("tenant_policy"),
            next_gap="stage18_tenant_policy_contract",
        ),
        _contract_requirement(
            "isolation_profile_contract",
            "Data, memory, receipt, connector, and capability-pack isolation profile is declared",
            ready=request_field_ready("isolation_profile"),
            next_gap="stage18_copy_isolation_rules",
        ),
        _contract_requirement(
            "capability_lineage_contract",
            "Capability pack lineage and allowed customization layers are declared",
            ready=request_field_ready("capability_lineage"),
            next_gap="stage18_capability_lineage_contract",
        ),
        _contract_requirement(
            "safe_delta_policy_contract",
            "Safe delta policy blocks raw private pooling and uncontrolled improvement flow",
            ready=request_field_ready("safe_delta_policy"),
            next_gap="stage18_safe_delta_model",
        ),
        _contract_requirement(
            "rogue_recovery_contract",
            "Rogue halt, quarantine, replacement, and support authority boundaries are declared",
            ready=request_field_ready("support_boundary"),
            next_gap="stage18_rogue_kill_replace_flows",
        ),
        _contract_requirement(
            "decommission_contract",
            "Export, deletion, retention, rotation, and proof receipts are declared",
            ready=request_field_ready("decommission_policy"),
            next_gap="stage18_decommission_export_delete_contract",
        ),
    ]
    process_steps = [
        _contract_step(
            "request",
            "Record an operator-approved managed-copy request",
            status=(
                "complete"
                if copy_request_recorded
                else "enabled"
                if bool(status["stage17_closed_by_receipt"])
                else "blocked"
            ),
            writes_receipt=True,
        ),
        _contract_step(
            "preflight",
            "Check Stage 17 closure, tenant identity, policy, isolation, lineage, and support prerequisites",
            status="complete" if copy_preflight_recorded else "enabled" if copy_request_recorded else "blocked",
            writes_receipt=True,
        ),
        _contract_step(
            "plan",
            "Produce a copy-creation plan without provisioning state",
            status="complete" if copy_plan_recorded else "enabled" if copy_preflight_recorded else "blocked",
            writes_receipt=True,
        ),
        _contract_step(
            "approve",
            "Require explicit tenant-admin or operator approval before any provision step",
            status=(
                copy_approval_status
                if copy_approval_request_recorded
                else "enabled"
                if copy_plan_recorded
                else "contract_only"
            ),
            writes_receipt=False,
        ),
        _contract_step(
            "provision",
            "Create isolated tenant state only after governed approval and receipt setup",
            status=(
                "recovery_required"
                if copy_provision_recovery_required
                else "complete"
                if copy_provisioned
                else "enabled"
                if copy_approval_status == "approved"
                else "disabled"
            ),
            writes_tenant_state=True,
            writes_registry=True,
            writes_receipt=True,
        ),
        _contract_step(
            "verify",
            "Verify isolation, lineage, policy, support boundaries, and decommission readiness",
            status=(
                "structural_complete"
                if copy_structural_isolation_verified
                else "drift_detected"
                if copy_isolation_drift_detected
                else "enabled"
                if copy_provisioned
                else "disabled"
            ),
            writes_receipt=True,
        ),
        _contract_step(
            "handoff",
            "Expose tenant/admin/support handoff only after verification receipts exist",
            status="disabled",
            writes_receipt=True,
        ),
    ]
    return {
        "ok": True,
        "kind": MANAGED_COPIES_COPY_CREATION_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "contract_readback_ready",
        "contract_readback_ready": True,
        "copy_creation_enabled": False,
        "copy_creation_allowed": False,
        "copy_request_recording_enabled": bool(status["stage17_closed_by_receipt"]),
        "copy_request_recorded": copy_request_recorded,
        "copy_request_receipt_id": _safe_str(status.get("copy_request_receipt_id")).strip(),
        "copy_request_stage17_receipt_aligned": bool(status["copy_request_stage17_receipt_aligned"]),
        "copy_preflight_recording_enabled": copy_request_recorded,
        "copy_preflight_recorded": copy_preflight_recorded,
        "copy_preflight_receipt_id": _safe_str(status.get("copy_preflight_receipt_id")).strip(),
        "copy_preflight_request_receipt_aligned": bool(status["copy_preflight_request_receipt_aligned"]),
        "copy_plan_recording_enabled": copy_preflight_recorded,
        "copy_plan_recorded": copy_plan_recorded,
        "copy_plan_receipt_id": _safe_str(status.get("copy_plan_receipt_id")).strip(),
        "copy_plan_preflight_receipt_aligned": bool(status["copy_plan_preflight_receipt_aligned"]),
        "copy_approval_request_recording_enabled": copy_plan_recorded,
        "copy_approval_request_recorded": copy_approval_request_recorded,
        "copy_approval_id": _safe_str(status.get("copy_approval_id")).strip(),
        "copy_approval_status": copy_approval_status,
        "copy_approval_plan_receipt_aligned": bool(status["copy_approval_plan_receipt_aligned"]),
        "copy_provisioning_enabled": bool(status["copy_provisioning_enabled"]),
        "copy_provisioned": copy_provisioned,
        "copy_provision_recovery_required": copy_provision_recovery_required,
        "copy_provision_receipt_id": _safe_str(status.get("copy_provision_receipt_id")).strip(),
        "provisioned_copy_id": _safe_str(status.get("provisioned_copy_id")).strip(),
        "copy_provision_approval_aligned": bool(status["copy_provision_approval_aligned"]),
        "copy_structural_isolation_verified": copy_structural_isolation_verified,
        "copy_isolation_drift_detected": copy_isolation_drift_detected,
        "copy_isolation_receipt_id": _safe_str(status.get("copy_isolation_receipt_id")).strip(),
        "copy_full_customer_isolation_verified": False,
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "stage17_blocker": status["stage17_blocker"],
        "requirements": requirements,
        "required_count": len(requirements),
        "ready_count": sum(1 for requirement in requirements if requirement["ready"]),
        "process_steps": process_steps,
        "state_machine": {
            "current_state": (
                "provision_recovery_required"
                if copy_provision_recovery_required
                else "structurally_verified"
                if copy_structural_isolation_verified
                else "provisioned_unverified"
                if copy_provisioned
                else _copy_approval_state(copy_approval_status)
                if copy_approval_request_recorded
                else "planned"
                if copy_plan_recorded
                else "preflighted"
                if copy_preflight_recorded
                else "requested"
                if copy_request_recorded
                else "request_recording_enabled"
                if bool(status["stage17_closed_by_receipt"])
                else "not_implemented"
            ),
            "states": [
                "request_recording_enabled",
                "requested",
                "preflight_blocked",
                "preflighted",
                "planned",
                "approval_pending",
                "approval_decided",
                "approval_rejected",
                "approval_emergency",
                "approved",
                "provisioning",
                "provision_recovery_required",
                "provisioned_unverified",
                "verifying",
                "structurally_verified",
                "active",
                "quarantined",
                "decommissioned",
            ],
            "active_transitions_enabled": bool(status["stage17_closed_by_receipt"]),
            "enabled_transitions": (
                []
                if copy_structural_isolation_verified
                else ["verify_isolation"]
                if copy_provisioned
                else ["recover_provision"]
                if copy_provision_recovery_required
                else ["provision"]
                if copy_approval_request_recorded and copy_approval_status == "approved"
                else []
                if copy_approval_request_recorded
                else ["request_approval"]
                if copy_plan_recorded
                else ["create_plan"]
                if copy_preflight_recorded
                else ["record_preflight"]
                if copy_request_recorded
                else ["record_request"]
                if bool(status["stage17_closed_by_receipt"])
                else []
            ),
        },
        "required_receipts": [
            "copy_request_receipt",
            "preflight_receipt",
            "copy_creation_plan_receipt",
            "operator_approval_receipt",
            "provisioning_receipt",
            "isolation_verification_receipt",
            "support_handoff_receipt",
        ],
        "copy_creation_request_route": "/managed-copies/copy-creation-request",
        "routes": {
            **status["routes"],
            "copy_creation_contract": "/managed-copies/copy-creation-contract",
            "copy_creation_request": "/managed-copies/copy-creation-request",
            "copy_creation_requests": "/managed-copies/copy-creation-requests",
            "copy_creation_preflight": "/managed-copies/copy-creation-preflight",
            "copy_creation_preflights": "/managed-copies/copy-creation-preflights",
            "copy_creation_plan": "/managed-copies/copy-creation-plan",
            "copy_creation_plans": "/managed-copies/copy-creation-plans",
            "copy_creation_approval_request": "/managed-copies/copy-creation-approval-request",
            "copy_creation_approval_requests": "/managed-copies/copy-creation-approval-requests",
            "copy_creation_provision": "/managed-copies/copy-creation-provision",
            "copy_creation_provisions": "/managed-copies/copy-creation-provisions",
            "isolation_verification": "/managed-copies/isolation-verification",
            "isolation_verifications": "/managed-copies/isolation-verifications",
        },
        "isolation_boundaries": [
            "tenant_data",
            "tenant_memory",
            "tenant_receipts",
            "tenant_connectors",
            "tenant_capability_packs",
            "tenant_policy",
            "support_operator_authority",
        ],
        "blocked_failure_modes": [
            "core_surrender",
            "privacy_weak_pooling",
            "uncontrolled_forks",
            "support_chaos",
            "invisible_vendor_power",
        ],
        "governance": governance,
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "next_smallest_truthful_gap": status["next_smallest_truthful_gap"],
    }


def managed_copy_creation_request_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Plan or record a governed copy request without creating tenant state."""
    governance = _governance()
    contract = managed_copy_creation_contract_snapshot()
    stage17_closed = bool(contract["stage17_closed_by_receipt"])
    status = managed_copies_status_snapshot()
    plan = managed_copy_request_plan(
        payload,
        actor=actor,
        stage17_closed=stage17_closed,
        stage17_receipt_id=_safe_str(status.get("stage17_closure_receipt_id")).strip(),
    )
    dry_run_value = payload.get("dry_run", True)
    dry_run_type_valid = isinstance(dry_run_value, bool)
    dry_run = dry_run_value if dry_run_type_valid else True
    if not stage17_closed:
        outcome: dict[str, Any] = {
            "ok": False,
            "status": "blocked_stage17_prerequisite",
            "error": "stage17_prerequisite_not_closed",
            "receipt": None,
            "receipt_id": "",
            "copy_request_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
            "writes_tenant_state": False,
            "starts_runtime": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }
    elif not dry_run_type_valid:
        outcome = {
            "ok": False,
            "status": "blocked_copy_request_contract",
            "error": "dry_run_must_be_boolean",
            "receipt": None,
            "receipt_id": "",
            "copy_request_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
            "writes_tenant_state": False,
            "starts_runtime": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }
    elif not plan["request_contract_ready"]:
        outcome = {
            "ok": False,
            "status": "blocked_copy_request_contract",
            "error": "copy_request_contract_not_ready",
            "receipt": None,
            "receipt_id": "",
            "copy_request_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
            "writes_tenant_state": False,
            "starts_runtime": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }
    elif dry_run:
        outcome = {
            "ok": True,
            "status": "planned",
            "error": "",
            "receipt": None,
            "receipt_id": "",
            "copy_request_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
            "writes_tenant_state": False,
            "starts_runtime": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }
    else:
        outcome = record_managed_copy_request(
            plan,
            provided_fingerprint=_safe_str(payload.get("dry_run_fingerprint")).strip(),
            confirm_request_recording=payload.get("confirm_request_recording") is True,
        )

    request_recorded = bool(outcome.get("copy_request_recorded"))
    writes_receipt = bool(outcome.get("writes_receipt"))
    next_gap = (
        contract["stage17_blocker"]
        if not stage17_closed
        else "stage18_copy_creation_preflight_process"
        if request_recorded
        else "stage18_copy_creation_request_recording"
    )
    return {
        "ok": bool(outcome["ok"]),
        "kind": MANAGED_COPIES_COPY_CREATION_REQUEST_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": outcome["status"],
        "error": outcome["error"],
        "actor": _safe_str(plan["actor"]).strip(),
        "request_known": bool(plan["request_known"]),
        "request_contract_ready": bool(plan["request_contract_ready"]),
        "request_field_presence": plan["request_field_presence"],
        "request_field_fingerprints": plan["request_field_fingerprints"],
        "tenant_key": plan["tenant_key"],
        "blockers": plan["blockers"],
        "dry_run": dry_run,
        "dry_run_fingerprint": plan["dry_run_fingerprint"],
        "dry_run_confirmation": {
            **plan["dry_run_confirmation"],
            "fingerprint_matched": bool(
                not dry_run
                and plan["dry_run_fingerprint"]
                and _safe_str(payload.get("dry_run_fingerprint")).strip() == plan["dry_run_fingerprint"]
            ),
            "recording_confirmed": payload.get("confirm_request_recording") is True,
        },
        "stage17_closed_by_receipt": stage17_closed,
        "stage17_blocker": contract["stage17_blocker"],
        "copy_creation_enabled": False,
        "copy_creation_allowed": False,
        "copy_request_recording_enabled": stage17_closed,
        "copy_request_recorded": request_recorded,
        "copy_created": False,
        "receipt_ready": bool(outcome.get("receipt_id")),
        "receipt_id": _safe_str(outcome.get("receipt_id")).strip(),
        "receipt": outcome.get("receipt"),
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": writes_receipt,
        "writes_receipts": writes_receipt,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_request_receipt_path": "logs/managed_copies/copy_requests.jsonl",
        "required_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "copy_creation_request": "/managed-copies/copy-creation-request",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": dry_run,
            "permission_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
            "permission_checked": True,
            "copy_creation_enabled": False,
            "copy_request_recording_enabled": stage17_closed,
            "records_copy_request_receipt": writes_receipt,
            "copy_request_receipt_present": request_recorded,
            "does_not_record_copy_request": not writes_receipt,
            "does_not_create_copy": True,
            "does_not_mark_stage_closed": True,
            "does_not_echo_raw_tenant_payload": True,
            "requires_stage17_closure_receipt": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": writes_receipt,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": not writes_receipt,
        "projection_only": not writes_receipt,
        "next_smallest_truthful_gap": next_gap,
    }


def managed_copy_creation_requests_snapshot(*, limit: int = 20) -> dict[str, Any]:
    """Return redacted managed-copy request receipts without mutating state."""
    return managed_copy_request_receipts_readback(limit=limit)


def managed_copy_creation_preflight_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Plan or record a request-aligned copy preflight without provisioning state."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    stage17_closed = bool(status["stage17_closed_by_receipt"])
    request_receipt = latest_managed_copy_request_receipt_for_stage17(
        _safe_str(status.get("stage17_closure_receipt_id")).strip()
    )
    plan = managed_copy_preflight_plan(payload, actor=actor, request_receipt=request_receipt)
    dry_run_value = payload.get("dry_run", True)
    dry_run_type_valid = isinstance(dry_run_value, bool)
    dry_run = dry_run_value if dry_run_type_valid else True
    if not stage17_closed:
        outcome: dict[str, Any] = {
            "ok": False,
            "status": "blocked_stage17_prerequisite",
            "error": "stage17_prerequisite_not_closed",
            "receipt": None,
            "receipt_id": "",
            "copy_preflight_recorded": False,
            "copy_plan_created": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif not request_receipt:
        outcome = {
            "ok": False,
            "status": "blocked_copy_request_required",
            "error": "copy_request_receipt_missing",
            "receipt": None,
            "receipt_id": "",
            "copy_preflight_recorded": False,
            "copy_plan_created": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif not dry_run_type_valid:
        outcome = {
            "ok": False,
            "status": "blocked_copy_preflight_contract",
            "error": "dry_run_must_be_boolean",
            "receipt": None,
            "receipt_id": "",
            "copy_preflight_recorded": False,
            "copy_plan_created": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif not plan["preflight_contract_ready"]:
        outcome = {
            "ok": False,
            "status": "blocked_copy_preflight_contract",
            "error": "copy_preflight_contract_not_ready",
            "receipt": None,
            "receipt_id": "",
            "copy_preflight_recorded": False,
            "copy_plan_created": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif dry_run:
        outcome = {
            "ok": True,
            "status": "preflight_planned",
            "error": "",
            "receipt": None,
            "receipt_id": "",
            "copy_preflight_recorded": False,
            "copy_plan_created": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    else:
        outcome = record_managed_copy_preflight(
            plan,
            provided_fingerprint=_safe_str(payload.get("preflight_fingerprint")).strip(),
            confirm_preflight_recording=payload.get("confirm_preflight_recording") is True,
        )

    preflight_recorded = bool(outcome.get("copy_preflight_recorded"))
    writes_receipt = bool(outcome.get("writes_receipt"))
    next_gap = (
        status["stage17_blocker"]
        if not stage17_closed
        else "stage18_copy_creation_request_recording"
        if not request_receipt
        else "stage18_copy_creation_plan_process"
        if preflight_recorded
        else "stage18_copy_creation_preflight_process"
    )
    return {
        "ok": bool(outcome["ok"]),
        "kind": MANAGED_COPIES_COPY_CREATION_PREFLIGHT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": outcome["status"],
        "error": outcome["error"],
        "actor": _safe_str(plan["actor"]).strip(),
        "tenant_key": plan["tenant_key"],
        "request_receipt_id": plan["request_receipt_id"],
        "request_receipt_aligned": bool(plan["request_receipt_aligned"]),
        "request_payload_fingerprints_matched": bool(plan["request_payload_fingerprints_matched"]),
        "request_field_presence": plan["request_field_presence"],
        "request_field_fingerprints": plan["request_field_fingerprints"],
        "managed_copy_law_ready": bool(plan["managed_copy_law_ready"]),
        "managed_copy_law_checks": plan["managed_copy_law_checks"],
        "managed_copy_law_ready_count": plan["managed_copy_law_ready_count"],
        "managed_copy_law_required_count": plan["managed_copy_law_required_count"],
        "blockers": plan["blockers"],
        "dry_run": dry_run,
        "preflight_contract_ready": bool(plan["preflight_contract_ready"]),
        "preflight_fingerprint": plan["preflight_fingerprint"],
        "dry_run_confirmation": {
            **plan["dry_run_confirmation"],
            "fingerprint_matched": bool(
                not dry_run
                and plan["preflight_fingerprint"]
                and _safe_str(payload.get("preflight_fingerprint")).strip() == plan["preflight_fingerprint"]
            ),
            "recording_confirmed": payload.get("confirm_preflight_recording") is True,
        },
        "stage17_closed_by_receipt": stage17_closed,
        "stage17_blocker": status["stage17_blocker"],
        "copy_request_recorded": bool(request_receipt),
        "copy_preflight_recording_enabled": bool(request_receipt),
        "copy_preflight_recorded": preflight_recorded,
        "copy_plan_created": False,
        "copy_created": False,
        "receipt_ready": bool(outcome.get("receipt_id")),
        "receipt_id": _safe_str(outcome.get("receipt_id")).strip(),
        "receipt": outcome.get("receipt"),
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": writes_receipt,
        "writes_receipts": writes_receipt,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_preflight_receipt_path": "logs/managed_copies/copy_preflights.jsonl",
        "required_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
        "routes": {
            **status["routes"],
            "copy_creation_preflight": "/managed-copies/copy-creation-preflight",
            "copy_creation_preflights": "/managed-copies/copy-creation-preflights",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": dry_run,
            "permission_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
            "permission_checked": True,
            "managed_copy_law_checked": True,
            "managed_copy_law_ready": bool(plan["managed_copy_law_ready"]),
            "copy_creation_enabled": False,
            "copy_preflight_recording_enabled": bool(request_receipt),
            "records_copy_preflight_receipt": writes_receipt,
            "copy_preflight_receipt_present": preflight_recorded,
            "does_not_create_copy_plan": True,
            "does_not_create_copy": True,
            "does_not_mark_stage_closed": True,
            "does_not_echo_raw_tenant_payload": True,
            "requires_stage17_closure_receipt": True,
            "requires_copy_request_receipt": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": writes_receipt,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "starts_runtime": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": not writes_receipt,
        "projection_only": not writes_receipt,
        "next_smallest_truthful_gap": next_gap,
    }


def managed_copy_creation_preflights_snapshot(*, limit: int = 20) -> dict[str, Any]:
    """Return redacted managed-copy preflight receipts without mutating state."""
    return managed_copy_preflight_receipts_readback(limit=limit)


def managed_copy_creation_plan_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Plan or record a receipt-aligned creation plan without provisioning state."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    stage17_closed = bool(status["stage17_closed_by_receipt"])
    request_receipt = latest_managed_copy_request_receipt_for_stage17(
        _safe_str(status.get("stage17_closure_receipt_id")).strip()
    )
    preflight_receipt = latest_managed_copy_preflight_receipt_for_request(
        _safe_str(request_receipt.get("receipt_id")).strip(),
        request_fingerprint=_safe_str(request_receipt.get("request_fingerprint")).strip(),
        stage17_receipt_id=_safe_str(status.get("stage17_closure_receipt_id")).strip(),
    )
    plan = managed_copy_creation_plan_dry_run(
        payload,
        actor=actor,
        request_receipt=request_receipt,
        preflight_receipt=preflight_receipt,
    )
    dry_run_value = payload.get("dry_run", True)
    dry_run_type_valid = isinstance(dry_run_value, bool)
    dry_run = dry_run_value if dry_run_type_valid else True
    if not stage17_closed:
        outcome: dict[str, Any] = {
            "ok": False,
            "status": "blocked_stage17_prerequisite",
            "error": "stage17_prerequisite_not_closed",
            "receipt": None,
            "receipt_id": "",
            "copy_plan_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif not request_receipt:
        outcome = {
            "ok": False,
            "status": "blocked_copy_request_required",
            "error": "copy_request_receipt_missing",
            "receipt": None,
            "receipt_id": "",
            "copy_plan_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif not preflight_receipt:
        outcome = {
            "ok": False,
            "status": "blocked_copy_preflight_required",
            "error": "copy_preflight_receipt_missing",
            "receipt": None,
            "receipt_id": "",
            "copy_plan_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif not dry_run_type_valid:
        outcome = {
            "ok": False,
            "status": "blocked_copy_plan_contract",
            "error": "dry_run_must_be_boolean",
            "receipt": None,
            "receipt_id": "",
            "copy_plan_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif not plan["plan_contract_ready"]:
        outcome = {
            "ok": False,
            "status": "blocked_copy_plan_contract",
            "error": "copy_plan_contract_not_ready",
            "receipt": None,
            "receipt_id": "",
            "copy_plan_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    elif dry_run:
        outcome = {
            "ok": True,
            "status": "copy_plan_ready",
            "error": "",
            "receipt": None,
            "receipt_id": "",
            "copy_plan_recorded": False,
            "copy_created": False,
            "writes_receipt": False,
        }
    else:
        outcome = record_managed_copy_creation_plan(
            plan,
            provided_fingerprint=_safe_str(payload.get("plan_fingerprint")).strip(),
            confirm_plan_recording=payload.get("confirm_plan_recording") is True,
        )

    copy_plan_recorded = bool(outcome.get("copy_plan_recorded"))
    writes_receipt = bool(outcome.get("writes_receipt"))
    next_gap = (
        status["stage17_blocker"]
        if not stage17_closed
        else "stage18_copy_creation_request_recording"
        if not request_receipt
        else "stage18_copy_creation_preflight_process"
        if not preflight_receipt
        else "stage18_copy_creation_approval_request"
        if copy_plan_recorded
        else "stage18_copy_creation_plan_process"
    )
    return {
        "ok": bool(outcome["ok"]),
        "kind": MANAGED_COPIES_COPY_CREATION_PLAN_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": outcome["status"],
        "error": outcome["error"],
        "actor": _safe_str(plan["actor"]).strip(),
        "tenant_key": plan["tenant_key"],
        "request_receipt_id": plan["request_receipt_id"],
        "request_fingerprint": plan["request_fingerprint"],
        "preflight_receipt_id": plan["preflight_receipt_id"],
        "preflight_fingerprint": plan["preflight_fingerprint"],
        "request_and_preflight_receipts_aligned": bool(plan["request_and_preflight_receipts_aligned"]),
        "request_field_fingerprints": plan["request_field_fingerprints"],
        "plan_steps": plan["plan_steps"],
        "blockers": plan["blockers"],
        "dry_run": dry_run,
        "plan_contract_ready": bool(plan["plan_contract_ready"]),
        "plan_fingerprint": plan["plan_fingerprint"],
        "dry_run_confirmation": {
            **plan["dry_run_confirmation"],
            "fingerprint_matched": bool(
                not dry_run
                and plan["plan_fingerprint"]
                and _safe_str(payload.get("plan_fingerprint")).strip() == plan["plan_fingerprint"]
            ),
            "recording_confirmed": payload.get("confirm_plan_recording") is True,
        },
        "stage17_closed_by_receipt": stage17_closed,
        "stage17_blocker": status["stage17_blocker"],
        "copy_request_recorded": bool(request_receipt),
        "copy_preflight_recorded": bool(preflight_receipt),
        "copy_plan_recording_enabled": bool(preflight_receipt),
        "copy_plan_recorded": copy_plan_recorded,
        "operator_approval_recorded": False,
        "copy_created": False,
        "receipt_ready": bool(outcome.get("receipt_id")),
        "receipt_id": _safe_str(outcome.get("receipt_id")).strip(),
        "receipt": outcome.get("receipt"),
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": writes_receipt,
        "writes_receipts": writes_receipt,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_plan_receipt_path": "logs/managed_copies/copy_plans.jsonl",
        "required_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
        "routes": {
            **status["routes"],
            "copy_creation_plan": "/managed-copies/copy-creation-plan",
            "copy_creation_plans": "/managed-copies/copy-creation-plans",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": dry_run,
            "permission_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
            "permission_checked": True,
            "copy_creation_enabled": False,
            "copy_plan_recording_enabled": bool(preflight_receipt),
            "records_copy_creation_plan_receipt": writes_receipt,
            "copy_creation_plan_receipt_present": copy_plan_recorded,
            "operator_approval_required_before_provisioning": True,
            "does_not_provision_copy": True,
            "does_not_write_tenant_state": True,
            "does_not_start_runtime": True,
            "does_not_echo_raw_tenant_payload": True,
            "requires_stage17_closure_receipt": True,
            "requires_copy_request_receipt": True,
            "requires_copy_preflight_receipt": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": writes_receipt,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "starts_runtime": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": not writes_receipt,
        "projection_only": not writes_receipt,
        "next_smallest_truthful_gap": next_gap,
    }


def managed_copy_creation_plans_snapshot(*, limit: int = 20) -> dict[str, Any]:
    """Return redacted managed-copy creation plan receipts without mutating state."""
    return managed_copy_creation_plan_receipts_readback(limit=limit)


def managed_copy_creation_approval_request_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Plan or record an exact-action approval request without provisioning."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    stage17_receipt_id = _safe_str(status.get("stage17_closure_receipt_id")).strip()
    request_receipt = latest_managed_copy_request_receipt_for_stage17(stage17_receipt_id)
    preflight_receipt = latest_managed_copy_preflight_receipt_for_request(
        _safe_str(request_receipt.get("receipt_id")).strip(),
        request_fingerprint=_safe_str(request_receipt.get("request_fingerprint")).strip(),
        stage17_receipt_id=stage17_receipt_id,
    )
    plan_receipt = latest_managed_copy_creation_plan_receipt_for_preflight(
        _safe_str(preflight_receipt.get("receipt_id")).strip(),
        preflight_fingerprint=_safe_str(preflight_receipt.get("preflight_fingerprint")).strip(),
        request_receipt_id=_safe_str(request_receipt.get("receipt_id")).strip(),
        request_fingerprint=_safe_str(request_receipt.get("request_fingerprint")).strip(),
        stage17_receipt_id=stage17_receipt_id,
    )
    plan = managed_copy_creation_approval_request_plan(
        payload,
        actor=actor,
        plan_receipt=plan_receipt,
    )
    dry_run_value = payload.get("dry_run", True)
    dry_run_type_valid = isinstance(dry_run_value, bool)
    dry_run = dry_run_value if dry_run_type_valid else True
    if not bool(status["stage17_closed_by_receipt"]):
        outcome: dict[str, Any] = {
            "ok": False,
            "status": "blocked_stage17_prerequisite",
            "error": "stage17_prerequisite_not_closed",
            "approval": None,
            "approval_id": "",
            "approval_status": "",
            "copy_approval_request_recorded": False,
            "writes_approval_request": False,
            "writes_receipt": False,
        }
    elif not request_receipt:
        outcome = {
            "ok": False,
            "status": "blocked_copy_request_required",
            "error": "copy_request_receipt_missing",
            "approval": None,
            "approval_id": "",
            "approval_status": "",
            "copy_approval_request_recorded": False,
            "writes_approval_request": False,
            "writes_receipt": False,
        }
    elif not preflight_receipt:
        outcome = {
            "ok": False,
            "status": "blocked_copy_preflight_required",
            "error": "copy_preflight_receipt_missing",
            "approval": None,
            "approval_id": "",
            "approval_status": "",
            "copy_approval_request_recorded": False,
            "writes_approval_request": False,
            "writes_receipt": False,
        }
    elif not plan_receipt:
        outcome = {
            "ok": False,
            "status": "blocked_copy_creation_plan_required",
            "error": "copy_creation_plan_receipt_missing",
            "approval": None,
            "approval_id": "",
            "approval_status": "",
            "copy_approval_request_recorded": False,
            "writes_approval_request": False,
            "writes_receipt": False,
        }
    elif not dry_run_type_valid:
        outcome = {
            "ok": False,
            "status": "blocked_copy_approval_request_contract",
            "error": "dry_run_must_be_boolean",
            "approval": None,
            "approval_id": "",
            "approval_status": "",
            "copy_approval_request_recorded": False,
            "writes_approval_request": False,
            "writes_receipt": False,
        }
    elif not plan["approval_request_contract_ready"]:
        outcome = {
            "ok": False,
            "status": "blocked_copy_approval_request_contract",
            "error": "copy_approval_request_contract_not_ready",
            "approval": None,
            "approval_id": "",
            "approval_status": "",
            "copy_approval_request_recorded": False,
            "writes_approval_request": False,
            "writes_receipt": False,
        }
    elif dry_run:
        outcome = {
            "ok": True,
            "status": "approval_request_ready",
            "error": "",
            "approval": None,
            "approval_id": "",
            "approval_status": "",
            "copy_approval_request_recorded": False,
            "writes_approval_request": False,
            "writes_receipt": False,
        }
    else:
        outcome = record_managed_copy_creation_approval_request(
            plan,
            provided_fingerprint=_safe_str(payload.get("approval_action_fingerprint")).strip(),
            confirm_approval_request=payload.get("confirm_approval_request") is True,
        )

    approval_status = _safe_str(outcome.get("approval_status")).strip()
    approval_recorded = bool(outcome.get("copy_approval_request_recorded"))
    writes_approval_request = bool(outcome.get("writes_approval_request"))
    next_gap = (
        status["stage17_blocker"]
        if not bool(status["stage17_closed_by_receipt"])
        else "stage18_copy_creation_request_recording"
        if not request_receipt
        else "stage18_copy_creation_preflight_process"
        if not preflight_receipt
        else "stage18_copy_creation_plan_process"
        if not plan_receipt
        else _copy_approval_next_gap(approval_status)
        if approval_recorded
        else "stage18_copy_creation_approval_request"
    )
    approval_id = _safe_str(outcome.get("approval_id")).strip()
    return {
        "ok": bool(outcome["ok"]),
        "kind": MANAGED_COPIES_COPY_CREATION_APPROVAL_REQUEST_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": outcome["status"],
        "error": outcome["error"],
        "actor": _safe_str(plan["actor"]).strip(),
        "plan_receipt_id": plan["plan_receipt_id"],
        "plan_fingerprint": plan["plan_fingerprint"],
        "plan_receipt_aligned": bool(plan["plan_receipt_aligned"]),
        "exact_action": plan["exact_action"],
        "approval_action_fingerprint": plan["approval_action_fingerprint"],
        "blockers": plan["blockers"],
        "dry_run": dry_run,
        "approval_request_contract_ready": bool(plan["approval_request_contract_ready"]),
        "dry_run_confirmation": {
            **plan["dry_run_confirmation"],
            "fingerprint_matched": bool(
                not dry_run
                and plan["approval_action_fingerprint"]
                and _safe_str(payload.get("approval_action_fingerprint")).strip() == plan["approval_action_fingerprint"]
            ),
            "request_confirmed": payload.get("confirm_approval_request") is True,
        },
        "copy_request_recorded": bool(request_receipt),
        "copy_preflight_recorded": bool(preflight_receipt),
        "copy_plan_recorded": bool(plan_receipt),
        "copy_approval_request_recording_enabled": bool(plan_receipt),
        "copy_approval_request_recorded": approval_recorded,
        "copy_approval_id": approval_id,
        "copy_approval_status": approval_status,
        "operator_approval_recorded": approval_status == "approved",
        "operator_approval_consumed": False,
        "copy_created": False,
        "approval": outcome.get("approval"),
        "writes_approval_request": writes_approval_request,
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "starts_runtime": False,
        "consumes_approval": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_approval_path": (
            f"approvals/{approval_status}/{approval_id}.json" if approval_status and approval_id else ""
        ),
        "required_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
        "routes": {
            **status["routes"],
            "copy_creation_approval_request": "/managed-copies/copy-creation-approval-request",
            "copy_creation_approval_requests": "/managed-copies/copy-creation-approval-requests",
            "approval_decision": "/approvals/decision",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": dry_run,
            "permission_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
            "permission_checked": True,
            "exact_action_hash_bound": bool(plan["approval_action_fingerprint"]),
            "copy_creation_plan_receipt_required": True,
            "operator_decision_required": True,
            "approval_request_only": True,
            "records_pending_approval_request": writes_approval_request,
            "contains_raw_tenant_payload": False,
            "does_not_consume_approval": True,
            "does_not_provision_copy": True,
            "does_not_write_tenant_state": True,
            "does_not_start_runtime": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "starts_runtime": False,
            "consumes_approval": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": not writes_approval_request,
        "projection_only": not writes_approval_request,
        "next_smallest_truthful_gap": next_gap,
    }


def managed_copy_creation_approval_requests_snapshot(*, limit: int = 20) -> dict[str, Any]:
    """Return managed-copy exact-action approval requests without mutating state."""
    return managed_copy_creation_approval_requests_readback(limit=limit)


def managed_copy_creation_provision_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Plan or publish approved isolated tenant state without starting a runtime."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    stage17_receipt_id = _safe_str(status.get("stage17_closure_receipt_id")).strip()
    request_receipt = latest_managed_copy_request_receipt_for_stage17(stage17_receipt_id)
    preflight_receipt = latest_managed_copy_preflight_receipt_for_request(
        _safe_str(request_receipt.get("receipt_id")).strip(),
        request_fingerprint=_safe_str(request_receipt.get("request_fingerprint")).strip(),
        stage17_receipt_id=stage17_receipt_id,
    )
    plan_receipt = latest_managed_copy_creation_plan_receipt_for_preflight(
        _safe_str(preflight_receipt.get("receipt_id")).strip(),
        preflight_fingerprint=_safe_str(preflight_receipt.get("preflight_fingerprint")).strip(),
        request_receipt_id=_safe_str(request_receipt.get("receipt_id")).strip(),
        request_fingerprint=_safe_str(request_receipt.get("request_fingerprint")).strip(),
        stage17_receipt_id=stage17_receipt_id,
    )
    approval_record = latest_managed_copy_creation_approval_for_plan(
        _safe_str(plan_receipt.get("receipt_id")).strip(),
        plan_fingerprint=_safe_str(plan_receipt.get("plan_fingerprint")).strip(),
    )
    plan = managed_copy_provision_plan(
        payload,
        actor=actor,
        plan_receipt=plan_receipt,
        approval_record=approval_record,
    )
    dry_run_value = payload.get("dry_run", True)
    dry_run_type_valid = isinstance(dry_run_value, bool)
    dry_run = dry_run_value if dry_run_type_valid else True
    approval_status = _safe_str(approval_record.get("status")).strip()
    outcome: dict[str, Any] = {
        "ok": False,
        "status": "blocked_copy_provision_contract",
        "error": "copy_provision_contract_not_ready",
        "receipt": None,
        "receipt_id": "",
        "copy_id": "",
        "copy_provisioned": False,
        "approval_consumed": False,
        "single_use_enforced": False,
        "writes_tenant_state": False,
        "writes_registry": False,
        "writes_receipt": False,
        "consumes_approval": False,
    }
    if not bool(status["stage17_closed_by_receipt"]):
        outcome.update(status="blocked_stage17_prerequisite", error="stage17_prerequisite_not_closed")
    elif not plan_receipt:
        outcome.update(
            status="blocked_copy_creation_plan_required",
            error="copy_creation_plan_receipt_missing",
        )
    elif not approval_record:
        outcome.update(
            status="blocked_copy_creation_approval_required",
            error="copy_creation_approval_missing",
        )
    elif approval_status != "approved":
        outcome.update(
            status="blocked_copy_creation_approval_not_approved",
            error="copy_creation_approval_not_approved",
        )
    elif not dry_run_type_valid:
        outcome.update(status="blocked_copy_provision_contract", error="dry_run_must_be_boolean")
    elif not plan["provision_contract_ready"]:
        outcome.update(status="blocked_copy_provision_contract", error="copy_provision_contract_not_ready")
    elif dry_run:
        outcome.update(ok=True, status="provision_ready", error="")
    else:
        outcome = record_managed_copy_provision(
            plan,
            provided_fingerprint=_safe_str(payload.get("provision_fingerprint")).strip(),
            confirm_provisioning=payload.get("confirm_provisioning") is True,
        )

    copy_provisioned = bool(outcome.get("copy_provisioned"))
    writes_tenant_state = bool(outcome.get("writes_tenant_state"))
    writes_registry = bool(outcome.get("writes_registry"))
    writes_receipt = bool(outcome.get("writes_receipt"))
    consumes_approval = bool(outcome.get("consumes_approval"))
    provision_recovery_required = bool(status["copy_provision_recovery_required"]) and not copy_provisioned
    next_gap = (
        "stage18_copy_isolation_verification"
        if copy_provisioned
        else "stage18_copy_provision_recovery"
        if provision_recovery_required
        else status["stage17_blocker"]
        if not bool(status["stage17_closed_by_receipt"])
        else _copy_approval_next_gap(approval_status)
        if approval_status != "approved"
        else "stage18_copy_creation_provision"
    )
    return {
        "ok": bool(outcome["ok"]),
        "kind": MANAGED_COPIES_COPY_CREATION_PROVISION_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": outcome["status"],
        "error": outcome["error"],
        "actor": _safe_str(plan["actor"]).strip(),
        "tenant_key": plan["tenant_key"],
        "copy_id": _safe_str(outcome.get("copy_id") or plan.get("copy_id")).strip(),
        "plan_receipt_id": plan["plan_receipt_id"],
        "plan_fingerprint": plan["plan_fingerprint"],
        "approval_id": plan["approval_id"],
        "approval_status": approval_status,
        "approval_action_fingerprint": plan["approval_action_fingerprint"],
        "approval_exact_action_aligned": bool(plan["approval_exact_action_aligned"]),
        "request_field_presence": plan["request_field_presence"],
        "request_field_fingerprints": plan["request_field_fingerprints"],
        "isolation_paths": plan["isolation_paths"],
        "state_root": plan["state_root"],
        "blockers": plan["blockers"],
        "dry_run": dry_run,
        "provision_contract_ready": bool(plan["provision_contract_ready"]),
        "provision_fingerprint": plan["provision_fingerprint"],
        "dry_run_confirmation": {
            **plan["dry_run_confirmation"],
            "fingerprint_matched": bool(
                not dry_run
                and plan["provision_fingerprint"]
                and _safe_str(payload.get("provision_fingerprint")).strip() == plan["provision_fingerprint"]
            ),
            "provisioning_confirmed": payload.get("confirm_provisioning") is True,
        },
        "copy_provisioning_enabled": approval_status == "approved" and not copy_provisioned,
        "copy_provisioned": copy_provisioned,
        "copy_provision_recovery_required": provision_recovery_required,
        "copy_created": copy_provisioned,
        "operator_approval_recorded": approval_status == "approved",
        "operator_approval_consumed": bool(outcome.get("approval_consumed")),
        "single_use_enforced": bool(outcome.get("single_use_enforced")),
        "receipt_ready": bool(outcome.get("receipt_id")),
        "receipt_id": _safe_str(outcome.get("receipt_id")).strip(),
        "receipt": outcome.get("receipt"),
        "writes_registry": writes_registry,
        "writes_memory": False,
        "writes_receipt": writes_receipt,
        "writes_receipts": writes_receipt,
        "writes_tenant_state": writes_tenant_state,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "starts_runtime": False,
        "consumes_approval": consumes_approval,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "required_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
        "routes": {
            **status["routes"],
            "copy_creation_provision": "/managed-copies/copy-creation-provision",
            "copy_creation_provisions": "/managed-copies/copy-creation-provisions",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": dry_run,
            "permission_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
            "permission_checked": True,
            "approved_exact_action_required": True,
            "approval_action_fingerprint_matched": bool(plan["approval_exact_action_aligned"]),
            "request_payload_fingerprints_matched": not plan["blockers"],
            "raw_tenant_payload_tenant_local_only": True,
            "starts_runtime": False,
            "writes_registry": writes_registry,
            "writes_memory": False,
            "writes_receipts": writes_receipt,
            "writes_tenant_state": writes_tenant_state,
            "consumes_approval": consumes_approval,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": not (writes_tenant_state or writes_registry or writes_receipt),
        "projection_only": not (writes_tenant_state or writes_registry or writes_receipt),
        "next_smallest_truthful_gap": next_gap,
    }


def managed_copy_creation_provisions_snapshot(*, limit: int = 20) -> dict[str, Any]:
    """Return redacted managed-copy provisioning receipts without mutating state."""
    return managed_copy_provision_receipts_readback(limit=limit)


def managed_copy_isolation_rules_contract_snapshot() -> dict[str, Any]:
    """Return the managed-copy isolation rules contract without enforcing tenant state."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    isolation_domains = [
        _isolation_domain(
            "tenant_data",
            "Tenant data remains copy-local and cannot be pooled across customers",
            isolated=False,
            enforcement_status="contract_only",
            verification_gap="stage18_tenant_data_isolation_verification",
        ),
        _isolation_domain(
            "tenant_memory",
            "Tenant memory and continuity traces remain copy-local",
            isolated=False,
            enforcement_status="contract_only",
            verification_gap="stage18_tenant_memory_isolation_verification",
        ),
        _isolation_domain(
            "tenant_receipts",
            "Tenant receipts are scoped to the managed copy and support audit boundary",
            isolated=False,
            enforcement_status="contract_only",
            verification_gap="stage18_tenant_receipt_isolation_verification",
        ),
        _isolation_domain(
            "tenant_connectors",
            "Tenant connectors and credentials stay inside declared tenant authority",
            isolated=False,
            enforcement_status="contract_only",
            verification_gap="stage18_tenant_connector_isolation_verification",
        ),
        _isolation_domain(
            "tenant_capability_packs",
            "Tenant capability-pack customizations preserve lineage to core packs",
            isolated=False,
            enforcement_status="contract_only",
            verification_gap="stage18_tenant_capability_pack_lineage_verification",
        ),
        _isolation_domain(
            "tenant_policy",
            "Tenant policy overlays are explicit and do not weaken core governance law",
            isolated=False,
            enforcement_status="contract_only",
            verification_gap="stage18_tenant_policy_overlay_verification",
        ),
        _isolation_domain(
            "support_operator_authority",
            "Support operator authority is explicit, time-bounded, audited, and revocable",
            isolated=False,
            enforcement_status="contract_only",
            verification_gap="stage18_support_operator_authority_verification",
        ),
    ]
    structural_verified = bool(status["copy_structural_isolation_verified"])
    structural_drift = bool(status["copy_isolation_drift_detected"])
    for domain in isolation_domains:
        domain["structurally_verified"] = structural_verified
        domain["structural_verification_status"] = (
            "verified" if structural_verified else "drift_detected" if structural_drift else "not_verified"
        )
        if structural_verified:
            domain["verification_gap"] = "stage18_copy_isolation_runtime_access_boundary"
        elif structural_drift:
            domain["verification_gap"] = "stage18_copy_isolation_reverification"
    return {
        "ok": True,
        "kind": MANAGED_COPIES_ISOLATION_RULES_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "contract_readback_ready",
        "contract_readback_ready": True,
        "isolation_rules_ready": False,
        "isolation_enforcement_enabled": False,
        "structural_isolation_verified": structural_verified,
        "structural_isolation_drift_detected": structural_drift,
        "structural_isolation_receipt_id": status["copy_isolation_receipt_id"],
        "filesystem_acl_isolation_verified": False,
        "runtime_access_boundary_verified": False,
        "full_customer_isolation_verified": False,
        "copy_creation_enabled": False,
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "stage17_blocker": status["stage17_blocker"],
        "isolation_domains": isolation_domains,
        "required_domain_count": len(isolation_domains),
        "enforced_domain_count": sum(1 for domain in isolation_domains if domain["isolated"]),
        "structurally_verified_domain_count": sum(1 for domain in isolation_domains if domain["structurally_verified"]),
        "support_access_rules": [
            "support_operator_identity_required",
            "tenant_admin_approval_required",
            "scope_limited_support_session_required",
            "time_bound_support_access_required",
            "support_action_receipts_required",
            "tenant_visible_support_activity_required",
            "support_revocation_required",
        ],
        "cross_tenant_rules": [
            "no_raw_private_data_pooling",
            "no_cross_tenant_memory_reads",
            "no_cross_tenant_receipt_writes",
            "no_cross_tenant_connector_reuse",
            "no_unattributed_safe_delta_flow",
            "no_uncontrolled_capability_pack_forks",
        ],
        "verification_receipts_required": [
            "tenant_data_isolation_receipt",
            "tenant_memory_isolation_receipt",
            "tenant_receipt_isolation_receipt",
            "tenant_connector_isolation_receipt",
            "tenant_policy_overlay_receipt",
            "support_authority_boundary_receipt",
            "cross_tenant_flow_denial_receipt",
        ],
        "isolation_verification_route": "/managed-copies/isolation-verification",
        "routes": {
            **status["routes"],
            "isolation_rules_contract": "/managed-copies/isolation-rules-contract",
            "isolation_verification": "/managed-copies/isolation-verification",
            "isolation_verifications": "/managed-copies/isolation-verifications",
        },
        "blocked_failure_modes": [
            "privacy_weak_pooling",
            "cross_customer_leakage",
            "support_backdoor",
            "ambiguous_operator_rights",
            "uncontrolled_forks",
            "policy_thin_managed_service",
        ],
        "governance": governance,
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "cross_tenant_data_flow_allowed": False,
        "raw_private_pooling_allowed": False,
        "support_backdoor_allowed": False,
        "tenant_state_shared": False,
        "next_smallest_truthful_gap": status["next_smallest_truthful_gap"],
    }


def _managed_copy_isolation_verification_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed isolation verification preflight without enforcing isolation."""
    governance = _governance()
    contract = managed_copy_isolation_rules_contract_snapshot()
    blocked_status, blocked_error = _managed_copy_preflight_block(bool(contract["stage17_closed_by_receipt"]))
    raw_domains = payload.get("domains")
    domain_values = raw_domains if isinstance(raw_domains, list) else []
    requested_domains = {_safe_str(domain).strip() for domain in domain_values if _safe_str(domain).strip()}
    required_domains = [item["id"] for item in contract["isolation_domains"]]
    domain_checks = [
        {
            "id": domain_id,
            "requested": domain_id in requested_domains,
            "verified": False,
            "status": blocked_status,
            "verification_gap": next(
                item["verification_gap"] for item in contract["isolation_domains"] if item["id"] == domain_id
            ),
        }
        for domain_id in required_domains
    ]
    requested_unknown_domains = sorted(requested_domains.difference(required_domains))
    return {
        "ok": False,
        "kind": MANAGED_COPIES_ISOLATION_VERIFICATION_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": blocked_status,
        "error": blocked_error,
        "actor": _safe_str(actor).strip(),
        "copy_id_present": bool(_safe_str(payload.get("copy_id")).strip()),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "requested_domain_count": len(requested_domains),
        "requested_unknown_domains": requested_unknown_domains,
        "required_domain_count": len(required_domains),
        "verified_domain_count": 0,
        "domain_checks": domain_checks,
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": contract["stage17_blocker"],
        "isolation_rules_ready": False,
        "isolation_enforcement_enabled": False,
        "isolation_verification_enabled": False,
        "isolation_verified": False,
        "tenant_state_shared": False,
        "cross_tenant_data_flow_allowed": False,
        "raw_private_pooling_allowed": False,
        "support_backdoor_allowed": False,
        "receipt_ready": False,
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_verification_receipt_path": "logs/managed_copies/isolation_verifications.jsonl",
        "required_scope": MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "isolation_verification": "/managed-copies/isolation-verification",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": True,
            "permission_scope": MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE,
            "permission_checked": True,
            "isolation_enforcement_enabled": False,
            "isolation_verification_enabled": False,
            "does_not_enforce_isolation": True,
            "does_not_record_isolation_receipt": True,
            "does_not_mutate_tenant_state": True,
            "does_not_echo_raw_tenant_payload": True,
            "requires_stage17_closure_receipt": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "next_smallest_truthful_gap": contract["next_smallest_truthful_gap"],
    }


def managed_copy_isolation_verification_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Verify provisioned tenant structure and optionally record bounded evidence."""
    status = managed_copies_status_snapshot()
    if not bool(status["stage17_closed_by_receipt"]):
        return _managed_copy_isolation_verification_blocked_snapshot(payload, actor=actor)

    governance = _governance()
    copy_id = _safe_str(payload.get("copy_id")).strip()
    provisioning_receipt_id = _safe_str(payload.get("provisioning_receipt_id")).strip()
    provision_receipt = managed_copy_provision_for_copy(
        copy_id,
        provisioning_receipt_id=provisioning_receipt_id,
    )
    plan = managed_copy_isolation_verification_plan(
        payload,
        actor=actor,
        provision_receipt=provision_receipt,
    )
    dry_run_value = payload.get("dry_run", True)
    dry_run_type_valid = isinstance(dry_run_value, bool)
    dry_run = dry_run_value if dry_run_type_valid else True
    outcome: dict[str, Any] = {
        "ok": False,
        "status": "blocked_isolation_verification_contract",
        "error": "isolation_verification_contract_not_ready",
        "receipt": None,
        "receipt_id": "",
        "structural_isolation_verified": False,
        "full_customer_isolation_verified": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }
    if not provision_receipt:
        outcome.update(
            status="blocked_copy_provision_required",
            error="copy_provision_receipt_missing_or_mismatch",
        )
    elif not dry_run_type_valid:
        outcome.update(error="dry_run_must_be_boolean")
    elif not plan["structural_isolation_ready"]:
        outcome.update(error="isolation_verification_contract_not_ready")
    elif dry_run:
        outcome.update(ok=True, status="structural_isolation_verification_ready", error="")
    else:
        outcome = record_managed_copy_isolation_verification(
            plan,
            provision_receipt=provision_receipt,
            provided_fingerprint=_safe_str(payload.get("verification_fingerprint")).strip(),
            confirm_verification=payload.get("confirm_isolation_verification") is True,
        )

    structural_verified = bool(outcome.get("structural_isolation_verified"))
    writes_receipt = bool(outcome.get("writes_receipt"))
    next_gap = (
        "stage18_copy_isolation_runtime_access_boundary"
        if structural_verified
        else "stage18_copy_isolation_verification"
        if provision_receipt
        else status["next_smallest_truthful_gap"]
    )
    return {
        "ok": bool(outcome["ok"]),
        "kind": MANAGED_COPIES_ISOLATION_VERIFICATION_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": outcome["status"],
        "error": outcome["error"],
        "actor": plan["actor"],
        "copy_id": plan["copy_id"],
        "copy_id_present": bool(copy_id),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "tenant_key": plan["tenant_key"],
        "provisioning_receipt_id": plan["provisioning_receipt_id"],
        "provision_fingerprint": plan["provision_fingerprint"],
        "state_root": plan["state_root"],
        "requested_domains": plan["requested_domains"],
        "requested_domain_count": len(plan["requested_domains"]),
        "requested_unknown_domains": plan["unknown_domains"],
        "required_domain_count": plan["required_domain_count"],
        "verified_domain_count": plan["verified_domain_count"],
        "domain_checks": plan["domain_checks"],
        "required_artifact_count": plan["required_artifact_count"],
        "verified_artifact_count": plan["verified_artifact_count"],
        "artifact_checks": plan["artifact_checks"],
        "stage17_closed_by_receipt": True,
        "stage17_blocker": "",
        "copy_provisioned": bool(provision_receipt),
        "isolation_rules_ready": False,
        "isolation_enforcement_enabled": False,
        "isolation_verification_enabled": bool(provision_receipt),
        "structural_isolation_ready": bool(plan["structural_isolation_ready"]),
        "structural_isolation_verified": structural_verified,
        "isolation_verified": False,
        "filesystem_acl_isolation_verified": False,
        "runtime_access_boundary_verified": False,
        "cross_tenant_denial_executed": False,
        "full_customer_isolation_verified": False,
        "tenant_state_shared": False,
        "cross_tenant_data_flow_allowed": False,
        "raw_private_pooling_allowed": False,
        "support_backdoor_allowed": False,
        "blockers": plan["blockers"],
        "dry_run": dry_run,
        "verification_fingerprint": plan["verification_fingerprint"],
        "dry_run_confirmation": {
            **plan["dry_run_confirmation"],
            "fingerprint_matched": bool(
                not dry_run
                and plan["verification_fingerprint"]
                and _safe_str(payload.get("verification_fingerprint")).strip() == plan["verification_fingerprint"]
            ),
            "verification_confirmed": payload.get("confirm_isolation_verification") is True,
        },
        "receipt_ready": bool(outcome.get("receipt_id")),
        "receipt_id": _safe_str(outcome.get("receipt_id")).strip(),
        "receipt": outcome.get("receipt"),
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": writes_receipt,
        "writes_receipts": writes_receipt,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "starts_runtime": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_verification_receipt_path": (
            "managed_copies/tenants/{tenant_key}/receipts/isolation_verification.json"
        ),
        "required_scope": MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE,
        "routes": {
            **status["routes"],
            "isolation_verification": "/managed-copies/isolation-verification",
            "isolation_verifications": "/managed-copies/isolation-verifications",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": dry_run,
            "permission_scope": MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE,
            "permission_checked": True,
            "copy_provision_receipt_required": True,
            "copy_provision_receipt_aligned": bool(provision_receipt),
            "structural_verification_only": True,
            "filesystem_acl_isolation_claimed": False,
            "runtime_access_boundary_claimed": False,
            "cross_tenant_denial_claimed": False,
            "does_not_echo_raw_tenant_payload": True,
            "starts_runtime": False,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": writes_receipt,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": not writes_receipt,
        "projection_only": not writes_receipt,
        "next_smallest_truthful_gap": next_gap,
    }


def managed_copy_isolation_verifications_snapshot(*, limit: int = 20) -> dict[str, Any]:
    """Return tenant-local structural-isolation receipts with live drift checks."""
    return managed_copy_isolation_verification_receipts_readback(limit=limit)


def managed_copy_safe_delta_model_contract_snapshot() -> dict[str, Any]:
    """Return the safe-delta model contract without exporting tenant data."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    reviews = managed_copy_safe_delta_review_receipts_readback(
        copy_id=_safe_str(status["provisioned_copy_id"]).strip(),
        provisioning_receipt_id=_safe_str(status["copy_provision_receipt_id"]).strip(),
        isolation_verification_receipt_id=_safe_str(status["copy_isolation_receipt_id"]).strip(),
        limit=20,
    )
    review_recorded = bool(status["safe_delta_review_recorded"])
    allowed_signal_classes = [
        _safe_delta_signal_class(
            "capability_metadata",
            "Capability metadata that preserves pack lineage without customer artifacts",
            allowed=True,
            status="contract_only",
        ),
        _safe_delta_signal_class(
            "policy_hardening_delta",
            "Policy hardening deltas that improve defaults without tenant secrets",
            allowed=True,
            status="contract_only",
        ),
        _safe_delta_signal_class(
            "quality_gate_learning",
            "Quality gate learnings expressed as non-sensitive rule improvements",
            allowed=True,
            status="contract_only",
        ),
        _safe_delta_signal_class(
            "regression_case_summary",
            "Regression case summaries with tenant details removed",
            allowed=True,
            status="contract_only",
        ),
        _safe_delta_signal_class(
            "performance_signal",
            "Performance and reliability signals without private payloads",
            allowed=True,
            status="contract_only",
        ),
        _safe_delta_signal_class(
            "class_level_friction_pattern",
            "Class-level friction patterns that do not identify a tenant or artifact",
            allowed=True,
            status="contract_only",
        ),
        _safe_delta_signal_class(
            "non_sensitive_outcome_metric",
            "Non-sensitive outcome metrics that cannot reconstruct tenant work",
            allowed=True,
            status="contract_only",
        ),
    ]
    denied_signal_classes = [
        _safe_delta_signal_class(
            "raw_customer_artifact",
            "Raw customer files, transcripts, messages, or artifacts",
            allowed=False,
            status="denied",
        ),
        _safe_delta_signal_class(
            "tenant_memory_trace",
            "Tenant memory and continuity traces",
            allowed=False,
            status="denied",
        ),
        _safe_delta_signal_class(
            "tenant_receipt_payload",
            "Tenant receipt payloads outside an explicit support/audit scope",
            allowed=False,
            status="denied",
        ),
        _safe_delta_signal_class(
            "credential_or_connector_secret",
            "Credentials, connector secrets, or raw integration payloads",
            allowed=False,
            status="denied",
        ),
        _safe_delta_signal_class(
            "support_session_private_context",
            "Support session private context and operator notes",
            allowed=False,
            status="denied",
        ),
        _safe_delta_signal_class(
            "tenant_identifying_metadata",
            "Tenant-identifying metadata that can re-link an abstracted signal",
            allowed=False,
            status="denied",
        ),
    ]
    return {
        "ok": True,
        "kind": MANAGED_COPIES_SAFE_DELTA_MODEL_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "candidate_review_recorded" if review_recorded else "contract_readback_ready",
        "contract_readback_ready": True,
        "safe_delta_model_ready": False,
        "safe_delta_review_enabled": bool(status["copy_structural_isolation_verified"]),
        "safe_delta_review_recorded": review_recorded,
        "safe_delta_review_receipt_id": status["safe_delta_review_receipt_id"],
        "safe_delta_review_receipt_count": reviews["valid_count"],
        "delta_export_enabled": False,
        "delta_import_enabled": False,
        "learning_write_enabled": False,
        "copy_creation_enabled": False,
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "stage17_blocker": status["stage17_blocker"],
        "allowed_signal_classes": allowed_signal_classes,
        "denied_signal_classes": denied_signal_classes,
        "allowed_signal_count": len(allowed_signal_classes),
        "denied_signal_count": len(denied_signal_classes),
        "approval_gates_required": [
            "tenant_policy_allows_safe_delta_export",
            "tenant_admin_or_operator_approval",
            "redaction_and_abstraction_review",
            "lineage_attribution_review",
            "risk_tier_review",
            "revocation_and_retention_review",
        ],
        "required_receipts": [
            "safe_delta_preflight_receipt",
            "redaction_review_receipt",
            "tenant_policy_allowance_receipt",
            "operator_approval_receipt",
            "delta_lineage_receipt",
            "safe_delta_export_receipt",
            "core_learning_ingest_receipt",
        ],
        "flow_states": [
            "candidate_detected",
            "redaction_pending",
            "operator_review_required",
            "tenant_policy_blocked",
            "approved_for_delta",
            "export_disabled",
            "ingest_disabled",
            "revoked",
        ],
        "safe_delta_review_route": "/managed-copies/safe-delta-review",
        "routes": {
            **status["routes"],
            "safe_delta_model_contract": "/managed-copies/safe-delta-model-contract",
            "safe_delta_review": "/managed-copies/safe-delta-review",
            "safe_delta_reviews": "/managed-copies/safe-delta-reviews",
        },
        "blocked_failure_modes": [
            "raw_private_data_pooling",
            "tenant_reidentification",
            "cross_customer_contamination",
            "unattributed_core_learning",
            "policy_bypass_learning",
            "support_confusion",
        ],
        "governance": governance,
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "raw_private_pooling_allowed": False,
        "cross_tenant_data_flow_allowed": False,
        "tenant_reidentification_allowed": False,
        "unattributed_learning_allowed": False,
        "safe_delta_flow_active": False,
        "next_smallest_truthful_gap": (
            "stage18_safe_delta_operator_approval"
            if review_recorded
            else "stage18_safe_delta_candidate_review"
            if status["copy_structural_isolation_verified"]
            else status["next_smallest_truthful_gap"]
        ),
    }


def _managed_copy_safe_delta_review_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed safe-delta review preflight without exporting data."""
    governance = _governance()
    contract = managed_copy_safe_delta_model_contract_snapshot()
    blocked_status, blocked_error = _managed_copy_preflight_block(bool(contract["stage17_closed_by_receipt"]))
    raw_signal_class = _safe_str(payload.get("signal_class")).strip()
    allowed_signal_ids = {item["id"] for item in contract["allowed_signal_classes"]}
    denied_signal_ids = {item["id"] for item in contract["denied_signal_classes"]}
    signal_class = raw_signal_class if raw_signal_class in allowed_signal_ids | denied_signal_ids else "unknown"
    raw_direction = _safe_str(payload.get("direction")).strip()
    direction = raw_direction if raw_direction in {"export", "import", "ingest"} else "unknown"
    return {
        "ok": False,
        "kind": MANAGED_COPIES_SAFE_DELTA_REVIEW_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": blocked_status,
        "error": blocked_error,
        "actor": _safe_str(actor).strip(),
        "copy_id_present": bool(_safe_str(payload.get("copy_id")).strip()),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "candidate_present": payload.get("candidate") is not None,
        "signal_class": signal_class,
        "signal_class_known": signal_class in allowed_signal_ids or signal_class in denied_signal_ids,
        "signal_allowed_by_contract": signal_class in allowed_signal_ids,
        "signal_denied_by_contract": signal_class in denied_signal_ids,
        "direction": direction,
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": contract["stage17_blocker"],
        "safe_delta_model_ready": False,
        "safe_delta_review_enabled": False,
        "safe_delta_approved": False,
        "safe_delta_flow_active": False,
        "delta_export_enabled": False,
        "delta_import_enabled": False,
        "learning_write_enabled": False,
        "raw_private_pooling_allowed": False,
        "cross_tenant_data_flow_allowed": False,
        "tenant_reidentification_allowed": False,
        "unattributed_learning_allowed": False,
        "receipt_ready": False,
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_review_receipt_path": (
            "managed_copies/tenants/{tenant_key}/receipts/sd/{review_fingerprint_prefix}.json"
        ),
        "required_scope": MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "safe_delta_review": "/managed-copies/safe-delta-review",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": True,
            "permission_scope": MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE,
            "permission_checked": True,
            "safe_delta_review_enabled": False,
            "safe_delta_flow_active": False,
            "does_not_export_delta": True,
            "does_not_import_delta": True,
            "does_not_write_learning": True,
            "does_not_record_safe_delta_receipt": True,
            "does_not_echo_raw_signal_payload": True,
            "requires_stage17_closure_receipt": True,
            "raw_private_pooling_allowed": False,
            "cross_tenant_data_flow_allowed": False,
            "tenant_reidentification_allowed": False,
            "unattributed_learning_allowed": False,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "next_smallest_truthful_gap": contract["next_smallest_truthful_gap"],
    }


def managed_copy_safe_delta_review_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Review a hash-only safe-delta candidate without exporting or learning."""
    status = managed_copies_status_snapshot()
    if not bool(status["stage17_closed_by_receipt"]):
        return _managed_copy_safe_delta_review_blocked_snapshot(payload, actor=actor)

    governance = _governance()
    copy_id = _safe_str(payload.get("copy_id")).strip()
    provisioning_receipt_id = _safe_str(payload.get("provisioning_receipt_id")).strip()
    isolation_receipt_id = _safe_str(payload.get("isolation_verification_receipt_id")).strip()
    provision_receipt = managed_copy_provision_for_copy(
        copy_id,
        provisioning_receipt_id=provisioning_receipt_id,
    )
    isolation_receipt = (
        latest_managed_copy_isolation_verification_for_provision(
            provisioning_receipt_id,
            provision_fingerprint=_safe_str(provision_receipt.get("provision_fingerprint")).strip(),
            copy_id=copy_id,
        )
        if provision_receipt
        else {}
    )
    plan = managed_copy_safe_delta_review_plan(
        payload,
        actor=actor,
        provision_receipt=provision_receipt,
        isolation_receipt=isolation_receipt,
    )
    dry_run_value = payload.get("dry_run", True)
    dry_run_type_valid = isinstance(dry_run_value, bool)
    dry_run = dry_run_value if dry_run_type_valid else True
    outcome: dict[str, Any] = {
        "ok": False,
        "status": "blocked_safe_delta_review_contract",
        "error": "safe_delta_review_contract_not_ready",
        "receipt": None,
        "receipt_id": "",
        "safe_delta_review_recorded": False,
        "safe_delta_approved": False,
        "safe_delta_exported": False,
        "learning_written": False,
        "writes_receipt": False,
    }
    if not provision_receipt:
        outcome.update(
            status="blocked_copy_provision_required",
            error="copy_provision_receipt_missing_or_mismatch",
        )
    elif not isolation_receipt.get("live_state_aligned"):
        outcome.update(
            status="blocked_live_structural_isolation_required",
            error="live_structural_isolation_receipt_required",
        )
    elif isolation_receipt_id != _safe_str(isolation_receipt.get("receipt_id")).strip():
        outcome.update(
            status="blocked_isolation_verification_receipt_mismatch",
            error="isolation_verification_receipt_id_mismatch",
        )
    elif not dry_run_type_valid:
        outcome.update(error="dry_run_must_be_boolean")
    elif not plan["review_contract_ready"]:
        outcome.update(error="safe_delta_review_contract_not_ready")
    elif dry_run:
        outcome.update(ok=True, status="safe_delta_review_ready", error="")
    else:
        outcome = record_managed_copy_safe_delta_review(
            plan,
            provided_fingerprint=_safe_str(payload.get("review_fingerprint")).strip(),
            confirm_review=payload.get("confirm_safe_delta_review") is True,
        )

    review_recorded = bool(outcome.get("safe_delta_review_recorded"))
    writes_receipt = bool(outcome.get("writes_receipt"))
    return {
        "ok": bool(outcome["ok"]),
        "kind": MANAGED_COPIES_SAFE_DELTA_REVIEW_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": outcome["status"],
        "error": outcome["error"],
        "actor": plan["actor"],
        "copy_id": plan["copy_id"],
        "copy_id_present": bool(copy_id),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "tenant_key": plan["tenant_key"],
        "provisioning_receipt_id": plan["provisioning_receipt_id"],
        "isolation_verification_receipt_id": plan["isolation_verification_receipt_id"],
        "candidate_present": isinstance(payload.get("candidate"), dict),
        "candidate_field_presence": plan["candidate_field_presence"],
        "candidate_unknown_field_count": plan["candidate_unknown_field_count"],
        "candidate_checks": plan["candidate_checks"],
        "candidate_fingerprint": plan["candidate_fingerprint"],
        "tenant_policy_checks": plan["tenant_policy_checks"],
        "signal_class": plan["signal_class"],
        "signal_class_known": bool(plan["signal_allowed_by_contract"] or plan["signal_denied_by_contract"]),
        "signal_allowed_by_contract": bool(plan["signal_allowed_by_contract"]),
        "signal_denied_by_contract": bool(plan["signal_denied_by_contract"]),
        "direction": plan["direction"],
        "stage17_closed_by_receipt": True,
        "stage17_blocker": "",
        "safe_delta_model_ready": False,
        "safe_delta_review_enabled": bool(provision_receipt and isolation_receipt.get("live_state_aligned")),
        "safe_delta_review_recorded": review_recorded,
        "safe_delta_approved": False,
        "safe_delta_flow_active": False,
        "delta_export_enabled": False,
        "delta_import_enabled": False,
        "learning_write_enabled": False,
        "safe_delta_exported": False,
        "learning_written": False,
        "raw_private_pooling_allowed": False,
        "cross_tenant_data_flow_allowed": False,
        "tenant_reidentification_allowed": False,
        "unattributed_learning_allowed": False,
        "blockers": plan["blockers"],
        "dry_run": dry_run,
        "review_contract_ready": bool(plan["review_contract_ready"]),
        "review_fingerprint": plan["review_fingerprint"],
        "dry_run_confirmation": {
            **plan["dry_run_confirmation"],
            "fingerprint_matched": bool(
                not dry_run
                and plan["review_fingerprint"]
                and _safe_str(payload.get("review_fingerprint")).strip() == plan["review_fingerprint"]
            ),
            "review_confirmed": payload.get("confirm_safe_delta_review") is True,
        },
        "receipt_ready": bool(outcome.get("receipt_id")),
        "receipt_id": _safe_str(outcome.get("receipt_id")).strip(),
        "receipt": outcome.get("receipt"),
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": writes_receipt,
        "writes_receipts": writes_receipt,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_review_receipt_path": (
            "managed_copies/tenants/{tenant_key}/receipts/sd/{review_fingerprint_prefix}.json"
        ),
        "required_scope": MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE,
        "routes": {
            **status["routes"],
            "safe_delta_review": "/managed-copies/safe-delta-review",
            "safe_delta_reviews": "/managed-copies/safe-delta-reviews",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": dry_run,
            "permission_scope": MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE,
            "permission_checked": True,
            "exact_candidate_schema_enforced": True,
            "live_structural_isolation_required": True,
            "tenant_safe_delta_policy_required": True,
            "operator_approval_required_before_export": True,
            "does_not_echo_raw_signal_payload": True,
            "safe_delta_flow_active": False,
            "exports_delta": False,
            "imports_delta": False,
            "writes_learning": False,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": writes_receipt,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": not writes_receipt,
        "projection_only": not writes_receipt,
        "next_smallest_truthful_gap": (
            "stage18_safe_delta_operator_approval" if review_recorded else "stage18_safe_delta_candidate_review"
        ),
    }


def managed_copy_safe_delta_reviews_snapshot(
    *,
    copy_id: str = "",
    provisioning_receipt_id: str = "",
    isolation_verification_receipt_id: str = "",
    review_fingerprint: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Return hash-only safe-delta review receipts without exporting data."""
    return managed_copy_safe_delta_review_receipts_readback(
        copy_id=copy_id,
        provisioning_receipt_id=provisioning_receipt_id,
        isolation_verification_receipt_id=isolation_verification_receipt_id,
        review_fingerprint=review_fingerprint,
        limit=limit,
    )


def managed_copy_safe_delta_decision_snapshot(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    plan = managed_copy_safe_delta_decision_plan(payload, actor=actor)
    dry_run_value = payload.get("dry_run", True)
    if not isinstance(dry_run_value, bool):
        outcome = {"ok": False, "status": "blocked", "error": "dry_run_must_be_boolean"}
    elif dry_run_value:
        outcome = {
            "ok": bool(plan["ok"]),
            "status": plan["status"],
            "error": "" if plan["ok"] else "safe_delta_decision_contract_not_ready",
        }
    else:
        outcome = record_managed_copy_safe_delta_decision(
            plan,
            provided_fingerprint=_safe_str(payload.get("decision_fingerprint")).strip(),
            confirmed=payload.get("confirm_safe_delta_decision") is True,
        )
    writes = bool(outcome.get("writes_receipt"))
    decision = _safe_str(plan.get("decision")).strip()
    return {
        **plan,
        "ok": bool(outcome["ok"]),
        "kind": "francis.stage18.managed_copies.safe_delta_approval",
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "status": outcome["status"],
        "error": outcome["error"],
        "dry_run": dry_run_value if isinstance(dry_run_value, bool) else True,
        "receipt": outcome.get("receipt"),
        "receipt_id": _safe_str(outcome.get("receipt_id")).strip(),
        "safe_delta_approved": bool(outcome.get("safe_delta_approved")),
        "safe_delta_rejected": bool(outcome.get("safe_delta_rejected")),
        "eligible_for_future_export_preflight": bool(outcome.get("eligible_for_future_export_preflight")),
        "writes_receipt": writes,
        "writes_receipts": writes,
        "exports_delta": False,
        "imports_delta": False,
        "writes_learning": False,
        "executes_action": False,
        "writes_memory": False,
        "writes_registry": False,
        "writes_tenant_state": False,
        "uses_network": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "required_scope": MANAGED_COPIES_SAFE_DELTA_APPROVAL_WRITE_SCOPE,
        "decision_exact": decision in {"approved", "rejected"},
    }


def managed_copy_safe_delta_decisions_snapshot(**kwargs: Any) -> dict[str, Any]:
    return managed_copy_safe_delta_decisions_readback(**kwargs)


def managed_copy_safe_delta_export_preflight_snapshot(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    return {
        **managed_copy_safe_delta_export_preflight(payload, actor=actor),
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "required_scope": MANAGED_COPIES_SAFE_DELTA_EXPORT_PREFLIGHT_SCOPE,
    }


def managed_copy_safe_delta_export_authorization_request_snapshot(
    payload: dict[str, Any], *, actor: str
) -> dict[str, Any]:
    plan = managed_copy_safe_delta_export_authorization_request_plan(payload, actor=actor)
    outcome: dict[str, Any] = plan
    if payload.get("dry_run") is False:
        outcome = record_managed_copy_safe_delta_export_authorization_request(
            plan,
            provided_fingerprint=_safe_str(payload.get("request_fingerprint")).strip(),
            confirmed=payload.get("confirm_export_authorization_request") is True,
        )
    return {
        **plan,
        **outcome,
        "kind": "francis.stage18.managed_copies.safe_delta_export_authorization_request",
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "required_scope": MANAGED_COPIES_SAFE_DELTA_EXPORT_AUTHORIZATION_REQUEST_SCOPE,
    }


def managed_copy_safe_delta_export_authorization_requests_snapshot(**kwargs: Any) -> dict[str, Any]:
    return managed_copy_safe_delta_export_authorization_requests_readback(**kwargs)


def managed_copy_safe_delta_export_authorization_decision_snapshot(
    payload: dict[str, Any], *, actor: str
) -> dict[str, Any]:
    plan = managed_copy_safe_delta_export_authorization_decision_plan(payload, actor=actor)
    outcome: dict[str, Any] = plan
    if payload.get("dry_run") is False:
        outcome = record_managed_copy_safe_delta_export_authorization_decision(
            plan,
            provided_fingerprint=_safe_str(payload.get("authorization_decision_fingerprint")).strip(),
            confirmed=payload.get("confirm_export_authorization_decision") is True,
        )
    return {
        **plan,
        **outcome,
        "kind": "francis.stage18.managed_copies.safe_delta_export_authorization_decision",
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "required_scope": MANAGED_COPIES_SAFE_DELTA_EXPORT_AUTHORIZATION_DECISION_SCOPE,
    }


def managed_copy_safe_delta_export_authorization_decisions_snapshot(**kwargs: Any) -> dict[str, Any]:
    return managed_copy_safe_delta_export_authorization_decisions_readback(**kwargs)


def managed_copy_safe_delta_export_artifact_plan_snapshot(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    return {
        **managed_copy_safe_delta_export_artifact_plan(payload, actor=actor),
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "required_scope": MANAGED_COPIES_SAFE_DELTA_EXPORT_ARTIFACT_PREFLIGHT_SCOPE,
    }


def managed_copy_rogue_recovery_contract_snapshot() -> dict[str, Any]:
    """Return the rogue recovery contract without acting on managed copies."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    detection_signals = [
        _rogue_recovery_signal(
            "governance_drift",
            "Governance or policy enforcement differs from the managed-copy contract",
            status="contract_only",
            severity="high",
        ),
        _rogue_recovery_signal(
            "unexpected_capability_behavior",
            "Capability behavior differs from declared lineage, risk tier, or approval scope",
            status="contract_only",
            severity="high",
        ),
        _rogue_recovery_signal(
            "suspicious_cross_boundary_activity",
            "Cross-tenant, support, connector, or safe-delta boundary activity is suspicious",
            status="contract_only",
            severity="critical",
        ),
        _rogue_recovery_signal(
            "broken_receipt_discipline",
            "Actions, support access, or policy changes lack required receipts",
            status="contract_only",
            severity="critical",
        ),
        _rogue_recovery_signal(
            "corrupted_continuity_state",
            "Continuity, memory, or tenant state appears corrupted or incoherent",
            status="contract_only",
            severity="high",
        ),
        _rogue_recovery_signal(
            "repeated_unexplained_failures",
            "Repeated failures occur without bounded explanation or repair lineage",
            status="contract_only",
            severity="medium",
        ),
        _rogue_recovery_signal(
            "unsafe_execution_deviation",
            "Execution deviates from approved scope, toolbelt, or tenant authority",
            status="contract_only",
            severity="critical",
        ),
    ]
    recovery_steps = [
        _rogue_recovery_step(
            "detect",
            "Detect anomalous managed-copy behavior and preserve evidence references",
            status="contract_only",
            writes_receipt=False,
            mutates_copy_state=False,
        ),
        _rogue_recovery_step(
            "halt",
            "Halt risky managed-copy operation before further tenant or support action",
            status="disabled",
            writes_receipt=True,
            mutates_copy_state=True,
        ),
        _rogue_recovery_step(
            "quarantine",
            "Quarantine the managed copy while preserving receipts, lineage, and diagnostic state",
            status="disabled",
            writes_receipt=True,
            mutates_copy_state=True,
        ),
        _rogue_recovery_step(
            "review",
            "Run support/operator review with tenant-visible evidence and bounded authority",
            status="contract_only",
            writes_receipt=False,
            mutates_copy_state=False,
        ),
        _rogue_recovery_step(
            "replace",
            "Replace from clean baseline, trusted snapshot, or controlled customer configuration",
            status="disabled",
            writes_receipt=True,
            mutates_copy_state=True,
        ),
        _rogue_recovery_step(
            "restore",
            "Restore lawful continuity only after verification receipts exist",
            status="disabled",
            writes_receipt=True,
            mutates_copy_state=True,
        ),
    ]
    return {
        "ok": True,
        "kind": MANAGED_COPIES_ROGUE_RECOVERY_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "contract_readback_ready",
        "contract_readback_ready": True,
        "rogue_recovery_ready": False,
        "rogue_detection_enabled": False,
        "halt_enabled": False,
        "quarantine_enabled": False,
        "replacement_enabled": False,
        "restore_enabled": False,
        "copy_creation_enabled": False,
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "stage17_blocker": status["stage17_blocker"],
        "detection_signals": detection_signals,
        "detection_signal_count": len(detection_signals),
        "recovery_steps": recovery_steps,
        "required_receipts": [
            "rogue_detection_receipt",
            "halt_decision_receipt",
            "quarantine_receipt",
            "evidence_preservation_receipt",
            "support_review_receipt",
            "replacement_plan_receipt",
            "clean_baseline_verification_receipt",
            "restore_verification_receipt",
        ],
        "replacement_sources_allowed": [
            "clean_core_baseline",
            "trusted_known_good_snapshot",
            "validated_global_state",
            "controlled_customer_configuration_state",
        ],
        "operator_controls_required": [
            "explicit_operator_or_tenant_admin_decision",
            "tenant_visible_incident_state",
            "support_authority_scope_check",
            "rollback_or_replace_plan_review",
            "post_restore_verification_review",
            "revocation_path_available",
        ],
        "rogue_recovery_review_route": "/managed-copies/rogue-recovery-review",
        "routes": {
            **status["routes"],
            "rogue_recovery_contract": "/managed-copies/rogue-recovery-contract",
            "rogue_recovery_review": "/managed-copies/rogue-recovery-review",
        },
        "blocked_failure_modes": [
            "uncontained_anomalous_instance",
            "messy_replacement_without_lineage",
            "support_team_improvisation",
            "evidence_loss_after_incident",
            "trust_collapse_after_incident",
            "hidden_vendor_control",
        ],
        "governance": governance,
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "halts_copy": False,
        "quarantines_copy": False,
        "replaces_copy": False,
        "restores_copy": False,
        "support_backdoor_allowed": False,
        "next_smallest_truthful_gap": status["next_smallest_truthful_gap"],
    }


def managed_copy_rogue_detection_assessment_snapshot(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    plan = managed_copy_rogue_detection_assessment_plan(payload, actor=actor)
    outcome: dict[str, Any] = plan
    if payload.get("dry_run") is False:
        outcome = record_managed_copy_rogue_detection_assessment(
            plan,
            provided_fingerprint=_safe_str(payload.get("assessment_fingerprint")).strip(),
            confirmed=payload.get("confirm_rogue_signal_assessment") is True,
        )
    return {
        **plan,
        **outcome,
        "kind": "francis.stage18.managed_copies.rogue_detection_assessment",
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "required_scope": MANAGED_COPIES_ROGUE_RECOVERY_WRITE_SCOPE,
    }


def managed_copy_rogue_detection_assessments_snapshot(**kwargs: Any) -> dict[str, Any]:
    return managed_copy_rogue_detection_assessments_readback(**kwargs)


def managed_copy_integrity_scan_snapshot(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    return managed_copy_integrity_scan(payload, actor=actor)


def managed_copy_integrity_evidence_snapshot(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    plan = managed_copy_integrity_evidence_plan(payload, actor=actor)
    outcome: dict[str, Any] = plan
    if payload.get("dry_run") is False:
        outcome = record_managed_copy_integrity_evidence(
            plan,
            provided_fingerprint=_safe_str(payload.get("evidence_fingerprint")).strip(),
            confirmed=payload.get("confirm_integrity_evidence") is True,
        )
    return {
        **plan,
        **outcome,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "required_scope": MANAGED_COPIES_ROGUE_RECOVERY_WRITE_SCOPE,
    }


def managed_copy_integrity_evidence_readback_snapshot(**kwargs: Any) -> dict[str, Any]:
    return managed_copy_integrity_evidence_readback(**kwargs)


def managed_copy_tenant_access_check_snapshot(payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    return managed_copy_tenant_access_check(payload, actor=actor)


def managed_copy_rogue_recovery_review_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed rogue-recovery review preflight without acting on a copy."""
    governance = _governance()
    contract = managed_copy_rogue_recovery_contract_snapshot()
    blocked_status, blocked_error = _managed_copy_preflight_block(bool(contract["stage17_closed_by_receipt"]))
    signal_id = _safe_str(payload.get("signal_id") or payload.get("detection_signal")).strip()
    signal_by_id = {item["id"]: item for item in contract["detection_signals"]}
    signal = signal_by_id.get(signal_id, {})
    action = _safe_str(payload.get("action") or payload.get("recovery_step")).strip()
    step_by_id = {item["id"]: item for item in contract["recovery_steps"]}
    step = step_by_id.get(action, {})
    raw_evidence_refs = payload.get("evidence_refs")
    evidence_ref_count = len(raw_evidence_refs) if isinstance(raw_evidence_refs, list) else 0
    return {
        "ok": False,
        "kind": MANAGED_COPIES_ROGUE_RECOVERY_REVIEW_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": blocked_status,
        "error": blocked_error,
        "actor": _safe_str(actor).strip(),
        "copy_id_present": bool(_safe_str(payload.get("copy_id")).strip()),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "incident_present": payload.get("incident") is not None,
        "evidence_ref_count": evidence_ref_count,
        "signal_id": signal_id,
        "signal_known": bool(signal),
        "signal_severity": _safe_str(signal.get("severity")).strip(),
        "action": action,
        "action_known": bool(step),
        "action_writes_receipt": bool(step.get("writes_receipt")),
        "action_mutates_copy_state": bool(step.get("mutates_copy_state")),
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": contract["stage17_blocker"],
        "rogue_recovery_ready": False,
        "rogue_recovery_review_enabled": False,
        "rogue_detection_enabled": False,
        "halt_enabled": False,
        "quarantine_enabled": False,
        "replacement_enabled": False,
        "restore_enabled": False,
        "halts_copy": False,
        "quarantines_copy": False,
        "replaces_copy": False,
        "restores_copy": False,
        "support_backdoor_allowed": False,
        "receipt_ready": False,
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_review_receipt_path": "logs/managed_copies/rogue_recovery_reviews.jsonl",
        "required_scope": MANAGED_COPIES_ROGUE_RECOVERY_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "rogue_recovery_review": "/managed-copies/rogue-recovery-review",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": True,
            "permission_scope": MANAGED_COPIES_ROGUE_RECOVERY_WRITE_SCOPE,
            "permission_checked": True,
            "rogue_recovery_review_enabled": False,
            "does_not_detect_rogue_copy": True,
            "does_not_halt_copy": True,
            "does_not_quarantine_copy": True,
            "does_not_replace_copy": True,
            "does_not_restore_copy": True,
            "does_not_record_rogue_recovery_receipt": True,
            "does_not_mutate_copy_state": True,
            "does_not_echo_raw_incident_payload": True,
            "requires_stage17_closure_receipt": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "next_smallest_truthful_gap": contract["next_smallest_truthful_gap"],
    }


def managed_copy_sla_framework_contract_snapshot() -> dict[str, Any]:
    """Return the managed-copy SLA framework contract without activating service commitments."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    commitments = [
        _sla_commitment(
            "uptime_commitment",
            "Managed-copy uptime commitments require tenant plan, monitoring, and incident receipts",
            status="contract_only",
            active=False,
        ),
        _sla_commitment(
            "response_commitment",
            "Support response commitments require support tier, escalation rules, and tenant visibility",
            status="contract_only",
            active=False,
        ),
        _sla_commitment(
            "incident_handling_commitment",
            "Incident handling commitments require evidence preservation and operator-visible state",
            status="contract_only",
            active=False,
        ),
        _sla_commitment(
            "recovery_commitment",
            "Recovery commitments require rogue recovery, clean baseline, and restore verification receipts",
            status="contract_only",
            active=False,
        ),
        _sla_commitment(
            "support_tier_commitment",
            "Support tiers require bounded support authority and tenant-admin approval paths",
            status="contract_only",
            active=False,
        ),
        _sla_commitment(
            "managed_governance_commitment",
            "Managed governance commitments require policy review, auditability, and revocation paths",
            status="contract_only",
            active=False,
        ),
    ]
    return {
        "ok": True,
        "kind": MANAGED_COPIES_SLA_FRAMEWORK_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "contract_readback_ready",
        "contract_readback_ready": True,
        "sla_framework_ready": False,
        "sla_commitments_active": False,
        "monitoring_enabled": False,
        "paging_enabled": False,
        "support_tiers_enabled": False,
        "billing_entitlements_enabled": False,
        "copy_creation_enabled": False,
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "stage17_blocker": status["stage17_blocker"],
        "commitments": commitments,
        "commitment_count": len(commitments),
        "active_commitment_count": sum(1 for commitment in commitments if commitment["active"]),
        "support_tiers": [
            "standard_support",
            "priority_support",
            "premium_governance_support",
            "rogue_recovery_assistance",
        ],
        "required_receipts": [
            "sla_plan_receipt",
            "tenant_support_tier_receipt",
            "monitoring_scope_receipt",
            "incident_response_receipt",
            "recovery_commitment_receipt",
            "managed_governance_review_receipt",
            "sla_exception_or_breach_receipt",
        ],
        "service_metrics": [
            "uptime_window",
            "response_time_window",
            "incident_acknowledgement_time",
            "recovery_time_objective",
            "recovery_point_objective",
            "governance_review_interval",
            "support_access_audit_interval",
        ],
        "operator_controls_required": [
            "tenant_visible_sla_state",
            "support_authority_scope_check",
            "incident_severity_review",
            "recovery_plan_review",
            "breach_exception_review",
            "revocation_or_downgrade_path",
        ],
        "blocked_failure_modes": [
            "unbounded_support_obligation",
            "invisible_vendor_power",
            "sla_claim_without_monitoring",
            "incident_handling_without_receipts",
            "recovery_promise_without_recovery_path",
            "support_tier_without_authority_boundary",
        ],
        "sla_commitment_review_route": "/managed-copies/sla-commitment-review",
        "routes": {
            **status["routes"],
            "sla_framework_contract": "/managed-copies/sla-framework-contract",
            "sla_commitment_review": "/managed-copies/sla-commitment-review",
        },
        "governance": governance,
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "creates_service_commitment": False,
        "pages_support": False,
        "opens_incident": False,
        "records_sla_receipt": False,
        "grants_support_authority": False,
        "next_smallest_truthful_gap": status["next_smallest_truthful_gap"],
    }


def managed_copy_sla_commitment_review_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed SLA commitment review preflight without activating service."""
    governance = _governance()
    contract = managed_copy_sla_framework_contract_snapshot()
    blocked_status, blocked_error = _managed_copy_preflight_block(bool(contract["stage17_closed_by_receipt"]))
    raw_commitment_id = _safe_str(payload.get("commitment_id") or payload.get("commitment")).strip()
    commitment_by_id = {item["id"]: item for item in contract["commitments"]}
    commitment = commitment_by_id.get(raw_commitment_id, {})
    raw_support_tier = _safe_str(payload.get("support_tier")).strip()
    support_tier_known = raw_support_tier in set(contract["support_tiers"])
    raw_metric = _safe_str(payload.get("metric") or payload.get("service_metric")).strip()
    metric_known = raw_metric in set(contract["service_metrics"])
    raw_evidence_refs = payload.get("evidence_refs")
    evidence_ref_count = len(raw_evidence_refs) if isinstance(raw_evidence_refs, list) else 0
    return {
        "ok": False,
        "kind": MANAGED_COPIES_SLA_COMMITMENT_REVIEW_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": blocked_status,
        "error": blocked_error,
        "actor": _safe_str(actor).strip(),
        "copy_id_present": bool(_safe_str(payload.get("copy_id")).strip()),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "incident_present": payload.get("incident") is not None,
        "evidence_ref_count": evidence_ref_count,
        "commitment_id": raw_commitment_id if commitment else "unknown",
        "commitment_known": bool(commitment),
        "commitment_active": bool(commitment.get("active")),
        "commitment_requires_receipt": bool(commitment.get("requires_receipt")),
        "support_tier": raw_support_tier if support_tier_known else "unknown",
        "support_tier_known": support_tier_known,
        "metric": raw_metric if metric_known else "unknown",
        "metric_known": metric_known,
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": contract["stage17_blocker"],
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
        "receipt_ready": False,
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_review_receipt_path": "logs/managed_copies/sla_commitment_reviews.jsonl",
        "required_scope": MANAGED_COPIES_SLA_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "sla_commitment_review": "/managed-copies/sla-commitment-review",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": True,
            "permission_scope": MANAGED_COPIES_SLA_WRITE_SCOPE,
            "permission_checked": True,
            "sla_review_enabled": False,
            "sla_framework_ready": False,
            "does_not_create_service_commitment": True,
            "does_not_enable_monitoring": True,
            "does_not_page_support": True,
            "does_not_open_incident": True,
            "does_not_record_sla_receipt": True,
            "does_not_grant_support_authority": True,
            "does_not_echo_raw_sla_payload": True,
            "requires_stage17_closure_receipt": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "next_smallest_truthful_gap": contract["next_smallest_truthful_gap"],
    }


def managed_copy_roles_contract_snapshot() -> dict[str, Any]:
    """Return managed-copy role boundaries without activating role authority."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    roles = [
        _managed_copy_role(
            "end_user",
            "End user",
            status="contract_only",
            allowed_authority=[
                "use_tenant_scoped_surfaces",
                "request_work_inside_tenant_policy",
                "view_own_visible_receipts",
            ],
            denied_authority=[
                "create_managed_copy",
                "change_tenant_policy",
                "grant_support_access",
                "bind_credentials",
                "pair_nodes",
            ],
        ),
        _managed_copy_role(
            "tenant_admin",
            "Tenant admin",
            status="contract_only",
            allowed_authority=[
                "approve_tenant_policy_changes",
                "approve_support_access",
                "review_sla_state",
                "request_export_or_decommission",
            ],
            denied_authority=[
                "surrender_core_ip",
                "bypass_core_governance",
                "grant_vendor_backdoor",
                "share_raw_private_pooling",
            ],
        ),
        _managed_copy_role(
            "support_operator",
            "Support operator",
            status="contract_only",
            allowed_authority=[
                "inspect_tenant_visible_incident_state",
                "assist_recovery_with_scoped_approval",
                "write_support_review_receipts_when_enabled",
            ],
            denied_authority=[
                "standing_tenant_access",
                "hidden_control",
                "read_raw_secrets",
                "mutate_tenant_state_without_approval",
                "expand_scope",
            ],
        ),
        _managed_copy_role(
            "automation_principal",
            "Automation principal",
            status="contract_only",
            allowed_authority=[
                "run_bounded_service_tasks_when_scoped",
                "use_bound_service_credentials_when_enabled",
                "emit_receipts_when_enabled",
            ],
            denied_authority=[
                "impersonate_human_operator",
                "hold_broad_standing_tokens",
                "change_policy",
                "grant_authority",
            ],
        ),
        _managed_copy_role(
            "paired_node",
            "Paired node",
            status="contract_only",
            allowed_authority=[
                "exchange_selective_state_when_paired",
                "carry_node_attributed_receipts_when_enabled",
                "participate_in_safe_delta_flow_when_approved",
            ],
            denied_authority=[
                "silent_trust_expansion",
                "receive_out_of_scope_artifacts",
                "read_cross_tenant_memory",
                "act_without_node_attribution",
            ],
        ),
    ]
    return {
        "ok": True,
        "kind": MANAGED_COPIES_ROLES_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "contract_readback_ready",
        "contract_readback_ready": True,
        "roles_contract_ready": False,
        "role_authority_active": False,
        "authority_binding_enabled": False,
        "credential_binding_enabled": False,
        "support_authority_enabled": False,
        "automation_principal_enabled": False,
        "paired_node_authority_enabled": False,
        "copy_creation_enabled": False,
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "stage17_blocker": status["stage17_blocker"],
        "roles": roles,
        "required_role_count": len(roles),
        "active_role_count": sum(1 for role in roles if role["authority_active"]),
        "role_separation_rules": [
            "human_authority_separate_from_backend_service_authority",
            "support_authority_separate_from_tenant_admin_authority",
            "automation_principal_cannot_impersonate_human_operator",
            "paired_node_authority_is_scoped_and_revocable",
            "tenant_admin_cannot_surrender_core_ip_or_bypass_core_law",
        ],
        "credential_binding_rules": [
            "scoped_credentials_only",
            "rotation_and_revocation_required",
            "bind_credentials_to_node_copy_connector_or_capability_class",
            "no_raw_secret_exposure_in_lens_logs_receipts_or_replay",
            "approval_and_audit_required_for_creation_attachment_elevation_and_replacement",
        ],
        "required_receipts": [
            "role_binding_receipt",
            "tenant_admin_delegation_receipt",
            "support_authority_receipt",
            "automation_principal_scope_receipt",
            "paired_node_trust_receipt",
            "credential_binding_receipt",
            "role_revocation_receipt",
        ],
        "blocked_failure_modes": [
            "fuzzy_role_authority",
            "standing_support_access",
            "backend_service_impersonates_user",
            "paired_node_trust_expansion",
            "automation_principal_scope_creep",
            "raw_secret_exposure",
            "tenant_admin_core_law_bypass",
        ],
        "role_authority_review_route": "/managed-copies/role-authority-review",
        "routes": {
            **status["routes"],
            "roles_contract": "/managed-copies/roles-contract",
            "role_authority_review": "/managed-copies/role-authority-review",
        },
        "governance": governance,
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "creates_role_binding": False,
        "binds_credentials": False,
        "grants_support_access": False,
        "activates_automation_principal": False,
        "pairs_node": False,
        "revokes_role": False,
        "next_smallest_truthful_gap": status["next_smallest_truthful_gap"],
    }


def managed_copy_role_authority_review_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed role-authority review preflight without binding authority."""
    governance = _governance()
    contract = managed_copy_roles_contract_snapshot()
    blocked_status, blocked_error = _managed_copy_preflight_block(bool(contract["stage17_closed_by_receipt"]))
    role_id = _safe_str(payload.get("role_id") or payload.get("role")).strip()
    role_by_id = {item["id"]: item for item in contract["roles"]}
    role = role_by_id.get(role_id, {})
    requested_authority = _safe_str(payload.get("requested_authority") or payload.get("authority")).strip()
    allowed_authorities = set(role.get("allowed_authority", []))
    denied_authorities = set(role.get("denied_authority", []))
    authority_known = requested_authority in allowed_authorities or requested_authority in denied_authorities
    binding_type = _safe_str(payload.get("binding_type") or payload.get("binding")).strip()
    known_binding_types = {
        "role_binding",
        "tenant_admin_delegation",
        "support_authority",
        "automation_principal_scope",
        "paired_node_trust",
        "credential_binding",
        "role_revocation",
    }
    binding_type_known = binding_type in known_binding_types
    raw_evidence_refs = payload.get("evidence_refs")
    evidence_ref_count = len(raw_evidence_refs) if isinstance(raw_evidence_refs, list) else 0
    return {
        "ok": False,
        "kind": MANAGED_COPIES_ROLE_AUTHORITY_REVIEW_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": blocked_status,
        "error": blocked_error,
        "actor": _safe_str(actor).strip(),
        "copy_id_present": bool(_safe_str(payload.get("copy_id")).strip()),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "role_id": role_id if role else "unknown",
        "role_known": bool(role),
        "requested_authority": requested_authority if authority_known else "unknown",
        "requested_authority_known": authority_known,
        "requested_authority_allowed_by_contract": requested_authority in allowed_authorities,
        "requested_authority_denied_by_contract": requested_authority in denied_authorities,
        "binding_type": binding_type if binding_type_known else "unknown",
        "binding_type_known": binding_type_known,
        "credential_binding_present": payload.get("credential_binding") is not None,
        "support_access_requested": payload.get("support_access") is not None,
        "automation_principal_requested": payload.get("automation_principal") is not None,
        "node_pairing_requested": payload.get("node_pairing") is not None,
        "evidence_ref_count": evidence_ref_count,
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": contract["stage17_blocker"],
        "roles_contract_ready": False,
        "role_authority_review_enabled": False,
        "role_authority_active": False,
        "authority_binding_enabled": False,
        "credential_binding_enabled": False,
        "support_authority_enabled": False,
        "automation_principal_enabled": False,
        "paired_node_authority_enabled": False,
        "creates_role_binding": False,
        "binds_credentials": False,
        "grants_support_access": False,
        "activates_automation_principal": False,
        "pairs_node": False,
        "revokes_role": False,
        "receipt_ready": False,
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_review_receipt_path": "logs/managed_copies/role_authority_reviews.jsonl",
        "required_scope": MANAGED_COPIES_ROLE_AUTHORITY_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "role_authority_review": "/managed-copies/role-authority-review",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": True,
            "permission_scope": MANAGED_COPIES_ROLE_AUTHORITY_WRITE_SCOPE,
            "permission_checked": True,
            "role_authority_review_enabled": False,
            "role_authority_active": False,
            "does_not_create_role_binding": True,
            "does_not_bind_credentials": True,
            "does_not_grant_support_access": True,
            "does_not_activate_automation_principal": True,
            "does_not_pair_node": True,
            "does_not_revoke_role": True,
            "does_not_record_role_authority_receipt": True,
            "does_not_echo_raw_authority_payload": True,
            "requires_stage17_closure_receipt": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "next_smallest_truthful_gap": contract["next_smallest_truthful_gap"],
    }


def managed_copy_decommission_contract_snapshot() -> dict[str, Any]:
    """Return managed-copy exit-rights rules without mutating tenant state."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    steps = [
        _decommission_step(
            "request",
            "Record a tenant-admin or operator decommission request",
            status="contract_only",
            writes_receipt=False,
            mutates_tenant_state=False,
        ),
        _decommission_step(
            "export_before_delete",
            "Export tenant data, receipts, configuration, and lawful continuity before deletion",
            status="disabled",
            writes_receipt=True,
            mutates_tenant_state=False,
        ),
        _decommission_step(
            "revoke_credentials",
            "Revoke credentials, connector bindings, support access, and automation principals",
            status="disabled",
            writes_receipt=True,
            mutates_tenant_state=True,
        ),
        _decommission_step(
            "unpair_nodes",
            "Revoke paired-node relationships without weakening other copies",
            status="disabled",
            writes_receipt=True,
            mutates_tenant_state=True,
        ),
        _decommission_step(
            "delete_tenant_state",
            "Delete tenant-specific state inside the declared decommission scope",
            status="disabled",
            writes_receipt=True,
            mutates_tenant_state=True,
        ),
        _decommission_step(
            "retain_required_records",
            "Retain only policy-required audit, legal, billing, or safety records",
            status="contract_only",
            writes_receipt=False,
            mutates_tenant_state=False,
        ),
        _decommission_step(
            "prove_outcome",
            "Prove what was exported, deleted, retained, rotated, revoked, or transferred",
            status="disabled",
            writes_receipt=True,
            mutates_tenant_state=False,
        ),
    ]
    return {
        "ok": True,
        "kind": MANAGED_COPIES_DECOMMISSION_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "contract_readback_ready",
        "contract_readback_ready": True,
        "decommission_contract_ready": False,
        "decommission_enabled": False,
        "export_enabled": False,
        "delete_enabled": False,
        "purge_enabled": False,
        "credential_revocation_enabled": False,
        "node_unpairing_enabled": False,
        "proof_receipts_enabled": False,
        "copy_creation_enabled": False,
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "stage17_blocker": status["stage17_blocker"],
        "decommission_steps": steps,
        "step_count": len(steps),
        "active_step_count": sum(1 for step in steps if step["status"] == "enabled"),
        "export_scope": [
            "tenant_configuration",
            "tenant_policy",
            "tenant_receipts",
            "tenant_memory_exports_where_policy_allows",
            "tenant_capability_pack_lineage",
            "tenant_sla_and_support_history",
            "tenant_safe_delta_lineage",
        ],
        "deletion_scope": [
            "tenant_runtime_state",
            "tenant_memory_state",
            "tenant_connector_bindings",
            "tenant_credentials",
            "tenant_support_access",
            "tenant_automation_principals",
            "tenant_pairings",
        ],
        "retention_scope": [
            "legal_hold_records",
            "billing_records",
            "security_incident_records",
            "policy_required_audit_summaries",
            "deidentified_platform_safety_metrics_when_allowed",
        ],
        "required_receipts": [
            "decommission_request_receipt",
            "export_before_delete_receipt",
            "credential_revocation_receipt",
            "node_unpairing_receipt",
            "tenant_state_delete_receipt",
            "retention_scope_receipt",
            "decommission_proof_receipt",
        ],
        "operator_controls_required": [
            "tenant_admin_or_operator_request",
            "export_review_before_delete",
            "deletion_scope_review",
            "retention_policy_review",
            "cross_copy_non_weakening_review",
            "final_proof_review",
        ],
        "blocked_failure_modes": [
            "trapped_tenant_state",
            "residual_authority_after_decommission",
            "delete_without_export",
            "cross_copy_state_damage",
            "unproved_deletion",
            "hidden_retention",
            "vendor_gravity_exit_block",
        ],
        "decommission_review_route": "/managed-copies/decommission-review",
        "routes": {
            **status["routes"],
            "decommission_contract": "/managed-copies/decommission-contract",
            "decommission_review": "/managed-copies/decommission-review",
        },
        "governance": governance,
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "exports_tenant_data": False,
        "deletes_tenant_state": False,
        "revokes_credentials": False,
        "unpairs_nodes": False,
        "purges_memory": False,
        "records_decommission_receipt": False,
        "weakens_other_copies": False,
        "next_smallest_truthful_gap": status["next_smallest_truthful_gap"],
    }


def _requested_known_scope_counts(payload: dict[str, Any], field: str, allowed: list[str]) -> dict[str, int]:
    raw_items = payload.get(field)
    if not isinstance(raw_items, list):
        return {"requested_count": 0, "known_count": 0, "unknown_count": 0}
    requested = [_safe_str(item).strip() for item in raw_items if _safe_str(item).strip()]
    allowed_set = set(allowed)
    known_count = sum(1 for item in requested if item in allowed_set)
    return {
        "requested_count": len(requested),
        "known_count": known_count,
        "unknown_count": len(requested) - known_count,
    }


def managed_copy_decommission_review_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed decommission review preflight without mutating tenant state."""
    governance = _governance()
    contract = managed_copy_decommission_contract_snapshot()
    blocked_status, blocked_error = _managed_copy_preflight_block(bool(contract["stage17_closed_by_receipt"]))
    action = _safe_str(payload.get("action") or payload.get("decommission_step")).strip()
    step_by_id = {item["id"]: item for item in contract["decommission_steps"]}
    step = step_by_id.get(action, {})
    raw_evidence_refs = payload.get("evidence_refs")
    evidence_ref_count = len(raw_evidence_refs) if isinstance(raw_evidence_refs, list) else 0
    export_scope_counts = _requested_known_scope_counts(payload, "export_scope", contract["export_scope"])
    deletion_scope_counts = _requested_known_scope_counts(payload, "deletion_scope", contract["deletion_scope"])
    retention_scope_counts = _requested_known_scope_counts(payload, "retention_scope", contract["retention_scope"])
    return {
        "ok": False,
        "kind": MANAGED_COPIES_DECOMMISSION_REVIEW_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": blocked_status,
        "error": blocked_error,
        "actor": _safe_str(actor).strip(),
        "copy_id_present": bool(_safe_str(payload.get("copy_id")).strip()),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "request_present": payload.get("decommission_request") is not None,
        "evidence_ref_count": evidence_ref_count,
        "action": action if step else "unknown",
        "action_known": bool(step),
        "action_writes_receipt": bool(step.get("writes_receipt")),
        "action_mutates_tenant_state": bool(step.get("mutates_tenant_state")),
        "export_scope_requested_count": export_scope_counts["requested_count"],
        "export_scope_known_count": export_scope_counts["known_count"],
        "export_scope_unknown_count": export_scope_counts["unknown_count"],
        "deletion_scope_requested_count": deletion_scope_counts["requested_count"],
        "deletion_scope_known_count": deletion_scope_counts["known_count"],
        "deletion_scope_unknown_count": deletion_scope_counts["unknown_count"],
        "retention_scope_requested_count": retention_scope_counts["requested_count"],
        "retention_scope_known_count": retention_scope_counts["known_count"],
        "retention_scope_unknown_count": retention_scope_counts["unknown_count"],
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": contract["stage17_blocker"],
        "decommission_contract_ready": False,
        "decommission_review_enabled": False,
        "decommission_enabled": False,
        "export_enabled": False,
        "delete_enabled": False,
        "purge_enabled": False,
        "credential_revocation_enabled": False,
        "node_unpairing_enabled": False,
        "proof_receipts_enabled": False,
        "exports_tenant_data": False,
        "deletes_tenant_state": False,
        "revokes_credentials": False,
        "unpairs_nodes": False,
        "purges_memory": False,
        "records_decommission_receipt": False,
        "weakens_other_copies": False,
        "receipt_ready": False,
        "writes_registry": False,
        "writes_memory": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_review_receipt_path": "logs/managed_copies/decommission_reviews.jsonl",
        "required_scope": MANAGED_COPIES_DECOMMISSION_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "decommission_review": "/managed-copies/decommission-review",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": True,
            "permission_scope": MANAGED_COPIES_DECOMMISSION_WRITE_SCOPE,
            "permission_checked": True,
            "decommission_review_enabled": False,
            "decommission_enabled": False,
            "does_not_export_tenant_data": True,
            "does_not_delete_tenant_state": True,
            "does_not_revoke_credentials": True,
            "does_not_unpair_nodes": True,
            "does_not_purge_memory": True,
            "does_not_record_decommission_receipt": True,
            "does_not_weaken_other_copies": True,
            "does_not_echo_raw_decommission_payload": True,
            "requires_stage17_closure_receipt": True,
            "writes_registry": False,
            "writes_memory": False,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "runs_tools": False,
            "runs_shell": False,
            "runs_git": False,
            "launches_browser": False,
            "captures_screen": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "next_smallest_truthful_gap": contract["next_smallest_truthful_gap"],
    }


def managed_copy_completion_review_snapshot() -> dict[str, Any]:
    """Return Stage 18 managed-copy closure readiness without recording closure."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    copy_creation = managed_copy_creation_contract_snapshot()
    isolation = managed_copy_isolation_rules_contract_snapshot()
    safe_delta = managed_copy_safe_delta_model_contract_snapshot()
    rogue_recovery = managed_copy_rogue_recovery_contract_snapshot()
    sla_framework = managed_copy_sla_framework_contract_snapshot()
    roles = managed_copy_roles_contract_snapshot()
    decommission = managed_copy_decommission_contract_snapshot()
    checks = [
        _completion_check(
            "stage17_ledger_closure_backstop",
            "Stage 17 is closed by receipt before managed-copy closure review",
            readback_ready=True,
            runtime_ready=bool(status["stage17_closed_by_receipt"]),
            route="/managed-copies/status",
            blocker=_safe_str(status["stage17_blocker"]),
        ),
        _completion_check(
            "copy_creation_contract",
            "Copy creation contract is read back and backed by runtime creation proof",
            readback_ready=bool(copy_creation["contract_readback_ready"]),
            runtime_ready=bool(copy_creation["copy_creation_allowed"]),
            route="/managed-copies/copy-creation-contract",
            blocker="stage18_copy_creation_runtime_not_implemented",
        ),
        _completion_check(
            "isolation_rules_contract",
            "Tenant isolation rules are read back and enforced at runtime",
            readback_ready=bool(isolation["contract_readback_ready"]),
            runtime_ready=bool(isolation["isolation_rules_ready"]),
            route="/managed-copies/isolation-rules-contract",
            blocker="stage18_tenant_isolation_runtime_not_implemented",
        ),
        _completion_check(
            "safe_delta_model_contract",
            "Safe delta model is read back and proven by governed runtime flow",
            readback_ready=bool(safe_delta["contract_readback_ready"]),
            runtime_ready=bool(safe_delta["safe_delta_model_ready"]),
            route="/managed-copies/safe-delta-model-contract",
            blocker="stage18_safe_delta_runtime_not_implemented",
        ),
        _completion_check(
            "rogue_recovery_contract",
            "Rogue recovery model is read back and backed by live detect/replace proof",
            readback_ready=bool(rogue_recovery["contract_readback_ready"]),
            runtime_ready=bool(rogue_recovery["rogue_recovery_ready"]),
            route="/managed-copies/rogue-recovery-contract",
            blocker="stage18_rogue_recovery_runtime_not_implemented",
        ),
        _completion_check(
            "sla_framework_contract",
            "SLA framework is read back and backed by active service evidence",
            readback_ready=bool(sla_framework["contract_readback_ready"]),
            runtime_ready=bool(sla_framework["sla_framework_ready"]),
            route="/managed-copies/sla-framework-contract",
            blocker="stage18_sla_runtime_not_implemented",
        ),
        _completion_check(
            "roles_contract",
            "Managed-copy role contract is read back and backed by authority binding proof",
            readback_ready=bool(roles["contract_readback_ready"]),
            runtime_ready=bool(roles["roles_contract_ready"]),
            route="/managed-copies/roles-contract",
            blocker="stage18_role_authority_runtime_not_implemented",
        ),
        _completion_check(
            "decommission_contract",
            "Decommission contract is read back and backed by exit-rights proof",
            readback_ready=bool(decommission["contract_readback_ready"]),
            runtime_ready=bool(decommission["decommission_contract_ready"]),
            route="/managed-copies/decommission-contract",
            blocker="stage18_decommission_runtime_not_implemented",
        ),
    ]
    readback_ready = all(check["readback_ready"] for check in checks)
    runtime_ready = all(check["runtime_ready"] for check in checks)
    ready_to_close = readback_ready and runtime_ready
    blockers = [check["blocker"] for check in checks if not check["passed"]]
    runtime_evidence_readbacks = managed_copy_runtime_evidence_readbacks_snapshot()
    return {
        "ok": True,
        "kind": MANAGED_COPIES_COMPLETION_REVIEW_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "ready" if ready_to_close else "blocked",
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "contract_readback_complete": readback_ready,
        "runtime_readiness_ready": runtime_ready,
        "stage18_completion_review_ready": ready_to_close,
        "ready_to_close": ready_to_close,
        "stage_closure_decision_required": ready_to_close,
        "runtime_evidence_readback_ready": bool(runtime_evidence_readbacks["runtime_evidence_readback_ready"]),
        "runtime_evidence_readbacks": {
            "status": runtime_evidence_readbacks["status"],
            "count": runtime_evidence_readbacks["count"],
            "ready_count": runtime_evidence_readbacks["ready_count"],
            "required_count": runtime_evidence_readbacks["required_count"],
            "missing_evidence": runtime_evidence_readbacks["missing_evidence"],
        },
        "checks": checks,
        "readback_ready_count": sum(1 for check in checks if check["readback_ready"]),
        "runtime_ready_count": sum(1 for check in checks if check["runtime_ready"]),
        "passed_count": sum(1 for check in checks if check["passed"]),
        "required_count": len(checks),
        "blockers": blockers,
        "done_criteria": {
            "customer_instances_are_isolated": bool(isolation["isolation_rules_ready"]),
            "global_core_improves_through_safe_signals": bool(safe_delta["safe_delta_model_ready"]),
            "rogue_instances_can_be_detected_and_replaced": bool(rogue_recovery["rogue_recovery_ready"]),
            "business_model_aligned_to_product_law": ready_to_close,
        },
        "routes": {
            **status["routes"],
            "completion_review": "/managed-copies/completion-review",
        },
        "governance": {
            **governance,
            "completion_review_only": True,
            "does_not_mark_stage_closed": True,
            "requires_runtime_evidence": True,
            "requires_stage17_closure_receipt": True,
            "stage_closure_decision_required": ready_to_close,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "copy_creation_enabled": governance["copy_creation_enabled"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "next_smallest_truthful_gap": blockers[0] if blockers else "stage18_stage_closure_decision",
    }


def managed_copy_runtime_evidence_contract_snapshot() -> dict[str, Any]:
    """Return required managed-copy runtime proof slots without collecting evidence."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    requirements = [
        _runtime_evidence_requirement(
            "stage17_closure_receipt",
            "Stage 17 closure receipt proves capability-economy prerequisites are closed",
            source_contract_route="/managed-copies/status",
            proof_kind="ledger_closure_receipt",
            blocker=_safe_str(status["stage17_blocker"]),
            ready=bool(status["stage17_closed_by_receipt"]),
            receipt_id=_safe_str(status["stage17_closure_receipt_id"]),
        ),
        _runtime_evidence_requirement(
            "copy_creation_runtime_proof",
            "A governed managed copy is created with isolated state and required receipts",
            source_contract_route="/managed-copies/copy-creation-contract",
            proof_kind="managed_copy_creation_runtime_receipt",
            blocker="stage18_copy_creation_runtime_not_implemented",
        ),
        _runtime_evidence_requirement(
            "tenant_isolation_runtime_proof",
            "Tenant data, memory, receipts, connectors, policy, and support authority are isolated",
            source_contract_route="/managed-copies/isolation-rules-contract",
            proof_kind="tenant_isolation_runtime_receipt",
            blocker="stage18_tenant_isolation_runtime_not_implemented",
        ),
        _runtime_evidence_requirement(
            "safe_delta_runtime_proof",
            "Safe deltas move only approved non-private signals with lineage and redaction evidence",
            source_contract_route="/managed-copies/safe-delta-model-contract",
            proof_kind="safe_delta_runtime_receipt",
            blocker="stage18_safe_delta_runtime_not_implemented",
        ),
        _runtime_evidence_requirement(
            "rogue_recovery_runtime_proof",
            "A rogue-copy scenario can be detected, halted, reviewed, replaced, and restored with evidence",
            source_contract_route="/managed-copies/rogue-recovery-contract",
            proof_kind="rogue_recovery_runtime_receipt",
            blocker="stage18_rogue_recovery_runtime_not_implemented",
        ),
        _runtime_evidence_requirement(
            "sla_runtime_proof",
            "Managed-copy SLA commitments are backed by monitoring, incident, support, and recovery evidence",
            source_contract_route="/managed-copies/sla-framework-contract",
            proof_kind="sla_runtime_receipt",
            blocker="stage18_sla_runtime_not_implemented",
        ),
        _runtime_evidence_requirement(
            "role_authority_runtime_proof",
            "Managed-copy role and credential authority is explicitly bound, scoped, auditable, and revocable",
            source_contract_route="/managed-copies/roles-contract",
            proof_kind="managed_copy_role_authority_receipt",
            blocker="stage18_role_authority_runtime_not_implemented",
        ),
        _runtime_evidence_requirement(
            "decommission_runtime_proof",
            "Managed-copy exit rights can export, delete, retain, revoke, unpair, and prove outcomes",
            source_contract_route="/managed-copies/decommission-contract",
            proof_kind="decommission_runtime_receipt",
            blocker="stage18_decommission_runtime_not_implemented",
        ),
    ]
    return {
        "ok": True,
        "kind": MANAGED_COPIES_RUNTIME_EVIDENCE_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "blocked",
        "contract_readback_ready": True,
        "runtime_evidence_contract_ready": False,
        "runtime_evidence_recording_enabled": False,
        "runtime_evidence_ready": False,
        "stage17_closed_by_receipt": bool(status["stage17_closed_by_receipt"]),
        "stage17_blocker": status["stage17_blocker"],
        "requirements": requirements,
        "ready_count": sum(1 for requirement in requirements if requirement["ready"]),
        "required_count": len(requirements),
        "blockers": [requirement["blocker"] for requirement in requirements if not requirement["ready"]],
        "accepted_proof_kinds": [requirement["proof_kind"] for requirement in requirements],
        "receipt_logical_scope": "future_managed_copy_runtime_evidence",
        "completion_review_route": "/managed-copies/completion-review",
        "routes": {
            **status["routes"],
            "runtime_evidence_contract": "/managed-copies/runtime-evidence-contract",
        },
        "governance": {
            **governance,
            "runtime_evidence_contract_only": True,
            "evidence_collection_enabled": False,
            "does_not_record_runtime_evidence": True,
            "does_not_mark_stage_closed": True,
            "requires_stage17_closure_receipt": True,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "copy_creation_enabled": governance["copy_creation_enabled"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "next_smallest_truthful_gap": status["next_smallest_truthful_gap"],
    }


def managed_copy_runtime_evidence_readbacks_snapshot(*, limit: int = 100) -> dict[str, Any]:
    """Return managed-copy runtime evidence receipts already present on disk."""
    governance = _governance()
    contract = managed_copy_runtime_evidence_contract_snapshot()
    items = _read_jsonl_tail(_runtime_evidence_path(), limit=limit)
    latest_by_requirement = _latest_runtime_evidence_by_requirement(items)
    checks: list[dict[str, Any]] = []
    for requirement in contract["requirements"]:
        item = latest_by_requirement.get(requirement["id"], {})
        prerequisite_ready = bool(requirement.get("ready"))
        receipt_ready = prerequisite_ready or _runtime_evidence_ready(item, requirement)
        receipt_id = (
            _safe_str(requirement.get("receipt_id")).strip()
            if prerequisite_ready
            else _safe_str(item.get("receipt_id")).strip()
        )
        checks.append(
            {
                "id": requirement["id"],
                "passed": receipt_ready,
                "receipt_ready": receipt_ready,
                "status": "observed" if receipt_ready else "not_observed",
                "receipt_id": receipt_id,
                "proof_kind": requirement["proof_kind"]
                if prerequisite_ready
                else _safe_str(item.get("proof_kind")).strip(),
                "trace_id": _safe_str(item.get("trace_id")).strip(),
                "source_contract_route": requirement["source_contract_route"],
                "blocker": requirement["blocker"],
                "evidence": (
                    f"validated prerequisite receipt {receipt_id}"
                    if prerequisite_ready
                    else _safe_str(item.get("evidence_summary")).strip()
                    or f"no {requirement['id']} runtime evidence receipt has been recorded"
                ),
            }
        )
    missing_evidence = [check["id"] for check in checks if not check["passed"]]
    ready = not missing_evidence
    return {
        "ok": True,
        "kind": MANAGED_COPIES_RUNTIME_EVIDENCE_READBACKS_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "ready" if ready else "partial" if any(check["passed"] for check in checks) else "empty",
        "items": items,
        "checks": checks,
        "count": len(items),
        "receipt_ready_count": sum(1 for check in checks if check["receipt_ready"]),
        "ready_count": sum(1 for check in checks if check["passed"]),
        "required_count": len(checks),
        "runtime_evidence_readback_ready": ready,
        "runtime_evidence_ready": ready,
        "missing_evidence": missing_evidence,
        "missing_blockers": [check["blocker"] for check in checks if not check["passed"] and check["blocker"]],
        "expected_receipt_path": "logs/managed_copies/runtime_evidence.jsonl",
        "runtime_evidence_recording_enabled": False,
        "routes": {
            **contract["routes"],
            "runtime_evidence_readbacks": "/managed-copies/runtime-evidence-readbacks",
        },
        "governance": {
            **governance,
            "runtime_evidence_readback_only": True,
            "does_not_record_runtime_evidence": True,
            "does_not_mark_stage_closed": True,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "copy_creation_enabled": governance["copy_creation_enabled"],
        "writes_registry": governance["writes_registry"],
        "writes_memory": governance["writes_memory"],
        "writes_receipts": governance["writes_receipts"],
        "writes_tenant_state": governance["writes_tenant_state"],
        "runs_tools": governance["runs_tools"],
        "runs_shell": governance["runs_shell"],
        "runs_git": governance["runs_git"],
        "launches_browser": governance["launches_browser"],
        "captures_screen": governance["captures_screen"],
        "grants_execution_authority": governance["grants_execution_authority"],
        "grants_mutation_authority": governance["grants_mutation_authority"],
        "next_smallest_truthful_gap": contract["next_smallest_truthful_gap"]
        if missing_evidence
        else "stage18_completion_review",
    }


def managed_copy_runtime_evidence_readback_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed runtime-evidence write preflight without recording evidence."""
    governance = _governance()
    contract = managed_copy_runtime_evidence_contract_snapshot()
    blocked_status, blocked_error = _managed_copy_preflight_block(bool(contract["stage17_closed_by_receipt"]))
    requirement_id = _safe_str(payload.get("requirement_id")).strip()
    proof_kind = _safe_str(payload.get("proof_kind")).strip()
    requirement_by_id = {item["id"]: item for item in contract["requirements"]}
    requirement = requirement_by_id.get(requirement_id, {})
    expected_proof_kind = _safe_str(requirement.get("proof_kind")).strip()
    return {
        "ok": False,
        "kind": MANAGED_COPIES_RUNTIME_EVIDENCE_READBACK_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": blocked_status,
        "error": blocked_error,
        "actor": _safe_str(actor).strip(),
        "requirement_id": requirement_id,
        "requirement_known": bool(requirement),
        "proof_kind": proof_kind,
        "expected_proof_kind": expected_proof_kind,
        "proof_kind_matches_requirement": bool(requirement) and proof_kind == expected_proof_kind,
        "trace_id": _safe_str(payload.get("trace_id")).strip()[:240],
        "reason": _safe_str(payload.get("reason")).strip()[:500],
        "evidence_summary_present": bool(_safe_str(payload.get("evidence_summary")).strip()),
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": contract["stage17_blocker"],
        "runtime_evidence_recording_enabled": False,
        "receipt_ready": False,
        "writes_receipt": False,
        "writes_receipts": False,
        "writes_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "expected_receipt_path": "logs/managed_copies/runtime_evidence.jsonl",
        "required_scope": MANAGED_COPIES_RUNTIME_EVIDENCE_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "runtime_evidence_readback": "/managed-copies/runtime-evidence-readback",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": True,
            "permission_scope": MANAGED_COPIES_RUNTIME_EVIDENCE_WRITE_SCOPE,
            "permission_checked": True,
            "runtime_evidence_recording_enabled": False,
            "does_not_record_runtime_evidence": True,
            "does_not_mark_stage_closed": True,
            "requires_stage17_closure_receipt": True,
            "writes_receipts": False,
            "writes_tenant_state": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "read_only": governance["read_only"],
        "projection_only": governance["projection_only"],
        "next_smallest_truthful_gap": contract["next_smallest_truthful_gap"],
    }
