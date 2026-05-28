from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.telemetry.status import redact_telemetry_value


def test_telemetry_status_projects_stage7_readonly_baseline(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.status"
    assert body["stage"] == "Stage 7 / Telemetry MVP"
    assert body["status"] == "inactive"
    assert body["active"] is False
    assert body["claim"] == "telemetry_posture_contract_only"
    assert body["source_total"] == 3
    assert body["active_source_total"] == 0
    assert body["next_smallest_truthful_gap"] == "stage7_terminal_connector_scope_contract"

    sources = {source["id"]: source for source in body["sources"]}
    assert set(sources) == {"terminal", "git", "ide_diagnostics"}
    assert sources["terminal"]["status"] == "write_scope_required"
    assert sources["terminal"]["retention"]["event_count"] == 0
    assert sources["terminal"]["routes"]["record"] == "/telemetry/terminal/events"
    for source in sources.values():
        assert source["active"] is False
        assert source["visible_indicator"] is True
        assert source["hidden_sensing"] is False
        assert source["scope"]["denied_by_default"] is True
        assert source["signals"] == []
        assert source["retention"]["stores_raw_events"] is False
        assert source["redaction"]["redact_before_storage"] is True
        assert source["authority"]["telemetry_collection"] is False
        assert source["authority"]["execution_authority"] is False
        assert source["authority"]["memory_write"] is False

    assert body["redaction"]["stores_raw_secret_values"] is False
    assert body["retention"]["stores_raw_events"] is False
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
    assert status["active_source_total"] == 1
    assert status["retention"]["event_count"] == 1
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
