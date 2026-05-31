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
    assert status["status"] == "stage14_injection_containment_contract_ready"
    assert status["stage13_closed_by_receipt"] is True
    assert status["injection_containment_contract_ready"] is True
    assert status["quarantine_model_contract_ready"] is False
    assert status["ready_count"] == 2
    assert status["required_count"] == 5
    assert status["next_smallest_truthful_gap"] == "stage14_quarantine_model_contract"
