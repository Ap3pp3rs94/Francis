from __future__ import annotations

import json
from pathlib import Path


def _client(monkeypatch, tmp_path: Path):
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    return TestClient(create_app()), data_root


def _request(client):  # type: ignore[no-untyped-def]
    response = client.post(
        "/lens/perception/input/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request bounded desktop input observation",
        },
    )
    assert response.status_code == 200
    return response.json()


def _approve(client, approval_id: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve bounded input observation metadata only",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_input_observation_request_is_exact_and_does_not_start_observation(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    body = _request(client)

    assert body["status"] == "approval_requested"
    assert body["authority_granted"] is False
    assert body["starts_observation"] is False
    approval = body["approval"]
    payload = approval["payload"]
    assert payload["source"] == "windows_desktop_input_events"
    assert payload["observations"] == [
        "cursor_position",
        "pointer_button_activity",
        "scroll_activity",
        "foreground_window_identity",
        "keyboard_activity_timing",
    ]
    assert payload["forbidden_content"] == [
        "keyboard_content",
        "key_codes",
        "typed_characters",
        "window_titles",
        "clipboard_content",
    ]
    assert payload["authority_boundary"]["input_execution_authority"] is False
    assert payload["authority_boundary"]["user_cursor_control_authority"] is False
    assert not (data_root / "runtime" / "lens-perception").exists()


def test_input_observation_grant_requires_approval_and_writes_only_authority_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    requested = _request(client)
    approval_id = requested["approval_id"]

    blocked = client.post(
        "/lens/perception/input/authority",
        json={"actor": "test.system.write", "approval_id": approval_id},
    ).json()
    assert blocked["status"] == "blocked"
    assert blocked["receipt_written"] is False
    assert "desktop_input_observation_authority_approval_not_approved" in blocked["blockers"]

    _approve(client, approval_id)
    granted = client.post(
        "/lens/perception/input/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "lease_seconds": 120,
        },
    ).json()

    assert granted["status"] == "authority_granted"
    assert granted["receipt_written"] is True
    assert granted["starts_observation"] is False
    assert granted["executed"] is False
    receipt = granted["receipt"]
    assert receipt["authorities"]["desktop_input_observation_authority"] is True
    assert receipt["authorities"]["keyboard_activity_timing_authority"] is True
    assert receipt["authorities"]["keyboard_content_capture_authority"] is False
    assert receipt["authorities"]["key_code_capture_authority"] is False
    assert receipt["authorities"]["window_title_capture_authority"] is False
    assert receipt["authorities"]["input_execution_authority"] is False
    assert receipt["authorities"]["user_cursor_control_authority"] is False
    receipt_path = (
        data_root / "lens" / "perception_desktop_input_observation_authority_grants" / f"{receipt['receipt_id']}.json"
    )
    assert receipt_path.exists()
    assert not (data_root / "runtime" / "lens-perception").exists()

    readback = client.get("/lens/perception/input/authority?limit=10").json()
    assert readback["status"] == "authority_granted"
    assert readback["active_authority_grant"]["receipt_id"] == receipt["receipt_id"]


def test_input_observation_receipt_fails_closed_if_approved_contract_is_widened(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    requested = _request(client)
    approval_id = requested["approval_id"]
    _approve(client, approval_id)
    granted = client.post(
        "/lens/perception/input/authority",
        json={"actor": "test.system.write", "approval_id": approval_id, "lease_seconds": 120},
    ).json()
    receipt_id = granted["receipt"]["receipt_id"]

    approval_path = data_root / "approvals" / "approved" / f"{approval_id}.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["payload"]["forbidden_content"] = []
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    readback = client.get("/lens/perception/input/authority/grants?active_only=false").json()
    validation = readback["latest"]["validation"]
    assert validation["receipt_id"] == receipt_id
    assert validation["active"] is False
    assert "desktop_input_observation_authority_approval_contract_invalid" in validation["blockers"]
