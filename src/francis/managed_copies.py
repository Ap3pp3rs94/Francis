from __future__ import annotations

from typing import Any

STAGE18_MANAGED_COPIES_STAGE = "Stage 18 / Managed Copies Platform"
MANAGED_COPIES_STATUS_KIND = "francis.stage18.managed_copies.status"
MANAGED_COPIES_COPY_CREATION_CONTRACT_KIND = "francis.stage18.managed_copies.copy_creation_contract"
MANAGED_COPIES_ISOLATION_RULES_CONTRACT_KIND = "francis.stage18.managed_copies.isolation_rules_contract"
MANAGED_COPIES_SAFE_DELTA_MODEL_CONTRACT_KIND = "francis.stage18.managed_copies.safe_delta_model_contract"
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
            status="pending",
            next_gap="stage18_rogue_kill_replace_flows",
        ),
        _deliverable(
            "sla_framework",
            "SLA framework beginnings",
            ready=False,
            status="pending",
            next_gap="stage18_sla_framework",
        ),
        _deliverable(
            "managed_copy_roles",
            "Managed-copy role contract",
            ready=False,
            status="pending",
            next_gap="stage18_managed_copy_roles_contract",
        ),
        _deliverable(
            "exit_rights",
            "Decommission export and deletion contract",
            ready=False,
            status="pending",
            next_gap="stage18_decommission_export_delete_contract",
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
