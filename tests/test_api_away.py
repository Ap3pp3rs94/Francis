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
    assert body["next_smallest_truthful_gap"] == "stage10_away_safe_task_classes"

    deliverables = {item["id"]: item for item in body["deliverables"]}
    assert deliverables["stage9_ledger_closure_backstop"]["ready"] is True
    assert deliverables["away_mode_visibility"]["ready"] is True
    assert deliverables["approvals_queue_visibility"]["ready"] is True
    assert deliverables["away_safe_task_classes"]["ready"] is False
    assert deliverables["autonomy_budgets"]["ready"] is False
    assert deliverables["shift_reports"]["ready"] is False
    assert deliverables["return_briefing_flow"]["ready"] is False
