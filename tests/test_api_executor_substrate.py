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
    assert body["next_smallest_truthful_gap"] == "stage8_leases_idempotency_review"
    assert body["stage8_done_ready"] is False
    assert body["ready_count"] == 4
    assert body["required_count"] == 6
    deliverables = {item["id"]: item for item in body["deliverables"]}
    assert set(deliverables) == {
        "stage7_ledger_closure_backstop",
        "execution_toolbelt_inventory",
        "allowlist_policy_filters",
        "branch_first_workflows",
        "leases_and_idempotency",
        "verification_hooks",
    }
    assert deliverables["stage7_ledger_closure_backstop"]["ready"] is True
    assert deliverables["execution_toolbelt_inventory"]["ready"] is True
    assert "codex.supervised_exec" in deliverables["execution_toolbelt_inventory"]["evidence"]["known_capabilities"]
    assert deliverables["allowlist_policy_filters"]["ready"] is True
    assert deliverables["branch_first_workflows"]["ready"] is True
    assert deliverables["branch_first_workflows"]["evidence"]["receipt_kind"] == (
        "git.push.branch_first_policy.receipt"
    )
    assert deliverables["leases_and_idempotency"]["ready"] is False
    assert deliverables["verification_hooks"]["ready"] is False
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
