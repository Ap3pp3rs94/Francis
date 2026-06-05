from __future__ import annotations

from typing import Any

STAGE18_MANAGED_COPIES_STAGE = "Stage 18 / Managed Copies Platform"
MANAGED_COPIES_STATUS_KIND = "francis.stage18.managed_copies.status"
MANAGED_COPIES_COPY_CREATION_CONTRACT_KIND = "francis.stage18.managed_copies.copy_creation_contract"
MANAGED_COPIES_ISOLATION_RULES_CONTRACT_KIND = "francis.stage18.managed_copies.isolation_rules_contract"
MANAGED_COPIES_SAFE_DELTA_MODEL_CONTRACT_KIND = "francis.stage18.managed_copies.safe_delta_model_contract"
MANAGED_COPIES_ROGUE_RECOVERY_CONTRACT_KIND = "francis.stage18.managed_copies.rogue_recovery_contract"
MANAGED_COPIES_SLA_FRAMEWORK_CONTRACT_KIND = "francis.stage18.managed_copies.sla_framework_contract"
MANAGED_COPIES_ROLES_CONTRACT_KIND = "francis.stage18.managed_copies.roles_contract"
MANAGED_COPIES_DECOMMISSION_CONTRACT_KIND = "francis.stage18.managed_copies.decommission_contract"
MANAGED_COPIES_COMPLETION_REVIEW_KIND = "francis.stage18.managed_copies.completion_review"
STAGE17_OPERATOR_EVIDENCE_REFS_GAP = "stage17_capability_library_operator_proposal_evidence_refs"


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
            "isolation_rules_contract": "/managed-copies/isolation-rules-contract",
            "safe_delta_model_contract": "/managed-copies/safe-delta-model-contract",
            "rogue_recovery_contract": "/managed-copies/rogue-recovery-contract",
            "sla_framework_contract": "/managed-copies/sla-framework-contract",
            "roles_contract": "/managed-copies/roles-contract",
            "decommission_contract": "/managed-copies/decommission-contract",
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


def managed_copy_isolation_rules_contract_snapshot() -> dict[str, Any]:
    """Return the managed-copy isolation rules contract without enforcing tenant state."""
    governance = _governance()
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


def managed_copy_safe_delta_model_contract_snapshot() -> dict[str, Any]:
    """Return the safe-delta model contract without exporting tenant data."""
    governance = _governance()
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
