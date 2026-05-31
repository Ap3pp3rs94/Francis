from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


def _write_stage9_closure_receipt(data_root: Path, *, receipt_id: str = "takeover_stage9_closure_test") -> None:
    path = data_root / "logs" / "takeover" / "stage9_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "francis.stage9.takeover.stage9_operator_stage_closure_decision_receipt",
                "receipt_id": receipt_id,
                "stage": "Stage 9 / Takeover (Pilot Mode)",
                "source_id": "takeover",
                "target": "stage9_takeover",
                "actor": "test.operator",
                "decision": "close_stage9",
                "completion_review_ready": True,
                "stage9_closed_by_receipt": True,
                "marks_runtime_stage_state": False,
                "recorded_ts": 1_800_000_000,
                "governance": {
                    "explicit_operator_decision": True,
                    "stage_closure_decision": True,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_away_status_waits_for_stage9_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/away/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage10.away.status"
    assert body["status"] == "awaiting_stage9_ledger_closure"
    assert body["stage9_closed_by_receipt"] is False
    assert body["away_mode_ready"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tasks"] is False
    assert body["runs_shell"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["away_autonomy_not_enabled_by_status"] is True
    assert body["governance"]["does_not_start_background_work"] is True
    assert body["next_smallest_truthful_gap"] == "stage9_ledger_closure"


def test_away_status_projects_stage10_groundwork_after_stage9_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_away_test")

    response = TestClient(create_app()).get("/away/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "stage10_groundwork_ready"
    assert body["stage10_closed_by_receipt"] is False
    assert body["stage10_latest_closure_receipt_id"] == ""
    assert body["stage9_closed_by_receipt"] is True
    assert body["stage9_latest_closure_receipt_id"] == "takeover_stage9_closure_away_test"
    assert body["stage9_next_smallest_truthful_gap"] == "stage9_ledger_closure"
    assert body["away_declared"] is False
    assert body["away_groundwork_ready"] is True
    assert body["away_mode_ready"] is False
    assert body["stage10_completion_review_route"] == "/away/completion-review"
    assert body["stage10_completion_review_ready"] is False
    assert body["stage10_closure_decision_route"] == "/away/stage-closure-decision"
    assert body["stage10_closure_decision_readback_route"] == "/away/stage-closure-decisions"
    assert body["live_away_progress_sample_ready"] is False
    assert body["reads_receipts"] is True
    assert body["writes_receipts"] is False
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["routes"]["stage9_closure_readback"] == "/takeover/stage-closure-decisions"
    assert body["routes"]["operator_mode"] == "/system/operator_mode"
    assert body["routes"]["safe_task_classes"] == "/away/safe-task-classes"
    assert body["routes"]["autonomy_budgets"] == "/away/autonomy-budgets"
    assert body["routes"]["shift_report"] == "/away/shift-report"
    assert body["routes"]["return_briefing"] == "/away/return-briefing"
    assert body["routes"]["completion_review"] == "/away/completion-review"
    assert body["routes"]["live_progress_samples"] == "/away/live-progress-samples"
    assert body["routes"]["live_progress_sample"] == "/away/live-progress-sample"
    assert body["routes"]["stage_closure_decision"] == "/away/stage-closure-decision"
    assert body["routes"]["stage_closure_decisions"] == "/away/stage-closure-decisions"
    assert body["governance"]["does_not_claim_away_completion_from_groundwork"] is True
    assert body["governance"]["requires_live_progress_sample_before_completion"] is True
    assert body["next_smallest_truthful_gap"] == "stage10_live_away_progress_sample"

    deliverables = {item["id"]: item for item in body["deliverables"]}
    assert deliverables["stage9_ledger_closure_backstop"]["ready"] is True
    assert deliverables["away_mode_visibility"]["ready"] is True
    assert deliverables["approvals_queue_visibility"]["ready"] is True
    assert deliverables["away_safe_task_classes"]["ready"] is True
    assert deliverables["autonomy_budgets"]["ready"] is True
    assert deliverables["shift_reports"]["ready"] is True
    assert deliverables["return_briefing_flow"]["ready"] is True


def test_away_safe_task_classes_are_readonly_and_gated(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_safe_classes_test")

    response = TestClient(create_app()).get("/away/safe-task-classes")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage10.away.safe_task_classes"
    assert body["status"] == "ready"
    assert body["stage9_closed_by_receipt"] is True
    assert body["away_safe_task_classes_ready"] is True
    assert body["class_count"] == 4
    assert body["writes_receipts"] is False
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["safe_task_class_contract_only"] is True
    assert body["governance"]["does_not_enable_away_autonomy"] is True
    assert body["governance"]["approval_decisions_remain_operator_gated"] is True
    assert body["next_smallest_truthful_gap"] == "stage10_autonomy_budgets"

    classes = {item["id"]: item for item in body["classes"]}
    assert set(classes) == {
        "approval_queue_triage",
        "continuity_monitoring",
        "safe_plan_preparation",
        "shift_report_draft",
    }
    for item in classes.values():
        assert item["allowed_effect"] in {"read_only", "read_only_priority_projection", "draft_only"}
        assert item["may_execute_tools"] is False
        assert item["may_run_shell"] is False
        assert item["may_run_git"] is False
        assert item["may_start_processes"] is False
        assert item["may_write_memory"] is False
        assert item["may_write_files"] is False
        assert item["may_send_external_messages"] is False
        assert item["may_decide_approvals"] is False
        assert item["requires_operator_approval_for_execution"] is True
        assert item["requires_autonomy_budget_before_execution"] is True

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["stage9_closure_backstop"]["passed"] is True
    assert checks["classes_declared"]["passed"] is True
    assert checks["effects_limited_to_read_or_draft"]["passed"] is True
    assert checks["execution_requires_future_budget_and_approval"]["passed"] is True
    assert checks["risky_actions_denied"]["passed"] is True


def test_away_autonomy_budgets_are_bounded_and_non_executing(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_budgets_test")

    response = TestClient(create_app()).get("/away/autonomy-budgets")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage10.away.autonomy_budgets"
    assert body["status"] == "ready"
    assert body["safe_task_classes_ready"] is True
    assert body["autonomy_budgets_ready"] is True
    assert body["budget_count"] == 4
    assert body["activates_away_autonomy"] is False
    assert body["writes_receipts"] is False
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["autonomy_budget_contract_only"] is True
    assert body["governance"]["does_not_activate_away_autonomy"] is True
    assert body["governance"]["approval_required_before_execution"] is True
    assert body["next_smallest_truthful_gap"] == "stage10_shift_reports"

    budgets = {item["class_id"]: item for item in body["budgets"]}
    assert set(budgets) == {
        "approval_queue_triage",
        "continuity_monitoring",
        "safe_plan_preparation",
        "shift_report_draft",
    }
    for item in budgets.values():
        assert 0 < item["max_items"] <= 50
        assert 0 < item["max_duration_minutes"] <= 120
        assert item["allowed_effect"] in {"read_only", "read_only_priority_projection", "draft_only"}
        assert item["may_execute_tools"] is False
        assert item["may_run_shell"] is False
        assert item["may_run_git"] is False
        assert item["may_start_processes"] is False
        assert item["may_write_memory"] is False
        assert item["may_write_files"] is False
        assert item["may_send_external_messages"] is False
        assert item["may_decide_approvals"] is False
        assert item["requires_operator_approval_for_execution"] is True
        assert item["budget_activation_required"] is True

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["safe_task_classes_ready"]["passed"] is True
    assert checks["budgets_declared_for_each_safe_class"]["passed"] is True
    assert checks["budgets_are_bounded"]["passed"] is True
    assert checks["budget_effects_match_safe_classes"]["passed"] is True
    assert checks["budget_activation_gated"]["passed"] is True
    assert checks["risky_actions_denied"]["passed"] is True


def test_away_shift_report_is_readonly_and_receipt_grounded(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_shift_report_test")

    response = TestClient(create_app()).get("/away/shift-report")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage10.away.shift_report"
    assert body["status"] == "ready"
    assert body["shift_report_ready"] is True
    assert body["stage9_closed_by_receipt"] is True
    assert body["stage9_latest_closure_receipt_id"] == "takeover_stage9_closure_shift_report_test"
    assert body["autonomy_budgets_ready"] is True
    assert body["section_count"] == 5
    assert body["writes_receipts"] is False
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["shift_report_projection_only"] is True
    assert body["governance"]["does_not_claim_background_progress"] is True
    assert body["governance"]["does_not_activate_away_autonomy"] is True
    assert body["next_smallest_truthful_gap"] == "stage10_return_briefing_flow"

    sections = {item["id"]: item for item in body["sections"]}
    assert set(sections) == {"away_budget", "backlog", "continuity", "operator_mode", "stage9_closure"}
    assert "takeover_stage9_closure_shift_report_test" in sections["stage9_closure"]["summary"]
    assert "autonomy activation remains off" in sections["away_budget"]["summary"]
    assert sections["backlog"]["summary"]
    assert sections["continuity"]["summary"]

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["autonomy_budgets_ready"]["passed"] is True
    assert checks["required_sections_present"]["passed"] is True
    assert checks["sections_have_summaries"]["passed"] is True
    assert checks["read_only_report"]["passed"] is True


def test_away_return_briefing_flow_is_readonly_and_operator_led(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_return_briefing_test")

    response = TestClient(create_app()).get("/away/return-briefing")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage10.away.return_briefing"
    assert body["status"] == "ready"
    assert body["return_briefing_ready"] is True
    assert body["shift_report_ready"] is True
    assert body["continuity_headline"]
    assert body["step_count"] == 4
    assert body["writes_receipts"] is False
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["return_briefing_flow_only"] is True
    assert body["governance"]["operator_reentry_decision_required"] is True
    assert body["governance"]["does_not_claim_background_progress"] is True
    assert body["governance"]["does_not_activate_away_autonomy"] is True
    assert body["next_smallest_truthful_gap"] == "stage10_completion_review"

    steps = {item["id"]: item for item in body["steps"]}
    assert set(steps) == {
        "choose_control_mode",
        "resume_continuity_focus",
        "review_pending_approvals",
        "review_shift_report",
    }
    assert steps["review_shift_report"]["route"] == "/away/shift-report"
    assert steps["review_pending_approvals"]["action"] == "operator_review"
    assert steps["choose_control_mode"]["action"] == "operator_decision"

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["shift_report_ready"]["passed"] is True
    assert checks["continuity_headline_available"]["passed"] is True
    assert checks["required_reentry_steps_present"]["passed"] is True
    assert checks["operator_decision_required"]["passed"] is True


def test_away_completion_review_blocks_until_live_progress_sample(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_completion_review_test")

    response = TestClient(create_app()).get("/away/completion-review")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage10.away.completion_review"
    assert body["status"] == "blocked"
    assert body["stage10_completion_review_ready"] is False
    assert body["stage10_closed_by_receipt"] is False
    assert body["stage_closure_decision_required"] is True
    assert body["stage9_closed_by_receipt"] is True
    assert body["stage9_latest_closure_receipt_id"] == "takeover_stage9_closure_completion_review_test"
    assert body["away_groundwork_ready"] is True
    assert body["away_mode_ready"] is False
    assert body["live_away_progress_sample_ready"] is False
    assert body["ready_count"] == body["required_count"] == 8
    assert body["writes_receipts"] is False
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["marks_stage_closed"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["completion_review_only"] is True
    assert body["governance"]["stage_closure_decision_required"] is True
    assert body["governance"]["requires_live_progress_sample_before_completion"] is True
    assert body["governance"]["does_not_claim_background_progress"] is True
    assert body["governance"]["does_not_activate_away_autonomy"] is True
    assert body["governance"]["does_not_mark_stage_closed"] is True
    assert body["routes"]["completion_review"] == "/away/completion-review"
    assert body["next_smallest_truthful_gap"] == "stage10_live_away_progress_sample"

    checks = {item["id"]: item for item in body["checks"]}
    assert checks["stage9_ledger_closure_backstop"]["passed"] is True
    assert checks["groundwork_deliverables_ready"]["passed"] is True
    assert checks["safe_task_classes_surface_ready"]["passed"] is True
    assert checks["autonomy_budgets_surface_ready"]["passed"] is True
    assert checks["shift_report_surface_ready"]["passed"] is True
    assert checks["return_briefing_surface_ready"]["passed"] is True
    assert checks["live_away_progress_sample_ready"]["passed"] is False
    assert checks["live_away_progress_sample_ready"]["evidence"] == "not_yet_recorded"
    assert checks["risky_actions_remain_gated"]["passed"] is True
    assert checks["stage_not_marked_closed_by_review"]["passed"] is True


def test_away_live_progress_sample_denies_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_progress_denied_test")

    client = TestClient(create_app())
    response = client.post(
        "/away/live-progress-sample",
        json={
            "actor": "test.away.progress",
            "reason": "missing progress scope",
            "summary": "should not record",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["writes_receipt"] is False
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["required_scope"] == "away.progress.write"
    assert not (data_root / "logs" / "away" / "live_progress_sample_receipts.jsonl").exists()


def test_away_live_progress_sample_records_receipt_and_unblocks_completion_review(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.away.progress": ["away.progress.write"]}),
    )
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_progress_sample_test")

    client = TestClient(create_app())
    response = client.post(
        "/away/live-progress-sample",
        json={
            "actor": "test.away.progress",
            "reason": "record live away progress sample token=awayprogressreasonsecret123",
            "sample_type": "return_briefing_review",
            "summary": "Prepared return briefing from existing readbacks token=awayprogresssummarysecret123",
            "next_recommendation": "Operator should review the shift report.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage10.away.live_progress_sample.record"
    assert body["status"] == "recorded"
    assert body["receipt_id"].startswith("away_live_progress_")
    assert body["sample_type"] == "return_briefing_review"
    assert body["writes_receipt"] is True
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["required_scope"] == "away.progress.write"
    assert body["governance"]["grounded_in_existing_readbacks"] is True
    assert body["governance"]["does_not_activate_away_autonomy"] is True
    assert body["next_smallest_truthful_gap"] == "stage10_completion_review"

    receipt = body["receipt"]
    assert receipt["kind"] == "francis.stage10.away.live_progress_sample_receipt"
    assert receipt["receipt_id"] == body["receipt_id"]
    assert receipt["actor"] == "test.away.progress"
    assert receipt["stage9_closure_receipt_id"] == "takeover_stage9_closure_progress_sample_test"
    assert receipt["groundwork_ready"] is True
    assert receipt["ready_count"] == receipt["required_count"] == 8
    assert receipt["shift_report_ready"] is True
    assert receipt["return_briefing_ready"] is True
    assert receipt["live_away_progress_sample_ready"] is True
    assert receipt["governance"]["required_scope"] == "away.progress.write"
    assert receipt["governance"]["progress_sample_not_background_autonomy"] is True
    assert receipt["governance"]["does_not_write_tasks"] is True
    assert receipt["governance"]["does_not_write_memory"] is True

    receipt_text = json.dumps(receipt, sort_keys=True)
    assert "awayprogressreasonsecret123" not in receipt_text
    assert "awayprogresssummarysecret123" not in receipt_text

    readback = client.get("/away/live-progress-samples").json()
    assert readback["ok"] is True
    assert readback["kind"] == "francis.stage10.away.live_progress_sample_receipts"
    assert readback["status"] == "ready"
    assert readback["count"] == 1
    assert readback["latest_receipt_id"] == body["receipt_id"]
    assert readback["items"][0]["receipt_id"] == body["receipt_id"]

    status = client.get("/away/status").json()
    assert status["away_groundwork_ready"] is True
    assert status["live_away_progress_sample_ready"] is True
    assert status["latest_live_progress_sample_receipt_id"] == body["receipt_id"]
    assert status["stage10_completion_review_ready"] is True
    assert status["away_mode_ready"] is True
    assert status["next_smallest_truthful_gap"] == "stage10_stage_closure_decision"

    review = client.get("/away/completion-review").json()
    assert review["status"] == "ready"
    assert review["stage10_completion_review_ready"] is True
    assert review["latest_live_progress_sample_receipt_id"] == body["receipt_id"]
    assert review["next_smallest_truthful_gap"] == "stage10_stage_closure_decision"
    checks = {item["id"]: item for item in review["checks"]}
    assert checks["live_away_progress_sample_ready"]["passed"] is True
    assert checks["live_away_progress_sample_ready"]["evidence"] == body["receipt_id"]
    assert all(item["passed"] for item in review["checks"])


def test_away_stage10_closure_decision_denies_without_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_stage10_denied_test")

    response = TestClient(create_app()).post(
        "/away/stage-closure-decision",
        json={
            "actor": "test.away.closure",
            "reason": "missing closure scope",
            "decision": "close_stage10",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["writes_receipt"] is False
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["required_scope"] == "away.stage10.closure.write"
    assert not (data_root / "logs" / "away" / "stage10_operator_stage_closure_decisions.jsonl").exists()


def test_away_stage10_closure_decision_records_receipt_after_completion_review(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                "test.away.progress": ["away.progress.write"],
                "test.away.closure": ["away.stage10.closure.write"],
            }
        ),
    )
    _write_stage9_closure_receipt(data_root, receipt_id="takeover_stage9_closure_stage10_close_test")

    client = TestClient(create_app())
    sample = client.post(
        "/away/live-progress-sample",
        json={
            "actor": "test.away.progress",
            "reason": "stage10 closure sample",
            "sample_type": "return_briefing_review",
            "summary": "Grounded sample before closure.",
        },
    ).json()
    assert sample["ok"] is True
    assert sample["receipt_id"]

    response = client.post(
        "/away/stage-closure-decision",
        json={
            "actor": "test.away.closure",
            "reason": "close stage 10 token=awayclosereasonsecret123",
            "decision": "close_stage10",
            "notes": "Completion review and live sample are present token=awayclosenotessecret123",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage10.away.stage10_operator_stage_closure_decision.record"
    assert body["status"] == "recorded"
    assert body["receipt_id"].startswith("away_stage10_closure_")
    assert body["decision"] == "close_stage10"
    assert body["stage10_closed_by_receipt"] is True
    assert body["writes_receipt"] is True
    assert body["writes_tasks"] is False
    assert body["writes_memory"] is False
    assert body["runs_tools"] is False
    assert body["runs_shell"] is False
    assert body["runs_git"] is False
    assert body["starts_processes"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["marks_runtime_stage_state"] is False
    assert body["governance"]["required_scope"] == "away.stage10.closure.write"
    assert body["governance"]["does_not_mutate_runtime_stage_state"] is True
    assert body["next_smallest_truthful_gap"] == "stage10_ledger_closure"

    receipt = body["receipt"]
    assert receipt["kind"] == "francis.stage10.away.stage10_operator_stage_closure_decision_receipt"
    assert receipt["receipt_id"] == body["receipt_id"]
    assert receipt["actor"] == "test.away.closure"
    assert receipt["completion_review_ready"] is True
    assert receipt["stage10_closed_by_receipt"] is True
    assert receipt["stage9_closure_receipt_id"] == "takeover_stage9_closure_stage10_close_test"
    assert receipt["live_progress_sample_receipt_id"] == sample["receipt_id"]
    assert receipt["marks_runtime_stage_state"] is False
    assert receipt["governance"]["permission_scope"] == "away.stage10.closure.write"
    assert receipt["governance"]["requires_live_progress_sample"] is True
    assert receipt["governance"]["does_not_mutate_runtime_stage_state"] is True
    receipt_text = json.dumps(receipt, sort_keys=True)
    assert "awayclosereasonsecret123" not in receipt_text
    assert "awayclosenotessecret123" not in receipt_text

    readback = client.get("/away/stage-closure-decisions").json()
    assert readback["ok"] is True
    assert readback["kind"] == "francis.stage10.away.stage10_operator_stage_closure_decision_receipts"
    assert readback["status"] == "closed"
    assert readback["latest_receipt_id"] == body["receipt_id"]
    assert readback["stage10_closed_by_receipt"] is True
    assert readback["marks_runtime_stage_state"] is False
    assert readback["writes_receipts"] is False
    assert readback["writes_tasks"] is False
    assert readback["writes_memory"] is False
    assert readback["runs_tools"] is False
    assert readback["runs_shell"] is False
    assert readback["runs_git"] is False
    assert readback["grants_execution_authority"] is False
    assert readback["grants_mutation_authority"] is False
    assert readback["governance"]["stage_closure_decision_receipt_readback"] is True
    assert readback["governance"]["does_not_mutate_runtime_stage_state"] is True
    assert readback["next_smallest_truthful_gap"] == "stage10_ledger_closure"

    status = client.get("/away/status").json()
    assert status["status"] == "stage10_closed_by_receipt"
    assert status["stage10_closed_by_receipt"] is True
    assert status["stage10_latest_closure_receipt_id"] == body["receipt_id"]
    assert status["next_smallest_truthful_gap"] == "stage10_ledger_closure"

    review = client.get("/away/completion-review").json()
    assert review["stage10_completion_review_ready"] is True
    assert review["stage10_closed_by_receipt"] is True
    assert review["stage_closure_decision_required"] is False
    assert review["next_smallest_truthful_gap"] == "stage10_ledger_closure"
