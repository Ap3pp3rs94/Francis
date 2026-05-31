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
    assert body["stage9_closed_by_receipt"] is True
    assert body["stage9_latest_closure_receipt_id"] == "takeover_stage9_closure_away_test"
    assert body["stage9_next_smallest_truthful_gap"] == "stage9_ledger_closure"
    assert body["away_declared"] is False
    assert body["away_mode_ready"] is False
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
    assert body["next_smallest_truthful_gap"] == "stage10_return_briefing_flow"

    deliverables = {item["id"]: item for item in body["deliverables"]}
    assert deliverables["stage9_ledger_closure_backstop"]["ready"] is True
    assert deliverables["away_mode_visibility"]["ready"] is True
    assert deliverables["approvals_queue_visibility"]["ready"] is True
    assert deliverables["away_safe_task_classes"]["ready"] is True
    assert deliverables["autonomy_budgets"]["ready"] is True
    assert deliverables["shift_reports"]["ready"] is True
    assert deliverables["return_briefing_flow"]["ready"] is False


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
