from __future__ import annotations

from pathlib import Path


def test_artifact_inspect_lists_metadata_without_file_contents(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    artifact_dir = data_root / "artifacts" / "supervised_exec" / "apr_alpha"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "result.json").write_text('{"token":"raw-secret-value"}', encoding="utf-8")
    (artifact_dir / "stdout.txt").write_text("hello from artifact", encoding="utf-8")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/artifacts/inspect", params={"artifact_dir": str(artifact_dir)})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["exists"] is True
    assert body["kind"] == "directory"
    assert body["relative_path"] == "supervised_exec/apr_alpha"
    assert body["entry_count"] == 2
    assert body["truncated"] is False
    assert [entry["name"] for entry in body["entries"]] == ["result.json", "stdout.txt"]
    assert all("raw-secret-value" not in str(entry) for entry in body["entries"])
    assert "raw-secret-value" not in str(body)


def test_artifact_inspect_accepts_artifact_root_relative_handles(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    artifact_file = data_root / "artifacts" / "plugins" / "demo.zip"
    artifact_file.parent.mkdir(parents=True)
    artifact_file.write_bytes(b"zip-bytes")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/artifacts/inspect", params={"artifact_dir": "plugins/demo.zip"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "file"
    assert body["relative_path"] == "plugins/demo.zip"
    assert body["bytes"] == len(b"zip-bytes")
    assert body["entries"] == []


def test_artifact_inspect_projects_originating_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    artifact_dir = data_root / "artifacts" / "supervised_exec" / "apr_receipt"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "result.json").write_text("{}", encoding="utf-8")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.chat.continuity.ledger import append

    append(
        "assistant",
        "Mission operation receipt with artifact handle.",
        {
            "subsystem": "operations.runtime",
            "domain": "operations",
            "scope": "mission.loop",
            "mission_id": "msn_artifact_origin",
            "operation_id": "tsk_artifact_origin",
            "approval_id": "apr_artifact_origin",
            "trace_id": "trace_artifact_origin",
            "run_id": "run_artifact_origin",
            "artifact_dir": str(artifact_dir),
            "operation_status": "failed",
            "operation_error": "plugin_id_required",
            "result_message": "Plugin id is required. password=artifactsecret123",
            "recovery_next_step": "review_operation_detail token=artifactrecovery123",
            "plan_status": "in_progress",
            "plan_current_step_id": "understand",
            "plan_current_step_title": "Understand goal + constraints",
            "plan_step_count": "4",
            "plan_checkpoint_count": 3,
            "active_stage": "deadletter",
            "handoff_stage": "deadletter",
            "handoff_action": "retry_or_deadletter",
            "handoff_gate": "operator_review",
            "handoff_approval_id": "apr_artifact_origin",
            "handoff_approval_status": "approved",
            "handoff_operation_id": "tsk_artifact_origin",
            "handoff_trace_id": "trace_artifact_origin",
            "handoff_run_id": "run_artifact_origin",
            "handoff_artifact_dir": str(artifact_dir),
            "current_task_source": "terminal_operation_receipt",
            "current_task_gate": "operator_review",
            "current_task_approval_id": "apr_artifact_origin",
            "current_task_approval_status": "approved",
            "current_task_previous_approval_id": "apr_artifact_previous",
            "current_task_previous_approval_status": "approved",
            "current_task_operation_id": "tsk_artifact_origin",
            "current_task_operation_name": "plugin.run",
            "current_task_operation_plane": "P7_EXECUTION",
            "current_task_advance_action": "run_operation",
            "current_task_trace_id": "trace_artifact_origin",
            "current_task_run_id": "run_artifact_origin",
            "current_task_artifact_dir": str(artifact_dir),
            "current_task_next_step": "review_operation_detail",
        },
    )

    client = TestClient(create_app())
    response = client.get("/artifacts/inspect", params={"artifact_dir": "supervised_exec/apr_receipt"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["relative_path"] == "supervised_exec/apr_receipt"
    receipt = body["originating_receipt"]
    assert receipt["source"] == "continuity.ledger"
    assert receipt["matched_artifact_field"] == "artifact_dir"
    assert receipt["mission_id"] == "msn_artifact_origin"
    assert receipt["operation_id"] == "tsk_artifact_origin"
    assert receipt["approval_id"] == "apr_artifact_origin"
    assert receipt["trace_id"] == "trace_artifact_origin"
    assert receipt["run_id"] == "run_artifact_origin"
    assert receipt["operation_status"] == "failed"
    assert receipt["operation_error"] == "plugin_id_required"
    assert receipt["result_message"] == "Plugin id is required. password=[REDACTED:secret]"
    assert receipt["recovery_next_step"] == "review_operation_detail token=[REDACTED:secret]"
    assert receipt["plan_status"] == "in_progress"
    assert receipt["plan_current_step_id"] == "understand"
    assert receipt["plan_current_step_title"] == "Understand goal + constraints"
    assert receipt["plan_step_count"] == 4
    assert receipt["plan_checkpoint_count"] == 3
    assert receipt["active_stage"] == "deadletter"
    assert receipt["handoff_stage"] == "deadletter"
    assert receipt["handoff_action"] == "retry_or_deadletter"
    assert receipt["handoff_gate"] == "operator_review"
    assert receipt["handoff_approval_id"] == "apr_artifact_origin"
    assert receipt["handoff_approval_status"] == "approved"
    assert receipt["handoff_operation_id"] == "tsk_artifact_origin"
    assert receipt["handoff_trace_id"] == "trace_artifact_origin"
    assert receipt["handoff_run_id"] == "run_artifact_origin"
    assert receipt["handoff_artifact_dir"] == str(artifact_dir)
    assert receipt["current_task_source"] == "terminal_operation_receipt"
    assert receipt["current_task_gate"] == "operator_review"
    assert receipt["current_task_approval_id"] == "apr_artifact_origin"
    assert receipt["current_task_approval_status"] == "approved"
    assert receipt["current_task_previous_approval_id"] == "apr_artifact_previous"
    assert receipt["current_task_previous_approval_status"] == "approved"
    assert receipt["current_task_operation_id"] == "tsk_artifact_origin"
    assert receipt["current_task_operation_name"] == "plugin.run"
    assert receipt["current_task_operation_plane"] == "P7_EXECUTION"
    assert receipt["current_task_advance_action"] == "run_operation"
    assert receipt["current_task_trace_id"] == "trace_artifact_origin"
    assert receipt["current_task_run_id"] == "run_artifact_origin"
    assert receipt["current_task_artifact_dir"] == str(artifact_dir)
    assert receipt["current_task_next_step"] == "review_operation_detail"
    assert receipt["references"]["artifact_dir"] == str(artifact_dir)
    assert "artifactsecret123" not in str(body)
    assert "artifactrecovery123" not in str(body)


def test_artifact_inspect_rejects_paths_outside_artifact_root(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    outside = tmp_path / "outside.txt"
    outside.write_text("not an artifact", encoding="utf-8")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/artifacts/inspect", params={"artifact_dir": str(outside)})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "artifact_outside_data_root"
    assert str(outside) in body["artifact_dir"]
    assert body["next_step"] == "inspect_originating_receipt"
    assert body["retryable"] is False
    assert "data/artifacts" in body["recovery_hint"]


def test_artifact_inspect_reports_missing_handles_without_creating_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    missing = data_root / "artifacts" / "missing" / "run_alpha"

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/artifacts/inspect", params={"artifact_dir": str(missing)})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "artifact_not_found"
    assert body["exists"] is False
    assert body["next_step"] == "refresh_originating_receipt"
    assert body["retryable"] is True
    assert "latest artifact_dir" in body["recovery_hint"]
    assert not missing.exists()
