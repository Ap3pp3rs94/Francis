from __future__ import annotations

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


def _grant_capture_authority(client) -> dict[str, object]:  # type: ignore[no-untyped-def]
    requested = client.post(
        "/lens/perception/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request desktop capture authority for execution test",
        },
    ).json()
    approval_id = requested["approval_id"]
    decision = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve bounded desktop capture authority",
        },
    ).json()
    assert decision["status"] == "approved"
    granted = client.post(
        "/lens/perception/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "grant desktop capture authority for execution test",
            "lease_seconds": 120,
        },
    ).json()
    assert granted["status"] == "authority_granted"
    return granted["receipt"]


def test_perception_execution_request_refuses_without_active_capture_authority(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    response = client.post(
        "/lens/perception/execution/request",
        json={
            "actor": "test.system.write",
            "authority_receipt_id": "missing-receipt",
            "reason": "attempt execution request without sensing authority",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["approval_requested"] is False
    assert body["executed"] is False
    assert body["starts_capture"] is False
    assert body["launches_process"] is False
    assert "desktop_capture_authority_receipt_not_found" in body["blockers"]
    assert not (data_root / "approvals" / "pending").exists()
    assert not (data_root / "runtime" / "lens-perception").exists()


def test_perception_execution_request_becomes_ready_only_after_exact_operator_approval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    capture_receipt = _grant_capture_authority(client)
    receipt_id = str(capture_receipt["receipt_id"])

    requested = client.post(
        "/lens/perception/execution/request",
        json={
            "actor": "test.system.write",
            "authority_receipt_id": receipt_id,
            "reason": "request resident desktop perception worker execution",
        },
    )

    assert requested.status_code == 200
    request_body = requested.json()
    assert request_body["status"] == "approval_requested"
    assert request_body["approval_requested"] is True
    assert request_body["authority_receipt_id"] == receipt_id
    assert request_body["executed"] is False
    assert request_body["starts_capture"] is False
    assert request_body["launches_process"] is False
    approval_id = request_body["approval_id"]
    payload = request_body["approval"]["payload"]
    assert payload["kind"] == "lens.perception.desktop_capture_execution.request"
    assert payload["authority_receipt_id"] == receipt_id
    assert payload["requested_effects"]["desktop_capture_execution"] is True
    assert payload["camera_capture_authority"] is False
    assert payload["keyboard_capture_authority"] is False
    assert payload["user_mouse_capture_authority"] is False
    assert payload["memory_write"] is False

    pending = client.get("/lens/perception/execution?limit=10").json()
    assert pending["status"] == "pending_review"
    assert pending["execution_ready"] is False

    decision = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve exact resident desktop perception execution",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    ready = client.get("/lens/perception/execution?limit=10").json()
    assert ready["status"] == "approved_ready_for_execution"
    assert ready["execution_ready"] is True
    assert ready["execution_validation"]["approval_id"] == approval_id
    assert ready["execution_validation"]["authority_receipt_id"] == receipt_id
    assert ready["executed"] is False
    assert ready["starts_capture"] is False
    assert ready["launches_process"] is False
    assert not (data_root / "runtime" / "lens-perception").exists()
