from __future__ import annotations

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
    for source in sources.values():
        assert source["status"] == "not_connected"
        assert source["active"] is False
        assert source["visible_indicator"] is True
        assert source["hidden_sensing"] is False
        assert source["scope"]["status"] == "not_granted"
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
