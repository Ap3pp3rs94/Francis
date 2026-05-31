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


def _write_stage13_ui_coherence_sources(repo_root: Path) -> None:
    app_path = repo_root / "apps" / "chat_ui" / "src" / "App.tsx"
    dashboard_path = repo_root / "apps" / "chat_ui" / "src" / "trust_dashboard" / "index.ts"
    app_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    app_path.write_text(
        """
        trustClient.evaluateClaim({
          claim_text: "Stage 13 trust calibration claim state is visible in the operator shell",
          claim_scope: "stage13_ui_state_coherence",
          requested_claim_strength: "likely",
          evidence: {
            missing_verification: ["operator_browser_visual_readback"],
          },
        });
        <span>Trust calibration</span>
        <div id="francis-trust-calibration">Stage 13 calibration</div>
        trustCalibrationPresentation.strong_claim_allowed;
        trustCalibrationPresentation.must_name_missing_verification;
        trustCalibrationPresentation.runtime_claim_integration_ready;
        trustCalibrationPresentation.side_effects_denied;
        """,
        encoding="utf-8",
    )
    dashboard_path.write_text(
        """
        export type TrustCalibrationPresentation = {
          strong_claim_allowed: boolean;
          must_name_missing_verification: boolean;
          side_effects_denied: boolean;
          next_smallest_truthful_gap: "stage13_ui_state_coherence";
        };
        """,
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
    assert body["ui_state_coherence_review_ready"] is False
    assert body["operator_browser_visual_readback_observed"] is False
    assert body["ready_count"] == 0
    assert body["required_count"] == 6
    assert body["routes"]["status"] == "/trust-calibration/status"
    assert body["routes"]["confidence_rules_contract"] == "/trust-calibration/confidence-rules-contract"
    assert body["routes"]["verification_gate_contract"] == "/trust-calibration/verification-gate-contract"
    assert body["routes"]["anti_overclaim_policy"] == "/trust-calibration/anti-overclaim-policy"
    assert body["routes"]["calibrated_claim_logic"] == "/trust-calibration/calibrated-claim-logic"
    assert body["routes"]["ui_state_coherence"] == "/trust-calibration/ui-state-coherence"
    assert body["routes"]["claim_evaluation"] == "/trust-calibration/evaluate-claim"
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

    calibrated = TestClient(create_app()).get("/trust-calibration/calibrated-claim-logic").json()
    assert calibrated["status"] == "blocked"
    assert calibrated["calibrated_claim_logic_ready"] is False
    assert calibrated["anti_overclaim_policy_ready"] is False
    assert calibrated["verification_gate_contract_ready"] is False
    assert calibrated["confidence_rules_contract_ready"] is False
    assert calibrated["stage12_closed_by_receipt"] is False
    assert calibrated["claim_logic_rule_count"] == 4
    assert calibrated["runtime_integration_status"] == "contract_only_not_enforced"
    assert calibrated["enforces_runtime_claims"] is False
    assert calibrated["scores_model_output"] is False
    assert calibrated["changes_ui_confidence"] is False
    assert calibrated["next_smallest_truthful_gap"] == "stage12_ledger_closure"

    evaluation = (
        TestClient(create_app())
        .post(
            "/trust-calibration/evaluate-claim",
            json={
                "claim_text": "Stage 13 is done",
                "requested_claim_strength": "confirmed",
                "evidence": {"current_route_readback": True},
            },
        )
        .json()
    )
    assert evaluation["status"] == "blocked"
    assert evaluation["runtime_claim_integration_ready"] is False
    assert evaluation["claim_strength"] == "blocked"
    assert evaluation["reason"] == "stage12_ledger_closure_missing"
    assert evaluation["downgraded"] is True
    assert evaluation["missing_verification"] == ["blocked_state_resolution"]
    assert evaluation["evaluates_supplied_evidence_only"] is True
    assert evaluation["writes_memory"] is False
    assert evaluation["writes_receipts"] is False
    assert evaluation["scores_model_output"] is False
    assert evaluation["changes_ui_confidence"] is False
    assert evaluation["enforces_runtime_claims"] is False


def test_trust_calibration_confidence_rules_contract_ready_after_stage12_closure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    _write_stage13_ui_coherence_sources(repo_root)
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

    calibrated = client.get("/trust-calibration/calibrated-claim-logic").json()
    assert calibrated["ok"] is True
    assert calibrated["kind"] == "francis.stage13.trust_calibration.calibrated_claim_logic"
    assert calibrated["status"] == "ready"
    assert calibrated["calibrated_claim_logic_ready"] is True
    assert calibrated["anti_overclaim_policy_ready"] is True
    assert calibrated["verification_gate_contract_ready"] is True
    assert calibrated["confidence_rules_contract_ready"] is True
    assert calibrated["stage12_closed_by_receipt"] is True
    assert calibrated["stage12_latest_closure_receipt_id"] == "knowledge_fabric_stage12_closure_tc_test"
    assert calibrated["claim_logic_rule_count"] == 4
    assert calibrated["decision_order"] == [
        "blocked_state_preservation_before_progress",
        "authority_and_receipt_gates_before_action_claims",
        "recency_and_conflict_checks_before_confirmed_claims",
        "evidence_scope_match_before_strong_language",
        "missing_verification_named_before_likely_or_uncertain_language",
    ]
    assert "orb" in calibrated["surface_targets"]
    assert "hud" in calibrated["surface_targets"]
    assert "chat_ui" in calibrated["surface_targets"]
    assert calibrated["runtime_integration_status"] == "contract_only_not_enforced"
    assert calibrated["writes_memory"] is False
    assert calibrated["writes_receipts"] is False
    assert calibrated["scores_model_output"] is False
    assert calibrated["changes_ui_confidence"] is False
    assert calibrated["enforces_runtime_claims"] is False
    assert calibrated["runs_tools"] is False
    assert calibrated["runs_shell"] is False
    assert calibrated["runs_git"] is False
    assert calibrated["grants_execution_authority"] is False
    assert calibrated["grants_mutation_authority"] is False
    assert calibrated["governance"]["contract_only"] is True
    assert calibrated["governance"]["does_not_enforce_runtime_claims"] is True
    assert calibrated["next_smallest_truthful_gap"] == "stage13_runtime_claim_integration"

    claim_rules = {item["claim_strength"]: item for item in calibrated["claim_logic_rules"]}
    assert set(claim_rules) == {"confirmed", "likely", "uncertain", "blocked"}
    assert claim_rules["confirmed"]["ui_state"] == "strong_signal_allowed_only_with_current_evidence"
    assert claim_rules["confirmed"]["must_cite"] is True
    assert "confirmed" in claim_rules["likely"]["forbidden_surface_language"]
    assert claim_rules["likely"]["must_name_missing_verification"] is True
    assert "safe_to_advance" in claim_rules["uncertain"]["forbidden_surface_language"]
    assert claim_rules["blocked"]["ui_state"] == "blocked_signal_required"
    assert claim_rules["blocked"]["must_cite"] is True

    decision_table = {item["condition"]: item for item in calibrated["decision_table"]}
    assert decision_table["current_readback_reports_blocked"]["claim_strength"] == "blocked"
    assert decision_table["authority_or_required_receipt_missing"]["claim_strength"] == "blocked"
    assert decision_table["current_receipt_or_readback_and_no_conflict"]["claim_strength"] == "confirmed"
    assert decision_table["supporting_evidence_with_missing_verification"]["claim_strength"] == "likely"
    assert decision_table["stale_or_conflicting_or_missing_evidence"]["claim_strength"] == "uncertain"

    ui_review = client.get("/trust-calibration/ui-state-coherence").json()
    assert ui_review["ok"] is True
    assert ui_review["kind"] == "francis.stage13.trust_calibration.ui_state_coherence_review"
    assert ui_review["status"] == "ready"
    assert ui_review["ui_state_coherence_review_ready"] is True
    assert ui_review["runtime_claim_integration_ready"] is True
    assert ui_review["stage12_closed_by_receipt"] is True
    assert ui_review["stage12_latest_closure_receipt_id"] == "knowledge_fabric_stage12_closure_tc_test"
    assert ui_review["source_contract_count"] == 4
    assert ui_review["source_contract_ready_count"] == 4
    assert ui_review["operator_shell_card_observed"] is True
    assert ui_review["bounded_shell_claim_request_observed"] is True
    assert ui_review["claim_guard_readback_observed"] is True
    assert ui_review["presentation_model_observed"] is True
    assert ui_review["browser_visual_readback_required"] is True
    assert ui_review["operator_browser_visual_readback_observed"] is False
    assert ui_review["missing_verification"] == ["operator_browser_visual_readback"]
    assert ui_review["writes_memory"] is False
    assert ui_review["writes_receipts"] is False
    assert ui_review["runs_tools"] is False
    assert ui_review["runs_shell"] is False
    assert ui_review["runs_git"] is False
    assert ui_review["grants_execution_authority"] is False
    assert ui_review["grants_mutation_authority"] is False
    assert ui_review["governance"]["static_source_readback_only"] is True
    assert ui_review["governance"]["browser_visual_readback_required"] is True
    assert ui_review["governance"]["does_not_launch_browser"] is True
    assert ui_review["governance"]["does_not_mark_stage_closed"] is True
    assert ui_review["next_smallest_truthful_gap"] == "stage13_operator_browser_visual_readback"
    assert all(item["observed"] for item in ui_review["source_contracts"])

    status = client.get("/trust-calibration/status").json()
    assert status["status"] == "stage13_ui_state_coherence_ready"
    assert status["stage12_closed_by_receipt"] is True
    assert status["confidence_rules_contract_ready"] is True
    assert status["verification_gates_ready"] is True
    assert status["anti_overclaim_policy_ready"] is True
    assert status["calibrated_claim_logic_ready"] is True
    assert status["runtime_claim_integration_ready"] is True
    assert status["ui_state_coherence_review_ready"] is True
    assert status["operator_browser_visual_readback_observed"] is False
    assert status["ready_count"] == 6
    assert status["required_count"] == 6
    assert status["next_smallest_truthful_gap"] == "stage13_operator_browser_visual_readback"

    blocked_eval = client.post(
        "/trust-calibration/evaluate-claim",
        json={
            "claim_text": "Stage can close",
            "claim_scope": "stage_closure",
            "requested_claim_strength": "confirmed",
            "evidence": {
                "current_readback_reports_blocked": True,
                "next_smallest_truthful_gap": "stage13_ui_state_coherence",
            },
        },
    ).json()
    assert blocked_eval["status"] == "evaluated"
    assert blocked_eval["runtime_claim_integration_ready"] is True
    assert blocked_eval["claim_strength"] == "blocked"
    assert blocked_eval["condition"] == "current_readback_reports_blocked"
    assert blocked_eval["downgraded"] is True
    assert blocked_eval["surface_obligation"] == "preserve_blocked_state_and_name_next_gap"
    assert blocked_eval["ui_state"] == "blocked_signal_required"
    assert blocked_eval["next_smallest_truthful_gap"] == "stage13_ui_state_coherence"
    assert blocked_eval["writes_memory"] is False
    assert blocked_eval["writes_receipts"] is False
    assert blocked_eval["enforces_runtime_claims"] is False
    assert blocked_eval["governance"]["read_only_evaluation"] is True
    assert blocked_eval["governance"]["does_not_persist_evaluation"] is True

    confirmed_eval = client.post(
        "/trust-calibration/evaluate-claim",
        json={
            "claim_text": "Completion review is ready",
            "claim_scope": "completion_review",
            "requested_claim_strength": "confirmed",
            "evidence": {
                "current_route_readback": True,
                "recency_readback": True,
                "claim_scope_matches_evidence_scope": True,
                "conflicting_evidence": False,
                "stale_evidence": False,
            },
        },
    ).json()
    assert confirmed_eval["claim_strength"] == "confirmed"
    assert confirmed_eval["downgraded"] is False
    assert confirmed_eval["missing_verification"] == []
    assert confirmed_eval["must_cite"] is True
    assert confirmed_eval["ui_state"] == "strong_signal_allowed_only_with_current_evidence"
    assert "confirmed" in confirmed_eval["allowed_surface_language"]
    assert "should_be_done" in confirmed_eval["forbidden_surface_language"]

    likely_eval = client.post(
        "/trust-calibration/evaluate-claim",
        json={
            "claim_text": "CI appears healthy",
            "claim_scope": "ci_state",
            "requested_claim_strength": "confirmed",
            "evidence": {
                "supporting_evidence": True,
                "conflicting_evidence": False,
                "missing_verification": ["current_actions_run_readback"],
            },
        },
    ).json()
    assert likely_eval["claim_strength"] == "likely"
    assert likely_eval["downgraded"] is True
    assert "current_actions_run_readback" in likely_eval["missing_verification"]
    assert likely_eval["must_name_missing_verification"] is True
    assert likely_eval["ui_state"] == "cautious_signal_only"

    uncertain_eval = client.post(
        "/trust-calibration/evaluate-claim",
        json={
            "claim_text": "Runtime is current",
            "claim_scope": "runtime_readback",
            "requested_claim_strength": "likely",
            "evidence": {"stale_evidence": True},
        },
    ).json()
    assert uncertain_eval["claim_strength"] == "uncertain"
    assert uncertain_eval["downgraded"] is True
    assert uncertain_eval["missing_verification"] == ["current_evidence_or_conflict_resolution"]
    assert uncertain_eval["surface_obligation"] == "state_uncertainty_and_next_check"
