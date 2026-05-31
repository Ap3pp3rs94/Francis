from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


def _write_stage7_closure_receipt(data_root: Path, *, receipt_id: str) -> None:
    receipt_path = data_root / "logs" / "telemetry" / "stage7_operator_stage_closure_decisions.jsonl"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(
        json.dumps(
            {
                "kind": "francis.stage7.telemetry.stage7_operator_stage_closure_decision_receipt",
                "receipt_id": receipt_id,
                "decision": "close_stage7",
                "stage7_closed_by_receipt": True,
                "marks_runtime_stage_state": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_executor_substrate_status_waits_for_stage7_closure_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/executor/substrate/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage8.executor_substrate.status"
    assert body["stage"] == "Stage 8 / Executor Substrate"
    assert body["status"] == "awaiting_stage7_ledger_closure"
    assert body["stage7_closed_by_receipt"] is False
    assert body["stage7_next_smallest_truthful_gap"] != "stage7_ledger_closure"
    assert body["next_smallest_truthful_gap"] == "stage7_ledger_closure"
    assert body["stage8_done_ready"] is False
    assert body["read_only"] is True
    assert body["runs_shell"] is False
    assert body["runs_tools"] is False
    assert body["writes_tasks"] is False
    assert body["writes_receipts"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["requires_stage7_ledger_closure"] is True
    assert body["governance"]["does_not_execute"] is True
    assert body["governance"]["does_not_grant_authority"] is True
    assert not data_root.exists()


def test_executor_substrate_status_starts_readonly_after_stage7_closure_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage7_closure_receipt(data_root, receipt_id="tel_stage7_closure_executor_substrate")

    body = TestClient(create_app()).get("/executor/substrate/status").json()

    assert body["ok"] is True
    assert body["status"] == "substrate_contract_ready"
    assert body["stage7_closed_by_receipt"] is True
    assert body["stage7_next_smallest_truthful_gap"] == "stage7_ledger_closure"
    assert body["next_smallest_truthful_gap"] == "stage8_substrate_scope_enforcement_review"
    assert body["stage8_done_ready"] is False
    assert body["ready_count"] == 6
    assert body["required_count"] == 7
    deliverables = {item["id"]: item for item in body["deliverables"]}
    assert set(deliverables) == {
        "stage7_ledger_closure_backstop",
        "execution_toolbelt_inventory",
        "allowlist_policy_filters",
        "branch_first_workflows",
        "leases_and_idempotency",
        "verification_hooks",
        "substrate_scope_enforcement",
    }
    assert deliverables["stage7_ledger_closure_backstop"]["ready"] is True
    assert deliverables["execution_toolbelt_inventory"]["ready"] is True
    assert "codex.supervised_exec" in deliverables["execution_toolbelt_inventory"]["evidence"]["known_capabilities"]
    assert deliverables["allowlist_policy_filters"]["ready"] is True
    assert deliverables["branch_first_workflows"]["ready"] is True
    assert deliverables["branch_first_workflows"]["evidence"]["receipt_kind"] == (
        "git.push.branch_first_policy.receipt"
    )
    assert deliverables["leases_and_idempotency"]["ready"] is True
    assert deliverables["leases_and_idempotency"]["evidence"]["review_route"] == (
        "/executor/substrate/leases-idempotency-review"
    )
    assert "bounded retry contract" in deliverables["leases_and_idempotency"]["evidence"]["ready_surfaces"]
    assert deliverables["verification_hooks"]["ready"] is True
    assert deliverables["verification_hooks"]["evidence"]["receipt_kind"] == "executor.verification.receipt"
    assert deliverables["substrate_scope_enforcement"]["ready"] is False
    assert body["read_only"] is True
    assert body["writes_tasks"] is False
    assert body["writes_receipts"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["stage8_posture_contract"] is True
    assert body["governance"]["uses_stage7_telemetry_receipt_readback"] is True


def test_executor_toolbelt_allowlist_review_advances_after_stage8_status_ready(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage7_closure_receipt(data_root, receipt_id="tel_stage7_closure_toolbelt_allowlist")

    body = TestClient(create_app()).get("/executor/substrate/toolbelt-allowlist-review").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage8.executor_substrate.toolbelt_allowlist_review"
    assert body["stage"] == "Stage 8 / Executor Substrate"
    assert body["status"] == "toolbelt_allowlist_review_ready"
    assert body["toolbelt_allowlist_review_ready"] is True
    assert body["ready_count"] == body["required_count"] == 4
    assert [item["id"] for item in body["criteria"]] == [
        "substrate_contract_ready",
        "toolbelt_inventory_readback",
        "allowlist_policy_filter_readback",
        "non_authorizing_review_guard",
    ]
    assert all(item["ready"] is True for item in body["criteria"])
    assert "codex.supervised_exec" in body["known_capabilities"]
    assert "git.push" in body["known_capabilities"]
    assert body["substrate_status"]["status"] == "substrate_contract_ready"
    assert body["read_only"] is True
    assert body["writes_tasks"] is False
    assert body["writes_receipts"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["toolbelt_allowlist_review"] is True
    assert body["governance"]["does_not_execute"] is True
    assert body["governance"]["does_not_grant_authority"] is True
    assert body["next_smallest_truthful_gap"] == "stage8_branch_first_workflow_review"


def test_executor_branch_first_workflow_review_projects_current_git_push_boundaries(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage7_closure_receipt(data_root, receipt_id="tel_stage7_closure_branch_first_review")

    body = TestClient(create_app()).get("/executor/substrate/branch-first-workflow-review").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage8.executor_substrate.branch_first_workflow_review"
    assert body["stage"] == "Stage 8 / Executor Substrate"
    assert body["status"] == "branch_first_workflow_review_ready"
    assert body["branch_first_workflow_review_ready"] is True
    assert body["current_git_push_boundary_reviewed"] is True
    assert body["branch_first_enforcement_ready"] is True
    assert body["ready_count"] == 8
    assert body["required_count"] == 8

    criteria = {item["id"]: item for item in body["criteria"]}
    assert list(criteria) == [
        "toolbelt_allowlist_review_ready",
        "exact_current_branch_binding",
        "detached_head_blocked",
        "approval_gated_execution",
        "stale_or_mismatched_approval_refresh",
        "branch_first_enforcement_policy",
        "branch_first_policy_receipt_readback",
        "non_authorizing_review_guard",
    ]
    assert criteria["toolbelt_allowlist_review_ready"]["ready"] is True
    assert criteria["exact_current_branch_binding"]["ready"] is True
    assert criteria["exact_current_branch_binding"]["evidence"]["denial_error"] == "branch_mismatch"
    assert criteria["detached_head_blocked"]["ready"] is True
    assert criteria["detached_head_blocked"]["evidence"]["denial_error"] == "detached_head_not_supported"
    assert criteria["approval_gated_execution"]["evidence"]["gate"] == "approvals_gate"
    assert criteria["stale_or_mismatched_approval_refresh"]["evidence"]["mismatch_error"] == (
        "approval_payload_mismatch"
    )
    assert criteria["branch_first_enforcement_policy"]["ready"] is True
    assert criteria["branch_first_enforcement_policy"]["evidence"]["current_maintainer_workflow"] == "direct_on_main"
    assert criteria["branch_first_enforcement_policy"]["evidence"]["protected_branch_error"] == (
        "branch_first_workflow_required"
    )
    assert criteria["branch_first_policy_receipt_readback"]["ready"] is True
    assert criteria["branch_first_policy_receipt_readback"]["evidence"]["receipt_kind"] == (
        "git.push.branch_first_policy.receipt"
    )
    assert criteria["non_authorizing_review_guard"]["ready"] is True

    assert body["current_workflow_compatibility"]["direct_on_main_supported"] is True
    assert body["toolbelt_allowlist_review"]["status"] == "toolbelt_allowlist_review_ready"
    assert body["read_only"] is True
    assert body["writes_tasks"] is False
    assert body["writes_receipts"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["branch_first_workflow_review"] is True
    assert body["governance"]["does_not_execute"] is True
    assert body["governance"]["preserves_current_maintainer_workflow"] is True
    assert body["governance"]["requires_branch_first_opt_in_for_git_push"] is True
    assert body["next_smallest_truthful_gap"] == "stage8_leases_idempotency_review"


def test_executor_leases_idempotency_review_projects_ready_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage7_closure_receipt(data_root, receipt_id="tel_stage7_closure_leases_idempotency")

    body = TestClient(create_app()).get("/executor/substrate/leases-idempotency-review").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage8.executor_substrate.leases_idempotency_review"
    assert body["stage"] == "Stage 8 / Executor Substrate"
    assert body["status"] == "leases_idempotency_review_ready"
    assert body["leases_idempotency_review_ready"] is True
    assert body["lock_file_contract_ready"] is True
    assert body["ttl_expiration_contract_ready"] is True
    assert body["idempotency_key_propagation_ready"] is True
    assert body["idempotency_dedup_enforcement_ready"] is True
    assert body["lease_receipt_readback_ready"] is True
    assert body["bounded_retry_contract_ready"] is True
    assert body["ready_count"] == 8
    assert body["required_count"] == 8

    criteria = {item["id"]: item for item in body["criteria"]}
    assert list(criteria) == [
        "branch_first_workflow_review_ready",
        "task_lock_file_contract",
        "ttl_expiration_contract",
        "idempotency_key_propagation",
        "idempotency_dedup_enforcement",
        "lease_receipt_readback",
        "bounded_retry_contract",
        "non_authorizing_review_guard",
    ]
    assert criteria["branch_first_workflow_review_ready"]["ready"] is True
    assert criteria["task_lock_file_contract"]["evidence"]["lock_filename"] == ".lock"
    assert criteria["ttl_expiration_contract"]["evidence"]["status_reason"] == "expired_ttl"
    assert criteria["idempotency_key_propagation"]["evidence"]["stored_input_key"] == "idempotency_key"
    assert criteria["idempotency_dedup_enforcement"]["ready"] is True
    assert criteria["idempotency_dedup_enforcement"]["evidence"]["current_surface"] == (
        "duplicate operation creation returns existing operation"
    )
    assert criteria["idempotency_dedup_enforcement"]["evidence"]["audit_event"] == "idempotency_reused"
    assert criteria["lease_receipt_readback"]["ready"] is True
    assert criteria["lease_receipt_readback"]["evidence"]["receipt_kind"] == "executor.lease.receipt"
    assert criteria["bounded_retry_contract"]["ready"] is True
    assert criteria["bounded_retry_contract"]["evidence"]["receipt_kind"] == "executor.retry_budget.receipt"
    assert criteria["bounded_retry_contract"]["evidence"]["hidden_retry"] is False
    assert criteria["bounded_retry_contract"]["evidence"]["retry_started"] is False
    assert criteria["bounded_retry_contract"]["evidence"]["retry_authority"] is False
    assert criteria["non_authorizing_review_guard"]["ready"] is True

    assert body["branch_first_workflow_review"]["status"] == "branch_first_workflow_review_ready"
    assert body["read_only"] is True
    assert body["writes_tasks"] is False
    assert body["writes_receipts"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["leases_idempotency_review"] is True
    assert body["governance"]["does_not_execute"] is True
    assert body["governance"]["does_not_grant_authority"] is True
    assert body["next_smallest_truthful_gap"] == "stage8_verification_hooks_review"


def test_executor_verification_hooks_review_projects_receipt_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage7_closure_receipt(data_root, receipt_id="tel_stage7_closure_verification_hooks")

    body = TestClient(create_app()).get("/executor/substrate/verification-hooks-review").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage8.executor_substrate.verification_hooks_review"
    assert body["stage"] == "Stage 8 / Executor Substrate"
    assert body["status"] == "verification_hooks_review_ready"
    assert body["verification_hooks_review_ready"] is True
    assert body["execution_handle_contract_ready"] is True
    assert body["operation_projection_contract_ready"] is True
    assert body["verification_receipt_contract_ready"] is True
    assert body["completion_claim_guard_ready"] is True
    assert body["ready_count"] == body["required_count"] == 6

    criteria = {item["id"]: item for item in body["criteria"]}
    assert list(criteria) == [
        "leases_idempotency_review_ready",
        "execution_handle_contract",
        "operation_projection_contract",
        "verification_receipt_contract",
        "completion_claim_guard",
        "non_authorizing_review_guard",
    ]
    assert criteria["leases_idempotency_review_ready"]["ready"] is True
    assert criteria["execution_handle_contract"]["evidence"]["trace_id_function"] == "_attach_execution_handles"
    assert criteria["operation_projection_contract"]["evidence"]["projected_handles"] == [
        "trace_id",
        "run_id",
        "artifact_dir",
    ]
    assert criteria["verification_receipt_contract"]["evidence"]["receipt_kind"] == "executor.verification.receipt"
    assert criteria["completion_claim_guard"]["evidence"]["default_without_explicit_verification"] == "not_run"
    assert criteria["completion_claim_guard"]["evidence"]["hidden_verification"] is False
    assert criteria["non_authorizing_review_guard"]["ready"] is True

    assert body["leases_idempotency_review"]["status"] == "leases_idempotency_review_ready"
    assert body["read_only"] is True
    assert body["writes_tasks"] is False
    assert body["writes_receipts"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["verification_hooks_review"] is True
    assert body["governance"]["requires_explicit_verification_for_completion_claim"] is True
    assert body["governance"]["hidden_verification"] is False
    assert body["governance"]["does_not_execute"] is True
    assert body["governance"]["does_not_grant_authority"] is True
    assert body["next_smallest_truthful_gap"] == "stage8_substrate_scope_enforcement_review"
