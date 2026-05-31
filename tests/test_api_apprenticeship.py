from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


def _write_stage10_closure_receipt(
    data_root: Path,
    *,
    receipt_id: str = "away_stage10_closure_test",
) -> None:
    path = data_root / "logs" / "away" / "stage10_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "francis.stage10.away.stage10_operator_stage_closure_decision_receipt",
                "receipt_id": receipt_id,
                "stage": "Stage 10 / Away Mode",
                "source_id": "away",
                "target": "stage10_away",
                "actor": "test.operator",
                "decision": "close_stage10",
                "completion_review_ready": True,
                "stage10_closed_by_receipt": True,
                "marks_runtime_stage_state": False,
                "recorded_ts": 1_800_000_000,
                "governance": {
                    "explicit_operator_decision": True,
                    "stage_closure_decision": True,
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


def test_apprenticeship_status_waits_for_stage10_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/apprenticeship/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage11.apprenticeship.status"
    assert body["status"] == "awaiting_stage10_ledger_closure"
    assert body["stage10_closed_by_receipt"] is False
    assert body["teaching_session_ready"] is False
    assert body["passive_learning_enabled"] is False
    assert body["captures_screen"] is False
    assert body["captures_audio"] is False
    assert body["captures_keystrokes"] is False
    assert body["writes_memory"] is False
    assert body["runs_shell"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["requires_stage10_ledger_closure"] is True
    assert body["governance"]["passive_capture_denied"] is True
    assert body["governance"]["surveillance_like_learning_denied"] is True
    assert body["next_smallest_truthful_gap"] == "stage10_ledger_closure"


def test_apprenticeship_status_starts_stage11_groundwork_after_stage10_closure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage10_closure_receipt(data_root, receipt_id="away_stage10_closure_apprenticeship_test")

    response = TestClient(create_app()).get("/apprenticeship/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage11.apprenticeship.status"
    assert body["status"] == "stage11_groundwork_ready"
    assert body["stage10_closed_by_receipt"] is True
    assert body["stage10_latest_closure_receipt_id"] == "away_stage10_closure_apprenticeship_test"
    assert body["stage10_next_smallest_truthful_gap"] == "stage10_ledger_closure"
    assert body["ready_count"] == 2
    assert body["required_count"] == 5
    assert body["teaching_session_ready"] is True
    assert body["replay_generalization_ready"] is False
    assert body["skillization_ready"] is False
    assert body["forge_handoff_ready"] is False
    assert body["reads_receipts"] is True
    assert body["writes_receipts"] is False
    assert body["writes_memory"] is False
    assert body["captures_screen"] is False
    assert body["captures_audio"] is False
    assert body["captures_keystrokes"] is False
    assert body["passive_learning_enabled"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["explicit_teaching_session_required"] is True
    assert body["governance"]["passive_capture_denied"] is True
    assert body["governance"]["surveillance_like_learning_denied"] is True
    assert body["governance"]["learned_skills_must_be_reviewable"] is True
    assert body["governance"]["forge_handoff_must_be_governed"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["governance"]["does_not_capture_screen"] is True
    assert body["governance"]["does_not_capture_audio"] is True
    assert body["governance"]["does_not_capture_keystrokes"] is True
    assert body["routes"]["status"] == "/apprenticeship/status"
    assert body["routes"]["stage10_closure_readback"] == "/away/stage-closure-decisions"
    assert body["routes"]["teaching_session_contract"] == "/apprenticeship/teaching-session-contract"
    assert body["next_smallest_truthful_gap"] == "stage11_replay_generalization_contract"

    deliverables = {item["id"]: item for item in body["deliverables"]}
    assert deliverables["stage10_ledger_closure_backstop"]["ready"] is True
    assert deliverables["teaching_session_ux"]["ready"] is True
    assert deliverables["replay_generalization_flow"]["ready"] is False
    assert deliverables["skillization_artifacts"]["ready"] is False
    assert deliverables["forge_ready_outputs"]["ready"] is False


def test_apprenticeship_teaching_session_contract_is_explicit_and_non_capturing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage10_closure_receipt(data_root, receipt_id="away_stage10_closure_teaching_contract_test")

    response = TestClient(create_app()).get("/apprenticeship/teaching-session-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage11.apprenticeship.teaching_session_contract"
    assert body["status"] == "ready"
    assert body["stage10_closed_by_receipt"] is True
    assert body["stage10_latest_closure_receipt_id"] == "away_stage10_closure_teaching_contract_test"
    assert body["teaching_session_contract_ready"] is True
    assert body["canonical_pipeline"] == ["demonstrate", "label_intent", "replay", "generalize", "skillize"]
    assert body["requirement_count"] == 5
    assert body["capture_boundary_count"] == 5
    assert body["reads_receipts"] is True
    assert body["writes_receipts"] is False
    assert body["writes_memory"] is False
    assert body["captures_screen"] is False
    assert body["captures_audio"] is False
    assert body["captures_keystrokes"] is False
    assert body["passive_learning_enabled"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["contract_only"] is True
    assert body["governance"]["explicit_teaching_session_required"] is True
    assert body["governance"]["operator_supplied_steps_only"] is True
    assert body["governance"]["operator_review_before_learning"] is True
    assert body["governance"]["passive_capture_denied"] is True
    assert body["governance"]["surveillance_like_learning_denied"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["governance"]["does_not_capture_screen"] is True
    assert body["governance"]["does_not_capture_audio"] is True
    assert body["governance"]["does_not_capture_keystrokes"] is True
    assert body["next_smallest_truthful_gap"] == "stage11_replay_generalization_contract"

    requirements = {item["id"]: item for item in body["requirements"]}
    assert set(requirements) == {
        "declared_scope",
        "explicit_start_stop",
        "intent_label",
        "operator_review_before_learning",
        "success_condition",
    }
    assert all(item["required"] for item in requirements.values())

    boundaries = {item["id"]: item for item in body["capture_boundaries"]}
    assert boundaries["operator_supplied_steps_only"]["allowed"] is True
    assert boundaries["screen_capture"]["allowed"] is False
    assert boundaries["audio_capture"]["allowed"] is False
    assert boundaries["keystroke_capture"]["allowed"] is False
    assert boundaries["passive_background_learning"]["allowed"] is False

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["stage10_ledger_closure_backstop"]["passed"] is True
    assert checks["canonical_teaching_requirements_declared"]["passed"] is True
    assert checks["capture_boundaries_deny_passive_learning"]["passed"] is True
    assert checks["ambient_capture_denied"]["passed"] is True
    assert checks["operator_supplied_steps_only"]["passed"] is True
