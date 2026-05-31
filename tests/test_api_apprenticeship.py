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
    assert body["status"] == "stage11_operator_surface_ready"
    assert body["stage10_closed_by_receipt"] is True
    assert body["stage10_latest_closure_receipt_id"] == "away_stage10_closure_apprenticeship_test"
    assert body["stage10_next_smallest_truthful_gap"] == "stage10_ledger_closure"
    assert body["ready_count"] == 5
    assert body["required_count"] == 5
    assert body["teaching_session_ready"] is True
    assert body["replay_generalization_ready"] is True
    assert body["skillization_ready"] is True
    assert body["forge_handoff_ready"] is True
    assert body["live_teaching_session_ux_ready"] is True
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
    assert body["routes"]["replay_generalization_contract"] == "/apprenticeship/replay-generalization-contract"
    assert body["routes"]["skillization_artifact_contract"] == "/apprenticeship/skillization-artifact-contract"
    assert body["routes"]["forge_handoff_contract"] == "/apprenticeship/forge-handoff-contract"
    assert body["routes"]["live_teaching_session_ux"] == "/apprenticeship/live-teaching-session-ux"
    assert body["next_smallest_truthful_gap"] == "stage11_teaching_session_receipt_write_path"

    deliverables = {item["id"]: item for item in body["deliverables"]}
    assert deliverables["stage10_ledger_closure_backstop"]["ready"] is True
    assert deliverables["teaching_session_ux"]["ready"] is True
    assert deliverables["replay_generalization_flow"]["ready"] is True
    assert deliverables["skillization_artifacts"]["ready"] is True
    assert deliverables["forge_ready_outputs"]["ready"] is True


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


def test_apprenticeship_replay_generalization_contract_is_bounded_and_reviewed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage10_closure_receipt(data_root, receipt_id="away_stage10_closure_replay_contract_test")

    response = TestClient(create_app()).get("/apprenticeship/replay-generalization-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage11.apprenticeship.replay_generalization_contract"
    assert body["status"] == "ready"
    assert body["teaching_session_contract_ready"] is True
    assert body["replay_generalization_contract_ready"] is True
    assert body["pipeline_position"] == ["replay", "generalize"]
    assert body["replay_requirement_count"] == 5
    assert body["generalization_requirement_count"] == 5
    assert set(body["denied_modes"]) == {
        "background_replay_execution",
        "literal_macro_playback",
        "silent_skill_promotion",
        "unreviewed_generalization",
    }
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
    assert body["executes_replay"] is False
    assert body["promotes_skill"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["contract_only"] is True
    assert body["governance"]["requires_teaching_session_contract"] is True
    assert body["governance"]["bounded_replay_only"] is True
    assert body["governance"]["operator_replay_review_required"] is True
    assert body["governance"]["generalization_review_required"] is True
    assert body["governance"]["literal_macro_playback_denied"] is True
    assert body["governance"]["background_replay_execution_denied"] is True
    assert body["governance"]["silent_skill_promotion_denied"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["governance"]["does_not_run_tools"] is True
    assert body["next_smallest_truthful_gap"] == "stage11_skillization_artifact_contract"

    replay_requirements = {item["id"]: item for item in body["replay_requirements"]}
    assert set(replay_requirements) == {
        "assumption_register",
        "bounded_replay_plan",
        "intent_label_readback",
        "operator_replay_review",
        "operator_supplied_demonstration_steps",
    }
    assert all(item["required"] for item in replay_requirements.values())

    generalization_requirements = {item["id"]: item for item in body["generalization_requirements"]}
    assert set(generalization_requirements) == {
        "failure_handling",
        "optional_branches",
        "stable_steps",
        "validation_checkpoints",
        "variable_inputs",
    }
    assert all(item["required"] for item in generalization_requirements.values())

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["teaching_session_contract_ready"]["passed"] is True
    assert checks["bounded_replay_requirements_declared"]["passed"] is True
    assert checks["generalization_requirements_declared"]["passed"] is True
    assert checks["macro_playback_denied"]["passed"] is True
    assert checks["unreviewed_execution_denied"]["passed"] is True


def test_apprenticeship_skillization_artifact_contract_is_forge_ready_without_promotion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage10_closure_receipt(data_root, receipt_id="away_stage10_closure_skillization_contract_test")

    response = TestClient(create_app()).get("/apprenticeship/skillization-artifact-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage11.apprenticeship.skillization_artifact_contract"
    assert body["status"] == "ready"
    assert body["replay_generalization_contract_ready"] is True
    assert body["skillization_artifact_contract_ready"] is True
    assert body["pipeline_position"] == ["skillize"]
    assert body["artifact_field_count"] == 8
    assert body["classification_option_count"] == 4
    assert set(body["denied_modes"]) == {
        "automatic_promotion",
        "memory_write_without_operator_review",
        "silent_authority_growth",
        "unreviewed_capability_creation",
    }
    assert body["reads_receipts"] is True
    assert body["writes_receipts"] is False
    assert body["writes_memory"] is False
    assert body["writes_skill_artifact"] is False
    assert body["captures_screen"] is False
    assert body["captures_audio"] is False
    assert body["captures_keystrokes"] is False
    assert body["passive_learning_enabled"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["creates_capability"] is False
    assert body["promotes_to_forge"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["contract_only"] is True
    assert body["governance"]["requires_replay_generalization_contract"] is True
    assert body["governance"]["operator_review_required_before_artifact_write"] is True
    assert body["governance"]["forge_promotion_requires_governed_handoff"] is True
    assert body["governance"]["automatic_promotion_denied"] is True
    assert body["governance"]["silent_authority_growth_denied"] is True
    assert body["governance"]["unreviewed_capability_creation_denied"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["governance"]["does_not_write_skill_artifact"] is True
    assert body["next_smallest_truthful_gap"] == "stage11_forge_handoff_contract"

    artifact_schema = {item["id"]: item for item in body["artifact_schema"]}
    assert set(artifact_schema) == {
        "decision_logic",
        "documentation_draft",
        "parameterization",
        "pattern_summary",
        "risk_tier_candidate",
        "test_candidate_structure",
        "usage_scope",
        "validation_expectations",
    }
    assert all(item["required"] for item in artifact_schema.values())

    assert set(body["classification_options"]) == {
        "candidate_reusable_skill",
        "forge_worthy_promoted_capability",
        "preference_adaptation",
        "workflow_understanding",
    }

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["replay_generalization_contract_ready"]["passed"] is True
    assert checks["forge_ready_artifact_schema_declared"]["passed"] is True
    assert checks["learning_classifications_declared"]["passed"] is True
    assert checks["automatic_promotion_denied"]["passed"] is True
    assert checks["artifact_write_requires_operator_review"]["passed"] is True


def test_apprenticeship_forge_handoff_contract_is_review_gated_without_writes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage10_closure_receipt(data_root, receipt_id="away_stage10_closure_forge_handoff_contract_test")

    response = TestClient(create_app()).get("/apprenticeship/forge-handoff-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage11.apprenticeship.forge_handoff_contract"
    assert body["status"] == "ready"
    assert body["skillization_artifact_contract_ready"] is True
    assert body["forge_handoff_contract_ready"] is True
    assert body["handoff_target"] == "forge_proposal_candidate"
    assert body["handoff_payload_field_count"] == 10
    assert body["required_review_count"] == 5
    assert set(body["denied_modes"]) == {
        "automatic_capability_registration",
        "authority_grant_from_teaching",
        "direct_forge_promotion",
        "proposal_write_without_operator_review",
    }
    assert body["reads_receipts"] is True
    assert body["writes_receipts"] is False
    assert body["writes_memory"] is False
    assert body["writes_forge_proposal"] is False
    assert body["creates_capability"] is False
    assert body["promotes_to_forge"] is False
    assert body["registers_capability"] is False
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
    assert body["governance"]["requires_skillization_artifact_contract"] is True
    assert body["governance"]["operator_review_required_before_forge_write"] is True
    assert body["governance"]["explicit_promotion_decision_required"] is True
    assert body["governance"]["direct_forge_promotion_denied"] is True
    assert body["governance"]["automatic_capability_registration_denied"] is True
    assert body["governance"]["authority_grant_from_teaching_denied"] is True
    assert body["governance"]["does_not_write_forge_proposal"] is True
    assert body["governance"]["does_not_create_capability"] is True
    assert body["governance"]["does_not_promote_to_forge"] is True
    assert body["next_smallest_truthful_gap"] == "stage11_live_teaching_session_ux"

    handoff_schema = {item["id"]: item for item in body["handoff_payload_schema"]}
    assert set(handoff_schema) == {
        "decision_logic",
        "documentation_draft",
        "operator_review_state",
        "parameterization",
        "pattern_summary",
        "promotion_boundary",
        "risk_tier_candidate",
        "test_candidate_structure",
        "usage_scope",
        "validation_expectations",
    }
    assert all(item["required"] for item in handoff_schema.values())

    assert set(body["required_reviews"]) == {
        "documentation_review",
        "explicit_promotion_decision",
        "operator_review",
        "risk_tier_review",
        "test_candidate_review",
    }

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["skillization_artifact_contract_ready"]["passed"] is True
    assert checks["forge_handoff_payload_declared"]["passed"] is True
    assert checks["promotion_reviews_required"]["passed"] is True
    assert checks["direct_promotion_denied"]["passed"] is True
    assert checks["authority_growth_denied"]["passed"] is True


def test_apprenticeship_live_teaching_session_ux_is_visible_without_actions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage10_closure_receipt(data_root, receipt_id="away_stage10_closure_live_teaching_ux_test")

    response = TestClient(create_app()).get("/apprenticeship/live-teaching-session-ux")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage11.apprenticeship.live_teaching_session_ux"
    assert body["status"] == "ready"
    assert body["forge_handoff_contract_ready"] is True
    assert body["live_teaching_session_ux_ready"] is True
    assert body["surface"] == "chat_ui.apprenticeship_panel"
    assert body["route"] == "/apprenticeship/live-teaching-session-ux"
    assert body["visible_section_count"] == 7
    assert body["operator_action_count"] == 5
    assert set(body["denied_modes"]) == {
        "ambient_capture_start",
        "background_learning_toggle",
        "forge_promotion_from_ui_surface",
        "teaching_session_without_receipt",
    }
    assert body["reads_receipts"] is True
    assert body["writes_receipts"] is False
    assert body["writes_memory"] is False
    assert body["writes_skill_artifact"] is False
    assert body["writes_forge_proposal"] is False
    assert body["creates_capability"] is False
    assert body["promotes_to_forge"] is False
    assert body["starts_teaching_session"] is False
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
    assert body["governance"]["operator_surface_only"] is True
    assert body["governance"]["requires_forge_handoff_contract"] is True
    assert body["governance"]["requires_receipt_write_path_before_actions_enable"] is True
    assert body["governance"]["ambient_capture_start_denied"] is True
    assert body["governance"]["background_learning_toggle_denied"] is True
    assert body["governance"]["forge_promotion_from_ui_surface_denied"] is True
    assert body["governance"]["does_not_start_teaching_session"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["governance"]["does_not_write_forge_proposal"] is True
    assert body["next_smallest_truthful_gap"] == "stage11_teaching_session_receipt_write_path"

    sections = {item["id"]: item for item in body["visible_sections"]}
    assert set(sections) == {
        "capture_boundaries",
        "forge_handoff",
        "next_gap",
        "replay_generalization",
        "skillization_artifact",
        "stage_status",
        "teaching_contract",
    }
    assert all(item["visible"] for item in sections.values())

    actions = {item["id"]: item for item in body["operator_actions"]}
    assert set(actions) == {
        "label_intent",
        "prepare_skillization_artifact",
        "review_replay",
        "stage_forge_handoff",
        "start_teaching_session",
    }
    assert all(item["enabled"] is False for item in actions.values())

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["forge_handoff_contract_ready"]["passed"] is True
    assert checks["apprenticeship_sections_visible"]["passed"] is True
    assert checks["operator_actions_declared_but_disabled"]["passed"] is True
    assert checks["ambient_capture_controls_denied"]["passed"] is True
    assert checks["write_and_promotion_controls_denied"]["passed"] is True
