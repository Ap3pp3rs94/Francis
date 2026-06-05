from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir

STAGE18_MANAGED_COPIES_STAGE = "Stage 18 / Managed Copies Platform"
MANAGED_COPIES_STATUS_KIND = "francis.stage18.managed_copies.status"
MANAGED_COPIES_COPY_CREATION_CONTRACT_KIND = "francis.stage18.managed_copies.copy_creation_contract"
MANAGED_COPIES_COPY_CREATION_REQUEST_KIND = "francis.stage18.managed_copies.copy_creation_request"
MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE = "managed_copies.copy_creation.write"
MANAGED_COPIES_ISOLATION_RULES_CONTRACT_KIND = "francis.stage18.managed_copies.isolation_rules_contract"
MANAGED_COPIES_ISOLATION_VERIFICATION_KIND = "francis.stage18.managed_copies.isolation_verification"
MANAGED_COPIES_ISOLATION_VERIFICATION_WRITE_SCOPE = "managed_copies.isolation_verification.write"
MANAGED_COPIES_SAFE_DELTA_MODEL_CONTRACT_KIND = "francis.stage18.managed_copies.safe_delta_model_contract"
MANAGED_COPIES_SAFE_DELTA_REVIEW_KIND = "francis.stage18.managed_copies.safe_delta_review"
MANAGED_COPIES_SAFE_DELTA_WRITE_SCOPE = "managed_copies.safe_delta.write"
MANAGED_COPIES_ROGUE_RECOVERY_CONTRACT_KIND = "francis.stage18.managed_copies.rogue_recovery_contract"
MANAGED_COPIES_SLA_FRAMEWORK_CONTRACT_KIND = "francis.stage18.managed_copies.sla_framework_contract"
MANAGED_COPIES_ROLES_CONTRACT_KIND = "francis.stage18.managed_copies.roles_contract"
MANAGED_COPIES_DECOMMISSION_CONTRACT_KIND = "francis.stage18.managed_copies.decommission_contract"
MANAGED_COPIES_COMPLETION_REVIEW_KIND = "francis.stage18.managed_copies.completion_review"
MANAGED_COPIES_RUNTIME_EVIDENCE_CONTRACT_KIND = "francis.stage18.managed_copies.runtime_evidence_contract"
MANAGED_COPIES_RUNTIME_EVIDENCE_READBACKS_KIND = "francis.stage18.managed_copies.runtime_evidence_readbacks"
MANAGED_COPIES_RUNTIME_EVIDENCE_READBACK_KIND = "francis.stage18.managed_copies.runtime_evidence_readback"
MANAGED_COPIES_RUNTIME_EVIDENCE_WRITE_SCOPE = "managed_copies.runtime_evidence.write"
STAGE17_OPERATOR_EVIDENCE_REFS_GAP = "stage17_capability_library_operator_proposal_evidence_refs"


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


def _runtime_evidence_requirement(
    requirement_id: str,
    title: str,
    *,
    source_contract_route: str,
    proof_kind: str,
    blocker: str,
    requires_receipt: bool = True,
) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "title": title,
        "status": "required_not_present",
        "ready": False,
        "source_contract_route": source_contract_route,
        "proof_kind": proof_kind,
        "blocker": blocker,
        "requires_receipt": requires_receipt,
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
    deliverables = [
        _deliverable(
            "stage17_ledger_closure_backstop",
            "Stage 17 closure backstop",
            ready=False,
            status="blocked",
            next_gap=STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
            evidence=[
                "Stage 17 still requires real operator refs to pass import-preview, dry-run, and governed apply.",
            ],
        ),
        _deliverable(
            "copy_creation_process",
            "Copy creation process",
            ready=False,
            status="contract_readback_ready",
            next_gap="stage18_copy_creation_process",
            evidence=[
                "GET /managed-copies/copy-creation-contract exposes required gates without enabling creation.",
            ],
        ),
        _deliverable(
            "isolation_rules",
            "Isolation rules",
            ready=False,
            status="contract_readback_ready",
            next_gap="stage18_copy_isolation_rules",
            evidence=[
                "GET /managed-copies/isolation-rules-contract exposes tenant boundary rules without enforcing them.",
            ],
        ),
        _deliverable(
            "safe_delta_model",
            "Safe delta model",
            ready=False,
            status="contract_readback_ready",
            next_gap="stage18_safe_delta_model",
            evidence=[
                "GET /managed-copies/safe-delta-model-contract exposes allowed signal classes without exporting data.",
            ],
        ),
        _deliverable(
            "rogue_recovery",
            "Rogue kill/replace flows",
            ready=False,
            status="contract_readback_ready",
            next_gap="stage18_rogue_kill_replace_flows",
            evidence=[
                "GET /managed-copies/rogue-recovery-contract exposes detect/halt/quarantine/replace gates without acting.",
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
        "status": "stage18_prerequisites_blocked",
        "status_readback_ready": True,
        "stage17_closed_by_receipt": False,
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "deliverables": deliverables,
        "routes": {
            "status": "/managed-copies/status",
            "copy_creation_contract": "/managed-copies/copy-creation-contract",
            "copy_creation_request": "/managed-copies/copy-creation-request",
            "isolation_rules_contract": "/managed-copies/isolation-rules-contract",
            "isolation_verification": "/managed-copies/isolation-verification",
            "safe_delta_model_contract": "/managed-copies/safe-delta-model-contract",
            "safe_delta_review": "/managed-copies/safe-delta-review",
            "rogue_recovery_contract": "/managed-copies/rogue-recovery-contract",
            "sla_framework_contract": "/managed-copies/sla-framework-contract",
            "roles_contract": "/managed-copies/roles-contract",
            "decommission_contract": "/managed-copies/decommission-contract",
            "runtime_evidence_contract": "/managed-copies/runtime-evidence-contract",
            "runtime_evidence_readbacks": "/managed-copies/runtime-evidence-readbacks",
            "runtime_evidence_readback": "/managed-copies/runtime-evidence-readback",
            "completion_review": "/managed-copies/completion-review",
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_creation_contract_snapshot() -> dict[str, Any]:
    """Return the governed copy-creation process contract without creating copies."""
    governance = _governance()
    status = managed_copies_status_snapshot()
    requirements = [
        _contract_requirement(
            "stage17_closed_by_receipt",
            "Stage 17 closure is backed by real operator proposal-evidence refs",
            ready=False,
            next_gap=STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
            evidence=[
                "Current ledger posture keeps Stage 17 open until real refs pass import-preview, dry-run, and apply.",
            ],
        ),
        _contract_requirement(
            "tenant_identity_contract",
            "Tenant identity and administrator authority are declared before planning",
            ready=False,
            next_gap="stage18_tenant_identity_contract",
        ),
        _contract_requirement(
            "tenant_policy_contract",
            "Tenant policy boundaries are explicit before provisioning",
            ready=False,
            next_gap="stage18_tenant_policy_contract",
        ),
        _contract_requirement(
            "isolation_profile_contract",
            "Data, memory, receipt, connector, and capability-pack isolation profile is declared",
            ready=False,
            next_gap="stage18_copy_isolation_rules",
        ),
        _contract_requirement(
            "capability_lineage_contract",
            "Capability pack lineage and allowed customization layers are declared",
            ready=False,
            next_gap="stage18_capability_lineage_contract",
        ),
        _contract_requirement(
            "safe_delta_policy_contract",
            "Safe delta policy blocks raw private pooling and uncontrolled improvement flow",
            ready=False,
            next_gap="stage18_safe_delta_model",
        ),
        _contract_requirement(
            "rogue_recovery_contract",
            "Rogue halt, quarantine, replacement, and support authority boundaries are declared",
            ready=False,
            next_gap="stage18_rogue_kill_replace_flows",
        ),
        _contract_requirement(
            "decommission_contract",
            "Export, deletion, retention, rotation, and proof receipts are declared",
            ready=False,
            next_gap="stage18_decommission_export_delete_contract",
        ),
    ]
    process_steps = [
        _contract_step(
            "request",
            "Record an operator-approved managed-copy request",
            status="not_implemented",
        ),
        _contract_step(
            "preflight",
            "Check Stage 17 closure, tenant identity, policy, isolation, lineage, and support prerequisites",
            status="contract_only",
        ),
        _contract_step(
            "plan",
            "Produce a copy-creation plan without provisioning state",
            status="contract_only",
        ),
        _contract_step(
            "approve",
            "Require explicit tenant-admin or operator approval before any provision step",
            status="contract_only",
        ),
        _contract_step(
            "provision",
            "Create isolated tenant state only after governed approval and receipt setup",
            status="disabled",
            writes_tenant_state=True,
            writes_registry=True,
            writes_receipt=True,
        ),
        _contract_step(
            "verify",
            "Verify isolation, lineage, policy, support boundaries, and decommission readiness",
            status="disabled",
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
        "stage17_closed_by_receipt": False,
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
        "requirements": requirements,
        "required_count": len(requirements),
        "ready_count": sum(1 for requirement in requirements if requirement["ready"]),
        "process_steps": process_steps,
        "state_machine": {
            "current_state": "not_implemented",
            "states": [
                "requested",
                "preflight_blocked",
                "planned",
                "approved",
                "provisioning",
                "verifying",
                "active",
                "quarantined",
                "decommissioned",
            ],
            "active_transitions_enabled": False,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_creation_request_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed copy-creation request preflight blocked by Stage 17."""
    governance = _governance()
    contract = managed_copy_creation_contract_snapshot()
    request_field_presence = {
        "tenant_id": bool(_safe_str(payload.get("tenant_id")).strip()),
        "tenant_identity": bool(payload.get("tenant_identity")),
        "tenant_policy": bool(payload.get("tenant_policy")),
        "isolation_profile": bool(payload.get("isolation_profile")),
        "capability_lineage": bool(payload.get("capability_lineage")),
        "safe_delta_policy": bool(payload.get("safe_delta_policy")),
        "support_boundary": bool(payload.get("support_boundary")),
        "decommission_policy": bool(payload.get("decommission_policy")),
    }
    return {
        "ok": False,
        "kind": MANAGED_COPIES_COPY_CREATION_REQUEST_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "blocked_stage17_prerequisite",
        "error": "stage17_prerequisite_not_closed",
        "actor": _safe_str(actor).strip(),
        "request_known": any(request_field_presence.values()),
        "request_field_presence": request_field_presence,
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
        "copy_creation_enabled": False,
        "copy_creation_allowed": False,
        "copy_request_recording_enabled": False,
        "copy_request_recorded": False,
        "copy_created": False,
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
        "expected_request_receipt_path": "logs/managed_copies/copy_requests.jsonl",
        "required_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
        "routes": {
            **contract["routes"],
            "copy_creation_request": "/managed-copies/copy-creation-request",
        },
        "governance": {
            **governance,
            "write_route": True,
            "preflight_only": True,
            "permission_scope": MANAGED_COPIES_COPY_CREATION_WRITE_SCOPE,
            "permission_checked": True,
            "copy_creation_enabled": False,
            "copy_request_recording_enabled": False,
            "does_not_record_copy_request": True,
            "does_not_create_copy": True,
            "does_not_mark_stage_closed": True,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


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
    return {
        "ok": True,
        "kind": MANAGED_COPIES_ISOLATION_RULES_CONTRACT_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "contract_readback_ready",
        "contract_readback_ready": True,
        "isolation_rules_ready": False,
        "isolation_enforcement_enabled": False,
        "copy_creation_enabled": False,
        "stage17_closed_by_receipt": False,
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
        "isolation_domains": isolation_domains,
        "required_domain_count": len(isolation_domains),
        "enforced_domain_count": sum(1 for domain in isolation_domains if domain["isolated"]),
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_isolation_verification_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed isolation verification preflight blocked by Stage 17."""
    governance = _governance()
    contract = managed_copy_isolation_rules_contract_snapshot()
    raw_domains = payload.get("domains")
    domain_values = raw_domains if isinstance(raw_domains, list) else []
    requested_domains = {_safe_str(domain).strip() for domain in domain_values if _safe_str(domain).strip()}
    required_domains = [item["id"] for item in contract["isolation_domains"]]
    domain_checks = [
        {
            "id": domain_id,
            "requested": domain_id in requested_domains,
            "verified": False,
            "status": "blocked_stage17_prerequisite",
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
        "status": "blocked_stage17_prerequisite",
        "error": "stage17_prerequisite_not_closed",
        "actor": _safe_str(actor).strip(),
        "copy_id_present": bool(_safe_str(payload.get("copy_id")).strip()),
        "tenant_id_present": bool(_safe_str(payload.get("tenant_id")).strip()),
        "requested_domain_count": len(requested_domains),
        "requested_unknown_domains": requested_unknown_domains,
        "required_domain_count": len(required_domains),
        "verified_domain_count": 0,
        "domain_checks": domain_checks,
        "stage17_closed_by_receipt": bool(contract["stage17_closed_by_receipt"]),
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_safe_delta_model_contract_snapshot() -> dict[str, Any]:
    """Return the safe-delta model contract without exporting tenant data."""
    governance = _governance()
    status = managed_copies_status_snapshot()
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
        "status": "contract_readback_ready",
        "contract_readback_ready": True,
        "safe_delta_model_ready": False,
        "delta_export_enabled": False,
        "delta_import_enabled": False,
        "learning_write_enabled": False,
        "copy_creation_enabled": False,
        "stage17_closed_by_receipt": False,
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_safe_delta_review_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed safe-delta review preflight blocked by Stage 17."""
    governance = _governance()
    contract = managed_copy_safe_delta_model_contract_snapshot()
    signal_class = _safe_str(payload.get("signal_class")).strip()
    allowed_signal_ids = {item["id"] for item in contract["allowed_signal_classes"]}
    denied_signal_ids = {item["id"] for item in contract["denied_signal_classes"]}
    raw_direction = _safe_str(payload.get("direction")).strip()
    direction = raw_direction if raw_direction in {"export", "import", "ingest"} else "unknown"
    return {
        "ok": False,
        "kind": MANAGED_COPIES_SAFE_DELTA_REVIEW_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "blocked_stage17_prerequisite",
        "error": "stage17_prerequisite_not_closed",
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
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "expected_review_receipt_path": "logs/managed_copies/safe_delta_reviews.jsonl",
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_rogue_recovery_contract_snapshot() -> dict[str, Any]:
    """Return the rogue recovery contract without acting on managed copies."""
    governance = _governance()
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
        "stage17_closed_by_receipt": False,
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_sla_framework_contract_snapshot() -> dict[str, Any]:
    """Return the managed-copy SLA framework contract without activating service commitments."""
    governance = _governance()
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
        "stage17_closed_by_receipt": False,
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_roles_contract_snapshot() -> dict[str, Any]:
    """Return managed-copy role boundaries without activating role authority."""
    governance = _governance()
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
        "stage17_closed_by_receipt": False,
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }


def managed_copy_decommission_contract_snapshot() -> dict[str, Any]:
    """Return managed-copy exit-rights rules without mutating tenant state."""
    governance = _governance()
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
        "stage17_closed_by_receipt": False,
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
            blocker=STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
            blocker=STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
        "requirements": requirements,
        "ready_count": sum(1 for requirement in requirements if requirement["ready"]),
        "required_count": len(requirements),
        "blockers": [requirement["blocker"] for requirement in requirements],
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        receipt_ready = _runtime_evidence_ready(item, requirement)
        checks.append(
            {
                "id": requirement["id"],
                "passed": receipt_ready,
                "receipt_ready": receipt_ready,
                "status": "observed" if receipt_ready else "not_observed",
                "receipt_id": _safe_str(item.get("receipt_id")).strip(),
                "proof_kind": _safe_str(item.get("proof_kind")).strip(),
                "trace_id": _safe_str(item.get("trace_id")).strip(),
                "source_contract_route": requirement["source_contract_route"],
                "blocker": requirement["blocker"],
                "evidence": _safe_str(item.get("evidence_summary")).strip()
                or f"no {requirement['id']} runtime evidence receipt has been recorded",
            }
        )
    missing_evidence = [check["id"] for check in checks if not check["passed"]]
    ready = not missing_evidence
    return {
        "ok": True,
        "kind": MANAGED_COPIES_RUNTIME_EVIDENCE_READBACKS_KIND,
        "stage": STAGE18_MANAGED_COPIES_STAGE,
        "source_id": "managed_copies",
        "status": "ready" if ready else "partial" if items else "empty",
        "items": items,
        "checks": checks,
        "count": len(items),
        "receipt_ready_count": sum(1 for check in checks if check["receipt_ready"]),
        "ready_count": sum(1 for check in checks if check["passed"]),
        "required_count": len(checks),
        "runtime_evidence_readback_ready": ready,
        "runtime_evidence_ready": ready,
        "missing_evidence": missing_evidence,
        "missing_blockers": [check["blocker"] for check in checks if not check["passed"]],
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP
        if missing_evidence
        else "stage18_completion_review",
    }


def managed_copy_runtime_evidence_readback_blocked_snapshot(
    payload: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    """Return a governed runtime-evidence write preflight blocked by Stage 17."""
    governance = _governance()
    contract = managed_copy_runtime_evidence_contract_snapshot()
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
        "status": "blocked_stage17_prerequisite",
        "error": "stage17_prerequisite_not_closed",
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
        "stage17_blocker": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
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
        "next_smallest_truthful_gap": STAGE17_OPERATOR_EVIDENCE_REFS_GAP,
    }
