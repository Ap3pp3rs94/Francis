from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


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
    receipt_path = data_root / "logs" / "telemetry" / "stage7_operator_stage_closure_decisions.jsonl"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(
        json.dumps(
            {
                "kind": "francis.stage7.telemetry.stage7_operator_stage_closure_decision_receipt",
                "receipt_id": "tel_stage7_closure_executor_substrate",
                "decision": "close_stage7",
                "stage7_closed_by_receipt": True,
                "marks_runtime_stage_state": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    body = TestClient(create_app()).get("/executor/substrate/status").json()

    assert body["ok"] is True
    assert body["status"] == "substrate_contract_ready"
    assert body["stage7_closed_by_receipt"] is True
    assert body["stage7_next_smallest_truthful_gap"] == "stage7_ledger_closure"
    assert body["next_smallest_truthful_gap"] == "stage8_executor_toolbelt_allowlist_review"
    assert body["stage8_done_ready"] is False
    assert body["ready_count"] == 3
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
    assert deliverables["branch_first_workflows"]["ready"] is False
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
