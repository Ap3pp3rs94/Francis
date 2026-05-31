from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


def _write_stage8_closure_receipt(data_root: Path, *, receipt_id: str = "exec_stage8_closure_test") -> None:
    path = data_root / "logs" / "executor_substrate" / "stage8_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "francis.stage8.executor_substrate.stage8_operator_stage_closure_decision_receipt",
                "receipt_id": receipt_id,
                "stage": "Stage 8 / Executor Substrate",
                "source_id": "executor_substrate",
                "target": "stage8_executor_substrate",
                "actor": "test.operator",
                "decision": "close_stage8",
                "scope_enforcement_review_ready": True,
                "stage8_closed_by_receipt": True,
                "recorded_ts": 1_800_000_000,
                "governance": {
                    "explicit_operator_decision": True,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _receipt_path(data_root: Path, name: str) -> Path:
    return data_root / "logs" / "takeover" / name


def test_takeover_status_blocks_without_stage8_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/takeover/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage9.takeover.status"
    assert body["status"] == "blocked"
    assert body["stage8_closed_by_receipt"] is False
    assert body["control_transfer_ready"] is False
    assert body["control_transfer_active"] is False
    assert body["panic_stop_ready"] is False
    assert body["operator_surface_contract_ready"] is False
    assert body["operator_surface_contract_route"] == "/takeover/operator-surface-contract"
    assert body["writes_receipts"] is False
    assert body["writes_tasks"] is False
    assert body["runs_shell"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["takeover_never_implicit"] is True
    assert body["next_smallest_truthful_gap"] == "stage8_ledger_closure"
    assert not _receipt_path(data_root, "control_transfer_receipts.jsonl").exists()


def test_takeover_control_transfer_denies_without_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage8_closure_receipt(data_root)

    response = TestClient(create_app()).post(
        "/takeover/control-transfer",
        json={
            "actor": "test.takeover",
            "reason": "pilot control transfer",
            "scope": "bounded stage9 pilot",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["writes_receipt"] is False
    assert body["writes_tasks"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["required_scope"] == "takeover.control.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert not _receipt_path(data_root, "control_transfer_receipts.jsonl").exists()


def test_takeover_control_transfer_receipt_and_panic_stop_are_auditable(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                "codex.builder": [
                    "takeover.control.write",
                    "takeover.panic.write",
                    "takeover.handback.write",
                ],
            }
        ),
    )
    _write_stage8_closure_receipt(data_root, receipt_id="exec_stage8_closure_takeover_test")

    client = TestClient(create_app())
    transfer = client.post(
        "/takeover/control-transfer",
        json={
            "actor": "codex.builder",
            "reason": "stage9 pilot transfer token=takeoversecret123",
            "scope": "bounded proof script execution token=takeoverscopesecret123",
            "mission_id": "msn_stage9_takeover",
        },
    )

    assert transfer.status_code == 200
    transfer_body = transfer.json()
    assert transfer_body["ok"] is True
    assert transfer_body["status"] == "recorded"
    assert transfer_body["writes_receipt"] is True
    assert transfer_body["writes_tasks"] is False
    assert transfer_body["writes_memory"] is False
    assert transfer_body["runs_tools"] is False
    assert transfer_body["runs_shell"] is False
    assert transfer_body["runs_git"] is False
    assert transfer_body["grants_execution_authority"] is False
    assert transfer_body["grants_mutation_authority"] is False
    assert transfer_body["control_transfer_active"] is True
    assert transfer_body["next_smallest_truthful_gap"] == "stage9_handback_summary_receipts"

    receipt = transfer_body["receipt"]
    assert receipt["kind"] == "francis.stage9.takeover.control_transfer_receipt"
    assert receipt["receipt_id"] == transfer_body["receipt_id"]
    assert receipt["actor"] == "codex.builder"
    assert receipt["stage8_closure_receipt_id"] == "exec_stage8_closure_takeover_test"
    assert receipt["stage8_closed_by_receipt"] is True
    assert receipt["control_transfer_active"] is True
    assert receipt["pilot_indicator_visible"] is True
    assert receipt["panic_stop_route"] == "/takeover/panic-stop"
    assert receipt["handback_required"] is True
    assert receipt["governance"]["required_scope"] == "takeover.control.write"
    assert receipt["governance"]["explicit_control_transfer"] is True
    assert receipt["governance"]["execution_still_uses_executor_governance"] is True
    assert receipt["governance"]["grants_execution_authority"] is False
    assert receipt["governance"]["grants_mutation_authority"] is False

    transfer_text = json.dumps(receipt, sort_keys=True)
    assert "takeoversecret123" not in transfer_text
    assert "takeoverscopesecret123" not in transfer_text

    status = client.get("/takeover/status").json()
    assert status["status"] == "pilot_active"
    assert status["control_mode"]["id"] == "pilot"
    assert status["pilot_indicator_visible"] is True
    assert status["control_transfer_active"] is True
    assert status["active_session_id"] == transfer_body["session_id"]
    assert status["panic_stop_ready"] is True
    assert status["handback_required"] is True
    assert status["deliverables"]["control_transfer_flow"] is True
    assert status["deliverables"]["live_action_feed"] is True
    assert status["deliverables"]["panic_stop"] is False
    assert status["deliverables"]["handback_summary"] is False

    panic = client.post(
        "/takeover/panic-stop",
        json={
            "actor": "codex.builder",
            "reason": "operator panic token=panicsecret123",
        },
    )

    assert panic.status_code == 200
    panic_body = panic.json()
    assert panic_body["ok"] is True
    assert panic_body["status"] == "recorded"
    assert panic_body["writes_receipt"] is True
    assert panic_body["revoked_control_transfer"] is True
    assert panic_body["writes_tasks"] is False
    assert panic_body["runs_shell"] is False
    assert panic_body["grants_execution_authority"] is False
    assert panic_body["session_id"] == transfer_body["session_id"]

    panic_receipt = panic_body["receipt"]
    assert panic_receipt["kind"] == "francis.stage9.takeover.panic_stop_receipt"
    assert panic_receipt["latest_control_transfer_receipt_id"] == transfer_body["receipt_id"]
    assert panic_receipt["control_mode_after"] == "assist"
    assert panic_receipt["revoked_control_transfer"] is True
    assert panic_receipt["cancels_operations"] is False
    assert panic_receipt["governance"]["required_scope"] == "takeover.panic.write"
    assert panic_receipt["governance"]["revokes_pilot_control_mode"] is True
    assert panic_receipt["governance"]["grants_execution_authority"] is False
    assert "panicsecret123" not in json.dumps(panic_receipt, sort_keys=True)

    final_status = client.get("/takeover/status").json()
    assert final_status["control_mode"]["id"] == "assist"
    assert final_status["control_transfer_active"] is False
    assert final_status["panic_stop_ready"] is False
    assert final_status["latest_panic_stop_receipt"]["receipt_id"] == panic_body["receipt_id"]
    assert final_status["deliverables"]["panic_stop"] is True
    assert final_status["deliverables"]["handback_summary"] is False

    handback = client.post(
        "/takeover/handback-summary",
        json={
            "actor": "codex.builder",
            "reason": "operator handback token=handbackreasonsecret123",
            "summary": "Pilot returned control after proof check token=handbacksummarysecret123",
            "validation_outcome": "targeted takeover tests passed",
            "remaining_uncertainty": "CI not checked in this unit test",
            "next_recommendation": "review operator surface",
        },
    )

    assert handback.status_code == 200
    handback_body = handback.json()
    assert handback_body["ok"] is True
    assert handback_body["status"] == "recorded"
    assert handback_body["writes_receipt"] is True
    assert handback_body["control_transferred_back"] is True
    assert handback_body["writes_tasks"] is False
    assert handback_body["writes_memory"] is False
    assert handback_body["runs_tools"] is False
    assert handback_body["runs_shell"] is False
    assert handback_body["grants_execution_authority"] is False

    handback_receipt = handback_body["receipt"]
    assert handback_receipt["kind"] == "francis.stage9.takeover.handback_summary_receipt"
    assert handback_receipt["control_transfer_receipt_id"] == transfer_body["receipt_id"]
    assert handback_receipt["panic_stop_receipt_id"] == panic_body["receipt_id"]
    assert handback_receipt["control_transferred_back"] is True
    assert handback_receipt["control_mode_after"] == "assist"
    assert handback_receipt["was_active_at_handback"] is False
    assert handback_receipt["governance"]["required_scope"] == "takeover.handback.write"
    assert handback_receipt["governance"]["requires_control_transfer_receipt"] is True
    assert handback_receipt["governance"]["proof_handles_included"] is True
    assert handback_receipt["governance"]["grants_execution_authority"] is False
    handback_text = json.dumps(handback_receipt, sort_keys=True)
    assert "handbackreasonsecret123" not in handback_text
    assert "handbacksummarysecret123" not in handback_text

    handback_status = client.get("/takeover/status").json()
    assert handback_status["control_mode"]["id"] == "assist"
    assert handback_status["control_transfer_active"] is False
    assert handback_status["handback_summary_ready"] is True
    assert handback_status["latest_handback_summary_receipt"]["receipt_id"] == handback_body["receipt_id"]
    assert handback_status["deliverables"]["handback_summary"] is True
    assert handback_status["operator_surface_contract_ready"] is True
    assert handback_status["operator_surface_contract_route"] == "/takeover/operator-surface-contract"
    assert handback_status["next_smallest_truthful_gap"] == "stage9_panic_operation_cancellation"

    surface_contract = client.get("/takeover/operator-surface-contract").json()
    assert surface_contract["ok"] is True
    assert surface_contract["kind"] == "francis.stage9.takeover.operator_surface_contract"
    assert surface_contract["status"] == "ready"
    assert surface_contract["operator_surface_contract_ready"] is True
    assert surface_contract["latest_control_transfer_receipt_id"] == transfer_body["receipt_id"]
    assert surface_contract["latest_panic_stop_receipt_id"] == panic_body["receipt_id"]
    assert surface_contract["latest_handback_summary_receipt_id"] == handback_body["receipt_id"]
    assert surface_contract["routes"]["status"] == "/takeover/status"
    assert surface_contract["routes"]["panic_stop"] == "/takeover/panic-stop"
    assert surface_contract["routes"]["handback_summary"] == "/takeover/handback-summary"
    assert surface_contract["reads_receipts"] is True
    assert surface_contract["writes_receipts"] is False
    assert surface_contract["writes_tasks"] is False
    assert surface_contract["writes_memory"] is False
    assert surface_contract["runs_tools"] is False
    assert surface_contract["runs_shell"] is False
    assert surface_contract["grants_execution_authority"] is False
    assert surface_contract["grants_mutation_authority"] is False
    assert surface_contract["governance"]["read_only"] is True
    assert surface_contract["governance"]["surface_contract_only"] is True
    assert surface_contract["next_smallest_truthful_gap"] == "stage9_panic_operation_cancellation"
    checks = {item["id"]: item for item in surface_contract["checks"]}
    assert checks["stage8_closure_receipt_visible"]["passed"] is True
    assert checks["control_transfer_receipt_visible"]["passed"] is True
    assert checks["panic_stop_receipt_visible"]["passed"] is True
    assert checks["handback_summary_receipt_visible"]["passed"] is True
    assert checks["live_action_feed_visible"]["passed"] is True
    assert checks["pilot_visibility_visible"]["passed"] is True
    assert checks["next_gap_visible"]["passed"] is True
    assert checks["no_authority_escalation"]["passed"] is True

    transfer_receipts = client.get("/takeover/control-transfer-receipts").json()
    panic_receipts = client.get("/takeover/panic-stop-receipts").json()
    handback_receipts = client.get("/takeover/handback-summaries").json()
    assert transfer_receipts["count"] == 1
    assert panic_receipts["count"] == 1
    assert handback_receipts["count"] == 1
    assert transfer_receipts["items"][0]["receipt_id"] == transfer_body["receipt_id"]
    assert panic_receipts["items"][0]["receipt_id"] == panic_body["receipt_id"]
    assert handback_receipts["items"][0]["receipt_id"] == handback_body["receipt_id"]
