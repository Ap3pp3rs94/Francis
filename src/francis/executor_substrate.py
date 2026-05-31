from __future__ import annotations

from typing import Any

from francis.telemetry.status import telemetry_status_snapshot

STAGE8_EXECUTOR_SUBSTRATE_STAGE = "Stage 8 / Executor Substrate"
EXECUTOR_SUBSTRATE_STATUS_KIND = "francis.stage8.executor_substrate.status"

_STAGE7_LEDGER_CLOSURE_GAP = "stage7_ledger_closure"
_STAGE8_TOOLBELT_ALLOWLIST_GAP = "stage8_executor_toolbelt_allowlist_review"
_STAGE8_BRANCH_FIRST_WORKFLOW_GAP = "stage8_branch_first_workflow_review"
_STAGE8_BRANCH_FIRST_ENFORCEMENT_GAP = "stage8_branch_first_workflow_enforcement"
_STAGE8_LEASES_IDEMPOTENCY_GAP = "stage8_leases_idempotency_review"


def executor_substrate_status_snapshot() -> dict[str, Any]:
    telemetry = telemetry_status_snapshot()
    stage7_closed = telemetry.get("next_smallest_truthful_gap") == _STAGE7_LEDGER_CLOSURE_GAP
    deliverables = _deliverables(stage7_closed=stage7_closed)
    ready_count = sum(1 for item in deliverables if item["ready"])
    return {
        "ok": True,
        "kind": EXECUTOR_SUBSTRATE_STATUS_KIND,
        "stage": STAGE8_EXECUTOR_SUBSTRATE_STAGE,
        "status": "substrate_contract_ready" if stage7_closed else "awaiting_stage7_ledger_closure",
        "source_id": "executor_substrate",
        "target": "safe_bounded_execution",
        "stage7_closed_by_receipt": stage7_closed,
        "stage7_next_smallest_truthful_gap": telemetry.get("next_smallest_truthful_gap", ""),
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "stage8_done_ready": False,
        "read_only": True,
        "writes_tasks": False,
        "writes_receipts": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "stage8_posture_contract": True,
            "requires_stage7_ledger_closure": True,
            "uses_stage7_telemetry_receipt_readback": True,
            "does_not_execute": True,
            "does_not_write_tasks": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_grant_authority": True,
            "telemetry_is_untrusted_input": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (_STAGE8_LEASES_IDEMPOTENCY_GAP if stage7_closed else _STAGE7_LEDGER_CLOSURE_GAP),
    }


def executor_toolbelt_allowlist_review_snapshot() -> dict[str, Any]:
    status = executor_substrate_status_snapshot()
    deliverables_value = status.get("deliverables")
    deliverables = deliverables_value if isinstance(deliverables_value, list) else []
    deliverable_map = {str(item.get("id")): item for item in deliverables if isinstance(item, dict)}
    toolbelt = deliverable_map.get("execution_toolbelt_inventory", {})
    allowlist = deliverable_map.get("allowlist_policy_filters", {})
    criteria = [
        {
            "id": "substrate_contract_ready",
            "ready": status.get("status") == "substrate_contract_ready",
            "evidence": {
                "status": status.get("status", "unknown"),
                "stage7_closed_by_receipt": bool(status.get("stage7_closed_by_receipt")),
            },
        },
        {
            "id": "toolbelt_inventory_readback",
            "ready": bool(toolbelt.get("ready")),
            "evidence": toolbelt.get("evidence", {}),
        },
        {
            "id": "allowlist_policy_filter_readback",
            "ready": bool(allowlist.get("ready")),
            "evidence": allowlist.get("evidence", {}),
        },
        {
            "id": "non_authorizing_review_guard",
            "ready": (
                status.get("read_only") is True
                and status.get("runs_tools") is False
                and status.get("runs_shell") is False
                and status.get("runs_git") is False
                and status.get("grants_execution_authority") is False
                and status.get("grants_mutation_authority") is False
            ),
            "evidence": {
                "read_only": bool(status.get("read_only")),
                "runs_tools": bool(status.get("runs_tools")),
                "runs_shell": bool(status.get("runs_shell")),
                "runs_git": bool(status.get("runs_git")),
                "grants_execution_authority": bool(status.get("grants_execution_authority")),
                "grants_mutation_authority": bool(status.get("grants_mutation_authority")),
            },
        },
    ]
    ready_count = sum(1 for criterion in criteria if criterion["ready"])
    review_ready = ready_count == len(criteria)
    toolbelt_evidence_value = toolbelt.get("evidence")
    toolbelt_evidence: dict[str, Any] = toolbelt_evidence_value if isinstance(toolbelt_evidence_value, dict) else {}
    known_capabilities = toolbelt_evidence.get("known_capabilities", [])
    return {
        "ok": True,
        "kind": "francis.stage8.executor_substrate.toolbelt_allowlist_review",
        "stage": STAGE8_EXECUTOR_SUBSTRATE_STAGE,
        "status": "toolbelt_allowlist_review_ready" if review_ready else "toolbelt_allowlist_review_partial",
        "source_id": "executor_substrate",
        "target": "safe_bounded_execution",
        "toolbelt_allowlist_review_ready": review_ready,
        "ready_count": ready_count,
        "required_count": len(criteria),
        "criteria": criteria,
        "known_capabilities": known_capabilities if isinstance(known_capabilities, list) else [],
        "substrate_status": {
            "route": "/executor/substrate/status",
            "status": status.get("status", "unknown"),
            "next_smallest_truthful_gap": status.get("next_smallest_truthful_gap", ""),
        },
        "read_only": True,
        "writes_tasks": False,
        "writes_receipts": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "toolbelt_allowlist_review": True,
            "uses_executor_substrate_status": True,
            "does_not_execute": True,
            "does_not_write_tasks": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_grant_authority": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (
            _STAGE8_BRANCH_FIRST_WORKFLOW_GAP if review_ready else _STAGE8_TOOLBELT_ALLOWLIST_GAP
        ),
    }


def executor_branch_first_workflow_review_snapshot() -> dict[str, Any]:
    allowlist_review = executor_toolbelt_allowlist_review_snapshot()
    criteria = [
        {
            "id": "toolbelt_allowlist_review_ready",
            "ready": bool(allowlist_review.get("toolbelt_allowlist_review_ready")),
            "evidence": {
                "route": "/executor/substrate/toolbelt-allowlist-review",
                "status": allowlist_review.get("status", "unknown"),
            },
        },
        {
            "id": "exact_current_branch_binding",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/git_push.py",
                "contract": "requested branch must match the detected current branch",
                "denial_error": "branch_mismatch",
            },
        },
        {
            "id": "detached_head_blocked",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/git_push.py",
                "contract": "detached HEAD is rejected before approval or push",
                "denial_error": "detached_head_not_supported",
            },
        },
        {
            "id": "approval_gated_execution",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/git_push.py",
                "gate": "approvals_gate",
                "next_step": "approve_exact_action",
            },
        },
        {
            "id": "stale_or_mismatched_approval_refresh",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/git_push.py",
                "missing_or_corrupt_status": "needs_approval",
                "mismatch_error": "approval_payload_mismatch",
                "writes_mismatch_artifact": True,
            },
        },
        {
            "id": "branch_first_enforcement_policy",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/git_push.py",
                "current_maintainer_workflow": "direct_on_main",
                "default_required": False,
                "required_input": "branch_first_required",
                "workflow_policy": "branch_first",
                "protected_branch_error": "branch_first_workflow_required",
                "preserves_current_maintainer_workflow": True,
            },
        },
        {
            "id": "branch_first_policy_receipt_readback",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/git_push.py",
                "receipt_kind": "git.push.branch_first_policy.receipt",
                "receipt_dir": "data/artifacts/git_push_branch_policy_receipts",
            },
        },
        {
            "id": "non_authorizing_review_guard",
            "ready": (
                allowlist_review.get("read_only") is True
                and allowlist_review.get("runs_tools") is False
                and allowlist_review.get("runs_shell") is False
                and allowlist_review.get("runs_git") is False
                and allowlist_review.get("grants_execution_authority") is False
                and allowlist_review.get("grants_mutation_authority") is False
            ),
            "evidence": {
                "read_only": bool(allowlist_review.get("read_only")),
                "runs_tools": bool(allowlist_review.get("runs_tools")),
                "runs_shell": bool(allowlist_review.get("runs_shell")),
                "runs_git": bool(allowlist_review.get("runs_git")),
                "grants_execution_authority": bool(allowlist_review.get("grants_execution_authority")),
                "grants_mutation_authority": bool(allowlist_review.get("grants_mutation_authority")),
            },
        },
    ]
    ready_count = sum(1 for criterion in criteria if criterion["ready"])
    review_ready = ready_count == len(criteria)
    allowlist_ready = bool(allowlist_review.get("toolbelt_allowlist_review_ready"))
    return {
        "ok": True,
        "kind": "francis.stage8.executor_substrate.branch_first_workflow_review",
        "stage": STAGE8_EXECUTOR_SUBSTRATE_STAGE,
        "status": (
            "branch_first_workflow_review_ready"
            if review_ready
            else "branch_first_workflow_review_partial"
            if allowlist_ready
            else "branch_first_workflow_review_blocked"
        ),
        "source_id": "executor_substrate",
        "target": "safe_bounded_execution",
        "branch_first_workflow_review_ready": review_ready,
        "current_git_push_boundary_reviewed": allowlist_ready,
        "branch_first_enforcement_ready": review_ready,
        "ready_count": ready_count,
        "required_count": len(criteria),
        "criteria": criteria,
        "current_workflow_compatibility": {
            "direct_on_main_supported": True,
            "source": "AGENTS.md",
            "reason": "current maintainer workflow is direct-on-main",
        },
        "toolbelt_allowlist_review": {
            "route": "/executor/substrate/toolbelt-allowlist-review",
            "status": allowlist_review.get("status", "unknown"),
            "next_smallest_truthful_gap": allowlist_review.get("next_smallest_truthful_gap", ""),
        },
        "read_only": True,
        "writes_tasks": False,
        "writes_receipts": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "branch_first_workflow_review": True,
            "uses_toolbelt_allowlist_review": True,
            "does_not_execute": True,
            "does_not_write_tasks": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_grant_authority": True,
            "preserves_current_maintainer_workflow": True,
            "requires_branch_first_opt_in_for_git_push": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (
            _STAGE8_LEASES_IDEMPOTENCY_GAP
            if review_ready
            else _STAGE8_BRANCH_FIRST_ENFORCEMENT_GAP
            if allowlist_ready
            else _STAGE8_BRANCH_FIRST_WORKFLOW_GAP
        ),
    }


def _deliverables(*, stage7_closed: bool) -> list[dict[str, Any]]:
    return [
        {
            "id": "stage7_ledger_closure_backstop",
            "label": "Stage 7 closure backstop",
            "ready": stage7_closed,
            "evidence": {
                "required_gap": _STAGE7_LEDGER_CLOSURE_GAP,
                "source_route": "/telemetry/status",
            },
        },
        {
            "id": "execution_toolbelt_inventory",
            "label": "Execution toolbelt inventory",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "known_capabilities": [
                    "chat.summarize",
                    "plan.create",
                    "plan.revise",
                    "plugin.run",
                    "plugin.tool.run",
                    "codex.supervised_exec",
                    "git.push",
                ],
            },
        },
        {
            "id": "allowlist_policy_filters",
            "label": "Allowlist and policy filters",
            "ready": True,
            "evidence": {
                "executor_allowlist": "CAPABILITY_ALLOWLIST",
                "supervised_exec_allowed_executables": "src/francis/agent/supervised_exec.py",
                "api_permission_gate": "src/francis/governance/api_permission_gate.py",
                "mutation_authority_matrix": "src/francis/api/mutation_authority_matrix.py",
            },
        },
        {
            "id": "branch_first_workflows",
            "label": "Branch-first workflows",
            "ready": True,
            "evidence": {
                "current_surface": "git.push approval-gated capability exists",
                "review_route": "/executor/substrate/branch-first-workflow-review",
                "enforcement": "opt-in branch_first_required blocks protected branches before approval",
                "receipt_kind": "git.push.branch_first_policy.receipt",
                "default_direct_on_main_preserved": True,
            },
        },
        {
            "id": "leases_and_idempotency",
            "label": "Leases and idempotency",
            "ready": False,
            "evidence": {
                "current_surface": "task lock files exist",
                "missing": "lease/idempotency receipt readback and retry contract",
            },
        },
        {
            "id": "verification_hooks",
            "label": "Verification hooks",
            "ready": False,
            "evidence": {
                "current_surface": "operation traces and artifacts exist",
                "missing": "executor-level verification hook contract",
            },
        },
    ]
