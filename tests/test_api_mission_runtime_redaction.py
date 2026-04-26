from __future__ import annotations

from pathlib import Path
from typing import Any


def test_mission_run_once_redacts_secret_handoff_text(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.missions import runtime as mission_runtime

    client = TestClient(create_app())
    created = client.post(
        "/missions/create",
        json={
            "objective": "Redact queue-run execution handoff text",
            "summary": "Mission queue results should not replay secrets.",
            "requester_id": "test.missions.queue",
        },
    )
    assert created.status_code == 200
    mission_id = str(created.json()["mission_id"])

    raw_secrets = {
        "error": "queueoutersecret123",
        "message": "queuemessagesecret123",
        "next_step": "queuenextstepsecret123",
        "operation_error": "queueoperationerrorsecret123",
        "result_message": "queueresultsecret123",
        "recovery_next_step": "queuerecoverysecret123",
    }

    def fail_advance(
        mission_id: str,
        *,
        actor: str = "missions.runner",
        note: str = "mission_advance",
        worker_id: str = "missions.runner",
        record_operator_receipt: bool = True,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "applied": False,
            "action": "create_first_operation",
            "mission_id": mission_id,
            "operation_id": "op_redaction",
            "status": "failed",
            "error": f"advance failed password={raw_secrets['error']}",
            "message": f"operation message token={raw_secrets['message']}",
            "next_step": f"review next step api_key={raw_secrets['next_step']}",
            "operation_error": f"operation failed secret={raw_secrets['operation_error']}",
            "result_message": f"result message password={raw_secrets['result_message']}",
            "recovery_next_step": f"recover by review token={raw_secrets['recovery_next_step']}",
        }

    monkeypatch.setattr(mission_runtime, "advance_mission", fail_advance)

    run_once = client.post("/missions/run_once", json={"actor": "test.missions.queue", "limit": 10})
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is False
    assert body["error"] == "advance failed password=[REDACTED:secret]"

    result = body["results"][0]
    assert result["mission_id"] == mission_id
    assert result["message"] == "operation message token=[REDACTED:secret]"
    assert result["next_step"] == "review next step api_key=[REDACTED:secret]"
    assert result["operation_error"] == "operation failed secret=[REDACTED:secret]"
    assert result["result_message"] == "result message password=[REDACTED:secret]"
    assert result["recovery_next_step"] == "recover by review token=[REDACTED:secret]"

    error = body["errors"][0]
    assert error["error"] == "advance failed password=[REDACTED:secret]"
    assert error["message"] == "operation message token=[REDACTED:secret]"
    assert error["next_step"] == "review next step api_key=[REDACTED:secret]"
    assert error["operation_error"] == "operation failed secret=[REDACTED:secret]"
    assert error["result_message"] == "result message password=[REDACTED:secret]"
    assert error["recovery_next_step"] == "recover by review token=[REDACTED:secret]"

    body_text = str(body)
    for raw_secret in raw_secrets.values():
        assert raw_secret not in body_text


def test_mission_advance_redacts_secret_handoff_text(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.missions import runtime as mission_runtime

    client = TestClient(create_app())
    mission = client.post(
        "/missions/create",
        json={
            "objective": "Redact direct mission advance handoff text",
            "summary": "Direct advance responses should not replay secrets.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    operation = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "direct advance redaction",
            "mission_id": mission_id,
            "input": {"goal": "Create a linked operation for redaction proof"},
        },
    )
    assert operation.status_code == 200
    operation_id = str(operation.json()["operation_id"])

    raw_secrets = {
        "message": "advancemessagesecret123",
        "next_step": "advancenextstepsecret123",
        "operation_message": "advanceoperationmessagesecret123",
    }

    def run_operation(operation_id: str, *, worker_id: str = "missions.runner") -> dict[str, Any]:
        return {
            "ok": False,
            "status": "blocked",
            "message": f"advance message password={raw_secrets['message']}",
            "operation": {
                "id": operation_id,
                "name": "plan.create",
                "meta": {
                    "orb_plane": "P7_EXECUTION",
                    "governance": {
                        "gate": "review_gate",
                        "next_step": f"review next token={raw_secrets['next_step']}",
                    },
                    "result_message": f"operation message api_key={raw_secrets['operation_message']}",
                },
                "output": {},
            },
        }

    monkeypatch.setattr(mission_runtime.operations_runtime, "run_operation", run_operation)

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "worker_id": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    body = advanced.json()
    assert body["ok"] is False
    assert body["operation_id"] == operation_id
    assert body["message"] == "advance message password=[REDACTED:secret]"
    assert body["next_step"] == "review next token=[REDACTED:secret]"
    assert body["operation_message"] == "operation message api_key=[REDACTED:secret]"

    advance_events = [item for item in body["history"] if item.get("event") == "advance_receipt"]
    assert advance_events
    assert advance_events[-1]["details"]["message"] == "advance message password=[REDACTED:secret]"
