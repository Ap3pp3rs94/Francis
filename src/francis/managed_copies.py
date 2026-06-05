from __future__ import annotations

from typing import Any

STAGE18_MANAGED_COPIES_STAGE = "Stage 18 / Managed Copies Platform"
MANAGED_COPIES_STATUS_KIND = "francis.stage18.managed_copies.status"
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
            status="blocked",
            next_gap="stage18_copy_creation_process",
        ),
        _deliverable(
            "isolation_rules",
            "Isolation rules",
            ready=False,
            status="pending",
            next_gap="stage18_copy_isolation_rules",
        ),
        _deliverable(
            "safe_delta_model",
            "Safe delta model",
            ready=False,
            status="pending",
            next_gap="stage18_safe_delta_model",
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
