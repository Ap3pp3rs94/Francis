from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


def _write_stage12_closure_receipt(
    data_root: Path,
    *,
    receipt_id: str = "knowledge_fabric_stage12_closure_test",
) -> None:
    path = data_root / "logs" / "knowledge_fabric" / "stage12_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "francis.stage12.knowledge_fabric.stage12_closure_decision_receipt",
                "receipt_id": receipt_id,
                "stage": "Stage 12 / Knowledge Fabric",
                "source_id": "knowledge_fabric",
                "target": "stage12_knowledge_fabric",
                "actor": "test.operator",
                "decision": "close_stage12",
                "completion_review_ready": True,
                "stage12_closed_by_receipt": True,
                "marks_runtime_stage_state": False,
                "recorded_ts": 1_800_001_000,
                "governance": {
                    "explicit_operator_decision": True,
                    "stage_closure_decision": True,
                    "completion_review_ready": True,
                    "does_not_mutate_runtime_stage_state": True,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_trust_calibration_status_blocks_until_stage12_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/trust-calibration/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage13.trust_calibration.status"
    assert body["stage"] == "Stage 13 / Trust Calibration"
    assert body["status"] == "awaiting_stage12_ledger_closure"
    assert body["stage12_closed_by_receipt"] is False
    assert body["stage12_latest_closure_receipt_id"] == ""
    assert body["confidence_rules_contract_ready"] is False
    assert body["verification_gates_ready"] is False
    assert body["anti_overclaim_policy_ready"] is False
    assert body["calibrated_claim_logic_ready"] is False
    assert body["ready_count"] == 0
    assert body["required_count"] == 5
    assert body["routes"]["status"] == "/trust-calibration/status"
    assert body["routes"]["confidence_rules_contract"] == "/trust-calibration/confidence-rules-contract"
    assert body["routes"]["stage12_closure_readback"] == "/knowledge-fabric/stage-closure-decisions"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["requires_stage12_ledger_closure"] is True
    assert body["governance"]["does_not_score_model_output"] is True
    assert body["governance"]["does_not_change_ui_confidence"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["next_smallest_truthful_gap"] == "stage12_ledger_closure"
    assert not data_root.exists()

    contract = TestClient(create_app()).get("/trust-calibration/confidence-rules-contract").json()
    assert contract["status"] == "blocked"
    assert contract["confidence_rules_contract_ready"] is False
    assert contract["stage12_closed_by_receipt"] is False
    assert contract["scores_model_output"] is False
    assert contract["changes_ui_confidence"] is False
    assert contract["writes_memory"] is False
    assert contract["next_smallest_truthful_gap"] == "stage12_ledger_closure"


def test_trust_calibration_confidence_rules_contract_ready_after_stage12_closure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage12_closure_receipt(data_root, receipt_id="knowledge_fabric_stage12_closure_tc_test")

    client = TestClient(create_app())
    response = client.get("/trust-calibration/confidence-rules-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage13.trust_calibration.confidence_rules_contract"
    assert body["status"] == "ready"
    assert body["confidence_rules_contract_ready"] is True
    assert body["stage12_closed_by_receipt"] is True
    assert body["stage12_latest_closure_receipt_id"] == "knowledge_fabric_stage12_closure_tc_test"
    assert body["claim_strength_rule_count"] == 4
    assert body["verification_inputs"] == [
        "current_route_readback",
        "explicit_receipt",
        "local_evidence_citation",
        "trace_lineage",
        "operator_decision",
        "recency_readback",
    ]
    assert body["anti_overclaim_constraints"]["no_false_done"] is True
    assert body["anti_overclaim_constraints"]["no_fake_certainty"] is True
    assert body["anti_overclaim_constraints"]["no_stale_evidence_as_current_proof"] is True
    assert body["anti_overclaim_constraints"]["must_name_missing_verification"] is True
    assert body["writes_memory"] is False
    assert body["writes_receipts"] is False
    assert body["scores_model_output"] is False
    assert body["changes_ui_confidence"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["contract_only"] is True
    assert body["governance"]["requires_stage12_ledger_closure"] is True
    assert body["next_smallest_truthful_gap"] == "stage13_verification_gate_contract"

    rules = {item["id"]: item for item in body["claim_strength_rules"]}
    assert set(rules) == {"confirmed", "likely", "uncertain", "blocked"}
    assert "current_direct_readback_or_receipt_exists" in rules["confirmed"]["allowed_when"]
    assert rules["likely"]["required_surface_behavior"] == "state_as_likely_and_name_missing_verification"
    assert "evidence_is_stale" in rules["uncertain"]["allowed_when"]
    assert rules["blocked"]["failure_mode_prevented"] == "fake_done_or_fake_autonomy"

    status = client.get("/trust-calibration/status").json()
    assert status["status"] == "stage13_confidence_rules_contract_ready"
    assert status["stage12_closed_by_receipt"] is True
    assert status["confidence_rules_contract_ready"] is True
    assert status["ready_count"] == 2
    assert status["required_count"] == 5
    assert status["next_smallest_truthful_gap"] == "stage13_verification_gate_contract"
