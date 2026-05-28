from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.telemetry.status import redact_telemetry_value


def test_telemetry_status_projects_stage7_readonly_sources(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.status"
    assert body["stage"] == "Stage 7 / Telemetry MVP"
    assert body["status"] in {"active", "inactive"}
    assert body["active"] is (body["active_source_total"] > 0)
    assert body["claim"] in {
        "telemetry_posture_contract_only",
        "explicit_telemetry_readback_available",
        "explicit_telemetry_events_recorded",
    }
    assert body["source_total"] == 3
    assert body["active_source_total"] == sum(1 for source in body["sources"] if source["active"])
    assert body["next_smallest_truthful_gap"] == "stage7_context_awareness_action_quality_feedback"

    sources = {source["id"]: source for source in body["sources"]}
    assert set(sources) == {"terminal", "git", "ide_diagnostics"}
    assert sources["terminal"]["status"] == "write_scope_required"
    assert sources["terminal"]["active"] is False
    assert sources["terminal"]["retention"]["event_count"] == 0
    assert sources["terminal"]["routes"]["record"] == "/telemetry/terminal/events"
    assert sources["git"]["routes"]["status"] == "/telemetry/git/status"
    assert sources["git"]["hidden_sensing"] is False
    assert sources["git"]["authority"]["execution_authority"] is False
    assert sources["ide_diagnostics"]["status"] == "write_scope_required"
    assert sources["ide_diagnostics"]["active"] is False
    assert sources["ide_diagnostics"]["routes"]["record"] == "/telemetry/ide-diagnostics/events"
    assert sources["ide_diagnostics"]["routes"]["events"] == "/telemetry/ide-diagnostics/events"
    for source in sources.values():
        assert source["visible_indicator"] is True
        assert source["hidden_sensing"] is False
        assert source["scope"]["denied_by_default"] is True
        assert source["retention"]["stores_raw_events"] is False
        assert source["redaction"]["redact_before_storage"] is True
        assert source["authority"]["telemetry_collection"] is False
        assert source["authority"]["execution_authority"] is False
        assert source["authority"]["memory_write"] is False

    assert body["redaction"]["stores_raw_secret_values"] is False
    assert body["retention"]["stores_raw_events"] is False
    if body["active"] and body["retention"]["event_count"] == 0:
        assert body["claim"] == "explicit_telemetry_readback_available"
        assert body["retention"]["status"] == "read_only_snapshot"
        assert body["sensing"]["status"] == "explicit_readback_available"
    elif body["retention"]["event_count"] > 0:
        assert body["claim"] == "explicit_telemetry_events_recorded"
        assert body["retention"]["status"] == "bounded_redacted_events"
        assert body["sensing"]["status"] == "explicit_events_recorded"
    else:
        assert body["claim"] == "telemetry_posture_contract_only"
        assert body["retention"]["status"] == "none"
        assert body["sensing"]["status"] == "inactive"
    assert body["sensing"]["hidden_sensing"] is False
    assert body["governance"]["read_only_contract"] is True
    assert body["governance"]["telemetry_collection"] is False
    assert body["governance"]["telemetry_is_untrusted_input"] is True
    assert body["governance"]["grants_execution_authority"] is False
    assert not data_root.exists()


def test_telemetry_redaction_uses_governed_redaction() -> None:
    payload = {
        "cwd": "D:/Francis",
        "operator_note": "token=stage7secret123",
        "nested": {"api_key": "stage7apikey123"},
    }

    redacted = redact_telemetry_value(payload)

    assert redacted["cwd"] == "D:/Francis"
    assert redacted["operator_note"] == "token=[REDACTED:secret]"
    assert redacted["nested"]["api_key"] == "[REDACTED:secret]"


def test_telemetry_context_projects_redacted_assist_surface(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                "test.telemetry.write": ["telemetry.terminal.write"],
                "test.telemetry.ide": ["telemetry.ide_diagnostics.write"],
            }
        ),
    )

    client = TestClient(create_app())
    client.post(
        "/telemetry/terminal/events",
        json={
            "actor": "test.telemetry.write",
            "reason": "record terminal context token=terminalreasonsecret123",
            "command": "pytest token=terminalcommandsecret123",
            "cwd": str(tmp_path),
            "exit_code": 1,
            "operation_id": "op_context_terminal",
        },
    )
    client.post(
        "/telemetry/ide-diagnostics/events",
        json={
            "actor": "test.telemetry.ide",
            "reason": "record IDE context token=idereasonsecret123",
            "file": "src/francis/password=idefilesecret123.py",
            "diagnostics": [{"severity": "error", "code": "F821", "message": "token=idemessagesecret123"}],
            "operation_id": "op_context_ide",
        },
    )

    body = client.get("/telemetry/context?surface=chat").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context"
    assert body["surface"] == "chat"
    assert body["status"] == "available"
    assert body["visible_indicator"] is True
    assert body["hidden_sensing"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["does_not_expand_collection_scope"] is True
    assert body["governance"]["telemetry_is_untrusted_input"] is True
    assert body["next_smallest_truthful_gap"] == "stage7_context_awareness_action_quality_feedback"

    source_ids = {item["source_id"] for item in body["context_items"]}
    assert "terminal" in source_ids
    assert "ide_diagnostics" in source_ids
    assert body["prompt_lines"]

    context_text = json.dumps(body, sort_keys=True)
    for raw_secret in (
        "terminalreasonsecret123",
        "terminalcommandsecret123",
        "idereasonsecret123",
        "idefilesecret123",
        "idemessagesecret123",
    ):
        assert raw_secret not in context_text
    assert "[REDACTED:secret]" in context_text


def test_terminal_telemetry_denies_event_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({}))

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/terminal/events",
        json={
            "actor": "test.telemetry.write",
            "reason": "record denied command outcome",
            "command": "echo denied",
            "cwd": str(tmp_path),
            "exit_code": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert not data_root.exists()


def test_terminal_telemetry_records_redacted_explicit_command_event(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({"test.telemetry.write": ["telemetry.terminal.write"]}))

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/terminal/events",
        json={
            "actor": "test.telemetry.write",
            "reason": "record terminal outcome token=reasonsecret123",
            "command": "echo token=commandsecret123",
            "cwd": str(tmp_path / "password=cwdsecret123"),
            "shell": "powershell",
            "exit_code": 0,
            "duration_ms": 42,
            "operation_id": "op_terminal",
            "approval_id": "apr_terminal",
            "trace_id": "trace_terminal",
            "run_id": "run_terminal",
            "artifact_dir": "supervised_exec/apr_terminal",
            "tags": ["stage7", "token=tagsecret123"],
            "meta": {"api_key": "metasecret123", "ticket": "TEL-7"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["governance"]["grants_execution_authority"] is False
    item = body["item"]
    assert item["kind"] == "francis.stage7.telemetry.terminal_event"
    assert item["capture_mode"] == "explicit_command_outcome_report"
    assert item["hidden_sensing"] is False
    assert item["governance"]["stores_stdout_stderr"] is False
    assert item["command"] == "echo token=[REDACTED:secret]"
    assert "stdout_tail" not in item
    assert "stderr_tail" not in item
    assert item["operation_id"] == "op_terminal"
    assert item["approval_id"] == "apr_terminal"
    assert item["trace_id"] == "trace_terminal"
    assert item["run_id"] == "run_terminal"
    assert item["artifact_dir"] == "supervised_exec/apr_terminal"
    assert item["meta"]["api_key"] == "[REDACTED:secret]"
    assert item["meta"]["ticket"] == "TEL-7"

    raw_text = (data_root / "logs" / "telemetry" / "terminal_events.jsonl").read_text(encoding="utf-8")
    for raw_secret in (
        "reasonsecret123",
        "commandsecret123",
        "cwdsecret123",
        "tagsecret123",
        "metasecret123",
    ):
        assert raw_secret not in raw_text

    listed = client.get("/telemetry/terminal/events?limit=5").json()
    assert listed["ok"] is True
    assert listed["total"] == 1
    assert listed["items"][0]["event_id"] == item["event_id"]

    status = client.get("/telemetry/status").json()
    sources = {source["id"]: source for source in status["sources"]}
    assert status["active"] is True
    assert status["claim"] == "explicit_telemetry_events_recorded"
    assert status["active_source_total"] >= 1
    assert status["retention"]["status"] == "bounded_redacted_events"
    assert status["retention"]["event_count"] == 1
    assert status["sensing"]["status"] == "explicit_events_recorded"
    assert sources["terminal"]["active"] is True
    assert sources["terminal"]["status"] == "explicit_events_recorded"
    assert sources["terminal"]["signals"] == ["command_outcome"]
    assert sources["terminal"]["retention"]["event_count"] == 1
    assert sources["terminal"]["latest_event"]["event_id"] == item["event_id"]


def test_terminal_scope_projects_permission_without_recording(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({"test.telemetry.write": ["telemetry.terminal.write"]}))

    client = TestClient(create_app())
    body = client.get("/telemetry/terminal/scope?actor=test.telemetry.write").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.terminal_scope"
    assert body["status"] == "write_scope_ready"
    assert body["required_scope"] == "telemetry.terminal.write"
    assert body["governance"]["permission_allowed"] is True
    assert body["governance"]["grants_execution_authority"] is False
    assert body["event_count"] == 0
    assert not data_root.exists()


def test_ide_diagnostics_telemetry_denies_event_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({}))

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/ide-diagnostics/events",
        json={
            "actor": "test.telemetry.ide",
            "reason": "record denied diagnostic",
            "file": "src/francis/example.py",
            "diagnostics": [{"severity": "error", "code": "E999", "message": "syntax error"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["source_id"] == "ide_diagnostics"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["required_scope"] == "telemetry.ide_diagnostics.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert not data_root.exists()


def test_ide_diagnostics_records_redacted_explicit_diagnostic_event(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.ide": ["telemetry.ide_diagnostics.write"]}),
    )

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/ide-diagnostics/events",
        json={
            "actor": "test.telemetry.ide",
            "reason": "record IDE diagnostic token=reasonsecret123",
            "source": "vscode",
            "workspace": "D:/Francis",
            "file": "src/francis/password=filesecret123.py",
            "diagnostics": [
                {
                    "severity": "error",
                    "code": "F821",
                    "message": "undefined name token=diagsecret123",
                    "range": {"start_line": 7, "start_character": 3, "end_line": 7, "end_character": 20},
                },
                {
                    "severity": "warning",
                    "code": "W0611",
                    "message": "unused import",
                    "range": {"line": 1, "character": 0},
                },
            ],
            "operation_id": "op_ide",
            "approval_id": "apr_ide",
            "trace_id": "trace_ide",
            "run_id": "run_ide",
            "tags": ["stage7", "token=tagsecret123"],
            "meta": {"api_key": "metasecret123", "ticket": "IDE-7"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["governance"]["grants_execution_authority"] is False
    assert body["governance"]["stores_file_contents"] is False
    item = body["item"]
    assert item["kind"] == "francis.stage7.telemetry.ide_diagnostic_event"
    assert item["capture_mode"] == "explicit_ide_diagnostic_report"
    assert item["hidden_sensing"] is False
    assert item["governance"]["stores_file_contents"] is False
    assert item["file"] == "src/francis/password=[REDACTED:secret]"
    assert item["diagnostic_count"] == 2
    assert item["highest_severity"] == "error"
    assert item["diagnostics"][0]["message"] == "undefined name token=[REDACTED:secret]"
    assert item["diagnostics"][0]["range"]["start_line"] == 7
    assert item["meta"]["api_key"] == "[REDACTED:secret]"
    assert item["meta"]["ticket"] == "IDE-7"

    raw_text = (data_root / "logs" / "telemetry" / "ide_diagnostics.jsonl").read_text(encoding="utf-8")
    for raw_secret in ("reasonsecret123", "filesecret123", "diagsecret123", "tagsecret123", "metasecret123"):
        assert raw_secret not in raw_text

    listed = client.get("/telemetry/ide-diagnostics/events?limit=5").json()
    assert listed["ok"] is True
    assert listed["total"] == 1
    assert listed["items"][0]["event_id"] == item["event_id"]
    assert listed["stores_file_contents"] is False

    scope = client.get("/telemetry/ide-diagnostics/scope?actor=test.telemetry.ide").json()
    assert scope["ok"] is True
    assert scope["status"] == "write_scope_ready"
    assert scope["required_scope"] == "telemetry.ide_diagnostics.write"
    assert scope["governance"]["captures_file_contents"] is False

    status = client.get("/telemetry/status").json()
    sources = {source["id"]: source for source in status["sources"]}
    assert status["active"] is True
    assert status["claim"] == "explicit_telemetry_events_recorded"
    assert sources["ide_diagnostics"]["active"] is True
    assert sources["ide_diagnostics"]["status"] == "explicit_diagnostics_recorded"
    assert sources["ide_diagnostics"]["signals"] == ["diagnostic_summary"]
    assert sources["ide_diagnostics"]["latest_diagnostic"]["event_id"] == item["event_id"]
    assert sources["ide_diagnostics"]["latest_diagnostic"]["file"] == "src/francis/password=[REDACTED:secret]"
    assert sources["ide_diagnostics"]["latest_diagnostic"]["highest_severity"] == "error"


def test_git_telemetry_status_is_readonly_snapshot(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    body = client.get("/telemetry/git/status?limit=5").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.git_status"
    assert body["source_id"] == "git"
    assert body["capture_mode"] == "explicit_git_status_snapshot"
    assert body["watch_mode"] == "on_request_snapshot"
    assert body["hidden_sensing"] is False
    assert body["visible_indicator"] is True
    assert body["stores_raw_events"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["background_watcher"] is False
    assert body["governance"]["git_fetch"] is False
    assert body["governance"]["git_pull"] is False
    assert body["governance"]["git_push"] is False
    assert isinstance(body["changed_paths"], list)
    assert len(body["changed_paths"]) <= 5
    assert body["changed_count"] >= len(body["changed_paths"])
    assert not data_root.exists()

    status = client.get("/telemetry/status").json()
    sources = {source["id"]: source for source in status["sources"]}
    assert sources["git"]["routes"]["status"] == "/telemetry/git/status"
    if body["active"]:
        assert sources["git"]["active"] is True
        assert sources["git"]["status"] == "snapshot_ready"
        assert sources["git"]["latest_snapshot"]["branch"] == body["branch"]
