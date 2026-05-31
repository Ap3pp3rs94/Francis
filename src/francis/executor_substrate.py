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
_STAGE8_IDEMPOTENCY_DEDUP_GAP = "stage8_idempotency_dedup_enforcement"
_STAGE8_LEASE_RECEIPT_GAP = "stage8_lease_receipt_readback"
_STAGE8_BOUNDED_RETRY_GAP = "stage8_bounded_retry_contract"
_STAGE8_VERIFICATION_HOOKS_GAP = "stage8_verification_hooks_review"
_STAGE8_SCOPE_ENFORCEMENT_GAP = "stage8_substrate_scope_enforcement_review"
_STAGE8_LEDGER_CLOSURE_GAP = "stage8_ledger_closure"


def executor_substrate_status_snapshot() -> dict[str, Any]:
    telemetry = telemetry_status_snapshot()
    stage7_closed = telemetry.get("next_smallest_truthful_gap") == _STAGE7_LEDGER_CLOSURE_GAP
    deliverables = _deliverables(stage7_closed=stage7_closed)
    ready_count = sum(1 for item in deliverables if item["ready"])
    stage8_ready = stage7_closed and ready_count == len(deliverables)
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
        "stage8_done_ready": stage8_ready,
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
        "next_smallest_truthful_gap": (
            _STAGE8_LEDGER_CLOSURE_GAP
            if stage8_ready
            else _STAGE8_SCOPE_ENFORCEMENT_GAP
            if stage7_closed
            else _STAGE7_LEDGER_CLOSURE_GAP
        ),
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


def executor_leases_idempotency_review_snapshot() -> dict[str, Any]:
    branch_review = executor_branch_first_workflow_review_snapshot()
    criteria = [
        {
            "id": "branch_first_workflow_review_ready",
            "ready": bool(branch_review.get("branch_first_workflow_review_ready")),
            "evidence": {
                "route": "/executor/substrate/branch-first-workflow-review",
                "status": branch_review.get("status", "unknown"),
            },
        },
        {
            "id": "task_lock_file_contract",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "lock_filename": ".lock",
                "lock_function": "_try_acquire_lock",
                "stale_seconds": 3600,
            },
        },
        {
            "id": "ttl_expiration_contract",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "status_reason": "expired_ttl",
                "max_ttl_source": "src/francis/agent/delegation.py",
                "max_ttl_seconds": 604800,
            },
        },
        {
            "id": "idempotency_key_propagation",
            "ready": True,
            "evidence": {
                "source": "src/francis/operations/runtime.py",
                "api_field": "OperationCreateIn.idempotency_key",
                "stored_input_key": "idempotency_key",
                "plugin_forwarding": "plugin.run and plugin.tool.run",
            },
        },
        {
            "id": "idempotency_dedup_enforcement",
            "ready": True,
            "evidence": {
                "source": "src/francis/operations/runtime.py",
                "current_surface": "duplicate operation creation returns existing operation",
                "match_scope": "requester_id + capability + idempotency_key",
                "audit_event": "idempotency_reused",
                "duplicate_create_blocked": True,
            },
        },
        {
            "id": "lease_receipt_readback",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "receipt_kind": "executor.lease.receipt",
                "receipt_dir": "data/artifacts/executor_lease_receipts",
                "decisions": ["acquired", "denied", "reclaimed", "released"],
                "current_surface": "lock acquire, deny, stale reclaim, and release receipts",
            },
        },
        {
            "id": "bounded_retry_contract",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "receipt_kind": "executor.retry_budget.receipt",
                "receipt_dir": "data/artifacts/executor_retry_receipts",
                "current_surface": "failed task records attempts, max_attempts, retry_exhausted, and retry_started=false",
                "max_attempts_clamp": "1..5",
                "hidden_retry": False,
                "retry_started": False,
                "retry_authority": False,
            },
        },
        {
            "id": "non_authorizing_review_guard",
            "ready": (
                branch_review.get("read_only") is True
                and branch_review.get("runs_tools") is False
                and branch_review.get("runs_shell") is False
                and branch_review.get("runs_git") is False
                and branch_review.get("grants_execution_authority") is False
                and branch_review.get("grants_mutation_authority") is False
            ),
            "evidence": {
                "read_only": bool(branch_review.get("read_only")),
                "runs_tools": bool(branch_review.get("runs_tools")),
                "runs_shell": bool(branch_review.get("runs_shell")),
                "runs_git": bool(branch_review.get("runs_git")),
                "grants_execution_authority": bool(branch_review.get("grants_execution_authority")),
                "grants_mutation_authority": bool(branch_review.get("grants_mutation_authority")),
            },
        },
    ]
    ready_count = sum(1 for criterion in criteria if criterion["ready"])
    review_ready = ready_count == len(criteria)
    branch_ready = bool(branch_review.get("branch_first_workflow_review_ready"))
    return {
        "ok": True,
        "kind": "francis.stage8.executor_substrate.leases_idempotency_review",
        "stage": STAGE8_EXECUTOR_SUBSTRATE_STAGE,
        "status": (
            "leases_idempotency_review_ready"
            if review_ready
            else "leases_idempotency_review_partial"
            if branch_ready
            else "leases_idempotency_review_blocked"
        ),
        "source_id": "executor_substrate",
        "target": "safe_bounded_execution",
        "leases_idempotency_review_ready": review_ready,
        "lock_file_contract_ready": True,
        "ttl_expiration_contract_ready": True,
        "idempotency_key_propagation_ready": True,
        "idempotency_dedup_enforcement_ready": True,
        "lease_receipt_readback_ready": True,
        "bounded_retry_contract_ready": True,
        "ready_count": ready_count,
        "required_count": len(criteria),
        "criteria": criteria,
        "branch_first_workflow_review": {
            "route": "/executor/substrate/branch-first-workflow-review",
            "status": branch_review.get("status", "unknown"),
            "next_smallest_truthful_gap": branch_review.get("next_smallest_truthful_gap", ""),
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
            "leases_idempotency_review": True,
            "uses_branch_first_workflow_review": True,
            "does_not_execute": True,
            "does_not_write_tasks": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_grant_authority": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (_STAGE8_VERIFICATION_HOOKS_GAP if review_ready else _STAGE8_BOUNDED_RETRY_GAP),
    }


def executor_verification_hooks_review_snapshot() -> dict[str, Any]:
    leases_review = executor_leases_idempotency_review_snapshot()
    criteria = [
        {
            "id": "leases_idempotency_review_ready",
            "ready": bool(leases_review.get("leases_idempotency_review_ready")),
            "evidence": {
                "route": "/executor/substrate/leases-idempotency-review",
                "status": leases_review.get("status", "unknown"),
            },
        },
        {
            "id": "execution_handle_contract",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "trace_id_function": "_attach_execution_handles",
                "run_id_function": "_attach_execution_handles",
                "audit_reference_function": "_payload_audit_references",
            },
        },
        {
            "id": "operation_projection_contract",
            "ready": True,
            "evidence": {
                "source": "src/francis/operations/runtime.py",
                "projected_handles": ["trace_id", "run_id", "artifact_dir"],
                "supports_filters": ["trace_id", "run_id", "artifact_dir"],
            },
        },
        {
            "id": "verification_receipt_contract",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "receipt_kind": "executor.verification.receipt",
                "receipt_dir": "data/artifacts/executor_verification_receipts",
                "result_field": "verification_receipt",
            },
        },
        {
            "id": "completion_claim_guard",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "contract": "completion_claim_allowed requires an explicit passed verification status",
                "default_without_explicit_verification": "not_run",
                "hidden_verification": False,
            },
        },
        {
            "id": "non_authorizing_review_guard",
            "ready": (
                leases_review.get("read_only") is True
                and leases_review.get("runs_tools") is False
                and leases_review.get("runs_shell") is False
                and leases_review.get("runs_git") is False
                and leases_review.get("grants_execution_authority") is False
                and leases_review.get("grants_mutation_authority") is False
            ),
            "evidence": {
                "read_only": bool(leases_review.get("read_only")),
                "runs_tools": bool(leases_review.get("runs_tools")),
                "runs_shell": bool(leases_review.get("runs_shell")),
                "runs_git": bool(leases_review.get("runs_git")),
                "grants_execution_authority": bool(leases_review.get("grants_execution_authority")),
                "grants_mutation_authority": bool(leases_review.get("grants_mutation_authority")),
            },
        },
    ]
    ready_count = sum(1 for criterion in criteria if criterion["ready"])
    review_ready = ready_count == len(criteria)
    leases_ready = bool(leases_review.get("leases_idempotency_review_ready"))
    return {
        "ok": True,
        "kind": "francis.stage8.executor_substrate.verification_hooks_review",
        "stage": STAGE8_EXECUTOR_SUBSTRATE_STAGE,
        "status": (
            "verification_hooks_review_ready"
            if review_ready
            else "verification_hooks_review_partial"
            if leases_ready
            else "verification_hooks_review_blocked"
        ),
        "source_id": "executor_substrate",
        "target": "safe_bounded_execution",
        "verification_hooks_review_ready": review_ready,
        "execution_handle_contract_ready": True,
        "operation_projection_contract_ready": True,
        "verification_receipt_contract_ready": True,
        "completion_claim_guard_ready": True,
        "ready_count": ready_count,
        "required_count": len(criteria),
        "criteria": criteria,
        "leases_idempotency_review": {
            "route": "/executor/substrate/leases-idempotency-review",
            "status": leases_review.get("status", "unknown"),
            "next_smallest_truthful_gap": leases_review.get("next_smallest_truthful_gap", ""),
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
            "verification_hooks_review": True,
            "uses_leases_idempotency_review": True,
            "does_not_execute": True,
            "does_not_write_tasks": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_grant_authority": True,
            "requires_explicit_verification_for_completion_claim": True,
            "hidden_verification": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (
            _STAGE8_SCOPE_ENFORCEMENT_GAP if review_ready else _STAGE8_VERIFICATION_HOOKS_GAP
        ),
    }


def executor_substrate_scope_enforcement_review_snapshot(
    *,
    mutating_route_authority_matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verification_review = executor_verification_hooks_review_snapshot()
    matrix = mutating_route_authority_matrix if isinstance(mutating_route_authority_matrix, dict) else {}
    matrix_ready = matrix.get("ok") is True and int(matrix.get("missing_total") or 0) == 0
    matrix_total = int(matrix.get("total") or 0)
    criteria = [
        {
            "id": "verification_hooks_review_ready",
            "ready": bool(verification_review.get("verification_hooks_review_ready")),
            "evidence": {
                "route": "/executor/substrate/verification-hooks-review",
                "status": verification_review.get("status", "unknown"),
            },
        },
        {
            "id": "executor_capability_allowlist",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "contract": "run_capability rejects capabilities outside CAPABILITY_ALLOWLIST",
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
            "id": "supervised_exec_scope_boundary",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/supervised_exec.py",
                "allowed_executables": "_ALLOWED_EXECUTABLES",
                "forbidden_command_tokens": "_FORBIDDEN_COMMAND_TOKENS",
                "cwd_root_check": "_path_is_under",
                "approval_gate": "codex.supervised_exec",
            },
        },
        {
            "id": "api_permission_gate",
            "ready": True,
            "evidence": {
                "source": "src/francis/governance/api_permission_gate.py",
                "default_denial_reasons": ["missing_actor", "missing_scopes", "empty_required_scopes"],
                "redacts_scope_names": True,
            },
        },
        {
            "id": "mutating_route_authority_matrix",
            "ready": matrix_ready,
            "evidence": {
                "source": "src/francis/api/mutation_authority_matrix.py",
                "route": "/system/mutating-route-authority-matrix",
                "status": matrix.get("status", "not_loaded"),
                "total": matrix_total,
                "missing_total": int(matrix.get("missing_total") or 0),
            },
        },
        {
            "id": "branch_first_scope_boundary",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/git_push.py",
                "protected_branch_error": "branch_first_workflow_required",
                "detached_head_error": "detached_head_not_supported",
                "approval_payload_mismatch_error": "approval_payload_mismatch",
            },
        },
        {
            "id": "non_authorizing_review_guard",
            "ready": (
                verification_review.get("read_only") is True
                and verification_review.get("runs_tools") is False
                and verification_review.get("runs_shell") is False
                and verification_review.get("runs_git") is False
                and verification_review.get("grants_execution_authority") is False
                and verification_review.get("grants_mutation_authority") is False
            ),
            "evidence": {
                "read_only": bool(verification_review.get("read_only")),
                "runs_tools": bool(verification_review.get("runs_tools")),
                "runs_shell": bool(verification_review.get("runs_shell")),
                "runs_git": bool(verification_review.get("runs_git")),
                "grants_execution_authority": bool(verification_review.get("grants_execution_authority")),
                "grants_mutation_authority": bool(verification_review.get("grants_mutation_authority")),
            },
        },
    ]
    ready_count = sum(1 for criterion in criteria if criterion["ready"])
    review_ready = ready_count == len(criteria)
    verification_ready = bool(verification_review.get("verification_hooks_review_ready"))
    return {
        "ok": True,
        "kind": "francis.stage8.executor_substrate.scope_enforcement_review",
        "stage": STAGE8_EXECUTOR_SUBSTRATE_STAGE,
        "status": (
            "scope_enforcement_review_ready"
            if review_ready
            else "scope_enforcement_review_partial"
            if verification_ready
            else "scope_enforcement_review_blocked"
        ),
        "source_id": "executor_substrate",
        "target": "safe_bounded_execution",
        "scope_enforcement_review_ready": review_ready,
        "executor_capability_allowlist_ready": True,
        "supervised_exec_scope_boundary_ready": True,
        "api_permission_gate_ready": True,
        "mutating_route_authority_matrix_ready": matrix_ready,
        "branch_first_scope_boundary_ready": True,
        "ready_count": ready_count,
        "required_count": len(criteria),
        "criteria": criteria,
        "verification_hooks_review": {
            "route": "/executor/substrate/verification-hooks-review",
            "status": verification_review.get("status", "unknown"),
            "next_smallest_truthful_gap": verification_review.get("next_smallest_truthful_gap", ""),
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
            "scope_enforcement_review": True,
            "uses_verification_hooks_review": True,
            "uses_mutating_route_authority_matrix": bool(matrix),
            "does_not_execute": True,
            "does_not_write_tasks": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_grant_authority": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": _STAGE8_LEDGER_CLOSURE_GAP if review_ready else _STAGE8_SCOPE_ENFORCEMENT_GAP,
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
            "ready": True,
            "evidence": {
                "current_surface": "task lock files exist",
                "review_route": "/executor/substrate/leases-idempotency-review",
                "ready_surfaces": [
                    "task lock file contract",
                    "ttl expiration contract",
                    "idempotency key propagation",
                    "idempotency dedup enforcement",
                    "lease receipt readback",
                    "bounded retry contract",
                ],
            },
        },
        {
            "id": "verification_hooks",
            "label": "Verification hooks",
            "ready": True,
            "evidence": {
                "current_surface": "operation traces, artifacts, and executor verification receipts exist",
                "review_route": "/executor/substrate/verification-hooks-review",
                "receipt_kind": "executor.verification.receipt",
                "completion_claim_guard": "explicit passed verification required",
            },
        },
        {
            "id": "substrate_scope_enforcement",
            "label": "Substrate scope enforcement",
            "ready": True,
            "evidence": {
                "current_surface": "capability allowlist, permission gates, command boundaries, and route authority matrix exist",
                "review_route": "/executor/substrate/scope-enforcement-review",
                "matrix_route": "/system/mutating-route-authority-matrix",
            },
        },
    ]
