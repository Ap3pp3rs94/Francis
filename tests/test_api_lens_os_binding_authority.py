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


def test_lens_os_binding_authority_grant_requires_approved_request(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    request_response = client.post(
        "/lens/os-binding/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request governed OS-binding authority",
        },
    )
    assert request_response.status_code == 200
    request_body = request_response.json()
    approval_id = request_body["approval_id"]

    blocked_grant = client.post(
        "/lens/os-binding/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "try before approval",
        },
    )
    assert blocked_grant.status_code == 200
    blocked_body = blocked_grant.json()
    assert blocked_body["kind"] == "lens.os_binding.command_palette_binding_authority.grant_denial"
    assert blocked_body["status"] == "blocked"
    assert blocked_body["authority_granted"] is False
    assert blocked_body["os_level_command_palette_binding_authority"] is False
    assert blocked_body["applied"] is False
    assert blocked_body["executed"] is False
    assert blocked_body["receipt_written"] is False
    assert "os_binding_authority_approval_not_approved" in blocked_body["blockers"]
    assert blocked_body["governance"]["execution_authority"] is False
    assert blocked_body["governance"]["approval_decision_authority"] is False
    assert blocked_body["governance"]["memory_write"] is False
    assert blocked_body["governance"]["hotkey_registration_authority"] is False
    assert blocked_body["governance"]["summon_authority"] is False

    grants_before = client.get("/lens/os-binding/authority/grants?limit=10").json()
    assert grants_before["kind"] == "lens.os_binding.command_palette_binding_authority.grant_receipts"
    assert grants_before["status"] == "empty"
    assert grants_before["authority_granted"] is False
    assert grants_before["items"] == []
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_os_binding_authority_grant_writes_receipt_without_binding(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    request_response = client.post(
        "/lens/os-binding/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request governed OS-binding authority",
        },
    )
    assert request_response.status_code == 200
    approval_id = request_response.json()["approval_id"]

    decision = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "allow bounded authority grant receipt",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    grant = client.post(
        "/lens/os-binding/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "grant OS-binding authority receipt only",
            "lease_seconds": 120,
        },
    )
    assert grant.status_code == 200
    body = grant.json()
    assert body["kind"] == "lens.os_binding.command_palette_binding_authority.grant"
    assert body["status"] == "authority_granted"
    assert body["approval_id"] == approval_id
    assert body["authority_granted"] is True
    assert body["os_level_command_palette_binding_authority"] is True
    assert body["os_level_command_palette"] is False
    assert body["summon_anywhere"] is False
    assert body["opens_palette"] is False
    assert body["registers_hotkey"] is False
    assert body["launches_process"] is False
    assert body["controls_overlay"] is False
    assert body["applied"] is True
    assert body["executed"] is False
    assert body["receipt_written"] is True
    assert body["grant"]["grant_receipt_written"] is True
    receipt = body["receipt"]
    assert receipt["kind"] == "lens.os_binding.command_palette_binding_authority.grant_receipt"
    assert receipt["approval_id"] == approval_id
    assert receipt["authority_granted"] is True
    assert receipt["os_level_command_palette_binding_authority"] is True
    assert receipt["os_level_command_palette"] is False
    assert receipt["summon_anywhere"] is False
    assert receipt["opens_palette"] is False
    assert receipt["registers_hotkey"] is False
    assert receipt["launches_process"] is False
    assert receipt["controls_overlay"] is False
    assert receipt["lease_seconds"] == 120
    governance = body["governance"]
    assert governance["authority_grant_boundary"] is True
    assert governance["authority_granted"] is True
    assert governance["os_level_command_palette_binding_authority"] is True
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["memory_write"] is False
    assert governance["hotkey_registration_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["resident_claim_authority"] is False
    assert governance["mutation_authority_granted"] is False

    grants = client.get("/lens/os-binding/authority/grants?limit=10").json()
    assert grants["status"] == "readback_ready"
    assert grants["authority_granted"] is True
    assert grants["os_level_command_palette_binding_authority"] is True
    assert grants["active_latest"]["receipt_id"] == receipt["receipt_id"]
    assert grants["items"][0]["receipt_id"] == receipt["receipt_id"]
    assert grants["opens_palette"] is False
    assert grants["registers_hotkey"] is False
    assert grants["launches_process"] is False
    assert grants["controls_overlay"] is False

    readback = client.get("/lens/os-binding/authority/requests?limit=10").json()
    assert readback["status"] == "authority_granted"
    assert readback["active_grant_receipt_id"] == receipt["receipt_id"]
    assert readback["authority_granted"] is True
    assert readback["os_level_command_palette_binding_authority"] is True
    assert readback["os_level_command_palette"] is False
    assert readback["summon_anywhere"] is False
    assert readback["opens_palette"] is False
    assert readback["registers_hotkey"] is False
    assert readback["launches_process"] is False
    assert readback["controls_overlay"] is False

    readiness = client.get("/lens/os-binding/readiness").json()
    authority_readback = readiness["authority_request_readback"]
    assert authority_readback["status"] == "authority_granted"
    assert authority_readback["active_grant_receipt_id"] == receipt["receipt_id"]
    assert authority_readback["authority_granted"] is True
    assert authority_readback["os_level_command_palette_binding_authority"] is True
    assert readiness["status"] == "blocked"
    assert readiness["ready"] is False
    assert readiness["os_level_command_palette"] is False
    assert readiness["summon_anywhere"] is False

    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()
