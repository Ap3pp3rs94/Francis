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
    assert body["routes"]["verification_gate_contract"] == "/trust-calibration/verification-gate-contract"
    assert body["routes"]["anti_overclaim_policy"] == "/trust-calibration/anti-overclaim-policy"
    assert body["routes"]["stage12_closure_readback"] == "/knowledge-fabric/stage-closure-decisions"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["requires_stage12_ledger_closure"] is True
    assert body["governance"]["does_not_enforce_runtime_claims"] is True
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

    verification = TestClient(create_app()).get("/trust-calibration/verification-gate-contract").json()
    assert verification["status"] == "blocked"
    assert verification["verification_gate_contract_ready"] is False
    assert verification["confidence_rules_contract_ready"] is False
    assert verification["stage12_closed_by_receipt"] is False
    assert verification["gate_count"] == 6
    assert verification["enforces_runtime_claims"] is False
    assert verification["scores_model_output"] is False
    assert verification["changes_ui_confidence"] is False
    assert verification["next_smallest_truthful_gap"] == "stage12_ledger_closure"

    anti_overclaim = TestClient(create_app()).get("/trust-calibration/anti-overclaim-policy").json()
    assert anti_overclaim["status"] == "blocked"
    assert anti_overclaim["anti_overclaim_policy_ready"] is False
    assert anti_overclaim["verification_gate_contract_ready"] is False
    assert anti_overclaim["confidence_rules_contract_ready"] is False
    assert anti_overclaim["stage12_closed_by_receipt"] is False
    assert anti_overclaim["policy_count"] == 7
    assert anti_overclaim["enforces_runtime_claims"] is False
    assert anti_overclaim["scores_model_output"] is False
    assert anti_overclaim["changes_ui_confidence"] is False
    assert anti_overclaim["next_smallest_truthful_gap"] == "stage12_ledger_closure"


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

    verification = client.get("/trust-calibration/verification-gate-contract").json()
    assert verification["ok"] is True
    assert verification["kind"] == "francis.stage13.trust_calibration.verification_gate_contract"
    assert verification["status"] == "ready"
    assert verification["verification_gate_contract_ready"] is True
    assert verification["confidence_rules_contract_ready"] is True
    assert verification["stage12_closed_by_receipt"] is True
    assert verification["stage12_latest_closure_receipt_id"] == "knowledge_fabric_stage12_closure_tc_test"
    assert verification["gate_count"] == 6
    assert verification["required_claim_strengths"] == ["confirmed", "likely", "uncertain", "blocked"]
    assert verification["denial_behavior"]["missing_receipt"] == "blocked"
    assert verification["denial_behavior"]["missing_current_readback"] == "uncertain"
    assert verification["denial_behavior"]["stale_evidence"] == "uncertain"
    assert verification["denial_behavior"]["missing_authority"] == "blocked"
    assert verification["writes_memory"] is False
    assert verification["writes_receipts"] is False
    assert verification["scores_model_output"] is False
    assert verification["changes_ui_confidence"] is False
    assert verification["enforces_runtime_claims"] is False
    assert verification["runs_tools"] is False
    assert verification["runs_shell"] is False
    assert verification["runs_git"] is False
    assert verification["grants_execution_authority"] is False
    assert verification["grants_mutation_authority"] is False
    assert verification["governance"]["contract_only"] is True
    assert verification["governance"]["does_not_enforce_runtime_claims"] is True
    assert verification["next_smallest_truthful_gap"] == "stage13_anti_overclaim_policy"

    gates = {item["id"]: item for item in verification["gates"]}
    assert set(gates) == {
        "current_state_claim_gate",
        "done_or_closure_claim_gate",
        "retrieval_backed_claim_gate",
        "authority_or_action_claim_gate",
        "stale_or_conflicting_evidence_gate",
        "blocked_state_preservation_gate",
    }
    done_gate = gates["done_or_closure_claim_gate"]
    assert "completion_review_or_stage_closure_readback" in done_gate["required_inputs"]
    assert done_gate["allows_max_strength"] == "confirmed"
    assert done_gate["downgrade_when_missing"] == "blocked"
    assert gates["retrieval_backed_claim_gate"]["allows_max_strength"] == "likely"
    blocked_gate = gates["blocked_state_preservation_gate"]
    assert blocked_gate["allows_max_strength"] == "blocked"
    assert blocked_gate["denial_behavior"] == "do_not_launder_blocked_state_into_progress"

    anti_overclaim = client.get("/trust-calibration/anti-overclaim-policy").json()
    assert anti_overclaim["ok"] is True
    assert anti_overclaim["kind"] == "francis.stage13.trust_calibration.anti_overclaim_policy"
    assert anti_overclaim["status"] == "ready"
    assert anti_overclaim["anti_overclaim_policy_ready"] is True
    assert anti_overclaim["verification_gate_contract_ready"] is True
    assert anti_overclaim["confidence_rules_contract_ready"] is True
    assert anti_overclaim["stage12_closed_by_receipt"] is True
    assert anti_overclaim["stage12_latest_closure_receipt_id"] == "knowledge_fabric_stage12_closure_tc_test"
    assert anti_overclaim["policy_count"] == 7
    assert anti_overclaim["required_claim_strengths"] == ["confirmed", "likely", "uncertain", "blocked"]
    assert anti_overclaim["required_verification_gates"] == [
        "current_state_claim_gate",
        "done_or_closure_claim_gate",
        "retrieval_backed_claim_gate",
        "authority_or_action_claim_gate",
        "stale_or_conflicting_evidence_gate",
        "blocked_state_preservation_gate",
    ]
    assert "false_done" in anti_overclaim["failure_modes_prevented"]
    assert "fake_certainty" in anti_overclaim["failure_modes_prevented"]
    assert "ui_confidence_laundering" in anti_overclaim["failure_modes_prevented"]
    assert "blocked_state_laundered_into_progress" in anti_overclaim["failure_modes_prevented"]
    assert anti_overclaim["surface_obligations"]["confirmed"] == "cite_current_evidence_and_receipt_or_readback"
    assert anti_overclaim["surface_obligations"]["likely"] == "name_missing_verification"
    assert anti_overclaim["surface_obligations"]["blocked"] == "state_blocker_without_implying_progress"
    assert anti_overclaim["writes_memory"] is False
    assert anti_overclaim["writes_receipts"] is False
    assert anti_overclaim["scores_model_output"] is False
    assert anti_overclaim["changes_ui_confidence"] is False
    assert anti_overclaim["enforces_runtime_claims"] is False
    assert anti_overclaim["runs_tools"] is False
    assert anti_overclaim["runs_shell"] is False
    assert anti_overclaim["runs_git"] is False
    assert anti_overclaim["grants_execution_authority"] is False
    assert anti_overclaim["grants_mutation_authority"] is False
    assert anti_overclaim["governance"]["contract_only"] is True
    assert anti_overclaim["governance"]["does_not_enforce_runtime_claims"] is True
    assert anti_overclaim["next_smallest_truthful_gap"] == "stage13_calibrated_claim_logic"

    policies = {item["id"]: item for item in anti_overclaim["policies"]}
    assert set(policies) == {
        "no_false_done",
        "no_fake_certainty",
        "stale_evidence_guard",
        "ui_confidence_laundering_guard",
        "blocked_state_preservation",
        "authority_claim_guard",
        "useful_uncertainty",
    }
    assert policies["no_false_done"]["required_gate"] == "done_or_closure_claim_gate"
    assert "call_done_from_partial_test_pass" in policies["no_false_done"]["forbidden"]
    assert policies["stale_evidence_guard"]["fallback_claim_strength"] == "uncertain"
    assert "make_uncertain_state_look_confirmed" in policies["ui_confidence_laundering_guard"]["forbidden"]
    assert policies["blocked_state_preservation"]["fallback_claim_strength"] == "blocked"
    assert policies["authority_claim_guard"]["required_gate"] == "authority_or_action_claim_gate"

    status = client.get("/trust-calibration/status").json()
    assert status["status"] == "stage13_anti_overclaim_policy_ready"
    assert status["stage12_closed_by_receipt"] is True
    assert status["confidence_rules_contract_ready"] is True
    assert status["verification_gates_ready"] is True
    assert status["anti_overclaim_policy_ready"] is True
    assert status["ready_count"] == 4
    assert status["required_count"] == 5
    assert status["next_smallest_truthful_gap"] == "stage13_calibrated_claim_logic"
