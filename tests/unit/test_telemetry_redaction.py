from __future__ import annotations

import json
from pathlib import Path


def test_audit_record_redacts_secret_fields_and_values(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.telemetry.audit import read_events, record

    event = record(
        "telemetry.redaction",
        actor="test.telemetry",
        reason="audit reason password=auditreasonsecret123",
        token="auditfieldsecret123",
        meta={
            "ticket": "TEL-1",
            "operator_note": "api_key=auditmetasecret123",
            "path": Path("C:/tmp/password=auditpathsecret123"),
        },
    )

    assert event["reason"] == "audit reason password=[REDACTED:secret]"
    assert event["token"] == "[REDACTED:secret]"
    assert event["meta"]["ticket"] == "TEL-1"
    assert event["meta"]["operator_note"] == "api_key=[REDACTED:secret]"
    assert str(event["meta"]["path"]).replace("\\", "/") == "C:/tmp/password=[REDACTED:secret]"

    events = read_events(limit=10, event="telemetry.redaction")
    assert events[-1]["reason"] == "audit reason password=[REDACTED:secret]"

    audit_text = (data_root / "logs" / "audit" / "audit.jsonl").read_text(encoding="utf-8")
    assert "auditreasonsecret123" not in audit_text
    assert "auditfieldsecret123" not in audit_text
    assert "auditmetasecret123" not in audit_text
    assert "auditpathsecret123" not in audit_text
    assert "TEL-1" in audit_text


def test_operation_and_error_logs_redact_secret_fields_and_values(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.telemetry.logging import error, log

    log(
        "telemetry.log.redaction",
        reason="log reason token=logreasonsecret123",
        meta={"ticket": "LOG-1", "operator_note": "secret=logmetasecret123"},
        api_key="logfieldsecret123",
    )
    error(
        "telemetry.error.redaction",
        message="error message password=errormessagesecret123",
        token="errorfieldsecret123",
        meta={"ticket": "ERR-1", "operator_note": "token=errormetasecret123"},
    )

    operation_log = data_root / "logs" / "operations" / "francis.jsonl"
    error_log = data_root / "logs" / "errors" / "errors.jsonl"
    operation_payload = json.loads(operation_log.read_text(encoding="utf-8").splitlines()[-1])
    error_payload = json.loads(error_log.read_text(encoding="utf-8").splitlines()[-1])

    assert operation_payload["reason"] == "log reason token=[REDACTED:secret]"
    assert operation_payload["api_key"] == "[REDACTED:secret]"
    assert operation_payload["meta"]["operator_note"] == "secret=[REDACTED:secret]"
    assert operation_payload["meta"]["ticket"] == "LOG-1"
    assert error_payload["message"] == "error message password=[REDACTED:secret]"
    assert error_payload["token"] == "[REDACTED:secret]"
    assert error_payload["meta"]["operator_note"] == "token=[REDACTED:secret]"
    assert error_payload["meta"]["ticket"] == "ERR-1"

    combined = "\n".join(
        [
            operation_log.read_text(encoding="utf-8"),
            error_log.read_text(encoding="utf-8"),
        ]
    )
    for raw in (
        "logreasonsecret123",
        "logmetasecret123",
        "logfieldsecret123",
        "errormessagesecret123",
        "errorfieldsecret123",
        "errormetasecret123",
    ):
        assert raw not in combined
